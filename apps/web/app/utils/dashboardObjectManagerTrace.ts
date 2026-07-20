import type { BuildingPlacement } from "../types";
import type { DraftUndoAction } from "./dashboardTypes";

export function getVisibleEditableDraftObjectIds(buildingPlacements: BuildingPlacement[]): string[] {
  return buildingPlacements
    .filter((item) => {
      if (item.type === "site") return false;
      if (item.meta?.ui_hidden) return false;
      if (item.meta?.ai_realism_artifact) return false;
      if (item.capabilities?.deletable === false) return false;
      return true;
    })
    .map((item) => item.id);
}

export function formatVisibleDraftSelectionMessage(count: number): string {
  return `Selected ${count} visible draft object${count === 1 ? "" : "s"}.`;
}

export function invertVisibleDraftSelection({
  visibleDraftIds,
  selectedObjectIds,
}: {
  visibleDraftIds: string[];
  selectedObjectIds: string[];
}): { nextSelection: string[]; message: string } {
  const selectedIdSet = new Set(selectedObjectIds);
  const nextSelection = visibleDraftIds.filter((id) => !selectedIdSet.has(id));
  return {
    nextSelection,
    message: nextSelection.length
      ? `Inverted selection to ${nextSelection.length} visible draft object${nextSelection.length === 1 ? "" : "s"}.`
      : "Inverted selection: no visible draft objects remain selected.",
  };
}

export function cloneBuildingPlacementForUndo(item: BuildingPlacement): BuildingPlacement {
  return {
    ...item,
    geometry: item.geometry?.map(([x, y]) => [x, y] as [number, number]),
    meta: item.meta ? { ...item.meta } : item.meta,
    capabilities: item.capabilities ? { ...item.capabilities } : item.capabilities,
  };
}

export function cloneBuildingPlacementWithUpdatesForUndo(
  item: BuildingPlacement,
  updates: Partial<BuildingPlacement>,
): BuildingPlacement {
  return cloneBuildingPlacementForUndo({
    ...item,
    ...updates,
    meta: updates.meta ? { ...(item.meta ?? {}), ...updates.meta } : item.meta,
    capabilities: updates.capabilities
      ? { ...(item.capabilities ?? {}), ...updates.capabilities }
      : item.capabilities,
  });
}

export function createDraftCopyWithTrace({
  item,
  buildingPlacements,
  idPrefix,
  label,
  dx,
  dy,
  source,
  extraMeta,
}: {
  item: BuildingPlacement;
  buildingPlacements: BuildingPlacement[];
  idPrefix: string;
  label: string;
  dx: number;
  dy: number;
  source: string;
  extraMeta?: Record<string, unknown>;
}): { visible: BuildingPlacement; created: BuildingPlacement[] } {
  const nextType = item.type ?? "custom";
  const nextId = `${nextType}-${idPrefix}-${Math.random().toString(36).slice(2, 8)}`;
  const sourceIds = Array.isArray(item.meta?.combined_from_object_ids)
    ? item.meta.combined_from_object_ids.map((sourceId) => String(sourceId)).filter(Boolean)
    : [];
  const sourceItems = sourceIds
    .map((sourceId) => buildingPlacements.find((candidate) => candidate.id === sourceId))
    .filter((candidate): candidate is BuildingPlacement => Boolean(candidate));
  const copiedSourceItems = sourceItems.map((sourceItem, sourceIndex): BuildingPlacement => {
    const copiedSourceId = `${nextId}-source-${sourceIndex}-${Math.random().toString(36).slice(2, 8)}`;
    return {
      ...sourceItem,
      id: copiedSourceId,
      label: `${sourceItem.label} ${label.includes("Array") ? "Array Source" : "Copy Source"}`,
      x: (sourceItem.x ?? 0) + dx,
      y: (sourceItem.y ?? 0) + dy,
      source: "manual_drawn",
      generated: false,
      locked: false,
      placed: true,
      geometry: sourceItem.geometry?.map(([x, y]) => [x + dx, y + dy]),
      capabilities: {
        movable: true,
        resizable: sourceItem.capabilities?.resizable ?? true,
        rotatable: sourceItem.capabilities?.rotatable ?? true,
        deletable: true,
      },
      meta: {
        ...(sourceItem.meta ?? {}),
        ui_hidden: true,
        source: `${source}_source`,
        copied_from_object_id: sourceItem.id,
        copied_from_label: sourceItem.label,
        combined_into_object_id: nextId,
        combined_into_label: label,
        review_status: "engineer_review_required",
        engineering_status: "draft_review_required",
        handoff_status: "draft_review_required",
        construction_release_allowed: false,
        ...(extraMeta ?? {}),
      },
    };
  });
  const visible: BuildingPlacement = {
    ...item,
    id: nextId,
    label,
    x: (item.x ?? 0) + dx,
    y: (item.y ?? 0) + dy,
    source: "manual_drawn",
    generated: false,
    locked: false,
    placed: true,
    geometry: item.geometry?.map(([x, y]) => [x + dx, y + dy]),
    capabilities: {
      movable: true,
      resizable: item.capabilities?.resizable ?? true,
      rotatable: item.capabilities?.rotatable ?? true,
      deletable: true,
    },
    meta: {
      ...(item.meta ?? {}),
      ui_hidden: false,
      source,
      copied_from_object_id: item.id,
      copied_from_label: item.label,
      copied_combined_from_object_ids: sourceIds,
      copied_combined_from_labels: sourceItems.map((sourceItem) => sourceItem.label),
      combined_from_object_ids: copiedSourceItems.map((sourceItem) => sourceItem.id),
      combined_from_labels: copiedSourceItems.map((sourceItem) => sourceItem.label),
      combined_source_count: copiedSourceItems.length || undefined,
      review_status: "engineer_review_required",
      engineering_status: "draft_review_required",
      handoff_status: "draft_review_required",
      construction_release_allowed: false,
      ...(extraMeta ?? {}),
    },
  };
  return { visible, created: [...copiedSourceItems, visible] };
}

