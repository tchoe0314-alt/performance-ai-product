import { expect, test } from "@playwright/test";

import type { BuildingPlacement } from "../../app/types";
import { selectedObjectsToSemanticArea } from "../../app/utils/objectGeometry";

const line = (id: string, start: [number, number], end: [number, number]): BuildingPlacement => ({
  id,
  label: id,
  type: "custom",
  x: Math.min(start[0], end[0]),
  y: Math.min(start[1], end[1]),
  w: Math.abs(end[0] - start[0]),
  d: Math.abs(end[1] - start[1]),
  rotation: 0,
  locked: false,
  placed: true,
  source: "manual_drawn",
  generated: false,
  geometryType: "polyline",
  geometry: [start, end],
});

test.describe("semantic geometry truth", () => {
  test("accepts one exact connected loop without changing its vertices", () => {
    const result = selectedObjectsToSemanticArea([
      line("south", [10, 10], [70, 10]),
      line("east", [70, 10], [70, 50]),
      line("north", [70, 50], [10, 50]),
      line("west", [10, 50], [10, 10]),
    ]);

    expect(result.valid).toBe(true);
    expect(result.geometry).toEqual([[10, 10], [70, 10], [70, 50], [10, 50]]);
  });

  test("does not silently repair a small drafting gap", () => {
    const result = selectedObjectsToSemanticArea([
      line("south", [10, 10], [70, 10]),
      line("east", [70.18, 10], [70, 50]),
      line("north", [70, 50], [10, 50]),
      line("west", [10, 50], [10, 10]),
    ]);

    expect(result.valid).toBe(false);
    expect(result.blockers[0]).toMatch(/Small gap requires permission.*0\.18 ft/i);
  });

  test("rejects duplicate segments, disconnected loops, and self-intersections", () => {
    const duplicate = selectedObjectsToSemanticArea([
      line("south", [0, 0], [20, 0]),
      line("south-copy", [20, 0], [0, 0]),
      line("east", [20, 0], [20, 20]),
      line("north", [20, 20], [0, 20]),
      line("west", [0, 20], [0, 0]),
    ]);
    expect(duplicate.valid).toBe(false);
    expect(duplicate.blockers[0]).toContain("Duplicate segments");

    const disconnected = selectedObjectsToSemanticArea([
      line("a1", [0, 0], [10, 0]),
      line("a2", [10, 0], [5, 8]),
      line("a3", [5, 8], [0, 0]),
      line("b1", [30, 30], [40, 30]),
      line("b2", [40, 30], [35, 38]),
      line("b3", [35, 38], [30, 30]),
    ]);
    expect(disconnected.valid).toBe(false);
    expect(disconnected.blockers[0]).toMatch(/one connected set/i);

    const crossing = selectedObjectsToSemanticArea([
      line("one", [0, 0], [20, 20]),
      line("two", [20, 20], [0, 20]),
      line("three", [0, 20], [20, 0]),
      line("four", [20, 0], [0, 0]),
    ]);
    expect(crossing.valid).toBe(false);
    expect(crossing.blockers[0]).toContain("crosses itself");
  });
});
