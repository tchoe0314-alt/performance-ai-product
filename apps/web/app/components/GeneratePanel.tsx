import type { Issue } from "../types";
import { DisclosurePanel, PanelCard } from "./ui";

export type GenerateSystemTarget = "roads" | "parking" | "grading" | "drainage" | "utilities" | "full";

type AutoSiteContextFlowSummary = {
  candidateCount: number;
  candidateLabels: string[];
  missingLabels: string[];
  status: string;
  message: string;
  reviewRequired: boolean;
};

type GenerateFlowSummary = {
  version: "generate_flow_summary_v1";
  generated_at: string;
  target: GenerateSystemTarget;
  ran: string[];
  skipped: string[];
  needs_review: string[];
  notes: string[];
  blocked: boolean;
  next_action: string;
  auto_site_context: AutoSiteContextFlowSummary;
  user_layout_context?: {
    count: number;
    semantic_count: number;
    labels: string[];
    drawn_labels?: string[];
    affected_systems: string[];
    review_required: boolean;
  } | null;
  safety_wording: string;
};

type UserLayoutContextSummary = NonNullable<GenerateFlowSummary["user_layout_context"]>;

type ReactiveValidationState = {
  status: "idle" | "pending" | "ready";
  changedSystems: Array<Exclude<GenerateSystemTarget, "full">>;
  changedTargets: string[];
  requiresConfirmation: boolean;
  message: string;
};

type SystemReadinessRow = {
  key: string;
  label: string;
  runTarget: GenerateSystemTarget;
  status: string;
  blockers: string[];
};

type GeneratePanelProps = {
  missingSite: boolean;
  busy: boolean;
  activeJobStatus: string;
  approvalState: "idle" | "approving" | "starting";
  approvalCheckpointLabel: string | null;
  approvalError: string | null;
  statusMessage: string;
  assistedEnabled: boolean;
  pendingPlacementCount: number;
  pendingPlacementLabels: string[];
  currentUserLayoutContext: UserLayoutContextSummary | null;
  autoSiteContextFlowSummary: AutoSiteContextFlowSummary;
  systemReadinessRows: readonly SystemReadinessRow[];
  issues: Issue[];
  generateFlowSummary: GenerateFlowSummary | null;
  reactiveValidation: ReactiveValidationState;
  reactiveAffectedRunTarget: GenerateSystemTarget | null;
  onAssistedEnabledChange: (value: boolean) => void;
  onStatusMessageChange: (message: string) => void;
  onGenerateFlowSummaryChange: (summary: GenerateFlowSummary) => void;
  onGenerateSystem: (target: GenerateSystemTarget) => void;
  onContinueActiveJob: () => void;
  drainageIssueApplyLabel: (issue: Issue) => string | null;
  canApplyDrainageIssue: (issue: Issue) => boolean;
  getIssueGuidance: (issue: Issue) => { bestNextFix: string | null };
  onApplyDrainageIssue: (issue: Issue) => void;
  formatStageLabel: (value: string) => string;
};

