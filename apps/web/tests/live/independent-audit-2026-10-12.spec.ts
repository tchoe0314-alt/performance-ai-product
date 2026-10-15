import { test, expect } from "@playwright/test";
import type { BuildingPlacement } from "../../app/types";
import { buildDashboardManualFields } from "../../app/utils/dashboardManualFields";
import { geometry } from "../../app/utils/culDeSacConcept";
import { defaultCulDeSacParameters, regenerateCulDeSac, culDeSacFrame } from "../../app/utils/parametricRoad";
import { assessSiteInterference } from "../../app/utils/siteInterference";
import { withCanonicalCanvasSnapshot, resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import { resolveDashboardExportBlockReason } from "../../app/utils/dashboardExportActions";

// Independent acceptance probes. A red probe is retained as an audit finding,
// not waived or rewritten to match the current implementation.
const fields = (setback: string, parking: string) => buildDashboardManualFields({
  nextSiteName: "Independent audit", nextFileName: "audit", nextUnits: "ft", nextProjectType: "commercial",
  nextLotWidth: "900", nextLotHeight: "700", nextSetback: setback,
  nextBuildingWidth: "", nextBuildingDepth: "", nextBuildingCount: "0", nextParkingCount: parking,
  nextMinSlopePct: "", nextPipeMinSlopePct: "", nextMaxParkingSlopePct: "", nextMaxRoadGradePct: "", nextMaxAdaCrossSlopePct: "",
  nextRoads: false, nextGrading: false, nextDrainage: false, nextUtilities: false,
  buildingPlacements: [], drainageForcedInlets: [], drainageConnectOrphans: false,
  drainageAllowSlopeAdjust: false, drainageMaxSlopeAdjust: 0,
});

test("explicit zero setback remains zero in the actual save/calculation field builder", () => {
  expect(fields("0", "140").setback).toBe(0);
});

test("explicit zero parking remains distinct from an unspecified parking requirement", () => {
  expect(fields("20", "0").site_plan?.parking_count).toBe(0);
});

test("blank setback and parking stay unknown, never silently become zero", () => {
  const result = fields("", "");
  expect(result.setback).toBeUndefined();
  expect(result.site_plan?.parking_count).toBeUndefined();
});

test("master-plan preliminary export policy does not use staleness alone as a universal veto", () => {
  // Governing Rule 10 permits disclosed preliminary exports where representation
  // is safe. Current implementation needs a separate safe geometry-only path;
  // this failure is NOT permission to remove stale-result safety guards.
  const requestedSafeMode = { token: "local-audit", backendResultPresent: true,
    projectId: "local-project", systemStatuses: { grading: "stale" as const }, staleOutputs: ["grading"], exportScope: "review" as const,
    // Separate drawing-only path; the original calculation gates remain intact.
    exportSource: "current_geometry_only" as const, geometryIsCurrent: true,
    geometryValid: true, unitsKnown: true, preliminaryAcknowledged: true,
    includeStaleCalculationDisclosures: true,
  };
  expect(resolveDashboardExportBlockReason(requestedSafeMode)).toBe("");
});

test("all supported radius/width transitions remain finite and analytically tangent", () => {
  for (let radius = 35; radius <= 80; radius += 5) for (let width = 20; width <= 48; width += 2) {
    const g = geometry(radius, width);
    expect(Object.values(g).every(Number.isFinite)).toBe(true);
    expect(Math.hypot(g.tx, g.ty)).toBeCloseTo(radius, 8);
    expect(Math.hypot(g.tx - g.x, g.ty - g.y)).toBeCloseTo(g.f, 8);
    const a = [g.tx, g.ty], b = [g.tx - g.x, g.ty - g.y];
    expect(Math.abs(a[0] * b[1] - a[1] * b[0])).toBeLessThan(1e-8);
  }
});

test("large-coordinate feet/meters roads survive exact JSON round trips and frame inversion", () => {
  for (const units of ["ft", "m"] as const) for (const angle of [0, 37, 90, 179, 270, 359]) {
    const road = regenerateCulDeSac({ id: "road", label: "Road", type: "road", placed: true,
      x: 1e6, y: -1e6, w: 100, d: 200, rotation: angle,
      meta: { cul_de_sac_v1: { ...defaultCulDeSacParameters(units), roadWidthFt: 48, bulbRadiusFt: 35 } } });
    const frame = culDeSacFrame(road)!;
    const local: [number, number] = [23.125, -11.5];
    const restoredPoint = frame.toLocal(frame.toWorld(local));
    expect(restoredPoint[0]).toBeCloseTo(local[0], 7); expect(restoredPoint[1]).toBeCloseTo(local[1], 7);
    const input = { manual_fields: { units, site_objects: [{ ...road, name: road.label, geometry_type: road.geometryType }] } };
    const snapshot = withCanonicalCanvasSnapshot(input);
    const restored = resolveCanonicalCanvasInput(JSON.parse(JSON.stringify(snapshot)));
    expect(restored.manual_fields?.site_objects?.[0].geometry).toEqual(road.geometry);
    expect(restored.manual_fields?.site_objects?.[0].meta?.cul_de_sac_v1).toEqual(road.meta?.cul_de_sac_v1);
  }
});

test("hiding any actual physical obstacle never makes its overlap disappear", () => {
  const building: BuildingPlacement = { id: "office", label: "Office", type: "building", placed: true, x: 0, y: 0, w: 40, d: 40 };
  for (const type of ["building", "road", "parking", "sidewalk", "basin", "no_build_zone", "hydrant"] as const) {
    const other: BuildingPlacement = { ...building, id: "other", label: "Obstacle", type };
    const visible = assessSiteInterference([building, other]);
    expect(visible.length).toBeGreaterThan(0);
    expect(assessSiteInterference([building, { ...other, meta: { ui_hidden: true } }])).toEqual(visible);
  }
});
