import type { BuildingPlacement, SiteObjectType } from "../types";

export type ObjectCategory = "structure" | "surface" | "utility" | "fixture" | "landscape" | "container" | "restriction" | "unknown";
export const SITE_OBJECT_RULEBOOK: Record<SiteObjectType, { category: ObjectCategory; guidance: string }> = {
  site: { category: "container", guidance: "Surveyed property boundary; not an occupied solid." },
  lot_block: { category: "container", guidance: "Planning subdivision; not an occupied solid." },
  setback_zone: { category: "restriction", guidance: "Specify excluded versus buildable area and applicable object types; do not assume zone meaning." },
  no_build_zone: { category: "restriction", guidance: "Restricted footprint; project-specific exceptions require review." },
  building: { category: "structure", guidance: "Include foundations and projections, not just the roof outline." },
  retail_building: { category: "structure", guidance: "Include foundations, projections and service access." },
  multifamily_building: { category: "structure", guidance: "Include foundations, projections and service access." },
  industrial_building: { category: "structure", guidance: "Include foundations, projections and service access." },
  office_building: { category: "structure", guidance: "Include foundations, projections and service access." },
  pad: { category: "structure", guidance: "Include supporting slab and equipment service space." },
  pool: { category: "structure", guidance: "Include below-ground shell and required access space." },
  amenity: { category: "structure", guidance: "Specify actual occupied structure and maintenance envelope." },
  basin: { category: "structure", guidance: "Include excavation, embankment and maintenance space; do not treat as empty land." },
  road: { category: "surface", guidance: "Junctions need intentional connection evidence; overlapping roads are not automatically compatible." },
  driveway: { category: "surface", guidance: "Confirm junction geometry and access requirements." },
  entrance: { category: "surface", guidance: "Confirm junction geometry and access requirements." },
  parking: { category: "surface", guidance: "Check circulation, stall conflicts and access separately." },
  sidewalk: { category: "surface", guidance: "Crossings require curb and accessibility review." },
  utility_corridor: { category: "utility", guidance: "Corridor is reserved space, not necessarily a pipe. Pipes need diameter, network and depth evidence." },
  hydrant: { category: "fixture", guidance: "Check service/access envelope; a pipe connection does not waive access requirements." },
  manhole: { category: "fixture", guidance: "Check shaft extent, access and intentional network connections." },
  inlet: { category: "fixture", guidance: "Check below-ground structure and intentional drainage connection." },
  outfall: { category: "fixture", guidance: "Check headwall, discharge and maintenance envelope." },
  landscape: { category: "landscape", guidance: "Include root protection and maintenance space where applicable." },
  open_space: { category: "landscape", guidance: "Planning overlap may be intentional; identify protected or maintained space." },
  bridge: { category: "unknown", guidance: "Deck, supports, foundations and underpass clearances need separate geometry/evidence." },
  custom: { category: "unknown", guidance: "Unclassified geometry requires review; do not infer engineering compatibility." },
};
export function objectRule(item: BuildingPlacement) {
  if (item.meta?.asset_kind === "pipe" || (item.geometryType === "polyline" && item.meta?.network)) return { category: "utility" as const, guidance: "Pipe/network crossing requires occupied diameter, depths and specified separation." };
  return SITE_OBJECT_RULEBOOK[item.type as SiteObjectType] ?? SITE_OBJECT_RULEBOOK.custom;
}
export type CoordinationEnvelope = { version: 1; bufferFt: number; purpose: "roots" | "foundation" | "maintenance" | "separation"; source: string; reviewed: boolean };
export function readCoordinationEnvelope(item: BuildingPlacement): CoordinationEnvelope | null {
  const value = item.meta?.coordination_envelope_v1 as CoordinationEnvelope | undefined;
  return value?.version === 1 && Number.isFinite(value.bufferFt) && value.bufferFt >= 0 && ["roots", "foundation", "maintenance", "separation"].includes(value.purpose) && typeof value.source === "string" && value.source.trim() && value.reviewed === true ? value : null;
}
export function hasReviewedConnection(a: BuildingPlacement, b: BuildingPlacement) {
  return [a, b].some((item, i) => {
    const value = item.meta?.intentional_connections_v1 as { version?: number; objectIds?: string[]; source?: string; reviewed?: boolean } | undefined;
    return value?.version === 1 && value.reviewed === true && typeof value.source === "string" && value.source.trim() && Array.isArray(value.objectIds) && value.objectIds.includes([b, a][i].id);
  });
}
