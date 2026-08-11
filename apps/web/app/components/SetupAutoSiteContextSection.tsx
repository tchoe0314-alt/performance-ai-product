import { DisclosurePanel } from "./ui";
import { sourceDisplayName, sourceDisplaySentence } from "../utils/sourceDisplayText";

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

type OnlineFoundSource = { label?: string; key?: string };

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

function rowDotClass(status: string) {
  if (status === "found") return "bg-emerald-500";
  if (status === "missing") return "bg-amber-500";
  if (status === "outside") return "bg-blue-400";
  if (status === "assumed") return "bg-violet-400";
  return "bg-slate-300";
}

function rowStatusLabel(status: string) {
  if (status === "missing") return "Unavailable";
  if (status === "not_checked") return "Not checked";
  return status.replaceAll("_", " ");
}

function calmSourceMessage(message: string) {
  return sourceDisplaySentence(
    message
      .replace(/\bblocked:?/gi, "needs source:")
      .replace(/\bfailed\b/gi, "could not complete"),
  );
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
  const detectedLabels = autoSiteContextFlowSummary.candidateLabels.length
    ? autoSiteContextFlowSummary.candidateLabels.map((label) => sourceDisplayName(label))
    : autoSiteContextRows.filter((row) => row.status === "found").map((row) => sourceDisplayName(row.title));
  const missingLabels = autoSiteContextFlowSummary.missingLabels.map((label) => sourceDisplayName(label));

  return (
    <DisclosurePanel
      defaultOpen={onlineDiscoveryBusy || autoSiteContextFlowSummary.candidateCount > 0}
      testId="setup-detect-inside-site"
      title="Site Context"
      subtitle={onlineDiscoveryBusy ? "Finding parcels, roads, buildings, terrain, and constraints" : autoSiteContextFlowSummary.message}
      status={onlineDiscoveryBusy ? "Working" : `${autoSiteContextFlowSummary.candidateCount} found`}
      statusClassName={onlineDiscoveryBusy ? "bg-blue-50 text-blue-700" : autoSiteContextFlowSummary.candidateCount ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}
    >
      <div data-testid="auto-site-context-summary">
        {onlineDiscoveryBusy ? (
          <div className="mb-3" data-testid="auto-site-context-progress">
            <div className="flex items-center justify-between text-xs font-medium text-slate-600">
              <span>{autoExistingConditionsStatus.latestSource || "Checking available sources"}</span>
              <span>{Math.round(autoExistingConditionsStatus.progress ?? 0)}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-blue-600 transition-[width]" style={{ width: `${Math.max(4, Math.min(100, autoExistingConditionsStatus.progress ?? 4))}%` }} />
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-3 divide-x divide-slate-100 rounded-[7px] border border-slate-200 bg-white py-2 text-center" data-testid="auto-site-context-counts">
          <span role="group" aria-label={`Found ${foundCount}`} data-testid="auto-site-context-found-count"><strong className="block text-base text-slate-900">{foundCount}</strong><span className="text-[10px] font-medium text-slate-500">Found</span></span>
          <span role="group" aria-label={`Unavailable ${missingCount}`} data-testid="auto-site-context-missing-count"><strong className="block text-base text-slate-900">{missingCount}</strong><span className="text-[10px] font-medium text-slate-500">Unavailable</span></span>
          <span role="group" aria-label={`Assumed ${assumedCount}`} data-testid="auto-site-context-assumed-count"><strong className="block text-base text-slate-900">{assumedCount}</strong><span className="text-[10px] font-medium text-slate-500">Assumed</span></span>
          <span className="sr-only" data-testid="auto-site-context-outside-count">Outside {outsideCount}</span>
        </div>

        <div className="mt-3 text-xs leading-5 text-slate-600" data-testid="auto-site-context-plain-summary">
          <p><span className="font-semibold text-slate-800">Found:</span> {detectedLabels.slice(0, 5).join(", ") || "No usable source objects yet"}{detectedLabels.length > 5 ? ` and ${detectedLabels.length - 5} more` : ""}.</p>
          <p className="mt-1"><span className="font-semibold text-slate-800">Still needed:</span> {missingLabels.slice(0, 4).join(", ") || "Nothing currently listed"}.</p>
          <p className="mt-1 text-slate-500" data-testid="auto-site-context-candidates">
            {autoSiteContextFlowSummary.candidateCount > 0
              ? `${autoSiteContextFlowSummary.candidateCount} source candidate${autoSiteContextFlowSummary.candidateCount === 1 ? "" : "s"} available for review. ${calmSourceMessage(autoExistingConditionsStatus.message)}`
              : calmSourceMessage(autoExistingConditionsStatus.message)}
          </p>
          {detectedLabels.length && missingLabels.length ? <p className="sr-only" data-testid="auto-site-context-evidence-level-note">Detected context and stronger missing evidence can both be true.</p> : null}
        </div>

        <div className="sr-only" aria-hidden="false">
          <span data-testid="auto-site-context-found">{onlineFoundSources.length ? onlineFoundSources.map((source) => sourceDisplayName(source.label || source.key)).join(", ") : "No usable features yet"}</span>
          <span data-testid="auto-site-context-missing">{missingLabels.join(", ") || "No missing source listed"}</span>
        </div>

        <div className={`mt-3 grid gap-2 ${onlineDiscoveryBusy ? "grid-cols-3" : "grid-cols-2"}`}>
          <button
            type="button"
            onClick={onReviewFoundContext}
            disabled={!autoSiteContextFlowSummary.candidateCount && !candidateReviewItemCount}
            className="rounded-[7px] border border-blue-600 bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
            data-testid="review-found-context"
          >
            Review detected items
          </button>
          <button
            type="button"
            onClick={onRerunSiteContext}
            disabled={onlineDiscoveryBusy || !hasAppliedAddress}
            className="rounded-[7px] border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
            data-testid="rerun-site-context"
          >
            {hasAppliedAddress ? "Refresh" : "Apply address first"}
          </button>
          {onlineDiscoveryBusy ? (
            <button
              type="button"
              onClick={onCancelSiteContext}
              className="rounded-[7px] border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              data-testid="cancel-site-context"
            >
              Cancel
            </button>
          ) : null}
        </div>

        <details className="mt-3 border-t border-slate-100 pt-3" data-testid="auto-site-context-details">
          <summary className="flex cursor-pointer list-none items-center text-xs font-semibold text-slate-600">Source and site details</summary>
          {siteIntelligenceSummary.version ? (
            <div className="mt-3 text-xs leading-5 text-slate-600" data-testid="site-intelligence-summary">
              <p className="font-semibold text-slate-800" data-testid="site-intelligence-one-sentence">{String(siteIntelligenceSummary.one_sentence || "Site context is still being assembled.")}</p>
              <p className="mt-1" data-testid="site-intelligence-frontage">Frontage: {roadFrontageMessage || "Not identified"}</p>
              <p data-testid="site-intelligence-driveway">Driveway: {drivewaySuggestionMessage || "Not suggested"}</p>
              <p data-testid="site-intelligence-grading">Grading: {gradingContextMessage || "Terrain source needed"}</p>
              <div className="sr-only">
                <span data-testid="site-intelligence-found-count">Found {siteIntelligenceFoundCount}</span>
                <span data-testid="site-intelligence-missing-count">Missing {siteIntelligenceMissingCount}</span>
                <span data-testid="site-intelligence-assumed-count">Assumed {siteIntelligenceAssumedCount}</span>
                <span data-testid="site-intelligence-outside-count">Outside {siteIntelligenceOutsideCount}</span>
              </div>
            </div>
          ) : null}
          <div className="mt-3 divide-y divide-slate-100 border-t border-slate-100" data-testid="auto-site-context-source-table">
            {autoSiteContextRows.map((row) => (
              <div key={row.key} className="flex items-start gap-2 py-2.5" data-testid={`auto-site-context-row-${row.key}`}>
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${rowDotClass(row.status)}`} />
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-semibold text-slate-800">{sourceDisplayName(row.title)}</span>
                  <span className="mt-0.5 block text-[11px] leading-4 text-slate-500" data-testid={`auto-site-context-detail-${row.key}`}>{sourceDisplaySentence(row.detail)}</span>
                </span>
                <span className="shrink-0 text-[10px] font-semibold text-slate-500" data-testid={`auto-site-context-status-${row.key}`}>{rowStatusLabel(row.status)}</span>
              </div>
            ))}
          </div>
        </details>
      </div>
    </DisclosurePanel>
  );
}
