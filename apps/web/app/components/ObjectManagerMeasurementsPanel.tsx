type ObjectManagerMeasurement = {
  id: string;
  label: string;
  typeLabel: string;
  lengthFt: number;
  areaSf: number;
  widthFt: number;
  depthFt: number;
};

type ObjectManagerMeasurementSummary = {
  count: number;
  totalLengthFt: number;
  totalAreaSf: number;
  widthFt: number;
  depthFt: number;
};

type ObjectManagerMeasurementsPanelProps = {
  summary: ObjectManagerMeasurementSummary | null;
  measurements: ObjectManagerMeasurement[];
};

const formatDraftMeasure = (value: number, unit: "ft" | "sf" | "deg") => {
  if (!Number.isFinite(value)) return `0 ${unit}`;
  const rounded = Math.abs(value) >= 100 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded.toLocaleString()} ${unit}`;
};

export function ObjectManagerMeasurementsPanel({ summary, measurements }: ObjectManagerMeasurementsPanelProps) {
  if (!summary) return null;

  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3" data-testid="object-manager-measurements">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Measurements
          </p>
          <p className="mt-1 text-xs font-medium text-slate-500">
            Draft readout only. Review dimensions before using them outside Civora.
          </p>
        </div>
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          {summary.count} selected
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <div className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
          <span className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Total length</span>
          <span className="mt-1 block font-semibold text-slate-800" data-testid="object-manager-measure-total-length">
            {formatDraftMeasure(summary.totalLengthFt, "ft")}
          </span>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
          <span className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Total area</span>
          <span className="mt-1 block font-semibold text-slate-800" data-testid="object-manager-measure-total-area">
            {formatDraftMeasure(summary.totalAreaSf, "sf")}
          </span>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
          <span className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Overall width</span>
          <span className="mt-1 block font-semibold text-slate-800" data-testid="object-manager-measure-width">
            {formatDraftMeasure(summary.widthFt, "ft")}
          </span>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
          <span className="block text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Overall depth</span>
          <span className="mt-1 block font-semibold text-slate-800" data-testid="object-manager-measure-depth">
            {formatDraftMeasure(summary.depthFt, "ft")}
          </span>
        </div>
      </div>
      <div className="mt-2 max-h-32 space-y-1 overflow-y-auto pr-1" data-testid="object-manager-measurement-list">
        {measurements.slice(0, 8).map((item) => (
          <div key={`measurement-${item.id}`} className="grid grid-cols-[1fr_auto] gap-2 rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2 text-[11px]">
            <div className="min-w-0">
              <p className="truncate font-semibold text-slate-800">{item.label}</p>
              <p className="mt-0.5 text-slate-500">
                {item.typeLabel} · {formatDraftMeasure(item.widthFt, "ft")} x {formatDraftMeasure(item.depthFt, "ft")}
              </p>
            </div>
            <div className="shrink-0 text-right font-semibold text-slate-600">
              {item.areaSf > 0 ? formatDraftMeasure(item.areaSf, "sf") : formatDraftMeasure(item.lengthFt, "ft")}
            </div>
          </div>
        ))}
        {measurements.length > 8 ? (
          <p className="px-2 text-[11px] font-medium text-slate-500">
            {measurements.length - 8} more selected object{measurements.length - 8 === 1 ? "" : "s"} included in totals.
          </p>
        ) : null}
      </div>
    </div>
  );
}
