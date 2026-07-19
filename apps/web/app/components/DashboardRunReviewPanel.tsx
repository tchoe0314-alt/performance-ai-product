import type { WorkflowReviewDashboard } from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";

type DashboardRunReviewPanelProps = {
  dashboard: WorkflowReviewDashboard;
  onOpenPanel: (panel: SidePanelKey) => void;
};

export function DashboardRunReviewPanel({ dashboard, onOpenPanel }: DashboardRunReviewPanelProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Run review</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">
            {dashboard.operational_state || "No saved state"}
          </p>
        </div>
        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
          {dashboard.release_ready ? "Ready for engineer review" : "Review required"}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {[
          ["Runs", dashboard.run_count ?? 0],
          ["Artifacts", dashboard.artifact_count ?? 0],
          ["Conflicts", dashboard.conflict_review?.unresolved_conflict_count ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold text-slate-700">
        <button
          type="button"
          onClick={() => onOpenPanel("deliverables")}
          className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left hover:bg-white"
        >
          <span className="block uppercase tracking-[0.14em] text-slate-400">Deliverables</span>
          <span className="mt-1 block text-sm text-slate-900">
            {(dashboard.deliverable_manager?.ready ?? []).length}/
            {(dashboard.deliverable_manager?.requested ?? []).length} review ready
          </span>
        </button>
        <button
          type="button"
          onClick={() => onOpenPanel("analysis")}
          className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left hover:bg-white"
        >
          <span className="block uppercase tracking-[0.14em] text-slate-400">Assumptions</span>
          <span className="mt-1 block text-sm text-slate-900">
            {dashboard.assumption_review?.requires_approval ? "Acceptance required" : "Engineer review required"}
          </span>
        </button>
      </div>
      {dashboard.primary_attention ? (
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
          {dashboard.primary_attention.replace(/_/g, " ")}
        </p>
      ) : null}
    </div>
  );
}
