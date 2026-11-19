import { test, expect } from "@playwright/test";
import { buildDashboardGradingEarthworkUx, shouldShowCurrentGradingComparison } from "../../app/utils/dashboardGradingEarthworkView";

test("an uncalculated site has no invented earthwork, elevation or pad checks", () => {
  const view = buildDashboardGradingEarthworkUx({ lotBounds: { w: 300, h: 200 },
    gradingSummary: {}, cutFillNet: null, managerMetrics: {}, buildingPlacements: [],
    gradingBlocker: null, siteTooLargeForGrading: false, gradingResultSummary: {},
    gradingSourceSummary: "No survey", hasGradingSurface: false });
  expect(view.heatmapCells).toEqual([]);
  expect(view.padTieIns).toEqual([]);
  expect(view.haulBalance.cutCf).toBeNull();
  expect(view.haulBalance.fillCf).toBeNull();
  expect(view.surfaceComparison.deltaLabel).toBe("Surface comparison not calculated");
  expect(view.retainingWall.label).toBe("Not assessed");
});

test("known surface cells preserve signed cut/fill depth and exact volumes", () => {
  const view = buildDashboardGradingEarthworkUx({ lotBounds: { w: 20, h: 10 },
    gradingSummary: { earthwork: { cut_cf: 100, fill_cf: 200, net_cf: 100 }, surface_model: {
      schema_version: "surface_artifact_v1", model: "grid", source_type: "survey-backed",
      control_verified: true, bounds: [0, 0, 20, 10], surface_comparison: { cells: [
        { x: 5, y: 5, width: 10, height: 10, existing_elevation_ft: 101, proposed_elevation_ft: 100, delta_ft: -1, cut_cf: 100, fill_cf: 0, mode: "cut" },
        { x: 15, y: 5, width: 10, height: 10, existing_elevation_ft: 100, proposed_elevation_ft: 102, delta_ft: 2, cut_cf: 0, fill_cf: 200, mode: "fill" },
      ] }, contours: [], spot_elevations: [], slope_arrows: [], flow_paths: [] } },
    cutFillNet: null, managerMetrics: {}, buildingPlacements: [], gradingBlocker: null,
    siteTooLargeForGrading: false, gradingResultSummary: { sourceQuality: "survey-backed" },
    gradingSourceSummary: "Survey/topo", hasGradingSurface: true });
  expect(view.surfaceModel?.comparisonCells.map(cell => [cell.mode, cell.deltaFt])).toEqual([["cut", -1], ["fill", 2]]);
  expect(view.haulBalance).toMatchObject({ cutCf: 100, fillCf: 200, netCf: 100, direction: "unknown", label: "Haul not assessed" });
  expect(view.heatmapCells).toHaveLength(2);
  expect(view.padTieIns).toEqual([]);
});

test("saved grading revision is hidden as soon as an edit makes grading stale", () => {
  expect(shouldShowCurrentGradingComparison({ hasGradingSurface: true, gradingStatus: "fresh", resultCurrent: true })).toBe(true);
  expect(shouldShowCurrentGradingComparison({ hasGradingSurface: true, gradingStatus: "not_generated", resultCurrent: true })).toBe(true);
  expect(shouldShowCurrentGradingComparison({ hasGradingSurface: true, gradingStatus: "stale", resultCurrent: true })).toBe(false);
  expect(shouldShowCurrentGradingComparison({ hasGradingSurface: true, gradingStatus: "fresh", resultCurrent: false })).toBe(false);
  expect(shouldShowCurrentGradingComparison({ hasGradingSurface: false, gradingStatus: "fresh", resultCurrent: true })).toBe(false);
});
