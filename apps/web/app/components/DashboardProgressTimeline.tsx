import type { ProgressTimelineStep } from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";

type ProgressTimelineState = {
  current_step_id?: string;
  current_step_label?: string;
  current_status?: ProgressTimelineStep["status"];
  current_panel?: string;
  completed_count?: number;
  total_count?: number;
  next_action?: string;
  export_blockers?: string[];
};

type DashboardProgressTimelineProps = {
  progressTimelineState: ProgressTimelineState;
  progressTimelineSteps: ProgressTimelineStep[];
  progressPercent: number;
  onOpenPanel: (panel: SidePanelKey) => void;
  progressPanelTarget: (value?: string) => SidePanelKey;
  progressTimelineDotClass: (status?: ProgressTimelineStep["status"]) => string;
  progressTimelineStatusClass: (status?: ProgressTimelineStep["status"]) => string;
};

export function DashboardProgressTimeline({
  progressTimelineState,
  progressTimelineSteps,
  progressPercent,
  onOpenPanel,
  progressPanelTarget,
  progressTimelineDotClass,
  progressTimelineStatusClass,
}: DashboardProgressTimelineProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="progress-timeline-dashboard">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Progress Timeline</p>
          <p className="mt-1 text-base font-semibold text-slate-950">
            {progressTimelineState.current_step_label || "Setup"}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {progressTimelineState.completed_count ?? 0} of {progressTimelineState.total_count ?? progressTimelineSteps.length} phases complete
          </p>
        </div>
        <button
          type="button"
          onClick={() => onOpenPanel(progressPanelTarget(progressTimelineState.current_panel))}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
        >
          {progressTimelineState.next_action || "Open current"}
        </button>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-slate-800" style={{ width: `${progressPercent}%` }} />
      </div>
      <details className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Show step details
        </summary>
        <div className="mt-3 space-y-2">
          {progressTimelineSteps.map((item, index) => {
            const isCurrent = item.id === progressTimelineState.current_step_id;
            const blockers = item.blockers ?? [];
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onOpenPanel(progressPanelTarget(item.action_panel || item.action?.target))}
                className={`w-full rounded-xl border px-3 py-2 text-left transition hover:bg-white ${
                  isCurrent ? "border-slate-900 bg-white" : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className={`mt-1 h-3 w-3 shrink-0 rounded-full border ${progressTimelineDotClass(item.status)}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-900">
                        {index + 1}. {item.label}
                      </p>
                      <span className={`shrink-0 text-[10px] font-semibold uppercase tracking-[0.12em] ${progressTimelineStatusClass(item.status)}`}>
                        {item.status.replace("_", " ")}
                      </span>
                    </div>
                    {item.summary ? (
                      <p className="mt-1 text-xs text-slate-500">{item.summary}</p>
                    ) : null}
                    {blockers.length ? (
                      <p className="mt-1 text-xs font-semibold text-amber-700">
                        Needs input: {blockers.slice(0, 2).join("; ")}
                      </p>
                    ) : null}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </details>
      {progressTimelineState.export_blockers?.length ? (
        <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
          Export needs input: {progressTimelineState.export_blockers.slice(0, 3).join("; ")}
        </div>
      ) : null}
    </div>
  );
}
