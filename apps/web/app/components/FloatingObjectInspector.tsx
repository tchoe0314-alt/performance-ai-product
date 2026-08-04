import type { BuildingPlacement } from "../types";

type FloatingObjectConfidence = {
  confidence_band?: string;
  visible_badge?: string;
  why_low_confidence?: string;
  next_action?: string;
} | null;

type FloatingObjectInspectorProps = {
  selectedBuilding: BuildingPlacement;
  selectedObjectConfidence?: FloatingObjectConfidence;
  moveEditFeedback?: string;
  onEdit: () => void;
  onFocus: () => void;
  onOpenDetails: () => void;
};

export function FloatingObjectInspector({
  selectedBuilding,
  selectedObjectConfidence,
  moveEditFeedback,
  onEdit,
  onFocus,
  onOpenDetails,
}: FloatingObjectInspectorProps) {
  const hasHeight = typeof selectedBuilding.h === "number" && selectedBuilding.h > 0;
  const confidenceBadgeTone =
    selectedObjectConfidence?.confidence_band === "higher"
      ? "bg-emerald-50 text-emerald-700"
      : selectedObjectConfidence?.confidence_band === "review"
        ? "bg-amber-50 text-amber-700"
        : "bg-slate-100 text-slate-600";

  return (
    <div
      data-testid="floating-object-inspector"
      className="pointer-events-none absolute left-3 top-[9.75rem] z-[32] hidden w-[min(340px,calc(100vw-1.5rem))] rounded-xl border border-slate-200 bg-white/94 p-3 text-xs text-slate-600 shadow-[0_22px_70px_-42px_rgba(15,23,42,0.72)] backdrop-blur-xl sm:block lg:left-[272px] lg:top-[9rem]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-950">{selectedBuilding.label}</p>
          <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
            {selectedBuilding.type} · {selectedBuilding.placed ? "placed" : "not placed"}
          </p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${confidenceBadgeTone}`}>
          {selectedObjectConfidence?.visible_badge || selectedBuilding.source || "draft"}
        </span>
      </div>
      <div className={`pointer-events-auto mt-3 grid ${hasHeight ? "grid-cols-4" : "grid-cols-3"} gap-2`}>
        {[
          ["W", `${Math.round(selectedBuilding.w)} ft`],
          ["D", `${Math.round(selectedBuilding.d)} ft`],
          ...(hasHeight ? [["H", `${Math.round(selectedBuilding.h ?? 0)} ft`]] : []),
          ["Rot", `${Math.round(selectedBuilding.rotation ?? 0)}°`],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5">
            <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
            <p className="mt-0.5 font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      {selectedObjectConfidence?.why_low_confidence || selectedObjectConfidence?.next_action ? (
        <p className="mt-2 line-clamp-2 rounded-lg border border-amber-100 bg-amber-50 px-2 py-1.5 text-[11px] font-semibold text-amber-700">
          {selectedObjectConfidence.why_low_confidence || selectedObjectConfidence.next_action}
        </p>
      ) : null}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <button
          type="button"
          onClick={onEdit}
          data-testid="selected-object-edit-button"
          className="rounded-lg border border-slate-950 bg-slate-950 px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-white"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={onFocus}
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Focus
        </button>
        <button
          type="button"
          onClick={onOpenDetails}
          className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
        >
          Details
        </button>
      </div>
      {moveEditFeedback ? (
        <p data-testid="selected-object-move-edit-feedback" className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-[11px] font-semibold text-slate-700">
          {moveEditFeedback}
        </p>
      ) : null}
    </div>
  );
}
