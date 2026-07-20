import { useCallback } from "react";
import type { MutableRefObject } from "react";

import type { BuildingPlacement, PlanResponse, ProjectInput, ProjectRecord } from "../types";
import { systemsImpactedByPlacement } from "../utils/dashboardGenerateLayoutContext";
import type { DraftUndoAction, RecentChange } from "../utils/dashboardTypes";
import type { EngineeringSystemKey } from "../utils/workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type SaveProject = (options?: {
  silent?: boolean;
  projectIdOverride?: string | null;
  nameOverride?: string;
  fileNameOverride?: string;
  projectInputOverride?: ProjectInput;
  latestResultOverride?: PlanResponse;
  autoNamedOverride?: boolean;
  autoFileNamedOverride?: boolean;
}) => Promise<ProjectRecord | null>;

type UseDashboardObjectRemoveRestoreActionsInput = {
  activePlacementId: string | null;
  buildingPlacements: BuildingPlacement[];
  clearGeneratedPreview: () => void;
  debugLog: (label: string, payload?: Record<string, unknown>) => void;
  ensureProjectDraftRef: MutableRefObject<() => Promise<string | null>>;
  markSystemsStale: (systems?: EngineeringSystemKey[]) => void;
  previewRefreshIntentRef: MutableRefObject<{ reason: string; track?: boolean } | null>;
  pushRecoveryMessage: (message: string) => void;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  recordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  saveProjectRef: MutableRefObject<SaveProject>;
  setActivePlacementId: StateSetter<string | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setFocusObjectId: StateSetter<string | null>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setSelectedObjectIds: StateSetter<string[]>;
  setStatusMessage: (message: string) => void;
};

export function useDashboardObjectRemoveRestoreActions({
  activePlacementId,
  buildingPlacements,
  clearGeneratedPreview,
  debugLog,
  ensureProjectDraftRef,
  markSystemsStale,
  previewRefreshIntentRef,
  pushRecoveryMessage,
  recordDraftUndoAction,
  recordRecentChange,
  saveProjectRef,
  setActivePlacementId,
  setBuildingPlacements,
  setFocusObjectId,
  setPlacementModeEnabled,
  setSelectedObjectIds,
  setStatusMessage,
}: UseDashboardObjectRemoveRestoreActionsInput) {
  const handleRemoveBuilding = useCallback((id: string) => {
    clearGeneratedPreview();
    const target = buildingPlacements.find((item) => item.id === id);
    const combinedSourceIds = target && Array.isArray(target.meta?.combined_from_object_ids)
      ? target.meta.combined_from_object_ids.map((sourceId) => String(sourceId)).filter(Boolean)
      : [];
    const relatedSourceObjects = combinedSourceIds.length
      ? buildingPlacements.filter((item) => combinedSourceIds.includes(item.id))
      : [];
    debugLog("remove-object", { id });
    const removedIds = new Set([id, ...relatedSourceObjects.map((item) => item.id)]);
    setBuildingPlacements((prev) => prev.filter((item) => !removedIds.has(item.id)));
    setActivePlacementId((prev) => (prev && removedIds.has(prev) ? null : prev));
    setSelectedObjectIds((prev) => prev.filter((itemId) => !removedIds.has(itemId)));
    setPlacementModeEnabled((prev) => (activePlacementId === id ? false : prev));
    setFocusObjectId((prev) => (prev && removedIds.has(prev) ? null : prev));
    markSystemsStale(systemsImpactedByPlacement(target));
    if (target) {
      const removedObjects = [target, ...relatedSourceObjects].map((item) => ({
        ...item,
        geometry: item.geometry?.map(([x, y]) => [x, y] as [number, number]),
        meta: item.meta ? { ...item.meta } : item.meta,
        capabilities: item.capabilities ? { ...item.capabilities } : item.capabilities,
      }));
      const undo: DraftUndoAction = removedObjects.length === 1
        ? { action: "delete", object: target }
        : { action: "delete_many", objects: removedObjects, label: "combined object delete" };
      recordDraftUndoAction(undo);
      recordRecentChange({
        type: "object_deleted",
        label: "Object deleted",
        detail: relatedSourceObjects.length
          ? `${target.label} and ${relatedSourceObjects.length} hidden source trace piece${relatedSourceObjects.length === 1 ? "" : "s"} were removed from the draft layout.`
          : `${target.label} was removed from the draft layout.`,
        undo,
      });
      pushRecoveryMessage(relatedSourceObjects.length
        ? `Deleted ${target.label} and ${relatedSourceObjects.length} hidden source trace piece${relatedSourceObjects.length === 1 ? "" : "s"}. Undo can restore the combined draft group.`
        : `Deleted ${target.label}. Undo can restore this draft object.`);
    } else {
      setStatusMessage("Object removed. Regenerate systems to reflect the new layout.");
    }
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object removal...", track: true });
  }, [
    activePlacementId,
    buildingPlacements,
    clearGeneratedPreview,
    debugLog,
    ensureProjectDraftRef,
    markSystemsStale,
    previewRefreshIntentRef,
    pushRecoveryMessage,
    recordDraftUndoAction,
    recordRecentChange,
    saveProjectRef,
    setActivePlacementId,
    setBuildingPlacements,
    setFocusObjectId,
    setPlacementModeEnabled,
    setSelectedObjectIds,
    setStatusMessage,
  ]);

  const handleRestoreBuilding = useCallback((snapshot: BuildingPlacement) => {
    clearGeneratedPreview();
    setBuildingPlacements((prev) => {
      if (prev.some((item) => item.id === snapshot.id)) return prev;
      return [...prev, { ...snapshot }];
    });
    markSystemsStale(systemsImpactedByPlacement(snapshot));
    recordRecentChange({
      type: "object_added",
      label: "Object restored",
      detail: `${snapshot.label} was restored from undo.`,
      undoBlockedReason: "Restore is already an undo result; use object delete if you need to remove it again.",
    });
    pushRecoveryMessage(`Undo: restored ${snapshot.label}. Generated systems may be stale.`);
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => {
        previewRefreshIntentRef.current = {
          reason: "Refreshing preview after undo restore...",
          track: true,
        };
      });
  }, [
    clearGeneratedPreview,
    ensureProjectDraftRef,
    markSystemsStale,
    previewRefreshIntentRef,
    pushRecoveryMessage,
    recordRecentChange,
    saveProjectRef,
    setBuildingPlacements,
  ]);

  return {
    handleRemoveBuilding,
    handleRestoreBuilding,
  };
}
