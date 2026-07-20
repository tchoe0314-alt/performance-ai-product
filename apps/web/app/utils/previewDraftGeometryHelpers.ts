import type { DrawMode } from "./cadToolTypes";

export type DraftPoint = [number, number];

export function getDraftGeometryMinPointCount(drawMode: DrawMode) {
  return drawMode === "site" || drawMode === "polygon" ? 3 : 2;
}

export function resolveDraftGeometryEffectivePoints(
  drawMode: DrawMode,
  draftPoints: DraftPoint[],
  previewPoint: DraftPoint | null,
) {
  return drawMode === "rect" && draftPoints.length === 1 && previewPoint
    ? [draftPoints[0], previewPoint]
    : draftPoints;
}

export function getDraftGeometryEffectivePointCount(
  drawMode: DrawMode,
  draftPoints: DraftPoint[],
  previewPoint: DraftPoint | null,
) {
  if (drawMode === "rect" && draftPoints.length === 1 && previewPoint) return 2;
  if (
    (drawMode === "site" || drawMode === "polygon") &&
    draftPoints.length >= 2 &&
    previewPoint &&
    (draftPoints[draftPoints.length - 1][0] !== previewPoint[0] ||
      draftPoints[draftPoints.length - 1][1] !== previewPoint[1])
  ) {
    return draftPoints.length + 1;
  }
  return draftPoints.length;
}

export function buildDraftGeometryFinishBlockedMessage(drawMode: DrawMode, selectedPointCount: number) {
  if (drawMode === "site") {
    return `FINISH blocked: site boundary needs at least three points; ${selectedPointCount} selected.`;
  }
  if (drawMode === "polygon") {
    return `FINISH blocked: Add Area needs at least three points; ${selectedPointCount} selected.`;
  }
  if (drawMode === "rect") {
    return `FINISH blocked: Add Box needs two opposite corners; ${selectedPointCount} selected.`;
  }
  return `FINISH blocked: Add Line needs at least two points; ${selectedPointCount} selected.`;
}

export function buildDraftGeometryFinishBlockedReason(drawMode: DrawMode) {
  if (drawMode === "site") return "Draw at least three boundary points before Finish.";
  if (drawMode === "polygon") return "Draw at least three area points before Finish.";
  return "Draw at least two line points before Finish.";
}

export function buildDrawToolLabel(mode: DrawMode) {
  if (mode === "site") return "Draw Site Boundary";
  if (mode === "polyline") return "Add Line";
  if (mode === "polygon") return "Add Area";
  if (mode === "rect") return "Add Box";
  if (mode === "point") return "Add Point";
  if (mode === "pan") return "Pan";
  return "Select";
}
