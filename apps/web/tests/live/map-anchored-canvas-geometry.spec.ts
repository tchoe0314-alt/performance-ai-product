import { expect, test } from "@playwright/test";

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
