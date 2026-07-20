"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, MouseEvent as ReactMouseEvent } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { Hand, MapPin, MousePointer2, Pentagon, PencilLine, Square, X } from "lucide-react";

import type { BuildingPlacement } from "../types";
import { CadPrecisionDock } from "./CadPrecisionDock";
import { CanvasQuickDrawPalette } from "./CanvasQuickDrawPalette";
import { Preview3DShell } from "./Preview3DShell";
import { formatCount, formatMetric } from "../utils/formatting";
import {
  boundsForSiteGeometry,
  mapLngLatToSite,
  resizeSiteGeometryFromOrigin,
  resolveCoordinateMode,
  screenToSitePoint as transformScreenToSitePoint,
  siteRectToPercent,
  siteToMapLngLat,
  siteTupleToPercent,
  translateSiteGeometry,
} from "../utils/geometryTransforms";
import {
  cleanupPolygon,
  filletGeometry,
  offsetGeometry,
  resolveCadSnap,
  transformGeometry,
  trimOrExtendGeometry,
  validatePolygon,
  validateTopology,
  type CadSegment2D,
  type CadSnapKind,
} from "../utils/cadGeometryKernel";
import type { CadDimensionMode, CadSymbolKind, DrawMode } from "../utils/cadToolTypes";
import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import { AiRealismPreviewOverlay } from "./AiRealismPreviewOverlay";
import { PreviewBasePlanGrid } from "./PreviewBasePlanGrid";
import { PreviewCadMarkers } from "./PreviewCadMarkers";
import { PreviewCanvasHeaderControls } from "./PreviewCanvasHeaderControls";
import { PreviewCanvasHud } from "./PreviewCanvasHud";
import { PreviewDraftGeometryOverlay } from "./PreviewDraftGeometryOverlay";
import { PreviewFloatingToolbar } from "./PreviewFloatingToolbar";
import { PreviewGradingEarthworkDock } from "./PreviewGradingEarthworkDock";
import { PreviewMobileDrawToolbar } from "./PreviewMobileDrawToolbar";
import { PreviewMapStatusOverlay } from "./PreviewMapStatusOverlay";
import { PreviewObjectManagerOverlay } from "./PreviewObjectManagerOverlay";
import { PreviewParkingModules } from "./PreviewParkingModules";
import { PreviewPolylineObjects } from "./PreviewPolylineObjects";
import { PreviewPolygonObjects } from "./PreviewPolygonObjects";
import { PreviewRectObjects } from "./PreviewRectObjects";
import { PreviewStableDrawToolbar } from "./PreviewStableDrawToolbar";
import { PreviewSuggestedGeometry } from "./PreviewSuggestedGeometry";
import { PreviewSvgDefs } from "./PreviewSvgDefs";
import { PreviewWaterFireFlowOverlay } from "./PreviewWaterFireFlowOverlay";
import { UtilityCoordinationDock } from "./UtilityCoordinationDock";
import { usePreviewFocusTransform } from "./usePreviewFocusTransform";
import { usePreviewMapLayerSync } from "./usePreviewMapLayerSync";
import { usePreviewMapRuntime } from "./usePreviewMapRuntime";
import { usePreviewResizeObservers } from "./usePreviewResizeObservers";
import { WaterFireFlowEvidenceDock } from "./WaterFireFlowEvidenceDock";
import {
  formatFlowValue,
  geometryTruthLabel,
  resolveSourceState,
  sourceStateLabel,
} from "../utils/previewGeometryTruth";
import {
  clampValue,
  getPreviewCadLayer,
  getPreviewEditCapabilities,
  getPreviewObjectActionBlocker as resolvePreviewObjectActionBlocker,
  getPreviewObjectDimensionsLabel as resolvePreviewObjectDimensionsLabel,
  getPreviewObjectGeometryPoints,
  getPreviewObjectSourceLabel as resolvePreviewObjectSourceLabel,
  getPreviewObjectStatusLabel as resolvePreviewObjectStatusLabel,
  snapPreviewValue,
} from "../utils/previewCadObjectHelpers";
import {
  buildUtilityCoordinationRows,
  summarizeUtilityCoordinationRows,
} from "../utils/previewUtilityCoordination";
import {
  buildWaterFireFlowViewModel,
} from "../utils/previewWaterFireFlow";
import { buildPreviewParkingMapModules } from "../utils/previewParkingMapModules";
import {
  buildPlanScaleBar,
  buildPreviewBoundsStyle,
  buildScaleTruthLabel,
} from "../utils/previewLayoutHelpers";
import {
  buildBalancedPreviewCanvasView,
  buildFocusedPreviewCanvasView,
} from "../utils/previewCanvasViewHelpers";
import {
  buildDraftGeometryFinishBlockedMessage,
  buildDraftGeometryFinishBlockedReason,
  buildDrawToolLabel,
  getDraftGeometryEffectivePointCount,
  getDraftGeometryMinPointCount,
  resolveDraftGeometryEffectivePoints,
} from "../utils/previewDraftGeometryHelpers";
import {
  buildPreviewObjectManagerCounts,
  buildPreviewObjectManagerRows,
} from "../utils/previewObjectManager";
import {
  buildDraftGeometryCreatedMessage,
  buildReviewRequiredCommandMeta,
  getCadCommandFirstValue,
  getCadCommandPointArgs,
  hasSelectedCadCommandArg,
  isKnownCadCommand,
  normalizeCadCommandKey,
  parseCadNumber,
  parseCadPointToken,
  parseCadPointTokens,
  parseCadRelativePointToken,
  parseCadVectorToken,
} from "../utils/previewCadCommandParsing";
import {
  isCadCrossingSelection,
  isCadWindowSelectionTooSmall,
  resolveCadWindowSelectedObjectIds,
} from "../utils/previewCadWindowSelection";
import { resolvePreviewVisualKind } from "../utils/previewVisualStyles";
import { PreviewActiveDrawHud } from "./PreviewActiveDrawHud";
import {
  AI_REALISM_WATERMARK,
  BALANCED_CANVAS_SCALE,
  formatCalmCadStatus,
  type CadCommandHistoryEntry,
  type CadHistoryEntry,
  type CadPoint,
  type PreviewPanelProps,
  type UtilityCoordinationRow,
} from "./previewPanelTypes";
import { useAiRealismPreview } from "./useAiRealismPreview";

