import { DisclosurePanel } from "./ui";

type AutoExistingConditionsStatus = {
  status: string;
  message: string;
  progress?: number;
  latestSource?: string;
};

type AutoSiteContextFlowSummary = {
  candidateCount: number;
  candidateLabels: string[];
  missingLabels: string[];
  status: string;
  message: string;
  reviewRequired: boolean;
};

type AutoSiteContextRow = {
  key: string;
  title: string;
  detail: string;
  status: string;
};

type OnlineFoundSource = {
  label?: string;
  key?: string;
};

type SetupAutoSiteContextSectionProps = {
  autoSiteContextFlowSummary: AutoSiteContextFlowSummary;
  autoExistingConditionsStatus: AutoExistingConditionsStatus;
  siteIntelligenceSummary: Record<string, unknown>;
  siteIntelligenceFoundCount: number;
  siteIntelligenceMissingCount: number;
  siteIntelligenceAssumedCount: number;
  siteIntelligenceOutsideCount: number;
  roadFrontageMessage: string;
  drivewaySuggestionMessage: string;
  gradingContextMessage: string;
  autoSiteContextRows: AutoSiteContextRow[];
  onlineFoundSources: OnlineFoundSource[];
  candidateReviewItemCount: number;
  hasAppliedAddress: boolean;
  onlineDiscoveryBusy: boolean;
  onReviewFoundContext: () => void;
  onRerunSiteContext: () => void;
  onCancelSiteContext: () => void;
};

function rowDotClass(status: string): string {
  if (status === "found") return "bg-emerald-500";
  if (status === "missing") return "bg-amber-500";
  if (status === "outside") return "bg-blue-400";
  if (status === "assumed") return "bg-violet-400";
  return "bg-slate-300";
}

function rowStatusClass(status: string): string {
  if (status === "found") return "bg-emerald-50 text-emerald-700";
  if (status === "missing") return "bg-amber-50 text-amber-700";
  if (status === "outside") return "bg-blue-50 text-blue-700";
  if (status === "assumed") return "bg-violet-50 text-violet-700";
  return "bg-slate-100 text-slate-500";
}

function rowStatusLabel(status: string): string {
  if (status === "missing") return "needs source";
  if (status === "not_checked") return "not checked";
  return status.replace("_", " ");
}

function formatSourceGuidance(message: string): string {
  return message
    .replace(/\bblocked:/gi, "needs source:")
    .replace(/\bblocked\b/gi, "needs source")
    .replace(/\bBlocked\b/g, "Needs source")
    .replace(/\bfailed\b/gi, "could not complete")
    .replace(/\bfailure\b/gi, "source issue");
}

