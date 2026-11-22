import { useCallback, useMemo, useRef, useState } from "react";

import { getJson } from "../../lib/api";

import type { JobSummary } from "../types";
import { mergeJobSummaries } from "../utils/jobSummaryMerge";

type RefreshJobsOptions = { suppressError?: boolean; force?: boolean };

export default function useJobsState({ activeJobId }: { activeJobId: string }) {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const refreshInFlightRef = useRef<Promise<void> | null>(null);
  const latestJobUpdatedAtRef = useRef<Record<string, number>>({});

  const hasTrackedJobs = useMemo(
    () =>
      Boolean(activeJobId) ||
      jobs.some((job) =>
        ["queued", "running", "awaiting_approval", "cancelling"].includes(
          String(job.status || "").toLowerCase(),
        ),
      ),
    [activeJobId, jobs],
  );

  const refreshJobs = useCallback(async (
    authToken: string,
    {
      suppressError = false,
      force = false,
    }: RefreshJobsOptions = {},
  ) => {
    if (!authToken) return;
    if (!force && !hasTrackedJobs) return;
    if (refreshInFlightRef.current) {
      return refreshInFlightRef.current;
    }
    const request = (async () => {
      try {
        const data = await getJson<{ jobs: JobSummary[] }>("/api/jobs", {
          token: authToken,
        });
        const incoming = Array.isArray(data.jobs) ? data.jobs : [];
        incoming.forEach((job) => {
          const updatedAt = Number(job.updated_at);
          if (Number.isFinite(updatedAt) && updatedAt > (latestJobUpdatedAtRef.current[job.job_id] ?? 0)) {
            latestJobUpdatedAtRef.current[job.job_id] = updatedAt;
          }
        });
        setJobs(current => mergeJobSummaries(current, incoming));
      } catch (error) {
        if (!suppressError) {
          throw error;
        }
      } finally {
        refreshInFlightRef.current = null;
      }
    })();
    refreshInFlightRef.current = request;
    return request;
  }, [hasTrackedJobs]);

  return {
    jobs,
    setJobs,
    latestJobUpdatedAtRef,
    hasTrackedJobs,
    refreshJobs,
  };
}
