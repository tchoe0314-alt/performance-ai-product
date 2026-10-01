import { expect, test } from "@playwright/test";
import type { BuildingPlacement, ProjectInput } from "../../app/types";
import { assessSiteInterference, objectFootprints, type VerticalExtent } from "../../app/utils/siteInterference";
import { culDeSacFrame, defaultCulDeSacParameters, reconcileCulDeSacUpdate, regenerateCulDeSac } from "../../app/utils/parametricRoad";
import { checkFootprint, defaultLayout } from "../../app/utils/culDeSacConcept";
import { buildProjectInputPlacements } from "../../app/utils/projectInputRestore";
import { buildDashboardManualFields } from "../../app/utils/dashboardManualFields";
import { buildCanonicalGeometryHandoffV1 } from "../../app/utils/objectGeometry";

const building: BuildingPlacement = { id: "building", label: "Building", type: "building", x: 0, y: 0, w: 20, d: 20, placed: true };
const pipe: BuildingPlacement = { id: "pipe", label: "Pipe", type: "utility_corridor", x: -10, y: 10, w: 40, d: 1, placed: true, geometryType: "polyline", geometry: [[-10, 10], [30, 10]], meta: { asset_kind: "pipe", pipe_diameter_ft: 1 } };
const extent = (minFt: number, maxFt: number, extra: Partial<VerticalExtent> = {}): VerticalExtent => ({ version: 1, minFt, maxFt, datum: "project-benchmark", source: "reviewed test drawing", reviewed: true, requiredClearanceFt: 1, ...extra });
const withZ = (o: BuildingPlacement, z: VerticalExtent) => ({ ...o, meta: { ...o.meta, vertical_extent_v1: z } });

test("pipes are conditional crossings, never blanket exemptions", () => {
  expect(assessSiteInterference([building, pipe])[0].severity).toBe("review");
  expect(assessSiteInterference([withZ(building, extent(-2, 20)), withZ(pipe, extent(-6, -5))])[0].severity).toBe("clear");
  expect(assessSiteInterference([withZ(building, extent(-5.5, 20)), withZ(pipe, extent(-6, -5))])[0].code).toBe("physical_volume_contact");
  expect(assessSiteInterference([withZ(building, extent(-2, 20, { requiredClearanceFt: 4 })), withZ(pipe, extent(-6, -5))])[0].code).toBe("insufficient_vertical_clearance");
  for (const override of [{ datum: "other" }, { reviewed: false }, { requiredClearanceFt: null }, { source: "" }]) {
    expect(assessSiteInterference([withZ(building, extent(-2, 20)), withZ(pipe, extent(-6, -5, override))])[0].severity).toBe("review");
  }
  expect(assessSiteInterference([withZ(building, extent(-2, 20)), withZ(pipe, extent(-6, -5.5))])[0].code).toBe("pipe_envelope_incomplete");
  expect(assessSiteInterference([building, { ...pipe, geometry: [[-10, 50], [30, 50]] }])).toEqual([]);
});

test("broader object rules handle fixtures, connected access, restrictions and hidden/pending objects", () => {
  const other = (type: BuildingPlacement["type"]) => ({ ...building, id: "other", label: "Other", type });
  expect(assessSiteInterference([building, other("road")])[0].severity).toBe("conflict");
  expect(assessSiteInterference([other("road"), { ...other("sidewalk"), id: "path" }])).toEqual([]);
  expect(assessSiteInterference([building, other("hydrant")])[0].severity).toBe("review");
  expect(assessSiteInterference([building, other("no_build_zone")])[0].code).toBe("restricted_area_contact");
  expect(assessSiteInterference([building, other("site")])).toEqual([]);
  expect(assessSiteInterference([building, { ...pipe, meta: { ...pipe.meta, ui_hidden: true } }])[0].severity).toBe("review");
  expect(assessSiteInterference([building, { ...pipe, placed: false }])).toEqual([]);
  const wrapper = { ...building, id: "group", meta: { combined_from_object_ids: [building.id] } };
  expect(assessSiteInterference([building, wrapper])).toEqual([]);
});

