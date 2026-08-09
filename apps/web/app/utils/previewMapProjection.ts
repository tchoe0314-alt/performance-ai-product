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

export function measureMapFeetPerPixel(targetMap: mapboxgl.Map | null) {
  if (!targetMap) return null;
  const container = targetMap.getContainer();
  const width = Math.max(container.clientWidth, 1);
  const height = Math.max(container.clientHeight, 1);
  const sampleHalfWidthPx = Math.min(50, Math.max(1, width / 4));
  const centerX = width / 2;
  const centerY = height / 2;
  const west = targetMap.unproject([centerX - sampleHalfWidthPx, centerY]);
  const east = targetMap.unproject([centerX + sampleHalfWidthPx, centerY]);
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const lat1 = toRadians(west.lat);
  const lat2 = toRadians(east.lat);
  const deltaLat = lat2 - lat1;
  const deltaLng = toRadians(east.lng - west.lng);
  const sinLat = Math.sin(deltaLat / 2);
  const sinLng = Math.sin(deltaLng / 2);
  const haversine = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng;
  const earthRadiusMeters = 6_378_137;
  const distanceMeters = 2 * earthRadiusMeters * Math.asin(Math.min(1, Math.sqrt(haversine)));
  const feetPerPixel = (distanceMeters * 3.28084) / (sampleHalfWidthPx * 2);
  return Number.isFinite(feetPerPixel) && feetPerPixel > 0 ? feetPerPixel : null;
}

export function measureMapSiteFeetPerPixel(targetMap: mapboxgl.Map | null, mapAnchor: MapAnchor | null) {
  if (!targetMap || !mapAnchor) return null;
  const container = targetMap.getContainer();
  const width = Math.max(container.clientWidth, 1);
  const height = Math.max(container.clientHeight, 1);
  const sampleHalfWidthPx = Math.min(50, Math.max(1, width / 4));
  const centerX = width / 2;
  const centerY = height / 2;
  const west = targetMap.unproject([centerX - sampleHalfWidthPx, centerY]);
  const east = targetMap.unproject([centerX + sampleHalfWidthPx, centerY]);
  const westSite = mapLngLatToSite({ lat: west.lat, lng: west.lng }, mapAnchor);
  const eastSite = mapLngLatToSite({ lat: east.lat, lng: east.lng }, mapAnchor);
  if (!westSite || !eastSite) return null;
  const distanceFeet = Math.hypot(eastSite.x - westSite.x, eastSite.y - westSite.y);
  const feetPerPixel = distanceFeet / (sampleHalfWidthPx * 2);
  return Number.isFinite(feetPerPixel) && feetPerPixel > 0 ? feetPerPixel : null;
}

export function synchronizeMapViewport(targetMap: mapboxgl.Map | null) {
  if (!targetMap || typeof window === "undefined") return false;
  const container = targetMap.getContainer();
  const canvas = targetMap.getCanvas();
  const pixelRatio = Math.max(window.devicePixelRatio || 1, 1);
  const renderedWidth = canvas.width / pixelRatio;
  const renderedHeight = canvas.height / pixelRatio;
  const widthChanged = Math.abs(renderedWidth - container.clientWidth) > 1;
  const heightChanged = Math.abs(renderedHeight - container.clientHeight) > 1;
  if (!widthChanged && !heightChanged) return false;
  targetMap.resize();
  return true;
}
