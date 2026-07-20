import type { ComponentProps } from "react";
import type { Issue } from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";
import { DesignAlternativesPanel } from "./DesignAlternativesPanel";
import { ReportGateListPanel } from "./ReportGateListPanel";
import { ReviewIssueTrackerPanel } from "./ReviewIssueTrackerPanel";
import { SourceConfidencePanel } from "./SourceConfidencePanel";

type IssueGuidance = {
  explanation: string | null;
  bestNextFix: string | null;
  suggested: string[] | null;
};

type ReportsPanelProps = {
  stats: Array<{ label: string; value: number | string }>;
  engineeringHealthLinks: Array<{ panel: SidePanelKey; label: string }>;
  issues: Issue[];
  drainageIssueApplyLabel: (issue: Issue) => string | null;
  canApplyDrainageIssue: (issue: Issue) => boolean;
  getIssueGuidance: (issue: Issue) => IssueGuidance;
  onApplyDrainageIssue: (issue: Issue) => void;
  onOpenSidePanel: (panel: SidePanelKey) => void;
  reviewIssueTracker: ComponentProps<typeof ReviewIssueTrackerPanel>;
  truthGates: ComponentProps<typeof ReportGateListPanel>["items"];
  reviewGates: ComponentProps<typeof ReportGateListPanel>["items"];
  designAlternatives: ComponentProps<typeof DesignAlternativesPanel>;
  sourceConfidence: ComponentProps<typeof SourceConfidencePanel>;
};

export function ReportsPanel({
  stats,
  engineeringHealthLinks,
  issues,
  drainageIssueApplyLabel,
  canApplyDrainageIssue,
  getIssueGuidance,
  onApplyDrainageIssue,
  onOpenSidePanel,
  reviewIssueTracker,
  truthGates,
  reviewGates,
  designAlternatives,
  sourceConfidence,
}: ReportsPanelProps) {
  return (
    <>
      <details className="rounded-2xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          What is the review package?
        </summary>
        <div className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
          <p>
            The review package collects current project inputs, assumptions, visible blockers,
            generated outputs, quantities, and export evidence so a qualified user or external
            licensed engineer can review the work.
          </p>
          <p className="font-semibold text-slate-800">
            It is not a field-use package. Exports remain review packages for external review.
          </p>
          <p>Field use remains outside Civora.</p>
        </div>
      </details>

      <div className="grid grid-cols-2 gap-2">
        {stats.map(({ label, value }) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Engineering health</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {engineeringHealthLinks.map(({ panel, label }) => (
            <button
              key={panel}
              type="button"
              onClick={() => onOpenSidePanel(panel)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {issues.length ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Engineering Issues</p>
            <span className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Apply fixes</span>
          </div>
          <div className="mt-3 space-y-2 text-xs text-slate-700">
            {issues.map((issue, idx) => {
              const applyLabel = drainageIssueApplyLabel(issue);
              const canApply = applyLabel ? canApplyDrainageIssue(issue) : false;
              const guidance = getIssueGuidance(issue);
              return (
                <div
                  key={`${issue.message}-${idx}`}
                  className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2"
                >
                  <div>
                    <p className="font-semibold text-slate-800">{issue.message}</p>
                    {issue.code ? (
                      <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-400">{issue.code}</p>
                    ) : null}
                    {guidance.bestNextFix ? (
                      <p className="mt-2 text-[11px] font-semibold text-slate-700">Best next fix: {guidance.bestNextFix}</p>
                    ) : null}
                  </div>
                  {applyLabel ? (
                    <button
                      type="button"
                      onClick={() => onApplyDrainageIssue(issue)}
                      disabled={!canApply}
                      className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                        canApply
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          : "border-slate-200 bg-white text-slate-400 cursor-not-allowed"
                      }`}
                    >
                      {applyLabel}
                    </button>
                  ) : (
                    <span className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Review</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <ReviewIssueTrackerPanel {...reviewIssueTracker} />
      <ReportGateListPanel title="Truth gates" items={truthGates} />
      <ReportGateListPanel title="Review gates" items={reviewGates} />
      <DesignAlternativesPanel {...designAlternatives} />
      <SourceConfidencePanel {...sourceConfidence} />
    </>
  );
}
