import type { LucideIcon } from "lucide-react";
import type { PrimaryWorkflowItem } from "../utils/dashboardTypes";

export type WorkspaceToolbarTool = {
  label: string;
  icon: LucideIcon;
  action: () => void;
  active: boolean;
  testId?: string;
};

type WorkspaceCanvasChromePanelProps = {
  hidden: boolean;
  sidebarVisible: boolean;
  rightRailCollapsed: boolean;
  projectName: string;
  activeWorkflowKey: string;
  workflowItems: PrimaryWorkflowItem[];
  toolbarTools: WorkspaceToolbarTool[];
  previewMode: "2d" | "3d";
  previewQuality: "standard" | "high";
  onOpenPanel: (panel: PrimaryWorkflowItem["panel"]) => void;
  onMinimize: () => void;
  onPreviewModeSelect: (mode: "2d" | "3d") => void;
  onPreviewQualitySelect: (quality: "standard" | "high") => void;
};

export function WorkspaceCanvasChromePanel({
  hidden,
  sidebarVisible,
  rightRailCollapsed,
  projectName,
  activeWorkflowKey,
  workflowItems,
  toolbarTools,
  previewMode,
  previewQuality,
  onOpenPanel,
  onMinimize,
  onPreviewModeSelect,
  onPreviewQualitySelect,
}: WorkspaceCanvasChromePanelProps) {
  return (
    <div
      className={`absolute left-3 right-3 top-3 z-40 rounded-xl border border-slate-200/80 bg-white/86 px-3 py-3 shadow-[0_20px_64px_-48px_rgba(15,23,42,0.62)] backdrop-blur-2xl transition-all duration-200 lg:left-[112px] ${rightRailCollapsed ? "lg:right-4" : "lg:right-[408px]"} ${sidebarVisible || hidden ? "hidden" : "opacity-100"}`}
      aria-hidden={hidden}
      hidden
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Civora Workspace</p>
            <p className="mt-1 truncate text-base font-semibold text-slate-950">{projectName}</p>
          </div>
          <div className="flex min-w-0 items-center gap-2">
            {!sidebarVisible ? (
              <div className="flex min-w-0 gap-1 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-1">
                {workflowItems.map((item) => {
                  const isActive = activeWorkflowKey === item.key;
                  return (
                    <button
                      key={`top-${item.key}`}
                      type="button"
                      aria-label={item.label}
                      onClick={() => onOpenPanel(item.panel)}
                      className={`min-h-9 min-w-[78px] rounded-md px-2.5 py-1.5 text-center text-xs font-semibold transition ${
                        isActive
                          ? "bg-white text-blue-700 shadow-sm ring-1 ring-blue-200"
                          : "text-slate-600 hover:bg-white hover:text-slate-950"
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            ) : null}
            <button
              type="button"
              onClick={onMinimize}
              className="h-9 shrink-0 rounded-lg border border-slate-200 bg-white px-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-600 hover:bg-slate-50"
              aria-label="Minimize Civora workspace controls"
            >
              Minimize
            </button>
          </div>
        </div>
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {toolbarTools.map((tool) => {
              const Icon = tool.icon;
              return (
                <button
                  key={tool.label}
                  type="button"
                  onClick={tool.action}
                  title={tool.label}
                  data-testid={tool.testId}
                  className={`flex h-9 items-center gap-2 rounded-lg border px-2.5 text-[13px] font-semibold transition ${
                    tool.active
                      ? "border-blue-200 bg-blue-50 text-blue-700"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tool.label}</span>
                </button>
              );
            })}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-1">
              {(["2d", "3d"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  data-testid={mode === "2d" ? "workspace-preview-mode-2d" : "workspace-preview-mode-3d"}
                  title={mode === "2d" ? "Show 2D plan preview" : "Show 3D model preview"}
                  onClick={() => onPreviewModeSelect(mode)}
                  className={`h-8 rounded-md px-3 text-xs font-semibold uppercase tracking-[0.08em] ${
                    previewMode === mode ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
            <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-1">
              {(["standard", "high"] as const).map((quality) => (
                <button
                  key={quality}
                  type="button"
                  data-testid={quality === "standard" ? "workspace-preview-quality-standard" : "workspace-preview-quality-high"}
                  title={quality === "standard" ? "Use faster standard rendering" : "Use richer high quality rendering"}
                  onClick={() => onPreviewQualitySelect(quality)}
                  className={`h-8 rounded-md px-3 text-xs font-semibold capitalize ${
                    previewQuality === quality ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"
                  }`}
                >
                  {quality}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
