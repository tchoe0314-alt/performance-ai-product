import type { SurveySlopeResponse } from "../types";

import { toReadableLabel } from "./formatting";

export type SystemGenerationTarget = "roads" | "parking" | "grading" | "drainage" | "utilities" | "full";
export type EngineeringSystemKey = Exclude<SystemGenerationTarget, "full">;
export type ReactiveValidationState = {
  status: "idle" | "pending" | "ready";
  changedSystems: EngineeringSystemKey[];
  changedTargets: string[];
  requiresConfirmation: boolean;
  message: string;
};

export type QuantityReviewStatus = "ok" | "review" | "reference" | "missing_cost" | "untraced" | "stale";
export type QuantityReviewRow = {
  metric: string;
  label: string;
  quantity: number;
  unit: string;
  canonicalIds: string[];
  sourceIds: string[];
  sourceStage: string;
  sourceLayer: string;
  method: string;
  confidence: string;
  costApplicable: boolean;
  traceRequired: boolean;
  traceComplete: boolean;
  delta: number | null;
  previousQuantity: number | null;
  currentQuantity: number | null;
  costItem: string;
  unitCost: number | null;
  amount: number | null;
  currency: string;
  priceSource: string;
  priceSourceItemId: string;
  productionPrice: boolean;
  missingCost: boolean;
  status: QuantityReviewStatus;
};

export const SQFT_PER_ACRE = 43_560;
export const SITE_WARNING_ACRES = 250;
export const SITE_GRADING_HARD_BLOCK_ACRES = 500;
export const DEFAULT_BLANK_SITE_WIDTH_FT = 300;
export const DEFAULT_BLANK_SITE_DEPTH_FT = 300;
export const OVERSIZED_SITE_MESSAGE =
  "Selected site is very large. Zoom in or reduce site area before grading.";
export const ACTIVE_PROJECT_STORAGE_KEY = "civora.activeProjectId";

export function isHardGenerateBlocker(label: string): boolean {
  return (
    label === "missing site boundary dimensions" ||
    label === "site boundary exists but is not locked" ||
    label === OVERSIZED_SITE_MESSAGE
  );
}

export function buildAssumedSlopeEstimate(slopePercent = 8): SurveySlopeResponse {
  const safeSlopePercent = Number.isFinite(slopePercent) && slopePercent > 0 ? slopePercent : 8;
  return {
    success: true,
    slope_ratio: safeSlopePercent / 100,
    slope_percent: safeSlopePercent,
    downhill_dx: 1,
    downhill_dy: 1,
    direction: "southeast",
    point_count: 0,
    warnings: [
      "Assumed terrain slope for early layout only. Survey/control is still required before engineering reliance.",
    ],
  };
}

export const siteAreaAcresFromSize = (widthFt?: number | null, heightFt?: number | null) => {
  if (!widthFt || !heightFt) return 0;
  return (widthFt * heightFt) / SQFT_PER_ACRE;
};

export type SystemStatus = "fresh" | "stale" | "not_generated";

export const isEngineeringSystemStatus = (value: unknown): value is SystemStatus =>
  value === "fresh" || value === "stale" || value === "not_generated";

export const DEFAULT_SYSTEM_STATUS: Record<
  "roads" | "parking" | "grading" | "drainage" | "utilities",
  SystemStatus
> = {
  roads: "not_generated",
  parking: "not_generated",
  grading: "not_generated",
  drainage: "not_generated",
  utilities: "not_generated",
};

export const REACTIVE_EDIT_POLICY_PREFERENCE = {
  live_visual_update: true,
  cheap_validation_auto_run: true,
  auto_engineering_rerun_max_cost: "quick",
  debounced_validation_ms: 500,
  require_confirmation_for_heavy_engineering: true,
  stale_exports_block_download: true,
} as const;

export const REACTIVE_SYSTEM_STAGE_MAP: Partial<Record<
  EngineeringSystemKey,
  string[]