export function buildSyncedCombinedSourceTraces({
  target,
  nextObject,
  updates,
  buildingPlacements,
}: {
  target: BuildingPlacement;
  nextObject: BuildingPlacement;
  updates: Partial<BuildingPlacement>;
  buildingPlacements: BuildingPlacement[];
}): BuildingPlacement[] {
  const combinedSourceIds = Array.isArray(target.meta?.combined_from_object_ids)
    ? target.meta.combined_from_object_ids.map((sourceId) => String(sourceId)).filter(Boolean)
    : [];
  if (!combinedSourceIds.length) return [];
  const sourceObjects = buildingPlacements.filter((item) => combinedSourceIds.includes(item.id));
  if (!sourceObjects.length) return [];
  const groupGeometryChanged =
    typeof updates.x === "number" ||
    typeof updates.y === "number" ||
    typeof updates.w === "number" ||
    typeof updates.d === "number" ||
    typeof updates.rotation === "number" ||
    Array.isArray(updates.geometry);
  const nextGroupLabel = nextObject.label || target.label;
  const nextGroupType = nextObject.type ?? target.type ?? "custom";
  const nextGroupColor = nextObject.meta?.ui_color ?? nextObject.meta?.color ?? target.meta?.ui_color ?? target.meta?.color;
  const groupOriginX = target.x ?? 0;
  const groupOriginY = target.y ?? 0;
  const nextGroupOriginX = nextObject.x ?? groupOriginX;
  const nextGroupOriginY = nextObject.y ?? groupOriginY;
  const groupScaleX = target.w > 0 && nextObject.w > 0 ? nextObject.w / target.w : 1;
  const groupScaleY = target.d > 0 && nextObject.d > 0 ? nextObject.d / target.d : 1;
  const groupCenterX = groupOriginX + target.w / 2;
  const groupCenterY = groupOriginY + target.d / 2;
  const nextGroupCenterX = nextGroupOriginX + nextObject.w / 2;
  const nextGroupCenterY = nextGroupOriginY + nextObject.d / 2;
  const rotationDeltaRadians = ((((nextObject.rotation ?? 0) - (target.rotation ?? 0)) % 360) * Math.PI) / 180;
  const cosDelta = Math.cos(rotationDeltaRadians);
  const sinDelta = Math.sin(rotationDeltaRadians);
  const transformPoint = ([px, py]: [number, number]): [number, number] => [
    nextGroupCenterX + ((px - groupCenterX) * groupScaleX) * cosDelta - ((py - groupCenterY) * groupScaleY) * sinDelta,
    nextGroupCenterY + ((px - groupCenterX) * groupScaleX) * sinDelta + ((py - groupCenterY) * groupScaleY) * cosDelta,
  ];
  return sourceObjects.map((sourceItem) => {
    const sourceCorners: Array<[number, number]> = [
      [sourceItem.x ?? 0, sourceItem.y ?? 0],
      [(sourceItem.x ?? 0) + sourceItem.w, sourceItem.y ?? 0],
      [(sourceItem.x ?? 0) + sourceItem.w, (sourceItem.y ?? 0) + sourceItem.d],
      [sourceItem.x ?? 0, (sourceItem.y ?? 0) + sourceItem.d],
    ];
    const transformedGeometry = sourceItem.geometry?.map((point) =>
      groupGeometryChanged ? transformPoint(point) : ([point[0], point[1]] as [number, number]),
    );
    const boundsPoints = groupGeometryChanged
      ? (transformedGeometry?.length ? transformedGeometry : sourceCorners.map(transformPoint))
      : sourceCorners;
    const boundsXs = boundsPoints.map(([x]) => x);
    const boundsYs = boundsPoints.map(([, y]) => y);
    const minSourceX = Math.min(...boundsXs);
    const maxSourceX = Math.max(...boundsXs);
    const minSourceY = Math.min(...boundsYs);
    const maxSourceY = Math.max(...boundsYs);
    return cloneBuildingPlacementForUndo({
      ...sourceItem,
      x: groupGeometryChanged ? minSourceX : sourceItem.x,
      y: groupGeometryChanged ? minSourceY : sourceItem.y,
      w: groupGeometryChanged ? Math.max(1, maxSourceX - minSourceX) : sourceItem.w,
      d: groupGeometryChanged ? Math.max(1, maxSourceY - minSourceY) : sourceItem.d,
      rotation: groupGeometryChanged
        ? ((sourceItem.rotation ?? 0) + ((nextObject.rotation ?? 0) - (target.rotation ?? 0))) % 360
        : sourceItem.rotation,
      geometry: transformedGeometry,
      capabilities: sourceItem.capabilities ? { ...sourceItem.capabilities } : sourceItem.capabilities,
      locked: typeof updates.locked === "boolean" ? updates.locked : sourceItem.locked,
      meta: {
        ...(sourceItem.meta ?? {}),
        combined_into_object_id: target.id,
        combined_into_label: nextGroupLabel,
        combined_into_type: nextGroupType,
        combined_trace_synced_at: new Date().toISOString(),
        ...(typeof updates.locked === "boolean" ? { combined_into_locked: updates.locked } : {}),
        ...(groupGeometryChanged ? { combined_transform_synced: true } : {}),
        ...(typeof nextGroupColor === "string" ? { combined_into_color: nextGroupColor } : {}),
      },
    });
  });
}

