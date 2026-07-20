import type { BuildingPlacement } from "../types";
import type { DraftUndoAction } from "./dashboardTypes";
import { getGeometryBounds, normalizeGeometryPoints } from "./objectGeometry";

export type ObjectManagerBounds = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  width: number;
  depth: number;
};

export type ObjectManagerLayoutAction = "align_left" | "align_top" | "distribute_x" | "distribute_y";
export type ObjectManagerUpdateEntry = {
  item: BuildingPlacement;
  updates: Partial<BuildingPlacement>;
};

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

export function partitionObjectManagerTargets({
  targets,
  isEditable,
}: {
  targets: BuildingPlacement[];
  isEditable: (item: BuildingPlacement) => boolean;
}): { editable: BuildingPlacement[]; blockedCount: number } {
  const editable = targets.filter(isEditable);
  return {
    editable,
    blockedCount: targets.length - editable.length,
  };
}

export function formatObjectManagerCountMessage({
  action,
  count,
  blockedCount = 0,
  noun = "selected object",
}: {
  action: string;
  count: number;
  blockedCount?: number;
  noun?: string;
}): string {
  return `${action} ${count} ${noun}${count === 1 ? "" : "s"}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
}

export function isObjectManagerCopyableDraft({
  item,
  hasCopyBlocker,
}: {
  item: BuildingPlacement;
  hasCopyBlocker: boolean;
}): boolean {
  if (hasCopyBlocker) return false;
  if (item.capabilities?.deletable === false) return false;
  if (item.generated) return false;
  if (item.source === "detected_from_gis" || item.source === "detected_from_image" || item.source === "inferred") return false;
  return true;
}

export function getObjectManagerBounds(item: BuildingPlacement): ObjectManagerBounds {
  const geometry = Array.isArray(item.geometry) ? normalizeGeometryPoints(item.geometry) : undefined;
  if (geometry?.length) return getGeometryBounds(geometry);
  return {
    minX: item.x ?? 0,
    maxX: (item.x ?? 0) + item.w,
    minY: item.y ?? 0,
    maxY: (item.y ?? 0) + item.d,
    width: item.w,
    depth: item.d,
  };
}

export function getObjectManagerBoundsRows(items: BuildingPlacement[]): Array<{
  item: BuildingPlacement;
  bounds: ObjectManagerBounds;
}> {
  return items.map((item) => ({ item, bounds: getObjectManagerBounds(item) }));
}

export function createObjectManagerLayoutUpdateEntries(
  editable: BuildingPlacement[],
  layout: ObjectManagerLayoutAction,
): ObjectManagerUpdateEntry[] {
  const objectBounds = getObjectManagerBoundsRows(editable);
  const layoutUpdates = new Map<string, Partial<BuildingPlacement>>();
  if (layout === "align_left") {
    const targetX = Math.min(...objectBounds.map(({ bounds }) => bounds.minX));
    objectBounds.forEach(({ item, bounds }) => {
      layoutUpdates.set(item.id, { x: (item.x ?? 0) + (targetX - bounds.minX) });
    });
  } else if (layout === "align_top") {
    const targetY = Math.min(...objectBounds.map(({ bounds }) => bounds.minY));
    objectBounds.forEach(({ item, bounds }) => {
      layoutUpdates.set(item.id, { y: (item.y ?? 0) + (targetY - bounds.minY) });
    });
  } else {
    const axis = layout === "distribute_x" ? "x" : "y";
    const sorted = [...objectBounds].sort((a, b) => {
      const aCenter = axis === "x"
        ? a.bounds.minX + a.bounds.width / 2
        : a.bounds.minY + a.bounds.depth / 2;
      const bCenter = axis === "x"
        ? b.bounds.minX + b.bounds.width / 2
        : b.bounds.minY + b.bounds.depth / 2;
      return aCenter - bCenter;
    });
    const centers = sorted.map(({ bounds }) =>
      axis === "x" ? bounds.minX + bounds.width / 2 : bounds.minY + bounds.depth / 2,
    );
    const first = centers[0];
    const last = centers[centers.length - 1];
    const step = sorted.length > 1 ? (last - first) / (sorted.length - 1) : 0;
    sorted.forEach(({ item, bounds }, index) => {
      const targetCenter = first + step * index;
      if (axis === "x") {
        const currentCenter = bounds.minX + bounds.width / 2;
        layoutUpdates.set(item.id, { x: (item.x ?? 0) + (targetCenter - currentCenter) });
      } else {
        const currentCenter = bounds.minY + bounds.depth / 2;
        layoutUpdates.set(item.id, { y: (item.y ?? 0) + (targetCenter - currentCenter) });
      }
    });
  }
  return editable.map((item) => ({ item, updates: layoutUpdates.get(item.id) ?? {} }));
}

export function createObjectManagerMoveUpdateEntries(
  editable: BuildingPlacement[],
  dx: number,
  dy: number,
): ObjectManagerUpdateEntry[] {
  return editable.map((item) => ({
    item,
    updates: {
      x: (item.x ?? 0) + dx,
      y: (item.y ?? 0) + dy,
    },
  }));
}

export function createObjectManagerMoveToCoordinateUpdateEntries(
  editable: BuildingPlacement[],
  targetX: number,
  targetY: number,
): { updateEntries: ObjectManagerUpdateEntry[]; dx: number; dy: number } {
  const objectBounds = getObjectManagerBoundsRows(editable);
  const sourceMinX = Math.min(...objectBounds.map(({ bounds }) => bounds.minX));
  const sourceMinY = Math.min(...objectBounds.map(({ bounds }) => bounds.minY));
  const dx = targetX - sourceMinX;
  const dy = targetY - sourceMinY;
  return {
    dx,
    dy,
    updateEntries: createObjectManagerMoveUpdateEntries(editable, dx, dy),
  };
}

export function createObjectManagerScaleUpdateEntries(
  editable: BuildingPlacement[],
  factor: number,
): ObjectManagerUpdateEntry[] {
  return editable.map((item) => ({
    item,
    updates: {
      w: Math.max(1, item.w * factor),
      d: Math.max(1, item.d * factor),
      h: typeof item.h === "number" ? Math.max(0, item.h * factor) : item.h,
    },
  }));
}

export function createObjectManagerRotateUpdateEntries(
  editable: BuildingPlacement[],
  angle: number,
): ObjectManagerUpdateEntry[] {
  const radians = (angle * Math.PI) / 180;
  return editable.map((item) => {
    const centerX = (item.x ?? 0) + item.w / 2;
    const centerY = (item.y ?? 0) + item.d / 2;
    const nextGeometry = item.geometry?.map(([x, y]) => {
      const dx = x - centerX;
      const dy = y - centerY;
      return [
        centerX + dx * Math.cos(radians) - dy * Math.sin(radians),
        centerY + dx * Math.sin(radians) + dy * Math.cos(radians),
      ] as [number, number];
    });
    return {
      item,
      updates: {
        rotation: ((item.rotation ?? 0) + angle) % 360,
        geometry: nextGeometry,
      },
    };
  });
}

export function createObjectManagerMirrorUpdateEntries(
  editable: BuildingPlacement[],
  axis: "x" | "y",
): ObjectManagerUpdateEntry[] {
  const objectBounds = getObjectManagerBoundsRows(editable);
  const selectionMinX = Math.min(...objectBounds.map(({ bounds }) => bounds.minX));
  const selectionMaxX = Math.max(...objectBounds.map(({ bounds }) => bounds.maxX));
  const selectionMinY = Math.min(...objectBounds.map(({ bounds }) => bounds.minY));
  const selectionMaxY = Math.max(...objectBounds.map(({ bounds }) => bounds.maxY));
  const mirrorX = selectionMinX + (selectionMaxX - selectionMinX) / 2;
  const mirrorY = selectionMinY + (selectionMaxY - selectionMinY) / 2;
  return objectBounds.map(({ item, bounds }) => {
    const nextGeometry = item.geometry?.map(([x, y]) =>
      axis === "x"
        ? ([mirrorX - (x - mirrorX), y] as [number, number])
        : ([x, mirrorY - (y - mirrorY)] as [number, number]),
    );
    const xOffsetFromBounds = (item.x ?? 0) - bounds.minX;
    const yOffsetFromBounds = (item.y ?? 0) - bounds.minY;
    const nextX = axis === "x"
      ? mirrorX - (bounds.maxX - mirrorX) + xOffsetFromBounds
      : item.x;
    const nextY = axis === "y"
      ? mirrorY - (bounds.maxY - mirrorY) + yOffsetFromBounds
      : item.y;
    return {
      item,
      updates: {
        x: nextX,
        y: nextY,
        geometry: nextGeometry,
        meta: {
          [axis === "x" ? "mirrored_x" : "mirrored_y"]: true,
        },
      },
    };
  });
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

export function summarizeDraftCopyResults(
  copyResults: Array<{ visible: BuildingPlacement; created: BuildingPlacement[] }>,
): {
  visibleDuplicates: BuildingPlacement[];
  createdObjects: BuildingPlacement[];
  hiddenTraceCount: number;
} {
  const visibleDuplicates = copyResults.map((result) => result.visible);
  const createdObjects = copyResults.flatMap((result) => result.created);
  return {
    visibleDuplicates,
    createdObjects,
    hiddenTraceCount: createdObjects.length - visibleDuplicates.length,
  };
}

export function createDraftArrayCopiesWithTrace({
  editable,
  buildingPlacements,
  rows,
  columns,
  spacingX,
  spacingY,
  stamp,
}: {
  editable: BuildingPlacement[];
  buildingPlacements: BuildingPlacement[];
  rows: number;
  columns: number;
  spacingX: number;
  spacingY: number;
  stamp: number;
}): Array<{ visible: BuildingPlacement; created: BuildingPlacement[] }> {
  return editable.flatMap((item, sourceIndex) => {
    const copyResults: Array<{ visible: BuildingPlacement; created: BuildingPlacement[] }> = [];
    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < columns; column += 1) {
        if (row === 0 && column === 0) continue;
        const dx = column * spacingX;
        const dy = row * spacingY;
        copyResults.push(createDraftCopyWithTrace({
          item,
          buildingPlacements,
          idPrefix: `array-${stamp}-${sourceIndex}-${row}-${column}`,
          label: `${item.label} Array ${row + 1}-${column + 1}`,
          dx,
          dy,
          source: "manual_drawn_array",
          extraMeta: {
            array_source_object_id: item.id,
            array_source_label: item.label,
            array_rows: rows,
            array_columns: columns,
            array_spacing_ft: [spacingX, spacingY],
          },
        }));
      }
    }
    return copyResults;
  });
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
