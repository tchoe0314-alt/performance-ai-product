"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, CSSProperties } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { Download, FileText, Hand, Lock, MapPin, Maximize2, MousePointer2, Pentagon, PencilLine, RefreshCw, RotateCcw, Square, Trash2, Unlock, X } from "lucide-react";

import type {
  Preview3DItem,
  PreviewResponse,
  PreviewReview,
  BuildingPlacement,
} from "../types";
import { formatCount, formatMetric } from "../utils/formatting";
import {
  boundsForSiteGeometry,
  mapLngLatToSite,
  resizeSiteGeometryFromOrigin,
  resolveCoordinateMode,
  screenToSitePoint as transformScreenToSitePoint,
  siteRectToPercent,
  siteToMapLngLat,
  siteToRelativePoint,
  siteTupleToPercent,
  translateSiteGeometry,
  coordinateModeLabel,
} from "../utils/geometryTransforms";
import Preview3DCanvas from "./Preview3DCanvas";

type PreviewPhaseLabel = { label: string } | null;
type EngineeringSystemStatus = "fresh" | "stale" | "not_generated";
type EngineeringSystemStatuses = Record<
  "roads" | "parking" | "grading" | "drainage" | "utilities",
  EngineeringSystemStatus
>;
type DrawMode = "select" | "pan" | "site" | "polyline" | "polygon" | "rect" | "point";

type ParkingParams = {
  stallWidth?: number;
  stallDepth?: number;
  aisleWidth?: number;
  adaAisleWidth?: number;
  adaCount?: number;
  compactCount?: number;
  compactWidth?: number;
  angleDeg?: number;
  loading?: "single" | "double";
  useMixedAngles?: boolean;
  compactZone?: boolean;
};

type PreviewPanelProps = {
  previewReview: PreviewReview | null;
  previewTotalPhaseCount: number;
  previewCompletedPhaseCount: number;
  previewRunningPhase: PreviewPhaseLabel;
  previewNextPendingPhase: PreviewPhaseLabel;
  onRefreshPreview: () => void;
  busy: boolean;
  planPreviewUrl: string;
  planPreviewProjectId?: string | null;
  currentProjectId?: string | null;
  previewMode: "2d" | "3d";
  previewInteraction: "static" | "edit";
  previewQuality: "standard" | "high";
  previewLabelDensity: "low" | "standard" | "high";
  systemStatuses: EngineeringSystemStatuses;
  hasTerrainSource: boolean;
  hasBasinPlaced: boolean;
  siteTooLargeForGrading: boolean;
  hasHardSystemBlock: boolean;
  hasGeneratedPlan: boolean;
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
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
  onCreateCustomGeometry: (payload: {
    mode: "polyline" | "polygon" | "rect" | "point";
    points: Array<[number, number]>;
    label?: string;
  }) => void;
  onCreateSiteBoundary?: (payload: { points: Array<[number, number]> }) => void;
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
  onRestoreBuilding?: (snapshot: BuildingPlacement) => void;
  externalRectUndo?: { id: string; snapshot: BuildingPlacement; action: "update" | "delete" | "add"; ts: number } | null;
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
  exportBlockReason?: string;
  planPreviewAnnotations: PreviewResponse["preview_annotations"] | null;
  selectedIssueLabel: string;
  showMeasurements: boolean;
  showCalculations: boolean;
  measurementOverlayStats: Array<{ label: string; value: number | null; unit: string }>;
  calculationOverlayStats: Array<{ label: string; value: number | null; unit: string }>;
  geocode?: { lat?: number; lng?: number } | null;
  siteRotationDeg?: number | null;
  showSiteBounds?: boolean;
  siteDrawRequest?: number;
  fitToSiteRequest?: number;
  alignToRoadRequest?: number;
  onSetSiteRotationDeg?: (value: number) => void;
  surveyPoints?: Array<{ x: number; y: number; z?: number }>;
  onMapScaleUpdate?: (payload: { ftPerPx: number; source: "mapbox" }) => void;
  mapCenterRequest?: number;
  onMapCenter?: (payload: { lat: number; lng: number }) => void;
  onViewportCenter?: (payload: { lat: number; lng: number }) => void;
  onViewportFootprint?: (value: {
    widthFt: number;
    heightFt: number;
    bounds?: {
      north: number;
      south: number;
      east: number;
      west: number;
      centerLat: number;
      centerLng: number;
    };
  }) => void;
  siteLocked?: boolean;
  gradingBlocker?: {
    sourcePoint: { x: number; y: number } | null;
    blockedTarget: { x: number; y: number } | null;
    blockerLocation: { x: number; y: number } | null;
    suggestedFixZone: { x: number; y: number; w: number; h: number } | null;
    approximate?: boolean;
  } | null;
  debugStats?: {
    enabled: boolean;
    projectId: string;
    canonicalCount: number;
    placedCount: number;
    previewImageActive: boolean;
    placementMode: boolean;
    selectedId: string | null;
  };
};

