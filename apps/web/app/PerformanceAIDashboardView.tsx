"use client";
/* eslint-disable react-hooks/exhaustive-deps */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { getJson, postJson } from "../lib/api";

import type {
  Assumption,
  Issue,
  ProjectRecord,
  ProjectInput,
  JobSummary,
  PlanMeta,
  PlanResponse,
  SurveySlopeResponse,
  MapAnalysis,
  PreviewResponse,
  UserRecord,
  PlanToolMode,
  ControlOverrides,
  BuildingPlacement,
  SiteObjectType,
  ChatDecisionResponse,
  ChatMessage,
  DisciplineToggle,
  PlanRequestPayload,
  PreviewRequestPayload,
  SiteInputs,
  CandidateReviewInbox,
  DesignAlternativesV1,
  ReviewIssueTrackerV1,
  SourceConfidenceMap,
  SmartFixRecommendation,
  EngineDepthDashboard,
} from "./types";

import {
  DEFAULT_SYSTEM_STATUS,
  EMPTY_REACTIVE_VALIDATION,
  OVERSIZED_SITE_MESSAGE,
  REACTIVE_EDIT_POLICY_PREFERENCE,
  SITE_GRADING_HARD_BLOCK_ACRES,
  SITE_WARNING_ACRES,
  formatStageLabel,
  statusLabelForQuantityReview,
  type EngineeringSystemKey,
  type ReactiveValidationState,
  type SystemGenerationTarget,
} from "./utils/workflowConstants";
import { buildDashboardCapabilityAuditRows } from "./utils/dashboardCapabilityAuditRows";
import { resolveDashboardPanelStatus } from "./utils/dashboardPanelStatus";
import { resolveActivePrimaryWorkflowKey } from "./utils/dashboardPrimaryWorkflows";
import { buildDashboardPrimaryWorkflowItems } from "./utils/dashboardPrimaryWorkflowItems";
import {
  DASHBOARD_SOURCE_HUB_LINKS,
  DASHBOARD_SUPPORTED_SHORTCUTS,
  buildDashboardLibraryPanelSections,
  buildDashboardStandardsPanelCriteria,
} from "./utils/dashboardShellConfig";
import { DASHBOARD_CAD_TOOL_GROUPS } from "./utils/dashboardCadToolGroups";
import {
  buildGenerateLayoutContext,
  systemsImpactedByPlacement,
} from "./utils/dashboardGenerateLayoutContext";
import {
  buildDashboardCivil3DWorkflowBlockers,
  buildDashboardWorkflowActionHints,
} from "./utils/dashboardWorkflowHints";
import {
  canApplyDashboardDrainageIssue,
  getDashboardDrainageIssueApplyLabel,
  getDashboardDrainageIssueGuidance,
} from "./utils/dashboardDrainageIssueGuidance";
import { buildDashboardSiteGradingView } from "./utils/dashboardSiteGradingView";
import {
  applyDashboardReactiveSystemStatusFromPlanResult,
  buildDashboardAssumptionsFromPlanResult,
  buildDashboardIssuesFromPlanResult,
} from "./utils/dashboardPlanResultView";
import {
  defaultAssumptions,
  toReadableLabel,
  parsePositiveNumber,
  formatMetric,
  summarizePlanResponse,
} from "./utils/formatting";

import {
  createChatMessage,
  createWelcomeMessage,
} from "./utils/chat";
import {
  hasPreviewablePlanResult,
  isDemoWorkspaceQuery,
  isSeededDemoProjectId,
  isSeededDemoWorkspaceQuery,
} from "./utils/demoWorkspaceData";
import { buildDashboardDemoWorkspaceSeed } from "./utils/dashboardDemoWorkspaceSeed";
import { createDefaultPlanSheetSet } from "./utils/planSheetDefaults";
import {
  ADD_MENU_SECTIONS,
  SITE_OBJECT_CATALOG,
} from "./utils/siteObjectCatalog";

import { uploadedImageSrc } from "./utils/auth";
import {
  chatFailureMessage,
  formatTimestamp,
  jobDetailMessage,
  panelErrorMessage,
} from "./utils/dashboardStatus";
import { buildDashboardWorkflowState } from "./utils/dashboardWorkflowState";
import { buildDashboardArtifactPayload } from "./utils/dashboardPayloads";
import { runDashboardApplyProjectInput } from "./utils/dashboardProjectRestoreActions";
import { buildDashboardObjectSelectionView } from "./utils/dashboardObjectSelectionView";
import {
  hasAddressCoordinates,
  type AddressSuggestion,
  type AutoExistingConditionsUiStatus,
  type CustomerTemplateRegistryResponse,
  type GenerateFlowSummary,
  type ReviewPackageFlowSummary,
  type UtilityCatalogResponse,
} from "./utils/dashboardDataTypes";
import {
  buildCandidateReviewInbox,
  buildDesignAlternatives,
  buildReviewIssueTracker,
  buildSourceConfidenceMap,
} from "./utils/reviewWorkflowData";
import {
  applyPreviewLayerGating,
  buildPreviewLayerList,
} from "./utils/dashboardPreviewLayers";
import {
  buildDashboardPreview3DView,
} from "./utils/dashboardPreview3DItems";
import {
  buildCanonicalWorkspaceBlockers,
  buildGeneratePreflightBlockers,
} from "./utils/dashboardWorkspaceBlockers";
import { buildProjectTruthLabels } from "./utils/dashboardProjectTruth";
import { buildDashboardSetupTruth } from "./utils/dashboardSetupTruth";
import {
  buildSmartFixBlockedReasons,
  buildSmartFixRecommendations,
} from "./utils/dashboardSmartFix";
import {
  buildDesignAlternativeSummary,
  buildReviewIssueCollections,
} from "./utils/dashboardReviewCollections";
import { buildDashboardSourceConfidenceView } from "./utils/dashboardSourceConfidenceView";
import {
  progressTimelineDotClass,
  progressTimelineStatusClass,
} from "./utils/dashboardWorkflowProgress";
import { buildDashboardSystemHealthItems } from "./utils/dashboardSystemHealth";
import {
  markCivoraInteraction,
  measureCivoraInteractionAfterPaint,
} from "./utils/performanceProbes";
import {
  runDashboardStartBlankSite,
  runDashboardStartSiteBoundaryDraw,
  runDashboardToggleSiteLock,
  runDashboardUnlockSite,
  type DashboardSiteSetupActions,
} from "./utils/dashboardSiteSetupActions";
import { createDashboardPlanSheetActions } from "./utils/dashboardPlanSheetActions";
import {
  runDashboardExplainPlan,
  runDashboardPreviewPlan,
  runDashboardQueuePreviewRefresh,
} from "./utils/dashboardPlanActionHelpers";
import { runDashboardSetMessageFeedback } from "./utils/dashboardChatFeedbackActions";
import {
  buildDashboardReactiveChangedSystems,
  buildDashboardReactiveChangedTargets,
  buildDashboardReactiveRerunSummary,
  resolveDashboardReactiveAffectedRunTarget,
  runDashboardReactiveValidation,
} from "./utils/dashboardReactiveRerunView";
import { createDashboardExportActions } from "./utils/dashboardExportActions";
import { useDashboardFloatingObjectActions } from "./hooks/useDashboardFloatingObjectActions";
import { useDashboardJobActions } from "./hooks/useDashboardJobActions";
import { useDashboardJobLoader } from "./hooks/useDashboardJobLoader";
import { useDashboardExistingConditionsUpload } from "./hooks/useDashboardExistingConditionsUpload";
import { useDashboardImageDetectionActions } from "./hooks/useDashboardImageDetectionActions";
import { useDashboardAutoExistingConditions } from "./hooks/useDashboardAutoExistingConditions";
import { useDashboardApplySiteAction } from "./hooks/useDashboardApplySiteAction";
import { useDashboardSiteAddressAction } from "./hooks/useDashboardSiteAddressAction";
import { useDashboardSiteSetupUtilityActions } from "./hooks/useDashboardSiteSetupUtilityActions";
import { useDashboardSelectedDetectionActions } from "./hooks/useDashboardSelectedDetectionActions";
import { useDashboardReviewWorkflowActions } from "./hooks/useDashboardReviewWorkflowActions";
import { useDashboardPlanPdfDerivedState } from "./hooks/useDashboardPlanPdfDerivedState";
import { useDashboardEngineeringReviewState } from "./hooks/useDashboardEngineeringReviewState";
import { useDashboardAutoSiteContextState } from "./hooks/useDashboardAutoSiteContextState";
import { useDashboardShellReviewState } from "./hooks/useDashboardShellReviewState";
import { useDashboardStartPanelProps } from "./hooks/useDashboardStartPanelProps";
import { useDashboardDataSourcesPanelProps } from "./hooks/useDashboardDataSourcesPanelProps";
import { useDashboardGenerationPanelProps } from "./hooks/useDashboardGenerationPanelProps";
import { useDashboardDraftHistoryState } from "./hooks/useDashboardDraftHistoryState";
import { useDashboardViewportState } from "./hooks/useDashboardViewportState";
import { useDashboardDeliverReportsPanelProps } from "./hooks/useDashboardDeliverReportsPanelProps";
import { useDashboardSupportPanelProps } from "./hooks/useDashboardSupportPanelProps";
import { useDashboardReviewUtilityPanelProps } from "./hooks/useDashboardReviewUtilityPanelProps";
import { useDashboardCanvasAreaProps } from "./hooks/useDashboardCanvasAreaProps";
import { useDashboardChatCommandProps } from "./hooks/useDashboardChatCommandProps";
import { useDashboardSiteBoundaryDrawAction } from "./hooks/useDashboardSiteBoundaryDrawAction";
import {
  useDashboardSiteAccessAnalysis,
  type DashboardAccessAnalysisIssue,
  type DashboardAccessAnalysisPath,
} from "./hooks/useDashboardSiteAccessAnalysis";
import { useDashboardProjectActions } from "./hooks/useDashboardProjectActions";
import { useDashboardProjectLoad } from "./hooks/useDashboardProjectLoad";
import { useDashboardPlanPdfActions } from "./hooks/useDashboardPlanPdfActions";
import { useDashboardMapAnalysisActions } from "./hooks/useDashboardMapAnalysisActions";
import { useDashboardProjectSave } from "./hooks/useDashboardProjectSave";
import { useDashboardProjectResultLoader } from "./hooks/useDashboardProjectResultLoader";
import { useDashboardShellShortcuts } from "./hooks/useDashboardShellShortcuts";
import { useDashboardWorkspaceReset } from "./hooks/useDashboardWorkspaceReset";
import { useDashboardObjectUpdateAction } from "./hooks/useDashboardObjectUpdateAction";
import { useDashboardObjectRemoveRestoreActions } from "./hooks/useDashboardObjectRemoveRestoreActions";
import { useDashboardAddObjectAction } from "./hooks/useDashboardAddObjectAction";
import { useDashboardReviewConceptActions } from "./hooks/useDashboardReviewConceptActions";
import { useDashboardPlanPayloadBuilder } from "./hooks/useDashboardPlanPayloadBuilder";
import { useDashboardChatDecisionContextBuilder } from "./hooks/useDashboardChatDecisionContextBuilder";
import { useDashboardSheetIntentHandler } from "./hooks/useDashboardSheetIntentHandler";
import { useDashboardObjectPersistenceActions } from "./hooks/useDashboardObjectPersistenceActions";
import { useDashboardPlacementActionHandlers } from "./hooks/useDashboardPlacementActionHandlers";
import { useDashboardCommandUtilityActions } from "./hooks/useDashboardCommandUtilityActions";
import { useDashboardDenseConceptAction } from "./hooks/useDashboardDenseConceptAction";
import { useDashboardActionIntentHandler } from "./hooks/useDashboardActionIntentHandler";
import { useDashboardPowerCommandHandler } from "./hooks/useDashboardPowerCommandHandler";
import { useDashboardObjectCommandIntentHandler } from "./hooks/useDashboardObjectCommandIntentHandler";
import { useDashboardChatSendHandlers } from "./hooks/useDashboardChatSendHandlers";
import { useDashboardInfoIntentHandler } from "./hooks/useDashboardInfoIntentHandler";
import { useDashboardDrainageAutofix } from "./hooks/useDashboardDrainageAutofix";
import { useDashboardDrainageIssueApplyAction } from "./hooks/useDashboardDrainageIssueApplyAction";
import { useDashboardGenerateSystemAction } from "./hooks/useDashboardGenerateSystemAction";
import { useDashboardSiteGeometryActions } from "./hooks/useDashboardSiteGeometryActions";
import { useDashboardPayloadPreviewState } from "./hooks/useDashboardPayloadPreviewState";
import { useDashboardAutoFitSite } from "./hooks/useDashboardAutoFitSite";
import { useDashboardGenerateFlowCoordinator } from "./hooks/useDashboardGenerateFlowCoordinator";
import { useDashboardSystemEvidenceView } from "./hooks/useDashboardSystemEvidenceView";
import { useDashboardScaleSaveScheduler } from "./hooks/useDashboardScaleSaveScheduler";
import { useDashboardContextualToolbarTools } from "./hooks/useDashboardContextualToolbarTools";
import type {
  ApprovalState,
  CadToolRequestForPreview,
  CapabilityExposure,
  DraftBlockDefinition,
  PerformanceAIDashboardProps,
} from "./utils/dashboardTypes";
import { buildCadEntityPreview, type CadEntityPreview } from "./utils/cadEntityPreview";
import {
  DEFAULT_PROJECT_STATUS,
  disciplinePanelLinks,
  engineeringHealthPanelLinks,
  formatProjectStatusText,
  isDashboardDisciplinePanel,
  projectStatusDisplayLabel,
  resolveDashboardControlsHealthStatus,
  resolveDashboardSidebarModeStatus,
  resolveSidePanelForRender,
  sidePanelCopy,
  type ProjectStatusSummary,
  type SidebarStatus,
  type SidePanelKey,
  type WorkspaceMode,
} from "./utils/workspaceShell";

import AppHeader from "./components/AppHeader";
import AuthScreen from "./components/AuthScreen";
import ChatPanel from "./components/ChatPanel";
import {
  type Civil3DWorkflowTab,
  type RoadwayWorkbenchTab,
} from "./components/CivilRoadwayWorkbench";
import { DashboardHomePanel } from "./components/DashboardHomePanel";
import { DashboardDetailsPanel } from "./components/DashboardDetailsPanel";
import { DataSourcesPanel } from "./components/DataSourcesPanel";
import { DeliverPanel } from "./components/DeliverPanel";
import { DisciplinePanelTabs } from "./components/DisciplinePanelTabs";
import { DrainageWorkbenchPanel } from "./components/DrainageWorkbenchPanel";
import { FilesPanel } from "./components/FilesPanel";
import type { PreviewLayerVisibility } from "./components/FloatingLayerManager";
import { GeneratePanel } from "./components/GeneratePanel";
import { GradingWorkbenchPanel } from "./components/GradingWorkbenchPanel";
import { ImportSurveyPanel } from "./components/ImportSurveyPanel";
import { JobsPanel } from "./components/JobsPanel";
import { LandscapeWorkbenchPanel } from "./components/LandscapeWorkbenchPanel";
import { LayersPanel } from "./components/LayersPanel";
import { LibrariesPanel } from "./components/LibrariesPanel";
import { ModelReviewPanel } from "./components/ModelReviewPanel";
import { DashboardObjectManagerPanel } from "./components/DashboardObjectManagerPanel";
import { DashboardReportsQuantitiesPanel } from "./components/DashboardReportsQuantitiesPanel";
import PinnedCommandBar from "./components/PinnedCommandBar";
import { ProjectsDrawer } from "./components/ProjectsDrawer";
import { RoadwayWorkbenchPanel } from "./components/RoadwayWorkbenchPanel";
import { SanitaryWorkbenchPanel } from "./components/SanitaryWorkbenchPanel";
import { SiteSetupPanel } from "./components/SiteSetupPanel";
import { StandardsPanel } from "./components/StandardsPanel";
import { SystemReadinessPanel } from "./components/SystemReadinessPanel";
import { TemplatesPanel } from "./components/TemplatesPanel";
import { TrustPanel } from "./components/TrustPanel";
import { UtilityCatalogPanel } from "./components/UtilityCatalogPanel";
import { UtilitiesWorkbenchPanel } from "./components/UtilitiesWorkbenchPanel";
import { WaterFireFlowWorkbenchPanel } from "./components/WaterFireFlowWorkbenchPanel";
import { WorkspaceCanvasArea } from "./components/WorkspaceCanvasArea";
import { WorkspaceLeftRail } from "./components/WorkspaceLeftRail";
import { WorkspaceSettingsPanel } from "./components/WorkspaceSettingsPanel";
import WorkspaceRightPanel from "./components/WorkspaceRightPanel";
import WorkspaceToasts, { type WorkspaceToast } from "./components/WorkspaceToasts";
import type {
  PlanSheetSet,
} from "./components/PlanSheetEditor";
import useChatPersistence from "./hooks/useChatPersistence";
import usePreviewReview from "./hooks/usePreviewReview";
import useJobPolling from "./hooks/useJobPolling";
import useAuthState from "./hooks/useAuthState";
import useProjectsState from "./hooks/useProjectsState";
import useJobsState from "./hooks/useJobsState";
import { useDashboardLeftSidebarState } from "./hooks/useDashboardLeftSidebarState";
import { useDashboardObjectManagerActions } from "./hooks/useDashboardObjectManagerActions";
import { useDashboardPreviewModeState } from "./hooks/useDashboardPreviewModeState";
import { useDashboardSidePanelState } from "./hooks/useDashboardSidePanelState";
import { useWorkspaceShortcuts } from "./hooks/useWorkspaceShortcuts";
import { mapSurveyPointsToSite } from "./utils/dashboardExistingConditionsUpload";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { WorkspaceShortcutsOverlay } from "./components/WorkspaceShortcutsOverlay";