export function SetupAutoSiteContextSection({
  autoSiteContextFlowSummary,
  autoExistingConditionsStatus,
  siteIntelligenceSummary,
  siteIntelligenceFoundCount,
  siteIntelligenceMissingCount,
  siteIntelligenceAssumedCount,
  siteIntelligenceOutsideCount,
  roadFrontageMessage,
  drivewaySuggestionMessage,
  gradingContextMessage,
  autoSiteContextRows,
  onlineFoundSources,
  candidateReviewItemCount,
  hasAppliedAddress,
  onlineDiscoveryBusy,
  onReviewFoundContext,
  onRerunSiteContext,
  onCancelSiteContext,
}: SetupAutoSiteContextSectionProps) {
  const foundCount = autoSiteContextRows.filter((row) => row.status === "found").length;
  const missingCount = autoSiteContextRows.filter((row) => row.status === "missing").length;
  const assumedCount = autoSiteContextRows.filter((row) => row.status === "assumed").length;
  const outsideCount = autoSiteContextRows.filter((row) => row.status === "outside").length;
  const sourceGuidanceMessage = formatSourceGuidance(autoExistingConditionsStatus.message);
  const detectedLabels = autoSiteContextFlowSummary.candidateLabels.length
    ? autoSiteContextFlowSummary.candidateLabels
    : autoSiteContextRows.filter((row) => row.status === "found").map((row) => row.title);
  const detectedSummary = detectedLabels.length
    ? detectedLabels.slice(0, 5).join(", ")
    : "nothing usable yet";
  const missingSummary = autoSiteContextFlowSummary.missingLabels.length
    ? autoSiteContextFlowSummary.missingLabels.slice(0, 4).join(", ")
    : "source evidence not available yet";

  return (
    <DisclosurePanel
      defaultOpen={autoSiteContextFlowSummary.candidateCount > 0 || autoExistingConditionsStatus.status !== "waiting"}
      testId="setup-detect-inside-site"
      title="Auto Site Context Results"
      subtitle={autoSiteContextFlowSummary.message}
      status={autoExistingConditionsStatus.status === "blocked" ? "Needs source" : `${autoSiteContextFlowSummary.candidateCount} found`}
      statusClassName={
        autoExistingConditionsStatus.status === "blocked"
          ? "bg-amber-50 text-amber-700"
          : autoSiteContextFlowSummary.candidateCount
            ? "bg-amber-50 text-amber-700"
            : "bg-slate-100 text-slate-500"
      }
      bodyClassName=""
    >
      <div data-testid="auto-site-context-summary">
        {onlineDiscoveryBusy ? (
          <div className="mb-3 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2" data-testid="auto-site-context-progress">
            <div className="flex items-center justify-between gap-3 text-xs font-semibold text-sky-900">
              <span className="min-w-0 truncate">{autoExistingConditionsStatus.latestSource || "Checking site sources"}</span>
              <span className="shrink-0">{Math.max(0, Math.min(100, Math.round(autoExistingConditionsStatus.progress ?? 0)))}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sky-100" aria-hidden="true">
              <div
                className="h-full rounded-full bg-sky-600 transition-[width] duration-200"
                style={{ width: `${Math.max(4, Math.min(100, autoExistingConditionsStatus.progress ?? 4))}%` }}
              />
            </div>
            <p className="mt-2 text-xs font-medium leading-5 text-sky-800">{sourceGuidanceMessage}</p>
          </div>
        ) : null}
        <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800" data-testid="auto-site-context-candidates">
          {autoExistingConditionsStatus.status === "blocked"
            ? sourceGuidanceMessage
            : autoExistingConditionsStatus.status === "waiting" && /cancel/i.test(autoExistingConditionsStatus.message)
              ? sourceGuidanceMessage
            : autoSiteContextFlowSummary.candidateCount
              ? `${autoSiteContextFlowSummary.candidateCount} source candidate${autoSiteContextFlowSummary.candidateCount === 1 ? "" : "s"} available for review. Sources still needed: ${autoSiteContextFlowSummary.missingLabels.join(", ") || "source evidence not available yet"}.`
              : `No source candidates found yet. Sources still needed: ${autoSiteContextFlowSummary.missingLabels.join(", ") || "source evidence not available yet"}.`}
        </p>
        <div className="mb-3 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-3 text-xs text-emerald-900" data-testid="auto-site-context-plain-summary">
          <p className="font-semibold">Detected inside site: {detectedSummary}{detectedLabels.length > 5 ? `, plus ${detectedLabels.length - 5} more` : ""}.</p>
          <p className="mt-1 text-emerald-800">
            Source notes: missing {missingSummary}. Use these as review context for Generate; they are not survey/control.
          </p>
        </div>
        {siteIntelligenceSummary.version ? (
          <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3" data-testid="site-intelligence-summary">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Site Intelligence</p>
                <p className="mt-1 text-sm font-semibold leading-5 text-slate-800" data-testid="site-intelligence-one-sentence">
                  {String(siteIntelligenceSummary.one_sentence || "Apply an address, lock the site, or add sources to build site intelligence.")}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
                Review
              </span>
            </div>
            <div className="mt-3 grid gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 sm:grid-cols-4">
              <span data-testid="site-intelligence-found-count">Found {siteIntelligenceFoundCount}</span>
              <span data-testid="site-intelligence-missing-count">Missing {siteIntelligenceMissingCount}</span>
              <span data-testid="site-intelligence-assumed-count">Assumed {siteIntelligenceAssumedCount}</span>
              <span data-testid="site-intelligence-outside-count">Outside {siteIntelligenceOutsideCount}</span>
            </div>
            <div className="mt-3 grid gap-2 text-xs text-slate-600 lg:grid-cols-3">
              <p data-testid="site-intelligence-frontage">
                <span className="font-semibold text-slate-800">Frontage:</span>{" "}
                {roadFrontageMessage || "Road frontage was not inferred yet."}
              </p>
              <p data-testid="site-intelligence-driveway">
                <span className="font-semibold text-slate-800">Driveway:</span>{" "}
                {drivewaySuggestionMessage || "Confirm road frontage before driveway suggestions."}
              </p>
              <p data-testid="site-intelligence-grading">
                <span className="font-semibold text-slate-800">Grading:</span>{" "}
                {gradingContextMessage || "Add terrain or survey evidence before relying on grading direction."}
              </p>
            </div>
          </div>
        ) : null}
        <div className="grid grid-cols-4 gap-2 text-center text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500" data-testid="auto-site-context-counts">
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2" data-testid="auto-site-context-found-count">Found {foundCount}</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2" data-testid="auto-site-context-missing-count">Need source {missingCount}</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2" data-testid="auto-site-context-assumed-count">Assumed {assumedCount}</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2" data-testid="auto-site-context-outside-count">Outside {outsideCount}</span>
        </div>
        <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white" data-testid="auto-site-context-source-table">
          {autoSiteContextRows.map((row) => (
            <div
              key={row.key}
              className="grid gap-2 border-b border-slate-100 px-3 py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_7.5rem]"
              data-testid={`auto-site-context-row-${row.key}`}
            >
              <div className="min-w-0">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${rowDotClass(row.status)}`} />
                  <p className="truncate text-sm font-semibold text-slate-900">{row.title}</p>
                </div>
                <p className="mt-1 text-xs font-medium leading-5 text-slate-500" data-testid={`auto-site-context-detail-${row.key}`}>
                  {row.detail}
                </p>
              </div>
              <span className={`h-fit rounded-full px-2.5 py-1 text-center text-[10px] font-semibold uppercase tracking-[0.12em] ${rowStatusClass(row.status)}`} data-testid={`auto-site-context-status-${row.key}`}>
                {rowStatusLabel(row.status)}
              </span>
            </div>
          ))}
        </div>
        <div className="sr-only" aria-hidden="false">
          <span data-testid="auto-site-context-found">
            {onlineFoundSources.length ? onlineFoundSources.map((source) => source.label || source.key).join(", ") : "No usable features yet"}
          </span>
          <span data-testid="auto-site-context-missing">
            {autoSiteContextFlowSummary.missingLabels.length ? autoSiteContextFlowSummary.missingLabels.join(", ") : "Source evidence not available yet"}
          </span>
        </div>
        <button
          type="button"
          onClick={onReviewFoundContext}
          disabled={!autoSiteContextFlowSummary.candidateCount && !candidateReviewItemCount}
          className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          data-testid="review-found-context"
        >
          Review / Accept Found Items
        </button>
        <div className={`mt-2 grid gap-2 ${onlineDiscoveryBusy ? "grid-cols-2" : "grid-cols-1"}`}>
          <button
            type="button"
            onClick={onRerunSiteContext}
            disabled={!hasAppliedAddress || onlineDiscoveryBusy}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="rerun-site-context"
          >
            {hasAppliedAddress ? "Rerun Site Context" : "Apply Address First"}
          </button>
          {onlineDiscoveryBusy ? (
            <button
              type="button"
              onClick={onCancelSiteContext}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50"
              data-testid="cancel-site-context"
            >
              Cancel Lookup
            </button>
          ) : null}
        </div>
      </div>
    </DisclosurePanel>
  );
}
