import type { GradingEarthworkUx, SourceConfidenceEntry, SiteObjectType } from "../types";
import {
  CivilSurfaceCorridorWorkflow,
  RoadwayCorridorWorkbench,
  type Civil3DWorkflowTab,
  type RoadwayWorkbenchData,
  type RoadwayWorkbenchTab,
} from "./CivilRoadwayWorkbench";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import type { SystemGenerationTarget, SystemStatus } from "../utils/workflowConstants";

type RoadwayWorkbenchPanelProps = {
  activeCivil3DWorkflowTab: Civil3DWorkflowTab;
  onCivil3DWorkflowTabChange: (tab: Civil3DWorkflowTab) => void;
  roadwayWorkbenchData: RoadwayWorkbenchData;
  gradingEarthworkUx: GradingEarthworkUx;
  sourceConfidenceRows: SourceConfidenceEntry[];
  civil3DWorkflowBlockers: string[];
  gradingSourceSummary: string;
  hasTerrainSource: boolean;
  hasVerifiedSurveyControl: boolean;
  onShowProfileControls: () => void;
  roadsStatus: SystemStatus;
  parkingStatus: SystemStatus;
  maxRoadGradePct: string;
  onMaxRoadGradePctChange: (value: string) => void;
  parkingAngle: "90" | "60" | "45";
  onParkingAngleChange: (value: "90" | "60" | "45") => void;
  roads: boolean;
  onRoadsChange: (enabled: boolean) => void;
  parkingLoading: "single" | "double";
  onParkingLoadingChange: (value: "single" | "double") => void;
  parkingStallWidth: string;
  onParkingStallWidthChange: (value: string) => void;
  parkingAisleWidth: string;
  onParkingAisleWidthChange: (value: string) => void;
  parkingStallDepth: string;
  onParkingStallDepthChange: (value: string) => void;
  parkingAdaCount: string;
  onParkingAdaCountChange: (value: string) => void;
  parkingCompactCount: string;
  onParkingCompactCountChange: (value: string) => void;
  parkingAdaAisleWidth: string;
  onParkingAdaAisleWidthChange: (value: string) => void;
  parkingCompactWidth: string;
  onParkingCompactWidthChange: (value: string) => void;
  activeRoadwayWorkbenchTab: RoadwayWorkbenchTab;
  onRoadwayWorkbenchTabChange: (tab: RoadwayWorkbenchTab) => void;
  maxAdaCrossSlopePct: string;
  onMaxAdaCrossSlopePctChange: (value: string) => void;
  onAddObject: (type: SiteObjectType) => void;
  onGenerateSystem: (target: SystemGenerationTarget) => void;
};