export default function PreviewPanel({
  previewTotalPhaseCount,
  previewCompletedPhaseCount,
  previewRunningPhase,
  previewNextPendingPhase,
  onRefreshPreview,
  busy,
  planPreviewUrl,
  planPreviewProjectId,
  currentProjectId,
  previewMode,
  previewInteraction,
  previewQuality,
  hasGeneratedPlan,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onSetPreviewQuality,
  onQueuePreviewRefresh,
  preview3DEffectiveItems,
  usingAnnotation3D,
  hasGradingSurface,
  placementMode,
  onPlaceBuilding,
  onPlaceObject,
  onCreateCustomGeometry,
  onCreateSiteBoundary,
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
  onRestoreBuilding,
  externalRectUndo,
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
  exportBlockReason,
  planPreviewAnnotations,
  selectedIssueLabel,
  showMeasurements,
  showCalculations,
  measurementOverlayStats,
  calculationOverlayStats,
  geocode,
  siteRotationDeg,
  showSiteBounds = false,
  siteDrawRequest = 0,
  fitToSiteRequest,
  alignToRoadRequest,
  onSetSiteRotationDeg,
  surveyPoints,
  onMapScaleUpdate,
  mapCenterRequest,
  onMapCenter,
  onViewportCenter,
  onViewportFootprint,
  siteLocked,
  gradingBlocker,
  debugStats,
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
  const [fullscreenContainerReady, setFullscreenContainerReady] = useState(false);
  const [previewContainerBounds, setPreviewContainerBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [cursorSitePoint, setCursorSitePoint] = useState<{ x: number; y: number } | null>(null);
  const [drawMode, setDrawMode] = useState<DrawMode>("select");
  const [draftPoints, setDraftPoints] = useState<Array<[number, number]>>([]);
  const [draftPreviewPoint, setDraftPreviewPoint] = useState<[number, number] | null>(null);
  const lastSiteDrawRequestRef = useRef(siteDrawRequest);
  const [canvasView, setCanvasView] = useState({ scale: 1, offsetX: 0, offsetY: 0 });
  const drawingLotWidth = lotWidth > 0 ? lotWidth : 500;
  const drawingLotHeight = lotHeight > 0 ? lotHeight : 300;
  const hasDrawableSiteSize = lotWidth > 0 && lotHeight > 0;
  const canDrawObjects = Boolean(siteLocked && hasDrawableSiteSize);
  const drawObjectsDisabledLabel = !siteLocked
    ? "Lock site boundary before drawing objects"
    : !hasDrawableSiteSize
      ? "Set site width and depth before drawing objects"
      : "Drawing tools available";
  const [canvasPanStart, setCanvasPanStart] = useState<{
    x: number;
    y: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const [draggingBuildingId, setDraggingBuildingId] = useState<string | null>(null);
  const [draggingMode, setDraggingMode] = useState<"move" | "resize" | "rotate" | "vertex" | null>(null);
  const [draggingVertex, setDraggingVertex] = useState<{ id: string; index: number } | null>(null);
  const [hoveredVertex, setHoveredVertex] = useState<{ id: string; index: number } | null>(null);
  const [hoveredSegment, setHoveredSegment] = useState<{ id: string; index: number } | null>(null);
  const [polylineInsertHintDismissed, setPolylineInsertHintDismissed] = useState(false);
  const [selectedVertex, setSelectedVertex] = useState<{ id: string; index: number } | null>(null);
  const [lastPolylineEdit, setLastPolylineEdit] = useState<{
    id: string;
    geometry: Array<[number, number]>;
    x: number;
    y: number;
    w: number;
    d: number;
    ts: number;
  } | null>(null);
  const [lastRectEdit, setLastRectEdit] = useState<{
    id: string;
    snapshot: BuildingPlacement;
    action: "update" | "delete" | "add";
    ts: number;
  } | null>(null);
  const polylineSegmentRef = useRef<SVGSVGElement | null>(null);
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
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapboxRequestCount, setMapboxRequestCount] = useState(0);
  const [mapboxTileCount, setMapboxTileCount] = useState(0);
  const [mapCanvasSize, setMapCanvasSize] = useState<{ w: number; h: number } | null>(null);
  const [mapContainerSize, setMapContainerSize] = useState<{ w: number; h: number } | null>(null);
  const lastMapResizeRef = useRef<number>(0);
  const [mapLocked, setMapLocked] = useState(false);
  const mapDragRef = useRef<{ x: number; y: number } | null>(null);
  const mapDragActiveRef = useRef(false);
  const previewSizeRef = useRef<{ w: number; h: number } | null>(null);
  const fullscreenSizeRef = useRef<{ w: number; h: number } | null>(null);
  const previewResizeRafRef = useRef<number | null>(null);
  const fullscreenResizeRafRef = useRef<number | null>(null);
  const [rotateDragActive, setRotateDragActive] = useState(false);
  const [rotateDragStart, setRotateDragStart] = useState<{ x: number; value: number } | null>(null);
  const activeAnnotation = pinnedAnnotation ?? hoveredAnnotation;
  const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  const mapAvailable =
    Boolean(mapboxToken) &&
    Boolean(geocode?.lat && geocode?.lng);
  const showMap = mapAvailable && previewQuality === "high";
  const showMap3D = showMap && previewMode === "3d";
  const mapPitch = showMap3D ? 58 : 0;
  const mapBearing = showMap3D ? (typeof siteRotationDeg === "number" ? siteRotationDeg : 0) : 0;
  const allowMapInteraction =
    showMap && previewInteraction === "static" && !placementMode && !rotateDragStart && !mapLocked;
  const showGeneratedPlan =
    !showMap &&
    hasGeneratedPlan &&
    !placementMode &&
    !selectedBuildingId &&
    (!planPreviewProjectId || !currentProjectId || planPreviewProjectId === currentProjectId);
  const hasInteractiveLabels = previewLabels.length > 0 && showGeneratedPlan;
  const hasLiveObjects =
    buildingPlacements.length > 0 ||
    suggestedPlacements.length > 0 ||
    (surveyPoints?.length ?? 0) > 0 ||
    Boolean(lotWidth && lotHeight);
  const canUse3D = showMap || hasLiveObjects || preview3DEffectiveItems.length > 0 || Boolean(planPreviewUrl);
  const showHover = previewInteraction === "static";
  const allowEdits = previewInteraction === "edit";
  const overlayPointerEvents = allowMapInteraction ? "pointer-events-none" : "pointer-events-auto";
  const normalPalette = {
    building: "#0f172a",
    buildingFill: "rgba(15, 23, 42, 0.12)",
    parking: "#cbd5e1",
    parkingFill: "rgba(148, 163, 184, 0.18)",
    road: "#475569",
    roadFill: "rgba(71, 85, 105, 0.2)",
    drainage: "#1d4ed8",
    utilities: "#7c3aed",
    detectedStroke: "#f59e0b",
    detectedFill: "rgba(245, 158, 11, 0.15)",
    siteBorder: "border-slate-300/90",
    siteFill: "bg-slate-200/40",
  } as const;
  const highPalette = {
    building: "#111827",
    buildingFill: "rgba(17, 24, 39, 0.24)",
    parking: "#6b7280",
    parkingFill: "rgba(107, 114, 128, 0.24)",
    road: "#1f2937",
    roadFill: "rgba(31, 41, 55, 0.3)",
    drainage: "#0ea5e9",
    utilities: "#8b5cf6",
    detectedStroke: "#f59e0b",
    detectedFill: "rgba(245, 158, 11, 0.2)",
    siteBorder: "border-white/80",
    siteFill: "bg-white/15",
  } as const;
  const legendPalette = previewQuality === "high" ? highPalette : normalPalette;
  const currentSiteSize = useMemo(
    () => ({ width: Math.max(lotWidth, 1), height: Math.max(lotHeight, 1) }),
    [lotHeight, lotWidth],
  );
  const isHighQuality = previewQuality === "high";
  const resolveVisualKind = useCallback((item: BuildingPlacement) => {
    const type = String(item.type || "building");
    if (type.includes("building") || type === "pad" || !item.type) return "building";
    if (type === "road" || type === "driveway") return "road";
    if (type === "parking") return "parking";
    if (type === "basin" || type === "pond" || type === "pool") return "water";
    if (type === "open_space" || type === "landscape" || type === "amenity") return "landscape";
    if (type === "sidewalk") return "sidewalk";
    if (
      type === "inlet" ||
      type === "outfall" ||
      type === "hydrant" ||
      type === "manhole" ||
      type === "utility_corridor"
    ) {
      return "utility";
    }
    return "fallback";
  }, []);
  const resolveSvgVisualStyle = useCallback(
    (item: BuildingPlacement, selected = false) => {
      const kind = resolveVisualKind(item);
      if (!isHighQuality) {
        return {
          fill: kind === "parking" ? legendPalette.parkingFill : legendPalette.buildingFill,
          stroke: selected ? "#f59e0b" : kind === "road" ? legendPalette.road : legendPalette.building,
          strokeWidth: selected ? 0.75 : 0.45,
        };
      }
      if (kind === "road") {
        return { fill: "none", stroke: selected ? "#fbbf24" : "#111827", strokeWidth: selected ? 1.35 : 1.05 };
      }
      if (kind === "parking") {
        return { fill: "rgba(71, 85, 105, 0.32)", stroke: selected ? "#fbbf24" : "#64748b", strokeWidth: selected ? 0.75 : 0.42 };
      }
      if (kind === "water") {
        return { fill: "rgba(14, 165, 233, 0.28)", stroke: selected ? "#fbbf24" : "#0284c7", strokeWidth: selected ? 0.75 : 0.45 };
      }
      if (kind === "landscape") {
        return { fill: "rgba(34, 197, 94, 0.22)", stroke: selected ? "#fbbf24" : "#16a34a", strokeWidth: selected ? 0.75 : 0.4 };
      }
      if (kind === "sidewalk") {
        return { fill: "none", stroke: selected ? "#fbbf24" : "#0f766e", strokeWidth: selected ? 0.85 : 0.55 };
      }
      if (kind === "utility") {
        return { fill: "rgba(124, 58, 237, 0.14)", stroke: selected ? "#fbbf24" : "#7c3aed", strokeWidth: selected ? 0.75 : 0.45 };
      }
      return { fill: "rgba(148, 163, 184, 0.18)", stroke: selected ? "#fbbf24" : "#64748b", strokeWidth: selected ? 0.75 : 0.42 };
    },
    [isHighQuality, legendPalette.building, legendPalette.buildingFill, legendPalette.parkingFill, legendPalette.road, resolveVisualKind],
  );
  const resolveObjectBoxStyle = useCallback(
    (item: BuildingPlacement): CSSProperties => {
      const kind = resolveVisualKind(item);
      if (!isHighQuality) {
        return {
          backgroundColor: "rgba(15, 23, 42, 0.22)",
          borderColor: (item.meta as { style?: { outline_color?: string } } | undefined)?.style?.outline_color,
        };
      }
      const outlineColor = (item.meta as { style?: { outline_color?: string } } | undefined)?.style?.outline_color;
      const base: CSSProperties = {
        borderColor: outlineColor,
        boxShadow: "0 8px 22px rgba(15,23,42,0.2)",
      };
      if (kind === "building") {
        return {
          ...base,
          backgroundColor: "rgba(30, 41, 59, 0.82)",
          backgroundImage:
            "linear-gradient(135deg, rgba(255,255,255,0.2), rgba(15,23,42,0.2)), repeating-linear-gradient(90deg, rgba(255,255,255,0.12) 0 1px, transparent 1px 14px)",
        };
      }
      if (kind === "road") {
        return {
          ...base,
          backgroundColor: "rgba(31, 41, 55, 0.82)",
          backgroundImage:
            "linear-gradient(90deg, transparent 0 45%, rgba(248,250,252,0.55) 45% 50%, transparent 50% 100%)",
        };
      }
      if (kind === "parking") {
        return {
          ...base,
          backgroundColor: "rgba(71, 85, 105, 0.34)",
          backgroundImage: "repeating-linear-gradient(90deg, rgba(255,255,255,0.58) 0 1px, transparent 1px 12px)",
          boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.24), 0 6px 18px rgba(15,23,42,0.12)",
        };
      }
      if (kind === "water") {
        return {
          ...base,
          backgroundColor: "rgba(14, 165, 233, 0.34)",
          backgroundImage: "linear-gradient(135deg, rgba(255,255,255,0.32), rgba(14,116,144,0.16))",
          boxShadow: "inset 0 0 18px rgba(56,189,248,0.22), 0 6px 18px rgba(14,116,144,0.16)",
        };
      }
      if (kind === "landscape") {
        return {
          ...base,
          backgroundColor: "rgba(34, 197, 94, 0.22)",
          backgroundImage:
            "radial-gradient(circle at 20% 30%, rgba(22,163,74,0.22) 0 2px, transparent 2px), radial-gradient(circle at 70% 65%, rgba(132,204,22,0.2) 0 2px, transparent 2px)",
        };
      }
      if (kind === "sidewalk") {
        return {
          ...base,
          backgroundColor: "rgba(240, 253, 250, 0.58)",
          backgroundImage: "repeating-linear-gradient(90deg, rgba(15,118,110,0.25) 0 1px, transparent 1px 10px)",
          boxShadow: "inset 0 0 0 1px rgba(15,118,110,0.24)",
        };
      }
      if (kind === "utility") {
        return {
          ...base,
          backgroundColor: "rgba(124, 58, 237, 0.18)",
          backgroundImage: "repeating-linear-gradient(135deg, rgba(124,58,237,0.28) 0 1px, transparent 1px 9px)",
          boxShadow: "inset 0 0 0 1px rgba(124,58,237,0.2)",
        };
      }
      return {
        ...base,
        backgroundColor: "rgba(148, 163, 184, 0.2)",
        backgroundImage: "repeating-linear-gradient(45deg, rgba(100,116,139,0.22) 0 1px, transparent 1px 9px)",
      };
    },
    [isHighQuality, resolveVisualKind],
  );
  const hoveredObject = useMemo(
    () =>
      [...buildingPlacements, ...suggestedPlacements].find(
        (item) => item.id === hoveredObjectId && item.type !== "site",
      ) ?? null,
    [buildingPlacements, suggestedPlacements, hoveredObjectId],
  );
  const show3D = previewMode === "3d" && !showMap;
  useEffect(() => {
    if (typeof window === "undefined") return;
    const debugWindow = window as unknown as Record<string, unknown>;
    debugWindow.__civoraGeocode = geocode ?? null;
    debugWindow.__civoraShowMap = showMap;
    debugWindow.__civoraPreviewQuality = previewQuality;
    debugWindow.__civoraMapLoaded = mapLoaded;
  }, [geocode, mapLoaded, showMap, previewQuality]);
  const selectedObject = useMemo(
    () =>
      [...buildingPlacements, ...suggestedPlacements].find(
        (item) => item.id === selectedBuildingId && item.type !== "site",
      ) ?? null,
    [buildingPlacements, suggestedPlacements, selectedBuildingId],
  );
  const selectedDeletableObject =
    selectedObject && !selectedObject.locked ? selectedObject : null;
  const accessPointsForParking = useMemo(
    () =>
      buildingPlacements
        .filter((item) => item.type === "entrance" || item.type === "road" || item.type === "driveway")
        .map((item) => ({ x: (item.x ?? 0) + item.w / 2, y: (item.y ?? 0) + item.d / 2 })),
    [buildingPlacements],
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
      const handle = window.requestAnimationFrame(() => {
        setHoveredObjectId((current) => (current === entityId ? current : entityId));
      });
      return () => window.cancelAnimationFrame(handle);
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
  const viewportTransformStyle = useMemo(
    () => ({
      transform: `translate(${canvasView.offsetX}px, ${canvasView.offsetY}px) scale(${canvasView.scale})`,
      transformOrigin: "top left",
    }),
    [canvasView.offsetX, canvasView.offsetY, canvasView.scale],
  );
  const screenToSitePoint = useCallback(
    (
      clientX: number,
      clientY: number,
      containerRef: React.RefObject<HTMLDivElement | null>,
      bounds: { left: number; top: number; width: number; height: number } | null,
    ) => {
      const effectiveLotWidth = drawMode === "site" ? drawingLotWidth : lotWidth;
      const effectiveLotHeight = drawMode === "site" ? drawingLotHeight : lotHeight;
      if (!containerRef.current || !bounds || !effectiveLotWidth || !effectiveLotHeight) return null;
      const rect = containerRef.current.getBoundingClientRect();
      const rawSitePoint = transformScreenToSitePoint(
        { x: clientX, y: clientY },
        { left: rect.left, top: rect.top },
        bounds,
        { width: effectiveLotWidth, height: effectiveLotHeight },
        canvasView,
      );
      const relX = rawSitePoint.x / Math.max(effectiveLotWidth, 1);
      const relY = rawSitePoint.y / Math.max(effectiveLotHeight, 1);
      if (!Number.isFinite(relX) || !Number.isFinite(relY)) return null;
      if (relX < 0 || relX > 1 || relY < 0 || relY > 1) return null;
      const snapStep = drawMode === "point" ? 1 : drawMode === "site" ? 5 : 2;
      return {
        x: Math.round(rawSitePoint.x / snapStep) * snapStep,
        y: Math.round(rawSitePoint.y / snapStep) * snapStep,
        relX,
        relY,
      };
    },
    [
      canvasView,
      drawMode,
      drawingLotHeight,
      drawingLotWidth,
      lotHeight,
      lotWidth,
    ],
  );
  const updateImageBounds = useCallback(
    (
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageRef: React.RefObject<HTMLImageElement | null>,
      setter: React.Dispatch<React.SetStateAction<{ left: number; top: number; width: number; height: number } | null>>,
    ) => {
      if (!containerRef.current || !imageRef.current) {
        setter((current) => (current === null ? current : null));
        return;
      }
      const containerRect = containerRef.current.getBoundingClientRect();
      const imageRect = imageRef.current.getBoundingClientRect();
      const width = Math.max(imageRect.width, 1);
      const height = Math.max(imageRect.height, 1);
      const nextBounds = {
        left: imageRect.left - containerRect.left,
        top: imageRect.top - containerRect.top,
        width,
        height,
      };
      setter((current) =>
        current &&
        Math.abs(current.left - nextBounds.left) < 0.5 &&
        Math.abs(current.top - nextBounds.top) < 0.5 &&
        Math.abs(current.width - nextBounds.width) < 0.5 &&
        Math.abs(current.height - nextBounds.height) < 0.5
          ? current
          : nextBounds,
      );
    },
    [],
  );
  const updateContainerBounds = useCallback(() => {
    if (!previewRef.current) return;
    const rect = previewRef.current.getBoundingClientRect();
    const nextBounds = { left: 0, top: 0, width: rect.width, height: rect.height };
    setPreviewContainerBounds((current) =>
      current &&
      Math.abs(current.width - nextBounds.width) < 0.5 &&
      Math.abs(current.height - nextBounds.height) < 0.5
        ? current
        : nextBounds,
    );
  }, []);
  const resolveHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageBounds: { left: number; top: number; width: number; height: number } | null,
      setPoint: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>,
    ) => {
      if (!showHover || !containerRef.current || !hasInteractiveLabels) {
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
    [hasInteractiveLabels, previewLabels, showHover],
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
      const sitePoint = screenToSitePoint(event.clientX, event.clientY, containerRef, bounds);
      if (!sitePoint) return;
      const relativeX = sitePoint.relX;
      const relativeY = sitePoint.relY;
      console.debug("[placement] canvas-click", {
        source: "overlay",
        relativeX,
        relativeY,
      });
      const fallback = buildingPlacements.find((item) => !item.placed && item.type !== "site");
      const targetId = selectedBuildingId ?? fallback?.id ?? null;
      if (targetId) {
        onPlaceObject(targetId, { x: relativeX, y: relativeY });
        return;
      }
      onPlaceBuilding({ x: relativeX, y: relativeY });
    },
    [buildingPlacements, onPlaceBuilding, onPlaceObject, placementMode, screenToSitePoint, selectedBuildingId],
  );

  const clampValue = (value: number, min: number, max: number) =>
    Math.min(Math.max(value, min), max);

  const getEditCapabilities = useCallback((item: BuildingPlacement) => {
    const type = item.type ?? "building";
    const editableTypes = new Set([
      "site",
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
      "custom",
    ]);
    const resizableTypes = new Set([
      "site",
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
      "custom",
    ]);
    const rotatableTypes = new Set([
      "site",
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
      "custom",
    ]);
    const deletableTypes = new Set([...editableTypes].filter((t) => t !== "site"));
    const isSite = type === "site";
    const effectiveLocked = isSite ? Boolean(siteLocked) : item.locked;
    const movable = editableTypes.has(type) && !effectiveLocked;
    const resizable = resizableTypes.has(type) && !effectiveLocked;
    const rotatable = rotatableTypes.has(type) && !effectiveLocked;
    const deletable = deletableTypes.has(type) && !effectiveLocked;
    return { movable, resizable, rotatable, deletable };
  }, [siteLocked]);

  const snapValue = useCallback((value: number, step: number) => {
    if (!step) return value;
    return Math.round(value / step) * step;
  }, []);

  const updateDraggedBuilding = useCallback(
    (event: React.MouseEvent<HTMLDivElement>, bounds: { left: number; top: number; width: number; height: number }) => {
      if (!draggingBuildingId || !draggingMode) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const sitePoint = transformScreenToSitePoint(
        { x: event.clientX, y: event.clientY },
        { left: rect.left, top: rect.top },
        bounds,
        currentSiteSize,
        canvasView,
      );
      const target =
        buildingPlacements.find((item) => item.id === draggingBuildingId) ??
        suggestedPlacements.find((item) => item.id === draggingBuildingId);
      if (!target) return;
      if (target.locked) return;
      const caps = getEditCapabilities(target);
      if (draggingMode === "move" && !caps.movable) return;
      if (draggingMode === "resize" && !caps.resizable) return;
      if (draggingMode === "rotate" && !caps.rotatable) return;
      if (draggingMode === "move") {
        const dragSiteOffset = {
          x: (dragOffset.x / Math.max(bounds.width, 1)) * lotWidth,
          y: (dragOffset.y / Math.max(bounds.height, 1)) * lotHeight,
        };
        const x = snapValue(
          clampValue(sitePoint.x - dragSiteOffset.x, 0, Math.max(lotWidth - target.w, 0)),
          5,
        );
        const y = snapValue(
          clampValue(sitePoint.y - dragSiteOffset.y, 0, Math.max(lotHeight - target.d, 0)),
          5,
        );
        const deltaX = x - (target.x ?? 0);
        const deltaY = y - (target.y ?? 0);
        const updates: Partial<BuildingPlacement> = { x, y, placed: true };
        if (target.geometryType && Array.isArray(target.geometry)) {
          updates.geometry = translateSiteGeometry(target.geometry as Array<[number, number]>, {
            x: deltaX,
            y: deltaY,
          });
        }
        if (target.source === "detected_from_image") {
          onUpdateSuggested(draggingBuildingId, updates);
        } else {
          onUpdateBuilding(draggingBuildingId, updates);
        }
        return;
      }
      if (
        draggingMode === "vertex" &&
        draggingVertex &&
        (target.geometryType === "polyline" || target.geometryType === "polygon")
      ) {
        const rawX = sitePoint.x;
        const rawY = sitePoint.y;
        const nextX = snapValue(clampValue(rawX, 0, lotWidth), 1);
        const nextY = snapValue(clampValue(rawY, 0, lotHeight), 1);
        const nextGeometry: Array<[number, number]> = Array.isArray(target.geometry)
          ? (target.geometry as Array<[number, number]>).map((pt, idx) =>
              idx === draggingVertex.index ? [nextX, nextY] : pt,
            )
          : [];
        const nextBounds = boundsForSiteGeometry(nextGeometry);
        const updates = {
          geometry: nextGeometry,
          x: nextBounds.minX,
          y: nextBounds.minY,
          w: Math.max(5, nextBounds.width),
          d: Math.max(5, nextBounds.height),
          placed: true,
        };
        if (target.source === "detected_from_image") {
          onUpdateSuggested(draggingBuildingId, updates);
        } else {
          onUpdateBuilding(draggingBuildingId, updates);
        }
        return;
      }
      if (draggingMode === "resize") {
        const rawW = clampValue(sitePoint.x, 10, lotWidth);
        const rawD = clampValue(sitePoint.y, 10, lotHeight);
        const nextW = Math.max(10, snapValue(rawW - (target.x ?? 0), 5));
        const nextD = Math.max(10, snapValue(rawD - (target.y ?? 0), 5));
        const updates: Partial<BuildingPlacement> = { w: nextW, d: nextD };
        if (
          (target.geometryType === "polygon" || target.geometryType === "rect") &&
          Array.isArray(target.geometry) &&
          target.w > 0 &&
          target.d > 0
        ) {
          const originX = target.x ?? 0;
          const originY = target.y ?? 0;
          updates.geometry = resizeSiteGeometryFromOrigin(
            target.geometry as Array<[number, number]>,
            { x: originX, y: originY },
            { width: target.w, height: target.d },
            { width: nextW, height: nextD },
          );
        } else if (target.geometryType === "point" && Array.isArray(target.geometry)) {
          updates.geometry = [[(target.x ?? 0) + nextW / 2, (target.y ?? 0) + nextD / 2]];
        }
        if (target.source === "detected_from_image") {
          onUpdateSuggested(draggingBuildingId, updates);
        } else {
          onUpdateBuilding(draggingBuildingId, updates);
        }
        return;
      }
      if (draggingMode === "rotate") {
        const centerX = bounds.left + ((target.x ?? 0) + target.w / 2) / Math.max(lotWidth, 1) * bounds.width;
        const centerY = bounds.top + ((target.y ?? 0) + target.d / 2) / Math.max(lotHeight, 1) * bounds.height;
        const pointerViewportX = (sitePoint.x / Math.max(lotWidth, 1)) * bounds.width;
        const pointerViewportY = (sitePoint.y / Math.max(lotHeight, 1)) * bounds.height;
        const angle = Math.atan2(pointerViewportY + bounds.top - centerY, pointerViewportX + bounds.left - centerX);
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
      draggingVertex,
      draggingBuildingId,
      draggingMode,
      canvasView,
      currentSiteSize,
      lotHeight,
      lotWidth,
      getEditCapabilities,
      onUpdateBuilding,
      onUpdateSuggested,
      snapValue,
    ],
  );

  const insertVertexOnSegment = useCallback(
    (
      event: React.MouseEvent<SVGLineElement>,
      item: BuildingPlacement,
      segmentIndex: number,
    ) => {
      if (!polylineSegmentRef.current || !lotWidth || !lotHeight) return;
      if (!Array.isArray(item.geometry) || item.geometry.length < 2) return;
      const rect = polylineSegmentRef.current.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const xPct = (event.clientX - rect.left) / rect.width;
      const yPct = (event.clientY - rect.top) / rect.height;
      const nextX = snapValue(clampValue((item.x ?? 0) + xPct * item.w, 0, lotWidth), 1);
      const nextY = snapValue(clampValue((item.y ?? 0) + yPct * item.d, 0, lotHeight), 1);
      const geometry = item.geometry as Array<[number, number]>;
      setLastPolylineEdit({
        id: item.id,
        geometry: geometry.map((pt) => [pt[0], pt[1]]),
        x: item.x ?? 0,
        y: item.y ?? 0,
        w: item.w,
        d: item.d,
        ts: Date.now(),
      });
      const nextGeometry = [...geometry];
      nextGeometry.splice(segmentIndex + 1, 0, [nextX, nextY]);
      const nextBounds = boundsForSiteGeometry(nextGeometry);
      const updates = {
        geometry: nextGeometry,
        x: nextBounds.minX,
        y: nextBounds.minY,
        w: Math.max(5, nextBounds.width),
        d: Math.max(5, nextBounds.height),
        placed: true,
      };
      if (item.source === "detected_from_image") {
        onUpdateSuggested(item.id, updates);
      } else {
        onUpdateBuilding(item.id, updates);
      }
      setHoveredVertex({ id: item.id, index: segmentIndex + 1 });
      setHoveredSegment({ id: item.id, index: segmentIndex });
      setSelectedVertex({ id: item.id, index: segmentIndex + 1 });
      setPolylineInsertHintDismissed(true);
      onSelectBuilding(item.id);
    },
    [lotHeight, lotWidth, onSelectBuilding, onUpdateBuilding, onUpdateSuggested, snapValue],
  );

  const deleteSelectedVertex = useCallback(() => {
    if (!selectedVertex) return;
    const target =
      buildingPlacements.find((item) => item.id === selectedVertex.id) ??
      suggestedPlacements.find((item) => item.id === selectedVertex.id);
    if (!target || !Array.isArray(target.geometry)) return;
    const geometry = target.geometry as Array<[number, number]>;
    const minVertices = target.geometryType === "polygon" ? 3 : 2;
    if (geometry.length <= minVertices) return;
    setLastPolylineEdit({
      id: target.id,
      geometry: geometry.map((pt) => [pt[0], pt[1]]),
      x: target.x ?? 0,
      y: target.y ?? 0,
      w: target.w,
      d: target.d,
      ts: Date.now(),
    });
    const nextGeometry = geometry.filter((_, idx) => idx !== selectedVertex.index);
    if (nextGeometry.length < minVertices) return;
    const nextBounds = boundsForSiteGeometry(nextGeometry);
    const updates = {
      geometry: nextGeometry,
      x: nextBounds.minX,
      y: nextBounds.minY,
      w: Math.max(5, nextBounds.width),
      d: Math.max(5, nextBounds.height),
      placed: true,
    };
    if (target.source === "detected_from_image") {
      onUpdateSuggested(target.id, updates);
    } else {
      onUpdateBuilding(target.id, updates);
    }
    setSelectedVertex(null);
  }, [buildingPlacements, onUpdateBuilding, onUpdateSuggested, selectedVertex, suggestedPlacements]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("input, textarea, select, [contenteditable='true']")) return;
      if (event.key !== "Backspace" && event.key !== "Delete") return;
      if (!selectedVertex) return;
      event.preventDefault();
      deleteSelectedVertex();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [deleteSelectedVertex, selectedVertex]);

  const applyPolylineUndo = useCallback(() => {
    if (!lastPolylineEdit) return;
    const target =
      buildingPlacements.find((item) => item.id === lastPolylineEdit.id) ??
      suggestedPlacements.find((item) => item.id === lastPolylineEdit.id);
    if (!target) return;
    const updates = {
      geometry: lastPolylineEdit.geometry.map((pt) => [pt[0], pt[1]] as [number, number]),
      x: lastPolylineEdit.x,
      y: lastPolylineEdit.y,
      w: lastPolylineEdit.w,
      d: lastPolylineEdit.d,
      placed: true,
    };
    if (target.source === "detected_from_image") {
      onUpdateSuggested(target.id, updates);
    } else {
      onUpdateBuilding(target.id, updates);
    }
    setSelectedVertex(null);
    setDraggingVertex(null);
    setDraggingMode(null);
    setDraggingBuildingId(null);
    setLastPolylineEdit(null);
  }, [buildingPlacements, lastPolylineEdit, onUpdateBuilding, onUpdateSuggested, suggestedPlacements]);

  const applyRectUndo = useCallback(() => {
    if (!lastRectEdit) return;
    if (lastRectEdit.action === "delete") {
      onRestoreBuilding?.(lastRectEdit.snapshot);
    } else if (lastRectEdit.action === "add") {
      onRemoveBuilding(lastRectEdit.id);
    } else {
      onUpdateBuilding(lastRectEdit.id, { ...lastRectEdit.snapshot });
    }
    setSelectedVertex(null);
    setDraggingVertex(null);
    setDraggingMode(null);
    setDraggingBuildingId(null);
    setLastRectEdit(null);
  }, [lastRectEdit, onRemoveBuilding, onRestoreBuilding, onUpdateBuilding]);

  const clearDraftGeometry = useCallback(() => {
    setDraftPoints([]);
    setDraftPreviewPoint(null);
  }, []);

  useEffect(() => {
    if (siteDrawRequest === lastSiteDrawRequestRef.current) return;
    lastSiteDrawRequestRef.current = siteDrawRequest;
    if (siteLocked) return;
    const handle = window.requestAnimationFrame(() => {
      clearDraftGeometry();
      setDrawMode("site");
      onSetPreviewInteraction("edit");
    });
    return () => window.cancelAnimationFrame(handle);
  }, [clearDraftGeometry, onSetPreviewInteraction, siteDrawRequest, siteLocked]);

  const finishDraftGeometry = useCallback(() => {
    if (drawMode !== "site" && drawMode !== "polyline" && drawMode !== "polygon" && drawMode !== "rect") return;
    const effectivePoints =
      draftPreviewPoint &&
      !draftPoints.some(
        (pt) => Math.abs(pt[0] - draftPreviewPoint[0]) < 0.001 && Math.abs(pt[1] - draftPreviewPoint[1]) < 0.001,
      )
        ? [...draftPoints, draftPreviewPoint]
        : draftPoints;
    const minPoints = drawMode === "site" || drawMode === "polygon" ? 3 : 2;
    if (effectivePoints.length < minPoints) return;
    if (drawMode === "site") {
      onCreateSiteBoundary?.({ points: effectivePoints });
    } else {
      onCreateCustomGeometry({ mode: drawMode, points: effectivePoints });
    }
    clearDraftGeometry();
    setDrawMode("select");
  }, [
    clearDraftGeometry,
    draftPoints,
    draftPreviewPoint,
    drawMode,
    onCreateCustomGeometry,
    onCreateSiteBoundary,
  ]);

  const draftPointCount = draftPoints.length + (draftPreviewPoint ? 1 : 0);
  const finishDraftMinPoints = drawMode === "site" || drawMode === "polygon" ? 3 : 2;
  const finishDraftBlockedReason =
    draftPoints.length && drawMode !== "rect" && draftPointCount < finishDraftMinPoints
      ? drawMode === "site"
        ? "Blocked: draw at least three boundary points before Finish."
        : drawMode === "polygon"
          ? "Blocked: draw at least three area points before Finish."
          : "Blocked: draw at least two line points before Finish."
      : null;

  const handleDrawPointer = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      bounds: { left: number; top: number; width: number; height: number } | null,
    ) => {
      if (drawMode === "select") return false;
      if (!bounds || !previewRef.current) return false;
      if (drawMode === "pan") {
        event.preventDefault();
        setCanvasPanStart({
          x: event.clientX,
          y: event.clientY,
          offsetX: canvasView.offsetX,
          offsetY: canvasView.offsetY,
        });
        return true;
      }
      if (drawMode !== "site" && !canDrawObjects) {
        event.preventDefault();
        event.stopPropagation();
        return true;
      }
      const sitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, bounds);
      if (!sitePoint) return true;
      event.preventDefault();
      event.stopPropagation();
      const point: [number, number] = [sitePoint.x, sitePoint.y];
      if (drawMode === "point") {
        onCreateCustomGeometry({ mode: "point", points: [point] });
        clearDraftGeometry();
        setDrawMode("select");
        return true;
      }
      if (drawMode === "rect") {
        if (!draftPoints.length) {
          setDraftPoints([point]);
          return true;
        }
        onCreateCustomGeometry({ mode: "rect", points: [draftPoints[0], point] });
        setDrawMode("select");
        setDraftPreviewPoint(null);
        setDraftPoints([]);
        return true;
      }
      setDraftPoints((prev) => [...prev, point]);
      return true;
    },
    [
      canvasView.offsetX,
      canvasView.offsetY,
      canDrawObjects,
      clearDraftGeometry,
      draftPoints,
      drawMode,
      onCreateCustomGeometry,
      screenToSitePoint,
    ],
  );

  const drawModeButtons: Array<{
    mode: DrawMode;
    label: string;
    icon: ComponentType<{ className?: string }>;
    disabled?: boolean;
    disabledLabel?: string;
  }> = [
    { mode: "select", label: "Select", icon: MousePointer2 },
    { mode: "pan", label: "Pan", icon: Hand },
    {
      mode: "site",
      label: siteLocked ? "Site Locked" : "Draw Site Boundary",
      icon: Pentagon,
      disabled: Boolean(siteLocked),
      disabledLabel: "Unlock site to change boundary",
    },
    {
      mode: "polyline",
      label: "Add Line",
      icon: PencilLine,
      disabled: !canDrawObjects,
      disabledLabel: drawObjectsDisabledLabel,
    },
    {
      mode: "polygon",
      label: "Add Area",
      icon: Pentagon,
      disabled: !canDrawObjects,
      disabledLabel: drawObjectsDisabledLabel,
    },
    {
      mode: "rect",
      label: "Add Box",
      icon: Square,
      disabled: !canDrawObjects,
      disabledLabel: drawObjectsDisabledLabel,
    },
    {
      mode: "point",
      label: "Add Point",
      icon: MapPin,
      disabled: !canDrawObjects,
      disabledLabel: drawObjectsDisabledLabel,
    },
  ];

  useEffect(() => {
    if (!externalRectUndo) return;
    const handle = window.requestAnimationFrame(() => {
      setLastRectEdit(externalRectUndo);
    });
    return () => window.cancelAnimationFrame(handle);
  }, [externalRectUndo]);

  useEffect(() => {
    const handleUndo = (event: KeyboardEvent) => {
      const isUndo = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z";
      if (!isUndo) return;
      if (!lastPolylineEdit && !lastRectEdit) return;
      event.preventDefault();
      const polyTs = lastPolylineEdit?.ts ?? 0;
      const rectTs = lastRectEdit?.ts ?? 0;
      if (polyTs >= rectTs) {
        applyPolylineUndo();
      } else {
        applyRectUndo();
      }
    };
    window.addEventListener("keydown", handleUndo);
    return () => window.removeEventListener("keydown", handleUndo);
  }, [applyPolylineUndo, applyRectUndo, lastPolylineEdit, lastRectEdit]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("input, textarea, select, [contenteditable='true']")) return;
      if (event.key === "Escape") {
        if (draftPoints.length || drawMode !== "select") {
          event.preventDefault();
          clearDraftGeometry();
          setDrawMode("select");
        }
        return;
      }
      if (event.key === "Enter") {
        if (drawMode === "site" || drawMode === "polyline" || drawMode === "polygon" || drawMode === "rect") {
          event.preventDefault();
          finishDraftGeometry();
        }
        return;
      }
      if ((event.key === "Backspace" || event.key === "Delete") && selectedBuildingId && !selectedVertex) {
        const targetObject = buildingPlacements.find((item) => item.id === selectedBuildingId);
        if (!targetObject || targetObject.type === "site" || targetObject.locked) return;
        event.preventDefault();
        setLastRectEdit({
          id: targetObject.id,
          snapshot: { ...targetObject },
          action: "delete",
          ts: Date.now(),
        });
        onRemoveBuilding(targetObject.id);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [
    buildingPlacements,
    clearDraftGeometry,
    draftPoints.length,
    drawMode,
    finishDraftGeometry,
    onRemoveBuilding,
    selectedBuildingId,
    selectedVertex,
  ]);

  const handleBuildingMouseDown = useCallback(
    (
      event: React.MouseEvent<HTMLElement>,
      building: BuildingPlacement,
      mode: "move" | "resize" | "rotate" = "move",
    ) => {
      if (!allowEdits || building.type === "site") return;
      if (building.locked) return;
      if (selectedBuildingId && selectedBuildingId !== building.id) {
        onSelectBuilding(building.id);
        return;
      }
      const caps = getEditCapabilities(building);
      if (mode === "move" && !caps.movable) return;
      if (mode === "resize" && !caps.resizable) return;
      if (mode === "rotate" && !caps.rotatable) return;
      event.preventDefault();
      event.stopPropagation();
      if (
        (building.geometryType === "polyline" || building.geometryType === "polygon") &&
        Array.isArray(building.geometry)
      ) {
        if (mode === "move") {
          setLastPolylineEdit({
            id: building.id,
            geometry: (building.geometry as Array<[number, number]>).map((pt) => [pt[0], pt[1]]),
            x: building.x ?? 0,
            y: building.y ?? 0,
            w: building.w,
            d: building.d,
            ts: Date.now(),
          });
        }
      } else if (mode === "move" || mode === "resize" || mode === "rotate") {
        setLastRectEdit({
          id: building.id,
          snapshot: { ...building },
          action: "update",
          ts: Date.now(),
        });
      }
      setDraggingBuildingId(building.id);
      setDraggingMode(mode);
      setDraggingVertex(null);
      onSelectBuilding(building.id);
      const rect = event.currentTarget.getBoundingClientRect();
      setDragOffset({
        x: (event.clientX - rect.left) / Math.max(canvasView.scale, 0.1),
        y: (event.clientY - rect.top) / Math.max(canvasView.scale, 0.1),
      });
    },
    [allowEdits, canvasView.scale, getEditCapabilities, onSelectBuilding, selectedBuildingId],
  );

  const formatHoverValue = useCallback((value: number | null | undefined, suffix: string) => {
    if (value === null || value === undefined || Number.isNaN(value)) return null;
    return `${value.toFixed(2)}${suffix}`;
  }, []);
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
    const name = hoveredObject.label || type;
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
      { label: "Name", value: name },
      { label: "Type", value: type },
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
  }, [hoveredObject, lotHeight, lotWidth]);
  const overlayBounds = useMemo(() => {
    if (!previewContainerBounds) return null;
    return {
      left: 0,
      top: 0,
      width: previewContainerBounds.width,
      height: previewContainerBounds.height,
    };
  }, [previewContainerBounds]);

  const renderedCanonicalCount = useMemo(
    () =>
      buildingPlacements.filter(
        (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
      ).length,
    [buildingPlacements],
  );

  const overlayBoundsResolved = useMemo(() => {
    if (overlayBounds) return overlayBounds;
    if (!previewContainerBounds) return null;
    return previewContainerBounds;
  }, [overlayBounds, previewContainerBounds]);

  useEffect(() => {
    if (showHover) return;
    const handle = window.requestAnimationFrame(() => {
      setHoveredObjectId(null);
      setHoveredAnnotation(null);
      setHoverPoint(null);
      setHoveredVertex(null);
      setHoveredSegment(null);
    });
    return () => window.cancelAnimationFrame(handle);
  }, [showHover]);

  useEffect(() => {
    if (previewInteraction !== "static") return;
    const handle = window.requestAnimationFrame(() => {
      setDraggingBuildingId(null);
      setDraggingMode(null);
      setDraggingVertex(null);
      setRotateDragActive(false);
      setRotateDragStart(null);
    });
    return () => window.cancelAnimationFrame(handle);
  }, [previewInteraction]);

  useEffect(() => {
    if (!renderedCanonicalCount) return;
    if (overlayBoundsResolved) return;
    if (!previewRef.current) return;
    const handle = window.requestAnimationFrame(() => updateContainerBounds());
    return () => window.cancelAnimationFrame(handle);
  }, [overlayBoundsResolved, renderedCanonicalCount, updateContainerBounds]);

  useEffect(() => {
    if (!debugStats?.enabled) return;
    if (renderedCanonicalCount > 0 && !overlayBoundsResolved) {
      console.warn("[debug-preview] render-missing-overlay", {
        renderedCanonicalCount,
        lotWidth,
        lotHeight,
      });
    }
  }, [debugStats?.enabled, lotHeight, lotWidth, overlayBoundsResolved, renderedCanonicalCount]);

  const geocodeLat = geocode?.lat;
  const geocodeLng = geocode?.lng;
  const mapAnchor = useMemo(
    () =>
      geocodeLat && geocodeLng && lotWidth > 0 && lotHeight > 0
        ? {
            lat: geocodeLat,
            lng: geocodeLng,
            siteWidth: lotWidth,
            siteHeight: lotHeight,
            rotationDeg: siteRotationDeg,
          }
        : null,
    [geocodeLat, geocodeLng, lotHeight, lotWidth, siteRotationDeg],
  );
  const coordinateMode = resolveCoordinateMode(mapAnchor);

  const siteToLatLng = useCallback(
    (xFt: number, yFt: number) => {
      return mapAnchor ? siteToMapLngLat({ x: xFt, y: yFt }, mapAnchor) : null;
    },
    [mapAnchor],
  );

  const latLngToSite = useCallback(
    (lat: number, lng: number) => {
      return mapAnchor ? mapLngLatToSite({ lat, lng }, mapAnchor) : null;
    },
    [mapAnchor],
  );

  const sitePointToSvgPercent = useCallback(
    (point: [number, number]) => {
      const [x, y] = siteTupleToPercent(point, currentSiteSize);
      return `${x},${y}`;
    },
    [currentSiteSize],
  );

  const siteRectPercent = useCallback(
    (item: BuildingPlacement) => {
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
    },
    [currentSiteSize],
  );

  useEffect(() => {
    if (!mapAvailable) return;
    if (!mapContainerRef.current || mapRef.current) return;
    mapboxgl.accessToken = mapboxToken || "";
    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/satellite-streets-v12",
      center: [-95.9345, 41.2565],
      zoom: 16,
      pitch: mapPitch,
      bearing: mapBearing,
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
        map.setTerrain({ source: "mapbox-dem", exaggeration: 1.0 });
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
      setMapLoaded(false);
    };
  }, [mapAvailable, mapBearing, mapPitch, mapboxToken]);

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
  }, [allowMapInteraction, mapAvailable, mapLoaded]);

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
  }, [mapBearing, mapLoaded, mapPitch, showMap]);

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
  }, [debugStats?.enabled, showMap]);

  useEffect(() => {
    if (!showMap || mapLocked) return;
    if (previewInteraction !== "edit") return;
    const handleMove = (event: MouseEvent) => {
      if (!mapDragActiveRef.current || !mapDragRef.current) return;
      const map = mapRef.current;
      if (!map) return;
      const deltaX = event.clientX - mapDragRef.current.x;
      const deltaY = event.clientY - mapDragRef.current.y;
      mapDragRef.current = { x: event.clientX, y: event.clientY };
      map.panBy([deltaX, deltaY], { animate: false });
    };
    const handleUp = () => {
      mapDragActiveRef.current = false;
      mapDragRef.current = null;
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [mapLocked, previewInteraction, showMap]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded || !mapRef.current) return;
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
    const handleClick = (event: mapboxgl.MapMouseEvent) => {
      if (placementMode) {
        const sitePoint = latLngToSite(event.lngLat.lat, event.lngLat.lng);
        if (!sitePoint || !lotWidth || !lotHeight) {
          return;
        }
        const relative = siteToRelativePoint(sitePoint, currentSiteSize);
        const relativeX = relative.x;
        const relativeY = relative.y;
        console.debug("[placement] map-click", {
          sitePoint,
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
      setCursorSitePoint(sitePoint);
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
    };
  }, [currentSiteSize, latLngToSite, lotHeight, lotWidth, mapAvailable, mapLoaded, onMapScaleUpdate, onPlaceBuilding, onPlaceObject, placementMode, selectedBuildingId, onSelectBuilding, showHover, onViewportCenter, onViewportFootprint, siteLocked]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded || !mapRef.current) return;
    if (!mapCenterRequest) return;
    const center = mapRef.current.getCenter();
    if (onMapCenter) {
      onMapCenter({ lat: center.lat, lng: center.lng });
    }
  }, [mapAvailable, mapCenterRequest, mapLoaded, onMapCenter]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded) return;
    const handle = window.setTimeout(() => {
      const now = Date.now();
      if (now - lastMapResizeRef.current < 140) return;
      lastMapResizeRef.current = now;
      mapRef.current?.resize();
      if (previewFullscreenOpen) {
        fullscreenMapRef.current?.resize();
      }
    }, 160);
    return () => window.clearTimeout(handle);
  }, [mapAvailable, mapLoaded, previewFullscreenOpen]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "r") {
        if (previewInteraction !== "edit" || siteLocked) return;
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
  }, [previewInteraction, siteLocked]);

  useEffect(() => {
    if (previewInteraction !== "edit" || siteLocked) {
      const handle = window.requestAnimationFrame(() => {
        setRotateDragActive(false);
        setRotateDragStart(null);
      });
      return () => window.cancelAnimationFrame(handle);
    }
  }, [previewInteraction, siteLocked]);

  useEffect(() => {
    if (!showMap || !previewFullscreenOpen) return;
    if (!fullscreenContainerReady) return;
    if (!fullscreenMapContainerRef.current || fullscreenMapRef.current) return;
    mapboxgl.accessToken = mapboxToken || "";
    const center = mapRef.current?.getCenter();
    const zoom = mapRef.current?.getZoom();
    fullscreenMapRef.current = new mapboxgl.Map({
      container: fullscreenMapContainerRef.current,
      style: "mapbox://styles/mapbox/satellite-streets-v12",
      center: center ? [center.lng, center.lat] : [-95.9345, 41.2565],
      zoom: typeof zoom === "number" ? zoom : 16,
      pitch: mapPitch,
      bearing: mapBearing,
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
  }, [fullscreenContainerReady, mapBearing, mapPitch, mapboxToken, previewFullscreenOpen, showMap]);

  useEffect(() => {
    if (previewFullscreenOpen) return;
    if (!fullscreenMapRef.current) return;
    fullscreenMapRef.current.remove();
    fullscreenMapRef.current = null;
  }, [previewFullscreenOpen]);

  useEffect(() => {
    if (!showMap) return;
    if (previewFullscreenOpen) return;
    if (!fullscreenMapRef.current || !mapRef.current) return;
    const center = fullscreenMapRef.current.getCenter();
    const zoom = fullscreenMapRef.current.getZoom();
    mapRef.current.jumpTo({ center: [center.lng, center.lat], zoom, pitch: mapPitch, bearing: mapBearing });
  }, [mapBearing, mapPitch, previewFullscreenOpen, showMap]);

  useEffect(() => {
    if (!mapAvailable) return;
    if (!geocode?.lng || !geocode?.lat) return;
    const center: [number, number] = [geocode.lng, geocode.lat];
    mapRef.current?.flyTo({ center, zoom: 17 });
    fullscreenMapRef.current?.flyTo({ center, zoom: 17 });
  }, [geocode?.lat, geocode?.lng, mapAvailable]);

  useEffect(() => {
    if (!mapAvailable || !mapLoaded || !mapRef.current || !geocode?.lat || !geocode?.lng) return;
    if (!fitToSiteRequest || !lotWidth || !lotHeight) return;
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
    mapRef.current.fitBounds(bounds, { padding: 80, duration: 650 });
  }, [siteToLatLng, fitToSiteRequest, geocode?.lat, geocode?.lng, lotHeight, lotWidth, mapAvailable, mapLoaded]);

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
  }, [alignToRoadRequest, mapAvailable, mapLoaded, onSetSiteRotationDeg]);

  const buildParkingModules = useCallback((item: BuildingPlacement, accessPoints: Array<{ x: number; y: number }>) => {
    const x = item.x ?? 0;
    const y = item.y ?? 0;
    const params = (item.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
    const stallWidth = Number.isFinite(params.stallWidth) ? Number(params.stallWidth) : 9;
    const stallDepth = Number.isFinite(params.stallDepth) ? Number(params.stallDepth) : 18;
    const aisleWidth = Number.isFinite(params.aisleWidth) ? Number(params.aisleWidth) : 24;
    const adaAisleWidth = Number.isFinite(params.adaAisleWidth) ? Number(params.adaAisleWidth) : 8;
    const adaCount = Number.isFinite(params.adaCount) ? Number(params.adaCount) : 0;
    const compactCount = Number.isFinite(params.compactCount) ? Number(params.compactCount) : 0;
    const compactWidth = Number.isFinite(params.compactWidth) ? Number(params.compactWidth) : 8;
    const angleDeg = Number.isFinite(params.angleDeg) ? Number(params.angleDeg) : 90;
    const loading = params.loading === "single" ? "single" : "double";
    const useMixedAngles = Boolean(params.useMixedAngles);
    const compactZone = params.compactZone !== false;
    const angleRad = (Math.max(Math.min(angleDeg, 89), 0) * Math.PI) / 180;
    const depthAdj = stallDepth / Math.cos(angleRad || 0.0001);
    const moduleDepth = depthAdj * (loading === "double" ? 2 : 1) + aisleWidth;
    const scale = item.d < moduleDepth ? item.d / moduleDepth : 1;
    const scaledStall = depthAdj * scale;
    const scaledAisle = aisleWidth * scale;
    const rows = loading === "double" ? 2 : 1;
    const desiredStalls = Math.max(item.stallCount ?? 0, adaCount + compactCount);
    const shift = Math.tan(angleRad || 0.0001) * scaledStall;
    let moduleCount = 1;
    if (desiredStalls > 0) {
      for (let candidate = 1; candidate <= 6; candidate += 1) {
        const moduleWidth = item.w / candidate;
        const stallsPerRow = Math.max(1, Math.floor((moduleWidth - Math.abs(shift)) / stallWidth));
        const capacity = stallsPerRow * rows * candidate;
        if (capacity >= desiredStalls) {
          moduleCount = candidate;
          break;
        }
        moduleCount = candidate;
      }
    }
    const modules: Array<{
      id: string;
      angle: number;
      isAdaModule: boolean;
      isCompactModule: boolean;
      bounds: Array<[number, number]>;
      aisleLine: Array<[number, number]>;
      stallPolygons: Array<{ points: Array<[number, number]>; kind: "standard" | "ada" | "compact" | "ada_aisle" }>;
      stripeLines: Array<Array<[number, number]>>;
    }> = [];
    const metaCols = Number((item.meta as { parkingModuleCols?: number })?.parkingModuleCols || 0);
    const metaRows = Number((item.meta as { parkingModuleRows?: number })?.parkingModuleRows || 0);
    const cols = metaCols > 0 ? metaCols : Math.max(1, Math.ceil(Math.sqrt(moduleCount)));
    const rowsOfModules = metaRows > 0 ? metaRows : Math.max(1, Math.ceil(moduleCount / cols));
    const gapScale = Math.max(0.02, Math.min(0.06, (stallWidth + aisleWidth) / Math.max(item.w, 1)));
    const moduleGapX = Math.min(8, Math.max(3, item.w * gapScale));
    const moduleGapY = Math.min(10, Math.max(4, item.d * gapScale));
    const totalGapX = cols > 1 ? moduleGapX * (cols - 1) : 0;
    const totalGapY = rowsOfModules > 1 ? moduleGapY * (rowsOfModules - 1) : 0;
    const availableW = Math.max(item.w - totalGapX, item.w * 0.7);
    const availableD = Math.max(item.d - totalGapY, item.d * 0.7);
    const moduleWidth = availableW / cols;
    const moduleDepthLocal = availableD / rowsOfModules;
    const offsetX = x + (item.w - (moduleWidth * cols + totalGapX)) / 2;
    const offsetY = y + (item.d - (moduleDepthLocal * rowsOfModules + totalGapY)) / 2;
    const totalModules = cols * rowsOfModules;
    const moduleAngles: number[] = [];
    for (let row = 0; row < rowsOfModules; row += 1) {
      for (let col = 0; col < cols; col += 1) {
        if (!useMixedAngles) {
          moduleAngles.push(angleDeg);
          continue;
        }
        const edge = col === 0 || col === cols - 1;
        const inner = col === 1 || col === cols - 2;
        const angle = edge ? 45 : inner ? 60 : angleDeg;
        moduleAngles.push(angle);
      }
    }
    const moduleCenters: Array<{ x: number; y: number }> = [];
    for (let r = 0; r < rowsOfModules; r += 1) {
      for (let c = 0; c < cols; c += 1) {
        moduleCenters.push({
          x: offsetX + c * (moduleWidth + moduleGapX) + moduleWidth / 2,
          y: offsetY + r * (moduleDepthLocal + moduleGapY) + moduleDepthLocal / 2,
        });
      }
    }
    const sortedModuleIdxByAccess = moduleCenters
      .map((center, idx) => {
        const minDist = accessPoints.length
          ? Math.min(...accessPoints.map((pt) => Math.hypot(center.x - pt.x, center.y - pt.y)))
          : 0;
        return { idx, dist: minDist };
      })
      .sort((a, b) => a.dist - b.dist)
      .map((entry) => entry.idx);
    const moduleCapacities = moduleAngles.map((angle) => {
      const angleRadModule = (Math.max(Math.min(angle, 89), 0) * Math.PI) / 180;
      const shiftModule = Math.tan(angleRadModule || 0.0001) * scaledStall;
      const stallsPerRow = Math.max(1, Math.floor((moduleWidth - Math.abs(shiftModule)) / stallWidth));
      return stallsPerRow * rows;
    });
    const buildModuleSet = (count: number, order: number[], fromEnd = false) => {
      const indices = fromEnd ? [...order].reverse() : order;
      let remaining = count;
      const set = new Set<number>();
      indices.forEach((idx) => {
        if (remaining <= 0) return;
        set.add(idx);
        remaining -= moduleCapacities[idx] ?? 0;
      });
      return set;
    };
    const adaPreferredModules = adaCount > 0 ? buildModuleSet(adaCount, sortedModuleIdxByAccess) : new Set<number>();
    const compactPreferredModules =
      compactCount > 0 && compactZone ? buildModuleSet(compactCount, sortedModuleIdxByAccess, true) : new Set<number>();
    let remainingAda = adaCount;
    let remainingCompact = compactCount;
    for (let m = 0; m < totalModules; m += 1) {
      const row = Math.floor(m / cols);
      const col = m % cols;
      const moduleX = offsetX + col * (moduleWidth + moduleGapX);
      const moduleY = offsetY + row * (moduleDepthLocal + moduleGapY);
      const angleForModule = moduleAngles[m] ?? angleDeg;
      const angleRadModule = (Math.max(Math.min(angleForModule, 89), 0) * Math.PI) / 180;
      const depthVecTop = {
        x: Math.sin(angleRadModule) * scaledStall,
        y: Math.cos(angleRadModule) * scaledStall,
      };
      const depthVecBottom = {
        x: -Math.sin(angleRadModule) * scaledStall,
        y: Math.cos(angleRadModule) * scaledStall,
      };
      const shiftModule = depthVecTop.x;
      const stallsPerRow = Math.max(1, Math.floor((moduleWidth - Math.abs(shiftModule)) / stallWidth));
      const stallW = (moduleWidth - Math.abs(shiftModule)) / stallsPerRow;
      const aisleY =
        loading === "double"
          ? moduleY + (moduleDepthLocal - scaledAisle) / 2
          : moduleY + scaledStall + scaledAisle / 2;
      const aisleLine: Array<[number, number]> = [
        [moduleX + 2, aisleY],
        [moduleX + moduleWidth - 2, aisleY],
      ];
      const stallPolygons: Array<{ points: Array<[number, number]>; kind: "standard" | "ada" | "compact" | "ada_aisle" }> = [];
      const stripeLines: Array<Array<[number, number]>> = [];
      const moduleBounds: Array<[number, number]> = [
        [moduleX, moduleY],
        [moduleX + moduleWidth, moduleY],
        [moduleX + moduleWidth, moduleY + moduleDepthLocal],
        [moduleX, moduleY + moduleDepthLocal],
        [moduleX, moduleY],
      ];
      const isAdaModule = adaPreferredModules.has(m);
      const isCompactModule = compactZone ? compactPreferredModules.has(m) : false;
      const depthLen = Math.hypot(depthVecTop.x, depthVecTop.y) || 1;
      const depthUnitTop = { x: depthVecTop.x / depthLen, y: depthVecTop.y / depthLen };
      const depthUnitBottom = { x: depthVecBottom.x / depthLen, y: depthVecBottom.y / depthLen };
      const inset = Math.min(0.35, stallW * 0.06);
      const clampWidth = (value: number) => Math.max(Math.min(value, stallW - inset * 2), stallW * 0.7);
      const buildStallPoly = (
        baseX: number,
        baseY: number,
        width: number,
        depthUnit: { x: number; y: number },
        depth: number,
      ): Array<[number, number]> => {
        const ux = 1;
        const uy = 0;
        const w = Math.max(width - inset * 2, width * 0.8);
        const d = Math.max(depth - inset * 2, depth * 0.8);
        const startX = baseX + inset * (ux + depthUnit.x);
        const startY = baseY + inset * (uy + depthUnit.y);
        const p0: [number, number] = [startX, startY];
        const p1: [number, number] = [startX + w * ux, startY + w * uy];
        const p2: [number, number] = [p1[0] + d * depthUnit.x, p1[1] + d * depthUnit.y];
        const p3: [number, number] = [p0[0] + d * depthUnit.x, p0[1] + d * depthUnit.y];
        return [p0, p1, p2, p3, p0];
      };
      for (let i = 0; i < stallsPerRow; i += 1) {
        let useAda = false;
        let useCompact = false;
        let includeAdaAisle = false;
        if (remainingAda > 0 && isAdaModule) {
          useAda = true;
          includeAdaAisle = true;
          remainingAda -= 1;
        } else if (remainingCompact > 0 && isCompactModule) {
          useCompact = true;
          remainingCompact -= 1;
        } else if (remainingAda > 0 && !adaPreferredModules.size) {
          useAda = true;
          includeAdaAisle = true;
          remainingAda -= 1;
        } else if (remainingCompact > 0 && !compactZone) {
          useCompact = true;
          remainingCompact -= 1;
        }
        const rowOffsetTop = depthVecTop.x > 0 ? 0 : Math.abs(depthVecTop.x);
        const rowOffsetBottom = depthVecBottom.x > 0 ? 0 : Math.abs(depthVecBottom.x);
        const baseXTop = moduleX + rowOffsetTop + i * stallW;
        const baseXBottom = moduleX + rowOffsetBottom + i * stallW;
        const baseYTop = moduleY;
        const baseYBottom = moduleY + moduleDepthLocal - scaledStall;
        const stallWidthUsed = useAda ? clampWidth(stallWidth) : useCompact ? clampWidth(compactWidth) : clampWidth(stallW);
        const topPoly = buildStallPoly(baseXTop, baseYTop, stallWidthUsed, depthUnitTop, scaledStall);
        stallPolygons.push({
          points: topPoly,
          kind: useAda ? "ada" : useCompact ? "compact" : "standard",
        });
        stripeLines.push([
          [baseXTop + stallWidthUsed, baseYTop],
          [baseXTop + stallWidthUsed + depthVecTop.x, baseYTop + depthVecTop.y],
        ]);
        if (useAda && includeAdaAisle) {
          const aisleWidth = Math.max(Math.min(adaAisleWidth, stallW - stallWidthUsed), 0);
          if (aisleWidth > 0.1) {
            const aislePoly = buildStallPoly(
              baseXTop + stallWidthUsed,
              baseYTop,
              aisleWidth,
              depthUnitTop,
              scaledStall,
            );
            stallPolygons.push({ points: aislePoly, kind: "ada_aisle" });
          }
        }
        if (loading === "double") {
          const bottomPoly = buildStallPoly(baseXBottom, baseYBottom, stallWidthUsed, depthUnitBottom, scaledStall);
          stallPolygons.push({
            points: bottomPoly,
            kind: useAda ? "ada" : useCompact ? "compact" : "standard",
          });
          stripeLines.push([
            [baseXBottom + stallWidthUsed, baseYBottom],
            [baseXBottom + stallWidthUsed + depthVecBottom.x, baseYBottom + depthVecBottom.y],
          ]);
          if (useAda && includeAdaAisle) {
            const aisleWidth = Math.max(Math.min(adaAisleWidth, stallW - stallWidthUsed), 0);
            if (aisleWidth > 0.1) {
              const bottomAisle = buildStallPoly(
                baseXBottom + stallWidthUsed,
                baseYBottom,
                aisleWidth,
                depthUnitBottom,
                scaledStall,
              );
              stallPolygons.push({ points: bottomAisle, kind: "ada_aisle" });
            }
          }
        }
      }
      const moduleId = `${item.id}-module-${m}`;
      modules.push({
        id: moduleId,
        angle: angleForModule,
        isAdaModule,
        isCompactModule,
        bounds: moduleBounds,
        aisleLine,
        stallPolygons,
        stripeLines,
      });
    }
    return modules;
  }, []);

  useEffect(() => {
    if (!showMap || !mapLoaded || !mapRef.current) return;
    if (!geocodeLat || !geocodeLng || !lotWidth || !lotHeight) return;

    const placedObjects = buildingPlacements.filter(
      (item) => item.type !== "site" && item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
    );

    if (debugStats?.enabled) {
      console.debug("[debug-preview] render-layer", {
        canonicalCount: buildingPlacements.length,
        placedCount: placedObjects.length,
        suggestedCount: suggestedPlacements.length,
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
    const basins = placedObjects.filter((item) => item.type === "basin");
    const customAreas = placedObjects.filter(
      (item) =>
        (item.type === "custom" || resolveVisualKind(item) === "landscape") &&
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

    const parkingModules = parking.flatMap((item) => buildParkingModules(item, accessPoints));

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
      ensureLayer("civora-sidewalks-line", "civora-sidewalks", "line", {
        "line-color": "#0f766e",
        "line-width": 2,
        "line-dasharray": [1, 1],
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
    };

    updateMap(mapRef.current);
    updateMap(fullscreenMapRef.current);
  }, [
    buildingPlacements,
    analysisPaths,
    buildParkingModules,
    debugStats?.enabled,
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
    suggestedPlacements.length,
    surveyPoints,
  ]);

  useEffect(() => {
    const handleUpdate = () => {
      if (previewResizeRafRef.current !== null) return;
      previewResizeRafRef.current = window.requestAnimationFrame(() => {
        previewResizeRafRef.current = null;
        updateContainerBounds();
        if (showMap && previewRef.current) {
          const rect = previewRef.current.getBoundingClientRect();
          const nextBounds = { left: 0, top: 0, width: rect.width, height: rect.height };
          setPreviewImageBounds((current) =>
            current &&
            Math.abs(current.width - nextBounds.width) < 0.5 &&
            Math.abs(current.height - nextBounds.height) < 0.5
              ? current
              : nextBounds,
          );
          const nextSize = { w: Math.round(rect.width), h: Math.round(rect.height) };
          const prev = previewSizeRef.current;
          if (!prev || prev.w !== nextSize.w || prev.h !== nextSize.h) {
            previewSizeRef.current = nextSize;
            const now = Date.now();
            if (now - lastMapResizeRef.current > 120) {
              lastMapResizeRef.current = now;
              mapRef.current?.resize();
            }
          }
        } else if (planPreviewUrl && showGeneratedPlan) {
          updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds);
        } else {
          setPreviewImageBounds(null);
        }
      });
    };
    handleUpdate();
    if (!previewRef.current) return;
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleUpdate) : null;
    if (observer) observer.observe(previewRef.current);
    window.addEventListener("resize", handleUpdate);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener("resize", handleUpdate);
      if (previewResizeRafRef.current !== null) {
        cancelAnimationFrame(previewResizeRafRef.current);
        previewResizeRafRef.current = null;
      }
    };
  }, [planPreviewUrl, previewMode, showGeneratedPlan, showMap, updateContainerBounds, updateImageBounds]);

  useEffect(() => {
    if (!previewFullscreenOpen) return;
    const handleUpdate = () => {
      if (fullscreenResizeRafRef.current !== null) return;
      fullscreenResizeRafRef.current = window.requestAnimationFrame(() => {
        fullscreenResizeRafRef.current = null;
        if (showMap && fullscreenRef.current) {
          const rect = fullscreenRef.current.getBoundingClientRect();
          const nextBounds = { left: 0, top: 0, width: rect.width, height: rect.height };
          setFullscreenImageBounds((current) =>
            current &&
            Math.abs(current.width - nextBounds.width) < 0.5 &&
            Math.abs(current.height - nextBounds.height) < 0.5
              ? current
              : nextBounds,
          );
          const nextSize = { w: Math.round(rect.width), h: Math.round(rect.height) };
          const prev = fullscreenSizeRef.current;
          if (!prev || prev.w !== nextSize.w || prev.h !== nextSize.h) {
            fullscreenSizeRef.current = nextSize;
            const now = Date.now();
            if (now - lastMapResizeRef.current > 120) {
              lastMapResizeRef.current = now;
              fullscreenMapRef.current?.resize();
            }
          }
        } else if (planPreviewUrl) {
          updateImageBounds(fullscreenRef, fullscreenImageRef, setFullscreenImageBounds);
        }
      });
    };
    handleUpdate();
    if (!fullscreenRef.current) return;
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleUpdate) : null;
    if (observer) observer.observe(fullscreenRef.current);
    window.addEventListener("resize", handleUpdate);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener("resize", handleUpdate);
      if (fullscreenResizeRafRef.current !== null) {
        cancelAnimationFrame(fullscreenResizeRafRef.current);
        fullscreenResizeRafRef.current = null;
      }
    };
  }, [planPreviewUrl, previewFullscreenOpen, showMap, updateImageBounds]);
  const [focusTransform, setFocusTransform] = useState<{ scale: number; tx: number; ty: number } | null>(null);
  const updateFocusTransform = useCallback((nextTransform: { scale: number; tx: number; ty: number }) => {
    setFocusTransform((current) =>
      current &&
      Math.abs(current.scale - nextTransform.scale) < 0.001 &&
      Math.abs(current.tx - nextTransform.tx) < 0.001 &&
      Math.abs(current.ty - nextTransform.ty) < 0.001
        ? current
        : nextTransform,
    );
  }, []);

  useEffect(() => {
    if (!focusDetectedId) return;
    const target = suggestedPlacements.find((item) => item.id === focusDetectedId);
    let frame: number | null = null;
    if (target) {
      frame = window.requestAnimationFrame(() => {
        setHoveredObjectId((current) => (current === target.id ? current : target.id));
        onSelectBuilding(target.id);
      });
    }
    if (onClearFocusDetected) {
      const timer = window.setTimeout(() => onClearFocusDetected(), 400);
      return () => {
        if (frame !== null) window.cancelAnimationFrame(frame);
        window.clearTimeout(timer);
      };
    }
    return () => {
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
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
    const nextTransform = { scale: Math.min(Math.max(scale, 1), 3), tx: centerX, ty: centerY };
    const handle = window.requestAnimationFrame(() => updateFocusTransform(nextTransform));
    if (onClearFocusObject) {
      const timer = window.setTimeout(() => onClearFocusObject(), 500);
      return () => {
        window.cancelAnimationFrame(handle);
        window.clearTimeout(timer);
      };
    }
    return () => window.cancelAnimationFrame(handle);
  }, [focusObjectId, buildingPlacements, lotHeight, lotWidth, onClearFocusObject, updateFocusTransform]);

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
    const nextTransform = { scale: Math.min(Math.max(scale, 1), 3), tx: centerX, ty: centerY };
    const handle = window.requestAnimationFrame(() => updateFocusTransform(nextTransform));
    return () => window.cancelAnimationFrame(handle);
  }, [analysisHighlight, analysisPaths, buildingPlacements, lotHeight, lotWidth, suggestedPlacements, updateFocusTransform]);
  const showParkingAnalysis = Boolean(analysisPaths && analysisPaths.length);
  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white/92 p-3 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.45)] backdrop-blur">
      <div className="mb-3 flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-md bg-slate-950 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
              Design Canvas
            </span>
            <span className="inline-flex items-center rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              {previewQuality === "high" ? "High Quality" : "Standard"}
            </span>
            {isHighQuality ? (
              <span
                data-testid="high-quality-preview-only-label"
                className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-800"
              >
                Visual preview only — canonical geometry unchanged. Not engineering evidence.
              </span>
            ) : null}
            <span className="inline-flex items-center rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              {previewMode.toUpperCase()}
            </span>
            <span
              className="inline-flex items-center rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500"
              data-testid="coordinate-mode-label"
            >
              {coordinateModeLabel(coordinateMode)}
            </span>
          </div>
          <p className="max-w-3xl text-xs text-slate-500">
            Visual anchoring keeps objects consistent in the model view. High Quality visuals are communication
            previews only and never construction evidence. Civora does not stamp, seal, sign, certify, approve
            construction, submit construction documents, or act as engineer of record.
          </p>
          {previewTotalPhaseCount > 0 && previewCompletedPhaseCount < previewTotalPhaseCount ? (
            <div className="inline-flex max-w-3xl items-start rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
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
          {analysisHighlight ? (
            <div className="inline-flex max-w-3xl items-start rounded-lg border border-slate-200 bg-white/90 px-3 py-2 text-xs text-slate-600">
              <div>
                <p className="font-semibold text-slate-800">Parking logic notes</p>
                <p className="mt-1">
                  ADA modules are placed closest to access paths, compact modules are grouped farther away, and mixed
                  angles apply 45° at edges, 60° inside, and the main angle in core zones.
                </p>
              </div>
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2 xl:justify-end">
          {showMap ? (
            <button
              type="button"
              onClick={() => setMapLocked((prev) => !prev)}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition ${
                mapLocked
                  ? "border-slate-900 bg-slate-950 text-white"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              {mapLocked ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
              {mapLocked ? "Unlock Map" : "Lock Map"}
            </button>
          ) : null}
          {analysisHighlight ? (
            <button
              type="button"
              onClick={() => {
                setFocusTransform(null);
                onClearHighlights?.();
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              <X className="h-4 w-4" />
              Clear highlights
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => {
              setFocusTransform(null);
              onResetView?.();
            }}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            <RotateCcw className="h-4 w-4" />
            Reset view
          </button>
          <button
            type="button"
            onClick={onRefreshPreview}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh Preview
          </button>
          {planPreviewUrl || showMap ? (
            <button
              type="button"
              onClick={onOpenFullscreen}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              <Maximize2 className="h-4 w-4" />
              Fullscreen Preview
            </button>
          ) : null}
          <button
            type="button"
            onClick={onExportDxf}
            disabled={busy || Boolean(exportBlockReason)}
            title={exportBlockReason || "Download a DXF review export"}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            Export DXF
          </button>
          <button
            type="button"
            onClick={onExportReport}
            disabled={busy || Boolean(exportBlockReason)}
            title={exportBlockReason || "Download an engineer-review package report"}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileText className="h-4 w-4" />
            Export Report
          </button>
          {exportBlockReason ? (
            <p className="w-full text-right text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700">
              Export blocked: {exportBlockReason}
            </p>
          ) : null}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white/85 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Preview Mode</span>
              <button
                type="button"
                data-testid="preview-mode-2d"
                onClick={() => onSetPreviewMode("2d")}
                className={`rounded-lg border px-2.5 py-1 ${
                  previewMode === "2d"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                2D
              </button>
              <button
                type="button"
                data-testid="preview-mode-3d"
                onClick={() => {
                  if (!canUse3D) return;
                  onSetPreviewMode("3d");
                }}
                className={`rounded-lg border px-2.5 py-1 ${
                  previewMode === "3d"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
                disabled={!canUse3D}
              >
                3D
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Interaction</span>
              <button
                type="button"
                onClick={() => onSetPreviewInteraction("static")}
                className={`rounded-lg border px-2.5 py-1 ${
                  previewInteraction === "static"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Static
              </button>
              <button
                type="button"
                data-testid="preview-interaction-edit"
                aria-label="Set preview interaction to edit"
                onClick={() => {
                  if (previewInteraction === "edit") return;
                  onQueuePreviewRefresh("Entering edit mode...");
                  onSetPreviewInteraction("edit");
                }}
                className={`rounded-lg border px-2.5 py-1 ${
                  previewInteraction === "edit"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Edit
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Quality</span>
              <button
                type="button"
                data-testid="preview-quality-standard"
                onClick={() => {
                  if (previewQuality === "standard") return;
                  onQueuePreviewRefresh("Requesting standard-quality preview...");
                  onSetPreviewQuality("standard");
                }}
                className={`rounded-lg border px-2.5 py-1 ${
                  previewQuality === "standard"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Standard
              </button>
              <button
                type="button"
                data-testid="preview-quality-high"
                onClick={() => {
                  if (previewQuality === "high") return;
                  onQueuePreviewRefresh("Requesting high-quality preview...");
                  onSetPreviewQuality("high");
                }}
                className={`rounded-lg border px-2.5 py-1 ${
                  previewQuality === "high"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                High
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Legend</span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: legendPalette.building }} />
                Buildings
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: legendPalette.road }} />
                Roads
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: legendPalette.parking }} />
                Parking
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: legendPalette.drainage }} />
                Drainage
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: legendPalette.utilities }} />
                Utilities
              </span>
              {cursorSitePoint ? (
                <span className="ml-2 flex items-center gap-2 text-[11px] text-slate-500">
                  <span className="font-semibold text-slate-700">Cursor</span>
                  X {cursorSitePoint.x.toFixed(1)} ft • Y {cursorSitePoint.y.toFixed(1)} ft
                </span>
              ) : null}
            </div>
          </div>
          {previewMode === "2d" ? (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white/85 px-3 py-2">
              <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                <span className="mr-1">Draw</span>
                {drawModeButtons.map((item) => {
                  const Icon = item.icon;
                  const active = drawMode === item.mode;
                  const disabled = Boolean(item.disabled);
                  return (
                    <button
                      key={item.mode}
                      type="button"
                      title={disabled ? item.disabledLabel ?? item.label : item.label}
                      aria-label={item.label}
                      disabled={disabled}
                      onClick={() => {
                        if (disabled) return;
                        setDrawMode(item.mode);
                        clearDraftGeometry();
                        if (item.mode !== "select") {
                          onSetPreviewInteraction("edit");
                        }
                      }}
                      className={`inline-flex min-h-8 items-center justify-center gap-1.5 rounded-md border px-2 py-1 transition ${
                        active
                          ? "border-slate-900 bg-slate-950 text-white"
                          : disabled
                            ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-300"
                          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      <span className="text-[10px] leading-none">{item.label}</span>
                    </button>
                  );
                })}
              </div>
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-slate-600">
                  {drawMode === "site" && draftPoints.length
                    ? "Draft site boundary"
                    : siteLocked
                      ? "Locked canonical site"
                      : drawMode === "site"
                        ? "Draft site boundary mode"
                        : draftPoints.length
                          ? "Draft geometry"
                          : canDrawObjects
                            ? "Canonical project geometry after finish"
                            : drawObjectsDisabledLabel}
                </span>
                <button
                  type="button"
                  onClick={() => setCanvasView({ scale: 1, offsetX: 0, offsetY: 0 })}
                  className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-slate-600 hover:bg-slate-50"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Zoom
                </button>
                <button
                  type="button"
                  aria-label="Use canvas edit tool"
                  onClick={() => onSetPreviewInteraction("edit")}
                  className={`inline-flex h-8 items-center gap-1.5 rounded-md border px-2 ${
                    allowEdits
                      ? "border-slate-900 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  Edit
                </button>
                <button
                  type="button"
                  disabled={!selectedDeletableObject}
                  title={
                    selectedObject?.locked
                      ? "Unlock the selected object before deleting"
                      : selectedObject
                        ? "Delete selected object"
                        : "Select an unlocked object to delete"
                  }
                  onClick={() => {
                    if (!selectedDeletableObject) return;
                    const targetObject = buildingPlacements.find((item) => item.id === selectedDeletableObject.id);
                    if (targetObject) {
                      setLastRectEdit({
                        id: targetObject.id,
                        snapshot: { ...targetObject },
                        action: "delete",
                        ts: Date.now(),
                      });
                    }
                    onRemoveBuilding(selectedDeletableObject.id);
                  }}
                  className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-300"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
                <button
                  type="button"
                  onClick={onOpenFullscreen}
                  className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-slate-600 hover:bg-slate-50"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                  More
                </button>
                <span className="min-w-12 text-right">{Math.round(canvasView.scale * 100)}%</span>
                {draftPoints.length ? (
                  <>
                    {drawMode !== "rect" ? (
                      <button
                        type="button"
                        onClick={finishDraftGeometry}
                        disabled={draftPointCount < finishDraftMinPoints}
                        title={finishDraftBlockedReason ?? "Finish drawn geometry"}
                        className="inline-flex h-8 items-center rounded-md border border-slate-900 bg-slate-950 px-2 text-white disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                      >
                        Finish
                      </button>
                    ) : null}
                    {finishDraftBlockedReason ? (
                      <span className="max-w-56 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700">
                        {finishDraftBlockedReason}
                      </span>
                    ) : null}
                    <button
                      type="button"
                      onClick={clearDraftGeometry}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                      aria-label="Clear draft geometry"
                      title="Clear draft geometry"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </>
                ) : null}
              </div>
            </div>
          ) : null}
          {show3D ? (
            preview3DEffectiveItems.length ? (
              <div
                className="relative cursor-pointer"
                onClick={onOpenFullscreen}
              >
                <Preview3DCanvas
                  items={preview3DEffectiveItems}
                  interactive={allowEdits}
                  previewQuality={previewQuality}
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
              <div className="relative flex min-h-0 w-full flex-1 items-center justify-center overflow-hidden rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)]">
                <div className="pointer-events-none absolute left-6 top-6 rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 shadow-sm">
                  3D geometry not ready yet
                </div>
              </div>
            )
          ) : (
            <div
              ref={previewRef}
              data-testid="preview-drawing-surface"
              className={`relative flex w-full flex-1 min-h-[320px] items-center justify-center rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)] ${
                previewFullscreenOpen && showMap
                  ? "fixed inset-0 z-[120] rounded-none bg-slate-950 p-0"
                  : ""
              } ${
                placementMode || allowEdits ? "cursor-crosshair" : "cursor-default"
              }`}
              style={{ touchAction: drawMode === "select" ? "auto" : "none" }}
              onDragOver={(event) => {
                event.preventDefault();
              }}
              onDrop={(event) => {
                event.preventDefault();
                const payload = event.dataTransfer?.getData("civora-object-id");
                if (!payload) return;
                const rect = previewRef.current?.getBoundingClientRect();
                const bounds = overlayBoundsResolved ?? {
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
                if (allowMapInteraction) return;
                if (rotateDragStart && previewContainerBounds && onSetSiteRotationDeg) {
                  const deltaX = event.clientX - rotateDragStart.x;
                  const width = Math.max(previewContainerBounds.width, 1);
                  const deltaDeg = (deltaX / width) * 180;
                  const nextValue = rotateDragStart.value + deltaDeg;
                  onSetSiteRotationDeg(Math.max(-180, Math.min(180, nextValue)));
                  return;
                }
                if (canvasPanStart) {
                  setCanvasView((prev) => ({
                    ...prev,
                    offsetX: canvasPanStart.offsetX + event.clientX - canvasPanStart.x,
                    offsetY: canvasPanStart.offsetY + event.clientY - canvasPanStart.y,
                  }));
                  return;
                }
                if (drawMode !== "select" && drawMode !== "pan" && overlayBoundsResolved) {
                  const sitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, overlayBoundsResolved);
                  setDraftPreviewPoint(sitePoint ? [sitePoint.x, sitePoint.y] : null);
                  if (sitePoint) {
                    setCursorSitePoint({ x: sitePoint.x, y: sitePoint.y });
                  }
                  return;
                }
                if (overlayBoundsResolved) {
                  updateDraggedBuilding(event, overlayBoundsResolved);
                }
                if (showHover) {
                  resolveHover(event, previewRef, overlayBoundsResolved, setHoverPoint);
                } else {
                  if (hoverPoint) setHoverPoint(null);
                  if (hoveredObjectId) setHoveredObjectId(null);
                  if (hoveredAnnotation) setHoveredAnnotation(null);
                }
                if (showHover && overlayBoundsResolved && lotWidth > 0 && lotHeight > 0 && previewRef.current) {
                  const sitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, overlayBoundsResolved);
                  setCursorSitePoint(sitePoint ? { x: sitePoint.x, y: sitePoint.y } : null);
                } else if (!showHover) {
                  setCursorSitePoint(null);
                } else {
                  setCursorSitePoint(null);
                }
              }}
              onMouseLeave={() => {
                setHoveredAnnotation(null);
                setHoveredObjectId(null);
                setHoverPoint(null);
                setCursorSitePoint(null);
                setDraggingBuildingId(null);
                setDraggingMode(null);
                setCanvasPanStart(null);
                setDraftPreviewPoint(null);
              }}
              onMouseUp={() => {
                setDraggingBuildingId(null);
                setDraggingMode(null);
                setRotateDragStart(null);
                setCanvasPanStart(null);
              }}
              onClick={(event) => {
                if (allowMapInteraction) return;
                if (drawMode !== "select") {
                  if (handleDrawPointer(event, overlayBoundsResolved)) return;
                }
                if (placementMode) {
                  resolvePlacement(event, previewRef, overlayBoundsResolved);
                  return;
                }
                if (!showHover || !hoveredAnnotation) return;
                setPinnedAnnotation((prev) =>
                  prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
                );
              }}
              onDoubleClick={(event) => {
                if (drawMode !== "site" && drawMode !== "polyline" && drawMode !== "polygon" && drawMode !== "rect") return;
                event.preventDefault();
                event.stopPropagation();
                finishDraftGeometry();
              }}
              onWheel={(event) => {
                if (!allowEdits || !overlayBoundsResolved || showMap) return;
                event.preventDefault();
                const nextScale = Math.min(
                  Math.max(canvasView.scale + (event.deltaY < 0 ? 0.12 : -0.12), 0.55),
                  4,
                );
                const rect = previewRef.current?.getBoundingClientRect();
                if (!rect) {
                  setCanvasView((prev) => ({ ...prev, scale: nextScale }));
                  return;
                }
                const localX = event.clientX - rect.left - overlayBoundsResolved.left;
                const localY = event.clientY - rect.top - overlayBoundsResolved.top;
                setCanvasView((prev) => {
                  const ratio = nextScale / Math.max(prev.scale, 0.1);
                  return {
                    scale: nextScale,
                    offsetX: localX - (localX - prev.offsetX) * ratio,
                    offsetY: localY - (localY - prev.offsetY) * ratio,
                  };
                });
              }}
            >
              <div
                className="relative flex h-full w-full items-center justify-center overflow-hidden"
                onMouseDown={(event) => {
                  if (allowMapInteraction) return;
                  if (drawMode === "pan") {
                    handleDrawPointer(event, overlayBoundsResolved);
                    return;
                  }
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
                <div
                  ref={mapContainerRef}
                  className={`absolute inset-0 overflow-hidden rounded-[24px] ${
                    showMap ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
                  }`}
                  style={{ width: "100%", height: "100%" }}
                />
                {debugStats?.enabled ? (
                  <div className="pointer-events-none absolute left-5 top-5 z-30 rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-[11px] text-slate-700 shadow-sm">
                    <div className="font-semibold">Map Debug</div>
                    <div>geocode: {geocode?.lat && geocode?.lng ? `${geocode.lat.toFixed(6)}, ${geocode.lng.toFixed(6)}` : "null"}</div>
                    <div>showMap: {showMap ? "true" : "false"}</div>
                    <div>quality: {previewQuality}</div>
                    <div>dimension: {previewMode}</div>
                    <div>mapLoaded: {mapLoaded ? "true" : "false"}</div>
                    <div>mapbox requests: {mapboxRequestCount}</div>
                    <div>mapbox tiles: {mapboxTileCount}</div>
                    <div>
                      container: {mapContainerSize ? `${mapContainerSize.w}×${mapContainerSize.h}` : "null"}
                    </div>
                    <div>
                      canvas: {mapCanvasSize ? `${mapCanvasSize.w}×${mapCanvasSize.h}` : "null"}
                    </div>
                    {mapError ? <div className="text-rose-600">error: {mapError}</div> : null}
                  </div>
                ) : null}
                {showMap ? (
                  <div className="pointer-events-none absolute right-5 top-5 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
                    {showMap3D ? "3D Map" : "2D Map"} · N ↑ {typeof siteRotationDeg === "number" ? `${siteRotationDeg.toFixed(1)}°` : "0°"}
                  </div>
                ) : null}
                {showGeneratedPlan && planPreviewUrl && !showMap ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    ref={previewImageRef}
                    src={planPreviewUrl}
                    alt="Generated plan preview"
                    className={`h-full w-full object-contain ${
                      placementMode || allowEdits ? "cursor-crosshair" : "cursor-default"
                    }`}
                    onLoad={() => updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds)}
                    onClick={onOpenFullscreen}
                  />
                ) : !showMap && !hasLiveObjects ? (
                  <div className="flex h-full w-full items-center justify-center text-sm text-slate-400">
                    Add objects to start building the site. Then click Place and drop them here.
                  </div>
                ) : null}
                {!showGeneratedPlan && previewMode === "3d" && !showMap ? (
                  <div className="pointer-events-none absolute left-6 top-6 rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm">
                    3D needs a preview run
                  </div>
                ) : null}
                {overlayBoundsResolved && previewMode === "2d" ? (
                  <div
                    className="pointer-events-none absolute z-10"
                    style={{
                      left: overlayBoundsResolved.left,
                      top: overlayBoundsResolved.top,
                      width: overlayBoundsResolved.width,
                      height: overlayBoundsResolved.height,
                    }}
                  >
                    {!siteLocked && (showSiteBounds || drawMode === "site") ? (
                      <div
                        className={`absolute inset-0 rounded-[16px] border border-dashed ${legendPalette.siteBorder} ${legendPalette.siteFill}`}
                        style={viewportTransformStyle}
                      />
                    ) : null}
                    {(buildingPlacements.length || suggestedPlacements.length || (surveyPoints?.length ?? 0) > 0) ? (
                      <svg
                        className="absolute inset-0"
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                        style={viewportTransformStyle}
                      >
                        {gradingBlocker ? (
                          (() => {
                            const toPct = (pt: { x: number; y: number }) => ({
                              x: siteTupleToPercent([pt.x, pt.y], currentSiteSize)[0],
                              y: siteTupleToPercent([pt.x, pt.y], currentSiteSize)[1],
                            });
                            const source = gradingBlocker.sourcePoint ? toPct(gradingBlocker.sourcePoint) : null;
                            const target = gradingBlocker.blockedTarget ? toPct(gradingBlocker.blockedTarget) : null;
                            const blocker = gradingBlocker.blockerLocation ? toPct(gradingBlocker.blockerLocation) : null;
                            const zone = gradingBlocker.suggestedFixZone
                              ? siteRectToPercent(
                                  {
                                    x: gradingBlocker.suggestedFixZone.x,
                                    y: gradingBlocker.suggestedFixZone.y,
                                    width: gradingBlocker.suggestedFixZone.w,
                                    height: gradingBlocker.suggestedFixZone.h,
                                  },
                                  currentSiteSize,
                                )
                              : null;
                            return (
                              <g>
                                {zone ? (
                                  <rect
                                    x={zone.left}
                                    y={zone.top}
                                    width={zone.width}
                                    height={zone.height}
                                    fill="rgba(248,113,113,0.12)"
                                    stroke="rgba(248,113,113,0.8)"
                                    strokeDasharray="2 2"
                                    strokeWidth={0.45}
                                  />
                                ) : null}
                                {source && target ? (
                                  <line
                                    x1={source.x}
                                    y1={source.y}
                                    x2={target.x}
                                    y2={target.y}
                                    stroke="rgba(14,116,144,0.75)"
                                    strokeWidth={0.45}
                                    strokeDasharray="3 3"
                                  />
                                ) : null}
                                {source ? (
                                  <circle cx={source.x} cy={source.y} r={1.2} fill="#10b981" />
                                ) : null}
                                {target ? (
                                  <circle cx={target.x} cy={target.y} r={1.2} fill="#3b82f6" />
                                ) : null}
                                {blocker ? (
                                  <circle cx={blocker.x} cy={blocker.y} r={1.1} fill="#f97316" />
                                ) : null}
                              </g>
                            );
                          })()
                        ) : null}
                        {buildingPlacements
                          .filter((item) => item.geometryType === "polyline" && Array.isArray(item.geometry))
                          .map((item) => {
                            const points = (item.geometry || []).map(sitePointToSvgPercent);
                            if (points.length < 2) return null;
                            const visualStyle = resolveSvgVisualStyle(item, selectedBuildingId === item.id);
                            const isSelectedPolyline = selectedBuildingId === item.id;
                            return (
                              <g key={`poly-${item.id}`}>
                                {isHighQuality && (item.type === "road" || item.type === "driveway") ? (
                                  <polyline
                                    points={points.join(" ")}
                                    fill="none"
                                    stroke="rgba(15, 23, 42, 0.18)"
                                    strokeWidth={1.85}
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                ) : null}
                                {isSelectedPolyline ? (
                                  <polyline
                                    points={points.join(" ")}
                                    fill="none"
                                    stroke={previewQuality === "high" ? "#fbbf24" : "#f59e0b"}
                                    strokeWidth={1.3}
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                ) : null}
                                <polyline
                                  points={points.join(" ")}
                                  fill="none"
                                  stroke={visualStyle.stroke}
                                  strokeWidth={visualStyle.strokeWidth}
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                                {isHighQuality && (item.type === "road" || item.type === "driveway") ? (
                                  <polyline
                                    points={points.join(" ")}
                                    fill="none"
                                    stroke="rgba(248, 250, 252, 0.72)"
                                    strokeWidth={0.2}
                                    strokeDasharray="1.4 1.4"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                ) : null}
                              </g>
                            );
                          })}
                        {buildingPlacements
                          .filter((item) => item.geometryType === "polygon" && Array.isArray(item.geometry))
                          .map((item) => {
                            const points = (item.geometry || []).map(sitePointToSvgPercent);
                            if (points.length < 3) return null;
                            const isSelectedPolygon = selectedBuildingId === item.id;
                            const visualStyle = resolveSvgVisualStyle(item, isSelectedPolygon);
                            return (
                              <polygon
                                key={`custom-poly-${item.id}`}
                                points={points.join(" ")}
                                fill={visualStyle.fill}
                                stroke={visualStyle.stroke}
                                strokeWidth={visualStyle.strokeWidth}
                                strokeLinejoin="round"
                              />
                            );
                          })}
                        {buildingPlacements
                          .filter((item) => item.type === "parking" && item.placed)
                          .flatMap((item) =>
                            buildParkingModules(item, accessPointsForParking).map((module, idx) => {
                              const toPct = (pt: [number, number]) => sitePointToSvgPercent(pt);
                              const moduleFill = module.isAdaModule
                                ? "rgba(16,185,129,0.18)"
                                : module.isCompactModule
                                  ? "rgba(168,85,247,0.16)"
                                  : module.angle === 45
                                    ? "rgba(56,189,248,0.14)"
                                    : module.angle === 60
                                      ? "rgba(129,140,248,0.14)"
                                      : "rgba(148,163,184,0.1)";
                              return (
                                <g key={`parking-mod-${item.id}-${idx}`}>
                                  {showParkingAnalysis ? (
                                    <polygon
                                      points={module.bounds.map(toPct).join(" ")}
                                      fill={moduleFill}
                                      stroke="rgba(15,23,42,0.15)"
                                      strokeWidth={0.22}
                                    />
                                  ) : null}
                                  {module.stallPolygons.map((stall, polyIdx) => {
                                    const fill =
                                      showParkingAnalysis && stall.kind === "ada"
                                        ? "rgba(16,185,129,0.55)"
                                        : showParkingAnalysis && stall.kind === "ada_aisle"
                                          ? "rgba(52,211,153,0.35)"
                                        : showParkingAnalysis && stall.kind === "compact"
                                          ? "rgba(168,85,247,0.45)"
                                          : legendPalette.parkingFill;
                                    const stroke =
                                      showParkingAnalysis && stall.kind !== "standard"
                                        ? "#0f172a"
                                        : legendPalette.parking;
                                    const strokeWidth = showParkingAnalysis && stall.kind !== "standard" ? 0.38 : 0.28;
                                    return (
                                      <polygon
                                        key={`stall-${polyIdx}`}
                                        points={stall.points.map(toPct).join(" ")}
                                        fill={fill}
                                        stroke={stroke}
                                        strokeWidth={strokeWidth}
                                      />
                                    );
                                  })}
                                  <polyline
                                    points={module.aisleLine.map(toPct).join(" ")}
                                    fill="none"
                                    stroke={legendPalette.road}
                                    strokeWidth={0.45}
                                  />
                                  {module.stripeLines.map((line, stripeIdx) => (
                                    <polyline
                                      key={`stripe-${stripeIdx}`}
                                      points={line.map(toPct).join(" ")}
                                      fill="none"
                                      stroke="#cbd5f5"
                                      strokeWidth={0.24}
                                    />
                                  ))}
                                </g>
                              );
                            }),
                          )}
                        {suggestedPlacements
                          .filter((item) => item.geometryType && Array.isArray(item.geometry))
                          .map((item) => {
                            const points = (item.geometry || []).map(sitePointToSvgPercent);
                            if (!points.length) return null;
                            const isLine = item.geometryType === "polyline";
                            const visualStyle = resolveSvgVisualStyle(item, selectedBuildingId === item.id);
                            const stroke = item.source === "detected_from_image" ? legendPalette.detectedStroke : visualStyle.stroke;
                            const fill = item.source === "detected_from_image" ? legendPalette.detectedFill : visualStyle.fill;
                            return isLine ? (
                              <polyline
                                key={`geom-${item.id}`}
                                points={points.join(" ")}
                                fill="none"
                                stroke={stroke}
                                strokeWidth={visualStyle.strokeWidth}
                                strokeDasharray={item.source === "detected_from_image" ? "2 2" : undefined}
                              />
                            ) : (
                              <polygon
                                key={`geom-${item.id}`}
                                points={points.join(" ")}
                                fill={fill}
                                stroke={stroke}
                                strokeWidth={visualStyle.strokeWidth}
                                strokeDasharray={item.source === "detected_from_image" ? "2 2" : undefined}
                              />
                            );
                          })}
                        {(surveyPoints ?? []).length
                          ? (surveyPoints ?? []).slice(0, 1500).map((pt, idx) => {
                              const [x, y] = siteTupleToPercent([pt.x, pt.y], currentSiteSize);
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
                        {draftPoints.length || draftPreviewPoint ? (
                          (() => {
                            const points =
                              draftPreviewPoint && drawMode !== "point"
                                ? [...draftPoints, draftPreviewPoint]
                                : draftPoints;
                            if (!points.length) return null;
                            const effectiveLotWidth = drawMode === "site" ? drawingLotWidth : lotWidth;
                            const effectiveLotHeight = drawMode === "site" ? drawingLotHeight : lotHeight;
                            const effectiveSiteSize = { width: effectiveLotWidth, height: effectiveLotHeight };
                            const pct = points.map((pt) => {
                              const [x, y] = siteTupleToPercent(pt, effectiveSiteSize);
                              return `${x},${y}`;
                            });
                            if ((drawMode === "polygon" || drawMode === "site") && pct.length >= 3) {
                              const draftColor = drawMode === "site" ? "#f59e0b" : "#0284c7";
                              return (
                                <g>
                                  <polygon
                                    points={pct.join(" ")}
                                    fill={drawMode === "site" ? "rgba(245,158,11,0.1)" : "rgba(14,165,233,0.08)"}
                                    stroke={draftColor}
                                    strokeWidth={0.55}
                                    strokeDasharray="1.5 1"
                                  />
                                  {points.map((pt, idx) => (
                                    <circle
                                      key={`draft-poly-${idx}`}
                                      cx={siteTupleToPercent(pt, effectiveSiteSize)[0]}
                                      cy={siteTupleToPercent(pt, effectiveSiteSize)[1]}
                                      r={0.55}
                                      fill={draftColor}
                                    />
                                  ))}
                                </g>
                              );
                            }
                            if (drawMode === "rect" && points.length >= 2) {
                              const [a, b] = points;
                              const rectPct = siteRectToPercent(
                                {
                                  x: Math.min(a[0], b[0]),
                                  y: Math.min(a[1], b[1]),
                                  width: Math.abs(a[0] - b[0]),
                                  height: Math.abs(a[1] - b[1]),
                                },
                                effectiveSiteSize,
                              );
                              return (
                                <rect
                                  x={rectPct.left}
                                  y={rectPct.top}
                                  width={rectPct.width}
                                  height={rectPct.height}
                                  fill="rgba(14,165,233,0.08)"
                                  stroke="#0284c7"
                                  strokeWidth={0.55}
                                  strokeDasharray="1.5 1"
                                />
                              );
                            }
                            if (pct.length >= 2) {
                              return (
                                <g>
                                  <polyline
                                    points={pct.join(" ")}
                                    fill="none"
                                    stroke="#0284c7"
                                    strokeWidth={0.55}
                                    strokeDasharray="1.5 1"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                  {points.map((pt, idx) => (
                                    <circle
                                      key={`draft-line-${idx}`}
                                      cx={siteTupleToPercent(pt, effectiveSiteSize)[0]}
                                      cy={siteTupleToPercent(pt, effectiveSiteSize)[1]}
                                      r={0.55}
                                      fill="#0284c7"
                                    />
                                  ))}
                                </g>
                              );
                            }
                            const [pt] = points;
                            return (
                              <circle
                                cx={siteTupleToPercent(pt, effectiveSiteSize)[0]}
                                cy={siteTupleToPercent(pt, effectiveSiteSize)[1]}
                                r={0.65}
                                fill="#0284c7"
                              />
                            );
                          })()
                        ) : null}
                      </svg>
                    ) : null}
                    <div
                      className={`${overlayPointerEvents} absolute inset-0 z-[30]`}
                      style={{
                        transformOrigin: "top left",
                        transform: `${viewportTransformStyle.transform}${
                          focusTransform
                            ? ` translate(50%, 50%) scale(${focusTransform.scale}) translate(-${focusTransform.tx * 100}%, -${focusTransform.ty * 100}%)`
                            : ""
                        }`,
                      }}
                      onMouseDown={(event) => {
                        if (!showMap || mapLocked) return;
                        if (previewInteraction !== "edit") return;
                        if (placementMode) return;
                        if ((event.target as HTMLElement)?.closest?.("[data-object-overlay]")) return;
                        mapDragActiveRef.current = true;
                        mapDragRef.current = { x: event.clientX, y: event.clientY };
                      }}
                      onWheel={(event) => {
                        if (!showMap || mapLocked) return;
                        if (previewInteraction !== "edit") return;
                        if (!mapRef.current) return;
                        event.preventDefault();
                        const map = mapRef.current;
                        const zoom = map.getZoom();
                        const nextZoom = zoom + (event.deltaY < 0 ? 0.4 : -0.4);
                        map.zoomTo(nextZoom, { animate: false });
                      }}
                      onClick={() => {
                        if (analysisFocusLocked) return;
                        onClearHighlights?.();
                      }}
                    >
                      {buildingPlacements
                      .filter(
                        (item) =>
                          item.type !== "site" &&
                          item.placed &&
                          Number.isFinite(item.x) &&
                          Number.isFinite(item.y),
                      )
                      .map((item) => {
                        const caps = getEditCapabilities(item);
                        const isSelected = selectedBuildingId === item.id;
                        const rectPct = siteRectPercent(item);
                        const rotation = item.rotation ?? 0;
                        const borderColorMap: Record<string, string> = {
                          site: previewQuality === "high" ? "border-white/70" : "border-slate-400",
                          setback_zone: "border-slate-300",
                          no_build_zone: "border-rose-400",
                          basin: previewQuality === "high" ? "border-sky-300" : "border-emerald-500",
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
                        const outlineColor =
                          (item.meta as { style?: { outline_color?: string } } | undefined)?.style
                            ?.outline_color;
                        const isAccessHighlight =
                          analysisHighlight &&
                          (analysisHighlight.buildingId === item.id || analysisHighlight.accessId === item.id);
                        const isPolyline = item.geometryType === "polyline";
                        const isPolygon = item.geometryType === "polygon";
                        const isEditableVertexGeometry = isPolyline || isPolygon;
                        const isCustomArea = isPolygon;
                        const showBox = !isPolyline && !isCustomArea;
                        const isSite = item.type === "site";
                        const visualKind = resolveVisualKind(item);
                        const objectBoxStyle = resolveObjectBoxStyle(item);
                        const allowItemInteraction =
                          drawMode === "select" &&
                          (!isSite || (previewInteraction === "edit" && !siteLocked));
                        return (
                          <div
                            key={item.id}
                            data-object-overlay
                            data-preview-quality={previewQuality}
                            data-visual-kind={visualKind}
                            className={`${allowItemInteraction ? "pointer-events-auto" : "pointer-events-none"} absolute z-[30]`}
                            style={{
                              left: `${rectPct.left}%`,
                              top: `${rectPct.top}%`,
                              width: `${rectPct.width}%`,
                              height: `${rectPct.height}%`,
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: caps.movable ? (isPolyline ? "grab" : "move") : "default",
                            }}
                            onMouseDown={(event) => {
                              if (!allowItemInteraction) return;
                              if (draggingMode === "vertex" || hoveredSegment?.id === item.id) return;
                              handleBuildingMouseDown(event, item, "move");
                            }}
                            onMouseEnter={() => {
                              if (!allowItemInteraction) return;
                              if (!showHover) return;
                              setHoveredObjectId(item.id);
                            }}
                            onMouseLeave={() => {
                              setHoveredObjectId(null);
                              setHoveredVertex(null);
                            }}
                            onClick={(event) => {
                              if (!allowItemInteraction) return;
                              event.stopPropagation();
                              setSelectedVertex(null);
                              onSelectBuilding(item.id);
                            }}
                          >
                            <div
                              className={`h-full w-full rounded-[8px] shadow-sm transition ${
                                showBox ? `border ${borderColor}` : ""
                              } ${
                                showBox && isSelected ? "ring-2 ring-amber-300" : ""
                              } ${showBox && isAccessHighlight ? "ring-2 ring-rose-300" : ""}`}
                              style={{
                                ...(showBox ? objectBoxStyle : { backgroundColor: "transparent", borderColor: outlineColor || undefined }),
                              }}
                            />
                            {showBox && isHighQuality && visualKind === "building" ? (
                              <div className="pointer-events-none absolute inset-x-[16%] top-1/2 h-px -translate-y-1/2 bg-white/35" />
                            ) : null}
                            {showBox && isHighQuality && visualKind === "water" ? (
                              <div className="pointer-events-none absolute inset-x-[14%] top-1/2 h-px -translate-y-1/2 bg-sky-100/60 shadow-[0_5px_0_rgba(224,242,254,0.34),0_-5px_0_rgba(224,242,254,0.24)]" />
                            ) : null}
                            {showBox && isHighQuality && visualKind === "utility" ? (
                              <div className="pointer-events-none absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/80 bg-violet-500/80" />
                            ) : null}
                            {isSelected && isEditableVertexGeometry && Array.isArray(item.geometry)
                              ? item.geometry.map((pt, idx) => {
                                  const handleLeft = ((pt[0] - (item.x ?? 0)) / Math.max(item.w, 1)) * 100;
                                  const handleTop = ((pt[1] - (item.y ?? 0)) / Math.max(item.d, 1)) * 100;
                                  const isDragging =
                                    draggingMode === "vertex" &&
                                    draggingVertex?.id === item.id &&
                                    draggingVertex?.index === idx;
                                  const isHovered =
                                    hoveredVertex?.id === item.id && hoveredVertex?.index === idx;
                                  const isSelectedVertex =
                                    selectedVertex?.id === item.id && selectedVertex?.index === idx;
                                  return (
                                    <button
                                      key={`vertex-${item.id}-${idx}`}
                                      type="button"
                                      className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full border shadow transition ${
                                        isDragging
                                          ? "h-4 w-4 border-amber-600 bg-amber-500 ring-4 ring-amber-200 cursor-grabbing"
                                          : isHovered
                                            ? "h-4 w-4 border-amber-500 bg-amber-400 ring-2 ring-amber-200 cursor-grab"
                                            : isSelectedVertex
                                              ? "h-4 w-4 border-amber-600 bg-amber-500 ring-2 ring-amber-200"
                                              : "h-3.5 w-3.5 border-white bg-amber-300 cursor-grab"
                                      }`}
                                      style={{ left: `${handleLeft}%`, top: `${handleTop}%` }}
                                      onMouseEnter={() => setHoveredVertex({ id: item.id, index: idx })}
                                      onMouseLeave={() => setHoveredVertex(null)}
                                      onMouseDown={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        if (Array.isArray(item.geometry)) {
                                          setLastPolylineEdit({
                                            id: item.id,
                                            geometry: (item.geometry as Array<[number, number]>).map((pt) => [
                                              pt[0],
                                              pt[1],
                                            ]),
                                            x: item.x ?? 0,
                                            y: item.y ?? 0,
                                            w: item.w,
                                            d: item.d,
                                            ts: Date.now(),
                                          });
                                        }
                                        setDraggingBuildingId(item.id);
                                        setDraggingMode("vertex");
                                        setDraggingVertex({ id: item.id, index: idx });
                                        setSelectedVertex({ id: item.id, index: idx });
                                        onSelectBuilding(item.id);
                                      }}
                                    />
                                  );
                                })
                              : null}
                            {isSelected &&
                            isEditableVertexGeometry &&
                            Array.isArray(item.geometry) &&
                            item.geometry.length > 1 &&
                            (isPolygon || item.type === "custom" || item.type === "road" || item.type === "driveway" || item.type === "sidewalk") ? (
                              <svg
                                ref={polylineSegmentRef}
                                className="absolute inset-0"
                                viewBox="0 0 100 100"
                                preserveAspectRatio="none"
                              >
                                {(item.geometry ?? []).map((pt, idx, arr) => {
                                  if (idx === arr.length - 1 && !isPolygon) return null;
                                  const next = idx === arr.length - 1 ? arr[0] : arr[idx + 1];
                                  const x1 = ((pt[0] - (item.x ?? 0)) / Math.max(item.w, 1)) * 100;
                                  const y1 = ((pt[1] - (item.y ?? 0)) / Math.max(item.d, 1)) * 100;
                                  const x2 = ((next[0] - (item.x ?? 0)) / Math.max(item.w, 1)) * 100;
                                  const y2 = ((next[1] - (item.y ?? 0)) / Math.max(item.d, 1)) * 100;
                                  const isHoveredSeg =
                                    hoveredSegment?.id === item.id && hoveredSegment?.index === idx;
                                  return (
                                    <g key={`seg-${item.id}-${idx}`}>
                                      {isHoveredSeg ? (
                                        <line
                                          x1={x1}
                                          y1={y1}
                                          x2={x2}
                                          y2={y2}
                                          stroke="rgba(245,158,11,0.6)"
                                          strokeWidth={1.3}
                                          strokeLinecap="round"
                                        />
                                      ) : null}
                                      <line
                                        x1={x1}
                                        y1={y1}
                                        x2={x2}
                                        y2={y2}
                                        stroke="transparent"
                                        strokeWidth={8}
                                        strokeLinecap="round"
                                        pointerEvents="stroke"
                                        onMouseEnter={() => setHoveredSegment({ id: item.id, index: idx })}
                                        onMouseLeave={() => setHoveredSegment(null)}
                                        onMouseDown={(event) => event.stopPropagation()}
                                        onClick={(event) => {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          insertVertexOnSegment(event, item, idx);
                                        }}
                                      />
                                    </g>
                                  );
                                })}
                              </svg>
                            ) : null}
                            {isSelected && isEditableVertexGeometry ? (
                              <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-amber-700 shadow">
                                Vertex edit
                              </div>
                            ) : null}
                            {isSelected &&
                            isEditableVertexGeometry &&
                            lastPolylineEdit?.id === item.id ? (
                              <button
                                type="button"
                                className="absolute -bottom-10 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-600 shadow"
                                onClick={(event) => {
                                  event.preventDefault();
                                  event.stopPropagation();
                                  applyPolylineUndo();
                                }}
                              >
                                Undo
                              </button>
                            ) : null}
                            {isSelected && isEditableVertexGeometry && selectedVertex?.id === item.id ? (
                              <button
                                type="button"
                                className="absolute -bottom-16 left-1/2 -translate-x-1/2 rounded-full border border-rose-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-rose-600 shadow"
                                onClick={(event) => {
                                  event.preventDefault();
                                  event.stopPropagation();
                                  deleteSelectedVertex();
                                }}
                              >
                                Delete vertex
                              </button>
                            ) : null}
                            {isSelected &&
                            !isPolyline &&
                            lastRectEdit?.id === item.id ? (
                              <button
                                type="button"
                                className="absolute -bottom-12 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-600 shadow"
                                onClick={(event) => {
                                  event.preventDefault();
                                  event.stopPropagation();
                                  applyRectUndo();
                                }}
                              >
                                Undo
                              </button>
                            ) : null}
                            {isSelected &&
                            isEditableVertexGeometry &&
                            !polylineInsertHintDismissed &&
                            (isPolygon || item.type === "custom" || item.type === "road" || item.type === "driveway" || item.type === "sidewalk") ? (
                              <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-600 shadow">
                                Click a segment to add a vertex
                              </div>
                            ) : null}
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
                                  setLastRectEdit({
                                    id: item.id,
                                    snapshot: { ...item },
                                    action: "delete",
                                    ts: Date.now(),
                                  });
                                  onRemoveBuilding(item.id);
                                }}
                              >
                                ×
                              </button>
                            ) : null}
                            {isSelected && caps.movable && !isPolyline ? (
                              <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
                                Snap 5ft
                              </div>
                            ) : null}
                            {isSelected && typeof item.x === "number" && typeof item.y === "number" ? (
                              <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-600 shadow">
                                X {item.x.toFixed(1)} ft • Y {item.y.toFixed(1)} ft
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
                        const rectPct = siteRectPercent(item);
                        const rotation = item.rotation ?? 0;
                        return (
                          <div
                            key={item.id}
                            className="pointer-events-auto absolute"
                            style={{
                              left: `${rectPct.left}%`,
                              top: `${rectPct.top}%`,
                              width: `${rectPct.width}%`,
                              height: `${rectPct.height}%`,
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: "move",
                            }}
                            onMouseDown={(event) => handleBuildingMouseDown(event, item, "move")}
                            onMouseEnter={() => {
                              if (!showHover) return;
                              setHoveredObjectId(item.id);
                            }}
                            onMouseLeave={() => setHoveredObjectId(null)}
                          >
                            <div className="h-full w-full rounded-[8px] border border-dashed border-amber-400 bg-amber-200/10" />
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
                              const [x, y] = siteTupleToPercent([pt.x, pt.y], currentSiteSize);
                              return `${x},${y}`;
                            })
                            .join(" ");
                          const labelPoint = points[Math.floor(points.length / 2)] ?? path.from;
                          const [labelX, labelY] = siteTupleToPercent([labelPoint.x, labelPoint.y], currentSiteSize);
                          return (
                            <g key={path.id}>
                              <polyline
                                points={coords}
                                fill="none"
                                stroke={isSelected ? "#ef4444" : "#f97316"}
                                strokeWidth={isSelected ? "0.75" : "0.4"}
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
                        className="absolute rounded-[14px] border border-sky-400/90 bg-sky-400/10 shadow-[0_0_0_4px_rgba(56,189,248,0.14)]"
                        style={buildBoundsStyle(activeHighlightBounds)}
                      />
                    ) : null}
                    {issueHighlightBounds ? (
                      <div
                        className="absolute rounded-[12px] border border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_4px_rgba(244,63,94,0.1)]"
                        style={buildBoundsStyle(issueHighlightBounds)}
                      />
                    ) : null}
                    {showHover
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
              {showHover && activeAnnotation && hoverPoint ? (
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
              {showHover && !planPreviewAnnotations?.labels?.length ? (
                <div className="pointer-events-none absolute right-6 top-6 hidden rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white lg:block">
                  Hover labels pending
                </div>
              ) : null}
              {showHover ? (
                <div
                  className="pointer-events-none absolute left-6 top-6 hidden rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white lg:block"
                >
                  Hover geometry for details
                </div>
              ) : null}
              {/* Status panel removed: keep preview visually clean. */}
              {previewFullscreenOpen && showMap ? (
                <div className="pointer-events-auto absolute left-0 right-0 top-0 z-40 flex items-center justify-between gap-3 border-b border-white/10 bg-slate-950/88 px-5 py-4 text-white backdrop-blur">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                      Fullscreen Preview
                    </p>
                    <p className="mt-1 text-sm text-slate-200">
                      Inspect the live map without rebuilding the preview.
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
              ) : null}
            </div>
          )}
        </div>

      {previewFullscreenOpen && planPreviewUrl && !showMap ? (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/92 backdrop-blur-sm">
          <div className="flex h-full w-full flex-col bg-slate-950">
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
            <div className="flex min-h-0 flex-1 items-center justify-center p-0">
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
                  if (allowMapInteraction) return;
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
                  setDraggingVertex(null);
                }}
                onClick={(event) => {
                  if (allowMapInteraction) return;
                  if (placementMode) {
                    resolvePlacement(event, fullscreenRef, fullscreenImageBounds);
                    return;
                  }
                  if (!showHover || !hoveredAnnotation) return;
                  setPinnedAnnotation((prev) =>
                    prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
                  );
                }}
              >
                {showMap ? (
                  <div
                    ref={(node) => {
                      fullscreenMapContainerRef.current = node;
                      setFullscreenContainerReady(Boolean(node));
                    }}
                    className="absolute inset-0 overflow-hidden"
                    style={{ width: "100%", height: "100%" }}
                  />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    ref={fullscreenImageRef}
                    src={planPreviewUrl}
                    alt="Generated plan preview fullscreen"
                    className="h-full w-full bg-white object-contain"
                    onLoad={() =>
                      updateImageBounds(fullscreenRef, fullscreenImageRef, setFullscreenImageBounds)
                    }
                  />
                )}
                {showHover && !planPreviewAnnotations?.labels?.length ? (
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
                    {!siteLocked && lotWidth > 0 && lotHeight > 0 ? (
                      <div className="absolute inset-0 rounded-[16px] border border-dashed border-slate-300/70" />
                    ) : null}
                    {activeHighlightBounds ? (
                      <div
                        className="absolute rounded-[14px] border border-sky-400/90 bg-sky-400/10 shadow-[0_0_0_4px_rgba(56,189,248,0.14)]"
                        style={buildBoundsStyle(activeHighlightBounds)}
                      />
                    ) : null}
                    {issueHighlightBounds ? (
                      <div
                        className="absolute rounded-[12px] border border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_4px_rgba(244,63,94,0.1)]"
                        style={buildBoundsStyle(issueHighlightBounds)}
                      />
                    ) : null}
                    {showHover
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
                        const rectPct = siteRectPercent(item);
                        const rotation = item.rotation ?? 0;
                        const isSite = item.type === "site";
                        const allowItemInteraction =
                          !isSite || (previewInteraction === "edit" && !siteLocked);
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
                        const outlineColor =
                          (item.meta as { style?: { outline_color?: string } } | undefined)?.style
                            ?.outline_color;
                        return (
                          <div
                            key={item.id}
                            data-object-overlay
                            className={`${allowMapInteraction || !allowItemInteraction ? "pointer-events-none" : "pointer-events-auto"} absolute`}
                            style={{
                              left: `${rectPct.left}%`,
                              top: `${rectPct.top}%`,
                              width: `${rectPct.width}%`,
                              height: `${rectPct.height}%`,
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: placementMode ? "move" : "default",
                            }}
                            onMouseDown={(event) => {
                              if (allowMapInteraction || !allowItemInteraction) return;
                              handleBuildingMouseDown(event, item, "move");
                            }}
                            onClick={(event) => {
                              if (allowMapInteraction || !allowItemInteraction) return;
                              if (!placementMode) return;
                              event.stopPropagation();
                              onSelectBuilding(item.id);
                            }}
                          >
                            <div
                              className={`h-full w-full rounded-[8px] border bg-slate-900/10 transition ${borderColor}`}
                              style={outlineColor ? { borderColor: outlineColor } : undefined}
                            />
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
                          const rectPct = siteRectPercent(item);
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
                                left: `${rectPct.left}%`,
                                top: `${rectPct.top}%`,
                                width: `${rectPct.width}%`,
                                height: `${rectPct.height}%`,
                                transform: `rotate(${rotation}deg)`,
                                transformOrigin: "center",
                                cursor: "pointer",
                              }}
                              onMouseEnter={() => {
                                if (!showHover) return;
                                setHoveredObjectId(item.id);
                              }}
                              onMouseLeave={() => setHoveredObjectId(null)}
                              onClick={(event) => {
                                event.stopPropagation();
                                onSelectBuilding(item.id);
                              }}
                            >
                              <div
                                className={`h-full w-full rounded-[8px] border border-dashed bg-slate-50/70 transition ${borderColor}`}
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
                {showHover && activeAnnotation && fullscreenHoverPoint ? (
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
                {allowEdits && showMeasurements ? (
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
                {allowEdits && showCalculations ? (
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
