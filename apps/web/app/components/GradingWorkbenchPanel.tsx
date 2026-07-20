import type { GradingEarthworkUx } from "../types";
import type { SystemStatus } from "../utils/workflowConstants";

type GradingWorkbenchPanelProps = {
  hasTerrainSource: boolean;
  hasGradingSurface: boolean;
  siteTooLargeForGrading: boolean;
  gradingStatus: SystemStatus;
  useSurveyForGrading: boolean;
  onUseSurveyForGradingChange: (enabled: boolean) => void;
  minSlopePct: string;
  maxParkingSlopePct: string;
  maxRoadGradePct: string;
  maxAdaCrossSlopePct: string;
  onMinSlopePctChange: (value: string) => void;
  onMaxParkingSlopePctChange: (value: string) => void;
  onMaxRoadGradePctChange: (value: string) => void;
  onMaxAdaCrossSlopePctChange: (value: string) => void;
  drainageAllowSlopeAdjust: boolean;
  onDrainageAllowSlopeAdjustChange: (enabled: boolean) => void;
  gradingEarthworkUx: GradingEarthworkUx;
  missingSite: boolean;
  onOpenAnalysis: () => void;
  onGenerateGrading: () => void;
};

export function GradingWorkbenchPanel({
  hasTerrainSource,
  hasGradingSurface,
  siteTooLargeForGrading,
  gradingStatus,
  useSurveyForGrading,
  onUseSurveyForGradingChange,
  minSlopePct,
  maxParkingSlopePct,
  maxRoadGradePct,
  maxAdaCrossSlopePct,
  onMinSlopePctChange,
  onMaxParkingSlopePctChange,
  onMaxRoadGradePctChange,
  onMaxAdaCrossSlopePctChange,
  drainageAllowSlopeAdjust,
  onDrainageAllowSlopeAdjustChange,
  gradingEarthworkUx,
  missingSite,
  onOpenAnalysis,
  onGenerateGrading,
}: GradingWorkbenchPanelProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Terrain", hasTerrainSource ? "Ready" : "Missing"],
          ["Surface", hasGradingSurface ? "Rendered" : "Not rendered"],
          ["Status", siteTooLargeForGrading ? "Needs input / review" : gradingStatus === "fresh" ? "Complete" : "Not configured"],
          ["Source", useSurveyForGrading ? "Survey / terrain" : "Manual"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Grading rules</p>
        <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
          <span>Use survey/terrain for grading</span>
          <input
            type="checkbox"
            checked={useSurveyForGrading}
            onChange={(event) => onUseSurveyForGradingChange(event.target.checked)}
            className="h-4 w-4 accent-slate-950"
          />
        </label>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {[
            ["Min slope %", minSlopePct, onMinSlopePctChange],
            ["Max parking %", maxParkingSlopePct, onMaxParkingSlopePctChange],
            ["Max road %", maxRoadGradePct, onMaxRoadGradePctChange],
            ["ADA cross %", maxAdaCrossSlopePct, onMaxAdaCrossSlopePctChange],
          ].map(([label, value, setter]) => (
            <label key={label as string} className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              {label as string}
              <input
                value={value as string}
                onChange={(event) => (setter as (next: string) => void)(event.target.value)}
                placeholder="Auto"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-700"
              />
            </label>
          ))}
        </div>
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Constructability controls</p>
          <div className="mt-2 space-y-2 text-sm font-semibold text-slate-700">
            <div className="flex items-center justify-between gap-3">
              <span>Drain away from pads</span>
              <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                Reviewed in grading run
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Respect ADA paths</span>
              <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                Review required
              </span>
            </div>
            <label className="flex items-center justify-between gap-3">
              <span>Repair local low points</span>
              <input
                type="checkbox"
                checked={drainageAllowSlopeAdjust}
                onChange={(event) => onDrainageAllowSlopeAdjustChange(event.target.checked)}
                className="h-4 w-4 accent-slate-950"
              />
            </label>
          </div>
        </div>
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Earthwork UX</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {[
              ["Heatmap", `${gradingEarthworkUx.heatmapCells.filter((cell) => cell.mode === "cut").length} cut / ${gradingEarthworkUx.heatmapCells.filter((cell) => cell.mode === "fill").length} fill`],
              ["Surface compare", gradingEarthworkUx.surfaceComparison.deltaLabel],
              ["Pad tie-ins", `${gradingEarthworkUx.padTieIns.filter((pad) => pad.status !== "ok").length} review`],
              ["Haul balance", gradingEarthworkUx.haulBalance.label],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-white px-2 py-2">
                <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <p className="mt-1 text-[11px] font-semibold text-slate-700">{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-2 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-600">
            <p className="font-semibold text-slate-800">{gradingEarthworkUx.retainingWall.label}</p>
            <p className="mt-1">{gradingEarthworkUx.retainingWall.tradeoff}</p>
          </div>
        </div>
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Outputs</p>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
            {["2-ft contours", "Spot elevations", "ADA slope check", "Pad tie-ins"].map((label) => (
              <span key={label} className="rounded-lg border border-slate-200 bg-white px-2 py-2">{label}</span>
            ))}
          </div>
          <button
            type="button"
            onClick={onOpenAnalysis}
            className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
          >
            Review grading issues
          </button>
        </div>
        <button
          type="button"
          onClick={onGenerateGrading}
          disabled={missingSite || !hasTerrainSource || siteTooLargeForGrading}
          className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
        >
          Generate grading
        </button>
      </div>
    </div>
  );
}
