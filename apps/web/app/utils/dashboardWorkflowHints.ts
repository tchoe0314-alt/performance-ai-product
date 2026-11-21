import type { BuildingPlacement, Issue } from "../types";
import type { DashboardExistingConditionRow } from "./dashboardEvidenceSummaries";
import {
  getDashboardSystemBlockers,
  type DashboardSystemBlockerContext,
  type DashboardSystemReadinessRow,
} from "./dashboardSystemReadiness";
import { isHardGenerateBlocker } from "./workflowConstants";
import type { DashboardResultTruth } from "./dashboardResultTruth";
import type { SidePanelKey } from "./workspaceShell";

export type DashboardNextAction = { label: string; detail: string; panel: SidePanelKey };

export function buildDashboardNextAction({
  hasLocationEvidence, siteSizeSet, hasSiteBoundary, siteScaleLocked, placedObjectCount,
  firstSystemBlocker, resultTruth, exportBlockReason,
}: {
  hasLocationEvidence: boolean;
  siteSizeSet: boolean;
  hasSiteBoundary: boolean;
  siteScaleLocked: boolean;
  placedObjectCount: number;
  firstSystemBlocker?: string;
  resultTruth: DashboardResultTruth;
  exportBlockReason: string;
}): DashboardNextAction {
  if (!hasLocationEvidence) return { label: "Set up site", detail: "Add an address or choose a blank site.", panel: "site_existing" };
  if (!siteSizeSet) return { label: "Set site size", detail: "Enter the site width and depth.", panel: "site_existing" };
  if (!hasSiteBoundary) return { label: "Draw boundary", detail: "Add the active site boundary.", panel: "site_existing" };
  if (!siteScaleLocked) return { label: "Lock boundary", detail: "Confirm the site boundary before generation.", panel: "site_existing" };
  if (placedObjectCount <= 1) return { label: "Add design objects", detail: "Draw objects or generate a layout.", panel: "generate" };
  if (firstSystemBlocker) return { label: "Resolve generation input", detail: firstSystemBlocker, panel: "generate" };
  if (resultTruth.state === "missing" || resultTruth.state === "failed") return { label: "Generate", detail: resultTruth.reason, panel: "generate" };
  if (resultTruth.state !== "current") return { label: "Recalculate", detail: resultTruth.reason, panel: "generate" };
  if (exportBlockReason) return { label: "Review export blockers", detail: exportBlockReason, panel: "deliverables" };
  return { label: "Export current review package", detail: "Calculated results match the active saved project.", panel: "deliverables" };
}

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
