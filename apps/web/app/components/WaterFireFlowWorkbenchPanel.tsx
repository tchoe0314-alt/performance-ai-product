import type { BuildingPlacement, SiteObjectType } from "../types";
import type { SystemStatus } from "../utils/workflowConstants";

type WaterFireFlowBlockerCard = {
  id: string;
  source: string;
  title: string;
  nextAction: string;
  severity: string;
};

type WaterFireFlowReview = {
  hydrants: Array<unknown>;
  pressureZones: Array<unknown>;
  networkSegments: Array<Record<string, unknown>>;
  scenarios: Array<Record<string, unknown> & { id?: string; label?: string; status?: string; missing_inputs?: string[] }>;
  spacingChecks: Array<Record<string, unknown> & { from?: string; to?: string; valid?: boolean }>;
  blockerCards: WaterFireFlowBlockerCard[];
  readiness: {
    status?: string;
  };
  checkRows: string[][];
};

type WaterFireFlowWorkbenchPanelProps = {
  hasHardSystemBlock: boolean;
  systemUtilitiesStatus: SystemStatus;
  waterFireFlowReview: WaterFireFlowReview;
  buildingPlacements: BuildingPlacement[];
  utilities: boolean;
  onUtilitiesChange: (enabled: boolean) => void;
  onAddObject: (type: SiteObjectType) => void;
  onGenerateUtilities: () => void;
};

function formatValue(value: unknown, suffix = "", digits = 0) {
  const next = typeof value === "number" ? value : Number(value);
  return Number.isFinite(next) ? `${next.toFixed(digits)}${suffix}` : "Missing";
}

