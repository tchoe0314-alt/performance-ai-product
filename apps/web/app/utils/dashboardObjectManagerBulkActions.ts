import type { BuildingPlacement, ChatMessage, SiteObjectType } from "../types";
import type { DraftUndoAction, RecentChange } from "./dashboardTypes";
import {
  cloneBuildingPlacementForUndo,
  cloneBuildingPlacementWithUpdatesForUndo,
  formatObjectManagerCountMessage,
  partitionObjectManagerTargets,
} from "./dashboardObjectManagerTrace";
import { toReadableLabel } from "./formatting";
import type { EngineeringSystemKey } from "./workflowConstants";
import { getObjectEditBlocker } from "./objectGeometry";
import { SITE_OBJECT_CATALOG } from "./siteObjectCatalog";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type RecordRecentChange = (change: Omit<RecentChange, "id" | "createdAt">) => void;
type MarkSystemsStale = (systems: EngineeringSystemKey[]) => void;
type SystemsImpactedByPlacement = (target?: Partial<BuildingPlacement> | null) => EngineeringSystemKey[];

export type ObjectManagerBulkActions = {
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setSelectedObjectIds: StateSetter<string[]>;
  setActivePlacementId: StateSetter<string | null>;
  setPreviewInteraction: (value: "static" | "edit") => void;
  setObjectManagerStatusMessage: (message: string) => void;
  setStatusMessage: (message: string) => void;
  appendChatMessage: AppendChatMessage;
  recordRecentChange: RecordRecentChange;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  markSystemsStale: MarkSystemsStale;
  systemsImpactedByPlacement: SystemsImpactedByPlacement;
  reportObjectActionBlocker: (message: string) => void;
  handleUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  clearGeneratedPreview: () => void;
  persistDraftRefresh: (reason: string) => void;
};

function selectedTargets({
  buildingPlacements,
  selectedObjectIds,
  emptyMessage,
  reportObjectActionBlocker,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  emptyMessage: string;
  reportObjectActionBlocker: (message: string) => void;
}) {
  const targets = buildingPlacements.filter((item) => selectedObjectIds.includes(item.id));
  if (!targets.length) {
    reportObjectActionBlocker(emptyMessage);
    return null;
  }
  return targets;
}

