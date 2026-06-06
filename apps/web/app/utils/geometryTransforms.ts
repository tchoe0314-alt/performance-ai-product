export type Point2D = { x: number; y: number };
export type SitePointTuple = [number, number];

export type Rect2D = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type SiteSize = {
  width: number;
  height: number;
};

export type CanvasCamera = {
  scale: number;
  offsetX: number;
  offsetY: number;
};

export type MapAnchor = {
  lat: number;
  lng: number;
  siteWidth: number;
  siteHeight: number;
  rotationDeg?: number | null;
};

export type CoordinateMode = "map_anchored" | "site_local";

const FEET_PER_METER = 3.28084;
const METERS_PER_FOOT = 0.3048;
const METERS_PER_DEGREE_LATITUDE = 111_320;

export function resolveCoordinateMode(anchor?: Pick<MapAnchor, "lat" | "lng"> | null): CoordinateMode {
  return anchor && Number.isFinite(anchor.lat) && Number.isFinite(anchor.lng)
    ? "map_anchored"
    : "site_local";
}

export function coordinateModeLabel(mode: CoordinateMode) {
  return mode === "map_anchored" ? "Map anchored" : "Local site coordinates";
}

export function clampPointToSite(point: Point2D, site: SiteSize): Point2D {
  return {
    x: Math.min(Math.max(point.x, 0), Math.max(site.width, 0)),
    y: Math.min(Math.max(point.y, 0), Math.max(site.height, 0)),
  };
}

export function screenToViewportPoint(
  client: Point2D,
  containerBounds: Pick<Rect2D, "left" | "top">,
  viewportBounds: Rect2D,
  camera: CanvasCamera,
): Point2D {
  const localX = client.x - containerBounds.left - viewportBounds.left;
  const localY = client.y - containerBounds.top - viewportBounds.top;
  const scale = Math.max(camera.scale, 0.1);
  return {
    x: (localX - camera.offsetX) / scale,
    y: (localY - camera.offsetY) / scale,
  };
}

export function viewportToSitePoint(point: Point2D, viewportBounds: Pick<Rect2D, "width" | "height">, site: SiteSize): Point2D {
  return {
    x: (point.x / Math.max(viewportBounds.width, 1)) * site.width,
    y: (point.y / Math.max(viewportBounds.height, 1)) * site.height,
  };
}

export function siteToViewportPoint(point: Point2D, viewportBounds: Pick<Rect2D, "width" | "height">, site: SiteSize): Point2D {
  return {
    x: (point.x / Math.max(site.width, 1)) * viewportBounds.width,
    y: (point.y / Math.max(site.height, 1)) * viewportBounds.height,
  };
}

export function viewportToScreenPoint(
  point: Point2D,
  containerBounds: Pick<Rect2D, "left" | "top">,
  viewportBounds: Rect2D,
  camera: CanvasCamera,
): Point2D {
  return {
    x: containerBounds.left + viewportBounds.left + camera.offsetX + point.x * camera.scale,
    y: containerBounds.top + viewportBounds.top + camera.offsetY + point.y * camera.scale,
  };
}

export function siteToScreenPoint(
  point: Point2D,
  containerBounds: Pick<Rect2D, "left" | "top">,
  viewportBounds: Rect2D,
  site: SiteSize,
  camera: CanvasCamera,
): Point2D {
  return viewportToScreenPoint(siteToViewportPoint(point, viewportBounds, site), containerBounds, viewportBounds, camera);
}

export function screenToSitePoint(
  client: Point2D,
  containerBounds: Pick<Rect2D, "left" | "top">,
  viewportBounds: Rect2D,
  site: SiteSize,
  camera: CanvasCamera,
): Point2D {
  return viewportToSitePoint(
    screenToViewportPoint(client, containerBounds, viewportBounds, camera),
    viewportBounds,
    site,
  );
}

export function siteToRelativePoint(point: Point2D, site: SiteSize): Point2D {
  return {
    x: point.x / Math.max(site.width, 1),
    y: point.y / Math.max(site.height, 1),
  };
}

