import type { BuildingPlacement } from "../types";
import { objectFootprints } from "./siteInterference";
import { culDeSacFrame } from "./parametricRoad";

export function reviewSheetGeometry(placements: BuildingPlacement[], lotWidth: number, lotHeight: number) {
  const invalidIds: string[] = [];
  const objects = placements.filter(item => item.placed !== false && !item.meta?.ui_hidden).flatMap(item => {
    if (![item.x ?? 0, item.y ?? 0, item.w, item.d, item.rotation ?? 0].every(Number.isFinite) || item.w <= 0 || item.d <= 0 ||
      (["polygon", "polyline"].includes(item.geometryType ?? "") && (!item.geometry || item.geometry.length < (item.geometryType === "polygon" ? 3 : 2))) ||
      (item.geometry && (!Array.isArray(item.geometry) || item.geometry.some(point => !Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))))) {
      invalidIds.push(item.id);
      return [];
    }
    const isPoint = item.geometryType === "point";
    const points = isPoint ? [item.geometry?.[0] ?? [item.x ?? 0, item.y ?? 0] as [number, number]] : item.geometryType === "polyline" ? item.geometry! : objectFootprints(item)[0];
    const frame = culDeSacFrame(item);
    const island = frame ? Array.from({ length: 96 }, (_, n) => frame.toWorld([frame.p.islandRadiusFt * Math.cos(n * Math.PI / 48), frame.p.islandRadiusFt * Math.sin(n * Math.PI / 48)])) : null;
    return [{ item, points, island, isPoint, isPolyline: item.geometryType === "polyline" }];
  });
  // Fit the entire actual layout, including out-of-site objects; never clamp a feature into the site.
  let minX = 0, minY = 0;
  let maxX = Number.isFinite(lotWidth) && lotWidth > 0 ? lotWidth : 0;
  let maxY = Number.isFinite(lotHeight) && lotHeight > 0 ? lotHeight : 0;
  for (const object of objects) for (const [x, y] of object.points) {
    minX = Math.min(minX, x); minY = Math.min(minY, y);
    maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
  }
  return { objects, invalidIds, bounds: { minX, minY, width: Math.max(1, maxX - minX), height: Math.max(1, maxY - minY) } };
}
