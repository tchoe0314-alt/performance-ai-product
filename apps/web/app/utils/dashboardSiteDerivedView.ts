import type { BuildingPlacement, ProjectRecord } from "../types";
import { siteAreaAcresFromSize } from "./workflowConstants";
import { parsePositiveNumber } from "./formatting";

type LotBounds = {
  x?: number;
  y?: number;
  w: number;
  h: number;
};

type DetectionPlacement = {
  confidence?: number;
};

export function buildDashboardSiteDerivedView<TDetection extends DetectionPlacement>({
  lotBounds,
  lotWidth,
  lotHeight,
  mapSnapshotPath,
  buildingPlacements,
  drainageSummary,
  mapAnalysis,
  detectedPlacements,
  detectionConfidenceFilter,
  projects,
  siteWarningAcres,
  siteGradingHardBlockAcres,
}: {
  lotBounds: LotBounds;
  lotWidth: string;
  lotHeight: string;
  mapSnapshotPath: string;
  buildingPlacements: BuildingPlacement[];
  drainageSummary: Record<string, unknown>;
  mapAnalysis: unknown;
  detectedPlacements: TDetection[];
  detectionConfidenceFilter: "all" | "medium" | "high";
  projects: ProjectRecord[];
  siteWarningAcres: number;
  siteGradingHardBlockAcres: number;
}) {
  const siteAreaAcres = siteAreaAcresFromSize(lotBounds.w, lotBounds.h);
  const placedObjects = buildingPlacements.filter((item) => item.placed && item.type !== "site");
  const pendingPlacementObjects = buildingPlacements.filter((item) => !item.placed && item.type !== "site");
  const hasUtilityConnectionObject = buildingPlacements.some((item) =>
    ["utility_corridor", "hydrant", "manhole", "inlet"].includes(item.type ?? "") ||
    ["public_water", "public_sanitary", "storm_sewer"].includes(String(item.meta?.utilityKind || "")),
  );
  const hasUtilityConnectionPlaced = buildingPlacements.some((item) =>
    item.placed &&
    (["utility_corridor", "hydrant", "manhole", "inlet"].includes(item.type ?? "") ||
      ["public_water", "public_sanitary", "storm_sewer"].includes(String(item.meta?.utilityKind || ""))),
  );
  const drainageSurfaceSummary = (() => {
    if (!drainageSummary || typeof drainageSummary !== "object") {
      return {
        surfaceSource: "unknown",
        surfaceQuality: "",
        surfaceDetail: "",
        surfaceFromGrading: false,
      };
    }
    const guidance = (drainageSummary as { surface_guidance?: Record<string, unknown> }).surface_guidance ?? {};
    return {
      surfaceSource: String(guidance.surface_source || "unknown"),
      surfaceQuality: String(guidance.surface_source_quality || ""),
      surfaceDetail: String(guidance.surface_source_detail || ""),
      surfaceFromGrading: Boolean(guidance.surface_from_grading),
    };
  })();
  const mapAnalysisCounts = (() => {
    if (!mapAnalysis || typeof mapAnalysis !== "object") return { zones: 0, objects: 0, centerlines: 0 };
    const record = mapAnalysis as { counts?: { zones?: number; objects?: number; centerlines?: number } };
    return {
      zones: record.counts?.zones ?? 0,
      objects: record.counts?.objects ?? 0,
      centerlines: record.counts?.centerlines ?? 0,
    };
  })();
  const detectionThreshold =
    detectionConfidenceFilter === "high" ? 0.6 : detectionConfidenceFilter === "medium" ? 0.3 : 0.0;
  return {
    siteAreaAcres,
    siteTooLargeForWarning: siteAreaAcres > siteWarningAcres,
    siteTooLargeForGrading: siteAreaAcres > siteGradingHardBlockAcres,
    missingSite: !(lotBounds.w && lotBounds.h),
    missingImage: !mapSnapshotPath,
    placedObjects,
    pendingPlacementObjects,
    pendingPlacementLabels: pendingPlacementObjects.map((item) => item.label),
    hasBasinObject: buildingPlacements.some((item) => item.type === "basin"),
    hasBasinPlaced: buildingPlacements.some((item) => item.type === "basin" && item.placed),
    hasUtilityConnectionObject,
    hasUtilityConnectionPlaced,
    siteSizeSet: Boolean(parsePositiveNumber(lotWidth) && parsePositiveNumber(lotHeight)),
    drainageSurfaceSummary,
    mapAnalysisCounts,
    filteredDetectedPlacements: detectedPlacements.filter((item) => (item.confidence ?? 0) >= detectionThreshold),
    sortedProjects: [...projects].sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0)),
  };
}
