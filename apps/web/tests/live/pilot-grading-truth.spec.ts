import { test, expect } from "@playwright/test";
import { buildDashboardGradingEarthworkUx } from "../../app/utils/dashboardGradingEarthworkView";

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
