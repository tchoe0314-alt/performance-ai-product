import { Droplets, Flame, GitBranch, Table2 } from "lucide-react";

import { formatFlowValue } from "../utils/previewGeometryTruth";

type FireFlowScenario = {
  id: string;
  label?: string;
  hydrantId?: string;
  networkType: string;
  availableFlowGpm: number | null;
  requiredFlowGpm: number | null;
  residualPressurePsi: number | null;
  residualTargetPsi?: number | null;
  missingInputs: string[];
  status: string;
};

type FireFlowHydrant = {
  id: string;
  label?: string;
};

type WaterFireFlowEvidence = {
  hasData: boolean;
  selectedScenario: FireFlowScenario | null;
  scenarios: FireFlowScenario[];
  hydrants: FireFlowHydrant[];
  networkSegments: Array<{ networkType: string }>;
  blockerCards: unknown[];
};

type WaterFireFlowEvidenceDockProps = {
  waterFireFlow: WaterFireFlowEvidence;
  onSelectScenario: (scenarioId: string) => void;
};

export function WaterFireFlowEvidenceDock({
  waterFireFlow,
  onSelectScenario,
}: WaterFireFlowEvidenceDockProps) {
  if (!waterFireFlow.hasData) {
    return null;
  }

  return (
    <div className="civora-evidence-dock civora-evidence-dock-right pointer-events-auto absolute bottom-3 left-3 right-3 z-40 rounded-lg border border-slate-200/80 bg-white/94 p-3 text-xs text-slate-700 shadow-[0_18px_55px_-32px_rgba(15,23,42,0.6)] backdrop-blur sm:left-auto sm:bottom-6 sm:right-6 sm:w-[380px] sm:max-w-[calc(100%-3rem)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            <Flame className="h-3.5 w-3.5 text-orange-500" />
            Water / Fire Flow
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            {waterFireFlow.selectedScenario?.label || "Hydrant scenarios"}
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-semibold text-slate-600">
          <Table2 className="h-3.5 w-3.5" />
          {waterFireFlow.scenarios.length || waterFireFlow.hydrants.length} rows
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase text-slate-500">
            <Droplets className="h-3.5 w-3.5 text-sky-600" />
            Hydrants
          </div>
          <p className="mt-1 text-lg font-semibold text-slate-950">{waterFireFlow.hydrants.length}</p>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase text-slate-500">
            <GitBranch className="h-3.5 w-3.5 text-sky-600" />
            Loops
          </div>
          <p className="mt-1 text-lg font-semibold text-slate-950">
            {waterFireFlow.networkSegments.filter((item) => item.networkType === "loop").length}
          </p>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
          <div className="text-[11px] font-semibold uppercase text-slate-500">Residual</div>
          <p
            className={`mt-1 text-lg font-semibold ${
              waterFireFlow.selectedScenario?.status === "pass"
                ? "text-emerald-700"
                : waterFireFlow.selectedScenario?.status === "fail"
                  ? "text-rose-700"
                  : "text-amber-700"
            }`}
          >
            {waterFireFlow.selectedScenario
              ? formatFlowValue(waterFireFlow.selectedScenario.residualPressurePsi, "psi", 1)
              : "Review"}
          </p>
        </div>
      </div>
      <div className="mt-3 max-h-[156px] overflow-auto rounded-md border border-slate-200">
        <table className="w-full border-collapse text-left text-[11px]">
          <thead className="sticky top-0 bg-slate-50 text-slate-500">
            <tr>
              <th className="px-2 py-1.5 font-semibold">Hydrant</th>
              <th className="px-2 py-1.5 font-semibold">Network</th>
              <th className="px-2 py-1.5 font-semibold">Flow</th>
              <th className="px-2 py-1.5 font-semibold">Residual</th>
              <th className="px-2 py-1.5 font-semibold">Check</th>
            </tr>
          </thead>
          <tbody>
            {waterFireFlow.scenarios.length ? (
              waterFireFlow.scenarios.map((scenario) => {
                const hydrant = waterFireFlow.hydrants.find((item) => item.id === scenario.hydrantId);
                const selected = waterFireFlow.selectedScenario?.id === scenario.id;
                return (
                  <tr
                    key={scenario.id}
                    className={`cursor-pointer border-t border-slate-100 ${selected ? "bg-sky-50" : "hover:bg-slate-50"}`}
                    onClick={() => onSelectScenario(scenario.id)}
                  >
                    <td className="px-2 py-1.5 font-semibold text-slate-900">
                      {hydrant?.label || scenario.hydrantId || "Hydrant"}
                    </td>
                    <td className="px-2 py-1.5 capitalize">{scenario.networkType.replace("_", " ")}</td>
                    <td className="px-2 py-1.5">
                      {formatFlowValue(scenario.availableFlowGpm, "gpm", 0)}/
                      {formatFlowValue(scenario.requiredFlowGpm, "gpm", 0)}
                    </td>
                    <td className="px-2 py-1.5">
                      {formatFlowValue(scenario.residualPressurePsi, "psi", 1)}
                      {scenario.missingInputs.length ? (
                        <div className="mt-0.5 text-[10px] font-semibold text-amber-700">
                          Missing: {scenario.missingInputs.slice(0, 2).join(", ")}
                        </div>
                      ) : null}
                    </td>
                    <td
                      className={`px-2 py-1.5 font-semibold uppercase ${
                        scenario.status === "pass"
                          ? "text-emerald-700"
                          : scenario.status === "fail"
                            ? "text-rose-700"
                            : "text-amber-700"
                      }`}
                    >
                      {scenario.status}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td className="px-2 py-4 text-slate-500" colSpan={5}>
                  Canonical hydrants found. Add pressure/flow data to run checks.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-5 rounded-full bg-sky-600" />
          Loop
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-5 rounded-full border border-orange-400 border-dashed" />
          Dead-end
        </span>
        <span>
          Target residual: {formatFlowValue(waterFireFlow.selectedScenario?.residualTargetPsi ?? null, "psi", 0)}
        </span>
        {waterFireFlow.blockerCards.length ? (
          <span className="font-semibold text-amber-700">
            {waterFireFlow.blockerCards.length} blocker cards
          </span>
        ) : null}
        <span className="font-semibold text-slate-600">Engineer review required</span>
      </div>
    </div>
  );
}
