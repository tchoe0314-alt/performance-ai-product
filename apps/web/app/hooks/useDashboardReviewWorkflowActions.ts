import { useCallback, useRef, useState } from "react";

import type {
  BuildingPlacement,
  CandidateReviewCorrection,
  CandidateReviewDecision,
  PlanResponse,
  ProjectRecord,
  SiteInputs,
} from "../types";
import { buildAcceptedCandidatePlacements } from "../utils/projectInputRestore";
import {
  runDashboardCandidateReviewDecision,
  runDashboardDesignAlternativesAction,
  exportDashboardVisionLearningManifest,
} from "../utils/dashboardReviewWorkflowActions";
import type { SidePanelKey, WorkspaceMode } from "../utils/workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type DashboardReviewWorkflowActionsOptions = {
  currentProject: ProjectRecord | null;
  currentProjectId?: string;
  designAlternativeCount: number;
  projectId: string;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setBackendResult: StateSetter<PlanResponse | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setSiteScaleLocked: StateSetter<boolean>;
  setStatusMessage: StateSetter<string>;
  siteScaleLocked: boolean;
  token: string;
};

export function useDashboardReviewWorkflowActions({
  currentProject,
  currentProjectId,
  designAlternativeCount,
  projectId,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setBackendResult,
  setBuildingPlacements,
  setCurrentProject,
  setSiteScaleLocked,
  setStatusMessage,
  siteScaleLocked,
  token,
}: DashboardReviewWorkflowActionsOptions) {
  const [candidateDecisionInFlight, setCandidateDecisionInFlight] = useState<{
    candidateId: string;
    action: CandidateReviewDecision;
  } | null>(null);
  const candidateDecisionLockRef = useRef(false);
  const handleCandidateReviewDecision = useCallback(
    async (
      candidateIds: string | string[],
      action: CandidateReviewDecision,
      correction?: CandidateReviewCorrection,
    ) => {
      if (candidateDecisionLockRef.current) return;
      candidateDecisionLockRef.current = true;
      const normalizedCandidateIds = Array.isArray(candidateIds) ? candidateIds : [candidateIds];
      setCandidateDecisionInFlight({ candidateId: normalizedCandidateIds.join(","), action });
      try {
        const updatedProject = await runDashboardCandidateReviewDecision({
          action,
          candidateIds: normalizedCandidateIds,
          currentProject,
          siteScaleLocked,
          currentProjectId,
          projectId,
          setBackendResult,
          setCurrentProject,
          setStatusMessage,
          token,
          correction,
        });
        if (updatedProject?.project_input) {
          if (siteScaleLocked) setSiteScaleLocked(true);
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
      } finally {
        candidateDecisionLockRef.current = false;
        setCandidateDecisionInFlight(null);
      }
    },
    [
      currentProjectId,
      currentProject,
      projectId,
      setBackendResult,
      setBuildingPlacements,
      setCurrentProject,
      setSiteScaleLocked,
      setStatusMessage,
      siteScaleLocked,
      token,
    ],
  );

  const handleExportVisionLearning = useCallback(async () => {
    await exportDashboardVisionLearningManifest({
      currentProjectId,
      projectId,
      setStatusMessage,
      token,
    });
  }, [currentProjectId, projectId, setStatusMessage, token]);

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
    candidateDecisionInFlight,
    handleCandidateReviewDecision,
    handleExportVisionLearning,
    handleDesignAlternativesAction,
  };
}
