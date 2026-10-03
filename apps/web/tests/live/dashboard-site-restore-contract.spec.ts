import { expect, test } from "@playwright/test";
import { buildDashboardSiteRestore } from "../../app/utils/dashboardSiteRestore";
import { buildDashboardProjectInputView } from "../../app/utils/dashboardProjectInputView";
import type { ProjectInput } from "../../app/types";
import { uploadedImageSrc } from "../../app/utils/auth";

test("missing saved context restores blank fields instead of another project's state", () => {
  const restored = buildDashboardSiteRestore({}, null);
  expect(restored.siteAddress).toBe("");
  expect(restored.detectedPlacements).toEqual([]);
  expect(restored.surveyPoints).toEqual([]);
  expect(restored.surveySlopeEstimate).toBeNull();
  expect(restored.mapAnalysis).toBeNull();
  expect(restored.uploadedImageApiUrl).toBe("");
  expect(restored.siteScaleLocked).toBe(false);
  expect(buildDashboardProjectInputView({}, undefined).mergedPlacements).toEqual([]);
});

test("source restoration uses saved lot dimensions, keeps geometry, and does not mutate input", () => {
  const input: ProjectInput = { manual_fields: { lot: { x: 0, y: 0, w: 500, h: 400 } }, meta: { site_inputs: {
    address: "Fixture address", site_alignment_locked: true, site_rotation_deg: 20,
    survey_points: [[10, 20, 30], [40, 50, 60]], use_survey_for_grading: true,
    detection_scale: { distance_ft: 100, pixel_distance: 200, scale_ft_per_px: 0.5, scale_source: "manual" },
  } } };
  const before = JSON.stringify(input);
  const restored = buildDashboardSiteRestore(input, null);
  expect(restored.siteScaleLocked).toBe(true);
  expect(restored.siteRotationInput).toBe("20");
  expect(restored.surveyPreviewPoints).toEqual([{ x: 10, y: 20, z: 30 }, { x: 40, y: 50, z: 60 }]);
  expect(restored.detectionScaleFtPerPx).toBe(0.5);
  expect(JSON.stringify(input)).toBe(before);
  expect(buildDashboardSiteRestore({ meta: input.meta }, null).siteScaleLocked).toBe(false);
});

test("saved assumed slope remains assumed rather than silently selecting survey", () => {
  const input = { manual_fields: { grading: { assumed_terrain_slope_pct: 6 } } } as ProjectInput;
  const restored = buildDashboardSiteRestore(input, null);
  expect(restored.useSurveyForGrading).toBe(false);
  expect(restored.surveySlopeEstimate?.slope_percent).toBe(6);
});

test("restoration preserves the saved upload when no map snapshot image exists", () => {
  const input: ProjectInput = { image_path: "uploads/saved-site.png" };
  expect(buildDashboardSiteRestore(input, "fixture-token").uploadedImageApiUrl).toBe(uploadedImageSrc(input.image_path!, "fixture-token"));
  input.meta = { site_inputs: { map_snapshot: { image_url: "/api/uploads/map.png" } } };
  expect(buildDashboardSiteRestore(input, "fixture-token").uploadedImageApiUrl).toBe(uploadedImageSrc("/api/uploads/map.png", "fixture-token"));
  expect(buildDashboardSiteRestore(input, null).uploadedImageApiUrl).toBe("");
});
