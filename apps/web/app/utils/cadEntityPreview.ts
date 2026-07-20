import type {
  BuildingPlacement,
  CadEntityModelEntityV1,
  Preview3DItem,
  SiteObjectType,
} from "../types";

export type CadEntityPoint = { x: number; y: number };

export type CadEntityPreview = {
  objects: BuildingPlacement[];
  items3D: Preview3DItem[];
  sourceIds: Set<string>;
  linkedIds: Set<string>;
};

export const CAD_PREVIEW_SUPPORTED_TYPES = new Set([
  "line",
  "polyline",
  "polygon",
  "rectangle",
  "circle",
  "text",
  "dimension",
  "block_reference",
  "symbol",
]);

export const readCadPoint = (value: unknown): CadEntityPoint | null => {
  if (Array.isArray(value) && value.length >= 2) {
    const x = Number(value[0]);
    const y = Number(value[1]);
    return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const x = Number(record.x);
    const y = Number(record.y);
    return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
  }
  return null;
};

const readCadPoints = (value: unknown) =>
  (Array.isArray(value) ? value : [])
    .map(readCadPoint)
    .filter((point): point is CadEntityPoint => Boolean(point));

export const boundsFromCadPoints = (points: CadEntityPoint[]) => {
  if (!points.length) return null;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
};

export const cadEntityGeometryPreview = (entity: CadEntityModelEntityV1) => {
  const geometry = entity.geometry ?? {};
  const type = String(entity.type || "").toLowerCase();
  if (type === "line") {
    const points = [readCadPoint(geometry.start), readCadPoint(geometry.end)].filter((point): point is CadEntityPoint => Boolean(point));
    return { geometryType: "polyline" as const, points, radius: undefined };
  }
  if (type === "polyline" || type === "polygon") {
    return {
      geometryType: type === "polygon" ? ("polygon" as const) : ("polyline" as const),
      points: readCadPoints(geometry.points ?? geometry.vertices),
      radius: undefined,
    };
  }
  if (type === "rectangle") {
    const origin = readCadPoint(geometry.origin ?? (geometry as Record<string, unknown>).min);
    const width = Number(geometry.width);
    const height = Number(geometry.height);
    const points = origin && Number.isFinite(width) && Number.isFinite(height)
      ? [
          origin,
          { x: origin.x + width, y: origin.y },
          { x: origin.x + width, y: origin.y + height },
          { x: origin.x, y: origin.y + height },
        ]
      : readCadPoints(geometry.points ?? geometry.vertices);
    return { geometryType: "polygon" as const, points, radius: undefined };
  }
  if (type === "circle") {
    const center = readCadPoint(geometry.center);
    const radius = Number(geometry.radius);
    return { geometryType: "circle" as const, points: center ? [center] : [], radius: Number.isFinite(radius) ? Math.max(radius, 0) : undefined };
  }
  if (type === "dimension") {
    const points = readCadPoints(geometry.points).length >= 2
      ? readCadPoints(geometry.points)
      : [readCadPoint(geometry.start), readCadPoint(geometry.end)].filter((point): point is CadEntityPoint => Boolean(point));
    return { geometryType: "polyline" as const, points, radius: undefined };
  }
  const insert = readCadPoint(geometry.insert ?? geometry.position ?? geometry.origin);
  return { geometryType: "point" as const, points: insert ? [insert] : [], radius: undefined };
};

export const cadLayerName = (entity: CadEntityModelEntityV1, layerNames: Map<string, string>) => {
  const layerId = String(entity.layer_id || "layer_draft");
  return layerNames.get(layerId) || layerId || "C-DRAFT";
};

export const cadPreviewLayer = (layer: string, entityType: string) => {
  const normalized = layer.toUpperCase();
  if (/BUILD|PAD/.test(normalized)) return "BUILDING";
  if (/PARK/.test(normalized)) return "PARKING";
  if (/ROAD|DRIVE|PAVE/.test(normalized)) return "ROAD";
  if (/SIDEWALK|WALK/.test(normalized)) return "SIDEWALK";
  if (/DRAIN|STORM|BASIN|POND|INLET|OUTFALL/.test(normalized)) return "DRAINAGE";
  if (/UTIL|WATER|WATR|SAN|HYDRANT|MANHOLE|VALVE/.test(normalized)) return "UTILITY";
  if (/LOT|EASE|SETBACK|CONSTRAINT/.test(normalized)) return "CONSTRAINT";
  if (entityType === "text" || entityType === "dimension") return "CONSTRAINT";
  return "OBJECT";
};

export const cadLayerToSiteType = (layer: string, entityType: string): SiteObjectType => {
  const previewLayer = cadPreviewLayer(layer, entityType);
  if (previewLayer === "BUILDING") return "building";
  if (previewLayer === "PARKING") return "parking";
  if (previewLayer === "ROAD") return "road";
  if (previewLayer === "SIDEWALK") return "sidewalk";
  if (previewLayer === "DRAINAGE") return "basin";
  if (previewLayer === "UTILITY") return "utility_corridor";
  if (previewLayer === "CONSTRAINT") return "setback_zone";
  return "custom";
};

export const cadEntityReviewBlockers = (entity: CadEntityModelEntityV1, modelBlockers: string[], unsupported: boolean) =>
  Array.from(
    new Set([
      ...(unsupported ? [`unsupported_entity_placeholder:${entity.type || "unknown"}`] : []),
      ...(Array.isArray(entity.validation_blockers) ? entity.validation_blockers : []),
      ...(Array.isArray(entity.blockers) ? entity.blockers : []),
      ...modelBlockers,
      ...(entity.dirty ? ["cad_entity_dirty_review_required"] : []),
      ...(entity.stale ? ["cad_entity_stale_review_required"] : []),
      ...(entity.source_confidence ? [`source_confidence:${entity.source_confidence}`] : ["source_confidence:missing"]),
    ]),
  );
