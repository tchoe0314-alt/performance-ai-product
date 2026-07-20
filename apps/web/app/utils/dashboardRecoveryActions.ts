import type { BuildingPlacement, ChatMessage } from "../types";
import type { DraftUndoAction, RecentChange } from "./dashboardTypes";
import type { EngineeringSystemKey } from "./workflowConstants";
import type { ProjectStatusSummary } from "./workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;
type RecordRecentChange = (change: Omit<RecentChange, "id" | "createdAt">) => void;
type MarkSystemsStale = (systems: EngineeringSystemKey[]) => void;
type SystemsImpactedByPlacement = (target?: Partial<BuildingPlacement> | null) => EngineeringSystemKey[];

type DashboardRecoveryActions = {
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setSelectedObjectIds: StateSetter<string[]>;
  setActivePlacementId: StateSetter<string | null>;
  setPlacementModeEnabled: (value: boolean) => void;
  setObjectManagerStatusMessage: (message: string) => void;
  setStatusMessage: (message: string) => void;
  pushRecoveryMessage: (message: string) => void;
  appendChatMessage: AppendChatMessage;
  updateProjectStatus: UpdateProjectStatus;
  recordRecentChange: RecordRecentChange;
  markSystemsStale: MarkSystemsStale;
  systemsImpactedByPlacement: SystemsImpactedByPlacement;
  handleRestoreBuilding: (object: BuildingPlacement) => void;
};

