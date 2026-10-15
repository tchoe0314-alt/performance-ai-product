import definitions from "../../../../core/data/site_object_definitions_v1.json";
import type { BuildingPlacement } from "../types";
import {isPhysicalCanvasObject} from "./objectGroups";

export const OBJECT_SCHEMA_VERSION = "civora_object_v1";
export type ObjectDefinition = {
  schema_version: typeof OBJECT_SCHEMA_VERSION;
  id: string; name: string; type: string; custom_type_id: string | null;
  geometry: { kind: string; origin: number[]; size: number[]; rotation: number; coordinates: number[][] };
  units: { length: string | null };
  layer: { id: string; visible: boolean; locked: boolean };
  source: { kind: string; reference: string | null; verified: boolean };
  created_by: { kind: string; actor_id: string | null };
  revision: { number: number; last_edit: unknown };
  validation: { status: "valid" | "invalid" | "unverified"; issues: string[]; paused_systems: string[]; engineering_verified: false };
  dependency_status: "clear" | "needs_review";
  relationships: { parent_group_id: string | null; object_ids: string[]; calculation_ids: string[] };
  export_mapping: { layer: string; geometry_kind: string; mode: string };
  properties: Record<string, unknown>;
};
export type CustomTypeDefinition = { id: string; name: string; fields: Array<{ name: string; type: "text" | "number" | "boolean"; unit?: string }>; version: 1 };
export function validateCustomTypeDefinition(value: unknown): CustomTypeDefinition {
  const type = value as CustomTypeDefinition;
  if (!type || type.version !== 1 || typeof type.id !== "string" || !/^custom-[a-zA-Z0-9-]{1,100}$/.test(type.id) || typeof type.name !== "string" || !type.name.trim() || type.name.length>100 || !Array.isArray(type.fields) || type.fields.length>30) throw new Error("Saved custom type is invalid.");
  const names = new Set<string>();
  for (const field of type.fields) {
    if (!field || typeof field.name !== "string" || !field.name.trim() || field.name.length>80 || !["text","number","boolean"].includes(field.type) || ["__proto__","prototype","constructor"].includes(field.name) || names.has(field.name.trim().toLowerCase()) || (field.unit !== undefined && (typeof field.unit !== "string" || field.unit.length>30))) throw new Error("Saved custom type field is invalid.");
    names.add(field.name.trim().toLowerCase());
  }
  return type;
}
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value));
export function typeDefinition(type: string | undefined): { geometry: string[]; layer: string; systems: string[]; export?: string } {
  const key=type ?? "custom";
  return Object.hasOwn(definitions.types,key) ? (definitions.types as Record<string, { geometry: string[]; layer: string; systems: string[]; export?: string }>)[key] : definitions.types.custom;
}
const distance = (a: number[], b: number[]) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const geometryKind = (item: BuildingPlacement): string => item.geometryType ?? (item as unknown as {geometry_type?: string}).geometry_type ?? "rect";
export function geometryIssues(item: BuildingPlacement): string[] {
  const kind = geometryKind(item);
  const points = item.geometry ?? [];
  const issues: string[] = [];
  if (!Array.isArray(points) || points.some(p => !Array.isArray(p) || p.length !== 2)) return ["Geometry must contain coordinate pairs."];
  if (!typeDefinition(item.type).geometry.includes(kind)) issues.push("This type needs a closed outline.");
  if (![item.x ?? 0, item.y ?? 0, item.w, item.d, item.rotation ?? 0, ...points.flat()].every(Number.isFinite)) return ["Geometry must contain finite coordinates."];
  if (kind === "rect" && (item.w <= 0 || item.d <= 0)) issues.push("Dimensions must be positive.");
  if (kind === "point" && points.length !== 1) issues.push("A point needs one coordinate.");
  if (kind === "polyline" && (points.length < 2 || points.slice(1).some((p, i) => distance(p, points[i]) <= 1e-7))) issues.push("A line needs distinct connected points.");
  if (kind === "polygon") {
    const ring = points.length > 1 && distance(points[0], points.at(-1)!) <= 1e-7 ? points.slice(0, -1) : points;
    const area = Math.abs(ring.reduce((sum, p, i) => { const q = ring[(i + 1) % ring.length]; return sum + p[0] * q[1] - q[0] * p[1]; }, 0)) / 2;
    if (ring.length < 3 || area <= 1e-7) issues.push("An outline needs at least three points and a nonzero area.");
    const cross = (a: number[], b: number[], c: number[]) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    const on = (a: number[], b: number[], c: number[]) => Math.abs(cross(a, b, c)) <= 1e-7 && c[0] >= Math.min(a[0], b[0]) - 1e-7 && c[0] <= Math.max(a[0], b[0]) + 1e-7 && c[1] >= Math.min(a[1], b[1]) - 1e-7 && c[1] <= Math.max(a[1], b[1]) + 1e-7;
    for (let i = 0; i < ring.length; i++) {
      const a = ring[i], b = ring[(i + 1) % ring.length];
      if (distance(a, b) <= 1e-7) issues.push("An outline has a zero-length edge.");
      for (let j = i + 1; j < ring.length; j++) {
        if (j === i + 1 || (i === 0 && j === ring.length - 1)) continue;
        const c = ring[j], d = ring[(j + 1) % ring.length];
        if ((cross(a, b, c) * cross(a, b, d) < 0 && cross(c, d, a) * cross(c, d, b) < 0) || on(a, b, c) || on(a, b, d) || on(c, d, a) || on(c, d, b)) issues.push("The outline crosses or touches itself.");
      }
    }
  }
  if (item.meta?.semantic_source_mode === "program_group_bounds" && item.type !== "custom" && item.type !== "group") issues.push("Group bounds are not a verified combined footprint.");
  return [...new Set(issues)];
}
export function objectDefinition(item: BuildingPlacement, units: string | null, previous?: ObjectDefinition): ObjectDefinition {
  if (!item.id || typeof item.id !== "string") throw new Error("Objects need stable IDs.");
  const definition = typeDefinition(item.type);
  const issues = geometryIssues(item);
  const meta = item.meta ?? {};
  const parking = (meta.canonical_relationships as {parking?: {object_ids?: unknown}} | undefined)?.parking?.object_ids;
  const graphTargets=Array.isArray(meta.dependency_links_v1)?meta.dependency_links_v1.map((edge:{target_id?:unknown})=>edge?.target_id):[];
  const relations = [...new Set([...(Array.isArray(meta.object_relationship_ids_v1) ? meta.object_relationship_ids_v1 : [...(Array.isArray(parking) ? parking : Array.isArray(meta.linked_parking_ids) ? meta.linked_parking_ids : []), ...(Array.isArray(meta.combined_from_object_ids) ? meta.combined_from_object_ids : [])]),...graphTargets].filter((id): id is string => typeof id === "string"))];
  const record: ObjectDefinition = {
    schema_version: OBJECT_SCHEMA_VERSION, id: item.id, name: item.label?.trim() || `${(item.type ?? "custom").replaceAll("_", " ")} ${item.id.slice(-6)}`,
    type: item.type ?? "custom", custom_type_id: typeof meta.custom_type_id === "string" ? meta.custom_type_id : null,
    geometry: { kind: geometryKind(item), origin: [item.x ?? 0, item.y ?? 0], size: [item.w ?? 0, item.d ?? 0, item.h ?? (item as unknown as {height_ft?:number}).height_ft ?? 0], rotation: item.rotation ?? 0, coordinates: clone(item.geometry ?? []) },
    units: { length: units }, layer: { id: typeof meta.layer_id === "string" ? meta.layer_id : definition.layer, visible: meta.ui_hidden !== true, locked: item.locked === true },
    source: { kind: item.source ?? "unknown", reference: typeof meta.source_id === "string" ? meta.source_id : null, verified: meta.source_verified === true },
    created_by: previous?.created_by ?? { kind: item.generated || item.source === "generated" ? "system" : item.source?.startsWith("detected") ? "import" : ["user", "manual_drawn", "user_confirmed"].includes(item.source ?? "") ? "user" : "unknown", actor_id: null },
    revision: { number: previous?.revision.number ?? 1, last_edit: clone(meta.canonical_last_edit ?? null) },
    validation: { status: issues.length ? "invalid" : item.type === "custom" || !Object.hasOwn(definitions.types,item.type ?? "custom") ? "unverified" : "valid", issues, paused_systems: item.placed === false ? [] : issues.length ? definition.systems : [], engineering_verified: false },
    dependency_status: relations.length ? "needs_review" : "clear",
    relationships: { parent_group_id: typeof meta.group_id === "string" ? meta.group_id : null, object_ids: relations, calculation_ids: Array.isArray(meta.calculation_ids) ? meta.calculation_ids.filter((id): id is string => typeof id === "string") : [] },
    export_mapping: { layer: definition.layer, geometry_kind: geometryKind(item), mode: definition.export ?? (item.type === "custom" || !Object.hasOwn(definitions.types,item.type ?? "custom") ? "reference_only" : "review_geometry") },
    properties: clone(meta.custom_properties_v1 as Record<string, unknown> ?? {}),
  };
  if (previous) {
    const content = (value: ObjectDefinition) => JSON.stringify({ ...value, revision: undefined, validation: undefined, created_by: undefined });
    if (content(previous) !== content(record)) record.revision.number++;
  }
  return record;
}
export function placementFromDefinition(item: BuildingPlacement, value: unknown): BuildingPlacement {
  const record = value as ObjectDefinition;
  if (!record || record.schema_version !== OBJECT_SCHEMA_VERSION || record.id !== item.id || !record.geometry || !record.layer || !record.relationships || !record.revision || !record.validation || !record.source || !record.created_by || !record.export_mapping || !record.units || !record.properties) throw new Error("Saved object definition is invalid.");
  const finiteTuple = (v: unknown, count: number) => Array.isArray(v) && v.length === count && v.every(n => typeof n === "number" && Number.isFinite(n));
  if (!finiteTuple(record.geometry.origin, 2) || !finiteTuple(record.geometry.size, 3) || !Number.isFinite(record.geometry.rotation) || !["rect", "polygon", "polyline", "point"].includes(record.geometry.kind)
    || !Array.isArray(record.geometry.coordinates) || !record.geometry.coordinates.every(p => finiteTuple(p, 2))
    || typeof record.name !== "string" || typeof record.type !== "string" || typeof record.layer.id !== "string" || typeof record.layer.visible !== "boolean" || typeof record.layer.locked !== "boolean"
    || !Number.isInteger(record.revision.number) || record.revision.number < 1 || !Array.isArray(record.relationships.object_ids) || !record.relationships.object_ids.every(v => typeof v === "string")
    || !Array.isArray(record.relationships.calculation_ids) || !record.relationships.calculation_ids.every(v => typeof v === "string") || (record.relationships.parent_group_id !== null && typeof record.relationships.parent_group_id !== "string")
    || (record.units.length !== null && typeof record.units.length !== "string") || Array.isArray(record.properties) || typeof record.properties !== "object") throw new Error("Saved object definition is invalid.");
  if (typeof record.source.kind !== "string" || typeof record.source.verified !== "boolean" || (record.source.reference !== null && typeof record.source.reference !== "string") || typeof record.created_by.kind !== "string" || (record.created_by.actor_id !== null && typeof record.created_by.actor_id !== "string")
    || !["valid","invalid","unverified"].includes(record.validation.status) || record.validation.engineering_verified !== false || !Array.isArray(record.validation.issues) || !record.validation.issues.every(v=>typeof v==="string") || !Array.isArray(record.validation.paused_systems) || !record.validation.paused_systems.every(v=>typeof v==="string")
    || !["clear","needs_review"].includes(record.dependency_status) || typeof record.export_mapping.layer !== "string" || typeof record.export_mapping.geometry_kind !== "string" || !["reference_only","review_geometry","organization_only"].includes(record.export_mapping.mode)) throw new Error("Saved object definition is invalid.");
  const original = objectDefinition(item, record.units.length);
  const result = clone(item);
  if (record.name !== original.name || "label" in item) result.label = record.name;
  if (record.type !== original.type || "type" in item) result.type = record.type as BuildingPlacement["type"];
  for (const [index, key] of ["x", "y"].entries()) if (record.geometry.origin[index] !== original.geometry.origin[index] || (item as unknown as Record<string,unknown>)[key] != null) (result as unknown as Record<string, unknown>)[key] = record.geometry.origin[index];
  for (const [index, key] of ["w", "d", "height_ft" in item ? "height_ft" : "h"].entries()) if (record.geometry.size[index] !== original.geometry.size[index] || (item as unknown as Record<string,unknown>)[key] != null) (result as unknown as Record<string, unknown>)[key] = record.geometry.size[index];
  if (record.geometry.rotation !== original.geometry.rotation || item.rotation != null) result.rotation = record.geometry.rotation;
  if (record.geometry.kind !== original.geometry.kind || "geometry_type" in item || "geometryType" in item) {
    if ("geometry_type" in item) (result as unknown as {geometry_type:string}).geometry_type = record.geometry.kind;
    else result.geometryType = record.geometry.kind as BuildingPlacement["geometryType"];
  }
  if (JSON.stringify(record.geometry.coordinates) !== JSON.stringify(original.geometry.coordinates) || "geometry" in item) result.geometry = clone(record.geometry.coordinates) as Array<[number, number]>;
  if (record.layer.locked !== original.layer.locked || "locked" in item) result.locked = record.layer.locked;
  if (record.source.kind !== original.source.kind || item.source != null) result.source = record.source.kind as BuildingPlacement["source"];
  const meta = { ...result.meta };
  if (record.layer.visible !== original.layer.visible || "ui_hidden" in meta) meta.ui_hidden = !record.layer.visible;
  if (record.layer.id !== original.layer.id || "layer_id" in meta) meta.layer_id = record.layer.id;
  if (record.relationships.parent_group_id !== original.relationships.parent_group_id || "group_id" in meta) meta.group_id = record.relationships.parent_group_id;
  if (record.custom_type_id !== original.custom_type_id || "custom_type_id" in meta) meta.custom_type_id = record.custom_type_id;
  if (JSON.stringify(record.properties) !== JSON.stringify(original.properties) || "custom_properties_v1" in meta) meta.custom_properties_v1 = clone(record.properties);
  if (record.source.reference !== original.source.reference || "source_id" in meta) meta.source_id = record.source.reference;
  if (record.source.verified !== original.source.verified || "source_verified" in meta) meta.source_verified = record.source.verified;
  if (JSON.stringify(record.relationships.object_ids) !== JSON.stringify(original.relationships.object_ids) || "object_relationship_ids_v1" in meta) meta.object_relationship_ids_v1 = clone(record.relationships.object_ids);
  if (JSON.stringify(record.relationships.calculation_ids) !== JSON.stringify(original.relationships.calculation_ids) || "calculation_ids" in meta) meta.calculation_ids = clone(record.relationships.calculation_ids);
  if (Object.keys(meta).length) result.meta = meta;
  return result;
}
export function pausedObjectSystems(objects: BuildingPlacement[]): string[] {
  return [...new Set(objects.filter(item=>isPhysicalCanvasObject(item,objects)).flatMap(item => objectDefinition(item, null).validation.paused_systems))];
}
export function validateObjectGroups(objects: BuildingPlacement[]): void {
  const byId = new Map(objects.map(item => [item.id, item]));
  if (byId.size !== objects.length) throw new Error("Canvas object IDs are duplicated.");
  for (const item of objects) {
    if (typeof item.id !== "string" || !item.id) throw new Error("Objects need stable IDs.");
    const seen = new Set([item.id]);
    let parent = item.meta?.group_id;
    while (parent != null) {
      if (typeof parent !== "string" || seen.has(parent) || byId.get(parent)?.type !== "group") throw new Error("Object groups have a missing parent or cycle.");
      seen.add(parent);
      parent = byId.get(parent)?.meta?.group_id;
    }
  }
}
