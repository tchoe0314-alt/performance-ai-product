import type { BuildingPlacement } from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";
import type { SystemStatus } from "../utils/workflowConstants";

type SystemReadinessPanelKey = Extract<
  SidePanelKey,
  | "system_grading"
  | "system_storm"
  | "system_sanitary"
  | "system_water"
  | "system_roadway"
  | "system_utilities"
  | "system_landscape"
>;

type StormHydrologyReview = {
  segments: Array<unknown>;
  profile: Array<{
    stationFt: number;
    invertFt: number | null;
    groundFt: number | null;
    hglFt: number | null;
    eglFt: number | null;
  }>;
  inletChecks: Array<{
    id: string;
    spreadFt: number | null;
    allowableSpreadFt: number | null;
    captureEfficiency: number | null;
  }>;
  detentionRouting: Array<{
    timeMin: number;
    inflowCfs: number | null;
    outflowCfs: number | null;
  }>;
  overflowPaths: Array<{
    id: string;
    name: string;
    capacityValid: boolean;
    capacityCfs: number | null;
    requiredCapacityCfs: number | null;
  }>;
  blockerDetails: Array<{
    code: string;
    message: string;
    fix: string;
    missingInputs: string[];
  }>;
};

type SystemStatuses = Pick<SystemStatusMap, "grading" | "drainage" | "utilities" | "roads" | "parking">;

type SystemStatusMap = {
  grading: SystemStatus;
  drainage: SystemStatus;
  utilities: SystemStatus;
  roads: SystemStatus;
  parking: SystemStatus;
};

type SystemReadinessPanelProps = {
  sidePanelForRender: SystemReadinessPanelKey;
  siteTooLargeForGrading: boolean;
  systemStatuses: SystemStatuses;
  siteScaleLocked: boolean;
  hasTerrainSource: boolean;
  hasBasinPlaced: boolean;
  hasHardSystemBlock: boolean;
  buildingPlacements: BuildingPlacement[];
  utilities: boolean;
  pipeMinSlopePct: string;
  roads: boolean;
  maxRoadGradePct: string;
  stormHydrologyReview: StormHydrologyReview;
  onOpenPanel: (panel: SidePanelKey) => void;
};

function lineForProfile(
  points: StormHydrologyReview["profile"],
  key: "invertFt" | "hglFt" | "eglFt" | "groundFt",
) {
  const stations = points.map((point) => point.stationFt);
  const elevations = points
    .flatMap((point) => [point.invertFt, point.hglFt, point.eglFt, point.groundFt])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const minStation = Math.min(...stations);
  const maxStation = Math.max(...stations, minStation + 1);
  const minElev = Math.min(...elevations) - 1;
  const maxElev = Math.max(...elevations) + 1;
  const x = (value: number) => 6 + ((value - minStation) / Math.max(maxStation - minStation, 1)) * 88;
  const y = (value: number) => 86 - ((value - minElev) / Math.max(maxElev - minElev, 1)) * 72;

  return points
    .filter((point) => typeof point[key] === "number")
    .map((point) => `${x(point.stationFt)},${y(point[key] as number)}`)
    .join(" ");
}

function lineForRouting(points: StormHydrologyReview["detentionRouting"], key: "inflowCfs" | "outflowCfs") {
  const maxTime = Math.max(...points.map((point) => point.timeMin), 1);
  const flowValues = points
    .flatMap((point) => [point.inflowCfs, point.outflowCfs])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const maxFlow = Math.max(...flowValues, 1);
  const x = (value: number) => 6 + (value / maxTime) * 88;
  const y = (value: number) => 86 - (value / maxFlow) * 72;

  return points
    .filter((point) => typeof point[key] === "number")
    .map((point) => `${x(point.timeMin)},${y(point[key] as number)}`)
    .join(" ");
}

