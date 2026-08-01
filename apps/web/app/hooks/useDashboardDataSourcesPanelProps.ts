import { useMemo } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";

import type { DataSourcesPanelProps } from "../components/DataSourcesPanel";
import type {
  BuildingPlacement,
  CandidateReviewInbox,
  CandidateReviewItem,
  MapAnalysis,
  OnlineExistingConditionsSource,
  PlanPdfAnalysis,
  PlanPdfChangedElements,
  PlanPdfElement,
  PlanRequestPayload,
  ProjectInput,
  ProjectRecord,
  SourceConfidenceEntry,
} from "../types";
import type { AddressSuggestion, AutoExistingConditionsUiStatus } from "../utils/dashboardDataTypes";
import type { CapabilityExposure } from "../utils/dashboardTypes";
import type { SidePanelKey } from "../utils/workspaceShell";
import type { SystemGenerationTarget } from "../utils/workflowConstants";

type PlanPdfPage = NonNullable<PlanPdfAnalysis["pages"]>[number];
type PlanPdfChangedElement = NonNullable<PlanPdfChangedElements["elements"]>[number];

type SaveProject = (options?: {
  silent?: boolean;
  projectInputOverride?: ProjectInput;
}) => Promise<ProjectRecord | null>;

type UseDashboardDataSourcesPanelPropsInput = {
  sourceHubLinks: DataSourcesPanelProps["sourceHubLinks"];
  sourceHubMetrics: DataSourcesPanelProps["sourceHubMetrics"];
  sourceConfidenceEntryCount: number;
  sourceConfidenceRows: SourceConfidenceEntry[];
  onOpenPanel: (panel: SidePanelKey) => void;
  planPdfAnalysis: PlanPdfAnalysis | undefined;
  planPdfSourceUrl: string;
  planPdfFirstPage: PlanPdfPage | null;
  planPdfElements: PlanPdfElement[];
  selectedPlanPdfElement: PlanPdfElement | null;
  planPdfChangedReport: PlanPdfChangedElements | null;
  planPdfChangedElements: PlanPdfChangedElement[];
  planPdfUnreadableItems: string[];
  planPdfBlockers: string[];
  planPdfUploadState: DataSourcesPanelProps["planPdfUploadState"];
  planPdfUploadMessage: string;
  planPdfElementDraftText: string;
  planPdfMoveX: string;
  planPdfMoveY: string;
  planPdfExtractionSummaryRows: DataSourcesPanelProps["planPdfExtractionSummaryRows"];
  planPdfClassificationPreviewRows: DataSourcesPanelProps["planPdfClassificationPreviewRows"];
  planPdfInputRef: RefObject<HTMLInputElement | null>;
  onUploadPlanPdf: (file: File) => Promise<void>;
  onSelectPlanPdfElement: DataSourcesPanelProps["onSelectPlanPdfElement"];
  onPlanPdfDraftTextChange: Dispatch<SetStateAction<string>>;
  onPlanPdfMoveXChange: Dispatch<SetStateAction<string>>;
  onPlanPdfMoveYChange: Dispatch<SetStateAction<string>>;
  onUpdatePlanPdfElement: DataSourcesPanelProps["onUpdatePlanPdfElement"];
  onExportPlanPdfJson: () => Promise<void>;
  onExportPlanPdf: () => Promise<void>;
  onPromptChange: Dispatch<SetStateAction<string>>;
  onStatusMessageChange: Dispatch<SetStateAction<string>>;
  capabilityAuditRows: CapabilityExposure[];
  onlineDiscoveryStatus: string;
  onlineDiscoveryRan: boolean;
  onlineDiscoverySources: OnlineExistingConditionsSource[];
  candidateReviewCounts: NonNullable<CandidateReviewInbox["counts"]>;
  candidateReviewItems: CandidateReviewItem[];
  candidateDecisionInFlight: DataSourcesPanelProps["candidateDecisionInFlight"];
  onCandidateDecision: (candidateId: string, decision: "accept" | "reject" | "pending") => Promise<void>;
  siteAddress: string;
  selectedAddressSuggestion: AddressSuggestion | null;
  addressSuggestions: AddressSuggestion[];
  onSiteAddressChange: Dispatch<SetStateAction<string>>;
  onSelectedAddressSuggestionChange: Dispatch<SetStateAction<AddressSuggestion | null>>;
  onAddressSuggestionsChange: Dispatch<SetStateAction<AddressSuggestion[]>>;
  onApplyAddress: () => Promise<void>;
  autoExistingConditionsStatus: AutoExistingConditionsUiStatus;
  mapSnapshotInputRef: RefObject<HTMLInputElement | null>;
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
  imageUploadState: DataSourcesPanelProps["imageUploadState"];
  imageUploadNote: string | null;
  mapSnapshotPath: string | null;
  mapAnalysis: MapAnalysis | null;
  onAnalyzeMapSnapshot: () => void;
  siteScaleLocked: boolean;
  onUnlockSite: () => void;
  onApplySite: () => Promise<void>;
  lotBounds: DataSourcesPanelProps["lotBounds"];
  siteTooLargeForWarning: boolean;
  missingSite: boolean;
  hasTerrainSource: boolean;
  siteTooLargeForGrading: boolean;
  onGenerateSystem: (target: SystemGenerationTarget) => void;
  onAnalyzeImageFeatures: () => void;
  missingImage: boolean;
  detectedPlacements: BuildingPlacement[];
  siteSelectionMode: boolean;
  buildingPlacements: BuildingPlacement[];
  detectionChoices: DataSourcesPanelProps["detectionChoices"];
  onDetectionChoicesChange: DataSourcesPanelProps["onDetectionChoicesChange"];
  onRunSelectedDetections: () => Promise<void>;
  onAnalyzeSiteAccess: () => void;
  confirmedObjectCounts: DataSourcesPanelProps["confirmedObjectCounts"];
  analysisIssueCount: number;
  mapAnalysisCounts: DataSourcesPanelProps["mapAnalysisCounts"];
  siteRotationDeg: number;
  siteRotationInput: string;
  onSiteRotationDegChange: Dispatch<SetStateAction<number>>;
  onSiteRotationInputChange: Dispatch<SetStateAction<string>>;
  onScheduleRotationSave: (value: number) => void;
  onFitToSite: () => void;
  onUseMapCenter: () => void;
  onAlignToRoad: () => void;
  drainageSourceOverride: DataSourcesPanelProps["drainageSourceOverride"];
  drainageSurfaceSummary: DataSourcesPanelProps["drainageSurfaceSummary"];
  onDrainageSourceOverrideChange: Dispatch<SetStateAction<"civora" | "user">>;
  currentProject: ProjectRecord | null;
  payloadPreview: PlanRequestPayload;
  onSaveProject: SaveProject;
  onUploadImage: (file: File) => Promise<void>;
};

