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

export function buildDrawToolDetail(drawMode: DrawMode, draftPointCount: number) {
  if (drawMode === "site") return "Pick three or more boundary points, then Finish.";
  if (drawMode === "polyline") return "Pick two or more vertices, then Finish.";
  if (drawMode === "polygon") return "Pick three or more area vertices, then Finish.";
  if (drawMode === "rect") {
    return draftPointCount ? "Pick the opposite box corner." : "Pick the first box corner.";
  }
  if (drawMode === "point") return "Click once to place a draft point.";
  if (drawMode === "pan") return "Drag the canvas.";
  return "Click an object or use Object Manager.";
}

export function buildDraftPrecisionReadout({
  cursorPoint,
  draftPoints,
  draftPreviewPoint,
  drawMode,
  finishDraftMinPoints,
}: {
  cursorPoint: DraftPoint | null;
  draftPoints: DraftPoint[];
  draftPreviewPoint: DraftPoint | null;
  drawMode: DrawMode;
  finishDraftMinPoints: number;
}) {
  if (drawMode === "select" || drawMode === "pan") return null;
  const points =
    draftPreviewPoint && drawMode !== "point"
      ? [...draftPoints, draftPreviewPoint]
      : draftPoints;
  const currentPoint =
    draftPreviewPoint ??
    (draftPoints.length ? draftPoints[draftPoints.length - 1] : cursorPoint);
  const segments = points.slice(1).map((point, index) => {
    const previous = points[index];
    const dx = point[0] - previous[0];
    const dy = point[1] - previous[1];
    return {
      length: Math.hypot(dx, dy),
      angle: ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360,
    };
  });
  const lastSegment = segments.at(-1) ?? null;
  const totalLength = segments.reduce((sum, segment) => sum + segment.length, 0);
  const polygonArea =
    (drawMode === "polygon" || drawMode === "site") && points.length >= 3
      ? Math.abs(
          points.reduce((sum, point, index) => {
            const next = points[(index + 1) % points.length];
            return sum + point[0] * next[1] - next[0] * point[1];
          }, 0) / 2,
        )
      : null;
  return {
    currentPoint,
    lastSegment,
    totalLength,
    polygonArea,
    pointCount: draftPoints.length,
    finishReady:
      drawMode === "point" ||
      drawMode === "rect" ||
      draftPoints.length >= finishDraftMinPoints,
  };
}

export function buildDraftGeometryViewModel({
  cursorPoint,
  draftPoints,
  draftPreviewPoint,
  drawMode,
  finishPreviewPoint,
}: {
  cursorPoint: DraftPoint | null;
  draftPoints: DraftPoint[];
  draftPreviewPoint: DraftPoint | null;
  drawMode: DrawMode;
  finishPreviewPoint: DraftPoint | null;
}) {
  const draftPointCount = draftPoints.length;
  const finishDraftMinPoints = getDraftGeometryMinPointCount(drawMode);
  const finishDraftEffectivePointCount = getDraftGeometryEffectivePointCount(
    drawMode,
    draftPoints,
    finishPreviewPoint,
  );
  const canFinishDraftGeometry =
    drawMode !== "select" &&
    drawMode !== "pan" &&
    drawMode !== "point" &&
    finishDraftEffectivePointCount >= finishDraftMinPoints;
  const finishDraftBlockedReason =
    drawMode !== "select" &&
    drawMode !== "pan" &&
    drawMode !== "point" &&
    finishDraftEffectivePointCount < finishDraftMinPoints
      ? buildDraftGeometryFinishBlockedReason(drawMode)
      : null;
  return {
    activeDrawToolDetail: buildDrawToolDetail(drawMode, draftPointCount),
    activeDrawToolLabel: buildDrawToolLabel(drawMode),
    canFinishDraftGeometry,
    draftPointCount,
    draftPrecisionReadout: buildDraftPrecisionReadout({
      cursorPoint,
      draftPoints,
      draftPreviewPoint,
      drawMode,
      finishDraftMinPoints,
    }),
    finishDraftBlockedReason,
    finishDraftEffectivePointCount,
    finishDraftMinPoints,
  };
}