export function runDashboardUndoDraftAction({
  draftAction,
  clearDraftAction,
  recordDraftRedoAction,
  actions,
}: {
  draftAction: DraftUndoAction | null;
  clearDraftAction: () => void;
  recordDraftRedoAction: (action: DraftUndoAction) => void;
  actions: DashboardRecoveryActions;
}) {
  const {
    appendChatMessage,
    handleRestoreBuilding,
    markSystemsStale,
    pushRecoveryMessage,
    recordRecentChange,
    setActivePlacementId,
    setBuildingPlacements,
    setObjectManagerStatusMessage,
    setPlacementModeEnabled,
    setSelectedObjectIds,
    systemsImpactedByPlacement,
    updateProjectStatus,
  } = actions;

  if (!draftAction) {
    const message = "Nothing available to undo yet.";
    updateProjectStatus({
      state: "blocked",
      area: "chat",
      title: "Undo not available yet",
      detail: "No supported draft action is available to undo.",
      nextAction: "Continue editing; the next supported draft add/delete can be undone.",
    });
    appendChatMessage("assistant", message, "status");
    return;
  }
  recordDraftRedoAction(draftAction);
  if (draftAction.action === "add") {
    setBuildingPlacements((prev) => prev.filter((item) => item.id !== draftAction.object.id));
    setActivePlacementId((prev) => (prev === draftAction.object.id ? null : prev));
    setPlacementModeEnabled(false);
    const message = `Undo: removed ${draftAction.object.label}.`;
    setObjectManagerStatusMessage(message);
    pushRecoveryMessage(message);
    updateProjectStatus({
      state: "stale",
      area: "chat",
      title: "Undo complete",
      detail: `Undo removed ${draftAction.object.label}.`,
      nextAction: "Review objects, then rerun affected generated systems if needed.",
    });
    appendChatMessage("assistant", message, "status");
    recordRecentChange({
      type: "object_deleted",
      label: "Undo removed object",
      detail: `${draftAction.object.label} was removed by undo.`,
      undoBlockedReason: "This is already an undo result.",
    });
    clearDraftAction();
    return;
  }
  if (draftAction.action === "add_many") {
    const createdIds = new Set(draftAction.objects.map((item) => item.id));
    setBuildingPlacements((prev) => prev.filter((item) => !createdIds.has(item.id)));
    setSelectedObjectIds((prev) => prev.filter((id) => !createdIds.has(id)));
    setActivePlacementId((prev) => (prev && createdIds.has(prev) ? null : prev));
    setPlacementModeEnabled(false);
    draftAction.objects.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    const message = `Undo: removed ${draftAction.objects.length} draft objects from ${draftAction.label}.`;
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
    recordRecentChange({
      type: "object_deleted",
      label: "Undo removed objects",
      detail: `${draftAction.objects.length} draft objects were removed by undo.`,
      undoBlockedReason: "This is already an undo result.",
    });
    clearDraftAction();
    return;
  }
  if (draftAction.action === "delete_many") {
    const restoredIds = new Set(draftAction.objects.map((item) => item.id));
    setBuildingPlacements((prev) => [
      ...prev.filter((item) => !restoredIds.has(item.id)),
      ...draftAction.objects.map((item) => ({ ...item })),
    ]);
    setSelectedObjectIds(draftAction.objects.map((item) => item.id));
    setActivePlacementId(draftAction.objects[0]?.id ?? null);
    draftAction.objects.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    const message = `Undo: restored ${draftAction.objects.length} draft objects from ${draftAction.label}.`;
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
    recordRecentChange({
      type: "object_added",
      label: "Undo restored deleted objects",
      detail: `${draftAction.objects.length} draft objects were restored by undo.`,
      undoBlockedReason: "This is already an undo result.",
    });
    clearDraftAction();
    return;
  }
  if (draftAction.action === "update") {
    setBuildingPlacements((prev) =>
      prev.map((item) => (item.id === draftAction.objectId ? { ...draftAction.before } : item)),
    );
    setActivePlacementId(draftAction.objectId);
    markSystemsStale(systemsImpactedByPlacement(draftAction.before));
    const message = `Undo: restored previous state for ${draftAction.before.label}.`;
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
    recordRecentChange({
      type: "object_style_changed",
      label: "Undo restored object",
      detail: `${draftAction.before.label} was restored to its previous draft state.`,
      undoBlockedReason: "This is already an undo result.",
    });
    clearDraftAction();
    return;
  }
  if (draftAction.action === "combine") {
    const sourceById = new Map(draftAction.hiddenSources.map((item) => [item.id, item]));
    setBuildingPlacements((prev) =>
      prev
        .filter((item) => item.id !== draftAction.object.id)
        .map((item) => (sourceById.has(item.id) ? { ...sourceById.get(item.id)! } : item)),
    );
    setSelectedObjectIds(draftAction.hiddenSources.map((item) => item.id));
    setActivePlacementId(draftAction.hiddenSources[0]?.id ?? null);
    draftAction.hiddenSources.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    const message = `Undo: restored ${draftAction.hiddenSources.length} source objects from ${draftAction.label}.`;
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
    recordRecentChange({
      type: "object_style_changed",
      label: "Undo restored combined sources",
      detail: `${draftAction.hiddenSources.length} source objects were restored and ${draftAction.object.label} was removed.`,
      undoBlockedReason: "This is already an undo result.",
    });
    clearDraftAction();
    return;
  }
  if (draftAction.action === "explode") {
    const beforeSourceById = new Map(draftAction.beforeSources.map((item) => [item.id, item]));
    setBuildingPlacements((prev) => [
      ...prev
        .filter((item) => item.id !== draftAction.object.id)
        .map((item) => (beforeSourceById.has(item.id) ? { ...beforeSourceById.get(item.id)! } : item)),
      { ...draftAction.object },
    ]);
    setSelectedObjectIds([draftAction.object.id]);
    setActivePlacementId(draftAction.object.id);
    markSystemsStale(systemsImpactedByPlacement(draftAction.object));
    const message = `Undo: restored ${draftAction.object.label} after ${draftAction.label}.`;
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
    recordRecentChange({
      type: "object_added",
      label: "Undo restored combined object",
      detail: `${draftAction.object.label} was restored and source pieces were hidden again.`,
      undoBlockedReason: "This is already an undo result.",
    });
    clearDraftAction();
    return;
  }
  if (draftAction.action === "bulk_update") {
    const beforeById = new Map(draftAction.before.map((item) => [item.id, item]));
    setBuildingPlacements((prev) =>
      prev.map((item) => (beforeById.has(item.id) ? { ...beforeById.get(item.id)! } : item)),
    );
    const visibleBefore = draftAction.before.filter((item) => !item.meta?.ui_hidden);
    setSelectedObjectIds(visibleBefore.map((item) => item.id));
    setActivePlacementId(visibleBefore[0]?.id ?? null);
    draftAction.before.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    const message = `Undo: restored ${draftAction.before.length} draft objects from ${draftAction.label}.`;
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
    recordRecentChange({
      type: "object_style_changed",
      label: "Undo restored objects",
      detail: `${draftAction.before.length} draft objects were restored to their previous state.`,
      undoBlockedReason: "This is already an undo result.",
    });
    clearDraftAction();
    return;
  }
  handleRestoreBuilding(draftAction.object);
  appendChatMessage("assistant", `Undo: restored ${draftAction.object.label}.`, "status");
  updateProjectStatus({
    state: "stale",
    area: "chat",
    title: "Undo complete",
    detail: `Undo restored ${draftAction.object.label}.`,
    nextAction: "Review objects, then rerun affected generated systems if needed.",
  });
  clearDraftAction();
}

