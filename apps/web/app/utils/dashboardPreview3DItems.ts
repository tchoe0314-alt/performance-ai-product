import type {
  BuildingPlacement,
  PlanResponse,
  Preview3DItem,
  SiteInputs,
  SourceConfidenceEntry,
} from "../types";
import type { CadEntityPreview } from "./cadEntityPreview";
import { SITE_OBJECT_CATALOG } from "./siteObjectCatalog";

type PreviewLayerFlags = {
  buildings: boolean;
  roads: boolean;
  drainage: boolean;
  utilities: boolean;
  structures: boolean;
  lots: boolean;
};

type LotBounds = { w: number; h: number };

function buildSourceTerrainPreview3DItems(siteInputs: SiteInputs | undefined, lot: LotBounds): Preview3DItem[] {
  const existingPackage = siteInputs?.existing_conditions_package as Record<string, unknown> | undefined;
  const canonical = existingPackage?.canonical_existing_conditions as Record<string, unknown> | undefined;
  const dem = (
    (existingPackage?.dem_lidar as Record<string, unknown> | undefined) ??
    (canonical?.dem_lidar as Record<string, unknown> | undefined)
  );
  const surfaceGrid = dem?.surface_grid as Record<string, unknown> | undefined;
  const rawSamples = Array.isArray(surfaceGrid?.samples) ? surfaceGrid.samples : [];
  const parsed = rawSamples
    .map((raw) => {
      const sample = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
      const xRatio = Number(sample.x_ratio);
      const yRatio = Number(sample.y_ratio);
      const elevationFt = Number(sample.elevation_ft);
      return Number.isFinite(xRatio) && Number.isFinite(yRatio) && Number.isFinite(elevationFt)
        ? { xRatio, yRatio, elevationFt }
        : null;
    })
    .filter((sample): sample is { xRatio: number; yRatio: number; elevationFt: number } => Boolean(sample));
  if (!surfaceGrid?.surface_ready || parsed.length < 4 || lot.w <= 0 || lot.h <= 0) return [];
  const baseline = Math.min(...parsed.map((sample) => sample.elevationFt));
  return parsed.slice(0, 121).map((sample, index) => ({
    id: `source-terrain-${index + 1}`,
    x: sample.xRatio * lot.w,
    y: sample.yRatio * lot.h,
    w: 0.5,
    h: 0.5,
    height: 0.1,
    z: sample.elevationFt - baseline,
    color: "#c9d9bf",
    label: `Public DEM ${sample.elevationFt.toFixed(1)} ft`,
    layer: "TERRAIN",
    source: String(surfaceGrid.provider || dem?.provider || "public DEM surface"),
    confidence: "source-backed review context",
    blockers: ["not project survey/control"],
    terrainSample: true,
    meta: {
      source_surface_ready: true,
      absolute_elevation_ft: sample.elevationFt,
      vertical_datum: dem?.vertical_datum ?? surfaceGrid.vertical_datum,
      horizontal_resolution: dem?.horizontal_resolution ?? surfaceGrid.horizontal_resolution,
      survey_backed: false,
      review_required: true,
    },
  }));
}

function contourElevationForPlacement(item: BuildingPlacement, fallbackIndex: number) {
  const metaElevation = Number((item.meta as { contour_elevation_ft?: number | string } | undefined)?.contour_elevation_ft);
  if (Number.isFinite(metaElevation)) return metaElevation;
  const labelMatch = String(item.label || "").match(/(-?\d+(?:\.\d+)?)/);
  if (labelMatch) {
    const labelElevation = Number(labelMatch[1]);
    if (Number.isFinite(labelElevation)) return labelElevation;
  }
  return 1000 - fallbackIndex * 2;
}

