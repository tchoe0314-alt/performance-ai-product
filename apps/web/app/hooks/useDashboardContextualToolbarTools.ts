import { useMemo } from "react";

import { buildDashboardContextualToolbarTools } from "../utils/dashboardContextualToolbar";
import type { PrimaryWorkflowKey } from "../utils/dashboardTypes";
import type { SidePanelKey } from "../utils/workspaceShell";

type UseDashboardContextualToolbarToolsInput = {
  activePrimaryWorkflowKey: PrimaryWorkflowKey;
  handleApplySite: () => void | Promise<void>;
  handleOpenPanelFromDrawer: (panel: SidePanelKey) => void;
  handleStartSiteBoundaryDraw: () => void;
  handleUnlockSite: () => void;
  layerManagerOpen: boolean;
  previewInteraction: "static" | "edit";
  setLayerManagerOpen: (value: boolean | ((prev: boolean) => boolean)) => void;
  setPreviewInteraction: (value: "static" | "edit") => void;
  setShowCalculations: (value: boolean | ((prev: boolean) => boolean)) => void;
  setShowMeasurements: (value: boolean | ((prev: boolean) => boolean)) => void;
  showCalculations: boolean;
  showMeasurements: boolean;
  sidePanelForRender: SidePanelKey | null;
  siteScaleLocked: boolean;
};

export function useDashboardContextualToolbarTools({
  activePrimaryWorkflowKey,
  handleApplySite,
  handleOpenPanelFromDrawer,
  handleStartSiteBoundaryDraw,
  handleUnlockSite,
  layerManagerOpen,
  previewInteraction,
  setLayerManagerOpen,
  setPreviewInteraction,
  setShowCalculations,
  setShowMeasurements,
  showCalculations,
  showMeasurements,
  sidePanelForRender,
  siteScaleLocked,
}: UseDashboardContextualToolbarToolsInput) {
  return useMemo(
    () =>
      buildDashboardContextualToolbarTools({
        activePrimaryWorkflowKey,
        sidePanelForRender,
        siteScaleLocked,
        previewInteraction,
        showMeasurements,
        showCalculations,
        layerManagerOpen,
        onOpenPanel: handleOpenPanelFromDrawer,
        onToggleSiteLock: () => void handleApplySite(),
        onUnlockSite: handleUnlockSite,
        onStartSiteBoundaryDraw: handleStartSiteBoundaryDraw,
        onSetPreviewInteraction: setPreviewInteraction,
        onToggleMeasurements: () => setShowMeasurements((value) => !value),
        onToggleCalculations: () => setShowCalculations((value) => !value),
        onToggleLayerManager: () => setLayerManagerOpen((value) => !value),
      }),
    [
      activePrimaryWorkflowKey,
      handleApplySite,
      handleOpenPanelFromDrawer,
      handleStartSiteBoundaryDraw,
      handleUnlockSite,
      layerManagerOpen,
      previewInteraction,
      setLayerManagerOpen,
      setPreviewInteraction,
      setShowCalculations,
      setShowMeasurements,
      showCalculations,
      showMeasurements,
      sidePanelForRender,
      siteScaleLocked,
    ],
  );
}
