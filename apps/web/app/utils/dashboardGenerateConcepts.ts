import type { BuildingPlacement, SiteObjectType } from "../types";
import { parsePositiveNumber } from "./formatting";
import type { EngineeringSystemKey, SystemGenerationTarget } from "./workflowConstants";

type LotBounds = { w: number; h: number };

export function buildGenerateConceptPlacements({
  target,
  notes,
  lot,
  siteScaleLocked,
  buildingPlacements,
  buildingWidth,
  buildingDepth,
  parkingCount,
  parkingStallWidth,
  parkingStallDepth,
  parkingAisleWidth,
  parkingAdaAisleWidth,
  parkingAdaCount,
  parkingCompactCount,
  parkingCompactWidth,
  parkingAngle,
  parkingLoading,
}: {
  target: SystemGenerationTarget;
  notes: string[];
  lot: LotBounds;
  siteScaleLocked?: boolean;
  buildingPlacements: BuildingPlacement[];
  buildingWidth: string | number | null | undefined;
  buildingDepth: string | number | null | undefined;
  parkingCount: string | number | null | undefined;
  parkingStallWidth: string | number | null | undefined;
  parkingStallDepth: string | number | null | undefined;
  parkingAisleWidth: string | number | null | undefined;
  parkingAdaAisleWidth: string | number | null | undefined;
  parkingAdaCount: string | number | null | undefined;
  parkingCompactCount: string | number | null | undefined;
  parkingCompactWidth: string | number | null | undefined;
  parkingAngle: string | number | null | undefined;
  parkingLoading: "single" | "double";
}) {
  if (!lot.w || !lot.h || !siteScaleLocked) return [];
  const now = Date.now();
  const targetSystems =
    target === "full"
      ? (["roads", "parking", "grading", "drainage", "utilities"] as EngineeringSystemKey[])
      : ([target] as EngineeringSystemKey[]);
  const wants = (system: EngineeringSystemKey) => targetSystems.includes(system);
  const existingObjects = buildingPlacements.filter((item) => !Boolean(item.meta?.generated_review_concept));
  const hasExistingType = (...types: SiteObjectType[]) =>
    existingObjects.some((item) => item.placed && item.type && types.includes(item.type));
  const hasExistingNetwork = (network: string) =>
    existingObjects.some((item) => item.placed && String(item.meta?.network || "").toLowerCase() === network);
  const baseMeta = {
    generated_review_concept: true,
    visual_concept_only: true,
    engineering_status: "draft_review_required",
    review_status: "engineer_review_required",
    construction_release_allowed: false,
    source: "generate_visual_review_layer",
    source_note: "Generated as a visible review concept from the locked site and available source context.",
    auto_site_context_notes: notes.slice(0, 5),
  };
  const concept: BuildingPlacement[] = [];
  const addConcept = (item: BuildingPlacement) => {
    concept.push({
      ...item,
      generated: true,
      placed: true,
      source: "generated",
      locked: false,
      capabilities: item.capabilities ?? {
    movable: true,
    resizable: true,
    rotatable: false,
    deletable: true,
      },
      meta: {
    ...baseMeta,
    ...(item.meta ?? {}),
      },
    });
  };
  if (target === "full" && !hasExistingType("building", "office_building", "pad")) {
    const requestedArea = parsePositiveNumber(buildingWidth) && parsePositiveNumber(buildingDepth)
      ? Math.round((parsePositiveNumber(buildingWidth) ?? 0) * (parsePositiveNumber(buildingDepth) ?? 0))
      : 28000;
    const buildingDepthFt = Math.max(80, Math.min(lot.h * 0.18, Math.round(Math.sqrt(requestedArea / 2))));
    const buildingWidthFt = Math.max(150, Math.min(lot.w * 0.34, Math.round(requestedArea / buildingDepthFt)));
    addConcept({
      id: `generate-office-${now}`,
      label: `Review office building concept - ${requestedArea.toLocaleString()} sf`,
      type: "office_building",
      x: lot.w * 0.36,
      y: lot.h * 0.22,
      w: buildingWidthFt,
      d: buildingDepthFt,
      systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
      meta: {
    cad_layer: "C-BLDG",
    ui_color: "#64748b",
    requested_area_sf: requestedArea,
    generated_program_object: true,
      },
    });
  }
  if (wants("roads") && !hasExistingType("road", "driveway", "entrance")) {
    addConcept({
      id: `generate-road-${now}`,
      label: "Review driveway / access concept",
      type: "driveway",
      x: lot.w * 0.05,
      y: lot.h * 0.48,
      w: lot.w * 0.58,
      d: 24,
      geometryType: "polyline",
      geometry: [
    [lot.w * 0.02, lot.h * 0.56],
    [lot.w * 0.28, lot.h * 0.56],
    [lot.w * 0.48, lot.h * 0.48],
    [lot.w * 0.62, lot.h * 0.48],
      ],
      systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
      meta: { cad_layer: "C-ROAD", ui_color: "#334155" },
    });
  }
  if ((wants("roads") || target === "full") && !hasExistingType("sidewalk")) {
    addConcept({
      id: `generate-sidewalk-${now}`,
      label: "Review sidewalk / ADA route concept",
      type: "sidewalk",
      x: 0,
      y: 0,
      w: lot.w,
      d: lot.h,
      geometryType: "polyline",
      geometry: [
    [lot.w * 0.18, lot.h * 0.5],
    [lot.w * 0.38, lot.h * 0.5],
    [lot.w * 0.5, lot.h * 0.43],
    [lot.w * 0.65, lot.h * 0.43],
      ],
      systemDependencies: ["roads", "parking", "grading"],
      meta: { cad_layer: "C-WALK", routeKind: "ada_review_route", ui_color: "#0f766e" },
    });
  }
  if (wants("parking") && !hasExistingType("parking")) {
    const stalls = parsePositiveNumber(parkingCount) ?? 140;
    addConcept({
      id: `generate-parking-${now}`,
      label: `Review parking concept - ${Math.round(stalls)} stalls`,
      type: "parking",
      x: lot.w * 0.16,
      y: lot.h * 0.18,
      w: Math.min(lot.w * 0.42, 360),
      d: Math.min(lot.h * 0.28, 220),
      stallCount: Math.round(stalls),
      systemDependencies: ["roads", "parking", "grading", "drainage"],
      meta: {
    cad_layer: "C-PARK",
    ui_color: "#475569",
    parkingParams: {
      stallWidth: parsePositiveNumber(parkingStallWidth) ?? 9,
      stallDepth: parsePositiveNumber(parkingStallDepth) ?? 18,
      aisleWidth: parsePositiveNumber(parkingAisleWidth) ?? 24,
      adaAisleWidth: parsePositiveNumber(parkingAdaAisleWidth) ?? 8,
      adaCount: parsePositiveNumber(parkingAdaCount) ?? 0,
      compactCount: parsePositiveNumber(parkingCompactCount) ?? 0,
      compactWidth: parsePositiveNumber(parkingCompactWidth) ?? 8,
      angleDeg: parsePositiveNumber(parkingAngle) ?? 90,
      loading: parkingLoading,
    },
      },
    });
  }
  if (wants("drainage") && !hasExistingType("basin")) {
    addConcept({
      id: `generate-basin-${now}`,
      label: "Review detention basin concept",
      type: "basin",
      x: lot.w * 0.72,
      y: lot.h * 0.68,
      w: Math.min(lot.w * 0.2, 220),
      d: Math.min(lot.h * 0.16, 160),
      geometryType: "polygon",
      geometry: [
    [lot.w * 0.72, lot.h * 0.74],
    [lot.w * 0.75, lot.h * 0.68],
    [lot.w * 0.86, lot.h * 0.66],
    [lot.w * 0.93, lot.h * 0.73],
    [lot.w * 0.89, lot.h * 0.83],
    [lot.w * 0.76, lot.h * 0.84],
      ],
      systemDependencies: ["grading", "drainage"],
      meta: { cad_layer: "C-DRAIN", ui_color: "#0284c7" },
    });
  }
  if (wants("drainage") && !hasExistingType("outfall")) {
    addConcept({
      id: `generate-outfall-${now}`,
      label: "Review outfall / discharge point",
      type: "outfall",
      x: lot.w * 0.87,
      y: lot.h * 0.67,
      w: 12,
      d: 12,
      geometryType: "point",
      geometry: [[lot.w * 0.87, lot.h * 0.67]],
      systemDependencies: ["drainage", "utilities"],
      meta: { cad_layer: "C-DRAIN", role: "storm_outfall_review_point", ui_color: "#0ea5e9" },
    });
  }
  if (wants("drainage") && !hasExistingNetwork("storm")) {
    addConcept({
      id: `generate-drainage-path-${now}`,
      label: "Review storm flow path",
      type: "utility_corridor",
      x: 0,
      y: 0,
      w: lot.w,
      d: lot.h,
      geometryType: "polyline",
      geometry: [
    [lot.w * 0.72, lot.h * 0.74],
    [lot.w * 0.84, lot.h * 0.74],
    [lot.w * 0.84, lot.h * 0.66],
      ],
      systemDependencies: ["drainage", "utilities"],
      meta: { cad_layer: "C-PIPE-STORM", network: "storm", ui_color: "#0ea5e9" },
    });
  }
  if (wants("utilities")) {
    ([
      ["water", "Review water corridor concept", "#2563eb", 0.9],
      ["sanitary", "Review sanitary corridor concept", "#7c3aed", 0.86],
      ["storm", "Review storm sewer concept", "#0ea5e9", 0.82],
    ] as Array<[string, string, string, number]>).forEach(([network, label, color, yFactor]) => {
      if (hasExistingNetwork(network)) return;
      const startX = network === "water" ? 0.08 : network === "sanitary" ? 0.14 : 0.2;
      const endX = network === "water" ? 0.92 : network === "sanitary" ? 0.88 : 0.84;
      addConcept({
    id: `generate-utility-${network}-${now}`,
    label,
    type: "utility_corridor",
    x: 0,
    y: 0,
    w: lot.w,
    d: lot.h,
    geometryType: "polyline",
    geometry: [
      [lot.w * startX, lot.h * Number(yFactor)],
      [lot.w * ((startX + endX) / 2), lot.h * Number(yFactor)],
      [lot.w * endX, lot.h * Number(yFactor)],
      ...(network === "storm" ? ([[lot.w * endX, lot.h * 0.68]] as Array<[number, number]>) : []),
    ],
    systemDependencies: ["utilities"],
    meta: { cad_layer: "C-UTIL", network, ui_color: color },
      });
    });
  }
  if (wants("grading")) {
    addConcept({
      id: `generate-grade-arrow-${now}`,
      label: "Review grading fall concept",
      type: "custom",
      x: 0,
      y: 0,
      w: lot.w,
      d: lot.h,
      geometryType: "polyline",
      geometry: [
    [lot.w * 0.72, lot.h * 0.18],
    [lot.w * 0.88, lot.h * 0.18],
    [lot.w * 0.9, lot.h * 0.28],
      ],
      systemDependencies: ["grading", "drainage"],
      meta: { cad_layer: "C-GRADE", ui_color: "#94a3b8" },
    });
  }
  return concept;
}
