import { expect, test } from "@playwright/test";
import type { BuildingPlacement, SiteObjectType, ProjectInput } from "../../app/types";
import { SITE_OBJECT_RULEBOOK } from "../../app/utils/siteObjectRulebook";
import { SITE_OBJECT_CATALOG } from "../../app/utils/siteObjectCatalog";
import { assessSiteInterference, footprintInside } from "../../app/utils/siteInterference";
import { buildCanonicalGeometryHandoffV1 } from "../../app/utils/objectGeometry";
import { buildProjectInputPlacements } from "../../app/utils/projectInputRestore";
import { buildDashboardObjectUpdateRecentChange } from "../../app/utils/dashboardObjectChangeMessages";

const object = (type: SiteObjectType, id: string = type, x = 0): BuildingPlacement => ({ id, type, label: id, placed: true, x, y: 0, w: 20, d: 20 });
const envelope = (purpose = "maintenance", bufferFt = 5, reviewed = true) => ({ version: 1, purpose, bufferFt, reviewed, source: "Entered project drawing" });
const connection = (id: string, reviewed = true) => ({ version: 1, objectIds: [id], source: "Reviewed junction drawing", reviewed });
const setback = (mode = "excluded_area", appliesTo = ["building"], reviewed = true) => ({ version: 1, mode, appliesTo, reviewed, source: "Entered project constraint" });

