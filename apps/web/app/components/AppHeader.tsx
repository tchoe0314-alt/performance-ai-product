"use client";

import {
  CircleHelp,
  MessageSquare,
  Redo2,
  Undo2,
} from "lucide-react";

type AppHeaderProps = {
  userEmail: string;
  projectName: string;
  saveStatus: string;
  canUndo: boolean;
  canRedo: boolean;
  onOpenProjects: () => void;
  onOpenDocs: () => void;
  onOpenChat: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onLogout: () => void;
};

export default function AppHeader({
  userEmail,
  projectName,
  saveStatus,
  canUndo,
  canRedo,
  onOpenProjects,
  onOpenDocs,
  onOpenChat,
  onUndo,
  onRedo,
  onLogout,
}: AppHeaderProps) {
  const normalizedSaveStatus = /saved|reloadable|restored/i.test(saveStatus)
    ? "Saved"
    : /saving/i.test(saveStatus)
      ? "Saving"
      : "Unsaved";

  return (
    <header className="civora-app-header sticky top-0 z-[1000] w-full border-b border-slate-200/80 bg-white/97 backdrop-blur-xl">
      <div className="flex h-[52px] w-full items-center justify-between gap-3 px-3 sm:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex shrink-0 items-center gap-2.5" aria-label="Civora">
            <div className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-blue-600 text-sm font-bold text-white">
              C
            </div>
            <span className="hidden text-[17px] font-semibold text-slate-950 sm:inline">Civora</span>
          </div>
          <span className="hidden h-6 w-px bg-slate-200 sm:block" aria-hidden="true" />
          <button
            type="button"
            onClick={onOpenProjects}
            aria-label="Projects"
            data-testid="header-projects-button"
            title="Open Projects"
            className="min-w-0 max-w-[min(42vw,30rem)] truncate rounded-[6px] px-2 py-1 text-left text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
          >
            {projectName || "Untitled Project"}
          </button>
          <span
            className="hidden shrink-0 items-center gap-1.5 text-xs font-medium text-slate-500 md:inline-flex"
            data-testid="header-save-status"
          >
            <span className={`h-2 w-2 rounded-full ${normalizedSaveStatus === "Saved" ? "bg-emerald-500" : normalizedSaveStatus === "Saving" ? "bg-blue-500" : "bg-amber-500"}`} />
            {normalizedSaveStatus}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={onUndo}
            disabled={!canUndo}
            className="civora-header-icon-button"
            aria-label="Undo last draft change"
            title="Undo"
          >
            <Undo2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onRedo}
            disabled={!canRedo}
            className="civora-header-icon-button"
            aria-label="Redo draft change"
            title="Redo"
          >
            <Redo2 className="h-4 w-4" />
          </button>
          <span className="mx-1 hidden h-6 w-px bg-slate-200 sm:block" aria-hidden="true" />
          <button
            type="button"
            onClick={onOpenChat}
            aria-label="Chat"
            data-testid="header-chat-button"
            className="civora-header-icon-button"
            title="Open Chat"
          >
            <MessageSquare className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onOpenDocs}
            data-testid="header-help-button"
            className="civora-header-icon-button"
            aria-label="Help"
            title="Help and product trust"
          >
            <CircleHelp className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="ml-1 inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-xs font-bold text-slate-800 transition hover:border-slate-300 hover:bg-white"
            title={`Sign out ${userEmail}`}
            aria-label={`Sign out ${userEmail}`}
          >
            {userEmail.slice(0, 1).toUpperCase()}
          </button>
        </div>
      </div>
    </header>
  );
}
