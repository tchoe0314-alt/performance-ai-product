import type { BuildingPlacement } from "../types";
import type { ObjectManagerLayoutAction } from "./dashboardObjectManagerTrace";
import {
  createObjectManagerLayoutUpdateEntries,
  createObjectManagerMirrorUpdateEntries,
  createObjectManagerMoveToCoordinateUpdateEntries,
  createObjectManagerMoveUpdateEntries,
  createObjectManagerRotateUpdateEntries,
  createObjectManagerScaleUpdateEntries,
  createTraceAwareBulkUpdate,
} from "./dashboardObjectManagerTrace";
import type { ObjectManagerBulkActions } from "./dashboardObjectManagerBulkActions";
import { getObjectEditBlocker } from "./objectGeometry";

type TransformEditableAction = "transform" | "resize";
export type ObjectManagerSingleTransform = "rotate" | "flip_horizontal" | "flip_vertical";

function editableTransformTargets({
  buildingPlacements,
  selectedObjectIds,
  emptyMessage,
  blockedMessage,
  action,
  minimumEditable = 1,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  emptyMessage: string;
  blockedMessage: string;
  action: TransformEditableAction;
  minimumEditable?: number;
  actions: ObjectManagerBulkActions;
}): { editable: BuildingPlacement[]; blockedCount: number } | null {
  const targets = buildingPlacements.filter((item) => selectedObjectIds.includes(item.id));
  if (targets.length < minimumEditable) {
    actions.reportObjectActionBlocker(emptyMessage);
    return null;
  }
  const editable = targets.filter((item) => !getObjectEditBlocker(item, action));
  const blockedCount = targets.length - editable.length;
  if (editable.length < minimumEditable) {
    actions.reportObjectActionBlocker(blockedMessage);
    return null;
  }
  return { editable, blockedCount };
}