export function runDashboardRedoDraftAction({
  redoAction,
  recordDraftUndoAction,
  actions,
}: {
  redoAction: DraftUndoAction | null;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  actions: DashboardRecoveryActions;
}) {
  const {
    appendChatMessage,
    markSystemsStale,
    pushRecoveryMessage,
    setActivePlacementId,
    setBuildingPlacements,
    setObjectManagerStatusMessage,
    setPlacementModeEnabled,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
  } = actions;

  if (!redoAction) {
    const message = "Nothing available to redo yet.";
    setObjectManagerStatusMessage(message);
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
    return;
  }
  const finishRedo = (message: string) => {
    recordDraftUndoAction(redoAction);
    setObjectManagerStatusMessage(message);
    setStatusMessage(message);
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
  };
  if (redoAction.action === "add") {
    setBuildingPlacements((prev) =>
      prev.some((item) => item.id === redoAction.object.id) ? prev : [...prev, { ...redoAction.object }],
    );
    setSelectedObjectIds([redoAction.object.id]);
    setActivePlacementId(redoAction.object.id);
    setPlacementModeEnabled(false);
    markSystemsStale(systemsImpactedByPlacement(redoAction.object));
    finishRedo(`Redo: restored ${redoAction.object.label}.`);
    return;
  }
  if (redoAction.action === "add_many") {
    const createdIds = new Set(redoAction.objects.map((item) => item.id));
    setBuildingPlacements((prev) => [
      ...prev.filter((item) => !createdIds.has(item.id)),
      ...redoAction.objects.map((item) => ({ ...item })),
    ]);
    setSelectedObjectIds(redoAction.objects.map((item) => item.id));
    setActivePlacementId(redoAction.objects[0]?.id ?? null);
    redoAction.objects.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    finishRedo(`Redo: restored ${redoAction.objects.length} draft objects from ${redoAction.label}.`);
    return;
  }
  if (redoAction.action === "delete") {
    setBuildingPlacements((prev) => prev.filter((item) => item.id !== redoAction.object.id));
    setSelectedObjectIds((prev) => prev.filter((id) => id !== redoAction.object.id));
    setActivePlacementId((prev) => (prev === redoAction.object.id ? null : prev));
    markSystemsStale(systemsImpactedByPlacement(redoAction.object));
    finishRedo(`Redo: deleted ${redoAction.object.label}.`);
    return;
  }
  if (redoAction.action === "delete_many") {
    const deletedIds = new Set(redoAction.objects.map((item) => item.id));
    setBuildingPlacements((prev) => prev.filter((item) => !deletedIds.has(item.id)));
    setSelectedObjectIds((prev) => prev.filter((id) => !deletedIds.has(id)));
    setActivePlacementId((prev) => (prev && deletedIds.has(prev) ? null : prev));
    redoAction.objects.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    finishRedo(`Redo: deleted ${redoAction.objects.length} draft objects from ${redoAction.label}.`);
    return;
  }
  if (redoAction.action === "update") {
    setBuildingPlacements((prev) =>
      prev.map((item) => (item.id === redoAction.objectId ? { ...redoAction.after } : item)),
    );
    setSelectedObjectIds([redoAction.objectId]);
    setActivePlacementId(redoAction.objectId);
    markSystemsStale(systemsImpactedByPlacement(redoAction.after));
    finishRedo(`Redo: restored edited state for ${redoAction.after.label}.`);
    return;
  }
  if (redoAction.action === "combine") {
    const sourceIds = new Set(redoAction.hiddenSources.map((item) => item.id));
    setBuildingPlacements((prev) => [
      ...prev
        .filter((item) => item.id !== redoAction.object.id)
        .map((item) =>
          sourceIds.has(item.id)
            ? {
                ...item,
                meta: {
                  ...(item.meta ?? {}),
                  ui_hidden: true,
                  combined_into_object_id: redoAction.object.id,
                  combined_into_label: redoAction.object.label,
                },
              }
            : item,
        ),
      { ...redoAction.object },
    ]);
    setSelectedObjectIds([redoAction.object.id]);
    setActivePlacementId(redoAction.object.id);
    markSystemsStale(systemsImpactedByPlacement(redoAction.object));
    finishRedo(`Redo: recombined ${redoAction.hiddenSources.length} source objects into ${redoAction.object.label}.`);
    return;
  }
  if (redoAction.action === "explode") {
    const afterSourceById = new Map(redoAction.afterSources.map((item) => [item.id, item]));
    setBuildingPlacements((prev) =>
      prev
        .filter((item) => item.id !== redoAction.object.id)
        .map((item) => (afterSourceById.has(item.id) ? { ...afterSourceById.get(item.id)! } : item)),
    );
    setSelectedObjectIds(redoAction.afterSources.map((item) => item.id));
    setActivePlacementId(redoAction.afterSources[0]?.id ?? null);
    markSystemsStale(systemsImpactedByPlacement(redoAction.object));
    finishRedo(`Redo: exploded ${redoAction.object.label} into ${redoAction.afterSources.length} source pieces.`);
    return;
  }
  if (redoAction.action === "bulk_update" && redoAction.after?.length) {
    const afterById = new Map(redoAction.after.map((item) => [item.id, item]));
    setBuildingPlacements((prev) =>
      prev.map((item) => (afterById.has(item.id) ? { ...afterById.get(item.id)! } : item)),
    );
    const visibleAfter = redoAction.after.filter((item) => !item.meta?.ui_hidden);
    setSelectedObjectIds(visibleAfter.map((item) => item.id));
    setActivePlacementId(visibleAfter[0]?.id ?? null);
    redoAction.after.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    finishRedo(`Redo: reapplied ${redoAction.after.length} draft objects from ${redoAction.label}.`);
    return;
  }
  const message = `Redo not available: ${redoAction.action === "bulk_update" ? `${redoAction.label} does not have an after snapshot yet.` : "this draft action cannot be reapplied safely."}`;
  setObjectManagerStatusMessage(message);
  pushRecoveryMessage(message);
  appendChatMessage("assistant", message, "status");
}

