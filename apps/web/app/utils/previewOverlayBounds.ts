import type { BuildingPlacement } from "../types";

export type PreviewOverlayBounds = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export const HIGH_QUALITY_DRAWING_VIEWPORT = {
  left: 1.2,
  top: 1.2,
  width: 82.6,
  height: 97.6,
} as const;

export function buildPreviewOverlayBounds(
  previewContainerBounds: PreviewOverlayBounds | null,
  siteSize?: { width: number; height: number } | null,
): PreviewOverlayBounds | null {
  if (!previewContainerBounds) return null;
  if (
    siteSize &&
    Number.isFinite(siteSize.width) &&
    Number.isFinite(siteSize.height) &&
    siteSize.width > 0 &&
    siteSize.height > 0
  ) {
    const horizontalPadding = Math.min(72, Math.max(28, previewContainerBounds.width * 0.055));
    const topPadding = Math.min(40, Math.max(24, previewContainerBounds.height * 0.045));
    const bottomPadding = Math.min(108, Math.max(84, previewContainerBounds.height * 0.14));
    const availableWidth = Math.max(1, previewContainerBounds.width - horizontalPadding * 2);
    const availableHeight = Math.max(1, previewContainerBounds.height - topPadding - bottomPadding);
    const siteAspect = siteSize.width / siteSize.height;
    const availableAspect = availableWidth / availableHeight;
    const width = availableAspect > siteAspect ? availableHeight * siteAspect : availableWidth;
    const height = availableAspect > siteAspect ? availableHeight : availableWidth / siteAspect;
    return {
      left: (previewContainerBounds.width - width) / 2,
      top: topPadding + (availableHeight - height) / 2,
      width,
      height,
    };
  }
  return {
    left: 0,
    top: 0,
    width: previewContainerBounds.width,
    height: previewContainerBounds.height,
  };
}

export function buildPreviewInteractionBounds(
  overlayBounds: PreviewOverlayBounds | null,
  viewportPercent: PreviewOverlayBounds | null,
): PreviewOverlayBounds | null {
  if (!overlayBounds || !viewportPercent) return overlayBounds;
  return {
    left: overlayBounds.left + (overlayBounds.width * viewportPercent.left) / 100,
    top: overlayBounds.top + (overlayBounds.height * viewportPercent.top) / 100,
    width: (overlayBounds.width * viewportPercent.width) / 100,
    height: (overlayBounds.height * viewportPercent.height) / 100,
  };
}

export function countRenderedCanonicalPreviewObjects(buildingPlacements: BuildingPlacement[]) {
  return buildingPlacements.filter(
    (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
  ).length;
}