test("every catalog type has explicit, documented compatibility guidance", () => {
  expect(Object.keys(SITE_OBJECT_RULEBOOK).sort()).toEqual(Object.keys(SITE_OBJECT_CATALOG).sort());
});
for (const type of Object.keys(SITE_OBJECT_CATALOG) as SiteObjectType[]) test(`classifies ${type} without silently exempting occupied or unknown objects`, () => {
  const rule = SITE_OBJECT_RULEBOOK[type];
  expect(rule.guidance.length).toBeGreaterThan(15);
  const results = assessSiteInterference([object("building", "existing"), object(type)]);
  if (rule.category === "container") expect(results).toEqual([]);
  else { expect(results.length).toBeGreaterThan(0); expect(results.some(r => r.severity !== "clear")).toBe(true); }
});
test("all catalog pairs produce symmetric rules independent of object order", () => {
  const types = Object.keys(SITE_OBJECT_CATALOG) as SiteObjectType[];
  const signature = (objects: BuildingPlacement[]) => assessSiteInterference(objects).map(r => `${r.severity}:${r.code}:${[...r.objectIds].sort().join(",")}`).sort();
  for (const a of types) for (const b of types) {
    const objects = [object(a, "a"), object(b, "b")];
    expect(signature(objects), `${a} / ${b}`).toEqual(signature([...objects].reverse()));
  }
});
test("surface overlaps require evidence and explicit connections never exempt buildings", () => {
  const road = object("road"), path = object("sidewalk");
  expect(assessSiteInterference([road, path])[0].code).toBe("surface_connection_unverified");
  expect(assessSiteInterference([{ ...road, meta: { intentional_connections_v1: connection(path.id) } }, path])).toEqual([]);
  expect(assessSiteInterference([{ ...road, meta: { intentional_connections_v1: connection(path.id, false) } }, path])[0].severity).toBe("review");
  const building = object("building");
  expect(assessSiteInterference([{ ...road, meta: { intentional_connections_v1: connection(building.id) } }, building])[0].severity).toBe("conflict");
});
test("network connections remain reviewable and do not waive maintenance buffers", () => {
  const pipe = { ...object("utility_corridor"), geometryType: "polyline" as const, geometry: [[-10, 10], [30, 10]] as [number, number][], meta: { asset_kind: "pipe", pipe_diameter_ft: 1, intentional_connections_v1: connection("manhole"), coordination_envelope_v1: envelope() } };
  const results = assessSiteInterference([pipe, object("manhole")]);
  expect(results.map(r => r.code)).toEqual(["coordination_envelope_contact", "network_connection_review"]);
});
for (const purpose of ["roots", "foundation", "maintenance", "separation"]) test(`${purpose} envelope checks near misses, additive buffers and rotation`, () => {
  const a = { ...object("landscape"), meta: { coordination_envelope_v1: envelope(purpose, 5) } }, b = object("building", "b", 24);
  expect(assessSiteInterference([a, b])[0].code).toBe("coordination_envelope_contact");
  expect(assessSiteInterference([a, { ...b, x: 25 }])).toEqual([]);
  expect(assessSiteInterference([a, { ...b, x: 27, meta: { coordination_envelope_v1: envelope("maintenance", 3) } }])[0].code).toBe("coordination_envelope_contact");
  expect(assessSiteInterference([a, { ...b, rotation: 45 }])[0].code).toBe("coordination_envelope_contact");
  expect(assessSiteInterference([{ ...a, meta: { coordination_envelope_v1: envelope(purpose, 5, false) } }, b])[0].code).toBe("coordination_envelope_unreviewed");
});
test("metric buffers and mixed coordinate units are handled honestly", () => {
  const a = { ...object("pad"), w: 6.096, d: 6.096, meta: { coordinate_units: "m", coordination_envelope_v1: envelope() } };
  const b = { ...object("building", "b", 7.3152), w: 6.096, d: 6.096, meta: { coordinate_units: "m" } };
  expect(assessSiteInterference([a, b])[0].code).toBe("coordination_envelope_contact");
  expect(assessSiteInterference([a, { ...b, meta: {} }])[0].code).toBe("coordinate_units_mismatch");
});
test("setbacks distinguish exclusion, containment, scope and unreviewed meaning", () => {
  const zone = { ...object("setback_zone"), meta: { setback_rule_v1: setback() } }, building = object("building");
  expect(assessSiteInterference([zone, building])[0].code).toBe("setback_rule_violation");
  expect(assessSiteInterference([zone, object("road")])).toEqual([]);
  expect(assessSiteInterference([{ ...zone, meta: { setback_rule_v1: setback("buildable_area") } }, building])).toEqual([]);
  expect(assessSiteInterference([{ ...zone, meta: { setback_rule_v1: setback("buildable_area") } }, { ...building, x: 1 }])[0].code).toBe("setback_rule_violation");
  expect(assessSiteInterference([{ ...zone, meta: { setback_rule_v1: setback("excluded_area", ["building"], false) } }, { ...building, x: 100 }])[0].code).toBe("setback_rule_unknown");
  expect(assessSiteInterference([{ ...zone, meta: { setback_rule_v1: setback("excluded_area", ["unsupported_type"]) } }, building])[0].code).toBe("setback_rule_unknown");
});
for (const key of ["cul_de_sac_v1", "vertical_extent_v1", "pipe_diameter_ft", "coordination_envelope_v1", "setback_rule_v1", "intentional_connections_v1"]) test(`${key} changes and clearing are recorded as undoable engineering updates`, () => {
  const before = object("building"), after = { ...before, meta: { [key]: { version: 1 } } };
  const undo = { action: "update" as const, objectId: before.id, before, after, label: before.label };
  expect(buildDashboardObjectUpdateRecentChange({ target: before, updates: { meta: after.meta }, undo })?.undo).toBe(undo);
  expect(buildDashboardObjectUpdateRecentChange({ target: after, updates: { meta: { [key]: null } }, undo })?.undo).toBe(undo);
});
test("concave boundaries catch edges crossing outside even when all corners are inside", () => {
  const boundary: [number, number][] = [[0, 0], [100, 0], [100, 100], [60, 100], [60, 40], [40, 40], [40, 100], [0, 100]];
  const footprint: [number, number][] = [[20, 60], [80, 60], [80, 80], [20, 80]];
  expect(footprintInside(boundary, footprint)).toBe(false);
  const site = { ...object("site"), geometryType: "polygon" as const, geometry: boundary };
  const building = { ...object("building"), geometryType: "polygon" as const, geometry: footprint };
  expect(assessSiteInterference([site, building])[0].code).toBe("outside_site_boundary");
  expect(footprintInside(boundary, [[0, 0], [100, 0], [100, 20], [0, 20]])).toBe(true);
});
test("new rule evidence survives project JSON restore and canonical handoff", () => {
  const item = { ...object("setback_zone"), meta: { setback_rule_v1: setback(), coordination_envelope_v1: envelope("foundation"), intentional_connections_v1: connection("other") } };
  const input = JSON.parse(JSON.stringify({ manual_fields: { site_objects: [item] }, meta: {} })) as ProjectInput;
  const restored = buildProjectInputPlacements({ projectInput: input, siteInputs: {} }).find(o => o.id === item.id)!;
  expect(restored.meta).toMatchObject(item.meta);
  expect(buildCanonicalGeometryHandoffV1(restored, "ft")?.engineering_attributes).toMatchObject(item.meta);
});
test("cleared evidence cannot reappear from stale canonical attribute copies", () => {
  const stale = { coordination_envelope_v1: envelope(), setback_rule_v1: setback(), vertical_extent_v1: { version: 1 }, asset_identifier: "preserve-me" };
  const item = { ...object("building"), meta: { coordination_envelope_v1: null, setback_rule_v1: null, vertical_extent_v1: null, engineering_attributes: stale } };
  const attributes = buildCanonicalGeometryHandoffV1(item, "ft")?.engineering_attributes;
  expect(attributes?.coordination_envelope_v1).toBeUndefined();
  expect(attributes?.setback_rule_v1).toBeUndefined();
  expect(attributes?.vertical_extent_v1).toBeUndefined();
  expect(attributes?.asset_identifier).toBe("preserve-me");
});
