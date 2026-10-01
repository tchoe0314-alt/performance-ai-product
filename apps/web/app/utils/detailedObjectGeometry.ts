import type { BuildingPlacement } from "../types";
import { polygonContains, segmentsTouch, type FootprintPoint as Point } from "./culDeSacConcept";

type Evidence = { version: 1; datum: string; source: string; reviewed: boolean; requiredClearanceFt: number | null; geometryBinding: string };
export type OccupiedComponent = { id: string; kind: "body" | "foundation" | "deck" | "support"; label: string; xFt: number; yFt: number; wFt: number; dFt: number; minFt: number; maxFt: number };
export type ComponentModel = Evidence & { complete: boolean; components: OccupiedComponent[] };
export type PipeProfile = Evidence & { centerElevationsFt: number[] };
export type DetailedFinding = { severity: "conflict" | "review" | "clear"; code: string; message: string };
export const detailedGeometryBinding = (item: BuildingPlacement) => JSON.stringify([item.type, item.x, item.y, item.w, item.d, item.rotation ?? 0, item.geometryType, item.geometry, item.meta?.coordinate_units ?? "ft", item.meta?.pipe_diameter_ft]);
const text = (value: unknown): value is string => typeof value === "string" && Boolean(value.trim());
function validEvidence(value: Partial<Evidence>, item: BuildingPlacement) {
  return [item.x ?? 0, item.y ?? 0, item.w, item.d, item.rotation ?? 0].every(Number.isFinite) && item.w > 0 && item.d > 0 && ["ft", "m"].includes(String(item.meta?.coordinate_units ?? "ft")) && value.version === 1 && text(value.datum) && text(value.source) && value.reviewed === true && value.geometryBinding === detailedGeometryBinding(item) && (value.requiredClearanceFt === null || (typeof value.requiredClearanceFt === "number" && Number.isFinite(value.requiredClearanceFt) && value.requiredClearanceFt >= 0));
}
export function validateComponentModel(value: unknown, item: BuildingPlacement): string | null {
  if (item.meta?.pipe_profile_v1) return "Choose one detailed model: occupied parts or a pipe profile, not both.";
  if (!value || typeof value !== "object") return "Component evidence is missing.";
  const model = value as ComponentModel;
  if (!validEvidence(model, item)) return "Component evidence is incomplete, unreviewed, or belongs to different geometry. Reapply after reviewing the current object.";
  if (!model.complete || !Array.isArray(model.components) || !model.components.length || model.components.length > 64) return "Confirm a complete occupied model with 1–64 parts.";
  if (new Set(model.components.map(c => c?.id)).size !== model.components.length) return "Part identifiers must be unique.";
  if (model.components.some(c => !c || !text(c.id) || !text(c.label) || !["body", "foundation", "deck", "support"].includes(c.kind) || ![c.xFt, c.yFt, c.wFt, c.dFt, c.minFt, c.maxFt].every(Number.isFinite) || c.wFt <= 0 || c.dFt <= 0 || c.minFt > c.maxFt)) return "Every part needs an identifier, label, kind, positive footprint and ordered finite elevations.";
  const kinds = model.components.map(c => c.kind);
  if (item.type === "bridge" ? !["deck", "support", "foundation"].every(k => kinds.includes(k as OccupiedComponent["kind"])) : !kinds.includes("body")) return item.type === "bridge" ? "A bridge model must include deck, support and foundation parts." : "Include the occupied body as well as any foundations or supports.";
  return null;
}
export function validatePipeProfile(value: unknown, item: BuildingPlacement): string | null {
  if (item.meta?.occupied_components_v1) return "Choose one detailed model: occupied parts or a pipe profile, not both.";
  if (!value || typeof value !== "object") return "Pipe profile evidence is missing.";
  const profile = value as PipeProfile, diameter = item.meta?.pipe_diameter_ft;
  if (!validEvidence(profile, item)) return "Pipe profile evidence is incomplete, unreviewed, or belongs to different geometry. Reapply after reviewing the current route.";
  if (item.geometryType !== "polyline" || !item.geometry || item.geometry.length < 2 || item.geometry.some(p => !p.every(Number.isFinite))) return "A pipe profile requires a finite polyline route.";
  if (typeof diameter !== "number" || !Number.isFinite(diameter) || diameter <= 0) return "Enter the actual pipe outside diameter first.";
  if (!Array.isArray(profile.centerElevationsFt) || profile.centerElevationsFt.length !== item.geometry.length || !profile.centerElevationsFt.every(Number.isFinite)) return "Supply one finite center elevation for every route vertex.";
  if (item.geometry.some((p, i) => i > 0 && Math.hypot(p[0] - item.geometry![i - 1][0], p[1] - item.geometry![i - 1][1]) < 1e-9)) return "Remove duplicate route vertices before applying a pipe profile.";
  return null;
}
export function componentFootprint(item: BuildingPlacement, c: OccupiedComponent): Point[] {
  const unit = item.meta?.coordinate_units === "m" ? .3048 : 1;
  const cx = (item.x ?? 0) + item.w / 2, cy = (item.y ?? 0) + item.d / 2, angle = (item.rotation ?? 0) * Math.PI / 180;
  return [[c.xFt, c.yFt], [c.xFt + c.wFt, c.yFt], [c.xFt + c.wFt, c.yFt + c.dFt], [c.xFt, c.yFt + c.dFt]].map(([x, y]) => {
    const dx = (item.x ?? 0) + x * unit - cx, dy = (item.y ?? 0) + y * unit - cy;
    return [cx + dx * Math.cos(angle) - dy * Math.sin(angle), cy + dx * Math.sin(angle) + dy * Math.cos(angle)] as Point;
  });
}
export function reviewedComponentFootprints(item: BuildingPlacement): Point[][] {
  const model = item.meta?.occupied_components_v1;
  return model && !validateComponentModel(model, item) ? (model as ComponentModel).components.map(c => componentFootprint(item, c)) : [];
}
const sub = (a: Point, b: Point): Point => [a[0] - b[0], a[1] - b[1]];
const dot = (a: Point, b: Point) => a[0] * b[0] + a[1] * b[1];
const cross = (a: Point, b: Point) => a[0] * b[1] - a[1] * b[0];
function pointSegmentDistance(p: Point, a: Point, b: Point) {
  const d = sub(b, a), length2 = dot(d, d), t = length2 ? Math.max(0, Math.min(1, dot(sub(p, a), d) / length2)) : 0;
  return Math.hypot(p[0] - a[0] - t * d[0], p[1] - a[1] - t * d[1]);
}
/** Analytic entry/exit parameters of a swept horizontal pipe disk against a polygon. */
export function pipeContactIntervals(a: Point, b: Point, polygon: Point[], radius: number): [number, number][] {
  const d = sub(b, a), length2 = dot(d, d), splits = [0, 1];
  if (length2 < 1e-18) return [];
  const add = (t: number) => { if (Number.isFinite(t) && t >= -1e-9 && t <= 1 + 1e-9) splits.push(Math.max(0, Math.min(1, t))); };
  polygon.forEach((p, i) => {
    const q = polygon[(i + 1) % polygon.length], edge = sub(q, p), delta = sub(p, a), denominator = cross(d, edge);
    if (Math.abs(denominator) > 1e-12) {
      const t = cross(delta, edge) / denominator, u = cross(delta, d) / denominator;
      if (u >= 0 && u <= 1) add(t);
    }
    const from = sub(a, p), qb = 2 * dot(from, d), qc = dot(from, from) - radius * radius, discriminant = qb * qb - 4 * length2 * qc;
    if (discriminant >= -1e-9) { const root = Math.sqrt(Math.max(0, discriminant)); add((-qb - root) / (2 * length2)); add((-qb + root) / (2 * length2)); }
    const edgeLength = Math.sqrt(dot(edge, edge)), slope = cross(d, edge);
    if (edgeLength && Math.abs(slope) > 1e-12) for (const sign of [-1, 1]) add((sign * radius * edgeLength - cross(from, edge)) / slope);
  });
  splits.sort((x, y) => x - y);
  const points = splits.filter((t, i) => !i || t - splits[i - 1] > 1e-10);
  const inside = (t: number) => {
    const p: Point = [a[0] + t * d[0], a[1] + t * d[1]];
    return polygonContains(polygon, p) || polygon.some((q, i) => pointSegmentDistance(p, q, polygon[(i + 1) % polygon.length]) <= radius + 1e-8);
  };
  const intervals: [number, number][] = [];
  for (let i = 1; i < points.length; i++) if (inside((points[i - 1] + points[i]) / 2)) intervals.push([points[i - 1], points[i]]);
  for (const t of points) if (inside(t) && !intervals.some(([lo, hi]) => t >= lo - 1e-9 && t <= hi + 1e-9)) intervals.push([t, t]);
  return intervals;
}
function polygonsContact(a: Point[], b: Point[]) {
  return a.some(p => polygonContains(b, p)) || b.some(p => polygonContains(a, p)) || a.some((p, i) => b.some((q, j) => segmentsTouch(p, a[(i + 1) % a.length], q, b[(j + 1) % b.length])));
}
type Volume = { label: string; polygon: Point[]; minFt: number; maxFt: number; datum: string; requiredClearanceFt: number | null };
function volumes(item: BuildingPlacement, footprints: Point[][], basic: { minFt: number; maxFt: number; datum: string; requiredClearanceFt: number | null } | null): Volume[] | null {
  const model = item.meta?.occupied_components_v1 as ComponentModel | undefined;
  if (model) return validateComponentModel(model, item) ? null : model.components.map(c => ({ ...c, polygon: componentFootprint(item, c), datum: model.datum, requiredClearanceFt: model.requiredClearanceFt }));
  return basic ? footprints.map(polygon => ({ ...basic, polygon, label: item.label })) : null;
}
function compare(a: Omit<Volume, "polygon">, b: Omit<Volume, "polygon">): DetailedFinding {
  if (a.datum !== b.datum) return { severity: "review", code: "detailed_datum_mismatch", message: `${a.label} / ${b.label}: elevation datums differ.` };
  const gap = Math.max(a.minFt - b.maxFt, b.minFt - a.maxFt);
  if (gap <= 0) return { severity: "conflict", code: "detailed_volume_contact", message: `${a.label} / ${b.label}: occupied component/profile envelopes touch or overlap at this crossing.` };
  if (a.requiredClearanceFt === null || b.requiredClearanceFt === null) return { severity: "review", code: "detailed_clearance_unknown", message: `${a.label} / ${b.label}: separated, but required project clearance is missing.` };
  const required = Math.max(a.requiredClearanceFt, b.requiredClearanceFt);
  return gap < required ? { severity: "conflict", code: "detailed_clearance_shortfall", message: `${a.label} / ${b.label}: local gap ${gap.toFixed(2)} ft is below entered ${required.toFixed(2)} ft clearance.` } : { severity: "clear", code: "detailed_modeled_separation", message: `${a.label} / ${b.label}: local modeled gap ${gap.toFixed(2)} ft meets entered clearance; not design approval.` };
}
export function assessDetailedPair(a: BuildingPlacement, b: BuildingPlacement, footprintsA: Point[][], footprintsB: Point[][], basicA: Parameters<typeof volumes>[2], basicB: Parameters<typeof volumes>[2]): DetailedFinding[] | null {
  if (![a, b].some(o => o.meta?.occupied_components_v1 || o.meta?.pipe_profile_v1)) return null;
  for (const item of [a, b]) {
    const error = item.meta?.occupied_components_v1 ? validateComponentModel(item.meta.occupied_components_v1, item) : item.meta?.pipe_profile_v1 ? validatePipeProfile(item.meta.pipe_profile_v1, item) : null;
    if (error) return [{ severity: "review", code: "detailed_evidence_invalid", message: `${item.label}: ${error}` }];
  }
  const profileItem = a.meta?.pipe_profile_v1 ? a : b.meta?.pipe_profile_v1 ? b : null;
  if (profileItem) {
    const other = profileItem === a ? b : a;
    if (other.meta?.pipe_profile_v1) return [{ severity: "review", code: "profile_profile_review", message: "Two varying-depth pipe profiles require 3D tube-to-tube review; no clearance is inferred." }];
    const targets = volumes(other, profileItem === a ? footprintsB : footprintsA, profileItem === a ? basicB : basicA);
    if (!targets) return [{ severity: "review", code: "detailed_evidence_missing", message: `${other.label}: reviewed occupied components or vertical extents are required.` }];
    const profile = profileItem.meta!.pipe_profile_v1 as PipeProfile, rFt = Number(profileItem.meta!.pipe_diameter_ft) / 2, unit = profileItem.meta?.coordinate_units === "m" ? .3048 : 1;
    const findings: DetailedFinding[] = [];
    profileItem.geometry!.slice(1).forEach((end, j) => targets.forEach(target => {
      const start = profileItem.geometry![j], z0 = profile.centerElevationsFt[j], z1 = profile.centerElevationsFt[j + 1];
      for (const [lo, hi] of pipeContactIntervals(start, end, target.polygon, rFt * unit)) {
        const elevations = [z0 + (z1 - z0) * lo, z0 + (z1 - z0) * hi];
        findings.push(compare({ ...profile, label: `${profileItem.label} segment ${j + 1}`, minFt: Math.min(...elevations) - rFt, maxFt: Math.max(...elevations) + rFt }, target));
      }
    }));
    return findings;
  }
  const A = volumes(a, footprintsA, basicA), B = volumes(b, footprintsB, basicB);
  if (!A || !B) return [{ severity: "review", code: "detailed_evidence_missing", message: "Both objects need reviewed occupied components or vertical extents." }];
  return A.flatMap(v => B.filter(w => polygonsContact(v.polygon, w.polygon)).map(w => compare(v, w)));
}
