"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { Maximize2, X } from "lucide-react";

import type {
  Preview3DItem,
  PreviewResponse,
  PreviewReview,
  BuildingPlacement,
} from "../types";
import { formatCount, formatMetric } from "../utils/formatting";
import Preview3DCanvas from "./Preview3DCanvas";

type PreviewPhaseLabel = { label: string } | null;

type PreviewPanelProps = {
  previewReview: PreviewReview | null;
  previewTotalPhaseCount: number;
  previewCompletedPhaseCount: number;
  previewRunningPhase: PreviewPhaseLabel;
  previewNextPendingPhase: PreviewPhaseLabel;
  onRefreshPreview: () => void;
  busy: boolean;
  planPreviewUrl: string;
  previewMode: "2d" | "3d";
  previewInteraction: "static" | "interactive";
  previewQuality: "standard" | "high";
  previewLabelDensity: "low" | "standard" | "high";
  hasGeneratedPlan: boolean;
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewInteraction: (value: "static" | "interactive") => void;
  onSetPreviewQuality: (value: "standard" | "high") => void;
  onSetPreviewLabelDensity: (value: "low" | "standard" | "high") => void;
  onQueuePreviewRefresh: (reason: string) => void;
  previewRefreshing: boolean;
  previewRefreshNote: string | null;
  preview3DEffectiveItems: Preview3DItem[];
  usingAnnotation3D: boolean;
  hasGradingSurface: boolean;
  placementMode: boolean;
  onPlaceBuilding: (position: { x: number; y: number }) => void;
  onPlaceObject: (id: string, position: { x: number; y: number }) => void;
  buildingPlacements: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
  selectedBuildingId: string | null;
  focusDetectedId?: string | null;
  focusObjectId?: string | null;
  onClearFocusDetected?: () => void;
  onClearFocusObject?: () => void;
  lotWidth: number;
  lotHeight: number;
  onUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  onUpdateSuggested: (id: string, updates: Partial<BuildingPlacement>) => void;
  onRemoveBuilding: (id: string) => void;
  onSelectBuilding: (id: string | null) => void;
  analysisPaths?: Array<{
    id: string;
    buildingId: string;
    accessId: string;
    from: { x: number; y: number };
    to: { x: number; y: number };
    label: string;
    points?: Array<{ x: number; y: number }>;
  }>;
  analysisHighlight?: { buildingId: string; accessId: string; pathId: string } | null;
  analysisFocusLocked?: boolean;
  onClearHighlights?: () => void;
  onResetView?: () => void;
  onOpenFullscreen: () => void;
  previewFullscreenOpen: boolean;
  onCloseFullscreen: () => void;
  onExportDxf: () => void;
  onExportReport: () => void;
  planPreviewAnnotations: PreviewResponse["preview_annotations"] | null;
  selectedIssueLabel: string;
  showMeasurements: boolean;
  showCalculations: boolean;
  measurementOverlayStats: Array<{ label: string; value: number | null; unit: string }>;
  calculationOverlayStats: Array<{ label: string; value: number | null; unit: string }>;
  geocode?: { lat?: number; lng?: number } | null;
  siteRotationDeg?: number | null;
  showSiteBounds?: boolean;
  fitToSiteRequest?: number;
  alignToRoadRequest?: number;
  onSetSiteRotationDeg?: (value: number) => void;
  surveyPoints?: Array<{ x: number; y: number; z?: number }>;
  onMapScaleUpdate?: (payload: { ftPerPx: number; source: "mapbox" }) => void;
};

