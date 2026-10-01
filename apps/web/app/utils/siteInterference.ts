import type { BuildingPlacement } from "../types";
import { checkFootprint, polygonContains, segmentsTouch, type FootprintPoint } from "./culDeSacConcept";
import { culDeSacFrame } from "./parametricRoad";

export type VerticalExtent = { version: 1; minFt: number; maxFt: number; datum: string; source: string; reviewed: boolean; requiredClearanceFt: number | null };
export type InterferenceResult = { code: string; objectIds: string[]; severity: "conflict" | "review" | "clear"; message: string };
export function isLinearUtility(item: BuildingPlacement) {
  return item.meta?.asset_kind === "pipe" || (item.geometryType === "polyline" && (item.type === "utility_corridor" || Boolean(item.meta?.network)));
}
export function readVerticalExtent(item: BuildingPlacement): VerticalExtent | null {
  const z = item.meta?.vertical_extent_v1 as VerticalExtent | undefined;
  return z && z.version === 1 && Number.isFinite(z.minFt) && Number.isFinite(z.maxFt) && z.minFt <= z.maxFt &&
    typeof z.datum === "string" && z.datum.trim() && typeof z.source === "string" && z.source.trim() && z.reviewed === true &&
    (z.requiredClearanceFt === null || (Number.isFinite(z.requiredClearanceFt) && Number(z.requiredClearanceFt) >= 0)) ? z : null;
}
function category(item: BuildingPlacement) {
  const t = item.type ?? "custom";
  if (t.includes("building") || ["pad", "pool", "amenity", "basin"].includes(t)) return "structure";
  if (["road", "driveway", "entrance", "parking", "sidewalk"].includes(t)) return "surface";
  if (item.meta?.asset_kind === "pipe" || t === "utility_corridor" || (item.geometryType === "polyline" && item.meta?.network)) return "utility";
  if (["hydrant", "manhole", "inlet", "outfall"].includes(t)) return "fixture";
  if (["landscape", "open_space"].includes(t)) return "landscape";
  if (["site", "lot_block", "setback_zone"].includes(t)) return "container";
  if (t === "no_build_zone") return "restriction";
  return "unknown";
}
export function objectFootprints(item: BuildingPlacement): FootprintPoint[][] {
  if (item.geometryType === "polygon" && item.geometry?.length) return [item.geometry];
  if (item.geometryType === "polyline" && item.geometry && item.geometry.length >= 2) {
    const scale = item.meta?.coordinate_units === "m" ? .3048 : 1;
    const diameter = Number(item.meta?.pipe_diameter_ft);
    const r = (Number.isFinite(diameter) && diameter > 0 ? diameter : 1) * scale / 2;
    const polygons: FootprintPoint[][] = [];
    item.geometry.forEach((p, i) => {
      // Conservative circumscribed caps; uncertain pipe sizes remain review-only.
      polygons.push(Array.from({ length: 24 }, (_, n) => {
        const a = n * Math.PI / 12, radius = r / Math.cos(Math.PI / 24);
        return [p[0] + radius * Math.cos(a), p[1] + radius * Math.sin(a)] as FootprintPoint;
      }));
      const next = item.geometry![i + 1]; if (!next) return;
      const length = Math.hypot(next[0] - p[0], next[1] - p[1]); if (!length) return;
      const nx = -(next[1] - p[1]) / length * r, ny = (next[0] - p[0]) / length * r;
      polygons.push([[p[0] + nx, p[1] + ny], [next[0] + nx, next[1] + ny], [next[0] - nx, next[1] - ny], [p[0] - nx, p[1] - ny]]);
    });
    return polygons;
  }
  const x = item.x ?? 0, y = item.y ?? 0, cx = x + item.w / 2, cy = y + item.d / 2, a = (item.rotation ?? 0) * Math.PI / 180;
  return [[[x, y], [x + item.w, y], [x + item.w, y + item.d], [x, y + item.d]].map(([px, py]) =>
    [cx + (px - cx) * Math.cos(a) - (py - cy) * Math.sin(a), cy + (px - cx) * Math.sin(a) + (py - cy) * Math.cos(a)] as FootprintPoint)];
}
function polygonsTouch(a: FootprintPoint[], b: FootprintPoint[]) {
  const bounds = (p: FootprintPoint[]) => ({ minX: Math.min(...p.map(v => v[0])), maxX: Math.max(...p.map(v => v[0])), minY: Math.min(...p.map(v => v[1])), maxY: Math.max(...p.map(v => v[1])) });
  const A = bounds(a), B = bounds(b);
  if (A.maxX < B.minX || B.maxX < A.minX || A.maxY < B.minY || B.maxY < A.minY) return false;
  return a.some(p => polygonContains(b, p)) || b.some(p => polygonContains(a, p)) ||
    a.some((p, i) => b.some((q, j) => segmentsTouch(p, a[(i + 1) % a.length], q, b[(j + 1) % b.length])));
}
function planContact(a: BuildingPlacement, b: BuildingPlacement, shapes: Map<BuildingPlacement, FootprintPoint[][]>) {
  const road = culDeSacFrame(a), otherRoad = culDeSacFrame(b);
  if (road && !otherRoad) return shapes.get(b)!.some(points => {
    const hit = checkFootprint(road.layout, points.map(road.toLocal)); return hit.pavement || hit.island;
  });
  if (otherRoad && !road) return planContact(b, a, shapes);
  return shapes.get(a)!.some(p => shapes.get(b)!.some(q => polygonsTouch(p, q)));
}
/** Draft coordination rules, not a claim of regulatory or engineering approval. */
export function assessSiteInterference(objects: BuildingPlacement[]): InterferenceResult[] {
  // A combined object's hull is an editing wrapper, not another occupied volume.
  // Keep its underlying sources (including hidden ones) as the physical objects.
  const candidates = objects.filter(o => o.placed && Number.isFinite(o.x) && Number.isFinite(o.y) && category(o) !== "container" && !(Array.isArray(o.meta?.combined_from_object_ids) && o.meta.combined_from_object_ids.length > 0));
  const results: InterferenceResult[] = [];
  const shapes = new Map(candidates.map(o => [o, objectFootprints(o)]));
  const site = objects.find(o => o.type === "site" && o.placed);
  if (site) {
    const boundary = objectFootprints(site)[0];
    for (const o of candidates) if (shapes.get(o)!.some(p => p.some(v => !polygonContains(boundary, v)))) {
      results.push({ severity: "review", code: "outside_site_boundary", objectIds: [site.id, o.id], message: `${o.label}: modeled geometry extends beyond the current site boundary; review placement and boundary evidence.` });
    }
  }
  for (const o of candidates) if (isLinearUtility(o) && !(typeof o.meta?.pipe_diameter_ft === "number" && Number.isFinite(o.meta.pipe_diameter_ft) && o.meta.pipe_diameter_ft > 0)) {
    results.push({ severity: "review", code: "pipe_size_unknown", objectIds: [o.id], message: `${o.label}: outside diameter is missing. The displayed centerline is not enough to establish clearance.` });
  }
  candidates.forEach((a, i) => candidates.slice(i + 1).forEach(b => {
    const A = category(a), B = category(b);
    // Access surfaces intentionally connect; landscape regions intentionally overlap.
    if (A === "surface" && B === "surface") {
      const frame = culDeSacFrame(a) ?? culDeSacFrame(b), other = culDeSacFrame(a) ? b : a;
      if (frame && shapes.get(other)!.some(p => checkFootprint(frame.layout, p.map(frame.toLocal)).island)) {
        results.push({ severity: "review", code: "access_crosses_island", objectIds: [a.id, b.id], message: `${a.label} / ${b.label}: access surface crosses the landscaped island; review curb and access geometry.` });
      }
      return;
    }
    if ((A === "landscape" && B === "landscape") || !planContact(a, b, shapes)) return;
    const objectIds = [a.id, b.id], names = `${a.label} / ${b.label}`;
    const result = (severity: InterferenceResult["severity"], code: string, detail: string) => results.push({ severity, code, objectIds, message: `${names}: ${detail}` });
    if ([a, b].some(o => isLinearUtility(o) && !(typeof o.meta?.pipe_diameter_ft === "number" && Number.isFinite(o.meta.pipe_diameter_ft) && o.meta.pipe_diameter_ft > 0))) {
      result("review", "pipe_size_unknown", "pipe outside diameter is unknown; do not infer physical clearance from the centerline."); return;
    }
    if (A === "restriction" || B === "restriction") { result("review", "restricted_area_contact", "overlaps a no-build restriction; confirm applicable exclusions."); return; }
    const zA = readVerticalExtent(a), zB = readVerticalExtent(b);
    if ([[a, zA], [b, zB]].some(([o, z]) => {
      const object = o as BuildingPlacement, extent = z as VerticalExtent | null;
      return isLinearUtility(object) && extent && extent.maxFt - extent.minFt + 1e-7 < Number(object.meta?.pipe_diameter_ft);
    })) { result("review", "pipe_envelope_incomplete", "the vertical envelope is thinner than the pipe outside diameter; occupied extents need correction."); return; }
    if (zA && zB && zA.datum === zB.datum) {
      const gap = Math.max(zA.minFt - zB.maxFt, zB.minFt - zA.maxFt);
      if (gap <= 0) { result("conflict", "physical_volume_contact", "modeled horizontal footprints and reviewed vertical extents touch or overlap."); return; }
      if (zA.requiredClearanceFt === null || zB.requiredClearanceFt === null) { result("review", "clearance_unknown", "vertically separated, but project-specific clearance requirements are missing."); return; }
      const required = Math.max(zA.requiredClearanceFt, zB.requiredClearanceFt);
      if (gap < required) result("conflict", "insufficient_vertical_clearance", `modeled vertical gap ${gap.toFixed(2)} ft is below the specified ${required.toFixed(2)} ft clearance.`);
      else result("clear", "modeled_vertical_separation", `no modeled interference: ${gap.toFixed(2)} ft vertical gap meets the entered clearance. This is not design approval.`);
      return;
    }
    if (A === "utility" || B === "utility" || A === "fixture" || B === "fixture" || A === "unknown" || B === "unknown" || A === "landscape" || B === "landscape") {
      result("review", "crossing_needs_evidence", "plan overlap alone does not prove a clash. Review depth/foundation extent, common elevation datum and required clearances.");
    } else result("conflict", "surface_footprint_contact", "occupied surface footprints touch or overlap. Review the layout or provide reviewed vertical separation.");
  }));
  return results;
}
