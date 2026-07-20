"use client";

import { FolderOpen } from "lucide-react";

import type { PrimaryWorkflowItem, PrimaryWorkflowKey } from "../utils/dashboardTypes";
import type { SidePanelKey } from "../utils/workspaceShell";

type WorkspaceLeftRailProps = {
  visible: boolean;
  activePanel: SidePanelKey | null;
  activeWorkflowKey: PrimaryWorkflowKey;
  restoreTruthLabel: string;
  primaryWorkflowItems: PrimaryWorkflowItem[];
  onOpenProjects: () => void;
  onOpenPanel: (panel: SidePanelKey) => void;
};

const LEFT_RAIL_WORKFLOWS: PrimaryWorkflowKey[] = ["setup", "draw", "design", "deliver"];

export function WorkspaceLeftRail({
  visible,
  activePanel,
  activeWorkflowKey,
  restoreTruthLabel,
  primaryWorkflowItems,
  onOpenProjects,
  onOpenPanel,
}: WorkspaceLeftRailProps) {
  return (
    <aside
      data-testid="left-sidebar"
      data-motion-state={visible ? "open" : "closed"}
      aria-hidden={!visible}
      className="civora-motion-sidebar civora-left-mode-rail fixed inset-x-3 top-20 z-[260] flex max-h-[calc(100svh-6rem)] min-w-0 shrink-0 flex-col overflow-y-auto rounded-xl border border-slate-200/80 bg-white/90 px-2.5 pb-28 pt-3 shadow-[0_24px_72px_-50px_rgba(15,23,42,0.62)] backdrop-blur-xl lg:bottom-0 lg:left-0 lg:right-auto lg:top-16 lg:max-h-none lg:w-[112px] lg:rounded-none lg:border-y-0 lg:border-l-0 lg:bg-white/92 lg:px-3 lg:pb-4 lg:shadow-none"
    >
      <button
        type="button"
        onClick={onOpenProjects}
        aria-label="Projects"
        className={`mb-2 flex min-h-[58px] w-full flex-col items-center justify-center gap-1 rounded-2xl border px-2 py-2 text-center transition ${
          activePanel === "projects"
            ? "border-slate-950 bg-slate-950 text-white"
            : "border-transparent bg-transparent text-slate-500 hover:bg-slate-50 hover:text-slate-950"
        }`}
      >
        <FolderOpen className="mx-auto h-4 w-4" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em]">Projects</span>
      </button>
      <span data-testid="workspace-restore-status" className="sr-only">{restoreTruthLabel}</span>
      <div className="rounded-lg border border-transparent bg-transparent" data-testid="primary-workflow-sidebar">
        <div className="space-y-1.5">
          {primaryWorkflowItems
            .filter((item) => LEFT_RAIL_WORKFLOWS.includes(item.key))
            .map((item) => {
              const Icon = item.icon;
              const isActive = activeWorkflowKey === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  aria-label={item.key === "draw" ? "Draw" : item.label}
                  onClick={() => onOpenPanel(item.panel)}
                  aria-current={isActive ? "page" : undefined}
                  title={`${item.label}: ${item.metric}`}
                  className={`flex min-h-[58px] w-full flex-col items-center justify-center gap-1 rounded-2xl border px-2 py-2 text-center transition ${
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