export function GeneratePanel({
  missingSite,
  busy,
  activeJobStatus,
  approvalState,
  approvalCheckpointLabel,
  approvalError,
  statusMessage,
  assistedEnabled,
  pendingPlacementCount,
  pendingPlacementLabels,
  currentUserLayoutContext,
  autoSiteContextFlowSummary,
  systemReadinessRows,
  issues,
  generateFlowSummary,
  reactiveValidation,
  reactiveAffectedRunTarget,
  onAssistedEnabledChange,
  onStatusMessageChange,
  onGenerateFlowSummaryChange,
  onGenerateSystem,
  onContinueActiveJob,
  drainageIssueApplyLabel,
  canApplyDrainageIssue,
  getIssueGuidance,
  onApplyDrainageIssue,
  formatStageLabel,
}: GeneratePanelProps) {
  const normalizedJobStatus = activeJobStatus.trim().toLowerCase();
  const isAwaitingApproval = normalizedJobStatus === "awaiting_approval";
  const isActiveJobRunning = ["queued", "running", "cancelling"].includes(normalizedJobStatus);
  const isApprovalBusy = approvalState !== "idle";
  const actionBusy = busy || isActiveJobRunning || isApprovalBusy;
  const reviewCheckpointLabel = approvalCheckpointLabel || "current phase";
  const issueActions = Array.from(
    issues
      .filter((issue) => Boolean(drainageIssueApplyLabel(issue)))
      .reduce((map, issue) => {
        const key = `${(issue.code ?? issue.message ?? "").toUpperCase()}-${drainageIssueApplyLabel(issue) ?? ""}`;
        if (!map.has(key)) map.set(key, issue);
        return map;
      }, new Map<string, Issue>())
      .values(),
  ).slice(0, 6);

  return (
    <div className="space-y-3" data-testid="clean-generate-panel">
      <PanelCard>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-950">Generate project systems</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">Civora uses the current site, drawn objects, and accepted context.</p>
          </div>
          <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
            missingSite
              ? "bg-amber-50 text-amber-700"
              : isAwaitingApproval
                ? "bg-violet-50 text-violet-700"
                : actionBusy
                  ? "bg-blue-50 text-blue-700"
                  : "bg-emerald-50 text-emerald-700"
          }`}>
            {missingSite ? "Needs site" : isAwaitingApproval ? "Review step" : actionBusy ? "Running" : "Ready"}
          </span>
        </div>
        <button
          type="button"
          data-testid="generate-main-action"
          aria-label="Generate systems"
          onClick={() => {
            if (isAwaitingApproval) {
              onContinueActiveJob();
              return;
            }
            if (missingSite) {
              onStatusMessageChange("Generate needs a locked site boundary in Setup first.");
              onGenerateFlowSummaryChange({
                version: "generate_flow_summary_v1",
                generated_at: new Date().toISOString(),
                target: "full",
                ran: [],
                skipped: systemReadinessRows.map((row) => row.label),
                needs_review: ["Lock a site boundary in Setup before generation."],
                notes: ["Optional sources do not hard-block generation once the site boundary is locked."],
                blocked: true,
                next_action: "Open Setup and lock the site boundary.",
                auto_site_context: autoSiteContextFlowSummary,
                user_layout_context: null,
                safety_wording: "Review draft only.",
              });
              return;
            }
            onGenerateSystem("full");
          }}
          disabled={actionBusy}
          className="mt-4 flex w-full items-center justify-center rounded-[7px] border border-blue-600 bg-blue-600 px-3 py-2.5 text-center text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
        >
          {isAwaitingApproval
            ? `Continue after ${reviewCheckpointLabel}`
            : actionBusy
              ? approvalState === "approving"
                ? "Saving review step"
                : approvalState === "starting"
                  ? "Starting next stage"
                  : "Generation Running"
              : missingSite
                ? "Generate needs site boundary"
                : "Generate"}
        </button>
        {isAwaitingApproval ? (
          <div
            className="mt-3 rounded-xl border border-violet-200 bg-violet-50 px-3 py-2 text-xs font-medium text-violet-900"
            data-testid="generate-review-hold"
          >
            Review {reviewCheckpointLabel}. Continue here when it looks right, or use Chat to request a change.
            {approvalError ? <span className="mt-1 block font-semibold text-red-700">{approvalError}</span> : null}
          </div>
        ) : null}
        <details className="mt-3 border-t border-slate-100 pt-3" data-testid="generate-context-details">
          <summary className="cursor-pointer list-none text-xs font-semibold text-slate-600">Inputs and context</summary>
        <div
          className="mt-3 rounded-[7px] border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600"
          data-testid="generate-auto-site-context"
        >
          Auto Site Context: {autoSiteContextFlowSummary.candidateCount} review-required source candidate{autoSiteContextFlowSummary.candidateCount === 1 ? "" : "s"} available.
          {" "}Sources still needed: {autoSiteContextFlowSummary.missingLabels.join(", ") || "source evidence not available yet"}.
        </div>
        <div
          className={`mt-2 rounded-xl border px-3 py-2 text-xs font-medium ${
            pendingPlacementCount ? "border-amber-200 bg-amber-50 text-amber-800" : "border-slate-200 bg-white text-slate-600"
          }`}
          data-testid="generate-placement-context"
        >
          Placement: {pendingPlacementCount
            ? `${pendingPlacementCount} requested object${pendingPlacementCount === 1 ? "" : "s"} still need placement: ${pendingPlacementLabels.slice(0, 4).join(", ")}${pendingPlacementCount > 4 ? `, plus ${pendingPlacementCount - 4} more` : ""}.`
            : "All requested workspace objects are placed or no requested objects are waiting."}
        </div>
        <div
          className={`mt-2 rounded-xl border px-3 py-2 text-xs font-medium ${
            currentUserLayoutContext?.count
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : "border-slate-200 bg-white text-slate-600"
          }`}
          data-testid="generate-current-drawing-context"
        >
          {currentUserLayoutContext?.count ? (
            <>
              Drawing context ready: {currentUserLayoutContext.labels.slice(0, 4).join(", ")}
              {currentUserLayoutContext.count > 4 ? `, plus ${currentUserLayoutContext.count - 4} more` : ""}.
              {" "}Affects {currentUserLayoutContext.affected_systems.join(", ") || "general layout"}; review context only.
            </>
          ) : (
            "Drawing context: no editable layout cues have been added yet."
          )}
        </div>
        {statusMessage ? (
          <div
            className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700"
            data-testid="generate-latest-status"
            aria-live="polite"
          >
            {statusMessage}
          </div>
        ) : null}
        </details>
      </PanelCard>

      <PanelCard testId="generate-system-list">
        <p className="text-sm font-semibold text-slate-900">Systems</p>
        <div className="mt-2 divide-y divide-slate-100">
          {systemReadinessRows.map((row) => (
            <button
              key={row.key}
              type="button"
              data-testid={`generate-${row.key}`}
              onClick={() => onGenerateSystem(row.runTarget)}
              disabled={actionBusy || isAwaitingApproval}
              className="flex w-full items-center justify-between gap-3 px-1 py-2.5 text-left text-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="min-w-0">
                <span className="block font-semibold text-slate-900">{row.label}</span>
                <span className="mt-0.5 block truncate text-xs font-medium text-slate-500">
                  {row.status === "fresh" ? "Current in this workspace" : row.blockers[0] || "Ready to run"}
                </span>
              </span>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                row.status === "fresh"
                  ? "bg-emerald-50 text-emerald-700"
                  : row.blockers.length
                    ? "bg-amber-50 text-amber-700"
                    : "bg-slate-100 text-slate-500"
              }`}>
                {row.status === "fresh" ? "Current" : row.blockers.length ? "Needs input" : "Ready"}
              </span>
            </button>
          ))}
        </div>
      </PanelCard>

      {issueActions.length ? (
        <PanelCard testId="generate-issue-actions">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Issue Fixes</p>
              <p className="mt-1 text-sm font-semibold text-slate-950">Apply one focused drainage fix, then Civora reruns the review draft.</p>
            </div>
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
              Review
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {issueActions.map((issue) => {
              const applyLabel = drainageIssueApplyLabel(issue);
              const canApply = applyLabel ? canApplyDrainageIssue(issue) : false;
              const guidance = getIssueGuidance(issue);
              return (
                <div key={`${issue.code ?? issue.message}-${applyLabel}`} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-900">{guidance.bestNextFix || issue.message}</p>
                      <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                        {issue.code || "review issue"}
                      </p>
                    </div>
                    {applyLabel ? (
                      <button
                        type="button"
                        onClick={() => onApplyDrainageIssue(issue)}
                        disabled={!canApply || actionBusy || isAwaitingApproval}
                        className={`shrink-0 rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                          canApply && !actionBusy && !isAwaitingApproval
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                            : "cursor-not-allowed border-slate-200 bg-white text-slate-400"
                        }`}
                      >
                        {applyLabel}
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </PanelCard>
      ) : null}

      <PanelCard testId="generate-flow-status">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Run Status</p>
        {generateFlowSummary ? (
          <div className={`mt-3 rounded-xl border px-3 py-2 text-xs ${generateFlowSummary.blocked ? "border-amber-200 bg-amber-50 text-amber-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`} data-testid="generate-flow-summary">
            <p className="font-semibold uppercase tracking-[0.12em]">
              {generateFlowSummary.blocked
                ? "Needs input"
                : generateFlowSummary.skipped.length
                  ? "Started, with skipped systems"
                  : "Started"}
            </p>
            <p className="mt-1">Ran: {generateFlowSummary.ran.join(", ") || "none"}</p>
            <p className="mt-1">Skipped: {generateFlowSummary.skipped.join(", ") || "none"}</p>
            <p className="mt-1">Needs review: {generateFlowSummary.needs_review.slice(0, 3).join("; ") || "standard review"}</p>
            {generateFlowSummary.user_layout_context?.count ? (
              <div className="mt-2 rounded-lg border border-emerald-200 bg-white/70 px-2.5 py-2 text-emerald-900" data-testid="generate-used-drawing-context">
                <p className="font-semibold">Using from drawing: {generateFlowSummary.user_layout_context.labels.slice(0, 5).join(", ")}{generateFlowSummary.user_layout_context.count > 5 ? `, plus ${generateFlowSummary.user_layout_context.count - 5} more` : ""}</p>
                <p className="mt-1 text-[11px] text-emerald-800">
                  {generateFlowSummary.user_layout_context.semantic_count} semantic object{generateFlowSummary.user_layout_context.semantic_count === 1 ? "" : "s"} · affects {generateFlowSummary.user_layout_context.affected_systems.join(", ") || "general layout"} · review context only
                </p>
                {generateFlowSummary.user_layout_context.drawn_labels?.length ? (
                  <p className="mt-1 text-[11px] text-emerald-800">
                    Draft edits: {generateFlowSummary.user_layout_context.drawn_labels.slice(0, 4).join(", ")}{generateFlowSummary.user_layout_context.drawn_labels.length > 4 ? `, plus ${generateFlowSummary.user_layout_context.drawn_labels.length - 4} more` : ""}
                  </p>
                ) : null}
              </div>
            ) : null}
            <p className="mt-1 font-semibold">Next: {generateFlowSummary.next_action}</p>
          </div>
        ) : (
          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
            No generation run started in this session.
          </div>
        )}
      </PanelCard>

      <DisclosurePanel
        testId="generate-system-details"
        title="Advanced"
        subtitle="System toggles and rerun preferences"
        status="Optional"
      >
        <label className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800">
          <span>Assisted generation</span>
          <input
            type="checkbox"
            checked={assistedEnabled}
            onChange={(event) => onAssistedEnabledChange(event.target.checked)}
            className="h-4 w-4 accent-slate-950"
          />
        </label>
      </DisclosurePanel>

      <DisclosurePanel
        testId="generate-reactive-details"
        title="Rerun Details"
        subtitle={reactiveValidation.status === "idle" ? "No stale systems" : reactiveValidation.message || "Impacted systems detected"}
        status={reactiveValidation.requiresConfirmation ? "Confirm" : reactiveValidation.status}
        statusClassName={
          reactiveValidation.requiresConfirmation ? "bg-amber-50 text-amber-700" : reactiveValidation.status === "idle" ? "bg-slate-100 text-slate-500" : "bg-emerald-50 text-emerald-700"
        }
        bodyClassName="text-xs text-slate-600"
      >
        {reactiveValidation.message ? <p className="leading-5">{reactiveValidation.message}</p> : null}
        {reactiveAffectedRunTarget && reactiveValidation.status !== "idle" ? (
          <button
            type="button"
            onClick={() => onGenerateSystem(reactiveAffectedRunTarget)}
            disabled={actionBusy || isAwaitingApproval}
            className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {actionBusy || isAwaitingApproval ? "Wait For Current Run" : "Rerun Affected Systems"}
          </button>
        ) : null}
        {reactiveValidation.changedTargets.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {reactiveValidation.changedTargets.slice(0, 8).map((stage) => (
              <span key={stage} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-600">
                {formatStageLabel(stage)}
              </span>
            ))}
          </div>
        ) : null}
      </DisclosurePanel>
    </div>
  );
}
