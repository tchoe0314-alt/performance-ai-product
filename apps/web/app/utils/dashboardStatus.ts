import { apiErrorMessage, classifyApiError } from "../../lib/api";

import type { JobSummary, PlanToolMode } from "../types";
import { toReadableLabel } from "./formatting";

export function formatTimestamp(value?: number): string {
  if (!value) return "Unknown time";
  try {
    return new Date(value * 1000).toLocaleString();
  } catch {
    return "Unknown time";
  }
}

export function panelErrorMessage(error: unknown, fallback: string): string {
  const kind = classifyApiError(error);
  if (kind === "auth_expired") return "Session expired. Sign in again.";
  if (kind === "backend_unreachable") return "Backend connection needs attention. Check the backend connection, then retry.";
  if (kind === "api_blocked") return "Backend access needs attention. Check account or app/backend access settings, then retry.";
  if (kind === "rate_limited") return "Rate limited. Wait about a minute, then retry.";
  if (kind === "upload_too_large") return "Upload too large. Choose a smaller file or compress it, then retry.";
  if (kind === "unsupported_file") return "Unsupported file. Use an accepted file type for this upload.";
  return apiErrorMessage(error, fallback);
}

export function uploadStatusMessage(kind: "image" | "pdf" | "survey", error: unknown): string {
  const label = kind === "image" ? "Image upload" : kind === "pdf" ? "PDF upload" : "Survey/topo upload";
  return `${label} failed: ${panelErrorMessage(error, `${label} failed.`)}`;
}

export function chatFailureMessage(error: unknown): string {
  const kind = classifyApiError(error);
  if (kind === "auth_expired") {
    return "I could not reach your Civora session. Sign in again, then resend your message.";
  }
  if (kind === "backend_unreachable" || kind === "api_blocked") {
    return "I could not reach Civora services just now. Check the connection, then retry your message.";
  }
  if (kind === "rate_limited") {
    return "The backend is rate limiting requests. Wait about a minute, then retry your message.";
  }
  return `I could not finish that request. ${apiErrorMessage(error, "Retry from chat or check the backend status.")}`;
}

export function jobDetailMessage(job: JobSummary): string {
  const status = String(job.status || "").toLowerCase();
  if (job.stage_detail) return job.stage_detail;
  if (job.error) return `Failed: ${job.error}`;
  if (job.stage) return job.stage;
  if (status === "queued") {
    return "Queued. Waiting for a backend worker; refresh jobs if this does not move soon.";
  }
  if (status === "running") {
    return "Running. Civora has not recorded the next stage detail yet.";
  }
  if (status === "awaiting_approval") {
    return "Waiting at a review hold. Continue after you finish the review step.";
  }
  if (status === "failed") {
    return "Failed before detailed stage notes were recorded. Retry or open the backend logs.";
  }
  if (status === "cancelled") {
    return "Cancelled before completion.";
  }
  if (status === "completed") {
    return "Completed. No additional detail was recorded.";
  }
  return "No job detail has been recorded yet. Refresh jobs or retry if the backend stays quiet.";
}

export function isLikelyStaleJob(job: JobSummary | null, nowMs: number): boolean {
  if (!job?.updated_at) return false;
  const status = String(job.status || "").toLowerCase();
  if (!["queued", "running", "cancelling"].includes(status)) {
    return false;
  }
  const updatedAtMs = Number(job.updated_at) * 1000;
  if (!Number.isFinite(updatedAtMs) || updatedAtMs <= 0) {
    return false;
  }
  const staleThresholdMs = status === "queued" ? 90_000 : 60_000;
  return nowMs - updatedAtMs > staleThresholdMs;
}

type ArtifactJobResult = {
  artifact?: {
    kind?: string;
    filename?: string;
    download_path?: string;
    review_only?: boolean;
    construction_release_allowed?: boolean;
  };
};

export function isArtifactExportJob(job: JobSummary): boolean {
  return String(job.job_type || "").startsWith("export_");
}

export function artifactFromJob(job: JobSummary): ArtifactJobResult["artifact"] | null {
  const result = (job.result ?? {}) as ArtifactJobResult;
  const artifact = result.artifact;
  return artifact && artifact.download_path ? artifact : null;
}

