import { expect, test } from "@playwright/test";
import { CivoraGeometryEngine } from "../../app/utils/CivoraGeometryEngine";

const engine = new CivoraGeometryEngine();

test("returns exact bulb clearance and curb bottleneck", () => {
  const result = engine.checkClearance({ x: 70, y: 0, width: 20, length: 20, rotationDeg: 0 }, 36, 50);
  expect(result.hasCollision).toBe(false);
  expect(result.shortestDistanceFt).toBeCloseTo(10, 10);
  expect(result.closestPointOnCurb.x).toBeCloseTo(50, 10);
  expect(result.closestPointOnCurb.y).toBeCloseTo(0, 10);
});

test("detects exact tangency, crossings and a footprint wholly inside the roadway", () => {
  expect(engine.checkClearance({ x: 60, y: 0, width: 20, length: 10, rotationDeg: 0 }, 36, 50).shortestDistanceFt).toBe(0);
  expect(engine.checkClearance({ x: 48, y: 0, width: 20, length: 10, rotationDeg: 0 }, 36, 50).hasCollision).toBe(true);
  const inside = engine.checkClearance({ x: 0, y: 0, width: 10, length: 10, rotationDeg: 31 }, 36, 50);
  expect(inside.hasCollision).toBe(true);
  expect(inside.shortestDistanceFt).toBeLessThan(0);
});

test("uses the exact infinite approach curb and remains symmetric", () => {
  for (const x of [-30, 30]) {
    const result = engine.checkClearance({ x, y: 100, width: 10, length: 20, rotationDeg: 0 }, 36, 50);
    expect(result.shortestDistanceFt).toBeCloseTo(7, 10);
    expect(result.closestPointOnCurb.x).toBe(x < 0 ? -18 : 18);
  }
});

test("handles rotated OBBs analytically and rejects impossible tangent geometry", () => {
  const axisAligned = engine.checkClearance({ x: 75, y: 0, width: 20, length: 20, rotationDeg: 0 }, 36, 50);
  const rotated = engine.checkClearance({ x: 75, y: 0, width: 20, length: 20, rotationDeg: 45 }, 36, 50);
  expect(rotated.shortestDistanceFt).toBeLessThan(axisAligned.shortestDistanceFt);
  expect(() => engine.checkClearance({ x: 0, y: 0, width: 20, length: 20, rotationDeg: 0 }, 100, 50)).toThrow(/roadWidth < 2 \* bulbRadius/);
  expect(() => engine.checkClearance({ x: 0, y: 0, width: 0, length: 20, rotationDeg: 0 }, 36, 50)).toThrow(/positive/);
});