export function createTraceAwareBulkUpdate({
  entries,
  label,
  buildingPlacements,
}: {
  entries: Array<{ item: BuildingPlacement; updates: Partial<BuildingPlacement> }>;
  label: string;
  buildingPlacements: BuildingPlacement[];
}): { undo: DraftUndoAction; afterById: Map<string, BuildingPlacement> } {
  const beforeById = new Map<string, BuildingPlacement>();
  const afterById = new Map<string, BuildingPlacement>();
  entries.forEach(({ item, updates }) => {
    const nextObject = cloneBuildingPlacementWithUpdatesForUndo(item, updates);
    beforeById.set(item.id, cloneBuildingPlacementForUndo(item));
    afterById.set(item.id, nextObject);
    const sourceIds = Array.isArray(item.meta?.combined_from_object_ids)
      ? item.meta.combined_from_object_ids.map((sourceId) => String(sourceId)).filter(Boolean)
      : [];
    sourceIds.forEach((sourceId) => {
      const sourceItem = buildingPlacements.find((candidate) => candidate.id === sourceId);
      if (sourceItem) beforeById.set(sourceItem.id, cloneBuildingPlacementForUndo(sourceItem));
    });
    buildSyncedCombinedSourceTraces({ target: item, nextObject, updates, buildingPlacements }).forEach((sourceItem) => {
      afterById.set(sourceItem.id, sourceItem);
    });
  });
  return {
    undo: {
      action: "bulk_update",
      before: Array.from(beforeById.values()),
      after: Array.from(afterById.values()),
      label,
    },
    afterById,
  };
}
