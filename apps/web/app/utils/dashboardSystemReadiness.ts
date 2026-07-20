import type { BuildingPlacement } from "../types";
import type { SidePanelKey } from "./workspaceShell";
import {
  OVERSIZED_SITE_MESSAGE,
  type EngineeringSystemKey,
  type SystemGenerationTarget,
  type SystemStatus,
} from "./workflowConstants";

export type DashboardSystemBlockerTarget =
  | "grading"
  | "drainage"
  | "storm"
  | "sanitary"
  | "water"
  | "utilities"
  | "roadway";

type ConfirmedObjectCounts = {
  buildings: number;
  access: number;
};

export type DashboardSystemBlockerContext = {
  missingSite: boolean;
  siteScaleLocked: boolean;
  siteTooLargeForGrading: boolean;
  hasTerrainSource: boolean;
  hasStandardsEvidence: boolean;
  hasAppliedAddress: boolean;
  onlineSourceLookupUnavailable: boolean;
  hasAssumedTerrainSlope: boolean;
  hasVerifiedSurveyControl: boolean;
  hasBasinPlaced: boolean;
  hasBasinObject: boolean;
  buildingPlacements: BuildingPlacement[];
  confirmedObjectCounts: ConfirmedObjectCounts;
  utilities: unknown;
  hasUtilityConnectionPlaced: boolean;
  hasUtilityConnectionObject: boolean;
  hasHardSystemBlock: boolean;
};

export type DashboardSystemReadinessRow = {
  key: DashboardSystemBlockerTarget;
  label: string;
  panel: SidePanelKey;
  runTarget: SystemGenerationTarget;
  status: SystemStatus;
  blockers: string[];
};

export function getDashboardSystemBlockers(
  target: DashboardSystemBlockerTarget,
  context: DashboardSystemBlockerContext,
): string[] {
  const blockers: string[] = [];
  if (context.missingSite) blockers.push("Set site width and depth.");
  if (!context.siteScaleLocked) blockers.push("Lock the site boundary.");
  if (context.siteTooLargeForGrading && (target === "grading" || target === "drainage" || target === "storm")) {
    blockers.push(OVERSIZED_SITE_MESSAGE);
  }
  if ((target === "grading" || target === "drainage" || target === "storm") && !context.hasTerrainSource) {
    blockers.push("missing terrain/source: add survey, DEM/geocoded terrain, or explicitly accept an assumed slope.");
  }
  if (!context.hasStandardsEvidence) {
    blockers.push("missing standards");
  }
  if (context.hasAppliedAddress && context.onlineSourceLookupUnavailable) {
    blockers.push("Address applied; online source lookup not configured/available.");
  }
  if (context.hasAssumedTerrainSlope && !context.hasVerifiedSurveyControl) {
    blockers.push("assumed terrain slope / survey-control still needed");
  }
  if ((target === "drainage" || target === "storm") && !context.hasBasinPlaced) {
    blockers.push(context.hasBasinObject ? "detention basin exists but needs placement." : "missing detention basin.");
  }
  if ((target === "drainage" || target === "storm") && !context.buildingPlacements.some((item) => item.type === "outfall" && item.placed)) {
    blockers.push(context.buildingPlacements.some((item) => item.type === "outfall") ? "outfall exists but is not placed" : "missing outfall");
  }
  if (target === "roadway" && context.confirmedObjectCounts.buildings === 0 && context.confirmedObjectCounts.access === 0) {
    blockers.push("Add at least one building, entrance, driveway, road, or parking object.");
  }
  if ((target === "sanitary" || target === "water" || target === "utilities") && !context.utilities) {
    blockers.push("Enable utility generation.");
  }
  if ((target === "sanitary" || target === "water") && context.confirmedObjectCounts.buildings === 0) {
    blockers.push("Add buildings or service/demand targets.");
  }
  if ((target === "sanitary" || target === "water" || target === "utilities") && !context.hasUtilityConnectionPlaced) {
    blockers.push(context.hasUtilityConnectionObject ? "utility connection exists but is not placed." : "missing utility connection.");
  }
  if (context.hasHardSystemBlock && target !== "roadway") {
    blockers.push("Resolve active hard model blockers.");
  }
  return blockers;
}

export function buildDashboardSystemReadinessRows({
  systemStatuses,
  blockerContext,
}: {
  systemStatuses: Record<EngineeringSystemKey, SystemStatus>;
  blockerContext: DashboardSystemBlockerContext;
}): DashboardSystemReadinessRow[] {
  return [
    { key: "grading", label: "Grading", panel: "grading", runTarget: "grading", status: systemStatuses.grading, blockers: getDashboardSystemBlockers("grading", blockerContext) },
    { key: "drainage", label: "Drainage", panel: "drainage", runTarget: "drainage", status: systemStatuses.drainage, blockers: getDashboardSystemBlockers("drainage", blockerContext) },
    { key: "storm", label: "Storm", panel: "drainage", runTarget: "drainage", status: systemStatuses.drainage, blockers: getDashboardSystemBlockers("storm", blockerContext) },
    { key: "sanitary", label: "Sanitary", panel: "sanitary", runTarget: "utilities", status: systemStatuses.utilities, blockers: getDashboardSystemBlockers("sanitary", blockerContext) },
    { key: "water", label: "Water", panel: "water", runTarget: "utilities", status: systemStatuses.utilities, blockers: getDashboardSystemBlockers("water", blockerContext) },
    { key: "utilities", label: "Utilities", panel: "utilities", runTarget: "utilities", status: systemStatuses.utilities, blockers: getDashboardSystemBlockers("utilities", blockerContext) },
    { key: "roadway", label: "Roadway", panel: "roadway", runTarget: "roads", status: systemStatuses.roads, blockers: getDashboardSystemBlockers("roadway", blockerContext) },
  ];
}