export function RoadwayWorkbenchPanel({
  activeCivil3DWorkflowTab,
  onCivil3DWorkflowTabChange,
  roadwayWorkbenchData,
  gradingEarthworkUx,
  sourceConfidenceRows,
  civil3DWorkflowBlockers,
  gradingSourceSummary,
  hasTerrainSource,
  hasVerifiedSurveyControl,
  onShowProfileControls,
  roadsStatus,
  parkingStatus,
  maxRoadGradePct,
  onMaxRoadGradePctChange,
  parkingAngle,
  onParkingAngleChange,
  roads,
  onRoadsChange,
  parkingLoading,
  onParkingLoadingChange,
  parkingStallWidth,
  onParkingStallWidthChange,
  parkingAisleWidth,
  onParkingAisleWidthChange,
  parkingStallDepth,
  onParkingStallDepthChange,
  parkingAdaCount,
  onParkingAdaCountChange,
  parkingCompactCount,
  onParkingCompactCountChange,
  parkingAdaAisleWidth,
  onParkingAdaAisleWidthChange,
  parkingCompactWidth,
  onParkingCompactWidthChange,
  activeRoadwayWorkbenchTab,
  onRoadwayWorkbenchTabChange,
  maxAdaCrossSlopePct,
  onMaxAdaCrossSlopePctChange,
  onAddObject,
  onGenerateSystem,
}: RoadwayWorkbenchPanelProps) {
  return (
    <div className="space-y-4">
      <CivilSurfaceCorridorWorkflow
        activeTab={activeCivil3DWorkflowTab}
        onTabChange={onCivil3DWorkflowTabChange}
        roadwayData={roadwayWorkbenchData}
        gradingEarthworkUx={gradingEarthworkUx}
        sourceConfidenceRows={sourceConfidenceRows}
        blockers={civil3DWorkflowBlockers}
        gradingSourceSummary={gradingSourceSummary}
        hasTerrainSource={hasTerrainSource}
        hasVerifiedSurveyControl={hasVerifiedSurveyControl}
        onOpenRoadwayControls={onShowProfileControls}
      />
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Roads", roadsStatus === "fresh" ? "Complete" : "Not configured"],
          ["Parking", parkingStatus === "fresh" ? "Complete" : "Not configured"],
          ["Max grade", maxRoadGradePct || "Auto"],
          ["Angle", `${parkingAngle} deg`],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Roadway rules</p>
        <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
          <span>Generate roads</span>
          <input type="checkbox" checked={roads} onChange={(event) => onRoadsChange(event.target.checked)} className="h-4 w-4 accent-slate-950" />
        </label>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Parking angle
            <select
              value={parkingAngle}
              onChange={(event) => onParkingAngleChange(event.target.value as "90" | "60" | "45")}
              className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm normal-case tracking-normal text-slate-700"
            >
              <option value="90">90 deg</option>
              <option value="60">60 deg</option>
              <option value="45">45 deg</option>
            </select>
          </label>
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Parking load
            <select
              value={parkingLoading}
              onChange={(event) => onParkingLoadingChange(event.target.value as "single" | "double")}
              className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm normal-case tracking-normal text-slate-700"
            >
              <option value="double">Double loaded</option>
              <option value="single">Single loaded</option>
            </select>
          </label>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Stall width
            <input value={parkingStallWidth} onChange={(event) => onParkingStallWidthChange(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Aisle width
            <input value={parkingAisleWidth} onChange={(event) => onParkingAisleWidthChange(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Stall depth
            <input value={parkingStallDepth} onChange={(event) => onParkingStallDepthChange(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Road max %
            <input value={maxRoadGradePct} onChange={(event) => onMaxRoadGradePctChange(event.target.value)} placeholder="Auto" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            ADA spaces
            <input value={parkingAdaCount} onChange={(event) => onParkingAdaCountChange(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Compact spaces
            <input value={parkingCompactCount} onChange={(event) => onParkingCompactCountChange(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            ADA aisle
            <input value={parkingAdaAisleWidth} onChange={(event) => onParkingAdaAisleWidthChange(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            Compact width
            <input value={parkingCompactWidth} onChange={(event) => onParkingCompactWidthChange(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
        </div>
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Roadway objects</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {(["entrance", "road", "parking", "sidewalk"] as const).map((type) => (
              <button key={type} type="button" onClick={() => onAddObject(type)} className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50">
                {SITE_OBJECT_CATALOG[type].label}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button type="button" onClick={() => onGenerateSystem("roads")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Roads</button>
          <button type="button" onClick={() => onGenerateSystem("parking")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Parking</button>
        </div>
      </div>
      <RoadwayCorridorWorkbench
        data={roadwayWorkbenchData}
        activeTab={activeRoadwayWorkbenchTab}
        onTabChange={onRoadwayWorkbenchTabChange}
        maxRoadGradePct={maxRoadGradePct}
        setMaxRoadGradePct={onMaxRoadGradePctChange}
        maxAdaCrossSlopePct={maxAdaCrossSlopePct}
        setMaxAdaCrossSlopePct={onMaxAdaCrossSlopePctChange}
        handleGenerateSystem={onGenerateSystem}
      />
    </div>
  );
}
