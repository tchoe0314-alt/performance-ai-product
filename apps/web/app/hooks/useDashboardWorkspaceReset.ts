import type { Dispatch, SetStateAction } from "react";
import { useCallback } from "react";

import type {
  BuildingPlacement,
  JobSummary,
  MapAnalysis,
  PlanResponse,
  PreviewResponse,
  SurveySlopeResponse,
} from "../types";
import type { PlanSheetSet } from "../components/PlanSheetEditor";
import type { WorkspaceToast } from "../components/WorkspaceToasts";
import { createDefaultPlanSheetSet } from "../utils/planSheetDefaults";
import type { AddressSuggestion, AutoExistingConditionsUiStatus, GenerateFlowSummary, ReviewPackageFlowSummary } from "../utils/dashboardDataTypes";
import type { CadToolRequestForPreview } from "../utils/dashboardTypes";

type AnalysisPath = {
  id: string;
  buildingId: string;
  accessId: string;
  from: { x: number; y: number };
  to: { x: number; y: number };
  label: string;
  points?: Array<{ x: number; y: number }>;
};

type AnalysisIssue = {
  id: string;
  buildingId: string;
  accessId: string;
  distanceFt: number;
  thresholdFt: number;
  message: string;
  pathId: string;
  issueType: "distance" | "no_access" | "no_buildings" | "no_access_objects";
};

