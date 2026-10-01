import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { checkConcept, defaultLayout, geometry, parseLayout, pointInRoad, serializeLayout } from "../../app/utils/culDeSacConcept";

test("analytic checks distinguish actual curves, road width and island", () => {
  const s = defaultLayout();
  const codes = (x: number, y: number) => checkConcept({ ...s, building: { x, y, w: 20, d: 20 } }).map(i => i.code);
  expect(codes(40, 40)).toEqual([]); // inside the old bounding box, outside asphalt
  expect(codes(50, 0)).toEqual(["pavement_contact"]);
  expect(codes(50.001, 0)).toEqual([]);
  expect(codes(-70, -10)).toEqual(["pavement_contact"]); // left contact
  expect(codes(-10, -70)).toEqual(["pavement_contact"]); // top contact
  expect(codes(15, 100)).toEqual(["pavement_contact"]);
  expect(codes(15.001, 100)).toEqual([]);
  const g = geometry(50, 30);
  const edge = g.x - Math.sqrt(g.f ** 2 - (50 - g.y) ** 2);
  expect(codes(edge, 50)).toEqual(["pavement_contact"]); // exact fillet arc
  expect(codes(edge + .001, 50)).toEqual([]);
  expect(codes(-10, -10)).toEqual(["island_contact"]); // wholly inside island
  expect(codes(15, -10)).toEqual(["pavement_contact", "island_contact"]);
  expect(codes(18, 100)).toEqual([]);
  expect(checkConcept({ ...s, roadWidth: 40, building: { x: 18, y: 100, w: 20, d: 20 } }).map(i => i.code)).toEqual(["pavement_contact"]);
  expect(codes(-10, g.bottom)).toEqual(["pavement_contact"]);
  expect(codes(-10, g.bottom + .001)).toEqual([]);
});

test("collision checks are translation invariant across every dimension combination", () => {
  for (let r = 35; r <= 80; r++) for (let w = 20; w <= 48; w++) {
    const s = { ...defaultLayout(), bulbRadius: r, roadWidth: w };
    for (const [x, y] of [[40, 40], [-10, -10], [15, 100], [r, 0]]) {
      const layout = { ...s, building: { x, y, w: 20, d: 20 } };
      const shifted = { ...layout, position: { x: -30, y: 15 }, building: { x: x - 30, y: y + 15, w: 20, d: 20 } };
      expect(checkConcept(shifted)).toEqual(checkConcept(layout));
    }
  }
});

test("schema round trips only validated design inputs", () => {
  const s = { ...defaultLayout(), roadWidth: 40, position: { x: 12.25, y: -4.5 }, revision: 123, isStale: false };
  const json = serializeLayout(s);
  expect(parseLayout(JSON.parse(json))).toEqual({ ...defaultLayout(), roadWidth: 40, position: s.position });
  expect(json).not.toContain("revision");
  expect(json).not.toContain("isStale");
  for (const invalid of [null, {}, { ...s, schemaVersion: 2 }, { ...s, units: "m" }, { ...s, roadWidth: NaN },
    { ...s, position: { x: Infinity, y: 0 } }, { ...s, building: { x: 0, y: 0, w: 0, d: 20 } }]) {
    expect(() => parseLayout(invalid)).toThrow();
  }
});

test("point classification agrees with the actual Canvas path", async ({ page }) => {
  await page.goto("/concepts/cul-de-sac.html");
  const mismatches = await page.evaluate(() => {
    const core = (window as unknown as { conceptTestCore: {
      defaultLayout: typeof defaultLayout; geometry: typeof geometry; pointInRoad: typeof pointInRoad;
    } }).conceptTestCore;
    const ctx = document.createElement("canvas").getContext("2d")!;
    const errors: string[] = [];
    for (const [r, w] of [[35, 48], [50, 30], [80, 20]]) {
      const s = { ...core.defaultLayout(), bulbRadius: r, roadWidth: w }, g = core.geometry(r, w);
      const path = new Path2D();
      path.moveTo(-g.a, g.bottom); path.lineTo(-g.a, g.y);
      path.arc(-g.x, g.y, g.f, 0, -g.theta, true);
      path.arc(0, 0, g.R, Math.PI - g.theta, 2 * Math.PI + g.theta);
      path.arc(g.x, g.y, g.f, -Math.PI + g.theta, -Math.PI, true);
      path.lineTo(g.a, g.bottom); path.closePath();
      for (let x = -90.137; x < 90; x += 2) for (let y = -90.317; y < 200; y += 2) {
        const expected = ctx.isPointInPath(path, x, y) && Math.hypot(x, y) >= 15;
        if (core.pointInRoad({ x, y }, s) !== expected) errors.push(`${r}/${w}/${x}/${y}`);
      }
    }
    return errors;
  });
  expect(mismatches).toEqual([]);
});

test("generated embedded core is the current source", async () => {
  const html = await readFile("public/concepts/cul-de-sac.html", "utf8");
  expect(html).toContain("// BEGIN GENERATED CONCEPT CORE");
});
