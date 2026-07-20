import { useMemo } from "react";
import type { ComponentProps, Dispatch, RefObject, SetStateAction } from "react";

import { DashboardHomePanel } from "../components/DashboardHomePanel";
import { ImportSurveyPanel } from "../components/ImportSurveyPanel";
import { SiteSetupPanel } from "../components/SiteSetupPanel";
import type {
  PlanResponse,
  ProjectInput,
  ProjectRecord,
} from "../types";
import type { AddressSuggestion } from "../utils/dashboardDataTypes";
import type { SidePanelKey } from "../utils/workspaceShell";

type DashboardHomePanelProps = ComponentProps<typeof DashboardHomePanel>;
type ImportSurveyPanelProps = ComponentProps<typeof ImportSurveyPanel>;
type SiteSetupPanelProps = ComponentProps<typeof SiteSetupPanel>;

type SaveProject = (options?: {
  silent?: boolean;
  projectIdOverride?: string | null;
  nameOverride?: string;
  fileNameOverride?: string;
  projectInputOverride?: ProjectInput;
  latestResultOverride?: PlanResponse;
  autoNamedOverride?: boolean;
  autoFileNamedOverride?: boolean;
}) => Promise<ProjectRecord | null>;

type UseDashboardStartPanelPropsInput = {
  siteName: string;
  fileName: string;
  lotBounds: { w: number; h: number };
  hasHardSystemBlock: boolean;
  hasBackendResult: boolean;
  onSiteNameChange: Dispatch<SetStateAction<string>>;
  onSiteNameAutoChange: Dispatch<SetStateAction<boolean>>;
  onFileNameChange: Dispatch<SetStateAction<string>>;
  onFileNameAutoChange: Dispatch<SetStateAction<boolean>>;
  onSaveProject: SaveProject;
  progressTimelineState: DashboardHomePanelProps["progressTimeline"]["progressTimelineState"];
  progressTimelineSteps: DashboardHomePanelProps["progressTimeline"]["progressTimelineSteps"];
  progressPercent: number;
  progressPanelTarget: DashboardHomePanelProps["progressTimeline"]["progressPanelTarget"];
  progressTimelineDotClass: DashboardHomePanelProps["progressTimeline"]["progressTimelineDotClass"];
  progressTimelineStatusClass: DashboardHomePanelProps["progressTimeline"]["progressTimelineStatusClass"];
  engineDepthDashboard: DashboardHomePanelProps["engineDepth"] extends infer T
    ? T extends { dashboard: infer Dashboard } ? Dashboard | null : never
    : never;
  dashboardGuidanceStats: DashboardHomePanelProps["guidance"]["stats"];
  issueReportMessage: string;
  issueDiagnosticSummary: DashboardHomePanelProps["issueReport"]["diagnosticSummary"];
  issueReportCopied: boolean;
  onIssueReportMessageChange: Dispatch<SetStateAction<string>>;
  onCopyIssueDiagnostic: () => void;
  workflowReviewDashboard: DashboardHomePanelProps["runReview"] extends infer T
    ? T extends { dashboard: infer Dashboard } ? Dashboard | null : never
    : never;
  systemHealthItems: DashboardHomePanelProps["statusPanels"]["systemHealthItems"];
  issueMessages: string[];
  analysisIssueMessages: string[];
  quantityRows: DashboardHomePanelProps["takeoffSnapshot"]["rows"];
  formatMetric: DashboardHomePanelProps["takeoffSnapshot"]["formatMetric"];
  statusLabelForQuantityReview: DashboardHomePanelProps["takeoffSnapshot"]["statusLabelForQuantityReview"];
  onOpenSidePanel: (panel: SidePanelKey) => void;
  pendingAddressEdit: boolean;
  siteAddress: string;
  appliedAddress: string;
  addressNeedsApply: boolean;
  hasAppliedAddress: boolean;
  localAddressLocked: boolean;
  siteScaleLocked: boolean;
  onlineDiscoveryBusy: boolean;
  addressSuggestions: AddressSuggestion[];
  autoExistingConditionsStatus: SiteSetupPanelProps["address"]["autoExistingConditionsStatus"];
  siteAddressInputRef: RefObject<HTMLInputElement | null>;
  onSiteAddressChange: Dispatch<SetStateAction<string>>;
  onSelectedAddressSuggestionChange: Dispatch<SetStateAction<AddressSuggestion | null>>;
  onAddressSuggestionsChange: Dispatch<SetStateAction<AddressSuggestion[]>>;
  onSaveSiteAddress: () => void;
  onCreateCenteredSite: () => void;
  onStartBlankSite: () => void;
  lotWidth: string;
  lotHeight: string;
  siteTooLargeForWarning: boolean;
  oversizedSiteMessage: string;
  onLotWidthChange: Dispatch<SetStateAction<string>>;
  onLotHeightChange: Dispatch<SetStateAction<string>>;
  onStartSiteBoundaryDraw: () => void;
  onApplySite: () => void;
  onUnlockSite: () => void;
  hasTerrainSource: boolean;
  surveyFileName: string;
  uploadedImagePreviewUrl: string;
  uploadedImageApiUrl: string;
  surveyPreviewPointCount: number;
  surveyUploadMessage: string;
  imageUploadState: string;
  imageUploadNote: string | null;
  mapSnapshotPath: string | null;
  mapSnapshotInputRef: RefObject<HTMLInputElement | null>;
  surveyInputRef: RefObject<HTMLInputElement | null>;
  onOpenImport: () => void;
  onAnalyzeMapSnapshot: () => void;
  onUploadImage: (file: File) => Promise<void>;
  onUploadExistingConditions: (file: File) => Promise<void>;
  autoSiteContextFlowSummary: SiteSetupPanelProps["autoSiteContext"]["autoSiteContextFlowSummary"];
  siteIntelligenceSummary: SiteSetupPanelProps["autoSiteContext"]["siteIntelligenceSummary"];
  siteIntelligenceFoundCount: number;
  siteIntelligenceMissingCount: number;
  siteIntelligenceAssumedCount: number;
  siteIntelligenceOutsideCount: number;
  roadFrontageMessage: string;
  drivewaySuggestionMessage: string;
  gradingContextMessage: string;
  autoSiteContextRows: SiteSetupPanelProps["autoSiteContext"]["autoSiteContextRows"];
  onlineFoundSources: SiteSetupPanelProps["autoSiteContext"]["onlineFoundSources"];
  candidateReviewItemCount: number;
  onReviewFoundContext: () => void;
  onRerunSiteContext: () => void;
  planPdfReady: boolean;
  mapAnalysisReady: boolean;
  detectionScaleFtPerPx: number | null;
  siteRotationDeg: number;
  onFitToSite: () => void;
  onMapCenter: () => void;
  onAlignRoad: () => void;
  onResetRotation: () => void;
  onRotationChange: (value: number) => void;
};

