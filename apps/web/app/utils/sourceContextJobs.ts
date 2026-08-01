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

const wait = (durationMs: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, durationMs));

export async function runQueuedSourceContextLookup({
  projectId,
  request,
  token,
  onProgress,
}: {
  projectId?: string | null;
  request: SourceContextRequest;
  token: string;
  onProgress?: (job: SourceContextJob) => void;
}): Promise<OnlineExistingConditionsFetchResponse> {
  let queued: { job: SourceContextJob };
  try {
    queued = await postJson<{ job: SourceContextJob }>(
      "/api/jobs/source-context",
      {
        project_id: projectId || null,
        request,
      },
      { token },
    );
  } catch (error) {
    if ((error as { status?: number })?.status !== 404) {
      throw error;
    }
    return postJsonWithTimeout<OnlineExistingConditionsFetchResponse>(
      "/api/existing-conditions/fetch-online",
      request,
      { token },
      90000,
    );
  }

  const jobId = String(queued.job?.job_id || "");
  if (!jobId) {
    throw new Error("Source lookup did not return a trackable background job.");
  }
  onProgress?.(queued.job);

  const deadline = Date.now() + 180000;
  let lastJob = queued.job;
  let pollFailureCount = 0;
  let lastPollError: unknown = null;
  while (Date.now() < deadline) {
    await wait(pollFailureCount ? Math.min(5000, 1250 * (pollFailureCount + 1)) : 1250);
    let job: SourceContextJob;
    try {
      const detail = await getJson<{ job: SourceContextJob }>(`/api/jobs/${jobId}`, { token });
      job = detail.job;
      lastJob = job;
      pollFailureCount = 0;
      lastPollError = null;
    } catch (error) {
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
      throw new Error("Source lookup was cancelled.");
    }
  }
  const lastErrorMessage = lastPollError instanceof Error ? ` Last status check: ${lastPollError.message}` : "";
  throw new Error(`Source lookup is still running. It remains visible in Jobs and can finish in the background.${lastErrorMessage}`);
}
