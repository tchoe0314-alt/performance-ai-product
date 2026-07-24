import type { BuildingPlacement, Preview3DItem } from "../types";

export type PreviewSemanticLayer =
  | "lots"
  | "roads"
  | "buildings"
  | "parking"
  | "landscape"
  | "utilities"
  | "water"
  | "other";

export const PREVIEW_SEMANTIC_LAYER_LABELS: Record<PreviewSemanticLayer, string> = {
  lots: "Lots",
  roads: "Roads",
  buildings: "Buildings",
  parking: "Parking",
  landscape: "Landscape",
  utilities: "Utilities",
  water: "Water",
  other: "Other",
};

export const PRIMARY_PREVIEW_SEMANTIC_LAYERS: PreviewSemanticLayer[] = [
  "lots",
  "roads",
  "buildings",
  "parking",
  "landscape",
  "utilities",
];

export function semanticLayerForPlacement(item: BuildingPlacement): PreviewSemanticLayer {
  const type = String(item.type || "").toLowerCase();
  const label = String(item.label || "").toLowerCase();
  const network = String(item.meta?.network || "").toLowerCase();
  if (type === "site") return "other";
  if (type === "lot_block" || type.includes("parcel") || label.includes("parcel")) return "lots";
  if (type === "road" || type === "driveway" || label.includes("road") || label.includes("boulevard") || label.includes("drive")) return "roads";
  if (type.includes("building") || type === "pad" || label.includes("hall") || label.includes("library")) return "buildings";
  if (type === "parking" || label.includes("parking")) return "parking";
  if (type === "open_space" || type === "landscape" || type === "amenity" || label.includes("park") || label.includes("tree") || label.includes("plaza")) return "landscape";
  if (
    type === "utility_corridor" ||
    type === "hydrant" ||
    type === "inlet" ||
    type === "outfall" ||
    type === "manhole" ||
    network ||
    label.includes("water") ||
    label.includes("sanitary") ||
    label.includes("storm")
  ) {
    return "utilities";
  }
  if (type === "basin" || type === "pond" || type === "pool" || label.includes("basin") || label.includes("pond")) return "water";
  return "other";
}

export function semanticLayerFor3DItem(item: Preview3DItem): PreviewSemanticLayer {
  const layer = String(item.layer || "").toUpperCase();
  const label = String(item.label || "").toLowerCase();
  if (layer === "ROAD" || label.includes("road") || label.includes("boulevard")) return "roads";
  if (layer === "BUILDING" || layer === "STRUCTURE" || label.includes("hall") || label.includes("library")) return "buildings";
  if (layer === "PARKING" || label.includes("parking")) return "parking";
  if (layer === "LANDSCAPE" || label.includes("tree") || label.includes("park") || label.includes("plaza")) return "landscape";
  if (layer === "UTILITY" || label.includes("water") || label.includes("sanitary") || label.includes("storm")) return "utilities";
  if (layer === "DRAINAGE" || label.includes("basin") || label.includes("pond")) return "water";
  if (layer === "CONSTRAINT" || label.includes("parcel") || label.includes("lot")) return "lots";
  return "other";
}

export function isPreviewSemanticLayerVisible(
  layer: PreviewSemanticLayer,
  visibility: Partial<Record<PreviewSemanticLayer, boolean>>,
) {
  return visibility[layer] !== false;
}
