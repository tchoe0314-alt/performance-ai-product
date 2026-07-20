import { useCallback, useMemo } from "react";

import type { BuildingPlacement, Issue, PlanMeta } from "../types";
import {
  buildDashboardProgressTimelineState,
  buildDashboardSetupWizardState,
} from "../utils/dashboardWorkflowProgress";
import {
  buildDashboardSidebarReviewState,
  buildIssueDiagnosticSummary,
} from "../utils/dashboardSidebarReview";
import { sidePanelCopy, type SidePanelKey, type WorkspaceMode } from "../utils/workspaceShell";

type DashboardShellReviewStateOptions = {
  activeWorkspaceMode: WorkspaceMode;
  analysisIssues: Array<{ message: string }>;
  appliedAddressLabel: string;
  backendResultPresent: boolean;
  buildingPlacements: BuildingPlacement[];
  candidateAcceptedCount: number;
  candidateItemCount: number;
  candidatePendingCount: number;
  candidateTotalCount: number;
  canonicalWorkspaceBlockers: string[];
  currentPlanMeta: PlanMeta;
  currentProjectId?: string | null;
  currentProjectName?: string | null;
  exportBlockText: string;
  hasAppliedAddress: boolean;
  hasAssumedTerrainSlope: boolean;
  hasBasinPlaced: boolean;
  hasHardSystemBlock: boolean;
  hasTerrainSource: boolean;
  hasVerifiedSurveyControl: boolean;
  issueReportMessage: string;
  issues: Issue[];
  lotHeight: number;
  lotWidth: number;
  mapAnalysisSuccess: boolean;
  mapSnapshotPath: string;
  missingSite: boolean;
  onlineSourceLookupLabel: string;
  parkingCount: string;
  placedObjectCount: number;
  previewBlockedReasons: string[];
  releaseStatusRaw?: unknown;
  sidePanelForRender: SidePanelKey | null;
  siteAddress: string;
  siteInputAddress?: unknown;
  siteInputLat?: unknown;
  siteInputLng?: unknown;
  siteName: string;
  siteScaleLocked: boolean;
  siteSizeSet: boolean;
  standardsOk: boolean;
  surveyPreviewPointCount: number;
  systemStatuses: Record<string, string>;
  trustScoreRaw?: unknown;
  assumptionCategories?: unknown;
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
};

