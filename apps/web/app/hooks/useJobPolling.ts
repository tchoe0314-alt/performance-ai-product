"use client";

import { useEffect, useRef } from "react";

import type { JobSummary } from "../types";

type UseJobPollingOptions = {
  token: string;
  activeJobId: string;
  visibleActiveJob: JobSummary | null;
  visibleActiveJobStale: boolean;
  onLoadJob: (jobId: string) => Promise<void> | void;
  onRefreshJobs: (token: string, options?: { suppressError?: boolean; force?: boolean }) => Promise<void> | void;
  setJobClockMs: (value: number) => void;
  setActiveJobId: (value: string) => void;
  currentProjectActiveJob: JobSummary | null;
  onStatusMessage: (message: string) => void;
  lastStaleJobWarningRef: React.MutableRefObject<Record<string, boolean>>;
};

export const ACTIVE_JOB_POLL_INTERVAL_MS = 2_000;

export function shouldPollActiveJob(status: string | undefined, documentHidden: boolean): boolean {
  if (documentHidden) return false;
  const normalizedStatus = String(status || "").toLowerCase();
  return !normalizedStatus || ["queued", "running", "cancelling"].includes(normalizedStatus);
}

export async function runActiveJobPoll(input: {
  status?: string;
  documentHidden: boolean;
  inFlight: { current: boolean };
  load: () => Promise<unknown> | unknown;
  refresh: () => Promise<unknown> | unknown;
}): Promise<boolean> {
  if (!shouldPollActiveJob(input.status, input.documentHidden) || input.inFlight.current) return false;
  input.inFlight.current = true;
  try {
    await Promise.allSettled([Promise.resolve(input.load()), Promise.resolve(input.refresh())]);
    return true;
  } finally {
    input.inFlight.current = false;
  }
}

export default function useJobPolling({
  token,
  activeJobId,
  visibleActiveJob,
  visibleActiveJobStale,
  onLoadJob,
  onRefreshJobs,
  setJobClockMs,
  setActiveJobId,
  currentProjectActiveJob,
  onStatusMessage,
  lastStaleJobWarningRef,
}: UseJobPollingOptions) {
  const pollInFlightRef = useRef(false);
  const loadJobRef = useRef(onLoadJob);
  const refreshJobsRef = useRef(onRefreshJobs);

  useEffect(() => {
    loadJobRef.current = onLoadJob;
  }, [onLoadJob]);

  useEffect(() => {
    refreshJobsRef.current = onRefreshJobs;
  }, [onRefreshJobs]);

  useEffect(() => {
    if (!token || !activeJobId) return;
    const normalizedStatus = String(visibleActiveJob?.status || "").toLowerCase();
    if (normalizedStatus && !["queued", "running", "cancelling"].includes(normalizedStatus)) {
      return;
    }

    const poll = async () => {
      await runActiveJobPoll({
        status: visibleActiveJob?.status,
        documentHidden: document.hidden,
        inFlight: pollInFlightRef,
        load: () => loadJobRef.current(activeJobId),
        refresh: () => refreshJobsRef.current(token, { suppressError: true, force: true }),
      });
    };

    void poll();
    const interval = window.setInterval(() => {
      void poll();
    // Review checkpoints are explicit user decisions. A four-second status
    // cadence made every approval feel unresponsive and added avoidable time
    // to a multi-stage run without reducing backend work. Two seconds keeps
    // requests bounded while making the saved checkpoint available promptly.
    }, ACTIVE_JOB_POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [token, activeJobId, visibleActiveJob?.status]);

  useEffect(() => {
    if (!currentProjectActiveJob) {
      return;
    }
    if (!activeJobId) {
      setActiveJobId(currentProjectActiveJob.job_id);
    }
  }, [activeJobId, currentProjectActiveJob, setActiveJobId]);

  useEffect(() => {
    if (!visibleActiveJob) return;
    const interval = window.setInterval(() => {
      setJobClockMs(Date.now());
    }, 5000);
    return () => window.clearInterval(interval);
  }, [visibleActiveJob, setJobClockMs]);

  useEffect(() => {
    if (!visibleActiveJob?.job_id) return;
    const normalizedStatus = String(visibleActiveJob.status || "").toLowerCase();
    if (!visibleActiveJobStale || normalizedStatus !== "running") {
      delete lastStaleJobWarningRef.current[visibleActiveJob.job_id];
      return;
    }
    if (lastStaleJobWarningRef.current[visibleActiveJob.job_id]) {
      return;
    }
    lastStaleJobWarningRef.current[visibleActiveJob.job_id] = true;
    onStatusMessage(
      "Civora AI has not received a recent status update from the backend. The run may still be in progress.",
    );
  }, [visibleActiveJob, visibleActiveJobStale, lastStaleJobWarningRef, onStatusMessage]);
}
