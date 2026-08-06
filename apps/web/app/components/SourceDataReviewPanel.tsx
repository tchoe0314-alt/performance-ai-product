import { useState } from "react";

import type {
  BuildingPlacement,
  CandidateReviewCorrection,
  CandidateReviewDecision,
  CandidateReviewItem,
  CivoraVisionQualityReport,
  CivoraVisionReviewWorkspace,
  CivoraVisionTrainingDataset,
  OnlineExistingConditionsSource,
} from "../types";
import { sourceStatusLabel } from "../utils/dashboardDataTypes";
import type { CapabilityExposure } from "../utils/dashboardTypes";
import { sourceDisplayName, sourceDisplaySentence } from "../utils/sourceDisplayText";
import { VisionGroundTruthWorkspace } from "./VisionGroundTruthWorkspace";

const DATA_CAPABILITY_KEYS = new Set([
  "existing_conditions_package",
  "survey_control_package",
  "map_feature_candidates",
  "plan_pdf_understanding",
  "standards_source_registry",
  "candidate_standards_review",
]);

const VISION_FEATURE_OPTIONS = [
  ["building_footprint", "Building"],
  ["road_or_drive", "Road / driveway"],
  ["parking_area", "Parking"],
  ["sidewalk_or_path", "Sidewalk / path"],
  ["water/pond/basin", "Water / basin"],
  ["vegetation/tree_area", "Vegetation / trees"],
  ["utility", "Visible utility object"],
  ["constraint_area", "Constraint / other"],
] as const;

const CANDIDATE_PAGE_SIZE = 12;
type CandidateView = "pending" | "vision" | "reviewed" | "all";

function sourceRecord(candidate: CandidateReviewItem) {
  return candidate.source_record && typeof candidate.source_record === "object"
    ? candidate.source_record
    : {};
}

function isVisionCandidate(candidate: CandidateReviewItem) {
  const source = sourceRecord(candidate);
  return (
    String(source.source_type ?? "") === "image_detected_candidate" ||
    Boolean((source.properties as Record<string, unknown> | undefined)?.vision_detection_id)
  );
}

function correctionGeometryFromObject(item: BuildingPlacement | null | undefined): Record<string, unknown> | null {
  if (!item || item.type === "site" || item.locked || item.placed === false) return null;
  const source = String(item.source ?? "");
  if (item.generated || ["generated", "inferred", "detected_from_image", "detected_from_gis"].includes(source)) {
    return null;
  }
  const points = Array.isArray(item.geometry) && item.geometry.length
    ? item.geometry.map(([x, y]) => [Number(x), Number(y)])
    : item.geometryType === "point"
      ? [[Number(item.x ?? 0) + item.w / 2, Number(item.y ?? 0) + item.d / 2]]
      : [
          [Number(item.x ?? 0), Number(item.y ?? 0)],
          [Number(item.x ?? 0) + item.w, Number(item.y ?? 0)],
          [Number(item.x ?? 0) + item.w, Number(item.y ?? 0) + item.d],
          [Number(item.x ?? 0), Number(item.y ?? 0) + item.d],
        ];
  if (!points.length || points.some((point) => point.some((value) => !Number.isFinite(value)))) return null;
  if (item.geometryType === "point") {
    return { type: "Point", coordinates: points[0] };
  }
  if (item.geometryType === "polyline") {
    return points.length >= 2 ? { type: "LineString", coordinates: points } : null;
  }
  if (points.length < 3) return null;
  const closed = points[0][0] === points.at(-1)?.[0] && points[0][1] === points.at(-1)?.[1]
    ? points
    : [...points, points[0]];
  return { type: "Polygon", coordinates: [closed] };
}

