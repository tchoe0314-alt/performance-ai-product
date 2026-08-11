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

const LEFT_RAIL_WORKFLOWS: PrimaryWorkflowKey[] = ["setup", "draw", "design", "analyze", "deliver"];

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
      className="civora-motion-sidebar civora-left-mode-rail fixed inset-x-2 bottom-2 z-[760] flex min-w-0 shrink-0 flex-col overflow-y-auto rounded-[10px] border border-slate-200/90 bg-white/97 p-1.5 shadow-[0_18px_54px_-34px_rgba(15,23,42,0.42)] backdrop-blur-xl lg:bottom-0 lg:left-0 lg:right-auto lg:top-[52px] lg:rounded-none lg:border-y-0 lg:border-l-0 lg:p-1 lg:pt-2 lg:shadow-none"
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
                  className={`group relative flex min-h-[58px] w-full flex-col items-center justify-center gap-1 rounded-[8px] border px-1 py-2 text-center transition ${
                    isActive
                      ? "border-blue-100 bg-blue-50 text-blue-700"
                      : "border-transparent bg-transparent text-slate-500 hover:bg-slate-50 hover:text-slate-950"
                  }`}
                >
                  {isActive ? <span className="absolute left-0 top-3 h-8 w-0.5 rounded-r bg-blue-600" /> : null}
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="text-[10px] font-semibold tracking-normal">
                    {item.key === "design" ? "Generate" : item.key === "analyze" ? "Review" : item.label}
                  </span>
                </button>
              );
            })}
        </div>
      </div>
    </aside>
  );
}
