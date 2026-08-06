"use client";

import type { PrimaryWorkflowItem, PrimaryWorkflowKey } from "../utils/dashboardTypes";
import type { SidePanelKey } from "../utils/workspaceShell";

type WorkspaceLeftRailProps = {
  visible: boolean;
  activeWorkflowKey: PrimaryWorkflowKey;
  restoreTruthLabel: string;
  primaryWorkflowItems: PrimaryWorkflowItem[];
  onOpenPanel: (panel: SidePanelKey) => void;
};

const LEFT_RAIL_WORKFLOWS: PrimaryWorkflowKey[] = ["setup", "draw", "design", "deliver"];

export function WorkspaceLeftRail({
  visible,
  activeWorkflowKey,
  restoreTruthLabel,
  primaryWorkflowItems,
  onOpenPanel,
}: WorkspaceLeftRailProps) {
  return (
    <aside
      data-testid="left-sidebar"
      data-motion-state={visible ? "open" : "closed"}
      aria-hidden={!visible}
      className="civora-motion-sidebar civora-left-mode-rail fixed inset-x-3 top-20 z-[260] flex max-h-[calc(100svh-6rem)] min-w-0 shrink-0 flex-col overflow-y-auto rounded-xl border border-slate-200/80 bg-white/95 px-2 pb-28 pt-2 shadow-[0_24px_72px_-50px_rgba(15,23,42,0.62)] backdrop-blur-xl lg:bottom-0 lg:left-0 lg:right-auto lg:top-16 lg:max-h-none lg:rounded-none lg:border-y-0 lg:border-l-0 lg:px-2 lg:pb-4 lg:pt-3 lg:shadow-none"
    >
      <span data-testid="workspace-restore-status" className="sr-only">{restoreTruthLabel}</span>
      <div className="rounded-lg border border-transparent bg-transparent" data-testid="primary-workflow-sidebar">
        <div className="space-y-1">
          {primaryWorkflowItems
            .filter((item) => LEFT_RAIL_WORKFLOWS.includes(item.key))
            .map((item) => {
              const Icon = item.icon;
              const isActive = activeWorkflowKey === item.key || (item.key === "draw" && activeWorkflowKey === "objects");
              return (
                <button
                  key={item.key}
                  type="button"
                  aria-label={item.key === "draw" ? "Draw" : item.label}
                  onClick={() => onOpenPanel(item.panel)}
                  aria-current={isActive ? "page" : undefined}
                  title={`${item.label}: ${item.metric}`}
                  className={`flex min-h-[58px] w-full flex-col items-center justify-center gap-1 border px-1.5 py-2 text-center transition ${
                    isActive
                      ? "border-slate-950 bg-slate-950 text-white"
                      : "border-transparent bg-transparent text-slate-500 hover:bg-slate-50 hover:text-slate-950"
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="text-[10px] font-semibold uppercase tracking-[0.12em]">
                    {item.key === "design" ? "Generate" : item.label}
                  </span>
                </button>
              );
            })}
        </div>
      </div>
    </aside>
  );
}
