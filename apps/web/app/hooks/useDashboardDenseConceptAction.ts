import { useCallback } from "react";

import type { BuildingPlacement, ChatMessage } from "../types";
import { createDenseCommercialConceptPlacements } from "../utils/demoWorkspaceData";
import type { RecentChange } from "../utils/dashboardTypes";
import type { ProjectStatusSummary, SidePanelKey, WorkspaceMode } from "../utils/workspaceShell";
import type { EngineeringSystemKey } from "../utils/workflowConstants";
import { SQFT_PER_ACRE } from "../utils/workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

type RecordRecentChange = (change: Omit<RecentChange, "id" | "createdAt">) => void;

type UseDashboardDenseConceptActionInput = {
  appendChatMessage: AppendChatMessage;
  clearGeneratedPreview: () => void;
  hasSiteBoundary: () => boolean;
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  recordRecentChange: RecordRecentChange;
  resolveLotBounds: () => { w: number; h: number };
  setActivePlacementId: StateSetter<string | null>;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setFitToSiteRequest: StateSetter<number>;
  setLotHeight: StateSetter<string>;
  setLotWidth: StateSetter<string>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setPreviewMode: StateSetter<"2d" | "3d">;
  setPreviewQuality: StateSetter<"standard" | "high">;
  setRenderedSidePanel: StateSetter<SidePanelKey | null>;
  setRightRailCollapsed: StateSetter<boolean>;
  setShowSiteBounds: StateSetter<boolean>;
  setSidePanelVisible: StateSetter<boolean>;
  setSiteScaleLocked: StateSetter<boolean>;
  setSiteSelectionMode: StateSetter<boolean>;
  updateProjectStatus: (summary: Omit<ProjectStatusSummary, "updatedAt">) => void;
};

export function useDashboardDenseConceptAction({
  appendChatMessage,
  clearGeneratedPreview,
  hasSiteBoundary,
  markSystemsStale,
  recordRecentChange,
  resolveLotBounds,
  setActivePlacementId,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setBuildingPlacements,
  setFitToSiteRequest,
  setLotHeight,
  setLotWidth,
  setPlacementModeEnabled,
  setPreviewInteraction,
  setPreviewMode,
  setPreviewQuality,
  setRenderedSidePanel,
  setRightRailCollapsed,
  setShowSiteBounds,
  setSidePanelVisible,
  setSiteScaleLocked,
  setSiteSelectionMode,
  updateProjectStatus,
}: UseDashboardDenseConceptActionInput) {
  return useCallback((message: string) => {
    appendChatMessage("user", message);
    const createdConceptSite = !hasSiteBoundary();
    if (createdConceptSite) {
      setLotWidth("1000");
      setLotHeight("1000");
      setSiteScaleLocked(true);
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setBuildingPlacements((prev) => [
        {
          id: `concept-site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: "Concept Site Boundary - 1000 ft x 1000 ft",
          type: "site",
          w: 1000,
          d: 1000,
          x: 0,
          y: 0,
          rotation: 0,
          locked: true,
          placed: true,
          source: "user",
          generated: false,
          capabilities: { movable: false, resizable: false, rotatable: false, deletable: false },
          systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
          meta: {
            category: "site",
            source_ui_mode: "chat_concept",
            site_boundary_state: "locked_concept_review_frame",
            engineering_status: "review_required",
            draft_review_required: true,
            construction_release_allowed: false,
            acres: Number((1_000_000 / SQFT_PER_ACRE).toFixed(3)),
          },
        },
        ...prev.filter((item) => item.type !== "site"),
      ]);
    }
    clearGeneratedPreview();
    const lot = createdConceptSite ? { w: 1000, h: 1000 } : resolveLotBounds();
    const conceptObjects = createDenseCommercialConceptPlacements(lot);
    setBuildingPlacements((prev) => {
      const keep = prev.filter((item) => item.type === "site" || !item.meta?.dense_concept_generated);
      return [...keep, ...conceptObjects];
    });
    markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
    setActivePlacementId(null);
    setPlacementModeEnabled(false);
    setPreviewMode("2d");
    setPreviewQuality("high");
    setPreviewInteraction("static");
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    setRightRailCollapsed(true);
    setFitToSiteRequest((value) => value + 1);
    recordRecentChange({
      type: "object_added",
      label: "Dense concept plan created",
      detail: "Office, parking, basin, driveway, sidewalks, water, sanitary, storm, inlet, outfall, hydrant, and manhole draft objects were placed.",
    });
    updateProjectStatus({
      state: "needs review",
      area: "setup",
      title: "Dense review concept created",
      detail: createdConceptSite
        ? "Created a 1000 ft by 1000 ft concept site and placed coherent editable building, parking, drainage, utilities, access, and sidewalk objects."
        : "Placed a coherent editable concept with building, parking, drainage, utilities, access, and sidewalk objects.",
      nextAction: "Edit the objects directly, then run Generate when the layout looks right.",
    });
    appendChatMessage(
      "assistant",
      createdConceptSite
        ? "Created a dense editable review concept on a 1000 ft by 1000 ft concept site: office building, two parking fields, detention basin, loop drive, driveway, sidewalk/ADA route, public water, public sanitary, storm sewer, inlets, outfall, hydrants, and sanitary manhole. Everything is draft review geometry and can be edited before Generate."
        : "Created a dense editable review concept: office building, two parking fields, detention basin, loop drive, driveway, sidewalk/ADA route, public water, public sanitary, storm sewer, inlets, outfall, hydrants, and sanitary manhole. Everything is draft review geometry and can be edited before Generate.",
      "status",
    );
    return true;
  }, [
    appendChatMessage,
    clearGeneratedPreview,
    hasSiteBoundary,
    markSystemsStale,
    recordRecentChange,
    resolveLotBounds,
    setActivePlacementId,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setBuildingPlacements,
    setFitToSiteRequest,
    setLotHeight,
    setLotWidth,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setPreviewQuality,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setShowSiteBounds,
    setSidePanelVisible,
    setSiteScaleLocked,
    setSiteSelectionMode,
    updateProjectStatus,
  ]);
}
