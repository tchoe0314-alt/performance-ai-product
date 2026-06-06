"use client";

import { Bell, CircleHelp, MessageSquare, PanelLeftClose, PanelLeftOpen, RotateCcw, Search, Undo2 } from "lucide-react";

type AppHeaderProps = {
  userEmail: string;
  onOpenDashboard: () => void;
  onOpenDocs: () => void;
  onOpenChat: () => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onLogout: () => void;
};

export default function AppHeader({
  userEmail,
  onOpenDashboard,
  onOpenDocs,
  onOpenChat,
  sidebarOpen,
  onToggleSidebar,
  onLogout,
}: AppHeaderProps) {
  const inactiveToolbarButtonClass =
    "hidden h-9 w-9 cursor-not-allowed items-center justify-center rounded-lg border border-slate-200 bg-slate-100 text-slate-400 opacity-70 md:inline-flex";

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/95 shadow-[0_14px_40px_-36px_rgba(15,23,42,0.5)] backdrop-blur-xl">
      <div className="flex h-16 w-full items-center justify-between gap-4 px-5">
        <div className="flex min-w-0 items-center gap-4">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 transition hover:bg-slate-50"
            aria-label={sidebarOpen ? "Hide left sidebar" : "Show left sidebar"}
            title={sidebarOpen ? "Hide left sidebar" : "Show left sidebar"}
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </button>
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-900 bg-slate-950 text-lg font-bold text-white shadow-[0_12px_30px_-24px_rgba(18,25,38,0.5)]">
            F
          </div>
          <div className="hidden sm:block">
            <p className="text-[15px] font-semibold tracking-[0.32em] text-slate-950">CIVORA</p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Engineering OS</p>
          </div>
          <button
            type="button"
            onClick={onOpenDashboard}
            className="hidden rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 md:inline-flex"
          >
            Dashboard
          </button>
          <button
            type="button"
            onClick={onOpenChat}
            className="hidden items-center gap-2 rounded-lg border border-slate-900 bg-slate-950 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 md:inline-flex"
          >
            <MessageSquare className="h-4 w-4" />
            Chat
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button type="button" className={inactiveToolbarButtonClass} aria-label="Search unavailable" title="Search is not available in this review workspace yet." disabled>
            <Search className="h-4 w-4" />
          </button>
          <button type="button" className={inactiveToolbarButtonClass} aria-label="Undo unavailable" title="Undo is available from individual canvas edit controls only." disabled>
            <Undo2 className="h-4 w-4" />
          </button>
          <button type="button" className={inactiveToolbarButtonClass} aria-label="Redo unavailable" title="Redo is not available for this review workspace yet." disabled>
            <RotateCcw className="h-4 w-4" />
          </button>
          <button type="button" className={inactiveToolbarButtonClass} aria-label="Notifications unavailable" title="Notifications are not connected in this workspace." disabled>
            <Bell className="h-4 w-4" />
          </button>
          <button type="button" onClick={onOpenDocs} className="hidden h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 transition hover:bg-slate-50 md:inline-flex" aria-label="Help">
            <CircleHelp className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-xs font-bold text-slate-900 shadow-[0_12px_30px_-24px_rgba(18,25,38,0.5)]"
            title={`Sign out ${userEmail}`}
          >
            {userEmail.slice(0, 1).toUpperCase()}
          </button>
        </div>
      </div>
    </header>
  );
}