function buildReviewContourTerrainSamples(buildingPlacements: BuildingPlacement[]): Preview3DItem[] {
  const contourObjects = buildingPlacements.filter(
    (item) =>
      item.placed &&
      item.geometryType === "polyline" &&
      Array.isArray(item.geometry) &&
      String((item.meta as { preview_kind?: unknown } | undefined)?.preview_kind || "").toLowerCase() === "contour",
  );
  if (contourObjects.length < 2) return [];

  const elevations = contourObjects.map((item, index) => contourElevationForPlacement(item, index));
  const minElevation = Math.min(...elevations);
  const maxElevation = Math.max(...elevations);
  const elevationRange = Math.max(maxElevation - minElevation, 1);
  const verticalScale = Math.min(18, Math.max(5, elevationRange * 0.32));

  return contourObjects.flatMap((item, contourIndex) => {
    const points = (item.geometry || []) as Array<[number, number]>;
    const elevation = elevations[contourIndex];
    const z = ((elevation - minElevation) / elevationRange - 0.5) * verticalScale;
    const stride = Math.max(1, Math.floor(points.length / 4));
    return points
      .filter((_, pointIndex) => pointIndex % stride === 0 || pointIndex === points.length - 1)
      .slice(0, 5)
      .map(([x, y], pointIndex) => ({
        id: `review-contour-terrain-${contourIndex + 1}-${pointIndex + 1}`,
        x,
        y,
        w: 1,
        h: 1,
        height: 0.1,
        z,
        color: "#d9f99d",
        label: `Review contour ${Math.round(elevation)}`,
        layer: "TERRAIN",
        source: "review contour geometry",
        confidence: "visual contour review only",
        blockers: ["not survey control"],
        terrainSample: true,
      }));
  });
}

function normalizePreview3DLayer(layer: unknown) {
  const key = String(layer || "").toUpperCase();
  if (key.includes("BUILDING") || key.includes("PAD")) return "BUILDING";
  if (key.includes("PARK")) return "PARKING";
  if (key.includes("SIDEWALK") || key.includes("WALK")) return "SIDEWALK";
  if (key.includes("DRAIN") || key.includes("BASIN") || key.includes("STORM") || key.includes("POND")) return "DRAINAGE";
  if (key.includes("UTILITY") || key.includes("WATER") || key.includes("SAN") || key.includes("HYDRANT") || key.includes("MANHOLE")) return "UTILITY";
  if (key.includes("LOT") || key.includes("EASEMENT") || key.includes("CONSTRAINT") || key.includes("SETBACK")) return "CONSTRAINT";
  if (key.includes("TERRAIN") || key.includes("SITE")) return "TERRAIN";
  if (key.includes("ROAD") || key.includes("DRIVE")) return "ROAD";
  return key || "OBJECT";
}

function preview3DOverlapRatio(a: Preview3DItem, b: Preview3DItem) {
  const ax1 = a.x;
  const ay1 = a.y;
  const ax2 = a.x + Math.max(a.w, 0);
  const ay2 = a.y + Math.max(a.h, 0);
  const bx1 = b.x;
  const by1 = b.y;
  const bx2 = b.x + Math.max(b.w, 0);
  const by2 = b.y + Math.max(b.h, 0);
  const ix = Math.max(0, Math.min(ax2, bx2) - Math.max(ax1, bx1));
  const iy = Math.max(0, Math.min(ay2, by2) - Math.max(ay1, by1));
  const intersection = ix * iy;
  const smallerArea = Math.max(1, Math.min(Math.max(a.w, 0) * Math.max(a.h, 0), Math.max(b.w, 0) * Math.max(b.h, 0)));
  return intersection / smallerArea;
}

function mergePlacementLedPreview3DItems(backendItems: Preview3DItem[], placementItems: Preview3DItem[]) {
  if (!backendItems.length) return placementItems;
  if (!placementItems.length) return backendItems;

  const merged = [...placementItems];
  const existingIds = new Set(merged.map((item) => String(item.id || "")));
  backendItems.forEach((item) => {
    const id = String(item.id || "");
    const layer = normalizePreview3DLayer(item.layer);
    if (id && existingIds.has(id)) return;
    const isTerrainEvidence = layer === "TERRAIN" && (item.terrainSample || /terrain|elevation/i.test(String(item.label || item.source || "")));
    if (!isTerrainEvidence) {
      const duplicate = merged.some((candidate) => {
        const candidateLayer = normalizePreview3DLayer(candidate.layer);
        if (candidateLayer !== layer) return false;
        return preview3DOverlapRatio(item, candidate) >= 0.58;
      });
      if (duplicate) return;
    }
    merged.push(item);
    if (id) existingIds.add(id);
  });
  return merged;
}