export function siteRectToPercent(
  rect: { x: number; y: number; width: number; height: number },
  site: SiteSize,
) {
  return {
    left: (rect.x / Math.max(site.width, 1)) * 100,
    top: (rect.y / Math.max(site.height, 1)) * 100,
    width: (rect.width / Math.max(site.width, 1)) * 100,
    height: (rect.height / Math.max(site.height, 1)) * 100,
  };
}

export function siteTupleToPercent(point: SitePointTuple, site: SiteSize): SitePointTuple {
  return [
    (point[0] / Math.max(site.width, 1)) * 100,
    (point[1] / Math.max(site.height, 1)) * 100,
  ];
}

export function translateSiteGeometry(
  geometry: SitePointTuple[] | undefined,
  delta: Point2D,
): SitePointTuple[] | undefined {
  if (!Array.isArray(geometry)) return undefined;
  return geometry.map(([x, y]) => [x + delta.x, y + delta.y]);
}

export function boundsForSiteGeometry(geometry: SitePointTuple[]) {
  const xs = geometry.map((pt) => pt[0]);
  const ys = geometry.map((pt) => pt[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return {
    minX,
    minY,
    maxX,
    maxY,
    width: Math.max(0, maxX - minX),
    height: Math.max(0, maxY - minY),
  };
}

export function resizeSiteGeometryFromOrigin(
  geometry: SitePointTuple[] | undefined,
  origin: Point2D,
  from: SiteSize,
  to: SiteSize,
): SitePointTuple[] | undefined {
  if (!Array.isArray(geometry)) return undefined;
  const scaleX = to.width / Math.max(from.width, 1);
  const scaleY = to.height / Math.max(from.height, 1);
  return geometry.map(([x, y]) => [
    origin.x + (x - origin.x) * scaleX,
    origin.y + (y - origin.y) * scaleY,
  ]);
}

export function siteToMapLngLat(point: Point2D, anchor: MapAnchor): [number, number] | null {
  if (resolveCoordinateMode(anchor) !== "map_anchored") return null;
  const metersPerDegLng = METERS_PER_DEGREE_LATITUDE * Math.cos((anchor.lat * Math.PI) / 180);
  if (!Number.isFinite(metersPerDegLng) || Math.abs(metersPerDegLng) < 0.000001) return null;
  const dxFt = point.x - anchor.siteWidth / 2;
  const dyFt = anchor.siteHeight / 2 - point.y;
  const theta = ((anchor.rotationDeg ?? 0) * Math.PI) / 180;
  const dxRot = dxFt * Math.cos(theta) - dyFt * Math.sin(theta);
  const dyRot = dxFt * Math.sin(theta) + dyFt * Math.cos(theta);
  return [
    anchor.lng + (dxRot / FEET_PER_METER) / metersPerDegLng,
    anchor.lat + (dyRot / FEET_PER_METER) / METERS_PER_DEGREE_LATITUDE,
  ];
}

export function mapLngLatToSite(lngLat: { lat: number; lng: number }, anchor: MapAnchor): Point2D | null {
  if (resolveCoordinateMode(anchor) !== "map_anchored") return null;
  const metersPerDegLng = METERS_PER_DEGREE_LATITUDE * Math.cos((anchor.lat * Math.PI) / 180);
  if (!Number.isFinite(metersPerDegLng) || Math.abs(metersPerDegLng) < 0.000001) return null;
  const dxFt = (lngLat.lng - anchor.lng) * metersPerDegLng / METERS_PER_FOOT;
  const dyFt = (lngLat.lat - anchor.lat) * METERS_PER_DEGREE_LATITUDE / METERS_PER_FOOT;
  const theta = -((anchor.rotationDeg ?? 0) * Math.PI) / 180;
  const invDx = dxFt * Math.cos(theta) - dyFt * Math.sin(theta);
  const invDy = dxFt * Math.sin(theta) + dyFt * Math.cos(theta);
  return {
    x: invDx + anchor.siteWidth / 2,
    y: anchor.siteHeight / 2 - invDy,
  };
}
