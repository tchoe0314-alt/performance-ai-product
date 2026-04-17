"use client";

import { useEffect } from "react";

import type { JobSummary } from "../types";

type UseJobPollingOptions = {
  token: string;
  activeJobId: string;
  visibleActiveJob: JobSummary | null;
  visibleActiveJobStale: boolean;
  onLoadJob: (jobId: string) => void;
  onRefreshJobs: (token: string, options?: { suppressError?: boolean; force?: boolean }) => void;
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
  useEffect(() => {
    if (!token || !activeJobId) return;
    onLoadJob(activeJobId);
    onRefreshJobs(token, { suppressError: true, force: true });
    const interval = window.setInterval(() => {
      onLoadJob(activeJobId);
      onRefreshJobs(token, { suppressError: true, force: true });
    }, 3000);
    return () => window.clearInterval(interval);
  }, [token, activeJobId, onLoadJob, onRefreshJobs]);

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
