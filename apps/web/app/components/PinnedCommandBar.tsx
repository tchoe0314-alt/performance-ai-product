"use client";

import type { CSSProperties } from "react";
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
  leftRailVisible?: boolean;
  rightPanelSize?: "none" | "standard" | "wide";
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
  leftRailVisible = true,
  rightPanelSize = "none",
}: PinnedCommandBarProps) {
  const isWorking = busy || hasVisibleActiveJob;
  const canSend = Boolean(prompt.trim() || imageName) && !isWorking;
  const dockStyle = {
    "--civora-command-left-inset": leftRailVisible ? "var(--civora-shell-rail-width)" : "0px",
    "--civora-command-right-inset": rightPanelSize === "none" ? "0px" : "var(--civora-shell-drawer-width)",
  } as CSSProperties;

  return (
    <div
      data-testid="floating-command-bar"
      data-command-bar-id="pinned-civora-command-bar"
      className="civora-motion-command-bar civora-command-dock fixed bottom-[calc(env(safe-area-inset-bottom)+0.75rem)] left-1/2 z-[720] w-[min(44rem,calc(100vw-1rem))] -translate-x-1/2 rounded-[10px] border border-slate-200/90 bg-white/97 p-1.5 shadow-[0_18px_54px_-30px_rgba(15,23,42,0.46)] backdrop-blur-xl"
      style={dockStyle}
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
      {!isWorking && statusText ? <span className="sr-only" aria-live="polite">{statusText}</span> : null}
      <div className="flex min-w-0 items-end gap-2">
        <button
          type="button"
          onClick={onOpenHistory}
          aria-label="Open Civora chat history"
          title="Open chat history"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[7px] text-slate-500 transition hover:bg-slate-100 hover:text-slate-950"
        >
          <MessageSquareText className="h-5 w-5" />
        </button>
        <textarea
          ref={commandInputRef}
          data-testid="civora-command-input"
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          onKeyDown={onPromptKeyDown}
          placeholder="Describe a change or enter a command..."
          rows={1}
          className="max-h-24 min-h-10 flex-1 resize-none border-0 bg-transparent px-2 py-2.5 text-sm font-medium leading-5 text-slate-950 outline-none placeholder:text-slate-400"
        />
        <button
          type="button"
          onClick={onSendMessage}
          disabled={!canSend}
          aria-label="Run Civora command"
          title={isWorking ? "Civora is working" : "Run command"}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[7px] bg-blue-600 text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-45"
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
