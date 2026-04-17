"use client";

import React from "react";
import { FileImage } from "lucide-react";

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
  autoAdvancePhases: boolean;
  onToggleAutoAdvance: () => void;
  revisePhaseTarget: "layout" | "grading" | "drainage_storm" | "utilities" | "coordination_validation";
  onRevisePhaseTargetChange: (value: ChatPanelProps["revisePhaseTarget"]) => void;
  onCancelJob: () => void;
  onReviseJob: () => void;
  onContinueJob: () => void;
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
  autoAdvancePhases,
  onToggleAutoAdvance,
  revisePhaseTarget,
  onRevisePhaseTargetChange,
  onCancelJob,
  onReviseJob,
  onContinueJob,
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
}: ChatPanelProps) {
  const normalizedStatus = String(visibleActiveJobStatus || "").toLowerCase();
  const isCancelling = normalizedStatus === "cancelling";
  const isAwaitingApproval = normalizedStatus === "awaiting_approval";

  return (
    <div className="rounded-[28px] border border-slate-200 bg-white">
      <div
        ref={chatScrollRef}
        className="max-h-[420px] space-y-4 overflow-y-auto p-4 md:p-6"
      >
        {chatMessages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-[28px] px-4 py-3 ${
                message.role === "user"
                  ? "bg-slate-950 text-white"
                  : message.role === "system"
                    ? "border border-amber-200 bg-amber-50 text-amber-900"
                    : "border border-slate-200 bg-white text-slate-900"
              }`}
            >
              <div className="flex items-center gap-2">
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
                <div className="mt-3 flex items-center gap-2 text-xs">
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

      <div className="border-t border-slate-200 p-4 md:p-6">
        {(busy || hasVisibleActiveJob) && (
          <div className="mb-4 rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
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
            {hasVisibleActiveJob && (
              <div className="mt-3 flex items-center justify-between text-xs text-slate-600">
                <span className="font-semibold uppercase tracking-[0.12em] text-slate-500">
                  Auto-advance phases
                </span>
                <button
                  type="button"
                  onClick={onToggleAutoAdvance}
                  className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] transition ${
                    autoAdvancePhases
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {autoAdvancePhases ? "On" : "Off"}
                </button>
              </div>
            )}
            {(hasVisibleActiveJob || hasDirectRunInFlight) && (
              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  onClick={onCancelJob}
                  disabled={isCancelling}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isCancelling ? "Cancelling..." : "Cancel"}
                </button>
                {isAwaitingApproval && (
                  <>
                    <div className="ml-2 flex items-center gap-2">
                      <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                        Revise phase
                      </label>
                      <select
                        value={revisePhaseTarget}
                        onChange={(event) =>
                          onRevisePhaseTargetChange(
                            event.target.value as ChatPanelProps["revisePhaseTarget"],
                          )
                        }
                        className="rounded-xl border border-slate-200 bg-white px-2 py-2 text-xs font-semibold text-slate-700"
                      >
                        <option value="layout">Layout</option>
                        <option value="grading">Grading</option>
                        <option value="drainage_storm">Drainage/Storm</option>
                        <option value="utilities">Utilities</option>
                        <option value="coordination_validation">Coordination</option>
                      </select>
                    </div>
                    <button
                      type="button"
                      onClick={onReviseJob}
                      className="ml-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                    >
                      Save Changes &amp; Revise
                    </button>
                    <button
                      type="button"
                      onClick={onContinueJob}
                      className="ml-2 rounded-xl border border-slate-900 bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
                    >
                      Approve &amp; Continue
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        <div className="mb-4 rounded-3xl border border-slate-200 bg-slate-50 p-3">
          <TextArea
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            onKeyDown={onPromptKeyDown}
            placeholder="Message Civora AI with what you want to create or change..."
            className="h-[150px] min-h-[150px] max-h-[240px] border-0 bg-transparent px-1 py-1 shadow-none focus:ring-0"
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
              <button
                type="button"
                onClick={onSendMessage}
                disabled={busy && !prompt.trim() && !imageName}
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

        {!busy && !hasVisibleActiveJob && statusMessage && (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            {statusMessage}
          </div>
        )}
      </div>
    </div>
  );
}
