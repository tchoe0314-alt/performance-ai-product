import type { BuildingPlacement } from "../types";

export type ParkingParams = {
  stallWidth?: number;
  stallDepth?: number;
  aisleWidth?: number;
  adaAisleWidth?: number;
  adaCount?: number;
  compactCount?: number;
  compactWidth?: number;
  angleDeg?: number;
  loading?: "single" | "double";
  autoResizeToFitCount?: boolean;
  useMixedAngles?: boolean;
  compactZone?: boolean;
};

export type PreviewSourceState = "verified" | "imported" | "inferred" | "stale" | "blocked" | "fallback";

export const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

export const readMetaNumber = (meta: Record<string, unknown> | undefined, keys: string[]): number | null => {
  if (!meta) return null;
  for (const key of keys) {
    const value = toFiniteNumber(meta[key]);
    if (value !== null) return value;
  }
  return null;
};

export const normalizeFlowStatus = (value: unknown): "pass" | "review" | "fail" => {
  const status = String(value || "").toLowerCase();
  if (status.includes("fail") || status.includes("block")) return "fail";
  if (status.includes("pass") || status.includes("ok") || status.includes("ready")) return "pass";
  return "review";
};

export const formatFlowValue = (value: number | null | undefined, unit: string, decimals = 0) =>
  value === null || value === undefined || Number.isNaN(value) ? "--" : `${value.toFixed(decimals)} ${unit}`;

export const normalizeSystemLabel = (value: unknown) => {
  const raw = String(value || "").toLowerCase();
  if (raw.includes("storm") || raw.includes("drain")) return "Storm";
  if (raw.includes("sanitary") || raw.includes("sewer")) return "Sanitary";
  if (raw.includes("water") || raw.includes("hydrant")) return "Water";
  if (raw.includes("gas")) return "Gas";
  if (raw.includes("electric") || raw.includes("power")) return "Electric";
  if (raw.includes("telecom") || raw.includes("fiber")) return "Telecom";
  if (raw.includes("road")) return "Road";
  if (raw.includes("building")) return "Building";
  if (raw.includes("utility")) return "Utility";
  return String(value || "Utility").replace(/_/g, " ");
};

export const formatClearance = (value: number | null | undefined) =>
  value === null || value === undefined || Number.isNaN(value) ? "Needs source" : `${value.toFixed(1)} ft`;

export const hasExplicitFootprintGeometry = (item: BuildingPlacement) =>
  (item.geometryType === "polygon" || item.geometryType === "polyline" || item.geometryType === "point") &&
  Array.isArray(item.geometry) &&
  item.geometry.length > 0;

export const resolveSourceState = (item: BuildingPlacement): PreviewSourceState => {
  const meta = item.meta ?? {};
  const statusText = [
    meta.source_confidence,
    meta.cad_source_confidence,
    meta.classification_status,
    meta.engineering_status,
    meta.review_status,
    meta.handoff_status,
    meta.source,
    item.source,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  if (item.meta?.unsupported_entity_placeholder || statusText.includes("blocked")) return "blocked";
  if (statusText.includes("stale") || statusText.includes("dirty")) return "stale";
  if (statusText.includes("inferred") || statusText.includes("low") || item.source === "inferred") return "inferred";
  if (statusText.includes("import") || item.source === "detected_from_image") return "imported";
  const hasPathGeometry = hasExplicitFootprintGeometry(item);
  const sourceBackedRect =
    item.geometryType === "rect" &&
    (item.source === "user" ||
      item.source === "manual_drawn" ||
      item.source === "user_confirmed" ||
      statusText.includes("verified") ||
      statusText.includes("source-backed") ||
      statusText.includes("survey") ||
      statusText.includes("import"));
  if (!hasPathGeometry && item.geometryType === "rect" && item.type !== "site" && !sourceBackedRect) return "fallback";
  if (!hasPathGeometry && item.geometryType !== "rect" && item.type !== "site") return "fallback";
  return "verified";
};

export const sourceStateLabel = (state: PreviewSourceState) => {
  if (state === "verified") return "Source-backed geometry";
  if (state === "imported") return "Imported geometry - review required";
  if (state === "inferred") return "Inferred geometry - low confidence";
  if (state === "stale") return "Stale geometry - rerun affected systems";
  if (state === "blocked") return "Geometry needs review";
  return "Fallback geometry - bounds only";
};

export const geometryTruthLabel = (item: BuildingPlacement) => {
  const state = resolveSourceState(item);
  const entityType = String(item.meta?.cad_entity_type || item.geometryType || "");
  if (state === "fallback") return sourceStateLabel(state);
  if (item.geometryType === "polygon") return "True polygon footprint";
  if (item.geometryType === "polyline") return "True linework";
  if (item.geometryType === "point") return "Point / symbol";
  if (item.geometryType === "rect" || entityType === "rectangle") return "Draft rectangular footprint";
  return sourceStateLabel(state);
};

export const utilityStrokeColor = (item: BuildingPlacement) => {
  const text = `${item.type || ""} ${item.label || ""} ${item.meta?.system || ""} ${item.meta?.discipline || ""}`.toLowerCase();
  if (text.includes("water") || text.includes("hydrant")) return "#2563eb";
  if (text.includes("sanitary") || text.includes("manhole")) return "#15803d";
  if (text.includes("storm") || text.includes("drain") || text.includes("inlet") || text.includes("sewer")) return "#c2410c";
  if (text.includes("electric") || text.includes("power")) return "#ca8a04";
  if (text.includes("gas")) return "#dc2626";
  return "#64748b";
};

export const polygonCentroid = (points: Array<[number, number]>): [number, number] => {
  if (!points.length) return [0, 0];
  const sum = points.reduce(
    (acc, pt) => {
      acc.x += pt[0];
      acc.y += pt[1];
      return acc;
    },
    { x: 0, y: 0 },
  );
  return [sum.x / points.length, sum.y / points.length];
};

export const scalePolygonTowardCenter = (points: Array<[number, number]>, scale: number): Array<[number, number]> => {
  const [cx, cy] = polygonCentroid(points);
  return points.map(([x, y]) => [cx + (x - cx) * scale, cy + (y - cy) * scale]);
};

export const firstMetaNumber = (item: BuildingPlacement, keys: string[]): number | null => readMetaNumber(item.meta, keys);

export const supportsParkingModuleRendering = (item: BuildingPlacement) => {
  const params = (item.meta as { parkingParams?: ParkingParams } | undefined)?.parkingParams ?? {};
  const stallDepth = Number.isFinite(params.stallDepth) ? Number(params.stallDepth) : 18;
  const aisleWidth = Number.isFinite(params.aisleWidth) ? Number(params.aisleWidth) : 24;
  const stallWidth = Number.isFinite(params.stallWidth) ? Number(params.stallWidth) : 9;
  const loading = params.loading === "single" ? "single" : "double";
  const minDepth = stallDepth * (loading === "double" ? 2 : 1) + aisleWidth;
  const minWidth = Math.max(stallWidth * 2.5, 24);
  return item.type === "parking" && item.w >= minWidth && item.d >= minDepth * 0.82;
};

export const hasParkingGeometryEvidence = (item: BuildingPlacement) =>
  supportsParkingModuleRendering(item) &&
  Number.isFinite(item.w) &&
  Number.isFinite(item.d);

export const stableHash = (value: string) => {
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
};
