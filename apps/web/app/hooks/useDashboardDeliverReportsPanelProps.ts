import { useMemo } from "react";
import type { ComponentProps, Dispatch, SetStateAction } from "react";

import { DashboardReportsQuantitiesPanel } from "../components/DashboardReportsQuantitiesPanel";
import { DeliverPanel } from "../components/DeliverPanel";
import type { PlanSheetAnnotation } from "../components/PlanSheetEditor";
import type {
  DesignAlternativesV1,
  Issue,
  ReviewIssue,
  ReviewIssueTrackerV1,
  SmartFixRecommendation,
  SourceConfidenceEntry,
} from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";

type DeliverPanelProps = ComponentProps<typeof DeliverPanel>;
type DashboardReportsQuantitiesPanelProps = ComponentProps<typeof DashboardReportsQuantitiesPanel>;

type UseDashboardDeliverReportsPanelPropsInput = {
  sidePanelForRender: SidePanelKey | null;
  reviewPackageFlowSummary: DeliverPanelProps["reviewPackageFlowSummary"];
  planPreviewUrl: string;
  hasBackendResult: boolean;
  placedObjectCount: number;
  sidebarTrustScore: string;
  exportActionMessage: string;
  exportBlockReason: string;
  planSheetSet: DeliverPanelProps["planSheetSet"];
  planSheetBlockers: string[];
  projectName: string;
  addressLabel: string;
  lotWidth: number;
  lotHeight: number;
  placements: DeliverPanelProps["placements"];
  autoSiteContextFlowSummary: DeliverPanelProps["autoSiteContextFlowSummary"];
  sidebarReleaseStatus: string;
  reviewGateItems: DeliverPanelProps["reviewGateItems"];
  topSmartFix: SmartFixRecommendation | null;
  onMakeReviewPackage: () => void;
  onPlanSheetExportPdf: () => void;
  onExportDxf: () => void;
  onExportReport: () => void;
  onOpenPanel: (panel: SidePanelKey) => void;
  onPlanSheetTitleBlockUpdate: DeliverPanelProps["onPlanSheetTitleBlockUpdate"];
  onPlanSheetScaleChange: DeliverPanelProps["onPlanSheetScaleChange"];
  onPlanSheetViewportUpdate: DeliverPanelProps["onPlanSheetViewportUpdate"];
  onPlanSheetViewportDelete: DeliverPanelProps["onPlanSheetViewportDelete"];
  onPlanSheetAddNote: DeliverPanelProps["onPlanSheetAddNote"];
  onPlanSheetAddAnnotation: (type: PlanSheetAnnotation["type"], text: string) => void;
  onStatusMessageChange: Dispatch<SetStateAction<string>>;
  onPlanSheetAddViewport: DeliverPanelProps["onPlanSheetAddViewport"];
  onPlanSheetViewportLayerToggle: DeliverPanelProps["onPlanSheetViewportLayerToggle"];
  onPlanSheetViewportScaleLockToggle: DeliverPanelProps["onPlanSheetViewportScaleLockToggle"];
  onPlanSheetGrayscaleToggle: DeliverPanelProps["onPlanSheetGrayscaleToggle"];
  onPlanSheetAddRevision: DeliverPanelProps["onPlanSheetAddRevision"];
  onPlanSheetAddTable: DeliverPanelProps["onPlanSheetAddTable"];
  onPlanSheetAddDetailBlock: DeliverPanelProps["onPlanSheetAddDetailBlock"];
  onPlanSheetAddReference: DeliverPanelProps["onPlanSheetAddReference"];
  onPlanSheetSelectSheet: DeliverPanelProps["onPlanSheetSelectSheet"];
  onCreateReviewSheet: DeliverPanelProps["onCreateReviewSheet"];
  onPlanSheetExportJson: DeliverPanelProps["onPlanSheetExportJson"];
  onSmartFixAction: DeliverPanelProps["onSmartFixAction"];
  issues: Issue[];
  analysisIssueCount: number;
  sidebarMissingInputCount: number;
  sidebarAssumptionCount: number;
  blockedSystemCount: number;
  engineeringHealthPanelLinks: DashboardReportsQuantitiesPanelProps["reports"]["engineeringHealthLinks"];
  drainageIssueApplyLabel: DashboardReportsQuantitiesPanelProps["reports"]["drainageIssueApplyLabel"];
  canApplyDrainageIssue: DashboardReportsQuantitiesPanelProps["reports"]["canApplyDrainageIssue"];
  getIssueGuidance: DashboardReportsQuantitiesPanelProps["reports"]["getIssueGuidance"];
  onApplyDrainageIssue: DashboardReportsQuantitiesPanelProps["reports"]["onApplyDrainageIssue"];
  reviewIssueItems: ReviewIssue[];
  openReviewIssueCount: number;
  reviewIssueTracker: ReviewIssueTrackerV1;
  drainageReviewIssueCount: number;
  onPromptChange: Dispatch<SetStateAction<string>>;
  sidebarTruthItems: DashboardReportsQuantitiesPanelProps["reports"]["truthGates"];
  designAlternatives: DesignAlternativesV1;
  designAlternativeItems: DashboardReportsQuantitiesPanelProps["reports"]["designAlternatives"]["alternatives"];
  topDesignAlternative: DashboardReportsQuantitiesPanelProps["reports"]["designAlternatives"]["topAlternative"];
  selectedDesignAlternativeId: string;
  designAlternativeQuantityAvailable: boolean;
  onDesignAlternativesAction: DashboardReportsQuantitiesPanelProps["reports"]["designAlternatives"]["onAction"];
  sourceConfidenceSummary: DashboardReportsQuantitiesPanelProps["reports"]["sourceConfidence"]["summary"];
  sourceConfidenceRows: SourceConfidenceEntry[];
  sourceConfidenceEntryCount: number;
  quantityRows: DashboardReportsQuantitiesPanelProps["quantities"]["rows"];
  staleSystemCount: number;
  onExportQuantityReviewReport: DashboardReportsQuantitiesPanelProps["quantities"]["onExportReport"];
  formatMetric: DashboardReportsQuantitiesPanelProps["quantities"]["formatMetric"];
  statusLabelForQuantityReview: DashboardReportsQuantitiesPanelProps["quantities"]["statusLabelForQuantityReview"];
};

