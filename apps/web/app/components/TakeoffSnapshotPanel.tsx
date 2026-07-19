import type { QuantityReviewRowView, QuantityReviewStatusView } from "./QuantitiesPanel";

export function TakeoffSnapshotPanel({
  rows,
  formatMetric,
  statusLabelForQuantityReview,
}: {
  rows: QuantityReviewRowView[];
  formatMetric: (value: number | null, unit: string) => string;
  statusLabelForQuantityReview: (status: QuantityReviewStatusView) => string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Takeoff snapshot</p>
      <div className="mt-3 space-y-2 text-sm text-slate-700">
        {rows.slice(0, 4).map((row) => (
          <div key={row.label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <span className="font-semibold">{row.label}</span>
            <span className="text-right">
              <span className="block">{formatMetric(row.quantity, row.unit)}</span>
              <span className={`text-[10px] font-semibold uppercase tracking-[0.12em] ${
                row.status === "missing_cost" || row.status === "untraced" ? "text-red-600" : "text-slate-500"
              }`}>
                {statusLabelForQuantityReview(row.status)}
              </span>
            </span>
          </div>
        ))}
        {!rows.length ? (
          <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
            Run systems to populate quantities.
          </p>
        ) : null}
      </div>
    </div>
  );
}
