import type { BuildingPlacement } from "../types";

export type PreviewCanvasView = {
  scale: number;
  offsetX: number;
  offsetY: number;
};

export function buildBalancedPreviewCanvasView(
  rect: { width: number; height: number } | null | undefined,
  balancedScale: number,
): PreviewCanvasView {
  const offsetX = rect ? Math.max(24, rect.width * (1 - balancedScale) * 0.5) : 36;
  const offsetY = rect ? Math.max(22, rect.height * (1 - balancedScale) * 0.5) : 32;
  return { scale: balancedScale, offsetX, offsetY };
}

export function buildFocusedPreviewCanvasView(
  item: BuildingPlacement,
  lotWidth: number,
  lotHeight: number,
): PreviewCanvasView {
  const minX = item.x ?? 0;
  const minY = item.y ?? 0;
  const maxX = minX + Math.max(item.w, 1);
  const maxY = minY + Math.max(item.d, 1);
  const centerX = (minX + maxX) / 2 / Math.max(lotWidth, 1);
  const centerY = (minY + maxY) / 2 / Math.max(lotHeight, 1);
  const objectShare = Math.max(
    Math.max(item.w, 1) / Math.max(lotWidth, 1),
    Math.max(item.d, 1) / Math.max(lotHeight, 1),
  );
  const focusScale = Math.min(Math.max(1 / Math.max(objectShare, 0.42), 0.96), 1.35);
  return {
    scale: focusScale,
    offsetX: (0.5 - centerX) * 96,
    offsetY: (0.5 - centerY) * 96,
  };
}
