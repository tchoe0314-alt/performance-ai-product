import { expect, test } from "@playwright/test";
import { buildDashboardSystemReadinessRows, getDashboardSystemBlockers, type DashboardSystemBlockerContext } from "../../app/utils/dashboardSystemReadiness";
import { applyDashboardReactiveSystemStatusFromPlanResult } from "../../app/utils/dashboardPlanResultView";

const context: DashboardSystemBlockerContext = {
  missingSite: false, siteScaleLocked: true, siteTooLargeForGrading: false,
  hasTerrainSource: false, hasStandardsEvidence: false, hasAppliedAddress: false,
  onlineSourceLookupUnavailable: false, hasAssumedTerrainSlope: false, hasVerifiedSurveyControl: false,
  hasBasinPlaced: false, hasBasinObject: false, buildingPlacements: [],
  confirmedObjectCounts: { buildings: 1, access: 0 }, utilities: null,
  hasUtilityConnectionPlaced: false, hasUtilityConnectionObject: false, hasHardSystemBlock: false,
};

test("parking has its own selective target and its own freshness", () => {
  const rows = buildDashboardSystemReadinessRows({ blockerContext: context, systemStatuses: {
    roads: "fresh", parking: "stale", grading: "not_generated", drainage: "not_generated", utilities: "not_generated",
  } });
  expect(rows.find(row => row.key === "parking")).toMatchObject({ runTarget: "parking", status: "stale", panel: "roadway" });
  expect(rows.find(row => row.key === "roadway")).toMatchObject({ runTarget: "roads", status: "fresh" });
});

test("parking reports site, standards, layout and active model blockers without inventing terrain requirements", () => {
  expect(getDashboardSystemBlockers("parking", context)).toEqual(["missing standards"]);
  const blockers = getDashboardSystemBlockers("parking", { ...context, missingSite: true, siteScaleLocked: false,
    confirmedObjectCounts: { buildings: 0, access: 0 }, hasHardSystemBlock: true });
  expect(blockers).toContain("Set site width and depth.");
  expect(blockers).toContain("Lock the site boundary.");
  expect(blockers).toContain("Add at least one building, entrance, driveway, road, or parking object.");
  expect(blockers).toContain("Resolve active hard model blockers.");
  expect(blockers.some(value => value.includes("terrain"))).toBe(false);
});

test("reopening a successful selective calculation restores only that system's freshness", () => {
  const previous = { roads: "stale", parking: "stale", grading: "stale", drainage: "stale", utilities: "stale" } as const;
  const result = { success: true, metadata: { calculation_scope_v1: { version: 1, requested_system: "parking" as const, omitted_fields: ["grading", "drainage", "utility_network"] } } };
  expect(applyDashboardReactiveSystemStatusFromPlanResult(result, previous)).toEqual({ ...previous, parking: "fresh" });
  expect(applyDashboardReactiveSystemStatusFromPlanResult({ ...result, success: false }, previous)).toEqual(previous);
  expect(applyDashboardReactiveSystemStatusFromPlanResult({ ...result, metadata: { calculation_scope_v1: { ...result.metadata.calculation_scope_v1, requested_system: "full" } } }, previous)).toEqual(previous);
});
