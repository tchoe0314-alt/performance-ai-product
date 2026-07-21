import { useCallback, useMemo } from "react";
import type { MutableRefObject } from "react";

import type { BuildingPlacement } from "../types";
import {
  runDashboardPlaceBuilding,
  runDashboardPlaceObject,
  runDashboardSelectPlacementTarget,
} from "../utils/dashboardPlacementActions";
import { runDashboardCreateCustomGeometry } from "../utils/dashboardCustomGeometryActions";
import type { DashboardCustomGeometryPayload } from "../utils/dashboardCustomGeometryActions";
import type { EngineeringSystemKey } from "../utils/workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type PreviewInteraction = "static" | "edit";
type PreviewMode = "2d" | "3d";
type LotBounds = { x: number; y: number; w: number; h: number };

type UseDashboardPlacementActionHandlersInput = {
  activePlacementId: string | null;
  askClarification: (question: string, action: string, payload?: Record<string, unknown>) => void;
  buildDefaultPolyline: (bounds: { x: number; y: number; w: number; d: number }) => Array<[number, number]>;
  buildingPlacements: BuildingPlacement[];
  buildingPlacementsRef: MutableRefObject<BuildingPlacement[]>;
  clearGeneratedPreview: () => void;
  debugLog: (label: string, payload?: Record<string, unknown>) => void;
  ensureSiteBoundary: (reason: string) => boolean;
  handleUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  persistDraftRefresh: (reason: string) => void;
  resolveDefaultBuildingDims: () => { w: number; d: number };
  resolveLotBounds: () => LotBounds;
  setActivePlacementId: StateSetter<string | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: (value: PreviewInteraction) => void;
  setPreviewMode: (value: PreviewMode) => void;
  setSelectedObjectIds: StateSetter<string[]>;
  setStatusMessage: (message: string) => void;
  siteScaleLocked: boolean;
  systemsImpactedByPlacement: (target?: Partial<BuildingPlacement> | null) => EngineeringSystemKey[];
  units: string;
};

export function useDashboardPlacementActionHandlers({
  activePlacementId,
  askClarification,
  buildDefaultPolyline,
  buildingPlacements,
  buildingPlacementsRef,
  clearGeneratedPreview,
  debugLog,
  ensureSiteBoundary,
  handleUpdateBuilding,
  markSystemsStale,
  persistDraftRefresh,
  resolveDefaultBuildingDims,
  resolveLotBounds,
  setActivePlacementId,
  setBuildingPlacements,
  setPlacementModeEnabled,
  setPreviewInteraction,
  setPreviewMode,
  setSelectedObjectIds,
  setStatusMessage,
  siteScaleLocked,
  systemsImpactedByPlacement,
  units,
}: UseDashboardPlacementActionHandlersInput) {
  const handleToggleBuildingLock = useCallback((id: string) => {
    const target = buildingPlacements.find((item) => item.id === id);
    if (!target) return;
    handleUpdateBuilding(id, { locked: !target.locked });
  }, [buildingPlacements, handleUpdateBuilding]);

  const dashboardPlacementActions = useMemo(() => ({
    askClarification,
    buildDefaultPolyline,
    clearGeneratedPreview,
    debugLog,
    ensureSiteBoundary,
    markSystemsStale,
    persistDraftRefresh,
    resolveDefaultBuildingDims,
    resolveLotBounds,
    setActivePlacementId,
    setBuildingPlacements,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
  }), [
    askClarification,
    buildDefaultPolyline,
    clearGeneratedPreview,
    debugLog,
    ensureSiteBoundary,
    markSystemsStale,
    persistDraftRefresh,
    resolveDefaultBuildingDims,
    resolveLotBounds,
    setActivePlacementId,
    setBuildingPlacements,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
  ]);

  const handlePlaceBuilding = useCallback(
    (position: { x: number; y: number }) => {
      runDashboardPlaceBuilding({
        position,
        activePlacementId,
        buildingPlacements,
        siteScaleLocked,
        actions: dashboardPlacementActions,
      });
    },
    [activePlacementId, buildingPlacements, dashboardPlacementActions, siteScaleLocked],
  );

  const handlePlaceObject = useCallback(
    (id: string, position: { x: number; y: number }) => {
      runDashboardPlaceObject({
        id,
        position,
        buildingPlacements,
        siteScaleLocked,
        actions: dashboardPlacementActions,
      });
    },
    [buildingPlacements, dashboardPlacementActions, siteScaleLocked],
  );

  const dashboardCustomGeometryActions = useMemo(() => ({
    clearGeneratedPreview,
    ensureSiteBoundary,
    markSystemsStale,
    persistDraftRefresh,
    resolveLotBounds,
    setActivePlacementId,
    setBuildingPlacements,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setSelectedObjectIds,
    setStatusMessage,
  }), [
    clearGeneratedPreview,
    ensureSiteBoundary,
    markSystemsStale,
    persistDraftRefresh,
    resolveLotBounds,
    setActivePlacementId,
    setBuildingPlacements,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setSelectedObjectIds,
    setStatusMessage,
  ]);

  const handleCreateCustomGeometry = useCallback(
    (payload: DashboardCustomGeometryPayload) => {
      runDashboardCreateCustomGeometry({
        payload,
        buildingPlacementsRef,
        siteScaleLocked,
        units: units || "ft",
        actions: dashboardCustomGeometryActions,
      });
    },
    [buildingPlacementsRef, dashboardCustomGeometryActions, siteScaleLocked, units],
  );

  const handleSelectPlacementTarget = useCallback((id: string) => {
    runDashboardSelectPlacementTarget({
      id,
      buildingPlacements,
      actions: dashboardPlacementActions,
    });
  }, [buildingPlacements, dashboardPlacementActions]);

  return {
    handleCreateCustomGeometry,
    handlePlaceBuilding,
    handlePlaceObject,
    handleSelectPlacementTarget,
    handleToggleBuildingLock,
  };
}