type UseDashboardWorkspaceResetOptions = {
  debugLog: (message: string, details?: Record<string, unknown>) => void;
  setActiveJobId: Dispatch<SetStateAction<string>>;
  setActivePlacementId: Dispatch<SetStateAction<string | null>>;
  setAddressSuggestions: Dispatch<SetStateAction<AddressSuggestion[]>>;
  setAnalysisFocusLocked: Dispatch<SetStateAction<boolean>>;
  setAnalysisIssues: Dispatch<SetStateAction<AnalysisIssue[]>>;
  setAnalysisPaths: Dispatch<SetStateAction<AnalysisPath[]>>;
  setAnalysisSelectedIssueId: Dispatch<SetStateAction<string | null>>;
  setAlignToRoadRequest: Dispatch<SetStateAction<number>>;
  setApprovalError: Dispatch<SetStateAction<string | null>>;
  setApprovalInFlight: Dispatch<SetStateAction<boolean>>;
  setApprovalPendingJobId: Dispatch<SetStateAction<string | null>>;
  setApprovalPhaseLabel: Dispatch<SetStateAction<string | null>>;
  setAutoExistingConditionsStatus: Dispatch<SetStateAction<AutoExistingConditionsUiStatus>>;
  setBackendResult: Dispatch<SetStateAction<PlanResponse | null>>;
  setBuildingPlacements: Dispatch<SetStateAction<BuildingPlacement[]>>;
  setCadToolRequest: Dispatch<SetStateAction<CadToolRequestForPreview | null>>;
  setDetectedPlacements: Dispatch<SetStateAction<BuildingPlacement[]>>;
  setDetectionScaleFeet: Dispatch<SetStateAction<string>>;
  setDetectionScaleFtPerPx: Dispatch<SetStateAction<number | null>>;
  setDetectionScalePixels: Dispatch<SetStateAction<string>>;
  setDetectionScaleSource: Dispatch<SetStateAction<"approximate" | "manual" | "mapbox">>;
  setExportActionMessage: Dispatch<SetStateAction<string>>;
  setFitToSiteRequest: Dispatch<SetStateAction<number>>;
  setFocusDetectedId: Dispatch<SetStateAction<string | null>>;
  setFocusObjectId: Dispatch<SetStateAction<string | null>>;
  setGenerateFlowSummary: Dispatch<SetStateAction<GenerateFlowSummary | null>>;
  setImageUploadNote: Dispatch<SetStateAction<string | null>>;
  setImageUploadState: Dispatch<SetStateAction<"idle" | "uploading" | "uploaded" | "detecting" | "failed">>;
  setJobs: Dispatch<SetStateAction<JobSummary[]>>;
  setJobToasts: Dispatch<SetStateAction<WorkspaceToast[]>>;
  setJobsPanelStatusMessage: Dispatch<SetStateAction<string>>;
  setLayerManagerOpen: Dispatch<SetStateAction<boolean>>;
  setMapAnalysis: Dispatch<SetStateAction<MapAnalysis | null>>;
  setMapCenterRequest: Dispatch<SetStateAction<number>>;
  setMapSnapshotPath: Dispatch<SetStateAction<string>>;
  setMoveEditFeedback: Dispatch<SetStateAction<string>>;
  setPendingClarification: Dispatch<SetStateAction<{ question: string; action: string; payload?: Record<string, unknown> } | null>>;
  setPlacementModeEnabled: Dispatch<SetStateAction<boolean>>;
  setPlanPdfElementDraftText: Dispatch<SetStateAction<string>>;
  setPlanPdfMoveX: Dispatch<SetStateAction<string>>;
  setPlanPdfMoveY: Dispatch<SetStateAction<string>>;
  setPlanPdfUploadMessage: Dispatch<SetStateAction<string>>;
  setPlanPdfUploadState: Dispatch<SetStateAction<"idle" | "uploading" | "uploaded" | "failed">>;
  setPlanPreviewAnnotations: Dispatch<SetStateAction<PreviewResponse["preview_annotations"] | null>>;
  setPlanPreviewProjectId: Dispatch<SetStateAction<string | null>>;
  setPlanPreviewSummary: Dispatch<SetStateAction<PreviewResponse["summary"] | null>>;
  setPlanPreviewUrl: Dispatch<SetStateAction<string>>;
  setPlanSheetSet: Dispatch<SetStateAction<PlanSheetSet>>;
  setPreviewFullscreenOpen: Dispatch<SetStateAction<boolean>>;
  setPreviewRefreshing: Dispatch<SetStateAction<boolean>>;
  setPreviewRefreshNote: Dispatch<SetStateAction<string | null>>;
  setReviewPackageFlowSummary: Dispatch<SetStateAction<ReviewPackageFlowSummary | null>>;
  setSelectedAddressSuggestion: Dispatch<SetStateAction<AddressSuggestion | null>>;
  setSelectedIssueId: Dispatch<SetStateAction<string | null>>;
  setSelectedJobId: Dispatch<SetStateAction<string>>;
  setSelectedPlanPdfElementId: Dispatch<SetStateAction<string>>;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setShowSiteBounds: Dispatch<SetStateAction<boolean>>;
  setSiteAddress: Dispatch<SetStateAction<string>>;
  setSiteRotationDeg: Dispatch<SetStateAction<number>>;
  setSiteRotationInput: Dispatch<SetStateAction<string>>;
  setSiteScaleLocked: Dispatch<SetStateAction<boolean>>;
  setSiteSelectionMode: Dispatch<SetStateAction<boolean>>;
  setSurveyDiagnostics: Dispatch<SetStateAction<{
    fileType?: string;
    parseSuccess?: boolean;
    pointCount?: number;
    contourCount?: number;
    recognizedColumns?: { x?: string; y?: string; z?: string };
    invalidRows?: number;
    bounds?: { min_x?: number; min_y?: number; max_x?: number; max_y?: number };
    elevationRange?: { min?: number; max?: number };
    warnings?: string[];
  } | null>>;
  setSurveyFileName: Dispatch<SetStateAction<string>>;
  setSurveyPoints: Dispatch<SetStateAction<number[][]>>;
  setSurveyPreviewPoints: Dispatch<SetStateAction<Array<{ x: number; y: number; z?: number }>>>;
  setSurveySlopeEstimate: Dispatch<SetStateAction<SurveySlopeResponse | null>>;
  setSourceEffectRows: Dispatch<SetStateAction<string[]>>;
  setSurveyUploadMessage: Dispatch<SetStateAction<string>>;
  setUseSurveyForGrading: Dispatch<SetStateAction<boolean>>;
  setUploadedImageApiUrl: Dispatch<SetStateAction<string>>;
  setUploadedImagePreviewUrl: Dispatch<SetStateAction<string>>;
  setViewportCenter: Dispatch<SetStateAction<{ lat: number; lng: number } | null>>;
  setViewportFootprint: Dispatch<SetStateAction<{
    widthFt: number;
    heightFt: number;
    bounds?: {
      north: number;
      south: number;
      east: number;
      west: number;
      centerLat: number;
      centerLng: number;
    };
  } | null>>;
  setWorkspaceRestoreState: Dispatch<SetStateAction<"idle" | "restored" | "failed">>;
};

