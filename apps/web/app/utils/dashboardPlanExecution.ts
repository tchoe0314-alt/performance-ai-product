import { postJson } from "../../lib/api";
import type { ChatMessage, JobSummary, PlanRequestPayload, PlanResponse, PlanToolMode, PreviewRequestPayload } from "../types";
import { panelErrorMessage } from "./dashboardStatus";
import { summarizePlanResponse } from "./formatting";
import type { ProjectStatusSummary } from "./workspaceShell";

export const isConnectivityFailureMessage = (message: string) =>
  message.toLowerCase().includes("backend unreachable") ||
  message.includes("could not reach the backend") || message.includes("Failed to fetch") ||
  message.includes("Load failed") || message.includes("NetworkError");

export type DashboardPlanExecutionRequest = {
  mode: PlanToolMode;
  requestPayload: PlanRequestPayload;
  resolvedProjectId?: string | null;
  assistantPrefix?: string | null;
  clearPromptOnSuccess?: boolean;
  signal?: AbortSignal;
  timeoutMs?: number;
  allowQueueFallback?: boolean;
  forceQueue?: boolean;
};

export type DashboardPlanExecutionOutcome = "completed" | "queued" | "blocked" | "cancelled" | "stale";
export type DashboardPlanExecutor = (request: DashboardPlanExecutionRequest) => Promise<DashboardPlanExecutionOutcome>;