function StormHydrologyReviewPanel({ stormHydrologyReview }: { stormHydrologyReview: StormHydrologyReview }) {
  return (
    <div className="mt-4 space-y-3" data-testid="storm-hydrology-review">
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Pipes", stormHydrologyReview.segments.length || "None"],
          ["HGL/EGL", stormHydrologyReview.profile.length ? "Available" : "Missing"],
          ["Inlet spread", stormHydrologyReview.inletChecks.length ? `${stormHydrologyReview.inletChecks.length} checks` : "Missing"],
          ["Overflow", stormHydrologyReview.overflowPaths.length ? `${stormHydrologyReview.overflowPaths.length} paths` : "Missing"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Pipe profile viewer</p>
          <span className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            HGL/EGL
          </span>
        </div>
        {stormHydrologyReview.profile.length ? (
          <svg className="mt-3 h-40 w-full rounded-xl border border-slate-200 bg-white" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Storm pipe profile with HGL and EGL">
            <line x1="6" y1="86" x2="94" y2="86" stroke="#cbd5e1" strokeWidth="0.5" />
            <line x1="6" y1="10" x2="6" y2="86" stroke="#cbd5e1" strokeWidth="0.5" />
            <polyline points={lineForProfile(stormHydrologyReview.profile, "groundFt")} fill="none" stroke="#64748b" strokeWidth="1.1" strokeDasharray="2 2" />
            <polyline points={lineForProfile(stormHydrologyReview.profile, "invertFt")} fill="none" stroke="#334155" strokeWidth="1.3" />
            <polyline points={lineForProfile(stormHydrologyReview.profile, "hglFt")} fill="none" stroke="#0284c7" strokeWidth="1.4" />
            <polyline points={lineForProfile(stormHydrologyReview.profile, "eglFt")} fill="none" stroke="#f97316" strokeWidth="1.2" />
          </svg>
        ) : (
          <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
            No HGL/EGL profile is recorded. Run drainage/storm with hydraulic analysis or provide tailwater/outfall evidence.
          </p>
        )}
        <div className="mt-2 flex flex-wrap gap-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          <span className="rounded-md bg-slate-200 px-2 py-1">Ground</span>
          <span className="rounded-md bg-slate-800 px-2 py-1 text-white">Invert</span>
          <span className="rounded-md bg-sky-100 px-2 py-1 text-sky-700">HGL</span>
          <span className="rounded-md bg-orange-100 px-2 py-1 text-orange-700">EGL</span>
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Inlet spread map</p>
        <div className="mt-2 space-y-2">
          {stormHydrologyReview.inletChecks.length ? stormHydrologyReview.inletChecks.slice(0, 5).map((inlet) => {
            const overTarget =
              inlet.spreadFt !== null &&
              inlet.allowableSpreadFt !== null &&
              inlet.spreadFt > inlet.allowableSpreadFt;
            return (
              <div key={inlet.id} className={`rounded-xl border px-3 py-2 text-xs ${overTarget ? "border-rose-200 bg-rose-50 text-rose-800" : "border-sky-200 bg-white text-slate-700"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{inlet.id}</span>
                  <span className="font-semibold">{inlet.spreadFt !== null ? `${inlet.spreadFt.toFixed(1)} ft` : "Spread n/a"}</span>
                </div>
                <p className="mt-1 text-[11px]">
                  Limit {inlet.allowableSpreadFt !== null ? `${inlet.allowableSpreadFt.toFixed(1)} ft` : "not recorded"}; capture {inlet.captureEfficiency !== null ? `${Math.round(inlet.captureEfficiency * 100)}%` : "n/a"}.
                </p>
              </div>
            );
          }) : (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
              Inlet spread checks are missing. Add inlet geometry and rerun storm hydraulics.
            </p>
          )}
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Detention routing chart</p>
        {stormHydrologyReview.detentionRouting.length ? (
          <svg className="mt-3 h-32 w-full rounded-xl border border-slate-200 bg-white" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Detention routing inflow and outflow">
            <line x1="6" y1="86" x2="94" y2="86" stroke="#cbd5e1" strokeWidth="0.5" />
            <line x1="6" y1="10" x2="6" y2="86" stroke="#cbd5e1" strokeWidth="0.5" />
            <polyline points={lineForRouting(stormHydrologyReview.detentionRouting, "inflowCfs")} fill="none" stroke="#0284c7" strokeWidth="1.4" />
            <polyline points={lineForRouting(stormHydrologyReview.detentionRouting, "outflowCfs")} fill="none" stroke="#16a34a" strokeWidth="1.4" />
          </svg>
        ) : (
          <p className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
            Detention routing is missing. Confirm basin storage/outlet data, then rerun drainage.
          </p>
        )}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Overflow path view</p>
        <div className="mt-2 space-y-2">
          {stormHydrologyReview.overflowPaths.length ? stormHydrologyReview.overflowPaths.map((path) => (
            <div key={path.id} className={`rounded-xl border px-3 py-2 text-xs ${path.capacityValid ? "border-emerald-200 bg-white text-slate-700" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">{path.name}</span>
                <span className="font-semibold">{path.capacityValid ? "Capacity ok" : "Needs input"}</span>
              </div>
              <p className="mt-1 text-[11px]">
                {path.capacityCfs !== null ? `${path.capacityCfs.toFixed(1)} cfs capacity` : "Capacity n/a"}; required {path.requiredCapacityCfs !== null ? `${path.requiredCapacityCfs.toFixed(1)} cfs` : "not recorded"}.
              </p>
            </div>
          )) : (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
              Overflow path is missing. Add spillway/high-flow route evidence before export.
            </p>
          )}
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Exact blockers / fixes</p>
        <div className="mt-2 space-y-2">
          {stormHydrologyReview.blockerDetails.length ? stormHydrologyReview.blockerDetails.map((blocker) => (
            <div key={blocker.code} className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs text-slate-700">
              <p className="font-semibold text-slate-900">{blocker.message}</p>
              <p className="mt-1 text-[11px] uppercase tracking-[0.12em] text-amber-700">{blocker.code.replaceAll("_", " ")}</p>
              <p className="mt-2 text-[11px] font-semibold text-slate-700">Fix: {blocker.fix}</p>
              {blocker.missingInputs.length ? (
                <p className="mt-1 text-[11px] text-slate-500">Missing: {blocker.missingInputs.join(", ")}</p>
              ) : null}
            </div>
          )) : (
            <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800">
              No storm-specific blockers are recorded in the current result.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function SystemReadinessPanel({
  sidePanelForRender,
  siteTooLargeForGrading,
  systemStatuses,
  siteScaleLocked,
  hasTerrainSource,
  hasBasinPlaced,
  hasHardSystemBlock,
  buildingPlacements,
  utilities,
  pipeMinSlopePct,
  roads,
  maxRoadGradePct,
  stormHydrologyReview,
  onOpenPanel,
}: SystemReadinessPanelProps) {
  const healthConfig: Record<SystemReadinessPanelKey, { label: string; status: string; needs: string[]; openPanel: SidePanelKey }> = {
    system_grading: {
      label: "Grading",
      status: siteTooLargeForGrading ? "Needs input / review" : systemStatuses.grading === "fresh" ? "Complete" : "Not configured / not rendered",
      needs: [
        siteScaleLocked ? "Site boundary locked" : "Lock a site boundary",
        hasTerrainSource ? "Terrain source ready" : "Import survey, DEM, or map terrain",
        siteTooLargeForGrading ? "Reduce oversized grading area" : "Area is within grading limits",
        systemStatuses.grading === "fresh" ? "Generated grading is current" : "Run grading generation",
      ],
      openPanel: "grading",
    },
    system_storm: {
      label: "Storm Drainage",
      status: hasHardSystemBlock ? "Needs input / review" : systemStatuses.drainage === "fresh" ? "Complete" : "Not configured / not rendered",
      needs: [
        hasTerrainSource ? "Terrain source ready" : "Import terrain for flow direction",
        hasBasinPlaced ? "Basin placed" : "Place a detention basin",
        systemStatuses.drainage === "fresh" ? "Drainage generated" : "Run drainage generation",
        hasHardSystemBlock ? "Resolve hard system blockers" : "No hard blockers detected",
      ],
      openPanel: "drainage",
    },
    system_sanitary: {
      label: "Sanitary Sewer",
      status: hasHardSystemBlock ? "Needs input / review" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured / not rendered",
      needs: [
        buildingPlacements.length ? "Buildings available for service coverage" : "Add buildings or service targets",
        utilities ? "Utility generation enabled" : "Enable utilities",
        pipeMinSlopePct ? "Minimum pipe slope configured" : "Set or accept automatic pipe slope",
        systemStatuses.utilities === "fresh" ? "Utility network generated" : "Run utility generation",
      ],
      openPanel: "sanitary",
    },
    system_water: {
      label: "Water",
      status: hasHardSystemBlock ? "Needs input / review" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured / not rendered",
      needs: [
        utilities ? "Water network enabled" : "Enable utilities",
        buildingPlacements.filter((item) => item.type === "hydrant").length ? "Hydrants placed" : "Add hydrants or allow generated hydrants",
        buildingPlacements.length ? "Demand targets available" : "Add buildings or demand targets",
        systemStatuses.utilities === "fresh" ? "Utility network generated" : "Run utility generation",
      ],
      openPanel: "water",
    },
    system_roadway: {
      label: "Roadway",
      status: systemStatuses.roads === "fresh" ? "Complete" : "Not configured / not rendered",
      needs: [
        siteScaleLocked ? "Site boundary locked" : "Lock a site boundary",
        roads ? "Road generation enabled" : "Enable roads",
        systemStatuses.roads === "fresh" ? "Roadway generated" : "Run roadway generation",
        maxRoadGradePct ? "Road grade criteria configured" : "Set or accept automatic road grade",
      ],
      openPanel: "roadway",
    },
    system_utilities: {
      label: "Utilities",
      status: hasHardSystemBlock ? "Needs input / review" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured / not rendered",
      needs: [
        utilities ? "Utility generation enabled" : "Enable utilities",
        systemStatuses.drainage === "fresh" ? "Storm context ready" : "Generate or review drainage first",
        hasHardSystemBlock ? "Resolve hard conflicts" : "No hard blockers detected",
        systemStatuses.utilities === "fresh" ? "Utilities generated" : "Run utility generation",
      ],
      openPanel: "utilities",
    },
    system_landscape: {
      label: "Landscape",
      status: buildingPlacements.some((value) => ["open_space", "amenity", "pool"].includes(value.type ?? "")) ? "Complete" : "Not configured / not rendered",
      needs: [
        buildingPlacements.some((value) => value.type === "open_space") ? "Open space placed" : "Add open space",
        buildingPlacements.some((value) => value.type === "sidewalk") ? "Pedestrian paths placed" : "Add pedestrian paths",
        buildingPlacements.some((value) => ["amenity", "pool"].includes(value.type ?? "")) ? "Amenity objects placed" : "Add amenity objects if needed",
      ],
      openPanel: "landscape",
    },
  };
  const config = healthConfig[sidePanelForRender];

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{config.label} readiness</p>
        <p className="mt-2 text-lg font-semibold text-slate-950">{config.status}</p>
        <div className="mt-4 space-y-2">
          {config.needs.map((need) => (
            <div key={need} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
              <span>{need}</span>
            </div>
          ))}
        </div>
        {sidePanelForRender === "system_storm" ? (
          <StormHydrologyReviewPanel stormHydrologyReview={stormHydrologyReview} />
        ) : null}
        <button
          type="button"
          onClick={() => onOpenPanel(config.openPanel)}
          className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
        >
          Open controls
        </button>
      </div>
    </div>
  );
}
