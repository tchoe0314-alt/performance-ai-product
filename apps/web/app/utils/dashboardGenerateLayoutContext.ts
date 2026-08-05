import type { BuildingPlacement } from "../types";
import {
  REACTIVE_SYSTEM_STAGE_MAP,
  type EngineeringSystemKey,
} from "./workflowConstants";

export type GenerateLayoutContext = {
  count: number;
  semantic_count: number;
  labels: string[];
  drawn_labels: string[];
  affected_systems: EngineeringSystemKey[];
  review_required: true;
};

export function systemsImpactedByPlacement(target?: Partial<BuildingPlacement> | null): EngineeringSystemKey[] {
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
}

const layoutContextScore = (item: BuildingPlacement) => {
  const source = String(item.source || item.meta?.source || "").toLowerCase();
  const type = String(item.type || "").toLowerCase();
  const label = String(item.label || "").toLowerCase();
  let value = 0;
  if (/(review grading|review drainage|drainage area|fall line|custom|command).*(line|area|box|point)|^(line|area|box|point)\b/.test(label)) {
    value += 240;
  }
  if (item.meta?.semantic_object_model || item.meta?.semantic_geometry_state) value += 160;
  if (Array.isArray(item.meta?.combined_from_object_ids) && item.meta.combined_from_object_ids.length > 0) value += 130;
  if (item.meta?.command_created || ["user", "user_confirmed", "manual_drawn"].includes(source)) value += 120;
  if (["office_building", "building"].includes(type)) value += 100;
  if (["parking", "basin"].includes(type)) value += 80;
  if (["road", "driveway", "sidewalk"].includes(type)) value += 50;
  if (["utility_corridor", "hydrant", "inlet", "outfall", "manhole"].includes(type)) value += 40;
  if (item.geometry || item.geometryType) value += 20;
  if (source === "generated") value -= 20;
  return value;
};

const SEMANTIC_SITE_OBJECT_TYPES = new Set([
  "office_building",
  "building",
  "retail_building",
  "multifamily_building",
  "industrial_building",
  "pad",
  "parking",
  "basin",
  "outfall",
  "road",
  "driveway",
  "entrance",
  "sidewalk",
  "utility_corridor",
  "hydrant",
  "inlet",
  "manhole",
]);

export function isSemanticEngineeringPlacement(item: BuildingPlacement): boolean {
  return Boolean(
    item.meta?.semantic_object_model ||
    item.meta?.semantic_geometry_state ||
    SEMANTIC_SITE_OBJECT_TYPES.has(String(item.type || "").toLowerCase()),
  );
}

export function buildGenerateLayoutContext(buildingPlacements: BuildingPlacement[]): GenerateLayoutContext | null {
  const userLayoutContext = buildingPlacements.filter((item) => {
    if (!item.placed || item.type === "site" || item.meta?.generated_review_concept) return false;
    const source = String(item.source || item.meta?.source || "").toLowerCase();
    const type = String(item.type || "").toLowerCase();
    return Boolean(
      item.meta?.semantic_object_model ||
      item.meta?.semantic_geometry_state ||
      item.meta?.command_created ||
      SEMANTIC_SITE_OBJECT_TYPES.has(type) ||
      ["user", "user_confirmed", "manual_drawn", "generated"].includes(source),
    );
  });
  if (!userLayoutContext.length) return null;
  const rankedUserLayoutContext = [...userLayoutContext].sort((a, b) => layoutContextScore(b) - layoutContextScore(a));
  const semanticLayoutCount = userLayoutContext.filter(isSemanticEngineeringPlacement).length;
  return {
    count: userLayoutContext.length,
    semantic_count: semanticLayoutCount,
    labels: rankedUserLayoutContext.slice(0, 20).map((item) => String(item.label || item.id || "Draft object")),
    drawn_labels: rankedUserLayoutContext
      .filter((item) => {
        const source = String(item.source || item.meta?.source || "").toLowerCase();
        return Boolean(item.meta?.command_created || ["user", "user_confirmed", "manual_drawn"].includes(source));
      })
      .slice(0, 12)
      .map((item) => String(item.label || item.id || "Draft object")),
    affected_systems: Array.from(new Set(userLayoutContext.flatMap((item) => systemsImpactedByPlacement(item)))),
    review_required: true,
  };
}