function statusTone(value: string) {
  if (value === "Pass") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (value === "Needs evidence") return "border-rose-200 bg-rose-50 text-rose-800";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

export function WaterFireFlowWorkbenchPanel({
  hasHardSystemBlock,
  systemUtilitiesStatus,
  waterFireFlowReview,
  buildingPlacements,
  utilities,
  onUtilitiesChange,
  onAddObject,
  onGenerateUtilities,
}: WaterFireFlowWorkbenchPanelProps) {
  return (
    <div className="space-y-4" data-testid="water-fire-flow-workbench">
      <div className="grid grid-cols-2 gap-2">
        {[
          [
            "Status",
            hasHardSystemBlock
              ? "Needs input / review"
              : waterFireFlowReview.readiness.status || (systemUtilitiesStatus === "fresh" ? "Review" : "Not configured"),
          ],
          ["Hydrants", waterFireFlowReview.hydrants.length || buildingPlacements.filter((item) => item.type === "hydrant").length],
          ["Pressure zones", waterFireFlowReview.pressureZones.length || "Missing"],
          ["Blockers", waterFireFlowReview.blockerCards.length],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Water / fire-flow workbench</p>
            <p className="mt-1 text-xs font-semibold text-slate-600">Engineer review required for all outputs.</p>
          </div>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            Evidence-led
          </span>
        </div>
        <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
          <span>Include water network</span>
          <input
            type="checkbox"
            checked={utilities}
            onChange={(event) => onUtilitiesChange(event.target.checked)}
            className="h-4 w-4 accent-slate-950"
          />
        </label>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold text-slate-700">
          {waterFireFlowReview.checkRows.map(([label = "Check", value = "Review"]) => (
            <div key={label} className={`rounded-xl border px-3 py-2 ${statusTone(value)}`}>
              <p className="text-[10px] uppercase tracking-[0.12em] opacity-75">{label}</p>
              <p className="mt-1">{value}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button type="button" onClick={() => onAddObject("hydrant")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
            Add hydrant
          </button>
          <button type="button" onClick={onGenerateUtilities} className="rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800">
            Run water review
          </button>
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Map / table output</p>
        <div className="mt-3 max-h-48 overflow-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-[11px]">
            <thead className="sticky top-0 bg-slate-50 text-slate-500">
              <tr>
                <th className="px-2 py-1.5">Main</th>
                <th className="px-2 py-1.5">Type</th>
                <th className="px-2 py-1.5">Velocity</th>
                <th className="px-2 py-1.5">End psi</th>
              </tr>
            </thead>
            <tbody>
              {waterFireFlowReview.networkSegments.length ? (
                waterFireFlowReview.networkSegments.slice(0, 8).map((segment) => (
                  <tr key={String(segment.id)} className="border-t border-slate-100">
                    <td className="px-2 py-1.5 font-semibold text-slate-900">{String(segment.label || segment.id)}</td>
                    <td className="px-2 py-1.5 capitalize">{String(segment.network_type || "review").replace("_", " ")}</td>
                    <td className="px-2 py-1.5">{formatValue(segment.velocity_fps, " fps", 1)}</td>
                    <td className="px-2 py-1.5">{formatValue(segment.end_pressure_psi, " psi", 1)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-2 py-4 text-slate-500">No water-main segment evidence is recorded yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="mt-3 max-h-40 overflow-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-[11px]">
            <thead className="sticky top-0 bg-slate-50 text-slate-500">
              <tr>
                <th className="px-2 py-1.5">Hydrants</th>
                <th className="px-2 py-1.5">Spacing</th>
                <th className="px-2 py-1.5">Limit</th>
                <th className="px-2 py-1.5">Check</th>
              </tr>
            </thead>
            <tbody>
              {waterFireFlowReview.spacingChecks.length ? (
                waterFireFlowReview.spacingChecks.map((row, index) => (
                  <tr key={`${row.from || "from"}-${row.to || "to"}-${index}`} className="border-t border-slate-100">
                    <td className="px-2 py-1.5 font-semibold text-slate-900">{row.from || "Hydrant"} to {row.to || "Hydrant"}</td>
                    <td className="px-2 py-1.5">{formatValue(row.spacing_ft, " ft", 1)}</td>
                    <td className="px-2 py-1.5">{formatValue(row.limit_ft, " ft", 1)}</td>
                    <td className={`px-2 py-1.5 font-semibold ${row.valid ? "text-emerald-700" : "text-rose-700"}`}>{row.valid ? "Pass" : "Needs evidence"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-2 py-4 text-slate-500">Hydrant spacing rows are missing.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Fire-flow scenarios</p>
        <div className="mt-2 space-y-2">
          {waterFireFlowReview.scenarios.length ? (
            waterFireFlowReview.scenarios.map((scenario) => (
              <div key={String(scenario.id)} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-900">{String(scenario.label)}</span>
                  <span className="font-semibold uppercase text-slate-500">{scenario.status || "review"}</span>
                </div>
                <p className="mt-1">
                  Flow {formatValue(scenario.available_flow_gpm, " gpm", 0)} / {formatValue(scenario.required_flow_gpm, " gpm", 0)}; residual {formatValue(scenario.residual_pressure_psi, " psi", 1)}.
                </p>
                {scenario.missing_inputs?.length ? (
                  <p className="mt-1 text-[11px] font-semibold text-amber-700">Missing: {scenario.missing_inputs.join(", ")}</p>
                ) : null}
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
              Fire-flow demand and residual pressure evidence are missing.
            </p>
          )}
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Blockers / fixes</p>
        <div className="mt-2 space-y-2">
          {waterFireFlowReview.blockerCards.length ? (
            waterFireFlowReview.blockerCards.map((blocker) => (
              <div key={blocker.id} className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                <p className="font-semibold">{blocker.title}</p>
                <p className="mt-1 text-[11px] uppercase tracking-[0.12em]">{blocker.source.replaceAll("_", " ")}</p>
                <p className="mt-2 text-[11px] font-semibold">Fix: {blocker.nextAction}</p>
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
              No water-specific blocker cards are recorded in the current result.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
