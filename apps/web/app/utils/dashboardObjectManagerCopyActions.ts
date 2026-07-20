import type { BuildingPlacement, ChatMessage } from "../types";
import type { DraftUndoAction, RecentChange } from "./dashboardTypes";
import {
  createDraftArrayCopiesWithTrace,
  createDraftCopyWithTrace,
  isObjectManagerCopyableDraft,
  partitionObjectManagerTargets,
  summarizeDraftCopyResults,
} from "./dashboardObjectManagerTrace";
import type { EngineeringSystemKey } from "./workflowConstants";
import { getObjectEditBlocker } from "./objectGeometry";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type RecordRecentChange = (change: Omit<RecentChange, "id" | "createdAt">) => void;
type MarkSystemsStale = (systems: EngineeringSystemKey[]) => void;
type SystemsImpactedByPlacement = (target?: Partial<BuildingPlacement> | null) => EngineeringSystemKey[];

type ObjectManagerCopyActions = {
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setSelectedObjectIds: StateSetter<string[]>;
  setActivePlacementId: StateSetter<string | null>;
  setObjectManagerStatusMessage: (message: string) => void;
  setStatusMessage: (message: string) => void;
  appendChatMessage: AppendChatMessage;
  recordRecentChange: RecordRecentChange;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  markSystemsStale: MarkSystemsStale;
  systemsImpactedByPlacement: SystemsImpactedByPlacement;
  reportObjectActionBlocker: (message: string) => void;
  clearGeneratedPreview: () => void;
  persistDraftRefresh: (reason: string) => void;
};

function selectedCopyableDraftObjects({
  buildingPlacements,
  selectedObjectIds,
  blockedMessage,
  emptyMessage,
  reportObjectActionBlocker,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  blockedMessage: string;
  emptyMessage: string;
  reportObjectActionBlocker: (message: string) => void;
}): { editable: BuildingPlacement[]; blockedCount: number } | null {
  const targets = buildingPlacements.filter((item) => selectedObjectIds.includes(item.id));
  if (!targets.length) {
    reportObjectActionBlocker(emptyMessage);
    return null;
  }
  const { editable, blockedCount } = partitionObjectManagerTargets({
    targets,
    isEditable: (item) => {
      return isObjectManagerCopyableDraft({
        item,
        hasCopyBlocker: Boolean(getObjectEditBlocker(item, "copy")),
      });
    },
  });
  if (!editable.length) {
    reportObjectActionBlocker(blockedMessage);
    return null;
  }
  return { editable, blockedCount };
}

function commitCopiedDraftObjects({
  visibleDuplicates,
  createdObjects,
  hiddenTraceCount,
  blockedCount,
  undoLabel,
  recentLabel,
  recentDetail,
  message,
  chatSuffix,
  refreshReason,
  actions,
}: {
  visibleDuplicates: BuildingPlacement[];
  createdObjects: BuildingPlacement[];
  hiddenTraceCount: number;
  blockedCount: number;
  undoLabel: string;
  recentLabel: string;
  recentDetail: string;
  message: string;
  chatSuffix: string;
  refreshReason: string;
  actions: ObjectManagerCopyActions;
}) {
  const {
    appendChatMessage,
    markSystemsStale,
    persistDraftRefresh,
    recordDraftUndoAction,
    recordRecentChange,
    setActivePlacementId,
    setBuildingPlacements,
    setObjectManagerStatusMessage,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
  } = actions;

  setBuildingPlacements((prev) => [...prev, ...createdObjects]);
  setSelectedObjectIds(visibleDuplicates.map((item) => item.id));
  setActivePlacementId(visibleDuplicates[0]?.id ?? null);
  createdObjects.forEach((item) => markSystemsStale(systemsImpactedByPlacement(item)));
  const undo: DraftUndoAction = { action: "add_many", objects: createdObjects, label: undoLabel };
  recordDraftUndoAction(undo);
  recordRecentChange({
    type: "object_added",
    label: recentLabel,
    detail: recentDetail || message,
    undo,
  });
  setObjectManagerStatusMessage(message);
  setStatusMessage(message);
  appendChatMessage("assistant", `${message} ${chatSuffix}`, "status");
  persistDraftRefresh(refreshReason);
  void hiddenTraceCount;
  void blockedCount;
}