function readGradingMeta(backendResult: PlanResponse | null | undefined): Record<string, unknown> | null {
  return (
    (backendResult?.final_plan?.meta as { grading?: Record<string, unknown> } | undefined)?.grading ??
    (backendResult?.metadata as { grading_summary?: Record<string, unknown> } | undefined)?.grading_summary ??
    (backendResult?.metadata as { grading?: Record<string, unknown> } | undefined)?.grading ??
    null
  );
}

export function hasDashboardGradingSurface(backendResult: PlanResponse | null | undefined): boolean {
  const gradingMeta = readGradingMeta(backendResult);
  if (!gradingMeta || typeof gradingMeta !== "object") return false;
  return Boolean(
    gradingMeta.proposed_surface ||
      gradingMeta.existing_surface ||
      (gradingMeta.surface_controls as { grade_range_ft?: number } | undefined)?.grade_range_ft,
  );
}

export function buildDashboardPreview3DView({
  backendResult,
  buildingPlacements,
  cadEntityPreview,
  lot,
  planPreviewAnnotations,
  previewLayersEffective,
  sourceConfidenceByObjectId,
  siteInputs,
}: {
  backendResult: PlanResponse | null | undefined;
  buildingPlacements: BuildingPlacement[];
  cadEntityPreview: CadEntityPreview;
  lot: { x?: number; y?: number; w: number; h: number };
  planPreviewAnnotations: { labels?: Array<Record<string, unknown>> } | null | undefined;
  previewLayersEffective: PreviewLayerFlags;
  sourceConfidenceByObjectId: Map<string, SourceConfidenceEntry>;
  siteInputs?: SiteInputs;
}) {
  const hasGradingSurface = hasDashboardGradingSurface(backendResult);
  const preview3DItems = buildBackendPreview3DItems({
    backendResult,
    cadEntityPreview,
    previewLayersEffective,
  });
  const preview3DAnnotationItems = buildAnnotationPreview3DItems({
    planPreviewAnnotations,
    previewLayersEffective,
  });
  const placementItems = buildPlacementPreview3DItems({
    lot,
    buildingPlacements,
    cadEntityPreviewItems3D: cadEntityPreview.items3D,
    sourceConfidenceByObjectId,
  });
  const sourceTerrainItems = buildSourceTerrainPreview3DItems(siteInputs, lot);
  const backendHasTerrainSamples = preview3DItems.some((item) => item.terrainSample);
  const preview3DPlacementItems = [
    ...(sourceTerrainItems.length
      ? placementItems.filter((item) => !item.terrainSample)
      : placementItems),
    ...(backendHasTerrainSamples ? [] : sourceTerrainItems),
  ];
  const preview3DEffectiveItems = preview3DItems.length
    ? mergePlacementLedPreview3DItems(preview3DItems, preview3DPlacementItems)
    : preview3DAnnotationItems.length
      ? mergePlacementLedPreview3DItems(preview3DAnnotationItems, preview3DPlacementItems)
      : preview3DPlacementItems;
  const usingAnnotation3D = preview3DItems.length === 0 && preview3DAnnotationItems.length > 0;

  return {
    hasGradingSurface,
    preview3DAnnotationItems,
    preview3DEffectiveItems,
    preview3DItems,
    preview3DPlacementItems,
    usingAnnotation3D,
  };
}

