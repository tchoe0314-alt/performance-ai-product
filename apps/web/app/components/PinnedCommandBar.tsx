"use client";

import { Loader2, MessageSquareText, SendHorizonal } from "lucide-react";

import type { PlanToolMode } from "../types";

type ThinkingState = {
  label: string;
  detail: string;
  progress: number;
};

type PinnedCommandBarProps = {
  prompt: string;
  imageName: string;
  onPromptChange: (value: string) => void;
  onPromptKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  commandInputRef?: React.RefObject<HTMLTextAreaElement | null>;
  onSendMessage: () => void;
  onOpenHistory: () => void;
  busy: boolean;
  hasVisibleActiveJob: boolean;
  activePlanTool: PlanToolMode;
  thinkingState: ThinkingState;
  statusText: string;
  commandContext?: {
    mode: string;
    interaction: string;
    layer: string;
    selectedCount: number;
    snap: string;
    view: string;
  };
};

export default function PinnedCommandBar({
  prompt,
  imageName,
  onPromptChange,
  onPromptKeyDown,
  commandInputRef,
  onSendMessage,
  onOpenHistory,
  busy,
  hasVisibleActiveJob,
  activePlanTool,
  thinkingState,
  statusText,
}: PinnedCommandBarProps) {
  const isWorking = busy || hasVisibleActiveJob;
  const canSend = Boolean(prompt.trim() || imageName) && !isWorking;
  const quietStatus = statusText.trim();
  const showQuietStatus =
    Boolean(quietStatus) &&
    !/^Civora:\s*(Duplicate blocked|Delete blocked)/i.test(quietStatus);

  return (
    <div
      data-testid="floating-command-bar"
      data-command-bar-id="pinned-civora-command-bar"
      className="civora-motion-command-bar fixed right-2 top-[4.75rem] z-[45] w-[min(30rem,calc(100vw-1rem))] rounded-xl border border-blue-200/70 bg-white/96 p-2 shadow-[0_24px_80px_-36px_rgba(15,23,42,0.58)] backdrop-blur-xl sm:right-4 sm:top-20"
    >
      {isWorking ? (
        <div className="mb-2 flex min-w-0 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-slate-900" />
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold text-slate-950">
              {thinkingState.label || "Civora is thinking..."}
            </p>
            <p className="truncate">{thinkingState.detail || statusText}</p>
          </div>
          <span className="shrink-0 rounded-full bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            {thinkingState.progress}%
          </span>
        </div>
      ) : null}
      {!isWorking && showQuietStatus ? (
        <p
          aria-live="polite"
          className="mb-2 truncate rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600"
        >
          {quietStatus}
        </p>
      ) : null}
      <div className="flex min-w-0 items-end gap-2">
        <button
          type="button"
          onClick={onOpenHistory}
          aria-label="Open Civora chat history"
          title="Open chat history"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-700 transition hover:border-blue-200 hover:bg-white hover:text-blue-700"
        >
          <MessageSquareText className="h-5 w-5" />
        </button>
        <textarea
          ref={commandInputRef}
          data-testid="civora-command-input"
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          onKeyDown={onPromptKeyDown}
          placeholder="Ask Civora..."
          rows={1}
          className="max-h-24 min-h-11 flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-medium leading-5 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-blue-300 focus:bg-white focus:ring-2 focus:ring-blue-100"
        />
        <button
          type="button"
          onClick={onSendMessage}
          disabled={!canSend}
          aria-label="Send message to Civora"
          title={isWorking ? "Civora is working" : "Send"}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-45"
        >
          {isWorking && activePlanTool === "run" ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <SendHorizonal className="h-5 w-5" />
          )}
        </button>
      </div>
    </div>
  );
}