export function useDashboardStartPanelProps({
  siteName,
  fileName,
  lotBounds,
  hasHardSystemBlock,
  hasBackendResult,
  onSiteNameChange,
  onSiteNameAutoChange,
  onFileNameChange,
  onFileNameAutoChange,
  onSaveProject,
  progressTimelineState,
  progressTimelineSteps,
  progressPercent,
  progressPanelTarget,
  progressTimelineDotClass,
  progressTimelineStatusClass,
  engineDepthDashboard,
  dashboardGuidanceStats,
  issueReportMessage,
  issueDiagnosticSummary,
  issueReportCopied,
  onIssueReportMessageChange,
  onCopyIssueDiagnostic,
  workflowReviewDashboard,
  systemHealthItems,
  issueMessages,
  analysisIssueMessages,
  quantityRows,
  formatMetric,
  statusLabelForQuantityReview,
  onOpenSidePanel,
  pendingAddressEdit,
  siteAddress,
  appliedAddress,
  addressNeedsApply,
  hasAppliedAddress,
  localAddressLocked,
  siteScaleLocked,
  onlineDiscoveryBusy,
  addressSuggestions,
  autoExistingConditionsStatus,
  siteAddressInputRef,
  onSiteAddressChange,
  onSelectedAddressSuggestionChange,
  onAddressSuggestionsChange,
  onSaveSiteAddress,
  onCreateCenteredSite,
  onStartBlankSite,
  lotWidth,
  lotHeight,
  siteTooLargeForWarning,
  oversizedSiteMessage,
  onLotWidthChange,
  onLotHeightChange,
  onStartSiteBoundaryDraw,
  onApplySite,
  onUnlockSite,
  hasTerrainSource,
  surveyFileName,
  uploadedImagePreviewUrl,
  uploadedImageApiUrl,
  surveyPreviewPointCount,
  surveyUploadMessage,
  imageUploadState,
  imageUploadNote,
  mapSnapshotPath,
  mapSnapshotInputRef,
  surveyInputRef,
  onOpenImport,
  onAnalyzeMapSnapshot,
  onUploadImage,
  onUploadExistingConditions,
  autoSiteContextFlowSummary,
  siteIntelligenceSummary,
  siteIntelligenceFoundCount,
  siteIntelligenceMissingCount,
  siteIntelligenceAssumedCount,
  siteIntelligenceOutsideCount,
  roadFrontageMessage,
  drivewaySuggestionMessage,
  gradingContextMessage,
  autoSiteContextRows,
  onlineFoundSources,
  candidateReviewItemCount,
  onReviewFoundContext,
  onRerunSiteContext,
  planPdfReady,
  mapAnalysisReady,
  detectionScaleFtPerPx,
  siteRotationDeg,
  onFitToSite,
  onMapCenter,
  onAlignRoad,
  onResetRotation,
  onRotationChange,
}: UseDashboardStartPanelPropsInput) {
  const dashboardHomePanelProps = useMemo<DashboardHomePanelProps>(() => ({
    projectSummary: {
      siteName,
      fileName,
      lotWidth: lotBounds.w,
      lotHeight: lotBounds.h,
      hasHardSystemBlock,
      hasBackendResult,
      onSiteNameChange: (value) => {
        onSiteNameChange(value);
        onSiteNameAutoChange(false);
      },
      onFileNameChange: (value) => {
        onFileNameChange(value);
        onFileNameAutoChange(false);
      },
      onSaveName: () =>
        void onSaveProject({
          nameOverride: siteName.trim(),
          fileNameOverride: fileName.trim(),
          autoNamedOverride: false,
          autoFileNamedOverride: false,
        }),
    },
    progressTimeline: {
      progressTimelineState,
      progressTimelineSteps,
      progressPercent,
      onOpenPanel: onOpenSidePanel,
      progressPanelTarget,
      progressTimelineDotClass,
      progressTimelineStatusClass,
    },
    engineDepth: engineDepthDashboard
      ? {
          dashboard: engineDepthDashboard,
          onOpenPanel: onOpenSidePanel,
        }
      : null,
    guidance: { stats: dashboardGuidanceStats },
    issueReport: {
      message: issueReportMessage,
      diagnosticSummary: issueDiagnosticSummary,
      copied: issueReportCopied,
      onMessageChange: onIssueReportMessageChange,
      onCopyDiagnostic: onCopyIssueDiagnostic,
    },
    runReview: workflowReviewDashboard
      ? {
          dashboard: workflowReviewDashboard,
          onOpenPanel: onOpenSidePanel,
        }
      : null,
    statusPanels: {
      systemHealthItems,
      attentionMessages: [...issueMessages, ...analysisIssueMessages],
      onOpenHealthItem: (key) =>
        onOpenSidePanel(
          key === "data"
            ? "site_existing"
            : key === "roadway"
              ? "roadway"
              : (key as SidePanelKey),
        ),
      onOpenReview: () => onOpenSidePanel("analysis"),
    },
    takeoffSnapshot: {
      rows: quantityRows,
      formatMetric,
      statusLabelForQuantityReview,
    },
  }), [
    analysisIssueMessages,
    dashboardGuidanceStats,
    engineDepthDashboard,
    fileName,
    formatMetric,
    hasBackendResult,
    hasHardSystemBlock,
    issueDiagnosticSummary,
    issueMessages,
    issueReportCopied,
    issueReportMessage,
    lotBounds.h,
    lotBounds.w,
    onCopyIssueDiagnostic,
    onFileNameAutoChange,
    onFileNameChange,
    onIssueReportMessageChange,
    onOpenSidePanel,
    onSaveProject,
    onSiteNameAutoChange,
    onSiteNameChange,
    progressPanelTarget,
    progressPercent,
    progressTimelineDotClass,
    progressTimelineState,
    progressTimelineStatusClass,
    progressTimelineSteps,
    quantityRows,
    siteName,
    statusLabelForQuantityReview,
    systemHealthItems,
    workflowReviewDashboard,
  ]);

  const siteSetupPanelProps = useMemo<SiteSetupPanelProps>(() => ({
    address: {
      pendingAddressEdit,
      siteAddress,
      appliedAddress,
      addressNeedsApply,
      hasAppliedAddress,
      localAddressLocked,
      siteScaleLocked,
      onlineDiscoveryBusy,
      addressSuggestions,
      autoExistingConditionsStatus,
      siteAddressInputRef,
      onSiteAddressChange,
      onSelectedAddressSuggestionChange,
      onAddressSuggestionsChange,
      onSaveSiteAddress,
      onCreateCenteredSite,
      onStartBlankSite,
    },
    boundary: {
      lotBounds,
      lotWidth,
      lotHeight,
      siteScaleLocked,
      siteTooLargeForWarning,
      oversizedSiteMessage,
      siteAddress,
      onlineDiscoveryBusy,
      onLotWidthChange,
      onLotHeightChange,
      onStartSiteBoundaryDraw,
      onApplySite,
      onUnlockSite,
      onCreateCenteredSite,
    },
    surveyTerrain: {
      hasTerrainSource,
      surveyFileName,
      uploadedImagePreviewUrl,
      uploadedImageApiUrl,
      surveyPreviewPointCount,
      surveyUploadMessage,
      imageUploadState,
      imageUploadNote,
      mapSnapshotPath,
      mapSnapshotInputRef,
      surveyInputRef,
      onOpenImport,
      onAnalyzeMapSnapshot,
      onUploadImage,
      onUploadExistingConditions,
    },
    autoSiteContext: {
      autoSiteContextFlowSummary,
      autoExistingConditionsStatus,
      siteIntelligenceSummary,
      siteIntelligenceFoundCount,
      siteIntelligenceMissingCount,
      siteIntelligenceAssumedCount,
      siteIntelligenceOutsideCount,
      roadFrontageMessage,
      drivewaySuggestionMessage,
      gradingContextMessage,
      autoSiteContextRows,
      onlineFoundSources,
      candidateReviewItemCount,
      hasAppliedAddress,
      onlineDiscoveryBusy,
      onReviewFoundContext,
      onRerunSiteContext,
    },
  }), [
    addressNeedsApply,
    addressSuggestions,
    appliedAddress,
    autoExistingConditionsStatus,
    autoSiteContextFlowSummary,
    autoSiteContextRows,
    candidateReviewItemCount,
    drivewaySuggestionMessage,
    gradingContextMessage,
    hasAppliedAddress,
    hasTerrainSource,
    imageUploadNote,
    imageUploadState,
    localAddressLocked,
    lotBounds,
    lotHeight,
    lotWidth,
    mapSnapshotInputRef,
    mapSnapshotPath,
    onAddressSuggestionsChange,
    onAnalyzeMapSnapshot,
    onApplySite,
    onCreateCenteredSite,
    onLotHeightChange,
    onLotWidthChange,
    onOpenImport,
    onRerunSiteContext,
    onReviewFoundContext,
    onSaveSiteAddress,
    onSelectedAddressSuggestionChange,
    onSiteAddressChange,
    onStartBlankSite,
    onStartSiteBoundaryDraw,
    onUnlockSite,
    onUploadExistingConditions,
    onUploadImage,
    onlineDiscoveryBusy,
    onlineFoundSources,
    oversizedSiteMessage,
    pendingAddressEdit,
    roadFrontageMessage,
    siteAddress,
    siteAddressInputRef,
    siteIntelligenceAssumedCount,
    siteIntelligenceFoundCount,
    siteIntelligenceMissingCount,
    siteIntelligenceOutsideCount,
    siteIntelligenceSummary,
    siteScaleLocked,
    siteTooLargeForWarning,
    surveyFileName,
    surveyInputRef,
    surveyPreviewPointCount,
    surveyUploadMessage,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
  ]);

  const importSurveyPanelProps = useMemo<ImportSurveyPanelProps>(() => ({
    mapSnapshotReady: Boolean(uploadedImagePreviewUrl || uploadedImageApiUrl),
    surveyPointCount: surveyPreviewPointCount,
    imageUploadState,
    imageUploadNote,
    surveyUploadMessage,
    planPdfReady,
    mapAnalysisReady,
    mapSnapshotPath,
    hasTerrainSource,
    detectionScaleFtPerPx,
    siteRotationDeg,
    siteScaleLocked,
    mapSnapshotInputRef,
    surveyInputRef,
    onUploadImage,
    onUploadExistingConditions,
    onOpenPlanPdf: () => onOpenSidePanel("data"),
    onAnalyzeMapSnapshot,
    onFitToSite,
    onMapCenter,
    onAlignRoad,
    onResetRotation,
    onRotationChange,
  }), [
    detectionScaleFtPerPx,
    hasTerrainSource,
    imageUploadNote,
    imageUploadState,
    mapAnalysisReady,
    mapSnapshotInputRef,
    mapSnapshotPath,
    onAlignRoad,
    onAnalyzeMapSnapshot,
    onFitToSite,
    onMapCenter,
    onOpenSidePanel,
    onResetRotation,
    onRotationChange,
    onUploadExistingConditions,
    onUploadImage,
    planPdfReady,
    siteRotationDeg,
    siteScaleLocked,
    surveyInputRef,
    surveyPreviewPointCount,
    surveyUploadMessage,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
  ]);

  return {
    dashboardHomePanelProps,
    importSurveyPanelProps,
    siteSetupPanelProps,
  };
}
