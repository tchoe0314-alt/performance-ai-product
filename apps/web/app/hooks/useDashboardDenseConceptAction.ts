import { useCallback } from "react";

import type { BuildingPlacement, ChatMessage } from "../types";
import {
  createDenseCommercialConceptPlacements,
  createDenseSubdivisionCadPlanPlacements,
  createUrbanizationCampusPlanPlacements,
} from "../utils/demoWorkspaceData";
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
  setCommandBarExpanded: StateSetter<boolean>;
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
  setCommandBarExpanded,
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
    const lower = message.toLowerCase();
    const wantsSubdivisionCadPlan =
      /\b(recreate|copy|like the image|like this image|subdivision|master plan|lots?|parcels?|contours?|cad screenshot|as many)\b/.test(lower) &&
      /\b(image|plan|site|cad|subdivision|lots?|parcels?|contours?|dense|stuff)\b/.test(lower);
    const wantsUrbanizationCampusPlan =
      /\b(urbanization|campus|boulevard|plaza|municipal|park|parks|master plan|site model|3d massing|massing|community|civic)\b/.test(lower) &&
      /\b(plan|site|layout|model|3d|buildings?|roads?|paths?|parking|trees?|plaza|like this|image)\b/.test(lower);
    const createdConceptSite = !hasSiteBoundary();
    if (createdConceptSite) {
      const conceptWidth = wantsUrbanizationCampusPlan ? 1120 : wantsSubdivisionCadPlan ? 1200 : 1000;
      const conceptHeight = wantsUrbanizationCampusPlan ? 720 : wantsSubdivisionCadPlan ? 820 : 1000;
      setLotWidth(String(conceptWidth));
      setLotHeight(String(conceptHeight));
      setSiteScaleLocked(true);
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setBuildingPlacements((prev) => [
        {
          id: `concept-site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: wantsUrbanizationCampusPlan
              ? "Concept Site Boundary - 1120 ft x 720 ft"
            : wantsSubdivisionCadPlan
              ? "Concept Site Boundary - 1200 ft x 820 ft"
              : "Concept Site Boundary - 1000 ft x 1000 ft",
          type: "site",
          w: conceptWidth,
          d: conceptHeight,
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
            acres: Number(((conceptWidth * conceptHeight) / SQFT_PER_ACRE).toFixed(3)),
          },
        },
        ...prev.filter((item) => item.type !== "site"),
      ]);
    }
    clearGeneratedPreview();
    const lot = createdConceptSite
      ? wantsUrbanizationCampusPlan
        ? { w: 1120, h: 720 }
        : wantsSubdivisionCadPlan
        ? { w: 1200, h: 820 }
        : { w: 1000, h: 1000 }
      : resolveLotBounds();
    const conceptObjects = wantsUrbanizationCampusPlan
      ? createUrbanizationCampusPlanPlacements(lot)
      : wantsSubdivisionCadPlan
        ? createDenseSubdivisionCadPlanPlacements(lot)
        : createDenseCommercialConceptPlacements(lot);
    setBuildingPlacements((prev) => {
      const keep = prev.filter((item) => item.type === "site" || !item.meta?.dense_concept_generated);
      return [...keep, ...conceptObjects];
    });
    markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
    setActivePlacementId(null);
    setPlacementModeEnabled(false);
    setCommandBarExpanded(false);
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
      label: wantsUrbanizationCampusPlan ? "Urbanization campus plan created" : wantsSubdivisionCadPlan ? "Dense subdivision CAD plan created" : "Dense concept plan created",
      detail: wantsUrbanizationCampusPlan
        ? "Urbanization parcels, boulevard roads, civic buildings, plaza, park, trees, parking, and service networks were placed."
        : wantsSubdivisionCadPlan
        ? "Subdivision lots, roads, contours, amenity core, ponds, utility spines, parking hatches, and feature courts were placed."
        : "Office, parking, basin, driveway, sidewalks, water, sanitary, storm, inlet, outfall, hydrant, and manhole draft objects were placed.",
    });
    updateProjectStatus({
      state: "needs review",
      area: "setup",
      title: wantsUrbanizationCampusPlan ? "Urbanization/campus review model created" : wantsSubdivisionCadPlan ? "Dense subdivision review plan created" : "Dense review concept created",
      detail: wantsUrbanizationCampusPlan
        ? "Created a colored editable urbanization/campus plan with parcels, civic massing, plaza, park, trees, road hierarchy, parking, and utilities. It is draft review geometry."
        : wantsSubdivisionCadPlan
        ? "Created a dense editable CAD-style subdivision plan with lots, streets, contours, amenity/drainage space, hatching, and utilities. It is draft review geometry."
        : createdConceptSite
        ? "Created a 1000 ft by 1000 ft concept site and placed coherent editable building, parking, drainage, utilities, access, and sidewalk objects."
        : "Placed a coherent editable concept with building, parking, drainage, utilities, access, and sidewalk objects.",
      nextAction: "Edit the objects directly, then run Generate when the layout looks right.",
    });
    appendChatMessage(
      "assistant",
      wantsUrbanizationCampusPlan
        ? "Created an editable urbanization/campus review plan with parcel rows, boulevard circulation, civic buildings, plaza paving, municipal park, trees, parking courts, and colored service networks. Switch to 3D to review the massing model. It is draft review geometry, not survey/control or construction evidence."
        : wantsSubdivisionCadPlan
          ? "Created a dense editable CAD-style subdivision review plan with lot blocks, collector roads, internal loop roads, yellow contour linework, central amenity/drainage space, blue/red hatched plan areas, ponds, storm/water/sanitary corridors, and feature nodes. It is draft review geometry, not survey/control or construction evidence."
        : createdConceptSite
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
    setCommandBarExpanded,
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
