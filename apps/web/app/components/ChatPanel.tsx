"use client";

import { ChevronDown, FileImage } from "lucide-react";

import type { ChatMessage, PlanToolMode } from "../types";
import { formatChatTimestamp } from "../utils/formatting";
import { TextArea } from "./ui";

type ThinkingState = {
  label: string;
  detail: string;
  progress: number;
};

type ChatPanelProps = {
  chatMessages: ChatMessage[];
  chatScrollRef: React.RefObject<HTMLDivElement | null>;
  onSetMessageFeedback: (messageId: string, feedback: ChatMessage["feedback"]) => void;
  thinkingState: ThinkingState;
  busy: boolean;
  activePlanTool: PlanToolMode;
  visibleActiveJobStatus: string;
  hasDirectRunInFlight: boolean;
  onCancelJob: () => void;
  onContinueJob: () => void;
  pendingClarification?: string | null;
  onContinuePendingClarification?: () => void;
  prompt: string;
  imageName: string;
  onPromptChange: (value: string) => void;
  onPromptKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSendMessage: () => void;
  onUploadImage: (file: File) => Promise<void>;
  onExplainPlan: () => void;
  onRunFix: () => void;
  onRunImprove: () => void;
  onSaveProject: () => void;
  canExplain: boolean;
  statusMessage: string;
  hasVisibleActiveJob: boolean;
  approvalState: "idle" | "approving" | "starting";
  approvalPhaseLabel: string | null;
  approvalError: string | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  summaryText: string;
};

