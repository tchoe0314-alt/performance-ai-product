import { useEffect, useRef } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { flushSync } from "react-dom";

import type { BuildingPlacement } from "../types";
import type { CadToolRequest, DrawMode } from "../utils/cadToolTypes";
import { handlePreviewCadToolRequest } from "../utils/previewCadActiveCommand";
import type { CadActiveCommand } from "./previewPanelTypes";

type CadCommandFeedbackStatus = "applied" | "blocked" | "info";
type SelectionIndex = { id: string; index: number } | null;

type PreviewCadToolRequestEffectArgs = {
  cadToolRequest?: CadToolRequest | null;
  lotWidth: number;
  lotHeight: number;
  cadOffsetDistance: string;
  selectedDeletableObject: BuildingPlacement | null;
  setDraftPoints: (points: Array<[number, number]>) => void;
  draftPointsRef?: MutableRefObject<Array<[number, number]>>;
  setDraftPreviewPoint: (point: [number, number] | null) => void;
  setDrawAutoFinishPointCount: (count: number | null) => void;
  setCadActiveCommand: (command: CadActiveCommand | null) => void;
  setCadCommandDraft: (command: string | ((value: string) => string)) => void;
  setDrawMode: (mode: DrawMode) => void;
  setManagedObjectId: (id: string | null) => void;
  setHoveredObjectId: (id: string | null) => void;
  setSelectedVertex: Dispatch<SetStateAction<SelectionIndex>>;
  setCadSelectionSet: (ids: string[]) => void;
  setCadSnapEnabled: Dispatch<SetStateAction<boolean>>;
  setCadOrthoEnabled: Dispatch<SetStateAction<boolean>>;
  onSelectBuilding: (id: string | null) => void;
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  onRemoveBuilding: (id: string) => void;
  transformSelectedCadObjects: (operation: "move" | "rotate" | "scale" | "flip_horizontal" | "flip_vertical", value?: string) => void;
  offsetSelectedCadObjectBy: (valueOverride?: string) => void;
  trimExtendSelectedCadObject: (operationOverride: "trim" | "extend", amountOverride?: string) => void;
  filletSelectedCadObject: () => void;
  joinSelectedCadObjects: () => void;
  splitSelectedJoinedObject: () => void;
  changeSelectedPolylineState: (operation: "close" | "open" | "reverse") => void;
  toggleSelectedCadHatch: () => void;
  applySelectedCadDimension: () => void;
  insertCadSymbol: () => void;
  applySelectedCadLayer: () => void;
  applyCadProperties: () => void;
  undoCadCommand: () => void;
  redoCadCommand: () => void;
  runCadCommand: (commandOverride?: string) => void;
  pushCadCommandFeedback: (command: string, status: CadCommandFeedbackStatus, message: string) => void;
};

type PreviewCadShortcutEffectArgs = {
  canDrawObjects: boolean;
  selectedCadCount: number;
  setDraftPoints: (points: Array<[number, number]>) => void;
  setDraftPreviewPoint: (point: [number, number] | null) => void;
  setDrawMode: (mode: DrawMode) => void;
  setCadSnapEnabled: Dispatch<SetStateAction<boolean>>;
  setCadOrthoEnabled: Dispatch<SetStateAction<boolean>>;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  moveSelectedCadObjectsByVector: (dx: number, dy: number) => void;
  transformSelectedCadObjects: (operation: "move" | "rotate" | "scale" | "flip_horizontal" | "flip_vertical", value?: string) => void;
};

