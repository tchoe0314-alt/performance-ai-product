import type { ReviewIssue } from "../types";

export function ReviewIssueTrackerPanel({
  issues,
  openIssueCount,
  totalIssueCount,
  needsReviewCount,
  drainageIssueCount,
  waivedCount,
  truthLabel,
  onAskCommand,
  onIssueCommand,
}: {
  issues: ReviewIssue[];
  openIssueCount: number;
  totalIssueCount: number;
  needsReviewCount: number;
  drainageIssueCount: number;
  waivedCount: number;
  truthLabel?: string;
  onAskCommand: (command: string) => void;
  onIssueCommand: (action: "resolve" | "reopen" | "waive", issueId: string) => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="review-issue-tracker-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Issue Tracker</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">
            {openIssueCount} open of {totalIssueCount}
          </p>
          <p className="mt-1 text-xs font-medium text-slate-500">
            Blockers, QA, exports, candidates, smart fixes, and depth checks.
          </p>
        </div>
        <button
          type="button"
          onClick={() => onAskCommand("what issues are open?")}
          className="rounded-lg border border-slate-900 bg-slate-950 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-white hover:bg-slate-800"
        >
          Ask Open
        </button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        {[
          ["Open", openIssueCount],
          ["Engineer review", needsReviewCount],
          ["Drainage", drainageIssueCount],
          ["Waived", waivedCount],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {[
          "show drainage blockers",
          "what does the engineer need to review?",
          "reopen grading issue",
        ].map((command) => (
          <button
            key={command}
            type="button"
            onClick={() => onAskCommand(command)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
          >
            {command}
          </button>
        ))}
      </div>
      <div className="mt-3 space-y-2">
        {issues.length ? (
          issues.slice(0, 10).map((issue) => {
            const status = String(issue.status ?? "open");
            const severity = String(issue.severity ?? "review");
            const linkSummary = [
              ...(issue.links?.object_ids ?? []).slice(0, 2),
              ...(issue.links?.sheet_ids ?? []).slice(0, 2),
              ...(issue.links?.system_ids ?? []).slice(0, 2),
            ].filter(Boolean);
            return (
              <div key={issue.issue_id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-800">{issue.title || issue.description || issue.issue_id}</p>
                    <p className="mt-1 truncate text-[11px] uppercase tracking-[0.12em] text-slate-400">
                      {issue.issue_id} / {issue.discipline || "general"} / {issue.assigned_to || issue.assigned_role || "unassigned"}
                    </p>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    status === "resolved"
                      ? "bg-emerald-50 text-emerald-700"
                      : status === "waived_review_required"
                        ? "bg-violet-50 text-violet-700"
                        : severity === "blocker" || severity === "critical" || severity === "error"
                          ? "bg-red-50 text-red-600"
                          : "bg-amber-50 text-amber-700"
                  }`}>
                    {status.replaceAll("_", " ")}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-xs font-medium text-slate-500">
                  {issue.next_action || issue.description || "Review issue details and update status when the workflow item changes."}
                </p>
                <div className="mt-2 grid gap-2 text-xs sm:grid-cols-3">
                  <p className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-medium text-slate-600">
                    <span className="font-semibold text-slate-400">Severity </span>{severity}
                  </p>
                  <p className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-medium text-slate-600">
                    <span className="font-semibold text-slate-400">Links </span>{linkSummary.length ? linkSummary.join(", ") : "none"}
                  </p>
                  <p className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-medium text-slate-600">
                    <span className="font-semibold text-slate-400">History </span>{issue.history?.length ?? 0} / {issue.comments?.length ?? 0} comments
                  </p>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => onIssueCommand("resolve", issue.issue_id)}
                    disabled={status === "resolved"}
                    className="rounded-lg border border-emerald-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Resolve
                  </button>
                  <button
                    type="button"
                    onClick={() => onIssueCommand("reopen", issue.issue_id)}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
                  >
                    Reopen
                  </button>
                  <button
                    type="button"
                    onClick={() => onIssueCommand("waive", issue.issue_id)}
                    className="rounded-lg border border-violet-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-700 hover:bg-violet-50"
                  >
                    Waive
                  </button>
                </div>
              </div>
            );
          })
        ) : (
          <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
            No tracker issues are recorded yet.
          </p>
        )}
      </div>
      <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
        {truthLabel || "Resolving an issue only closes the issue workflow item. Field use remains outside Civora."}
      </p>
    </div>
  );
}