export function useDashboardDeliverReportsPanelProps({
  sidePanelForRender,
  reviewPackageFlowSummary,
  planPreviewUrl,
  hasBackendResult,
  placedObjectCount,
  sidebarTrustScore,
  exportActionMessage,
  exportBlockReason,
  planSheetSet,
  planSheetBlockers,
  projectName,
  addressLabel,
  lotWidth,
  lotHeight,
  placements,
  autoSiteContextFlowSummary,
  sidebarReleaseStatus,
  reviewGateItems,
  topSmartFix,
  onMakeReviewPackage,
  onPlanSheetExportPdf,
  onExportDxf,
  onExportReport,
  onOpenPanel,
  onPlanSheetTitleBlockUpdate,
  onPlanSheetScaleChange,
  onPlanSheetViewportUpdate,
  onPlanSheetViewportDelete,
  onPlanSheetAddNote,
  onPlanSheetAddAnnotation,
  onStatusMessageChange,
  onPlanSheetAddViewport,
  onPlanSheetViewportLayerToggle,
  onPlanSheetViewportScaleLockToggle,
  onPlanSheetGrayscaleToggle,
  onPlanSheetAddRevision,
  onPlanSheetAddTable,
  onPlanSheetAddDetailBlock,
  onPlanSheetAddReference,
  onPlanSheetSelectSheet,
  onCreateReviewSheet,
  onPlanSheetExportJson,
  onSmartFixAction,
  issues,
  analysisIssueCount,
  sidebarMissingInputCount,
  sidebarAssumptionCount,
  blockedSystemCount,
  engineeringHealthPanelLinks,
  drainageIssueApplyLabel,
  canApplyDrainageIssue,
  getIssueGuidance,
  onApplyDrainageIssue,
  reviewIssueItems,
  openReviewIssueCount,
  reviewIssueTracker,
  drainageReviewIssueCount,
  onPromptChange,
  sidebarTruthItems,
  designAlternatives,
  designAlternativeItems,
  topDesignAlternative,
  selectedDesignAlternativeId,
  designAlternativeQuantityAvailable,
  onDesignAlternativesAction,
  sourceConfidenceSummary,
  sourceConfidenceRows,
  sourceConfidenceEntryCount,
  quantityRows,
  staleSystemCount,
  onExportQuantityReviewReport,
  formatMetric,
  statusLabelForQuantityReview,
}: UseDashboardDeliverReportsPanelPropsInput) {
  const deliverPanelProps = useMemo<DeliverPanelProps>(() => ({
    reviewPackageFlowSummary,
    planPreviewUrl,
    hasBackendResult,
    placedObjectCount,
    sidebarTrustScore,
    exportActionMessage,
    exportBlockReason,
    planSheetSet,
    planSheetBlockers,
    projectName,
    addressLabel,
    lotWidth,
    lotHeight,
    placements,
    autoSiteContextFlowSummary,
    sidebarReleaseStatus,
    reviewGateItems,
    topSmartFix,
    onMakeReviewPackage,
    onPlanSheetExportPdf,
    onExportDxf,
    onExportReport,
    onOpenQuantities: () => onOpenPanel("quantities"),
    onPlanSheetTitleBlockUpdate,
    onPlanSheetScaleChange,
    onPlanSheetViewportUpdate,
    onPlanSheetViewportDelete,
    onPlanSheetAddNote,
    onPlanSheetAddLabel: () => {
      onPlanSheetAddAnnotation("label", "New sheet label");
      onStatusMessageChange("Added a sheet label.");
    },
    onPlanSheetAddCallout: () => {
      onPlanSheetAddAnnotation("callout", "Review callout");
      onStatusMessageChange("Added a sheet callout.");
    },
    onPlanSheetAddDimension: () => {
      onPlanSheetAddAnnotation("dimension", "Dimension reference");
      onStatusMessageChange("Added a dimension note.");
    },
    onPlanSheetAddViewport,
    onPlanSheetViewportLayerToggle,
    onPlanSheetViewportScaleLockToggle,
    onPlanSheetGrayscaleToggle,
    onPlanSheetAddRevision,
    onPlanSheetAddTable,
    onPlanSheetAddDetailBlock,
    onPlanSheetAddReference,
    onPlanSheetSelectSheet,
    onCreateReviewSheet,
    onPlanSheetExportJson,
    onSmartFixAction,
  }), [
    addressLabel,
    autoSiteContextFlowSummary,
    exportActionMessage,
    exportBlockReason,
    hasBackendResult,
    lotHeight,
    lotWidth,
    onCreateReviewSheet,
    onExportDxf,
    onExportReport,
    onMakeReviewPackage,
    onOpenPanel,
    onPlanSheetAddAnnotation,
    onPlanSheetAddDetailBlock,
    onPlanSheetAddNote,
    onPlanSheetAddReference,
    onPlanSheetAddRevision,
    onPlanSheetAddTable,
    onPlanSheetAddViewport,
    onPlanSheetExportJson,
    onPlanSheetExportPdf,
    onPlanSheetGrayscaleToggle,
    onPlanSheetScaleChange,
    onPlanSheetSelectSheet,
    onPlanSheetTitleBlockUpdate,
    onPlanSheetViewportDelete,
    onPlanSheetViewportLayerToggle,
    onPlanSheetViewportScaleLockToggle,
    onPlanSheetViewportUpdate,
    onSmartFixAction,
    onStatusMessageChange,
    placedObjectCount,
    placements,
    planPreviewUrl,
    planSheetBlockers,
    planSheetSet,
    projectName,
    reviewGateItems,
    reviewPackageFlowSummary,
    sidebarReleaseStatus,
    sidebarTrustScore,
    topSmartFix,
  ]);

  const reportsQuantitiesPanelProps = useMemo<DashboardReportsQuantitiesPanelProps>(() => ({
    activePanel: sidePanelForRender === "quantities" ? "quantities" : "reports",
    reports: {
      stats: [
        { label: "QA items", value: issues.length + analysisIssueCount },
        { label: "Missing", value: sidebarMissingInputCount },
        { label: "Assumptions", value: sidebarAssumptionCount },
        { label: "Needs input", value: blockedSystemCount },
      ],
      engineeringHealthLinks: engineeringHealthPanelLinks,
      issues,
      drainageIssueApplyLabel,
      canApplyDrainageIssue,
      getIssueGuidance,
      onApplyDrainageIssue,
      onOpenSidePanel: onOpenPanel,
      reviewIssueTracker: {
        issues: reviewIssueItems,
        openIssueCount: openReviewIssueCount,
        totalIssueCount: reviewIssueTracker.issue_count ?? reviewIssueItems.length,
        needsReviewCount: reviewIssueTracker.needs_review_count ?? 0,
        drainageIssueCount: drainageReviewIssueCount,
        waivedCount: reviewIssueTracker.by_status?.waived_review_required ?? 0,
        truthLabel: reviewIssueTracker.truth_label,
        onAskCommand: (command) => {
          onPromptChange(command);
          onOpenPanel("chat");
        },
        onIssueCommand: (action, issueId) => {
          onPromptChange(`${action} issue ${issueId}`);
          onOpenPanel("chat");
        },
      },
      truthGates: sidebarTruthItems,
      reviewGates: reviewGateItems,
      designAlternatives: {
        designAlternatives,
        alternatives: designAlternativeItems,
        topAlternative: topDesignAlternative,
        selectedAlternativeId: selectedDesignAlternativeId,
        quantityAvailable: designAlternativeQuantityAvailable,
        onAction: onDesignAlternativesAction,
      },
      sourceConfidence: {
        summary: sourceConfidenceSummary,
        entries: sourceConfidenceRows,
        totalEntryCount: sourceConfidenceEntryCount,
      },
    },
    quantities: {
      rows: quantityRows,
      staleSystemCount,
      trustScoreLabel: sidebarTrustScore,
      onExportReport: onExportQuantityReviewReport,
      formatMetric,
      statusLabelForQuantityReview,
    },
  }), [
    analysisIssueCount,
    blockedSystemCount,
    canApplyDrainageIssue,
    designAlternativeItems,
    designAlternativeQuantityAvailable,
    designAlternatives,
    drainageIssueApplyLabel,
    drainageReviewIssueCount,
    engineeringHealthPanelLinks,
    formatMetric,
    getIssueGuidance,
    issues,
    onApplyDrainageIssue,
    onDesignAlternativesAction,
    onExportQuantityReviewReport,
    onOpenPanel,
    onPromptChange,
    openReviewIssueCount,
    quantityRows,
    reviewGateItems,
    reviewIssueItems,
    reviewIssueTracker.by_status,
    reviewIssueTracker.issue_count,
    reviewIssueTracker.needs_review_count,
    reviewIssueTracker.truth_label,
    selectedDesignAlternativeId,
    sidebarAssumptionCount,
    sidebarMissingInputCount,
    sidebarTruthItems,
    sidebarTrustScore,
    sidePanelForRender,
    sourceConfidenceEntryCount,
    sourceConfidenceRows,
    sourceConfidenceSummary,
    staleSystemCount,
    statusLabelForQuantityReview,
    topDesignAlternative,
  ]);

  return {
    deliverPanelProps,
    reportsQuantitiesPanelProps,
  };
}
