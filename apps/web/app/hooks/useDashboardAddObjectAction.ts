import { useCallback } from "react";

import type { BuildingPlacement, SiteObjectType } from "../types";
import {
  buildDashboardObjectPlacement,
  buildDashboardSitePlacement,
} from "../utils/dashboardObjectPlacementBuilder";
import { systemsImpactedByPlacement } from "../utils/dashboardGenerateLayoutContext";
import type { DraftUndoAction, RecentChange } from "../utils/dashboardTypes";
import { parsePositiveNumber } from "../utils/formatting";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import type { EngineeringSystemKey } from "../utils/workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AddObjectOptions = {
  label?: string;
  style?: Record<string, string>;
  geometryType?: "polygon" | "polyline" | "rect";
  placed?: boolean;
  width?: number;
  depth?: number;
  stallCount?: number;
  meta?: Record<string, unknown>;
};
type ParkingFootprint = {
  maxStalls: number;
  moduleCols: number;
  moduleRows: number;
};
type ParkingFootprintParams = {
  stallWidth: number;
  stallDepth: number;
  aisleWidth: number;
  adaAisleWidth: number;
  adaCount: number;
  compactCount: number;
  compactWidth: number;
  angleDeg: number;
  loading: "single" | "double";
  autoResizeToFitCount: boolean;
  useMixedAngles: boolean;
  compactZone: boolean;
};

type UseDashboardAddObjectActionInput = {
  buildingPlacements: BuildingPlacement[];
  clearGeneratedPreview: () => void;
  computeParkingFootprint: (
    target: BuildingPlacement,
    params: ParkingFootprintParams,
    stallCount: number,
  ) => ParkingFootprint;
  debugLog: (label: string, payload?: Record<string, unknown>) => void;
  ensureSiteBoundary: (reason: string) => boolean;
  formatObjectLabel: (type: SiteObjectType, count: number) => string;
  hasSiteBoundary: () => boolean;
  lotHeight: string;
  lotWidth: string;
  markSystemsStale: (systems?: EngineeringSystemKey[]) => void;
  parkingAdaAisleWidth: string;
  parkingAdaCount: string;
  parkingAisleWidth: string;
  parkingAngle: string;
  parkingCompactCount: string;
  parkingCompactWidth: string;
  parkingCount: string;
  parkingLoading: "single" | "double";
  parkingStallDepth: string;
  parkingStallWidth: string;
  pushRecoveryMessage: (message: string) => void;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  recordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  resolveDefaultBuildingDims: () => { w: number; d: number };
  resolveLotBounds: () => { w: number; h: number };
  setActivePlacementId: StateSetter<string | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setLotHeight: StateSetter<string>;
  setLotWidth: StateSetter<string>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setPreviewMode: StateSetter<"2d" | "3d">;
  setPreviewQuality: StateSetter<"standard" | "high">;
};

export function useDashboardAddObjectAction({
  buildingPlacements,
  clearGeneratedPreview,
  computeParkingFootprint,
  debugLog,
  ensureSiteBoundary,
  formatObjectLabel,
  hasSiteBoundary,
  lotHeight,
  lotWidth,
  markSystemsStale,
  parkingAdaAisleWidth,
  parkingAdaCount,
  parkingAisleWidth,
  parkingAngle,
  parkingCompactCount,
  parkingCompactWidth,
  parkingCount,
  parkingLoading,
  parkingStallDepth,
  parkingStallWidth,
  pushRecoveryMessage,
  recordDraftUndoAction,
  recordRecentChange,
  resolveDefaultBuildingDims,
  resolveLotBounds,
  setActivePlacementId,
  setBuildingPlacements,
  setLotHeight,
  setLotWidth,
  setPlacementModeEnabled,
  setPreviewInteraction,
  setPreviewMode,
  setPreviewQuality,
}: UseDashboardAddObjectActionInput) {
  return useCallback(
    (
      type: SiteObjectType,
      options?: AddObjectOptions,
    ) => {
      const catalog = SITE_OBJECT_CATALOG[type];
      if (!catalog) return;
      clearGeneratedPreview();
      if (type === "site") {
        const width = parsePositiveNumber(lotWidth) ?? catalog.defaultW;
        const height = parsePositiveNumber(lotHeight) ?? catalog.defaultD;
        if (!parsePositiveNumber(lotWidth)) setLotWidth(String(width));
        if (!parsePositiveNumber(lotHeight)) setLotHeight(String(height));
        setBuildingPlacements((prev) => {
          const filtered = prev.filter((item) => item.type !== "site");
          const sitePlacement = buildDashboardSitePlacement({ width, height });
          return [sitePlacement, ...filtered];
        });
        return;
      }
      if (!hasSiteBoundary()) {
        const ok = ensureSiteBoundary("You can adjust the site size anytime.");
        if (!ok) return;
      }
      const lot = resolveLotBounds();
      const existingCount =
        buildingPlacements.filter((item) => item.type === type).length + 1;
      const autoPlaced = Boolean(options?.placed);
      const nextPlacement = buildDashboardObjectPlacement({
        type,
        options,
        lot,
        existingPlacements: buildingPlacements,
        existingCount,
        defaultDimensions:
          type === "building" ? resolveDefaultBuildingDims() : { w: catalog.defaultW, d: catalog.defaultD },
        fallbackLabel: formatObjectLabel(type, existingCount),
        parkingControls: {
          parkingCount,
          parkingStallWidth,
          parkingStallDepth,
          parkingAisleWidth,
          parkingAdaAisleWidth,
          parkingAdaCount,
          parkingCompactCount,
          parkingCompactWidth,
          parkingAngle,
          parkingLoading,
        },
        computeParkingFootprint,
      });
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      markSystemsStale(systemsImpactedByPlacement(nextPlacement));
      setActivePlacementId(autoPlaced ? null : nextPlacement.id);
      setPlacementModeEnabled(!autoPlaced);
      setPreviewMode("2d");
      setPreviewQuality("standard");
      setPreviewInteraction(autoPlaced ? "static" : "edit");
      recordDraftUndoAction({ action: "add", object: nextPlacement });
      recordRecentChange({
        type: "object_added",
        label: "Object added",
        detail: `${nextPlacement.label} was added as draft geometry.`,
        undo: { action: "add", object: nextPlacement },
      });
      pushRecoveryMessage(`Added ${nextPlacement.label}. Undo can remove this draft object.`);
      debugLog("add-object", {
        id: nextPlacement.id,
        type: nextPlacement.type,
      });
    },
    [
      buildingPlacements,
      clearGeneratedPreview,
      computeParkingFootprint,
      debugLog,
      ensureSiteBoundary,
      formatObjectLabel,
      hasSiteBoundary,
      lotHeight,
      lotWidth,
      markSystemsStale,
      parkingAdaAisleWidth,
      parkingAdaCount,
      parkingAisleWidth,
      parkingAngle,
      parkingCompactCount,
      parkingCompactWidth,
      parkingCount,
      parkingLoading,
      parkingStallDepth,
      parkingStallWidth,
      pushRecoveryMessage,
      recordDraftUndoAction,
      recordRecentChange,
      resolveDefaultBuildingDims,
      resolveLotBounds,
      setActivePlacementId,
      setBuildingPlacements,
      setLotHeight,
      setLotWidth,
      setPlacementModeEnabled,
      setPreviewInteraction,
      setPreviewMode,
      setPreviewQuality,
    ],
  );
}
