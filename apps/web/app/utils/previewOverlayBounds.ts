import type { BuildingPlacement } from "../types";

export type PreviewOverlayBounds = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export function buildPreviewOverlayBounds(
  previewContainerBounds: PreviewOverlayBounds | null,
): PreviewOverlayBounds | null {
  if (!previewContainerBounds) return null;
  return {
    left: 0,
    top: 0,
    width: previewContainerBounds.width,
    height: previewContainerBounds.height,
  };
}

export function countRenderedCanonicalPreviewObjects(buildingPlacements: BuildingPlacement[]) {
  return buildingPlacements.filter(
    (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
  ).length;
}