export function buildThinkingState({
  busy,
  activePlanTool,
  activeJobStatus,
  activeJobStage,
  activeJobDetail,
  activeJobProgress,
  activeJobUpdatedAt,
  activeJobQueuePosition,
  activeJobQueuedCount,
  activeJobRunningCount,
  staleJob,
  statusMessage,
}: {
  busy: boolean;
  activePlanTool: PlanToolMode;
  activeJobStatus?: string;
  activeJobStage?: string;
  activeJobDetail?: string;
  activeJobProgress?: number;
  activeJobUpdatedAt?: number;
  activeJobQueuePosition?: number | null;
  activeJobQueuedCount?: number;
  activeJobRunningCount?: number;
  staleJob?: boolean;
  statusMessage: string;
}) {
  const normalizedJobStatus = String(activeJobStatus || "").trim().toLowerCase();
  const normalizedStatus = statusMessage.toLowerCase();
  const stageLabel = String(activeJobStage || "").trim();
  const stageDetail = String(activeJobDetail || "").trim();
  const numericProgress =
    typeof activeJobProgress === "number" && Number.isFinite(activeJobProgress)
      ? Math.max(0, Math.min(100, Math.round(activeJobProgress)))
      : null;
  const lastUpdateText =
    activeJobUpdatedAt && Number.isFinite(activeJobUpdatedAt)
      ? `Last backend update: ${formatTimestamp(activeJobUpdatedAt)}.`
      : "";
  const queuePosition =
    typeof activeJobQueuePosition === "number" && Number.isFinite(activeJobQueuePosition)
      ? Math.max(1, Math.round(activeJobQueuePosition))
      : null;
  const queuedCount =
    typeof activeJobQueuedCount === "number" && Number.isFinite(activeJobQueuedCount)
      ? Math.max(0, Math.round(activeJobQueuedCount))
      : 0;
  const runningCount =
    typeof activeJobRunningCount === "number" && Number.isFinite(activeJobRunningCount)
      ? Math.max(0, Math.round(activeJobRunningCount))
      : 0;
  const queueDetail = queuePosition
    ? `Civora queued the run. Queue position: ${queuePosition}${queuedCount > 0 ? ` of ${queuedCount}` : ""}. ${runningCount > 0 ? `${runningCount} worker${runningCount === 1 ? "" : "s"} active.` : ""}`.trim()
    : "Civora queued the run and is waiting for a worker to pick it up.";

  if (normalizedJobStatus && staleJob) {
    return {
      label: normalizedJobStatus === "queued" ? "Queue Delayed" : "Check Run Status",
      detail:
        stageDetail ||
        `Civora has not received a fresh backend update for this ${normalizedJobStatus} job recently. ${lastUpdateText}`.trim(),
      progress:
        numericProgress ??
        (normalizedJobStatus === "queued" ? 18 : normalizedJobStatus === "cancelling" ? 68 : 72),
    };
  }

  if (normalizedJobStatus === "awaiting_approval") {
    const checkpointLabel = stageLabel && stageLabel.toLowerCase() !== "awaiting approval"
      ? toReadableLabel(stageLabel)
      : "current phase";
    return {
      label: "Review step",
      detail:
        stageDetail ||
        `Review ${checkpointLabel}, then continue from Generate or request a change in Chat.`,
      progress: numericProgress ?? 60,
    };
  }

  if (normalizedJobStatus && stageLabel) {
    return {
      label: stageLabel,
      detail:
        stageDetail ||
        (normalizedJobStatus === "queued"
          ? queueDetail
          : "Civora is processing the design in the background now."),
      progress: numericProgress ?? (normalizedJobStatus === "queued" ? 12 : 48),
    };
  }

  if (normalizedJobStatus === "queued") {
    return {
      label: "Queued",
      detail: queueDetail,
      progress: 18,
    };
  }
  if (normalizedJobStatus === "running") {
    return {
      label: "Running",
      detail: "Civora is processing the design in the background now.",
      progress: 68,
    };
  }
  if (normalizedJobStatus === "cancelling") {
    return {
      label: "Cancelling",
      detail:
        stageDetail ||
        "Civora is stopping the background run and cleaning up the active job.",
      progress: numericProgress ?? 68,
    };
  }
  if (busy && activePlanTool === "fix") {
    return {
      label: "Fixing",
      detail: "Applying a focused fix pass to the active design.",
      progress: 62,
    };
  }
  if (busy && activePlanTool === "improve") {
    return {
      label: "Improving",
      detail: "Improving the current design while preserving the main intent.",
      progress: 62,
    };
  }
  if (busy && normalizedStatus.includes("reviewing your request")) {
    return {
      label: "Reading Request",
      detail: "Reviewing your prompt and preparing the run.",
      progress: 22,
    };
  }
  if (busy && normalizedStatus.includes("starting the engineering run")) {
    return {
      label: "Engineering Run",
      detail: "Starting the core design pipeline and waiting for the first engineering result.",
      progress: 34,
    };
  }
  return {
    label: "Thinking",
    detail:
      statusMessage ||
      "Civora is building the design, checking engineering constraints, and preparing the next result.",
    progress: 42,
  };
}
