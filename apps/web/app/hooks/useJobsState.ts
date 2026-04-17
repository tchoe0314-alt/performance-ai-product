import { useCallback, useMemo, useState } from "react";

import { getJson } from "../../lib/api";

import type { JobSummary } from "../types";

type RefreshJobsOptions = { suppressError?: boolean; force?: boolean };

export default function useJobsState({ activeJobId }: { activeJobId: string }) {
  const [jobs, setJobs] = useState<JobSummary[]>([]);

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
    try {
      const data = await getJson<{ jobs: JobSummary[] }>("/api/jobs", {
        token: authToken,
      });
      setJobs(Array.isArray(data.jobs) ? data.jobs : []);
    } catch (error) {
      if (!suppressError) {
        throw error;
      }
    }
  }, [hasTrackedJobs]);

  return {
    jobs,
    setJobs,
    hasTrackedJobs,
    refreshJobs,
  };
}
