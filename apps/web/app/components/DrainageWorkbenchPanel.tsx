import type { SiteObjectType } from "../types";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import type { SystemStatus } from "../utils/workflowConstants";

type DrainageWorkbenchPanelProps = {
  hasBasinPlaced: boolean;
  hasTerrainSource: boolean;
  hasHardSystemBlock: boolean;
  drainageStatus: SystemStatus;
  drainageSourceOverride: "civora" | "user";
  onDrainageSourceOverrideChange: (value: "civora" | "user") => void;
  drainageConnectOrphans: boolean;
  onDrainageConnectOrphansChange: (enabled: boolean) => void;
  drainageAllowSlopeAdjust: boolean;
  onDrainageAllowSlopeAdjustChange: (enabled: boolean) => void;
  drainageMaxSlopeAdjust: number;
  onDrainageMaxSlopeAdjustChange: (value: number) => void;
  missingSite: boolean;
  onAddObject: (type: SiteObjectType) => void;
  onGenerateDrainage: () => void;
};

export function DrainageWorkbenchPanel({
  hasBasinPlaced,
  hasTerrainSource,
  hasHardSystemBlock,
  drainageStatus,
  drainageSourceOverride,
  onDrainageSourceOverrideChange,
  drainageConnectOrphans,
  onDrainageConnectOrphansChange,
  drainageAllowSlopeAdjust,
  onDrainageAllowSlopeAdjustChange,
  drainageMaxSlopeAdjust,
  onDrainageMaxSlopeAdjustChange,
  missingSite,
  onAddObject,
  onGenerateDrainage,
}: DrainageWorkbenchPanelProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Basin", hasBasinPlaced ? "Placed" : "Missing"],
          ["Surface", hasTerrainSource ? "Ready" : "Missing"],
          ["Status", hasHardSystemBlock ? "Needs input / review" : drainageStatus === "fresh" ? "Complete" : "Not configured"],
          ["Source", drainageSourceOverride === "user" ? "User" : "Civora"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Drainage rules</p>
        <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
          <span>Drainage source</span>
          <select
            value={drainageSourceOverride}
            onChange={(event) => onDrainageSourceOverrideChange(event.target.value === "user" ? "user" : "civora")}
            className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700"
          >
            <option value="civora">Civora</option>
            <option value="user">User</option>
          </select>
        </label>
        <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
          <span>Connect orphan inlets</span>
          <input
            type="checkbox"
            checked={drainageConnectOrphans}
            onChange={(event) => onDrainageConnectOrphansChange(event.target.checked)}
            className="h-4 w-4 accent-slate-950"
          />
        </label>
        <label className="mt-2 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
          <span>Allow slope repair</span>
          <input
            type="checkbox"
            checked={drainageAllowSlopeAdjust}
            onChange={(event) => onDrainageAllowSlopeAdjustChange(event.target.checked)}
            className="h-4 w-4 accent-slate-950"
          />
        </label>
        <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Max slope adjustment
          <input
            value={drainageMaxSlopeAdjust}
            type="number"
            step="0.001"
            onChange={(event) => onDrainageMaxSlopeAdjustChange(Number(event.target.value) || 0)}
            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-700"
          />
        </label>
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Hydrology assumptions</p>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
            <span className="rounded-lg border border-slate-200 bg-white px-2 py-2">Low point detection</span>
            <span className="rounded-lg border border-slate-200 bg-white px-2 py-2">Flow path routing</span>
            <span className="rounded-lg border border-slate-200 bg-white px-2 py-2">Basin targeting</span>
            <span className="rounded-lg border border-slate-200 bg-white px-2 py-2">Overflow checks</span>
          </div>
        </div>
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Drainage objects</p>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {(["basin", "inlet", "outfall"] as const).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => onAddObject(type)}
                className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
              >
                {SITE_OBJECT_CATALOG[type].label}
              </button>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={onGenerateDrainage}
          disabled={missingSite || !hasTerrainSource || !hasBasinPlaced}
          className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
        >
          Generate drainage
        </button>
      </div>
    </div>
  );
}
