import type { BuildingPlacement } from "../types";
import { objectFootprints, footprintInside } from "./siteInterference";

type Point = [number, number];
function distanceToEdge(p: Point, a: Point, b: Point) {
  const dx = b[0] - a[0], dy = b[1] - a[1], denominator = dx * dx + dy * dy;
  const t = denominator ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denominator)) : 0;
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
}
function edgeDistance(a: Point[], b: Point[]) {
  let minimum = Infinity;
  for (const [source, target] of [[a, b], [b, a]]) for (const p of source) for (let index = 0; index < target.length; index++) minimum = Math.min(minimum, distanceToEdge(p, target[index], target[(index + 1) % target.length]));
  return minimum;
}

/** Entered uniform building setback only; not a jurisdictional rule or survey proof. */
export function layoutBoundaryViolations(placements: BuildingPlacement[], setback: number | null | undefined): string[] {
  const site = placements.find(item => item.type === "site" && item.placed !== false);
  if (!site) return ["missing site boundary"];
  const boundary = objectFootprints(site)[0];
  const violations: string[] = [];
  for (const item of placements) {
    if (item === site || item.placed === false || !/building|office|retail|industrial|multifamily/.test(item.type ?? "")) continue;
    for (const footprint of objectFootprints(item)) {
      if (!footprintInside(boundary, footprint)) violations.push("building outside current site boundary");
      else if (setback != null && edgeDistance(boundary, footprint) + 1e-6 < setback) violations.push("entered building setback violation");
    }
  }
  return [...new Set(violations)];
}
