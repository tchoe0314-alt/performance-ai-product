import type { EngineDepthDashboard } from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";

type DashboardEngineDepthPanelProps = {
  dashboard: EngineDepthDashboard;
  onOpenPanel: (panel: SidePanelKey) => void;
};

export function DashboardEngineDepthPanel({ dashboard, onOpenPanel }: DashboardEngineDepthPanelProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="engine-depth-dashboard">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Engine Depth</p>
          <p className="mt-1 text-lg font-semibold text-slate-950">
            {Math.round(dashboard.overall_depth_score ?? 0)}% backend depth
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {dashboard.truth_label || "Deterministic backend evidence for review only."}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${
          dashboard.status === "passed" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"
        }`}>
          {dashboard.status === "passed" ? "Audit passed" : "Audit blocked"}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-4 gap-2">
        {[
          ["Engines", dashboard.engine_count ?? 0],
          ["Scenarios", dashboard.scenario_count ?? 0],
          ["Failed", dashboard.failed_check_count ?? 0],
          ["Blockers", dashboard.blocker_count ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-base font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-2">
        {(dashboard.per_engine_scores ?? []).slice(0, 6).map((engine) => {
          const score = Math.round(engine.score ?? 0);
          const blocked = (engine.blocker_count ?? 0) > 0 || (engine.failed_check_count ?? 0) > 0;
          return (
            <button
              key={engine.engine_id || engine.name}
              type="button"
              onClick={() => onOpenPanel((engine.fix_link?.target_panel || "analysis") as SidePanelKey)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left hover:bg-white"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-slate-900">{engine.name || engine.engine_id}</span>
                  <span className="mt-0.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                    {(engine.classification || "unknown").replace(/-/g, " ")} · {engine.scenario_coverage_count ?? 0} scenario(s)
                  </span>
                </span>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                  blocked ? "bg-red-50 text-red-600" : score >= 90 ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                }`}>
                  {score}%
                </span>
              </div>
              {blocked ? (
                <p className="mt-2 text-xs font-semibold text-red-600">
                  {engine.first_failing_layer || engine.fix_link?.suggested_next_action || "Missing deterministic proof"}
                </p>
              ) : null}
            </button>
          );
        })}
      </div>
      <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Scenario coverage
        </summary>
        <div className="mt-3 space-y-2">
          {(dashboard.scenario_coverage ?? []).slice(0, 5).map((scenario) => (
            <button
              key={scenario.scenario_id || scenario.name}
              type="button"
              onClick={() => onOpenPanel((scenario.blocker_link?.target_panel || "analysis") as SidePanelKey)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-left hover:bg-slate-50"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-semibold text-slate-800">{scenario.name || scenario.scenario_id}</span>
                <span className="text-xs font-semibold text-slate-500">
                  {scenario.covered_engine_count ?? 0}/{scenario.required_engine_count ?? 0} · {Math.round(scenario.coverage_percent ?? 0)}%
                </span>
              </div>
            </button>
          ))}
        </div>
      </details>
      <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Missing proof checklist
        </summary>
        <div className="mt-3 space-y-2">
          {(dashboard.missing_proof_checklist ?? []).slice(0, 6).map((item) => (
            <button
              key={item.id || `${item.scenario_id}-${item.engine_id}-${item.label}`}
              type="button"
              onClick={() => onOpenPanel((item.target_panel || "analysis") as SidePanelKey)}
              className="w-full rounded-lg border border-red-100 bg-white px-3 py-2 text-left hover:bg-red-50"
            >
              <span className="block text-xs font-semibold text-slate-800">{item.label}</span>
              <span className="mt-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-red-500">
                {item.engine_id || "engine"} · {item.scenario_id || "scenario"}
              </span>
            </button>
          ))}
          {!(dashboard.missing_proof_checklist ?? []).length ? (
            <p className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600">
              No missing deterministic proof recorded in the latest audit.
            </p>
          ) : null}
        </div>
      </details>
      {(dashboard.trend_history ?? []).length > 1 ? (
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Trend</p>
          <div className="mt-3 flex items-end gap-2">
            {(dashboard.trend_history ?? []).slice(-8).map((point) => (
              <div key={`${point.index}-${point.overall_depth_score}`} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className="w-full rounded-t bg-slate-800"
                  style={{ height: `${Math.max(8, Math.min(64, point.overall_depth_score ?? 0))}px` }}
                />
                <span className="text-[10px] font-semibold text-slate-500">{Math.round(point.overall_depth_score ?? 0)}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