export function runDashboardUndoRecentChange({
  change,
  recordDraftRedoAction,
  actions,
}: {
  change: RecentChange;
  recordDraftRedoAction: (action: DraftUndoAction) => void;
  actions: DashboardRecoveryActions;
}) {
  const {
    appendChatMessage,
    handleRestoreBuilding,
    markSystemsStale,
    pushRecoveryMessage,
    recordRecentChange,
    setActivePlacementId,
    setBuildingPlacements,
    setPlacementModeEnabled,
    setSelectedObjectIds,
    systemsImpactedByPlacement,
  } = actions;

  if (!change.undo) {
    const message = `Undo not available: ${change.undoBlockedReason || "this recent change does not have a reversible draft snapshot."}`;
    pushRecoveryMessage(message);
    appendChatMessage("assistant", message, "status");
    return;
  }
  const undo = change.undo;
  recordDraftRedoAction(undo);
  if (undo.action === "add") {
    setBuildingPlacements((prev) => prev.filter((item) => item.id !== undo.object.id));
    setActivePlacementId((prev) => (prev === undo.object.id ? null : prev));
    setPlacementModeEnabled(false);
    markSystemsStale(systemsImpactedByPlacement(undo.object));
    pushRecoveryMessage(`Undo: removed ${undo.object.label}.`);
    recordRecentChange({
      type: "object_deleted",
      label: "Undo removed object",
      detail: `${undo.object.label} was removed by undo.`,
      undoBlockedReason: "This is already an undo result.",
    });
    return;
  }
  if (undo.action === "add_many") {
    const createdIds = new Set(undo.objects.map((item) => item.id));
    setBuildingPlacements((prev) => prev.filter((item) => !createdIds.has(item.id)));
    setSelectedObjectIds((prev) => prev.filter((id) => !createdIds.has(id)));
    setActivePlacementId((prev) => (prev && createdIds.has(prev) ? null : prev));
    setPlacementModeEnabled(false);
    undo.objects.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    pushRecoveryMessage(`Undo: removed ${undo.objects.length} draft objects from ${undo.label}.`);
    recordRecentChange({
      type: "object_deleted",
      label: "Undo removed objects",
      detail: `${undo.objects.length} draft objects were removed by undo.`,
      undoBlockedReason: "This is already an undo result.",
    });
    return;
  }
  if (undo.action === "delete_many") {
    const restoredIds = new Set(undo.objects.map((item) => item.id));
    setBuildingPlacements((prev) => [
      ...prev.filter((item) => !restoredIds.has(item.id)),
      ...undo.objects.map((item) => ({ ...item })),
    ]);
    setSelectedObjectIds(undo.objects.map((item) => item.id));
    setActivePlacementId(undo.objects[0]?.id ?? null);
    undo.objects.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    pushRecoveryMessage(`Undo: restored ${undo.objects.length} draft objects from ${undo.label}.`);
    recordRecentChange({
      type: "object_added",
      label: "Undo restored deleted objects",
      detail: `${undo.objects.length} draft objects were restored by undo.`,
      undoBlockedReason: "This is already an undo result.",
    });
    return;
  }
  if (undo.action === "delete") {
    handleRestoreBuilding(undo.object);
    return;
  }
  if (undo.action === "combine") {
    const sourceById = new Map(undo.hiddenSources.map((item) => [item.id, item]));
    setBuildingPlacements((prev) =>
      prev
        .filter((item) => item.id !== undo.object.id)
        .map((item) => (sourceById.has(item.id) ? { ...sourceById.get(item.id)! } : item)),
    );
    setSelectedObjectIds(undo.hiddenSources.map((item) => item.id));
    setActivePlacementId(undo.hiddenSources[0]?.id ?? null);
    undo.hiddenSources.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    pushRecoveryMessage(`Undo: restored ${undo.hiddenSources.length} source objects from ${undo.label}.`);
    recordRecentChange({
      type: "object_style_changed",
      label: "Undo restored combined sources",
      detail: `${undo.hiddenSources.length} source objects were restored and ${undo.object.label} was removed.`,
      undoBlockedReason: "This is already an undo result.",
    });
    return;
  }
  if (undo.action === "explode") {
    const beforeSourceById = new Map(undo.beforeSources.map((item) => [item.id, item]));
    setBuildingPlacements((prev) => [
      ...prev
        .filter((item) => item.id !== undo.object.id)
        .map((item) => (beforeSourceById.has(item.id) ? { ...beforeSourceById.get(item.id)! } : item)),
      { ...undo.object },
    ]);
    setSelectedObjectIds([undo.object.id]);
    setActivePlacementId(undo.object.id);
    markSystemsStale(systemsImpactedByPlacement(undo.object));
    pushRecoveryMessage(`Undo: restored ${undo.object.label} after ${undo.label}.`);
    recordRecentChange({
      type: "object_added",
      label: "Undo restored combined object",
      detail: `${undo.object.label} was restored and source pieces were hidden again.`,
      undoBlockedReason: "This is already an undo result.",
    });
    return;
  }
  if (undo.action === "bulk_update") {
    const beforeById = new Map(undo.before.map((item) => [item.id, item]));
    setBuildingPlacements((prev) =>
      prev.map((item) => (beforeById.has(item.id) ? { ...beforeById.get(item.id)! } : item)),
    );
    const visibleBefore = undo.before.filter((item) => !item.meta?.ui_hidden);
    setSelectedObjectIds(visibleBefore.map((item) => item.id));
    setActivePlacementId(visibleBefore[0]?.id ?? null);
    undo.before.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
    pushRecoveryMessage(`Undo: restored ${undo.before.length} draft objects from ${undo.label}.`);
    recordRecentChange({
      type: "object_style_changed",
      label: "Undo restored objects",
      detail: `${undo.before.length} draft objects were restored to their previous state.`,
      undoBlockedReason: "This is already an undo result.",
    });
    return;
  }
  setBuildingPlacements((prev) =>
    prev.map((item) => (item.id === undo.objectId ? { ...undo.before } : item)),
  );
  setActivePlacementId(undo.objectId);
  markSystemsStale(systemsImpactedByPlacement(undo.before));
  pushRecoveryMessage(`Undo: restored previous state for ${undo.before.label}.`);
  recordRecentChange({
    type: "object_style_changed",
    label: "Undo restored object",
    detail: `${undo.before.label} was restored to its previous draft state.`,
    undoBlockedReason: "This is already an undo result.",
  });
}
