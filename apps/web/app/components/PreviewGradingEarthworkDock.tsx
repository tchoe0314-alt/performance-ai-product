import type { GradingEarthworkUx } from "../types";

type PreviewGradingEarthworkDockProps = {
  gradingEarthworkUx: GradingEarthworkUx;
  formatMetric: (value: number | null, unit: string) => string;
};

export function PreviewGradingEarthworkDock({
  gradingEarthworkUx,
  formatMetric,
}: PreviewGradingEarthworkDockProps) {
  const surfaceModel = gradingEarthworkUx.surfaceModel;

  return (
    <div
      data-testid="grading-earthwork-panel"
      className="civora-evidence-dock civora-evidence-dock-left pointer-events-none absolute bottom-4 left-4 z-[24] w-[min(360px,calc(100%-2rem))] rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-[0_18px_45px_-30px_rgba(15,23,42,0.85)] backdrop-blur"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            Grading / earthwork
          </p>
          <p className="mt-1 font-semibold text-slate-900">
            {gradingEarthworkUx.surfaceComparison.deltaLabel}
          </p>
        </div>
        <span
          className={`rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
            gradingEarthworkUx.haulBalance.direction === "export"
              ? "border-rose-200 bg-rose-50 text-rose-700"
              : gradingEarthworkUx.haulBalance.direction === "import"
                ? "border-sky-200 bg-sky-50 text-sky-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-700"
          }`}
        >
          {gradingEarthworkUx.haulBalance.label}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {[
          ["Cut", gradingEarthworkUx.haulBalance.cutCf, "cf"],
          ["Fill", gradingEarthworkUx.haulBalance.fillCf, "cf"],
          ["Net", gradingEarthworkUx.haulBalance.netCf, "cf"],
        ].map(([label, value, unit]) => (
          <div key={label as string} className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5">
            <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
              {label as string}
            </p>
            <p className="mt-0.5 font-semibold text-slate-800">
              {typeof value === "number" ? formatMetric(value, unit as string) : "Pending"}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white px-2 py-2">
          <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
            Surface comparison
          </p>
          <p className="mt-1 text-[11px] font-semibold text-slate-700">
            {gradingEarthworkUx.surfaceComparison.existing} to {gradingEarthworkUx.surfaceComparison.proposed}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-2 py-2">
          <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
            Wall trigger
          </p>
          <p className="mt-1 text-[11px] font-semibold text-slate-700">
            {gradingEarthworkUx.retainingWall.label}
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.12em]">
        <span className="inline-flex items-center gap-1 text-rose-700">
          <span className="h-2 w-2 rounded-sm bg-rose-500/70" />
          Cut
        </span>
        <span className="inline-flex items-center gap-1 text-sky-700">
          <span className="h-2 w-2 rounded-sm bg-sky-500/70" />
          Fill
        </span>
        <span className="inline-flex items-center gap-1 text-emerald-700">
          <span className="h-2 w-2 rounded-sm bg-emerald-500/70" />
          Balanced
        </span>
        {surfaceModel ? (
          <span className="inline-flex items-center gap-1 text-teal-700">
            <span className="h-2 w-2 rounded-sm bg-teal-600/70" />
            {surfaceModel.model?.toUpperCase() || "SURFACE"}
          </span>
        ) : null}
      </div>
      {surfaceModel ? (
        <p className="mt-2 text-[10px] font-medium text-slate-500">
          Source: {surfaceModel.sourceType || "surface"} · Control {surfaceModel.controlVerified ? "verified" : "not verified"}
        </p>
      ) : null}
    </div>
  );
}
