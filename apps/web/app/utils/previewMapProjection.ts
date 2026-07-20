import type mapboxgl from "mapbox-gl";

import type { BuildingPlacement } from "../types";
import {
  mapLngLatToSite,
  siteRectToPercent,
  siteToMapLngLat,
  siteTupleToPercent,
  type MapAnchor,
  type SiteSize,
} from "./geometryTransforms";

export type PreviewMapAnchorInput = {
  geocode?: { lat?: number | null; lng?: number | null } | null;
  lotWidth: number;
  lotHeight: number;
  siteRotationDeg?: number | null;
};

export function buildPreviewMapAnchor({
  geocode,
  lotWidth,
  lotHeight,
  siteRotationDeg,
}: PreviewMapAnchorInput): MapAnchor | null {
  const geocodeLat = geocode?.lat;
  const geocodeLng = geocode?.lng;
  return geocodeLat && geocodeLng && lotWidth > 0 && lotHeight > 0
    ? {
        lat: geocodeLat,
        lng: geocodeLng,
        siteWidth: lotWidth,
        siteHeight: lotHeight,
        rotationDeg: siteRotationDeg ?? 0,
      }
    : null;
}

export function sitePointToPreviewPercent({
  point,
  targetMap,
  showMap,
  mapAnchor,
  currentSiteSize,
}: {
  point: [number, number];
  targetMap: mapboxgl.Map | null;
  showMap: boolean;
  mapAnchor: MapAnchor | null;
  currentSiteSize: SiteSize;
}): [number, number] {
  if (showMap && mapAnchor && targetMap) {
    const container = targetMap.getContainer();
    const containerWidth = Math.max(container.clientWidth, 1);
    const containerHeight = Math.max(container.clientHeight, 1);
    const lngLat = siteToMapLngLat({ x: point[0], y: point[1] }, mapAnchor);
    if (!lngLat) return siteTupleToPercent(point, currentSiteSize);
    const projected = targetMap.project(lngLat);
    return [(projected.x / containerWidth) * 100, (projected.y / containerHeight) * 100];
  }
  return siteTupleToPercent(point, currentSiteSize);
}

export function siteRectPercent(item: BuildingPlacement, currentSiteSize: SiteSize) {
  const rotated = (item.rotation ?? 0) % 180 !== 0;
  const displayW = rotated ? item.d : item.w;
  const displayD = rotated ? item.w : item.d;
  return siteRectToPercent(
    {
      x: item.x ?? 0,
      y: item.y ?? 0,
      width: displayW,
      height: displayD,
    },
    currentSiteSize,
  );
}

export function mapAnchoredRectPercent({
  item,
  targetMap,
  showMap,
  mapAnchor,
  currentSiteSize,
}: {
  item: BuildingPlacement;
  targetMap: mapboxgl.Map | null;
  showMap: boolean;
  mapAnchor: MapAnchor | null;
  currentSiteSize: SiteSize;
}) {
  const fallback = siteRectPercent(item, currentSiteSize);
  if (!showMap || !targetMap || !mapAnchor) return fallback;
  const container = targetMap.getContainer();
  const containerWidth = Math.max(container.clientWidth, 1);
  const containerHeight = Math.max(container.clientHeight, 1);
  const sitePoints =
    (item.geometryType === "polygon" || item.geometryType === "rect" || item.geometryType === "polyline") &&
    Array.isArray(item.geometry) &&
    item.geometry.length
      ? item.geometry
      : (() => {
          const x = item.x ?? 0;
          const y = item.y ?? 0;
          const rotated = (item.rotation ?? 0) % 180 !== 0;
          const w = rotated ? item.d : item.w;
          const d = rotated ? item.w : item.d;
          return [
            [x, y],
            [x + w, y],
            [x + w, y + d],
            [x, y + d],
          ] as Array<[number, number]>;
        })();
  const projected = sitePoints
    .map(([x, y]) => siteToMapLngLat({ x, y }, mapAnchor))
    .filter(Boolean)
    .map((coord) => targetMap.project(coord as [number, number]));
  if (!projected.length) return fallback;
  const xs = projected.map((pt) => pt.x);
  const ys = projected.map((pt) => pt.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return {
    left: (minX / containerWidth) * 100,
    top: (minY / containerHeight) * 100,
    width: (Math.max(maxX - minX, 8) / containerWidth) * 100,
    height: (Math.max(maxY - minY, 8) / containerHeight) * 100,
  };
}

export function mapLngLatToSitePoint(lat: number, lng: number, mapAnchor: MapAnchor | null) {
  return mapAnchor ? mapLngLatToSite({ lat, lng }, mapAnchor) : null;
}
