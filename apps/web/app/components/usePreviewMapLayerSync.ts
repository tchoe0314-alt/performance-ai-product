"use client";

import { useEffect } from "react";
import type { RefObject } from "react";
import mapboxgl from "mapbox-gl";

import type { BuildingPlacement } from "../types";
import { buildPreviewParkingMapModules } from "../utils/previewParkingMapModules";
import type { buildWaterFireFlowViewModel } from "../utils/previewWaterFireFlow";
import type { PreviewPanelProps } from "./previewPanelTypes";

type SiteToLatLng = (xFt: number, yFt: number) => [number, number] | null;
type WaterFireFlowViewModel = ReturnType<typeof buildWaterFireFlowViewModel>;

export function usePreviewMapLayerSync({
  mapRef,
  fullscreenMapRef,
  showMap,
  mapLoaded,
  geocodeLat,
  geocodeLng,
  lotWidth,
  lotHeight,
  buildingPlacements,
  suggestedPlacementsLength,
  analysisPaths,
  debugStatsEnabled,
  planPreviewUrl,
  resolveVisualKind,
  showSiteBounds,
  surveyPoints,
  useLightHighQuality,
  waterFireFlow,
  siteToLatLng,
  mapRevision,
}: {
  mapRef: RefObject<mapboxgl.Map | null>;
  fullscreenMapRef: RefObject<mapboxgl.Map | null>;
  showMap: boolean;
  mapLoaded: boolean;
  geocodeLat?: number | null;
  geocodeLng?: number | null;
  lotWidth: number;
  lotHeight: number;
  buildingPlacements: BuildingPlacement[];
  suggestedPlacementsLength: number;
  analysisPaths: PreviewPanelProps["analysisPaths"];
  debugStatsEnabled?: boolean;
  planPreviewUrl?: string | null;
  resolveVisualKind: (item: BuildingPlacement) => string;
  showSiteBounds?: boolean;
  surveyPoints: PreviewPanelProps["surveyPoints"];
  useLightHighQuality: boolean;
  waterFireFlow: WaterFireFlowViewModel;
  siteToLatLng: SiteToLatLng;
  mapRevision: number;
}) {
  useEffect(() => {
    if (!showMap || !mapLoaded || !mapRef.current) return;
    if (!geocodeLat || !geocodeLng || !lotWidth || !lotHeight) return;

    const placedObjects = buildingPlacements.filter(
      (item) => item.type !== "site" && item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
    );

    if (debugStatsEnabled && process.env.NODE_ENV !== "production") {
      console.debug("[debug-preview] render-layer", {
        canonicalCount: buildingPlacements.length,
        placedCount: placedObjects.length,
        suggestedCount: suggestedPlacementsLength,
        showMap,
        previewImageActive: Boolean(planPreviewUrl),
      });
    }

    const buildPolygon = (item: BuildingPlacement) => {
      if ((item.geometryType === "polygon" || item.geometryType === "rect") && Array.isArray(item.geometry) && item.geometry.length > 2) {
        const closed = [...item.geometry];
        const first = closed[0];
        const last = closed[closed.length - 1];
        if (first && last && (first[0] !== last[0] || first[1] !== last[1])) {
          closed.push([first[0], first[1]]);
        }
        const coords = closed
          .map((pt) => siteToLatLng(pt[0], pt[1]))
          .filter(Boolean) as Array<[number, number]>;
        return coords.length === closed.length ? coords : null;
      }
      const x = item.x ?? 0;
      const y = item.y ?? 0;
      const rotation = item.rotation ?? 0;
      const rotated = rotation % 180 !== 0;
      const w = rotated ? item.d : item.w;
      const d = rotated ? item.w : item.d;
      const corners: Array<[number, number]> = [
        [x, y],
        [x + w, y],
        [x + w, y + d],
        [x, y + d],
        [x, y],
      ];
      const coords = corners
        .map((pt) => siteToLatLng(pt[0], pt[1]))
        .filter(Boolean) as Array<[number, number]>;
      return coords.length === corners.length ? coords : null;
    };

    const buildPolyline = (item: BuildingPlacement) => {
      if (item.geometryType === "polyline" && Array.isArray(item.geometry) && item.geometry.length > 1) {
        const coords = item.geometry
          .map((pt) => siteToLatLng(pt[0], pt[1]))
          .filter(Boolean) as Array<[number, number]>;
        return coords.length === item.geometry.length ? coords : null;
      }
      const x = item.x ?? 0;
      const y = item.y ?? 0;
      const isHorizontal = item.w >= item.d;
      const fallback = isHorizontal
        ? [
            [x, y + item.d / 2],
            [x + item.w, y + item.d / 2],
          ]
        : [
            [x + item.w / 2, y],
            [x + item.w / 2, y + item.d],
          ];
      const coords = fallback
        .map((pt) => siteToLatLng(pt[0], pt[1]))
        .filter(Boolean) as Array<[number, number]>;
      return coords.length === fallback.length ? coords : null;
    };

    const buildSitePolygon = () => {
      const corners: Array<[number, number]> = [
        [0, 0],
        [lotWidth, 0],
        [lotWidth, lotHeight],
        [0, lotHeight],
        [0, 0],
      ];
      const coords = corners
        .map((pt) => siteToLatLng(pt[0], pt[1]))
        .filter(Boolean) as Array<[number, number]>;
      return coords.length === corners.length ? coords : null;
    };

    const toFeatureCollection = (items: BuildingPlacement[], geometry: "Polygon" | "LineString") => ({
      type: "FeatureCollection",
      features: items
        .map((item) => {
          const coords = geometry === "LineString" ? buildPolyline(item) : buildPolygon(item);
          if (!coords) return null;
          return {
            type: "Feature",
            geometry: {
              type: geometry,
              coordinates: geometry === "Polygon" ? [coords] : coords,
            },
            properties: {
              id: item.id,
              type: item.type || "building",
              label: item.label || item.type || "object",
              height: typeof item.h === "number" && Number.isFinite(item.h) ? item.h : 16,
            },
          };
        })
        .filter(Boolean),
    });

    const surveyFeatureCollection = () => {
      if (!surveyPoints || !surveyPoints.length) {
        return { type: "FeatureCollection", features: [] };
      }
      const features = surveyPoints
        .map((pt, idx) => {
          const coords = siteToLatLng(pt.x, pt.y);
          if (!coords) return null;
          return {
            type: "Feature",
            geometry: {
              type: "Point",
              coordinates: coords,
            },
            properties: {
              id: `survey-${idx}`,
              elevation: typeof pt.z === "number" ? pt.z : null,
            },
          };
        })
        .filter(Boolean);
      return { type: "FeatureCollection", features };
    };

    const buildings = placedObjects.filter((item) => resolveVisualKind(item) === "building");
    const roads = placedObjects.filter((item) => item.type === "road" || item.type === "driveway");
    const sidewalks = placedObjects.filter((item) => item.type === "sidewalk");
    const parking = placedObjects.filter((item) => item.type === "parking");
    const basins = placedObjects.filter((item) => resolveVisualKind(item) === "water");
    const utilities = placedObjects.filter((item) => resolveVisualKind(item) === "utility");
    const constraints = placedObjects.filter(
      (item) => item.type === "setback_zone" || item.type === "no_build_zone" || item.type === "lot_block",
    );
    const landscapeAreas = placedObjects.filter((item) => resolveVisualKind(item) === "landscape");
    const customAreas = placedObjects.filter(
      (item) =>
        item.type === "custom" &&
        (item.geometryType === "polygon" || item.geometryType === "rect"),
    );
    const customLines = placedObjects.filter(
      (item) => item.type === "custom" && item.geometryType === "polyline",
    );
    const customPoints = placedObjects.filter(
      (item) => item.type === "custom" && item.geometryType === "point",
    );
    const accessPoints = placedObjects
      .filter((item) => item.type === "entrance" || item.type === "road" || item.type === "driveway")
      .map((item) => ({ x: (item.x ?? 0) + item.w / 2, y: (item.y ?? 0) + item.d / 2 }));
    const sitePolygon = buildSitePolygon();

    const parkingModules = parking.flatMap((item) => buildPreviewParkingMapModules(item, accessPoints));
    const visualLabelFeatureCollection = () => ({
      type: "FeatureCollection",
      features: placedObjects
        .filter((item) => item.type !== "site")
        .map((item) => {
          const x = (item.x ?? 0) + item.w / 2;
          const y = (item.y ?? 0) + item.d / 2;
          const coords = siteToLatLng(x, y);
          if (!coords) return null;
          return {
            type: "Feature",
            geometry: { type: "Point", coordinates: coords },
            properties: {
              id: item.id,
              label: item.label || item.type || "Object",
              visualOnly: true,
              kind: resolveVisualKind(item),
            },
          };
        })
        .filter(Boolean),
    });

    const updateMap = (map: mapboxgl.Map | null) => {
      if (!map || !map.isStyleLoaded()) return;
      const ensureSource = (id: string, data: unknown) => {
        const sourceData = data as Parameters<mapboxgl.GeoJSONSource["setData"]>[0];
        if (!map.getSource(id)) {
          map.addSource(id, { type: "geojson", data: sourceData });
        } else {
          (map.getSource(id) as mapboxgl.GeoJSONSource).setData(sourceData);
        }
      };

      const ensureLayer = (
        id: string,
        source: string,
        type: "fill" | "line" | "circle",
        paint: mapboxgl.AnyPaint,
      ) => {
        if (!map.getLayer(id)) {
          map.addLayer({ id, type, source, paint });
        }
      };
      const ensureExtrusion = (id: string, source: string, paint: mapboxgl.AnyPaint) => {
        if (!map.getLayer(id)) {
          map.addLayer({ id, type: "fill-extrusion", source, paint });
        }
      };

      ensureSource("civora-buildings", toFeatureCollection(buildings, "Polygon"));
      ensureSource("civora-roads", toFeatureCollection(roads, "LineString"));
      ensureSource("civora-sidewalks", toFeatureCollection(sidewalks, "LineString"));
      ensureSource("civora-parking", toFeatureCollection(parking, "Polygon"));
      ensureSource("civora-constraints", toFeatureCollection(constraints, "Polygon"));
      ensureSource("civora-landscape", toFeatureCollection(landscapeAreas, "Polygon"));
      ensureSource("civora-utilities", toFeatureCollection(utilities, "LineString"));
      ensureSource("civora-visual-labels", visualLabelFeatureCollection());
      ensureSource("civora-parking-aisles", {
        type: "FeatureCollection",
        features: parkingModules
          .map((module) => {
            const coords = module.aisleLine
              .map((pt) => siteToLatLng(pt[0], pt[1]))
              .filter(Boolean) as Array<[number, number]>;
            if (coords.length < 2) return null;
            return {
              type: "Feature",
              geometry: { type: "LineString", coordinates: coords },
              properties: { id: `${module.id}-aisle` },
            };
          })
          .filter(Boolean),
      });
      ensureSource("civora-parking-stalls", {
        type: "FeatureCollection",
        features: parkingModules
          .flatMap((module) =>
            module.stallPolygons.map((stall, idx) => {
              const coords = stall.points
                .map((pt) => siteToLatLng(pt[0], pt[1]))
                .filter(Boolean) as Array<[number, number]>;
              if (coords.length < 4) return null;
              return {
                type: "Feature",
                geometry: { type: "Polygon", coordinates: [coords] },
                properties: {
                  id: `${module.id}-stall-${idx}`,
                  kind: stall.kind,
                  angle: module.angle,
                  ada: module.isAdaModule,
                  compact: module.isCompactModule,
                },
              };
            }),
          )
          .filter(Boolean),
      });
      ensureSource("civora-parking-stripes", {
        type: "FeatureCollection",
        features: parkingModules
          .flatMap((module) =>
            module.stripeLines.map((line, idx) => {
              const coords = line
                .map((pt) => siteToLatLng(pt[0], pt[1]))
                .filter(Boolean) as Array<[number, number]>;
              if (coords.length < 2) return null;
              return {
                type: "Feature",
                geometry: { type: "LineString", coordinates: coords },
                properties: { id: `${module.id}-stripe-${idx}` },
              };
            }),
          )
          .filter(Boolean),
      });
      ensureSource("civora-parking-modules", {
        type: "FeatureCollection",
        features: parkingModules
          .map((module) => {
            const coords = module.bounds
              .map((pt) => siteToLatLng(pt[0], pt[1]))
              .filter(Boolean) as Array<[number, number]>;
            if (coords.length < 4) return null;
            return {
              type: "Feature",
              geometry: { type: "Polygon", coordinates: [coords] },
              properties: {
                id: module.id,
                angle: module.angle,
                ada: module.isAdaModule,
                compact: module.isCompactModule,
              },
            };
          })
          .filter(Boolean),
      });
      ensureSource("civora-basins", toFeatureCollection(basins, "Polygon"));
      ensureSource("civora-pressure-zones", {
        type: "FeatureCollection",
        features: waterFireFlow.pressureZones
          .filter((zone) => zone.geometry.length > 2)
          .map((zone) => {
            const coords = zone.geometry
              .map((pt) => siteToLatLng(pt[0], pt[1]))
              .filter(Boolean) as Array<[number, number]>;
            if (coords.length < 4) return null;
            return {
              type: "Feature",
              geometry: { type: "Polygon", coordinates: [coords] },
              properties: {
                id: zone.id,
                label: zone.label,
                color: zone.color,
              },
            };
          })
          .filter(Boolean),
      });
      ensureSource("civora-water-segments", {
        type: "FeatureCollection",
        features: waterFireFlow.networkSegments
          .filter((segment) => segment.geometry.length > 1)
          .map((segment) => {
            const coords = segment.geometry
              .map((pt) => siteToLatLng(pt[0], pt[1]))
              .filter(Boolean) as Array<[number, number]>;
            if (coords.length < 2) return null;
            return {
              type: "Feature",
              geometry: { type: "LineString", coordinates: coords },
              properties: {
                id: segment.id,
                label: segment.label,
                networkType: segment.networkType,
                diameter: segment.diameterIn,
              },
            };
          })
          .filter(Boolean),
      });
      ensureSource("civora-hydrants", {
        type: "FeatureCollection",
        features: waterFireFlow.hydrants
          .map((hydrant) => {
            const coord = siteToLatLng(hydrant.x, hydrant.y);
            if (!coord) return null;
            return {
              type: "Feature",
              geometry: { type: "Point", coordinates: coord },
              properties: {
                id: hydrant.id,
                label: hydrant.label,
                status: hydrant.status,
                selected: waterFireFlow.selectedHydrant?.id === hydrant.id,
              },
            };
          })
          .filter(Boolean),
      });
      ensureSource("civora-custom-areas", toFeatureCollection(customAreas, "Polygon"));
      ensureSource("civora-custom-lines", toFeatureCollection(customLines, "LineString"));
      ensureSource("civora-custom-points", {
        type: "FeatureCollection",
        features: customPoints
          .map((item) => {
            const coord = siteToLatLng((item.x ?? 0) + item.w / 2, (item.y ?? 0) + item.d / 2);
            if (!coord) return null;
            return {
              type: "Feature",
              geometry: { type: "Point", coordinates: coord },
              properties: { id: item.id, label: item.label },
            };
          })
          .filter(Boolean),
      });
      if (sitePolygon) {
        ensureSource("civora-site", {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: { type: "Polygon", coordinates: [sitePolygon] },
              properties: { id: "site-boundary" },
            },
          ],
        });
      }
      if (geocodeLat && geocodeLng) {
        ensureSource("civora-center", {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: { type: "Point", coordinates: [geocodeLng, geocodeLat] },
              properties: { id: "site-center" },
            },
          ],
        });
      }
      ensureSource("civora-survey", surveyFeatureCollection());

      ensureExtrusion("civora-buildings-extrusion", "civora-buildings", {
        "fill-extrusion-color": "#374151",
        "fill-extrusion-height": ["get", "height"],
        "fill-extrusion-base": 0,
        "fill-extrusion-opacity": useLightHighQuality ? 0.28 : 0.6,
      });
      ensureLayer("civora-buildings-fill", "civora-buildings", "fill", {
        "fill-color": "#475569",
        "fill-opacity": useLightHighQuality ? 0.18 : 0.26,
      });
      ensureLayer("civora-buildings-line", "civora-buildings", "line", {
        "line-color": "#111827",
        "line-width": useLightHighQuality ? 1.3 : 2,
      });
      ensureLayer("civora-roads-line", "civora-roads", "line", {
        "line-color": "#1f2937",
        "line-width": useLightHighQuality ? 2.1 : 3,
      });
      ensureLayer("civora-sidewalks-line", "civora-sidewalks", "line", {
        "line-color": "#0f766e",
        "line-width": useLightHighQuality ? 1.2 : 2,
        "line-dasharray": [1, 1],
      });
      ensureLayer("civora-constraints-fill", "civora-constraints", "fill", {
        "fill-color": [
          "case",
          ["==", ["get", "type"], "no_build_zone"],
          "#ef4444",
          ["==", ["get", "type"], "setback_zone"],
          "#f59e0b",
          "#64748b",
        ],
        "fill-opacity": useLightHighQuality ? 0.12 : 0.18,
      });
      ensureLayer("civora-constraints-line", "civora-constraints", "line", {
        "line-color": [
          "case",
          ["==", ["get", "type"], "no_build_zone"],
          "#b91c1c",
          ["==", ["get", "type"], "setback_zone"],
          "#d97706",
          "#475569",
        ],
        "line-width": useLightHighQuality ? 1 : 1.4,
        "line-dasharray": [2, 1],
      });
      ensureLayer("civora-landscape-fill", "civora-landscape", "fill", {
        "fill-color": [
          "case",
          ["==", ["get", "type"], "amenity"],
          "#84cc16",
          "#22c55e",
        ],
        "fill-opacity": useLightHighQuality ? 0.16 : 0.26,
      });
      ensureLayer("civora-landscape-line", "civora-landscape", "line", {
        "line-color": "#16a34a",
        "line-width": useLightHighQuality ? 0.8 : 1.2,
      });
      ensureLayer("civora-utilities-line", "civora-utilities", "line", {
        "line-color": [
          "case",
          ["==", ["get", "type"], "hydrant"],
          "#dc2626",
          ["==", ["get", "type"], "inlet"],
          "#0284c7",
          "#7c3aed",
        ],
        "line-width": useLightHighQuality ? 1.5 : 2.2,
        "line-dasharray": [3, 1],
      });
      ensureLayer("civora-parking-fill", "civora-parking", "fill", {
        "fill-color": "#64748b",
        "fill-opacity": 0.35,
      });
      ensureLayer("civora-parking-stalls", "civora-parking-stalls", "fill", {
        "fill-color": [
          "case",
          ["==", ["get", "kind"], "ada"],
          "#10b981",
          ["==", ["get", "kind"], "ada_aisle"],
          "#34d399",
          ["==", ["get", "kind"], "compact"],
          "#a855f7",
          "#94a3b8",
        ],
        "fill-opacity": [
          "case",
          ["==", ["get", "kind"], "ada"],
          0.35,
          ["==", ["get", "kind"], "ada_aisle"],
          0.25,
          ["==", ["get", "kind"], "compact"],
          0.3,
          0.22,
        ],
      });
      ensureLayer("civora-parking-stripes", "civora-parking-stripes", "line", {
        "line-color": "#cbd5f5",
        "line-width": 0.8,
        "line-opacity": 0.5,
      });
      ensureLayer("civora-parking-aisles", "civora-parking-aisles", "line", {
        "line-color": "#334155",
        "line-width": 1.6,
      });
      if (analysisPaths && analysisPaths.length) {
        ensureLayer("civora-parking-modules", "civora-parking-modules", "fill", {
          "fill-color": [
            "case",
            ["==", ["get", "ada"], true],
            "#10b981",
            ["==", ["get", "compact"], true],
            "#a855f7",
            ["==", ["get", "angle"], 45],
            "#38bdf8",
            ["==", ["get", "angle"], 60],
            "#818cf8",
            "#94a3b8",
          ],
          "fill-opacity": 0.15,
        });
      } else if (map.getLayer("civora-parking-modules")) {
        map.removeLayer("civora-parking-modules");
      }
      ensureLayer("civora-basins-fill", "civora-basins", "fill", {
        "fill-color": "#0ea5e9",
        "fill-opacity": 0.28,
      });
      ensureLayer("civora-pressure-zones-fill", "civora-pressure-zones", "fill", {
        "fill-color": ["coalesce", ["get", "color"], "#0ea5e9"],
        "fill-opacity": 0.12,
      });
      ensureLayer("civora-pressure-zones-line", "civora-pressure-zones", "line", {
        "line-color": ["coalesce", ["get", "color"], "#0ea5e9"],
        "line-width": 1.6,
        "line-dasharray": [2, 1],
      });
      ensureLayer("civora-water-segments-line", "civora-water-segments", "line", {
        "line-color": [
          "case",
          ["==", ["get", "networkType"], "loop"],
          "#0284c7",
          "#f97316",
        ],
        "line-width": ["case", ["==", ["get", "networkType"], "loop"], 3, 2.4],
        "line-dasharray": ["case", ["==", ["get", "networkType"], "loop"], ["literal", [1, 0]], ["literal", [2, 1]]],
      });
      ensureLayer("civora-hydrants-circle", "civora-hydrants", "circle", {
        "circle-color": [
          "case",
          ["==", ["get", "status"], "pass"],
          "#16a34a",
          ["==", ["get", "status"], "fail"],
          "#dc2626",
          "#f97316",
        ],
        "circle-radius": ["case", ["==", ["get", "selected"], true], 7, 5],
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2,
      });
      ensureLayer("civora-custom-areas-fill", "civora-custom-areas", "fill", {
        "fill-color": [
          "case",
          ["==", ["get", "type"], "open_space"],
          "#22c55e",
          ["==", ["get", "type"], "landscape"],
          "#22c55e",
          ["==", ["get", "type"], "amenity"],
          "#84cc16",
          "#94a3b8",
        ],
        "fill-opacity": [
          "case",
          ["any", ["==", ["get", "type"], "open_space"], ["==", ["get", "type"], "landscape"]],
          0.22,
          0.16,
        ],
      });
      ensureLayer("civora-custom-areas-line", "civora-custom-areas", "line", {
        "line-color": "#0284c7",
        "line-width": 1.4,
      });
      ensureLayer("civora-custom-lines-line", "civora-custom-lines", "line", {
        "line-color": "#0284c7",
        "line-width": 1.4,
      });
      ensureLayer("civora-custom-points-circle", "civora-custom-points", "circle", {
        "circle-color": "#0284c7",
        "circle-radius": 4,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1,
      });
      if (showSiteBounds && sitePolygon) {
        ensureLayer("civora-site-line", "civora-site", "line", {
          "line-color": "#f59e0b",
          "line-width": 2,
          "line-dasharray": [2, 2],
        });
      } else if (map.getLayer("civora-site-line")) {
        map.removeLayer("civora-site-line");
      }
      if (geocodeLat && geocodeLng) {
        ensureLayer("civora-center-crosshair", "civora-center", "circle", {
          "circle-color": "#f97316",
          "circle-radius": 4,
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 1,
        });
      }
      if (surveyPoints && surveyPoints.length) {
        ensureLayer("civora-survey-points", "civora-survey", "circle", {
          "circle-color": "#7c3aed",
          "circle-radius": 2.2,
          "circle-opacity": 0.7,
        });
      } else if (map.getLayer("civora-survey-points")) {
        map.removeLayer("civora-survey-points");
      }
      if (map.getLayer("civora-visual-labels")) {
        map.removeLayer("civora-visual-labels");
      }
    };

    updateMap(mapRef.current);
    updateMap(fullscreenMapRef.current);
  }, [
    buildingPlacements,
    analysisPaths,
    debugStatsEnabled,
    siteToLatLng,
    geocodeLat,
    geocodeLng,
    lotHeight,
    lotWidth,
    mapLoaded,
    mapRevision,
    planPreviewUrl,
    resolveVisualKind,
    showMap,
    showSiteBounds,
    suggestedPlacementsLength,
    surveyPoints,
    useLightHighQuality,
    waterFireFlow,
    mapRef,
    fullscreenMapRef,
  ]);
}
