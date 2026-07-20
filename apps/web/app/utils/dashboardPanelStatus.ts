import type { BuildingPlacement } from "../types";
import type { SidePanelKey, SidebarStatus } from "./workspaceShell";
import type { SystemStatus } from "./workflowConstants";

export type DashboardPanelStatusContext = {
  issuesLength: number;
  analysisIssuesLength: number;
  hasHardSystemBlock: boolean;
  backendResultPresent: boolean;
  siteScaleLocked: boolean;
  geocodePresent: boolean;
  hasTerrainSource: boolean;
  surveyPreviewPointsLength: number;
  uploadedImagePreviewUrl: string;
  uploadedImageApiUrl: string;
  mapSnapshotPath: string;
  placedObjectCount: number;
  planPreviewUrl: string | null;
  buildingPlacements: BuildingPlacement[];
  controlsHealthStatus: SidebarStatus;
  siteTooLargeForGrading: boolean;
  hasBasinPlaced: boolean;
  systemStatuses: Record<"roads" | "parking" | "grading" | "drainage" | "utilities", SystemStatus>;
  utilities: unknown;
  roads: unknown;
  minSlopePct: string;
  maxRoadGradePct: string;
  pipeMinSlopePct: string;
  maxAdaCrossSlopePct: string;
  customerTemplateBlockerCount: number;
  customerTemplates: unknown;
  utilityCatalog: { summary?: { review_required_count?: number } } | null | undefined;
};

export function resolveDashboardPanelStatus(
  target: SidePanelKey,
  context: DashboardPanelStatusContext,
): SidebarStatus {
  if (target === "dashboard" || target === "analysis") {
    return context.issuesLength || context.analysisIssuesLength || context.hasHardSystemBlock
      ? "review"
      : context.backendResultPresent
        ? "ok"
        : "idle";
  }
  if (target === "site_existing" || target === "data") {
    return context.siteScaleLocked || context.geocodePresent ? "ok" : "review";
  }
  if (target === "import_survey" || target === "files") {
    return context.hasTerrainSource ||
      context.surveyPreviewPointsLength ||
      context.uploadedImagePreviewUrl ||
      context.uploadedImageApiUrl ||
      context.mapSnapshotPath
      ? "ok"
      : "review";
  }
  if (target === "model" || target === "layers") {
    return context.placedObjectCount > 0 || context.planPreviewUrl ? "ok" : "idle";
  }
  if (target === "objects" || target === "details") {
    return context.buildingPlacements.length > 0 ? "ok" : "idle";
  }
  if (target === "generate") return context.controlsHealthStatus;
  if (target === "grading") {
    return context.siteTooLargeForGrading
      ? "block"
      : context.hasTerrainSource || context.systemStatuses.grading === "fresh"
        ? "ok"
        : "review";
  }
  if (target === "drainage") {
    return context.hasHardSystemBlock
      ? "block"
      : context.hasBasinPlaced || context.systemStatuses.drainage === "fresh"
        ? "ok"
        : "review";
  }
  if (target === "sanitary" || target === "water" || target === "utilities") {
    return context.hasHardSystemBlock
      ? "block"
      : context.utilities || context.systemStatuses.utilities === "fresh"
        ? "ok"
        : "review";
  }
  if (target === "roadway") {
    return context.roads || context.systemStatuses.roads === "fresh" ? "ok" : "review";
  }
  if (target === "landscape") {
    return context.buildingPlacements.some((value) => ["open_space", "amenity", "pool", "sidewalk"].includes(value.type ?? ""))
      ? "ok"
      : "idle";
  }
  if (target === "reports" || target === "quantities" || target === "deliverables") {
    return context.backendResultPresent ? "ok" : "idle";
  }
  if (target === "standards") {
    return context.minSlopePct || context.maxRoadGradePct || context.pipeMinSlopePct || context.maxAdaCrossSlopePct
      ? "ok"
      : "review";
  }
  if (target === "templates") {
    return context.customerTemplateBlockerCount > 0 ? "review" : context.customerTemplates ? "ok" : "idle";
  }
  if (target === "catalogs") {
    return Number(context.utilityCatalog?.summary?.review_required_count ?? 0) > 0
      ? "review"
      : context.utilityCatalog
        ? "ok"
        : "idle";
  }
  if (target === "libraries" || target === "settings" || target === "chat" || target === "projects") {
    return "ok";
  }
  return "idle";
}
