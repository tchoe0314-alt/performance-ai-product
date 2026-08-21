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
  const needsSystemInput = blockedSystemCount > 0;
  const hasAttentionItems = issues.length > 0 || needsSystemInput;

  return (
    <div className="space-y-3" data-testid="clean-review-panel">
      <section className="rounded-[8px] border border-slate-200 bg-white p-3">
        <div className="flex items-start gap-3">
          <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] ${hasAttentionItems ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>
            {hasAttentionItems ? <CircleAlert className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-950">
              {issues.length
                ? `${issues.length} item${issues.length === 1 ? "" : "s"} need attention`
                : needsSystemInput
                  ? "Setup needs input before a full review"
                  : "No active review issues"}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-500">{systemsCompleteCount} systems current · {blockedSystemCount} need input</p>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 divide-x divide-slate-100 border-y border-slate-100 py-2 text-center text-xs">
          <span><strong className="block text-sm text-slate-900">{modelIssueCount}</strong><span className="text-slate-500">Model</span></span>
          <span><strong className="block text-sm text-slate-900">{accessIssueCount}</strong><span className="text-slate-500">Access</span></span>
        </div>
        <button type="button" onClick={onRunAccessAnalysis} className="mt-3 flex w-full items-center justify-center gap-2 rounded-[7px] border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50">
          <ScanSearch className="h-4 w-4" /> Run review scan
        </button>
      </section>

      <section className="overflow-hidden rounded-[8px] border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-3 py-2.5">
          <p className="text-sm font-semibold text-slate-900">Issues</p>
        </div>
        <div className="divide-y divide-slate-100">
          {issues.map((issue) => (
            <div key={issue.id} className="p-3">
              <div className="flex items-start gap-2.5">
                <CircleAlert className={`mt-0.5 h-4 w-4 shrink-0 ${issue.severity === "error" ? "text-red-500" : "text-amber-500"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium leading-5 text-slate-700">{issue.message}</p>
                  {issue.code ? <p className="mt-1 text-[10px] font-semibold text-slate-400">{issue.code}</p> : null}
                </div>
                {issue.applyLabel ? (
                  <button type="button" onClick={issue.onApply} disabled={!issue.canApply} className="shrink-0 rounded-[6px] border border-slate-200 px-2 py-1 text-[10px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                    {issue.applyLabel}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
          {!issues.length ? (
            <p className="px-3 py-5 text-center text-xs text-slate-500">
              {needsSystemInput
                ? "No conflicts are detected yet. Complete the needed inputs, then run the review scan."
                : "This project has no active review issues."}
            </p>
          ) : null}
        </div>
      </section>

      <button
        type="button"
        onClick={onOpenDashboard}
        className="flex w-full items-center justify-between rounded-[8px] border border-slate-200 bg-white px-3 py-2.5 text-left text-xs font-semibold text-slate-700 hover:bg-slate-50"
      >
        Project Health
        <ChevronRight className="h-4 w-4 text-slate-400" />
      </button>
    </div>
  );
}
import { CheckCircle2, ChevronRight, CircleAlert, ScanSearch } from "lucide-react";
