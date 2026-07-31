import { useCallback } from "react";

import type { BuildingPlacement, PlanResponse, ProjectRecord, SiteInputs } from "../types";
import { buildAcceptedCandidatePlacements } from "../utils/projectInputRestore";
import {
  runDashboardCandidateReviewDecision,
  runDashboardDesignAlternativesAction,
} from "../utils/dashboardReviewWorkflowActions";
import type { SidePanelKey, WorkspaceMode } from "../utils/workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type DashboardReviewWorkflowActionsOptions = {
  currentProjectId?: string;
  designAlternativeCount: number;
  projectId: string;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setBackendResult: StateSetter<PlanResponse | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setStatusMessage: StateSetter<string>;
  token: string;
};

export function useDashboardReviewWorkflowActions({
  currentProjectId,
  designAlternativeCount,
  projectId,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setBackendResult,
  setBuildingPlacements,
  setCurrentProject,
  setStatusMessage,
  token,
}: DashboardReviewWorkflowActionsOptions) {
  const handleCandidateReviewDecision = useCallback(
    async (candidateId: string, action: "accept" | "reject" | "pending") => {
      const updatedProject = await runDashboardCandidateReviewDecision({
        action,
        candidateId,
        currentProjectId,
        projectId,
        setBackendResult,
        setCurrentProject,
        setStatusMessage,
        token,
      });
      if (updatedProject?.project_input) {
        const updatedSiteInputs = (updatedProject.project_input.meta?.site_inputs ?? {}) as SiteInputs;
        const acceptedPlacements = buildAcceptedCandidatePlacements({
          projectInput: updatedProject.project_input,
          siteInputs: updatedSiteInputs,
        });
        const acceptedIds = new Set(acceptedPlacements.map((item) => item.id));
        setBuildingPlacements((previous) => [
          ...previous.filter(
            (item) => !item.meta?.accepted_source_candidate && !acceptedIds.has(item.id),
          ),
          ...acceptedPlacements,
        ]);
      }
    },
    [
      currentProjectId,
      projectId,
      setBackendResult,
      setBuildingPlacements,
      setCurrentProject,
      setStatusMessage,
      token,
    ],
  );

  const handleDesignAlternativesAction = useCallback(
    async (action: "generate" | "compare" | "choose" | "merge" | "revise", optionNumber?: number) => {
      await runDashboardDesignAlternativesAction({
        action,
        currentProjectId,
        designAlternativeCount,
        optionNumber,
        projectId,
        setActiveSidePanel,
        setActiveWorkspaceMode,
        setBackendResult,
        setCurrentProject,
        setStatusMessage,
        token,
      });
    },
    [
      currentProjectId,
      designAlternativeCount,
      projectId,
      setActiveSidePanel,
      setActiveWorkspaceMode,
      setBackendResult,
      setCurrentProject,
      setStatusMessage,
      token,
    ],
  );

  return {
    handleCandidateReviewDecision,
    handleDesignAlternativesAction,
  };
}