export default function ChatPanel({
  chatMessages,
  chatScrollRef,
  onSetMessageFeedback,
  thinkingState,
  busy,
  activePlanTool,
  visibleActiveJobStatus,
  hasDirectRunInFlight,
  onCancelJob,
  onContinueJob,
  pendingClarification,
  onContinuePendingClarification,
  prompt,
  imageName,
  onPromptChange,
  onPromptKeyDown,
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
  collapsed,
  onToggleCollapsed,
  summaryText,
}: ChatPanelProps) {
  const normalizedStatus = String(visibleActiveJobStatus || "").toLowerCase();
  const isCancelling = normalizedStatus === "cancelling";
  const isAwaitingApproval = normalizedStatus === "awaiting_approval";
  const isApprovalBusy = approvalState !== "idle";
  const approvalLabel = approvalPhaseLabel ? `Starting ${approvalPhaseLabel}...` : "Starting next phase...";
  const showContinuePending = Boolean(pendingClarification && onContinuePendingClarification && !busy && !hasVisibleActiveJob);

  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-white shadow-[0_10px_40px_-28px_rgba(15,23,42,0.5)]">
      <button
        type="button"
        onClick={onToggleCollapsed}
        className="flex w-full min-w-0 items-center justify-between gap-4 border-b border-slate-200 px-4 py-3 text-left"
      >
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Command Center (AI)
          </p>
          <p className="mt-1 text-sm text-slate-700">{summaryText}</p>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-slate-500 transition ${collapsed ? "" : "rotate-180"}`}
        />
      </button>

      {!collapsed ? (
        <div
          ref={chatScrollRef}
          className="max-h-[min(320px,36svh)] space-y-4 overflow-y-auto p-3 sm:p-4"
        >
          {chatMessages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[92%] overflow-hidden rounded-xl px-3 py-3 sm:max-w-[85%] sm:px-4 ${
                  message.role === "user"
                    ? "bg-slate-950 text-white"
                    : message.role === "system"
                      ? "border border-amber-200 bg-amber-50 text-amber-900"
                      : "border border-slate-200 bg-white text-slate-900"
                }`}
              >
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">
                    {message.role === "user"
                      ? "You"
                      : message.role === "system"
                        ? "Action"
                        : "Civora AI"}
                  </span>
                  {message.role === "assistant" && message.phaseTag ? (
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                      {message.phaseTag}
                    </span>
                  ) : null}
                  <span className="text-[11px] opacity-60">
                    {formatChatTimestamp(message.createdAt)}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6">
                  {message.content}
                </p>
                {message.role === "assistant" ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                    <span className="text-slate-400">Was this helpful?</span>
                    <button
                      type="button"
                      onClick={() => onSetMessageFeedback(message.id, "up")}
                      className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                        message.feedback === "up"
                          ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                          : "border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      Helpful
                    </button>
                    <button
                      type="button"
                      onClick={() => onSetMessageFeedback(message.id, "down")}
                      className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                        message.feedback === "down"
                          ? "border-rose-500 bg-rose-50 text-rose-700"
                          : "border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      Not quite
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="border-t border-slate-200 p-3 sm:p-4">
        {(busy || hasVisibleActiveJob) && (
          <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-4 sm:px-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-slate-950">
                  {thinkingState.label}
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  {thinkingState.detail}
                </p>
              </div>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {thinkingState.progress}%
              </span>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-slate-950 transition-all duration-500"
                style={{ width: `${thinkingState.progress}%` }}
              />
            </div>
            {isAwaitingApproval ? (
              <div className="mt-4 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
                {approvalState === "starting"
                  ? approvalLabel
                  : "Phase ready for review. Approve to continue or send changes."}
              </div>
            ) : null}
            {(hasVisibleActiveJob || hasDirectRunInFlight) && (
              <div className="mt-4 space-y-2">
                {isAwaitingApproval && approvalError ? (
                  <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold leading-5 text-rose-700">
                    {approvalError}
                  </div>
                ) : null}
                <div className="flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={onCancelJob}
                    disabled={isCancelling}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isCancelling ? "Cancelling..." : "Cancel"}
                  </button>
                  {isAwaitingApproval && (
                    <button
                      type="button"
                      onClick={onContinueJob}
                      disabled={isApprovalBusy || isCancelling}
                      className="rounded-xl border border-slate-900 bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {approvalState === "approving"
                        ? "Approving..."
                        : approvalState === "starting"
                          ? approvalLabel
                          : "Approve & Continue"}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        <div className={`min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-3 sm:rounded-3xl ${collapsed ? "" : "mb-4"}`}>
          <TextArea
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            onKeyDown={onPromptKeyDown}
            placeholder="Message Civora AI with what you want to create or change..."
            className={`border-0 bg-transparent px-1 py-1 shadow-none focus:ring-0 ${
              collapsed ? "h-[72px] min-h-[72px] max-h-[96px]" : "h-[150px] min-h-[150px] max-h-[240px]"
            }`}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                <FileImage className="mr-2 h-4 w-4" />
                Upload
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      await onUploadImage(file);
                    }
                  }}
                />
              </label>
              <button
                type="button"
                onClick={onExplainPlan}
                disabled={!canExplain}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Explain
              </button>
              <button
                type="button"
                onClick={onRunFix}
                disabled={busy || hasVisibleActiveJob}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Fix
              </button>
              <button
                type="button"
                onClick={onRunImprove}
                disabled={busy || hasVisibleActiveJob}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Improve
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onSaveProject}
                disabled={busy || hasVisibleActiveJob}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Save
              </button>
              {showContinuePending ? (
                <button
                  type="button"
                  onClick={onContinuePendingClarification}
                  className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 transition hover:bg-amber-100"
                >
                  Continue
                </button>
              ) : null}
              <button
                type="button"
                onClick={onSendMessage}
                disabled={busy || hasVisibleActiveJob || (!prompt.trim() && !imageName)}
                className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy && activePlanTool === "run"
                  ? "Working..."
                  : hasVisibleActiveJob
                    ? "Working..."
                    : "Send"}
              </button>
            </div>
          </div>
        </div>

        {!busy && !hasVisibleActiveJob && !collapsed && statusMessage && (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            {statusMessage}
          </div>
        )}
      </div>
    </div>
  );
}
