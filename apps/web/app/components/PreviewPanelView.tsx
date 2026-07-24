"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

import type { BuildingPlacement } from "../types";
import { CadPrecisionDock } from "./CadPrecisionDock";
import { Preview2DCanvasShell } from "./Preview2DCanvasShell";
import { Preview3DShell } from "./Preview3DShell";
import {
  boundsForSiteGeometry,
  resizeSiteGeometryFromOrigin,
  resolveCoordinateMode,
  screenToSitePoint as transformScreenToSitePoint,
  siteRectToPercent,
  siteToMapLngLat,
  siteTupleToPercent,
  translateSiteGeometry,
} from "../utils/geometryTransforms";
import {
  resolveCadSnap,
  type CadSnapKind,
} from "../utils/cadGeometryKernel";
import type { CadDimensionMode, CadSymbolKind, DrawMode } from "../utils/cadToolTypes";
import { measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import { PreviewCanvasControlStack } from "./PreviewCanvasControlStack";
import { PreviewGeneratedPlanFullscreen } from "./PreviewGeneratedPlanFullscreen";
import { UtilityCoordinationDock } from "./UtilityCoordinationDock";
import { usePreviewFocusTransform } from "./usePreviewFocusTransform";
import { usePreviewAnnotationHover } from "./usePreviewAnnotationHover";
import { usePreview2DShellHandlers } from "./usePreview2DShellHandlers";
import { usePreviewMapLayerSync } from "./usePreviewMapLayerSync";
import { usePreviewMapRuntime } from "./usePreviewMapRuntime";
import { usePreviewResizeObservers } from "./usePreviewResizeObservers";
import {
  usePreviewCadShortcutEffect,
  usePreviewCadToolRequestEffect,
} from "./usePreviewCadToolEffects";
import {
  clampValue,
  getPreviewCadLayer,
  getPreviewEditCapabilities,
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
import {
  buildPlanScaleBar,
  buildScaleTruthLabel,
} from "../utils/previewLayoutHelpers";
import {
  buildBalancedPreviewCanvasView,
  buildFocusedPreviewCanvasView,
} from "../utils/previewCanvasViewHelpers";
import { usePreviewObjectManagerModel } from "../utils/previewObjectManager";
import {
  buildPreviewAnnotationHoverDetails,
  buildPreviewObjectHoverDetails,
} from "../utils/previewHoverDetails";
import {
  buildPreviewOverlayBounds,
  countRenderedCanonicalPreviewObjects,
} from "../utils/previewOverlayBounds";
import {
  previewRectIntersectsViewport,
  resolvePreviewObjectHitZIndex,
} from "../utils/previewObjectLayering";
import {
  resolvePreviewPointerSitePoint,
} from "../utils/previewPointerGeometry";
import {
  buildPreviewMapAnchor,
  mapAnchoredRectPercent as resolveMapAnchoredRectPercent,
  mapLngLatToSitePoint,
  sitePointToPreviewPercent as resolveSitePointToPreviewPercent,
  siteRectPercent as resolveSiteRectPercent,
} from "../utils/previewMapProjection";
import {
  buildCadSegments,
  buildCanvasCompositionSignature,
  buildPreviewTopologyIssues,
  buildSelectedCadMetrics,
  buildVisibleCadObjects,
} from "../utils/previewCadDerivedObjects";

import {
  getCadCommandFirstValue,
  getCadCommandPointArgs,
  hasSelectedCadCommandArg,
  isKnownCadCommand,
  normalizeCadCommandKey,
  parseCadNumber,
} from "../utils/previewCadCommandParsing";
import {
  finishPreviewCadActiveCommand,
  handlePreviewActiveCanvasDrawInput,
  handlePreviewCadActiveCommandControl,
  handlePreviewCadArrangeMeasureCommand,
  handlePreviewCadActiveCommandInput,
  handlePreviewCadAnnotationSettingsCommand,
  handlePreviewCadGeometryCommand,
  handlePreviewCadModifyCommand,
  handlePreviewCadSelectionCommand,
  handlePreviewCadTransformCommand,
} from "../utils/previewCadActiveCommand";
import { resolvePreviewVisualKind } from "../utils/previewVisualStyles";
import type { PreviewSemanticLayer } from "../utils/previewSemanticLayers";
import {
  isPreviewSemanticLayerVisible,
  semanticLayerFor3DItem,
} from "../utils/previewSemanticLayers";
import {
  buildPreviewCurrentSiteSize,
  buildPreviewParkingAccessPoints,
  findPreviewHoveredObject,
  findPreviewSelectedObject,
  isAiRealismProviderConfigured,
  resolvePreviewSelectedDeletableObject,
} from "../utils/previewViewModel";
import { buildPreviewInteractionState } from "../utils/previewInteractionState";
import {
  AI_REALISM_WATERMARK,
  BALANCED_CANVAS_SCALE,
  type CadActiveCommand,
  formatCalmCadStatus,
  type CadCommandHistoryEntry,
  type CadHistoryEntry,
  type CadPoint,
  type PreviewPanelProps,
  type UtilityCoordinationRow,
} from "./previewPanelTypes";
import { useAiRealismPreview } from "./useAiRealismPreview";
import { usePreviewCadLineworkCommands } from "./usePreviewCadLineworkCommands";
import { usePreviewCadTransformCommands } from "./usePreviewCadTransformCommands";
import { usePreviewCadWindowSelection } from "./usePreviewCadWindowSelection";
import { usePreviewDraftGeometry } from "./usePreviewDraftGeometry";

const HIGH_QUALITY_DRAWING_VIEWPORT = {
  left: 1.2,
  top: 1.2,
  width: 82.6,
  height: 97.6,
};

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
  hasSourceBackedSurfaceEvidence,
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
  const [hoveredObjectId, setHoveredObjectId] = useState<string | null>(null);
  const [managedObjectId, setManagedObjectId] = useState<string | null>(null);
  const fullscreenContainerReady = false;
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
  const [cadActiveCommand, setCadActiveCommand] = useState<CadActiveCommand | null>(null);
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
  const [rotateDragActive, setRotateDragActive] = useState(false);
  const [rotateDragStart, setRotateDragStart] = useState<{ x: number; value: number } | null>(null);
  const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  const previewInteractionState = buildPreviewInteractionState({
    mapboxToken,
    geocode,
    buildingPlacementCount: buildingPlacements.length,
    suggestedPlacementCount: suggestedPlacements.length,
    surveyPointCount: surveyPoints?.length ?? 0,
    previewQuality,
    compactViewport,
    mapOverlayEnabled,
    previewMode,
    previewInteraction,
    drawMode,
    hasGeneratedPlan,
    placementMode,
    selectedBuildingId,
    planPreviewProjectId,
    currentProjectId,
    lotWidth,
    lotHeight,
    preview3DItemCount: preview3DEffectiveItems.length,
    planPreviewUrl,
    siteLocked,
    canDrawObjects,
    draggingBuildingActive: Boolean(draggingBuildingId && draggingMode),
    rotateDragActive: Boolean(rotateDragStart),
    canvasPanActive: Boolean(canvasPanStart),
    mapLocked,
  });
  const { mapAvailable, useLightHighQuality, showMap, showMap3D, mapPitch, allowMapInteraction, showGeneratedPlan, hasLiveObjects, canUse3D, showHover, allowEdits, showQuickDrawPalette, showMobileDrawToolbar, drawingOwnsCanvasHits, overlayPointerEvents, passiveOverlayPointerEvents } = previewInteractionState;
  const mapBearing = showMap3D ? (typeof siteRotationDeg === "number" ? siteRotationDeg : 0) : 0;
  const hasInteractiveLabels = previewLabels.length > 0 && showGeneratedPlan;
  const {
    hoveredAnnotation,
    setPinnedAnnotation,
    hoverPoint,
    setHoverPoint,
    fullscreenHoverPoint,
    setFullscreenHoverPoint,
    activeAnnotation,
    clearScheduledHoverAnnotationState,
    resolveHover,
  } = usePreviewAnnotationHover({
    labels: previewLabels,
    showHover,
    hasInteractiveLabels,
  });
  const {
    previewImageBounds,
    setPreviewImageBounds,
    fullscreenImageBounds,
    setFullscreenImageBounds,
    previewContainerBounds,
    updateImageBounds,
    updateContainerBounds,
  } = usePreviewResizeObservers({
    previewRef,
    previewImageRef,
    fullscreenRef,
    fullscreenImageRef,
    mapRef,
    fullscreenMapRef,
    lastMapResizeRef,
    showMap,
    showGeneratedPlan,
    planPreviewUrl,
    previewMode,
    previewFullscreenOpen,
  });
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
    () => buildPreviewCurrentSiteSize(lotWidth, lotHeight),
    [lotHeight, lotWidth],
  );
  const isHighQuality = previewQuality === "high";
  const aiRealismProviderConfigured = useMemo(() => isAiRealismProviderConfigured(), []);
  const planScaleBar = useMemo(() => buildPlanScaleBar(currentSiteSize), [currentSiteSize]);
  const scaleTruthLabel = useMemo(
    () => buildScaleTruthLabel({ geocode, mapScaleFtPerPx, mapScaleSource }),
    [geocode, mapScaleFtPerPx, mapScaleSource],
  );
  const resolveVisualKind = useCallback(resolvePreviewVisualKind, []);
  const hoveredObject = useMemo(
    () => findPreviewHoveredObject({ hoveredObjectId, buildingPlacements, cadEntityPreviewObjects, suggestedPlacements }),
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
  const selectedObject = useMemo(
    () =>
      findPreviewSelectedObject({
        selectedBuildingId,
        managedObjectId,
        hoveredObjectId,
        selectedObjectIds,
        cadSelectionSet,
        buildingPlacements,
        cadEntityPreviewObjects,
        suggestedPlacements,
      }),
    [buildingPlacements, cadEntityPreviewObjects, cadSelectionSet, hoveredObjectId, managedObjectId, selectedBuildingId, selectedObjectIds, suggestedPlacements],
  );
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
  const selectedDeletableObject = resolvePreviewSelectedDeletableObject({ selectedObject, buildingPlacements });
  const showEarthworkUx =
    previewMode === "2d" &&
    Boolean(gradingEarthworkUx) &&
    (hasGradingSurface || systemStatuses.grading === "fresh");
  const accessPointsForParking = useMemo(
    () => buildPreviewParkingAccessPoints(buildingPlacements),
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
      if (!containerRef.current) return null;
      const rect = containerRef.current.getBoundingClientRect();
      return resolvePreviewPointerSitePoint({
        clientX,
        clientY,
        containerRect: rect,
        bounds,
        drawMode,
        drawingLotWidth,
        drawingLotHeight,
        lotWidth,
        lotHeight,
        canvasView,
      });
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
    },
    [],
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

  const {
    cadLayerOptions,
    getPreviewObjectActionBlocker,
    objectManagerCounts,
    objectManagerRows,
    previewObjectEditableSource,
  } = usePreviewObjectManagerModel({
    buildingPlacements,
    cadEntityPreviewObjects,
    hiddenCadLayers,
    suggestedPlacements,
  });
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
    () => buildVisibleCadObjects({
      buildingPlacements,
      cadEntityPreviewObjects,
      hiddenCadLayers,
      getCadLayer,
    }),
    [buildingPlacements, cadEntityPreviewObjects, getCadLayer, hiddenCadLayers],
  );
  const cadReferenceMode = useMemo(
    () =>
      visibleCadObjects.some(
        (item) =>
          item.meta?.cad_reference_recreation ||
          item.meta?.dense_subdivision_cad_plan ||
          item.meta?.subdivision_cad_recreation,
      ),
    [visibleCadObjects],
  );
  const [semanticLayerVisibility, setSemanticLayerVisibility] = useState<Partial<Record<PreviewSemanticLayer, boolean>>>({});
  const toggleSemanticLayer = useCallback((layer: PreviewSemanticLayer) => {
    setSemanticLayerVisibility((current) => ({
      ...current,
      [layer]: current[layer] === false,
    }));
  }, []);
  const showAllSemanticLayers = useCallback(() => {
    setSemanticLayerVisibility({});
  }, []);
  const filteredPreview3DItems = useMemo(
    () =>
      preview3DEffectiveItems.filter((item) =>
        isPreviewSemanticLayerVisible(semanticLayerFor3DItem(item), semanticLayerVisibility),
      ),
    [preview3DEffectiveItems, semanticLayerVisibility],
  );

  const canvasCompositionSignature = useMemo(
    () => buildCanvasCompositionSignature(visibleCadObjects),
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

  const cadSegments = useMemo(
    () => buildCadSegments({ visibleCadObjects, suggestedPlacements, getObjectGeometryPoints }),
    [getObjectGeometryPoints, suggestedPlacements, visibleCadObjects],
  );

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
  const selectedCadMetrics = useMemo(
    () => buildSelectedCadMetrics({ selectedCadObject, getObjectGeometryPoints, getCadLayer }),
    [getCadLayer, getObjectGeometryPoints, selectedCadObject],
  );
  const topologyIssues = useMemo(
    () => buildPreviewTopologyIssues(visibleCadObjects),
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
  const { beginCadWindowSelect, finishCadWindowSelect } = usePreviewCadWindowSelection({
    previewRef,
    cadWindowSelect,
    cadWindowSelectRef,
    setCadWindowSelect,
    visibleCadObjects,
    allowEdits,
    drawMode,
    placementMode,
    suppressNextObjectClickRef,
    onSelectBuilding,
    onSelectObjects,
    setCadSelectionSet,
    setSelectedVertex,
    pushCadCommandFeedback,
  });

  const {
    alignOrDistributeSelectedCadObjects,
    arraySelectedCadObject,
    copySelectedCadObjectsByVector,
    createCadCommandGeometry,
    moveSelectedCadObjectsByVector,
    transformSelectedCadObjects,
  } = usePreviewCadTransformCommands({
    buildingPlacements,
    canDrawObjects,
    cadTransformValue,
    selectedCadIds,
    selectedCadObject,
    getCadLayer,
    getObjectGeometryPoints,
    onCreateCustomGeometry,
    pushCadCommandFeedback,
    updateCadObject,
  });
  const {
    changeSelectedPolylineState,
    filletSelectedCadObject,
    joinSelectedCadObjects,
    offsetSelectedCadObject,
    offsetSelectedCadObjectBy,
    splitSelectedJoinedObject,
    toggleSelectedCadHatch,
    trimExtendSelectedCadObject,
  } = usePreviewCadLineworkCommands({
    buildingPlacements,
    cadFilletRadius,
    cadOffsetDistance,
    cadSegments,
    cadTransformValue,
    lotHeight,
    lotWidth,
    selectedCadIds,
    selectedCadObject,
    selectedVertex,
    getCadLayer,
    onCreateCustomGeometry,
    onRemoveBuilding,
    onSelectBuilding,
    onSelectObjects,
    onUpdateBuilding,
    previewObjectEditableSource,
    pushCadCommandFeedback,
    resolveVisualKind,
    setCadCommandStatus,
    setCadSelectionSet,
    updateCadObject,
  });
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

  const finishCadActiveCommand = useCallback(() => {
    return finishPreviewCadActiveCommand({
      cadActiveCommand,
      draftPoints,
      offsetSelectedCadObjectBy,
      trimExtendSelectedCadObject,
      moveSelectedCadObjectsByVector,
      copySelectedCadObjectsByVector,
      transformSelectedCadObjects,
      createCadCommandGeometry,
      setDraftPoints,
      setDraftPreviewPoint,
      setCadActiveCommand,
      setDrawMode,
      setCadCommandDraft,
      pushCadCommandFeedback,
    });
  }, [
    cadActiveCommand,
    copySelectedCadObjectsByVector,
    createCadCommandGeometry,
    draftPoints,
    moveSelectedCadObjectsByVector,
    offsetSelectedCadObjectBy,
    pushCadCommandFeedback,
    transformSelectedCadObjects,
    trimExtendSelectedCadObject,
  ]);

  const runCadCommand = useCallback((commandOverride?: string) => {
    const raw = (commandOverride ?? cadCommandDraft).trim();
    if (!raw) {
      finishCadActiveCommand();
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
      handlePreviewActiveCanvasDrawInput({
        raw,
        drawMode,
        draftPoints,
        draftPreviewPoint,
        setDraftPoints,
        setDraftPreviewPoint,
        setCadCommandDraft,
        pushCadCommandFeedback,
      });
      return;
    }

    if (handlePreviewCadSelectionCommand({
      commandKey,
      args,
      buildingPlacements,
      selectedCadIds,
      setCadSelectionSet,
      onSelectObjects,
      onSelectBuilding,
      setSelectedVertex,
      pushCadCommandFeedback,
    })) {
      return;
    }

    if (cadActiveCommand && !isKnownCadCommand(commandKey)) {
      handlePreviewCadActiveCommandInput({
        cadActiveCommand,
        raw,
        tokens,
        selectedCadObject,
        selectedCadIds,
        draftPoints,
        setCadOffsetDistance,
        setCadTransformValue,
        setCadActiveCommand,
        setCadCommandDraft,
        setDraftPoints,
        setDraftPreviewPoint,
        setDrawMode,
        offsetSelectedCadObjectBy,
        trimExtendSelectedCadObject,
        moveSelectedCadObjectsByVector,
        copySelectedCadObjectsByVector,
        transformSelectedCadObjects,
        createCadCommandGeometry,
        pushCadCommandFeedback,
      });
      return;
    }

    if (handlePreviewCadActiveCommandControl({
      commandKey,
      cadActiveCommand,
      finishCadActiveCommand,
      setDraftPoints,
      setDraftPreviewPoint,
      setCadActiveCommand,
      setDrawMode,
      setCadCommandDraft,
      pushCadCommandFeedback,
    })) {
      return;
    }

    if (handlePreviewCadGeometryCommand({
      commandKey,
      args,
      pointArgs,
      setDraftPoints,
      setDraftPreviewPoint,
      setCadActiveCommand,
      setDrawMode,
      onSetPreviewInteraction,
      createCadCommandGeometry,
      pushCadCommandFeedback,
    })) {
      return;
    }
    if (handlePreviewCadArrangeMeasureCommand({
      commandKey,
      args,
      pointArgs,
      selectedCadObject,
      selectedCadMetrics,
      visibleCadObjects,
      getObjectGeometryPoints,
      arraySelectedCadObject,
      alignOrDistributeSelectedCadObjects,
      pushCadCommandFeedback,
    })) {
      return;
    }
    if (handlePreviewCadTransformCommand({
      commandKey,
      args,
      firstValue,
      selectedRequested,
      setCadActiveCommand,
      setCadCommandDraft,
      setCadTransformValue,
      moveSelectedCadObjectsByVector,
      copySelectedCadObjectsByVector,
      transformSelectedCadObjects,
      pushCadCommandFeedback,
    })) {
      return;
    }
    if (handlePreviewCadModifyCommand({
      commandKey,
      args,
      firstValue,
      selectedDeletableObject,
      setCadOffsetDistance,
      setCadTransformValue,
      setCadFilletRadius,
      setCadActiveCommand,
      setCadCommandDraft,
      onRemoveBuilding,
      offsetSelectedCadObjectBy,
      trimExtendSelectedCadObject,
      filletSelectedCadObject,
      joinSelectedCadObjects,
      splitSelectedJoinedObject,
      changeSelectedPolylineState,
      toggleSelectedCadHatch,
      applySelectedCadDimension,
      pushCadCommandFeedback,
    })) {
      return;
    }
    if (handlePreviewCadAnnotationSettingsCommand({
      commandKey,
      args,
      pointArgs,
      selectedCadIds,
      buildingPlacements,
      cadLayerOptions,
      cadSnapEnabled,
      cadOrthoEnabled,
      setHiddenCadLayers,
      setCadLayerDraft,
      setCadSnapEnabled,
      setCadOrthoEnabled,
      createCadCommandGeometry,
      updateCadObject,
      pushCadCommandFeedback,
    })) {
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
    finishCadActiveCommand,
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

  usePreviewCadToolRequestEffect({
    cadToolRequest,
    lotWidth,
    lotHeight,
    cadOffsetDistance,
    selectedDeletableObject,
    setDraftPoints,
    setDraftPreviewPoint,
    setDrawAutoFinishPointCount,
    setCadActiveCommand,
    setCadCommandDraft,
    setDrawMode,
    setManagedObjectId,
    setHoveredObjectId,
    setSelectedVertex,
    setCadSelectionSet,
    setCadSnapEnabled,
    setCadOrthoEnabled,
    onSelectBuilding,
    onSetPreviewMode,
    onSetPreviewInteraction,
    onRemoveBuilding,
    transformSelectedCadObjects,
    offsetSelectedCadObjectBy,
    trimExtendSelectedCadObject,
    filletSelectedCadObject,
    joinSelectedCadObjects,
    splitSelectedJoinedObject,
    changeSelectedPolylineState,
    toggleSelectedCadHatch,
    applySelectedCadDimension,
    insertCadSymbol,
    applySelectedCadLayer,
    applyCadProperties,
    undoCadCommand,
    redoCadCommand,
    runCadCommand,
    pushCadCommandFeedback,
  });

  usePreviewCadShortcutEffect({
    canDrawObjects,
    selectedCadCount: selectedCadIds.length,
    setDraftPoints,
    setDraftPreviewPoint,
    setDrawMode,
    setCadSnapEnabled,
    setCadOrthoEnabled,
    onSetPreviewInteraction,
    moveSelectedCadObjectsByVector,
    transformSelectedCadObjects,
    undoCadCommand,
    redoCadCommand,
  });

  const {
    activeDrawToolDetail,
    activeDrawToolLabel,
    activateDrawTool,
    canFinishDraftGeometry,
    clearDraftGeometry,
    draftPointCount,
    draftPrecisionReadout,
    drawModeButtons,
    finishDraftBlockedReason,
    finishDraftGeometry,
    handleDrawPointer,
  } = usePreviewDraftGeometry({
    draftPoints,
    setDraftPoints,
    draftPointsRef,
    draftPreviewPoint,
    setDraftPreviewPoint,
    lastDraftPreviewPointRef,
    drawMode,
    setDrawMode,
    drawAutoFinishPointCount,
    setDrawAutoFinishPointCount,
    setCadActiveCommand,
    setCadCommandStatus,
    pushCadCommandFeedback,
    cursorSitePoint,
    siteDrawRequest,
    lastSiteDrawRequestRef,
    siteLocked,
    onSetPreviewInteraction,
    onCreateCustomGeometry,
    onCreateSiteBoundary,
    previewRef,
    userAdjustedCanvasViewRef,
    canvasPanStartedAtRef,
    setCanvasPanStart,
    canvasView,
    canDrawObjects,
    screenToSitePoint,
    resolveCadSnapPoint,
    setActiveSnapPoint,
    drawObjectsDisabledLabel,
    onSelectBuilding,
    setManagedObjectId,
    setHoveredObjectId,
    setSelectedVertex,
    setCadSelectionSet,
    externalRectUndo,
    setLastRectEdit,
    lastPolylineEdit,
    lastRectEdit,
    applyPolylineUndo,
    applyRectUndo,
    selectedBuildingId,
    selectedVertex,
    buildingPlacements,
    onRemoveBuilding,
  });

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

  const hoverDetails = useMemo(
    () => buildPreviewAnnotationHoverDetails(activeAnnotation),
    [activeAnnotation],
  );
  const objectHoverDetails = useMemo(
    () => buildPreviewObjectHoverDetails({ hoveredObject, lotHeight, lotWidth }),
    [hoveredObject, lotHeight, lotWidth],
  );
  const renderedCanonicalCount = useMemo(
    () => countRenderedCanonicalPreviewObjects(buildingPlacements),
    [buildingPlacements],
  );

  const overlayBoundsResolved = useMemo(
    () => buildPreviewOverlayBounds(previewContainerBounds),
    [previewContainerBounds],
  );

  useEffect(() => {
    if (showHover) return;
    const handle = window.requestAnimationFrame(() => {
      setHoveredObjectId(null);
      clearScheduledHoverAnnotationState(setHoverPoint);
      setHoveredVertex(null);
      setHoveredSegment(null);
    });
    return () => window.cancelAnimationFrame(handle);
  }, [clearScheduledHoverAnnotationState, setHoverPoint, showHover]);

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

  const mapAnchor = useMemo(
    () => buildPreviewMapAnchor({ geocode, lotWidth, lotHeight, siteRotationDeg }),
    [geocode, lotHeight, lotWidth, siteRotationDeg],
  );
  const coordinateMode = resolveCoordinateMode(mapAnchor);
  const sheetDrawingViewport = isHighQuality && !showMap ? HIGH_QUALITY_DRAWING_VIEWPORT : null;
  const mapPointIntoSheetViewport = useCallback(
    (point: [number, number]): [number, number] => {
      if (!sheetDrawingViewport) return point;
      return [
        sheetDrawingViewport.left + (point[0] / 100) * sheetDrawingViewport.width,
        sheetDrawingViewport.top + (point[1] / 100) * sheetDrawingViewport.height,
      ];
    },
    [sheetDrawingViewport],
  );
  const mapRectIntoSheetViewport = useCallback(
    (rect: { left: number; top: number; width: number; height: number }) => {
      if (!sheetDrawingViewport) return rect;
      return {
        left: sheetDrawingViewport.left + (rect.left / 100) * sheetDrawingViewport.width,
        top: sheetDrawingViewport.top + (rect.top / 100) * sheetDrawingViewport.height,
        width: (rect.width / 100) * sheetDrawingViewport.width,
        height: (rect.height / 100) * sheetDrawingViewport.height,
      };
    },
    [sheetDrawingViewport],
  );

  const siteToLatLng = useCallback(
    (xFt: number, yFt: number) => {
      return mapAnchor ? siteToMapLngLat({ x: xFt, y: yFt }, mapAnchor) : null;
    },
    [mapAnchor],
  );

  const latLngToSite = useCallback(
    (lat: number, lng: number) => {
      return mapLngLatToSitePoint(lat, lng, mapAnchor);
    },
    [mapAnchor],
  );

  const sitePointToPreviewPercent = useCallback(
    (point: [number, number], targetMap: mapboxgl.Map | null = mapRef.current): [number, number] => {
      return mapPointIntoSheetViewport(resolveSitePointToPreviewPercent({ point, targetMap, showMap, mapAnchor, currentSiteSize }));
    },
    [currentSiteSize, mapAnchor, mapPointIntoSheetViewport, showMap],
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
      return mapRectIntoSheetViewport(resolveSiteRectPercent(item, currentSiteSize));
    },
    [currentSiteSize, mapRectIntoSheetViewport],
  );
  const mapAnchoredRectPercent = useCallback(
    (item: BuildingPlacement, targetMap: mapboxgl.Map | null) => {
      return mapRectIntoSheetViewport(resolveMapAnchoredRectPercent({ item, targetMap, showMap, mapAnchor, currentSiteSize }));
    },
    [currentSiteSize, mapAnchor, mapRectIntoSheetViewport, showMap],
  );
  const drawingSiteTupleToPercent = useCallback(
    (point: [number, number], siteSize: { width: number; height: number }) => {
      return mapPointIntoSheetViewport(siteTupleToPercent(point, siteSize));
    },
    [mapPointIntoSheetViewport],
  );
  const drawingSiteRectToPercent = useCallback(
    (rect: { x: number; y: number; width: number; height: number }, siteSize: { width: number; height: number }) => {
      return mapRectIntoSheetViewport(siteRectToPercent(rect, siteSize));
    },
    [mapRectIntoSheetViewport],
  );
  const resolveObjectHitZIndex = useCallback(
    (
      item: BuildingPlacement,
      rectPct: { left: number; top: number; width: number; height: number },
      selected = false,
    ) => {
      const visualKind = resolveVisualKind(item);
      return resolvePreviewObjectHitZIndex({ item, rectPct, visualKind, selected });
    },
    [resolveVisualKind],
  );
  const rectIntersectsPreview = useCallback(previewRectIntersectsViewport, []);
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
    geocodeLat: geocode?.lat,
    geocodeLng: geocode?.lng,
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
  const preview2DShellHandlers = usePreview2DShellHandlers({
    allowMapInteraction,
    drawMode,
    overlayBoundsResolved,
    previewRef,
    previewContainerBounds,
    previewMode,
    showMap,
    lotWidth,
    lotHeight,
    draftPoints,
    canvasView,
    placementMode,
    showHover,
    hoverPoint,
    hoveredAnnotation,
    hoveredObjectId,
    cadWindowSelect,
    cadWindowSelectRef,
    rotateDragStart,
    canvasPanStart,
    suppressNextDrawClickRef,
    suppressNextObjectClickRef,
    userAdjustedCanvasViewRef,
    onSetSiteRotationDeg,
    handleDrawPointer,
    beginCadWindowSelect,
    finishCadWindowSelect,
    onPlaceObject,
    screenToSitePoint,
    resolveCadSnapPoint,
    scheduleDraftPointerState,
    scheduleCanvasPanView,
    updateDraggedBuilding,
    resolveHover,
    resolvePlacement,
    clearScheduledHoverAnnotationState,
    scheduleCursorSitePoint,
    finishCanvasPanInteraction,
    clearScheduledPointerState,
    finishDraftGeometry,
    setHoverPoint,
    setHoveredObjectId,
    setCadWindowSelect,
    setRotateDragStart,
    setCanvasPanStart,
    setDraggingBuildingId,
    setDraggingMode,
    setPinnedAnnotation,
    setCanvasView,
  });
  return (
    <div className="civora-preview-panel flex h-full min-w-0 flex-col overflow-x-hidden overflow-y-auto rounded-xl border border-slate-200 bg-white/92 p-2 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.45)] backdrop-blur sm:p-3">
      <div className="civora-preview-canvas-container flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] sm:p-3">
          <PreviewCanvasControlStack
            previewMode={previewMode}
            allowEdits={allowEdits}
            drawMode={drawMode}
            selectedObjectPresent={Boolean(selectedObject)}
            showDesktopDrawTools={previewInteraction === "edit" && !showMobileDrawToolbar && !showQuickDrawPalette}
            headerProps={{
              previewMode,
              previewQuality,
              coordinateMode,
              canUse3D,
              mapAvailable,
              mapOverlayEnabled,
              mapLocked,
              showMap,
              allowEdits,
              drawMode,
              siteLocked,
              canDrawObjects,
              drawObjectsDisabledLabel,
              showDrawTools: previewInteraction === "edit" && !showMobileDrawToolbar && !showQuickDrawPalette,
              isHighQuality,
              aiRealismEnabled,
              useLightHighQuality,
              busy,
              analysisHighlight,
              semanticLayerVisibility,
              onSetPreviewQuality,
              onSetPreviewMode,
              onSetAiVisualizationOff: setAiVisualizationOff,
              onSetAiVisualizationOn: setAiVisualizationOn,
              onSetPreviewInteraction,
              onSetMapOverlayEnabled: setMapOverlayEnabled,
              onSetMapLocked: setMapLocked,
              onActivateDrawTool: activateDrawTool,
              onPushCadCommandFeedback: pushCadCommandFeedback,
              onUnlockSite,
              onClearDraftGeometry: clearDraftGeometry,
              onSetDrawMode: setDrawMode,
              onSetFocusTransform: setFocusTransform,
              onResetView,
              onRefreshPreview,
              onClearHighlights,
              onToggleSemanticLayer: toggleSemanticLayer,
              onShowAllSemanticLayers: showAllSemanticLayers,
            }}
            objectManagerProps={{
              visible: allowEdits && drawMode === "select" && Boolean(selectedObject),
              selectedObject,
              selectedBuildingId,
              objectManagerRows,
              objectManagerCounts,
              selectedCadIds,
              onSetManagedObjectId: setManagedObjectId,
              onSelectBuilding,
              onSetCadSelectionSet: setCadSelectionSet,
              onClearSelectedVertex: () => setSelectedVertex(null),
              onSetCadCommandStatus: setCadCommandStatus,
              onUpdatePreviewManagedObject: updatePreviewManagedObject,
              onFocusPreviewManagedObject: focusPreviewManagedObject,
              onRemoveBuilding,
              onSetLastRectEdit: setLastRectEdit,
              getPreviewObjectActionBlocker,
              getPreviewObjectDimensionsLabel,
              getPreviewObjectSourceLabel,
              getPreviewObjectStatusLabel,
              getCadLayer,
            }}
            stableDrawToolbarProps={{
              drawMode,
              siteLocked: Boolean(siteLocked),
              hasDrawableSiteSize,
              canDrawObjects,
              drawObjectsDisabledLabel,
              onUnlockSite,
              onLockSite,
              onClearDraftGeometry: clearDraftGeometry,
              onSetDrawMode: setDrawMode,
              onSetPreviewInteraction,
              onActivateDrawTool: activateDrawTool,
              onPushCadCommandFeedback: pushCadCommandFeedback,
            }}
            activeDrawHudProps={{
              drawMode,
              activeDrawToolLabel,
              activeDrawToolDetail,
              draftPointCount: draftPoints.length,
              siteLocked: Boolean(siteLocked),
              canDrawObjects,
              drawObjectsDisabledLabel,
              cursorSitePoint,
              canvasScale: canvasView.scale,
              lastCommandLabel: cadHistory.at(-1)?.label,
              canFinishDraftGeometry,
              finishDraftBlockedReason,
              onFinishDraftGeometry: finishDraftGeometry,
              onCancelDraw: () => {
                clearDraftGeometry();
                setDrawMode("select");
                setActiveSnapPoint(null);
                setCadCommandStatus("Cancelled active drawing tool.");
              },
            }}
          />
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
              items={filteredPreview3DItems}
              allowEdits={allowEdits}
              previewQuality={previewQuality}
              selectedItemId={selectedBuildingId}
              hasTerrainSource={hasTerrainSource}
              hasGradingSurface={hasGradingSurface}
              usingAnnotation3D={usingAnnotation3D}
              onSelectItem={onSelectBuilding}
              onOpenFullscreen={onOpenFullscreen}
            />
          ) : (
            <Preview2DCanvasShell
              previewRef={previewRef}
              previewFullscreenOpen={previewFullscreenOpen}
              showMap={showMap}
              placementMode={placementMode}
              allowEdits={allowEdits}
              drawMode={drawMode}
              shellHandlers={preview2DShellHandlers}
              quickDrawPaletteProps={{
                visible: previewMode === "2d" && showQuickDrawPalette,
                drawMode,
                siteLocked: Boolean(siteLocked),
                hasDrawableSiteSize,
                canDrawObjects,
                drawObjectsDisabledLabel,
                canFinishDraftGeometry,
                finishDraftBlockedReason,
                onActivateDrawTool: activateDrawTool,
                onFinishDraftGeometry: finishDraftGeometry,
                onCancelDraw: () => {
                  clearDraftGeometry();
                  setDrawMode("select");
                  setActiveSnapPoint(null);
                  setCadCommandStatus("Cancelled active drawing tool.");
                },
                onUnlockSite,
                onLockSite,
                onClearDraftGeometry: clearDraftGeometry,
                onSetDrawMode: setDrawMode,
                onSetPreviewInteraction,
                onPushCadCommandFeedback: pushCadCommandFeedback,
              }}
              aiRealismPreviewOverlayProps={
                isHighQuality && aiRealismEnabled
                  ? {
                      artifact: aiRealismDisplayArtifact,
                      blocker: aiRealismBlocker,
                      stale: Boolean(aiRealismDisplayArtifact?.stale),
                      hasTerrainSource,
                      watermark: AI_REALISM_WATERMARK,
                      onRegenerate: generateAiRealismArtifact,
                    }
                  : undefined
              }
              mobileDrawToolbarProps={
                showMobileDrawToolbar
                  ? {
                      drawModeButtons,
                      drawMode,
                      compactViewport,
                      canFinishDraftGeometry,
                      finishDraftBlockedReason,
                      selectedDeletable: Boolean(selectedDeletableObject),
                      siteLocked: Boolean(siteLocked),
                      onActivateTool: (mode, blockedMessage) => {
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
                      },
                      onFinish: finishDraftGeometry,
                      onCancel: () => {
                        clearDraftGeometry();
                        setDrawMode("select");
                        setActiveSnapPoint(null);
                        setCadCommandStatus("Cancelled active drawing tool.");
                      },
                      onChangeSite: onUnlockSite
                        ? () => {
                            onUnlockSite();
                            clearDraftGeometry();
                            setDrawMode("select");
                            onSetPreviewInteraction("edit");
                          }
                        : undefined,
                      onResetView: resetCanvasView,
                      onDeleteSelected: () => {
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
                      },
                    }
                  : undefined
              }
              surfaceProps={{
                mapContainerRef,
                showMap,
                previewMode,
                showGeneratedPlan,
                planPreviewUrl,
                hasLiveObjects,
                placementMode,
                allowEdits,
                overlayBoundsResolved: Boolean(overlayBoundsResolved),
                cadWindowSelect,
                previewImageRef,
                previewRef,
                setPreviewImageBounds,
                updateImageBounds,
                onMouseDown: (event) => {
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
                },
                mapStatusOverlayProps: {
                  debugEnabled: Boolean(debugStats?.enabled),
                  geocode,
                  showMap,
                  previewQuality,
                  previewMode,
                  mapLoaded,
                  mapboxRequestCount,
                  mapboxTileCount,
                  mapContainerSize,
                  mapCanvasSize,
                  mapError,
                  showMap3D,
                  siteRotationDeg,
                },
                canvasHudProps: {
                  scaleLengthFt: planScaleBar.lengthFt,
                  zoomScale: canvasView.scale,
                  lotWidth,
                  lotHeight,
                  scaleTruthLabel,
                  cursorSitePoint,
                  draftPrecisionReadout,
                  activeDrawToolLabel,
                  activeSnapKind: activeSnapPoint?.kind,
                  onZoomIn: () => {
                    userAdjustedCanvasViewRef.current = true;
                    setCanvasView((prev) => ({ ...prev, scale: Math.min(prev.scale + 0.15, 4) }));
                  },
                  onZoomOut: () => {
                    userAdjustedCanvasViewRef.current = true;
                    setCanvasView((prev) => ({ ...prev, scale: Math.max(prev.scale - 0.15, 0.55) }));
                  },
                  onResetView: resetCanvasView,
                },
                overlayStackProps: {
                  drawMode,
                  draftPointCount,
                  overlayPointerEvents,
                  viewportTransformStyle,
                  focusTransform,
                  showMap,
                  mapLocked,
                  previewInteraction,
                  placementMode,
                  mapRef,
                  mapDragActiveRef,
                  mapDragRef,
                  analysisFocusLocked,
                  onClearHighlights,
                  beginCadWindowSelect,
                  planCanvasLayersProps: {
                    overlayBoundsResolved,
                    previewMode,
                    siteLocked: Boolean(siteLocked),
                    showSiteBounds,
                    drawMode,
                    legendPalette,
                    viewportTransformStyle,
                    buildingPlacements,
                    suggestedPlacements,
                    surveyPointCount: surveyPoints?.length ?? 0,
                    surveyPoints,
                    hasTerrainSurfaceEvidence: Boolean(hasSourceBackedSurfaceEvidence && hasGradingSurface),
                    showMap,
                    isHighQuality,
                    cadReferenceMode,
                    lotWidth,
                    lotHeight,
                    planScaleBar,
                    visibleCadObjects,
                    selectedBuildingId,
                    currentSiteSize,
                    sitePointToSvgPercent,
                    mapAnchoredRectPercent: (item) => mapAnchoredRectPercent(item, mapRef.current),
                    shouldRevealObjectLabel,
                    getObjectGeometryPoints,
                    accessPointsForParking,
                    showParkingAnalysis,
                    waterFireFlow,
                    previewQuality,
                    sitePointToPreviewPercent,
                    activeSnapPoint,
                    draftPoints,
                    draftPreviewPoint,
                    drawingLotWidth,
                    drawingLotHeight,
                    siteTupleToPercent: drawingSiteTupleToPercent,
                    siteRectToPercent: drawingSiteRectToPercent,
                    showEarthworkUx,
                    gradingEarthworkUx,
                    semanticLayerVisibility,
                  },
                  waterFireFlowHitTargetsProps: {
                    waterFireFlow,
                    passiveOverlayPointerEvents,
                    sitePointToPreviewPercent,
                    setSelectedFireScenarioId,
                  },
                  editableObjectHitTargetsProps: {
                    visibleCadObjects,
                    previewInteraction,
                    siteLocked: Boolean(siteLocked),
                    showSiteBounds,
                    showMap,
                    drawMode,
                    selectedBuildingId,
                    analysisHighlight,
                    previewQuality,
                    isHighQuality,
                    allowEdits,
                    passiveOverlayPointerEvents,
                    drawingOwnsCanvasHits,
                    draggingMode,
                    draggingVertex,
                    hoveredVertex,
                    selectedVertex,
                    hoveredSegment,
                    lastPolylineEdit,
                    lastRectEdit,
                    polylineInsertHintDismissed,
                    polylineSegmentRef,
                    hoveredObjectId,
                    objectHoverDetails,
                    selectedDeletableObject,
                    cadCommandStatusDisplay,
                    suppressNextObjectClickRef,
                    getEditCapabilities,
                    interactiveRectPercent: (item) => interactiveRectPercent(item, mapRef.current),
                    rectIntersectsPreview,
                    resolveObjectHitZIndex,
                    shouldRevealObjectLabel,
                    handleBuildingMouseDown,
                    onSelectBuilding,
                    setSelectedVertex,
                    setHoveredObjectId,
                    setHoveredVertex,
                    setHoveredSegment,
                    setLastPolylineEdit,
                    setLastRectEdit,
                    setDraggingBuildingId,
                    setDraggingMode,
                    setDraggingVertex,
                    runCadCommand,
                    copySelectedCadObjectsByVector,
                    transformSelectedCadObjects,
                    pushCadCommandFeedback,
                    onRemoveBuilding,
                    onUpdateSuggested,
                    onUpdateBuilding,
                    insertVertexOnSegment,
                    applyPolylineUndo,
                    deleteSelectedVertex,
                    applyRectUndo,
                  },
                  suggestedObjectHitTargetsProps: {
                    suggestedPlacements,
                    passiveOverlayPointerEvents,
                    drawingOwnsCanvasHits,
                    hoveredObjectId,
                    objectHoverDetails,
                    mapAnchoredRectPercent: (item) => interactiveRectPercent(item, mapRef.current),
                    rectIntersectsPreview,
                    resolveObjectHitZIndex,
                    selectedBuildingId,
                    showMap,
                    handleBuildingMouseDown,
                    setHoveredObjectId,
                  },
                  analysisPathsOverlayProps: {
                    analysisPaths,
                    analysisHighlight,
                    sitePointToPreviewPercent,
                  },
                },
                planAnnotationOverlayProps:
                  showGeneratedPlan && planPreviewAnnotations?.labels?.length && previewImageBounds
                    ? {
                        imageBounds: previewImageBounds,
                        labels: planPreviewAnnotations.labels,
                        selectedIssueLabel,
                        showHover,
                        activeHighlightBounds,
                        issueHighlightBounds,
                      }
                    : undefined,
              }}
              annotationHoverCardProps={
                showHover && activeAnnotation && hoverPoint
                  ? {
                      annotation: activeAnnotation,
                      details: hoverDetails,
                      point: hoverPoint,
                      maxLeft: 520,
                      maxTop: 420,
                    }
                  : undefined
              }
              waterFireFlowEvidenceDockProps={{
                waterFireFlow,
                onSelectScenario: setSelectedFireScenarioId,
              }}
              fullscreenHeaderProps={
                previewFullscreenOpen && showMap
                  ? {
                      description: "Inspect the live map without rebuilding the preview.",
                      onClose: onCloseFullscreen,
                    }
                  : undefined
              }
            />
          )}
        </div>

      <PreviewGeneratedPlanFullscreen
        open={previewFullscreenOpen && !showMap}
        planPreviewUrl={planPreviewUrl}
        fullscreenRef={fullscreenRef}
        fullscreenImageRef={fullscreenImageRef}
        fullscreenImageBounds={fullscreenImageBounds}
        setFullscreenImageBounds={setFullscreenImageBounds}
        updateImageBounds={updateImageBounds}
        onCloseFullscreen={onCloseFullscreen}
        onPlaceObject={onPlaceObject}
        updateDraggedBuilding={updateDraggedBuilding}
        resolveHover={resolveHover}
        clearScheduledHoverAnnotationState={clearScheduledHoverAnnotationState}
        setFullscreenHoverPoint={setFullscreenHoverPoint}
        setDraggingBuildingId={setDraggingBuildingId}
        setDraggingMode={setDraggingMode}
        setDraggingVertex={setDraggingVertex}
        resolvePlacement={resolvePlacement}
        placementMode={placementMode}
        showHover={showHover}
        hoveredAnnotation={hoveredAnnotation}
        setPinnedAnnotation={setPinnedAnnotation}
        planPreviewAnnotations={planPreviewAnnotations}
        selectedIssueLabel={selectedIssueLabel}
        activeHighlightBounds={activeHighlightBounds}
        issueHighlightBounds={issueHighlightBounds}
        siteLocked={Boolean(siteLocked)}
        lotWidth={lotWidth}
        lotHeight={lotHeight}
        visibleCadObjects={visibleCadObjects}
        suggestedPlacements={suggestedPlacements}
        interactiveRectPercent={(item) => interactiveRectPercent(item, null)}
        rectIntersectsPreview={rectIntersectsPreview}
        resolveObjectHitZIndex={resolveObjectHitZIndex}
        selectedBuildingId={selectedBuildingId}
        drawMode={drawMode}
        previewInteraction={previewInteraction}
        handleBuildingMouseDown={handleBuildingMouseDown}
        onSelectBuilding={onSelectBuilding}
        setLastRectEdit={setLastRectEdit}
        onUpdateSuggested={onUpdateSuggested}
        onUpdateBuilding={onUpdateBuilding}
        setHoveredObjectId={setHoveredObjectId}
        activeAnnotation={activeAnnotation}
        hoverDetails={hoverDetails}
        fullscreenHoverPoint={fullscreenHoverPoint}
        allowEdits={allowEdits}
        showMeasurements={showMeasurements}
        showCalculations={showCalculations}
        measurementOverlayStats={measurementOverlayStats}
        calculationOverlayStats={calculationOverlayStats}
      />
    </div>
  );
}