export function runObjectManagerBulkVisibility({
  hidden,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  hidden: boolean;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const targets = selectedTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Bulk visibility blocked: select one or more objects first.",
    reportObjectActionBlocker: actions.reportObjectActionBlocker,
  });
  if (!targets) return;
  const blocked = targets
    .map((item) => getObjectEditBlocker(item, "hide"))
    .filter(Boolean) as string[];
  const editable = targets.filter((item) => !getObjectEditBlocker(item, "hide"));
  if (!editable.length) {
    actions.reportObjectActionBlocker(blocked[0] ?? "Bulk visibility blocked: selected objects cannot be hidden from the preview.");
    return;
  }
  const undo: DraftUndoAction = {
    action: "bulk_update",
    before: editable.map(cloneBuildingPlacementForUndo),
    after: editable.map((item) => cloneBuildingPlacementWithUpdatesForUndo(item, {
      meta: { ui_hidden: hidden },
    })),
    label: hidden ? "bulk hide" : "bulk show",
  };
  editable.forEach((item) => {
    actions.handleUpdateBuilding(item.id, {
      meta: {
        ...(item.meta ?? {}),
        ui_hidden: hidden,
      },
    });
  });
  const message = `${hidden ? "Hidden" : "Shown"} ${editable.length} selected object${editable.length === 1 ? "" : "s"}${blocked.length ? `; ${blocked.length} blocked.` : "."}`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", message, "status");
  actions.recordRecentChange({
    type: "object_visibility_changed",
    label: hidden ? "Objects hidden" : "Objects shown",
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}

export function runObjectManagerIsolateSelected({
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const selected = buildingPlacements.filter((item) => selectedObjectIds.includes(item.id));
  const editableSelected = selected.filter((item) => !getObjectEditBlocker(item, "hide"));
  if (!editableSelected.length) {
    actions.reportObjectActionBlocker("Isolate selected blocked: select one or more visible editable objects first.");
    return;
  }
  const selectedIdSet = new Set(editableSelected.map((item) => item.id));
  const editableAffected = buildingPlacements.filter((item) => !getObjectEditBlocker(item, "hide"));
  const undo: DraftUndoAction = {
    action: "bulk_update",
    before: editableAffected.map(cloneBuildingPlacementForUndo),
    after: editableAffected.map((item) => cloneBuildingPlacementWithUpdatesForUndo(item, {
      meta: { ui_hidden: !selectedIdSet.has(item.id) },
    })),
    label: "isolate selected",
  };
  let hiddenCount = 0;
  let shownCount = 0;
  editableAffected.forEach((item) => {
    const blocker = getObjectEditBlocker(item, "hide");
    if (blocker) return;
    const shouldHide = !selectedIdSet.has(item.id);
    if (shouldHide && !item.meta?.ui_hidden) hiddenCount += 1;
    if (!shouldHide && item.meta?.ui_hidden) shownCount += 1;
    actions.handleUpdateBuilding(item.id, {
      meta: {
        ...(item.meta ?? {}),
        ui_hidden: shouldHide,
      },
    });
  });
  const message = `Isolated ${editableSelected.length} selected object${editableSelected.length === 1 ? "" : "s"}; ${hiddenCount} other object${hiddenCount === 1 ? "" : "s"} hidden${shownCount ? `, ${shownCount} restored.` : "."}`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", message, "status");
  actions.recordRecentChange({
    type: "object_visibility_changed",
    label: "Objects isolated",
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}

export function runObjectManagerBulkLock({
  locked,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  locked: boolean;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const targets = selectedTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Bulk lock blocked: select one or more draft objects first.",
    reportObjectActionBlocker: actions.reportObjectActionBlocker,
  });
  if (!targets) return;
  const { editable, blockedCount } = partitionObjectManagerTargets({
    targets,
    isEditable: (item) => {
      if (item.type === "site") return false;
      if (item.meta?.ai_realism_artifact) return false;
      if (item.capabilities?.deletable === false) return false;
      return true;
    },
  });
  if (!editable.length) {
    actions.reportObjectActionBlocker("Bulk lock blocked: selected objects are source-only or required project evidence.");
    return;
  }
  const undo: DraftUndoAction = {
    action: "bulk_update",
    before: editable.map(cloneBuildingPlacementForUndo),
    after: editable.map((item) => cloneBuildingPlacementWithUpdatesForUndo(item, { locked })),
    label: locked ? "bulk lock" : "bulk unlock",
  };
  editable.forEach((item) => actions.handleUpdateBuilding(item.id, { locked }));
  const message = formatObjectManagerCountMessage({
    action: locked ? "Locked" : "Unlocked",
    count: editable.length,
    blockedCount,
    noun: "selected draft object",
  });
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", `${message} Locked objects stay visible but cannot be edited until unlocked.`, "status");
  actions.recordRecentChange({
    type: "object_style_changed",
    label: `Objects ${locked ? "locked" : "unlocked"}`,
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}

export function runObjectManagerBulkColor({
  color,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  color: string;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const targets = selectedTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Bulk color blocked: select one or more editable objects first.",
    reportObjectActionBlocker: actions.reportObjectActionBlocker,
  });
  if (!targets) return;
  const { editable, blockedCount } = partitionObjectManagerTargets({
    targets,
    isEditable: (item) => !getObjectEditBlocker(item, "style"),
  });
  if (!editable.length) {
    actions.reportObjectActionBlocker("Bulk color blocked: selected objects are locked, source-only, or not editable.");
    return;
  }
  const undo: DraftUndoAction = {
    action: "bulk_update",
    before: editable.map(cloneBuildingPlacementForUndo),
    after: editable.map((item) => cloneBuildingPlacementWithUpdatesForUndo(item, {
      meta: { ui_color: color },
    })),
    label: "bulk color",
  };
  editable.forEach((item) => {
    actions.handleUpdateBuilding(item.id, {
      meta: {
        ...(item.meta ?? {}),
        ui_color: color,
      },
    });
  });
  const message = formatObjectManagerCountMessage({
    action: "Updated color for",
    count: editable.length,
    blockedCount,
  });
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.recordRecentChange({
    type: "object_style_changed",
    label: "Objects recolored",
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}

export function runObjectManagerBulkType({
  nextType,
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  nextType: SiteObjectType;
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  const targets = selectedTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Bulk layer/type blocked: select one or more editable objects first.",
    reportObjectActionBlocker: actions.reportObjectActionBlocker,
  });
  if (!targets) return;
  const { editable, blockedCount } = partitionObjectManagerTargets({
    targets,
    isEditable: (item) => !getObjectEditBlocker(item, "type"),
  });
  if (!editable.length) {
    actions.reportObjectActionBlocker("Bulk layer/type blocked: selected objects are locked, source-only, or not editable.");
    return;
  }
  const undo: DraftUndoAction = {
    action: "bulk_update",
    before: editable.map(cloneBuildingPlacementForUndo),
    after: editable.map((item) => cloneBuildingPlacementWithUpdatesForUndo(item, {
      type: nextType,
      use: SITE_OBJECT_CATALOG[nextType]?.use ?? item.use,
      meta: {
        category: SITE_OBJECT_CATALOG[nextType]?.category ?? "advanced",
      },
    })),
    label: "bulk layer/type",
  };
  editable.forEach((item) => {
    actions.handleUpdateBuilding(item.id, {
      type: nextType,
      use: SITE_OBJECT_CATALOG[nextType]?.use ?? item.use,
      meta: {
        ...(item.meta ?? {}),
        category: SITE_OBJECT_CATALOG[nextType]?.category ?? "advanced",
      },
    });
  });
  const message = formatObjectManagerCountMessage({
    action: "Updated layer/type for",
    count: editable.length,
    blockedCount,
  });
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.recordRecentChange({
    type: "object_style_changed",
    label: "Objects layer/type changed",
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}

export function runObjectManagerBulkDelete({
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerBulkActions;
}) {
  actions.clearGeneratedPreview();
  const targets = selectedTargets({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Bulk delete blocked: select one or more editable draft objects first.",
    reportObjectActionBlocker: actions.reportObjectActionBlocker,
  });
  if (!targets) return;
  const editable = targets.filter((item) => !getObjectEditBlocker(item, "delete"));
  const blockedCount = targets.length - editable.length;
  if (!editable.length) {
    actions.reportObjectActionBlocker("Bulk delete blocked: selected objects are locked, source-only, or required project evidence.");
    return;
  }
  const editableIds = new Set(editable.map((item) => item.id));
  actions.setBuildingPlacements((prev) => prev.filter((item) => !editableIds.has(item.id)));
  actions.setSelectedObjectIds((prev) => prev.filter((id) => !editableIds.has(id)));
  actions.setActivePlacementId((prev) => (prev && editableIds.has(prev) ? null : prev));
  editable.forEach((item) => actions.markSystemsStale(actions.systemsImpactedByPlacement(item)));
  const undo: DraftUndoAction = {
    action: "delete_many",
    objects: editable.map(cloneBuildingPlacementForUndo),
    label: "bulk delete",
  };
  actions.recordDraftUndoAction(undo);
  const message = `Deleted ${editable.length} selected draft object${editable.length === 1 ? "" : "s"}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  actions.recordRecentChange({
    type: "object_deleted",
    label: "Objects deleted",
    detail: message,
    undo,
  });
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", message, "status");
  actions.persistDraftRefresh("Refreshing preview after bulk delete...");
}

export function runObjectManagerLayerVisibility({
  layerType,
  hidden,
  buildingPlacements,
  actions,
}: {
  layerType: SiteObjectType;
  hidden: boolean;
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerBulkActions;
}) {
  const targets = buildingPlacements.filter((item) => item.type === layerType && item.type !== "site");
  if (!targets.length) {
    actions.reportObjectActionBlocker("Layer visibility blocked: no objects exist on that layer.");
    return;
  }
  const undo: DraftUndoAction = {
    action: "bulk_update",
    before: targets.map(cloneBuildingPlacementForUndo),
    after: targets.map((item) => cloneBuildingPlacementWithUpdatesForUndo(item, {
      meta: { ui_hidden: hidden },
    })),
    label: `${toReadableLabel(layerType)} layer visibility`,
  };
  targets.forEach((item) => {
    actions.handleUpdateBuilding(item.id, {
      meta: {
        ...(item.meta ?? {}),
        ui_hidden: hidden,
      },
    });
  });
  const label = SITE_OBJECT_CATALOG[layerType]?.label ?? toReadableLabel(layerType);
  const message = `${hidden ? "Hidden" : "Shown"} ${targets.length} ${label} layer object${targets.length === 1 ? "" : "s"}.`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", message, "status");
  actions.recordRecentChange({
    type: "object_visibility_changed",
    label: `${label} layer ${hidden ? "hidden" : "shown"}`,
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}

export function runObjectManagerLayerLock({
  layerType,
  locked,
  buildingPlacements,
  actions,
}: {
  layerType: SiteObjectType;
  locked: boolean;
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerBulkActions;
}) {
  const targets = buildingPlacements.filter((item) => item.type === layerType && item.type !== "site");
  if (!targets.length) {
    actions.reportObjectActionBlocker("Layer lock blocked: no editable objects exist on that layer.");
    return;
  }
  const editable = targets.filter((item) => !item.meta?.ai_realism_artifact && item.capabilities?.deletable !== false);
  if (!editable.length) {
    actions.reportObjectActionBlocker("Layer lock blocked: this layer only contains source-only or required evidence objects.");
    return;
  }
  const undo: DraftUndoAction = {
    action: "bulk_update",
    before: editable.map(cloneBuildingPlacementForUndo),
    after: editable.map((item) => cloneBuildingPlacementWithUpdatesForUndo(item, { locked })),
    label: `${toReadableLabel(layerType)} layer lock`,
  };
  editable.forEach((item) => actions.handleUpdateBuilding(item.id, { locked }));
  const label = SITE_OBJECT_CATALOG[layerType]?.label ?? toReadableLabel(layerType);
  const unchangedCount = targets.length - editable.length;
  const message = `${locked ? "Locked" : "Unlocked"} ${editable.length} ${label} layer object${editable.length === 1 ? "" : "s"}${unchangedCount ? `; ${unchangedCount} source-only object${unchangedCount === 1 ? "" : "s"} unchanged.` : "."}`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", message, "status");
  actions.recordRecentChange({
    type: "object_style_changed",
    label: `${label} layer ${locked ? "locked" : "unlocked"}`,
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}

export function runObjectManagerLayerSelect({
  layerType,
  buildingPlacements,
  actions,
}: {
  layerType: SiteObjectType;
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerBulkActions;
}) {
  const targets = buildingPlacements.filter((item) => item.type === layerType && item.type !== "site");
  if (!targets.length) {
    actions.reportObjectActionBlocker("Layer select blocked: no objects exist on that layer.");
    return;
  }
  const ids = targets.map((item) => item.id);
  actions.setSelectedObjectIds(ids);
  actions.setActivePlacementId(ids[0] ?? null);
  actions.setPreviewInteraction("edit");
  const label = SITE_OBJECT_CATALOG[layerType]?.label ?? toReadableLabel(layerType);
  const message = `Selected ${targets.length} ${label} layer object${targets.length === 1 ? "" : "s"}.`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", message, "status");
}

export function runObjectManagerLayerIsolate({
  layerType,
  buildingPlacements,
  actions,
}: {
  layerType: SiteObjectType;
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerBulkActions;
}) {
  const targets = buildingPlacements.filter((item) => item.type === layerType && item.type !== "site");
  if (!targets.length) {
    actions.reportObjectActionBlocker("Layer isolate blocked: no objects exist on that layer.");
    return;
  }
  const editableAffected = buildingPlacements.filter((item) => item.type !== "site" && !getObjectEditBlocker(item, "hide"));
  const undo: DraftUndoAction = {
    action: "bulk_update",
    before: editableAffected.map(cloneBuildingPlacementForUndo),
    after: editableAffected.map((item) => cloneBuildingPlacementWithUpdatesForUndo(item, {
      meta: { ui_hidden: item.type !== layerType },
    })),
    label: `${toReadableLabel(layerType)} layer isolate`,
  };
  editableAffected.forEach((item) => {
    actions.handleUpdateBuilding(item.id, {
      meta: {
        ...(item.meta ?? {}),
        ui_hidden: item.type !== layerType,
      },
    });
  });
  const label = SITE_OBJECT_CATALOG[layerType]?.label ?? toReadableLabel(layerType);
  const hiddenCount = buildingPlacements.filter((item) => item.type !== "site" && item.type !== layerType).length;
  const message = `Showing only ${targets.length} ${label} layer object${targets.length === 1 ? "" : "s"}; ${hiddenCount} other object${hiddenCount === 1 ? "" : "s"} hidden.`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", message, "status");
  actions.recordRecentChange({
    type: "object_visibility_changed",
    label: `${label} layer isolated`,
    detail: message,
    undo,
  });
  actions.recordDraftUndoAction(undo);
}