export default function PreviewPanel({
  previewReview,
  onRefreshPreview,
  busy,
  planPreviewUrl,
  planPreviewProjectId,
  currentProjectId,
  previewMode,
  previewInteraction,
  previewQuality,
  systemStatuses,
  hasTerrainSource,
  hasGeneratedPlan,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onSetPreviewQuality,
  onAiRealismChange,
  preview3DEffectiveItems,
  usingAnnotation3D,
  hasGradingSurface,
  placementMode,
  onPlaceBuilding,
  onPlaceObject,
  onCreateCustomGeometry,
  onCreateSiteBoundary,
  onLockSite,
  onUnlockSite,
  buildingPlacements,
  cadEntityPreviewObjects = [],
  suggestedPlacements,
  selectedBuildingId,
  selectedObjectIds = [],
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
  onSelectObjects,
  analysisPaths,
  analysisHighlight,
  analysisFocusLocked,
  onClearHighlights,
  onResetView,
  onOpenFullscreen,
  previewFullscreenOpen,
  onCloseFullscreen,
  planPreviewAnnotations,
  selectedIssueLabel,
  showMeasurements,
  showCalculations,
  measurementOverlayStats,
  calculationOverlayStats,
  gradingEarthworkUx,
  geocode,
  mapScaleFtPerPx,
  mapScaleSource,
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
  debugStats,
  cadToolRequest,
}: PreviewPanelProps) {
  const previewLabels = useMemo(
    () => (Array.isArray(planPreviewAnnotations?.labels) ? planPreviewAnnotations?.labels : []),
    [planPreviewAnnotations],
  );
  const utilityCoordinationRows = useMemo<UtilityCoordinationRow[]>(
    () => buildUtilityCoordinationRows(planPreviewAnnotations, previewLabels),
    [planPreviewAnnotations, previewLabels],
  );
  const utilityCoordinationSummary = useMemo(() => {
    const summary = summarizeUtilityCoordinationRows(utilityCoordinationRows);
    const avgScore = utilityCoordinationRows.length
      ? Math.round(utilityCoordinationRows.reduce((sum, row) => sum + row.constructabilityScore, 0) / utilityCoordinationRows.length)
      : previewReview?.unresolved_conflict_count
        ? 48
        : 76;
    return {
      crossingCount: utilityCoordinationRows.length,
      conflictCount: summary.conflictCount,
      watchCount: summary.watchCount,
      avgScore,
      status: summary.status,
    };
  }, [previewReview?.unresolved_conflict_count, utilityCoordinationRows]);
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
  const [managedObjectId, setManagedObjectId] = useState<string | null>(null);
  const [pinnedAnnotation, setPinnedAnnotation] = useState<(typeof previewLabels)[number] | null>(null);
  const [hoverPoint, setHoverPoint] = useState<{ x: number; y: number } | null>(null);
  const [fullscreenHoverPoint, setFullscreenHoverPoint] = useState<{ x: number; y: number } | null>(null);
  const hoverAnnotationRafRef = useRef<number | null>(null);
  const pendingHoverAnnotationRef = useRef<{
    annotation: (typeof previewLabels)[number] | null;
    point: { x: number; y: number } | null;
    setter: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>;
  } | null>(null);
  const [previewImageBounds, setPreviewImageBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [fullscreenImageBounds, setFullscreenImageBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [fullscreenContainerReady, setFullscreenContainerReady] = useState(false);
  const [previewContainerBounds, setPreviewContainerBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [cursorSitePoint, setCursorSitePoint] = useState<{ x: number; y: number } | null>(null);
  const [drawMode, setDrawMode] = useState<DrawMode>("select");
  const [cadSnapEnabled, setCadSnapEnabled] = useState(true);
  const [cadOrthoEnabled, setCadOrthoEnabled] = useState(false);
  const [cadOffsetDistance, setCadOffsetDistance] = useState("10");
  const [cadFilletRadius, setCadFilletRadius] = useState("5");
  const [cadTransformValue, setCadTransformValue] = useState("10");
  const [cadLayerDraft, setCadLayerDraft] = useState("C-DRAFT");
  const [cadCoordinateDraft, setCadCoordinateDraft] = useState({ x: "", y: "" });
  const [cadSelectionSet, setCadSelectionSet] = useState<string[]>([]);
  const [hiddenCadLayers, setHiddenCadLayers] = useState<string[]>([]);
  const [cadCommandDraft, setCadCommandDraft] = useState("");
  const [cadCommandStatus, setCadCommandStatus] = useState("Commands: LINE, PLINE, RECTANGLE, CIRCLE, ARC, ARRAY, ALIGN, DISTRIBUTE, DIST, OFFSET, TRIM, EXTEND, FILLET, JOIN, SPLIT, CLOSE, OPEN, REVERSE, HATCH, MIRROR, MOVE, ROTATE, SCALE, COPY, DELETE, DIM, TEXT, LAYER, SNAP, ORTHO.");
  const [cadCommandHistory, setCadCommandHistory] = useState<CadCommandHistoryEntry[]>([]);
  const [cadActiveCommand, setCadActiveCommand] = useState<
    | {
        kind: "draw";
        command: "LINE" | "PLINE" | "RECTANGLE";
        mode: "polyline" | "rect";
        minPoints: number;
      }
    | {
        kind: "offset";
        command: "OFFSET";
        distance?: number;
      }
    | {
        kind: "modify";
        command: "TRIM" | "EXTEND";
        amount?: number;
      }
    | {
        kind: "transform";
        command: "MOVE" | "ROTATE" | "SCALE" | "COPY";
        value?: string;
      }
    | null
  >(null);
  const [cadSymbolDraft, setCadSymbolDraft] = useState<CadSymbolKind>("hydrant");
  const [cadDimensionMode, setCadDimensionMode] = useState<CadDimensionMode>("linear");
  const [cadDimensionLabelDraft, setCadDimensionLabelDraft] = useState("");
  const [cadPropertyDraft, setCadPropertyDraft] = useState({
    id: "",
    name: "",
    type: "",
    layer: "C-DRAFT",
    elevation: "",
    material: "",
    size: "",
    source: "",
    sourceNote: "",
    reviewNote: "",
  });
  const [cadHistory, setCadHistory] = useState<CadHistoryEntry[]>([]);
  const [cadRedoStack, setCadRedoStack] = useState<CadHistoryEntry[]>([]);
  const [activeSnapPoint, setActiveSnapPoint] = useState<(CadPoint & { kind: CadSnapKind }) | null>(null);
  const cursorSitePointRafRef = useRef<number | null>(null);
  const pendingCursorSitePointRef = useRef<CadPoint | null>(null);
  const draftPointerRafRef = useRef<number | null>(null);
  const pendingDraftPointerRef = useRef<(CadPoint & { kind: CadSnapKind }) | null>(null);
  const canvasPanRafRef = useRef<number | null>(null);
  const pendingCanvasPanViewRef = useRef<{ offsetX: number; offsetY: number } | null>(null);
  const canvasPanStartedAtRef = useRef<number | null>(null);
  const [selectedFireScenarioId, setSelectedFireScenarioId] = useState<string | null>(null);
  const [draftPoints, setDraftPoints] = useState<Array<[number, number]>>([]);
  const draftPointsRef = useRef<Array<[number, number]>>([]);
  const [draftPreviewPoint, setDraftPreviewPoint] = useState<[number, number] | null>(null);
  const [drawAutoFinishPointCount, setDrawAutoFinishPointCount] = useState<number | null>(null);
  const lastSiteDrawRequestRef = useRef(siteDrawRequest);
  const suppressNextDrawClickRef = useRef(false);
  const suppressNextObjectClickRef = useRef(false);
  const lastDraftPreviewPointRef = useRef<[number, number] | null>(null);
  const [canvasView, setCanvasView] = useState({ scale: BALANCED_CANVAS_SCALE, offsetX: 0, offsetY: 0 });
  const autoFitSignatureRef = useRef("");
  const userAdjustedCanvasViewRef = useRef(false);
  const drawingLotWidth = lotWidth > 0 ? lotWidth : 500;
  const drawingLotHeight = lotHeight > 0 ? lotHeight : 300;
  const hasDrawableSiteSize = lotWidth > 0 && lotHeight > 0;
  const canDrawObjects = hasDrawableSiteSize;
  const previousPlacementIdsRef = useRef<Set<string> | null>(null);
  const drawObjectsDisabledLabel = !hasDrawableSiteSize
    ? "Set site width and depth before drawing objects"
    : "Drawing tools available";
  const [canvasPanStart, setCanvasPanStart] = useState<{
    x: number;
    y: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const [cadWindowSelect, setCadWindowSelect] = useState<{
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
    containerLeft: number;
    containerTop: number;
  } | null>(null);
  const cadWindowSelectRef = useRef<typeof cadWindowSelect>(null);
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
  const buildBalancedCanvasView = useCallback(() => {
    const rect = previewRef.current?.getBoundingClientRect();
    return buildBalancedPreviewCanvasView(rect, BALANCED_CANVAS_SCALE);
  }, []);
  const resetCanvasView = useCallback(() => {
    userAdjustedCanvasViewRef.current = false;
    setCanvasView(buildBalancedCanvasView());
  }, [buildBalancedCanvasView]);
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
  const [compactViewport, setCompactViewport] = useState(false);
  const lastMapResizeRef = useRef<number>(0);
  const [mapOverlayEnabled, setMapOverlayEnabled] = useState(false);
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
  const highQualityObjectCount = buildingPlacements.length + suggestedPlacements.length + (surveyPoints?.length ?? 0);
  const useLightHighQuality =
    previewQuality === "high" && (compactViewport || highQualityObjectCount > 220);
  const showMapBase = mapAvailable && mapOverlayEnabled;
  const showMap = showMapBase && previewMode === "2d";
  const showMap3D = showMapBase && previewMode === "3d";
  const mapPitch = showMap3D ? 58 : 0;
  const mapBearing = showMap3D ? (typeof siteRotationDeg === "number" ? siteRotationDeg : 0) : 0;
  const allowMapInteraction =
    showMap && previewInteraction === "static" && !placementMode && !rotateDragStart && !mapLocked;
  const showGeneratedPlan =
    !showMap &&
    previewInteraction === "static" &&
    drawMode === "select" &&
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
  const showQuickDrawPalette =
    previewMode === "2d" &&
    (allowEdits || drawMode !== "select") &&
    drawMode !== "pan";
  const showMobileDrawToolbar = showQuickDrawPalette;
  const activeDrawMode =
    (drawMode === "site" && !siteLocked) ||
    ((drawMode === "polyline" || drawMode === "polygon" || drawMode === "rect" || drawMode === "point") && canDrawObjects);
  const drawingOwnsCanvasHits = activeDrawMode || drawMode === "pan";
  const drawingSurfaceInteractive =
    placementMode ||
    activeDrawMode ||
    Boolean(draggingBuildingId && draggingMode) ||
    Boolean(rotateDragStart) ||
    Boolean(canvasPanStart) ||
    (allowEdits && drawMode === "select") ||
    (showMap && previewInteraction === "edit" && !mapLocked);
  const overlayPointerEvents = drawingSurfaceInteractive ? "pointer-events-auto" : "pointer-events-none";
  const passiveOverlayPointerEvents = drawingOwnsCanvasHits ? "pointer-events-none" : "pointer-events-auto";
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
  useEffect(() => {
    if (typeof window === "undefined") return;
    const query = window.matchMedia("(max-width: 767px), (pointer: coarse)");
    const update = () => setCompactViewport(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  const currentSiteSize = useMemo(
    () => ({ width: Math.max(lotWidth, 1), height: Math.max(lotHeight, 1) }),
    [lotHeight, lotWidth],
  );
  const isHighQuality = previewQuality === "high";
  const aiRealismProviderConfigured = useMemo(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("aiRealismProvider") === "mock") return true;
    }
    return Boolean(process.env.NEXT_PUBLIC_CIVORA_AI_REALISM_PROVIDER?.trim());
  }, []);
  const planScaleBar = useMemo(() => buildPlanScaleBar(currentSiteSize), [currentSiteSize]);
  const scaleTruthLabel = useMemo(
    () => buildScaleTruthLabel({ geocode, mapScaleFtPerPx, mapScaleSource }),
    [geocode, mapScaleFtPerPx, mapScaleSource],
  );
  const resolveVisualKind = useCallback(resolvePreviewVisualKind, []);
  const hoveredObject = useMemo(
    () =>
      [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements].find(
        (item) => item.id === hoveredObjectId && item.type !== "site",
      ) ?? null,
    [buildingPlacements, cadEntityPreviewObjects, suggestedPlacements, hoveredObjectId],
  );
  const shouldRevealObjectLabel = useCallback(
    (item: BuildingPlacement) => hoveredObjectId === item.id || selectedBuildingId === item.id,
    [hoveredObjectId, selectedBuildingId],
  );
  const show3D = previewMode === "3d" && !showMap;
  useEffect(() => {
    if (typeof window === "undefined") return;
    const debugWindow = window as unknown as Record<string, unknown>;
    debugWindow.__civoraGeocode = geocode ?? null;
    debugWindow.__civoraShowMap = showMap;
    debugWindow.__civoraMapOverlayEnabled = mapOverlayEnabled;
    debugWindow.__civoraPreviewQuality = previewQuality;
    debugWindow.__civoraMapLoaded = mapLoaded;
  }, [geocode, mapLoaded, mapOverlayEnabled, showMap, previewQuality]);
  const selectedObject = useMemo(() => {
    const selectedIds = [selectedBuildingId, managedObjectId, hoveredObjectId, ...selectedObjectIds, ...cadSelectionSet].filter(Boolean);
    return (
      [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements].find(
        (item) => selectedIds.includes(item.id) && item.type !== "site",
      ) ?? null
    );
  }, [buildingPlacements, cadEntityPreviewObjects, cadSelectionSet, hoveredObjectId, managedObjectId, selectedBuildingId, selectedObjectIds, suggestedPlacements]);
  const {
    aiRealismEnabled,
    aiRealismBlocker,
    aiRealismDisplayArtifact,
    generateAiRealismArtifact,
    setAiVisualizationOff,
    setAiVisualizationOn,
  } = useAiRealismPreview({
    buildingPlacements,
    cadEntityPreviewObjects,
    suggestedPlacements,
    lotWidth,
    lotHeight,
    siteRotationDeg: siteRotationDeg ?? 0,
    hasTerrainSource,
    geocode,
    currentProjectId,
    planPreviewProjectId,
    aiRealismProviderConfigured,
    onAiRealismChange,
  });
  const selectedDeletableObject =
    selectedObject &&
    !selectedObject.locked &&
    selectedObject.type !== "site" &&
    buildingPlacements.some((item) => item.id === selectedObject.id)
      ? selectedObject
      : null;
  const showEarthworkUx =
    previewMode === "2d" &&
    Boolean(gradingEarthworkUx) &&
    (hasGradingSurface || systemStatuses.grading === "fresh");
  const accessPointsForParking = useMemo(
    () =>
      buildingPlacements
        .filter((item) => item.type === "entrance" || item.type === "road" || item.type === "driveway")
        .map((item) => ({ x: (item.x ?? 0) + item.w / 2, y: (item.y ?? 0) + item.d / 2 })),
    [buildingPlacements],
  );
  const waterFireFlow = useMemo(
    () =>
      buildWaterFireFlowViewModel({
        annotations: planPreviewAnnotations?.water_fire_flow,
        buildingPlacements,
        suggestedPlacements,
        selectedFireScenarioId,
      }),
    [buildingPlacements, planPreviewAnnotations?.water_fire_flow, selectedFireScenarioId, suggestedPlacements],
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
      const isDrawingMode = drawMode === "site" || drawMode === "polyline" || drawMode === "polygon" || drawMode === "rect" || drawMode === "point";
      if (!isDrawingMode && (relX < 0 || relX > 1 || relY < 0 || relY > 1)) return null;
      const clampedRelX = Math.min(Math.max(relX, 0), 1);
      const clampedRelY = Math.min(Math.max(relY, 0), 1);
      const clampedX = Math.min(Math.max(rawSitePoint.x, 0), effectiveLotWidth);
      const clampedY = Math.min(Math.max(rawSitePoint.y, 0), effectiveLotHeight);
      const snapStep = drawMode === "point" ? 1 : drawMode === "site" ? 5 : 2;
      return {
        x: Math.round(clampedX / snapStep) * snapStep,
        y: Math.round(clampedY / snapStep) * snapStep,
        relX: clampedRelX,
        relY: clampedRelY,
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
  const applyCursorSitePoint = useCallback((nextPoint: CadPoint | null) => {
    setCursorSitePoint((current) => {
      if (!nextPoint) return current === null ? current : null;
      return current &&
        Math.abs(current.x - nextPoint.x) < 0.5 &&
        Math.abs(current.y - nextPoint.y) < 0.5
        ? current
        : { x: nextPoint.x, y: nextPoint.y };
    });
  }, []);
  const scheduleCursorSitePoint = useCallback(
    (nextPoint: CadPoint | null) => {
      pendingCursorSitePointRef.current = nextPoint;
      if (cursorSitePointRafRef.current !== null) return;
      cursorSitePointRafRef.current = window.requestAnimationFrame(() => {
        cursorSitePointRafRef.current = null;
        applyCursorSitePoint(pendingCursorSitePointRef.current);
      });
    },
    [applyCursorSitePoint],
  );
  const clearScheduledPointerState = useCallback(() => {
    if (cursorSitePointRafRef.current !== null) {
      window.cancelAnimationFrame(cursorSitePointRafRef.current);
      cursorSitePointRafRef.current = null;
    }
    if (draftPointerRafRef.current !== null) {
      window.cancelAnimationFrame(draftPointerRafRef.current);
      draftPointerRafRef.current = null;
    }
    pendingCursorSitePointRef.current = null;
    pendingDraftPointerRef.current = null;
    setCursorSitePoint(null);
    setDraftPreviewPoint(null);
    setActiveSnapPoint(null);
  }, []);
  const scheduleCanvasPanView = useCallback((nextView: { offsetX: number; offsetY: number }) => {
    pendingCanvasPanViewRef.current = nextView;
    if (canvasPanRafRef.current !== null) return;
    canvasPanRafRef.current = window.requestAnimationFrame(() => {
      canvasPanRafRef.current = null;
      const pending = pendingCanvasPanViewRef.current;
      pendingCanvasPanViewRef.current = null;
      if (!pending) return;
      setCanvasView((prev) =>
        Math.abs(prev.offsetX - pending.offsetX) < 0.5 && Math.abs(prev.offsetY - pending.offsetY) < 0.5
          ? prev
          : { ...prev, offsetX: pending.offsetX, offsetY: pending.offsetY },
      );
    });
  }, []);
  const clearScheduledCanvasPan = useCallback(() => {
    if (canvasPanRafRef.current !== null) {
      window.cancelAnimationFrame(canvasPanRafRef.current);
      canvasPanRafRef.current = null;
    }
    pendingCanvasPanViewRef.current = null;
  }, []);
  const finishCanvasPanInteraction = useCallback(() => {
    if (canvasPanStartedAtRef.current !== null) {
      measureCivoraInteractionAfterPaint("preview.pan.drag", canvasPanStartedAtRef.current, {
        mode: previewMode,
        quality: previewQuality,
      });
      canvasPanStartedAtRef.current = null;
    }
    clearScheduledCanvasPan();
  }, [clearScheduledCanvasPan, previewMode, previewQuality]);
  const scheduleDraftPointerState = useCallback(
    (sitePoint: (CadPoint & { kind: CadSnapKind }) | null) => {
      pendingDraftPointerRef.current = sitePoint;
      if (draftPointerRafRef.current !== null) return;
      draftPointerRafRef.current = window.requestAnimationFrame(() => {
        draftPointerRafRef.current = null;
        const nextPoint = pendingDraftPointerRef.current;
        setDraftPreviewPoint(nextPoint ? [nextPoint.x, nextPoint.y] : null);
        setActiveSnapPoint(nextPoint);
        applyCursorSitePoint(nextPoint);
      });
    },
    [applyCursorSitePoint],
  );
  useEffect(
    () => () => {
      if (cursorSitePointRafRef.current !== null) {
        window.cancelAnimationFrame(cursorSitePointRafRef.current);
      }
      if (draftPointerRafRef.current !== null) {
        window.cancelAnimationFrame(draftPointerRafRef.current);
      }
      if (canvasPanRafRef.current !== null) {
        window.cancelAnimationFrame(canvasPanRafRef.current);
      }
      if (hoverAnnotationRafRef.current !== null) {
        window.cancelAnimationFrame(hoverAnnotationRafRef.current);
      }
    },
    [],
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
  const scheduleHoverAnnotationState = useCallback(
    (
      annotation: (typeof previewLabels)[number] | null,
      point: { x: number; y: number } | null,
      setter: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>,
    ) => {
      pendingHoverAnnotationRef.current = { annotation, point, setter };
      if (hoverAnnotationRafRef.current !== null) return;
      hoverAnnotationRafRef.current = window.requestAnimationFrame(() => {
        hoverAnnotationRafRef.current = null;
        const pending = pendingHoverAnnotationRef.current;
        pendingHoverAnnotationRef.current = null;
        if (!pending) return;
        setHoveredAnnotation((current) =>
          current?.label === pending.annotation?.label ? current : pending.annotation,
        );
        pending.setter((current) => {
          if (!pending.point) return current === null ? current : null;
          return current &&
            Math.abs(current.x - pending.point.x) < 6 &&
            Math.abs(current.y - pending.point.y) < 6
            ? current
            : pending.point;
        });
      });
    },
    [],
  );
  const clearScheduledHoverAnnotationState = useCallback(
    (setter: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>) => {
      if (hoverAnnotationRafRef.current !== null) {
        window.cancelAnimationFrame(hoverAnnotationRafRef.current);
        hoverAnnotationRafRef.current = null;
      }
      pendingHoverAnnotationRef.current = null;
      setHoveredAnnotation(null);
      setter((current) => (current === null ? current : null));
    },
    [],
  );
  const resolveHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageBounds: { left: number; top: number; width: number; height: number } | null,
      setPoint: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>,
    ) => {
      if (!showHover || !containerRef.current || !hasInteractiveLabels) {
        clearScheduledHoverAnnotationState(setPoint);
        return;
      }
      const rect = containerRef.current.getBoundingClientRect();
      const bounds = imageBounds || { left: 0, top: 0, width: rect.width, height: rect.height };
      const relativeX = (event.clientX - rect.left - bounds.left) / Math.max(bounds.width, 1);
      const relativeY = (event.clientY - rect.top - bounds.top) / Math.max(bounds.height, 1);
      if (relativeX < 0 || relativeX > 1 || relativeY < 0 || relativeY > 1) {
        clearScheduledHoverAnnotationState(setPoint);
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
      if (!next) {
        clearScheduledHoverAnnotationState(setPoint);
        return;
      }
      const nextPoint = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      scheduleHoverAnnotationState(next, nextPoint, setPoint);
    },
    [clearScheduledHoverAnnotationState, hasInteractiveLabels, previewLabels, scheduleHoverAnnotationState, showHover],
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

  const getEditCapabilities = useCallback(
    (item: BuildingPlacement) => getPreviewEditCapabilities(item, siteLocked),
    [siteLocked],
  );

  const snapValue = useCallback((value: number, step: number) => snapPreviewValue(value, step), []);

  const getObjectGeometryPoints = useCallback(getPreviewObjectGeometryPoints, []);

  const getCadLayer = useCallback(getPreviewCadLayer, []);

  const cadLayerOptions = useMemo(() => {
    const layers = new Set(["C-DRAFT", "C-SITE", "C-ROAD", "C-UTIL", "C-DRAIN", "C-BLDG", "C-SYMB", "C-ANNO"]);
    [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements].forEach((item) => layers.add(getCadLayer(item)));
    return Array.from(layers).sort();
  }, [buildingPlacements, cadEntityPreviewObjects, getCadLayer, suggestedPlacements]);
  const objectManagerRows = useMemo(
    () => buildPreviewObjectManagerRows([...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements]),
    [buildingPlacements, cadEntityPreviewObjects, suggestedPlacements],
  );
  const objectManagerCounts = useMemo(
    () => buildPreviewObjectManagerCounts({ rows: objectManagerRows, hiddenCadLayers, getCadLayer }),
    [getCadLayer, hiddenCadLayers, objectManagerRows],
  );
  const getPreviewObjectDimensionsLabel = useCallback(resolvePreviewObjectDimensionsLabel, []);
  const getPreviewObjectSourceLabel = useCallback(
    (item: BuildingPlacement) =>
      resolvePreviewObjectSourceLabel(
        item,
        cadEntityPreviewObjects.some((candidate) => candidate.id === item.id),
      ),
    [cadEntityPreviewObjects],
  );
  const getPreviewObjectStatusLabel = useCallback(
    (item: BuildingPlacement) => resolvePreviewObjectStatusLabel(item, siteLocked),
    [siteLocked],
  );
  const previewObjectEditableSource = useCallback(
    (item: BuildingPlacement) =>
      buildingPlacements.some((candidate) => candidate.id === item.id) ||
      suggestedPlacements.some((candidate) => candidate.id === item.id),
    [buildingPlacements, suggestedPlacements],
  );
  const getPreviewObjectActionBlocker = useCallback(
    (item: BuildingPlacement | null, action: "rename" | "style" | "type" | "hide" | "delete" | "focus") =>
      resolvePreviewObjectActionBlocker({
        item,
        action,
        isEditableSource: item ? previewObjectEditableSource(item) : false,
        isCanonicalBuilding: item ? buildingPlacements.some((candidate) => candidate.id === item.id) : false,
      }),
    [buildingPlacements, previewObjectEditableSource],
  );
  const updatePreviewManagedObject = useCallback(
    (item: BuildingPlacement, updates: Partial<BuildingPlacement>) => {
      if (buildingPlacements.some((candidate) => candidate.id === item.id)) {
        onUpdateBuilding(item.id, updates);
        return true;
      }
      if (suggestedPlacements.some((candidate) => candidate.id === item.id)) {
        onUpdateSuggested(item.id, updates);
        return true;
      }
      return false;
    },
    [buildingPlacements, onUpdateBuilding, onUpdateSuggested, suggestedPlacements],
  );
  const focusPreviewManagedObject = useCallback(
    (item: BuildingPlacement | null) => {
      const blocker = getPreviewObjectActionBlocker(item, "focus");
      if (!item || blocker) {
        setCadCommandStatus(blocker || "FOCUS blocked: select an object first.");
        return;
      }
      setManagedObjectId(item.id);
      onSelectBuilding(item.id);
      setHoveredObjectId(item.id);
      setCanvasView(buildFocusedPreviewCanvasView(item, lotWidth, lotHeight));
      setCadCommandStatus(`Focused ${item.label || item.id}.`);
    },
    [getPreviewObjectActionBlocker, lotHeight, lotWidth, onSelectBuilding],
  );

  const visibleCadObjects = useMemo(
    () =>
      [...buildingPlacements, ...cadEntityPreviewObjects].filter(
        (item) => !hiddenCadLayers.includes(getCadLayer(item)) && !item.meta?.ui_hidden,
      ),
    [buildingPlacements, cadEntityPreviewObjects, getCadLayer, hiddenCadLayers],
  );

  const canvasCompositionSignature = useMemo(
    () =>
      visibleCadObjects
        .filter((item) => item.type !== "site" && item.placed && !item.meta?.ui_hidden)
        .map((item) => {
          const geometryLength = Array.isArray(item.geometry) ? item.geometry.length : 0;
          return `${item.id}:${item.type}:${Math.round(item.x ?? 0)},${Math.round(item.y ?? 0)},${Math.round(item.w ?? 0)},${Math.round(item.d ?? 0)}:${geometryLength}`;
        })
        .sort()
        .join("|"),
    [visibleCadObjects],
  );

  useEffect(() => {
    if (showMap || previewMode !== "2d" || userAdjustedCanvasViewRef.current) return;
    const signature = `${Math.round(currentSiteSize.width)}x${Math.round(currentSiteSize.height)}:${canvasCompositionSignature}`;
    if (autoFitSignatureRef.current === signature) return;
    autoFitSignatureRef.current = signature;
    const nextView = buildBalancedCanvasView();
    setCanvasView((current) =>
      Math.abs(current.scale - nextView.scale) < 0.001 &&
      Math.abs(current.offsetX - nextView.offsetX) < 0.5 &&
      Math.abs(current.offsetY - nextView.offsetY) < 0.5
        ? current
        : nextView,
    );
  }, [
    buildBalancedCanvasView,
    canvasCompositionSignature,
    currentSiteSize.height,
    currentSiteSize.width,
    previewMode,
    showMap,
  ]);

  const cadSegments = useMemo(() => {
    const segments: CadSegment2D[] = [];
    [...visibleCadObjects, ...suggestedPlacements].forEach((item) => {
      const points = getObjectGeometryPoints(item);
      if (points.length < 2) return;
      points.forEach((pt, idx) => {
        const isLast = idx === points.length - 1;
        if (isLast && item.geometryType === "polyline") return;
        const next = isLast ? points[0] : points[idx + 1];
        segments.push({
          a: { x: pt[0], y: pt[1] },
          b: { x: next[0], y: next[1] },
          objectId: item.id,
          segmentIndex: idx,
          closed: item.geometryType !== "polyline",
        });
      });
    });
    return segments;
  }, [getObjectGeometryPoints, suggestedPlacements, visibleCadObjects]);

  const resolveCadSnapPoint = useCallback(
    (point: CadPoint, basePoint?: CadPoint | null): (CadPoint & { kind: CadSnapKind }) => {
      const shouldIgnoreObjectSnap = drawMode === "site" || drawMode === "polygon";
      return resolveCadSnap(point, shouldIgnoreObjectSnap ? [] : cadSegments, {
        enabled: cadSnapEnabled,
        ortho: shouldIgnoreObjectSnap ? false : cadOrthoEnabled,
        basePoint,
        threshold: Math.max(lotWidth, lotHeight, 1) * 0.018,
        gridSize: 5,
      });
    },
    [cadOrthoEnabled, cadSegments, cadSnapEnabled, drawMode, lotHeight, lotWidth],
  );

  const updateCadObject = useCallback(
    (target: BuildingPlacement, updates: Partial<BuildingPlacement>, label: string) => {
      const after: BuildingPlacement = {
        ...target,
        ...updates,
        meta: {
          ...(target.meta ?? {}),
          ...(updates.meta ?? {}),
          source: "manual_drawn",
          classification_status: target.meta?.classification_status ?? "draft_review_required",
          engineering_status: target.meta?.engineering_status ?? "draft_review_required",
          review_status: target.meta?.review_status ?? "engineer_review_required",
          handoff_status: target.meta?.handoff_status ?? "draft_review_required",
          construction_release_allowed: false,
        },
        source: "manual_drawn",
        generated: false,
        placed: true,
      };
      setCadHistory((prev) => [
        ...prev.slice(-24),
        {
          id: `${Date.now()}-${target.id}`,
          label,
          objectId: target.id,
          before: { ...target, meta: { ...(target.meta ?? {}) } },
          after,
        },
      ]);
      setCadRedoStack([]);
      onUpdateBuilding(target.id, after);
    },
    [onUpdateBuilding],
  );

  const updateDraggedBuilding = useCallback(
    (event: React.MouseEvent<HTMLDivElement>, bounds: { left: number; top: number; width: number; height: number }) => {
      if (!draggingBuildingId || !draggingMode) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const transformedSitePoint = transformScreenToSitePoint(
        { x: event.clientX, y: event.clientY },
        { left: rect.left, top: rect.top },
        bounds,
        currentSiteSize,
        canvasView,
      );
      const sitePoint = resolveCadSnapPoint(transformedSitePoint, null);
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
      resolveCadSnapPoint,
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

  const selectedCadObject = useMemo(
    () => visibleCadObjects.find((item) => item.id === selectedBuildingId && item.type !== "site") ?? null,
    [selectedBuildingId, visibleCadObjects],
  );
  const selectedCadMetrics = useMemo(() => {
    const points = selectedCadObject ? getObjectGeometryPoints(selectedCadObject) : [];
    if (!selectedCadObject || points.length < 2) return null;
    const segments = points.map((point, index) => {
      if (index === points.length - 1 && selectedCadObject.geometryType === "polyline") return null;
      const next = index === points.length - 1 ? points[0] : points[index + 1];
      return {
        length: Math.hypot(next[0] - point[0], next[1] - point[1]),
        angle: ((Math.atan2(next[1] - point[1], next[0] - point[0]) * 180) / Math.PI + 360) % 360,
      };
    }).filter(Boolean) as Array<{ length: number; angle: number }>;
    return {
      segmentCount: segments.length,
      totalLength: segments.reduce((sum, segment) => sum + segment.length, 0),
      firstLength: segments[0]?.length ?? 0,
      firstAngle: segments[0]?.angle ?? 0,
      layer: getCadLayer(selectedCadObject),
    };
  }, [getCadLayer, getObjectGeometryPoints, selectedCadObject]);
  const topologyIssues = useMemo(
    () => validateTopology(visibleCadObjects.map((item) => ({
      id: item.id,
      type: item.type,
      geometryType: item.geometryType,
      geometry: Array.isArray(item.geometry) ? (item.geometry as Array<[number, number]>) : undefined,
      x: item.x,
      y: item.y,
      w: item.w,
      d: item.d,
    }))).slice(0, 8),
    [visibleCadObjects],
  );

  useEffect(() => {
    if (!selectedCadObject) return;
    const layer = getCadLayer(selectedCadObject);
    setCadLayerDraft(layer);
    setCadDimensionLabelDraft(String(selectedCadObject.meta?.cad_dimension_label || ""));
    const symbolAttributes = (selectedCadObject.meta?.symbol_attributes ?? {}) as Record<string, unknown>;
    setCadPropertyDraft({
      id: String(symbolAttributes.id || selectedCadObject.meta?.symbol_id || selectedCadObject.id || ""),
      name: selectedCadObject.label || "",
      type: selectedCadObject.type || "custom",
      layer,
      elevation: String(symbolAttributes.elevation || selectedCadObject.meta?.elevation || ""),
      material: String(symbolAttributes.material || selectedCadObject.meta?.material || ""),
      size: String(symbolAttributes.size || selectedCadObject.meta?.size || ""),
      source: String(symbolAttributes.source || selectedCadObject.meta?.source || "manual_drawn"),
      sourceNote: String(selectedCadObject.meta?.source_note || ""),
      reviewNote: String(selectedCadObject.meta?.review_note || ""),
    });
  }, [getCadLayer, selectedCadObject]);
  const selectedCadIds = useMemo(
    () => Array.from(new Set([...(selectedBuildingId ? [selectedBuildingId] : []), ...selectedObjectIds, ...cadSelectionSet])),
    [cadSelectionSet, selectedBuildingId, selectedObjectIds],
  );
  const hasCadCommandActivity = Boolean(selectedCadObject) || drawMode !== "select" || Boolean(cadActiveCommand) || cadCommandHistory.length > 0;
  const cadCommandStatusDisplay = useMemo(() => formatCalmCadStatus(cadCommandStatus), [cadCommandStatus]);
  const cadCommandHistoryDisplay = useMemo(
    () =>
      cadCommandHistory.map((entry) => ({
        ...entry,
        message: formatCalmCadStatus(entry.message),
      })),
    [cadCommandHistory],
  );
  useEffect(() => {
    const currentIds = new Set(buildingPlacements.map((item) => item.id));
    const previousIds = previousPlacementIdsRef.current;
    previousPlacementIdsRef.current = currentIds;
    if (!previousIds) return;

    const newlyAddedDrafts = buildingPlacements.filter(
      (item) =>
        !previousIds.has(item.id) &&
        item.type !== "site" &&
        (item.source === "manual_drawn" || item.meta?.source === "manual_drawn"),
    );
    if (newlyAddedDrafts.length !== 1) return;
    const [newlyAddedDraft] = newlyAddedDrafts;
    if (!newlyAddedDraft) return;

    setManagedObjectId(newlyAddedDraft.id);
    onSelectBuilding(newlyAddedDraft.id);
    onSelectObjects?.([newlyAddedDraft.id]);
    setCadSelectionSet([newlyAddedDraft.id]);
  }, [buildingPlacements, onSelectBuilding, onSelectObjects]);
  const applyCadHistorySnapshot = useCallback(
    (snapshot: BuildingPlacement) => {
      onUpdateBuilding(snapshot.id, {
        ...snapshot,
        meta: { ...(snapshot.meta ?? {}) },
      });
    },
    [onUpdateBuilding],
  );
  const undoCadCommand = useCallback(() => {
    const recordUndoFeedback = (status: CadCommandHistoryEntry["status"], message: string) => {
      setCadCommandStatus(message);
      setCadCommandHistory((prev) => [
        ...prev.slice(-11),
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          command: "UNDO",
          status,
          message,
        },
      ]);
    };
    const entry = cadHistory[cadHistory.length - 1];
    if (!entry) {
      if (lastPolylineEdit || lastRectEdit) {
        const polyTs = lastPolylineEdit?.ts ?? 0;
        const rectTs = lastRectEdit?.ts ?? 0;
        if (polyTs >= rectTs) applyPolylineUndo();
        else applyRectUndo();
        recordUndoFeedback("applied", "UNDO restored the last canvas drawing edit.");
      } else {
        recordUndoFeedback("blocked", "UNDO blocked: no draft history is available.");
      }
      return;
    }
    applyCadHistorySnapshot(entry.before);
    setCadHistory((prev) => prev.slice(0, -1));
    setCadRedoStack((prev) => [...prev, entry]);
    recordUndoFeedback("applied", "UNDO restored the last draft object edit.");
  }, [applyCadHistorySnapshot, applyPolylineUndo, applyRectUndo, cadHistory, lastPolylineEdit, lastRectEdit]);
  const redoCadCommand = useCallback(() => {
    const recordRedoFeedback = (status: CadCommandHistoryEntry["status"], message: string) => {
      setCadCommandStatus(message);
      setCadCommandHistory((prev) => [
        ...prev.slice(-11),
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          command: "REDO",
          status,
          message,
        },
      ]);
    };
    const entry = cadRedoStack[cadRedoStack.length - 1];
    if (!entry) {
      recordRedoFeedback("blocked", "REDO blocked: no draft redo history is available.");
      return;
    }
    applyCadHistorySnapshot(entry.after);
    setCadRedoStack((prev) => prev.slice(0, -1));
    setCadHistory((prev) => [...prev, entry]);
    recordRedoFeedback("applied", "REDO restored the draft object edit.");
  }, [applyCadHistorySnapshot, cadRedoStack]);
  const pushCadCommandFeedback = useCallback((command: string, status: CadCommandHistoryEntry["status"], message: string) => {
    setCadCommandStatus(message);
    setCadCommandHistory((prev) => [
      ...prev.slice(-11),
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        command: command || "COMMAND",
        status,
        message,
      },
    ]);
  }, []);
  const finishCadWindowSelect = useCallback(
    (windowRect: { startX: number; startY: number; currentX: number; currentY: number }) => {
      if (!previewRef.current) return;
      const crossingSelect = isCadCrossingSelection(windowRect);
      if (isCadWindowSelectionTooSmall(windowRect)) return;
      const candidates = Array.from(
        previewRef.current.querySelectorAll<HTMLElement>("[data-cad-object-id]"),
      );
      const selectableIds = resolveCadWindowSelectedObjectIds(windowRect, candidates, visibleCadObjects);
      setCadSelectionSet(selectableIds);
      onSelectObjects?.(selectableIds);
      onSelectBuilding(selectableIds[0] ?? null);
      setSelectedVertex(null);
      pushCadCommandFeedback(
        "SELECT",
        selectableIds.length ? "applied" : "blocked",
        selectableIds.length
          ? `${crossingSelect ? "Crossing" : "Window"} selected ${selectableIds.length} editable draft object${selectableIds.length === 1 ? "" : "s"}.`
          : `${crossingSelect ? "Crossing" : "Window"} select found no editable draft objects.`,
      );
    },
    [onSelectBuilding, onSelectObjects, pushCadCommandFeedback, visibleCadObjects],
  );
  const beginCadWindowSelect = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      if (!allowEdits || drawMode !== "select" || placementMode || event.button !== 0) return false;
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("button,input,textarea,select,[role='button'],[data-no-window-select]")) {
        return false;
      }
      const objectOverlay = target?.closest?.("[data-object-overlay]") as HTMLElement | null;
      if (objectOverlay) {
        const item = visibleCadObjects.find((candidate) => candidate.id === objectOverlay.dataset.cadObjectId);
        if (item?.type !== "site") return false;
      }
      const rect = previewRef.current?.getBoundingClientRect();
      event.preventDefault();
      event.stopPropagation();
      suppressNextObjectClickRef.current = true;
      setCadWindowSelect({
        startX: event.clientX,
        startY: event.clientY,
        currentX: event.clientX,
        currentY: event.clientY,
        containerLeft: rect?.left ?? 0,
        containerTop: rect?.top ?? 0,
      });
      return true;
    },
    [allowEdits, drawMode, placementMode, visibleCadObjects],
  );

  useEffect(() => {
    cadWindowSelectRef.current = cadWindowSelect;
  }, [cadWindowSelect]);

  useEffect(() => {
    if (!cadWindowSelect) return;
    const handleMove = (event: MouseEvent) => {
      setCadWindowSelect((current) =>
        current ? { ...current, currentX: event.clientX, currentY: event.clientY } : current,
      );
    };
    const handleUp = () => {
      const selection = cadWindowSelectRef.current;
      if (selection) finishCadWindowSelect(selection);
      cadWindowSelectRef.current = null;
      setCadWindowSelect(null);
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp, { once: true });
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [cadWindowSelect, finishCadWindowSelect]);

  const createCadCommandGeometry = useCallback(
    (
      command: string,
      mode: "polyline" | "polygon" | "rect" | "point",
      points: Array<[number, number]>,
      options: { label?: string; meta?: Record<string, unknown>; minPoints?: number } = {},
    ) => {
      const minPoints = options.minPoints ?? (mode === "point" ? 1 : mode === "rect" ? 2 : mode === "polygon" ? 3 : 2);
      if (!canDrawObjects) {
        pushCadCommandFeedback(command, "blocked", `${command.toUpperCase()} blocked: create or size the drawing canvas before creating draft geometry.`);
        return false;
      }
      if (points.length < minPoints) {
        pushCadCommandFeedback(command, "blocked", `${command.toUpperCase()} blocked: expected at least ${minPoints} coordinate point${minPoints === 1 ? "" : "s"}.`);
        return false;
      }
      onCreateCustomGeometry({
        mode,
        points,
        label: options.label,
        meta: buildReviewRequiredCommandMeta(command, options.meta),
      });
      pushCadCommandFeedback(command, "applied", buildDraftGeometryCreatedMessage(command));
      return true;
    },
    [canDrawObjects, onCreateCustomGeometry, pushCadCommandFeedback],
  );
  const transformSelectedCadObjects = useCallback(
    (kind: "move" | "rotate" | "scale" | "flip_horizontal" | "flip_vertical", valueOverride?: string) => {
      if (!selectedCadIds.length) {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: select one or more editable draft objects first.`);
        return;
      }
      const amount = parseCadNumber(valueOverride ?? cadTransformValue, kind === "scale" ? 1 : 0);
      let applied = 0;
      let blocked = 0;
      selectedCadIds.forEach((id) => {
        const target = buildingPlacements.find((item) => item.id === id);
        if (!target || target.locked || target.type === "site") {
          blocked += 1;
          return;
        }
        if (kind === "move") {
          const updates: Partial<BuildingPlacement> = {
            x: (target.x ?? 0) + amount,
            y: (target.y ?? 0) + amount,
          };
          if (Array.isArray(target.geometry)) {
            const moved = transformGeometry(target.geometry as Array<[number, number]>, "move", amount);
            if (!moved.ok) {
              blocked += 1;
              pushCadCommandFeedback("MOVE", "blocked", `MOVE blocked: ${moved.reason}`);
              return;
            }
            updates.geometry = moved.value;
          }
          updateCadObject(target, updates, "Move");
          applied += 1;
          return;
        }
        if (kind === "rotate") {
          const updates: Partial<BuildingPlacement> = { rotation: ((target.rotation ?? 0) + amount + 360) % 360 };
          if (Array.isArray(target.geometry)) {
            const rotated = transformGeometry(target.geometry as Array<[number, number]>, "rotate", amount);
            if (!rotated.ok) {
              blocked += 1;
              pushCadCommandFeedback("ROTATE", "blocked", `ROTATE blocked: ${rotated.reason}`);
              return;
            }
            updates.geometry = rotated.value;
            const nextBounds = boundsForSiteGeometry(rotated.value);
            updates.x = nextBounds.minX;
            updates.y = nextBounds.minY;
            updates.w = Math.max(5, nextBounds.width);
            updates.d = Math.max(5, nextBounds.height);
          }
          updateCadObject(target, updates, "Rotate");
          applied += 1;
          return;
        }
        if (kind === "flip_horizontal" || kind === "flip_vertical") {
          const updates: Partial<BuildingPlacement> = {
            meta: {
              ...(target.meta ?? {}),
              [kind === "flip_horizontal" ? "flipped_horizontal" : "flipped_vertical"]: true,
            },
          };
          if (Array.isArray(target.geometry)) {
            const flipped = transformGeometry(target.geometry as Array<[number, number]>, kind, 0);
            if (!flipped.ok) {
              blocked += 1;
              pushCadCommandFeedback("MIRROR", "blocked", `MIRROR blocked: ${flipped.reason}`);
              return;
            }
            updates.geometry = flipped.value;
          }
          updateCadObject(target, updates, kind === "flip_horizontal" ? "Flip horizontal" : "Flip vertical");
          applied += 1;
          return;
        }
        const factor = amount;
        if (factor <= 0) {
          blocked += 1;
          pushCadCommandFeedback("SCALE", "blocked", "SCALE blocked: scale requires a positive factor.");
          return;
        }
        const nextW = Math.max(1, target.w * factor);
        const nextD = Math.max(1, target.d * factor);
        const updates: Partial<BuildingPlacement> = { w: nextW, d: nextD };
        if (Array.isArray(target.geometry)) {
          const scaled = transformGeometry(target.geometry as Array<[number, number]>, "scale", factor);
          if (!scaled.ok) {
            blocked += 1;
            pushCadCommandFeedback("SCALE", "blocked", `SCALE blocked: ${scaled.reason}`);
            return;
          }
          updates.geometry = scaled.value;
          const nextBounds = boundsForSiteGeometry(scaled.value);
          updates.x = nextBounds.minX;
          updates.y = nextBounds.minY;
          updates.w = Math.max(5, nextBounds.width);
          updates.d = Math.max(5, nextBounds.height);
        }
        updateCadObject(target, updates, "Scale");
        applied += 1;
      });
      if (applied || blocked) {
        pushCadCommandFeedback(
          kind,
          applied ? "applied" : "blocked",
          `${kind === "flip_horizontal" ? "MIRROR H" : kind === "flip_vertical" ? "MIRROR V" : kind.toUpperCase()} ${applied ? `applied to ${applied}` : "blocked for all"} selected object${applied === 1 ? "" : "s"}${blocked ? `; ${blocked} blocked` : ""}.`,
        );
      }
    },
    [buildingPlacements, cadTransformValue, pushCadCommandFeedback, selectedCadIds, updateCadObject],
  );
  const moveSelectedCadObjectsByVector = useCallback(
    (dx: number, dy: number) => {
      if (!selectedCadIds.length) {
        pushCadCommandFeedback("MOVE", "blocked", "MOVE blocked: select one or more editable draft objects first.");
        return;
      }
      if (!Number.isFinite(dx) || !Number.isFinite(dy) || (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001)) {
        pushCadCommandFeedback("MOVE", "blocked", "MOVE blocked: provide a non-zero displacement like MOVE selected 20,0.");
        return;
      }
      let applied = 0;
      let blocked = 0;
      selectedCadIds.forEach((id) => {
        const target = buildingPlacements.find((item) => item.id === id);
        if (!target || target.locked || target.type === "site") {
          blocked += 1;
          return;
        }
        const updates: Partial<BuildingPlacement> = {
          x: (target.x ?? 0) + dx,
          y: (target.y ?? 0) + dy,
        };
        if (Array.isArray(target.geometry)) {
          updates.geometry = translateSiteGeometry(target.geometry as Array<[number, number]>, { x: dx, y: dy });
        }
        updateCadObject(target, updates, "Move");
        applied += 1;
      });
      pushCadCommandFeedback(
        "MOVE",
        applied ? "applied" : "blocked",
        `MOVE ${applied ? `applied ${dx.toFixed(3).replace(/\.?0+$/, "")},${dy.toFixed(3).replace(/\.?0+$/, "")} to ${applied}` : "blocked for all"} selected draft object${applied === 1 ? "" : "s"}${blocked ? `; ${blocked} blocked` : ""}.`,
      );
    },
    [buildingPlacements, pushCadCommandFeedback, selectedCadIds, updateCadObject],
  );
  const copySelectedCadObjectsByVector = useCallback(
    (vectorOverride?: [number, number]) => {
      if (!selectedCadIds.length) {
        pushCadCommandFeedback("COPY", "blocked", "COPY blocked: select one or more editable draft objects first.");
        return;
      }
      const vector = vectorOverride ?? [10, 10];
      if (!Number.isFinite(vector[0]) || !Number.isFinite(vector[1]) || (Math.abs(vector[0]) < 0.001 && Math.abs(vector[1]) < 0.001)) {
        pushCadCommandFeedback("COPY", "blocked", "COPY blocked: provide a non-zero vector like COPY 20,0.");
        return;
      }
      let created = 0;
      let blocked = 0;
      selectedCadIds.forEach((id) => {
        const target = buildingPlacements.find((item) => item.id === id);
        if (!target || target.locked || target.type === "site") {
          blocked += 1;
          return;
        }
        const selectedGeometry = getObjectGeometryPoints(target);
        if (!selectedGeometry.length) {
          blocked += 1;
          return;
        }
        const copiedGeometry = translateSiteGeometry(selectedGeometry, { x: vector[0], y: vector[1] }) ?? selectedGeometry;
        const mode =
          target.geometryType === "point"
            ? "point"
            : target.geometryType === "polyline"
              ? "polyline"
              : "polygon";
        onCreateCustomGeometry({
          mode,
          points: copiedGeometry,
          label: `${target.label || "Draft object"} Copy`,
          meta: buildReviewRequiredCommandMeta("COPY", {
            copied_from_object_id: target.id,
            copied_object_type: target.type,
            copy_vector: vector,
            source_type: "manual_drawn_copy",
            source_confidence: "draft_review_required",
            cad_layer: getCadLayer(target),
          }),
        });
        created += 1;
      });
      pushCadCommandFeedback(
        "COPY",
        created ? "applied" : "blocked",
        created
          ? `COPY created ${created} draft review cop${created === 1 ? "y" : "ies"} from selected object${selectedCadIds.length === 1 ? "" : "s"}${blocked ? `; ${blocked} blocked` : ""}.`
          : "COPY blocked: selected objects are locked or have no editable draft geometry.",
      );
    },
    [buildingPlacements, getCadLayer, getObjectGeometryPoints, onCreateCustomGeometry, pushCadCommandFeedback, selectedCadIds],
  );
  const alignOrDistributeSelectedCadObjects = useCallback(
    (
      command: "ALIGN" | "DISTRIBUTE",
      mode: "LEFT" | "RIGHT" | "CENTER" | "TOP" | "BOTTOM" | "MIDDLE" | "X" | "Y",
    ) => {
      const selectedTargets = selectedCadIds
        .map((id) => buildingPlacements.find((item) => item.id === id))
        .filter((item): item is BuildingPlacement => Boolean(item && !item.locked && item.type !== "site"));
      const minimum = command === "DISTRIBUTE" ? 3 : 2;
      if (selectedTargets.length < minimum) {
        pushCadCommandFeedback(
          command,
          "blocked",
          `${command} blocked: select at least ${minimum} editable draft objects first.`,
        );
        return;
      }
      const frameForObject = (item: BuildingPlacement) => {
        const points = getObjectGeometryPoints(item);
        const bounds = points.length ? boundsForSiteGeometry(points) : null;
        const left = bounds ? bounds.minX : item.x ?? 0;
        const top = bounds ? bounds.minY : item.y ?? 0;
        const width = Math.max(1, bounds ? bounds.width : item.w ?? 1);
        const height = Math.max(1, bounds ? bounds.height : item.d ?? 1);
        return {
          left,
          top,
          right: left + width,
          bottom: top + height,
          centerX: left + width / 2,
          centerY: top + height / 2,
          width,
          height,
        };
      };
      const moveTargetBy = (target: BuildingPlacement, dx: number, dy: number, label: string) => {
        if (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001) return false;
        const updates: Partial<BuildingPlacement> = {
          x: (target.x ?? 0) + dx,
          y: (target.y ?? 0) + dy,
        };
        if (Array.isArray(target.geometry)) {
          updates.geometry = translateSiteGeometry(target.geometry as Array<[number, number]>, { x: dx, y: dy });
        }
        updateCadObject(target, updates, label);
        return true;
      };

      let moved = 0;
      if (command === "ALIGN") {
        const anchor = selectedTargets[0];
        const anchorFrame = frameForObject(anchor);
        selectedTargets.forEach((target) => {
          const frame = frameForObject(target);
          let dx = 0;
          let dy = 0;
          if (mode === "LEFT") dx = anchorFrame.left - frame.left;
          if (mode === "RIGHT") dx = anchorFrame.right - frame.right;
          if (mode === "CENTER" || mode === "X") dx = anchorFrame.centerX - frame.centerX;
          if (mode === "TOP") dy = anchorFrame.top - frame.top;
          if (mode === "BOTTOM") dy = anchorFrame.bottom - frame.bottom;
          if (mode === "MIDDLE" || mode === "Y") dy = anchorFrame.centerY - frame.centerY;
          if (moveTargetBy(target, dx, dy, `Align ${mode.toLowerCase()}`)) moved += 1;
        });
        pushCadCommandFeedback(
          "ALIGN",
          "applied",
          `ALIGN ${mode} aligned ${selectedTargets.length} selected draft object${selectedTargets.length === 1 ? "" : "s"} to ${anchor.label || "the first selected object"}${moved ? "" : " (already aligned)"}.`,
        );
        return;
      }

      const axis = mode === "Y" || mode === "MIDDLE" ? "Y" : "X";
      const sorted = [...selectedTargets].sort((a, b) => {
        const frameA = frameForObject(a);
        const frameB = frameForObject(b);
        return axis === "X" ? frameA.centerX - frameB.centerX : frameA.centerY - frameB.centerY;
      });
      const firstFrame = frameForObject(sorted[0]);
      const lastFrame = frameForObject(sorted[sorted.length - 1]);
      const start = axis === "X" ? firstFrame.centerX : firstFrame.centerY;
      const end = axis === "X" ? lastFrame.centerX : lastFrame.centerY;
      if (Math.abs(end - start) < 0.001) {
        pushCadCommandFeedback("DISTRIBUTE", "blocked", `DISTRIBUTE ${axis} blocked: selected objects need different ${axis.toLowerCase()} positions.`);
        return;
      }
      const step = (end - start) / (sorted.length - 1);
      sorted.slice(1, -1).forEach((target, index) => {
        const frame = frameForObject(target);
        const desired = start + step * (index + 1);
        const dx = axis === "X" ? desired - frame.centerX : 0;
        const dy = axis === "Y" ? desired - frame.centerY : 0;
        if (moveTargetBy(target, dx, dy, `Distribute ${axis}`)) moved += 1;
      });
      pushCadCommandFeedback(
        "DISTRIBUTE",
        "applied",
        `DISTRIBUTE ${axis} spaced ${selectedTargets.length} selected draft objects evenly${moved ? "" : " (already spaced)"}.`,
      );
    },
    [buildingPlacements, getObjectGeometryPoints, pushCadCommandFeedback, selectedCadIds, updateCadObject],
  );
  const arraySelectedCadObject = useCallback(
    (rowCount: number, columnCount: number, spacing: [number, number]) => {
      if (!selectedCadObject || !Array.isArray(selectedCadObject.geometry)) {
        pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: select one editable draft object with geometry first.");
        return;
      }
      const rows = Math.max(1, Math.min(20, Math.floor(rowCount || 1)));
      const columns = Math.max(1, Math.min(20, Math.floor(columnCount || 1)));
      if (rows * columns <= 1) {
        pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: use at least 2 total copies, like ARRAY 2 3 20,15.");
        return;
      }
      const [dx, dy] = spacing;
      if (!Number.isFinite(dx) || !Number.isFinite(dy) || (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001)) {
        pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: provide a non-zero spacing vector like ARRAY 2 3 20,15.");
        return;
      }
      const sourceGeometry = selectedCadObject.geometry as Array<[number, number]>;
      let created = 0;
      for (let row = 0; row < rows; row += 1) {
        for (let column = 0; column < columns; column += 1) {
          if (row === 0 && column === 0) continue;
          const copiedGeometry = translateSiteGeometry(sourceGeometry, { x: dx * column, y: dy * row }) ?? sourceGeometry;
          const ok = createCadCommandGeometry("ARRAY", selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect" ? "polygon" : "polyline", copiedGeometry, {
            label: `${selectedCadObject.label || "Draft object"} Array ${row + 1}-${column + 1}`,
            meta: {
              array_source_object_id: selectedCadObject.id,
              array_rows: rows,
              array_columns: columns,
              array_spacing: [dx, dy],
            },
            minPoints: selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect" ? 3 : 2,
          });
          if (ok) created += 1;
        }
      }
      pushCadCommandFeedback("ARRAY", created ? "applied" : "blocked", created ? `ARRAY created ${created} draft review cop${created === 1 ? "y" : "ies"} from ${selectedCadObject.label || "selected object"}.` : "ARRAY blocked: no copies could be created.");
    },
    [createCadCommandGeometry, pushCadCommandFeedback, selectedCadObject],
  );
  const joinSelectedCadObjects = useCallback(() => {
    const selectedTargets = selectedCadIds
      .map((id) => buildingPlacements.find((item) => item.id === id))
      .filter((item): item is BuildingPlacement => Boolean(
        item &&
          item.type !== "site" &&
          !item.locked &&
          !item.meta?.ui_hidden &&
          Array.isArray(item.geometry) &&
          item.geometry.length >= 2,
      ));
    if (selectedTargets.length < 2) {
      pushCadCommandFeedback("JOIN", "blocked", "JOIN blocked: select two or more editable draft line/area objects first.");
      return;
    }
    const remaining = selectedTargets.map((item) => ({
      item,
      geometry: (item.geometry as Array<[number, number]>).map(([x, y]) => [x, y] as [number, number]),
    }));
    const first = remaining.shift();
    if (!first) {
      pushCadCommandFeedback("JOIN", "blocked", "JOIN blocked: selected geometry could not be read.");
      return;
    }
    const joinedGeometry = [...first.geometry];
    const distance = (a: [number, number], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1]);
    while (remaining.length) {
      const tail = joinedGeometry[joinedGeometry.length - 1];
      let bestIndex = 0;
      let bestReverse = false;
      let bestDistance = Number.POSITIVE_INFINITY;
      remaining.forEach((candidate, index) => {
        const start = candidate.geometry[0];
        const end = candidate.geometry[candidate.geometry.length - 1];
        const startDistance = distance(tail, start);
        const endDistance = distance(tail, end);
        if (startDistance < bestDistance) {
          bestDistance = startDistance;
          bestIndex = index;
          bestReverse = false;
        }
        if (endDistance < bestDistance) {
          bestDistance = endDistance;
          bestIndex = index;
          bestReverse = true;
        }
      });
      const [next] = remaining.splice(bestIndex, 1);
      const nextGeometry = bestReverse ? [...next.geometry].reverse() : next.geometry;
      const nextStart = nextGeometry[0];
      joinedGeometry.push(
        ...(distance(tail, nextStart) < 0.001 ? nextGeometry.slice(1) : nextGeometry),
      );
    }
    if (joinedGeometry.length < 2) {
      pushCadCommandFeedback("JOIN", "blocked", "JOIN blocked: selected geometry did not produce a joined line.");
      return;
    }
    const joinedLabel =
      selectedTargets.length === 2
        ? `${selectedTargets[0].label || "Draft"} + ${selectedTargets[1].label || "Draft"} Join`
        : `Joined Draft Object ${selectedTargets.length}`;
    selectedTargets.forEach((item) => {
      onUpdateBuilding(item.id, {
        meta: {
          ...(item.meta ?? {}),
          ui_hidden: true,
          joined_source_trace: true,
          joined_into_label: joinedLabel,
          review_status: "engineer_review_required",
          engineering_status: "draft_review_required",
          construction_release_allowed: false,
        },
      });
    });
    onCreateCustomGeometry({
      mode: "polyline",
      points: joinedGeometry,
      label: joinedLabel,
      meta: buildReviewRequiredCommandMeta("JOIN", {
        joined_from_object_ids: selectedTargets.map((item) => item.id),
        joined_from_labels: selectedTargets.map((item) => item.label),
        joined_source_count: selectedTargets.length,
        cad_layer: getCadLayer(selectedTargets[0]),
        source_type: "manual_drawn_join",
      }),
    });
    setCadSelectionSet([]);
    onSelectObjects?.([]);
    pushCadCommandFeedback("JOIN", "applied", `JOIN created ${joinedLabel} from ${selectedTargets.length} draft source objects; sources are hidden as review trace pieces.`);
  }, [
    buildingPlacements,
    getCadLayer,
    onCreateCustomGeometry,
    onSelectObjects,
    onUpdateBuilding,
    pushCadCommandFeedback,
    selectedCadIds,
  ]);
  const splitSelectedJoinedObject = useCallback(() => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("SPLIT", "blocked", "SPLIT blocked: select one joined draft object first.");
      return;
    }
    const sourceIds = Array.isArray(selectedCadObject.meta?.joined_from_object_ids)
      ? selectedCadObject.meta.joined_from_object_ids.map((id) => String(id)).filter(Boolean)
      : [];
    if (!sourceIds.length) {
      pushCadCommandFeedback("SPLIT", "blocked", "SPLIT blocked: selected object has no joined source trace to restore.");
      return;
    }
    const sourceObjects = buildingPlacements.filter((item) => sourceIds.includes(item.id));
    if (!sourceObjects.length) {
      pushCadCommandFeedback("SPLIT", "blocked", "SPLIT blocked: joined source trace objects are missing.");
      return;
    }
    sourceObjects.forEach((item) => {
      onUpdateBuilding(item.id, {
        meta: {
          ...(item.meta ?? {}),
          ui_hidden: false,
          split_from_joined_object_id: selectedCadObject.id,
          split_from_joined_label: selectedCadObject.label,
          review_status: "engineer_review_required",
          engineering_status: "draft_review_required",
          construction_release_allowed: false,
        },
      });
    });
    onRemoveBuilding(selectedCadObject.id);
    setCadSelectionSet(sourceObjects.map((item) => item.id));
    onSelectObjects?.(sourceObjects.map((item) => item.id));
    onSelectBuilding(sourceObjects[0]?.id ?? null);
    pushCadCommandFeedback("SPLIT", "applied", `SPLIT restored ${sourceObjects.length} source trace object${sourceObjects.length === 1 ? "" : "s"} from ${selectedCadObject.label || "joined object"}.`);
  }, [
    buildingPlacements,
    onRemoveBuilding,
    onSelectBuilding,
    onSelectObjects,
    onUpdateBuilding,
    pushCadCommandFeedback,
    selectedCadObject,
  ]);
  const changeSelectedPolylineState = useCallback((mode: "close" | "open" | "reverse") => {
    const command = mode === "close" ? "CLOSE" : mode === "open" ? "OPEN" : "REVERSE";
    if (!selectedCadObject || !Array.isArray(selectedCadObject.geometry) || selectedCadObject.geometry.length < 2) {
      pushCadCommandFeedback(command, "blocked", `${command} blocked: select one editable draft line or area object first.`);
      return;
    }
    if (selectedCadObject.type === "site" || selectedCadObject.locked || !previewObjectEditableSource(selectedCadObject)) {
      pushCadCommandFeedback(command, "blocked", `${command} blocked: selected object is locked, source-only, or required project evidence.`);
      return;
    }
    const geometry = (selectedCadObject.geometry as Array<[number, number]>).map(([x, y]) => [x, y] as [number, number]);
    if (geometry.length < 2) {
      pushCadCommandFeedback(command, "blocked", `${command} blocked: selected object has no editable vertices.`);
      return;
    }
    const first = geometry[0];
    const last = geometry[geometry.length - 1];
    const explicitlyClosed = Boolean(last && Math.hypot(first[0] - last[0], first[1] - last[1]) < 0.001);
    const stripDuplicateClosure = () => (explicitlyClosed ? geometry.slice(0, -1) : geometry);
    if (mode === "close") {
      const base = stripDuplicateClosure();
      if (base.length < 3) {
        pushCadCommandFeedback("CLOSE", "blocked", "CLOSE blocked: draft linework needs at least three vertices to become a closed area.");
        return;
      }
      if (selectedCadObject.geometryType !== "polyline" && !explicitlyClosed) {
        pushCadCommandFeedback("CLOSE", "info", "CLOSE skipped: selected object is already treated as closed area geometry.");
        return;
      }
      const nextGeometry = [...base, base[0]];
      const nextBounds = boundsForSiteGeometry(nextGeometry);
      updateCadObject(
        selectedCadObject,
        {
          geometry: nextGeometry,
          geometryType: "polygon",
          x: nextBounds.minX,
          y: nextBounds.minY,
          w: Math.max(5, nextBounds.width),
          d: Math.max(5, nextBounds.height),
          meta: {
            ...(selectedCadObject.meta ?? {}),
            cad_polyline_closed: true,
            cad_polyline_state_command: "CLOSE",
            engineering_status: "draft_review_required",
            review_status: "engineer_review_required",
            construction_release_allowed: false,
          },
        },
        "Close polyline",
      );
      pushCadCommandFeedback("CLOSE", "applied", "CLOSE converted selected draft linework into closed review area geometry.");
      return;
    }
    if (mode === "open") {
      if (selectedCadObject.geometryType === "polyline" && !explicitlyClosed) {
        pushCadCommandFeedback("OPEN", "info", "OPEN skipped: selected linework is already open.");
        return;
      }
      const nextGeometry = stripDuplicateClosure();
      if (nextGeometry.length < 2) {
        pushCadCommandFeedback("OPEN", "blocked", "OPEN blocked: opening this object would leave too few vertices.");
        return;
      }
      const nextBounds = boundsForSiteGeometry(nextGeometry);
      updateCadObject(
        selectedCadObject,
        {
          geometry: nextGeometry,
          geometryType: "polyline",
          x: nextBounds.minX,
          y: nextBounds.minY,
          w: Math.max(5, nextBounds.width),
          d: Math.max(5, nextBounds.height),
          meta: {
            ...(selectedCadObject.meta ?? {}),
            cad_polyline_closed: false,
            cad_polyline_state_command: "OPEN",
            engineering_status: "draft_review_required",
            review_status: "engineer_review_required",
            construction_release_allowed: false,
          },
        },
        "Open polyline",
      );
      pushCadCommandFeedback("OPEN", "applied", "OPEN converted selected draft area into open review linework.");
      return;
    }
    const nextGeometry = [...geometry].reverse();
    const nextBounds = boundsForSiteGeometry(nextGeometry);
    updateCadObject(
      selectedCadObject,
      {
        geometry: nextGeometry,
        x: nextBounds.minX,
        y: nextBounds.minY,
        w: Math.max(5, nextBounds.width),
        d: Math.max(5, nextBounds.height),
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_polyline_state_command: "REVERSE",
          engineering_status: "draft_review_required",
          review_status: "engineer_review_required",
          construction_release_allowed: false,
        },
      },
      "Reverse polyline",
    );
    pushCadCommandFeedback("REVERSE", "applied", "REVERSE flipped the selected draft linework vertex order.");
  }, [previewObjectEditableSource, pushCadCommandFeedback, selectedCadObject, updateCadObject]);
  const toggleSelectedCadHatch = useCallback(() => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("HATCH", "blocked", "HATCH blocked: select a closed draft area, box, building, basin, parking field, or closed polyline first.");
      return;
    }
    if (selectedCadObject.type === "site" || selectedCadObject.locked || !previewObjectEditableSource(selectedCadObject)) {
      pushCadCommandFeedback("HATCH", "blocked", "HATCH blocked: selected object is locked, source-only, or required project evidence.");
      return;
    }
    const geometry = Array.isArray(selectedCadObject.geometry)
      ? (selectedCadObject.geometry as Array<[number, number]>)
      : [];
    const first = geometry[0];
    const last = geometry[geometry.length - 1];
    const closedLinework = Boolean(
      geometry.length >= 4 &&
        first &&
        last &&
        Math.hypot(first[0] - last[0], first[1] - last[1]) < 0.001,
    );
    const closedArea =
      selectedCadObject.geometryType === "polygon" ||
      selectedCadObject.geometryType === "rect" ||
      (!selectedCadObject.geometryType && selectedCadObject.type !== "utility_corridor") ||
      Boolean(selectedCadObject.meta?.cad_polyline_closed) ||
      closedLinework;
    if (!closedArea) {
      pushCadCommandFeedback("HATCH", "blocked", "HATCH blocked: select a closed draft area, or use CLOSE first to turn linework into an area.");
      return;
    }
    const enabled = Boolean(selectedCadObject.meta?.cad_hatch_enabled);
    const visualKind = resolveVisualKind(selectedCadObject);
    const pattern =
      visualKind === "water"
        ? "water"
        : visualKind === "landscape"
          ? "landscape"
          : "diagonal";
    updateCadObject(
      selectedCadObject,
      {
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_hatch_enabled: !enabled,
          cad_hatch_pattern: pattern,
          cad_hatch_source: "manual_drawn_review",
          engineering_status: "draft_review_required",
          review_status: "engineer_review_required",
          construction_release_allowed: false,
        },
      },
      enabled ? "Remove hatch" : "Apply hatch",
    );
    pushCadCommandFeedback(
      "HATCH",
      "applied",
      enabled
        ? "HATCH removed from selected draft area."
        : "HATCH applied as draft review fill; it is visual drafting context only and not engineering evidence.",
    );
  }, [previewObjectEditableSource, pushCadCommandFeedback, resolveVisualKind, selectedCadObject, updateCadObject]);
  const applyCadCoordinate = useCallback(() => {
    const x = parseCadNumber(cadCoordinateDraft.x, NaN);
    const y = parseCadNumber(cadCoordinateDraft.y, NaN);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    if (selectedCadObject) {
      const delta = { x: x - (selectedCadObject.x ?? 0), y: y - (selectedCadObject.y ?? 0) };
      const updates: Partial<BuildingPlacement> = { x, y };
      if (Array.isArray(selectedCadObject.geometry)) {
        updates.geometry = translateSiteGeometry(selectedCadObject.geometry as Array<[number, number]>, delta);
      }
      updateCadObject(selectedCadObject, updates, "Coordinate input");
      return;
    }
    setDraftPoints((prev) => [...prev, [clampValue(x, 0, lotWidth), clampValue(y, 0, lotHeight)]]);
    setDrawMode((prev) => prev === "select" ? "polyline" : prev);
    onSetPreviewInteraction("edit");
  }, [cadCoordinateDraft.x, cadCoordinateDraft.y, lotHeight, lotWidth, onSetPreviewInteraction, selectedCadObject, updateCadObject]);
  const applySelectedCadLayer = useCallback(() => {
    if (!selectedCadIds.length) {
      pushCadCommandFeedback("LAYER", "blocked", "LAYER blocked: select one or more editable draft objects first.");
      return;
    }
    let appliedCount = 0;
    selectedCadIds.forEach((id) => {
      const target = buildingPlacements.find((item) => item.id === id);
      if (!target || target.locked || target.type === "site") return;
      updateCadObject(target, { meta: { ...(target.meta ?? {}), cad_layer: cadLayerDraft || "C-DRAFT" } }, "Layer");
      appliedCount += 1;
    });
    if (appliedCount) {
      pushCadCommandFeedback("LAYER", "applied", `LAYER applied to ${appliedCount} draft object${appliedCount === 1 ? "" : "s"}.`);
    } else {
      pushCadCommandFeedback("LAYER", "blocked", "LAYER blocked: selected objects are locked or not editable draft objects.");
    }
  }, [buildingPlacements, cadLayerDraft, pushCadCommandFeedback, selectedCadIds, updateCadObject]);
  const offsetSelectedCadObject = useCallback(() => {
    if (!selectedCadObject) return;
    const distance = parseCadNumber(cadOffsetDistance, 0);
    if (!distance) return;
    if (!Array.isArray(selectedCadObject.geometry)) {
      setCadCommandStatus("OFFSET blocked: selected object has no editable line or polygon vertices.");
      return;
    }
    const result = offsetGeometry(
      selectedCadObject.geometry as Array<[number, number]>,
      distance,
      selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect",
    );
    if (!result.ok) {
      setCadCommandStatus(`OFFSET blocked: ${result.reason}`);
      return;
    }
    const nextBounds = boundsForSiteGeometry(result.value);
    const updates: Partial<BuildingPlacement> = {
      geometry: result.value,
      x: nextBounds.minX,
      y: nextBounds.minY,
      w: Math.max(5, nextBounds.width),
      d: Math.max(5, nextBounds.height),
      meta: {
        ...(selectedCadObject.meta ?? {}),
        cad_offset_distance_ft: distance,
        geometry_kernel_warnings: result.warnings ?? [],
      },
    };
    updateCadObject(selectedCadObject, updates, "Offset");
    setCadCommandStatus(`OFFSET applied ${distance} ft as draft review geometry.`);
  }, [cadOffsetDistance, selectedCadObject, updateCadObject]);
  const offsetSelectedCadObjectBy = useCallback((valueOverride?: string) => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("OFFSET", "blocked", "OFFSET blocked: select one editable draft object first.");
      return;
    }
    const distance = parseCadNumber(valueOverride ?? cadOffsetDistance, 0);
    if (!distance) {
      pushCadCommandFeedback("OFFSET", "blocked", "OFFSET blocked: provide a non-zero distance like OFFSET 10.");
      return;
    }
    if (!Array.isArray(selectedCadObject.geometry)) {
      pushCadCommandFeedback("OFFSET", "blocked", "OFFSET blocked: selected object has no editable line or polygon vertices.");
      return;
    }
    const result = offsetGeometry(
      selectedCadObject.geometry as Array<[number, number]>,
      distance,
      selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect",
    );
    if (!result.ok) {
      pushCadCommandFeedback("OFFSET", "blocked", `OFFSET blocked: ${result.reason}`);
      return;
    }
    const nextBounds = boundsForSiteGeometry(result.value);
    const updates: Partial<BuildingPlacement> = {
      geometry: result.value,
      x: nextBounds.minX,
      y: nextBounds.minY,
      w: Math.max(5, nextBounds.width),
      d: Math.max(5, nextBounds.height),
      meta: {
        ...(selectedCadObject.meta ?? {}),
        cad_offset_distance_ft: distance,
        geometry_kernel_warnings: result.warnings ?? [],
      },
    };
    updateCadObject(selectedCadObject, updates, "Offset");
    pushCadCommandFeedback("OFFSET", "applied", `OFFSET applied ${distance} ft as draft review geometry.`);
  }, [cadOffsetDistance, pushCadCommandFeedback, selectedCadObject, updateCadObject]);
  const trimExtendSelectedCadObject = useCallback(
    (kind: "trim" | "extend", amountOverride?: string) => {
      if (!selectedCadObject || !Array.isArray(selectedCadObject.geometry)) {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: select one editable line/polyline draft object first.`);
        return;
      }
      const geometry = selectedCadObject.geometry as Array<[number, number]>;
      const amount = Math.max(1, parseCadNumber(amountOverride ?? cadTransformValue, 10));
      if (selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect") {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: polygon trim/extend needs an explicit cutting edge and is not applied automatically.`);
        return;
      }
      const result = trimOrExtendGeometry(geometry, kind, cadSegments, {
        amountFt: amount,
        selectedObjectId: selectedCadObject.id,
        siteWidth: lotWidth,
        siteHeight: lotHeight,
      });
      if (!result.ok) {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: ${result.reason}`);
        return;
      }
      const nextBounds = boundsForSiteGeometry(result.value);
      updateCadObject(
        selectedCadObject,
        {
          geometry: result.value,
          x: nextBounds.minX,
          y: nextBounds.minY,
          w: Math.max(5, nextBounds.width),
          d: Math.max(5, nextBounds.height),
        },
        kind === "trim" ? "Trim" : "Extend",
      );
      pushCadCommandFeedback(kind, "applied", `${kind.toUpperCase()} applied to terminal segment as draft review geometry.`);
    },
    [cadSegments, cadTransformValue, lotHeight, lotWidth, pushCadCommandFeedback, selectedCadObject, updateCadObject],
  );
  const filletSelectedCadObject = useCallback(() => {
    if (!selectedCadObject || !Array.isArray(selectedCadObject.geometry)) {
      pushCadCommandFeedback("FILLET", "blocked", "FILLET blocked: select one editable draft object with vertices first.");
      return;
    }
    const geometry = selectedCadObject.geometry as Array<[number, number]>;
    const radius = Math.max(1, parseCadNumber(cadFilletRadius, 5));
    const index = selectedVertex?.id === selectedCadObject.id ? selectedVertex.index : 1;
    const result = filletGeometry(
      geometry,
      radius,
      index,
      selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect",
    );
    if (!result.ok) {
      pushCadCommandFeedback("FILLET", "blocked", `FILLET blocked: ${result.reason}`);
      return;
    }
    const nextBounds = boundsForSiteGeometry(result.value);
    updateCadObject(
      selectedCadObject,
      {
        geometry: result.value,
        x: nextBounds.minX,
        y: nextBounds.minY,
        w: Math.max(5, nextBounds.width),
        d: Math.max(5, nextBounds.height),
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_fillet_radius_ft: radius,
          cad_fillet_storage: "tangent_chord_vertices",
          geometry_kernel_warnings: result.warnings ?? [],
        },
      },
      "Fillet",
    );
    pushCadCommandFeedback("FILLET", "applied", "FILLET applied as tangent chord draft geometry.");
  }, [cadFilletRadius, pushCadCommandFeedback, selectedCadObject, selectedVertex, updateCadObject]);

  const applySelectedCadDimension = useCallback(() => {
    if (!selectedCadObject || selectedCadMetrics === null) {
      pushCadCommandFeedback("DIM", "blocked", "DIM blocked: select one editable line/polyline draft object first.");
      return;
    }
    const defaultLabel =
      cadDimensionMode === "linear"
        ? `${selectedCadMetrics.firstLength.toFixed(1)} ft`
        : `${selectedCadMetrics.firstLength.toFixed(1)} ft @ ${selectedCadMetrics.firstAngle.toFixed(1)} deg`;
    updateCadObject(
      selectedCadObject,
      {
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_dimension_mode: cadDimensionMode,
          cad_dimension_label: cadDimensionLabelDraft.trim() || defaultLabel,
        },
      },
      "Dimension",
    );
    pushCadCommandFeedback("DIM", "applied", "DIM label stored on selected draft geometry for review.");
  }, [cadDimensionLabelDraft, cadDimensionMode, pushCadCommandFeedback, selectedCadMetrics, selectedCadObject, updateCadObject]);

  const applyCadProperties = useCallback(() => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("PROPERTIES", "blocked", "PROPERTIES blocked: select one editable draft object first.");
      return;
    }
    const safeName = cadPropertyDraft.name.trim() || selectedCadObject.label || "Draft object";
    const safeLayer = cadPropertyDraft.layer.trim().toUpperCase() || "C-DRAFT";
    const safeType = cadPropertyDraft.type.trim() || selectedCadObject.type || "custom";
    updateCadObject(
      selectedCadObject,
      {
        label: safeName,
        type: safeType as BuildingPlacement["type"],
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_layer: safeLayer,
          source_note: cadPropertyDraft.sourceNote.trim(),
          review_note: cadPropertyDraft.reviewNote.trim(),
          source: cadPropertyDraft.source.trim() || "manual_drawn",
          symbol_id: cadPropertyDraft.id.trim() || selectedCadObject.id,
          symbol_attributes: {
            id: cadPropertyDraft.id.trim() || selectedCadObject.id,
            label: safeName,
            elevation: cadPropertyDraft.elevation.trim(),
            material: cadPropertyDraft.material.trim(),
            size: cadPropertyDraft.size.trim(),
            source: cadPropertyDraft.source.trim() || "manual_drawn",
            review_note: cadPropertyDraft.reviewNote.trim(),
          },
          engineering_status: "draft_review_required",
          review_status: "engineer_review_required",
        },
      },
      "Properties",
    );
    pushCadCommandFeedback("PROPERTIES", "applied", "PROPERTIES applied to selected draft object.");
  }, [cadPropertyDraft, pushCadCommandFeedback, selectedCadObject, updateCadObject]);

  const insertCadSymbol = useCallback(() => {
    const x = clampValue(parseCadNumber(cadCoordinateDraft.x, lotWidth / 2), 0, lotWidth);
    const y = clampValue(parseCadNumber(cadCoordinateDraft.y, lotHeight / 2), 0, lotHeight);
    const symbolInstanceId = `${cadSymbolDraft}-${Date.now()}`;
    const labels: Record<CadSymbolKind, string> = {
      hydrant: "Hydrant",
      inlet: "Inlet",
      manhole: "Manhole",
      valve: "Valve",
      tree: "Tree",
      light: "Light",
      sign: "Sign",
      utility_marker: "Utility Marker",
      benchmark: "Benchmark",
      note_callout: "Note / Callout",
    };
    onCreateCustomGeometry({
      mode: "point",
      points: [[x, y]],
      label: labels[cadSymbolDraft],
      meta: {
        cad_symbol: cadSymbolDraft,
        symbol_id: symbolInstanceId,
        cad_layer: cadSymbolDraft === "tree" || cadSymbolDraft === "note_callout" ? "C-ANNO" : "C-SYMB",
        symbol_attributes: {
          id: symbolInstanceId,
          label: labels[cadSymbolDraft],
          elevation: "",
          material: "",
          size: "",
          source: "manual_drawn",
          review_note: "Inserted symbol remains draft/review-required.",
        },
        symbol_review_required: true,
        engineering_status: "draft_review_required",
        review_status: "engineer_review_required",
        source: "manual_drawn",
      },
    });
    setCadCommandStatus(`${labels[cadSymbolDraft]} symbol inserted for draft review.`);
    pushCadCommandFeedback("SYMBOL", "applied", `SYMBOL inserted: ${labels[cadSymbolDraft]} remains draft/review-required.`);
  }, [cadCoordinateDraft.x, cadCoordinateDraft.y, cadSymbolDraft, lotHeight, lotWidth, onCreateCustomGeometry, pushCadCommandFeedback]);

  const toggleCadLayerVisibility = useCallback((layer: string) => {
    setHiddenCadLayers((prev) => prev.includes(layer) ? prev.filter((item) => item !== layer) : [...prev, layer]);
  }, []);

  const runCadCommand = useCallback((commandOverride?: string) => {
    const raw = (commandOverride ?? cadCommandDraft).trim();
    if (!raw) {
      if (cadActiveCommand) {
        if (cadActiveCommand.kind === "offset") {
          if (typeof cadActiveCommand.distance === "number") {
            offsetSelectedCadObjectBy(String(cadActiveCommand.distance));
            setCadActiveCommand(null);
            setCadCommandDraft("");
            return;
          }
          pushCadCommandFeedback("OFFSET", "blocked", "OFFSET needs a distance like 10 before it can run.");
          return;
        }
        if (cadActiveCommand.kind === "modify") {
          if (typeof cadActiveCommand.amount === "number") {
            trimExtendSelectedCadObject(cadActiveCommand.command.toLowerCase() as "trim" | "extend", String(cadActiveCommand.amount));
            setCadActiveCommand(null);
            setCadCommandDraft("");
            return;
          }
          pushCadCommandFeedback(cadActiveCommand.command, "blocked", `${cadActiveCommand.command} needs an amount like 8 before it can run.`);
          return;
        }
        if (cadActiveCommand.kind === "transform") {
          if (!cadActiveCommand.value) {
            pushCadCommandFeedback(cadActiveCommand.command, "blocked", `${cadActiveCommand.command} needs ${cadActiveCommand.command === "MOVE" || cadActiveCommand.command === "COPY" ? "a vector like 20,0 or @75<45" : cadActiveCommand.command === "ROTATE" ? "an angle like 45" : "a factor like 1.2"}.`);
            return;
          }
          if (cadActiveCommand.command === "MOVE") {
            const vector = parseCadVectorToken(cadActiveCommand.value);
            if (vector) {
              moveSelectedCadObjectsByVector(vector[0], vector[1]);
            } else {
              transformSelectedCadObjects("move", cadActiveCommand.value);
            }
          } else if (cadActiveCommand.command === "COPY") {
            copySelectedCadObjectsByVector(parseCadVectorToken(cadActiveCommand.value) ?? undefined);
          } else {
            transformSelectedCadObjects(cadActiveCommand.command.toLowerCase() as "rotate" | "scale", cadActiveCommand.value);
          }
          setCadActiveCommand(null);
          setCadCommandDraft("");
          return;
        }
        if (draftPoints.length < cadActiveCommand.minPoints) {
          pushCadCommandFeedback(
            cadActiveCommand.command,
            "blocked",
            `${cadActiveCommand.command} finish blocked: needs at least ${cadActiveCommand.minPoints} point${cadActiveCommand.minPoints === 1 ? "" : "s"}; ${draftPoints.length} entered.`,
          );
          return;
        }
        createCadCommandGeometry(
          cadActiveCommand.command,
          cadActiveCommand.mode,
          draftPoints,
          {
            label: cadActiveCommand.command === "RECTANGLE" ? "Command Rectangle" : cadActiveCommand.command === "PLINE" ? "Command Polyline" : "Command Line",
            minPoints: cadActiveCommand.minPoints,
          },
        );
        setDraftPoints([]);
        setDraftPreviewPoint(null);
        setCadActiveCommand(null);
        setDrawMode("select");
        setCadCommandDraft("");
      }
      return;
    }
    const tokens = raw.split(/\s+/);
    const [commandRaw, ...args] = tokens;
    const command = commandRaw.toUpperCase();
    const commandKey = normalizeCadCommandKey(command);
    const pointArgs = getCadCommandPointArgs(args);
    const firstValue = getCadCommandFirstValue(args, cadTransformValue);
    const selectedRequested = hasSelectedCadCommandArg(args);
    const activeCanvasDrawMode =
      drawMode === "site" ||
      drawMode === "polyline" ||
      drawMode === "polygon" ||
      drawMode === "rect";
    if (activeCanvasDrawMode && !cadActiveCommand && !isKnownCadCommand(commandKey)) {
      const basePoint = draftPoints.length ? draftPoints[draftPoints.length - 1] : null;
      const typedPoint = parseCadPointToken(raw) ?? parseCadRelativePointToken(raw, basePoint);
      const typedDistance = Number(raw);
      let nextPoint: [number, number] | null = typedPoint;
      if (!nextPoint && Number.isFinite(typedDistance) && Math.abs(typedDistance) > 0.001) {
        if (!basePoint) {
        pushCadCommandFeedback("DRAW", "blocked", "DRAW distance input needs a first point. Pick a start point or type x,y first.");
          return;
        }
        const guidePoint = draftPreviewPoint ?? [basePoint[0] + 1, basePoint[1]] as [number, number];
        const dx = guidePoint[0] - basePoint[0];
        const dy = guidePoint[1] - basePoint[1];
        const length = Math.hypot(dx, dy);
        const unit = length > 0.001 ? { x: dx / length, y: dy / length } : { x: 1, y: 0 };
        nextPoint = [
          Math.round((basePoint[0] + unit.x * typedDistance) * 1000) / 1000,
          Math.round((basePoint[1] + unit.y * typedDistance) * 1000) / 1000,
        ];
      }
      if (!nextPoint) {
        pushCadCommandFeedback("DRAW", "blocked", "DRAW expected 100,50, @20,0, @75<45, or a distance like 75 while a draw tool is active.");
        return;
      }
      const nextPoints = [...draftPoints, nextPoint];
      setDraftPoints(nextPoints);
      setDraftPreviewPoint(null);
      setCadCommandDraft("");
      const minPoints = drawMode === "site" || drawMode === "polygon" ? 3 : 2;
      const readyText = nextPoints.length >= minPoints ? " Press Enter/Finish to complete." : "";
      pushCadCommandFeedback(
        "DRAW",
        "info",
        `DRAW accepted point ${nextPoints.length} at ${nextPoint[0].toFixed(1)},${nextPoint[1].toFixed(1)}.${readyText}`,
      );
      return;
    }

    if (commandKey === "SELECT") {
      const mode = (args[0] || "").trim().toUpperCase();
      if (mode === "NONE" || mode === "CLEAR") {
        setCadSelectionSet([]);
        onSelectObjects?.([]);
        onSelectBuilding(null);
        setSelectedVertex(null);
        pushCadCommandFeedback("SELECT", "info", "SELECT NONE cleared the draft object selection.");
        return;
      }
      const selectableObjects = buildingPlacements.filter((item) => item.type !== "site" && !item.locked);
      if (mode === "ALL") {
        const ids = selectableObjects.map((item) => item.id);
        setCadSelectionSet(ids);
        onSelectObjects?.(ids);
        onSelectBuilding(ids[0] ?? null);
        setSelectedVertex(null);
        pushCadCommandFeedback("SELECT", ids.length ? "applied" : "blocked", ids.length ? `SELECT ALL selected ${ids.length} editable draft object${ids.length === 1 ? "" : "s"}.` : "SELECT ALL found no editable draft objects.");
        return;
      }
      if (mode === "LAYER") {
        const layer = (args[1] || "").trim().toUpperCase();
        if (!layer) {
          pushCadCommandFeedback("SELECT", "blocked", "SELECT LAYER blocked: provide a layer like SELECT LAYER C-UTIL.");
          return;
        }
        const ids = selectableObjects
          .filter((item) => String(item.meta?.cad_layer || item.type || "").toUpperCase() === layer)
          .map((item) => item.id);
        setCadSelectionSet(ids);
        onSelectObjects?.(ids);
        onSelectBuilding(ids[0] ?? null);
        setSelectedVertex(null);
        pushCadCommandFeedback("SELECT", ids.length ? "applied" : "blocked", ids.length ? `SELECT LAYER ${layer} selected ${ids.length} editable draft object${ids.length === 1 ? "" : "s"}.` : `SELECT LAYER ${layer} found no editable draft objects.`);
        return;
      }
      pushCadCommandFeedback("SELECT", "info", `SELECT supports ALL, NONE, CLEAR, or LAYER. Current selection: ${selectedCadIds.length}.`);
      return;
    }

    if (cadActiveCommand && !isKnownCadCommand(commandKey)) {
      if (cadActiveCommand.kind === "offset") {
        const distance = Number(raw);
        if (!Number.isFinite(distance) || Math.abs(distance) < 0.001) {
          pushCadCommandFeedback("OFFSET", "blocked", "OFFSET expected a non-zero distance like 10.");
          return;
        }
        setCadOffsetDistance(String(distance));
        if (!selectedCadObject) {
          setCadActiveCommand({ command: "OFFSET", kind: "offset", distance });
          setCadCommandDraft("");
          pushCadCommandFeedback("OFFSET", "info", `OFFSET distance set to ${distance}. Select one draft object, then run OFFSET or press Run empty.`);
          return;
        }
        offsetSelectedCadObjectBy(String(distance));
        setCadActiveCommand(null);
        setCadCommandDraft("");
        return;
      }
      if (cadActiveCommand.kind === "modify") {
        const amount = Number(raw);
        if (!Number.isFinite(amount) || Math.abs(amount) < 0.001) {
          pushCadCommandFeedback(cadActiveCommand.command, "blocked", `${cadActiveCommand.command} expected a non-zero amount like 8.`);
          return;
        }
        setCadTransformValue(String(amount));
        if (!selectedCadObject) {
          setCadActiveCommand({ command: cadActiveCommand.command, kind: "modify", amount });
          setCadCommandDraft("");
          pushCadCommandFeedback(cadActiveCommand.command, "info", `${cadActiveCommand.command} amount set to ${amount}. Select one line/polyline draft object, then run ${cadActiveCommand.command} or press Run empty.`);
          return;
        }
        trimExtendSelectedCadObject(cadActiveCommand.command.toLowerCase() as "trim" | "extend", String(amount));
        setCadActiveCommand(null);
        setCadCommandDraft("");
        return;
      }
      if (cadActiveCommand.kind === "transform") {
        setCadActiveCommand({ command: cadActiveCommand.command, kind: "transform", value: raw });
        setCadCommandDraft("");
        if (!selectedCadObject && cadActiveCommand.command === "COPY") {
          pushCadCommandFeedback("COPY", "info", `COPY vector set to ${raw}. Select one editable draft object, then run COPY or press Run empty.`);
          return;
        }
        if (!selectedCadIds.length && cadActiveCommand.command !== "COPY") {
          pushCadCommandFeedback(cadActiveCommand.command, "info", `${cadActiveCommand.command} value set to ${raw}. Select one or more editable draft objects, then run ${cadActiveCommand.command} or press Run empty.`);
          return;
        }
        if (cadActiveCommand.command === "MOVE") {
          const vector = parseCadVectorToken(raw);
          if (vector) {
            moveSelectedCadObjectsByVector(vector[0], vector[1]);
          } else {
            transformSelectedCadObjects("move", raw);
          }
        } else if (cadActiveCommand.command === "COPY") {
          copySelectedCadObjectsByVector(parseCadVectorToken(raw) ?? undefined);
        } else {
          transformSelectedCadObjects(cadActiveCommand.command.toLowerCase() as "rotate" | "scale", raw);
        }
        setCadActiveCommand(null);
        return;
      }
      const activePoints = parseCadPointTokens(tokens);
      if (!activePoints.length) {
        pushCadCommandFeedback(
          cadActiveCommand.command,
          "blocked",
          `${cadActiveCommand.command} expected a coordinate like 100,50, or press Enter to finish.`,
        );
        return;
      }
      const nextPoints = [...draftPoints, ...activePoints];
      if (cadActiveCommand.mode === "rect" && nextPoints.length >= 2) {
        createCadCommandGeometry("RECTANGLE", "rect", nextPoints.slice(0, 2), { label: "Command Rectangle", minPoints: 2 });
        setDraftPoints([]);
        setDraftPreviewPoint(null);
        setCadActiveCommand(null);
        setDrawMode("select");
        setCadCommandDraft("");
        return;
      }
      setDraftPoints(nextPoints);
      setCadCommandDraft("");
      pushCadCommandFeedback(
        cadActiveCommand.command,
        "info",
        `${cadActiveCommand.command} accepted ${nextPoints.length} point${nextPoints.length === 1 ? "" : "s"}. Type next point or press Enter/Run with an empty command to finish.`,
      );
      return;
    }

    if (cadActiveCommand && (commandKey === "FINISH" || commandKey === "DONE")) {
      if (cadActiveCommand.kind === "offset") {
        if (typeof cadActiveCommand.distance !== "number") {
          pushCadCommandFeedback("OFFSET", "blocked", "OFFSET needs a distance like 10 before it can run.");
          return;
        }
        offsetSelectedCadObjectBy(String(cadActiveCommand.distance));
        setCadActiveCommand(null);
        setCadCommandDraft("");
        return;
      }
      if (cadActiveCommand.kind === "modify") {
        if (typeof cadActiveCommand.amount !== "number") {
          pushCadCommandFeedback(cadActiveCommand.command, "blocked", `${cadActiveCommand.command} needs an amount like 8 before it can run.`);
          return;
        }
        trimExtendSelectedCadObject(cadActiveCommand.command.toLowerCase() as "trim" | "extend", String(cadActiveCommand.amount));
        setCadActiveCommand(null);
        setCadCommandDraft("");
        return;
      }
      if (cadActiveCommand.kind === "transform") {
        if (!cadActiveCommand.value) {
          pushCadCommandFeedback(cadActiveCommand.command, "blocked", `${cadActiveCommand.command} needs ${cadActiveCommand.command === "MOVE" || cadActiveCommand.command === "COPY" ? "a vector like 20,0 or @75<45" : cadActiveCommand.command === "ROTATE" ? "an angle like 45" : "a factor like 1.2"}.`);
          return;
        }
        if (cadActiveCommand.command === "MOVE") {
          const vector = parseCadVectorToken(cadActiveCommand.value);
          if (vector) {
            moveSelectedCadObjectsByVector(vector[0], vector[1]);
          } else {
            transformSelectedCadObjects("move", cadActiveCommand.value);
          }
        } else if (cadActiveCommand.command === "COPY") {
          copySelectedCadObjectsByVector(parseCadVectorToken(cadActiveCommand.value) ?? undefined);
        } else {
          transformSelectedCadObjects(cadActiveCommand.command.toLowerCase() as "rotate" | "scale", cadActiveCommand.value);
        }
        setCadActiveCommand(null);
        setCadCommandDraft("");
        return;
      }
      if (draftPoints.length < cadActiveCommand.minPoints) {
        pushCadCommandFeedback(
          cadActiveCommand.command,
          "blocked",
          `${cadActiveCommand.command} finish blocked: needs at least ${cadActiveCommand.minPoints} point${cadActiveCommand.minPoints === 1 ? "" : "s"}; ${draftPoints.length} entered.`,
        );
        return;
      }
      createCadCommandGeometry(
        cadActiveCommand.command,
        cadActiveCommand.mode,
        draftPoints,
        {
          label: cadActiveCommand.command === "RECTANGLE" ? "Command Rectangle" : cadActiveCommand.command === "PLINE" ? "Command Polyline" : "Command Line",
          minPoints: cadActiveCommand.minPoints,
        },
      );
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setCadActiveCommand(null);
      setDrawMode("select");
      setCadCommandDraft("");
      return;
    }

    if (cadActiveCommand && (commandKey === "CANCEL" || commandKey === "ESC")) {
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setCadActiveCommand(null);
      setDrawMode("select");
      pushCadCommandFeedback(cadActiveCommand.command, "info", `${cadActiveCommand.command} cancelled.`);
      setCadCommandDraft("");
      return;
    }

    if (commandKey === "LINE") {
      if (pointArgs.length >= 2) {
        createCadCommandGeometry("LINE", "polyline", pointArgs, { label: "Command Line", minPoints: 2 });
      } else {
        setDraftPoints([]);
        setDraftPreviewPoint(null);
        setCadActiveCommand({ command: "LINE", kind: "draw", mode: "polyline", minPoints: 2 });
        setDrawMode("polyline");
        onSetPreviewInteraction("edit");
        pushCadCommandFeedback("LINE", "info", "LINE active. Type the first point like 0,0, then the next point like 100,0. Press Enter/Run empty to finish.");
      }
      return;
    }
    if (commandKey === "PLINE") {
      if (pointArgs.length >= 2) {
        createCadCommandGeometry("PLINE", "polyline", pointArgs, { label: "Command Polyline", minPoints: 2 });
      } else {
        setDraftPoints([]);
        setDraftPreviewPoint(null);
        setCadActiveCommand({ command: "PLINE", kind: "draw", mode: "polyline", minPoints: 2 });
        setDrawMode("polyline");
        onSetPreviewInteraction("edit");
        pushCadCommandFeedback("PLINE", "info", "PLINE active. Type points one at a time, then press Enter/Run empty to finish.");
      }
      return;
    }
    if (commandKey === "RECTANGLE" || commandKey === "BOX") {
      if (pointArgs.length >= 2) {
        createCadCommandGeometry("RECTANGLE", "rect", pointArgs.slice(0, 2), { label: "Command Rectangle", minPoints: 2 });
      } else {
        setDraftPoints([]);
        setDraftPreviewPoint(null);
        setCadActiveCommand({ command: "RECTANGLE", kind: "draw", mode: "rect", minPoints: 2 });
        setDrawMode("rect");
        onSetPreviewInteraction("edit");
        pushCadCommandFeedback("RECTANGLE", "info", "RECTANGLE active. Type first corner like 0,0, then opposite corner like 100,60.");
      }
      return;
    }
    if (commandKey === "CIRCLE") {
      const radius = parseCadNumber(args[1] ?? args[0] ?? "", NaN);
      const center = pointArgs[0];
      if (!center || !Number.isFinite(radius) || radius <= 0) {
        pushCadCommandFeedback("CIRCLE", "blocked", "CIRCLE blocked: use CIRCLE centerX,centerY radius.");
        return;
      }
      const points = Array.from({ length: 32 }, (_, index) => {
        const radians = (index / 32) * Math.PI * 2;
        return [center[0] + Math.cos(radians) * radius, center[1] + Math.sin(radians) * radius] as [number, number];
      });
      createCadCommandGeometry("CIRCLE", "polygon", points, {
        label: "Command Circle",
        meta: { cad_curve_storage: "32_segment_chord_polygon", cad_radius_ft: radius },
        minPoints: 3,
      });
      return;
    }
    if (commandKey === "ARC") {
      const center = pointArgs[0];
      const radius = parseCadNumber(args[1] ?? "", NaN);
      const startDeg = parseCadNumber(args[2] ?? "", NaN);
      const endDeg = parseCadNumber(args[3] ?? "", NaN);
      if (!center || !Number.isFinite(radius) || radius <= 0 || !Number.isFinite(startDeg) || !Number.isFinite(endDeg)) {
        pushCadCommandFeedback("ARC", "blocked", "ARC blocked: use ARC centerX,centerY radius startDeg endDeg.");
        return;
      }
      const sweep = endDeg >= startDeg ? endDeg - startDeg : endDeg + 360 - startDeg;
      const steps = Math.max(4, Math.ceil(sweep / 12));
      const points = Array.from({ length: steps + 1 }, (_, index) => {
        const radians = ((startDeg + (sweep * index) / steps) * Math.PI) / 180;
        return [center[0] + Math.cos(radians) * radius, center[1] + Math.sin(radians) * radius] as [number, number];
      });
      createCadCommandGeometry("ARC", "polyline", points, {
        label: "Command Arc",
        meta: { cad_curve_storage: "sampled_chord_polyline", cad_radius_ft: radius, cad_start_deg: startDeg, cad_end_deg: endDeg },
        minPoints: 2,
      });
      return;
    }
    if (commandKey === "ARRAY") {
      const rows = parseCadNumber(args[0] ?? "", 0);
      const columns = parseCadNumber(args[1] ?? "", 0);
      const spacing = parseCadPointToken(args[2] ?? "") ?? [20, 20];
      if (!Number.isFinite(rows) || !Number.isFinite(columns) || rows < 1 || columns < 1) {
        pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: use ARRAY rows columns dx,dy, for example ARRAY 2 3 20,15.");
        return;
      }
      arraySelectedCadObject(rows, columns, spacing);
      return;
    }
    if (commandKey === "ALIGN") {
      const modeArg = (args[0] || "LEFT").trim().toUpperCase();
      const modeAliases: Record<string, "LEFT" | "RIGHT" | "CENTER" | "TOP" | "BOTTOM" | "MIDDLE" | "X" | "Y"> = {
        L: "LEFT",
        LEFT: "LEFT",
        R: "RIGHT",
        RIGHT: "RIGHT",
        C: "CENTER",
        CENTER: "CENTER",
        CENTRE: "CENTER",
        X: "X",
        T: "TOP",
        TOP: "TOP",
        B: "BOTTOM",
        BOTTOM: "BOTTOM",
        M: "MIDDLE",
        MID: "MIDDLE",
        MIDDLE: "MIDDLE",
        Y: "Y",
      };
      const mode = modeAliases[modeArg];
      if (!mode) {
        pushCadCommandFeedback("ALIGN", "blocked", "ALIGN blocked: use ALIGN LEFT, RIGHT, CENTER, TOP, BOTTOM, or MIDDLE.");
        return;
      }
      alignOrDistributeSelectedCadObjects("ALIGN", mode);
      return;
    }
    if (commandKey === "DISTRIBUTE") {
      const modeArg = (args[0] || "X").trim().toUpperCase();
      const axis = ["Y", "V", "VERTICAL"].includes(modeArg) ? "Y" : "X";
      alignOrDistributeSelectedCadObjects("DISTRIBUTE", axis);
      return;
    }
    if (commandKey === "DIST" || commandKey === "MEASURE") {
      if (pointArgs.length >= 2) {
        const [a, b] = pointArgs;
        const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
        const angle = ((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI + 360) % 360;
        pushCadCommandFeedback("DIST", "info", `DIST ${length.toFixed(2)} ft at ${angle.toFixed(1)} deg between typed points.`);
        return;
      }
      const fallbackCadObject = selectedCadObject ?? [...visibleCadObjects]
        .reverse()
        .find((item) => item.type !== "site" && getObjectGeometryPoints(item).length >= 2) ?? null;
      const fallbackPoints = fallbackCadObject ? getObjectGeometryPoints(fallbackCadObject) : [];
      const fallbackSegments = fallbackCadObject && fallbackPoints.length >= 2
        ? fallbackPoints.map((point, index) => {
            if (index === fallbackPoints.length - 1 && fallbackCadObject.geometryType === "polyline") return null;
            const next = index === fallbackPoints.length - 1 ? fallbackPoints[0] : fallbackPoints[index + 1];
            return {
              length: Math.hypot(next[0] - point[0], next[1] - point[1]),
              angle: ((Math.atan2(next[1] - point[1], next[0] - point[0]) * 180) / Math.PI + 360) % 360,
            };
          }).filter(Boolean) as Array<{ length: number; angle: number }>
        : [];
      const metrics = selectedCadMetrics ?? (fallbackSegments.length
        ? {
            segmentCount: fallbackSegments.length,
            totalLength: fallbackSegments.reduce((sum, segment) => sum + segment.length, 0),
            firstAngle: fallbackSegments[0]?.angle ?? 0,
          }
        : null);
      if (!metrics || !fallbackCadObject) {
        pushCadCommandFeedback("DIST", "blocked", "DIST blocked: select a draft line/polyline/area or use DIST x1,y1 x2,y2.");
        return;
      }
      pushCadCommandFeedback(
        "DIST",
        "info",
        `DIST selected ${fallbackCadObject.label || "object"}: ${metrics.totalLength.toFixed(2)} ft total, ${metrics.segmentCount} segment${metrics.segmentCount === 1 ? "" : "s"}, first angle ${metrics.firstAngle.toFixed(1)} deg.`,
      );
      return;
    }
    if (commandKey === "MOVE") {
      const vectorArg = args.find((arg) => arg.toLowerCase() !== "selected");
      const vector = vectorArg ? parseCadVectorToken(vectorArg) : null;
      if (!args.length) {
        setCadActiveCommand({ command: "MOVE", kind: "transform" });
        setCadCommandDraft("");
        pushCadCommandFeedback("MOVE", "info", "MOVE active. Type a vector like 20,0, @20,0, @75<45, or a distance like 5 for a diagonal move.");
      } else if (selectedRequested && vector) {
        moveSelectedCadObjectsByVector(vector[0], vector[1]);
      } else {
        setCadTransformValue(firstValue);
        transformSelectedCadObjects("move", firstValue);
      }
      return;
    }
    if (commandKey === "ROTATE" || commandKey === "SCALE") {
      if (!args.length) {
        setCadActiveCommand({ command: commandKey as "ROTATE" | "SCALE", kind: "transform" });
        setCadCommandDraft("");
        pushCadCommandFeedback(commandKey, "info", `${commandKey} active. Type ${commandKey === "ROTATE" ? "an angle like 45" : "a factor like 1.2"}.`);
      } else {
        setCadTransformValue(firstValue);
        transformSelectedCadObjects(commandKey.toLowerCase() as "rotate" | "scale", firstValue);
      }
      return;
    }
    if (commandKey === "COPY") {
      if (!args.length) {
        setCadActiveCommand({ command: "COPY", kind: "transform" });
        setCadCommandDraft("");
        pushCadCommandFeedback("COPY", "info", "COPY active. Type a vector like 10,10, @20,0, @75<45, or run empty to use the default offset.");
      } else {
        const vectorArg = args.find((arg) => arg.toLowerCase() !== "selected");
        copySelectedCadObjectsByVector((vectorArg ? parseCadVectorToken(vectorArg) : null) ?? [10, 10]);
      }
      return;
    }
    if (commandKey === "MIRROR" || commandKey === "FLIP") {
      const axisArg = (args[0] || "").trim().toLowerCase();
      const horizontal = ["h", "x", "horizontal"].includes(axisArg);
      const vertical = ["v", "y", "vertical"].includes(axisArg);
      if (!horizontal && !vertical) {
        pushCadCommandFeedback(commandKey, "blocked", `${commandKey} blocked: use ${commandKey} H or ${commandKey} V after selecting editable draft objects.`);
        return;
      }
      transformSelectedCadObjects(horizontal ? "flip_horizontal" : "flip_vertical", "0");
      return;
    }
    if (commandKey === "DELETE" || commandKey === "ERASE") {
      if (!selectedDeletableObject) {
        pushCadCommandFeedback("DELETE", "blocked", "DELETE blocked: select one unlocked draft object first.");
        return;
      }
      onRemoveBuilding(selectedDeletableObject.id);
      pushCadCommandFeedback("DELETE", "applied", "DELETE removed the selected draft object. Downstream systems remain review-required until rerun.");
      return;
    }
    if (commandKey === "OFFSET") {
      if (args.length) {
        setCadOffsetDistance(firstValue);
        offsetSelectedCadObjectBy(firstValue);
        setCadActiveCommand(null);
      } else {
        setCadActiveCommand({ command: "OFFSET", kind: "offset" });
        setCadCommandDraft("");
        pushCadCommandFeedback("OFFSET", "info", "OFFSET active. Type a non-zero distance like 10. Select one draft object first for immediate offset.");
      }
      return;
    }
    if (commandKey === "TRIM" || commandKey === "EXTEND") {
      if (args.length) {
        setCadTransformValue(firstValue);
        trimExtendSelectedCadObject(commandKey.toLowerCase() as "trim" | "extend", firstValue);
        setCadActiveCommand(null);
      } else {
        setCadActiveCommand({ command: commandKey as "TRIM" | "EXTEND", kind: "modify" });
        setCadCommandDraft("");
        pushCadCommandFeedback(commandKey, "info", `${commandKey} active. Type an amount like 8. Select one line/polyline draft object first for immediate ${commandKey.toLowerCase()}.`);
      }
      return;
    }
    if (commandKey === "FILLET") {
      setCadFilletRadius(firstValue);
      filletSelectedCadObject();
      return;
    }
    if (commandKey === "JOIN") {
      joinSelectedCadObjects();
      return;
    }
    if (commandKey === "SPLIT" || commandKey === "BREAK") {
      splitSelectedJoinedObject();
      return;
    }
    if (commandKey === "CLOSE") {
      changeSelectedPolylineState("close");
      return;
    }
    if (commandKey === "OPEN") {
      changeSelectedPolylineState("open");
      return;
    }
    if (commandKey === "REVERSE") {
      changeSelectedPolylineState("reverse");
      return;
    }
    if (commandKey === "HATCH") {
      toggleSelectedCadHatch();
      return;
    }
    if (commandKey === "DIM") {
      applySelectedCadDimension();
      return;
    }
    if (commandKey === "TEXT") {
      const point = pointArgs[0];
      const text = args.filter((arg) => !parseCadPointToken(arg)).join(" ").trim();
      if (!point || !text) {
        pushCadCommandFeedback("TEXT", "blocked", "TEXT blocked: use TEXT x,y note text.");
        return;
      }
      createCadCommandGeometry("TEXT", "point", [point], { label: text.slice(0, 48), meta: { cad_text: text, cad_layer: "C-ANNO" }, minPoints: 1 });
      return;
    }
    if (commandKey === "LAYER") {
      const layerAction = (args[0] || "").trim().toUpperCase();
      const layer = (args[1] || "").trim().toUpperCase();
      if (layerAction === "ALL" || layerAction === "SHOWALL") {
        setHiddenCadLayers([]);
        pushCadCommandFeedback("LAYER", "applied", "LAYER ALL showed every draft layer.");
        return;
      }
      if (["HIDE", "OFF", "SHOW", "ON", "ONLY", "ISOLATE"].includes(layerAction)) {
        if (!layer) {
          pushCadCommandFeedback("LAYER", "blocked", `LAYER ${layerAction} blocked: provide a layer name like LAYER ${layerAction} C-UTIL.`);
          return;
        }
        if (layerAction === "HIDE" || layerAction === "OFF") {
          setHiddenCadLayers((prev) => Array.from(new Set([...prev, layer])));
          pushCadCommandFeedback("LAYER", "applied", `LAYER ${layerAction} hid ${layer}.`);
          return;
        }
        if (layerAction === "SHOW" || layerAction === "ON") {
          setHiddenCadLayers((prev) => prev.filter((item) => item !== layer));
          pushCadCommandFeedback("LAYER", "applied", `LAYER ${layerAction} showed ${layer}.`);
          return;
        }
        setHiddenCadLayers(cadLayerOptions.filter((item) => item !== layer));
        pushCadCommandFeedback("LAYER", "applied", `LAYER ${layerAction} isolated ${layer}.`);
        return;
      }
      const targetLayer = layerAction;
      if (!targetLayer) {
        pushCadCommandFeedback("LAYER", "blocked", "LAYER blocked: provide a layer name like LAYER C-UTIL.");
        return;
      }
      setCadLayerDraft(targetLayer);
      if (selectedCadIds.length) {
        selectedCadIds.forEach((id) => {
          const target = buildingPlacements.find((item) => item.id === id);
          if (!target || target.locked || target.type === "site") return;
          updateCadObject(target, { meta: { ...(target.meta ?? {}), cad_layer: targetLayer } }, "Layer");
        });
        pushCadCommandFeedback("LAYER", "applied", `LAYER applied ${targetLayer} to selected draft object(s).`);
      } else {
        pushCadCommandFeedback("LAYER", "info", `Current draft layer set to ${targetLayer}. Select objects to apply it.`);
      }
      return;
    }
    if (commandKey === "SNAP") {
      const arg = (args[0] || "").toLowerCase();
      const next = arg === "off" ? false : arg === "on" ? true : !cadSnapEnabled;
      setCadSnapEnabled(next);
      pushCadCommandFeedback("SNAP", "info", `SNAP ${next ? "on" : "off"}.`);
      return;
    }
    if (commandKey === "ORTHO") {
      const arg = (args[0] || "").toLowerCase();
      const next = arg === "off" ? false : arg === "on" ? true : !cadOrthoEnabled;
      setCadOrthoEnabled(next);
      pushCadCommandFeedback("ORTHO", "info", `ORTHO ${next ? "on" : "off"}.`);
      return;
    }
    pushCadCommandFeedback(commandKey, "blocked", `Unknown command: ${commandKey}. Try LINE/L, PLINE/PL, RECTANGLE/REC, CIRCLE/C, ARC/A, ARRAY/AR, ALIGN/AL, DISTRIBUTE, DIST/DI, OFFSET/O, TRIM/TR, EXTEND/EX, FILLET/F, JOIN/J, SPLIT/BR, CLOSE/CL, OPEN, REVERSE/REV, HATCH/H, MIRROR/MI, MOVE/M, ROTATE/RO, SCALE/SC, COPY/CO, DELETE/E, DIM/D, TEXT/T, LAYER/LA, SELECT, SNAP, or ORTHO.`);
  }, [
    alignOrDistributeSelectedCadObjects,
    applySelectedCadDimension,
    arraySelectedCadObject,
    buildingPlacements,
    cadActiveCommand,
    cadCommandDraft,
    cadLayerOptions,
    changeSelectedPolylineState,
    cadOrthoEnabled,
    cadSnapEnabled,
    cadTransformValue,
    copySelectedCadObjectsByVector,
    createCadCommandGeometry,
    draftPreviewPoint,
    draftPoints,
    drawMode,
    filletSelectedCadObject,
    getObjectGeometryPoints,
    joinSelectedCadObjects,
    moveSelectedCadObjectsByVector,
    offsetSelectedCadObjectBy,
    onSelectBuilding,
    onSelectObjects,
    onSetPreviewInteraction,
    onRemoveBuilding,
    pushCadCommandFeedback,
    selectedCadIds,
    selectedCadMetrics,
    selectedCadObject,
    selectedDeletableObject,
    splitSelectedJoinedObject,
    toggleSelectedCadHatch,
    transformSelectedCadObjects,
    trimExtendSelectedCadObject,
    updateCadObject,
    visibleCadObjects,
  ]);

  const lastCadToolRequestIdRef = useRef(0);

  useEffect(() => {
    if (!cadToolRequest || cadToolRequest.id === lastCadToolRequestIdRef.current) return;
    lastCadToolRequestIdRef.current = cadToolRequest.id;
    onSetPreviewMode("2d");
    onSetPreviewInteraction("edit");

    const activateDrawMode = (mode: DrawMode, label: string, autoFinishPointCount: number | null = null) => {
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setDrawAutoFinishPointCount(autoFinishPointCount);
      setCadActiveCommand(null);
      onSelectBuilding(null);
      setManagedObjectId(null);
      setHoveredObjectId(null);
      setSelectedVertex(null);
      setCadSelectionSet([]);
      setDrawMode(mode);
      pushCadCommandFeedback(
        label,
        "info",
        autoFinishPointCount
          ? `${label} tool active. Pick ${autoFinishPointCount} point${autoFinishPointCount === 1 ? "" : "s"} on the canvas to create the draft object.`
          : `${label} tool active. Pick points on the canvas, then Finish when shown.`,
      );
    };

    switch (cadToolRequest.tool) {
      case "select":
        setDrawMode("select");
        setDraftPoints([]);
        setDraftPreviewPoint(null);
        setDrawAutoFinishPointCount(null);
        pushCadCommandFeedback("SELECT", "info", "SELECT tool active. Click an object on the canvas or choose one from the object list.");
        break;
      case "line":
        activateDrawMode("polyline", "LINE", 2);
        break;
      case "polyline":
        activateDrawMode("polyline", "PLINE");
        break;
      case "area":
        activateDrawMode("polygon", "AREA");
        break;
      case "box":
        activateDrawMode("rect", "RECTANGLE");
        break;
      case "point":
        activateDrawMode("point", "POINT");
        break;
      case "circle":
        setCadCommandDraft(`CIRCLE ${(lotWidth / 2).toFixed(0)},${(lotHeight / 2).toFixed(0)} 25`);
        pushCadCommandFeedback("CIRCLE", "info", "CIRCLE command loaded. Adjust center/radius in the command line, then press Run.");
        break;
      case "arc":
        setCadCommandDraft(`ARC ${(lotWidth / 2).toFixed(0)},${(lotHeight / 2).toFixed(0)} 40 0 90`);
        pushCadCommandFeedback("ARC", "info", "ARC command loaded. Adjust center/radius/start/end in the command line, then press Run.");
        break;
      case "text":
        setCadCommandDraft(`TEXT ${(lotWidth / 2).toFixed(0)},${(lotHeight / 2).toFixed(0)} note`);
        pushCadCommandFeedback("TEXT", "info", "TEXT command loaded. Edit the point and note text, then press Run.");
        break;
      case "move":
        transformSelectedCadObjects("move");
        break;
      case "copy":
        setCadCommandDraft("COPY selected 10,10");
        pushCadCommandFeedback("COPY", "info", "COPY command loaded. Select an object, adjust the vector if needed, then press Run.");
        break;
      case "rotate":
        transformSelectedCadObjects("rotate");
        break;
      case "scale":
        transformSelectedCadObjects("scale");
        break;
      case "offset":
        offsetSelectedCadObjectBy(cadOffsetDistance);
        break;
      case "trim":
        trimExtendSelectedCadObject("trim");
        break;
      case "extend":
        trimExtendSelectedCadObject("extend");
        break;
      case "fillet":
        filletSelectedCadObject();
        break;
      case "join":
        joinSelectedCadObjects();
        break;
      case "split":
        splitSelectedJoinedObject();
        break;
      case "close":
        changeSelectedPolylineState("close");
        break;
      case "open":
        changeSelectedPolylineState("open");
        break;
      case "reverse":
        changeSelectedPolylineState("reverse");
        break;
      case "hatch":
        toggleSelectedCadHatch();
        break;
      case "delete":
        if (selectedDeletableObject) {
          onRemoveBuilding(selectedDeletableObject.id);
          pushCadCommandFeedback("DELETE", "applied", "DELETE removed the selected draft object.");
        } else {
          pushCadCommandFeedback("DELETE", "blocked", "DELETE blocked: select one unlocked draft object first.");
        }
        break;
      case "dimension":
        applySelectedCadDimension();
        break;
      case "measure":
        runCadCommand("DIST");
        break;
      case "symbol":
        insertCadSymbol();
        break;
      case "layer":
        applySelectedCadLayer();
        break;
      case "properties":
        applyCadProperties();
        break;
      case "snap":
        setCadSnapEnabled((value) => {
          pushCadCommandFeedback("SNAP", "info", `SNAP ${!value ? "on" : "off"}.`);
          return !value;
        });
        break;
      case "ortho":
        setCadOrthoEnabled((value) => {
          pushCadCommandFeedback("ORTHO", "info", `ORTHO ${!value ? "on" : "off"}.`);
          return !value;
        });
        break;
      case "undo":
        undoCadCommand();
        break;
      case "redo":
        redoCadCommand();
        break;
      case "command":
        if (cadToolRequest.commandText?.trim()) {
          setCadCommandDraft(cadToolRequest.commandText);
          window.requestAnimationFrame(() => runCadCommand(cadToolRequest.commandText));
        } else {
          setCadCommandDraft((value) => value || "LINE 0,0 100,0");
          pushCadCommandFeedback("COMMAND", "info", "Command line focused. Type a command or run the loaded example.");
        }
        break;
      default:
        break;
    }
  }, [
    applyCadProperties,
    applySelectedCadDimension,
    applySelectedCadLayer,
    cadOffsetDistance,
    cadToolRequest,
    changeSelectedPolylineState,
    filletSelectedCadObject,
    insertCadSymbol,
    joinSelectedCadObjects,
    lotHeight,
    lotWidth,
    offsetSelectedCadObjectBy,
    onRemoveBuilding,
    onSelectBuilding,
    onSetPreviewInteraction,
    onSetPreviewMode,
    pushCadCommandFeedback,
    redoCadCommand,
    runCadCommand,
    selectedDeletableObject,
    splitSelectedJoinedObject,
    toggleSelectedCadHatch,
    transformSelectedCadObjects,
    trimExtendSelectedCadObject,
    undoCadCommand,
  ]);

  useEffect(() => {
    const handleCadShortcuts = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("input, textarea, select, [contenteditable='true']")) return;
      const key = event.key.toLowerCase();
      const command = event.metaKey || event.ctrlKey;
      if (command && key === "z") {
        event.preventDefault();
        if (event.shiftKey) redoCadCommand();
        else undoCadCommand();
        return;
      }
      if (command && key === "y") {
        event.preventDefault();
        redoCadCommand();
        return;
      }
      if (["arrowup", "arrowdown", "arrowleft", "arrowright"].includes(key)) {
        if (!selectedCadIds.length) return;
        event.preventDefault();
        const step = event.altKey ? 1 : event.shiftKey ? 25 : 5;
        const dx = key === "arrowleft" ? -step : key === "arrowright" ? step : 0;
        const dy = key === "arrowup" ? -step : key === "arrowdown" ? step : 0;
        moveSelectedCadObjectsByVector(dx, dy);
        return;
      }
      if (key === "v") {
        event.preventDefault();
        setDrawMode("select");
        return;
      }
      if (key === "l") {
        event.preventDefault();
        if (canDrawObjects) {
          setDraftPoints([]);
          setDraftPreviewPoint(null);
          setDrawMode("polyline");
          onSetPreviewInteraction("edit");
        }
        return;
      }
      if (key === "a") {
        event.preventDefault();
        if (canDrawObjects) {
          setDraftPoints([]);
          setDraftPreviewPoint(null);
          setDrawMode("polygon");
          onSetPreviewInteraction("edit");
        }
        return;
      }
      if (key === "o") {
        event.preventDefault();
        setCadOrthoEnabled((value) => !value);
        return;
      }
      if (key === "s") {
        event.preventDefault();
        setCadSnapEnabled((value) => !value);
        return;
      }
      if (key === "m") {
        event.preventDefault();
        transformSelectedCadObjects("move");
        return;
      }
      if (key === "r") {
        event.preventDefault();
        transformSelectedCadObjects("rotate");
      }
    };
    window.addEventListener("keydown", handleCadShortcuts);
    return () => window.removeEventListener("keydown", handleCadShortcuts);
  }, [
    canDrawObjects,
    moveSelectedCadObjectsByVector,
    onSetPreviewInteraction,
    redoCadCommand,
    selectedCadIds.length,
    transformSelectedCadObjects,
    undoCadCommand,
  ]);

  const clearDraftGeometry = useCallback(() => {
    draftPointsRef.current = [];
    setDraftPoints([]);
    setDraftPreviewPoint(null);
    lastDraftPreviewPointRef.current = null;
    setCadActiveCommand(null);
  }, []);

  useEffect(() => {
    draftPointsRef.current = draftPoints;
  }, [draftPoints]);

  useEffect(() => {
    if (draftPreviewPoint) {
      lastDraftPreviewPointRef.current = draftPreviewPoint;
    }
  }, [draftPreviewPoint]);

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
    if (drawMode !== "site" && drawMode !== "polyline" && drawMode !== "polygon" && drawMode !== "rect") {
      pushCadCommandFeedback("FINISH", "blocked", "FINISH blocked: start Add Line, Add Area, Add Box, Add Point, or Draw Site Boundary first.");
      return;
    }
    const cursorFinishPoint = cursorSitePoint ? ([cursorSitePoint.x, cursorSitePoint.y] as [number, number]) : null;
    const rectFinishPreviewPoint = draftPreviewPoint ?? lastDraftPreviewPointRef.current ?? cursorFinishPoint;
    const currentDraftPoints = draftPointsRef.current.length ? draftPointsRef.current : draftPoints;
    const effectivePoints = resolveDraftGeometryEffectivePoints(drawMode, currentDraftPoints, rectFinishPreviewPoint);
    const minPoints = getDraftGeometryMinPointCount(drawMode);
    if (effectivePoints.length < minPoints) {
      pushCadCommandFeedback("FINISH", "blocked", buildDraftGeometryFinishBlockedMessage(drawMode, effectivePoints.length));
      return;
    }
    if (drawMode === "site" || drawMode === "polygon") {
      const cleaned = cleanupPolygon(effectivePoints, 0.5);
      if (!cleaned.ok) {
        setCadCommandStatus(`POLYGON blocked: ${cleaned.reason}`);
        pushCadCommandFeedback(
          drawMode === "site" ? "SITE" : "AREA",
          "blocked",
          `${drawMode === "site" ? "SITE" : "AREA"} blocked: ${cleaned.reason}`,
        );
        return;
      }
      const validation = validatePolygon(cleaned.value);
      if (!validation.ok) {
        setCadCommandStatus(`POLYGON blocked: ${validation.issues.join(", ")}`);
        pushCadCommandFeedback(
          drawMode === "site" ? "SITE" : "AREA",
          "blocked",
          `${drawMode === "site" ? "SITE" : "AREA"} blocked: ${validation.issues.join(", ")}`,
        );
        return;
      }
      if (drawMode === "site") {
        onCreateSiteBoundary?.({ points: cleaned.value });
      } else {
        onCreateCustomGeometry({
          mode: drawMode,
          points: cleaned.value,
          meta: {
            geometry_cleanup: "duplicate_vertices_removed_and_gap_closed_within_tolerance",
            polygon_holes_supported: false,
            polygon_holes_blocked_reason: "Canvas polygon editor supports one exterior ring only.",
          },
        });
      }
      setCadCommandStatus("POLYGON cleaned and stored as draft review geometry.");
      pushCadCommandFeedback(
        drawMode === "site" ? "SITE" : "AREA",
        "applied",
        drawMode === "site"
          ? "Site boundary captured from drawn points."
          : buildDraftGeometryCreatedMessage("AREA"),
      );
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setCadActiveCommand(null);
      draftPointsRef.current = [];
      setDrawMode("select");
      return;
    }
    onCreateCustomGeometry({ mode: drawMode, points: effectivePoints });
    pushCadCommandFeedback(
      drawMode === "rect" ? "BOX" : "LINE",
      "applied",
      buildDraftGeometryCreatedMessage(drawMode === "rect" ? "BOX" : "LINE"),
    );
    clearDraftGeometry();
    setDrawMode("select");
  }, [
	    clearDraftGeometry,
	    cursorSitePoint,
	    draftPoints,
      draftPreviewPoint,
	    drawMode,
    onCreateCustomGeometry,
    onCreateSiteBoundary,
    pushCadCommandFeedback,
  ]);

  const draftPointCount = draftPoints.length;
  const finishDraftMinPoints = getDraftGeometryMinPointCount(drawMode);
  const finishDraftCursorPoint = cursorSitePoint ? ([cursorSitePoint.x, cursorSitePoint.y] as [number, number]) : null;
  const finishDraftPreviewPoint = draftPreviewPoint ?? lastDraftPreviewPointRef.current ?? finishDraftCursorPoint;
  const finishDraftEffectivePointCount = getDraftGeometryEffectivePointCount(
    drawMode,
    draftPoints,
    finishDraftPreviewPoint,
  );
  const canFinishDraftGeometry =
    drawMode !== "select" &&
    drawMode !== "pan" &&
    drawMode !== "point" &&
    finishDraftEffectivePointCount >= finishDraftMinPoints;
  const finishDraftBlockedReason =
    drawMode !== "select" && drawMode !== "pan" && drawMode !== "point" && finishDraftEffectivePointCount < finishDraftMinPoints
      ? buildDraftGeometryFinishBlockedReason(drawMode)
      : null;
  const activeDrawToolLabel = buildDrawToolLabel(drawMode);
  const activeDrawToolDetail =
    drawMode === "site"
      ? "Pick three or more boundary points, then Finish."
      : drawMode === "polyline"
        ? "Pick two or more vertices, then Finish."
        : drawMode === "polygon"
          ? "Pick three or more area vertices, then Finish."
          : drawMode === "rect"
            ? draftPoints.length
              ? "Pick the opposite box corner."
              : "Pick the first box corner."
            : drawMode === "point"
              ? "Click once to place a draft point."
              : drawMode === "pan"
                ? "Drag the canvas."
                : "Click an object or use Object Manager.";
  const draftPrecisionReadout = useMemo(() => {
    if (drawMode === "select" || drawMode === "pan") return null;
    const points =
      draftPreviewPoint && drawMode !== "point"
        ? [...draftPoints, draftPreviewPoint]
        : draftPoints;
    const currentPoint =
      draftPreviewPoint ??
      (draftPoints.length ? draftPoints[draftPoints.length - 1] : cursorSitePoint ? [cursorSitePoint.x, cursorSitePoint.y] as [number, number] : null);
    const segments = points.slice(1).map((point, index) => {
      const previous = points[index];
      const dx = point[0] - previous[0];
      const dy = point[1] - previous[1];
      return {
        length: Math.hypot(dx, dy),
        angle: ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360,
      };
    });
    const lastSegment = segments.at(-1) ?? null;
    const totalLength = segments.reduce((sum, segment) => sum + segment.length, 0);
    const polygonArea =
      (drawMode === "polygon" || drawMode === "site") && points.length >= 3
        ? Math.abs(
            points.reduce((sum, point, index) => {
              const next = points[(index + 1) % points.length];
              return sum + point[0] * next[1] - next[0] * point[1];
            }, 0) / 2,
          )
        : null;
    return {
      currentPoint,
      lastSegment,
      totalLength,
      polygonArea,
      pointCount: draftPoints.length,
      finishReady:
        drawMode === "point" ||
        drawMode === "rect" ||
        draftPoints.length >= finishDraftMinPoints,
    };
  }, [cursorSitePoint, draftPoints, draftPreviewPoint, drawMode, finishDraftMinPoints]);

  const handleDrawPointer = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      bounds: { left: number; top: number; width: number; height: number } | null,
    ) => {
      if (drawMode === "select") return false;
      if (!bounds || !previewRef.current) return false;
      if (drawMode === "pan") {
        event.preventDefault();
        userAdjustedCanvasViewRef.current = true;
        canvasPanStartedAtRef.current = markCivoraInteraction();
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
      const rawSitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, bounds);
      if (!rawSitePoint) return true;
      event.preventDefault();
      event.stopPropagation();
      const currentDraftPoints = draftPointsRef.current.length ? draftPointsRef.current : draftPoints;
      const basePoint = currentDraftPoints.length
        ? { x: currentDraftPoints[currentDraftPoints.length - 1][0], y: currentDraftPoints[currentDraftPoints.length - 1][1] }
        : null;
      const sitePoint = resolveCadSnapPoint(rawSitePoint, basePoint);
      setActiveSnapPoint(sitePoint);
      const point: [number, number] = [sitePoint.x, sitePoint.y];
      if (drawMode === "point") {
        onCreateCustomGeometry({ mode: "point", points: [point] });
        clearDraftGeometry();
        setDrawMode("select");
        return true;
      }
      if (drawMode === "rect") {
        if (!currentDraftPoints.length) {
          draftPointsRef.current = [point];
          setDraftPoints([point]);
          return true;
        }
        onCreateCustomGeometry({ mode: "rect", points: [currentDraftPoints[0], point] });
        pushCadCommandFeedback("BOX", "applied", buildDraftGeometryCreatedMessage("BOX"));
        setDrawMode("select");
        setDraftPreviewPoint(null);
        draftPointsRef.current = [];
        setDraftPoints([]);
        return true;
      }
      const nextPoints = [...currentDraftPoints, point];
      if (drawMode === "site" && nextPoints.length >= 4) {
        const cleaned = cleanupPolygon(nextPoints, 0.5);
        if (!cleaned.ok) {
          setCadCommandStatus(`SITE blocked: ${cleaned.reason}`);
          pushCadCommandFeedback("SITE", "blocked", `SITE blocked: ${cleaned.reason}`);
          return true;
        }
        const validation = validatePolygon(cleaned.value);
        if (!validation.ok) {
          const reason = validation.issues.join(", ");
          setCadCommandStatus(`SITE blocked: ${reason}`);
          pushCadCommandFeedback("SITE", "blocked", `SITE blocked: ${reason}`);
          return true;
        }
        onCreateSiteBoundary?.({ points: cleaned.value });
        setDrawMode("select");
        setDraftPreviewPoint(null);
        draftPointsRef.current = [];
        setDraftPoints([]);
        setDrawAutoFinishPointCount(null);
        setCadActiveCommand(null);
        setCadCommandStatus("SITE boundary locked from drawn points.");
        pushCadCommandFeedback("SITE", "applied", "Site boundary locked from drawn points.");
        return true;
      }
      if (
        drawAutoFinishPointCount &&
        nextPoints.length >= drawAutoFinishPointCount &&
        (drawMode === "polyline" || drawMode === "polygon")
      ) {
        if (drawMode === "polygon") {
          const cleaned = cleanupPolygon(nextPoints, 0.5);
          if (!cleaned.ok) {
            setCadCommandStatus(`AREA blocked: ${cleaned.reason}`);
            pushCadCommandFeedback("AREA", "blocked", `AREA blocked: ${cleaned.reason}`);
            return true;
          }
          const validation = validatePolygon(cleaned.value);
          if (!validation.ok) {
            const reason = validation.issues.join(", ");
            setCadCommandStatus(`AREA blocked: ${reason}`);
            pushCadCommandFeedback("AREA", "blocked", `AREA blocked: ${reason}`);
            return true;
          }
          onCreateCustomGeometry({
            mode: "polygon",
            points: cleaned.value,
            meta: {
              geometry_cleanup: "auto_finished_after_three_points",
              polygon_holes_supported: false,
              polygon_holes_blocked_reason: "Canvas polygon editor supports one exterior ring only.",
            },
          });
          pushCadCommandFeedback("AREA", "applied", buildDraftGeometryCreatedMessage("AREA"));
        } else {
          onCreateCustomGeometry({ mode: "polyline", points: nextPoints });
          pushCadCommandFeedback("LINE", "applied", buildDraftGeometryCreatedMessage("LINE"));
        }
        setDrawMode("select");
        setDraftPreviewPoint(null);
        draftPointsRef.current = [];
        setDraftPoints([]);
        setDrawAutoFinishPointCount(null);
        setCadActiveCommand(null);
        return true;
      }
      draftPointsRef.current = nextPoints;
      setDraftPoints(nextPoints);
      return true;
    },
    [
      canvasView.offsetX,
      canvasView.offsetY,
      canDrawObjects,
      clearDraftGeometry,
      drawAutoFinishPointCount,
      draftPoints,
      drawMode,
      onCreateCustomGeometry,
      onCreateSiteBoundary,
      pushCadCommandFeedback,
      resolveCadSnapPoint,
      screenToSitePoint,
    ],
  );
  const activateDrawTool = useCallback(
    (mode: DrawMode, disabledLabel?: string) => {
      if (disabledLabel) {
        pushCadCommandFeedback("TOOL", "blocked", disabledLabel);
        return;
      }
      setDrawMode(mode);
      setDrawAutoFinishPointCount(mode === "polyline" ? 2 : null);
      clearDraftGeometry();
      if (mode !== "pan") {
        onSetPreviewInteraction("edit");
      }
      if (mode !== "select") {
        onSelectBuilding(null);
        setManagedObjectId(null);
        setHoveredObjectId(null);
        setSelectedVertex(null);
        setCadSelectionSet([]);
      }
      const label = buildDrawToolLabel(mode);
      pushCadCommandFeedback(
        "TOOL",
        "info",
        `${label} active. ${
          mode === "select"
            ? "Click an object or choose one from Object Manager."
            : mode === "polyline"
              ? "Pick two points on the canvas to create a draft line."
              : mode === "polygon"
                ? "Pick area vertices on the canvas, then Finish."
                : "Use the canvas; Finish appears when needed."
        }`,
      );
    },
    [clearDraftGeometry, onSelectBuilding, onSetPreviewInteraction, pushCadCommandFeedback],
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
      label: "Draw Site Boundary",
      icon: Pentagon,
      disabled: Boolean(siteLocked),
      disabledLabel: "Change site boundary before drawing a new boundary",
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
    const sourceState = resolveSourceState(hoveredObject);
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
      { label: "Geometry", value: geometryTruthLabel(hoveredObject) },
      { label: "Review state", value: sourceStateLabel(sourceState) },
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
      clearScheduledHoverAnnotationState(setHoverPoint);
      setHoveredVertex(null);
      setHoveredSegment(null);
    });
    return () => window.cancelAnimationFrame(handle);
  }, [clearScheduledHoverAnnotationState, showHover]);

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
    if (!debugStats?.enabled || process.env.NODE_ENV === "production") return;
    if (renderedCanonicalCount > 0 && !overlayBoundsResolved) {
      console.debug("[debug-preview] overlay-bounds-pending", {
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

  const sitePointToPreviewPercent = useCallback(
    (point: [number, number], targetMap: mapboxgl.Map | null = mapRef.current): [number, number] => {
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
    },
    [currentSiteSize, mapAnchor, showMap],
  );

  const sitePointToSvgPercent = useCallback(
    (point: [number, number]) => {
      const [x, y] = sitePointToPreviewPercent(point);
      return `${x},${y}`;
    },
    [sitePointToPreviewPercent],
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
  const mapAnchoredRectPercent = useCallback(
    (item: BuildingPlacement, targetMap: mapboxgl.Map | null) => {
      if (!showMap || !targetMap || !mapAnchor) return siteRectPercent(item);
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
      if (!projected.length) return siteRectPercent(item);
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
    },
    [mapAnchor, showMap, siteRectPercent],
  );
  const resolveObjectHitZIndex = useCallback(
    (
      item: BuildingPlacement,
      rectPct: { left: number; top: number; width: number; height: number },
      selected = false,
    ) => {
      if (selected) return 86;
      if (item.type === "site") return 18;
      const visualKind = resolveVisualKind(item);
      const sourceState = resolveSourceState(item);
      const area = Math.max(rectPct.width * rectPct.height, 0.01);
      const compactShapeBoost = Math.max(0, Math.min(18, 18 - area * 0.9));
      const pointLike =
        item.geometryType === "point" ||
        Boolean(item.meta?.cad_symbol) ||
        ["hydrant", "inlet", "outfall", "manhole"].includes(String(item.type || ""));
      const kindBoost =
        pointLike ? 24 : visualKind === "utility" ? 16 : visualKind === "water" ? 10 : visualKind === "road" ? 8 : 0;
      const stateBoost = sourceState === "fallback" ? -8 : sourceState === "blocked" ? 4 : 0;
      return Math.max(22, Math.min(84, Math.round(42 + compactShapeBoost + kindBoost + stateBoost)));
    },
    [resolveVisualKind],
  );
  const rectIntersectsPreview = useCallback(
    (rectPct: { left: number; top: number; width: number; height: number }) =>
      rectPct.left < 100 &&
      rectPct.top < 100 &&
      rectPct.left + Math.max(rectPct.width, 0) > 0 &&
      rectPct.top + Math.max(rectPct.height, 0) > 0,
    [],
  );
  const interactiveRectPercent = useCallback(
    (item: BuildingPlacement, targetMap: mapboxgl.Map | null) => {
      const anchored = mapAnchoredRectPercent(item, targetMap);
      return rectIntersectsPreview(anchored) ? anchored : siteRectPercent(item);
    },
    [mapAnchoredRectPercent, rectIntersectsPreview, siteRectPercent],
  );

  usePreviewMapRuntime({
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
    mapLocked,
    previewInteraction,
    mapDragActiveRef,
    mapDragRef,
    onMapScaleUpdate,
    onViewportFootprint,
    siteLocked,
    onViewportCenter,
    currentSiteSize,
    latLngToSite,
    lotWidth,
    lotHeight,
    placementMode,
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
  });

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

  usePreviewMapLayerSync({
    mapRef,
    fullscreenMapRef,
    showMap,
    mapLoaded,
    geocodeLat,
    geocodeLng,
    lotWidth,
    lotHeight,
    buildingPlacements,
    suggestedPlacementsLength: suggestedPlacements.length,
    analysisPaths,
    debugStatsEnabled: debugStats?.enabled,
    planPreviewUrl,
    resolveVisualKind,
    showSiteBounds,
    surveyPoints,
    useLightHighQuality,
    waterFireFlow,
    siteToLatLng,
    mapRevision,
  });

  usePreviewResizeObservers({
    previewRef,
    previewImageRef,
    fullscreenRef,
    fullscreenImageRef,
    mapRef,
    fullscreenMapRef,
    previewResizeRafRef,
    fullscreenResizeRafRef,
    previewSizeRef,
    fullscreenSizeRef,
    lastMapResizeRef,
    showMap,
    showGeneratedPlan,
    planPreviewUrl,
    previewMode,
    previewFullscreenOpen,
    updateContainerBounds,
    updateImageBounds,
    setPreviewImageBounds,
    setFullscreenImageBounds,
  });
  const { focusTransform, setFocusTransform } = usePreviewFocusTransform({
    focusDetectedId,
    focusObjectId,
    buildingPlacements,
    suggestedPlacements,
    analysisPaths,
    analysisHighlight,
    lotWidth,
    lotHeight,
    onSelectBuilding,
    onClearFocusDetected,
    onClearFocusObject,
    setHoveredObjectId,
  });
  const showParkingAnalysis = Boolean(analysisPaths && analysisPaths.length);
  const activePreviewMode: "2d" | "3d" = previewMode;
  return (
    <div className="civora-preview-panel flex h-full min-w-0 flex-col overflow-x-hidden overflow-y-auto rounded-xl border border-slate-200 bg-white/92 p-2 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.45)] backdrop-blur sm:p-3">
      <div className="civora-preview-canvas-container flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] sm:p-3">
          <div className="relative isolate z-[220] mb-3 overflow-visible rounded-xl border border-slate-200 bg-white/95 shadow-sm">
            <PreviewCanvasHeaderControls
              previewMode={previewMode}
              previewQuality={previewQuality}
              coordinateMode={coordinateMode}
              canUse3D={canUse3D}
              mapAvailable={mapAvailable}
              mapOverlayEnabled={mapOverlayEnabled}
              mapLocked={mapLocked}
              showMap={showMap}
              allowEdits={allowEdits}
              drawMode={drawMode}
              siteLocked={siteLocked}
              canDrawObjects={canDrawObjects}
              drawObjectsDisabledLabel={drawObjectsDisabledLabel}
              isHighQuality={isHighQuality}
              useLightHighQuality={useLightHighQuality}
              busy={busy}
              analysisHighlight={analysisHighlight}
              onSetPreviewQuality={onSetPreviewQuality}
              onSetPreviewMode={onSetPreviewMode}
              onSetPreviewInteraction={onSetPreviewInteraction}
              onSetMapOverlayEnabled={setMapOverlayEnabled}
              onSetMapLocked={setMapLocked}
              onActivateDrawTool={activateDrawTool}
              onPushCadCommandFeedback={pushCadCommandFeedback}
              onUnlockSite={onUnlockSite}
              onClearDraftGeometry={clearDraftGeometry}
              onSetDrawMode={setDrawMode}
              onSetFocusTransform={setFocusTransform}
              onResetView={onResetView}
              onRefreshPreview={onRefreshPreview}
              onClearHighlights={onClearHighlights}
            />
            <div className="pointer-events-none relative z-[220] flex min-w-0 max-w-full flex-wrap items-stretch gap-2 px-3 py-2">
              {previewMode === "2d" ? (
                <PreviewObjectManagerOverlay
                  visible={allowEdits && drawMode === "select" && Boolean(selectedObject)}
                  selectedObject={selectedObject}
                  selectedBuildingId={selectedBuildingId}
                  objectManagerRows={objectManagerRows}
                  objectManagerCounts={objectManagerCounts}
                  selectedCadIds={selectedCadIds}
                  onSetManagedObjectId={setManagedObjectId}
                  onSelectBuilding={onSelectBuilding}
                  onSetCadSelectionSet={setCadSelectionSet}
                  onClearSelectedVertex={() => setSelectedVertex(null)}
                  onSetCadCommandStatus={setCadCommandStatus}
                  onUpdatePreviewManagedObject={updatePreviewManagedObject}
                  onFocusPreviewManagedObject={focusPreviewManagedObject}
                  onRemoveBuilding={onRemoveBuilding}
                  onSetLastRectEdit={setLastRectEdit}
                  getPreviewObjectActionBlocker={getPreviewObjectActionBlocker}
                  getPreviewObjectDimensionsLabel={getPreviewObjectDimensionsLabel}
                  getPreviewObjectSourceLabel={getPreviewObjectSourceLabel}
                  getPreviewObjectStatusLabel={getPreviewObjectStatusLabel}
                  getCadLayer={getCadLayer}
                />
              ) : null}
            </div>
            {previewMode === "2d" && allowEdits ? (
              <PreviewStableDrawToolbar
                drawMode={drawMode}
                siteLocked={Boolean(siteLocked)}
                hasDrawableSiteSize={hasDrawableSiteSize}
                canDrawObjects={canDrawObjects}
                drawObjectsDisabledLabel={drawObjectsDisabledLabel}
                onUnlockSite={onUnlockSite}
                onLockSite={onLockSite}
                onClearDraftGeometry={clearDraftGeometry}
                onSetDrawMode={setDrawMode}
                onSetPreviewInteraction={onSetPreviewInteraction}
                onActivateDrawTool={activateDrawTool}
                onPushCadCommandFeedback={pushCadCommandFeedback}
              />
            ) : null}
            <PreviewActiveDrawHud
              drawMode={drawMode}
              activeDrawToolLabel={activeDrawToolLabel}
              activeDrawToolDetail={activeDrawToolDetail}
              draftPointCount={draftPoints.length}
              siteLocked={Boolean(siteLocked)}
              canDrawObjects={canDrawObjects}
              drawObjectsDisabledLabel={drawObjectsDisabledLabel}
              cursorSitePoint={cursorSitePoint}
              canvasScale={canvasView.scale}
              lastCommandLabel={cadHistory.at(-1)?.label}
              canFinishDraftGeometry={canFinishDraftGeometry}
              finishDraftBlockedReason={finishDraftBlockedReason}
              onFinishDraftGeometry={finishDraftGeometry}
              onCancelDraw={() => {
                clearDraftGeometry();
                setDrawMode("select");
                setActiveSnapPoint(null);
                setCadCommandStatus("Cancelled active drawing tool.");
              }}
            />
          </div>
          <CadPrecisionDock
            visible={previewMode === "2d" && allowEdits && hasCadCommandActivity}
            selectedCadObject={selectedCadObject}
            selectedCadIds={selectedCadIds}
            selectedBuildingId={selectedBuildingId}
            selectedCadMetrics={selectedCadMetrics}
            cadSnapEnabled={cadSnapEnabled}
            cadOrthoEnabled={cadOrthoEnabled}
            cadCoordinateDraft={cadCoordinateDraft}
            cadCommandDraft={cadCommandDraft}
            cadCommandStatus={cadCommandStatusDisplay}
            cadCommandHistory={cadCommandHistoryDisplay}
            cadActiveCommand={cadActiveCommand}
            draftPoints={draftPoints}
            cadHistory={cadHistory}
            cadRedoStack={cadRedoStack}
            lastPolylineEdit={lastPolylineEdit}
            lastRectEdit={lastRectEdit}
            activeSnapPoint={activeSnapPoint}
            cadTransformValue={cadTransformValue}
            cadDimensionMode={cadDimensionMode}
            cadDimensionLabelDraft={cadDimensionLabelDraft}
            cadOffsetDistance={cadOffsetDistance}
            cadFilletRadius={cadFilletRadius}
            cadLayerDraft={cadLayerDraft}
            cadLayerOptions={cadLayerOptions}
            hiddenCadLayers={hiddenCadLayers}
            cadSymbolDraft={cadSymbolDraft}
            cadPropertyDraft={cadPropertyDraft}
            topologyIssues={topologyIssues}
            setCadSnapEnabled={setCadSnapEnabled}
            setCadOrthoEnabled={setCadOrthoEnabled}
            setCadCoordinateDraft={setCadCoordinateDraft}
            setCadCommandDraft={setCadCommandDraft}
            setCadTransformValue={setCadTransformValue}
            setCadDimensionMode={setCadDimensionMode}
            setCadDimensionLabelDraft={setCadDimensionLabelDraft}
            setCadOffsetDistance={setCadOffsetDistance}
            setCadFilletRadius={setCadFilletRadius}
            setCadLayerDraft={setCadLayerDraft}
            setCadSelectionSet={setCadSelectionSet}
            setCadSymbolDraft={setCadSymbolDraft}
            setCadPropertyDraft={setCadPropertyDraft}
            undoCadCommand={undoCadCommand}
            redoCadCommand={redoCadCommand}
            applyCadCoordinate={applyCadCoordinate}
            runCadCommand={runCadCommand}
            transformSelectedCadObjects={transformSelectedCadObjects}
            applySelectedCadDimension={applySelectedCadDimension}
            offsetSelectedCadObject={offsetSelectedCadObject}
            trimExtendSelectedCadObject={trimExtendSelectedCadObject}
            filletSelectedCadObject={filletSelectedCadObject}
            applySelectedCadLayer={applySelectedCadLayer}
            toggleCadLayerVisibility={toggleCadLayerVisibility}
            insertCadSymbol={insertCadSymbol}
            applyCadProperties={applyCadProperties}
          />
          <UtilityCoordinationDock rows={utilityCoordinationRows} summary={utilityCoordinationSummary} />
          {show3D ? (
            <Preview3DShell
              items={preview3DEffectiveItems}
              allowEdits={allowEdits}
              previewQuality={previewQuality}
              selectedItemId={selectedBuildingId}
              hasTerrainSource={hasTerrainSource}
              hasGradingSurface={hasGradingSurface}
              usingAnnotation3D={usingAnnotation3D}
              isHighQuality={isHighQuality}
              aiRealismEnabled={aiRealismEnabled}
              onSetPreviewMode={onSetPreviewMode}
              onSetPreviewQuality={onSetPreviewQuality}
              onSelectItem={onSelectBuilding}
              onOpenFullscreen={onOpenFullscreen}
              onSetAiVisualizationOff={setAiVisualizationOff}
              onSetAiVisualizationOn={setAiVisualizationOn}
            />
          ) : (
            <div
              ref={previewRef}
              className={`civora-preview-shell relative flex w-full min-w-0 flex-1 min-h-[320px] items-center justify-center overflow-hidden rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)] ${
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
              onMouseDownCapture={(event) => {
                const target = event.target as HTMLElement | null;
                if (
                  drawMode !== "select" &&
                  drawMode !== "pan" &&
                  !target?.closest?.("button,input,textarea,select,[role='button'],[data-no-window-select]")
                ) {
                  if (handleDrawPointer(event, overlayBoundsResolved)) {
                    suppressNextDrawClickRef.current = true;
                    return;
                  }
                }
                beginCadWindowSelect(event);
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
                if (cadWindowSelect) {
                  setCadWindowSelect((current) =>
                    current ? { ...current, currentX: event.clientX, currentY: event.clientY } : current,
                  );
                  return;
                }
                if (rotateDragStart && previewContainerBounds && onSetSiteRotationDeg) {
                  const deltaX = event.clientX - rotateDragStart.x;
                  const width = Math.max(previewContainerBounds.width, 1);
                  const deltaDeg = (deltaX / width) * 180;
                  const nextValue = rotateDragStart.value + deltaDeg;
                  onSetSiteRotationDeg(Math.max(-180, Math.min(180, nextValue)));
                  return;
                }
                if (canvasPanStart) {
                  scheduleCanvasPanView({
                    offsetX: canvasPanStart.offsetX + event.clientX - canvasPanStart.x,
                    offsetY: canvasPanStart.offsetY + event.clientY - canvasPanStart.y,
                  });
                  return;
                }
                if (drawMode !== "select" && drawMode !== "pan" && overlayBoundsResolved) {
                  const rawSitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, overlayBoundsResolved);
                  const basePoint = draftPoints.length
                    ? { x: draftPoints[draftPoints.length - 1][0], y: draftPoints[draftPoints.length - 1][1] }
                    : null;
                  const sitePoint = rawSitePoint ? resolveCadSnapPoint(rawSitePoint, basePoint) : null;
                  scheduleDraftPointerState(sitePoint);
                  return;
                }
                if (overlayBoundsResolved) {
                  updateDraggedBuilding(event, overlayBoundsResolved);
                }
                if (showHover) {
                  resolveHover(event, previewRef, overlayBoundsResolved, setHoverPoint);
                } else {
                  if (hoverPoint || hoveredAnnotation) clearScheduledHoverAnnotationState(setHoverPoint);
                  if (hoveredObjectId) setHoveredObjectId(null);
                }
                if (showHover && overlayBoundsResolved && lotWidth > 0 && lotHeight > 0 && previewRef.current) {
                  const sitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, overlayBoundsResolved);
                  scheduleCursorSitePoint(sitePoint);
                } else if (!showHover) {
                  scheduleCursorSitePoint(null);
                } else {
                  scheduleCursorSitePoint(null);
                }
              }}
              onMouseLeave={() => {
                clearScheduledHoverAnnotationState(setHoverPoint);
                setHoveredObjectId(null);
                setDraggingBuildingId(null);
                setDraggingMode(null);
                finishCanvasPanInteraction();
                setCanvasPanStart(null);
                clearScheduledPointerState();
                if (!cadWindowSelect) setCadWindowSelect(null);
              }}
              onMouseUp={() => {
                if (cadWindowSelect) {
                  finishCadWindowSelect(cadWindowSelect);
                  cadWindowSelectRef.current = null;
                  setCadWindowSelect(null);
                }
                setDraggingBuildingId(null);
                setDraggingMode(null);
                setRotateDragStart(null);
                finishCanvasPanInteraction();
                setCanvasPanStart(null);
              }}
              onClick={(event) => {
                if (suppressNextObjectClickRef.current) {
                  suppressNextObjectClickRef.current = false;
                  event.stopPropagation();
                  return;
                }
                if (allowMapInteraction) return;
                if (drawMode !== "select") {
                  if (suppressNextDrawClickRef.current) {
                    suppressNextDrawClickRef.current = false;
                    return;
                  }
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
	                if (previewMode !== "2d" || !overlayBoundsResolved || showMap) return;
	                userAdjustedCanvasViewRef.current = true;
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
	              <CanvasQuickDrawPalette
                visible={previewMode === "2d" && showQuickDrawPalette}
                drawMode={drawMode}
                siteLocked={Boolean(siteLocked)}
                hasDrawableSiteSize={hasDrawableSiteSize}
                canDrawObjects={canDrawObjects}
                drawObjectsDisabledLabel={drawObjectsDisabledLabel}
                canFinishDraftGeometry={canFinishDraftGeometry}
                finishDraftBlockedReason={finishDraftBlockedReason}
                onActivateDrawTool={activateDrawTool}
                onFinishDraftGeometry={finishDraftGeometry}
                onCancelDraw={() => {
                  clearDraftGeometry();
                  setDrawMode("select");
                  setActiveSnapPoint(null);
                  setCadCommandStatus("Cancelled active drawing tool.");
                }}
                onUnlockSite={onUnlockSite}
                onLockSite={onLockSite}
                onClearDraftGeometry={clearDraftGeometry}
                onSetDrawMode={setDrawMode}
                onSetPreviewInteraction={onSetPreviewInteraction}
                onPushCadCommandFeedback={pushCadCommandFeedback}
              />
              <PreviewFloatingToolbar
                previewMode={previewMode}
                activePreviewMode={activePreviewMode}
                previewQuality={previewQuality}
                canUse3D={canUse3D}
                isHighQuality={isHighQuality}
                aiRealismEnabled={aiRealismEnabled}
                allowEdits={allowEdits}
                siteLocked={Boolean(siteLocked)}
                canDrawObjects={canDrawObjects}
                drawObjectsDisabledLabel={drawObjectsDisabledLabel}
                drawMode={drawMode}
                onSetPreviewMode={onSetPreviewMode}
                onSetPreviewQuality={onSetPreviewQuality}
                onSetAiVisualizationOff={setAiVisualizationOff}
                onSetAiVisualizationOn={setAiVisualizationOn}
                onSetPreviewInteraction={onSetPreviewInteraction}
                onUnlockSite={onUnlockSite}
                onClearDraftGeometry={clearDraftGeometry}
                onSetDrawMode={setDrawMode}
                onActivateDrawTool={activateDrawTool}
              />
              {isHighQuality && aiRealismEnabled ? (
                <AiRealismPreviewOverlay
                  artifact={aiRealismDisplayArtifact}
                  blocker={aiRealismBlocker}
                  stale={Boolean(aiRealismDisplayArtifact?.stale)}
                  hasTerrainSource={hasTerrainSource}
                  watermark={AI_REALISM_WATERMARK}
                  onRegenerate={generateAiRealismArtifact}
                />
              ) : null}
              {showMobileDrawToolbar ? (
                <PreviewMobileDrawToolbar
                  drawModeButtons={drawModeButtons}
                  drawMode={drawMode}
                  compactViewport={compactViewport}
                  canFinishDraftGeometry={canFinishDraftGeometry}
                  finishDraftBlockedReason={finishDraftBlockedReason}
                  selectedDeletable={Boolean(selectedDeletableObject)}
                  siteLocked={Boolean(siteLocked)}
                  onActivateTool={(mode, blockedMessage) => {
                    activateDrawTool(mode, blockedMessage);
                    if (!blockedMessage && mode !== "select") {
                      window.requestAnimationFrame(() => {
                        previewRef.current?.scrollIntoView({
                          behavior: "auto",
                          block: "center",
                          inline: "nearest",
                        });
                      });
                    }
                  }}
                  onFinish={finishDraftGeometry}
                  onCancel={() => {
                    clearDraftGeometry();
                    setDrawMode("select");
                    setActiveSnapPoint(null);
                    setCadCommandStatus("Cancelled active drawing tool.");
                  }}
                  onChangeSite={onUnlockSite ? () => {
                    onUnlockSite();
                    clearDraftGeometry();
                    setDrawMode("select");
                    onSetPreviewInteraction("edit");
                  } : undefined}
                  onResetView={resetCanvasView}
                  onDeleteSelected={() => {
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
                />
              ) : null}
              <div
                className="relative flex h-full w-full items-center justify-center overflow-hidden"
                onMouseDown={(event) => {
                  if (allowMapInteraction) return;
                  if (drawMode === "pan") {
                    handleDrawPointer(event, overlayBoundsResolved);
                    return;
                  }
                  if (drawMode !== "select") {
                    if (handleDrawPointer(event, overlayBoundsResolved)) {
                      suppressNextDrawClickRef.current = true;
                    }
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
	                <PreviewMapStatusOverlay
	                  debugEnabled={Boolean(debugStats?.enabled)}
	                  geocode={geocode}
	                  showMap={showMap}
	                  previewQuality={previewQuality}
	                  previewMode={previewMode}
	                  mapLoaded={mapLoaded}
	                  mapboxRequestCount={mapboxRequestCount}
	                  mapboxTileCount={mapboxTileCount}
	                  mapContainerSize={mapContainerSize}
	                  mapCanvasSize={mapCanvasSize}
	                  mapError={mapError}
	                  showMap3D={showMap3D}
	                  siteRotationDeg={siteRotationDeg}
	                />
                {previewMode === "2d" ? (
                  <PreviewCanvasHud
                    scaleLengthFt={planScaleBar.lengthFt}
                    zoomScale={canvasView.scale}
                    lotWidth={lotWidth}
                    lotHeight={lotHeight}
                    scaleTruthLabel={scaleTruthLabel}
                    cursorSitePoint={cursorSitePoint}
                    draftPrecisionReadout={draftPrecisionReadout}
                    activeDrawToolLabel={activeDrawToolLabel}
                    activeSnapKind={activeSnapPoint?.kind}
                    onZoomIn={() => {
                      userAdjustedCanvasViewRef.current = true;
                      setCanvasView((prev) => ({ ...prev, scale: Math.min(prev.scale + 0.15, 4) }));
                    }}
                    onZoomOut={() => {
                      userAdjustedCanvasViewRef.current = true;
                      setCanvasView((prev) => ({ ...prev, scale: Math.max(prev.scale - 0.15, 0.55) }));
                    }}
                    onResetView={resetCanvasView}
                  />
                ) : null}
                {showGeneratedPlan && planPreviewUrl && !showMap ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    ref={previewImageRef}
                    src={planPreviewUrl}
                    alt="Generated plan preview"
                    className={`pointer-events-none h-full w-full object-contain ${
                      placementMode || allowEdits ? "cursor-crosshair" : "cursor-default"
                    }`}
                    onLoad={() => updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds)}
                  />
                ) : !showMap && !hasLiveObjects ? (
                  <div className="flex h-full w-full items-center justify-center text-sm text-slate-400">
                    Add objects to start building the site. Then click Place and drop them here.
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
	                        <PreviewSvgDefs />
	                        <PreviewBasePlanGrid
	                          showMap={showMap}
	                          isHighQuality={isHighQuality}
	                          siteLocked={Boolean(siteLocked)}
	                          lotWidth={lotWidth}
	                          lotHeight={lotHeight}
	                          planScaleBar={planScaleBar}
	                        />
	                        <PreviewPolylineObjects
	                          objects={visibleCadObjects}
	                          selectedBuildingId={selectedBuildingId}
	                          isHighQuality={isHighQuality}
	                          currentSiteSize={currentSiteSize}
	                          sitePointToSvgPercent={sitePointToSvgPercent}
	                        />
                        <PreviewRectObjects
                          objects={visibleCadObjects}
                          selectedBuildingId={selectedBuildingId}
                          isHighQuality={isHighQuality}
                          mapAnchoredRectPercent={(item) => mapAnchoredRectPercent(item, mapRef.current)}
                        />
                        <PreviewPolygonObjects
                          objects={visibleCadObjects}
                          selectedBuildingId={selectedBuildingId}
                          isHighQuality={isHighQuality}
                          sitePointToSvgPercent={sitePointToSvgPercent}
                        />
                        <PreviewCadMarkers
                          objects={visibleCadObjects}
                          selectedBuildingId={selectedBuildingId}
                          currentSiteSize={currentSiteSize}
                          sitePointToPreviewPercent={sitePointToPreviewPercent}
                          mapAnchoredRectPercent={(item) => mapAnchoredRectPercent(item, mapRef.current)}
                          shouldRevealObjectLabel={shouldRevealObjectLabel}
                          getObjectGeometryPoints={getObjectGeometryPoints}
                        />
                        <PreviewParkingModules
                          objects={visibleCadObjects}
                          accessPoints={accessPointsForParking}
                          showParkingAnalysis={showParkingAnalysis}
                          buildParkingModules={buildPreviewParkingMapModules}
                          sitePointToSvgPercent={sitePointToSvgPercent}
                        />
                        <PreviewSuggestedGeometry
                          objects={suggestedPlacements}
                          selectedBuildingId={selectedBuildingId}
                          detectedStroke={legendPalette.detectedStroke}
                          detectedFill={legendPalette.detectedFill}
                          sitePointToSvgPercent={sitePointToSvgPercent}
                        />
                        <PreviewWaterFireFlowOverlay
                          waterFireFlow={waterFireFlow}
                          previewQuality={previewQuality}
                          sitePointToPreviewPercent={sitePointToPreviewPercent}
                        />
                        <PreviewDraftGeometryOverlay
                          activeSnapPoint={activeSnapPoint}
                          draftPoints={draftPoints}
                          draftPreviewPoint={draftPreviewPoint}
                          drawMode={drawMode}
                          drawingLotWidth={drawingLotWidth}
                          drawingLotHeight={drawingLotHeight}
                          lotWidth={lotWidth}
                          lotHeight={lotHeight}
                          sitePointToPreviewPercent={sitePointToPreviewPercent}
                          siteTupleToPercent={siteTupleToPercent}
                          siteRectToPercent={siteRectToPercent}
                        />
                      </svg>
                    ) : null}
                    {showEarthworkUx && gradingEarthworkUx ? (
                      <PreviewGradingEarthworkDock
                        gradingEarthworkUx={gradingEarthworkUx}
                        formatMetric={formatMetric}
                      />
                    ) : null}
              <div
                data-testid="preview-drawing-surface"
                data-draw-mode={drawMode}
                data-draft-point-count={draftPointCount}
                aria-label="Drawing surface"
                className={`absolute inset-0 ${drawMode !== "select" && drawMode !== "pan" ? "z-[35]" : "z-[14]"} ${
                  drawMode !== "select" && drawMode !== "pan" ? "pointer-events-auto cursor-crosshair" : "pointer-events-none"
                }`}
              />
                    <div
                      data-testid="preview-drawing-overlays"
                      className={`${overlayPointerEvents} absolute inset-0 z-[15]`}
                      style={{
                        transformOrigin: "top left",
                        transform: `${viewportTransformStyle.transform}${
                          focusTransform
                            ? ` translate(50%, 50%) scale(${focusTransform.scale}) translate(-${focusTransform.tx * 100}%, -${focusTransform.ty * 100}%)`
                            : ""
                        }`,
                      }}
                      onMouseDown={(event) => {
                        if (beginCadWindowSelect(event)) return;
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
                      {waterFireFlow.hydrants.map((hydrant) => {
                        const [left, top] = sitePointToPreviewPercent([hydrant.x, hydrant.y]);
                        const scenario = waterFireFlow.scenarios.find((item) => item.hydrantId === hydrant.id);
                        const selected = waterFireFlow.selectedHydrant?.id === hydrant.id;
                        return (
                          <button
                            key={`hydrant-hit-${hydrant.id}`}
                            type="button"
                            data-object-overlay
                            aria-label={`Select ${hydrant.label} fire-flow scenario`}
                            title={`${hydrant.label}: ${formatFlowValue(hydrant.availableFlowGpm, "gpm")}`}
                            onClick={(event) => {
                              event.stopPropagation();
                              if (scenario) setSelectedFireScenarioId(scenario.id);
                            }}
                            className={`${passiveOverlayPointerEvents} absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-white/20 transition ${
                              selected
                                ? "border-slate-950 shadow-[0_0_0_4px_rgba(14,165,233,0.18)]"
                                : "border-white/80 hover:border-slate-950"
                            }`}
                            style={{ left: `${left}%`, top: `${top}%` }}
                          />
                        );
                      })}
                      {visibleCadObjects
                      .filter(
                        (item) => {
                          const editableSiteBox =
                            item.type === "site" && previewInteraction === "edit" && !siteLocked && showSiteBounds && !showMap;
                          return (
                            (item.type !== "site" || editableSiteBox) &&
                          item.placed &&
                          Number.isFinite(item.x) &&
                            Number.isFinite(item.y)
                          );
                        },
                      )
                      .map((item) => {
                        const caps = getEditCapabilities(item);
                        const isSelected = selectedBuildingId === item.id;
                        const rectPct = interactiveRectPercent(item, mapRef.current);
                        const rotation = showMap ? 0 : (item.rotation ?? 0);
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
                        const showBoxChrome = showBox && (isSelected || Boolean(isAccessHighlight));
                        const showQuickSelectionActions = isSelected && drawMode === "select";
                        const showSelectionAffordances = showQuickSelectionActions && allowEdits;
                        const isSite = item.type === "site";
                        const visualKind = resolveVisualKind(item);
                        const sourceState = resolveSourceState(item);
                        if (!rectIntersectsPreview(rectPct)) return null;
                        const allowItemInteraction =
                          drawMode === "select" &&
                          (!isSite || (previewInteraction === "edit" && !siteLocked));
                        const hitZIndex = resolveObjectHitZIndex(item, rectPct, isSelected);
                        const overlayZIndex = isSelected ? Math.max(hitZIndex, 120) : hitZIndex;
                        return (
                          <div
                            key={item.id}
                            data-object-overlay
                            data-cad-object-id={item.id}
                            aria-label={`Select ${item.label || item.type || "Draft object"}`}
                            data-preview-quality={previewQuality}
                            data-visual-kind={visualKind}
                            data-source-state={sourceState}
                            data-hit-priority={hitZIndex}
                            className={`${allowItemInteraction ? passiveOverlayPointerEvents : "pointer-events-none"} absolute z-[30]`}
                            style={{
                              left: `${rectPct.left}%`,
                              top: `${rectPct.top}%`,
                              width: `${rectPct.width}%`,
                              height: `${rectPct.height}%`,
                              zIndex: overlayZIndex,
                              scrollMarginBottom: "10rem",
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: caps.movable ? (isPolyline ? "grab" : "move") : "default",
                            }}
                            onMouseDown={(event) => {
                              if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                              if (draggingMode === "vertex" || hoveredSegment?.id === item.id) return;
                              handleBuildingMouseDown(event, item, "move");
                            }}
                            onMouseEnter={() => {
                              if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                              setHoveredObjectId(item.id);
                            }}
                            onMouseLeave={() => {
                              setHoveredObjectId(null);
                              setHoveredVertex(null);
                            }}
                            onClick={(event) => {
                              if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                              if (suppressNextObjectClickRef.current) {
                                suppressNextObjectClickRef.current = false;
                                event.stopPropagation();
                                return;
                              }
                              event.stopPropagation();
                              setSelectedVertex(null);
                              onSelectBuilding(item.id);
                            }}
                          >
                            <div
                              className={`pointer-events-none h-full w-full rounded-[8px] shadow-sm transition ${
                                showBoxChrome ? `border ${borderColor}` : ""
                              } ${
                                showBoxChrome && isSelected ? "ring-2 ring-amber-400 ring-offset-2 ring-offset-white/80 shadow-[0_0_0_6px_rgba(251,191,36,0.14)]" : ""
                              } ${showBoxChrome && isAccessHighlight ? "ring-2 ring-rose-300" : ""}`}
                              style={{
                                backgroundColor: "transparent",
                                borderColor: showBoxChrome ? outlineColor || undefined : "transparent",
                              }}
                            />
                            {isSelected && showBox ? (
                              <>
                                <div className="pointer-events-none absolute inset-0 rounded-[8px] border border-amber-500/80" />
                                {[
                                  "left-0 top-0 -translate-x-1/2 -translate-y-1/2",
                                  "right-0 top-0 translate-x-1/2 -translate-y-1/2",
                                  "bottom-0 right-0 translate-x-1/2 translate-y-1/2",
                                  "bottom-0 left-0 -translate-x-1/2 translate-y-1/2",
                                ].map((position) => (
                                  <span
                                    key={`box-grip-${item.id}-${position}`}
                                    className={`pointer-events-none absolute h-2.5 w-2.5 rounded-sm border border-white bg-amber-400 shadow ${position}`}
                                  />
                                ))}
                              </>
                            ) : null}
                            {showQuickSelectionActions ? (
                              <div
                                data-testid="selected-object-quick-toolbar"
                                className="pointer-events-auto absolute left-1/2 top-0 z-[95] flex min-w-max -translate-x-1/2 -translate-y-[calc(100%+10px)] flex-col items-center gap-1 rounded-lg border border-slate-200 bg-white/95 p-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-700 shadow-lg backdrop-blur"
                                onMouseDown={(event) => {
                                  event.preventDefault();
                                  event.stopPropagation();
                                }}
                                onClick={(event) => event.stopPropagation()}
                              >
                                <div className="flex items-center gap-1">
                                  <button
                                    type="button"
                                    data-testid="selected-object-quick-measure"
                                    className="rounded-md px-2 py-1 hover:bg-slate-100"
                                    onClick={() => runCadCommand("DIST")}
                                  >
                                    Measure
                                  </button>
                                  <button
                                    type="button"
                                    data-testid="selected-object-quick-copy"
                                    className="rounded-md px-2 py-1 hover:bg-slate-100"
                                    onClick={() => copySelectedCadObjectsByVector([10, 10])}
                                  >
                                    Copy
                                  </button>
                                  <button
                                    type="button"
                                    data-testid="selected-object-quick-rotate"
                                    className="rounded-md px-2 py-1 hover:bg-slate-100"
                                    onClick={() => transformSelectedCadObjects("rotate")}
                                  >
                                    Rotate
                                  </button>
                                  <button
                                    type="button"
                                    data-testid="selected-object-quick-inspect"
                                    className="rounded-md px-2 py-1 hover:bg-slate-100"
                                    onClick={() => {
                                      onSelectBuilding(item.id);
                                      pushCadCommandFeedback("INSPECT", "info", `INSPECT selected ${item.label || "draft object"}. Use Object Manager for full properties.`);
                                    }}
                                  >
                                    Inspect
                                  </button>
                                  <button
                                    type="button"
                                    data-testid="selected-object-quick-delete"
                                    disabled={!selectedDeletableObject || selectedDeletableObject.id !== item.id}
                                    className="rounded-md px-2 py-1 text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40"
                                    onClick={() => {
                                      if (!selectedDeletableObject || selectedDeletableObject.id !== item.id) {
                                        pushCadCommandFeedback("DELETE", "blocked", "DELETE blocked: selected object is locked or required evidence.");
                                        return;
                                      }
                                      setLastRectEdit({
                                        id: item.id,
                                        snapshot: { ...item },
                                        action: "delete",
                                        ts: Date.now(),
                                      });
                                      onRemoveBuilding(item.id);
                                      pushCadCommandFeedback("DELETE", "applied", `DELETE removed ${item.label || "selected draft object"}.`);
                                    }}
                                  >
                                    Delete
                                  </button>
                                </div>
                                <p
                                  data-testid="selected-object-quick-status"
                                  className="max-w-[22rem] truncate rounded-md bg-slate-50 px-2 py-0.5 normal-case tracking-normal text-slate-500"
                                >
                                  {cadCommandStatusDisplay}
                                </p>
                              </div>
                            ) : null}
                            {showBox && isHighQuality && visualKind === "building" ? (
                              <div className="pointer-events-none absolute inset-x-[16%] top-1/2 h-px -translate-y-1/2 bg-white/35" />
                            ) : null}
                            {showBox && isHighQuality && visualKind === "water" ? (
                              <div className="pointer-events-none absolute inset-x-[14%] top-1/2 h-px -translate-y-1/2 bg-sky-100/60 shadow-[0_5px_0_rgba(224,242,254,0.34),0_-5px_0_rgba(224,242,254,0.24)]" />
                            ) : null}
                            {showBox && isHighQuality && visualKind === "utility" ? (
                              <div className="pointer-events-none absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/80 bg-violet-500/80" />
                            ) : null}
                            {showSelectionAffordances && isEditableVertexGeometry && Array.isArray(item.geometry)
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
                            {showSelectionAffordances &&
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
                            {showSelectionAffordances && isEditableVertexGeometry ? (
                              <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-amber-700 shadow">
                                Vertex edit
                              </div>
                            ) : null}
                            {showSelectionAffordances &&
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
                            {showSelectionAffordances && isEditableVertexGeometry && selectedVertex?.id === item.id ? (
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
                            {showSelectionAffordances &&
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
                            {showSelectionAffordances &&
                            isEditableVertexGeometry &&
                            !polylineInsertHintDismissed &&
                            (isPolygon || item.type === "custom" || item.type === "road" || item.type === "driveway" || item.type === "sidewalk") ? (
                              <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-600 shadow">
                                Click a segment to add a vertex
                              </div>
                            ) : null}
                            {showSelectionAffordances && caps.rotatable ? (
                              <button
                                type="button"
                                title="Rotate selected object"
                                aria-label="Rotate selected object"
                                data-testid="selected-object-rotate-handle"
                                className="absolute -right-3 -top-3 h-7 w-7 rounded-full border border-slate-300 bg-white text-[10px] font-semibold text-slate-700 shadow-lg hover:bg-slate-50"
                                onMouseDown={(event) => handleBuildingMouseDown(event, item, "rotate")}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setLastRectEdit({
                                    id: item.id,
                                    snapshot: { ...item },
                                    action: "update",
                                    ts: Date.now(),
                                  });
                                  const nextRotation = (((item.rotation ?? 0) + 15) % 360 + 360) % 360;
                                  if (item.source === "detected_from_image") {
                                    onUpdateSuggested(item.id, { rotation: nextRotation });
                                  } else {
                                    onUpdateBuilding(item.id, { rotation: nextRotation });
                                  }
                                }}
                              >
                                R
                              </button>
                            ) : null}
                            {showSelectionAffordances && caps.resizable ? (
                              <button
                                type="button"
                                title="Resize selected object"
                                aria-label="Resize selected object"
                                data-testid="selected-object-resize-handle"
                                className="absolute -right-3 -bottom-3 h-7 w-7 rounded-full border border-slate-300 bg-white text-[10px] font-semibold text-slate-700 shadow-lg hover:bg-slate-50"
                                onMouseDown={(event) => handleBuildingMouseDown(event, item, "resize")}
                              >
                                Z
                              </button>
                            ) : null}
                            {showSelectionAffordances && caps.deletable ? (
                              <button
                                type="button"
                                title="Delete selected object"
                                aria-label="Delete selected object"
                                data-testid="selected-object-delete-handle"
                                className="absolute -left-3 -top-3 h-7 w-7 rounded-full border border-rose-200 bg-white text-[10px] font-semibold text-rose-600 shadow-lg hover:bg-rose-50"
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
                            {showSelectionAffordances && shouldRevealObjectLabel(item) && caps.movable && !isPolyline ? (
                              <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
                                Snap 5ft
                              </div>
                            ) : null}
                            {showSelectionAffordances && shouldRevealObjectLabel(item) && typeof item.x === "number" && typeof item.y === "number" ? (
                              <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-600 shadow">
                                X {item.x.toFixed(1)} ft • Y {item.y.toFixed(1)} ft
                              </div>
                            ) : null}
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
                        const rectPct = interactiveRectPercent(item, mapRef.current);
                        if (!rectIntersectsPreview(rectPct)) return null;
                        const rotation = showMap ? 0 : (item.rotation ?? 0);
                        const hitZIndex = resolveObjectHitZIndex(item, rectPct, selectedBuildingId === item.id);
                        return (
                          <div
                            key={item.id}
                            className={`${passiveOverlayPointerEvents} absolute`}
                            style={{
                              left: `${rectPct.left}%`,
                              top: `${rectPct.top}%`,
                              width: `${rectPct.width}%`,
                              height: `${rectPct.height}%`,
                              zIndex: hitZIndex,
                              scrollMarginBottom: "10rem",
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: "move",
                            }}
                            onMouseDown={(event) => {
                              if (drawingOwnsCanvasHits) return;
                              handleBuildingMouseDown(event, item, "move");
                            }}
                            onMouseEnter={() => {
                              if (drawingOwnsCanvasHits) return;
                              setHoveredObjectId(item.id);
                            }}
                            onMouseLeave={() => setHoveredObjectId(null)}
                          >
                            <div className="h-full w-full rounded-[8px] border border-dashed border-amber-400 bg-amber-200/10" />
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
                              const [x, y] = sitePointToPreviewPercent([pt.x, pt.y]);
                              return `${x},${y}`;
                            })
                            .join(" ");
                          const labelPoint = points[Math.floor(points.length / 2)] ?? path.from;
                          const [labelX, labelY] = sitePointToPreviewPercent([labelPoint.x, labelPoint.y]);
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
                {cadWindowSelect ? (
                  <div
                    data-testid="cad-window-select-marquee"
                    data-selection-mode={cadWindowSelect.currentX < cadWindowSelect.startX ? "crossing" : "window"}
                    className={`pointer-events-none absolute z-[65] rounded-sm border shadow-[0_0_0_1px_rgba(14,165,233,0.18)] ${
                      cadWindowSelect.currentX < cadWindowSelect.startX
                        ? "border-emerald-500 bg-emerald-400/12"
                        : "border-sky-500 bg-sky-400/12"
                    }`}
                    style={{
                      left: Math.min(cadWindowSelect.startX, cadWindowSelect.currentX) - cadWindowSelect.containerLeft,
                      top: Math.min(cadWindowSelect.startY, cadWindowSelect.currentY) - cadWindowSelect.containerTop,
                      width: Math.abs(cadWindowSelect.currentX - cadWindowSelect.startX),
                      height: Math.abs(cadWindowSelect.currentY - cadWindowSelect.startY),
                    }}
                  />
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
                        style={buildPreviewBoundsStyle(activeHighlightBounds)}
                      />
                    ) : null}
                    {issueHighlightBounds ? (
                      <div
                        className="absolute rounded-[12px] border border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_4px_rgba(244,63,94,0.1)]"
                        style={buildPreviewBoundsStyle(issueHighlightBounds)}
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
              <WaterFireFlowEvidenceDock
                waterFireFlow={waterFireFlow}
                onSelectScenario={setSelectedFireScenarioId}
              />
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
                  clearScheduledHoverAnnotationState(setFullscreenHoverPoint);
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
                        style={buildPreviewBoundsStyle(activeHighlightBounds)}
                      />
                    ) : null}
                    {issueHighlightBounds ? (
                      <div
                        className="absolute rounded-[12px] border border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_4px_rgba(244,63,94,0.1)]"
                        style={buildPreviewBoundsStyle(issueHighlightBounds)}
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
                    {visibleCadObjects
                      .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                      .map((item) => {
                        const rectPct = interactiveRectPercent(item, fullscreenMapRef.current);
                        if (!rectIntersectsPreview(rectPct)) return null;
                        const rotation = showMap ? 0 : (item.rotation ?? 0);
                        const isSite = item.type === "site";
                        const allowItemInteraction =
                          drawMode === "select" &&
                          (!isSite || (previewInteraction === "edit" && !siteLocked));
                        const hitZIndex = resolveObjectHitZIndex(item, rectPct, selectedBuildingId === item.id);
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
                              zIndex: hitZIndex,
                              scrollMarginBottom: "10rem",
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
                              className={`pointer-events-none h-full w-full rounded-[8px] border bg-slate-900/10 transition ${borderColor}`}
                              style={outlineColor ? { borderColor: outlineColor } : undefined}
                            />
                            <button
                              type="button"
                              className="absolute -right-3 -top-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                              onMouseDown={(event) => handleBuildingMouseDown(event, item, "rotate")}
                              onClick={(event) => {
                                event.stopPropagation();
                                setLastRectEdit({
                                  id: item.id,
                                  snapshot: { ...item },
                                  action: "update",
                                  ts: Date.now(),
                                });
                                const nextRotation = (((item.rotation ?? 0) + 15) % 360 + 360) % 360;
                                if (item.source === "detected_from_image") {
                                  onUpdateSuggested(item.id, { rotation: nextRotation });
                                } else {
                                  onUpdateBuilding(item.id, { rotation: nextRotation });
                                }
                              }}
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
                          const rectPct = interactiveRectPercent(item, fullscreenMapRef.current);
                          if (!rectIntersectsPreview(rectPct)) return null;
                          const rotation = showMap ? 0 : (item.rotation ?? 0);
                          const hitZIndex = resolveObjectHitZIndex(item, rectPct, selectedBuildingId === item.id);
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
                                zIndex: hitZIndex,
                                scrollMarginBottom: "10rem",
                                transform: `rotate(${rotation}deg)`,
                                transformOrigin: "center",
                                cursor: "pointer",
                              }}
                              onMouseEnter={() => {
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