export function useDashboardDataSourcesPanelProps({
  sourceHubLinks,
  sourceHubMetrics,
  sourceConfidenceEntryCount,
  sourceConfidenceRows,
  onOpenPanel,
  planPdfAnalysis,
  planPdfSourceUrl,
  planPdfFirstPage,
  planPdfElements,
  selectedPlanPdfElement,
  planPdfChangedReport,
  planPdfChangedElements,
  planPdfUnreadableItems,
  planPdfBlockers,
  planPdfUploadState,
  planPdfUploadMessage,
  planPdfElementDraftText,
  planPdfMoveX,
  planPdfMoveY,
  planPdfExtractionSummaryRows,
  planPdfClassificationPreviewRows,
  planPdfInputRef,
  onUploadPlanPdf,
  onSelectPlanPdfElement,
  onPlanPdfDraftTextChange,
  onPlanPdfMoveXChange,
  onPlanPdfMoveYChange,
  onUpdatePlanPdfElement,
  onExportPlanPdfJson,
  onExportPlanPdf,
  onPromptChange,
  onStatusMessageChange,
  capabilityAuditRows,
  onlineDiscoveryStatus,
  onlineDiscoveryRan,
  onlineDiscoverySources,
  candidateReviewCounts,
  candidateReviewItems,
  candidateDecisionInFlight,
  onCandidateDecision,
  siteAddress,
  selectedAddressSuggestion,
  addressSuggestions,
  onSiteAddressChange,
  onSelectedAddressSuggestionChange,
  onAddressSuggestionsChange,
  onApplyAddress,
  autoExistingConditionsStatus,
  mapSnapshotInputRef,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  imageUploadState,
  imageUploadNote,
  mapSnapshotPath,
  mapAnalysis,
  onAnalyzeMapSnapshot,
  siteScaleLocked,
  onUnlockSite,
  onApplySite,
  lotBounds,
  siteTooLargeForWarning,
  missingSite,
  hasTerrainSource,
  siteTooLargeForGrading,
  onGenerateSystem,
  onAnalyzeImageFeatures,
  missingImage,
  detectedPlacements,
  siteSelectionMode,
  buildingPlacements,
  detectionChoices,
  onDetectionChoicesChange,
  onRunSelectedDetections,
  onAnalyzeSiteAccess,
  confirmedObjectCounts,
  analysisIssueCount,
  mapAnalysisCounts,
  siteRotationDeg,
  siteRotationInput,
  onSiteRotationDegChange,
  onSiteRotationInputChange,
  onScheduleRotationSave,
  onFitToSite,
  onUseMapCenter,
  onAlignToRoad,
  drainageSourceOverride,
  drainageSurfaceSummary,
  onDrainageSourceOverrideChange,
  currentProject,
  payloadPreview,
  onSaveProject,
  onUploadImage,
}: UseDashboardDataSourcesPanelPropsInput): DataSourcesPanelProps {
  return useMemo(() => ({
    sourceHubLinks,
    sourceHubMetrics,
    sourceConfidenceEntryCount,
    sourceConfidenceRows,
    onOpenPanel,
    planPdfAnalysis,
    planPdfSourceUrl,
    planPdfFirstPage,
    planPdfElements,
    selectedPlanPdfElement,
    planPdfChangedReport,
    planPdfChangedElements,
    planPdfUnreadableItems,
    planPdfBlockers,
    planPdfUploadState,
    planPdfUploadMessage,
    planPdfElementDraftText,
    planPdfMoveX,
    planPdfMoveY,
    planPdfExtractionSummaryRows,
    planPdfClassificationPreviewRows,
    planPdfInputRef,
    onUploadPlanPdf,
    onSelectPlanPdfElement,
    onPlanPdfDraftTextChange,
    onPlanPdfMoveXChange,
    onPlanPdfMoveYChange,
    onUpdatePlanPdfElement: (elementId, patch) => void onUpdatePlanPdfElement(elementId, patch),
    onExportPlanPdfJson: () => void onExportPlanPdfJson(),
    onExportPlanPdf: () => void onExportPlanPdf(),
    onEditPdfByChat: () => {
      onPromptChange("change pool deck elevation");
      onOpenPanel("chat");
    },
    onWhatChanged: () => {
      onPromptChange("what changed?");
      onOpenPanel("chat");
    },
    onAskUnreadable: () => {
      onPromptChange("show unreadable text");
      onOpenPanel("chat");
    },
    onInvalidPlanPdfMove: () => {
      onStatusMessageChange("Moving a PDF-derived element requires explicit target x0/y0 coordinates.");
    },
    capabilityAuditRows,
    onlineDiscoveryStatus,
    onlineDiscoveryRan,
    onlineDiscoverySources,
    candidateReviewCounts,
    candidateReviewItems,
    candidateDecisionInFlight,
    onCandidateDecision: (candidateId, decision) => void onCandidateDecision(candidateId, decision),
    siteAddress,
    selectedAddressSuggestion,
    addressSuggestions,
    onSiteAddressChange,
    onSelectedAddressSuggestionChange,
    onAddressSuggestionsChange,
    onApplyAddress: () => void onApplyAddress(),
    autoExistingConditionsStatus,
    mapSnapshotInputRef,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
    imageUploadState,
    imageUploadNote,
    mapSnapshotPath,
    mapAnalysis,
    onAnalyzeMapSnapshot,
    siteScaleLocked,
    onUnlockSite,
    onApplySite: () => void onApplySite(),
    lotBounds,
    siteTooLargeForWarning,
    missingSite,
    hasTerrainSource,
    siteTooLargeForGrading,
    onGenerateSystem,
    onAnalyzeImageFeatures,
    missingImage,
    detectedPlacementsCount: detectedPlacements.length,
    siteSelectionMode,
    hasSiteObject: buildingPlacements.some((item) => item.type === "site"),
    detectionChoices,
    onDetectionChoicesChange,
    onRunSelectedDetections: () => void onRunSelectedDetections(),
    onAnalyzeSiteAccess,
    confirmedObjectCounts,
    analysisIssueCount,
    mapAnalysisCounts,
    siteRotationDeg,
    siteRotationInput,
    onSiteRotationDegChange,
    onSiteRotationInputChange,
    onScheduleRotationSave,
    onFitToSite,
    onUseMapCenter,
    onAlignToRoad,
    drainageSourceOverride,
    drainageSurfaceSummary,
    onDrainageSourceOverrideChange: (next) => {
      onDrainageSourceOverrideChange(next);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      void onSaveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: {
              ...(currentInput?.meta?.site_inputs ?? {}),
              drainage_source_override: next,
            },
          },
        },
      });
    },
    mapSnapshotUploadInputRef: mapSnapshotInputRef,
    onUploadImage,
  }), [
    addressSuggestions,
    analysisIssueCount,
    autoExistingConditionsStatus,
    buildingPlacements,
    candidateReviewCounts,
    candidateReviewItems,
    candidateDecisionInFlight,
    capabilityAuditRows,
    confirmedObjectCounts,
    currentProject?.project_input,
    detectedPlacements.length,
    detectionChoices,
    drainageSourceOverride,
    drainageSurfaceSummary,
    hasTerrainSource,
    imageUploadNote,
    imageUploadState,
    lotBounds,
    mapAnalysis,
    mapAnalysisCounts,
    mapSnapshotInputRef,
    mapSnapshotPath,
    missingImage,
    missingSite,
    onAddressSuggestionsChange,
    onAlignToRoad,
    onAnalyzeImageFeatures,
    onAnalyzeMapSnapshot,
    onAnalyzeSiteAccess,
    onApplyAddress,
    onApplySite,
    onCandidateDecision,
    onDetectionChoicesChange,
    onDrainageSourceOverrideChange,
    onExportPlanPdf,
    onExportPlanPdfJson,
    onFitToSite,
    onGenerateSystem,
    onOpenPanel,
    onPlanPdfDraftTextChange,
    onPlanPdfMoveXChange,
    onPlanPdfMoveYChange,
    onPromptChange,
    onRunSelectedDetections,
    onSaveProject,
    onScheduleRotationSave,
    onSelectPlanPdfElement,
    onSelectedAddressSuggestionChange,
    onSiteAddressChange,
    onSiteRotationDegChange,
    onSiteRotationInputChange,
    onStatusMessageChange,
    onUnlockSite,
    onUpdatePlanPdfElement,
    onUploadImage,
    onUploadPlanPdf,
    onUseMapCenter,
    onlineDiscoveryRan,
    onlineDiscoverySources,
    onlineDiscoveryStatus,
    payloadPreview,
    planPdfAnalysis,
    planPdfBlockers,
    planPdfChangedElements,
    planPdfChangedReport,
    planPdfClassificationPreviewRows,
    planPdfElementDraftText,
    planPdfElements,
    planPdfExtractionSummaryRows,
    planPdfFirstPage,
    planPdfInputRef,
    planPdfMoveX,
    planPdfMoveY,
    planPdfSourceUrl,
    planPdfUnreadableItems,
    planPdfUploadMessage,
    planPdfUploadState,
    selectedAddressSuggestion,
    selectedPlanPdfElement,
    siteAddress,
    siteRotationDeg,
    siteRotationInput,
    siteScaleLocked,
    siteSelectionMode,
    siteTooLargeForGrading,
    siteTooLargeForWarning,
    sourceConfidenceEntryCount,
    sourceConfidenceRows,
    sourceHubLinks,
    sourceHubMetrics,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
  ]);
}
