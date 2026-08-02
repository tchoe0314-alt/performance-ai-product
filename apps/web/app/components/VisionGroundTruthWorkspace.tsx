import type {
  CandidateReviewCorrection,
  CandidateReviewDecision,
  CivoraVisionReviewWorkspace,
} from "../types";

type ReviewedOutline = {
  label: string;
  geometry: Record<string, unknown>;
};

function friendlyClass(value: string) {
  return value
    .replace("water/pond/basin", "water / basin")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function reasonLabel(value: string) {
  const labels: Record<string, string> = {
    pending_human_review: "Pending review",
    high_model_uncertainty: "Uncertain detection",
    confidence_missing: "Confidence missing",
    source_classification_disagreement: "Sources disagree",
    baseline_shadow_disagreement: "Detectors disagree",
    underrepresented_class: "More examples needed",
    rights_cleared_learning_value: "Rights cleared",
    cross_source_overlap: "Overlaps another source",
  };
  return labels[value] ?? friendlyClass(value);
}

export function VisionGroundTruthWorkspace({
  workspace,
  selectedCandidateIds,
  selectedOutlines,
  selectedFeatureType,
  busy,
  onDecision,
  onClearSelection,
}: {
  workspace?: CivoraVisionReviewWorkspace;
  selectedCandidateIds: string[];
  selectedOutlines: ReviewedOutline[];
  selectedFeatureType: string;
  busy: boolean;
  onDecision: (
    candidateIds: string[],
    action: CandidateReviewDecision,
    correction?: CandidateReviewCorrection,
  ) => void;
  onClearSelection: () => void;
}) {
  if (!workspace) return null;
  const ledger = workspace.ledger_summary ?? {};
  const dataset = workspace.dataset_summary ?? {};
  const queue = workspace.active_learning_queue ?? {};
  const coverage = workspace.coverage ?? {};
  const splitCounts = dataset.counts_by_split ?? {};
  const queueItems = queue.items ?? [];
  const coverageRows = Object.entries(coverage.classes ?? {});
  const mergeReady = selectedCandidateIds.length >= 2 && selectedOutlines.length === 1;
  const splitReady = selectedCandidateIds.length === 1 && selectedOutlines.length >= 2;

  const runDecision = (
    action: CandidateReviewDecision,
    correction?: CandidateReviewCorrection,
  ) => {
    if (!selectedCandidateIds.length || busy) return;
    onDecision(selectedCandidateIds, action, correction);
    onClearSelection();
  };

  return (
    <div
      className="mt-3 rounded-xl border border-slate-200 bg-white p-3"
      data-testid="vision-ground-truth-workspace"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-slate-800">Vision review workspace</p>
          <p className="mt-1 text-[11px] text-slate-500">
            Reviewed edits are recorded in an integrity-checked learning ledger. The visible detector does not change here.
          </p>
        </div>
        <span
          className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
            ledger.integrity_valid === false ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
          }`}
        >
          {ledger.integrity_valid === false ? "Integrity issue" : "Ledger verified"}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
        {[
          ["Review events", Number(ledger.event_count ?? 0)],
          ["Reviewed labels", Number(dataset.annotation_count ?? 0)],
          ["Priority queue", Number(queue.candidate_count ?? 0)],
          ["Classes needing data", Number(coverage.blocked_classes?.length ?? 0)],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[11px]">
        {[
          ["Train", Number(splitCounts.train ?? 0)],
          ["Validation", Number(splitCounts.validation ?? 0)],
          ["Test", Number(splitCounts.test ?? 0)],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border border-slate-200 px-2 py-2">
            <span className="font-semibold text-slate-500">{label}</span>{" "}
            <span className="font-semibold text-slate-800">{value}</span>
          </div>
        ))}
      </div>

      {selectedCandidateIds.length ? (
        <div className="mt-3 rounded-lg border border-sky-200 bg-sky-50/60 p-3" data-testid="vision-review-selection-actions">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold text-slate-800">
                {selectedCandidateIds.length} detection{selectedCandidateIds.length === 1 ? "" : "s"} selected
              </p>
              <p className="mt-1 text-[11px] text-slate-600">
                {selectedOutlines.length
                  ? `${selectedOutlines.length} editable outline${selectedOutlines.length === 1 ? "" : "s"} selected in Draw.`
                  : "Select and edit user-drawn outlines in Draw for merge or split geometry."}
              </p>
            </div>
            <button
              type="button"
              onClick={onClearSelection}
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-[11px] font-semibold text-slate-600 hover:bg-slate-50"
            >
              Clear
            </button>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <button
              type="button"
              onClick={() => runDecision("accept")}
              disabled={busy}
              className="rounded-lg border border-emerald-200 bg-white px-2 py-2 text-[11px] font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
            >
              Accept selected
            </button>
            <button
              type="button"
              onClick={() => runDecision("reject")}
              disabled={busy}
              className="rounded-lg border border-red-200 bg-white px-2 py-2 text-[11px] font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              Reject selected
            </button>
            <button
              type="button"
              onClick={() =>
                runDecision("merge", {
                  correctedFeatureType: selectedFeatureType,
                  correctedGeometry: selectedOutlines[0]?.geometry,
                  correctionCoordinateSpace: "project_local",
                  reason: `Merged ${selectedCandidateIds.length} detections into reviewed outline ${selectedOutlines[0]?.label ?? "selected outline"}.`,
                })
              }
              disabled={busy || !mergeReady}
              title={mergeReady ? "Merge into the selected edited outline" : "Select two detections and exactly one edited outline"}
              className="rounded-lg border border-sky-200 bg-white px-2 py-2 text-[11px] font-semibold text-sky-800 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Merge outlines
            </button>
            <button
              type="button"
              onClick={() =>
                runDecision("split", {
                  correctedFeatureType: selectedFeatureType,
                  replacementGeometries: selectedOutlines.map((item) => item.geometry),
                  replacementFeatureTypes: selectedOutlines.map(() => selectedFeatureType),
                  correctionCoordinateSpace: "project_local",
                  reason: `Split one detection into ${selectedOutlines.length} reviewed user-drawn outlines.`,
                })
              }
              disabled={busy || !splitReady}
              title={splitReady ? "Split into the selected edited outlines" : "Select one detection and at least two edited outlines"}
              className="rounded-lg border border-sky-200 bg-white px-2 py-2 text-[11px] font-semibold text-sky-800 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Split outline
            </button>
          </div>
        </div>
      ) : null}

      {queueItems.length ? (
        <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <summary className="cursor-pointer text-xs font-semibold text-slate-700">Highest-value reviews</summary>
          <div className="mt-2 space-y-2">
            {queueItems.slice(0, 5).map((item) => (
              <div key={item.candidate_id} className="rounded-lg border border-slate-200 bg-white px-2.5 py-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-xs font-semibold text-slate-700">{item.label || friendlyClass(item.feature_type ?? "candidate")}</p>
                  <span className="text-[10px] font-semibold text-slate-500">Priority {Math.round(Number(item.priority_score ?? 0))}</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  {(item.reason_codes ?? []).slice(0, 3).map(reasonLabel).join(" · ")}
                </p>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <details className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <summary className="cursor-pointer text-xs font-semibold text-slate-700">Coverage by visual class</summary>
        <div className="mt-2 space-y-2">
          {coverageRows.map(([featureType, row]) => (
            <div key={featureType} className="rounded-lg border border-slate-200 bg-white px-2.5 py-2">
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="font-semibold text-slate-700">{friendlyClass(featureType)}</span>
                <span className={row.target_ready ? "font-semibold text-emerald-700" : "font-semibold text-amber-700"}>
                  {Number(row.reviewed_annotation_count ?? 0)} / {Number(row.target_annotation_count ?? 0)}
                </span>
              </div>
              {!row.target_ready ? (
                <p className="mt-1 text-[11px] text-slate-500">
                  {Number(row.geography_count ?? 0)} geographies · {Number(row.season_count ?? 0)} seasons · {Number(row.imagery_quality_band_count ?? 0)} quality bands
                </p>
              ) : null}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
