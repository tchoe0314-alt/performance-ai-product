import type {
  BuildingPlacement,
  ManagerMetrics,
  ProjectRecord,
  SiteInputs,
} from "../types";
import {
  buildDashboardGradingEarthworkUx,
  buildDashboardGradingSourceSummary,
} from "./dashboardGradingEarthworkView";
import { buildDashboardSiteDerivedView } from "./dashboardSiteDerivedView";

type LotBounds = {
  x?: number;
  y?: number;
  w: number;
  h: number;
};

type DetectionPlacement = {
  confidence?: number;
};

type GradingResultSummary = {
  sourceQuality?: string;
  sourceDetail?: string;
};

export function buildDashboardSiteGradingView<TDetection extends DetectionPlacement>({
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
  siteInputs,
  gradingSummary,
  cutFillNet,
  managerMetrics,
  gradingBlocker,
  gradingResultSummary,
  hasGradingSurface,
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
  siteInputs: SiteInputs | null | undefined;
  gradingSummary: Record<string, unknown>;
  cutFillNet: number | null | undefined;
  managerMetrics: ManagerMetrics;
  gradingBlocker: unknown;
  gradingResultSummary: GradingResultSummary;
  hasGradingSurface: boolean;
}) {
  const siteDerivedView = buildDashboardSiteDerivedView({
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
  });
  const gradingSourceSummary = buildDashboardGradingSourceSummary(siteInputs);
  const gradingEarthworkUx = buildDashboardGradingEarthworkUx({
    lotBounds,
    gradingSummary,
    cutFillNet,
    managerMetrics,
    buildingPlacements,
    gradingBlocker,
    siteTooLargeForGrading: siteDerivedView.siteTooLargeForGrading,
    gradingResultSummary,
    gradingSourceSummary,
    hasGradingSurface,
  });

  return {
    gradingEarthworkUx,
    gradingSourceSummary,
    siteDerivedView,
  };
}