export function runObjectManagerBulkDuplicate({
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerCopyActions;
}) {
  actions.clearGeneratedPreview();
  const selection = selectedCopyableDraftObjects({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Bulk duplicate blocked: select one or more editable draft objects first.",
    blockedMessage: "Bulk duplicate blocked: selected objects are locked, source-only, or required project evidence.",
    reportObjectActionBlocker: actions.reportObjectActionBlocker,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const offset = 28;
  const stamp = Date.now();
  const copyResults = editable.map((item, index) =>
    createDraftCopyWithTrace({
      item,
      buildingPlacements,
      idPrefix: `duplicate-${stamp}-${index}`,
      label: `${item.label} Copy`,
      dx: offset,
      dy: offset,
      source: "manual_drawn_copy",
    }),
  );
  const { visibleDuplicates, createdObjects, hiddenTraceCount } = summarizeDraftCopyResults(copyResults);
  const message = `Duplicated ${visibleDuplicates.length} selected draft object${visibleDuplicates.length === 1 ? "" : "s"}${hiddenTraceCount ? ` with ${hiddenTraceCount} hidden source trace piece${hiddenTraceCount === 1 ? "" : "s"}` : ""}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  commitCopiedDraftObjects({
    visibleDuplicates,
    createdObjects,
    hiddenTraceCount,
    blockedCount,
    undoLabel: "bulk duplicate",
    recentLabel: "Objects duplicated",
    recentDetail: `Duplicated ${visibleDuplicates.length} selected draft object${visibleDuplicates.length === 1 ? "" : "s"}${blockedCount ? `; ${blockedCount} blocked.` : "."}`,
    message,
    chatSuffix: "Duplicates remain review-required draft geometry.",
    refreshReason: "Refreshing preview after bulk duplicate...",
    actions,
  });
}

export function runObjectManagerPaste({
  objectClipboard,
  buildingPlacements,
  actions,
}: {
  objectClipboard: BuildingPlacement[];
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerCopyActions;
}) {
  actions.clearGeneratedPreview();
  if (!objectClipboard.length) {
    actions.reportObjectActionBlocker("Paste blocked: copy an editable object first.");
    return;
  }
  const blocked = objectClipboard
    .map((item) => getObjectEditBlocker(item, "copy"))
    .filter(Boolean) as string[];
  const editable = objectClipboard.filter((item) => !getObjectEditBlocker(item, "copy"));
  if (!editable.length) {
    const blocker = blocked[0] ?? "Paste blocked: copied objects are source-only or cannot be copied.";
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  const offset = 24;
  const stamp = Date.now();
  const {
    visibleDuplicates: visiblePastedObjects,
    createdObjects,
    hiddenTraceCount,
  } = summarizeDraftCopyResults(
    editable.map((item, index) =>
      createDraftCopyWithTrace({
        item,
        buildingPlacements,
        idPrefix: `copy-${stamp}-${index}`,
        label: `${item.label} Copy`,
        dx: offset,
        dy: offset,
        source: "manual_drawn_copy",
        extraMeta: {
          copied_set_size: editable.length,
        },
      }),
    ),
  );
  actions.setBuildingPlacements((prev) => [...prev, ...createdObjects]);
  actions.setActivePlacementId(visiblePastedObjects[0]?.id ?? null);
  actions.setSelectedObjectIds(visiblePastedObjects.map((item) => item.id));
  createdObjects.forEach((item) => actions.markSystemsStale(actions.systemsImpactedByPlacement(item)));
  const pasteUndoLabel = hiddenTraceCount ? "group paste" : "multi-object paste";
  const undoAction: DraftUndoAction = createdObjects.length === 1
    ? { action: "add", object: createdObjects[0] }
    : { action: "add_many", objects: createdObjects, label: pasteUndoLabel };
  actions.recordDraftUndoAction(undoAction);
  actions.recordRecentChange({
    type: "object_added",
    label: visiblePastedObjects.length === 1 ? "Object pasted" : "Objects pasted",
    detail: visiblePastedObjects.length === 1
      ? `${visiblePastedObjects[0].label} was pasted as an editable draft duplicate.`
      : `${visiblePastedObjects.length} copied draft objects were pasted as editable draft duplicates.`,
    undo: undoAction,
  });
  const message = visiblePastedObjects.length === 1
    ? `Pasted ${visiblePastedObjects[0].label}${hiddenTraceCount ? ` with ${hiddenTraceCount} hidden source trace piece${hiddenTraceCount === 1 ? "" : "s"}` : ""}. It remains review-required draft geometry.`
    : `Pasted ${visiblePastedObjects.length} copied draft objects${hiddenTraceCount ? ` with ${hiddenTraceCount} hidden source trace piece${hiddenTraceCount === 1 ? "" : "s"}` : ""}${blocked.length ? `; ${blocked.length} blocked.` : "."} They remain review-required draft geometry.`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
  actions.appendChatMessage("assistant", message, "status");
  actions.persistDraftRefresh("Refreshing preview after paste...");
}

export function runObjectManagerBulkCopyByOffset({
  buildingPlacements,
  selectedObjectIds,
  bulkMoveX,
  bulkMoveY,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  bulkMoveX: string;
  bulkMoveY: string;
  actions: ObjectManagerCopyActions;
}) {
  actions.clearGeneratedPreview();
  const dx = Number(bulkMoveX);
  const dy = Number(bulkMoveY);
  if (!Number.isFinite(dx) || !Number.isFinite(dy) || (dx === 0 && dy === 0)) {
    actions.reportObjectActionBlocker("Copy by offset blocked: enter a non-zero X or Y offset.");
    return;
  }
  const selection = selectedCopyableDraftObjects({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Copy by offset blocked: select one or more editable draft objects first.",
    blockedMessage: "Copy by offset blocked: selected objects are locked, source-only, or required project evidence.",
    reportObjectActionBlocker: actions.reportObjectActionBlocker,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const stamp = Date.now();
  const copyResults = editable.map((item, index) =>
    createDraftCopyWithTrace({
      item,
      buildingPlacements,
      idPrefix: `copy-vector-${stamp}-${index}`,
      label: `${item.label} Copy`,
      dx,
      dy,
      source: "manual_drawn_copy_by_offset",
      extraMeta: { copied_offset_ft: [dx, dy] },
    }),
  );
  const { visibleDuplicates, createdObjects, hiddenTraceCount } = summarizeDraftCopyResults(copyResults);
  const message = `Copied ${visibleDuplicates.length} selected draft object${visibleDuplicates.length === 1 ? "" : "s"} by ${dx},${dy}${hiddenTraceCount ? ` with ${hiddenTraceCount} hidden source trace piece${hiddenTraceCount === 1 ? "" : "s"}` : ""}${blockedCount ? `; ${blockedCount} blocked.` : "."}`;
  commitCopiedDraftObjects({
    visibleDuplicates,
    createdObjects,
    hiddenTraceCount,
    blockedCount,
    undoLabel: "copy by offset",
    recentLabel: "Objects copied by offset",
    recentDetail: message,
    message,
    chatSuffix: "Copies remain review-required draft geometry.",
    refreshReason: "Refreshing preview after copy by offset...",
    actions,
  });
}

export function runObjectManagerArraySelected({
  buildingPlacements,
  selectedObjectIds,
  arrayRows,
  arrayColumns,
  arraySpacingX,
  arraySpacingY,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  arrayRows: string;
  arrayColumns: string;
  arraySpacingX: string;
  arraySpacingY: string;
  actions: ObjectManagerCopyActions;
}) {
  actions.clearGeneratedPreview();
  const rows = Math.floor(Number(arrayRows));
  const columns = Math.floor(Number(arrayColumns));
  const spacingX = Number(arraySpacingX);
  const spacingY = Number(arraySpacingY);
  if (!Number.isFinite(rows) || !Number.isFinite(columns) || rows < 1 || columns < 1 || rows * columns < 2) {
    actions.reportObjectActionBlocker("Array blocked: use at least 2 total positions, like 2 rows by 3 columns.");
    return;
  }
  if (!Number.isFinite(spacingX) || !Number.isFinite(spacingY) || (spacingX === 0 && spacingY === 0)) {
    actions.reportObjectActionBlocker("Array blocked: provide a non-zero X or Y spacing.");
    return;
  }
  const selection = selectedCopyableDraftObjects({
    buildingPlacements,
    selectedObjectIds,
    emptyMessage: "Array blocked: select one or more editable draft objects first.",
    blockedMessage: "Array blocked: selected objects are locked, source-only, or required project evidence.",
    reportObjectActionBlocker: actions.reportObjectActionBlocker,
  });
  if (!selection) return;
  const { editable, blockedCount } = selection;
  const totalCopies = editable.length * (rows * columns - 1);
  if (totalCopies > 80) {
    actions.reportObjectActionBlocker("Array blocked: limit this draft array to 80 new objects or fewer.");
    return;
  }
  const { visibleDuplicates, createdObjects, hiddenTraceCount } = summarizeDraftCopyResults(createDraftArrayCopiesWithTrace({
    editable,
    buildingPlacements,
    rows,
    columns,
    spacingX,
    spacingY,
    stamp: Date.now(),
  }));
  const message = `Array created ${visibleDuplicates.length} draft review cop${visibleDuplicates.length === 1 ? "y" : "ies"}${hiddenTraceCount ? ` with ${hiddenTraceCount} hidden source trace piece${hiddenTraceCount === 1 ? "" : "s"}` : ""}${blockedCount ? `; ${blockedCount} selected object${blockedCount === 1 ? "" : "s"} blocked.` : "."}`;
  commitCopiedDraftObjects({
    visibleDuplicates,
    createdObjects,
    hiddenTraceCount,
    blockedCount,
    undoLabel: "array",
    recentLabel: "Objects arrayed",
    recentDetail: message,
    message,
    chatSuffix: "Array output remains review-required draft geometry.",
    refreshReason: "Refreshing preview after array...",
    actions,
  });
}