type PlanExecutionOptions = {
  token: string | null;
  projectId: string;
  currentProjectId?: string;
  fileName: string;
  siteName: string;
  getWorkspaceGeneration: () => number;
  directRunAbortRef: { current: AbortController | null };
  setBusy: (busy: boolean) => void;
  setActivePlanTool: (mode: PlanToolMode) => void;
  setActiveJobId: (id: string) => void;
  setPrompt: (prompt: string) => void;
  setStatusMessage: (message: string) => void;
  updateProjectStatus: (status: Omit<ProjectStatusSummary, "updatedAt">) => void;
  appendChatMessage: (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
  applyBackendResult: (result: PlanResponse) => void;
  requestPreview: (payload: PreviewRequestPayload, options?: { silent?: boolean }) => Promise<void>;
  post?: typeof postJson;
};

/** Owns run/queue/cancellation lifecycle, not engineering math or project persistence. */
export function createDashboardPlanExecutor(options: PlanExecutionOptions): DashboardPlanExecutor {
  const { token, projectId, currentProjectId, fileName, siteName, directRunAbortRef,
    setBusy, setActivePlanTool, setActiveJobId, setPrompt, setStatusMessage,
    updateProjectStatus, appendChatMessage, applyBackendResult, requestPreview } = options;
  const post = options.post ?? postJson;
  return async ({ mode, requestPayload, resolvedProjectId, assistantPrefix,
    clearPromptOnSuccess = false, signal, timeoutMs = 12_000,
    allowQueueFallback = true, forceQueue = false }: DashboardPlanExecutionRequest) => {
    if (signal?.aborted) return "cancelled";
    const generation = options.getWorkspaceGeneration();
    const runOwner = directRunAbortRef.current;
    const isCurrent = () => options.getWorkspaceGeneration() === generation;
    const canPublish = () => isCurrent() && !signal?.aborted;
    const prefix = (message: string) => [assistantPrefix, message].filter(Boolean).join(" ");
    const queueRun = () => post<{ job: JobSummary }>("/api/jobs/orchestrate", {
      project_id: resolvedProjectId !== undefined ? resolvedProjectId : ((requestPayload.project_id ?? projectId) || null),
      request: requestPayload,
    }, { token, signal });
    const publishQueued = (job: JobSummary, staged: boolean, reason?: "timeout" | "connection") => {
      if (!canPublish()) return;
      setActiveJobId(job.job_id);
      const explanation = staged
        ? forceQueue
          ? `I queued this long-running engineering workflow as ${job.job_id} so progress stays visible while the backend works.`
          : `I queued the full staged design workflow as ${job.job_id} so each phase can save, pause for review, and continue on the same project.`
        : `${reason === "connection" ? "The direct connection was interrupted" : "The live run took too long to stay on the direct connection"}, so I queued it in the background instead. Job ${job.job_id} is now running and I’ll pick it up when it finishes.`;
      appendChatMessage("assistant", prefix(explanation), "status");
      updateProjectStatus({ state: "working", area: "generate", title: "Generate queued",
        detail: staged ? `Queued staged run ${job.job_id}.` : `The live run was queued as ${job.job_id} because ${reason === "connection" ? "the direct connection was interrupted" : "the direct request took too long"}.`,
        nextAction: "Open Jobs or watch the visible job status until the backend finishes." });
      if (staged && clearPromptOnSuccess) setPrompt("");
    };
    const publishQueueFailure = (error: unknown, staged: boolean, reason?: "timeout" | "connection") => {
      if (!canPublish()) return;
      const timeoutFailure = reason === "timeout";
      appendChatMessage("assistant", `${timeoutFailure ? "Generate failed" : "Generate could not complete"}: ${panelErrorMessage(error, timeoutFailure ? "Job queue failed." : "Job queue could not complete.")} Next action: check the backend connection, then press Generate again.`, "status");
      updateProjectStatus({ state: "blocked", area: "generate", title: staged ? "Generate needs sign-in" : "Generate needs attention",
        detail: panelErrorMessage(error, "Job queue failed."), nextAction: "Check the backend connection, then press Generate again." });
    };
    setBusy(true);
    setActivePlanTool(mode);
    updateProjectStatus({ state: "working", area: "generate",
      title: mode === "fix" ? "Fix pass working" : mode === "improve" ? "Improvement pass working" : "Generate working",
      detail: mode === "fix" ? "Civora AI is starting the fix run." : mode === "improve" ? "Civora AI is starting the improvement run." : "Civora AI is starting the review draft run.",
      nextAction: "Keep this project open until the run finishes or shows what needs attention." });
    const liveRunController = new AbortController();
    const handleAbort = () => liveRunController.abort();
    signal?.addEventListener("abort", handleAbort, { once: true });
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let timedOut = false;
    try {
      if ((forceQueue || requestPayload.full_design_mode) && token) {
        try {
          const queued = await queueRun();
          if (!canPublish()) return isCurrent() ? "cancelled" : "stale";
          publishQueued(queued.job, true);
          return "queued";
        } catch (error) {
          publishQueueFailure(error, true);
          return !isCurrent() ? "stale" : signal?.aborted ? "cancelled" : "blocked";
        }
      }
      timeoutId = setTimeout(() => { timedOut = true; liveRunController.abort(); }, timeoutMs);
      const data = await post<PlanResponse>("/api/orchestrate", requestPayload, { token, signal: liveRunController.signal });
      if (!canPublish()) return isCurrent() ? "cancelled" : "stale";
      applyBackendResult(data);
      appendChatMessage("assistant", prefix(summarizePlanResponse(data, mode)));
      await requestPreview({ project_id: projectId || currentProjectId || null, result: data, filename_stem: fileName || siteName || "civora-ai-plan" }, { silent: true });
      if (!canPublish()) return isCurrent() ? "cancelled" : "stale";
      const detail = mode === "fix" ? "Civora AI ran a focused fix pass." : mode === "improve" ? "Civora AI generated an improved plan." : "Plan run completed.";
      setStatusMessage(detail);
      updateProjectStatus({ state: "needs review", area: "generate", title: mode === "fix" ? "Fix pass needs review" : mode === "improve" ? "Improvement pass needs review" : "Generate needs review",
        detail, nextAction: "Review the generated draft, needs, assumptions, and preview before deliverables." });
      if (clearPromptOnSuccess) setPrompt("");
      return "completed";
    } catch (error) {
      if (!isCurrent()) return "stale";
      if (signal?.aborted || (!timedOut && error instanceof Error && error.name === "AbortError")) {
        appendChatMessage("assistant", "I stopped the live request before it finished.", "status");
        setStatusMessage("Cancelled the live request.");
        return "cancelled";
      }
      const connectionFailure = isConnectivityFailureMessage(error instanceof Error ? error.message : "");
      if ((timedOut || connectionFailure) && token && allowQueueFallback) {
        const reason = timedOut ? "timeout" : "connection";
        try {
          const queued = await queueRun();
          if (!canPublish()) return isCurrent() ? "cancelled" : "stale";
          publishQueued(queued.job, false, reason);
          return "queued";
        } catch (queueError) {
          publishQueueFailure(queueError, false, reason);
          return !isCurrent() ? "stale" : signal?.aborted ? "cancelled" : "blocked";
        }
      }
      appendChatMessage("assistant", mode === "fix"
        ? `Fix pass could not complete: ${panelErrorMessage(error, "Could not complete the fix pass.")} Next action: review inputs, then retry Fix.`
        : mode === "improve"
          ? `Improve pass could not complete: ${panelErrorMessage(error, "Could not complete the improvement pass.")} Next action: review inputs, then retry Improve.`
          : `Generate could not complete: ${panelErrorMessage(error, "Could not update the design.")} Next action: check the status message, then press Generate again.`, "status");
      updateProjectStatus({ state: "blocked", area: "generate", title: mode === "run" ? "Generate needs attention" : `${mode} needs attention`,
        detail: panelErrorMessage(error, mode === "run" ? "Could not update the design." : "Could not complete the run."), nextAction: mode === "run" ? "Check the status message, then press Generate again." : "Review inputs, then retry." });
      return "blocked";
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId);
      signal?.removeEventListener("abort", handleAbort);
      if (isCurrent()) {
        setBusy(false);
        setActivePlanTool("run");
        if (directRunAbortRef.current === runOwner) directRunAbortRef.current = null;
      }
    }
  };
}
