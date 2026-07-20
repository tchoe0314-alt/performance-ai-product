import type { ReactNode } from "react";

type WorkspaceRightPanelProps = {
  title: string;
  description: string;
  visible: boolean;
  wide?: boolean;
  commandBarVisible?: boolean;
  onMinimize: () => void;
  children: ReactNode;
};

export default function WorkspaceRightPanel({
  title,
  description,
  visible,
  wide = false,
  commandBarVisible = false,
  onMinimize,
  children,
}: WorkspaceRightPanelProps) {
  return (
    <aside
      data-testid="workspace-right-panel"
      data-motion-state={visible ? "open" : "closed"}
      aria-hidden={!visible}
      className={`civora-motion-right-panel fixed inset-x-0 ${
        commandBarVisible
          ? "bottom-[calc(env(safe-area-inset-bottom)+4.75rem)] max-h-[calc(82svh-4.75rem)] sm:bottom-[calc(env(safe-area-inset-bottom)+5.25rem)] sm:max-h-[calc(78svh-5.25rem)] lg:bottom-0"
          : "bottom-[calc(env(safe-area-inset-bottom)+0.75rem)] max-h-[calc(92svh-0.75rem)] sm:bottom-[calc(env(safe-area-inset-bottom)+1rem)] sm:max-h-[calc(90svh-1rem)] lg:bottom-0"
      } top-auto z-[90] order-3 flex min-h-0 min-w-0 shrink-0 flex-col overflow-hidden rounded-t-xl border border-slate-200/80 bg-white/94 shadow-[0_-28px_80px_-50px_rgba(15,23,42,0.62)] backdrop-blur-2xl sm:inset-x-4 sm:rounded-xl lg:inset-x-auto lg:left-auto lg:right-0 lg:top-16 lg:h-auto lg:max-h-none lg:rounded-none lg:border-y-0 lg:border-r-0 lg:shadow-[-18px_0_60px_-54px_rgba(15,23,42,0.72)] ${
        wide ? "lg:w-[680px] xl:w-[760px]" : "lg:w-[360px] xl:w-[390px]"
      }`}
    >
      <div className="flex items-center justify-between gap-3 border-b border-[var(--civora-border)] px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--civora-text)]">{title}</p>
          <p className="sr-only">
            {description}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onMinimize}
            className="civora-control px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--civora-text-muted)]"
          >
            Minimize
          </button>
        </div>
      </div>
      <div
        className="civora-right-panel-sections flex-1 overflow-y-auto overscroll-contain p-3 pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:p-4"
        data-sections-collapsed="false"
      >
        {children}
      </div>
    </aside>
  );
}
