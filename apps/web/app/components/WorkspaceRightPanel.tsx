import type { ReactNode } from "react";
import { PanelRightClose } from "lucide-react";

type WorkspaceRightPanelProps = {
  title: string;
  description: string;
  visible: boolean;
  wide?: boolean;
  commandBarVisible?: boolean;
  mobileNavigationVisible?: boolean;
  onMinimize: () => void;
  children: ReactNode;
};

export default function WorkspaceRightPanel({
  title,
  description,
  visible,
  wide = false,
  commandBarVisible = false,
  mobileNavigationVisible = false,
  onMinimize,
  children,
}: WorkspaceRightPanelProps) {
  return (
    <aside
      data-testid="workspace-right-panel"
      data-motion-state={visible ? "open" : "closed"}
      data-drawer-size={wide ? "wide" : "standard"}
      data-command-bar-visible={commandBarVisible}
      data-mobile-navigation-visible={mobileNavigationVisible}
      aria-hidden={!visible}
      className="civora-motion-right-panel civora-workspace-drawer fixed inset-x-0 top-auto z-[700] order-3 flex min-h-0 min-w-0 shrink-0 flex-col overflow-hidden rounded-t-xl border border-slate-200/80 bg-white shadow-[0_-28px_80px_-50px_rgba(15,23,42,0.62)] sm:inset-x-4 sm:rounded-xl lg:inset-x-auto lg:left-auto lg:right-0 lg:top-16 lg:h-auto lg:rounded-none lg:border-y-0 lg:border-r-0 lg:shadow-[-18px_0_60px_-54px_rgba(15,23,42,0.72)]"
    >
      <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-[var(--civora-border)] px-4">
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
            className="civora-control inline-flex h-9 w-9 items-center justify-center text-[var(--civora-text-muted)]"
            aria-label="Minimize"
            title="Minimize panel"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div
        className="civora-right-panel-sections flex-1 overflow-y-auto overscroll-contain p-3 pb-[calc(env(safe-area-inset-bottom)+1rem)]"
        data-sections-collapsed="false"
      >
        {children}
      </div>
    </aside>
  );
}
