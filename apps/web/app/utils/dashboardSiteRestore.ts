import type { BuildingPlacement, MapAnalysis, ProjectInput, SurveySlopeResponse } from "../types";
import { uploadedImageSrc } from "./auth";
import { mapSurveyPointsToSite } from "./dashboardExistingConditionsUpload";
import { parsePositiveNumber } from "./formatting";
import { buildAssumedSlopeEstimate } from "./workflowConstants";

export function buildDashboardSiteRestore(projectInput: ProjectInput, token: string | null) {
  const site = projectInput.meta?.site_inputs ?? {};
  const lot = projectInput.manual_fields?.lot;
  const width = parsePositiveNumber(lot?.w);
  const height = parsePositiveNumber(lot?.h);
  const points = Array.isArray(site.survey_points) ? site.survey_points as number[][] : [];
  const imported = (site as Record<string, unknown>).existing_conditions_import as Record<string, unknown> | undefined;
  const grading = projectInput.manual_fields?.grading as Record<string, unknown> | undefined;
  const assumedSlope = typeof grading?.assumed_terrain_slope_pct === "number" ? grading.assumed_terrain_slope_pct : null;
  const scale = site.detection_scale ?? {};
  const rotation = typeof site.site_rotation_deg === "number" ? site.site_rotation_deg : 0;
  const imageUrl = String(site.map_snapshot?.image_url || projectInput.image_path || "");
  return {
    siteAddress: String(site.address || ""),
    surveyFileName: String(site.survey_file?.stored_filename || ""),
    sourceEffectRows: Array.isArray(imported?.source_effect_rows) ? imported.source_effect_rows.map(String) : [],
    surveySlopeEstimate: (site.slope_estimate ?? (assumedSlope !== null ? buildAssumedSlopeEstimate(assumedSlope) : null)) as SurveySlopeResponse | null,
    useSurveyForGrading: site.use_survey_for_grading !== undefined ? Boolean(site.use_survey_for_grading) : assumedSlope === null,
    surveyPoints: points,
    surveyPreviewPoints: mapSurveyPointsToSite(points, width, height),
    drainageSourceOverride: (site.drainage_source_override === "user" ? "user" : "civora") as "user" | "civora",
    surveyDiagnostics: {
      fileType: site.survey_file_type, parseSuccess: site.survey_parse_success,
      pointCount: site.survey_point_count, recognizedColumns: site.survey_point_columns,
      invalidRows: site.survey_invalid_rows, bounds: site.survey_bounds ?? undefined,
      elevationRange: site.survey_elevation_range ?? undefined, warnings: site.survey_point_warnings,
    },
    detectionScaleFeet: scale.distance_ft ? String(scale.distance_ft) : "",
    detectionScalePixels: scale.pixel_distance ? String(scale.pixel_distance) : "",
    detectionScaleFtPerPx: typeof scale.scale_ft_per_px === "number" ? scale.scale_ft_per_px : null,
    detectionScaleSource: (scale.scale_source === "mapbox" || scale.scale_source === "manual" ? scale.scale_source : "approximate") as "mapbox" | "manual" | "approximate",
    siteScaleLocked: Boolean(site.site_alignment_locked && width && height),
    siteRotationDeg: rotation,
    siteRotationInput: String(rotation),
    detectedPlacements: (Array.isArray(site.detected_objects) ? site.detected_objects : []) as BuildingPlacement[],
    uploadedImageApiUrl: imageUrl ? uploadedImageSrc(imageUrl, token ?? "") : "",
    mapSnapshotPath: String(site.map_snapshot?.image_path || ""),
    mapAnalysis: (site.map_analysis ?? null) as MapAnalysis | null,
  };
}

export type DashboardSiteRestoreState = ReturnType<typeof buildDashboardSiteRestore>;
