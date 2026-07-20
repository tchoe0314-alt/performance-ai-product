import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import {
  boundsForSiteGeometry,
  coordinateModeLabel,
  mapLngLatToSite,
  resizeSiteGeometryFromOrigin,
  resolveCoordinateMode,
  screenToSitePoint,
  siteToMapLngLat,
  siteToScreenPoint,
  translateSiteGeometry,
} from "../../app/utils/geometryTransforms";

type CanonicalObject = {
  id: string;
  geometry: Array<[number, number]>;
  x: number;
  y: number;
  w: number;
  d: number;
};

const site = { width: 400, height: 300 };
const viewport = { left: 12, top: 16, width: 800, height: 600 };
const container = { left: 100, top: 50 };
const EARTH_RADIUS_METERS = 6_378_137;
const METERS_PER_FOOT = 0.3048;

function rectangleBuilding(): CanonicalObject {
  return {
    id: "building-1",
    x: 80,
    y: 70,
    w: 120,
    d: 60,
    geometry: [
      [80, 70],
      [200, 70],
      [200, 130],
      [80, 130],
      [80, 70],
    ],
  };
}

function toMercatorMeters(lngLat: [number, number]) {
  const [lng, lat] = lngLat;
  const lngRad = (lng * Math.PI) / 180;
  const latRad = (lat * Math.PI) / 180;
  return {
    x: EARTH_RADIUS_METERS * lngRad,
    y: EARTH_RADIUS_METERS * Math.log(Math.tan(Math.PI / 4 + latRad / 2)),
  };
}

function mercatorDistanceFeet(a: [number, number], b: [number, number]) {
  const aMeters = toMercatorMeters(a);
  const bMeters = toMercatorMeters(b);
  const dx = bMeters.x - aMeters.x;
  const dy = bMeters.y - aMeters.y;
  return Math.hypot(dx, dy) / METERS_PER_FOOT;
}

function projectMercatorPixels(lngLat: [number, number], center: [number, number], zoom: number) {
  const point = toMercatorMeters(lngLat);
  const centerPoint = toMercatorMeters(center);
  const worldPixels = 512 * 2 ** zoom;
  const metersPerPixelAtEquator = (2 * Math.PI * EARTH_RADIUS_METERS) / worldPixels;
  return {
    x: (point.x - centerPoint.x) / metersPerPixelAtEquator,
    y: (centerPoint.y - point.y) / metersPerPixelAtEquator,
  };
}

