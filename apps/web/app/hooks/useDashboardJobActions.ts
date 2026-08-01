import { useCallback } from "react";
import type { MutableRefObject } from "react";

import { postJson } from "../../lib/api";
import type { ChatMessage, JobSummary, PlanToolMode } from "../types";
import type { WorkspaceToast } from "../components/WorkspaceToasts";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type RefreshJobs = (
  authToken: string,
  options?: { suppressError?: boolean; force?: boolean },
) => Promise<void>;

type UseDashboardJobActionsOptions = {
  activeJobId: string;
  appendChatMessage: AppendChatMessage;
  directRunAbortRef: MutableRefObject<AbortController | null>;
  previewNextPendingPhase?: { label?: string | null } | null;
  previewRunningPhase?: { label?: string | null } | null;
  queuePreviewRefresh: (reason: string) => void;
  refreshJobs: RefreshJobs;
  runSubmissionRef: MutableRefObject<boolean>;
  setActiveJobId: StateSetter<string>;
  setActivePlanTool: StateSetter<PlanToolMode>;
  setApprovalError: StateSetter<string | null>;
  setApprovalInFlight: StateSetter<boolean>;
  setApprovalPendingJobId: StateSetter<string | null>;
  setApprovalPhaseLabel: StateSetter<string | null>;
  setBusy: StateSetter<boolean>;
  setJobs: StateSetter<JobSummary[]>;
  setJobToasts: StateSetter<WorkspaceToast[]>;
  setSelectedJobId: StateSetter<string>;
  setStatusMessage: (message: string) => void;
  token: string | null;
  visibleActiveJob?: JobSummary | null;
};

