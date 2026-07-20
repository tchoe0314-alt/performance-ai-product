"use client";
/* eslint-disable react-hooks/exhaustive-deps */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { deleteJson, getJson, patchJson, postForm, postJson, toApiUrl } from "../lib/api";

import type {
  Assumption,
  Issue,
  ProjectRecord,
  ProjectInput,
  JobSummary,
  ManualFailure,
  ManagerMetrics,
  QuantityTotals,
  StormSummary,
  PlanExplanation,
  PlanMeta,
  PlanResponse,
  SurveySlopeResponse,
  ImageDetectResponse,
  MapAnalysis,
  PreviewResponse,
  UploadImageResponse,
  UploadExistingConditionsResponse,
  UploadPlanPdfResponse,
  UploadSurveyResponse,
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
  OnlineExistingConditionsDiscovery,
  LocalGisProviderRegistry,
  CandidateReviewInbox,
  DesignAlternativesV1,
  ReviewIssueTrackerV1,
  SourceConfidenceMap,
  SmartFixRecommendation,
  EngineDepthDashboard,
  PlanPdfAnalysis,
  PlanPdfChangedElements,
  PlanPdfEditableSheet,
  PlanPdfElement,
} from "./types";

import {
  ACTIVE_PROJECT_STORAGE_KEY,
  DEFAULT_SYSTEM_STATUS,
  EMPTY_REACTIVE_VALIDATION,
  OVERSIZED_SITE_MESSAGE,
  REACTIVE_EDIT_POLICY_PREFERENCE,
  REACTIVE_SYSTEM_STAGE_MAP,
  SQFT_PER_ACRE,
  SITE_GRADING_HARD_BLOCK_ACRES,
  SITE_WARNING_ACRES,
  buildAssumedSlopeEstimate,
  formatStageLabel,
  isHardGenerateBlocker,
  siteAreaAcresFromSize,
  statusLabelForQuantityReview,
  uniqueStrings,
  type EngineeringSystemKey,
  type ReactiveValidationState,
  type SystemGenerationTarget,
} from "./utils/workflowConstants";
import { buildDashboardQuantityRows } from "./utils/dashboardQuantityRows";
import {
  buildDashboardGradingBlocker,
  buildDashboardIssueTargets,
} from "./utils/dashboardIssueTargets";
import { buildDashboardCapabilityAuditRows } from "./utils/dashboardCapabilityAuditRows";
import {
  buildDashboardCalculationOverlayStats,
  buildDashboardEngineeringMetrics,
  buildDashboardMeasurementOverlayStats,
} from "./utils/dashboardEngineeringMetrics";
import { resolveDashboardPanelStatus } from "./utils/dashboardPanelStatus";
import { resolveActivePrimaryWorkflowKey } from "./utils/dashboardPrimaryWorkflows";
import { buildDashboardPrimaryWorkflowItems } from "./utils/dashboardPrimaryWorkflowItems";
import { buildDashboardSystemEvidenceView } from "./utils/dashboardSystemEvidenceView";
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
import { buildDashboardContextualToolbarTools } from "./utils/dashboardContextualToolbar";
import {
  buildDashboardCivil3DWorkflowBlockers,
  buildDashboardWorkflowActionHints,
} from "./utils/dashboardWorkflowHints";
import { buildDashboardSiteGradingView } from "./utils/dashboardSiteGradingView";
import {
  parseDashboardDirectSiteSetupCommand,
  parseDashboardObjectCommandIntent,
} from "./utils/dashboardChatCommandParsing";
import {
  buildDashboardAutoSiteContextMessage,
  buildDashboardPreviewExplanationMessage,
  buildDashboardUsedLayoutMessage,
  buildDashboardWhatChangedMessage,
  formatDashboardChatPlacement,
} from "./utils/dashboardChatResponseView";
import {
  applyDashboardReactiveSystemStatusFromPlanResult,
  buildDashboardAssumptionsFromPlanResult,
  buildDashboardIssuesFromPlanResult,
  buildDashboardSuggestedImproveGoal,
} from "./utils/dashboardPlanResultView";
import {
  buildCustomGeometryMeta,
  clampValue,
  formatCalmActionMessage,
  getObjectDimensionsLabel,
  getObjectDisplayType,
  getObjectEditBlocker,
  getObjectLayerLabel,
  getObjectReviewLabel,
  getObjectSourceLabel,
  isCustomGeometryMode,
  normalizeGeometryPoints,
  type CustomGeometryMode,
} from "./utils/objectGeometry";



import {
  defaultAssumptions,
  toReadableLabel,
  toArray,
  parsePositiveNumber,
  formatMetric,
  summarizePlanResponse,
} from "./utils/formatting";

import {
  createChatMessage,
  createWelcomeMessage,
  extractDesignMemory,
  getChatThreadStorageKey,
} from "./utils/chat";
import {
  createDenseCommercialConceptPlacements,
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
  artifactFromJob,
  chatFailureMessage,
  formatTimestamp,
  isArtifactExportJob,
  jobDetailMessage,
  panelErrorMessage,
  uploadStatusMessage,
} from "./utils/dashboardStatus";
import { buildDashboardWorkflowState } from "./utils/dashboardWorkflowState";
import {
  buildDashboardArtifactPayload,
  buildDashboardPayloadPreview,
} from "./utils/dashboardPayloads";
import { runDashboardApplyProjectInput } from "./utils/dashboardProjectRestoreActions";
import { buildDashboardObjectSelectionView } from "./utils/dashboardObjectSelectionView";
import {
  hasAddressCoordinates,
  type AddressSuggestion,
  type AutoExistingConditionsUiStatus,
  type AutoSiteContextFlowSummary,
  type CustomerTemplateRegistryResponse,
  type GenerateFlowSummary,
  type OnlineExistingConditionsFetchResponse,
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
  buildAutoSiteContextFlowSummary,
  buildAutoSiteContextRows,
  buildPreviewSourceContextBadges,
} from "./utils/dashboardAutoSiteContext";
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
  buildDashboardProgressTimelineState,
  buildDashboardSetupWizardState,
  progressTimelineDotClass,
  progressTimelineStatusClass,
} from "./utils/dashboardWorkflowProgress";
import {
  buildDrainageLowPoints,
  buildGradingResultSummary,
  buildStormHydrologyReview,
  buildStormPipeSegments,
  buildWaterFireFlowReview,
} from "./utils/dashboardReviewSummaries";
import { buildDashboardManualFields } from "./utils/dashboardManualFields";
import { buildGenerateConceptPlacements } from "./utils/dashboardGenerateConcepts";
import {
  buildGradingDrainageReviewContextPlacements,
  type GradingDrainageReviewContextMode,
} from "./utils/dashboardReviewContextPlacements";
import {
  buildDashboardSidebarReviewState,
  buildIssueDiagnosticSummary,
} from "./utils/dashboardSidebarReview";
import { buildDashboardSystemHealthItems } from "./utils/dashboardSystemHealth";
import {
  markCivoraInteraction,
  measureCivoraInteractionAfterPaint,
} from "./utils/performanceProbes";
import {
  runDashboardPlaceBuilding,
  runDashboardPlaceObject,
  runDashboardSelectPlacementTarget,
} from "./utils/dashboardPlacementActions";
import {
  runDashboardCreateCustomGeometry,
  type DashboardCustomGeometryPayload,
} from "./utils/dashboardCustomGeometryActions";
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
import {
  runDashboardCandidateReviewDecision,
  runDashboardDesignAlternativesAction,
} from "./utils/dashboardReviewWorkflowActions";
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
import { useDashboardShellShortcuts } from "./hooks/useDashboardShellShortcuts";
import type { ParkingParams } from "./utils/previewGeometryTruth";
import type {
  ApprovalState,
  CadToolRequestForPreview,
  CapabilityExposure,
  DraftBlockDefinition,
  DraftUndoAction,
  PerformanceAIDashboardProps,
  RecentChange,
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
  buildRoadwayWorkbenchData,
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
import { SelectedObjectInspectorPanel } from "./components/SelectedObjectInspectorPanel";
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
  PlanSheetScale,
  PlanSheetSet,
  PlanSheetTitleBlock,
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
  const [mobileViewport, setMobileViewport] = useState(false);
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
  const [analysisPaths, setAnalysisPaths] = useState<
    Array<{
      id: string;
      buildingId: string;
      accessId: string;
      from: { x: number; y: number };
      to: { x: number; y: number };
      label: string;
      points?: Array<{ x: number; y: number }>;
    }>
  >([]);
  const [analysisIssues, setAnalysisIssues] = useState<
    Array<{
      id: string;
      buildingId: string;
      accessId: string;
      distanceFt: number;
      thresholdFt: number;
      message: string;
      pathId: string;
      issueType: "distance" | "no_access" | "no_buildings" | "no_access_objects";
    }>
  >([]);
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
  const [viewportFootprint, setViewportFootprint] = useState<{
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
  } | null>(null);
  const [viewportCenter, setViewportCenter] = useState<{ lat: number; lng: number } | null>(null);
  const handleViewportFootprint = useCallback((value: NonNullable<typeof viewportFootprint>) => {
    setViewportFootprint((prev) => {
      if (
        prev &&
        Math.abs(prev.widthFt - value.widthFt) < 0.01 &&
        Math.abs(prev.heightFt - value.heightFt) < 0.01 &&
        Math.abs((prev.bounds?.north ?? 0) - (value.bounds?.north ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.south ?? 0) - (value.bounds?.south ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.east ?? 0) - (value.bounds?.east ?? 0)) < 1e-7 &&
        Math.abs((prev.bounds?.west ?? 0) - (value.bounds?.west ?? 0)) < 1e-7
      ) {
        return prev;
      }
      return value;
    });
  }, []);
  const handleViewportCenter = useCallback((value: { lat: number; lng: number }) => {
    setViewportCenter((prev) => {
      if (prev && Math.abs(prev.lat - value.lat) < 1e-7 && Math.abs(prev.lng - value.lng) < 1e-7) {
        return prev;
      }
      return value;
    });
  }, []);
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
  const [lastDraftAction, setLastDraftAction] = useState<DraftUndoAction | null>(null);
  const lastDraftActionRef = useRef<DraftUndoAction | null>(null);
  const [redoDraftAction, setRedoDraftAction] = useState<DraftUndoAction | null>(null);
  const redoDraftActionRef = useRef<DraftUndoAction | null>(null);
  const [recentChanges, setRecentChanges] = useState<RecentChange[]>([]);
  const [recentChangesOpen, setRecentChangesOpen] = useState(false);
  const [jobClockMs, setJobClockMs] = useState(() => Date.now());
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const commandInputRef = useRef<HTMLTextAreaElement | null>(null);
  const siteAddressInputRef = useRef<HTMLInputElement | null>(null);
  const mapSnapshotInputRef = useRef<HTMLInputElement | null>(null);
  const planPdfInputRef = useRef<HTMLInputElement | null>(null);
  const surveyInputRef = useRef<HTMLInputElement | null>(null);
  const runSubmissionRef = useRef(false);
  const directRunAbortRef = useRef<AbortController | null>(null);
  const draftProjectPromiseRef = useRef<Promise<ProjectRecord | null> | null>(null);
  const ensureProjectDraftRef = useRef<() => Promise<string | null>>(() => Promise.resolve(null));
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

  useEffect(() => {
    lastDraftActionRef.current = lastDraftAction;
  }, [lastDraftAction]);

  useEffect(() => {
    redoDraftActionRef.current = redoDraftAction;
  }, [redoDraftAction]);

  const recordDraftUndoAction = useCallback((action: DraftUndoAction) => {
    lastDraftActionRef.current = action;
    setLastDraftAction(action);
    redoDraftActionRef.current = null;
    setRedoDraftAction(null);
  }, []);

  const recordDraftRedoAction = useCallback((action: DraftUndoAction) => {
    redoDraftActionRef.current = action;
    setRedoDraftAction(action);
  }, []);

  const clearDraftUndoAction = useCallback(() => {
    lastDraftActionRef.current = null;
    setLastDraftAction(null);
  }, []);

  useEffect(() => {
    const syncViewport = () => setMobileViewport(window.innerWidth < 1024);
    syncViewport();
    window.addEventListener("resize", syncViewport);
    if (window.innerWidth < 1024) {
      setRightRailCollapsed(true);
    }
    return () => window.removeEventListener("resize", syncViewport);
  }, []);

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

  const buildManualFields = useCallback(
    (fields: Omit<Parameters<typeof buildDashboardManualFields>[0], "buildingPlacements" | "surveySlopeEstimate" | "drainageForcedInlets" | "drainageConnectOrphans" | "drainageAllowSlopeAdjust" | "drainageMaxSlopeAdjust">) =>
      buildDashboardManualFields({
        ...fields,
        buildingPlacements: buildingPlacementsRef.current,
        surveySlopeEstimate,
        drainageForcedInlets,
        drainageConnectOrphans,
        drainageAllowSlopeAdjust,
        drainageMaxSlopeAdjust,
      }),
    [
      drainageAllowSlopeAdjust,
      drainageConnectOrphans,
      drainageForcedInlets,
      drainageMaxSlopeAdjust,
      surveySlopeEstimate,
    ],
  );

  const payloadPreview = useMemo(
    () => buildDashboardPayloadPreview({
      projectId,
      assistedEnabled,
      prompt,
      imageName,
      chatMessages: chatMessagesRef.current,
      currentProject,
      systemStatuses,
      reactiveEditPolicyPreference: REACTIVE_EDIT_POLICY_PREFERENCE,
      siteObjectId: buildingPlacements.find((item) => item.type === "site")?.id ?? null,
      manualFields: buildManualFields({
        nextSiteName: siteName,
        nextFileName: fileName,
        nextUnits: units,
        nextProjectType: projectType,
        nextLotWidth: lotWidth,
        nextLotHeight: lotHeight,
        nextSetback: setback,
        nextBuildingWidth: buildingWidth,
        nextBuildingDepth: buildingDepth,
        nextBuildingCount: buildingCount,
        nextParkingCount: parkingCount,
        nextMinSlopePct: minSlopePct,
        nextPipeMinSlopePct: pipeMinSlopePct,
        nextMaxParkingSlopePct: maxParkingSlopePct,
        nextMaxRoadGradePct: maxRoadGradePct,
        nextMaxAdaCrossSlopePct: maxAdaCrossSlopePct,
        nextRoads: roads,
        nextGrading: grading,
        nextDrainage: drainage,
        nextUtilities: utilities,
      }),
    }),
    [
      buildingPlacements,
      projectId,
      prompt,
      imageName,
      siteName,
      fileName,
      units,
      projectType,
      lotWidth,
      lotHeight,
      setback,
      buildingWidth,
      buildingDepth,
      buildingCount,
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
      systemStatuses,
      assistedEnabled,
      currentProject,
      buildManualFields,
    ],
  );

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
  const planPdfAnalysis = currentPlanMeta.plan_pdf_analysis_v1;
  const planPdfEditableSheet = currentPlanMeta.plan_pdf_editable_sheet_v1 ?? planPdfAnalysis?.editable_sheet;
  const planPdfElements = useMemo<PlanPdfElement[]>(
    () => (planPdfEditableSheet?.elements ?? []).filter((item): item is PlanPdfElement => Boolean(item?.element_id)),
    [planPdfEditableSheet?.elements],
  );
  const selectedPlanPdfElement = useMemo(
    () => planPdfElements.find((item) => item.element_id === selectedPlanPdfElementId) ?? planPdfElements[0] ?? null,
    [planPdfElements, selectedPlanPdfElementId],
  );
  const planPdfFirstPage = planPdfAnalysis?.pages?.[0] ?? null;
  const planPdfSourceUrl = planPdfAnalysis?.source_pdf?.file_url
    ? toApiUrl(`${planPdfAnalysis.source_pdf.file_url}?access_token=${encodeURIComponent(token || "")}`)
    : "";
  const planPdfSummary = planPdfAnalysis?.summary ?? {};
  const planPdfBlockers = planPdfAnalysis?.blockers ?? [];
  const planPdfChangedReport = currentPlanMeta.plan_pdf_changed_elements_v1 ?? planPdfEditableSheet?.changed_elements ?? null;
  const planPdfChangedElements = planPdfChangedReport?.elements ?? [];
  const planPdfUnreadableItems = planPdfBlockers.filter((item) => /ocr|raster|vector|unread|parser|renderer/i.test(String(item)));
  const planPdfExtractionSummaryRows = [
    ["Text", Number(planPdfSummary.text_evidence_count ?? 0)],
    ["Labels", Number(planPdfSummary.label_count ?? 0)],
    ["Dimensions", Number(planPdfSummary.dimension_count ?? 0)],
    ["Title block", Number(planPdfSummary.title_block_count ?? 0)],
    ["Scale", Number(planPdfSummary.scale_candidate_count ?? 0)],
    ["Elevations", Number(planPdfSummary.elevation_callout_count ?? 0)],
    ["Matchlines", Number(planPdfSummary.matchline_count ?? 0)],
    ["Details", Number(planPdfSummary.detail_block_count ?? 0)],
  ] satisfies Array<[string, number]>;
  const planPdfClassificationPreviewRows = [
    ["Labels", "labels"],
    ["Dimensions", "dimensions"],
    ["Title block fields", "title_blocks"],
    ["Scale candidates", "scale_candidates"],
    ["Elevation callouts", "elevation_callouts"],
    ["Matchlines", "matchlines"],
    ["Detail blocks", "detail_blocks"],
  ].map(([label, bucket]) => {
    const items = planPdfAnalysis?.classifications?.[bucket] ?? [];
    return {
      label,
      value: items
        .slice(0, 3)
        .map((item) => String(item.text ?? "").trim())
        .filter(Boolean)
        .join(" | "),
    };
  });
  const siteInputs = (currentProject?.project_input?.meta?.site_inputs ?? {}) as SiteInputs;
  useEffect(() => {
    if (selectedPlanPdfElement?.element_id && selectedPlanPdfElement.element_id !== selectedPlanPdfElementId) {
      setSelectedPlanPdfElementId(selectedPlanPdfElement.element_id);
    }
    setPlanPdfElementDraftText(selectedPlanPdfElement?.text ?? "");
    const bbox = selectedPlanPdfElement?.bbox;
    setPlanPdfMoveX(bbox?.x0 !== undefined ? String(bbox.x0) : "");
    setPlanPdfMoveY(bbox?.y0 !== undefined ? String(bbox.y0) : "");
  }, [selectedPlanPdfElement?.bbox, selectedPlanPdfElement?.element_id, selectedPlanPdfElement?.text]);
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
  const handleCandidateReviewDecision = useCallback(
    async (candidateId: string, action: "accept" | "reject" | "pending") => {
      await runDashboardCandidateReviewDecision({
        action,
        candidateId,
        currentProjectId: currentProject?.project_id,
        projectId,
        setBackendResult,
        setCurrentProject,
        setStatusMessage,
        token,
      });
    },
    [currentProject?.project_id, projectId, token],
  );
  const handleDesignAlternativesAction = useCallback(
    async (action: "generate" | "compare" | "choose" | "merge" | "revise", optionNumber?: number) => {
      await runDashboardDesignAlternativesAction({
        action,
        currentProjectId: currentProject?.project_id,
        designAlternativeCount: designAlternativeItems.length,
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
    [currentProject?.project_id, designAlternativeItems.length, projectId, token],
  );
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
  const managerMetrics = useMemo<ManagerMetrics>(
    () => currentPlanMeta?.manager_export?.metrics ?? {},
    [currentPlanMeta],
  );
  const quantityTotals = useMemo<QuantityTotals>(
    () => currentPlanMeta?.quantities?.totals ?? {},
    [currentPlanMeta],
  );
  const quantityExplain = useMemo(
    () => currentPlanMeta?.quantities?.explain ?? {},
    [currentPlanMeta],
  );
  const costEstimate = useMemo(
    () => currentPlanMeta?.cost_estimate ?? {},
    [currentPlanMeta],
  );
  const stormSummary = useMemo<StormSummary>(() => currentPlanMeta?.storm_pipes ?? {}, [currentPlanMeta]);
  const pipeSegments = useMemo(() => buildStormPipeSegments(stormSummary), [stormSummary]);
  const drainageSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.drainage ?? {}, [currentPlanMeta]);
  const gradingSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.grading ?? {}, [currentPlanMeta]);
  const roadwayWorkbenchData = useMemo(
    () => buildRoadwayWorkbenchData(currentPlanMeta),
    [currentPlanMeta],
  );
  const drainageLowPoints = useMemo(
    () => buildDrainageLowPoints({ drainageSummary, gradingSummary }),
    [drainageSummary, gradingSummary],
  );
  const stormHydrologyReview = useMemo(
    () => buildStormHydrologyReview({ stormSummary, drainageSummary, pipeSegments, smartFixItems }),
    [drainageSummary, pipeSegments, smartFixItems, stormSummary],
  );
  const waterFireFlowReview = useMemo(
    () => buildWaterFireFlowReview(planPreviewAnnotations),
    [planPreviewAnnotations],
  );
  const gradingResultSummary = useMemo(
    () => buildGradingResultSummary(gradingSummary),
    [gradingSummary],
  );

  const previewLabels = useMemo(
    () => planPreviewAnnotations?.labels ?? [],
    [planPreviewAnnotations],
  );
  const issueTargets = useMemo(
    () => buildDashboardIssueTargets(issues, previewLabels),
    [issues, previewLabels],
  );

  const [debugGradingFixtureLoaded, setDebugGradingFixtureLoaded] = useState(false);

  const gradingBlocker = useMemo(() => buildDashboardGradingBlocker(issues), [issues]);

  const selectedIssueLabel = issueTargets.find((item) => item.id === selectedIssueId)?.label ?? "";

  const engineeringMetrics = useMemo(
    () => buildDashboardEngineeringMetrics({
      managerMetrics,
      pipeSegments,
      stormSummary,
      gradingSummary,
      drainageSummary,
    }),
    [drainageSummary, gradingSummary, managerMetrics, pipeSegments, stormSummary],
  );
  const { totalPipeLength, maxSlope, minSlope, flowCfs, cutFillNet, basinSize } = engineeringMetrics;
  const quantityRows = useMemo(
    () => buildDashboardQuantityRows({ costEstimate, quantityExplain, quantityTotals }),
    [costEstimate, quantityExplain, quantityTotals],
  );
  const measurementOverlayStats = useMemo(
    () => buildDashboardMeasurementOverlayStats(quantityTotals),
    [quantityTotals],
  );
  const calculationOverlayStats = useMemo(
    () => buildDashboardCalculationOverlayStats(engineeringMetrics),
    [engineeringMetrics],
  );
  const currentTruthAudit = useMemo(
    () => currentPlanMeta?.truth_audit ?? {},
    [currentPlanMeta],
  );
  const currentManualFailures = useMemo<ManualFailure[]>(
    () =>
      Array.isArray(currentPlanMeta?.manual_validation?.failures)
        ? currentPlanMeta.manual_validation.failures
        : [],
    [currentPlanMeta],
  );
  const currentExplanation = useMemo<PlanExplanation>(
    () => currentPlanMeta?.explanation ?? {},
    [currentPlanMeta],
  );
  const suggestedImproveGoal = useMemo(
    () => buildDashboardSuggestedImproveGoal({ currentManualFailures, issues }),
    [currentManualFailures, issues],
  );

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

  const recordRecentChange = useCallback((change: Omit<RecentChange, "id" | "createdAt">) => {
    const nextChange: RecentChange = {
      ...change,
      id: `change-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      createdAt: Date.now(),
    };
    setRecentChanges((current) => [nextChange, ...current].slice(0, 12));
    setRecentChangesOpen(true);
    return nextChange;
  }, []);

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

  const resolveLotBounds = useCallback(() => {
    const width = parsePositiveNumber(lotWidth) ?? 0;
    const height = parsePositiveNumber(lotHeight) ?? 0;
    if (!width || !height) {
      const manualLotRaw =
        currentProject?.project_input &&
        typeof currentProject.project_input === "object" &&
        (currentProject.project_input as {
          manual_fields?: { lot?: { x?: number; y?: number; w?: number; h?: number } | false };
        }).manual_fields?.lot;
      const manualLot: { x?: number; y?: number; w?: number; h?: number } | null =
        manualLotRaw && typeof manualLotRaw === "object" ? manualLotRaw : null;
      if (manualLot?.w && manualLot?.h) {
        return {
          x: typeof manualLot.x === "number" ? manualLot.x : 0,
          y: typeof manualLot.y === "number" ? manualLot.y : 0,
          w: manualLot.w,
          h: manualLot.h,
        };
      }
      const site = buildingPlacements.find((item) => item.type === "site");
      if (site?.w && site?.d) {
        return { x: site.x ?? 0, y: site.y ?? 0, w: site.w, h: site.d };
      }
    }
    const site = buildingPlacements.find((item) => item.type === "site");
    return { x: site?.x ?? 0, y: site?.y ?? 0, w: width, h: height };
  }, [buildingPlacements, lotHeight, lotWidth]);

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

  const resolveDefaultBuildingDims = useCallback(() => {
    const width = parsePositiveNumber(buildingWidth) ?? SITE_OBJECT_CATALOG.building.defaultW;
    const depth = parsePositiveNumber(buildingDepth) ?? SITE_OBJECT_CATALOG.building.defaultD;
    return { w: width, d: depth };
  }, [buildingDepth, buildingWidth]);

  const hasSiteBoundary = useCallback(() => {
    const lot = resolveLotBounds();
    return Boolean(lot.w && lot.h);
  }, [resolveLotBounds]);

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


  const ensureSiteBoundary = useCallback(
    (reason: string) => {
      const hasSite = buildingPlacements.some((item) => item.type === "site");
      if (hasSite) return true;
      const width =
        parsePositiveNumber(lotWidth) ?? SITE_OBJECT_CATALOG.site.defaultW;
      const height =
        parsePositiveNumber(lotHeight) ?? SITE_OBJECT_CATALOG.site.defaultD;
      if (!parsePositiveNumber(lotWidth)) setLotWidth(String(width));
      if (!parsePositiveNumber(lotHeight)) setLotHeight(String(height));
      setBuildingPlacements((prev) => {
        const filtered = prev.filter((item) => item.type !== "site");
        const sitePlacement: BuildingPlacement = {
          id: `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: SITE_OBJECT_CATALOG.site.label,
          type: "site",
          w: width,
          d: height,
          x: 0,
          y: 0,
          rotation: 0,
          locked: true,
          placed: true,
          source: "user",
          generated: false,
          capabilities: {
            movable: false,
            resizable: false,
            rotatable: false,
            deletable: false,
          },
          systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
          meta: { category: SITE_OBJECT_CATALOG.site.category },
        };
        return [sitePlacement, ...filtered];
      });
      setStatusMessage(
        `Site boundary initialized at ${width} ft by ${height} ft. ${reason}`,
      );
      return true;
    },
    [buildingPlacements, lotHeight, lotWidth],
  );

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

  const resolveParkingParams = useCallback(
    (
      target: BuildingPlacement,
      overrides?: Partial<BuildingPlacement>,
    ): {
      stallWidth: number;
      stallDepth: number;
      aisleWidth: number;
      adaAisleWidth: number;
      adaCount: number;
      compactCount: number;
      compactWidth: number;
      angleDeg: number;
      loading: "single" | "double";
      autoResizeToFitCount: boolean;
      useMixedAngles: boolean;
      compactZone: boolean;
    } => {
      const currentMeta = (target.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
      const nextMeta = (overrides?.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
      const loading =
        nextMeta.loading === "single"
          ? "single"
          : nextMeta.loading === "double"
            ? "double"
            : currentMeta.loading === "single"
              ? "single"
              : "double";
      return {
        stallWidth: Number.isFinite(nextMeta.stallWidth) ? Number(nextMeta.stallWidth) : Number(currentMeta.stallWidth) || 9,
        stallDepth: Number.isFinite(nextMeta.stallDepth) ? Number(nextMeta.stallDepth) : Number(currentMeta.stallDepth) || 18,
        aisleWidth: Number.isFinite(nextMeta.aisleWidth) ? Number(nextMeta.aisleWidth) : Number(currentMeta.aisleWidth) || 24,
        adaAisleWidth: Number.isFinite(nextMeta.adaAisleWidth) ? Number(nextMeta.adaAisleWidth) : Number(currentMeta.adaAisleWidth) || 8,
        adaCount: Number.isFinite(nextMeta.adaCount) ? Number(nextMeta.adaCount) : Number(currentMeta.adaCount) || 0,
        compactCount: Number.isFinite(nextMeta.compactCount) ? Number(nextMeta.compactCount) : Number(currentMeta.compactCount) || 0,
        compactWidth: Number.isFinite(nextMeta.compactWidth) ? Number(nextMeta.compactWidth) : Number(currentMeta.compactWidth) || 8,
        angleDeg: Number.isFinite(nextMeta.angleDeg) ? Number(nextMeta.angleDeg) : Number(currentMeta.angleDeg) || 90,
        loading,
        autoResizeToFitCount:
          typeof nextMeta.autoResizeToFitCount === "boolean"
            ? nextMeta.autoResizeToFitCount
            : Boolean(currentMeta.autoResizeToFitCount),
        useMixedAngles:
          typeof nextMeta.useMixedAngles === "boolean"
            ? nextMeta.useMixedAngles
            : Boolean(currentMeta.useMixedAngles),
        compactZone:
          typeof nextMeta.compactZone === "boolean"
            ? nextMeta.compactZone
            : Boolean(currentMeta.compactZone),
      };
    },
    [],
  );

  const computeParkingFootprint = useCallback(
    (
      target: BuildingPlacement,
      params: {
        stallWidth: number;
        stallDepth: number;
        aisleWidth: number;
        adaAisleWidth: number;
        adaCount: number;
        compactCount: number;
        compactWidth: number;
        angleDeg: number;
        loading: "single" | "double";
      },
      stallCount: number,
    ) => {
      const rows = params.loading === "double" ? 2 : 1;
      const angleRad = (Math.max(Math.min(params.angleDeg, 89), 0) * Math.PI) / 180;
      const depthAdj = params.stallDepth / Math.cos(angleRad || 0.0001);
      const shift = Math.tan(angleRad || 0.0001) * depthAdj;
      const moduleDepth = depthAdj * rows + params.aisleWidth;
      const perModuleWidth = (stallsPerRow: number) =>
        stallsPerRow * params.stallWidth + Math.abs(shift);
      const totalStalls = Math.max(stallCount, params.adaCount + params.compactCount);
      const stallsPerRow = Math.max(1, Math.ceil(totalStalls / rows));
      const moduleWidth = perModuleWidth(stallsPerRow);
      const modulesNeeded = Math.max(1, Math.ceil(totalStalls / (stallsPerRow * rows)));
      let cols = Math.max(1, Math.ceil(Math.sqrt(modulesNeeded)));
      let rowsOfModules = Math.max(1, Math.ceil(modulesNeeded / cols));
      if (totalStalls === 0) {
        cols = 1;
        rowsOfModules = 1;
      }
      if (target.w > 0) {
        const maxCols = Math.max(1, Math.floor(target.w / moduleWidth));
        cols = Math.max(1, Math.min(cols, maxCols || 1));
      }
      if (target.d > 0) {
        const maxRows = Math.max(1, Math.floor(target.d / moduleDepth));
        rowsOfModules = Math.max(1, Math.min(rowsOfModules, maxRows || 1));
      }
      const totalCapacity = stallsPerRow * rows * cols * rowsOfModules;
      const totalWidth = moduleWidth * cols;
      const totalDepth = moduleDepth * rowsOfModules;
      return {
        w: totalWidth,
        d: totalDepth,
        maxStalls: totalCapacity,
        moduleCount: cols * rowsOfModules,
        stallsPerRow,
        moduleCols: cols,
        moduleRows: rowsOfModules,
      };
    },
    [],
  );

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

  const handleAddObject = useCallback(
    (
      type: SiteObjectType,
      options?: {
        label?: string;
        style?: Record<string, string>;
        geometryType?: "polygon" | "polyline" | "rect";
        placed?: boolean;
        width?: number;
        depth?: number;
        meta?: Record<string, unknown>;
      },
    ) => {
      const catalog = SITE_OBJECT_CATALOG[type];
      if (!catalog) return;
      clearGeneratedPreview();
      if (type === "site") {
        const width = parsePositiveNumber(lotWidth) ?? catalog.defaultW;
        const height = parsePositiveNumber(lotHeight) ?? catalog.defaultD;
        if (!parsePositiveNumber(lotWidth)) setLotWidth(String(width));
        if (!parsePositiveNumber(lotHeight)) setLotHeight(String(height));
        setBuildingPlacements((prev) => {
          const filtered = prev.filter((item) => item.type !== "site");
          const sitePlacement: BuildingPlacement = {
            id: `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            label: catalog.label,
            type: "site",
            w: width,
            d: height,
            x: 0,
            y: 0,
            rotation: 0,
            locked: true,
            placed: true,
            source: "user",
            generated: false,
            capabilities: {
              movable: false,
              resizable: false,
              rotatable: false,
              deletable: false,
            },
            systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
            meta: { category: catalog.category },
          };
          return [sitePlacement, ...filtered];
        });
        return;
      }
      if (!hasSiteBoundary()) {
        const ok = ensureSiteBoundary("You can adjust the site size anytime.");
        if (!ok) return;
      }
      const lot = resolveLotBounds();
      const existingCount =
        buildingPlacements.filter((item) => item.type === type).length + 1;
      const defaults = {
        ...(type === "building" ? resolveDefaultBuildingDims() : { w: catalog.defaultW, d: catalog.defaultD }),
        ...(options?.width ? { w: options.width } : {}),
        ...(options?.depth ? { d: options.depth } : {}),
      };
      const defaultHeight = catalog.defaultH ?? 0;
      const autoPlaced = Boolean(options?.placed);
      const clampPlacement = (value: number, size: number, total: number) =>
        Math.min(Math.max(value, 24), Math.max(24, total - size - 24));
      const smartPlacement = (() => {
        const typeKey = type === "office_building" ? "building" : type;
        const offset = Math.max(0, existingCount - 1);
        if (typeKey === "building") {
          return {
            x: clampPlacement(lot.w * 0.36 + offset * 18, defaults.w, lot.w),
            y: clampPlacement(lot.h * 0.16 + offset * 14, defaults.d, lot.h),
          };
        }
        if (typeKey === "parking") {
          return {
            x: clampPlacement(lot.w * 0.18 + offset * 18, defaults.w, lot.w),
            y: clampPlacement(lot.h * 0.40 + offset * 10, defaults.d, lot.h),
          };
        }
        if (typeKey === "basin") {
          return {
            x: clampPlacement(lot.w * 0.66, defaults.w, lot.w),
            y: clampPlacement(lot.h * 0.50, defaults.d, lot.h),
          };
        }
        if (typeKey === "outfall") {
          return {
            x: clampPlacement(lot.w * 0.86, defaults.w, lot.w),
            y: clampPlacement(lot.h * 0.62, defaults.d, lot.h),
          };
        }
        if (typeKey === "inlet" || typeKey === "manhole" || typeKey === "hydrant") {
          const defaultX =
            typeKey === "inlet" ? 0.58 : typeKey === "manhole" ? 0.72 : 0.30 + Math.min(offset, 3) * 0.10;
          return {
            x: clampPlacement(lot.w * defaultX, defaults.w, lot.w),
            y: clampPlacement(lot.h * (typeKey === "hydrant" ? 0.30 : 0.46), defaults.d, lot.h),
          };
        }
        if (typeKey === "driveway" || typeKey === "road" || typeKey === "entrance") {
          return {
            x: clampPlacement(lot.w * 0.04, defaults.w, lot.w),
            y: clampPlacement(lot.h * 0.42, defaults.d, lot.h),
          };
        }
        if (typeKey === "sidewalk") {
          return {
            x: clampPlacement(lot.w * 0.18, defaults.w, lot.w),
            y: clampPlacement(lot.h * 0.40, defaults.d, lot.h),
          };
        }
        if (typeKey === "utility_corridor") {
          const network = String(options?.meta?.network || "").toLowerCase();
          const yFactor = network === "water" ? 0.28 : network === "sanitary" ? 0.78 : network === "storm" ? 0.58 : 0.68;
          return {
            x: clampPlacement(lot.w * 0.08, defaults.w, lot.w),
            y: clampPlacement(lot.h * yFactor, defaults.d, lot.h),
          };
        }
        return {
          x: Math.min(Math.max(24, existingCount * 24), Math.max(24, lot.w - defaults.w - 24)),
          y: Math.min(Math.max(24, existingCount * 18), Math.max(24, lot.h - defaults.d - 24)),
        };
      })();
      const autoX = smartPlacement.x;
      const autoY = smartPlacement.y;
      const parkingStalls =
        type === "parking" ? parsePositiveNumber(parkingCount) ?? 0 : undefined;
      const parkingParams =
        type === "parking"
          ? {
              stallWidth: parsePositiveNumber(parkingStallWidth) ?? 9,
              stallDepth: parsePositiveNumber(parkingStallDepth) ?? 18,
              aisleWidth: parsePositiveNumber(parkingAisleWidth) ?? 24,
              adaAisleWidth: parsePositiveNumber(parkingAdaAisleWidth) ?? 8,
              adaCount: parsePositiveNumber(parkingAdaCount) ?? 0,
              compactCount: parsePositiveNumber(parkingCompactCount) ?? 0,
              compactWidth: parsePositiveNumber(parkingCompactWidth) ?? 8,
              angleDeg: parsePositiveNumber(parkingAngle) ?? 90,
              loading: parkingLoading,
              autoResizeToFitCount: false,
              useMixedAngles: false,
              compactZone: true,
            }
          : null;
      const nextPlacement: BuildingPlacement = {
        id: `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: options?.label ?? formatObjectLabel(type, existingCount),
        type,
        use: catalog.use,
        w: defaults.w,
        d: defaults.d,
        h: defaultHeight,
        x: autoPlaced ? autoX : undefined,
        y: autoPlaced ? autoY : undefined,
        rotation: 0,
        stallCount: parkingStalls,
        locked: false,
        placed: autoPlaced,
        source: "user",
        generated: false,
        capabilities: {
          movable: true,
          resizable: true,
          rotatable: true,
          deletable: true,
        },
        systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
        meta: {
          category: catalog.category,
          ...(parkingParams ? { parkingParams } : {}),
          ...(options?.style ? { style: options.style } : {}),
          ...(options?.meta ?? {}),
        },
      };
      if (type === "parking" && parkingParams) {
        const totalStalls = Math.max(
          parkingStalls ?? 0,
          parkingParams.adaCount + parkingParams.compactCount,
        );
        const footprint = computeParkingFootprint(
          nextPlacement,
          parkingParams,
          totalStalls,
        );
        nextPlacement.meta = {
          ...nextPlacement.meta,
          parkingCapacity: footprint.maxStalls,
          parkingModuleCols: footprint.moduleCols,
          parkingModuleRows: footprint.moduleRows,
        };
      }
      if (["road", "driveway", "sidewalk"].includes(type)) {
        nextPlacement.geometryType = "polyline";
        const yFactor = type === "sidewalk" ? 0.42 : 0.72;
        const endXFactor = type === "sidewalk" ? 0.64 : 0.54;
        nextPlacement.geometry = [
          [lot.w * 0.04, lot.h * yFactor],
          [lot.w * 0.24, lot.h * yFactor],
          [lot.w * endXFactor, lot.h * (type === "sidewalk" ? 0.42 : 0.54)],
        ];
        nextPlacement.capabilities = {
          movable: true,
          resizable: false,
          rotatable: false,
          deletable: true,
        };
      }
      if (options?.geometryType === "polyline") {
        nextPlacement.geometryType = "polyline";
        const network = String(options?.meta?.network || "").toLowerCase();
        const yFactor = network === "water" ? 0.28 : network === "sanitary" ? 0.78 : network === "storm" ? 0.58 : 0.68;
        const startX = network === "water" ? 0.08 : network === "sanitary" ? 0.10 : 0.52;
        const endX = network === "water" ? 0.88 : network === "sanitary" ? 0.86 : 0.86;
        const rightSideRun =
          network === "storm"
            ? ([
                [lot.w * endX, lot.h * yFactor],
                [lot.w * endX, lot.h * 0.62],
              ] as Array<[number, number]>)
            : [];
        nextPlacement.geometry = [
          [lot.w * startX, lot.h * yFactor],
          [lot.w * ((startX + endX) / 2), lot.h * yFactor],
          [lot.w * endX, lot.h * yFactor],
          ...rightSideRun,
        ];
        nextPlacement.capabilities = {
          movable: true,
          resizable: false,
          rotatable: false,
          deletable: true,
        };
      } else if (options?.geometryType === "polygon") {
        nextPlacement.geometryType = "polygon";
        nextPlacement.geometry = [
          [0, 0],
          [nextPlacement.w, 0],
          [nextPlacement.w * 0.82, nextPlacement.d],
          [nextPlacement.w * 0.18, nextPlacement.d],
        ];
      }
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      markSystemsStale(systemsImpactedByPlacement(nextPlacement));
      setActivePlacementId(autoPlaced ? null : nextPlacement.id);
      setPlacementModeEnabled(!autoPlaced);
      setPreviewMode("2d");
      setPreviewInteraction(autoPlaced ? "static" : "edit");
      recordDraftUndoAction({ action: "add", object: nextPlacement });
      recordRecentChange({
        type: "object_added",
        label: "Object added",
        detail: `${nextPlacement.label} was added as draft geometry.`,
        undo: { action: "add", object: nextPlacement },
      });
      pushRecoveryMessage(`Added ${nextPlacement.label}. Undo can remove this draft object.`);
      debugLog("add-object", {
        id: nextPlacement.id,
        type: nextPlacement.type,
      });
    },
    [
      buildingPlacements,
      clearGeneratedPreview,
      formatObjectLabel,
      hasSiteBoundary,
      askClarification,
      lotHeight,
      lotWidth,
      parkingAisleWidth,
      parkingAngle,
      parkingCount,
      parkingLoading,
      parkingStallDepth,
      parkingStallWidth,
      resolveDefaultBuildingDims,
      resolveLotBounds,
      buildDefaultPolyline,
      computeParkingFootprint,
      markSystemsStale,
      pushRecoveryMessage,
      recordRecentChange,
      systemsImpactedByPlacement,
    ],
  );

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
      siteScaleLocked,
    ],
  );

  const handleUpdateBuilding = useCallback((id: string, updates: Partial<BuildingPlacement>) => {
    clearGeneratedPreview();
    const nextUpdates = { ...updates };
    const target = buildingPlacements.find((item) => item.id === id);
    if (target?.type === "site" && (typeof updates.x === "number" || typeof updates.y === "number")) {
      const currentX = target.x ?? 0;
      const currentY = target.y ?? 0;
      const nextX = typeof updates.x === "number" ? updates.x : currentX;
      const nextY = typeof updates.y === "number" ? updates.y : currentY;
      const deltaX = nextX - currentX;
      const deltaY = nextY - currentY;
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const geocode = currentInput?.meta?.site_inputs?.geocode;
      if (geocode?.lat && geocode?.lng) {
        const metersPerDegLat = 111320;
        const metersPerDegLng = 111320 * Math.cos((geocode.lat * Math.PI) / 180);
        const dxM = deltaX * 0.3048;
        const dyM = -deltaY * 0.3048;
        const nextLat = geocode.lat + dyM / metersPerDegLat;
        const nextLng = geocode.lng + dxM / metersPerDegLng;
        const nextSiteInputs = {
          ...(currentInput?.meta?.site_inputs ?? {}),
          geocode: {
            ...(geocode ?? {}),
            lat: nextLat,
            lng: nextLng,
          },
        };
        void saveProjectRef.current?.({
          silent: true,
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
        setFitToSiteRequest((value) => value + 1);
        nextUpdates.x = 0;
        nextUpdates.y = 0;
      }
    }
    if (typeof updates.x === "number" || typeof updates.y === "number") {
      nextUpdates.placed = true;
    }
    if (
      target?.geometryType &&
      Array.isArray(target.geometry) &&
      !Array.isArray(updates.geometry) &&
      (typeof updates.x === "number" || typeof updates.y === "number")
    ) {
      const deltaX = (typeof updates.x === "number" ? updates.x : target.x ?? 0) - (target.x ?? 0);
      const deltaY = (typeof updates.y === "number" ? updates.y : target.y ?? 0) - (target.y ?? 0);
      if (Number.isFinite(deltaX) && Number.isFinite(deltaY)) {
        nextUpdates.geometry = target.geometry.map(([px, py]) => [px + deltaX, py + deltaY]);
      }
    }
    if (
      target?.geometryType &&
      Array.isArray(target.geometry) &&
      (typeof updates.w === "number" || typeof updates.d === "number")
    ) {
      const sourceGeometry = Array.isArray(nextUpdates.geometry) ? nextUpdates.geometry : target.geometry;
      const xs = sourceGeometry.map(([px]) => px);
      const ys = sourceGeometry.map(([, py]) => py);
      const minX = Math.min(...xs);
      const minY = Math.min(...ys);
      const width = Math.max(0.001, Math.max(...xs) - minX);
      const depth = Math.max(0.001, Math.max(...ys) - minY);
      const nextW = typeof updates.w === "number" && updates.w > 0 ? updates.w : target.w;
      const nextD = typeof updates.d === "number" && updates.d > 0 ? updates.d : target.d;
      const scaleX = nextW / width;
      const scaleY = nextD / depth;
      if (Number.isFinite(scaleX) && Number.isFinite(scaleY)) {
        nextUpdates.geometry = sourceGeometry.map(([px, py]) => [
          minX + (px - minX) * scaleX,
          minY + (py - minY) * scaleY,
        ]);
      }
    }
    if (target?.type === "custom") {
      const geometryType = isCustomGeometryMode(updates.geometryType ?? target.geometryType)
        ? (updates.geometryType ?? target.geometryType) as CustomGeometryMode
        : undefined;
      const geometry = Array.isArray(nextUpdates.geometry)
        ? nextUpdates.geometry
        : Array.isArray(target.geometry)
          ? target.geometry
          : undefined;
      if (geometryType && geometry?.length) {
        nextUpdates.source = "manual_drawn";
        nextUpdates.generated = false;
        nextUpdates.meta = {
          ...buildCustomGeometryMeta(
            target.id,
            updates.label ?? target.label,
            geometryType,
            geometry,
            units || "ft",
            target.meta,
          ),
          ...(updates.meta ?? {}),
        };
      }
    }
    if (target?.type === "parking") {
      const params = resolveParkingParams(target, updates);
      const stallCount = typeof updates.stallCount === "number" ? updates.stallCount : target.stallCount ?? 0;
      const totalStalls = Math.max(stallCount, params.adaCount + params.compactCount);
      const footprint = computeParkingFootprint(target, params, totalStalls);
      nextUpdates.meta = {
        ...(target.meta ?? {}),
        ...(updates.meta ?? {}),
        parkingParams: {
          ...(target.meta as { parkingParams?: ParkingParams })?.parkingParams,
          ...(updates.meta as { parkingParams?: ParkingParams })?.parkingParams,
          ...params,
        },
        parkingCapacity: footprint.maxStalls,
        parkingModuleCols: footprint.moduleCols,
        parkingModuleRows: footprint.moduleRows,
      };
      if (params.autoResizeToFitCount && totalStalls > 0) {
        nextUpdates.w = footprint.w;
        nextUpdates.d = footprint.d;
      }
    }
    const nextObject = target ? { ...target, ...nextUpdates } : null;
    let recentChange: Omit<RecentChange, "id" | "createdAt"> | null = null;
    let bulkUpdateUndo: DraftUndoAction | null = null;
    if (target && nextObject) {
      const combinedSourceIds = Array.isArray(target.meta?.combined_from_object_ids)
        ? target.meta.combined_from_object_ids.map((sourceId) => String(sourceId)).filter(Boolean)
        : [];
      const groupGeometryChanged =
        typeof updates.x === "number" ||
        typeof updates.y === "number" ||
        typeof updates.w === "number" ||
        typeof updates.d === "number" ||
        typeof updates.rotation === "number" ||
        Array.isArray(updates.geometry);
      const shouldSyncCombinedSources =
        combinedSourceIds.length > 0 &&
        (
          typeof updates.label === "string" ||
          updates.type !== undefined ||
          typeof updates.locked === "boolean" ||
          groupGeometryChanged ||
          Boolean(updates.meta && ("ui_color" in updates.meta || "color" in updates.meta || "style" in updates.meta))
        );
      if (shouldSyncCombinedSources) {
        const sourceObjects = buildingPlacements.filter((item) => combinedSourceIds.includes(item.id));
        if (sourceObjects.length) {
          const nextGroupLabel = nextObject.label || target.label;
          const nextGroupType = nextObject.type ?? target.type ?? "custom";
          const nextGroupColor = nextObject.meta?.ui_color ?? nextObject.meta?.color ?? target.meta?.ui_color ?? target.meta?.color;
          const groupOriginX = target.x ?? 0;
          const groupOriginY = target.y ?? 0;
          const nextGroupOriginX = nextObject.x ?? groupOriginX;
          const nextGroupOriginY = nextObject.y ?? groupOriginY;
          const groupScaleX = target.w > 0 && nextObject.w > 0 ? nextObject.w / target.w : 1;
          const groupScaleY = target.d > 0 && nextObject.d > 0 ? nextObject.d / target.d : 1;
          const groupCenterX = groupOriginX + target.w / 2;
          const groupCenterY = groupOriginY + target.d / 2;
          const nextGroupCenterX = nextGroupOriginX + nextObject.w / 2;
          const nextGroupCenterY = nextGroupOriginY + nextObject.d / 2;
          const rotationDeltaRadians = ((((nextObject.rotation ?? 0) - (target.rotation ?? 0)) % 360) * Math.PI) / 180;
          const cosDelta = Math.cos(rotationDeltaRadians);
          const sinDelta = Math.sin(rotationDeltaRadians);
          const transformPoint = ([px, py]: [number, number]): [number, number] => [
            nextGroupCenterX + ((px - groupCenterX) * groupScaleX) * cosDelta - ((py - groupCenterY) * groupScaleY) * sinDelta,
            nextGroupCenterY + ((px - groupCenterX) * groupScaleX) * sinDelta + ((py - groupCenterY) * groupScaleY) * cosDelta,
          ];
          const afterSources = sourceObjects.map((source) => {
            const sourceCorners: Array<[number, number]> = [
              [source.x ?? 0, source.y ?? 0],
              [(source.x ?? 0) + source.w, source.y ?? 0],
              [(source.x ?? 0) + source.w, (source.y ?? 0) + source.d],
              [source.x ?? 0, (source.y ?? 0) + source.d],
            ];
            const transformedGeometry = source.geometry?.map((point) => groupGeometryChanged ? transformPoint(point) : ([point[0], point[1]] as [number, number]));
            const boundsPoints = groupGeometryChanged ? (transformedGeometry?.length ? transformedGeometry : sourceCorners.map(transformPoint)) : sourceCorners;
            const boundsXs = boundsPoints.map(([x]) => x);
            const boundsYs = boundsPoints.map(([, y]) => y);
            const minSourceX = Math.min(...boundsXs);
            const maxSourceX = Math.max(...boundsXs);
            const minSourceY = Math.min(...boundsYs);
            const maxSourceY = Math.max(...boundsYs);
            return {
              ...source,
              x: groupGeometryChanged ? minSourceX : source.x,
              y: groupGeometryChanged ? minSourceY : source.y,
              w: groupGeometryChanged ? Math.max(1, maxSourceX - minSourceX) : source.w,
              d: groupGeometryChanged ? Math.max(1, maxSourceY - minSourceY) : source.d,
              rotation: groupGeometryChanged ? ((source.rotation ?? 0) + ((nextObject.rotation ?? 0) - (target.rotation ?? 0))) % 360 : source.rotation,
              geometry: transformedGeometry,
              capabilities: source.capabilities ? { ...source.capabilities } : source.capabilities,
            meta: {
              ...(source.meta ?? {}),
              combined_into_object_id: target.id,
              combined_into_label: nextGroupLabel,
              combined_into_type: nextGroupType,
              combined_trace_synced_at: new Date().toISOString(),
              ...(typeof updates.locked === "boolean" ? { combined_into_locked: updates.locked } : {}),
              ...(groupGeometryChanged ? { combined_transform_synced: true } : {}),
              ...(typeof nextGroupColor === "string" ? { combined_into_color: nextGroupColor } : {}),
            },
            locked: typeof updates.locked === "boolean" ? updates.locked : source.locked,
          };
        });
          bulkUpdateUndo = {
            action: "bulk_update",
            before: [target, ...sourceObjects].map((item) => ({
              ...item,
              geometry: item.geometry?.map(([x, y]) => [x, y] as [number, number]),
              meta: item.meta ? { ...item.meta } : item.meta,
              capabilities: item.capabilities ? { ...item.capabilities } : item.capabilities,
            })),
            after: [nextObject, ...afterSources],
            label: "combined object trace update",
          };
        }
      }
      const undo: DraftUndoAction = {
        action: "update",
        objectId: target.id,
        before: target,
        after: nextObject,
        label: target.label,
      };
      const changeUndo = bulkUpdateUndo ?? undo;
      if (typeof updates.label === "string" && updates.label !== target.label) {
        recentChange = {
          type: "object_renamed",
          label: "Object renamed",
          detail: `${target.label} renamed to ${updates.label || "Unnamed object"}.`,
          undo: changeUndo,
        };
      } else if (updates.type && updates.type !== target.type) {
        recentChange = {
          type: "object_type_changed",
          label: "Object type changed",
          detail: `${target.label} changed from ${getObjectDisplayType(target)} to ${SITE_OBJECT_CATALOG[updates.type]?.label ?? updates.type}.`,
          undo: changeUndo,
        };
      } else if (
        updates.meta &&
        "ui_hidden" in updates.meta &&
        Boolean(updates.meta.ui_hidden) !== Boolean(target.meta?.ui_hidden)
      ) {
        recentChange = {
          type: "object_visibility_changed",
          label: Boolean(updates.meta.ui_hidden) ? "Object hidden" : "Object shown",
          detail: `${target.label} is now ${Boolean(updates.meta.ui_hidden) ? "hidden from" : "visible in"} the preview.`,
          undo: changeUndo,
        };
      } else if (
        updates.meta &&
        ("ui_color" in updates.meta || "color" in updates.meta || "style" in updates.meta)
      ) {
        recentChange = {
          type: "object_style_changed",
          label: "Object style changed",
          detail: `${target.label} style changed.`,
          undo: changeUndo,
        };
      } else if (typeof updates.locked === "boolean" && updates.locked !== Boolean(target.locked)) {
        recentChange = {
          type: "object_style_changed",
          label: updates.locked ? "Object locked" : "Object unlocked",
          detail: `${target.label} was ${updates.locked ? "locked" : "unlocked"}.`,
          undo: changeUndo,
        };
      } else if (
        typeof updates.x === "number" ||
        typeof updates.y === "number" ||
        typeof updates.w === "number" ||
        typeof updates.d === "number" ||
        typeof updates.h === "number" ||
        typeof updates.rotation === "number" ||
        Array.isArray(updates.geometry)
      ) {
        recentChange = {
          type: "object_style_changed",
          label: "Object geometry changed",
          detail: `${target.label} geometry changed.`,
          undo: changeUndo,
        };
      }
    }
    const nextPlacements = bulkUpdateUndo?.after
      ? (() => {
          const afterById = new Map(bulkUpdateUndo.after.map((item) => [item.id, item]));
          return buildingPlacementsRef.current.map((item) =>
            afterById.has(item.id) ? { ...afterById.get(item.id)! } : item,
          );
        })()
      : buildingPlacementsRef.current.map((item) => (item.id === id ? { ...item, ...nextUpdates } : item));
    buildingPlacementsRef.current = nextPlacements;
    setBuildingPlacements(nextPlacements);
    markSystemsStale(systemsImpactedByPlacement(target));
    if (recentChange?.undo) {
      setLastDraftAction(recentChange.undo);
      recordRecentChange(recentChange);
      pushRecoveryMessage(`${recentChange.detail} Undo can restore the previous draft object state.`);
    } else {
      setStatusMessage("Object updated. Regenerate systems to reflect the new layout.");
    }
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object update...", track: true });
  }, [
    buildingPlacements,
    clearGeneratedPreview,
    computeParkingFootprint,
    currentProject,
    markSystemsStale,
    payloadPreview,
    pushRecoveryMessage,
    recordRecentChange,
    resolveParkingParams,
    systemsImpactedByPlacement,
  ]);

  const persistDetectedPlacements = useCallback(
    (nextDetected: BuildingPlacement[]) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        detected_objects: nextDetected,
      };
      void ensureProjectDraftRef.current()
        .then(() => saveProjectRef.current({
          silent: true,
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
        }));
    },
    [currentProject, payloadPreview],
  );

  const handleRemoveBuilding = useCallback((id: string) => {
    clearGeneratedPreview();
    const target = buildingPlacements.find((item) => item.id === id);
    const combinedSourceIds = target && Array.isArray(target.meta?.combined_from_object_ids)
      ? target.meta.combined_from_object_ids.map((sourceId) => String(sourceId)).filter(Boolean)
      : [];
    const relatedSourceObjects = combinedSourceIds.length
      ? buildingPlacements.filter((item) => combinedSourceIds.includes(item.id))
      : [];
    debugLog("remove-object", { id });
    const removedIds = new Set([id, ...relatedSourceObjects.map((item) => item.id)]);
    setBuildingPlacements((prev) => prev.filter((item) => !removedIds.has(item.id)));
    setActivePlacementId((prev) => (prev && removedIds.has(prev) ? null : prev));
    setSelectedObjectIds((prev) => prev.filter((itemId) => !removedIds.has(itemId)));
    setPlacementModeEnabled((prev) => (activePlacementId === id ? false : prev));
    setFocusObjectId((prev) => (prev && removedIds.has(prev) ? null : prev));
    markSystemsStale(systemsImpactedByPlacement(target));
    if (target) {
      const removedObjects = [target, ...relatedSourceObjects].map((item) => ({
        ...item,
        geometry: item.geometry?.map(([x, y]) => [x, y] as [number, number]),
        meta: item.meta ? { ...item.meta } : item.meta,
        capabilities: item.capabilities ? { ...item.capabilities } : item.capabilities,
      }));
      const undo: DraftUndoAction = removedObjects.length === 1
        ? { action: "delete", object: target }
        : { action: "delete_many", objects: removedObjects, label: "combined object delete" };
      recordDraftUndoAction(undo);
      recordRecentChange({
        type: "object_deleted",
        label: "Object deleted",
        detail: relatedSourceObjects.length
          ? `${target.label} and ${relatedSourceObjects.length} hidden source trace piece${relatedSourceObjects.length === 1 ? "" : "s"} were removed from the draft layout.`
          : `${target.label} was removed from the draft layout.`,
        undo,
      });
      pushRecoveryMessage(relatedSourceObjects.length
        ? `Deleted ${target.label} and ${relatedSourceObjects.length} hidden source trace piece${relatedSourceObjects.length === 1 ? "" : "s"}. Undo can restore the combined draft group.`
        : `Deleted ${target.label}. Undo can restore this draft object.`);
    } else {
      setStatusMessage("Object removed. Regenerate systems to reflect the new layout.");
    }
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object removal...", track: true });
  }, [activePlacementId, buildingPlacements, clearGeneratedPreview, markSystemsStale, pushRecoveryMessage, recordDraftUndoAction, recordRecentChange, systemsImpactedByPlacement]);

  const handleRestoreBuilding = useCallback((snapshot: BuildingPlacement) => {
    clearGeneratedPreview();
    setBuildingPlacements((prev) => {
      if (prev.some((item) => item.id === snapshot.id)) return prev;
      return [...prev, { ...snapshot }];
    });
    markSystemsStale(systemsImpactedByPlacement(snapshot));
    recordRecentChange({
      type: "object_added",
      label: "Object restored",
      detail: `${snapshot.label} was restored from undo.`,
      undoBlockedReason: "Restore is already an undo result; use object delete if you need to remove it again.",
    });
    pushRecoveryMessage(`Undo: restored ${snapshot.label}. Generated systems may be stale.`);
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => {
        previewRefreshIntentRef.current = {
          reason: "Refreshing preview after undo restore...",
          track: true,
        };
      });
  }, [clearGeneratedPreview, markSystemsStale, pushRecoveryMessage, recordRecentChange, systemsImpactedByPlacement]);

  const reportObjectActionBlocker = useCallback((message: string) => {
    const calmMessage = formatCalmActionMessage(message);
    setObjectManagerStatusMessage(calmMessage);
    setStatusMessage(calmMessage);
    appendChatMessage("assistant", calmMessage, "status");
  }, []);

  const persistDraftRefresh = useCallback((reason: string) => {
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => {
        previewRefreshIntentRef.current = {
          reason,
          track: true,
        };
      });
  }, [ensureProjectDraftRef, saveProjectRef]);

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

  const handleToggleBuildingLock = useCallback((id: string) => {
    const target = buildingPlacements.find((item) => item.id === id);
    if (!target) return;
    handleUpdateBuilding(id, { locked: !target.locked });
  }, [buildingPlacements, handleUpdateBuilding]);

  const dashboardPlacementActions = useMemo(() => ({
    askClarification,
    buildDefaultPolyline,
    clearGeneratedPreview,
    debugLog,
    ensureSiteBoundary,
    markSystemsStale,
    persistDraftRefresh,
    resolveDefaultBuildingDims,
    resolveLotBounds,
    setActivePlacementId,
    setBuildingPlacements,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
  }), [
    askClarification,
    buildDefaultPolyline,
    clearGeneratedPreview,
    debugLog,
    ensureSiteBoundary,
    markSystemsStale,
    persistDraftRefresh,
    resolveDefaultBuildingDims,
    resolveLotBounds,
    systemsImpactedByPlacement,
  ]);

  const handlePlaceBuilding = useCallback(
    (position: { x: number; y: number }) => {
      runDashboardPlaceBuilding({
        position,
        activePlacementId,
        buildingPlacements,
        siteScaleLocked,
        actions: dashboardPlacementActions,
      });
    },
    [activePlacementId, buildingPlacements, dashboardPlacementActions, siteScaleLocked],
  );

  const handlePlaceObject = useCallback(
    (id: string, position: { x: number; y: number }) => {
      runDashboardPlaceObject({
        id,
        position,
        buildingPlacements,
        siteScaleLocked,
        actions: dashboardPlacementActions,
      });
    },
    [buildingPlacements, dashboardPlacementActions, siteScaleLocked],
  );

  const handleCreateSiteBoundary = useCallback(
    (payload: { points: Array<[number, number]> }) => {
      clearGeneratedPreview();
      const validPoints = payload.points.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
      if (validPoints.length < 3) {
        setStatusMessage("Draw at least three points before locking a site boundary.");
        return;
      }
      const xs = validPoints.map((pt) => pt[0]);
      const ys = validPoints.map((pt) => pt[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const width = Math.max(1, maxX - minX);
      const height = Math.max(1, maxY - minY);
      if (width < 10 || height < 10) {
        setStatusMessage("Drawn site boundary is too small. Add a wider boundary or set dimensions manually.");
        return;
      }
      const normalizedGeometry = validPoints.map(([x, y]) => [x - minX, y - minY] as [number, number]);
      const acres = (width * height) / SQFT_PER_ACRE;
      const siteId = `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const nextSite: BuildingPlacement = {
        id: siteId,
        label: "Site Boundary",
        type: "site",
        x: 0,
        y: 0,
        w: Number(width.toFixed(0)),
        d: Number(height.toFixed(0)),
        rotation: 0,
        locked: true,
        placed: true,
        source: "manual_drawn",
        generated: false,
        geometryType: "polygon",
        geometry: normalizedGeometry,
        capabilities: {
          movable: false,
          resizable: false,
          rotatable: false,
          deletable: false,
        },
        systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
        meta: {
          category: "site",
          site_boundary_state: "locked_canonical",
          source: "manual_drawn",
          source_ui_mode: "canvas_draw",
          confidence: "user_drawn_review_required",
          engineering_status: "review_required",
          construction_release_allowed: false,
          units: units || "ft",
          acres: Number(acres.toFixed(3)),
          boundary_vertices: normalizedGeometry.map(([x, y], idx) => ({
            id: `${siteId}-v-${idx + 1}`,
            x,
            y,
            units: units || "ft",
          })),
        },
      };
      const nextPlacements = [
        nextSite,
        ...buildingPlacements.filter((item) => item.type !== "site"),
      ];
      const nextLotWidth = String(nextSite.w);
      const nextLotHeight = String(nextSite.d);
      const siteBoundaryGeometry: NonNullable<SiteInputs["site_boundary_geometry"]> = {
        type: "polygon",
        source: "manual_drawn",
        units: units || "ft",
        engineering_status: "review_required",
        construction_release_allowed: false,
        vertices: normalizedGeometry.map(([x, y]) => ({ x, y, units: units || "ft" })),
        bounds: {
          x: 0,
          y: 0,
          w: nextSite.w,
          h: nextSite.d,
        },
      };
      setLotWidth(nextLotWidth);
      setLotHeight(nextLotHeight);
      setSiteScaleLocked(true);
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setFitToSiteRequest((value) => value + 1);
      setBuildingPlacements(nextPlacements);
      markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
      setStatusMessage(`Site boundary locked at ${nextSite.w.toFixed(0)} ft x ${nextSite.d.toFixed(0)} ft (${acres.toFixed(2)} acres).`);

      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextManualFields = buildManualFields({
        nextSiteName: siteName,
        nextFileName: fileName,
        nextUnits: units,
        nextProjectType: projectType,
        nextLotWidth,
        nextLotHeight,
        nextSetback: setback,
        nextBuildingWidth: buildingWidth,
        nextBuildingDepth: buildingDepth,
        nextBuildingCount: buildingCount,
        nextParkingCount: parkingCount,
        nextMinSlopePct: minSlopePct,
        nextPipeMinSlopePct: pipeMinSlopePct,
        nextMaxParkingSlopePct: maxParkingSlopePct,
        nextMaxRoadGradePct: maxRoadGradePct,
        nextMaxAdaCrossSlopePct: maxAdaCrossSlopePct,
        nextRoads: roads,
        nextGrading: grading,
        nextDrainage: drainage,
        nextUtilities: utilities,
        placementsOverride: nextPlacements,
      });
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        manual_fields: nextManualFields,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: {
            ...(currentInput?.meta?.site_inputs ?? {}),
            site_alignment_locked: true,
            site_boundary_source: "manual_drawn",
            site_boundary_state: "locked_canonical",
            site_boundary_acres: Number(acres.toFixed(3)),
            site_boundary_geometry: siteBoundaryGeometry,
          },
        },
      };
      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              has_result: false,
              latest_result: undefined,
            }
          : project,
      );
      void ensureProjectDraftRef.current()
        .then(() =>
          saveProjectRef.current({
            silent: true,
            projectInputOverride: nextProjectInput,
          }),
        )
        .then(() => {
          previewRefreshIntentRef.current = {
            reason: "Refreshing preview after site boundary draw...",
            track: true,
          };
        });
    },
    [
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
      projectType,
      roads,
      setback,
      siteName,
      units,
      utilities,
    ],
  );

  const dashboardCustomGeometryActions = useMemo(() => ({
    clearGeneratedPreview,
    ensureSiteBoundary,
    markSystemsStale,
    persistDraftRefresh,
    resolveLotBounds,
    setActivePlacementId,
    setBuildingPlacements,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setPreviewMode,
    setSelectedObjectIds,
    setStatusMessage,
  }), [clearGeneratedPreview, ensureSiteBoundary, markSystemsStale, persistDraftRefresh, resolveLotBounds]);

  const handleCreateCustomGeometry = useCallback(
    (payload: DashboardCustomGeometryPayload) => {
      runDashboardCreateCustomGeometry({
        payload,
        buildingPlacementsRef,
        siteScaleLocked,
        units: units || "ft",
        actions: dashboardCustomGeometryActions,
      });
    },
    [dashboardCustomGeometryActions, siteScaleLocked, units],
  );

  const handleSelectPlacementTarget = useCallback((id: string) => {
    runDashboardSelectPlacementTarget({
      id,
      buildingPlacements,
      actions: dashboardPlacementActions,
    });
  }, [buildingPlacements, dashboardPlacementActions]);

  function askClarification(question: string, action: string, payload?: Record<string, unknown>) {
    setPendingClarification({ action, payload, question });
    setActiveSidePanel("chat");
    setChatCollapsed(false);
    appendChatMessage("assistant", question, "status");
    setStatusMessage(question);
  }

  const scheduleScaleSave = useCallback(
    (ftPerPx: number, source: "mapbox" | "manual" | "approximate") => {
      if (scaleSaveTimeoutRef.current !== null) {
        window.clearTimeout(scaleSaveTimeoutRef.current);
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      scaleSaveTimeoutRef.current = window.setTimeout(() => {
        if (!saveProjectRef.current) return;
        void saveProjectRef.current({
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
                detection_scale: {
                  distance_ft: detectionScaleFeet ? parsePositiveNumber(detectionScaleFeet) ?? undefined : undefined,
                  pixel_distance: detectionScalePixels ? parsePositiveNumber(detectionScalePixels) ?? undefined : undefined,
                  scale_ft_per_px: ftPerPx,
                  scale_source: source,
                },
                site_alignment_locked: siteScaleLocked,
              },
            },
          },
        });
      }, 600);
    },
    [currentProject, detectionScaleFeet, detectionScalePixels, payloadPreview, siteScaleLocked],
  );

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

  const buildChatDecisionContext = (
    overrides: ControlOverrides = {},
    message: string,
  ) => {
    const liveThread = chatMessagesRef.current;
    const designMemory = extractDesignMemory(liveThread);
    const storedMemory =
      currentProject?.project_input?.meta?.chat_memory &&
      typeof currentProject.project_input.meta.chat_memory === "object"
        ? currentProject.project_input.meta.chat_memory
        : null;
    const mergedPreferences = [
      ...toArray((storedMemory as { preferences?: string[] } | null)?.preferences),
      ...designMemory.preferences,
    ].slice(-8);
    const mergedConstraints = [
      ...toArray((storedMemory as { constraints?: string[] } | null)?.constraints),
      ...designMemory.constraints,
    ].slice(-8);
    return {
      strategy_mode: assistedEnabled ? "assisted" : "user",
      site_name: overrides.siteName ?? siteName,
      file_name: overrides.fileName ?? fileName,
      project_type: overrides.projectType ?? projectType,
      units: overrides.units ?? units,
      lot_width: overrides.lotWidth ?? lotWidth,
      lot_height: overrides.lotHeight ?? lotHeight,
      building_width: overrides.buildingWidth ?? buildingWidth,
      building_depth: overrides.buildingDepth ?? buildingDepth,
      setback: overrides.setback ?? setback,
      building_count: overrides.buildingCount ?? buildingCount,
      parking_count: overrides.parkingCount ?? parkingCount,
      min_slope_pct: overrides.minSlopePct ?? minSlopePct,
      pipe_min_slope_pct: overrides.pipeMinSlopePct ?? pipeMinSlopePct,
      max_parking_slope_pct: overrides.maxParkingSlopePct ?? maxParkingSlopePct,
      max_road_grade_pct: overrides.maxRoadGradePct ?? maxRoadGradePct,
      max_ada_cross_slope_pct: overrides.maxAdaCrossSlopePct ?? maxAdaCrossSlopePct,
      roads: overrides.roads ?? roads,
      grading: overrides.grading ?? grading,
      drainage: overrides.drainage ?? drainage,
      utilities: overrides.utilities ?? utilities,
      has_plan: Boolean(backendResult?.final_plan),
      has_preview: Boolean(planPreviewUrl),
      site_locked: siteScaleLocked,
      site_address: siteAddress,
      applied_address: appliedAddressLabel,
      online_source_lookup: onlineSourceLookupLabel,
      has_location_evidence: hasLocationEvidence,
      has_site_boundary: buildingPlacements.some((item) => item.type === "site"),
      has_terrain_source: hasTerrainSource,
      has_assumed_terrain_slope: hasAssumedTerrainSlope,
      has_verified_survey_control: hasVerifiedSurveyControl,
      placed_object_count: placedObjectCount,
      pending_placement_count: pendingPlacementObjects.length,
      pending_placement_objects: pendingPlacementObjects.map((item) => ({ id: item.id, label: item.label, type: item.type })),
      system_statuses: systemStatuses,
      map_analysis_success: Boolean(mapAnalysis?.success),
      setup_wizard_state_v1: setupWizardState,
      current_project: currentProject
        ? {
            project_id: currentProject.project_id,
            name: currentProject.name,
          }
        : null,
      current_explanation: currentExplanation,
      current_truth_audit: currentTruthAudit,
      engineering_status: currentPlanMeta?.engineering_status ?? {},
      convergence_summary: currentPlanMeta?.convergence_summary ?? {},
      manual_failures: currentManualFailures,
      assumptions,
      produced_deliverables: Array.isArray(currentPlanMeta?.deliverables?.produced)
        ? currentPlanMeta.deliverables.produced
        : [],
      issues,
      memory_summary: {
        preferences: mergedPreferences,
        constraints: mergedConstraints,
        open_questions: toArray((storedMemory as { open_questions?: string[] } | null)?.open_questions).slice(-6),
        examples: [...mergedPreferences, ...mergedConstraints].slice(-8),
      },
      current_phase:
        String(visibleActiveJob?.stage || "") ||
        String((currentPlanMeta?.runtime_phase_checkpoint as { stage_name?: string } | undefined)?.stage_name || ""),
      current_phase_detail: String(visibleActiveJob?.stage_detail || ""),
      progress_timeline_v1: progressTimelineState,
      chat_thread: [
        ...liveThread,
        createChatMessage("user", message),
      ].map(({ role, content, kind }) => ({ role, content, kind })),
    };
  };

  const buildPayloadFromOverrides = (
    overrides: ControlOverrides = {},
    promptOverride?: string,
    projectIdOverride?: string | null,
    placementsOverride?: BuildingPlacement[],
  ): PlanRequestPayload => {
    const nextSiteName = overrides.siteName ?? siteName;
    const nextFileName = overrides.fileName ?? fileName;
    const nextUnits = overrides.units ?? units;
    const nextProjectType = overrides.projectType ?? projectType;
    const nextRoads = overrides.roads ?? roads;
    const nextGrading = overrides.grading ?? grading;
    const nextDrainage = overrides.drainage ?? drainage;
    const nextUtilities = overrides.utilities ?? utilities;
    const nextBuildingCount = overrides.buildingCount ?? buildingCount;
    const nextMinSlopePct = overrides.minSlopePct ?? minSlopePct;
    const nextPipeMinSlopePct = overrides.pipeMinSlopePct ?? pipeMinSlopePct;
    const nextMaxParkingSlopePct = overrides.maxParkingSlopePct ?? maxParkingSlopePct;
    const nextMaxRoadGradePct = overrides.maxRoadGradePct ?? maxRoadGradePct;
    const nextMaxAdaCrossSlopePct = overrides.maxAdaCrossSlopePct ?? maxAdaCrossSlopePct;

    return {
      project_id:
        projectIdOverride !== undefined ? projectIdOverride : projectId || null,
      full_design_mode: true,
      input_mode: assistedEnabled ? "assisted" : "user",
      strict_mode: false,
      prompt_text: (promptOverride ?? prompt) || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
        system_dirty_state: systemStatuses,
        reactive_edit_policy_preference: REACTIVE_EDIT_POLICY_PREFERENCE,
        site_object_id: buildingPlacements.find((item) => item.type === "site")?.id ?? null,
        assisted_enabled: assistedEnabled,
      },
      manual_fields: buildManualFields({
        nextSiteName,
        nextFileName,
        nextUnits,
        nextProjectType,
        nextLotWidth: overrides.lotWidth ?? lotWidth,
        nextLotHeight: overrides.lotHeight ?? lotHeight,
        nextSetback: overrides.setback ?? setback,
        nextBuildingWidth: overrides.buildingWidth ?? buildingWidth,
        nextBuildingDepth: overrides.buildingDepth ?? buildingDepth,
        nextBuildingCount,
        nextParkingCount: overrides.parkingCount ?? parkingCount,
        nextMinSlopePct,
        nextPipeMinSlopePct,
        nextMaxParkingSlopePct,
        nextMaxRoadGradePct,
        nextMaxAdaCrossSlopePct,
        nextRoads,
        nextGrading,
        nextDrainage,
        nextUtilities,
        placementsOverride,
      }),
      allow_ai_fill_for_blanks: assistedEnabled,
    };
  };

  const withReactiveRerunContext = useCallback(
    (
      requestPayload: PlanRequestPayload,
      requestedSystem: "roads" | "parking" | "grading" | "drainage" | "utilities" | "full",
    ): PlanRequestPayload => {
      if (requestedSystem === "full") return requestPayload;
      const checkpointFinalPlan = backendResult?.final_plan;
      if (!checkpointFinalPlan || typeof checkpointFinalPlan !== "object") {
        return requestPayload;
      }
      const changedSystems = Object.entries(systemStatuses)
        .filter(([system, status]) => status === "stale" && system in REACTIVE_SYSTEM_STAGE_MAP)
        .map(([system]) => system as keyof typeof REACTIVE_SYSTEM_STAGE_MAP);
      if (!changedSystems.includes(requestedSystem)) {
        changedSystems.push(requestedSystem);
      }
      const changedTargets = Array.from(
        new Set(
          changedSystems.flatMap((system) => REACTIVE_SYSTEM_STAGE_MAP[system] ?? []),
        ),
      );
      if (!changedTargets.length) return requestPayload;

      const existingMeta = (requestPayload.meta ?? {}) as Record<string, unknown>;
      const existingOrchestratorMeta =
        existingMeta.orchestrator_meta && typeof existingMeta.orchestrator_meta === "object"
          ? (existingMeta.orchestrator_meta as Record<string, unknown>)
          : {};
      const existingRuntimeResume =
        existingOrchestratorMeta.runtime_resume &&
        typeof existingOrchestratorMeta.runtime_resume === "object"
          ? (existingOrchestratorMeta.runtime_resume as Record<string, unknown>)
          : {};

      return {
        ...requestPayload,
        meta: {
          ...existingMeta,
          requested_system: requestedSystem,
          changed_targets: changedTargets,
          stale_outputs: changedTargets,
          reactive_checkpoint_final_plan: checkpointFinalPlan,
          reactive_partial_rerun_request: {
            enabled: true,
            requested_system: requestedSystem,
            checkpoint_attached: true,
            changed_targets: changedTargets,
          },
          orchestrator_meta: {
            ...existingOrchestratorMeta,
            runtime_resume: {
              ...existingRuntimeResume,
              final_plan: checkpointFinalPlan,
              reactive_checkpoint_source: "web_current_backend_result",
            },
          },
        },
      };
    },
    [backendResult?.final_plan, systemStatuses],
  );

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

  const tryHandleObjectIntent = (message: string): boolean => {
    const intent = parseDashboardObjectCommandIntent(message);
    if (!intent) return false;
    const lot = resolveLotBounds();

    if (intent.kind === "grading_context") {
      appendChatMessage("user", message);
      addGradingDrainageReviewContext(
        message,
        intent.mode,
      );
      return true;
    }

    if (intent.kind === "parking_count") {
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the parking field can be added immediately.");
      }
      appendChatMessage("user", message);
      setParkingCount(String(Math.round(intent.stalls)));
      handleAddObject("parking", {
        label: `Parking Field - ${Math.round(intent.stalls)} stalls`,
        placed: true,
        meta: { command_created: true, requested_stalls: Math.round(intent.stalls) },
      });
      appendChatMessage(
        "assistant",
        `Added and placed a ${Math.round(intent.stalls)} stall parking field as draft layout geometry. It still needs review.`,
        "status",
      );
      setStatusMessage(`Added and placed ${Math.round(intent.stalls)} parking stalls as draft review geometry.`);
      return true;
    }

    if (intent.kind === "office_area") {
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the office building can be added immediately.");
      }
      appendChatMessage("user", message);
      const depth = Math.round(Math.sqrt(intent.areaSf / 1.8));
      const width = Math.round(intent.areaSf / Math.max(depth, 1));
      handleAddObject("office_building", {
        label: `Office Building - ${Math.round(intent.areaSf).toLocaleString()} sf`,
        placed: true,
        width,
        depth,
        meta: {
          command_created: true,
          requested_area_sf: Math.round(intent.areaSf),
          sizing_method: "command_area_to_review_footprint",
        },
      });
      appendChatMessage(
        "assistant",
        `Added and placed a ${Math.round(intent.areaSf).toLocaleString()} sf office building as a draft ${width} ft by ${depth} ft footprint.`,
        "status",
      );
      setStatusMessage("Office building added and placed as draft review geometry.");
      return true;
    }

    if (intent.kind === "building_dims") {
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the building can be added immediately.");
      }
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `building-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Building ${buildingPlacements.length + 1}`,
        type: "building",
        w: intent.width,
        d: intent.depth,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      recordDraftUndoAction({ action: "add", object: nextPlacement });
      appendChatMessage(
        "assistant",
        `Added a ${intent.width} ft by ${intent.depth} ft building to the placement tray. Use placement mode to drop it on the site or auto-place it.`,
        "status",
      );
      return true;
    }
    if (intent.kind === "object") {
      const typeKey = intent.type;
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the object can be added immediately.");
      }
      appendChatMessage("user", message);
      const catalog = SITE_OBJECT_CATALOG[typeKey];
      const nextLabel = formatObjectLabel(
        typeKey,
        buildingPlacements.filter((item) => item.type === typeKey).length + 1,
      );
      handleAddObject(typeKey, {
        label: formatObjectLabel(
          typeKey,
          buildingPlacements.filter((item) => item.type === typeKey).length + 1,
        ),
        placed: true,
        width: intent.width ?? catalog?.defaultW,
        depth: intent.depth ?? catalog?.defaultD,
        meta: { command_created: true },
      });
      appendChatMessage(
        "assistant",
        `Added and placed ${nextLabel} as draft review geometry.`,
        "status",
      );
      return true;
    }
    if (intent.kind === "basin") {
      if (!lot.w || !lot.h) {
        ensureSiteBoundary("Created a default review site so the basin can be added immediately.");
      }
      appendChatMessage("user", message);
      handleAddObject("basin", {
        width: intent.width,
        depth: intent.depth,
        placed: true,
        meta: { command_created: true },
      });
      appendChatMessage(
        "assistant",
        "Added and placed a basin object as draft review geometry.",
        "status",
      );
      return true;
    }
    if (intent.kind === "entrance") {
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add an entrance anchor.",
          "status",
        );
        return true;
      }
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `entrance-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Entrance ${buildingPlacements.length + 1}`,
        type: "entrance",
        w: 20,
        d: 20,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      recordDraftUndoAction({ action: "add", object: nextPlacement });
      appendChatMessage(
        "assistant",
        "Added an entrance object to the placement tray. Place it on the canvas when ready.",
        "status",
      );
      return true;
    }
    if (intent.kind === "plot_dims") {
      appendChatMessage("user", message);
      setLotWidth(String(intent.width));
      setLotHeight(String(intent.height));
      appendChatMessage(
        "assistant",
        `Set the site boundary to ${intent.width} ft by ${intent.height} ft.`,
        "status",
      );
      return true;
    }

    if (intent.kind === "plot_acres") {
      appendChatMessage("user", message);
      const area = intent.acres * 43560;
      const side = Math.sqrt(area);
      const width = Math.round(side);
      const height = Math.round(side);
      setLotWidth(String(width));
      setLotHeight(String(height));
      appendChatMessage(
        "assistant",
        `Set the site boundary to about ${width} ft by ${height} ft to match ${intent.acres} acres.`,
        "status",
      );
      return true;
    }

    return false;
  };

  const tryHandleSheetIntent = (message: string): boolean => {
    const normalized = message.toLowerCase();
    const activeSheet =
      planSheetSet.sheets.find((sheet) => sheet.id === planSheetSet.activeSheetId) ??
      planSheetSet.sheets[0];

    if (/(make|create|build).*((review\s+)?sheet|sheet set)|review sheet package|plan sheet/i.test(normalized)) {
      handleCreateReviewSheet();
      return true;
    }

    if (/edit title block|title block/i.test(normalized)) {
      const titleMatch = message.match(/title(?: block)?(?: to|:)\s*([^.;\n]+)/i);
      const sheetNoMatch = message.match(/(?:sheet number|sheet no\.?|number)(?: to|:)\s*([A-Za-z0-9.-]+)/i);
      const stageMatch = message.match(/(?:stage|review stage)(?: to|:)\s*([^.;\n]+)/i);
      const updates: Partial<PlanSheetTitleBlock> = {};
      if (titleMatch?.[1]) updates.sheetTitle = titleMatch[1].trim();
      if (sheetNoMatch?.[1]) updates.sheetNumber = sheetNoMatch[1].trim();
      if (stageMatch?.[1]) updates.reviewStage = stageMatch[1].trim();
      if (Object.keys(updates).length) {
        handlePlanSheetTitleBlockUpdate(updates);
        appendChatMessage("assistant", "Updated the active sheet title block.", "status");
      } else {
        setActiveWorkspaceMode("deliver");
        handleOpenSidePanel("deliverables");
        appendChatMessage("assistant", "Opened the sheet editor title block fields.", "status");
      }
      return true;
    }

    if (/add revision note|revision note/i.test(normalized)) {
      const noteText =
        message.match(/revision note(?: that says| saying|:)?\s*["“]?([^"”]+)["”]?/i)?.[1]?.trim() ||
        "Review revision note added; verify before package handoff.";
      handlePlanSheetAddRevision(noteText);
      appendChatMessage("assistant", `Added revision note: ${noteText}`, "status");
      return true;
    }

    if (/add note|new note|sheet note/i.test(normalized)) {
      const noteText =
        message.match(/(?:add|new)\s+(?:a\s+)?note(?: that says| saying|:)?\s*["“]?([^"”]+)["”]?/i)?.[1]?.trim() ||
        "Review note: confirm source before package handoff.";
      handlePlanSheetAddNote(noteText);
      appendChatMessage("assistant", `Added note: ${noteText}`, "status");
      return true;
    }

    if (/change scale|set scale|viewport scale|scale/i.test(normalized)) {
      const scaleMatch =
        message.match(/1\s*:\s*(10|20|30|40|50|100)/i) ||
        message.match(/1\s*(?:inch|in|")?\s*(?:equals|=)\s*(10|20|30|40|50|100)\s*(?:feet|foot|ft|')?/i);
      const scale = scaleMatch ? (`1:${scaleMatch[1]}` as PlanSheetScale) : null;
      const viewportId = activeSheet?.viewports[0]?.id;
      if (scale && viewportId) {
        handlePlanSheetScaleChange(viewportId, scale);
        appendChatMessage("assistant", `Changed the active viewport scale to ${scale}.`, "status");
      } else {
        appendChatMessage("assistant", "Tell me a supported scale like 1:20, 1:40, or 1:100.", "status");
      }
      return true;
    }

    if (/plot this review set|plot.*review set|review pdf|print package/i.test(normalized)) {
      handlePlanSheetExportPdf();
      appendChatMessage("assistant", "Opened the review PDF print package with review-only watermark and plotting standards.", "status");
      return true;
    }

    if (/why is this not for construction|not for construction/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        "This is not for construction because sheets and plots are review-only production aids. Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.",
        "status",
      );
      return true;
    }

    if (/show sheet blockers|sheet blockers|sheet blocked|show sheet needs|sheet needs/i.test(normalized)) {
      const blockers = getPlanSheetBlockers();
      appendChatMessage(
        "assistant",
        blockers.length
          ? `Sheet needs:\n${blockers.map((blocker) => `- ${formatCalmActionMessage(blocker)}`).join("\n")}`
          : "No sheet needs are recorded.",
        "status",
      );
      setActiveWorkspaceMode("deliver");
      handleOpenSidePanel("deliverables");
      return true;
    }

    return false;
  };

  const onlineDiscovery =
    (siteInputs?.online_existing_conditions_discovery_v1 ??
      (currentPlanMeta.online_existing_conditions_discovery_v1 as OnlineExistingConditionsDiscovery | undefined) ??
      {}) as OnlineExistingConditionsDiscovery;
  const mapFeatureDetectionReport =
    ((siteInputs?.map_feature_detection_report_v1 ??
      (currentPlanMeta.map_feature_detection_report_v1 as Record<string, unknown> | undefined) ??
      {}) as Record<string, unknown>);
  const siteIntelligenceSummary =
    ((onlineDiscovery.site_intelligence_summary_v1 ??
      mapFeatureDetectionReport.site_intelligence_summary_v1 ??
      {}) as Record<string, unknown>);
  const siteIntelligenceFound = Array.isArray(siteIntelligenceSummary.found)
    ? (siteIntelligenceSummary.found as Array<Record<string, unknown>>)
    : [];
  const siteIntelligenceMissing = Array.isArray(siteIntelligenceSummary.missing)
    ? (siteIntelligenceSummary.missing as Array<Record<string, unknown>>)
    : [];
  const siteIntelligenceAssumed = Array.isArray(siteIntelligenceSummary.assumed)
    ? (siteIntelligenceSummary.assumed as Array<Record<string, unknown>>)
    : [];
  const siteIntelligenceOutside = Array.isArray(siteIntelligenceSummary.outside_site)
    ? (siteIntelligenceSummary.outside_site as Array<Record<string, unknown>>)
    : [];
  const roadFrontageHint = (siteIntelligenceSummary.road_frontage ?? {}) as Record<string, unknown>;
  const drivewaySuggestion = Array.isArray(siteIntelligenceSummary.driveway_suggestions)
    ? ((siteIntelligenceSummary.driveway_suggestions as Array<Record<string, unknown>>)[0] ?? {})
    : {};
  const gradingContextHint = (siteIntelligenceSummary.grading_context ?? {}) as Record<string, unknown>;
  const onlineDiscoverySources = Array.isArray(onlineDiscovery.sources) ? onlineDiscovery.sources : [];
  const onlineFoundSources = onlineDiscoverySources.filter((source) => Number(source.candidate_count ?? 0) > 0);
  const onlineDiscoveryCandidateCount = Number(onlineDiscovery.candidate_count ?? 0);
  const localGisProviderRegistry =
    (siteInputs?.local_gis_provider_registry_v1 ??
      onlineDiscovery.local_gis_provider_registry_v1 ??
      (currentPlanMeta.local_gis_provider_registry_v1 as LocalGisProviderRegistry | undefined) ??
      {}) as LocalGisProviderRegistry;
  const localGisProviders = Array.isArray(localGisProviderRegistry.providers) ? localGisProviderRegistry.providers : [];
  const configuredLocalGisProviders = localGisProviders.filter((provider) => Boolean(provider.service_url || provider.arcgis?.service_url));
  const onlineSourceLookupUnavailable =
    hasAppliedAddress &&
    onlineDiscoveryCandidateCount === 0 &&
    String(onlineDiscovery.status || "").includes("failed");
  const onlineSourceProvidersAbsent =
    hasAppliedAddress &&
    onlineDiscoveryCandidateCount === 0 &&
    onlineDiscoverySources.length === 0 &&
    configuredLocalGisProviders.length === 0 &&
    !onlineSourceLookupUnavailable;
  const onlineSourceLookupLabel = !hasAppliedAddress
    ? "Needs address/location first"
    : onlineDiscoveryCandidateCount > 0
      ? `${onlineDiscoveryCandidateCount} candidate${onlineDiscoveryCandidateCount === 1 ? "" : "s"} for review`
      : onlineSourceLookupUnavailable
        ? "Provider lookup failed; retry source discovery."
        : onlineSourceProvidersAbsent
          ? "No source providers configured."
          : "Providers returned no usable features.";
  const autoSiteContextData = useMemo(
    () =>
      ((siteInputs?.auto_existing_conditions_v1 ??
        (currentPlanMeta as Record<string, unknown>).auto_existing_conditions_v1 ??
        {}) as Record<string, unknown>),
    [(currentPlanMeta as Record<string, unknown>).auto_existing_conditions_v1, siteInputs?.auto_existing_conditions_v1],
  );
  const autoSiteContextFlowSummary = useMemo<AutoSiteContextFlowSummary>(
    () =>
      buildAutoSiteContextFlowSummary({
        autoContext: autoSiteContextData,
        onlineDiscovery,
        autoExistingConditionsStatus,
      }),
    [autoExistingConditionsStatus, autoSiteContextData, onlineDiscovery],
  );
  const autoSiteContextRows = useMemo(
    () =>
      buildAutoSiteContextRows({
        onlineDiscovery,
        onlineDiscoverySources,
        siteIntelligenceFound,
        siteIntelligenceMissing,
        siteIntelligenceAssumed,
        siteIntelligenceOutside,
        hasAssumedTerrainSlope,
        assumedTerrainSlopePct,
      }),
    [
      assumedTerrainSlopePct,
      hasAssumedTerrainSlope,
      onlineDiscovery,
      onlineDiscoverySources,
      siteIntelligenceAssumed,
      siteIntelligenceFound,
      siteIntelligenceMissing,
      siteIntelligenceOutside,
    ],
  );
  const previewSourceContextBadges = useMemo(
    () =>
      buildPreviewSourceContextBadges({
        autoSiteContextFlowSummary,
        hasAssumedTerrainSlope,
        assumedTerrainSlopePct,
      }),
    [assumedTerrainSlopePct, autoSiteContextFlowSummary, hasAssumedTerrainSlope],
  );
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

  const tryHandleInfoIntent = (message: string): boolean => {
    const normalized = message.toLowerCase();
    const placed = buildingPlacements.filter((item) => item.placed);
    const unplaced = buildingPlacements.filter((item) => !item.placed);
    const selected = activePlacementId
      ? buildingPlacements.find((item) => item.id === activePlacementId)
      : null;

    if (/^(hi|hello|hey|yo|good\s+(morning|afternoon|evening))[\s.!?]*$/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        `Hi. I can help with casual project questions, setup commands, draw/edit commands, needs-input review, review/export questions, and focused fixes. ${progressTimelineState.next_action ? `Best next action: ${progressTimelineState.next_action}.` : nextSetupAction} Outputs stay review-required.`,
        "status",
      );
      return true;
    }

    if (/(what(’|')?s on the site|what is on the site|placed objects|site objects)/i.test(normalized)) {
      if (!placed.length) {
        appendChatMessage("assistant", "No objects are placed on the site yet.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Placed objects:\n${placed.map(formatDashboardChatPlacement).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(unplaced|in the tray|not placed)/i.test(normalized)) {
      if (!unplaced.length) {
        appendChatMessage("assistant", "All current objects are placed on the site.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Unplaced objects:\n${unplaced.map(formatDashboardChatPlacement).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(selected|current selection|what is selected)/i.test(normalized)) {
      if (!selected) {
        appendChatMessage("assistant", "Nothing is selected right now.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Selected object: ${formatDashboardChatPlacement(selected)}`,
        "status",
      );
      return true;
    }

    if (/(how.*(draw|draft|canvas)|what.*(can|should).*draw|what.*draw.*tools|finish.*(drawing|boundary|line|area|box)|stop.*(drawing|drafting)|cancel.*(drawing|drafting)|submit.*(boundary|drawing)|end.*(drawing|boundary)|where.*finish|how.*use.*(draw|cad))/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        [
          "Draw Canvas works like this:",
          "- Open Draw, then pick Draw Site Boundary, Add Line, Add Area, Add Box, or Add Point.",
          "- Click the preview to place points. The crosshair/readout shows point count and coordinates.",
          "- Press Finish to commit the boundary/object. Finish needs 3 points for a site/area, 2 points for a line/box, and 1 point for a point.",
          "- Press Cancel or Escape to stop the active draw tool without saving it.",
          "- After an object exists, use Object Manager to select, rename, recolor, change type/layer, copy, rotate, mirror, array, combine, hide, or delete it.",
          "Everything drawn this way stays editable draft/review context. Generate can use it as layout intent, but it is not survey/control or final professional evidence.",
        ].join("\n"),
        "status",
      );
      return true;
    }

    if (/(why.*(slow|lag|laggy|stuck|glitch|glitchy)|what.*(slow|lag|laggy|stuck|glitch|glitchy)|is.*(slow|laggy|stuck|glitchy)|performance|taking.*long|debug.*(speed|performance|lag))/i.test(normalized)) {
      type ChatPerfEntry = { label: string; durationMs: number };
      const perfStore =
        typeof window !== "undefined"
          ? (window as typeof window & {
              __civoraPerf?: {
                entries?: ChatPerfEntry[];
                last?: Record<string, ChatPerfEntry>;
              };
            }).__civoraPerf
          : null;
      const entries = [
        ...Object.values(perfStore?.last ?? {}),
        ...(perfStore?.entries ?? []).slice(-8),
      ].filter((entry, index, list) =>
        entry && list.findIndex((other) => other.label === entry.label) === index,
      );
      const priorityLabels = [
        "preview.mode.3d",
        "preview.mode.2d",
        "preview.quality.high",
        "preview.quality.standard",
        "preview.ai_visualization.on",
        "preview.ai_visualization.off",
        "projects.new_project",
        "projects.open_saved_project",
        "generate.panel.response.visible",
        "panel.open.generate",
        "panel.open.deliver",
        "draw.tool.add_line",
        "draw.tool.add_area",
        "preview.pan.drag",
      ];
      const sortedEntries = entries
        .sort((a, b) => {
          const aPriority = priorityLabels.indexOf(a.label);
          const bPriority = priorityLabels.indexOf(b.label);
          const normalizedA = aPriority === -1 ? 999 : aPriority;
          const normalizedB = bPriority === -1 ? 999 : bPriority;
          if (normalizedA !== normalizedB) return normalizedA - normalizedB;
          return b.durationMs - a.durationMs;
        })
        .slice(0, 8);
      const humanLabel = (label: string) =>
        label
          .replace(/^preview\./, "Preview ")
          .replace(/^projects\./, "Projects ")
          .replace(/^generate\./, "Generate ")
          .replace(/^panel\./, "Panel ")
          .replace(/^draw\./, "Draw ")
          .replace(/\./g, " ")
          .replace(/_/g, " ");
      const statusFor = (durationMs: number) => {
        if (durationMs <= 250) return "instant";
        if (durationMs <= 1000) return "normal";
        return "slow, worth checking";
      };

      appendChatMessage(
        "assistant",
        sortedEntries.length
          ? [
              "Recent UI timings from this browser:",
              ...sortedEntries.map(
                (entry) =>
                  `- ${humanLabel(entry.label)}: ${Math.round(entry.durationMs)} ms (${statusFor(entry.durationMs)})`,
              ),
              "If something feels laggy, try that action again and ask me this question again. I will compare the newest timings instead of guessing.",
            ].join("\n")
          : [
              "I do not have recent UI timing samples yet in this browser.",
              "Try opening a panel, switching 2D/3D, toggling Standard/High, drawing, or running Generate, then ask me again. I will summarize the measured timings instead of giving a generic answer.",
            ].join("\n"),
        "status",
      );
      return true;
    }

    if (/(what.*(random|weird|messy).*(circle|line|shape|stuff)|what.*(circle|line|shape).*mean|why.*(circle|line|shape|preview).*look|explain.*(preview|drawing|canvas|map)|what\s+am\s+i\s+looking\s+at|what.*on.*(canvas|preview|map|plan))/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        buildDashboardPreviewExplanationMessage({
          placed,
          buildingPlacements,
          selected: selected ?? null,
        }),
        "status",
      );
      return true;
    }

    if (/(what did.*use|what.*used.*draw|use.*my (drawing|objects|layout)|what.*from.*(drawing|objects|layout)|did.*use.*(drawing|objects|layout))/i.test(normalized)) {
      const userLayoutObjects = placed.filter((item) => {
        if (item.type === "site" || item.meta?.generated_review_concept) return false;
        const source = String(item.source || item.meta?.source || "").toLowerCase();
        return Boolean(
          item.meta?.semantic_object_model ||
          item.meta?.semantic_geometry_state ||
          item.meta?.command_created ||
          ["user", "user_confirmed", "manual_drawn", "generated"].includes(source),
        );
      });
      appendChatMessage(
        "assistant",
        buildDashboardUsedLayoutMessage({
          userLayoutObjects,
          generateFlowSummary,
          systemsImpactedByPlacement,
        }),
        "status",
      );
      return true;
    }

    if (/(what did you find here|what did.*find|what.*detected|what sources.*available|what.*site context|auto site context|found context|roads.*buildings.*terrain|why.*(didn.t|did not|didn't).*(detect|find)|why.*(roads|buildings|grading|terrain|utilities).*(missing|not found|not detected|unavailable))/i.test(normalized)) {
      appendChatMessage("assistant", buildDashboardAutoSiteContextMessage(autoSiteContextRows), "status");
      return true;
    }

    if (/(what changed|what has changed|changes|revision state|revision status)/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        buildDashboardWhatChangedMessage({
          systemStatuses,
          projectStatusSummary,
          restoreTruthLabel,
          currentProjectUpdatedAt: currentProject?.updated_at,
          hasAppliedAddress,
          appliedAddressLabel,
          onlineSourceLookupUnavailable,
          onlineSourceLookupLabel,
          siteAddress,
          placedCount: placedObjects.length,
          pendingPlacementCount: pendingPlacementObjects.length,
          hasAssumedTerrainSlope,
          hasVerifiedSurveyControl,
          generateFlowSummary,
          reviewPackageFlowSummary,
          autoSiteContextFlowSummary,
          planSheetRevisionCount: planSheetSet.revisions.length,
        }),
        "status",
      );
      return true;
    }

    if (/(what ran|what did.*run|which systems ran|what systems ran)/i.test(normalized)) {
      const freshSystems = Object.entries(systemStatuses)
        .filter(([, status]) => status === "fresh")
        .map(([system]) => system);
      appendChatMessage(
        "assistant",
        generateFlowSummary
          ? `Last Generate ran: ${generateFlowSummary.ran.join(", ") || "none"}. Current fresh systems: ${freshSystems.join(", ") || "none"}. Review-only output; engineer review is required.`
          : `No Generate run summary is recorded yet. Current fresh systems: ${freshSystems.join(", ") || "none"}.`,
        "status",
      );
      return true;
    }

    if (/(what did you skip|what.*skipped|what was skipped|skipped systems)/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        generateFlowSummary
          ? `Skipped: ${generateFlowSummary.skipped.join(", ") || "none"}. Needs review: ${generateFlowSummary.needs_review.slice(0, 5).join("; ") || "standard engineer review"}.`
          : "No skipped-system summary is recorded yet because Generate has not run in this workspace state.",
        "status",
      );
      return true;
    }

    if (/(what is blocked|what's blocked|what.*blocked|blocked right now|what needs input|needs input|what needs attention)/i.test(normalized)) {
      const flowBlockers = uniqueStrings([
        projectStatusSummary.state === "blocked" ? `${projectStatusSummary.title}: ${projectStatusSummary.detail}` : "",
        ...(generateFlowSummary?.blocked ? generateFlowSummary.needs_review : []),
        ...(reviewPackageFlowSummary?.missing ?? []),
        getExportBlockReason(),
      ]);
      appendChatMessage(
        "assistant",
        canonicalWorkspaceBlockers.length || flowBlockers.length
          ? `Needs input:\n${uniqueStrings([...canonicalWorkspaceBlockers, ...flowBlockers]).map((reason) => `- ${reason}`).join("\n")}`
          : "No current needs-input items are recorded. Outputs remain review-required.",
        "status",
      );
      return true;
    }

    if (/(what do i need next|what should i do next|what next|next step|where should i start|what do i do next)/i.test(normalized)) {
      const firstBlocker = fullGeneratePreflightBlockers[0];
      const activePlacementObject =
        activePlacementId && placementModeEnabled
          ? buildingPlacements.find((item) => item.id === activePlacementId)
          : null;
      const visibleAction = activePlacementObject
        ? `Click the canvas to place ${activePlacementObject.label}.`
        : firstBlocker
        ? `Open ${sidePanelCopy[firstBlocker.action].title} and fix: ${firstBlocker.label}.`
        : reviewPackageFlowSummary?.missing.length
          ? reviewPackageFlowSummary.next_action
          : generateFlowSummary?.needs_review.length
            ? generateFlowSummary.next_action
            : pendingPlacementObjects.length
              ? `Open Objects and place ${pendingPlacementObjects[0].label}.`
              : projectStatusSummary.nextAction || progressTimelineState.next_action || nextSetupAction;
	      appendChatMessage(
	        "assistant",
	        `${visibleAction} Current status: ${projectStatusDisplayLabel[projectStatusSummary.state]}. Current needs-input source: ${canonicalWorkspaceBlockerText} This is the next visible UI action; all outputs remain review-required.`,
        "status",
      );
      return true;
    }

    if (/(why is this review[- ]only|why.*review[- ]only|why.*engineer review|required review)/i.test(normalized)) {
      const lines = [
        "Civora is review-only because it is showing draft layouts, source evidence, assumptions, needs-input items, and generated artifacts for qualified review.",
        hasAppliedAddress
          ? `Address context is applied (${appliedAddressLabel || "coordinate context"}), but address/GIS context is not survey/control.`
          : "Address/location evidence is not fully applied yet.",
        hasAssumedTerrainSlope
          ? "Terrain slope is assumed; survey/control still needed."
          : hasVerifiedSurveyControl
            ? "Survey/control is uploaded for review but still requires professional verification."
            : "Survey/control is still missing.",
        `${placedObjects.length} design object${placedObjects.length === 1 ? "" : "s"} placed; ${pendingPlacementObjects.length} still need placement.`,
        "Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.",
      ];
      appendChatMessage("assistant", lines.join("\n"), "status");
      return true;
    }

    if (/\bshow\s+profile\b|\bprofile\s+view\b/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("profile");
      setActiveRoadwayWorkbenchTab("profile");
      appendChatMessage(
        "assistant",
        roadwayWorkbenchData.profilePoints.length
          ? `Opened the linked profile view with ${roadwayWorkbenchData.profilePoints.length} profile samples. This remains review-required evidence.`
          : "Opened the profile view. No profile samples are recorded yet, so the corridor still needs review.",
        "status",
      );
      return true;
    }

    if (/\bshow\s+(cross[-\s]?)?sections\b|\bsection\s+view\b/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("sections");
      setActiveRoadwayWorkbenchTab("section");
      appendChatMessage(
        "assistant",
        roadwayWorkbenchData.sectionPoints.length
          ? `Opened the cross-section viewer with ${roadwayWorkbenchData.sectionPoints.length} section samples. These are review-required only.`
          : "Opened the cross-section viewer. Corridor section samples are missing, so review needs remain visible.",
        "status",
      );
      return true;
    }

    if (/why\s+is\s+(the\s+)?corridor\s+blocked|corridor.*blocked/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("blockers");
      const blockers = civil3DWorkflowBlockers.length
        ? civil3DWorkflowBlockers
        : ["No corridor-specific needs-input note is recorded, but profile, section, surface, and source confidence still require review."];
      appendChatMessage(
        "assistant",
        `Corridor review needs:\n${blockers.map((item) => `- ${item}`).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/where\s+is\s+cut\/?fill\s+high|cut\/?fill\s+high|high\s+cut|high\s+fill/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("cutfill");
      const highCells = [...gradingEarthworkUx.heatmapCells]
        .sort((a, b) => Math.abs(b.deltaFt) - Math.abs(a.deltaFt))
        .slice(0, 4);
      appendChatMessage(
        "assistant",
        highCells.length
          ? `Opened cut/fill visualization. Highest review deltas: ${highCells.map((cell) => `${cell.mode} ${cell.deltaFt > 0 ? "+" : ""}${cell.deltaFt.toFixed(1)} ft`).join("; ")}.`
          : "Opened cut/fill visualization. No cut/fill cells are available yet.",
        "status",
      );
      return true;
    }

    if (/show\s+surface\s+confidence|surface\s+confidence/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      handleOpenSidePanel("roadway");
      setActiveCivil3DWorkflowTab("confidence");
      const sourceLines = sourceConfidenceRows.slice(0, 4).map((entry) =>
        `- ${entry.label || "Source entry"}: ${entry.visible_badge || entry.confidence_band || entry.source_type || "review"}`,
      );
      appendChatMessage(
        "assistant",
        sourceLines.length
          ? `Opened surface confidence. Source/control note: ${hasVerifiedSurveyControl ? "survey/control uploaded for review" : "no verified survey/control attached"}.\n${sourceLines.join("\n")}`
          : `Opened surface confidence. ${hasVerifiedSurveyControl ? "Survey/control is uploaded for review." : "No verified survey/control is attached."}`,
        "status",
      );
      return true;
    }

    if (/(what should i do next|what next|next step|where should i start|what do i do next)/i.test(normalized)) {
      const blockers = progressTimelineState.exact_blockers?.length
        ? ` Needs input: ${progressTimelineState.exact_blockers.slice(0, 3).join("; ")}.`
        : "";
      const current = progressTimelineState.current_step_label
        ? `Current step: ${progressTimelineState.current_step_label}. `
        : "";
      appendChatMessage(
        "assistant",
        `${current}${progressTimelineState.next_action || nextSetupAction}.${blockers} Everything remains review-required and limited to review evidence.`,
        "status",
      );
      return true;
    }

    if (/(show.*in\s+3d|open\s+3d|3d\s+view|show\s+this\s+3d)/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      setPreviewMode("3d");
      handleOpenSidePanel("details");
      appendChatMessage(
        "assistant",
        `Opened the 3D civil model workspace. You are looking at placed site objects, roads/paving, drainage, utilities when evidence exists, confidence badges, and terrain status. ${
          hasTerrainSource && hasGradingSurface
            ? "Terrain is shown only from available preview elevations."
            : "The site is flat because no terrain mesh source is attached to this preview."
        } Visual review does not change canonical geometry.`,
        "status",
      );
      return true;
    }

    if (/why\s+is\s+(this|it|the\s+site|terrain)\s+flat|why.*flat/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      setPreviewMode("3d");
      appendChatMessage(
        "assistant",
        hasTerrainSource && hasGradingSurface
          ? "The 3D view is using the available preview elevation samples. If it still appears flat, the preview did not include enough vertical variation or sampled terrain vertices."
          : "It is flat because no terrain mesh source is attached. The fallback plane is labeled in the 3D view, and Civora is not inventing terrain.",
        "status",
      );
      return true;
    }

    if (/show\s+low\s+confidence|low\s+confidence\s+objects|show\s+blockers|show\s+fix\s+badges/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      setPreviewMode("3d");
      handleOpenSidePanel("data");
      setPreviewLabelDensity("high");
      appendChatMessage(
        "assistant",
        sourceConfidenceRows.length
          ? `Showing source confidence and review-need badges in 3D. Low-confidence entries: ${sourceConfidenceRows
              .filter((entry) => entry.confidence_band !== "higher")
              .slice(0, 4)
              .map((entry) => entry.label || entry.source_name || "source entry")
              .join("; ") || "none in the visible source map"}.`
          : "Showing 3D confidence badges. No source confidence entries are available yet.",
        "status",
      );
      return true;
    }

    if (/show\s+utilities\s+(in\s+)?3d|utilities\s+in\s+3d|show\s+utility\s+network/i.test(normalized)) {
      setActiveWorkspaceMode("canvas");
      setPreviewMode("3d");
      handleOpenSidePanel("utilities");
      setPreviewLayers((prev) => ({ ...prev, utilities: true, drainage: true }));
      appendChatMessage(
        "assistant",
        "Utilities are enabled in the 3D workspace where utility evidence exists. Depth, pressure, and elevation are not inferred when missing.",
        "status",
      );
      return true;
    }

    if (/(can i export|can we export|export now|why.*export|can(?:not|'t) export|export.*blocked|why.*download)/i.test(normalized)) {
      const reason = getExportBlockReason();
      const exportBlockers = [
        ...(progressTimelineState.export_blockers ?? []),
        ...previewBlockedReasons,
        ...(reviewPackageFlowSummary?.missing ?? []),
      ].filter(Boolean);
	      const blockerText = exportBlockers.length
	        ? ` Current export/review needs: ${Array.from(new Set(exportBlockers)).slice(0, 4).join("; ")}.`
	        : "";
      appendChatMessage(
        "assistant",
        reason
	          ? `Export needs input: ${reason}.${blockerText}`
          : `Exports are available only as engineer-review packages. Field use is outside Civora and requires independent licensed-professional review.${blockerText}`,
        "status",
      );
      return true;
    }

    if (/(stamp|seal|sign|submit|construction[- ]ready|approve.*construction|engineer of record)/i.test(normalized)) {
      appendChatMessage(
        "assistant",
        "No. Civora cannot stamp, seal, sign, certify, submit, approve construction, or act as engineer of record. Civora can prepare review evidence packages, calculations, reports, exports, assumptions, needs, and traceability for qualified review. Field use and professional responsibility remain outside Civora.",
        "status",
      );
      return true;
    }

    if (/(issues|conflicts|problems)/i.test(normalized)) {
      if (!issues.length) {
        appendChatMessage("assistant", "No issues are reported on the latest run.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Issues:\n${issues.slice(0, 6).map((item) => `- ${item.message}`).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(blocked|needs input|needs attention|why.*(drainage|utilities|grading))/i.test(normalized)) {
      const blockers = [
        ...(progressTimelineState.exact_blockers ?? []),
        ...previewBlockedReasons,
      ].filter(Boolean);
      if (!blockers.length) {
        appendChatMessage(
          "assistant",
          topSmartFix?.one_action_needed_next
            ? `No needs-input text is currently recorded, but the smart-fix panel recommends: ${topSmartFix.one_action_needed_next}`
            : "No needs-input items are currently recorded in the active project metadata.",
          "status",
        );
        return true;
      }
      appendChatMessage(
        "assistant",
        `Needs input:\n${Array.from(new Set(blockers)).map((reason) => `- ${reason}`).join("\n")}`,
        "status",
      );
      return true;
    }

    if (/(smart\s*fix|best fix|what.*fix|fix request|can civora fix)/i.test(normalized)) {
      if (!topSmartFix) {
        appendChatMessage(
          "assistant",
          workflowActionHints[0]
            ? `Best available fix path: ${workflowActionHints[0]} Review responsibility remains outside Civora.`
            : "No smart-fix recommendation is recorded yet. Run or load a project so Civora can tie fixes to needs and evidence.",
          "status",
        );
        return true;
      }
      appendChatMessage(
        "assistant",
        [
          topSmartFix.can_civora_fix ? "Civora has a focused fix available." : "This needs user/source input before Civora can fix it.",
          topSmartFix.one_action_needed_next ? `Exact fix: ${topSmartFix.one_action_needed_next}` : null,
          topSmartFix.missing_user_input_or_source ? `Missing input/source: ${topSmartFix.missing_user_input_or_source}` : null,
          topSmartFix.what_happens_after_fix ? `After fix: ${topSmartFix.what_happens_after_fix}` : null,
          "Any output remains review-required.",
        ].filter(Boolean).join(" "),
        "status",
      );
      return true;
    }

    if (/(drainage stats|storm stats|pipe length|metrics|quantities)/i.test(normalized)) {
      if (!totalPipeLength && !maxSlope && !minSlope && !flowCfs && !cutFillNet && !basinSize) {
        appendChatMessage("assistant", "Drainage stats are not available yet.", "status");
        return true;
      }
      const metricLines = [
        totalPipeLength ? `Total pipe length: ${formatMetric(totalPipeLength, "ft")}` : null,
        maxSlope ? `Max slope: ${formatMetric(maxSlope, "%")}` : null,
        minSlope ? `Min slope: ${formatMetric(minSlope, "%")}` : null,
        flowCfs ? `Flow: ${formatMetric(flowCfs, "cfs")}` : null,
        cutFillNet ? `Cut/Fill net: ${formatMetric(cutFillNet, "cf")}` : null,
        basinSize ? `Pond size: ${formatMetric(basinSize, "sf")}` : null,
      ].filter(Boolean);
      appendChatMessage("assistant", metricLines.join("\n"), "status");
      return true;
    }

    if (/(systems|generated systems|what systems)/i.test(normalized)) {
      const enabled = [
        previewLayers.buildings ? "buildings" : null,
        previewLayers.roads ? "roads/parking" : null,
        previewLayers.grading ? "grading" : null,
        previewLayers.drainage ? "drainage/storm" : null,
        previewLayers.utilities ? "utilities" : null,
        previewLayers.structures ? "structures" : null,
      ].filter(Boolean);
      appendChatMessage(
        "assistant",
        `Preview layers enabled: ${enabled.length ? enabled.join(", ") : "none"}.`,
        "status",
      );
      return true;
    }

    return false;
  };

  const tryHandleActionIntent = (message: string): boolean => {
    const normalized = message.toLowerCase();
    const tokens = normalized.split(/\s+/);
    const allObjects = buildingPlacements;

    const findByLabel = (label: string) =>
      allObjects.find((item) => item.label.toLowerCase() === label.toLowerCase());
    const matchByKeyword = (keyword: string) =>
      allObjects.filter((item) =>
        item.label.toLowerCase().includes(keyword) ||
        (item.type ?? "").toLowerCase() === keyword,
      );

    const numberMatch = normalized.match(/(?:building|basin|entrance)\s*(\d+)/i);
    const keywordMatch = tokens.find((token) =>
      ["building", "basin", "entrance", "site", "road", "parking"].includes(token),
    );
    const selected = activePlacementId
      ? allObjects.find((item) => item.id === activePlacementId)
      : null;

    const targetFromNumber = numberMatch
      ? findByLabel(`${numberMatch[0].charAt(0).toUpperCase()}${numberMatch[0].slice(1)}`)
      : null;
    const targetFromKeyword = keywordMatch
      ? matchByKeyword(keywordMatch).filter((item) => item.placed)
      : [];

    const resolveTarget = () => {
      if (targetFromNumber) return targetFromNumber;
      if (selected) return selected;
      if (targetFromKeyword.length === 1) return targetFromKeyword[0];
      return null;
    };

    if (normalized.startsWith("select ")) {
      const label = message.replace(/^select\s+/i, "").replace(/^(the|a|an)\s+/i, "").trim();
      const target =
        findByLabel(label) ||
        allObjects.find((item) => item.label.toLowerCase().includes(label.toLowerCase())) ||
        (matchByKeyword(label).length === 1 ? matchByKeyword(label)[0] : null);
      if (target) {
        setActivePlacementId(target.id);
        setStatusMessage(`Selected ${target.label}.`);
        appendChatMessage("assistant", `Selected ${target.label}.`, "status");
        return true;
      }
      appendChatMessage("assistant", "I couldn't find that object. Try 'select Building 1' or 'select basin 1'.", "status");
      return true;
    }

    if (/(delete|remove)\b/.test(normalized)) {
      const target = resolveTarget();
      if (target) {
        handleRemoveBuilding(target.id);
        appendChatMessage("assistant", `Removed ${target.label}.`, "status");
        return true;
      }
      appendChatMessage("assistant", "Which object should I remove? You can say 'remove Building 1'.", "status");
      return true;
    }

    if (/(make|classify|change|convert).*\b(building|road|parking|basin|detention|pond|line|area|rectangle)\b/.test(normalized)) {
      const target = resolveTarget();
      const requestedType: SiteObjectType | null = /basin|detention|pond/.test(normalized)
        ? "basin"
        : /parking/.test(normalized)
          ? "parking"
          : /road|line/.test(normalized)
            ? "road"
            : /building|rectangle/.test(normalized)
              ? "building"
              : null;
      if (!requestedType) return false;
      if (!target) {
        appendChatMessage(
          "assistant",
          `Select a drawn object first, then say "make this a ${SITE_OBJECT_CATALOG[requestedType].label.toLowerCase()}."`,
          "status",
        );
        return true;
      }
      if (target.type === "site") {
        appendChatMessage("assistant", "The site boundary cannot be reclassified. Draw or select a separate object first.", "status");
        return true;
      }
      const nextLabel = formatObjectLabel(
        requestedType,
        buildingPlacements.filter((item) => item.id !== target.id && item.type === requestedType).length + 1,
      );
      handleUpdateBuilding(target.id, {
        type: requestedType,
        label: nextLabel,
        use: SITE_OBJECT_CATALOG[requestedType].use,
        source: target.source ?? "user",
        meta: {
          ...(target.meta ?? {}),
          category: SITE_OBJECT_CATALOG[requestedType].category,
          classification_status: "draft_review_required",
        },
      });
      appendChatMessage(
        "assistant",
        `Reclassified ${target.label} as ${SITE_OBJECT_CATALOG[requestedType].label}. This is draft geometry and still requires engineer review.`,
        "status",
      );
      return true;
    }

    if (/(place|re-?place|move)\b/.test(normalized) && !/\b(pdf|plan|label|sheet)\b/.test(normalized)) {
      const target = resolveTarget();
      if (target) {
        handleSelectPlacementTarget(target.id);
        return true;
      }
      if (allObjects.length === 0) {
        appendChatMessage("assistant", "There are no objects to place yet. Add a building first.", "status");
        return true;
      }
      appendChatMessage("assistant", "Which object should I place? For example, 'place Building 1'.", "status");
      return true;
    }

    if (/(bigger|smaller|resize|scale|shrink|grow)\b/.test(normalized)) {
      const target = resolveTarget();
      if (!target) {
        appendChatMessage("assistant", "Which object should I resize? For example, 'make Building 1 bigger'.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `How should I resize ${target.label}? Give me a size like "set to 120 ft by 60 ft".`,
        "status",
      );
      return true;
    }

    if (/(generate|run)\b/.test(normalized)) {
      if (/roads|circulation/.test(normalized)) {
        void handleGenerateSystem("roads");
        return true;
      }
      if (/parking/.test(normalized)) {
        void handleGenerateSystem("parking");
        return true;
      }
      if (/grading|contours/.test(normalized)) {
        void handleGenerateSystem("grading");
        return true;
      }
      if (/drainage|storm/.test(normalized)) {
        void handleGenerateSystem("drainage");
        return true;
      }
      if (/utilities|utility/.test(normalized)) {
        void handleGenerateSystem("utilities");
        return true;
      }
      if (/full|all|everything/.test(normalized)) {
        void handleGenerateSystem("full");
        return true;
      }
    }

    if (/(fix|improve)\b/.test(normalized)) {
      const nextHint = workflowActionHints[0];
      if (nextHint) {
        const targetPanel: SidePanelKey =
          nextHint.startsWith("Setup panel")
            ? "site_existing"
            : nextHint.startsWith("Data panel")
              ? "data"
              : nextHint.startsWith("Objects panel")
                ? "objects"
                : nextHint.startsWith("Generate Systems panel")
                  ? "generate"
                  : nextHint.startsWith("Deliver panel")
                    ? "deliverables"
                    : "reports";
        handleOpenSidePanel(targetPanel);
        appendChatMessage(
          "assistant",
          `Next fix: ${nextHint} I opened the ${sidePanelCopy[targetPanel].title} panel. Civora can prepare review evidence only; independent professional review remains required.`,
          "status",
        );
        return true;
      }
      appendChatMessage(
        "assistant",
        "I do not see a single automatic fix to apply. Open Review for needs, or ask for a specific action like 'fix drainage' or 'improve parking'.",
        "status",
      );
      return true;
    }

    return false;
  };

  const shouldRouteToOrchestrator = (message: string): boolean => {
    const normalized = message.toLowerCase();
    if (normalized.length < 140) return false;
    const asksForDesign =
      /\b(design|create|generate|produce|engineer|layout|site plan|development)\b/.test(normalized);
    const describesScope =
      /\b(include|with|building|road|parking|grading|drainage|utilities|detention|basin|sanitary|water)\b/.test(
        normalized,
      );
    return asksForDesign && describesScope;
  };

  const focusCommandInput = useCallback(() => {
    setShortcutsOverlayOpen(false);
    setCommandBarExpanded(true);
    setRightRailCollapsed(true);
    setSidePanelVisible(false);
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setWorkspaceChromeMinimized(true);
    setPlacementModeEnabled(false);
    setPreviewInteraction("static");
    setCadToolRequest({ id: Date.now() + Math.random(), tool: "select" });
    window.requestAnimationFrame(() => {
      const input =
        commandInputRef.current ??
        (document.querySelector(
          '[data-testid="civora-command-input"], textarea[placeholder="Ask Civora..."], textarea[placeholder^="Message Civora"]',
        ) as HTMLTextAreaElement | null);
      if (!input) {
        updateProjectStatus({
          state: "blocked",
          area: "chat",
          title: "Command focus needs attention",
          detail: "Command input is not mounted.",
          nextAction: "Open the chat panel or return to the canvas, then try / again.",
        });
        return;
      }
      input.focus();
      input.select();
    });
  }, [updateProjectStatus]);

  const refuseUnsafeConstructionCommand = (message: string) => {
    appendChatMessage("user", message);
    appendChatMessage(
      "assistant",
      "I can't stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record. I can help prepare review-only draft materials and call out needs for a qualified professional to review.",
      "status",
    );
    updateProjectStatus({
      state: "blocked",
      area: "chat",
      title: "Command refused",
      detail: "Construction authorization refused. Civora stays review-only.",
      nextAction: "Ask for review-only draft materials, blocker review, or a review package instead.",
    });
    return true;
  };

  const handleCreateDenseCommercialConcept = useCallback((message: string) => {
    appendChatMessage("user", message);
    const createdConceptSite = !hasSiteBoundary();
    if (createdConceptSite) {
      setLotWidth("1000");
      setLotHeight("1000");
      setSiteScaleLocked(true);
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setBuildingPlacements((prev) => [
        {
          id: `concept-site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: "Concept Site Boundary - 1000 ft x 1000 ft",
          type: "site",
          w: 1000,
          d: 1000,
          x: 0,
          y: 0,
          rotation: 0,
          locked: true,
          placed: true,
          source: "user",
          generated: false,
          capabilities: { movable: false, resizable: false, rotatable: false, deletable: false },
          systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
          meta: {
            category: "site",
            source_ui_mode: "chat_concept",
            site_boundary_state: "locked_concept_review_frame",
            engineering_status: "review_required",
            draft_review_required: true,
            construction_release_allowed: false,
            acres: Number((1_000_000 / SQFT_PER_ACRE).toFixed(3)),
          },
        },
        ...prev.filter((item) => item.type !== "site"),
      ]);
    }
    clearGeneratedPreview();
    const lot = createdConceptSite ? { w: 1000, h: 1000 } : resolveLotBounds();
    const conceptObjects = createDenseCommercialConceptPlacements(lot);
    setBuildingPlacements((prev) => {
      const keep = prev.filter((item) => item.type === "site" || !item.meta?.dense_concept_generated);
      return [...keep, ...conceptObjects];
    });
    markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
    setActivePlacementId(null);
    setPlacementModeEnabled(false);
    setPreviewMode("2d");
    setPreviewQuality("high");
    setPreviewInteraction("static");
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    setRightRailCollapsed(true);
    setFitToSiteRequest((value) => value + 1);
    recordRecentChange({
      type: "object_added",
      label: "Dense concept plan created",
      detail: "Office, parking, basin, driveway, sidewalks, water, sanitary, storm, inlet, outfall, hydrant, and manhole draft objects were placed.",
    });
    updateProjectStatus({
      state: "needs review",
      area: "setup",
      title: "Dense review concept created",
      detail: createdConceptSite
        ? "Created a 1000 ft by 1000 ft concept site and placed coherent editable building, parking, drainage, utilities, access, and sidewalk objects."
        : "Placed a coherent editable concept with building, parking, drainage, utilities, access, and sidewalk objects.",
      nextAction: "Edit the objects directly, then run Generate when the layout looks right.",
    });
    appendChatMessage(
      "assistant",
      createdConceptSite
        ? "Created a dense editable review concept on a 1000 ft by 1000 ft concept site: office building, two parking fields, detention basin, loop drive, driveway, sidewalk/ADA route, public water, public sanitary, storm sewer, inlets, outfall, hydrants, and sanitary manhole. Everything is draft review geometry and can be edited before Generate."
        : "Created a dense editable review concept: office building, two parking fields, detention basin, loop drive, driveway, sidewalk/ADA route, public water, public sanitary, storm sewer, inlets, outfall, hydrants, and sanitary manhole. Everything is draft review geometry and can be edited before Generate.",
      "status",
    );
    return true;
  }, [
    appendChatMessage,
    clearGeneratedPreview,
    hasSiteBoundary,
    markSystemsStale,
    recordRecentChange,
    resolveLotBounds,
    updateProjectStatus,
  ]);

  const tryHandleSiteProgramCommand = (message: string): boolean => {
    const lower = message.toLowerCase();
    if (!/\b(add|create|place|make|include|put|recreate|copy|draft|draw|layout|produce)\b/.test(lower)) return false;
    const wantsDensePlan =
      /\b(dense|full|complete|professional|civil|utility design|site plan|plan sheet|like the image|like this image|recreate|copy this|as many|detailed|realistic)\b/.test(
        lower,
      ) &&
      (/\b(office|building|parking|basin|detention|drainage|storm|water|sanitary|sidewalk|driveway|utilities|roads?|site|plan|image|sheet|stuff|layout)\b/.test(
        lower,
      ) ||
        /\b(recreate|copy|like the image|like this image)\b/.test(lower));
    if (
      wantsDensePlan
    ) {
      return handleCreateDenseCommercialConcept(message);
    }
    const lot = resolveLotBounds();
    const requested: Array<() => void> = [];
    const labels: string[] = [];
    const officeArea = lower.match(/(\d{3,8})\s*(?:sf|sq\s*ft|square\s*feet)\s+(?:office\s+)?building/);
    if (officeArea || /\boffice building\b/.test(lower)) {
      const area = officeArea ? Number(officeArea[1]) : null;
      const depth = area ? Math.round(Math.sqrt(area / 1.8)) : undefined;
      const width = area && depth ? Math.round(area / Math.max(depth, 1)) : undefined;
      requested.push(() => handleAddObject("office_building", {
        label: area ? `Office Building - ${Math.round(area).toLocaleString()} sf` : undefined,
        placed: true,
        width,
        depth,
        meta: area ? { requested_area_sf: Math.round(area), command_created: true } : { command_created: true },
      }));
      labels.push(area ? `${Math.round(area).toLocaleString()} sf office building` : "office building");
    }
    const parking = lower.match(/(\d{1,5})\s+(?:parking\s+)?(?:spaces|stalls)/);
    if (parking || /\bparking\b/.test(lower)) {
      const stalls = parking ? Number(parking[1]) : parsePositiveNumber(parkingCount) ?? 140;
      const fieldWidth = Math.max(260, Math.min((lot.w || 1000) * 0.48, Math.ceil(stalls / 2) * 9 + 36));
      const fieldDepth = Math.max(120, Math.min((lot.h || 1000) * 0.20, 18 * 2 + 24 + Math.ceil(stalls / 70) * 42));
      requested.push(() => {
        setParkingCount(String(Math.round(stalls)));
        handleAddObject("parking", {
          label: `Parking Field - ${Math.round(stalls)} stalls`,
          placed: true,
          width: fieldWidth,
          depth: fieldDepth,
          meta: { command_created: true, requested_stalls: Math.round(stalls) },
        });
      });
      labels.push(`${Math.round(stalls)} parking stalls`);
    }
    if (/\b(basin|detention|pond)\b/.test(lower)) {
      requested.push(() => handleAddObject("basin", { placed: true, meta: { command_created: true } }));
      labels.push("detention basin");
    }
    if (/\b(driveway|drive aisle|access)\b/.test(lower)) {
      requested.push(() => handleAddObject("driveway", { placed: true, meta: { command_created: true } }));
      labels.push("driveway/access");
    }
    if (/\b(sidewalk|sidewalks|ada route|ada routes|path|paths)\b/.test(lower)) {
      requested.push(() => handleAddObject("sidewalk", { label: "Sidewalk / ADA Route", placed: true, meta: { command_created: true, routeKind: "ada_review_route" } }));
      labels.push("sidewalk / ADA route");
    }
    if (/\b(public water|water line|water)\b/.test(lower)) {
      requested.push(() => handleAddObject("utility_corridor", { label: "Public Water Line", geometryType: "polyline", placed: true, meta: { network: "water", command_created: true } }));
      labels.push("public water line");
    }
    if (/\b(public sanitary|sanitary|sewer)\b/.test(lower)) {
      requested.push(() => handleAddObject("utility_corridor", { label: "Public Sanitary Line", geometryType: "polyline", placed: true, meta: { network: "sanitary", command_created: true } }));
      labels.push("public sanitary line");
    }
    if (/\bstorm\b/.test(lower)) {
      requested.push(() => handleAddObject("utility_corridor", { label: "Storm Sewer", geometryType: "polyline", placed: true, meta: { network: "storm", command_created: true } }));
      labels.push("storm sewer");
    }
    if (/\boutfall\b/.test(lower)) {
      requested.push(() => handleAddObject("outfall", { placed: true, meta: { command_created: true, role: "storm_outfall_review_point" } }));
      labels.push("outfall");
    }
    if (/\binlet\b/.test(lower)) {
      requested.push(() => handleAddObject("inlet", { placed: true, meta: { command_created: true, role: "storm_inlet_review_point" } }));
      labels.push("inlet");
    }
    if (requested.length < 2) return false;
    appendChatMessage("user", message);
    if (!hasSiteBoundary()) {
      appendChatMessage(
        "assistant",
        "I understood the site program, but I need a site boundary before I can place those objects at project scale. Tell me the address and site size, or draw/lock the site first.",
        "status",
      );
      handleOpenSidePanel("site_existing");
      return true;
    }
    requested.forEach((action) => action());
    setActivePlacementId(null);
    setPreviewInteraction("static");
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    setRightRailCollapsed(true);
    appendChatMessage(
      "assistant",
      `Added and placed ${labels.join(", ")} as draft review objects. They are editable on the canvas and still require review before Generate/Deliver.`,
      "status",
    );
    return true;
  };

  const tryHandlePowerCommand = (message: string): boolean => {
    const normalized = message.trim().toLowerCase().replace(/\s+/g, " ");
    if (!normalized) return false;
    if (/\b(stamp|seal|sign|certify|approve construction|submit construction documents|engineer of record|eor)\b/.test(normalized)) {
      return refuseUnsafeConstructionCommand(message);
    }
    const directSiteSetup = parseDashboardDirectSiteSetupCommand(message, siteAddress.trim());
    if (directSiteSetup) {
      appendChatMessage("user", message);
      clearGeneratedPreview();
      const wantsProgramAfterSiteSetup =
        /\b(office|building|parking|spaces|stalls|basin|detention|pond|storm|water|sanitary|sewer|sidewalk|ada|driveway|road|grading|drainage|utilities|utility)\b/i.test(message) &&
        /\b(add|include|create|make|generate|design|layout|put|place|with)\b/i.test(message);
      setSiteAddress(directSiteSetup.address);
      setLotWidth(String(Math.round(directSiteSetup.width)));
      setLotHeight(String(Math.round(directSiteSetup.height)));
      autoFitSite(
        directSiteSetup.width,
        directSiteSetup.height,
        "Site Boundary",
        undefined,
        true,
        true,
      );
      if (wantsProgramAfterSiteSetup) {
        const conceptObjects = createDenseCommercialConceptPlacements({
          w: directSiteSetup.width,
          h: directSiteSetup.height,
        }).map((item) => ({
          ...item,
          meta: {
            ...(item.meta ?? {}),
            command_created: true,
            command_source: "site_setup_program_command",
          },
        }));
        setParkingCount("140");
        setBuildingPlacements((prev) => [
          ...prev.filter((item) => item.type === "site" || !item.meta?.dense_concept_generated),
          ...conceptObjects,
        ]);
        markSystemsStale(["roads", "parking", "grading", "drainage", "utilities"]);
        recordRecentChange({
          type: "object_added",
          label: "Site program placed from chat",
          detail: "Office, parking, basin, driveway, sidewalks, water, sanitary, storm, inlet, outfall, hydrant, and manhole draft objects were placed from one natural-language command.",
        });
      }
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setPreviewMode("2d");
      setPreviewInteraction("static");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setSidePanelVisible(false);
      setRightRailCollapsed(true);
      setFitToSiteRequest((value) => value + 1);
      updateProjectStatus({
        state: "working",
        area: "setup",
        title: "Site setup started",
        detail: `${directSiteSetup.address} is being applied with a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft locked review site.`,
        nextAction: "Civora is checking available roads, buildings, terrain, utilities, and source context. Draw or Generate after the context check finishes.",
      });
      setAutoExistingConditionsStatus({
        status: "running",
        message: wantsProgramAfterSiteSetup
          ? `Applying ${directSiteSetup.address}, placing the requested draft site program, and checking available source context inside a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft locked site.`
          : `Applying ${directSiteSetup.address} and checking available source context inside a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft locked site.`,
        candidateCount: 0,
        missing: [],
      });
      appendChatMessage(
        "assistant",
        wantsProgramAfterSiteSetup
          ? `Got it. I set up a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft review site centered on ${directSiteSetup.address}, placed an editable office/parking/drainage/utility/sidewalk draft concept, and started source context detection. You can move, rename, delete, or redraw the objects before Generate.`
          : `Got it. I set up a ${Math.round(directSiteSetup.width)} ft by ${Math.round(directSiteSetup.height)} ft review site centered on ${directSiteSetup.address}, locked the site frame, and started source context detection. Any roads, buildings, terrain, utilities, or constraints found from configured sources stay review-required.`,
        "status",
      );
      void saveSiteAddress(directSiteSetup.address, {
        preserveLockedSite: true,
        siteWidth: directSiteSetup.width,
        siteHeight: directSiteSetup.height,
      });
      return true;
    }
    if (/^(?:add|create|place|put|make)\s+(?:a\s+)?(?:(?:detention|stormwater|drainage)\s+)?(?:basin|pond)$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("basin", {
        label: "Detention Basin",
        placed: true,
        meta: { command_created: true, command_source: "direct_object_command" },
      });
      setActivePlacementId(null);
      setPreviewInteraction("static");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setSidePanelVisible(false);
      setRightRailCollapsed(true);
      appendChatMessage(
        "assistant",
        "Added and placed a detention basin as draft review geometry. It will be passed into Generate as review context.",
        "status",
      );
      return true;
    }
    if (tryHandleSiteProgramCommand(message)) {
      return true;
    }
    if (
      /^(select\s+(?:all|none|clear|layer\b.*)|align\b.*|distribute\b.*|move\b.*|copy\b.*|rotate\b.*|scale\b.*|mirror\b.*|flip\b.*|array\b.*|layer\b.*|delete\b.*|erase\b.*|offset\b.*|trim\b.*|extend\b.*|fillet\b.*|join\b.*|split\b.*|break\b.*|close\b.*|open\b.*|reverse\b.*|dist\b.*|measure\b.*)$/i.test(
        message.trim(),
      )
    ) {
      appendChatMessage("user", message);
      setPreviewMode("2d");
      setPreviewInteraction("edit");
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel("objects");
      setRenderedSidePanel("objects");
      setSidePanelVisible(true);
      setRightRailCollapsed(false);
      setCadToolRequest({ id: Date.now() + Math.random(), tool: "command", commandText: message.trim() });
      setCommandBarExpanded(false);
      appendChatMessage(
        "assistant",
        `Running draft command: ${message.trim()}. Results are shown in Draw / Object Manager command feedback. Draft objects remain review-required.`,
        "status",
      );
      return true;
    }
    if (/^(start site|start a site|new site)$/.test(normalized)) {
      appendChatMessage("user", message);
      handleStartBlankSite();
      setCommandBarExpanded(false);
      appendChatMessage("assistant", "Started a blank review site. Draw the boundary on the clear canvas; it remains review-required until locked.", "status");
      return true;
    }
    if (/^apply address$/.test(normalized)) {
      appendChatMessage("user", message);
      if (!siteAddress.trim()) {
        handleOpenSidePanel("site_existing");
        appendChatMessage("assistant", "Apply Address needs a project address in Setup first.", "status");
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Apply address needs input",
          detail: "No address is typed.",
          nextAction: "Type a project address in Setup, then run apply address again.",
        });
        return true;
      }
      void saveSiteAddress();
      appendChatMessage("assistant", "Applying the typed address as source context. Exact provider/auth needs will stay visible in Setup if the backend cannot apply it.", "status");
      return true;
    }
    if (/^draw site boundary$/.test(normalized)) {
      appendChatMessage("user", message);
      handleStartSiteBoundaryDraw();
      setCommandBarExpanded(false);
      appendChatMessage("assistant", "Site boundary drawing is active. Draw the boundary on the canvas; it remains review-required until locked.", "status");
      return true;
    }
    if (/^add water line$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("utility_corridor", { label: "Water Line", geometryType: "polyline", placed: true, meta: { network: "water", command_created: true } });
      appendChatMessage("assistant", "Added and placed a water-line utility corridor as draft review geometry.", "status");
      return true;
    }
    if (/^add sanitary line$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("utility_corridor", { label: "Sanitary Line", geometryType: "polyline", placed: true, meta: { network: "sanitary", command_created: true } });
      appendChatMessage("assistant", "Added and placed a sanitary-line utility corridor as draft review geometry.", "status");
      return true;
    }
    if (/^add storm sewer$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("utility_corridor", { label: "Storm Sewer", geometryType: "polyline", placed: true, meta: { network: "storm", command_created: true } });
      appendChatMessage("assistant", "Added and placed a storm-sewer utility corridor as draft review geometry.", "status");
      return true;
    }
    if (/^add (?:detention )?basin$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("basin", { label: "Detention Basin", placed: true, meta: { command_created: true } });
      appendChatMessage("assistant", "Added and placed a detention basin as draft review geometry.", "status");
      return true;
    }
    if (/^add outfall$/.test(normalized)) {
      appendChatMessage("user", message);
      handleAddObject("outfall", { label: "Outfall", placed: true, meta: { command_created: true, role: "storm_outfall_review_point" } });
      appendChatMessage("assistant", "Added and placed an outfall point as draft review geometry.", "status");
      return true;
    }
    if (/^hide utilities$/.test(normalized)) {
      appendChatMessage("user", message);
      setPreviewLayers((prev) => ({ ...prev, utilities: false, drainage: false, structures: false }));
      const hiddenTypes: SiteObjectType[] = ["utility_corridor", "manhole", "hydrant", "inlet", "outfall", "basin"];
      const hiddenCount = buildingPlacements.filter((item) => item.type && hiddenTypes.includes(item.type)).length;
      setBuildingPlacements((prev) =>
        prev.map((item) => {
          if (!item.type || !hiddenTypes.includes(item.type)) return item;
          return {
            ...item,
            meta: {
              ...(item.meta ?? {}),
              ui_hidden: true,
            },
          };
        }),
      );
      appendChatMessage(
        "assistant",
        hiddenCount
          ? `Utility and drainage layers are hidden in the preview. ${hiddenCount} utility/drainage object${hiddenCount === 1 ? "" : "s"} are marked hidden in Object Manager.`
          : "Utility and drainage layers are hidden in the preview. No utility/drainage objects are in Object Manager yet.",
        "status",
      );
      recordRecentChange({
        type: "object_visibility_changed",
        label: "Utilities hidden",
        detail: hiddenCount
          ? `${hiddenCount} utility/drainage object${hiddenCount === 1 ? "" : "s"} marked hidden.`
          : "Utility and drainage layers hidden; no matching objects were present.",
        undoBlockedReason: "Use Object Manager Show all to make hidden utility/drainage objects visible again.",
      });
      setStatusMessage(
        hiddenCount
          ? `Utility and drainage layers are hidden in the preview. ${hiddenCount} utility/drainage object${hiddenCount === 1 ? "" : "s"} are marked hidden in Object Manager.`
          : "Utility and drainage layers are hidden in the preview. No utility/drainage objects are in Object Manager yet.",
      );
      updateProjectStatus({
        state: "ready",
        area: "chat",
        title: "Utilities hidden",
        detail: hiddenCount ? `${hiddenCount} utility/drainage object${hiddenCount === 1 ? "" : "s"} marked hidden.` : "Utility and drainage layers are hidden.",
        nextAction: "Open Layers or Object Manager to review visibility.",
      });
      return true;
    }
    if (/^show only blockers$/.test(normalized)) {
      appendChatMessage("user", message);
      handleOpenSidePanel("analysis");
      appendChatMessage("assistant", "Opened the needs/review view. If no needs are recorded, the panel will show the exact empty state.", "status");
      updateProjectStatus({
        state: canonicalWorkspaceBlockers.length ? "blocked" : "ready",
        area: "chat",
        title: "Blocker view opened",
        detail: canonicalWorkspaceBlockers.length ? canonicalWorkspaceBlockers[0] : "No current needs-input items are recorded in the active workspace.",
        nextAction: canonicalWorkspaceBlockers.length ? "Review the needs-input panel and fix the first item." : "Continue setup, generate, or deliver from the current workspace.",
      });
      return true;
    }
    if (/^generate$/.test(normalized)) {
      appendChatMessage("user", message);
      handleOpenSidePanel("generate");
      appendChatMessage("assistant", "Running Generate from the locked site. I will show visible review concepts on the canvas and exact needs if a system cannot run.", "status");
      void handleGenerateSystem("full");
      return true;
    }
    if (/^(make review package|create review package)$/.test(normalized)) {
      appendChatMessage("user", message);
      handleOpenSidePanel("deliverables");
      handleMakeReviewPackage();
      appendChatMessage("assistant", "Opened Deliver and created/updated the review package summary. It remains review-only.", "status");
      return true;
    }
    if (/^what changed\??$/.test(normalized)) {
      appendChatMessage("user", message);
      const changed = Object.entries(systemStatuses)
        .filter(([, status]) => status === "stale")
        .map(([system]) => system);
      appendChatMessage(
        "assistant",
        changed.length
          ? `Changed/stale systems: ${changed.join(", ")}. Regenerate only the affected systems after reviewing draft objects.`
          : `No stale generated systems are currently marked. Project status: ${projectStatusSummary.state}. ${projectStatusSummary.detail}`,
        "status",
      );
      return true;
    }
    if (/^(what is blocked|what needs input|what needs attention)\??$/.test(normalized)) {
      appendChatMessage("user", message);
      const blockers = uniqueStrings([
        projectStatusSummary.state === "blocked" ? `${projectStatusSummary.title}: ${projectStatusSummary.detail}` : "",
        ...issues.map((issue) => issue.message),
        ...analysisIssues.map((issue) => issue.message),
        ...(workflowReviewDashboard?.release_blockers ?? []),
        ...(generateFlowSummary?.needs_review ?? []),
      ]);
      appendChatMessage(
        "assistant",
        blockers.length ? `Needs input:\n${blockers.map((item) => `- ${item}`).join("\n")}` : "No needs-input items are currently recorded in the active workspace.",
        "status",
      );
      return true;
    }
    if (/^what should i do next\??$/.test(normalized)) {
      appendChatMessage("user", message);
      const activePlacementObject =
        activePlacementId && placementModeEnabled
          ? buildingPlacements.find((item) => item.id === activePlacementId)
          : null;
      const next = activePlacementObject
        ? `Click the canvas to place ${activePlacementObject.label}.`
        : pendingPlacementObjects.length
          ? `Open Objects and place ${pendingPlacementObjects[0].label}.`
          : projectStatusSummary.nextAction || workflowActionHints[0] || progressTimelineState.next_action || (siteScaleLocked ? "Open Generate and run a review draft." : "Open Setup and lock a site boundary.");
      appendChatMessage("assistant", `Next action: ${next} Current status: ${projectStatusDisplayLabel[projectStatusSummary.state]}.`, "status");
      return true;
    }
    if (/^create ai realism$/.test(normalized)) {
      appendChatMessage("user", message);
      handleSetPreviewQuality("high");
      handleSetPreviewMode("2d");
      handleOpenSidePanel("model");
      appendChatMessage("assistant", "Opened high-quality preview mode. Use the AI Realism toggle there; provider/layout needs will be shown exactly in the preview panel.", "status");
      return true;
    }
    if (/^turn ai realism off$/.test(normalized)) {
      appendChatMessage("user", message);
      handleSetPreviewQuality("standard");
      appendChatMessage("assistant", "Turned presentation/AI realism preview mode off by returning to Standard preview quality.", "status");
      return true;
    }
    return false;
  };

  const handlePromptKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (event.key === "Escape") {
      event.preventDefault();
      setShortcutsOverlayOpen(false);
      setPlacementModeEnabled(false);
      setActivePlacementId(null);
      setPendingClarification(null);
      setPreviewInteraction("static");
      setCadToolRequest({ id: Date.now() + Math.random(), tool: "select" });
      setStatusMessage("Active drawing/tool state cancelled.");
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const handleSendMessage = () => {
    const trimmed = prompt.trim();
    if (!trimmed && !imageName) return;
    if (trimmed && /\b(stamp|seal|sign|certify|approve construction|submit construction documents|engineer of record|eor)\b/i.test(trimmed)) {
      refuseUnsafeConstructionCommand(trimmed);
      setPrompt("");
      return;
    }
    const normalizedStatus = String(visibleActiveJob?.status || "").toLowerCase();
    const approvalCommand = Boolean(
      trimmed &&
        /^(ok(ay)?|approve|continue|yes|y|go ahead|start next|proceed)$/i.test(trimmed.trim()),
    );
    if (normalizedStatus === "awaiting_approval" && approvalCommand) {
      appendChatMessage("user", trimmed);
      setPrompt("");
      handleContinueActiveJob();
      return;
    }
    if (pendingClarification && trimmed) {
      appendChatMessage("user", trimmed);
      setPrompt("");
      const lot = resolveLotBounds();
      const hasSite = Boolean(lot.w && lot.h);
      if (pendingClarification.action === "set_site_then_add") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const type = pendingClarification.payload?.type as SiteObjectType | undefined;
          if (type) {
            setPendingClarification(null);
            handleAddObject(type);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "set_site_then_detect") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          setPendingClarification(null);
          void handleAnalyzeImageFeatures();
          return;
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "set_site_then_generate") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const target = pendingClarification.payload?.target as
            | "roads"
            | "parking"
            | "grading"
            | "drainage"
            | "utilities"
            | "full"
            | undefined;
          if (target) {
            setPendingClarification(null);
            void handleGenerateSystem(target);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "place_object_missing_site") {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled && hasSite) {
          const id = pendingClarification.payload?.id as string | undefined;
          if (id) {
            setPendingClarification(null);
            handleSelectPlacementTarget(id);
            return;
          }
        }
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      if (pendingClarification.action === "upload_image_then_detect") {
        if (mapSnapshotPath) {
          setPendingClarification(null);
          void handleAnalyzeImageFeatures();
          return;
        }
        appendChatMessage(
          "assistant",
          "Please upload a site image/map snapshot first, then say “done.”",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "access_analysis_missing") {
        const confirmed = buildingPlacements.filter(
          (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
        );
        const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
        const buildingTypes = new Set<SiteObjectType>([
          "building",
          "retail_building",
          "multifamily_building",
          "industrial_building",
          "office_building",
          "pad",
        ]);
        const buildings = confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType));
        const access = confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType));
        if (buildings.length && access.length) {
          setPendingClarification(null);
          handleAnalyzeSiteAccess();
          return;
        }
        appendChatMessage(
          "assistant",
          "Once you add or confirm buildings and access objects, I can run access analysis.",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "grading_source") {
        const lower = trimmed.toLowerCase();
        let slopeEstimateOverride: SurveySlopeResponse | null = null;
        if (/(survey)/.test(lower)) {
          if (!surveyFileName) {
            appendChatMessage("assistant", "Please upload a survey/topo file first.", "status");
            return;
          }
          setUseSurveyForGrading(true);
        } else if (/(map|terrain)/.test(lower)) {
          setUseSurveyForGrading(false);
        } else if (/(assume|assumed|fallback)/.test(lower)) {
          slopeEstimateOverride = buildAssumedSlopeEstimate(parsePositiveNumber(assumedTerrainSlopePct) ?? 8);
          setUseSurveyForGrading(false);
          setSurveySlopeEstimate(slopeEstimateOverride);
        } else {
          appendChatMessage(
            "assistant",
            "Should I use survey, map terrain, or an assumed slope?",
            "status",
          );
          return;
        }
        const target = pendingClarification.payload?.target as
          | "roads"
          | "parking"
          | "grading"
          | "drainage"
          | "utilities"
          | "full"
          | undefined;
        if (target) {
          setPendingClarification(null);
          void handleGenerateSystem(target, { slopeEstimateOverride });
          return;
        }
      }
      if (pendingClarification.action === "drainage_missing_basin") {
        const hasBasin = buildingPlacements.some((item) => item.type === "basin" && item.placed);
        if (hasBasin) {
          const target = pendingClarification.payload?.target as
            | "drainage"
            | "full"
            | undefined;
          if (target) {
            setPendingClarification(null);
            void handleGenerateSystem(target);
            return;
          }
        }
        appendChatMessage(
          "assistant",
          "Add a basin object first, then I can run drainage.",
          "status",
        );
        return;
      }
      if (pendingClarification.action === "lock_site_required") {
        const lower = trimmed.toLowerCase();
        if (/(yes|ok|lock|confirm)/.test(lower)) {
          setPendingClarification(null);
          handleToggleSiteLock();
          const target = pendingClarification.payload?.action as
            | "roads"
            | "parking"
            | "grading"
            | "drainage"
            | "utilities"
            | "full"
            | undefined;
          if (target) {
            void handleGenerateSystem(target);
          }
          return;
        }
        appendChatMessage(
          "assistant",
          "Lock the site when you're ready, then I can continue.",
          "status",
        );
        return;
      }
    }
    if (busy || visibleActiveJob) {
      if (trimmed || imageName) {
        appendChatMessage("user", trimmed || "Uploaded an image.");
        appendChatMessage(
          "assistant",
          "A run is already in progress. Please wait for it to finish before sending a new request.",
          "status",
        );
      }
      setStatusMessage("A run is already in progress. Please wait for it to finish.");
      setPrompt("");
      return;
    }
    if (trimmed) {
      const handledPowerCommand = tryHandlePowerCommand(trimmed);
      if (handledPowerCommand) {
        setPrompt("");
        return;
      }
      const routeToOrchestrator = shouldRouteToOrchestrator(trimmed);
      if (!routeToOrchestrator) {
        const handled = tryHandleObjectIntent(trimmed);
        if (handled) {
          setPrompt("");
          return;
        }
        const handledSheet = tryHandleSheetIntent(trimmed);
        if (handledSheet) {
          setPrompt("");
          return;
        }
        const handledInfo = tryHandleInfoIntent(trimmed);
        if (handledInfo) {
          setPrompt("");
          return;
        }
        const handledAction = tryHandleActionIntent(trimmed);
        if (handledAction) {
          setPrompt("");
          return;
        }
      }
    }
    void runOrchestrator("run");
  };

  const handleContinuePendingClarification = () => {
    if (!pendingClarification) return;
    const lot = resolveLotBounds();
    const hasSite = Boolean(lot.w && lot.h);
    if (pendingClarification.action === "set_site_then_add") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      const type = pendingClarification.payload?.type as SiteObjectType | undefined;
      if (type) {
        setPendingClarification(null);
        handleAddObject(type);
      }
      return;
    }
    if (pendingClarification.action === "set_site_then_detect") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      setPendingClarification(null);
      void handleAnalyzeImageFeatures();
      return;
    }
    if (pendingClarification.action === "set_site_then_generate") {
      if (!hasSite) {
        appendChatMessage("assistant", pendingClarification.question, "status");
        return;
      }
      const target = pendingClarification.payload?.target as
        | "roads"
        | "parking"
        | "grading"
        | "drainage"
        | "utilities"
        | "full"
        | undefined;
      if (target) {
        setPendingClarification(null);
        void handleGenerateSystem(target);
      }
      return;
    }
    if (pendingClarification.action === "upload_image_then_detect") {
      if (!mapSnapshotPath) {
        appendChatMessage("assistant", "Please upload a site image/map snapshot first.", "status");
        return;
      }
      setPendingClarification(null);
      void handleAnalyzeImageFeatures();
      return;
    }
    if (pendingClarification.action === "access_analysis_missing") {
      setPendingClarification(null);
      handleAnalyzeSiteAccess();
      return;
    }
    if (pendingClarification.action === "grading_source") {
      const target = pendingClarification.payload?.target as
        | "roads"
        | "parking"
        | "grading"
        | "drainage"
        | "utilities"
        | "full"
        | undefined;
      if (target) {
        const slopeEstimateOverride = buildAssumedSlopeEstimate(parsePositiveNumber(assumedTerrainSlopePct) ?? 8);
        setUseSurveyForGrading(false);
        setSurveySlopeEstimate(slopeEstimateOverride);
        setPendingClarification(null);
        void handleGenerateSystem(target, { slopeEstimateOverride });
      }
      return;
    }
  };

  const pushJobToast = useCallback((toast: Omit<WorkspaceToast, "id">) => {
    const id = `job-toast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setJobToasts((current) => [{ id, ...toast }, ...current].slice(0, 4));
    window.setTimeout(() => {
      setJobToasts((current) => current.filter((item) => item.id !== id));
    }, 6500);
  }, []);

  const upsertJobSummary = useCallback((job: JobSummary) => {
    setJobs((current) => {
      const next = [...current];
      const index = next.findIndex((item) => item.job_id === job.job_id);
      if (index >= 0) {
        next[index] = { ...next[index], ...job };
      } else {
        next.unshift(job);
      }
      return next;
    });
  }, [setJobs]);

  const handleCancelJobById = async (jobId: string) => {
    if (!token || !jobId) return;
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${jobId}/cancel`,
        {},
        { token },
      );
      upsertJobSummary(data.job);
      appendChatMessage("assistant", `Job ${data.job.job_id} was cancelled.`, "status");
      pushJobToast({
        title: "Job cancelled",
        detail: data.job.job_id,
        tone: "warning",
      });
      setStatusMessage(`Cancelled job ${data.job.job_id}.`);
      if (activeJobId === data.job.job_id) {
        setActiveJobId("");
      }
      setBusy(false);
      runSubmissionRef.current = false;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Job cancel failed.";
      setStatusMessage(message);
      pushJobToast({ title: "Cancel failed", detail: message, tone: "error" });
    }
  };

  const handleCancelActiveJob = async () => {
    if (visibleActiveJob?.job_id && token) {
      await handleCancelJobById(visibleActiveJob.job_id);
      return;
    }
    if (directRunAbortRef.current) {
      directRunAbortRef.current.abort();
      directRunAbortRef.current = null;
      runSubmissionRef.current = false;
      setBusy(false);
      setActivePlanTool("run");
      setStatusMessage("Cancelling the live request...");
      return;
    }
  };

  const handleRetryJob = async (jobId: string) => {
    if (!token || !jobId) return;
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${jobId}/retry`,
        {},
        { token },
      );
      upsertJobSummary(data.job);
      setActiveJobId(data.job.job_id);
      setSelectedJobId(data.job.job_id);
      await refreshJobs(token, { suppressError: true, force: true });
      appendChatMessage("assistant", `Retry queued as job ${data.job.job_id}.`, "status");
      pushJobToast({
        title: "Retry queued",
        detail: `${data.job.job_id} from ${jobId}`,
        tone: "info",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Job retry failed.";
      setStatusMessage(message);
      pushJobToast({ title: "Retry failed", detail: message, tone: "error" });
    }
  };

  const handleResumeJob = async (jobId: string) => {
    if (!token || !jobId) return;
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${jobId}/continue`,
        {},
        { token },
      );
      upsertJobSummary(data.job);
      setActiveJobId(data.job.job_id);
      setSelectedJobId(data.job.job_id);
      await refreshJobs(token, { suppressError: true, force: true });
      appendChatMessage("assistant", `Resumed job ${data.job.job_id}.`, "status");
      pushJobToast({
        title: "Job resumed",
        detail: data.job.job_id,
        tone: "success",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not resume job.";
      setStatusMessage(message);
      pushJobToast({ title: "Resume failed", detail: message, tone: "error" });
    }
  };

  const handleContinueActiveJob = async () => {
    if (!token) return;
    if (!visibleActiveJob?.job_id) {
      setStatusMessage("No active job is waiting at a review hold.");
      return;
    }
    const status = String(visibleActiveJob.status || "").toLowerCase();
    if (status !== "awaiting_approval") {
      setStatusMessage("There is no phase waiting at a review hold right now.");
      return;
    }
    const nextPhaseLabel =
      previewNextPendingPhase?.label || previewRunningPhase?.label || "Next phase";
    setApprovalError(null);
    setApprovalPhaseLabel(nextPhaseLabel);
    setApprovalInFlight(true);
    setBusy(true);
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${visibleActiveJob.job_id}/continue`,
        {},
        { token },
      );
      upsertJobSummary(data.job);
      appendChatMessage(
        "assistant",
        `Accepted the current phase for review workflow. Starting ${nextPhaseLabel}.`,
        "status",
      );
      pushJobToast({
        title: "Job resumed",
        detail: `${data.job.job_id} starting ${nextPhaseLabel}`,
        tone: "success",
      });
      setStatusMessage(`Accepted ${data.job.job_id} for review workflow. Starting ${nextPhaseLabel}.`);
      if (data.job.job_id) {
        setActiveJobId(data.job.job_id);
        setApprovalPendingJobId(data.job.job_id);
      }
      await refreshJobs(token, { suppressError: true, force: true });
      queuePreviewRefresh("Refreshing preview after review step...");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not continue the staged run.";
      setApprovalError(message);
      setStatusMessage(message);
      pushJobToast({ title: "Resume failed", detail: message, tone: "error" });
    } finally {
      setBusy(false);
      setApprovalInFlight(false);
    }
  };

  const saveProject = async ({
    silent = false,
    projectIdOverride,
    nameOverride,
    fileNameOverride,
    projectInputOverride,
    latestResultOverride,
    autoNamedOverride,
    autoFileNamedOverride,
  }: {
    silent?: boolean;
    projectIdOverride?: string | null;
    nameOverride?: string;
    fileNameOverride?: string;
    projectInputOverride?: ProjectInput;
    latestResultOverride?: PlanResponse;
    autoNamedOverride?: boolean;
    autoFileNamedOverride?: boolean;
  } = {}): Promise<ProjectRecord | null> => {
    if (!token) {
      const message = "Sign in/connect backend to save projects.";
      if (!silent) {
        setProjectDrawerNotice(message);
        updateProjectStatus({
          state: "blocked",
          area: "projects",
          title: "Save needs sign-in",
          detail: "Sign in/connect backend to save projects.",
          nextAction: "Sign in or reconnect the backend, then press Save Project again.",
        });
      }
      return null;
    }
    const effectiveProjectId =
      projectIdOverride !== undefined
        ? projectIdOverride
        : resolvedProjectIdRef.current || projectId || currentProject?.project_id || null;
    const resolvedName = (nameOverride ?? siteName).trim();
    const resolvedFileName = (fileNameOverride ?? fileName).trim();
    if (effectiveDemoWorkspaceEnabled && isSeededDemoProjectId(effectiveProjectId)) {
      if (!silent) {
        updateProjectStatus({
          state: "blocked",
          area: "projects",
          title: "Save unavailable in demo",
          detail: "Demo workspace changes stay local and are not saved to pilot projects.",
          nextAction: "Start a non-demo project or sign in/connect backend before saving.",
        });
      }
      return currentProject;
    }
    if (!silent) {
      setBusy(true);
      updateProjectStatus({
        state: "working",
        area: "projects",
        title: "Saving project",
        detail: `Saving "${resolvedName || "Untitled Project"}" to the project backend.`,
            nextAction: "Keep the drawer open until the save finishes or shows what needs attention.",
      });
    }
    const liveChatThread = chatMessagesRef.current;
    const projectInputToSave = projectInputOverride
      ? {
          ...projectInputOverride,
          manual_fields: {
            ...(projectInputOverride.manual_fields ?? {}),
            project_name: resolvedName,
            file_name: resolvedFileName,
          },
          meta: {
            ...(projectInputOverride.meta ?? {}),
            chat_thread: liveChatThread,
            auto_named: autoNamedOverride ?? siteNameAuto,
            auto_file_named: autoFileNamedOverride ?? fileNameAuto,
            setup_wizard_state_v1: setupWizardState,
          },
        }
      : {
          ...payloadPreview,
          manual_fields: {
            ...(payloadPreview.manual_fields ?? {}),
            project_name: resolvedName,
            file_name: resolvedFileName,
          },
          meta: {
            ...(payloadPreview.meta ?? {}),
            chat_thread: liveChatThread,
            auto_named: autoNamedOverride ?? siteNameAuto,
            auto_file_named: autoFileNamedOverride ?? fileNameAuto,
            setup_wizard_state_v1: setupWizardState,
          },
        };
    const latestResultToSave =
      latestResultOverride !== undefined ? latestResultOverride : undefined;
    try {
      const requestBody: Record<string, unknown> = {
        project_id: effectiveProjectId,
        name: resolvedName,
        project_input: projectInputToSave,
        metadata: {
          auto_named: autoNamedOverride ?? siteNameAuto,
          auto_file_named: autoFileNamedOverride ?? fileNameAuto,
        },
      };
      if (latestResultToSave !== undefined) {
        requestBody.latest_result = latestResultToSave;
      }
      const data = await postJson<{ project: ProjectRecord }>(
        "/api/projects",
        requestBody,
        { token },
      );
      resolvedProjectIdRef.current = data.project.project_id;
      setProjectId(data.project.project_id);
      setCurrentProject(data.project);
      setWorkspaceRestoreState("restored");
      if (typeof window !== "undefined") {
        window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, data.project.project_id);
      }
      upsertProjectSummary(data.project);
      setProjectDrawerNotice("Saved. Reload will restore this project on this browser.");
      if (!silent) {
        updateProjectStatus({
          state: "ready",
          area: "projects",
          title: "Project saved",
          detail: `Saved project "${data.project.name || resolvedName || "Untitled Project"}".`,
          nextAction: "Continue setup, generate a review draft, or open Deliver when ready.",
        });
      }
      return data.project;
    } catch (error) {
      const message = panelErrorMessage(error, "Project save could not complete.");
      setProjectDrawerNotice(`Save needs attention: ${message}`);
      if (!silent) {
        updateProjectStatus({
          state: "blocked",
          area: "projects",
          title: "Save could not finish",
          detail: message,
          nextAction: "Check auth/backend connectivity, then press Save Project again.",
        });
      }
      return null;
    } finally {
      if (!silent) setBusy(false);
    }
  };

  useEffect(() => {
    const activeProjectId =
      resolvedProjectIdRef.current || projectId || currentProject?.project_id || "";
    if (!token || !activeProjectId || !currentProject) return;
    if (autosaveSuspendRef.current) return;
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
      void saveProject({ silent: true, projectIdOverride: activeProjectId });
    }, 700);
  }, [chatMessages, prompt, token, projectId, currentProject]);

  useEffect(() => {
    if (!token || !currentProject?.project_id) return;
    if (autosaveSuspendRef.current) return;
    if (controlAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(controlAutosaveTimeoutRef.current);
    }
    controlAutosaveTimeoutRef.current = window.setTimeout(() => {
      void saveProject({ silent: true });
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
    setSurveySlopeEstimate(slopeEstimate || null);
    setUseSurveyForGrading(useSurvey !== undefined ? Boolean(useSurvey) : true);
    setSurveyPoints(storedPoints as number[][]);
    setSurveyPreviewPoints(mapSurveyPointsToSite(storedPoints as number[][]));
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
  }, [currentProject, mapSurveyPointsToSite, token]);

  const loadProject = async (id: string) => {
    if (!token) return;
    const loadStartedAt = markCivoraInteraction();
    autosaveSuspendRef.current = true;
    if (chatAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(chatAutosaveTimeoutRef.current);
      chatAutosaveTimeoutRef.current = null;
    }
    if (controlAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(controlAutosaveTimeoutRef.current);
      controlAutosaveTimeoutRef.current = null;
    }
    const requestId = projectLoadRequestRef.current + 1;
    projectLoadRequestRef.current = requestId;
    try {
      resetWorkspaceState();
      updateProjectStatus({
        state: "working",
        area: "projects",
        title: "Opening project",
        detail: "Loading the saved project workspace from the backend.",
        nextAction: "Wait for the project drawer to restore the workspace or show a blocker.",
      });
      const data = await getJson<{ project: ProjectRecord }>(
        `/api/projects/${id}`,
        { token },
      );
      if (projectLoadRequestRef.current !== requestId) {
        return;
      }
      const project = data.project;
      resolvedProjectIdRef.current = project.project_id;
      setCurrentProject(project);
      setProjectId(project.project_id);
      setSiteName(project.name ?? "");
      applyProjectInput(project.project_input ?? {});
      setBackendResult(null);
      setIssues([]);
      setPlanPreviewUrl("");
      setPlanPreviewSummary(null);
      updateProjectStatus({
        state: "ready",
        area: "projects",
        title: "Project opened",
        detail: `Loaded project "${project.name || "Untitled Project"}".`,
        nextAction: "Review the restored setup, objects, and generated outputs before continuing.",
      });
      setProjectDrawerNotice(`Restored "${project.name || "Untitled Project"}".`);
      setWorkspaceRestoreState("restored");
      measureCivoraInteractionAfterPaint("projects.drawer.open_project", loadStartedAt, {
        projectId: project.project_id,
      });
      if (typeof window !== "undefined") {
        window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, project.project_id);
      }
      loadProjectResultInBackground(project);
      if (activeJobId && (!projectId || currentProjectActiveJob?.project_id === id || activeJob?.project_id === id)) {
        void loadJob(activeJobId);
      }
    } catch (error) {
      setWorkspaceRestoreState("failed");
      const message =
        error instanceof Error ? `Could not restore saved workspace: ${error.message}` : "Could not restore saved workspace.";
      setProjectDrawerNotice(message);
      updateProjectStatus({
        state: "blocked",
        area: "projects",
        title: "Open needs attention",
        detail: message,
        nextAction: "Check auth/backend connectivity, then open the project again.",
      });
      measureCivoraInteractionAfterPaint("projects.drawer.open_project.failed", loadStartedAt, { projectId: id });
    } finally {
      autosaveSuspendRef.current = false;
    }
  };

  useEffect(() => {
    if (!token || effectiveDemoWorkspaceEnabled || restoredActiveProjectRef.current) return;
    if (currentProject?.project_id || projectId) return;
    if (typeof window === "undefined") return;
    const savedProjectId = window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
    if (!savedProjectId) return;
    restoredActiveProjectRef.current = true;
    void loadProject(savedProjectId);
  }, [token, effectiveDemoWorkspaceEnabled, currentProject?.project_id, projectId]);

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

  const loadJob = async (id: string) => {
    if (!token) return;
    try {
      const data = await getJson<{ job: JobSummary }>(`/api/jobs/${id}`, { token });
      const job = data.job;
      const jobProjectId = String(job.project_id || "").trim();
      const activeJobProjectSignature = `${job.job_id}:${jobProjectId}`;
      const activeTrackedProjectId =
        jobProjectId ||
        resolvedProjectIdRef.current ||
        projectId ||
        currentProject?.project_id ||
        "";
      if (jobProjectId) {
        resolvedProjectIdRef.current = jobProjectId;
        upsertProjectSummary({
          project_id: jobProjectId,
          name: currentProject?.project_id === jobProjectId
            ? currentProject.name || siteName || "Untitled Project"
            : siteName || "Untitled Project",
          description:
            currentProject?.project_id === jobProjectId
              ? currentProject.description ?? ""
              : "",
          has_result:
            Boolean(job.result && Object.keys(job.result).length) ||
            ["awaiting_approval", "completed"].includes(
              String(job.status || "").toLowerCase(),
            ),
          updated_at:
            typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
              ? job.updated_at
              : Date.now() / 1000,
        });
        if (projectId !== jobProjectId) {
          setProjectId(jobProjectId);
        }
        if (!currentProject || currentProject.project_id !== jobProjectId) {
          setCurrentProject((existing) => {
            if (existing?.project_id === jobProjectId) {
              return existing;
            }
            return {
              project_id: jobProjectId,
              name: existing?.name || siteName || "Untitled Project",
              description: existing?.description ?? "",
              has_result: true,
            } as ProjectRecord;
          });
        }
        const shouldSyncActiveJobProject =
          (currentProject?.project_id !== jobProjectId ||
            projectId !== jobProjectId) &&
          activeJobProjectSyncRef.current !== activeJobProjectSignature;
        if (shouldSyncActiveJobProject) {
          activeJobProjectSyncRef.current = activeJobProjectSignature;
          const requestId = projectLoadRequestRef.current + 1;
          projectLoadRequestRef.current = requestId;
          autosaveSuspendRef.current = true;
          void getJson<{ project: ProjectRecord }>(`/api/projects/${jobProjectId}`, {
            token,
          })
            .then((projectData) => {
              if (projectLoadRequestRef.current !== requestId) {
                autosaveSuspendRef.current = false;
                return;
              }
              const syncedProject = projectData.project;
              resolvedProjectIdRef.current = syncedProject.project_id;
              setCurrentProject(syncedProject);
              setProjectId(syncedProject.project_id);
              setSiteName(syncedProject.name ?? "");
              applyProjectInput(syncedProject.project_input ?? {});
              upsertProjectSummary(syncedProject);
              loadProjectResultInBackground(syncedProject);
              autosaveSuspendRef.current = false;
            })
            .catch((error) => {
              setStatusMessage(
                error instanceof Error
                  ? error.message
                  : "Project sync from active job failed.",
              );
              autosaveSuspendRef.current = false;
            });
        }
      }
      setJobs((current) => {
        const next = [...current];
        const existingIndex = next.findIndex((item) => item.job_id === job.job_id);
        if (existingIndex >= 0) {
          next[existingIndex] = { ...next[existingIndex], ...job };
        } else {
          next.unshift(job);
        }
        return next;
      });
      setActiveJobId(job.job_id);
      const previousStatus = lastJobStatusRef.current[job.job_id];
      const normalizedStatus = String(job.status || "").toLowerCase();
      const stageLabel = String(job.stage || "").trim() || "Engineering Run";
      const stageDetail = String(job.stage_detail || "").trim();
      const phaseSignature = `${normalizedStatus}|${stageLabel}|${stageDetail}`;
      if (previousStatus !== job.status) {
        lastJobStatusRef.current[job.job_id] = job.status;
        if (job.status === "queued") {
          const queuePosition =
            typeof job.queue_position === "number" && Number.isFinite(job.queue_position)
              ? Math.max(1, Math.round(job.queue_position))
              : null;
          const queuedCount =
            typeof job.queued_count === "number" && Number.isFinite(job.queued_count)
              ? Math.max(0, Math.round(job.queued_count))
              : 0;
          const runningCount =
            typeof job.running_count === "number" && Number.isFinite(job.running_count)
              ? Math.max(0, Math.round(job.running_count))
              : 0;
          appendChatMessage(
            "assistant",
            queuePosition
              ? `Job ${job.job_id} is queued in the background. Position ${queuePosition}${queuedCount > 0 ? ` of ${queuedCount}` : ""}. ${runningCount > 0 ? `${runningCount} worker${runningCount === 1 ? "" : "s"} active.` : ""}`.trim()
              : `Job ${job.job_id} is queued and waiting to run in the background.`,
            "status",
          );
        } else if (job.status === "awaiting_approval") {
          appendChatMessage(
            "assistant",
            `${toReadableLabel(stageLabel)} stage complete. Waiting at a user-controlled review hold.`,
            "status",
          );
        } else if (job.status === "cancelling") {
          appendChatMessage(
            "assistant",
            `Job ${job.job_id} is cancelling now.`,
            "status",
          );
        }
        lastJobPhaseSignatureRef.current[job.job_id] = phaseSignature;
      } else if (
        ["running", "awaiting_approval", "queued"].includes(normalizedStatus) &&
        lastJobPhaseSignatureRef.current[job.job_id] !== phaseSignature
      ) {
        lastJobPhaseSignatureRef.current[job.job_id] = phaseSignature;
        if (normalizedStatus === "awaiting_approval") {
          appendChatMessage(
            "assistant",
            `${toReadableLabel(stageLabel)} stage complete. Waiting at a user-controlled review hold.`,
            "status",
          );
        }
      }
      if (
        activeTrackedProjectId &&
        ["queued", "running", "awaiting_approval"].includes(String(job.status || "").toLowerCase())
      ) {
        const refreshStamp =
          typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
            ? job.updated_at
            : Date.now() / 1000;
        const previousRefresh = lastProjectResultRefreshRef.current[job.job_id] ?? 0;
        if (refreshStamp > previousRefresh) {
          lastProjectResultRefreshRef.current[job.job_id] = refreshStamp;
          loadProjectResultInBackground({
            project_id: activeTrackedProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
          } as ProjectRecord);
        }
      }
      if (
        job.result &&
        Object.keys(job.result).length &&
        activeTrackedProjectId &&
        ["queued", "running", "awaiting_approval"].includes(String(job.status || "").toLowerCase())
      ) {
        const partialRefreshStamp =
          typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
            ? job.updated_at
            : Date.now() / 1000;
        const previousPartialRefresh =
          lastJobPartialResultRefreshRef.current[job.job_id] ?? 0;
        if (partialRefreshStamp > previousPartialRefresh) {
          lastJobPartialResultRefreshRef.current[job.job_id] = partialRefreshStamp;
          applyBackendResult(job.result);
          requestPreviewInBackground(
            {
              project_id: activeTrackedProjectId || null,
              result: job.result,
              filename_stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
            },
            {
              silentStatus: true,
            },
          );
        }
      }
      if (job.status === "completed" && job.result) {
        setJobsPanelStatusMessage("");
        if (isArtifactExportJob(job)) {
          const artifact = artifactFromJob(job);
          if (artifact?.download_path) {
            await handleArtifactDownload(
              artifact.download_path,
              artifact.filename || (artifact.kind === "dxf" ? "civora-ai-plan.dxf" : "civora-ai-report.json"),
            );
            appendChatMessage(
              "assistant",
              `${toReadableLabel(String(artifact.kind || "export"))} review export is ready and downloaded. Field use is outside Civora and requires independent licensed-professional review.`,
              "status",
            );
            setStatusMessage("Review export downloaded. Field use remains outside Civora.");
          } else {
            setStatusMessage("Export job completed but did not return a download path.");
          }
          setActiveJobId("");
          if (activeTrackedProjectId) {
            loadProjectResultInBackground({
              project_id: activeTrackedProjectId,
              name: currentProject?.name || siteName || "Untitled Project",
            } as ProjectRecord);
          }
          return;
        }
        applyBackendResult(job.result);
        requestPreviewInBackground(
          {
            project_id: activeTrackedProjectId || null,
            result: job.result,
            filename_stem: fileName || siteName,
          },
          {
            loadingMessage:
              projectId && job.project_id === projectId
                ? `Job ${job.job_id} completed. Refreshing preview...`
                : undefined,
            successMessage: `Job ${job.job_id} completed.`,
          },
        );
        appendChatMessage(
          "assistant",
          summarizePlanResponse(job.result, "run"),
          "message",
        );
        setActiveJobId("");
        if (jobProjectId) {
          upsertProjectSummary({
            project_id: jobProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
            description: currentProject?.description ?? "",
            has_result: true,
            updated_at: Date.now() / 1000,
          });
        }
        if (activeTrackedProjectId) {
          loadProjectResultInBackground({
            project_id: activeTrackedProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
          } as ProjectRecord);
        }
      } else if (job.status === "failed") {
        setJobsPanelStatusMessage(`Job failed: ${job.error || "No backend detail was recorded. Retry or inspect backend logs."}`);
        appendChatMessage(
          "assistant",
          job.error
            ? `The background job failed: ${job.error}. Retry from Jobs after checking the inputs.`
            : "The background job failed before Civora could finish the design. Retry from Jobs after checking the inputs.",
          "status",
        );
        setStatusMessage(job.error ?? "Job failed.");
        setActiveJobId("");
      } else if (job.status === "cancelled") {
        appendChatMessage(
          "assistant",
          `Job ${job.job_id} was cancelled before completion.`,
          "status",
        );
        setStatusMessage(`Job ${job.job_id} was cancelled.`);
        setActiveJobId("");
      } else {
        setStatusMessage(
          job.stage_detail
            ? `${job.stage || "Running"}: ${job.stage_detail}`
            : `Job ${job.job_id} is ${job.status}.`,
        );
      }
    } catch (error) {
      const message = `Job refresh failed: ${panelErrorMessage(error, "Could not refresh job detail.")}`;
      setJobsPanelStatusMessage(message);
      setStatusMessage(message);
    }
  };

  const handleSelectJob = useCallback((jobId: string) => {
    setSelectedJobId(jobId);
    if (jobId) {
      void loadJob(jobId);
    }
  }, [loadJob]);

  const uploadImage = async (file: File) => {
    if (!token) {
      const message = "Image upload failed: Sign in/connect backend to upload images.";
      setImageUploadState("failed");
      setImageUploadNote(message);
      setStatusMessage(message);
      return;
    }
    const localPreviewUrl = URL.createObjectURL(file);
    setUploadedImagePreviewUrl(localPreviewUrl);
    setImageUploadState("uploading");
    setImageUploadNote("Uploading image…");
    clearGeneratedPreview();
    try {
      const imageElement = new Image();
      const imageSize = await new Promise<{ width: number; height: number } | null>((resolve) => {
        imageElement.onload = () => resolve({ width: imageElement.width, height: imageElement.height });
        imageElement.onerror = () => resolve(null);
        imageElement.src = localPreviewUrl;
      });
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadImageResponse>("/api/upload-image", formData, {
        token,
      });
      setImageName(data.image_path || file.name);
      setUploadedImageApiUrl(
        data.image_url ? uploadedImageSrc(data.image_url, token) : "",
      );
      setMapSnapshotPath(data.image_path || "");
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        map_snapshot: {
          filename: data.filename || file.name,
          stored_filename: data.image_path || file.name,
          image_path: data.image_path || "",
          image_url: data.image_url || "",
        },
        site_alignment_locked: true,
      };
      const hasSite = buildingPlacements.some((item) => item.type === "site");
      let width = parsePositiveNumber(lotWidth);
      let height = parsePositiveNumber(lotHeight);
      if (!hasSite) {
        const acres = 10;
        const baseSide = Math.sqrt(acres * 43560);
        const aspect =
          imageSize && imageSize.width > 0 && imageSize.height > 0
            ? imageSize.width / imageSize.height
            : 1;
        const fallbackWidth = baseSide * Math.sqrt(aspect);
        const fallbackHeight = baseSide / Math.sqrt(aspect);
        const scaledWidth =
          imageSize && detectionScaleFtPerPx
            ? imageSize.width * detectionScaleFtPerPx
            : null;
        const scaledHeight =
          imageSize && detectionScaleFtPerPx
            ? imageSize.height * detectionScaleFtPerPx
            : null;
        width = scaledWidth ?? fallbackWidth;
        height = scaledHeight ?? fallbackHeight;
        autoFitSite(width, height, "Site Boundary");
        setShowSiteBounds(false);
        setSiteScaleLocked(true);
        setSiteSelectionMode(false);
      }
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
          manual_fields: {
            ...(currentInput?.manual_fields ?? {}),
            lot: {
              x: 0,
              y: 0,
              w: width || 0,
              h: height || 0,
            },
          },
        },
      });
      setImageUploadState("uploaded");
      setImageUploadNote("Image uploaded. Ready for detection.");
      setStatusMessage("Image uploaded.");
      if (width && height) {
        setImageUploadState("detecting");
        setImageUploadNote("Detecting site features…");
        void handleAnalyzeImageFeatures(data.image_path || "");
      } else {
        setStatusMessage("Image uploaded. Set site dimensions to run detection.");
      }
    } catch (error) {
      setImageName(file.name);
      setImageUploadState("failed");
      const message = uploadStatusMessage("image", error);
      setImageUploadNote(message);
      setStatusMessage(message);
    }
  };

  const uploadPlanPdf = async (file: File) => {
    if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
      const message = "PDF upload failed: Unsupported file. Use a PDF plan file.";
      setPlanPdfUploadState("failed");
      setPlanPdfUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    if (!token) {
      const message = "PDF upload failed: Sign in/connect backend to upload plan PDFs.";
      setPlanPdfUploadState("failed");
      setPlanPdfUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    setPlanPdfUploadState("uploading");
    setPlanPdfUploadMessage("Uploading PDF for review extraction...");
    setStatusMessage("Uploading plan PDF...");
    try {
      const activeProjectId = projectId || currentProject?.project_id || (await ensureProjectDraft());
      if (!activeProjectId) {
        throw new Error("Save or create a project before importing a plan PDF.");
      }
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", activeProjectId);
      const data = await postForm<UploadPlanPdfResponse>("/api/upload-plan-pdf", formData, { token });
      if (data.project) {
        setCurrentProject(data.project);
        setProjectId(data.project.project_id);
        resolvedProjectIdRef.current = data.project.project_id;
        if (data.project.latest_result) {
          setBackendResult(data.project.latest_result);
        }
      } else if (data.plan_pdf_analysis_v1) {
        setBackendResult((current) => ({
          ...(current ?? { success: true }),
          final_plan: {
            ...(current?.final_plan ?? { actions: [] }),
            meta: {
              ...(current?.final_plan?.meta ?? {}),
              plan_pdf_analysis_v1: data.plan_pdf_analysis_v1,
              plan_pdf_editable_sheet_v1: data.plan_pdf_editable_sheet_v1,
              candidate_review_inbox_v1: data.candidate_review_inbox_v1,
            },
          },
        }));
      }
      setPlanPdfUploadState("uploaded");
      setPlanPdfUploadMessage("Plan PDF analyzed. Extracted objects are review-required.");
      setActiveWorkspaceMode("data");
      setStatusMessage("Plan PDF analyzed. All extracted objects are review-required.");
      appendChatMessage(
        "assistant",
        "Plan PDF imported. I extracted review-required sheet candidates where embedded text was available and recorded needs for OCR, raster preview, and vector geometry where unsupported.",
        "status",
      );
    } catch (error) {
      setPlanPdfUploadState("failed");
      const message = uploadStatusMessage("pdf", error);
      setPlanPdfUploadMessage(message);
      setStatusMessage(message);
    }
  };

  const updatePlanPdfElement = async (
    elementId: string,
    updates: { text?: string; review_status?: string; move_target?: { x0: number; y0: number } },
  ) => {
    if (!token) return;
    const activeProjectId = projectId || currentProject?.project_id;
    if (!activeProjectId) {
      setStatusMessage("Save or load a project before editing PDF-derived sheet elements.");
      return;
    }
    try {
      const data = await patchJson<{
        success?: boolean;
        project?: ProjectRecord;
        plan_pdf_editable_sheet_v1?: PlanMeta["plan_pdf_editable_sheet_v1"];
        plan_pdf_changed_elements_v1?: PlanMeta["plan_pdf_changed_elements_v1"];
        candidate_review_inbox_v1?: CandidateReviewInbox;
      }>(`/api/projects/${activeProjectId}/plan-pdf/elements/${elementId}`, updates, { token });
      if (data.project) {
        setCurrentProject(data.project);
        if (data.project.latest_result) setBackendResult(data.project.latest_result);
      } else if (data.plan_pdf_editable_sheet_v1) {
        setBackendResult((current) => ({
          ...(current ?? { success: true }),
          final_plan: {
            ...(current?.final_plan ?? { actions: [] }),
            meta: {
              ...(current?.final_plan?.meta ?? {}),
              plan_pdf_editable_sheet_v1: data.plan_pdf_editable_sheet_v1,
              plan_pdf_changed_elements_v1: data.plan_pdf_changed_elements_v1,
              candidate_review_inbox_v1: data.candidate_review_inbox_v1,
            },
          },
        }));
      }
      setStatusMessage("PDF-derived sheet element updated. Review is still required.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "PDF element update failed.");
    }
  };

  const exportPlanPdfReport = async () => {
    const activeProjectId = projectId || currentProject?.project_id;
    if (!token || !activeProjectId) {
      setStatusMessage("Save or load a project before exporting the PDF extraction report.");
      return;
    }
    try {
      const data = await getJson<{ success?: boolean; report?: Record<string, unknown> }>(
        `/api/projects/${activeProjectId}/plan-pdf/report`,
        { token },
      );
      const blob = new Blob([JSON.stringify(data.report ?? {}, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${activeProjectId}_plan_pdf_extraction_report.json`;
      link.click();
      window.URL.revokeObjectURL(url);
      setStatusMessage("PDF extraction report exported.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "PDF extraction report export failed.");
    }
  };

  const exportPlanPdfReviewPdf = async () => {
    const activeProjectId = projectId || currentProject?.project_id;
    if (!token || !activeProjectId) {
      setStatusMessage("Save or load a project before exporting the PDF review sheet.");
      return;
    }
    const escapeHtml = (value: unknown) =>
      String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    try {
      const data = await getJson<{ success?: boolean; report?: Record<string, unknown> }>(
        `/api/projects/${activeProjectId}/plan-pdf/report`,
        { token },
      );
      const report = (data.report ?? {}) as Record<string, unknown>;
      const analysis = (report.analysis ?? {}) as PlanPdfAnalysis;
      const sheet = (report.editable_sheet ?? {}) as PlanPdfEditableSheet;
      const changed = (report.changed_elements ?? {}) as PlanPdfChangedElements;
      const elements = sheet.elements ?? [];
      const changedElements = changed.elements ?? [];
      const blockedCapabilities = Array.isArray(report.blocked_capabilities)
        ? report.blocked_capabilities.map(String)
        : [];
      const popup = window.open("", "_blank", "width=1200,height=900");
      if (!popup) {
        setStatusMessage("Browser blocked the PDF review sheet window.");
        return;
      }
      popup.document.write(`<!doctype html>
<html>
<head>
  <title>${escapeHtml(analysis.source_pdf?.filename || "Plan PDF")} review extraction</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; color: #0f172a; }
    h1, h2, p { margin: 0; }
    h1 { font-size: 22px; }
    h2 { color: #475569; font-size: 12px; letter-spacing: .12em; margin-top: 18px; text-transform: uppercase; }
    p, li, td, th { font-size: 12px; line-height: 1.45; }
    .banner { background: #fffbeb; border: 1px solid #f59e0b; color: #92400e; margin: 12px 0; padding: 10px; }
    .sheet { border: 2px solid #0f172a; min-height: 720px; padding: 24px; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
    .metric { border: 1px solid #cbd5e1; padding: 8px; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th, td { border: 1px solid #cbd5e1; padding: 6px; text-align: left; vertical-align: top; }
    th { background: #f8fafc; }
    @media print { button { display: none; } body { margin: 0.25in; } }
  </style>
</head>
<body>
  <button onclick="window.print()">Print PDF review sheet</button>
  <div class="sheet">
    <h1>${escapeHtml(analysis.source_pdf?.filename || "Plan PDF")} extraction review</h1>
    <p>${escapeHtml(analysis.page_count ?? 0)} page(s) · ${escapeHtml(analysis.source_confidence || "imported_pdf_review_required")} · review required</p>
    <div class="banner">
      PDF-derived labels, dimensions, title blocks, and edits are imported source evidence only. They are not survey-backed, engineer-approved, stamped, sealed, signed, certified, approved for construction, or construction-release evidence.
    </div>
    <div class="grid">
      ${planPdfExtractionSummaryRows
        .map(([label, value]) => `<div class="metric"><p>${escapeHtml(label)}</p><strong>${escapeHtml(value)}</strong></div>`)
        .join("")}
    </div>
    <h2>Editable / Review Candidates</h2>
    <table>
      <thead><tr><th>Type</th><th>Text</th><th>Status</th><th>Source Confidence</th></tr></thead>
      <tbody>${(elements.length ? elements.slice(0, 80) : [])
        .map(
          (element) =>
            `<tr><td>${escapeHtml(element.type || "element")}</td><td>${escapeHtml(element.text || "")}</td><td>${escapeHtml(element.review_status || "pending")}</td><td>${escapeHtml(element.source_confidence || analysis.source_confidence || "imported_pdf_review_required")}</td></tr>`,
        )
        .join("") || `<tr><td colspan="4">No extracted editable candidates were recorded.</td></tr>`}</tbody>
    </table>
    <h2>Changed Elements</h2>
    <table>
      <thead><tr><th>Type</th><th>Original</th><th>Current</th><th>Status</th></tr></thead>
      <tbody>${(changedElements.length ? changedElements.slice(0, 40) : [])
        .map(
          (element) =>
            `<tr><td>${escapeHtml(element.type || "element")}</td><td>${escapeHtml(element.original_text || "")}</td><td>${escapeHtml(element.text || "")}</td><td>${escapeHtml(element.review_status || "pending")}${element.moved ? " / moved" : ""}${element.changed_text ? " / text edited" : ""}</td></tr>`,
        )
        .join("") || `<tr><td colspan="4">No PDF-derived sheet edits have been recorded.</td></tr>`}</tbody>
    </table>
    <h2>Unreadable / OCR / Vector Blockers</h2>
    <ul>${(blockedCapabilities.length ? blockedCapabilities : ["No extraction blockers recorded."])
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("")}</ul>
  </div>
</body>
</html>`);
      popup.document.close();
      setStatusMessage("Opened PDF extraction review sheet.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "PDF review sheet export failed.");
    }
  };

  function mapSurveyPointsToSite(points: number[][]) {
    const width = parsePositiveNumber(lotWidth);
    const height = parsePositiveNumber(lotHeight);
    if (!points.length || !width || !height) return [];
    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = Math.max(maxX - minX, 1e-6);
    const spanY = Math.max(maxY - minY, 1e-6);
    const withinLot = minX >= 0 && minY >= 0 && maxX <= width * 1.2 && maxY <= height * 1.2;
    const mapPoint = (p: number[]) => {
      const x = withinLot ? p[0] : ((p[0] - minX) / spanX) * width;
      const y = withinLot ? p[1] : ((p[1] - minY) / spanY) * height;
      const z = typeof p[2] === "number" ? p[2] : undefined;
      return { x, y, z };
    };
    const mapped = points.map(mapPoint);
    const step = Math.max(1, Math.ceil(mapped.length / 2000));
    return mapped.filter((_, idx) => idx % step === 0);
  }

  const summarizeExistingConditionsUpload = (data: UploadExistingConditionsResponse) => {
    const matrix = data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix ?? [];
    const countByStatus = (status: string) => matrix.filter((item) => item.status === status).length;
    const canonical = countByStatus("canonical");
    const reviewRequired = countByStatus("review_required");
    const metadataOnly = countByStatus("metadata_only");
    const blocked = countByStatus("blocked");
    const confidence = String(
      data.import_validation?.terrain_source_confidence?.label ??
        ((data.existing_conditions_package?.terrain_source_confidence as Record<string, unknown> | undefined)?.label) ??
        "missing",
    );
    const blockerMessages = matrix
      .flatMap((item) => item.blocker_messages ?? [])
      .concat((data.blockers ?? []).map((item) => String(item.reason || item.message || item.field || "")))
      .filter((item, index, items) => item && items.indexOf(item) === index)
      .slice(0, 5);
    const targets = matrix
      .flatMap((item) => item.canonical_targets ?? [])
      .filter((item, index, items) => item && items.indexOf(item) === index);
    return [
      `Existing-condition import: ${data.filename ?? "file"} (${data.file_type ?? "unknown"}).`,
      `Matrix: canonical ${canonical}, review-required ${reviewRequired}, metadata-only ${metadataOnly}, blocked ${blocked}.`,
      `Terrain confidence: ${confidence}. Canonical targets: ${targets.length ? targets.join(", ") : "none"}.`,
      blockerMessages.length ? `Exact blockers:\n${blockerMessages.map((item) => `- ${item}`).join("\n")}` : "Exact blockers: none recorded.",
    ].join("\n");
  };

  const uploadExistingConditions = async (file: File) => {
    const supportedSurveyPattern = /\.(csv|geojson|json|dxf|shp|zip|gpkg|tif|tiff|las|laz|xml|landxml)$/i;
    if (!supportedSurveyPattern.test(file.name)) {
      const message = "Survey/topo upload failed: Unsupported file. Use CSV, DXF, LAS/LAZ, GeoTIFF, GeoJSON, SHP/ZIP, GPKG, XML, or LandXML.";
      setSurveyFileName(file.name);
      setSurveyUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    if (!token) {
      const message = "Survey/topo upload failed: Sign in/connect backend to upload existing-condition files.";
      setSurveyFileName(file.name);
      setSurveyUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    setSurveyUploadMessage(`Uploading ${file.name} for source review...`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadExistingConditionsResponse>("/api/upload-existing-conditions", formData, {
        token,
      });
      const storedFilename = data.stored_filename || file.name;
      const canonical = data.canonical_existing_conditions ?? {};
      const survey = canonical.survey && typeof canonical.survey === "object" ? canonical.survey as Record<string, unknown> : {};
      const surveyPoints = Array.isArray(survey.points)
        ? (survey.points as Array<Record<string, unknown>>)
            .map((point) => [Number(point.x), Number(point.y), Number(point.z)])
            .filter((point) => point.every((value) => Number.isFinite(value)))
        : [];
      setSurveyFileName(storedFilename);
      setSurveyPoints(surveyPoints);
      setSurveyPreviewPoints(mapSurveyPointsToSite(surveyPoints));
      setSurveyDiagnostics({
        fileType: data.file_type,
        parseSuccess: Boolean(data.success && surveyPoints.length),
        pointCount: Number(survey.point_count ?? surveyPoints.length ?? 0),
        contourCount: Number(survey.breakline_count ?? 0),
        recognizedColumns: {},
        invalidRows: 0,
        bounds: survey.bounds as UploadSurveyResponse["bounds"],
        elevationRange: survey.elevation_range as UploadSurveyResponse["elevation_range"],
        warnings: data.warnings,
      });
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        survey_file: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          survey_url: data.file_url || "",
        },
        survey_file_type: data.file_type,
        survey_parse_success: Boolean(data.success && surveyPoints.length),
        survey_point_count: Number(survey.point_count ?? surveyPoints.length ?? 0),
        survey_point_warnings: data.warnings ?? [],
        survey_points: surveyPoints,
        survey_bounds: (survey.bounds as SiteInputs["survey_bounds"]) ?? null,
        survey_elevation_range: (survey.elevation_range as SiteInputs["survey_elevation_range"]) ?? null,
        use_survey_for_grading: useSurveyForGrading,
        existing_conditions_import: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          file_type: data.file_type,
          import_matrix: data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix ?? [],
          canonical_vs_metadata_only: data.canonical_vs_metadata_only ?? data.import_validation?.canonical_vs_metadata_only ?? {},
          blockers: data.blockers ?? data.import_validation?.blockers ?? [],
          package_status: String(data.existing_conditions_package?.status ?? "unknown"),
        },
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
            existing_conditions_package: data.existing_conditions_package,
            existing_conditions_import_validation: data.import_validation,
            existing_conditions_summary: data.existing_conditions_summary,
            canonical_existing_conditions: data.canonical_existing_conditions,
            canonical_existing_conditions_model: data.canonical_existing_conditions?.canonical_existing_conditions_model,
            import_matrix: data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix,
            canonical_vs_metadata_only: data.canonical_vs_metadata_only ?? data.import_validation?.canonical_vs_metadata_only,
          },
        },
      });
      appendChatMessage("assistant", summarizeExistingConditionsUpload(data), "status");
      setSurveyUploadMessage(
        data.existing_conditions_package?.status === "ready"
          ? "Survey/topo imported and ready for review."
          : "Survey/topo imported; exact review needs are recorded.",
      );
      setStatusMessage(
        data.existing_conditions_package?.status === "ready"
          ? "Existing conditions imported and ready."
          : "Existing conditions imported; review needs are recorded.",
      );
    } catch (error) {
      setSurveyFileName(file.name);
      const message = uploadStatusMessage("survey", error);
      setSurveyUploadMessage(message);
      setStatusMessage(message);
    }
  };

  const mapDetectionToPlacement = useCallback(
    (
      detection: {
        kind: string;
        bbox: [number, number, number, number];
        confidence?: number;
        geometry_type?: "polygon" | "polyline" | "rect";
        geometry?: Array<[number, number]>;
      },
      imageWidth: number,
      imageHeight: number,
    ): BuildingPlacement | null => {
      if (!imageWidth || !imageHeight) return null;
      const [x, y, w, h] = detection.bbox;
      const width = parsePositiveNumber(lotWidth);
      const height = parsePositiveNumber(lotHeight);
      if (!width || !height) return null;
      const scaleFtPerPx = detectionScaleFtPerPx && detectionScaleFtPerPx > 0 ? detectionScaleFtPerPx : null;
      const mapPoint = (pt: [number, number]) => {
        const [px, py] = pt;
        const mappedX = scaleFtPerPx ? px * scaleFtPerPx : (px / imageWidth) * width;
        const mappedY = scaleFtPerPx ? py * scaleFtPerPx : (py / imageHeight) * height;
        return [mappedX, mappedY] as [number, number];
      };
      const mappedGeometry = Array.isArray(detection.geometry)
        ? detection.geometry.map((pt) => mapPoint(pt))
        : null;
      const geometryBounds = mappedGeometry?.length
        ? mappedGeometry.reduce(
            (acc, pt) => {
              return {
                minX: Math.min(acc.minX, pt[0]),
                minY: Math.min(acc.minY, pt[1]),
                maxX: Math.max(acc.maxX, pt[0]),
                maxY: Math.max(acc.maxY, pt[1]),
              };
            },
            {
              minX: Number.POSITIVE_INFINITY,
              minY: Number.POSITIVE_INFINITY,
              maxX: Number.NEGATIVE_INFINITY,
              maxY: Number.NEGATIVE_INFINITY,
            },
          )
        : null;
      const mappedX = geometryBounds
        ? geometryBounds.minX
        : scaleFtPerPx
          ? x * scaleFtPerPx
          : (x / imageWidth) * width;
      const mappedY = geometryBounds
        ? geometryBounds.minY
        : scaleFtPerPx
          ? y * scaleFtPerPx
          : (y / imageHeight) * height;
      const mappedW = geometryBounds
        ? geometryBounds.maxX - geometryBounds.minX
        : scaleFtPerPx
          ? w * scaleFtPerPx
          : (w / imageWidth) * width;
      const mappedD = geometryBounds
        ? geometryBounds.maxY - geometryBounds.minY
        : scaleFtPerPx
          ? h * scaleFtPerPx
          : (h / imageHeight) * height;
      const typeMap: Record<string, SiteObjectType> = {
        building: "building",
        road: "road",
        parking: "parking",
        sidewalk: "sidewalk",
        driveway: "driveway",
        basin: "basin",
        pool: "pool",
        open_space: "open_space",
      };
      const type = typeMap[detection.kind] ?? "building";
      const labelMap: Record<SiteObjectType, string> = {
        site: "Site",
        setback_zone: "Setback Zone",
        no_build_zone: "No-Build Zone",
        building: "Detected Building",
        retail_building: "Detected Retail",
        multifamily_building: "Detected Multifamily",
        industrial_building: "Detected Industrial",
        office_building: "Detected Office",
        pad: "Detected Pad",
        pool: "Detected Pool",
        amenity: "Detected Amenity",
        open_space: "Detected Open Space",
        entrance: "Detected Entrance",
        driveway: "Detected Driveway",
        road: "Detected Road",
        parking: "Detected Parking",
        sidewalk: "Detected Path",
        basin: "Detected Basin",
        outfall: "Detected Outfall",
        inlet: "Detected Inlet",
        manhole: "Detected Manhole",
        hydrant: "Detected Hydrant",
        utility_corridor: "Detected Utility Corridor",
        lot_block: "Detected Lot Block",
        bridge: "Detected Bridge",
        custom: "Detected Custom Geometry",
      };
      return {
        id: `detected_${Math.random().toString(36).slice(2, 9)}`,
        label: labelMap[type] ?? "Detected Object",
        x: clampValue(mappedX, 0, width - mappedW),
        y: clampValue(mappedY, 0, height - mappedD),
        w: Math.max(12, mappedW),
        d: Math.max(12, mappedD),
        rotation: 0,
        type,
        source: "detected_from_image",
        generated: false,
        confidence: detection.confidence ?? 0.2,
        confirmed: false,
        geometryType: detection.geometry_type,
        geometry: mappedGeometry ?? undefined,
        capabilities: { movable: true, resizable: true, rotatable: false, deletable: true },
        placed: true,
        meta: {
          detection_kind: detection.kind,
          confidence: detection.confidence ?? 0.2,
          detected: true,
          scale_source: scaleFtPerPx ? "calibrated" : "approximate",
          scale_ft_per_px: scaleFtPerPx ?? null,
        },
      };
    },
    [detectionScaleFtPerPx, lotHeight, lotWidth],
  );


  const handleAnalyzeImageFeatures = useCallback(async (overridePath?: string) => {
    if (!token) {
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Site context needs connection",
        detail: "Sign in/connect backend to detect site context.",
        nextAction: "Sign in or reconnect backend, then run map/image detection again.",
      });
      return;
    }
    const sourcePath = overridePath || mapSnapshotPath;
    if (!sourcePath) {
      askClarification(
        "Upload a site image or map snapshot before running detection. Want me to open the Site Inputs panel?",
        "upload_image_then_detect",
      );
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Site context needs image",
        detail: "A site image or map snapshot is required before detection.",
        nextAction: "Upload a site image or map snapshot, then run detection.",
      });
      return;
    }
    clearGeneratedPreview();
    setImageUploadState("detecting");
    setImageUploadNote("Detecting site features…");
    updateProjectStatus({
      state: "working",
      area: "setup",
      title: "Detecting site context",
      detail: "Civora is detecting site features from the uploaded map/image.",
      nextAction: "Wait for detections, then review suggested objects before generating.",
    });
    const width = parsePositiveNumber(lotWidth);
    const height = parsePositiveNumber(lotHeight);
    if (!width || !height) {
      askClarification(
        "I need the site boundary dimensions before detection. What size should the site be?",
        "set_site_then_detect",
      );
      setImageUploadState("uploaded");
      setImageUploadNote("Image uploaded. Set site dimensions to run detection.");
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Site context needs site size",
        detail: "Site boundary dimensions are required before detection.",
        nextAction: "Set site width/depth or draw a boundary, then run detection again.",
      });
      return;
    }
    try {
      const result = await postJson<ImageDetectResponse>(
        "/api/image/detect-features",
        { image_path: sourcePath, source_type: "map" },
        { token },
      );
      const detections = Array.isArray(result.detections) ? result.detections : [];
      const mapped = detections
        .map((det) => mapDetectionToPlacement(det, result.image_width ?? 0, result.image_height ?? 0))
        .filter((item): item is BuildingPlacement => Boolean(item));
      setDetectedPlacements(mapped);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        detected_objects: mapped,
      };
      await saveProject({
        silent: true,
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
      setImageUploadState("uploaded");
      setImageUploadNote(mapped.length ? "Detection complete. Review suggested objects." : "No detections found.");
      updateProjectStatus({
        state: result.success ? "needs review" : "blocked",
        area: "setup",
        title: result.success ? "Site context needs review" : "Site context needs attention",
        detail: result.success
          ? (mapped.length ? "Detection complete. Review suggested objects." : "Detection complete. No detections were found.")
          : result.message || "Detection failed.",
        nextAction: result.success
          ? "Review suggested objects in Object Manager before generating."
          : "Check the map/image source and retry detection.",
      });
    } catch (error) {
      setImageUploadState("failed");
      setImageUploadNote("Detection failed.");
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Site context needs attention",
        detail: error instanceof Error ? error.message : "Detection failed.",
        nextAction: "Check the uploaded map/image and backend connection, then retry detection.",
      });
    }
  }, [
    askClarification,
    clearGeneratedPreview,
    currentProject,
    lotHeight,
    lotWidth,
    mapDetectionToPlacement,
    mapSnapshotPath,
    payloadPreview,
    saveProject,
    token,
    updateProjectStatus,
  ]);

  const handleAnalyzeSiteAccess = useCallback(() => {
    const confirmed = buildingPlacements.filter(
      (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
    );
    const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
    const buildingTypes = new Set<SiteObjectType>([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
    ]);
    const buildings = confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType));
    const access = confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType));
    if (!buildings.length || !access.length) {
      setAnalysisIssues([]);
      setAnalysisPaths([]);
      setAnalysisSelectedIssueId(null);
      setAnalysisFocusLocked(false);
      let reason = "Address provides site context only. Add or confirm buildings and access objects to run analysis.";
      if (!buildings.length && access.length) {
        reason = "Add or confirm buildings to run access analysis.";
      }
      if (!access.length && buildings.length) {
        reason = "Add or confirm roads, driveways, or access objects to run access analysis.";
      }
      setAnalysisEmptyReason(reason);
      askClarification(reason, "access_analysis_missing");
      return;
    }
    setAnalysisEmptyReason(null);
    const issues: Array<{
      id: string;
      buildingId: string;
      accessId: string;
      distanceFt: number;
      thresholdFt: number;
      message: string;
      pathId: string;
      issueType: "distance" | "no_access" | "no_buildings" | "no_access_objects";
    }> = [];
    const paths: Array<{
      id: string;
      buildingId: string;
      accessId: string;
      from: { x: number; y: number };
      to: { x: number; y: number };
      label: string;
      points?: Array<{ x: number; y: number }>;
    }> = [];
    const threshold = 150;
    const adjacencyGap = 25;
    const buildingAccessGap = 60;

    type GraphEdge = { to: string; weight: number; points: Array<{ x: number; y: number }> };
    const graph: Record<string, GraphEdge[]> = {};

    const addEdge = (from: string, to: string, weight: number, points: Array<{ x: number; y: number }>) => {
      if (!graph[from]) graph[from] = [];
      graph[from].push({ to, weight, points });
    };

    const clampToRect = (pt: { x: number; y: number }, rect: { x: number; y: number; w: number; d: number }) => ({
      x: Math.min(Math.max(pt.x, rect.x), rect.x + rect.w),
      y: Math.min(Math.max(pt.y, rect.y), rect.y + rect.d),
    });

    const distancePointToRect = (pt: { x: number; y: number }, rect: { x: number; y: number; w: number; d: number }) => {
      const closest = clampToRect(pt, rect);
      const dx = pt.x - closest.x;
      const dy = pt.y - closest.y;
      return { distance: Math.hypot(dx, dy), closest };
    };

    const closestPointOnSegment = (
      a: { x: number; y: number },
      b: { x: number; y: number },
      p: { x: number; y: number },
    ) => {
      const abx = b.x - a.x;
      const aby = b.y - a.y;
      const ab2 = abx * abx + aby * aby;
      if (!ab2) return { x: a.x, y: a.y };
      const t = ((p.x - a.x) * abx + (p.y - a.y) * aby) / ab2;
      const clamped = Math.max(0, Math.min(1, t));
      return { x: a.x + abx * clamped, y: a.y + aby * clamped };
    };

    const getAccessPolyline = (item: BuildingPlacement): Array<{ x: number; y: number }> => {
      if (item.geometryType === "polyline" && Array.isArray(item.geometry) && item.geometry.length > 1) {
        return item.geometry.map(([x, y]) => ({ x, y }));
      }
      const x = item.x ?? 0;
      const y = item.y ?? 0;
      const isHorizontal = item.w >= item.d;
      if (item.type === "parking") {
        const params = (item.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
        const stallDepth = Number.isFinite(params.stallDepth) ? Number(params.stallDepth) : 18;
        const aisleWidth = Number.isFinite(params.aisleWidth) ? Number(params.aisleWidth) : 24;
        const angleDeg = Number.isFinite(params.angleDeg) ? Number(params.angleDeg) : 90;
        const loading = params.loading === "single" ? "single" : "double";
        const angleRad = (Math.max(Math.min(angleDeg, 89), 0) * Math.PI) / 180;
        const depthAdj = stallDepth / Math.cos(angleRad || 0.0001);
        const moduleDepth = depthAdj * (loading === "double" ? 2 : 1) + aisleWidth;
        const scale = item.d < moduleDepth ? item.d / moduleDepth : 1;
        const scaledStall = depthAdj * scale;
        const scaledAisle = aisleWidth * scale;
        const centerY =
          loading === "double"
            ? y + (item.d - scaledAisle) / 2 + scaledAisle / 2
            : y + scaledStall + scaledAisle / 2;
        const start = { x: x + 4, y: centerY };
        const end = { x: x + item.w - 4, y: centerY };
        return [start, end];
      }
      if (isHorizontal) {
        return [
          { x, y: y + item.d / 2 },
          { x: x + item.w, y: y + item.d / 2 },
        ];
      }
      return [
        { x: x + item.w / 2, y },
        { x: x + item.w / 2, y: y + item.d },
      ];
    };

    const accessPaths = access.map((item) => ({
      id: item.id,
      type: item.type,
      points: getAccessPolyline(item),
    }));

    accessPaths.forEach((path) => {
      const points = path.points;
      if (points.length < 2) return;
      for (let i = 0; i < points.length - 1; i += 1) {
        const a = points[i];
        const b = points[i + 1];
        const weight = Math.hypot(b.x - a.x, b.y - a.y);
        const nodeA = `${path.id}-p${i}`;
        const nodeB = `${path.id}-p${i + 1}`;
        addEdge(nodeA, nodeB, weight, [a, b]);
        addEdge(nodeB, nodeA, weight, [b, a]);
      }
    });

    const pathEndpoints = accessPaths
      .map((path) => {
        const points = path.points;
        if (points.length < 2) return null;
        return [
          { id: `${path.id}-p0`, point: points[0] },
          { id: `${path.id}-p${points.length - 1}`, point: points[points.length - 1] },
        ];
      })
      .flat()
      .filter(Boolean) as Array<{ id: string; point: { x: number; y: number } }>;

    for (let i = 0; i < pathEndpoints.length; i += 1) {
      for (let j = i + 1; j < pathEndpoints.length; j += 1) {
        const a = pathEndpoints[i];
        const b = pathEndpoints[j];
        const distance = Math.hypot(a.point.x - b.point.x, a.point.y - b.point.y);
        if (distance <= adjacencyGap) {
          addEdge(a.id, b.id, Math.max(distance, 1), [a.point, b.point]);
          addEdge(b.id, a.id, Math.max(distance, 1), [b.point, a.point]);
        }
      }
    }

    const buildPathPoints = (edgePoints: Array<Array<{ x: number; y: number }>>) => {
      const points: Array<{ x: number; y: number }> = [];
      edgePoints.forEach((segment) => {
        segment.forEach((pt, idx) => {
          if (!points.length) {
            points.push(pt);
            return;
          }
          const last = points[points.length - 1];
          if (Math.hypot(last.x - pt.x, last.y - pt.y) < 0.01) return;
          if (idx === 0) {
            points.push(pt);
            return;
          }
          points.push(pt);
        });
      });
      return points;
    };

    buildings.forEach((building) => {
      const buildingNodeId = `building-${building.id}`;
      const buildingRect = { x: building.x ?? 0, y: building.y ?? 0, w: building.w, d: building.d };
      graph[buildingNodeId] = [];
      accessPaths.forEach((path) => {
        const points = path.points;
        if (points.length < 2) return;
        let closestDistance = Number.POSITIVE_INFINITY;
        let closestPoint: { x: number; y: number } | null = null;
        let closestNodeId: string | null = null;
        for (let i = 0; i < points.length - 1; i += 1) {
          const a = points[i];
          const b = points[i + 1];
          const segmentPoint = closestPointOnSegment(a, b, {
            x: buildingRect.x + buildingRect.w / 2,
            y: buildingRect.y + buildingRect.d / 2,
          });
          const { distance } = distancePointToRect(segmentPoint, buildingRect);
          if (distance < closestDistance) {
            closestDistance = distance;
            closestPoint = segmentPoint;
            closestNodeId = `${path.id}-p${i}`;
          }
        }
        if (closestPoint && closestNodeId && closestDistance <= buildingAccessGap) {
          addEdge(buildingNodeId, closestNodeId, Math.max(closestDistance, 1), [
            clampToRect(closestPoint, buildingRect),
            closestPoint,
          ]);
        }
      });

      const distances = new Map<string, number>();
      const prev = new Map<string, { node: string; points: Array<{ x: number; y: number }> }>();
      const unvisited = new Set<string>(Object.keys(graph));
      distances.set(buildingNodeId, 0);

      while (unvisited.size) {
        let current: string | null = null;
        let bestDistance = Number.POSITIVE_INFINITY;
        unvisited.forEach((nodeId) => {
          const dist = distances.get(nodeId);
          if (dist !== undefined && dist < bestDistance) {
            bestDistance = dist;
            current = nodeId;
          }
        });
        if (!current) break;
        unvisited.delete(current);
        const edges = graph[current] ?? [];
        edges.forEach((edge) => {
          if (!unvisited.has(edge.to)) return;
          const nextDist = bestDistance + edge.weight;
          const existing = distances.get(edge.to);
          if (existing === undefined || nextDist < existing) {
            distances.set(edge.to, nextDist);
            prev.set(edge.to, { node: current as string, points: edge.points });
          }
        });
      }

      let closestAccessId: string | null = null;
      let closestDistance = Number.POSITIVE_INFINITY;
      let closestNodeId: string | null = null;
      accessPaths.forEach((path) => {
        path.points.forEach((_, idx) => {
          const nodeId = `${path.id}-p${idx}`;
          const dist = distances.get(nodeId);
          if (dist !== undefined && dist < closestDistance) {
            closestDistance = dist;
            closestNodeId = nodeId;
            closestAccessId = path.id;
          }
        });
      });

      if (!closestAccessId || !Number.isFinite(closestDistance)) {
        issues.push({
          id: `${building.id}-no-access`,
          buildingId: building.id,
          accessId: "",
          distanceFt: 0,
          thresholdFt: threshold,
          message: `Building ${building.label} has no access path.`,
          pathId: "",
          issueType: "no_access",
        });
        return;
      }

      const edgePoints: Array<Array<{ x: number; y: number }>> = [];
      let cursor: string | null = closestNodeId;
      while (cursor && cursor !== buildingNodeId) {
        const step = prev.get(cursor);
        if (!step) break;
        edgePoints.unshift(step.points);
        cursor = step.node;
      }

      const points = buildPathPoints(edgePoints);
      const from = points[0] ?? { x: buildingRect.x, y: buildingRect.y };
      const to = points[points.length - 1] ?? from;
      const pathId = `${building.id}-${closestAccessId}`;
      paths.push({
        id: pathId,
        buildingId: building.id,
        accessId: closestAccessId,
        from,
        to,
        label: `Access ${Math.round(closestDistance)} ft`,
        points,
      });
      if (closestDistance > threshold) {
        issues.push({
          id: `${building.id}-distance`,
          buildingId: building.id,
          accessId: closestAccessId,
          distanceFt: closestDistance,
          thresholdFt: threshold,
          message: `Building ${building.label} is ${Math.round(closestDistance)} ft from nearest access (>${threshold} ft).`,
          pathId,
          issueType: "distance",
        });
      }
    });

    setAnalysisIssues(issues);
    setAnalysisPaths(paths);
    setAnalysisSelectedIssueId(issues[0]?.id ?? null);
    setAnalysisFocusLocked(Boolean(issues[0]?.id));
    setStatusMessage("Site access analysis complete (conceptual).");
  }, [askClarification, buildingPlacements]);


  useEffect(() => {
    if (!analysisSelectedIssueId) {
      setAnalysisFocusLocked(false);
    }
  }, [analysisSelectedIssueId]);

  const persistSiteRotation = useCallback(
    async (nextValue: number) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        site_rotation_deg: nextValue,
      };
      await saveProject({
        silent: true,
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
    },
    [currentProject, payloadPreview, saveProject],
  );

  const scheduleRotationSave = useCallback(
    (nextValue: number) => {
      if (rotationSaveTimeoutRef.current) {
        window.clearTimeout(rotationSaveTimeoutRef.current);
      }
      rotationSaveTimeoutRef.current = window.setTimeout(() => {
        void persistSiteRotation(nextValue);
        rotationSaveTimeoutRef.current = null;
      }, 400);
    },
    [persistSiteRotation],
  );

  useEffect(() => {
    if (activePlacementId) return;
    const pending = buildingPlacements.find((item) => !item.placed && item.type !== "site");
    if (pending) {
      setActivePlacementId(pending.id);
    }
  }, [activePlacementId, buildingPlacements]);

  const analyzeMapSnapshot = async () => {
    if (!token || !mapSnapshotPath) return;
    try {
      const data = await postJson<MapAnalysis>(
        "/api/image/analyze",
        {
          image_path: mapSnapshotPath,
          source_name: "map_snapshot",
          source_type: "map",
        },
        { token },
      );
      setMapAnalysis(data);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        map_analysis: data,
      };
      await saveProject({
        silent: true,
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
      setStatusMessage("Map snapshot analyzed.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Map snapshot analysis failed.",
      );
    }
  };

  const autoFitSite = useCallback(
    (
      width: number,
      height: number,
      label?: string,
      siteIdOverride?: string | null,
      fitMap: boolean = true,
      lockSite: boolean = true,
      preserveExistingObjects: boolean = true,
    ) => {
      const clampedW = Math.max(width, 1);
      const clampedH = Math.max(height, 1);
      setLotWidth(clampedW.toFixed(0));
      setLotHeight(clampedH.toFixed(0));
      setSiteScaleLocked(lockSite);
      setBuildingPlacements((prev) => {
        const filtered = preserveExistingObjects ? prev.filter((item) => item.type !== "site") : [];
        const existingSite = prev.find((item) => item.type === "site");
        const siteId =
          siteIdOverride ||
          existingSite?.id ||
          `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const siteLabel = label || existingSite?.label || "Site Boundary";
        return [
          {
            id: siteId,
            label: siteLabel,
            type: "site",
            w: clampedW,
            d: clampedH,
            x: 0,
            y: 0,
            rotation: 0,
            locked: lockSite,
            placed: true,
            source: "user",
            generated: false,
            capabilities: {
              movable: !lockSite,
              resizable: !lockSite,
              rotatable: !lockSite,
              deletable: false,
            },
            systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
            meta: {
              category: "site",
              site_boundary_state: lockSite ? "locked_canonical" : "draft_editable",
              source_ui_mode: "site_setup",
              engineering_status: "review_required",
              construction_release_allowed: false,
              acres: Number(((clampedW * clampedH) / SQFT_PER_ACRE).toFixed(3)),
            },
          },
          ...filtered,
        ];
      });
      if (fitMap) {
        setFitToSiteRequest((value) => value + 1);
      }
    },
    [],
  );

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

  const runAutoExistingConditionsAfterSiteLock = useCallback(
    async (projectInputOverride?: ProjectInput) => {
      const currentInput = projectInputOverride ?? currentProject?.project_input ?? payloadPreview;
      const currentSiteInputs = (currentInput?.meta?.site_inputs ?? {}) as SiteInputs;
      const geocode = currentSiteInputs.geocode;
      const address = String(currentSiteInputs.address || geocode?.display_name || siteAddress || "").trim();
      const site = buildingPlacements.find((item) => item.type === "site");
      const width = parsePositiveNumber(lotWidth) ?? site?.w ?? viewportFootprint?.widthFt ?? 0;
      const height = parsePositiveNumber(lotHeight) ?? site?.d ?? viewportFootprint?.heightFt ?? 0;
      const runKey = [
        projectId || currentProject?.project_id || "local",
        address,
        geocode?.lat ?? viewportCenter?.lat ?? "",
        geocode?.lng ?? viewportCenter?.lng ?? "",
        Math.round(width),
        Math.round(height),
        site?.id ?? "",
      ].join("|");

      if (!address && !(geocode?.lat && geocode?.lng)) {
        setAutoExistingConditionsStatus({
          status: "blocked",
          message: "Site is locked. Add an address to automatically check roads, buildings, terrain, constraints, and utilities.",
          candidateCount: 0,
          missing: ["address/geocode"],
        });
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Site context needs address",
          detail: "Site is locked, but address/geocode context is missing.",
          nextAction: "Add an address or map center context, then recheck sources inside the site.",
        });
        return;
      }
      if (!token) {
        setAutoExistingConditionsStatus({
          status: "blocked",
          message: "Site is locked. Sign in or connect the backend to run automatic source discovery.",
          candidateCount: 0,
          missing: ["backend session"],
        });
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Site context needs connection",
          detail: "Automatic source discovery needs a backend session.",
          nextAction: "Sign in or reconnect backend, then recheck sources inside the site.",
        });
        return;
      }
      if (autoExistingRunKeyRef.current === runKey) {
        return;
      }
      autoExistingRunKeyRef.current = runKey;
      setOnlineDiscoveryBusy(true);
      setAutoExistingConditionsStatus({
        status: "running",
        message: "Checking parcels, roads, buildings, constraints, utilities, elevation, and grading context inside the locked site...",
        candidateCount: 0,
        missing: [],
      });
      updateProjectStatus({
        state: "working",
        area: "setup",
        title: "Detecting site context",
        detail: "Checking parcels, roads, buildings, constraints, utilities, elevation, and grading context inside the locked site.",
        nextAction: "Wait for source candidates or an exact provider/backend blocker.",
      });

      try {
        let onlineFetch: OnlineExistingConditionsFetchResponse | null = null;
        try {
          onlineFetch = await postJson<OnlineExistingConditionsFetchResponse>(
            "/api/existing-conditions/fetch-online",
            {
              address: address || geocode?.display_name || "Locked site",
              bbox: viewportFootprint?.bounds
                ? {
                    north: viewportFootprint.bounds.north,
                    south: viewportFootprint.bounds.south,
                    east: viewportFootprint.bounds.east,
                    west: viewportFootprint.bounds.west,
                    center_lat: viewportFootprint.bounds.centerLat,
                    center_lng: viewportFootprint.bounds.centerLng,
                    width_ft: width || viewportFootprint.widthFt,
                    height_ft: height || viewportFootprint.heightFt,
                  }
                : undefined,
              include_floodplain: true,
              include_wetlands: true,
              include_parcels: true,
              include_building_footprints: true,
              include_roads: true,
              include_utilities: true,
              include_contours: true,
              include_elevation: true,
              provider_registry: currentSiteInputs.local_gis_provider_registry_v1 ?? siteInputs?.local_gis_provider_registry_v1 ?? {},
            },
            { token },
          );
        } catch (error) {
          onlineFetch = {
            success: false,
            status: "fetch_failed",
            online_existing_conditions_discovery_v1: {
              version: "online_existing_conditions_discovery_v1",
              status: "fetch_failed",
              candidate_count: 0,
              sources: [],
              blockers: [error instanceof Error ? error.message : "Automatic existing-condition discovery failed."],
              review_required: true,
              acceptance_status: "missing",
              truth_label:
                "Automatic existing-condition discovery failed; no source candidate is treated as accepted project evidence.",
            },
          };
        }

      const discovery = onlineFetch?.online_existing_conditions_discovery_v1;
      const sources = Array.isArray(discovery?.sources) ? discovery.sources : [];
      const candidateCount = Number(discovery?.candidate_count ?? 0);
      const discoveryStatus = String(discovery?.status || onlineFetch?.status || "");
      const providerFailed = discoveryStatus.includes("failed") || Boolean(discovery?.blockers?.length && candidateCount === 0);
      const providersAbsent = candidateCount === 0 && sources.length === 0 && !configuredLocalGisProviders.length;
      const missing = sources
        .filter((source) => Number(source.candidate_count ?? 0) <= 0)
        .map((source) => String(source.label || source.key || source.source_type || "source unavailable"))
        .slice(0, 6);
      const slopePct = parsePositiveNumber(assumedTerrainSlopePct) ?? 8;
      const needsAssumedSlope = !hasTerrainSource && !surveySlopeEstimate?.slope_percent;
      const slopeEstimateOverride = needsAssumedSlope ? buildAssumedSlopeEstimate(slopePct) : null;
      if (needsAssumedSlope && slopeEstimateOverride) {
        setAssumedTerrainSlopePct(String(slopePct));
        setUseSurveyForGrading(false);
        setSurveySlopeEstimate(slopeEstimateOverride);
      }

      const autoExistingConditions = {
        version: "auto_existing_conditions_v1",
        status: candidateCount > 0 || slopeEstimateOverride || hasTerrainSource ? "ready_for_review" : "blocked_or_missing_sources",
        triggered_by: "site_lock",
        clipped_to_locked_site: true,
        candidate_count: candidateCount,
        sources_requested: [
          "parcels",
          "buildings",
          "roads",
          "floodplain",
          "wetlands",
          "utilities",
          "contours",
          "elevation",
          "grading_context",
        ],
        missing_sources: missing,
        grading_context: slopeEstimateOverride
          ? {
              source: "explicit_assumed_slope",
              slope_percent: slopePct,
              review_required: true,
              survey_backed: false,
            }
          : {
              source: hasTerrainSource ? "survey_or_terrain_source" : "missing",
              review_required: true,
              survey_backed: hasVerifiedSurveyControl,
            },
        review_required: true,
        construction_release_allowed: false,
        truth_label:
          "Automatic existing-condition detection creates review-required candidates only; it is not survey/control or final professional evidence.",
      };
      const nextSiteInputs: SiteInputs = {
        ...currentSiteInputs,
        site_alignment_locked: true,
        site_boundary_state: "locked_canonical",
        online_existing_conditions_discovery_v1: discovery ?? currentSiteInputs.online_existing_conditions_discovery_v1,
        map_feature_detection_report_v1:
          onlineFetch?.map_feature_detection_report_v1 ?? currentSiteInputs.map_feature_detection_report_v1,
        existing_conditions_package:
          onlineFetch?.existing_conditions_package ?? currentSiteInputs.existing_conditions_package,
        auto_existing_conditions_v1: autoExistingConditions,
        ...(slopeEstimateOverride
          ? {
              assumed_terrain_slope_pct: slopePct,
              slope_estimate: slopeEstimateOverride,
              use_survey_for_grading: false,
            }
          : {}),
      };
      if (discovery?.local_gis_provider_registry_v1) {
        nextSiteInputs.local_gis_provider_registry_v1 = discovery.local_gis_provider_registry_v1;
      }
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: nextSiteInputs,
        },
      };
      const latestResultOverride =
        currentProject?.latest_result?.final_plan
          ? {
              ...currentProject.latest_result,
              final_plan: {
                ...currentProject.latest_result.final_plan,
                meta: {
                  ...(currentProject.latest_result.final_plan.meta ?? {}),
                  online_existing_conditions_discovery_v1: discovery,
                  map_feature_detection_report_v1: onlineFetch?.map_feature_detection_report_v1,
                  existing_conditions_package: onlineFetch?.existing_conditions_package,
                  existing_conditions_summary: onlineFetch?.existing_conditions_summary,
                  auto_existing_conditions_v1: autoExistingConditions,
                },
              },
            }
          : undefined;

      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              latest_result: latestResultOverride ?? project.latest_result,
              has_result: latestResultOverride ? true : project.has_result,
              updated_at: Date.now() / 1000,
            }
          : project,
      );
      await saveProject({
        silent: true,
        projectInputOverride: nextProjectInput,
        latestResultOverride,
      });
      setAutoExistingConditionsStatus({
        status: providerFailed || providersAbsent ? "blocked" : candidateCount > 0 || slopeEstimateOverride || hasTerrainSource ? "ready" : "blocked",
        message:
          providerFailed
            ? `Source provider lookup failed: ${(discovery?.blockers ?? [])[0] || "the backend/provider did not return source candidates"}. Retry source discovery after the provider responds.`
            : providersAbsent
              ? "No source providers are configured. Add GIS providers or upload survey/topo evidence before relying on source context."
              : candidateCount > 0
            ? `Found ${candidateCount} source candidate${candidateCount === 1 ? "" : "s"} inside/near the locked site for review.`
            : slopeEstimateOverride
              ? `No source candidates were found yet. Grading has an explicit ${slopePct}% assumed slope for review only.`
              : "Configured providers returned no usable features inside/near the locked site.",
        candidateCount,
        missing: providersAbsent ? ["source providers"] : providerFailed ? ["provider lookup"] : missing,
      });
      updateProjectStatus({
        state: providerFailed || providersAbsent ? "blocked" : "needs review",
        area: "setup",
        title: providerFailed
          ? "Site context needs provider"
          : providersAbsent
            ? "Site context needs sources"
            : "Site context needs review",
        detail:
          providerFailed
            ? "Existing-condition source lookup failed; retry after providers/backend respond."
            : providersAbsent
              ? "No source providers are configured yet."
              : candidateCount > 0
                ? `Found ${candidateCount} existing-condition candidate${candidateCount === 1 ? "" : "s"} for review inside the site.`
                : slopeEstimateOverride
                  ? `No source candidates found yet; grading is using an explicit ${slopePct}% assumed slope for review only.`
                  : "Existing-condition providers returned no usable features inside the site.",
        nextAction:
          providerFailed
            ? "Retry source discovery after providers/backend respond."
            : providersAbsent
              ? "Add GIS providers or upload survey/topo evidence before relying on source context."
              : "Review source candidates and assumptions before generating.",
      });
        if (slopeEstimateOverride || hasTerrainSource) {
          void handleGenerateSystemRef.current?.("grading", { slopeEstimateOverride });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Automatic existing-condition discovery could not finish.";
        setAutoExistingConditionsStatus({
          status: "blocked",
          message,
          candidateCount: 0,
          missing: ["automatic source discovery"],
        });
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Site context needs attention",
          detail: message,
          nextAction: "Check backend/provider connectivity, then recheck sources inside the site.",
        });
      } finally {
        setOnlineDiscoveryBusy(false);
      }
    },
    [
      assumedTerrainSlopePct,
      buildingPlacements,
      configuredLocalGisProviders.length,
      currentProject,
      hasTerrainSource,
      hasVerifiedSurveyControl,
      lotHeight,
      lotWidth,
      payloadPreview,
      projectId,
      saveProject,
      siteAddress,
      siteInputs,
      surveySlopeEstimate?.slope_percent,
      token,
      updateProjectStatus,
      viewportCenter,
      viewportFootprint,
    ],
  );

  const handleApplySite = useCallback(async () => {
    if (applyingSiteRef.current) return;
    if (siteScaleLocked) {
      if (hasSiteBoundary()) {
        updateProjectStatus({
          state: "ready",
          area: "setup",
          title: "Site already locked",
          detail: "Site boundary is already locked.",
          nextAction: "Open Generate when you are ready to create review drafts.",
        });
        return;
      }
      setSiteScaleLocked(false);
    }
    applyingSiteRef.current = true;
    const currentInput = currentProject?.project_input ?? payloadPreview;
    const visibleWidth = parsePositiveNumber(lotWidth);
    const visibleHeight = parsePositiveNumber(lotHeight);
    const width = visibleWidth ?? viewportFootprint?.widthFt;
    const height = visibleHeight ?? viewportFootprint?.heightFt;
    if (!width || !height) {
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Apply site needs size",
        detail: "Set the site width and height before applying the site.",
        nextAction: "Type width/depth or draw a site boundary, then lock the site.",
      });
      applyingSiteRef.current = false;
      return;
    }
    const selectedAreaAcres = siteAreaAcresFromSize(width, height);
    if (selectedAreaAcres > SITE_WARNING_ACRES) {
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Apply site needs smaller area",
        detail: OVERSIZED_SITE_MESSAGE,
        nextAction: "Reduce the site area or zoom to a smaller review boundary.",
      });
      applyingSiteRef.current = false;
      return;
    }
    updateProjectStatus({
      state: "working",
      area: "setup",
      title: "Applying site",
      detail: "Civora is locking the site boundary and preparing site context checks.",
      nextAction: "Wait for the boundary to lock, then review source context results.",
    });
    const existingSite = buildingPlacements.find((item) => item.type === "site");
    if (existingSite && !existingSite.locked) {
      const existingBoundarySource =
        currentInput?.meta?.site_inputs?.site_boundary_source ?? existingSite.source;
      const normalizedBoundarySource: SiteInputs["site_boundary_source"] =
        existingBoundarySource === "manual_drawn" ||
        existingBoundarySource === "map_viewport" ||
        existingBoundarySource === "imported"
          ? existingBoundarySource
          : "dimensions";
      const nextSiteInputs: SiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        site_alignment_locked: true,
        site_boundary_state: "locked_canonical",
        site_boundary_source: normalizedBoundarySource,
      };
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: nextSiteInputs,
        },
        manual_fields: {
          ...(currentInput?.manual_fields ?? {}),
          lot: {
            x: existingSite.x ?? 0,
            y: existingSite.y ?? 0,
            w: width,
            h: height,
          },
        },
      };
      setSiteScaleLocked(true);
      setShowSiteBounds(false);
      setSiteSelectionMode(false);
      setActiveWorkspaceMode("canvas");
      setActiveSidePanel(null);
      setRenderedSidePanel(null);
      setSidePanelVisible(false);
      setFitToSiteRequest((value) => value + 1);
      setBuildingPlacements((prevPlacements) =>
        prevPlacements.map((item) =>
          item.type === "site"
            ? {
                ...item,
                locked: true,
                meta: {
                  ...(item.meta ?? {}),
                  site_boundary_state: "locked_canonical",
                  engineering_status: "review_required",
                  construction_release_allowed: false,
                },
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
      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              has_result: false,
              latest_result: undefined,
            }
          : project,
      );
      await saveProject({
        silent: true,
        projectInputOverride: nextProjectInput,
      });
      lastAppliedSiteRef.current = {
        w: width,
        h: height,
        lat: viewportCenter?.lat,
        lng: viewportCenter?.lng,
      };
      applyingSiteRef.current = false;
      updateProjectStatus({
        state: "working",
        area: "setup",
        title: "Detecting site context",
        detail: "Site boundary locked. Checking available existing-condition sources inside the site.",
        nextAction: "Review found candidates or needs before generating.",
      });
      void runAutoExistingConditionsAfterSiteLock(nextProjectInput);
      return;
    }
    const lastApplied = lastAppliedSiteRef.current;
    if (
      lastApplied &&
      Math.abs(lastApplied.w - width) < 1 &&
      Math.abs(lastApplied.h - height) < 1 &&
      (!viewportCenter ||
        (Math.abs((lastApplied.lat ?? 0) - viewportCenter.lat) < 1e-6 &&
          Math.abs((lastApplied.lng ?? 0) - viewportCenter.lng) < 1e-6))
    ) {
      updateProjectStatus({
        state: "ready",
        area: "setup",
        title: "Site already applied",
        detail: "Site already matches the current viewport.",
        nextAction: "Open Generate when you are ready to create review drafts.",
      });
      applyingSiteRef.current = false;
      return;
    }
    autoFitSite(width, height, "Site Boundary", undefined, false, true);
    setShowSiteBounds(false);
    setSiteScaleLocked(true);
    const nextSiteInputs = {
      ...(currentInput?.meta?.site_inputs ?? {}),
      site_alignment_locked: true,
      ...(viewportFootprint?.bounds
        ? {
            viewport_bounds: {
              north: viewportFootprint.bounds.north,
              south: viewportFootprint.bounds.south,
              east: viewportFootprint.bounds.east,
              west: viewportFootprint.bounds.west,
              center_lat: viewportFootprint.bounds.centerLat,
              center_lng: viewportFootprint.bounds.centerLng,
              width_ft: width,
              height_ft: height,
            },
          }
        : {}),
      ...(viewportCenter
        ? {
            geocode: {
              ...(currentInput?.meta?.site_inputs?.geocode ?? {}),
              lat: viewportCenter.lat,
              lng: viewportCenter.lng,
              display_name:
                currentInput?.meta?.site_inputs?.geocode?.display_name ?? "Map center",
            },
          }
        : {}),
    };
    await saveProject({
      silent: true,
      projectInputOverride: {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: nextSiteInputs,
        },
        manual_fields: {
          ...(currentInput?.manual_fields ?? {}),
          lot: {
            x: 0,
            y: 0,
            w: width,
            h: height,
          },
        },
      },
    });
    setSiteSelectionMode(false);
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setLeftSidebarOpen(false);
    }
    updateProjectStatus({
      state: "working",
      area: "setup",
      title: "Detecting site context",
      detail: "Site applied and locked. Civora is checking source context inside the site.",
      nextAction: "Review found candidates or needs before generating.",
    });
    lastAppliedSiteRef.current = {
      w: width,
      h: height,
      lat: viewportCenter?.lat,
      lng: viewportCenter?.lng,
    };
    applyingSiteRef.current = false;
    void runAutoExistingConditionsAfterSiteLock({
      ...currentInput,
      input_mode: "user",
      strict_mode: false,
      allow_ai_fill_for_blanks: false,
      meta: {
        ...(currentInput?.meta ?? {}),
        site_inputs: nextSiteInputs,
      },
      manual_fields: {
        ...(currentInput?.manual_fields ?? {}),
        lot: {
          x: 0,
          y: 0,
          w: width,
          h: height,
        },
      },
    });
  }, [
    autoFitSite,
    buildingPlacements,
    currentProject,
    lotHeight,
    lotWidth,
    payloadPreview,
    runAutoExistingConditionsAfterSiteLock,
    saveProject,
    updateProjectStatus,
    viewportCenter,
    viewportFootprint,
  ]);

  const runSelectedDetections = useCallback(async () => {
    if (!siteScaleLocked) {
      setStatusMessage("Lock the site first, then Civora can detect or draft inside that boundary.");
      return;
    }
    const wantsContext = detectionChoices.roads || detectionChoices.buildings || detectionChoices.parking;
    let ranSomething = false;
    if (wantsContext) {
      if (!mapSnapshotPath) {
        setStatusMessage("Map/image detection needs a map snapshot. Grading can still run from survey, terrain, or an explicit assumed slope.");
      } else {
        await handleAnalyzeImageFeatures();
        ranSomething = true;
      }
    }
    if (detectionChoices.grading) {
      let slopeEstimateOverride: SurveySlopeResponse | null = null;
      if (!hasTerrainSource && !surveySlopeEstimate?.slope_percent) {
        const slopePct = parsePositiveNumber(assumedTerrainSlopePct) ?? 8;
        slopeEstimateOverride = buildAssumedSlopeEstimate(slopePct);
        setAssumedTerrainSlopePct(String(slopePct));
        setUseSurveyForGrading(false);
        setSurveySlopeEstimate(slopeEstimateOverride);
        setStatusMessage(`No survey/terrain source is attached, so Civora is using an explicit ${slopePct}% assumed slope for this review draft.`);
      }
      await handleGenerateSystemRef.current?.("grading", { slopeEstimateOverride });
      ranSomething = true;
    }
    if (!ranSomething && !wantsContext && !detectionChoices.grading) {
      setStatusMessage("Select at least one detection option.");
    }
  }, [
    assumedTerrainSlopePct,
    detectionChoices,
    handleAnalyzeImageFeatures,
    hasTerrainSource,
    mapSnapshotPath,
    siteScaleLocked,
    surveySlopeEstimate?.slope_percent,
  ]);

  useEffect(() => {
    if (!siteScaleLocked) return;
    const hasSite = buildingPlacements.some((item) => item.type === "site");
    if (!hasSite) return;
    setFitToSiteRequest((value) => value + 1);
  }, [activeSidePanel, buildingPlacements, previewHeightPx, siteScaleLocked]);

  const saveSiteAddress = async (
    addressOverride?: string,
    options?: { preserveLockedSite?: boolean; siteWidth?: number; siteHeight?: number },
  ) => {
    const trimmed = (addressOverride ?? siteAddress).trim();
    const preserveLockedSite = Boolean(options?.preserveLockedSite);
    const overrideSiteWidth = options?.siteWidth;
    const overrideSiteHeight = options?.siteHeight;
    if (!token) {
      if (!trimmed) {
        const message = "Type a project address before applying.";
        setAutoExistingConditionsStatus({
          status: "waiting",
          message,
          candidateCount: 0,
          missing: ["address"],
        });
        updateProjectStatus({
          state: "needs review",
          area: "setup",
          title: "Address needed",
          detail: message,
          nextAction: "Type an address in Setup, or lock a manually drawn site boundary.",
        });
        return;
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        address: trimmed,
      };
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        manual_fields:
          preserveLockedSite && overrideSiteWidth && overrideSiteHeight
            ? {
                ...(currentInput?.manual_fields ?? {}),
                lot: { x: 0, y: 0, w: overrideSiteWidth, h: overrideSiteHeight },
              }
            : currentInput?.manual_fields,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: nextSiteInputs,
        },
      };
      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              updated_at: Date.now() / 1000,
            }
          : project,
      );
      setSelectedAddressSuggestion(null);
      setAddressSuggestions([]);
      autoExistingRunKeyRef.current = "";
      setActiveWorkspaceMode("setup");
      setActiveSidePanel("site_existing");
      const message = "Sign in/connect backend to apply address. Address saved locally; online geocode/source lookup needs sign-in/backend connection.";
      setAutoExistingConditionsStatus({
        status: "blocked",
        message,
        candidateCount: 0,
        missing: ["backend session", "geocode", "source providers"],
      });
      updateProjectStatus({
        state: "needs review",
        area: "setup",
        title: "Address applied locally",
        detail: message,
        nextAction: "Lock the site boundary for layout, or sign in/connect backend to geocode and fetch source context.",
      });
      return;
    }
    const currentInput = currentProject?.project_input ?? payloadPreview;
    const nextSiteInputs = {
      ...(currentInput?.meta?.site_inputs ?? {}),
      address: trimmed || undefined,
    };
    if (!trimmed) {
      setSelectedAddressSuggestion(null);
      setAddressSuggestions([]);
      autoExistingRunKeyRef.current = "";
      setAutoExistingConditionsStatus({
        status: "waiting",
        message: "Apply an address and lock the site. Civora will then check available source context inside the boundary.",
        candidateCount: 0,
        missing: [],
      });
      await saveProject({
        silent: true,
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
      updateProjectStatus({
        state: "needs review",
        area: "setup",
        title: "Address cleared",
        detail: "Site address cleared.",
        nextAction: "Apply a new address or lock a manually drawn site boundary.",
      });
      return;
    }
    try {
      setOnlineDiscoveryBusy(true);
      updateProjectStatus({
        state: "working",
        area: "setup",
        title: "Applying address",
        detail: "Civora is geocoding the address and checking available source context.",
        nextAction: "Wait for source candidates or an exact provider/auth blocker.",
      });
      let geocode = selectedAddressSuggestion;
      if (!hasAddressCoordinates(geocode)) {
        geocode = await postJson<AddressSuggestion>("/api/geocode", { address: trimmed }, { token });
      }
      if (!hasAddressCoordinates(geocode)) {
        const geocodeMessage =
          geocode?.message ||
          geocode?.blockers?.find((item) => item?.message)?.message ||
          "Address lookup did not return usable map coordinates.";
        setAutoExistingConditionsStatus({
          status: "blocked",
          message: `Geocode failed: ${geocodeMessage} Check the address or place the site manually.`,
          candidateCount: 0,
          missing: ["geocode"],
        });
        updateProjectStatus({
          state: "blocked",
          area: "setup",
          title: "Apply address needs correction",
          detail: `${geocodeMessage} The map was not moved.`,
          nextAction: "Check the address, or set site size/draw the boundary manually.",
        });
        return;
      }
      clearGeneratedPreview();
      nextSiteInputs.address = trimmed;
      nextSiteInputs.geocode = {
        lat: geocode.lat,
        lng: geocode.lng,
        display_name: geocode.display_name,
        provider: geocode.provider ?? "nominatim",
        confidence: geocode.confidence ?? null,
        crs: geocode.crs ?? { epsg: "EPSG:4326", units: "degrees" },
        location_context: geocode.location_context ?? undefined,
      };
      nextSiteInputs.location_context =
        geocode.location_context ?? {
          address: geocode.display_name,
          normalized_address: geocode.display_name,
          coordinates: { lat: geocode.lat, lng: geocode.lng },
          crs: geocode.crs ?? { epsg: "EPSG:4326", units: "degrees" },
          evidence_source: geocode.provider ?? "geocoder",
          truth_label:
            "Address/geocode is location context only; it is not a site boundary, survey, control, or final reliance source.",
        };
      const activeViewportBounds = (nextSiteInputs.viewport_bounds ?? {}) as {
        west?: number;
        south?: number;
        east?: number;
        north?: number;
      };
      const activeSiteBoundary =
        Number.isFinite(Number(activeViewportBounds.west)) &&
        Number.isFinite(Number(activeViewportBounds.south)) &&
        Number.isFinite(Number(activeViewportBounds.east)) &&
        Number.isFinite(Number(activeViewportBounds.north))
          ? {
              west: Number(activeViewportBounds.west),
              south: Number(activeViewportBounds.south),
              east: Number(activeViewportBounds.east),
              north: Number(activeViewportBounds.north),
            }
          : undefined;
      let onlineFetch: OnlineExistingConditionsFetchResponse | null = null;
      try {
        onlineFetch = await postJson<OnlineExistingConditionsFetchResponse>(
          "/api/existing-conditions/fetch-online",
          {
            address: geocode.display_name,
            bbox: activeSiteBoundary,
            active_site_boundary: activeSiteBoundary ?? {},
            include_floodplain: true,
            include_wetlands: true,
            include_parcels: true,
            include_building_footprints: true,
            include_roads: true,
            include_utilities: true,
            include_contours: true,
            include_elevation: true,
            provider_registry: localGisProviderRegistry,
          },
          { token },
        );
      } catch (error) {
        onlineFetch = {
          success: false,
          status: "fetch_failed",
          online_existing_conditions_discovery_v1: {
            version: "online_existing_conditions_discovery_v1",
            status: "fetch_failed",
            candidate_count: 0,
            sources: [],
            blockers: [error instanceof Error ? error.message : "Online existing-condition discovery failed."],
            review_required: true,
            acceptance_status: "missing",
            truth_label:
              "Online existing-condition discovery failed; no online source candidate is treated as accepted project evidence.",
          },
        };
      }
      if (onlineFetch?.online_existing_conditions_discovery_v1) {
        nextSiteInputs.online_existing_conditions_discovery_v1 = onlineFetch.online_existing_conditions_discovery_v1;
        if (onlineFetch.online_existing_conditions_discovery_v1.local_gis_provider_registry_v1) {
          nextSiteInputs.local_gis_provider_registry_v1 = onlineFetch.online_existing_conditions_discovery_v1.local_gis_provider_registry_v1;
        }
      }
      if (onlineFetch?.map_feature_detection_report_v1) {
        nextSiteInputs.map_feature_detection_report_v1 = onlineFetch.map_feature_detection_report_v1;
      }
      if (onlineFetch?.existing_conditions_package) {
        nextSiteInputs.existing_conditions_package = onlineFetch.existing_conditions_package;
      }
      nextSiteInputs.site_alignment_locked = preserveLockedSite ? true : false;
      if (preserveLockedSite) {
        nextSiteInputs.site_boundary_state = "locked_canonical";
        nextSiteInputs.site_boundary_source = "dimensions";
      }
      setAddressSuggestions([]);
      setActiveWorkspaceMode("setup");
      setActiveSidePanel("site_existing");
      const latestResultOverride =
        currentProject?.latest_result?.final_plan
          ? {
              ...currentProject.latest_result,
              final_plan: {
                ...currentProject.latest_result.final_plan,
                meta: {
                  ...(currentProject.latest_result.final_plan.meta ?? {}),
                  location_context: nextSiteInputs.location_context,
                  online_existing_conditions_discovery_v1: onlineFetch?.online_existing_conditions_discovery_v1,
                  map_feature_detection_report_v1: onlineFetch?.map_feature_detection_report_v1,
                  existing_conditions_package: onlineFetch?.existing_conditions_package,
                  existing_conditions_summary: onlineFetch?.existing_conditions_summary,
                },
              },
            }
          : undefined;
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: "user",
        strict_mode: false,
        allow_ai_fill_for_blanks: false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: nextSiteInputs,
        },
        manual_fields:
          preserveLockedSite && overrideSiteWidth && overrideSiteHeight
            ? {
                ...(currentInput?.manual_fields ?? {}),
                lot: { x: 0, y: 0, w: overrideSiteWidth, h: overrideSiteHeight },
              }
            : currentInput?.manual_fields,
      };
      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              latest_result: latestResultOverride ?? project.latest_result,
              has_result: latestResultOverride ? true : project.has_result,
              updated_at: Date.now() / 1000,
            }
          : project,
      );
      await saveProject({
        silent: true,
        projectInputOverride: nextProjectInput,
        latestResultOverride,
      });
      if (preserveLockedSite) {
        setSiteScaleLocked(true);
        setShowSiteBounds(false);
        setSiteSelectionMode(false);
        setBuildingPlacements((prevPlacements) =>
          prevPlacements.map((item) =>
            item.type === "site"
              ? {
                  ...item,
                  locked: true,
                  capabilities: {
                    ...(item.capabilities ?? {}),
                    movable: false,
                    resizable: false,
                    rotatable: false,
                    deletable: false,
                  },
                  meta: {
                    ...(item.meta ?? {}),
                    site_boundary_state: "locked_canonical",
                    source_ui_mode: item.meta?.source_ui_mode ?? "site_setup",
                  },
                }
              : item,
          ),
        );
      } else {
        setSiteScaleLocked(false);
      }
      setSiteAddress(trimmed);
      setShowSiteBounds(preserveLockedSite ? false : true);
      setPreviewQuality("high");
      setSiteSelectionMode(preserveLockedSite ? false : true);
      setViewportCenter({ lat: geocode.lat, lng: geocode.lng });
      autoExistingRunKeyRef.current = "";
      const candidateCount = Number(onlineFetch?.online_existing_conditions_discovery_v1?.candidate_count ?? 0);
      const discoveryStatus = String(onlineFetch?.online_existing_conditions_discovery_v1?.status || onlineFetch?.status || "");
      const providerSources = onlineFetch?.online_existing_conditions_discovery_v1?.sources ?? [];
      const lookupUnavailable =
        candidateCount === 0 &&
        (discoveryStatus.includes("failed") ||
          (!configuredLocalGisProviders.length && !providerSources.length));
      const providerAbsent =
        candidateCount === 0 &&
        !discoveryStatus.includes("failed") &&
        !configuredLocalGisProviders.length &&
        !providerSources.length;
      updateProjectStatus({
        state: lookupUnavailable ? "blocked" : candidateCount > 0 ? "needs review" : "ready",
        area: "setup",
        title: lookupUnavailable
          ? "Address applied, source lookup needs attention"
          : candidateCount > 0
            ? "Address applied, sources need review"
            : "Address applied",
        detail:
          candidateCount > 0
            ? `Found ${candidateCount} online source candidate${candidateCount === 1 ? "" : "s"} for review.`
            : lookupUnavailable
              ? providerAbsent
                ? "Address applied; no online/local source providers are configured yet."
                : "Address applied; online source lookup failed or providers were unavailable."
              : "Online source discovery found no usable candidates yet; missing providers are listed in setup.",
        nextAction: lookupUnavailable
          ? "Add GIS providers or upload survey/topo evidence before relying on source context."
          : preserveLockedSite || siteScaleLocked
            ? "Review source candidates, then generate review drafts when ready."
            : "Lock the site boundary to check sources inside the site.",
      });
      setAutoExistingConditionsStatus({
        status: lookupUnavailable ? "blocked" : preserveLockedSite || siteScaleLocked ? "running" : "waiting",
        message: lookupUnavailable
          ? providerAbsent
            ? "Address applied, but no source providers are configured. Add GIS providers or upload survey/topo evidence before relying on source context."
            : "Address applied, but provider lookup failed or was unavailable. Retry after the backend/providers respond."
          : preserveLockedSite || siteScaleLocked
          ? "Address changed. Civora will recheck sources inside the locked site."
          : "Address applied. Lock the site boundary to auto-check roads, buildings, terrain, constraints, and utilities inside it.",
        candidateCount,
        missing: lookupUnavailable ? (providerAbsent ? ["source providers"] : ["provider lookup"]) : [],
      });
      setSelectedAddressSuggestion(geocode);
      if (preserveLockedSite || siteScaleLocked) {
        void runAutoExistingConditionsAfterSiteLock(nextProjectInput);
      }
    } catch (error) {
      const message = `Geocode failed: ${panelErrorMessage(error, "Check the address or retry after the backend responds.")}`;
      setAutoExistingConditionsStatus({
        status: "blocked",
        message,
        candidateCount: 0,
        missing: ["geocode"],
      });
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Apply address needs attention",
        detail: message,
        nextAction: "Check the address or retry after the backend responds.",
      });
    } finally {
      setOnlineDiscoveryBusy(false);
    }
  };

  const handleCreateCenteredSiteFromSetup = useCallback(async () => {
    const address = siteAddress.trim();
    const width = parsePositiveNumber(lotWidth) ?? 1000;
    const height = parsePositiveNumber(lotHeight) ?? 1000;
    if (!address) {
      updateProjectStatus({
        state: "needs review",
        area: "setup",
        title: "Address needed",
        detail: "Type the site address first.",
        nextAction: "Enter an address, then create the centered site.",
      });
      siteAddressInputRef.current?.focus();
      return;
    }
    setLotWidth(String(Math.round(width)));
    setLotHeight(String(Math.round(height)));
    clearGeneratedPreview();
    autoFitSite(width, height, "Site Boundary", undefined, true, true, true);
    setShowSiteBounds(false);
    setSiteSelectionMode(false);
    setPreviewMode("2d");
    setPreviewQuality("high");
    setPreviewInteraction("static");
    setActiveWorkspaceMode("canvas");
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    setRightRailCollapsed(true);
    setFitToSiteRequest((value) => value + 1);
    updateProjectStatus({
      state: "working",
      area: "setup",
      title: "Creating centered site",
      detail: `${address} is being applied with a ${Math.round(width)} ft by ${Math.round(height)} ft site box centered on the address.`,
      nextAction: "Review the detected source context, then draw or generate inside the locked site.",
    });
    setAutoExistingConditionsStatus({
      status: "running",
      message: `Creating a ${Math.round(width)} ft by ${Math.round(height)} ft site centered on ${address}, then checking available source context.`,
      candidateCount: 0,
      missing: [],
    });
    lastAppliedSiteRef.current = {
      w: width,
      h: height,
      lat: viewportCenter?.lat,
      lng: viewportCenter?.lng,
    };
    await saveSiteAddress(address, {
      preserveLockedSite: true,
      siteWidth: width,
      siteHeight: height,
    });
  }, [
    autoFitSite,
    clearGeneratedPreview,
    lotHeight,
    lotWidth,
    saveSiteAddress,
    siteAddress,
    updateProjectStatus,
    viewportCenter?.lat,
    viewportCenter?.lng,
  ]);

  const handleMapCenter = useCallback(
    async (payload: { lat: number; lng: number }) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        geocode: {
          ...(currentInput?.meta?.site_inputs?.geocode ?? {}),
          lat: payload.lat,
          lng: payload.lng,
          display_name: currentInput?.meta?.site_inputs?.geocode?.display_name ?? "Map center",
        },
      };
      await saveProject({
        silent: true,
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
      setFitToSiteRequest((value) => value + 1);
      setStatusMessage("Site centered on the map view.");
    },
    [currentProject, payloadPreview, saveProject],
  );

  const requestPreview = async (
    payload: PreviewRequestPayload,
    options?: { silent?: boolean; track?: boolean },
  ) => {
    if (!token) return;
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
      setPlanPreviewUrl(data.preview_image_data_url);
      setPlanPreviewProjectId(projectId || currentProject?.project_id || null);
      setPlanPreviewSummary(data.summary ?? null);
      setPlanPreviewAnnotations(data.preview_annotations ?? null);
      if (!options?.silent) {
        setStatusMessage("Plan preview generated.");
      }
    } finally {
      if (options?.track) {
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

  const loadProjectResultInBackground = (project: ProjectRecord) => {
    if (!token) return;
    const requestId = projectResultLoadRequestRef.current + 1;
    projectResultLoadRequestRef.current = requestId;
    void getJson<{ project_id: string; latest_result: PlanResponse }>(
      `/api/projects/${project.project_id}/result`,
      { token },
    )
      .then((data) => {
        if (projectResultLoadRequestRef.current !== requestId) {
          return;
        }
        const latestResult = data.latest_result ?? {};
        if (latestResult && Object.keys(latestResult).length) {
          const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
          const hasStaleSystems = Object.values(systemStatuses).some(
            (status) => status === "stale",
          );
          const shouldSuppressLatestResult =
            hasStaleSystems &&
            activeStatus !== "running" &&
            activeStatus !== "queued" &&
            activeStatus !== "awaiting_approval";
          if (shouldSuppressLatestResult) {
            return;
          }
          applyBackendResult(latestResult);
          requestPreviewInBackground(
            {
              project_id: project.project_id,
              result: latestResult,
              filename_stem: fileName || project.name || "civora-ai-plan",
            },
            {
              silentStatus: true,
            },
          );
        } else {
          const activeProjectForPreview =
            visibleActiveJob?.project_id ||
            resolvedProjectIdRef.current ||
            projectId ||
            currentProject?.project_id ||
            "";
          if (activeProjectForPreview && activeProjectForPreview !== project.project_id) {
            return;
          }
          const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
          const shouldPreserveCurrentPreview =
            project.project_id &&
            activeProjectForPreview === project.project_id &&
            (activeStatus === "running" ||
              activeStatus === "queued" ||
              activeStatus === "awaiting_approval");
          if (shouldPreserveCurrentPreview && (planPreviewUrl || backendResult)) {
            return;
          }
          setBackendResult(null);
          setPlanPreviewUrl("");
          setPlanPreviewSummary(null);
        }
      })
      .catch((error) => {
        setStatusMessage(
          error instanceof Error ? error.message : "Project result load failed.",
        );
      });
  };

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

  const drainageIssueApplyLabel = useCallback(
    (issue: Issue) => {
      const code = (issue.code ?? "").toUpperCase();
      if (code === "NO_PONDS_DEFINED" || code === "NO_VALID_OUTFALL" || code === "DRAINAGE_NO_BASIN") {
        return "Add basin";
      }
      if (code === "BASIN_UNREACHABLE") return "Add basin";
      if (code === "POOR_SLOPE") return "Adjust slope";
      if (code === "ORPHAN_INLETS") return "Connect inlet";
      if (code === "UNDER_COLLECTION") return "Add inlet";
      if (code === "UNDER_COLLECTION_REDUCED") return "Add inlet";
      return null;
    },
    [],
  );

  const getIssueGuidance = useCallback((issue: Issue) => {
    const code = (issue.code ?? "").toUpperCase();
    const rawContext = issue.context;
    const context =
      rawContext && typeof rawContext === "object"
        ? (rawContext as Record<string, unknown>)
        : null;
    const explanation =
      context && typeof context.explanation === "string"
        ? String(context.explanation)
        : null;
    const bestNextFix =
      context && typeof context.best_next_fix === "string"
        ? String(context.best_next_fix)
        : null;
    const suggested =
      context && Array.isArray(context.suggested_actions)
        ? context.suggested_actions
            .filter((item) => typeof item === "string")
            .map((item) => String(item))
        : null;
    if (explanation || bestNextFix || (suggested && suggested.length)) {
      return { explanation, bestNextFix, suggested };
    }
    const fallback: Record<string, { explanation: string; suggested: string[]; bestNextFix: string }> = {
      BASIN_UNREACHABLE: {
        explanation: "Flow cannot reach the basin from current low points.",
        suggested: [
          "Move the basin to a lower point.",
          "Add an inlet near the low point.",
          "Adjust grading to direct flow toward the basin.",
        ],
        bestNextFix: "Move the basin to a lower point.",
      },
      DRAINAGE_NO_BASIN: {
        explanation: "No valid basin or outfall was provided for drainage.",
        suggested: [
          "Add a basin at a low point.",
          "Define an outfall location.",
          "Connect to an existing downstream system.",
        ],
        bestNextFix: "Add a basin at a low point.",
      },
      NO_VALID_OUTFALL: {
        explanation: "No valid outlet was found for drainage discharge.",
        suggested: [
          "Add a basin at a low point.",
          "Define an outfall location.",
          "Connect to an existing downstream system.",
        ],
        bestNextFix: "Add a basin at a low point.",
      },
      NO_PONDS_DEFINED: {
        explanation: "No basin/pond target is defined for drainage.",
        suggested: [
          "Add a basin at a low point.",
          "Define an outfall location.",
          "Connect to an existing downstream system.",
        ],
        bestNextFix: "Add a basin at a low point.",
      },
      POOR_SLOPE: {
        explanation: "Terrain is too flat for the minimum pipe slope.",
        suggested: [
          "Modify grading to introduce slope.",
          "Relocate inlets or basin to a steeper area.",
          "Increase slope in this region.",
        ],
        bestNextFix: "Modify grading to introduce slope.",
      },
      SLOPE_ADJUSTMENT_FAILED: {
        explanation: "Slope adjustment is not feasible with the current geometry.",
        suggested: [
          "Modify grading to introduce slope.",
          "Relocate inlets or basin to a steeper area.",
          "Increase slope in this region.",
        ],
        bestNextFix: "Modify grading to introduce slope.",
      },
      ORPHAN_INLETS: {
        explanation: "One or more inlets are not connected to a drainage run.",
        suggested: [
          "Connect the inlet to the nearest run.",
          "Reroute the pipe network to include the inlet.",
        ],
        bestNextFix: "Connect the inlet to the nearest run.",
      },
      UNDER_COLLECTION: {
        explanation: "There are not enough inlets to collect runoff.",
        suggested: ["Add inlets along pavement edges."],
        bestNextFix: "Add inlets along pavement edges.",
      },
      UNDER_COLLECTION_REDUCED: {
        explanation: "Inlet coverage improved, but runoff is still under-collected.",
        suggested: ["Add inlets along pavement edges."],
        bestNextFix: "Add inlets along pavement edges.",
      },
    };
    const fallbackGuidance = fallback[code];
    return fallbackGuidance
      ? fallbackGuidance
      : { explanation: null, bestNextFix: null, suggested: null };
  }, []);

  const canApplyDrainageIssue = useCallback(
    (issue: Issue) => {
      const code = (issue.code ?? "").toUpperCase();
      if (
        code === "UNDER_COLLECTION" ||
        code === "UNDER_COLLECTION_REDUCED" ||
        code === "BASIN_UNREACHABLE" ||
        code === "DRAINAGE_NO_BASIN" ||
        code === "NO_VALID_OUTFALL" ||
        code === "NO_PONDS_DEFINED"
      ) {
        return true;
      }
      if (code === "ORPHAN_INLETS" || code === "POOR_SLOPE") return true;
      return false;
    },
    [pickBestLowPoint],
  );

  const runDrainageAutofix = useCallback(
    async ({
      placementsOverride,
      forcedInlets,
      forcedBasins,
      connectOrphans,
      allowSlopeAdjust,
    }: {
      placementsOverride?: BuildingPlacement[];
      forcedInlets?: Array<Record<string, unknown>>;
      forcedBasins?: Array<Record<string, unknown>>;
      connectOrphans?: boolean;
      allowSlopeAdjust?: boolean;
    }): Promise<boolean> => {
      if (!ensureSiteLocked("drainage")) return false;
      const requestPayload = buildPayloadFromOverrides({}, undefined, projectId || null, placementsOverride);
      const omitField = { source: "omit", value: null } as const;
      const nextManualFields = {
        ...(requestPayload.manual_fields ?? {}),
      } as Record<string, unknown>;
      const rawDrainage = nextManualFields.drainage;
      const unwrappedDrainage =
        rawDrainage &&
        typeof rawDrainage === "object" &&
        "value" in (rawDrainage as Record<string, unknown>)
          ? ((rawDrainage as Record<string, unknown>).value ?? {})
          : rawDrainage ?? {};
      const nextDrainage = {
        ...(typeof unwrappedDrainage === "object" && unwrappedDrainage !== null ? unwrappedDrainage : {}),
      } as Record<string, unknown>;
      if (forcedInlets && forcedInlets.length) {
        nextDrainage.forced_inlets = forcedInlets;
      }
      if (forcedBasins) {
        if (forcedBasins.length) {
          nextManualFields.ponds = forcedBasins;
        }
        nextDrainage.autofix_action = "add_basin";
      }
      if (connectOrphans) {
        nextDrainage.connect_orphans = true;
      }
      if (allowSlopeAdjust) {
        nextDrainage.allow_slope_adjustment = true;
        nextDrainage.max_slope_adjust = drainageMaxSlopeAdjust;
        nextDrainage.autofix_action = "adjust_slope";
      }
      nextManualFields.drainage = nextDrainage;
      nextManualFields.utility_network = omitField;

      const drainagePayload: PlanRequestPayload = withReactiveRerunContext(
        {
          ...requestPayload,
          manual_fields: nextManualFields,
          meta: {
            ...(requestPayload.meta ?? {}),
            requested_system: "drainage",
          },
          prompt_text: null,
        },
        "drainage",
      );
      if (allowSlopeAdjust) {
        const existingDrainage = (requestPayload.drainage ?? {}) as Record<string, unknown>;
        (drainagePayload as Record<string, unknown>).drainage = {
          ...existingDrainage,
          allow_slope_adjustment: true,
          max_slope_adjust: drainageMaxSlopeAdjust,
          autofix_action: "adjust_slope",
        };
      }

      if (token && (projectId || currentProject?.project_id)) {
        const targetProjectId = projectId || currentProject?.project_id || null;
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/drainage",
            {
              project_id: targetProjectId,
              request: drainagePayload,
            },
            { token },
          );
          const jobId = queued.job.job_id;
          setActiveJobId(jobId);
          appendChatMessage(
            "assistant",
            `Queued drainage autofix as ${jobId}. Civora will show queued/running progress here and refresh the review state when it completes.`,
            "status",
          );
          setStatusMessage(`Drainage autofix queued as ${jobId}.`);
          return true;
        } catch (error) {
          const message = error instanceof Error ? error.message : "Drainage autofix failed.";
          appendChatMessage("assistant", message, "status");
          setStatusMessage(message);
          return false;
        }
      } else {
        await executePlanAction({
          mode: "run",
          requestPayload: drainagePayload,
          assistantPrefix: "Applying drainage fix…",
        });
      }
      setSystemStatuses((prev) => ({ ...prev, drainage: "fresh" }));
      return true;
    },
    [
      buildPayloadFromOverrides,
      drainageMaxSlopeAdjust,
      ensureSiteLocked,
      executePlanAction,
      token,
      projectId,
      currentProject?.project_id,
      currentProject?.name,
      siteName,
      loadProjectResultInBackground,
      appendChatMessage,
      setActiveJobId,
      setSystemStatuses,
      withReactiveRerunContext,
    ],
  );

  const persistFlowMetadata = useCallback(
    async (
      updates: Partial<{
        generate_flow_summary_v1: GenerateFlowSummary;
        review_package_flow_summary_v1: ReviewPackageFlowSummary;
      }>,
    ) => {
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const currentInputMode = currentInput?.input_mode === "assisted" ? "assisted" : "user";
      const nextProjectInput: ProjectInput = {
        ...currentInput,
        input_mode: currentInputMode,
        strict_mode: currentInput?.strict_mode ?? false,
        allow_ai_fill_for_blanks: currentInput?.allow_ai_fill_for_blanks ?? false,
        meta: {
          ...(currentInput?.meta ?? {}),
          site_inputs: {
            ...((currentInput?.meta?.site_inputs ?? {}) as SiteInputs),
            ...updates,
          },
        },
      };
      setCurrentProject((project) =>
        project
          ? {
              ...project,
              project_input: nextProjectInput,
              updated_at: Date.now() / 1000,
            }
          : project,
      );
      await saveProject({ silent: true, projectInputOverride: nextProjectInput });
    },
    [currentProject, payloadPreview, saveProject],
  );

  const handleGenerateSystem = useCallback(
    async (
      target: "roads" | "parking" | "grading" | "drainage" | "utilities" | "full",
      options?: { slopeEstimateOverride?: SurveySlopeResponse | null },
    ) => {
      const generateStartedAt = markCivoraInteraction();
      const preflightBlockers = getGeneratePreflightBlockers(target);
      const hardPreflightBlockers = preflightBlockers.filter((item) => isHardGenerateBlocker(item.label));
      const userLayoutContextSummary = currentGenerateLayoutContext;
      const reviewNotes = uniqueStrings([
        ...preflightBlockers.filter((item) => !isHardGenerateBlocker(item.label)).map((item) => item.label),
        userLayoutContextSummary
          ? `User layout context used by Generate: ${userLayoutContextSummary.labels.join(", ")}${userLayoutContextSummary.count > userLayoutContextSummary.labels.length ? `, plus ${userLayoutContextSummary.count - userLayoutContextSummary.labels.length} more` : ""}`
          : "",
        userLayoutContextSummary?.semantic_count ? `${userLayoutContextSummary.semantic_count} semantic drafted object${userLayoutContextSummary.semantic_count === 1 ? "" : "s"} included as review context` : "",
        pendingPlacementObjects.length
          ? `Requested objects still need placement before Generate can use them as layout context: ${pendingPlacementLabels.slice(0, 8).join(", ")}${pendingPlacementObjects.length > 8 ? `, plus ${pendingPlacementObjects.length - 8} more` : ""}`
          : "",
        ...autoSiteContextFlowSummary.missingLabels.map((item) => `Auto Site Context missing source: ${item}`),
        autoSiteContextFlowSummary.candidateCount > 0
          ? `Auto Site Context source candidates available for review: ${autoSiteContextFlowSummary.candidateLabels.join(", ") || `${autoSiteContextFlowSummary.candidateCount} candidate(s)`}`
          : "",
        hasAssumedTerrainSlope ? "review-only assumed terrain slope; survey/control still needed" : "",
      ]);
      const targetSystems =
        target === "full"
          ? (["roads", "parking", "grading", "drainage", "utilities"] as EngineeringSystemKey[])
          : ([target] as EngineeringSystemKey[]);
      const skippedSystems =
        target === "full"
          ? []
          : (["roads", "parking", "grading", "drainage", "utilities"] as EngineeringSystemKey[]).filter((system) => system !== target);
      const blockedSummary = (reason: string, nextAction: string): GenerateFlowSummary => ({
        version: "generate_flow_summary_v1",
        generated_at: new Date().toISOString(),
        target,
        ran: [],
        skipped: targetSystems,
        needs_review: uniqueStrings([reason, ...reviewNotes]),
        notes: reviewNotes,
        blocked: true,
        next_action: nextAction,
        auto_site_context: autoSiteContextFlowSummary,
        user_layout_context: userLayoutContextSummary,
        safety_wording:
          "Generate creates review-required drafts for qualified review.",
      });
      const recordGenerateSummary = (summary: GenerateFlowSummary) => {
        setGenerateFlowSummary(summary);
        recordRecentChange({
          type: "generate_recorded",
	          label: summary.blocked ? "Generate needs input" : "Generate recorded",
          detail: summary.blocked
	            ? `Generate needs input: ${summary.needs_review[0] || summary.next_action}`
            : `Generate ran ${summary.ran.join(", ") || "none"}; skipped ${summary.skipped.join(", ") || "none"}.`,
          undoBlockedReason: "Generate history is a review record. Undo draft object edits separately, then rerun Generate if needed.",
        });
        measureCivoraInteractionAfterPaint("generate.panel.response.visible", generateStartedAt, {
          target,
          blocked: summary.blocked,
          ran: summary.ran.length,
          skipped: summary.skipped.length,
        });
        void persistFlowMetadata({ generate_flow_summary_v1: summary });
      };
      if (hardPreflightBlockers.length) {
        const firstHardBlocker = hardPreflightBlockers[0];
        const summary = blockedSummary(
          firstHardBlocker.label,
          `Open ${toReadableLabel(firstHardBlocker.action)} and fix: ${firstHardBlocker.label}.`,
        );
        recordGenerateSummary(summary);
        appendChatMessage(
          "assistant",
	          `Generate needs input: ${firstHardBlocker.label}. Next action: ${summary.next_action}`,
          "status",
        );
        updateProjectStatus({
          state: "blocked",
          area: "generate",
	          title: "Generate needs input",
          detail: firstHardBlocker.label,
          nextAction: summary.next_action,
        });
        handleOpenSidePanel(firstHardBlocker.action);
        return;
      }
      if (!hasSiteBoundary()) {
        const summary = blockedSummary("missing site boundary dimensions", "Set site width/depth or draw a site boundary, then lock the site.");
        recordGenerateSummary(summary);
        updateProjectStatus({
          state: "blocked",
          area: "generate",
	          title: "Generate needs site boundary",
          detail: "Set and lock a site boundary first.",
          nextAction: summary.next_action,
        });
        askClarification(
          "I need a site boundary before generating systems. What size should the site be?",
          "set_site_then_generate",
          { target },
        );
        return;
      }
      if (!ensureSiteLocked(target)) {
        const summary = blockedSummary("site boundary exists but is not locked", "Lock the site boundary in Setup before running Generate.");
        recordGenerateSummary(summary);
        updateProjectStatus({
          state: "blocked",
          area: "generate",
	          title: "Generate needs locked boundary",
          detail: "Site boundary exists but is not locked.",
          nextAction: summary.next_action,
        });
        return;
      }
      if (target === "grading" || target === "drainage" || target === "full") {
        const lot = resolveLotBounds();
        const siteAreaAcres = siteAreaAcresFromSize(lot.w, lot.h);
        if (target === "grading" && siteAreaAcres > SITE_GRADING_HARD_BLOCK_ACRES) {
          const summary = blockedSummary(OVERSIZED_SITE_MESSAGE, "Reduce the site area or zoom to a smaller grading area.");
          recordGenerateSummary(summary);
          updateProjectStatus({
            state: "blocked",
            area: "generate",
	            title: "Generate needs smaller grading area",
            detail: OVERSIZED_SITE_MESSAGE,
            nextAction: summary.next_action,
          });
          return;
        }
      }
      const conceptCount = createGenerateConceptObjects(target, reviewNotes);
      const requestPayload = buildPayloadFromOverrides({}, undefined, projectId || null);
      const omitField = { source: "omit", value: null } as const;
      const nextManualFields = {
        ...(requestPayload.manual_fields ?? {}),
      } as Record<string, unknown>;
      const targetUsesTerrain = target === "grading" || target === "drainage" || target === "full";
      const hasSurvey = Boolean(surveyFileName) && useSurveyForGrading;
      const hasMapTerrain = Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng);
      const slopeEstimateOverride =
        options?.slopeEstimateOverride ??
        (targetUsesTerrain && !hasSurvey && !hasMapTerrain && !surveySlopeEstimate?.slope_percent
          ? buildAssumedSlopeEstimate(parsePositiveNumber(assumedTerrainSlopePct) ?? 8)
          : null);
      if (slopeEstimateOverride?.slope_percent) {
        nextManualFields.grading = {
          ...((typeof nextManualFields.grading === "object" && nextManualFields.grading !== null
            ? nextManualFields.grading
            : {}) as Record<string, unknown>),
          min_slope_pct:
            parsePositiveNumber(minSlopePct) ?? slopeEstimateOverride.slope_percent,
          assumed_terrain_source: true,
        };
        nextManualFields.terrain =
          slopeEstimateOverride.direction && slopeEstimateOverride.slope_percent
            ? `First-pass assumed ${slopeEstimateOverride.slope_percent.toFixed(2)}% slope toward ${slopeEstimateOverride.direction}`
            : "First-pass assumed terrain slope";
      }

      if (target === "roads" || target === "parking") {
        nextManualFields.grading = omitField;
        nextManualFields.drainage = omitField;
        nextManualFields.utility_network = omitField;
      } else if (target === "grading") {
        nextManualFields.drainage = omitField;
        nextManualFields.utility_network = omitField;
      } else if (target === "drainage") {
        nextManualFields.utility_network = omitField;
      } else if (target === "utilities") {
        nextManualFields.drainage = omitField;
      }

      const systemLabel = target === "full" ? "full site systems" : target;
      const queueLongRun = target === "grading" || target === "drainage" || target === "utilities" || target === "full";
      if (
        target !== "full" &&
        reactiveValidation.requiresConfirmation &&
        REACTIVE_EDIT_POLICY_PREFERENCE.require_confirmation_for_heavy_engineering
      ) {
        const confirmed = window.confirm(
          `This rerun will update ${reactiveValidation.changedSystems.join(", ")} from the saved checkpoint and may touch ${reactiveValidation.changedTargets.length} downstream stages. Run it now?`,
        );
        if (!confirmed) {
          updateProjectStatus({
            state: "stale",
            area: "generate",
            title: "Generate stale",
            detail: "Reactive engineering rerun cancelled. Visual edits remain live; engineering outputs are still stale.",
            nextAction: "Review changed objects, then rerun affected systems when ready.",
          });
          return;
        }
      }
      const systemRequestPayload = withReactiveRerunContext(
        {
          ...requestPayload,
          full_design_mode: target === "full" ? true : requestPayload.full_design_mode,
          manual_fields: nextManualFields,
          meta: {
            ...(requestPayload.meta ?? {}),
            requested_system: target,
            auto_site_context_review_summary: autoSiteContextFlowSummary,
            user_layout_context_summary: userLayoutContextSummary,
            generate_notes: reviewNotes,
          },
          prompt_text: null,
        },
        target,
      );
      if (!token && effectiveDemoWorkspaceEnabled) {
        const runSummary: GenerateFlowSummary = {
          version: "generate_flow_summary_v1",
          generated_at: new Date().toISOString(),
          target,
          ran: targetSystems,
          skipped: skippedSystems,
          needs_review: reviewNotes,
          notes: reviewNotes,
          blocked: false,
          next_action: reviewNotes.length
            ? "Review the local draft notes and provide or accept missing sources before relying on outputs."
            : "Review the local draft package; outputs remain engineer-review-required.",
          auto_site_context: autoSiteContextFlowSummary,
          user_layout_context: userLayoutContextSummary,
          safety_wording:
            "Generate creates review-required drafts for qualified review.",
        };
        recordGenerateSummary(runSummary);
        setSystemStatuses((prev) => {
          const next = { ...prev };
          targetSystems.forEach((system) => {
            next[system] = "fresh";
          });
          return next;
        });
        updateProjectStatus({
          state: "needs review",
          area: "generate",
          title: runSummary.skipped.length ? "Started, with skipped systems" : "Generate draft ready",
          detail: `${systemLabel} ran in local demo mode with review-required outputs.`,
          nextAction: runSummary.next_action,
        });
        appendChatMessage(
          "assistant",
          [
            `${runSummary.skipped.length ? "Started, with skipped systems" : "Generate started"}. Ran: ${runSummary.ran.join(", ")}.`,
            conceptCount ? `Canvas: added ${conceptCount} visible review concept object${conceptCount === 1 ? "" : "s"}.` : "",
            runSummary.skipped.length ? `Skipped: ${runSummary.skipped.join(", ")}.` : "Skipped: none.",
            runSummary.needs_review.length ? `Needs review: ${runSummary.needs_review.slice(0, 5).join("; ")}.` : "Needs review: standard engineer review.",
          ].filter(Boolean).join(" "),
          "status",
        );
        return;
      }
      if (!token) {
        const summary = blockedSummary(
          "backend/auth session is required to run Generate on the hosted website",
          "Sign in/connect backend, or keep editing the local review layout before running Generate.",
        );
        recordGenerateSummary(summary);
        updateProjectStatus({
          state: "blocked",
          area: "generate",
          title: "Generate needs sign-in",
          detail: "Hosted Generate needs a signed-in backend session. No backend request was sent.",
          nextAction: summary.next_action,
        });
        appendChatMessage(
          "assistant",
          conceptCount
            ? `I added ${conceptCount} visible review concept object${conceptCount === 1 ? "" : "s"} to the canvas. Hosted Generate still needs a signed-in backend session before an engineering request can run.`
            : "Generate needs a signed-in backend session on the hosted website. I did not send an engineering request; keep editing locally or sign in/connect backend to run Generate.",
          "status",
        );
        return;
      }
      const runSummary: GenerateFlowSummary = {
        version: "generate_flow_summary_v1",
        generated_at: new Date().toISOString(),
        target,
        ran: targetSystems,
        skipped: skippedSystems,
        needs_review: reviewNotes,
        notes: reviewNotes,
        blocked: false,
        next_action: reviewNotes.length
          ? "Review the generated draft notes and provide or accept missing sources before relying on outputs."
          : "Review the generated draft package; outputs remain engineer-review-required.",
        auto_site_context: autoSiteContextFlowSummary,
        user_layout_context: userLayoutContextSummary,
        safety_wording:
          "Generate creates review-required drafts for qualified review.",
      };
      recordGenerateSummary(runSummary);
      updateProjectStatus({
        state: "working",
        area: "generate",
        title: "Generate working",
        detail: `Running ${systemLabel} from the locked site.`,
        nextAction: "Wait for the run to finish, queue, or show a blocker.",
      });
      appendChatMessage(
        "assistant",
        [
          `${runSummary.skipped.length ? "Started, with skipped systems" : "Generate started"}. Ran: ${runSummary.ran.join(", ")}.`,
          conceptCount ? `Canvas: added ${conceptCount} visible review concept object${conceptCount === 1 ? "" : "s"}.` : "",
          runSummary.skipped.length ? `Skipped: ${runSummary.skipped.join(", ")}.` : "Skipped: none.",
          runSummary.needs_review.length ? `Needs review: ${runSummary.needs_review.slice(0, 5).join("; ")}.` : "Needs review: standard engineer review.",
        ].filter(Boolean).join(" "),
        "status",
      );
      await executePlanAction({
        mode: "run",
        requestPayload: systemRequestPayload,
        assistantPrefix: `Generating a review draft for ${systemLabel} around the locked site...`,
        timeoutMs: queueLongRun ? undefined : 20_000,
        allowQueueFallback: true,
        forceQueue: queueLongRun,
      });
      if (queueLongRun) {
        return;
      }
      setSystemStatuses((prev) => {
        const next = { ...prev };
        next[target] = "fresh";
        reactiveChangedSystems.forEach((system) => {
          next[system] = "fresh";
        });
        return next;
      });
      updateProjectStatus({
        state: "needs review",
        area: "generate",
        title: "Generate needs review",
        detail: `${systemLabel} draft is current in this workspace.`,
        nextAction: runSummary.next_action,
      });
    },
    [
      askClarification,
      assumedTerrainSlopePct,
      buildPayloadFromOverrides,
      createGenerateConceptObjects,
      currentGenerateLayoutContext,
      executePlanAction,
      getGeneratePreflightBlockers,
      hasSiteBoundary,
      ensureSiteLocked,
      autoSiteContextFlowSummary,
      hasAssumedTerrainSlope,
      minSlopePct,
      persistFlowMetadata,
      projectId,
      resolveLotBounds,
      siteInputs?.geocode?.lat,
      siteInputs?.geocode?.lng,
      surveyFileName,
      surveySlopeEstimate?.slope_percent,
      token,
      useSurveyForGrading,
      withReactiveRerunContext,
      reactiveValidation,
      reactiveChangedSystems,
      recordRecentChange,
      updateProjectStatus,
    ],
  );

  useEffect(() => {
    handleGenerateSystemRef.current = handleGenerateSystem;
  }, [handleGenerateSystem]);

  const handleApplyDrainageIssue = useCallback(
    async (issue: Issue) => {
      const issueCode = (issue.code ?? "").toUpperCase();
      const lot = resolveLotBounds();
      const lowPoint = pickBestLowPoint();
      const issueX = typeof issue.context?.x === "number" ? issue.context.x : Number(issue.context?.x);
      const issueY = typeof issue.context?.y === "number" ? issue.context.y : Number(issue.context?.y);
      const issueLocation =
        Number.isFinite(issueX) && Number.isFinite(issueY) ? { x: issueX, y: issueY } : null;
      const distanceFt = (a: { x: number; y: number }, b: { x: number; y: number }) =>
        Math.hypot(a.x - b.x, a.y - b.y);
      const findNearbyPlacement = (
        type: SiteObjectType,
        point: { x: number; y: number },
        threshold: number,
      ) =>
        buildingPlacements.find(
          (item) =>
            item.type === type &&
            item.placed &&
            Number.isFinite(item.x) &&
            Number.isFinite(item.y) &&
            distanceFt({ x: item.x as number, y: item.y as number }, point) <= threshold,
        );

      if (issueCode === "UNDER_COLLECTION" || issueCode === "UNDER_COLLECTION_REDUCED") {
        if (!lowPoint) {
          setStatusMessage("No low points available to place an inlet.");
          return;
        }
        if (issueLocation && distanceFt(lowPoint, issueLocation) > 200) {
          setStatusMessage("Closest low point is too far from the flagged area to place an inlet.");
          return;
        }
        if (findNearbyPlacement("inlet", lowPoint, 10)) {
          setStatusMessage("An inlet already exists near the suggested location.");
          return;
        }
        if (
          drainageForcedInlets.some(
            (item) =>
              typeof item.x === "number" &&
              typeof item.y === "number" &&
              distanceFt({ x: item.x, y: item.y }, lowPoint) <= 8,
          )
        ) {
          setStatusMessage("An inlet is already queued near that location.");
          return;
        }
        const forcedInlet = {
          x: lowPoint.x,
          y: lowPoint.y,
          label: "Autofix inlet",
          source: "autofix",
        };
        const nextForced = [...drainageForcedInlets, forcedInlet];
        setDrainageForcedInlets(nextForced);
        const inletPlacement: BuildingPlacement = {
          id: `inlet-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: "Autofix inlet",
          type: "inlet",
          w: 8,
          d: 8,
          x: lowPoint.x - 4,
          y: lowPoint.y - 4,
          rotation: 0,
          placed: true,
          source: "generated",
          generated: true,
          systemDependencies: ["drainage"],
        };
        clearGeneratedPreview();
        setBuildingPlacements((prev) => [...prev, inletPlacement]);
        setExternalRectUndo({
          id: inletPlacement.id,
          snapshot: inletPlacement,
          action: "add",
          ts: Date.now(),
        });
        setFocusObjectId(inletPlacement.id);
        const queued = await runDrainageAutofix({ placementsOverride: [...buildingPlacements, inletPlacement], forcedInlets: nextForced });
        if (queued) {
          setStatusMessage("Applied inlet placement. Drainage regenerated.");
        }
        return;
      }

      if (issueCode === "ORPHAN_INLETS") {
        if (drainageConnectOrphans) {
          setStatusMessage("Orphan inlet connection already queued. Regenerate drainage to apply.");
          return;
        }
        setDrainageConnectOrphans(true);
        const queued = await runDrainageAutofix({ connectOrphans: true });
        if (queued) {
          setStatusMessage("Applied orphan inlet connection. Drainage regenerated.");
        }
        return;
      }

      if (issueCode === "POOR_SLOPE") {
        if (drainageAllowSlopeAdjust) {
          setStatusMessage("Slope adjustment already queued. Regenerate drainage to apply.");
          return;
        }
        setDrainageAllowSlopeAdjust(true);
        const queued = await runDrainageAutofix({ allowSlopeAdjust: true });
        if (queued) {
          setStatusMessage("Applied slope adjustment attempt. Drainage regenerated.");
        }
        return;
      }

      if (
        issueCode === "BASIN_UNREACHABLE" ||
        issueCode === "DRAINAGE_NO_BASIN" ||
        issueCode === "NO_VALID_OUTFALL" ||
        issueCode === "NO_PONDS_DEFINED"
      ) {
        if (!lowPoint) {
          setStatusMessage("No low points available to place a basin.");
          return;
        }
        if (issueCode === "BASIN_UNREACHABLE" && issueLocation && distanceFt(lowPoint, issueLocation) > 300) {
          setStatusMessage("Closest low point is too far from the flagged area to place a basin.");
          return;
        }
        if (findNearbyPlacement("basin", lowPoint, 40)) {
          setStatusMessage("A basin already exists near the suggested location.");
          return;
        }
        const basinPlacement: BuildingPlacement = {
          id: `basin-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: "Autofix basin",
          type: "basin",
          w: 60,
          d: 40,
          x: Math.min(Math.max(lowPoint.x - 30, lot.x), lot.x + lot.w - 60),
          y: Math.min(Math.max(lowPoint.y - 20, lot.y), lot.y + lot.h - 40),
          rotation: 0,
          placed: true,
          source: "generated",
          generated: true,
          systemDependencies: ["drainage"],
        };
        clearGeneratedPreview();
        const nextPlacements = [...buildingPlacements, basinPlacement];
        setBuildingPlacements(nextPlacements);
        setExternalRectUndo({
          id: basinPlacement.id,
          snapshot: basinPlacement,
          action: "add",
          ts: Date.now(),
        });
        setFocusObjectId(basinPlacement.id);
        const forcedBasins = nextPlacements
          .filter((placement) => placement.type === "basin")
          .map((placement) => ({
            id: placement.id,
            name: placement.label,
            x: placement.x,
            y: placement.y,
            w: placement.w,
            d: placement.d,
            rotation: placement.rotation ?? 0,
            locked: placement.locked,
            source: "autofix",
            generated: placement.generated,
            systemDependencies: placement.systemDependencies,
          }));
        const queued = await runDrainageAutofix({
          placementsOverride: nextPlacements,
          forcedBasins,
        });
        if (queued) {
          setStatusMessage("Applied basin placement. Drainage regenerated.");
        }
        return;
      }
    },
    [
      buildingPlacements,
      clearGeneratedPreview,
      drainageForcedInlets,
      pickBestLowPoint,
      resolveLotBounds,
      runDrainageAutofix,
      setDrainageAllowSlopeAdjust,
      setDrainageConnectOrphans,
      setDrainageForcedInlets,
      setFocusObjectId,
      setStatusMessage,
    ],
  );

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
  }, [setJobs]);

  const handleNewProject = async () => {
    const newProjectStartedAt = markCivoraInteraction();
    debugLog("new-project-start");
    projectLoadRequestRef.current += 1;
    suppressProjectAutoLoadRef.current = true;
    autosaveSuspendRef.current = true;
    if (chatAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(chatAutosaveTimeoutRef.current);
      chatAutosaveTimeoutRef.current = null;
    }
    if (controlAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(controlAutosaveTimeoutRef.current);
      controlAutosaveTimeoutRef.current = null;
    }
    draftProjectPromiseRef.current = null;
    resolvedProjectIdRef.current = "";
    setProjectId("");
    setCurrentProject(null);
    setSelectedRunId("");
    setActiveJobId("");
    setPrompt("");
    setImageName("");
    setPlanSheetSet(createDefaultPlanSheetSet("Untitled Project"));
    setUploadedImageApiUrl("");
    setUploadedImagePreviewUrl("");
    setSurveyFileName("");
    setSurveySlopeEstimate(null);
    setSurveyPoints([]);
    setSurveyPreviewPoints([]);
    setSurveyDiagnostics(null);
    setUseSurveyForGrading(true);
    setMapSnapshotPath("");
    setMapAnalysis(null);
    resetWorkspaceState();
    setSystemStatuses(DEFAULT_SYSTEM_STATUS);
    setAssumptions(defaultAssumptions);
    setIssues([]);
    setSiteName("");
    setFileName("");
    setSiteNameAuto(false);
    setFileNameAuto(false);
    setProjectType("");
    setUnits("ft");
    setLotWidth("");
    setLotHeight("");
    setBuildingWidth("");
    setBuildingDepth("");
    setBuildingCount("");
    setSetback("");
    setParkingCount("");
    setParkingStallWidth("9");
    setParkingStallDepth("18");
    setParkingAisleWidth("24");
    setParkingAdaAisleWidth("8");
    setParkingAdaCount("0");
    setParkingCompactCount("0");
    setParkingCompactWidth("8");
    setParkingAngle("90");
    setParkingLoading("double");
    setMinSlopePct("");
    setPipeMinSlopePct("");
    setMaxParkingSlopePct("");
    setMaxRoadGradePct("");
    setMaxAdaCrossSlopePct("");
    setRoads(true);
    setGrading(true);
    setDrainage(true);
    setUtilities(true);
    setActiveSidePanel(null);
    setRenderedSidePanel(null);
    setSidePanelVisible(false);
    setRightRailCollapsed(true);
    setWorkspaceChromeMinimized(true);
    setLeftSidebarOpen(true);
    const nextThread = [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
        window.localStorage.removeItem(getChatThreadStorageKey("draft"));
      } catch {
        // Ignore local storage failures.
      }
    }
    setWorkspaceRestoreState("idle");
    setProjectDrawerNotice("Unsaved draft. Save Project will persist this clean workspace.");
    setStatusMessage("Started a new project.");
    measureCivoraInteractionAfterPaint("projects.drawer.new_project", newProjectStartedAt);
    draftProjectPromiseRef.current = null;
    suppressProjectAutoLoadRef.current = false;
    window.setTimeout(() => {
      autosaveSuspendRef.current = false;
    }, 0);
  };

  const handleDeleteProject = async (projectIdToDelete: string) => {
    const deleteStartedAt = markCivoraInteraction();
    if (!token) {
      const message = "Sign in and reconnect to the backend before deleting saved projects.";
      setProjectDrawerNotice(message);
      updateProjectStatus({
        state: "blocked",
        area: "projects",
        title: "Delete needs sign-in",
        detail: "Sign in and reconnect to the backend before deleting saved projects.",
        nextAction: "Sign in or reconnect backend, then retry delete from Projects.",
      });
      measureCivoraInteractionAfterPaint("projects.drawer.delete_project.blocked", deleteStartedAt, {
        projectId: projectIdToDelete,
      });
      return;
    }
    const target = projects.find((item) => item.project_id === projectIdToDelete);
    const confirmed = window.confirm(
      `Delete "${target?.name || "Untitled Project"}"? This cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      updateProjectStatus({
        state: "working",
        area: "projects",
        title: "Deleting project",
        detail: `Deleting "${target?.name || "Untitled Project"}" from saved projects.`,
        nextAction: "Wait for the backend to confirm deletion or show a blocker.",
      });
      const response = await deleteJson<{ success: boolean }>(`/api/projects/${projectIdToDelete}`, {
        token,
      });
      if (!response.success) {
        throw new Error("the backend did not confirm deletion.");
      }
      if (typeof window !== "undefined") {
        try {
          window.localStorage.removeItem(getChatThreadStorageKey(projectIdToDelete));
        } catch {
          // Ignore local storage failures.
        }
      }
      removeProjectSummary(projectIdToDelete);
      if (currentProject?.project_id === projectIdToDelete || projectId === projectIdToDelete) {
        await handleNewProject();
      } else {
        await refreshProjects(token);
      }
      setProjectDrawerNotice("Project deleted.");
      updateProjectStatus({
        state: "ready",
        area: "projects",
        title: "Project deleted",
        detail: "The saved project was deleted.",
        nextAction: "Start or open another project before continuing.",
      });
      measureCivoraInteractionAfterPaint("projects.drawer.delete_project", deleteStartedAt, {
        projectId: projectIdToDelete,
      });
    } catch (error) {
      const message =
        error instanceof Error ? `Delete could not finish: ${error.message}` : "Delete could not finish.";
      setProjectDrawerNotice(message);
      updateProjectStatus({
        state: "blocked",
        area: "projects",
        title: "Delete could not finish",
        detail: message,
        nextAction: "Check auth/backend connectivity, then retry delete from Projects.",
      });
      measureCivoraInteractionAfterPaint("projects.drawer.delete_project.failed", deleteStartedAt, {
        projectId: projectIdToDelete,
      });
    }
  };

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
	    previewReview,
	    previewBlockedReasons,
	    previewRunningPhase,
	    previewNextPendingPhase,
	  } = usePreviewReview({ currentPlanMeta, planPreviewSummary });
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
  const systemEvidenceView = useMemo(() => buildDashboardSystemEvidenceView({
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
  }), [
    appliedAddressLabel,
    buildingPlacements,
    hasAppliedAddress,
    hasAssumedTerrainSlope,
    hasBasinObject,
    hasBasinPlaced,
    hasLocationEvidence,
    hasStandardsEvidence,
    hasTerrainSource,
    hasUtilityConnectionObject,
    hasUtilityConnectionPlaced,
    hasVerifiedSurveyControl,
    issues,
    mapAnalysis?.success,
    missingSite,
    onlineSourceLookupLabel,
    onlineSourceLookupUnavailable,
    siteInputs,
    siteScaleLocked,
    siteTooLargeForGrading,
    systemStatuses,
    uploadedImageApiUrl,
    uploadedImagePreviewUrl,
    utilities,
  ]);
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

  const contextualToolbarTools = useMemo(
    () =>
      buildDashboardContextualToolbarTools({
        activePrimaryWorkflowKey,
        sidePanelForRender,
        siteScaleLocked,
        previewInteraction,
        showMeasurements,
        showCalculations,
        layerManagerOpen,
        onOpenPanel: handleOpenPanelFromDrawer,
        onToggleSiteLock: () => void handleApplySite(),
        onUnlockSite: handleUnlockSite,
        onStartSiteBoundaryDraw: handleStartSiteBoundaryDraw,
        onSetPreviewInteraction: setPreviewInteraction,
        onToggleMeasurements: () => setShowMeasurements((value) => !value),
        onToggleCalculations: () => setShowCalculations((value) => !value),
        onToggleLayerManager: () => setLayerManagerOpen((value) => !value),
      }),
    [
      activePrimaryWorkflowKey,
      handleApplySite,
      handleOpenPanelFromDrawer,
      handleStartSiteBoundaryDraw,
      handleUnlockSite,
      layerManagerOpen,
      previewInteraction,
      showCalculations,
      showMeasurements,
      sidePanelForRender,
      siteScaleLocked,
    ],
  );
  const {
    handleEditFloatingSelectedObject,
    handleFocusFloatingSelectedObject,
    handleOpenFloatingObjectDetails,
    selectedObjectConfidence,
  } = useDashboardFloatingObjectActions({
    appendChatMessage,
    handleOpenPanelFromDrawer,
    selectedBuilding,
    setActiveSidePanel,
    setFocusObjectId,
    setMoveEditFeedback,
    setPlacementModeEnabled,
    setPreviewInteraction,
    setStatusMessage,
    sourceConfidenceByObjectId,
  });
  const {
    sidebarStaleSystems,
    sidebarMissingInputs,
    sidebarReleaseStatus,
    sidebarTrustScore,
    sidebarAssumptions,
    sidebarTruthItems,
    reviewGateItems,
  } = buildDashboardSidebarReviewState({
    systemStatuses,
    missingSite,
    hasTerrainSource,
    hasBasinPlaced,
    drainageFresh: systemStatuses.drainage === "fresh",
    backendResultPresent: Boolean(backendResult),
    siteScaleLocked,
    buildingPlacementCount: buildingPlacements.length,
    siteAddress,
    siteInputAddress: siteInputs?.address,
    siteInputLat: siteInputs?.geocode?.lat,
    siteInputLng: siteInputs?.geocode?.lng,
    uploadedImagePreviewUrl,
    uploadedImageApiUrl,
    surveyPreviewPointCount: surveyPreviewPoints.length,
    mapSnapshotPath,
    releaseStatusRaw: previewReview?.release_status,
    trustScoreRaw: previewReview?.trust_score,
    assumptionCategories: previewReview?.assumption_categories,
    hasHardSystemBlock,
    previewBlockedReasonCount: previewBlockedReasons.length,
    standardsOk: panelStatus("standards") === "ok",
  });
  const exportBlockText = getExportBlockReason();
  const { setupWizardState, setupWizardSteps, nextSetupAction } = buildDashboardSetupWizardState({
    persistedSetupWizardState: currentPlanMeta.setup_wizard_state_v1,
    hasAppliedAddress,
    siteAddress,
    appliedAddressLabel,
    siteScaleLocked,
    siteSizeSet,
    hasSiteObject: buildingPlacements.some((item) => item.type === "site"),
    hasSourceContext: Boolean(mapAnalysis?.success || uploadedImageApiUrl || uploadedImagePreviewUrl),
    onlineSourceLookupLabel,
    hasVerifiedSurveyControl,
    hasTerrainSource,
    surveyPreviewPointCount: surveyPreviewPoints.length,
    hasAssumedTerrainSlope,
    standardsOk: panelStatus("standards") === "ok",
    placedObjectCount,
    parkingCount,
    systemStatuses,
    hasBackendResult: Boolean(backendResult),
    exportBlockText,
  });
  const dashboardGuidanceStats: Array<[string, number]> = [
    ["Objects", placedObjectCount],
    ["Issues", issues.length + analysisIssues.length],
    ["Fresh", Object.values(systemStatuses).filter((status) => status === "fresh").length],
    ["Outputs", backendResult ? 1 : 0],
  ];
  const progressPanelTarget = (value?: string): SidePanelKey => {
    const panel = String(value || "dashboard") as SidePanelKey;
    return sidePanelCopy[panel] ? panel : "dashboard";
  };
  const bottomBlockerItems = [
    ...canonicalWorkspaceBlockers,
    ...previewBlockedReasons,
    ...issues.map((issue) => issue.message),
    ...analysisIssues.map((issue) => issue.message),
  ].filter(Boolean);
  const { progressTimelineState, progressTimelineSteps, progressPercent } = buildDashboardProgressTimelineState({
    persistedProgressTimeline: currentPlanMeta.progress_timeline_v1,
    setupWizardSteps,
    candidatePendingCount: candidateReviewCounts.pending ?? 0,
    candidateAcceptedCount: candidateReviewCounts.accepted ?? 0,
    candidateItemCount: candidateReviewItems.length,
    candidateTotalCount: candidateReviewInbox.candidate_count ?? 0,
    placedObjectCount,
    systemStatuses,
    bottomBlockerItems,
    hasHardSystemBlock,
    hasBackendResult: Boolean(backendResult),
    exportBlockText,
  });
  const visibleStatusSummary = bottomBlockerItems.length
    ? bottomBlockerItems.slice(0, 6).join("; ")
    : hasHardSystemBlock
      ? "Hard system blocker recorded."
      : backendResult
        ? "No visible blockers recorded."
        : "No run output yet.";
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
    activeSidePanel !== "chat" &&
    !sidePanelVisible &&
    !(mobileViewport && leftSidebarOpen);
  const workspaceChromeHidden = workspaceChromeMinimized || (drawWorkspaceActive && sidebarVisible);
  const issueDiagnosticSummary = buildIssueDiagnosticSummary({
    projectId: currentProject?.project_id || projectId || "draft / unavailable",
    projectName: siteName || currentProject?.name || "Untitled Project",
    panelTitle: sidePanelForRender ? sidePanelCopy[sidePanelForRender].title : activeWorkspaceMode,
    visibleStatusSummary,
    siteLocked: siteScaleLocked,
    lotWidth: lotBounds.w,
    lotHeight: lotBounds.h,
    systemStatuses,
    issueReportMessage,
  });
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
                  <DashboardHomePanel
                    projectSummary={{
                      siteName,
                      fileName,
                      lotWidth: lotBounds.w,
                      lotHeight: lotBounds.h,
                      hasHardSystemBlock,
                      hasBackendResult: Boolean(backendResult),
                      onSiteNameChange: (value) => {
                        setSiteName(value);
                        setSiteNameAuto(false);
                      },
                      onFileNameChange: (value) => {
                        setFileName(value);
                        setFileNameAuto(false);
                      },
                      onSaveName: () =>
                        void saveProject({
                          nameOverride: siteName.trim(),
                          fileNameOverride: fileName.trim(),
                          autoNamedOverride: false,
                          autoFileNamedOverride: false,
                        }),
                    }}
                    progressTimeline={{
                      progressTimelineState,
                      progressTimelineSteps,
                      progressPercent,
                      onOpenPanel: handleOpenSidePanel,
                      progressPanelTarget,
                      progressTimelineDotClass,
                      progressTimelineStatusClass,
                    }}
                    engineDepth={engineDepthDashboard ? {
                      dashboard: engineDepthDashboard,
                      onOpenPanel: handleOpenSidePanel,
                    } : null}
                    guidance={{ stats: dashboardGuidanceStats }}
                    issueReport={{
                      message: issueReportMessage,
                      diagnosticSummary: issueDiagnosticSummary,
                      copied: issueReportCopied,
                      onMessageChange: setIssueReportMessage,
                      onCopyDiagnostic: handleCopyIssueDiagnostic,
                    }}
                    runReview={workflowReviewDashboard ? {
                      dashboard: workflowReviewDashboard,
                      onOpenPanel: handleOpenSidePanel,
                    } : null}
                    statusPanels={{
                      systemHealthItems,
                      attentionMessages: [...issues.map((issue) => issue.message), ...analysisIssues.map((issue) => issue.message)],
                      onOpenHealthItem: (key) =>
                        handleOpenSidePanel(
                          key === "data"
                            ? "site_existing"
                            : key === "roadway"
                              ? "roadway"
                              : (key as SidePanelKey),
                        ),
                      onOpenReview: () => handleOpenSidePanel("analysis"),
                    }}
                    takeoffSnapshot={{
                      rows: quantityRows,
                      formatMetric,
                      statusLabelForQuantityReview,
                    }}
                  />
                ) : null}

                {sidePanelForRender === "site_existing" ? (
                  <SiteSetupPanel
                    address={{
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
                    }}
                    boundary={{
                      lotBounds,
                      lotWidth,
                      lotHeight,
                      siteScaleLocked,
                      siteTooLargeForWarning,
                      oversizedSiteMessage: OVERSIZED_SITE_MESSAGE,
                      siteAddress,
                      onlineDiscoveryBusy,
                      onLotWidthChange: setLotWidth,
                      onLotHeightChange: setLotHeight,
                      onStartSiteBoundaryDraw: handleStartSiteBoundaryDraw,
                      onApplySite: () => void handleApplySite(),
                      onUnlockSite: handleUnlockSite,
                      onCreateCenteredSite: () => void handleCreateCenteredSiteFromSetup(),
                    }}
                    surveyTerrain={{
                      hasTerrainSource,
                      surveyFileName,
                      uploadedImagePreviewUrl,
                      uploadedImageApiUrl,
                      surveyPreviewPointCount: surveyPreviewPoints.length,
                      surveyUploadMessage,
                      imageUploadState,
                      imageUploadNote,
                      mapSnapshotPath,
                      mapSnapshotInputRef,
                      surveyInputRef,
                      onOpenImport: () => handleOpenSidePanel("import_survey"),
                      onAnalyzeMapSnapshot: analyzeMapSnapshot,
                      onUploadImage: uploadImage,
                      onUploadExistingConditions: uploadExistingConditions,
                    }}
                    autoSiteContext={{
                      autoSiteContextFlowSummary,
                      autoExistingConditionsStatus,
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
                      hasAppliedAddress,
                      onlineDiscoveryBusy,
                      onReviewFoundContext: () => handleOpenSidePanel("data"),
                      onRerunSiteContext: () => void saveSiteAddress(),
                    }}
                  />
                ) : null}


                {sidePanelForRender === "import_survey" ? (
                  <ImportSurveyPanel
                    mapSnapshotReady={Boolean(uploadedImagePreviewUrl || uploadedImageApiUrl)}
                    surveyPointCount={surveyPreviewPoints.length}
                    imageUploadState={imageUploadState}
                    imageUploadNote={imageUploadNote}
                    surveyUploadMessage={surveyUploadMessage}
                    planPdfReady={Boolean(planPdfAnalysis)}
                    mapAnalysisReady={Boolean(mapAnalysis?.success)}
                    mapSnapshotPath={mapSnapshotPath}
                    hasTerrainSource={hasTerrainSource}
                    detectionScaleFtPerPx={detectionScaleFtPerPx}
                    siteRotationDeg={siteRotationDeg}
                    siteScaleLocked={siteScaleLocked}
                    mapSnapshotInputRef={mapSnapshotInputRef}
                    surveyInputRef={surveyInputRef}
                    onUploadImage={uploadImage}
                    onUploadExistingConditions={uploadExistingConditions}
                    onOpenPlanPdf={() => handleOpenSidePanel("data")}
                    onAnalyzeMapSnapshot={analyzeMapSnapshot}
                    onFitToSite={() => setFitToSiteRequest((value) => value + 1)}
                    onMapCenter={() => setMapCenterRequest((value) => value + 1)}
                    onAlignRoad={() => setAlignToRoadRequest((value) => value + 1)}
                    onResetRotation={() => {
                      setSiteRotationDeg(0);
                      setSiteRotationInput("0");
                      scheduleRotationSave(0);
                    }}
                    onRotationChange={(value) => {
                      setSiteRotationDeg(value);
                      setSiteRotationInput(String(value));
                      scheduleRotationSave(value);
                    }}
                  />
                ) : null}

                {sidePanelForRender === "data" ? (
                  <DataSourcesPanel
                    sourceHubLinks={sourceHubLinks}
                    sourceHubMetrics={sourceHubMetrics}
                    sourceConfidenceEntryCount={sourceConfidenceSummary.entry_count ?? sourceConfidenceEntries.length}
                    sourceConfidenceRows={sourceConfidenceRows}
                    onOpenPanel={handleOpenSidePanel}
                    planPdfAnalysis={planPdfAnalysis}
                    planPdfSourceUrl={planPdfSourceUrl}
                    planPdfFirstPage={planPdfFirstPage}
                    planPdfElements={planPdfElements}
                    selectedPlanPdfElement={selectedPlanPdfElement}
                    planPdfChangedReport={planPdfChangedReport}
                    planPdfChangedElements={planPdfChangedElements}
                    planPdfUnreadableItems={planPdfUnreadableItems}
                    planPdfBlockers={planPdfBlockers}
                    planPdfUploadState={planPdfUploadState}
                    planPdfUploadMessage={planPdfUploadMessage}
                    planPdfElementDraftText={planPdfElementDraftText}
                    planPdfMoveX={planPdfMoveX}
                    planPdfMoveY={planPdfMoveY}
                    planPdfExtractionSummaryRows={planPdfExtractionSummaryRows}
                    planPdfClassificationPreviewRows={planPdfClassificationPreviewRows}
                    planPdfInputRef={planPdfInputRef}
                    onUploadPlanPdf={uploadPlanPdf}
                    onSelectPlanPdfElement={setSelectedPlanPdfElementId}
                    onPlanPdfDraftTextChange={setPlanPdfElementDraftText}
                    onPlanPdfMoveXChange={setPlanPdfMoveX}
                    onPlanPdfMoveYChange={setPlanPdfMoveY}
                    onUpdatePlanPdfElement={(elementId, patch) => void updatePlanPdfElement(elementId, patch)}
                    onExportPlanPdfJson={() => void exportPlanPdfReport()}
                    onExportPlanPdf={() => void exportPlanPdfReviewPdf()}
                    onEditPdfByChat={() => {
                      setPrompt("change pool deck elevation");
                      handleOpenSidePanel("chat");
                    }}
                    onWhatChanged={() => {
                      setPrompt("what changed?");
                      handleOpenSidePanel("chat");
                    }}
                    onAskUnreadable={() => {
                      setPrompt("show unreadable text");
                      handleOpenSidePanel("chat");
                    }}
                    onInvalidPlanPdfMove={() => {
                      setStatusMessage("Moving a PDF-derived element requires explicit target x0/y0 coordinates.");
                    }}
                    capabilityAuditRows={capabilityAuditRows}
                    onlineDiscoveryStatus={onlineDiscovery.status ?? ""}
                    onlineDiscoveryRan={Boolean(onlineDiscovery.version)}
                    onlineDiscoverySources={onlineDiscoverySources}
                    candidateReviewCounts={candidateReviewCounts}
                    candidateReviewItems={candidateReviewItems}
                    onCandidateDecision={(candidateId, decision) => void handleCandidateReviewDecision(candidateId, decision)}
                    siteAddress={siteAddress}
                    selectedAddressSuggestion={selectedAddressSuggestion}
                    addressSuggestions={addressSuggestions}
                    onSiteAddressChange={setSiteAddress}
                    onSelectedAddressSuggestionChange={setSelectedAddressSuggestion}
                    onAddressSuggestionsChange={setAddressSuggestions}
                    onApplyAddress={() => void saveSiteAddress()}
                    autoExistingConditionsStatus={autoExistingConditionsStatus}
                    mapSnapshotInputRef={mapSnapshotInputRef}
                    uploadedImageApiUrl={uploadedImageApiUrl}
                    uploadedImagePreviewUrl={uploadedImagePreviewUrl}
                    imageUploadState={imageUploadState}
                    imageUploadNote={imageUploadNote}
                    mapSnapshotPath={mapSnapshotPath}
                    mapAnalysis={mapAnalysis}
                    onAnalyzeMapSnapshot={analyzeMapSnapshot}
                    siteScaleLocked={siteScaleLocked}
                    onUnlockSite={handleUnlockSite}
                    onApplySite={() => void handleApplySite()}
                    lotBounds={lotBounds}
                    siteTooLargeForWarning={siteTooLargeForWarning}
                    missingSite={missingSite}
                    hasTerrainSource={hasTerrainSource}
                    siteTooLargeForGrading={siteTooLargeForGrading}
                    onGenerateSystem={handleGenerateSystem}
                    onAnalyzeImageFeatures={() => handleAnalyzeImageFeatures()}
                    missingImage={missingImage}
                    detectedPlacementsCount={detectedPlacements.length}
                    siteSelectionMode={siteSelectionMode}
                    hasSiteObject={buildingPlacements.some((item) => item.type === "site")}
                    detectionChoices={detectionChoices}
                    onDetectionChoicesChange={setDetectionChoices}
                    onRunSelectedDetections={() => void runSelectedDetections()}
                    onAnalyzeSiteAccess={handleAnalyzeSiteAccess}
                    confirmedObjectCounts={confirmedObjectCounts}
                    analysisIssueCount={analysisIssues.length}
                    mapAnalysisCounts={mapAnalysisCounts}
                    siteRotationDeg={siteRotationDeg}
                    siteRotationInput={siteRotationInput}
                    onSiteRotationDegChange={setSiteRotationDeg}
                    onSiteRotationInputChange={setSiteRotationInput}
                    onScheduleRotationSave={scheduleRotationSave}
                    onFitToSite={() => setFitToSiteRequest((value) => value + 1)}
                    onUseMapCenter={() => setMapCenterRequest((value) => value + 1)}
                    onAlignToRoad={() => setAlignToRoadRequest((value) => value + 1)}
                    drainageSourceOverride={drainageSourceOverride}
                    drainageSurfaceSummary={drainageSurfaceSummary}
                    onDrainageSourceOverrideChange={(next) => {
                      setDrainageSourceOverride(next);
                      const currentInput = currentProject?.project_input ?? payloadPreview;
                      void saveProject({
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
                    }}
                    mapSnapshotUploadInputRef={mapSnapshotInputRef}
                    onUploadImage={uploadImage}
                  />
                ) : null}

                {sidePanelForRender === "model" ? (
                  <ModelReviewPanel
                    previewMode={previewMode}
                    previewQuality={previewQuality}
                    hasGradingSurface={hasGradingSurface}
                    hasHardSystemBlock={hasHardSystemBlock}
                    placedObjectCount={placedObjectCount}
                    issueCount={issues.length + analysisIssues.length}
                  />
                ) : null}

                {sidePanelForRender === "generate" ? (
                  <GeneratePanel
                    missingSite={missingSite}
                    busy={busy}
                    hasVisibleActiveJob={Boolean(visibleActiveJob)}
                    statusMessage={statusMessage}
                    assistedEnabled={assistedEnabled}
                    pendingPlacementCount={pendingPlacementObjects.length}
                    pendingPlacementLabels={pendingPlacementLabels}
                    currentUserLayoutContext={currentGenerateLayoutContext}
                    autoSiteContextFlowSummary={autoSiteContextFlowSummary}
                    systemReadinessRows={systemReadinessRows}
                    issues={issues}
                    generateFlowSummary={generateFlowSummary}
                    reactiveValidation={reactiveValidation}
                    reactiveAffectedRunTarget={reactiveAffectedRunTarget}
                    onAssistedEnabledChange={setAssistedEnabled}
                    onStatusMessageChange={setStatusMessage}
                    onGenerateFlowSummaryChange={setGenerateFlowSummary}
                    onGenerateSystem={(target) => void handleGenerateSystem(target)}
                    drainageIssueApplyLabel={drainageIssueApplyLabel}
                    canApplyDrainageIssue={canApplyDrainageIssue}
                    getIssueGuidance={getIssueGuidance}
                    onApplyDrainageIssue={handleApplyDrainageIssue}
                    formatStageLabel={formatStageLabel}
                  />
                ) : null}

                {sidePanelForRender === "grading" ? (
                  <GradingWorkbenchPanel
                    hasTerrainSource={hasTerrainSource}
                    hasGradingSurface={hasGradingSurface}
                    siteTooLargeForGrading={siteTooLargeForGrading}
                    gradingStatus={systemStatuses.grading}
                    useSurveyForGrading={useSurveyForGrading}
                    onUseSurveyForGradingChange={setUseSurveyForGrading}
                    minSlopePct={minSlopePct}
                    maxParkingSlopePct={maxParkingSlopePct}
                    maxRoadGradePct={maxRoadGradePct}
                    maxAdaCrossSlopePct={maxAdaCrossSlopePct}
                    onMinSlopePctChange={setMinSlopePct}
                    onMaxParkingSlopePctChange={setMaxParkingSlopePct}
                    onMaxRoadGradePctChange={setMaxRoadGradePct}
                    onMaxAdaCrossSlopePctChange={setMaxAdaCrossSlopePct}
                    drainageAllowSlopeAdjust={drainageAllowSlopeAdjust}
                    onDrainageAllowSlopeAdjustChange={setDrainageAllowSlopeAdjust}
                    gradingEarthworkUx={gradingEarthworkUx}
                    missingSite={missingSite}
                    onOpenAnalysis={() => handleOpenSidePanel("analysis")}
                    onGenerateGrading={() => handleGenerateSystem("grading")}
                  />
                ) : null}

                {sidePanelForRender === "drainage" ? (
                  <DrainageWorkbenchPanel
                    hasBasinPlaced={hasBasinPlaced}
                    hasTerrainSource={hasTerrainSource}
                    hasHardSystemBlock={hasHardSystemBlock}
                    drainageStatus={systemStatuses.drainage}
                    drainageSourceOverride={drainageSourceOverride}
                    onDrainageSourceOverrideChange={setDrainageSourceOverride}
                    drainageConnectOrphans={drainageConnectOrphans}
                    onDrainageConnectOrphansChange={setDrainageConnectOrphans}
                    drainageAllowSlopeAdjust={drainageAllowSlopeAdjust}
                    onDrainageAllowSlopeAdjustChange={setDrainageAllowSlopeAdjust}
                    drainageMaxSlopeAdjust={drainageMaxSlopeAdjust}
                    onDrainageMaxSlopeAdjustChange={setDrainageMaxSlopeAdjust}
                    missingSite={missingSite}
                    onAddObject={handleAddObject}
                    onGenerateDrainage={() => handleGenerateSystem("drainage")}
                  />
                ) : null}
                {sidePanelForRender === "utilities" ? (
                  <UtilitiesWorkbenchPanel
                    hasHardSystemBlock={hasHardSystemBlock}
                    utilitiesStatus={systemStatuses.utilities}
                    drainageEnabled={drainage}
                    utilitiesEnabled={utilities}
                    pipeMinSlopePct={pipeMinSlopePct}
                    onUtilitiesChange={setUtilities}
                    onPipeMinSlopePctChange={setPipeMinSlopePct}
                    onOpenSanitary={() => handleOpenSidePanel("sanitary")}
                    onOpenWater={() => handleOpenSidePanel("water")}
                    onAddObject={handleAddObject}
                    onGenerateUtilities={() => handleGenerateSystem("utilities")}
                  />
                ) : null}

                {sidePanelForRender === "sanitary" ? (
                  <SanitaryWorkbenchPanel
                    hasHardSystemBlock={hasHardSystemBlock}
                    utilitiesStatus={systemStatuses.utilities}
                    utilitiesEnabled={utilities}
                    pipeMinSlopePct={pipeMinSlopePct}
                    buildingCoverageLabel={buildingPlacements.length ? `${confirmedObjectCounts.buildings} buildings` : "No buildings"}
                    onUtilitiesChange={setUtilities}
                    onPipeMinSlopePctChange={setPipeMinSlopePct}
                    onAddObject={handleAddObject}
                    onGenerateUtilities={() => handleGenerateSystem("utilities")}
                  />
                ) : null}
                {sidePanelForRender === "water" ? (
                  <WaterFireFlowWorkbenchPanel
                    hasHardSystemBlock={hasHardSystemBlock}
                    systemUtilitiesStatus={systemStatuses.utilities}
                    waterFireFlowReview={waterFireFlowReview}
                    buildingPlacements={buildingPlacements}
                    utilities={utilities}
                    onUtilitiesChange={setUtilities}
                    onAddObject={handleAddObject}
                    onGenerateUtilities={() => handleGenerateSystem("utilities")}
                  />
                ) : null}

                {sidePanelForRender.startsWith("system_") ? (
                  <SystemReadinessPanel
                    sidePanelForRender={sidePanelForRender as Extract<SidePanelKey, "system_grading" | "system_storm" | "system_sanitary" | "system_water" | "system_roadway" | "system_utilities" | "system_landscape">}
                    siteTooLargeForGrading={siteTooLargeForGrading}
                    systemStatuses={systemStatuses}
                    siteScaleLocked={siteScaleLocked}
                    hasTerrainSource={hasTerrainSource}
                    hasBasinPlaced={hasBasinPlaced}
                    hasHardSystemBlock={hasHardSystemBlock}
                    buildingPlacements={buildingPlacements}
                    utilities={utilities}
                    pipeMinSlopePct={pipeMinSlopePct}
                    roads={roads}
                    maxRoadGradePct={maxRoadGradePct}
                    stormHydrologyReview={stormHydrologyReview}
                    onOpenPanel={handleOpenSidePanel}
                  />
                ) : null}

                {sidePanelForRender === "roadway" ? (
                  <RoadwayWorkbenchPanel
                    activeCivil3DWorkflowTab={activeCivil3DWorkflowTab}
                    onCivil3DWorkflowTabChange={setActiveCivil3DWorkflowTab}
                    roadwayWorkbenchData={roadwayWorkbenchData}
                    gradingEarthworkUx={gradingEarthworkUx}
                    sourceConfidenceRows={sourceConfidenceRows}
                    civil3DWorkflowBlockers={civil3DWorkflowBlockers}
                    gradingSourceSummary={gradingSourceSummary}
                    hasTerrainSource={hasTerrainSource}
                    hasVerifiedSurveyControl={hasVerifiedSurveyControl}
                    onShowProfileControls={() => {
                      setActiveRoadwayWorkbenchTab("profile");
                    }}
                    roadsStatus={systemStatuses.roads}
                    parkingStatus={systemStatuses.parking}
                    maxRoadGradePct={maxRoadGradePct}
                    onMaxRoadGradePctChange={setMaxRoadGradePct}
                    parkingAngle={parkingAngle}
                    onParkingAngleChange={setParkingAngle}
                    roads={roads}
                    onRoadsChange={setRoads}
                    parkingLoading={parkingLoading}
                    onParkingLoadingChange={setParkingLoading}
                    parkingStallWidth={parkingStallWidth}
                    onParkingStallWidthChange={setParkingStallWidth}
                    parkingAisleWidth={parkingAisleWidth}
                    onParkingAisleWidthChange={setParkingAisleWidth}
                    parkingStallDepth={parkingStallDepth}
                    onParkingStallDepthChange={setParkingStallDepth}
                    parkingAdaCount={parkingAdaCount}
                    onParkingAdaCountChange={setParkingAdaCount}
                    parkingCompactCount={parkingCompactCount}
                    onParkingCompactCountChange={setParkingCompactCount}
                    parkingAdaAisleWidth={parkingAdaAisleWidth}
                    onParkingAdaAisleWidthChange={setParkingAdaAisleWidth}
                    parkingCompactWidth={parkingCompactWidth}
                    onParkingCompactWidthChange={setParkingCompactWidth}
                    activeRoadwayWorkbenchTab={activeRoadwayWorkbenchTab}
                    onRoadwayWorkbenchTabChange={setActiveRoadwayWorkbenchTab}
                    maxAdaCrossSlopePct={maxAdaCrossSlopePct}
                    onMaxAdaCrossSlopePctChange={setMaxAdaCrossSlopePct}
                    onAddObject={handleAddObject}
                    onGenerateSystem={handleGenerateSystem}
                  />
                ) : null}

                {sidePanelForRender === "landscape" ? (
                  <LandscapeWorkbenchPanel
                    buildingPlacements={buildingPlacements}
                    hasBackendResult={Boolean(backendResult)}
                    onAddObject={handleAddObject}
                  />
                ) : null}

                {sidePanelForRender === "details" ? (
                  <DashboardDetailsPanel
                    profileRows={[
                      { label: "Road profiles", value: roads ? "Review" : "No generated roads" },
                      { label: "Pipe profiles", value: utilities ? "Review" : "No generated pipes" },
                      { label: "Basin sections", value: hasBasinPlaced ? "Available" : "Needs basin" },
                      {
                        label: "ADA paths",
                        value: buildingPlacements.some((item) => item.type === "sidewalk") ? "Review" : "Needs paths",
                      },
                    ]}
                    selectedInspector={
                      <SelectedObjectInspectorPanel
                        selectedBuilding={selectedBuilding}
                        confidenceEntry={selectedBuilding ? sourceConfidenceByObjectId.get(selectedBuilding.id) : null}
                        objectManagerStatusMessage={objectManagerStatusMessage}
                        objectClipboardCount={objectClipboard.length}
                        displayType={selectedBuilding ? getObjectDisplayType(selectedBuilding) : ""}
                        reviewLabel={selectedBuilding ? getObjectReviewLabel(selectedBuilding) : ""}
                        sourceLabel={selectedBuilding ? getObjectSourceLabel(selectedBuilding) : ""}
                        layerLabel={selectedBuilding ? getObjectLayerLabel(selectedBuilding) : ""}
                        dimensionsLabel={selectedBuilding ? getObjectDimensionsLabel(selectedBuilding) : ""}
                        editableGeometry={selectedBuilding ? normalizeGeometryPoints(selectedBuilding.geometry) : undefined}
                        editBlocked={selectedBuilding ? Boolean(getObjectEditBlocker(selectedBuilding, "resize")) : false}
                        onRename={(item, value) => {
                          const blocker = getObjectEditBlocker(item, "rename");
                          if (blocker) {
                            reportObjectActionBlocker(blocker);
                            return;
                          }
                          handleUpdateBuilding(item.id, { label: value });
                        }}
                        onToggleLock={(item) => handleToggleBuildingLock(item.id)}
                        onToggleHidden={(item) =>
                          handleUpdateBuilding(item.id, {
                            meta: {
                              ...(item.meta ?? {}),
                              ui_hidden: !Boolean(item.meta?.ui_hidden),
                            },
                          })
                        }
                        onUpdateObject={(item, updates) => handleUpdateBuilding(item.id, updates)}
                        onUpdateVertex={handleUpdateObjectVertex}
                        onInsertVertex={handleInsertObjectVertex}
                        onDeleteVertex={handleDeleteObjectVertex}
                        onSnapVertex={handleSnapObjectVertexToNearestEndpoint}
                        onAlignVertex={handleAlignObjectVertexToPrevious}
                        onMove={(item) => {
                          handleObjectManagerSelect(item.id);
                          setPlacementModeEnabled(true);
                        }}
                        onFocus={(item) => {
                          setFocusObjectId(item.id);
                          setActiveSidePanel(null);
                        }}
                        onCopy={handleObjectManagerCopy}
                        onPaste={handleObjectManagerPaste}
                        onTransform={handleObjectManagerTransform}
                        onDelete={handleObjectManagerDelete}
                      />
                    }
                    objects={buildingPlacements}
                    activePlacementId={activePlacementId}
                    onSelectObject={setActivePlacementId}
                  />
                ) : null}

                {sidePanelForRender === "layers" ? (
                  <LayersPanel
                    layers={previewLayers}
                    onLayersChange={(updater) => setPreviewLayers((previous) => updater(previous) as typeof previous)}
                  />
                ) : null}

                {sidePanelForRender === "analysis" ? (
                  <AnalysisPanel
                    modelIssueCount={issues.length}
                    accessIssueCount={analysisIssues.length}
                    systemsCompleteCount={systemHealthItems.filter((item) => item.state === "complete").length}
                    blockedSystemCount={systemHealthItems.filter((item) => item.state === "blocked").length}
                    issues={[
                      ...issues.map((issue, index) => {
                        const applyLabel = drainageIssueApplyLabel(issue) ?? undefined;
                        return {
                          id: `issue-${index}`,
                          severity: issue.severity,
                          message: issue.message,
                          code: issue.code,
                          applyLabel,
                          canApply: applyLabel ? canApplyDrainageIssue(issue) : false,
                          onApply: applyLabel ? () => handleApplyDrainageIssue(issue) : undefined,
                        };
                      }),
                      ...analysisIssues.map((issue) => ({
                        id: issue.id,
                        message: issue.message,
                        severity: "warning" as const,
                      })),
                    ]}
                    onRunAccessAnalysis={handleAnalyzeSiteAccess}
                    onOpenDashboard={() => handleOpenSidePanel("dashboard")}
                  />
                ) : null}

                {sidePanelForRender === "files" ? (
                  <FilesPanel
                    mapSnapshotReady={Boolean(uploadedImageApiUrl || uploadedImagePreviewUrl)}
                    surveyFileName={surveyFileName}
                    projectRecordLabel={currentProject?.project_id || projectId || "Draft"}
                    surveyUploadMessage={surveyUploadMessage}
                    previewReady={Boolean(planPreviewUrl)}
                    reportReady={Boolean(backendResult)}
                    dxfStatus={getExportBlockReason() || (backendResult ? "Review export" : "Needs run")}
                    onOpenImportFiles={() => handleOpenSidePanel("import_survey")}
                    onSelectMapImage={() => mapSnapshotInputRef.current?.click()}
                    onSelectSurveyFile={() => surveyInputRef.current?.click()}
                    onOpenPlanPdf={() => handleOpenSidePanel("data")}
                    onExportDxf={handleExportDxf}
                    onExportReport={handleExportReport}
                    exportBlockReason={getExportBlockReason()}
                  />
                ) : null}

                {sidePanelForRender === "jobs" ? (
                  <JobsPanel
                    activeJob={visibleActiveJob}
                    selectedJob={selectedJob}
                    jobHistory={jobHistory}
                    jobStatusCounts={jobStatusCounts}
                    artifactHistory={artifactHistory}
                    activeJobStale={visibleActiveJobStale}
                    selectedJobStale={selectedJobStale}
                    statusMessage={jobsPanelStatusMessage}
                    formatTimestamp={formatTimestamp}
                    toReadableLabel={toReadableLabel}
                    jobDetailMessage={jobDetailMessage}
                    onRefresh={() => {
                      if (!token) {
                        setJobsPanelStatusMessage("Sign in/connect backend to refresh jobs.");
                        return;
                      }
                      void refreshJobs(token, { force: true })
                        .then(() => setJobsPanelStatusMessage("Jobs refreshed."))
                        .catch((error) => {
                          const message = `Job refresh failed: ${panelErrorMessage(error, "Could not refresh job history.")}`;
                          setJobsPanelStatusMessage(message);
                          setStatusMessage(message);
                        });
                    }}
                    onSelectJob={handleSelectJob}
                    onCancelJob={(jobId) => void handleCancelJobById(jobId)}
                    onRetryJob={(jobId) => void handleRetryJob(jobId)}
                    onResumeJob={(jobId) => void handleResumeJob(jobId)}
                    onDownloadArtifact={(downloadPath, filename) => void handleArtifactDownload(downloadPath, filename)}
                  />
                ) : null}

                {sidePanelForRender === "templates" ? (
                  <TemplatesPanel
                    registry={customerTemplates}
                    status={customerTemplateStatus}
                    summaries={customerTemplateSummaries}
                    activeTemplate={activeCustomerTemplate}
                    blockerCount={customerTemplateBlockerCount}
                    toReadableLabel={toReadableLabel}
                    onUseCompanyTemplate={() => {
                      if (!token) return;
                      void postJson<Record<string, unknown>>("/api/customer-templates/activate", { template_id: "" }, { token })
                        .then((result) => {
                          const registry = result.registry as CustomerTemplateRegistryResponse | undefined;
                          if (registry) setCustomerTemplates(registry);
                          setCustomerTemplateStatus("Company template activated");
                        })
                        .catch((error) => setCustomerTemplateStatus(error instanceof Error ? error.message : "Template activation failed"));
                    }}
                    onExportJson={() => {
                      if (!token) return;
                      void getJson<Record<string, unknown>>("/api/customer-templates/export", { token })
                        .then(() => setCustomerTemplateStatus("Template JSON export prepared"))
                        .catch((error) => setCustomerTemplateStatus(error instanceof Error ? error.message : "Template export failed"));
                    }}
                    onActivateTemplate={(item) => {
                      if (!token || !item.template_id) return;
                      void postJson<Record<string, unknown>>("/api/customer-templates/activate", { template_id: item.template_id }, { token })
                        .then((result) => {
                          const registry = result.registry as CustomerTemplateRegistryResponse | undefined;
                          if (registry) setCustomerTemplates(registry);
                          setCustomerTemplateStatus(`${item.name || "Template"} activated`);
                        })
                        .catch((error) => setCustomerTemplateStatus(error instanceof Error ? error.message : "Template activation failed"));
                    }}
                  />
                ) : null}

                {sidePanelForRender === "catalogs" ? (
                  <UtilityCatalogPanel
                    catalog={utilityCatalog}
                    status={utilityCatalogStatus}
                    networkFilter={utilityCatalogNetworkFilter}
                    onNetworkFilterChange={setUtilityCatalogNetworkFilter}
                  />
                ) : null}

                {sidePanelForRender === "standards" ? (
                  <StandardsPanel
                    criteria={standardsPanelCriteria}
                    rows={standardsPanelRows}
                    onOpenSourceData={() => handleOpenSidePanel("data")}
                    onOpenReviewGates={() => handleOpenSidePanel("reports")}
                  />
                ) : null}

                {sidePanelForRender === "libraries" ? (
                  <LibrariesPanel
                    sections={libraryPanelSections}
                    onAddObject={(type) => handleAddObject(type as SiteObjectType)}
                  />
                ) : null}

                {sidePanelForRender === "settings" ? (
                  <WorkspaceSettingsPanel
                    previewQuality={previewQuality}
                    leftSidebarOpen={leftSidebarOpen}
                    assistedEnabled={assistedEnabled}
                    releaseStatus={sidebarReleaseStatus}
                    standardsStatus={panelStatus("standards")}
                    disciplineToggles={disciplineToggles}
                    onOpenStandards={() => handleOpenSidePanel("standards")}
                    onOpenDeliverables={() => handleOpenSidePanel("deliverables")}
                  />
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
                    setRightRailCollapsed={setRightRailCollapsed}
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
                  <DeliverPanel
                    reviewPackageFlowSummary={reviewPackageFlowSummary}
                    planPreviewUrl={planPreviewUrl}
                    hasBackendResult={Boolean(backendResult)}
                    placedObjectCount={placedObjectCount}
                    sidebarTrustScore={sidebarTrustScore}
                    exportActionMessage={exportActionMessage}
                    exportBlockReason={getExportBlockReason() || ""}
                    planSheetSet={planSheetSet}
                    planSheetBlockers={getPlanSheetBlockers()}
                    projectName={siteName || currentProject?.name || "Untitled Project"}
                    addressLabel={appliedAddressLabel || siteAddress.trim() || "No address applied"}
                    lotWidth={parsePositiveNumber(lotWidth) ?? lotBounds.w ?? 0}
                    lotHeight={parsePositiveNumber(lotHeight) ?? lotBounds.h ?? 0}
                    placements={buildingPlacements}
                    autoSiteContextFlowSummary={autoSiteContextFlowSummary}
                    sidebarReleaseStatus={sidebarReleaseStatus}
                    reviewGateItems={reviewGateItems}
                    topSmartFix={topSmartFix}
                    onMakeReviewPackage={handleMakeReviewPackage}
                    onPlanSheetExportPdf={handlePlanSheetExportPdf}
                    onExportDxf={handleExportDxf}
                    onExportReport={handleExportReport}
                    onOpenQuantities={() => handleOpenSidePanel("quantities")}
                    onPlanSheetTitleBlockUpdate={handlePlanSheetTitleBlockUpdate}
                    onPlanSheetScaleChange={handlePlanSheetScaleChange}
                    onPlanSheetViewportUpdate={handlePlanSheetViewportUpdate}
                    onPlanSheetViewportDelete={handlePlanSheetViewportDelete}
                    onPlanSheetAddNote={handlePlanSheetAddNote}
                    onPlanSheetAddLabel={() => {
                      addPlanSheetAnnotation("label", "New sheet label");
                      setStatusMessage("Added a sheet label.");
                    }}
                    onPlanSheetAddCallout={() => {
                      addPlanSheetAnnotation("callout", "Review callout");
                      setStatusMessage("Added a sheet callout.");
                    }}
                    onPlanSheetAddDimension={() => {
                      addPlanSheetAnnotation("dimension", "Dimension reference");
                      setStatusMessage("Added a dimension note.");
                    }}
                    onPlanSheetAddViewport={handlePlanSheetAddViewport}
                    onPlanSheetViewportLayerToggle={handlePlanSheetViewportLayerToggle}
                    onPlanSheetViewportScaleLockToggle={handlePlanSheetViewportScaleLockToggle}
                    onPlanSheetGrayscaleToggle={handlePlanSheetGrayscaleToggle}
                    onPlanSheetAddRevision={() => handlePlanSheetAddRevision()}
                    onPlanSheetAddTable={handlePlanSheetAddTable}
                    onPlanSheetAddDetailBlock={handlePlanSheetAddDetailBlock}
                    onPlanSheetAddReference={handlePlanSheetAddReference}
                    onPlanSheetSelectSheet={(sheetId) => {
                      setPlanSheetSet((current) => ({
                        ...current,
                        activeSheetId: sheetId,
                        updatedAt: new Date().toISOString(),
                      }));
                    }}
                    onCreateReviewSheet={handleCreateReviewSheet}
                    onPlanSheetExportJson={handlePlanSheetExportJson}
                    onSmartFixAction={handleSmartFixAction}
                  />
                ) : null}

                {sidePanelForRender === "reports" || sidePanelForRender === "quantities" ? (
                  <DashboardReportsQuantitiesPanel
                    activePanel={sidePanelForRender}
                    reports={{
                      stats: [
                        { label: "QA items", value: issues.length + analysisIssues.length },
                        { label: "Missing", value: sidebarMissingInputs.length },
                        { label: "Assumptions", value: sidebarAssumptions.length },
                        { label: "Needs input", value: systemHealthItems.filter((item) => item.state === "blocked").length },
                      ],
                      engineeringHealthLinks: engineeringHealthPanelLinks,
                      issues,
                      drainageIssueApplyLabel,
                      canApplyDrainageIssue,
                      getIssueGuidance,
                      onApplyDrainageIssue: handleApplyDrainageIssue,
                      onOpenSidePanel: handleOpenSidePanel,
                      reviewIssueTracker: {
                        issues: reviewIssueItems,
                        openIssueCount: openReviewIssueItems.length,
                        totalIssueCount: reviewIssueTracker.issue_count ?? reviewIssueItems.length,
                        needsReviewCount: reviewIssueTracker.needs_review_count ?? 0,
                        drainageIssueCount: drainageReviewIssueItems.length,
                        waivedCount: reviewIssueTracker.by_status?.waived_review_required ?? 0,
                        truthLabel: reviewIssueTracker.truth_label,
                        onAskCommand: (command) => {
                          setPrompt(command);
                          handleOpenSidePanel("chat");
                        },
                        onIssueCommand: (action, issueId) => {
                          setPrompt(`${action} issue ${issueId}`);
                          handleOpenSidePanel("chat");
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
                        onAction: (action, optionNumber) => void handleDesignAlternativesAction(action, optionNumber),
                      },
                      sourceConfidence: {
                        summary: sourceConfidenceSummary,
                        entries: sourceConfidenceRows,
                        totalEntryCount: sourceConfidenceEntries.length,
                      },
                    }}
                    quantities={{
                      rows: quantityRows,
                      staleSystemCount: sidebarStaleSystems.length,
                      trustScoreLabel: sidebarTrustScore,
                      onExportReport: handleExportQuantityReviewReport,
                      formatMetric,
                      statusLabelForQuantityReview,
                    }}
                  />
                ) : null}

                {sidePanelForRender === "chat" ? (
                  <ChatPanel
                    chatMessages={chatMessages}
                    chatScrollRef={chatScrollRef}
                    onSetMessageFeedback={setMessageFeedback}
                    thinkingState={thinkingState}
                    busy={busy}
                    activePlanTool={activePlanTool}
                    visibleActiveJobStatus={visibleActiveJob?.status ?? ""}
                    hasDirectRunInFlight={Boolean(directRunAbortRef.current)}
                    onCancelJob={handleCancelActiveJob}
                    onContinueJob={handleContinueActiveJob}
                    pendingClarification={pendingClarification?.question || null}
                    onContinuePendingClarification={handleContinuePendingClarification}
                    prompt={prompt}
                    imageName={imageName}
                    onPromptChange={setPrompt}
                    onPromptKeyDown={handlePromptKeyDown}
                    onSendMessage={handleSendMessage}
                    onUploadImage={uploadImage}
                    onExplainPlan={() => void handleExplainPlan()}
                    onRunFix={() => void handleRunFix()}
                    onRunImprove={() => void handleRunImprove()}
                    onSaveProject={() => void saveProject()}
                    canExplain={Boolean(planPreviewUrl)}
                    statusMessage={statusMessage}
                    hasVisibleActiveJob={Boolean(visibleActiveJob)}
                    approvalState={approvalStatus.state}
                    approvalPhaseLabel={approvalStatus.label}
                    approvalError={approvalError}
                    collapsed={false}
                    onToggleCollapsed={handleCloseSidePanel}
                    summaryText={chatSummary}
                  />
                ) : null}
            </WorkspaceRightPanel>
          ) : null}
          <WorkspaceCanvasArea
            siteScaleLocked={siteScaleLocked}
            workspaceChromeHidden={workspaceChromeHidden}
            sidebarVisible={sidebarVisible}
            rightRailCollapsed={rightRailCollapsed}
            sidePanelForRender={sidePanelForRender}
            projectName={siteName || currentProject?.name || "Untitled Project"}
            activeWorkflowKey={activePrimaryWorkflowKey}
            workflowItems={primaryWorkflowItems}
            toolbarTools={contextualToolbarTools}
            previewMode={previewMode}
            previewQuality={previewQuality}
            layerManagerOpen={layerManagerOpen}
            previewLayers={previewLayers}
            selectedBuilding={selectedBuilding}
            selectedObjectConfidence={selectedObjectConfidence}
            moveEditFeedback={moveEditFeedback}
            previewInteraction={previewInteraction}
            denseConceptActive={denseConceptActive}
            sidePanelVisible={sidePanelVisible}
            denseConceptObjectCount={denseConceptObjectCount}
            onOpenPanel={handleOpenPanelFromDrawer}
            onMinimizeChrome={() => setWorkspaceChromeMinimized(true)}
            onPreviewModeSelect={handleSetPreviewMode}
            onPreviewQualitySelect={handleSetPreviewQuality}
            onSetRightRailCollapsed={setRightRailCollapsed}
            onCloseLayerManager={() => setLayerManagerOpen(false)}
            onApplyLayerPreset={setPreviewLayers}
            onToggleLayer={(key, visible) => setPreviewLayers((prev) => ({ ...prev, [key]: visible }))}
            onEditSelectedObject={handleEditFloatingSelectedObject}
            onFocusSelectedObject={handleFocusFloatingSelectedObject}
            onOpenSelectedObjectDetails={handleOpenFloatingObjectDetails}
            previewPanelProps={{
              previewReview,
              onRefreshPreview: handlePreviewPlan,
              busy,
              planPreviewUrl,
              planPreviewProjectId,
              currentProjectId: projectId || currentProject?.project_id || null,
              previewMode,
              previewInteraction: canvasPreviewInteraction,
              previewQuality,
              systemStatuses,
              hasTerrainSource,
              hasBasinPlaced,
              siteTooLargeForGrading,
              hasHardSystemBlock,
              hasGeneratedPlan: Boolean(planPreviewUrl && backendResult),
              placementMode: placementModeEnabled || Boolean(activePlacementId),
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
              selectedBuildingId: activePlacementId,
              selectedObjectIds,
              focusDetectedId,
              onClearFocusDetected: () => setFocusDetectedId(null),
              focusObjectId,
              onClearFocusObject: () => setFocusObjectId(null),
              lotWidth: lotBounds.w,
              lotHeight: lotBounds.h,
              onViewportFootprint: handleViewportFootprint,
              onUpdateBuilding: handleUpdateBuilding,
              onUpdateSuggested: (id, updates) => {
                setDetectedPlacements((prev) => {
                  const nextDetected = prev.map((item) =>
                    item.id === id ? { ...item, ...updates } : item,
                  );
                  persistDetectedPlacements(nextDetected);
                  return nextDetected;
                });
              },
              analysisPaths,
              analysisHighlight: selectedAccessIssue
                ? {
                    buildingId: selectedAccessIssue.buildingId,
                    accessId: selectedAccessIssue.accessId,
                    pathId: selectedAccessIssue.pathId,
                  }
                : null,
              analysisFocusLocked,
              onClearHighlights: () => {
                setAnalysisSelectedIssueId(null);
                setAnalysisFocusLocked(false);
              },
              onResetView: () => {
                setAnalysisSelectedIssueId(null);
                setFocusDetectedId(null);
                setAnalysisFocusLocked(false);
              },
              onRemoveBuilding: handleRemoveBuilding,
              onRestoreBuilding: handleRestoreBuilding,
              onSelectBuilding: setActivePlacementId,
              onSelectObjects: setSelectedObjectIds,
              onSetPreviewMode: handleSetPreviewMode,
              onSetPreviewInteraction: setPreviewInteraction,
              onSetPreviewQuality: handleSetPreviewQuality,
              onAiRealismChange: (event) => {
                recordRecentChange({
                  type: "ai_realism_recorded",
                  label:
                    event.type === "generated"
                      ? "AI realism regenerated"
                      : event.type === "stale"
                        ? "AI realism stale"
                        : "AI realism blocked",
                  detail: event.detail,
                  undoBlockedReason: "AI realism is a visual preview record. Regenerate from the current review layout instead of undoing it.",
                });
                pushRecoveryMessage(`${event.detail} AI realism remains visual preview only.`);
              },
              previewRefreshing,
              previewRefreshNote,
              preview3DEffectiveItems,
              usingAnnotation3D,
              hasGradingSurface,
              onOpenFullscreen: () => setPreviewFullscreenOpen(true),
              previewFullscreenOpen,
              onCloseFullscreen: () => setPreviewFullscreenOpen(false),
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
              onSetSiteRotationDeg: (value) => {
                setSiteRotationDeg(value);
                setSiteRotationInput(String(value));
                scheduleRotationSave(value);
              },
              surveyPoints: surveyPreviewPoints,
              onMapScaleUpdate: ({ ftPerPx, source }) => {
                if (siteScaleLocked) return;
                if (!Number.isFinite(ftPerPx) || ftPerPx <= 0) return;
                setDetectionScaleFtPerPx(ftPerPx);
                setDetectionScaleSource(source);
                scheduleScaleSave(ftPerPx, source);
              },
              debugStats: {
                enabled: mapDebugOverlay,
                projectId: projectId || currentProject?.project_id || "",
                canonicalCount: buildingPlacements.length,
                placedCount: placedObjectCount,
                previewImageActive: Boolean(planPreviewUrl),
                placementMode: placementModeEnabled || Boolean(activePlacementId),
                selectedId: activePlacementId,
              },
              cadToolRequest,
            }}
          />
          {shortcutsOverlayOpen ? (
            <WorkspaceShortcutsOverlay
              shortcuts={supportedShortcuts}
              onClose={() => setShortcutsOverlayOpen(false)}
            />
          ) : null}
          {commandBarVisible ? (
            <PinnedCommandBar
              prompt={prompt}
              imageName={imageName}
              onPromptChange={setPrompt}
              onPromptKeyDown={handlePromptKeyDown}
              commandInputRef={commandInputRef}
              onSendMessage={handleSendMessage}
              onOpenHistory={() => handleOpenSidePanel("chat")}
              busy={busy}
              hasVisibleActiveJob={chatBlockingActiveJob}
              activePlanTool={activePlanTool}
              thinkingState={thinkingState}
              statusText={chatSummary || formatProjectStatusText(projectStatusSummary) || statusMessage}
              commandContext={{
                mode: activePrimaryWorkflowKey,
                interaction: previewInteraction,
                layer: activePlacementId ? "selected" : "C-DRAFT",
                selectedCount: activePlacementId ? 1 : 0,
                snap: "ready",
                view: `${previewMode.toUpperCase()} / ${previewQuality}`,
              }}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function PerformanceAIDashboard() {
  return <PerformanceAIDashboardView />;
}
