import { useCallback } from "react";

import type { BuildingPlacement, ChatMessage, SourceConfidenceEntry } from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;

type UseDashboardFloatingObjectActionsOptions = {
  appendChatMessage: AppendChatMessage;
  handleOpenPanelFromDrawer: (panel: SidePanelKey) => void;
  selectedBuilding: BuildingPlacement | null;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setFocusObjectId: StateSetter<string | null>;
  setMoveEditFeedback: (message: string) => void;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setStatusMessage: (message: string) => void;
  sourceConfidenceByObjectId: Map<string, SourceConfidenceEntry>;
};

export function useDashboardFloatingObjectActions({
  appendChatMessage,
  handleOpenPanelFromDrawer,
  selectedBuilding,
  setActiveSidePanel,
  setFocusObjectId,
  setMoveEditFeedback,
  setPlacementModeEnabled,
  setPreviewInteraction,
  setStatusMessage,
  sourceConfidenceByObjectId,
}: UseDashboardFloatingObjectActionsOptions) {
  const selectedObjectConfidence = selectedBuilding
    ? sourceConfidenceByObjectId.get(selectedBuilding.id)
    : null;

  const handleEditFloatingSelectedObject = useCallback(() => {
    if (!selectedBuilding) {
      return;
    }
    if (selectedBuilding.locked || selectedBuilding.capabilities?.movable === false) {
      const message = `Move/edit needs ${selectedBuilding.label} to be unlocked and movable.`;
      setPlacementModeEnabled(false);
      setMoveEditFeedback(message);
      setStatusMessage(message);
      appendChatMessage("assistant", message, "status");
      return;
    }
    setPlacementModeEnabled(true);
    setPreviewInteraction("edit");
    const message = `Move/edit mode active for ${selectedBuilding.label}.`;
    setMoveEditFeedback(message);
    setStatusMessage(`${message} Drag it on the canvas or use object details.`);
  }, [
    appendChatMessage,
    selectedBuilding,
    setMoveEditFeedback,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setStatusMessage,
  ]);

  const handleFocusFloatingSelectedObject = useCallback(() => {
    if (!selectedBuilding) {
      return;
    }
    setFocusObjectId(selectedBuilding.id);
    setActiveSidePanel(null);
  }, [selectedBuilding, setActiveSidePanel, setFocusObjectId]);

  const handleOpenFloatingObjectDetails = useCallback(() => {
    handleOpenPanelFromDrawer("details");
  }, [handleOpenPanelFromDrawer]);

  return {
    handleEditFloatingSelectedObject,
    handleFocusFloatingSelectedObject,
    handleOpenFloatingObjectDetails,
    selectedObjectConfidence,
  };
}
