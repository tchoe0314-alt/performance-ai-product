import { useCallback, useEffect } from "react";
import type { Dispatch, MouseEvent as ReactMouseEvent, MutableRefObject, RefObject, SetStateAction } from "react";

import type { BuildingPlacement } from "../types";
import type { CadCommandHistoryEntry } from "./previewPanelTypes";
import {
  isCadCrossingSelection,
  isCadWindowSelectionTooSmall,
  resolveCadWindowSelectedObjectIds,
} from "../utils/previewCadWindowSelection";

type CadWindowSelect = {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  containerLeft: number;
  containerTop: number;
} | null;

type UsePreviewCadWindowSelectionOptions = {
  previewRef: RefObject<HTMLDivElement | null>;
  cadWindowSelect: CadWindowSelect;
  cadWindowSelectRef: MutableRefObject<CadWindowSelect>;
  setCadWindowSelect: Dispatch<SetStateAction<CadWindowSelect>>;
  visibleCadObjects: BuildingPlacement[];
  allowEdits: boolean;
  drawMode: string;
  placementMode: boolean;
  suppressNextObjectClickRef: MutableRefObject<boolean>;
  onSelectBuilding: (id: string | null) => void;
  onSelectObjects?: (ids: string[]) => void;
  setCadSelectionSet: Dispatch<SetStateAction<string[]>>;
  setSelectedVertex: Dispatch<SetStateAction<{ id: string; index: number } | null>>;
  pushCadCommandFeedback: (
    command: string,
    status: CadCommandHistoryEntry["status"],
    message: string,
  ) => void;
};

export function usePreviewCadWindowSelection({
  previewRef,
  cadWindowSelect,
  cadWindowSelectRef,
  setCadWindowSelect,
  visibleCadObjects,
  allowEdits,
  drawMode,
  placementMode,
  suppressNextObjectClickRef,
  onSelectBuilding,
  onSelectObjects,
  setCadSelectionSet,
  setSelectedVertex,
  pushCadCommandFeedback,
}: UsePreviewCadWindowSelectionOptions) {
  const finishCadWindowSelect = useCallback(
    (windowRect: { startX: number; startY: number; currentX: number; currentY: number }) => {
      if (!previewRef.current) return;
      const crossingSelect = isCadCrossingSelection(windowRect);
      if (isCadWindowSelectionTooSmall(windowRect)) return;
      const candidates = Array.from(
        previewRef.current.querySelectorAll<HTMLElement>("[data-cad-object-id]"),
      );
      const selectableIds = resolveCadWindowSelectedObjectIds(windowRect, candidates, visibleCadObjects);
      setCadSelectionSet(selectableIds);
      onSelectObjects?.(selectableIds);
      onSelectBuilding(selectableIds[0] ?? null);
      setSelectedVertex(null);
      pushCadCommandFeedback(
        "SELECT",
        selectableIds.length ? "applied" : "blocked",
        selectableIds.length
          ? `${crossingSelect ? "Crossing" : "Window"} selected ${selectableIds.length} editable draft object${selectableIds.length === 1 ? "" : "s"}.`
          : `${crossingSelect ? "Crossing" : "Window"} select found no editable draft objects.`,
      );
    },
    [
      onSelectBuilding,
      onSelectObjects,
      previewRef,
      pushCadCommandFeedback,
      setCadSelectionSet,
      setSelectedVertex,
      visibleCadObjects,
    ],
  );

  const beginCadWindowSelect = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      if (!allowEdits || drawMode !== "select" || placementMode || event.button !== 0) return false;
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("button,input,textarea,select,[role='button'],[data-no-window-select]")) {
        return false;
      }
      const objectOverlay = target?.closest?.("[data-object-overlay]") as HTMLElement | null;
      if (objectOverlay) {
        const item = visibleCadObjects.find((candidate) => candidate.id === objectOverlay.dataset.cadObjectId);
        if (item?.type !== "site") return false;
      }
      const rect = previewRef.current?.getBoundingClientRect();
      event.preventDefault();
      event.stopPropagation();
      suppressNextObjectClickRef.current = true;
      setCadWindowSelect({
        startX: event.clientX,
        startY: event.clientY,
        currentX: event.clientX,
        currentY: event.clientY,
        containerLeft: rect?.left ?? 0,
        containerTop: rect?.top ?? 0,
      });
      return true;
    },
    [allowEdits, drawMode, placementMode, previewRef, setCadWindowSelect, suppressNextObjectClickRef, visibleCadObjects],
  );

  useEffect(() => {
    cadWindowSelectRef.current = cadWindowSelect;
  }, [cadWindowSelect, cadWindowSelectRef]);

  useEffect(() => {
    if (!cadWindowSelect) return;
    const handleMove = (event: MouseEvent) => {
      setCadWindowSelect((current) =>
        current ? { ...current, currentX: event.clientX, currentY: event.clientY } : current,
      );
    };
    const handleUp = () => {
      const selection = cadWindowSelectRef.current;
      if (selection) finishCadWindowSelect(selection);
      cadWindowSelectRef.current = null;
      setCadWindowSelect(null);
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp, { once: true });
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [cadWindowSelect, cadWindowSelectRef, finishCadWindowSelect, setCadWindowSelect]);

  return { beginCadWindowSelect, finishCadWindowSelect };
}