function applyTransformUpdate({
  buildingPlacements,
  editable,
  updateEntries,
  undoLabel,
  recentLabel,
  message,
  chatSuffix,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  editable: BuildingPlacement[];
  updateEntries: Array<{ item: BuildingPlacement; updates: Partial<BuildingPlacement> }>;
  undoLabel: string;
  recentLabel: string;
  message: string;
  chatSuffix: string;
  actions: ObjectManagerBulkActions;
}) {
  const { undo, afterById } = createTraceAwareBulkUpdate({
    entries: updateEntries,
    label: undoLabel,
    buildingPlacements,
  });
  actions.setBuildingPlacements((prev) => prev.map((item) => afterById.get(item.id) ?? item));
  editable.forEach((item) => actions.markSystemsStale(actions.systemsImpactedByPlacement(item)));
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", `${message} ${chatSuffix}`, "status");
  actions.recordRecentChange({
    type: "object_style_changed",
    label: recentLabel,
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}

export function runObjectManagerBulkLayout({
  layout,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  layout: ObjectManagerLayoutAction;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const selection = editableTransformTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Layout blocked: select at least two editable draft objects first.",
    blockedMessage: "Layout blocked: selected objects are locked, source-only, or required project evidence.",
    action: "transform",
    minimumEditable: 2,
    actions,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const labelMap: Record<typeof layout, string> = {
    align_left: "Aligned left",
    align_top: "Aligned top",
    distribute_x: "Distributed X",
    distribute_y: "Distributed Y",
  };
  const message = `${labelMap[layout]} ${editable.length} selected draft object${editable.length === 1 ? "" : "s"}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  applyTransformUpdate({
    buildingPlacements,
    editable,
    updateEntries: createObjectManagerLayoutUpdateEntries(editable, layout),
    undoLabel: `layout ${layout.replace("_", " ")}`,
    recentLabel: "Objects laid out",
    message,
    chatSuffix: "Layout changes remain draft review geometry.",
    actions,
  });
}

export function runObjectManagerTransform({
  item,
  transform,
  actions,
}: {
  item: BuildingPlacement;
  transform: ObjectManagerSingleTransform;
  actions: ObjectManagerBulkActions;
}) {
  const blocker = getObjectEditBlocker(item, "transform");
  if (blocker) {
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  const centerX = (item.x ?? 0) + item.w / 2;
  const centerY = (item.y ?? 0) + item.d / 2;
  const transformPoint = ([x, y]: [number, number]): [number, number] => {
    if (transform === "flip_horizontal") return [centerX - (x - centerX), y];
    if (transform === "flip_vertical") return [x, centerY - (y - centerY)];
    return [centerX - (y - centerY), centerY + (x - centerX)];
  };
  const nextGeometry = item.geometry?.map(transformPoint);
  const nextUpdates: Partial<BuildingPlacement> = transform === "rotate"
    ? {
        x: centerX - item.d / 2,
        y: centerY - item.w / 2,
        rotation: ((item.rotation ?? 0) + 90) % 360,
        w: item.d,
        d: item.w,
        geometry: nextGeometry,
      }
    : {
        geometry: nextGeometry,
        meta: {
          ...(item.meta ?? {}),
          [transform === "flip_horizontal" ? "flipped_horizontal" : "flipped_vertical"]: true,
        },
      };
  actions.handleUpdateBuilding(item.id, nextUpdates);
  const label = transform === "rotate" ? "Rotated" : transform === "flip_horizontal" ? "Flipped horizontal" : "Flipped vertical";
  const message = `${label} ${item.label}. Generated systems may be stale until rerun.`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
}

export function runObjectManagerBulkMove({
  bulkMoveX,
  bulkMoveY,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  bulkMoveX: string;
  bulkMoveY: string;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const dx = Number(bulkMoveX);
  const dy = Number(bulkMoveY);
  if (!Number.isFinite(dx) || !Number.isFinite(dy) || (dx === 0 && dy === 0)) {
    actions.reportObjectActionBlocker("Move blocked: enter a non-zero X or Y offset.");
    return;
  }
  const selection = editableTransformTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Move blocked: select one or more editable draft objects first.",
    blockedMessage: "Move blocked: selected objects are locked, source-only, or required project evidence.",
    action: "transform",
    actions,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const message = `Moved ${editable.length} selected draft object${editable.length === 1 ? "" : "s"} by ${dx},${dy}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  applyTransformUpdate({
    buildingPlacements,
    editable,
    updateEntries: createObjectManagerMoveUpdateEntries(editable, dx, dy),
    undoLabel: "bulk move",
    recentLabel: "Objects moved",
    message,
    chatSuffix: "Move remains draft review geometry.",
    actions,
  });
}

export function runObjectManagerBulkMoveTo({
  bulkMoveToX,
  bulkMoveToY,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  bulkMoveToX: string;
  bulkMoveToY: string;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const targetX = Number(bulkMoveToX);
  const targetY = Number(bulkMoveToY);
  if (!Number.isFinite(targetX) || !Number.isFinite(targetY)) {
    actions.reportObjectActionBlocker("Move to coordinate blocked: enter finite target X and Y coordinates.");
    return;
  }
  const selection = editableTransformTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Move to coordinate blocked: select one or more editable draft objects first.",
    blockedMessage: "Move to coordinate blocked: selected objects are locked, source-only, or required project evidence.",
    action: "transform",
    actions,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const { updateEntries, dx, dy } = createObjectManagerMoveToCoordinateUpdateEntries(editable, targetX, targetY);
  if (dx === 0 && dy === 0) {
    actions.reportObjectActionBlocker("Move to coordinate blocked: selected objects are already at that target coordinate.");
    return;
  }
  const message = `Moved ${editable.length} selected draft object${editable.length === 1 ? "" : "s"} to ${targetX},${targetY}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  applyTransformUpdate({
    buildingPlacements,
    editable,
    updateEntries,
    undoLabel: "bulk move to coordinate",
    recentLabel: "Objects moved to coordinate",
    message,
    chatSuffix: "Absolute move remains draft review geometry.",
    actions,
  });
}

export function runObjectManagerBulkScale({
  bulkScaleFactor,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  bulkScaleFactor: string;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const factor = Number(bulkScaleFactor);
  if (!Number.isFinite(factor) || factor <= 0 || factor > 10) {
    actions.reportObjectActionBlocker("Scale blocked: enter a scale factor greater than 0 and no more than 10.");
    return;
  }
  const selection = editableTransformTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Scale blocked: select one or more editable draft objects first.",
    blockedMessage: "Scale blocked: selected objects are locked, source-only, or required project evidence.",
    action: "resize",
    actions,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const message = `Scaled ${editable.length} selected draft object${editable.length === 1 ? "" : "s"} by ${factor}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  applyTransformUpdate({
    buildingPlacements,
    editable,
    updateEntries: createObjectManagerScaleUpdateEntries(editable, factor),
    undoLabel: "bulk scale",
    recentLabel: "Objects scaled",
    message,
    chatSuffix: "Scale remains draft review geometry.",
    actions,
  });
}

export function runObjectManagerBulkRotate({
  bulkRotateAngle,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  bulkRotateAngle: string;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const angle = Number(bulkRotateAngle);
  if (!Number.isFinite(angle) || angle === 0) {
    actions.reportObjectActionBlocker("Rotate blocked: enter a non-zero angle.");
    return;
  }
  const selection = editableTransformTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Rotate blocked: select one or more editable draft objects first.",
    blockedMessage: "Rotate blocked: selected objects are locked, source-only, or required project evidence.",
    action: "transform",
    actions,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const message = `Rotated ${editable.length} selected draft object${editable.length === 1 ? "" : "s"} by ${angle} degrees${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  applyTransformUpdate({
    buildingPlacements,
    editable,
    updateEntries: createObjectManagerRotateUpdateEntries(editable, angle),
    undoLabel: "bulk rotate",
    recentLabel: "Objects rotated",
    message,
    chatSuffix: "Rotation remains draft review geometry.",
    actions,
  });
}

export function runObjectManagerBulkMirror({
  axis,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  axis: "x" | "y";
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const selection = editableTransformTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Mirror blocked: select one or more editable draft objects first.",
    blockedMessage: "Mirror blocked: selected objects are locked, source-only, or required project evidence.",
    action: "transform",
    actions,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const message = `Mirrored ${axis.toUpperCase()} ${editable.length} selected draft object${editable.length === 1 ? "" : "s"}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  applyTransformUpdate({
    buildingPlacements,
    editable,
    updateEntries: createObjectManagerMirrorUpdateEntries(editable, axis),
    undoLabel: `bulk mirror ${axis.toUpperCase()}`,
    recentLabel: `Objects mirrored ${axis.toUpperCase()}`,
    message,
    chatSuffix: "Mirror remains draft review geometry.",
    actions,
  });
}
