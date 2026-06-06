"use client";
/* eslint-disable react-hooks/exhaustive-deps */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import {
  AlertCircle,
  Box,
  ClipboardCheck,
  CheckCircle2,
  Circle,
  FileText,
  Gauge,
  Layers,
  MapPinned,
  Settings,
} from "lucide-react";

import { deleteJson, getJson, postBinary, postForm, postJson } from "../lib/api";

import type {
  Assumption,
  Issue,
  BackendAssumption,
  BackendIssue,
  ManualFields,
  ProjectRecord,
  ProjectInput,
  JobSummary,
  WorkflowRunSummary,
  WorkflowReviewDashboard,
  ManualFailure,
  ManagerMetrics,
  QuantityTotals,
  PipeSegment,
  StormSummary,
  PlanExplanation,
  PlanMeta,
  PlanResponse,
  SurveySlopeResponse,
  SurveyPointsResponse,
  ImageDetectResponse,
  MapAnalysis,
  PreviewResponse,
  UploadImageResponse,
  UploadSurveyResponse,
  UserRecord,
  PlanToolMode,
  ControlOverrides,
  BuildingPlacement,
  SiteObjectType,
  ChatDecisionResponse,
  ChatMessage,
  DisciplineToggle,
  Preview3DItem,
  PlanRequestPayload,
  PreviewRequestPayload,
  SiteInputs,
  CanonicalGeometryHandoffV1,
} from "./types";
import type { CivoraWorkflowStep } from "./design-system";

type SystemGenerationTarget = "roads" | "parking" | "grading" | "drainage" | "utilities" | "full";
type EngineeringSystemKey = Exclude<SystemGenerationTarget, "full">;
type ReactiveValidationState = {
  status: "idle" | "pending" | "ready";
  changedSystems: EngineeringSystemKey[];
  changedTargets: string[];
  requiresConfirmation: boolean;
  message: string;
};
type SidePanelKey =
  | "projects"
  | "dashboard"
  | "model"
  | "site_existing"
  | "import_survey"
  | "objects"
  | "generate"
  | "grading"
  | "drainage"
  | "sanitary"
  | "water"
  | "utilities"
  | "roadway"
  | "landscape"
  | "details"
  | "layers"
  | "analysis"
  | "reports"
  | "quantities"
  | "deliverables"
  | "files"
  | "standards"
  | "libraries"
  | "data"
  | "settings"
  | "chat"
  | "system_grading"
  | "system_storm"
  | "system_sanitary"
  | "system_water"
  | "system_roadway"
  | "system_utilities"
  | "system_landscape";
type WorkspaceMode =
  | "dashboard"
  | "setup"
  | "canvas"
  | "layers"
  | "review"
  | "deliver"
  | "data"
  | "settings";
type SidebarStatus = "ok" | "review" | "block" | "idle";
type CapabilityExposure = {
  key: string;
  label: string;
  exposed: "yes" | "no";
  surfaces: string[];
  status: SidebarStatus;
  value: string;
  missingWiring: string;
  exactFix: string;
};
type AddressSuggestion = {
  success?: boolean;
  status?: string;
  blocked?: boolean;
  lat?: number;
  lng?: number;
  display_name?: string;
  provider?: string;
  message?: string;
  confidence?: number | string | null;
  crs?: Record<string, unknown>;
  location_context?: Record<string, unknown>;
  blockers?: Array<{ area?: string; code?: string; message?: string }>;
};
const hasAddressCoordinates = (
  value: AddressSuggestion | null | undefined,
): value is AddressSuggestion & { lat: number; lng: number; display_name: string } =>
  Boolean(
    value &&
      !value.blocked &&
      Number.isFinite(value.lat) &&
      Number.isFinite(value.lng) &&
      value.display_name,
  );
type BottomPanelTab = "model_review" | "systems" | "objects" | "properties" | "history";
type SidebarNavItem = {
  label: string;
  caption: string;
  target: WorkspaceMode;
  icon: typeof Gauge;
  status: SidebarStatus;
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
  autoResizeToFitCount?: boolean;
  useMixedAngles?: boolean;
  compactZone?: boolean;
};

const SQFT_PER_ACRE = 43_560;
const SITE_WARNING_ACRES = 250;
const SITE_GRADING_HARD_BLOCK_ACRES = 500;
const DEFAULT_BLANK_SITE_WIDTH_FT = 300;
const DEFAULT_BLANK_SITE_DEPTH_FT = 300;
const OVERSIZED_SITE_MESSAGE =
  "Selected site is very large. Zoom in or reduce site area before grading.";

function buildAssumedSlopeEstimate(): SurveySlopeResponse {
  return {
    success: true,
    slope_ratio: 0.015,
    slope_percent: 1.5,
    downhill_dx: 1,
    downhill_dy: 1,
    direction: "southeast",
    point_count: 0,
    warnings: [
      "First-pass assumed slope for early layout only. Replace with survey, DEM, or map terrain before final engineering.",
    ],
  };
}

const siteAreaAcresFromSize = (widthFt?: number | null, heightFt?: number | null) => {
  if (!widthFt || !heightFt) return 0;
  return (widthFt * heightFt) / SQFT_PER_ACRE;
};

const ADD_MENU_SECTIONS: Array<{
  title: string;
  key: string;
  items: SiteObjectType[];
  collapsible?: boolean;
}> = [
  {
    title: "Site",
    key: "site",
    items: ["site", "setback_zone", "no_build_zone"],
  },
  {
    title: "Buildings & Program",
    key: "buildings",
    items: [
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "amenity",
      "open_space",
    ],
  },
  {
    title: "Access & Parking",
    key: "access",
    items: ["entrance", "driveway", "road", "parking", "sidewalk"],
  },
  {
    title: "Drainage & Water",
    key: "drainage",
    items: ["basin", "outfall", "inlet", "manhole", "hydrant"],
  },
  {
    title: "Advanced",
    key: "advanced",
    items: ["utility_corridor", "lot_block", "bridge"],
    collapsible: true,
  },
];

const SITE_OBJECT_CATALOG: Record<
  SiteObjectType,
  { label: string; category: string; defaultW: number; defaultD: number; defaultH?: number; use?: string }
> = {
  site: { label: "Site", category: "site", defaultW: 400, defaultD: 300 },
  setback_zone: { label: "Setback Zone", category: "site", defaultW: 200, defaultD: 120 },
  no_build_zone: { label: "No-Build Zone", category: "site", defaultW: 160, defaultD: 120 },
  building: { label: "Building", category: "buildings", defaultW: 80, defaultD: 50, defaultH: 30 },
  retail_building: {
    label: "Retail Building",
    category: "buildings",
    defaultW: 70,
    defaultD: 45,
    defaultH: 24,
    use: "retail",
  },
  multifamily_building: {
    label: "Multifamily Building",
    category: "buildings",
    defaultW: 110,
    defaultD: 58,
    defaultH: 36,
    use: "multifamily",
  },
  industrial_building: {
    label: "Industrial Building",
    category: "buildings",
    defaultW: 140,
    defaultD: 90,
    defaultH: 36,
    use: "industrial",
  },
  office_building: {
    label: "Office Building",
    category: "buildings",
    defaultW: 100,
    defaultD: 60,
    defaultH: 30,
    use: "office",
  },
  pad: { label: "Pad", category: "buildings", defaultW: 60, defaultD: 40, defaultH: 4 },
  pool: { label: "Pool", category: "buildings", defaultW: 50, defaultD: 30, defaultH: 6 },
  amenity: { label: "Amenity Area", category: "buildings", defaultW: 80, defaultD: 40, defaultH: 12 },
  open_space: { label: "Open Space", category: "buildings", defaultW: 120, defaultD: 80, defaultH: 0 },
  entrance: { label: "Entrance / Access", category: "access", defaultW: 24, defaultD: 24 },
  driveway: { label: "Driveway", category: "access", defaultW: 60, defaultD: 16 },
  road: { label: "Road / Drive Aisle", category: "access", defaultW: 120, defaultD: 28 },
  parking: { label: "Parking Field", category: "access", defaultW: 140, defaultD: 60 },
  sidewalk: { label: "Sidewalk / Path", category: "access", defaultW: 80, defaultD: 12 },
  basin: { label: "Basin / Detention Pond", category: "drainage", defaultW: 90, defaultD: 60 },
  outfall: { label: "Outfall Point", category: "drainage", defaultW: 18, defaultD: 18 },
  inlet: { label: "Inlet", category: "drainage", defaultW: 12, defaultD: 12 },
  manhole: { label: "Manhole", category: "drainage", defaultW: 12, defaultD: 12 },
  hydrant: { label: "Hydrant", category: "drainage", defaultW: 10, defaultD: 10 },
  utility_corridor: { label: "Utility Corridor", category: "advanced", defaultW: 140, defaultD: 24 },
  lot_block: { label: "Lot / Subdivision Block", category: "advanced", defaultW: 160, defaultD: 120 },
  bridge: { label: "Bridge", category: "advanced", defaultW: 80, defaultD: 24 },
  custom: { label: "Custom Geometry", category: "advanced", defaultW: 40, defaultD: 40 },
};

const clampValue = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

type CustomGeometryMode = "polygon" | "polyline" | "rect" | "point";

const isCustomGeometryMode = (value: unknown): value is CustomGeometryMode =>
  value === "polygon" || value === "polyline" || value === "rect" || value === "point";

const normalizeGeometryPoints = (points: unknown): Array<[number, number]> | undefined =>
  Array.isArray(points)
    ? points
        .map((pt) => (Array.isArray(pt) ? ([Number(pt[0]), Number(pt[1])] as [number, number]) : null))
        .filter((pt): pt is [number, number] => pt !== null && Number.isFinite(pt[0]) && Number.isFinite(pt[1]))
    : undefined;

const getGeometryBounds = (geometry: Array<[number, number]>) => {
  const xs = geometry.map((pt) => pt[0]);
  const ys = geometry.map((pt) => pt[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return {
    minX,
    maxX,
    minY,
    maxY,
    width: Math.max(0, maxX - minX),
    depth: Math.max(0, maxY - minY),
  };
};

const getGeometryLength = (geometry: Array<[number, number]>, closed = false) => {
  const points = closed && geometry.length > 2 ? [...geometry, geometry[0]] : geometry;
  return points.slice(1).reduce((sum, pt, idx) => {
    const prev = points[idx];
    return sum + Math.hypot(pt[0] - prev[0], pt[1] - prev[1]);
  }, 0);
};

const getPolygonArea = (geometry: Array<[number, number]>) => {
  if (geometry.length < 3) return 0;
  const sum = geometry.reduce((acc, pt, idx) => {
    const next = geometry[(idx + 1) % geometry.length];
    return acc + pt[0] * next[1] - next[0] * pt[1];
  }, 0);
  return Math.abs(sum) / 2;
};

const getCustomGeometryMetrics = (item: Pick<BuildingPlacement, "geometry" | "geometryType" | "w" | "d">) => {
  const geometry = Array.isArray(item.geometry) ? item.geometry : [];
  const isArea = item.geometryType === "polygon" || item.geometryType === "rect";
  const areaSf = isArea ? getPolygonArea(geometry) : 0;
  const lengthFt =
    item.geometryType === "polyline"
      ? getGeometryLength(geometry)
      : isArea
        ? getGeometryLength(geometry, true)
        : 0;
  const bounds = geometry.length ? getGeometryBounds(geometry) : { width: item.w, depth: item.d };
  return {
    areaSf,
    lengthFt,
    widthFt: bounds.width || item.w,
    depthFt: bounds.depth || item.d,
  };
};

const buildCustomGeometryMeta = (
  id: string,
  label: string,
  geometryType: CustomGeometryMode,
  geometry: Array<[number, number]>,
  units: string,
  previousMeta?: Record<string, unknown>,
) => {
  const previousVertices = Array.isArray(previousMeta?.vertices)
    ? (previousMeta.vertices as Array<{ id?: unknown }>)
    : [];
  const metrics = getCustomGeometryMetrics({ geometry, geometryType, w: 0, d: 0 });
  const timestamp = new Date().toISOString();
  const previousCreatedAt =
    typeof previousMeta?.created_at === "string" ? previousMeta.created_at : timestamp;
  return {
    ...(previousMeta ?? {}),
    schema_version: "custom_geometry_metadata_v1",
    category: "advanced",
    custom_geometry: true,
    object_id: id,
    geometry_id: id,
    reference_name: label,
    source: "manual_drawn",
    confidence: "user_drawn_review_required",
    engineering_status: "draft_review_required",
    review_status: "engineer_review_required",
    construction_release_allowed: false,
    units,
    coordinate_system: `site_local_${units || "ft"}`,
    coordinates_are: "site_local",
    source_ui_mode: "canvas_draw",
    handoff_schema: "canonical_geometry_handoff_v1",
    handoff_status: "draft_review_required",
    created_at: previousCreatedAt,
    updated_at: timestamp,
    vertices: geometry.map(([x, y], idx) => ({
      id:
        typeof previousVertices[idx]?.id === "string"
          ? previousVertices[idx].id
          : `${id}-v-${idx + 1}`,
      x,
      y,
      units,
    })),
    metrics: {
      length_ft: Number(metrics.lengthFt.toFixed(2)),
      area_sf: Number(metrics.areaSf.toFixed(2)),
      width_ft: Number(metrics.widthFt.toFixed(2)),
      depth_ft: Number(metrics.depthFt.toFixed(2)),
    },
    canonical_note:
      "Stored as user-authored project geometry for engineer review. Backend engineering generation does not automatically consume arbitrary drawn geometry.",
  };
};

const isFinitePoint = (point: unknown): point is [number, number] =>
  Array.isArray(point) &&
  typeof point[0] === "number" &&
  typeof point[1] === "number" &&
  Number.isFinite(point[0]) &&
  Number.isFinite(point[1]);

const pointsMatch = (a?: [number, number], b?: [number, number]) =>
  Boolean(a && b && Math.abs(a[0] - b[0]) < 0.0001 && Math.abs(a[1] - b[1]) < 0.0001);

const closeAreaGeometry = (geometry: Array<[number, number]>) => {
  if (!geometry.length || pointsMatch(geometry[0], geometry[geometry.length - 1])) return geometry;
  return [...geometry, geometry[0]];
};

const getMinimumCanonicalVertices = (geometryType: CustomGeometryMode) => {
  if (geometryType === "point") return 1;
  if (geometryType === "polyline") return 2;
  if (geometryType === "polygon") return 4;
  return 5;
};

const validateCanonicalGeometryHandoffV1 = (
  handoff: Omit<CanonicalGeometryHandoffV1, "valid" | "blockers">,
) => {
  const blockers: string[] = [];
  if (!handoff.object_id.trim()) blockers.push("object_id is required");
  if (!handoff.geometry_id.trim()) blockers.push("geometry_id is required");
  if (!isCustomGeometryMode(handoff.geometry_type)) {
    blockers.push("geometry_type must be point, polyline, polygon, or rect");
  }
  if (!handoff.units.trim()) blockers.push("units are required");
  if (!handoff.coordinate_system.trim()) blockers.push("coordinate_system is required");
  if (handoff.source !== "manual_drawn") blockers.push("source must be manual_drawn");
  if (handoff.confidence !== "user_drawn_review_required") {
    blockers.push("confidence must be user_drawn_review_required");
  }
  if (handoff.engineering_status !== "draft_review_required") {
    blockers.push("engineering_status must remain draft_review_required");
  }
  const minimumVertices = isCustomGeometryMode(handoff.geometry_type)
    ? getMinimumCanonicalVertices(handoff.geometry_type)
    : 0;
  if (handoff.vertices.length < minimumVertices) {
    blockers.push(
      `vertices must include at least ${minimumVertices} point${minimumVertices === 1 ? "" : "s"} for ${handoff.geometry_type}`,
    );
  }
  if (handoff.vertices.some((vertex) => !vertex.id.trim())) {
    blockers.push("all vertices require stable ids");
  }
  if (
    handoff.vertices.some(
      (vertex) => !Number.isFinite(vertex.x) || !Number.isFinite(vertex.y),
    )
  ) {
    blockers.push("all vertex coordinates must be finite numbers");
  }
  if (handoff.vertices.some((vertex) => !vertex.units.trim())) {
    blockers.push("all vertices require units");
  }
  if (handoff.geometry_type === "polygon" || handoff.geometry_type === "rect") {
    const first = handoff.vertices[0];
    const last = handoff.vertices[handoff.vertices.length - 1];
    if (!first || !last || Math.abs(first.x - last.x) >= 0.0001 || Math.abs(first.y - last.y) >= 0.0001) {
      blockers.push(`${handoff.geometry_type} geometry must be closed`);
    }
  }
  return blockers;
};

const buildCanonicalGeometryHandoffV1 = (
  item: BuildingPlacement,
  fallbackUnits: string,
): CanonicalGeometryHandoffV1 | null => {
  if (item.type !== "custom" || !isCustomGeometryMode(item.geometryType)) return null;
  const metadata = item.meta ?? {};
  const objectId =
    typeof metadata.object_id === "string" && metadata.object_id.trim()
      ? metadata.object_id
      : item.id;
  const geometryId =
    typeof metadata.geometry_id === "string" && metadata.geometry_id.trim()
      ? metadata.geometry_id
      : objectId;
  const units =
    typeof metadata.units === "string" && metadata.units.trim()
      ? metadata.units
      : fallbackUnits;
  const coordinateSystem =
    typeof metadata.coordinate_system === "string" && metadata.coordinate_system.trim()
      ? metadata.coordinate_system
      : `site_local_${units || "ft"}`;
  const rawGeometry = Array.isArray(item.geometry) ? item.geometry : [];
  const geometry =
    item.geometryType === "polygon" || item.geometryType === "rect"
      ? closeAreaGeometry(rawGeometry.filter(isFinitePoint))
      : rawGeometry.filter(isFinitePoint);
  const storedVertices = Array.isArray(metadata.vertices)
    ? (metadata.vertices as Array<{ id?: unknown }>)
    : [];
  const metrics = getCustomGeometryMetrics({
    geometry: rawGeometry.filter(isFinitePoint),
    geometryType: item.geometryType,
    w: item.w,
    d: item.d,
  });
  const handoffCore: Omit<CanonicalGeometryHandoffV1, "valid" | "blockers"> = {
    schema_version: "canonical_geometry_handoff_v1",
    object_id: objectId,
    geometry_id: geometryId,
    object_name: item.label,
    object_type: item.type,
    geometry_type: item.geometryType,
    vertices: geometry.map(([x, y], idx) => ({
      id:
        idx < rawGeometry.length && typeof storedVertices[idx]?.id === "string"
          ? (storedVertices[idx].id as string)
          : idx >= rawGeometry.length
            ? `${geometryId}-v-close`
            : `${geometryId}-v-${idx + 1}`,
      x,
      y,
      units,
    })),
    units,
    coordinate_system: coordinateSystem,
    source: "manual_drawn",
    confidence: "user_drawn_review_required",
    engineering_status: "draft_review_required",
    metrics: {
      length_ft: Number(metrics.lengthFt.toFixed(2)),
      area_sf: Number(metrics.areaSf.toFixed(2)),
      width_ft: Number(metrics.widthFt.toFixed(2)),
      depth_ft: Number(metrics.depthFt.toFixed(2)),
    },
    created_at: typeof metadata.created_at === "string" ? metadata.created_at : undefined,
    updated_at: typeof metadata.updated_at === "string" ? metadata.updated_at : undefined,
    source_ui_mode: "canvas_draw",
  };
  const blockers = validateCanonicalGeometryHandoffV1(handoffCore);
  return {
    ...handoffCore,
    valid: blockers.length === 0,
    blockers,
  };
};

const formatCustomGeometryMetrics = (item: BuildingPlacement) => {
  const metrics = getCustomGeometryMetrics(item);
  const parts = [`${metrics.widthFt.toFixed(1)} ft x ${metrics.depthFt.toFixed(1)} ft`];
  if (item.geometryType === "polyline" && metrics.lengthFt > 0) {
    parts.push(`${metrics.lengthFt.toFixed(1)} ft length`);
  }
  if ((item.geometryType === "polygon" || item.geometryType === "rect") && metrics.areaSf > 0) {
    parts.push(`${metrics.areaSf.toFixed(0)} sf area`);
  }
  return parts.join(" · ");
};

function CustomGeometryHandoffDetails({
  item,
  units,
  compact = false,
}: {
  item: BuildingPlacement;
  units: string;
  compact?: boolean;
}) {
  const handoff = buildCanonicalGeometryHandoffV1(item, units || "ft");
  if (!handoff) return null;
  const blockerText = handoff.blockers.length ? handoff.blockers.join("; ") : "none";
  return (
    <div
      className={`mt-1 space-y-1 uppercase tracking-[0.12em] text-slate-500 ${compact ? "text-[10px]" : "text-[11px]"}`}
      data-canonical-geometry-handoff="canonical_geometry_handoff_v1"
      data-object-id={handoff.object_id}
      data-geometry-id={handoff.geometry_id}
      data-handoff-valid={handoff.valid ? "true" : "false"}
    >
      <p>Canonical geometry · Draft review required</p>
      <p>Handoff: canonical_geometry_handoff_v1 · {handoff.valid ? "valid draft" : "blocked"}</p>
      <p>Object ID: {handoff.object_id}</p>
      <p>Geometry ID: {handoff.geometry_id}</p>
      <p>Type: {handoff.geometry_type} · Name: {handoff.object_name}</p>
      <p>{formatCustomGeometryMetrics(item)}</p>
      <p>Source: manual_drawn · UI: canvas_draw</p>
      <p>Confidence: user_drawn_review_required</p>
      <p>Engineering status: draft_review_required</p>
      {!handoff.valid ? (
        <p className="text-amber-600">Handoff blockers: {blockerText}</p>
      ) : null}
    </div>
  );
}

type SystemStatus = "fresh" | "stale" | "not_generated";

const DEFAULT_SYSTEM_STATUS: Record<
  "roads" | "parking" | "grading" | "drainage" | "utilities",
  SystemStatus
> = {
  roads: "not_generated",
  parking: "not_generated",
  grading: "not_generated",
  drainage: "not_generated",
  utilities: "not_generated",
};

const REACTIVE_EDIT_POLICY_PREFERENCE = {
  live_visual_update: true,
  cheap_validation_auto_run: true,
  auto_engineering_rerun_max_cost: "quick",
  debounced_validation_ms: 500,
  require_confirmation_for_heavy_engineering: true,
  stale_exports_block_download: true,
} as const;

const REACTIVE_SYSTEM_STAGE_MAP: Record<
  EngineeringSystemKey,
  string[]
> = {
  roads: ["layout", "grading", "drainage", "storm_pipes", "utility_network", "coordination_resolution", "qa"],
  parking: ["layout", "grading", "drainage", "storm_pipes", "coordination_resolution", "qa"],
  grading: ["grading", "drainage", "storm_pipes", "sanitary", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa"],
  drainage: ["drainage", "storm_pipes", "coordination_resolution", "sheets", "qa"],
  utilities: ["sanitary", "utility_network", "coordination_resolution", "sheets", "qa"],
};

const EMPTY_REACTIVE_VALIDATION: ReactiveValidationState = {
  status: "idle",
  changedSystems: [],
  changedTargets: [],
  requiresConfirmation: false,
  message: "",
};

const DEMO_PROJECT_ID = "demo-pinecrest-mixed-use";

function isDemoWorkspaceQuery() {
  if (typeof window === "undefined") return false;
  if (window.location.pathname === "/demo/workspace") return true;
  const query = window.location.search || (window.location.href.includes("?") ? `?${window.location.href.split("?")[1]}` : "");
  const params = new URLSearchParams(query);
  const demoValue = params.get("demo") || params.get("ui_demo");
  return demoValue === "workspace" || demoValue === "1" || demoValue === "true";
}

const createDemoPlacements = (): BuildingPlacement[] => [
  {
    id: "demo-site",
    label: "Pinecrest Site",
    type: "site",
    w: 760,
    d: 520,
    x: 0,
    y: 0,
    rotation: 0,
    locked: true,
    placed: true,
    source: "user",
    generated: false,
    capabilities: { movable: false, resizable: false, rotatable: false, deletable: false },
    systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
  },
  {
    id: "demo-building-a",
    label: "Multifamily Building A",
    type: "multifamily_building",
    w: 110,
    d: 58,
    h: 36,
    x: 120,
    y: 95,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-building-b",
    label: "Multifamily Building B",
    type: "multifamily_building",
    w: 110,
    d: 58,
    h: 36,
    x: 330,
    y: 82,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-retail",
    label: "Retail Building",
    type: "retail_building",
    w: 70,
    d: 45,
    h: 24,
    x: 96,
    y: 350,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-loop-road",
    label: "Internal Loop Road",
    type: "road",
    w: 590,
    d: 28,
    x: 70,
    y: 275,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
    geometryType: "polyline",
    geometry: [
      [82, 294],
      [210, 210],
      [522, 210],
      [664, 310],
      [540, 410],
      [160, 410],
      [82, 294],
    ],
  },
  {
    id: "demo-parking-north",
    label: "Residential Parking Court",
    type: "parking",
    w: 210,
    d: 104,
    x: 255,
    y: 190,
    rotation: 0,
    stallCount: 72,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-parking-retail",
    label: "Retail Parking Field",
    type: "parking",
    w: 165,
    d: 92,
    x: 185,
    y: 345,
    rotation: 0,
    stallCount: 44,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-basin-a",
    label: "Detention Basin A",
    type: "basin",
    w: 150,
    d: 86,
    x: 540,
    y: 380,
    rotation: 0,
    placed: true,
    source: "user_confirmed",
  },
  {
    id: "demo-sidewalk",
    label: "ADA Pedestrian Route",
    type: "sidewalk",
    w: 410,
    d: 8,
    x: 120,
    y: 305,
    placed: true,
    source: "user_confirmed",
    geometryType: "polyline",
    geometry: [
      [122, 314],
      [255, 314],
      [365, 246],
      [500, 246],
      [592, 388],
    ],
  },
  {
    id: "demo-inlet-1",
    label: "Storm Inlet S-15",
    type: "inlet",
    w: 12,
    d: 12,
    x: 472,
    y: 312,
    placed: true,
    source: "generated",
  },
  {
    id: "demo-hydrant-1",
    label: "Hydrant W-12",
    type: "hydrant",
    w: 10,
    d: 10,
    x: 238,
    y: 270,
    placed: true,
    source: "generated",
  },
];

const createDemoPlanResponse = (): PlanResponse => ({
  success: true,
  message: "Demo workspace loaded for UI QA.",
  assumptions: [
    {
      field_name: "demo_mode",
      assumed_value: "UI-only seeded project",
      reason: "Allows dashboard and canvas review without authenticating.",
    },
  ],
  issues: [
    {
      severity: "warning",
      code: "DEMO_WATER_CLEARANCE",
      message: "Water line W-12 conflicts with proposed building clearance envelope.",
    },
    {
      severity: "warning",
      code: "DEMO_ROAD_GRADE",
      message: "Roadway R-03 exceeds target max grade in one localized segment.",
    },
  ],
  final_plan: {
    actions: [
      { label: "Multifamily Building A", layer: "BUILDING", task: "rectangle", origin: [120, 95], width: 110, height: 58, meta: { preview_role: "final" } } as Record<string, unknown>,
      { label: "Multifamily Building B", layer: "BUILDING", task: "rectangle", origin: [330, 82], width: 110, height: 58, meta: { preview_role: "final" } } as Record<string, unknown>,
      { label: "Retail Building", layer: "BUILDING", task: "rectangle", origin: [96, 350], width: 70, height: 45, meta: { preview_role: "final" } } as Record<string, unknown>,
      { label: "Residential Parking", layer: "PARKING", task: "rectangle", origin: [255, 190], width: 210, height: 104, meta: { preview_role: "final", system: "parking" } } as Record<string, unknown>,
      { label: "Detention Basin A", layer: "POND", task: "rectangle", origin: [540, 380], width: 150, height: 86, meta: { preview_role: "final", system: "drainage" } } as Record<string, unknown>,
    ] as unknown as NonNullable<NonNullable<PlanResponse["final_plan"]>["actions"]>,
    meta: {
      engineering_status: { success: true, status: "demo_ready", trust_score: 82 },
      manager_export: {
        metrics: {
          storm_pipe_length_ft: 1240,
          pipe_capacity_total_cfs: 18.7,
          earthwork_net_cf: -8640,
        },
      },
      quantities: {
        totals: {
          lot_area_sf: 395200,
          building_area_sf: 17590,
          parking_area_sf: 36990,
          road_length_ft: 890,
          pipe_length_ft: 1240,
          utility_length_ft: 1510,
          sanitary_length_ft: 1080,
          estimated_impervious_area_sf: 112450,
          estimated_parking_stalls: 116,
          pond_count: 1,
          inlet_count: 5,
        },
      },
      storm_pipes: {
        total_system_flow_cfs: 18.7,
        total_system_capacity_cfs: 25.2,
        segments: [
          { length_ft: 320, slope_pct: 0.62 },
          { length_ft: 460, slope_pct: 0.48 },
          { length_ft: 460, slope_pct: 0.52 },
        ],
      },
      drainage: {
        basins: [{ area_sf: 12900, footprint_area_sf: 12900 }],
        low_points: [{ x: 618, y: 428, z: 641.2 }],
        surface_guidance: { downhill_vector: { dx: 0.45, dy: -0.7 } },
      },
      grading: {
        grading_source_quality: "demo_surface",
        grading_source_detail: "Seeded northwest-to-southeast slope for UI QA.",
        existing_surface: {
          range_z: 6.8,
          high_points: [{ x: 60, y: 60, z: 648.0 }],
          low_points: [{ x: 690, y: 460, z: 641.2 }],
          terrain_profile: {
            source_quality: "demo_surface",
            source_detail: "Synthetic surface for visual QA only.",
            terrain_stats: { sample_count: 144, missing_count: 0 },
            downhill_dx: 0.45,
            downhill_dy: -0.7,
          },
        },
        earthwork: { net_cf: -8640 },
      },
      truth_audit: { success: true },
    },
  },
});

import {
  defaultAssumptions,
  toReadableLabel,
  toArray,
  parsePositiveNumber,
  readMetricValue,
  formatMetric,
  summarizePlanResponse,
} from "./utils/formatting";

import {
  createChatMessage,
  createWelcomeMessage,
  extractDesignMemory,
  getChatThreadStorageKey,
} from "./utils/chat";

import { uploadedImageSrc } from "./utils/auth";

import AppHeader from "./components/AppHeader";
import AuthScreen from "./components/AuthScreen";
import ChatPanel from "./components/ChatPanel";
import PreviewPanel from "./components/PreviewPanel";
import useChatPersistence from "./hooks/useChatPersistence";
import usePreviewReview from "./hooks/usePreviewReview";
import useJobPolling from "./hooks/useJobPolling";
import useAuthState from "./hooks/useAuthState";
import useProjectsState from "./hooks/useProjectsState";
import useJobsState from "./hooks/useJobsState";

function formatTimestamp(value?: number): string {
  if (!value) return "Unknown time";
  try {
    return new Date(value * 1000).toLocaleString();
  } catch {
    return "Unknown time";
  }
}

function isLikelyStaleJob(job: JobSummary | null, nowMs: number): boolean {
  if (!job?.updated_at) return false;
  const status = String(job.status || "").toLowerCase();
  if (!["queued", "running", "cancelling"].includes(status)) {
    return false;
  }
  const updatedAtMs = Number(job.updated_at) * 1000;
  if (!Number.isFinite(updatedAtMs) || updatedAtMs <= 0) {
    return false;
  }
  const staleThresholdMs = status === "queued" ? 90_000 : 60_000;
  return nowMs - updatedAtMs > staleThresholdMs;
}

type ApprovalState = "idle" | "approving" | "starting";

function buildThinkingState({
  busy,
  activePlanTool,
  activeJobStatus,
  activeJobStage,
  activeJobDetail,
  activeJobProgress,
  activeJobUpdatedAt,
  activeJobQueuePosition,
  activeJobQueuedCount,
  activeJobRunningCount,
  staleJob,
  statusMessage,
}: {
  busy: boolean;
  activePlanTool: PlanToolMode;
  activeJobStatus?: string;
  activeJobStage?: string;
  activeJobDetail?: string;
  activeJobProgress?: number;
  activeJobUpdatedAt?: number;
  activeJobQueuePosition?: number | null;
  activeJobQueuedCount?: number;
  activeJobRunningCount?: number;
  staleJob?: boolean;
  statusMessage: string;
}) {
  const normalizedJobStatus = String(activeJobStatus || "").trim().toLowerCase();
  const normalizedStatus = statusMessage.toLowerCase();
  const stageLabel = String(activeJobStage || "").trim();
  const stageDetail = String(activeJobDetail || "").trim();
  const numericProgress =
    typeof activeJobProgress === "number" && Number.isFinite(activeJobProgress)
      ? Math.max(0, Math.min(100, Math.round(activeJobProgress)))
      : null;
  const lastUpdateText =
    activeJobUpdatedAt && Number.isFinite(activeJobUpdatedAt)
      ? `Last backend update: ${formatTimestamp(activeJobUpdatedAt)}.`
      : "";
  const queuePosition =
    typeof activeJobQueuePosition === "number" && Number.isFinite(activeJobQueuePosition)
      ? Math.max(1, Math.round(activeJobQueuePosition))
      : null;
  const queuedCount =
    typeof activeJobQueuedCount === "number" && Number.isFinite(activeJobQueuedCount)
      ? Math.max(0, Math.round(activeJobQueuedCount))
      : 0;
  const runningCount =
    typeof activeJobRunningCount === "number" && Number.isFinite(activeJobRunningCount)
      ? Math.max(0, Math.round(activeJobRunningCount))
      : 0;
  const queueDetail = queuePosition
    ? `Civora queued the run. Queue position: ${queuePosition}${queuedCount > 0 ? ` of ${queuedCount}` : ""}. ${runningCount > 0 ? `${runningCount} worker${runningCount === 1 ? "" : "s"} active.` : ""}`.trim()
    : "Civora queued the run and is waiting for a worker to pick it up.";

  if (normalizedJobStatus && staleJob) {
    return {
      label: normalizedJobStatus === "queued" ? "Queue Delayed" : "Check Run Status",
      detail:
        stageDetail ||
        `Civora has not received a fresh backend update for this ${normalizedJobStatus} job recently. ${lastUpdateText}`.trim(),
      progress:
        numericProgress ??
        (normalizedJobStatus === "queued" ? 18 : normalizedJobStatus === "cancelling" ? 68 : 72),
    };
  }

  if (normalizedJobStatus && stageLabel) {
    return {
      label: stageLabel,
      detail:
        stageDetail ||
        (normalizedJobStatus === "queued"
          ? queueDetail
          : "Civora is processing the design in the background now."),
      progress: numericProgress ?? (normalizedJobStatus === "queued" ? 12 : 48),
    };
  }

  if (normalizedJobStatus === "queued") {
    return {
      label: "Queued",
      detail: queueDetail,
      progress: 18,
    };
  }
  if (normalizedJobStatus === "awaiting_approval") {
    return {
      label: stageLabel || "Awaiting Approval",
      detail:
        stageDetail ||
        "Civora saved the current phase result and is waiting for your approval to continue.",
      progress: numericProgress ?? 60,
    };
  }
  if (normalizedJobStatus === "running") {
    return {
      label: "Running",
      detail: "Civora is processing the design in the background now.",
      progress: 68,
    };
  }
  if (normalizedJobStatus === "cancelling") {
    return {
      label: "Cancelling",
      detail:
        stageDetail ||
        "Civora is stopping the background run and cleaning up the active job.",
      progress: numericProgress ?? 68,
    };
  }
  if (busy && activePlanTool === "fix") {
    return {
      label: "Fixing",
      detail: "Applying a focused fix pass to the active design.",
      progress: 62,
    };
  }
  if (busy && activePlanTool === "improve") {
    return {
      label: "Improving",
      detail: "Improving the current design while preserving the main intent.",
      progress: 62,
    };
  }
  if (busy && normalizedStatus.includes("reviewing your request")) {
    return {
      label: "Reading Request",
      detail: "Reviewing your prompt and preparing the run.",
      progress: 22,
    };
  }
  if (busy && normalizedStatus.includes("starting the engineering run")) {
    return {
      label: "Engineering Run",
      detail: "Starting the core design pipeline and waiting for the first engineering result.",
      progress: 34,
    };
  }
  return {
    label: "Thinking",
    detail:
      statusMessage ||
      "Civora is building the design, checking engineering constraints, and preparing the next result.",
    progress: 42,
  };
}

type PerformanceAIDashboardProps = {
  forceDemoWorkspace?: boolean;
};

function PerformanceAIDashboardView({
  forceDemoWorkspace = false,
}: PerformanceAIDashboardProps = {}) {
  const pathname = usePathname();
  const routeDemoWorkspaceEnabled = pathname === "/demo/workspace";
  const [projectType, setProjectType] = useState("");
  const [units, setUnits] = useState("ft");
  const [prompt, setPrompt] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [
    createWelcomeMessage(),
  ]);
  const [demoWorkspaceEnabled, setDemoWorkspaceEnabled] = useState(false);
  const [clientMounted, setClientMounted] = useState(false);
  const effectiveDemoWorkspaceEnabled = forceDemoWorkspace || routeDemoWorkspaceEnabled || demoWorkspaceEnabled;
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [, setChatCollapsed] = useState(false);
  const [activeSidePanel, setActiveSidePanel] = useState<SidePanelKey | null>(null);
  const [renderedSidePanel, setRenderedSidePanel] = useState<SidePanelKey | null>(null);
  const [sidePanelVisible, setSidePanelVisible] = useState(false);
  const [sidebarRendered, setSidebarRendered] = useState(true);
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [bottomPanelContentRendered, setBottomPanelContentRendered] = useState(true);
  const [bottomPanelContentVisible, setBottomPanelContentVisible] = useState(true);
  const [activeWorkspaceMode, setActiveWorkspaceMode] = useState<WorkspaceMode>("setup");
  const [imageName, setImageName] = useState("");
  const [siteName, setSiteName] = useState("");
  const [fileName, setFileName] = useState("");
  const [siteNameAuto, setSiteNameAuto] = useState(false);
  const [fileNameAuto, setFileNameAuto] = useState(false);
  const [lotWidth, setLotWidth] = useState("");
  const [lotHeight, setLotHeight] = useState("");
  const [buildingWidth, setBuildingWidth] = useState("");
  const [buildingDepth, setBuildingDepth] = useState("");
  const [buildingCount, setBuildingCount] = useState("");
  const [setback, setSetback] = useState("");
  const [parkingCount, setParkingCount] = useState("");
  const [parkingStallWidth, setParkingStallWidth] = useState("9");
  const [parkingStallDepth, setParkingStallDepth] = useState("18");
  const [parkingAisleWidth, setParkingAisleWidth] = useState("24");
  const [parkingAdaAisleWidth, setParkingAdaAisleWidth] = useState("8");
  const [parkingAdaCount, setParkingAdaCount] = useState("0");
  const [parkingCompactCount, setParkingCompactCount] = useState("0");
  const [parkingCompactWidth, setParkingCompactWidth] = useState("8");
  const [parkingAngle, setParkingAngle] = useState<"90" | "60" | "45">("90");
  const [parkingLoading, setParkingLoading] = useState<"single" | "double">("double");
  const [minSlopePct, setMinSlopePct] = useState("");
  const [pipeMinSlopePct, setPipeMinSlopePct] = useState("");
  const [maxParkingSlopePct, setMaxParkingSlopePct] = useState("");
  const [maxRoadGradePct, setMaxRoadGradePct] = useState("");
  const [maxAdaCrossSlopePct, setMaxAdaCrossSlopePct] = useState("");
  const [roads, setRoads] = useState(true);
  const [grading, setGrading] = useState(true);
  const [drainage, setDrainage] = useState(true);
  const [assistedEnabled, setAssistedEnabled] = useState(false);
  const [drainageForcedInlets, setDrainageForcedInlets] = useState<
    Array<{ x: number; y: number; name?: string }>
  >([]);
  const [drainageConnectOrphans, setDrainageConnectOrphans] = useState(false);
  const [drainageAllowSlopeAdjust, setDrainageAllowSlopeAdjust] = useState(false);
  const [drainageMaxSlopeAdjust, setDrainageMaxSlopeAdjust] = useState(0.001);
  const [utilities, setUtilities] = useState(true);
  const [buildingPlacements, setBuildingPlacements] = useState<BuildingPlacement[]>([]);
  const [placementModeEnabled, setPlacementModeEnabled] = useState(false);
  const [activePlacementId, setActivePlacementId] = useState<string | null>(null);
  const [objectPrompt, setObjectPrompt] = useState("");
  const [systemStatuses, setSystemStatuses] = useState(DEFAULT_SYSTEM_STATUS);
  const [reactiveValidation, setReactiveValidation] = useState<ReactiveValidationState>(EMPTY_REACTIVE_VALIDATION);

  const [assumptions, setAssumptions] =
    useState<Assumption[]>(defaultAssumptions);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [backendResult, setBackendResult] = useState<PlanResponse | null>(null);
  const [uploadedImagePreviewUrl, setUploadedImagePreviewUrl] = useState("");
  const [uploadedImageApiUrl, setUploadedImageApiUrl] = useState("");
  const [surveyFileName, setSurveyFileName] = useState("");
  const [surveySlopeEstimate, setSurveySlopeEstimate] = useState<SurveySlopeResponse | null>(null);
  const [, setSurveyPoints] = useState<number[][]>([]);
  const [, setSurveyDiagnostics] = useState<{
    fileType?: string;
    parseSuccess?: boolean;
    pointCount?: number;
    contourCount?: number;
    recognizedColumns?: { x?: string; y?: string; z?: string };
    invalidRows?: number;
    bounds?: { min_x?: number; min_y?: number; max_x?: number; max_y?: number };
    elevationRange?: { min?: number; max?: number };
    warnings?: string[];
  } | null>(null);
  const [surveyPreviewPoints, setSurveyPreviewPoints] = useState<Array<{ x: number; y: number; z?: number }>>([]);
  const [useSurveyForGrading, setUseSurveyForGrading] = useState(true);
  const [detectedPlacements, setDetectedPlacements] = useState<BuildingPlacement[]>([]);
  const [detectionScaleFeet, setDetectionScaleFeet] = useState("");
  const [detectionScalePixels, setDetectionScalePixels] = useState("");
  const [detectionScaleFtPerPx, setDetectionScaleFtPerPx] = useState<number | null>(null);
  const [, setDetectionScaleSource] = useState<"mapbox" | "manual" | "approximate">("approximate");
  const [siteScaleLocked, setSiteScaleLocked] = useState(false);
  const [drainageSourceOverride, setDrainageSourceOverride] = useState<"civora" | "user">(
    "civora",
  );
  const [siteRotationDeg, setSiteRotationDeg] = useState(0);
  const [siteRotationInput, setSiteRotationInput] = useState("0");
  const [showSiteBounds, setShowSiteBounds] = useState(false);
  const [fitToSiteRequest, setFitToSiteRequest] = useState(0);
  const [siteDrawRequest, setSiteDrawRequest] = useState(0);
  const [mapCenterRequest, setMapCenterRequest] = useState(0);
  const [alignToRoadRequest, setAlignToRoadRequest] = useState(0);
  const debugPreview = useMemo(() => {
    if (!clientMounted || typeof window === "undefined") return false;
    return window.location.search.includes("debugPreview=1");
  }, [clientMounted]);
  const rotationSaveTimeoutRef = useRef<number | null>(null);
  const scaleSaveTimeoutRef = useRef<number | null>(null);
  const [focusDetectedId, setFocusDetectedId] = useState<string | null>(null);
  const [focusObjectId, setFocusObjectId] = useState<string | null>(null);
  const [analysisPaths, setAnalysisPaths] = useState<
    Array<{
      id: string;
      buildingId: string;
      accessId: string;
      from: { x: number; y: number };
      to: { x: number; y: number };
      label: string;
      points?: Array<{ x: number; y: number }>;
    }>
  >([]);
  const [analysisIssues, setAnalysisIssues] = useState<
    Array<{
      id: string;
      buildingId: string;
      accessId: string;
      distanceFt: number;
      thresholdFt: number;
      message: string;
      pathId: string;
      issueType: "distance" | "no_access" | "no_buildings" | "no_access_objects";
    }>
  >([]);
  const [analysisSelectedIssueId, setAnalysisSelectedIssueId] = useState<string | null>(null);
  const [analysisFocusLocked, setAnalysisFocusLocked] = useState(false);
  const [analysisEmptyReason, setAnalysisEmptyReason] = useState<string | null>(null);
  const [externalRectUndo, setExternalRectUndo] = useState<{
    id: string;
    snapshot: BuildingPlacement;
    action: "update" | "delete" | "add";
    ts: number;
  } | null>(null);
  const [detectionConfidenceFilter, setDetectionConfidenceFilter] = useState<"high" | "medium" | "all">("all");
  const [mapSnapshotPath, setMapSnapshotPath] = useState("");
  const [mapAnalysis, setMapAnalysis] = useState<MapAnalysis | null>(null);
  const [siteAddress, setSiteAddress] = useState("");
  const [siteSelectionMode, setSiteSelectionMode] = useState(false);
  const [viewportFootprint, setViewportFootprint] = useState<{
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
  } | null>(null);
  const [viewportCenter, setViewportCenter] = useState<{ lat: number; lng: number } | null>(null);
  const handleViewportFootprint = useCallback((value: NonNullable<typeof viewportFootprint>) => {
    setViewportFootprint((prev) => {
      if (
        prev &&
        Math.abs(prev.widthFt - value.widthFt) < 0.01 &&
        Math.abs(prev.heightFt - value.heightFt) < 0.01 &&
        Math.abs((prev.bounds?.north ?? 0) - (value.bounds?.north ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.south ?? 0) - (value.bounds?.south ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.east ?? 0) - (value.bounds?.east ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.west ?? 0) - (value.bounds?.west ?? 0)) < 1e-7
      ) {
        return prev;
      }
      return value;
    });
  }, []);
  const handleViewportCenter = useCallback((value: { lat: number; lng: number }) => {
    setViewportCenter((prev) => {
      if (prev && Math.abs(prev.lat - value.lat) < 1e-7 && Math.abs(prev.lng - value.lng) < 1e-7) {
        return prev;
      }
      return value;
    });
  }, []);
  const [detectionChoices, setDetectionChoices] = useState({
    roads: true,
    buildings: true,
    parking: true,
    grading: false,
  });
  const [addressSuggestions, setAddressSuggestions] = useState<AddressSuggestion[]>([]);
  const [selectedAddressSuggestion, setSelectedAddressSuggestion] = useState<AddressSuggestion | null>(null);
  const addressSuggestTimeoutRef = useRef<number | null>(null);
  const [imageUploadState, setImageUploadState] = useState<"idle" | "uploading" | "uploaded" | "detecting" | "failed">("idle");
  const [imageUploadNote, setImageUploadNote] = useState<string | null>(null);
  const [pendingClarification, setPendingClarification] = useState<{
    action: string;
    payload?: Record<string, unknown>;
    question: string;
  } | null>(null);
  const [planPreviewUrl, setPlanPreviewUrl] = useState("");
  const [planPreviewProjectId, setPlanPreviewProjectId] = useState<string | null>(null);
  const [planPreviewSummary, setPlanPreviewSummary] =
    useState<PreviewResponse["summary"] | null>(null);
  const [planPreviewAnnotations, setPlanPreviewAnnotations] =
    useState<PreviewResponse["preview_annotations"] | null>(null);
  const [previewMode, setPreviewMode] = useState<"2d" | "3d">("2d");
  const [previewInteraction, setPreviewInteraction] = useState<"static" | "edit">("static");
  const [previewQuality, setPreviewQuality] = useState<"standard" | "high">("standard");
  const [previewLabelDensity, setPreviewLabelDensity] = useState<"low" | "standard" | "high">("standard");
  const [previewLabelDensityTouched, setPreviewLabelDensityTouched] = useState(false);
  const [previewHeightPx, setPreviewHeightPx] = useState(900);
  const [objectOutlineColor, setObjectOutlineColor] = useState("#1f2937");
  const [previewRefreshing, setPreviewRefreshing] = useState(false);
  const [previewRefreshNote, setPreviewRefreshNote] = useState<string | null>(null);
  const [approvalInFlight, setApprovalInFlight] = useState(false);
  const [approvalPhaseLabel, setApprovalPhaseLabel] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approvalPendingJobId, setApprovalPendingJobId] = useState<string | null>(null);
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [showCalculations, setShowCalculations] = useState(false);
  const [bottomPanelCollapsed, setBottomPanelCollapsed] = useState(false);
  const [activeBottomPanelTab, setActiveBottomPanelTab] = useState<BottomPanelTab>("model_review");
  const [previewLayers, setPreviewLayers] = useState({
    buildings: true,
    roads: true,
    grading: true,
    drainage: true,
    utilities: true,
    structures: true,
    lots: false,
  });
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const [previewFullscreenOpen, setPreviewFullscreenOpen] = useState(false);
  const [, setActiveWorkflowStep] = useState<CivoraWorkflowStep>("Concept");
  const [projectId, setProjectId] = useState("");
  const [currentProject, setCurrentProject] = useState<ProjectRecord | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activePlanTool, setActivePlanTool] = useState<PlanToolMode>("run");
  const [jobClockMs, setJobClockMs] = useState(() => Date.now());
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const siteAddressInputRef = useRef<HTMLInputElement | null>(null);
  const mapSnapshotInputRef = useRef<HTMLInputElement | null>(null);
  const surveyInputRef = useRef<HTMLInputElement | null>(null);
  const runSubmissionRef = useRef(false);
  const directRunAbortRef = useRef<AbortController | null>(null);
  const draftProjectPromiseRef = useRef<Promise<ProjectRecord | null> | null>(null);
  const ensureProjectDraftRef = useRef<() => Promise<string | null>>(() => Promise.resolve(null));
  const saveProjectRef = useRef<
    (options?: {
      silent?: boolean;
      projectIdOverride?: string | null;
      nameOverride?: string;
      fileNameOverride?: string;
      projectInputOverride?: ProjectInput;
      latestResultOverride?: PlanResponse;
      autoNamedOverride?: boolean;
      autoFileNamedOverride?: boolean;
    }) => Promise<ProjectRecord | null>
  >(() => Promise.resolve(null));
  const resolvedProjectIdRef = useRef("");
  const projectLoadRequestRef = useRef(0);
  const projectResultLoadRequestRef = useRef(0);
  const activeJobProjectSyncRef = useRef("");
  const lastJobStatusRef = useRef<Record<string, string>>({});
  const lastJobPhaseSignatureRef = useRef<Record<string, string>>({});
  const lastStaleJobWarningRef = useRef<Record<string, boolean>>({});
  const previewRefreshIntentRef = useRef<{ reason: string; track?: boolean } | null>(null);
  const lastProjectResultRefreshRef = useRef<Record<string, number>>({});
  const lastJobPartialResultRefreshRef = useRef<Record<string, number>>({});
  const handleGenerateSystemRef = useRef<((target: SystemGenerationTarget) => Promise<void>) | null>(null);
  const chatMessagesRef = useRef<ChatMessage[]>([createWelcomeMessage()]);
  const suppressProjectAutoLoadRef = useRef(false);
  const chatAutosaveTimeoutRef = useRef<number | null>(null);
  const autosaveSuspendRef = useRef(false);
  const demoWorkspaceSeededRef = useRef(false);
  const currentPhaseLabelRef = useRef<string>("");
  const previewRecoveryKeyRef = useRef("");
  const lastSiteInputProjectRef = useRef("");
  const controlAutosaveTimeoutRef = useRef<number | null>(null);
  const lastAppliedSiteRef = useRef<{ w: number; h: number; lat?: number; lng?: number } | null>(null);
  const lastViewportSyncRef = useRef<{ w: number; h: number } | null>(null);
  const applyingSiteRef = useRef(false);
  const sidePanelCloseTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    let timeout: number | undefined;
    let frame: number | undefined;

    if (activeSidePanel) {
      setRenderedSidePanel(activeSidePanel);
      frame = window.requestAnimationFrame(() => setSidePanelVisible(true));
    } else {
      setSidePanelVisible(false);
      timeout = window.setTimeout(() => setRenderedSidePanel(null), 180);
    }

    return () => {
      if (frame !== undefined) window.cancelAnimationFrame(frame);
      if (timeout !== undefined) window.clearTimeout(timeout);
    };
  }, [activeSidePanel]);

  useEffect(() => {
    let timeout: number | undefined;
    let frame: number | undefined;

    if (leftSidebarOpen) {
      setSidebarRendered(true);
      frame = window.requestAnimationFrame(() => setSidebarVisible(true));
    } else {
      setSidebarVisible(false);
      timeout = window.setTimeout(() => setSidebarRendered(false), 180);
    }

    return () => {
      if (frame !== undefined) window.cancelAnimationFrame(frame);
      if (timeout !== undefined) window.clearTimeout(timeout);
    };
  }, [leftSidebarOpen]);

  useEffect(() => {
    let timeout: number | undefined;
    let frame: number | undefined;

    if (!bottomPanelCollapsed) {
      setBottomPanelContentRendered(true);
      frame = window.requestAnimationFrame(() => setBottomPanelContentVisible(true));
    } else {
      setBottomPanelContentVisible(false);
      timeout = window.setTimeout(() => setBottomPanelContentRendered(false), 180);
    }

    return () => {
      if (frame !== undefined) window.cancelAnimationFrame(frame);
      if (timeout !== undefined) window.clearTimeout(timeout);
    };
  }, [bottomPanelCollapsed]);

  const {
    projects,
    setProjects,
    refreshProjects,
    upsertProjectSummary,
    removeProjectSummary,
  } = useProjectsState();

  const {
    jobs,
    setJobs,
    refreshJobs,
  } = useJobsState({ activeJobId });

  const {
    token,
    user,
    authMode,
    authStatus,
    authName,
    authEmail,
    authPassword,
    showPassword,
    authError,
    authLoading,
    authStatusError,
    setAuthMode,
    setAuthName,
    setAuthEmail,
    setAuthPassword,
    setAuthError,
    setShowPassword,
    handleAuth,
    handleLogout,
  } = useAuthState({
    onRefreshProjects: refreshProjects,
    onRefreshJobs: refreshJobs,
    onStatusMessage: setStatusMessage,
    onLogoutCleanup: () => {
      setProjects([]);
      setJobs([]);
      setCurrentProject(null);
      setProjectId("");
    },
  });
  const effectiveUser: UserRecord | null =
    user ??
    (effectiveDemoWorkspaceEnabled
      ? {
          user_id: "demo-user",
          name: "Demo Reviewer",
          email: "demo@civora.local",
        }
      : null);

  useEffect(() => {
    setClientMounted(true);
  }, []);

  useEffect(() => {
    setDemoWorkspaceEnabled(forceDemoWorkspace || isDemoWorkspaceQuery());
  }, [forceDemoWorkspace, routeDemoWorkspaceEnabled]);

  const disciplineToggles: DisciplineToggle[] = [
    {
      label: "Roads",
      checked: roads,
      setter: setRoads,
      desc: "Corridor / access layout",
    },
    {
      label: "Grading",
      checked: grading,
      setter: setGrading,
      desc: "Pads, slopes, tie-ins",
    },
    {
      label: "Drainage",
      checked: drainage,
      setter: setDrainage,
      desc: "Inlets, ponds, routing",
    },
    {
      label: "Utilities",
      checked: utilities,
      setter: setUtilities,
      desc: "Water, sanitary, utility",
    },
  ];

  const buildManualFields = useCallback(({
    nextSiteName,
    nextFileName,
    nextUnits,
    nextProjectType,
    nextLotWidth,
    nextLotHeight,
    nextSetback,
    nextBuildingWidth,
    nextBuildingDepth,
    nextBuildingCount,
    nextParkingCount,
    nextMinSlopePct,
    nextPipeMinSlopePct,
    nextMaxParkingSlopePct,
    nextMaxRoadGradePct,
    nextMaxAdaCrossSlopePct,
    nextRoads,
    nextGrading,
    nextDrainage,
    nextUtilities,
    placementsOverride,
  }: {
    nextSiteName: string;
    nextFileName: string;
    nextUnits: string;
    nextProjectType: string;
    nextLotWidth: string | number | null | undefined;
    nextLotHeight: string | number | null | undefined;
    nextSetback: string | number | null | undefined;
    nextBuildingWidth: string | number | null | undefined;
    nextBuildingDepth: string | number | null | undefined;
    nextBuildingCount: string | number | null | undefined;
    nextParkingCount: string | number | null | undefined;
    nextMinSlopePct: string | number | null | undefined;
    nextPipeMinSlopePct: string | number | null | undefined;
    nextMaxParkingSlopePct: string | number | null | undefined;
    nextMaxRoadGradePct: string | number | null | undefined;
    nextMaxAdaCrossSlopePct: string | number | null | undefined;
    nextRoads: boolean;
    nextGrading: boolean;
    nextDrainage: boolean;
    nextUtilities: boolean;
    placementsOverride?: BuildingPlacement[];
  }) => {
    const lotWidthValue = parsePositiveNumber(nextLotWidth);
    const lotHeightValue = parsePositiveNumber(nextLotHeight);
    const setbackValue = parsePositiveNumber(nextSetback);
    const buildingWidthValue = parsePositiveNumber(nextBuildingWidth);
    const buildingDepthValue = parsePositiveNumber(nextBuildingDepth);
    const buildingCountValue = parsePositiveNumber(nextBuildingCount);
    const parkingCountValue = parsePositiveNumber(nextParkingCount);
    const minSlopeValue = parsePositiveNumber(nextMinSlopePct);
    const pipeMinSlopeValue = parsePositiveNumber(nextPipeMinSlopePct);
    const maxParkingSlopeValue = parsePositiveNumber(nextMaxParkingSlopePct);
    const maxRoadGradeValue = parsePositiveNumber(nextMaxRoadGradePct);
    const maxAdaSlopeValue = parsePositiveNumber(nextMaxAdaCrossSlopePct);

    const manualFields: ManualFields = {
      project_name: nextSiteName,
      file_name: nextFileName,
      units: nextUnits,
      project_type: nextProjectType,
      disciplines: [
        nextRoads ? "corridor" : null,
        nextGrading ? "grading" : null,
        nextDrainage ? "drainage" : null,
        nextUtilities ? "utility" : null,
      ].filter((item): item is string => Boolean(item)),
    };

    if (lotWidthValue !== null && lotHeightValue !== null) {
      manualFields.lot = {
        x: 0,
        y: 0,
        w: lotWidthValue,
        h: lotHeightValue,
      };
    }

    if (setbackValue !== null) {
      manualFields.setback = setbackValue;
    }

    if (buildingWidthValue !== null) {
      manualFields.building_width = buildingWidthValue;
    }

    if (buildingDepthValue !== null) {
      manualFields.building_depth = buildingDepthValue;
    }

    const placementOverrides = (placementsOverride ?? buildingPlacements)
      .filter((placement) => placement.placed && Number.isFinite(placement.x) && Number.isFinite(placement.y))
      .map((placement) => ({
        id: placement.id,
        name: placement.label,
        label: placement.label,
        type: placement.type ?? "building",
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        height_ft: placement.h,
        rotation: placement.rotation,
        use: placement.use,
        stall_count: placement.stallCount,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        geometry_type: placement.geometryType,
        geometry: placement.geometry,
        meta: placement.meta,
        systemDependencies: placement.systemDependencies,
      }));
    const canonicalGeometryHandoffs = placementOverrides
      .map((placement) =>
        placement.type === "custom"
          ? buildCanonicalGeometryHandoffV1(
              {
                id: placement.id,
                label: placement.label,
                type: "custom",
                x: placement.x,
                y: placement.y,
                w: placement.w,
                d: placement.d,
                h: placement.height_ft,
                rotation: placement.rotation,
                locked: placement.locked,
                placed: true,
                source: "manual_drawn",
                generated: false,
                geometryType: isCustomGeometryMode(placement.geometry_type)
                  ? placement.geometry_type
                  : undefined,
                geometry: placement.geometry,
                meta: placement.meta,
                systemDependencies: placement.systemDependencies,
              },
              nextUnits || "ft",
            )
          : null,
      )
      .filter((handoff): handoff is CanonicalGeometryHandoffV1 => Boolean(handoff));
    const basinOverrides = placementOverrides.filter((placement) => placement.type === "basin");
    const entranceOverrides = placementOverrides.filter((placement) => placement.type === "entrance");
    const parkingOverrides = placementOverrides.filter((placement) => placement.type === "parking");
    const buildingTypes = new Set<SiteObjectType>([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "amenity",
      "open_space",
    ]);
    const buildingOverrides = placementOverrides.filter((placement) =>
      buildingTypes.has(placement.type as SiteObjectType),
    );

    if (buildingOverrides.length) {
      manualFields.buildings = buildingOverrides.map((placement) => ({
        ...placement,
        height_ft: placement.height_ft,
      }));
    }
    if (basinOverrides.length) {
      manualFields.ponds = basinOverrides.map((placement) => ({
        id: placement.id,
        name: placement.label,
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        rotation: placement.rotation,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        systemDependencies: placement.systemDependencies,
      }));
    }
    if (entranceOverrides.length) {
      manualFields.access_points = entranceOverrides.map((placement) => ({
        id: placement.id,
        name: placement.label,
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        rotation: placement.rotation,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        systemDependencies: placement.systemDependencies,
      }));
    }

    if (!buildingOverrides.length && buildingCountValue !== null) {
      manualFields.buildings = Array.from({ length: Math.max(1, Math.round(buildingCountValue)) }).map(
        (_, idx) => ({
          name: `Building ${idx + 1}`,
          w: buildingWidthValue ?? undefined,
          d: buildingDepthValue ?? undefined,
        }),
      );
    }

    const parkingFromPlacements = parkingOverrides.reduce((sum, placement) => {
      const value =
        typeof placement.stall_count === "number"
          ? placement.stall_count
          : parsePositiveNumber(placement.stall_count);
      return sum + (value ?? 0);
    }, 0);
    const resolvedParkingCount =
      parkingFromPlacements > 0 ? parkingFromPlacements : parkingCountValue;

    if (resolvedParkingCount !== null) {
      manualFields.site_plan = { parking_count: resolvedParkingCount };
    }

    if (placementOverrides.length) {
      manualFields.site_objects = placementOverrides.map((placement) => ({
        id: placement.id,
        name: placement.label,
        label: placement.label,
        type: placement.type,
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        height_ft: placement.height_ft,
        rotation: placement.rotation,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        geometry_type: placement.geometry_type,
        geometry: placement.geometry,
        meta: placement.meta,
        canonical_geometry_handoff_v1:
          placement.type === "custom"
            ? canonicalGeometryHandoffs.find((handoff) => handoff.object_id === placement.id)
            : undefined,
        systemDependencies: placement.systemDependencies,
      }));
    }

    if (canonicalGeometryHandoffs.length) {
      manualFields.canonical_geometry_handoff_v1 = canonicalGeometryHandoffs;
    }

    if (minSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        min_slope_pct: minSlopeValue,
      };
    }

    if (maxParkingSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_parking_slope_pct: maxParkingSlopeValue,
      };
    }

    if (maxRoadGradeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_road_grade_pct: maxRoadGradeValue,
      };
    }

    if (maxAdaSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_ada_cross_slope_pct: maxAdaSlopeValue,
      };
    }

    if (pipeMinSlopeValue !== null) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        min_pipe_slope_pct: pipeMinSlopeValue,
      };
    }
    if (drainageForcedInlets.length) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        forced_inlets: drainageForcedInlets,
      };
    }
    if (drainageConnectOrphans) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        connect_orphans: true,
      };
    }
    if (drainageAllowSlopeAdjust) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        allow_slope_adjustment: true,
        max_slope_adjust: drainageMaxSlopeAdjust,
      };
    }

    return manualFields;
  }, [
    buildingPlacements,
    drainageAllowSlopeAdjust,
    drainageConnectOrphans,
    drainageForcedInlets,
    drainageMaxSlopeAdjust,
  ]);

  const payloadPreview = useMemo(
    () => ({
      project_id: projectId || null,
      full_design_mode: true,
      input_mode: assistedEnabled ? "assisted" : "user",
      strict_mode: false,
      prompt_text: prompt || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
        system_dirty_state: systemStatuses,
        reactive_edit_policy_preference: REACTIVE_EDIT_POLICY_PREFERENCE,
        site_object_id: buildingPlacements.find((item) => item.type === "site")?.id ?? null,
        assisted_enabled: assistedEnabled,
      },
      manual_fields: buildManualFields({
        nextSiteName: siteName,
        nextFileName: fileName,
        nextUnits: units,
        nextProjectType: projectType,
        nextLotWidth: lotWidth,
        nextLotHeight: lotHeight,
        nextSetback: setback,
        nextBuildingWidth: buildingWidth,
        nextBuildingDepth: buildingDepth,
        nextBuildingCount: buildingCount,
        nextParkingCount: parkingCount,
        nextMinSlopePct: minSlopePct,
        nextPipeMinSlopePct: pipeMinSlopePct,
        nextMaxParkingSlopePct: maxParkingSlopePct,
        nextMaxRoadGradePct: maxRoadGradePct,
        nextMaxAdaCrossSlopePct: maxAdaCrossSlopePct,
        nextRoads: roads,
        nextGrading: grading,
        nextDrainage: drainage,
        nextUtilities: utilities,
      }),
      allow_ai_fill_for_blanks: assistedEnabled,
    }),
    [
      buildingPlacements,
      projectId,
      prompt,
      imageName,
      siteName,
      fileName,
      units,
      projectType,
      lotWidth,
      lotHeight,
      setback,
      buildingWidth,
      buildingDepth,
      buildingCount,
      parkingCount,
      minSlopePct,
      pipeMinSlopePct,
      maxParkingSlopePct,
      maxRoadGradePct,
      maxAdaCrossSlopePct,
      roads,
      grading,
      drainage,
      utilities,
      systemStatuses,
      assistedEnabled,
      currentProject,
      buildManualFields,
    ],
  );

  const artifactPayload = useMemo(() => {
    if (
      backendResult &&
      typeof backendResult === "object" &&
      Object.keys(backendResult).length
    ) {
      return {
        project_id: projectId || currentProject?.project_id || null,
        result: backendResult,
        filename_stem: fileName || siteName,
      };
    }

    return {
      project_id: projectId || currentProject?.project_id || null,
      filename_stem: fileName || siteName,
    };
  }, [backendResult, currentProject?.project_id, fileName, projectId, siteName]);

  const workflowRuns = useMemo<WorkflowRunSummary[]>(
    () =>
      Array.isArray(currentProject?.metadata?.workflow?.runs)
        ? currentProject?.metadata?.workflow?.runs
        : [],
    [currentProject],
  );

  const selectedRun = useMemo<WorkflowRunSummary | null>(() => {
    if (!workflowRuns.length) return null;
    return (
      workflowRuns.find((run) => run.run_id === selectedRunId) ?? workflowRuns[0]
    );
  }, [workflowRuns, selectedRunId]);
  const workflowReviewDashboard = useMemo<WorkflowReviewDashboard | null>(
    () => currentProject?.metadata?.workflow?.review_dashboard ?? null,
    [currentProject],
  );
  const activeJob = useMemo(
    () => jobs.find((job) => job.job_id === activeJobId) ?? null,
    [jobs, activeJobId],
  );
  const currentProjectActiveJob = useMemo(
    () =>
      jobs.find(
        (job) =>
          Boolean(projectId) &&
          job.project_id === projectId &&
          ["queued", "running", "awaiting_approval", "cancelling"].includes(String(job.status || "").toLowerCase()),
      ) ?? null,
    [jobs, projectId],
  );
  const visibleActiveJob = useMemo(() => {
    if (activeJobId) {
      return activeJob;
    }
    return projectId ? currentProjectActiveJob : activeJob;
  }, [activeJob, activeJobId, currentProjectActiveJob, projectId]);
  const visibleActiveJobStale = useMemo(
    () => isLikelyStaleJob(visibleActiveJob, jobClockMs),
    [visibleActiveJob, jobClockMs],
  );
  const thinkingState = useMemo(
    () =>
      buildThinkingState({
        busy,
        activePlanTool,
        activeJobStatus: visibleActiveJob?.status,
        activeJobStage: visibleActiveJob?.stage,
        activeJobDetail: visibleActiveJob?.stage_detail,
        activeJobProgress: visibleActiveJob?.progress,
        activeJobUpdatedAt: visibleActiveJob?.updated_at,
        activeJobQueuePosition: visibleActiveJob?.queue_position,
        activeJobQueuedCount: visibleActiveJob?.queued_count,
        activeJobRunningCount: visibleActiveJob?.running_count,
        staleJob: visibleActiveJobStale,
        statusMessage,
      }),
    [busy, visibleActiveJob?.status, visibleActiveJob?.stage, visibleActiveJob?.stage_detail, visibleActiveJob?.progress, visibleActiveJob?.updated_at, visibleActiveJob?.queue_position, visibleActiveJob?.queued_count, visibleActiveJob?.running_count, visibleActiveJobStale, activePlanTool, statusMessage],
  );

  const chatSummary = useMemo(() => {
    const last = chatMessages[chatMessages.length - 1];
    if (!last) return "Ask Civora about your site or place objects.";
    const roleLabel = last.role === "user" ? "You" : "Civora";
    const snippet = String(last.content || "").trim().slice(0, 120);
    return snippet ? `${roleLabel}: ${snippet}${snippet.length >= 120 ? "…" : ""}` : "Chat is ready.";
  }, [chatMessages]);
  const approvalStatus = useMemo<{ state: ApprovalState; label: string | null }>(() => {
    if (approvalInFlight) {
      return { state: "approving", label: approvalPhaseLabel };
    }
    if (
      approvalPendingJobId &&
      visibleActiveJob?.job_id === approvalPendingJobId &&
      String(visibleActiveJob?.status || "").toLowerCase() !== "awaiting_approval"
    ) {
      return { state: "starting", label: approvalPhaseLabel };
    }
    return { state: "idle", label: approvalPhaseLabel };
  }, [approvalInFlight, approvalPendingJobId, approvalPhaseLabel, visibleActiveJob?.job_id, visibleActiveJob?.status]);

  useEffect(() => {
    if (!approvalPendingJobId) return;
    if (visibleActiveJob?.job_id !== approvalPendingJobId) {
      setApprovalInFlight(false);
      setApprovalPendingJobId(null);
      setApprovalPhaseLabel(null);
      return;
    }
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (["awaiting_approval", "completed", "failed", "cancelled"].includes(status)) {
      setApprovalInFlight(false);
      setApprovalPendingJobId(null);
      setApprovalPhaseLabel(null);
    }
  }, [approvalPendingJobId, visibleActiveJob?.job_id, visibleActiveJob?.status]);

  useEffect(() => {
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") {
      setApprovalError(null);
    }
  }, [visibleActiveJob?.status]);
  const currentPlanMeta = useMemo<PlanMeta>(() => backendResult?.final_plan?.meta ?? {}, [backendResult]);
  const reactiveChangedSystems = useMemo<EngineeringSystemKey[]>(
    () =>
      (Object.entries(systemStatuses) as Array<[EngineeringSystemKey, SystemStatus]>)
        .filter(([, status]) => status === "stale")
        .map(([system]) => system),
    [systemStatuses],
  );
  const reactiveChangedTargets = useMemo(
    () =>
      Array.from(
        new Set(
          reactiveChangedSystems.flatMap((system) => REACTIVE_SYSTEM_STAGE_MAP[system] ?? []),
        ),
      ),
    [reactiveChangedSystems],
  );
  const reactiveRerunSummary = useMemo(() => {
    const partial = currentPlanMeta.reactive_partial_rerun ?? {};
    const report = currentPlanMeta.reactive_update_report ?? {};
    const telemetry = partial.telemetry ?? report.partial_rerun_telemetry ?? {};
    const rerunStages = partial.rerun_stages ?? telemetry.rerun_stages ?? report.impacted_stages ?? [];
    const skippedStages = partial.skipped_stages ?? telemetry.skipped_stages ?? [];
    return {
      enabled: Boolean(partial.enabled || report.partial_rerun_executed),
      checkpointRestored: Boolean(partial.checkpoint_restored),
      executionMode: report.execution_mode ?? "",
      rerunStages,
      skippedStages,
      elapsedMs: telemetry.elapsed_ms,
      withinQuickThreshold: telemetry.within_quick_threshold,
    };
  }, [currentPlanMeta]);

  useEffect(() => {
    if (!reactiveChangedSystems.length || !backendResult?.final_plan) {
      setReactiveValidation(EMPTY_REACTIVE_VALIDATION);
      return;
    }
    setReactiveValidation((prev) => ({
      ...prev,
      status: "pending",
      changedSystems: reactiveChangedSystems,
      changedTargets: reactiveChangedTargets,
      requiresConfirmation: reactiveChangedTargets.length > 4,
      message: "Checking impacted engineering systems...",
    }));
    const timeout = window.setTimeout(() => {
      const requiresConfirmation = reactiveChangedTargets.length > 4;
      setReactiveValidation({
        status: "ready",
        changedSystems: reactiveChangedSystems,
        changedTargets: reactiveChangedTargets,
        requiresConfirmation,
        message: requiresConfirmation
          ? `This edit affects ${reactiveChangedSystems.join(", ")} and needs confirmation before engineering reruns.`
          : `Ready for quick partial rerun: ${reactiveChangedSystems.join(", ")}.`,
      });
    }, REACTIVE_EDIT_POLICY_PREFERENCE.debounced_validation_ms);
    return () => window.clearTimeout(timeout);
  }, [backendResult?.final_plan, reactiveChangedSystems, reactiveChangedTargets]);
  const managerMetrics = useMemo<ManagerMetrics>(
    () => currentPlanMeta?.manager_export?.metrics ?? {},
    [currentPlanMeta],
  );
  const quantityTotals = useMemo<QuantityTotals>(
    () => currentPlanMeta?.quantities?.totals ?? {},
    [currentPlanMeta],
  );
  const stormSummary = useMemo<StormSummary>(() => currentPlanMeta?.storm_pipes ?? {}, [currentPlanMeta]);
  const drainageSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.drainage ?? {}, [currentPlanMeta]);
  const gradingSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.grading ?? {}, [currentPlanMeta]);
  const drainageLowPoints = useMemo(() => {
    const fromDrainage = Array.isArray((drainageSummary as Record<string, unknown>)?.low_points)
      ? ((drainageSummary as Record<string, unknown>).low_points as Array<Record<string, unknown>>)
      : [];
    const fromGrading = Array.isArray((gradingSummary as Record<string, unknown>)?.low_points)
      ? ((gradingSummary as Record<string, unknown>).low_points as Array<Record<string, unknown>>)
      : [];
    const candidates = fromDrainage.length ? fromDrainage : fromGrading;
    return candidates
      .map((item) => ({
        x: typeof item.x === "number" ? item.x : Number(item.x),
        y: typeof item.y === "number" ? item.y : Number(item.y),
        z: typeof item.z === "number" ? item.z : Number(item.z),
      }))
      .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
  }, [drainageSummary, gradingSummary]);

  const gradingResultSummary = useMemo(() => {
    const record = gradingSummary && typeof gradingSummary === "object" ? gradingSummary : {};
    const existingSurface =
      record.existing_surface && typeof record.existing_surface === "object"
        ? (record.existing_surface as Record<string, unknown>)
        : {};
    const terrainProfile =
      existingSurface.terrain_profile && typeof existingSurface.terrain_profile === "object"
        ? (existingSurface.terrain_profile as Record<string, unknown>)
        : {};
    const terrainStats =
      terrainProfile.terrain_stats && typeof terrainProfile.terrain_stats === "object"
        ? (terrainProfile.terrain_stats as Record<string, unknown>)
        : {};
    const surfaceControls =
      record.surface_controls && typeof record.surface_controls === "object"
        ? (record.surface_controls as Record<string, unknown>)
        : {};
    const downhillVector =
      surfaceControls.downhill_vector && typeof surfaceControls.downhill_vector === "object"
        ? (surfaceControls.downhill_vector as Record<string, unknown>)
        : {};
    const highPoints = Array.isArray(existingSurface.high_points)
      ? (existingSurface.high_points as unknown[])
      : [];
    const lowPoints = Array.isArray(record.low_points)
      ? (record.low_points as unknown[])
      : Array.isArray(existingSurface.low_points)
        ? (existingSurface.low_points as unknown[])
        : [];
    const rangeValue =
      typeof existingSurface.range_z === "number"
        ? existingSurface.range_z
        : Number(existingSurface.range_z ?? 0);
    const sampleCount = Number(terrainStats.sample_count ?? 0);
    const missingCount = Number(terrainStats.missing_count ?? 0);
    const dx = Number(downhillVector.dx ?? terrainProfile.downhill_dx ?? 0);
    const dy = Number(downhillVector.dy ?? terrainProfile.downhill_dy ?? 0);
    const eastWest = Math.abs(dx) > 0.05 ? (dx > 0 ? "east" : "west") : "";
    const northSouth = Math.abs(dy) > 0.05 ? (dy > 0 ? "north" : "south") : "";
    const slopeDirection = [northSouth, eastWest].filter(Boolean).join("-") || "not established";
    const sourceQuality = String(record.grading_source_quality || terrainProfile.source_quality || "");
    const sourceDetail = String(record.grading_source_detail || terrainProfile.source_detail || "");
    return {
      hasResult: Boolean(sourceQuality || sourceDetail || highPoints.length || lowPoints.length || rangeValue),
      sourceQuality,
      sourceDetail,
      sampleCount: Number.isFinite(sampleCount) ? sampleCount : 0,
      missingCount: Number.isFinite(missingCount) ? missingCount : 0,
      elevationRange: Number.isFinite(rangeValue) ? rangeValue : 0,
      highPointCount: highPoints.length,
      lowPointCount: lowPoints.length,
      slopeSummary: slopeDirection === "not established" ? "Slope direction not established." : `Slope direction trends ${slopeDirection}.`,
    };
  }, [gradingSummary]);

  const previewLabels = useMemo(
    () => planPreviewAnnotations?.labels ?? [],
    [planPreviewAnnotations],
  );
  const issueTargets = useMemo(() => {
    const keywordMap = [
      { key: "pipe", token: "PIPE" },
      { key: "drain", token: "DRAIN" },
      { key: "storm", token: "STORM" },
      { key: "basin", token: "BASIN" },
      { key: "parking", token: "PARK" },
      { key: "ada", token: "ADA" },
      { key: "road", token: "ROAD" },
      { key: "utility", token: "UTIL" },
      { key: "water", token: "WATER" },
      { key: "sanitary", token: "SAN" },
    ];
    if (!issues.length) return [];
    return issues.map((issue, idx) => {
      const lowered = issue.message.toLowerCase();
      const matched = keywordMap.find((item) => lowered.includes(item.key));
      const labelMatch = matched
        ? previewLabels.find((label) => label.label.toLowerCase().includes(matched.key))
        : null;
      return {
        id: `${issue.message}-${idx}`,
        label: labelMatch?.label ?? "",
      };
    });
  }, [issues, previewLabels]);

  const [debugGradingFixtureLoaded, setDebugGradingFixtureLoaded] = useState(false);

  const gradingBlocker = useMemo(() => {
    const issue = issues.find(
      (item) => (item.code ?? "").toUpperCase() === "DRAINAGE_BLOCKED_BY_GRADING",
    );
    if (!issue?.context || typeof issue.context !== "object") return null;
    const ctx = issue.context as Record<string, unknown>;
    const toPoint = (value: unknown) => {
      if (!value || typeof value !== "object") return null;
      const rec = value as Record<string, unknown>;
      const x = typeof rec.x === "number" ? rec.x : Number(rec.x);
      const y = typeof rec.y === "number" ? rec.y : Number(rec.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      return { x, y };
    };
    const toZone = (value: unknown) => {
      if (!value || typeof value !== "object") return null;
      const rec = value as Record<string, unknown>;
      const x = typeof rec.x === "number" ? rec.x : Number(rec.x);
      const y = typeof rec.y === "number" ? rec.y : Number(rec.y);
      const w = typeof rec.w === "number" ? rec.w : Number(rec.w);
      const h = typeof rec.h === "number" ? rec.h : Number(rec.h);
      if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(w) || !Number.isFinite(h)) return null;
      return { x, y, w, h };
    };
    return {
      sourcePoint: toPoint(ctx.source_point),
      blockedTarget: toPoint(ctx.blocked_target),
      blockerLocation: toPoint(ctx.blocker_location),
      suggestedFixZone: toZone(ctx.suggested_fix_zone),
      approximate: Boolean(ctx.approximate),
    };
  }, [issues]);

  const selectedIssueLabel = issueTargets.find((item) => item.id === selectedIssueId)?.label ?? "";

  const pipeSegments = useMemo<PipeSegment[]>(() => {
    const segments =
      stormSummary?.segments ||
      stormSummary?.pipe_segments ||
      stormSummary?.storm_pipe_segments ||
      [];
    return Array.isArray(segments) ? segments : [];
  }, [stormSummary]);

  const totalPipeLength =
    readMetricValue(managerMetrics.storm_pipe_length_ft) ??
    (pipeSegments.length
      ? pipeSegments.reduce((sum, seg) => sum + Number(seg.length_ft || 0), 0)
      : null);
  const maxSlope = pipeSegments.length
    ? Math.max(
        ...pipeSegments.map((seg) =>
          Number(seg.slope_pct ?? (seg.slope_ft_ft ?? 0) * 100),
        ),
      )
    : null;
  const minSlope = pipeSegments.length
    ? Math.min(
        ...pipeSegments.map((seg) =>
          Number(seg.slope_pct ?? (seg.slope_ft_ft ?? 0) * 100),
        ),
      )
    : null;
  const flowCfs =
    readMetricValue(managerMetrics.pipe_capacity_total_cfs) ??
    readMetricValue(stormSummary.total_system_flow_cfs) ??
    readMetricValue(stormSummary.total_system_capacity_cfs) ??
    null;
  const cutFillNet =
    readMetricValue(managerMetrics.earthwork_net_cf) ??
    readMetricValue((gradingSummary as { earthwork?: { net_cf?: number } })?.earthwork?.net_cf) ??
    null;
  const basinSize =
    (Array.isArray(drainageSummary?.basins) && drainageSummary.basins[0]?.area_sf) ||
    (Array.isArray(drainageSummary?.basins) && drainageSummary.basins[0]?.footprint_area_sf) ||
    null;
  const quantityRows = useMemo(() => {
    const rows = [
      { label: "Lot area", value: quantityTotals.lot_area_sf ?? null, unit: "sf" },
      { label: "Building area", value: quantityTotals.building_area_sf ?? null, unit: "sf" },
      { label: "Parking area", value: quantityTotals.parking_area_sf ?? null, unit: "sf" },
      { label: "Road area", value: quantityTotals.road_area_sf ?? null, unit: "sf" },
      { label: "Impervious area", value: quantityTotals.estimated_impervious_area_sf ?? null, unit: "sf" },
      { label: "Parking stalls", value: quantityTotals.estimated_parking_stalls ?? null, unit: "stalls" },
      { label: "Road length", value: quantityTotals.road_length_ft ?? null, unit: "ft" },
      { label: "Sidewalk length", value: quantityTotals.sidewalk_length_ft ?? null, unit: "ft" },
      { label: "Pipe length", value: quantityTotals.pipe_length_ft ?? null, unit: "ft" },
      { label: "Utility length", value: quantityTotals.utility_length_ft ?? null, unit: "ft" },
      { label: "Sanitary length", value: quantityTotals.sanitary_length_ft ?? null, unit: "ft" },
      { label: "Drainage flow length", value: quantityTotals.drainage_flow_length_ft ?? null, unit: "ft" },
      { label: "Pond count", value: quantityTotals.pond_count ?? null, unit: "ea" },
      { label: "Inlet count", value: quantityTotals.inlet_count ?? null, unit: "ea" },
      { label: "Bridge area", value: quantityTotals.bridge_area_sf ?? null, unit: "sf" },
      { label: "Pool area", value: quantityTotals.pool_area_sf ?? null, unit: "sf" },
      { label: "Lot count", value: quantityTotals.lot_feature_count ?? null, unit: "ea" },
    ];
    return rows.filter((row) => Number(row.value || 0) > 0);
  }, [quantityTotals]);
  const measurementOverlayStats = useMemo(
    () => [
      { label: "Lot area", value: quantityTotals.lot_area_sf ?? null, unit: "sf" },
      { label: "Building area", value: quantityTotals.building_area_sf ?? null, unit: "sf" },
      { label: "Parking area", value: quantityTotals.parking_area_sf ?? null, unit: "sf" },
      { label: "Road length", value: quantityTotals.road_length_ft ?? null, unit: "ft" },
      { label: "Impervious area", value: quantityTotals.estimated_impervious_area_sf ?? null, unit: "sf" },
      { label: "Parking stalls", value: quantityTotals.estimated_parking_stalls ?? null, unit: "stalls" },
    ],
    [quantityTotals],
  );
  const calculationOverlayStats = useMemo(
    () => [
      { label: "Total pipe length", value: totalPipeLength, unit: "ft" },
      { label: "Max slope", value: maxSlope, unit: "%" },
      { label: "Min slope", value: minSlope, unit: "%" },
      { label: "Flow (CFS)", value: flowCfs, unit: "cfs" },
      { label: "Cut / fill net", value: cutFillNet, unit: "cf" },
      { label: "Pond size", value: basinSize, unit: "sf" },
    ],
    [totalPipeLength, maxSlope, minSlope, flowCfs, cutFillNet, basinSize],
  );
  const currentTruthAudit = useMemo(
    () => currentPlanMeta?.truth_audit ?? {},
    [currentPlanMeta],
  );
  const currentManualFailures = useMemo<ManualFailure[]>(
    () =>
      Array.isArray(currentPlanMeta?.manual_validation?.failures)
        ? currentPlanMeta.manual_validation.failures
        : [],
    [currentPlanMeta],
  );
  const currentExplanation = useMemo<PlanExplanation>(
    () => currentPlanMeta?.explanation ?? {},
    [currentPlanMeta],
  );
  const suggestedImproveGoal = useMemo(() => {
    const failureBlob = [
      ...currentManualFailures.map((failure) =>
        [failure.code, failure.message, failure.system, failure.rule]
          .filter(Boolean)
          .join(" "),
      ),
      ...issues.map((issue) => issue.message),
    ]
      .join(" ")
      .toLowerCase();

    if (failureBlob.includes("drain") || failureBlob.includes("inlet")) {
      return "improve_drainage";
    }
    if (failureBlob.includes("pipe")) {
      return "reduce_pipe_length";
    }
    if (
      failureBlob.includes("grade") ||
      failureBlob.includes("earthwork") ||
      failureBlob.includes("slope")
    ) {
      return "reduce_grading";
    }
    if (failureBlob.includes("parking")) {
      return "maximize_parking";
    }
    return undefined;
  }, [currentManualFailures, issues]);


  const applyBackendResult = (data: PlanResponse) => {
    setBackendResult(data);
    if (Array.isArray(data?.assumptions)) {
      setAssumptions(
        data.assumptions.map((item: BackendAssumption) => ({
          field: item.field_name ?? "unknown",
          value:
            typeof item.assumed_value === "string"
              ? item.assumed_value
              : JSON.stringify(item.assumed_value),
          reason: item.reason ?? "",
        })),
      );
    } else {
      setAssumptions(defaultAssumptions);
    }

    if (Array.isArray(data?.issues)) {
      setIssues(
        data.issues.map((item: BackendIssue) => ({
          severity: item.severity === "error" ? "error" : "warning",
          message: item.message ?? "Unknown issue",
          code: typeof item.code === "string" ? item.code : undefined,
          context: item.context && typeof item.context === "object" ? item.context : undefined,
        })),
      );
    } else {
      setIssues([]);
    }
  };

  const appendChatMessage = (
    role: ChatMessage["role"],
    content: string,
    kind: ChatMessage["kind"] = "message",
    feedback?: ChatMessage["feedback"],
  ) => {
    setChatMessages((current) => {
      const phaseTag =
        role === "assistant" || role === "system"
          ? currentPhaseLabelRef.current || undefined
          : undefined;
      const next = [
        ...current,
        createChatMessage(role, content, kind, feedback, phaseTag),
      ];
      chatMessagesRef.current = next;
      return next;
    });
  };


  const setMessageFeedback = async (
    messageId: string,
    feedback: ChatMessage["feedback"],
  ) => {
    if (!token || !feedback) return;
    const thread = chatMessagesRef.current;
    const idx = thread.findIndex((message) => message.id === messageId);
    if (idx < 0) return;
    const target = thread[idx];
    const prevUser = [...thread]
      .slice(0, idx)
      .reverse()
      .find((message) => message.role === "user");
    const userMessage = prevUser?.content ?? "";

    setChatMessages((current) => {
      const next = current.map((message) =>
        message.id === messageId ? { ...message, feedback } : message,
      );
      chatMessagesRef.current = next;
      return next;
    });

    try {
      await postJson<{ success: boolean }>(
        "/api/chat/feedback",
        {
          project_id: currentProject?.project_id ?? null,
          message_id: messageId,
          feedback,
          message: userMessage,
          assistant_message: target.content,
          context: buildChatDecisionContext({}, userMessage),
        },
        { token },
      );
    } catch {
      // Feedback logging should never block chat UX.
    }
  };

  useEffect(() => {
    return () => {
      if (chatAutosaveTimeoutRef.current !== null) {
        window.clearTimeout(chatAutosaveTimeoutRef.current);
      }
    };
  }, []);


  useChatPersistence({
    chatMessages,
    setChatMessages,
    chatMessagesRef,
    chatScrollRef,
    projectId,
    currentProjectId: currentProject?.project_id,
  });

  useEffect(() => {
    if (!effectiveDemoWorkspaceEnabled || demoWorkspaceSeededRef.current) return;
    const demoPlacements = createDemoPlacements();
    const demoResult = createDemoPlanResponse();
    const demoProjectInput: ProjectInput = {
      prompt_text: "Demo UI QA workspace for a 9-acre mixed-use civil site.",
      input_mode: "user",
      strict_mode: false,
      allow_ai_fill_for_blanks: false,
      manual_fields: {
        project_name: "Pinecrest Mixed-Use",
        file_name: "pinecrest-demo-ui",
        units: "ft",
        project_type: "mixed_use",
        lot: { x: 0, y: 0, w: 760, h: 520 },
        disciplines: ["roads", "grading", "drainage", "utilities"],
        buildings: demoPlacements
          .filter((item) => item.type !== "site")
          .map((item) => ({
            id: item.id,
            name: item.label ?? item.id,
            type: item.type,
            x: item.x,
            y: item.y,
            w: item.w,
            d: item.d,
            height_ft: item.h,
            rotation: item.rotation,
            source: item.source,
            generated: item.generated,
            locked: item.locked,
          })),
      },
      meta: {
        auto_named: false,
        auto_file_named: false,
        site_inputs: {
          address: "Pinecrest Mixed-Use Demo Site",
          geocode: {
            lat: 32.7767,
            lng: -96.797,
            display_name: "Pinecrest Mixed-Use Demo Site",
            provider: "demo",
          },
          site_rotation_deg: 0,
          site_alignment_locked: true,
          use_survey_for_grading: true,
        },
      },
    };
    const demoProject: ProjectRecord = {
      project_id: DEMO_PROJECT_ID,
      name: "Pinecrest Mixed-Use",
      description: "Seeded demo workspace for UI QA.",
      updated_at: Date.now() / 1000,
      project_input: demoProjectInput,
      latest_result: demoResult,
      has_result: true,
    };
    demoWorkspaceSeededRef.current = true;
    suppressProjectAutoLoadRef.current = true;
    setProjects([demoProject]);
    setCurrentProject(demoProject);
    setProjectId(DEMO_PROJECT_ID);
    setSiteName("Pinecrest Mixed-Use");
    setFileName("pinecrest-demo-ui");
    setSiteNameAuto(false);
    setFileNameAuto(false);
    setLotWidth("760");
    setLotHeight("520");
    setParkingCount("116");
    setBuildingWidth("110");
    setBuildingDepth("58");
    setBuildingCount("3");
    setProjectType("mixed_use");
    setSiteAddress("Pinecrest Mixed-Use Demo Site");
    setSiteScaleLocked(true);
    setUseSurveyForGrading(true);
    setBuildingPlacements(demoPlacements);
    setPlacementModeEnabled(false);
    setActivePlacementId("demo-basin-a");
    setPreviewQuality("standard");
    setPreviewMode("2d");
    setPreviewInteraction("static");
    setPreviewHeightPx(720);
    setSystemStatuses({
      roads: "fresh",
      parking: "fresh",
      grading: "fresh",
      drainage: "stale",
      utilities: "fresh",
    });
    applyBackendResult(demoResult);
    const demoThread = [
      createWelcomeMessage(),
      createChatMessage(
        "system",
        "Demo workspace loaded. Use this seeded project to QA canvas modes, sidebars, status cards, and object editing without signing in.",
        "status",
      ),
    ];
    setChatMessages(demoThread);
    chatMessagesRef.current = demoThread;
    setStatusMessage("Demo workspace loaded for UI QA.");
  }, [effectiveDemoWorkspaceEnabled]);

  const applyProjectInput = (projectInput: ProjectInput) => {
    if (!projectInput || typeof projectInput !== "object") {
      return;
    }

    const manualFields = projectInput.manual_fields ?? {};
    const lot = (manualFields.lot ?? {}) as { w?: number; h?: number };
    const sitePlan = (manualFields.site_plan ?? {}) as { parking_count?: number };
    const gradingFields = (manualFields.grading ?? {}) as {
      min_slope_pct?: number;
      max_parking_slope_pct?: number;
      max_road_grade_pct?: number;
      max_ada_cross_slope_pct?: number;
    };
    const drainageFields = (manualFields.drainage ?? {}) as NonNullable<ManualFields["drainage"]>;
    const drainageForced = Array.isArray(drainageFields?.forced_inlets)
      ? (drainageFields?.forced_inlets as Array<Record<string, unknown>>)
      : [];
    const disciplines = toArray(manualFields.disciplines);
    const buildingsList = Array.isArray(manualFields.buildings) ? manualFields.buildings : [];
    const restoredThread: ChatMessage[] = Array.isArray(projectInput.meta?.chat_thread)
      ? projectInput.meta.chat_thread
          .filter((message) => message && typeof message.content === "string")
          .map((message): ChatMessage => ({
            id:
              typeof message.id === "string"
                ? message.id
                : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            role:
              message.role === "user" ||
              message.role === "assistant" ||
              message.role === "system"
                ? message.role
                : "assistant",
            content: message.content,
            createdAt:
              typeof message.createdAt === "number"
                ? message.createdAt
                : Date.now(),
            kind:
              message.kind === "status" ||
              message.kind === "explanation" ||
              message.kind === "action"
                ? message.kind
                : "message",
            feedback:
              message.feedback === "up" || message.feedback === "down"
                ? message.feedback
                : undefined,
            phaseTag: typeof message.phaseTag === "string" ? message.phaseTag : undefined,
          }))
      : [];
    const autoNamed = Boolean(projectInput.meta?.auto_named);
    const autoFileNamed = Boolean(projectInput.meta?.auto_file_named);

    setPrompt(projectInput.prompt_text ?? "");
    setImageName(projectInput.image_path ?? "");
    setUploadedImageApiUrl(
      projectInput.image_path ? uploadedImageSrc(projectInput.image_path, token) : "",
    );
    setUploadedImagePreviewUrl("");
    setSiteName(manualFields.project_name ?? "");
    setFileName(manualFields.file_name ?? "");
    setSiteNameAuto(autoNamed || !manualFields.project_name);
    setFileNameAuto(autoFileNamed || !(manualFields.file_name ?? manualFields.project_name));
    setUnits(manualFields.units ?? "ft");
    setProjectType(manualFields.project_type ?? "");
    setLotWidth(String(lot.w ?? ""));
    setLotHeight(String(lot.h ?? ""));
    setSetback(String(manualFields.setback ?? ""));
    setBuildingWidth(String(manualFields.building_width ?? ""));
    setBuildingDepth(String(manualFields.building_depth ?? ""));
    setBuildingCount(buildingsList.length ? String(buildingsList.length) : "");
    const parsedPlacements = buildingsList
      .map((raw, idx) => {
        if (!raw || typeof raw !== "object") return null;
        const rec = raw as Record<string, unknown>;
        const originRaw = (rec as { origin?: unknown }).origin;
        const origin = Array.isArray(originRaw) ? originRaw : [];
        const rawX = rec.x ?? origin[0];
        const rawY = rec.y ?? origin[1];
        const x = typeof rawX === "number" ? rawX : rawX !== undefined ? Number(rawX) : NaN;
        const y = typeof rawY === "number" ? rawY : rawY !== undefined ? Number(rawY) : NaN;
        const rawW = rec.w ?? rec.width ?? manualFields.building_width;
        const rawD = rec.d ?? rec.depth ?? manualFields.building_depth;
        const w = typeof rawW === "number" ? rawW : rawW !== undefined ? Number(rawW) : NaN;
        const d = typeof rawD === "number" ? rawD : rawD !== undefined ? Number(rawD) : NaN;
        if (!Number.isFinite(w) || !Number.isFinite(d)) return null;
        const placed = Number.isFinite(x) && Number.isFinite(y);
        const geometryType = isCustomGeometryMode(rec.geometry_type) ? rec.geometry_type : undefined;
        const geometry = normalizeGeometryPoints(rec.geometry);
        return {
          id: typeof rec.id === "string" ? rec.id : `building-${Date.now()}-${idx}`,
          label:
            typeof rec.label === "string"
              ? rec.label
              : typeof rec.name === "string"
                ? rec.name
                : `Building ${idx + 1}`,
          type: (typeof rec.type === "string" ? rec.type : "building") as SiteObjectType,
          x: placed ? x : undefined,
          y: placed ? y : undefined,
          w,
          d,
          rotation: typeof rec.rotation === "number" ? rec.rotation : undefined,
          use: typeof rec.use === "string" ? rec.use : undefined,
          locked: Boolean(rec.locked),
          placed,
          source:
            rec.source === "generated" ||
            rec.source === "manual_drawn" ||
            rec.source === "inferred" ||
            rec.source === "detected_from_image" ||
            rec.source === "user_confirmed"
              ? rec.source
              : "user",
          generated: Boolean(rec.generated),
          geometryType,
          geometry: geometry?.length ? geometry : undefined,
          meta: rec.meta && typeof rec.meta === "object" ? (rec.meta as Record<string, unknown>) : undefined,
          systemDependencies: Array.isArray(rec.systemDependencies)
            ? (rec.systemDependencies as BuildingPlacement["systemDependencies"])
            : undefined,
        } as BuildingPlacement;
      })
      .filter(Boolean) as BuildingPlacement[];

    const pondPlacements = (Array.isArray(manualFields.ponds) ? manualFields.ponds : [])
      .map((raw, idx) => {
        if (!raw || typeof raw !== "object") return null;
        const rec = raw as Record<string, unknown>;
        const rawX = rec.x;
        const rawY = rec.y;
        const x = typeof rawX === "number" ? rawX : rawX !== undefined ? Number(rawX) : NaN;
        const y = typeof rawY === "number" ? rawY : rawY !== undefined ? Number(rawY) : NaN;
        const rawW = rec.w ?? 60;
        const rawD = rec.d ?? 40;
        const w = typeof rawW === "number" ? rawW : rawW !== undefined ? Number(rawW) : NaN;
        const d = typeof rawD === "number" ? rawD : rawD !== undefined ? Number(rawD) : NaN;
        if (!Number.isFinite(w) || !Number.isFinite(d)) return null;
        const placed = Number.isFinite(x) && Number.isFinite(y);
        return {
          id: typeof rec.id === "string" ? rec.id : `basin-${Date.now()}-${idx}`,
          label:
            typeof rec.label === "string"
              ? rec.label
              : typeof rec.name === "string"
                ? rec.name
                : "Basin",
          type: "basin" as SiteObjectType,
          x: placed ? x : undefined,
          y: placed ? y : undefined,
          w,
          d,
          rotation: typeof rec.rotation === "number" ? rec.rotation : undefined,
          locked: Boolean(rec.locked),
          placed,
          source: typeof rec.source === "string" ? rec.source : "generated",
          generated: Boolean(rec.generated),
          systemDependencies: Array.isArray(rec.systemDependencies)
            ? (rec.systemDependencies as string[])
            : ["drainage"],
        } as BuildingPlacement;
      })
      .filter(Boolean) as BuildingPlacement[];

    const inletPlacements = (Array.isArray((manualFields.drainage ?? {}).forced_inlets)
      ? ((manualFields.drainage ?? {}).forced_inlets as Array<Record<string, unknown>>)
      : []
    )
      .map((raw, idx) => {
        if (!raw || typeof raw !== "object") return null;
        const rec = raw as Record<string, unknown>;
        const rawX = rec.x;
        const rawY = rec.y;
        const x = typeof rawX === "number" ? rawX : rawX !== undefined ? Number(rawX) : NaN;
        const y = typeof rawY === "number" ? rawY : rawY !== undefined ? Number(rawY) : NaN;
        if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
        return {
          id: typeof rec.id === "string" ? rec.id : `inlet-${Date.now()}-${idx}`,
          label:
            typeof rec.label === "string"
              ? rec.label
              : typeof rec.name === "string"
                ? rec.name
                : "Inlet",
          type: "inlet" as SiteObjectType,
          x,
          y,
          w: 8,
          d: 8,
          rotation: 0,
          locked: Boolean(rec.locked),
          placed: true,
          source: typeof rec.source === "string" ? rec.source : "generated",
          generated: Boolean(rec.generated),
          systemDependencies: ["drainage"],
        } as BuildingPlacement;
      })
      .filter(Boolean) as BuildingPlacement[];

    const siteObjectPlacements = (Array.isArray(manualFields.site_objects) ? manualFields.site_objects : [])
      .map((raw, idx) => {
        if (!raw || typeof raw !== "object") return null;
        const rec = raw as Record<string, unknown>;
        const rawX = rec.x;
        const rawY = rec.y;
        const x = typeof rawX === "number" ? rawX : rawX !== undefined ? Number(rawX) : NaN;
        const y = typeof rawY === "number" ? rawY : rawY !== undefined ? Number(rawY) : NaN;
        const rawW = rec.w ?? 10;
        const rawD = rec.d ?? 10;
        const w = typeof rawW === "number" ? rawW : rawW !== undefined ? Number(rawW) : NaN;
        const d = typeof rawD === "number" ? rawD : rawD !== undefined ? Number(rawD) : NaN;
        if (!Number.isFinite(w) || !Number.isFinite(d)) return null;
        const placed = Number.isFinite(x) && Number.isFinite(y);
        const geometryType = isCustomGeometryMode(rec.geometry_type) ? rec.geometry_type : undefined;
        const geometry = normalizeGeometryPoints(rec.geometry);
        return {
          id: typeof rec.id === "string" ? rec.id : `site-object-${Date.now()}-${idx}`,
          label:
            typeof rec.label === "string"
              ? rec.label
              : typeof rec.name === "string"
                ? rec.name
                : `Object ${idx + 1}`,
          type: (typeof rec.type === "string" ? rec.type : "custom") as SiteObjectType,
          x: placed ? x : undefined,
          y: placed ? y : undefined,
          w,
          d,
          h: typeof rec.height_ft === "number" ? rec.height_ft : undefined,
          rotation: typeof rec.rotation === "number" ? rec.rotation : undefined,
          locked: Boolean(rec.locked),
          placed,
          source:
            rec.source === "generated" ||
            rec.source === "manual_drawn" ||
            rec.source === "inferred" ||
            rec.source === "detected_from_image" ||
            rec.source === "user_confirmed"
              ? rec.source
              : "manual_drawn",
          generated: Boolean(rec.generated),
          geometryType,
          geometry: geometry?.length ? geometry : undefined,
          meta: rec.meta && typeof rec.meta === "object" ? (rec.meta as Record<string, unknown>) : undefined,
          systemDependencies: Array.isArray(rec.systemDependencies)
            ? (rec.systemDependencies as BuildingPlacement["systemDependencies"])
            : ["roads", "parking", "grading", "drainage", "utilities"],
        } as BuildingPlacement;
      })
      .filter(Boolean) as BuildingPlacement[];

    const mergedPlacements = siteObjectPlacements.length
      ? siteObjectPlacements
      : [...parsedPlacements, ...pondPlacements, ...inletPlacements];
    setBuildingPlacements(mergedPlacements);
    setPlacementModeEnabled(false);
    setActivePlacementId(null);
    setParkingCount(String(sitePlan.parking_count ?? ""));
    setMinSlopePct(String(gradingFields.min_slope_pct ?? ""));
    setPipeMinSlopePct(String(drainageFields.min_pipe_slope_pct ?? ""));
    setDrainageForcedInlets(
      drainageForced
        .map((item) => {
          const rec = item as { x?: number; y?: number; name?: string };
          if (typeof rec?.x !== "number" || typeof rec?.y !== "number") return null;
          return { x: rec.x, y: rec.y, name: typeof rec.name === "string" ? rec.name : undefined };
        })
        .filter(Boolean) as Array<{ x: number; y: number; name?: string }>,
    );
    setDrainageConnectOrphans(Boolean((manualFields.drainage ?? {}).connect_orphans));
    setDrainageAllowSlopeAdjust(Boolean((manualFields.drainage ?? {}).allow_slope_adjustment));
    const rawMaxSlopeAdjust = (manualFields.drainage ?? {}).max_slope_adjust;
    setDrainageMaxSlopeAdjust(
      typeof rawMaxSlopeAdjust === "number" && Number.isFinite(rawMaxSlopeAdjust)
        ? rawMaxSlopeAdjust
        : 0.001,
    );
    setMaxParkingSlopePct(String(gradingFields.max_parking_slope_pct ?? ""));
    setMaxRoadGradePct(String(gradingFields.max_road_grade_pct ?? ""));
    setMaxAdaCrossSlopePct(String(gradingFields.max_ada_cross_slope_pct ?? ""));
    setRoads(disciplines.includes("corridor"));
    setGrading(disciplines.includes("grading"));
    setDrainage(disciplines.includes("drainage"));
    setUtilities(disciplines.includes("utility"));
    const nextThread = restoredThread.length ? restoredThread : [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
  };

  const resolveLotBounds = useCallback(() => {
    const width = parsePositiveNumber(lotWidth) ?? 0;
    const height = parsePositiveNumber(lotHeight) ?? 0;
    if (!width || !height) {
      const manualLotRaw =
        currentProject?.project_input &&
        typeof currentProject.project_input === "object" &&
        (currentProject.project_input as {
          manual_fields?: { lot?: { x?: number; y?: number; w?: number; h?: number } | false };
        }).manual_fields?.lot;
      const manualLot: { x?: number; y?: number; w?: number; h?: number } | null =
        manualLotRaw && typeof manualLotRaw === "object" ? manualLotRaw : null;
      if (manualLot?.w && manualLot?.h) {
        return {
          x: typeof manualLot.x === "number" ? manualLot.x : 0,
          y: typeof manualLot.y === "number" ? manualLot.y : 0,
          w: manualLot.w,
          h: manualLot.h,
        };
      }
      const site = buildingPlacements.find((item) => item.type === "site");
      if (site?.w && site?.d) {
        return { x: site.x ?? 0, y: site.y ?? 0, w: site.w, h: site.d };
      }
    }
    const site = buildingPlacements.find((item) => item.type === "site");
    return { x: site?.x ?? 0, y: site?.y ?? 0, w: width, h: height };
  }, [buildingPlacements, lotHeight, lotWidth]);

  useEffect(() => {
    const site = buildingPlacements.find((item) => item.type === "site");
    if (!site) return;
    const nextWidth = String(site.w ?? "");
    const nextHeight = String(site.d ?? "");
    if (nextWidth && lotWidth !== nextWidth) {
      setLotWidth(nextWidth);
    }
    if (nextHeight && lotHeight !== nextHeight) {
      setLotHeight(nextHeight);
    }
  }, [buildingPlacements, lotHeight, lotWidth]);

  useEffect(() => {
    const site = buildingPlacements.find((item) => item.type === "site");
    if (!site) return;
    if (siteScaleLocked && !site.locked) {
      setBuildingPlacements((prev) =>
        prev.map((item) =>
          item.type === "site"
            ? {
                ...item,
                locked: true,
                capabilities: {
                  ...item.capabilities,
                  movable: false,
                  resizable: false,
                  rotatable: false,
                },
              }
            : item,
        ),
      );
    }
  }, [buildingPlacements, siteScaleLocked]);

  useEffect(() => {
    const hasSite = buildingPlacements.some((item) => item.type === "site");
    if (!hasSite) return;
    setShowSiteBounds(!siteScaleLocked);
  }, [buildingPlacements, siteScaleLocked]);

  const resolveDefaultBuildingDims = useCallback(() => {
    const width = parsePositiveNumber(buildingWidth) ?? SITE_OBJECT_CATALOG.building.defaultW;
    const depth = parsePositiveNumber(buildingDepth) ?? SITE_OBJECT_CATALOG.building.defaultD;
    return { w: width, d: depth };
  }, [buildingDepth, buildingWidth]);

  const hasSiteBoundary = useCallback(() => {
    const lot = resolveLotBounds();
    return Boolean(lot.w && lot.h);
  }, [resolveLotBounds]);

  const placedObjectCount = useMemo(
    () =>
      buildingPlacements.filter(
        (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
      ).length,
    [buildingPlacements],
  );

  const debugLog = useCallback(
    (label: string, payload?: Record<string, unknown>) => {
      if (!debugPreview) return;
      const snapshot = {
        projectId: projectId || currentProject?.project_id || "",
        canonicalCount: buildingPlacements.length,
        placedCount: placedObjectCount,
        previewImageActive: Boolean(planPreviewUrl),
        placementMode: placementModeEnabled || Boolean(activePlacementId),
      };
      console.debug(`[debug-preview] ${label}`, { ...snapshot, ...(payload ?? {}) });
    },
    [
      activePlacementId,
      buildingPlacements.length,
      currentProject?.project_id,
      debugPreview,
      placedObjectCount,
      placementModeEnabled,
      planPreviewUrl,
      projectId,
    ],
  );

  useEffect(() => {
    if (!activePlacementId) return;
    const exists = buildingPlacements.some((item) => item.id === activePlacementId);
    if (!exists) {
      debugLog("clear-missing-selected", { id: activePlacementId });
      setActivePlacementId(null);
      setPlacementModeEnabled(false);
    }
  }, [activePlacementId, buildingPlacements, debugLog]);

  useEffect(() => {
    if (!focusObjectId) return;
    const exists = buildingPlacements.some((item) => item.id === focusObjectId);
    if (!exists) {
      debugLog("clear-missing-focus", { id: focusObjectId });
      setFocusObjectId(null);
    }
  }, [buildingPlacements, debugLog, focusObjectId]);

  useEffect(() => {
    if (!debugPreview) return;
    if (placedObjectCount > buildingPlacements.length) {
      console.warn("[debug-preview] placed-count-exceeds-canonical", {
        placedObjectCount,
        canonicalCount: buildingPlacements.length,
      });
    }
  }, [buildingPlacements.length, debugPreview, placedObjectCount]);


  const ensureSiteBoundary = useCallback(
    (reason: string) => {
      const hasSite = buildingPlacements.some((item) => item.type === "site");
      if (hasSite) return true;
      const width =
        parsePositiveNumber(lotWidth) ?? SITE_OBJECT_CATALOG.site.defaultW;
      const height =
        parsePositiveNumber(lotHeight) ?? SITE_OBJECT_CATALOG.site.defaultD;
      if (!parsePositiveNumber(lotWidth)) setLotWidth(String(width));
      if (!parsePositiveNumber(lotHeight)) setLotHeight(String(height));
      setBuildingPlacements((prev) => {
        const filtered = prev.filter((item) => item.type !== "site");
        const sitePlacement: BuildingPlacement = {
          id: `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: SITE_OBJECT_CATALOG.site.label,
          type: "site",
          w: width,
          d: height,
          x: 0,
          y: 0,
          rotation: 0,
          locked: true,
          placed: true,
          source: "user",
          generated: false,
          capabilities: {
            movable: false,
            resizable: false,
            rotatable: false,
            deletable: false,
          },
          systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
          meta: { category: SITE_OBJECT_CATALOG.site.category },
        };
        return [sitePlacement, ...filtered];
      });
      setStatusMessage(
        `Site boundary initialized at ${width} ft by ${height} ft. ${reason}`,
      );
      return true;
    },
    [buildingPlacements, lotHeight, lotWidth],
  );

  const systemsImpactedByPlacement = useCallback((target?: Partial<BuildingPlacement> | null): EngineeringSystemKey[] => {
    const explicit = Array.isArray(target?.systemDependencies)
      ? target.systemDependencies.filter((item): item is EngineeringSystemKey => item in REACTIVE_SYSTEM_STAGE_MAP)
      : [];
    if (explicit.length) return Array.from(new Set(explicit));
    const type = target?.type ?? "building";
    if (type === "site") return ["roads", "parking", "grading", "drainage", "utilities"];
    if (["building", "pad", "amenity", "pool", "open_space", "lot_block"].includes(type)) {
      return ["roads", "parking", "grading", "drainage", "utilities"];
    }
    if (["basin", "outfall"].includes(type)) return ["grading", "drainage"];
    if (["inlet", "manhole"].includes(type)) return ["drainage", "utilities"];
    if (["hydrant", "utility_corridor"].includes(type)) return ["utilities"];
    if (["road", "driveway", "entrance", "parking", "sidewalk", "bridge"].includes(type)) {
      return ["roads", "parking", "grading", "drainage", "utilities"];
    }
    return ["roads", "parking", "grading", "drainage", "utilities"];
  }, []);

  const markSystemsStale = useCallback((systems?: EngineeringSystemKey[]) => {
    const targets = systems?.length
      ? Array.from(new Set(systems))
      : (["roads", "parking", "grading", "drainage", "utilities"] as EngineeringSystemKey[]);
    setSystemStatuses((prev) => ({
      roads: targets.includes("roads") && prev.roads !== "not_generated" ? "stale" : prev.roads,
      parking: targets.includes("parking") && prev.parking !== "not_generated" ? "stale" : prev.parking,
      grading: targets.includes("grading") && prev.grading !== "not_generated" ? "stale" : prev.grading,
      drainage: targets.includes("drainage") && prev.drainage !== "not_generated" ? "stale" : prev.drainage,
      utilities: targets.includes("utilities") && prev.utilities !== "not_generated" ? "stale" : prev.utilities,
    }));
  }, []);

  const resolveParkingParams = useCallback(
    (
      target: BuildingPlacement,
      overrides?: Partial<BuildingPlacement>,
    ): {
      stallWidth: number;
      stallDepth: number;
      aisleWidth: number;
      adaAisleWidth: number;
      adaCount: number;
      compactCount: number;
      compactWidth: number;
      angleDeg: number;
      loading: "single" | "double";
      autoResizeToFitCount: boolean;
      useMixedAngles: boolean;
      compactZone: boolean;
    } => {
      const currentMeta = (target.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
      const nextMeta = (overrides?.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
      const loading =
        nextMeta.loading === "single"
          ? "single"
          : nextMeta.loading === "double"
            ? "double"
            : currentMeta.loading === "single"
              ? "single"
              : "double";
      return {
        stallWidth: Number.isFinite(nextMeta.stallWidth) ? Number(nextMeta.stallWidth) : Number(currentMeta.stallWidth) || 9,
        stallDepth: Number.isFinite(nextMeta.stallDepth) ? Number(nextMeta.stallDepth) : Number(currentMeta.stallDepth) || 18,
        aisleWidth: Number.isFinite(nextMeta.aisleWidth) ? Number(nextMeta.aisleWidth) : Number(currentMeta.aisleWidth) || 24,
        adaAisleWidth: Number.isFinite(nextMeta.adaAisleWidth) ? Number(nextMeta.adaAisleWidth) : Number(currentMeta.adaAisleWidth) || 8,
        adaCount: Number.isFinite(nextMeta.adaCount) ? Number(nextMeta.adaCount) : Number(currentMeta.adaCount) || 0,
        compactCount: Number.isFinite(nextMeta.compactCount) ? Number(nextMeta.compactCount) : Number(currentMeta.compactCount) || 0,
        compactWidth: Number.isFinite(nextMeta.compactWidth) ? Number(nextMeta.compactWidth) : Number(currentMeta.compactWidth) || 8,
        angleDeg: Number.isFinite(nextMeta.angleDeg) ? Number(nextMeta.angleDeg) : Number(currentMeta.angleDeg) || 90,
        loading,
        autoResizeToFitCount:
          typeof nextMeta.autoResizeToFitCount === "boolean"
            ? nextMeta.autoResizeToFitCount
            : Boolean(currentMeta.autoResizeToFitCount),
        useMixedAngles:
          typeof nextMeta.useMixedAngles === "boolean"
            ? nextMeta.useMixedAngles
            : Boolean(currentMeta.useMixedAngles),
        compactZone:
          typeof nextMeta.compactZone === "boolean"
            ? nextMeta.compactZone
            : Boolean(currentMeta.compactZone),
      };
    },
    [],
  );

  const computeParkingFootprint = useCallback(
    (
      target: BuildingPlacement,
      params: {
        stallWidth: number;
        stallDepth: number;
        aisleWidth: number;
        adaAisleWidth: number;
        adaCount: number;
        compactCount: number;
        compactWidth: number;
        angleDeg: number;
        loading: "single" | "double";
      },
      stallCount: number,
    ) => {
      const rows = params.loading === "double" ? 2 : 1;
      const angleRad = (Math.max(Math.min(params.angleDeg, 89), 0) * Math.PI) / 180;
      const depthAdj = params.stallDepth / Math.cos(angleRad || 0.0001);
      const shift = Math.tan(angleRad || 0.0001) * depthAdj;
      const moduleDepth = depthAdj * rows + params.aisleWidth;
      const perModuleWidth = (stallsPerRow: number) =>
        stallsPerRow * params.stallWidth + Math.abs(shift);
      const totalStalls = Math.max(stallCount, params.adaCount + params.compactCount);
      const stallsPerRow = Math.max(1, Math.ceil(totalStalls / rows));
      const moduleWidth = perModuleWidth(stallsPerRow);
      const modulesNeeded = Math.max(1, Math.ceil(totalStalls / (stallsPerRow * rows)));
      let cols = Math.max(1, Math.ceil(Math.sqrt(modulesNeeded)));
      let rowsOfModules = Math.max(1, Math.ceil(modulesNeeded / cols));
      if (totalStalls === 0) {
        cols = 1;
        rowsOfModules = 1;
      }
      if (target.w > 0) {
        const maxCols = Math.max(1, Math.floor(target.w / moduleWidth));
        cols = Math.max(1, Math.min(cols, maxCols || 1));
      }
      if (target.d > 0) {
        const maxRows = Math.max(1, Math.floor(target.d / moduleDepth));
        rowsOfModules = Math.max(1, Math.min(rowsOfModules, maxRows || 1));
      }
      const totalCapacity = stallsPerRow * rows * cols * rowsOfModules;
      const totalWidth = moduleWidth * cols;
      const totalDepth = moduleDepth * rowsOfModules;
      return {
        w: totalWidth,
        d: totalDepth,
        maxStalls: totalCapacity,
        moduleCount: cols * rowsOfModules,
        stallsPerRow,
        moduleCols: cols,
        moduleRows: rowsOfModules,
      };
    },
    [],
  );

  const formatObjectLabel = useCallback(
    (type: SiteObjectType, count: number) => {
      const base = SITE_OBJECT_CATALOG[type]?.label ?? "Object";
      return type === "site" ? base : `${base} ${count}`;
    },
    [],
  );

  const clearGeneratedPreview = useCallback(() => {
    setPlanPreviewUrl("");
    setPlanPreviewSummary(null);
    setPlanPreviewAnnotations(null);
    setBackendResult(null);
    setPlanPreviewProjectId(null);
    debugLog("clear-generated-preview");
  }, []);

  useEffect(() => {
    if (buildingPlacements.length > 0 || detectedPlacements.length > 0) return;
    if (backendResult) return;
    if (!planPreviewUrl) return;
    debugLog("clear-preview-empty-canonical");
    clearGeneratedPreview();
  }, [
    backendResult,
    buildingPlacements.length,
    clearGeneratedPreview,
    debugLog,
    detectedPlacements.length,
    planPreviewUrl,
  ]);

  const buildDefaultPolyline = useCallback(
    (target: { x: number; y: number; w: number; d: number }): Array<[number, number]> => {
      const isHorizontal = target.w >= target.d;
      if (isHorizontal) {
        return [
          [target.x, target.y + target.d / 2],
          [target.x + target.w, target.y + target.d / 2],
        ];
      }
      return [
        [target.x + target.w / 2, target.y],
        [target.x + target.w / 2, target.y + target.d],
      ];
    },
    [],
  );

  const parsePromptToObjects = useCallback(
    (value: string) => {
      const normalized = value.trim().toLowerCase();
      if (!normalized) return [];
      const typeMap: Array<{ keys: string[]; type: SiteObjectType; label: string }> = [
        { keys: ["building", "office", "retail", "industrial", "warehouse", "house"], type: "building", label: "Building" },
        { keys: ["road", "street", "drive", "driveway"], type: "road", label: "Road" },
        { keys: ["parking", "lot", "garage"], type: "parking", label: "Parking" },
        { keys: ["basin", "pond", "detention"], type: "basin", label: "Basin" },
        { keys: ["outfall"], type: "outfall", label: "Outfall" },
        { keys: ["inlet", "catch basin"], type: "inlet", label: "Inlet" },
        { keys: ["sidewalk", "path", "trail"], type: "sidewalk", label: "Path" },
      ];
      const matched = typeMap.filter((item) => item.keys.some((key) => normalized.includes(key)));
      if (!matched.length) return [];
      const colors = ["red", "blue", "green", "white", "black", "gray", "grey", "tan", "brown"];
      const materials = ["brick", "glass", "concrete", "asphalt", "gravel", "metal", "wood"];
      const color = colors.find((c) => normalized.includes(c));
      const material = materials.find((m) => normalized.includes(m));
      const style: Record<string, string> = {};
      if (color) style.color = color;
      if (material) style.material = material;
      const styleLabel = [color, material].filter(Boolean).join(" ");
      return matched.map((item) => ({
        type: item.type,
        label: styleLabel ? `${item.label} — ${styleLabel}` : item.label,
        style: Object.keys(style).length ? style : undefined,
      }));
    },
    [],
  );

  const handleAddObject = useCallback(
    (
      type: SiteObjectType,
      options?: {
        label?: string;
        style?: Record<string, string>;
        geometryType?: "polygon" | "polyline" | "rect";
        placed?: boolean;
      },
    ) => {
      const catalog = SITE_OBJECT_CATALOG[type];
      if (!catalog) return;
      clearGeneratedPreview();
      if (type === "site") {
        const width = parsePositiveNumber(lotWidth) ?? catalog.defaultW;
        const height = parsePositiveNumber(lotHeight) ?? catalog.defaultD;
        if (!parsePositiveNumber(lotWidth)) setLotWidth(String(width));
        if (!parsePositiveNumber(lotHeight)) setLotHeight(String(height));
        setBuildingPlacements((prev) => {
          const filtered = prev.filter((item) => item.type !== "site");
          const sitePlacement: BuildingPlacement = {
            id: `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            label: catalog.label,
            type: "site",
            w: width,
            d: height,
            x: 0,
            y: 0,
            rotation: 0,
            locked: true,
            placed: true,
            source: "user",
            generated: false,
            capabilities: {
              movable: false,
              resizable: false,
              rotatable: false,
              deletable: false,
            },
            systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
            meta: { category: catalog.category },
          };
          return [sitePlacement, ...filtered];
        });
        return;
      }
      if (!hasSiteBoundary()) {
        const ok = ensureSiteBoundary("You can adjust the site size anytime.");
        if (!ok) return;
      }
      const lot = resolveLotBounds();
      const existingCount =
        buildingPlacements.filter((item) => item.type === type).length + 1;
      const defaults =
        type === "building" ? resolveDefaultBuildingDims() : { w: catalog.defaultW, d: catalog.defaultD };
      const defaultHeight = catalog.defaultH ?? 0;
      const autoPlaced = Boolean(options?.placed);
      const autoX =
        type === "basin" || type === "outfall"
          ? Math.max(0, lot.w - defaults.w - 24)
          : Math.min(Math.max(24, existingCount * 24), Math.max(24, lot.w - defaults.w - 24));
      const autoY =
        type === "basin" || type === "outfall"
          ? Math.max(0, lot.h - defaults.d - (type === "outfall" ? 8 : 24))
          : Math.min(Math.max(24, existingCount * 18), Math.max(24, lot.h - defaults.d - 24));
      const parkingStalls =
        type === "parking" ? parsePositiveNumber(parkingCount) ?? 0 : undefined;
      const parkingParams =
        type === "parking"
          ? {
              stallWidth: parsePositiveNumber(parkingStallWidth) ?? 9,
              stallDepth: parsePositiveNumber(parkingStallDepth) ?? 18,
              aisleWidth: parsePositiveNumber(parkingAisleWidth) ?? 24,
              adaAisleWidth: parsePositiveNumber(parkingAdaAisleWidth) ?? 8,
              adaCount: parsePositiveNumber(parkingAdaCount) ?? 0,
              compactCount: parsePositiveNumber(parkingCompactCount) ?? 0,
              compactWidth: parsePositiveNumber(parkingCompactWidth) ?? 8,
              angleDeg: parsePositiveNumber(parkingAngle) ?? 90,
              loading: parkingLoading,
              autoResizeToFitCount: false,
              useMixedAngles: false,
              compactZone: true,
            }
          : null;
      const nextPlacement: BuildingPlacement = {
        id: `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: options?.label ?? formatObjectLabel(type, existingCount),
        type,
        use: catalog.use,
        w: defaults.w,
        d: defaults.d,
        h: defaultHeight,
        x: autoPlaced ? autoX : undefined,
        y: autoPlaced ? autoY : undefined,
        rotation: 0,
        stallCount: parkingStalls,
        locked: false,
        placed: autoPlaced,
        source: "user",
        generated: false,
        capabilities: {
          movable: true,
          resizable: true,
          rotatable: true,
          deletable: true,
        },
        systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
        meta: {
          category: catalog.category,
          ...(parkingParams ? { parkingParams } : {}),
          ...(options?.style ? { style: options.style } : {}),
        },
      };
      if (type === "parking" && parkingParams) {
        const totalStalls = Math.max(
          parkingStalls ?? 0,
          parkingParams.adaCount + parkingParams.compactCount,
        );
        const footprint = computeParkingFootprint(
          nextPlacement,
          parkingParams,
          totalStalls,
        );
        nextPlacement.meta = {
          ...nextPlacement.meta,
          parkingCapacity: footprint.maxStalls,
          parkingModuleCols: footprint.moduleCols,
          parkingModuleRows: footprint.moduleRows,
        };
      }
      if (["road", "driveway", "sidewalk"].includes(type)) {
        nextPlacement.geometryType = "polyline";
        nextPlacement.geometry = buildDefaultPolyline({
          x: 0,
          y: 0,
          w: nextPlacement.w,
          d: nextPlacement.d,
        });
        nextPlacement.capabilities = {
          movable: true,
          resizable: false,
          rotatable: false,
          deletable: true,
        };
      }
      if (options?.geometryType === "polyline") {
        nextPlacement.geometryType = "polyline";
        nextPlacement.geometry = buildDefaultPolyline({
          x: 0,
          y: 0,
          w: nextPlacement.w,
          d: nextPlacement.d,
        });
        nextPlacement.capabilities = {
          movable: true,
          resizable: false,
          rotatable: false,
          deletable: true,
        };
      } else if (options?.geometryType === "polygon") {
        nextPlacement.geometryType = "polygon";
        nextPlacement.geometry = [
          [0, 0],
          [nextPlacement.w, 0],
          [nextPlacement.w * 0.82, nextPlacement.d],
          [nextPlacement.w * 0.18, nextPlacement.d],
        ];
      }
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      setActivePlacementId(nextPlacement.id);
      setPlacementModeEnabled(true);
      setPreviewMode("2d");
      setPreviewInteraction("edit");
      console.debug("[placement] add-object", {
        id: nextPlacement.id,
        type: nextPlacement.type,
        w: nextPlacement.w,
        d: nextPlacement.d,
        placed: nextPlacement.placed,
      });
      debugLog("add-object", {
        id: nextPlacement.id,
        type: nextPlacement.type,
      });
    },
    [
      buildingPlacements,
      clearGeneratedPreview,
      formatObjectLabel,
      hasSiteBoundary,
      askClarification,
      lotHeight,
      lotWidth,
      parkingAisleWidth,
      parkingAngle,
      parkingCount,
      parkingLoading,
      parkingStallDepth,
      parkingStallWidth,
      resolveDefaultBuildingDims,
      resolveLotBounds,
      buildDefaultPolyline,
      computeParkingFootprint,
    ],
  );

  const handlePromptAddObject = useCallback(() => {
    const parsedObjects = parsePromptToObjects(objectPrompt);
    if (!parsedObjects.length) {
      setStatusMessage("Describe a building, road, parking, or basin to add.");
      return;
    }
    parsedObjects.forEach((parsed) => {
      const style = {
        ...(parsed.style ?? {}),
        outline_color: objectOutlineColor,
      };
      handleAddObject(parsed.type, { label: parsed.label, style, placed: true });
    });
    setObjectPrompt("");
  }, [handleAddObject, objectOutlineColor, objectPrompt, parsePromptToObjects, setStatusMessage]);

  const handleUpdateBuilding = useCallback((id: string, updates: Partial<BuildingPlacement>) => {
    clearGeneratedPreview();
    const nextUpdates = { ...updates };
    const target = buildingPlacements.find((item) => item.id === id);
    if (target?.type === "site" && (typeof updates.x === "number" || typeof updates.y === "number")) {
      const currentX = target.x ?? 0;
      const currentY = target.y ?? 0;
      const nextX = typeof updates.x === "number" ? updates.x : currentX;
      const nextY = typeof updates.y === "number" ? updates.y : currentY;
      const deltaX = nextX - currentX;
      const deltaY = nextY - currentY;
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const geocode = currentInput?.meta?.site_inputs?.geocode;
      if (geocode?.lat && geocode?.lng) {
        const metersPerDegLat = 111320;
        const metersPerDegLng = 111320 * Math.cos((geocode.lat * Math.PI) / 180);
        const dxM = deltaX * 0.3048;
        const dyM = -deltaY * 0.3048;
        const nextLat = geocode.lat + dyM / metersPerDegLat;
        const nextLng = geocode.lng + dxM / metersPerDegLng;
        const nextSiteInputs = {
          ...(currentInput?.meta?.site_inputs ?? {}),
          geocode: {
            ...(geocode ?? {}),
            lat: nextLat,
            lng: nextLng,
          },
        };
        void saveProjectRef.current?.({
          silent: true,
          projectInputOverride: {
            ...currentInput,
            input_mode: "user",
            strict_mode: false,
            allow_ai_fill_for_blanks: false,
            meta: {
              ...(currentInput?.meta ?? {}),
              site_inputs: nextSiteInputs,
            },
          },
        });
        setFitToSiteRequest((value) => value + 1);
        nextUpdates.x = 0;
        nextUpdates.y = 0;
      }
    }
    if (typeof updates.x === "number" || typeof updates.y === "number") {
      nextUpdates.placed = true;
    }
    if (
      target?.geometryType &&
      Array.isArray(target.geometry) &&
      (typeof updates.x === "number" || typeof updates.y === "number")
    ) {
      const deltaX = (typeof updates.x === "number" ? updates.x : target.x ?? 0) - (target.x ?? 0);
      const deltaY = (typeof updates.y === "number" ? updates.y : target.y ?? 0) - (target.y ?? 0);
      if (Number.isFinite(deltaX) && Number.isFinite(deltaY)) {
        nextUpdates.geometry = target.geometry.map(([px, py]) => [px + deltaX, py + deltaY]);
      }
    }
    if (target?.type === "custom") {
      const geometryType = isCustomGeometryMode(updates.geometryType ?? target.geometryType)
        ? (updates.geometryType ?? target.geometryType) as CustomGeometryMode
        : undefined;
      const geometry = Array.isArray(nextUpdates.geometry)
        ? nextUpdates.geometry
        : Array.isArray(target.geometry)
          ? target.geometry
          : undefined;
      if (geometryType && geometry?.length) {
        nextUpdates.source = "manual_drawn";
        nextUpdates.generated = false;
        nextUpdates.meta = buildCustomGeometryMeta(
          target.id,
          updates.label ?? target.label,
          geometryType,
          geometry,
          units || "ft",
          target.meta,
        );
      }
    }
    if (target?.type === "parking") {
      const params = resolveParkingParams(target, updates);
      const stallCount = typeof updates.stallCount === "number" ? updates.stallCount : target.stallCount ?? 0;
      const totalStalls = Math.max(stallCount, params.adaCount + params.compactCount);
      const footprint = computeParkingFootprint(target, params, totalStalls);
      nextUpdates.meta = {
        ...(target.meta ?? {}),
        ...(updates.meta ?? {}),
        parkingParams: {
          ...(target.meta as { parkingParams?: ParkingParams })?.parkingParams,
          ...(updates.meta as { parkingParams?: ParkingParams })?.parkingParams,
          ...params,
        },
        parkingCapacity: footprint.maxStalls,
        parkingModuleCols: footprint.moduleCols,
        parkingModuleRows: footprint.moduleRows,
      };
      if (params.autoResizeToFitCount && totalStalls > 0) {
        nextUpdates.w = footprint.w;
        nextUpdates.d = footprint.d;
      }
    }
    setBuildingPlacements((prev) =>
      prev.map((item) => (item.id === id ? { ...item, ...nextUpdates } : item)),
    );
    markSystemsStale(systemsImpactedByPlacement(target));
    setStatusMessage("Object updated. Regenerate systems to reflect the new layout.");
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object update...", track: true });
  }, [
    buildingPlacements,
    clearGeneratedPreview,
    computeParkingFootprint,
    currentProject,
    markSystemsStale,
    payloadPreview,
    resolveParkingParams,
    systemsImpactedByPlacement,
  ]);

  const persistDetectedPlacements = useCallback(
    (nextDetected: BuildingPlacement[]) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        detected_objects: nextDetected,
      };
      void ensureProjectDraftRef.current()
        .then(() => saveProjectRef.current({
          silent: true,
          projectInputOverride: {
            ...currentInput,
            input_mode: "user",
            strict_mode: false,
            allow_ai_fill_for_blanks: false,
            meta: {
              ...(currentInput?.meta ?? {}),
              site_inputs: nextSiteInputs,
            },
          },
        }));
    },
    [currentProject, payloadPreview],
  );

  const handleRemoveBuilding = useCallback((id: string) => {
    clearGeneratedPreview();
    const target = buildingPlacements.find((item) => item.id === id);
    debugLog("remove-object", { id });
    setBuildingPlacements((prev) => prev.filter((item) => item.id !== id));
    setActivePlacementId((prev) => (prev === id ? null : prev));
    setPlacementModeEnabled((prev) => (activePlacementId === id ? false : prev));
    setFocusObjectId((prev) => (prev === id ? null : prev));
    markSystemsStale(systemsImpactedByPlacement(target));
    setStatusMessage("Object removed. Regenerate systems to reflect the new layout.");
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object removal...", track: true });
  }, [activePlacementId, buildingPlacements, clearGeneratedPreview, markSystemsStale, systemsImpactedByPlacement]);

  const handleRestoreBuilding = useCallback((snapshot: BuildingPlacement) => {
    clearGeneratedPreview();
    setBuildingPlacements((prev) => {
      if (prev.some((item) => item.id === snapshot.id)) return prev;
      return [...prev, { ...snapshot }];
    });
    markSystemsStale(systemsImpactedByPlacement(snapshot));
    setStatusMessage("Undo: object restored.");
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => {
        previewRefreshIntentRef.current = {
          reason: "Refreshing preview after undo restore...",
          track: true,
        };
      });
  }, [clearGeneratedPreview, markSystemsStale, systemsImpactedByPlacement]);

  const handleAcceptDetected = useCallback((id: string) => {
    clearGeneratedPreview();
    setDetectedPlacements((prev) => {
      const target = prev.find((item) => item.id === id);
      if (!target) return prev;
      setBuildingPlacements((placements) => [
        ...placements,
        {
          ...target,
          id: `obj_${Math.random().toString(36).slice(2, 9)}`,
          label: target.label.replace("Detected ", ""),
          source: "user_confirmed",
          confirmed: true,
        },
      ]);
      const nextDetected = prev.filter((item) => item.id !== id);
      persistDetectedPlacements(nextDetected);
      return nextDetected;
    });
  }, [clearGeneratedPreview, persistDetectedPlacements]);

  const handleRejectDetected = useCallback((id: string) => {
    clearGeneratedPreview();
    setDetectedPlacements((prev) => {
      const nextDetected = prev.filter((item) => item.id !== id);
      persistDetectedPlacements(nextDetected);
      return nextDetected;
    });
  }, [clearGeneratedPreview, persistDetectedPlacements]);

  const handleToggleBuildingLock = useCallback((id: string) => {
    setBuildingPlacements((prev) =>
      prev.map((item) => (item.id === id ? { ...item, locked: !item.locked } : item)),
    );
  }, []);

  const handlePlaceBuilding = useCallback(
    (position: { x: number; y: number }) => {
      clearGeneratedPreview();
      if (!siteScaleLocked) {
        setStatusMessage("Lock the site boundary before placing buildings.");
        return;
      }
      const lot = resolveLotBounds();
      if (!lot.w || !lot.h) {
        setStatusMessage("Set the site width and height before placing buildings.");
        return;
      }
      const { w, d } = resolveDefaultBuildingDims();
      const clampedX = Math.min(Math.max(position.x, 0), 1);
      const clampedY = Math.min(Math.max(position.y, 0), 1);
      const nextX = lot.x + clampedX * lot.w - w / 2;
      const nextY = lot.y + clampedY * lot.h - d / 2;
      if (!Number.isFinite(nextX) || !Number.isFinite(nextY)) {
        setStatusMessage("Placement failed: invalid coordinates.");
        return;
      }
      const boundedX = Math.min(Math.max(nextX, lot.x), lot.x + lot.w - w);
      const boundedY = Math.min(Math.max(nextY, lot.y), lot.y + lot.h - d);
      console.debug("[placement] place-building", {
        activePlacementId,
        position,
        lot,
        boundedX,
        boundedY,
        w,
        d,
      });
      debugLog("place-building", {
        activePlacementId: activePlacementId ?? null,
        boundedX,
        boundedY,
      });
      if (activePlacementId) {
        const activePlacement = buildingPlacements.find((item) => item.id === activePlacementId);
        setBuildingPlacements((prev) =>
          prev.map((item) =>
            item.id === activePlacementId
              ? {
                  ...item,
                  x: boundedX,
                  y: boundedY,
                  placed: true,
                  geometry:
                    item.geometryType === "polyline"
                      ? buildDefaultPolyline({ x: boundedX, y: boundedY, w: item.w, d: item.d })
                      : item.geometry,
                }
              : item,
          ),
        );
        setActivePlacementId(null);
        markSystemsStale(systemsImpactedByPlacement(activePlacement));
        debugLog("place-building-commit", { id: activePlacementId ?? null });
        setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
        void ensureProjectDraftRef.current()
          .then(() => saveProjectRef.current({ silent: true }))
          .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object placement...", track: true });
        return;
      }
      const nextPlacement: BuildingPlacement = {
        id: `building-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Building ${buildingPlacements.length + 1}`,
        type: "building",
        x: boundedX,
        y: boundedY,
        w,
        d,
        rotation: 0,
        locked: false,
        placed: true,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      console.debug("[placement] place-building-new", {
        id: nextPlacement.id,
        x: nextPlacement.x,
        y: nextPlacement.y,
        w: nextPlacement.w,
        d: nextPlacement.d,
      });
      debugLog("place-building-new", {
        id: nextPlacement.id,
        x: nextPlacement.x,
        y: nextPlacement.y,
      });
      markSystemsStale(systemsImpactedByPlacement(nextPlacement));
      setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
      void ensureProjectDraftRef.current()
        .then(() => saveProjectRef.current({ silent: true }))
        .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object placement...", track: true });
    },
    [
      activePlacementId,
      buildingPlacements.length,
      buildingPlacements,
      clearGeneratedPreview,
      markSystemsStale,
      resolveDefaultBuildingDims,
      resolveLotBounds,
      siteScaleLocked,
      systemsImpactedByPlacement,
    ],
  );

  const handlePlaceObject = useCallback(
    (id: string, position: { x: number; y: number }) => {
      clearGeneratedPreview();
      if (!siteScaleLocked) {
        setStatusMessage("Lock the site boundary before placing objects.");
        return;
      }
      const lot = resolveLotBounds();
      if (!lot.w || !lot.h) {
        const ok = ensureSiteBoundary(
          "Place the object again to drop it on the new site.",
        );
        if (!ok) {
          setStatusMessage("Set the site width and height before placing objects.");
        }
        return;
      }
      const clampedX = Math.min(Math.max(position.x, 0), 1);
      const clampedY = Math.min(Math.max(position.y, 0), 1);
      console.debug("[placement] place-object", {
        id,
        position,
        lot,
        clampedX,
        clampedY,
      });
      debugLog("place-object", { id, clampedX, clampedY });
      const target = buildingPlacements.find((item) => item.id === id);
      setBuildingPlacements((prev) =>
        prev.map((item) => {
          if (item.id !== id) return item;
          const x = lot.x + clampedX * lot.w - item.w / 2;
          const y = lot.y + clampedY * lot.h - item.d / 2;
          if (!Number.isFinite(x) || !Number.isFinite(y)) {
            return { ...item, placed: false };
          }
          const boundedX = Math.min(Math.max(x, lot.x), lot.x + lot.w - item.w);
          const boundedY = Math.min(Math.max(y, lot.y), lot.y + lot.h - item.d);
          console.debug("[placement] place-object-commit", {
            id,
            x: boundedX,
            y: boundedY,
            w: item.w,
            d: item.d,
          });
          debugLog("place-object-commit", { id, x: boundedX, y: boundedY });
          return {
            ...item,
            x: boundedX,
            y: boundedY,
            placed: true,
            geometry:
              item.geometryType === "polyline"
                ? buildDefaultPolyline({ x: boundedX, y: boundedY, w: item.w, d: item.d })
                : item.geometry,
          };
        }),
      );
      setActivePlacementId((prev) => (prev === id ? null : prev));
      setPlacementModeEnabled(false);
      markSystemsStale(systemsImpactedByPlacement(target));
      debugLog("place-object-complete", { id });
      setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
      void ensureProjectDraftRef.current()
        .then(() => saveProjectRef.current({ silent: true }))
        .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object placement...", track: true });
    },
    [
      buildDefaultPolyline,
      buildingPlacements,
      clearGeneratedPreview,
      ensureSiteBoundary,
      markSystemsStale,
      resolveLotBounds,
      siteScaleLocked,
      systemsImpactedByPlacement,
    ],
  );

  const handleCreateSiteBoundary = useCallback(
    (payload: { points: Array<[number, number]> }) => {
      clearGeneratedPreview();
      const validPoints = payload.points.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
      if (validPoints.length < 3) {
        setStatusMessage("Draw at least three points before locking a site boundary.");
        return;
      }
      const xs = validPoints.map((pt) => pt[0]);
      const ys = validPoints.map((pt) => pt[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const width = Math.max(1, maxX - minX);
      const height = Math.max(1, maxY - minY);
      if (width < 10 || height < 10) {
        setStatusMessage("Drawn site boundary is too small. Add a wider boundary or set dimensions manually.");
        return;
      }
      const normalizedGeometry = validPoints.map(([x, y]) => [x - minX, y - minY] as [number, number]);
      const acres = (width * height) / SQFT_PER_ACRE;
      const siteId = `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const nextSite: BuildingPlacement = {
        id: siteId,
        label: "Site Boundary",
        type: "site",
        x: 0,
        y: 0,
        w: Number(width.toFixed(0)),
        d: Number(height.toFixed(0)),
        rotation: 0,
        locked: true,
        placed: true,
        source: "manual_drawn",
        generated: false,
        geometryType: "polygon",
        geometry: normalizedGeometry,
        capabilities: {
          movable: false,
          resizable: false,
          rotatable: false,
          deletable: false,
        },
        systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
        meta: {
          category: "site",
          site_boundary_state: "locked_canonical",
          source: "manual_drawn",
          source_ui_mode: "canvas_draw",
          confidence: "user_drawn_review_required",
          engineering_status: "review_required",
          construction_release_allowed: false,
          units: units || "ft",
          acres: Number(acres.toFixed(3)),
          boundary_vertices: normalizedGeometry.map(([x, y], idx) => ({
            id: `${siteId}-v-${idx + 1}`,
            x,
            y,
            units: units || "ft",
          })),
        },
      };
      const nextPlacements = [
        nextSite,
        ...buildingPlacements.filter((item) => item.type !== "site"),
      ];
      const nextLotWidth = String(nextSite.w);
      const nextLotHeight = String(nextSite.d);
      const siteBoundaryGeometry: NonNullable<SiteInputs["site_boundary_geometry"]> = {
        type: "polygon",
        source: "manual_drawn",
        units: units || "ft",
        engineering_status: "review_required",
        construction_release_allowed: false,
        vertices: normalizedGeometry.map(([x, y]) => ({ x, y, units: units || "ft" })),
        bounds: {
          x: 0,
          y: 0,
          w: nextSite.w,
          h: nextSite.d,
        },
      };
      setLotWidth(nextLotWidth);
      setLotHeight(nextLotHeight);
      setSiteScaleLocked(true);
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setFitToSiteRequest((value) => value + 1);
      setBuildingPlacements(nextPlacements);
      markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
      setStatusMessage(`Site boundary locked at ${nextSite.w.toFixed(0)} ft x ${nextSite.d.toFixed(0)} ft (${acres.toFixed(2)} acres).`);

      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextManualFields = buildManualFields({
        nextSiteName: siteName,
        nextFileName: fileName,
        nextUnits: units,
        nextProjectType: projectType,
        nextLotWidth,
        nextLotHeight,
        nextSetback: setback,
        nextBuildingWidth: buildingWidth,
        nextBuildingDepth: buildingDepth,
        nextBuildingCount: buildingCount,
        nextParkingCount: parkingCount,
        nextMinSlopePct: minSlopePct,
        nextPipeMinSlopePct: pipeMinSlopePct,
        nextMaxParkingSlopePct: maxParkingSlopePct,
        nextMaxRoadGradePct: maxRoadGradePct,
        nextMaxAdaCrossSlopePct: maxAdaCrossSlopePct,
        nextRoads: roads,
        nextGrading: grading,
        nextDrainage: drainage,
        nextUtilities: utilities,
        placementsOverride: nextPlacements,
      });
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        manual_fields: nextManualFields,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: {
            ...(currentInput?.meta?.site_inputs ?? {}),
            site_alignment_locked: true,
            site_boundary_source: "manual_drawn",
            site_boundary_state: "locked_canonical",
            site_boundary_acres: Number(acres.toFixed(3)),
            site_boundary_geometry: siteBoundaryGeometry,
          },
        },
      };
      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              has_result: false,
              latest_result: undefined,
            }
          : project,
      );
      void ensureProjectDraftRef.current()
        .then(() =>
          saveProjectRef.current({
            silent: true,
            projectInputOverride: nextProjectInput,
          }),
        )
        .then(() => {
          previewRefreshIntentRef.current = {
            reason: "Refreshing preview after site boundary draw...",
            track: true,
          };
        });
    },
    [
      buildManualFields,
      buildingCount,
      buildingDepth,
      buildingPlacements,
      buildingWidth,
      clearGeneratedPreview,
      currentProject,
      drainage,
      ensureProjectDraftRef,
      fileName,
      grading,
      markSystemsStale,
      maxAdaCrossSlopePct,
      maxParkingSlopePct,
      maxRoadGradePct,
      minSlopePct,
      parkingCount,
      payloadPreview,
      pipeMinSlopePct,
      projectType,
      roads,
      setback,
      siteName,
      units,
      utilities,
    ],
  );

  const handleCreateCustomGeometry = useCallback(
    (payload: {
      mode: "polyline" | "polygon" | "rect" | "point";
      points: Array<[number, number]>;
      label?: string;
    }) => {
      clearGeneratedPreview();
      if (!siteScaleLocked) {
        setStatusMessage("Lock the site boundary before drawing objects.");
        return;
      }
      const lot = resolveLotBounds();
      if (!lot.w || !lot.h) {
        const ok = ensureSiteBoundary("Draw the geometry again after confirming the site boundary.");
        if (!ok) {
          setStatusMessage("Set the site width and height before drawing geometry.");
        }
        return;
      }
      const validPoints = payload.points
        .map(([x, y]) => [
          Math.min(Math.max(x, 0), lot.w),
          Math.min(Math.max(y, 0), lot.h),
        ] as [number, number])
        .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
      const minRequired = payload.mode === "point" ? 1 : payload.mode === "rect" ? 2 : payload.mode === "polygon" ? 3 : 2;
      if (validPoints.length < minRequired) {
        setStatusMessage("Drawn geometry needs more points before it can be added.");
        return;
      }
      const geometry =
        payload.mode === "rect"
          ? (() => {
              const [a, b] = validPoints;
              const minX = Math.min(a[0], b[0]);
              const maxX = Math.max(a[0], b[0]);
              const minY = Math.min(a[1], b[1]);
              const maxY = Math.max(a[1], b[1]);
              return [
                [minX, minY],
                [maxX, minY],
                [maxX, maxY],
                [minX, maxY],
              ] as Array<[number, number]>;
            })()
          : validPoints;
      const xs = geometry.map((pt) => pt[0]);
      const ys = geometry.map((pt) => pt[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const isLine = payload.mode === "polyline";
      const isPoint = payload.mode === "point";
      const existingCustomCount =
        buildingPlacements.filter((item) => item.type === "custom").length + 1;
      const nextId = `custom-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const nextLabel =
        payload.label ??
        `Custom ${payload.mode === "polyline" ? "Line" : payload.mode === "polygon" ? "Area" : payload.mode === "rect" ? "Rectangle" : "Point"} ${existingCustomCount}`;
      const nextPlacement: BuildingPlacement = {
        id: nextId,
        label: nextLabel,
        type: "custom",
        x: isPoint ? geometry[0][0] - 5 : minX,
        y: isPoint ? geometry[0][1] - 5 : minY,
        w: isPoint ? 10 : Math.max(5, maxX - minX),
        d: isPoint ? 10 : Math.max(5, maxY - minY),
        rotation: 0,
        locked: false,
        placed: true,
        source: "manual_drawn",
        generated: false,
        geometryType: payload.mode,
        geometry,
        capabilities: {
          movable: true,
          resizable: payload.mode === "rect" || payload.mode === "polygon" || payload.mode === "point",
          rotatable: payload.mode === "rect",
          deletable: true,
        },
        systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
        meta: buildCustomGeometryMeta(nextId, nextLabel, payload.mode, geometry, units || "ft"),
      };
      if (isLine) {
        nextPlacement.capabilities = {
          movable: true,
          resizable: false,
          rotatable: false,
          deletable: true,
        };
      }
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      setActivePlacementId(nextPlacement.id);
      setPlacementModeEnabled(false);
      setPreviewMode("2d");
      setPreviewInteraction("edit");
      markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
      setStatusMessage("Custom geometry added as user-authored project geometry. Regenerate systems only after reviewing impacts.");
      void ensureProjectDraftRef.current()
        .then(() => saveProjectRef.current({ silent: true }))
        .then(() => {
          previewRefreshIntentRef.current = {
            reason: "Refreshing preview after custom geometry draw...",
            track: true,
          };
        });
    },
    [
      buildingPlacements,
      clearGeneratedPreview,
      ensureSiteBoundary,
      markSystemsStale,
      resolveLotBounds,
      siteScaleLocked,
      units,
    ],
  );

  const handleSelectPlacementTarget = useCallback((id: string) => {
    const lot = resolveLotBounds();
    if (!lot.w || !lot.h) {
      askClarification(
        "I need a site boundary before placing objects. What size should the site be?",
        "place_object_missing_site",
        { id },
      );
      return;
    }
    setPreviewMode("2d");
    setPreviewInteraction("edit");
    setActivePlacementId(id);
    setPlacementModeEnabled(true);
    const target = buildingPlacements.find((item) => item.id === id);
    console.debug("[placement] select-target", {
      id,
      type: target?.type,
      placed: target?.placed,
    });
    setStatusMessage(
      target
        ? `Ready to place ${target.label}. Click on the canvas to drop it.`
        : "Placement active. Click on the canvas to drop the object.",
    );
  }, [askClarification, buildingPlacements, resolveLotBounds]);

  function askClarification(question: string, action: string, payload?: Record<string, unknown>) {
    setPendingClarification({ action, payload, question });
    setActiveSidePanel("chat");
    setChatCollapsed(false);
    appendChatMessage("assistant", question, "status");
    setStatusMessage(question);
  }

  const scheduleScaleSave = useCallback(
    (ftPerPx: number, source: "mapbox" | "manual" | "approximate") => {
      if (scaleSaveTimeoutRef.current !== null) {
        window.clearTimeout(scaleSaveTimeoutRef.current);
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      scaleSaveTimeoutRef.current = window.setTimeout(() => {
        if (!saveProjectRef.current) return;
        void saveProjectRef.current({
          silent: true,
          projectInputOverride: {
            ...currentInput,
            input_mode: "user",
            strict_mode: false,
            allow_ai_fill_for_blanks: false,
            meta: {
              ...(currentInput?.meta ?? {}),
              site_inputs: {
                ...(currentInput?.meta?.site_inputs ?? {}),
                detection_scale: {
                  distance_ft: detectionScaleFeet ? parsePositiveNumber(detectionScaleFeet) ?? undefined : undefined,
                  pixel_distance: detectionScalePixels ? parsePositiveNumber(detectionScalePixels) ?? undefined : undefined,
                  scale_ft_per_px: ftPerPx,
                  scale_source: source,
                },
                site_alignment_locked: siteScaleLocked,
              },
            },
          },
        });
      }, 600);
    },
    [currentProject, detectionScaleFeet, detectionScalePixels, payloadPreview, siteScaleLocked],
  );

  useEffect(() => {
    const placed = buildingPlacements.filter(
      (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
    );
    console.debug("[placement] state", {
      total: buildingPlacements.length,
      placed: placed.length,
      ids: placed.map((item) => item.id),
    });
  }, [buildingPlacements]);

  useEffect(() => {
    if (buildingPlacements.length > 0) {
      setBuildingCount(String(buildingPlacements.length));
    }
  }, [buildingPlacements.length]);

  const applyControlOverrides = (overrides: ControlOverrides) => {
    if (overrides.projectType) setProjectType(overrides.projectType);
    if (overrides.units) setUnits(overrides.units);
    if (typeof overrides.roads === "boolean") setRoads(overrides.roads);
    if (typeof overrides.grading === "boolean") setGrading(overrides.grading);
    if (typeof overrides.drainage === "boolean") setDrainage(overrides.drainage);
    if (typeof overrides.utilities === "boolean") setUtilities(overrides.utilities);
    if (typeof overrides.siteName === "string") setSiteName(overrides.siteName);
    if (typeof overrides.fileName === "string") setFileName(overrides.fileName);
    if (typeof overrides.lotWidth === "string" || typeof overrides.lotWidth === "number") {
      setLotWidth(String(overrides.lotWidth));
    }
    if (typeof overrides.lotHeight === "string" || typeof overrides.lotHeight === "number") {
      setLotHeight(String(overrides.lotHeight));
    }
    if (typeof overrides.buildingWidth === "string" || typeof overrides.buildingWidth === "number") {
      setBuildingWidth(String(overrides.buildingWidth));
    }
    if (typeof overrides.buildingDepth === "string" || typeof overrides.buildingDepth === "number") {
      setBuildingDepth(String(overrides.buildingDepth));
    }
    if (typeof overrides.buildingCount === "string" || typeof overrides.buildingCount === "number") {
      setBuildingCount(String(overrides.buildingCount));
    }
    if (typeof overrides.setback === "string" || typeof overrides.setback === "number") {
      setSetback(String(overrides.setback));
    }
    if (typeof overrides.parkingCount === "string" || typeof overrides.parkingCount === "number") {
      setParkingCount(String(overrides.parkingCount));
    }
    if (typeof overrides.minSlopePct === "string" || typeof overrides.minSlopePct === "number") {
      setMinSlopePct(String(overrides.minSlopePct));
    }
    if (typeof overrides.pipeMinSlopePct === "string" || typeof overrides.pipeMinSlopePct === "number") {
      setPipeMinSlopePct(String(overrides.pipeMinSlopePct));
    }
    if (typeof overrides.maxParkingSlopePct === "string" || typeof overrides.maxParkingSlopePct === "number") {
      setMaxParkingSlopePct(String(overrides.maxParkingSlopePct));
    }
    if (typeof overrides.maxRoadGradePct === "string" || typeof overrides.maxRoadGradePct === "number") {
      setMaxRoadGradePct(String(overrides.maxRoadGradePct));
    }
    if (typeof overrides.maxAdaCrossSlopePct === "string" || typeof overrides.maxAdaCrossSlopePct === "number") {
      setMaxAdaCrossSlopePct(String(overrides.maxAdaCrossSlopePct));
    }
  };

  const buildChatDecisionContext = (
    overrides: ControlOverrides = {},
    message: string,
  ) => {
    const liveThread = chatMessagesRef.current;
    const designMemory = extractDesignMemory(liveThread);
    const storedMemory =
      currentProject?.project_input?.meta?.chat_memory &&
      typeof currentProject.project_input.meta.chat_memory === "object"
        ? currentProject.project_input.meta.chat_memory
        : null;
    const mergedPreferences = [
      ...toArray((storedMemory as { preferences?: string[] } | null)?.preferences),
      ...designMemory.preferences,
    ].slice(-8);
    const mergedConstraints = [
      ...toArray((storedMemory as { constraints?: string[] } | null)?.constraints),
      ...designMemory.constraints,
    ].slice(-8);
    return {
      strategy_mode: assistedEnabled ? "assisted" : "user",
      site_name: overrides.siteName ?? siteName,
      file_name: overrides.fileName ?? fileName,
      project_type: overrides.projectType ?? projectType,
      units: overrides.units ?? units,
      lot_width: overrides.lotWidth ?? lotWidth,
      lot_height: overrides.lotHeight ?? lotHeight,
      building_width: overrides.buildingWidth ?? buildingWidth,
      building_depth: overrides.buildingDepth ?? buildingDepth,
      setback: overrides.setback ?? setback,
      building_count: overrides.buildingCount ?? buildingCount,
      parking_count: overrides.parkingCount ?? parkingCount,
      min_slope_pct: overrides.minSlopePct ?? minSlopePct,
      pipe_min_slope_pct: overrides.pipeMinSlopePct ?? pipeMinSlopePct,
      max_parking_slope_pct: overrides.maxParkingSlopePct ?? maxParkingSlopePct,
      max_road_grade_pct: overrides.maxRoadGradePct ?? maxRoadGradePct,
      max_ada_cross_slope_pct: overrides.maxAdaCrossSlopePct ?? maxAdaCrossSlopePct,
      roads: overrides.roads ?? roads,
      grading: overrides.grading ?? grading,
      drainage: overrides.drainage ?? drainage,
      utilities: overrides.utilities ?? utilities,
      has_plan: Boolean(backendResult?.final_plan),
      has_preview: Boolean(planPreviewUrl),
      current_project: currentProject
        ? {
            project_id: currentProject.project_id,
            name: currentProject.name,
          }
        : null,
      current_explanation: currentExplanation,
      current_truth_audit: currentTruthAudit,
      engineering_status: currentPlanMeta?.engineering_status ?? {},
      convergence_summary: currentPlanMeta?.convergence_summary ?? {},
      manual_failures: currentManualFailures,
      assumptions,
      produced_deliverables: Array.isArray(currentPlanMeta?.deliverables?.produced)
        ? currentPlanMeta.deliverables.produced
        : [],
      issues,
      memory_summary: {
        preferences: mergedPreferences,
        constraints: mergedConstraints,
        open_questions: toArray((storedMemory as { open_questions?: string[] } | null)?.open_questions).slice(-6),
        examples: [...mergedPreferences, ...mergedConstraints].slice(-8),
      },
      current_phase:
        String(visibleActiveJob?.stage || "") ||
        String((currentPlanMeta?.runtime_phase_checkpoint as { stage_name?: string } | undefined)?.stage_name || ""),
      current_phase_detail: String(visibleActiveJob?.stage_detail || ""),
      chat_thread: [
        ...liveThread,
        createChatMessage("user", message),
      ].map(({ role, content, kind }) => ({ role, content, kind })),
    };
  };

  const buildPayloadFromOverrides = (
    overrides: ControlOverrides = {},
    promptOverride?: string,
    projectIdOverride?: string | null,
    placementsOverride?: BuildingPlacement[],
  ): PlanRequestPayload => {
    const nextSiteName = overrides.siteName ?? siteName;
    const nextFileName = overrides.fileName ?? fileName;
    const nextUnits = overrides.units ?? units;
    const nextProjectType = overrides.projectType ?? projectType;
    const nextRoads = overrides.roads ?? roads;
    const nextGrading = overrides.grading ?? grading;
    const nextDrainage = overrides.drainage ?? drainage;
    const nextUtilities = overrides.utilities ?? utilities;
    const nextBuildingCount = overrides.buildingCount ?? buildingCount;
    const nextMinSlopePct = overrides.minSlopePct ?? minSlopePct;
    const nextPipeMinSlopePct = overrides.pipeMinSlopePct ?? pipeMinSlopePct;
    const nextMaxParkingSlopePct = overrides.maxParkingSlopePct ?? maxParkingSlopePct;
    const nextMaxRoadGradePct = overrides.maxRoadGradePct ?? maxRoadGradePct;
    const nextMaxAdaCrossSlopePct = overrides.maxAdaCrossSlopePct ?? maxAdaCrossSlopePct;

    return {
      project_id:
        projectIdOverride !== undefined ? projectIdOverride : projectId || null,
      full_design_mode: true,
      input_mode: assistedEnabled ? "assisted" : "user",
      strict_mode: false,
      prompt_text: (promptOverride ?? prompt) || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
        system_dirty_state: systemStatuses,
        reactive_edit_policy_preference: REACTIVE_EDIT_POLICY_PREFERENCE,
        site_object_id: buildingPlacements.find((item) => item.type === "site")?.id ?? null,
        assisted_enabled: assistedEnabled,
      },
      manual_fields: buildManualFields({
        nextSiteName,
        nextFileName,
        nextUnits,
        nextProjectType,
        nextLotWidth: overrides.lotWidth ?? lotWidth,
        nextLotHeight: overrides.lotHeight ?? lotHeight,
        nextSetback: overrides.setback ?? setback,
        nextBuildingWidth: overrides.buildingWidth ?? buildingWidth,
        nextBuildingDepth: overrides.buildingDepth ?? buildingDepth,
        nextBuildingCount,
        nextParkingCount: overrides.parkingCount ?? parkingCount,
        nextMinSlopePct,
        nextPipeMinSlopePct,
        nextMaxParkingSlopePct,
        nextMaxRoadGradePct,
        nextMaxAdaCrossSlopePct,
        nextRoads,
        nextGrading,
        nextDrainage,
        nextUtilities,
        placementsOverride,
      }),
      allow_ai_fill_for_blanks: assistedEnabled,
    };
  };

  const withReactiveRerunContext = useCallback(
    (
      requestPayload: PlanRequestPayload,
      requestedSystem: "roads" | "parking" | "grading" | "drainage" | "utilities" | "full",
    ): PlanRequestPayload => {
      if (requestedSystem === "full") return requestPayload;
      const checkpointFinalPlan = backendResult?.final_plan;
      if (!checkpointFinalPlan || typeof checkpointFinalPlan !== "object") {
        return requestPayload;
      }
      const changedSystems = Object.entries(systemStatuses)
        .filter(([system, status]) => status === "stale" && system in REACTIVE_SYSTEM_STAGE_MAP)
        .map(([system]) => system as keyof typeof REACTIVE_SYSTEM_STAGE_MAP);
      if (!changedSystems.includes(requestedSystem)) {
        changedSystems.push(requestedSystem);
      }
      const changedTargets = Array.from(
        new Set(
          changedSystems.flatMap((system) => REACTIVE_SYSTEM_STAGE_MAP[system] ?? []),
        ),
      );
      if (!changedTargets.length) return requestPayload;

      const existingMeta = (requestPayload.meta ?? {}) as Record<string, unknown>;
      const existingOrchestratorMeta =
        existingMeta.orchestrator_meta && typeof existingMeta.orchestrator_meta === "object"
          ? (existingMeta.orchestrator_meta as Record<string, unknown>)
          : {};
      const existingRuntimeResume =
        existingOrchestratorMeta.runtime_resume &&
        typeof existingOrchestratorMeta.runtime_resume === "object"
          ? (existingOrchestratorMeta.runtime_resume as Record<string, unknown>)
          : {};

      return {
        ...requestPayload,
        meta: {
          ...existingMeta,
          requested_system: requestedSystem,
          changed_targets: changedTargets,
          stale_outputs: changedTargets,
          reactive_checkpoint_final_plan: checkpointFinalPlan,
          reactive_partial_rerun_request: {
            enabled: true,
            requested_system: requestedSystem,
            checkpoint_attached: true,
            changed_targets: changedTargets,
          },
          orchestrator_meta: {
            ...existingOrchestratorMeta,
            runtime_resume: {
              ...existingRuntimeResume,
              final_plan: checkpointFinalPlan,
              reactive_checkpoint_source: "web_current_backend_result",
            },
          },
        },
      };
    },
    [backendResult?.final_plan, systemStatuses],
  );

  const isConnectivityFailureMessage = (message: string) =>
    message.includes("could not reach the backend") ||
    message.includes("Failed to fetch") ||
    message.includes("Load failed") ||
    message.includes("NetworkError");

  const executePlanAction = async ({
    mode,
    requestPayload,
    resolvedProjectId,
    assistantPrefix,
    clearPromptOnSuccess = false,
    signal,
    timeoutMs,
    allowQueueFallback = true,
  }: {
    mode: PlanToolMode;
    requestPayload: PlanRequestPayload;
    resolvedProjectId?: string | null;
    assistantPrefix?: string | null;
    clearPromptOnSuccess?: boolean;
    signal?: AbortSignal;
    timeoutMs?: number;
    allowQueueFallback?: boolean;
  }) => {
    setBusy(true);
    setActivePlanTool(mode);
    setStatusMessage(
      mode === "fix"
        ? "Civora AI is starting the fix run."
        : mode === "improve"
          ? "Civora AI is starting the improvement run."
          : "Civora AI is starting the engineering run.",
    );
    const shouldQueueStagedRun = Boolean(requestPayload?.full_design_mode && token);
    if (shouldQueueStagedRun) {
      try {
        const queued = await postJson<{ job: JobSummary }>(
          "/api/jobs/orchestrate",
          {
            project_id:
              resolvedProjectId !== undefined
                ? resolvedProjectId
                : ((requestPayload?.project_id ?? projectId) || null),
            request: requestPayload,
          },
          { token },
        );
        setActiveJobId(queued.job.job_id);
        appendChatMessage(
          "assistant",
          [
            assistantPrefix,
            `I queued the full staged design workflow as ${queued.job.job_id} so each phase can save, pause for approval, and continue on the same project.`,
          ]
            .filter(Boolean)
            .join(" "),
          "status",
        );
        setStatusMessage(`Queued staged run ${queued.job.job_id}.`);
        if (clearPromptOnSuccess) {
          setPrompt("");
        }
        return;
      } catch (queueError) {
        const queueMessage =
          queueError instanceof Error ? queueError.message : "Job queue failed.";
        appendChatMessage("assistant", queueMessage, "status");
        setStatusMessage(queueMessage);
        return;
      } finally {
        setBusy(false);
      }
    }
    const liveRunController = new AbortController();
    const liveRunTimeoutMs = typeof timeoutMs === "number" ? timeoutMs : 12_000;
    let timedOut = false;
    const handleAbort = () => liveRunController.abort();
    signal?.addEventListener("abort", handleAbort, { once: true });
    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      liveRunController.abort();
    }, liveRunTimeoutMs);
    try {
      const data = await postJson<PlanResponse>("/api/orchestrate", requestPayload, {
        token,
        signal: liveRunController.signal,
      });
      applyBackendResult(data);
      appendChatMessage(
        "assistant",
        [assistantPrefix, summarizePlanResponse(data, mode)].filter(Boolean).join(" "),
      );
      await requestPreview(
        {
          project_id: projectId || currentProject?.project_id || null,
          result: data,
          filename_stem: fileName || siteName || "civora-ai-plan",
        },
        { silent: true },
      );
      setStatusMessage(
        mode === "fix"
          ? "Civora AI ran a focused fix pass."
          : mode === "improve"
            ? "Civora AI generated an improved plan."
            : "Plan run completed.",
      );
      if (clearPromptOnSuccess) {
        setPrompt("");
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "";
      if (timedOut && token && allowQueueFallback) {
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id:
                resolvedProjectId !== undefined
                  ? resolvedProjectId
                  : ((requestPayload?.project_id ?? projectId) || null),
              request: requestPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            [
              assistantPrefix,
              "The live run took too long to stay on the direct connection, so I queued it in the background instead.",
              `Job ${queued.job.job_id} is now running and I’ll pick it up when it finishes.`,
            ]
              .filter(Boolean)
              .join(" "),
            "status",
          );
          setStatusMessage(
            `The live run was queued as ${queued.job.job_id} because the direct request took too long.`,
          );
          return;
        } catch (queueError) {
          const queueMessage =
            queueError instanceof Error ? queueError.message : "Job queue failed.";
          appendChatMessage("assistant", queueMessage, "status");
          setStatusMessage(queueMessage);
          return;
        }
      }
      if (error instanceof Error && error.name === "AbortError") {
        appendChatMessage(
          "assistant",
          "I stopped the live request before it finished.",
          "status",
        );
        setStatusMessage("Cancelled the live request.");
        return;
      }
      const looksLikeConnectivityFailure = isConnectivityFailureMessage(errorMessage);
      if (looksLikeConnectivityFailure && token && allowQueueFallback) {
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id:
                resolvedProjectId !== undefined
                  ? resolvedProjectId
                  : ((requestPayload?.project_id ?? projectId) || null),
              request: requestPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            [
              assistantPrefix,
              "The live run took too long to stay on the direct connection, so I queued it in the background instead.",
              `Job ${queued.job.job_id} is now running and I’ll pick it up when it finishes.`,
            ]
              .filter(Boolean)
              .join(" "),
            "status",
          );
          setStatusMessage(
            `The live run was queued as ${queued.job.job_id} because the direct request took too long.`,
          );
          return;
        } catch (queueError) {
          const queueMessage =
            queueError instanceof Error ? queueError.message : "Job queue failed.";
          appendChatMessage(
            "assistant",
            queueMessage,
            "status",
          );
          setStatusMessage(queueMessage);
          return;
        }
      }
      appendChatMessage(
        "assistant",
        error instanceof Error
          ? error.message
          : mode === "fix"
            ? "I couldn’t complete the fix pass."
            : mode === "improve"
              ? "I couldn’t complete the improvement pass."
              : "I couldn’t update the design.",
        "status",
      );
      setStatusMessage(
        error instanceof Error
          ? error.message
          : mode === "fix"
            ? "Fix pass failed."
            : mode === "improve"
              ? "Improve pass failed."
              : "Planner run failed.",
      );
    } finally {
      window.clearTimeout(timeoutId);
      signal?.removeEventListener("abort", handleAbort);
      setBusy(false);
      setActivePlanTool("run");
      directRunAbortRef.current = null;
    }
  };

  const runOrchestrator = async (mode: PlanToolMode = "run") => {
    if (!token) return;
    if (
      runSubmissionRef.current ||
      Boolean(
        currentProjectActiveJob &&
          ["queued", "running", "awaiting_approval", "cancelling"].includes(
            String(currentProjectActiveJob.status || "").toLowerCase(),
          ),
      )
    ) {
      setStatusMessage("Civora AI is already working on your last request.");
      return;
    }
    const trimmedPrompt = prompt.trim();
    if (mode === "run" && !trimmedPrompt && !imageName) {
      setStatusMessage("Add a request or image so Civora AI has something to work from.");
      return;
    }
    if (mode !== "run") {
      if (mode === "fix") {
        appendChatMessage(
          "system",
          "Fix the active design and focus on the most important engineering blockers.",
          "action",
        );
      } else if (mode === "improve") {
        appendChatMessage(
          "system",
          "Improve the active design while preserving the current project intent.",
          "action",
        );
      }
      const basePayload = buildPayloadFromOverrides({}, undefined, projectId || null);
      await executePlanAction({
        mode,
        requestPayload: {
          ...basePayload,
          full_design_mode: true,
          optimize_goal:
            mode === "fix"
              ? suggestedImproveGoal ?? "reduce_pipe_length"
              : suggestedImproveGoal,
          meta: {
            ...(basePayload.meta ?? {}),
            requested_plan_tool: mode,
          },
        },
        resolvedProjectId: projectId || null,
      });
      return;
    }

    const runController = new AbortController();
    directRunAbortRef.current = runController;
    runSubmissionRef.current = true;
    setBusy(true);
    setActivePlanTool("run");
    setPrompt("");
    appendChatMessage("user", trimmedPrompt);
    setStatusMessage("Civora AI is reviewing your request and starting the design run.");
    try {
      const resolvedProjectId =
        ((await ensureProjectDraft()) ?? projectId) || null;
      const decision = await postJson<ChatDecisionResponse>(
        "/api/chat/decide",
        {
          message: trimmedPrompt,
          context: buildChatDecisionContext({}, trimmedPrompt),
        },
        { token, signal: runController.signal },
      );
      const overrides = decision.control_overrides ?? {};
      applyControlOverrides(overrides);
      const shouldAutoName = false;
      const shouldAutoFileName = false;
      const generatedTitle = siteName.trim();
      const generatedFileName = fileName.trim();

      const isChatOnlyDecision =
        decision.needs_clarification ||
        decision.intent === "conversation" ||
        decision.intent === "settings" ||
        decision.intent === "explain" ||
        (decision.run_mode === "none" && !decision.design_prompt);

      if (isChatOnlyDecision) {
        const chatMetadata = decision.response_metadata ?? {};
        const uiPanel = chatMetadata.ui_navigation_target;
        const uiMode = chatMetadata.requested_ui_mode;
        const validPanels: SidePanelKey[] = [
          "projects", "dashboard", "model", "site_existing", "import_survey", "objects", "generate", "grading", "drainage", "sanitary", "water", "utilities", "roadway", "landscape", "details", "layers", "analysis", "reports", "quantities", "deliverables", "files", "standards", "libraries", "data", "settings", "chat", "system_grading", "system_storm", "system_sanitary", "system_water", "system_roadway", "system_utilities", "system_landscape",
        ];
        const validModes: WorkspaceMode[] = ["dashboard", "setup", "canvas", "layers", "review", "deliver", "data", "settings"];
        if (uiMode && validModes.includes(uiMode as WorkspaceMode)) {
          setActiveWorkspaceMode(uiMode as WorkspaceMode);
        }
        if (uiPanel && validPanels.includes(uiPanel as SidePanelKey)) {
          setActiveSidePanel(uiPanel as SidePanelKey);
        }
        if (chatMetadata.requested_preview_mode === "2d" || chatMetadata.requested_preview_mode === "3d") {
          setPreviewMode(chatMetadata.requested_preview_mode);
        }
        if (chatMetadata.requested_preview_quality === "standard" || chatMetadata.requested_preview_quality === "high") {
          setPreviewQuality(chatMetadata.requested_preview_quality);
        }
        if (chatMetadata.requested_site_lock_state) {
          setActiveWorkspaceMode("setup");
          setActiveSidePanel("site_existing");
        }
        appendChatMessage(
          "assistant",
          decision.intent === "explain" && !decision.assistant_message
            ? "I can explain the current design once there’s a plan in the workspace."
            : decision.assistant_message,
          decision.intent === "explain" ? "explanation" : "message",
        );
        setStatusMessage(
          decision.needs_clarification
            ? "Civora AI is asking for a little more detail before running a design."
            : "Civora AI responded in chat without rerunning the planner.",
        );
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        setBusy(false);
        setActivePlanTool("run");
        return;
      }

      const resolvedMode: PlanToolMode =
        decision.run_mode === "fix"
          ? "fix"
          : decision.run_mode === "improve"
            ? "improve"
            : "run";

      if (resolvedMode !== "run") {
        const basePayload = buildPayloadFromOverrides(overrides, undefined, resolvedProjectId);
        await executePlanAction({
          mode: resolvedMode,
          requestPayload: {
            ...basePayload,
            full_design_mode: true,
            optimize_goal:
              resolvedMode === "fix"
                ? suggestedImproveGoal ?? "reduce_pipe_length"
                : suggestedImproveGoal,
            meta: {
              ...(basePayload.meta ?? {}),
              requested_plan_tool: resolvedMode,
              chat_decision_reason: decision.reason,
              chat_command: decision.response_metadata ?? null,
            },
          },
          resolvedProjectId,
          assistantPrefix: decision.assistant_message,
          clearPromptOnSuccess: true,
          signal: runController.signal,
        });
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        return;
      }

      if (!decision.design_prompt && !imageName) {
        appendChatMessage(
          "assistant",
          decision.assistant_message || "Tell me what you want me to design or change.",
        );
        setStatusMessage(
          "Civora AI needs a little more direction before generating a design.",
        );
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        setBusy(false);
        setActivePlanTool("run");
        return;
      }

      const basePayload = buildPayloadFromOverrides(
        overrides,
        decision.design_prompt || trimmedPrompt,
        resolvedProjectId,
      );
      await executePlanAction({
        mode: "run",
        requestPayload: {
          ...basePayload,
          meta: {
            ...(basePayload.meta ?? {}),
            chat_decision_reason: decision.reason,
            chat_decision_confidence: decision.confidence,
            chat_command: decision.response_metadata ?? null,
          },
        },
        resolvedProjectId,
        assistantPrefix: decision.assistant_message,
        clearPromptOnSuccess: true,
        signal: runController.signal,
      });
      await saveProject({
        silent: true,
        projectIdOverride: resolvedProjectId,
        nameOverride: generatedTitle || undefined,
        fileNameOverride: generatedFileName || undefined,
        autoNamedOverride: shouldAutoName,
        autoFileNamedOverride: shouldAutoFileName,
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "";
      if (error instanceof Error && error.name === "AbortError") {
        appendChatMessage(
          "assistant",
          "I stopped the live request before it finished.",
          "status",
        );
        setStatusMessage("Cancelled the live request.");
        setBusy(false);
        setActivePlanTool("run");
        directRunAbortRef.current = null;
        return;
      }
      if (token && isConnectivityFailureMessage(errorMessage)) {
        try {
          const resolvedProjectId =
            projectId || (await ensureProjectDraft()) || null;
          const fallbackPayload = buildPayloadFromOverrides(
            {},
            trimmedPrompt,
            resolvedProjectId,
          );
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id: resolvedProjectId,
              request: fallbackPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            `The live request could not stay connected long enough to finish the first pass, so I queued it in the background instead. Job ${queued.job.job_id} is queued and I’ll pick it up when it starts reporting progress.`,
            "status",
          );
          setStatusMessage(
            `The live request was queued as ${queued.job.job_id} because the direct connection dropped.`,
          );
          return;
        } catch (queueError) {
          appendChatMessage(
            "assistant",
            queueError instanceof Error ? queueError.message : "I couldn’t queue the design request either.",
            "status",
          );
          setStatusMessage(
            queueError instanceof Error ? queueError.message : "Queued fallback failed.",
          );
          return;
        }
      }
      appendChatMessage(
        "assistant",
        error instanceof Error ? error.message : "I couldn’t process that message.",
        "status",
      );
      setStatusMessage(
        error instanceof Error ? error.message : "Civora AI could not process that message.",
      );
      setBusy(false);
      setActivePlanTool("run");
    } finally {
      runSubmissionRef.current = false;
      directRunAbortRef.current = null;
    }
  };

  const tryHandleObjectIntent = (message: string): boolean => {
    const lower = message.toLowerCase();
    const lot = resolveLotBounds();
    const addBuildingMatch = lower.match(
      /(add|create|place)\s+(a\s+)?building[^0-9]*?(\d+(\.\d+)?)\s*(ft|feet|')?\s*(x|by)\s*(\d+(\.\d+)?)/,
    );
    const addObjectMatch = lower.match(
      /(add|create|place)\s+(a\s+)?(retail building|multifamily building|industrial building|office building|pad|pool|amenity area|open space|entrance|access point|driveway|road|drive aisle|parking field|parking|sidewalk|path|basin|detention pond|outfall|inlet|manhole|hydrant|setback zone|no-build zone|utility corridor|lot block|subdivision block|bridge)\s*(\d+(\.\d+)?)?\s*(ft|feet|')?\s*(x|by)?\s*(\d+(\.\d+)?)?/,
    );
    const plotDimsMatch = lower.match(
      /(add|create|set)\s+(a\s+)?(lot|plot|site)[^0-9]*?(\d+(\.\d+)?)\s*(ft|feet|')?\s*(x|by)\s*(\d+(\.\d+)?)/,
    );
    const plotAcreMatch = lower.match(/(add|create|set)\s+(a\s+)?(\d+(\.\d+)?)\s*acre/);

    if (addBuildingMatch) {
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add buildings at scale.",
          "status",
        );
        return true;
      }
      const width = Number(addBuildingMatch[3]);
      const depth = Number(addBuildingMatch[7]);
      if (!Number.isFinite(width) || !Number.isFinite(depth)) {
        return false;
      }
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `building-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Building ${buildingPlacements.length + 1}`,
        type: "building",
        w: width,
        d: depth,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      appendChatMessage(
        "assistant",
        `Added a ${width} ft by ${depth} ft building to the placement tray. Use placement mode to drop it on the site or auto-place it.`,
        "status",
      );
      return true;
    }
    if (addObjectMatch) {
      const rawType = addObjectMatch[3];
      if (!rawType) return false;
      const typeMap: Record<string, SiteObjectType> = {
        "retail building": "retail_building",
        "multifamily building": "multifamily_building",
        "industrial building": "industrial_building",
        "office building": "office_building",
        pad: "pad",
        pool: "pool",
        "amenity area": "amenity",
        "open space": "open_space",
        entrance: "entrance",
        "access point": "entrance",
        driveway: "driveway",
        road: "road",
        "drive aisle": "road",
        "parking field": "parking",
        parking: "parking",
        sidewalk: "sidewalk",
        path: "sidewalk",
        basin: "basin",
        "detention pond": "basin",
        outfall: "outfall",
        inlet: "inlet",
        manhole: "manhole",
        hydrant: "hydrant",
        "setback zone": "setback_zone",
        "no-build zone": "no_build_zone",
        "utility corridor": "utility_corridor",
        "lot block": "lot_block",
        "subdivision block": "lot_block",
        bridge: "bridge",
      };
      const typeKey = typeMap[rawType];
      if (!typeKey) return false;
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add that object at scale.",
          "status",
        );
        return true;
      }
      const width = addObjectMatch[4] ? Number(addObjectMatch[4]) : null;
      const depth = addObjectMatch[8] ? Number(addObjectMatch[8]) : null;
      appendChatMessage("user", message);
      const catalog = SITE_OBJECT_CATALOG[typeKey];
      const nextPlacement: BuildingPlacement = {
        id: `${typeKey}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: formatObjectLabel(
          typeKey,
          buildingPlacements.filter((item) => item.type === typeKey).length + 1,
        ),
        type: typeKey,
        use: catalog?.use,
        w: width && Number.isFinite(width) ? width : catalog?.defaultW ?? 40,
        d: depth && Number.isFinite(depth) ? depth : catalog?.defaultD ?? 40,
        rotation: 0,
        locked: false,
        placed: false,
        meta: { category: catalog?.category },
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      appendChatMessage(
        "assistant",
        `Added ${nextPlacement.label} to the placement tray. Place it on the canvas when you're ready.`,
        "status",
      );
      return true;
    }
    const addBasinMatch = lower.match(
      /(add|create|place)\s+(a\s+)?(basin|detention)\s*(\d+(\.\d+)?)?\s*(ft|feet|')?\s*(x|by)?\s*(\d+(\.\d+)?)?/,
    );
    if (addBasinMatch) {
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add a basin at scale.",
          "status",
        );
        return true;
      }
      const width = addBasinMatch[4] ? Number(addBasinMatch[4]) : 80;
      const depth = addBasinMatch[8] ? Number(addBasinMatch[8]) : 60;
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `basin-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Basin ${buildingPlacements.length + 1}`,
        type: "basin",
        w: Number.isFinite(width) ? width : 80,
        d: Number.isFinite(depth) ? depth : 60,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      appendChatMessage(
        "assistant",
        `Added a basin object to the placement tray. You can place it manually or auto-place it.`,
        "status",
      );
      return true;
    }
    const addEntranceMatch = lower.match(/(add|create|place)\s+(an?\s+)?entrance/);
    if (addEntranceMatch) {
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add an entrance anchor.",
          "status",
        );
        return true;
      }
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `entrance-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Entrance ${buildingPlacements.length + 1}`,
        type: "entrance",
        w: 20,
        d: 20,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      appendChatMessage(
        "assistant",
        "Added an entrance object to the placement tray. Place it on the canvas when ready.",
        "status",
      );
      return true;
    }
    if (plotDimsMatch) {
      const width = Number(plotDimsMatch[4]);
      const height = Number(plotDimsMatch[8]);
      if (!Number.isFinite(width) || !Number.isFinite(height)) {
        return false;
      }
      appendChatMessage("user", message);
      setLotWidth(String(width));
      setLotHeight(String(height));
      appendChatMessage(
        "assistant",
        `Set the site boundary to ${width} ft by ${height} ft.`,
        "status",
      );
      return true;
    }

    if (plotAcreMatch) {
      const acres = Number(plotAcreMatch[3]);
      if (!Number.isFinite(acres)) {
        return false;
      }
      appendChatMessage("user", message);
      const area = acres * 43560;
      const side = Math.sqrt(area);
      const width = Math.round(side);
      const height = Math.round(side);
      setLotWidth(String(width));
      setLotHeight(String(height));
      appendChatMessage(
        "assistant",
        `Set the site boundary to about ${width} ft by ${height} ft to match ${acres} acres.`,
        "status",
      );
      return true;
    }

    return false;
  };

  const tryHandleInfoIntent = (message: string): boolean => {
    const normalized = message.toLowerCase();
    const placed = buildingPlacements.filter((item) => item.placed);
    const unplaced = buildingPlacements.filter((item) => !item.placed);
    const selected = activePlacementId
      ? buildingPlacements.find((item) => item.id === activePlacementId)
      : null;

    const formatPlacement = (item: BuildingPlacement) => {
      const dims = `${item.w} ft x ${item.d} ft`;
      const position =
        item.placed && typeof item.x === "number" && typeof item.y === "number"
          ? `@ ${Math.round(item.x)} ft, ${Math.round(item.y)} ft`
          : "unplaced";
      const lockTag = item.locked ? "locked" : "unlocked";
      return `${item.label} (${item.type ?? "building"}, ${dims}, ${position}, ${lockTag})`;
    };

    if (/(what(’|')?s on the site|what is on the site|placed objects|site objects)/i.test(normalized)) {
      if (!placed.length) {
        appendChatMessage("assistant", "No objects are placed on the site yet.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Placed objects:\n${placed.map(formatPlacement).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(unplaced|in the tray|not placed)/i.test(normalized)) {
      if (!unplaced.length) {
        appendChatMessage("assistant", "All current objects are placed on the site.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Unplaced objects:\n${unplaced.map(formatPlacement).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(selected|current selection|what is selected)/i.test(normalized)) {
      if (!selected) {
        appendChatMessage("assistant", "Nothing is selected right now.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Selected object: ${formatPlacement(selected)}`,
        "status",
      );
      return true;
    }

    if (/(what should i do next|what next|next step|where should i start|what do i do next)/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        `${nextSetupAction} Everything remains review-required; Civora does not stamp, seal, sign, submit, approve construction, or act as engineer of record.`,
        "status",
      );
      return true;
    }

    if (/(why.*export|can(?:not|'t) export|export.*blocked|why.*download)/i.test(normalized)) {
      const reason = getExportBlockReason();
      const blockerText = previewBlockedReasons.length
        ? ` Current export/review blockers: ${previewBlockedReasons.slice(0, 3).join("; ")}.`
        : "";
      appendChatMessage(
        "assistant",
        reason
          ? `Export is blocked: ${reason}.${blockerText}`
          : `Exports are available only as engineer-review packages. Construction release remains blocked unless an external licensed engineer approves it.${blockerText}`,
        "status",
      );
      return true;
    }

    if (/(stamp|seal|sign|submit|construction[- ]ready|approve.*construction|engineer of record)/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        "Civora cannot stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record. I can prepare review evidence packages, calculations, reports, exports, assumptions, blockers, and traceability for a licensed engineer or the user to review.",
        "status",
      );
      return true;
    }

    if (/(issues|conflicts|problems)/i.test(normalized)) {
      if (!issues.length) {
        appendChatMessage("assistant", "No issues are reported on the latest run.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Issues:\n${issues.slice(0, 6).map((item) => `- ${item.message}`).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(blocked|why.*(drainage|utilities|grading))/i.test(normalized)) {
      if (!previewBlockedReasons.length) {
        appendChatMessage("assistant", "No blockers are currently recorded.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Current blockers:\n${previewBlockedReasons.map((reason) => `- ${reason}`).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(drainage stats|storm stats|pipe length|metrics|quantities)/i.test(normalized)) {
      if (!totalPipeLength && !maxSlope && !minSlope && !flowCfs && !cutFillNet && !basinSize) {
        appendChatMessage("assistant", "Drainage stats are not available yet.", "status");
        return true;
      }
      const metricLines = [
        totalPipeLength ? `Total pipe length: ${formatMetric(totalPipeLength, "ft")}` : null,
        maxSlope ? `Max slope: ${formatMetric(maxSlope, "%")}` : null,
        minSlope ? `Min slope: ${formatMetric(minSlope, "%")}` : null,
        flowCfs ? `Flow: ${formatMetric(flowCfs, "cfs")}` : null,
        cutFillNet ? `Cut/Fill net: ${formatMetric(cutFillNet, "cf")}` : null,
        basinSize ? `Pond size: ${formatMetric(basinSize, "sf")}` : null,
      ].filter(Boolean);
      appendChatMessage("assistant", metricLines.join("\n"), "status");
      return true;
    }

    if (/(systems|generated systems|what systems)/i.test(normalized)) {
      const enabled = [
        previewLayers.buildings ? "buildings" : null,
        previewLayers.roads ? "roads/parking" : null,
        previewLayers.grading ? "grading" : null,
        previewLayers.drainage ? "drainage/storm" : null,
        previewLayers.utilities ? "utilities" : null,
        previewLayers.structures ? "structures" : null,
      ].filter(Boolean);
      appendChatMessage(
        "assistant",
        `Preview layers enabled: ${enabled.length ? enabled.join(", ") : "none"}.`,
        "status",
      );
      return true;
    }

    return false;
  };

  const tryHandleActionIntent = (message: string): boolean => {
    const normalized = message.toLowerCase();
    const tokens = normalized.split(/\s+/);
    const allObjects = buildingPlacements;

    const findByLabel = (label: string) =>
      allObjects.find((item) => item.label.toLowerCase() === label.toLowerCase());
    const matchByKeyword = (keyword: string) =>
      allObjects.filter((item) =>
        item.label.toLowerCase().includes(keyword) ||
        (item.type ?? "").toLowerCase() === keyword,
      );

    const numberMatch = normalized.match(/(?:building|basin|entrance)\s*(\d+)/i);
    const keywordMatch = tokens.find((token) =>
      ["building", "basin", "entrance", "site", "road", "parking"].includes(token),
    );
    const selected = activePlacementId
      ? allObjects.find((item) => item.id === activePlacementId)
      : null;

    const targetFromNumber = numberMatch
      ? findByLabel(`${numberMatch[0].charAt(0).toUpperCase()}${numberMatch[0].slice(1)}`)
      : null;
    const targetFromKeyword = keywordMatch
      ? matchByKeyword(keywordMatch).filter((item) => item.placed)
      : [];

    const resolveTarget = () => {
      if (targetFromNumber) return targetFromNumber;
      if (selected) return selected;
      if (targetFromKeyword.length === 1) return targetFromKeyword[0];
      return null;
    };

    if (normalized.startsWith("select ")) {
      const label = message.replace(/^select\s+/i, "").trim();
      const target =
        findByLabel(label) ||
        allObjects.find((item) => item.label.toLowerCase().includes(label.toLowerCase()));
      if (target) {
        setActivePlacementId(target.id);
        setStatusMessage(`Selected ${target.label}.`);
        appendChatMessage("assistant", `Selected ${target.label}.`, "status");
        return true;
      }
      appendChatMessage("assistant", "I couldn't find that object. Try 'select Building 1' or 'select basin 1'.", "status");
      return true;
    }

    if (/(delete|remove)\b/.test(normalized)) {
      const target = resolveTarget();
      if (target) {
        handleRemoveBuilding(target.id);
        appendChatMessage("assistant", `Removed ${target.label}.`, "status");
        return true;
      }
      appendChatMessage("assistant", "Which object should I remove? You can say 'remove Building 1'.", "status");
      return true;
    }

    if (/(make|classify|change|convert).*\b(building|road|parking|basin|detention|pond|line|area|rectangle)\b/.test(normalized)) {
      const target = resolveTarget();
      const requestedType: SiteObjectType | null = /basin|detention|pond/.test(normalized)
        ? "basin"
        : /parking/.test(normalized)
          ? "parking"
          : /road|line/.test(normalized)
            ? "road"
            : /building|rectangle/.test(normalized)
              ? "building"
              : null;
      if (!requestedType) return false;
      if (!target) {
        appendChatMessage(
          "assistant",
          `Select a drawn object first, then say "make this a ${SITE_OBJECT_CATALOG[requestedType].label.toLowerCase()}."`,
          "status",
        );
        return true;
      }
      if (target.type === "site") {
        appendChatMessage("assistant", "The site boundary cannot be reclassified. Draw or select a separate object first.", "status");
        return true;
      }
      const nextLabel = formatObjectLabel(
        requestedType,
        buildingPlacements.filter((item) => item.type === requestedType).length + 1,
      );
      handleUpdateBuilding(target.id, {
        type: requestedType,
        label: nextLabel,
        use: SITE_OBJECT_CATALOG[requestedType].use,
        source: target.source ?? "user",
        meta: {
          ...(target.meta ?? {}),
          category: SITE_OBJECT_CATALOG[requestedType].category,
          classification_status: "draft_review_required",
        },
      });
      appendChatMessage(
        "assistant",
        `Reclassified ${target.label} as ${SITE_OBJECT_CATALOG[requestedType].label}. This is draft geometry and still requires engineer review.`,
        "status",
      );
      return true;
    }

    if (/(place|re-?place|move)\b/.test(normalized)) {
      const target = resolveTarget();
      if (target) {
        handleSelectPlacementTarget(target.id);
        return true;
      }
      if (allObjects.length === 0) {
        appendChatMessage("assistant", "There are no objects to place yet. Add a building first.", "status");
        return true;
      }
      appendChatMessage("assistant", "Which object should I place? For example, 'place Building 1'.", "status");
      return true;
    }

    if (/(bigger|smaller|resize|scale|shrink|grow)\b/.test(normalized)) {
      const target = resolveTarget();
      if (!target) {
        appendChatMessage("assistant", "Which object should I resize? For example, 'make Building 1 bigger'.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `How should I resize ${target.label}? Give me a size like "set to 120 ft by 60 ft".`,
        "status",
      );
      return true;
    }

    if (/(generate|run)\b/.test(normalized)) {
      if (/roads|circulation/.test(normalized)) {
        void handleGenerateSystem("roads");
        return true;
      }
      if (/parking/.test(normalized)) {
        void handleGenerateSystem("parking");
        return true;
      }
      if (/grading|contours/.test(normalized)) {
        void handleGenerateSystem("grading");
        return true;
      }
      if (/drainage|storm/.test(normalized)) {
        void handleGenerateSystem("drainage");
        return true;
      }
      if (/utilities|utility/.test(normalized)) {
        void handleGenerateSystem("utilities");
        return true;
      }
      if (/full|all|everything/.test(normalized)) {
        void handleGenerateSystem("full");
        return true;
      }
    }

    if (/(fix|improve)\b/.test(normalized)) {
      const nextHint = workflowActionHints[0];
      if (nextHint) {
        const targetPanel: SidePanelKey =
          nextHint.startsWith("Setup panel")
            ? "site_existing"
            : nextHint.startsWith("Data panel")
              ? "data"
              : nextHint.startsWith("Objects panel")
                ? "objects"
                : nextHint.startsWith("Generate Systems panel")
                  ? "generate"
                  : nextHint.startsWith("Deliver panel")
                    ? "deliverables"
                    : "reports";
        handleOpenSidePanel(targetPanel);
        appendChatMessage(
          "assistant",
          `Next fix: ${nextHint} I opened the ${sidePanelCopy[targetPanel].title} panel. Civora can prepare review evidence only; external engineer approval remains required.`,
          "status",
        );
        return true;
      }
      appendChatMessage(
        "assistant",
        "I do not see a single automatic fix to apply. Open Review for blockers, or ask for a specific action like 'fix drainage' or 'improve parking'.",
        "status",
      );
      return true;
    }

    return false;
  };

  const shouldRouteToOrchestrator = (message: string): boolean => {
    const normalized = message.toLowerCase();
    if (normalized.length < 140) return false;
    const asksForDesign =
      /\b(design|create|generate|produce|engineer|layout|site plan|development)\b/.test(normalized);
    const describesScope =
      /\b(include|with|building|road|parking|grading|drainage|utilities|detention|basin|sanitary|water)\b/.test(
        normalized,
      );
    return asksForDesign && describesScope;
  };

  const handlePromptKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const handleSendMessage = () => {
    const trimmed = prompt.trim();
    if (!trimmed && !imageName) return;
    const normalizedStatus = String(visibleActiveJob?.status || "").toLowerCase();
    const approvalCommand = Boolean(
      trimmed &&
        /^(ok(ay)?|approve|continue|yes|y|go ahead|start next|proceed)$/i.test(trimmed.trim()),
    );
    if (normalizedStatus === "awaiting_approval" && approvalCommand) {
      appendChatMessage("user", trimmed);
      setPrompt("");
      handleContinueActiveJob();
      return;
    }
    if (pendingClarification && trimmed) {
      appendChatMessage("user", trimmed);
      setPrompt("");
      const lot = resolveLotBounds();
      const hasSite = Boolean(lot.w && lot.h);
      if (pendingClarification.action === "set_site_then_add") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const type = pendingClarification.payload?.type as SiteObjectType | undefined;
          if (type) {
            setPendingClarification(null);
            handleAddObject(type);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "set_site_then_detect") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          setPendingClarification(null);
          void handleAnalyzeImageFeatures();
          return;
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "set_site_then_generate") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const target = pendingClarification.payload?.target as
            | "roads"
            | "parking"
            | "grading"
            | "drainage"
            | "utilities"
            | "full"
            | undefined;
          if (target) {
            setPendingClarification(null);
            void handleGenerateSystem(target);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "place_object_missing_site") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const id = pendingClarification.payload?.id as string | undefined;
          if (id) {
            setPendingClarification(null);
            handleSelectPlacementTarget(id);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "upload_image_then_detect") {
        if (mapSnapshotPath) {
          setPendingClarification(null);
          void handleAnalyzeImageFeatures();
          return;
        }
        appendChatMessage(
          "assistant",
          "Please upload a site image/map snapshot first, then say “done.”",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "access_analysis_missing") {
        const confirmed = buildingPlacements.filter(
          (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
        );
        const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
        const buildingTypes = new Set<SiteObjectType>([
          "building",
          "retail_building",
          "multifamily_building",
          "industrial_building",
          "office_building",
          "pad",
        ]);
        const buildings = confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType));
        const access = confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType));
        if (buildings.length && access.length) {
          setPendingClarification(null);
          handleAnalyzeSiteAccess();
          return;
        }
        appendChatMessage(
          "assistant",
          "Once you add or confirm buildings and access objects, I can run access analysis.",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "grading_source") {
        const lower = trimmed.toLowerCase();
        let slopeEstimateOverride: SurveySlopeResponse | null = null;
        if (/(survey)/.test(lower)) {
          if (!surveyFileName) {
            appendChatMessage("assistant", "Please upload a survey/topo file first.", "status");
            return;
          }
          setUseSurveyForGrading(true);
        } else if (/(map|terrain)/.test(lower)) {
          setUseSurveyForGrading(false);
        } else if (/(assume|assumed|fallback)/.test(lower)) {
          slopeEstimateOverride = buildAssumedSlopeEstimate();
          setUseSurveyForGrading(false);
          setSurveySlopeEstimate(slopeEstimateOverride);
        } else {
          appendChatMessage(
            "assistant",
            "Should I use survey, map terrain, or an assumed slope?",
            "status",
          );
          return;
        }
        const target = pendingClarification.payload?.target as
          | "roads"
          | "parking"
          | "grading"
          | "drainage"
          | "utilities"
          | "full"
          | undefined;
        if (target) {
          setPendingClarification(null);
          void handleGenerateSystem(target, { slopeEstimateOverride });
          return;
        }
      }
      if (pendingClarification.action === "drainage_missing_basin") {
        const hasBasin = buildingPlacements.some((item) => item.type === "basin" && item.placed);
        if (hasBasin) {
          const target = pendingClarification.payload?.target as
            | "drainage"
            | "full"
            | undefined;
          if (target) {
            setPendingClarification(null);
            void handleGenerateSystem(target);
            return;
          }
        }
        appendChatMessage(
          "assistant",
          "Add a basin object first, then I can run drainage.",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "lock_site_required") {
        const lower = trimmed.toLowerCase();
        if (/(yes|ok|lock|confirm)/.test(lower)) {
          setPendingClarification(null);
          handleToggleSiteLock();
          const target = pendingClarification.payload?.action as
            | "roads"
            | "parking"
            | "grading"
            | "drainage"
            | "utilities"
            | "full"
            | undefined;
          if (target) {
            void handleGenerateSystem(target);
          }
          return;
        }
        appendChatMessage(
          "assistant",
          "Lock the site when you're ready, then I can continue.",
          "status",
        );
        return;
      }
    }
    if (busy || visibleActiveJob) {
      if (trimmed || imageName) {
        appendChatMessage("user", trimmed || "Uploaded an image.");
        appendChatMessage(
          "assistant",
          "A run is already in progress. Please wait for it to finish before sending a new request.",
          "status",
        );
      }
      setStatusMessage("A run is already in progress. Please wait for it to finish.");
      setPrompt("");
      return;
    }
    if (trimmed) {
      const routeToOrchestrator = shouldRouteToOrchestrator(trimmed);
      if (!routeToOrchestrator) {
        const handledInfo = tryHandleInfoIntent(trimmed);
        if (handledInfo) {
          setPrompt("");
          return;
        }
        const handledAction = tryHandleActionIntent(trimmed);
        if (handledAction) {
          setPrompt("");
          return;
        }
        const handled = tryHandleObjectIntent(trimmed);
        if (handled) {
          setPrompt("");
          return;
        }
      }
    }
    void runOrchestrator("run");
  };

  const handleContinuePendingClarification = () => {
    if (!pendingClarification) return;
    const lot = resolveLotBounds();
    const hasSite = Boolean(lot.w && lot.h);
    if (pendingClarification.action === "set_site_then_add") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      const type = pendingClarification.payload?.type as SiteObjectType | undefined;
      if (type) {
        setPendingClarification(null);
        handleAddObject(type);
      }
      return;
    }
    if (pendingClarification.action === "set_site_then_detect") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      setPendingClarification(null);
      void handleAnalyzeImageFeatures();
      return;
    }
    if (pendingClarification.action === "set_site_then_generate") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      const target = pendingClarification.payload?.target as
        | "roads"
        | "parking"
        | "grading"
        | "drainage"
        | "utilities"
        | "full"
        | undefined;
      if (target) {
        setPendingClarification(null);
        void handleGenerateSystem(target);
      }
      return;
    }
    if (pendingClarification.action === "upload_image_then_detect") {
      if (!mapSnapshotPath) {
        appendChatMessage("assistant", "Please upload a site image/map snapshot first.", "status");
        return;
      }
      setPendingClarification(null);
      void handleAnalyzeImageFeatures();
      return;
    }
    if (pendingClarification.action === "access_analysis_missing") {
      setPendingClarification(null);
      handleAnalyzeSiteAccess();
      return;
    }
    if (pendingClarification.action === "grading_source") {
      const target = pendingClarification.payload?.target as
        | "roads"
        | "parking"
        | "grading"
        | "drainage"
        | "utilities"
        | "full"
        | undefined;
      if (target) {
        const slopeEstimateOverride = buildAssumedSlopeEstimate();
        setUseSurveyForGrading(false);
        setSurveySlopeEstimate(slopeEstimateOverride);
        setPendingClarification(null);
        void handleGenerateSystem(target, { slopeEstimateOverride });
      }
      return;
    }
  };

  const handleCancelActiveJob = async () => {
    if (visibleActiveJob?.job_id && token) {
      try {
        const data = await postJson<{ job: JobSummary }>(
          `/api/jobs/${visibleActiveJob.job_id}/cancel`,
          {},
          { token },
        );
        setJobs((current) => {
          const next = [...current];
          const index = next.findIndex((job) => job.job_id === data.job.job_id);
          if (index >= 0) {
            next[index] = { ...next[index], ...data.job };
          } else {
            next.unshift(data.job);
          }
          return next;
        });
        appendChatMessage("assistant", `Job ${data.job.job_id} was cancelled.`, "status");
        setStatusMessage(`Cancelled job ${data.job.job_id}.`);
        if (activeJobId === data.job.job_id) {
          setActiveJobId("");
        }
        setBusy(false);
        runSubmissionRef.current = false;
      } catch (error) {
        setStatusMessage(
          error instanceof Error ? error.message : "Job cancel failed.",
        );
      }
      return;
    }
    if (directRunAbortRef.current) {
      directRunAbortRef.current.abort();
      directRunAbortRef.current = null;
      runSubmissionRef.current = false;
      setBusy(false);
      setActivePlanTool("run");
      setStatusMessage("Cancelling the live request...");
      return;
    }
  };

  const handleContinueActiveJob = async () => {
    if (!token) return;
    if (!visibleActiveJob?.job_id) {
      setStatusMessage("No active job is awaiting approval.");
      return;
    }
    const status = String(visibleActiveJob.status || "").toLowerCase();
    if (status !== "awaiting_approval") {
      setStatusMessage("There is no phase awaiting approval right now.");
      return;
    }
    const nextPhaseLabel =
      previewNextPendingPhase?.label || previewRunningPhase?.label || "Next phase";
    setApprovalError(null);
    setApprovalPhaseLabel(nextPhaseLabel);
    setApprovalInFlight(true);
    setBusy(true);
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${visibleActiveJob.job_id}/continue`,
        {},
        { token },
      );
      setJobs((current) => {
        const next = [...current];
        const index = next.findIndex((job) => job.job_id === data.job.job_id);
        if (index >= 0) {
          next[index] = { ...next[index], ...data.job };
        } else {
          next.unshift(data.job);
        }
        return next;
      });
      appendChatMessage(
        "assistant",
        `Accepted the current phase for review workflow. Starting ${nextPhaseLabel}.`,
        "status",
      );
      setStatusMessage(`Accepted ${data.job.job_id} for review workflow. Starting ${nextPhaseLabel}.`);
      if (data.job.job_id) {
        setActiveJobId(data.job.job_id);
        setApprovalPendingJobId(data.job.job_id);
      }
      await refreshJobs(token, { suppressError: true, force: true });
      queuePreviewRefresh("Refreshing preview after approval...");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not continue the staged run.";
      setApprovalError(message);
      setStatusMessage(message);
    } finally {
      setBusy(false);
      setApprovalInFlight(false);
    }
  };

  const saveProject = async ({
    silent = false,
    projectIdOverride,
    nameOverride,
    fileNameOverride,
    projectInputOverride,
    latestResultOverride,
    autoNamedOverride,
    autoFileNamedOverride,
  }: {
    silent?: boolean;
    projectIdOverride?: string | null;
    nameOverride?: string;
    fileNameOverride?: string;
    projectInputOverride?: ProjectInput;
    latestResultOverride?: PlanResponse;
    autoNamedOverride?: boolean;
    autoFileNamedOverride?: boolean;
  } = {}): Promise<ProjectRecord | null> => {
    if (!token) return null;
    if (!silent) setBusy(true);
    const effectiveProjectId =
      projectIdOverride !== undefined
        ? projectIdOverride
        : resolvedProjectIdRef.current || projectId || currentProject?.project_id || null;
    const resolvedName = (nameOverride ?? siteName).trim();
    const resolvedFileName = (fileNameOverride ?? fileName).trim();
    const liveChatThread = chatMessagesRef.current;
    const projectInputToSave = projectInputOverride
      ? {
          ...projectInputOverride,
          manual_fields: {
            ...(projectInputOverride.manual_fields ?? {}),
            project_name: resolvedName,
            file_name: resolvedFileName,
          },
          meta: {
            ...(projectInputOverride.meta ?? {}),
            chat_thread: liveChatThread,
            auto_named: autoNamedOverride ?? siteNameAuto,
            auto_file_named: autoFileNamedOverride ?? fileNameAuto,
          },
        }
      : {
          ...payloadPreview,
          manual_fields: {
            ...(payloadPreview.manual_fields ?? {}),
            project_name: resolvedName,
            file_name: resolvedFileName,
          },
          meta: {
            ...(payloadPreview.meta ?? {}),
            chat_thread: liveChatThread,
            auto_named: autoNamedOverride ?? siteNameAuto,
            auto_file_named: autoFileNamedOverride ?? fileNameAuto,
          },
        };
    const latestResultToSave =
      latestResultOverride !== undefined ? latestResultOverride : undefined;
    try {
      const requestBody: Record<string, unknown> = {
        project_id: effectiveProjectId,
        name: resolvedName,
        project_input: projectInputToSave,
        metadata: {
          auto_named: autoNamedOverride ?? siteNameAuto,
          auto_file_named: autoFileNamedOverride ?? fileNameAuto,
        },
      };
      if (latestResultToSave !== undefined) {
        requestBody.latest_result = latestResultToSave;
      }
      const data = await postJson<{ project: ProjectRecord }>(
        "/api/projects",
        requestBody,
        { token },
      );
      resolvedProjectIdRef.current = data.project.project_id;
      setProjectId(data.project.project_id);
      setCurrentProject(data.project);
      upsertProjectSummary(data.project);
      if (!silent) {
        setStatusMessage(
          `Saved project "${data.project.name || resolvedName || "Untitled Project"}".`,
        );
      }
      return data.project;
    } catch (error) {
      if (!silent) {
        setStatusMessage(
          error instanceof Error ? error.message : "Project save failed.",
        );
      }
      return null;
    } finally {
      if (!silent) setBusy(false);
    }
  };

  useEffect(() => {
    const activeProjectId =
      resolvedProjectIdRef.current || projectId || currentProject?.project_id || "";
    if (!token || !activeProjectId || !currentProject) return;
    if (autosaveSuspendRef.current) return;
    const savedThread = Array.isArray(currentProject?.project_input?.meta?.chat_thread)
      ? currentProject.project_input.meta.chat_thread
      : [];
    const currentThread = chatMessagesRef.current.map(
      ({ role, content, kind, createdAt, id }) => ({
        role,
        content,
        kind,
        createdAt,
        id,
      }),
    );
    const savedPrompt = String(currentProject?.project_input?.prompt_text ?? "");
    const currentPrompt = String(prompt ?? "");
    const threadChanged =
      JSON.stringify(savedThread) !== JSON.stringify(currentThread);
    const promptChanged = savedPrompt !== currentPrompt;
    if (!threadChanged && !promptChanged) {
      return;
    }
    if (chatAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(chatAutosaveTimeoutRef.current);
    }
    chatAutosaveTimeoutRef.current = window.setTimeout(() => {
      void saveProject({ silent: true, projectIdOverride: activeProjectId });
    }, 700);
  }, [chatMessages, prompt, token, projectId, currentProject]);

  useEffect(() => {
    if (!token || !currentProject?.project_id) return;
    if (autosaveSuspendRef.current) return;
    if (controlAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(controlAutosaveTimeoutRef.current);
    }
    controlAutosaveTimeoutRef.current = window.setTimeout(() => {
      void saveProject({ silent: true });
    }, 700);
  }, [
    token,
    currentProject?.project_id,
    siteName,
    fileName,
    units,
    projectType,
    lotWidth,
    lotHeight,
    buildingWidth,
    buildingDepth,
    buildingCount,
    setback,
    parkingCount,
    minSlopePct,
    pipeMinSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    maxAdaCrossSlopePct,
    roads,
    grading,
    drainage,
    utilities,
    buildingPlacements,
  ]);

  useEffect(() => {
    if (!currentProject?.project_id) return;
    if (lastSiteInputProjectRef.current === currentProject.project_id) return;
    lastSiteInputProjectRef.current = currentProject.project_id;
    const siteInputs =
      currentProject?.project_input?.meta?.site_inputs &&
      typeof currentProject.project_input.meta.site_inputs === "object"
        ? currentProject.project_input.meta.site_inputs
        : {};
    const mapSnapshot = siteInputs?.map_snapshot ?? {};
    const mapAnalysisResult = siteInputs?.map_analysis ?? null;
    const surveyFile = siteInputs?.survey_file ?? {};
    const slopeEstimate = siteInputs?.slope_estimate ?? null;
      const detectionScale = siteInputs?.detection_scale ?? {};
      const alignmentLocked =
        typeof siteInputs?.site_alignment_locked === "boolean"
          ? siteInputs.site_alignment_locked
          : null;
    const useSurvey = siteInputs?.use_survey_for_grading;
    const storedPoints = Array.isArray(siteInputs?.survey_points) ? siteInputs?.survey_points : [];
    const detectedObjects = Array.isArray(siteInputs?.detected_objects)
      ? (siteInputs?.detected_objects as BuildingPlacement[])
      : [];
    setSiteAddress(String(siteInputs?.address || ""));
    setSurveyFileName(String(surveyFile?.stored_filename || ""));
    setSurveySlopeEstimate(slopeEstimate || null);
    setUseSurveyForGrading(useSurvey !== undefined ? Boolean(useSurvey) : true);
    setSurveyPoints(storedPoints as number[][]);
    setSurveyPreviewPoints(mapSurveyPointsToSite(storedPoints as number[][]));
    setDrainageSourceOverride(
      siteInputs?.drainage_source_override === "user" ? "user" : "civora",
    );
    setSurveyDiagnostics((prev) => ({
      ...(prev ?? {}),
      fileType: siteInputs?.survey_file_type ?? prev?.fileType,
      parseSuccess: siteInputs?.survey_parse_success ?? prev?.parseSuccess,
      pointCount: siteInputs?.survey_point_count ?? prev?.pointCount,
      recognizedColumns: siteInputs?.survey_point_columns ?? prev?.recognizedColumns,
      invalidRows: siteInputs?.survey_invalid_rows ?? prev?.invalidRows,
      bounds: siteInputs?.survey_bounds ?? prev?.bounds,
      elevationRange: siteInputs?.survey_elevation_range ?? prev?.elevationRange,
      warnings: siteInputs?.survey_point_warnings ?? prev?.warnings,
    }));
      setDetectionScaleFeet(
        detectionScale?.distance_ft ? String(detectionScale.distance_ft) : "",
      );
    setDetectionScalePixels(
      detectionScale?.pixel_distance ? String(detectionScale.pixel_distance) : "",
    );
      setDetectionScaleFtPerPx(
        typeof detectionScale?.scale_ft_per_px === "number" ? detectionScale.scale_ft_per_px : null,
      );
      setDetectionScaleSource(
        detectionScale?.scale_source === "mapbox" || detectionScale?.scale_source === "manual"
          ? detectionScale.scale_source
          : "approximate",
      );
      if (alignmentLocked !== null) {
        const lotW = parsePositiveNumber(lotWidth);
        const lotH = parsePositiveNumber(lotHeight);
        if (alignmentLocked && (!lotW || !lotH)) {
          setSiteScaleLocked(false);
        } else {
          setSiteScaleLocked(alignmentLocked);
        }
      }
      const rotationValue =
        typeof siteInputs?.site_rotation_deg === "number" ? siteInputs.site_rotation_deg : 0;
      setSiteRotationDeg(rotationValue);
      setSiteRotationInput(String(rotationValue));
    setDetectedPlacements(detectedObjects);
    const mapUrl = String(mapSnapshot?.image_url || "");
    if (mapUrl) {
      setUploadedImageApiUrl(uploadedImageSrc(mapUrl, token));
    }
    setMapSnapshotPath(String(mapSnapshot?.image_path || ""));
    setMapAnalysis(mapAnalysisResult || null);
  }, [currentProject, mapSurveyPointsToSite, token]);

  const loadProject = async (id: string) => {
    if (!token) return;
    autosaveSuspendRef.current = true;
    if (chatAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(chatAutosaveTimeoutRef.current);
      chatAutosaveTimeoutRef.current = null;
    }
    if (controlAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(controlAutosaveTimeoutRef.current);
      controlAutosaveTimeoutRef.current = null;
    }
    const requestId = projectLoadRequestRef.current + 1;
    projectLoadRequestRef.current = requestId;
    try {
      resetWorkspaceState();
      setStatusMessage("Loading project...");
      const data = await getJson<{ project: ProjectRecord }>(
        `/api/projects/${id}`,
        { token },
      );
      if (projectLoadRequestRef.current !== requestId) {
        return;
      }
      const project = data.project;
      resolvedProjectIdRef.current = project.project_id;
      setCurrentProject(project);
      setProjectId(project.project_id);
      setSiteName(project.name ?? "");
      applyProjectInput(project.project_input ?? {});
      setBackendResult(null);
      setPlanPreviewUrl("");
      setPlanPreviewSummary(null);
      setStatusMessage(`Loaded project "${project.name}".`);
      loadProjectResultInBackground(project);
      if (activeJobId && (!projectId || currentProjectActiveJob?.project_id === id || activeJob?.project_id === id)) {
        void loadJob(activeJobId);
      }
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Project load failed.",
      );
    } finally {
      autosaveSuspendRef.current = false;
    }
  };

  const ensureProjectDraft = async (): Promise<string | null> => {
    if (!token) return null;
    if (resolvedProjectIdRef.current) return resolvedProjectIdRef.current;
    if (projectId) return projectId;
    if (currentProject?.project_id) return currentProject.project_id;
    if (draftProjectPromiseRef.current) {
      const inFlightProject = await draftProjectPromiseRef.current;
      return inFlightProject?.project_id ?? null;
    }
    draftProjectPromiseRef.current = saveProject({
      silent: true,
      projectIdOverride: null,
      nameOverride: siteName.trim(),
      fileNameOverride: fileName.trim(),
      autoNamedOverride: false,
      autoFileNamedOverride: false,
    });
    try {
      const savedProject = await draftProjectPromiseRef.current;
      return savedProject?.project_id ?? null;
    } finally {
      draftProjectPromiseRef.current = null;
    }
  };

  useEffect(() => {
    ensureProjectDraftRef.current = ensureProjectDraft;
    saveProjectRef.current = saveProject;
  }, [ensureProjectDraft, saveProject]);

  const loadJob = async (id: string) => {
    if (!token) return;
    try {
      const data = await getJson<{ job: JobSummary }>(`/api/jobs/${id}`, { token });
      const job = data.job;
      const jobProjectId = String(job.project_id || "").trim();
      const activeJobProjectSignature = `${job.job_id}:${jobProjectId}`;
      const activeTrackedProjectId =
        jobProjectId ||
        resolvedProjectIdRef.current ||
        projectId ||
        currentProject?.project_id ||
        "";
      if (jobProjectId) {
        resolvedProjectIdRef.current = jobProjectId;
        upsertProjectSummary({
          project_id: jobProjectId,
          name: currentProject?.project_id === jobProjectId
            ? currentProject.name || siteName || "Untitled Project"
            : siteName || "Untitled Project",
          description:
            currentProject?.project_id === jobProjectId
              ? currentProject.description ?? ""
              : "",
          has_result:
            Boolean(job.result && Object.keys(job.result).length) ||
            ["awaiting_approval", "completed"].includes(
              String(job.status || "").toLowerCase(),
            ),
          updated_at:
            typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
              ? job.updated_at
              : Date.now() / 1000,
        });
        if (projectId !== jobProjectId) {
          setProjectId(jobProjectId);
        }
        if (!currentProject || currentProject.project_id !== jobProjectId) {
          setCurrentProject((existing) => {
            if (existing?.project_id === jobProjectId) {
              return existing;
            }
            return {
              project_id: jobProjectId,
              name: existing?.name || siteName || "Untitled Project",
              description: existing?.description ?? "",
              has_result: true,
            } as ProjectRecord;
          });
        }
        const shouldSyncActiveJobProject =
          (currentProject?.project_id !== jobProjectId ||
            projectId !== jobProjectId) &&
          activeJobProjectSyncRef.current !== activeJobProjectSignature;
        if (shouldSyncActiveJobProject) {
          activeJobProjectSyncRef.current = activeJobProjectSignature;
          const requestId = projectLoadRequestRef.current + 1;
          projectLoadRequestRef.current = requestId;
          autosaveSuspendRef.current = true;
          void getJson<{ project: ProjectRecord }>(`/api/projects/${jobProjectId}`, {
            token,
          })
            .then((projectData) => {
              if (projectLoadRequestRef.current !== requestId) {
                autosaveSuspendRef.current = false;
                return;
              }
              const syncedProject = projectData.project;
              resolvedProjectIdRef.current = syncedProject.project_id;
              setCurrentProject(syncedProject);
              setProjectId(syncedProject.project_id);
              setSiteName(syncedProject.name ?? "");
              applyProjectInput(syncedProject.project_input ?? {});
              upsertProjectSummary(syncedProject);
              loadProjectResultInBackground(syncedProject);
              autosaveSuspendRef.current = false;
            })
            .catch((error) => {
              setStatusMessage(
                error instanceof Error
                  ? error.message
                  : "Project sync from active job failed.",
              );
              autosaveSuspendRef.current = false;
            });
        }
      }
      setJobs((current) => {
        const next = [...current];
        const existingIndex = next.findIndex((item) => item.job_id === job.job_id);
        if (existingIndex >= 0) {
          next[existingIndex] = { ...next[existingIndex], ...job };
        } else {
          next.unshift(job);
        }
        return next;
      });
      setActiveJobId(job.job_id);
      const previousStatus = lastJobStatusRef.current[job.job_id];
      const normalizedStatus = String(job.status || "").toLowerCase();
      const stageLabel = String(job.stage || "").trim() || "Engineering Run";
      const stageDetail = String(job.stage_detail || "").trim();
      const phaseSignature = `${normalizedStatus}|${stageLabel}|${stageDetail}`;
      if (previousStatus !== job.status) {
        lastJobStatusRef.current[job.job_id] = job.status;
        if (job.status === "queued") {
          const queuePosition =
            typeof job.queue_position === "number" && Number.isFinite(job.queue_position)
              ? Math.max(1, Math.round(job.queue_position))
              : null;
          const queuedCount =
            typeof job.queued_count === "number" && Number.isFinite(job.queued_count)
              ? Math.max(0, Math.round(job.queued_count))
              : 0;
          const runningCount =
            typeof job.running_count === "number" && Number.isFinite(job.running_count)
              ? Math.max(0, Math.round(job.running_count))
              : 0;
          appendChatMessage(
            "assistant",
            queuePosition
              ? `Job ${job.job_id} is queued in the background. Position ${queuePosition}${queuedCount > 0 ? ` of ${queuedCount}` : ""}. ${runningCount > 0 ? `${runningCount} worker${runningCount === 1 ? "" : "s"} active.` : ""}`.trim()
              : `Job ${job.job_id} is queued and waiting to run in the background.`,
            "status",
          );
        } else if (job.status === "awaiting_approval") {
          appendChatMessage(
            "assistant",
            `${toReadableLabel(stageLabel)} stage complete. Waiting for your approval. User-controlled workflow.`,
            "status",
          );
        } else if (job.status === "cancelling") {
          appendChatMessage(
            "assistant",
            `Job ${job.job_id} is cancelling now.`,
            "status",
          );
        }
        lastJobPhaseSignatureRef.current[job.job_id] = phaseSignature;
      } else if (
        ["running", "awaiting_approval", "queued"].includes(normalizedStatus) &&
        lastJobPhaseSignatureRef.current[job.job_id] !== phaseSignature
      ) {
        lastJobPhaseSignatureRef.current[job.job_id] = phaseSignature;
        if (normalizedStatus === "awaiting_approval") {
          appendChatMessage(
            "assistant",
            `${toReadableLabel(stageLabel)} stage complete. Waiting for your approval. User-controlled workflow.`,
            "status",
          );
        }
      }
      if (
        activeTrackedProjectId &&
        ["queued", "running", "awaiting_approval"].includes(String(job.status || "").toLowerCase())
      ) {
        const refreshStamp =
          typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
            ? job.updated_at
            : Date.now() / 1000;
        const previousRefresh = lastProjectResultRefreshRef.current[job.job_id] ?? 0;
        if (refreshStamp > previousRefresh) {
          lastProjectResultRefreshRef.current[job.job_id] = refreshStamp;
          loadProjectResultInBackground({
            project_id: activeTrackedProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
          } as ProjectRecord);
        }
      }
      if (
        job.result &&
        Object.keys(job.result).length &&
        activeTrackedProjectId &&
        ["queued", "running", "awaiting_approval"].includes(String(job.status || "").toLowerCase())
      ) {
        const partialRefreshStamp =
          typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
            ? job.updated_at
            : Date.now() / 1000;
        const previousPartialRefresh =
          lastJobPartialResultRefreshRef.current[job.job_id] ?? 0;
        if (partialRefreshStamp > previousPartialRefresh) {
          lastJobPartialResultRefreshRef.current[job.job_id] = partialRefreshStamp;
          applyBackendResult(job.result);
          requestPreviewInBackground(
            {
              project_id: activeTrackedProjectId || null,
              result: job.result,
              filename_stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
            },
            {
              silentStatus: true,
            },
          );
        }
      }
      if (job.status === "completed" && job.result) {
        applyBackendResult(job.result);
        requestPreviewInBackground(
          {
            project_id: activeTrackedProjectId || null,
            result: job.result,
            filename_stem: fileName || siteName,
          },
          {
            loadingMessage:
              projectId && job.project_id === projectId
                ? `Job ${job.job_id} completed. Refreshing preview...`
                : undefined,
            successMessage: `Job ${job.job_id} completed.`,
          },
        );
        appendChatMessage(
          "assistant",
          summarizePlanResponse(job.result, "run"),
          "message",
        );
        setActiveJobId("");
        if (jobProjectId) {
          upsertProjectSummary({
            project_id: jobProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
            description: currentProject?.description ?? "",
            has_result: true,
            updated_at: Date.now() / 1000,
          });
        }
        if (activeTrackedProjectId) {
          loadProjectResultInBackground({
            project_id: activeTrackedProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
          } as ProjectRecord);
        }
      } else if (job.status === "failed") {
        appendChatMessage(
          "assistant",
          job.error ?? "The background job failed before Civora could finish the design.",
          "status",
        );
        setStatusMessage(job.error ?? "Job failed.");
        setActiveJobId("");
      } else if (job.status === "cancelled") {
        appendChatMessage(
          "assistant",
          `Job ${job.job_id} was cancelled before completion.`,
          "status",
        );
        setStatusMessage(`Job ${job.job_id} was cancelled.`);
        setActiveJobId("");
      } else {
        setStatusMessage(
          job.stage_detail
            ? `${job.stage || "Running"}: ${job.stage_detail}`
            : `Job ${job.job_id} is ${job.status}.`,
        );
      }
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Job load failed.");
    }
  };

  const uploadImage = async (file: File) => {
    if (!token) return;
    const localPreviewUrl = URL.createObjectURL(file);
    setUploadedImagePreviewUrl(localPreviewUrl);
    setImageUploadState("uploading");
    setImageUploadNote("Uploading image…");
    clearGeneratedPreview();
    try {
      const imageElement = new Image();
      const imageSize = await new Promise<{ width: number; height: number } | null>((resolve) => {
        imageElement.onload = () => resolve({ width: imageElement.width, height: imageElement.height });
        imageElement.onerror = () => resolve(null);
        imageElement.src = localPreviewUrl;
      });
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadImageResponse>("/api/upload-image", formData, {
        token,
      });
      setImageName(data.image_path || file.name);
      setUploadedImageApiUrl(
        data.image_url ? uploadedImageSrc(data.image_url, token) : "",
      );
      setMapSnapshotPath(data.image_path || "");
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        map_snapshot: {
          filename: data.filename || file.name,
          stored_filename: data.image_path || file.name,
          image_path: data.image_path || "",
          image_url: data.image_url || "",
        },
        site_alignment_locked: true,
      };
      const hasSite = buildingPlacements.some((item) => item.type === "site");
      let width = parsePositiveNumber(lotWidth);
      let height = parsePositiveNumber(lotHeight);
      if (!hasSite) {
        const acres = 10;
        const baseSide = Math.sqrt(acres * 43560);
        const aspect =
          imageSize && imageSize.width > 0 && imageSize.height > 0
            ? imageSize.width / imageSize.height
            : 1;
        const fallbackWidth = baseSide * Math.sqrt(aspect);
        const fallbackHeight = baseSide / Math.sqrt(aspect);
        const scaledWidth =
          imageSize && detectionScaleFtPerPx
            ? imageSize.width * detectionScaleFtPerPx
            : null;
        const scaledHeight =
          imageSize && detectionScaleFtPerPx
            ? imageSize.height * detectionScaleFtPerPx
            : null;
        width = scaledWidth ?? fallbackWidth;
        height = scaledHeight ?? fallbackHeight;
        autoFitSite(width, height, "Site Boundary");
        setShowSiteBounds(false);
        setSiteScaleLocked(true);
        setSiteSelectionMode(false);
      }
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
          manual_fields: {
            ...(currentInput?.manual_fields ?? {}),
            lot: {
              x: 0,
              y: 0,
              w: width || 0,
              h: height || 0,
            },
          },
        },
      });
      setImageUploadState("uploaded");
      setImageUploadNote("Image uploaded. Ready for detection.");
      setStatusMessage("Image uploaded.");
      if (width && height) {
        setImageUploadState("detecting");
        setImageUploadNote("Detecting site features…");
        void handleAnalyzeImageFeatures(data.image_path || "");
      } else {
        setStatusMessage("Image uploaded. Set site dimensions to run detection.");
      }
    } catch (error) {
      setImageName(file.name);
      setImageUploadState("failed");
      setImageUploadNote("Image upload failed.");
      setStatusMessage(
        error instanceof Error ? error.message : "Image upload failed.",
      );
    }
  };

  function mapSurveyPointsToSite(points: number[][]) {
    const width = parsePositiveNumber(lotWidth);
    const height = parsePositiveNumber(lotHeight);
    if (!points.length || !width || !height) return [];
    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = Math.max(maxX - minX, 1e-6);
    const spanY = Math.max(maxY - minY, 1e-6);
    const withinLot = minX >= 0 && minY >= 0 && maxX <= width * 1.2 && maxY <= height * 1.2;
    const mapPoint = (p: number[]) => {
      const x = withinLot ? p[0] : ((p[0] - minX) / spanX) * width;
      const y = withinLot ? p[1] : ((p[1] - minY) / spanY) * height;
      const z = typeof p[2] === "number" ? p[2] : undefined;
      return { x, y, z };
    };
    const mapped = points.map(mapPoint);
    const step = Math.max(1, Math.ceil(mapped.length / 2000));
    return mapped.filter((_, idx) => idx % step === 0);
  }

  const uploadSurvey = async (file: File) => {
    if (!token) return;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadSurveyResponse>("/api/upload-survey", formData, {
        token,
      });
      const storedFilename = data.stored_filename || file.name;
      setSurveyFileName(storedFilename);
      setSurveyDiagnostics({
        fileType: data.file_type,
        parseSuccess: data.parse_success,
        pointCount: data.point_count,
        contourCount: data.contour_count,
        recognizedColumns: data.recognized_columns,
        invalidRows: data.invalid_rows,
        bounds: data.bounds,
        elevationRange: data.elevation_range,
        warnings: data.warnings,
      });
      let pointsResponse: SurveyPointsResponse | null = null;
      if (storedFilename && (data.file_type || "").toLowerCase() === "csv") {
        pointsResponse = await postJson<SurveyPointsResponse>(
          "/api/survey/points",
          { filename: storedFilename },
          { token },
        );
        const points = Array.isArray(pointsResponse.points) ? pointsResponse.points : [];
        setSurveyPoints(points);
        setSurveyPreviewPoints(mapSurveyPointsToSite(points));
      } else {
        setSurveyPoints([]);
        setSurveyPreviewPoints([]);
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        survey_file: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          survey_url: data.survey_url || "",
        },
        survey_file_type: data.file_type,
        survey_parse_success: data.parse_success,
        survey_point_count: pointsResponse?.point_count ?? data.point_count ?? 0,
        survey_point_columns: pointsResponse?.recognized_columns ?? data.recognized_columns ?? {},
        survey_invalid_rows: pointsResponse?.invalid_rows ?? data.invalid_rows ?? 0,
        survey_point_warnings: pointsResponse?.warnings ?? data.warnings ?? [],
        survey_points: pointsResponse?.points ?? [],
        survey_bounds: data.bounds ?? null,
        survey_elevation_range: data.elevation_range ?? null,
        use_survey_for_grading: useSurveyForGrading,
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage(data.parse_success ? "Survey uploaded and parsed." : "Survey uploaded.");
    } catch (error) {
      setSurveyFileName(file.name);
      setStatusMessage(
        error instanceof Error ? error.message : "Survey upload failed.",
      );
    }
  };

  const mapDetectionToPlacement = useCallback(
    (
      detection: {
        kind: string;
        bbox: [number, number, number, number];
        confidence?: number;
        geometry_type?: "polygon" | "polyline" | "rect";
        geometry?: Array<[number, number]>;
      },
      imageWidth: number,
      imageHeight: number,
    ): BuildingPlacement | null => {
      if (!imageWidth || !imageHeight) return null;
      const [x, y, w, h] = detection.bbox;
      const width = parsePositiveNumber(lotWidth);
      const height = parsePositiveNumber(lotHeight);
      if (!width || !height) return null;
      const scaleFtPerPx = detectionScaleFtPerPx && detectionScaleFtPerPx > 0 ? detectionScaleFtPerPx : null;
      const mapPoint = (pt: [number, number]) => {
        const [px, py] = pt;
        const mappedX = scaleFtPerPx ? px * scaleFtPerPx : (px / imageWidth) * width;
        const mappedY = scaleFtPerPx ? py * scaleFtPerPx : (py / imageHeight) * height;
        return [mappedX, mappedY] as [number, number];
      };
      const mappedGeometry = Array.isArray(detection.geometry)
        ? detection.geometry.map((pt) => mapPoint(pt))
        : null;
      const geometryBounds = mappedGeometry?.length
        ? mappedGeometry.reduce(
            (acc, pt) => {
              return {
                minX: Math.min(acc.minX, pt[0]),
                minY: Math.min(acc.minY, pt[1]),
                maxX: Math.max(acc.maxX, pt[0]),
                maxY: Math.max(acc.maxY, pt[1]),
              };
            },
            {
              minX: Number.POSITIVE_INFINITY,
              minY: Number.POSITIVE_INFINITY,
              maxX: Number.NEGATIVE_INFINITY,
              maxY: Number.NEGATIVE_INFINITY,
            },
          )
        : null;
      const mappedX = geometryBounds
        ? geometryBounds.minX
        : scaleFtPerPx
          ? x * scaleFtPerPx
          : (x / imageWidth) * width;
      const mappedY = geometryBounds
        ? geometryBounds.minY
        : scaleFtPerPx
          ? y * scaleFtPerPx
          : (y / imageHeight) * height;
      const mappedW = geometryBounds
        ? geometryBounds.maxX - geometryBounds.minX
        : scaleFtPerPx
          ? w * scaleFtPerPx
          : (w / imageWidth) * width;
      const mappedD = geometryBounds
        ? geometryBounds.maxY - geometryBounds.minY
        : scaleFtPerPx
          ? h * scaleFtPerPx
          : (h / imageHeight) * height;
      const typeMap: Record<string, SiteObjectType> = {
        building: "building",
        road: "road",
        parking: "parking",
        sidewalk: "sidewalk",
        driveway: "driveway",
        basin: "basin",
        pool: "pool",
        open_space: "open_space",
      };
      const type = typeMap[detection.kind] ?? "building";
      const labelMap: Record<SiteObjectType, string> = {
        site: "Site",
        setback_zone: "Setback Zone",
        no_build_zone: "No-Build Zone",
        building: "Detected Building",
        retail_building: "Detected Retail",
        multifamily_building: "Detected Multifamily",
        industrial_building: "Detected Industrial",
        office_building: "Detected Office",
        pad: "Detected Pad",
        pool: "Detected Pool",
        amenity: "Detected Amenity",
        open_space: "Detected Open Space",
        entrance: "Detected Entrance",
        driveway: "Detected Driveway",
        road: "Detected Road",
        parking: "Detected Parking",
        sidewalk: "Detected Path",
        basin: "Detected Basin",
        outfall: "Detected Outfall",
        inlet: "Detected Inlet",
        manhole: "Detected Manhole",
        hydrant: "Detected Hydrant",
        utility_corridor: "Detected Utility Corridor",
        lot_block: "Detected Lot Block",
        bridge: "Detected Bridge",
        custom: "Detected Custom Geometry",
      };
      return {
        id: `detected_${Math.random().toString(36).slice(2, 9)}`,
        label: labelMap[type] ?? "Detected Object",
        x: clampValue(mappedX, 0, width - mappedW),
        y: clampValue(mappedY, 0, height - mappedD),
        w: Math.max(12, mappedW),
        d: Math.max(12, mappedD),
        rotation: 0,
        type,
        source: "detected_from_image",
        generated: false,
        confidence: detection.confidence ?? 0.2,
        confirmed: false,
        geometryType: detection.geometry_type,
        geometry: mappedGeometry ?? undefined,
        capabilities: { movable: true, resizable: true, rotatable: false, deletable: true },
        placed: true,
        meta: {
          detection_kind: detection.kind,
          confidence: detection.confidence ?? 0.2,
          detected: true,
          scale_source: scaleFtPerPx ? "calibrated" : "approximate",
          scale_ft_per_px: scaleFtPerPx ?? null,
        },
      };
    },
    [detectionScaleFtPerPx, lotHeight, lotWidth],
  );


  const handleAnalyzeImageFeatures = useCallback(async (overridePath?: string) => {
    if (!token) return;
    const sourcePath = overridePath || mapSnapshotPath;
    if (!sourcePath) {
      askClarification(
        "Upload a site image or map snapshot before running detection. Want me to open the Site Inputs panel?",
        "upload_image_then_detect",
      );
      return;
    }
    clearGeneratedPreview();
    setImageUploadState("detecting");
    setImageUploadNote("Detecting site features…");
    const width = parsePositiveNumber(lotWidth);
    const height = parsePositiveNumber(lotHeight);
    if (!width || !height) {
      askClarification(
        "I need the site boundary dimensions before detection. What size should the site be?",
        "set_site_then_detect",
      );
      setImageUploadState("uploaded");
      setImageUploadNote("Image uploaded. Set site dimensions to run detection.");
      return;
    }
    try {
      const result = await postJson<ImageDetectResponse>(
        "/api/image/detect-features",
        { image_path: sourcePath, source_type: "map" },
        { token },
      );
      const detections = Array.isArray(result.detections) ? result.detections : [];
      const mapped = detections
        .map((det) => mapDetectionToPlacement(det, result.image_width ?? 0, result.image_height ?? 0))
        .filter((item): item is BuildingPlacement => Boolean(item));
      setDetectedPlacements(mapped);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        detected_objects: mapped,
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setImageUploadState("uploaded");
      setImageUploadNote(mapped.length ? "Detection complete. Review suggested objects." : "No detections found.");
      setStatusMessage(result.success ? "Detection complete. Review suggested objects." : result.message || "Detection failed.");
    } catch (error) {
      setImageUploadState("failed");
      setImageUploadNote("Detection failed.");
      setStatusMessage(error instanceof Error ? error.message : "Detection failed.");
    }
  }, [
    askClarification,
    clearGeneratedPreview,
    currentProject,
    lotHeight,
    lotWidth,
    mapDetectionToPlacement,
    mapSnapshotPath,
    payloadPreview,
    saveProject,
    token,
  ]);

  const handleAnalyzeSiteAccess = useCallback(() => {
    const confirmed = buildingPlacements.filter(
      (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
    );
    const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
    const buildingTypes = new Set<SiteObjectType>([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
    ]);
    const buildings = confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType));
    const access = confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType));
    if (!buildings.length || !access.length) {
      setAnalysisIssues([]);
      setAnalysisPaths([]);
      setAnalysisSelectedIssueId(null);
      setAnalysisFocusLocked(false);
      let reason = "Address provides site context only. Add or confirm buildings and access objects to run analysis.";
      if (!buildings.length && access.length) {
        reason = "Add or confirm buildings to run access analysis.";
      }
      if (!access.length && buildings.length) {
        reason = "Add or confirm roads, driveways, or access objects to run access analysis.";
      }
      setAnalysisEmptyReason(reason);
      askClarification(reason, "access_analysis_missing");
      return;
    }
    setAnalysisEmptyReason(null);
    const issues: Array<{
      id: string;
      buildingId: string;
      accessId: string;
      distanceFt: number;
      thresholdFt: number;
      message: string;
      pathId: string;
      issueType: "distance" | "no_access" | "no_buildings" | "no_access_objects";
    }> = [];
    const paths: Array<{
      id: string;
      buildingId: string;
      accessId: string;
      from: { x: number; y: number };
      to: { x: number; y: number };
      label: string;
      points?: Array<{ x: number; y: number }>;
    }> = [];
    const threshold = 150;
    const adjacencyGap = 25;
    const buildingAccessGap = 60;

    type GraphEdge = { to: string; weight: number; points: Array<{ x: number; y: number }> };
    const graph: Record<string, GraphEdge[]> = {};

    const addEdge = (from: string, to: string, weight: number, points: Array<{ x: number; y: number }>) => {
      if (!graph[from]) graph[from] = [];
      graph[from].push({ to, weight, points });
    };

    const clampToRect = (pt: { x: number; y: number }, rect: { x: number; y: number; w: number; d: number }) => ({
      x: Math.min(Math.max(pt.x, rect.x), rect.x + rect.w),
      y: Math.min(Math.max(pt.y, rect.y), rect.y + rect.d),
    });

    const distancePointToRect = (pt: { x: number; y: number }, rect: { x: number; y: number; w: number; d: number }) => {
      const closest = clampToRect(pt, rect);
      const dx = pt.x - closest.x;
      const dy = pt.y - closest.y;
      return { distance: Math.hypot(dx, dy), closest };
    };

    const closestPointOnSegment = (
      a: { x: number; y: number },
      b: { x: number; y: number },
      p: { x: number; y: number },
    ) => {
      const abx = b.x - a.x;
      const aby = b.y - a.y;
      const ab2 = abx * abx + aby * aby;
      if (!ab2) return { x: a.x, y: a.y };
      const t = ((p.x - a.x) * abx + (p.y - a.y) * aby) / ab2;
      const clamped = Math.max(0, Math.min(1, t));
      return { x: a.x + abx * clamped, y: a.y + aby * clamped };
    };

    const getAccessPolyline = (item: BuildingPlacement): Array<{ x: number; y: number }> => {
      if (item.geometryType === "polyline" && Array.isArray(item.geometry) && item.geometry.length > 1) {
        return item.geometry.map(([x, y]) => ({ x, y }));
      }
      const x = item.x ?? 0;
      const y = item.y ?? 0;
      const isHorizontal = item.w >= item.d;
      if (item.type === "parking") {
        const params = (item.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
        const stallDepth = Number.isFinite(params.stallDepth) ? Number(params.stallDepth) : 18;
        const aisleWidth = Number.isFinite(params.aisleWidth) ? Number(params.aisleWidth) : 24;
        const angleDeg = Number.isFinite(params.angleDeg) ? Number(params.angleDeg) : 90;
        const loading = params.loading === "single" ? "single" : "double";
        const angleRad = (Math.max(Math.min(angleDeg, 89), 0) * Math.PI) / 180;
        const depthAdj = stallDepth / Math.cos(angleRad || 0.0001);
        const moduleDepth = depthAdj * (loading === "double" ? 2 : 1) + aisleWidth;
        const scale = item.d < moduleDepth ? item.d / moduleDepth : 1;
        const scaledStall = depthAdj * scale;
        const scaledAisle = aisleWidth * scale;
        const centerY =
          loading === "double"
            ? y + (item.d - scaledAisle) / 2 + scaledAisle / 2
            : y + scaledStall + scaledAisle / 2;
        const start = { x: x + 4, y: centerY };
        const end = { x: x + item.w - 4, y: centerY };
        return [start, end];
      }
      if (isHorizontal) {
        return [
          { x, y: y + item.d / 2 },
          { x: x + item.w, y: y + item.d / 2 },
        ];
      }
      return [
        { x: x + item.w / 2, y },
        { x: x + item.w / 2, y: y + item.d },
      ];
    };

    const accessPaths = access.map((item) => ({
      id: item.id,
      type: item.type,
      points: getAccessPolyline(item),
    }));

    accessPaths.forEach((path) => {
      const points = path.points;
      if (points.length < 2) return;
      for (let i = 0; i < points.length - 1; i += 1) {
        const a = points[i];
        const b = points[i + 1];
        const weight = Math.hypot(b.x - a.x, b.y - a.y);
        const nodeA = `${path.id}-p${i}`;
        const nodeB = `${path.id}-p${i + 1}`;
        addEdge(nodeA, nodeB, weight, [a, b]);
        addEdge(nodeB, nodeA, weight, [b, a]);
      }
    });

    const pathEndpoints = accessPaths
      .map((path) => {
        const points = path.points;
        if (points.length < 2) return null;
        return [
          { id: `${path.id}-p0`, point: points[0] },
          { id: `${path.id}-p${points.length - 1}`, point: points[points.length - 1] },
        ];
      })
      .flat()
      .filter(Boolean) as Array<{ id: string; point: { x: number; y: number } }>;

    for (let i = 0; i < pathEndpoints.length; i += 1) {
      for (let j = i + 1; j < pathEndpoints.length; j += 1) {
        const a = pathEndpoints[i];
        const b = pathEndpoints[j];
        const distance = Math.hypot(a.point.x - b.point.x, a.point.y - b.point.y);
        if (distance <= adjacencyGap) {
          addEdge(a.id, b.id, Math.max(distance, 1), [a.point, b.point]);
          addEdge(b.id, a.id, Math.max(distance, 1), [b.point, a.point]);
        }
      }
    }

    const buildPathPoints = (edgePoints: Array<Array<{ x: number; y: number }>>) => {
      const points: Array<{ x: number; y: number }> = [];
      edgePoints.forEach((segment) => {
        segment.forEach((pt, idx) => {
          if (!points.length) {
            points.push(pt);
            return;
          }
          const last = points[points.length - 1];
          if (Math.hypot(last.x - pt.x, last.y - pt.y) < 0.01) return;
          if (idx === 0) {
            points.push(pt);
            return;
          }
          points.push(pt);
        });
      });
      return points;
    };

    buildings.forEach((building) => {
      const buildingNodeId = `building-${building.id}`;
      const buildingRect = { x: building.x ?? 0, y: building.y ?? 0, w: building.w, d: building.d };
      graph[buildingNodeId] = [];
      accessPaths.forEach((path) => {
        const points = path.points;
        if (points.length < 2) return;
        let closestDistance = Number.POSITIVE_INFINITY;
        let closestPoint: { x: number; y: number } | null = null;
        let closestNodeId: string | null = null;
        for (let i = 0; i < points.length - 1; i += 1) {
          const a = points[i];
          const b = points[i + 1];
          const segmentPoint = closestPointOnSegment(a, b, {
            x: buildingRect.x + buildingRect.w / 2,
            y: buildingRect.y + buildingRect.d / 2,
          });
          const { distance } = distancePointToRect(segmentPoint, buildingRect);
          if (distance < closestDistance) {
            closestDistance = distance;
            closestPoint = segmentPoint;
            closestNodeId = `${path.id}-p${i}`;
          }
        }
        if (closestPoint && closestNodeId && closestDistance <= buildingAccessGap) {
          addEdge(buildingNodeId, closestNodeId, Math.max(closestDistance, 1), [
            clampToRect(closestPoint, buildingRect),
            closestPoint,
          ]);
        }
      });

      const distances = new Map<string, number>();
      const prev = new Map<string, { node: string; points: Array<{ x: number; y: number }> }>();
      const unvisited = new Set<string>(Object.keys(graph));
      distances.set(buildingNodeId, 0);

      while (unvisited.size) {
        let current: string | null = null;
        let bestDistance = Number.POSITIVE_INFINITY;
        unvisited.forEach((nodeId) => {
          const dist = distances.get(nodeId);
          if (dist !== undefined && dist < bestDistance) {
            bestDistance = dist;
            current = nodeId;
          }
        });
        if (!current) break;
        unvisited.delete(current);
        const edges = graph[current] ?? [];
        edges.forEach((edge) => {
          if (!unvisited.has(edge.to)) return;
          const nextDist = bestDistance + edge.weight;
          const existing = distances.get(edge.to);
          if (existing === undefined || nextDist < existing) {
            distances.set(edge.to, nextDist);
            prev.set(edge.to, { node: current as string, points: edge.points });
          }
        });
      }

      let closestAccessId: string | null = null;
      let closestDistance = Number.POSITIVE_INFINITY;
      let closestNodeId: string | null = null;
      accessPaths.forEach((path) => {
        path.points.forEach((_, idx) => {
          const nodeId = `${path.id}-p${idx}`;
          const dist = distances.get(nodeId);
          if (dist !== undefined && dist < closestDistance) {
            closestDistance = dist;
            closestNodeId = nodeId;
            closestAccessId = path.id;
          }
        });
      });

      if (!closestAccessId || !Number.isFinite(closestDistance)) {
        issues.push({
          id: `${building.id}-no-access`,
          buildingId: building.id,
          accessId: "",
          distanceFt: 0,
          thresholdFt: threshold,
          message: `Building ${building.label} has no access path.`,
          pathId: "",
          issueType: "no_access",
        });
        return;
      }

      const edgePoints: Array<Array<{ x: number; y: number }>> = [];
      let cursor: string | null = closestNodeId;
      while (cursor && cursor !== buildingNodeId) {
        const step = prev.get(cursor);
        if (!step) break;
        edgePoints.unshift(step.points);
        cursor = step.node;
      }

      const points = buildPathPoints(edgePoints);
      const from = points[0] ?? { x: buildingRect.x, y: buildingRect.y };
      const to = points[points.length - 1] ?? from;
      const pathId = `${building.id}-${closestAccessId}`;
      paths.push({
        id: pathId,
        buildingId: building.id,
        accessId: closestAccessId,
        from,
        to,
        label: `Access ${Math.round(closestDistance)} ft`,
        points,
      });
      if (closestDistance > threshold) {
        issues.push({
          id: `${building.id}-distance`,
          buildingId: building.id,
          accessId: closestAccessId,
          distanceFt: closestDistance,
          thresholdFt: threshold,
          message: `Building ${building.label} is ${Math.round(closestDistance)} ft from nearest access (>${threshold} ft).`,
          pathId,
          issueType: "distance",
        });
      }
    });

    setAnalysisIssues(issues);
    setAnalysisPaths(paths);
    setAnalysisSelectedIssueId(issues[0]?.id ?? null);
    setAnalysisFocusLocked(Boolean(issues[0]?.id));
    setStatusMessage("Site access analysis complete (conceptual).");
  }, [askClarification, buildingPlacements]);


  useEffect(() => {
    if (!analysisSelectedIssueId) {
      setAnalysisFocusLocked(false);
    }
  }, [analysisSelectedIssueId]);

  const persistSiteRotation = useCallback(
    async (nextValue: number) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        site_rotation_deg: nextValue,
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
    },
    [currentProject, payloadPreview, saveProject],
  );

  const scheduleRotationSave = useCallback(
    (nextValue: number) => {
      if (rotationSaveTimeoutRef.current) {
        window.clearTimeout(rotationSaveTimeoutRef.current);
      }
      rotationSaveTimeoutRef.current = window.setTimeout(() => {
        void persistSiteRotation(nextValue);
        rotationSaveTimeoutRef.current = null;
      }, 400);
    },
    [persistSiteRotation],
  );

  useEffect(() => {
    if (activePlacementId) return;
    const pending = buildingPlacements.find((item) => !item.placed && item.type !== "site");
    if (pending) {
      setActivePlacementId(pending.id);
    }
  }, [activePlacementId, buildingPlacements]);

  const analyzeMapSnapshot = async () => {
    if (!token || !mapSnapshotPath) return;
    try {
      const data = await postJson<MapAnalysis>(
        "/api/image/analyze",
        {
          image_path: mapSnapshotPath,
          source_name: "map_snapshot",
          source_type: "map",
        },
        { token },
      );
      setMapAnalysis(data);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        map_analysis: data,
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Map snapshot analyzed.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Map snapshot analysis failed.",
      );
    }
  };

  const autoFitSite = useCallback(
    (
      width: number,
      height: number,
      label?: string,
      siteIdOverride?: string | null,
      fitMap: boolean = true,
      lockSite: boolean = true,
      preserveExistingObjects: boolean = true,
    ) => {
      const clampedW = Math.max(width, 1);
      const clampedH = Math.max(height, 1);
      setLotWidth(clampedW.toFixed(0));
      setLotHeight(clampedH.toFixed(0));
      setSiteScaleLocked(lockSite);
      setBuildingPlacements((prev) => {
        const filtered = preserveExistingObjects ? prev.filter((item) => item.type !== "site") : [];
        const existingSite = prev.find((item) => item.type === "site");
        const siteId =
          siteIdOverride ||
          existingSite?.id ||
          `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const siteLabel = label || existingSite?.label || "Site Boundary";
        return [
          {
            id: siteId,
            label: siteLabel,
            type: "site",
            w: clampedW,
            d: clampedH,
            x: 0,
            y: 0,
            rotation: 0,
            locked: lockSite,
            placed: true,
            source: "user",
            generated: false,
            capabilities: {
              movable: !lockSite,
              resizable: !lockSite,
              rotatable: !lockSite,
              deletable: false,
            },
            systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
            meta: {
              category: "site",
              site_boundary_state: lockSite ? "locked_canonical" : "draft_editable",
              source_ui_mode: "site_setup",
              engineering_status: "review_required",
              construction_release_allowed: false,
              acres: Number(((clampedW * clampedH) / SQFT_PER_ACRE).toFixed(3)),
            },
          },
          ...filtered,
        ];
      });
      if (fitMap) {
        setFitToSiteRequest((value) => value + 1);
      }
    },
    [],
  );

  const handleToggleSiteLock = useCallback(() => {
    if (siteScaleLocked) return;
    const lastApplied = lastAppliedSiteRef.current;
    if (lastApplied?.w && lastApplied?.h) {
      autoFitSite(lastApplied.w, lastApplied.h, "Site Boundary", undefined, false, true);
    }
    setSiteScaleLocked(true);
    setShowSiteBounds(false);
    setFitToSiteRequest((value) => value + 1);
    const currentInput = currentProject?.project_input ?? payloadPreview;
    void saveProject({
      silent: true,
      projectInputOverride: {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: {
            ...(currentInput?.meta?.site_inputs ?? {}),
            site_alignment_locked: true,
          },
        },
      },
    });
    setBuildingPlacements((prevPlacements) =>
      prevPlacements.map((item) =>
        item.type === "site"
          ? {
              ...item,
              locked: true,
              meta: {
                ...(item.meta ?? {}),
                site_boundary_state: "locked_canonical",
                engineering_status: "review_required",
                construction_release_allowed: false,
              },
              capabilities: {
                ...item.capabilities,
                movable: false,
                resizable: false,
                rotatable: false,
              },
            }
          : item,
      ),
    );
    setStatusMessage("Site alignment locked.");
  }, [autoFitSite, currentProject, payloadPreview, saveProject, siteScaleLocked]);

  const handleUnlockSite = useCallback(() => {
    if (!siteScaleLocked) return;
    setSiteScaleLocked(false);
    setShowSiteBounds(true);
    setSiteSelectionMode(true);
    lastViewportSyncRef.current = null;
    const currentInput = currentProject?.project_input ?? payloadPreview;
    void saveProject({
      silent: true,
      projectInputOverride: {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: {
            ...(currentInput?.meta?.site_inputs ?? {}),
            site_alignment_locked: false,
          },
        },
      },
    });
    setBuildingPlacements((prevPlacements) =>
      prevPlacements.map((item) =>
        item.type === "site"
          ? {
              ...item,
              locked: false,
              meta: {
                ...(item.meta ?? {}),
                site_boundary_state: "draft_editable",
                engineering_status: "review_required",
                construction_release_allowed: false,
              },
              capabilities: {
                ...item.capabilities,
                movable: true,
                resizable: true,
                rotatable: true,
              },
            }
          : item,
      ),
    );
    setStatusMessage("Site unlocked for editing.");
  }, [currentProject, payloadPreview, saveProject, siteScaleLocked]);

  const handleStartBlankSite = useCallback(() => {
    const width = DEFAULT_BLANK_SITE_WIDTH_FT;
    const height = DEFAULT_BLANK_SITE_DEPTH_FT;
    const blankSiteName = "Blank Site";
    const blankFileName = "blank-site";
    clearGeneratedPreview();
    setSiteName(blankSiteName);
    setFileName(blankFileName);
    setSiteNameAuto(false);
    setFileNameAuto(false);
    setSiteAddress("");
    setSelectedAddressSuggestion(null);
    setAddressSuggestions([]);
    setUploadedImagePreviewUrl("");
    setUploadedImageApiUrl("");
    setMapSnapshotPath("");
    setMapAnalysis(null);
    setDetectedPlacements([]);
    setAnalysisIssues([]);
    setAnalysisPaths([]);
    setAnalysisSelectedIssueId(null);
    setIssues([]);
    setSelectedIssueId(null);
    setAssumptions(defaultAssumptions);
    setFocusDetectedId(null);
    setFocusObjectId(null);
    setSystemStatuses(DEFAULT_SYSTEM_STATUS);
    setSiteSelectionMode(true);
    setShowSiteBounds(true);
    setPreviewInteraction("edit");
    autoFitSite(width, height, "Blank Site Boundary", undefined, true, false, false);
    lastAppliedSiteRef.current = null;
    const currentInput = currentProject?.project_input ?? payloadPreview;
    const nextSiteInputs: Record<string, unknown> = {
      ...(currentInput?.meta?.site_inputs ?? {}),
      site_alignment_locked: false,
      site_boundary_source: "blank_user_defined",
      site_boundary_state: "draft_editable",
    };
    delete nextSiteInputs.address;
    delete nextSiteInputs.geocode;
    delete nextSiteInputs.map_analysis;
    delete nextSiteInputs.viewport_bounds;
    const nextProjectInput: ProjectInput = {
      ...currentInput,
      input_mode: "user",
      strict_mode: false,
      allow_ai_fill_for_blanks: false,
      meta: {
        ...(currentInput?.meta ?? {}),
        site_inputs: nextSiteInputs,
      },
      manual_fields: {
        ...(currentInput?.manual_fields ?? {}),
        project_name: blankSiteName,
        lot: {
          x: 0,
          y: 0,
          w: width,
          h: height,
        },
      },
    };
    setCurrentProject((project) =>
      project
        ? {
            ...project,
            name: blankSiteName,
            description: "Blank user-defined site.",
            project_input: nextProjectInput,
            latest_result: undefined,
            has_result: false,
          }
        : project,
    );
    void saveProject({
      silent: true,
      nameOverride: blankSiteName,
      fileNameOverride: blankFileName,
      autoNamedOverride: false,
      autoFileNamedOverride: false,
      projectInputOverride: {
        ...nextProjectInput,
      },
    });
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setLeftSidebarOpen(false);
    }
    setStatusMessage("Blank site started. Set dimensions, draw the boundary, then lock it for review.");
  }, [
    autoFitSite,
    clearGeneratedPreview,
    currentProject,
    payloadPreview,
    saveProject,
  ]);

  const handleStartSiteBoundaryDraw = useCallback(() => {
    const width = parsePositiveNumber(lotWidth);
    const height = parsePositiveNumber(lotHeight);
    if (!width || !height) {
      setStatusMessage("Set site width and depth before drawing the boundary.");
      return;
    }
    if (siteScaleLocked) {
      handleUnlockSite();
    }
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setShowSiteBounds(true);
    setSiteSelectionMode(true);
    setPreviewInteraction("edit");
    setSiteDrawRequest((value) => value + 1);
    setStatusMessage("Draw the site boundary on the canvas. Double-click or use Finish to lock it.");
  }, [handleUnlockSite, lotHeight, lotWidth, siteScaleLocked]);

  useEffect(() => {
    if (siteScaleLocked) return;
    if (!viewportFootprint?.widthFt || !viewportFootprint?.heightFt) return;
    const nextWidth = viewportFootprint.widthFt;
    const nextHeight = viewportFootprint.heightFt;
    const last = lastViewportSyncRef.current;
    if (last && Math.abs(last.w - nextWidth) < 1 && Math.abs(last.h - nextHeight) < 1) {
      return;
    }
    lastViewportSyncRef.current = { w: nextWidth, h: nextHeight };
  }, [siteScaleLocked, viewportFootprint]);

  useEffect(() => {
    if (addressSuggestTimeoutRef.current) {
      window.clearTimeout(addressSuggestTimeoutRef.current);
    }
    const trimmed = siteAddress.trim();
    if (!trimmed || trimmed.length < 4) {
      setAddressSuggestions([]);
      return;
    }
    addressSuggestTimeoutRef.current = window.setTimeout(() => {
      const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
      const fallbackToMapbox = () => {
        if (!mapboxToken) {
          setAddressSuggestions([]);
          return;
        }
        const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(trimmed)}.json?access_token=${mapboxToken}&autocomplete=true&limit=5`;
        fetch(url)
          .then((resp) => resp.json())
          .then((data) => {
            const features = Array.isArray(data?.features) ? data.features : [];
            const suggestions = features
              .map((feature: { center?: [number, number]; place_name?: string }) => {
                if (!feature?.center || feature.center.length < 2) return null;
                return {
                  lat: feature.center[1],
                  lng: feature.center[0],
                  display_name: feature.place_name || trimmed,
                  provider: "mapbox",
                };
              })
              .filter(Boolean) as AddressSuggestion[];
            setAddressSuggestions(suggestions);
          })
          .catch(() => {
            setAddressSuggestions([]);
          });
      };
      if (!token) {
        fallbackToMapbox();
        return;
      }
      void postJson<AddressSuggestion>(
        "/api/geocode",
        { address: trimmed },
        { token },
      )
        .then((result) => {
          if (hasAddressCoordinates(result)) {
            setAddressSuggestions([result]);
          } else if (result?.blocked || result?.status) {
            setAddressSuggestions([]);
          } else {
            fallbackToMapbox();
          }
        })
        .catch(() => {
          fallbackToMapbox();
        });
    }, 350);
    return () => {
      if (addressSuggestTimeoutRef.current) {
        window.clearTimeout(addressSuggestTimeoutRef.current);
      }
    };
  }, [siteAddress, token]);

  const handleApplySite = useCallback(async () => {
    if (applyingSiteRef.current) return;
    if (siteScaleLocked) {
      if (hasSiteBoundary()) {
        setStatusMessage("Site is already locked.");
        return;
      }
      setSiteScaleLocked(false);
    }
    applyingSiteRef.current = true;
    const visibleWidth = parsePositiveNumber(lotWidth);
    const visibleHeight = parsePositiveNumber(lotHeight);
    const width = visibleWidth ?? viewportFootprint?.widthFt;
    const height = visibleHeight ?? viewportFootprint?.heightFt;
    if (!width || !height) {
      setStatusMessage("Set the site width and height before applying the site.");
      applyingSiteRef.current = false;
      return;
    }
    const selectedAreaAcres = siteAreaAcresFromSize(width, height);
    if (selectedAreaAcres > SITE_WARNING_ACRES) {
      setStatusMessage(OVERSIZED_SITE_MESSAGE);
      applyingSiteRef.current = false;
      return;
    }
    const lastApplied = lastAppliedSiteRef.current;
    if (
      lastApplied &&
      Math.abs(lastApplied.w - width) < 1 &&
      Math.abs(lastApplied.h - height) < 1 &&
      (!viewportCenter ||
        (Math.abs((lastApplied.lat ?? 0) - viewportCenter.lat) < 1e-6 &&
          Math.abs((lastApplied.lng ?? 0) - viewportCenter.lng) < 1e-6))
    ) {
      setStatusMessage("Site already matches the current viewport.");
      applyingSiteRef.current = false;
      return;
    }
    autoFitSite(width, height, "Site Boundary", undefined, false, true);
    setShowSiteBounds(false);
    setSiteScaleLocked(true);
    const currentInput = currentProject?.project_input ?? payloadPreview;
    const nextSiteInputs = {
      ...(currentInput?.meta?.site_inputs ?? {}),
      site_alignment_locked: true,
      ...(viewportFootprint?.bounds
        ? {
            viewport_bounds: {
              north: viewportFootprint.bounds.north,
              south: viewportFootprint.bounds.south,
              east: viewportFootprint.bounds.east,
              west: viewportFootprint.bounds.west,
              center_lat: viewportFootprint.bounds.centerLat,
              center_lng: viewportFootprint.bounds.centerLng,
              width_ft: width,
              height_ft: height,
            },
          }
        : {}),
      ...(viewportCenter
        ? {
            geocode: {
              ...(currentInput?.meta?.site_inputs?.geocode ?? {}),
              lat: viewportCenter.lat,
              lng: viewportCenter.lng,
              display_name:
                currentInput?.meta?.site_inputs?.geocode?.display_name ?? "Map center",
            },
          }
        : {}),
    };
    await saveProject({
      silent: true,
      projectInputOverride: {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: nextSiteInputs,
        },
        manual_fields: {
          ...(currentInput?.manual_fields ?? {}),
          lot: {
            x: 0,
            y: 0,
            w: width,
            h: height,
          },
        },
      },
    });
    setSiteSelectionMode(false);
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setLeftSidebarOpen(false);
    }
    setStatusMessage("Site applied and locked.");
    lastAppliedSiteRef.current = {
      w: width,
      h: height,
      lat: viewportCenter?.lat,
      lng: viewportCenter?.lng,
    };
    applyingSiteRef.current = false;
  }, [
    autoFitSite,
    currentProject,
    lotHeight,
    lotWidth,
    payloadPreview,
    saveProject,
    viewportCenter,
    viewportFootprint,
  ]);

  const runSelectedDetections = useCallback(async () => {
    const wantsContext = detectionChoices.roads || detectionChoices.buildings || detectionChoices.parking;
    if (wantsContext) {
      if (!mapSnapshotPath) {
        setStatusMessage("Upload a map snapshot to detect existing context.");
      } else {
        await handleAnalyzeImageFeatures();
      }
    }
    if (detectionChoices.grading) {
      await handleGenerateSystemRef.current?.("grading");
    }
    if (!wantsContext && !detectionChoices.grading) {
      setStatusMessage("Select at least one detection option.");
    }
  }, [detectionChoices, handleAnalyzeImageFeatures, mapSnapshotPath]);

  useEffect(() => {
    if (!siteScaleLocked) return;
    const hasSite = buildingPlacements.some((item) => item.type === "site");
    if (!hasSite) return;
    setFitToSiteRequest((value) => value + 1);
  }, [activeSidePanel, buildingPlacements, previewHeightPx, siteScaleLocked]);

  const saveSiteAddress = async () => {
    if (!token) return;
    const trimmed = siteAddress.trim();
    const currentInput = currentProject?.project_input ?? payloadPreview;
    const nextSiteInputs = {
      ...(currentInput?.meta?.site_inputs ?? {}),
      address: trimmed || undefined,
    };
    if (!trimmed) {
      setSelectedAddressSuggestion(null);
      setAddressSuggestions([]);
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Site address cleared.");
      return;
    }
    try {
      let geocode = selectedAddressSuggestion;
      if (!hasAddressCoordinates(geocode)) {
        geocode = await postJson<AddressSuggestion>("/api/geocode", { address: trimmed }, { token });
      }
      if (!hasAddressCoordinates(geocode)) {
        const geocodeMessage =
          geocode?.message ||
          geocode?.blockers?.find((item) => item?.message)?.message ||
          "Address lookup did not return usable map coordinates.";
        setStatusMessage(`${geocodeMessage} The map was not moved. You can still set site size or draw the boundary manually.`);
        return;
      }
      clearGeneratedPreview();
      nextSiteInputs.address = geocode.display_name;
      nextSiteInputs.geocode = {
        lat: geocode.lat,
        lng: geocode.lng,
        display_name: geocode.display_name,
        provider: geocode.provider ?? "nominatim",
        confidence: geocode.confidence ?? null,
        crs: geocode.crs ?? { epsg: "EPSG:4326", units: "degrees" },
        location_context: geocode.location_context ?? undefined,
      };
      nextSiteInputs.location_context =
        geocode.location_context ?? {
          address: geocode.display_name,
          normalized_address: geocode.display_name,
          coordinates: { lat: geocode.lat, lng: geocode.lng },
          crs: geocode.crs ?? { epsg: "EPSG:4326", units: "degrees" },
          evidence_source: geocode.provider ?? "geocoder",
          truth_label:
            "Address/geocode is location context only; it is not a site boundary, survey, control, or construction approval.",
        };
      nextSiteInputs.site_alignment_locked = false;
      setAddressSuggestions([]);
      setActiveWorkspaceMode("setup");
      setActiveSidePanel("site_existing");
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
          manual_fields: currentInput?.manual_fields,
        },
      });
      setSiteScaleLocked(false);
      setShowSiteBounds(true);
      setPreviewQuality("high");
      setSiteSelectionMode(true);
      setViewportCenter({ lat: geocode.lat, lng: geocode.lng });
      setStatusMessage("Address applied as location evidence. Set site size, draw the boundary, then lock it.");
      setSelectedAddressSuggestion(geocode);
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Geocoding failed.",
      );
    }
  };

  const handleMapCenter = useCallback(
    async (payload: { lat: number; lng: number }) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        geocode: {
          ...(currentInput?.meta?.site_inputs?.geocode ?? {}),
          lat: payload.lat,
          lng: payload.lng,
          display_name: currentInput?.meta?.site_inputs?.geocode?.display_name ?? "Map center",
        },
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setFitToSiteRequest((value) => value + 1);
      setStatusMessage("Site centered on the map view.");
    },
    [currentProject, payloadPreview, saveProject],
  );

  const requestPreview = async (
    payload: PreviewRequestPayload,
    options?: { silent?: boolean; track?: boolean },
  ) => {
    if (!token) return;
    if (options?.track) {
      setPreviewRefreshing(true);
      setPreviewRefreshNote((prev) => prev || "Refreshing preview...");
    }
    const previewPayload = {
      ...payload,
      preview_quality: previewQuality,
      label_density: previewLabelDensity,
      render_labels: previewInteraction !== "static" || previewQuality === "high",
      preview_mode: "production",
      preview_layers: previewLayerList,
    };
    try {
      const data = await postJson<PreviewResponse>("/api/preview", previewPayload, {
        token,
      });
      setPlanPreviewUrl(data.preview_image_data_url);
      setPlanPreviewProjectId(projectId || currentProject?.project_id || null);
      setPlanPreviewSummary(data.summary ?? null);
      setPlanPreviewAnnotations(data.preview_annotations ?? null);
      if (!options?.silent) {
        setStatusMessage("Plan preview generated.");
      }
    } finally {
      if (options?.track) {
        setPreviewRefreshing(false);
        setPreviewRefreshNote(null);
      }
    }
  };

  const requestPreviewInBackground = (
    payload: PreviewRequestPayload,
    options?: { loadingMessage?: string; successMessage?: string; silentStatus?: boolean; track?: boolean },
  ) => {
    if (!token) return;
    if (options?.loadingMessage && !options?.silentStatus) {
      setStatusMessage(options.loadingMessage);
    }
    void requestPreview(payload, { silent: true, track: options?.track })
      .then(() => {
        if (options?.successMessage && !options?.silentStatus) {
          setStatusMessage(options.successMessage);
        }
      })
      .catch((error) => {
        if (!options?.silentStatus) {
          setStatusMessage(
            error instanceof Error ? error.message : "Preview generation failed.",
          );
        }
        if (options?.track) {
          setPreviewRefreshing(false);
          setPreviewRefreshNote(null);
        }
      });
  };

  useEffect(() => {
    if (planPreviewProjectId && projectId && planPreviewProjectId !== projectId) {
      debugLog("discard-preview-project-mismatch", {
        planPreviewProjectId,
        projectId,
      });
      clearGeneratedPreview();
      return;
    }
    if (!buildingPlacements.length && !detectedPlacements.length && planPreviewUrl && !backendResult) {
      debugLog("discard-preview-empty-canonical");
      clearGeneratedPreview();
    }
  }, [
    backendResult,
    buildingPlacements.length,
    clearGeneratedPreview,
    debugLog,
    detectedPlacements.length,
    planPreviewProjectId,
    planPreviewUrl,
    projectId,
  ]);

  useEffect(() => {
    if (!token || !backendResult) return;
    const finalPlan =
      backendResult?.final_plan && typeof backendResult.final_plan === "object"
        ? backendResult.final_plan
        : {};
    const finalMeta =
      finalPlan?.meta && typeof finalPlan.meta === "object" ? finalPlan.meta : {};
    const actions = Array.isArray(finalPlan?.actions)
      ? finalPlan.actions.filter((item: unknown) => item && typeof item === "object")
      : [];
    const phaseCheckpoints =
      finalMeta?.phase_checkpoints && typeof finalMeta.phase_checkpoints === "object"
        ? finalMeta.phase_checkpoints
        : {};
    const runtimeCheckpoint =
      finalMeta?.runtime_phase_checkpoint && typeof finalMeta.runtime_phase_checkpoint === "object"
        ? finalMeta.runtime_phase_checkpoint
        : {};
    const jobProgress =
      backendResult?.job_progress && typeof backendResult.job_progress === "object"
        ? backendResult.job_progress
        : {};
    const hasRecoverablePreviewState =
      actions.length > 0 ||
      Object.keys(phaseCheckpoints).length > 0 ||
      Object.keys(runtimeCheckpoint).length > 0 ||
      Boolean(jobProgress.stage);

    if (!hasRecoverablePreviewState) return;

    const recoveryKey = JSON.stringify({
      projectId,
      actionCount: actions.length,
      phaseKeys: Object.keys(phaseCheckpoints),
      checkpointStage: String(runtimeCheckpoint.stage_name || ""),
      jobStage: String(jobProgress.stage || ""),
      stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
    });

    if (previewRecoveryKeyRef.current === recoveryKey) return;
    previewRecoveryKeyRef.current = recoveryKey;

    requestPreviewInBackground(
      {
        project_id: projectId || currentProject?.project_id || null,
        result: backendResult,
        filename_stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
      },
      {
        silentStatus: true,
      },
    );
  }, [token, backendResult, projectId, fileName, currentProject?.name, siteName]);

  const loadProjectResultInBackground = (project: ProjectRecord) => {
    if (!token) return;
    const requestId = projectResultLoadRequestRef.current + 1;
    projectResultLoadRequestRef.current = requestId;
    void getJson<{ project_id: string; latest_result: PlanResponse }>(
      `/api/projects/${project.project_id}/result`,
      { token },
    )
      .then((data) => {
        if (projectResultLoadRequestRef.current !== requestId) {
          return;
        }
        const latestResult = data.latest_result ?? {};
        if (latestResult && Object.keys(latestResult).length) {
          const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
          const hasStaleSystems = Object.values(systemStatuses).some(
            (status) => status === "stale",
          );
          const shouldSuppressLatestResult =
            hasStaleSystems &&
            activeStatus !== "running" &&
            activeStatus !== "queued" &&
            activeStatus !== "awaiting_approval";
          if (shouldSuppressLatestResult) {
            return;
          }
          applyBackendResult(latestResult);
          requestPreviewInBackground(
            {
              project_id: project.project_id,
              result: latestResult,
              filename_stem: fileName || project.name || "civora-ai-plan",
            },
            {
              silentStatus: true,
            },
          );
        } else {
          const activeProjectForPreview =
            visibleActiveJob?.project_id ||
            resolvedProjectIdRef.current ||
            projectId ||
            currentProject?.project_id ||
            "";
          if (activeProjectForPreview && activeProjectForPreview !== project.project_id) {
            return;
          }
          const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
          const shouldPreserveCurrentPreview =
            project.project_id &&
            activeProjectForPreview === project.project_id &&
            (activeStatus === "running" ||
              activeStatus === "queued" ||
              activeStatus === "awaiting_approval");
          if (shouldPreserveCurrentPreview && (planPreviewUrl || backendResult)) {
            return;
          }
          setBackendResult(null);
          setPlanPreviewUrl("");
          setPlanPreviewSummary(null);
        }
      })
      .catch((error) => {
        setStatusMessage(
          error instanceof Error ? error.message : "Project result load failed.",
        );
      });
  };

  useEffect(() => {
    if (!token) return;
    const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
    if (activeStatus !== "awaiting_approval") return;
    const targetProjectId =
      visibleActiveJob?.project_id || currentProject?.project_id || projectId || "";
    if (!targetProjectId) return;

    const targetProject = {
      project_id: targetProjectId,
      name: currentProject?.name || siteName || "Untitled Project",
    } as ProjectRecord;

    loadProjectResultInBackground(targetProject);
    const interval = window.setInterval(() => {
      loadProjectResultInBackground(targetProject);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [
    token,
    planPreviewUrl,
    visibleActiveJob?.status,
    visibleActiveJob?.project_id,
    currentProject?.project_id,
    currentProject?.name,
    projectId,
    siteName,
  ]);

  const siteInputs = (currentProject?.project_input?.meta?.site_inputs ?? {}) as SiteInputs;

  const ensureSiteLocked = useCallback(
    (action: string) => {
      if (siteScaleLocked) return true;
      const alignmentLocked =
        currentProject?.project_input?.meta?.site_inputs &&
        typeof currentProject.project_input.meta.site_inputs === "object"
          ? currentProject.project_input.meta.site_inputs.site_alignment_locked
          : null;
      if (alignmentLocked === true) return true;
      askClarification(
        "Please lock the site alignment before running this step. Do you want me to lock the site now?",
        "lock_site_required",
        { action },
      );
      return false;
    },
    [askClarification, siteScaleLocked],
  );

  const pickBestLowPoint = useCallback(() => {
    if (drainageLowPoints.length) {
      let best = drainageLowPoints[0];
      for (let i = 1; i < drainageLowPoints.length; i += 1) {
        const current = drainageLowPoints[i];
        const bestZ = Number.isFinite(best.z) ? best.z : Number.POSITIVE_INFINITY;
        const currentZ = Number.isFinite(current.z) ? current.z : Number.POSITIVE_INFINITY;
        if (currentZ < bestZ) {
          best = current;
        }
      }
      return best ?? null;
    }
    const lot = resolveLotBounds();
    if (lot.w && lot.h) {
      return {
        x: lot.x + lot.w / 2,
        y: lot.y + lot.h / 2,
        z: 0,
      };
    }
    return null;
  }, [drainageLowPoints, resolveLotBounds]);

  const drainageIssueApplyLabel = useCallback(
    (issue: Issue) => {
      const code = (issue.code ?? "").toUpperCase();
      if (code === "NO_PONDS_DEFINED" || code === "NO_VALID_OUTFALL" || code === "DRAINAGE_NO_BASIN") {
        return "Add basin";
      }
      if (code === "BASIN_UNREACHABLE") return "Add basin";
      if (code === "POOR_SLOPE") return "Adjust slope";
      if (code === "ORPHAN_INLETS") return "Connect inlet";
      if (code === "UNDER_COLLECTION") return "Add inlet";
      if (code === "UNDER_COLLECTION_REDUCED") return "Add inlet";
      return null;
    },
    [],
  );

  const getIssueGuidance = useCallback((issue: Issue) => {
    const code = (issue.code ?? "").toUpperCase();
    const rawContext = issue.context;
    const context =
      rawContext && typeof rawContext === "object"
        ? (rawContext as Record<string, unknown>)
        : null;
    const explanation =
      context && typeof context.explanation === "string"
        ? String(context.explanation)
        : null;
    const bestNextFix =
      context && typeof context.best_next_fix === "string"
        ? String(context.best_next_fix)
        : null;
    const suggested =
      context && Array.isArray(context.suggested_actions)
        ? context.suggested_actions
            .filter((item) => typeof item === "string")
            .map((item) => String(item))
        : null;
    if (explanation || bestNextFix || (suggested && suggested.length)) {
      return { explanation, bestNextFix, suggested };
    }
    const fallback: Record<string, { explanation: string; suggested: string[]; bestNextFix: string }> = {
      BASIN_UNREACHABLE: {
        explanation: "Flow cannot reach the basin from current low points.",
        suggested: [
          "Move the basin to a lower point.",
          "Add an inlet near the low point.",
          "Adjust grading to direct flow toward the basin.",
        ],
        bestNextFix: "Move the basin to a lower point.",
      },
      DRAINAGE_NO_BASIN: {
        explanation: "No valid basin or outfall was provided for drainage.",
        suggested: [
          "Add a basin at a low point.",
          "Define an outfall location.",
          "Connect to an existing downstream system.",
        ],
        bestNextFix: "Add a basin at a low point.",
      },
      NO_VALID_OUTFALL: {
        explanation: "No valid outlet was found for drainage discharge.",
        suggested: [
          "Add a basin at a low point.",
          "Define an outfall location.",
          "Connect to an existing downstream system.",
        ],
        bestNextFix: "Add a basin at a low point.",
      },
      NO_PONDS_DEFINED: {
        explanation: "No basin/pond target is defined for drainage.",
        suggested: [
          "Add a basin at a low point.",
          "Define an outfall location.",
          "Connect to an existing downstream system.",
        ],
        bestNextFix: "Add a basin at a low point.",
      },
      POOR_SLOPE: {
        explanation: "Terrain is too flat for the minimum pipe slope.",
        suggested: [
          "Modify grading to introduce slope.",
          "Relocate inlets or basin to a steeper area.",
          "Increase slope in this region.",
        ],
        bestNextFix: "Modify grading to introduce slope.",
      },
      SLOPE_ADJUSTMENT_FAILED: {
        explanation: "Slope adjustment is not feasible with the current geometry.",
        suggested: [
          "Modify grading to introduce slope.",
          "Relocate inlets or basin to a steeper area.",
          "Increase slope in this region.",
        ],
        bestNextFix: "Modify grading to introduce slope.",
      },
      ORPHAN_INLETS: {
        explanation: "One or more inlets are not connected to a drainage run.",
        suggested: [
          "Connect the inlet to the nearest run.",
          "Reroute the pipe network to include the inlet.",
        ],
        bestNextFix: "Connect the inlet to the nearest run.",
      },
      UNDER_COLLECTION: {
        explanation: "There are not enough inlets to collect runoff.",
        suggested: ["Add inlets along pavement edges."],
        bestNextFix: "Add inlets along pavement edges.",
      },
      UNDER_COLLECTION_REDUCED: {
        explanation: "Inlet coverage improved, but runoff is still under-collected.",
        suggested: ["Add inlets along pavement edges."],
        bestNextFix: "Add inlets along pavement edges.",
      },
    };
    const fallbackGuidance = fallback[code];
    return fallbackGuidance
      ? fallbackGuidance
      : { explanation: null, bestNextFix: null, suggested: null };
  }, []);

  const canApplyDrainageIssue = useCallback(
    (issue: Issue) => {
      const code = (issue.code ?? "").toUpperCase();
      if (
        code === "UNDER_COLLECTION" ||
        code === "UNDER_COLLECTION_REDUCED" ||
        code === "BASIN_UNREACHABLE" ||
        code === "DRAINAGE_NO_BASIN" ||
        code === "NO_VALID_OUTFALL" ||
        code === "NO_PONDS_DEFINED"
      ) {
        return Boolean(pickBestLowPoint());
      }
      if (code === "ORPHAN_INLETS" || code === "POOR_SLOPE") return true;
      return false;
    },
    [pickBestLowPoint],
  );

  const runDrainageAutofix = useCallback(
    async ({
      placementsOverride,
      forcedInlets,
      forcedBasins,
      connectOrphans,
      allowSlopeAdjust,
    }: {
      placementsOverride?: BuildingPlacement[];
      forcedInlets?: Array<Record<string, unknown>>;
      forcedBasins?: Array<Record<string, unknown>>;
      connectOrphans?: boolean;
      allowSlopeAdjust?: boolean;
    }) => {
      if (!ensureSiteLocked("drainage")) return;
      const requestPayload = buildPayloadFromOverrides({}, undefined, projectId || null, placementsOverride);
      const omitField = { source: "omit", value: null } as const;
      const nextManualFields = {
        ...(requestPayload.manual_fields ?? {}),
      } as Record<string, unknown>;
      const rawDrainage = nextManualFields.drainage;
      const unwrappedDrainage =
        rawDrainage &&
        typeof rawDrainage === "object" &&
        "value" in (rawDrainage as Record<string, unknown>)
          ? ((rawDrainage as Record<string, unknown>).value ?? {})
          : rawDrainage ?? {};
      const nextDrainage = {
        ...(typeof unwrappedDrainage === "object" && unwrappedDrainage !== null ? unwrappedDrainage : {}),
      } as Record<string, unknown>;
      if (forcedInlets && forcedInlets.length) {
        nextDrainage.forced_inlets = forcedInlets;
      }
      if (forcedBasins) {
        if (forcedBasins.length) {
          nextManualFields.ponds = forcedBasins;
        }
        nextDrainage.autofix_action = "add_basin";
      }
      if (connectOrphans) {
        nextDrainage.connect_orphans = true;
      }
      if (allowSlopeAdjust) {
        nextDrainage.allow_slope_adjustment = true;
        nextDrainage.max_slope_adjust = drainageMaxSlopeAdjust;
        nextDrainage.autofix_action = "adjust_slope";
      }
      nextManualFields.drainage = nextDrainage;
      nextManualFields.utility_network = omitField;

      const drainagePayload: PlanRequestPayload = withReactiveRerunContext(
        {
          ...requestPayload,
          manual_fields: nextManualFields,
          meta: {
            ...(requestPayload.meta ?? {}),
            requested_system: "drainage",
          },
          prompt_text: null,
        },
        "drainage",
      );
      if (allowSlopeAdjust) {
        const existingDrainage = (requestPayload.drainage ?? {}) as Record<string, unknown>;
        (drainagePayload as Record<string, unknown>).drainage = {
          ...existingDrainage,
          allow_slope_adjustment: true,
          max_slope_adjust: drainageMaxSlopeAdjust,
          autofix_action: "adjust_slope",
        };
      }

      if (token && (projectId || currentProject?.project_id)) {
        const targetProjectId = projectId || currentProject?.project_id || null;
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/drainage",
            {
              project_id: targetProjectId,
              request: drainagePayload,
            },
            { token },
          );
          const jobId = queued.job.job_id;
          setActiveJobId(jobId);
          const deadline = Date.now() + 120_000;
          while (Date.now() < deadline) {
            const jobState = await getJson<{ job: JobSummary }>(
              `/api/jobs/${jobId}`,
              { token },
            );
            const status = String(jobState.job?.status || "");
            if (status === "completed") break;
            if (status === "failed" || status === "cancelled") {
              throw new Error(jobState.job?.error || "Drainage job failed.");
            }
            await new Promise((resolve) => window.setTimeout(resolve, 2000));
          }
          if (targetProjectId) {
            loadProjectResultInBackground({
              project_id: targetProjectId,
              name: currentProject?.name || siteName || "Untitled Project",
            } as ProjectRecord);
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : "Drainage autofix failed.";
          appendChatMessage("assistant", message, "status");
          setStatusMessage(message);
        }
      } else {
        await executePlanAction({
          mode: "run",
          requestPayload: drainagePayload,
          assistantPrefix: "Applying drainage fix…",
        });
      }
      setSystemStatuses((prev) => ({ ...prev, drainage: "fresh" }));
    },
    [
      buildPayloadFromOverrides,
      drainageMaxSlopeAdjust,
      ensureSiteLocked,
      executePlanAction,
      token,
      projectId,
      currentProject?.project_id,
      currentProject?.name,
      siteName,
      loadProjectResultInBackground,
      appendChatMessage,
      setActiveJobId,
      setSystemStatuses,
      withReactiveRerunContext,
    ],
  );

  const handleGenerateSystem = useCallback(
    async (
      target: "roads" | "parking" | "grading" | "drainage" | "utilities" | "full",
      options?: { slopeEstimateOverride?: SurveySlopeResponse | null },
    ) => {
      if (!hasSiteBoundary()) {
        askClarification(
          "I need a site boundary before generating systems. What size should the site be?",
          "set_site_then_generate",
          { target },
        );
        return;
      }
      if (!ensureSiteLocked(target)) {
        return;
      }
      const hasBasin =
        target === "drainage" || target === "full"
          ? buildingPlacements.some((item) => item.type === "basin" && item.placed)
          : true;
      if (!hasBasin && (target === "drainage" || target === "full")) {
        askClarification(
          "Drainage needs a basin or outfall target. Do you want me to add a basin object for you?",
          "drainage_missing_basin",
          { target },
        );
        return;
      }
      if (target === "roads") {
        const hasRoadAnchor = buildingPlacements.some((item) =>
          ["road", "driveway", "entrance", "building"].includes(item.type ?? ""),
        );
        if (!hasRoadAnchor) {
          setStatusMessage("Add a building or entrance before generating roads.");
          return;
        }
      }
      if (target === "grading" || target === "drainage" || target === "full") {
        const lot = resolveLotBounds();
        const siteAreaAcres = siteAreaAcresFromSize(lot.w, lot.h);
        if (target === "grading" && siteAreaAcres > SITE_GRADING_HARD_BLOCK_ACRES) {
          setStatusMessage(OVERSIZED_SITE_MESSAGE);
          return;
        }
        const effectiveSlopeEstimate = options?.slopeEstimateOverride ?? surveySlopeEstimate;
        const hasSurvey = Boolean(surveyFileName) && useSurveyForGrading;
        const hasMapTerrain = Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng);
        if (!hasSurvey && !hasMapTerrain && !effectiveSlopeEstimate?.slope_percent) {
          askClarification(
            "I need a terrain source for grading. Use survey, map terrain, or a first‑pass assumed slope?",
            "grading_source",
            { target },
          );
          return;
        }
      }
      const requestPayload = buildPayloadFromOverrides({}, undefined, projectId || null);
      const omitField = { source: "omit", value: null } as const;
      const nextManualFields = {
        ...(requestPayload.manual_fields ?? {}),
      } as Record<string, unknown>;
      const slopeEstimateOverride = options?.slopeEstimateOverride ?? null;
      if (slopeEstimateOverride?.slope_percent) {
        nextManualFields.grading = {
          ...((typeof nextManualFields.grading === "object" && nextManualFields.grading !== null
            ? nextManualFields.grading
            : {}) as Record<string, unknown>),
          min_slope_pct:
            parsePositiveNumber(minSlopePct) ?? slopeEstimateOverride.slope_percent,
          assumed_terrain_source: true,
        };
        nextManualFields.terrain =
          slopeEstimateOverride.direction && slopeEstimateOverride.slope_percent
            ? `First-pass assumed ${slopeEstimateOverride.slope_percent.toFixed(2)}% slope toward ${slopeEstimateOverride.direction}`
            : "First-pass assumed terrain slope";
      }

      if (target === "roads" || target === "parking") {
        nextManualFields.grading = omitField;
        nextManualFields.drainage = omitField;
        nextManualFields.utility_network = omitField;
      } else if (target === "grading") {
        nextManualFields.drainage = omitField;
        nextManualFields.utility_network = omitField;
      } else if (target === "drainage") {
        nextManualFields.utility_network = omitField;
      } else if (target === "utilities") {
        nextManualFields.drainage = omitField;
      }

      const systemLabel = target === "full" ? "full site systems" : target;
      const directRun = target === "grading";
      if (
        target !== "full" &&
        reactiveValidation.requiresConfirmation &&
        REACTIVE_EDIT_POLICY_PREFERENCE.require_confirmation_for_heavy_engineering
      ) {
        const confirmed = window.confirm(
          `This rerun will update ${reactiveValidation.changedSystems.join(", ")} from the saved checkpoint and may touch ${reactiveValidation.changedTargets.length} downstream stages. Run it now?`,
        );
        if (!confirmed) {
          setStatusMessage("Reactive engineering rerun cancelled. Visual edits remain live; engineering outputs are still stale.");
          return;
        }
      }
      const systemRequestPayload = withReactiveRerunContext(
        {
          ...requestPayload,
          full_design_mode: directRun ? false : requestPayload.full_design_mode,
          manual_fields: nextManualFields,
          meta: {
            ...(requestPayload.meta ?? {}),
            requested_system: target,
          },
          prompt_text: null,
        },
        target,
      );
      await executePlanAction({
        mode: "run",
        requestPayload: systemRequestPayload,
        assistantPrefix: `Generating ${systemLabel} around your placed layout...`,
        timeoutMs: directRun ? 90_000 : undefined,
        allowQueueFallback: !directRun,
      });
      setSystemStatuses((prev) => {
        if (target === "full") {
          return {
            roads: "fresh",
            parking: "fresh",
            grading: "fresh",
            drainage: "fresh",
            utilities: "fresh",
          };
        }
        return {
          ...prev,
          [target]: "fresh",
        };
      });
    },
    [
      askClarification,
      buildPayloadFromOverrides,
      buildingPlacements,
      executePlanAction,
      hasSiteBoundary,
      ensureSiteLocked,
      minSlopePct,
      projectId,
      resolveLotBounds,
      siteInputs?.geocode?.lat,
      siteInputs?.geocode?.lng,
      surveyFileName,
      surveySlopeEstimate?.slope_percent,
      useSurveyForGrading,
      withReactiveRerunContext,
      reactiveValidation,
    ],
  );

  useEffect(() => {
    handleGenerateSystemRef.current = handleGenerateSystem;
  }, [handleGenerateSystem]);

  const handleApplyDrainageIssue = useCallback(
    async (issue: Issue) => {
      const issueCode = (issue.code ?? "").toUpperCase();
      const lot = resolveLotBounds();
      const lowPoint = pickBestLowPoint();
      const issueX = typeof issue.context?.x === "number" ? issue.context.x : Number(issue.context?.x);
      const issueY = typeof issue.context?.y === "number" ? issue.context.y : Number(issue.context?.y);
      const issueLocation =
        Number.isFinite(issueX) && Number.isFinite(issueY) ? { x: issueX, y: issueY } : null;
      const distanceFt = (a: { x: number; y: number }, b: { x: number; y: number }) =>
        Math.hypot(a.x - b.x, a.y - b.y);
      const findNearbyPlacement = (
        type: SiteObjectType,
        point: { x: number; y: number },
        threshold: number,
      ) =>
        buildingPlacements.find(
          (item) =>
            item.type === type &&
            item.placed &&
            Number.isFinite(item.x) &&
            Number.isFinite(item.y) &&
            distanceFt({ x: item.x as number, y: item.y as number }, point) <= threshold,
        );

      if (issueCode === "UNDER_COLLECTION" || issueCode === "UNDER_COLLECTION_REDUCED") {
        if (!lowPoint) {
          setStatusMessage("No low points available to place an inlet.");
          return;
        }
        if (issueLocation && distanceFt(lowPoint, issueLocation) > 200) {
          setStatusMessage("Closest low point is too far from the flagged area to place an inlet.");
          return;
        }
        if (findNearbyPlacement("inlet", lowPoint, 10)) {
          setStatusMessage("An inlet already exists near the suggested location.");
          return;
        }
        if (
          drainageForcedInlets.some(
            (item) =>
              typeof item.x === "number" &&
              typeof item.y === "number" &&
              distanceFt({ x: item.x, y: item.y }, lowPoint) <= 8,
          )
        ) {
          setStatusMessage("An inlet is already queued near that location.");
          return;
        }
        const forcedInlet = {
          x: lowPoint.x,
          y: lowPoint.y,
          label: "Autofix inlet",
          source: "autofix",
        };
        const nextForced = [...drainageForcedInlets, forcedInlet];
        setDrainageForcedInlets(nextForced);
        const inletPlacement: BuildingPlacement = {
          id: `inlet-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: "Autofix inlet",
          type: "inlet",
          w: 8,
          d: 8,
          x: lowPoint.x - 4,
          y: lowPoint.y - 4,
          rotation: 0,
          placed: true,
          source: "generated",
          generated: true,
          systemDependencies: ["drainage"],
        };
        clearGeneratedPreview();
        setBuildingPlacements((prev) => [...prev, inletPlacement]);
        setExternalRectUndo({
          id: inletPlacement.id,
          snapshot: inletPlacement,
          action: "add",
          ts: Date.now(),
        });
        setFocusObjectId(inletPlacement.id);
        await runDrainageAutofix({ placementsOverride: [...buildingPlacements, inletPlacement], forcedInlets: nextForced });
        setStatusMessage("Applied inlet placement. Drainage regenerated.");
        return;
      }

      if (issueCode === "ORPHAN_INLETS") {
        if (drainageConnectOrphans) {
          setStatusMessage("Orphan inlet connection already queued. Regenerate drainage to apply.");
          return;
        }
        setDrainageConnectOrphans(true);
        await runDrainageAutofix({ connectOrphans: true });
        setStatusMessage("Applied orphan inlet connection. Drainage regenerated.");
        return;
      }

      if (issueCode === "POOR_SLOPE") {
        if (drainageAllowSlopeAdjust) {
          setStatusMessage("Slope adjustment already queued. Regenerate drainage to apply.");
          return;
        }
        setDrainageAllowSlopeAdjust(true);
        await runDrainageAutofix({ allowSlopeAdjust: true });
        setStatusMessage("Applied slope adjustment attempt. Drainage regenerated.");
        return;
      }

      if (
        issueCode === "BASIN_UNREACHABLE" ||
        issueCode === "DRAINAGE_NO_BASIN" ||
        issueCode === "NO_VALID_OUTFALL" ||
        issueCode === "NO_PONDS_DEFINED"
      ) {
        if (!lowPoint) {
          setStatusMessage("No low points available to place a basin.");
          return;
        }
        if (issueCode === "BASIN_UNREACHABLE" && issueLocation && distanceFt(lowPoint, issueLocation) > 300) {
          setStatusMessage("Closest low point is too far from the flagged area to place a basin.");
          return;
        }
        if (findNearbyPlacement("basin", lowPoint, 40)) {
          setStatusMessage("A basin already exists near the suggested location.");
          return;
        }
        const basinPlacement: BuildingPlacement = {
          id: `basin-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: "Autofix basin",
          type: "basin",
          w: 60,
          d: 40,
          x: Math.min(Math.max(lowPoint.x - 30, lot.x), lot.x + lot.w - 60),
          y: Math.min(Math.max(lowPoint.y - 20, lot.y), lot.y + lot.h - 40),
          rotation: 0,
          placed: true,
          source: "generated",
          generated: true,
          systemDependencies: ["drainage"],
        };
        clearGeneratedPreview();
        const nextPlacements = [...buildingPlacements, basinPlacement];
        setBuildingPlacements(nextPlacements);
        setExternalRectUndo({
          id: basinPlacement.id,
          snapshot: basinPlacement,
          action: "add",
          ts: Date.now(),
        });
        setFocusObjectId(basinPlacement.id);
        const forcedBasins = nextPlacements
          .filter((placement) => placement.type === "basin")
          .map((placement) => ({
            id: placement.id,
            name: placement.label,
            x: placement.x,
            y: placement.y,
            w: placement.w,
            d: placement.d,
            rotation: placement.rotation ?? 0,
            locked: placement.locked,
            source: "autofix",
            generated: placement.generated,
            systemDependencies: placement.systemDependencies,
          }));
        await runDrainageAutofix({
          placementsOverride: nextPlacements,
          forcedBasins,
        });
        setStatusMessage("Applied basin placement. Drainage regenerated.");
        return;
      }
    },
    [
      buildingPlacements,
      clearGeneratedPreview,
      drainageForcedInlets,
      pickBestLowPoint,
      resolveLotBounds,
      runDrainageAutofix,
      setDrainageAllowSlopeAdjust,
      setDrainageConnectOrphans,
      setDrainageForcedInlets,
      setFocusObjectId,
      setStatusMessage,
    ],
  );

  const queuePreviewRefresh = (reason: string) => {
    if (!token) return;
    previewRefreshIntentRef.current = { reason, track: true };
  };

  const handlePreviewPlan = async () => {
    if (!token) return;
    setStatusMessage("Refreshing preview...");
    setBusy(true);
    try {
      await requestPreview(artifactPayload, { track: true });
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Preview generation failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleExplainPlan = () => {
    const explanationText =
      typeof currentExplanation?.summary === "string"
        ? currentExplanation.summary
        : typeof currentExplanation?.overview === "string"
          ? currentExplanation.overview
          : typeof selectedRun?.message === "string"
            ? selectedRun.message
            : "";
    const fallbackDetails = [
      currentManualFailures.length
        ? `Current blockers: ${currentManualFailures
            .slice(0, 3)
            .map((failure) => failure.code || failure.message || "missing information issue")
            .join(", ")}.`
        : null,
      issues.length
        ? `Current warnings: ${issues
            .slice(0, 3)
            .map((issue) => issue.message)
            .join("; ")}.`
        : null,
      currentTruthAudit?.success === true
        ? "Truth checks are currently passing."
        : currentTruthAudit?.success === false
          ? "Truth checks still need review."
          : null,
    ]
      .filter(Boolean)
      .join(" ");

    if (!explanationText && !fallbackDetails) {
      setStatusMessage("Run Civora AI first so there is a plan to explain.");
      return;
    }

    appendChatMessage(
      "assistant",
      [
        explanationText || "Here’s where the current design stands.",
        typeof currentExplanation?.why === "string" ? currentExplanation.why : null,
        fallbackDetails || null,
      ]
        .filter(Boolean)
        .join(" "),
      "explanation",
    );
    setStatusMessage("Added the latest plan explanation to the conversation.");
  };

  const handleRunFix = () => {
    void runOrchestrator("fix");
  };

  const handleRunImprove = () => {
    void runOrchestrator("improve");
  };

  const resetWorkspaceState = useCallback(() => {
    debugLog("reset-workspace");
    setPlanPreviewUrl("");
    setPlanPreviewSummary(null);
    setPlanPreviewAnnotations(null);
    setPreviewRefreshing(false);
    setPreviewRefreshNote(null);
    setBackendResult(null);
    setUploadedImageApiUrl("");
    setUploadedImagePreviewUrl("");
    setImageUploadState("idle");
    setImageUploadNote(null);
    setSurveyFileName("");
    setSurveySlopeEstimate(null);
    setSurveyPoints([]);
    setSurveyPreviewPoints([]);
    setSurveyDiagnostics(null);
    setUseSurveyForGrading(true);
    setMapSnapshotPath("");
    setMapAnalysis(null);
    setSiteAddress("");
    setBuildingPlacements([]);
    setDetectedPlacements([]);
    setDetectionScaleFeet("");
    setDetectionScalePixels("");
    setDetectionScaleFtPerPx(null);
    setDetectionScaleSource("approximate");
    setSiteScaleLocked(false);
    setSiteRotationDeg(0);
    setSiteRotationInput("0");
    setShowSiteBounds(true);
    setFitToSiteRequest(0);
    setMapCenterRequest(0);
    setAlignToRoadRequest(0);
    setFocusDetectedId(null);
    setFocusObjectId(null);
    setPlacementModeEnabled(false);
    setActivePlacementId(null);
    setAnalysisIssues([]);
    setAnalysisPaths([]);
    setAnalysisSelectedIssueId(null);
    setAnalysisFocusLocked(false);
    setSelectedIssueId(null);
    setPendingClarification(null);
  }, []);

  const handleNewProject = async () => {
    debugLog("new-project-start");
    projectLoadRequestRef.current += 1;
    suppressProjectAutoLoadRef.current = true;
    draftProjectPromiseRef.current = null;
    resolvedProjectIdRef.current = "";
    setProjectId("");
    setCurrentProject(null);
    setSelectedRunId("");
    setActiveJobId("");
    setPrompt("");
    setImageName("");
    setUploadedImageApiUrl("");
    setUploadedImagePreviewUrl("");
    setSurveyFileName("");
    setSurveySlopeEstimate(null);
    setSurveyPoints([]);
    setSurveyPreviewPoints([]);
    setSurveyDiagnostics(null);
    setUseSurveyForGrading(true);
    setMapSnapshotPath("");
    setMapAnalysis(null);
    resetWorkspaceState();
    setSystemStatuses(DEFAULT_SYSTEM_STATUS);
    setAssumptions(defaultAssumptions);
    setIssues([]);
    setSiteName("");
    setFileName("");
    setSiteNameAuto(false);
    setFileNameAuto(false);
    setProjectType("");
    setUnits("ft");
    setLotWidth("");
    setLotHeight("");
    setBuildingWidth("");
    setBuildingDepth("");
    setBuildingCount("");
    setSetback("");
    setParkingCount("");
    setParkingStallWidth("9");
    setParkingStallDepth("18");
    setParkingAisleWidth("24");
    setParkingAdaAisleWidth("8");
    setParkingAdaCount("0");
    setParkingCompactCount("0");
    setParkingCompactWidth("8");
    setParkingAngle("90");
    setParkingLoading("double");
    setMinSlopePct("");
    setPipeMinSlopePct("");
    setMaxParkingSlopePct("");
    setMaxRoadGradePct("");
    setMaxAdaCrossSlopePct("");
    setRoads(true);
    setGrading(true);
    setDrainage(true);
    setUtilities(true);
    const nextThread = [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(getChatThreadStorageKey("draft"));
      } catch {
        // Ignore local storage failures.
      }
    }
    setStatusMessage("Started a new project.");
    try {
      if (token) {
        draftProjectPromiseRef.current = saveProject({
          silent: true,
          projectIdOverride: null,
          nameOverride: "",
          fileNameOverride: "",
          projectInputOverride: {
            input_mode: "user",
            strict_mode: false,
            prompt_text: null,
            image_path: null,
            meta: {
              chat_thread: [createWelcomeMessage()],
              auto_named: false,
              auto_file_named: false,
            },
            manual_fields: {
              project_name: "",
              file_name: "",
              units: "ft",
              project_type: "",
              lot: { x: 0, y: 0, w: 0, h: 0 },
              setback: 0,
              building_width: 0,
              building_depth: 0,
              site_plan: { parking_count: 0 },
              disciplines: ["corridor", "grading", "drainage", "utility"],
            },
            allow_ai_fill_for_blanks: false,
          },
          latestResultOverride: {},
          autoNamedOverride: false,
          autoFileNamedOverride: false,
        });
        const createdProject = await draftProjectPromiseRef.current;
        if (createdProject?.project_id) {
          resolvedProjectIdRef.current = createdProject.project_id;
          setProjectId(createdProject.project_id);
          debugLog("new-project-created", { projectId: createdProject.project_id });
        }
      }
    } finally {
      draftProjectPromiseRef.current = null;
      suppressProjectAutoLoadRef.current = false;
    }
  };

  const handleDeleteProject = async (projectIdToDelete: string) => {
    if (!token) return;
    const target = projects.find((item) => item.project_id === projectIdToDelete);
    const confirmed = window.confirm(
      `Delete "${target?.name || "Untitled Project"}"? This cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      setStatusMessage("Deleting project...");
      await deleteJson<{ success: boolean }>(`/api/projects/${projectIdToDelete}`, {
        token,
      });
      if (typeof window !== "undefined") {
        try {
          window.localStorage.removeItem(getChatThreadStorageKey(projectIdToDelete));
        } catch {
          // Ignore local storage failures.
        }
      }
      removeProjectSummary(projectIdToDelete);
      if (currentProject?.project_id === projectIdToDelete || projectId === projectIdToDelete) {
        const remaining = projects.filter(
          (item) => item.project_id !== projectIdToDelete,
        );
        if (remaining.length) {
          const next = [...remaining].sort(
            (a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0),
          )[0];
          if (next?.project_id) {
            await loadProject(next.project_id);
          }
        } else {
          await handleNewProject();
        }
      }
      setStatusMessage("Project deleted.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Could not delete project.",
      );
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleExportDxf = async () => {
    const blockReason = getExportBlockReason();
    if (blockReason) {
      setStatusMessage(`Export blocked: ${blockReason}`);
      return;
    }
    setBusy(true);
    try {
      const { blob, filename } = await postBinary(
        "/api/export/dxf",
        artifactPayload,
        { token },
      );
      downloadBlob(blob, filename ?? "civora-ai-plan.dxf");
      setStatusMessage("DXF review export downloaded. Engineer review required; construction release remains blocked.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "DXF export failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleExportReport = async () => {
    const blockReason = getExportBlockReason();
    if (blockReason) {
      setStatusMessage(`Export blocked: ${blockReason}`);
      return;
    }
    setBusy(true);
    try {
      const { blob, filename } = await postBinary(
        "/api/export/report",
        artifactPayload,
        { token },
      );
      downloadBlob(blob, filename ?? "civora-ai-report.json");
      setStatusMessage("Engineer-review report downloaded. Construction release remains blocked.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Report export failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  useJobPolling({
    token,
    activeJobId,
    visibleActiveJob,
    visibleActiveJobStale,
    onLoadJob: loadJob,
    onRefreshJobs: refreshJobs,
    setJobClockMs,
    setActiveJobId,
    currentProjectActiveJob,
    onStatusMessage: (message) => {
      setStatusMessage(message);
    },
    lastStaleJobWarningRef,
  });

  useEffect(() => {
    if (!workflowRuns.length) {
      setSelectedRunId("");
      return;
    }
    setSelectedRunId((current) =>
      current && workflowRuns.some((run) => run.run_id === current)
        ? current
        : workflowRuns[0].run_id,
    );
  }, [workflowRuns]);

  // Intentionally avoid auto-loading the last project on initial load so the
  // workspace starts clean and only loads a project when the user selects it.

  const {
    previewReview,
    previewBlockedReasons,
    previewCompletedPhaseCount,
    previewTotalPhaseCount,
    previewRunningPhase,
    previewNextPendingPhase,
  } = usePreviewReview({ currentPlanMeta, planPreviewSummary });
  const getExportBlockReason = useCallback(() => {
    if (!token) {
      return "sign in with a backend session before exporting review packages";
    }
    if (busy) {
      return "wait for the current operation to finish";
    }
    if (!backendResult) {
      return projectId
        ? "run systems or load a generated review package before exporting"
        : "run the planner or load a saved project before exporting";
    }
    return "";
  }, [backendResult, busy, projectId, token]);
  const gatingPhaseKey =
    String(visibleActiveJob?.status || "").toLowerCase() === "awaiting_approval"
      ? previewRunningPhase?.key || previewNextPendingPhase?.key
      : null;

  useEffect(() => {
    const phaseLabel =
      previewRunningPhase?.label ||
      String(visibleActiveJob?.stage || "").trim() ||
      String((currentPlanMeta?.runtime_phase_checkpoint as { stage_name?: string } | undefined)?.stage_name || "")
        .trim();
    currentPhaseLabelRef.current = phaseLabel ? toReadableLabel(phaseLabel) : "";
  }, [previewRunningPhase?.label, visibleActiveJob?.stage, currentPlanMeta]);

  const previewLayersEffective = useMemo(() => {
    if (!gatingPhaseKey) return previewLayers;
    switch (gatingPhaseKey) {
      case "layout":
        return { ...previewLayers, grading: false, drainage: false, utilities: false };
      case "grading":
        return { ...previewLayers, drainage: false, utilities: false };
      case "drainage_storm":
        return { ...previewLayers, grading: false, utilities: false };
      case "utilities":
        return { ...previewLayers, grading: false, drainage: false };
      default:
        return previewLayers;
    }
  }, [gatingPhaseKey, previewLayers]);

  const previewLayerList = useMemo(() => {
    const layers = new Set<string>();
    if (previewLayersEffective.buildings) {
      [
        "BUILDING",
        "STRUCTURE",
        "PAD",
        "C-BUILDING",
        "C-BOUNDARY",
        "C-SETBACK",
      ].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.roads) {
      [
        "ROAD",
        "PAVEMENT",
        "PARKING",
        "WALK",
        "C-ROAD",
        "C-PAVEMENT",
        "C-PARKING",
        "C-DRIVEWAY",
        "C-SIDEWALK",
        "C-CENTERLINE",
      ].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.grading) {
      [
        "SURFACE",
        "FG_CONTOUR",
        "EG_CONTOUR",
        "SPOT_FG",
        "DRAIN_FLOW",
        "FLOW_ARROW",
        "C-CONTOUR",
        "C-SPOT-ELEV",
        "C-GRADING",
        "C-CUT",
        "C-FILL",
      ].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.drainage) {
      [
        "DRAIN",
        "PIPE",
        "STORM",
        "BASIN_BOUNDARY",
        "C-STRM-PIPE",
        "C-STRM-INLET",
        "C-STRM-MH",
        "C-DRAIN-FLOW",
        "C-LOW-POINT",
        "C-POND",
      ].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.utilities) {
      ["UTILITY", "WATER", "SAN", "C-WATR", "C-SAN", "C-UTIL", "C-HYDRANT"].forEach((layer) =>
        layers.add(layer),
      );
    }
    if (previewLayersEffective.structures) {
      ["BRIDGE", "POOL", "STRUCTURE"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.lots) {
      ["LOT", "OPEN_SPACE", "EASEMENT"].forEach((layer) => layers.add(layer));
    }
    return Array.from(layers);
  }, [previewLayersEffective]);

  useEffect(() => {
    if (!token) return;
    if (!backendResult && !planPreviewUrl && !projectId) return;
    const intent = previewRefreshIntentRef.current;
    if (intent) {
      previewRefreshIntentRef.current = null;
      setPreviewRefreshNote(intent.reason);
      requestPreviewInBackground(artifactPayload, {
        silentStatus: true,
        track: intent.track,
      });
      return;
    }
    requestPreviewInBackground(artifactPayload, { silentStatus: true });
  }, [
    previewQuality,
    previewLabelDensity,
    previewInteraction,
    previewLayerList,
    planPreviewUrl,
    token,
    artifactPayload,
    backendResult,
  ]);

  useEffect(() => {
    if (previewLabelDensityTouched) return;
    setPreviewLabelDensity(previewQuality === "high" ? "high" : "standard");
  }, [previewLabelDensityTouched, previewQuality]);

  const hasGradingSurface = useMemo(() => {
    const gradingMeta =
      (backendResult?.final_plan?.meta as { grading?: Record<string, unknown> } | undefined)?.grading ??
      (backendResult?.metadata as { grading_summary?: Record<string, unknown> } | undefined)?.grading_summary ??
      (backendResult?.metadata as { grading?: Record<string, unknown> } | undefined)?.grading ??
      null;
    if (!gradingMeta || typeof gradingMeta !== "object") return false;
    const record = gradingMeta as Record<string, unknown>;
    return Boolean(
      record.proposed_surface ||
        record.existing_surface ||
        (record.surface_controls as { grade_range_ft?: number } | undefined)?.grade_range_ft,
    );
  }, [backendResult]);

  const preview3DItems = useMemo<Preview3DItem[]>(() => {
    const actions = Array.isArray(backendResult?.final_plan?.actions)
      ? backendResult.final_plan.actions
      : [];
    const items: Preview3DItem[] = [];
    const gradingMeta =
      (backendResult?.final_plan?.meta as { grading?: Record<string, unknown> } | undefined)?.grading ??
      (backendResult?.metadata as { grading_summary?: Record<string, unknown> } | undefined)?.grading_summary ??
      (backendResult?.metadata as { grading?: Record<string, unknown> } | undefined)?.grading ??
      null;
    const surfaceControls =
      gradingMeta && typeof gradingMeta === "object"
        ? ((gradingMeta as { surface_controls?: Record<string, unknown> }).surface_controls ?? {})
        : {};
    const surfaceGuidance =
      gradingMeta && typeof gradingMeta === "object"
        ? ((gradingMeta as { surface_guidance?: Record<string, unknown> }).surface_guidance ?? {})
        : {};
    const gradeRangeFt = Number(
      (surfaceControls as { grade_range_ft?: number }).grade_range_ft ?? 0,
    );
    const downhillVector =
      (surfaceGuidance as { downhill_vector?: { x?: number; y?: number; dx?: number; dy?: number } })
        .downhill_vector ?? null;
    const baseTerrain = {
      minX: Number.POSITIVE_INFINITY,
      minY: Number.POSITIVE_INFINITY,
      maxX: Number.NEGATIVE_INFINITY,
      maxY: Number.NEGATIVE_INFINITY,
    };

    const addBounds = (bounds: [number, number, number, number]) => {
      baseTerrain.minX = Math.min(baseTerrain.minX, bounds[0]);
      baseTerrain.minY = Math.min(baseTerrain.minY, bounds[1]);
      baseTerrain.maxX = Math.max(baseTerrain.maxX, bounds[2]);
      baseTerrain.maxY = Math.max(baseTerrain.maxY, bounds[3]);
    };

    const elevationAt = (x: number, y: number) => {
      if (!gradeRangeFt) return 0;
      const spanX = Math.max(baseTerrain.maxX - baseTerrain.minX, 1);
      const spanY = Math.max(baseTerrain.maxY - baseTerrain.minY, 1);
      const nx = (x - baseTerrain.minX) / spanX - 0.5;
      const ny = (y - baseTerrain.minY) / spanY - 0.5;
      const dirX = Number(downhillVector?.x ?? downhillVector?.dx ?? 0);
      const dirY = Number(downhillVector?.y ?? downhillVector?.dy ?? -1);
      const norm = Math.hypot(dirX, dirY) || 1;
      const dot = (nx * dirX + ny * dirY) / norm;
      return dot * gradeRangeFt;
    };

    for (const action of actions) {
      if (!action || typeof action !== "object") continue;
      const actionRecord = action as Record<string, unknown>;
      const task = String(actionRecord.task || "").toLowerCase();
      const layerRaw = String(actionRecord.layer || "").toUpperCase();
      const normalizedLayer = layerRaw.startsWith("C-") ? layerRaw.slice(2) : layerRaw;
      const meta = actionRecord.meta as Record<string, unknown> | undefined;
      const previewRole = String(meta?.preview_role || (meta?.is_final ? "final" : "overlay"));
      if (previewRole !== "final") continue;

      let bounds: [number, number, number, number] | null = null;
      if (task === "rectangle") {
        const origin = Array.isArray(actionRecord.origin) ? (actionRecord.origin as number[]) : [];
        const width = Number(actionRecord.width || 0);
        const height = Number(actionRecord.height || 0);
        if (origin.length >= 2 && width > 0 && height > 0) {
          bounds = [Number(origin[0]), Number(origin[1]), Number(origin[0]) + width, Number(origin[1]) + height];
        }
      } else if (task === "polygon" || task === "polyline") {
        const points = Array.isArray(actionRecord.points) ? (actionRecord.points as number[][]) : [];
        if (points.length >= 2) {
          const xs = points.map((pt) => Number((pt as number[])[0] || 0));
          const ys = points.map((pt) => Number((pt as number[])[1] || 0));
          bounds = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
        }
      }
      if (!bounds) continue;

      addBounds(bounds);
      const [x1, y1, x2, y2] = bounds;
      const w = Math.max(1, x2 - x1);
      const h = Math.max(1, y2 - y1);
      const centerX = x1 + w / 2;
      const centerY = y1 + h / 2;
      const label = String(actionRecord.label || normalizedLayer);
      const system = String(meta?.system || "");
      const isBuilding = normalizedLayer === "BUILDING";
      const isRoad = ["ROAD", "PAVEMENT", "DRIVEWAY", "WALK", "SIDEWALK"].includes(normalizedLayer) || system === "roads";
      const isParking = normalizedLayer === "PARKING" || system === "parking";
      const isStructure = ["BRIDGE", "POOL", "STRUCTURE"].includes(normalizedLayer);
      const isDrainage = ["POND", "DRAIN_FLOW", "STRM-PIPE", "STRM-INLET", "STRM-MH"].includes(normalizedLayer) || system === "drainage";
      const isUtility = ["SAN", "UTIL", "WATR", "WATER"].includes(normalizedLayer) || system === "utilities";

      if (isBuilding && !previewLayersEffective.buildings) continue;
      if ((isRoad || isParking) && !previewLayersEffective.roads) continue;
      if (isDrainage && !previewLayersEffective.drainage) continue;
      if (isUtility && !previewLayersEffective.utilities) continue;
      if (isStructure && !previewLayersEffective.structures) continue;

      const color = isBuilding
        ? "#e2e8f0"
        : isStructure
          ? "#fde68a"
          : isDrainage
            ? "#bbf7d0"
            : isUtility
              ? "#fbcfe8"
              : isRoad || isParking
                ? "#c7d2fe"
                : "#dbeafe";
      const heightFt = isBuilding ? 28 : isStructure ? 10 : isDrainage ? 4 : isRoad ? 2 : isParking ? 1.5 : 1;
      const elevationOffset = elevationAt(centerX, centerY);
      const pondAdjustment = normalizedLayer === "POND" ? Math.max(1.5, gradeRangeFt * 0.12) : 0;
      items.push({
        x: x1,
        y: y1,
        w,
        h,
        height: heightFt,
        z: elevationOffset - pondAdjustment,
        color,
        label: label || normalizedLayer,
        layer: isBuilding ? "BUILDING" : isStructure ? "STRUCTURE" : isRoad ? "ROAD" : "PARKING",
      });
    }

    if (
      Number.isFinite(baseTerrain.minX) &&
      Number.isFinite(baseTerrain.minY) &&
      Number.isFinite(baseTerrain.maxX) &&
      Number.isFinite(baseTerrain.maxY)
    ) {
      const terrainWidth = Math.max(1, baseTerrain.maxX - baseTerrain.minX);
      const terrainHeight = Math.max(1, baseTerrain.maxY - baseTerrain.minY);
      const terrainZ = gradeRangeFt ? -gradeRangeFt * 0.4 : 0;
      items.unshift({
        x: baseTerrain.minX,
        y: baseTerrain.minY,
        w: terrainWidth,
        h: terrainHeight,
        height: 1,
        z: terrainZ,
        color: "#e5e7eb",
        label: "Terrain",
        layer: "TERRAIN",
      });
    }
    return items;
  }, [backendResult, previewLayersEffective]);
  const preview3DAnnotationItems = useMemo<Preview3DItem[]>(() => {
    const labels = Array.isArray(planPreviewAnnotations?.labels)
      ? planPreviewAnnotations?.labels
      : [];
    if (!labels.length) return [];
    const items: Preview3DItem[] = [];
    const scale = 100;
    for (const label of labels) {
      const bounds = (label as { bounds?: { x1?: number; y1?: number; x2?: number; y2?: number } })
        .bounds;
      if (!bounds) continue;
      const x1 = Number(bounds.x1 ?? 0);
      const y1 = Number(bounds.y1 ?? 0);
      const x2 = Number(bounds.x2 ?? 0);
      const y2 = Number(bounds.y2 ?? 0);
      const w = Math.max(0.01, (x2 - x1) * scale);
      const h = Math.max(0.01, (y2 - y1) * scale);
      const layer = String((label as { layer?: string }).layer || "").toUpperCase();
      const isBuilding = layer === "BUILDING";
      const isRoad = ["ROAD", "PAVEMENT", "PARKING", "WALK"].includes(layer);
      const isDrainage = ["DRAIN", "PIPE", "STORM", "BASIN_BOUNDARY"].includes(layer);
      const isUtility = ["SAN", "UTILITY", "WATER"].includes(layer);
      const isStructure = ["STRUCTURE", "BRIDGE", "POOL"].includes(layer);
      const isLot = layer === "LOT";

      if (isBuilding && !previewLayersEffective.buildings) continue;
      if (isRoad && !previewLayersEffective.roads) continue;
      if (isDrainage && !previewLayersEffective.drainage) continue;
      if (isUtility && !previewLayersEffective.utilities) continue;
      if (isStructure && !previewLayersEffective.structures) continue;
      if (isLot && !previewLayersEffective.lots) continue;

      const color = isBuilding
        ? "#e2e8f0"
        : isStructure
          ? "#fde68a"
          : isRoad
            ? "#c7d2fe"
            : isDrainage
              ? "#bbf7d0"
              : isUtility
                ? "#fbcfe8"
                : isLot
                  ? "#e2e8f0"
                  : "#dbeafe";
      const heightFt = isBuilding ? 26 : isStructure ? 8 : isRoad ? 2 : 1;
      items.push({
        x: x1 * scale,
        y: y1 * scale,
        w,
        h,
        height: heightFt,
        color,
        label: String((label as { label?: string }).label || layer || "Shape"),
        layer: isBuilding ? "BUILDING" : isStructure ? "STRUCTURE" : isRoad ? "ROAD" : "PARKING",
      });
    }
    return items;
  }, [planPreviewAnnotations, previewLayersEffective]);
  const preview3DPlacementItems = useMemo<Preview3DItem[]>(() => {
    const lot = resolveLotBounds();
    const items: Preview3DItem[] = [];
    if (lot.w && lot.h) {
      items.push({
        x: 0,
        y: 0,
        w: lot.w,
        h: lot.h,
        height: 1,
        z: -0.5,
        color: "#f8fafc",
        label: "Site",
        layer: "TERRAIN",
      });
    }
    buildingPlacements
      .filter((item) => item.type !== "site" && item.placed)
      .forEach((item) => {
        const isBuilding = Boolean(item.type && item.type.includes("building")) || !item.type;
        const isRoad = item.type === "road" || item.type === "driveway" || item.type === "sidewalk";
        const isParking = item.type === "parking";
        const isDrainage = item.type === "basin" || item.type === "inlet" || item.type === "outfall";
        const isUtility = item.type === "hydrant" || item.type === "manhole" || item.type === "utility_corridor";
        items.push({
          x: item.x ?? 0,
          y: item.y ?? 0,
          w: Math.max(1, item.w),
          h: Math.max(1, item.d),
          height: isBuilding ? Math.max(8, Number(item.h ?? 28)) : isDrainage ? 3 : isRoad ? 1.5 : isParking ? 1 : 6,
          z: isDrainage ? -1 : 0,
          color: isBuilding
            ? "#d1d5db"
            : isDrainage
              ? "#bfdbfe"
              : isUtility
                ? "#e9d5ff"
                : isRoad || isParking
                  ? "#cbd5e1"
                  : "#e5e7eb",
          label: item.label ?? SITE_OBJECT_CATALOG[item.type ?? "building"]?.label ?? "Object",
          layer: isBuilding
            ? "BUILDING"
            : isParking
              ? "PARKING"
            : isDrainage
              ? "DRAINAGE"
              : isUtility
                ? "UTILITY"
                : "ROAD",
        });
      });
    return items;
  }, [buildingPlacements, resolveLotBounds]);
  const preview3DEffectiveItems = preview3DItems.length
    ? preview3DItems
    : preview3DAnnotationItems.length
      ? preview3DAnnotationItems
      : preview3DPlacementItems;
  const usingAnnotation3D =
    preview3DItems.length === 0 && preview3DAnnotationItems.length > 0;
  const lotBounds = resolveLotBounds();
  const siteAreaAcres = siteAreaAcresFromSize(lotBounds.w, lotBounds.h);
  const siteTooLargeForWarning = siteAreaAcres > SITE_WARNING_ACRES;
  const siteTooLargeForGrading = siteAreaAcres > SITE_GRADING_HARD_BLOCK_ACRES;
  const missingSite = !(lotBounds.w && lotBounds.h);
  const missingImage = !mapSnapshotPath;
  const hasBasinPlaced = buildingPlacements.some((item) => item.type === "basin" && item.placed);
  const hasLocationEvidence =
    Boolean(siteInputs?.address || siteAddress.trim()) ||
    Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng) ||
    Boolean(uploadedImageApiUrl || uploadedImagePreviewUrl);
  const hasVerifiedSurveyControl = Boolean(surveyFileName && surveyPreviewPoints.length);
  const hasTerrainSource =
    (Boolean(surveyFileName) && useSurveyForGrading) ||
    Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng) ||
    Boolean(surveySlopeEstimate?.slope_percent);
  const siteSizeSet = Boolean(parsePositiveNumber(lotWidth) && parsePositiveNumber(lotHeight));
  const gradingSourceSummary = useMemo(() => {
    const hasSurvey = Boolean(siteInputs?.survey_file?.stored_filename || siteInputs?.survey_file?.survey_url);
    const hasMapAnalysis = Boolean(siteInputs?.map_analysis);
    const hasMapSnapshot = Boolean(siteInputs?.map_snapshot?.stored_filename || siteInputs?.map_snapshot?.image_path);
    const hasAddress = Boolean(siteInputs?.address);
    if (hasSurvey) {
      return "Survey/topo (highest trust)";
    }
    if (hasMapAnalysis || hasMapSnapshot) {
      return "Image/map inferred (approximate)";
    }
    if (hasAddress) {
      return "Address-only context (approximate)";
    }
    return "Fallback assumptions";
  }, [siteInputs]);

  useEffect(() => {
    if (debugGradingFixtureLoaded) return;
    if (typeof window === "undefined") return;
    if (process.env.NODE_ENV === "production") return;
    const params = new URLSearchParams(window.location.search);
    if (!params.has("debugGradingBlocked")) return;
    const lotW = lotBounds.w || 200;
    const lotH = lotBounds.h || 200;
    const source = { x: lotBounds.x + lotW * 0.2, y: lotBounds.y + lotH * 0.2 };
    const target = { x: lotBounds.x + lotW * 0.8, y: lotBounds.y + lotH * 0.8 };
    const blocker = { x: lotBounds.x + lotW * 0.5, y: lotBounds.y + lotH * 0.5, approximate: true };
    const fixZone = {
      x: lotBounds.x + lotW * 0.25,
      y: lotBounds.y + lotH * 0.25,
      w: lotW * 0.5,
      h: lotH * 0.5,
      approximate: true,
    };
    const fixture = {
      code: "DRAINAGE_BLOCKED_BY_GRADING",
      severity: "warning" as const,
      message: "Proposed grading blocks flow paths that were reachable on existing terrain.",
      context: {
        explanation: "Proposed grading blocks flow paths that would otherwise reach the basin.",
        reason: "proposed_surface_blocks_flow",
        best_next_fix: "Introduce a grading swale toward the basin or lower the ridge between inlet and basin.",
        suggested_actions: [
          "Introduce a grading swale toward the basin.",
          "Lower local ridge between inlet and basin.",
          "Adjust pad edges to restore flow.",
        ],
        blocker_type: "ridge",
        source_point: source,
        blocked_target: target,
        blocker_location: blocker,
        suggested_fix_zone: fixZone,
        approximate: true,
      },
    };
    setIssues((prev) => {
      if (prev.some((issue) => (issue.code ?? "").toUpperCase() === "DRAINAGE_BLOCKED_BY_GRADING")) {
        return prev;
      }
      return [...prev, fixture];
    });
    setDebugGradingFixtureLoaded(true);
  }, [debugGradingFixtureLoaded, lotBounds.h, lotBounds.w, lotBounds.x, lotBounds.y]);
  const drainageSurfaceSummary = useMemo(() => {
    if (!drainageSummary || typeof drainageSummary !== "object") {
      return {
        surfaceSource: "unknown",
        surfaceQuality: "",
        surfaceDetail: "",
        surfaceFromGrading: false,
      };
    }
    const guidance = (drainageSummary as { surface_guidance?: Record<string, unknown> }).surface_guidance ?? {};
    const surfaceSource = String(guidance.surface_source || "unknown");
    const surfaceQuality = String(guidance.surface_source_quality || "");
    const surfaceDetail = String(guidance.surface_source_detail || "");
    const surfaceFromGrading = Boolean(guidance.surface_from_grading);
    return { surfaceSource, surfaceQuality, surfaceDetail, surfaceFromGrading };
  }, [drainageSummary]);
  const mapAnalysisCounts = useMemo(() => {
    if (!mapAnalysis || typeof mapAnalysis !== "object") return { zones: 0, objects: 0, centerlines: 0 };
    const record = mapAnalysis as { counts?: { zones?: number; objects?: number; centerlines?: number } };
    return {
      zones: record.counts?.zones ?? 0,
      objects: record.counts?.objects ?? 0,
      centerlines: record.counts?.centerlines ?? 0,
    };
  }, [mapAnalysis]);
  const selectedAccessIssue = useMemo(
    () => analysisIssues.find((issue) => issue.id === analysisSelectedIssueId) ?? null,
    [analysisIssues, analysisSelectedIssueId],
  );
  const confirmedObjectCounts = useMemo(() => {
    const confirmed = buildingPlacements.filter(
      (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
    );
    const buildingTypes = new Set<SiteObjectType>([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
    ]);
    const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
    return {
      buildings: confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType)).length,
      access: confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType)).length,
    };
  }, [buildingPlacements]);
  const buildAnalysisReport = useCallback(
    (selectedOnly: boolean) => {
      const confirmed = buildingPlacements.filter(
        (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
      );
      const buildingTypes = new Set<SiteObjectType>([
        "building",
        "retail_building",
        "multifamily_building",
        "industrial_building",
        "office_building",
        "pad",
      ]);
      const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
      const buildings = confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType));
      const access = confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType));
      const selectedIssue = selectedOnly
        ? analysisIssues.find((issue) => issue.id === analysisSelectedIssueId) ?? null
        : null;
      const issues = selectedOnly && selectedIssue ? [selectedIssue] : analysisIssues;
      const paths = selectedOnly && selectedIssue
        ? analysisPaths.filter((path) => path.id === selectedIssue.pathId)
        : analysisPaths;
      const resolvedSurfaceSource =
        drainageSurfaceSummary.surfaceSource && drainageSurfaceSummary.surfaceSource !== "unknown"
          ? drainageSurfaceSummary.surfaceSource
          : gradingSourceSummary;
      return {
        generated_at: new Date().toISOString(),
        note: "Conceptual access analysis. Not a code compliance determination.",
        surface_source: resolvedSurfaceSource,
        threshold_ft: issues[0]?.thresholdFt ?? 150,
        buildings: buildings.map((b) => ({
          id: b.id,
          label: b.label,
          type: b.type,
          x: b.x,
          y: b.y,
          w: b.w,
          d: b.d,
        })),
        access_objects: access.map((a) => ({
          id: a.id,
          label: a.label,
          type: a.type,
          x: a.x,
          y: a.y,
          w: a.w,
          d: a.d,
        })),
        issues: issues.map((issue) => {
          const path = analysisPaths.find((candidate) => candidate.id === issue.pathId);
          return {
            issue_id: issue.id,
            issue_type: issue.issueType,
            building_id: issue.buildingId,
            access_object_id: issue.accessId,
            distance_ft: issue.distanceFt,
            threshold_ft: issue.thresholdFt,
            message: issue.message,
            surface_source: resolvedSurfaceSource,
            path_coordinates: path
              ? {
                  from: path.from,
                  to: path.to,
                  points: path.points ?? [path.from, path.to],
                }
              : null,
          };
        }),
        paths,
      };
    },
    [
      analysisIssues,
      analysisPaths,
      analysisSelectedIssueId,
      buildingPlacements,
      drainageSurfaceSummary,
      gradingSourceSummary,
    ],
  );

  const exportAnalysisReport = useCallback(() => {
    const report = buildAnalysisReport(false);
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "civora-access-analysis.json";
    link.click();
    URL.revokeObjectURL(url);
  }, [buildAnalysisReport]);

  const exportSelectedAnalysis = useCallback(() => {
    if (!analysisSelectedIssueId) return;
    const report = buildAnalysisReport(true);
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "civora-access-analysis-selected.json";
    link.click();
    URL.revokeObjectURL(url);
  }, [analysisSelectedIssueId, buildAnalysisReport]);

  const copyAnalysisJson = useCallback(async () => {
    const report = buildAnalysisReport(false);
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      setStatusMessage("Analysis JSON copied to clipboard.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Clipboard copy failed.",
      );
    }
  }, [buildAnalysisReport]);
  const filteredDetectedPlacements = useMemo(() => {
    const threshold = detectionConfidenceFilter === "high" ? 0.6 : detectionConfidenceFilter === "medium" ? 0.3 : 0.0;
    return detectedPlacements.filter((item) => (item.confidence ?? 0) >= threshold);
  }, [detectedPlacements, detectionConfidenceFilter]);
  const sortedProjects = useMemo(
    () => [...projects].sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0)),
    [projects],
  );
  const hasHardSystemBlock = issues.some((issue) => issue.severity === "error") || siteTooLargeForGrading;
  const existingConditionRows = [
    {
      label: "Address / location evidence",
      value: hasLocationEvidence ? "Imported / applied" : "Missing",
      status: hasLocationEvidence ? "review" : "block",
      action: "Setup panel -> enter an address, pick a geocode suggestion, then Apply address.",
    },
    {
      label: "Survey / control",
      value: hasVerifiedSurveyControl ? "Uploaded / verify control" : "Missing verified control",
      status: hasVerifiedSurveyControl ? "review" : "block",
      action: "Import & Survey panel -> upload survey/topo/control evidence.",
    },
    {
      label: "Datum / CRS",
      value: (siteInputs as { coordinate_system?: string } | null)?.coordinate_system || "Missing",
      status: (siteInputs as { coordinate_system?: string } | null)?.coordinate_system ? "review" : "block",
      action: "Data panel -> add coordinate system/datum evidence when available.",
    },
    {
      label: "Terrain",
      value: hasTerrainSource ? "Available for review" : "Missing survey, DEM, or assumed slope",
      status: hasTerrainSource ? "review" : "block",
      action: "Import & Survey panel -> upload terrain, apply geocoded map terrain, or choose assumed slope when prompted.",
    },
    {
      label: "GIS / map context",
      value: mapAnalysis?.success ? "Analyzed" : uploadedImageApiUrl || uploadedImagePreviewUrl ? "Image uploaded" : "Missing",
      status: mapAnalysis?.success || uploadedImageApiUrl || uploadedImagePreviewUrl ? "review" : "block",
      action: "Setup panel -> upload a map snapshot and run Analyze map snapshot.",
    },
  ] as const;
  const getSystemBlockers = (target: "grading" | "drainage" | "storm" | "sanitary" | "water" | "utilities" | "roadway") => {
    const blockers: string[] = [];
    if (missingSite) blockers.push("Set site width and depth.");
    if (!siteScaleLocked) blockers.push("Lock the site boundary.");
    if (siteTooLargeForGrading && (target === "grading" || target === "drainage" || target === "storm")) {
      blockers.push(OVERSIZED_SITE_MESSAGE);
    }
    if ((target === "grading" || target === "drainage" || target === "storm") && !hasTerrainSource) {
      blockers.push("Add survey, DEM/geocoded terrain, or explicitly accept an assumed slope.");
    }
    if ((target === "drainage" || target === "storm") && !hasBasinPlaced) {
      blockers.push("Place a basin or outfall target.");
    }
    if (target === "roadway" && confirmedObjectCounts.buildings === 0 && confirmedObjectCounts.access === 0) {
      blockers.push("Add at least one building, entrance, driveway, road, or parking object.");
    }
    if ((target === "sanitary" || target === "water" || target === "utilities") && !utilities) {
      blockers.push("Enable utility generation.");
    }
    if ((target === "sanitary" || target === "water") && confirmedObjectCounts.buildings === 0) {
      blockers.push("Add buildings or service/demand targets.");
    }
    if (hasHardSystemBlock && target !== "roadway") {
      blockers.push("Resolve active hard model blockers.");
    }
    return blockers;
  };
  const systemReadinessRows = [
    { key: "grading", label: "Grading", panel: "grading" as SidePanelKey, runTarget: "grading" as SystemGenerationTarget, status: systemStatuses.grading, blockers: getSystemBlockers("grading") },
    { key: "drainage", label: "Drainage", panel: "drainage" as SidePanelKey, runTarget: "drainage" as SystemGenerationTarget, status: systemStatuses.drainage, blockers: getSystemBlockers("drainage") },
    { key: "storm", label: "Storm", panel: "drainage" as SidePanelKey, runTarget: "drainage" as SystemGenerationTarget, status: systemStatuses.drainage, blockers: getSystemBlockers("storm") },
    { key: "sanitary", label: "Sanitary", panel: "sanitary" as SidePanelKey, runTarget: "utilities" as SystemGenerationTarget, status: systemStatuses.utilities, blockers: getSystemBlockers("sanitary") },
    { key: "water", label: "Water", panel: "water" as SidePanelKey, runTarget: "utilities" as SystemGenerationTarget, status: systemStatuses.utilities, blockers: getSystemBlockers("water") },
    { key: "utilities", label: "Utilities", panel: "utilities" as SidePanelKey, runTarget: "utilities" as SystemGenerationTarget, status: systemStatuses.utilities, blockers: getSystemBlockers("utilities") },
    { key: "roadway", label: "Roadway", panel: "roadway" as SidePanelKey, runTarget: "roads" as SystemGenerationTarget, status: systemStatuses.roads, blockers: getSystemBlockers("roadway") },
  ] as const;
  const workflowActionHints = [
    !hasLocationEvidence ? "Setup panel -> Start from address or blank site." : "",
    !siteSizeSet ? "Setup panel -> enter site width and depth." : "",
    !buildingPlacements.some((item) => item.type === "site") ? "Setup panel -> Draw site boundary." : "",
    !siteScaleLocked ? "Setup panel -> Lock site boundary." : "",
    existingConditionRows.some((item) => item.status === "block") ? "Data panel -> resolve missing existing-condition evidence." : "",
    placedObjectCount <= 1 ? "Objects panel -> add or draw buildings, parking, roads, basin/outfall, and utility points/lines." : "",
    systemReadinessRows.some((row) => row.blockers.length) ? `Generate Systems panel -> ${systemReadinessRows.find((row) => row.blockers.length)?.label}: ${systemReadinessRows.find((row) => row.blockers.length)?.blockers[0]}` : "",
    getExportBlockReason() ? `Deliver panel -> export blocked: ${getExportBlockReason()}.` : "",
  ].filter(Boolean);
  const formatSupportValue = (value: string, blocked = false) => ({ value, status: blocked ? "block" : "review" });
  const deliverableSupportRows = [
    ["DXF", formatSupportValue(getExportBlockReason() || (backendResult ? "Review export available" : "Needs planner run"), Boolean(getExportBlockReason()))],
    ["Engineer-review report", formatSupportValue(getExportBlockReason() || (backendResult ? "Available" : "Needs planner run"), Boolean(getExportBlockReason()))],
    ["LandXML", formatSupportValue("Not generated in this UI yet", true)],
    ["Civil 3D", formatSupportValue("No native Civil 3D package; use review exports externally", true)],
    ["DWG", formatSupportValue("Not exported directly; DXF review export only", true)],
    ["Construction document support package", formatSupportValue(backendResult ? "Review-only package; external engineer approval required" : "Needs run and review gates", !backendResult)],
    ["External engineer approval", formatSupportValue("Always required outside Civora")],
  ] as const;
  const capabilityAuditRows = useMemo<CapabilityExposure[]>(() => {
    const meta = currentPlanMeta as Record<string, unknown>;
    const readRecord = (key: string): Record<string, unknown> =>
      meta[key] && typeof meta[key] === "object" ? (meta[key] as Record<string, unknown>) : {};
    const readArray = (record: Record<string, unknown>, key: string): unknown[] =>
      Array.isArray(record[key]) ? (record[key] as unknown[]) : [];
    const blockerCount = (record: Record<string, unknown>) =>
      readArray(record, "blockers").length +
      readArray(record, "warnings").length +
      readArray(record, "missing_inputs").length;
    const packageStatus = (...keys: string[]) => {
      for (const key of keys) {
        const rec = readRecord(key);
        const status = String(
          rec.status ||
            rec.review_status ||
            rec.export_status ||
            rec.readiness_status ||
            rec.qa_status ||
            "",
        );
        if (status) return status;
      }
      return "";
    };
    const hasRecord = (...keys: string[]) => keys.some((key) => Object.keys(readRecord(key)).length > 0);
    const statusFrom = (present: boolean, blocked: boolean, review = true): SidebarStatus =>
      !present ? "idle" : blocked ? "block" : review ? "review" : "ok";
    const row = (
      key: string,
      label: string,
      present: boolean,
      surfaces: string[],
      value: string,
      missingWiring: string,
      exactFix: string,
      blocked = false,
      review = true,
    ): CapabilityExposure => ({
      key,
      label,
      exposed: present ? "yes" : "no",
      surfaces,
      status: statusFrom(present, blocked, review),
      value,
      missingWiring: present ? "None for status visibility" : missingWiring,
      exactFix: present ? "Review the listed blockers or accept/reupload evidence where required." : exactFix,
    });

    const standardsPackage = readRecord("standards_package");
    const standardsRegistry = readRecord("standards_source_registry");
    const standardsCandidateReport = readRecord("candidate_rule_report");
    const standardsAcceptanceReport = readRecord("standards_acceptance_report");
    const existingPackage = readRecord("existing_conditions_package");
    const surveyControl = readRecord("survey_control_package");
    const mapFeatureReport = readRecord("map_feature_detection_report_v1");
    const engineDepth = readRecord("engine_depth_audit");
    const productionEvidence = readRecord("production_evidence");
    const quantityCost = productionEvidence.quantity_cost && typeof productionEvidence.quantity_cost === "object"
      ? (productionEvidence.quantity_cost as Record<string, unknown>)
      : {};
    const exportPackage = readRecord("export_package_report_v1");
    const constructionPackage = readRecord("construction_document_support_package_v1");
    const constructionManifest = readRecord("construction_package_manifest");
    const engineerReviewPackage = readRecord("engineer_review_package_v1");
    const reactiveReport = readRecord("reactive_update_report");
    const reactivePartial = readRecord("reactive_partial_rerun");
    const handoffs =
      Array.isArray((currentProject?.project_input?.manual_fields as Record<string, unknown> | undefined)?.canonical_geometry_handoff_v1)
        ? ((currentProject?.project_input?.manual_fields as Record<string, unknown>).canonical_geometry_handoff_v1 as unknown[])
        : buildingPlacements.filter((item) => item.meta && typeof item.meta === "object" && "canonical_geometry_handoff_v1" in item.meta);
    const mapCandidateCount = Number(mapFeatureReport.candidate_count ?? 0);
    const acceptedStandards = Number(
      standardsCandidateReport.accepted_rule_count ??
        (standardsAcceptanceReport.rules && typeof standardsAcceptanceReport.rules === "object"
          ? (standardsAcceptanceReport.rules as Record<string, unknown>).accepted_rule_count
          : 0) ??
        0,
    );
    const standardsCandidateCount = Number(
      standardsCandidateReport.candidate_count ??
        (standardsAcceptanceReport.rules && typeof standardsAcceptanceReport.rules === "object"
          ? ((standardsAcceptanceReport.rules as Record<string, unknown>).candidates as Record<string, unknown> | undefined)?.candidate_count
          : 0) ??
        0,
    );
    const surveyPresent = hasRecord("survey_control_package") || hasVerifiedSurveyControl;
    const existingPresent = hasRecord("existing_conditions_package") || existingConditionRows.some((item) => item.status !== "block");
    const costPresent = hasRecord("production_evidence") || hasRecord("cost_estimate") || quantityRows.length > 0;
    const exportBlocked = Boolean(exportPackage.export_blocked || getExportBlockReason());
    const reactivePresent = hasRecord("reactive_update_report") || hasRecord("reactive_partial_rerun") || reactiveChangedSystems.length > 0;
    return [
      row(
        "standards_source_registry",
        "Standards source registry",
        hasRecord("standards_source_registry", "standards_package"),
        ["UI", "chat", "API", "report"],
        standardsRegistry.accepted_source_count !== undefined
          ? `${standardsRegistry.accepted_source_count} accepted source(s)`
          : packageStatus("standards_package") || "Needs accepted official source",
        "Registry is only produced after standards discovery/acceptance evidence exists.",
        "Run standards discovery, review candidate sources, accept official HTTPS sources, then regenerate the standards package.",
        blockerCount(standardsPackage) > 0 || standardsRegistry.accepted_source_count === 0,
      ),
      row(
        "candidate_standards_review",
        "Candidate standards review",
        hasRecord("candidate_rule_report", "standards_acceptance_report", "standards_package"),
        ["UI", "chat", "API", "report"],
        `${standardsCandidateCount || 0} candidate(s), ${acceptedStandards || 0} accepted`,
        "Candidate rules are absent until extraction/review packet evidence is saved.",
        "Extract standards candidates or build a standards review packet, then accept/reject each candidate rule.",
        standardsCandidateCount > 0 && acceptedStandards === 0,
      ),
      row(
        "existing_conditions_package",
        "Existing conditions package",
        existingPresent,
        ["UI", "chat", "API", "report"],
        packageStatus("existing_conditions_package") || (existingPresent ? "Imported / review required" : "Missing imports"),
        "No existing conditions import package is attached.",
        "Upload survey/topo/GIS files or fetch online existing-condition sources, then rerun import validation.",
        blockerCount(existingPackage) > 0 || !hasLocationEvidence,
      ),
      row(
        "survey_control_package",
        "Survey control package",
        surveyPresent,
        ["UI", "chat", "API", "report"],
        packageStatus("survey_control_package") || (hasVerifiedSurveyControl ? "Uploaded / verify control" : "Missing verified control"),
        "Survey/control status is blocked until control evidence exists.",
        "Upload survey/control evidence with datum, benchmark, coordinate system, and verification status.",
        blockerCount(surveyControl) > 0 || !hasVerifiedSurveyControl,
      ),
      row(
        "map_feature_candidates",
        "Map feature candidates",
        hasRecord("map_feature_detection_report_v1") || Boolean(mapAnalysis?.success || uploadedImageApiUrl || uploadedImagePreviewUrl),
        ["UI", "chat", "API", "report"],
        mapCandidateCount ? `${mapCandidateCount} candidate(s) need review` : mapAnalysis?.success ? "Map analyzed; candidates need review" : "No candidates yet",
        "No map feature report is attached.",
        "Upload/analyze a map snapshot or accept GIS feature sources, then review candidates before drafting objects.",
        blockerCount(mapFeatureReport) > 0 || mapCandidateCount === 0,
      ),
      row(
        "engine_depth_audit",
        "Engine depth audit",
        hasRecord("engine_depth_audit", "engine_readiness"),
        ["UI", "chat", "API", "report"],
        packageStatus("engine_depth_audit", "engine_readiness") || "Needs generated model evidence",
        "No engine depth audit is present in the current plan meta.",
        "Run the planner or golden depth audit so each discipline records readiness, blockers, and validation depth.",
        blockerCount(engineDepth) > 0,
      ),
      row(
        "production_evidence",
        "Production evidence",
        hasRecord("production_evidence"),
        ["UI", "chat", "API", "report"],
        productionEvidence.production_evidence_ready === true ? "Ready for review handoff" : "Review/blocked evidence only",
        "No canonical production evidence record is present.",
        "Run production evidence assembly after standards, existing conditions, quantities, export audit, and reactive checks exist.",
        productionEvidence.production_evidence_ready !== true,
      ),
      row(
        "cost_book_pricing",
        "Cost book / pricing",
        costPresent,
        ["UI", "chat", "API", "report"],
        quantityCost.ready === true ? "Approved pricing source covers quantities" : "Blocked without approved/current unit-price book",
        "Cost pricing validation is absent until quantities and a unit-price book exist.",
        "Normalize and validate an approved unit-price book, then rerun quantities/cost evidence.",
        quantityCost.ready !== true,
      ),
      row(
        "export_package_report",
        "Export package report",
        hasRecord("export_package_report_v1") || Boolean(backendResult),
        ["UI", "chat", "API", "report"],
        packageStatus("export_package_report_v1") || (exportBlocked ? String(getExportBlockReason()) : "Review export available"),
        "No export package report has been generated yet.",
        "Generate a report/DXF export package so export audit, support matrix, traceability, and blockers are recorded.",
        exportBlocked || blockerCount(exportPackage) > 0,
      ),
      row(
        "construction_document_support_package",
        "Construction document support package",
        hasRecord("construction_document_support_package_v1", "construction_package_manifest"),
        ["UI", "chat", "API", "report"],
        packageStatus("construction_document_support_package_v1", "construction_package_manifest") || "Review-only support; external approval required",
        "Construction document support package is not attached to this plan.",
        "Build the construction document support package after deliverable artifacts, standards, survey/control, QA, and pricing evidence exist.",
        blockerCount(constructionPackage) > 0 || blockerCount(constructionManifest) > 0 || true,
      ),
      row(
        "engineer_review_package",
        "Engineer review package",
        hasRecord("engineer_review_package_v1"),
        ["UI", "chat", "API", "report"],
        packageStatus("engineer_review_package_v1") ||
          (blockerCount(engineerReviewPackage)
            ? `${blockerCount(engineerReviewPackage)} review blocker(s)`
            : "External licensed engineer review required"),
        "No engineer review package is attached.",
        "Generate the engineer review package from the current plan and route blockers to a licensed external reviewer.",
        true,
      ),
      row(
        "reactive_rerun_evidence",
        "Reactive rerun evidence",
        reactivePresent,
        ["UI", "chat", "API", "report"],
        reactiveRerunSummary.enabled
          ? `${reactiveRerunSummary.rerunStages.length} rerun stage(s), ${reactiveRerunSummary.skippedStages.length} skipped`
          : reactiveChangedSystems.length
            ? `${reactiveChangedSystems.length} stale system(s) need rerun`
            : "No reactive rerun yet",
        "Reactive evidence appears only after a saved edit or partial rerun.",
        "Make a scoped model edit, confirm the reactive policy if required, and run the dependency-aware partial rerun.",
        readArray(reactiveReport, "stale_outputs").length > 0 || readArray(reactivePartial, "stale_outputs").length > 0 || reactiveChangedSystems.length > 0,
      ),
      row(
        "cad_geometry_handoff",
        "CAD geometry handoff",
        handoffs.length > 0 || placedObjectCount > 0,
        ["UI", "chat", "API", "report"],
        handoffs.length ? `${handoffs.length} canonical handoff(s)` : placedObjectCount ? "Draft objects need canonical handoff review" : "No geometry yet",
        "No canonical geometry handoff exists.",
        "Draw or import geometry, classify it, then preserve the canonical_geometry_handoff_v1 record for CAD/export.",
        handoffs.length === 0,
      ),
    ];
  }, [
    backendResult,
    buildingPlacements,
    currentPlanMeta,
    currentProject?.project_input?.manual_fields,
    existingConditionRows,
    getExportBlockReason,
    hasLocationEvidence,
    hasVerifiedSurveyControl,
    mapAnalysis,
    placedObjectCount,
    quantityRows.length,
    reactiveChangedSystems,
    reactiveRerunSummary,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
  ]);
  const systemHealthItems = useMemo(
    () => [
      {
        key: "data",
        label: "Data",
        state: siteScaleLocked || hasTerrainSource ? "complete" : "not_configured",
        detail: siteScaleLocked ? "Site locked" : "Needs site setup",
      },
      {
        key: "roadway",
        label: "Roadway",
        state: systemStatuses.roads === "fresh" && systemStatuses.parking === "fresh" ? "complete" : "not_configured",
        detail: systemStatuses.roads === "fresh" ? "Complete" : "Not configured / not rendered",
      },
      {
        key: "grading",
        label: "Grading",
        state: siteTooLargeForGrading ? "blocked" : systemStatuses.grading === "fresh" ? "complete" : "not_configured",
        detail: siteTooLargeForGrading ? "Site too large" : systemStatuses.grading === "fresh" ? "Complete" : "Needs terrain/run",
      },
      {
        key: "drainage",
        label: "Drainage",
        state: hasHardSystemBlock ? "blocked" : systemStatuses.drainage === "fresh" ? "complete" : "not_configured",
        detail: hasHardSystemBlock ? "Review blockers" : systemStatuses.drainage === "fresh" ? "Complete" : "Needs basin/run",
      },
      {
        key: "utilities",
        label: "Utilities",
        state: hasHardSystemBlock ? "blocked" : systemStatuses.utilities === "fresh" ? "complete" : "not_configured",
        detail: hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured / not rendered",
      },
    ],
    [hasHardSystemBlock, hasTerrainSource, siteScaleLocked, siteTooLargeForGrading, systemStatuses],
  );
  const selectedBuilding = useMemo(
    () => buildingPlacements.find((item) => item.id === activePlacementId) ?? null,
    [activePlacementId, buildingPlacements],
  );
  const sidePanelCopy: Record<SidePanelKey, { title: string; desc: string }> = {
    projects: { title: "Projects", desc: "Open, create, and manage project records." },
    dashboard: { title: "Dashboard", desc: "Review project readiness, health, and active work." },
    model: { title: "Canvas", desc: "Design, prompt-create, generate systems, and open contextual discipline controls." },
    site_existing: { title: "Project Setup", desc: "Start from address, blank site, site size, boundary drawing, and first objects." },
    import_survey: { title: "Import & Survey", desc: "Bring in survey, map snapshots, and terrain sources." },
    objects: { title: "Objects", desc: "Add, size, and place model objects." },
    generate: { title: "Generate Systems", desc: "Run focused engines from one control panel." },
    grading: { title: "Grading Controls", desc: "Control grading rules, terrain inputs, and slope limits." },
    drainage: { title: "Drainage Controls", desc: "Control drainage rules, sources, and repair behavior." },
    sanitary: { title: "Sanitary Controls", desc: "Configure sanitary coverage, slopes, and service assumptions." },
    water: { title: "Water Controls", desc: "Configure water, hydrant, loop, and pressure assumptions." },
    utilities: { title: "Utility Controls", desc: "Control utility generation and coordination assumptions." },
    roadway: { title: "Roadway Controls", desc: "Control roads, parking, and corridor behavior." },
    landscape: { title: "Landscape Controls", desc: "Place open space and landscape-related site objects." },
    details: { title: "Sections", desc: "Review profiles, cross sections, selected objects, locks, and engineering metadata." },
    layers: { title: "Layers", desc: "Choose visible model layers and labels." },
    analysis: { title: "Issues", desc: "Track active model issues, access findings, blockers, and QA signals." },
    reports: { title: "Review", desc: "Review engineer gates, assumptions, standards, conflicts, and system readiness." },
    quantities: { title: "Quantities", desc: "Review takeoff totals, stale labels, source confidence, and cost inputs." },
    deliverables: { title: "Deliver", desc: "Review sheets, reports, quantities, profiles, sections, exports, and package gates." },
    files: { title: "Files", desc: "Manage imported inputs and generated outputs." },
    standards: { title: "Standards", desc: "Review rule packs, assumptions, and project criteria." },
    libraries: { title: "Libraries", desc: "Use reusable objects, templates, and project presets." },
    data: { title: "Data", desc: "Configure survey, terrain, GIS, parcels, standards sources, imported utilities, and confidence labels." },
    settings: { title: "Settings", desc: "Set project rules, defaults, and run preferences." },
    chat: { title: "Civora AI", desc: "Conversation and assisted workflow control." },
    system_grading: { title: "Grading Health", desc: "Review what grading needs before it can be trusted." },
    system_storm: { title: "Storm Drainage Health", desc: "Review what storm drainage needs before it can be trusted." },
    system_sanitary: { title: "Sanitary Sewer Health", desc: "Review what sanitary needs before it can be trusted." },
    system_water: { title: "Water Health", desc: "Review what water needs before it can be trusted." },
    system_roadway: { title: "Roadway Health", desc: "Review what roadway needs before it can be trusted." },
    system_utilities: { title: "Utilities Health", desc: "Review what utility coordination needs before it can be trusted." },
    system_landscape: { title: "Landscape Health", desc: "Review what landscape needs before it can be trusted." },
  };
  const disciplinePanelLinks: Array<{ panel: SidePanelKey; label: string }> = [
    { panel: "grading", label: "Grading" },
    { panel: "drainage", label: "Drainage" },
    { panel: "utilities", label: "Utilities" },
    { panel: "roadway", label: "Roadway" },
    { panel: "landscape", label: "Landscape" },
  ];
  const sidePanelForRender = activeSidePanel ?? renderedSidePanel;
  const isDisciplinePanel = disciplinePanelLinks.some((item) => item.panel === sidePanelForRender);
  const workspaceModeByPanel: Record<SidePanelKey, WorkspaceMode> = {
    projects: "dashboard",
    dashboard: "dashboard",
    model: "canvas",
    site_existing: "setup",
    import_survey: "setup",
    objects: "canvas",
    generate: "canvas",
    grading: "canvas",
    drainage: "canvas",
    sanitary: "canvas",
    water: "canvas",
    utilities: "canvas",
    roadway: "canvas",
    landscape: "canvas",
    details: "review",
    layers: "layers",
    analysis: "review",
    reports: "review",
    quantities: "deliver",
    deliverables: "deliver",
    files: "data",
    standards: "data",
    libraries: "data",
    data: "data",
    settings: "settings",
    chat: "canvas",
    system_grading: "review",
    system_storm: "review",
    system_sanitary: "review",
    system_water: "review",
    system_roadway: "review",
    system_utilities: "review",
    system_landscape: "review",
  };
  const workspacePanelByMode: Record<WorkspaceMode, SidePanelKey> = {
    dashboard: "dashboard",
    setup: "site_existing",
    canvas: "model",
    layers: "layers",
    review: "reports",
    deliver: "deliverables",
    data: "data",
    settings: "settings",
  };
  const handleOpenSidePanel = useCallback((panel: SidePanelKey | null) => {
    if (sidePanelCloseTimeoutRef.current !== null) {
      window.clearTimeout(sidePanelCloseTimeoutRef.current);
      sidePanelCloseTimeoutRef.current = null;
    }
    setActiveSidePanel(panel);
    if (!panel) return;
    setActiveWorkspaceMode(workspaceModeByPanel[panel]);
    const workflowByPanel: Partial<Record<SidePanelKey, CivoraWorkflowStep>> = {
      dashboard: "Review",
      model: "Concept",
      site_existing: "Concept",
      import_survey: "Concept",
      objects: "Concept",
      generate: "Concept",
      grading: "Grading",
      drainage: "Drainage",
      sanitary: "Utilities",
      water: "Utilities",
      utilities: "Utilities",
      roadway: "Concept",
      landscape: "Concept",
      details: "Review",
      analysis: "Review",
      reports: "Deliverables",
      quantities: "Deliverables",
      deliverables: "Deliverables",
      files: "Deliverables",
      standards: "Review",
      libraries: "Concept",
      data: "Concept",
      settings: "Concept",
      chat: "Concept",
      system_grading: "Review",
      system_storm: "Review",
      system_sanitary: "Review",
      system_water: "Review",
      system_roadway: "Review",
      system_utilities: "Review",
      system_landscape: "Review",
    };
    const nextStep = workflowByPanel[panel];
    if (nextStep) setActiveWorkflowStep(nextStep);
  }, []);
  const handleCloseSidePanel = useCallback(() => {
    if (sidePanelCloseTimeoutRef.current !== null) {
      window.clearTimeout(sidePanelCloseTimeoutRef.current);
    }
    setSidePanelVisible(false);
    sidePanelCloseTimeoutRef.current = window.setTimeout(() => {
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      sidePanelCloseTimeoutRef.current = null;
    }, 180);
  }, []);
  const handleOpenWorkspaceMode = useCallback((mode: WorkspaceMode) => {
    handleOpenSidePanel(workspacePanelByMode[mode]);
    setActiveWorkspaceMode(mode);
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setLeftSidebarOpen(false);
    }
  }, [handleOpenSidePanel]);
  const controlsHealthStatus = Object.values(systemStatuses).some((value) => value === "fresh") ? "ok" : "review";
  const panelStatus = (target: SidePanelKey): SidebarStatus => {
    if (target === "dashboard" || target === "analysis") {
      return issues.length || analysisIssues.length || hasHardSystemBlock ? "review" : backendResult ? "ok" : "idle";
    }
    if (target === "site_existing" || target === "data") {
      return siteScaleLocked || Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng) ? "ok" : "review";
    }
    if (target === "import_survey" || target === "files") {
      return hasTerrainSource || surveyPreviewPoints.length || uploadedImagePreviewUrl || uploadedImageApiUrl || mapSnapshotPath
        ? "ok"
        : "review";
    }
    if (target === "model" || target === "layers") {
      return placedObjectCount > 0 || planPreviewUrl ? "ok" : "idle";
    }
    if (target === "objects" || target === "details") {
      return buildingPlacements.length > 0 ? "ok" : "idle";
    }
    if (target === "generate") {
      return controlsHealthStatus;
    }
    if (target === "grading") {
      return siteTooLargeForGrading ? "block" : hasTerrainSource || systemStatuses.grading === "fresh" ? "ok" : "review";
    }
    if (target === "drainage") {
      return hasHardSystemBlock ? "block" : hasBasinPlaced || systemStatuses.drainage === "fresh" ? "ok" : "review";
    }
    if (target === "sanitary" || target === "water" || target === "utilities") {
      return hasHardSystemBlock ? "block" : utilities || systemStatuses.utilities === "fresh" ? "ok" : "review";
    }
    if (target === "roadway") {
      return roads || systemStatuses.roads === "fresh" ? "ok" : "review";
    }
    if (target === "landscape") {
      return buildingPlacements.some((value) => ["open_space", "amenity", "pool", "sidewalk"].includes(value.type ?? ""))
        ? "ok"
        : "idle";
    }
    if (target === "reports" || target === "quantities" || target === "deliverables") {
      return backendResult ? "ok" : "idle";
    }
    if (target === "standards") {
      return minSlopePct || maxRoadGradePct || pipeMinSlopePct || maxAdaCrossSlopePct ? "ok" : "review";
    }
    if (target === "libraries" || target === "settings" || target === "chat" || target === "projects") {
      return "ok";
    }
    return "idle";
  };
  const sidebarModeStatus = (mode: WorkspaceMode): SidebarStatus => {
    if (mode === "dashboard") return panelStatus("dashboard");
    if (mode === "setup") return siteScaleLocked ? "ok" : "review";
    if (mode === "canvas") return panelStatus("model");
    if (mode === "layers") return panelStatus("layers");
    if (mode === "review") return hasHardSystemBlock ? "block" : issues.length || analysisIssues.length ? "review" : panelStatus("reports");
    if (mode === "deliver") return String(previewReview?.release_status || "review").toLowerCase() === "blocked" ? "block" : panelStatus("deliverables");
    if (mode === "data") return panelStatus("data");
    if (mode === "settings") return panelStatus("settings");
    return "idle";
  };
  const sidebarModes: SidebarNavItem[] = [
    { label: "Dashboard", caption: "Project status", target: "dashboard", icon: Gauge, status: sidebarModeStatus("dashboard") },
    { label: "Setup", caption: "Site and boundary", target: "setup", icon: MapPinned, status: sidebarModeStatus("setup") },
    { label: "Canvas", caption: "Design workspace", target: "canvas", icon: Box, status: sidebarModeStatus("canvas") },
    { label: "Layers", caption: "Visibility presets", target: "layers", icon: Layers, status: sidebarModeStatus("layers") },
    { label: "Review", caption: "Gates and health", target: "review", icon: ClipboardCheck, status: sidebarModeStatus("review") },
    { label: "Deliver", caption: "Sheets and exports", target: "deliver", icon: FileText, status: sidebarModeStatus("deliver") },
    { label: "Data", caption: "Survey and sources", target: "data", icon: MapPinned, status: sidebarModeStatus("data") },
    { label: "Settings", caption: "Workspace defaults", target: "settings", icon: Settings, status: sidebarModeStatus("settings") },
  ];
  const sidebarStaleSystems = (Object.entries(systemStatuses) as Array<[EngineeringSystemKey, SystemStatus]>)
    .filter(([, status]) => status === "stale")
    .map(([system]) => system);
  const sidebarMissingInputs = [
    missingSite ? "site" : null,
    !hasTerrainSource ? "terrain" : null,
    !hasBasinPlaced && systemStatuses.drainage !== "fresh" ? "basin" : null,
  ].filter(Boolean) as string[];
  const sidebarHasTruthEvidence = Boolean(
    backendResult ||
      siteScaleLocked ||
      buildingPlacements.length ||
      siteAddress.trim() ||
      siteInputs?.address ||
      siteInputs?.geocode?.lat ||
      siteInputs?.geocode?.lng ||
      uploadedImagePreviewUrl ||
      uploadedImageApiUrl ||
      surveyPreviewPoints.length ||
      mapSnapshotPath,
  );
  const sidebarReleaseStatus = String(previewReview?.release_status || "review").toLowerCase();
  const sidebarTrustScore =
    typeof previewReview?.trust_score === "number" ? `${Math.round(previewReview.trust_score)}%` : "not reported";
  const sidebarAssumptions = Array.isArray(previewReview?.assumption_categories)
    ? previewReview.assumption_categories.filter(Boolean)
    : [];
  const sidebarTruthItems: Array<{ label: string; value: string; status: SidebarStatus }> = [
    {
      label: "Engineer review",
      value: !sidebarHasTruthEvidence
        ? "not evaluated"
        : sidebarReleaseStatus === "ready"
          ? "ready_for_engineer_review"
          : sidebarReleaseStatus === "blocked"
            ? "blocked"
            : "review required",
      status: !sidebarHasTruthEvidence ? "idle" : sidebarReleaseStatus === "blocked" ? "block" : "review",
    },
    {
      label: "Construction blocks",
      value: sidebarHasTruthEvidence ? "external approval required" : "not evaluated",
      status: sidebarHasTruthEvidence ? "block" : "idle",
    },
    {
      label: "Low confidence",
      value: !sidebarHasTruthEvidence
        ? "not evaluated"
        : typeof previewReview?.trust_score === "number" && previewReview.trust_score >= 80
          ? "none flagged"
          : sidebarTrustScore,
      status: !sidebarHasTruthEvidence
        ? "idle"
        : typeof previewReview?.trust_score === "number" && previewReview.trust_score >= 80
          ? "ok"
          : "review",
    },
    {
      label: "Assumptions",
      value: !backendResult
        ? "not evaluated"
        : sidebarAssumptions.length
          ? `${sidebarAssumptions.length} need acceptance`
          : "none reported",
      status: !backendResult ? "idle" : sidebarAssumptions.length ? "review" : "ok",
    },
    {
      label: "Stale outputs",
      value: !backendResult
        ? "not evaluated"
        : sidebarStaleSystems.length
          ? sidebarStaleSystems.slice(0, 2).join(", ")
          : "none",
      status: !backendResult ? "idle" : sidebarStaleSystems.length ? "review" : "ok",
    },
    {
      label: "Blocked systems",
      value: !sidebarHasTruthEvidence
        ? "not evaluated"
        : hasHardSystemBlock || previewBlockedReasons.length
          ? "review blockers"
          : "none recorded",
      status: !sidebarHasTruthEvidence ? "idle" : hasHardSystemBlock || previewBlockedReasons.length ? "block" : "ok",
    },
  ] as const;
  const sidebarTruthCounts = {
    ready: sidebarHasTruthEvidence ? sidebarTruthItems.filter((item) => item.status === "ok").length : 0,
    review: sidebarHasTruthEvidence ? sidebarTruthItems.filter((item) => item.status === "review").length : 0,
    blocked: sidebarHasTruthEvidence ? sidebarTruthItems.filter((item) => item.status === "block").length : 0,
    notRun: backendResult ? 0 : 1,
  };
  const sidebarTruthTotal = Math.max(
    1,
    sidebarTruthCounts.ready +
      sidebarTruthCounts.review +
      sidebarTruthCounts.blocked +
      sidebarTruthCounts.notRun,
  );
  const sidebarTruthScore = sidebarHasTruthEvidence
    ? Math.max(
        0,
        Math.min(
          100,
          Math.round(
            ((sidebarTruthCounts.ready + sidebarTruthCounts.review * 0.45) /
              sidebarTruthTotal) *
              100,
          ),
        ),
      )
    : null;
  const truthReadyDeg = (sidebarTruthCounts.ready / sidebarTruthTotal) * 360;
  const truthReviewDeg = truthReadyDeg + (sidebarTruthCounts.review / sidebarTruthTotal) * 360;
  const truthBlockedDeg = truthReviewDeg + (sidebarTruthCounts.blocked / sidebarTruthTotal) * 360;
  const reviewGateItems = [
    {
      label: "Standards",
      value: panelStatus("standards") === "ok" ? "engineer/user acceptance" : "sources or criteria needed",
      status: panelStatus("standards") === "ok" ? "review" : "block",
    },
    {
      label: "Survey / control",
      value: hasTerrainSource ? "verification required" : "missing",
      status: hasTerrainSource ? "review" : "block",
    },
    {
      label: "Calculations",
      value: backendResult ? "engineer review required" : "not generated",
      status: backendResult ? "review" : "block",
    },
    {
      label: "Exports",
      value: sidebarReleaseStatus === "ready" ? "review package ready" : sidebarReleaseStatus === "blocked" ? "blocked" : "review package",
      status: sidebarReleaseStatus === "blocked" ? "block" : "review",
    },
    {
      label: "External approval",
      value: "required outside Civora",
      status: "review",
    },
  ] as const;
  const setupChecklistItems = [
    {
      label: "Address / map",
      value: siteAddress.trim() || uploadedImageApiUrl || uploadedImagePreviewUrl ? "Set" : "Missing",
      status: siteAddress.trim() || uploadedImageApiUrl || uploadedImagePreviewUrl ? "review" : "block",
    },
    {
      label: "Site size",
      value: siteSizeSet
        ? `${parsePositiveNumber(lotWidth)?.toFixed(0)} ft x ${parsePositiveNumber(lotHeight)?.toFixed(0)} ft`
        : "Missing",
      status: siteSizeSet ? "review" : "block",
    },
    {
      label: "Site boundary",
      value: siteScaleLocked ? "Locked" : buildingPlacements.some((item) => item.type === "site") ? "Drawn / unlocked" : "Unlocked",
      status: siteScaleLocked ? "review" : "block",
    },
    {
      label: "Existing conditions",
      value: hasTerrainSource || uploadedImageApiUrl || uploadedImagePreviewUrl ? "Imported" : "Missing",
      status: hasTerrainSource || uploadedImageApiUrl || uploadedImagePreviewUrl ? "review" : "block",
    },
    {
      label: "Standards",
      value: panelStatus("standards") === "ok" ? "Selected / needs acceptance" : "Missing",
      status: panelStatus("standards") === "ok" ? "review" : "block",
    },
  ] as const;
  const nextSetupAction = !siteAddress.trim() && !uploadedImageApiUrl && !uploadedImagePreviewUrl
    ? "Start from address/map or choose blank site."
    : !siteSizeSet
      ? "Set site width and length, or enter acreage through chat."
      : !buildingPlacements.some((item) => item.type === "site")
        ? "Draw or add the site boundary."
        : !siteScaleLocked
          ? "Lock the site boundary before generating systems."
          : placedObjectCount <= 1
            ? "Add or draw buildings, roads, parking, and utilities."
            : "Run systems, then review blockers and gates.";
  const selectedCanvasObject = activePlacementId
    ? buildingPlacements.find((item) => item.id === activePlacementId) ??
      filteredDetectedPlacements.find((item) => item.id === activePlacementId) ??
      null
    : null;
  const bottomBlockerItems = [
    ...previewBlockedReasons,
    ...issues.map((issue) => issue.message),
    ...analysisIssues.map((issue) => issue.message),
  ].filter(Boolean);
  const bottomPanelTabs: Array<{ key: BottomPanelTab; label: string; panel: SidePanelKey }> = [
    { key: "model_review", label: "Model Review", panel: "reports" },
    { key: "systems", label: "Systems", panel: "generate" },
    { key: "objects", label: "Objects", panel: "objects" },
    { key: "properties", label: "Properties", panel: selectedCanvasObject ? "details" : "site_existing" },
    { key: "history", label: "History", panel: "dashboard" },
  ];
  const activePanelTitle =
    previewMode === "3d" && sidePanelForRender === "model"
      ? "3D"
      : sidePanelForRender
        ? sidePanelCopy[sidePanelForRender].title
        : "";
  const activePanelDescription =
    previewMode === "3d" && sidePanelForRender === "model"
      ? "Cinematic engineering visualization and review with the same truthful readiness gates."
      : sidePanelForRender
        ? sidePanelCopy[sidePanelForRender].desc
        : "";

  if (!effectiveUser) {
    return (
      <AuthScreen
        authMode={authMode}
        authStatus={authStatus}
        authStatusError={authStatusError}
        authName={authName}
        authEmail={authEmail}
        authPassword={authPassword}
        showPassword={showPassword}
        authError={authError}
        authLoading={authLoading}
        onAuthModeChange={setAuthMode}
        onAuthNameChange={setAuthName}
        onAuthEmailChange={setAuthEmail}
        onAuthPasswordChange={setAuthPassword}
        onTogglePassword={() => setShowPassword((value) => !value)}
        onClearAuthError={() => setAuthError("")}
        onSubmit={handleAuth}
      />
    );
  }

  return (
    <div className="civora-app-bg min-h-screen text-[var(--civora-text)]">
      <div className="flex min-h-screen flex-col">
        <AppHeader
          userEmail={effectiveUser.email}
          onOpenDashboard={() => handleOpenSidePanel("dashboard")}
          onOpenDocs={() => handleOpenSidePanel("deliverables")}
          onOpenChat={() => handleOpenSidePanel("chat")}
          sidebarOpen={leftSidebarOpen}
          onToggleSidebar={() => setLeftSidebarOpen((value) => !value)}
          onLogout={handleLogout}
        />

        <div className="flex h-[calc(100vh-4rem)] min-h-0 flex-col overflow-hidden lg:flex-row">
          {sidebarRendered ? (
          <aside
            data-testid="left-sidebar"
            data-motion-state={sidebarVisible ? "open" : "closed"}
            aria-hidden={!sidebarVisible}
            className="civora-motion-sidebar fixed inset-x-3 top-20 z-40 flex max-h-[calc(100vh-6rem)] shrink-0 flex-col rounded-xl border border-slate-200 bg-white/98 px-4 py-5 shadow-[0_28px_80px_-42px_rgba(15,23,42,0.65)] backdrop-blur-xl lg:static lg:inset-auto lg:z-auto lg:h-full lg:max-h-none lg:w-[276px] lg:rounded-none lg:border-y-0 lg:border-l-0 lg:shadow-[18px_0_40px_-36px_rgba(15,23,42,0.5)]"
          >
            <button
              type="button"
              onClick={() => handleOpenWorkspaceMode("dashboard")}
              className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-left transition hover:bg-white"
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Project</p>
              <p className="mt-1 truncate text-sm font-semibold text-slate-950">
                {siteName || currentProject?.name || "Untitled Project"}
              </p>
              <div className="mt-2 grid gap-1 text-[11px] font-semibold text-slate-500">
                <span className="flex items-center justify-between gap-2">
                  <span>Site</span>
                  <span className={siteScaleLocked ? "text-slate-900" : "text-amber-700"}>
                    {siteScaleLocked ? "Locked" : "Not locked"}
                  </span>
                </span>
                <span className="flex items-center justify-between gap-2">
                  <span>Sync</span>
                  <span className={currentProject?.project_id ? "text-slate-900" : "text-amber-700"}>
                    {currentProject?.project_id ? "Saved" : "Draft"}
                  </span>
                </span>
              </div>
            </button>
            <div className="mb-4 rounded-lg border border-slate-200 bg-white px-3 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Truth Status
              </p>
              <div className="mt-3 flex items-center gap-4">
                <div
                  className="grid h-24 w-24 shrink-0 place-items-center rounded-full"
                  style={{
                    background: `conic-gradient(#64748b 0deg ${truthReadyDeg}deg, #f59e0b ${truthReadyDeg}deg ${truthReviewDeg}deg, #8b5cf6 ${truthReviewDeg}deg ${truthBlockedDeg}deg, #cbd5e1 ${truthBlockedDeg}deg 360deg)`,
                  }}
                  aria-label={sidebarTruthScore === null ? "Truth status not evaluated" : `Truth score ${sidebarTruthScore}`}
                >
                  <div className="grid h-16 w-16 place-items-center rounded-full bg-white text-center shadow-inner">
                    <span className="text-xl font-semibold text-slate-950">{sidebarTruthScore ?? "-"}</span>
                    <span className="-mt-2 text-[9px] font-semibold text-slate-500">
                      {sidebarTruthScore === null ? "No data" : "Overall"}
                    </span>
                  </div>
                </div>
                <div className="min-w-0 flex-1 space-y-1.5">
                  {[
                    ["Ready", sidebarTruthCounts.ready, "bg-slate-500"],
                    ["Review", sidebarTruthCounts.review, "bg-amber-500"],
                    ["Blocked", sidebarTruthCounts.blocked, "bg-violet-500"],
                    ["Not Run", sidebarTruthCounts.notRun, "bg-slate-300"],
                  ].map(([label, value, dotClass]) => (
                    <div key={label} className="flex items-center justify-between gap-2 text-[11px] font-semibold text-slate-600">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${dotClass}`} />
                        <span className="truncate">{label}</span>
                      </span>
                      <span className="text-slate-500">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <p className="mt-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                {sidebarHasTruthEvidence
                  ? "Engineer review required | Construction blocked until external approval"
                  : "No project evidence yet | Engineer review required before release"}
              </p>
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto pr-1">
              <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Workspace
              </p>
              {sidebarModes.map((item) => {
                const isActive = activeWorkspaceMode === item.target;
                const status = item.status;
                const Icon = item.icon;
                const StatusIcon = status === "ok" ? CheckCircle2 : status === "block" ? AlertCircle : status === "review" ? AlertCircle : Circle;
                return (
                  <button
                    key={item.target}
                    type="button"
                    onClick={() => handleOpenWorkspaceMode(item.target)}
                    className={`flex min-h-12 items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition ${
                      isActive
                        ? "bg-slate-950 text-white"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
                    }`}
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold">{item.label}</span>
                        <span className={`block truncate text-[10px] font-semibold uppercase tracking-[0.12em] ${
                          isActive ? "text-white/55" : "text-slate-400"
                        }`}>
                          {item.caption}
                        </span>
                      </span>
                    </span>
                    <StatusIcon
                      className={`h-3.5 w-3.5 shrink-0 ${
                        isActive
                          ? "text-white/80"
                          : status === "ok"
                            ? "text-slate-700"
                            : status === "block"
                              ? "text-red-500"
                              : status === "review"
                                ? "text-amber-500"
                                : "text-slate-300"
                      }`}
                    />
                  </button>
                );
              })}
            </div>
            <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-3 text-left text-slate-900">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Command</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <button type="button" aria-label="Open chat from sidebar command" onClick={() => handleOpenSidePanel("chat")} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-2 text-xs font-semibold text-slate-700 hover:bg-white">
                  Chat
                </button>
                <button type="button" onClick={() => handleOpenSidePanel("generate")} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-2 text-xs font-semibold text-slate-700 hover:bg-white">
                  Generate
                </button>
              </div>
            </div>
          </aside>
          ) : null}
          {sidePanelForRender ? (
            <aside
              data-testid="workspace-right-panel"
              data-motion-state={sidePanelVisible ? "open" : "closed"}
              aria-hidden={!sidePanelVisible}
              className="civora-motion-right-panel order-3 m-3 flex min-h-0 w-auto shrink-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white/96 shadow-[var(--civora-shadow-panel)] backdrop-blur-xl lg:ml-0 lg:h-[calc(100%-1.5rem)] lg:w-[372px]"
            >
              <div className="flex items-center justify-between border-b border-[var(--civora-border)] px-4 py-4">
                <div>
                  <p className="civora-muted-label">{activePanelTitle}</p>
                  <p className="mt-1 text-sm text-[var(--civora-text-muted)]">
                    {activePanelDescription}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (sidePanelCloseTimeoutRef.current !== null) {
                      window.clearTimeout(sidePanelCloseTimeoutRef.current);
                    }
                    setSidePanelVisible(false);
                    sidePanelCloseTimeoutRef.current = window.setTimeout(() => {
                      setActiveSidePanel(null);
                      setRenderedSidePanel(null);
                      sidePanelCloseTimeoutRef.current = null;
                    }, 180);
                  }}
                  className="civora-control px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--civora-text-muted)]"
                >
                  Close
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {isDisciplinePanel ? (
                  <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-2">
                    <p className="px-1 pb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Discipline controls
                    </p>
                    <div className="grid grid-cols-2 gap-1.5">
                      {disciplinePanelLinks.map((item) => (
                        <button
                          key={item.panel}
                          type="button"
                          onClick={() => handleOpenSidePanel(item.panel)}
                          aria-current={sidePanelForRender === item.panel ? "page" : undefined}
                          className={`rounded-lg border px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                            sidePanelForRender === item.panel
                              ? "border-slate-950 bg-slate-950 text-white"
                              : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
                {sidePanelForRender === "projects" ? (
                  <div className="space-y-3">
                    <button
                      type="button"
                      onClick={async () => {
                        await handleNewProject();
                        setActiveSidePanel(null);
                      }}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
                    >
                      + New Project
                    </button>
                    {sortedProjects.length ? (
                      sortedProjects.map((projectSummary) => (
                        <div
                          key={projectSummary.project_id}
                          className={`relative w-full rounded-2xl border px-4 py-3 text-left transition ${
                            projectSummary.project_id === projectId
                              ? "border-slate-900 bg-slate-950 text-white"
                              : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                          }`}
                        >
                          <button
                            type="button"
                            onClick={() => {
                              void loadProject(projectSummary.project_id);
                              setActiveSidePanel(null);
                            }}
                            className="block w-full text-left"
                          >
                            <p className="text-sm font-semibold">
                              {projectSummary.name || "Untitled Project"}
                            </p>
                            <p className="mt-1 text-xs uppercase tracking-[0.12em] opacity-70">
                              {projectSummary.description ||
                                (projectSummary.updated_at
                                  ? `Updated ${new Date(projectSummary.updated_at * 1000).toLocaleDateString()}`
                                  : "No description")}
                            </p>
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleDeleteProject(projectSummary.project_id)}
                            className={`absolute right-3 top-3 rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                              projectSummary.project_id === projectId
                                ? "border-white/40 text-white/80 hover:bg-white/10"
                                : "border-slate-200 text-slate-500 hover:bg-slate-50"
                            }`}
                          >
                            Delete
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No projects yet.</p>
                    )}
                  </div>
                ) : null}

                {sidePanelForRender === "dashboard" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Dashboard</p>
                          <p className="mt-1 text-lg font-semibold text-slate-950">{siteName || "Untitled Project"}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {fileName || "No file name"} · {lotBounds.w && lotBounds.h ? `${lotBounds.w.toFixed(0)} ft x ${lotBounds.h.toFixed(0)} ft` : "Site not locked"}
                          </p>
                        </div>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${
                          hasHardSystemBlock
                            ? "bg-red-50 text-red-600"
                            : backendResult
                              ? "bg-slate-100 text-slate-700"
                              : "bg-amber-50 text-amber-600"
                        }`}>
                          {hasHardSystemBlock ? "Blocked" : backendResult ? "Review output" : "Setup"}
                        </span>
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-2">
                        <input
                          value={siteName}
                          onChange={(event) => {
                            setSiteName(event.target.value);
                            setSiteNameAuto(false);
                          }}
                          placeholder="Project name"
                          className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-slate-400 focus:outline-none"
                        />
                        <input
                          value={fileName}
                          onChange={(event) => {
                            setFileName(event.target.value);
                            setFileNameAuto(false);
                          }}
                          placeholder="File name"
                          className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-slate-400 focus:outline-none"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          void saveProject({
                            nameOverride: siteName.trim(),
                            fileNameOverride: fileName.trim(),
                            autoNamedOverride: false,
                            autoFileNamedOverride: false,
                          })
                        }
                        className="mt-3 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
                      >
                        Save project identity
                      </button>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Objects", placedObjectCount],
                        ["Issues", issues.length + analysisIssues.length],
                        ["Fresh", Object.values(systemStatuses).filter((status) => status === "fresh").length],
                        ["Outputs", backendResult ? 1 : 0],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
                        </div>
                      ))}
                    </div>
                    {workflowReviewDashboard ? (
                      <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Run review</p>
                            <p className="mt-1 text-sm font-semibold text-slate-900">
                              {workflowReviewDashboard.operational_state || "No saved state"}
                            </p>
                          </div>
                          <span
                            className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${
                              workflowReviewDashboard.release_ready
                                ? "bg-amber-50 text-amber-700"
                                : "bg-amber-50 text-amber-700"
                            }`}
                          >
                            {workflowReviewDashboard.release_ready ? "Ready for engineer review" : "Review required"}
                          </span>
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-2">
                          {[
                            ["Runs", workflowReviewDashboard.run_count ?? 0],
                            ["Artifacts", workflowReviewDashboard.artifact_count ?? 0],
                            ["Conflicts", workflowReviewDashboard.conflict_review?.unresolved_conflict_count ?? 0],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                              <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold text-slate-700">
                          <button
                            type="button"
                            onClick={() => handleOpenSidePanel("deliverables")}
                            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left hover:bg-white"
                          >
                            <span className="block uppercase tracking-[0.14em] text-slate-400">Deliverables</span>
                            <span className="mt-1 block text-sm text-slate-900">
                              {(workflowReviewDashboard.deliverable_manager?.ready ?? []).length}/
                              {(workflowReviewDashboard.deliverable_manager?.requested ?? []).length} review ready
                            </span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenSidePanel("analysis")}
                            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left hover:bg-white"
                          >
                            <span className="block uppercase tracking-[0.14em] text-slate-400">Assumptions</span>
                            <span className="mt-1 block text-sm text-slate-900">
                              {workflowReviewDashboard.assumption_review?.requires_approval ? "Acceptance required" : "Engineer acceptance required"}
                            </span>
                          </button>
                        </div>
                        {workflowReviewDashboard.primary_attention ? (
                          <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
                            {workflowReviewDashboard.primary_attention.replace(/_/g, " ")}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Project readiness</p>
                        <span className="text-[11px] font-semibold text-slate-500">
                          {systemHealthItems.filter((item) => item.state === "complete").length}/{systemHealthItems.length}
                        </span>
                      </div>
                      <div className="mt-3 space-y-2">
                        {systemHealthItems.map((item) => (
                          <button
                            key={item.key}
                            type="button"
                            onClick={() =>
                              handleOpenSidePanel(
                                item.key === "data"
                                  ? "site_existing"
                                  : item.key === "roadway"
                                    ? "roadway"
                                    : (item.key as SidePanelKey),
                              )
                            }
                            className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left hover:bg-white"
                          >
                            <span>
                              <span className="block text-sm font-semibold text-slate-800">{item.label}</span>
                              <span className="block text-xs text-slate-500">{item.detail}</span>
                            </span>
                            <span
                              className={`h-2.5 w-2.5 rounded-full ${
                                item.state === "complete"
                                  ? "bg-emerald-500"
                                  : item.state === "blocked"
                                    ? "bg-red-500"
                                    : "bg-amber-400"
                              }`}
                            />
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Attention</p>
                      <div className="mt-3 space-y-2">
                        {[...issues.map((issue) => issue.message), ...analysisIssues.map((issue) => issue.message)].slice(0, 3).map((message) => (
                          <button
                            key={message}
                            type="button"
                            onClick={() => handleOpenSidePanel("analysis")}
                            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-white"
                          >
                            {message}
                          </button>
                        ))}
                        {!issues.length && !analysisIssues.length ? (
                          <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
                            No active issues in the current workspace.
                          </p>
                        ) : null}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Takeoff snapshot</p>
                      <div className="mt-3 space-y-2 text-sm text-slate-700">
                        {quantityRows.slice(0, 4).map((row) => (
                          <div key={row.label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                            <span className="font-semibold">{row.label}</span>
                            <span>{formatMetric(Number(row.value), row.unit)}</span>
                          </div>
                        ))}
                        {!quantityRows.length ? (
                          <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
                            Run systems to populate quantities.
                          </p>
                        ) : null}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <button type="button" onClick={() => handleOpenSidePanel("objects")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Objects</button>
                      <button type="button" onClick={() => handleOpenSidePanel("analysis")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Review</button>
                      <button type="button" data-testid="open-generate-panel" onClick={() => handleOpenSidePanel("generate")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Generate</button>
                      <button type="button" onClick={() => handleOpenSidePanel("deliverables")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Deliver</button>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "site_existing" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Project setup</p>
                          <p className="mt-1 text-lg font-semibold text-slate-950">Start the site</p>
                          <p className="mt-1 text-xs text-slate-500">
                            Set the address or blank site, define size, draw the boundary, then lock it before generating systems.
                          </p>
                        </div>
                        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
                          Engineer review required
                        </span>
                      </div>
                      <div className="mt-4 grid gap-2 sm:grid-cols-2">
                        <button
                          type="button"
                          onClick={() => {
                            setActiveSidePanel("site_existing");
                            siteAddressInputRef.current?.focus();
                            setStatusMessage("Enter an address, choose a suggestion if one appears, then apply the address.");
                          }}
                          className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-left text-sm font-semibold text-slate-800 hover:bg-white"
                        >
                          Start from address
                          <span className="mt-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                            Geocode first, then add map or terrain
                          </span>
                        </button>
                        <button
                          type="button"
                          onClick={handleStartBlankSite}
                          aria-label="Start a blank site and clear address map evidence"
                          className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-left text-sm font-semibold text-slate-800 hover:bg-white"
                        >
                          Start from blank site
                          <span className="mt-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                            Begin with editable width and length
                          </span>
                        </button>
                      </div>
                      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <label className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Address / location
                          <input
                            ref={siteAddressInputRef}
                            value={siteAddress}
                            onChange={(event) => {
                              setSiteAddress(event.target.value);
                              setSelectedAddressSuggestion(null);
                            }}
                            placeholder="123 Main St, City, State"
                            className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium normal-case tracking-normal text-slate-700 focus:border-slate-400 focus:outline-none"
                          />
                        </label>
                        {addressSuggestions.length && !siteScaleLocked ? (
                          <div className="mt-2 max-h-40 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 text-xs text-slate-600">
                            {addressSuggestions.map((suggestion) => (
                              <button
                                key={`${suggestion.lat ?? "lat"}-${suggestion.lng ?? "lng"}-${suggestion.display_name ?? "address"}`}
                                type="button"
                                aria-label={`Use address suggestion ${suggestion.display_name ?? "address"}`}
                                onClick={() => {
                                  setSelectedAddressSuggestion(suggestion);
                                  setSiteAddress(suggestion.display_name ?? siteAddress);
                                  setAddressSuggestions([]);
                                }}
                                className={`w-full rounded-lg px-3 py-2 text-left text-[12px] transition ${
                                  selectedAddressSuggestion?.display_name === suggestion.display_name
                                    ? "bg-slate-900 text-white"
                                    : "hover:bg-slate-50"
                                }`}
                              >
                                <span className="block truncate">{suggestion.display_name ?? "Address suggestion"}</span>
                              </button>
                            ))}
                          </div>
                        ) : null}
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          <button
                            type="button"
                            onClick={() => void saveSiteAddress()}
                            disabled={!siteAddress.trim()}
                            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            Apply address
                          </button>
                          <button
                            type="button"
                            onClick={() => mapSnapshotInputRef.current?.click()}
                            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                          >
                            Upload map
                          </button>
                        </div>
                      </div>
                      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Site size</p>
                        <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-600">
                          <label className="flex flex-col gap-1 font-semibold">
                            Width / length (ft)
                            <input
                              type="number"
                              value={lotWidth}
                              disabled={siteScaleLocked}
                              onChange={(event) => {
                                const nextValue = event.target.value;
                                setLotWidth(nextValue);
                                setBuildingPlacements((prev) =>
                                  prev.map((item) =>
                                    item.type === "site"
                                      ? { ...item, w: parsePositiveNumber(nextValue) ?? item.w }
                                      : item,
                                  ),
                                );
                              }}
                              className="rounded-lg border border-slate-200 bg-white px-2 py-2 disabled:cursor-not-allowed disabled:opacity-60"
                            />
                          </label>
                          <label className="flex flex-col gap-1 font-semibold">
                            Depth / length (ft)
                            <input
                              type="number"
                              value={lotHeight}
                              disabled={siteScaleLocked}
                              onChange={(event) => {
                                const nextValue = event.target.value;
                                setLotHeight(nextValue);
                                setBuildingPlacements((prev) =>
                                  prev.map((item) =>
                                    item.type === "site"
                                      ? { ...item, d: parsePositiveNumber(nextValue) ?? item.d }
                                      : item,
                                  ),
                                );
                              }}
                              className="rounded-lg border border-slate-200 bg-white px-2 py-2 disabled:cursor-not-allowed disabled:opacity-60"
                            />
                          </label>
                        </div>
                        <p className="mt-2 text-xs font-semibold text-slate-500">
                          {siteSizeSet
                            ? `${(((parsePositiveNumber(lotWidth) ?? 0) * (parsePositiveNumber(lotHeight) ?? 0)) / SQFT_PER_ACRE).toFixed(2)} acres`
                            : "Set both dimensions, or ask chat to create an acreage-based blank site."}
                        </p>
                        <div className="mt-3 grid grid-cols-3 gap-2">
                          {[1, 5, 10].map((acres) => (
                            <button
                              key={acres}
                              type="button"
                              disabled={siteScaleLocked}
                              onClick={() => {
                                const side = Math.round(Math.sqrt(acres * SQFT_PER_ACRE));
                                setLotWidth(String(side));
                                setLotHeight(String(side));
                                autoFitSite(side, side, "Blank Site Boundary", undefined, true, false);
                                setSiteSelectionMode(true);
                                setStatusMessage(`Set a blank ${acres}-acre site. Review dimensions, then draw or lock the boundary.`);
                              }}
                              className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {acres} acre{acres === 1 ? "" : "s"}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700">Next required step</p>
                        <p className="mt-1 text-sm font-semibold text-amber-900">{nextSetupAction}</p>
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Existing conditions evidence</p>
                        <div className="mt-2 space-y-2">
                          {existingConditionRows.map((item) => (
                            <div key={item.label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                              <div className="flex items-center justify-between gap-3 text-sm">
                                <span className="font-semibold text-slate-700">{item.label}</span>
                                <span className={`text-right text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                  item.status === "block" ? "text-red-600" : "text-amber-600"
                                }`}>
                                  {item.value}
                                </span>
                              </div>
                              {item.status === "block" ? (
                                <p className="mt-1 text-xs text-slate-500">{item.action}</p>
                              ) : null}
                            </div>
                          ))}
                        </div>
                        <p className="mt-2 text-xs font-medium text-slate-500">
                          No imported source is labeled survey-backed unless survey/control evidence is uploaded and reviewed.
                        </p>
                      </div>
                    </div>
                    <input
                      ref={mapSnapshotInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={async (event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) {
                          await uploadImage(file);
                        }
                        event.currentTarget.value = "";
                      }}
                    />
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Site tools</p>
                        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                          Setup only
                        </span>
                      </div>
                      <div className="mt-3 space-y-2">
                        <button
                          type="button"
                          onClick={() => mapSnapshotInputRef.current?.click()}
                          aria-label="Upload site image or map snapshot"
                          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-white"
                        >
                          <span>Upload site image / map</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{uploadedImagePreviewUrl || uploadedImageApiUrl ? "Uploaded" : "Upload"}</span>
                        </button>
                        <button
                          type="button"
                          onClick={analyzeMapSnapshot}
                          disabled={!mapSnapshotPath}
                          aria-label="Analyze uploaded map snapshot"
                          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <span>Analyze map snapshot</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{mapAnalysis?.success ? "Analyzed" : "Analyze"}</span>
                        </button>
                        <button
                          type="button"
                          onClick={handleStartSiteBoundaryDraw}
                          disabled={siteScaleLocked}
                          aria-label="Open canvas draw mode for site boundary"
                          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <span>Draw site boundary</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{siteScaleLocked ? "Locked" : "Canvas"}</span>
                        </button>
                        <button
                          type="button"
                          onClick={siteScaleLocked ? handleUnlockSite : () => void handleApplySite()}
                          aria-label={siteScaleLocked ? "Unlock site boundary for editing" : "Lock current site boundary for engineer review"}
                          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-white"
                        >
                          <span>{siteScaleLocked ? "Change site boundary" : "Lock site boundary"}</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{siteScaleLocked ? "Unlock" : "Lock"}</span>
                        </button>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Site status</p>
                      <div className="mt-3 space-y-2">
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                          <div className="flex items-center justify-between gap-3">
                            <span>Site</span>
                            <span className="truncate text-right text-xs uppercase tracking-[0.14em] text-slate-500">
                              {siteName || "Untitled"}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center justify-between gap-3 text-xs text-slate-500">
                            <span>Status</span>
                            <span>{siteScaleLocked ? "Site locked" : "Site not locked"}</span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleOpenSidePanel("objects")}
                          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          <span>Add / draw objects</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">Canvas</span>
                        </button>
                        <button
                          type="button"
                          onClick={handleAnalyzeSiteAccess}
                          disabled={confirmedObjectCounts.buildings === 0 || confirmedObjectCounts.access === 0}
                          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <span>Detect grading issues</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{analysisIssues.length ? "Reviewed" : "Run"}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleOpenSidePanel("data")}
                          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          <span>Survey, standards, GIS</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">Data</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "import_survey" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Import inputs</p>
                      <div className="mt-3 space-y-2">
                        <button type="button" onClick={() => mapSnapshotInputRef.current?.click()} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                          <span>Map snapshot / image</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{uploadedImagePreviewUrl || uploadedImageApiUrl ? "Ready" : "Upload"}</span>
                        </button>
                        <button type="button" onClick={() => surveyInputRef.current?.click()} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                          <span>Survey / topo file</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{surveyPreviewPoints.length ? "Ready" : "Upload"}</span>
                        </button>
                        <button type="button" onClick={analyzeMapSnapshot} disabled={!mapSnapshotPath} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60">
                          <span>Analyze map snapshot</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{mapAnalysis?.success ? "Ready" : "Analyze"}</span>
                        </button>
                      </div>
                      <input
                        ref={surveyInputRef}
                        type="file"
                        accept=".csv,.txt,.xml,.las,.laz,.xyz,.pts"
                        className="hidden"
                        onChange={async (event) => {
                          const file = event.currentTarget.files?.[0];
                          if (file) {
                            await uploadSurvey(file);
                          }
                          event.currentTarget.value = "";
                        }}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Survey pts", surveyPreviewPoints.length],
                        ["Terrain", hasTerrainSource ? "Ready" : "Missing"],
                        ["Image", uploadedImagePreviewUrl || uploadedImageApiUrl ? "Ready" : "Missing"],
                        ["Scale", detectionScaleFtPerPx ? `${detectionScaleFtPerPx.toFixed(2)} ft/px` : "Unset"],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Map calibration</p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => setFitToSiteRequest((value) => value + 1)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Fit to site
                        </button>
                        <button
                          type="button"
                          onClick={() => setMapCenterRequest((value) => value + 1)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Map center
                        </button>
                        <button
                          type="button"
                          onClick={() => setAlignToRoadRequest((value) => value + 1)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Align road
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSiteRotationDeg(0);
                            setSiteRotationInput("0");
                            scheduleRotationSave(0);
                          }}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Reset rotation
                        </button>
                      </div>
                      <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Rotation
                        <input
                          type="range"
                          min={-180}
                          max={180}
                          value={siteRotationDeg}
                          disabled={siteScaleLocked}
                          onChange={(event) => {
                            const value = Number(event.target.value);
                            setSiteRotationDeg(value);
                            setSiteRotationInput(String(value));
                            scheduleRotationSave(value);
                          }}
                          className="mt-2 h-2 w-full accent-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
                        />
                      </label>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "data" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Source hub</p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        {([
                          ["site_existing", "Existing Conditions"],
                          ["import_survey", "Survey / Terrain"],
                          ["files", "Files"],
                          ["standards", "Standards Sources"],
                          ["libraries", "Libraries"],
                        ] as Array<[SidePanelKey, string]>).map(([panel, label]) => (
                          <button
                            key={panel}
                            type="button"
                            onClick={() => handleOpenSidePanel(panel)}
                            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        {[
                          ["CRS / datum", (siteInputs as { coordinate_system?: string } | null)?.coordinate_system || "Not set"],
                          ["Terrain", hasTerrainSource ? "Provided" : "Missing"],
                          ["GIS", mapAnalysis?.success ? "Analyzed" : "Not analyzed"],
                          ["Confidence", sidebarTrustScore],
                        ].map(([label, value]) => (
                          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                            <p className="mt-1 truncate font-semibold text-slate-800">{value}</p>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3 space-y-2">
                        {capabilityAuditRows
                          .filter((item) =>
                            [
                              "existing_conditions_package",
                              "survey_control_package",
                              "map_feature_candidates",
                              "standards_source_registry",
                              "candidate_standards_review",
                            ].includes(item.key),
                          )
                          .map((item) => (
                            <div key={item.key} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                              <div className="flex items-center justify-between gap-3 text-sm">
                                <span className="font-semibold text-slate-700">{item.label}</span>
                                <span className={`text-right text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                  item.status === "block" ? "text-red-600" : item.status === "idle" ? "text-slate-400" : "text-amber-600"
                                }`}>
                                  {item.value}
                                </span>
                              </div>
                              {item.status === "block" || item.status === "idle" ? (
                                <p className="mt-1 text-xs text-slate-500">{item.exactFix}</p>
                              ) : null}
                            </div>
                          ))}
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Site address
                      </label>
                      <input
                        value={siteAddress}
                        onChange={(event) => {
                          setSiteAddress(event.target.value);
                          setSelectedAddressSuggestion(null);
                        }}
                        placeholder="123 Main St, City, State"
                        className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-slate-400 focus:outline-none"
                      />
                      {addressSuggestions.length ? (
                        <div className="mt-2 max-h-40 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-2 text-xs text-slate-600">
                          {addressSuggestions.map((suggestion) => (
                            <button
                              key={`${suggestion.lat ?? "lat"}-${suggestion.lng ?? "lng"}-${suggestion.display_name ?? "address"}`}
                              type="button"
                              aria-label={`Use address suggestion ${suggestion.display_name ?? "address"}`}
                              onClick={() => {
                                setSelectedAddressSuggestion(suggestion);
                                setSiteAddress(suggestion.display_name ?? siteAddress);
                                setAddressSuggestions([]);
                              }}
                              className={`w-full rounded-xl px-3 py-2 text-left text-[12px] transition ${
                                selectedAddressSuggestion?.display_name === suggestion.display_name
                                  ? "bg-slate-900 text-white"
                                  : "hover:bg-slate-50"
                              }`}
                            >
                              <span className="block truncate">{suggestion.display_name ?? "Address suggestion"}</span>
                            </button>
                          ))}
                        </div>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => void saveSiteAddress()}
                        disabled={!siteAddress.trim()}
                        className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Apply address
                      </button>
                    </div>

                  <div className="space-y-2 text-sm text-slate-700">
                      <button
                        type="button"
                        onClick={() => mapSnapshotInputRef.current?.click()}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                      >
                        <span>Upload site image / map snapshot</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {uploadedImageApiUrl || uploadedImagePreviewUrl ? "Ready" : "Upload"}
                        </span>
                      </button>
                      {imageUploadState !== "idle" ? (
                        <p className="text-xs text-slate-500">
                          {imageUploadNote ||
                            (imageUploadState === "uploading"
                              ? "Uploading image…"
                              : imageUploadState === "detecting"
                                ? "Detecting site features…"
                                : imageUploadState === "failed"
                                  ? "Image upload failed."
                                  : "Image uploaded.")}
                        </p>
                      ) : null}
                      <button
                        type="button"
                        onClick={analyzeMapSnapshot}
                        disabled={!mapSnapshotPath}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span>Analyze map snapshot</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {mapAnalysis?.success ? "Ready" : "Analyze"}
                        </span>
                      </button>
                      {siteScaleLocked ? (
                        <button
                          type="button"
                          onClick={handleUnlockSite}
                          className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                        >
                          <span>Change Site</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">Unlock</span>
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => void handleApplySite()}
                          className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                        >
                          <span>Lock Site</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">Apply</span>
                        </button>
                      )}
                      <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-600">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Site
                        </p>
                        <p className="mt-1 text-sm font-semibold text-slate-800">
                          {lotBounds.w && lotBounds.h
                            ? `Site: ${lotBounds.w.toFixed(0)} ft × ${lotBounds.h.toFixed(0)} ft`
                            : "Site: —"}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Status: {siteScaleLocked ? "Site Locked" : "Selecting Site"}
                        </p>
                        {siteTooLargeForWarning ? (
                          <p className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-700">
                            {OVERSIZED_SITE_MESSAGE}
                          </p>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleGenerateSystem("grading")}
                        disabled={missingSite || !hasTerrainSource || siteTooLargeForGrading}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span>Detect grading</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {missingSite
                            ? "Needs site"
                            : !hasTerrainSource
                              ? "Needs terrain"
                              : siteTooLargeForGrading
                                ? "Too large"
                                : "Run"}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAnalyzeImageFeatures()}
                        disabled={!mapSnapshotPath}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span>Detect site features</span>
                        <span className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                          {missingImage ? "Needs image" : detectedPlacements.length ? "Detected" : "Run"}
                        </span>
                      </button>
                      {!siteSelectionMode && buildingPlacements.some((item) => item.type === "site") ? (
                        <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-600">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            Detect existing context
                          </p>
                          <div className="mt-2 grid gap-2">
                            {(["roads", "buildings", "parking"] as const).map((key) => (
                              <label key={key} className="flex items-center gap-2">
                                <input
                                  type="checkbox"
                                  checked={detectionChoices[key]}
                                  onChange={(event) =>
                                    setDetectionChoices((prev) => ({
                                      ...prev,
                                      [key]: event.target.checked,
                                    }))
                                  }
                                />
                                <span className="capitalize">{key}</span>
                              </label>
                            ))}
                            <label className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                checked={detectionChoices.grading}
                                onChange={(event) =>
                                  setDetectionChoices((prev) => ({
                                    ...prev,
                                    grading: event.target.checked,
                                  }))
                                }
                              />
                              <span>Detect grading</span>
                            </label>
                          </div>
                          <button
                            type="button"
                            onClick={() => void runSelectedDetections()}
                            className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                          >
                            Run selected detection
                          </button>
                        </div>
                      ) : null}
                      <button
                        type="button"
                        onClick={handleAnalyzeSiteAccess}
                        disabled={confirmedObjectCounts.buildings === 0 || confirmedObjectCounts.access === 0}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                      >
                        <span>Analyze site access</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {analysisIssues.length ? "Reviewed" : "Run"}
                        </span>
                      </button>
                      {confirmedObjectCounts.buildings === 0 || confirmedObjectCounts.access === 0 ? (
                        <p className="text-xs text-slate-500">
                          Address provides site context only. Add or confirm buildings and access objects to run analysis.
                        </p>
                      ) : null}
                      {uploadedImageApiUrl || uploadedImagePreviewUrl ? (
                        <p className="text-xs text-slate-500">
                          Map snapshot loaded and ready for interpretation.
                        </p>
                      ) : null}
                      {mapAnalysis?.success ? (
                        <p className="text-xs text-slate-500">
                          Map analysis captured {mapAnalysisCounts.zones} zones,{" "}
                          {mapAnalysisCounts.objects} objects,{" "}
                          {mapAnalysisCounts.centerlines} centerlines.
                        </p>
                      ) : null}
                    </div>


                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Site rotation
                      </p>
                      <div className="mt-3 flex items-center gap-3">
                        <input
                          type="range"
                          min={-180}
                          max={180}
                          value={siteRotationDeg}
                          disabled={siteScaleLocked}
                          onChange={(event) => {
                            const value = Number(event.target.value);
                            setSiteRotationDeg(value);
                            setSiteRotationInput(String(value));
                            scheduleRotationSave(value);
                          }}
                          className="w-full disabled:cursor-not-allowed disabled:opacity-50"
                        />
                        <input
                          type="number"
                          value={siteRotationInput}
                          disabled={siteScaleLocked}
                          onChange={(event) => {
                            setSiteRotationInput(event.target.value);
                            const value = Number(event.target.value);
                            if (Number.isFinite(value)) {
                              setSiteRotationDeg(value);
                              scheduleRotationSave(value);
                            }
                          }}
                          className="w-24 rounded-lg border border-slate-200 px-2 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                        />
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setFitToSiteRequest((value) => value + 1);
                          }}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Fit to Site
                        </button>
                        <button
                          type="button"
                          onClick={() => setMapCenterRequest((value) => value + 1)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Use Map Center
                        </button>
                        <button
                          type="button"
                          onClick={() => setAlignToRoadRequest((value) => value + 1)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Align to Nearest Road
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSiteRotationDeg(0);
                            setSiteRotationInput("0");
                            scheduleRotationSave(0);
                          }}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Reset Rotation
                        </button>
                      </div>
                      {!siteScaleLocked ? (
                        <p className="mt-2 text-xs text-slate-500">
                          Hold <span className="font-semibold">R</span> and drag the canvas to rotate the site.
                        </p>
                      ) : null}
                    </div>


                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Drainage source
                      </p>
                      <p className="mt-2 text-sm font-semibold text-slate-800">
                        {drainageSourceOverride === "user" ? "User provided" : "Civora generated"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Source: {drainageSurfaceSummary.surfaceSource}
                        {drainageSurfaceSummary.surfaceQuality
                          ? ` · ${drainageSurfaceSummary.surfaceQuality.replace(/_/g, " ")}`
                          : ""}
                      </p>
                      {drainageSurfaceSummary.surfaceDetail ? (
                        <p className="mt-1 text-xs text-slate-500">
                          {drainageSurfaceSummary.surfaceDetail}
                        </p>
                      ) : null}
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
                        <span>Source override</span>
                        <select
                          value={drainageSourceOverride}
                          onChange={(event) => {
                            const next = event.target.value === "user" ? "user" : "civora";
                            setDrainageSourceOverride(next);
                            const currentInput = currentProject?.project_input ?? payloadPreview;
                            void saveProject({
                              silent: true,
                              projectInputOverride: {
                                ...currentInput,
                                input_mode: "user",
                                strict_mode: false,
                                allow_ai_fill_for_blanks: false,
                                meta: {
                                  ...(currentInput?.meta ?? {}),
                                  site_inputs: {
                                    ...(currentInput?.meta?.site_inputs ?? {}),
                                    drainage_source_override: next,
                                  },
                                },
                              },
                            });
                          }}
                          className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700"
                        >
                          <option value="civora">Civora</option>
                          <option value="user">User</option>
                        </select>
                      </label>
                    </div>

                    <input
                      ref={mapSnapshotInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={async (event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) {
                          await uploadImage(file);
                        }
                        event.currentTarget.value = "";
                      }}
                    />
                  </div>
                ) : null}

                {sidePanelForRender === "model" ? (
                  <div className="space-y-4">
                    {!siteScaleLocked ? (
                      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">Setup required</p>
                        <p className="mt-1 text-sm font-semibold text-amber-950">{nextSetupAction}</p>
                        <div className="mt-3 space-y-2">
                          {setupChecklistItems.map((item) => (
                            <div key={item.label} className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-white/80 px-3 py-2 text-sm">
                              <span className="font-semibold text-slate-700">{item.label}</span>
                              <span className={`text-right text-xs font-semibold uppercase tracking-[0.12em] ${
                                item.status === "block" ? "text-red-600" : "text-amber-700"
                              }`}>
                                {item.value}
                              </span>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          <button
                            type="button"
                            onClick={() => handleOpenSidePanel("site_existing")}
                            className="rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
                          >
                            Open setup
                          </button>
                          <button
                            type="button"
                            onClick={() => handleAddObject("site")}
                            className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-amber-800 hover:bg-amber-100"
                          >
                            Draw boundary
                          </button>
                        </div>
                      </div>
                    ) : null}
                    {previewMode === "3d" ? (
                      <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">3D engineering review</p>
                        <p className="mt-2 text-sm text-slate-600">
                          Use the canvas toolbar for 2D/3D and quality. Review geometry, grading surface, annotations, and blocked systems before export.
                        </p>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                          {[
                            ["Mode", previewMode.toUpperCase()],
                            ["Quality", previewQuality],
                            ["Surface", hasGradingSurface ? "Grading surface" : "No grading surface"],
                            ["Blocked", hasHardSystemBlock ? "Review required" : "None recorded"],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                              <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                              <p className="mt-1 font-semibold text-slate-800">{value}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Canvas
                      </p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                          <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Objects</p>
                          <p className="mt-1 text-lg font-semibold text-slate-900">{placedObjectCount}</p>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                          <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Issues</p>
                          <p className="mt-1 text-lg font-semibold text-slate-900">{issues.length + analysisIssues.length}</p>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Create and engineer</p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => handleOpenSidePanel("objects")} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-left text-sm font-semibold text-slate-800 hover:bg-white">
                          Objects
                          <span className="mt-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">Prompt and object controls</span>
                        </button>
                        <button type="button" onClick={() => handleOpenSidePanel("generate")} className="rounded-xl border border-slate-950 bg-slate-950 px-3 py-3 text-left text-sm font-semibold text-white hover:bg-slate-800">
                          Generate Systems
                          <span className="mt-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-white/60">Run engines with gates</span>
                        </button>
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Discipline panels</p>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          {([
                            ["grading", "Grading"],
                            ["drainage", "Drainage"],
                            ["utilities", "Utilities"],
                            ["roadway", "Roadway"],
                            ["landscape", "Landscape"],
                            ["details", "Selected Details"],
                          ] as Array<[SidePanelKey, string]>).map(([panel, label]) => (
                            <button
                              key={panel}
                              type="button"
                              onClick={() => handleOpenSidePanel(panel)}
                              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Canvas controls</p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        {[
                          ["View", previewMode.toUpperCase()],
                          ["Quality", previewQuality],
                        ].map(([label, value]) => (
                          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                            <p className="mt-1 font-semibold text-slate-800">{value}</p>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          View behavior
                        </p>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          {(["static", "edit"] as const).map((mode) => (
                            <button
                              key={mode}
                              type="button"
                              onClick={() => setPreviewInteraction(mode)}
                              className={`rounded-xl border px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] ${
                                previewInteraction === mode
                                  ? "border-slate-950 bg-slate-950 text-white"
                                  : "border-slate-200 bg-white text-slate-700"
                              }`}
                            >
                              {mode}
                            </button>
                          ))}
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-2">
                          {(["low", "standard", "high"] as const).map((density) => (
                            <button
                              key={density}
                              type="button"
                              onClick={() => {
                                setPreviewLabelDensityTouched(true);
                                setPreviewLabelDensity(density);
                              }}
                              className={`rounded-xl border px-2 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                previewLabelDensity === density
                                  ? "border-slate-950 bg-slate-950 text-white"
                                  : "border-slate-200 bg-white text-slate-700"
                              }`}
                            >
                              {density}
                            </button>
                          ))}
                        </div>
                        <div className="mt-3 space-y-2 text-sm font-semibold text-slate-700">
                          <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                            <span>Measurements overlay</span>
                            <input
                              type="checkbox"
                              checked={showMeasurements}
                              onChange={(event) => setShowMeasurements(event.target.checked)}
                              className="h-4 w-4 accent-slate-950"
                            />
                          </label>
                          <label className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                            <span>Calculation overlay</span>
                            <input
                              type="checkbox"
                              checked={showCalculations}
                              onChange={(event) => setShowCalculations(event.target.checked)}
                              className="h-4 w-4 accent-slate-950"
                            />
                          </label>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setFitToSiteRequest((value) => value + 1)}
                        className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                      >
                        Fit site
                      </button>
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setAnalysisSelectedIssueId(null);
                            setFocusDetectedId(null);
                            setAnalysisFocusLocked(false);
                            setFitToSiteRequest((value) => value + 1);
                          }}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Reset view
                        </button>
                        <button
                          type="button"
                          onClick={handlePreviewPlan}
                          disabled={busy}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Refresh preview
                        </button>
                        <button
                          type="button"
                          onClick={() => setPreviewFullscreenOpen(true)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Fullscreen
                        </button>
                      </div>
                      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <label className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Canvas height
                          <input
                            type="range"
                            min={590}
                            max={1200}
                            step={10}
                            value={previewHeightPx}
                            onChange={(event) => {
                              const next = Number(event.target.value);
                              if (Number.isFinite(next)) setPreviewHeightPx(next);
                            }}
                            className="mt-3 h-2 w-full accent-slate-900"
                          />
                        </label>
                        <input
                          type="number"
                          min={590}
                          max={1200}
                          step={10}
                          value={previewHeightPx}
                          onChange={(event) => {
                            const next = Number(event.target.value);
                            if (Number.isFinite(next)) setPreviewHeightPx(next);
                          }}
                          className="mt-2 h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                        />
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Legend</p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold text-slate-700">
                        {[
                          ["Buildings", "#0f172a", "solid"],
                          ["Roads", "#475569", "solid"],
                          ["Parking", "#cbd5e1", "solid"],
                          ["Drainage", "#2563eb", "solid"],
                          ["Utilities", "#7c3aed", "solid"],
                          ["Site boundary", "#94a3b8", "dash"],
                          ["AI detected", "#f59e0b", "dash"],
                          ["Survey points", "#14b8a6", "dot"],
                        ].map(([label, color, style]) => (
                          <div key={label} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                            <span
                              className={`h-3 w-8 rounded-full ${style === "dash" ? "border-t-2 border-dashed" : style === "dot" ? "w-3" : ""}`}
                              style={{
                                backgroundColor: style === "dash" ? "transparent" : color,
                                borderColor: color,
                              }}
                            />
                            <span>{label}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "generate" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Generate systems
                      </p>
                      <p className="mt-1 text-sm text-slate-600">
                        Run one discipline or regenerate the whole coordinated model.
                      </p>
                      <div className="mt-4 grid grid-cols-2 gap-2">
                        {systemReadinessRows.map((row) => {
                          const blocked = row.blockers.length > 0;
                          const statusLabel = blocked
                            ? row.blockers[0]
                            : row.status === "fresh"
                              ? "Run complete / current"
                              : busy || visibleActiveJob
                                ? "Queue or wait for current run"
                                : "Ready to run";
                          return (
                            <button
                              key={row.key}
                              type="button"
                              data-testid={`generate-${row.key}`}
                              onClick={() => blocked ? handleOpenSidePanel(row.panel) : handleGenerateSystem(row.runTarget)}
                              title={blocked ? `Blocked: ${row.blockers.join("; ")}` : `Run ${row.label}`}
                              className={`rounded-xl border px-3 py-3 text-left transition ${
                                blocked
                                  ? "border-red-100 bg-red-50 hover:border-red-200"
                                  : "border-slate-200 bg-white hover:border-slate-950 hover:bg-slate-50"
                              }`}
                            >
                              <span className={`block text-xs font-semibold uppercase tracking-[0.14em] ${
                                blocked ? "text-red-700" : "text-slate-900"
                              }`}>
                                {row.label}
                              </span>
                              <span className={`mt-1 block text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                blocked ? "text-red-500" : "text-slate-400"
                              }`}>
                                {blocked ? "Blocked" : row.status.replace("_", " ")}
                              </span>
                              <span className="mt-2 block text-[11px] leading-4 text-slate-500">
                                {statusLabel}
                              </span>
                            </button>
                          );
                        })}
                        <button
                          type="button"
                          onClick={() => handleGenerateSystem("full")}
                          className="col-span-2 rounded-xl border border-slate-950 bg-slate-950 px-3 py-3 text-left text-white transition hover:bg-slate-800"
                        >
                          <span className="block text-xs font-semibold uppercase tracking-[0.14em]">
                            Full System Run
                          </span>
                          <span className="mt-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-white/65">
                            Roads, grading, drainage, utilities
                          </span>
                        </button>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="reactive-rerun-status">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Reactive engineering</p>
                          <p className="mt-1 text-sm font-semibold text-slate-900">
                            {reactiveValidation.status === "idle"
                              ? "No stale engineering systems"
                              : reactiveValidation.status === "pending"
                                ? "Checking impacted systems"
                                : reactiveValidation.requiresConfirmation
                                  ? "Confirmation required"
                                  : "Quick partial rerun ready"}
                          </p>
                        </div>
                        <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                          reactiveValidation.requiresConfirmation
                            ? "bg-amber-100 text-amber-700"
                            : reactiveValidation.status === "idle"
                              ? "bg-slate-100 text-slate-500"
                              : "bg-emerald-100 text-emerald-700"
                        }`}>
                          {reactiveValidation.requiresConfirmation ? "Confirm" : reactiveValidation.status}
                        </span>
                      </div>
                      {reactiveValidation.message ? (
                        <p className="mt-3 text-xs leading-5 text-slate-600">{reactiveValidation.message}</p>
                      ) : null}
                      {reactiveValidation.changedTargets.length ? (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {reactiveValidation.changedTargets.slice(0, 8).map((stage) => (
                            <span key={stage} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-600">
                              {stage.replace(/_/g, " ")}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {reactiveRerunSummary.enabled ? (
                        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                          <p className="font-semibold uppercase tracking-[0.14em] text-slate-500">Last partial rerun</p>
                          <p className="mt-2">
                            {reactiveRerunSummary.checkpointRestored ? "Checkpoint restored. " : ""}
                            Reran {reactiveRerunSummary.rerunStages.length ? reactiveRerunSummary.rerunStages.join(", ") : "changed stages"}.
                          </p>
                          <p className="mt-1">
                            Skipped {reactiveRerunSummary.skippedStages.length ? reactiveRerunSummary.skippedStages.join(", ") : "clean upstream stages"}.
                          </p>
                          {typeof reactiveRerunSummary.elapsedMs === "number" ? (
                            <p className="mt-1">
                              {Math.round(reactiveRerunSummary.elapsedMs)} ms
                              {reactiveRerunSummary.withinQuickThreshold === false ? " over quick threshold" : " within quick threshold"}.
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <label className="flex items-center justify-between gap-3 text-sm font-semibold text-slate-800">
                        <span>Assisted generation</span>
                        <input
                          type="checkbox"
                          checked={assistedEnabled}
                          onChange={(event) => setAssistedEnabled(event.target.checked)}
                          className="h-4 w-4 accent-slate-950"
                        />
                      </label>
                      <p className="mt-2 text-xs text-slate-500">
                        Assisted runs can fill missing choices with explicit assumptions.
                      </p>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "grading" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Terrain", hasTerrainSource ? "Ready" : "Missing"],
                        ["Surface", hasGradingSurface ? "Rendered" : "Not rendered"],
                        ["Status", siteTooLargeForGrading ? "Blocked / unsafe" : systemStatuses.grading === "fresh" ? "Complete" : "Not configured"],
                        ["Source", useSurveyForGrading ? "Survey / terrain" : "Manual"],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Grading rules</p>
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                        <span>Use survey/terrain for grading</span>
                        <input type="checkbox" checked={useSurveyForGrading} onChange={(event) => setUseSurveyForGrading(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                      </label>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        {[
                          ["Min slope %", minSlopePct, setMinSlopePct],
                          ["Max parking %", maxParkingSlopePct, setMaxParkingSlopePct],
                          ["Max road %", maxRoadGradePct, setMaxRoadGradePct],
                          ["ADA cross %", maxAdaCrossSlopePct, setMaxAdaCrossSlopePct],
                        ].map(([label, value, setter]) => (
                          <label key={label as string} className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                            {label as string}
                            <input
                              value={value as string}
                              onChange={(event) => (setter as (next: string) => void)(event.target.value)}
                              placeholder="Auto"
                              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-700"
                            />
                          </label>
                        ))}
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Constructability controls</p>
                        <div className="mt-2 space-y-2 text-sm font-semibold text-slate-700">
                          <div className="flex items-center justify-between gap-3">
                            <span>Drain away from pads</span>
                            <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                              Reviewed in grading run
                            </span>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <span>Respect ADA paths</span>
                            <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                              Review required
                            </span>
                          </div>
                          <label className="flex items-center justify-between gap-3">
                            <span>Repair local low points</span>
                            <input type="checkbox" checked={drainageAllowSlopeAdjust} onChange={(event) => setDrainageAllowSlopeAdjust(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                          </label>
                        </div>
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Outputs</p>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                          {["2-ft contours", "Spot elevations", "ADA slope check", "Pad tie-ins"].map((label) => (
                            <span key={label} className="rounded-lg border border-slate-200 bg-white px-2 py-2">{label}</span>
                          ))}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleOpenSidePanel("analysis")}
                          className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Review grading issues
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleGenerateSystem("grading")}
                        disabled={missingSite || !hasTerrainSource || siteTooLargeForGrading}
                        className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                      >
                        Generate grading
                      </button>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "drainage" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Basin", hasBasinPlaced ? "Placed" : "Missing"],
                        ["Surface", hasTerrainSource ? "Ready" : "Missing"],
                        ["Status", hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.drainage === "fresh" ? "Complete" : "Not configured"],
                        ["Source", drainageSourceOverride === "user" ? "User" : "Civora"],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Drainage rules</p>
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                        <span>Drainage source</span>
                        <select value={drainageSourceOverride} onChange={(event) => setDrainageSourceOverride(event.target.value === "user" ? "user" : "civora")} className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700">
                          <option value="civora">Civora</option>
                          <option value="user">User</option>
                        </select>
                      </label>
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                        <span>Connect orphan inlets</span>
                        <input type="checkbox" checked={drainageConnectOrphans} onChange={(event) => setDrainageConnectOrphans(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                      </label>
                      <label className="mt-2 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                        <span>Allow slope repair</span>
                        <input type="checkbox" checked={drainageAllowSlopeAdjust} onChange={(event) => setDrainageAllowSlopeAdjust(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                      </label>
                      <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Max slope adjustment
                        <input
                          value={drainageMaxSlopeAdjust}
                          type="number"
                          step="0.001"
                          onChange={(event) => setDrainageMaxSlopeAdjust(Number(event.target.value) || 0)}
                          className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-700"
                        />
                      </label>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Hydrology assumptions</p>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                          <span className="rounded-lg border border-slate-200 bg-white px-2 py-2">Low point detection</span>
                          <span className="rounded-lg border border-slate-200 bg-white px-2 py-2">Flow path routing</span>
                          <span className="rounded-lg border border-slate-200 bg-white px-2 py-2">Basin targeting</span>
                          <span className="rounded-lg border border-slate-200 bg-white px-2 py-2">Overflow checks</span>
                        </div>
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Drainage objects</p>
                        <div className="mt-2 grid grid-cols-3 gap-2">
                          {(["basin", "inlet", "outfall"] as const).map((type) => (
                            <button
                              key={type}
                              type="button"
                              onClick={() => handleAddObject(type)}
                              className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
                            >
                              {SITE_OBJECT_CATALOG[type].label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleGenerateSystem("drainage")}
                        disabled={missingSite || !hasTerrainSource || !hasBasinPlaced}
                        className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                      >
                        Generate drainage
                      </button>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "utilities" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Status", hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured"],
                        ["Storm", drainage ? "Enabled" : "Off"],
                        ["Sanitary", utilities ? "Enabled" : "Off"],
                        ["Water", utilities ? "Enabled" : "Off"],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Utility rules</p>
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                        <span>Include utilities</span>
                        <input type="checkbox" checked={utilities} onChange={(event) => setUtilities(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                      </label>
                      <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Pipe min slope %
                        <input
                          value={pipeMinSlopePct}
                          onChange={(event) => setPipeMinSlopePct(event.target.value)}
                          placeholder="Auto"
                          className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-700"
                        />
                      </label>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Coordination rules</p>
                        <div className="mt-2 space-y-2 text-sm font-semibold text-slate-700">
                          {["Maintain crossing clearance", "Prefer shared corridors", "Avoid building footprints", "Reroute around conflicts"].map((label) => (
                            <div key={label} className="flex items-center justify-between gap-3">
                              <span>{label}</span>
                              <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                                Checked during utility run
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => handleOpenSidePanel("sanitary")}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Sanitary
                        </button>
                        <button
                          type="button"
                          onClick={() => handleOpenSidePanel("water")}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Water
                        </button>
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Utility objects</p>
                        <div className="mt-2 grid grid-cols-3 gap-2">
                          {(["utility_corridor", "manhole", "hydrant"] as const).map((type) => (
                            <button
                              key={type}
                              type="button"
                              onClick={() => handleAddObject(type)}
                              className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
                            >
                              {SITE_OBJECT_CATALOG[type].label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <button type="button" onClick={() => handleGenerateSystem("utilities")} className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800">
                        Generate utilities
                      </button>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "sanitary" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Status", hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured"],
                        ["Service", utilities ? "Enabled" : "Off"],
                        ["Pipe slope", pipeMinSlopePct || "Auto"],
                        ["Coverage", buildingPlacements.length ? `${confirmedObjectCounts.buildings} buildings` : "No buildings"],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Sanitary rules</p>
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                        <span>Include sanitary services</span>
                        <input type="checkbox" checked={utilities} onChange={(event) => setUtilities(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                      </label>
                      <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Minimum pipe slope %
                        <input value={pipeMinSlopePct} onChange={(event) => setPipeMinSlopePct(event.target.value)} placeholder="Auto" className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                      </label>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Service laterals</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Manhole spacing</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Cover checks</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Tie-in review</span>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => handleAddObject("manhole")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Add manhole</button>
                        <button type="button" onClick={() => handleAddObject("utility_corridor")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Add corridor</button>
                      </div>
                      <button type="button" onClick={() => handleGenerateSystem("utilities")} className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800">
                        Generate sanitary
                      </button>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "water" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Status", hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured"],
                        ["Network", utilities ? "Enabled" : "Off"],
                        ["Hydrants", buildingPlacements.filter((item) => item.type === "hydrant").length],
                        ["Buildings", confirmedObjectCounts.buildings],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Water rules</p>
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                        <span>Include water network</span>
                        <input type="checkbox" checked={utilities} onChange={(event) => setUtilities(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                      </label>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Hydrant spacing</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Looping</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Fire flow</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Velocity checks</span>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => handleAddObject("hydrant")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Add hydrant</button>
                        <button type="button" onClick={() => handleGenerateSystem("utilities")} className="rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800">Generate</button>
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender.startsWith("system_") ? (() => {
                  const healthConfig: Record<
                    Extract<SidePanelKey, "system_grading" | "system_storm" | "system_sanitary" | "system_water" | "system_roadway" | "system_utilities" | "system_landscape">,
                    { label: string; status: string; needs: string[]; openPanel: SidePanelKey }
                  > = {
                    system_grading: {
                      label: "Grading",
                      status: siteTooLargeForGrading ? "Blocked / unsafe" : systemStatuses.grading === "fresh" ? "Complete" : "Not configured / not rendered",
                      needs: [
                        siteScaleLocked ? "Site boundary locked" : "Lock a site boundary",
                        hasTerrainSource ? "Terrain source ready" : "Import survey, DEM, or map terrain",
                        siteTooLargeForGrading ? "Reduce oversized grading area" : "Area is within grading limits",
                        systemStatuses.grading === "fresh" ? "Generated grading is current" : "Run grading generation",
                      ],
                      openPanel: "grading",
                    },
                    system_storm: {
                      label: "Storm Drainage",
                      status: hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.drainage === "fresh" ? "Complete" : "Not configured / not rendered",
                      needs: [
                        hasTerrainSource ? "Terrain source ready" : "Import terrain for flow direction",
                        hasBasinPlaced ? "Basin placed" : "Place a detention basin",
                        systemStatuses.drainage === "fresh" ? "Drainage generated" : "Run drainage generation",
                        hasHardSystemBlock ? "Resolve hard system blockers" : "No hard blockers detected",
                      ],
                      openPanel: "drainage",
                    },
                    system_sanitary: {
                      label: "Sanitary Sewer",
                      status: hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured / not rendered",
                      needs: [
                        buildingPlacements.length ? "Buildings available for service coverage" : "Add buildings or service targets",
                        utilities ? "Utility generation enabled" : "Enable utilities",
                        pipeMinSlopePct ? "Minimum pipe slope configured" : "Set or accept automatic pipe slope",
                        systemStatuses.utilities === "fresh" ? "Utility network generated" : "Run utility generation",
                      ],
                      openPanel: "sanitary",
                    },
                    system_water: {
                      label: "Water",
                      status: hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured / not rendered",
                      needs: [
                        utilities ? "Water network enabled" : "Enable utilities",
                        buildingPlacements.filter((item) => item.type === "hydrant").length ? "Hydrants placed" : "Add hydrants or allow generated hydrants",
                        buildingPlacements.length ? "Demand targets available" : "Add buildings or demand targets",
                        systemStatuses.utilities === "fresh" ? "Utility network generated" : "Run utility generation",
                      ],
                      openPanel: "water",
                    },
                    system_roadway: {
                      label: "Roadway",
                      status: systemStatuses.roads === "fresh" ? "Complete" : "Not configured / not rendered",
                      needs: [
                        siteScaleLocked ? "Site boundary locked" : "Lock a site boundary",
                        roads ? "Road generation enabled" : "Enable roads",
                        systemStatuses.roads === "fresh" ? "Roadway generated" : "Run roadway generation",
                        maxRoadGradePct ? "Road grade criteria configured" : "Set or accept automatic road grade",
                      ],
                      openPanel: "roadway",
                    },
                    system_utilities: {
                      label: "Utilities",
                      status: hasHardSystemBlock ? "Blocked / unsafe" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured / not rendered",
                      needs: [
                        utilities ? "Utility generation enabled" : "Enable utilities",
                        systemStatuses.drainage === "fresh" ? "Storm context ready" : "Generate or review drainage first",
                        hasHardSystemBlock ? "Resolve hard conflicts" : "No hard blockers detected",
                        systemStatuses.utilities === "fresh" ? "Utilities generated" : "Run utility generation",
                      ],
                      openPanel: "utilities",
                    },
                    system_landscape: {
                      label: "Landscape",
                      status: buildingPlacements.some((value) => ["open_space", "amenity", "pool"].includes(value.type ?? "")) ? "Complete" : "Not configured / not rendered",
                      needs: [
                        buildingPlacements.some((value) => value.type === "open_space") ? "Open space placed" : "Add open space",
                        buildingPlacements.some((value) => value.type === "sidewalk") ? "Pedestrian paths placed" : "Add pedestrian paths",
                        buildingPlacements.some((value) => ["amenity", "pool"].includes(value.type ?? "")) ? "Amenity objects placed" : "Add amenity objects if needed",
                      ],
                      openPanel: "landscape",
                    },
                  };
                  const config = healthConfig[sidePanelForRender as keyof typeof healthConfig];
                  return (
                    <div className="space-y-4">
                      <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{config.label} readiness</p>
                        <p className="mt-2 text-lg font-semibold text-slate-950">{config.status}</p>
                        <div className="mt-4 space-y-2">
                          {config.needs.map((need) => (
                            <div key={need} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                              <span>{need}</span>
                            </div>
                          ))}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleOpenSidePanel(config.openPanel)}
                          className="mt-4 w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
                        >
                          Open controls
                        </button>
                      </div>
                    </div>
                  );
                })() : null}

                {sidePanelForRender === "roadway" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Roads", systemStatuses.roads === "fresh" ? "Complete" : "Not configured"],
                        ["Parking", systemStatuses.parking === "fresh" ? "Complete" : "Not configured"],
                        ["Max grade", maxRoadGradePct || "Auto"],
                        ["Angle", `${parkingAngle} deg`],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Roadway rules</p>
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                        <span>Generate roads</span>
                        <input type="checkbox" checked={roads} onChange={(event) => setRoads(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                      </label>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Parking angle
                          <select
                            value={parkingAngle}
                            onChange={(event) => setParkingAngle(event.target.value as "90" | "60" | "45")}
                            className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm normal-case tracking-normal text-slate-700"
                          >
                            <option value="90">90 deg</option>
                            <option value="60">60 deg</option>
                            <option value="45">45 deg</option>
                          </select>
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Parking load
                          <select
                            value={parkingLoading}
                            onChange={(event) => setParkingLoading(event.target.value as "single" | "double")}
                            className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm normal-case tracking-normal text-slate-700"
                          >
                            <option value="double">Double loaded</option>
                            <option value="single">Single loaded</option>
                          </select>
                        </label>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Stall width
                          <input value={parkingStallWidth} onChange={(event) => setParkingStallWidth(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Aisle width
                          <input value={parkingAisleWidth} onChange={(event) => setParkingAisleWidth(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Stall depth
                          <input value={parkingStallDepth} onChange={(event) => setParkingStallDepth(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Road max %
                          <input value={maxRoadGradePct} onChange={(event) => setMaxRoadGradePct(event.target.value)} placeholder="Auto" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          ADA spaces
                          <input value={parkingAdaCount} onChange={(event) => setParkingAdaCount(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Compact spaces
                          <input value={parkingCompactCount} onChange={(event) => setParkingCompactCount(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          ADA aisle
                          <input value={parkingAdaAisleWidth} onChange={(event) => setParkingAdaAisleWidth(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Compact width
                          <input value={parkingCompactWidth} onChange={(event) => setParkingCompactWidth(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
                        </label>
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Roadway objects</p>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          {(["entrance", "road", "parking", "sidewalk"] as const).map((type) => (
                            <button key={type} type="button" onClick={() => handleAddObject(type)} className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50">
                              {SITE_OBJECT_CATALOG[type].label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => handleGenerateSystem("roads")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Roads</button>
                        <button type="button" onClick={() => handleGenerateSystem("parking")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Parking</button>
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "landscape" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        ["Status", buildingPlacements.some((item) => ["open_space", "amenity", "pool", "sidewalk"].includes(item.type ?? "")) ? "Draft" : "Not configured"],
                        ["Source", backendResult ? "Generated/model" : "User setup"],
                        ["Review", "Engineer required"],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Open space", buildingPlacements.filter((item) => item.type === "open_space").length],
                        ["Amenities", buildingPlacements.filter((item) => ["amenity", "pool"].includes(item.type ?? "")).length],
                        ["Paths", buildingPlacements.filter((item) => item.type === "sidewalk").length],
                        ["Placed", buildingPlacements.filter((item) => item.placed && ["open_space", "amenity", "pool", "sidewalk"].includes(item.type ?? "")).length],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Landscape controls</p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Open space</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Amenities</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Pedestrian paths</span>
                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2">Buffers</span>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Landscape objects</p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        {(["open_space", "amenity", "pool", "sidewalk"] as const).map((type) => (
                          <button key={type} type="button" onClick={() => handleAddObject(type)} className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
                            {SITE_OBJECT_CATALOG[type].label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "details" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Profiles and cross sections</p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        {[
                          ["Road profiles", roads ? "Review" : "No generated roads"],
                          ["Pipe profiles", utilities ? "Review" : "No generated pipes"],
                          ["Basin sections", hasBasinPlaced ? "Available" : "Needs basin"],
                          ["ADA paths", buildingPlacements.some((item) => item.type === "sidewalk") ? "Review" : "Needs paths"],
                        ].map(([label, value]) => (
                          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                            <p className="mt-1 font-semibold text-slate-800">{value}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Selected object</p>
                      {selectedBuilding ? (
                        <div className="mt-3 space-y-2 text-sm text-slate-700">
                          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Name</p>
                            <p className="mt-1 font-semibold text-slate-900">{selectedBuilding.label}</p>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Size</p>
                              <p className="mt-1 font-semibold text-slate-900">{Math.round(selectedBuilding.w)} x {Math.round(selectedBuilding.d)} ft</p>
                            </div>
                            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Status</p>
                              <p className="mt-1 font-semibold text-slate-900">{selectedBuilding.placed ? "Placed" : "Unplaced"}</p>
                            </div>
                          </div>
                          <button type="button" onClick={() => handleToggleBuildingLock(selectedBuilding.id)} disabled={selectedBuilding.type === "site"} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
                            {selectedBuilding.locked ? "Unlock object" : "Lock object"}
                          </button>
                          <div className="grid grid-cols-2 gap-2 text-[11px]">
                            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
                              X
                              <input
                                type="number"
                                value={Math.round(selectedBuilding.x ?? 0)}
                                onChange={(event) =>
                                  handleUpdateBuilding(selectedBuilding.id, {
                                    x: Number(event.target.value) || 0,
                                  })
                                }
                                className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
                              />
                            </label>
                            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
                              Y
                              <input
                                type="number"
                                value={Math.round(selectedBuilding.y ?? 0)}
                                onChange={(event) =>
                                  handleUpdateBuilding(selectedBuilding.id, {
                                    y: Number(event.target.value) || 0,
                                  })
                                }
                                className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
                              />
                            </label>
                            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
                              Rotation
                              <input
                                type="number"
                                value={Math.round(selectedBuilding.rotation ?? 0)}
                                onChange={(event) =>
                                  handleUpdateBuilding(selectedBuilding.id, {
                                    rotation: Number(event.target.value) || 0,
                                  })
                                }
                                className="rounded-md border border-slate-200 px-2 py-1 normal-case tracking-normal text-slate-700"
                              />
                            </label>
                            <label className="flex flex-col gap-1 font-semibold uppercase tracking-[0.12em] text-slate-500">
                              Source
                              <input
                                value={selectedBuilding.source ?? "user"}
                                readOnly
                                className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 normal-case tracking-normal text-slate-700"
                              />
                            </label>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setActivePlacementId(selectedBuilding.id);
                                setPlacementModeEnabled(true);
                              }}
                              className="rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800"
                            >
                              Move
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setFocusObjectId(selectedBuilding.id);
                                setActiveSidePanel(null);
                              }}
                              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                            >
                              Focus
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="mt-3 text-sm text-slate-500">Select an object on the canvas or in Objects to inspect its details.</p>
                      )}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Object list</p>
                      <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
                        {buildingPlacements.length ? (
                          buildingPlacements.map((item) => {
                            const meta = item.meta && typeof item.meta === "object" ? item.meta as Record<string, unknown> : {};
                            const isDraftReviewGeometry =
                              item.type === "custom" ||
                              item.source === "manual_drawn" ||
                              meta.classification_status === "draft_review_required" ||
                              meta.engineering_status === "draft_review_required";
                            return (
                              <button key={item.id} type="button" onClick={() => setActivePlacementId(item.id)} className={`w-full rounded-xl border px-3 py-2 text-left text-sm font-semibold transition ${activePlacementId === item.id ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-white"}`}>
                                {item.label}
                                <span className="mt-1 block text-[10px] uppercase tracking-[0.12em] opacity-70">
                                  {isDraftReviewGeometry
                                    ? "Canonical geometry · Draft review required"
                                    : `${item.placed ? "Placed" : "Not placed"} · ${item.locked ? "Locked" : "Editable"}`}
                                </span>
                              </button>
                            );
                          })
                        ) : (
                          <p className="text-sm text-slate-500">No objects yet.</p>
                        )}
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "layers" ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          setPreviewLayers((prev) =>
                            Object.fromEntries(Object.keys(prev).map((key) => [key, true])) as typeof prev,
                          )
                        }
                        className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                      >
                        Show all
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setPreviewLayers((prev) => ({
                            ...Object.fromEntries(Object.keys(prev).map((key) => [key, false])),
                            buildings: true,
                          }) as typeof prev)
                        }
                        className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                      >
                        Buildings only
                      </button>
                    </div>
                    {Object.entries(previewLayers).map(([key, value]) => (
                      <label key={key} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold capitalize text-slate-700">
                        <span>{key.replace("_", " ")}</span>
                        <input
                          type="checkbox"
                          checked={Boolean(value)}
                          onChange={(event) => setPreviewLayers((prev) => ({ ...prev, [key]: event.target.checked }))}
                          className="h-4 w-4 accent-slate-950"
                        />
                      </label>
                    ))}
                  </div>
                ) : null}

                {sidePanelForRender === "analysis" ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        ["Model issues", issues.length],
                        ["Access issues", analysisIssues.length],
                        ["Systems complete", systemHealthItems.filter((item) => item.state === "complete").length],
                        ["Blocked", systemHealthItems.filter((item) => item.state === "blocked").length],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                          <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <button type="button" onClick={handleAnalyzeSiteAccess} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50">Run access analysis</button>
                      <button type="button" onClick={() => handleOpenSidePanel("dashboard")} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50">Open dashboard</button>
                    </div>
                    {[...issues.map((issue, index) => ({ id: `issue-${index}`, message: issue.message, severity: issue.severity })), ...analysisIssues.map((issue) => ({ id: issue.id, message: issue.message, severity: "warning" as const }))].map((issue) => (
                      <div key={issue.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${issue.severity === "error" ? "text-red-600" : "text-amber-600"}`}>{issue.severity}</p>
                        <p className="mt-2 text-sm text-slate-700">{issue.message}</p>
                      </div>
                    ))}
                    {!issues.length && !analysisIssues.length ? <p className="text-sm text-slate-500">No active analysis issues.</p> : null}
                  </div>
                ) : null}

                {sidePanelForRender === "files" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Input files</p>
                      <div className="mt-3 space-y-2">
                        {[
                          ["Map snapshot", uploadedImageApiUrl || uploadedImagePreviewUrl ? "Ready" : "Not uploaded"],
                          ["Survey/topo", surveyFileName || "Not uploaded"],
                          ["Project record", currentProject?.project_id || projectId || "Draft"],
                        ].map(([label, value]) => (
                          <div key={label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                            <span className="font-semibold text-slate-700">{label}</span>
                            <span className="max-w-[150px] truncate text-xs uppercase tracking-[0.12em] text-slate-500">{value}</span>
                          </div>
                        ))}
                      </div>
                      <button type="button" onClick={() => handleOpenSidePanel("import_survey")} className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Import files</button>
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => mapSnapshotInputRef.current?.click()} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Map image</button>
                        <button type="button" onClick={() => surveyInputRef.current?.click()} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Survey file</button>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Generated outputs</p>
                      <div className="mt-3 space-y-2">
                        {[
                          ["Preview", planPreviewUrl ? "Review ready" : "Not generated"],
                          ["Report", backendResult ? "Review package" : "Not generated"],
                          ["DXF", getExportBlockReason() || (backendResult ? "Review export" : "Needs run")],
                        ].map(([label, value]) => (
                          <div key={label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                            <span className="font-semibold text-slate-700">{label}</span>
                            <span className="text-xs uppercase tracking-[0.12em] text-slate-500">{value}</span>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button type="button" onClick={handleExportDxf} disabled={Boolean(getExportBlockReason())} title={getExportBlockReason() || "Download DXF review export"} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400">DXF</button>
                        <button type="button" onClick={handleExportReport} disabled={Boolean(getExportBlockReason())} title={getExportBlockReason() || "Download engineer-review report"} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400">Report</button>
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "standards" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Active criteria</p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        {[
                          ["Min slope", minSlopePct || "Auto"],
                          ["Parking max", maxParkingSlopePct || "Auto"],
                          ["Road max", maxRoadGradePct || "Auto"],
                          ["ADA cross", maxAdaCrossSlopePct || "Auto"],
                          ["Pipe slope", pipeMinSlopePct || "Auto"],
                          ["Parking angle", `${parkingAngle} deg`],
                        ].map(([label, value]) => (
                          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                            <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Standards source registry</p>
                      <div className="mt-3 space-y-2 text-sm font-semibold text-slate-700">
                        {capabilityAuditRows
                          .filter((item) => item.key === "standards_source_registry" || item.key === "candidate_standards_review")
                          .map((item) => (
                            <div key={item.key} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                              <div className="flex items-start justify-between gap-3">
                                <span>{item.label}</span>
                                <span className={`text-right text-[10px] uppercase tracking-[0.12em] ${
                                  item.status === "block" ? "text-red-600" : item.status === "idle" ? "text-slate-400" : "text-amber-600"
                                }`}>
                                  {item.value}
                                </span>
                              </div>
                              {item.status === "block" || item.status === "idle" ? (
                                <p className="mt-1 text-xs font-medium normal-case tracking-normal text-slate-500">
                                  {item.exactFix}
                                </p>
                              ) : null}
                            </div>
                          ))}
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => handleOpenSidePanel("data")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
                          Source data
                        </button>
                        <button type="button" onClick={() => handleOpenSidePanel("reports")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
                          Review gates
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "libraries" ? (
                  <div className="space-y-4">
                    {ADD_MENU_SECTIONS.map((group) => (
                      <div key={group.key} className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{group.title}</p>
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          {group.items.map((type) => (
                            <button key={type} type="button" onClick={() => handleAddObject(type)} className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">
                              {SITE_OBJECT_CATALOG[type].label}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}

                {sidePanelForRender === "settings" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Workspace settings</p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">
                        {[
                          ["Appearance", previewQuality],
                          ["Layout", leftSidebarOpen ? "Sidebar on" : "Sidebar off"],
                          ["AI behavior", assistedEnabled ? "Assisted" : "Manual"],
                          ["Exports", sidebarReleaseStatus === "ready" ? "Review audit ready" : sidebarReleaseStatus],
                          ["Shortcuts", "Default"],
                          ["Standards", panelStatus("standards") === "ok" ? "Acceptance required" : panelStatus("standards")],
                        ].map(([label, value]) => (
                          <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="text-slate-400">{label}</p>
                            <p className="mt-1 text-slate-800">{value}</p>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => handleOpenSidePanel("standards")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Standards</button>
                        <button type="button" onClick={() => handleOpenSidePanel("deliverables")} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50">Export settings</button>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Run defaults</p>
                      <div className="mt-3 space-y-2">
                        {disciplineToggles.map((toggle) => (
                          <label key={toggle.label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                            <span>{toggle.label}</span>
                            <input type="checkbox" checked={toggle.checked} onChange={(event) => toggle.setter(event.target.checked)} className="h-4 w-4 accent-slate-950" />
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "objects" ? (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Add Object
                      </p>
                      <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                        <label className="flex items-center justify-between gap-3 text-sm font-semibold text-slate-800">
                          <span>Assisted</span>
                          <input
                            type="checkbox"
                            checked={assistedEnabled}
                            onChange={(event) => setAssistedEnabled(event.target.checked)}
                            className="h-4 w-4 accent-slate-950"
                          />
                        </label>
                      </div>
                      <div className="mt-3 flex flex-col gap-2">
                        <input
                          value={objectPrompt}
                          onChange={(event) => setObjectPrompt(event.target.value)}
                          placeholder="building 110x58, road, basin..."
                          className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-slate-400 focus:outline-none"
                        />
                        <div className="flex items-center gap-3">
                          <label className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            Outline
                            <input
                              type="color"
                              value={objectOutlineColor}
                              onChange={(event) => setObjectOutlineColor(event.target.value)}
                              className="h-9 w-10 rounded-lg border border-slate-200 bg-white"
                            />
                          </label>
                          <button
                            type="button"
                            onClick={handlePromptAddObject}
                            disabled={!objectPrompt.trim()}
                            className="flex-1 rounded-2xl border border-slate-900 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            Add Object
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Shape tools</p>
                      <div className="mt-3 grid grid-cols-3 gap-2">
                        <button
                          type="button"
                          onClick={() => handleAddObject("building", { label: "Rectangle Shape", geometryType: "rect" })}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Rectangle
                        </button>
                        <button
                          type="button"
                          onClick={() => handleAddObject("open_space", { label: "Polygon Shape", geometryType: "polygon" })}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Polygon
                        </button>
                        <button
                          type="button"
                          onClick={() => handleAddObject("road", { label: "Line Shape", geometryType: "polyline" })}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                        >
                          Line
                        </button>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Object Library
                      </p>
                      <div className="mt-3 space-y-4">
                        {ADD_MENU_SECTIONS.map((section) => (
                          <div key={section.key}>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                              {section.title}
                            </p>
                            <div className="mt-2 grid grid-cols-2 gap-2">
                              {section.items.map((type) => {
                                const catalog = SITE_OBJECT_CATALOG[type];
                                return (
                                  <button
                                    key={type}
                                    type="button"
                                    onClick={() => handleAddObject(type)}
                                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600 transition hover:border-slate-900 hover:text-slate-950"
                                  >
                                    {catalog.label}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Project Setup
                      </p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                          <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Site width</p>
                          <p className="mt-1 font-semibold text-slate-800">
                            {lotBounds.w ? `${lotBounds.w.toFixed(0)} ft` : "Not set"}
                          </p>
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                          <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Site length</p>
                          <p className="mt-1 font-semibold text-slate-800">
                            {lotBounds.h ? `${lotBounds.h.toFixed(0)} ft` : "Not set"}
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setActiveSidePanel("data")}
                        className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                      >
                        Edit Site Setup
                      </button>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Canvas Objects
                        </p>
                        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                          {buildingPlacements.length}
                        </span>
                      </div>
                      <div className="mt-3 max-h-96 space-y-2 overflow-y-auto pr-1">
                        {buildingPlacements.length ? (
                          buildingPlacements.map((item) => (
                            <div
                              key={item.id}
                              draggable={!item.locked}
                              onDragStart={(event) => {
                                if (item.locked) return;
                                event.dataTransfer?.setData("civora-object-id", item.id);
                                setPlacementModeEnabled(true);
                              }}
                              className={`rounded-2xl border bg-white p-3 text-xs text-slate-600 ${
                                activePlacementId === item.id
                                  ? "border-slate-900 ring-2 ring-slate-200"
                                  : "border-slate-200"
                              }`}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <p className="font-semibold text-slate-900">{item.label}</p>
                                  <p className="mt-1 uppercase tracking-[0.12em] text-slate-400">
                                    {SITE_OBJECT_CATALOG[item.type ?? "building"]?.label ?? "Object"} ·{" "}
                                    {item.placed ? "Placed" : "Unplaced"}
                                  </p>
                                  {item.type === "custom" ? (
                                    <CustomGeometryHandoffDetails item={item} units={units} />
                                  ) : null}
                                </div>
                                {item.type !== "site" ? (
                                  <button
                                    type="button"
                                    onClick={() => handleRemoveBuilding(item.id)}
                                    className="text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-500"
                                  >
                                    Delete
                                  </button>
                                ) : null}
                              </div>
                              {item.type !== "site" ? (
                                <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
                                  <label className="flex flex-col gap-1">
                                    Length
                                    <input
                                      type="number"
                                      value={item.w}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          w: parsePositiveNumber(event.target.value) ?? item.w,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  <label className="flex flex-col gap-1">
                                    Width
                                    <input
                                      type="number"
                                      value={item.d}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          d: parsePositiveNumber(event.target.value) ?? item.d,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  {SITE_OBJECT_CATALOG[item.type ?? "building"]?.defaultH !== undefined ? (
                                    <label className="col-span-2 flex flex-col gap-1">
                                      Height
                                      <input
                                        type="number"
                                        value={item.h ?? ""}
                                        onChange={(event) =>
                                          handleUpdateBuilding(item.id, {
                                            h: parsePositiveNumber(event.target.value) ?? item.h,
                                          })
                                        }
                                        className="rounded-md border border-slate-200 px-2 py-1"
                                      />
                                    </label>
                                  ) : null}
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePlacementId(item.id);
                                      setPlacementModeEnabled(true);
                                    }}
                                    className="col-span-2 rounded-xl border border-slate-900 bg-slate-950 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white"
                                  >
                                    {item.placed ? "Move on Canvas" : "Place on Canvas"}
                                  </button>
                                </div>
                              ) : null}
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-slate-500">No objects yet.</p>
                        )}
                      </div>
                    </div>
                  </div>
                ) : null}

                {sidePanelForRender === "reports" || sidePanelForRender === "quantities" || sidePanelForRender === "deliverables" ? (
                  <div className="space-y-3">
                    {sidePanelForRender === "reports" ? (
                      <>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            ["QA items", issues.length + analysisIssues.length],
                            ["Missing", sidebarMissingInputs.length],
                            ["Assumptions", sidebarAssumptions.length],
                            ["Blocked", systemHealthItems.filter((item) => item.state === "blocked").length],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-3">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                              <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
                            </div>
                          ))}
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Engineering health</p>
                          <div className="mt-3 grid grid-cols-2 gap-2">
                            {([
                              ["system_grading", "Grading"],
                              ["system_storm", "Storm"],
                              ["system_sanitary", "Sanitary"],
                              ["system_water", "Water"],
                              ["system_roadway", "Roadway"],
                              ["system_utilities", "Utilities"],
                              ["system_landscape", "Landscape"],
                              ["analysis", "Review & QA"],
                            ] as Array<[SidePanelKey, string]>).map(([panel, label]) => (
                              <button
                                key={panel}
                                type="button"
                                onClick={() => handleOpenSidePanel(panel)}
                                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-white"
                              >
                                {label}
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Truth gates</p>
                          <div className="mt-3 space-y-2">
                            {sidebarTruthItems.map((item) => (
                              <div key={item.label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                                <span className="font-semibold text-slate-700">{item.label}</span>
                                <span className={`text-xs font-semibold uppercase tracking-[0.12em] ${
                                  item.status === "block" ? "text-red-600" : item.status === "review" ? "text-amber-600" : "text-slate-500"
                                }`}>
                                  {item.value}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Review gates</p>
                          <div className="mt-3 space-y-2">
                            {reviewGateItems.map((item) => (
                              <div key={item.label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                                <span className="font-semibold text-slate-700">{item.label}</span>
                                <span className={`text-right text-xs font-semibold uppercase tracking-[0.12em] ${
                                  item.status === "block" ? "text-red-600" : "text-amber-600"
                                }`}>
                                  {item.value}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Backend capability audit</p>
                          <div className="mt-3 space-y-2">
                            {capabilityAuditRows.map((item) => (
                              <div key={item.key} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <p className="text-sm font-semibold text-slate-800">{item.label}</p>
                                    <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                      Exposed {item.exposed} in {item.surfaces.join(" / ")}
                                    </p>
                                  </div>
                                  <span className={`max-w-[150px] text-right text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                    item.status === "block"
                                      ? "text-red-600"
                                      : item.status === "idle"
                                        ? "text-slate-400"
                                        : item.status === "ok"
                                          ? "text-slate-600"
                                          : "text-amber-600"
                                  }`}>
                                    {item.value}
                                  </span>
                                </div>
                                <p className="mt-2 text-xs text-slate-500">Missing wiring: {item.missingWiring}</p>
                                <p className="mt-1 text-xs font-medium text-slate-600">Exact fix: {item.exactFix}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    ) : null}
                    {sidePanelForRender === "quantities" ? (
                      <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Quantity takeoff</p>
                            <p className="mt-1 text-xs text-slate-500">Canonical state with stale and confidence labels.</p>
                          </div>
                          <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                            sidebarStaleSystems.length ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-600"
                          }`}>
                            {sidebarStaleSystems.length ? "Stale" : sidebarTrustScore}
                          </span>
                        </div>
                        <div className="mt-3 space-y-2 text-sm text-slate-700">
                          {quantityRows.slice(0, 8).map((row) => (
                            <div key={row.label} className="flex items-center justify-between gap-3">
                              <span>{row.label}</span>
                              <span className="font-semibold text-slate-950">{formatMetric(Number(row.value), row.unit)}</span>
                            </div>
                          ))}
                          {!quantityRows.length ? <p className="text-slate-500">Run systems to populate quantities.</p> : null}
                        </div>
                      </div>
                    ) : null}
                    {sidePanelForRender === "deliverables" ? (
                      <>
                        <div className="rounded-2xl border border-slate-200 bg-white p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Package gate</p>
                              <p className="mt-1 text-sm font-semibold text-slate-900">
                                {sidebarReleaseStatus === "ready" ? "Ready for engineer review" : sidebarReleaseStatus === "blocked" ? "Construction package blocked" : "Review-only package"}
                              </p>
                              <p className="mt-1 text-xs font-medium text-slate-500">
                                Construction remains blocked unless an external licensed engineer approval record exists.
                              </p>
                            </div>
                            <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                              sidebarReleaseStatus === "blocked" ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-700"
                            }`}>
                              {sidebarReleaseStatus === "ready" ? "Review" : sidebarReleaseStatus === "blocked" ? "Blocked" : "Review"}
                            </span>
                          </div>
                          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                            {[
                              ["Plan sheets", backendResult ? "Available" : "Needs run"],
                              ["Profiles", roads || utilities ? "Review" : "Not generated"],
                              ["Sections", placedObjectCount ? "Available" : "Needs objects"],
                              ["Export audit", sidebarTrustScore],
                            ].map(([label, value]) => (
                              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                                <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                                <p className="mt-1 font-semibold text-slate-800">{value}</p>
                              </div>
                            ))}
                          </div>
                          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Format support status</p>
                            <div className="mt-2 space-y-2">
                              {deliverableSupportRows.map(([label, item]) => (
                                <div key={label} className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
                                  <span className="font-semibold text-slate-700">{label}</span>
                                  <span className={`max-w-[180px] text-right text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                    item.status === "block" ? "text-red-600" : "text-amber-600"
                                  }`}>
                                    {item.value}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Package support status</p>
                            <div className="mt-2 space-y-2">
                              {capabilityAuditRows
                                .filter((item) =>
                                  [
                                    "production_evidence",
                                    "cost_book_pricing",
                                    "export_package_report",
                                    "construction_document_support_package",
                                    "engineer_review_package",
                                    "reactive_rerun_evidence",
                                    "cad_geometry_handoff",
                                  ].includes(item.key),
                                )
                                .map((item) => (
                                  <div key={item.key} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
                                    <div className="flex items-start justify-between gap-3">
                                      <span className="font-semibold text-slate-700">{item.label}</span>
                                      <span className={`max-w-[170px] text-right text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                        item.status === "block" ? "text-red-600" : item.status === "idle" ? "text-slate-400" : "text-amber-600"
                                      }`}>
                                        {item.value}
                                      </span>
                                    </div>
                                    {item.status === "block" || item.status === "idle" ? (
                                      <p className="mt-1 text-xs text-slate-500">{item.exactFix}</p>
                                    ) : null}
                                  </div>
                                ))}
                            </div>
                          </div>
                          <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
                            Civora never stamps, seals, signs, certifies, approves construction, submits construction documents, or acts as engineer of record.
                          </p>
                        </div>
                        <div className="rounded-2xl border border-slate-200 bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Review gates</p>
                          <div className="mt-3 space-y-2">
                            {reviewGateItems.map((item) => (
                              <div key={item.label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                                <span className="font-semibold text-slate-700">{item.label}</span>
                                <span className={`text-right text-xs font-semibold uppercase tracking-[0.12em] ${
                                  item.status === "block" ? "text-red-600" : "text-amber-600"
                                }`}>
                                  {item.value}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <button type="button" onClick={handleExportDxf} disabled={Boolean(getExportBlockReason())} title={getExportBlockReason() || "Download DXF review export"} className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400">Export DXF</button>
                          <button type="button" onClick={handleExportReport} disabled={Boolean(getExportBlockReason())} title={getExportBlockReason() || "Download engineer-review report"} className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400">Export Report</button>
                        </div>
                      </>
                    ) : null}
                    {sortedProjects.length ? (
                      sortedProjects.map((projectSummary) => (
                        <div
                          key={projectSummary.project_id}
                          className="rounded-2xl border border-slate-200 bg-white p-4"
                        >
                          <p className="text-sm font-semibold text-slate-900">
                            {projectSummary.name || "Untitled Project"}
                          </p>
                          <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500">
                            {projectSummary.description ||
                              (projectSummary.updated_at
                                ? `Updated ${new Date(projectSummary.updated_at * 1000).toLocaleDateString()}`
                                : "No description")}
                          </p>
                          <button
                            type="button"
                            onClick={async () => {
                              await loadProject(projectSummary.project_id);
                              await handlePreviewPlan();
                              setPreviewFullscreenOpen(true);
                              setActiveSidePanel(null);
                            }}
                            className="mt-3 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
                          >
                            View Docs
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No docs available yet.</p>
                    )}
                  </div>
                ) : null}

                {activeSidePanel === "chat" ? (
                  <ChatPanel
                    chatMessages={chatMessages}
                    chatScrollRef={chatScrollRef}
                    onSetMessageFeedback={setMessageFeedback}
                    thinkingState={thinkingState}
                    busy={busy}
                    activePlanTool={activePlanTool}
                    visibleActiveJobStatus={visibleActiveJob?.status ?? ""}
                    hasDirectRunInFlight={Boolean(directRunAbortRef.current)}
                    onCancelJob={handleCancelActiveJob}
                    onContinueJob={handleContinueActiveJob}
                    pendingClarification={pendingClarification?.question || null}
                    onContinuePendingClarification={handleContinuePendingClarification}
                    prompt={prompt}
                    imageName={imageName}
                    onPromptChange={setPrompt}
                    onPromptKeyDown={handlePromptKeyDown}
                    onSendMessage={handleSendMessage}
                    onUploadImage={uploadImage}
                    onExplainPlan={() => void handleExplainPlan()}
                    onRunFix={() => void handleRunFix()}
                    onRunImprove={() => void handleRunImprove()}
                    onSaveProject={() => void saveProject()}
                    canExplain={Boolean(planPreviewUrl)}
                    statusMessage={statusMessage}
                    hasVisibleActiveJob={Boolean(visibleActiveJob)}
                    approvalState={approvalStatus.state}
                    approvalPhaseLabel={approvalStatus.label}
                    approvalError={approvalError}
                    collapsed={false}
                    onToggleCollapsed={handleCloseSidePanel}
                    summaryText={chatSummary}
                  />
                ) : null}
              </div>
            </aside>
          ) : null}
          <main className="order-2 flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto">
            <div className="flex w-full flex-1 flex-col gap-4 px-4 py-4 md:px-5">
              <div className="flex w-full flex-col">
                <div
                  data-testid="workspace-canvas-shell"
                  className="civora-canvas mx-auto w-full overflow-hidden p-1"
                  style={{
                    width: "100%",
                    height: `${previewHeightPx}px`,
                  }}
                >
                  <div className="h-full w-full">
                    <PreviewPanel
                previewReview={previewReview}
                previewTotalPhaseCount={previewTotalPhaseCount}
                previewCompletedPhaseCount={previewCompletedPhaseCount}
                previewRunningPhase={previewRunningPhase}
                previewNextPendingPhase={previewNextPendingPhase}
                onRefreshPreview={handlePreviewPlan}
                busy={busy}
                planPreviewUrl={planPreviewUrl}
                planPreviewProjectId={planPreviewProjectId}
                currentProjectId={projectId || currentProject?.project_id || null}
                previewMode={previewMode}
                previewInteraction={previewInteraction}
                previewQuality={previewQuality}
                previewLabelDensity={previewLabelDensity}
                systemStatuses={systemStatuses}
                hasTerrainSource={hasTerrainSource}
                hasBasinPlaced={hasBasinPlaced}
                siteTooLargeForGrading={siteTooLargeForGrading}
                hasHardSystemBlock={hasHardSystemBlock}
                hasGeneratedPlan={Boolean(planPreviewUrl && backendResult)}
                placementMode={placementModeEnabled || Boolean(activePlacementId)}
                onViewportCenter={handleViewportCenter}
                externalRectUndo={externalRectUndo}
              onPlaceBuilding={handlePlaceBuilding}
              onPlaceObject={handlePlaceObject}
              onCreateCustomGeometry={handleCreateCustomGeometry}
              onCreateSiteBoundary={handleCreateSiteBoundary}
              onUnlockSite={handleUnlockSite}
              buildingPlacements={buildingPlacements}
              suggestedPlacements={filteredDetectedPlacements}
              selectedBuildingId={activePlacementId}
              focusDetectedId={focusDetectedId}
              onClearFocusDetected={() => setFocusDetectedId(null)}
              focusObjectId={focusObjectId}
              onClearFocusObject={() => setFocusObjectId(null)}
              lotWidth={lotBounds.w}
              lotHeight={lotBounds.h}
              onViewportFootprint={handleViewportFootprint}
              onUpdateBuilding={handleUpdateBuilding}
              onUpdateSuggested={(id, updates) => {
                setDetectedPlacements((prev) => {
                  const nextDetected = prev.map((item) =>
                    item.id === id ? { ...item, ...updates } : item,
                  );
                  persistDetectedPlacements(nextDetected);
                  return nextDetected;
                });
              }}
              analysisPaths={analysisPaths}
              analysisHighlight={
                selectedAccessIssue
                  ? {
                      buildingId: selectedAccessIssue.buildingId,
                      accessId: selectedAccessIssue.accessId,
                      pathId: selectedAccessIssue.pathId,
                    }
                  : null
              }
              analysisFocusLocked={analysisFocusLocked}
              onClearHighlights={() => {
                setAnalysisSelectedIssueId(null);
                setAnalysisFocusLocked(false);
              }}
              onResetView={() => {
                setAnalysisSelectedIssueId(null);
                setFocusDetectedId(null);
                setAnalysisFocusLocked(false);
              }}
              onRemoveBuilding={handleRemoveBuilding}
              onRestoreBuilding={handleRestoreBuilding}
              onSelectBuilding={setActivePlacementId}
                onSetPreviewMode={setPreviewMode}
                onSetPreviewInteraction={setPreviewInteraction}
                onSetPreviewQuality={setPreviewQuality}
                onSetPreviewLabelDensity={(value) => {
                  setPreviewLabelDensityTouched(true);
                  setPreviewLabelDensity(value);
                }}
                onQueuePreviewRefresh={queuePreviewRefresh}
                previewRefreshing={previewRefreshing}
                previewRefreshNote={previewRefreshNote}
                preview3DEffectiveItems={preview3DEffectiveItems}
                usingAnnotation3D={usingAnnotation3D}
                hasGradingSurface={hasGradingSurface}
                onOpenFullscreen={() => setPreviewFullscreenOpen(true)}
                previewFullscreenOpen={previewFullscreenOpen}
                onCloseFullscreen={() => setPreviewFullscreenOpen(false)}
                onExportDxf={handleExportDxf}
                onExportReport={handleExportReport}
                exportBlockReason={getExportBlockReason()}
                planPreviewAnnotations={planPreviewAnnotations}
                selectedIssueLabel={selectedIssueLabel}
                showMeasurements={showMeasurements}
                showCalculations={showCalculations}
                measurementOverlayStats={measurementOverlayStats}
                calculationOverlayStats={calculationOverlayStats}
                geocode={siteInputs?.geocode ?? null}
                siteRotationDeg={siteInputs?.site_rotation_deg ?? 0}
                showSiteBounds={showSiteBounds}
                siteDrawRequest={siteDrawRequest}
                gradingBlocker={gradingBlocker}
                fitToSiteRequest={fitToSiteRequest}
                mapCenterRequest={mapCenterRequest}
                alignToRoadRequest={alignToRoadRequest}
                onMapCenter={handleMapCenter}
                siteLocked={siteScaleLocked}
                onSetSiteRotationDeg={(value) => {
                  setSiteRotationDeg(value);
                  setSiteRotationInput(String(value));
                  scheduleRotationSave(value);
                }}
                surveyPoints={surveyPreviewPoints}
                onMapScaleUpdate={({ ftPerPx, source }) => {
                  if (siteScaleLocked) return;
                  if (!Number.isFinite(ftPerPx) || ftPerPx <= 0) return;
                  setDetectionScaleFtPerPx(ftPerPx);
                  setDetectionScaleSource(source);
                  scheduleScaleSave(ftPerPx, source);
                }}
                debugStats={{
                  enabled: debugPreview,
                  projectId: projectId || currentProject?.project_id || "",
                  canonicalCount: buildingPlacements.length,
                  placedCount: placedObjectCount,
                  previewImageActive: Boolean(planPreviewUrl),
                  placementMode: placementModeEnabled || Boolean(activePlacementId),
                  selectedId: activePlacementId,
                }}
              />
                  </div>
                </div>
              </div>
              <div
                data-testid="bottom-review-panel"
                className="mx-auto w-full max-w-[1600px] rounded-xl border border-slate-200 bg-white/95 shadow-sm"
              >
                <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Review Status
                    </p>
                    <p className="truncate text-xs font-semibold text-slate-500">
                      {sidebarHasTruthEvidence
                        ? "Engineer review required. Construction remains blocked until external approval."
                        : "No project evidence yet. Start setup to create traceable state."}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setBottomPanelCollapsed((value) => !value)}
                    className="shrink-0 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
                  >
                    {bottomPanelCollapsed ? "Open" : "Collapse"}
                  </button>
                </div>
                {bottomPanelContentRendered ? (
                  <div
                    className="civora-motion-bottom-panel grid gap-3 px-3 py-3 lg:grid-cols-[auto,1fr]"
                    data-motion-state={bottomPanelContentVisible ? "open" : "closed"}
                    aria-hidden={bottomPanelCollapsed}
                  >
                    <div className="grid min-w-0 grid-cols-2 gap-1 sm:flex sm:overflow-x-auto lg:flex-col lg:overflow-visible">
                      {bottomPanelTabs.map((tab) => (
                        <button
                          key={tab.key}
                          type="button"
                          onClick={() => {
                            setActiveBottomPanelTab(tab.key);
                            handleOpenSidePanel(tab.panel);
                          }}
                          className={`min-w-0 whitespace-normal rounded-lg border px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.12em] transition sm:whitespace-nowrap ${
                            activeBottomPanelTab === tab.key
                              ? "border-slate-950 bg-slate-950 text-white"
                              : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>
                    <div className="min-w-0">
                      {activeBottomPanelTab === "model_review" ? (
                        <div className="grid gap-2 md:grid-cols-3">
                          <button
                            type="button"
                            onClick={() => handleOpenSidePanel("reports")}
                            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left"
                          >
                            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Top blocker</p>
                            <p className="mt-1 line-clamp-2 text-xs font-semibold text-slate-800">
                              {bottomBlockerItems[0] || (sidebarHasTruthEvidence ? "No blocker text recorded. Engineer review still required." : "No evidence yet. Start setup.")}
                            </p>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenSidePanel("generate")}
                            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left"
                          >
                            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">System status</p>
                            <p className="mt-1 line-clamp-2 text-xs font-semibold text-slate-800">
                              {Object.entries(systemStatuses).map(([key, value]) => `${key}: ${value.replace("_", " ")}`).join(" / ")}
                            </p>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenSidePanel(siteScaleLocked ? "objects" : "site_existing")}
                            className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-left"
                          >
                            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">Next step</p>
                            <p className="mt-1 line-clamp-2 text-xs font-semibold text-amber-900">{nextSetupAction}</p>
                          </button>
                        </div>
                      ) : null}
                      {activeBottomPanelTab === "systems" ? (
                        <div className="flex flex-wrap gap-2">
                          {(Object.entries(systemStatuses) as Array<[EngineeringSystemKey, SystemStatus]>).map(([system, state]) => (
                            <button
                              key={system}
                              type="button"
                              onClick={() => handleOpenSidePanel(system === "drainage" ? "system_storm" : system === "roads" ? "system_roadway" : system === "parking" ? "generate" : (`system_${system}` as SidePanelKey))}
                              className={`rounded-lg border px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] ${
                                state === "stale"
                                  ? "border-amber-200 bg-amber-50 text-amber-700"
                                  : state === "fresh"
                                    ? "border-slate-200 bg-slate-50 text-slate-700"
                                    : "border-slate-200 bg-white text-slate-500"
                              }`}
                            >
                              {system} / {state.replace("_", " ")}
                            </button>
                          ))}
                        </div>
                      ) : null}
                      {activeBottomPanelTab === "objects" ? (
                        <div className="grid gap-2 md:grid-cols-3">
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Placed objects</p>
                            <p className="mt-1 text-lg font-semibold text-slate-900">{placedObjectCount}</p>
                          </div>
                          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Selected</p>
                            <p className="mt-1 truncate text-xs font-semibold text-slate-800">{selectedCanvasObject?.label || "None"}</p>
                          </div>
                          <button type="button" onClick={() => handleOpenSidePanel("objects")} className="rounded-lg border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-white">
                            Add / draw objects
                          </button>
                        </div>
                      ) : null}
                      {activeBottomPanelTab === "properties" ? (
                        <div className="grid gap-2 md:grid-cols-3">
                          {[
                            ["Object type", selectedCanvasObject?.type || "No selection"],
                            ["Source", selectedCanvasObject?.source || "Not selected"],
                            ["Confidence", String(selectedCanvasObject?.meta?.confidence || "engineer_review_required")],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                              <p className="mt-1 truncate text-xs font-semibold text-slate-800">{value}</p>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {activeBottomPanelTab === "history" ? (
                        <div className="grid gap-2 md:grid-cols-3">
                          {[
                            ["Project sync", currentProject?.project_id ? "Saved" : "Draft"],
                            ["Last action", statusMessage || "No recent action"],
                            ["Package state", sidebarReleaseStatus === "ready" ? "ready_for_engineer_review" : sidebarReleaseStatus],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
                              <p className="mt-1 line-clamp-2 text-xs font-semibold text-slate-800">{value}</p>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="hidden">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Create Objects
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      Describe what you want to add.
                    </p>
                    <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <label className="flex items-center justify-between gap-3 text-sm font-semibold text-slate-800">
                        <span>Assisted</span>
                        <input
                          type="checkbox"
                          checked={assistedEnabled}
                          onChange={(event) => setAssistedEnabled(event.target.checked)}
                          className="h-4 w-4 accent-slate-950"
                        />
                      </label>
                      <p className="mt-1 text-xs text-slate-500">
                        When on, Civora can infer missing details using clearly labeled assumptions.
                      </p>
                    </div>
                    <div className="mt-3 flex flex-col gap-2">
                      <input
                        value={objectPrompt}
                        onChange={(event) => setObjectPrompt(event.target.value)}
                        placeholder="Describe what you want to add..."
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-slate-400 focus:outline-none"
                      />
                      <div className="flex flex-wrap items-center gap-3">
                        <label className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Outline
                          <input
                            type="color"
                            value={objectOutlineColor}
                            onChange={(event) => setObjectOutlineColor(event.target.value)}
                            className="h-9 w-10 rounded-lg border border-slate-200 bg-white"
                          />
                        </label>
                        <button
                          type="button"
                          onClick={handlePromptAddObject}
                          disabled={!objectPrompt.trim()}
                          className="flex-1 rounded-2xl border border-slate-900 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Add Object
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1">red brick building</span>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1">parking lot behind building</span>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1">two-lane road</span>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1">detention basin</span>
                    </div>
                    <div className="mt-4 grid gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-600 sm:grid-cols-2 lg:grid-cols-4">
                      <div>
                        <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Site width</p>
                        <p data-testid="site-width" className="mt-1 font-semibold text-slate-800">
                          {lotBounds.w ? `${lotBounds.w.toFixed(0)} ft` : "Not set"}
                        </p>
                      </div>
                      <div>
                        <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Site length</p>
                        <p data-testid="site-length" className="mt-1 font-semibold text-slate-800">
                          {lotBounds.h ? `${lotBounds.h.toFixed(0)} ft` : "Not set"}
                        </p>
                      </div>
                      <div>
                        <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Status</p>
                        <p data-testid="site-status" className="mt-1 font-semibold text-slate-800">
                          {siteScaleLocked ? "Site Locked" : "Selecting Site"}
                        </p>
                      </div>
                      <div>
                        <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">Detect grading</p>
                        <p data-testid="grading-readiness" className="mt-1 font-semibold text-slate-800">
                          {missingSite ? "Needs Site" : siteTooLargeForGrading ? "Too Large" : "Ready"}
                        </p>
                      </div>
                      {siteTooLargeForWarning ? (
                        <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 font-semibold text-amber-700 sm:col-span-2 lg:col-span-4">
                          {OVERSIZED_SITE_MESSAGE}
                        </p>
                      ) : null}
                    </div>
                    {gradingResultSummary.hasResult ? (
                      <div
                        data-testid="grading-result"
                        className="mt-3 grid gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs text-emerald-900 sm:grid-cols-2 lg:grid-cols-3"
                      >
                        <p className="font-semibold uppercase tracking-[0.14em] text-emerald-600 sm:col-span-2 lg:col-span-3">
                          Grading Result
                        </p>
                        <p data-testid="grading-source-quality">
                          source_quality = {gradingResultSummary.sourceQuality || "pending"}
                        </p>
                        <p data-testid="grading-source-detail">
                          source_detail = {gradingResultSummary.sourceDetail || "pending"}
                        </p>
                        <p data-testid="grading-sample-count">
                          sample_count = {gradingResultSummary.sampleCount}
                        </p>
                        <p data-testid="grading-missing-count">
                          missing_count = {gradingResultSummary.missingCount}
                        </p>
                        <p data-testid="grading-elevation-range">
                          elevation range = {gradingResultSummary.elevationRange.toFixed(2)} ft
                        </p>
                        <p data-testid="grading-high-points">
                          high_points = {gradingResultSummary.highPointCount}
                        </p>
                        <p data-testid="grading-low-points">
                          low_points = {gradingResultSummary.lowPointCount}
                        </p>
                        <p data-testid="grading-slope-summary">
                          slope summary = {gradingResultSummary.slopeSummary}
                        </p>
                      </div>
                    ) : null}
                  </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr,2fr]">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Site</p>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-600">
                      <label className="flex flex-col gap-1">
                        Length (ft)
                        <input
                          type="number"
                          value={lotWidth}
                          disabled={siteScaleLocked}
                          onChange={(event) => {
                            const nextValue = event.target.value;
                            setLotWidth(nextValue);
                            setBuildingPlacements((prev) =>
                              prev.map((item) =>
                                item.type === "site"
                                  ? {
                                      ...item,
                                      w:
                                        parsePositiveNumber(nextValue) ??
                                        item.w,
                                    }
                                  : item,
                              ),
                            );
                          }}
                          className="rounded-lg border border-slate-200 px-2 py-1 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                        />
                      </label>
                      <label className="flex flex-col gap-1">
                        Width (ft)
                        <input
                          type="number"
                          value={lotHeight}
                          disabled={siteScaleLocked}
                          onChange={(event) => {
                            const nextValue = event.target.value;
                            setLotHeight(nextValue);
                            setBuildingPlacements((prev) =>
                              prev.map((item) =>
                                item.type === "site"
                                  ? {
                                      ...item,
                                      d:
                                        parsePositiveNumber(nextValue) ??
                                        item.d,
                                    }
                                  : item,
                              ),
                            );
                          }}
                          className="rounded-lg border border-slate-200 px-2 py-1 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                        />
                      </label>
                    </div>
                    <div className="mt-3 text-xs text-slate-500">
                      Area:{" "}
                      {(() => {
                        const w = parsePositiveNumber(lotWidth) ?? 0;
                        const h = parsePositiveNumber(lotHeight) ?? 0;
                        const acres = w && h ? (w * h) / 43560 : 0;
                        return acres ? `${acres.toFixed(2)} acres` : "Set dimensions to compute acreage";
                      })()}
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      {siteScaleLocked
                        ? "Locked canonical site boundary. Unlock to change dimensions or redraw."
                        : "Set dimensions here or draw the site boundary from Setup."}
                    </p>
                    <button
                      type="button"
                      onClick={siteScaleLocked ? handleUnlockSite : () => void handleApplySite()}
                      className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
                    >
                      {siteScaleLocked ? "Change Site / Unlock" : "Lock Site From Dimensions"}
                    </button>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Objects</p>
                    {detectedPlacements.length ? (
                      <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50/70 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700">
                          Detected Objects (Review Required)
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(["high", "medium", "all"] as const).map((level) => (
                            <button
                              key={level}
                              type="button"
                              onClick={() => setDetectionConfidenceFilter(level)}
                              className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                                detectionConfidenceFilter === level
                                  ? "border-amber-400 bg-amber-100 text-amber-800"
                                  : "border-amber-200 bg-white text-amber-700"
                              }`}
                            >
                              {level === "high" ? "High only" : level === "medium" ? "Medium+" : "All"}
                            </button>
                          ))}
                        </div>
                        <div className="mt-3 space-y-2">
                          {filteredDetectedPlacements.map((item) => (
                            <div
                              key={item.id}
                              className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs text-slate-700"
                            >
                              <div>
                                <p className="font-semibold text-slate-800">{item.label}</p>
                                <p className="text-[11px] text-slate-500">
                                  {item.w.toFixed(1)} ft × {item.d.toFixed(1)} ft ·{" "}
                                  {item.confidence ? `${Math.round(item.confidence * 100)}%` : "Approx."} ·{" "}
                                  {detectionScaleFtPerPx ? "Calibrated" : "Approx scale"}
                                </p>
                              </div>
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  onClick={() => setFocusDetectedId(item.id)}
                                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600"
                                >
                                  Zoom
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleAcceptDetected(item.id)}
                                  className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-700"
                                >
                                  Accept
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleRejectDetected(item.id)}
                                  className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-700"
                                >
                                  Reject
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                        <p className="mt-2 text-[11px] text-amber-700/80">
                          Detected features are approximate and must be confirmed.
                        </p>
                      </div>
                    ) : null}
                    {analysisIssues.length ? (
                      <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50/70 p-3">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-rose-700">
                            Access Analysis (Conceptual)
                          </p>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={exportAnalysisReport}
                              className="rounded-full border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600"
                            >
                              Export analysis
                            </button>
                            {analysisSelectedIssueId ? (
                              <button
                                type="button"
                                onClick={exportSelectedAnalysis}
                                className="rounded-full border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600"
                              >
                                Export selected
                              </button>
                            ) : null}
                            <button
                              type="button"
                              onClick={copyAnalysisJson}
                              className="rounded-full border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600"
                            >
                              Copy JSON
                            </button>
                            <div
                              className="rounded-full border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600"
                              title="Access analysis checks distance from confirmed buildings to nearest confirmed access. Threshold 150 ft."
                            >
                              Explain
                            </div>
                          </div>
                        </div>
                        <p className="mt-2 text-[11px] text-rose-700/80">
                          Uses confirmed buildings + access objects. Calculates nearest access distance and compares to 150 ft threshold.
                        </p>
                        {selectedAccessIssue ? (
                          <p className="mt-2 text-[11px] text-rose-700">
                            Selected: {Math.round(selectedAccessIssue.distanceFt)} ft (threshold {selectedAccessIssue.thresholdFt} ft)
                          </p>
                        ) : null}
                        <ul className="mt-3 space-y-1 text-[11px] text-rose-700">
                          {analysisIssues.map((issue) => (
                            <li key={issue.id}>
                              <button
                                type="button"
                                onClick={() => {
                                  setAnalysisSelectedIssueId(issue.id);
                                  setAnalysisFocusLocked(true);
                                }}
                                className={`w-full text-left ${analysisSelectedIssueId === issue.id ? "font-semibold underline" : ""}`}
                              >
                                {issue.message}
                              </button>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : analysisEmptyReason ? (
                      <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                        <p className="font-semibold text-slate-700">Access analysis needs objects</p>
                        <p className="mt-1">{analysisEmptyReason}</p>
                      </div>
                    ) : null}
                    {issues.length ? (
                      <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-3">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700">
                            Engineering Issues
                          </p>
                          <span className="text-[10px] uppercase tracking-[0.12em] text-slate-400">
                            Apply fixes
                          </span>
                        </div>
                        <div className="mt-3 space-y-2 text-xs text-slate-700">
                          {issues.map((issue, idx) => {
                            const applyLabel = drainageIssueApplyLabel(issue);
                            const canApply = applyLabel ? canApplyDrainageIssue(issue) : false;
                            const guidance = getIssueGuidance(issue);
                            return (
                              <div
                                key={`${issue.message}-${idx}`}
                                className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2"
                              >
                                <div>
                                  <p className="font-semibold text-slate-800">{issue.message}</p>
                                  {issue.code ? (
                                    <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-400">
                                      {issue.code}
                                    </p>
                                  ) : null}
                                  {guidance.explanation ? (
                                    <p className="mt-2 text-[11px] text-slate-600">
                                      {guidance.explanation}
                                    </p>
                                  ) : null}
                                  {guidance.bestNextFix ? (
                                    <p className="mt-2 text-[11px] font-semibold text-slate-700">
                                      Best next fix: {guidance.bestNextFix}
                                    </p>
                                  ) : null}
                                  {guidance.suggested && guidance.suggested.length ? (
                                    <div className="mt-2 space-y-1 text-[11px] text-slate-600">
                                      {guidance.suggested.map((item) => (
                                        <p key={item}>• {item}</p>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                                {applyLabel ? (
                                  <button
                                    type="button"
                                    onClick={() => handleApplyDrainageIssue(issue)}
                                    disabled={!canApply}
                                    className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                                      canApply
                                        ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                                        : "border-slate-200 bg-white text-slate-400 cursor-not-allowed"
                                    }`}
                                  >
                                    {applyLabel}
                                  </button>
                                ) : (
                                  <span className="text-[10px] uppercase tracking-[0.12em] text-slate-400">
                                    Review
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                    <div className="mt-2 max-h-72 space-y-3 overflow-y-auto pr-1">
                      <div className="flex w-full gap-3 overflow-x-auto pb-2">
                        {buildingPlacements
                          .filter((item) => !item.placed)
                          .map((item) => (
                            <div
                              key={item.id}
                              draggable={!item.locked}
                              onDragStart={(event) => {
                                if (item.locked) return;
                                event.dataTransfer?.setData("civora-object-id", item.id);
                                setPlacementModeEnabled(true);
                              }}
                              className={`min-w-[220px] rounded-2xl border bg-white p-3 text-xs text-slate-600 shadow-sm ${
                                activePlacementId === item.id
                                  ? "border-amber-400 ring-2 ring-amber-200"
                                  : "border-slate-200"
                              }`}
                              title={`${item.label} • ${item.w} ft x ${item.d} ft`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-800">{item.label}</span>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveBuilding(item.id)}
                                  className="text-xs font-semibold text-rose-500"
                                >
                                  Delete
                                </button>
                              </div>
                              <div className="mt-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                                <span>{SITE_OBJECT_CATALOG[item.type ?? "building"]?.label ?? "Building"}</span>
                                <span>•</span>
                                <span>{item.w} ft x {item.d} ft</span>
                              </div>
                              {item.type === "custom" ? (
                                <CustomGeometryHandoffDetails item={item} units={units} />
                              ) : null}
                              {item.type !== "site" ? (
                                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                                  <label className="flex flex-col gap-1">
                                    Length
                                    <input
                                      type="number"
                                      value={item.w}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          w: parsePositiveNumber(event.target.value) ?? item.w,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  <label className="flex flex-col gap-1">
                                    Width
                                    <input
                                      type="number"
                                      value={item.d}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          d: parsePositiveNumber(event.target.value) ?? item.d,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  {SITE_OBJECT_CATALOG[item.type ?? "building"]?.defaultH !== undefined ? (
                                    <label className="col-span-2 flex flex-col gap-1">
                                      Height (ft)
                                      <input
                                        type="number"
                                        value={item.h ?? ""}
                                        onChange={(event) =>
                                          handleUpdateBuilding(item.id, {
                                            h:
                                              parsePositiveNumber(event.target.value) ??
                                              item.h,
                                          })
                                        }
                                        className="rounded-md border border-slate-200 px-2 py-1"
                                      />
                                    </label>
                                  ) : null}
                                  {item.type === "parking" ? (
                                    <>
                                      <label className="col-span-2 flex flex-col gap-1">
                                        Stalls
                                        <input
                                          type="number"
                                          value={item.stallCount ?? ""}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              stallCount:
                                                parsePositiveNumber(event.target.value) ?? 0,
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Stall W
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.stallWidth ??
                                              parkingStallWidth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  stallWidth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingStallWidth) ??
                                                    9,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Stall D
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.stallDepth ??
                                              parkingStallDepth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  stallDepth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingStallDepth) ??
                                                    18,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Aisle
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.aisleWidth ??
                                              parkingAisleWidth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  aisleWidth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingAisleWidth) ??
                                                    24,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        ADA Count
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.adaCount ??
                                              parkingAdaCount,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  adaCount:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingAdaCount) ??
                                                    0,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        ADA Aisle
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.adaAisleWidth ??
                                              parkingAdaAisleWidth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  adaAisleWidth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingAdaAisleWidth) ??
                                                    8,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Compact Count
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.compactCount ??
                                              parkingCompactCount,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  compactCount:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingCompactCount) ??
                                                    0,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Compact W
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.compactWidth ??
                                              parkingCompactWidth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  compactWidth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingCompactWidth) ??
                                                    8,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Angle
                                        <select
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.angleDeg ??
                                              parkingAngle,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  angleDeg: parsePositiveNumber(event.target.value) ?? 90,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        >
                                          <option value="90">90°</option>
                                          <option value="60">60°</option>
                                          <option value="45">45°</option>
                                        </select>
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Loading
                                        <select
                                          value={String(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.loading ??
                                              parkingLoading,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  loading: event.target.value === "single" ? "single" : "double",
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        >
                                          <option value="double">Double</option>
                                          <option value="single">Single</option>
                                        </select>
                                      </label>
                                      <label className="col-span-2 flex items-center justify-between gap-2 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-600">
                                        <span>Mixed angle zones</span>
                                        <input
                                          type="checkbox"
                                          checked={Boolean(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.useMixedAngles,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  useMixedAngles: event.target.checked,
                                                },
                                              },
                                            })
                                          }
                                        />
                                      </label>
                                      <label className="col-span-2 flex items-center justify-between gap-2 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-600">
                                        <span>Compact zone grouping</span>
                                        <input
                                          type="checkbox"
                                          checked={Boolean(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.compactZone ?? true,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  compactZone: event.target.checked,
                                                },
                                              },
                                            })
                                          }
                                        />
                                      </label>
                                      <label className="col-span-2 flex items-center justify-between gap-2 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-600">
                                        <span>Auto-resize to fit count</span>
                                        <input
                                          type="checkbox"
                                          checked={Boolean(
                                            (item.meta as { parkingParams?: ParkingParams })?.parkingParams?.autoResizeToFitCount,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: ParkingParams })?.parkingParams,
                                                  autoResizeToFitCount: event.target.checked,
                                                },
                                              },
                                            })
                                          }
                                        />
                                      </label>
                                      {!(item.meta as { parkingParams?: ParkingParams })?.parkingParams?.autoResizeToFitCount &&
                                      typeof item.stallCount === "number" &&
                                      typeof (item.meta as { parkingCapacity?: number })?.parkingCapacity === "number" &&
                                      item.stallCount >
                                        Number((item.meta as { parkingCapacity?: number })?.parkingCapacity) ? (
                                        <div className="col-span-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-700">
                                          Max fits{" "}
                                          {Number(
                                            (item.meta as { parkingCapacity?: number })?.parkingCapacity,
                                          )}{" "}
                                          stalls at current size.
                                        </div>
                                      ) : null}
                                    </>
                                  ) : null}
                                </div>
                              ) : null}
                              <div className="mt-2 flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleSelectPlacementTarget(item.id)}
                                  disabled={item.type === "site"}
                                  className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                    item.type === "site"
                                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  {item.type === "site" ? "Configured" : item.placed ? "Re-place" : "Place"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleToggleBuildingLock(item.id)}
                                  disabled={item.type === "site"}
                                  className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                    item.type === "site"
                                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                      : item.locked
                                        ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  {item.locked ? "Locked" : "Unlock"}
                                </button>
                              </div>
                            </div>
                          ))}
                      </div>
                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        {buildingPlacements
                          .filter((item) => item.placed)
                          .map((item) => (
                            <div
                              key={item.id}
                              className={`rounded-2xl border bg-slate-50 p-3 text-xs text-slate-600 shadow-sm ${
                                activePlacementId === item.id
                                  ? "border-amber-400 ring-2 ring-amber-200"
                                  : "border-slate-200"
                              }`}
                              title={`${item.label} • ${item.w} ft x ${item.d} ft`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-800">{item.label}</span>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveBuilding(item.id)}
                                  className="text-xs font-semibold text-rose-500"
                                >
                                  Delete
                                </button>
                              </div>
                              <div className="mt-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                                <span>{SITE_OBJECT_CATALOG[item.type ?? "building"]?.label ?? "Building"}</span>
                                <span>•</span>
                                <span>{item.w} ft x {item.d} ft</span>
                              </div>
                              {item.type === "custom" ? (
                                <CustomGeometryHandoffDetails item={item} units={units} />
                              ) : null}
                              {typeof item.x === "number" && typeof item.y === "number" ? (
                                <div className="mt-1 text-[11px] text-slate-500">
                                  X {item.x.toFixed(1)} ft • Y {item.y.toFixed(1)} ft
                                  {lotBounds.w > 0 && lotBounds.h > 0 ? (
                                    <span className="ml-2 text-[10px] uppercase tracking-[0.12em] text-slate-400">
                                      {((item.x / lotBounds.w) * 100).toFixed(1)}% · {((item.y / lotBounds.h) * 100).toFixed(1)}%
                                    </span>
                                  ) : null}
                                </div>
                              ) : null}
                              {item.type !== "site" ? (
                                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                                  <label className="flex flex-col gap-1">
                                    Length
                                    <input
                                      type="number"
                                      value={item.w}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          w: parsePositiveNumber(event.target.value) ?? item.w,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  <label className="flex flex-col gap-1">
                                    Width
                                    <input
                                      type="number"
                                      value={item.d}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          d: parsePositiveNumber(event.target.value) ?? item.d,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  {SITE_OBJECT_CATALOG[item.type ?? "building"]?.defaultH !== undefined ? (
                                    <label className="col-span-2 flex flex-col gap-1">
                                      Height (ft)
                                      <input
                                        type="number"
                                        value={item.h ?? ""}
                                        onChange={(event) =>
                                          handleUpdateBuilding(item.id, {
                                            h:
                                              parsePositiveNumber(event.target.value) ??
                                              item.h,
                                          })
                                        }
                                        className="rounded-md border border-slate-200 px-2 py-1"
                                      />
                                    </label>
                                  ) : null}
                                  {item.type === "parking" ? (
                                    <label className="col-span-2 flex flex-col gap-1">
                                      Stalls
                                      <input
                                        type="number"
                                        value={item.stallCount ?? ""}
                                        onChange={(event) =>
                                          handleUpdateBuilding(item.id, {
                                            stallCount:
                                              parsePositiveNumber(event.target.value) ?? 0,
                                          })
                                        }
                                        className="rounded-md border border-slate-200 px-2 py-1"
                                      />
                                    </label>
                                  ) : null}
                                </div>
                              ) : null}
                              <div className="mt-2 flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleSelectPlacementTarget(item.id)}
                                  disabled={item.type === "site"}
                                  className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                    item.type === "site"
                                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  {item.type === "site" ? "Configured" : "Re-place"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleToggleBuildingLock(item.id)}
                                  disabled={item.type === "site"}
                                  className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                    item.type === "site"
                                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                      : item.locked
                                        ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  {item.locked ? "Locked" : "Unlock"}
                                </button>
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-4 border-t border-slate-200 pt-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Generate Systems</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600">
                    {(
                      ["roads", "parking", "grading", "drainage", "utilities"] as const
                    ).map((system) => {
                      const status = systemStatuses[system];
                      const tone =
                        status === "fresh"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : status === "stale"
                            ? "border-amber-200 bg-amber-50 text-amber-700"
                            : "border-slate-200 bg-slate-50 text-slate-500";
                      return (
                        <span
                          key={system}
                          className={`rounded-full border px-3 py-1 ${tone}`}
                        >
                          {system} · {status.replace("_", " ")}
                        </span>
                      );
                    })}
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 md:grid-cols-3">
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("roads")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Roads</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("parking")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Parking</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("grading")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Grading</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : !hasTerrainSource ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs terrain</span>
                        ) : siteTooLargeForGrading ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Too large</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("drainage")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Drainage</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : !hasTerrainSource ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs terrain</span>
                        ) : !hasBasinPlaced ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs basin</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("utilities")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Utilities</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("full")}
                      className="rounded-xl border border-slate-900 bg-slate-950 px-2 py-2 text-white transition hover:bg-slate-800"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Full Site</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-200">Needs site</span>
                        ) : !hasTerrainSource ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-200">Needs terrain</span>
                        ) : !hasBasinPlaced ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-200">Needs basin</span>
                        ) : null}
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </main>
          <div
            data-testid="floating-command-bar"
            className="civora-motion-command-bar fixed bottom-4 left-1/2 z-30 flex w-[calc(100vw-2rem)] max-w-xl items-center justify-between gap-2 rounded-2xl border border-slate-200 bg-white/95 px-3 py-2 shadow-[0_24px_70px_-32px_rgba(15,23,42,0.55)] backdrop-blur-xl lg:hidden"
          >
            <button
              type="button"
              aria-label="Open chat from floating command bar"
              onClick={() => handleOpenSidePanel("chat")}
              className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 transition hover:bg-white"
            >
              Chat
            </button>
            <button
              type="button"
              onClick={() => handleOpenSidePanel("objects")}
              className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 transition hover:bg-white"
            >
              Prompt Create
            </button>
            <button
              type="button"
              onClick={() => handleOpenSidePanel("generate")}
              className="flex-1 rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-white transition hover:bg-slate-800"
            >
              Generate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PerformanceAIDashboard() {
  return <PerformanceAIDashboardView />;
}
