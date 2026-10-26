"use client";

import { MapPinned, Box, SlidersHorizontal, CircleAlert, FileText } from "lucide-react";
import { WORKSPACE_STAGE_KEYS, WORKSPACE_STAGES, type WorkspaceStage } from "../utils/workspaceStages";

type WorkspaceLeftRailProps = {
  visible: boolean;
  activeStage: WorkspaceStage;
  restoreTruthLabel: string;
  onSelectStage: (stage:WorkspaceStage) => void;
};

const icons = {brief:MapPinned,explore:Box,analyze:SlidersHorizontal,review:CircleAlert,deliver:FileText};

export function WorkspaceLeftRail({
  visible,
  activeStage,
  restoreTruthLabel,
  onSelectStage,
}: WorkspaceLeftRailProps) {
  return (
    <aside
      data-testid="left-sidebar"
      data-motion-state={visible ? "open" : "closed"}
      aria-hidden={!visible}
      inert={!visible}
      className="civora-motion-sidebar civora-left-mode-rail fixed inset-x-2 bottom-2 z-[760] flex min-w-0 shrink-0 flex-col overflow-y-auto rounded-[14px] border border-slate-200/90 bg-white/95 p-1.5 shadow-[0_18px_54px_-34px_rgba(15,23,42,0.42)] backdrop-blur-xl lg:bottom-0 lg:left-0 lg:right-auto lg:top-[52px] lg:rounded-none lg:border-y-0 lg:border-l-0 lg:p-1.5 lg:pt-3 lg:shadow-none"
    >
      <span data-testid="workspace-restore-status" className="sr-only">{restoreTruthLabel}</span>
      <div className="rounded-lg border border-transparent bg-transparent" data-testid="primary-workflow-sidebar">
        <div className="space-y-1">
          {WORKSPACE_STAGE_KEYS.map((stage) => {
              const item = WORKSPACE_STAGES[stage];
              const Icon = icons[stage];
              const isActive = activeStage === stage;
              return (
                <button
                  key={stage}
                  type="button"
                  aria-label={item.label}
                  data-testid={`workspace-stage-${stage}`}
                  onClick={() => onSelectStage(stage)}
                  aria-current={isActive ? "page" : undefined}
                  title={`Open ${item.label}`}
                  className={`group relative flex min-h-[58px] w-full flex-col items-center justify-center gap-1 rounded-[10px] border px-1 py-2 text-center transition ${
                    isActive
                      ? "border-slate-900 bg-slate-950 text-white shadow-sm"
                      : "border-transparent bg-transparent text-slate-700 hover:bg-slate-50 hover:text-slate-950"
                  }`}
                >
                  {isActive ? <span className="absolute -left-1.5 top-3 h-8 w-0.5 rounded-r bg-blue-500" /> : null}
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="text-[10px] font-semibold tracking-normal">
                    {item.label}
                  </span>
                </button>
              );
            })}
        </div>
      </div>
    </aside>
  );
}
