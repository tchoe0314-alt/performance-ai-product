import type { MutableRefObject } from "react";

import type { ChatMessage, Issue, ManualFailure, PlanExplanation } from "../types";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

export function runDashboardQueuePreviewRefresh({
  previewRefreshIntentRef,
  reason,
  token,
}: {
  previewRefreshIntentRef: MutableRefObject<{ reason: string; track?: boolean } | null>;
  reason: string;
  token: string | null;
}) {
  if (!token) return;
  const lowerReason = reason.toLowerCase();
  if (
    lowerReason.includes("quality") ||
    lowerReason.includes("label density") ||
    lowerReason.includes("entering edit mode")
  ) {
    return;
  }
  previewRefreshIntentRef.current = { reason, track: true };
}

export async function runDashboardPreviewPlan({
  artifactPayload,
  requestPreview,
  setBusy,
  setStatusMessage,
  token,
}: {
  artifactPayload: Record<string, unknown>;
  requestPreview: (payload: Record<string, unknown>, options?: { track?: boolean }) => Promise<unknown>;
  setBusy: StateSetter<boolean>;
  setStatusMessage: StateSetter<string>;
  token: string | null;
}) {
  if (!token) return;
  setStatusMessage("Refreshing preview...");
  setBusy(true);
  try {
    await requestPreview(artifactPayload, { track: true });
  } catch (error) {
    setStatusMessage(error instanceof Error ? error.message : "Preview generation failed.");
  } finally {
    setBusy(false);
  }
}

export function runDashboardExplainPlan({
  appendChatMessage,
  currentExplanation,
  currentManualFailures,
  currentTruthAudit,
  issues,
  selectedRunMessage,
  setStatusMessage,
}: {
  appendChatMessage: AppendChatMessage;
  currentExplanation: PlanExplanation | null | undefined;
  currentManualFailures: ManualFailure[];
  currentTruthAudit: { success?: boolean } | null | undefined;
  issues: Issue[];
  selectedRunMessage: string;
  setStatusMessage: StateSetter<string>;
}) {
  const explanationText =
    typeof currentExplanation?.summary === "string"
      ? currentExplanation.summary
      : typeof currentExplanation?.overview === "string"
        ? currentExplanation.overview
        : selectedRunMessage;
  const fallbackDetails = [
    currentManualFailures.length
      ? `Needs input: ${currentManualFailures
          .slice(0, 3)
          .map((failure) => failure.code || failure.message || "missing information issue")
          .join(", ")}.`
      : null,
    issues.length
      ? `Current warnings: ${issues
          .slice(0, 3)
          .map((issue) => issue.message)
          .join("; ")}.`
      : null,
    currentTruthAudit?.success === true
      ? "Truth checks are currently passing."
      : currentTruthAudit?.success === false
        ? "Truth checks still need review."
        : null,
  ]
    .filter(Boolean)
    .join(" ");

  if (!explanationText && !fallbackDetails) {
    setStatusMessage("Run Civora AI first so there is a plan to explain.");
    return;
  }

  appendChatMessage(
    "assistant",
    [
      explanationText || "Here’s where the current design stands.",
      typeof currentExplanation?.why === "string" ? currentExplanation.why : null,
      fallbackDetails || null,
    ]
      .filter(Boolean)
      .join(" "),
    "explanation",
  );
  setStatusMessage("Added the latest plan explanation to the conversation.");
}
