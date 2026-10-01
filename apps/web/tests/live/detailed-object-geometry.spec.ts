import { expect, test } from "@playwright/test";
import type { BuildingPlacement, ProjectInput } from "../../app/types";
import { assessSiteInterference } from "../../app/utils/siteInterference";
import { detailedGeometryBinding, pipeContactIntervals, componentFootprint, validateComponentModel, validatePipeProfile, type ComponentModel, type PipeProfile, type OccupiedComponent } from "../../app/utils/detailedObjectGeometry";
import { buildProjectInputPlacements } from "../../app/utils/projectInputRestore";
import { buildCanonicalGeometryHandoffV1 } from "../../app/utils/objectGeometry";
import { buildDashboardObjectUpdateRecentChange } from "../../app/utils/dashboardObjectChangeMessages";
import { buildDashboardObjectPlacement } from "../../app/utils/dashboardObjectPlacementBuilder";
import { PUBLIC_PLAN_REFERENCE } from "../../app/utils/publicPlanReference";

const building: BuildingPlacement = { id: "building", type: "building", label: "Building", placed: true, x: 0, y: 0, w: 10, d: 10 };
const pipe: BuildingPlacement = { id: "pipe", type: "utility_corridor", label: "Pipe", placed: true, x: -10, y: 5, w: 100, d: 1, geometryType: "polyline", geometry: [[-10, 5], [90, 5]], meta: { asset_kind: "pipe", pipe_diameter_ft: 1 } };
const evidence = { version: 1 as const, datum: "test-datum", source: "Synthetic test fixture; not a real surveyed site", reviewed: true, requiredClearanceFt: 1 };
const part = (kind: OccupiedComponent["kind"], minFt: number, maxFt: number, xFt = 0, wFt = 10): OccupiedComponent => ({ id: kind, label: kind, kind, xFt, yFt: 0, wFt, dFt: 10, minFt, maxFt });
const withParts = (item = building, parts = [part("body", 0, 20), part("foundation", -4, 0)]) => ({ ...item, meta: { ...item.meta, occupied_components_v1: { ...evidence, geometryBinding: detailedGeometryBinding(item), complete: true, components: parts } satisfies ComponentModel } });
const withProfile = (item = pipe, elevations = [-10, 10]) => ({ ...item, meta: { ...item.meta, pipe_profile_v1: { ...evidence, geometryBinding: detailedGeometryBinding(item), centerElevationsFt: elevations } satisfies PipeProfile } });

