"use client";

import { Bell, CircleHelp, RotateCcw, Undo2 } from "lucide-react";

import { workflowSteps } from "../design-system";

type AppHeaderProps = {
  userEmail: string;
  onOpenProjects: () => void;
  onOpenSiteInputs: () => void;
  onOpenDocs: () => void;
  onOpenChat: () => void;
  onLogout: () => void;
};

export default function AppHeader({
  userEmail,
  onOpenProjects,
  onOpenSiteInputs,
  onOpenDocs,
  onOpenChat,
  onLogout,
}: AppHeaderProps) {
  return (
    <header className="civora-glass sticky top-0 z-50 w-full rounded-none border-x-0 border-t-0">
      <div className="flex h-16 w-full items-center justify-between gap-4 px-5">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--civora-border)] bg-[var(--civora-surface-solid)] text-lg font-bold text-[var(--civora-text)] shadow-[0_12px_30px_-24px_rgba(18,25,38,0.5)]">
            C
          </div>
          <div className="hidden sm:block">
            <p className="text-[15px] font-semibold tracking-tight text-[var(--civora-text)]">Civora</p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.26em] text-[var(--civora-text-soft)]">Civil AI</p>
          </div>
          <button
            type="button"
            onClick={onOpenProjects}
            className="civora-control hidden min-w-[172px] items-center justify-between gap-3 px-3 py-2 text-left text-sm font-medium md:flex"
          >
            <span className="truncate">Workspace</span>
            <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--civora-text-soft)]">Select</span>
          </button>
          <button
            type="button"
            onClick={onOpenSiteInputs}
            className="civora-control hidden px-3 py-2 text-sm font-semibold text-[var(--civora-text)] md:inline-flex"
          >
            Site
          </button>
        </div>

        <nav className="hidden flex-1 items-center justify-center gap-2 lg:flex">
          {workflowSteps.map((step, index) => {
            const state = index === 0 ? "complete" : index === 1 ? "active" : "idle";
            return (
              <div key={step} className="flex items-center gap-2">
                <span
                  data-state={state}
                  className="civora-step inline-flex h-6 w-6 items-center justify-center text-[11px] font-semibold"
                >
                  {state === "complete" ? "✓" : index + 1}
                </span>
                <span className={`text-xs font-semibold ${state === "active" ? "text-[var(--civora-text)]" : "text-[var(--civora-text-muted)]"}`}>
                  {step}
                </span>
              </div>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <button type="button" className="civora-control hidden h-9 w-9 items-center justify-center md:inline-flex" aria-label="Undo">
            <Undo2 className="h-4 w-4" />
          </button>
          <button type="button" className="civora-control hidden h-9 w-9 items-center justify-center md:inline-flex" aria-label="Redo">
            <RotateCcw className="h-4 w-4" />
          </button>
          <button type="button" className="civora-control hidden h-9 w-9 items-center justify-center md:inline-flex" aria-label="Notifications">
            <Bell className="h-4 w-4" />
          </button>
          <button type="button" onClick={onOpenDocs} className="civora-control hidden h-9 w-9 items-center justify-center md:inline-flex" aria-label="Help">
            <CircleHelp className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onOpenChat}
            className="civora-control hidden px-3 py-2 text-xs font-semibold text-[var(--civora-text-muted)] xl:inline-flex"
          >
            AI
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-[var(--civora-border)] bg-[var(--civora-surface-solid)] text-xs font-bold text-[var(--civora-text)] shadow-[0_12px_30px_-24px_rgba(18,25,38,0.5)]"
            title={`Sign out ${userEmail}`}
          >
            {userEmail.slice(0, 1).toUpperCase()}
          </button>
        </div>
      </div>
    </header>
  );
}