export function buildBackendPreview3DItems({
  backendResult,
  cadEntityPreview,
  previewLayersEffective,
}: {
  backendResult: PlanResponse | null | undefined;
  cadEntityPreview: CadEntityPreview;
  previewLayersEffective: PreviewLayerFlags;
}): Preview3DItem[] {
  const actions = Array.isArray(backendResult?.final_plan?.actions)
    ? backendResult.final_plan.actions
    : [];
  const items: Preview3DItem[] = [];
  const gradingMeta = readGradingMeta(backendResult);
  const surfaceControls =
    gradingMeta && typeof gradingMeta === "object"
      ? ((gradingMeta as { surface_controls?: Record<string, unknown> }).surface_controls ?? {})
      : {};
  const rawSurfaceModel =
    gradingMeta && typeof gradingMeta === "object"
      ? ((gradingMeta as { surface_model?: Record<string, unknown> }).surface_model ?? {})
      : {};
  const rawPreviewElevationSamples = Array.isArray(rawSurfaceModel.spot_elevations)
    ? rawSurfaceModel.spot_elevations
        .map((item) => {
          const record = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
          const x = Number(record.x);
          const y = Number(record.y);
          const z = Number(record.z);
          return Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z) ? { x, y, z } : null;
        })
        .filter((item): item is { x: number; y: number; z: number } => Boolean(item))
        .slice(0, 72)
    : [];
  const elevationBaseline = rawPreviewElevationSamples.length
    ? Math.min(...rawPreviewElevationSamples.map((sample) => sample.z))
    : 0;
  const previewElevationSamples = rawPreviewElevationSamples.map((sample) => ({
    ...sample,
    z: sample.z - elevationBaseline,
  }));
  const gradeRangeFt = Number((surfaceControls as { grade_range_ft?: number }).grade_range_ft ?? 0);
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
  for (const action of actions) {
    if (!action || typeof action !== "object") continue;
    const actionRecord = action as Record<string, unknown>;
    const task = String(actionRecord.task || "").toLowerCase();
    const layerRaw = String(actionRecord.layer || "").toUpperCase();
    const normalizedLayer = layerRaw.startsWith("C-") ? layerRaw.slice(2) : layerRaw;
    const meta = actionRecord.meta as Record<string, unknown> | undefined;
    const previewRole = String(meta?.preview_role || (meta?.is_final ? "final" : "overlay"));
    if (previewRole !== "final") continue;
    const actionId = String(actionRecord.id || meta?.site_object_id || "");
    if (actionId && (cadEntityPreview.sourceIds.has(actionId) || cadEntityPreview.linkedIds.has(actionId))) {
      continue;
    }

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
    const pondAdjustment = normalizedLayer === "POND" ? Math.max(1.5, gradeRangeFt * 0.12) : 0;
    items.push({
      id: String(actionRecord.id || meta?.site_object_id || `${normalizedLayer.toLowerCase()}-${items.length + 1}`),
      x: x1,
      y: y1,
      w,
      h,
      height: heightFt,
      z: isDrainage ? -pondAdjustment : 0,
      color,
      label: label || normalizedLayer,
      layer: isBuilding
        ? "BUILDING"
        : isStructure
          ? "STRUCTURE"
          : isDrainage
            ? "DRAINAGE"
            : isUtility
              ? "UTILITY"
              : isParking
                ? "PARKING"
                : isRoad
                  ? normalizedLayer === "SIDEWALK" || normalizedLayer === "WALK" ? "SIDEWALK" : "ROAD"
                  : "OBJECT",
      source: String(meta?.source_name || meta?.source || "final plan preview"),
      confidence: typeof meta?.confidence === "number" || typeof meta?.confidence === "string" ? meta.confidence : "review required",
      blockers: Array.isArray(meta?.blockers) ? meta.blockers.map((blocker) => String(blocker)) : [],
    });
  }

  cadEntityPreview.items3D.forEach((item) => {
    addBounds([item.x, item.y, item.x + item.w, item.y + item.h]);
  });
  previewElevationSamples.forEach((sample, index) => {
    addBounds([sample.x, sample.y, sample.x, sample.y]);
    items.push({
      id: `terrain-sample-${index + 1}`,
      x: sample.x,
      y: sample.y,
      w: 1,
      h: 1,
      height: 0.1,
      z: sample.z,
      color: "#bbf7d0",
      label: `Elevation sample ${index + 1}`,
      layer: "TERRAIN",
      source: "preview elevation sample",
      confidence: "review required",
      terrainSample: true,
    });
  });
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
      source: previewElevationSamples.length ? "preview elevation sample extent" : "flat fallback extent",
      terrainSample: false,
    });
  }
  return [...cadEntityPreview.items3D, ...items];
}

