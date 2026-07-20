import type { CandidateReviewItem, OnlineExistingConditionsSource } from "../types";
import { sourceStatusLabel } from "../utils/dashboardDataTypes";
import type { CapabilityExposure } from "../utils/dashboardTypes";

type CandidateReviewDecision = "accept" | "reject" | "pending";

const DATA_CAPABILITY_KEYS = new Set([
  "existing_conditions_package",
  "survey_control_package",
  "map_feature_candidates",
  "plan_pdf_understanding",
  "standards_source_registry",
  "candidate_standards_review",
]);

export function SourceDataReviewPanel({
  capabilityRows,
  onlineDiscoveryStatus,
  onlineDiscoveryRan,
  onlineDiscoverySources,
  candidateCounts,
  candidateItems,
  onCandidateDecision,
}: {
  capabilityRows: CapabilityExposure[];
  onlineDiscoveryStatus: string;
  onlineDiscoveryRan: boolean;
  onlineDiscoverySources: OnlineExistingConditionsSource[];
  candidateCounts: {
    accepted?: number;
    rejected?: number;
    pending?: number;
  };
  candidateItems: CandidateReviewItem[];
  onCandidateDecision: (candidateId: string, decision: CandidateReviewDecision) => void;
}) {
  const dataCapabilityRows = capabilityRows.filter((item) => DATA_CAPABILITY_KEYS.has(item.key));

  return (
    <>
      <div className="mt-3 space-y-2">
        {dataCapabilityRows.map((item) => (
          <div key={item.key} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-semibold text-slate-700">{item.label}</span>
              <span
                className={`text-right text-[11px] font-semibold uppercase tracking-[0.12em] ${
                  item.status === "block" ? "text-red-600" : item.status === "idle" ? "text-slate-400" : "text-amber-600"
                }`}
              >
                {item.value}
              </span>
            </div>
            {item.status === "block" || item.status === "idle" ? <p className="mt-1 text-xs text-slate-500">{item.exactFix}</p> : null}
          </div>
        ))}
      </div>
      <div className="mt-4 border-t border-slate-200 pt-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Online discovery</p>
          <span className="text-[11px] font-semibold text-slate-500">{onlineDiscoveryRan ? sourceStatusLabel(onlineDiscoveryStatus) : "not run"}</span>
        </div>
        <div className="mt-3 space-y-2">
          {onlineDiscoverySources.slice(0, 8).map((source) => (
            <div key={source.key || source.label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="flex items-start justify-between gap-3 text-sm">
                <span className="font-semibold text-slate-700">{source.label || source.key}</span>
                <span
                  className={`shrink-0 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                    Number(source.candidate_count ?? 0) > 0 ? "text-amber-700" : "text-red-600"
                  }`}
                >
                  {Number(source.candidate_count ?? 0) > 0 ? `${source.candidate_count} found` : sourceStatusLabel(source.status)}
                </span>
              </div>
              <p className="mt-1 truncate text-xs font-medium text-slate-500">
                {source.provider || source.agency || source.source_type || "Provider not configured"}
              </p>
              {Number(source.candidate_count ?? 0) <= 0 ? (
                <p className="mt-1 text-xs text-slate-500">
                  {(source.blockers ?? [])[0] || `${source.label || source.key} source is missing/unavailable.`}
                </p>
              ) : (
                <p className="mt-1 text-xs text-slate-500">Candidate evidence only; review is required before use.</p>
              )}
            </div>
          ))}
          {!onlineDiscoverySources.length ? (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
              Apply an address to run online source discovery.
            </p>
          ) : null}
        </div>
      </div>
      <div className="mt-4 border-t border-slate-200 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Candidate Review Inbox</p>
            <p className="mt-1 text-xs font-medium text-slate-500">Accepted items become draft evidence for review only.</p>
          </div>
          <span className="shrink-0 rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
            {candidateCounts.pending ?? 0} pending
          </span>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 text-center text-[11px] font-semibold uppercase tracking-[0.12em]">
          {[
            ["Accepted", candidateCounts.accepted ?? 0, "text-emerald-700"],
            ["Rejected", candidateCounts.rejected ?? 0, "text-red-600"],
            ["Pending", candidateCounts.pending ?? 0, "text-amber-700"],
          ].map(([label, value, color]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-2">
              <p className="text-slate-400">{label}</p>
              <p className={`mt-1 text-sm ${color}`}>{value}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 space-y-2">
          {candidateItems.length ? (
            candidateItems.slice(0, 8).map((candidate) => {
              const status = candidate.status === "accepted" || candidate.status === "rejected" ? candidate.status : "pending";
              return (
                <div key={candidate.candidate_id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-800">{candidate.label || candidate.candidate_type || "Candidate"}</p>
                      <p className="mt-1 truncate text-xs font-medium text-slate-500">
                        {candidate.provider || candidate.source || "Unknown provider"}
                        {candidate.source_date ? ` | ${candidate.source_date}` : ""}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                        status === "accepted"
                          ? "bg-emerald-50 text-emerald-700"
                          : status === "rejected"
                            ? "bg-red-50 text-red-600"
                            : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {status}
                    </span>
                  </div>
                  <div className="mt-2 grid gap-2 text-xs sm:grid-cols-3">
                    <p className="min-w-0 rounded-lg border border-slate-200 bg-white px-2 py-2 font-medium text-slate-600">
                      <span className="font-semibold text-slate-400">Source </span>
                      <span className="break-words">{candidate.source || candidate.source_url || "Unknown"}</span>
                    </p>
                    <p className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-medium text-slate-600">
                      <span className="font-semibold text-slate-400">Confidence </span>
                      {String(candidate.confidence ?? "unknown")}
                    </p>
                    <p className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-medium text-slate-600">
                      <span className="font-semibold text-slate-400">Objects </span>
                      {Number(candidate.object_count ?? 1)}
                    </p>
                  </div>
                  <p className="mt-2 text-xs font-medium text-slate-500">{candidate.blocker_review_reason || "Review reason not recorded."}</p>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => onCandidateDecision(candidate.candidate_id, "accept")}
                      disabled={status === "accepted"}
                      className="rounded-lg border border-emerald-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Accept
                    </button>
                    <button
                      type="button"
                      onClick={() => onCandidateDecision(candidate.candidate_id, "reject")}
                      disabled={status === "rejected"}
                      className="rounded-lg border border-red-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Reject
                    </button>
                    <button
                      type="button"
                      onClick={() => onCandidateDecision(candidate.candidate_id, "pending")}
                      disabled={status === "pending"}
                      className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Pending
                    </button>
                  </div>
                </div>
              );
            })
          ) : (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
              No source candidates have been discovered or imported yet.
            </p>
          )}
        </div>
      </div>
    </>
  );
}
