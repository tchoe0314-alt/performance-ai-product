export type QuantityReviewStatusView = "ok" | "review" | "reference" | "missing_cost" | "untraced" | "stale";

export type QuantityReviewRowView = {
  metric: string;
  label: string;
  quantity: number;
  unit: string;
  canonicalIds: string[];
  sourceIds: string[];
  sourceStage: string;
  sourceLayer: string;
  method: string;
  confidence: string;
  costApplicable: boolean;
  traceRequired: boolean;
  traceComplete: boolean;
  delta: number | null;
  previousQuantity: number | null;
  currentQuantity: number | null;
  costItem: string;
  unitCost: number | null;
  amount: number | null;
  currency: string;
  priceSource: string;
  priceSourceItemId: string;
  productionPrice: boolean;
  missingCost: boolean;
  status: QuantityReviewStatusView;
};

export type ConstructionTakeoffView = {
  earthwork?: {
    cut_cy?: number | null;
    fill_cy?: number | null;
    unit?: string;
    status?: string;
    haul_quantity_inferred?: boolean;
  };
  pipes_by_system_and_diameter?: Array<{
    system?: string;
    diameter_in?: number | null;
    measurement_basis?: string;
    horizontal_length_ft?: number;
    three_dimensional_length_ft?: number | null;
    source_object_ids?: string[];
    unit?: string;
    rate_provenance?: { status?: string; unit_rate?: number | null; currency?: string | null; source?: string | null };
  }>;
  structures_by_system_and_type?: Array<{
    system?: string;
    structure_type?: string;
    count?: number;
    source_object_ids?: string[];
    unit?: string;
  }>;
};

