import type { SiteObjectType } from "../types";
import type { SystemStatus } from "../utils/workflowConstants";

type SanitaryWorkbenchPanelProps = {
  hasHardSystemBlock: boolean;
  utilitiesStatus: SystemStatus;
  utilitiesEnabled: boolean;
  pipeMinSlopePct: string;
  buildingCoverageLabel: string;
  onUtilitiesChange: (enabled: boolean) => void;
  onPipeMinSlopePctChange: (value: string) => void;
  onAddObject: (type: SiteObjectType) => void;
  onGenerateUtilities: () => void;
};

export function SanitaryWorkbenchPanel({
  hasHardSystemBlock,
  utilitiesStatus,
  utilitiesEnabled,
  pipeMinSlopePct,
  buildingCoverageLabel,
  onUtilitiesChange,
  onPipeMinSlopePctChange,
  onAddObject,
  onGenerateUtilities,
}: SanitaryWorkbenchPanelProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Status", hasHardSystemBlock ? "Needs input / review" : utilitiesStatus === "fresh" ? "Complete" : "Not configured"],
          ["Service", utilitiesEnabled ? "Enabled" : "Off"],
          ["Pipe slope", pipeMinSlopePct || "Auto"],
          ["Coverage", buildingCoverageLabel],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Sanitary rules</p>
        <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
          <span>Include sanitary services</span>
          <input
            type="checkbox"
            checked={utilitiesEnabled}
            onChange={(event) => onUtilitiesChange(event.target.checked)}
            className="h-4 w-4 accent-slate-950"
          />
        </label>
        <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Minimum pipe slope %
          <input
            value={pipeMinSlopePct}
            onChange={(event) => onPipeMinSlopePctChange(event.target.value)}
            placeholder="Auto"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-700"
          />
        </label>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Service laterals</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Manhole spacing</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Cover checks</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Tie-in review</span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button type="button" onClick={() => onAddObject("manhole")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
            Add manhole
          </button>
          <button type="button" onClick={() => onAddObject("utility_corridor")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
            Add corridor
          </button>
        </div>
        <button type="button" onClick={onGenerateUtilities} className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800">
          Generate sanitary
        </button>
      </div>
    </div>
  );
}
