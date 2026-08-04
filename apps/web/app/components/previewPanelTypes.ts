import type {
  BuildingPlacement,
  GradingEarthworkUx,
  Preview3DItem,
  PreviewResponse,
  PreviewReview,
} from "../types";
import type { CadToolRequest, DrawMode } from "../utils/cadToolTypes";

export type EngineeringSystemStatus = "fresh" | "stale" | "not_generated";

export type EngineeringSystemStatuses = Record<
  "roads" | "parking" | "grading" | "drainage" | "utilities",
  EngineeringSystemStatus
>;

export type CadPoint = { x: number; y: number };

export type CadHistoryEntry = {
  id: string;
  label: string;
  objectId: string;
  before: BuildingPlacement;
  after: BuildingPlacement;
};

export const BALANCED_CANVAS_SCALE = 0.58;

export type CadCommandHistoryEntry = {
  id: string;
  command: string;
  status: "applied" | "blocked" | "info";
  message: string;
};

export type CadActiveCommand =
  | {
      kind: "draw";
      command: "LINE" | "PLINE" | "RECTANGLE";
      mode: Extract<DrawMode, "polyline" | "rect">;
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
    };

export const formatCalmCadStatus = (message: string) =>
  message
    .replace(/\bblocked:/gi, "needs input:")
    .replace(/\bblocked\b/gi, "needs input")
    .replace(/\bBlocked\b/g, "Needs input")
    .replace(/\bfailed\b/gi, "could not complete")
    .replace(/\binvalid\b/gi, "needs correction")
    .replace(/\bInvalid\b/g, "Needs correction");

export type StormHydrologyOverlay = {
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

export type WaterHydrantView = {
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

export type WaterPressureZoneView = {
  id: string;
  label: string;
  minPressurePsi: number | null;
  maxPressurePsi: number | null;
  residualTargetPsi: number;
  color: string;
  geometry: Array<[number, number]>;
};

export type WaterNetworkSegmentView = {
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

export type FireScenarioView = {
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

export type CoordinationSeverity = "clear" | "watch" | "conflict";

export type UtilityCoordinationRow = {
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

export type AiRealismArtifact = {
  type: "high_quality_ai_render_v1";
  project_id: string;
  source_layout_hash: string;
  site_frame: {
    width_ft: number;
    height_ft: number;
    map_context_available: boolean;
  };
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

export const AI_REALISM_WATERMARK =
  "AI visualization from current review layout - visual concept only, not engineering evidence.";

export type PreviewPanelProps = {
  previewReview: PreviewReview | null;
  onRefreshPreview: () => void;
  busy: boolean;
  planPreviewUrl: string;
  planPreviewProjectId?: string | null;
  currentProjectId?: string | null;
  previewMode: "2d" | "3d";
  previewInteraction: "static" | "edit";
  previewQuality: "standard" | "high";
  systemStatuses: EngineeringSystemStatuses;
  hasTerrainSource: boolean;
  hasSourceBackedSurfaceEvidence: boolean;
  hasBasinPlaced: boolean;
  siteTooLargeForGrading: boolean;
  hasHardSystemBlock: boolean;
  hasGeneratedPlan: boolean;
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  onSetPreviewQuality: (value: "standard" | "high") => void;
  onAiRealismChange?: (event: { type: "generated" | "stale" | "blocked"; detail: string }) => void;
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
  }) => boolean;
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
  planPreviewAnnotations: PreviewResponse["preview_annotations"] | null;
  selectedIssueLabel: string;
  showMeasurements: boolean;
  showCalculations: boolean;
  measurementOverlayStats: Array<{ label: string; value: number | null; unit: string }>;
  calculationOverlayStats: Array<{ label: string; value: number | null; unit: string }>;
  gradingEarthworkUx?: GradingEarthworkUx | null;
  geocode?: { lat?: number; lng?: number } | null;
  mapScaleFtPerPx?: number | null;
  mapScaleSource?: "mapbox" | "manual" | "approximate" | null;
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
