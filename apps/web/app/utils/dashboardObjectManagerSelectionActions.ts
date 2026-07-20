import type { BuildingPlacement } from "../types";
import {
  cloneBuildingPlacementForUndo,
  formatVisibleDraftSelectionMessage,
  getVisibleEditableDraftObjectIds,
  invertVisibleDraftSelection,
} from "./dashboardObjectManagerTrace";
import { getObjectEditBlocker } from "./objectGeometry";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

export type ObjectManagerSelectionActions = {
  appendStatusMessage: (message: string) => void;
  handleRemoveBuilding: (id: string) => void;
  reportObjectActionBlocker: (message: string) => void;
  setActivePlacementId: StateSetter<string | null>;
  setObjectClipboard: StateSetter<BuildingPlacement[]>;
  setObjectManagerStatusMessage: (message: string) => void;
  setPreviewInteraction: (value: "static" | "edit") => void;
  setSelectedObjectIds: StateSetter<string[]>;
  setStatusMessage: (message: string) => void;
};

export function runObjectManagerSelect({
  id,
  actions,
}: {
  id: string;
  actions: ObjectManagerSelectionActions;
}) {
  actions.setActivePlacementId(id);
  actions.setSelectedObjectIds([id]);
  actions.setPreviewInteraction("edit");
}

export function runObjectManagerToggleMultiSelect({
  id,
  checked,
  actions,
}: {
  id: string;
  checked: boolean;
  actions: ObjectManagerSelectionActions;
}) {
  actions.setSelectedObjectIds((prev) => {
    const next = checked
      ? Array.from(new Set([...prev, id]))
      : prev.filter((itemId) => itemId !== id);
    if (checked) actions.setActivePlacementId(id);
    return next;
  });
}

export function runObjectManagerSelectVisibleDraft({
  buildingPlacements,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerSelectionActions;
}) {
  const visibleDraftIds = getVisibleEditableDraftObjectIds(buildingPlacements);
  if (!visibleDraftIds.length) {
    actions.reportObjectActionBlocker("Select visible blocked: no visible editable draft objects are available.");
    return;
  }
  actions.setSelectedObjectIds(visibleDraftIds);
  actions.setActivePlacementId(visibleDraftIds[0] ?? null);
  const message = formatVisibleDraftSelectionMessage(visibleDraftIds.length);
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
}

export function runObjectManagerInvertSelection({
  buildingPlacements,
  selectedObjectIds,
  actions,
}: {
  buildingPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  actions: ObjectManagerSelectionActions;
}) {
  const visibleDraftIds = getVisibleEditableDraftObjectIds(buildingPlacements);
  if (!visibleDraftIds.length) {
    actions.reportObjectActionBlocker("Invert selection blocked: no visible editable draft objects are available.");
    return;
  }
  const { nextSelection, message } = invertVisibleDraftSelection({ visibleDraftIds, selectedObjectIds });
  actions.setSelectedObjectIds(nextSelection);
  actions.setActivePlacementId(nextSelection[0] ?? null);
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
}

export function runObjectManagerDelete({
  item,
  actions,
}: {
  item: BuildingPlacement;
  actions: ObjectManagerSelectionActions;
}) {
  const blocker = getObjectEditBlocker(item, "delete");
  if (blocker) {
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  actions.handleRemoveBuilding(item.id);
  actions.appendStatusMessage(`Deleted ${item.label}.`);
}

export function runObjectManagerCopy({
  item,
  actions,
}: {
  item: BuildingPlacement;
  actions: ObjectManagerSelectionActions;
}) {
  const blocker = getObjectEditBlocker(item, "copy");
  if (blocker) {
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  actions.setObjectClipboard([cloneBuildingPlacementForUndo(item)]);
  const message = `Copied ${item.label}. Use Paste to place an editable draft duplicate.`;
  actions.setObjectManagerStatusMessage(message);
  actions.setStatusMessage(message);
}
