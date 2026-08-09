"use client";

import { useEffect, useRef } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import mapboxgl from "mapbox-gl";

import { siteToRelativePoint, type MapAnchor, type SiteSize } from "../utils/geometryTransforms";
import { measureMapFeetPerPixel, measureMapSiteFeetPerPixel } from "../utils/previewMapProjection";
import type { PreviewPanelProps } from "./previewPanelTypes";

type MutableRef<T> = { current: T };
type SiteToLatLng = (xFt: number, yFt: number) => [number, number] | null;
type LatLngToSite = (lat: number, lng: number) => { x: number; y: number } | null;
type Geocode = { lat?: number; lng?: number } | null | undefined;
type DebugStats = { enabled?: boolean } | null | undefined;
type MapSize = { w: number; h: number };

type PreviewMapRuntimeOptions = {
  mapAvailable: boolean;
  mapOverlayEnabled: boolean;
  mapContainerRef: RefObject<HTMLDivElement | null>;
  fullscreenMapContainerRef: RefObject<HTMLDivElement | null>;
  mapRef: MutableRef<mapboxgl.Map | null>;
  fullscreenMapRef: MutableRef<mapboxgl.Map | null>;
  mapboxToken?: string;
  mapPitch: number;
  mapBearing: number;
  setMapLoaded: Dispatch<SetStateAction<boolean>>;
  setMapRevision: Dispatch<SetStateAction<number>>;
  setMapError: Dispatch<SetStateAction<string | null>>;
  allowMapInteraction?: boolean;
  mapLoaded: boolean;
  debugStats: DebugStats;
  showMap: boolean;
  setMapboxRequestCount: Dispatch<SetStateAction<number>>;
  setMapboxTileCount: Dispatch<SetStateAction<number>>;
  setMapCanvasSize: Dispatch<SetStateAction<MapSize | null>>;
  setMapContainerSize: Dispatch<SetStateAction<MapSize | null>>;
  onMapScaleUpdate?: PreviewPanelProps["onMapScaleUpdate"];
  mapAnchor: MapAnchor | null;
  onViewportFootprint?: PreviewPanelProps["onViewportFootprint"];
  siteLocked?: boolean;
  onViewportCenter?: PreviewPanelProps["onViewportCenter"];
  currentSiteSize: SiteSize;
  latLngToSite: LatLngToSite;
  lotWidth: number;
  lotHeight: number;
  placementMode: boolean;
  mapPanMode: boolean;
  selectedBuildingId: string | null;
  onPlaceObject: PreviewPanelProps["onPlaceObject"];
  onPlaceBuilding: PreviewPanelProps["onPlaceBuilding"];
  onSelectBuilding: PreviewPanelProps["onSelectBuilding"];
  showHover: boolean;
  scheduleCursorSitePoint: (point: { x: number; y: number } | null) => void;
  mapCenterRequest?: number;
  onMapCenter?: PreviewPanelProps["onMapCenter"];
  lastMapResizeRef: MutableRef<number>;
  previewFullscreenOpen: boolean;
  fullscreenContainerReady: boolean;
  geocode: Geocode;
  fitToSiteRequest?: number;
  siteToLatLng: SiteToLatLng;
  alignToRoadRequest?: number;
  onSetSiteRotationDeg?: PreviewPanelProps["onSetSiteRotationDeg"];
};

