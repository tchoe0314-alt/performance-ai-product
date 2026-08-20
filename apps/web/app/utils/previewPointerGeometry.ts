import type { DrawMode } from "./cadToolTypes";
import {
  screenToSitePoint,
  type CanvasCamera,
  type Rect2D,
} from "./geometryTransforms";

export type PreviewPointerSitePoint = {
  x: number;
  y: number;
  relX: number;
  relY: number;
};

export function normalizePreviewPointerSitePoint({
  rawSitePoint,
  drawMode,
  drawingLotWidth,
  drawingLotHeight,
  lotWidth,
  lotHeight,
}: {
  rawSitePoint: { x: number; y: number };
  drawMode: DrawMode;
  drawingLotWidth: number;
  drawingLotHeight: number;
  lotWidth: number;
  lotHeight: number;
}): PreviewPointerSitePoint | null {
  const effectiveLotWidth = drawMode === "site" ? drawingLotWidth : lotWidth;
  const effectiveLotHeight = drawMode === "site" ? drawingLotHeight : lotHeight;
  if (!effectiveLotWidth || !effectiveLotHeight) return null;
  const relX = rawSitePoint.x / Math.max(effectiveLotWidth, 1);
  const relY = rawSitePoint.y / Math.max(effectiveLotHeight, 1);
  if (!Number.isFinite(relX) || !Number.isFinite(relY)) return null;
  // A pointer outside the rendered site is not a site point. Clamping it to an
  // edge makes the cursor and committed geometry visibly disagree.
  if (relX < 0 || relX > 1 || relY < 0 || relY > 1) return null;
  const clampedRelX = Math.min(Math.max(relX, 0), 1);
  const clampedRelY = Math.min(Math.max(relY, 0), 1);
  const clampedX = Math.min(Math.max(rawSitePoint.x, 0), effectiveLotWidth);
  const clampedY = Math.min(Math.max(rawSitePoint.y, 0), effectiveLotHeight);
  const snapStep = drawMode === "point" ? 1 : drawMode === "site" ? 5 : 2;
  return {
    x: Math.round(clampedX / snapStep) * snapStep,
    y: Math.round(clampedY / snapStep) * snapStep,
    relX: clampedRelX,
    relY: clampedRelY,
  };
}

export function resolvePreviewPointerSitePoint({
  clientX,
  clientY,
  containerRect,
  bounds,
  drawMode,
  drawingLotWidth,
  drawingLotHeight,
  lotWidth,
  lotHeight,
  canvasView,
}: {
  clientX: number;
  clientY: number;
  containerRect: Pick<DOMRect, "left" | "top">;
  bounds: Rect2D | null;
  drawMode: DrawMode;
  drawingLotWidth: number;
  drawingLotHeight: number;
  lotWidth: number;
  lotHeight: number;
  canvasView: CanvasCamera;
}): PreviewPointerSitePoint | null {
  const effectiveLotWidth = drawMode === "site" ? drawingLotWidth : lotWidth;
  const effectiveLotHeight = drawMode === "site" ? drawingLotHeight : lotHeight;
  if (!bounds || !effectiveLotWidth || !effectiveLotHeight) return null;
  const rawSitePoint = screenToSitePoint(
    { x: clientX, y: clientY },
    { left: containerRect.left, top: containerRect.top },
    bounds,
    { width: effectiveLotWidth, height: effectiveLotHeight },
    canvasView,
  );
  return normalizePreviewPointerSitePoint({
    rawSitePoint,
    drawMode,
    drawingLotWidth,
    drawingLotHeight,
    lotWidth,
    lotHeight,
  });
}
