import type { BuildingPlacement } from "../types";
import { defaultLayout, geometry } from "./culDeSacConcept";

export type CulDeSacParameters = { version: 1; bulbRadiusFt: number; roadWidthFt: number; islandRadiusFt: 15; transitionRadiusFt: 20; coordinateUnits: "ft" | "m" };
export const defaultCulDeSacParameters = (units = "ft"): CulDeSacParameters => ({ version: 1, bulbRadiusFt: 50, roadWidthFt: 30, islandRadiusFt: 15, transitionRadiusFt: 20, coordinateUnits: units === "m" ? "m" : "ft" });
export function readCulDeSac(item: Pick<BuildingPlacement, "type" | "meta">): CulDeSacParameters | null {
  const p = item.meta?.cul_de_sac_v1 as CulDeSacParameters | undefined;
  if (item.type !== "road" || !p || p.version !== 1 || !Number.isFinite(p.bulbRadiusFt) || p.bulbRadiusFt < 35 || p.bulbRadiusFt > 80 ||
      !Number.isFinite(p.roadWidthFt) || p.roadWidthFt < 20 || p.roadWidthFt > 48 || p.islandRadiusFt !== 15 || p.transitionRadiusFt !== 20 || !["ft", "m"].includes(p.coordinateUnits)) return null;
  return p;
}
export function culDeSacFrame(item: BuildingPlacement) {
  const p = readCulDeSac(item);
  if (!p) return null;
  const scale = p.coordinateUnits === "m" ? .3048 : 1, g = geometry(p.bulbRadiusFt, p.roadWidthFt);
  const cx = (item.x ?? 0) + g.R * scale, cy = (item.y ?? 0) + (g.bottom + g.R) * scale / 2;
  const angle = (item.rotation ?? 0) * Math.PI / 180;
  const toWorld = ([x, y]: [number, number]): [number, number] => {
    const dy = (y - (g.bottom - g.R) / 2) * scale, dx = x * scale;
    return [cx + dx * Math.cos(angle) - dy * Math.sin(angle), cy + dx * Math.sin(angle) + dy * Math.cos(angle)];
  };
  const toLocal = ([x, y]: [number, number]): [number, number] => {
    const dx = x - cx, dy = y - cy;
    return [(dx * Math.cos(angle) + dy * Math.sin(angle)) / scale, (-dx * Math.sin(angle) + dy * Math.cos(angle)) / scale + (g.bottom - g.R) / 2];
  };
  return { p, g, scale, toWorld, toLocal, layout: { ...defaultLayout(), bulbRadius: p.bulbRadiusFt, roadWidth: p.roadWidthFt } };
}
export function regenerateCulDeSac(item: BuildingPlacement): BuildingPlacement {
  const frame = culDeSacFrame(item);
  if (!frame) return item;
  const { g, scale, toWorld } = frame;
  const points: Array<[number, number]> = [[-g.a, g.bottom], [-g.a, g.y]];
  // Exportable linework within 0.02 ft chord error. Checks remain analytic.
  const arc = (x: number, y: number, r: number, start: number, sweep: number) => {
    const count = Math.ceil(Math.abs(sweep) / (2 * Math.acos(1 - .02 / r)));
    for (let i = 1; i <= count; i++) { const a = start + sweep * i / count; points.push([x + r * Math.cos(a), y + r * Math.sin(a)]); }
  };
  arc(-g.x, g.y, g.f, 0, -g.theta); arc(0, 0, g.R, Math.PI - g.theta, Math.PI + 2 * g.theta); arc(g.x, g.y, g.f, -Math.PI + g.theta, -g.theta);
  points.push([g.a, g.bottom]);
  return { ...item, w: 2 * g.R * scale, d: (g.bottom + g.R) * scale, geometryType: "polygon", geometry: points.map(toWorld),
    meta: { ...item.meta, draft_review_required: true }, capabilities: { ...item.capabilities, resizable: false } };
}
/** Arbitrary vertex/scaling edits detach the template rather than retaining false arc claims. */
export function reconcileCulDeSacUpdate(target: BuildingPlacement, updates: Partial<BuildingPlacement>): Partial<BuildingPlacement> {
  if (!readCulDeSac(target) && !readCulDeSac({ ...target, ...updates })) return updates;
  const merged = { ...target, ...updates, meta: { ...target.meta, ...updates.meta } };
  const dimensionChange = Boolean(updates.meta && "cul_de_sac_v1" in updates.meta);
  const transformChange = updates.x !== undefined || updates.y !== undefined || updates.rotation !== undefined;
  if (merged.type !== "road" || (!dimensionChange && !transformChange && (updates.geometry !== undefined || updates.w !== undefined || updates.d !== undefined))) {
    const meta = { ...merged.meta }; delete meta.cul_de_sac_v1;
    return { ...updates, meta, capabilities: { ...target.capabilities, resizable: true } };
  }
  return { ...updates, ...regenerateCulDeSac(merged) };
}