export function useDashboardShellReviewState({
  activeWorkspaceMode,
  analysisIssues,
  appliedAddressLabel,
  backendResultPresent,
  buildingPlacements,
  candidateAcceptedCount,
  candidateItemCount,
  candidatePendingCount,
  candidateTotalCount,
  canonicalWorkspaceBlockers,
  currentPlanMeta,
  currentProjectId,
  currentProjectName,
  exportBlockText,
  hasAppliedAddress,
  hasAssumedTerrainSlope,
  hasBasinPlaced,
  hasHardSystemBlock,
  hasTerrainSource,
  hasVerifiedSurveyControl,
  issueReportMessage,
  issues,
  lotHeight,
  lotWidth,
  mapAnalysisSuccess,
  mapSnapshotPath,
  missingSite,
  onlineSourceLookupLabel,
  parkingCount,
  placedObjectCount,
  previewBlockedReasons,
  releaseStatusRaw,
  sidePanelForRender,
  siteAddress,
  siteInputAddress,
  siteInputLat,
  siteInputLng,
  siteName,
  siteScaleLocked,
  siteSizeSet,
  standardsOk,
  surveyPreviewPointCount,
  systemStatuses,
  trustScoreRaw,
  assumptionCategories,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
}: DashboardShellReviewStateOptions) {
  const sidebarReviewState = buildDashboardSidebarReviewState({
    systemStatuses,
    missingSite,
    hasTerrainSource,
    hasBasinPlaced,
    drainageFresh: systemStatuses.drainage === "fresh",
    backendResultPresent,
    siteScaleLocked,
    buildingPlacementCount: buildingPlacements.length,
    siteAddress,
    siteInputAddress,
    siteInputLat,
    siteInputLng,
    uploadedImagePreviewUrl,
    uploadedImageApiUrl,
    surveyPreviewPointCount,
    mapSnapshotPath,
    releaseStatusRaw,
    trustScoreRaw,
    assumptionCategories,
    hasHardSystemBlock,
    previewBlockedReasonCount: previewBlockedReasons.length,
    standardsOk,
  });

  const { setupWizardState, setupWizardSteps, nextSetupAction } = buildDashboardSetupWizardState({
    persistedSetupWizardState: currentPlanMeta.setup_wizard_state_v1,
    hasAppliedAddress,
    siteAddress,
    appliedAddressLabel,
    siteScaleLocked,
    siteSizeSet,
    hasSiteObject: buildingPlacements.some((item) => item.type === "site"),
    hasSourceContext: Boolean(mapAnalysisSuccess || uploadedImageApiUrl || uploadedImagePreviewUrl),
    onlineSourceLookupLabel,
    hasVerifiedSurveyControl,
    hasTerrainSource,
    surveyPreviewPointCount,
    hasAssumedTerrainSlope,
    standardsOk,
    placedObjectCount,
    parkingCount,
    systemStatuses,
    hasBackendResult: backendResultPresent,
    exportBlockText,
  });

  const dashboardGuidanceStats: Array<[string, number]> = [
    ["Objects", placedObjectCount],
    ["Issues", issues.length + analysisIssues.length],
    ["Fresh", Object.values(systemStatuses).filter((status) => status === "fresh").length],
    ["Outputs", backendResultPresent ? 1 : 0],
  ];

  const progressPanelTarget = useCallback((value?: string): SidePanelKey => {
    const panel = String(value || "dashboard") as SidePanelKey;
    return sidePanelCopy[panel] ? panel : "dashboard";
  }, []);

  const bottomBlockerItems = useMemo(
    () => [
      ...canonicalWorkspaceBlockers,
      ...previewBlockedReasons,
      ...issues.map((issue) => issue.message),
      ...analysisIssues.map((issue) => issue.message),
    ].filter(Boolean),
    [analysisIssues, canonicalWorkspaceBlockers, issues, previewBlockedReasons],
  );

  const { progressTimelineState, progressTimelineSteps, progressPercent } =
    buildDashboardProgressTimelineState({
      persistedProgressTimeline: currentPlanMeta.progress_timeline_v1,
      setupWizardSteps,
      candidatePendingCount,
      candidateAcceptedCount,
      candidateItemCount,
      candidateTotalCount,
      placedObjectCount,
      systemStatuses,
      bottomBlockerItems,
      hasHardSystemBlock,
      hasBackendResult: backendResultPresent,
      exportBlockText,
    });

  const visibleStatusSummary = bottomBlockerItems.length
    ? bottomBlockerItems.slice(0, 6).join("; ")
    : hasHardSystemBlock
      ? "Hard system blocker recorded."
      : backendResultPresent
        ? "No visible blockers recorded."
        : "No run output yet.";

  const issueDiagnosticSummary = buildIssueDiagnosticSummary({
    projectId: currentProjectId || "draft / unavailable",
    projectName: siteName || currentProjectName || "Untitled Project",
    panelTitle: sidePanelForRender ? sidePanelCopy[sidePanelForRender].title : activeWorkspaceMode,
    visibleStatusSummary,
    siteLocked: siteScaleLocked,
    lotWidth,
    lotHeight,
    systemStatuses,
    issueReportMessage,
  });

  return {
    ...sidebarReviewState,
    bottomBlockerItems,
    dashboardGuidanceStats,
    issueDiagnosticSummary,
    nextSetupAction,
    progressPanelTarget,
    progressPercent,
    progressTimelineState,
    progressTimelineSteps,
    setupWizardState,
    setupWizardSteps,
    visibleStatusSummary,
  };
}
