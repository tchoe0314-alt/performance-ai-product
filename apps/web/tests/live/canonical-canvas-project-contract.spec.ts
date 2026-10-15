import { expect, test } from "@playwright/test";
import type { ProjectInput } from "../../app/types";
import { resolveCanonicalCanvasInput, withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { buildDashboardProjectInputView } from "../../app/utils/dashboardProjectInputView";

function fixture(): ProjectInput {
  return { input_mode: "user", manual_fields: { units: "ft", project_name: "Pilot", lot: { x: 0, y: 0, w: 900, h: 700 },
    site_objects: [
      { id: "office", type: "office_building", x: 125.25, y: 120, w: 160, d: 90, rotation: 17, meta: { unknown: [false, 0] } },
      { id: "pipe", type: "utility_corridor", x: 10, y: 30, w: 100, d: 1, geometry_type: "polyline", geometry: [[10.125, 30], [110.75, 30]],
        meta: { vertical_extent_v1: { minFt: -6, maxFt: -5, datum: "benchmark", reviewed: true } } },
      { id: "road", type: "road", x: 300, y: 100, w: 100, d: 200, meta: { cul_de_sac_v1: { roadWidthFt: 40, bulbRadiusFt: 50 } } },
    ] }, meta: { site_inputs: { address: "Fixture" } } };
}

test("canonical canvas round trip retains exact geometry, metadata and order", () => {
  const input = fixture();
  const before = JSON.stringify(input);
  const compiled = withCanonicalCanvasSnapshot(input);
  const restored = resolveCanonicalCanvasInput(JSON.parse(JSON.stringify(compiled)));
  expect(restored.manual_fields).toEqual(input.manual_fields);
  expect(restored.meta).toEqual(input.meta);
  expect(JSON.stringify(input)).toBe(before);
  expect((compiled.canonical_project_v1?.cul_de_sacs as unknown[])).toHaveLength(1);
});

test("program-only model units and site inputs override stale compatibility shadows", () => {
  const compiled = withCanonicalCanvasSnapshot(fixture());
  const doc = compiled.canonical_project_v1!;
  const extensions = doc.extensions as Record<string, unknown>;
  delete extensions.canvas_workspace_v1;
  extensions.project_record_v1 = { version: 1, input_controls: { input_mode: "user" }, input_meta: {},
    legacy_manual_fields: { units: "ft", building_width: 30 }, active_result_id: null };
  doc.units = { length: "m", area: null, volume: null };
  doc.site = { site_inputs_v1: { address: "Canonical address" } };
  const restored = resolveCanonicalCanvasInput(compiled);
  expect(restored.manual_fields?.units).toBe("m");
  expect(restored.meta?.site_inputs?.address).toBe("Canonical address");
  doc.units = { length: null, area: null, volume: null };
  expect(resolveCanonicalCanvasInput(compiled).manual_fields?.units).toBeNull();
});

test("canonical geometry beats conflicting legacy shadow in the actual restore view", () => {
  const compiled = withCanonicalCanvasSnapshot(fixture());
  compiled.manual_fields!.site_objects![0].x = 999;
  const view = buildDashboardProjectInputView(compiled, compiled.meta?.site_inputs);
  expect(view.mergedPlacements.find(item => item.id === "office")?.x).toBe(125.25);
});

test("explicit empty canonical canvas does not regenerate legacy buildings or pending programs", () => {
  const input = fixture();
  input.manual_fields!.site_objects = [];
  input.manual_fields!.buildings = [{ id: "old", name: "Old", x: 100, y: 100, w: 50, d: 50 }];
  const compiled = withCanonicalCanvasSnapshot(input);
  expect(buildDashboardProjectInputView(compiled, compiled.meta?.site_inputs).mergedPlacements).toEqual([]);
});

test("repeated compilation preserves independent document sections without duplicating objects", () => {
  let compiled = withCanonicalCanvasSnapshot(fixture());
  compiled.canonical_project_v1!.client = { name: "Client" };
  compiled.canonical_project_v1!.revisions = [{ id: "revision-1" }];
  for (let index = 0; index < 4; index++) compiled = withCanonicalCanvasSnapshot(compiled);
  expect(compiled.canonical_project_v1!.client).toEqual({ name: "Client" });
  expect(compiled.canonical_project_v1!.revisions).toEqual([{ id: "revision-1" }]);
  expect(compiled.canonical_project_v1!.buildings).toHaveLength(1);
});

test("invalid references and non-finite live geometry are rejected", () => {
  const compiled = withCanonicalCanvasSnapshot(fixture());
  const ext = compiled.canonical_project_v1!.extensions as Record<string, unknown>;
  const workspace = ext.canvas_workspace_v1 as { object_order: unknown[] };
  workspace.object_order.push(workspace.object_order[0]);
  expect(() => resolveCanonicalCanvasInput(compiled)).toThrow(/duplicated/);
  const input = fixture();
  input.manual_fields!.site_objects![0].x = Infinity;
  expect(() => withCanonicalCanvasSnapshot(input)).toThrow(/non-finite/);
});

test("old projects without canonical geometry keep their existing restore behavior", () => {
  const input = fixture();
  expect(resolveCanonicalCanvasInput(input)).toBe(input);
  expect(buildDashboardProjectInputView(input, input.meta?.site_inputs).mergedPlacements.find(item => item.id === "office")?.x).toBe(125.25);
});

test("canonical length units take precedence over stale compatibility units", () => {
  const compiled = withCanonicalCanvasSnapshot(fixture());
  compiled.canonical_project_v1!.units = { length: "m", area: null, volume: null };
  expect(resolveCanonicalCanvasInput(compiled).manual_fields?.units).toBe("m");
  compiled.canonical_project_v1!.units = { length: null, area: null, volume: null };
  expect(resolveCanonicalCanvasInput(compiled).manual_fields?.units).toBeUndefined();
});