test("pipe profile checks local crossing instead of its highest point elsewhere", () => {
  const findings = assessSiteInterference([withParts(), withProfile()]);
  expect(findings.length).toBeGreaterThan(0);
  expect(findings.every(r => r.severity === "clear")).toBe(true);
  const nearHighPoint = withParts({ ...building, x: 30 });
  expect(assessSiteInterference([nearHighPoint, withProfile()]).some(r => r.code === "detailed_volume_contact")).toBe(true);
});
test("deep foundations conflict even while the body is above the pipe", () => {
  const findings = assessSiteInterference([withParts(building, [part("body", 0, 20), part("foundation", -12, 0)]), withProfile()]);
  expect(findings.some(r => r.code === "detailed_volume_contact" && r.message.includes("foundation"))).toBe(true);
});
test("project clearance, missing datum and missing clearance remain enforced", () => {
  const flat = withProfile(pipe, [-5, -5]);
  expect(assessSiteInterference([withParts(), flat]).some(r => r.code === "detailed_clearance_shortfall")).toBe(true);
  const model = withParts(); model.meta.occupied_components_v1.datum = "different";
  expect(assessSiteInterference([model, flat]).every(r => r.severity === "review")).toBe(true);
  const noClearance = { ...flat, meta: { ...flat.meta, pipe_profile_v1: { ...flat.meta.pipe_profile_v1, requiredClearanceFt: null } } };
  expect(assessSiteInterference([withParts(), noClearance]).some(r => r.code === "detailed_clearance_unknown")).toBe(true);
});
test("bridge deck is separated from the route but a pier at that route conflicts", () => {
  const bridge = { ...building, type: "bridge" as const, w: 100, d: 20, label: "Bridge" };
  const assembly = [part("deck", 20, 22, 0, 100), part("support", -2, 20, 0, 5), part("foundation", -10, -2, 0, 5)];
  const road = { ...building, type: "road" as const, id: "road", x: 40, w: 20, meta: { vertical_extent_v1: { ...evidence, minFt: 0, maxFt: 1 } } };
  expect(assessSiteInterference([withParts(bridge, assembly), road]).every(r => r.severity === "clear")).toBe(true);
  expect(assessSiteInterference([withParts(bridge, assembly.map(c => c.kind === "deck" ? c : { ...c, xFt: 45 })), road]).some(r => r.code === "detailed_volume_contact")).toBe(true);
  expect(validateComponentModel(withParts(bridge, [assembly[0]]).meta.occupied_components_v1, bridge)).toMatch(/support/);
});
test("foundation projections outside the displayed building footprint still participate", () => {
  const expanded = withParts(building, [part("body", 0, 20), part("foundation", -10, 0, 20, 5)]);
  const nearby = { ...building, id: "other", x: 20, w: 5, meta: { vertical_extent_v1: { ...evidence, minFt: -8, maxFt: -5 } } };
  expect(assessSiteInterference([expanded, nearby]).some(r => r.code === "detailed_volume_contact")).toBe(true);
});
test("analytic pipe intervals include radius, endcaps, tangencies and concave disjoint crossings", () => {
  const box: [number, number][] = [[0, 0], [10, 0], [10, 10], [0, 10]];
  const intervals = pipeContactIntervals([-10, 5], [20, 5], box, 1);
  expect(Math.min(...intervals.map(r => r[0]))).toBeCloseTo(.3, 9);
  expect(Math.max(...intervals.map(r => r[1]))).toBeCloseTo(.7, 9);
  expect(pipeContactIntervals([-10, -1], [20, -1], box, 1).length).toBeGreaterThan(0);
  expect(pipeContactIntervals([-10, -1.01], [20, -1.01], box, 1)).toEqual([]);
  expect(pipeContactIntervals([-2, 5], [-.5, 5], box, 1).length).toBeGreaterThan(0);
  const u: [number, number][] = [[0, 0], [10, 0], [10, 10], [7, 10], [7, 3], [3, 3], [3, 10], [0, 10]];
  const hits = pipeContactIntervals([-5, 8], [15, 8], u, .1);
  expect(hits.some(([a, b]) => a <= .5 && b >= .5)).toBe(false);
});
test("malformed, incomplete and unreviewed detailed evidence never falls back to a false clear", () => {
  const valid = withParts();
  for (const override of [{ complete: false }, { reviewed: false }, { source: "" }, { components: [{ ...part("body", 0, 1), wFt: -1 }] }, { requiredClearanceFt: -1 }]) {
    const item = { ...valid, meta: { ...valid.meta, occupied_components_v1: { ...valid.meta.occupied_components_v1, ...override } } };
    expect(assessSiteInterference([item, withProfile()]).some(r => r.code === "detailed_evidence_invalid")).toBe(true);
  }
  expect(validatePipeProfile({ ...withProfile().meta.pipe_profile_v1, centerElevationsFt: [1] }, pipe)).toMatch(/every route vertex/);
});
test("movement, rotation, scale, route and diameter edits invalidate reviewed bindings", () => {
  const profiled = withProfile();
  for (const change of [{ x: 1 }, { rotation: 20 }, { w: 50 }, { geometry: [[-10, 5], [20, 5]] as [number, number][] }, { meta: { ...profiled.meta, pipe_diameter_ft: 2 } }]) {
    const changed = { ...profiled, ...change };
    expect(validatePipeProfile(changed.meta.pipe_profile_v1, changed)).toMatch(/different geometry/);
  }
  const solid = withParts(), moved = { ...solid, x: 10 };
  expect(validateComponentModel(moved.meta.occupied_components_v1, moved)).toMatch(/different geometry/);
});
test("metric and rotated component coordinates use the correct parent frame", () => {
  const metric = { ...building, x: 10, y: 20, w: 3.048, d: 3.048, rotation: 90, meta: { coordinate_units: "m" } };
  const footprint = componentFootprint(metric, part("body", 0, 1));
  expect(footprint[0][0]).toBeCloseTo(13.048, 8); expect(footprint[0][1]).toBeCloseTo(20, 8);
});
test("two varying profiles and missing counterpart evidence remain explicit review cases", () => {
  const other = withProfile({ ...pipe, id: "other" }, [10, 10]);
  expect(assessSiteInterference([withProfile(), other]).some(r => r.code === "profile_profile_review")).toBe(true);
  expect(assessSiteInterference([withProfile(), building]).some(r => r.code === "detailed_evidence_missing")).toBe(true);
});
test("detailed evidence persists and is undoable without stale canonical copies", () => {
  const items = [withParts(), withProfile()];
  const projectInput = JSON.parse(JSON.stringify({ manual_fields: { site_objects: items }, meta: {} })) as ProjectInput;
  const restored = buildProjectInputPlacements({ projectInput, siteInputs: {} });
  for (const item of items) {
    const loaded = restored.find(o => o.id === item.id)!;
    expect(loaded.meta).toMatchObject(item.meta);
    const key = item.id === "pipe" ? "pipe_profile_v1" : "occupied_components_v1";
    expect(buildCanonicalGeometryHandoffV1(loaded, "ft")?.engineering_attributes?.[key]).toEqual((item as BuildingPlacement).meta?.[key]);
    const before = item.id === "pipe" ? pipe : building;
    const undo = { action: "update" as const, objectId: item.id, before, after: item, label: item.label };
    expect(buildDashboardObjectUpdateRecentChange({ target: before, updates: { meta: item.meta }, undo })?.undo).toBe(undo);
  }
});
test("specific pipe routes use their actual dimensions even before site initialization", () => {
  for (const units of ["ft", "m"]) {
    const scale = units === "m" ? .3048 : 1;
    const item = buildDashboardObjectPlacement({ type: "utility_corridor", lot: { w: 0, h: 0 }, existingCount: 0, defaultDimensions: { w: 140, d: 12 }, fallbackLabel: "Reference pipe", options: { placed: true, geometryType: "polyline", width: 65 * scale, depth: scale, meta: { asset_kind: "pipe", network: "sanitary", coordinate_units: units, public_reference_v1: PUBLIC_PLAN_REFERENCE } }, parkingControls: {} as Parameters<typeof buildDashboardObjectPlacement>[0]["parkingControls"], computeParkingFootprint: () => ({ maxStalls: 0, moduleCols: 0, moduleRows: 0 }) });
    expect(item.geometry).toHaveLength(3);
    expect(item.geometry![2][0] - item.geometry![0][0]).toBeCloseTo(65 * scale, 8);
    expect(item.geometry![1]).not.toEqual(item.geometry![0]);
    expect(item.meta?.pipe_diameter_ft).toBeUndefined();
    expect(validatePipeProfile(withProfile(item, [-10, -10, -10]).meta.pipe_profile_v1, item)).toMatch(/outside diameter/);
  }
});
