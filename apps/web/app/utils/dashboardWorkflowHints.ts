import type { BuildingPlacement, Issue } from "../types";
import type { DashboardExistingConditionRow } from "./dashboardEvidenceSummaries";
import {
  getDashboardSystemBlockers,
  type DashboardSystemBlockerContext,
  type DashboardSystemReadinessRow,
} from "./dashboardSystemReadiness";
import { isHardGenerateBlocker } from "./workflowConstants";

export function buildDashboardCivil3DWorkflowBlockers({
  blockerContext,
  previewBlockedReasons,
  issues,
}: {
  blockerContext: DashboardSystemBlockerContext;
  previewBlockedReasons: string[];
  issues: Issue[];
}): string[] {
  const blockers = [
    ...getDashboardSystemBlockers("roadway", blockerContext),
    ...getDashboardSystemBlockers("grading", blockerContext),
    ...previewBlockedReasons,
    ...issues
      .filter((issue) =>
        /corridor|road|profile|section|surface|grading|cut|fill/i.test(`${issue.code ?? ""} ${issue.message}`),
      )
      .map((issue) => issue.message),
  ];
  return Array.from(new Set(blockers.filter(Boolean))).slice(0, 8);
}

export function buildDashboardWorkflowActionHints({
  hasLocationEvidence,
  siteSizeSet,
  buildingPlacements,
  siteScaleLocked,
  existingConditionRows,
  placedObjectCount,
  systemReadinessRows,
  exportBlockReason,
}: {
  hasLocationEvidence: boolean;
  siteSizeSet: boolean;
  buildingPlacements: BuildingPlacement[];
  siteScaleLocked: boolean;
  existingConditionRows: DashboardExistingConditionRow[];
  placedObjectCount: number;
  systemReadinessRows: DashboardSystemReadinessRow[];
  exportBlockReason: string;
}): string[] {
  const firstHardSystemRow = systemReadinessRows.find((row) => row.blockers.some(isHardGenerateBlocker));
  const firstHardSystemBlocker = firstHardSystemRow?.blockers.find(isHardGenerateBlocker);
  return [
    !hasLocationEvidence ? "Setup panel -> Start from address or blank site." : "",
    !siteSizeSet ? "Setup panel -> enter site width and depth." : "",
    !buildingPlacements.some((item) => item.type === "site") ? "Setup panel -> Draw site boundary." : "",
    !siteScaleLocked ? "Setup panel -> Lock site boundary." : "",
    existingConditionRows.some((item) => item.status === "block") ? "Data panel -> resolve missing existing-condition evidence." : "",
    placedObjectCount <= 1 ? "Objects panel -> add or draw buildings, parking, roads, basin/outfall, and utility points/lines." : "",
    firstHardSystemRow && firstHardSystemBlocker
      ? `Generate Systems panel -> ${firstHardSystemRow.label}: ${firstHardSystemBlocker}`
      : "",
    exportBlockReason ? `Deliver panel -> export blocked: ${exportBlockReason}.` : "",
  ].filter(Boolean);
}
