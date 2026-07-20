import type {
  BuildingPlacement,
  CadEntityModelEntityV1,
  PlanMeta,
  Preview3DItem,
  SourceConfidenceEntry,
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

export function buildCadEntityPreview(
  currentPlanMeta: PlanMeta,
  sourceConfidenceByObjectId: Map<string, SourceConfidenceEntry>,
): CadEntityPreview {
  const model = currentPlanMeta.cad_entity_model_v1;
  const entities = Array.isArray(model?.entities) ? model.entities : [];
  const layerNames = new Map(
    (model?.layers ?? []).map((layer) => [
      String(layer.id || layer.layer_id || ""),
      String(layer.name || layer.id || layer.layer_id || "C-DRAFT"),
    ]),
  );
  const validationBlockersByEntity = new Map<string, string[]>();
  (model?.validation?.blockers ?? []).forEach((blocker) => {
    if (typeof blocker === "string") return;
    const entityId = String(blocker.entity_id || "");
    if (!entityId) return;
    const list = validationBlockersByEntity.get(entityId) ?? [];
    if (blocker.reason) list.push(String(blocker.reason));
    validationBlockersByEntity.set(entityId, list);
  });
  const objects: BuildingPlacement[] = [];
  const items3D: Preview3DItem[] = [];
  const sourceIds = new Set<string>();
  const linkedIds = new Set<string>();

  entities.forEach((entity, index) => {
    const entityId = String(entity.id || `cad-entity-${index + 1}`);
    sourceIds.add(entityId);
    const entityType = String(entity.type || "unknown").toLowerCase();
    const layerName = cadLayerName(entity, layerNames);
    const linkedObjectId = String(entity.linked_object_id || entity.canonical_geometry_handoff?.object_id || "");
    if (linkedObjectId) linkedIds.add(linkedObjectId);
    const geometryPreview = cadEntityGeometryPreview(entity);
    const bboxRaw = entity.bounding_box ?? model?.entity_bounding_boxes?.[entityId];
    const bbox =
      bboxRaw && Number.isFinite(Number(bboxRaw.min_x)) && Number.isFinite(Number(bboxRaw.min_y))
        ? {
            minX: Number(bboxRaw.min_x),
            minY: Number(bboxRaw.min_y),
            maxX: Number(bboxRaw.max_x ?? Number(bboxRaw.min_x) + Number(bboxRaw.width ?? 1)),
            maxY: Number(bboxRaw.max_y ?? Number(bboxRaw.min_y) + Number(bboxRaw.height ?? 1)),
          }
        : boundsFromCadPoints(geometryPreview.points);
    if (!bbox) return;
    const unsupported = !CAD_PREVIEW_SUPPORTED_TYPES.has(entityType);
    const blockers = cadEntityReviewBlockers(entity, validationBlockersByEntity.get(entityId) ?? [], unsupported);
    const w = Math.max(1, bbox.maxX - bbox.minX);
    const d = Math.max(1, bbox.maxY - bbox.minY);
    const label = String(entity.label || entity.name || entity.geometry?.text || entityType.replace(/_/g, " ") || "Draft entity");
    const siteType = cadLayerToSiteType(layerName, entityType);
    const previewLayer = cadPreviewLayer(layerName, entityType);
    const sourceConfidence = String(entity.source_confidence || sourceConfidenceByObjectId.get(linkedObjectId)?.confidence_band || "review required");
    const sharedMeta = {
      cad_entity_id: entityId,
      cad_entity_type: entityType,
      cad_layer: layerName,
      cad_source_confidence: sourceConfidence,
      cad_review_status: entity.review_status || "draft_review_required",
      cad_validation_status: entity.validation_status,
      cad_review_blockers: blockers,
      linked_object_id: linkedObjectId || undefined,
      source_entity_id: entityId,
      unsupported_entity_placeholder: unsupported,
      review_only: true,
      construction_release_allowed: false,
      source_note: "Persistent draft entity preview; review/communication only.",
    };
    objects.push({
      id: entityId,
      label,
      type: siteType,
      x: bbox.minX,
      y: bbox.minY,
      w,
      d,
      source: "manual_drawn",
      generated: false,
      confidence: undefined,
      geometryType:
        geometryPreview.geometryType === "circle" ? "point" : geometryPreview.geometryType,
      geometry: geometryPreview.points.map((point) => [point.x, point.y] as [number, number]),
      capabilities: { movable: false, resizable: false, rotatable: false, deletable: false },
      meta: {
        ...sharedMeta,
        cad_radius: geometryPreview.radius,
        cad_symbol: entityType === "block_reference" || entityType === "symbol" ? "utility_marker" : undefined,
        cad_dimension_label: entityType === "dimension" ? label : undefined,
      },
      locked: true,
      placed: true,
    });
    items3D.push({
      id: entityId,
      x: bbox.minX,
      y: bbox.minY,
      w,
      h: d,
      height: previewLayer === "BUILDING" ? 18 : previewLayer === "DRAINAGE" ? 2.5 : previewLayer === "UTILITY" ? 1.5 : 0.8,
      z: previewLayer === "DRAINAGE" ? -0.4 : 0,
      color: previewLayer === "UTILITY" ? "#e9d5ff" : previewLayer === "DRAINAGE" ? "#bfdbfe" : previewLayer === "ROAD" ? "#cbd5e1" : "#e5e7eb",
      label,
      layer: previewLayer,
      source: String(entity.source || "cad_entity_model_v1"),
      confidence: sourceConfidence,
      blockers,
      geometryType: geometryPreview.geometryType,
      geometry: geometryPreview.points.map((point) => [point.x, point.y] as [number, number]),
      radius: geometryPreview.radius,
      entityType,
      linkedObjectId: linkedObjectId || undefined,
      sourceEntityId: entityId,
      unsupported,
    });
  });

  return { objects, items3D, sourceIds, linkedIds };
}
