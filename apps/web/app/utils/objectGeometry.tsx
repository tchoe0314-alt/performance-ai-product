import type { BuildingPlacement, CanonicalGeometryHandoffV1, SiteObjectType } from "../types";

import { toReadableLabel } from "./formatting";
import { SITE_OBJECT_CATALOG } from "./siteObjectCatalog";

export const clampValue = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

export type CustomGeometryMode = "polygon" | "polyline" | "rect" | "point";

export const isCustomGeometryMode = (value: unknown): value is CustomGeometryMode =>
  value === "polygon" || value === "polyline" || value === "rect" || value === "point";

export const normalizeGeometryPoints = (points: unknown): Array<[number, number]> | undefined =>
  Array.isArray(points)
    ? points
        .map((pt) => (Array.isArray(pt) ? ([Number(pt[0]), Number(pt[1])] as [number, number]) : null))
        .filter((pt): pt is [number, number] => pt !== null && Number.isFinite(pt[0]) && Number.isFinite(pt[1]))
    : undefined;

export const getGeometryBounds = (geometry: Array<[number, number]>) => {
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

export const getGeometryLength = (geometry: Array<[number, number]>, closed = false) => {
  const points = closed && geometry.length > 2 ? [...geometry, geometry[0]] : geometry;
  return points.slice(1).reduce((sum, pt, idx) => {
    const prev = points[idx];
    return sum + Math.hypot(pt[0] - prev[0], pt[1] - prev[1]);
  }, 0);
};

export const getPolygonArea = (geometry: Array<[number, number]>) => {
  if (geometry.length < 3) return 0;
  const sum = geometry.reduce((acc, pt, idx) => {
    const next = geometry[(idx + 1) % geometry.length];
    return acc + pt[0] * next[1] - next[0] * pt[1];
  }, 0);
  return Math.abs(sum) / 2;
};

export const pointDistance = (a: [number, number], b: [number, number]) => Math.hypot(b[0] - a[0], b[1] - a[1]);

export const selectedObjectsToSemanticArea = (items: BuildingPlacement[], tolerance = 0.25) => {
  const segments: Array<[[number, number], [number, number]]> = [];
  const blockers: string[] = [];
  const areaItems: BuildingPlacement[] = [];
  const semanticAreaTypes = new Set<SiteObjectType>([
    "building",
    "retail_building",
    "multifamily_building",
    "industrial_building",
    "office_building",
    "pad",
    "pool",
    "amenity",
    "open_space",
    "parking",
    "basin",
    "landscape",
    "no_build_zone",
    "setback_zone",
    "lot_block",
  ]);
  items.forEach((item) => {
    const geometry = normalizeGeometryPoints(item.geometry);
    if (item.type && semanticAreaTypes.has(item.type) && item.w > 0 && item.d > 0) {
      const x = item.x ?? 0;
      const y = item.y ?? 0;
      areaItems.push({
        ...item,
        geometryType: "polygon",
        geometry: geometry && geometry.length >= 3
          ? geometry
          : [
              [x, y],
              [x + item.w, y],
              [x + item.w, y + item.d],
              [x, y + item.d],
            ],
      });
      return;
    }
    if (item.geometryType === "polyline" && geometry && geometry.length >= 2) {
      geometry.slice(1).forEach((pt, index) => segments.push([geometry[index], pt]));
      return;
    }
    if ((item.geometryType === "polygon" || item.geometryType === "rect") && geometry && geometry.length >= 3) {
      areaItems.push(item);
      return;
    }
    if (item.geometryType === "point") {
      blockers.push(`${item.label} is a point, not area linework.`);
      return;
    }
    const x = item.x ?? 0;
    const y = item.y ?? 0;
    if (item.w > 0 && item.d > 0 && item.type !== "site") {
      areaItems.push({
        ...item,
        geometryType: "polygon",
        geometry: [
          [x, y],
          [x + item.w, y],
          [x + item.w, y + item.d],
          [x, y + item.d],
        ],
      });
      return;
    }
    blockers.push(`${item.label} does not have usable geometry.`);
  });
  if (areaItems.length === 1 && !segments.length && !blockers.length) {
    const geometry = normalizeGeometryPoints(areaItems[0].geometry) ?? [];
    return { valid: geometry.length >= 3, geometry, blockers: geometry.length >= 3 ? [] : ["Selected area needs at least three points."], sourceMode: "existing_area" as const };
  }
  if (areaItems.length > 1 && !segments.length && !blockers.length) {
    const geometryPoints = areaItems.flatMap((item) => normalizeGeometryPoints(item.geometry) ?? []);
    const validPoints = geometryPoints.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
    if (validPoints.length < 3) {
      return { valid: false, geometry: [] as Array<[number, number]>, blockers: ["Selected areas do not have enough geometry to group."], sourceMode: "program_group_bounds" as const };
    }
    const xs = validPoints.map(([x]) => x);
    const ys = validPoints.map(([, y]) => y);
    return {
      valid: true,
      geometry: [
        [Math.min(...xs), Math.min(...ys)],
        [Math.max(...xs), Math.min(...ys)],
        [Math.max(...xs), Math.max(...ys)],
        [Math.min(...xs), Math.max(...ys)],
      ] as Array<[number, number]>,
      blockers: [] as string[],
      sourceMode: "program_group_bounds" as const,
    };
  }
  if (areaItems.length > 1) {
    return { valid: false, geometry: [] as Array<[number, number]>, blockers: ["Select one area or select connected linework. Mixed areas and linework need an explicit merge step."], sourceMode: "mixed_area" as const };
  }
  if (blockers.length) return { valid: false, geometry: [] as Array<[number, number]>, blockers, sourceMode: "invalid" as const };
  if (segments.length < 3) {
    return { valid: false, geometry: [] as Array<[number, number]>, blockers: ["Select at least three connected line segments to combine into an area."], sourceMode: "linework" as const };
  }
  const remaining = [...segments];
  const [firstStart, firstEnd] = remaining.shift()!;
  const ordered: Array<[number, number]> = [firstStart, firstEnd];
  while (remaining.length) {
    const current = ordered[ordered.length - 1];
    let bestIndex = -1;
    let bestReverse = false;
    let bestGap = Number.POSITIVE_INFINITY;
    remaining.forEach(([start, end], index) => {
      const startGap = pointDistance(current, start);
      const endGap = pointDistance(current, end);
      if (startGap < bestGap) {
        bestIndex = index;
        bestReverse = false;
        bestGap = startGap;
      }
      if (endGap < bestGap) {
        bestIndex = index;
        bestReverse = true;
        bestGap = endGap;
      }
    });
    if (bestIndex < 0 || bestGap > tolerance) {
      return { valid: false, geometry: [] as Array<[number, number]>, blockers: [`Two endpoints do not meet. Gap is ${bestGap.toFixed(2)} ft.`], sourceMode: "linework" as const };
    }
    const [start, end] = remaining.splice(bestIndex, 1)[0];
    ordered.push(bestReverse ? start : end);
  }
  const closeGap = pointDistance(ordered[ordered.length - 1], ordered[0]);
  if (closeGap > tolerance) {
    return { valid: false, geometry: [] as Array<[number, number]>, blockers: [`Shape is not closed. Final gap is ${closeGap.toFixed(2)} ft.`], sourceMode: "linework" as const };
  }
  const loop = ordered.slice(0, -1);
  if (loop.length < 3) {
    return { valid: false, geometry: [] as Array<[number, number]>, blockers: ["Selected linework does not form an area."], sourceMode: "linework" as const };
  }
  return { valid: true, geometry: loop, blockers: [] as string[], sourceMode: "linework" as const };
};

export const getCustomGeometryMetrics = (item: Pick<BuildingPlacement, "geometry" | "geometryType" | "w" | "d">) => {
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

export const formatDraftMeasure = (value: number, unit: "ft" | "sf" | "deg") => {
  if (!Number.isFinite(value)) return `0 ${unit}`;
  const rounded = Math.abs(value) >= 100 ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded.toLocaleString()} ${unit}`;
};

export const isAreaLikeDraftObject = (item: Pick<BuildingPlacement, "geometryType" | "type">) =>
  item.geometryType === "polygon" ||
  item.geometryType === "rect" ||
  item.type === "site" ||
  item.type === "office_building" ||
  item.type === "retail_building" ||
  item.type === "multifamily_building" ||
  item.type === "industrial_building" ||
  item.type === "parking" ||
  item.type === "basin" ||
  item.type === "amenity" ||
  item.type === "open_space" ||
  item.type === "lot_block";

export const getDraftObjectMeasurement = (item: BuildingPlacement) => {
  const geometry = normalizeGeometryPoints(item.geometry);
  const bounds = geometry?.length
    ? getGeometryBounds(geometry)
    : {
        minX: item.x ?? 0,
        maxX: (item.x ?? 0) + item.w,
        minY: item.y ?? 0,
        maxY: (item.y ?? 0) + item.d,
        width: item.w,
        depth: item.d,
      };
  const hasClosedGeometry = item.geometryType === "polygon" || item.geometryType === "rect";
  const areaSf = geometry?.length && hasClosedGeometry
    ? getPolygonArea(geometry)
    : isAreaLikeDraftObject(item)
      ? Math.max(0, item.w * item.d)
      : 0;
  const lengthFt = geometry?.length
    ? getGeometryLength(geometry, hasClosedGeometry)
    : item.geometryType === "polyline" || item.type === "driveway" || item.type === "road" || item.type === "sidewalk" || item.type === "utility_corridor"
      ? Math.max(item.w, item.d)
      : 0;
  return {
    id: item.id,
    label: item.label,
    typeLabel: SITE_OBJECT_CATALOG[item.type ?? "custom"]?.label ?? toReadableLabel(item.type ?? "custom"),
    lengthFt,
    areaSf,
    widthFt: Math.max(0, bounds.width || item.w),
    depthFt: Math.max(0, bounds.depth || item.d),
    minX: bounds.minX,
    minY: bounds.minY,
    maxX: bounds.maxX,
    maxY: bounds.maxY,
    rotationDeg: item.rotation ?? 0,
  };
};

export type DraftObjectMeasurement = ReturnType<typeof getDraftObjectMeasurement>;

export type DraftObjectMeasurementSummary = {
  count: number;
  totalLengthFt: number;
  totalAreaSf: number;
  widthFt: number;
  depthFt: number;
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
};

export type DraftObjectLayerSummary = {
  type: SiteObjectType;
  label: string;
  count: number;
  hiddenCount: number;
  lockedCount: number;
  allHidden: boolean;
  allLocked: boolean;
};

export const summarizeDraftObjectMeasurements = (
  measurements: DraftObjectMeasurement[],
): DraftObjectMeasurementSummary | null => {
  if (!measurements.length) return null;
  const minX = Math.min(...measurements.map((item) => item.minX));
  const minY = Math.min(...measurements.map((item) => item.minY));
  const maxX = Math.max(...measurements.map((item) => item.maxX));
  const maxY = Math.max(...measurements.map((item) => item.maxY));
  return {
    count: measurements.length,
    totalLengthFt: measurements.reduce((sum, item) => sum + item.lengthFt, 0),
    totalAreaSf: measurements.reduce((sum, item) => sum + item.areaSf, 0),
    widthFt: Math.max(0, maxX - minX),
    depthFt: Math.max(0, maxY - minY),
    minX,
    minY,
    maxX,
    maxY,
  };
};

export const buildObjectManagerTypes = (placements: BuildingPlacement[]) =>
  Array.from(new Set(placements.map((item) => getObjectDisplayType(item)))).sort();

export const buildObjectManagerLayerRows = (placements: BuildingPlacement[]): DraftObjectLayerSummary[] =>
  Object.entries(
    placements
      .filter((item) => item.type && item.type !== "site")
      .reduce<Record<string, BuildingPlacement[]>>((acc, item) => {
        const key = item.type ?? "custom";
        acc[key] = [...(acc[key] ?? []), item];
        return acc;
      }, {}),
  )
    .map(([type, objects]) => {
      const hiddenCount = objects.filter((item) => Boolean(item.meta?.ui_hidden)).length;
      const lockedCount = objects.filter((item) => Boolean(item.locked)).length;
      return {
        type: type as SiteObjectType,
        label: SITE_OBJECT_CATALOG[type as SiteObjectType]?.label ?? toReadableLabel(type),
        count: objects.length,
        hiddenCount,
        lockedCount,
        allHidden: hiddenCount === objects.length,
        allLocked: lockedCount === objects.length,
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label));

export const buildCustomGeometryMeta = (
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
      "Stored as user-authored project geometry for engineer review and passed to Generate as review context when present.",
  };
};

export const isFinitePoint = (point: unknown): point is [number, number] =>
  Array.isArray(point) &&
  typeof point[0] === "number" &&
  typeof point[1] === "number" &&
  Number.isFinite(point[0]) &&
  Number.isFinite(point[1]);

export const pointsMatch = (a?: [number, number], b?: [number, number]) =>
  Boolean(a && b && Math.abs(a[0] - b[0]) < 0.0001 && Math.abs(a[1] - b[1]) < 0.0001);

export const closeAreaGeometry = (geometry: Array<[number, number]>) => {
  if (!geometry.length || pointsMatch(geometry[0], geometry[geometry.length - 1])) return geometry;
  return [...geometry, geometry[0]];
};

export const getMinimumCanonicalVertices = (geometryType: CustomGeometryMode) => {
  if (geometryType === "point") return 1;
  if (geometryType === "polyline") return 2;
  if (geometryType === "polygon") return 4;
  return 5;
};

export const validateCanonicalGeometryHandoffV1 = (
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
  if (!handoff.source.trim()) blockers.push("source is required");
  if (!handoff.confidence.trim()) blockers.push("confidence is required");
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

export const buildCanonicalGeometryHandoffV1 = (
  item: BuildingPlacement,
  fallbackUnits: string,
): CanonicalGeometryHandoffV1 | null => {
  const metadata = item.meta ?? {};
  const itemType = item.type ?? "custom";
  const itemX = item.x ?? 0;
  const itemY = item.y ?? 0;
  const areaTypes = new Set<SiteObjectType>([
    "setback_zone", "no_build_zone", "building", "retail_building", "multifamily_building",
    "industrial_building", "office_building", "pad", "pool", "amenity", "open_space",
    "landscape", "parking", "basin", "lot_block",
  ]);
  const pathTypes = new Set<SiteObjectType>(["entrance", "driveway", "road", "sidewalk", "utility_corridor", "bridge"]);
  const pointTypes = new Set<SiteObjectType>(["outfall", "inlet", "manhole", "hydrant"]);
  const inferredGeometryType: CustomGeometryMode | undefined = isCustomGeometryMode(item.geometryType)
    ? item.geometryType
    : areaTypes.has(itemType)
      ? "polygon"
      : pathTypes.has(itemType)
        ? "polyline"
        : pointTypes.has(itemType)
          ? "point"
          : undefined;
  if (itemType === "site" || !inferredGeometryType) return null;
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
  const acceptedSourceCandidate = metadata.acceptance_status === "accepted" || metadata.accepted_source_candidate === true;
  const source = item.source || "manual_drawn";
  const sourceIsDetected = source === "detected_from_gis" || source === "detected_from_image" || source === "inferred";
  if (sourceIsDetected && !acceptedSourceCandidate && !item.confirmed) return null;
  const confidence =
    typeof metadata.source_confidence === "string" && metadata.source_confidence.trim()
      ? metadata.source_confidence
      : source === "manual_drawn"
        ? "user_drawn_review_required"
        : source === "user_confirmed"
          ? "user_confirmed_review_required"
          : sourceIsDetected
            ? "accepted_source_candidate_review_required"
            : "source_review_required";
  const rawGeometry = Array.isArray(item.geometry) ? item.geometry.filter(isFinitePoint) : [];
  const centerX = itemX + item.w / 2;
  const centerY = itemY + item.d / 2;
  const rotatePoint = ([x, y]: [number, number]): [number, number] => {
    const angle = ((item.rotation || 0) * Math.PI) / 180;
    if (!angle) return [x, y];
    const dx = x - centerX;
    const dy = y - centerY;
    return [centerX + dx * Math.cos(angle) - dy * Math.sin(angle), centerY + dx * Math.sin(angle) + dy * Math.cos(angle)];
  };
  const inferredGeometry: Array<[number, number]> =
    inferredGeometryType === "point"
      ? [[centerX, centerY]]
      : inferredGeometryType === "polyline"
        ? ([[itemX, centerY], [itemX + item.w, centerY]] as Array<[number, number]>).map(rotatePoint)
        : [
            [itemX, itemY] as [number, number],
            [itemX + item.w, itemY] as [number, number],
            [itemX + item.w, itemY + item.d] as [number, number],
            [itemX, itemY + item.d] as [number, number],
          ].map(rotatePoint);
  const usableGeometry = rawGeometry.length >= (inferredGeometryType === "point" ? 1 : inferredGeometryType === "polyline" ? 2 : 3)
    ? rawGeometry
    : inferredGeometry;
  const geometry = inferredGeometryType === "polygon" || inferredGeometryType === "rect"
    ? closeAreaGeometry(usableGeometry)
    : usableGeometry;
  const storedVertices = Array.isArray(metadata.vertices)
    ? (metadata.vertices as Array<{ id?: unknown }>)
    : [];
  const metrics = getCustomGeometryMetrics({
    geometry: rawGeometry.filter(isFinitePoint),
    geometryType: inferredGeometryType,
    w: item.w,
    d: item.d,
  });
  const handoffCore: Omit<CanonicalGeometryHandoffV1, "valid" | "blockers"> = {
    schema_version: "canonical_geometry_handoff_v1",
    object_id: objectId,
    geometry_id: geometryId,
    object_name: item.label,
    object_type: itemType,
    geometry_type: inferredGeometryType,
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
    source,
    confidence,
    engineering_status: "draft_review_required",
    metrics: {
      length_ft: Number(metrics.lengthFt.toFixed(2)),
      area_sf: Number(metrics.areaSf.toFixed(2)),
      width_ft: Number(metrics.widthFt.toFixed(2)),
      depth_ft: Number(metrics.depthFt.toFixed(2)),
    },
    created_at: typeof metadata.created_at === "string" ? metadata.created_at : undefined,
    updated_at: typeof metadata.updated_at === "string" ? metadata.updated_at : undefined,
    source_ui_mode: sourceIsDetected ? "candidate_review_acceptance" : "canvas_draw",
    canonical_object_type: typeof metadata.canonical_object_type === "string" ? metadata.canonical_object_type : itemType,
    creation_method: typeof metadata.semantic_object_model === "string"
      ? "semantic_conversion"
      : sourceIsDetected
        ? "accepted_detected_candidate"
        : "canvas_object",
    engineering_attributes: {
      ...(metadata.engineering_attributes && typeof metadata.engineering_attributes === "object"
        ? metadata.engineering_attributes as Record<string, unknown>
        : {}),
      ...(typeof item.h === "number" ? { height_ft: item.h } : {}),
      ...(typeof item.stallCount === "number" ? { stall_count: item.stallCount } : {}),
      ...(typeof metadata.footprint_area_sf === "number" ? { footprint_area_sf: metadata.footprint_area_sf } : {}),
      ...(item.use ? { use_type: item.use } : {}),
    },
    affected_systems: Array.isArray(metadata.affected_systems)
      ? metadata.affected_systems.filter((value): value is string => typeof value === "string")
      : item.systemDependencies,
    relationships: Array.isArray(metadata.relationships)
      ? metadata.relationships.filter((value): value is Record<string, unknown> => Boolean(value) && typeof value === "object")
      : [],
  };
  const blockers = validateCanonicalGeometryHandoffV1(handoffCore);
  return {
    ...handoffCore,
    valid: blockers.length === 0,
    blockers,
  };
};

export const formatCustomGeometryMetrics = (item: BuildingPlacement) => {
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

export const getObjectDisplayType = (item: BuildingPlacement) =>
  SITE_OBJECT_CATALOG[item.type ?? "custom"]?.label ?? "Object";

export const getObjectLayerLabel = (item: BuildingPlacement) => {
  const rawLayer =
    typeof item.meta?.layer === "string"
      ? item.meta.layer
      : typeof item.meta?.cad_layer === "string"
        ? item.meta.cad_layer
        : SITE_OBJECT_CATALOG[item.type ?? "custom"]?.category;
  return rawLayer ? String(rawLayer).replace(/_/g, " ") : "draft";
};

export const getObjectSourceLabel = (item: BuildingPlacement) => {
  if (item.meta?.ai_realism_artifact) return "AI realism visualization only";
  if (item.source === "manual_drawn") return "manual drawn";
  if (item.source === "generated" || item.generated) return "generated draft";
  if (item.source === "detected_from_gis") return "GIS review candidate";
  if (item.source === "detected_from_image") return "image/PDF review candidate";
  if (item.source === "inferred") return "inferred review candidate";
  if (item.source === "user_confirmed") return "user confirmed draft";
  return "user draft";
};

export const getObjectReviewLabel = (item: BuildingPlacement) => {
  if (item.type === "site") return "locked site boundary";
  if (item.meta?.ai_realism_artifact) return "visualization only";
  if (item.locked) return "locked";
  if (item.source === "detected_from_gis" || item.source === "detected_from_image" || item.source === "inferred") {
    return "source review required";
  }
  if (item.type === "custom" || item.source === "manual_drawn") return "draft geometry review required";
  return item.placed ? "draft placed" : "pending placement";
};

export const getObjectDimensionsLabel = (item: BuildingPlacement) => {
  if (item.type === "custom") return formatCustomGeometryMetrics(item);
  const pieces = [`${Math.round(item.w)} ft x ${Math.round(item.d)} ft`];
  if (typeof item.h === "number" && item.h > 0) pieces.push(`${Math.round(item.h)} ft high`);
  if (item.type === "parking" && typeof item.stallCount === "number") {
    pieces.push(`${Math.round(item.stallCount)} stalls`);
  }
  return pieces.join(" · ");
};

export const getObjectEditBlocker = (item: BuildingPlacement, action: "rename" | "style" | "type" | "hide" | "delete" | "copy" | "transform" | "resize") => {
  if (item.type === "site") {
    return `${action} needs input: locked site boundary is controlled from Setup.`;
  }
  if (item.meta?.ai_realism_artifact) {
    return `${action} needs input: AI realism artifacts are visualization only, not editable site evidence.`;
  }
  if (action === "delete" && item.capabilities?.deletable === false) {
    return `Delete needs input: ${item.label} is source-only or required project evidence.`;
  }
  if ((action === "rename" || action === "style" || action === "type") && item.locked) {
    return `${action} needs input: unlock ${item.label} before editing metadata.`;
  }
  if (action === "delete" && item.locked) {
    return `Delete needs input: unlock ${item.label} before deleting it.`;
  }
  if ((action === "copy" || action === "transform" || action === "resize") && item.locked) {
    return `${action} needs input: unlock ${item.label} before changing draft geometry.`;
  }
  return null;
};

export const formatCalmActionMessage = (message: string) =>
  message
    .replace(/\bblocked:/gi, "needs input:")
    .replace(/\bblocked\b/gi, "needs input")
    .replace(/\bBlocked\b/g, "Needs input")
    .replace(/\bfailed\b/gi, "could not complete")
    .replace(/\bInvalid\b/g, "Needs correction")
    .replace(/\binvalid\b/g, "needs correction")
    .replace(/\bStale\b/g, "Update recommended")
    .replace(/\bstale\b/g, "update recommended");

export function CustomGeometryHandoffDetails({
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
      <p>Handoff: canonical_geometry_handoff_v1 · {handoff.valid ? "valid draft" : "needs review"}</p>
      <p>Object ID: {handoff.object_id}</p>
      <p>Geometry ID: {handoff.geometry_id}</p>
      <p>Type: {handoff.geometry_type} · Name: {handoff.object_name}</p>
      <p>{formatCustomGeometryMetrics(item)}</p>
      <p>Source: manual_drawn · UI: canvas_draw</p>
      <p>Confidence: user_drawn_review_required</p>
      <p>Engineering status: draft_review_required</p>
      {!handoff.valid ? (
        <p className="text-amber-600">Handoff needs review: {blockerText}</p>
      ) : null}
    </div>
  );
}
