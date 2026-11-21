import { expect, test } from "@playwright/test";
import { parseNonNegativeNumber, parseNonNegativeInteger, parsePositiveNumber } from "../../app/utils/formatting";
import { projectEditKey } from "../../app/hooks/useProjectTabBranch";
import { buildDashboardManualFields } from "../../app/utils/dashboardManualFields";
import { resolveCanonicalCanvasInput, withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { detailedGeometryBinding, type CanonicalPipeProfile } from "../../app/utils/detailedObjectGeometry";

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

test("a single authored building keeps planner compatibility dimensions in sync with canonical edits", () => {
  const edited = fields({
    nextBuildingWidth: "160",
    nextBuildingDepth: "90",
    nextBuildingCount: "1",
    buildingPlacements: [{
      id: "office", label: "Office", type: "office_building", x: 100, y: 100,
      w: 170, d: 90, placed: true, source: "manual_drawn",
    }],
  });
  expect(edited.building_width).toBe(170);
  expect(edited.building_depth).toBe(90);
  expect(edited.site_objects?.find((item) => item.id === "office")?.w).toBe(170);
});

test("an edited generated concept keeps its authored width through recalculation payloads", () => {
  const edited = fields({
    nextBuildingWidth: "169",
    nextBuildingDepth: "85",
    nextBuildingCount: "1",
    buildingPlacements: [{
      id: "industrial-concept",
      label: "Industrial building concept",
      type: "industrial_building",
      x: 100,
      y: 100,
      w: 179,
      d: 85,
      placed: true,
      source: "manual_drawn",
      generated: true,
      meta: {
        generated_review_concept: true,
        requested_project_type: "industrial_site",
      },
    }],
  });

  expect(edited.building_width).toBe(179);
  expect(edited.building_depth).toBe(85);
  expect(edited.site_objects?.find((item) => item.id === "industrial-concept")).toMatchObject({
    w: 179,
    d: 85,
    source: "manual_drawn",
    generated: true,
    meta: { generated_review_concept: true },
  });
});

test("stale reviewed pipe evidence cannot fall back to an undetailed compatibility pipe", () => {
  const inlet = { id: "inlet", label: "Inlet", type: "inlet" as const, x: 0, y: 0, w: 1, d: 1, placed: true, source: "manual_drawn" as const };
  const outfall = { id: "outfall", label: "Outfall", type: "outfall" as const, x: 30, y: 40, w: 1, d: 1, placed: true, source: "manual_drawn" as const };
  const pipe = { id: "pipe", label: "Storm pipe", type: "utility_corridor" as const, x: 0, y: 0, w: 30, d: 40, placed: true, source: "manual_drawn" as const, geometryType: "polyline" as const, geometry: [[0,0],[30,40]] as [number,number][], meta: { network: "storm", coordinate_units: "ft", pipe_diameter_ft: 1 } };
  const profile:CanonicalPipeProfile = { version: 1, datum: "reviewed datum", source: "reviewed source", reviewed: true, requiredClearanceFt: null, geometryBinding: detailedGeometryBinding(pipe), network: "storm", centerElevationsFt: [100.5,100], invertElevationsFt: [100,99.5], endpointStructures: [{ id: inlet.id, name: inlet.label, x: 0, y: 0, rimElevationFt: 110, sumpElevationFt: 99 }, { id: outfall.id, name: outfall.label, x: 30, y: 40, rimElevationFt: 109, sumpElevationFt: 99 }] };
  const reviewed = { ...pipe, meta: { ...pipe.meta, pipe_profile_v1: profile } };
  expect(fields({ buildingPlacements: [inlet,outfall,reviewed] }).pipe_network).toHaveLength(1);
  expect(fields({ buildingPlacements: [{...inlet,x:10},outfall,reviewed] }).pipe_network).toEqual([]);
  expect(fields({ buildingPlacements: [inlet,outfall,{...pipe,meta:{...pipe.meta,pipe_profile_v1:undefined}}] }).pipe_network).toHaveLength(1);
});