export function buildAnnotationPreview3DItems({
  planPreviewAnnotations,
  previewLayersEffective,
}: {
  planPreviewAnnotations: { labels?: unknown[] } | null | undefined;
  previewLayersEffective: PreviewLayerFlags;
}): Preview3DItem[] {
  const labels = Array.isArray(planPreviewAnnotations?.labels) ? planPreviewAnnotations.labels : [];
  if (!labels.length) return [];
  const items: Preview3DItem[] = [];
  const scale = 100;
  for (const label of labels) {
    const bounds = (label as { bounds?: { x1?: number; y1?: number; x2?: number; y2?: number } }).bounds;
    if (!bounds) continue;
    const x1 = Number(bounds.x1 ?? 0);
    const y1 = Number(bounds.y1 ?? 0);
    const x2 = Number(bounds.x2 ?? 0);
    const y2 = Number(bounds.y2 ?? 0);
    const w = Math.max(0.01, (x2 - x1) * scale);
    const h = Math.max(0.01, (y2 - y1) * scale);
    const layer = String((label as { layer?: string }).layer || "").toUpperCase();
    const isBuilding = layer === "BUILDING";
    const isRoad = ["ROAD", "PAVEMENT", "WALK", "SIDEWALK"].includes(layer);
    const isParking = layer === "PARKING";
    const isDrainage = ["DRAIN", "PIPE", "STORM", "BASIN_BOUNDARY"].includes(layer);
    const isUtility = ["SAN", "UTILITY", "WATER"].includes(layer);
    const isStructure = ["STRUCTURE", "BRIDGE", "POOL"].includes(layer);
    const isLot = layer === "LOT";

    if (isBuilding && !previewLayersEffective.buildings) continue;
    if ((isRoad || isParking) && !previewLayersEffective.roads) continue;
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
    const heightFt = isBuilding ? 26 : isStructure ? 8 : isDrainage ? 3 : isUtility ? 2 : isRoad ? 1.5 : isParking ? 1 : 1;
    items.push({
      id: String((label as { id?: string }).id || `${layer.toLowerCase()}-annotation-${items.length + 1}`),
      x: x1 * scale,
      y: y1 * scale,
      w,
      h,
      height: heightFt,
      color,
      label: String((label as { label?: string }).label || layer || "Shape"),
      layer: isBuilding
        ? "BUILDING"
        : isStructure
          ? "STRUCTURE"
          : isDrainage
            ? "DRAINAGE"
            : isUtility
              ? "UTILITY"
              : isParking
                ? "PARKING"
                : isRoad
                  ? layer === "SIDEWALK" || layer === "WALK" ? "SIDEWALK" : "ROAD"
                  : isLot
                    ? "CONSTRAINT"
                    : "OBJECT",
      source: "preview annotation",
      confidence: "annotation review required",
    });
  }
  return items;
}

