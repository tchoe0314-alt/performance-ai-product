"use client";

import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, MouseEvent as ReactMouseEvent } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { AlertTriangle, CornerUpLeft, CornerUpRight, Download, Droplets, Eye, EyeOff, FileText, Flame, GitBranch, Hand, Lock, MapPin, Maximize2, MousePointer2, Move, Navigation, Pentagon, PencilLine, RefreshCw, RotateCcw, RotateCw, Route, Ruler, Scale, Scissors, ShieldCheck, Square, Table2, Trash2, Unlock, X, ZoomIn, ZoomOut } from "lucide-react";

import type {
  Preview3DItem,
  PreviewResponse,
  PreviewReview,
  BuildingPlacement,
  GradingEarthworkUx,
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
import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";

const Preview3DCanvas = lazy(() => import("./Preview3DCanvas"));

type PreviewPhaseLabel = { label: string } | null;
type EngineeringSystemStatus = "fresh" | "stale" | "not_generated";
type EngineeringSystemStatuses = Record<
  "roads" | "parking" | "grading" | "drainage" | "utilities",
  EngineeringSystemStatus
>;
type DrawMode = "select" | "pan" | "site" | "polyline" | "polygon" | "rect" | "point";
type CadPoint = { x: number; y: number };
type CadSymbolKind = "hydrant" | "inlet" | "manhole" | "valve" | "tree" | "light" | "sign" | "utility_marker" | "benchmark" | "note_callout";
type CadDimensionMode = "linear" | "aligned";
type CadToolRequest = {
  id: number;
  commandText?: string;
  tool:
    | "select"
    | "line"
    | "polyline"
    | "area"
    | "box"
    | "point"
    | "circle"
    | "arc"
    | "text"
    | "move"
    | "copy"
    | "rotate"
    | "scale"
    | "offset"
    | "trim"
    | "extend"
    | "fillet"
    | "join"
    | "split"
    | "close"
    | "open"
    | "reverse"
    | "hatch"
    | "delete"
    | "dimension"
    | "measure"
    | "symbol"
    | "layer"
    | "properties"
    | "snap"
    | "ortho"
    | "undo"
    | "redo"
    | "command";
};
type CadHistoryEntry = {
  id: string;
  label: string;
  objectId: string;
  before: BuildingPlacement;
  after: BuildingPlacement;
};

const BALANCED_CANVAS_SCALE = 0.62;
type CadCommandHistoryEntry = {
  id: string;
  command: string;
  status: "applied" | "blocked" | "info";
  message: string;
};
type StormHydrologyOverlay = {
  inletChecks?: Array<{
    id: string;
    x: number | null;
    y: number | null;
    spreadFt: number | null;
    allowableSpreadFt: number | null;
    status: string;
  }>;
  overflowPaths?: Array<{
    id: string;
    name: string;
    capacityValid: boolean;
    path: Array<{ x: number; y: number }>;
  }>;
};

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

type WaterHydrantView = {
  id: string;
  label: string;
  x: number;
  y: number;
  zoneId: string;
  staticPressurePsi: number | null;
  residualPressurePsi: number | null;
  availableFlowGpm: number | null;
  status: "pass" | "review" | "fail";
  source: "annotation" | "canonical";
};

type WaterPressureZoneView = {
  id: string;
  label: string;
  minPressurePsi: number | null;
  maxPressurePsi: number | null;
  residualTargetPsi: number;
  color: string;
  geometry: Array<[number, number]>;
};

type WaterNetworkSegmentView = {
  id: string;
  label: string;
  fromHydrantId?: string;
  toHydrantId?: string;
  fromNode?: string;
  toNode?: string;
  networkType: "loop" | "dead_end";
  diameterIn: number | null;
  lengthFt: number | null;
  flowGpm: number | null;
  velocityFps: number | null;
  startPressurePsi: number | null;
  endPressurePsi: number | null;
  status: "pass" | "review" | "fail";
  geometry: Array<[number, number]>;
};

type FireScenarioView = {
  id: string;
  label: string;
  hydrantId: string;
  requiredFlowGpm: number | null;
  availableFlowGpm: number | null;
  staticPressurePsi: number | null;
  residualPressurePsi: number | null;
  residualTargetPsi: number | null;
  status: "pass" | "review" | "fail";
  networkType: "loop" | "dead_end";
  missingInputs: string[];
};

type CoordinationSeverity = "clear" | "watch" | "conflict";

type UtilityCoordinationRow = {
  id: string;
  label: string;
  systemA: string;
  systemB: string;
  crossingType: "vertical" | "horizontal" | "unknown";
  clearanceFt: number | null;
  requiredFt: number | null;
  status: CoordinationSeverity;
  x: number;
  y: number;
  source: string;
  rerouteOptions: string[];
  constructabilityScore: number;
};

type AiRealismArtifact = {
  type: "high_quality_ai_render_v1";
  project_id: string;
  source_layout_hash: string;
  source_objects_summary: {
    total: number;
    objects_included: string[];
    counts_by_type: Record<string, number>;
  };
  missing_inputs: string[];
  stale: boolean;
  generated_timestamp: string;
  review_only: true;
  not_site_evidence: true;
  construction_release_allowed: false;
  image_data_url: string;
};

const AI_REALISM_WATERMARK =
  "AI visualization from current review layout - visual concept only, not engineering evidence.";

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const readMetaNumber = (meta: Record<string, unknown> | undefined, keys: string[]): number | null => {
  if (!meta) return null;
  for (const key of keys) {
    const value = toFiniteNumber(meta[key]);
    if (value !== null) return value;
  }
  return null;
};

const normalizeFlowStatus = (value: unknown): "pass" | "review" | "fail" => {
  const status = String(value || "").toLowerCase();
  if (status.includes("fail") || status.includes("block")) return "fail";
  if (status.includes("pass") || status.includes("ok") || status.includes("ready")) return "pass";
  return "review";
};

const formatFlowValue = (value: number | null | undefined, unit: string, decimals = 0) =>
  value === null || value === undefined || Number.isNaN(value) ? "--" : `${value.toFixed(decimals)} ${unit}`;

const normalizeSystemLabel = (value: unknown) => {
  const raw = String(value || "").toLowerCase();
  if (raw.includes("storm") || raw.includes("drain")) return "Storm";
  if (raw.includes("sanitary") || raw.includes("sewer")) return "Sanitary";
  if (raw.includes("water") || raw.includes("hydrant")) return "Water";
  if (raw.includes("gas")) return "Gas";
  if (raw.includes("electric") || raw.includes("power")) return "Electric";
  if (raw.includes("telecom") || raw.includes("fiber")) return "Telecom";
  if (raw.includes("road")) return "Road";
  if (raw.includes("building")) return "Building";
  if (raw.includes("utility")) return "Utility";
  return String(value || "Utility").replace(/_/g, " ");
};

const formatClearance = (value: number | null | undefined) =>
  value === null || value === undefined || Number.isNaN(value) ? "Needs source" : `${value.toFixed(1)} ft`;

type PreviewSourceState = "verified" | "imported" | "inferred" | "stale" | "blocked" | "fallback";

const resolveSourceState = (item: BuildingPlacement): PreviewSourceState => {
  const meta = item.meta ?? {};
  const statusText = [
    meta.source_confidence,
    meta.cad_source_confidence,
    meta.classification_status,
    meta.engineering_status,
    meta.review_status,
    meta.handoff_status,
    meta.source,
    item.source,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  if (item.meta?.unsupported_entity_placeholder || statusText.includes("blocked")) return "blocked";
  if (statusText.includes("stale") || statusText.includes("dirty")) return "stale";
  if (statusText.includes("inferred") || statusText.includes("low") || item.source === "inferred") return "inferred";
  if (statusText.includes("import") || item.source === "detected_from_image") return "imported";
  const hasPathGeometry = hasExplicitFootprintGeometry(item);
  const sourceBackedRect =
    item.geometryType === "rect" &&
    (item.source === "user" ||
      item.source === "manual_drawn" ||
      item.source === "user_confirmed" ||
      statusText.includes("verified") ||
      statusText.includes("source-backed") ||
      statusText.includes("survey") ||
      statusText.includes("import"));
  if (!hasPathGeometry && item.geometryType === "rect" && item.type !== "site" && !sourceBackedRect) return "fallback";
  if (!hasPathGeometry && item.geometryType !== "rect" && item.type !== "site") return "fallback";
  return "verified";
};

const sourceStateLabel = (state: PreviewSourceState) => {
  if (state === "verified") return "Source-backed geometry";
  if (state === "imported") return "Imported geometry - review required";
  if (state === "inferred") return "Inferred geometry - low confidence";
  if (state === "stale") return "Stale geometry - rerun affected systems";
  if (state === "blocked") return "Geometry needs review";
  return "Fallback geometry - bounds only";
};

const geometryTruthLabel = (item: BuildingPlacement) => {
  const state = resolveSourceState(item);
  const entityType = String(item.meta?.cad_entity_type || item.geometryType || "");
  if (state === "fallback") return sourceStateLabel(state);
  if (item.geometryType === "polygon") return "True polygon footprint";
  if (item.geometryType === "polyline") return "True linework";
  if (item.geometryType === "point") return "Point / symbol";
  if (item.geometryType === "rect" || entityType === "rectangle") return "Draft rectangular footprint";
  return sourceStateLabel(state);
};

const utilityStrokeColor = (item: BuildingPlacement) => {
  const text = `${item.type || ""} ${item.label || ""} ${item.meta?.system || ""} ${item.meta?.discipline || ""}`.toLowerCase();
  if (text.includes("water") || text.includes("hydrant")) return "#0284c7";
  if (text.includes("sanitary") || text.includes("sewer") || text.includes("manhole")) return "#7c3aed";
  if (text.includes("storm") || text.includes("drain") || text.includes("inlet")) return "#0f766e";
  if (text.includes("electric") || text.includes("power")) return "#ca8a04";
  if (text.includes("gas")) return "#dc2626";
  return "#7c3aed";
};

const polygonCentroid = (points: Array<[number, number]>): [number, number] => {
  if (!points.length) return [0, 0];
  const sum = points.reduce(
    (acc, pt) => {
      acc.x += pt[0];
      acc.y += pt[1];
      return acc;
    },
    { x: 0, y: 0 },
  );
  return [sum.x / points.length, sum.y / points.length];
};

const scalePolygonTowardCenter = (points: Array<[number, number]>, scale: number): Array<[number, number]> => {
  const [cx, cy] = polygonCentroid(points);
  return points.map(([x, y]) => [cx + (x - cx) * scale, cy + (y - cy) * scale]);
};

const firstMetaNumber = (item: BuildingPlacement, keys: string[]): number | null => readMetaNumber(item.meta, keys);

const hasExplicitFootprintGeometry = (item: BuildingPlacement) =>
  (item.geometryType === "polygon" || item.geometryType === "polyline" || item.geometryType === "point") &&
  Array.isArray(item.geometry) &&
  item.geometry.length > 0;

const supportsParkingModuleRendering = (item: BuildingPlacement) => {
  const params = (item.meta as { parkingParams?: ParkingParams } | undefined)?.parkingParams ?? {};
  const stallDepth = Number.isFinite(params.stallDepth) ? Number(params.stallDepth) : 18;
  const aisleWidth = Number.isFinite(params.aisleWidth) ? Number(params.aisleWidth) : 24;
  const stallWidth = Number.isFinite(params.stallWidth) ? Number(params.stallWidth) : 9;
  const loading = params.loading === "single" ? "single" : "double";
  const minDepth = stallDepth * (loading === "double" ? 2 : 1) + aisleWidth;
  const minWidth = Math.max(stallWidth * 2.5, 24);
  return item.type === "parking" && item.w >= minWidth && item.d >= minDepth * 0.82;
};

const hasParkingGeometryEvidence = (item: BuildingPlacement) =>
  supportsParkingModuleRendering(item) &&
  Number.isFinite(item.w) &&
  Number.isFinite(item.d);

const stableHash = (value: string) => {
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
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
  onAiRealismChange?: (event: { type: "generated" | "stale" | "blocked"; detail: string }) => void;
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
    meta?: Record<string, unknown>;
  }) => void;
  onCreateSiteBoundary?: (payload: { points: Array<[number, number]> }) => void;
  onLockSite?: () => void;
  onUnlockSite?: () => void;
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewObjects?: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
  selectedBuildingId: string | null;
  selectedObjectIds?: string[];
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
  onSelectObjects?: (ids: string[]) => void;
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
  gradingEarthworkUx?: GradingEarthworkUx | null;
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
  stormHydrologyOverlay?: StormHydrologyOverlay;
  sourceContextBadges?: Array<{ label: string; tone: "found" | "missing" | "review" }>;
  debugStats?: {
    enabled: boolean;
    projectId: string;
    canonicalCount: number;
    placedCount: number;
    previewImageActive: boolean;
    placementMode: boolean;
    selectedId: string | null;
  };
  cadToolRequest?: CadToolRequest | null;
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
  planPreviewProjectId,
  currentProjectId,
  previewMode,
  previewInteraction,
  previewQuality,
  previewLabelDensity,
  systemStatuses,
  hasTerrainSource,
  hasGeneratedPlan,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onSetPreviewQuality,
  onAiRealismChange,
  onSetPreviewLabelDensity,
  onQueuePreviewRefresh,
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
  onExportDxf,
  onExportReport,
  exportBlockReason,
  planPreviewAnnotations,
  selectedIssueLabel,
  showMeasurements,
  showCalculations,
  measurementOverlayStats,
  calculationOverlayStats,
  gradingEarthworkUx,
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
  debugStats,
  cadToolRequest,
}: PreviewPanelProps) {
  const previewLabels = useMemo(
    () => (Array.isArray(planPreviewAnnotations?.labels) ? planPreviewAnnotations?.labels : []),
    [planPreviewAnnotations],
  );
  const utilityCoordinationRows = useMemo<UtilityCoordinationRow[]>(() => {
    const explicit = (planPreviewAnnotations as Record<string, unknown> | null | undefined)?.utility_coordination;
    const explicitRows = Array.isArray(explicit)
      ? explicit
      : Array.isArray((explicit as { rows?: unknown[] } | undefined)?.rows)
        ? (explicit as { rows: unknown[] }).rows
        : [];
    const fromExplicit = explicitRows
      .map((item, index) => {
        const row = item as Record<string, unknown>;
        const clearance = readMetaNumber(row, ["clearance_ft", "clearance", "vertical_clearance_ft", "horizontal_clearance_ft"]);
        const required = readMetaNumber(row, ["required_clearance_ft", "minimum_clearance_ft", "min_clearance_ft"]);
        const score = toFiniteNumber(row.constructability_score) ?? (clearance !== null && required !== null ? Math.round(Math.min(Math.max((clearance / Math.max(required, 0.1)) * 82, 20), 96)) : 58);
        const status: CoordinationSeverity =
          String(row.status || row.severity || "").toLowerCase().includes("conflict") ||
          (clearance !== null && required !== null && clearance < required)
            ? "conflict"
            : clearance !== null && required !== null && clearance < required + 1
              ? "watch"
              : "clear";
        const crossingType: UtilityCoordinationRow["crossingType"] =
          String(row.crossing_type || row.clearance_type || "").toLowerCase().includes("horizontal")
            ? "horizontal"
            : String(row.crossing_type || row.clearance_type || "").toLowerCase().includes("vertical")
              ? "vertical"
              : "unknown";
        return {
          id: String(row.id || row.crossing_id || `coord-explicit-${index}`),
          label: String(row.label || row.name || `Crossing ${index + 1}`),
          systemA: normalizeSystemLabel(row.system_a || row.systemA || row.primary_system),
          systemB: normalizeSystemLabel(row.system_b || row.systemB || row.secondary_system),
          crossingType,
          clearanceFt: clearance,
          requiredFt: required,
          status,
          x: Math.min(Math.max(toFiniteNumber(row.x) ?? toFiniteNumber(row.relative_x) ?? 0.5, 0), 1),
          y: Math.min(Math.max(toFiniteNumber(row.y) ?? toFiniteNumber(row.relative_y) ?? 0.5, 0), 1),
          source: String(row.source || "coordination payload"),
          rerouteOptions: Array.isArray(row.reroute_options)
            ? row.reroute_options.map((value) => String(value)).slice(0, 3)
            : [],
          constructabilityScore: Math.round(Math.min(Math.max(score, 0), 100)),
        };
      });
    if (fromExplicit.length) return fromExplicit;

    const coordinationLabels = previewLabels.filter((item) => {
      const text = `${item.label} ${item.layer} ${item.meta?.system || ""} ${item.meta?.source_stage || ""}`.toLowerCase();
      return (
        text.includes("conflict") ||
        text.includes("crossing") ||
        text.includes("clearance") ||
        text.includes("utility") ||
        text.includes("storm") ||
        text.includes("sanitary") ||
        text.includes("water")
      );
    });
    const utilityLike = coordinationLabels.filter((item) => {
      const text = `${item.label} ${item.layer} ${item.meta?.system || ""}`.toLowerCase();
      return text.includes("utility") || text.includes("storm") || text.includes("sanitary") || text.includes("water");
    });
    const sourceRows = coordinationLabels.length ? coordinationLabels : utilityLike;
    return sourceRows.slice(0, 8).map((item, index) => {
      const meta = item.meta as Record<string, unknown> | undefined;
      const text = `${item.label} ${item.layer} ${meta?.system || ""}`.toLowerCase();
      const clearance = readMetaNumber(meta, [
        "clearance_ft",
        "vertical_clearance_ft",
        "horizontal_clearance_ft",
        "separation_ft",
      ]);
      const required = readMetaNumber(meta, ["required_clearance_ft", "minimum_clearance_ft", "min_clearance_ft"]);
      const isConflict = text.includes("conflict") || (clearance !== null && required !== null && clearance < required);
      const isWatch = text.includes("review") || text.includes("clearance") || (clearance !== null && required !== null && clearance < required + 1);
      const primary = normalizeSystemLabel(meta?.system || meta?.source_type || item.layer);
      const secondary = text.includes("storm")
        ? "Utility"
        : text.includes("sanitary")
          ? "Storm"
          : text.includes("water")
            ? "Storm"
            : "Drainage";
      const scoreBase = isConflict ? 42 : isWatch ? 68 : 84;
      const score = clearance !== null && required !== null
        ? Math.round(Math.min(Math.max((clearance / Math.max(required, 0.1)) * 78, 24), 94))
        : scoreBase;
      return {
        id: String(meta?.entity_id || `${item.layer}-${item.label}-${index}`),
        label: item.label || `Coordination item ${index + 1}`,
        systemA: primary,
        systemB: normalizeSystemLabel(secondary),
        crossingType: text.includes("horizontal") ? "horizontal" : text.includes("vertical") || text.includes("crossing") ? "vertical" : "unknown",
        clearanceFt: clearance,
        requiredFt: required,
        status: isConflict ? "conflict" : isWatch ? "watch" : "clear",
        x: Math.min(Math.max(item.x, 0), 1),
        y: Math.min(Math.max(item.y, 0), 1),
        source: String(meta?.source_stage || meta?.canonical_source_type || "preview annotation"),
        rerouteOptions: isConflict
          ? ["Shift laterally", "Raise/flatten crossing", "Split run around constraint"]
          : isWatch
            ? ["Verify invert", "Add survey-control check", "Hold route for engineer review"]
            : ["Keep route", "Document clearance"],
        constructabilityScore: score,
      };
    });
  }, [planPreviewAnnotations, previewLabels]);
  const utilityCoordinationSummary = useMemo(() => {
    const conflictCount = utilityCoordinationRows.filter((row) => row.status === "conflict").length;
    const watchCount = utilityCoordinationRows.filter((row) => row.status === "watch").length;
    const avgScore = utilityCoordinationRows.length
      ? Math.round(utilityCoordinationRows.reduce((sum, row) => sum + row.constructabilityScore, 0) / utilityCoordinationRows.length)
      : previewReview?.unresolved_conflict_count
        ? 48
        : 76;
    return {
      crossingCount: utilityCoordinationRows.length,
      conflictCount,
      watchCount,
      avgScore,
      status: conflictCount > 0 ? "conflict" : watchCount > 0 ? "watch" : "clear" as CoordinationSeverity,
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
  const [aiRealismEnabled, setAiRealismEnabled] = useState(false);
  const [aiRealismArtifact, setAiRealismArtifact] = useState<AiRealismArtifact | null>(null);
  const [aiRealismBlocker, setAiRealismBlocker] = useState<string | null>(null);
  const aiRealismGenerationFrameRef = useRef<number | null>(null);
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
  const [selectedFireScenarioId, setSelectedFireScenarioId] = useState<string | null>(null);
  const [draftPoints, setDraftPoints] = useState<Array<[number, number]>>([]);
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
  const canDrawObjects = Boolean(siteLocked && hasDrawableSiteSize);
  const previousPlacementIdsRef = useRef<Set<string> | null>(null);
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
  const [cadWindowSelect, setCadWindowSelect] = useState<{
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
    containerLeft: number;
    containerTop: number;
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
  const buildBalancedCanvasView = useCallback(() => {
    const rect = previewRef.current?.getBoundingClientRect();
    const offsetX = rect ? Math.max(24, rect.width * (1 - BALANCED_CANVAS_SCALE) * 0.5) : 36;
    const offsetY = rect ? Math.max(22, rect.height * (1 - BALANCED_CANVAS_SCALE) * 0.5) : 32;
    return { scale: BALANCED_CANVAS_SCALE, offsetX, offsetY };
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
    drawMode !== "select" &&
    drawMode !== "pan" &&
    !selectedBuildingId;
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
  useEffect(
    () => () => {
      if (aiRealismGenerationFrameRef.current !== null) {
        window.cancelAnimationFrame(aiRealismGenerationFrameRef.current);
      }
    },
    [],
  );
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
  const planScaleBar = useMemo(() => {
    const span = Math.max(currentSiteSize.width, currentSiteSize.height, 1);
    const target = span / 5;
    const candidates = [10, 20, 25, 40, 50, 100, 200, 400, 500, 1000];
    const lengthFt = candidates.find((candidate) => candidate >= target) ?? candidates[candidates.length - 1];
    const widthPct = Math.min(36, Math.max(12, (lengthFt / currentSiteSize.width) * 100));
    return { lengthFt, widthPct };
  }, [currentSiteSize.height, currentSiteSize.width]);
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
      const sourceState = resolveSourceState(item);
      const blocked = sourceState === "blocked";
      const lowConfidence = sourceState === "inferred" || sourceState === "fallback";
      const reviewConcept = Boolean(item.meta?.generated_review_concept || item.meta?.visual_concept_only);
	      const imported = sourceState === "imported";
	      const stale = sourceState === "stale";
	      const customStroke =
	        typeof item.meta?.ui_color === "string" && /^#[0-9a-f]{6}$/i.test(item.meta.ui_color)
	          ? item.meta.ui_color
	          : null;
      const dash =
	        blocked ? "1.2 0.8" : reviewConcept ? "1.7 1.2" : stale ? "2.2 0.9 0.5 0.9" : lowConfidence ? "1.4 1.1" : imported ? "2.4 1" : undefined;
	      const stateStroke = (fallback: string) => (
	        selected ? "#0f766e" : blocked ? "#dc2626" : sourceState === "fallback" ? "#64748b" : customStroke ?? fallback
	      );
      const stateOpacity = blocked ? 0.92 : reviewConcept ? 0.62 : lowConfidence ? 0.9 : 1;
      const reviewWidth = (normal: number, selectedWidth: number) => (reviewConcept ? (selected ? 0.32 : 0.18) : selected ? selectedWidth : normal);
      if (!isHighQuality) {
        const standardPalette: Record<string, { fill: string; stroke: string }> = {
          building: { fill: "rgba(255, 255, 255, 0.42)", stroke: "#111827" },
          parking: { fill: "rgba(248, 250, 252, 0.2)", stroke: "#64748b" },
          road: { fill: "rgba(71, 85, 105, 0.08)", stroke: "#334155" },
          water: { fill: "rgba(186, 230, 253, 0.18)", stroke: "#0369a1" },
          landscape: { fill: "rgba(220, 252, 231, 0.14)", stroke: "#15803d" },
          sidewalk: { fill: "rgba(248, 250, 252, 0.36)", stroke: "#94a3b8" },
          utility: { fill: "rgba(59, 130, 246, 0.035)", stroke: "#1d4ed8" },
          fallback: { fill: "rgba(248, 250, 252, 0.025)", stroke: "#94a3b8" },
        };
        const style = standardPalette[kind] ?? standardPalette.fallback;
	        return {
	          fill: style.fill,
	          stroke: selected ? "#0f766e" : blocked ? "#dc2626" : customStroke ?? style.stroke,
          strokeWidth: selected ? (kind === "utility" ? 0.28 : 0.46) : reviewConcept ? 0.16 : kind === "fallback" ? 0.16 : kind === "building" ? 0.3 : kind === "road" || kind === "sidewalk" ? 0.32 : kind === "utility" ? 0.18 : 0.22,
          strokeDasharray: dash,
          opacity: stateOpacity,
        };
      }
      if (kind === "road") {
        return { fill: "rgba(71, 85, 105, 0.085)", stroke: stateStroke("#475569"), strokeWidth: reviewWidth(0.62, 0.86), strokeDasharray: dash, opacity: stateOpacity };
      }
      if (kind === "parking") {
        return { fill: "rgba(248, 250, 252, 0.2)", stroke: stateStroke("#64748b"), strokeWidth: reviewWidth(0.24, 0.54), strokeDasharray: dash, opacity: stateOpacity };
      }
      if (kind === "water") {
        return { fill: "rgba(125, 211, 252, 0.22)", stroke: stateStroke("#0284c7"), strokeWidth: reviewWidth(0.34, 0.62), strokeDasharray: dash, opacity: stateOpacity };
      }
      if (kind === "landscape") {
        return { fill: "rgba(134, 239, 172, 0.16)", stroke: stateStroke("#16a34a"), strokeWidth: reviewWidth(0.28, 0.56), strokeDasharray: dash, opacity: stateOpacity };
      }
      if (kind === "sidewalk") {
        return { fill: "rgba(248, 250, 252, 0.42)", stroke: stateStroke("#94a3b8"), strokeWidth: reviewWidth(0.32, 0.56), strokeDasharray: dash, opacity: stateOpacity };
      }
      if (kind === "utility") {
        return { fill: "rgba(37, 99, 235, 0.065)", stroke: stateStroke(utilityStrokeColor(item)), strokeWidth: reviewWidth(0.34, 0.58), strokeDasharray: dash, opacity: stateOpacity };
      }
      if (kind === "building") {
        return { fill: "rgba(255, 255, 255, 0.48)", stroke: stateStroke("#111827"), strokeWidth: reviewWidth(0.3, 0.58), strokeDasharray: dash, opacity: stateOpacity };
      }
      return { fill: "rgba(248, 250, 252, 0.025)", stroke: stateStroke("#94a3b8"), strokeWidth: reviewWidth(0.16, 0.42), strokeDasharray: dash, opacity: stateOpacity };
    },
    [isHighQuality, resolveVisualKind],
  );
  const cadHatchPatternForItem = useCallback((item: BuildingPlacement) => {
    if (!item.meta?.cad_hatch_enabled) return null;
    const pattern = String(item.meta?.cad_hatch_pattern || "").toLowerCase();
    if (pattern === "water") return "url(#cad-hatch-water)";
    if (pattern === "landscape") return "url(#cad-hatch-landscape)";
    return "url(#cad-hatch-diagonal)";
  }, []);
  const roundedSiteShapePath = useCallback(
    (
      rect: { left: number; top: number; width: number; height: number },
      kind: "water" | "landscape" | "road" | "sidewalk",
    ) => {
      const x = rect.left;
      const y = rect.top;
      const w = Math.max(rect.width, 0.1);
      const h = Math.max(rect.height, 0.1);
      if (kind === "road" || kind === "sidewalk") {
        const r = Math.min(w, h) * 0.22;
        return `M ${x + r} ${y} L ${x + w - r} ${y} Q ${x + w} ${y} ${x + w} ${y + r} L ${x + w} ${y + h - r} Q ${x + w} ${y + h} ${x + w - r} ${y + h} L ${x + r} ${y + h} Q ${x} ${y + h} ${x} ${y + h - r} L ${x} ${y + r} Q ${x} ${y} ${x + r} ${y} Z`;
      }
      const wobble = kind === "water" ? 0.13 : 0.18;
      return [
        `M ${x + w * 0.18} ${y + h * 0.18}`,
        `C ${x + w * 0.32} ${y - h * wobble} ${x + w * 0.7} ${y - h * 0.04} ${x + w * 0.84} ${y + h * 0.22}`,
        `C ${x + w * 1.04} ${y + h * 0.42} ${x + w * 0.96} ${y + h * 0.78} ${x + w * 0.76} ${y + h * 0.9}`,
        `C ${x + w * 0.54} ${y + h * 1.05} ${x + w * 0.2} ${y + h * 0.94} ${x + w * 0.08} ${y + h * 0.7}`,
        `C ${x - w * 0.04} ${y + h * 0.48} ${x + w * 0.02} ${y + h * 0.28} ${x + w * 0.18} ${y + h * 0.18}`,
        "Z",
      ].join(" ");
    },
    [],
  );
  const rectCorridorAxis = useCallback((rect: { left: number; top: number; width: number; height: number }) => {
    const inset = 0.12;
    if (rect.width >= rect.height) {
      return {
        x1: rect.left + rect.width * inset,
        y1: rect.top + rect.height / 2,
        x2: rect.left + rect.width * (1 - inset),
        y2: rect.top + rect.height / 2,
        width: Math.max(0.85, Math.min(5.2, rect.height * 0.72)),
      };
    }
    return {
      x1: rect.left + rect.width / 2,
      y1: rect.top + rect.height * inset,
      x2: rect.left + rect.width / 2,
      y2: rect.top + rect.height * (1 - inset),
      width: Math.max(0.85, Math.min(5.2, rect.width * 0.72)),
    };
  }, []);
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
  const aiRealismSourceObjects = useMemo(
    () =>
      [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements]
        .filter(
          (item) =>
            item.type !== "site" &&
            item.placed &&
            Number.isFinite(item.x) &&
            Number.isFinite(item.y),
        )
        .map((item) => ({
          id: item.id,
          label: item.label || item.type || item.id,
          type: item.type || "custom",
          x: Number(item.x ?? 0),
          y: Number(item.y ?? 0),
          w: Number(item.w ?? 0),
          d: Number(item.d ?? 0),
          h: Number(item.h ?? 0),
          rotation: Number(item.rotation ?? 0),
          geometryType: item.geometryType || "rect",
          geometry: Array.isArray(item.geometry) ? item.geometry : undefined,
          source: item.source || (item.generated ? "generated" : "user"),
          confidence: typeof item.confidence === "number" ? item.confidence : null,
        }))
        .sort((a, b) => a.id.localeCompare(b.id)),
    [buildingPlacements, cadEntityPreviewObjects, suggestedPlacements],
  );
  const aiRealismLayoutHash = useMemo(
    () =>
      stableHash(
        JSON.stringify({
          site: {
            lotWidth,
            lotHeight,
            siteRotationDeg: siteRotationDeg ?? 0,
            terrain: hasTerrainSource ? "terrain-source" : "terrain-missing",
          },
          objects: aiRealismSourceObjects,
        }),
      ),
    [aiRealismSourceObjects, hasTerrainSource, lotHeight, lotWidth, siteRotationDeg],
  );
  const aiRealismSourceSummary = useMemo(() => {
    const counts: Record<string, number> = {};
    aiRealismSourceObjects.forEach((item) => {
      counts[item.type] = (counts[item.type] ?? 0) + 1;
    });
    return {
      total: aiRealismSourceObjects.length,
      objects_included: aiRealismSourceObjects.map((item) => `${item.label} (${item.type})`),
      counts_by_type: counts,
    };
  }, [aiRealismSourceObjects]);
  const aiRealismMissingInputs = useMemo(() => {
    const missing: string[] = [];
    if (!hasTerrainSource) missing.push("terrain/source confidence");
    if (!geocode?.lat || !geocode?.lng) missing.push("source-backed map/geocode context");
    if (!aiRealismSourceObjects.some((item) => item.type === "road" || item.type === "driveway")) {
      missing.push("roads/driveways");
    }
    if (!aiRealismSourceObjects.some((item) => item.type === "utility_corridor" || item.type === "hydrant" || item.type === "manhole" || item.type === "inlet" || item.type === "outfall")) {
      missing.push("visible storm/sanitary/water utility context");
    }
    return missing;
  }, [aiRealismSourceObjects, geocode?.lat, geocode?.lng, hasTerrainSource]);
  const aiRealismStale = Boolean(
    aiRealismArtifact && aiRealismArtifact.source_layout_hash !== aiRealismLayoutHash,
  );
  const aiRealismStaleNoticeRef = useRef("");
  useEffect(() => {
    if (!aiRealismStale) {
      aiRealismStaleNoticeRef.current = "";
      return;
    }
    const key = `${aiRealismArtifact?.generated_timestamp || "artifact"}:${aiRealismLayoutHash}`;
    if (aiRealismStaleNoticeRef.current === key) return;
    aiRealismStaleNoticeRef.current = key;
    onAiRealismChange?.({
      type: "stale",
      detail: "AI realism visualization is stale after the review layout changed.",
    });
  }, [aiRealismArtifact?.generated_timestamp, aiRealismLayoutHash, aiRealismStale, onAiRealismChange]);
  const generateAiRealismArtifact = useCallback(() => {
    if (!aiRealismSourceObjects.length) {
      setAiRealismBlocker("Add or generate site objects before creating AI realism.");
      onAiRealismChange?.({
        type: "blocked",
        detail: "Add or generate site objects before creating AI realism.",
      });
      return;
    }
    if (!aiRealismProviderConfigured) {
      setAiRealismBlocker("AI realism provider is not configured.");
      onAiRealismChange?.({
        type: "blocked",
        detail: "AI realism provider is not configured.",
      });
      return;
    }
    const generated_timestamp = new Date().toISOString();
    const project_id = currentProjectId || planPreviewProjectId || "unsaved-review-layout";
    const counts = aiRealismSourceSummary.counts_by_type;
    const promptSummary = [
      `${aiRealismSourceObjects.length} review layout objects`,
      counts.building || counts.multifamily_building || counts.retail_building ? "building massing" : "",
      counts.parking ? "parking fields" : "",
      counts.road || counts.driveway ? "roads and driveways" : "",
      counts.basin ? "detention basin" : "",
      hasTerrainSource ? "terrain source present" : "terrain source missing",
    ]
      .filter(Boolean)
      .join(", ");
    const image_data_url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img" aria-label="Mock AI realism visualization from current review layout"><defs><linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#dbeafe"/><stop offset="0.48" stop-color="#f8fafc"/><stop offset="1" stop-color="#b7d6b4"/></linearGradient><filter id="soft"><feGaussianBlur stdDeviation="0.45"/></filter></defs><rect width="1200" height="760" fill="url(#sky)"/><path d="M0 470 C220 390 390 480 610 410 C820 342 1010 412 1200 346 L1200 760 L0 760 Z" fill="#8bb17f"/><path d="M40 610 C230 520 390 576 578 502 C804 412 968 506 1180 418" fill="none" stroke="#4b5563" stroke-width="58" stroke-linecap="round"/><path d="M40 610 C230 520 390 576 578 502 C804 412 968 506 1180 418" fill="none" stroke="#e5e7eb" stroke-width="4" stroke-dasharray="24 18" opacity="0.85"/><rect x="195" y="214" width="176" height="82" rx="6" fill="#c7b897" stroke="#76664d" stroke-width="4" transform="skewY(-8)"/><rect x="535" y="188" width="176" height="82" rx="6" fill="#c7b897" stroke="#76664d" stroke-width="4" transform="skewY(-6)"/><rect x="188" y="540" width="128" height="68" rx="6" fill="#c7b897" stroke="#76664d" stroke-width="4" transform="skewY(-7)"/><rect x="410" y="352" width="310" height="128" rx="10" fill="#9ca3af" opacity="0.56"/><g stroke="#f8fafc" stroke-width="3" opacity="0.85">${Array.from({ length: 9 }).map((_, index) => `<line x1="${430 + index * 30}" y1="360" x2="${452 + index * 30}" y2="472"/>`).join("")}</g><ellipse cx="935" cy="598" rx="145" ry="68" fill="#7dd3fc" opacity="0.72" stroke="#0284c7" stroke-width="4"/><path d="M220 404 C350 378 508 392 635 360" fill="none" stroke="#f8fafc" stroke-width="18" opacity="0.82"/><text x="54" y="72" fill="#0f172a" font-family="Arial, sans-serif" font-size="26" font-weight="700">High Quality AI Realism Preview</text><text x="54" y="108" fill="#334155" font-family="Arial, sans-serif" font-size="18">${promptSummary}</text><rect x="48" y="676" width="1104" height="44" rx="8" fill="rgba(15,23,42,0.78)"/><text x="70" y="704" fill="#fff" font-family="Arial, sans-serif" font-size="18">${AI_REALISM_WATERMARK}</text></svg>`,
    )}`;
    setAiRealismArtifact({
      type: "high_quality_ai_render_v1",
      project_id,
      source_layout_hash: aiRealismLayoutHash,
      source_objects_summary: aiRealismSourceSummary,
      missing_inputs: aiRealismMissingInputs,
      stale: false,
      generated_timestamp,
      review_only: true,
      not_site_evidence: true,
      construction_release_allowed: false,
      image_data_url,
    });
    setAiRealismBlocker(null);
    onAiRealismChange?.({
      type: "generated",
      detail: "AI realism visualization regenerated from the current review layout.",
    });
  }, [
    aiRealismLayoutHash,
    aiRealismMissingInputs,
    aiRealismProviderConfigured,
    aiRealismSourceObjects,
    aiRealismSourceSummary,
    currentProjectId,
    hasTerrainSource,
    onAiRealismChange,
    planPreviewProjectId,
  ]);
  const setAiVisualizationOff = useCallback(() => {
    const startedAt = markCivoraInteraction();
    if (aiRealismGenerationFrameRef.current !== null) {
      window.cancelAnimationFrame(aiRealismGenerationFrameRef.current);
      aiRealismGenerationFrameRef.current = null;
    }
    setAiRealismEnabled(false);
    setAiRealismBlocker(null);
    measureCivoraInteractionAfterPaint("preview.aiVisualization.off", startedAt, {
      hasArtifact: Boolean(aiRealismArtifact),
    });
  }, [aiRealismArtifact]);
  const setAiVisualizationOn = useCallback(() => {
    const startedAt = markCivoraInteraction();
    setAiRealismEnabled(true);
    measureCivoraInteractionAfterPaint("preview.aiVisualization.on", startedAt, {
      hasArtifact: Boolean(aiRealismArtifact),
      providerConfigured: aiRealismProviderConfigured,
    });
    if (aiRealismArtifact || aiRealismGenerationFrameRef.current !== null) return;
    aiRealismGenerationFrameRef.current = window.requestAnimationFrame(() => {
      aiRealismGenerationFrameRef.current = null;
      generateAiRealismArtifact();
    });
  }, [aiRealismArtifact, aiRealismProviderConfigured, generateAiRealismArtifact]);
  const aiRealismDisplayArtifact = useMemo(
    () => (aiRealismArtifact ? { ...aiRealismArtifact, stale: aiRealismStale } : null),
    [aiRealismArtifact, aiRealismStale],
  );
  useEffect(() => {
    if (typeof window === "undefined") return;
    const debugWindow = window as unknown as Record<string, unknown>;
    debugWindow.__civoraAiRealismArtifact = aiRealismDisplayArtifact;
    debugWindow.__civoraAiRealismEnabled = aiRealismEnabled;
    debugWindow.__civoraAiRealismLayoutHash = aiRealismLayoutHash;
  }, [aiRealismDisplayArtifact, aiRealismEnabled, aiRealismLayoutHash]);
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
  const surfaceModel = gradingEarthworkUx?.surfaceModel;
  const accessPointsForParking = useMemo(
    () =>
      buildingPlacements
        .filter((item) => item.type === "entrance" || item.type === "road" || item.type === "driveway")
        .map((item) => ({ x: (item.x ?? 0) + item.w / 2, y: (item.y ?? 0) + item.d / 2 })),
    [buildingPlacements],
  );
  const waterFireFlow = useMemo(() => {
    const annotations = planPreviewAnnotations?.water_fire_flow;
    const placedObjects = [...buildingPlacements, ...suggestedPlacements].filter(
      (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
    );
    const annotationZones: WaterPressureZoneView[] = (annotations?.pressure_zones ?? [])
      .map((zone, idx) => {
        const geometry = Array.isArray(zone.geometry) ? zone.geometry : [];
        return {
          id: zone.id || `pressure-zone-${idx + 1}`,
          label: zone.label || `Pressure Zone ${idx + 1}`,
          minPressurePsi: toFiniteNumber(zone.min_pressure_psi),
          maxPressurePsi: toFiniteNumber(zone.max_pressure_psi),
          residualTargetPsi: toFiniteNumber(zone.residual_target_psi) ?? 20,
          color: zone.color || (idx % 2 === 0 ? "#0ea5e9" : "#14b8a6"),
          geometry,
        };
      });
    const pressureZones = annotationZones;
    const defaultZone = pressureZones[0];
    const annotatedHydrants: WaterHydrantView[] = (annotations?.hydrants ?? [])
      .map((hydrant, idx) => {
        const staticPressurePsi = toFiniteNumber(hydrant.static_pressure_psi);
        const availableFlowGpm = toFiniteNumber(hydrant.available_flow_gpm);
        const residualPressurePsi = toFiniteNumber(hydrant.residual_pressure_psi);
        const row: WaterHydrantView = {
          id: hydrant.id || `hydrant-ann-${idx + 1}`,
          label: hydrant.label || `H-${idx + 1}`,
          x: toFiniteNumber(hydrant.x) ?? 0,
          y: toFiniteNumber(hydrant.y) ?? 0,
          zoneId: hydrant.zone_id || defaultZone?.id || "zone-a",
          staticPressurePsi,
          residualPressurePsi,
          availableFlowGpm,
          status: normalizeFlowStatus(hydrant.status),
          source: "annotation" as const,
        };
        return row;
      })
      .filter((hydrant) => Number.isFinite(hydrant.x) && Number.isFinite(hydrant.y));
    const canonicalHydrants: WaterHydrantView[] = placedObjects
      .filter((item) => item.type === "hydrant" || String(item.label || "").toLowerCase().includes("hydrant"))
      .map((item, idx) => {
        const meta = item.meta as Record<string, unknown> | undefined;
        const staticPressurePsi = readMetaNumber(meta, ["static_pressure_psi", "pressure_psi", "staticPressurePsi"]);
        const residualPressurePsi = readMetaNumber(meta, ["residual_pressure_psi", "residualPressurePsi"]);
        const availableFlowGpm = readMetaNumber(meta, ["available_flow_gpm", "flow_gpm", "availableFlowGpm"]);
        return {
          id: item.id || `hydrant-${idx + 1}`,
          label: item.label || `H-${idx + 1}`,
          x: (item.x ?? 0) + item.w / 2,
          y: (item.y ?? 0) + item.d / 2,
          zoneId: String(meta?.zone_id || meta?.pressure_zone_id || defaultZone?.id || "zone-a"),
          staticPressurePsi,
          residualPressurePsi,
          availableFlowGpm,
          status: normalizeFlowStatus(meta?.status),
          source: "canonical" as const,
        };
      });
    const hydrantsById = new Map<string, WaterHydrantView>();
    [...annotatedHydrants, ...canonicalHydrants].forEach((hydrant) => {
      if (!hydrantsById.has(hydrant.id)) hydrantsById.set(hydrant.id, hydrant);
    });
    const hydrants = Array.from(hydrantsById.values());
    const waterLineObjects = placedObjects.filter((item) => {
      const label = String(item.label || "").toLowerCase();
      const meta = item.meta as Record<string, unknown> | undefined;
      const system = String(meta?.system || meta?.discipline || "").toLowerCase();
      return (
        item.type === "utility_corridor" ||
        label.includes("water") ||
        label.includes("main") ||
        label.includes("fire") ||
        system.includes("water")
      );
    });
    const annotatedSegments: WaterNetworkSegmentView[] = (annotations?.network_segments ?? [])
      .map((segment, idx) => ({
        id: segment.id || `water-segment-ann-${idx + 1}`,
        label: segment.label || `W-${idx + 1}`,
        fromHydrantId: segment.from_hydrant_id,
        toHydrantId: segment.to_hydrant_id,
        fromNode: segment.from_node,
        toNode: segment.to_node,
        networkType: String(segment.network_type || "").toLowerCase().includes("dead") ? "dead_end" : "loop",
        diameterIn: toFiniteNumber(segment.diameter_in),
        lengthFt: toFiniteNumber(segment.length_ft),
        flowGpm: toFiniteNumber(segment.flow_gpm),
        velocityFps: toFiniteNumber(segment.velocity_fps),
        startPressurePsi: toFiniteNumber(segment.start_pressure_psi),
        endPressurePsi: toFiniteNumber(segment.end_pressure_psi),
        status: normalizeFlowStatus(segment.status),
        geometry: Array.isArray(segment.geometry) ? segment.geometry : [],
      }));
    const objectSegments: WaterNetworkSegmentView[] = waterLineObjects
      .filter((item) => item.geometryType === "polyline" && Array.isArray(item.geometry) && item.geometry.length > 1)
      .map((item, idx) => {
        const meta = item.meta as Record<string, unknown> | undefined;
        const geometry = item.geometry ?? [];
        const first = geometry[0];
        const last = geometry[geometry.length - 1];
        const closed = Boolean(first && last && Math.hypot(first[0] - last[0], first[1] - last[1]) < 5);
        return {
          id: item.id || `water-segment-${idx + 1}`,
          label: item.label || `Water Main ${idx + 1}`,
          networkType: closed ? "loop" : "dead_end",
          diameterIn: readMetaNumber(meta, ["diameter_in", "diameterIn"]),
          lengthFt: readMetaNumber(meta, ["length_ft", "lengthFt"]),
          flowGpm: readMetaNumber(meta, ["flow_gpm", "flowGpm"]),
          velocityFps: readMetaNumber(meta, ["velocity_fps", "velocityFps"]),
          startPressurePsi: readMetaNumber(meta, ["start_pressure_psi", "startPressurePsi"]),
          endPressurePsi: readMetaNumber(meta, ["end_pressure_psi", "endPressurePsi"]),
          status: normalizeFlowStatus(meta?.status),
          geometry,
        };
      });
    const networkSegments = [...annotatedSegments, ...objectSegments];
    const zoneById = new Map(pressureZones.map((zone) => [zone.id, zone]));
    const networkByHydrant = new Map<string, "loop" | "dead_end">();
    networkSegments.forEach((segment) => {
      if (segment.fromHydrantId) networkByHydrant.set(segment.fromHydrantId, segment.networkType);
      if (segment.toHydrantId) networkByHydrant.set(segment.toHydrantId, segment.networkType);
    });
    const annotatedScenarios: FireScenarioView[] = (annotations?.scenario_runs ?? [])
      .map((scenario, idx) => {
        const hydrant = hydrants.find((item) => item.id === scenario.hydrant_id) ?? hydrants[idx] ?? hydrants[0];
        const zone = hydrant ? zoneById.get(hydrant.zoneId) : defaultZone;
        const requiredFlowGpm = toFiniteNumber(scenario.required_flow_gpm);
        const availableFlowGpm = toFiniteNumber(scenario.available_flow_gpm) ?? hydrant?.availableFlowGpm ?? null;
        const staticPressurePsi = toFiniteNumber(scenario.static_pressure_psi) ?? hydrant?.staticPressurePsi ?? null;
        const residualTargetPsi = toFiniteNumber(scenario.residual_target_psi) ?? zone?.residualTargetPsi ?? null;
        const residualPressurePsi = toFiniteNumber(scenario.residual_pressure_psi) ?? hydrant?.residualPressurePsi ?? null;
        return {
          id: scenario.id || `fire-flow-${idx + 1}`,
          label: scenario.label || `${hydrant?.label || "Hydrant"} fire-flow`,
          hydrantId: hydrant?.id || scenario.hydrant_id || "",
          requiredFlowGpm,
          availableFlowGpm,
          staticPressurePsi,
          residualPressurePsi,
          residualTargetPsi,
          status: normalizeFlowStatus(scenario.status),
          networkType: hydrant ? networkByHydrant.get(hydrant.id) ?? "dead_end" : "dead_end",
          missingInputs: Array.isArray(scenario.missing_inputs) ? scenario.missing_inputs : [],
        };
      });
    const scenarios = annotatedScenarios;
    const selectedScenario =
      scenarios.find((scenario) => scenario.id === selectedFireScenarioId) ?? scenarios[0] ?? null;
    const selectedHydrant = selectedScenario
      ? hydrants.find((hydrant) => hydrant.id === selectedScenario.hydrantId) ?? null
      : null;
    const readiness = annotations?.readiness ?? null;
    const spacingChecks = annotations?.spacing_checks ?? [];
    const velocityChecks = annotations?.velocity_checks ?? [];
    const blockerCards = annotations?.blocker_cards ?? [];
    const hasData =
      hydrants.length > 0 ||
      networkSegments.length > 0 ||
      pressureZones.length > 0 ||
      scenarios.length > 0 ||
      spacingChecks.length > 0 ||
      velocityChecks.length > 0 ||
      blockerCards.length > 0 ||
      Boolean(readiness);
    return { hydrants, pressureZones, networkSegments, scenarios, selectedScenario, selectedHydrant, spacingChecks, velocityChecks, blockerCards, readiness, hasData };
  }, [buildingPlacements, planPreviewAnnotations?.water_fire_flow, selectedFireScenarioId, suggestedPlacements]);

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
      setHoveredAnnotation((current) => (current?.label === next?.label ? current : next));
      const nextPoint = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      setPoint((current) =>
        current &&
        Math.abs(current.x - nextPoint.x) < 6 &&
        Math.abs(current.y - nextPoint.y) < 6
          ? current
          : nextPoint,
      );
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

  const getObjectGeometryPoints = useCallback((item: BuildingPlacement): Array<[number, number]> => {
    if (Array.isArray(item.geometry) && item.geometry.length) {
      return (item.geometry as Array<[number, number]>).map((pt) => [pt[0], pt[1]]);
    }
    const x = item.x ?? 0;
    const y = item.y ?? 0;
    if (item.geometryType === "point") return [[x + item.w / 2, y + item.d / 2]];
    return [
      [x, y],
      [x + item.w, y],
      [x + item.w, y + item.d],
      [x, y + item.d],
    ];
  }, []);

  const getCadLayer = useCallback((item: BuildingPlacement) => {
    return String(item.meta?.cad_layer || item.meta?.layer || (item.type === "site" ? "C-SITE" : "C-DRAFT")).toUpperCase();
  }, []);

  const cadLayerOptions = useMemo(() => {
    const layers = new Set(["C-DRAFT", "C-SITE", "C-ROAD", "C-UTIL", "C-DRAIN", "C-BLDG", "C-SYMB", "C-ANNO"]);
    [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements].forEach((item) => layers.add(getCadLayer(item)));
    return Array.from(layers).sort();
  }, [buildingPlacements, cadEntityPreviewObjects, getCadLayer, suggestedPlacements]);
  const objectManagerRows = useMemo(() => {
    const rows = new Map<string, BuildingPlacement>();
    [...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements].forEach((item) => {
      if (!rows.has(item.id)) rows.set(item.id, item);
    });
    return Array.from(rows.values()).sort((a, b) => {
      const aHidden = a.meta?.ui_hidden ? 1 : 0;
      const bHidden = b.meta?.ui_hidden ? 1 : 0;
      if (aHidden !== bHidden) return aHidden - bHidden;
      if (a.type === "site" && b.type !== "site") return -1;
      if (b.type === "site" && a.type !== "site") return 1;
      return (a.label || a.id).localeCompare(b.label || b.id);
    });
  }, [buildingPlacements, cadEntityPreviewObjects, suggestedPlacements]);
  const objectManagerCounts = useMemo(
    () => ({
      total: objectManagerRows.length,
      visible: objectManagerRows.filter((item) => !item.meta?.ui_hidden && !hiddenCadLayers.includes(getCadLayer(item))).length,
      draft: objectManagerRows.filter((item) => item.source === "manual_drawn" || item.type === "custom" || item.meta?.engineering_status === "draft_review_required").length,
      generated: objectManagerRows.filter((item) => item.generated || item.source === "generated").length,
    }),
    [getCadLayer, hiddenCadLayers, objectManagerRows],
  );
  const getPreviewObjectDimensionsLabel = useCallback((item: BuildingPlacement) => {
    if (item.geometryType === "point") return "Point object";
    const width = Number.isFinite(item.w) ? item.w.toFixed(1) : "--";
    const depth = Number.isFinite(item.d) ? item.d.toFixed(1) : "--";
    return `${width} ft x ${depth} ft`;
  }, []);
  const getPreviewObjectSourceLabel = useCallback((item: BuildingPlacement) => {
    if (cadEntityPreviewObjects.some((candidate) => candidate.id === item.id)) return "Source-only CAD preview";
    if (item.generated || item.source === "generated") return "Generated";
    if (item.source === "manual_drawn") return "Manual draft";
    if (item.source === "detected_from_image" || item.source === "detected_from_gis") return "Detected source";
    if (item.source === "inferred") return "Inferred";
    return item.source ? item.source.replace(/_/g, " ") : "User";
  }, [cadEntityPreviewObjects]);
  const getPreviewObjectStatusLabel = useCallback((item: BuildingPlacement) => {
    const sourceState = resolveSourceState(item);
    if (item.type === "site") return siteLocked ? "Site boundary locked" : "Site boundary draft";
    if (item.locked) return "Locked";
    if (item.meta?.ui_hidden) return "Hidden";
    if (!item.placed) return "Unplaced";
    if (sourceState !== "verified") return sourceStateLabel(sourceState);
    return "Visible draft/review object";
  }, [siteLocked]);
  const previewObjectEditableSource = useCallback(
    (item: BuildingPlacement) =>
      buildingPlacements.some((candidate) => candidate.id === item.id) ||
      suggestedPlacements.some((candidate) => candidate.id === item.id),
    [buildingPlacements, suggestedPlacements],
  );
  const getPreviewObjectActionBlocker = useCallback(
    (item: BuildingPlacement | null, action: "rename" | "style" | "type" | "hide" | "delete" | "focus") => {
      if (!item) return `${action.toUpperCase()} blocked: select an object first.`;
      if (action === "focus") return null;
      if (item.type === "site") return `${action.toUpperCase()} blocked: site boundary is controlled from site setup/change-site tools.`;
      if (!previewObjectEditableSource(item)) return `${action.toUpperCase()} blocked: ${item.label || item.id} is source-only preview geometry.`;
      if (item.locked) return `${action.toUpperCase()} blocked: ${item.label || item.id} is locked. Unlock or use a draft copy before editing.`;
      if (action === "delete" && !buildingPlacements.some((candidate) => candidate.id === item.id)) {
        return "DELETE blocked: detected/source suggestions can be hidden or reviewed, but not deleted from the canonical canvas here.";
      }
      return null;
    },
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
      const minX = item.x ?? 0;
      const minY = item.y ?? 0;
      const maxX = minX + Math.max(item.w, 1);
      const maxY = minY + Math.max(item.d, 1);
      const centerX = (minX + maxX) / 2 / Math.max(lotWidth, 1);
      const centerY = (minY + maxY) / 2 / Math.max(lotHeight, 1);
      const objectShare = Math.max(
        Math.max(item.w, 1) / Math.max(lotWidth, 1),
        Math.max(item.d, 1) / Math.max(lotHeight, 1),
      );
      const focusScale = Math.min(Math.max(1 / Math.max(objectShare, 0.42), 0.96), 1.35);
      setCanvasView({
        scale: focusScale,
        offsetX: (0.5 - centerX) * 96,
        offsetY: (0.5 - centerY) * 96,
      });
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
      return resolveCadSnap(point, cadSegments, {
        enabled: cadSnapEnabled,
        ortho: cadOrthoEnabled,
        basePoint,
        threshold: Math.max(lotWidth, lotHeight, 1) * 0.018,
        gridSize: 5,
      });
    },
    [cadOrthoEnabled, cadSegments, cadSnapEnabled, lotHeight, lotWidth],
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
        recordUndoFeedback("blocked", "UNDO blocked: no draft CAD history is available.");
      }
      return;
    }
    applyCadHistorySnapshot(entry.before);
    setCadHistory((prev) => prev.slice(0, -1));
    setCadRedoStack((prev) => [...prev, entry]);
    recordUndoFeedback("applied", "UNDO restored the last draft CAD object edit.");
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
      recordRedoFeedback("blocked", "REDO blocked: no draft CAD redo history is available.");
      return;
    }
    applyCadHistorySnapshot(entry.after);
    setCadRedoStack((prev) => prev.slice(0, -1));
    setCadHistory((prev) => [...prev, entry]);
    recordRedoFeedback("applied", "REDO restored the draft CAD object edit.");
  }, [applyCadHistorySnapshot, cadRedoStack]);
  const parseCadNumber = useCallback((value: string, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }, []);
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
      const left = Math.min(windowRect.startX, windowRect.currentX);
      const right = Math.max(windowRect.startX, windowRect.currentX);
      const top = Math.min(windowRect.startY, windowRect.currentY);
      const bottom = Math.max(windowRect.startY, windowRect.currentY);
      const crossingSelect = windowRect.currentX < windowRect.startX;
      if (right - left < 8 || bottom - top < 8) return;
      const candidates = Array.from(
        previewRef.current.querySelectorAll<HTMLElement>("[data-cad-object-id]"),
      );
      const ids = candidates
        .filter((element) => {
          const rect = element.getBoundingClientRect();
          const intersects = rect.right >= left && rect.left <= right && rect.bottom >= top && rect.top <= bottom;
          if (crossingSelect) return intersects;
          return intersects && rect.left >= left && rect.right <= right && rect.top >= top && rect.bottom <= bottom;
        })
        .map((element) => element.dataset.cadObjectId)
        .filter((id): id is string => Boolean(id));
      const uniqueIds = Array.from(new Set(ids));
      const selectableIds = uniqueIds.filter((id) => {
        const item = visibleCadObjects.find((candidate) => candidate.id === id);
        return item && item.type !== "site" && !item.locked;
      });
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
  const parseCadPointToken = useCallback((token: string): [number, number] | null => {
    const match = token.trim().match(/^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/);
    if (!match) return null;
    const x = Number(match[1]);
    const y = Number(match[2]);
    return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
  }, []);
  const parseCadRelativePointToken = useCallback((token: string, basePoint: [number, number] | null): [number, number] | null => {
    if (!basePoint) return null;
    const trimmed = token.trim();
    const relativeMatch = trimmed.match(/^@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/);
    if (relativeMatch) {
      const dx = Number(relativeMatch[1]);
      const dy = Number(relativeMatch[2]);
      return Number.isFinite(dx) && Number.isFinite(dy)
        ? [Math.round((basePoint[0] + dx) * 1000) / 1000, Math.round((basePoint[1] + dy) * 1000) / 1000]
        : null;
    }
    const polarMatch = trimmed.match(/^@(-?\d+(?:\.\d+)?)<(-?\d+(?:\.\d+)?)$/);
    if (polarMatch) {
      const distance = Number(polarMatch[1]);
      const angleDeg = Number(polarMatch[2]);
      if (!Number.isFinite(distance) || !Number.isFinite(angleDeg)) return null;
      const radians = (angleDeg * Math.PI) / 180;
      return [
        Math.round((basePoint[0] + Math.cos(radians) * distance) * 1000) / 1000,
        Math.round((basePoint[1] + Math.sin(radians) * distance) * 1000) / 1000,
      ];
    }
    return null;
  }, []);
  const parseCadVectorToken = useCallback(
    (token: string): [number, number] | null => parseCadPointToken(token) ?? parseCadRelativePointToken(token, [0, 0]),
    [parseCadPointToken, parseCadRelativePointToken],
  );
  const parseCadPointTokens = useCallback(
    (tokens: string[]) => tokens.map((token) => parseCadPointToken(token)).filter((point): point is [number, number] => Boolean(point)),
    [parseCadPointToken],
  );
  const reviewRequiredCommandMeta = useCallback((command: string, extra: Record<string, unknown> = {}) => ({
    cad_command: command.toUpperCase(),
    cad_command_source: "typed_command_line",
    source: "manual_drawn",
    engineering_status: "draft_review_required",
    review_status: "engineer_review_required",
    handoff_status: "draft_review_required",
    construction_release_allowed: false,
    ...extra,
  }), []);
  const createCadCommandGeometry = useCallback(
    (
      command: string,
      mode: "polyline" | "polygon" | "rect" | "point",
      points: Array<[number, number]>,
      options: { label?: string; meta?: Record<string, unknown>; minPoints?: number } = {},
    ) => {
      const minPoints = options.minPoints ?? (mode === "point" ? 1 : mode === "rect" ? 2 : mode === "polygon" ? 3 : 2);
      if (!canDrawObjects) {
        pushCadCommandFeedback(command, "blocked", `${command.toUpperCase()} blocked: lock a scaled site boundary before creating draft CAD geometry.`);
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
        meta: reviewRequiredCommandMeta(command, options.meta),
      });
      pushCadCommandFeedback(command, "applied", `${command.toUpperCase()} created manual_drawn draft_review_required geometry. Review and rerun affected systems before relying on it.`);
      return true;
    },
    [canDrawObjects, onCreateCustomGeometry, pushCadCommandFeedback, reviewRequiredCommandMeta],
  );
  const transformSelectedCadObjects = useCallback(
    (kind: "move" | "rotate" | "scale" | "flip_horizontal" | "flip_vertical", valueOverride?: string) => {
      if (!selectedCadIds.length) {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: select one or more editable draft CAD objects first.`);
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
    [buildingPlacements, cadTransformValue, parseCadNumber, pushCadCommandFeedback, selectedCadIds, updateCadObject],
  );
  const moveSelectedCadObjectsByVector = useCallback(
    (dx: number, dy: number) => {
      if (!selectedCadIds.length) {
        pushCadCommandFeedback("MOVE", "blocked", "MOVE blocked: select one or more editable draft CAD objects first.");
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
        pushCadCommandFeedback("COPY", "blocked", "COPY blocked: select one or more editable draft CAD objects first.");
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
          label: `${target.label || "CAD object"} Copy`,
          meta: reviewRequiredCommandMeta("COPY", {
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
    [buildingPlacements, getCadLayer, getObjectGeometryPoints, onCreateCustomGeometry, pushCadCommandFeedback, reviewRequiredCommandMeta, selectedCadIds],
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
          `${command} blocked: select at least ${minimum} editable draft CAD objects first.`,
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
        pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: select one editable draft CAD object with geometry first.");
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
            label: `${selectedCadObject.label || "CAD object"} Array ${row + 1}-${column + 1}`,
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
        ? `${selectedTargets[0].label || "CAD"} + ${selectedTargets[1].label || "CAD"} Join`
        : `Joined CAD Object ${selectedTargets.length}`;
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
      meta: reviewRequiredCommandMeta("JOIN", {
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
    reviewRequiredCommandMeta,
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
  }, [cadCoordinateDraft.x, cadCoordinateDraft.y, lotHeight, lotWidth, onSetPreviewInteraction, parseCadNumber, selectedCadObject, updateCadObject]);
  const applySelectedCadLayer = useCallback(() => {
    if (!selectedCadIds.length) {
      pushCadCommandFeedback("LAYER", "blocked", "LAYER blocked: select one or more editable draft CAD objects first.");
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
      pushCadCommandFeedback("LAYER", "blocked", "LAYER blocked: selected objects are locked or not editable draft CAD objects.");
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
  }, [cadOffsetDistance, parseCadNumber, selectedCadObject, updateCadObject]);
  const offsetSelectedCadObjectBy = useCallback((valueOverride?: string) => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("OFFSET", "blocked", "OFFSET blocked: select one editable draft CAD object first.");
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
  }, [cadOffsetDistance, parseCadNumber, pushCadCommandFeedback, selectedCadObject, updateCadObject]);
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
    [cadSegments, cadTransformValue, lotHeight, lotWidth, parseCadNumber, pushCadCommandFeedback, selectedCadObject, updateCadObject],
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
  }, [cadFilletRadius, parseCadNumber, pushCadCommandFeedback, selectedCadObject, selectedVertex, updateCadObject]);

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
      pushCadCommandFeedback("PROPERTIES", "blocked", "PROPERTIES blocked: select one editable draft CAD object first.");
      return;
    }
    const safeName = cadPropertyDraft.name.trim() || selectedCadObject.label || "CAD object";
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
  }, [cadCoordinateDraft.x, cadCoordinateDraft.y, cadSymbolDraft, lotHeight, lotWidth, onCreateCustomGeometry, parseCadNumber, pushCadCommandFeedback]);

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
    const commandAliases: Record<string, string> = {
      L: "LINE",
      PL: "PLINE",
      REC: "RECTANGLE",
      RECT: "RECTANGLE",
      B: "BOX",
      C: "CIRCLE",
      A: "ARC",
      AR: "ARRAY",
      AL: "ALIGN",
      DALIGN: "DISTRIBUTE",
      DISTRIB: "DISTRIBUTE",
      M: "MOVE",
      RO: "ROTATE",
      SC: "SCALE",
      CO: "COPY",
      O: "OFFSET",
      TR: "TRIM",
      EX: "EXTEND",
      F: "FILLET",
      J: "JOIN",
      BR: "SPLIT",
      BREAK: "SPLIT",
      CL: "CLOSE",
      H: "HATCH",
      BH: "HATCH",
      REV: "REVERSE",
      MI: "MIRROR",
      E: "ERASE",
      D: "DIM",
      DI: "DIST",
      T: "TEXT",
      LA: "LAYER",
      SEL: "SELECT",
    };
    const commandKey = commandAliases[command] ?? command;
    const knownCommands = new Set([
      "LINE",
      "PLINE",
      "RECTANGLE",
      "RECT",
      "BOX",
      "CIRCLE",
      "ARC",
      "ARRAY",
      "ALIGN",
      "DISTRIBUTE",
      "DIST",
      "MEASURE",
      "MOVE",
      "ROTATE",
      "SCALE",
      "COPY",
      "DELETE",
      "ERASE",
      "OFFSET",
      "TRIM",
      "EXTEND",
      "FILLET",
      "JOIN",
      "SPLIT",
      "BREAK",
      "CLOSE",
      "OPEN",
      "REVERSE",
      "HATCH",
      "MIRROR",
      "FLIP",
      "DIM",
      "TEXT",
      "LAYER",
      "SELECT",
      "SEL",
      "SNAP",
      "ORTHO",
      "FINISH",
      "DONE",
      "CANCEL",
      "ESC",
    ]);
    const pointArgs = parseCadPointTokens(args.filter((arg) => arg.toLowerCase() !== "selected"));
    const firstValue = args.find((arg) => arg.toLowerCase() !== "selected") ?? cadTransformValue;
    const selectedRequested = args.some((arg) => arg.toLowerCase() === "selected");
    const activeCanvasDrawMode =
      drawMode === "site" ||
      drawMode === "polyline" ||
      drawMode === "polygon" ||
      drawMode === "rect";
    if (activeCanvasDrawMode && !cadActiveCommand && !knownCommands.has(commandKey)) {
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

    if (cadActiveCommand && !knownCommands.has(command)) {
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
        pushCadCommandFeedback("DELETE", "blocked", "DELETE blocked: select one unlocked draft CAD object first.");
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
        pushCadCommandFeedback("LAYER", "applied", "LAYER ALL showed every draft CAD layer.");
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
    parseCadNumber,
    parseCadPointToken,
    parseCadPointTokens,
    parseCadRelativePointToken,
    parseCadVectorToken,
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
    setDraftPoints([]);
    setDraftPreviewPoint(null);
    lastDraftPreviewPointRef.current = null;
    setCadActiveCommand(null);
  }, []);

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
    const rectFinishPreviewPoint = draftPreviewPoint ?? lastDraftPreviewPointRef.current;
    const effectivePoints =
      drawMode === "rect" && draftPoints.length === 1 && rectFinishPreviewPoint
        ? [draftPoints[0], rectFinishPreviewPoint]
        : draftPoints;
    const minPoints = drawMode === "site" || drawMode === "polygon" ? 3 : 2;
    if (effectivePoints.length < minPoints) {
      const message =
        drawMode === "site"
          ? `FINISH blocked: site boundary needs at least three points; ${effectivePoints.length} selected.`
          : drawMode === "polygon"
            ? `FINISH blocked: Add Area needs at least three points; ${effectivePoints.length} selected.`
            : drawMode === "rect"
              ? `FINISH blocked: Add Box needs two opposite corners; ${effectivePoints.length} selected.`
              : `FINISH blocked: Add Line needs at least two points; ${effectivePoints.length} selected.`;
      pushCadCommandFeedback("FINISH", "blocked", message);
      return;
    }
    if (drawMode === "site" || drawMode === "polygon") {
      const cleaned = cleanupPolygon(effectivePoints, 0.5);
      if (!cleaned.ok) {
        setCadCommandStatus(`POLYGON blocked: ${cleaned.reason}`);
        return;
      }
      const validation = validatePolygon(cleaned.value);
      if (!validation.ok) {
        setCadCommandStatus(`POLYGON blocked: ${validation.issues.join(", ")}`);
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
          : "AREA created manual_drawn draft_review_required geometry.",
      );
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setCadActiveCommand(null);
      setDrawMode("select");
      return;
    }
    onCreateCustomGeometry({ mode: drawMode, points: effectivePoints });
    pushCadCommandFeedback(
      drawMode === "rect" ? "BOX" : "LINE",
      "applied",
      `${drawMode === "rect" ? "BOX" : "LINE"} created manual_drawn draft_review_required geometry.`,
    );
    clearDraftGeometry();
    setDrawMode("select");
  }, [
	    clearDraftGeometry,
	    draftPoints,
      draftPreviewPoint,
	    drawMode,
    onCreateCustomGeometry,
    onCreateSiteBoundary,
    pushCadCommandFeedback,
  ]);

  const draftPointCount = draftPoints.length;
  const finishDraftMinPoints = drawMode === "site" || drawMode === "polygon" ? 3 : 2;
  const finishDraftEffectivePointCount =
    drawMode === "rect" && draftPointCount === 1 && (draftPreviewPoint || lastDraftPreviewPointRef.current) ? 2 : draftPointCount;
  const canFinishDraftGeometry =
    drawMode !== "select" &&
    drawMode !== "pan" &&
    drawMode !== "point" &&
    finishDraftEffectivePointCount >= finishDraftMinPoints;
  const finishDraftBlockedReason =
    drawMode !== "select" && drawMode !== "pan" && drawMode !== "point" && finishDraftEffectivePointCount < finishDraftMinPoints
      ? drawMode === "site"
        ? "Draw at least three boundary points before Finish."
        : drawMode === "polygon"
          ? "Draw at least three area points before Finish."
          : "Draw at least two line points before Finish."
      : null;
  const activeDrawToolLabel =
    drawMode === "site"
      ? "Draw Site Boundary"
      : drawMode === "polyline"
        ? "Add Line"
        : drawMode === "polygon"
          ? "Add Area"
          : drawMode === "rect"
            ? "Add Box"
            : drawMode === "point"
              ? "Add Point"
              : drawMode === "pan"
                ? "Pan"
                : "Select";
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
      const basePoint = draftPoints.length
        ? { x: draftPoints[draftPoints.length - 1][0], y: draftPoints[draftPoints.length - 1][1] }
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
        if (!draftPoints.length) {
          setDraftPoints([point]);
          return true;
        }
        onCreateCustomGeometry({ mode: "rect", points: [draftPoints[0], point] });
        pushCadCommandFeedback("BOX", "applied", "BOX created manual_drawn draft_review_required geometry.");
        setDrawMode("select");
        setDraftPreviewPoint(null);
        setDraftPoints([]);
        return true;
      }
      const nextPoints = [...draftPoints, point];
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
          pushCadCommandFeedback("AREA", "applied", "AREA created manual_drawn draft_review_required geometry.");
        } else {
          onCreateCustomGeometry({ mode: "polyline", points: nextPoints });
          pushCadCommandFeedback("LINE", "applied", "LINE created manual_drawn draft_review_required geometry.");
        }
        setDrawMode("select");
        setDraftPreviewPoint(null);
        setDraftPoints([]);
        setDrawAutoFinishPointCount(null);
        setCadActiveCommand(null);
        return true;
      }
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
        setSelectedVertex(null);
        setCadSelectionSet([]);
      }
      const label =
        mode === "polyline"
          ? "Add Line"
          : mode === "polygon"
            ? "Add Area"
            : mode === "rect"
              ? "Add Box"
              : mode === "point"
                ? "Add Point"
                : mode === "site"
                  ? "Draw Site Boundary"
                  : mode === "pan"
                    ? "Pan"
                    : "Select";
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

  useEffect(() => {
    if (!mapAvailable || !mapOverlayEnabled) return;
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
  }, [mapAvailable, mapBearing, mapOverlayEnabled, mapPitch, mapboxToken]);

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
      map.off("move", requestMapOverlayUpdate);
      map.off("zoom", requestMapOverlayUpdate);
      map.off("pitch", requestMapOverlayUpdate);
      map.off("rotate", requestMapOverlayUpdate);
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
      fullscreenMap.setTerrain({ source: "mapbox-dem", exaggeration: 1.0 });
      fullscreenMap.resize();
      setMapRevision((value) => value + 1);
    });
    return () => {
      fullscreenMap.off("move", requestMapOverlayUpdate);
      fullscreenMap.off("zoom", requestMapOverlayUpdate);
      fullscreenMap.off("pitch", requestMapOverlayUpdate);
      fullscreenMap.off("rotate", requestMapOverlayUpdate);
    };
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
    if (!supportsParkingModuleRendering(item)) return [];
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

    const parkingModules = parking.flatMap((item) => buildParkingModules(item, accessPoints));
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
    useLightHighQuality,
    waterFireFlow,
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
  }, [setFocusTransform]);

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
    const nextTransform = { scale: Math.min(Math.max(scale, 1), 1.6), tx: centerX, ty: centerY };
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
  const activePreviewMode: "2d" | "3d" = previewMode;
  return (
    <div className="civora-preview-panel flex h-full min-w-0 flex-col overflow-x-hidden overflow-y-auto rounded-xl border border-slate-200 bg-white/92 p-2 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.45)] backdrop-blur sm:p-3">
      <div className="hidden">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-md bg-slate-950 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
              Design Canvas
            </span>
            <div className="flex min-w-0 max-w-full flex-wrap items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
              <button
                type="button"
                data-testid="preview-panel-quality-standard"
                onClick={() => {
                  if (previewQuality === "standard") return;
                  onQueuePreviewRefresh("Requesting standard-quality preview...");
                  onSetPreviewQuality("standard");
                }}
                className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                  previewQuality === "standard" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Standard
              </button>
              <button
                type="button"
                data-testid="preview-panel-quality-high"
                onClick={() => {
                  if (previewQuality === "high") return;
                  onQueuePreviewRefresh("Requesting high-quality preview...");
                  onSetPreviewQuality("high");
                }}
                className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                  previewQuality === "high" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                High
              </button>
              <button
                type="button"
                data-testid="preview-panel-mode-2d"
                onClick={() => onSetPreviewMode("2d")}
                className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                  previewMode === "2d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                2D
              </button>
              <button
                type="button"
                data-testid="preview-panel-mode-3d"
                onClick={() => {
                  if (!canUse3D) return;
                  onSetPreviewMode("3d");
                }}
                className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                  previewMode === "3d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                }`}
                disabled={!canUse3D}
              >
                3D
              </button>
              <button
                type="button"
                data-testid="preview-panel-map-toggle"
                onClick={() => setMapOverlayEnabled((value) => !value)}
                disabled={!mapAvailable}
                title={mapAvailable ? "Toggle satellite/map context" : "Map context needs an applied geocoded address"}
                className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                  mapOverlayEnabled
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                } disabled:cursor-not-allowed disabled:opacity-45`}
              >
                Map {mapOverlayEnabled ? "On" : "Off"}
              </button>
              <button
                type="button"
                data-testid="preview-panel-interaction-edit"
                aria-label="Use canvas edit tool"
                onClick={() => onSetPreviewInteraction("edit")}
                className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                  allowEdits ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Edit
              </button>
            </div>
            <span className="inline-flex items-center rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              {previewQuality === "high" ? "High Quality" : "Standard"}
            </span>
            {isHighQuality ? (
              <span
                data-testid="high-quality-preview-only-label"
                className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-800"
              >
                Visual preview only. Presentation/realism mode. Canonical geometry unchanged. Not engineering evidence.
              </span>
            ) : null}
            {isHighQuality ? (
              <div
                data-testid="ai-realism-toggle-header"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1"
                aria-label="AI Visualization toggle"
              >
                <span className="px-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">AI Visualization</span>
                <button
                  type="button"
                  data-testid="ai-realism-off-header"
                  onClick={setAiVisualizationOff}
                        aria-pressed={!aiRealismEnabled}
                  className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                    !aiRealismEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  Off
                </button>
                <button
                  type="button"
                  data-testid="ai-realism-on-header"
                  onClick={setAiVisualizationOn}
                        aria-pressed={aiRealismEnabled}
                  className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                    aiRealismEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  On
                </button>
              </div>
            ) : null}
            {useLightHighQuality ? (
              <span
                data-testid="high-quality-lite-label"
                className="inline-flex items-center rounded-md border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-sky-800"
              >
                High Quality Lite: simplified labels and effects for this viewport.
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
            Visual anchoring keeps objects consistent in the model view. High Quality is a presentation preview only
            and never engineering evidence. AI Realism, when enabled, is an AI visualization from the current review layout
            and is not source-confidence evidence or used for QA, compliance, quantities, engineering generation, or release.
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
        <div className="flex min-w-0 flex-wrap gap-2 xl:justify-end">
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
            disabled={busy}
            title={exportBlockReason || "Download a DXF review export"}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            Export DXF
          </button>
          <button
            type="button"
            onClick={onExportReport}
            disabled={busy}
            title={exportBlockReason || "Download an engineer-review package report"}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileText className="h-4 w-4" />
            Export Report
          </button>
          {exportBlockReason ? (
            <p className="w-full text-right text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700">
              Export note: {exportBlockReason}
            </p>
          ) : null}
        </div>
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] sm:p-3">
          <div className="relative isolate z-[220] mb-3 overflow-visible rounded-xl border border-slate-200 bg-white/95 shadow-sm">
            <div className="hidden">
              <div className="pointer-events-auto relative z-[120] flex min-w-0 max-w-full flex-wrap items-center gap-2">
                <span className="inline-flex items-center rounded-md bg-slate-950 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
                  Canvas
                </span>
                <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {previewQuality === "high" ? "High Quality" : "Standard"} / {previewMode.toUpperCase()} / {coordinateModeLabel(coordinateMode)}
                </span>
                <div className="hidden">
                  <button
                    type="button"
                    data-testid="preview-inner-quality-standard"
                    onClick={() => {
                      if (previewQuality === "standard") return;
                      onQueuePreviewRefresh("Requesting standard-quality preview...");
                      onSetPreviewQuality("standard");
                    }}
                    className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                      previewQuality === "standard" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                    }`}
                  >
                    Standard
                  </button>
                  <button
                    type="button"
                    data-testid="preview-inner-quality-high"
                    onClick={() => {
                      if (previewQuality === "high") return;
                      onQueuePreviewRefresh("Requesting high-quality preview...");
                      onSetPreviewQuality("high");
                    }}
                    className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                      previewQuality === "high" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                    }`}
                  >
                    High
                  </button>
                  <button
                    type="button"
                    data-testid="preview-inner-mode-2d"
                    onClick={() => onSetPreviewMode("2d")}
                    className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                      previewMode === "2d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                    }`}
                  >
                    2D
                  </button>
                  <button
                    type="button"
                    data-testid="preview-inner-mode-3d"
                    onClick={() => {
                      if (!canUse3D) return;
                      onSetPreviewMode("3d");
                    }}
                    className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                      previewMode === "3d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                    }`}
                  disabled={!canUse3D}
                >
                  3D
                </button>
                <button
                  type="button"
                  data-testid="preview-inner-map-toggle"
                  onClick={() => setMapOverlayEnabled((value) => !value)}
                  disabled={!mapAvailable}
                  title={mapAvailable ? "Toggle satellite/map context" : "Map context needs an applied geocoded address"}
                  className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                    mapOverlayEnabled
                      ? "border-slate-900 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-600"
                  } disabled:cursor-not-allowed disabled:opacity-45`}
                >
                  Map {mapOverlayEnabled ? "On" : "Off"}
                </button>
	                <button
	                  type="button"
	                  data-testid="preview-inner-interaction-edit"
	                    aria-label="Use canvas edit tool"
	                    onClick={() => onSetPreviewInteraction("edit")}
                    className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                      allowEdits ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                    }`}
	                  >
	                    Edit
	                  </button>
	                  {previewMode === "2d" ? (
	                    <button
	                      type="button"
	                      data-testid="draw-site-boundary-toolbar-hidden"
	                      aria-pressed={drawMode === "site"}
	                      title={siteLocked ? "Site is locked. Use Change Site before drawing a new boundary." : "Draw the site boundary"}
	                      onClick={() => {
	                        if (siteLocked) {
	                          pushCadCommandFeedback("SITE", "blocked", "SITE boundary is locked. Use Change Site before drawing a replacement boundary.");
	                          return;
	                        }
	                        activateDrawTool("site");
	                      }}
	                      className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
	                        drawMode === "site"
	                          ? "border-slate-900 bg-slate-950 text-white"
	                          : siteLocked
	                            ? "border-slate-200 bg-white text-slate-600"
	                            : "border-amber-200 bg-amber-50 text-amber-800"
	                      }`}
	                    >
	                      Draw Site Boundary
	                    </button>
	                  ) : null}
	                  {previewMode === "2d" && siteLocked && onUnlockSite ? (
	                    <button
	                      type="button"
	                      data-testid="change-site-boundary-toolbar-hidden"
	                      aria-label="Change Site Boundary"
	                      onClick={() => {
	                        onUnlockSite();
	                        clearDraftGeometry();
	                        setDrawMode("select");
	                        onSetPreviewInteraction("edit");
	                      }}
	                      className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600"
	                    >
	                      Change Site
	                    </button>
	                  ) : null}
	                  {previewMode === "2d"
	                    ? ([
	                        { mode: "polyline" as DrawMode, label: "Add Line", disabledLabel: drawObjectsDisabledLabel },
	                        { mode: "polygon" as DrawMode, label: "Add Area", disabledLabel: drawObjectsDisabledLabel },
	                        { mode: "rect" as DrawMode, label: "Add Box", disabledLabel: drawObjectsDisabledLabel },
	                        { mode: "point" as DrawMode, label: "Add Point", disabledLabel: drawObjectsDisabledLabel },
	                      ]).map((item) => {
	                        const active = drawMode === item.mode;
	                        const disabled = !canDrawObjects;
	                        return (
	                          <button
	                            key={`canvas-primary-draw-${item.mode}`}
	                            type="button"
	                            aria-pressed={active}
	                            title={disabled ? item.disabledLabel : item.label}
	                            data-blocked={disabled ? "true" : undefined}
	                            onClick={() => activateDrawTool(item.mode, disabled ? item.disabledLabel : undefined)}
	                            className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
	                              active
	                                ? "border-slate-900 bg-slate-950 text-white"
	                                : disabled
	                                  ? "border-amber-200 bg-amber-50 text-amber-800"
	                                  : "border-slate-200 bg-white text-slate-600"
	                            }`}
	                          >
	                            {item.label}
	                          </button>
	                        );
	                      })
	                    : null}
	                </div>
                {isHighQuality ? (
                  <span className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-800">
                    Visual preview only. Canonical geometry unchanged. Not engineering evidence.
                  </span>
                ) : null}
                {useLightHighQuality ? (
                  <span className="inline-flex items-center rounded-md border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-sky-800">
                    High Quality Lite
                  </span>
                ) : null}
              </div>
              <div className="pointer-events-auto flex min-w-0 max-w-full flex-wrap items-center gap-2">
                {showMap ? (
                  <button
                    type="button"
                    onClick={() => setMapLocked((prev) => !prev)}
                    className={`inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-semibold transition ${
                      mapLocked
                        ? "border-slate-900 bg-slate-950 text-white"
                        : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {mapLocked ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
                    {mapLocked ? "Unlock Map" : "Lock Map"}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => {
                    setFocusTransform(null);
                    onResetView?.();
                  }}
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  <RotateCcw className="h-4 w-4" />
                  Reset
                </button>
                <button
                  type="button"
                  onClick={onRefreshPreview}
                  disabled={busy}
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </button>
                {analysisHighlight ? (
                  <button
                    type="button"
                    onClick={() => {
                      setFocusTransform(null);
                      onClearHighlights?.();
                    }}
                    className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    <X className="h-4 w-4" />
                    Clear
                  </button>
                ) : null}
              </div>
            </div>
            <div className="pointer-events-none relative z-[220] flex min-w-0 max-w-full flex-wrap items-stretch gap-2 px-3 py-2">
              <section className="hidden">
                <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">View</span>
                <button
                  type="button"
                  data-testid="preview-toolbar-mode-2d"
                  onClick={() => onSetPreviewMode("2d")}
                  className={`inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold ${
                    activePreviewMode === "2d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  2D
                </button>
                <button
                  type="button"
                  data-testid="preview-toolbar-mode-3d"
                  onClick={() => {
                    if (!canUse3D) return;
                    onSetPreviewMode("3d");
                  }}
                  className={`inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold ${
                    previewMode === "3d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                  disabled={!canUse3D}
                >
                  3D
                </button>
                <button
                  type="button"
                  data-testid="preview-toolbar-map-toggle"
                  onClick={() => setMapOverlayEnabled((value) => !value)}
                  disabled={!mapAvailable}
                  title={mapAvailable ? "Toggle satellite/map context" : "Map context needs an applied geocoded address"}
                  className={`inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold ${
                    mapOverlayEnabled
                      ? "border-slate-900 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-600"
                  } disabled:cursor-not-allowed disabled:opacity-45`}
                >
                  Map {mapOverlayEnabled ? "On" : "Off"}
                </button>
                <button
                  type="button"
                  data-testid="preview-toolbar-quality-standard"
                  onClick={() => {
                    if (previewQuality === "standard") return;
                    onQueuePreviewRefresh("Requesting standard-quality preview...");
                    onSetPreviewQuality("standard");
                  }}
                  className={`inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold ${
                    previewQuality === "standard" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  Standard
                </button>
                <button
                  type="button"
                  data-testid="preview-toolbar-quality-high"
                  onClick={() => {
                    if (previewQuality === "high") return;
                    onQueuePreviewRefresh("Requesting high-quality preview...");
                    onSetPreviewQuality("high");
                  }}
                  className={`inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold ${
                    previewQuality === "high" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  High
                </button>
              </section>
              {previewMode === "2d" ? (
                <section className="hidden" data-testid="canvas-draw-controls">
                  <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Draw</span>
                  <button
                    type="button"
                    data-testid="draw-site-boundary-toolbar-secondary"
                    aria-pressed={drawMode === "site"}
                    title={siteLocked ? "Site is locked. Use Change Site before drawing a new boundary." : "Draw the site boundary"}
                    onClick={() => {
                      if (siteLocked) {
                        pushCadCommandFeedback("SITE", "blocked", "SITE boundary is locked. Use Change Site before drawing a replacement boundary.");
                        return;
                      }
                      activateDrawTool("site");
                    }}
                    className={`inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold ${
                      drawMode === "site"
                        ? "border-slate-900 bg-slate-950 text-white"
                        : siteLocked
                          ? "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                          : "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
                    }`}
                  >
                    Draw Site Boundary
                  </button>
                  {siteLocked && onUnlockSite ? (
                    <button
                      type="button"
                      data-testid="change-site-boundary-toolbar-secondary"
                      aria-label="Change Site Boundary"
                      onClick={() => {
                        onUnlockSite();
                        clearDraftGeometry();
                        setDrawMode("select");
                        onSetPreviewInteraction("edit");
                      }}
                      className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      Change Site
                    </button>
                  ) : null}
                  {[
                    { mode: "polyline" as DrawMode, label: "Add Line", disabledLabel: drawObjectsDisabledLabel },
                    { mode: "polygon" as DrawMode, label: "Add Area", disabledLabel: drawObjectsDisabledLabel },
                    { mode: "rect" as DrawMode, label: "Add Box", disabledLabel: drawObjectsDisabledLabel },
                    { mode: "point" as DrawMode, label: "Add Point", disabledLabel: drawObjectsDisabledLabel },
                  ].map((item) => {
                    const active = drawMode === item.mode;
                    const disabled = !canDrawObjects;
                    return (
                      <button
                        key={`canvas-draw-${item.mode}`}
                        type="button"
                        aria-pressed={active}
                        title={disabled ? item.disabledLabel : item.label}
                        data-blocked={disabled ? "true" : undefined}
                        onClick={() => activateDrawTool(item.mode, disabled ? item.disabledLabel : undefined)}
                        className={`inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold ${
                          active
                            ? "border-slate-900 bg-slate-950 text-white"
                            : disabled
                              ? "border-amber-200 bg-amber-50 text-amber-800"
                              : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        {item.label}
                      </button>
                    );
                  })}
                  {drawMode !== "select" ? (
                    <>
                      {drawMode !== "point" && drawMode !== "pan" ? (
                        <button
                          type="button"
                          onClick={finishDraftGeometry}
                          disabled={!canFinishDraftGeometry}
                          title={finishDraftBlockedReason ?? "Finish drawn geometry"}
                          className={`inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold ${
                            !canFinishDraftGeometry
                              ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-800"
                              : "border-slate-900 bg-slate-950 text-white"
                          }`}
                        >
                          Finish
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => {
                          clearDraftGeometry();
                          setDrawMode("select");
                          setActiveSnapPoint(null);
                          setCadCommandStatus("Cancelled active drawing tool.");
                        }}
                        className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                      >
                        Cancel
                      </button>
                    </>
                  ) : null}
                </section>
              ) : null}
              {previewMode === "2d" ? (
                <section className={`${allowEdits && selectedObject ? "pointer-events-auto relative z-[230] flex" : "hidden"} min-w-[280px] max-w-full flex-wrap items-center gap-1.5 rounded-lg border border-slate-200 bg-white/94 p-1 shadow-[0_18px_45px_-34px_rgba(15,23,42,0.65)] backdrop-blur`} data-testid="preview-object-manager">
                  <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Objects</span>
                  {selectedObject?.label ? (
                    <span className="max-w-[180px] truncate rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs font-semibold text-slate-700">
                      {selectedObject.label}
                    </span>
                  ) : null}
                  <select
                    aria-label="Object Manager object list"
                    data-testid="preview-object-manager-list"
                    value={selectedObject?.id ?? selectedBuildingId ?? ""}
                    onChange={(event) => {
                      const id = event.target.value || null;
                      setManagedObjectId(id);
                      onSelectBuilding(id);
                      setCadSelectionSet(id ? [id] : []);
                      setSelectedVertex(null);
                    }}
                    className="h-9 min-w-[168px] max-w-[240px] rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700"
                  >
                    <option value="">
                      {objectManagerCounts.total
                        ? `${objectManagerCounts.total} objects: ${objectManagerCounts.visible} visible`
                        : "No objects"}
                    </option>
                    {objectManagerRows.map((item) => (
                      <option key={`manager-option-${item.id}`} value={item.id}>
                        {item.label || item.id}
                      </option>
                    ))}
                  </select>
                  <span className="hidden h-9 items-center rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 lg:inline-flex" data-testid="preview-object-manager-counts">
                    {objectManagerCounts.draft} draft / {objectManagerCounts.generated} generated
                  </span>
                  {selectedObject ? (
                    <>
                      <input
                        aria-label="Rename selected object"
                        data-testid="preview-object-manager-rename"
                        value={selectedObject.label || ""}
                        onChange={(event) => {
                          const blocker = getPreviewObjectActionBlocker(selectedObject, "rename");
                          if (blocker) {
                            setCadCommandStatus(blocker);
                            return;
                          }
                          updatePreviewManagedObject(selectedObject, { label: event.target.value });
                        }}
                        className="h-9 min-w-[128px] max-w-[190px] rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-800"
                      />
                      <span className="hidden h-9 max-w-[190px] items-center truncate rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 xl:inline-flex" data-testid="preview-object-manager-selected-status">
                        {getPreviewObjectDimensionsLabel(selectedObject)}
                      </span>
                      <details className="hidden h-9 max-w-[210px] items-center rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 xl:inline-flex">
                        <summary className="cursor-pointer list-none whitespace-nowrap">Details</summary>
                        <div className="absolute right-4 top-24 z-[140] w-72 rounded-xl border border-slate-200 bg-white p-3 text-left normal-case tracking-normal text-slate-600 shadow-xl">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Selected object</p>
                          <p className="mt-2 text-xs font-semibold text-slate-800">{getPreviewObjectSourceLabel(selectedObject)}</p>
                          <p className="mt-1 text-xs text-slate-500">{getPreviewObjectStatusLabel(selectedObject)}</p>
                          <p className="mt-1 text-xs text-slate-500">{getPreviewObjectDimensionsLabel(selectedObject)}</p>
                        </div>
                      </details>
                      <input
                        type="color"
                        aria-label="Change selected object color"
                        data-testid="preview-object-manager-color"
                        value={String(selectedObject.meta?.ui_color || selectedObject.meta?.color || "#64748b")}
                        onChange={(event) => {
                          const blocker = getPreviewObjectActionBlocker(selectedObject, "style");
                          if (blocker) {
                            setCadCommandStatus(blocker);
                            return;
                          }
                          updatePreviewManagedObject(selectedObject, {
                            meta: { ...(selectedObject.meta ?? {}), ui_color: event.target.value },
                          });
                        }}
                        className="h-9 w-10 rounded-md border border-slate-200 bg-white p-1"
                      />
                      <select
                        aria-label="Change selected object layer or type"
                        data-testid="preview-object-manager-type"
                        value={selectedObject.type ?? "custom"}
                        onChange={(event) => {
                          const blocker = getPreviewObjectActionBlocker(selectedObject, "type");
                          if (blocker) {
                            setCadCommandStatus(blocker);
                            return;
                          }
                          const type = event.target.value as BuildingPlacement["type"];
                          updatePreviewManagedObject(selectedObject, {
                            type,
                            meta: { ...(selectedObject.meta ?? {}), cad_layer: getCadLayer(selectedObject) },
                          });
                        }}
                        className="h-9 max-w-[132px] rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold capitalize text-slate-700"
                      >
                        {[
                          "building",
                          "road",
                          "parking",
                          "sidewalk",
                          "basin",
                          "utility_corridor",
                          "hydrant",
                          "inlet",
                          "manhole",
                          "custom",
                        ].map((type) => (
                          <option key={`preview-object-type-${type}`} value={type}>
                            {type.replace(/_/g, " ")}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        aria-label="Focus selected object"
                        data-testid="preview-object-manager-focus"
                        onClick={() => focusPreviewManagedObject(selectedObject)}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                      >
                        <Maximize2 className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        aria-label={selectedObject.meta?.ui_hidden ? "Show selected object" : "Hide selected object"}
                        data-testid="preview-object-manager-visibility"
                        onClick={() => {
                          const blocker = getPreviewObjectActionBlocker(selectedObject, "hide");
                          if (blocker) {
                            setCadCommandStatus(blocker);
                            return;
                          }
                          updatePreviewManagedObject(selectedObject, {
                            meta: {
                              ...(selectedObject.meta ?? {}),
                              ui_hidden: !Boolean(selectedObject.meta?.ui_hidden),
                            },
                          });
                        }}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                      >
                        {selectedObject.meta?.ui_hidden ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                      <button
                        type="button"
                        aria-label="Delete selected object"
                        data-testid="preview-object-manager-delete"
                        onClick={() => {
                          const blocker = getPreviewObjectActionBlocker(selectedObject, "delete");
                          if (blocker) {
                            setCadCommandStatus(blocker);
                            return;
                          }
                          setLastRectEdit({
                            id: selectedObject.id,
                            snapshot: { ...selectedObject },
                            action: "delete",
                            ts: Date.now(),
                          });
                          onRemoveBuilding(selectedObject.id);
                        }}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-rose-200 bg-white text-rose-600 hover:bg-rose-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </>
                  ) : null}
                </section>
              ) : null}
              {previewMode === "2d" ? (
	                <section className="hidden">
	                  <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Modify</span>
	                  <button
	                    type="button"
	                    data-testid="draw-site-boundary-toolbar-modify"
	                    aria-pressed={drawMode === "site"}
	                    title={siteLocked ? "Site is locked. Use Change Site before drawing a new boundary." : "Draw the site boundary"}
	                    onClick={() => {
	                      if (siteLocked) {
	                        pushCadCommandFeedback("SITE", "blocked", "SITE boundary is locked. Use Change Site before drawing a replacement boundary.");
	                        return;
	                      }
	                      activateDrawTool("site");
	                    }}
	                    className={`inline-flex h-9 shrink-0 items-center rounded-md border px-3 text-xs font-semibold ${
	                      drawMode === "site"
	                        ? "border-slate-900 bg-slate-950 text-white"
	                        : siteLocked
	                          ? "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
	                          : "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
	                    }`}
	                  >
	                    Draw Site Boundary
	                  </button>
	                  {[
	                    { mode: "polyline" as DrawMode, label: "Add Line", disabledLabel: drawObjectsDisabledLabel },
	                    { mode: "polygon" as DrawMode, label: "Add Area", disabledLabel: drawObjectsDisabledLabel },
	                    { mode: "rect" as DrawMode, label: "Add Box", disabledLabel: drawObjectsDisabledLabel },
	                    { mode: "point" as DrawMode, label: "Add Point", disabledLabel: drawObjectsDisabledLabel },
	                  ].map((item) => {
	                    const active = drawMode === item.mode;
	                    const disabled = !canDrawObjects;
	                    return (
	                      <button
	                        key={`canvas-visible-draw-${item.mode}`}
	                        type="button"
	                        aria-pressed={active}
	                        title={disabled ? item.disabledLabel : item.label}
	                        data-blocked={disabled ? "true" : undefined}
	                        onClick={() => activateDrawTool(item.mode, disabled ? item.disabledLabel : undefined)}
	                        className={`inline-flex h-9 shrink-0 items-center rounded-md border px-3 text-xs font-semibold ${
	                          active
	                            ? "border-slate-900 bg-slate-950 text-white"
	                            : disabled
	                              ? "border-amber-200 bg-amber-50 text-amber-800"
	                              : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
	                        }`}
	                      >
	                        {item.label}
	                      </button>
	                    );
	                  })}
	                  <button
	                    type="button"
	                    data-testid="preview-toolbar-interaction-edit"
                    aria-label="Use canvas edit tool"
                    onClick={() => onSetPreviewInteraction("edit")}
                    className={`inline-flex h-9 items-center gap-1.5 rounded-md border px-3 text-xs font-semibold ${
                      allowEdits ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    Edit
                  </button>
                  <button type="button" aria-label="Move selected CAD objects" onClick={() => transformSelectedCadObjects("move")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Move className="h-4 w-4" /></button>
                  <button type="button" aria-label="Rotate selected CAD objects" onClick={() => transformSelectedCadObjects("rotate")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><RotateCw className="h-4 w-4" /></button>
                  <button type="button" aria-label="Scale selected CAD objects" onClick={() => transformSelectedCadObjects("scale")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Scale className="h-4 w-4" /></button>
                  <button type="button" aria-label="Trim selected CAD object" title="Trim selected CAD object" onClick={() => trimExtendSelectedCadObject("trim")} disabled={!selectedCadObject} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Scissors className="h-4 w-4" /></button>
                  <button type="button" aria-label="Fillet selected CAD vertex" title="Fillet selected CAD vertex" onClick={filletSelectedCadObject} disabled={!selectedCadObject} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><RefreshCw className="h-4 w-4" /></button>
                  <button
                    type="button"
                    disabled={!selectedDeletableObject}
                    title={selectedObject?.locked ? "Unlock the selected object before deleting" : selectedObject ? "Delete selected object" : "Select an unlocked object to delete"}
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
                    className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:cursor-not-allowed disabled:bg-white disabled:text-slate-300"
                  >
	                    <Trash2 className="h-4 w-4" />
	                  </button>
	                  {siteLocked && onUnlockSite ? (
	                    <button
	                      type="button"
	                      data-testid="change-site-boundary-toolbar-modify"
	                      title="Unlock the site boundary for editing"
	                      aria-label="Change Site Boundary"
                      onClick={() => {
                        onUnlockSite();
                        clearDraftGeometry();
                        setDrawMode("select");
                        onSetPreviewInteraction("edit");
                      }}
                      className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
                    >
                      <Unlock className="h-4 w-4" />
                      Change Site
                    </button>
                  ) : null}
                </section>
              ) : null}
              <section className="hidden">
                <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Snaps</span>
                <label className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700">
                  <input type="checkbox" checked={cadSnapEnabled} onChange={(event) => setCadSnapEnabled(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                  Snap
                </label>
                <label className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700">
                  <input type="checkbox" checked={cadOrthoEnabled} onChange={(event) => setCadOrthoEnabled(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                  Ortho
                </label>
                <span className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-2.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  {activeSnapPoint ? activeSnapPoint.kind : "No snap"}
                </span>
              </section>
              <section className="hidden">
                <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Layers</span>
                <select
                  aria-label="CAD layer"
                  value={cadLayerDraft}
                  onChange={(event) => setCadLayerDraft(event.target.value)}
                  className="h-9 min-w-[104px] rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700"
                >
                  {["C-DRAFT", "C-SITE", "C-ROAD", "C-UTIL", "C-DRAIN", "C-BLDG"].map((layer) => (
                    <option key={layer} value={layer}>{layer}</option>
                  ))}
                </select>
                <button type="button" onClick={applySelectedCadLayer} disabled={!selectedCadIds.length} className="h-9 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white disabled:opacity-40">Apply</button>
                {(["low", "standard", "high"] as const).map((density) => (
                  <button
                    key={density}
                    type="button"
                    data-testid={`preview-label-density-${density}`}
                    onClick={() => {
                      if (previewLabelDensity === density) return;
                      onQueuePreviewRefresh(`Requesting ${density} label density...`);
                      onSetPreviewLabelDensity(density);
                    }}
                    className={`h-9 rounded-md border px-2.5 text-xs font-semibold ${
                      previewLabelDensity === density ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                    }`}
                  >
                    {density === "standard" ? "Std" : density}
                  </button>
                ))}
              </section>
              <section className="hidden">
                <span className="px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Export</span>
                {planPreviewUrl || showMap ? (
                  <button type="button" onClick={onOpenFullscreen} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">
                    <Maximize2 className="h-4 w-4" />
                    Full
                  </button>
                ) : null}
                <button type="button" aria-label="Export DXF" onClick={onExportDxf} disabled={busy} title={exportBlockReason || "Download a DXF review export"} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
                  <Download className="h-4 w-4" />
                  DXF
                </button>
                <button type="button" aria-label="Export Report" onClick={onExportReport} disabled={busy} title={exportBlockReason || "Download an engineer-review package report"} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
                  <FileText className="h-4 w-4" />
                  Report
                </button>
              </section>
            </div>
	            <div className={`${drawMode !== "select" ? "pointer-events-auto relative z-[80] flex" : "hidden"} min-w-0 flex-wrap items-center gap-3 border-t border-slate-200 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500`}>
              <span className="rounded-md border border-slate-900 bg-white px-2 py-1 text-slate-900" data-testid="draw-active-tool">
                {activeDrawToolLabel}
              </span>
              <span className="max-w-[320px] truncate normal-case tracking-normal text-slate-600" data-testid="draw-active-tool-detail">
                {activeDrawToolDetail}
              </span>
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
              {cursorSitePoint ? (
                <span>X {cursorSitePoint.x.toFixed(1)} ft / Y {cursorSitePoint.y.toFixed(1)} ft</span>
              ) : null}
              <span>{Math.round(canvasView.scale * 100)}%</span>
              <span>{cadHistory.at(-1)?.label || "No command"}</span>
              {drawMode !== "select" ? (
                <>
                  {drawMode !== "point" && drawMode !== "pan" ? (
                    <button
                      type="button"
                      onClick={finishDraftGeometry}
                      disabled={!canFinishDraftGeometry}
                      title={finishDraftBlockedReason ?? "Finish drawn geometry"}
                      className={`relative z-[90] inline-flex h-8 items-center rounded-md border px-3 text-xs ${
                        !canFinishDraftGeometry
                          ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-800"
                          : "border-slate-900 bg-slate-950 text-white"
                      }`}
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
                    onClick={() => {
                      clearDraftGeometry();
                      setDrawMode("select");
                      setActiveSnapPoint(null);
                      setCadCommandStatus("Cancelled active drawing tool.");
                    }}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                    aria-label="Cancel active drawing tool"
                    title="Cancel active drawing tool"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </>
              ) : null}
            </div>
          </div>
          <div className="hidden mb-3 min-w-0 flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white/85 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Preview Mode</span>
              <button
                type="button"
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
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Labels</span>
              {(["low", "standard", "high"] as const).map((density) => (
                <button
                  key={density}
                  type="button"
                  onClick={() => {
                    if (previewLabelDensity === density) return;
                    onQueuePreviewRefresh(`Requesting ${density} label density...`);
                    onSetPreviewLabelDensity(density);
                  }}
                  className={`rounded-lg border px-2.5 py-1 ${
                    previewLabelDensity === density
                      ? "border-slate-900 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  {density === "standard" ? "Std" : density}
                </button>
              ))}
            </div>
            <div className="flex min-w-0 flex-wrap items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
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
            <div className="hidden">
              <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
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
                          onSelectBuilding(null);
                          setSelectedVertex(null);
                          setCadSelectionSet([]);
                          onSetPreviewInteraction("edit");
                          window.requestAnimationFrame(() => {
                            previewRef.current?.scrollIntoView({
                              behavior: "auto",
                              block: "center",
                              inline: "nearest",
                            });
                          });
                        }
                      }}
                      className={`inline-flex min-h-8 shrink-0 items-center justify-center gap-1.5 rounded-md border px-2 py-1 transition ${
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
                {siteLocked && onUnlockSite ? (
                  <button
                    type="button"
                    title="Unlock the site boundary for editing"
                    aria-label="Change Site Boundary"
                    onClick={() => {
                      onUnlockSite();
                      clearDraftGeometry();
                      setDrawMode("select");
                      onSetPreviewInteraction("edit");
                    }}
                    className="inline-flex min-h-8 shrink-0 items-center justify-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-slate-600 transition hover:bg-slate-50"
                  >
                    <Unlock className="h-4 w-4" />
                    <span className="text-[10px] leading-none">Change Site Boundary</span>
                  </button>
                ) : null}
              </div>
              <div className="flex min-w-0 flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
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
                  onClick={resetCanvasView}
                  className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-slate-600 hover:bg-slate-50"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Zoom
                </button>
                <button
                  type="button"
                  data-testid="preview-strip-interaction-edit"
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
                  className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-300"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
                <button
                  type="button"
                  onClick={onOpenFullscreen}
                  className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 text-slate-600 hover:bg-slate-50"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                  More
                </button>
                <span className="min-w-12 text-right">{Math.round(canvasView.scale * 100)}%</span>
                {drawMode !== "select" ? (
                  <>
                    {drawMode !== "point" && drawMode !== "pan" ? (
                      <button
                        type="button"
                        onClick={finishDraftGeometry}
                        disabled={!canFinishDraftGeometry}
                        title={finishDraftBlockedReason ?? "Finish drawn geometry"}
                        className="relative z-[90] inline-flex h-8 items-center rounded-md border border-slate-900 bg-slate-950 px-2 text-white disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
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
	          {previewMode === "2d" && allowEdits && hasCadCommandActivity ? (
            <div className="civora-cad-dock relative z-[10] mb-3 grid gap-3 rounded-xl border border-slate-200 bg-white/90 p-3 shadow-sm lg:max-w-[calc(100%-30rem)] lg:grid-cols-[1.05fr_1fr_1fr_1.1fr]" data-testid="cad-precision-tools">
              <section className="min-w-0">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">CAD precision</p>
                    <p className="mt-1 truncate text-sm font-semibold text-slate-900">
                      {selectedCadObject?.label || "No CAD object selected"}
                    </p>
                  </div>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      aria-label="Undo CAD command"
                      title="Undo CAD command"
                      onClick={undoCadCommand}
                      disabled={!cadHistory.length && !lastPolylineEdit && !lastRectEdit}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 disabled:opacity-40"
                    >
                      <CornerUpLeft className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      aria-label="Redo CAD command"
                      title="Redo CAD command"
                      onClick={redoCadCommand}
                      disabled={!cadRedoStack.length}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 disabled:opacity-40"
                    >
                      <CornerUpRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold text-slate-700 sm:grid-cols-4">
                  <label className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2">
                    <input type="checkbox" checked={cadSnapEnabled} onChange={(event) => setCadSnapEnabled(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                    Snap
                  </label>
                  <label className="flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2">
                    <input type="checkbox" checked={cadOrthoEnabled} onChange={(event) => setCadOrthoEnabled(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                    Ortho
                  </label>
                  <span className="flex min-h-10 items-center rounded-lg border border-slate-200 bg-slate-50 px-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                    {activeSnapPoint ? activeSnapPoint.kind : "No snap"}
                  </span>
                  <span className="flex min-h-10 items-center rounded-lg border border-slate-200 bg-slate-50 px-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                    {cadHistory.at(-1)?.label || "No command"}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2">
                  <input
                    aria-label="CAD X coordinate"
                    inputMode="decimal"
                    value={cadCoordinateDraft.x}
                    onChange={(event) => setCadCoordinateDraft((prev) => ({ ...prev, x: event.target.value }))}
                    placeholder="X ft"
                    className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  />
                  <input
                    aria-label="CAD Y coordinate"
                    inputMode="decimal"
                    value={cadCoordinateDraft.y}
                    onChange={(event) => setCadCoordinateDraft((prev) => ({ ...prev, y: event.target.value }))}
                    placeholder="Y ft"
                    className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  />
                  <button
                    type="button"
                    onClick={applyCadCoordinate}
                    className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white"
                  >
                    <MapPin className="h-3.5 w-3.5" />
                    XY
                  </button>
                </div>
                <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
                  <input
                    aria-label="CAD command input"
                    value={cadCommandDraft}
                    onChange={(event) => setCadCommandDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        runCadCommand();
                      }
                    }}
                    placeholder={cadActiveCommand ? "Next point, FINISH, or CANCEL" : "LINE, then 0,0, then 100,0"}
                    className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  />
                  <button type="button" onClick={() => runCadCommand()} className="h-9 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white">Run</button>
                </div>
                {cadActiveCommand ? (
                  <div
                    className="mt-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] font-semibold text-blue-800"
                    data-testid="cad-active-command"
                  >
                    {cadActiveCommand.kind === "draw"
                      ? `Active command: ${cadActiveCommand.command} · ${draftPoints.length}/${cadActiveCommand.minPoints}+ point${draftPoints.length === 1 ? "" : "s"} · type next coordinate or run empty to finish.`
                      : cadActiveCommand.kind === "offset"
                        ? `Active command: OFFSET · ${typeof cadActiveCommand.distance === "number" ? `${cadActiveCommand.distance} ft` : "distance needed"} · type distance or run empty after selecting an object.`
                        : cadActiveCommand.kind === "modify"
                          ? `Active command: ${cadActiveCommand.command} · ${typeof cadActiveCommand.amount === "number" ? `${cadActiveCommand.amount} ft` : "amount needed"} · type amount or run empty after selecting a line.`
                          : `Active command: ${cadActiveCommand.command} · ${cadActiveCommand.value || (cadActiveCommand.command === "MOVE" || cadActiveCommand.command === "COPY" ? "vector needed" : cadActiveCommand.command === "ROTATE" ? "angle needed" : "factor needed")} · type the value, then press Run.`}
                  </div>
                ) : null}
                <p className="mt-2 text-[11px] font-medium text-slate-500">{cadCommandStatus}</p>
                <div className="mt-2 max-h-28 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-2" data-testid="cad-command-feedback-panel" aria-live="polite">
                  {cadCommandHistory.length ? (
                    <ol className="space-y-1 text-[11px]">
                      {cadCommandHistory.slice().reverse().map((entry) => (
                        <li key={entry.id} className="grid grid-cols-[4.5rem_1fr] gap-2">
                          <span className={entry.status === "blocked" ? "font-semibold text-amber-700" : entry.status === "applied" ? "font-semibold text-emerald-700" : "font-semibold text-slate-500"}>
                            {entry.command}
                          </span>
                          <span className="min-w-0 break-words text-slate-600">{entry.message}</span>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="text-[11px] font-medium text-slate-500">Command feedback appears here.</p>
                  )}
                </div>
              </section>
              <section className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Readout / transform</p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  {[
                    ["Length", selectedCadMetrics ? `${selectedCadMetrics.totalLength.toFixed(1)} ft` : "Select object"],
                    ["Angle", selectedCadMetrics ? `${selectedCadMetrics.firstAngle.toFixed(1)} deg` : "Select object"],
                    ["Segments", selectedCadMetrics ? String(selectedCadMetrics.segmentCount) : "--"],
                    ["Layer", selectedCadMetrics?.layer || "C-DRAFT"],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                      <p className="mt-1 truncate font-semibold text-slate-800">{value}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-3 grid grid-cols-[1fr_repeat(3,auto)] gap-2">
                  <input
                    aria-label="CAD transform value"
                    inputMode="decimal"
                    value={cadTransformValue}
                    onChange={(event) => setCadTransformValue(event.target.value)}
                    className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  />
                  <button type="button" aria-label="Move selected CAD objects" onClick={() => transformSelectedCadObjects("move")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Move className="h-4 w-4" /></button>
                  <button type="button" aria-label="Rotate selected CAD objects" onClick={() => transformSelectedCadObjects("rotate")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><RotateCw className="h-4 w-4" /></button>
                  <button type="button" aria-label="Scale selected CAD objects" onClick={() => transformSelectedCadObjects("scale")} disabled={!selectedCadIds.length} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Scale className="h-4 w-4" /></button>
                </div>
                <div className="mt-3 grid grid-cols-[auto_1fr_auto] gap-2">
                  <select
                    aria-label="CAD dimension mode"
                    value={cadDimensionMode}
                    onChange={(event) => setCadDimensionMode(event.target.value as CadDimensionMode)}
                    className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  >
                    <option value="linear">Linear</option>
                    <option value="aligned">Aligned</option>
                  </select>
                  <input
                    aria-label="CAD dimension label"
                    value={cadDimensionLabelDraft}
                    onChange={(event) => setCadDimensionLabelDraft(event.target.value)}
                    placeholder="Editable dimension label"
                    className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  />
                  <button type="button" onClick={applySelectedCadDimension} disabled={!selectedCadObject} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 disabled:opacity-40">Dim</button>
                </div>
              </section>
              <section className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Modify / layers</p>
                <div className="mt-3 grid grid-cols-4 gap-2">
                  <button type="button" aria-label="Offset selected CAD object" title="Offset selected CAD object" onClick={offsetSelectedCadObject} disabled={!selectedCadObject} className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Ruler className="h-4 w-4" /></button>
                  <button type="button" aria-label="Trim selected CAD object" title="Trim selected CAD object" onClick={() => trimExtendSelectedCadObject("trim")} disabled={!selectedCadObject} className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><Scissors className="h-4 w-4" /></button>
                  <button type="button" aria-label="Extend selected CAD object" title="Extend selected CAD object" onClick={() => trimExtendSelectedCadObject("extend")} disabled={!selectedCadObject} className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><GitBranch className="h-4 w-4" /></button>
                  <button type="button" aria-label="Fillet selected CAD vertex" title="Fillet selected CAD vertex" onClick={filletSelectedCadObject} disabled={!selectedCadObject} className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 disabled:opacity-40"><RefreshCw className="h-4 w-4" /></button>
                </div>
                <div className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2">
                  <input aria-label="CAD offset distance" inputMode="decimal" value={cadOffsetDistance} onChange={(event) => setCadOffsetDistance(event.target.value)} className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD fillet radius" inputMode="decimal" value={cadFilletRadius} onChange={(event) => setCadFilletRadius(event.target.value)} className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <button type="button" onClick={() => setCadSelectionSet(selectedBuildingId ? [selectedBuildingId] : [])} disabled={!selectedBuildingId} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 disabled:opacity-40">Set</button>
                </div>
                <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
                  <select
                    aria-label="CAD layer"
                    value={cadLayerDraft}
                    onChange={(event) => setCadLayerDraft(event.target.value)}
                    className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  >
                    {cadLayerOptions.map((layer) => (
                      <option key={layer} value={layer}>{layer}</option>
                    ))}
                  </select>
                  <button type="button" onClick={applySelectedCadLayer} disabled={!selectedCadIds.length} className="h-9 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white disabled:opacity-40">Layer</button>
                </div>
                <div className="mt-3 grid max-h-24 gap-1 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-1">
                  {cadLayerOptions.map((layer) => {
                    const hidden = hiddenCadLayers.includes(layer);
                    return (
                      <button
                        key={`layer-toggle-${layer}`}
                        type="button"
                        onClick={() => toggleCadLayerVisibility(layer)}
                        className="flex min-h-8 items-center justify-between gap-2 rounded-md bg-white px-2 text-left text-[11px] font-semibold text-slate-600"
                      >
                        <span className="truncate">{layer}</span>
                        {hidden ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                      </button>
                    );
                  })}
                </div>
              </section>
              <section className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Symbols / properties</p>
                <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
                  <select
                    aria-label="CAD symbol"
                    value={cadSymbolDraft}
                    onChange={(event) => setCadSymbolDraft(event.target.value as CadSymbolKind)}
                    className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  >
                    <option value="hydrant">Hydrant</option>
                    <option value="inlet">Inlet</option>
                    <option value="manhole">Manhole</option>
                    <option value="valve">Valve</option>
                    <option value="tree">Tree</option>
                    <option value="light">Light</option>
                    <option value="sign">Sign</option>
                    <option value="utility_marker">Utility marker</option>
                    <option value="benchmark">Benchmark</option>
                    <option value="note_callout">Note / callout</option>
                  </select>
                  <button type="button" aria-label="Insert CAD symbol" onClick={insertCadSymbol} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600">Insert</button>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <input aria-label="CAD symbol attribute ID" value={cadPropertyDraft.id} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, id: event.target.value }))} placeholder="ID" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD object name" value={cadPropertyDraft.name} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, name: event.target.value }))} placeholder="Name" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD object type" value={cadPropertyDraft.type} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, type: event.target.value }))} placeholder="Type" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD object layer property" value={cadPropertyDraft.layer} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, layer: event.target.value }))} placeholder="Layer" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD symbol elevation attribute" value={cadPropertyDraft.elevation} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, elevation: event.target.value }))} placeholder="Elevation" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD symbol material attribute" value={cadPropertyDraft.material} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, material: event.target.value }))} placeholder="Material" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD symbol size attribute" value={cadPropertyDraft.size} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, size: event.target.value }))} placeholder="Size" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <button type="button" aria-label="Apply CAD symbol properties" onClick={applyCadProperties} disabled={!selectedCadObject} className="h-9 rounded-md border border-slate-900 bg-slate-950 px-3 text-xs font-semibold uppercase tracking-[0.12em] text-white disabled:opacity-40">Apply</button>
                </div>
                <div className="mt-3 grid gap-2">
                  <input aria-label="CAD symbol source attribute" value={cadPropertyDraft.source} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, source: event.target.value }))} placeholder="Source" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD source note" value={cadPropertyDraft.sourceNote} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, sourceNote: event.target.value }))} placeholder="Source note" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                  <input aria-label="CAD review note" value={cadPropertyDraft.reviewNote} onChange={(event) => setCadPropertyDraft((prev) => ({ ...prev, reviewNote: event.target.value }))} placeholder="Review note" className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" />
                </div>
                <p className="mt-2 text-[11px] font-medium text-slate-500">Snap priority: endpoint, midpoint, intersection, perpendicular, then ortho.</p>
                <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-[11px] font-semibold text-slate-600" data-testid="cad-topology-status">
                  {topologyIssues.length ? (
                    <>
                      <p className="text-amber-700">Topology review needs</p>
                      <ul className="mt-1 space-y-1">
                        {topologyIssues.slice(0, 3).map((issue) => (
                          <li key={`${issue.code}-${issue.objectIds.join("-")}`} className="break-words">
                            {issue.code.replace(/_/g, " ")}: {issue.message}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p>Topology checks: no visible CAD blockers.</p>
                  )}
                </div>
              </section>
            </div>
          ) : null}
          <div className="civora-coordination-dock mb-3 grid gap-3 xl:grid-cols-[1.1fr_1.4fr_1fr]">
            <section className="rounded-xl border border-slate-200 bg-white/90 p-3 shadow-sm" data-testid="utility-conflict-viewer">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Conflict Viewer</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {utilityCoordinationSummary.conflictCount
                      ? `${utilityCoordinationSummary.conflictCount} conflicts need review`
                      : utilityCoordinationSummary.watchCount
                        ? `${utilityCoordinationSummary.watchCount} clearance items need review`
                        : "No utility conflicts flagged"}
                  </p>
                </div>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    utilityCoordinationSummary.status === "conflict"
                      ? "bg-red-50 text-red-700"
                      : utilityCoordinationSummary.status === "watch"
                        ? "bg-amber-50 text-amber-700"
                        : "bg-emerald-50 text-emerald-700"
                  }`}
                >
                  <AlertTriangle className="h-3 w-3" />
                  {utilityCoordinationSummary.status}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {[
                  ["Crossings", utilityCoordinationSummary.crossingCount],
                  ["Conflicts", utilityCoordinationSummary.conflictCount],
                  ["Watch", utilityCoordinationSummary.watchCount],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs leading-5 text-slate-500">
                Coordination evidence is review-only. Clearance and reroute guidance do not approve construction or replace the responsible engineer.
              </p>
            </section>

            <section className="min-w-0 rounded-xl border border-slate-200 bg-white/90 p-3 shadow-sm" data-testid="utility-crossing-table">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Crossing Table</p>
                <Table2 className="h-4 w-4 text-slate-400" />
              </div>
              <div className="mt-3 overflow-hidden rounded-lg border border-slate-200">
                <div className="grid grid-cols-[1.2fr_0.7fr_0.7fr_0.7fr] bg-slate-50 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                  <span>Pair</span>
                  <span>Type</span>
                  <span>Clearance</span>
                  <span>Score</span>
                </div>
                <div className="max-h-36 overflow-auto">
                  {utilityCoordinationRows.length ? (
                    utilityCoordinationRows.map((row) => (
                      <div key={row.id} className="grid grid-cols-[1.2fr_0.7fr_0.7fr_0.7fr] border-t border-slate-100 px-3 py-2 text-xs">
                        <span className="min-w-0 truncate font-semibold text-slate-800">{row.systemA} / {row.systemB}</span>
                        <span className="capitalize text-slate-500">{row.crossingType}</span>
                        <span className={row.status === "conflict" ? "font-semibold text-red-700" : row.status === "watch" ? "font-semibold text-amber-700" : "font-semibold text-emerald-700"}>
                          {formatClearance(row.clearanceFt)}
                        </span>
                        <span className="font-semibold text-slate-800">{row.constructabilityScore}</span>
                      </div>
                    ))
                  ) : (
                    <div className="px-3 py-4 text-sm text-slate-500">No crossing evidence has been generated yet.</div>
                  )}
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white/90 p-3 shadow-sm" data-testid="utility-constructability-scoring">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Constructability</p>
                <ShieldCheck className="h-4 w-4 text-slate-400" />
              </div>
              <div className="mt-3">
                <div className="flex items-end justify-between gap-3">
                  <span className="text-3xl font-semibold text-slate-900">{utilityCoordinationSummary.avgScore}</span>
                  <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">review score</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full ${
                      utilityCoordinationSummary.avgScore < 55
                        ? "bg-red-500"
                        : utilityCoordinationSummary.avgScore < 75
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                    }`}
                    style={{ width: `${Math.min(Math.max(utilityCoordinationSummary.avgScore, 4), 100)}%` }}
                  />
                </div>
              </div>
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" data-testid="utility-clearance-view">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Vertical / Horizontal Clearance</p>
                <p className="mt-1 text-xs font-semibold text-slate-700">
                  {utilityCoordinationRows.filter((row) => row.crossingType === "vertical").length} vertical · {utilityCoordinationRows.filter((row) => row.crossingType === "horizontal").length} horizontal
                </p>
              </div>
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" data-testid="utility-reroute-options">
                <div className="flex items-center gap-2">
                  <Route className="h-3.5 w-3.5 text-slate-400" />
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Reroute Options</p>
                </div>
                <p className="mt-1 line-clamp-2 text-xs font-medium text-slate-700">
                  {(utilityCoordinationRows.find((row) => row.status === "conflict") ?? utilityCoordinationRows[0])?.rerouteOptions.join(" · ") || "Generate utilities to see reroute options."}
                </p>
              </div>
            </section>
          </div>
          {show3D ? (
            preview3DEffectiveItems.length ? (
              <div className="relative min-w-0">
                <div className="absolute left-1/2 top-3 z-[120] flex max-w-[calc(100%-8rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white/94 p-1 shadow-[0_16px_45px_-28px_rgba(15,23,42,0.65)] backdrop-blur">
                  <button
                    type="button"
                    data-testid="preview-mode-2d"
                    aria-label="Show 2D plan preview"
                    onClick={() => onSetPreviewMode("2d")}
                    className="h-8 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600"
                  >
                    2D
                  </button>
                  <button
                    type="button"
                    data-testid="preview-mode-3d"
                    aria-label="Show 3D model preview"
                    onClick={() => onSetPreviewMode("3d")}
                    className="h-8 rounded-md border border-slate-900 bg-slate-950 px-2.5 text-xs font-semibold text-white"
                  >
                    3D
                  </button>
                  <button
                    type="button"
                    data-testid="preview-quality-standard"
                    onClick={() => {
                      if (previewQuality === "standard") return;
                      onQueuePreviewRefresh("Requesting standard-quality preview...");
                      onSetPreviewQuality("standard");
                    }}
                    className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
                      previewQuality === "standard" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
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
                    className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
                      previewQuality === "high" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                    }`}
                  >
                    High
                  </button>
                  {isHighQuality ? (
                    <div
                      data-testid="ai-realism-toggle"
                      className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white p-0.5"
                      aria-label="AI Visualization toggle"
                    >
                      <span className="px-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">AI Visualization</span>
                      <button
                        type="button"
                        data-testid="ai-realism-off"
                        onClick={setAiVisualizationOff}
                        aria-pressed={!aiRealismEnabled}
                        className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                          !aiRealismEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        Off
                      </button>
                      <button
                        type="button"
                        data-testid="ai-realism-on"
                        onClick={setAiVisualizationOn}
                        aria-pressed={aiRealismEnabled}
                        className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                          aiRealismEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        On
                      </button>
                    </div>
                  ) : null}
                </div>
                <Suspense
                  fallback={
                    <div
                      data-testid="civil-3d-viewer-loading"
                      className="flex min-h-[520px] items-center justify-center rounded-xl border border-slate-200 bg-slate-950 text-xs font-semibold uppercase tracking-[0.18em] text-white"
                    >
                      Loading 3D preview...
                    </div>
                  }
                >
                  <Preview3DCanvas
                    items={preview3DEffectiveItems}
                    interactive={allowEdits}
                    previewQuality={previewQuality}
                    selectedItemId={selectedBuildingId}
                    hasTerrainSource={hasTerrainSource}
                    hasGradingSurface={hasGradingSurface}
                    onSelectItem={onSelectBuilding}
                    onOpenFullscreen={onOpenFullscreen}
                  />
                </Suspense>
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
                  className="absolute right-4 top-4 rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm transition hover:bg-slate-900"
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
                  setCanvasView((prev) => ({
                    ...prev,
                    offsetX: canvasPanStart.offsetX + event.clientX - canvasPanStart.x,
                    offsetY: canvasPanStart.offsetY + event.clientY - canvasPanStart.y,
                  }));
                  return;
                }
                if (drawMode !== "select" && drawMode !== "pan" && overlayBoundsResolved) {
                  const rawSitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, overlayBoundsResolved);
                  const basePoint = draftPoints.length
                    ? { x: draftPoints[draftPoints.length - 1][0], y: draftPoints[draftPoints.length - 1][1] }
                    : null;
                  const sitePoint = rawSitePoint ? resolveCadSnapPoint(rawSitePoint, basePoint) : null;
                  setDraftPreviewPoint(sitePoint ? [sitePoint.x, sitePoint.y] : null);
                  setActiveSnapPoint(sitePoint);
                  if (sitePoint) {
                    setCursorSitePoint((current) =>
                      current &&
                      Math.abs(current.x - sitePoint.x) < 0.5 &&
                      Math.abs(current.y - sitePoint.y) < 0.5
                        ? current
                        : { x: sitePoint.x, y: sitePoint.y },
                    );
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
                  setCursorSitePoint((current) => {
                    if (!sitePoint) return current === null ? current : null;
                    return current &&
                      Math.abs(current.x - sitePoint.x) < 0.5 &&
                      Math.abs(current.y - sitePoint.y) < 0.5
                      ? current
                      : { x: sitePoint.x, y: sitePoint.y };
                  });
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
                setActiveSnapPoint(null);
                setCadWindowSelect(null);
              }}
              onMouseUp={() => {
                if (cadWindowSelect) {
                  finishCadWindowSelect(cadWindowSelect);
                  setCadWindowSelect(null);
                }
                setDraggingBuildingId(null);
                setDraggingMode(null);
                setRotateDragStart(null);
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
	                if (!allowEdits || !overlayBoundsResolved || showMap) return;
	                event.preventDefault();
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
	              {previewMode === "2d" && showQuickDrawPalette ? (
		                <div
		                  data-testid="canvas-quick-draw-palette"
		                  className="pointer-events-auto absolute left-[7rem] top-20 z-[35] flex max-w-[calc(100%-8rem)] flex-wrap items-center gap-1.5 rounded-xl border border-slate-200 bg-white/96 p-1.5 shadow-[0_18px_55px_-34px_rgba(15,23,42,0.75)] backdrop-blur"
		                  onMouseDown={(event) => event.stopPropagation()}
		                  onPointerDown={(event) => event.stopPropagation()}
		                  onTouchStart={(event) => event.stopPropagation()}
		                  onClick={(event) => event.stopPropagation()}
		                >
	                  <button
	                    type="button"
	                    data-testid="draw-site-boundary-toolbar"
	                    aria-pressed={drawMode === "site"}
	                    title={siteLocked ? "Site is locked. Use Change Site before drawing a new boundary." : "Draw the site boundary"}
	                    onClick={() => {
	                      if (siteLocked) {
	                        pushCadCommandFeedback("SITE", "blocked", "SITE boundary is locked. Use Change Site before drawing a replacement boundary.");
	                        return;
	                      }
	                      activateDrawTool("site");
	                    }}
	                    className={`inline-flex h-8 shrink-0 items-center rounded-lg border px-2.5 text-[11px] font-semibold ${
	                      drawMode === "site"
	                        ? "border-slate-900 bg-slate-950 text-white"
	                        : siteLocked
	                          ? "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
	                          : "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
	                    }`}
	                  >
	                    Draw Site
	                  </button>
	                  {siteLocked && onUnlockSite ? (
	                    <button
	                      type="button"
	                      data-testid="change-site-boundary-toolbar"
	                      aria-label="Change Site Boundary"
	                      onClick={() => {
	                        onUnlockSite();
	                        clearDraftGeometry();
	                        setDrawMode("select");
	                        onSetPreviewInteraction("edit");
	                      }}
	                      className="inline-flex h-8 shrink-0 items-center rounded-lg border border-slate-200 bg-white px-2.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
	                    >
	                      Change Site
	                    </button>
	                  ) : null}
	                  {!siteLocked && hasDrawableSiteSize && onLockSite ? (
	                    <button
	                      type="button"
	                      data-testid="lock-site-boundary-toolbar"
	                      aria-label="Lock Site Boundary"
	                      onClick={() => {
	                        clearDraftGeometry();
	                        setDrawMode("select");
	                        onLockSite();
	                      }}
	                      className="inline-flex h-8 shrink-0 items-center rounded-lg border border-slate-950 bg-slate-950 px-2.5 text-[11px] font-semibold text-white hover:bg-slate-800"
	                    >
	                      Lock Site
	                    </button>
	                  ) : null}
	                  {[
	                    { mode: "polyline" as DrawMode, label: "Add Line", disabledLabel: drawObjectsDisabledLabel },
	                    { mode: "polygon" as DrawMode, label: "Add Area", disabledLabel: drawObjectsDisabledLabel },
	                    { mode: "rect" as DrawMode, label: "Add Box", disabledLabel: drawObjectsDisabledLabel },
	                    { mode: "point" as DrawMode, label: "Add Point", disabledLabel: drawObjectsDisabledLabel },
	                  ].map((item) => {
	                    const active = drawMode === item.mode;
	                    const disabled = !canDrawObjects;
	                    return (
	                      <button
	                        key={`canvas-quick-draw-${item.mode}`}
	                        type="button"
	                        aria-pressed={active}
	                        title={disabled ? item.disabledLabel : item.label}
	                        data-blocked={disabled ? "true" : undefined}
	                        onClick={() => activateDrawTool(item.mode, disabled ? item.disabledLabel : undefined)}
	                        className={`inline-flex h-8 shrink-0 items-center rounded-lg border px-2.5 text-[11px] font-semibold ${
	                          active
	                            ? "border-slate-900 bg-slate-950 text-white"
	                            : disabled
	                              ? "border-amber-200 bg-amber-50 text-amber-800"
	                              : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
	                        }`}
	                      >
	                        {item.label}
	                      </button>
	                    );
	                  })}
			                  {drawMode !== "point" ? (
		                    <button
		                      type="button"
		                      data-testid="canvas-quick-finish"
		                      onClick={finishDraftGeometry}
		                      disabled={!canFinishDraftGeometry}
		                      title={finishDraftBlockedReason ?? "Finish drawn geometry"}
	                      className={`inline-flex h-8 shrink-0 items-center rounded-lg border px-2.5 text-[11px] font-semibold ${
	                        !canFinishDraftGeometry
	                          ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-800"
	                          : "border-slate-900 bg-slate-950 text-white"
	                      }`}
	                    >
	                      Finish
	                    </button>
	                  ) : null}
	                    <button
	                      type="button"
	                      data-testid="canvas-quick-cancel"
	                      onClick={() => {
	                        clearDraftGeometry();
	                        setDrawMode("select");
	                        setActiveSnapPoint(null);
	                        setCadCommandStatus("Cancelled active drawing tool.");
	                      }}
	                      className="inline-flex h-8 shrink-0 items-center rounded-lg border border-slate-200 bg-white px-2.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
	                    >
	                      Cancel
	                    </button>
	                </div>
	              ) : null}
	              <div className="absolute left-1/2 top-3 z-[85] flex max-w-[calc(100%-8rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white/94 p-1 shadow-[0_16px_45px_-28px_rgba(15,23,42,0.65)] backdrop-blur">
                <button
                  type="button"
                  data-testid="preview-mode-2d"
                  aria-label="Show 2D plan preview"
                  onClick={() => onSetPreviewMode("2d")}
                  className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
                    previewMode === "2d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  2D
                </button>
                <button
                  type="button"
                  data-testid="preview-mode-3d"
                  aria-label="Show 3D model preview"
                  onClick={() => {
                    if (!canUse3D) return;
                    onSetPreviewMode("3d");
                  }}
                  disabled={!canUse3D}
                  className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
                    activePreviewMode === "3d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600 disabled:text-slate-300"
                  }`}
                >
                  3D
                </button>
                <button
                  type="button"
                  data-testid="preview-quality-standard"
                  onClick={() => {
                    if (previewQuality === "standard") return;
                    onQueuePreviewRefresh("Requesting standard-quality preview...");
                    onSetPreviewQuality("standard");
                  }}
                  className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
                    previewQuality === "standard" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
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
                  className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
                    previewQuality === "high" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  High
                </button>
                {isHighQuality ? (
                  <div
                    data-testid="ai-realism-toggle"
                    className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white p-0.5"
                    aria-label="AI Visualization toggle"
                  >
                    <span className="px-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">AI Visualization</span>
                    <button
                      type="button"
                      data-testid="ai-realism-off"
                      onClick={setAiVisualizationOff}
                        aria-pressed={!aiRealismEnabled}
                      className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                        !aiRealismEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                      }`}
                    >
                      Off
                    </button>
                    <button
                      type="button"
                      data-testid="ai-realism-on"
                      onClick={setAiVisualizationOn}
                        aria-pressed={aiRealismEnabled}
                      className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                        aiRealismEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                      }`}
                    >
                      On
                    </button>
                  </div>
                ) : null}
                <button
                  type="button"
                  data-testid="preview-interaction-edit"
                  aria-label="Use canvas edit tool"
                  onClick={() => onSetPreviewInteraction("edit")}
                  className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
                    allowEdits ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  Edit
                </button>
                {siteLocked && onUnlockSite ? (
                  <button
                    type="button"
                    title="Unlock the site boundary for editing"
                    aria-label="Change Site Boundary"
                    onClick={() => {
                      onUnlockSite();
                      clearDraftGeometry();
                      setDrawMode("select");
                      onSetPreviewInteraction("edit");
                    }}
                    className="h-8 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600"
                  >
                    Change Site
                  </button>
                ) : null}
              </div>
              {isHighQuality && aiRealismEnabled ? (
                <div
                  data-testid="ai-realism-preview"
                  className="absolute inset-0 z-[60] flex items-center justify-center overflow-hidden rounded-[24px] bg-slate-950"
                  onClick={(event) => event.stopPropagation()}
                  onDoubleClick={(event) => event.stopPropagation()}
                  onMouseDown={(event) => event.stopPropagation()}
                  onMouseMove={(event) => event.stopPropagation()}
                  onMouseUp={(event) => event.stopPropagation()}
                >
                  {aiRealismDisplayArtifact ? (
                    <>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        data-testid="ai-realism-image"
                        src={aiRealismDisplayArtifact.image_data_url}
                        alt="AI realism visualization generated from the current review layout"
                        className="h-full w-full object-cover"
                      />
                      <div
                        data-testid="ai-realism-watermark"
                        className="absolute inset-x-4 bottom-4 rounded-lg border border-white/25 bg-slate-950/82 px-4 py-2 text-xs font-semibold text-white shadow-lg backdrop-blur"
                      >
                        {AI_REALISM_WATERMARK}
                      </div>
                      <div
                        data-testid="ai-realism-source-summary"
                        className="absolute left-4 top-4 max-w-[min(32rem,calc(100%-2rem))] rounded-xl border border-white/35 bg-white/92 p-3 text-xs text-slate-700 shadow-lg backdrop-blur"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="font-semibold uppercase tracking-[0.14em] text-slate-500">
                              high_quality_ai_render_v1
                            </p>
                            <p className="mt-0.5 text-[11px] text-slate-500">
                              Source summary: {aiRealismDisplayArtifact.source_objects_summary.total} review object(s)
                              {Object.keys(aiRealismDisplayArtifact.source_objects_summary.counts_by_type).length
                                ? ` across ${Object.entries(aiRealismDisplayArtifact.source_objects_summary.counts_by_type)
                                    .map(([type, count]) => `${type}: ${count}`)
                                    .join(", ")}`
                                : ""}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            <a
                              data-testid="ai-realism-view-snapshot"
                              href={aiRealismDisplayArtifact.image_data_url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                            >
                              View snapshot
                            </a>
                            <a
                              data-testid="ai-realism-save-snapshot"
                              href={aiRealismDisplayArtifact.image_data_url}
                              download={`ai-visualization-${aiRealismDisplayArtifact.project_id}.svg`}
                              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                            >
                              Save snapshot
                            </a>
                            <button
                              type="button"
                              data-testid="ai-realism-regenerate"
                              onClick={generateAiRealismArtifact}
                              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                            >
                              Regenerate
                            </button>
                          </div>
                        </div>
                        {aiRealismStale ? (
                          <p
                            data-testid="ai-realism-stale-warning"
                            className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 font-semibold text-amber-800"
                          >
                            AI visualization is stale. Regenerate from current layout.
                          </p>
                        ) : null}
                        <dl className="mt-2 grid gap-1">
                          <div>
                            <dt className="font-semibold text-slate-900">Objects included</dt>
                            <dd data-testid="ai-realism-objects-included" className="text-slate-600">
                              {aiRealismDisplayArtifact.source_objects_summary.objects_included.slice(0, 5).join(", ")}
                              {aiRealismDisplayArtifact.source_objects_summary.total > 5 ? "..." : ""}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-slate-900">Missing context</dt>
                            <dd data-testid="ai-realism-missing-context" className="text-slate-600">
                              {aiRealismDisplayArtifact.missing_inputs.length
                                ? aiRealismDisplayArtifact.missing_inputs.join(", ")
                                : "None reported from current review layout."}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-slate-900">Terrain/source confidence</dt>
                            <dd data-testid="ai-realism-terrain-confidence" className="text-slate-600">
                              {hasTerrainSource
                                ? "Terrain source present in review context; source confidence remains review-only."
                                : "Terrain/source confidence missing or not source-backed."}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-semibold text-slate-900">Generated timestamp</dt>
                            <dd data-testid="ai-realism-generated-timestamp" className="text-slate-600">
                              {aiRealismDisplayArtifact.generated_timestamp}
                            </dd>
                          </div>
                        </dl>
                      </div>
                    </>
                  ) : (
                    <div
                      data-testid="ai-realism-blocker"
                      className="mx-4 max-w-md rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 shadow-lg"
                    >
                      <p className="font-semibold">
                        {aiRealismBlocker || "AI realism provider is not configured."}
                      </p>
                      <button
                        type="button"
                        data-testid="ai-realism-regenerate"
                        onClick={generateAiRealismArtifact}
                        className="mt-3 rounded-md border border-amber-300 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-amber-900"
                      >
                        Regenerate
                      </button>
                    </div>
                  )}
                </div>
              ) : null}
              {showMobileDrawToolbar ? (
                <div className="absolute inset-x-1 bottom-1 z-[70] max-h-[52%] overflow-y-auto rounded-xl border border-slate-200 bg-white/95 p-2 shadow-[0_20px_50px_-28px_rgba(15,23,42,0.55)] backdrop-blur sm:inset-x-2 sm:bottom-2 md:hidden">
                  <div className="grid grid-cols-4 gap-1.5 pb-1 min-[420px]:grid-cols-7">
                    {drawModeButtons.map((item) => {
                      const Icon = item.icon;
                      const active = drawMode === item.mode;
                      const disabled = Boolean(item.disabled);
                      const mobileLabel =
                        item.mode === "site"
                          ? "Site"
                          : item.mode === "polyline"
                            ? "Line"
                            : item.mode === "polygon"
                              ? "Area"
                              : item.mode === "rect"
                                ? "Box"
                                : item.mode === "point"
                                  ? "Point"
                                  : item.label;
                      return (
                        <button
                          key={`mobile-${item.mode}`}
                          type="button"
                          data-testid={compactViewport && item.mode === "site" ? "draw-site-boundary-toolbar-mobile" : undefined}
                          title={disabled ? item.disabledLabel ?? item.label : item.label}
                          aria-label={item.mode === "site" ? "Site boundary drawing tool" : item.label}
                          data-blocked={disabled ? "true" : undefined}
                          onClick={() => {
                            activateDrawTool(item.mode, disabled ? item.disabledLabel ?? `${item.label} blocked.` : undefined);
                            if (!disabled && item.mode !== "select") {
                              window.requestAnimationFrame(() => {
                                previewRef.current?.scrollIntoView({
                                  behavior: "auto",
                                  block: "center",
                                  inline: "nearest",
                                });
                              });
                            }
                          }}
                          className={`relative z-[90] inline-flex min-h-10 min-w-0 items-center justify-center gap-1 rounded-lg border px-1.5 py-2 text-[11px] font-semibold transition ${
                            active
                              ? "border-slate-900 bg-slate-950 text-white"
                              : disabled
                                ? "border-amber-200 bg-amber-50 text-amber-700"
                                : "border-slate-200 bg-white text-slate-700"
                          }`}
                        >
                          <Icon className="h-4 w-4" />
                          <span className="truncate">{mobileLabel}</span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
	                    {drawMode !== "point" ? (
                      <button
                        type="button"
                        onClick={finishDraftGeometry}
                        disabled={!canFinishDraftGeometry}
                        title={finishDraftBlockedReason ?? "Finish drawn geometry"}
                        className={`relative z-[90] min-h-10 flex-1 rounded-lg border px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] ${
                          !canFinishDraftGeometry
                            ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-800"
                            : "border-slate-900 bg-slate-950 text-white"
                        }`}
                      >
                        Finish
                      </button>
                    ) : null}
                      <button
                        type="button"
                        onClick={() => {
                          clearDraftGeometry();
                          setDrawMode("select");
                          setActiveSnapPoint(null);
                          setCadCommandStatus("Cancelled active drawing tool.");
                        }}
                        className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700"
                      >
                        Cancel
                      </button>
                    {siteLocked && onUnlockSite ? (
                      <button
                        type="button"
                        title="Unlock the site boundary for editing"
                        aria-label="Change Site Boundary"
                        onClick={() => {
                          onUnlockSite();
                          clearDraftGeometry();
                          setDrawMode("select");
                          onSetPreviewInteraction("edit");
                        }}
                        className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700"
                      >
                        Change Site
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={resetCanvasView}
                      className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700"
                    >
                      Reset
                    </button>
                    <button
                      type="button"
                      disabled={!selectedDeletableObject}
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
                      className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-300"
                    >
                      Delete
                    </button>
                  </div>
                  {finishDraftBlockedReason ? (
                    <p className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700">
                      {finishDraftBlockedReason}
                    </p>
                  ) : null}
                </div>
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
                {previewMode === "2d" ? (
                  <>
                    <div className="pointer-events-none absolute left-4 top-4 z-[45] flex items-start gap-2">
                      <div
                        aria-label="Plan north arrow"
                        data-testid="plan-north-arrow"
                        role="img"
                        className="flex h-16 w-12 flex-col items-center justify-center rounded-lg border border-slate-300 bg-white/92 text-slate-800 shadow-sm backdrop-blur"
                      >
                        <Navigation className="h-5 w-5 -rotate-45" />
                        <span className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em]">N</span>
                      </div>
                      <div
                        aria-label="Plan scale bar"
                        data-testid="plan-scale-bar"
                        className="rounded-lg border border-slate-300 bg-white/92 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 shadow-sm backdrop-blur"
                      >
                        <div className="mb-1 flex items-center justify-between gap-4">
                          <span>Scale</span>
                          <span>{planScaleBar.lengthFt} ft</span>
                        </div>
                        <div className="flex h-3 w-28 overflow-hidden rounded-sm border border-slate-800 bg-white">
                          {[0, 1, 2, 3].map((segment) => (
                            <span
                              key={`scale-segment-${segment}`}
                              className={`h-full flex-1 ${segment % 2 === 0 ? "bg-slate-900" : "bg-white"}`}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                    <div
                      className="civora-preview-zoom-controls absolute right-4 top-[4.75rem] z-[45] flex flex-col overflow-hidden rounded-lg border border-slate-300 bg-white/92 shadow-sm backdrop-blur"
                      onMouseDown={(event) => event.stopPropagation()}
                      onClick={(event) => event.stopPropagation()}
                    >
                      <button
                        type="button"
                        aria-label="Zoom in canvas"
                        title="Zoom in canvas"
                        onClick={() => {
                          userAdjustedCanvasViewRef.current = true;
                          setCanvasView((prev) => ({ ...prev, scale: Math.min(prev.scale + 0.15, 4) }));
                        }}
                        className="inline-flex h-9 w-9 items-center justify-center border-b border-slate-200 text-slate-700 transition hover:bg-slate-50"
                      >
                        <ZoomIn className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        aria-label="Zoom out canvas"
                        title="Zoom out canvas"
                        onClick={() => {
                          userAdjustedCanvasViewRef.current = true;
                          setCanvasView((prev) => ({ ...prev, scale: Math.max(prev.scale - 0.15, 0.55) }));
                        }}
                        className="inline-flex h-9 w-9 items-center justify-center border-b border-slate-200 text-slate-700 transition hover:bg-slate-50"
                      >
                        <ZoomOut className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        aria-label="Reset canvas view"
                        title="Reset canvas view"
                        onClick={resetCanvasView}
                        className="inline-flex h-9 w-9 items-center justify-center text-slate-700 transition hover:bg-slate-50"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </button>
                    </div>
                    <div
                      aria-label="Canvas coordinate readout"
                      data-testid="canvas-coordinate-readout"
                      className="civora-preview-coordinate-readout pointer-events-none absolute bottom-4 left-4 z-[45] rounded-lg border border-slate-300 bg-white/92 px-3 py-2 font-mono text-[11px] text-slate-700 shadow-sm backdrop-blur"
                    >
                      <div>ZOOM {Math.round(canvasView.scale * 100)}%</div>
                      <div>
                        X {cursorSitePoint ? cursorSitePoint.x.toFixed(1) : "--"} ft / Y{" "}
                        {cursorSitePoint ? cursorSitePoint.y.toFixed(1) : "--"} ft
                      </div>
                    </div>
                    {draftPrecisionReadout ? (
                      <div
                        aria-label="Draft precision readout"
                        data-testid="draft-precision-readout"
                        className="pointer-events-none absolute bottom-4 left-[13.5rem] z-[45] max-w-[min(360px,calc(100%-15rem))] rounded-lg border border-slate-300 bg-slate-950/86 px-3 py-2 font-mono text-[11px] text-white shadow-sm backdrop-blur max-md:left-4 max-md:bottom-24 max-md:max-w-[calc(100%-2rem)]"
                      >
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          <span>{activeDrawToolLabel}</span>
                          <span>PTS {draftPrecisionReadout.pointCount}</span>
                          <span>
                            X {draftPrecisionReadout.currentPoint ? draftPrecisionReadout.currentPoint[0].toFixed(1) : "--"} / Y{" "}
                            {draftPrecisionReadout.currentPoint ? draftPrecisionReadout.currentPoint[1].toFixed(1) : "--"}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-slate-200">
                          <span>
                            SEG{" "}
                            {draftPrecisionReadout.lastSegment
                              ? `${draftPrecisionReadout.lastSegment.length.toFixed(1)} ft @ ${draftPrecisionReadout.lastSegment.angle.toFixed(1)} deg`
                              : "--"}
                          </span>
                          {draftPrecisionReadout.polygonArea !== null ? (
                            <span>AREA {draftPrecisionReadout.polygonArea.toFixed(0)} sf</span>
                          ) : (
                            <span>TOTAL {draftPrecisionReadout.totalLength.toFixed(1)} ft</span>
                          )}
                          <span>SNAP {activeSnapPoint ? activeSnapPoint.kind : "none"}</span>
                        </div>
                        <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-300">
                          Enter {draftPrecisionReadout.finishReady ? "finish" : "when ready"} · Esc cancel
                        </div>
                      </div>
                    ) : null}
                  </>
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
                {false && !showGeneratedPlan && !showMap ? (
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
                        <defs>
                          <filter id="plan-ink-soften" x="-10%" y="-10%" width="120%" height="120%">
                            <feDropShadow dx="0" dy="0.08" stdDeviation="0.08" floodColor="rgba(15,23,42,0.18)" />
                          </filter>
                          <pattern id="cad-hatch-diagonal" patternUnits="userSpaceOnUse" width="2.4" height="2.4" patternTransform="rotate(45)">
                            <line x1="0" y1="0" x2="0" y2="2.4" stroke="rgba(15,23,42,0.34)" strokeWidth="0.16" />
                          </pattern>
                          <pattern id="cad-building-poche" patternUnits="userSpaceOnUse" width="3.2" height="3.2" patternTransform="rotate(45)">
                            <line x1="0" y1="0" x2="0" y2="3.2" stroke="rgba(15,23,42,0.16)" strokeWidth="0.12" />
                          </pattern>
                          <pattern id="cad-asphalt-light" patternUnits="userSpaceOnUse" width="3.4" height="3.4">
                            <path d="M 0 3.4 L 3.4 0" stroke="rgba(51,65,85,0.08)" strokeWidth="0.12" />
                            <path d="M 1.7 3.4 L 3.4 1.7" stroke="rgba(51,65,85,0.06)" strokeWidth="0.1" />
                          </pattern>
                          <pattern id="cad-hatch-water" patternUnits="userSpaceOnUse" width="4.4" height="2.6">
                            <path d="M 0 1.3 C 1.1 0.3 2.2 2.3 3.3 1.3 S 5.5 1.3 6.6 1.3" fill="none" stroke="rgba(2,132,199,0.42)" strokeWidth="0.18" />
                          </pattern>
                          <pattern id="cad-hatch-landscape" patternUnits="userSpaceOnUse" width="3.6" height="3.6">
                            <path d="M 0 3.2 L 3.2 0" stroke="rgba(22,101,52,0.34)" strokeWidth="0.14" />
                            <circle cx="2.8" cy="2.8" r="0.22" fill="rgba(22,101,52,0.34)" />
                          </pattern>
                        </defs>
                        <g data-testid="cad-plan-grid" opacity={showMap ? 0 : 1}>
                          <rect
                            x={0}
                            y={0}
                            width={100}
                            height={100}
                            fill={showMap ? "transparent" : isHighQuality ? "rgba(248,250,252,0.22)" : "transparent"}
                            stroke="transparent"
                            strokeWidth={0}
                          />
                          <rect
                            x={1.2}
                            y={1.2}
                            width={97.6}
                            height={97.6}
                            fill={siteLocked ? "rgba(16,185,129,0.024)" : "none"}
                            stroke={siteLocked ? "rgba(5,150,105,0.62)" : isHighQuality ? "rgba(15,23,42,0.44)" : "rgba(51,65,85,0.36)"}
                            strokeWidth={siteLocked ? 0.34 : 0.26}
                            strokeDasharray={siteLocked ? undefined : "2 1.2"}
                          />
                          {siteLocked ? (
                            <text
                              x={2.4}
                              y={4.2}
                              fontSize={1.12}
                              fill="rgba(4,120,87,0.58)"
                              fontWeight={800}
                              letterSpacing={0.16}
                            >
                              SITE LOCKED · {Math.round(lotWidth)} FT x {Math.round(lotHeight)} FT
                            </text>
                          ) : null}
                          <title>Local review canvas site extent.</title>
                          <line
                            x1={4}
                            y1={95}
                            x2={4 + planScaleBar.widthPct}
                            y2={95}
                            stroke="#0f172a"
                            strokeWidth={0.72}
                          />
                          <line x1={4} y1={93.7} x2={4} y2={96.3} stroke="#0f172a" strokeWidth={0.44} />
                          <line
                            x1={4 + planScaleBar.widthPct}
                            y1={93.7}
                            x2={4 + planScaleBar.widthPct}
                            y2={96.3}
                            stroke="#0f172a"
                            strokeWidth={0.44}
                          />
                          <text x={4} y={92.4} fontSize="2.15" fill="#0f172a" fontWeight={700}>
                            0
                          </text>
                          <text
                            x={4 + planScaleBar.widthPct}
                            y={92.4}
                            fontSize="2.15"
                            fill="#0f172a"
                            fontWeight={700}
                            textAnchor="end"
                          >
                            {planScaleBar.lengthFt} FT
                          </text>
                        </g>
                        {isHighQuality && !showMap && siteLocked ? (
                          <g data-testid="plan-grading-context-lines" opacity={0.22}>
                            {[0, 1, 2, 3, 4].map((index) => {
                              const y = 18 + index * 12.5;
                              const offset = index * 1.8;
                              return (
                                <path
                                  key={`review-contour-${index}`}
                                  d={`M ${9 + offset} ${y} C ${25 + offset} ${y - 4.2} ${37 - offset} ${y + 5.8} ${54 + offset} ${y + 1.2} S ${79 - offset} ${y - 3.6} ${93 - offset * 0.2} ${y + 1.8}`}
                                  fill="none"
                                  stroke="#64748b"
                                  strokeWidth={0.12}
                                >
                                  <title>Subtle review contour cue. Not survey control.</title>
                                </path>
                              );
                            })}
                          </g>
                        ) : null}
                        {visibleCadObjects
                          .filter((item) => !item.meta?.unsupported_entity_placeholder && item.geometryType === "polyline" && Array.isArray(item.geometry))
                          .map((item) => {
                            const points = (item.geometry || []).map(sitePointToSvgPercent);
                            if (points.length < 2) return null;
                            const visualKind = resolveVisualKind(item);
                            const visualStyle = resolveSvgVisualStyle(item, selectedBuildingId === item.id);
                            const isSelectedPolyline = selectedBuildingId === item.id;
                            const sourceState = resolveSourceState(item);
                            const isCorridorLine = visualKind === "road" || item.type === "driveway";
                            const isUtilityLine = visualKind === "utility";
                            const corridorWidthFt =
                              firstMetaNumber(item, ["corridor_width_ft", "pavement_width_ft", "width_ft", "road_width_ft"]) ??
                              (isCorridorLine ? Math.max(Math.min(item.w, item.d), 18) : null);
                            const corridorStrokeWidth =
                              corridorWidthFt && isCorridorLine
                                ? Math.max(1.15, Math.min(5.5, (corridorWidthFt / Math.max(currentSiteSize.width, currentSiteSize.height, 1)) * 100))
                                : visualStyle.strokeWidth;
                            return (
                              <g key={`poly-${item.id}`}>
                                {isHighQuality && isCorridorLine ? (
                                  <polyline
                                    data-testid="plan-road-corridor"
                                    points={points.join(" ")}
                                    fill="none"
                                    stroke={sourceState === "fallback" ? "rgba(100,116,139,0.2)" : "rgba(15, 23, 42, 0.16)"}
                                    strokeWidth={corridorStrokeWidth}
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeDasharray={sourceState === "fallback" ? "1.4 1" : undefined}
                                  />
                                ) : null}
                                {isSelectedPolyline ? (
                                  <polyline
                                    points={points.join(" ")}
                                    fill="none"
                                    stroke="rgba(15,118,110,0.42)"
                                    strokeWidth={0.82}
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeDasharray="1.8 1.2"
                                  />
                                ) : null}
                                <polyline
                                  data-testid="plan-polyline-object"
                                  points={points.join(" ")}
                                  fill="none"
                                  stroke={visualStyle.stroke}
                                  strokeWidth={isCorridorLine && isHighQuality ? Math.max(0.22, corridorStrokeWidth * 0.12) : visualStyle.strokeWidth}
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeDasharray={visualStyle.strokeDasharray || (isUtilityLine ? "1.2 0.85" : undefined)}
                                  opacity={visualStyle.opacity}
                                />
                                {isHighQuality && isCorridorLine ? (
                                  <polyline
                                    points={points.join(" ")}
                                    fill="none"
                                    stroke="url(#cad-asphalt-light)"
                                    strokeWidth={Math.max(0.34, corridorStrokeWidth * 0.42)}
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    opacity={sourceState === "fallback" ? 0.28 : 0.72}
                                  />
                                ) : null}
                                {isHighQuality && isUtilityLine ? (
                                  <g>
                                    {points.map((point, idx) => {
                                      const [x, y] = String(point).split(",").map((value) => Number(value));
                                      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
                                      return (
                                        <circle
                                          key={`utility-node-${item.id}-${idx}`}
                                          cx={x}
                                          cy={y}
                                          r={0.42}
                                          fill="#ffffff"
                                          stroke={visualStyle.stroke}
                                          strokeWidth={0.18}
                                        >
                                          <title>{sourceStateLabel(sourceState)}</title>
                                        </circle>
                                      );
                                    })}
                                  </g>
                                ) : null}
                              </g>
                            );
                          })}
                        {visibleCadObjects
                          .filter((item) => !item.meta?.unsupported_entity_placeholder && (!item.geometryType || item.geometryType === "rect") && item.type !== "site")
                          .map((item) => {
                            const rect = mapAnchoredRectPercent(item, mapRef.current);
                            const selected = selectedBuildingId === item.id;
                            const visualKind = resolveVisualKind(item);
                            const visualStyle = resolveSvgVisualStyle(item, selected);
                            const hatchFill = cadHatchPatternForItem(item);
                            const sourceState = resolveSourceState(item);
                            const isFallbackBounds = sourceState === "fallback";
                            const useShapePath = ["water", "landscape", "sidewalk"].includes(visualKind);
                            const shapePath = useShapePath
                              ? roundedSiteShapePath(rect, visualKind as "water" | "landscape" | "road" | "sidewalk")
                              : null;
                            const corridorAxis = visualKind === "road" ? rectCorridorAxis(rect) : null;
                            const cornerRadius =
                              visualKind === "road" || visualKind === "parking" || visualKind === "sidewalk"
                                ? 0.35
                                : visualKind === "building"
                                  ? 0.18
                                  : 0.7;
                            return (
                              <g key={`rect-plan-${item.id}`} data-testid="plan-rect-object">
                                {corridorAxis ? (
                                  <>
                                    <polyline
                                      data-testid="plan-road-corridor"
                                      points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                                      fill="none"
                                      stroke={visualStyle.fill}
                                      strokeWidth={corridorAxis.width}
                                      strokeLinecap="round"
                                      opacity={visualStyle.opacity}
                                    >
                                      <title>{sourceStateLabel(sourceState)}</title>
                                    </polyline>
                                    {isHighQuality ? (
                                      <polyline
                                        points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                                        fill="none"
                                        stroke="url(#cad-asphalt-light)"
                                        strokeWidth={Math.max(0.6, corridorAxis.width * 0.82)}
                                        strokeLinecap="round"
                                        opacity={sourceState === "fallback" ? 0.28 : 0.75}
                                      />
                                    ) : null}
                                    <polyline
                                      points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                                      fill="none"
                                      stroke={visualStyle.stroke}
                                      strokeWidth={Math.max(0.24, visualStyle.strokeWidth)}
                                      strokeLinecap="round"
                                      strokeDasharray={visualStyle.strokeDasharray}
                                      opacity={visualStyle.opacity}
                                    />
                                    {isHighQuality && sourceState !== "fallback" ? (
                                      <polyline
                                        points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                                        fill="none"
                                        stroke="rgba(248,250,252,0.7)"
                                        strokeWidth={0.16}
                                        strokeDasharray={item.type === "driveway" ? undefined : "1.25 1"}
                                        strokeLinecap="round"
                                      />
                                    ) : null}
                                  </>
                                ) : shapePath ? (
                                  <>
                                    <path
                                      d={shapePath}
                                      fill={isFallbackBounds ? "rgba(248,250,252,0.04)" : visualStyle.fill}
                                      stroke={visualStyle.stroke}
                                      strokeWidth={isFallbackBounds ? 0.2 : visualStyle.strokeWidth}
                                      strokeDasharray={isFallbackBounds ? "1.2 1" : visualStyle.strokeDasharray}
                                      strokeLinejoin="round"
                                    >
                                      <title>{sourceStateLabel(sourceState)}</title>
                                    </path>
                                    {hatchFill ? (
                                      <path
                                        data-testid="cad-hatch-fill"
                                        d={shapePath}
                                        fill={hatchFill}
                                        stroke="none"
                                        opacity={0.72}
                                      >
                                        <title>Draft hatch fill, review required.</title>
                                      </path>
                                    ) : null}
                                  </>
                                ) : (
                                  <>
                                    <rect
                                      data-testid={
                                        visualKind === "building"
                                          ? "professional-building-footprint"
                                          : visualKind === "parking"
                                            ? "professional-parking-field"
                                            : undefined
                                      }
                                      x={rect.left}
                                      y={rect.top}
                                      width={rect.width}
                                      height={rect.height}
                                      rx={isFallbackBounds ? 0.18 : cornerRadius}
                                      fill={isFallbackBounds ? "rgba(248,250,252,0.035)" : visualStyle.fill}
                                      stroke={visualStyle.stroke}
                                      strokeWidth={isFallbackBounds ? 0.2 : visualStyle.strokeWidth}
                                      strokeDasharray={isFallbackBounds ? "1.2 1" : visualStyle.strokeDasharray}
                                      strokeLinejoin="round"
                                    >
                                      <title>{sourceStateLabel(sourceState)}</title>
                                      </rect>
                                    {isHighQuality && visualKind === "building" ? (
                                      <rect
                                        x={rect.left}
                                        y={rect.top}
                                        width={rect.width}
                                        height={rect.height}
                                        rx={cornerRadius}
                                        fill="url(#cad-building-poche)"
                                        stroke="none"
                                        opacity={sourceState === "fallback" ? 0.28 : 0.8}
                                      />
                                    ) : null}
                                    {isFallbackBounds ? (
                                      <rect
                                        x={rect.left + rect.width * 0.03}
                                        y={rect.top + rect.height * 0.03}
                                        width={rect.width * 0.94}
                                        height={rect.height * 0.94}
                                        rx={0.14}
                                        fill="none"
                                        stroke="#cbd5e1"
                                        strokeWidth={0.06}
                                        strokeDasharray="0.4 0.9"
                                        opacity={0.5}
                                      />
                                    ) : null}
                                    {hatchFill ? (
                                      <rect
                                        data-testid="cad-hatch-fill"
                                        x={rect.left}
                                        y={rect.top}
                                        width={rect.width}
                                        height={rect.height}
                                        rx={cornerRadius}
                                        fill={hatchFill}
                                        stroke="none"
                                        opacity={0.72}
                                      >
                                        <title>Draft hatch fill, review required.</title>
                                      </rect>
                                    ) : null}
                                  </>
                                )}
                                {isHighQuality && visualKind === "water" ? (
                                  <g data-testid="plan-basin-shelf-cues">
                                    <path
                                      d={roundedSiteShapePath(
                                        {
                                          left: rect.left + rect.width * 0.1,
                                          top: rect.top + rect.height * 0.14,
                                          width: rect.width * 0.78,
                                          height: rect.height * 0.62,
                                        },
                                        "water",
                                      )}
                                      fill="none"
                                      stroke="rgba(224,242,254,0.72)"
                                      strokeWidth={0.16}
                                    />
                                    <path
                                      data-testid="professional-basin-footprint"
                                      d={roundedSiteShapePath(
                                        {
                                          left: rect.left + rect.width * 0.24,
                                          top: rect.top + rect.height * 0.32,
                                          width: rect.width * 0.5,
                                          height: rect.height * 0.32,
                                        },
                                        "water",
                                      )}
                                      fill="rgba(125,211,252,0.16)"
                                      stroke="rgba(2,132,199,0.36)"
                                      strokeWidth={0.1}
                                    />
                                    <path
                                      d={`M ${rect.left + rect.width * 0.18} ${rect.top + rect.height * 0.55} C ${rect.left + rect.width * 0.35} ${rect.top + rect.height * 0.46} ${rect.left + rect.width * 0.58} ${rect.top + rect.height * 0.64} ${rect.left + rect.width * 0.82} ${rect.top + rect.height * 0.5}`}
                                      fill="none"
                                      stroke="rgba(14,116,144,0.34)"
                                      strokeWidth={0.18}
                                      strokeLinecap="round"
                                    />
                                  </g>
                                ) : null}
                                {isHighQuality && visualKind === "building" ? (
                                  <g data-testid="professional-building-cues" opacity={sourceState === "fallback" ? 0.42 : 0.86}>
                                    <line
                                      x1={rect.left}
                                      y1={rect.top + rect.height}
                                      x2={rect.left + rect.width}
                                      y2={rect.top}
                                      stroke="rgba(15,23,42,0.32)"
                                      strokeWidth={0.12}
                                    />
                                    <line
                                      x1={rect.left}
                                      y1={rect.top}
                                      x2={rect.left + rect.width}
                                      y2={rect.top + rect.height}
                                      stroke="rgba(15,23,42,0.18)"
                                      strokeWidth={0.1}
                                    />
                                    <rect
                                      x={rect.left + rect.width * 0.08}
                                      y={rect.top + rect.height * 0.08}
                                      width={rect.width * 0.84}
                                      height={rect.height * 0.84}
                                      rx={0.08}
                                      fill="none"
                                      stroke="rgba(15,23,42,0.14)"
                                      strokeWidth={0.08}
                                    />
                                    <line
                                      x1={rect.left + rect.width * 0.43}
                                      y1={rect.top + rect.height}
                                      x2={rect.left + rect.width * 0.57}
                                      y2={rect.top + rect.height}
                                      stroke="rgba(15,23,42,0.62)"
                                      strokeWidth={0.16}
                                    />
                                    <path
                                      d={`M ${rect.left + rect.width * 0.43} ${rect.top + rect.height * 1.04} Q ${rect.left + rect.width * 0.5} ${rect.top + rect.height * 1.1} ${rect.left + rect.width * 0.57} ${rect.top + rect.height * 1.04}`}
                                      fill="none"
                                      stroke="rgba(15,23,42,0.24)"
                                      strokeWidth={0.1}
                                    />
                                  </g>
                                ) : null}
                                {isHighQuality && visualKind === "parking" && hasParkingGeometryEvidence(item) ? (
                                  <g data-testid="plan-parking-stall-cues">
                                    <line
                                      x1={rect.left + rect.width * 0.08}
                                      y1={rect.top + rect.height * 0.5}
                                      x2={rect.left + rect.width * 0.92}
                                      y2={rect.top + rect.height * 0.5}
                                      stroke="rgba(248,250,252,0.78)"
                                      strokeWidth={0.2}
                                      strokeDasharray="1 0.8"
                                    />
                                    {Array.from({ length: Math.min(10, Math.max(3, Math.round(rect.width / 3.6))) }).map((_, stallIdx, stalls) => {
                                      const x = rect.left + rect.width * (0.12 + (stallIdx / Math.max(stalls.length - 1, 1)) * 0.76);
                                      return (
                                        <line
                                          key={`parking-stall-${item.id}-${stallIdx}`}
                                          x1={x}
                                          y1={rect.top + rect.height * 0.16}
                                          x2={x}
                                          y2={rect.top + rect.height * 0.84}
                                          stroke="rgba(248,250,252,0.5)"
                                          strokeWidth={0.12}
                                        />
                                      );
                                    })}
                                  </g>
                                ) : null}
                                {selected ? (
                                  corridorAxis ? (
                                    <polyline
                                      points={`${corridorAxis.x1},${corridorAxis.y1} ${corridorAxis.x2},${corridorAxis.y2}`}
                                      fill="none"
                                      stroke="rgba(15,118,110,0.34)"
                                      strokeWidth={Math.max(0.9, corridorAxis.width + 0.32)}
                                      strokeLinecap="round"
                                      opacity={0.48}
                                    />
                                  ) : (
                                    <rect
                                      x={rect.left - 0.28}
                                      y={rect.top - 0.28}
                                      width={rect.width + 0.56}
                                      height={rect.height + 0.56}
                                      rx={0.7}
                                      fill="none"
                                      stroke="rgba(15,118,110,0.58)"
                                      strokeWidth={0.22}
                                      strokeDasharray="1.2 0.9"
                                    />
                                  )
                                ) : null}
                              </g>
                            );
                          })}
                        {visibleCadObjects
                          .filter((item) => !item.meta?.unsupported_entity_placeholder && item.geometryType === "polygon" && Array.isArray(item.geometry))
                          .map((item) => {
                            const points = (item.geometry || []).map(sitePointToSvgPercent);
                            if (points.length < 3) return null;
                            const isSelectedPolygon = selectedBuildingId === item.id;
                            const visualKind = resolveVisualKind(item);
                            const sourceState = resolveSourceState(item);
                            const visualStyle = resolveSvgVisualStyle(item, isSelectedPolygon);
                            const isFallbackBounds = sourceState === "fallback";
                            const hatchFill = cadHatchPatternForItem(item);
                            const geometry = (item.geometry || []) as Array<[number, number]>;
                            const bounds = points.reduce(
                              (acc, point) => {
                                const [rawX, rawY] = String(point).split(",").map((value) => Number(value));
                                if (!Number.isFinite(rawX) || !Number.isFinite(rawY)) return acc;
                                return {
                                  minX: Math.min(acc.minX, rawX),
                                  maxX: Math.max(acc.maxX, rawX),
                                  minY: Math.min(acc.minY, rawY),
                                  maxY: Math.max(acc.maxY, rawY),
                                };
                              },
                              { minX: 100, maxX: 0, minY: 100, maxY: 0 },
                            );
                            const stripeCount = Math.min(12, Math.max(4, Math.round((bounds.maxX - bounds.minX) / 3.2)));
                            const innerPolygonPoints = points
                              .map((point) => {
                                const [rawX, rawY] = String(point).split(",").map((value) => Number(value));
                                if (!Number.isFinite(rawX) || !Number.isFinite(rawY)) return null;
                                const centerX = (bounds.minX + bounds.maxX) / 2;
                                const centerY = (bounds.minY + bounds.maxY) / 2;
                                const inset = visualKind === "water" ? 0.82 : 0.88;
                                return `${centerX + (rawX - centerX) * inset},${centerY + (rawY - centerY) * inset}`;
                              })
                              .filter(Boolean)
                              .join(" ");
                            const innerShelf = visualKind === "water" ? scalePolygonTowardCenter(geometry, 0.78) : [];
                            const bottomShelf = visualKind === "water" ? scalePolygonTowardCenter(geometry, 0.48) : [];
                            const waterSurface =
                              visualKind === "water" &&
                              firstMetaNumber(item, ["normal_pool_elevation_ft", "water_surface_elevation_ft", "normal_pool_ft"]) !== null
                                ? scalePolygonTowardCenter(geometry, 0.62)
                                : [];
                            const roadAxis =
                              visualKind === "road"
                                ? (() => {
                                    const shapeBounds = boundsForSiteGeometry(geometry);
                                    const y = shapeBounds.minY + shapeBounds.height / 2;
                                    const x = shapeBounds.minX + shapeBounds.width / 2;
                                    return shapeBounds.width >= shapeBounds.height
                                      ? ([[shapeBounds.minX, y], [shapeBounds.maxX, y]] as Array<[number, number]>)
                                      : ([[x, shapeBounds.minY], [x, shapeBounds.maxY]] as Array<[number, number]>);
                                  })()
                                : [];
                            return (
                              <g key={`custom-poly-${item.id}`}>
                                <polygon
                                  data-testid="plan-polygon-object"
                                  points={points.join(" ")}
                                  fill={isFallbackBounds ? "rgba(248,250,252,0.035)" : visualStyle.fill}
                                  stroke={visualStyle.stroke}
                                  strokeWidth={isFallbackBounds ? 0.2 : visualStyle.strokeWidth}
                                  strokeDasharray={isFallbackBounds ? "1.2 1" : visualStyle.strokeDasharray}
                                  opacity={visualStyle.opacity}
                                  strokeLinejoin="round"
                                >
                                  <title>{sourceStateLabel(sourceState)}</title>
                                </polygon>
                                {isFallbackBounds ? (
                                  <polyline
                                    points={points.join(" ")}
                                    fill="none"
                                    stroke="#94a3b8"
                                    strokeWidth={0.08}
                                    strokeDasharray="0.4 1.2"
                                    opacity={0.5}
                                  />
                                ) : null}
                                {hatchFill ? (
                                  <polygon
                                    data-testid="cad-hatch-fill"
                                    points={points.join(" ")}
                                    fill={hatchFill}
                                    stroke="none"
                                    opacity={0.72}
                                  >
                                    <title>Draft hatch fill, review required.</title>
                                  </polygon>
                                ) : null}
                                {isHighQuality && visualKind === "parking" && supportsParkingModuleRendering(item) ? (
                                  <g data-testid="plan-parking-stall-cues" opacity={0.72}>
                                    <line
                                      x1={bounds.minX + (bounds.maxX - bounds.minX) * 0.1}
                                      y1={(bounds.minY + bounds.maxY) / 2}
                                      x2={bounds.maxX - (bounds.maxX - bounds.minX) * 0.1}
                                      y2={(bounds.minY + bounds.maxY) / 2}
                                      stroke="rgba(248,250,252,0.75)"
                                      strokeWidth={0.18}
                                      strokeDasharray="1.1 0.8"
                                    />
                                    {Array.from({ length: stripeCount }).map((_, stripeIdx) => {
                                      const x =
                                        bounds.minX +
                                        (bounds.maxX - bounds.minX) *
                                          (0.12 + (stripeIdx / Math.max(stripeCount - 1, 1)) * 0.76);
                                      return (
                                        <line
                                          key={`poly-parking-stall-${item.id}-${stripeIdx}`}
                                          x1={x}
                                          y1={bounds.minY + (bounds.maxY - bounds.minY) * 0.16}
                                          x2={x}
                                          y2={bounds.maxY - (bounds.maxY - bounds.minY) * 0.16}
                                          stroke="rgba(248,250,252,0.48)"
                                          strokeWidth={0.1}
                                        />
                                      );
                                    })}
                                  </g>
                                ) : null}
                                {isHighQuality && visualKind === "water" && innerPolygonPoints ? (
                                  <g data-testid="plan-basin-shelf-cues">
                                    <polygon
                                      points={(innerShelf.length ? innerShelf.map(sitePointToSvgPercent).join(" ") : innerPolygonPoints)}
                                      fill="none"
                                      stroke="rgba(224,242,254,0.7)"
                                      strokeWidth={0.16}
                                      strokeLinejoin="round"
                                    />
                                    {bottomShelf.length ? (
                                      <polygon
                                        points={bottomShelf.map(sitePointToSvgPercent).join(" ")}
                                        fill="rgba(2,132,199,0.1)"
                                        stroke="rgba(3,105,161,0.6)"
                                        strokeWidth={0.14}
                                        strokeLinejoin="round"
                                      />
                                    ) : null}
                                    {waterSurface.length ? (
                                      <polygon
                                        points={waterSurface.map(sitePointToSvgPercent).join(" ")}
                                        fill="rgba(125,211,252,0.24)"
                                        stroke="rgba(14,165,233,0.58)"
                                        strokeWidth={0.12}
                                        strokeLinejoin="round"
                                      />
                                    ) : null}
                                  </g>
                                ) : null}
                                {isHighQuality && visualKind === "road" && roadAxis.length === 2 ? (
                                  <polyline
                                    points={roadAxis.map(sitePointToSvgPercent).join(" ")}
                                    fill="none"
                                    stroke="rgba(248,250,252,0.62)"
                                    strokeWidth={0.14}
                                    strokeDasharray={item.type === "driveway" ? undefined : "1.25 1"}
                                    strokeLinecap="round"
                                  />
                                ) : null}
                              </g>
                            );
                          })}
                        {visibleCadObjects
                          .filter((item) => item.geometryType === "point" && item.meta?.cad_symbol)
                          .map((item) => {
                            const symbol = String(item.meta?.cad_symbol || "utility_marker") as CadSymbolKind;
                            const glyph: Record<CadSymbolKind, string> = {
                              hydrant: "H",
                              inlet: "I",
                              manhole: "M",
                              valve: "V",
                              tree: "T",
                              light: "L",
                              sign: "S",
                              utility_marker: "U",
                              benchmark: "B",
                              note_callout: "N",
                            };
                            const [x, y] = sitePointToPreviewPercent(
                              Array.isArray(item.geometry) && item.geometry[0]
                                ? item.geometry[0]
                                : [(item.x ?? 0) + item.w / 2, (item.y ?? 0) + item.d / 2],
                            );
                            return (
                              <g key={`cad-symbol-${item.id}`} data-testid="cad-symbol">
                                <circle cx={x} cy={y} r={1.55} fill="#ffffff" stroke="#0f172a" strokeWidth={0.42} />
                                <text x={x} y={y + 0.72} textAnchor="middle" fontSize="2.3" fill="#0f172a" fontWeight={800}>
                                  {glyph[symbol] ?? "U"}
                                </text>
                              </g>
                            );
                          })}
                        {visibleCadObjects
                          .filter((item) => item.meta?.cad_entity_type === "circle" && Number.isFinite(Number(item.meta?.cad_radius)))
                          .map((item) => {
                            const center = Array.isArray(item.geometry) && item.geometry[0]
                              ? item.geometry[0]
                              : ([(item.x ?? 0) + item.w / 2, (item.y ?? 0) + item.d / 2] as [number, number]);
                            const [x, y] = sitePointToPreviewPercent(center);
                            const radiusFt = Math.max(0, Number(item.meta?.cad_radius));
                            const radiusPct = Math.max(0.35, (radiusFt / Math.max(currentSiteSize.width, currentSiteSize.height, 1)) * 100);
                            const isSelected = selectedBuildingId === item.id;
                            return (
                              <g key={`cad-circle-${item.id}`} data-testid="cad-entity-circle">
                                <circle
                                  cx={x}
                                  cy={y}
                                  r={radiusPct}
                                  fill="rgba(124, 58, 237, 0.08)"
                                  stroke={isSelected ? "#f59e0b" : "#7c3aed"}
                                  strokeWidth={isSelected ? 0.75 : 0.42}
                                >
                                  <title>{String(item.meta?.cad_source_confidence || "review required")}</title>
                                </circle>
                              </g>
                            );
                          })}
                        {visibleCadObjects
                          .filter((item) => item.meta?.cad_entity_type === "text")
                          .map((item) => {
                            const insert = Array.isArray(item.geometry) && item.geometry[0]
                              ? item.geometry[0]
                              : ([(item.x ?? 0) + item.w / 2, (item.y ?? 0) + item.d / 2] as [number, number]);
                            const [x, y] = sitePointToPreviewPercent(insert);
                            return (
                              <g key={`cad-text-${item.id}`} data-testid="cad-entity-text">
                                <circle cx={x} cy={y} r={0.5} fill="#64748b" opacity={0.72} />
                              </g>
                            );
                          })}
                        {visibleCadObjects
                          .filter((item) => item.meta?.unsupported_entity_placeholder)
                          .map((item) => {
                            const rect = mapAnchoredRectPercent(item, mapRef.current);
                            const blockers = Array.isArray(item.meta?.cad_review_blockers) ? item.meta.cad_review_blockers.map(String) : [];
                            return (
                              <g key={`cad-unsupported-${item.id}`} data-testid="cad-entity-unsupported">
                                <rect
                                  x={rect.left}
                                  y={rect.top}
                                  width={Math.max(1.2, rect.width)}
                                  height={Math.max(1.2, rect.height)}
                                  fill="rgba(251, 191, 36, 0.12)"
                                  stroke="#b45309"
                                  strokeWidth={0.42}
                                  strokeDasharray="1.4 1"
                                >
                                  <title>{blockers[0] || "Unsupported CAD entity requires review."}</title>
                                </rect>
                              </g>
                            );
                          })}
                        {visibleCadObjects
                          .filter((item) => item.meta?.cad_dimension_label && shouldRevealObjectLabel(item) && getObjectGeometryPoints(item).length >= 2)
                          .map((item) => {
                            const points = getObjectGeometryPoints(item);
                            const [a, b] = points;
                            const mode = String(item.meta?.cad_dimension_mode || "linear");
                            const start: [number, number] = mode === "linear" ? [a[0], Math.max(a[1], b[1]) + 8] : a;
                            const end: [number, number] = mode === "linear" ? [b[0], Math.max(a[1], b[1]) + 8] : b;
                            const [x1, y1] = sitePointToPreviewPercent(start);
                            const [x2, y2] = sitePointToPreviewPercent(end);
                            const labelX = (x1 + x2) / 2;
                            const labelY = (y1 + y2) / 2 - 1.1;
                            return (
                              <g key={`cad-dim-${item.id}`} data-testid="cad-dimension-label">
                                <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#0f766e" strokeWidth={0.35} strokeDasharray="1 0.7" />
                                <circle cx={x1} cy={y1} r={0.42} fill="#0f766e" />
                                <circle cx={x2} cy={y2} r={0.42} fill="#0f766e" />
                                <text x={labelX} y={Math.max(labelY, 3)} textAnchor="middle" fontSize="2.2" fill="#0f766e" fontWeight={800}>
                                  {String(item.meta?.cad_dimension_label).slice(0, 24)}
                                </text>
                              </g>
                            );
                          })}
                        {visibleCadObjects
                          .filter((item) => item.type === "parking" && item.placed && hasParkingGeometryEvidence(item))
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
                        {waterFireFlow.hasData ? (
                          <g>
                            {waterFireFlow.pressureZones.map((zone) => {
                              if (zone.geometry.length < 3) return null;
                              const points = zone.geometry
                                .map((pt) => sitePointToPreviewPercent(pt).join(","))
                                .join(" ");
                              return (
                                <polygon
                                  key={`water-zone-${zone.id}`}
                                  points={points}
                                  fill={zone.color}
                                  opacity={0.1}
                                  stroke={zone.color}
                                  strokeWidth={0.45}
                                  strokeDasharray="2 1"
                                />
                              );
                            })}
                            {waterFireFlow.networkSegments.map((segment) => {
                              if (segment.geometry.length < 2) return null;
                              const points = segment.geometry
                                .map((pt) => sitePointToPreviewPercent(pt).join(","))
                                .join(" ");
                              return (
                                <polyline
                                  key={`water-segment-${segment.id}`}
                                  points={points}
                                  fill="none"
                                  stroke={segment.networkType === "loop" ? "#0284c7" : "#f97316"}
                                  strokeWidth={segment.networkType === "loop" ? 0.72 : 0.58}
                                  strokeDasharray={segment.networkType === "loop" ? undefined : "1.5 1"}
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                              );
                            })}
                            {waterFireFlow.hydrants.map((hydrant) => {
                              const [x, y] = sitePointToPreviewPercent([hydrant.x, hydrant.y]);
                              const selected = waterFireFlow.selectedHydrant?.id === hydrant.id;
                              const statusColor =
                                hydrant.status === "pass"
                                  ? "#16a34a"
                                  : hydrant.status === "fail"
                                    ? "#dc2626"
                                    : "#f97316";
                              return (
                                <g key={`hydrant-marker-${hydrant.id}`}>
                                  <circle
                                    cx={x}
                                    cy={y}
                                    r={selected ? 1.25 : 0.92}
                                    fill={statusColor}
                                    stroke="#ffffff"
                                    strokeWidth={0.32}
                                  >
                                    <title>{hydrant.label}</title>
                                  </circle>
                                </g>
                              );
                            })}
                          </g>
                        ) : null}
                        {activeSnapPoint ? (
                          (() => {
                            const [snapX, snapY] = sitePointToPreviewPercent([activeSnapPoint.x, activeSnapPoint.y]);
                            return (
                          <g>
                            <circle
                              cx={snapX}
                              cy={snapY}
                              r={1.15}
                              fill="none"
                              stroke="#f59e0b"
                              strokeWidth={0.42}
                            />
                            <path
                              d={`M ${snapX - 1.6} ${snapY} L ${snapX + 1.6} ${snapY} M ${snapX} ${snapY - 1.6} L ${snapX} ${snapY + 1.6}`}
                              stroke="#f59e0b"
                              strokeWidth={0.32}
                              strokeLinecap="round"
                            />
                          </g>
                            );
                          })()
                        ) : null}
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
                    {showEarthworkUx && gradingEarthworkUx ? (
                      <div
                        data-testid="grading-earthwork-panel"
                        className="civora-evidence-dock civora-evidence-dock-left pointer-events-none absolute bottom-4 left-4 z-[24] w-[min(360px,calc(100%-2rem))] rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-[0_18px_45px_-30px_rgba(15,23,42,0.85)] backdrop-blur"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                              Grading / earthwork
                            </p>
                            <p className="mt-1 font-semibold text-slate-900">
                              {gradingEarthworkUx.surfaceComparison.deltaLabel}
                            </p>
                          </div>
                          <span
                            className={`rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                              gradingEarthworkUx.haulBalance.direction === "export"
                                ? "border-rose-200 bg-rose-50 text-rose-700"
                                : gradingEarthworkUx.haulBalance.direction === "import"
                                  ? "border-sky-200 bg-sky-50 text-sky-700"
                                  : "border-emerald-200 bg-emerald-50 text-emerald-700"
                            }`}
                          >
                            {gradingEarthworkUx.haulBalance.label}
                          </span>
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-2">
                          {[
                            ["Cut", gradingEarthworkUx.haulBalance.cutCf, "cf"],
                            ["Fill", gradingEarthworkUx.haulBalance.fillCf, "cf"],
                            ["Net", gradingEarthworkUx.haulBalance.netCf, "cf"],
                          ].map(([label, value, unit]) => (
                            <div key={label as string} className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5">
                              <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                {label as string}
                              </p>
                              <p className="mt-0.5 font-semibold text-slate-800">
                                {typeof value === "number" ? formatMetric(value, unit as string) : "Pending"}
                              </p>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          <div className="rounded-lg border border-slate-200 bg-white px-2 py-2">
                            <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                              Surface comparison
                            </p>
                            <p className="mt-1 text-[11px] font-semibold text-slate-700">
                              {gradingEarthworkUx.surfaceComparison.existing} to {gradingEarthworkUx.surfaceComparison.proposed}
                            </p>
                          </div>
                          <div className="rounded-lg border border-slate-200 bg-white px-2 py-2">
                            <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                              Wall trigger
                            </p>
                            <p className="mt-1 text-[11px] font-semibold text-slate-700">
                              {gradingEarthworkUx.retainingWall.label}
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.12em]">
                          <span className="inline-flex items-center gap-1 text-rose-700">
                            <span className="h-2 w-2 rounded-sm bg-rose-500/70" />
                            Cut
                          </span>
                          <span className="inline-flex items-center gap-1 text-sky-700">
                            <span className="h-2 w-2 rounded-sm bg-sky-500/70" />
                            Fill
                          </span>
                          <span className="inline-flex items-center gap-1 text-emerald-700">
                            <span className="h-2 w-2 rounded-sm bg-emerald-500/70" />
                            Balanced
                          </span>
                          {surfaceModel ? (
                            <span className="inline-flex items-center gap-1 text-teal-700">
                              <span className="h-2 w-2 rounded-sm bg-teal-600/70" />
                              {surfaceModel.model?.toUpperCase() || "SURFACE"}
                            </span>
                          ) : null}
                        </div>
                        {surfaceModel ? (
                          <p className="mt-2 text-[10px] font-medium text-slate-500">
                            Source: {surfaceModel.sourceType || "surface"} · Control {surfaceModel.controlVerified ? "verified" : "not verified"}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    <div
                      data-testid="preview-drawing-surface"
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
                            aria-label={`Select ${item.label || item.type || "CAD object"}`}
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
                                  {cadCommandStatus}
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
              {waterFireFlow.hasData ? (
                <div className="civora-evidence-dock civora-evidence-dock-right pointer-events-auto absolute bottom-3 left-3 right-3 z-40 rounded-lg border border-slate-200/80 bg-white/94 p-3 text-xs text-slate-700 shadow-[0_18px_55px_-32px_rgba(15,23,42,0.6)] backdrop-blur sm:left-auto sm:bottom-6 sm:right-6 sm:w-[380px] sm:max-w-[calc(100%-3rem)]">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        <Flame className="h-3.5 w-3.5 text-orange-500" />
                        Water / Fire Flow
                      </p>
                      <p className="mt-1 text-sm font-semibold text-slate-950">
                        {waterFireFlow.selectedScenario?.label || "Hydrant scenarios"}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-semibold text-slate-600">
                      <Table2 className="h-3.5 w-3.5" />
                      {waterFireFlow.scenarios.length || waterFireFlow.hydrants.length} rows
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase text-slate-500">
                        <Droplets className="h-3.5 w-3.5 text-sky-600" />
                        Hydrants
                      </div>
                      <p className="mt-1 text-lg font-semibold text-slate-950">{waterFireFlow.hydrants.length}</p>
                    </div>
                    <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase text-slate-500">
                        <GitBranch className="h-3.5 w-3.5 text-sky-600" />
                        Loops
                      </div>
                      <p className="mt-1 text-lg font-semibold text-slate-950">
                        {waterFireFlow.networkSegments.filter((item) => item.networkType === "loop").length}
                      </p>
                    </div>
                    <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
                      <div className="text-[11px] font-semibold uppercase text-slate-500">Residual</div>
                      <p
                        className={`mt-1 text-lg font-semibold ${
                          waterFireFlow.selectedScenario?.status === "pass"
                            ? "text-emerald-700"
                            : waterFireFlow.selectedScenario?.status === "fail"
                              ? "text-rose-700"
                              : "text-amber-700"
                        }`}
                      >
                        {waterFireFlow.selectedScenario
                          ? formatFlowValue(waterFireFlow.selectedScenario.residualPressurePsi, "psi", 1)
                          : "Review"}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 max-h-[156px] overflow-auto rounded-md border border-slate-200">
                    <table className="w-full border-collapse text-left text-[11px]">
                      <thead className="sticky top-0 bg-slate-50 text-slate-500">
                        <tr>
                          <th className="px-2 py-1.5 font-semibold">Hydrant</th>
                          <th className="px-2 py-1.5 font-semibold">Network</th>
                          <th className="px-2 py-1.5 font-semibold">Flow</th>
                          <th className="px-2 py-1.5 font-semibold">Residual</th>
                          <th className="px-2 py-1.5 font-semibold">Check</th>
                        </tr>
                      </thead>
                      <tbody>
                        {waterFireFlow.scenarios.length ? (
                          waterFireFlow.scenarios.map((scenario) => {
                            const hydrant = waterFireFlow.hydrants.find((item) => item.id === scenario.hydrantId);
                            const selected = waterFireFlow.selectedScenario?.id === scenario.id;
                            return (
                              <tr
                                key={scenario.id}
                                className={`cursor-pointer border-t border-slate-100 ${
                                  selected ? "bg-sky-50" : "hover:bg-slate-50"
                                }`}
                                onClick={() => setSelectedFireScenarioId(scenario.id)}
                              >
                                <td className="px-2 py-1.5 font-semibold text-slate-900">
                                  {hydrant?.label || scenario.hydrantId || "Hydrant"}
                                </td>
                                <td className="px-2 py-1.5 capitalize">{scenario.networkType.replace("_", " ")}</td>
                                <td className="px-2 py-1.5">
                                  {formatFlowValue(scenario.availableFlowGpm, "gpm", 0)}/
                                  {formatFlowValue(scenario.requiredFlowGpm, "gpm", 0)}
                                </td>
                                <td className="px-2 py-1.5">
                                  {formatFlowValue(scenario.residualPressurePsi, "psi", 1)}
                                  {scenario.missingInputs.length ? (
                                    <div className="mt-0.5 text-[10px] font-semibold text-amber-700">
                                      Missing: {scenario.missingInputs.slice(0, 2).join(", ")}
                                    </div>
                                  ) : null}
                                </td>
                                <td
                                  className={`px-2 py-1.5 font-semibold uppercase ${
                                    scenario.status === "pass"
                                      ? "text-emerald-700"
                                      : scenario.status === "fail"
                                        ? "text-rose-700"
                                        : "text-amber-700"
                                  }`}
                                >
                                  {scenario.status}
                                </td>
                              </tr>
                            );
                          })
                        ) : (
                          <tr>
                            <td className="px-2 py-4 text-slate-500" colSpan={5}>
                              Canonical hydrants found. Add pressure/flow data to run checks.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <span className="h-2 w-5 rounded-full bg-sky-600" />
                      Loop
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span className="h-2 w-5 rounded-full border border-orange-400 border-dashed" />
                      Dead-end
                    </span>
                    <span>
                      Target residual: {formatFlowValue(waterFireFlow.selectedScenario?.residualTargetPsi ?? null, "psi", 0)}
                    </span>
                    {waterFireFlow.blockerCards.length ? (
                      <span className="font-semibold text-amber-700">
                        {waterFireFlow.blockerCards.length} blocker cards
                      </span>
                    ) : null}
                    <span className="font-semibold text-slate-600">
                      Engineer review required
                    </span>
                  </div>
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
                    {visibleCadObjects
                      .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                      .map((item) => {
                        const rectPct = interactiveRectPercent(item, fullscreenMapRef.current);
                        if (!rectIntersectsPreview(rectPct)) return null;
                        const rotation = showMap ? 0 : (item.rotation ?? 0);
                        const isSite = item.type === "site";
                        const allowItemInteraction =
                          !isSite || (previewInteraction === "edit" && !siteLocked);
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
