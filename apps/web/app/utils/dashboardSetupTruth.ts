import type { SiteInputs } from "../types";

type SurveySlopeLike = {
  slope_percent?: number | string | null;
  point_count?: number | string | null;
} | null;

type BuildDashboardSetupTruthOptions = {
  siteInputs: SiteInputs;
  siteAddress: string;
  siteScaleLocked: boolean;
  uploadedImageApiUrl?: string | null;
  uploadedImagePreviewUrl?: string | null;
  surveyFileName?: string | null;
  surveyPreviewPointCount: number;
  surveySlopeEstimate?: SurveySlopeLike;
  debugNoTerrain: boolean;
  useSurveyForGrading: boolean;
  standardsEvidenceValues: unknown[];
};

export type DashboardSetupTruth = {
  appliedAddressLabel: string;
  hasAppliedAddress: boolean;
  hasLocationEvidence: boolean;
  hasVerifiedSurveyControl: boolean;
  hasAssumedTerrainSlope: boolean;
  hasTerrainSource: boolean;
  hasStandardsEvidence: boolean;
  pendingAddressEdit: boolean;
  localAddressLocked: boolean;
  addressNeedsApply: boolean;
};

export function buildDashboardSetupTruth({
  siteInputs,
  siteAddress,
  siteScaleLocked,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  surveyFileName,
  surveyPreviewPointCount,
  surveySlopeEstimate,
  debugNoTerrain,
  useSurveyForGrading,
  standardsEvidenceValues,
}: BuildDashboardSetupTruthOptions): DashboardSetupTruth {
  const appliedAddressLabel = String(siteInputs?.address || siteInputs?.geocode?.display_name || "").trim();
  const hasAppliedAddress = Boolean(appliedAddressLabel || (siteInputs?.geocode?.lat && siteInputs?.geocode?.lng));
  const hasLocationEvidence =
    hasAppliedAddress ||
    Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng) ||
    Boolean(uploadedImageApiUrl || uploadedImagePreviewUrl);
  const hasVerifiedSurveyControl = Boolean(surveyFileName && surveyPreviewPointCount);
  const hasAssumedTerrainSlope =
    Boolean(surveySlopeEstimate?.slope_percent) &&
    Number(surveySlopeEstimate?.point_count ?? 0) === 0;
  const discoveredTerrainSource = (siteInputs?.online_existing_conditions_discovery_v1?.sources ?? []).some((source) => {
    const sourceLabel = `${source.key || ""} ${source.label || ""} ${source.source_type || ""}`.toLowerCase();
    return Number(source.candidate_count ?? 0) > 0 && /terrain|elevation|contour|dem|lidar|topo/.test(sourceLabel);
  });
  const hasTerrainSource =
    !debugNoTerrain &&
    ((Boolean(surveyFileName) && useSurveyForGrading) ||
      discoveredTerrainSource ||
      Boolean(surveySlopeEstimate?.slope_percent));
  const hasStandardsEvidence = standardsEvidenceValues.some(Boolean);
  const trimmedSiteAddress = siteAddress.trim();
  const pendingAddressEdit = Boolean(
    trimmedSiteAddress &&
      trimmedSiteAddress !== String(siteInputs?.address || siteInputs?.geocode?.display_name || "").trim(),
  );
  const localAddressLocked = Boolean(!hasAppliedAddress && siteScaleLocked && trimmedSiteAddress);
  const addressNeedsApply = Boolean(
    !localAddressLocked && (pendingAddressEdit || (trimmedSiteAddress && !hasAppliedAddress)),
  );

  return {
    appliedAddressLabel,
    hasAppliedAddress,
    hasLocationEvidence,
    hasVerifiedSurveyControl,
    hasAssumedTerrainSlope,
    hasTerrainSource,
    hasStandardsEvidence,
    pendingAddressEdit,
    localAddressLocked,
    addressNeedsApply,
  };
}