export function useDashboardWorkspaceReset({
  debugLog,
  setActiveJobId,
  setActivePlacementId,
  setAddressSuggestions,
  setAnalysisFocusLocked,
  setAnalysisIssues,
  setAnalysisPaths,
  setAnalysisSelectedIssueId,
  setAlignToRoadRequest,
  setApprovalError,
  setApprovalInFlight,
  setApprovalPendingJobId,
  setApprovalPhaseLabel,
  setAutoExistingConditionsStatus,
  setBackendResult,
  setBuildingPlacements,
  setCadToolRequest,
  setDetectedPlacements,
  setDetectionScaleFeet,
  setDetectionScaleFtPerPx,
  setDetectionScalePixels,
  setDetectionScaleSource,
  setExportActionMessage,
  setFitToSiteRequest,
  setFocusDetectedId,
  setFocusObjectId,
  setGenerateFlowSummary,
  setImageUploadNote,
  setImageUploadState,
  setJobs,
  setJobToasts,
  setJobsPanelStatusMessage,
  setLayerManagerOpen,
  setMapAnalysis,
  setMapCenterRequest,
  setMapSnapshotPath,
  setMoveEditFeedback,
  setPendingClarification,
  setPlacementModeEnabled,
  setPlanPdfElementDraftText,
  setPlanPdfMoveX,
  setPlanPdfMoveY,
  setPlanPdfUploadMessage,
  setPlanPdfUploadState,
  setPlanPreviewAnnotations,
  setPlanPreviewProjectId,
  setPlanPreviewSummary,
  setPlanPreviewUrl,
  setPlanSheetSet,
  setPreviewFullscreenOpen,
  setPreviewRefreshing,
  setPreviewRefreshNote,
  setReviewPackageFlowSummary,
  setSelectedAddressSuggestion,
  setSelectedIssueId,
  setSelectedJobId,
  setSelectedPlanPdfElementId,
  setSelectedRunId,
  setShowSiteBounds,
  setSiteAddress,
  setSiteRotationDeg,
  setSiteRotationInput,
  setSiteScaleLocked,
  setSiteSelectionMode,
  setSurveyDiagnostics,
  setSurveyFileName,
  setSurveyPoints,
  setSurveyPreviewPoints,
  setSurveySlopeEstimate,
  setSourceEffectRows,
  setSurveyUploadMessage,
  setUseSurveyForGrading,
  setUploadedImageApiUrl,
  setUploadedImagePreviewUrl,
  setViewportCenter,
  setViewportFootprint,
  setWorkspaceRestoreState,
}: UseDashboardWorkspaceResetOptions) {
  const resetWorkspaceState = useCallback(() => {
    debugLog("reset-workspace");
    setCadToolRequest(null);
    setPlanPreviewUrl("");
    setPlanPreviewProjectId(null);
    setPlanPreviewSummary(null);
    setPlanPreviewAnnotations(null);
    setPreviewRefreshing(false);
    setPreviewRefreshNote(null);
    setBackendResult(null);
    setGenerateFlowSummary(null);
    setReviewPackageFlowSummary(null);
    setExportActionMessage("");
    setPlanPdfUploadState("idle");
    setPlanPdfUploadMessage("");
    setSelectedPlanPdfElementId("");
    setPlanPdfElementDraftText("");
    setPlanPdfMoveX("");
    setPlanPdfMoveY("");
    setSelectedRunId("");
    setActiveJobId("");
    setSelectedJobId("");
    setJobs([]);
    setJobToasts([]);
    setApprovalInFlight(false);
    setApprovalPhaseLabel(null);
    setApprovalError(null);
    setApprovalPendingJobId(null);
    setUploadedImageApiUrl("");
    setUploadedImagePreviewUrl("");
    setImageUploadState("idle");
    setImageUploadNote(null);
    setSurveyFileName("");
    setSurveyUploadMessage("");
    setSurveySlopeEstimate(null);
    setSurveyPoints([]);
    setSurveyPreviewPoints([]);
    setSurveyDiagnostics(null);
    setSourceEffectRows([]);
    setUseSurveyForGrading(true);
    setMapSnapshotPath("");
    setMapAnalysis(null);
    setSiteSelectionMode(false);
    setViewportFootprint(null);
    setViewportCenter(null);
    setAddressSuggestions([]);
    setSelectedAddressSuggestion(null);
    setAutoExistingConditionsStatus({
      status: "waiting",
      message: "Apply an address and lock the site. Civora will then check available source context inside the boundary.",
      candidateCount: 0,
      missing: [],
    });
    setLayerManagerOpen(false);
    setPreviewFullscreenOpen(false);
    setSelectedJobId("");
    setMoveEditFeedback("");
    setJobsPanelStatusMessage("");
    setWorkspaceRestoreState("idle");
    setSiteAddress("");
    setBuildingPlacements([]);
    setDetectedPlacements([]);
    setDetectionScaleFeet("");
    setDetectionScalePixels("");
    setDetectionScaleFtPerPx(null);
    setDetectionScaleSource("approximate");
    setSiteScaleLocked(false);
    setSiteRotationDeg(0);
    setSiteRotationInput("0");
    setShowSiteBounds(true);
    setFitToSiteRequest(0);
    setMapCenterRequest(0);
    setAlignToRoadRequest(0);
    setFocusDetectedId(null);
    setFocusObjectId(null);
    setPlacementModeEnabled(false);
    setActivePlacementId(null);
    setAnalysisIssues([]);
    setAnalysisPaths([]);
    setAnalysisSelectedIssueId(null);
    setAnalysisFocusLocked(false);
    setSelectedIssueId(null);
    setPendingClarification(null);
    setPlanSheetSet(createDefaultPlanSheetSet("Untitled Project"));
  }, [
    debugLog,
    setActiveJobId,
    setActivePlacementId,
    setAddressSuggestions,
    setAnalysisFocusLocked,
    setAnalysisIssues,
    setAnalysisPaths,
    setAnalysisSelectedIssueId,
    setAlignToRoadRequest,
    setApprovalError,
    setApprovalInFlight,
    setApprovalPendingJobId,
    setApprovalPhaseLabel,
    setAutoExistingConditionsStatus,
    setBackendResult,
    setBuildingPlacements,
    setCadToolRequest,
    setDetectedPlacements,
    setDetectionScaleFeet,
    setDetectionScaleFtPerPx,
    setDetectionScalePixels,
    setDetectionScaleSource,
    setExportActionMessage,
    setFitToSiteRequest,
    setFocusDetectedId,
    setFocusObjectId,
    setGenerateFlowSummary,
    setImageUploadNote,
    setImageUploadState,
    setJobs,
    setJobToasts,
    setJobsPanelStatusMessage,
    setLayerManagerOpen,
    setMapAnalysis,
    setMapCenterRequest,
    setMapSnapshotPath,
    setMoveEditFeedback,
    setPendingClarification,
    setPlacementModeEnabled,
    setPlanPdfElementDraftText,
    setPlanPdfMoveX,
    setPlanPdfMoveY,
    setPlanPdfUploadMessage,
    setPlanPdfUploadState,
    setPlanPreviewAnnotations,
    setPlanPreviewProjectId,
    setPlanPreviewSummary,
    setPlanPreviewUrl,
    setPlanSheetSet,
    setPreviewFullscreenOpen,
    setPreviewRefreshing,
    setPreviewRefreshNote,
    setReviewPackageFlowSummary,
    setSelectedAddressSuggestion,
    setSelectedIssueId,
    setSelectedJobId,
    setSelectedPlanPdfElementId,
    setSelectedRunId,
    setShowSiteBounds,
    setSiteAddress,
    setSiteRotationDeg,
    setSiteRotationInput,
    setSiteScaleLocked,
    setSiteSelectionMode,
    setSurveyDiagnostics,
    setSurveyFileName,
    setSurveyPoints,
    setSurveyPreviewPoints,
    setSurveySlopeEstimate,
    setSourceEffectRows,
    setSurveyUploadMessage,
    setUseSurveyForGrading,
    setUploadedImageApiUrl,
    setUploadedImagePreviewUrl,
    setViewportCenter,
    setViewportFootprint,
    setWorkspaceRestoreState,
  ]);

  return { resetWorkspaceState };
}
