import { useCallback } from "react";

import type { PlanResponse, ProjectRecord } from "../types";
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
  setCurrentProject,
  setStatusMessage,
  token,
}: DashboardReviewWorkflowActionsOptions) {
  const handleCandidateReviewDecision = useCallback(
    async (candidateId: string, action: "accept" | "reject" | "pending") => {
      await runDashboardCandidateReviewDecision({
        action,
        candidateId,
        currentProjectId,
        projectId,
        setBackendResult,
        setCurrentProject,
        setStatusMessage,
        token,
      });
    },
    [currentProjectId, projectId, setBackendResult, setCurrentProject, setStatusMessage, token],
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