export function usePreviewMapRuntime({
  mapAvailable,
  mapOverlayEnabled,
  mapContainerRef,
  fullscreenMapContainerRef,
  mapRef,
  fullscreenMapRef,
  mapboxToken,
  mapPitch,
  mapBearing,
  setMapLoaded,
  setMapRevision,
  setMapError,
  allowMapInteraction,
  mapLoaded,
  debugStats,
  showMap,
  setMapboxRequestCount,
  setMapboxTileCount,
  setMapCanvasSize,
  setMapContainerSize,
  onMapScaleUpdate,
  mapAnchor,
  onViewportFootprint,
  siteLocked,
  onViewportCenter,
  currentSiteSize,
  latLngToSite,
  lotWidth,
  lotHeight,
  placementMode,
  mapPanMode,
  selectedBuildingId,
  onPlaceObject,
  onPlaceBuilding,
  onSelectBuilding,
  showHover,
  scheduleCursorSitePoint,
  mapCenterRequest,
  onMapCenter,
  lastMapResizeRef,
  previewFullscreenOpen,
  fullscreenContainerReady,
  geocode,
  fitToSiteRequest,
  siteToLatLng,
  alignToRoadRequest,
  onSetSiteRotationDeg,
}: PreviewMapRuntimeOptions) {
  const lastFittedSiteKeyRef = useRef("");
  useEffect(() => {
    if (!mapAvailable || !mapOverlayEnabled || !showMap) return;
    if (!mapContainerRef.current || mapRef.current) return;
    mapboxgl.accessToken = mapboxToken || "";
    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/satellite-streets-v12",
      center: [-95.9345, 41.2565],
      zoom: 16,
      pitch: 0,
      bearing: 0,
      attributionControl: false,
    });
    mapRef.current = map;
    const markMapReady = () => {
      if (mapRef.current !== map) return;
      map.resize();
      setMapLoaded(true);
      setMapRevision((value) => value + 1);
    };
    map.on("error", (event) => {
      const message =
        (event as { error?: { message?: string } })?.error?.message ||
        (event as { message?: string })?.message ||
        "Mapbox error";
      setMapError(message);
      markMapReady();
    });
    map.once("load", () => {
      try {
        if (!map.getSource("mapbox-dem")) {
          map.addSource("mapbox-dem", {
            type: "raster-dem",
            url: "mapbox://mapbox.terrain-rgb",
            tileSize: 512,
            maxzoom: 14,
          });
        }
      } catch (error) {
        setMapError(error instanceof Error ? error.message : "Map terrain setup failed");
      }
      markMapReady();
    });
    map.once("style.load", markMapReady);
    map.once("render", markMapReady);
    window.setTimeout(markMapReady, 500);
    return () => {
      if (mapRef.current !== map) return;
      map.remove();
      mapRef.current = null;
      lastFittedSiteKeyRef.current = "";
      setMapLoaded(false);
    };
  }, [mapAvailable, mapContainerRef, mapOverlayEnabled, mapRef, mapboxToken, setMapError, setMapLoaded, setMapRevision, showMap]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded || !mapRef.current) return;
    const map = mapRef.current;
    try {
      if (mapPitch > 0 && map.getSource("mapbox-dem")) {
        map.setTerrain({ source: "mapbox-dem", exaggeration: 1.0 });
      } else if (map.getTerrain()) {
        map.setTerrain(null);
      }
      setMapRevision((value) => value + 1);
    } catch (error) {
      setMapError(error instanceof Error ? error.message : "Map terrain mode failed");
    }
  }, [mapAvailable, mapLoaded, mapPitch, mapRef, setMapError, setMapRevision]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded) return;
    const targets = [mapRef.current, fullscreenMapRef.current].filter(
      (map): map is mapboxgl.Map => Boolean(map),
    );
    targets.forEach((map) => {
      if (allowMapInteraction) {
        map.dragPan.enable();
        map.scrollZoom.enable();
        map.boxZoom.enable();
        map.doubleClickZoom.enable();
        map.keyboard.enable();
        map.touchZoomRotate.enable();
      } else {
        map.dragPan.disable();
        map.scrollZoom.disable();
        map.boxZoom.disable();
        map.doubleClickZoom.disable();
        map.keyboard.disable();
        map.touchZoomRotate.disable();
      }
    });
  }, [allowMapInteraction, fullscreenMapRef, mapAvailable, mapLoaded, mapRef]);

  useEffect(() => {
    if (!showMap || !mapLoaded) return;
    const targets = [mapRef.current, fullscreenMapRef.current].filter(
      (map): map is mapboxgl.Map => Boolean(map),
    );
    targets.forEach((map) => {
      map.easeTo({
        pitch: mapPitch,
        bearing: mapBearing,
        duration: 450,
      });
    });
  }, [fullscreenMapRef, mapBearing, mapLoaded, mapPitch, mapRef, showMap]);

  useEffect(() => {
    if (!debugStats?.enabled || !showMap) return;
    const handle = window.setInterval(() => {
      const resources = performance.getEntriesByType("resource");
      const count = resources.filter((entry) => entry.name.includes("mapbox")).length;
      const tileCount = resources.filter(
        (entry) =>
          entry.name.includes("mapbox") &&
          (entry.name.includes("/styles/") ||
            entry.name.includes("/tiles/") ||
            entry.name.includes("sprite") ||
            entry.name.includes("glyphs")),
      ).length;
      setMapboxRequestCount(count);
      setMapboxTileCount(tileCount);
      const canvas = mapRef.current?.getCanvas?.();
      if (canvas) {
        setMapCanvasSize({ w: canvas.width, h: canvas.height });
      }
      if (mapContainerRef.current) {
        setMapContainerSize({
          w: mapContainerRef.current.clientWidth,
          h: mapContainerRef.current.clientHeight,
        });
      }
    }, 1500);
    return () => window.clearInterval(handle);
  }, [debugStats?.enabled, mapContainerRef, mapRef, setMapCanvasSize, setMapContainerSize, setMapboxRequestCount, setMapboxTileCount, showMap]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded || !mapRef.current) return;
    const map = mapRef.current;
    const reportScale = () => {
      if (!onMapScaleUpdate) return;
      const ftPerPx = measureMapSiteFeetPerPixel(map, mapAnchor) ?? measureMapFeetPerPixel(map);
      if (ftPerPx) {
        onMapScaleUpdate({ ftPerPx, source: "mapbox" });
      }
    };
    const reportViewport = () => {
      if (!onViewportFootprint) return;
      if (siteLocked) return;
      const bounds = map.getBounds();
      if (!bounds) return;
      const north = bounds.getNorth();
      const south = bounds.getSouth();
      const east = bounds.getEast();
      const west = bounds.getWest();
      const centerLat = (north + south) / 2;
      const metersPerDegLat = 111320;
      const metersPerDegLng = 111320 * Math.cos((centerLat * Math.PI) / 180);
      const widthM = Math.abs(east - west) * metersPerDegLng;
      const heightM = Math.abs(north - south) * metersPerDegLat;
      if (!Number.isFinite(widthM) || !Number.isFinite(heightM)) return;
      onViewportFootprint({
        widthFt: widthM / 0.3048,
        heightFt: heightM / 0.3048,
        bounds: {
          north,
          south,
          east,
          west,
          centerLat,
          centerLng: (east + west) / 2,
        },
      });
    };
    const reportCenter = () => {
      if (!onViewportCenter) return;
      const center = map.getCenter();
      onViewportCenter({ lat: center.lat, lng: center.lng });
    };
    reportScale();
    reportViewport();
    reportCenter();
    map.on("moveend", reportScale);
    map.on("zoomend", reportScale);
    map.on("moveend", reportViewport);
    map.on("zoomend", reportViewport);
    map.on("moveend", reportCenter);
    map.on("zoomend", reportCenter);
    map.on("resize", reportScale);
    map.on("resize", reportViewport);
    map.on("resize", reportCenter);
    const requestMapOverlayUpdate = () => setMapRevision((value) => value + 1);
    map.on("move", requestMapOverlayUpdate);
    map.on("zoom", requestMapOverlayUpdate);
    map.on("pitch", requestMapOverlayUpdate);
    map.on("rotate", requestMapOverlayUpdate);
    const handleClick = (event: mapboxgl.MapMouseEvent) => {
      if (placementMode) {
        const sitePoint = latLngToSite(event.lngLat.lat, event.lngLat.lng);
        if (!sitePoint || !lotWidth || !lotHeight) {
          return;
        }
        const relative = siteToRelativePoint(sitePoint, currentSiteSize);
        const relativeX = relative.x;
        const relativeY = relative.y;
        if (selectedBuildingId) {
          onPlaceObject(selectedBuildingId, { x: relativeX, y: relativeY });
        } else {
          onPlaceBuilding({ x: relativeX, y: relativeY });
        }
        return;
      }
      if (mapPanMode) return;
      const features = map.queryRenderedFeatures(event.point, {
        layers: [
          "civora-buildings-fill",
          "civora-parking-fill",
          "civora-basins-fill",
          "civora-constraints-fill",
          "civora-landscape-fill",
          "civora-utilities-line",
          "civora-roads-line",
          "civora-custom-areas-line",
          "civora-custom-lines-line",
          "civora-custom-points-circle",
        ],
      });
      const hit = features?.[0];
      const id = hit?.properties?.id;
      if (typeof id === "string") {
        onSelectBuilding(id);
      }
    };
    map.on("click", handleClick);
    const handleMouseMove = (event: mapboxgl.MapMouseEvent) => {
      if (!showHover || !lotWidth || !lotHeight) return;
      const sitePoint = latLngToSite(event.lngLat.lat, event.lngLat.lng);
      if (!sitePoint) return;
      scheduleCursorSitePoint(sitePoint);
    };
    map.on("mousemove", handleMouseMove);
    return () => {
      map.off("click", handleClick);
      map.off("mousemove", handleMouseMove);
      map.off("moveend", reportScale);
      map.off("zoomend", reportScale);
      map.off("moveend", reportViewport);
      map.off("zoomend", reportViewport);
      map.off("moveend", reportCenter);
      map.off("zoomend", reportCenter);
      map.off("resize", reportScale);
      map.off("resize", reportViewport);
      map.off("resize", reportCenter);
      map.off("move", requestMapOverlayUpdate);
      map.off("zoom", requestMapOverlayUpdate);
      map.off("pitch", requestMapOverlayUpdate);
      map.off("rotate", requestMapOverlayUpdate);
    };
  }, [currentSiteSize, latLngToSite, lotHeight, lotWidth, mapAnchor, mapAvailable, mapLoaded, mapPanMode, mapRef, onMapScaleUpdate, onPlaceBuilding, onPlaceObject, placementMode, scheduleCursorSitePoint, selectedBuildingId, onSelectBuilding, setMapRevision, showHover, onViewportCenter, onViewportFootprint, siteLocked]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded || !mapRef.current) return;
    if (!mapCenterRequest) return;
    const center = mapRef.current.getCenter();
    if (onMapCenter) {
      onMapCenter({ lat: center.lat, lng: center.lng });
    }
  }, [mapAvailable, mapCenterRequest, mapLoaded, mapRef, onMapCenter]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded) return;
    const container = mapContainerRef.current;
    if (!container) return;
    let frame: number | null = null;
    let settledFrame: number | null = null;
    const resizeMaps = () => {
      if (frame !== null) window.cancelAnimationFrame(frame);
      if (settledFrame !== null) window.cancelAnimationFrame(settledFrame);
      frame = window.requestAnimationFrame(() => {
        frame = null;
        lastMapResizeRef.current = Date.now();
        mapRef.current?.resize();
        if (previewFullscreenOpen) fullscreenMapRef.current?.resize();
        setMapRevision((value) => value + 1);
        settledFrame = window.requestAnimationFrame(() => {
          settledFrame = null;
          const map = mapRef.current;
          if (!map) return;
          const ftPerPx = measureMapSiteFeetPerPixel(map, mapAnchor) ?? measureMapFeetPerPixel(map);
          if (ftPerPx) onMapScaleUpdate?.({ ftPerPx, source: "mapbox" });
          setMapRevision((value) => value + 1);
        });
      });
    };
    resizeMaps();
    if (typeof ResizeObserver === "undefined") {
      const handle = window.setTimeout(resizeMaps, 160);
      return () => {
        window.clearTimeout(handle);
        if (frame !== null) window.cancelAnimationFrame(frame);
        if (settledFrame !== null) window.cancelAnimationFrame(settledFrame);
      };
    }
    const observer = new ResizeObserver(resizeMaps);
    observer.observe(container);
    if (previewFullscreenOpen && fullscreenMapContainerRef.current) {
      observer.observe(fullscreenMapContainerRef.current);
    }
    return () => {
      observer.disconnect();
      if (frame !== null) window.cancelAnimationFrame(frame);
      if (settledFrame !== null) window.cancelAnimationFrame(settledFrame);
    };
  }, [
    fullscreenMapContainerRef,
    fullscreenMapRef,
    lastMapResizeRef,
    mapAvailable,
    mapContainerRef,
    mapLoaded,
    mapAnchor,
    mapRef,
    onMapScaleUpdate,
    previewFullscreenOpen,
    setMapRevision,
  ]);

  useEffect(() => {
    if (!showMap || !previewFullscreenOpen) return;
    if (!fullscreenContainerReady) return;
    if (!fullscreenMapContainerRef.current || fullscreenMapRef.current) return;
    mapboxgl.accessToken = mapboxToken || "";
    const center = mapRef.current?.getCenter();
    const zoom = mapRef.current?.getZoom();
    const fullscreenMap = new mapboxgl.Map({
      container: fullscreenMapContainerRef.current,
      style: "mapbox://styles/mapbox/satellite-streets-v12",
      center: center ? [center.lng, center.lat] : [-95.9345, 41.2565],
      zoom: typeof zoom === "number" ? zoom : 16,
      pitch: mapPitch,
      bearing: mapBearing,
      attributionControl: false,
    });
    fullscreenMapRef.current = fullscreenMap;
    const requestMapOverlayUpdate = () => setMapRevision((value) => value + 1);
    fullscreenMap.on("move", requestMapOverlayUpdate);
    fullscreenMap.on("zoom", requestMapOverlayUpdate);
    fullscreenMap.on("pitch", requestMapOverlayUpdate);
    fullscreenMap.on("rotate", requestMapOverlayUpdate);
    fullscreenMap.on("load", () => {
      fullscreenMap.addSource("mapbox-dem", {
        type: "raster-dem",
        url: "mapbox://mapbox.terrain-rgb",
        tileSize: 512,
        maxzoom: 14,
      });
      if (mapPitch > 0) {
        fullscreenMap.setTerrain({ source: "mapbox-dem", exaggeration: 1.0 });
      }
      fullscreenMap.resize();
      setMapRevision((value) => value + 1);
    });
    return () => {
      fullscreenMap.off("move", requestMapOverlayUpdate);
      fullscreenMap.off("zoom", requestMapOverlayUpdate);
      fullscreenMap.off("pitch", requestMapOverlayUpdate);
      fullscreenMap.off("rotate", requestMapOverlayUpdate);
    };
  }, [fullscreenContainerReady, fullscreenMapContainerRef, fullscreenMapRef, mapBearing, mapPitch, mapRef, mapboxToken, previewFullscreenOpen, setMapRevision, showMap]);

  useEffect(() => {
    if (previewFullscreenOpen) return;
    if (!fullscreenMapRef.current) return;
    fullscreenMapRef.current.remove();
    fullscreenMapRef.current = null;
  }, [fullscreenMapRef, previewFullscreenOpen]);

  useEffect(() => {
    if (!showMap) return;
    if (previewFullscreenOpen) return;
    if (!fullscreenMapRef.current || !mapRef.current) return;
    const center = fullscreenMapRef.current.getCenter();
    const zoom = fullscreenMapRef.current.getZoom();
    mapRef.current.jumpTo({ center: [center.lng, center.lat], zoom, pitch: mapPitch, bearing: mapBearing });
  }, [fullscreenMapRef, mapBearing, mapPitch, mapRef, previewFullscreenOpen, showMap]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded) return;
    if (!geocode?.lng || !geocode?.lat) return;
    if (lotWidth > 0 && lotHeight > 0) return;
    const center: [number, number] = [geocode.lng, geocode.lat];
    mapRef.current?.flyTo({ center, zoom: 17 });
    fullscreenMapRef.current?.flyTo({ center, zoom: 17 });
  }, [fullscreenMapRef, geocode?.lat, geocode?.lng, lotHeight, lotWidth, mapAvailable, mapLoaded, mapRef]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded || !mapRef.current || !geocode?.lat || !geocode?.lng) return;
    if (!lotWidth || !lotHeight) return;
    const fitKey = `${geocode.lat.toFixed(7)}:${geocode.lng.toFixed(7)}:${lotWidth}:${lotHeight}:${fitToSiteRequest ?? "auto"}`;
    if (lastFittedSiteKeyRef.current === fitKey) return;
    const corners = [
      siteToLatLng(0, 0),
      siteToLatLng(lotWidth, 0),
      siteToLatLng(lotWidth, lotHeight),
      siteToLatLng(0, lotHeight),
    ].filter(Boolean) as Array<[number, number]>;
    if (corners.length < 4) return;
    const bounds = corners.reduce(
      (acc, coord) => acc.extend(coord),
      new mapboxgl.LngLatBounds(corners[0], corners[0]),
    );
    lastFittedSiteKeyRef.current = fitKey;
    mapRef.current.fitBounds(bounds, { padding: 80, duration: fitToSiteRequest ? 650 : 0 });
  }, [siteToLatLng, fitToSiteRequest, geocode?.lat, geocode?.lng, lotHeight, lotWidth, mapAvailable, mapLoaded, mapRef]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded || !mapRef.current) return;
    if (!alignToRoadRequest || !onSetSiteRotationDeg) return;
    const map = mapRef.current;
    const centerPoint = map.project(map.getCenter());
    const box = [
      [centerPoint.x - 120, centerPoint.y - 120],
      [centerPoint.x + 120, centerPoint.y + 120],
    ] as [mapboxgl.PointLike, mapboxgl.PointLike];
    const features = map.queryRenderedFeatures(box, { layers: ["road", "road-primary", "road-secondary", "road-street"] });
    const bearings: Array<{ bearing: number; weight: number }> = [];
    features.forEach((feature) => {
      const geom = feature.geometry;
      if (geom.type !== "LineString") return;
      const coords = geom.coordinates as number[][];
      for (let i = 0; i < coords.length - 1; i += 1) {
        const [lng1, lat1] = coords[i];
        const [lng2, lat2] = coords[i + 1];
        const dx = lng2 - lng1;
        const dy = lat2 - lat1;
        const bearing = (Math.atan2(dy, dx) * 180) / Math.PI;
        const weight = Math.hypot(dx, dy);
        if (Number.isFinite(bearing) && Number.isFinite(weight)) {
          bearings.push({ bearing, weight });
        }
      }
    });
    if (!bearings.length) return;
    const dominant = bearings.reduce((acc, item) => (item.weight > acc.weight ? item : acc), bearings[0]);
    const normalized = ((90 - dominant.bearing + 540) % 360) - 180;
    onSetSiteRotationDeg(normalized);
  }, [alignToRoadRequest, mapAvailable, mapLoaded, mapRef, onSetSiteRotationDeg]);

}