function PerformanceAIDashboardView({
  forceDemoWorkspace = false,
}: PerformanceAIDashboardProps = {}) {
  const pathname = usePathname();
  const routeDemoWorkspaceEnabled = pathname === "/demo/workspace";
  const [projectType, setProjectType] = useState("");
  const [units, setUnits] = useState("ft");
  const [prompt, setPrompt] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [
    createWelcomeMessage(),
  ]);
  const [demoWorkspaceEnabled, setDemoWorkspaceEnabled] = useState(false);
  const [clientMounted, setClientMounted] = useState(false);
  const queryDemoWorkspaceEnabled = clientMounted && isDemoWorkspaceQuery();
  const seededDemoWorkspaceEnabled = clientMounted && isSeededDemoWorkspaceQuery();
  const effectiveDemoWorkspaceEnabled =
    forceDemoWorkspace || routeDemoWorkspaceEnabled || demoWorkspaceEnabled || queryDemoWorkspaceEnabled;
  const {
    leftSidebarOpen,
    setLeftSidebarOpen,
    sidebarRendered,
    sidebarVisible,
    setSidebarVisible,
  } = useDashboardLeftSidebarState();
  const [, setChatCollapsed] = useState(false);
  const [commandBarExpanded, setCommandBarExpanded] = useState(false);
  const {
    activeSidePanel,
    setActiveSidePanel,
    renderedSidePanel,
    setRenderedSidePanel,
    sidePanelVisible,
    setSidePanelVisible,
    rightRailCollapsed,
    setRightRailCollapsed,
    panelOpenProbeRef,
    panelCloseProbeRef,
    sidePanelCloseTimeoutRef,
  } = useDashboardSidePanelState();
  const {
    handleViewportCenter,
    handleViewportFootprint,
    mobileViewport,
    setViewportCenter,
    setViewportFootprint,
    viewportCenter,
    viewportFootprint,
  } = useDashboardViewportState({
    onCollapseRightRail: setRightRailCollapsed,
  });
  const [workspaceChromeMinimized, setWorkspaceChromeMinimized] = useState(true);
  const [cadToolRequest, setCadToolRequest] = useState<CadToolRequestForPreview | null>(null);
  const [activeWorkspaceMode, setActiveWorkspaceMode] = useState<WorkspaceMode>("setup");
  const [issueReportMessage, setIssueReportMessage] = useState("");
  const [issueReportCopied, setIssueReportCopied] = useState(false);
  const [imageName, setImageName] = useState("");
  const [siteName, setSiteName] = useState("");
  const [fileName, setFileName] = useState("");
  const [siteNameAuto, setSiteNameAuto] = useState(false);
  const [fileNameAuto, setFileNameAuto] = useState(false);
  const [lotWidth, setLotWidth] = useState("");
  const [lotHeight, setLotHeight] = useState("");
  const [buildingWidth, setBuildingWidth] = useState("");
  const [buildingDepth, setBuildingDepth] = useState("");
  const [buildingCount, setBuildingCount] = useState("");
  const [setback, setSetback] = useState("");
  const [parkingCount, setParkingCount] = useState("");
  const [parkingStallWidth, setParkingStallWidth] = useState("9");
  const [parkingStallDepth, setParkingStallDepth] = useState("18");
  const [parkingAisleWidth, setParkingAisleWidth] = useState("24");
  const [parkingAdaAisleWidth, setParkingAdaAisleWidth] = useState("8");
  const [parkingAdaCount, setParkingAdaCount] = useState("0");
  const [parkingCompactCount, setParkingCompactCount] = useState("0");
  const [parkingCompactWidth, setParkingCompactWidth] = useState("8");
  const [parkingAngle, setParkingAngle] = useState<"90" | "60" | "45">("90");
  const [parkingLoading, setParkingLoading] = useState<"single" | "double">("double");
  const [activeRoadwayWorkbenchTab, setActiveRoadwayWorkbenchTab] = useState<RoadwayWorkbenchTab>("alignment");
  const [activeCivil3DWorkflowTab, setActiveCivil3DWorkflowTab] = useState<Civil3DWorkflowTab>("surface");
  const [minSlopePct, setMinSlopePct] = useState("");
  const [pipeMinSlopePct, setPipeMinSlopePct] = useState("");
  const [maxParkingSlopePct, setMaxParkingSlopePct] = useState("");
  const [maxRoadGradePct, setMaxRoadGradePct] = useState("");
  const [maxAdaCrossSlopePct, setMaxAdaCrossSlopePct] = useState("");
  const [assumedTerrainSlopePct, setAssumedTerrainSlopePct] = useState("8");
  const [roads, setRoads] = useState(true);
  const [grading, setGrading] = useState(true);
  const [drainage, setDrainage] = useState(true);
  const [utilityCatalog, setUtilityCatalog] = useState<UtilityCatalogResponse | null>(null);
  const [utilityCatalogStatus, setUtilityCatalogStatus] = useState("Catalog not loaded");
  const [utilityCatalogNetworkFilter, setUtilityCatalogNetworkFilter] = useState("all");
  const [customerTemplates, setCustomerTemplates] = useState<CustomerTemplateRegistryResponse | null>(null);
  const [customerTemplateStatus, setCustomerTemplateStatus] = useState("Templates not loaded");
  const [assistedEnabled, setAssistedEnabled] = useState(false);
  const [drainageForcedInlets, setDrainageForcedInlets] = useState<
    Array<{ x: number; y: number; name?: string }>
  >([]);
  const [drainageConnectOrphans, setDrainageConnectOrphans] = useState(false);
  const [drainageAllowSlopeAdjust, setDrainageAllowSlopeAdjust] = useState(false);
  const [drainageMaxSlopeAdjust, setDrainageMaxSlopeAdjust] = useState(0.001);
  const [utilities, setUtilities] = useState(true);
  const [buildingPlacements, setBuildingPlacements] = useState<BuildingPlacement[]>([]);
  const buildingPlacementsRef = useRef<BuildingPlacement[]>([]);
  const [placementModeEnabled, setPlacementModeEnabled] = useState(false);
  const [activePlacementId, setActivePlacementId] = useState<string | null>(null);
  const [selectedObjectIds, setSelectedObjectIds] = useState<string[]>([]);
  const [objectManagerStatusMessage, setObjectManagerStatusMessage] = useState("");
  const [objectClipboard, setObjectClipboard] = useState<BuildingPlacement[]>([]);
  const [combineObjectName, setCombineObjectName] = useState("");
  const [combineObjectType, setCombineObjectType] = useState<SiteObjectType>("custom");
  const [draftBlockName, setDraftBlockName] = useState("");
  const [draftBlockLibrary, setDraftBlockLibrary] = useState<DraftBlockDefinition[]>([]);
  const [arrayRows, setArrayRows] = useState("2");
  const [arrayColumns, setArrayColumns] = useState("3");
  const [arraySpacingX, setArraySpacingX] = useState("60");
  const [arraySpacingY, setArraySpacingY] = useState("40");
  const [bulkMoveX, setBulkMoveX] = useState("25");
  const [bulkMoveY, setBulkMoveY] = useState("0");
  const [bulkMoveToX, setBulkMoveToX] = useState("0");
  const [bulkMoveToY, setBulkMoveToY] = useState("0");
  const [bulkScaleFactor, setBulkScaleFactor] = useState("1.1");
  const [bulkRotateAngle, setBulkRotateAngle] = useState("15");
  const [systemStatuses, setSystemStatuses] = useState(DEFAULT_SYSTEM_STATUS);
  const [reactiveValidation, setReactiveValidation] = useState<ReactiveValidationState>(EMPTY_REACTIVE_VALIDATION);

  useEffect(() => {
    buildingPlacementsRef.current = buildingPlacements;
  }, [buildingPlacements]);

  const [assumptions, setAssumptions] =
    useState<Assumption[]>(defaultAssumptions);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [backendResult, setBackendResult] = useState<PlanResponse | null>(null);
  const [planSheetSet, setPlanSheetSet] = useState<PlanSheetSet>(() =>
    createDefaultPlanSheetSet("Untitled Project"),
  );
  const [uploadedImagePreviewUrl, setUploadedImagePreviewUrl] = useState("");
  const [uploadedImageApiUrl, setUploadedImageApiUrl] = useState("");
  const [planPdfUploadState, setPlanPdfUploadState] = useState<"idle" | "uploading" | "uploaded" | "failed">("idle");
  const [planPdfUploadMessage, setPlanPdfUploadMessage] = useState("");
  const [selectedPlanPdfElementId, setSelectedPlanPdfElementId] = useState("");
  const [planPdfElementDraftText, setPlanPdfElementDraftText] = useState("");
  const [planPdfMoveX, setPlanPdfMoveX] = useState("");
  const [planPdfMoveY, setPlanPdfMoveY] = useState("");
  const [surveyFileName, setSurveyFileName] = useState("");
  const [surveyUploadMessage, setSurveyUploadMessage] = useState("");
  const [sourceEffectRows, setSourceEffectRows] = useState<string[]>([]);
  const [surveySlopeEstimate, setSurveySlopeEstimate] = useState<SurveySlopeResponse | null>(null);
  const [, setSurveyPoints] = useState<number[][]>([]);
  const [, setSurveyDiagnostics] = useState<{
    fileType?: string;
    parseSuccess?: boolean;
    pointCount?: number;
    contourCount?: number;
    recognizedColumns?: { x?: string; y?: string; z?: string };
    invalidRows?: number;
    bounds?: { min_x?: number; min_y?: number; max_x?: number; max_y?: number };
    elevationRange?: { min?: number; max?: number };
    warnings?: string[];
  } | null>(null);
  const [surveyPreviewPoints, setSurveyPreviewPoints] = useState<Array<{ x: number; y: number; z?: number }>>([]);
  const [useSurveyForGrading, setUseSurveyForGrading] = useState(true);
  const [detectedPlacements, setDetectedPlacements] = useState<BuildingPlacement[]>([]);
  const [detectionScaleFeet, setDetectionScaleFeet] = useState("");
  const [detectionScalePixels, setDetectionScalePixels] = useState("");
  const [detectionScaleFtPerPx, setDetectionScaleFtPerPx] = useState<number | null>(null);
  const [detectionScaleSource, setDetectionScaleSource] = useState<"mapbox" | "manual" | "approximate">("approximate");
  const [siteScaleLocked, setSiteScaleLocked] = useState(false);
  const [drainageSourceOverride, setDrainageSourceOverride] = useState<"civora" | "user">(
    "civora",
  );
  const [siteRotationDeg, setSiteRotationDeg] = useState(0);
  const [siteRotationInput, setSiteRotationInput] = useState("0");
  const [showSiteBounds, setShowSiteBounds] = useState(false);
  const [fitToSiteRequest, setFitToSiteRequest] = useState(0);
  const [siteDrawRequest, setSiteDrawRequest] = useState(0);
  const [mapCenterRequest, setMapCenterRequest] = useState(0);
  const [alignToRoadRequest, setAlignToRoadRequest] = useState(0);
  const debugPreview = useMemo(() => {
    if (!clientMounted || typeof window === "undefined") return false;
    return window.location.search.includes("debugPreview=1");
  }, [clientMounted]);
  const mapDebugOverlay = useMemo(() => {
    if (!clientMounted || typeof window === "undefined") return false;
    return window.location.search.includes("mapDebug=1");
  }, [clientMounted]);
  const debugNoTerrain = useMemo(() => {
    if (!clientMounted || typeof window === "undefined") return false;
    return process.env.NODE_ENV !== "production" && window.location.search.includes("debugNoTerrain=1");
  }, [clientMounted]);
  const rotationSaveTimeoutRef = useRef<number | null>(null);
  const scaleSaveTimeoutRef = useRef<number | null>(null);
  const [focusDetectedId, setFocusDetectedId] = useState<string | null>(null);
  const [focusObjectId, setFocusObjectId] = useState<string | null>(null);
  const [analysisPaths, setAnalysisPaths] = useState<DashboardAccessAnalysisPath[]>([]);
  const [analysisIssues, setAnalysisIssues] = useState<DashboardAccessAnalysisIssue[]>([]);
  const [analysisSelectedIssueId, setAnalysisSelectedIssueId] = useState<string | null>(null);
  const [analysisFocusLocked, setAnalysisFocusLocked] = useState(false);
  const [, setAnalysisEmptyReason] = useState<string | null>(null);
  const [externalRectUndo, setExternalRectUndo] = useState<{
    id: string;
    snapshot: BuildingPlacement;
    action: "update" | "delete" | "add";
    ts: number;
  } | null>(null);
  const [detectionConfidenceFilter] = useState<"high" | "medium" | "all">("all");
  const [mapSnapshotPath, setMapSnapshotPath] = useState("");
  const [mapAnalysis, setMapAnalysis] = useState<MapAnalysis | null>(null);
  const [siteAddress, setSiteAddress] = useState("");
  const [siteSelectionMode, setSiteSelectionMode] = useState(false);
  const [detectionChoices, setDetectionChoices] = useState({
    roads: true,
    buildings: true,
    parking: true,
    grading: true,
  });
  const [addressSuggestions, setAddressSuggestions] = useState<AddressSuggestion[]>([]);
  const [selectedAddressSuggestion, setSelectedAddressSuggestion] = useState<AddressSuggestion | null>(null);
  const [onlineDiscoveryBusy, setOnlineDiscoveryBusy] = useState(false);
  const [autoExistingConditionsStatus, setAutoExistingConditionsStatus] = useState<AutoExistingConditionsUiStatus>({
    status: "waiting",
    message: "Apply an address and lock the site. Civora will then check available source context inside the boundary.",
    candidateCount: 0,
    missing: [],
  });
  const [generateFlowSummary, setGenerateFlowSummary] = useState<GenerateFlowSummary | null>(null);
  const [reviewPackageFlowSummary, setReviewPackageFlowSummary] = useState<ReviewPackageFlowSummary | null>(null);
  const [exportActionMessage, setExportActionMessage] = useState("");
  const addressSuggestTimeoutRef = useRef<number | null>(null);
  const [imageUploadState, setImageUploadState] = useState<"idle" | "uploading" | "uploaded" | "detecting" | "failed">("idle");
  const [imageUploadNote, setImageUploadNote] = useState<string | null>(null);
  const autoExistingRunKeyRef = useRef("");
  const [pendingClarification, setPendingClarification] = useState<{
    action: string;
    payload?: Record<string, unknown>;
    question: string;
  } | null>(null);
  const [planPreviewUrl, setPlanPreviewUrl] = useState("");
  const [planPreviewProjectId, setPlanPreviewProjectId] = useState<string | null>(null);
  const [planPreviewSummary, setPlanPreviewSummary] =
    useState<PreviewResponse["summary"] | null>(null);
  const [planPreviewAnnotations, setPlanPreviewAnnotations] =
    useState<PreviewResponse["preview_annotations"] | null>(null);
  const [previewInteraction, setPreviewInteraction] = useState<"static" | "edit">("static");
  const [previewLabelDensity, setPreviewLabelDensity] = useState<"low" | "standard" | "high">("standard");
  const [layerManagerOpen, setLayerManagerOpen] = useState(false);
  const [previewHeightPx, setPreviewHeightPx] = useState(900);
  const [objectOutlineColor] = useState("#1f2937");
  const [previewRefreshing, setPreviewRefreshing] = useState(false);
  const [previewRefreshNote, setPreviewRefreshNote] = useState<string | null>(null);
  const [approvalInFlight, setApprovalInFlight] = useState(false);
  const [approvalPhaseLabel, setApprovalPhaseLabel] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approvalPendingJobId, setApprovalPendingJobId] = useState<string | null>(null);
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [showCalculations, setShowCalculations] = useState(false);
  const [previewLayers, setPreviewLayers] = useState<PreviewLayerVisibility>({
    buildings: true,
    roads: true,
    grading: true,
    drainage: true,
    utilities: true,
    structures: true,
    lots: false,
  });
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const [previewFullscreenOpen, setPreviewFullscreenOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [currentProject, setCurrentProject] = useState<ProjectRecord | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [selectedJobId, setSelectedJobId] = useState("");
  const [jobToasts, setJobToasts] = useState<WorkspaceToast[]>([]);
  const [statusMessage, setStatusMessage] = useState("");
  const [projectStatusSummary, setProjectStatusSummary] =
    useState<ProjectStatusSummary>(DEFAULT_PROJECT_STATUS);
  const [moveEditFeedback, setMoveEditFeedback] = useState("");
  const [workspaceRestoreState, setWorkspaceRestoreState] = useState<"idle" | "restored" | "failed">("idle");
  const [projectDrawerNotice, setProjectDrawerNotice] = useState("");
  const [jobsPanelStatusMessage, setJobsPanelStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activePlanTool, setActivePlanTool] = useState<PlanToolMode>("run");
  const [shortcutsOverlayOpen, setShortcutsOverlayOpen] = useState(false);
  const {
    clearDraftUndoAction,
    lastDraftAction,
    lastDraftActionRef,
    recentChanges,
    recentChangesOpen,
    recordDraftRedoAction,
    recordDraftUndoAction,
    recordRecentChange,
    redoDraftAction,
    redoDraftActionRef,
    setRecentChangesOpen,
  } = useDashboardDraftHistoryState();
  const [jobClockMs, setJobClockMs] = useState(() => Date.now());
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const chatPromptInputRef = useRef<HTMLTextAreaElement | null>(null);
  const commandInputRef = useRef<HTMLTextAreaElement | null>(null);
  const siteAddressInputRef = useRef<HTMLInputElement | null>(null);
  const mapSnapshotInputRef = useRef<HTMLInputElement | null>(null);
  const planPdfInputRef = useRef<HTMLInputElement | null>(null);
  const surveyInputRef = useRef<HTMLInputElement | null>(null);
  const runSubmissionRef = useRef(false);
  const directRunAbortRef = useRef<AbortController | null>(null);
  const draftProjectPromiseRef = useRef<Promise<ProjectRecord | null> | null>(null);
  const ensureProjectDraftRef = useRef<() => Promise<string | null>>(() => Promise.resolve(null));
  const loadJobRef = useRef<((id: string) => Promise<void> | void) | null>(null);
  const loadProjectResultInBackgroundRef = useRef<((project: ProjectRecord) => void) | null>(null);
  const resetWorkspaceStateRef = useRef<(() => void) | null>(null);
  const setupWizardStateRef = useRef<unknown>(null);
  const saveProjectRef = useRef<
    (options?: {
      silent?: boolean;
      projectIdOverride?: string | null;
      nameOverride?: string;
      fileNameOverride?: string;
      projectInputOverride?: ProjectInput;
      latestResultOverride?: PlanResponse;
      autoNamedOverride?: boolean;
      autoFileNamedOverride?: boolean;
    }) => Promise<ProjectRecord | null>
  >(() => Promise.resolve(null));
  const resolvedProjectIdRef = useRef("");
  const projectLoadRequestRef = useRef(0);
  const projectResultLoadRequestRef = useRef(0);
  const activeJobProjectSyncRef = useRef("");
  const lastJobStatusRef = useRef<Record<string, string>>({});
  const lastJobPhaseSignatureRef = useRef<Record<string, string>>({});
  const lastStaleJobWarningRef = useRef<Record<string, boolean>>({});
  const previewRefreshIntentRef = useRef<{ reason: string; track?: boolean } | null>(null);
  const previewAutoRefreshTimeoutRef = useRef<number | null>(null);
  const lastProjectResultRefreshRef = useRef<Record<string, number>>({});
  const lastJobPartialResultRefreshRef = useRef<Record<string, number>>({});
  const handleGenerateSystemRef = useRef<((target: SystemGenerationTarget, options?: { slopeEstimateOverride?: SurveySlopeResponse | null }) => Promise<void>) | null>(null);
  const chatMessagesRef = useRef<ChatMessage[]>([createWelcomeMessage()]);
  const suppressProjectAutoLoadRef = useRef(false);
  const restoredActiveProjectRef = useRef(false);
  const chatAutosaveTimeoutRef = useRef<number | null>(null);
  const autosaveSuspendRef = useRef(false);
  const demoWorkspaceSeededRef = useRef(false);
  const currentPhaseLabelRef = useRef<string>("");
  const previewRecoveryKeyRef = useRef("");
  const lastSiteInputProjectRef = useRef("");
  const controlAutosaveTimeoutRef = useRef<number | null>(null);
  const lastAppliedSiteRef = useRef<{ w: number; h: number; lat?: number; lng?: number } | null>(null);
  const lastViewportSyncRef = useRef<{ w: number; h: number } | null>(null);
  const scrollToDrawingSurface = useCallback(() => {
    if (typeof window === "undefined") return;
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const surface = document.querySelector('[data-testid="preview-drawing-surface"]');
        surface?.scrollIntoView({ behavior: "auto", block: "center", inline: "nearest" });
      });
    });
  }, []);
  const applyingSiteRef = useRef(false);

  const {
    projects,
    setProjects,
    refreshProjects,
    upsertProjectSummary,
    removeProjectSummary,
  } = useProjectsState();

  const {
    jobs,
    setJobs,
    refreshJobs,
  } = useJobsState({ activeJobId });

  const {
    token,
    user,
    authMode,
    authStatus,
    authName,
    authEmail,
    authPassword,
    showPassword,
    authError,
    authLoading,
    authStatusError,
    setAuthMode,
    setAuthName,
    setAuthEmail,
    setAuthPassword,
    setAuthError,
    setShowPassword,
    handleAuth,
    handleLogout,
  } = useAuthState({
    onRefreshProjects: refreshProjects,
    onRefreshJobs: refreshJobs,
    onStatusMessage: setStatusMessage,
    skipInitialAuthStatus: effectiveDemoWorkspaceEnabled,
    skipStoredAuthRestore: effectiveDemoWorkspaceEnabled,
    shouldSkipStoredAuthRestore: () =>
      forceDemoWorkspace ||
      routeDemoWorkspaceEnabled ||
      demoWorkspaceEnabled ||
      isDemoWorkspaceQuery(),
    onLogoutCleanup: () => {
      setProjects([]);
      setJobs([]);
      setCurrentProject(null);
      setProjectId("");
    },
  });
  const effectiveUser: UserRecord | null =
    user ??
    (effectiveDemoWorkspaceEnabled
      ? {
          user_id: "demo-user",
          name: "Demo Reviewer",
          email: "demo@civora.local",
        }
      : null);

  useEffect(() => {
    setClientMounted(true);
  }, []);

  useEffect(() => {
    setDemoWorkspaceEnabled(forceDemoWorkspace || isDemoWorkspaceQuery());
  }, [clientMounted, forceDemoWorkspace, routeDemoWorkspaceEnabled]);

  useEffect(() => {
    if (!token) {
      setUtilityCatalog(null);
      setUtilityCatalogStatus("Sign in to load utility catalogs");
      setCustomerTemplates(null);
      setCustomerTemplateStatus("Sign in to load templates");
      return;
    }
    let cancelled = false;
    setUtilityCatalogStatus("Loading utility catalogs");
    setCustomerTemplateStatus("Loading templates");
    void getJson<UtilityCatalogResponse>("/api/utility-catalogs", { token })
      .then((data) => {
        if (cancelled) return;
        setUtilityCatalog(data);
        const reviewCount = Number(data.summary?.review_required_count ?? 0);
        setUtilityCatalogStatus(
          reviewCount > 0
            ? `${reviewCount} catalog entries need workspace review`
            : "Catalog entries loaded",
        );
      })
      .catch((error) => {
        if (cancelled) return;
        setUtilityCatalog(null);
        setUtilityCatalogStatus(error instanceof Error ? error.message : "Catalog load failed");
      });
    void getJson<CustomerTemplateRegistryResponse>("/api/customer-templates", { token })
      .then((data) => {
        if (cancelled) return;
        setCustomerTemplates(data);
        const active = data.behavior?.active_template;
        const blockerCount = Number(data.behavior?.blockers?.length ?? 0);
        setCustomerTemplateStatus(
          active
            ? `${active.name || "Company template"} active${blockerCount ? `, ${blockerCount} item(s) need review` : ""}`
            : "No company template active",
        );
      })
      .catch((error) => {
        if (cancelled) return;
        setCustomerTemplates(null);
        setCustomerTemplateStatus(error instanceof Error ? error.message : "Template load failed");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const disciplineToggles: DisciplineToggle[] = [
    {
      label: "Roads",
      checked: roads,
      setter: setRoads,
      desc: "Corridor / access layout",
    },
    {
      label: "Grading",
      checked: grading,
      setter: setGrading,
      desc: "Pads, slopes, tie-ins",
    },
    {
      label: "Drainage",
      checked: drainage,
      setter: setDrainage,
      desc: "Inlets, ponds, routing",
    },
    {
      label: "Utilities",
      checked: utilities,
      setter: setUtilities,
      desc: "Water, sanitary, utility",
    },
  ];

  const { buildManualFields, payloadPreview } = useDashboardPayloadPreviewState({
    assistedEnabled,
    buildingPlacements,
    buildingCount,
    buildingDepth,
    buildingWidth,
    chatMessages,
    currentProject,
    drainageAllowSlopeAdjust,
    drainageConnectOrphans,
    drainageForcedInlets,
    drainageMaxSlopeAdjust,
    drainage,
    fileName,
    grading,
    imageName,
    lotHeight,
    lotWidth,
    maxAdaCrossSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    minSlopePct,
    parkingCount,
    pipeMinSlopePct,
    projectId,
    projectType,
    prompt,
    reactiveEditPolicyPreference: REACTIVE_EDIT_POLICY_PREFERENCE,
    roads,
    setback,
    siteName,
    surveySlopeEstimate,
    systemStatuses,
    units,
    utilities,
  });

  const artifactPayload = useMemo(
    () => buildDashboardArtifactPayload({ backendResult, projectId, currentProject, fileName, siteName }),
    [backendResult, currentProject, fileName, projectId, siteName],
  );

  const workflowState = useMemo(
    () =>
      buildDashboardWorkflowState({
        currentProject,
        jobs,
        selectedRunId,
        activeJobId,
        selectedJobId,
        projectId,
        jobClockMs,
        busy,
        activePlanTool,
        statusMessage,
      }),
    [activeJobId, activePlanTool, busy, currentProject, jobClockMs, jobs, projectId, selectedJobId, selectedRunId, statusMessage],
  );
  const { workflowRuns, selectedRun, workflowReviewDashboard, activeJob, jobHistory, jobStatusCounts, artifactHistory, currentProjectActiveJob, visibleActiveJob, visibleActiveJobStale, chatBlockingActiveJob, selectedJob, selectedJobStale, thinkingState } = workflowState;

  const chatSummary = useMemo(() => {
    const last = chatMessages[chatMessages.length - 1];
    if (!last) return "Ask Civora about your site or place objects.";
    const roleLabel = last.role === "user" ? "You" : "Civora";
    const snippet = String(last.content || "").trim().slice(0, 120);
    return snippet ? `${roleLabel}: ${snippet}${snippet.length >= 120 ? "…" : ""}` : "Chat is ready.";
  }, [chatMessages]);
  const approvalStatus = useMemo<{ state: ApprovalState; label: string | null }>(() => {
    if (approvalInFlight) {
      return { state: "approving", label: approvalPhaseLabel };
    }
    if (
      approvalPendingJobId &&
      visibleActiveJob?.job_id === approvalPendingJobId &&
      String(visibleActiveJob?.status || "").toLowerCase() !== "awaiting_approval"
    ) {
      return { state: "starting", label: approvalPhaseLabel };
    }
    return { state: "idle", label: approvalPhaseLabel };
  }, [approvalInFlight, approvalPendingJobId, approvalPhaseLabel, visibleActiveJob?.job_id, visibleActiveJob?.status]);

  useEffect(() => {
    if (!approvalPendingJobId) return;
    if (visibleActiveJob?.job_id !== approvalPendingJobId) {
      setApprovalInFlight(false);
      setApprovalPendingJobId(null);
      setApprovalPhaseLabel(null);
      return;
    }
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (["awaiting_approval", "completed", "failed", "cancelled"].includes(status)) {
      setApprovalInFlight(false);
      setApprovalPendingJobId(null);
      setApprovalPhaseLabel(null);
    }
  }, [approvalPendingJobId, visibleActiveJob?.job_id, visibleActiveJob?.status]);

  useEffect(() => {
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") {
      setApprovalError(null);
    }
  }, [visibleActiveJob?.status]);
  const currentPlanMeta = useMemo<PlanMeta>(() => backendResult?.final_plan?.meta ?? {}, [backendResult]);
  const {
    planPdfAnalysis,
    planPdfBlockers,
    planPdfChangedElements,
    planPdfChangedReport,
    planPdfClassificationPreviewRows,
    planPdfElements,
    planPdfExtractionSummaryRows,
    planPdfFirstPage,
    planPdfSourceUrl,
    planPdfUnreadableItems,
    selectedPlanPdfElement,
  } = useDashboardPlanPdfDerivedState({
    currentPlanMeta,
    selectedPlanPdfElementId,
    setPlanPdfElementDraftText,
    setPlanPdfMoveX,
    setPlanPdfMoveY,
    setSelectedPlanPdfElementId,
    token,
  });
  const siteInputs = (currentProject?.project_input?.meta?.site_inputs ?? {}) as SiteInputs;
  const engineDepthDashboard = useMemo<EngineDepthDashboard | null>(() => {
    const direct = currentPlanMeta.engine_depth_dashboard_v1;
    if (direct?.version) return direct;
    const auditReport = currentPlanMeta.engine_depth_audit_report_v1;
    if (auditReport?.engine_depth_dashboard_v1?.version) return auditReport.engine_depth_dashboard_v1;
    const audit = currentPlanMeta.engine_depth_audit;
    if (audit?.engine_depth_dashboard_v1?.version) return audit.engine_depth_dashboard_v1;
    return null;
  }, [currentPlanMeta, siteInputs]);
  const currentPlanMetaRecord = currentPlanMeta as Record<string, unknown>;
  const { appliedAddressLabel, hasAppliedAddress, hasLocationEvidence, hasVerifiedSurveyControl, hasAssumedTerrainSlope, hasTerrainSource, hasStandardsEvidence, pendingAddressEdit, localAddressLocked, addressNeedsApply } = buildDashboardSetupTruth({
    siteInputs,
    siteAddress,
    siteScaleLocked,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
    surveyFileName,
    surveyPreviewPointCount: surveyPreviewPoints.length,
    surveySlopeEstimate,
    debugNoTerrain,
    useSurveyForGrading,
    standardsEvidenceValues: [minSlopePct, pipeMinSlopePct, maxParkingSlopePct, maxRoadGradePct, maxAdaCrossSlopePct, currentPlanMetaRecord.standards_package, currentPlanMetaRecord.standards_source_registry, currentPlanMetaRecord.standards_acceptance_report],
  });
  const hasSourceBackedSurfaceEvidence = useMemo(() => {
    const normalizedSurveyFile = String(surveyFileName || "").trim();
    const sourceBackedFile =
      useSurveyForGrading &&
      /\.(csv|txt|nez|pnezd|dxf|xml|landxml|las|laz|tif|tiff|geotiff)$/i.test(normalizedSurveyFile);
    const slopeFromSourcePoints =
      Boolean(surveySlopeEstimate?.slope_percent) && Number(surveySlopeEstimate?.point_count ?? 0) > 0;
    return surveyPreviewPoints.length > 0 || sourceBackedFile || slopeFromSourcePoints;
  }, [surveyFileName, surveyPreviewPoints.length, surveySlopeEstimate?.point_count, surveySlopeEstimate?.slope_percent, useSurveyForGrading]);
  const smartFixBlockedReasons = useMemo(() => buildSmartFixBlockedReasons(currentPlanMeta), [currentPlanMeta]);
  const smartFixRecommendations = useMemo(
    () => buildSmartFixRecommendations(currentPlanMeta, smartFixBlockedReasons),
    [currentPlanMeta, smartFixBlockedReasons],
  );
  const smartFixItems = smartFixRecommendations.recommendations ?? [];
  const topSmartFix = smartFixRecommendations.next_best_recommendation ?? smartFixItems[0];
  const candidateReviewInbox = useMemo<CandidateReviewInbox>(
    () => buildCandidateReviewInbox(siteInputs, currentPlanMeta),
    [currentPlanMeta, siteInputs],
  );
  const designAlternatives = useMemo<DesignAlternativesV1>(
    () => buildDesignAlternatives(currentPlanMeta),
    [currentPlanMeta],
  );
  const designAlternativeSummary = useMemo(() => buildDesignAlternativeSummary(designAlternatives), [designAlternatives]);
  const designAlternativeItems = designAlternativeSummary.items;
  const topDesignAlternative = designAlternativeSummary.top;
  const selectedDesignAlternativeId = designAlternativeSummary.selectedId;
  const designAlternativeQuantityAvailable = designAlternativeSummary.quantityAvailable;
  const reviewIssueTracker = useMemo<ReviewIssueTrackerV1>(
    () => buildReviewIssueTracker(currentPlanMeta, issues, analysisIssues),
    [analysisIssues, currentPlanMeta, issues],
  );
  const reviewIssueCollections = useMemo(() => buildReviewIssueCollections(reviewIssueTracker), [reviewIssueTracker]);
  const reviewIssueItems = reviewIssueCollections.items;
  const openReviewIssueItems = reviewIssueCollections.openItems;
  const drainageReviewIssueItems = reviewIssueCollections.drainageItems;
  const candidateReviewItems = candidateReviewInbox.candidates ?? [];
  const candidateReviewCounts = candidateReviewInbox.counts ?? { accepted: 0, rejected: 0, pending: 0 };
  const sourceConfidenceMap = useMemo<SourceConfidenceMap>(
    () =>
      buildSourceConfidenceMap({
        currentPlanMeta,
        candidateReviewItems,
        buildingPlacements,
        hasVerifiedSurveyControl,
      }),
    [buildingPlacements, candidateReviewItems, currentPlanMeta, hasVerifiedSurveyControl],
  );
  const sourceConfidenceView = useMemo(
    () =>
      buildDashboardSourceConfidenceView({
        sourceConfidenceMap,
        siteInputs,
        hasTerrainSource,
        mapAnalysisSuccess: Boolean(mapAnalysis?.success),
      }),
    [hasTerrainSource, mapAnalysis?.success, siteInputs, sourceConfidenceMap],
  );
  const sourceConfidenceEntries = sourceConfidenceView.entries;
  const sourceConfidenceSummary = sourceConfidenceView.summary;
  const sourceConfidenceRows = sourceConfidenceView.rows;
  const sourceHubLinks = DASHBOARD_SOURCE_HUB_LINKS;
  const sourceHubMetrics = sourceConfidenceView.hubMetrics;
  const sourceConfidenceByObjectId = sourceConfidenceView.byObjectId;
  const cadEntityPreview = useMemo<CadEntityPreview>(
    () => buildCadEntityPreview(currentPlanMeta, sourceConfidenceByObjectId),
    [currentPlanMeta, sourceConfidenceByObjectId],
  );
  const { handleCandidateReviewDecision, handleDesignAlternativesAction } =
    useDashboardReviewWorkflowActions({
      currentProjectId: currentProject?.project_id,
      designAlternativeCount: designAlternativeItems.length,
      projectId,
      setActiveSidePanel,
      setActiveWorkspaceMode,
      setBackendResult,
      setBuildingPlacements,
      setCurrentProject,
      setStatusMessage,
      token,
    });
  const reactiveChangedSystems = useMemo<EngineeringSystemKey[]>(
    () => buildDashboardReactiveChangedSystems(systemStatuses),
    [systemStatuses],
  );
  const reactiveChangedTargets = useMemo(
    () => buildDashboardReactiveChangedTargets(reactiveChangedSystems),
    [reactiveChangedSystems],
  );
  const reactiveRerunSummary = useMemo(
    () => buildDashboardReactiveRerunSummary(currentPlanMeta),
    [currentPlanMeta],
  );
  const reactiveAffectedRunTarget = useMemo<SystemGenerationTarget | null>(() => {
    return resolveDashboardReactiveAffectedRunTarget({ currentPlanMeta, reactiveChangedSystems });
  }, [currentPlanMeta.reactive_update_report?.impacted_stages, reactiveChangedSystems]);

  useEffect(() => {
    return runDashboardReactiveValidation({
      backendFinalPlanPresent: Boolean(backendResult?.final_plan),
      reactiveChangedSystems,
      reactiveChangedTargets,
      setReactiveValidation,
    });
  }, [backendResult?.final_plan, reactiveChangedSystems, reactiveChangedTargets]);
  const [debugGradingFixtureLoaded, setDebugGradingFixtureLoaded] = useState(false);

  const {
    basinSize,
    calculationOverlayStats,
    costEstimate,
    currentExplanation,
    currentManualFailures,
    currentTruthAudit,
    cutFillNet,
    drainageLowPoints,
    drainageSummary,
    flowCfs,
    gradingBlocker,
    gradingResultSummary,
    gradingSummary,
    managerMetrics,
    maxSlope,
    measurementOverlayStats,
    minSlope,
    quantityExplain,
    quantityRows,
    roadwayWorkbenchData,
    selectedIssueLabel,
    stormHydrologyReview,
    suggestedImproveGoal,
    totalPipeLength,
    waterFireFlowReview,
  } = useDashboardEngineeringReviewState({
    currentPlanMeta,
    issues,
    planPreviewAnnotations,
    selectedIssueId,
    smartFixItems,
  });

  const updateProjectStatus = useCallback(
    (summary: Omit<ProjectStatusSummary, "updatedAt">) => {
      const nextSummary = { ...summary, updatedAt: Date.now() };
      setProjectStatusSummary(nextSummary);
      setStatusMessage(formatProjectStatusText(nextSummary));
    },
    [],
  );
  const {
    previewMode,
    setPreviewMode,
    previewQuality,
    setPreviewQuality,
    handleSetPreviewMode,
    handleSetPreviewQuality,
  } = useDashboardPreviewModeState({ updateProjectStatus });

  const pushRecoveryMessage = useCallback(
    (message: string) => {
      setObjectManagerStatusMessage(message);
      setStatusMessage(message);
    },
    [],
  );

  const applyBackendResult = (data: PlanResponse) => {
    setBackendResult(data);
    setAssumptions(buildDashboardAssumptionsFromPlanResult(data));
    setIssues(buildDashboardIssuesFromPlanResult(data));
    setSystemStatuses((prev) => applyDashboardReactiveSystemStatusFromPlanResult(data, prev));
  };

  const appendChatMessage = (
    role: ChatMessage["role"],
    content: string,
    kind: ChatMessage["kind"] = "message",
    feedback?: ChatMessage["feedback"],
  ) => {
    setChatMessages((current) => {
      const phaseTag =
        role === "assistant" || role === "system"
          ? currentPhaseLabelRef.current || undefined
          : undefined;
      const next = [
        ...current,
        createChatMessage(role, content, kind, feedback, phaseTag),
      ];
      chatMessagesRef.current = next;
      return next;
    });
  };


  const setMessageFeedback = async (
    messageId: string,
    feedback: ChatMessage["feedback"],
  ) => {
    await runDashboardSetMessageFeedback({
      buildChatDecisionContext,
      chatMessagesRef,
      currentProjectId: currentProject?.project_id,
      feedback,
      messageId,
      setChatMessages,
      token,
    });
  };

  useEffect(() => {
    return () => {
      if (chatAutosaveTimeoutRef.current !== null) {
        window.clearTimeout(chatAutosaveTimeoutRef.current);
      }
    };
  }, []);


  useChatPersistence({
    chatMessages,
    setChatMessages,
    chatMessagesRef,
    chatScrollRef,
    projectId,
    currentProjectId: currentProject?.project_id,
  });

  useEffect(() => {
    if (demoWorkspaceSeededRef.current) return;
    if (!forceDemoWorkspace && !seededDemoWorkspaceEnabled) return;
    const debugEmptyLayout =
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("chat226EmptyLayout") === "1";
    const debugEmptyObjects =
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("chat230EmptyObjects") === "1";
    const { demoPlacements, demoResult, demoProject, demoThread, systemStatuses: demoSystemStatuses } =
      buildDashboardDemoWorkspaceSeed({ debugEmptyLayout, debugEmptyObjects });
    demoWorkspaceSeededRef.current = true;
    suppressProjectAutoLoadRef.current = true;
    setProjects([demoProject]);
    setCurrentProject(demoProject);
    setProjectId(demoProject.project_id);
    setSiteName("Pinecrest Mixed-Use");
    setFileName("pinecrest-demo-ui");
    setSiteNameAuto(false);
    setFileNameAuto(false);
    setLotWidth("760");
    setLotHeight("520");
    setParkingCount("116");
    setBuildingWidth("110");
    setBuildingDepth("58");
    setBuildingCount("3");
    setProjectType("mixed_use");
    setSiteAddress("Pinecrest Mixed-Use Demo Site");
    setSiteScaleLocked(true);
    setUseSurveyForGrading(true);
    setBuildingPlacements(demoPlacements);
    setPlacementModeEnabled(false);
    setActivePlacementId(null);
    setPreviewQuality("standard");
    setPreviewMode("2d");
    setPreviewInteraction("static");
    setPreviewHeightPx(720);
    setSystemStatuses(demoSystemStatuses);
    applyBackendResult(demoResult);
    setChatMessages(demoThread);
    chatMessagesRef.current = demoThread;
    setStatusMessage("Demo workspace loaded for UI QA.");
  }, [clientMounted, forceDemoWorkspace, routeDemoWorkspaceEnabled, seededDemoWorkspaceEnabled]);

  const applyProjectInput = (projectInput: ProjectInput) => {
    runDashboardApplyProjectInput({
      chatMessagesRef,
      projectInput,
      setActivePlacementId,
      setAssumedTerrainSlopePct,
      setBuildingCount,
      setBuildingDepth,
      setBuildingPlacements,
      setBuildingWidth,
      setChatMessages,
      setDrainage,
      setDrainageAllowSlopeAdjust,
      setDrainageConnectOrphans,
      setDrainageForcedInlets,
      setDrainageMaxSlopeAdjust,
      setFileName,
      setFileNameAuto,
      setGrading,
      setImageName,
      setLotHeight,
      setLotWidth,
      setMaxAdaCrossSlopePct,
      setMaxParkingSlopePct,
      setMaxRoadGradePct,
      setMinSlopePct,
      setParkingCount,
      setPipeMinSlopePct,
      setPlacementModeEnabled,
      setProjectType,
      setPrompt,
      setRoads,
      setSetback,
      setSiteName,
      setSiteNameAuto,
      setSurveySlopeEstimate,
      setSystemStatuses,
      setUnits,
      setUploadedImageApiUrl,
      setUploadedImagePreviewUrl,
      setUseSurveyForGrading,
      setUtilities,
      siteInputs,
      token,
    });
  };

  const {
    computeParkingFootprint,
    ensureSiteBoundary,
    hasSiteBoundary,
    resolveDefaultBuildingDims,
    resolveLotBounds,
    resolveParkingParams,
  } = useDashboardSiteGeometryActions({
    buildingDepth,
    buildingPlacements,
    buildingWidth,
    currentProject,
    lotHeight,
    lotWidth,
    setBuildingPlacements,
    setLotHeight,
    setLotWidth,
    setStatusMessage,
  });

  useEffect(() => {
    const site = buildingPlacements.find((item) => item.type === "site");
    if (!site) return;
    const nextWidth = String(site.w ?? "");
    const nextHeight = String(site.d ?? "");
    if (nextWidth && lotWidth !== nextWidth) {
      setLotWidth(nextWidth);
    }
    if (nextHeight && lotHeight !== nextHeight) {
      setLotHeight(nextHeight);
    }
  }, [buildingPlacements, lotHeight, lotWidth]);

  useEffect(() => {
    const site = buildingPlacements.find((item) => item.type === "site");
    if (!site) return;
    if (siteScaleLocked && !site.locked) {
      setBuildingPlacements((prev) =>
        prev.map((item) =>
          item.type === "site"
            ? {
                ...item,
                locked: true,
                capabilities: {
                  ...item.capabilities,
                  movable: false,
                  resizable: false,
                  rotatable: false,
                },
              }
            : item,
        ),
      );
    }
  }, [buildingPlacements, siteScaleLocked]);

  useEffect(() => {
    const hasSite = buildingPlacements.some((item) => item.type === "site");
    if (!hasSite) return;
    setShowSiteBounds(!siteScaleLocked);
  }, [buildingPlacements, siteScaleLocked]);

  const placedObjectCount = useMemo(
    () =>
      buildingPlacements.filter(
        (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
      ).length,
    [buildingPlacements],
  );

  const debugLog = useCallback(
    (label: string, payload?: Record<string, unknown>) => {
      if (!debugPreview || process.env.NODE_ENV === "production") return;
      const snapshot = {
        projectId: projectId || currentProject?.project_id || "",
        canonicalCount: buildingPlacements.length,
        placedCount: placedObjectCount,
        previewImageActive: Boolean(planPreviewUrl),
        placementMode: placementModeEnabled || Boolean(activePlacementId),
      };
      console.debug(`[debug-preview] ${label}`, { ...snapshot, ...(payload ?? {}) });
    },
    [
      activePlacementId,
      buildingPlacements.length,
      currentProject?.project_id,
      debugPreview,
      placedObjectCount,
      placementModeEnabled,
      planPreviewUrl,
      projectId,
    ],
  );

  useEffect(() => {
    if (!activePlacementId) return;
    const exists = buildingPlacements.some((item) => item.id === activePlacementId);
    if (!exists) {
      debugLog("clear-missing-selected", { id: activePlacementId });
      setActivePlacementId(null);
      setPlacementModeEnabled(false);
    }
  }, [activePlacementId, buildingPlacements, debugLog]);

  useEffect(() => {
    if (!focusObjectId) return;
    const exists = buildingPlacements.some((item) => item.id === focusObjectId);
    if (!exists) {
      debugLog("clear-missing-focus", { id: focusObjectId });
      setFocusObjectId(null);
    }
  }, [buildingPlacements, debugLog, focusObjectId]);

  useEffect(() => {
    setSelectedObjectIds((prev) => {
      const validIds = new Set(buildingPlacements.map((item) => item.id));
      const next = prev.filter((id) => validIds.has(id));
      return next.length === prev.length ? prev : next;
    });
  }, [buildingPlacements]);

  useEffect(() => {
    if (!debugPreview || process.env.NODE_ENV === "production") return;
    if (placedObjectCount > buildingPlacements.length) {
      console.warn("[debug-preview] placed-count-exceeds-canonical", {
        placedObjectCount,
        canonicalCount: buildingPlacements.length,
      });
    }
  }, [buildingPlacements.length, debugPreview, placedObjectCount]);

  const currentGenerateLayoutContext = useMemo(
    () => buildGenerateLayoutContext(buildingPlacements),
    [buildingPlacements],
  );

  const markSystemsStale = useCallback((systems?: EngineeringSystemKey[]) => {
    const targets = systems?.length
      ? Array.from(new Set(systems))
      : (["roads", "parking", "grading", "drainage", "utilities"] as EngineeringSystemKey[]);
    setSystemStatuses((prev) => ({
      roads: targets.includes("roads") && prev.roads !== "not_generated" ? "stale" : prev.roads,
      parking: targets.includes("parking") && prev.parking !== "not_generated" ? "stale" : prev.parking,
      grading: targets.includes("grading") && prev.grading !== "not_generated" ? "stale" : prev.grading,
      drainage: targets.includes("drainage") && prev.drainage !== "not_generated" ? "stale" : prev.drainage,
      utilities: targets.includes("utilities") && prev.utilities !== "not_generated" ? "stale" : prev.utilities,
    }));
  }, []);


  const formatObjectLabel = useCallback(
    (type: SiteObjectType, count: number) => {
      const base = SITE_OBJECT_CATALOG[type]?.label ?? "Object";
      return type === "site" ? base : `${base} ${count}`;
    },
    [],
  );

  const clearGeneratedPreview = useCallback(() => {
    setPlanPreviewUrl("");
    setPlanPreviewSummary(null);
    setPlanPreviewAnnotations(null);
    setBackendResult(null);
    setPlanPreviewProjectId(null);
    debugLog("clear-generated-preview");
  }, []);

  useEffect(() => {
    if (buildingPlacements.length > 0 || detectedPlacements.length > 0) return;
    if (backendResult) return;
    if (!planPreviewUrl) return;
    debugLog("clear-preview-empty-canonical");
    clearGeneratedPreview();
  }, [
    backendResult,
    buildingPlacements.length,
    clearGeneratedPreview,
    debugLog,
    detectedPlacements.length,
    planPreviewUrl,
  ]);

  const buildDefaultPolyline = useCallback(
    (target: { x: number; y: number; w: number; d: number }): Array<[number, number]> => {
      const isHorizontal = target.w >= target.d;
      if (isHorizontal) {
        return [
          [target.x, target.y + target.d / 2],
          [target.x + target.w, target.y + target.d / 2],
        ];
      }
      return [
        [target.x + target.w / 2, target.y],
        [target.x + target.w / 2, target.y + target.d],
      ];
    },
    [],
  );

  const handleAddObject = useDashboardAddObjectAction({
    buildingPlacements,
    clearGeneratedPreview,
    computeParkingFootprint,
    debugLog,
    ensureSiteBoundary,
    formatObjectLabel,
    hasSiteBoundary,
    lotHeight,
    lotWidth,
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
    pushRecoveryMessage,
    recordDraftUndoAction,
    recordRecentChange,
    resolveDefaultBuildingDims,
    resolveLotBounds,
    setActivePlacementId,
    setBuildingPlacements,
    setLotHeight,
    setLotWidth,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setPreviewQuality,
  });

  const {
    addGradingDrainageReviewContext,
    createGenerateConceptObjects,
  } = useDashboardReviewConceptActions({
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
  });

  const handleUpdateBuilding = useDashboardObjectUpdateAction({
    buildingPlacements,
    buildingPlacementsRef,
    clearGeneratedPreview,
    computeParkingFootprint,
    currentProject,
    ensureProjectDraftRef,
    markSystemsStale,
    payloadPreview,
    previewRefreshIntentRef,
    pushRecoveryMessage,
    recordDraftUndoAction,
    recordRecentChange,
    resolveParkingParams,
    saveProjectRef,
    setBuildingPlacements,
    setFitToSiteRequest,
    setStatusMessage,
    units,
  });

  const {
    persistDetectedPlacements,
    persistDraftRefresh,
    reportObjectActionBlocker,
  } = useDashboardObjectPersistenceActions({
    appendChatMessage,
    currentProject,
    ensureProjectDraftRef,
    payloadPreview,
    previewRefreshIntentRef,
    saveProjectRef,
    setObjectManagerStatusMessage,
    setStatusMessage,
  });

  const {
    handleRemoveBuilding,
    handleRestoreBuilding,
  } = useDashboardObjectRemoveRestoreActions({
    activePlacementId,
    buildingPlacements,
    clearGeneratedPreview,
    debugLog,
    ensureProjectDraftRef,
    markSystemsStale,
    previewRefreshIntentRef,
    pushRecoveryMessage,
    recordDraftUndoAction,
    recordRecentChange,
    saveProjectRef,
    setActivePlacementId,
    setBuildingPlacements,
    setFocusObjectId,
    setPlacementModeEnabled,
    setSelectedObjectIds,
    setStatusMessage,
  });

  const {
    handleAlignObjectVertexToPrevious,
    handleDeleteObjectVertex,
    handleInsertObjectVertex,
    handleObjectManagerArraySelected,
    handleObjectManagerBulkColor,
    handleObjectManagerBulkCopyByOffset,
    handleObjectManagerBulkDelete,
    handleObjectManagerBulkDuplicate,
    handleObjectManagerBulkLayout,
    handleObjectManagerBulkLock,
    handleObjectManagerBulkMirror,
    handleObjectManagerBulkMove,
    handleObjectManagerBulkMoveTo,
    handleObjectManagerBulkRotate,
    handleObjectManagerBulkScale,
    handleObjectManagerBulkType,
    handleObjectManagerBulkVisibility,
    handleObjectManagerCombineSelected,
    handleObjectManagerCopy,
    handleObjectManagerDelete,
    handleObjectManagerDeleteBlock,
    handleObjectManagerExplodeCombined,
    handleObjectManagerInsertBlock,
    handleObjectManagerInvertSelection,
    handleObjectManagerIsolateSelected,
    handleObjectManagerLayerIsolate,
    handleObjectManagerLayerLock,
    handleObjectManagerLayerSelect,
    handleObjectManagerLayerVisibility,
    handleObjectManagerPaste,
    handleObjectManagerRenameBlock,
    handleObjectManagerSaveBlock,
    handleObjectManagerSelect,
    handleObjectManagerSelectVisibleDraft,
    handleObjectManagerToggleMultiSelect,
    handleObjectManagerTransform,
    handleObjectManagerUpdateBlock,
    handleSnapObjectVertexToNearestEndpoint,
    handleUpdateObjectVertex,
  } = useDashboardObjectManagerActions({
    activePlacementId,
    arrayColumns,
    arrayRows,
    arraySpacingX,
    arraySpacingY,
    bulkMoveToX,
    bulkMoveToY,
    bulkMoveX,
    bulkMoveY,
    bulkRotateAngle,
    bulkScaleFactor,
    buildingPlacements,
    buildingPlacementsRef,
    clearGeneratedPreview,
    combineObjectName,
    combineObjectType,
    draftBlockLibrary,
    draftBlockName,
    handleRemoveBuilding,
    handleUpdateBuilding,
    markSystemsStale,
    objectClipboard,
    persistDraftRefresh,
    recordDraftUndoAction,
    recordRecentChange,
    reportObjectActionBlocker,
    selectedObjectIds,
    setActivePlacementId,
    setBuildingPlacements,
    setCombineObjectName,
    setCombineObjectType,
    setDraftBlockLibrary,
    setDraftBlockName,
    setObjectClipboard,
    setObjectManagerStatusMessage,
    setPreviewInteraction,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
    appendChatMessage,
  });

  const {
    handleCreateCustomGeometry,
    handlePlaceBuilding,
    handlePlaceObject,
    handleSelectPlacementTarget,
    handleToggleBuildingLock,
  } = useDashboardPlacementActionHandlers({
    activePlacementId,
    askClarification,
    buildDefaultPolyline,
    buildingPlacements,
    buildingPlacementsRef,
    clearGeneratedPreview,
    debugLog,
    ensureSiteBoundary,
    handleUpdateBuilding,
    markSystemsStale,
    persistDraftRefresh,
    resolveDefaultBuildingDims,
    resolveLotBounds,
    setActivePlacementId,
    setBuildingPlacements,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setPreviewQuality,
    setSelectedObjectIds,
    setStatusMessage,
    siteScaleLocked,
    systemsImpactedByPlacement,
    units,
  });

  const handleCreateSiteBoundary = useDashboardSiteBoundaryDrawAction({
    buildManualFields,
    buildingCount,
    buildingDepth,
    buildingPlacements,
    buildingWidth,
    clearGeneratedPreview,
    currentProject,
    drainage,
    ensureProjectDraftRef,
    fileName,
    grading,
    markSystemsStale,
    maxAdaCrossSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    minSlopePct,
    parkingCount,
    payloadPreview,
    pipeMinSlopePct,
    previewRefreshIntentRef,
    projectType,
    roads,
    saveProjectRef,
    setback,
    setBuildingPlacements,
    setCurrentProject,
    setFitToSiteRequest,
    setLotHeight,
    setLotWidth,
    setShowSiteBounds,
    setSiteScaleLocked,
    setSiteSelectionMode,
    setPreviewQuality,
    setStatusMessage,
    siteName,
    units,
    utilities,
  });

  function askClarification(question: string, action: string, payload?: Record<string, unknown>) {
    setPendingClarification({ action, payload, question });
    setActiveSidePanel("chat");
    setChatCollapsed(false);
    appendChatMessage("assistant", question, "status");
    setStatusMessage(question);
  }

  const scheduleScaleSave = useDashboardScaleSaveScheduler({
    currentProject,
    detectionScaleFeet,
    detectionScalePixels,
    payloadPreview,
    projectLoadRequestRef,
    resolvedProjectIdRef,
    saveProjectRef,
    scaleSaveTimeoutRef,
    siteScaleLocked,
  });

  useEffect(() => {
    if (buildingPlacements.length > 0) {
      setBuildingCount(String(buildingPlacements.length));
    }
  }, [buildingPlacements.length]);

  const applyControlOverrides = (overrides: ControlOverrides) => {
    if (overrides.projectType) setProjectType(overrides.projectType);
    if (overrides.units) setUnits(overrides.units);
    if (typeof overrides.roads === "boolean") setRoads(overrides.roads);
    if (typeof overrides.grading === "boolean") setGrading(overrides.grading);
    if (typeof overrides.drainage === "boolean") setDrainage(overrides.drainage);
    if (typeof overrides.utilities === "boolean") setUtilities(overrides.utilities);
    if (typeof overrides.siteName === "string") setSiteName(overrides.siteName);
    if (typeof overrides.fileName === "string") setFileName(overrides.fileName);
    if (typeof overrides.siteAddress === "string") setSiteAddress(overrides.siteAddress);
    if (typeof overrides.lotWidth === "string" || typeof overrides.lotWidth === "number") {
      setLotWidth(String(overrides.lotWidth));
    }
    if (typeof overrides.lotHeight === "string" || typeof overrides.lotHeight === "number") {
      setLotHeight(String(overrides.lotHeight));
    }
    if (typeof overrides.buildingWidth === "string" || typeof overrides.buildingWidth === "number") {
      setBuildingWidth(String(overrides.buildingWidth));
    }
    if (typeof overrides.buildingDepth === "string" || typeof overrides.buildingDepth === "number") {
      setBuildingDepth(String(overrides.buildingDepth));
    }
    if (typeof overrides.buildingCount === "string" || typeof overrides.buildingCount === "number") {
      setBuildingCount(String(overrides.buildingCount));
    }
    if (typeof overrides.setback === "string" || typeof overrides.setback === "number") {
      setSetback(String(overrides.setback));
    }
    if (typeof overrides.parkingCount === "string" || typeof overrides.parkingCount === "number") {
      setParkingCount(String(overrides.parkingCount));
    }
    if (typeof overrides.minSlopePct === "string" || typeof overrides.minSlopePct === "number") {
      setMinSlopePct(String(overrides.minSlopePct));
    }
    if (typeof overrides.pipeMinSlopePct === "string" || typeof overrides.pipeMinSlopePct === "number") {
      setPipeMinSlopePct(String(overrides.pipeMinSlopePct));
    }
    if (typeof overrides.maxParkingSlopePct === "string" || typeof overrides.maxParkingSlopePct === "number") {
      setMaxParkingSlopePct(String(overrides.maxParkingSlopePct));
    }
    if (typeof overrides.maxRoadGradePct === "string" || typeof overrides.maxRoadGradePct === "number") {
      setMaxRoadGradePct(String(overrides.maxRoadGradePct));
    }
    if (typeof overrides.maxAdaCrossSlopePct === "string" || typeof overrides.maxAdaCrossSlopePct === "number") {
      setMaxAdaCrossSlopePct(String(overrides.maxAdaCrossSlopePct));
    }
  };

  const {
    buildPayloadFromOverrides,
    withReactiveRerunContext,
  } = useDashboardPlanPayloadBuilder({
    assistedEnabled,
    backendResult,
    buildManualFields,
    buildingCount,
    buildingDepth,
    buildingPlacements,
    buildingWidth,
    chatMessagesRef,
    currentProject,
    drainage,
    fileName,
    grading,
    imageName,
    lotHeight,
    lotWidth,
    maxAdaCrossSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    minSlopePct,
    parkingCount,
    pipeMinSlopePct,
    projectId,
    projectType,
    prompt,
    roads,
    setback,
    siteName,
    systemStatuses,
    units,
    utilities,
  });

  const isConnectivityFailureMessage = (message: string) =>
    message.toLowerCase().includes("backend unreachable") ||
    message.includes("could not reach the backend") ||
    message.includes("Failed to fetch") ||
    message.includes("Load failed") ||
    message.includes("NetworkError");

  const executePlanAction = async ({
    mode,
    requestPayload,
    resolvedProjectId,
    assistantPrefix,
    clearPromptOnSuccess = false,
    signal,
    timeoutMs,
    allowQueueFallback = true,
    forceQueue = false,
  }: {
    mode: PlanToolMode;
    requestPayload: PlanRequestPayload;
    resolvedProjectId?: string | null;
    assistantPrefix?: string | null;
    clearPromptOnSuccess?: boolean;
    signal?: AbortSignal;
    timeoutMs?: number;
    allowQueueFallback?: boolean;
    forceQueue?: boolean;
  }) => {
    setBusy(true);
    setActivePlanTool(mode);
    updateProjectStatus({
      state: "working",
      area: "generate",
      title:
        mode === "fix"
          ? "Fix pass working"
          : mode === "improve"
            ? "Improvement pass working"
            : "Generate working",
      detail:
      mode === "fix"
        ? "Civora AI is starting the fix run."
        : mode === "improve"
          ? "Civora AI is starting the improvement run."
          : "Civora AI is starting the review draft run.",
      nextAction: "Keep this project open until the run finishes or shows what needs attention.",
    });
    const shouldQueueStagedRun = Boolean((forceQueue || requestPayload?.full_design_mode) && token);
    if (shouldQueueStagedRun) {
      try {
        const queued = await postJson<{ job: JobSummary }>(
          "/api/jobs/orchestrate",
          {
            project_id:
              resolvedProjectId !== undefined
                ? resolvedProjectId
                : ((requestPayload?.project_id ?? projectId) || null),
            request: requestPayload,
          },
          { token },
        );
        setActiveJobId(queued.job.job_id);
        const queuedDetail = forceQueue
          ? `I queued this long-running engineering workflow as ${queued.job.job_id} so progress stays visible while the backend works.`
          : `I queued the full staged design workflow as ${queued.job.job_id} so each phase can save, pause for review, and continue on the same project.`;
        appendChatMessage(
          "assistant",
          [
            assistantPrefix,
            queuedDetail,
          ]
            .filter(Boolean)
            .join(" "),
          "status",
        );
        updateProjectStatus({
          state: "working",
          area: "generate",
          title: "Generate queued",
          detail: `Queued staged run ${queued.job.job_id}.`,
          nextAction: "Open Jobs or watch the visible job status until the backend finishes.",
        });
        if (clearPromptOnSuccess) {
          setPrompt("");
        }
        return;
      } catch (queueError) {
	          const queueMessage = `Generate could not complete: ${panelErrorMessage(queueError, "Job queue could not complete.")} Next action: check the backend connection, then press Generate again.`;
        appendChatMessage("assistant", queueMessage, "status");
        updateProjectStatus({
          state: "blocked",
          area: "generate",
          title: "Generate needs sign-in",
          detail: panelErrorMessage(queueError, "Job queue failed."),
          nextAction: "Check the backend connection, then press Generate again.",
        });
        return;
      } finally {
        setBusy(false);
      }
    }
    const liveRunController = new AbortController();
    const liveRunTimeoutMs = typeof timeoutMs === "number" ? timeoutMs : 12_000;
    let timedOut = false;
    const handleAbort = () => liveRunController.abort();
    signal?.addEventListener("abort", handleAbort, { once: true });
    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      liveRunController.abort();
    }, liveRunTimeoutMs);
    try {
      const data = await postJson<PlanResponse>("/api/orchestrate", requestPayload, {
        token,
        signal: liveRunController.signal,
      });
      applyBackendResult(data);
      appendChatMessage(
        "assistant",
        [assistantPrefix, summarizePlanResponse(data, mode)].filter(Boolean).join(" "),
      );
      await requestPreview(
        {
          project_id: projectId || currentProject?.project_id || null,
          result: data,
          filename_stem: fileName || siteName || "civora-ai-plan",
        },
        { silent: true },
      );
      setStatusMessage(
        mode === "fix"
          ? "Civora AI ran a focused fix pass."
          : mode === "improve"
            ? "Civora AI generated an improved plan."
            : "Plan run completed.",
      );
      updateProjectStatus({
        state: "needs review",
        area: "generate",
        title:
          mode === "fix"
            ? "Fix pass needs review"
            : mode === "improve"
              ? "Improvement pass needs review"
              : "Generate needs review",
        detail:
          mode === "fix"
            ? "Civora AI ran a focused fix pass."
            : mode === "improve"
              ? "Civora AI generated an improved plan."
              : "Plan run completed.",
        nextAction: "Review the generated draft, needs, assumptions, and preview before deliverables.",
      });
      if (clearPromptOnSuccess) {
        setPrompt("");
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "";
      if (timedOut && token && allowQueueFallback) {
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id:
                resolvedProjectId !== undefined
                  ? resolvedProjectId
                  : ((requestPayload?.project_id ?? projectId) || null),
              request: requestPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            [
              assistantPrefix,
              "The live run took too long to stay on the direct connection, so I queued it in the background instead.",
              `Job ${queued.job.job_id} is now running and I’ll pick it up when it finishes.`,
            ]
              .filter(Boolean)
              .join(" "),
            "status",
          );
          updateProjectStatus({
            state: "working",
            area: "generate",
            title: "Generate queued",
            detail: `The live run was queued as ${queued.job.job_id} because the direct request took too long.`,
            nextAction: "Open Jobs or watch the visible job status until the backend finishes.",
          });
          return;
        } catch (queueError) {
          const queueMessage = `Generate failed: ${panelErrorMessage(queueError, "Job queue failed.")} Next action: check the backend connection, then press Generate again.`;
          appendChatMessage("assistant", queueMessage, "status");
          updateProjectStatus({
            state: "blocked",
            area: "generate",
	            title: "Generate needs attention",
            detail: panelErrorMessage(queueError, "Job queue failed."),
            nextAction: "Check the backend connection, then press Generate again.",
          });
          return;
        }
      }
      if (error instanceof Error && error.name === "AbortError") {
        appendChatMessage(
          "assistant",
          "I stopped the live request before it finished.",
          "status",
        );
        setStatusMessage("Cancelled the live request.");
        return;
      }
      const looksLikeConnectivityFailure = isConnectivityFailureMessage(errorMessage);
      if (looksLikeConnectivityFailure && token && allowQueueFallback) {
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id:
                resolvedProjectId !== undefined
                  ? resolvedProjectId
                  : ((requestPayload?.project_id ?? projectId) || null),
              request: requestPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            [
              assistantPrefix,
              "The live run took too long to stay on the direct connection, so I queued it in the background instead.",
              `Job ${queued.job.job_id} is now running and I’ll pick it up when it finishes.`,
            ]
              .filter(Boolean)
              .join(" "),
            "status",
          );
          updateProjectStatus({
            state: "working",
            area: "generate",
            title: "Generate queued",
            detail: `The live run was queued as ${queued.job.job_id} because the direct request took too long.`,
            nextAction: "Open Jobs or watch the visible job status until the backend finishes.",
          });
          return;
        } catch (queueError) {
	          const queueMessage = `Generate could not complete: ${panelErrorMessage(queueError, "Job queue could not complete.")} Next action: check the backend connection, then press Generate again.`;
          appendChatMessage(
            "assistant",
            queueMessage,
            "status",
          );
          updateProjectStatus({
            state: "blocked",
            area: "generate",
	            title: "Generate needs attention",
            detail: panelErrorMessage(queueError, "Job queue failed."),
            nextAction: "Check the backend connection, then press Generate again.",
          });
          return;
        }
      }
      const message =
        mode === "fix"
	          ? `Fix pass could not complete: ${panelErrorMessage(error, "Could not complete the fix pass.")} Next action: review inputs, then retry Fix.`
          : mode === "improve"
	            ? `Improve pass could not complete: ${panelErrorMessage(error, "Could not complete the improvement pass.")} Next action: review inputs, then retry Improve.`
	            : `Generate could not complete: ${panelErrorMessage(error, "Could not update the design.")} Next action: check the status message, then press Generate again.`;
      appendChatMessage("assistant", message, "status");
      updateProjectStatus({
        state: "blocked",
        area: "generate",
        title: mode === "run" ? "Generate needs attention" : `${mode} needs attention`,
        detail: panelErrorMessage(error, mode === "run" ? "Could not update the design." : "Could not complete the run."),
        nextAction: mode === "run" ? "Check the status message, then press Generate again." : "Review inputs, then retry.",
      });
    } finally {
      window.clearTimeout(timeoutId);
      signal?.removeEventListener("abort", handleAbort);
      setBusy(false);
      setActivePlanTool("run");
      directRunAbortRef.current = null;
    }
  };

  const runOrchestrator = async (mode: PlanToolMode = "run") => {
    if (!token) return;
    if (
      runSubmissionRef.current ||
      Boolean(
        currentProjectActiveJob &&
          ["queued", "running", "awaiting_approval", "cancelling"].includes(
            String(currentProjectActiveJob.status || "").toLowerCase(),
          ),
      )
    ) {
      setStatusMessage("Civora AI is already working on your last request.");
      return;
    }
    const trimmedPrompt = prompt.trim();
    if (mode === "run" && !trimmedPrompt && !imageName) {
      setStatusMessage("Add a request or image so Civora AI has something to work from.");
      return;
    }
    if (mode !== "run") {
      if (mode === "fix") {
        appendChatMessage(
          "system",
          "Fix the active design and focus on the most important engineering needs.",
          "action",
        );
      } else if (mode === "improve") {
        appendChatMessage(
          "system",
          "Improve the active design while preserving the current project intent.",
          "action",
        );
      }
      const basePayload = buildPayloadFromOverrides({}, undefined, projectId || null);
      await executePlanAction({
        mode,
        requestPayload: {
          ...basePayload,
          full_design_mode: true,
          optimize_goal:
            mode === "fix"
              ? suggestedImproveGoal ?? "reduce_pipe_length"
              : suggestedImproveGoal,
          meta: {
            ...(basePayload.meta ?? {}),
            requested_plan_tool: mode,
          },
        },
        resolvedProjectId: projectId || null,
      });
      return;
    }

    const runController = new AbortController();
    directRunAbortRef.current = runController;
    runSubmissionRef.current = true;
    setBusy(true);
    setActivePlanTool("run");
    setPrompt("");
    appendChatMessage("user", trimmedPrompt);
    setStatusMessage("Civora AI is reviewing your request and starting the design run.");
    try {
      const resolvedProjectId =
        ((await ensureProjectDraft()) ?? projectId) || null;
      const decision = await postJson<ChatDecisionResponse>(
        "/api/chat/decide",
        {
          message: trimmedPrompt,
          context: buildChatDecisionContext({}, trimmedPrompt),
        },
        { token, signal: runController.signal },
      );
      const overrides = decision.control_overrides ?? {};
      applyControlOverrides(overrides);
      const shouldAutoName = false;
      const shouldAutoFileName = false;
      const generatedTitle = siteName.trim();
      const generatedFileName = fileName.trim();

      const isChatOnlyDecision =
        decision.needs_clarification ||
        decision.intent === "conversation" ||
        decision.intent === "settings" ||
        decision.intent === "explain" ||
        (decision.run_mode === "none" && !decision.design_prompt);

      if (isChatOnlyDecision) {
        const chatMetadata = decision.response_metadata ?? {};
        const chatCommandPayload =
          chatMetadata.command_payload && typeof chatMetadata.command_payload === "object"
            ? (chatMetadata.command_payload as Record<string, unknown>)
            : {};
        const uiPanel = chatCommandPayload.ui_navigation_target ?? chatMetadata.ui_navigation_target;
        const uiMode = chatCommandPayload.requested_ui_mode ?? chatMetadata.requested_ui_mode;
        const validPanels: SidePanelKey[] = [
          "projects", "trust", "dashboard", "model", "site_existing", "import_survey", "objects", "generate", "grading", "drainage", "sanitary", "water", "utilities", "roadway", "landscape", "details", "layers", "analysis", "reports", "quantities", "deliverables", "files", "standards", "templates", "catalogs", "libraries", "data", "settings", "chat", "system_grading", "system_storm", "system_sanitary", "system_water", "system_roadway", "system_utilities", "system_landscape",
        ];
        const validModes: WorkspaceMode[] = ["trust", "dashboard", "setup", "canvas", "layers", "review", "deliver", "data", "settings"];
        if (uiMode && validModes.includes(uiMode as WorkspaceMode)) {
          setActiveWorkspaceMode(uiMode as WorkspaceMode);
        }
        if (uiPanel && validPanels.includes(uiPanel as SidePanelKey)) {
          setActiveSidePanel(uiPanel as SidePanelKey);
        }
        const requestedPreviewMode = chatCommandPayload.requested_preview_mode ?? chatMetadata.requested_preview_mode;
        const requestedPreviewQuality = chatCommandPayload.requested_preview_quality ?? chatMetadata.requested_preview_quality;
        if (requestedPreviewMode === "2d" || requestedPreviewMode === "3d") {
          setPreviewMode(requestedPreviewMode);
        }
        if (requestedPreviewQuality === "standard" || requestedPreviewQuality === "high") {
          setPreviewQuality(requestedPreviewQuality);
        }
        if (chatCommandPayload.requested_site_lock_state || chatMetadata.requested_site_lock_state) {
          setActiveWorkspaceMode("setup");
          setActiveSidePanel("site_existing");
        }
        const alternativesPayload = chatCommandPayload.design_alternatives_v1 ?? chatMetadata.design_alternatives_v1;
        if (alternativesPayload) {
          const alternatives = alternativesPayload as DesignAlternativesV1;
          setBackendResult((prev) => {
            if (!prev?.final_plan) return prev;
            return {
              ...prev,
              final_plan: {
                ...prev.final_plan,
                meta: {
                  ...(prev.final_plan.meta ?? {}),
                  design_alternatives_v1: alternatives,
                },
              },
            };
          });
        }
        const issueTrackerPayload = chatCommandPayload.review_issue_tracker_v1 ?? chatMetadata.review_issue_tracker_v1;
        if (issueTrackerPayload) {
          const issueTracker = issueTrackerPayload as ReviewIssueTrackerV1;
          setBackendResult((prev) => {
            if (!prev?.final_plan) return prev;
            return {
              ...prev,
              final_plan: {
                ...prev.final_plan,
                meta: {
                  ...(prev.final_plan.meta ?? {}),
                  review_issue_tracker_v1: issueTracker,
                },
              },
            };
          });
        }
        appendChatMessage(
          "assistant",
          decision.intent === "explain" && !decision.assistant_message
            ? "I can explain the current design once there’s a plan in the workspace."
            : decision.assistant_message,
          decision.intent === "explain" ? "explanation" : "message",
        );
        setStatusMessage(
          decision.needs_clarification
            ? "Civora AI is asking for a little more detail before running a design."
            : "Civora AI responded in chat without rerunning the planner.",
        );
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        setBusy(false);
        setActivePlanTool("run");
        return;
      }

      const resolvedMode: PlanToolMode =
        decision.run_mode === "fix"
          ? "fix"
          : decision.run_mode === "improve"
            ? "improve"
            : "run";

      if (resolvedMode !== "run") {
        const basePayload = buildPayloadFromOverrides(overrides, undefined, resolvedProjectId);
        await executePlanAction({
          mode: resolvedMode,
          requestPayload: {
            ...basePayload,
            full_design_mode: true,
            optimize_goal:
              resolvedMode === "fix"
                ? suggestedImproveGoal ?? "reduce_pipe_length"
                : suggestedImproveGoal,
            meta: {
              ...(basePayload.meta ?? {}),
              requested_plan_tool: resolvedMode,
              chat_decision_reason: decision.reason,
              chat_command: decision.response_metadata ?? null,
            },
          },
          resolvedProjectId,
          assistantPrefix: decision.assistant_message,
          clearPromptOnSuccess: true,
          signal: runController.signal,
        });
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        return;
      }

      if (!decision.design_prompt && !imageName) {
        appendChatMessage(
          "assistant",
          decision.assistant_message || "Tell me what you want me to design or change.",
        );
        setStatusMessage(
          "Civora AI needs a little more direction before generating a design.",
        );
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        setBusy(false);
        setActivePlanTool("run");
        return;
      }

      const basePayload = buildPayloadFromOverrides(
        overrides,
        decision.design_prompt || trimmedPrompt,
        resolvedProjectId,
      );
      await executePlanAction({
        mode: "run",
        requestPayload: {
          ...basePayload,
          meta: {
            ...(basePayload.meta ?? {}),
            chat_decision_reason: decision.reason,
            chat_decision_confidence: decision.confidence,
            chat_command: decision.response_metadata ?? null,
          },
        },
        resolvedProjectId,
        assistantPrefix: decision.assistant_message,
        clearPromptOnSuccess: true,
        signal: runController.signal,
      });
      await saveProject({
        silent: true,
        projectIdOverride: resolvedProjectId,
        nameOverride: generatedTitle || undefined,
        fileNameOverride: generatedFileName || undefined,
        autoNamedOverride: shouldAutoName,
        autoFileNamedOverride: shouldAutoFileName,
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "";
      if (error instanceof Error && error.name === "AbortError") {
        appendChatMessage(
          "assistant",
          "I stopped the live request before it finished.",
          "status",
        );
        setStatusMessage("Cancelled the live request.");
        setBusy(false);
        setActivePlanTool("run");
        directRunAbortRef.current = null;
        return;
      }
      if (token && isConnectivityFailureMessage(errorMessage)) {
        try {
          const resolvedProjectId =
            projectId || (await ensureProjectDraft()) || null;
          const fallbackPayload = buildPayloadFromOverrides(
            {},
            trimmedPrompt,
            resolvedProjectId,
          );
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id: resolvedProjectId,
              request: fallbackPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            `The live request could not stay connected long enough to finish the first pass, so I queued it in the background instead. Job ${queued.job.job_id} is queued and I’ll pick it up when it starts reporting progress.`,
            "status",
          );
          setStatusMessage(
            `The live request was queued as ${queued.job.job_id} because the direct connection dropped.`,
          );
          return;
        } catch (queueError) {
          const friendly = chatFailureMessage(queueError);
          const technical = panelErrorMessage(queueError, "I couldn’t queue the design request either.");
          appendChatMessage(
            "assistant",
            friendly,
            "status",
          );
          setStatusMessage(`Chat backend fallback failed: ${technical}`);
          return;
        }
      }
      const friendly = chatFailureMessage(error);
      const technical = panelErrorMessage(error, "Civora AI could not process that message.");
      appendChatMessage(
        "assistant",
        friendly,
        "status",
      );
      setStatusMessage(`Chat backend failed: ${technical}`);
      setBusy(false);
      setActivePlanTool("run");
    } finally {
      runSubmissionRef.current = false;
      directRunAbortRef.current = null;
    }
  };

  const {
    autoSiteContextFlowSummary,
    autoSiteContextRows,
    configuredLocalGisProviders,
    drivewaySuggestion,
    gradingContextHint,
    localGisProviderRegistry,
    onlineDiscovery,
    onlineDiscoverySources,
    onlineFoundSources,
    onlineSourceLookupLabel,
    onlineSourceLookupUnavailable,
    previewSourceContextBadges,
    roadFrontageHint,
    siteIntelligenceAssumed,
    siteIntelligenceFound,
    siteIntelligenceMissing,
    siteIntelligenceOutside,
    siteIntelligenceSummary,
  } = useDashboardAutoSiteContextState({
    assumedTerrainSlopePct,
    autoExistingConditionsStatus,
    currentPlanMeta,
    hasAppliedAddress,
    hasAssumedTerrainSlope,
    siteInputs,
  });
  const getGeneratePreflightBlockers = useCallback(
    (target: SystemGenerationTarget) =>
      buildGeneratePreflightBlockers({
        target,
        lot: resolveLotBounds(),
        siteScaleLocked,
        hasTerrainSource,
        hasStandardsEvidence,
        hasAppliedAddress,
        onlineSourceLookupUnavailable,
        hasVerifiedSurveyControl,
        hasAssumedTerrainSlope,
      }),
    [
      hasAppliedAddress,
      hasAssumedTerrainSlope,
      hasStandardsEvidence,
      hasTerrainSource,
      hasVerifiedSurveyControl,
      onlineSourceLookupUnavailable,
      resolveLotBounds,
      siteScaleLocked,
    ],
  );
  const fullGeneratePreflightBlockers = getGeneratePreflightBlockers("full");
  const canonicalWorkspaceBlockers = useMemo(
    () =>
      buildCanonicalWorkspaceBlockers({
        fullGeneratePreflightBlockers,
        issues,
        analysisIssues,
        siteBoundaryState: siteInputs?.site_boundary_state,
        siteScaleLocked,
      }),
    [
      analysisIssues,
      fullGeneratePreflightBlockers,
      issues,
      siteInputs?.site_boundary_state,
      siteScaleLocked,
    ],
  );
  const canonicalWorkspaceBlockerText =
    canonicalWorkspaceBlockers.length
      ? canonicalWorkspaceBlockers.join("; ")
      : "No needs-input items recorded for the active workspace; Civora outputs remain review-required.";
  const {
    restoreTruthLabel,
    projectDrawerStateLabel,
    projectDrawerStateDetail,
  } = buildProjectTruthLabels({
    effectiveDemoWorkspaceEnabled,
    workspaceRestoreState,
    currentProject,
    token,
    projectDrawerNotice,
  });

  const {
    cancelActiveCommandState,
    focusCommandInput,
    refuseUnsafeConstructionCommand,
    shouldRouteToOrchestrator,
  } = useDashboardCommandUtilityActions({
    appendChatMessage,
    commandInputRef,
    setActivePlacementId,
    setCadToolRequest,
    setCommandBarExpanded,
    setPendingClarification,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setShortcutsOverlayOpen,
    setStatusMessage,
    setWorkspaceChromeMinimized,
    updateProjectStatus,
  });

  const handleCreateDenseCommercialConcept = useDashboardDenseConceptAction({
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
  });

  const { saveProject } = useDashboardProjectSave({
    chatMessagesRef,
    currentProject,
    effectiveDemoWorkspaceEnabled,
    fileName,
    fileNameAuto,
    isSeededDemoProjectId,
    payloadPreview,
    projectId,
    projectLoadRequestRef,
    resolvedProjectIdRef,
    setBusy,
    setCurrentProject,
    setProjectDrawerNotice,
    setProjectId,
    setWorkspaceRestoreState,
    setupWizardStateRef,
    siteName,
    siteNameAuto,
    token,
    updateProjectStatus,
    upsertProjectSummary,
  });

  useEffect(() => {
    const activeProjectId = resolvedProjectIdRef.current;
    if (!token || !activeProjectId || currentProject?.project_id !== activeProjectId) return;
    if (autosaveSuspendRef.current) return;
    const workspaceGeneration = projectLoadRequestRef.current;
    const savedThread = Array.isArray(currentProject?.project_input?.meta?.chat_thread)
      ? currentProject.project_input.meta.chat_thread
      : [];
    const currentThread = chatMessagesRef.current.map(
      ({ role, content, kind, createdAt, id }) => ({
        role,
        content,
        kind,
        createdAt,
        id,
      }),
    );
    const savedPrompt = String(currentProject?.project_input?.prompt_text ?? "");
    const currentPrompt = String(prompt ?? "");
    const threadChanged =
      JSON.stringify(savedThread) !== JSON.stringify(currentThread);
    const promptChanged = savedPrompt !== currentPrompt;
    if (!threadChanged && !promptChanged) {
      return;
    }
    if (chatAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(chatAutosaveTimeoutRef.current);
    }
    chatAutosaveTimeoutRef.current = window.setTimeout(() => {
      chatAutosaveTimeoutRef.current = null;
      if (projectLoadRequestRef.current !== workspaceGeneration) return;
      if (resolvedProjectIdRef.current !== activeProjectId) return;
      void saveProject({ silent: true, projectIdOverride: activeProjectId });
    }, 700);
  }, [chatMessages, prompt, token, projectId, currentProject]);

  useEffect(() => {
    const activeProjectId = resolvedProjectIdRef.current;
    if (!token || !activeProjectId || currentProject?.project_id !== activeProjectId) return;
    if (autosaveSuspendRef.current) return;
    const workspaceGeneration = projectLoadRequestRef.current;
    if (controlAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(controlAutosaveTimeoutRef.current);
    }
    controlAutosaveTimeoutRef.current = window.setTimeout(() => {
      controlAutosaveTimeoutRef.current = null;
      if (projectLoadRequestRef.current !== workspaceGeneration) return;
      if (resolvedProjectIdRef.current !== activeProjectId) return;
      void saveProject({ silent: true, projectIdOverride: activeProjectId });
    }, 700);
  }, [
    token,
    currentProject?.project_id,
    siteName,
    fileName,
    units,
    projectType,
    lotWidth,
    lotHeight,
    buildingWidth,
    buildingDepth,
    buildingCount,
    setback,
    parkingCount,
    minSlopePct,
    pipeMinSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    maxAdaCrossSlopePct,
    roads,
    grading,
    drainage,
    utilities,
    buildingPlacements,
  ]);

  useEffect(() => {
    if (!currentProject?.project_id) return;
    if (lastSiteInputProjectRef.current === currentProject.project_id) return;
    lastSiteInputProjectRef.current = currentProject.project_id;
    const siteInputs =
      currentProject?.project_input?.meta?.site_inputs &&
      typeof currentProject.project_input.meta.site_inputs === "object"
        ? currentProject.project_input.meta.site_inputs
        : {};
    const mapSnapshot = siteInputs?.map_snapshot ?? {};
    const mapAnalysisResult = siteInputs?.map_analysis ?? null;
    const surveyFile = siteInputs?.survey_file ?? {};
    const existingImport = (siteInputs as Record<string, unknown>)?.existing_conditions_import as Record<string, unknown> | undefined;
    const slopeEstimate = siteInputs?.slope_estimate ?? null;
      const detectionScale = siteInputs?.detection_scale ?? {};
      const alignmentLocked =
        typeof siteInputs?.site_alignment_locked === "boolean"
          ? siteInputs.site_alignment_locked
          : null;
    const useSurvey = siteInputs?.use_survey_for_grading;
    const storedPoints = Array.isArray(siteInputs?.survey_points) ? siteInputs?.survey_points : [];
    const detectedObjects = Array.isArray(siteInputs?.detected_objects)
      ? (siteInputs?.detected_objects as BuildingPlacement[])
      : [];
    setSiteAddress(String(siteInputs?.address || ""));
    setSurveyFileName(String(surveyFile?.stored_filename || ""));
    setSourceEffectRows(Array.isArray(existingImport?.source_effect_rows) ? existingImport.source_effect_rows.map(String) : []);
    setSurveySlopeEstimate(slopeEstimate || null);
    setUseSurveyForGrading(useSurvey !== undefined ? Boolean(useSurvey) : true);
    setSurveyPoints(storedPoints as number[][]);
    setSurveyPreviewPoints(
      mapSurveyPointsToSite(
        storedPoints as number[][],
        parsePositiveNumber(lotWidth),
        parsePositiveNumber(lotHeight),
      ),
    );
    setDrainageSourceOverride(
      siteInputs?.drainage_source_override === "user" ? "user" : "civora",
    );
    setSurveyDiagnostics((prev) => ({
      ...(prev ?? {}),
      fileType: siteInputs?.survey_file_type ?? prev?.fileType,
      parseSuccess: siteInputs?.survey_parse_success ?? prev?.parseSuccess,
      pointCount: siteInputs?.survey_point_count ?? prev?.pointCount,
      recognizedColumns: siteInputs?.survey_point_columns ?? prev?.recognizedColumns,
      invalidRows: siteInputs?.survey_invalid_rows ?? prev?.invalidRows,
      bounds: siteInputs?.survey_bounds ?? prev?.bounds,
      elevationRange: siteInputs?.survey_elevation_range ?? prev?.elevationRange,
      warnings: siteInputs?.survey_point_warnings ?? prev?.warnings,
    }));
      setDetectionScaleFeet(
        detectionScale?.distance_ft ? String(detectionScale.distance_ft) : "",
      );
    setDetectionScalePixels(
      detectionScale?.pixel_distance ? String(detectionScale.pixel_distance) : "",
    );
      setDetectionScaleFtPerPx(
        typeof detectionScale?.scale_ft_per_px === "number" ? detectionScale.scale_ft_per_px : null,
      );
      setDetectionScaleSource(
        detectionScale?.scale_source === "mapbox" || detectionScale?.scale_source === "manual"
          ? detectionScale.scale_source
          : "approximate",
      );
      if (alignmentLocked !== null) {
        const projectLot: { w?: string | number | null; h?: string | number | null } =
          currentProject?.project_input?.manual_fields?.lot &&
          typeof currentProject.project_input.manual_fields.lot === "object"
            ? currentProject.project_input.manual_fields.lot
            : {};
        const lotW = parsePositiveNumber(lotWidth) ?? parsePositiveNumber(projectLot.w);
        const lotH = parsePositiveNumber(lotHeight) ?? parsePositiveNumber(projectLot.h);
        if (alignmentLocked && (!lotW || !lotH)) {
          setSiteScaleLocked(false);
        } else {
          setSiteScaleLocked(alignmentLocked);
        }
      }
      const rotationValue =
        typeof siteInputs?.site_rotation_deg === "number" ? siteInputs.site_rotation_deg : 0;
      setSiteRotationDeg(rotationValue);
      setSiteRotationInput(String(rotationValue));
    setDetectedPlacements(detectedObjects);
    const mapUrl = String(mapSnapshot?.image_url || "");
    if (mapUrl) {
      setUploadedImageApiUrl(uploadedImageSrc(mapUrl, token));
    }
    setMapSnapshotPath(String(mapSnapshot?.image_path || ""));
    setMapAnalysis(mapAnalysisResult || null);
  }, [currentProject, lotHeight, lotWidth, token]);

  const { loadProject } = useDashboardProjectLoad({
    activeJob,
    activeJobId,
    applyProjectInput,
    autosaveSuspendRef,
    chatAutosaveTimeoutRef,
    controlAutosaveTimeoutRef,
    currentProject,
    currentProjectActiveJob,
    effectiveDemoWorkspaceEnabled,
    loadJobRef,
    loadProjectResultInBackgroundRef,
    projectId,
    projectLoadRequestRef,
    resetWorkspaceStateRef,
    resolvedProjectIdRef,
    restoredActiveProjectRef,
    suppressProjectAutoLoadRef,
    setBackendResult,
    setCurrentProject,
    setIssues,
    setPlanPreviewSummary,
    setPlanPreviewUrl,
    setProjectDrawerNotice,
    setProjectId,
    setSiteName,
    setWorkspaceRestoreState,
    token,
    updateProjectStatus,
  });

  const ensureProjectDraft = async (): Promise<string | null> => {
    if (!token) return null;
    if (effectiveDemoWorkspaceEnabled) return null;
    if (resolvedProjectIdRef.current) return resolvedProjectIdRef.current;
    if (projectId) return projectId;
    if (currentProject?.project_id) return currentProject.project_id;
    if (draftProjectPromiseRef.current) {
      const inFlightProject = await draftProjectPromiseRef.current;
      return inFlightProject?.project_id ?? null;
    }
    draftProjectPromiseRef.current = saveProject({
      silent: true,
      projectIdOverride: null,
      nameOverride: siteName.trim(),
      fileNameOverride: fileName.trim(),
      autoNamedOverride: false,
      autoFileNamedOverride: false,
    });
    try {
      const savedProject = await draftProjectPromiseRef.current;
      return savedProject?.project_id ?? null;
    } finally {
      draftProjectPromiseRef.current = null;
    }
  };

  useEffect(() => {
    ensureProjectDraftRef.current = ensureProjectDraft;
    saveProjectRef.current = saveProject;
  }, [ensureProjectDraft, saveProject]);

  const {
    exportPlanPdfReport,
    exportPlanPdfReviewPdf,
    updatePlanPdfElement,
    uploadPlanPdf,
  } = useDashboardPlanPdfActions({
    appendChatMessage,
    currentProject,
    ensureProjectDraft,
    planPdfExtractionSummaryRows,
    projectId,
    resolvedProjectIdRef,
    setActiveWorkspaceMode,
    setBackendResult,
    setCurrentProject,
    setPlanPdfUploadMessage,
    setPlanPdfUploadState,
    setProjectId,
    setStatusMessage,
    token,
  });

  const { uploadExistingConditions } = useDashboardExistingConditionsUpload({
    appendChatMessage,
    currentProject,
    lotHeightValue: parsePositiveNumber(lotHeight),
    lotWidthValue: parsePositiveNumber(lotWidth),
    payloadPreview,
    saveProject,
    setSurveyDiagnostics,
    setSurveyFileName,
    setSurveyPoints,
    setSurveyPreviewPoints,
    setSourceEffectRows,
    setStatusMessage,
    setSurveyUploadMessage,
    token,
    useSurveyForGrading,
  });

  const handleAnalyzeSiteAccess = useDashboardSiteAccessAnalysis({
    askClarification,
    buildingPlacements,
    setAnalysisEmptyReason,
    setAnalysisFocusLocked,
    setAnalysisIssues,
    setAnalysisPaths,
    setAnalysisSelectedIssueId,
    setStatusMessage,
  });


  useEffect(() => {
    if (!analysisSelectedIssueId) {
      setAnalysisFocusLocked(false);
    }
  }, [analysisSelectedIssueId]);

  const scheduleRotationSave = useCallback(
    (nextValue: number) => {
      const activeProjectId = resolvedProjectIdRef.current;
      if (!activeProjectId || currentProject?.project_id !== activeProjectId) return;
      const workspaceGeneration = projectLoadRequestRef.current;
      const currentInput = currentProject.project_input ?? payloadPreview;
      if (rotationSaveTimeoutRef.current) {
        window.clearTimeout(rotationSaveTimeoutRef.current);
      }
      rotationSaveTimeoutRef.current = window.setTimeout(() => {
        rotationSaveTimeoutRef.current = null;
        if (projectLoadRequestRef.current !== workspaceGeneration) return;
        if (resolvedProjectIdRef.current !== activeProjectId) return;
        const nextSiteInputs = {
          ...(currentInput?.meta?.site_inputs ?? {}),
          site_rotation_deg: nextValue,
        };
        void saveProject({
          silent: true,
          projectIdOverride: activeProjectId,
          projectInputOverride: {
            ...currentInput,
            input_mode: "user",
            strict_mode: false,
            allow_ai_fill_for_blanks: false,
            meta: {
              ...(currentInput?.meta ?? {}),
              site_inputs: nextSiteInputs,
            },
          },
        });
      }, 400);
    },
    [currentProject, payloadPreview, saveProject],
  );

  useEffect(() => {
    if (activePlacementId) return;
    const pending = buildingPlacements.find((item) => !item.placed && item.type !== "site");
    if (pending) {
      setActivePlacementId(pending.id);
    }
  }, [activePlacementId, buildingPlacements]);

  const analyzeMapSnapshot = useDashboardMapAnalysisActions({
    currentProject,
    mapSnapshotPath,
    payloadPreview,
    saveProject,
    setMapAnalysis,
    setStatusMessage,
    token,
  });

  const autoFitSite = useDashboardAutoFitSite({
    setBuildingPlacements,
    setFitToSiteRequest,
    setLotHeight,
    setLotWidth,
    setSiteScaleLocked,
  });

  const { handleAnalyzeImageFeatures, uploadImage } = useDashboardImageDetectionActions({
    askClarification,
    autoFitSite,
    buildingPlacements,
    clearGeneratedPreview,
    currentProject,
    detectionScaleFtPerPx,
    lotHeightValue: parsePositiveNumber(lotHeight),
    lotWidthValue: parsePositiveNumber(lotWidth),
    mapSnapshotPath,
    payloadPreview,
    saveProject,
    setDetectedPlacements,
    setImageName,
    setImageUploadNote,
    setImageUploadState,
    setMapSnapshotPath,
    setShowSiteBounds,
    setSiteScaleLocked,
    setSiteSelectionMode,
    setStatusMessage,
    setUploadedImageApiUrl,
    setUploadedImagePreviewUrl,
    token,
    updateProjectStatus,
  });

  const siteSetupActions = useMemo<DashboardSiteSetupActions>(
    () => ({
      autoExistingRunKeyRef,
      autoFitSite,
      clearGeneratedPreview,
      currentProject,
      defaultAssumptions,
      lastAppliedSiteRef,
      lastViewportSyncRef,
      payloadPreview,
      pushRecoveryMessage,
      recordRecentChange,
      saveProject,
      scrollToDrawingSurface,
      setActiveSidePanel,
      setActiveWorkspaceMode,
      setAddressSuggestions,
      setAnalysisIssues,
      setAnalysisPaths,
      setAnalysisSelectedIssueId,
      setAssumptions,
      setAutoExistingConditionsStatus,
      setBuildingPlacements,
      setCurrentProject,
      setDetectedPlacements,
      setFileName,
      setFileNameAuto,
      setFitToSiteRequest,
      setFocusDetectedId,
      setFocusObjectId,
      setIssues,
      setLeftSidebarOpen,
      setMapAnalysis,
      setMapSnapshotPath,
      setPreviewInteraction,
      setRenderedSidePanel,
      setRightRailCollapsed,
      setSelectedAddressSuggestion,
      setSelectedIssueId,
      setShowSiteBounds,
      setSidePanelVisible,
      setSiteAddress,
      setSiteDrawRequest,
      setSiteName,
      setSiteNameAuto,
      setSiteScaleLocked,
      setSiteSelectionMode,
      setStatusMessage,
      setSystemStatuses,
      setUploadedImageApiUrl,
      setUploadedImagePreviewUrl,
      systemStatusesDefault: DEFAULT_SYSTEM_STATUS,
    }),
    [
      autoFitSite,
      clearGeneratedPreview,
      currentProject,
      payloadPreview,
      pushRecoveryMessage,
      recordRecentChange,
      saveProject,
      scrollToDrawingSurface,
    ],
  );

  const handleToggleSiteLock = useCallback(() => {
    runDashboardToggleSiteLock({ actions: siteSetupActions, siteScaleLocked });
  }, [siteSetupActions, siteScaleLocked]);

  const handleUnlockSite = useCallback(() => {
    runDashboardUnlockSite({ actions: siteSetupActions, siteScaleLocked });
  }, [siteSetupActions, siteScaleLocked]);

  const handleStartBlankSite = useCallback(() => {
    runDashboardStartBlankSite({ actions: siteSetupActions });
  }, [siteSetupActions]);

  const handleStartSiteBoundaryDraw = useCallback(() => {
    runDashboardStartSiteBoundaryDraw({
      actions: siteSetupActions,
      height: parsePositiveNumber(lotHeight),
      unlockSite: handleUnlockSite,
      width: parsePositiveNumber(lotWidth),
      siteScaleLocked,
    });
  }, [handleUnlockSite, lotHeight, lotWidth, siteScaleLocked, siteSetupActions]);

  useEffect(() => {
    if (siteScaleLocked) return;
    if (!viewportFootprint?.widthFt || !viewportFootprint?.heightFt) return;
    const nextWidth = viewportFootprint.widthFt;
    const nextHeight = viewportFootprint.heightFt;
    const last = lastViewportSyncRef.current;
    if (last && Math.abs(last.w - nextWidth) < 1 && Math.abs(last.h - nextHeight) < 1) {
      return;
    }
    lastViewportSyncRef.current = { w: nextWidth, h: nextHeight };
  }, [siteScaleLocked, viewportFootprint]);

  useEffect(() => {
    if (addressSuggestTimeoutRef.current) {
      window.clearTimeout(addressSuggestTimeoutRef.current);
    }
    const trimmed = siteAddress.trim();
    if (!trimmed || trimmed.length < 4) {
      setAddressSuggestions([]);
      return;
    }
    addressSuggestTimeoutRef.current = window.setTimeout(() => {
      const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
      const fallbackToMapbox = () => {
        if (!mapboxToken) {
          setAddressSuggestions([]);
          return;
        }
        const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(trimmed)}.json?access_token=${mapboxToken}&autocomplete=true&limit=5`;
        fetch(url)
          .then((resp) => resp.json())
          .then((data) => {
            const features = Array.isArray(data?.features) ? data.features : [];
            const suggestions = features
              .map((feature: { center?: [number, number]; place_name?: string }) => {
                if (!feature?.center || feature.center.length < 2) return null;
                return {
                  lat: feature.center[1],
                  lng: feature.center[0],
                  display_name: feature.place_name || trimmed,
                  provider: "mapbox",
                };
              })
              .filter(Boolean) as AddressSuggestion[];
            setAddressSuggestions(suggestions);
          })
          .catch(() => {
            setAddressSuggestions([]);
          });
      };
      if (!token) {
        fallbackToMapbox();
        return;
      }
      void postJson<AddressSuggestion>(
        "/api/geocode",
        { address: trimmed },
        { token },
      )
        .then((result) => {
          if (hasAddressCoordinates(result)) {
            setAddressSuggestions([result]);
          } else if (result?.blocked || result?.status) {
            setAddressSuggestions([]);
          } else {
            fallbackToMapbox();
          }
        })
        .catch(() => {
          fallbackToMapbox();
        });
    }, 350);
    return () => {
      if (addressSuggestTimeoutRef.current) {
        window.clearTimeout(addressSuggestTimeoutRef.current);
      }
    };
  }, [siteAddress, token]);

  const runAutoExistingConditionsAfterSiteLock = useDashboardAutoExistingConditions({
    assumedTerrainSlopePct,
    autoExistingRunKeyRef,
    buildingPlacements,
    configuredLocalGisProviderCount: configuredLocalGisProviders.length,
    currentProject,
    handleGenerateSystemRef,
    hasTerrainSource,
    hasVerifiedSurveyControl,
    lotHeight,
    lotWidth,
    payloadPreview,
    projectId,
    saveProject,
    setAssumedTerrainSlopePct,
    setAutoExistingConditionsStatus,
    setCurrentProject,
    setOnlineDiscoveryBusy,
    setSurveySlopeEstimate,
    setUseSurveyForGrading,
    siteAddress,
    siteInputs,
    surveySlopeEstimate,
    token,
    updateProjectStatus,
    viewportCenter,
    viewportFootprint,
  });

  const handleApplySite = useDashboardApplySiteAction({
    applyingSiteRef,
    autoFitSite,
    buildingPlacements,
    currentProject,
    hasSiteBoundary,
    lastAppliedSiteRef,
    lotHeight,
    lotWidth,
    payloadPreview,
    runAutoExistingConditionsAfterSiteLock,
    saveProject,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setBuildingPlacements,
    setCurrentProject,
    setFitToSiteRequest,
    setLeftSidebarOpen,
    setRenderedSidePanel,
    setShowSiteBounds,
    setSidePanelVisible,
    setSiteScaleLocked,
    setSiteSelectionMode,
    siteScaleLocked,
    updateProjectStatus,
    viewportCenter,
    viewportFootprint,
  });

  const runSelectedDetections = useDashboardSelectedDetectionActions({
    assumedTerrainSlopePct,
    detectionChoices,
    handleAnalyzeImageFeatures,
    handleGenerateSystemRef,
    hasTerrainSource,
    mapSnapshotPath,
    setAssumedTerrainSlopePct,
    setStatusMessage,
    setSurveySlopeEstimate,
    setUseSurveyForGrading,
    siteScaleLocked,
    surveySlopeEstimate,
  });

  useEffect(() => {
    if (!siteScaleLocked) return;
    const hasSite = buildingPlacements.some((item) => item.type === "site");
    if (!hasSite) return;
    setFitToSiteRequest((value) => value + 1);
  }, [activeSidePanel, buildingPlacements, previewHeightPx, siteScaleLocked]);

  const saveSiteAddress = useDashboardSiteAddressAction({
    autoExistingRunKeyRef,
    clearGeneratedPreview,
    configuredLocalGisProviderCount: configuredLocalGisProviders.length,
    currentProject,
    localGisProviderRegistry,
    payloadPreview,
    projectLoadRequestRef,
    saveProject,
    selectedAddressSuggestion,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setAddressSuggestions,
    setAutoExistingConditionsStatus,
    setBuildingPlacements,
    setCurrentProject,
    setOnlineDiscoveryBusy,
    setPreviewQuality,
    setSelectedAddressSuggestion,
    setShowSiteBounds,
    setSiteAddress,
    setSiteScaleLocked,
    setSiteSelectionMode,
    setViewportCenter,
    siteAddress,
    siteScaleLocked,
    token,
    updateProjectStatus,
  });

  const { handleCreateCenteredSiteFromSetup, handleMapCenter } = useDashboardSiteSetupUtilityActions({
    autoFitSite,
    clearGeneratedPreview,
    currentProject,
    lastAppliedSiteRef,
    lotHeight,
    lotWidth,
    payloadPreview,
    saveProject,
    saveSiteAddress,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setAutoExistingConditionsStatus,
    setFitToSiteRequest,
    setLotHeight,
    setLotWidth,
    setPreviewInteraction,
    setPreviewMode,
    setPreviewQuality,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setShowSiteBounds,
    setSidePanelVisible,
    setSiteSelectionMode,
    setStatusMessage,
    siteAddress,
    siteAddressInputRef,
    updateProjectStatus,
    viewportCenter,
  });

  const requestPreview = async (
    payload: PreviewRequestPayload,
    options?: { silent?: boolean; track?: boolean },
  ) => {
    if (!token) return;
    const workspaceGeneration = projectLoadRequestRef.current;
    if (effectiveDemoWorkspaceEnabled || isSeededDemoProjectId(payload.project_id)) {
      return;
    }
    if (!hasPreviewablePlanResult(payload.result ?? backendResult)) {
      return;
    }
    if (options?.track) {
      setPreviewRefreshing(true);
      setPreviewRefreshNote((prev) => prev || "Refreshing preview...");
    }
    const previewPayload = {
      ...payload,
      preview_quality: previewQuality,
      label_density: previewLabelDensity,
      render_labels: previewInteraction !== "static" || previewQuality === "high",
      preview_mode: "production",
      preview_layers: previewLayerList,
    };
    try {
      const data = await postJson<PreviewResponse>("/api/preview", previewPayload, {
        token,
      });
      if (projectLoadRequestRef.current !== workspaceGeneration) return;
      setPlanPreviewUrl(data.preview_image_data_url);
      setPlanPreviewProjectId(projectId || currentProject?.project_id || null);
      setPlanPreviewSummary(data.summary ?? null);
      setPlanPreviewAnnotations(data.preview_annotations ?? null);
      if (!options?.silent) {
        setStatusMessage("Plan preview generated.");
      }
    } finally {
      if (options?.track && projectLoadRequestRef.current === workspaceGeneration) {
        setPreviewRefreshing(false);
        setPreviewRefreshNote(null);
      }
    }
  };

  const requestPreviewInBackground = (
    payload: PreviewRequestPayload,
    options?: { loadingMessage?: string; successMessage?: string; silentStatus?: boolean; track?: boolean },
  ) => {
    if (!token) return;
    if (options?.loadingMessage && !options?.silentStatus) {
      setStatusMessage(options.loadingMessage);
    }
    void requestPreview(payload, { silent: true, track: options?.track })
      .then(() => {
        if (options?.successMessage && !options?.silentStatus) {
          setStatusMessage(options.successMessage);
        }
      })
      .catch((error) => {
        if (!options?.silentStatus) {
          setStatusMessage(
            error instanceof Error ? error.message : "Preview generation failed.",
          );
        }
        if (options?.track) {
          setPreviewRefreshing(false);
          setPreviewRefreshNote(null);
        }
      });
  };

  useEffect(() => {
    if (planPreviewProjectId && projectId && planPreviewProjectId !== projectId) {
      debugLog("discard-preview-project-mismatch", {
        planPreviewProjectId,
        projectId,
      });
      clearGeneratedPreview();
      return;
    }
    if (!buildingPlacements.length && !detectedPlacements.length && planPreviewUrl && !backendResult) {
      debugLog("discard-preview-empty-canonical");
      clearGeneratedPreview();
    }
  }, [
    backendResult,
    buildingPlacements.length,
    clearGeneratedPreview,
    debugLog,
    detectedPlacements.length,
    planPreviewProjectId,
    planPreviewUrl,
    projectId,
  ]);

  useEffect(() => {
    if (!token || !backendResult) return;
    const finalPlan =
      backendResult?.final_plan && typeof backendResult.final_plan === "object"
        ? backendResult.final_plan
        : {};
    const finalMeta =
      finalPlan?.meta && typeof finalPlan.meta === "object" ? finalPlan.meta : {};
    const actions = Array.isArray(finalPlan?.actions)
      ? finalPlan.actions.filter((item: unknown) => item && typeof item === "object")
      : [];
    const phaseCheckpoints =
      finalMeta?.phase_checkpoints && typeof finalMeta.phase_checkpoints === "object"
        ? finalMeta.phase_checkpoints
        : {};
    const runtimeCheckpoint =
      finalMeta?.runtime_phase_checkpoint && typeof finalMeta.runtime_phase_checkpoint === "object"
        ? finalMeta.runtime_phase_checkpoint
        : {};
    const jobProgress =
      backendResult?.job_progress && typeof backendResult.job_progress === "object"
        ? backendResult.job_progress
        : {};
    const hasRecoverablePreviewState =
      actions.length > 0 ||
      Object.keys(phaseCheckpoints).length > 0 ||
      Object.keys(runtimeCheckpoint).length > 0 ||
      Boolean(jobProgress.stage);

    if (!hasRecoverablePreviewState) return;

    const recoveryKey = JSON.stringify({
      projectId,
      actionCount: actions.length,
      phaseKeys: Object.keys(phaseCheckpoints),
      checkpointStage: String(runtimeCheckpoint.stage_name || ""),
      jobStage: String(jobProgress.stage || ""),
      stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
    });

    if (previewRecoveryKeyRef.current === recoveryKey) return;
    previewRecoveryKeyRef.current = recoveryKey;

    requestPreviewInBackground(
      {
        project_id: projectId || currentProject?.project_id || null,
        result: backendResult,
        filename_stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
      },
      {
        silentStatus: true,
      },
    );
  }, [token, backendResult, projectId, fileName, currentProject?.name, siteName]);

  const { loadProjectResultInBackground } = useDashboardProjectResultLoader({
    applyBackendResult,
    backendResult,
    currentProject,
    fileName,
    planPreviewUrl,
    projectId,
    projectLoadRequestRef,
    projectResultLoadRequestRef,
    requestPreviewInBackground,
    resolvedProjectIdRef,
    setBackendResult,
    setPlanPreviewSummary,
    setPlanPreviewUrl,
    setStatusMessage,
    systemStatuses,
    token,
    visibleActiveJob,
  });
  loadProjectResultInBackgroundRef.current = loadProjectResultInBackground;

  useEffect(() => {
    if (!token) return;
    const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
    if (activeStatus !== "awaiting_approval") return;
    const targetProjectId =
      visibleActiveJob?.project_id || currentProject?.project_id || projectId || "";
    if (!targetProjectId) return;

    const targetProject = {
      project_id: targetProjectId,
      name: currentProject?.name || siteName || "Untitled Project",
    } as ProjectRecord;

    loadProjectResultInBackground(targetProject);
    const interval = window.setInterval(() => {
      loadProjectResultInBackground(targetProject);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [
    token,
    planPreviewUrl,
    visibleActiveJob?.status,
    visibleActiveJob?.project_id,
    currentProject?.project_id,
    currentProject?.name,
    projectId,
    siteName,
  ]);

  const ensureSiteLocked = useCallback(
    (action: string) => {
      if (siteScaleLocked) return true;
      const alignmentLocked =
        currentProject?.project_input?.meta?.site_inputs &&
        typeof currentProject.project_input.meta.site_inputs === "object"
          ? currentProject.project_input.meta.site_inputs.site_alignment_locked
          : null;
      if (alignmentLocked === true) return true;
      askClarification(
        "Please lock the site alignment before running this step. Do you want me to lock the site now?",
        "lock_site_required",
        { action },
      );
      return false;
    },
    [askClarification, siteScaleLocked],
  );

  const pickBestLowPoint = useCallback(() => {
    if (drainageLowPoints.length) {
      let best = drainageLowPoints[0];
      for (let i = 1; i < drainageLowPoints.length; i += 1) {
        const current = drainageLowPoints[i];
        const bestZ = Number.isFinite(best.z) ? best.z : Number.POSITIVE_INFINITY;
        const currentZ = Number.isFinite(current.z) ? current.z : Number.POSITIVE_INFINITY;
        if (currentZ < bestZ) {
          best = current;
        }
      }
      return best ?? null;
    }
    const lot = resolveLotBounds();
    if (lot.w && lot.h) {
      return {
        x: lot.x + lot.w / 2,
        y: lot.y + lot.h / 2,
        z: 0,
      };
    }
    return null;
  }, [drainageLowPoints, resolveLotBounds]);

  const drainageIssueApplyLabel = getDashboardDrainageIssueApplyLabel;
  const getIssueGuidance = getDashboardDrainageIssueGuidance;
  const canApplyDrainageIssue = canApplyDashboardDrainageIssue;

  const runDrainageAutofix = useDashboardDrainageAutofix({
    appendChatMessage,
    buildPayloadFromOverrides,
    currentProjectId: currentProject?.project_id,
    drainageMaxSlopeAdjust,
    ensureSiteLocked,
    executePlanAction,
    projectId,
    setActiveJobId,
    setStatusMessage,
    setSystemStatuses,
    token,
    withReactiveRerunContext,
  });

  const {
    generatePendingPlacementLabels,
    generatePendingPlacementObjects,
    openGenerateBlockerPanel,
    persistFlowMetadata,
  } = useDashboardGenerateFlowCoordinator({
    buildingPlacements,
    currentProject,
    panelOpenProbeRef,
    payloadPreview,
    saveProject,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setCadToolRequest,
    setCurrentProject,
    setLayerManagerOpen,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setRightRailCollapsed,
    sidePanelCloseTimeoutRef,
  });

  const handleGenerateSystem = useDashboardGenerateSystemAction({
    appendChatMessage,
    askClarification,
    assumedTerrainSlopePct,
    autoSiteContextFlowSummary,
    buildPayloadFromOverrides,
    createGenerateConceptObjects,
    currentGenerateLayoutContext,
    effectiveDemoWorkspaceEnabled,
    ensureSiteLocked,
    executePlanAction,
    getGeneratePreflightBlockers,
    handleOpenSidePanel: openGenerateBlockerPanel,
    hasAssumedTerrainSlope,
    hasSiteBoundary,
    minSlopePct,
    pendingPlacementLabels: generatePendingPlacementLabels,
    pendingPlacementObjects: generatePendingPlacementObjects,
    persistFlowMetadata,
    projectId,
    reactiveChangedSystems,
    reactiveValidation,
    recordRecentChange,
    resolveLotBounds,
    setGenerateFlowSummary,
    setSystemStatuses,
    siteHasGeocode: Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng),
    surveyFileName,
    surveySlopePercent: surveySlopeEstimate?.slope_percent,
    token,
    updateProjectStatus,
    useSurveyForGrading,
    withReactiveRerunContext,
  });

  useEffect(() => {
    handleGenerateSystemRef.current = handleGenerateSystem;
  }, [handleGenerateSystem]);

  const handleApplyDrainageIssue = useDashboardDrainageIssueApplyAction({
    buildingPlacements,
    clearGeneratedPreview,
    drainageAllowSlopeAdjust,
    drainageConnectOrphans,
    drainageForcedInlets,
    pickBestLowPoint,
    resolveLotBounds,
    runDrainageAutofix,
    setBuildingPlacements,
    setDrainageAllowSlopeAdjust,
    setDrainageConnectOrphans,
    setDrainageForcedInlets,
    setExternalRectUndo,
    setFocusObjectId,
    setStatusMessage,
  });

  const queuePreviewRefresh = (reason: string) => {
    runDashboardQueuePreviewRefresh({
      previewRefreshIntentRef,
      reason,
      token,
    });
  };

  const handlePreviewPlan = async () => {
    await runDashboardPreviewPlan({
      artifactPayload,
      requestPreview,
      setBusy,
      setStatusMessage,
      token,
    });
  };

  const handleExplainPlan = () => {
    runDashboardExplainPlan({
      appendChatMessage,
      currentExplanation,
      currentManualFailures,
      currentTruthAudit,
      issues,
      selectedRunMessage: typeof selectedRun?.message === "string" ? selectedRun.message : "",
      setStatusMessage,
    });
  };

  const handleRunFix = () => {
    void runOrchestrator("fix");
  };

  const handleRunImprove = () => {
    void runOrchestrator("improve");
  };

  const { resetWorkspaceState } = useDashboardWorkspaceReset({
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
  });
  resetWorkspaceStateRef.current = resetWorkspaceState;

  const { handleDeleteProject, handleNewProject } = useDashboardProjectActions({
    autosaveSuspendRef,
    chatAutosaveTimeoutRef,
    chatMessagesRef,
    controlAutosaveTimeoutRef,
    currentProject,
    debugLog,
    draftProjectPromiseRef,
    projectId,
    projectLoadRequestRef,
    projectResultLoadRequestRef,
    projects,
    refreshProjects,
    removeProjectSummary,
    resetWorkspaceState,
    resolvedProjectIdRef,
    restoredActiveProjectRef,
    rotationSaveTimeoutRef,
    scaleSaveTimeoutRef,
    setActiveJobId,
    setActiveSidePanel,
    setAssumptions,
    setBuildingCount,
    setBuildingDepth,
    setBuildingWidth,
    setChatMessages,
    setCurrentProject,
    setDrainage,
    setFileName,
    setFileNameAuto,
    setGrading,
    setImageName,
    setIssues,
    setLeftSidebarOpen,
    setLotHeight,
    setLotWidth,
    setMapAnalysis,
    setMapSnapshotPath,
    setMaxAdaCrossSlopePct,
    setMaxParkingSlopePct,
    setMaxRoadGradePct,
    setMinSlopePct,
    setParkingAdaAisleWidth,
    setParkingAdaCount,
    setParkingAisleWidth,
    setParkingAngle,
    setParkingCompactCount,
    setParkingCompactWidth,
    setParkingCount,
    setParkingLoading,
    setParkingStallDepth,
    setParkingStallWidth,
    setPipeMinSlopePct,
    setPlanSheetSet,
    setProjectDrawerNotice,
    setProjectId,
    setProjectType,
    setPrompt,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setRoads,
    setSelectedRunId,
    setSetback,
    setSidePanelVisible,
    setSiteName,
    setSiteNameAuto,
    setSurveyDiagnostics,
    setSurveyFileName,
    setSurveyPoints,
    setSurveyPreviewPoints,
    setSurveySlopeEstimate,
    setSourceEffectRows,
    setSystemStatuses,
    setUnits,
    setUploadedImageApiUrl,
    setUploadedImagePreviewUrl,
    setUseSurveyForGrading,
    setUtilities,
    setWorkspaceChromeMinimized,
    setWorkspaceRestoreState,
    suppressProjectAutoLoadRef,
    token,
    updateProjectStatus,
  });

  const {
    downloadBlob,
    getExportBlockReason,
    handleArtifactDownload,
    handleExportDxf,
    handleExportQuantityReviewReport,
    handleExportReport,
  } = useMemo(
    () =>
      createDashboardExportActions({
        appendChatMessage,
        artifactPayload,
        backendResultPresent: Boolean(backendResult),
        busy,
        costEstimate,
        currentPlanMeta,
        currentProject,
        projectId,
        quantityExplain,
        quantityRows,
        setActiveJobId,
        setActiveSidePanel,
        setActiveWorkspaceMode,
        setBusy,
        setExportActionMessage,
        setStatusMessage,
        siteName,
        token,
        visibleActiveJob,
      }),
    [
      appendChatMessage,
      artifactPayload,
      backendResult,
      busy,
      costEstimate,
      currentPlanMeta,
      currentProject,
      projectId,
      quantityExplain,
      quantityRows,
      siteName,
      token,
      visibleActiveJob,
    ],
  );

  const {
    previewReview,
    previewBlockedReasons,
    previewRunningPhase,
    previewNextPendingPhase,
  } = usePreviewReview({ currentPlanMeta, planPreviewSummary });
  const {
    handleCancelActiveJob,
    handleCancelJobById,
    handleContinueActiveJob,
    handleResumeJob,
    handleRetryJob,
  } = useDashboardJobActions({
    activeJobId,
    appendChatMessage,
    directRunAbortRef,
    previewNextPendingPhase,
    previewRunningPhase,
    queuePreviewRefresh,
    refreshJobs,
    runSubmissionRef,
    setActiveJobId,
    setActivePlanTool,
    setApprovalError,
    setApprovalInFlight,
    setApprovalPendingJobId,
    setApprovalPhaseLabel,
    setBusy,
    setJobs,
    setJobToasts,
    setSelectedJobId,
    setStatusMessage,
    token,
    visibleActiveJob,
  });
  const { handleSelectJob, loadJob } = useDashboardJobLoader({
    activeJobProjectSyncRef,
    appendChatMessage,
    applyBackendResult,
    applyProjectInput,
    autosaveSuspendRef,
    currentProject,
    fileName,
    handleArtifactDownload,
    lastJobPartialResultRefreshRef,
    lastJobPhaseSignatureRef,
    lastJobStatusRef,
    lastProjectResultRefreshRef,
    loadProjectResultInBackground,
    projectId,
    projectLoadRequestRef,
    requestPreviewInBackground,
    resolvedProjectIdRef,
    setActiveJobId,
    setCurrentProject,
    setJobs,
    setJobsPanelStatusMessage,
    setProjectId,
    setSiteName,
    setStatusMessage,
    siteName,
    token,
    upsertProjectSummary,
  });
  loadJobRef.current = loadJob;

  const handleSmartFixAction = (recommendation: SmartFixRecommendation) => {
    const action = recommendation.ui_action ?? {};
    const actionType = String(action.type || "");
    if (actionType === "open_panel" && action.panel) {
      handleOpenSidePanel(action.panel as SidePanelKey);
      setStatusMessage(recommendation.one_action_needed_next || "Opened the recommended panel.");
      return;
    }
    if (actionType === "run_fix") {
      void handleRunFix();
      return;
    }
    if (actionType === "generate_system") {
      const target = String(action.target || "");
      const mappedTarget = target === "roadway" ? "roads" : target;
      if (["roads", "parking", "grading", "drainage", "utilities", "full"].includes(mappedTarget)) {
        void handleGenerateSystem(mappedTarget as SystemGenerationTarget);
        return;
      }
    }
    if (actionType === "export_report") {
      void handleExportReport();
      return;
    }
    if (actionType === "export_dxf") {
      void handleExportDxf();
      return;
    }
    if (actionType === "chat_prompt" && action.prompt) {
      const nextPrompt = String(action.prompt);
      setPrompt(nextPrompt);
      appendChatMessage("assistant", `I need you to confirm or send: ${nextPrompt}`, "status");
      setStatusMessage("Smart Fix needs a chat confirmation.");
      return;
    }
    const missing = recommendation.missing_user_input_or_source;
    appendChatMessage(
      "assistant",
      missing
        ? `I need exactly this from you: ${missing}.`
        : recommendation.one_action_needed_next || "This blocker needs manual review before Civora can continue.",
      "status",
    );
  };

  useJobPolling({
    token,
    activeJobId,
    visibleActiveJob,
    visibleActiveJobStale,
    onLoadJob: loadJob,
    onRefreshJobs: refreshJobs,
    setJobClockMs,
    setActiveJobId,
    currentProjectActiveJob,
    onStatusMessage: (message) => {
      setStatusMessage(message);
    },
    lastStaleJobWarningRef,
  });

  useEffect(() => {
    if (!workflowRuns.length) {
      setSelectedRunId("");
      return;
    }
    setSelectedRunId((current) =>
      current && workflowRuns.some((run) => run.run_id === current)
        ? current
        : workflowRuns[0].run_id,
    );
  }, [workflowRuns]);

  // Intentionally avoid auto-loading the last project on initial load so the
  // workspace starts clean and only loads a project when the user selects it.

  const {
    addPlanSheetAnnotation,
    getPlanSheetBlockers,
    handleCreateReviewSheet,
    handleMakeReviewPackage,
    handlePlanSheetAddDetailBlock,
    handlePlanSheetAddNote,
    handlePlanSheetAddReference,
    handlePlanSheetAddRevision,
    handlePlanSheetAddTable,
    handlePlanSheetAddViewport,
    handlePlanSheetExportJson,
    handlePlanSheetExportPdf,
    handlePlanSheetGrayscaleToggle,
    handlePlanSheetScaleChange,
    handlePlanSheetTitleBlockUpdate,
    handlePlanSheetViewportDelete,
    handlePlanSheetViewportLayerToggle,
    handlePlanSheetViewportScaleLockToggle,
    handlePlanSheetViewportUpdate,
  } = useMemo(
    () =>
      createDashboardPlanSheetActions({
        analysisIssues,
        appendChatMessage,
        autoSiteContextFlowSummary,
        backendResult,
        currentProject,
        downloadBlob,
        issues,
        persistFlowMetadata,
        planPreviewUrl,
        planSheetSet,
        previewBlockedReasons,
        recordRecentChange,
        reviewPackageFlowSummary,
        setActiveSidePanel,
        setActiveWorkspaceMode,
        setPlanSheetSet,
        setReviewPackageFlowSummary,
        setStatusMessage,
        siteName,
        updateProjectStatus,
      }),
    [
      analysisIssues,
      appendChatMessage,
      autoSiteContextFlowSummary,
      backendResult,
      currentProject,
      downloadBlob,
      issues,
      persistFlowMetadata,
      planPreviewUrl,
      planSheetSet,
      previewBlockedReasons,
      recordRecentChange,
      reviewPackageFlowSummary,
      siteName,
      updateProjectStatus,
    ],
  );
  const gatingPhaseKey =
    String(visibleActiveJob?.status || "").toLowerCase() === "awaiting_approval"
      ? previewRunningPhase?.key || previewNextPendingPhase?.key
      : null;

  useEffect(() => {
    const phaseLabel =
      previewRunningPhase?.label ||
      String(visibleActiveJob?.stage || "").trim() ||
      String((currentPlanMeta?.runtime_phase_checkpoint as { stage_name?: string } | undefined)?.stage_name || "")
        .trim();
    currentPhaseLabelRef.current = phaseLabel ? toReadableLabel(phaseLabel) : "";
  }, [previewRunningPhase?.label, visibleActiveJob?.stage, currentPlanMeta]);

  const previewLayersEffective = useMemo(
    () => applyPreviewLayerGating(previewLayers, gatingPhaseKey),
    [gatingPhaseKey, previewLayers],
  );

  const previewLayerList = useMemo(
    () => buildPreviewLayerList(previewLayersEffective),
    [previewLayersEffective],
  );

  useEffect(() => {
    if (!token || !hasPreviewablePlanResult(backendResult)) {
      if (previewAutoRefreshTimeoutRef.current !== null) {
        window.clearTimeout(previewAutoRefreshTimeoutRef.current);
        previewAutoRefreshTimeoutRef.current = null;
      }
      return;
    }
    const intent = previewRefreshIntentRef.current;
    if (intent) {
      previewRefreshIntentRef.current = null;
      if (previewAutoRefreshTimeoutRef.current !== null) {
        window.clearTimeout(previewAutoRefreshTimeoutRef.current);
        previewAutoRefreshTimeoutRef.current = null;
      }
      setPreviewRefreshNote(intent.reason);
      requestPreviewInBackground(artifactPayload, {
        silentStatus: true,
        track: intent.track,
      });
      return;
    }
    if (previewAutoRefreshTimeoutRef.current !== null) {
      window.clearTimeout(previewAutoRefreshTimeoutRef.current);
    }
    previewAutoRefreshTimeoutRef.current = window.setTimeout(() => {
      previewAutoRefreshTimeoutRef.current = null;
      const startedAt = markCivoraInteraction();
      requestPreviewInBackground(artifactPayload, { silentStatus: true });
      measureCivoraInteractionAfterPaint("preview.background_refresh.debounced", startedAt, {
        mode: previewMode,
        quality: previewQuality,
      });
    }, 450);
    return () => {
      if (previewAutoRefreshTimeoutRef.current !== null) {
        window.clearTimeout(previewAutoRefreshTimeoutRef.current);
        previewAutoRefreshTimeoutRef.current = null;
      }
    };
  }, [
    previewLayerList,
    token,
    artifactPayload,
    backendResult,
    previewMode,
    previewQuality,
  ]);

  useEffect(() => {
    setPreviewLabelDensity(previewQuality === "high" ? "high" : "standard");
  }, [previewQuality]);

  const lotBounds = resolveLotBounds();
  const {
    hasGradingSurface,
    preview3DEffectiveItems,
    usingAnnotation3D,
  } = useMemo(
    () =>
      buildDashboardPreview3DView({
        backendResult,
        buildingPlacements,
        cadEntityPreview,
        lot: lotBounds,
        planPreviewAnnotations,
        previewLayersEffective,
        sourceConfidenceByObjectId,
      }),
    [
      backendResult,
      buildingPlacements,
      cadEntityPreview,
      lotBounds,
      planPreviewAnnotations,
      previewLayersEffective,
      sourceConfidenceByObjectId,
    ],
  );
  const {
    gradingEarthworkUx,
    gradingSourceSummary,
    siteDerivedView,
  } = useMemo(
    () =>
      buildDashboardSiteGradingView({
        lotBounds,
        lotWidth,
        lotHeight,
        mapSnapshotPath,
        buildingPlacements,
        drainageSummary,
        mapAnalysis,
        detectedPlacements,
        detectionConfidenceFilter,
        projects,
        siteWarningAcres: SITE_WARNING_ACRES,
        siteGradingHardBlockAcres: SITE_GRADING_HARD_BLOCK_ACRES,
        siteInputs,
        gradingSummary,
        cutFillNet,
        managerMetrics,
        gradingBlocker,
        gradingResultSummary,
        hasGradingSurface,
      }),
    [
      buildingPlacements,
      cutFillNet,
      detectedPlacements,
      detectionConfidenceFilter,
      drainageSummary,
      gradingBlocker,
      gradingResultSummary,
      gradingSummary,
      hasGradingSurface,
      lotBounds,
      lotHeight,
      lotWidth,
      managerMetrics,
      mapAnalysis,
      mapSnapshotPath,
      projects,
      siteInputs,
    ],
  );
  const {
    siteTooLargeForWarning,
    siteTooLargeForGrading,
    missingSite,
    missingImage,
    placedObjects,
    pendingPlacementObjects,
    pendingPlacementLabels,
    hasBasinObject,
    hasBasinPlaced,
    hasUtilityConnectionObject,
    hasUtilityConnectionPlaced,
    siteSizeSet,
    drainageSurfaceSummary,
    mapAnalysisCounts,
    filteredDetectedPlacements,
    sortedProjects,
  } = siteDerivedView;
  useEffect(() => {
    if (debugGradingFixtureLoaded) return;
    if (typeof window === "undefined") return;
    if (process.env.NODE_ENV === "production") return;
    const params = new URLSearchParams(window.location.search);
    if (!params.has("debugGradingBlocked")) return;
    const lotW = lotBounds.w || 200;
    const lotH = lotBounds.h || 200;
    const source = { x: lotBounds.x + lotW * 0.2, y: lotBounds.y + lotH * 0.2 };
    const target = { x: lotBounds.x + lotW * 0.8, y: lotBounds.y + lotH * 0.8 };
    const blocker = { x: lotBounds.x + lotW * 0.5, y: lotBounds.y + lotH * 0.5, approximate: true };
    const fixZone = {
      x: lotBounds.x + lotW * 0.25,
      y: lotBounds.y + lotH * 0.25,
      w: lotW * 0.5,
      h: lotH * 0.5,
      approximate: true,
    };
    const fixture = {
      code: "DRAINAGE_BLOCKED_BY_GRADING",
      severity: "warning" as const,
      message: "Proposed grading blocks flow paths that were reachable on existing terrain.",
      context: {
        explanation: "Proposed grading blocks flow paths that would otherwise reach the basin.",
        reason: "proposed_surface_blocks_flow",
        best_next_fix: "Introduce a grading swale toward the basin or lower the ridge between inlet and basin.",
        suggested_actions: [
          "Introduce a grading swale toward the basin.",
          "Lower local ridge between inlet and basin.",
          "Adjust pad edges to restore flow.",
        ],
        blocker_type: "ridge",
        source_point: source,
        blocked_target: target,
        blocker_location: blocker,
        suggested_fix_zone: fixZone,
        approximate: true,
      },
    };
    setIssues((prev) => {
      if (prev.some((issue) => (issue.code ?? "").toUpperCase() === "DRAINAGE_BLOCKED_BY_GRADING")) {
        return prev;
      }
      return [...prev, fixture];
    });
    setDebugGradingFixtureLoaded(true);
  }, [debugGradingFixtureLoaded, lotBounds.h, lotBounds.w, lotBounds.x, lotBounds.y]);
  const selectedAccessIssue = useMemo(
    () => analysisIssues.find((issue) => issue.id === analysisSelectedIssueId) ?? null,
    [analysisIssues, analysisSelectedIssueId],
  );
  const systemEvidenceView = useDashboardSystemEvidenceView({
    buildingPlacements,
    issues,
    siteTooLargeForGrading,
    hasAppliedAddress,
    appliedAddressLabel,
    hasLocationEvidence,
    hasVerifiedSurveyControl,
    coordinateSystem: (siteInputs as { coordinate_system?: string } | null)?.coordinate_system || "",
    hasTerrainSource,
    mapAnalysisSuccess: Boolean(mapAnalysis?.success),
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
    onlineSourceLookupLabel,
    missingSite,
    siteScaleLocked,
    hasStandardsEvidence,
    onlineSourceLookupUnavailable,
    hasAssumedTerrainSlope,
    hasBasinPlaced,
    hasBasinObject,
    utilities,
    hasUtilityConnectionPlaced,
    hasUtilityConnectionObject,
    systemStatuses,
  });
  const {
    confirmedObjectCounts,
    hasHardSystemBlock,
    existingConditionRows,
    systemBlockerContext,
    systemReadinessRows,
  } = systemEvidenceView;
  const exportBlockReason = getExportBlockReason();
  const civil3DWorkflowBlockers = useMemo(
    () =>
      buildDashboardCivil3DWorkflowBlockers({
        blockerContext: systemBlockerContext,
        previewBlockedReasons,
        issues,
      }),
    [issues, previewBlockedReasons, systemBlockerContext],
  );
  const workflowActionHints = useMemo(
    () =>
      buildDashboardWorkflowActionHints({
        hasLocationEvidence,
        siteSizeSet,
        buildingPlacements,
        siteScaleLocked,
        existingConditionRows,
        placedObjectCount,
        systemReadinessRows,
        exportBlockReason,
      }),
    [
      buildingPlacements,
      existingConditionRows,
      exportBlockReason,
      hasLocationEvidence,
      placedObjectCount,
      siteScaleLocked,
      siteSizeSet,
      systemReadinessRows,
    ],
  );
  const capabilityAuditRows = useMemo<CapabilityExposure[]>(() => buildDashboardCapabilityAuditRows({
    currentPlanMeta: currentPlanMeta as Record<string, unknown>,
    manualFields: currentProject?.project_input?.manual_fields as Record<string, unknown> | undefined,
    buildingPlacements,
    existingConditionRows,
    backendResultPresent: Boolean(backendResult),
    hasLocationEvidence,
    hasVerifiedSurveyControl,
    mapAnalysis,
    placedObjectCount,
    quantityRowCount: quantityRows.length,
    reactiveChangedSystems,
    reactiveRerunSummary,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
    exportBlockReason,
  }), [
    backendResult,
    buildingPlacements,
    currentPlanMeta,
    currentProject?.project_input?.manual_fields,
    existingConditionRows,
    exportBlockReason,
    hasLocationEvidence,
    hasVerifiedSurveyControl,
    mapAnalysis,
    placedObjectCount,
    quantityRows.length,
    reactiveChangedSystems,
    reactiveRerunSummary,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
  ]);
  const systemHealthItems = useMemo(
    () =>
      buildDashboardSystemHealthItems({
        canonicalWorkspaceBlockers,
        hasHardSystemBlock,
        hasTerrainSource,
        siteScaleLocked,
        siteTooLargeForGrading,
        systemStatuses,
      }),
    [canonicalWorkspaceBlockers, hasHardSystemBlock, hasTerrainSource, siteScaleLocked, siteTooLargeForGrading, systemStatuses],
  );
  const objectSelectionView = useMemo(
    () => buildDashboardObjectSelectionView({ buildingPlacements, activePlacementId, selectedObjectIds }),
    [activePlacementId, buildingPlacements, selectedObjectIds],
  );
  const { selectedBuilding, selectedObjectSet, selectedObjectRows, selectedObjectMeasurements, selectedObjectMeasurementSummary, hiddenObjectCount, objectManagerTypes, objectManagerLayerRows } = objectSelectionView;
  const sidePanelForRender = resolveSidePanelForRender({
    rightRailCollapsed,
    activeSidePanel,
    renderedSidePanel,
  });
  const customerTemplateSummaries = customerTemplates?.summaries ?? [];
  const activeCustomerTemplate = customerTemplates?.behavior?.active_template ?? null;
  const customerTemplateBlockerCount = Number(customerTemplates?.behavior?.blockers?.length ?? 0);
  const libraryPanelSections = buildDashboardLibraryPanelSections({
    addMenuSections: ADD_MENU_SECTIONS,
    siteObjectCatalog: SITE_OBJECT_CATALOG,
  });
  const standardsPanelCriteria = buildDashboardStandardsPanelCriteria({
    minSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    maxAdaCrossSlopePct,
    pipeMinSlopePct,
    parkingAngle,
  });
  const standardsPanelRows = capabilityAuditRows.filter(
    (item) => item.key === "standards_source_registry" || item.key === "candidate_standards_review",
  );
  const isDisciplinePanel = isDashboardDisciplinePanel(sidePanelForRender);
  const {
    handleCancelActiveTool,
    handleCloseSidePanel,
    handleCopySelectedObject,
    handleDeleteSelectedObject,
    handleOpenPanelFromDrawer,
    handleOpenSidePanel,
    handlePasteSelectedObject,
    handleRedoDraftAction,
    handleShortcutOpenDrawCanvas,
    handleShortcutOpenGenerate,
    handleShortcutOpenProjects,
    handleShortcutSaveProject,
    handleUndoDraftAction,
    handleUndoRecentChange,
    triggerCadTool,
  } = useDashboardShellShortcuts({
    activePlacementId,
    activeSidePanel,
    appendChatMessage,
    buildingPlacements,
    clearDraftUndoAction,
    currentProjectId: currentProject?.project_id,
    effectiveDemoWorkspaceEnabled,
    handleObjectManagerBulkDelete,
    handleObjectManagerCopy,
    handleObjectManagerPaste,
    handleRemoveBuilding,
    handleRestoreBuilding,
    isSeededDemoProjectId,
    lastDraftAction,
    lastDraftActionRef,
    markSystemsStale,
    objectClipboard,
    panelCloseProbeRef,
    panelOpenProbeRef,
    previewFullscreenOpen,
    projectId,
    pushRecoveryMessage,
    recordDraftRedoAction,
    recordDraftUndoAction,
    recordRecentChange,
    redoDraftAction,
    redoDraftActionRef,
    reportObjectActionBlocker,
    resolvedProjectIdRef,
    saveProject,
    selectedObjectIds,
    setActivePlacementId,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setBuildingPlacements,
    setCadToolRequest,
    setLayerManagerOpen,
    setLeftSidebarOpen,
    setObjectClipboard,
    setObjectManagerStatusMessage,
    setPendingClarification,
    setPlacementModeEnabled,
    setPreviewFullscreenOpen,
    setPreviewInteraction,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setSelectedObjectIds,
    setShortcutsOverlayOpen,
    setSidePanelVisible,
    setStatusMessage,
    setWorkspaceChromeMinimized,
    sidePanelCloseTimeoutRef,
    shortcutsOverlayOpen,
    systemsImpactedByPlacement,
    token,
    updateProjectStatus,
  });
  const tryHandleObjectIntent = useDashboardObjectCommandIntentHandler({
    addGradingDrainageReviewContext,
    appendChatMessage,
    buildingPlacements,
    ensureSiteBoundary,
    formatObjectLabel,
    handleAddObject,
    parkingCount,
    recordDraftUndoAction,
    resolveLotBounds,
    setBuildingPlacements,
    setLotHeight,
    setLotWidth,
    setParkingCount,
    setStatusMessage,
  });
  const tryHandleSheetIntent = useDashboardSheetIntentHandler({
    appendChatMessage,
    getPlanSheetBlockers,
    handleCreateReviewSheet,
    handleOpenSidePanel,
    handlePlanSheetAddNote,
    handlePlanSheetAddRevision,
    handlePlanSheetExportPdf,
    handlePlanSheetScaleChange,
    handlePlanSheetTitleBlockUpdate,
    planSheetSet,
    setActiveWorkspaceMode,
  });
  const tryHandleActionIntent = useDashboardActionIntentHandler({
    activePlacementId,
    appendChatMessage,
    buildingPlacements,
    formatObjectLabel,
    handleGenerateSystem,
    handleOpenSidePanel,
    handleRemoveBuilding,
    handleSelectPlacementTarget,
    handleUpdateBuilding,
    setActivePlacementId,
    setStatusMessage,
    workflowActionHints,
  });
  useEffect(() => {
    if (typeof window === "undefined") return;
    const panel = new URLSearchParams(window.location.search).get("debugPanel") as SidePanelKey | null;
    if (!panel || !sidePanelCopy[panel]) return;
    handleOpenSidePanel(panel);
  }, [handleOpenSidePanel]);
  const cadToolGroups = DASHBOARD_CAD_TOOL_GROUPS;
  const controlsHealthStatus = resolveDashboardControlsHealthStatus(systemStatuses);
  const panelStatus = (target: SidePanelKey): SidebarStatus =>
    resolveDashboardPanelStatus(target, {
      issuesLength: issues.length,
      analysisIssuesLength: analysisIssues.length,
      hasHardSystemBlock,
      backendResultPresent: Boolean(backendResult),
      siteScaleLocked,
      geocodePresent: Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng),
      hasTerrainSource,
      surveyPreviewPointsLength: surveyPreviewPoints.length,
      uploadedImagePreviewUrl,
      uploadedImageApiUrl,
      mapSnapshotPath,
      placedObjectCount,
      planPreviewUrl,
      buildingPlacements,
      controlsHealthStatus,
      siteTooLargeForGrading,
      hasBasinPlaced,
      systemStatuses,
      utilities,
      roads,
      minSlopePct,
      maxRoadGradePct,
      pipeMinSlopePct,
      maxAdaCrossSlopePct,
      customerTemplateBlockerCount,
      customerTemplates,
      utilityCatalog,
    });
  const sidebarModeStatus = (mode: WorkspaceMode): SidebarStatus =>
    resolveDashboardSidebarModeStatus({
      mode,
      panelStatus,
      siteScaleLocked,
      previewReleaseStatus: previewReview?.release_status,
    });
  const activePrimaryWorkflowKey = resolveActivePrimaryWorkflowKey({
    sidePanelForRender,
    activeWorkspaceMode,
  });
  const primaryWorkflowItems = buildDashboardPrimaryWorkflowItems({
    sidebarModeStatus,
    panelStatus,
    siteScaleLocked,
    placedObjectCount: placedObjects.length,
    pendingPlacementCount: pendingPlacementObjects.length,
    hasHardSystemBlock,
    controlsHealthStatus,
    systemStatuses,
    issueCount: issues.length + analysisIssues.length,
    backendResultPresent: Boolean(backendResult),
    exportBlockReason,
  });
  useWorkspaceShortcuts({
    onCancelActiveTool: handleCancelActiveTool,
    onFocusCommandInput: focusCommandInput,
    onOpenShortcuts: () => setShortcutsOverlayOpen(true),
    onSaveProject: handleShortcutSaveProject,
    onCopySelectedObject: handleCopySelectedObject,
    onPasteSelectedObject: handlePasteSelectedObject,
    onRedoDraftAction: handleRedoDraftAction,
    onUndoDraftAction: handleUndoDraftAction,
    onDeleteSelectedObject: handleDeleteSelectedObject,
    onOpenGenerate: handleShortcutOpenGenerate,
    onOpenDrawCanvas: handleShortcutOpenDrawCanvas,
    onOpenProjects: handleShortcutOpenProjects,
  });

  const supportedShortcuts = DASHBOARD_SUPPORTED_SHORTCUTS;

  const contextualToolbarTools = useDashboardContextualToolbarTools({
    activePrimaryWorkflowKey,
    handleApplySite,
    handleOpenPanelFromDrawer,
    handleStartSiteBoundaryDraw,
    handleUnlockSite,
    layerManagerOpen,
    previewInteraction,
    setLayerManagerOpen,
    setPreviewInteraction,
    setShowCalculations,
    setShowMeasurements,
    showCalculations,
    showMeasurements,
    sidePanelForRender,
    siteScaleLocked,
  });
  const {
    handleEditFloatingSelectedObject,
    handleFocusFloatingSelectedObject,
    handleOpenFloatingObjectDetails,
    selectedObjectConfidence,
  } = useDashboardFloatingObjectActions({
    appendChatMessage,
    handleOpenPanelFromDrawer,
    onCloseSidePanel: handleCloseSidePanel,
    selectedBuilding,
    setFocusObjectId,
    setMoveEditFeedback,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setStatusMessage,
    sourceConfidenceByObjectId,
  });
  const exportBlockText = getExportBlockReason();
  const {
    dashboardGuidanceStats,
    issueDiagnosticSummary,
    nextSetupAction,
    progressPanelTarget,
    progressPercent,
    progressTimelineState,
    progressTimelineSteps,
    reviewGateItems,
    setupWizardState,
    sidebarAssumptions,
    sidebarMissingInputs,
    sidebarReleaseStatus,
    sidebarStaleSystems,
    sidebarTrustScore,
    sidebarTruthItems,
  } = useDashboardShellReviewState({
    activeWorkspaceMode,
    analysisIssues,
    appliedAddressLabel,
    backendResultPresent: Boolean(backendResult),
    buildingPlacements,
    candidateAcceptedCount: candidateReviewCounts.accepted ?? 0,
    candidateItemCount: candidateReviewItems.length,
    candidatePendingCount: candidateReviewCounts.pending ?? 0,
    candidateTotalCount: candidateReviewInbox.candidate_count ?? 0,
    canonicalWorkspaceBlockers,
    currentPlanMeta,
    currentProjectId: currentProject?.project_id || projectId || null,
    currentProjectName: currentProject?.name,
    exportBlockText,
    hasAppliedAddress,
    hasAssumedTerrainSlope,
    hasBasinPlaced,
    hasHardSystemBlock,
    hasTerrainSource,
    hasVerifiedSurveyControl,
    issueReportMessage,
    issues,
    lotHeight: lotBounds.h,
    lotWidth: lotBounds.w,
    mapAnalysisSuccess: Boolean(mapAnalysis?.success),
    mapSnapshotPath,
    missingSite,
    onlineSourceLookupLabel,
    parkingCount,
    placedObjectCount,
    previewBlockedReasons,
    releaseStatusRaw: previewReview?.release_status,
    sidePanelForRender,
    siteAddress,
    siteInputAddress: siteInputs?.address,
    siteInputLat: siteInputs?.geocode?.lat,
    siteInputLng: siteInputs?.geocode?.lng,
    siteName,
    siteScaleLocked,
    siteSizeSet,
    standardsOk: panelStatus("standards") === "ok",
    surveyPreviewPointCount: surveyPreviewPoints.length,
    systemStatuses,
    trustScoreRaw: previewReview?.trust_score,
    assumptionCategories: previewReview?.assumption_categories,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
  });
  setupWizardStateRef.current = setupWizardState;
  const tryHandleInfoIntent = useDashboardInfoIntentHandler({
    activePlacementId,
    appendChatMessage,
    appliedAddressLabel,
    autoSiteContextFlowSummary,
    autoSiteContextRows,
    basinSize,
    buildingPlacements,
    canonicalWorkspaceBlockerText,
    canonicalWorkspaceBlockers,
    civil3DWorkflowBlockers,
    currentProject,
    cutFillNet,
    flowCfs,
    fullGeneratePreflightBlockers,
    generateFlowSummary,
    getExportBlockReason,
    gradingEarthworkUx,
    handleOpenSidePanel,
    hasAppliedAddress,
    hasAssumedTerrainSlope,
    hasGradingSurface,
    hasTerrainSource,
    hasVerifiedSurveyControl,
    issues,
    maxSlope,
    minSlope,
    nextSetupAction,
    onlineSourceLookupLabel,
    onlineSourceLookupUnavailable,
    pendingPlacementObjects,
    placedObjects,
    placementModeEnabled,
    planSheetSet,
    previewBlockedReasons,
    previewLayers,
    progressTimelineState,
    projectStatusSummary,
    restoreTruthLabel,
    reviewPackageFlowSummary,
    roadwayWorkbenchData,
    setActiveCivil3DWorkflowTab,
    setActiveRoadwayWorkbenchTab,
    setActiveWorkspaceMode,
    setPreviewLabelDensity,
    setPreviewLayers,
    setPreviewMode,
    siteAddress,
    sourceConfidenceRows,
    systemStatuses,
    topSmartFix,
    totalPipeLength,
    workflowActionHints,
  });
  const tryHandlePowerCommand = useDashboardPowerCommandHandler({
    activePlacementId,
    analysisIssues,
    appendChatMessage,
    autoFitSite,
    buildingPlacements,
    canonicalWorkspaceBlockers,
    clearGeneratedPreview,
    generateFlowSummary,
    handleAddObject,
    handleCreateDenseCommercialConcept,
    handleGenerateSystem,
    handleMakeReviewPackage,
    handleOpenSidePanel,
    handleSetPreviewMode,
    handleSetPreviewQuality,
    handleStartBlankSite,
    handleStartSiteBoundaryDraw,
    hasSiteBoundary,
    issues,
    markSystemsStale,
    parkingCount,
    pendingPlacementObjects,
    placementModeEnabled,
    progressTimelineState,
    projectStatusSummary,
    recordRecentChange,
    refuseUnsafeConstructionCommand,
    resolveLotBounds,
    saveSiteAddress,
    setActivePlacementId,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setAutoExistingConditionsStatus,
    setBuildingPlacements,
    setCadToolRequest,
    setCommandBarExpanded,
    setFitToSiteRequest,
    setLotHeight,
    setLotWidth,
    setParkingCount,
    setPreviewInteraction,
    setPreviewLayers,
    setPreviewMode,
    setRenderedSidePanel,
    setRightRailCollapsed,
    setShowSiteBounds,
    setSidePanelVisible,
    setSiteAddress,
    setSiteSelectionMode,
    setStatusMessage,
    siteAddress,
    siteScaleLocked,
    systemStatuses,
    updateProjectStatus,
    workflowActionHints,
    workflowReviewDashboard,
  });
  const { handleContinuePendingClarification, handlePromptKeyDown, handleSendMessage } = useDashboardChatSendHandlers({
    activeJob: visibleActiveJob,
    appendChatMessage,
    assumedTerrainSlopePct,
    buildingPlacements,
    busy,
    cancelActiveCommandState,
    handleAddObject,
    handleAnalyzeImageFeatures,
    handleAnalyzeSiteAccess,
    handleContinueActiveJob,
    handleGenerateSystem,
    handleSelectPlacementTarget,
    handleToggleSiteLock,
    imageName,
    mapSnapshotPath,
    onOpenChatPanel: () => handleOpenSidePanel("chat"),
    pendingClarification,
    prompt,
    refuseUnsafeConstructionCommand,
    resolveLotBounds,
    runOrchestrator,
    setPendingClarification,
    setPrompt,
    setStatusMessage,
    setSurveySlopeEstimate,
    setUseSurveyForGrading,
    shouldRouteToOrchestrator,
    surveyFileName,
    tryHandleActionIntent,
    tryHandleInfoIntent,
    tryHandleObjectIntent,
    tryHandlePowerCommand,
    tryHandleSheetIntent,
  });
  const buildChatDecisionContext = useDashboardChatDecisionContextBuilder({
    appliedAddressLabel,
    assistedEnabled,
    assumptions,
    backendResultHasFinalPlan: Boolean(backendResult?.final_plan),
    buildingCount,
    buildingDepth,
    buildingPlacements,
    buildingWidth,
    chatMessagesRef,
    currentExplanation,
    currentManualFailures,
    currentPlanMeta,
    currentProject,
    currentTruthAudit,
    drainage,
    fileName,
    grading,
    hasAssumedTerrainSlope,
    hasLocationEvidence,
    hasTerrainSource,
    hasVerifiedSurveyControl,
    issues,
    lotHeight,
    lotWidth,
    mapAnalysisSuccess: Boolean(mapAnalysis?.success),
    maxAdaCrossSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    minSlopePct,
    onlineSourceLookupLabel,
    parkingCount,
    pendingPlacementObjects,
    pipeMinSlopePct,
    planPreviewUrl,
    placedObjectCount,
    progressTimelineState,
    projectType,
    roads,
    setback,
    setupWizardState,
    siteAddress,
    siteName,
    siteScaleLocked,
    systemStatuses,
    units,
    utilities,
    visibleActiveJob,
  });
  const denseConceptObjectCount = buildingPlacements.filter((item) => Boolean(item.meta?.dense_concept_generated)).length;
  const denseConceptActive = denseConceptObjectCount >= 6;
  const drawWorkspaceActive =
    activePrimaryWorkflowKey === "draw" ||
    activePrimaryWorkflowKey === "objects" ||
    sidePanelForRender === "objects" ||
    sidePanelForRender === "model" ||
    previewInteraction === "edit";
  const canvasDrawControlsActive =
    sidePanelForRender === "objects" ||
    sidePanelForRender === "model" ||
    sidePanelForRender === "layers" ||
    sidePanelForRender === "details";
  const canvasPreviewInteraction =
    canvasDrawControlsActive ? "edit" : "static";
  const commandBarVisible =
    Boolean(commandBarExpanded || prompt.trim() || imageName || busy || chatBlockingActiveJob) &&
    !(mobileViewport && leftSidebarOpen);
  const workspaceChromeHidden = workspaceChromeMinimized || (drawWorkspaceActive && sidebarVisible);
  const handleCopyIssueDiagnostic = async () => {
    try {
      await navigator.clipboard.writeText(issueDiagnosticSummary);
      setIssueReportCopied(true);
      setStatusMessage("Issue diagnostic summary copied.");
      window.setTimeout(() => setIssueReportCopied(false), 2000);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Could not copy issue summary.");
    }
  };
  const { dashboardHomePanelProps, importSurveyPanelProps, siteSetupPanelProps } = useDashboardStartPanelProps({
    siteName,
    fileName,
    lotBounds,
    hasHardSystemBlock,
    hasBackendResult: Boolean(backendResult),
    onSiteNameChange: setSiteName,
    onSiteNameAutoChange: setSiteNameAuto,
    onFileNameChange: setFileName,
    onFileNameAutoChange: setFileNameAuto,
    onSaveProject: saveProject,
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
    onIssueReportMessageChange: setIssueReportMessage,
    onCopyIssueDiagnostic: handleCopyIssueDiagnostic,
    workflowReviewDashboard,
    systemHealthItems,
    issueMessages: issues.map((issue) => issue.message),
    analysisIssueMessages: analysisIssues.map((issue) => issue.message),
    quantityRows,
    formatMetric,
    statusLabelForQuantityReview,
    onOpenSidePanel: handleOpenSidePanel,
    pendingAddressEdit,
    siteAddress,
    appliedAddress: siteInputs?.address || "",
    addressNeedsApply,
    hasAppliedAddress,
    localAddressLocked,
    siteScaleLocked,
    onlineDiscoveryBusy,
    addressSuggestions,
    autoExistingConditionsStatus,
    siteAddressInputRef,
    onSiteAddressChange: setSiteAddress,
    onSelectedAddressSuggestionChange: setSelectedAddressSuggestion,
    onAddressSuggestionsChange: setAddressSuggestions,
    onSaveSiteAddress: () => void saveSiteAddress(),
    onCreateCenteredSite: () => void handleCreateCenteredSiteFromSetup(),
    onStartBlankSite: handleStartBlankSite,
    lotWidth,
    lotHeight,
    siteTooLargeForWarning,
    oversizedSiteMessage: OVERSIZED_SITE_MESSAGE,
    onLotWidthChange: setLotWidth,
    onLotHeightChange: setLotHeight,
    onStartSiteBoundaryDraw: handleStartSiteBoundaryDraw,
    onApplySite: () => void handleApplySite(),
    onUnlockSite: handleUnlockSite,
    hasTerrainSource,
    surveyFileName,
    uploadedImagePreviewUrl,
    uploadedImageApiUrl,
    surveyPreviewPointCount: surveyPreviewPoints.length,
    surveyUploadMessage,
    sourceEffectRows,
    imageUploadState,
    imageUploadNote,
    mapSnapshotPath,
    mapSnapshotInputRef,
    surveyInputRef,
    onOpenImport: () => handleOpenSidePanel("import_survey"),
    onAnalyzeMapSnapshot: analyzeMapSnapshot,
    onUploadImage: uploadImage,
    onUploadExistingConditions: uploadExistingConditions,
    autoSiteContextFlowSummary,
    siteIntelligenceSummary,
    siteIntelligenceFoundCount: siteIntelligenceFound.length,
    siteIntelligenceMissingCount: siteIntelligenceMissing.length,
    siteIntelligenceAssumedCount: siteIntelligenceAssumed.length,
    siteIntelligenceOutsideCount: siteIntelligenceOutside.length,
    roadFrontageMessage: String(roadFrontageHint.message || ""),
    drivewaySuggestionMessage: String(drivewaySuggestion.message || ""),
    gradingContextMessage: String(gradingContextHint.message || ""),
    autoSiteContextRows,
    onlineFoundSources,
    candidateReviewItemCount: candidateReviewItems.length,
    onReviewFoundContext: () => handleOpenSidePanel("data"),
    onRerunSiteContext: () => void saveSiteAddress(),
    planPdfReady: Boolean(planPdfAnalysis),
    mapAnalysisReady: Boolean(mapAnalysis?.success),
    detectionScaleFtPerPx,
    siteRotationDeg,
    onFitToSite: () => setFitToSiteRequest((value) => value + 1),
    onMapCenter: () => setMapCenterRequest((value) => value + 1),
    onAlignRoad: () => setAlignToRoadRequest((value) => value + 1),
    onResetRotation: () => {
      setSiteRotationDeg(0);
      setSiteRotationInput("0");
      scheduleRotationSave(0);
    },
    onRotationChange: (value) => {
      setSiteRotationDeg(value);
      setSiteRotationInput(String(value));
      scheduleRotationSave(value);
    },
  });
  const dataSourcesPanelProps = useDashboardDataSourcesPanelProps({
    sourceHubLinks,
    sourceHubMetrics,
    sourceConfidenceEntryCount: sourceConfidenceSummary.entry_count ?? sourceConfidenceEntries.length,
    sourceConfidenceRows,
    onOpenPanel: handleOpenSidePanel,
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
    onUploadPlanPdf: uploadPlanPdf,
    onSelectPlanPdfElement: setSelectedPlanPdfElementId,
    onPlanPdfDraftTextChange: setPlanPdfElementDraftText,
    onPlanPdfMoveXChange: setPlanPdfMoveX,
    onPlanPdfMoveYChange: setPlanPdfMoveY,
    onUpdatePlanPdfElement: updatePlanPdfElement,
    onExportPlanPdfJson: exportPlanPdfReport,
    onExportPlanPdf: exportPlanPdfReviewPdf,
    onPromptChange: setPrompt,
    onStatusMessageChange: setStatusMessage,
    capabilityAuditRows,
    onlineDiscoveryStatus: onlineDiscovery.status ?? "",
    onlineDiscoveryRan: Boolean(onlineDiscovery.version),
    onlineDiscoverySources,
    candidateReviewCounts,
    candidateReviewItems,
    onCandidateDecision: handleCandidateReviewDecision,
    siteAddress,
    selectedAddressSuggestion,
    addressSuggestions,
    onSiteAddressChange: setSiteAddress,
    onSelectedAddressSuggestionChange: setSelectedAddressSuggestion,
    onAddressSuggestionsChange: setAddressSuggestions,
    onApplyAddress: saveSiteAddress,
    autoExistingConditionsStatus,
    mapSnapshotInputRef,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
    imageUploadState,
    imageUploadNote,
    mapSnapshotPath,
    mapAnalysis,
    onAnalyzeMapSnapshot: analyzeMapSnapshot,
    siteScaleLocked,
    onUnlockSite: handleUnlockSite,
    onApplySite: handleApplySite,
    lotBounds,
    siteTooLargeForWarning,
    missingSite,
    hasTerrainSource,
    siteTooLargeForGrading,
    onGenerateSystem: handleGenerateSystem,
    onAnalyzeImageFeatures: handleAnalyzeImageFeatures,
    missingImage,
    detectedPlacements,
    siteSelectionMode,
    buildingPlacements,
    detectionChoices,
    onDetectionChoicesChange: setDetectionChoices,
    onRunSelectedDetections: runSelectedDetections,
    onAnalyzeSiteAccess: handleAnalyzeSiteAccess,
    confirmedObjectCounts,
    analysisIssueCount: analysisIssues.length,
    mapAnalysisCounts,
    siteRotationDeg,
    siteRotationInput,
    onSiteRotationDegChange: setSiteRotationDeg,
    onSiteRotationInputChange: setSiteRotationInput,
    onScheduleRotationSave: scheduleRotationSave,
    onFitToSite: () => setFitToSiteRequest((value) => value + 1),
    onUseMapCenter: () => setMapCenterRequest((value) => value + 1),
    onAlignToRoad: () => setAlignToRoadRequest((value) => value + 1),
    drainageSourceOverride,
    drainageSurfaceSummary,
    onDrainageSourceOverrideChange: setDrainageSourceOverride,
    currentProject,
    payloadPreview,
    onSaveProject: saveProject,
    onUploadImage: uploadImage,
  });
  const {
    drainageWorkbenchPanelProps,
    generatePanelProps,
    gradingWorkbenchPanelProps,
    landscapeWorkbenchPanelProps,
    roadwayWorkbenchPanelProps,
    sanitaryWorkbenchPanelProps,
    systemReadinessPanelProps,
    utilitiesWorkbenchPanelProps,
    waterFireFlowWorkbenchPanelProps,
  } = useDashboardGenerationPanelProps({
    missingSite,
    busy,
    hasVisibleActiveJob: Boolean(visibleActiveJob),
    statusMessage,
    assistedEnabled,
    pendingPlacementCount: pendingPlacementObjects.length,
    pendingPlacementLabels,
    currentUserLayoutContext: currentGenerateLayoutContext,
    autoSiteContextFlowSummary,
    systemReadinessRows,
    issues,
    generateFlowSummary,
    reactiveValidation,
    reactiveAffectedRunTarget,
    onAssistedEnabledChange: setAssistedEnabled,
    onStatusMessageChange: setStatusMessage,
    onGenerateFlowSummaryChange: setGenerateFlowSummary,
    onGenerateSystem: handleGenerateSystem,
    drainageIssueApplyLabel,
    canApplyDrainageIssue,
    getIssueGuidance,
    onApplyDrainageIssue: handleApplyDrainageIssue,
    formatStageLabel,
    hasTerrainSource,
    hasGradingSurface,
    siteTooLargeForGrading,
    systemStatuses,
    useSurveyForGrading,
    onUseSurveyForGradingChange: setUseSurveyForGrading,
    minSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    maxAdaCrossSlopePct,
    onMinSlopePctChange: setMinSlopePct,
    onMaxParkingSlopePctChange: setMaxParkingSlopePct,
    onMaxRoadGradePctChange: setMaxRoadGradePct,
    onMaxAdaCrossSlopePctChange: setMaxAdaCrossSlopePct,
    drainageAllowSlopeAdjust,
    onDrainageAllowSlopeAdjustChange: setDrainageAllowSlopeAdjust,
    gradingEarthworkUx,
    onOpenPanel: handleOpenSidePanel,
    hasBasinPlaced,
    hasHardSystemBlock,
    drainageSourceOverride,
    onDrainageSourceOverrideChange: setDrainageSourceOverride,
    drainageConnectOrphans,
    onDrainageConnectOrphansChange: setDrainageConnectOrphans,
    drainageMaxSlopeAdjust,
    onDrainageMaxSlopeAdjustChange: setDrainageMaxSlopeAdjust,
    onAddObject: handleAddObject,
    drainage,
    utilities,
    pipeMinSlopePct,
    onUtilitiesChange: setUtilities,
    onPipeMinSlopePctChange: setPipeMinSlopePct,
    buildingPlacements,
    confirmedBuildingCount: confirmedObjectCounts.buildings,
    waterFireFlowReview,
    roads,
    stormHydrologyReview,
    systemReadinessPanelKey: sidePanelForRender as Extract<SidePanelKey, "system_grading" | "system_storm" | "system_sanitary" | "system_water" | "system_roadway" | "system_utilities" | "system_landscape">,
    siteScaleLocked,
    activeCivil3DWorkflowTab,
    onCivil3DWorkflowTabChange: setActiveCivil3DWorkflowTab,
    roadwayWorkbenchData,
    sourceConfidenceRows,
    civil3DWorkflowBlockers,
    gradingSourceSummary,
    hasVerifiedSurveyControl,
    onShowProfileControls: () => {
      setActiveRoadwayWorkbenchTab("profile");
    },
    parkingAngle,
    onParkingAngleChange: setParkingAngle,
    onRoadsChange: setRoads,
    parkingLoading,
    onParkingLoadingChange: setParkingLoading,
    parkingStallWidth,
    onParkingStallWidthChange: setParkingStallWidth,
    parkingAisleWidth,
    onParkingAisleWidthChange: setParkingAisleWidth,
    parkingStallDepth,
    onParkingStallDepthChange: setParkingStallDepth,
    parkingAdaCount,
    onParkingAdaCountChange: setParkingAdaCount,
    parkingCompactCount,
    onParkingCompactCountChange: setParkingCompactCount,
    parkingAdaAisleWidth,
    onParkingAdaAisleWidthChange: setParkingAdaAisleWidth,
    parkingCompactWidth,
    onParkingCompactWidthChange: setParkingCompactWidth,
    activeRoadwayWorkbenchTab,
    onRoadwayWorkbenchTabChange: setActiveRoadwayWorkbenchTab,
    hasBackendResult: Boolean(backendResult),
  });
  const {
    deliverPanelProps,
    reportsQuantitiesPanelProps,
  } = useDashboardDeliverReportsPanelProps({
    sidePanelForRender,
    reviewPackageFlowSummary,
    planPreviewUrl,
    hasBackendResult: Boolean(backendResult),
    placedObjectCount,
    sidebarTrustScore,
    exportActionMessage,
    exportBlockReason: getExportBlockReason() || "",
    planSheetSet,
    planSheetBlockers: getPlanSheetBlockers(),
    projectName: siteName || currentProject?.name || "Untitled Project",
    addressLabel: appliedAddressLabel || siteAddress.trim() || "No address applied",
    lotWidth: parsePositiveNumber(lotWidth) ?? lotBounds.w ?? 0,
    lotHeight: parsePositiveNumber(lotHeight) ?? lotBounds.h ?? 0,
    placements: buildingPlacements,
    autoSiteContextFlowSummary,
    sidebarReleaseStatus,
    reviewGateItems,
    topSmartFix,
    onMakeReviewPackage: handleMakeReviewPackage,
    onPlanSheetExportPdf: handlePlanSheetExportPdf,
    onExportDxf: handleExportDxf,
    onExportReport: handleExportReport,
    onOpenPanel: handleOpenSidePanel,
    onPlanSheetTitleBlockUpdate: handlePlanSheetTitleBlockUpdate,
    onPlanSheetScaleChange: handlePlanSheetScaleChange,
    onPlanSheetViewportUpdate: handlePlanSheetViewportUpdate,
    onPlanSheetViewportDelete: handlePlanSheetViewportDelete,
    onPlanSheetAddNote: handlePlanSheetAddNote,
    onPlanSheetAddAnnotation: addPlanSheetAnnotation,
    onStatusMessageChange: setStatusMessage,
    onPlanSheetAddViewport: handlePlanSheetAddViewport,
    onPlanSheetViewportLayerToggle: handlePlanSheetViewportLayerToggle,
    onPlanSheetViewportScaleLockToggle: handlePlanSheetViewportScaleLockToggle,
    onPlanSheetGrayscaleToggle: handlePlanSheetGrayscaleToggle,
    onPlanSheetAddRevision: () => handlePlanSheetAddRevision(),
    onPlanSheetAddTable: handlePlanSheetAddTable,
    onPlanSheetAddDetailBlock: handlePlanSheetAddDetailBlock,
    onPlanSheetAddReference: handlePlanSheetAddReference,
    onPlanSheetSelectSheet: (sheetId) => {
      setPlanSheetSet((current) => ({
        ...current,
        activeSheetId: sheetId,
        updatedAt: new Date().toISOString(),
      }));
    },
    onCreateReviewSheet: handleCreateReviewSheet,
    onPlanSheetExportJson: handlePlanSheetExportJson,
    onSmartFixAction: handleSmartFixAction,
    issues,
    analysisIssueCount: analysisIssues.length,
    sidebarMissingInputCount: sidebarMissingInputs.length,
    sidebarAssumptionCount: sidebarAssumptions.length,
    blockedSystemCount: systemHealthItems.filter((item) => item.state === "blocked").length,
    engineeringHealthPanelLinks,
    drainageIssueApplyLabel,
    canApplyDrainageIssue,
    getIssueGuidance,
    onApplyDrainageIssue: handleApplyDrainageIssue,
    reviewIssueItems,
    openReviewIssueCount: openReviewIssueItems.length,
    reviewIssueTracker,
    drainageReviewIssueCount: drainageReviewIssueItems.length,
    onPromptChange: setPrompt,
    sidebarTruthItems,
    designAlternatives,
    designAlternativeItems,
    topDesignAlternative,
    selectedDesignAlternativeId,
    designAlternativeQuantityAvailable,
    onDesignAlternativesAction: (action, optionNumber) => void handleDesignAlternativesAction(action, optionNumber),
    sourceConfidenceSummary,
    sourceConfidenceRows,
    sourceConfidenceEntryCount: sourceConfidenceEntries.length,
    quantityRows,
    staleSystemCount: sidebarStaleSystems.length,
    onExportQuantityReviewReport: handleExportQuantityReviewReport,
    formatMetric,
    statusLabelForQuantityReview,
  });
  const {
    filesPanelProps,
    jobsPanelProps,
    librariesPanelProps,
    standardsPanelProps,
    templatesPanelProps,
    utilityCatalogPanelProps,
  } = useDashboardSupportPanelProps({
    token,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
    surveyFileName,
    projectRecordLabel: currentProject?.project_id || projectId || "Draft",
    surveyUploadMessage,
    sourceEffectRows,
    planPreviewUrl,
    hasBackendResult: Boolean(backendResult),
    dxfStatus: getExportBlockReason() || (backendResult ? "Review export" : "Needs run"),
    exportBlockReason: getExportBlockReason(),
    onOpenPanel: handleOpenSidePanel,
    mapSnapshotInputRef,
    surveyInputRef,
    onExportDxf: handleExportDxf,
    onExportReport: handleExportReport,
    activeJob: visibleActiveJob,
    selectedJob,
    jobHistory,
    jobStatusCounts,
    artifactHistory,
    activeJobStale: visibleActiveJobStale,
    selectedJobStale,
    jobsPanelStatusMessage,
    onJobsPanelStatusMessageChange: setJobsPanelStatusMessage,
    onStatusMessageChange: setStatusMessage,
    formatTimestamp,
    toReadableLabel,
    jobDetailMessage,
    refreshJobs,
    onSelectJob: handleSelectJob,
    onCancelJobById: (jobId) => void handleCancelJobById(jobId),
    onRetryJob: (jobId) => void handleRetryJob(jobId),
    onResumeJob: (jobId) => void handleResumeJob(jobId),
    onArtifactDownload: (downloadPath, filename) => void handleArtifactDownload(downloadPath, filename),
    customerTemplates,
    customerTemplateStatus,
    customerTemplateSummaries,
    activeCustomerTemplate,
    customerTemplateBlockerCount,
    onCustomerTemplatesChange: setCustomerTemplates,
    onCustomerTemplateStatusChange: setCustomerTemplateStatus,
    utilityCatalog,
    utilityCatalogStatus,
    utilityCatalogNetworkFilter,
    onUtilityCatalogNetworkFilterChange: setUtilityCatalogNetworkFilter,
    standardsPanelCriteria,
    standardsPanelRows,
    libraryPanelSections,
    onAddObject: handleAddObject,
  });
  const {
    analysisPanelProps,
    detailsPanelProps,
    layersPanelProps,
    modelReviewPanelProps,
    workspaceSettingsPanelProps,
  } = useDashboardReviewUtilityPanelProps({
    previewMode,
    previewQuality,
    hasGradingSurface,
    hasHardSystemBlock,
    placedObjectCount,
    issues,
    analysisIssues,
    roads,
    utilities,
    hasBasinPlaced,
    buildingPlacements,
    selectedBuilding,
    sourceConfidenceByObjectId,
    objectManagerStatusMessage,
    objectClipboardCount: objectClipboard.length,
    activePlacementId,
    onActivePlacementIdChange: setActivePlacementId,
    onReportObjectActionBlocker: reportObjectActionBlocker,
    onUpdateBuilding: handleUpdateBuilding,
    onToggleBuildingLock: handleToggleBuildingLock,
    onUpdateObjectVertex: handleUpdateObjectVertex,
    onInsertObjectVertex: handleInsertObjectVertex,
    onDeleteObjectVertex: handleDeleteObjectVertex,
    onSnapObjectVertexToNearestEndpoint: handleSnapObjectVertexToNearestEndpoint,
    onAlignObjectVertexToPrevious: handleAlignObjectVertexToPrevious,
    onObjectManagerSelect: handleObjectManagerSelect,
    onPlacementModeEnabledChange: setPlacementModeEnabled,
    onFocusObjectIdChange: setFocusObjectId,
    onCloseSidePanel: handleCloseSidePanel,
    onObjectManagerCopy: handleObjectManagerCopy,
    onObjectManagerPaste: handleObjectManagerPaste,
    onObjectManagerTransform: handleObjectManagerTransform,
    onObjectManagerDelete: handleObjectManagerDelete,
    previewLayers,
    onPreviewLayersChange: (updater) => setPreviewLayers((previous) => updater(previous) as typeof previous),
    systemCompleteCount: systemHealthItems.filter((item) => item.state === "complete").length,
    blockedSystemCount: systemHealthItems.filter((item) => item.state === "blocked").length,
    drainageIssueApplyLabel,
    canApplyDrainageIssue,
    onApplyDrainageIssue: handleApplyDrainageIssue,
    onAnalyzeSiteAccess: handleAnalyzeSiteAccess,
    onOpenDashboard: () => handleOpenSidePanel("dashboard"),
    leftSidebarOpen,
    assistedEnabled,
    sidebarReleaseStatus,
    standardsStatus: panelStatus("standards"),
    disciplineToggles,
    onOpenStandards: () => handleOpenSidePanel("standards"),
    onOpenDeliverables: () => handleOpenSidePanel("deliverables"),
  });
  const workspaceCanvasAreaProps = useDashboardCanvasAreaProps({
    siteScaleLocked,
    workspaceChromeHidden,
    sidebarVisible,
    rightRailCollapsed,
    sidePanelForRender,
    siteName,
    currentProject,
    activeWorkflowKey: activePrimaryWorkflowKey,
    workflowItems: primaryWorkflowItems,
    toolbarTools: contextualToolbarTools,
    previewMode,
    previewQuality,
    layerManagerOpen,
    previewLayers,
    selectedBuilding,
    selectedObjectConfidence,
    moveEditFeedback,
    previewInteraction,
    denseConceptActive,
    denseConceptObjectCount,
    onOpenPanel: handleOpenPanelFromDrawer,
    onMinimizeChrome: () => setWorkspaceChromeMinimized(true),
    onPreviewModeSelect: handleSetPreviewMode,
    onPreviewQualitySelect: handleSetPreviewQuality,
    onSetRightRailCollapsed: setRightRailCollapsed,
    onCloseLayerManager: () => setLayerManagerOpen(false),
    onApplyLayerPreset: setPreviewLayers,
    onToggleLayer: (key, visible) => setPreviewLayers((prev) => ({ ...prev, [key]: visible })),
    onEditSelectedObject: handleEditFloatingSelectedObject,
    onFocusSelectedObject: handleFocusFloatingSelectedObject,
    onOpenSelectedObjectDetails: handleOpenFloatingObjectDetails,
    previewReview,
    onRefreshPreview: handlePreviewPlan,
    busy,
    planPreviewUrl,
    planPreviewProjectId,
    projectId,
    canvasPreviewInteraction,
    systemStatuses,
    hasTerrainSource,
    hasSourceBackedSurfaceEvidence,
    hasBasinPlaced,
    siteTooLargeForGrading,
    hasHardSystemBlock,
    hasBackendResult: Boolean(backendResult),
    placedObjectCount,
    placementModeEnabled,
    activePlacementId,
    onViewportCenter: handleViewportCenter,
    externalRectUndo,
    onPlaceBuilding: handlePlaceBuilding,
    onPlaceObject: handlePlaceObject,
    onCreateCustomGeometry: handleCreateCustomGeometry,
    onCreateSiteBoundary: handleCreateSiteBoundary,
    onUnlockSite: handleUnlockSite,
    buildingPlacements,
    cadEntityPreviewObjects: cadEntityPreview.objects,
    suggestedPlacements: filteredDetectedPlacements,
    selectedObjectIds,
    focusDetectedId,
    onFocusDetectedIdChange: setFocusDetectedId,
    focusObjectId,
    onFocusObjectIdChange: setFocusObjectId,
    lotWidth: lotBounds.w,
    lotHeight: lotBounds.h,
    onViewportFootprint: handleViewportFootprint,
    onUpdateBuilding: handleUpdateBuilding,
    onDetectedPlacementsChange: setDetectedPlacements,
    onPersistDetectedPlacements: persistDetectedPlacements,
    analysisPaths,
    selectedAccessIssue,
    analysisFocusLocked,
    onAnalysisSelectedIssueIdChange: setAnalysisSelectedIssueId,
    onAnalysisFocusLockedChange: setAnalysisFocusLocked,
    onRemoveBuilding: handleRemoveBuilding,
    onRestoreBuilding: handleRestoreBuilding,
    onSelectBuilding: setActivePlacementId,
    onSelectObjects: setSelectedObjectIds,
    onSetPreviewMode: handleSetPreviewMode,
    onSetPreviewInteraction: setPreviewInteraction,
    onSetPreviewQuality: handleSetPreviewQuality,
    onRecordRecentChange: recordRecentChange,
    onPushRecoveryMessage: pushRecoveryMessage,
    previewRefreshing,
    previewRefreshNote,
    preview3DEffectiveItems,
    usingAnnotation3D,
    hasGradingSurface,
    onPreviewFullscreenOpenChange: setPreviewFullscreenOpen,
    previewFullscreenOpen,
    planPreviewAnnotations,
    selectedIssueLabel,
    showMeasurements,
    showCalculations,
    measurementOverlayStats,
    calculationOverlayStats,
    gradingEarthworkUx,
    geocode: siteInputs?.geocode ?? null,
    mapScaleFtPerPx: detectionScaleFtPerPx,
    mapScaleSource: detectionScaleSource,
    siteRotationDeg: siteInputs?.site_rotation_deg ?? 0,
    showSiteBounds,
    siteDrawRequest,
    gradingBlocker,
    fitToSiteRequest,
    mapCenterRequest,
    alignToRoadRequest,
    onMapCenter: handleMapCenter,
    siteLocked: siteScaleLocked,
    onLockSite: () => void handleApplySite(),
    stormHydrologyOverlay: {
      inletChecks: stormHydrologyReview.inletChecks,
      overflowPaths: stormHydrologyReview.overflowPaths,
    },
    sourceContextBadges: previewSourceContextBadges,
    onSiteRotationDegChange: setSiteRotationDeg,
    onSiteRotationInputChange: setSiteRotationInput,
    onScheduleRotationSave: scheduleRotationSave,
    surveyPoints: surveyPreviewPoints,
    onMapScaleFtPerPxChange: setDetectionScaleFtPerPx,
    onMapScaleSourceChange: setDetectionScaleSource,
    onScheduleScaleSave: scheduleScaleSave,
    mapDebugOverlay,
    cadToolRequest,
  });
  const {
    chatPanelProps,
    pinnedCommandBarProps,
  } = useDashboardChatCommandProps({
    chatMessages,
    chatScrollRef,
    chatPromptInputRef,
    onSetMessageFeedback: setMessageFeedback,
    thinkingState,
    busy,
    activePlanTool,
    visibleActiveJobStatus: visibleActiveJob?.status ?? "",
    hasDirectRunInFlight: Boolean(directRunAbortRef.current),
    onCancelJob: handleCancelActiveJob,
    onContinueJob: handleContinueActiveJob,
    pendingClarificationQuestion: pendingClarification?.question || null,
    onContinuePendingClarification: handleContinuePendingClarification,
    prompt,
    imageName,
    onPromptChange: setPrompt,
    onPromptKeyDown: handlePromptKeyDown,
    commandInputRef,
    onSendMessage: handleSendMessage,
    onUploadImage: uploadImage,
    onExplainPlan: () => void handleExplainPlan(),
    onRunFix: () => void handleRunFix(),
    onRunImprove: () => void handleRunImprove(),
    onSaveProject: () => void saveProject(),
    canExplain: Boolean(planPreviewUrl),
    statusMessage,
    hasVisibleActiveJob: Boolean(visibleActiveJob),
    approvalState: approvalStatus.state,
    approvalPhaseLabel: approvalStatus.label,
    approvalError,
    onToggleChatCollapsed: handleCloseSidePanel,
    summaryText: chatSummary,
    onOpenHistory: () => handleOpenSidePanel("chat"),
    chatBlockingActiveJob,
    projectStatusSummary,
    activePrimaryWorkflowKey,
    previewInteraction,
    activePlacementId,
    previewMode,
    previewQuality,
  });
  const activePanelTitle =
    previewMode === "3d" && sidePanelForRender === "model"
      ? "3D"
      : sidePanelForRender
        ? sidePanelCopy[sidePanelForRender].title
        : "";
  const activePanelDescription =
    previewMode === "3d" && sidePanelForRender === "model"
      ? "Cinematic engineering visualization and review with the same truthful readiness gates."
      : sidePanelForRender
        ? sidePanelCopy[sidePanelForRender].desc
        : "";
	  if (!clientMounted) {
    return (
      <div className="civora-app-bg min-h-screen text-[var(--civora-text)]">
        <div className="flex min-h-screen items-center justify-center px-6">
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              Civora AI
            </p>
            <p className="mt-3 text-sm font-medium text-slate-600">
              Loading workspace...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!effectiveUser) {
    return (
      <AuthScreen
        authMode={authMode}
        authStatus={authStatus}
        authStatusError={authStatusError}
        authName={authName}
        authEmail={authEmail}
        authPassword={authPassword}
        showPassword={showPassword}
        authError={authError}
        authLoading={authLoading}
        onAuthModeChange={setAuthMode}
        onAuthNameChange={setAuthName}
        onAuthEmailChange={setAuthEmail}
        onAuthPasswordChange={setAuthPassword}
        onTogglePassword={() => setShowPassword((value) => !value)}
        onClearAuthError={() => setAuthError("")}
        onSubmit={handleAuth}
      />
    );
  }

  return (
    <div
      className="civora-app-bg min-h-screen text-[var(--civora-text)]"
      onKeyDownCapture={(event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        handleCancelActiveTool();
      }}
    >
      <WorkspaceToasts toasts={jobToasts} />
      <div className="flex min-h-screen flex-col">
        <AppHeader
          userEmail={effectiveUser.email}
          onOpenProjects={() => {
            if (token) void refreshProjects(token);
            handleOpenSidePanel("projects");
          }}
          onOpenDocs={() => handleOpenSidePanel("trust")}
          onOpenChat={() => handleOpenSidePanel("chat")}
          onOpenWorkspaceControls={() => {
            setLeftSidebarOpen(true);
            setSidebarVisible(true);
            setWorkspaceChromeMinimized(false);
            handleOpenSidePanel("site_existing");
          }}
          sidebarOpen={leftSidebarOpen}
          onToggleSidebar={() => {
            setLeftSidebarOpen((value) => !value);
          }}
          onLogout={handleLogout}
        />
        <div data-testid="project-status-summary" className="sr-only" aria-live="polite">
          {`${projectStatusDisplayLabel[projectStatusSummary.state]}: ${projectStatusSummary.title}.`}
        </div>

        <div className="relative h-[calc(100svh-4rem)] min-h-0 w-full max-w-full overflow-hidden lg:h-[calc(100vh-4rem)]">
          {sidebarRendered ? (
            <WorkspaceLeftRail
              visible={sidebarVisible}
              activePanel={sidePanelForRender}
              activeWorkflowKey={activePrimaryWorkflowKey}
              restoreTruthLabel={restoreTruthLabel}
              primaryWorkflowItems={primaryWorkflowItems}
              onOpenProjects={() => {
                if (token) void refreshProjects(token);
                handleOpenSidePanel("projects");
              }}
              onOpenPanel={handleOpenPanelFromDrawer}
            />
          ) : null}
          {sidePanelForRender ? (
            <WorkspaceRightPanel
              title={activePanelTitle}
              description={activePanelDescription}
              visible={sidePanelVisible}
              commandBarVisible={commandBarVisible}
              wide={sidePanelForRender === "deliverables"}
              onMinimize={handleCloseSidePanel}
            >
                {sidePanelForRender === "trust" ? <TrustPanel /> : null}
                {isDisciplinePanel ? (
                  <DisciplinePanelTabs
                    items={disciplinePanelLinks}
                    activePanel={sidePanelForRender}
                    onOpenPanel={(panel) => handleOpenSidePanel(panel)}
                  />
                ) : null}
                {sidePanelForRender === "projects" ? (
                  <ProjectsDrawer
                    stateLabel={projectDrawerStateLabel}
                    stateDetail={projectDrawerStateDetail}
                    notice={projectDrawerNotice}
                    projectTitle={siteName || currentProject?.name || "Untitled Project"}
                    activeProjectId={projectId}
                    projects={sortedProjects}
                    onNewProject={handleNewProject}
                    onSaveProject={() => void saveProject()}
                    onOpenJobs={() => handleOpenSidePanel("jobs")}
                    onOpenProject={(projectIdToOpen) => void loadProject(projectIdToOpen)}
                    onDeleteProject={handleDeleteProject}
                  />
                ) : null}

                {sidePanelForRender === "dashboard" ? (
                  <DashboardHomePanel {...dashboardHomePanelProps} />
                ) : null}

                {sidePanelForRender === "site_existing" ? (
                  <SiteSetupPanel {...siteSetupPanelProps} />
                ) : null}


                {sidePanelForRender === "import_survey" ? (
                  <ImportSurveyPanel {...importSurveyPanelProps} />
                ) : null}

                {sidePanelForRender === "data" ? (
                  <DataSourcesPanel {...dataSourcesPanelProps} />
                ) : null}

                {sidePanelForRender === "model" ? (
                  <ModelReviewPanel {...modelReviewPanelProps} />
                ) : null}

                {sidePanelForRender === "generate" ? (
                  <GeneratePanel {...generatePanelProps} />
                ) : null}

                {sidePanelForRender === "grading" ? (
                  <GradingWorkbenchPanel {...gradingWorkbenchPanelProps} />
                ) : null}

                {sidePanelForRender === "drainage" ? (
                  <DrainageWorkbenchPanel {...drainageWorkbenchPanelProps} />
                ) : null}
                {sidePanelForRender === "utilities" ? (
                  <UtilitiesWorkbenchPanel {...utilitiesWorkbenchPanelProps} />
                ) : null}

                {sidePanelForRender === "sanitary" ? (
                  <SanitaryWorkbenchPanel {...sanitaryWorkbenchPanelProps} />
                ) : null}
                {sidePanelForRender === "water" ? (
                  <WaterFireFlowWorkbenchPanel {...waterFireFlowWorkbenchPanelProps} />
                ) : null}

                {sidePanelForRender.startsWith("system_") ? (
                  <SystemReadinessPanel {...systemReadinessPanelProps} />
                ) : null}

                {sidePanelForRender === "roadway" ? (
                  <RoadwayWorkbenchPanel {...roadwayWorkbenchPanelProps} />
                ) : null}

                {sidePanelForRender === "landscape" ? (
                  <LandscapeWorkbenchPanel {...landscapeWorkbenchPanelProps} />
                ) : null}

                {sidePanelForRender === "details" ? (
                  <DashboardDetailsPanel {...detailsPanelProps} />
                ) : null}

                {sidePanelForRender === "layers" ? (
                  <LayersPanel {...layersPanelProps} />
                ) : null}

                {sidePanelForRender === "analysis" ? (
                  <AnalysisPanel {...analysisPanelProps} />
                ) : null}

                {sidePanelForRender === "files" ? (
                  <FilesPanel {...filesPanelProps} />
                ) : null}

                {sidePanelForRender === "jobs" ? (
                  <JobsPanel {...jobsPanelProps} />
                ) : null}

                {sidePanelForRender === "templates" ? (
                  <TemplatesPanel {...templatesPanelProps} />
                ) : null}

                {sidePanelForRender === "catalogs" ? (
                  <UtilityCatalogPanel {...utilityCatalogPanelProps} />
                ) : null}

                {sidePanelForRender === "standards" ? (
                  <StandardsPanel {...standardsPanelProps} />
                ) : null}

                {sidePanelForRender === "libraries" ? (
                  <LibrariesPanel {...librariesPanelProps} />
                ) : null}

                {sidePanelForRender === "settings" ? (
                  <WorkspaceSettingsPanel {...workspaceSettingsPanelProps} />
                ) : null}

                {sidePanelForRender === "objects" ? (
                  <DashboardObjectManagerPanel
                    cadToolGroups={cadToolGroups}
                    triggerCadTool={triggerCadTool}
                    pendingPlacementObjects={pendingPlacementObjects}
                    handleSelectPlacementTarget={handleSelectPlacementTarget}
                    selectedBuilding={selectedBuilding}
                    handleObjectManagerSelect={handleObjectManagerSelect}
                    setPlacementModeEnabled={setPlacementModeEnabled}
                    setFocusObjectId={setFocusObjectId}
                    onCloseSidePanel={handleCloseSidePanel}
                    handleObjectManagerCopy={handleObjectManagerCopy}
                    handleObjectManagerTransform={handleObjectManagerTransform}
                    handleObjectManagerDelete={handleObjectManagerDelete}
                    buildingPlacements={buildingPlacements}
                    placedObjects={placedObjects}
                    pendingPlacementCount={pendingPlacementObjects.length}
                    selectedObjectIds={selectedObjectIds}
                    hiddenObjectCount={hiddenObjectCount}
                    objectManagerTypes={objectManagerTypes}
                    objectClipboard={objectClipboard}
                    handleObjectManagerSelectVisibleDraft={handleObjectManagerSelectVisibleDraft}
                    handleObjectManagerInvertSelection={handleObjectManagerInvertSelection}
                    handleObjectManagerPaste={handleObjectManagerPaste}
                    handleUpdateBuilding={handleUpdateBuilding}
                    recordRecentChange={recordRecentChange}
                    pushRecoveryMessage={pushRecoveryMessage}
                    objectManagerLayerRows={objectManagerLayerRows}
                    handleObjectManagerLayerSelect={handleObjectManagerLayerSelect}
                    handleObjectManagerLayerIsolate={handleObjectManagerLayerIsolate}
                    handleObjectManagerLayerVisibility={handleObjectManagerLayerVisibility}
                    handleObjectManagerLayerLock={handleObjectManagerLayerLock}
                    objectManagerStatusMessage={objectManagerStatusMessage}
                    recentChanges={recentChanges}
                    handleUndoRecentChange={handleUndoRecentChange}
                    recentChangesOpen={recentChangesOpen}
                    lastDraftAction={lastDraftAction}
                    redoDraftAction={redoDraftAction}
                    setRecentChangesOpen={setRecentChangesOpen}
                    handleUndoDraftAction={handleUndoDraftAction}
                    handleRedoDraftAction={handleRedoDraftAction}
                    selectedObjectRows={selectedObjectRows}
                    selectedObjectMeasurementSummary={selectedObjectMeasurementSummary}
                    selectedObjectMeasurements={selectedObjectMeasurements}
                    arrayRows={arrayRows}
                    arrayColumns={arrayColumns}
                    arraySpacingX={arraySpacingX}
                    arraySpacingY={arraySpacingY}
                    bulkMoveX={bulkMoveX}
                    bulkMoveY={bulkMoveY}
                    bulkMoveToX={bulkMoveToX}
                    bulkMoveToY={bulkMoveToY}
                    bulkScaleFactor={bulkScaleFactor}
                    bulkRotateAngle={bulkRotateAngle}
                    combineObjectName={combineObjectName}
                    combineObjectType={combineObjectType}
                    draftBlockName={draftBlockName}
                    draftBlockLibrary={draftBlockLibrary}
                    setSelectedObjectIds={setSelectedObjectIds}
                    handleObjectManagerBulkVisibility={handleObjectManagerBulkVisibility}
                    handleObjectManagerIsolateSelected={handleObjectManagerIsolateSelected}
                    handleObjectManagerBulkLock={handleObjectManagerBulkLock}
                    handleObjectManagerBulkColor={handleObjectManagerBulkColor}
                    handleObjectManagerBulkType={handleObjectManagerBulkType}
                    handleObjectManagerBulkDuplicate={handleObjectManagerBulkDuplicate}
                    handleObjectManagerBulkLayout={handleObjectManagerBulkLayout}
                    handleObjectManagerBulkDelete={handleObjectManagerBulkDelete}
                    setArrayRows={setArrayRows}
                    setArrayColumns={setArrayColumns}
                    setArraySpacingX={setArraySpacingX}
                    setArraySpacingY={setArraySpacingY}
                    handleObjectManagerArraySelected={handleObjectManagerArraySelected}
                    setBulkMoveX={setBulkMoveX}
                    setBulkMoveY={setBulkMoveY}
                    handleObjectManagerBulkMove={handleObjectManagerBulkMove}
                    handleObjectManagerBulkCopyByOffset={handleObjectManagerBulkCopyByOffset}
                    setBulkMoveToX={setBulkMoveToX}
                    setBulkMoveToY={setBulkMoveToY}
                    handleObjectManagerBulkMoveTo={handleObjectManagerBulkMoveTo}
                    setBulkScaleFactor={setBulkScaleFactor}
                    handleObjectManagerBulkScale={handleObjectManagerBulkScale}
                    setBulkRotateAngle={setBulkRotateAngle}
                    handleObjectManagerBulkRotate={handleObjectManagerBulkRotate}
                    handleObjectManagerBulkMirror={handleObjectManagerBulkMirror}
                    setCombineObjectName={setCombineObjectName}
                    setCombineObjectType={setCombineObjectType}
                    handleObjectManagerCombineSelected={handleObjectManagerCombineSelected}
                    setDraftBlockName={setDraftBlockName}
                    handleObjectManagerSaveBlock={handleObjectManagerSaveBlock}
                    handleObjectManagerRenameBlock={handleObjectManagerRenameBlock}
                    handleObjectManagerUpdateBlock={handleObjectManagerUpdateBlock}
                    handleObjectManagerInsertBlock={handleObjectManagerInsertBlock}
                    handleObjectManagerDeleteBlock={handleObjectManagerDeleteBlock}
                    units={units}
                    activePlacementId={activePlacementId}
                    selectedObjectSet={selectedObjectSet}
                    sourceConfidenceByObjectId={sourceConfidenceByObjectId}
                    objectOutlineColor={objectOutlineColor || "#64748b"}
                    handleObjectManagerToggleMultiSelect={handleObjectManagerToggleMultiSelect}
                    reportObjectActionBlocker={reportObjectActionBlocker}
                    handleToggleBuildingLock={handleToggleBuildingLock}
                    handleOpenDetailsPanel={() => handleOpenPanelFromDrawer("details")}
                    handleObjectManagerExplodeCombined={handleObjectManagerExplodeCombined}
                  />
                ) : null}

                {sidePanelForRender === "deliverables" ? (
                  <DeliverPanel {...deliverPanelProps} />
                ) : null}

                {sidePanelForRender === "reports" || sidePanelForRender === "quantities" ? (
                  <DashboardReportsQuantitiesPanel {...reportsQuantitiesPanelProps} />
                ) : null}

                {sidePanelForRender === "chat" ? (
                  <ChatPanel {...chatPanelProps} />
                ) : null}
            </WorkspaceRightPanel>
          ) : null}
          <WorkspaceCanvasArea {...workspaceCanvasAreaProps} />
          {shortcutsOverlayOpen ? (
            <WorkspaceShortcutsOverlay
              shortcuts={supportedShortcuts}
              onClose={() => setShortcutsOverlayOpen(false)}
            />
          ) : null}
          {commandBarVisible ? (
            <PinnedCommandBar {...pinnedCommandBarProps} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function PerformanceAIDashboard() {
  return <PerformanceAIDashboardView />;
}
