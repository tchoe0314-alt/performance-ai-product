import type { ComponentProps, RefObject } from "react";

import ChatPanel from "../components/ChatPanel";
import PinnedCommandBar from "../components/PinnedCommandBar";
import type { ChatMessage, PlanToolMode } from "../types";
import type { ProjectStatusSummary } from "../utils/workspaceShell";
import { formatProjectStatusText } from "../utils/workspaceShell";

type ChatPanelProps = ComponentProps<typeof ChatPanel>;
type PinnedCommandBarProps = ComponentProps<typeof PinnedCommandBar>;

type UseDashboardChatCommandPropsInput = {
  chatMessages: ChatMessage[];
  chatScrollRef: ChatPanelProps["chatScrollRef"];
  chatPromptInputRef: RefObject<HTMLTextAreaElement | null>;
  onSetMessageFeedback: ChatPanelProps["onSetMessageFeedback"];
  thinkingState: ChatPanelProps["thinkingState"];
  busy: boolean;
  activePlanTool: PlanToolMode;
  visibleActiveJobStatus: string;
  hasDirectRunInFlight: boolean;
  onCancelJob: () => void;
  onContinueJob: () => void;
  pendingClarificationQuestion: string | null;
  onContinuePendingClarification: () => void;
  prompt: string;
  imageName: string;
  onPromptChange: (value: string) => void;
  onPromptKeyDown: ChatPanelProps["onPromptKeyDown"];
  commandInputRef: RefObject<HTMLTextAreaElement | null>;
  onSendMessage: () => void;
  onUploadImage: ChatPanelProps["onUploadImage"];
  onExplainPlan: () => void;
  onRunFix: () => void;
  onRunImprove: () => void;
  onSaveProject: () => void;
  canExplain: boolean;
  statusMessage: string;
  hasVisibleActiveJob: boolean;
  approvalState: ChatPanelProps["approvalState"];
  approvalPhaseLabel: string | null;
  approvalError: string | null;
  onToggleChatCollapsed: () => void;
  summaryText: string;
  onOpenHistory: () => void;
  chatBlockingActiveJob: boolean;
  projectStatusSummary: ProjectStatusSummary;
  activePrimaryWorkflowKey: string;
  previewInteraction: string;
  activePlacementId: string | null;
  previewMode: "2d" | "3d";
  previewQuality: "standard" | "high";
};

export function useDashboardChatCommandProps({
  chatMessages,
  chatScrollRef,
  chatPromptInputRef,
  onSetMessageFeedback,
  thinkingState,
  busy,
  activePlanTool,
  visibleActiveJobStatus,
  hasDirectRunInFlight,
  onCancelJob,
  onContinueJob,
  pendingClarificationQuestion,
  onContinuePendingClarification,
  prompt,
  imageName,
  onPromptChange,
  onPromptKeyDown,
  commandInputRef,
  onSendMessage,
  onUploadImage,
  onExplainPlan,
  onRunFix,
  onRunImprove,
  onSaveProject,
  canExplain,
  statusMessage,
  hasVisibleActiveJob,
  approvalState,
  approvalPhaseLabel,
  approvalError,
  onToggleChatCollapsed,
  summaryText,
  onOpenHistory,
  chatBlockingActiveJob,
  projectStatusSummary,
  activePrimaryWorkflowKey,
  previewInteraction,
  activePlacementId,
  previewMode,
  previewQuality,
}: UseDashboardChatCommandPropsInput) {
  const sharedPromptProps = {
    prompt,
    imageName,
    onPromptChange,
    onPromptKeyDown,
    onSendMessage,
    busy,
    activePlanTool,
    thinkingState,
  };

  const chatPanelProps: ChatPanelProps = {
    chatMessages,
    chatScrollRef,
    onSetMessageFeedback,
    ...sharedPromptProps,
    promptInputRef: chatPromptInputRef,
    visibleActiveJobStatus,
    hasDirectRunInFlight,
    onCancelJob,
    onContinueJob,
    pendingClarification: pendingClarificationQuestion,
    onContinuePendingClarification,
    onUploadImage,
    onExplainPlan,
    onRunFix,
    onRunImprove,
    onSaveProject,
    canExplain,
    statusMessage,
    hasVisibleActiveJob,
    approvalState,
    approvalPhaseLabel,
    approvalError,
    collapsed: false,
    onToggleCollapsed: onToggleChatCollapsed,
    summaryText,
  };

  const pinnedCommandBarProps: PinnedCommandBarProps = {
    ...sharedPromptProps,
    commandInputRef,
    onOpenHistory,
    hasVisibleActiveJob: chatBlockingActiveJob,
    statusText: statusMessage || summaryText || formatProjectStatusText(projectStatusSummary),
    commandContext: {
      mode: activePrimaryWorkflowKey,
      interaction: previewInteraction,
      layer: activePlacementId ? "selected" : "C-DRAFT",
      selectedCount: activePlacementId ? 1 : 0,
      snap: "ready",
      view: `${previewMode.toUpperCase()} / ${previewQuality}`,
    },
  };

  return {
    chatPanelProps,
    pinnedCommandBarProps,
  };
}