export default function PreviewPanel({
  previewReview,
  previewTotalPhaseCount,
  previewCompletedPhaseCount,
  previewRunningPhase,
  previewNextPendingPhase,
  onRefreshPreview,
  busy,
  planPreviewUrl,
  previewMode,
  previewInteraction,
  previewQuality,
  previewLabelDensity,
  hasGeneratedPlan,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onSetPreviewQuality,
  onSetPreviewLabelDensity,
  onQueuePreviewRefresh,
  previewRefreshing,
  previewRefreshNote,
  preview3DEffectiveItems,
  usingAnnotation3D,
  hasGradingSurface,
  placementMode,
  onPlaceBuilding,
  onPlaceObject,
  buildingPlacements,
  suggestedPlacements,
  selectedBuildingId,
  focusDetectedId,
  focusObjectId,
  onClearFocusDetected,
  onClearFocusObject,
  lotWidth,
  lotHeight,
  onUpdateBuilding,
  onUpdateSuggested,
  onRemoveBuilding,
  onSelectBuilding,
  analysisPaths,
  analysisHighlight,
  analysisFocusLocked,
  onClearHighlights,
  onResetView,
  onOpenFullscreen,
  previewFullscreenOpen,
  onCloseFullscreen,
  onExportDxf,
  onExportReport,
  planPreviewAnnotations,
  selectedIssueLabel,
  showMeasurements,
  showCalculations,
  measurementOverlayStats,
  calculationOverlayStats,
  geocode,
  siteRotationDeg,
  showSiteBounds = false,
  fitToSiteRequest,
  alignToRoadRequest,
  onSetSiteRotationDeg,
  surveyPoints,
  onMapScaleUpdate,
}: PreviewPanelProps) {
  const previewLabels = useMemo(
    () => (Array.isArray(planPreviewAnnotations?.labels) ? planPreviewAnnotations?.labels : []),
    [planPreviewAnnotations],
  );
  const issueHighlightBounds = useMemo(() => {
    if (!selectedIssueLabel || !previewLabels.length) return null;
    const target = previewLabels.find(
      (item) =>
        item.bounds &&
        (item.label === selectedIssueLabel || item.label.includes(selectedIssueLabel)),
    );
    return target?.bounds ?? null;
  }, [previewLabels, selectedIssueLabel]);
  const [hoveredAnnotation, setHoveredAnnotation] = useState<(typeof previewLabels)[number] | null>(null);
  const [hoveredObjectId, setHoveredObjectId] = useState<string | null>(null);
  const [pinnedAnnotation, setPinnedAnnotation] = useState<(typeof previewLabels)[number] | null>(null);
  const [hoverPoint, setHoverPoint] = useState<{ x: number; y: number } | null>(null);
  const [fullscreenHoverPoint, setFullscreenHoverPoint] = useState<{ x: number; y: number } | null>(null);
  const [previewImageBounds, setPreviewImageBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [fullscreenImageBounds, setFullscreenImageBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [previewContainerBounds, setPreviewContainerBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [draggingBuildingId, setDraggingBuildingId] = useState<string | null>(null);
  const [draggingMode, setDraggingMode] = useState<"move" | "resize" | "rotate" | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const previewRef = useRef<HTMLDivElement | null>(null);
  const fullscreenRef = useRef<HTMLDivElement | null>(null);
  const previewImageRef = useRef<HTMLImageElement | null>(null);
  const fullscreenImageRef = useRef<HTMLImageElement | null>(null);
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const fullscreenMapContainerRef = useRef<HTMLDivElement | null>(null);
  const fullscreenMapRef = useRef<mapboxgl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapRevision, setMapRevision] = useState(0);
  const [rotateDragActive, setRotateDragActive] = useState(false);
  const [rotateDragStart, setRotateDragStart] = useState<{ x: number; value: number } | null>(null);
  const activeAnnotation = pinnedAnnotation ?? hoveredAnnotation;
  const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  const showMap = Boolean(mapboxToken) && previewQuality === "high";
  const showGeneratedPlan = !showMap && hasGeneratedPlan && !placementMode && !selectedBuildingId;
  const hasInteractiveLabels = previewLabels.length > 0 && showGeneratedPlan;
  const showInteractive = previewInteraction === "interactive";
  const legendPalette = {
    building: "#0f172a",
    parking: "#cbd5e1",
    road: "#475569",
    drainage: "#1d4ed8",
    utilities: "#7c3aed",
  } as const;
  const hoveredObject = useMemo(
    () =>
      [...buildingPlacements, ...suggestedPlacements].find((item) => item.id === hoveredObjectId) ??
      null,
    [buildingPlacements, suggestedPlacements, hoveredObjectId],
  );
  const show3D = previewMode === "3d" && Boolean(planPreviewUrl) && !showMap;
  useEffect(() => {
    if (previewMode === "3d" && (!planPreviewUrl || preview3DEffectiveItems.length === 0 || showMap)) {
      onSetPreviewMode("2d");
    }
  }, [onSetPreviewMode, planPreviewUrl, preview3DEffectiveItems.length, previewMode, showMap]);
  useEffect(() => {
    if ((!planPreviewUrl || showMap) && previewMode === "3d") {
      onSetPreviewMode("2d");
    }
  }, [onSetPreviewMode, planPreviewUrl, previewMode, showMap]);
  const selectedObject = useMemo(
    () =>
      [...buildingPlacements, ...suggestedPlacements].find(
        (item) => item.id === selectedBuildingId,
      ) ?? null,
    [buildingPlacements, suggestedPlacements, selectedBuildingId],
  );

  useEffect(() => {
    if (!activeAnnotation?.meta) {
      return;
    }
    const entityId = String(activeAnnotation.meta.entity_id || "");
    if (!entityId) {
      return;
    }
    if ([...buildingPlacements, ...suggestedPlacements].some((item) => item.id === entityId)) {
      setHoveredObjectId(entityId);
    }
  }, [activeAnnotation, buildingPlacements, suggestedPlacements]);
  const activeHighlightBounds = activeAnnotation?.bounds ?? null;
  const clampPercent = (value: number) => Math.min(Math.max(value * 100, 0), 100);
  const buildBoundsStyle = (bounds: { x1: number; y1: number; x2: number; y2: number }) => {
    const left = clampPercent(bounds.x1);
    const right = clampPercent(bounds.x2);
    const top = clampPercent(bounds.y1);
    const bottom = clampPercent(bounds.y2);
    return {
      left: `${left}%`,
      top: `${top}%`,
      width: `${Math.max(right - left, 1)}%`,
      height: `${Math.max(bottom - top, 1)}%`,
    };
  };
  const updateImageBounds = useCallback(
    (
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageRef: React.RefObject<HTMLImageElement | null>,
      setter: React.Dispatch<React.SetStateAction<{ left: number; top: number; width: number; height: number } | null>>,
    ) => {
      if (!containerRef.current || !imageRef.current) {
        setter(null);
        return;
      }
      const containerRect = containerRef.current.getBoundingClientRect();
      const imageRect = imageRef.current.getBoundingClientRect();
      const width = Math.max(imageRect.width, 1);
      const height = Math.max(imageRect.height, 1);
      setter({
        left: imageRect.left - containerRect.left,
        top: imageRect.top - containerRect.top,
        width,
        height,
      });
    },
    [],
  );
  const updateContainerBounds = useCallback(() => {
    if (!previewRef.current) return;
    const rect = previewRef.current.getBoundingClientRect();
    setPreviewContainerBounds({ left: 0, top: 0, width: rect.width, height: rect.height });
  }, []);
  const resolveHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageBounds: { left: number; top: number; width: number; height: number } | null,
      setPoint: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>,
    ) => {
      if (!showInteractive || !containerRef.current || !hasInteractiveLabels) {
        setHoveredAnnotation(null);
        setPoint(null);
        return;
      }
      const rect = containerRef.current.getBoundingClientRect();
      const bounds = imageBounds || { left: 0, top: 0, width: rect.width, height: rect.height };
      const relativeX = (event.clientX - rect.left - bounds.left) / Math.max(bounds.width, 1);
      const relativeY = (event.clientY - rect.top - bounds.top) / Math.max(bounds.height, 1);
      if (relativeX < 0 || relativeX > 1 || relativeY < 0 || relativeY > 1) {
        setHoveredAnnotation(null);
        setPoint(null);
        return;
      }
      const matches = previewLabels
        .filter((label) => {
          const bounds = label.bounds;
          if (!bounds) return false;
          return (
            relativeX >= bounds.x1 &&
            relativeX <= bounds.x2 &&
            relativeY >= bounds.y1 &&
            relativeY <= bounds.y2
          );
        })
        .sort((a, b) => {
          const aBounds = a.bounds;
          const bBounds = b.bounds;
          if (!aBounds || !bBounds) return 0;
          const aArea = Math.max(0, aBounds.x2 - aBounds.x1) * Math.max(0, aBounds.y2 - aBounds.y1);
          const bArea = Math.max(0, bBounds.x2 - bBounds.x1) * Math.max(0, bBounds.y2 - bBounds.y1);
          return aArea - bArea;
        });
      const next = matches[0] ?? null;
      setHoveredAnnotation(next);
      setPoint({ x: event.clientX - rect.left, y: event.clientY - rect.top });
    },
    [hasInteractiveLabels, previewLabels, showInteractive],
  );

  const resolvePlacement = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageBounds: { left: number; top: number; width: number; height: number } | null,
    ) => {
      if (!placementMode || !containerRef.current) {
        return;
      }
      const rect = containerRef.current.getBoundingClientRect();
      const bounds = imageBounds || { left: 0, top: 0, width: rect.width, height: rect.height };
      const relativeX = (event.clientX - rect.left - bounds.left) / Math.max(bounds.width, 1);
      const relativeY = (event.clientY - rect.top - bounds.top) / Math.max(bounds.height, 1);
      if (!Number.isFinite(relativeX) || !Number.isFinite(relativeY)) {
        return;
      }
      if (relativeX < 0 || relativeX > 1 || relativeY < 0 || relativeY > 1) {
        return;
      }
      console.debug("[placement] canvas-click", {
        source: "overlay",
        relativeX,
        relativeY,
      });
      onPlaceBuilding({ x: relativeX, y: relativeY });
    },
    [onPlaceBuilding, placementMode],
  );

  const clampValue = (value: number, min: number, max: number) =>
    Math.min(Math.max(value, min), max);

  const getEditCapabilities = (item: BuildingPlacement) => {
    const type = item.type ?? "building";
    const editableTypes = new Set([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "basin",
      "entrance",
      "driveway",
      "amenity",
      "open_space",
      "no_build_zone",
      "setback_zone",
      "parking",
      "road",
      "sidewalk",
    ]);
    const resizableTypes = new Set([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "basin",
      "amenity",
      "open_space",
      "no_build_zone",
      "setback_zone",
      "parking",
      "driveway",
    ]);
    const rotatableTypes = new Set([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "basin",
      "amenity",
      "open_space",
      "parking",
      "driveway",
    ]);
    const deletableTypes = new Set([...editableTypes].filter((t) => t !== "site"));
    const movable = editableTypes.has(type) && !item.locked;
    const resizable = resizableTypes.has(type) && !item.locked;
    const rotatable = rotatableTypes.has(type) && !item.locked;
    const deletable = deletableTypes.has(type) && !item.locked;
    return { movable, resizable, rotatable, deletable };
  };

  const snapValue = (value: number, step: number) => {
    if (!step) return value;
    return Math.round(value / step) * step;
  };

  const updateDraggedBuilding = useCallback(
    (event: React.MouseEvent<HTMLDivElement>, bounds: { left: number; top: number; width: number; height: number }) => {
      if (!draggingBuildingId || !draggingMode) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const localX = event.clientX - rect.left - bounds.left;
      const localY = event.clientY - rect.top - bounds.top;
      const target =
        buildingPlacements.find((item) => item.id === draggingBuildingId) ??
        suggestedPlacements.find((item) => item.id === draggingBuildingId);
      if (!target) return;
      const caps = getEditCapabilities(target);
      if (draggingMode === "move" && !caps.movable) return;
      if (draggingMode === "resize" && !caps.resizable) return;
      if (draggingMode === "rotate" && !caps.rotatable) return;
      if (draggingMode === "move") {
        const x = snapValue(
          clampValue(((localX - dragOffset.x) / Math.max(bounds.width, 1)) * lotWidth, 0, Math.max(lotWidth - target.w, 0)),
          5,
        );
        const y = snapValue(
          clampValue(((localY - dragOffset.y) / Math.max(bounds.height, 1)) * lotHeight, 0, Math.max(lotHeight - target.d, 0)),
          5,
        );
        if (target.source === "detected_from_image") {
          onUpdateSuggested(draggingBuildingId, { x, y, placed: true });
        } else {
          onUpdateBuilding(draggingBuildingId, { x, y, placed: true });
        }
        return;
      }
      if (draggingMode === "resize") {
        const rawW = clampValue((localX / Math.max(bounds.width, 1)) * lotWidth, 10, lotWidth);
        const rawD = clampValue((localY / Math.max(bounds.height, 1)) * lotHeight, 10, lotHeight);
        const nextW = Math.max(10, snapValue(rawW - (target.x ?? 0), 5));
        const nextD = Math.max(10, snapValue(rawD - (target.y ?? 0), 5));
        if (target.source === "detected_from_image") {
          onUpdateSuggested(draggingBuildingId, { w: nextW, d: nextD });
        } else {
          onUpdateBuilding(draggingBuildingId, { w: nextW, d: nextD });
        }
        return;
      }
      if (draggingMode === "rotate") {
        const centerX = bounds.left + ((target.x ?? 0) + target.w / 2) / Math.max(lotWidth, 1) * bounds.width;
        const centerY = bounds.top + ((target.y ?? 0) + target.d / 2) / Math.max(lotHeight, 1) * bounds.height;
        const angle = Math.atan2(localY + bounds.top - centerY, localX + bounds.left - centerX);
        const deg = (angle * 180) / Math.PI;
        const normalized = (deg + 360) % 360;
        const snapped = snapValue(normalized, 15);
        if (target.source === "detected_from_image") {
          onUpdateSuggested(draggingBuildingId, { rotation: snapped });
        } else {
          onUpdateBuilding(draggingBuildingId, { rotation: snapped });
        }
      }
    },
    [
      buildingPlacements,
      suggestedPlacements,
      dragOffset.x,
      dragOffset.y,
      draggingBuildingId,
      draggingMode,
      lotHeight,
      lotWidth,
      onUpdateBuilding,
      onUpdateSuggested,
      placementMode,
    ],
  );

  const handleBuildingMouseDown = useCallback(
    (
      event: React.MouseEvent<HTMLElement>,
      building: BuildingPlacement,
      mode: "move" | "resize" | "rotate" = "move",
    ) => {
      const caps = getEditCapabilities(building);
      if (mode === "move" && !caps.movable) return;
      if (mode === "resize" && !caps.resizable) return;
      if (mode === "rotate" && !caps.rotatable) return;
      event.preventDefault();
      event.stopPropagation();
      setDraggingBuildingId(building.id);
      setDraggingMode(mode);
      onSelectBuilding(building.id);
      const rect = event.currentTarget.getBoundingClientRect();
      setDragOffset({ x: event.clientX - rect.left, y: event.clientY - rect.top });
    },
    [getEditCapabilities, onSelectBuilding],
  );

  const formatHoverValue = (value: number | null | undefined, suffix: string) => {
    if (value === null || value === undefined || Number.isNaN(value)) return null;
    return `${value.toFixed(2)}${suffix}`;
  };
  const hoverDetails = useMemo(() => {
    if (!activeAnnotation?.meta) return [];
    const meta = activeAnnotation.meta;
    const sourceLabel = meta.preview_role
      ? meta.preview_role === "final"
        ? "Final geometry"
        : meta.preview_role === "overlay"
          ? "Overlay"
          : "Debug"
      : "Unknown";
    const inferredLabel = meta.inferred ? "Inferred" : "";
    const entries = [
      { label: "Entity ID", value: meta.entity_id },
      { label: "System", value: meta.system },
      { label: "Layer", value: activeAnnotation.layer },
      { label: "Type", value: meta.entity_type },
      { label: "Source", value: inferredLabel ? `${sourceLabel} (${inferredLabel})` : sourceLabel },
      { label: "Length", value: formatHoverValue(meta.length_ft ?? null, " ft") },
      { label: "Width", value: formatHoverValue(meta.width_ft ?? null, " ft") },
      { label: "Height", value: formatHoverValue(meta.height_ft ?? null, " ft") },
      { label: "Area", value: formatHoverValue(meta.area_sf ?? null, " sf") },
      { label: "Slope", value: formatHoverValue(meta.slope_pct ?? null, "%") },
      { label: "Diameter", value: formatHoverValue(meta.diameter_in ?? null, " in") },
      { label: "Flow", value: formatHoverValue(meta.flow_cfs ?? null, " cfs") },
      { label: "Elevation", value: formatHoverValue(meta.elevation_ft ?? null, " ft") },
      { label: "Invert Start", value: formatHoverValue(meta.invert_start_ft ?? null, " ft") },
      { label: "Invert End", value: formatHoverValue(meta.invert_end_ft ?? null, " ft") },
    ];
    return entries.filter((entry) => entry.value);
  }, [activeAnnotation, formatHoverValue]);
  const objectHoverDetails = useMemo(() => {
    if (!hoveredObject) return [];
    const type = hoveredObject.type ?? "building";
    const dims = `${hoveredObject.w.toFixed(1)} ft x ${hoveredObject.d.toFixed(1)} ft`;
    const height =
      typeof hoveredObject.h === "number" && Number.isFinite(hoveredObject.h)
        ? `${hoveredObject.h.toFixed(1)} ft`
        : null;
    const source = hoveredObject.generated ? "generated" : hoveredObject.source || "user";
    const confidence =
      typeof hoveredObject.confidence === "number"
        ? `${Math.round(hoveredObject.confidence * 100)}%`
        : null;
    const position =
      typeof hoveredObject.x === "number" && typeof hoveredObject.y === "number"
        ? `X ${hoveredObject.x.toFixed(1)} ft • Y ${hoveredObject.y.toFixed(1)} ft`
        : null;
    const positionRelative =
      position && lotWidth > 0 && lotHeight > 0
        ? `(${((hoveredObject.x ?? 0) / lotWidth * 100).toFixed(1)}%, ${(
            (hoveredObject.y ?? 0) /
            lotHeight *
            100
          ).toFixed(1)}%)`
        : null;
    return [
      { label: "Type", value: type },
      { label: "ID", value: hoveredObject.id },
      { label: "Dimensions", value: dims },
      ...(position
        ? [
            {
              label: "Position",
              value: positionRelative ? `${position} ${positionRelative}` : position,
            },
          ]
        : []),
      ...(height ? [{ label: "Height", value: height }] : []),
      { label: "Source", value: source },
      ...(confidence ? [{ label: "Confidence", value: confidence }] : []),
    ];
  }, [hoveredObject]);
  const overlayBounds = previewContainerBounds;

  useEffect(() => {
    if (!showMap) return;
    if (!mapContainerRef.current || mapRef.current) return;
    mapboxgl.accessToken = mapboxToken || "";
    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/satellite-streets-v12",
      center: [-95.9345, 41.2565],
      zoom: 16,
      attributionControl: false,
    });
    mapRef.current.on("load", () => {
      mapRef.current?.addSource("mapbox-dem", {
        type: "raster-dem",
        url: "mapbox://mapbox.terrain-rgb",
        tileSize: 512,
        maxzoom: 14,
      });
      mapRef.current?.setTerrain({ source: "mapbox-dem", exaggeration: 1.0 });
      setMapLoaded(true);
      setMapRevision((value) => value + 1);
    });
  }, [mapboxToken, showMap]);

  useEffect(() => {
    if (!showMap || !mapLoaded || !mapRef.current) return;
    const map = mapRef.current;
    const reportScale = () => {
      if (!onMapScaleUpdate) return;
      const center = map.getCenter();
      const zoom = map.getZoom();
      const metersPerPixel = 156543.03392 * Math.cos((center.lat * Math.PI) / 180) / Math.pow(2, zoom);
      const ftPerPx = metersPerPixel * 3.28084;
      if (Number.isFinite(ftPerPx)) {
        onMapScaleUpdate({ ftPerPx, source: "mapbox" });
      }
    };
    reportScale();
    map.on("moveend", reportScale);
    map.on("zoomend", reportScale);
    const handleClick = (event: mapboxgl.MapMouseEvent) => {
      if (placementMode) {
        const container = map.getContainer();
        const rect = container.getBoundingClientRect();
        const relativeX = event.point.x / Math.max(rect.width, 1);
        const relativeY = event.point.y / Math.max(rect.height, 1);
        console.debug("[placement] map-click", {
          relativeX,
          relativeY,
          activeId: selectedBuildingId ?? null,
        });
        if (selectedBuildingId) {
          onPlaceObject(selectedBuildingId, { x: relativeX, y: relativeY });
        } else {
          onPlaceBuilding({ x: relativeX, y: relativeY });
        }
        return;
      }
      const features = map.queryRenderedFeatures(event.point, {
        layers: [
          "civora-buildings-fill",
          "civora-parking-fill",
          "civora-basins-fill",
          "civora-roads-line",
        ],
      });
      const hit = features?.[0];
      const id = hit?.properties?.id;
      if (typeof id === "string") {
        onSelectBuilding(id);
      }
    };
    map.on("click", handleClick);
    return () => {
      map.off("click", handleClick);
      map.off("moveend", reportScale);
      map.off("zoomend", reportScale);
    };
  }, [mapLoaded, onMapScaleUpdate, onPlaceBuilding, onPlaceObject, placementMode, selectedBuildingId, onSelectBuilding, showMap]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "r") {
        setRotateDragActive(true);
      }
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "r") {
        setRotateDragActive(false);
        setRotateDragStart(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  useEffect(() => {
    if (!showMap || !previewFullscreenOpen) return;
    if (!fullscreenMapContainerRef.current || fullscreenMapRef.current) return;
    mapboxgl.accessToken = mapboxToken || "";
    fullscreenMapRef.current = new mapboxgl.Map({
      container: fullscreenMapContainerRef.current,
      style: "mapbox://styles/mapbox/satellite-streets-v12",
      center: [-95.9345, 41.2565],
      zoom: 16,
      attributionControl: false,
    });
    fullscreenMapRef.current.on("load", () => {
      fullscreenMapRef.current?.addSource("mapbox-dem", {
        type: "raster-dem",
        url: "mapbox://mapbox.terrain-rgb",
        tileSize: 512,
        maxzoom: 14,
      });
      fullscreenMapRef.current?.setTerrain({ source: "mapbox-dem", exaggeration: 1.0 });
      fullscreenMapRef.current?.resize();
      setMapRevision((value) => value + 1);
    });
  }, [mapboxToken, previewFullscreenOpen, showMap]);

  useEffect(() => {
    if (!showMap) return;
    if (!geocode?.lng || !geocode?.lat) return;
    const center: [number, number] = [geocode.lng, geocode.lat];
    mapRef.current?.flyTo({ center, zoom: 17 });
    fullscreenMapRef.current?.flyTo({ center, zoom: 17 });
  }, [geocode?.lat, geocode?.lng, showMap]);

  const convertSiteToLngLat = useCallback(
    (xFt: number, yFt: number) => {
      if (!geocode?.lat || !geocode?.lng) return null;
      const metersPerDegLat = 111320;
      const metersPerDegLng = 111320 * Math.cos((geocode.lat * Math.PI) / 180);
      const dxFt = xFt - lotWidth / 2;
      const dyFt = lotHeight / 2 - yFt;
      const rotationDeg = typeof siteRotationDeg === "number" ? siteRotationDeg : 0;
      const theta = (rotationDeg * Math.PI) / 180;
      const dxRot = dxFt * Math.cos(theta) - dyFt * Math.sin(theta);
      const dyRot = dxFt * Math.sin(theta) + dyFt * Math.cos(theta);
      const dxM = dxRot * 0.3048;
      const dyM = dyRot * 0.3048;
      const lng = geocode.lng + dxM / metersPerDegLng;
      const lat = geocode.lat + dyM / metersPerDegLat;
      return [lng, lat] as [number, number];
    },
    [geocode?.lat, geocode?.lng, lotHeight, lotWidth, siteRotationDeg],
  );

  useEffect(() => {
    if (!showMap || !mapLoaded || !mapRef.current || !geocode?.lat || !geocode?.lng) return;
    if (!fitToSiteRequest || !lotWidth || !lotHeight) return;
    const corners = [
      convertSiteToLngLat(0, 0),
      convertSiteToLngLat(lotWidth, 0),
      convertSiteToLngLat(lotWidth, lotHeight),
      convertSiteToLngLat(0, lotHeight),
    ].filter(Boolean) as Array<[number, number]>;
    if (corners.length < 4) return;
    const bounds = corners.reduce(
      (acc, coord) => acc.extend(coord),
      new mapboxgl.LngLatBounds(corners[0], corners[0]),
    );
    mapRef.current.fitBounds(bounds, { padding: 80, duration: 650 });
  }, [convertSiteToLngLat, fitToSiteRequest, geocode?.lat, geocode?.lng, lotHeight, lotWidth, mapLoaded, showMap]);

  useEffect(() => {
    if (!showMap || !mapLoaded || !mapRef.current) return;
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
  }, [alignToRoadRequest, mapLoaded, onSetSiteRotationDeg, showMap]);

  useEffect(() => {
    if (!showMap || !mapLoaded || !mapRef.current) return;
    if (!geocode?.lat || !geocode?.lng || !lotWidth || !lotHeight) return;

    const placedObjects = buildingPlacements.filter(
      (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
    );

    const buildPolygon = (item: BuildingPlacement) => {
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
        .map((pt) => convertSiteToLngLat(pt[0], pt[1]))
        .filter(Boolean) as Array<[number, number]>;
      return coords.length === corners.length ? coords : null;
    };

    const buildLine = (item: BuildingPlacement) => {
      const coords = buildPolygon(item);
      if (!coords) return null;
      return coords;
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
        .map((pt) => convertSiteToLngLat(pt[0], pt[1]))
        .filter(Boolean) as Array<[number, number]>;
      return coords.length === corners.length ? coords : null;
    };

    const toFeatureCollection = (items: BuildingPlacement[], geometry: "Polygon" | "LineString") => ({
      type: "FeatureCollection",
      features: items
        .map((item) => {
          const coords = geometry === "LineString" ? buildLine(item) : buildPolygon(item);
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
              label: item.label || item.name || item.type || "object",
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
          const coords = convertSiteToLngLat(pt.x, pt.y);
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

    const buildings = placedObjects.filter((item) => !item.type || item.type === "building");
    const roads = placedObjects.filter((item) => item.type === "road" || item.type === "driveway");
    const parking = placedObjects.filter((item) => item.type === "parking");
    const basins = placedObjects.filter((item) => item.type === "basin");
    const sitePolygon = buildSitePolygon();

    const updateMap = (map: mapboxgl.Map | null) => {
      if (!map || !map.isStyleLoaded()) return;
      const ensureSource = (id: string, data: any) => {
        if (!map.getSource(id)) {
          map.addSource(id, { type: "geojson", data });
        } else {
          (map.getSource(id) as mapboxgl.GeoJSONSource).setData(data);
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
      ensureSource("civora-parking", toFeatureCollection(parking, "Polygon"));
      ensureSource("civora-basins", toFeatureCollection(basins, "Polygon"));
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
      if (geocode?.lat && geocode?.lng) {
        ensureSource("civora-center", {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: { type: "Point", coordinates: [geocode.lng, geocode.lat] },
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
        "fill-extrusion-opacity": 0.6,
      });
      ensureLayer("civora-buildings-line", "civora-buildings", "line", {
        "line-color": "#111827",
        "line-width": 2,
      });
      ensureLayer("civora-roads-line", "civora-roads", "line", {
        "line-color": "#1f2937",
        "line-width": 3,
      });
      ensureLayer("civora-parking-fill", "civora-parking", "fill", {
        "fill-color": "#64748b",
        "fill-opacity": 0.35,
      });
      ensureLayer("civora-basins-fill", "civora-basins", "fill", {
        "fill-color": "#0ea5e9",
        "fill-opacity": 0.28,
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
      if (geocode?.lat && geocode?.lng) {
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
    };

    updateMap(mapRef.current);
    updateMap(fullscreenMapRef.current);
  }, [
    buildingPlacements,
    convertSiteToLngLat,
    geocode?.lat,
    geocode?.lng,
    lotHeight,
    lotWidth,
    mapLoaded,
    mapRevision,
    showMap,
    showSiteBounds,
    surveyPoints,
  ]);

  useEffect(() => {
    const handleUpdate = () => {
      updateContainerBounds();
      if (showMap) {
        if (previewRef.current) {
          const rect = previewRef.current.getBoundingClientRect();
          setPreviewImageBounds({ left: 0, top: 0, width: rect.width, height: rect.height });
        }
        mapRef.current?.resize();
        fullscreenMapRef.current?.resize();
      } else if (planPreviewUrl && showGeneratedPlan) {
        updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds);
      } else {
        setPreviewImageBounds(null);
      }
    };
    handleUpdate();
    if (!previewRef.current) return;
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleUpdate) : null;
    if (observer) observer.observe(previewRef.current);
    window.addEventListener("resize", handleUpdate);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener("resize", handleUpdate);
    };
  }, [planPreviewUrl, previewMode, showGeneratedPlan, showMap, updateContainerBounds, updateImageBounds]);

  useEffect(() => {
    if (!previewFullscreenOpen) return;
    const handleUpdate = () => {
      if (showMap) {
        if (fullscreenRef.current) {
          const rect = fullscreenRef.current.getBoundingClientRect();
          setFullscreenImageBounds({ left: 0, top: 0, width: rect.width, height: rect.height });
        }
        fullscreenMapRef.current?.resize();
      } else if (planPreviewUrl) {
        updateImageBounds(fullscreenRef, fullscreenImageRef, setFullscreenImageBounds);
      }
    };
    handleUpdate();
    if (!fullscreenRef.current) return;
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleUpdate) : null;
    if (observer) observer.observe(fullscreenRef.current);
    window.addEventListener("resize", handleUpdate);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener("resize", handleUpdate);
    };
  }, [planPreviewUrl, previewFullscreenOpen, showMap, updateImageBounds]);
  const [focusTransform, setFocusTransform] = useState<{ scale: number; tx: number; ty: number } | null>(null);

  useEffect(() => {
    if (!focusDetectedId) return;
    const target = suggestedPlacements.find((item) => item.id === focusDetectedId);
    if (target) {
      setHoveredObjectId(target.id);
      onSelectBuilding(target.id);
    }
    if (onClearFocusDetected) {
      const timer = window.setTimeout(() => onClearFocusDetected(), 400);
      return () => window.clearTimeout(timer);
    }
  }, [focusDetectedId, onClearFocusDetected, onSelectBuilding, suggestedPlacements]);

  useEffect(() => {
    if (!focusObjectId) return;
    const target = buildingPlacements.find((item) => item.id === focusObjectId);
    if (!target || !lotWidth || !lotHeight) return;
    const minX = target.x ?? 0;
    const minY = target.y ?? 0;
    const maxX = minX + target.w;
    const maxY = minY + target.d;
    const padding = 0.15;
    const boxW = Math.max((maxX - minX) / lotWidth, 0.02);
    const boxH = Math.max((maxY - minY) / lotHeight, 0.02);
    const scale = Math.min(1 / (boxW + padding), 1 / (boxH + padding));
    const centerX = (minX + maxX) / 2 / lotWidth;
    const centerY = (minY + maxY) / 2 / lotHeight;
    setFocusTransform({ scale: Math.min(Math.max(scale, 1), 3), tx: centerX, ty: centerY });
    if (onClearFocusObject) {
      const timer = window.setTimeout(() => onClearFocusObject(), 500);
      return () => window.clearTimeout(timer);
    }
  }, [focusObjectId, buildingPlacements, lotHeight, lotWidth, onClearFocusObject]);

  useEffect(() => {
    if (!analysisHighlight || !lotWidth || !lotHeight) return;
    const focusItems = [...buildingPlacements, ...suggestedPlacements].filter(
      (item) => item.id === analysisHighlight.buildingId || item.id === analysisHighlight.accessId,
    );
    if (!focusItems.length) return;
    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    focusItems.forEach((item) => {
      const x = item.x ?? 0;
      const y = item.y ?? 0;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + item.w);
      maxY = Math.max(maxY, y + item.d);
    });
    const path = analysisPaths?.find((p) => p.id === analysisHighlight.pathId);
    if (path) {
      minX = Math.min(minX, path.from.x, path.to.x);
      minY = Math.min(minY, path.from.y, path.to.y);
      maxX = Math.max(maxX, path.from.x, path.to.x);
      maxY = Math.max(maxY, path.from.y, path.to.y);
    }
    if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) return;
    const padding = 0.1;
    const boxW = Math.max((maxX - minX) / lotWidth, 0.02);
    const boxH = Math.max((maxY - minY) / lotHeight, 0.02);
    const scale = Math.min(1 / (boxW + padding), 1 / (boxH + padding));
    const centerX = (minX + maxX) / 2 / lotWidth;
    const centerY = (minY + maxY) / 2 / lotHeight;
    setFocusTransform({ scale: Math.min(Math.max(scale, 1), 3), tx: centerX, ty: centerY });
  }, [analysisHighlight, analysisPaths, buildingPlacements, lotHeight, lotWidth, suggestedPlacements]);
  return (
    <div className="flex h-full flex-col rounded-[28px] border border-slate-200 bg-white/90 p-4 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.4)] backdrop-blur md:p-6">
      <div className="mb-4 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600">
              Preview Workspace
            </span>
          </div>
          <p className="text-sm font-semibold text-slate-950">Live Preview</p>
          <p className="mt-1 text-sm text-slate-500">
            The preview shows the latest engineered plan even when final export is still under review.
          </p>
          {previewTotalPhaseCount > 0 && previewCompletedPhaseCount < previewTotalPhaseCount ? (
            <div className="inline-flex max-w-3xl items-start rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <div>
                <p className="font-semibold">Preview shows completed phases only.</p>
                <p className="mt-1 text-xs">
                  {previewRunningPhase
                    ? `${previewRunningPhase.label} is the current active phase. Systems like drainage, storm, and utilities appear after their phases finish.`
                    : previewNextPendingPhase
                      ? `${previewNextPendingPhase.label} is still pending. Systems like drainage, storm, and utilities appear after their phases finish.`
                      : "Additional systems appear as later phases complete."}
                </p>
              </div>
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {analysisHighlight ? (
            <button
              type="button"
              onClick={() => {
                setFocusTransform(null);
                onClearHighlights?.();
              }}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              Clear highlights
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => {
              setFocusTransform(null);
              onResetView?.();
            }}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            Reset view
          </button>
          <button
            type="button"
            onClick={onRefreshPreview}
            disabled={busy}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Refresh Preview
          </button>
          {planPreviewUrl || showMap ? (
            <button
              type="button"
              onClick={onOpenFullscreen}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              <Maximize2 className="h-4 w-4" />
              Fullscreen Preview
            </button>
          ) : null}
          <button
            type="button"
            onClick={onExportDxf}
            disabled={busy}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Export DXF
          </button>
          <button
            type="button"
            onClick={onExportReport}
            disabled={busy}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Export Report
          </button>
        </div>
      </div>

      <div className="flex flex-col rounded-[28px] border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Preview Mode</span>
              <button
                type="button"
                onClick={() => onSetPreviewMode("2d")}
                className={`rounded-full border px-2.5 py-1 ${
                  previewMode === "2d"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                2D
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!planPreviewUrl) return;
                  onSetPreviewMode("3d");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewMode === "3d"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
                disabled={!planPreviewUrl}
              >
                3D
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Interaction</span>
              <button
                type="button"
                onClick={() => onSetPreviewInteraction("static")}
                className={`rounded-full border px-2.5 py-1 ${
                  previewInteraction === "static"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Static
              </button>
              <button
                type="button"
                onClick={() => {
                  if (previewInteraction === "interactive") return;
                  onQueuePreviewRefresh("Loading interactive labels...");
                  onSetPreviewInteraction("interactive");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewInteraction === "interactive"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Interactive
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Quality</span>
              <button
                type="button"
                onClick={() => {
                  if (previewQuality === "standard") return;
                  onQueuePreviewRefresh("Requesting standard-quality preview...");
                  onSetPreviewQuality("standard");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewQuality === "standard"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Standard
              </button>
              <button
                type="button"
                onClick={() => {
                  if (previewQuality === "high") return;
                  onQueuePreviewRefresh("Requesting high-quality preview...");
                  onSetPreviewQuality("high");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewQuality === "high"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                High
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Labels</span>
              {(["low", "standard", "high"] as const).map((density) => (
                <button
                  key={density}
                  type="button"
                  onClick={() => {
                    if (previewLabelDensity === density) return;
                    onQueuePreviewRefresh("Updating label density...");
                    onSetPreviewLabelDensity(density);
                  }}
                  className={`rounded-full border px-2.5 py-1 ${
                    previewLabelDensity === density
                      ? "border-slate-900 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  {density === "standard" ? "Standard" : density.charAt(0).toUpperCase() + density.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
            <span className="font-semibold text-slate-900">Quality:</span>
            <span>{previewQuality === "high" ? "High" : "Standard"}</span>
            <span className="font-semibold text-slate-900">Labels:</span>
            <span>
              {previewLabelDensity === "standard"
                ? "Standard"
                : previewLabelDensity.charAt(0).toUpperCase() + previewLabelDensity.slice(1)}
            </span>
            <span className="font-semibold text-slate-900">Interactive:</span>
            <span>{previewInteraction === "interactive" ? "Hover enabled" : "Static"}</span>
          </div>
          {(previewRefreshing || previewRefreshNote) && (
            <div className="mb-4 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              <span>{previewRefreshNote || "Refreshing preview..."}</span>
            </div>
          )}
          {show3D ? (
            preview3DEffectiveItems.length ? (
              <div className="relative">
                <Preview3DCanvas
                  items={preview3DEffectiveItems}
                  interactive={previewInteraction === "interactive"}
                  onOpenFullscreen={onOpenFullscreen}
                />
                {usingAnnotation3D ? (
                  <div
                    className={`pointer-events-none absolute left-4 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm ${
                      "top-4"
                    }`}
                  >
                    Approximate 3D
                  </div>
                ) : null}
                {!hasGradingSurface ? (
                  <div
                    className={`pointer-events-none absolute right-4 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm ${
                      usingAnnotation3D ? "top-14" : "top-4"
                    }`}
                  >
                    Grading surface missing
                  </div>
                ) : null}
                <button
                  type="button"
                  onClick={onOpenFullscreen}
                  className="absolute bottom-4 right-4 rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm transition hover:bg-slate-900"
                >
                  Open Fullscreen
                </button>
              </div>
            ) : (
              <div className="relative flex items-center justify-center overflow-hidden rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)] min-h-[520px] h-[clamp(520px,70vh,820px)]">
                <div className="pointer-events-none absolute left-6 top-6 rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 shadow-sm">
                  3D geometry not ready yet
                </div>
              </div>
            )
          ) : (
            <div
              ref={previewRef}
              className={`relative flex items-center justify-center rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)] min-h-[520px] h-[clamp(520px,70vh,820px)] ${
                previewInteraction === "interactive" ? "cursor-crosshair" : "cursor-default"
              }`}
              onDragOver={(event) => {
                event.preventDefault();
              }}
              onDrop={(event) => {
                event.preventDefault();
                const payload = event.dataTransfer?.getData("civora-object-id");
                if (!payload) return;
                const rect = previewRef.current?.getBoundingClientRect();
                const bounds = overlayBounds ?? {
                  left: 0,
                  top: 0,
                  width: rect?.width ?? 1,
                  height: rect?.height ?? 1,
                };
                onPlaceObject(payload, {
                  x: Math.min(
                    Math.max((event.clientX - (rect?.left ?? 0) - bounds.left) / Math.max(bounds.width, 1), 0),
                    1,
                  ),
                  y: Math.min(
                    Math.max((event.clientY - (rect?.top ?? 0) - bounds.top) / Math.max(bounds.height, 1), 0),
                    1,
                  ),
                });
              }}
              onMouseMove={(event) => {
                if (rotateDragStart && previewContainerBounds && onSetSiteRotationDeg) {
                  const deltaX = event.clientX - rotateDragStart.x;
                  const width = Math.max(previewContainerBounds.width, 1);
                  const deltaDeg = (deltaX / width) * 180;
                  const nextValue = rotateDragStart.value + deltaDeg;
                  onSetSiteRotationDeg(Math.max(-180, Math.min(180, nextValue)));
                  return;
                }
                if (overlayBounds) {
                  updateDraggedBuilding(event, overlayBounds);
                }
                resolveHover(event, previewRef, overlayBounds, setHoverPoint);
              }}
              onMouseLeave={() => {
                setHoveredAnnotation(null);
                setHoveredObjectId(null);
                setHoverPoint(null);
                setDraggingBuildingId(null);
                setDraggingMode(null);
              }}
              onMouseUp={() => {
                setDraggingBuildingId(null);
                setDraggingMode(null);
                setRotateDragStart(null);
              }}
              onClick={(event) => {
                if (placementMode) {
                  resolvePlacement(event, previewRef, overlayBounds);
                  return;
                }
                if (!showInteractive || !hoveredAnnotation) return;
                setPinnedAnnotation((prev) =>
                  prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
                );
              }}
            >
              <div
                className="relative flex h-full w-full items-center justify-center overflow-hidden"
                onMouseDown={(event) => {
                  if (rotateDragActive && onSetSiteRotationDeg) {
                    event.preventDefault();
                    event.stopPropagation();
                    setRotateDragStart({
                      x: event.clientX,
                      value: typeof siteRotationDeg === "number" ? siteRotationDeg : 0,
                    });
                  }
                }}
              >
                {showMap ? (
                  <div ref={mapContainerRef} className="absolute inset-0 overflow-hidden rounded-[24px]" />
                ) : null}
                {showMap ? (
                  <div className="pointer-events-none absolute right-5 top-5 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
                    N ↑ {typeof siteRotationDeg === "number" ? `${siteRotationDeg.toFixed(1)}°` : "0°"}
                  </div>
                ) : null}
                {showGeneratedPlan && planPreviewUrl && !showMap ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    ref={previewImageRef}
                    src={planPreviewUrl}
                    alt="Generated plan preview"
                  className={`h-full w-full object-contain ${
                      previewInteraction === "interactive" ? "cursor-crosshair" : "cursor-default"
                    }`}
                    onLoad={() => updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds)}
                    onClick={onOpenFullscreen}
                  />
                ) : !showMap ? (
                  <div className="flex h-full w-full items-center justify-center text-sm text-slate-400">
                    Add objects to start building the site. Then click Place and drop them here.
                  </div>
                ) : null}
                {!showGeneratedPlan && previewMode === "3d" ? (
                  <div className="pointer-events-none absolute left-6 top-6 rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm">
                    3D needs a preview run
                  </div>
                ) : null}
                {overlayBounds && (previewMode === "2d" || !showGeneratedPlan) ? (
                  <div
                    className="pointer-events-none absolute"
                    style={{
                      left: overlayBounds.left,
                      top: overlayBounds.top,
                      width: overlayBounds.width,
                      height: overlayBounds.height,
                    }}
                  >
                    {lotWidth > 0 && lotHeight > 0 ? (
                      <div className="absolute inset-0 rounded-[16px] border-2 border-dashed border-slate-300/70" />
                    ) : null}
                    {(buildingPlacements.length || suggestedPlacements.length || (surveyPoints?.length ?? 0) > 0) ? (
                      <svg
                        className="absolute inset-0"
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                      >
                        {[...buildingPlacements, ...suggestedPlacements]
                          .filter((item) => item.geometryType && Array.isArray(item.geometry))
                          .map((item) => {
                            const points = (item.geometry || []).map((pt) => {
                              const x = (pt[0] / Math.max(lotWidth, 1)) * 100;
                              const y = (pt[1] / Math.max(lotHeight, 1)) * 100;
                              return `${x},${y}`;
                            });
                            if (!points.length) return null;
                            const isLine = item.geometryType === "polyline";
                            const stroke =
                              item.source === "detected_from_image"
                                ? "#f59e0b"
                                : item.type === "road"
                                  ? "#2563eb"
                                  : "#0f172a";
                            const fill =
                              item.source === "detected_from_image"
                                ? "rgba(245, 158, 11, 0.15)"
                                : "rgba(15, 23, 42, 0.12)";
                            return isLine ? (
                              <polyline
                                key={`geom-${item.id}`}
                                points={points.join(" ")}
                                fill="none"
                                stroke={stroke}
                                strokeWidth={0.8}
                                strokeDasharray={item.source === "detected_from_image" ? "2 2" : undefined}
                              />
                            ) : (
                              <polygon
                                key={`geom-${item.id}`}
                                points={points.join(" ")}
                                fill={fill}
                                stroke={stroke}
                                strokeWidth={0.8}
                                strokeDasharray={item.source === "detected_from_image" ? "2 2" : undefined}
                              />
                            );
                          })}
                        {(surveyPoints ?? []).length
                          ? (surveyPoints ?? []).slice(0, 1500).map((pt, idx) => {
                              const x = (pt.x / Math.max(lotWidth, 1)) * 100;
                              const y = (pt.y / Math.max(lotHeight, 1)) * 100;
                              return (
                                <circle
                                  key={`survey-${idx}`}
                                  cx={x}
                                  cy={y}
                                  r={0.35}
                                  fill="#7c3aed"
                                  opacity={0.65}
                                />
                              );
                            })
                          : null}
                      </svg>
                    ) : null}
                    <div
                      className="pointer-events-auto absolute inset-0"
                      style={{
                        transformOrigin: "top left",
                        transform: focusTransform
                          ? `translate(50%, 50%) scale(${focusTransform.scale}) translate(-${focusTransform.tx * 100}%, -${focusTransform.ty * 100}%)`
                          : undefined,
                      }}
                      onClick={() => {
                        if (analysisFocusLocked) return;
                        onClearHighlights?.();
                      }}
                    >
                      {buildingPlacements
                      .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                      .map((item) => {
                        const caps = getEditCapabilities(item);
                        const isSelected = selectedBuildingId === item.id;
                        const left = ((item.x || 0) / Math.max(lotWidth, 1)) * 100;
                        const top = ((item.y || 0) / Math.max(lotHeight, 1)) * 100;
                        const rotated = (item.rotation ?? 0) % 180 !== 0;
                        const displayW = rotated ? item.d : item.w;
                        const displayD = rotated ? item.w : item.d;
                        const width = (displayW / Math.max(lotWidth, 1)) * 100;
                        const height = (displayD / Math.max(lotHeight, 1)) * 100;
                        const rotation = item.rotation ?? 0;
                        const borderColorMap: Record<string, string> = {
                          site: "border-slate-400",
                          setback_zone: "border-slate-300",
                          no_build_zone: "border-rose-400",
                          basin: "border-emerald-500",
                          entrance: "border-amber-500",
                          driveway: "border-orange-400",
                          road: "border-blue-500",
                          parking: "border-violet-500",
                          sidewalk: "border-teal-500",
                          pool: "border-cyan-500",
                          pad: "border-stone-400",
                        };
                        const borderColor =
                          (item.type && borderColorMap[item.type]) || "border-slate-900/70";
                        const isAccessHighlight =
                          analysisHighlight &&
                          (analysisHighlight.buildingId === item.id || analysisHighlight.accessId === item.id);
                        return (
                          <div
                            key={item.id}
                            className="pointer-events-auto absolute"
                            style={{
                              left: `${left}%`,
                              top: `${top}%`,
                              width: `${width}%`,
                              height: `${height}%`,
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: caps.movable ? "move" : "default",
                            }}
                            onMouseDown={(event) => handleBuildingMouseDown(event, item, "move")}
                            onMouseEnter={() => setHoveredObjectId(item.id)}
                            onMouseLeave={() => setHoveredObjectId(null)}
                            onClick={(event) => {
                              event.stopPropagation();
                              onSelectBuilding(item.id);
                            }}
                          >
                            <div
                              className={`h-full w-full rounded-[8px] border-2 bg-slate-900/15 shadow-sm transition ${borderColor} ${
                                isSelected ? "ring-2 ring-amber-300" : ""
                              } ${isAccessHighlight ? "ring-2 ring-rose-300" : ""}`}
                            />
                            {isSelected && caps.rotatable ? (
                              <button
                                type="button"
                                className="absolute -right-3 -top-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                                onMouseDown={(event) => handleBuildingMouseDown(event, item, "rotate")}
                              >
                                R
                              </button>
                            ) : null}
                            {isSelected && caps.resizable ? (
                              <button
                                type="button"
                                className="absolute -right-3 -bottom-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                                onMouseDown={(event) => handleBuildingMouseDown(event, item, "resize")}
                              >
                                Z
                              </button>
                            ) : null}
                            {isSelected && caps.deletable ? (
                              <button
                                type="button"
                                className="absolute -left-3 -top-3 h-6 w-6 rounded-full border border-rose-200 bg-white text-[10px] font-semibold text-rose-600 shadow"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onRemoveBuilding(item.id);
                                }}
                              >
                                ×
                              </button>
                            ) : null}
                            {isSelected && caps.movable ? (
                              <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
                                Snap 5ft
                              </div>
                            ) : null}
                            <div className="absolute -top-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600 shadow">
                              {item.label}
                            </div>
                            {hoveredObjectId === item.id && objectHoverDetails.length ? (
                              <div className="absolute left-1/2 top-full z-10 mt-3 w-48 -translate-x-1/2 rounded-2xl border border-slate-200 bg-white p-3 text-[11px] text-slate-600 shadow">
                                <div className="space-y-1">
                                  {objectHoverDetails.map((detail) => (
                                    <div
                                      key={detail.label}
                                      className="flex items-center justify-between gap-2"
                                    >
                                      <span className="text-slate-500">{detail.label}</span>
                                      <span className="font-semibold text-slate-900">{detail.value}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                      {suggestedPlacements
                      .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                      .map((item) => {
                        const left = ((item.x || 0) / Math.max(lotWidth, 1)) * 100;
                        const top = ((item.y || 0) / Math.max(lotHeight, 1)) * 100;
                        const rotated = (item.rotation ?? 0) % 180 !== 0;
                        const displayW = rotated ? item.d : item.w;
                        const displayD = rotated ? item.w : item.d;
                        const width = (displayW / Math.max(lotWidth, 1)) * 100;
                        const height = (displayD / Math.max(lotHeight, 1)) * 100;
                        const rotation = item.rotation ?? 0;
                        return (
                          <div
                            key={item.id}
                            className="pointer-events-auto absolute"
                            style={{
                              left: `${left}%`,
                              top: `${top}%`,
                              width: `${width}%`,
                              height: `${height}%`,
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: "move",
                            }}
                            onMouseDown={(event) => handleBuildingMouseDown(event, item, "move")}
                            onMouseEnter={() => setHoveredObjectId(item.id)}
                            onMouseLeave={() => setHoveredObjectId(null)}
                          >
                            <div className="h-full w-full rounded-[8px] border-2 border-dashed border-amber-400 bg-amber-200/10" />
                            <div className="absolute -top-6 left-1/2 -translate-x-1/2 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 shadow">
                              {item.label}
                            </div>
                            {hoveredObjectId === item.id && objectHoverDetails.length ? (
                              <div className="absolute left-1/2 top-full z-10 mt-3 w-48 -translate-x-1/2 rounded-2xl border border-slate-200 bg-white p-3 text-[11px] text-slate-600 shadow">
                                <div className="space-y-1">
                                  {objectHoverDetails.map((detail) => (
                                    <div
                                      key={detail.label}
                                      className="flex items-center justify-between gap-2"
                                    >
                                      <span className="text-slate-500">{detail.label}</span>
                                      <span className="font-semibold text-slate-900">{detail.value}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                      {analysisPaths && analysisPaths.length ? (
                      <svg className="absolute inset-0" viewBox="0 0 100 100" preserveAspectRatio="none">
                        {analysisPaths.map((path) => {
                          const isSelected = analysisHighlight?.pathId === path.id;
                          const points = path.points?.length
                            ? path.points
                            : [path.from, path.to];
                          const coords = points
                            .map((pt) => {
                              const x = (pt.x / Math.max(lotWidth, 1)) * 100;
                              const y = (pt.y / Math.max(lotHeight, 1)) * 100;
                              return `${x},${y}`;
                            })
                            .join(" ");
                          const labelPoint = points[Math.floor(points.length / 2)] ?? path.from;
                          const labelX = (labelPoint.x / Math.max(lotWidth, 1)) * 100;
                          const labelY = (labelPoint.y / Math.max(lotHeight, 1)) * 100;
                          return (
                            <g key={path.id}>
                              <polyline
                                points={coords}
                                fill="none"
                                stroke={isSelected ? "#ef4444" : "#f97316"}
                                strokeWidth={isSelected ? "1.2" : "0.6"}
                                strokeDasharray="2 2"
                              />
                              <text
                                x={labelX}
                                y={labelY}
                                fontSize="3"
                                fill={isSelected ? "#dc2626" : "#ea580c"}
                                textAnchor="middle"
                              >
                                {path.label}
                              </text>
                            </g>
                          );
                        })}
                      </svg>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {showGeneratedPlan && planPreviewAnnotations?.labels?.length && previewImageBounds ? (
                  <div
                    className="pointer-events-none absolute"
                    style={{
                      left: previewImageBounds.left,
                      top: previewImageBounds.top,
                      width: previewImageBounds.width,
                      height: previewImageBounds.height,
                    }}
                  >
                    {activeHighlightBounds ? (
                      <div
                        className="absolute rounded-[14px] border-2 border-sky-400/90 bg-sky-400/10 shadow-[0_0_0_6px_rgba(56,189,248,0.18)]"
                        style={buildBoundsStyle(activeHighlightBounds)}
                      />
                    ) : null}
                    {issueHighlightBounds ? (
                      <div
                        className="absolute rounded-[12px] border-2 border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_6px_rgba(244,63,94,0.12)]"
                        style={buildBoundsStyle(issueHighlightBounds)}
                      />
                    ) : null}
                    {previewInteraction === "interactive"
                      ? planPreviewAnnotations.labels.map((item, idx) => (
                          <div
                            key={`${item.label}-${idx}`}
                            className="group pointer-events-auto absolute"
                            style={{
                              left: `${Math.min(Math.max(item.x * 100, 0), 100)}%`,
                              top: `${Math.min(Math.max(item.y * 100, 0), 100)}%`,
                              transform: "translate(-50%, -50%)",
                            }}
                          >
                            <div
                              className={`h-2 w-2 rounded-full transition ${
                                item.label === selectedIssueLabel
                                  ? "bg-rose-500/80 shadow-[0_0_0_6px_rgba(244,63,94,0.15)]"
                                  : "bg-slate-900/30 opacity-0 group-hover:opacity-100"
                              }`}
                            />
                            <div className="pointer-events-none absolute left-1/2 top-0 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 shadow-sm group-hover:block">
                              {item.label}
                            </div>
                          </div>
                        ))
                      : null}
                  </div>
                ) : null}
              </div>
              {showInteractive && activeAnnotation && hoverPoint ? (
                <div
                  className="pointer-events-none absolute z-20 min-w-[220px] max-w-[280px] rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg"
                  style={{
                    left: Math.min(Math.max(hoverPoint.x + 16, 16), 520),
                    top: Math.min(Math.max(hoverPoint.y + 16, 16), 420),
                  }}
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    {activeAnnotation.label}
                  </p>
                  <div className="mt-2 space-y-1">
                    {hoverDetails.length ? (
                      hoverDetails.map((detail) => (
                        <div key={detail.label} className="flex items-center justify-between gap-2">
                          <span className="text-slate-500">{detail.label}</span>
                          <span className="font-semibold text-slate-900">{detail.value}</span>
                        </div>
                      ))
                    ) : (
                      <div className="space-y-1 text-slate-500">
                        <div className="flex items-center justify-between gap-2">
                          <span>Layer</span>
                          <span className="font-semibold text-slate-900">
                            {activeAnnotation.layer || "Unknown"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Type</span>
                          <span className="font-semibold text-slate-900">
                            {activeAnnotation.meta?.entity_type || "Shape"}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : null}
              <div className="pointer-events-none absolute bottom-6 left-6 hidden rounded-[18px] border border-white/20 bg-white/70 px-4 py-3 text-xs text-slate-700 shadow-[0_10px_30px_-20px_rgba(15,23,42,0.6)] backdrop-blur lg:block">
                <span className="font-semibold uppercase tracking-[0.18em] text-slate-500">
                  AI Layout + Generation
                </span>
              </div>
              {previewInteraction === "interactive" && !planPreviewAnnotations?.labels?.length ? (
                <div className="pointer-events-none absolute right-6 top-6 hidden rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white lg:block">
                  Hover labels pending
                </div>
              ) : null}
              {placementMode ? (
                <div className="pointer-events-none absolute left-6 top-6 hidden rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-800 lg:block">
                  Placement mode: click to drop the selected object
                </div>
              ) : previewInteraction === "interactive" ? (
                <div
                  className="pointer-events-none absolute left-6 top-6 hidden rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white lg:block"
                >
                  Hover geometry for details
                </div>
              ) : null}
              <div className="pointer-events-none absolute bottom-6 right-6 hidden rounded-2xl border border-white/40 bg-white/85 px-3 py-2 text-[11px] text-slate-700 shadow-sm backdrop-blur lg:block">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Legend
                </p>
                <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.building }} />
                    <span>Buildings</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.parking }} />
                    <span>Parking</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.road }} />
                    <span>Roads</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.drainage }} />
                    <span>Drainage</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.utilities }} />
                    <span>Utilities</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

      {previewFullscreenOpen && (planPreviewUrl || showMap) ? (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/88 p-4 backdrop-blur-sm">
          <div className="flex h-full w-full max-w-[96vw] flex-col rounded-[28px] border border-slate-700/60 bg-slate-950 shadow-[0_30px_90px_-40px_rgba(15,23,42,0.95)]">
            <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-5 py-4 text-white">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Fullscreen Preview
                </p>
                <p className="mt-1 text-sm text-slate-200">
                  Inspect the latest engineered plan without the sidebar chrome.
                </p>
              </div>
              <button
                type="button"
                onClick={onCloseFullscreen}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-100 transition hover:bg-slate-800"
              >
                <X className="h-4 w-4" />
                Close
              </button>
            </div>
            <div className="flex min-h-0 flex-1 items-center justify-center p-4">
              <div
                ref={fullscreenRef}
                className="relative h-full w-full"
                onDragOver={(event) => {
                  event.preventDefault();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  const payload = event.dataTransfer?.getData("civora-object-id");
                  if (!payload) return;
                  onPlaceObject(payload, {
                    x: Math.min(Math.max((event.clientX - (fullscreenImageBounds?.left ?? 0)) / Math.max(fullscreenImageBounds?.width ?? 1, 1), 0), 1),
                    y: Math.min(Math.max((event.clientY - (fullscreenImageBounds?.top ?? 0)) / Math.max(fullscreenImageBounds?.height ?? 1, 1), 0), 1),
                  });
                }}
                onMouseMove={(event) => {
                  if (fullscreenImageBounds) {
                    updateDraggedBuilding(event, fullscreenImageBounds);
                  }
                  resolveHover(event, fullscreenRef, fullscreenImageBounds, setFullscreenHoverPoint);
                }}
                onMouseLeave={() => {
                  setHoveredAnnotation(null);
                  setFullscreenHoverPoint(null);
                  setDraggingBuildingId(null);
                  setDraggingMode(null);
                }}
                onMouseUp={() => {
                  setDraggingBuildingId(null);
                  setDraggingMode(null);
                }}
                onClick={(event) => {
                  if (placementMode) {
                    resolvePlacement(event, fullscreenRef, fullscreenImageBounds);
                    return;
                  }
                  if (!showInteractive || !hoveredAnnotation) return;
                  setPinnedAnnotation((prev) =>
                    prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
                  );
                }}
              >
                {showMap ? (
                  <div ref={fullscreenMapContainerRef} className="absolute inset-0 overflow-hidden rounded-[20px]" />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    ref={fullscreenImageRef}
                    src={planPreviewUrl}
                    alt="Generated plan preview fullscreen"
                    className="h-full w-full rounded-[20px] bg-white object-contain shadow-2xl"
                    onLoad={() =>
                      updateImageBounds(fullscreenRef, fullscreenImageRef, setFullscreenImageBounds)
                    }
                  />
                )}
                {previewInteraction === "interactive" &&
                !planPreviewAnnotations?.labels?.length ? (
                  <div className="pointer-events-none absolute right-6 top-6 rounded-2xl border border-white/20 bg-slate-900/80 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white">
                    No hover labels yet. Refresh the preview to generate them.
                  </div>
                ) : null}
                {planPreviewAnnotations?.labels?.length && fullscreenImageBounds ? (
                  <div
                    className="pointer-events-none absolute"
                    style={{
                      left: fullscreenImageBounds.left,
                      top: fullscreenImageBounds.top,
                      width: fullscreenImageBounds.width,
                      height: fullscreenImageBounds.height,
                    }}
                  >
                    {lotWidth > 0 && lotHeight > 0 ? (
                      <div className="absolute inset-0 rounded-[16px] border-2 border-dashed border-slate-300/70" />
                    ) : null}
                    {activeHighlightBounds ? (
                      <div
                        className="absolute rounded-[14px] border-2 border-sky-400/90 bg-sky-400/10 shadow-[0_0_0_6px_rgba(56,189,248,0.18)]"
                        style={buildBoundsStyle(activeHighlightBounds)}
                      />
                    ) : null}
                    {issueHighlightBounds ? (
                      <div
                        className="absolute rounded-[12px] border-2 border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_6px_rgba(244,63,94,0.12)]"
                        style={buildBoundsStyle(issueHighlightBounds)}
                      />
                    ) : null}
                    {previewInteraction === "interactive"
                      ? planPreviewAnnotations.labels.map((item, idx) => (
                          <div
                            key={`${item.label}-${idx}`}
                            className="group pointer-events-auto absolute"
                            style={{
                              left: `${Math.min(Math.max(item.x * 100, 0), 100)}%`,
                              top: `${Math.min(Math.max(item.y * 100, 0), 100)}%`,
                              transform: "translate(-50%, -50%)",
                            }}
                          >
                            <div
                              className={`h-2 w-2 rounded-full transition ${
                                item.label === selectedIssueLabel
                                  ? "bg-rose-500/80 shadow-[0_0_0_6px_rgba(244,63,94,0.15)]"
                                  : "bg-slate-900/30 opacity-0 group-hover:opacity-100"
                              }`}
                            />
                            <div className="pointer-events-none absolute left-1/2 top-0 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 shadow-sm group-hover:block">
                              {item.label}
                            </div>
                          </div>
                        ))
                      : null}
                    {buildingPlacements
                      .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                      .map((item) => {
                        const left = ((item.x || 0) / Math.max(lotWidth, 1)) * 100;
                        const top = ((item.y || 0) / Math.max(lotHeight, 1)) * 100;
                        const rotated = (item.rotation ?? 0) % 180 !== 0;
                        const displayW = rotated ? item.d : item.w;
                        const displayD = rotated ? item.w : item.d;
                        const width = (displayW / Math.max(lotWidth, 1)) * 100;
                        const height = (displayD / Math.max(lotHeight, 1)) * 100;
                        const rotation = item.rotation ?? 0;
                        const borderColorMap: Record<string, string> = {
                          site: "border-slate-400",
                          setback_zone: "border-slate-300",
                          no_build_zone: "border-rose-400",
                          basin: "border-emerald-500",
                          entrance: "border-amber-500",
                          driveway: "border-orange-400",
                          road: "border-blue-500",
                          parking: "border-violet-500",
                          sidewalk: "border-teal-500",
                          pool: "border-cyan-500",
                          pad: "border-stone-400",
                        };
                        const borderColor =
                          (item.type && borderColorMap[item.type]) || "border-slate-900/70";
                        return (
                          <div
                            key={item.id}
                            className="pointer-events-auto absolute"
                            style={{
                              left: `${left}%`,
                              top: `${top}%`,
                              width: `${width}%`,
                              height: `${height}%`,
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: placementMode ? "move" : "default",
                            }}
                            onMouseDown={(event) => handleBuildingMouseDown(event, item, "move")}
                            onClick={(event) => {
                              if (!placementMode) return;
                              event.stopPropagation();
                              onSelectBuilding(item.id);
                            }}
                          >
                            <div className={`h-full w-full rounded-[8px] border-2 bg-slate-900/10 transition ${borderColor}`} />
                            <button
                              type="button"
                              className="absolute -right-3 -top-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                              onMouseDown={(event) => handleBuildingMouseDown(event, item, "rotate")}
                            >
                              R
                            </button>
                            <button
                              type="button"
                              className="absolute -right-3 -bottom-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                              onMouseDown={(event) => handleBuildingMouseDown(event, item, "resize")}
                            >
                              Z
                            </button>
                            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
                              Snap 5ft
                            </div>
                          </div>
                        );
                      })}
                      {suggestedPlacements
                        .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                        .map((item) => {
                          const left = ((item.x || 0) / Math.max(lotWidth, 1)) * 100;
                          const top = ((item.y || 0) / Math.max(lotHeight, 1)) * 100;
                          const rotated = (item.rotation ?? 0) % 180 !== 0;
                          const displayW = rotated ? item.d : item.w;
                          const displayD = rotated ? item.w : item.d;
                          const width = (displayW / Math.max(lotWidth, 1)) * 100;
                          const height = (displayD / Math.max(lotHeight, 1)) * 100;
                          const rotation = item.rotation ?? 0;
                          const borderColorMap: Record<string, string> = {
                            site: "border-slate-400",
                            setback_zone: "border-slate-300",
                            no_build_zone: "border-rose-400",
                            basin: "border-emerald-500",
                            entrance: "border-amber-500",
                            driveway: "border-orange-400",
                            road: "border-blue-500",
                            parking: "border-violet-500",
                            sidewalk: "border-teal-500",
                            pool: "border-cyan-500",
                            pad: "border-stone-400",
                          };
                          const borderColor =
                            (item.type && borderColorMap[item.type]) || "border-slate-400";
                          return (
                            <div
                              key={item.id}
                              className="pointer-events-auto absolute"
                              style={{
                                left: `${left}%`,
                                top: `${top}%`,
                                width: `${width}%`,
                                height: `${height}%`,
                                transform: `rotate(${rotation}deg)`,
                                transformOrigin: "center",
                                cursor: "pointer",
                              }}
                              onMouseEnter={() => setHoveredObjectId(item.id)}
                              onMouseLeave={() => setHoveredObjectId(null)}
                              onClick={(event) => {
                                event.stopPropagation();
                                onSelectBuilding(item.id);
                              }}
                            >
                              <div
                                className={`h-full w-full rounded-[8px] border-2 border-dashed bg-slate-50/70 transition ${borderColor}`}
                              />
                              <div className="absolute left-2 top-2 rounded-full border border-slate-200 bg-white/90 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
                                {item.label}
                              </div>
                              <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
                                Suggested
                              </div>
                            </div>
                          );
                        })}
                  </div>
                ) : null}
                {showInteractive && activeAnnotation && fullscreenHoverPoint ? (
                  <div
                    className="pointer-events-none absolute z-20 min-w-[220px] max-w-[280px] rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg"
                    style={{
                      left: Math.min(Math.max(fullscreenHoverPoint.x + 16, 16), 620),
                      top: Math.min(Math.max(fullscreenHoverPoint.y + 16, 16), 520),
                    }}
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      {activeAnnotation.label}
                    </p>
                    <div className="mt-2 space-y-1">
                    {hoverDetails.length ? (
                      hoverDetails.map((detail) => (
                        <div key={detail.label} className="flex items-center justify-between gap-2">
                          <span className="text-slate-500">{detail.label}</span>
                          <span className="font-semibold text-slate-900">{detail.value}</span>
                        </div>
                      ))
                    ) : (
                      <div className="space-y-1 text-slate-500">
                        <div className="flex items-center justify-between gap-2">
                          <span>Layer</span>
                          <span className="font-semibold text-slate-900">
                            {activeAnnotation.layer || "Unknown"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Type</span>
                          <span className="font-semibold text-slate-900">
                            {activeAnnotation.meta?.entity_type || "Shape"}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : null}
                {previewInteraction === "interactive" && showMeasurements ? (
                  <div className="pointer-events-none absolute left-6 top-6 w-[240px] rounded-2xl border border-slate-200/70 bg-white/90 p-3 text-xs text-slate-700 shadow-sm backdrop-blur">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Measurements
                    </p>
                    <div className="mt-2 space-y-1">
                      {measurementOverlayStats
                        .filter((item) => Number(item.value || 0) > 0)
                        .map((item) => (
                          <div key={item.label} className="flex items-center justify-between gap-2">
                            <span>{item.label}</span>
                            <span className="font-semibold">
                              {item.unit === "stalls"
                                ? formatCount(Number(item.value || 0), item.unit)
                                : formatMetric(Number(item.value || 0), item.unit)}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                ) : null}
                {previewInteraction === "interactive" && showCalculations ? (
                  <div className="pointer-events-none absolute bottom-6 left-6 w-[240px] rounded-2xl border border-slate-200/70 bg-white/90 p-3 text-xs text-slate-700 shadow-sm backdrop-blur">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Calculations
                    </p>
                    <div className="mt-2 space-y-1">
                      {calculationOverlayStats
                        .filter((item) => Number(item.value || 0) > 0)
                        .map((item) => (
                          <div key={item.label} className="flex items-center justify-between gap-2">
                            <span>{item.label}</span>
                            <span className="font-semibold">
                              {formatMetric(Number(item.value || 0), item.unit)}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
