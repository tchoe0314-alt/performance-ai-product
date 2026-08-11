import type { ReactNode } from "react";
import { Minus, X } from "lucide-react";

type WorkspaceRightPanelProps = {
  title: string;
  description: string;
  visible: boolean;
  wide?: boolean;
  commandBarVisible?: boolean;
  mobileNavigationVisible?: boolean;
  onMinimize: () => void;
  onClose?: () => void;
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
  onClose,
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
      className="civora-motion-right-panel civora-workspace-drawer fixed inset-x-0 top-auto z-[700] order-3 flex min-h-0 min-w-0 shrink-0 flex-col overflow-hidden rounded-t-[10px] border border-slate-200/90 bg-white shadow-[0_-24px_70px_-46px_rgba(15,23,42,0.48)] sm:inset-x-3 sm:rounded-[10px] lg:inset-x-auto lg:left-auto lg:right-0 lg:top-[52px] lg:h-auto lg:rounded-none lg:border-y-0 lg:border-r-0 lg:shadow-[-18px_0_52px_-44px_rgba(15,23,42,0.5)]"
    >
      <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200/80 px-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--civora-text)]">{title}</p>
          <p className="sr-only">
            {description}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={onMinimize}
            className="inline-flex h-8 w-8 items-center justify-center rounded-[6px] text-slate-500 transition hover:bg-slate-100 hover:text-slate-950"
            aria-label="Minimize"
            title="Minimize panel"
          >
            <Minus className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onClose ?? onMinimize}
            className="inline-flex h-8 w-8 items-center justify-center rounded-[6px] text-slate-500 transition hover:bg-slate-100 hover:text-slate-950"
            aria-label="Close panel"
            title="Close panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div
        className="civora-right-panel-sections flex-1 overflow-y-auto overscroll-contain px-3 py-3 pb-[calc(env(safe-area-inset-bottom)+1rem)]"
        data-sections-collapsed="false"
      >
        {children}
      </div>
    </aside>
  );
}
