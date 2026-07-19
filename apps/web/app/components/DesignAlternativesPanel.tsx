import type { DesignAlternative, DesignAlternativesV1 } from "../types";

export type DesignAlternativeAction = "generate" | "compare" | "revise" | "choose" | "merge";

export function DesignAlternativesPanel({
  designAlternatives,
  alternatives,
  topAlternative,
  selectedAlternativeId,
  quantityAvailable,
  onAction,
}: {
  designAlternatives: DesignAlternativesV1;
  alternatives: DesignAlternative[];
  topAlternative: DesignAlternative | null;
  selectedAlternativeId: string;
  quantityAvailable: boolean;
  onAction: (action: DesignAlternativeAction, optionNumber?: number) => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="design-alternatives-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Design Alternatives</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">
            {topAlternative?.label || "Generate review-required concepts"}
          </p>
          <p className="mt-1 text-xs font-medium text-slate-500">
            Parking, circulation, basin, utility, grading/drainage, and organization options.
          </p>
        </div>
        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
          Review required
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        {[
          ["Options", designAlternatives.alternative_count ?? alternatives.length],
          ["Accepted inputs", designAlternatives.accepted_input_summary?.accepted_candidate_count ?? 0],
          ["Trusted sources", designAlternatives.accepted_input_summary?.trusted_source_count ?? 0],
          ["Quantities", quantityAvailable ? "available" : "not yet"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onAction("generate")}
          className="rounded-lg border border-slate-900 bg-slate-950 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-white hover:bg-slate-800"
        >
          Show 3 Options
        </button>
        <button
          type="button"
          onClick={() => onAction("compare")}
          disabled={!alternatives.length}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Compare
        </button>
        <button
          type="button"
          onClick={() => onAction("revise", Number(topAlternative?.option_number ?? 1))}
          disabled={!alternatives.length}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Another Layout
        </button>
      </div>
      <div className="mt-3 space-y-2">
        {alternatives.length ? (
          alternatives.slice(0, 5).map((alternative) => {
            const selected = selectedAlternativeId === alternative.alternative_id;
            const quantityDeltas = Object.entries(alternative.cost_quantity_comparison?.estimated_review_deltas ?? {});
            return (
              <div key={alternative.alternative_id} className={`rounded-xl border px-3 py-3 ${selected ? "border-slate-900 bg-slate-50" : "border-slate-200 bg-slate-50"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-800">
                      {alternative.label || `Option ${alternative.option_number ?? ""}`}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs font-medium text-slate-500">
                      {alternative.summary || "Review-required concept."}
                    </p>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${selected ? "bg-slate-900 text-white" : "bg-amber-50 text-amber-700"}`}>
                    {selected ? "selected" : `${Number(alternative.scoring?.review_score ?? 0)} score`}
                  </span>
                </div>
                <div className="mt-2 grid gap-2 text-xs sm:grid-cols-3">
                  {(alternative.tradeoffs ?? []).slice(0, 3).map((tradeoff) => (
                    <p key={tradeoff} className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-medium text-slate-600">
                      {tradeoff}
                    </p>
                  ))}
                </div>
                {quantityDeltas.length ? (
                  <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
                    {quantityDeltas.slice(0, 4).map(([key, delta]) => (
                      <p key={key} className="rounded-lg border border-slate-200 bg-white px-2 py-2 font-medium text-slate-600">
                        <span className="font-semibold text-slate-400">{key.replaceAll("_", " ")} </span>
                        {Number(delta.delta ?? 0) >= 0 ? "+" : ""}{Number(delta.delta ?? 0).toLocaleString()}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs font-medium text-slate-500">
                    {alternative.cost_quantity_comparison?.reason || "Cost/quantity comparison appears when quantities are available."}
                  </p>
                )}
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => onAction("choose", alternative.option_number)}
                    disabled={selected}
                    className="rounded-lg border border-emerald-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Use Option
                  </button>
                  <button
                    type="button"
                    onClick={() => onAction("merge", alternative.option_number)}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
                  >
                    Merge/Revise
                  </button>
                </div>
              </div>
            );
          })
        ) : (
          <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
            Ask “show me 3 options” or use the button above to generate concept alternatives.
          </p>
        )}
      </div>
      <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
        {designAlternatives.truth_label || "Alternatives are concepts for review only unless supported by accepted inputs."}
      </p>
    </div>
  );
}