export function QuantitiesPanel({
  rows,
  staleSystemCount,
  trustScoreLabel,
  onExportReport,
  formatMetric,
  statusLabelForQuantityReview,
  outdated = false,
  calculationReference,
  constructionTakeoff,
}: {
  rows: QuantityReviewRowView[];
  staleSystemCount: number;
  trustScoreLabel: string;
  onExportReport: () => void;
  formatMetric: (value: number | null, unit: string) => string;
  statusLabelForQuantityReview: (status: QuantityReviewStatusView) => string;
  outdated?: boolean;
  calculationReference?: string;
  constructionTakeoff?: ConstructionTakeoffView;
}) {
  const isOutdated = outdated || staleSystemCount > 0 || rows.some(row => row.status === "stale");
  const hasMissingCost = rows.some((row) => row.missingCost);
  const hasMissingTrace = rows.some((row) => row.status === "untraced");
  const hasDelta = rows.some((row) => row.delta !== null);
  const statusLabel = isOutdated ? "Out of date" : hasMissingCost ? "Cost gaps" : trustScoreLabel;
  const statusClass =
    hasMissingCost || hasMissingTrace
      ? "bg-red-50 text-red-600"
      : isOutdated || hasDelta
        ? "bg-amber-50 text-amber-700"
        : "bg-slate-100 text-slate-600";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Quantity takeoff</p>
          <p data-testid="quantity-calculation-source" className="mt-1 text-xs text-slate-500">{isOutdated ? "Previous calculation. Recalculate for current totals." : calculationReference ? `Calculation: ${calculationReference}` : "Calculation version unverified."}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${statusClass}`}>
            {statusLabel}
          </span>
          <button
            type="button"
            onClick={onExportReport}
            disabled={!rows.length || isOutdated}
            className="rounded-xl border border-slate-900 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
          >
            Export report
          </button>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
        {[
          ["Rows", rows.length.toLocaleString()],
          ["Missing cost", rows.filter((row) => row.missingCost).length.toLocaleString()],
          ["Untraced", rows.filter((row) => row.traceRequired && !row.traceComplete).length.toLocaleString()],
          ["Reference", rows.filter((row) => row.status === "reference").length.toLocaleString()],
          ["Deltas", rows.filter((row) => row.delta !== null && Math.abs(row.delta) > 0.0001).length.toLocaleString()],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-base font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200">
        <table className="min-w-[760px] w-full border-collapse text-left text-xs">
          <thead className="bg-slate-50 text-[10px] uppercase tracking-[0.12em] text-slate-500">
            <tr>
              <th className="px-3 py-2 font-semibold">Quantity</th>
              <th className="px-3 py-2 font-semibold">Trace</th>
              <th className="px-3 py-2 font-semibold">Delta after edits</th>
              <th className="px-3 py-2 font-semibold">Cost mapping</th>
              <th className="px-3 py-2 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {rows.map((row) => (
              <tr key={row.metric} className="align-top">
                <td className="px-3 py-3">
                  <p className="font-semibold text-slate-900">{row.label}</p>
                  <p className="mt-1 font-semibold text-slate-700">{formatMetric(row.quantity, row.unit)}</p>
                  <p className="mt-1 break-all text-[11px] text-slate-400">{row.metric}</p>
                </td>
                <td className="px-3 py-3">
                  <p className="font-semibold text-slate-700">{row.sourceStage}</p>
                  <p className="mt-1 text-slate-500">{row.sourceLayer} / {row.method}</p>
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600">
                      Source / canonical IDs
                    </summary>
                    <div className="mt-2 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
                      <p className="break-all">
                        <span className="font-semibold text-slate-700">Canonical:</span>{" "}
                        {row.canonicalIds.length ? row.canonicalIds.join(", ") : "Missing"}
                      </p>
                      <p className="break-all">
                        <span className="font-semibold text-slate-700">Source:</span>{" "}
                        {row.sourceIds.length ? row.sourceIds.join(", ") : "Missing"}
                      </p>
                    </div>
                  </details>
                </td>
                <td className="px-3 py-3">
                  {row.delta !== null ? (
                    <>
                      <p className={`font-semibold ${row.delta > 0 ? "text-emerald-700" : row.delta < 0 ? "text-red-600" : "text-slate-700"}`}>
                        {row.delta > 0 ? "+" : ""}{formatMetric(row.delta, row.unit)}
                      </p>
                      <p className="mt-1 text-slate-500">
                        {row.previousQuantity !== null ? formatMetric(row.previousQuantity, row.unit) : "Previous pending"}
                        {" -> "}
                        {formatMetric(row.currentQuantity ?? row.quantity, row.unit)}
                      </p>
                    </>
                  ) : (
                    <p className="font-semibold text-slate-400">No edit delta recorded</p>
                  )}
                </td>
                <td className="px-3 py-3">
                  <p className="font-semibold text-slate-900">{row.costItem}</p>
                  <p className="mt-1 text-slate-600">
                    {row.unitCost !== null
                      ? `${row.currency} ${row.unitCost.toLocaleString()} / ${row.unit}`
                      : row.costApplicable
                        ? "No unit cost"
                        : "Not priced separately"}
                  </p>
                  <p className="mt-1 text-slate-500">
                    {row.amount !== null
                      ? `${row.currency} ${row.amount.toLocaleString()}`
                      : row.costApplicable
                        ? "Amount pending"
                        : "Reference quantity"}
                  </p>
                  <p className="mt-1 break-all text-[11px] text-slate-400">
                    {row.priceSourceItemId || row.priceSource}
                  </p>
                </td>
                <td className="px-3 py-3">
                  <span className={`inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    row.status === "missing_cost" || row.status === "untraced"
                      ? "bg-red-50 text-red-600"
                      : row.status === "stale" || row.status === "review"
                        ? "bg-amber-50 text-amber-700"
                        : row.status === "reference"
                          ? "bg-slate-100 text-slate-600"
                          : "bg-emerald-50 text-emerald-700"
                  }`}>
                    {statusLabelForQuantityReview(row.status)}
                  </span>
                  <p className="mt-2 text-[11px] text-slate-500">
                    {row.missingCost
                      ? "Needs unit-price book mapping."
                      : !row.costApplicable
                        ? "Reference total; not a separate cost line."
                      : row.traceComplete
                        ? "Traceable to canonical model."
                        : "Missing canonical source ID."}
                  </p>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? (
          <p className="p-4 text-sm font-semibold text-slate-500">
            {staleSystemCount
              ? "Run or refresh the stale systems to calculate traceable quantities."
              : "No traceable quantity result was produced. Review generation inputs and run the required systems again."}
          </p>
        ) : null}
      </div>
      {constructionTakeoff ? (
        <div data-testid="construction-takeoff-breakdown" className="mt-3 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs">
          <div>
            <p className="font-semibold uppercase tracking-[0.14em] text-slate-500">Construction breakdown</p>
            <p className="mt-1 text-slate-500">Review quantities preserve each source measurement basis; they do not establish a universal bid basis.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="font-semibold text-slate-700">Earthwork cut</p>
              <p className="mt-1 text-base font-semibold text-slate-900">{formatMetric(constructionTakeoff.earthwork?.cut_cy ?? null, "cy")}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="font-semibold text-slate-700">Earthwork fill</p>
              <p className="mt-1 text-base font-semibold text-slate-900">{formatMetric(constructionTakeoff.earthwork?.fill_cy ?? null, "cy")}</p>
            </div>
          </div>
          <p className="text-[11px] text-slate-500">Haul quantity: not inferred from cut/fill totals.</p>
          {(constructionTakeoff.pipes_by_system_and_diameter ?? []).map((pipe, index) => (
            <div key={`${pipe.system}-${pipe.diameter_in}-${pipe.measurement_basis}-${index}`} className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="font-semibold text-slate-900">{pipe.system || "Unknown system"} · {pipe.diameter_in ?? "Unknown"} in</p>
              <p className="mt-1 text-slate-700">Horizontal: {formatMetric(pipe.horizontal_length_ft ?? null, "ft")}</p>
              <p className="mt-1 text-slate-700">3D: {pipe.three_dimensional_length_ft == null ? "Not reported" : formatMetric(pipe.three_dimensional_length_ft, "ft")}</p>
              <p className="mt-1 break-all text-[11px] text-slate-500">Basis: {pipe.measurement_basis || "Unspecified"} · Sources: {(pipe.source_object_ids ?? []).join(", ") || "Missing"}</p>
              <p className="mt-1 break-all text-[11px] text-slate-500">Rate: {pipe.rate_provenance?.status === "source_provided" ? `${pipe.rate_provenance.currency || "USD"} ${pipe.rate_provenance.unit_rate} / ${pipe.unit || "ft"} · ${pipe.rate_provenance.source}` : "Missing — no group rate applied"}</p>
            </div>
          ))}
          {(constructionTakeoff.structures_by_system_and_type ?? []).length ? (
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <p className="font-semibold text-slate-900">Distinct structures</p>
              {(constructionTakeoff.structures_by_system_and_type ?? []).map((structure, index) => (
                <p key={`${structure.system}-${structure.structure_type}-${index}`} className="mt-1 text-slate-700">
                  {structure.system || "Unknown system"} · {structure.structure_type || "structure"}: {structure.count ?? 0}
                </p>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
