import type { BuildingPlacement, Preview3DItem } from "../types";
import { semanticLayerForPlacement } from "./previewSemanticLayers";

export type DetectedExistingSubLayer = "buildings" | "roads" | "parcels" | "other";

export type PreviewSourceLayerVisibility = {
  detectedExisting: boolean;
  proposedDesign: boolean;
  detectedBuildings: boolean;
  detectedRoads: boolean;
  detectedParcels: boolean;
  detectedOther: boolean;
};

export const DEFAULT_PREVIEW_SOURCE_LAYER_VISIBILITY: PreviewSourceLayerVisibility = {
  detectedExisting: true,
  proposedDesign: true,
  detectedBuildings: true,
  detectedRoads: true,
  detectedParcels: true,
  detectedOther: true,
};

const detectedSourceTokens = (item: Pick<BuildingPlacement, "source" | "meta">) => {
  const meta = item.meta ?? {};
  return [
    item.source,
    meta.source,
    meta.source_type,
    meta.original_source,
    meta.source_kind,
    meta.creation_method,
    meta.classification_status,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
};

export function isDetectedExistingPlacement(item: Pick<BuildingPlacement, "source" | "meta">) {
  const source = String(item.source || "").toLowerCase();
  if (["detected_from_gis", "detected_from_image", "inferred"].includes(source)) return true;
  if (item.meta?.accepted_source_candidate === true || item.meta?.source_candidate_id) return true;
  const tokens = detectedSourceTokens(item);
  return (
    tokens.includes("accepted_detected_candidate") ||
    tokens.includes("image_detected_candidate") ||
    tokens.includes("imagery_detected") ||
    tokens.includes("detected_from_gis") ||
    tokens.includes("detected_from_image")
  );
}
export function detectedExistingSubLayer(item: BuildingPlacement): DetectedExistingSubLayer {
  const semanticLayer = semanticLayerForPlacement(item);
  if (semanticLayer === "buildings") return "buildings";
  if (semanticLayer === "roads") return "roads";
  if (semanticLayer === "lots") return "parcels";
  return "other";
}

export function isDetectedExistingPlacementVisible(
  item: BuildingPlacement,
  visibility: PreviewSourceLayerVisibility,
) {
  if (!visibility.detectedExisting) return false;
  const subLayer = detectedExistingSubLayer(item);
  if (subLayer === "buildings") return visibility.detectedBuildings;
  if (subLayer === "roads") return visibility.detectedRoads;
  if (subLayer === "parcels") return visibility.detectedParcels;
  return visibility.detectedOther;
}

export function isPreview3DItemDetectedExisting(item: Preview3DItem) {
  const meta = item.meta ?? {};
  const source = [
    item.source,
    meta.source,
    meta.source_type,
    meta.original_source,
    meta.source_kind,
    meta.creation_method,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return (
    source.includes("detected_from_gis") ||
    source.includes("detected_from_image") ||
    source.includes("image_detected_candidate") ||
    source.includes("accepted_detected_candidate") ||
    meta.accepted_source_candidate === true ||
    Boolean(meta.source_candidate_id)
  );
}
