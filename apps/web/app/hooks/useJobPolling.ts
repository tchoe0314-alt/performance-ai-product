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
      if (pollInFlightRef.current) return;
      pollInFlightRef.current = true;
      try {
        await Promise.allSettled([
          Promise.resolve(loadJobRef.current(activeJobId)),
          Promise.resolve(refreshJobsRef.current(token, { suppressError: true, force: true })),
        ]);
      } finally {
        pollInFlightRef.current = false;
      }
    };

    void poll();
    const interval = window.setInterval(() => {
      void poll();
    }, 4000);
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
