import type { BuildingPlacement } from "../types";
import {
  validateTopology,
  type CadSegment2D,
} from "./cadGeometryKernel";

export type PreviewCadMetrics = {
  segmentCount: number;
  totalLength: number;
  firstLength: number;
  firstAngle: number;
  layer: string;
};

type GeometryPointResolver = (item: BuildingPlacement) => Array<[number, number]>;
type LayerResolver = (item: BuildingPlacement) => string;

export function buildVisibleCadObjects({
  buildingPlacements,
  cadEntityPreviewObjects,
  hiddenCadLayers,
  getCadLayer,
}: {
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewObjects: BuildingPlacement[];
  hiddenCadLayers: string[];
  getCadLayer: LayerResolver;
}): BuildingPlacement[] {
  return [...buildingPlacements, ...cadEntityPreviewObjects].filter(
    (item) => !hiddenCadLayers.includes(getCadLayer(item)) && !item.meta?.ui_hidden,
  );
}

export function buildCanvasCompositionSignature(visibleCadObjects: BuildingPlacement[]): string {
  return visibleCadObjects
    .filter((item) => item.type !== "site" && item.placed && !item.meta?.ui_hidden)
    .map((item) => {
      const geometryLength = Array.isArray(item.geometry) ? item.geometry.length : 0;
      return `${item.id}:${item.type}:${Math.round(item.x ?? 0)},${Math.round(item.y ?? 0)},${Math.round(item.w ?? 0)},${Math.round(item.d ?? 0)}:${geometryLength}`;
    })
    .sort()
    .join("|");
}

export function buildCadSegments({
  visibleCadObjects,
  suggestedPlacements,
  getObjectGeometryPoints,
}: {
  visibleCadObjects: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
  getObjectGeometryPoints: GeometryPointResolver;
}): CadSegment2D[] {
  const segments: CadSegment2D[] = [];
  [...visibleCadObjects, ...suggestedPlacements].forEach((item) => {
    const points = getObjectGeometryPoints(item);
    if (points.length < 2) return;
    points.forEach((pt, idx) => {
      const isLast = idx === points.length - 1;
      if (isLast && item.geometryType === "polyline") return;
      const next = isLast ? points[0] : points[idx + 1];
      segments.push({
        a: { x: pt[0], y: pt[1] },
        b: { x: next[0], y: next[1] },
        objectId: item.id,
        segmentIndex: idx,
        closed: item.geometryType !== "polyline",
      });
    });
  });
  return segments;
}

export function buildSelectedCadMetrics({
  selectedCadObject,
  getObjectGeometryPoints,
  getCadLayer,
}: {
  selectedCadObject: BuildingPlacement | null;
  getObjectGeometryPoints: GeometryPointResolver;
  getCadLayer: LayerResolver;
}): PreviewCadMetrics | null {
  const points = selectedCadObject ? getObjectGeometryPoints(selectedCadObject) : [];
  if (!selectedCadObject || points.length < 2) return null;
  const segments = points.map((point, index) => {
    if (index === points.length - 1 && selectedCadObject.geometryType === "polyline") return null;
    const next = index === points.length - 1 ? points[0] : points[index + 1];
    return {
      length: Math.hypot(next[0] - point[0], next[1] - point[1]),
      angle: ((Math.atan2(next[1] - point[1], next[0] - point[0]) * 180) / Math.PI + 360) % 360,
    };
  }).filter(Boolean) as Array<{ length: number; angle: number }>;
  return {
    segmentCount: segments.length,
    totalLength: segments.reduce((sum, segment) => sum + segment.length, 0),
    firstLength: segments[0]?.length ?? 0,
    firstAngle: segments[0]?.angle ?? 0,
    layer: getCadLayer(selectedCadObject),
  };
}

export function buildPreviewTopologyIssues(visibleCadObjects: BuildingPlacement[]): ReturnType<typeof validateTopology> {
  return validateTopology(visibleCadObjects.filter((item) => item.type !== "site").map((item) => ({
    id: item.id,
    type: item.type,
    geometryType: item.geometryType,
    geometry: Array.isArray(item.geometry) ? (item.geometry as Array<[number, number]>) : undefined,
    x: item.x,
    y: item.y,
    w: item.w,
    d: item.d,
  }))).slice(0, 8);
}
