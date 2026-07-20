import type { SiteObjectType } from "../types";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import type { SystemStatus } from "../utils/workflowConstants";

type UtilitiesWorkbenchPanelProps = {
  hasHardSystemBlock: boolean;
  utilitiesStatus: SystemStatus;
  drainageEnabled: boolean;
  utilitiesEnabled: boolean;
  pipeMinSlopePct: string;
  onUtilitiesChange: (enabled: boolean) => void;
  onPipeMinSlopePctChange: (value: string) => void;
  onOpenSanitary: () => void;
  onOpenWater: () => void;
  onAddObject: (type: SiteObjectType) => void;
  onGenerateUtilities: () => void;
};

export function UtilitiesWorkbenchPanel({
  hasHardSystemBlock,
  utilitiesStatus,
  drainageEnabled,
  utilitiesEnabled,
  pipeMinSlopePct,
  onUtilitiesChange,
  onPipeMinSlopePctChange,
  onOpenSanitary,
  onOpenWater,
  onAddObject,
  onGenerateUtilities,
}: UtilitiesWorkbenchPanelProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Status", hasHardSystemBlock ? "Needs input / review" : utilitiesStatus === "fresh" ? "Complete" : "Not configured"],
          ["Storm", drainageEnabled ? "Enabled" : "Off"],
          ["Sanitary", utilitiesEnabled ? "Enabled" : "Off"],
          ["Water", utilitiesEnabled ? "Enabled" : "Off"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Utility rules</p>
        <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
          <span>Include utilities</span>
          <input
            type="checkbox"
            checked={utilitiesEnabled}
            onChange={(event) => onUtilitiesChange(event.target.checked)}
            className="h-4 w-4 accent-slate-950"
          />
        </label>
        <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Pipe min slope %
          <input
            value={pipeMinSlopePct}
            onChange={(event) => onPipeMinSlopePctChange(event.target.value)}
            placeholder="Auto"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-700"
          />
        </label>
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Coordination rules</p>
          <div className="mt-2 space-y-2 text-sm font-semibold text-slate-700">
            {["Maintain crossing clearance", "Prefer shared corridors", "Avoid building footprints", "Reroute around conflicts"].map((label) => (
              <div key={label} className="flex items-center justify-between gap-3">
                <span>{label}</span>
                <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                  Checked during utility run
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onOpenSanitary}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Sanitary
          </button>
          <button
            type="button"
            onClick={onOpenWater}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
          >
            Water
          </button>
        </div>
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Utility objects</p>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {(["utility_corridor", "manhole", "hydrant"] as const).map((type) => (
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
        <button type="button" onClick={onGenerateUtilities} className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800">
          Generate utilities
        </button>
      </div>
    </div>
  );
}