export function useDashboardJobActions({
  activeJobId,
  appendChatMessage,
  directRunAbortRef,
  previewNextPendingPhase,
  previewRunningPhase,
  queuePreviewRefresh,
  refreshJobs,
  runSubmissionRef,
  setActiveJobId,
  setActivePlanTool,
  setApprovalError,
  setApprovalInFlight,
  setApprovalPendingJobId,
  setApprovalPhaseLabel,
  setBusy,
  setJobs,
  setJobToasts,
  setSelectedJobId,
  setStatusMessage,
  token,
  visibleActiveJob,
}: UseDashboardJobActionsOptions) {
  const pushJobToast = useCallback((toast: Omit<WorkspaceToast, "id">) => {
    const id = `job-toast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setJobToasts((current) => [{ id, ...toast }, ...current].slice(0, 4));
    window.setTimeout(() => {
      setJobToasts((current) => current.filter((item) => item.id !== id));
    }, 6500);
  }, [setJobToasts]);

  const upsertJobSummary = useCallback((job: JobSummary) => {
    setJobs((current) => {
      const next = [...current];
      const index = next.findIndex((item) => item.job_id === job.job_id);
      if (index >= 0) {
        next[index] = { ...next[index], ...job };
      } else {
        next.unshift(job);
      }
      return next;
    });
  }, [setJobs]);

  const handleCancelJobById = useCallback(async (jobId: string) => {
    if (!token || !jobId) return;
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${jobId}/cancel`,
        {},
        { token },
      );
      upsertJobSummary(data.job);
      appendChatMessage("assistant", `Job ${data.job.job_id} was cancelled.`, "status");
      pushJobToast({
        title: "Job cancelled",
        detail: data.job.job_id,
        tone: "warning",
      });
      setStatusMessage(`Cancelled job ${data.job.job_id}.`);
      if (activeJobId === data.job.job_id) {
        setActiveJobId("");
      }
      setBusy(false);
      runSubmissionRef.current = false;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Job cancel failed.";
      setStatusMessage(message);
      pushJobToast({ title: "Cancel failed", detail: message, tone: "error" });
    }
  }, [
    activeJobId,
    appendChatMessage,
    pushJobToast,
    runSubmissionRef,
    setActiveJobId,
    setBusy,
    setStatusMessage,
    token,
    upsertJobSummary,
  ]);

  const handleCancelActiveJob = useCallback(async () => {
    if (visibleActiveJob?.job_id && token) {
      await handleCancelJobById(visibleActiveJob.job_id);
      return;
    }
    if (directRunAbortRef.current) {
      directRunAbortRef.current.abort();
      directRunAbortRef.current = null;
      runSubmissionRef.current = false;
      setBusy(false);
      setActivePlanTool("run");
      setStatusMessage("Cancelling the live request...");
      return;
    }
  }, [
    directRunAbortRef,
    handleCancelJobById,
    runSubmissionRef,
    setActivePlanTool,
    setBusy,
    setStatusMessage,
    token,
    visibleActiveJob?.job_id,
  ]);

  const handleRetryJob = useCallback(async (jobId: string) => {
    if (!token || !jobId) return;
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${jobId}/retry`,
        {},
        { token },
      );
      upsertJobSummary(data.job);
      setActiveJobId(data.job.job_id);
      setSelectedJobId(data.job.job_id);
      await refreshJobs(token, { suppressError: true, force: true });
      appendChatMessage("assistant", `Retry queued as job ${data.job.job_id}.`, "status");
      pushJobToast({
        title: "Retry queued",
        detail: `${data.job.job_id} from ${jobId}`,
        tone: "info",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Job retry failed.";
      setStatusMessage(message);
      pushJobToast({ title: "Retry failed", detail: message, tone: "error" });
    }
  }, [
    appendChatMessage,
    pushJobToast,
    refreshJobs,
    setActiveJobId,
    setSelectedJobId,
    setStatusMessage,
    token,
    upsertJobSummary,
  ]);

  const handleResumeJob = useCallback(async (jobId: string) => {
    if (!token || !jobId) return;
    setJobs((current) =>
      current.map((job) =>
        job.job_id === jobId
          ? {
              ...job,
              can_resume: false,
              stage_detail: "Sending approval and preparing the next phase...",
            }
          : job,
      ),
    );
    setStatusMessage(`Sending approval for ${jobId}...`);
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${jobId}/continue`,
        {},
        { token },
      );
      upsertJobSummary(data.job);
      setActiveJobId(data.job.job_id);
      setSelectedJobId(data.job.job_id);
      await refreshJobs(token, { suppressError: true, force: true });
      appendChatMessage("assistant", `Resumed job ${data.job.job_id}.`, "status");
      pushJobToast({
        title: "Job resumed",
        detail: data.job.job_id,
        tone: "success",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not resume job.";
      setJobs((current) =>
        current.map((job) =>
          job.job_id === jobId ? { ...job, can_resume: true } : job,
        ),
      );
      setStatusMessage(message);
      pushJobToast({ title: "Resume failed", detail: message, tone: "error" });
    }
  }, [
    appendChatMessage,
    pushJobToast,
    refreshJobs,
    setActiveJobId,
    setJobs,
    setSelectedJobId,
    setStatusMessage,
    token,
    upsertJobSummary,
  ]);

  const handleContinueActiveJob = useCallback(async () => {
    if (!token) return;
    if (!visibleActiveJob?.job_id) {
      setStatusMessage("No active job is waiting at a review hold.");
      return;
    }
    const status = String(visibleActiveJob.status || "").toLowerCase();
    if (status !== "awaiting_approval") {
      setStatusMessage("There is no phase waiting at a review hold right now.");
      return;
    }
    const nextPhaseLabel =
      previewNextPendingPhase?.label || previewRunningPhase?.label || "Next phase";
    setApprovalError(null);
    setApprovalPhaseLabel(nextPhaseLabel);
    setApprovalInFlight(true);
    setBusy(true);
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${visibleActiveJob.job_id}/continue`,
        {},
        { token },
      );
      upsertJobSummary(data.job);
      appendChatMessage(
        "assistant",
        `Accepted the current phase for review workflow. Starting ${nextPhaseLabel}.`,
        "status",
      );
      pushJobToast({
        title: "Job resumed",
        detail: `${data.job.job_id} starting ${nextPhaseLabel}`,
        tone: "success",
      });
      setStatusMessage(`Accepted ${data.job.job_id} for review workflow. Starting ${nextPhaseLabel}.`);
      if (data.job.job_id) {
        setActiveJobId(data.job.job_id);
        setApprovalPendingJobId(data.job.job_id);
      }
      await refreshJobs(token, { suppressError: true, force: true });
      queuePreviewRefresh("Refreshing preview after review step...");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not continue the staged run.";
      setApprovalError(message);
      setStatusMessage(message);
      pushJobToast({ title: "Resume failed", detail: message, tone: "error" });
    } finally {
      setBusy(false);
      setApprovalInFlight(false);
    }
  }, [
    appendChatMessage,
    previewNextPendingPhase?.label,
    previewRunningPhase?.label,
    pushJobToast,
    queuePreviewRefresh,
    refreshJobs,
    setActiveJobId,
    setApprovalError,
    setApprovalInFlight,
    setApprovalPendingJobId,
    setApprovalPhaseLabel,
    setBusy,
    setStatusMessage,
    token,
    upsertJobSummary,
    visibleActiveJob?.job_id,
    visibleActiveJob?.status,
  ]);

  return {
    handleCancelActiveJob,
    handleCancelJobById,
    handleContinueActiveJob,
    handleResumeJob,
    handleRetryJob,
  };
}
