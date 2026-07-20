import type { BuildingPlacement } from "../types";
import { resolveSourceState, sourceStateLabel } from "./previewGeometryTruth";

export type PreviewObjectAction = "rename" | "style" | "type" | "hide" | "delete" | "focus";

export function clampValue(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function snapPreviewValue(value: number, step: number) {
  if (!step) return value;
  return Math.round(value / step) * step;
}

export function getPreviewEditCapabilities(item: BuildingPlacement, siteLocked?: boolean) {
  const type = item.type ?? "building";
  const editableTypes = new Set([
    "site",
    "building",
    "retail_building",
    "multifamily_building",
    "industrial_building",
    "office_building",
    "pad",
    "pool",
    "basin",
    "entrance",
    "driveway",
    "amenity",
    "open_space",
    "no_build_zone",
    "setback_zone",
    "parking",
    "road",
    "sidewalk",
    "custom",
  ]);
  const resizableTypes = new Set([
    "site",
    "building",
    "retail_building",
    "multifamily_building",
    "industrial_building",
    "office_building",
    "pad",
    "pool",
    "basin",
    "amenity",
    "open_space",
    "no_build_zone",
    "setback_zone",
    "parking",
    "driveway",
    "custom",
  ]);
  const rotatableTypes = new Set([
    "site",
    "building",
    "retail_building",
    "multifamily_building",
    "industrial_building",
    "office_building",
    "pad",
    "pool",
    "basin",
    "amenity",
    "open_space",
    "parking",
    "driveway",
    "custom",
  ]);
  const deletableTypes = new Set([...editableTypes].filter((t) => t !== "site"));
  const isSite = type === "site";
  const effectiveLocked = isSite ? Boolean(siteLocked) : item.locked;
  const movable = editableTypes.has(type) && !effectiveLocked;
  const resizable = resizableTypes.has(type) && !effectiveLocked;
  const rotatable = rotatableTypes.has(type) && !effectiveLocked;
  const deletable = deletableTypes.has(type) && !effectiveLocked;
  return { movable, resizable, rotatable, deletable };
}

export function getPreviewObjectGeometryPoints(item: BuildingPlacement): Array<[number, number]> {
  if (Array.isArray(item.geometry) && item.geometry.length) {
    return (item.geometry as Array<[number, number]>).map((pt) => [pt[0], pt[1]]);
  }
  const x = item.x ?? 0;
  const y = item.y ?? 0;
  if (item.geometryType === "point") return [[x + item.w / 2, y + item.d / 2]];
  return [
    [x, y],
    [x + item.w, y],
    [x + item.w, y + item.d],
    [x, y + item.d],
  ];
}

export function getPreviewCadLayer(item: BuildingPlacement) {
  return String(item.meta?.cad_layer || item.meta?.layer || (item.type === "site" ? "C-SITE" : "C-DRAFT")).toUpperCase();
}

export function getPreviewObjectDimensionsLabel(item: BuildingPlacement) {
  if (item.geometryType === "point") return "Point object";
  const width = Number.isFinite(item.w) ? item.w.toFixed(1) : "--";
  const depth = Number.isFinite(item.d) ? item.d.toFixed(1) : "--";
  return `${width} ft x ${depth} ft`;
}

export function getPreviewObjectSourceLabel(item: BuildingPlacement, isCadSourcePreview: boolean) {
  if (isCadSourcePreview) return "Source-only preview";
  if (item.generated || item.source === "generated") return "Generated";
  if (item.source === "manual_drawn") return "Manual draft";
  if (item.source === "detected_from_image" || item.source === "detected_from_gis") return "Detected source";
  if (item.source === "inferred") return "Inferred";
  return item.source ? item.source.replace(/_/g, " ") : "User";
}

export function getPreviewObjectStatusLabel(item: BuildingPlacement, siteLocked?: boolean) {
  const sourceState = resolveSourceState(item);
  if (item.type === "site") return siteLocked ? "Site boundary locked" : "Site boundary draft";
  if (item.locked) return "Locked";
  if (item.meta?.ui_hidden) return "Hidden";
  if (!item.placed) return "Unplaced";
  if (sourceState !== "verified") return sourceStateLabel(sourceState);
  return "Visible draft/review object";
}

export function getPreviewObjectActionBlocker({
  item,
  action,
  isEditableSource,
  isCanonicalBuilding,
}: {
  item: BuildingPlacement | null;
  action: PreviewObjectAction;
  isEditableSource: boolean;
  isCanonicalBuilding: boolean;
}) {
  if (!item) return `${action.toUpperCase()} blocked: select an object first.`;
  if (action === "focus") return null;
  if (item.type === "site") return `${action.toUpperCase()} blocked: site boundary is controlled from site setup/change-site tools.`;
  if (!isEditableSource) return `${action.toUpperCase()} blocked: ${item.label || item.id} is source-only preview geometry.`;
  if (item.locked) return `${action.toUpperCase()} blocked: ${item.label || item.id} is locked. Unlock or use a draft copy before editing.`;
  if (action === "delete" && !isCanonicalBuilding) {
    return "DELETE blocked: detected/source suggestions can be hidden or reviewed, but not deleted from the canonical canvas here.";
  }
  return null;
}
