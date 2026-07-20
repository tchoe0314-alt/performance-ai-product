import type { BuildingPlacement, Issue } from "../types";
import {
  buildDashboardConfirmedObjectCounts,
  buildDashboardExistingConditionRows,
} from "./dashboardEvidenceSummaries";
import {
  buildDashboardSystemReadinessRows,
  type DashboardSystemBlockerContext,
} from "./dashboardSystemReadiness";
import type { EngineeringSystemKey, SystemStatus } from "./workflowConstants";

export function buildDashboardSystemEvidenceView({
  buildingPlacements,
  issues,
  siteTooLargeForGrading,
  hasAppliedAddress,
  appliedAddressLabel,
  hasLocationEvidence,
  hasVerifiedSurveyControl,
  coordinateSystem,
  hasTerrainSource,
  mapAnalysisSuccess,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  onlineSourceLookupLabel,
  missingSite,
  siteScaleLocked,
  hasStandardsEvidence,
  onlineSourceLookupUnavailable,
  hasAssumedTerrainSlope,
  hasBasinPlaced,
  hasBasinObject,
  utilities,
  hasUtilityConnectionPlaced,
  hasUtilityConnectionObject,
  systemStatuses,
}: {
  buildingPlacements: BuildingPlacement[];
  issues: Issue[];
  siteTooLargeForGrading: boolean;
  hasAppliedAddress: boolean;
  appliedAddressLabel: string;
  hasLocationEvidence: boolean;
  hasVerifiedSurveyControl: boolean;
  coordinateSystem: string;
  hasTerrainSource: boolean;
  mapAnalysisSuccess: boolean;
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
  onlineSourceLookupLabel: string;
  missingSite: boolean;
  siteScaleLocked: boolean;
  hasStandardsEvidence: boolean;
  onlineSourceLookupUnavailable: boolean;
  hasAssumedTerrainSlope: boolean;
  hasBasinPlaced: boolean;
  hasBasinObject: boolean;
  utilities: unknown;
  hasUtilityConnectionPlaced: boolean;
  hasUtilityConnectionObject: boolean;
  systemStatuses: Record<EngineeringSystemKey, SystemStatus>;
}) {
  const confirmedObjectCounts = buildDashboardConfirmedObjectCounts(buildingPlacements);
  const hasHardSystemBlock = issues.some((issue) => issue.severity === "error") || siteTooLargeForGrading;
  const existingConditionRows = buildDashboardExistingConditionRows({
    hasAppliedAddress,
    appliedAddressLabel,
    hasLocationEvidence,
    hasVerifiedSurveyControl,
    coordinateSystem,
    hasTerrainSource,
    mapAnalysisSuccess,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
    onlineSourceLookupLabel,
  });
  const systemBlockerContext: DashboardSystemBlockerContext = {
    missingSite,
    siteScaleLocked,
    siteTooLargeForGrading,
    hasTerrainSource,
    hasStandardsEvidence,
    hasAppliedAddress,
    onlineSourceLookupUnavailable,
    hasAssumedTerrainSlope,
    hasVerifiedSurveyControl,
    hasBasinPlaced,
    hasBasinObject,
    buildingPlacements,
    confirmedObjectCounts,
    utilities,
    hasUtilityConnectionPlaced,
    hasUtilityConnectionObject,
    hasHardSystemBlock,
  };
  const systemReadinessRows = buildDashboardSystemReadinessRows({
    systemStatuses,
    blockerContext: systemBlockerContext,
  });

  return {
    confirmedObjectCounts,
    hasHardSystemBlock,
    existingConditionRows,
    systemBlockerContext,
    systemReadinessRows,
  };
}
