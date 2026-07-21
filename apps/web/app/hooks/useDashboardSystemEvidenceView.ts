import { useMemo } from "react";

import type { BuildingPlacement, Issue } from "../types";
import { buildDashboardSystemEvidenceView } from "../utils/dashboardSystemEvidenceView";
import type { EngineeringSystemKey, SystemStatus } from "../utils/workflowConstants";

type UseDashboardSystemEvidenceViewInput = {
  appliedAddressLabel: string;
  buildingPlacements: BuildingPlacement[];
  coordinateSystem: string;
  hasAppliedAddress: boolean;
  hasAssumedTerrainSlope: boolean;
  hasBasinObject: boolean;
  hasBasinPlaced: boolean;
  hasLocationEvidence: boolean;
  hasStandardsEvidence: boolean;
  hasTerrainSource: boolean;
  hasUtilityConnectionObject: boolean;
  hasUtilityConnectionPlaced: boolean;
  hasVerifiedSurveyControl: boolean;
  issues: Issue[];
  mapAnalysisSuccess: boolean;
  missingSite: boolean;
  onlineSourceLookupLabel: string;
  onlineSourceLookupUnavailable: boolean;
  siteScaleLocked: boolean;
  siteTooLargeForGrading: boolean;
  systemStatuses: Record<EngineeringSystemKey, SystemStatus>;
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
  utilities: unknown;
};

export function useDashboardSystemEvidenceView({
  appliedAddressLabel,
  buildingPlacements,
  coordinateSystem,
  hasAppliedAddress,
  hasAssumedTerrainSlope,
  hasBasinObject,
  hasBasinPlaced,
  hasLocationEvidence,
  hasStandardsEvidence,
  hasTerrainSource,
  hasUtilityConnectionObject,
  hasUtilityConnectionPlaced,
  hasVerifiedSurveyControl,
  issues,
  mapAnalysisSuccess,
  missingSite,
  onlineSourceLookupLabel,
  onlineSourceLookupUnavailable,
  siteScaleLocked,
  siteTooLargeForGrading,
  systemStatuses,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  utilities,
}: UseDashboardSystemEvidenceViewInput) {
  return useMemo(
    () =>
      buildDashboardSystemEvidenceView({
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
      }),
    [
      appliedAddressLabel,
      buildingPlacements,
      coordinateSystem,
      hasAppliedAddress,
      hasAssumedTerrainSlope,
      hasBasinObject,
      hasBasinPlaced,
      hasLocationEvidence,
      hasStandardsEvidence,
      hasTerrainSource,
      hasUtilityConnectionObject,
      hasUtilityConnectionPlaced,
      hasVerifiedSurveyControl,
      issues,
      mapAnalysisSuccess,
      missingSite,
      onlineSourceLookupLabel,
      onlineSourceLookupUnavailable,
      siteScaleLocked,
      siteTooLargeForGrading,
      systemStatuses,
      uploadedImageApiUrl,
      uploadedImagePreviewUrl,
      utilities,
    ],
  );
}
