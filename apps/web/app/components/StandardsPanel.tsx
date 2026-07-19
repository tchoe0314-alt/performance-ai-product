import { PanelCard } from "./ui";

export type StandardsPanelRow = {
  key: string;
  label: string;
  status: string;
  value: string;
  exactFix: string;
};

export type StandardsCriterion = {
  label: string;
  value: string;
};

export function StandardsPanel({
  criteria,
  rows,
  onOpenSourceData,
  onOpenReviewGates,
}: {
  criteria: StandardsCriterion[];
  rows: StandardsPanelRow[];
  onOpenSourceData: () => void;
  onOpenReviewGates: () => void;
}) {
  return (
    <div className="space-y-4">
      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Active criteria</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {criteria.map((item) => (
            <div key={item.label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{item.label}</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{item.value}</p>
            </div>
          ))}
        </div>
      </PanelCard>
      <PanelCard>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Standards source registry</p>
        <div className="mt-3 space-y-2 text-sm font-semibold text-slate-700">
          {rows.map((item) => (
            <div key={item.key} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="flex items-start justify-between gap-3">
                <span>{item.label}</span>
                <span
                  className={`text-right text-[10px] uppercase tracking-[0.12em] ${
                    item.status === "block" ? "text-red-600" : item.status === "idle" ? "text-slate-400" : "text-amber-600"
                  }`}
                >
                  {item.value}
                </span>
              </div>
              {item.status === "block" || item.status === "idle" ? (
                <p className="mt-1 text-xs font-medium normal-case tracking-normal text-slate-500">
                  {item.exactFix}
                </p>
              ) : null}
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onOpenSourceData}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Source data
          </button>
          <button
            type="button"
            onClick={onOpenReviewGates}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Review gates
          </button>
        </div>
      </PanelCard>
    </div>
  );
}
