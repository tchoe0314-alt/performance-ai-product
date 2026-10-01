import type { BuildingPlacement } from "../types";
import { checkFootprint, polygonContains, segmentsTouch, type FootprintPoint } from "./culDeSacConcept";
import { culDeSacFrame } from "./parametricRoad";
import { objectRule, readCoordinationEnvelope, hasReviewedConnection, SITE_OBJECT_RULEBOOK } from "./siteObjectRulebook";
import type { SiteObjectType } from "../types";
import { assessDetailedPair, reviewedComponentFootprints, validateComponentModel, validatePipeProfile } from "./detailedObjectGeometry";

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
  return objectRule(item).category;
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
function pointSegmentDistance(p: FootprintPoint, a: FootprintPoint, b: FootprintPoint) {
  const dx = b[0] - a[0], dy = b[1] - a[1], length2 = dx * dx + dy * dy;
  const t = length2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2)) : 0;
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
}
function footprintDistance(a: FootprintPoint[][], b: FootprintPoint[][]) {
  let distance = Infinity;
  for (const p of a) for (const q of b) {
    if (polygonsTouch(p, q)) return 0;
    for (const v of p) for (let i = 0; i < q.length; i++) distance = Math.min(distance, pointSegmentDistance(v, q[i], q[(i + 1) % q.length]));
    for (const v of q) for (let i = 0; i < p.length; i++) distance = Math.min(distance, pointSegmentDistance(v, p[i], p[(i + 1) % p.length]));
  }
  return distance;
}
/** Split each edge at boundary crossings so a concave notch cannot be missed by checking vertices alone. */
export function footprintInside(boundary: FootprintPoint[], footprint: FootprintPoint[]) {
  if (!footprint.every(p => polygonContains(boundary, p))) return false;
  const cross = (a: FootprintPoint, b: FootprintPoint) => a[0] * b[1] - a[1] * b[0];
  return footprint.every((a, i) => {
    const b = footprint[(i + 1) % footprint.length], r: FootprintPoint = [b[0] - a[0], b[1] - a[1]], splits = [0, 1];
    boundary.forEach((c, j) => {
      const d = boundary[(j + 1) % boundary.length], s: FootprintPoint = [d[0] - c[0], d[1] - c[1]], delta: FootprintPoint = [c[0] - a[0], c[1] - a[1]], denominator = cross(r, s);
      if (Math.abs(denominator) < 1e-10) return;
      const t = cross(delta, s) / denominator, u = cross(delta, r) / denominator;
      if (t >= 0 && t <= 1 && u >= 0 && u <= 1) splits.push(t);
    });
    splits.sort((x, y) => x - y);
    return splits.slice(1).every((t, j) => { const mid = (splits[j] + t) / 2; return polygonContains(boundary, [a[0] + mid * r[0], a[1] + mid * r[1]]); });
  });
}
/** Draft coordination rules, not a claim of regulatory or engineering approval. */
export function assessSiteInterference(objects: BuildingPlacement[]): InterferenceResult[] {
  // A combined object's hull is an editing wrapper, not another occupied volume.
  // Keep its underlying sources (including hidden ones) as the physical objects.
  const candidates = objects.filter(o => o.placed && Number.isFinite(o.x) && Number.isFinite(o.y) && category(o) !== "container" && !(Array.isArray(o.meta?.combined_from_object_ids) && o.meta.combined_from_object_ids.length > 0));
  const results: InterferenceResult[] = [];
  const shapes = new Map(candidates.map(o => [o, [...objectFootprints(o), ...reviewedComponentFootprints(o)]]));
  for (const o of candidates) {
    const error = o.meta?.occupied_components_v1 ? validateComponentModel(o.meta.occupied_components_v1, o) : o.meta?.pipe_profile_v1 ? validatePipeProfile(o.meta.pipe_profile_v1, o) : null;
    if (error) results.push({ severity: "review", code: "detailed_evidence_invalid", objectIds: [o.id], message: `${o.label}: ${error}` });
  }
  for (const o of candidates) if (o.meta?.coordination_envelope_v1 && !readCoordinationEnvelope(o)) results.push({ severity: "review", code: "coordination_envelope_unreviewed", objectIds: [o.id], message: `${o.label}: horizontal protection/access buffer is incomplete or unreviewed; it has not been used to establish clearance.` });
  const site = objects.find(o => o.type === "site" && o.placed);
  if (site) {
    const boundary = objectFootprints(site)[0];
    for (const o of candidates) if (shapes.get(o)!.some(p => !footprintInside(boundary, p))) {
      results.push({ severity: "review", code: "outside_site_boundary", objectIds: [site.id, o.id], message: `${o.label}: modeled geometry extends beyond the current site boundary; review placement and boundary evidence.` });
    }
  }
  for (const o of candidates) if (isLinearUtility(o) && !(typeof o.meta?.pipe_diameter_ft === "number" && Number.isFinite(o.meta.pipe_diameter_ft) && o.meta.pipe_diameter_ft > 0)) {
    results.push({ severity: "review", code: "pipe_size_unknown", objectIds: [o.id], message: `${o.label}: outside diameter is missing. The displayed centerline is not enough to establish clearance.` });
  }
  candidates.forEach((a, i) => candidates.slice(i + 1).forEach(b => {
    const A = category(a), B = category(b);
    const objectIds = [a.id, b.id], names = `${a.label} / ${b.label}`;
    const result = (severity: InterferenceResult["severity"], code: string, detail: string) => results.push({ severity, code, objectIds, message: `${names}: ${detail}` });
    if ((a.meta?.coordinate_units ?? "ft") !== (b.meta?.coordinate_units ?? "ft")) { result("review", "coordinate_units_mismatch", "coordinate units differ; normalize the objects before evaluating interference."); return; }
    const zone = a.type === "setback_zone" ? a : b.type === "setback_zone" ? b : null;
    if (zone) {
      const other = zone === a ? b : a;
      if (category(other) === "restriction") return;
      const rule = zone.meta?.setback_rule_v1 as { version?: number; mode?: string; appliesTo?: string[]; source?: string; reviewed?: boolean } | undefined;
      const valid = rule?.version === 1 && ["excluded_area", "buildable_area"].includes(rule.mode ?? "") && Array.isArray(rule.appliesTo) && rule.appliesTo.length > 0 && rule.appliesTo.every(t => SITE_OBJECT_RULEBOOK[t as SiteObjectType] && !["container", "restriction"].includes(SITE_OBJECT_RULEBOOK[t as SiteObjectType].category)) && typeof rule.source === "string" && rule.source.trim() && rule.reviewed === true;
      if (!valid) { result("review", "setback_rule_unknown", "setback meaning, applicable types and reviewed source are missing; do not infer compliance from its outline."); return; }
      if (!rule!.appliesTo!.includes(other.type ?? "custom")) return;
      const violation = rule!.mode === "excluded_area" ? planContact(zone, other, shapes) : shapes.get(other)!.some(p => !footprintInside(shapes.get(zone)![0], p));
      if (violation) result("conflict", "setback_rule_violation", rule!.mode === "excluded_area" ? "contacts the entered excluded setback area." : "extends outside the entered buildable setback area.");
      return;
    }
    const contact = planContact(a, b, shapes);
    const eA = readCoordinationEnvelope(a), eB = readCoordinationEnvelope(b);
    if (eA || eB) {
      const unitsA = a.meta?.coordinate_units ?? "ft";
      const buffer = (eA?.bufferFt ?? 0) + (eB?.bufferFt ?? 0);
      const distanceFt = footprintDistance(shapes.get(a)!, shapes.get(b)!) / (unitsA === "m" ? .3048 : 1);
      if (buffer > 0 && distanceFt < buffer) { result("review", "coordination_envelope_contact", `footprint gap ${distanceFt.toFixed(2)} ft intrudes into entered ${[eA?.purpose, eB?.purpose].filter(Boolean).join(" / ")} buffers totaling ${buffer.toFixed(2)} ft. Vertical separation or a connection does not waive this requirement.`); }
    }
    if (!contact) return;
    if (A === "restriction" || B === "restriction") { result("review", "restricted_area_contact", "overlaps a no-build restriction; confirm applicable exclusions."); return; }
    // Only documented surface/network connections are intentional; access/roots remain separately checked.
    if (A === "surface" && B === "surface") {
      const frame = culDeSacFrame(a) ?? culDeSacFrame(b), other = culDeSacFrame(a) ? b : a;
      if (frame && shapes.get(other)!.some(p => checkFootprint(frame.layout, p.map(frame.toLocal)).island)) {
        results.push({ severity: "review", code: "access_crosses_island", objectIds: [a.id, b.id], message: `${a.label} / ${b.label}: access surface crosses the landscaped island; review curb and access geometry.` });
      } else if (!hasReviewedConnection(a, b)) result("review", "surface_connection_unverified", "overlapping access surfaces need a reviewed intentional connection; confirm junction, stall, curb and accessibility geometry.");
      return;
    }
    if (A === "landscape" && B === "landscape") return;
    if ([a, b].some(o => isLinearUtility(o) && !(typeof o.meta?.pipe_diameter_ft === "number" && Number.isFinite(o.meta.pipe_diameter_ft) && o.meta.pipe_diameter_ft > 0))) {
      result("review", "pipe_size_unknown", "pipe outside diameter is unknown; do not infer physical clearance from the centerline."); return;
    }
    if ((A === "utility" || A === "fixture") && (B === "utility" || B === "fixture") && hasReviewedConnection(a, b)) { result("review", "network_connection_review", "documented network connection; verify fitting/shaft geometry, network compatibility and maintenance access rather than treating it as an unrelated clash."); return; }
    const zA = readVerticalExtent(a), zB = readVerticalExtent(b);
    const detailed = assessDetailedPair(a, b, objectFootprints(a), objectFootprints(b), zA, zB);
    if (detailed !== null) {
      detailed.forEach(finding => result(finding.severity, finding.code, finding.message));
      return;
    }
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
