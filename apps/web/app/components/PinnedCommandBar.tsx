"use client";

import type { CSSProperties } from "react";
import { useEffect, useRef } from "react";
import { Bot, ChevronRight, Loader2, MessageSquareText, SendHorizonal, Sparkles } from "lucide-react";

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
  commandContext,
  leftRailVisible = true,
  rightPanelSize = "none",
}: PinnedCommandBarProps) {
  const dockRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const dock = dockRef.current;
    if (!dock) return;
    const style = document.documentElement.style;
    const previous = style.getPropertyValue("--civora-command-dock-height");
    const measure = () => style.setProperty("--civora-command-dock-height", `${dock.getBoundingClientRect().height}px`);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(dock);
    return () => {
      observer.disconnect();
      if (previous) style.setProperty("--civora-command-dock-height", previous);
      else style.removeProperty("--civora-command-dock-height");
    };
  }, []);
  const isWorking = busy || hasVisibleActiveJob;
  const canSend = Boolean(prompt.trim() || imageName) && !isWorking;
  const dockStyle = {
    "--civora-command-left-inset": leftRailVisible ? "var(--civora-shell-rail-width)" : "0px",
    "--civora-command-right-inset": rightPanelSize === "none" ? "0px" : "var(--civora-shell-drawer-width)",
  } as CSSProperties;

  return (
    <div
      ref={dockRef}
      data-testid="floating-command-bar"
      data-command-bar-id="pinned-civora-command-bar"
      className="civora-motion-command-bar civora-command-dock fixed bottom-[calc(env(safe-area-inset-bottom)+1rem)] left-1/2 z-[720] w-[min(48rem,calc(100vw-1rem))] -translate-x-1/2 overflow-hidden rounded-[16px] border border-slate-300/80 bg-white/95 shadow-[0_24px_70px_-28px_rgba(15,23,42,0.52)] backdrop-blur-2xl"
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
      <div className="flex items-center justify-between gap-3 border-b border-slate-200/80 bg-slate-50/80 px-3.5 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-950 text-white shadow-sm">
            <Sparkles className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-900">Civora Copilot</p>
            <p className="truncate text-[10px] font-medium text-slate-500">Edit the plan with plain language</p>
          </div>
        </div>
        {commandContext ? (
          <div className="hidden min-w-0 items-center gap-1.5 md:flex" aria-label="Current design context">
            <span className="civora-command-context-chip">{commandContext.view}</span>
            <span className="civora-command-context-chip">{commandContext.layer}</span>
            {commandContext.selectedCount > 0 ? (
              <span className="civora-command-context-chip civora-command-context-chip-active">
                {commandContext.selectedCount} selected
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className="flex min-w-0 items-center gap-2 px-2 py-2">
        <button
          type="button"
          onClick={onOpenHistory}
          aria-label="Open Civora chat history"
          title="Open chat history"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] text-slate-500 transition hover:bg-slate-100 hover:text-slate-950"
        >
          <MessageSquareText className="h-5 w-5" />
        </button>
        <textarea
          ref={commandInputRef}
          data-testid="civora-command-input"
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          onKeyDown={onPromptKeyDown}
          placeholder="Ask Civora to change the site plan…"
          rows={1}
          className="max-h-24 min-h-[60px] min-w-0 flex-1 resize-none border-0 bg-transparent px-2 py-2.5 text-[15px] font-medium leading-5 text-slate-950 outline-none placeholder:text-slate-400 sm:min-h-10"
        />
        <button
          type="button"
          onClick={onSendMessage}
          disabled={!canSend}
          aria-label="Run Civora command"
          title={isWorking ? "Civora is working" : "Run command"}
          className="flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-[10px] bg-slate-950 px-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {isWorking && activePlanTool === "run" ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <><span className="hidden sm:inline">Run</span><SendHorizonal className="h-4 w-4" /></>
          )}
        </button>
      </div>
      {!isWorking && !prompt.trim() ? (
        <div className="flex items-center gap-1.5 overflow-x-auto px-3 pb-2.5" aria-label="Example Civora commands">
          <Bot className="mr-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
          {["Add a 50 ft cul-de-sac", "Fit 12 more stalls", "Check the entry geometry"].map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onPromptChange(suggestion)}
              className="group flex h-7 shrink-0 items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 text-[11px] font-semibold text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
            >
              {suggestion}
              <ChevronRight className="h-3 w-3 opacity-40 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
