import { useCallback } from "react";

import type { BuildingPlacement, ChatMessage } from "../types";
import { buildGenerateConceptPlacements } from "../utils/dashboardGenerateConcepts";
import {
  buildGradingDrainageReviewContextPlacements,
  type GradingDrainageReviewContextMode,
} from "../utils/dashboardReviewContextPlacements";
import type { RecentChange } from "../utils/dashboardTypes";
import type { SidePanelKey, WorkspaceMode } from "../utils/workspaceShell";
import type { EngineeringSystemKey, SystemGenerationTarget } from "../utils/workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;

type UseDashboardReviewConceptActionsInput = {
  appendChatMessage: AppendChatMessage;
  buildingDepth: string;
  buildingPlacements: BuildingPlacement[];
  buildingWidth: string;
  clearGeneratedPreview: () => void;
  ensureSiteBoundary: (reason: string) => boolean;
  hasSiteBoundary: () => boolean;
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
  recordDraftUndoAction: (action: { action: "add"; object: BuildingPlacement }) => void;
  recordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  resolveLotBounds: () => { w: number; h: number };
  setActivePlacementId: StateSetter<string | null>;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setFitToSiteRequest: StateSetter<number>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setPreviewMode: StateSetter<"2d" | "3d">;
  setRenderedSidePanel: StateSetter<SidePanelKey | null>;
  setRightRailCollapsed: StateSetter<boolean>;
  setSidePanelVisible: StateSetter<boolean>;
  setStatusMessage: (message: string) => void;
  siteScaleLocked: boolean;
};

export function useDashboardReviewConceptActions({
  appendChatMessage,
  buildingDepth,
  buildingPlacements,
  buildingWidth,
  clearGeneratedPreview,
  ensureSiteBoundary,
  hasSiteBoundary,
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
  recordDraftUndoAction,
  recordRecentChange,
  resolveLotBounds,
  setActivePlacementId,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setBuildingPlacements,
  setFitToSiteRequest,
  setPlacementModeEnabled,
  setPreviewInteraction,
  setPreviewMode,
  setRenderedSidePanel,
  setRightRailCollapsed,
  setSidePanelVisible,
  setStatusMessage,
  siteScaleLocked,
}: UseDashboardReviewConceptActionsInput) {
  const addGradingDrainageReviewContext = useCallback(
    (message: string, mode: GradingDrainageReviewContextMode = "both") => {
      clearGeneratedPreview();
      if (!hasSiteBoundary()) {
        ensureSiteBoundary("Created a default review site so grading/drainage context can be added immediately.");
      }
      const lot = resolveLotBounds();
      const additions = buildGradingDrainageReviewContextPlacements({ lot, mode });
      setBuildingPlacements((prev) => [...prev, ...additions]);
      additions.forEach((item) => recordDraftUndoAction({ action: "add", object: item }));
      markSystemsStale(["grading", "drainage"]);
      setActivePlacementId(null);
      setPlacementModeEnabled(false);
      setPreviewMode("2d");
      setPreviewInteraction("static");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setSidePanelVisible(false);
      setRightRailCollapsed(true);
      setFitToSiteRequest((value) => value + 1);
      recordRecentChange({
        type: "object_added",
        label: "Grading/drainage context added",
        detail: `${additions.map((item) => item.label).join(", ")} added as draft review geometry.`,
      });
      const messageLabel = additions.map((item) => item.label).join(" and ");
      appendChatMessage(
        "assistant",
        `${messageLabel} added to the canvas as editable review context. Generate will treat it as draft grading/drainage intent, not survey/control evidence.`,
        "status",
      );
      setStatusMessage(
        `${messageLabel} added as editable review context. Draft grading/drainage intent only; not survey/control evidence.`,
      );
      return true;
    },
    [
      appendChatMessage,
      clearGeneratedPreview,
      ensureSiteBoundary,
      hasSiteBoundary,
      markSystemsStale,
      recordDraftUndoAction,
      recordRecentChange,
      resolveLotBounds,
      setActivePlacementId,
      setActiveSidePanel,
      setActiveWorkspaceMode,
      setBuildingPlacements,
      setFitToSiteRequest,
      setPlacementModeEnabled,
      setPreviewInteraction,
      setPreviewMode,
      setRenderedSidePanel,
      setRightRailCollapsed,
      setSidePanelVisible,
      setStatusMessage,
    ],
  );

  const createGenerateConceptObjects = useCallback(
    (target: SystemGenerationTarget, notes: string[]) => {
      const lot = resolveLotBounds();
      const concept = buildGenerateConceptPlacements({
        target,
        notes,
        lot,
        siteScaleLocked,
        buildingPlacements,
        buildingWidth,
        buildingDepth,
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
      });
      if (!concept.length) return 0;
      setBuildingPlacements((prev) => [
        ...prev.filter((item) => !Boolean(item.meta?.generated_review_concept)),
        ...concept,
      ]);
      setPreviewMode("2d");
      setPreviewInteraction("static");
      setActiveWorkspaceMode("canvas");
      recordRecentChange({
        type: "generate_recorded",
        label: "Review concept layer updated",
        detail: `${concept.length} visible review concept object${concept.length === 1 ? "" : "s"} added to the canvas.`,
        undoBlockedReason: "Use Object Manager to hide/delete generated review concepts, then rerun Generate.",
      });
      setStatusMessage(`${concept.length} review concept object${concept.length === 1 ? "" : "s"} added to the canvas. Review required.`);
      return concept.length;
    },
    [
      buildingDepth,
      buildingPlacements,
      buildingWidth,
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
      recordRecentChange,
      resolveLotBounds,
      setActiveWorkspaceMode,
      setBuildingPlacements,
      setPreviewInteraction,
      setPreviewMode,
      setStatusMessage,
      siteScaleLocked,
    ],
  );

  return {
    addGradingDrainageReviewContext,
    createGenerateConceptObjects,
  };
}
