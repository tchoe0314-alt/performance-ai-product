import { getJson, postJson, postJsonWithTimeout } from "../../lib/api";
import type { OnlineExistingConditionsFetchResponse } from "./dashboardDataTypes";

type SourceContextJob = {
  job_id: string;
  status: string;
  stage?: string;
  stage_detail?: string;
  progress?: number;
  error?: string | null;
  result?: OnlineExistingConditionsFetchResponse;
};

type SourceContextRequest = Record<string, unknown>;

const abortError = () => new DOMException("Source lookup cancelled.", "AbortError");

const wait = (durationMs: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    const timeout = window.setTimeout(() => {
      signal?.removeEventListener("abort", handleAbort);
      resolve();
    }, durationMs);
    const handleAbort = () => {
      window.clearTimeout(timeout);
      reject(abortError());
    };
    signal?.addEventListener("abort", handleAbort, { once: true });
  });

export async function runQueuedSourceContextLookup({
  projectId,
  request,
  token,
  onProgress,
  onQueued,
  signal,
}: {
  projectId?: string | null;
  request: SourceContextRequest;
  token: string;
  onProgress?: (job: SourceContextJob) => void;
  onQueued?: (job: SourceContextJob) => void;
  signal?: AbortSignal;
}): Promise<OnlineExistingConditionsFetchResponse> {
  if (signal?.aborted) throw abortError();
  let queued: { job: SourceContextJob };
  try {
    queued = await postJson<{ job: SourceContextJob }>(
      "/api/jobs/source-context",
      {
        project_id: projectId || null,
        request,
      },
      { token, signal },
    );
  } catch (error) {
    if ((error as { status?: number })?.status !== 404) {
      throw error;
    }
    return postJsonWithTimeout<OnlineExistingConditionsFetchResponse>(
      "/api/existing-conditions/fetch-online",
      request,
      { token, signal },
      90000,
    );
  }

  const jobId = String(queued.job?.job_id || "");
  if (!jobId) {
    throw new Error("Source lookup did not return a trackable background job.");
  }
  onQueued?.(queued.job);
  onProgress?.(queued.job);

  const cancelQueuedJob = () => {
    void postJson(`/api/jobs/${jobId}/cancel`, {}, { token }).catch(() => undefined);
  };
  signal?.addEventListener("abort", cancelQueuedJob, { once: true });

  try {
    const deadline = Date.now() + 180000;
    let lastJob = queued.job;
    let pollFailureCount = 0;
    let lastPollError: unknown = null;
    while (Date.now() < deadline) {
      await wait(pollFailureCount ? Math.min(5000, 1250 * (pollFailureCount + 1)) : 1250, signal);
      let job: SourceContextJob;
      try {
        const detail = await getJson<{ job: SourceContextJob }>(`/api/jobs/${jobId}`, { token, signal });
        job = detail.job;
        lastJob = job;
        pollFailureCount = 0;
        lastPollError = null;
      } catch (error) {
        if (signal?.aborted) throw abortError();
        const status = Number((error as { status?: number })?.status || 0);
        if (status === 401 || status === 403) {
          throw error;
        }
        pollFailureCount += 1;
        lastPollError = error;
        onProgress?.({
          ...lastJob,
          status: "running",
          stage: lastJob.stage || "source_context",
          stage_detail: "Source lookup is still running; reconnecting to its background status...",
        });
        continue;
      }
      onProgress?.(job);
      const status = String(job.status || "").toLowerCase();
      if (status === "completed") {
        if (!job.result || typeof job.result !== "object") {
          throw new Error("Source lookup completed without a usable result.");
        }
        return job.result;
      }
      if (status === "failed") {
        throw new Error(job.error || "Source lookup failed. Retry the source check.");
      }
      if (status === "cancelled") {
        throw abortError();
      }
    }
    const lastErrorMessage = lastPollError instanceof Error ? ` Last status check: ${lastPollError.message}` : "";
    throw new Error(`Source lookup is still running. It remains visible in Jobs and can finish in the background.${lastErrorMessage}`);
  } finally {
    signal?.removeEventListener("abort", cancelQueuedJob);
  }
}