test("cul-de-sac exact checks handle variable and rotated footprints without bounding-box false positives", () => {
  const road = regenerateCulDeSac({ ...building, id: "road", type: "road", meta: { cul_de_sac_v1: defaultCulDeSacParameters() } });
  const frame = culDeSacFrame(road)!;
  const b = { ...building, x: 90, y: 90, geometryType: "polygon" as const, geometry: [[40, 40], [60, 40], [60, 60], [40, 60]].map(p => frame.toWorld(p as [number, number])) };
  expect(assessSiteInterference([road, b])).toEqual([]);
  const rotated = regenerateCulDeSac({ ...road, rotation: 37, x: 70, y: 25 });
  const rotatedFrame = culDeSacFrame(rotated)!;
  const rotatedBuilding = { ...b, geometry: [[40, 40], [60, 40], [60, 60], [40, 60]].map(p => rotatedFrame.toWorld(p as [number, number])) };
  expect(assessSiteInterference([rotated, rotatedBuilding])).toEqual([]);
  const centerBuilding = { ...building, geometryType: "polygon" as const, geometry: [[-5, -5], [5, -5], [5, 5], [-5, 5]].map(p => rotatedFrame.toWorld(p as [number, number])) };
  expect(assessSiteInterference([rotated, centerBuilding])[0].severity).toBe("conflict");
  expect(checkFootprint(defaultLayout(), [[-10, -10], [10, -10], [10, 10], [-10, 10]])).toEqual({ pavement: false, island: true });
});

test("parametric updates move, rotate, resize dimensions and detach arbitrary edits honestly", () => {
  const road = regenerateCulDeSac({ ...building, type: "road", meta: { cul_de_sac_v1: defaultCulDeSacParameters() } });
  const moved = { ...road, ...reconcileCulDeSacUpdate(road, { x: 10, y: 20, rotation: 40 }) };
  expect(moved.geometry).not.toEqual(road.geometry);
  const widened = { ...moved, ...reconcileCulDeSacUpdate(moved, { meta: { ...moved.meta, cul_de_sac_v1: { ...defaultCulDeSacParameters(), roadWidthFt: 40 } } }) };
  expect(culDeSacFrame(widened)!.p.roadWidthFt).toBe(40);
  const detached = reconcileCulDeSacUpdate(road, { geometry: [[0, 0], [20, 0], [20, 20]] });
  expect(detached.meta?.cul_de_sac_v1).toBeUndefined();
  const metric = regenerateCulDeSac({ ...building, type: "road", meta: { cul_de_sac_v1: defaultCulDeSacParameters("m") } });
  expect(metric.w).toBeCloseTo(30.48);
  const point: [number, number] = [40, -20];
  const local = culDeSacFrame(metric)!.toLocal(culDeSacFrame(metric)!.toWorld(point));
  expect(local[0]).toBeCloseTo(point[0]); expect(local[1]).toBeCloseTo(point[1]);
});

test("native project serialization/restoration preserves road parameters and pipe elevation evidence", () => {
  const road = regenerateCulDeSac({ ...building, id: "road", type: "road", rotation: 27, meta: { cul_de_sac_v1: { ...defaultCulDeSacParameters(), roadWidthFt: 40 } } });
  const objects = [road, withZ(pipe, extent(-6, -5))];
  const manual = buildDashboardManualFields({ nextSiteName: "Test", nextFileName: "Test", nextUnits: "ft", nextProjectType: "commercial", nextLotWidth: 400, nextLotHeight: 300, nextSetback: 0, nextBuildingWidth: 20, nextBuildingDepth: 20, nextBuildingCount: 0, nextParkingCount: 0, nextMinSlopePct: 1, nextPipeMinSlopePct: 1, nextMaxParkingSlopePct: 5, nextMaxRoadGradePct: 5, nextMaxAdaCrossSlopePct: 2, nextRoads: true, nextGrading: false, nextDrainage: false, nextUtilities: true, buildingPlacements: objects, drainageForcedInlets: [], drainageConnectOrphans: false, drainageAllowSlopeAdjust: false, drainageMaxSlopeAdjust: 0 });
  const projectInput = JSON.parse(JSON.stringify({ manual_fields: manual, meta: {} })) as ProjectInput;
  const restored = buildProjectInputPlacements({ projectInput, siteInputs: {} });
  const restoredRoad = restored.find(o => o.id === "road")!, restoredPipe = restored.find(o => o.id === "pipe")!;
  expect(restoredRoad.geometry).toEqual(road.geometry); expect(restoredRoad.meta?.cul_de_sac_v1).toEqual(road.meta?.cul_de_sac_v1);
  expect(restoredPipe.meta?.vertical_extent_v1).toEqual(objects[1].meta?.vertical_extent_v1);
  expect(objectFootprints(restoredPipe)).toEqual(objectFootprints(objects[1]));
  expect(buildCanonicalGeometryHandoffV1(road, "ft").engineering_attributes.cul_de_sac_v1).toEqual(road.meta?.cul_de_sac_v1);
  expect(buildCanonicalGeometryHandoffV1(objects[1], "ft").engineering_attributes.vertical_extent_v1).toEqual(objects[1].meta?.vertical_extent_v1);
  expect(buildCanonicalGeometryHandoffV1(objects[1], "ft").engineering_attributes.pipe_diameter_ft).toBe(pipe.meta?.pipe_diameter_ft);
});