export function SourceDataReviewPanel({
  capabilityRows,
  onlineDiscoveryStatus,
  onlineDiscoveryRan,
  onlineDiscoverySources,
  candidateCounts,
  candidateItems,
  candidateDecisionInFlight,
  onCandidateDecision,
  visionTrainingDataset,
  visionQualityReport,
  visionReviewWorkspace,
  onExportVisionLearning,
  selectedCorrectionObject,
  selectedCorrectionObjects,
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
  candidateDecisionInFlight: {
    candidateId: string;
    action: CandidateReviewDecision;
  } | null;
  onCandidateDecision: (
    candidateId: string | string[],
    decision: CandidateReviewDecision,
    correction?: CandidateReviewCorrection,
  ) => void;
  visionTrainingDataset?: CivoraVisionTrainingDataset;
  visionQualityReport?: CivoraVisionQualityReport;
  visionReviewWorkspace?: CivoraVisionReviewWorkspace;
  onExportVisionLearning: () => void;
  selectedCorrectionObject?: BuildingPlacement | null;
  selectedCorrectionObjects?: BuildingPlacement[];
}) {
  const dataCapabilityRows = capabilityRows.filter((item) => DATA_CAPABILITY_KEYS.has(item.key));
  const [candidateView, setCandidateView] = useState<CandidateView>("pending");
  const [candidatePage, setCandidatePage] = useState(0);
  const [candidateTypeCorrections, setCandidateTypeCorrections] = useState<Record<string, string>>({});
  const [selectedVisionCandidateIds, setSelectedVisionCandidateIds] = useState<string[]>([]);
  const visionCandidateCount = candidateItems.filter(isVisionCandidate).length;
  const filteredCandidates = candidateItems.filter((candidate) => {
    const status = String(candidate.status || "pending").toLowerCase();
    if (candidateView === "vision") return isVisionCandidate(candidate);
    if (candidateView === "reviewed") return status === "accepted" || status === "rejected";
    if (candidateView === "pending") return status !== "accepted" && status !== "rejected";
    return true;
  });
  const candidatePageCount = Math.max(1, Math.ceil(filteredCandidates.length / CANDIDATE_PAGE_SIZE));
  const activeCandidatePage = Math.min(candidatePage, candidatePageCount - 1);
  const candidatePageStart = activeCandidatePage * CANDIDATE_PAGE_SIZE;
  const visibleCandidates = filteredCandidates.slice(candidatePageStart, candidatePageStart + CANDIDATE_PAGE_SIZE);
  const candidatePageEnd = candidatePageStart + visibleCandidates.length;
  const visionInferenceCounts = candidateItems.filter(isVisionCandidate).reduce(
    (counts, candidate) => {
      const source = sourceRecord(candidate);
      const properties = source.properties && typeof source.properties === "object"
        ? (source.properties as Record<string, unknown>)
        : {};
      const provider = String(candidate.provider || source.provider || source.source_name || properties.provider || "").toLowerCase();
      const modelName = String(properties.model_name || "").trim();
      if (provider.includes("heuristic")) counts.heuristic += 1;
      else if (provider.includes("learned") || modelName) counts.learned += 1;
      else counts.external += 1;
      return counts;
    },
    { learned: 0, heuristic: 0, external: 0 },
  );
  const reviewedVisionCount = Number(visionTrainingDataset?.reviewed_example_count ?? 0);
  const trainableVisionCount = Number(visionTrainingDataset?.training_eligible_example_count ?? 0);
  const selectedCorrectionGeometry = correctionGeometryFromObject(selectedCorrectionObject);
  const selectedOutlines = (selectedCorrectionObjects?.length
    ? selectedCorrectionObjects
    : selectedCorrectionObject
      ? [selectedCorrectionObject]
      : [])
    .map((item) => ({ label: item.label, geometry: correctionGeometryFromObject(item) }))
    .filter((item): item is { label: string; geometry: Record<string, unknown> } => Boolean(item.geometry));
  const firstSelectedVisionCandidate = candidateItems.find((item) =>
    selectedVisionCandidateIds.includes(item.candidate_id),
  );
  const firstSelectedSource = firstSelectedVisionCandidate ? sourceRecord(firstSelectedVisionCandidate) : {};
  const selectedVisionFeatureType = firstSelectedVisionCandidate
    ? candidateTypeCorrections[firstSelectedVisionCandidate.candidate_id]
      ?? firstSelectedVisionCandidate.corrected_feature_type
      ?? String(firstSelectedSource.feature_type ?? "constraint_area")
    : "constraint_area";

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
                <span className="font-semibold text-slate-700">{sourceDisplayName(source.label || source.key)}</span>
                <span
                  className={`shrink-0 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                    Number(source.candidate_count ?? 0) > 0 ? "text-amber-700" : "text-red-600"
                  }`}
                >
                  {Number(source.candidate_count ?? 0) > 0 ? `${source.candidate_count} found` : sourceStatusLabel(source.status)}
                </span>
              </div>
              <p className="mt-1 truncate text-xs font-medium text-slate-500">
                {sourceDisplayName(source.provider || source.agency || source.source_type, "Provider not configured")}
              </p>
              {Number(source.candidate_count ?? 0) <= 0 ? (
                <p className="mt-1 text-xs text-slate-500">
                  {sourceDisplaySentence((source.blockers ?? [])[0] || `${source.label || source.key} source is missing/unavailable.`)}
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
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Review Detected Items</p>
            <p className="mt-1 text-xs font-medium text-slate-500">Choose what belongs in this project. You can change the decision later.</p>
          </div>
          <span className="shrink-0 rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
            {candidateCounts.pending ?? 0} pending
          </span>
        </div>
        <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-900" data-testid="detected-item-decision-help">
          <strong>Accept</strong> adds the detected item to project context. <strong>Reject</strong> keeps it out. <strong>Pending</strong> leaves it undecided. Detected items do not become survey or control evidence.
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
        {visionCandidateCount ? (
          <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50/60 px-3 py-3" data-testid="vision-learning-summary">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-slate-800">Civora Vision feedback</p>
                <p className="mt-1 text-xs text-slate-600">
                  {visionCandidateCount} visual candidate{visionCandidateCount === 1 ? "" : "s"}; {reviewedVisionCount} reviewed; {trainableVisionCount} rights-cleared for training.
                </p>
                <p className="mt-1 text-[11px] font-medium text-slate-600" data-testid="vision-inference-source-summary">
                  {[
                    visionInferenceCounts.learned ? `${visionInferenceCounts.learned} learned-model` : "",
                    visionInferenceCounts.heuristic ? `${visionInferenceCounts.heuristic} heuristic estimate` : "",
                    visionInferenceCounts.external ? `${visionInferenceCounts.external} external/other` : "",
                  ].filter(Boolean).join("; ")}
                  {visionInferenceCounts.heuristic ? ". Heuristic estimates are not learned inference." : "."}
                </p>
                <p className="mt-1 text-[11px] text-slate-500">
                  {visionQualityReport?.quality_claim_allowed
                    ? `Measured precision ${Math.round(Number(visionQualityReport.precision ?? 0) * 100)}% and recall ${Math.round(Number(visionQualityReport.recall ?? 0) * 100)}%.`
                    : "Accuracy is not claimed until a rights-cleared ground-truth set is attached."}
                </p>
              </div>
              <button
                type="button"
                onClick={onExportVisionLearning}
                className="shrink-0 rounded-lg border border-sky-200 bg-white px-2.5 py-2 text-[11px] font-semibold text-sky-800 hover:bg-sky-100"
              >
                Export feedback
              </button>
            </div>
          </div>
        ) : null}
        <VisionGroundTruthWorkspace
          workspace={visionReviewWorkspace}
          selectedCandidateIds={selectedVisionCandidateIds}
          selectedOutlines={selectedOutlines}
          selectedFeatureType={selectedVisionFeatureType}
          busy={Boolean(candidateDecisionInFlight)}
          onDecision={(candidateIds, action, correction) => onCandidateDecision(candidateIds, action, correction)}
          onClearSelection={() => setSelectedVisionCandidateIds([])}
        />
        {candidateItems.length ? (
          <div className="mt-3 flex flex-wrap items-center gap-2" role="tablist" aria-label="Detected item views">
            {([
              ["pending", "Pending"],
              ["vision", `Vision ${visionCandidateCount}`],
              ["reviewed", "Reviewed"],
              ["all", "All"],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={candidateView === value}
                onClick={() => {
                  setCandidateView(value);
                  setCandidatePage(0);
                }}
                className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  candidateView === value
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        ) : null}
        <div className="mt-3 space-y-2">
          {visibleCandidates.length ? (
            visibleCandidates.map((candidate) => {
              const status = candidate.status === "accepted" || candidate.status === "rejected" ? candidate.status : "pending";
              const candidateBusy = candidateDecisionInFlight?.candidateId === candidate.candidate_id;
              const anyCandidateBusy = Boolean(candidateDecisionInFlight);
              const source = sourceRecord(candidate);
              const sourceProperties =
                source.properties && typeof source.properties === "object"
                  ? (source.properties as Record<string, unknown>)
                  : {};
              const visionCandidate = isVisionCandidate(candidate);
              const originalFeatureType = String(source.feature_type ?? "");
              const selectedFeatureType =
                candidateTypeCorrections[candidate.candidate_id] ??
                candidate.corrected_feature_type ??
                originalFeatureType;
              const sourceRights =
                sourceProperties.source_rights && typeof sourceProperties.source_rights === "object"
                  ? (sourceProperties.source_rights as Record<string, unknown>)
                  : {};
              const geometryQuality =
                sourceProperties.geometry_quality_v1 && typeof sourceProperties.geometry_quality_v1 === "object"
                  ? (sourceProperties.geometry_quality_v1 as Record<string, unknown>)
                  : {};
              const outlineQuality = Number(
                geometryQuality.quality_score ?? sourceProperties.outline_quality_score ?? sourceProperties.candidate_quality_score,
              );
              const cleanupActions = Array.isArray(geometryQuality.cleanup_actions)
                ? geometryQuality.cleanup_actions.map((item) => String(item).replaceAll("_", " ")).filter(Boolean)
                : [];
              return (
                <div
                  key={candidate.candidate_id}
                  className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3"
                  data-testid="detected-item-candidate"
                  data-candidate-id={candidate.candidate_id}
                  aria-busy={candidateBusy}
                >
                  <div className="flex items-start justify-between gap-3">
                    {visionCandidate ? (
                      <input
                        type="checkbox"
                        aria-label={`Select vision detection ${candidate.label || candidate.candidate_id}`}
                        checked={selectedVisionCandidateIds.includes(candidate.candidate_id)}
                        onChange={(event) =>
                          setSelectedVisionCandidateIds((current) =>
                            event.target.checked
                              ? [...new Set([...current, candidate.candidate_id])]
                              : current.filter((candidateId) => candidateId !== candidate.candidate_id),
                          )
                        }
                        disabled={anyCandidateBusy}
                        className="mt-1 h-4 w-4 shrink-0 accent-slate-900"
                      />
                    ) : null}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-800">{sourceDisplayName(candidate.label || candidate.candidate_type, "Detected item")}</p>
                      <p className="mt-1 truncate text-xs font-medium text-slate-500">
                        {sourceDisplayName(candidate.provider || candidate.source, "Unknown provider")}
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
                      <span className="break-words">
                        {sourceDisplayName(
                          candidate.source || candidate.provider,
                          candidate.source_url ? "See source details" : "Unknown",
                        )}
                      </span>
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
                  <p className="mt-2 text-xs font-medium text-slate-500">{sourceDisplaySentence(candidate.blocker_review_reason, "Review why this item was detected before deciding.")}</p>
                  {candidate.source_url ? (
                    <details className="mt-2 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-500">
                      <summary className="cursor-pointer font-semibold text-slate-600">Source details</summary>
                      <p className="mt-2 break-all">{candidate.source_url}</p>
                    </details>
                  ) : null}
                  {visionCandidate ? (
                    <div className="mt-3 rounded-lg border border-sky-200 bg-white p-2.5" data-testid="vision-candidate-correction">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="text-[11px] font-semibold text-sky-800">Civora Vision detection</p>
                          <p className="mt-0.5 text-[11px] text-slate-500">
                            {sourceRights.training_use_allowed === true
                              ? "Source rights permit training after review."
                              : "Feedback is saved, but training waits for source-rights clearance."}
                          </p>
                          <p className="mt-1 text-[11px] font-medium text-slate-600" data-testid="vision-outline-quality">
                            {Number.isFinite(outlineQuality) && outlineQuality > 0
                              ? `Outline quality ${Math.round(outlineQuality * 100)}%`
                              : "Provider outline"}
                            {cleanupActions.length ? ` | ${cleanupActions.slice(0, 2).join(", ")}` : " | check edges before accepting"}
                          </p>
                        </div>
                        <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:flex-none">
                          <select
                            aria-label={`Correct detected type for ${candidate.label || candidate.candidate_id}`}
                            value={selectedFeatureType}
                            onChange={(event) =>
                              setCandidateTypeCorrections((current) => ({
                                ...current,
                                [candidate.candidate_id]: event.target.value,
                              }))
                            }
                            disabled={anyCandidateBusy}
                            className="min-w-0 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs font-medium text-slate-700"
                          >
                            {VISION_FEATURE_OPTIONS.map(([value, label]) => (
                              <option key={value} value={value}>{label}</option>
                            ))}
                          </select>
                          <button
                            type="button"
                            onClick={() =>
                              onCandidateDecision(candidate.candidate_id, "correct", {
                                correctedFeatureType: selectedFeatureType,
                                reason: `Corrected visual detection from ${originalFeatureType || "unknown"} to ${selectedFeatureType}.`,
                              })
                            }
                            disabled={anyCandidateBusy || !selectedFeatureType || selectedFeatureType === originalFeatureType}
                            className="shrink-0 rounded-lg border border-sky-200 bg-white px-2.5 py-2 text-[11px] font-semibold text-sky-800 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {candidateBusy && candidateDecisionInFlight?.action === "correct" ? "Saving..." : "Save type"}
                          </button>
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-sky-100 pt-2">
                        <p className="min-w-0 flex-1 text-[11px] text-slate-500">
                          {selectedCorrectionGeometry && selectedCorrectionObject
                            ? `Selected outline: ${selectedCorrectionObject.label}. Project-local geometry will be saved; training waits for map registration.`
                            : "If the detected edges are wrong, draw the correct outline, select it, then use it here before Accept."}
                        </p>
                        <button
                          type="button"
                          data-testid="vision-use-selected-outline"
                          onClick={() => {
                            if (!selectedCorrectionGeometry || !selectedCorrectionObject) return;
                            onCandidateDecision(candidate.candidate_id, "redraw", {
                              correctedFeatureType: selectedFeatureType || originalFeatureType,
                              correctedGeometry: selectedCorrectionGeometry,
                              correctionCoordinateSpace: "project_local",
                              reason: `Replaced visual detection geometry with user-drawn outline ${selectedCorrectionObject.label}.`,
                            });
                          }}
                          disabled={anyCandidateBusy || !selectedCorrectionGeometry}
                          className="shrink-0 rounded-lg border border-sky-200 bg-white px-2.5 py-2 text-[11px] font-semibold text-sky-800 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Use selected outline
                        </button>
                      </div>
                    </div>
                  ) : null}
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      title="Add this detected item to project context"
                      onClick={() => onCandidateDecision(candidate.candidate_id, "accept")}
                      disabled={status === "accepted" || anyCandidateBusy}
                      className="rounded-lg border border-emerald-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {candidateBusy && candidateDecisionInFlight?.action === "accept" ? "Saving..." : "Accept"}
                    </button>
                    <button
                      type="button"
                      title="Keep this detected item out of the project"
                      onClick={() => onCandidateDecision(candidate.candidate_id, "reject")}
                      disabled={status === "rejected" || anyCandidateBusy}
                      className="rounded-lg border border-red-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {candidateBusy && candidateDecisionInFlight?.action === "reject" ? "Saving..." : "Reject"}
                    </button>
                    <button
                      type="button"
                      title="Leave this detected item undecided"
                      onClick={() => onCandidateDecision(candidate.candidate_id, "pending")}
                      disabled={status === "pending" || anyCandidateBusy}
                      className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {candidateBusy && candidateDecisionInFlight?.action === "pending" ? "Saving..." : "Pending"}
                    </button>
                  </div>
                </div>
              );
            })
          ) : candidateItems.length ? (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
              No detected items match this view.
            </p>
          ) : (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
              No source candidates have been discovered or imported yet.
            </p>
          )}
        </div>
        {filteredCandidates.length ? (
          <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
            <p className="text-xs font-medium text-slate-500" data-testid="detected-items-page-summary">
              Showing {candidatePageStart + 1}-{candidatePageEnd} of {filteredCandidates.length}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCandidatePage((current) => Math.max(0, current - 1))}
                disabled={activeCandidatePage === 0}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setCandidatePage((current) => Math.min(candidatePageCount - 1, current + 1))}
                disabled={activeCandidatePage >= candidatePageCount - 1}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </>
  );
}
