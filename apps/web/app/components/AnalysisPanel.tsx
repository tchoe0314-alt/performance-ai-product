type AnalysisPanelIssue = {
  id: string;
  severity: "warning" | "error";
  message: string;
  code?: string;
  applyLabel?: string;
  canApply?: boolean;
  onApply?: () => void;
};

type AnalysisPanelProps = {
  modelIssueCount: number;
  accessIssueCount: number;
  systemsCompleteCount: number;
  blockedSystemCount: number;
  issues: AnalysisPanelIssue[];
  onRunAccessAnalysis: () => void;
  onOpenDashboard: () => void;
};

export function AnalysisPanel({
  modelIssueCount,
  accessIssueCount,
  systemsCompleteCount,
  blockedSystemCount,
  issues,
  onRunAccessAnalysis,
  onOpenDashboard,
}: AnalysisPanelProps) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Model issues", modelIssueCount],
          ["Access issues", accessIssueCount],
          ["Systems complete", systemsCompleteCount],
          ["Needs input", blockedSystemCount],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={onRunAccessAnalysis}
          className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Run access analysis
        </button>
        <button
          type="button"
          onClick={onOpenDashboard}
          className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Open dashboard
        </button>
      </div>
      {issues.map((issue) => (
        <div key={issue.id} className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${issue.severity === "error" ? "text-red-600" : "text-amber-600"}`}>
                {issue.severity}
              </p>
              <p className="mt-2 text-sm text-slate-700">{issue.message}</p>
              {issue.code ? (
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{issue.code}</p>
              ) : null}
            </div>
            {issue.applyLabel ? (
              <button
                type="button"
                onClick={issue.onApply}
                disabled={!issue.canApply}
                className={`shrink-0 rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                  issue.canApply
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                    : "cursor-not-allowed border-slate-200 bg-white text-slate-400"
                }`}
              >
                {issue.applyLabel}
              </button>
            ) : null}
          </div>
        </div>
      ))}
      {!issues.length ? <p className="text-sm text-slate-500">No active analysis issues.</p> : null}
    </div>
  );
}