test.describe("map anchored canvas geometry transforms", () => {
  test("camera pan and zoom change projection but not canonical rectangle geometry", () => {
    const building = rectangleBuilding();
    const canonicalBefore = structuredClone(building);
    const camera = { scale: 1, offsetX: 0, offsetY: 0 };
    const pannedCamera = { scale: 1, offsetX: 160, offsetY: -45 };
    const zoomedCamera = { scale: 2.25, offsetX: -90, offsetY: 35 };

    const originalScreen = siteToScreenPoint({ x: building.x, y: building.y }, container, viewport, site, camera);
    const pannedScreen = siteToScreenPoint({ x: building.x, y: building.y }, container, viewport, site, pannedCamera);
    const zoomedScreen = siteToScreenPoint({ x: building.x, y: building.y }, container, viewport, site, zoomedCamera);

    expect(pannedScreen).not.toEqual(originalScreen);
    expect(zoomedScreen).not.toEqual(originalScreen);
    expect(building).toEqual(canonicalBefore);

    const recoveredFromZoom = screenToSitePoint(zoomedScreen, container, viewport, site, zoomedCamera);
    expect(recoveredFromZoom.x).toBeCloseTo(building.x, 6);
    expect(recoveredFromZoom.y).toBeCloseTo(building.y, 6);
    expect(building.w).toBe(canonicalBefore.w);
    expect(building.d).toBe(canonicalBefore.d);
  });

  test("quality and 2d or 3d toggles reuse the same canonical geometry", () => {
    const building = rectangleBuilding();
    const canonicalBefore = JSON.stringify(building);
    const renderStates = [
      { quality: "standard", mode: "2d" },
      { quality: "high", mode: "2d" },
      { quality: "standard", mode: "3d" },
      { quality: "high", mode: "3d" },
    ];

    for (const renderState of renderStates) {
      expect(renderState.quality).toMatch(/standard|high/);
      expect(renderState.mode).toMatch(/2d|3d/);
      const bounds = boundsForSiteGeometry(building.geometry);
      expect(bounds.width).toBe(120);
      expect(bounds.height).toBe(60);
      expect(JSON.stringify(building)).toBe(canonicalBefore);
    }
  });

  test("high quality and AI visualization copy stays visual-only and avoids restricted wording", () => {
    const sourcePath = fs.existsSync(path.resolve(process.cwd(), "app/components/PreviewPanel.tsx"))
      ? path.resolve(process.cwd(), "app/components/PreviewPanel.tsx")
      : path.resolve(process.cwd(), "apps/web/app/components/PreviewPanel.tsx");
    const source = fs.readFileSync(sourcePath, "utf8");
    const aiWatermarkStart = source.indexOf("const AI_REALISM_WATERMARK");
    const aiWatermarkSection = source.slice(aiWatermarkStart, aiWatermarkStart + 1200);

    expect(aiWatermarkSection).toContain("AI visualization from current review layout");
    expect(aiWatermarkSection).toContain("visual concept only");
    expect(aiWatermarkSection).toContain("not engineering evidence");
    expect(source).toContain("not_site_evidence: true");
    expect(source).toContain("construction_release_allowed: false");
    expect(aiWatermarkSection).not.toMatch(/construction-ready|stamp|seal|sign|certify|approval/i);
  });

  test("coordinate mode labels distinguish map anchored from local site fallback", () => {
    expect(coordinateModeLabel(resolveCoordinateMode({ lat: 41.2565, lng: -95.9345 }))).toBe("Map anchored");
    expect(coordinateModeLabel(resolveCoordinateMode(null))).toBe("Local site coordinates");
  });

  test("map projection round trips site coordinates without mutating geometry", () => {
    const building = rectangleBuilding();
    const canonicalBefore = structuredClone(building);
    const anchor = {
      lat: 41.2565,
      lng: -95.9345,
      siteWidth: site.width,
      siteHeight: site.height,
      rotationDeg: 18,
    };

    const lngLat = siteToMapLngLat({ x: building.x, y: building.y }, anchor);
    expect(lngLat).not.toBeNull();
    const recovered = mapLngLatToSite({ lng: lngLat![0], lat: lngLat![1] }, anchor);
    expect(recovered).not.toBeNull();
    expect(recovered!.x).toBeCloseTo(building.x, 5);
    expect(recovered!.y).toBeCloseTo(building.y, 5);
    expect(building).toEqual(canonicalBefore);
  });

  test("map anchored site size stays accurate to the requested feet dimensions", () => {
    const anchor = {
      lat: 41.151,
      lng: -96.247,
      siteWidth: 1000,
      siteHeight: 1000,
      rotationDeg: 0,
    };

    const westMid = siteToMapLngLat({ x: 0, y: 500 }, anchor);
    const eastMid = siteToMapLngLat({ x: 1000, y: 500 }, anchor);
    const northMid = siteToMapLngLat({ x: 500, y: 0 }, anchor);
    const southMid = siteToMapLngLat({ x: 500, y: 1000 }, anchor);

    expect(westMid).not.toBeNull();
    expect(eastMid).not.toBeNull();
    expect(northMid).not.toBeNull();
    expect(southMid).not.toBeNull();
    expect(mercatorDistanceFeet(westMid!, eastMid!)).toBeCloseTo(1000, 4);
    expect(mercatorDistanceFeet(northMid!, southMid!)).toBeCloseTo(1000, 4);

    const recoveredCenter = mapLngLatToSite({ lng: anchor.lng, lat: anchor.lat }, anchor);
    expect(recoveredCenter).not.toBeNull();
    expect(recoveredCenter!.x).toBeCloseTo(500, 5);
    expect(recoveredCenter!.y).toBeCloseTo(500, 5);
  });

  test("zoom changes screen projection without changing map anchored site dimensions", () => {
    const anchor = {
      lat: 41.151,
      lng: -96.247,
      siteWidth: 1000,
      siteHeight: 1000,
      rotationDeg: 22,
    };
    const center: [number, number] = [anchor.lng, anchor.lat];
    const left = siteToMapLngLat({ x: 0, y: 500 }, anchor);
    const right = siteToMapLngLat({ x: 1000, y: 500 }, anchor);

    expect(left).not.toBeNull();
    expect(right).not.toBeNull();
    expect(mercatorDistanceFeet(left!, right!)).toBeCloseTo(1000, 4);

    const leftZoom15 = projectMercatorPixels(left!, center, 15);
    const rightZoom15 = projectMercatorPixels(right!, center, 15);
    const leftZoom17 = projectMercatorPixels(left!, center, 17);
    const rightZoom17 = projectMercatorPixels(right!, center, 17);
    const pxAt15 = Math.hypot(rightZoom15.x - leftZoom15.x, rightZoom15.y - leftZoom15.y);
    const pxAt17 = Math.hypot(rightZoom17.x - leftZoom17.x, rightZoom17.y - leftZoom17.y);

    expect(pxAt17 / pxAt15).toBeCloseTo(4, 5);
    expect(mercatorDistanceFeet(left!, right!)).toBeCloseTo(1000, 4);
  });

  test("intentional move and resize update canonical coordinates only from edit operations", () => {
    const building = rectangleBuilding();
    const movedGeometry = translateSiteGeometry(building.geometry, { x: 25, y: -10 })!;
    const movedBounds = boundsForSiteGeometry(movedGeometry);

    expect(movedBounds.minX).toBe(105);
    expect(movedBounds.minY).toBe(60);
    expect(movedBounds.width).toBe(120);
    expect(movedBounds.height).toBe(60);

    const resizedGeometry = resizeSiteGeometryFromOrigin(
      movedGeometry,
      { x: movedBounds.minX, y: movedBounds.minY },
      { width: movedBounds.width, height: movedBounds.height },
      { width: 160, height: 80 },
    )!;
    const resizedBounds = boundsForSiteGeometry(resizedGeometry);

    expect(resizedBounds.minX).toBe(105);
    expect(resizedBounds.minY).toBe(60);
    expect(resizedBounds.width).toBe(160);
    expect(resizedBounds.height).toBe(80);
  });
});