export function buildPlacementPreview3DItems({
  lot,
  buildingPlacements,
  cadEntityPreviewItems3D,
  sourceConfidenceByObjectId,
}: {
  lot: LotBounds;
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewItems3D: Preview3DItem[];
  sourceConfidenceByObjectId: Map<string, SourceConfidenceEntry>;
}): Preview3DItem[] {
  const items: Preview3DItem[] = [];
  const placementIds = new Set(
    buildingPlacements
      .filter((item) => item.type !== "site" && item.placed)
      .map((item) => String(item.id || ""))
      .filter(Boolean),
  );
  const independentCadItems = cadEntityPreviewItems3D.filter((item) => {
    const linkedObjectId = String(item.linkedObjectId || "");
    const sourceId = String(item.id || "");
    return !placementIds.has(linkedObjectId) && !placementIds.has(sourceId);
  });
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
  items.push(...buildReviewContourTerrainSamples(buildingPlacements));
  buildingPlacements
    .filter((item) => item.type !== "site" && item.placed)
    .forEach((item) => {
      const confidenceEntry = sourceConfidenceByObjectId.get(item.id);
      const metaConfidence =
        typeof item.meta?.confidence === "number" || typeof item.meta?.confidence === "string"
          ? item.meta.confidence
          : null;
      const metaBlockers = Array.isArray(item.meta?.blockers)
        ? item.meta.blockers.map((blocker) => String(blocker))
        : [];
      const isBuilding = Boolean(item.type && item.type.includes("building")) || !item.type;
      const isSidewalk = item.type === "sidewalk";
      const isRoad = item.type === "road" || item.type === "driveway";
      const isParking = item.type === "parking";
      const isDrainage = item.type === "basin" || item.type === "inlet" || item.type === "outfall";
      const isUtility = item.type === "hydrant" || item.type === "manhole" || item.type === "utility_corridor";
      const isLandscape = item.type === "open_space" || item.type === "landscape";
      const isAmenity = item.type === "amenity";
      const isLotBlock = item.type === "lot_block";
      const isConstraint = item.type === "setback_zone" || item.type === "no_build_zone";
      const rawCorridorWidth =
        Number(item.meta?.corridor_width_ft) ||
        Number(item.meta?.width_ft) ||
        Number(item.meta?.road_width_ft) ||
        Number(item.meta?.sidewalk_width_ft) ||
        0;
      const corridorWidth = isRoad
        ? Math.max(18, Math.min(rawCorridorWidth || Math.min(item.w, item.d) || 28, 42))
        : isSidewalk
          ? Math.max(4, Math.min(rawCorridorWidth || 6, 12))
          : undefined;
      items.push({
        id: item.id,
        x: item.x ?? 0,
        y: item.y ?? 0,
        w: Math.max(1, item.w),
        h: Math.max(1, item.d),
        height: isBuilding
          ? Math.max(8, Number(item.h ?? 28))
          : isDrainage
            ? 3
          : isRoad
              ? 1.5
              : isParking
                ? 1
                : isSidewalk
                  ? 0.4
                  : isLandscape || isAmenity
                    ? 0.35
                    : isLotBlock || isConstraint
                      ? 0.08
                      : 0.1,
        rotation: Number.isFinite(Number(item.rotation)) ? Number(item.rotation) : 0,
        z: isDrainage ? -1 : 0,
        geometryType: item.geometryType,
        geometry: item.geometry,
        corridorWidth,
        color: isBuilding
          ? "#d1d5db"
          : isDrainage
            ? "#bfdbfe"
            : isUtility
              ? "#e9d5ff"
          : isSidewalk
                ? "#d6d3d1"
                : isLandscape
                  ? "#a7c77b"
                  : isAmenity
                    ? "#eab308"
                    : isLotBlock
                      ? "#f8fafc"
                      : isConstraint
                      ? "#eef2ff"
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
              : isSidewalk
                ? "SIDEWALK"
                : isLandscape
                  ? "LANDSCAPE"
                  : isAmenity
                    ? "STRUCTURE"
                    : isLotBlock
                      ? "LOT"
                      : isConstraint
                        ? "CONSTRAINT"
                        : "OBJECT",
        source: confidenceEntry?.source_name || item.source || "workspace object",
        confidence: confidenceEntry?.confidence_band || item.confidence || metaConfidence,
        blockers: [
          ...(confidenceEntry?.why_low_confidence ? [confidenceEntry.why_low_confidence] : []),
          ...(confidenceEntry?.next_action ? [confidenceEntry.next_action] : []),
          ...metaBlockers,
        ],
        meta: item.meta,
      });
    });
  return [...independentCadItems, ...items];
}
