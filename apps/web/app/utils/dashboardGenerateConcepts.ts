import type { BuildingPlacement, SiteObjectType } from "../types";
import { parsePositiveNumber } from "./formatting";
import { footprintInside, objectFootprints } from "./siteInterference";
import type { EngineeringSystemKey, SystemGenerationTarget } from "./workflowConstants";

type LotBounds = { w: number; h: number };

export type GenerateConceptPlacementInput = {
  target: SystemGenerationTarget;
  notes: string[];
  lot: LotBounds;
  siteScaleLocked?: boolean;
  buildingPlacements: BuildingPlacement[];
  projectType?: string | null;
  buildingProgramSf?: string | number | null;
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
};

export type GenerateConceptPlacementResult = {
  placements: BuildingPlacement[];
  blockers: string[];
};

export const isReplaceableGeneratedReviewConcept = (item: BuildingPlacement) =>
  Boolean(item.meta?.generated_review_concept) && item.source === "generated";

export function buildGenerateConceptPlacementResult({
  target,
  notes,
  lot,
  siteScaleLocked,
  buildingPlacements,
  projectType,
  buildingProgramSf,
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
}: GenerateConceptPlacementInput): GenerateConceptPlacementResult {
  if (!lot.w || !lot.h || !siteScaleLocked) return { placements: [], blockers: [] };
  const now = Date.now();
  const targetSystems =
    target === "full"
      ? (["roads", "parking", "grading", "drainage", "utilities"] as EngineeringSystemKey[])
      : ([target] as EngineeringSystemKey[]);
  const wants = (system: EngineeringSystemKey) => targetSystems.includes(system);
  // A generated review concept becomes authored canonical geometry once the
  // user edits it. Preserve that object on rerun; only replace untouched
  // generated review-layer objects.
  const existingObjects = buildingPlacements.filter((item) => !isReplaceableGeneratedReviewConcept(item));
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
  const blockers: string[] = [];
  const activeSite = existingObjects.find(item => item.type === "site" && item.placed !== false);
  const activeBoundary = activeSite ? objectFootprints(activeSite)[0] : null;
  const fitsBoundary = (item: BuildingPlacement) => !activeBoundary
    || objectFootprints(item).every(footprint => footprintInside(activeBoundary, footprint));
  const moveTo = (item: BuildingPlacement, x: number, y: number): BuildingPlacement => {
    const dx = x - (item.x ?? 0), dy = y - (item.y ?? 0);
    return {
      ...item,
      x,
      y,
      geometry: item.geometry?.map(point => [point[0] + dx, point[1] + dy] as [number, number]),
    };
  };
  const fitToBoundary = (item: BuildingPlacement): BuildingPlacement | null => {
    if (!activeBoundary || fitsBoundary(item)) return item;
    const maxX = Math.max(0, lot.w - item.w), maxY = Math.max(0, lot.h - item.d);
    const x = Math.max(0, Math.min(item.x ?? 0, maxX));
    const y = Math.max(0, Math.min(item.y ?? 0, maxY));
    const stepX = Math.max(lot.w / 40, 1), stepY = Math.max(lot.h / 40, 1);
    const candidates: Array<[number, number]> = [[x, y]];
    for (let step = 1; step <= 40; step += 1) {
      candidates.push(
        [x, Math.max(0, y - step * stepY)],
        [x, Math.min(maxY, y + step * stepY)],
        [Math.max(0, x - step * stepX), y],
        [Math.min(maxX, x + step * stepX), y],
      );
    }
    for (let row = 0; row <= 20; row += 1) for (let column = 0; column <= 20; column += 1) {
      candidates.push([maxX * column / 20, maxY * row / 20]);
    }
    const visited = new Set<string>();
    for (const [candidateX, candidateY] of candidates) {
      const key = `${candidateX.toFixed(6)}:${candidateY.toFixed(6)}`;
      if (visited.has(key)) continue;
      visited.add(key);
      const moved = moveTo(item, candidateX, candidateY);
      if (fitsBoundary(moved)) return moved;
    }
    return null;
  };
  const addConcept = (item: BuildingPlacement) => {
    // Explicit geometry is in site coordinates. Its selection bounds must not
    // cover the entire site merely because it was generated from the site.
    const points = item.geometry;
    const bounds = points?.length ? {
      x: Math.min(...points.map(point => point[0])),
      y: Math.min(...points.map(point => point[1])),
      w: Math.max(...points.map(point => point[0])) - Math.min(...points.map(point => point[0])),
      d: Math.max(...points.map(point => point[1])) - Math.min(...points.map(point => point[1])),
    } : {};
    const candidate: BuildingPlacement = {
      ...item,
      ...bounds,
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
    };
    const fitted = fitToBoundary(candidate);
    if (!fitted) {
      blockers.push(`${item.label} cannot fit inside the active site boundary without changing its required geometry.`);
      return;
    }
    concept.push(fitted);
  };
  const canonicalProgramArea = parsePositiveNumber(buildingProgramSf);
  const dimensionProgramArea = parsePositiveNumber(buildingWidth) && parsePositiveNumber(buildingDepth)
    ? Math.round((parsePositiveNumber(buildingWidth) ?? 0) * (parsePositiveNumber(buildingDepth) ?? 0))
    : null;
  // Never invent a program. The canonical brief is authoritative when it is
  // present; dimensions are a legacy fallback only when no brief target exists.
  const requestedBuildingArea = canonicalProgramArea ? Math.round(canonicalProgramArea) : dimensionProgramArea;
  const selectedProjectType = String(projectType ?? "").trim().toLowerCase();
  const generatedBuilding = selectedProjectType === "industrial_site"
    ? { type: "industrial_building" as const, use: "industrial", label: "industrial building" }
    : selectedProjectType === "commercial_pad"
      ? { type: "retail_building" as const, use: "retail", label: "retail building" }
      : selectedProjectType === "multifamily_site"
        ? { type: "multifamily_building" as const, use: "multifamily", label: "multifamily building" }
        : selectedProjectType === "office_site"
          ? { type: "office_building" as const, use: "office", label: "office building" }
          : { type: "building" as const, use: "unspecified", label: "building" };
  const plannedParkingX = lot.w * 0.16;
  const plannedParkingWidth = Math.min(lot.w * 0.42, 360);
  const plannedParkingDepth = Math.min(lot.h * 0.28, 220);
  if (target === "full" && requestedBuildingArea && !hasExistingType(
    "building", "office_building", "retail_building", "multifamily_building", "industrial_building", "pad",
  )) {
    const requestedArea = requestedBuildingArea;
    const buildingX = Math.max(lot.w * 0.62, plannedParkingX + plannedParkingWidth + 2);
    const buildingY = lot.h * 0.22;
    const availableWidth = lot.w * 0.96 - buildingX;
    const availableDepth = lot.h * 0.96 - buildingY;
    let buildingDepthFt = Math.max(80, Math.min(lot.h * 0.18, Math.round(Math.sqrt(requestedArea / 2))));
    let buildingWidthFt = requestedArea / buildingDepthFt;
    if (buildingWidthFt > availableWidth && availableWidth > 0) {
      buildingWidthFt = availableWidth;
      buildingDepthFt = requestedArea / buildingWidthFt;
    }
    const programFits = availableWidth > 0 && availableDepth > 0
      && buildingWidthFt > 0 && buildingDepthFt > 0
      && buildingWidthFt <= availableWidth && buildingDepthFt <= availableDepth;
    if (programFits) {
      addConcept({
        id: `generate-${generatedBuilding.use}-${now}`,
        label: `Review ${generatedBuilding.label} concept - ${requestedArea.toLocaleString()} sf`,
        type: generatedBuilding.type,
        x: buildingX,
        y: buildingY,
        w: buildingWidthFt,
        d: buildingDepthFt,
        systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
        meta: {
      cad_layer: "C-BLDG",
      ui_color: "#64748b",
      requested_area_sf: requestedArea,
      requested_project_type: selectedProjectType || null,
      building_use: generatedBuilding.use,
      generated_program_object: true,
        },
      });
    }
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
      x: plannedParkingX,
      y: lot.h * 0.18,
      w: plannedParkingWidth,
      d: plannedParkingDepth,
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
  return { placements: concept, blockers: [...new Set(blockers)] };
}

export function buildGenerateConceptPlacements(input: GenerateConceptPlacementInput) {
  return buildGenerateConceptPlacementResult(input).placements;
}