export function usePreviewCadToolRequestEffect({
  cadToolRequest,
  lotWidth,
  lotHeight,
  cadOffsetDistance,
  selectedDeletableObject,
  setDraftPoints,
  draftPointsRef,
  setDraftPreviewPoint,
  setDrawAutoFinishPointCount,
  setCadActiveCommand,
  setCadCommandDraft,
  setDrawMode,
  setManagedObjectId,
  setHoveredObjectId,
  setSelectedVertex,
  setCadSelectionSet,
  setCadSnapEnabled,
  setCadOrthoEnabled,
  onSelectBuilding,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onRemoveBuilding,
  transformSelectedCadObjects,
  offsetSelectedCadObjectBy,
  trimExtendSelectedCadObject,
  filletSelectedCadObject,
  joinSelectedCadObjects,
  splitSelectedJoinedObject,
  changeSelectedPolylineState,
  toggleSelectedCadHatch,
  applySelectedCadDimension,
  insertCadSymbol,
  applySelectedCadLayer,
  applyCadProperties,
  undoCadCommand,
  redoCadCommand,
  runCadCommand,
  pushCadCommandFeedback,
}: PreviewCadToolRequestEffectArgs) {
  const lastCadToolRequestIdRef = useRef(0);

  useEffect(() => {
    if (!cadToolRequest || cadToolRequest.id === lastCadToolRequestIdRef.current) return;
    lastCadToolRequestIdRef.current = cadToolRequest.id;
    handlePreviewCadToolRequest({
      cadToolRequest,
      lotWidth,
      lotHeight,
      cadOffsetDistance,
      selectedDeletableObject,
      setDraftPoints,
      draftPointsRef,
      setDraftPreviewPoint,
      setDrawAutoFinishPointCount,
      setCadActiveCommand,
      setCadCommandDraft,
      setDrawMode,
      setManagedObjectId,
      setHoveredObjectId,
      setSelectedVertex,
      setCadSelectionSet,
      setCadSnapEnabled,
      setCadOrthoEnabled,
      onSelectBuilding,
      onSetPreviewMode,
      onSetPreviewInteraction,
      onRemoveBuilding,
      transformSelectedCadObjects,
      offsetSelectedCadObjectBy,
      trimExtendSelectedCadObject,
      filletSelectedCadObject,
      joinSelectedCadObjects,
      splitSelectedJoinedObject,
      changeSelectedPolylineState,
      toggleSelectedCadHatch,
      applySelectedCadDimension,
      insertCadSymbol,
      applySelectedCadLayer,
      applyCadProperties,
      undoCadCommand,
      redoCadCommand,
      runCadCommand,
      pushCadCommandFeedback,
    });
  }, [
    applyCadProperties,
    applySelectedCadDimension,
    applySelectedCadLayer,
    cadOffsetDistance,
    cadToolRequest,
    changeSelectedPolylineState,
    draftPointsRef,
    filletSelectedCadObject,
    insertCadSymbol,
    joinSelectedCadObjects,
    lotHeight,
    lotWidth,
    offsetSelectedCadObjectBy,
    onRemoveBuilding,
    onSelectBuilding,
    onSetPreviewInteraction,
    onSetPreviewMode,
    pushCadCommandFeedback,
    redoCadCommand,
    runCadCommand,
    selectedDeletableObject,
    setCadActiveCommand,
    setCadCommandDraft,
    setCadOrthoEnabled,
    setCadSelectionSet,
    setCadSnapEnabled,
    setDraftPoints,
    setDraftPreviewPoint,
    setDrawAutoFinishPointCount,
    setDrawMode,
    setHoveredObjectId,
    setManagedObjectId,
    setSelectedVertex,
    splitSelectedJoinedObject,
    toggleSelectedCadHatch,
    transformSelectedCadObjects,
    trimExtendSelectedCadObject,
    undoCadCommand,
  ]);
}

export function usePreviewCadShortcutEffect({
  canDrawObjects,
  selectedCadCount,
  setDraftPoints,
  setDraftPreviewPoint,
  setDrawMode,
  setCadSnapEnabled,
  setCadOrthoEnabled,
  onSetPreviewInteraction,
  moveSelectedCadObjectsByVector,
  transformSelectedCadObjects,
}: PreviewCadShortcutEffectArgs) {
  useEffect(() => {
    const handleCadShortcuts = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("input, textarea, select, [contenteditable='true']")) return;
      const key = event.key.toLowerCase();
      const command = event.metaKey || event.ctrlKey;
      // Modified shortcuts belong to the unified workspace history and
      // clipboard. Canvas edits already record there through onUpdateBuilding;
      // handling them again here made Cmd/Ctrl+Z undo an older canvas edit and
      // made Cmd/Ctrl+V look like the plain V selection shortcut.
      if (command) return;
      if (["arrowup", "arrowdown", "arrowleft", "arrowright"].includes(key)) {
        if (!selectedCadCount) return;
        event.preventDefault();
        const step = event.altKey ? 1 : event.shiftKey ? 25 : 5;
        const dx = key === "arrowleft" ? -step : key === "arrowright" ? step : 0;
        const dy = key === "arrowup" ? -step : key === "arrowdown" ? step : 0;
        moveSelectedCadObjectsByVector(dx, dy);
        return;
      }
      if (key === "v") {
        event.preventDefault();
        setDrawMode("select");
        return;
      }
      if (key === "l") {
        event.preventDefault();
        if (canDrawObjects) {
          setDraftPoints([]);
          setDraftPreviewPoint(null);
          setDrawMode("polyline");
          onSetPreviewInteraction("edit");
        }
        return;
      }
      if (key === "a") {
        event.preventDefault();
        if (canDrawObjects) {
          setDraftPoints([]);
          setDraftPreviewPoint(null);
          setDrawMode("polygon");
          onSetPreviewInteraction("edit");
        }
        return;
      }
      if (key === "o") {
        event.preventDefault();
        // Drafting modifiers must be active before the next pointer event. A
        // hosted map can otherwise receive a fast follow-up click while React
        // still has the previous Ortho value in the drawing callback.
        flushSync(() => setCadOrthoEnabled((value) => !value));
        return;
      }
      if (key === "s") {
        event.preventDefault();
        flushSync(() => setCadSnapEnabled((value) => !value));
        return;
      }
      if (key === "m") {
        event.preventDefault();
        transformSelectedCadObjects("move");
        return;
      }
      if (key === "r") {
        event.preventDefault();
        transformSelectedCadObjects("rotate");
      }
    };
    // Map canvases and other interactive preview surfaces may stop bubbling
    // keyboard events. Capture drafting shortcuts before those surfaces so
    // Ortho, Snap, and tool keys behave the same over imagery and local canvas.
    window.addEventListener("keydown", handleCadShortcuts, { capture: true });
    return () => window.removeEventListener("keydown", handleCadShortcuts, { capture: true });
  }, [
    canDrawObjects,
    moveSelectedCadObjectsByVector,
    onSetPreviewInteraction,
    selectedCadCount,
    setCadOrthoEnabled,
    setCadSnapEnabled,
    setDraftPoints,
    setDraftPreviewPoint,
    setDrawMode,
    transformSelectedCadObjects,
  ]);
}
