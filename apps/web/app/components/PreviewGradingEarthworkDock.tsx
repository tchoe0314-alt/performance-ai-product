import { useMemo, useState } from "react";
import type { GradingEarthworkUx } from "../types";

type PreviewGradingEarthworkDockProps = {
  gradingEarthworkUx: GradingEarthworkUx;
  formatMetric: (value: number | null, unit: string) => string;
};

export function PreviewGradingEarthworkDock({ gradingEarthworkUx, formatMetric }: PreviewGradingEarthworkDockProps) {
  const surfaceModel = gradingEarthworkUx.surfaceModel;
  const [view, setView] = useState<"existing" | "proposed" | "difference">("difference");
  const [selectedCellId, setSelectedCellId] = useState<string | null>(null);
  const cells = surfaceModel?.comparisonCells ?? [];
  const selectedCell = cells.find((cell) => cell.id === selectedCellId) ?? null;
  const cellLayout = useMemo(() => new Map(gradingEarthworkUx.heatmapCells.map((cell) => [cell.id, cell])), [gradingEarthworkUx.heatmapCells]);
  const elevationValues = cells.flatMap((cell) => [cell.existingElevationFt, cell.proposedElevationFt]);
  const elevationMin = elevationValues.length ? Math.min(...elevationValues) : 0;
  const elevationMax = elevationValues.length ? Math.max(...elevationValues) : 0;
  const elevationColor = (value: number) => {
    const ratio = elevationMax > elevationMin ? (value - elevationMin) / (elevationMax - elevationMin) : 0.5;
    return `hsl(${205 - ratio * 85} 55% ${78 - ratio * 22}%)`;
  };
  const cellColor = (cell: (typeof cells)[number]) => view === "existing"
    ? elevationColor(cell.existingElevationFt)
    : view === "proposed"
      ? elevationColor(cell.proposedElevationFt)
      : cell.mode === "cut" ? "rgba(225, 29, 72, .56)" : cell.mode === "fill" ? "rgba(14, 165, 233, .56)" : "rgba(16, 185, 129, .35)";

  return <>
    {cells.length ? <svg data-testid="grading-surface-comparison-layer" className="pointer-events-none absolute inset-0 z-[20] h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
      {cells.map((cell) => {
        const layout = cellLayout.get(cell.id);
        if (!layout) return null;
        return <rect key={cell.id} data-testid="grading-comparison-cell" data-mode={cell.mode} className="pointer-events-auto cursor-crosshair" x={layout.xPct} y={layout.yPct} width={layout.wPct} height={layout.hPct} fill={cellColor(cell)} stroke={selectedCellId === cell.id ? "#0f172a" : "rgba(255,255,255,.35)"} strokeWidth={selectedCellId === cell.id ? 0.55 : 0.12} onClick={() => setSelectedCellId(cell.id)} />;
      })}
    </svg> : null}
    <div data-testid="grading-earthwork-panel" className="civora-evidence-dock civora-grading-earthwork-dock civora-evidence-dock-left pointer-events-auto absolute bottom-4 left-4 z-[40] w-[min(380px,calc(100%-2rem))] rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-[0_18px_45px_-30px_rgba(15,23,42,0.85)] backdrop-blur">
      <div className="flex items-start justify-between gap-3">
        <div><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Grading / earthwork</p><p className="mt-1 font-semibold text-slate-900">{gradingEarthworkUx.surfaceComparison.deltaLabel}</p></div>
        <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5" aria-label="Surface view">
          {(["existing", "proposed", "difference"] as const).map((mode) => <button key={mode} type="button" data-testid={`grading-view-${mode}`} aria-pressed={view === mode} onClick={() => setView(mode)} className={`rounded-md px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.08em] ${view === mode ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>{mode}</button>)}
        </div>
      </div>
      <p className="mt-1 text-[10px] text-slate-500">Whole site · current calculated surface revision</p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {[["Excavation", gradingEarthworkUx.haulBalance.cutCf, "cf"], ["Fill", gradingEarthworkUx.haulBalance.fillCf, "cf"], ["Net", gradingEarthworkUx.haulBalance.netCf, "cf"]].map(([label, value, unit]) => <div key={label as string} className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5"><p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label as string}</p><p className="mt-0.5 font-semibold text-slate-800">{typeof value === "number" ? formatMetric(value, unit as string) : "Pending"}</p></div>)}
      </div>
      {selectedCell ? <div data-testid="grading-selected-area" className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
        <div className="flex items-center justify-between gap-2"><p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500">Selected cell</p><button type="button" className="text-[10px] font-semibold text-slate-500" onClick={() => setSelectedCellId(null)}>Clear</button></div>
        <div className="mt-1 grid grid-cols-3 gap-2 text-[11px]"><p>EG <strong>{selectedCell.existingElevationFt.toFixed(2)} ft</strong></p><p>FG <strong>{selectedCell.proposedElevationFt.toFixed(2)} ft</strong></p><p>Depth <strong>{selectedCell.deltaFt > 0 ? "+" : ""}{selectedCell.deltaFt.toFixed(2)} ft</strong></p></div>
        <p className="mt-1 text-[10px] text-slate-500">{selectedCell.deltaFt < 0 ? "Cut" : selectedCell.deltaFt > 0 ? "Fill" : "Balanced"} · selected-area excavation {formatMetric(selectedCell.cutCf, "cf")} · fill {formatMetric(selectedCell.fillCf, "cf")}</p>
      </div> : null}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.12em]"><span className="text-rose-700">■ Cut</span><span className="text-sky-700">■ Fill</span><span className="text-emerald-700">■ Balanced</span></div>
      {surfaceModel ? <p className="mt-2 text-[10px] font-medium text-slate-500">Source: {surfaceModel.sourceType || "surface"} · Control {surfaceModel.controlVerified ? "verified" : "not verified"}</p> : null}
      <p className="mt-1 text-[10px] font-medium text-amber-700">{gradingEarthworkUx.haulBalance.label}; no off-site quantity is shown.</p>
    </div>
  </>;
}
