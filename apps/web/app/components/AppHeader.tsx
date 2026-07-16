"use client";

import { CircleHelp, FolderOpen, MessageSquare, PanelLeftClose, PanelLeftOpen } from "lucide-react";

type AppHeaderProps = {
  userEmail: string;
  onOpenDashboard: () => void;
  onOpenWorkspace: () => void;
  onOpenProjects: () => void;
  onOpenDocs: () => void;
  onOpenChat: () => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onLogout: () => void;
};

export default function AppHeader({
  userEmail,
  onOpenDashboard,
  onOpenWorkspace,
  onOpenProjects,
  onOpenDocs,
  onOpenChat,
  sidebarOpen,
  onToggleSidebar,
  onLogout,
}: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200/70 bg-white/86 backdrop-blur-2xl">
      <div className="flex h-16 w-full items-center justify-between gap-4 px-4 sm:px-5">
        <div className="flex min-w-0 items-center gap-4">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200/80 bg-white/80 text-slate-700 transition hover:bg-slate-50"
            aria-label={sidebarOpen ? "Hide left sidebar" : "Show left sidebar"}
            title={sidebarOpen ? "Hide left sidebar" : "Show left sidebar"}
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </button>
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-950 text-sm font-semibold text-white">
            C
          </div>
          <div className="hidden sm:block">
            <p className="text-[15px] font-semibold text-slate-950">Civora</p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Planning support</p>
          </div>
          <button
            type="button"
            onClick={onOpenDashboard}
            className="hidden rounded-lg border border-transparent bg-transparent px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100/70 hover:text-slate-950 md:inline-flex"
          >
            Recent changes
          </button>
          <button
            type="button"
            onClick={onOpenChat}
            aria-label="Open chat from header"
            className="hidden items-center gap-2 rounded-lg border border-slate-900 bg-slate-950 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 md:inline-flex"
          >
            <MessageSquare className="h-4 w-4" />
            Chat
          </button>
          <button
            type="button"
            onClick={onOpenProjects}
            aria-label="Open projects from header"
            className="hidden items-center gap-2 rounded-lg border border-transparent bg-transparent px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100/70 hover:text-slate-950 md:inline-flex"
          >
            <FolderOpen className="h-4 w-4" />
            Projects
          </button>
          <button
            type="button"
            onClick={onOpenWorkspace}
            aria-label="Open workspace controls"
            className="hidden items-center gap-2 rounded-lg border border-transparent bg-transparent px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100/70 hover:text-slate-950 md:inline-flex"
          >
            <PanelLeftOpen className="h-4 w-4" />
            Setup
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenChat}
            aria-label="Open Civora chat history"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-900 bg-slate-950 text-white transition hover:bg-slate-800 md:hidden"
            title="Chat"
          >
            <MessageSquare className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onOpenProjects}
            aria-label="Open projects"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200/80 bg-white/80 text-slate-700 transition hover:bg-slate-50 md:hidden"
            title="Projects"
          >
            <FolderOpen className="h-4 w-4" />
          </button>
          <button type="button" onClick={onOpenDocs} className="hidden h-9 w-9 items-center justify-center rounded-lg border border-slate-200/80 bg-white/80 text-slate-700 transition hover:bg-slate-50 md:inline-flex" aria-label="Help">
            <CircleHelp className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-xs font-bold text-slate-900"
            title={`Sign out ${userEmail}`}
          >
            {userEmail.slice(0, 1).toUpperCase()}
          </button>
        </div>
      </div>
    </header>
  );
}