>> = {
  roads: ["layout", "grading", "drainage", "storm_pipes", "utility_network", "coordination_resolution", "qa"],
  parking: ["layout", "grading", "drainage", "storm_pipes", "coordination_resolution", "qa"],
  grading: ["grading", "drainage", "storm_pipes", "sanitary", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa"],
  drainage: ["drainage", "storm_pipes", "coordination_resolution", "sheets", "qa"],
  utilities: ["sanitary", "utility_network", "coordination_resolution", "sheets", "qa"],
};

export const formatStageLabel = (value: string) => value.replace(/_/g, " ");

export const QUANTITY_METRIC_LABELS: Record<string, { label: string; unit: string }> = {
  lot_area_sf: { label: "Lot area", unit: "sf" },
  building_area_sf: { label: "Building area", unit: "sf" },
  parking_area_sf: { label: "Parking area", unit: "sf" },
  road_area_sf: { label: "Road area", unit: "sf" },
  sidewalk_area_sf: { label: "Sidewalk area", unit: "sf" },
  estimated_impervious_area_sf: { label: "Impervious area", unit: "sf" },
  estimated_parking_stalls: { label: "Parking stalls", unit: "stalls" },
  road_length_ft: { label: "Road length", unit: "ft" },
  sidewalk_length_ft: { label: "Sidewalk length", unit: "ft" },
  pipe_length_ft: { label: "Pipe length", unit: "ft" },
  utility_length_ft: { label: "Utility length", unit: "ft" },
  sanitary_length_ft: { label: "Sanitary length", unit: "ft" },
  sanitary_manhole_count: { label: "Sanitary manholes", unit: "ea" },
  sanitary_service_count: { label: "Sanitary services", unit: "ea" },
  drainage_flow_length_ft: { label: "Drainage flow length", unit: "ft" },
  pond_area_sf: { label: "Pond area", unit: "sf" },
  pond_count: { label: "Pond count", unit: "ea" },
  inlet_count: { label: "Inlet count", unit: "ea" },
  bridge_area_sf: { label: "Bridge area", unit: "sf" },
  pool_area_sf: { label: "Pool area", unit: "sf" },
  lot_feature_count: { label: "Lot count", unit: "ea" },
};

export const QUANTITY_METRIC_ORDER = Object.keys(QUANTITY_METRIC_LABELS);

export const COST_APPLICABLE_QUANTITY_METRICS = new Set([
  "parking_area_sf",
  "road_area_sf",
  "sidewalk_area_sf",
  "pipe_length_ft",
  "inlet_count",
  "pond_area_sf",
  "utility_length_ft",
  "sanitary_length_ft",
  "sanitary_manhole_count",
  "sanitary_service_count",
  "estimated_parking_stalls",
]);

export const readNumberOrNull = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

export const uniqueStrings = (items: unknown[]): string[] =>
  Array.from(new Set(items.map((item) => String(item || "").trim()).filter(Boolean)));

export const quantityMetricFallbackUnit = (metric: string) => {
  if (metric.endsWith("_sf")) return "sf";
  if (metric.endsWith("_ft")) return "ft";
  if (metric.endsWith("_count")) return "ea";
  return "units";
};

export const quantityMetricLabel = (metric: string) =>
  QUANTITY_METRIC_LABELS[metric]?.label || toReadableLabel(metric);

export const statusLabelForQuantityReview = (status: QuantityReviewStatus) => {
  if (status === "missing_cost") return "Missing cost";
  if (status === "untraced") return "Untraced";
  if (status === "stale") return "Delta";
  if (status === "ok") return "Mapped";
  if (status === "reference") return "Reference";
  return "Review";
};

export const EMPTY_REACTIVE_VALIDATION: ReactiveValidationState = {
  status: "idle",
  changedSystems: [],
  changedTargets: [],
  requiresConfirmation: false,
  message: "",
};
