import { expect, test } from "@playwright/test";
import { parseNonNegativeNumber, parseNonNegativeInteger, parsePositiveNumber } from "../../app/utils/formatting";
import { projectEditKey } from "../../app/hooks/useProjectTabBranch";
import { buildDashboardManualFields } from "../../app/utils/dashboardManualFields";
import { resolveCanonicalCanvasInput, withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";

const fields = (overrides: Partial<Parameters<typeof buildDashboardManualFields>[0]> = {}) => buildDashboardManualFields({
  nextSiteName: "Empty canvas renamed", nextFileName: "empty-plan", nextUnits: "ft", nextProjectType: "commercial",
  nextLotWidth: "900", nextLotHeight: "700", nextSetback: "0", nextBuildingWidth: "", nextBuildingDepth: "",
  nextBuildingCount: "0", nextParkingCount: "0", nextMinSlopePct: "", nextPipeMinSlopePct: "",
  nextMaxParkingSlopePct: "", nextMaxRoadGradePct: "", nextMaxAdaCrossSlopePct: "",
  nextRoads: false, nextGrading: false, nextDrainage: false, nextUtilities: false,
  buildingPlacements: [], drainageForcedInlets: [], drainageConnectOrphans: false,
  drainageAllowSlopeAdjust: false, drainageMaxSlopeAdjust: 0,
  ...overrides,
});

test("zero percentage requirements survive while invalid percentages remain absent", () => {
  const zero = fields({ nextMinSlopePct: "0", nextPipeMinSlopePct: "0", nextMaxParkingSlopePct: "0", nextMaxRoadGradePct: "0", nextMaxAdaCrossSlopePct: "0" });
  expect(zero.grading).toMatchObject({ min_slope_pct: 0, max_parking_slope_pct: 0, max_road_grade_pct: 0, max_ada_cross_slope_pct: 0 });
  expect(zero.drainage?.min_pipe_slope_pct).toBe(0);
  const bad = fields({ nextMaxRoadGradePct: "-1", nextMaxParkingSlopePct: "NaN" });
  expect(bad.grading?.max_road_grade_pct).toBeUndefined();
  expect(bad.grading?.max_parking_slope_pct).toBeUndefined();
});

test("nonnegative requirements distinguish explicit zero from blank and invalid inputs", () => {
  for (const value of [0, "0", " 0 ", "0.0"]) expect(parseNonNegativeNumber(value)).toBe(0);
  for (const value of [null, undefined, "", " ", -1, "-1", "NaN", Infinity, "1e309"]) expect(parseNonNegativeNumber(value)).toBeNull();
  expect(parseNonNegativeNumber("20.5")).toBe(20.5);
  expect(parsePositiveNumber(0)).toBeNull();
});

test("count controls never round fractional requirements or allocate unbounded placeholders", () => {
  expect(parseNonNegativeInteger("1.5")).toBeNull();
  expect(fields({ nextBuildingCount: "1000000000" }).buildings).toBeUndefined();
  expect(fields({ nextBuildingCount: "0" }).buildings).toEqual([]);
  expect(fields({ nextBuildingCount: "0" }).site_plan?.building_count).toBe(0);
  const before = { manual_fields: fields(), meta: { edit_controls_v1: { buildingCount: "" } } };
  const invalidDraft = { ...before, meta: { edit_controls_v1: { buildingCount: "-" } } };
  expect(projectEditKey(before)).not.toBe(projectEditKey(invalidDraft));
});

test("empty canvas saves new identity and requirements into the authoritative snapshot", () => {
  const old = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", setback: 20, site_objects: [] } });
  const live = fields();
  expect(live.site_objects).toEqual([]);
  const saved = withCanonicalCanvasSnapshot({ manual_fields: live }, old.canonical_project_v1);
  const reopened = resolveCanonicalCanvasInput(JSON.parse(JSON.stringify(saved)));
  expect(reopened.manual_fields?.project_name).toBe("Empty canvas renamed");
  expect(reopened.manual_fields?.setback).toBe(0);
  expect(reopened.manual_fields?.site_plan?.parking_count).toBe(0);
});

test("deleting the final object cannot retain or resurrect the old canonical drawing", () => {
  const old = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", site_objects: [
    { id: "last", name: "Last building", type: "building", x: 100, y: 100, w: 40, d: 40, placed: true },
  ] } });
  const saved = withCanonicalCanvasSnapshot({ manual_fields: fields() }, old.canonical_project_v1);
  expect(resolveCanonicalCanvasInput(saved).manual_fields?.site_objects).toEqual([]);
  expect(saved.canonical_project_v1?.buildings).toEqual([]);
});
