"use client";
/* eslint-disable react-hooks/exhaustive-deps */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { deleteJson, getJson, postBinary, postForm, postJson } from "../lib/api";

import type {
  Assumption,
  Issue,
  BackendAssumption,
  BackendIssue,
  ManualFields,
  ProjectRecord,
  ProjectInput,
  JobSummary,
  WorkflowRunSummary,
  ManualFailure,
  ManagerMetrics,
  QuantityTotals,
  PipeSegment,
  StormSummary,
  PlanExplanation,
  PlanMeta,
  PlanResponse,
  SurveySlopeResponse,
  SurveyPointsResponse,
  ImageDetectResponse,
  MapAnalysis,
  PreviewResponse,
  UploadImageResponse,
  UploadSurveyResponse,
  PlanToolMode,
  ControlOverrides,
  BuildingPlacement,
  SiteObjectType,
  ChatDecisionResponse,
  ChatMessage,
  DisciplineToggle,
  Preview3DItem,
  PlanRequestPayload,
  PreviewRequestPayload,
  SiteInputs,
} from "./types";

const ADD_MENU_SECTIONS: Array<{
  title: string;
  key: string;
  items: SiteObjectType[];
  collapsible?: boolean;
}> = [
  {
    title: "Site",
    key: "site",
    items: ["site", "setback_zone", "no_build_zone"],
  },
  {
    title: "Buildings & Program",
    key: "buildings",
    items: [
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "amenity",
      "open_space",
    ],
  },
  {
    title: "Access & Parking",
    key: "access",
    items: ["entrance", "driveway", "road", "parking", "sidewalk"],
  },
  {
    title: "Drainage & Water",
    key: "drainage",
    items: ["basin", "outfall", "inlet", "manhole", "hydrant"],
  },
  {
    title: "Advanced",
    key: "advanced",
    items: ["utility_corridor", "lot_block", "bridge"],
    collapsible: true,
  },
];

const SITE_OBJECT_CATALOG: Record<
  SiteObjectType,
  { label: string; category: string; defaultW: number; defaultD: number; defaultH?: number; use?: string }
> = {
  site: { label: "Site", category: "site", defaultW: 400, defaultD: 300 },
  setback_zone: { label: "Setback Zone", category: "site", defaultW: 200, defaultD: 120 },
  no_build_zone: { label: "No-Build Zone", category: "site", defaultW: 160, defaultD: 120 },
  building: { label: "Building", category: "buildings", defaultW: 80, defaultD: 50, defaultH: 30 },
  retail_building: {
    label: "Retail Building",
    category: "buildings",
    defaultW: 70,
    defaultD: 45,
    defaultH: 24,
    use: "retail",
  },
  multifamily_building: {
    label: "Multifamily Building",
    category: "buildings",
    defaultW: 110,
    defaultD: 58,
    defaultH: 36,
    use: "multifamily",
  },
  industrial_building: {
    label: "Industrial Building",
    category: "buildings",
    defaultW: 140,
    defaultD: 90,
    defaultH: 36,
    use: "industrial",
  },
  office_building: {
    label: "Office Building",
    category: "buildings",
    defaultW: 100,
    defaultD: 60,
    defaultH: 30,
    use: "office",
  },
  pad: { label: "Pad", category: "buildings", defaultW: 60, defaultD: 40, defaultH: 4 },
  pool: { label: "Pool", category: "buildings", defaultW: 50, defaultD: 30, defaultH: 6 },
  amenity: { label: "Amenity Area", category: "buildings", defaultW: 80, defaultD: 40, defaultH: 12 },
  open_space: { label: "Open Space", category: "buildings", defaultW: 120, defaultD: 80, defaultH: 0 },
  entrance: { label: "Entrance / Access", category: "access", defaultW: 24, defaultD: 24 },
  driveway: { label: "Driveway", category: "access", defaultW: 60, defaultD: 16 },
  road: { label: "Road / Drive Aisle", category: "access", defaultW: 120, defaultD: 28 },
  parking: { label: "Parking Field", category: "access", defaultW: 140, defaultD: 60 },
  sidewalk: { label: "Sidewalk / Path", category: "access", defaultW: 80, defaultD: 12 },
  basin: { label: "Basin / Detention Pond", category: "drainage", defaultW: 90, defaultD: 60 },
  outfall: { label: "Outfall Point", category: "drainage", defaultW: 18, defaultD: 18 },
  inlet: { label: "Inlet", category: "drainage", defaultW: 12, defaultD: 12 },
  manhole: { label: "Manhole", category: "drainage", defaultW: 12, defaultD: 12 },
  hydrant: { label: "Hydrant", category: "drainage", defaultW: 10, defaultD: 10 },
  utility_corridor: { label: "Utility Corridor", category: "advanced", defaultW: 140, defaultD: 24 },
  lot_block: { label: "Lot / Subdivision Block", category: "advanced", defaultW: 160, defaultD: 120 },
  bridge: { label: "Bridge", category: "advanced", defaultW: 80, defaultD: 24 },
};

const clampValue = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

type SystemStatus = "fresh" | "stale" | "not_generated";

const DEFAULT_SYSTEM_STATUS: Record<
  "roads" | "parking" | "grading" | "drainage" | "utilities",
  SystemStatus
> = {
  roads: "not_generated",
  parking: "not_generated",
  grading: "not_generated",
  drainage: "not_generated",
  utilities: "not_generated",
};

import {
  defaultAssumptions,
  toReadableLabel,
  joinNatural,
  toArray,
  readPositiveNumber,
  parsePositiveNumber,
  readMetricValue,
  formatMetric,
  summarizePlanResponse,
} from "./utils/formatting";

import {
  createChatMessage,
  createWelcomeMessage,
  extractDesignMemory,
  getChatThreadStorageKey,
} from "./utils/chat";

import { uploadedImageSrc } from "./utils/auth";

import AppHeader from "./components/AppHeader";
import AuthScreen from "./components/AuthScreen";
import WorkspaceToolbar from "./components/WorkspaceToolbar";
import ChatPanel from "./components/ChatPanel";
import PreviewPanel from "./components/PreviewPanel";
import ProjectControls from "./components/ProjectControls";
import useChatPersistence from "./hooks/useChatPersistence";
import usePreviewReview from "./hooks/usePreviewReview";
import useJobPolling from "./hooks/useJobPolling";
import useAuthState from "./hooks/useAuthState";
import useProjectsState from "./hooks/useProjectsState";
import useJobsState from "./hooks/useJobsState";

function formatTimestamp(value?: number): string {
  if (!value) return "Unknown time";
  try {
    return new Date(value * 1000).toLocaleString();
  } catch {
    return "Unknown time";
  }
}

function isLikelyStaleJob(job: JobSummary | null, nowMs: number): boolean {
  if (!job?.updated_at) return false;
  const status = String(job.status || "").toLowerCase();
  if (!["queued", "running", "cancelling"].includes(status)) {
    return false;
  }
  const updatedAtMs = Number(job.updated_at) * 1000;
  if (!Number.isFinite(updatedAtMs) || updatedAtMs <= 0) {
    return false;
  }
  const staleThresholdMs = status === "queued" ? 90_000 : 60_000;
  return nowMs - updatedAtMs > staleThresholdMs;
}

type ApprovalState = "idle" | "approving" | "starting";

function buildThinkingState({
  busy,
  activePlanTool,
  activeJobStatus,
  activeJobStage,
  activeJobDetail,
  activeJobProgress,
  activeJobUpdatedAt,
  activeJobQueuePosition,
  activeJobQueuedCount,
  activeJobRunningCount,
  staleJob,
  statusMessage,
}: {
  busy: boolean;
  activePlanTool: PlanToolMode;
  activeJobStatus?: string;
  activeJobStage?: string;
  activeJobDetail?: string;
  activeJobProgress?: number;
  activeJobUpdatedAt?: number;
  activeJobQueuePosition?: number | null;
  activeJobQueuedCount?: number;
  activeJobRunningCount?: number;
  staleJob?: boolean;
  statusMessage: string;
}) {
  const normalizedJobStatus = String(activeJobStatus || "").trim().toLowerCase();
  const normalizedStatus = statusMessage.toLowerCase();
  const stageLabel = String(activeJobStage || "").trim();
  const stageDetail = String(activeJobDetail || "").trim();
  const numericProgress =
    typeof activeJobProgress === "number" && Number.isFinite(activeJobProgress)
      ? Math.max(0, Math.min(100, Math.round(activeJobProgress)))
      : null;
  const lastUpdateText =
    activeJobUpdatedAt && Number.isFinite(activeJobUpdatedAt)
      ? `Last backend update: ${formatTimestamp(activeJobUpdatedAt)}.`
      : "";
  const queuePosition =
    typeof activeJobQueuePosition === "number" && Number.isFinite(activeJobQueuePosition)
      ? Math.max(1, Math.round(activeJobQueuePosition))
      : null;
  const queuedCount =
    typeof activeJobQueuedCount === "number" && Number.isFinite(activeJobQueuedCount)
      ? Math.max(0, Math.round(activeJobQueuedCount))
      : 0;
  const runningCount =
    typeof activeJobRunningCount === "number" && Number.isFinite(activeJobRunningCount)
      ? Math.max(0, Math.round(activeJobRunningCount))
      : 0;
  const queueDetail = queuePosition
    ? `Civora queued the run. Queue position: ${queuePosition}${queuedCount > 0 ? ` of ${queuedCount}` : ""}. ${runningCount > 0 ? `${runningCount} worker${runningCount === 1 ? "" : "s"} active.` : ""}`.trim()
    : "Civora queued the run and is waiting for a worker to pick it up.";

  if (normalizedJobStatus && staleJob) {
    return {
      label: normalizedJobStatus === "queued" ? "Queue Delayed" : "Check Run Status",
      detail:
        stageDetail ||
        `Civora has not received a fresh backend update for this ${normalizedJobStatus} job recently. ${lastUpdateText}`.trim(),
      progress:
        numericProgress ??
        (normalizedJobStatus === "queued" ? 18 : normalizedJobStatus === "cancelling" ? 68 : 72),
    };
  }

  if (normalizedJobStatus && stageLabel) {
    return {
      label: stageLabel,
      detail:
        stageDetail ||
        (normalizedJobStatus === "queued"
          ? queueDetail
          : "Civora is processing the design in the background now."),
      progress: numericProgress ?? (normalizedJobStatus === "queued" ? 12 : 48),
    };
  }

  if (normalizedJobStatus === "queued") {
    return {
      label: "Queued",
      detail: queueDetail,
      progress: 18,
    };
  }
  if (normalizedJobStatus === "awaiting_approval") {
    return {
      label: stageLabel || "Awaiting Approval",
      detail:
        stageDetail ||
        "Civora saved the current phase result and is waiting for your approval to continue.",
      progress: numericProgress ?? 60,
    };
  }
  if (normalizedJobStatus === "running") {
    return {
      label: "Running",
      detail: "Civora is processing the design in the background now.",
      progress: 68,
    };
  }
  if (normalizedJobStatus === "cancelling") {
    return {
      label: "Cancelling",
      detail:
        stageDetail ||
        "Civora is stopping the background run and cleaning up the active job.",
      progress: numericProgress ?? 68,
    };
  }
  if (busy && activePlanTool === "fix") {
    return {
      label: "Fixing",
      detail: "Applying a focused fix pass to the active design.",
      progress: 62,
    };
  }
  if (busy && activePlanTool === "improve") {
    return {
      label: "Improving",
      detail: "Improving the current design while preserving the main intent.",
      progress: 62,
    };
  }
  if (busy && normalizedStatus.includes("reviewing your request")) {
    return {
      label: "Reading Request",
      detail: "Reviewing your prompt and preparing the run.",
      progress: 22,
    };
  }
  if (busy && normalizedStatus.includes("starting the engineering run")) {
    return {
      label: "Engineering Run",
      detail: "Starting the core design pipeline and waiting for the first engineering result.",
      progress: 34,
    };
  }
  return {
    label: "Thinking",
    detail:
      statusMessage ||
      "Civora is building the design, checking engineering constraints, and preparing the next result.",
    progress: 42,
  };
}

export default function PerformanceAIDashboard() {
  const [projectType, setProjectType] = useState("");
  const [units, setUnits] = useState("ft");
  const [prompt, setPrompt] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [
    createWelcomeMessage(),
  ]);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [activeSidePanel, setActiveSidePanel] = useState<"projects" | "docs" | "chat" | "site" | null>(null);
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
  const [minSlopePct, setMinSlopePct] = useState("");
  const [pipeMinSlopePct, setPipeMinSlopePct] = useState("");
  const [maxParkingSlopePct, setMaxParkingSlopePct] = useState("");
  const [maxRoadGradePct, setMaxRoadGradePct] = useState("");
  const [maxAdaCrossSlopePct, setMaxAdaCrossSlopePct] = useState("");
  const [roads, setRoads] = useState(true);
  const [grading, setGrading] = useState(true);
  const [drainage, setDrainage] = useState(true);
  const [drainageForcedInlets, setDrainageForcedInlets] = useState<
    Array<{ x: number; y: number; name?: string }>
  >([]);
  const [drainageConnectOrphans, setDrainageConnectOrphans] = useState(false);
  const [drainageAllowSlopeAdjust, setDrainageAllowSlopeAdjust] = useState(false);
  const [drainageMaxSlopeAdjust, setDrainageMaxSlopeAdjust] = useState(0.001);
  const [utilities, setUtilities] = useState(true);
  const [buildingPlacements, setBuildingPlacements] = useState<BuildingPlacement[]>([]);
  const [placementModeEnabled, setPlacementModeEnabled] = useState(false);
  const [activePlacementId, setActivePlacementId] = useState<string | null>(null);
  const [placementSuggestions, setPlacementSuggestions] = useState<BuildingPlacement[][]>([]);
  const [advancedAddOpen, setAdvancedAddOpen] = useState(false);
  const [systemStatuses, setSystemStatuses] = useState(DEFAULT_SYSTEM_STATUS);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0);

  const [assumptions, setAssumptions] =
    useState<Assumption[]>(defaultAssumptions);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [backendResult, setBackendResult] = useState<PlanResponse | null>(null);
  const [uploadedImagePreviewUrl, setUploadedImagePreviewUrl] = useState("");
  const [uploadedImageApiUrl, setUploadedImageApiUrl] = useState("");
  const [surveyFileName, setSurveyFileName] = useState("");
  const [surveySlopeEstimate, setSurveySlopeEstimate] = useState<SurveySlopeResponse | null>(null);
  const [surveyPoints, setSurveyPoints] = useState<number[][]>([]);
  const [surveyDiagnostics, setSurveyDiagnostics] = useState<{
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
  const [showAdvancedCalibration, setShowAdvancedCalibration] = useState(false);
  const [siteRotationDeg, setSiteRotationDeg] = useState(0);
  const [siteRotationInput, setSiteRotationInput] = useState("0");
  const [showSiteBounds, setShowSiteBounds] = useState(true);
  const [fitToSiteRequest, setFitToSiteRequest] = useState(0);
  const [mapCenterRequest, setMapCenterRequest] = useState(0);
  const [alignToRoadRequest, setAlignToRoadRequest] = useState(0);
  const debugPreview = useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.location.search.includes("debugPreview=1");
  }, []);
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
  const [analysisEmptyReason, setAnalysisEmptyReason] = useState<string | null>(null);
  const [externalRectUndo, setExternalRectUndo] = useState<{
    id: string;
    snapshot: BuildingPlacement;
    action: "update" | "delete" | "add";
    ts: number;
  } | null>(null);
  const [detectionConfidenceFilter, setDetectionConfidenceFilter] = useState<"high" | "medium" | "all">("all");
  const [mapSnapshotPath, setMapSnapshotPath] = useState("");
  const [mapAnalysis, setMapAnalysis] = useState<MapAnalysis | null>(null);
  const [siteAddress, setSiteAddress] = useState("");
  const [imageUploadState, setImageUploadState] = useState<"idle" | "uploading" | "uploaded" | "detecting" | "failed">("idle");
  const [imageUploadNote, setImageUploadNote] = useState<string | null>(null);
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
  const [previewMode, setPreviewMode] = useState<"2d" | "3d">("2d");
  const [previewInteraction, setPreviewInteraction] = useState<"static" | "interactive">("interactive");
  const [previewQuality, setPreviewQuality] = useState<"standard" | "high">("standard");
  const [previewLabelDensity, setPreviewLabelDensity] = useState<"low" | "standard" | "high">("standard");
  const [previewLabelDensityTouched, setPreviewLabelDensityTouched] = useState(false);
  const [previewHeightPx, setPreviewHeightPx] = useState(560);
  const [previewRefreshing, setPreviewRefreshing] = useState(false);
  const [previewRefreshNote, setPreviewRefreshNote] = useState<string | null>(null);
  const [approvalInFlight, setApprovalInFlight] = useState(false);
  const [approvalPhaseLabel, setApprovalPhaseLabel] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approvalPendingJobId, setApprovalPendingJobId] = useState<string | null>(null);
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [showCalculations, setShowCalculations] = useState(false);
  const [previewLayers, setPreviewLayers] = useState({
    buildings: true,
    roads: true,
    grading: true,
    drainage: true,
    utilities: true,
    structures: true,
    lots: false,
  });
  const [quantityRollupsEnabled, setQuantityRollupsEnabled] = useState(true);
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const [previewFullscreenOpen, setPreviewFullscreenOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [currentProject, setCurrentProject] = useState<ProjectRecord | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activePlanTool, setActivePlanTool] = useState<PlanToolMode>("run");
  const [jobClockMs, setJobClockMs] = useState(() => Date.now());
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const mapSnapshotInputRef = useRef<HTMLInputElement | null>(null);
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
  const lastProjectResultRefreshRef = useRef<Record<string, number>>({});
  const lastJobPartialResultRefreshRef = useRef<Record<string, number>>({});
  const chatMessagesRef = useRef<ChatMessage[]>([createWelcomeMessage()]);
  const suppressProjectAutoLoadRef = useRef(false);
  const chatAutosaveTimeoutRef = useRef<number | null>(null);
  const autosaveSuspendRef = useRef(false);
  const currentPhaseLabelRef = useRef<string>("");
  const previewRecoveryKeyRef = useRef("");
  const lastSiteInputProjectRef = useRef("");
  const controlAutosaveTimeoutRef = useRef<number | null>(null);

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
    onLogoutCleanup: () => {
      setProjects([]);
      setJobs([]);
      setCurrentProject(null);
      setProjectId("");
    },
  });

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

  const buildManualFields = useCallback(({
    nextSiteName,
    nextFileName,
    nextUnits,
    nextProjectType,
    nextLotWidth,
    nextLotHeight,
    nextSetback,
    nextBuildingWidth,
    nextBuildingDepth,
    nextBuildingCount,
    nextParkingCount,
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
  }: {
    nextSiteName: string;
    nextFileName: string;
    nextUnits: string;
    nextProjectType: string;
    nextLotWidth: string | number | null | undefined;
    nextLotHeight: string | number | null | undefined;
    nextSetback: string | number | null | undefined;
    nextBuildingWidth: string | number | null | undefined;
    nextBuildingDepth: string | number | null | undefined;
    nextBuildingCount: string | number | null | undefined;
    nextParkingCount: string | number | null | undefined;
    nextMinSlopePct: string | number | null | undefined;
    nextPipeMinSlopePct: string | number | null | undefined;
    nextMaxParkingSlopePct: string | number | null | undefined;
    nextMaxRoadGradePct: string | number | null | undefined;
    nextMaxAdaCrossSlopePct: string | number | null | undefined;
    nextRoads: boolean;
    nextGrading: boolean;
    nextDrainage: boolean;
    nextUtilities: boolean;
    placementsOverride?: BuildingPlacement[];
  }) => {
    const lotWidthValue = parsePositiveNumber(nextLotWidth);
    const lotHeightValue = parsePositiveNumber(nextLotHeight);
    const setbackValue = parsePositiveNumber(nextSetback);
    const buildingWidthValue = parsePositiveNumber(nextBuildingWidth);
    const buildingDepthValue = parsePositiveNumber(nextBuildingDepth);
    const buildingCountValue = parsePositiveNumber(nextBuildingCount);
    const parkingCountValue = parsePositiveNumber(nextParkingCount);
    const minSlopeValue = parsePositiveNumber(nextMinSlopePct);
    const pipeMinSlopeValue = parsePositiveNumber(nextPipeMinSlopePct);
    const maxParkingSlopeValue = parsePositiveNumber(nextMaxParkingSlopePct);
    const maxRoadGradeValue = parsePositiveNumber(nextMaxRoadGradePct);
    const maxAdaSlopeValue = parsePositiveNumber(nextMaxAdaCrossSlopePct);

    const manualFields: ManualFields = {
      project_name: nextSiteName,
      file_name: nextFileName,
      units: nextUnits,
      project_type: nextProjectType,
      disciplines: [
        nextRoads ? "corridor" : null,
        nextGrading ? "grading" : null,
        nextDrainage ? "drainage" : null,
        nextUtilities ? "utility" : null,
      ].filter((item): item is string => Boolean(item)),
    };

    if (lotWidthValue !== null && lotHeightValue !== null) {
      manualFields.lot = {
        x: 0,
        y: 0,
        w: lotWidthValue,
        h: lotHeightValue,
      };
    }

    if (setbackValue !== null) {
      manualFields.setback = setbackValue;
    }

    if (buildingWidthValue !== null) {
      manualFields.building_width = buildingWidthValue;
    }

    if (buildingDepthValue !== null) {
      manualFields.building_depth = buildingDepthValue;
    }

    const placementOverrides = (placementsOverride ?? buildingPlacements)
      .filter((placement) => placement.placed && Number.isFinite(placement.x) && Number.isFinite(placement.y))
      .map((placement) => ({
        id: placement.id,
        name: placement.label,
        label: placement.label,
        type: placement.type ?? "building",
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        height_ft: placement.h,
        rotation: placement.rotation,
        use: placement.use,
        stall_count: placement.stallCount,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        systemDependencies: placement.systemDependencies,
      }));
    const basinOverrides = placementOverrides.filter((placement) => placement.type === "basin");
    const entranceOverrides = placementOverrides.filter((placement) => placement.type === "entrance");
    const parkingOverrides = placementOverrides.filter((placement) => placement.type === "parking");
    const buildingTypes = new Set<SiteObjectType>([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
      "pool",
      "amenity",
      "open_space",
    ]);
    const buildingOverrides = placementOverrides.filter((placement) =>
      buildingTypes.has(placement.type as SiteObjectType),
    );

    if (buildingOverrides.length) {
      manualFields.buildings = buildingOverrides.map((placement) => ({
        ...placement,
        height_ft: placement.height_ft,
      }));
    }
    if (basinOverrides.length) {
      manualFields.ponds = basinOverrides.map((placement) => ({
        id: placement.id,
        name: placement.label,
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        rotation: placement.rotation,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        systemDependencies: placement.systemDependencies,
      }));
    }
    if (entranceOverrides.length) {
      manualFields.access_points = entranceOverrides.map((placement) => ({
        id: placement.id,
        name: placement.label,
        x: placement.x,
        y: placement.y,
        w: placement.w,
        d: placement.d,
        rotation: placement.rotation,
        locked: placement.locked,
        source: placement.source,
        generated: placement.generated,
        systemDependencies: placement.systemDependencies,
      }));
    }

    if (!buildingOverrides.length && buildingCountValue !== null) {
      manualFields.buildings = Array.from({ length: Math.max(1, Math.round(buildingCountValue)) }).map(
        (_, idx) => ({
          name: `Building ${idx + 1}`,
          w: buildingWidthValue ?? undefined,
          d: buildingDepthValue ?? undefined,
        }),
      );
    }

    const parkingFromPlacements = parkingOverrides.reduce((sum, placement) => {
      const value =
        typeof placement.stall_count === "number"
          ? placement.stall_count
          : parsePositiveNumber(placement.stall_count);
      return sum + (value ?? 0);
    }, 0);
    const resolvedParkingCount =
      parkingFromPlacements > 0 ? parkingFromPlacements : parkingCountValue;

    if (resolvedParkingCount !== null) {
      manualFields.site_plan = { parking_count: resolvedParkingCount };
    }

    if (minSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        min_slope_pct: minSlopeValue,
      };
    }

    if (maxParkingSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_parking_slope_pct: maxParkingSlopeValue,
      };
    }

    if (maxRoadGradeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_road_grade_pct: maxRoadGradeValue,
      };
    }

    if (maxAdaSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_ada_cross_slope_pct: maxAdaSlopeValue,
      };
    }

    if (pipeMinSlopeValue !== null) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        min_pipe_slope_pct: pipeMinSlopeValue,
      };
    }
    if (drainageForcedInlets.length) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        forced_inlets: drainageForcedInlets,
      };
    }
    if (drainageConnectOrphans) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        connect_orphans: true,
      };
    }
    if (drainageAllowSlopeAdjust) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        allow_slope_adjustment: true,
        max_slope_adjust: drainageMaxSlopeAdjust,
      };
    }

    return manualFields;
  }, [
    buildingPlacements,
    drainageAllowSlopeAdjust,
    drainageConnectOrphans,
    drainageForcedInlets,
    drainageMaxSlopeAdjust,
  ]);

  const payloadPreview = useMemo(
    () => ({
      project_id: projectId || null,
      full_design_mode: true,
      input_mode: "user",
      strict_mode: false,
      prompt_text: prompt || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
        system_dirty_state: systemStatuses,
        site_object_id: buildingPlacements.find((item) => item.type === "site")?.id ?? null,
      },
      manual_fields: buildManualFields({
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
      allow_ai_fill_for_blanks: false,
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
      currentProject,
      buildManualFields,
    ],
  );

  const artifactPayload = useMemo(() => {
    if (
      backendResult &&
      typeof backendResult === "object" &&
      Object.keys(backendResult).length
    ) {
      return {
        project_id: projectId || currentProject?.project_id || null,
        result: backendResult,
        filename_stem: fileName || siteName,
      };
    }

    return {
      project_id: projectId || currentProject?.project_id || null,
      filename_stem: fileName || siteName,
    };
  }, [backendResult, currentProject?.project_id, fileName, projectId, siteName]);

  const workflowRuns = useMemo<WorkflowRunSummary[]>(
    () =>
      Array.isArray(currentProject?.metadata?.workflow?.runs)
        ? currentProject?.metadata?.workflow?.runs
        : [],
    [currentProject],
  );

  const selectedRun = useMemo<WorkflowRunSummary | null>(() => {
    if (!workflowRuns.length) return null;
    return (
      workflowRuns.find((run) => run.run_id === selectedRunId) ?? workflowRuns[0]
    );
  }, [workflowRuns, selectedRunId]);
  const activeJob = useMemo(
    () => jobs.find((job) => job.job_id === activeJobId) ?? null,
    [jobs, activeJobId],
  );
  const currentProjectActiveJob = useMemo(
    () =>
      jobs.find(
        (job) =>
          Boolean(projectId) &&
          job.project_id === projectId &&
          ["queued", "running", "awaiting_approval", "cancelling"].includes(String(job.status || "").toLowerCase()),
      ) ?? null,
    [jobs, projectId],
  );
  const visibleActiveJob = useMemo(() => {
    if (activeJobId) {
      return activeJob;
    }
    return projectId ? currentProjectActiveJob : activeJob;
  }, [activeJob, activeJobId, currentProjectActiveJob, projectId]);
  const hasDirectRunInFlight = busy && !visibleActiveJob && Boolean(directRunAbortRef.current);
  const visibleActiveJobStale = useMemo(
    () => isLikelyStaleJob(visibleActiveJob, jobClockMs),
    [visibleActiveJob, jobClockMs],
  );
  const thinkingState = useMemo(
    () =>
      buildThinkingState({
        busy,
        activePlanTool,
        activeJobStatus: visibleActiveJob?.status,
        activeJobStage: visibleActiveJob?.stage,
        activeJobDetail: visibleActiveJob?.stage_detail,
        activeJobProgress: visibleActiveJob?.progress,
        activeJobUpdatedAt: visibleActiveJob?.updated_at,
        activeJobQueuePosition: visibleActiveJob?.queue_position,
        activeJobQueuedCount: visibleActiveJob?.queued_count,
        activeJobRunningCount: visibleActiveJob?.running_count,
        staleJob: visibleActiveJobStale,
        statusMessage,
      }),
    [busy, visibleActiveJob?.status, visibleActiveJob?.stage, visibleActiveJob?.stage_detail, visibleActiveJob?.progress, visibleActiveJob?.updated_at, visibleActiveJob?.queue_position, visibleActiveJob?.queued_count, visibleActiveJob?.running_count, visibleActiveJobStale, activePlanTool, statusMessage],
  );

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
      setApprovalPendingJobId(null);
      setApprovalPhaseLabel(null);
      return;
    }
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (["awaiting_approval", "completed", "failed", "cancelled"].includes(status)) {
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
  const managerMetrics = useMemo<ManagerMetrics>(
    () => currentPlanMeta?.manager_export?.metrics ?? {},
    [currentPlanMeta],
  );
  const quantityTotals = useMemo<QuantityTotals>(
    () => currentPlanMeta?.quantities?.totals ?? {},
    [currentPlanMeta],
  );
  const stormSummary = useMemo<StormSummary>(() => currentPlanMeta?.storm_pipes ?? {}, [currentPlanMeta]);
  const drainageSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.drainage ?? {}, [currentPlanMeta]);
  const gradingSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.grading ?? {}, [currentPlanMeta]);
  const drainageLowPoints = useMemo(() => {
    const fromDrainage = Array.isArray((drainageSummary as Record<string, unknown>)?.low_points)
      ? ((drainageSummary as Record<string, unknown>).low_points as Array<Record<string, unknown>>)
      : [];
    const fromGrading = Array.isArray((gradingSummary as Record<string, unknown>)?.low_points)
      ? ((gradingSummary as Record<string, unknown>).low_points as Array<Record<string, unknown>>)
      : [];
    const candidates = fromDrainage.length ? fromDrainage : fromGrading;
    return candidates
      .map((item) => ({
        x: typeof item.x === "number" ? item.x : Number(item.x),
        y: typeof item.y === "number" ? item.y : Number(item.y),
        z: typeof item.z === "number" ? item.z : Number(item.z),
      }))
      .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
  }, [drainageSummary, gradingSummary]);

  const previewLabels = useMemo(
    () => planPreviewAnnotations?.labels ?? [],
    [planPreviewAnnotations],
  );
  const issueTargets = useMemo(() => {
    const keywordMap = [
      { key: "pipe", token: "PIPE" },
      { key: "drain", token: "DRAIN" },
      { key: "storm", token: "STORM" },
      { key: "basin", token: "BASIN" },
      { key: "parking", token: "PARK" },
      { key: "ada", token: "ADA" },
      { key: "road", token: "ROAD" },
      { key: "utility", token: "UTIL" },
      { key: "water", token: "WATER" },
      { key: "sanitary", token: "SAN" },
    ];
    if (!issues.length) return [];
    return issues.map((issue, idx) => {
      const lowered = issue.message.toLowerCase();
      const matched = keywordMap.find((item) => lowered.includes(item.key));
      const labelMatch = matched
        ? previewLabels.find((label) => label.label.toLowerCase().includes(matched.key))
        : null;
      return {
        id: `${issue.message}-${idx}`,
        label: labelMatch?.label ?? "",
      };
    });
  }, [issues, previewLabels]);

  const selectedIssueLabel = issueTargets.find((item) => item.id === selectedIssueId)?.label ?? "";

  const pipeSegments = useMemo<PipeSegment[]>(() => {
    const segments =
      stormSummary?.segments ||
      stormSummary?.pipe_segments ||
      stormSummary?.storm_pipe_segments ||
      [];
    return Array.isArray(segments) ? segments : [];
  }, [stormSummary]);

  const totalPipeLength =
    readMetricValue(managerMetrics.storm_pipe_length_ft) ??
    (pipeSegments.length
      ? pipeSegments.reduce((sum, seg) => sum + Number(seg.length_ft || 0), 0)
      : null);
  const maxSlope = pipeSegments.length
    ? Math.max(
        ...pipeSegments.map((seg) =>
          Number(seg.slope_pct ?? (seg.slope_ft_ft ?? 0) * 100),
        ),
      )
    : null;
  const minSlope = pipeSegments.length
    ? Math.min(
        ...pipeSegments.map((seg) =>
          Number(seg.slope_pct ?? (seg.slope_ft_ft ?? 0) * 100),
        ),
      )
    : null;
  const flowCfs =
    readMetricValue(managerMetrics.pipe_capacity_total_cfs) ??
    readMetricValue(stormSummary.total_system_flow_cfs) ??
    readMetricValue(stormSummary.total_system_capacity_cfs) ??
    null;
  const cutFillNet =
    readMetricValue(managerMetrics.earthwork_net_cf) ??
    readMetricValue((gradingSummary as { earthwork?: { net_cf?: number } })?.earthwork?.net_cf) ??
    null;
  const basinSize =
    (Array.isArray(drainageSummary?.basins) && drainageSummary.basins[0]?.area_sf) ||
    (Array.isArray(drainageSummary?.basins) && drainageSummary.basins[0]?.footprint_area_sf) ||
    null;
  const quantityRows = useMemo(() => {
    const rows = [
      { label: "Lot area", value: quantityTotals.lot_area_sf ?? null, unit: "sf" },
      { label: "Building area", value: quantityTotals.building_area_sf ?? null, unit: "sf" },
      { label: "Parking area", value: quantityTotals.parking_area_sf ?? null, unit: "sf" },
      { label: "Road area", value: quantityTotals.road_area_sf ?? null, unit: "sf" },
      { label: "Impervious area", value: quantityTotals.estimated_impervious_area_sf ?? null, unit: "sf" },
      { label: "Parking stalls", value: quantityTotals.estimated_parking_stalls ?? null, unit: "stalls" },
      { label: "Road length", value: quantityTotals.road_length_ft ?? null, unit: "ft" },
      { label: "Sidewalk length", value: quantityTotals.sidewalk_length_ft ?? null, unit: "ft" },
      { label: "Pipe length", value: quantityTotals.pipe_length_ft ?? null, unit: "ft" },
      { label: "Utility length", value: quantityTotals.utility_length_ft ?? null, unit: "ft" },
      { label: "Sanitary length", value: quantityTotals.sanitary_length_ft ?? null, unit: "ft" },
      { label: "Drainage flow length", value: quantityTotals.drainage_flow_length_ft ?? null, unit: "ft" },
      { label: "Pond count", value: quantityTotals.pond_count ?? null, unit: "ea" },
      { label: "Inlet count", value: quantityTotals.inlet_count ?? null, unit: "ea" },
      { label: "Bridge area", value: quantityTotals.bridge_area_sf ?? null, unit: "sf" },
      { label: "Pool area", value: quantityTotals.pool_area_sf ?? null, unit: "sf" },
      { label: "Lot count", value: quantityTotals.lot_feature_count ?? null, unit: "ea" },
    ];
    return rows.filter((row) => Number(row.value || 0) > 0);
  }, [quantityTotals]);
  const measurementOverlayStats = useMemo(
    () => [
      { label: "Lot area", value: quantityTotals.lot_area_sf ?? null, unit: "sf" },
      { label: "Building area", value: quantityTotals.building_area_sf ?? null, unit: "sf" },
      { label: "Parking area", value: quantityTotals.parking_area_sf ?? null, unit: "sf" },
      { label: "Road length", value: quantityTotals.road_length_ft ?? null, unit: "ft" },
      { label: "Impervious area", value: quantityTotals.estimated_impervious_area_sf ?? null, unit: "sf" },
      { label: "Parking stalls", value: quantityTotals.estimated_parking_stalls ?? null, unit: "stalls" },
    ],
    [quantityTotals],
  );
  const calculationOverlayStats = useMemo(
    () => [
      { label: "Total pipe length", value: totalPipeLength, unit: "ft" },
      { label: "Max slope", value: maxSlope, unit: "%" },
      { label: "Min slope", value: minSlope, unit: "%" },
      { label: "Flow (CFS)", value: flowCfs, unit: "cfs" },
      { label: "Cut / fill net", value: cutFillNet, unit: "cf" },
      { label: "Pond size", value: basinSize, unit: "sf" },
    ],
    [totalPipeLength, maxSlope, minSlope, flowCfs, cutFillNet, basinSize],
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
  const suggestedImproveGoal = useMemo(() => {
    const failureBlob = [
      ...currentManualFailures.map((failure) =>
        [failure.code, failure.message, failure.system, failure.rule]
          .filter(Boolean)
          .join(" "),
      ),
      ...issues.map((issue) => issue.message),
    ]
      .join(" ")
      .toLowerCase();

    if (failureBlob.includes("drain") || failureBlob.includes("inlet")) {
      return "improve_drainage";
    }
    if (failureBlob.includes("pipe")) {
      return "reduce_pipe_length";
    }
    if (
      failureBlob.includes("grade") ||
      failureBlob.includes("earthwork") ||
      failureBlob.includes("slope")
    ) {
      return "reduce_grading";
    }
    if (failureBlob.includes("parking")) {
      return "maximize_parking";
    }
    return undefined;
  }, [currentManualFailures, issues]);


  const applyBackendResult = (data: PlanResponse) => {
    setBackendResult(data);
    if (Array.isArray(data?.assumptions)) {
      setAssumptions(
        data.assumptions.map((item: BackendAssumption) => ({
          field: item.field_name ?? "unknown",
          value:
            typeof item.assumed_value === "string"
              ? item.assumed_value
              : JSON.stringify(item.assumed_value),
          reason: item.reason ?? "",
        })),
      );
    } else {
      setAssumptions(defaultAssumptions);
    }

    if (Array.isArray(data?.issues)) {
      setIssues(
        data.issues.map((item: BackendIssue) => ({
          severity: item.severity === "error" ? "error" : "warning",
          message: item.message ?? "Unknown issue",
          code: typeof item.code === "string" ? item.code : undefined,
          context: item.context && typeof item.context === "object" ? item.context : undefined,
        })),
      );
    } else {
      setIssues([]);
    }
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
    if (!token || !feedback) return;
    const thread = chatMessagesRef.current;
    const idx = thread.findIndex((message) => message.id === messageId);
    if (idx < 0) return;
    const target = thread[idx];
    const prevUser = [...thread]
      .slice(0, idx)
      .reverse()
      .find((message) => message.role === "user");
    const userMessage = prevUser?.content ?? "";

    setChatMessages((current) => {
      const next = current.map((message) =>
        message.id === messageId ? { ...message, feedback } : message,
      );
      chatMessagesRef.current = next;
      return next;
    });

    try {
      await postJson<{ success: boolean }>(
        "/api/chat/feedback",
        {
          project_id: currentProject?.project_id ?? null,
          message_id: messageId,
          feedback,
          message: userMessage,
          assistant_message: target.content,
          context: buildChatDecisionContext({}, userMessage),
        },
        { token },
      );
    } catch {
      // Feedback logging should never block chat UX.
    }
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

  const applyProjectInput = (projectInput: ProjectInput) => {
    if (!projectInput || typeof projectInput !== "object") {
      return;
    }

    const manualFields = projectInput.manual_fields ?? {};
    const lot = (manualFields.lot ?? {}) as { w?: number; h?: number };
    const sitePlan = (manualFields.site_plan ?? {}) as { parking_count?: number };
    const gradingFields = (manualFields.grading ?? {}) as {
      min_slope_pct?: number;
      max_parking_slope_pct?: number;
      max_road_grade_pct?: number;
      max_ada_cross_slope_pct?: number;
    };
    const drainageFields = (manualFields.drainage ?? {}) as NonNullable<ManualFields["drainage"]>;
    const drainageForced = Array.isArray(drainageFields?.forced_inlets)
      ? (drainageFields?.forced_inlets as Array<Record<string, unknown>>)
      : [];
    const disciplines = toArray(manualFields.disciplines);
    const buildingsList = Array.isArray(manualFields.buildings) ? manualFields.buildings : [];
    const restoredThread: ChatMessage[] = Array.isArray(projectInput.meta?.chat_thread)
      ? projectInput.meta.chat_thread
          .filter((message) => message && typeof message.content === "string")
          .map((message): ChatMessage => ({
            id:
              typeof message.id === "string"
                ? message.id
                : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            role:
              message.role === "user" ||
              message.role === "assistant" ||
              message.role === "system"
                ? message.role
                : "assistant",
            content: message.content,
            createdAt:
              typeof message.createdAt === "number"
                ? message.createdAt
                : Date.now(),
            kind:
              message.kind === "status" ||
              message.kind === "explanation" ||
              message.kind === "action"
                ? message.kind
                : "message",
            feedback:
              message.feedback === "up" || message.feedback === "down"
                ? message.feedback
                : undefined,
            phaseTag: typeof message.phaseTag === "string" ? message.phaseTag : undefined,
          }))
      : [];
    const autoNamed = Boolean(projectInput.meta?.auto_named);
    const autoFileNamed = Boolean(projectInput.meta?.auto_file_named);

    setPrompt(projectInput.prompt_text ?? "");
    setImageName(projectInput.image_path ?? "");
    setUploadedImageApiUrl(
      projectInput.image_path ? uploadedImageSrc(projectInput.image_path, token) : "",
    );
    setUploadedImagePreviewUrl("");
    setSiteName(manualFields.project_name ?? "");
    setFileName(manualFields.file_name ?? "");
    setSiteNameAuto(autoNamed || !manualFields.project_name);
    setFileNameAuto(autoFileNamed || !(manualFields.file_name ?? manualFields.project_name));
    setUnits(manualFields.units ?? "ft");
    setProjectType(manualFields.project_type ?? "");
    setLotWidth(String(lot.w ?? ""));
    setLotHeight(String(lot.h ?? ""));
    setSetback(String(manualFields.setback ?? ""));
    setBuildingWidth(String(manualFields.building_width ?? ""));
    setBuildingDepth(String(manualFields.building_depth ?? ""));
    setBuildingCount(buildingsList.length ? String(buildingsList.length) : "");
    const parsedPlacements = buildingsList
      .map((raw, idx) => {
        if (!raw || typeof raw !== "object") return null;
        const rec = raw as Record<string, unknown>;
        const originRaw = (rec as { origin?: unknown }).origin;
        const origin = Array.isArray(originRaw) ? originRaw : [];
        const rawX = rec.x ?? origin[0];
        const rawY = rec.y ?? origin[1];
        const x = typeof rawX === "number" ? rawX : rawX !== undefined ? Number(rawX) : NaN;
        const y = typeof rawY === "number" ? rawY : rawY !== undefined ? Number(rawY) : NaN;
        const rawW = rec.w ?? rec.width ?? manualFields.building_width;
        const rawD = rec.d ?? rec.depth ?? manualFields.building_depth;
        const w = typeof rawW === "number" ? rawW : rawW !== undefined ? Number(rawW) : NaN;
        const d = typeof rawD === "number" ? rawD : rawD !== undefined ? Number(rawD) : NaN;
        if (!Number.isFinite(w) || !Number.isFinite(d)) return null;
        const placed = Number.isFinite(x) && Number.isFinite(y);
        return {
          id: typeof rec.id === "string" ? rec.id : `building-${Date.now()}-${idx}`,
          label:
            typeof rec.label === "string"
              ? rec.label
              : typeof rec.name === "string"
                ? rec.name
                : `Building ${idx + 1}`,
          type: (typeof rec.type === "string" ? rec.type : "building") as SiteObjectType,
          x: placed ? x : undefined,
          y: placed ? y : undefined,
          w,
          d,
          rotation: typeof rec.rotation === "number" ? rec.rotation : undefined,
          use: typeof rec.use === "string" ? rec.use : undefined,
          locked: Boolean(rec.locked),
          placed,
        } as BuildingPlacement;
      })
      .filter(Boolean) as BuildingPlacement[];

    const pondPlacements = (Array.isArray(manualFields.ponds) ? manualFields.ponds : [])
      .map((raw, idx) => {
        if (!raw || typeof raw !== "object") return null;
        const rec = raw as Record<string, unknown>;
        const rawX = rec.x;
        const rawY = rec.y;
        const x = typeof rawX === "number" ? rawX : rawX !== undefined ? Number(rawX) : NaN;
        const y = typeof rawY === "number" ? rawY : rawY !== undefined ? Number(rawY) : NaN;
        const rawW = rec.w ?? 60;
        const rawD = rec.d ?? 40;
        const w = typeof rawW === "number" ? rawW : rawW !== undefined ? Number(rawW) : NaN;
        const d = typeof rawD === "number" ? rawD : rawD !== undefined ? Number(rawD) : NaN;
        if (!Number.isFinite(w) || !Number.isFinite(d)) return null;
        const placed = Number.isFinite(x) && Number.isFinite(y);
        return {
          id: typeof rec.id === "string" ? rec.id : `basin-${Date.now()}-${idx}`,
          label:
            typeof rec.label === "string"
              ? rec.label
              : typeof rec.name === "string"
                ? rec.name
                : "Basin",
          type: "basin" as SiteObjectType,
          x: placed ? x : undefined,
          y: placed ? y : undefined,
          w,
          d,
          rotation: typeof rec.rotation === "number" ? rec.rotation : undefined,
          locked: Boolean(rec.locked),
          placed,
          source: typeof rec.source === "string" ? rec.source : "generated",
          generated: Boolean(rec.generated),
          systemDependencies: Array.isArray(rec.systemDependencies)
            ? (rec.systemDependencies as string[])
            : ["drainage"],
        } as BuildingPlacement;
      })
      .filter(Boolean) as BuildingPlacement[];

    const inletPlacements = (Array.isArray((manualFields.drainage ?? {}).forced_inlets)
      ? ((manualFields.drainage ?? {}).forced_inlets as Array<Record<string, unknown>>)
      : []
    )
      .map((raw, idx) => {
        if (!raw || typeof raw !== "object") return null;
        const rec = raw as Record<string, unknown>;
        const rawX = rec.x;
        const rawY = rec.y;
        const x = typeof rawX === "number" ? rawX : rawX !== undefined ? Number(rawX) : NaN;
        const y = typeof rawY === "number" ? rawY : rawY !== undefined ? Number(rawY) : NaN;
        if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
        return {
          id: typeof rec.id === "string" ? rec.id : `inlet-${Date.now()}-${idx}`,
          label:
            typeof rec.label === "string"
              ? rec.label
              : typeof rec.name === "string"
                ? rec.name
                : "Inlet",
          type: "inlet" as SiteObjectType,
          x,
          y,
          w: 8,
          d: 8,
          rotation: 0,
          locked: Boolean(rec.locked),
          placed: true,
          source: typeof rec.source === "string" ? rec.source : "generated",
          generated: Boolean(rec.generated),
          systemDependencies: ["drainage"],
        } as BuildingPlacement;
      })
      .filter(Boolean) as BuildingPlacement[];

    const mergedPlacements = [...parsedPlacements, ...pondPlacements, ...inletPlacements];
    setBuildingPlacements(mergedPlacements);
    setPlacementModeEnabled(false);
    setActivePlacementId(null);
    setParkingCount(String(sitePlan.parking_count ?? ""));
    setMinSlopePct(String(gradingFields.min_slope_pct ?? ""));
    setPipeMinSlopePct(String(drainageFields.min_pipe_slope_pct ?? ""));
    setDrainageForcedInlets(
      drainageForced
        .map((item) => {
          const rec = item as { x?: number; y?: number; name?: string };
          if (typeof rec?.x !== "number" || typeof rec?.y !== "number") return null;
          return { x: rec.x, y: rec.y, name: typeof rec.name === "string" ? rec.name : undefined };
        })
        .filter(Boolean) as Array<{ x: number; y: number; name?: string }>,
    );
    setDrainageConnectOrphans(Boolean((manualFields.drainage ?? {}).connect_orphans));
    setDrainageAllowSlopeAdjust(Boolean((manualFields.drainage ?? {}).allow_slope_adjustment));
    const rawMaxSlopeAdjust = (manualFields.drainage ?? {}).max_slope_adjust;
    setDrainageMaxSlopeAdjust(
      typeof rawMaxSlopeAdjust === "number" && Number.isFinite(rawMaxSlopeAdjust)
        ? rawMaxSlopeAdjust
        : 0.001,
    );
    setMaxParkingSlopePct(String(gradingFields.max_parking_slope_pct ?? ""));
    setMaxRoadGradePct(String(gradingFields.max_road_grade_pct ?? ""));
    setMaxAdaCrossSlopePct(String(gradingFields.max_ada_cross_slope_pct ?? ""));
    setRoads(disciplines.includes("corridor"));
    setGrading(disciplines.includes("grading"));
    setDrainage(disciplines.includes("drainage"));
    setUtilities(disciplines.includes("utility"));
    const nextThread = restoredThread.length ? restoredThread : [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
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
    if (site.locked === siteScaleLocked) return;
    setBuildingPlacements((prev) =>
      prev.map((item) =>
        item.type === "site"
          ? {
              ...item,
              locked: siteScaleLocked,
              capabilities: {
                ...item.capabilities,
                movable: !siteScaleLocked,
                resizable: !siteScaleLocked,
                rotatable: !siteScaleLocked,
              },
            }
          : item,
      ),
    );
  }, [buildingPlacements, siteScaleLocked]);

  useEffect(() => {
    const site = buildingPlacements.find((item) => item.type === "site");
    if (!site || typeof site.locked !== "boolean") return;
    if (site.locked !== siteScaleLocked) {
      setSiteScaleLocked(site.locked);
    }
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
      if (!debugPreview) return;
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
    if (!debugPreview) return;
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

  const markSystemsStale = useCallback(() => {
    setSystemStatuses((prev) => ({
      roads: prev.roads === "not_generated" ? "not_generated" : "stale",
      parking: prev.parking === "not_generated" ? "not_generated" : "stale",
      grading: prev.grading === "not_generated" ? "not_generated" : "stale",
      drainage: prev.drainage === "not_generated" ? "not_generated" : "stale",
      utilities: prev.utilities === "not_generated" ? "not_generated" : "stale",
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
      const currentMeta = (target.meta as { parkingParams?: any })?.parkingParams ?? {};
      const nextMeta = (overrides?.meta as { parkingParams?: any })?.parkingParams ?? {};
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
      let stallsPerRow = Math.max(1, Math.ceil(totalStalls / rows));
      let moduleWidth = perModuleWidth(stallsPerRow);
      let modulesNeeded = Math.max(1, Math.ceil(totalStalls / (stallsPerRow * rows)));
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
    (type: SiteObjectType) => {
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
      const defaults =
        type === "building" ? resolveDefaultBuildingDims() : { w: catalog.defaultW, d: catalog.defaultD };
      const defaultHeight = catalog.defaultH ?? 0;
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
        label: formatObjectLabel(type, existingCount),
        type,
        use: catalog.use,
        w: defaults.w,
        d: defaults.d,
        h: defaultHeight,
        rotation: 0,
        stallCount: parkingStalls,
        locked: false,
        placed: false,
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
        nextPlacement.geometry = buildDefaultPolyline({
          x: 0,
          y: 0,
          w: nextPlacement.w,
          d: nextPlacement.d,
        });
        nextPlacement.capabilities = {
          movable: true,
          resizable: false,
          rotatable: false,
          deletable: true,
        };
      }
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      console.debug("[placement] add-object", {
        id: nextPlacement.id,
        type: nextPlacement.type,
        w: nextPlacement.w,
        d: nextPlacement.d,
        placed: nextPlacement.placed,
      });
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
      target?.geometryType === "polyline" &&
      Array.isArray(target.geometry) &&
      (typeof updates.x === "number" || typeof updates.y === "number")
    ) {
      const deltaX = (typeof updates.x === "number" ? updates.x : target.x ?? 0) - (target.x ?? 0);
      const deltaY = (typeof updates.y === "number" ? updates.y : target.y ?? 0) - (target.y ?? 0);
      if (Number.isFinite(deltaX) && Number.isFinite(deltaY)) {
        nextUpdates.geometry = target.geometry.map(([px, py]) => [px + deltaX, py + deltaY]);
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
          ...(target.meta as { parkingParams?: any })?.parkingParams,
          ...(updates.meta as { parkingParams?: any })?.parkingParams,
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
    setBuildingPlacements((prev) =>
      prev.map((item) => (item.id === id ? { ...item, ...nextUpdates } : item)),
    );
    markSystemsStale();
    setStatusMessage("Object updated. Regenerate systems to reflect the new layout.");
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
    resolveParkingParams,
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
    debugLog("remove-object", { id });
    setBuildingPlacements((prev) => prev.filter((item) => item.id !== id));
    setActivePlacementId((prev) => (prev === id ? null : prev));
    setPlacementModeEnabled((prev) => (activePlacementId === id ? false : prev));
    setFocusObjectId((prev) => (prev === id ? null : prev));
    markSystemsStale();
    setStatusMessage("Object removed. Regenerate systems to reflect the new layout.");
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object removal...", track: true });
  }, [activePlacementId, clearGeneratedPreview, markSystemsStale]);

  const handleRestoreBuilding = useCallback((snapshot: BuildingPlacement) => {
    clearGeneratedPreview();
    setBuildingPlacements((prev) => {
      if (prev.some((item) => item.id === snapshot.id)) return prev;
      return [...prev, { ...snapshot }];
    });
    markSystemsStale();
    setStatusMessage("Undo: object restored.");
    void ensureProjectDraftRef.current()
      .then(() => saveProjectRef.current({ silent: true }))
      .then(() => {
        previewRefreshIntentRef.current = {
          reason: "Refreshing preview after undo restore...",
          track: true,
        };
      });
  }, [clearGeneratedPreview, markSystemsStale]);

  const handleAcceptDetected = useCallback((id: string) => {
    clearGeneratedPreview();
    setDetectedPlacements((prev) => {
      const target = prev.find((item) => item.id === id);
      if (!target) return prev;
      setBuildingPlacements((placements) => [
        ...placements,
        {
          ...target,
          id: `obj_${Math.random().toString(36).slice(2, 9)}`,
          label: target.label.replace("Detected ", ""),
          source: "user_confirmed",
          confirmed: true,
        },
      ]);
      const nextDetected = prev.filter((item) => item.id !== id);
      persistDetectedPlacements(nextDetected);
      return nextDetected;
    });
  }, [clearGeneratedPreview, persistDetectedPlacements]);

  const handleRejectDetected = useCallback((id: string) => {
    clearGeneratedPreview();
    setDetectedPlacements((prev) => {
      const nextDetected = prev.filter((item) => item.id !== id);
      persistDetectedPlacements(nextDetected);
      return nextDetected;
    });
  }, [clearGeneratedPreview, persistDetectedPlacements]);

  const handleToggleBuildingLock = useCallback((id: string) => {
    setBuildingPlacements((prev) =>
      prev.map((item) => (item.id === id ? { ...item, locked: !item.locked } : item)),
    );
  }, []);

  const handlePlaceBuilding = useCallback(
    (position: { x: number; y: number }) => {
      clearGeneratedPreview();
      const lot = resolveLotBounds();
      if (!lot.w || !lot.h) {
        setStatusMessage("Set the site width and height before placing buildings.");
        return;
      }
      const { w, d } = resolveDefaultBuildingDims();
      const clampedX = Math.min(Math.max(position.x, 0), 1);
      const clampedY = Math.min(Math.max(position.y, 0), 1);
      const nextX = lot.x + clampedX * lot.w - w / 2;
      const nextY = lot.y + clampedY * lot.h - d / 2;
      if (!Number.isFinite(nextX) || !Number.isFinite(nextY)) {
        setStatusMessage("Placement failed: invalid coordinates.");
        return;
      }
      const boundedX = Math.min(Math.max(nextX, lot.x), lot.x + lot.w - w);
      const boundedY = Math.min(Math.max(nextY, lot.y), lot.y + lot.h - d);
      console.debug("[placement] place-building", {
        activePlacementId,
        position,
        lot,
        boundedX,
        boundedY,
        w,
        d,
      });
      debugLog("place-building", {
        activePlacementId: activePlacementId ?? null,
        boundedX,
        boundedY,
      });
      if (activePlacementId) {
        setBuildingPlacements((prev) =>
          prev.map((item) =>
            item.id === activePlacementId
              ? {
                  ...item,
                  x: boundedX,
                  y: boundedY,
                  placed: true,
                  geometry:
                    item.geometryType === "polyline"
                      ? buildDefaultPolyline({ x: boundedX, y: boundedY, w: item.w, d: item.d })
                      : item.geometry,
                }
              : item,
          ),
        );
        setActivePlacementId(null);
        markSystemsStale();
        debugLog("place-building-commit", { id: activePlacementId ?? null });
        setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
        void ensureProjectDraftRef.current()
          .then(() => saveProjectRef.current({ silent: true }))
          .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object placement...", track: true });
        return;
      }
      const nextPlacement: BuildingPlacement = {
        id: `building-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Building ${buildingPlacements.length + 1}`,
        type: "building",
        x: boundedX,
        y: boundedY,
        w,
        d,
        rotation: 0,
        locked: false,
        placed: true,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      console.debug("[placement] place-building-new", {
        id: nextPlacement.id,
        x: nextPlacement.x,
        y: nextPlacement.y,
        w: nextPlacement.w,
        d: nextPlacement.d,
      });
      debugLog("place-building-new", {
        id: nextPlacement.id,
        x: nextPlacement.x,
        y: nextPlacement.y,
      });
      markSystemsStale();
      setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
      void ensureProjectDraftRef.current()
        .then(() => saveProjectRef.current({ silent: true }))
        .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object placement...", track: true });
    },
    [
      activePlacementId,
      buildingPlacements.length,
      clearGeneratedPreview,
      markSystemsStale,
      resolveDefaultBuildingDims,
      resolveLotBounds,
    ],
  );

  const handlePlaceObject = useCallback(
    (id: string, position: { x: number; y: number }) => {
      clearGeneratedPreview();
      const lot = resolveLotBounds();
      if (!lot.w || !lot.h) {
        const ok = ensureSiteBoundary(
          "Place the object again to drop it on the new site.",
        );
        if (!ok) {
          setStatusMessage("Set the site width and height before placing objects.");
        }
        return;
      }
      const clampedX = Math.min(Math.max(position.x, 0), 1);
      const clampedY = Math.min(Math.max(position.y, 0), 1);
      console.debug("[placement] place-object", {
        id,
        position,
        lot,
        clampedX,
        clampedY,
      });
      debugLog("place-object", { id, clampedX, clampedY });
      setBuildingPlacements((prev) =>
        prev.map((item) => {
          if (item.id !== id) return item;
          const x = lot.x + clampedX * lot.w - item.w / 2;
          const y = lot.y + clampedY * lot.h - item.d / 2;
          if (!Number.isFinite(x) || !Number.isFinite(y)) {
            return { ...item, placed: false };
          }
          const boundedX = Math.min(Math.max(x, lot.x), lot.x + lot.w - item.w);
          const boundedY = Math.min(Math.max(y, lot.y), lot.y + lot.h - item.d);
          console.debug("[placement] place-object-commit", {
            id,
            x: boundedX,
            y: boundedY,
            w: item.w,
            d: item.d,
          });
          debugLog("place-object-commit", { id, x: boundedX, y: boundedY });
          return {
            ...item,
            x: boundedX,
            y: boundedY,
            placed: true,
            geometry:
              item.geometryType === "polyline"
                ? buildDefaultPolyline({ x: boundedX, y: boundedY, w: item.w, d: item.d })
                : item.geometry,
          };
        }),
      );
      setActivePlacementId((prev) => (prev === id ? null : prev));
      setPlacementModeEnabled(false);
      markSystemsStale();
      debugLog("place-object-complete", { id });
      setStatusMessage("Object placed. Regenerate systems to reflect the new layout.");
      void ensureProjectDraftRef.current()
        .then(() => saveProjectRef.current({ silent: true }))
        .then(() => previewRefreshIntentRef.current = { reason: "Refreshing preview after object placement...", track: true });
    },
    [buildDefaultPolyline, clearGeneratedPreview, ensureSiteBoundary, markSystemsStale, resolveLotBounds],
  );

  const handleTogglePlacementMode = useCallback(() => {
    setPlacementModeEnabled((prev) => {
      const next = !prev;
      if (next && !activePlacementId) {
        const firstUnplaced = buildingPlacements.find((item) => !item.placed);
        if (firstUnplaced) {
          setActivePlacementId(firstUnplaced.id);
        }
      }
      if (!next) {
        setActivePlacementId(null);
      }
      if (next) {
        setPreviewMode("2d");
      }
      setStatusMessage(
        next
          ? "Placement mode enabled. Click on the canvas to drop the selected object."
          : "Placement mode disabled.",
      );
      return next;
    });
  }, [activePlacementId, buildingPlacements]);

  const handleSelectPlacementTarget = useCallback((id: string) => {
    const lot = resolveLotBounds();
    if (!lot.w || !lot.h) {
      askClarification(
        "I need a site boundary before placing objects. What size should the site be?",
        "place_object_missing_site",
        { id },
      );
      return;
    }
    setPreviewMode("2d");
    setActivePlacementId(id);
    setPlacementModeEnabled(true);
    const target = buildingPlacements.find((item) => item.id === id);
    console.debug("[placement] select-target", {
      id,
      type: target?.type,
      placed: target?.placed,
    });
    setStatusMessage(
      target
        ? `Ready to place ${target.label}. Click on the canvas to drop it.`
        : "Placement active. Click on the canvas to drop the object.",
    );
  }, [askClarification, buildingPlacements, resolveLotBounds]);

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
    const placed = buildingPlacements.filter(
      (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
    );
    console.debug("[placement] state", {
      total: buildingPlacements.length,
      placed: placed.length,
      ids: placed.map((item) => item.id),
    });
  }, [buildingPlacements]);

  const handleAutoPlaceBuildings = useCallback(() => {
    const lot = resolveLotBounds();
    if (!lot.w || !lot.h) {
      setStatusMessage("Set the site width and height before auto-placing objects.");
      return;
    }
    const placed = buildingPlacements.filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y));
    const unplaced = buildingPlacements.filter((item) => !item.placed);
    if (!unplaced.length) return;

    const spacing = 20;
    let cursorX = lot.x + spacing;
    let cursorY = lot.y + spacing;
    let rowHeight = 0;
    const placedRects = placed.map((item) => ({
      x: item.x ?? 0,
      y: item.y ?? 0,
      w: item.w,
      d: item.d,
    }));

    const next = buildingPlacements.map((item) => ({ ...item }));
    const overlaps = (rect: { x: number; y: number; w: number; d: number }) =>
      placedRects.some(
        (existing) =>
          !(
            rect.x + rect.w + spacing <= existing.x ||
            existing.x + existing.w + spacing <= rect.x ||
            rect.y + rect.d + spacing <= existing.y ||
            existing.y + existing.d + spacing <= rect.y
          ),
      );

    for (const item of next) {
      if (item.placed) continue;
      let candidate = {
        x: cursorX,
        y: cursorY,
        w: item.w,
        d: item.d,
      };
      let attempts = 0;
      while (overlaps(candidate) && attempts < 5) {
        candidate.x += item.w + spacing;
        attempts += 1;
      }
      if (candidate.x + item.w > lot.x + lot.w - spacing) {
        cursorX = lot.x + spacing;
        cursorY += rowHeight + spacing;
        rowHeight = 0;
        candidate = { x: cursorX, y: cursorY, w: item.w, d: item.d };
      }
      item.x = candidate.x;
      item.y = candidate.y;
      item.placed = true;
      placedRects.push({ ...candidate });
      cursorX += item.w + spacing;
      rowHeight = Math.max(rowHeight, item.d);
    }

    setBuildingPlacements(next);
    setActivePlacementId(null);
  }, [buildingPlacements, resolveLotBounds]);

  const buildLayoutSuggestions = useCallback(() => {
    const lot = resolveLotBounds();
    const movable = buildingPlacements.filter((item) => !(item.locked && item.placed));
    if (!movable.length) return [];

    const spacing = 24;
    const makeSuggestion = (strategy: "grid" | "top" | "left") => {
      let cursorX = lot.x + spacing;
      let cursorY = lot.y + spacing;
      let rowHeight = 0;
      return buildingPlacements.map((item) => {
        if (item.locked && item.placed) return { ...item };
        if (strategy === "top") {
          const next = { ...item, placed: true, x: cursorX, y: lot.y + spacing };
          cursorX += item.w + spacing;
          return next;
        }
        if (strategy === "left") {
          const next = { ...item, placed: true, x: lot.x + spacing, y: cursorY };
          cursorY += item.d + spacing;
          return next;
        }
        const next = { ...item, placed: true, x: cursorX, y: cursorY };
        cursorX += item.w + spacing;
        rowHeight = Math.max(rowHeight, item.d);
        if (cursorX + item.w > lot.x + lot.w - spacing) {
          cursorX = lot.x + spacing;
          cursorY += rowHeight + spacing;
          rowHeight = 0;
        }
        return next;
      });
    };

    return [makeSuggestion("grid"), makeSuggestion("top"), makeSuggestion("left")];
  }, [buildingPlacements, resolveLotBounds]);

  const handleSuggestLayouts = useCallback(() => {
    const suggestions = buildLayoutSuggestions();
    if (!suggestions.length) return;
    setPlacementSuggestions(suggestions);
    setActiveSuggestionIndex(0);
    setBuildingPlacements(suggestions[0]);
  }, [buildLayoutSuggestions]);

  const handleNextSuggestion = useCallback(() => {
    if (!placementSuggestions.length) return;
    const nextIndex = (activeSuggestionIndex + 1) % placementSuggestions.length;
    setActiveSuggestionIndex(nextIndex);
    setBuildingPlacements(placementSuggestions[nextIndex]);
  }, [activeSuggestionIndex, placementSuggestions]);

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
      strategy_mode: "user",
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
      input_mode: "user",
      strict_mode: false,
      prompt_text: (promptOverride ?? prompt) || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
        system_dirty_state: systemStatuses,
        site_object_id: buildingPlacements.find((item) => item.type === "site")?.id ?? null,
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
      allow_ai_fill_for_blanks: false,
    };
  };

  const isConnectivityFailureMessage = (message: string) =>
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
  }: {
    mode: PlanToolMode;
    requestPayload: PlanRequestPayload;
    resolvedProjectId?: string | null;
    assistantPrefix?: string | null;
    clearPromptOnSuccess?: boolean;
    signal?: AbortSignal;
  }) => {
    setBusy(true);
    setActivePlanTool(mode);
    setStatusMessage(
      mode === "fix"
        ? "Civora AI is starting the fix run."
        : mode === "improve"
          ? "Civora AI is starting the improvement run."
          : "Civora AI is starting the engineering run.",
    );
    const shouldQueueStagedRun = Boolean(requestPayload?.full_design_mode && token);
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
        appendChatMessage(
          "assistant",
          [
            assistantPrefix,
            `I queued the full staged design workflow as ${queued.job.job_id} so each phase can save, pause for approval, and continue on the same project.`,
          ]
            .filter(Boolean)
            .join(" "),
          "status",
        );
        setStatusMessage(`Queued staged run ${queued.job.job_id}.`);
        if (clearPromptOnSuccess) {
          setPrompt("");
        }
        return;
      } catch (queueError) {
        const queueMessage =
          queueError instanceof Error ? queueError.message : "Job queue failed.";
        appendChatMessage("assistant", queueMessage, "status");
        setStatusMessage(queueMessage);
        return;
      } finally {
        setBusy(false);
      }
    }
    const liveRunController = new AbortController();
    const liveRunTimeoutMs = 12_000;
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
      if (clearPromptOnSuccess) {
        setPrompt("");
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "";
      if (timedOut && token) {
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
          setStatusMessage(
            `The live run was queued as ${queued.job.job_id} because the direct request took too long.`,
          );
          return;
        } catch (queueError) {
          const queueMessage =
            queueError instanceof Error ? queueError.message : "Job queue failed.";
          appendChatMessage("assistant", queueMessage, "status");
          setStatusMessage(queueMessage);
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
      if (looksLikeConnectivityFailure && token) {
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
          setStatusMessage(
            `The live run was queued as ${queued.job.job_id} because the direct request took too long.`,
          );
          return;
        } catch (queueError) {
          const queueMessage =
            queueError instanceof Error ? queueError.message : "Job queue failed.";
          appendChatMessage(
            "assistant",
            queueMessage,
            "status",
          );
          setStatusMessage(queueMessage);
          return;
        }
      }
      appendChatMessage(
        "assistant",
        error instanceof Error
          ? error.message
          : mode === "fix"
            ? "I couldn’t complete the fix pass."
            : mode === "improve"
              ? "I couldn’t complete the improvement pass."
              : "I couldn’t update the design.",
        "status",
      );
      setStatusMessage(
        error instanceof Error
          ? error.message
          : mode === "fix"
            ? "Fix pass failed."
            : mode === "improve"
              ? "Improve pass failed."
              : "Planner run failed.",
      );
    } finally {
      window.clearTimeout(timeoutId);
      signal?.removeEventListener("abort", handleAbort);
      setBusy(false);
      setActivePlanTool("run");
      directRunAbortRef.current = null;
    }
  };

  const handleRefreshWorkspace = async () => {
    if (!token) return;
    const results = await Promise.allSettled([
      refreshProjects(token),
      refreshJobs(token, { suppressError: true, force: true }),
    ]);
    const projectsFailed = results[0].status === "rejected";
    const jobsFailed = results[1].status === "rejected";
    if (!projectsFailed && !jobsFailed) {
      setStatusMessage("Workspace refreshed.");
      return;
    }
    if (!projectsFailed && jobsFailed) {
      setStatusMessage("Projects refreshed. Jobs could not be refreshed right now.");
      return;
    }
    if (projectsFailed && !jobsFailed) {
      const reason = results[0].status === "rejected" ? results[0].reason : null;
      setStatusMessage(
        reason instanceof Error ? reason.message : "Project refresh failed.",
      );
      return;
    }
    setStatusMessage("Workspace refresh failed.");
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
          "Fix the active design and focus on the most important engineering blockers.",
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

      if (
        decision.needs_clarification ||
        decision.intent === "conversation" ||
        decision.intent === "settings" ||
        decision.intent === "explain"
      ) {
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
          appendChatMessage(
            "assistant",
            queueError instanceof Error ? queueError.message : "I couldn’t queue the design request either.",
            "status",
          );
          setStatusMessage(
            queueError instanceof Error ? queueError.message : "Queued fallback failed.",
          );
          return;
        }
      }
      appendChatMessage(
        "assistant",
        error instanceof Error ? error.message : "I couldn’t process that message.",
        "status",
      );
      setStatusMessage(
        error instanceof Error ? error.message : "Civora AI could not process that message.",
      );
      setBusy(false);
      setActivePlanTool("run");
    } finally {
      runSubmissionRef.current = false;
      directRunAbortRef.current = null;
    }
  };

  const tryHandleObjectIntent = (message: string): boolean => {
    const lower = message.toLowerCase();
    const lot = resolveLotBounds();
    const addBuildingMatch = lower.match(
      /(add|create|place)\s+(a\s+)?building[^0-9]*?(\d+(\.\d+)?)\s*(ft|feet|')?\s*(x|by)\s*(\d+(\.\d+)?)/,
    );
    const addObjectMatch = lower.match(
      /(add|create|place)\s+(a\s+)?(retail building|multifamily building|industrial building|office building|pad|pool|amenity area|open space|entrance|access point|driveway|road|drive aisle|parking field|parking|sidewalk|path|basin|detention pond|outfall|inlet|manhole|hydrant|setback zone|no-build zone|utility corridor|lot block|subdivision block|bridge)\s*(\d+(\.\d+)?)?\s*(ft|feet|')?\s*(x|by)?\s*(\d+(\.\d+)?)?/,
    );
    const plotDimsMatch = lower.match(
      /(add|create|set)\s+(a\s+)?(lot|plot|site)[^0-9]*?(\d+(\.\d+)?)\s*(ft|feet|')?\s*(x|by)\s*(\d+(\.\d+)?)/,
    );
    const plotAcreMatch = lower.match(/(add|create|set)\s+(a\s+)?(\d+(\.\d+)?)\s*acre/);

    if (addBuildingMatch) {
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add buildings at scale.",
          "status",
        );
        return true;
      }
      const width = Number(addBuildingMatch[3]);
      const depth = Number(addBuildingMatch[7]);
      if (!Number.isFinite(width) || !Number.isFinite(depth)) {
        return false;
      }
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `building-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Building ${buildingPlacements.length + 1}`,
        type: "building",
        w: width,
        d: depth,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      appendChatMessage(
        "assistant",
        `Added a ${width} ft by ${depth} ft building to the placement tray. Use placement mode to drop it on the site or auto-place it.`,
        "status",
      );
      return true;
    }
    if (addObjectMatch) {
      const rawType = addObjectMatch[3];
      if (!rawType) return false;
      const typeMap: Record<string, SiteObjectType> = {
        "retail building": "retail_building",
        "multifamily building": "multifamily_building",
        "industrial building": "industrial_building",
        "office building": "office_building",
        pad: "pad",
        pool: "pool",
        "amenity area": "amenity",
        "open space": "open_space",
        entrance: "entrance",
        "access point": "entrance",
        driveway: "driveway",
        road: "road",
        "drive aisle": "road",
        "parking field": "parking",
        parking: "parking",
        sidewalk: "sidewalk",
        path: "sidewalk",
        basin: "basin",
        "detention pond": "basin",
        outfall: "outfall",
        inlet: "inlet",
        manhole: "manhole",
        hydrant: "hydrant",
        "setback zone": "setback_zone",
        "no-build zone": "no_build_zone",
        "utility corridor": "utility_corridor",
        "lot block": "lot_block",
        "subdivision block": "lot_block",
        bridge: "bridge",
      };
      const typeKey = typeMap[rawType];
      if (!typeKey) return false;
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add that object at scale.",
          "status",
        );
        return true;
      }
      const width = addObjectMatch[4] ? Number(addObjectMatch[4]) : null;
      const depth = addObjectMatch[8] ? Number(addObjectMatch[8]) : null;
      appendChatMessage("user", message);
      const catalog = SITE_OBJECT_CATALOG[typeKey];
      const nextPlacement: BuildingPlacement = {
        id: `${typeKey}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: formatObjectLabel(
          typeKey,
          buildingPlacements.filter((item) => item.type === typeKey).length + 1,
        ),
        type: typeKey,
        use: catalog?.use,
        w: width && Number.isFinite(width) ? width : catalog?.defaultW ?? 40,
        d: depth && Number.isFinite(depth) ? depth : catalog?.defaultD ?? 40,
        rotation: 0,
        locked: false,
        placed: false,
        meta: { category: catalog?.category },
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      appendChatMessage(
        "assistant",
        `Added ${nextPlacement.label} to the placement tray. Place it on the canvas when you're ready.`,
        "status",
      );
      return true;
    }
    const addBasinMatch = lower.match(
      /(add|create|place)\s+(a\s+)?(basin|detention)\s*(\d+(\.\d+)?)?\s*(ft|feet|')?\s*(x|by)?\s*(\d+(\.\d+)?)?/,
    );
    if (addBasinMatch) {
      if (!lot.w || !lot.h) {
        appendChatMessage("user", message);
        appendChatMessage(
          "assistant",
          "Set the site boundary first (width and height), then I can add a basin at scale.",
          "status",
        );
        return true;
      }
      const width = addBasinMatch[4] ? Number(addBasinMatch[4]) : 80;
      const depth = addBasinMatch[8] ? Number(addBasinMatch[8]) : 60;
      appendChatMessage("user", message);
      const nextPlacement: BuildingPlacement = {
        id: `basin-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label: `Basin ${buildingPlacements.length + 1}`,
        type: "basin",
        w: Number.isFinite(width) ? width : 80,
        d: Number.isFinite(depth) ? depth : 60,
        rotation: 0,
        locked: false,
        placed: false,
      };
      setBuildingPlacements((prev) => [...prev, nextPlacement]);
      appendChatMessage(
        "assistant",
        `Added a basin object to the placement tray. You can place it manually or auto-place it.`,
        "status",
      );
      return true;
    }
    const addEntranceMatch = lower.match(/(add|create|place)\s+(an?\s+)?entrance/);
    if (addEntranceMatch) {
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
      appendChatMessage(
        "assistant",
        "Added an entrance object to the placement tray. Place it on the canvas when ready.",
        "status",
      );
      return true;
    }
    if (plotDimsMatch) {
      const width = Number(plotDimsMatch[4]);
      const height = Number(plotDimsMatch[8]);
      if (!Number.isFinite(width) || !Number.isFinite(height)) {
        return false;
      }
      appendChatMessage("user", message);
      setLotWidth(String(width));
      setLotHeight(String(height));
      appendChatMessage(
        "assistant",
        `Set the site boundary to ${width} ft by ${height} ft.`,
        "status",
      );
      return true;
    }

    if (plotAcreMatch) {
      const acres = Number(plotAcreMatch[3]);
      if (!Number.isFinite(acres)) {
        return false;
      }
      appendChatMessage("user", message);
      const area = acres * 43560;
      const side = Math.sqrt(area);
      const width = Math.round(side);
      const height = Math.round(side);
      setLotWidth(String(width));
      setLotHeight(String(height));
      appendChatMessage(
        "assistant",
        `Set the site boundary to about ${width} ft by ${height} ft to match ${acres} acres.`,
        "status",
      );
      return true;
    }

    return false;
  };

  const tryHandleInfoIntent = (message: string): boolean => {
    const normalized = message.toLowerCase();
    const placed = buildingPlacements.filter((item) => item.placed);
    const unplaced = buildingPlacements.filter((item) => !item.placed);
    const selected = activePlacementId
      ? buildingPlacements.find((item) => item.id === activePlacementId)
      : null;

    const formatPlacement = (item: BuildingPlacement) => {
      const dims = `${item.w} ft x ${item.d} ft`;
      const position =
        item.placed && typeof item.x === "number" && typeof item.y === "number"
          ? `@ ${Math.round(item.x)} ft, ${Math.round(item.y)} ft`
          : "unplaced";
      const lockTag = item.locked ? "locked" : "unlocked";
      return `${item.label} (${item.type ?? "building"}, ${dims}, ${position}, ${lockTag})`;
    };

    if (/(what(’|')?s on the site|what is on the site|placed objects|site objects)/i.test(normalized)) {
      if (!placed.length) {
        appendChatMessage("assistant", "No objects are placed on the site yet.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Placed objects:\n${placed.map(formatPlacement).join("\n")}`,
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
        `Unplaced objects:\n${unplaced.map(formatPlacement).join("\n")}`,
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
        `Selected object: ${formatPlacement(selected)}`,
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

    if (/(blocked|why.*(drainage|utilities|grading))/i.test(normalized)) {
      if (!previewBlockedReasons.length) {
        appendChatMessage("assistant", "No blockers are currently recorded.", "status");
        return true;
      }
      appendChatMessage(
        "assistant",
        `Current blockers:\n${previewBlockedReasons.map((reason) => `- ${reason}`).join("\n")}`,
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
    const placed = buildingPlacements.filter((item) => item.placed);
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
      const label = message.replace(/^select\s+/i, "").trim();
      const target =
        findByLabel(label) ||
        allObjects.find((item) => item.label.toLowerCase().includes(label.toLowerCase()));
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

    if (/(place|re-?place|move)\b/.test(normalized)) {
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
      appendChatMessage(
        "assistant",
        "What should I fix? You can say 'fix layout overlaps', 'fix drainage', or 'improve parking'.",
        "status",
      );
      return true;
    }

    return false;
  };

  const handlePromptKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const handleSendMessage = () => {
    const trimmed = prompt.trim();
    if (!trimmed && !imageName) return;
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
        if (/(survey)/.test(lower)) {
          if (!surveyFileName) {
            appendChatMessage("assistant", "Please upload a survey/topo file first.", "status");
            return;
          }
          setUseSurveyForGrading(true);
        } else if (/(map|terrain)/.test(lower)) {
          setUseSurveyForGrading(false);
        } else if (/(assume|assumed|fallback)/.test(lower)) {
          setUseSurveyForGrading(false);
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
          void handleGenerateSystem(target);
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
      const handled = tryHandleObjectIntent(trimmed);
      if (handled) {
        setPrompt("");
        return;
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
  };

  const handleCancelActiveJob = async () => {
    if (visibleActiveJob?.job_id && token) {
      try {
        const data = await postJson<{ job: JobSummary }>(
          `/api/jobs/${visibleActiveJob.job_id}/cancel`,
          {},
          { token },
        );
        setJobs((current) => {
          const next = [...current];
          const index = next.findIndex((job) => job.job_id === data.job.job_id);
          if (index >= 0) {
            next[index] = { ...next[index], ...data.job };
          } else {
            next.unshift(data.job);
          }
          return next;
        });
        appendChatMessage("assistant", `Job ${data.job.job_id} was cancelled.`, "status");
        setStatusMessage(`Cancelled job ${data.job.job_id}.`);
        if (activeJobId === data.job.job_id) {
          setActiveJobId("");
        }
        setBusy(false);
        runSubmissionRef.current = false;
      } catch (error) {
        setStatusMessage(
          error instanceof Error ? error.message : "Job cancel failed.",
        );
      }
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

  const handleContinueActiveJob = async () => {
    if (!token) return;
    if (!visibleActiveJob?.job_id) {
      setStatusMessage("No active job is awaiting approval.");
      return;
    }
    const status = String(visibleActiveJob.status || "").toLowerCase();
    if (status !== "awaiting_approval") {
      setStatusMessage("There is no phase awaiting approval right now.");
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
      setJobs((current) => {
        const next = [...current];
        const index = next.findIndex((job) => job.job_id === data.job.job_id);
        if (index >= 0) {
          next[index] = { ...next[index], ...data.job };
        } else {
          next.unshift(data.job);
        }
        return next;
      });
      appendChatMessage(
        "assistant",
        `Approved the current phase. Starting ${nextPhaseLabel}.`,
        "status",
      );
      setStatusMessage(`Approved ${data.job.job_id}. Starting ${nextPhaseLabel}.`);
      if (data.job.job_id) {
        setActiveJobId(data.job.job_id);
        setApprovalPendingJobId(data.job.job_id);
      }
      await refreshJobs(token, { suppressError: true, force: true });
      queuePreviewRefresh("Refreshing preview after approval...");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not continue the staged run.";
      setApprovalError(message);
      setStatusMessage(message);
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
    if (!token) return null;
    if (!silent) setBusy(true);
    const effectiveProjectId =
      projectIdOverride !== undefined
        ? projectIdOverride
        : resolvedProjectIdRef.current || projectId || currentProject?.project_id || null;
    const resolvedName = (nameOverride ?? siteName).trim();
    const resolvedFileName = (fileNameOverride ?? fileName).trim();
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
      upsertProjectSummary(data.project);
      if (!silent) {
        setStatusMessage(
          `Saved project "${data.project.name || resolvedName || "Untitled Project"}".`,
        );
      }
      return data.project;
    } catch (error) {
      if (!silent) {
        setStatusMessage(
          error instanceof Error ? error.message : "Project save failed.",
        );
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
        setSiteScaleLocked(alignmentLocked);
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
      setStatusMessage("Loading project...");
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
      setPlanPreviewUrl("");
      setPlanPreviewSummary(null);
      setStatusMessage(`Loaded project "${project.name}".`);
      loadProjectResultInBackground(project);
      if (activeJobId && (!projectId || currentProjectActiveJob?.project_id === id || activeJob?.project_id === id)) {
        void loadJob(activeJobId);
      }
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Project load failed.",
      );
    } finally {
      autosaveSuspendRef.current = false;
    }
  };

  const ensureProjectDraft = async (): Promise<string | null> => {
    if (!token) return null;
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
            `${toReadableLabel(stageLabel)} stage complete. Waiting for your approval. User-controlled workflow.`,
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
            `${toReadableLabel(stageLabel)} stage complete. Waiting for your approval. User-controlled workflow.`,
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
        appendChatMessage(
          "assistant",
          job.error ?? "The background job failed before Civora could finish the design.",
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
      setStatusMessage(error instanceof Error ? error.message : "Job load failed.");
    }
  };

  const uploadImage = async (file: File) => {
    if (!token) return;
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
        site_alignment_locked: false,
      };
      const hasSite = buildingPlacements.some((item) => item.type === "site");
      if (!hasSite) {
        const acres = 10;
        const baseSide = Math.sqrt(acres * 43560);
        const aspect =
          imageSize && imageSize.width > 0 && imageSize.height > 0
            ? imageSize.width / imageSize.height
            : 1;
        const width = baseSide * Math.sqrt(aspect);
        const height = baseSide / Math.sqrt(aspect);
        setLotWidth((prev) => (prev ? prev : width.toFixed(0)));
        setLotHeight((prev) => (prev ? prev : height.toFixed(0)));
        setSiteScaleLocked(false);
        setBuildingPlacements((prev) => {
          const filtered = prev.filter((item) => item.type !== "site");
          const siteId = `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
          return [
            {
              id: siteId,
              label: "Site Boundary",
              type: "site",
              w: width,
              d: height,
              x: 0,
              y: 0,
              rotation: 0,
              locked: false,
              placed: true,
              source: "user",
              generated: false,
              capabilities: {
                movable: true,
                resizable: true,
                rotatable: true,
                deletable: false,
              },
              systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
              meta: { category: "site" },
            },
            ...filtered,
          ];
        });
        setFitToSiteRequest((value) => value + 1);
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
        },
      });
      setImageUploadState("uploaded");
      setImageUploadNote("Image uploaded. Ready for detection.");
      setStatusMessage("Image uploaded.");
      const width = parsePositiveNumber(lotWidth);
      const height = parsePositiveNumber(lotHeight);
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
      setImageUploadNote("Image upload failed.");
      setStatusMessage(
        error instanceof Error ? error.message : "Image upload failed.",
      );
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

  const uploadSurvey = async (file: File) => {
    if (!token) return;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadSurveyResponse>("/api/upload-survey", formData, {
        token,
      });
      const storedFilename = data.stored_filename || file.name;
      setSurveyFileName(storedFilename);
      setSurveyDiagnostics({
        fileType: data.file_type,
        parseSuccess: data.parse_success,
        pointCount: data.point_count,
        contourCount: data.contour_count,
        recognizedColumns: data.recognized_columns,
        invalidRows: data.invalid_rows,
        bounds: data.bounds,
        elevationRange: data.elevation_range,
        warnings: data.warnings,
      });
      let pointsResponse: SurveyPointsResponse | null = null;
      if (storedFilename && (data.file_type || "").toLowerCase() === "csv") {
        pointsResponse = await postJson<SurveyPointsResponse>(
          "/api/survey/points",
          { filename: storedFilename },
          { token },
        );
        const points = Array.isArray(pointsResponse.points) ? pointsResponse.points : [];
        setSurveyPoints(points);
        setSurveyPreviewPoints(mapSurveyPointsToSite(points));
      } else {
        setSurveyPoints([]);
        setSurveyPreviewPoints([]);
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        survey_file: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          survey_url: data.survey_url || "",
        },
        survey_file_type: data.file_type,
        survey_parse_success: data.parse_success,
        survey_point_count: pointsResponse?.point_count ?? data.point_count ?? 0,
        survey_point_columns: pointsResponse?.recognized_columns ?? data.recognized_columns ?? {},
        survey_invalid_rows: pointsResponse?.invalid_rows ?? data.invalid_rows ?? 0,
        survey_point_warnings: pointsResponse?.warnings ?? data.warnings ?? [],
        survey_points: pointsResponse?.points ?? [],
        survey_bounds: data.bounds ?? null,
        survey_elevation_range: data.elevation_range ?? null,
        use_survey_for_grading: useSurveyForGrading,
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
      setStatusMessage(data.parse_success ? "Survey uploaded and parsed." : "Survey uploaded.");
    } catch (error) {
      setSurveyFileName(file.name);
      setStatusMessage(
        error instanceof Error ? error.message : "Survey upload failed.",
      );
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
    if (!token) return;
    const sourcePath = overridePath || mapSnapshotPath;
    if (!sourcePath) {
      askClarification(
        "Upload a site image or map snapshot before running detection. Want me to open the Site Inputs panel?",
        "upload_image_then_detect",
      );
      return;
    }
    clearGeneratedPreview();
    setImageUploadState("detecting");
    setImageUploadNote("Detecting site features…");
    const width = parsePositiveNumber(lotWidth);
    const height = parsePositiveNumber(lotHeight);
    if (!width || !height) {
      askClarification(
        "I need the site boundary dimensions before detection. What size should the site be?",
        "set_site_then_detect",
      );
      setImageUploadState("uploaded");
      setImageUploadNote("Image uploaded. Set site dimensions to run detection.");
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
      setStatusMessage(result.success ? "Detection complete. Review suggested objects." : result.message || "Detection failed.");
    } catch (error) {
      setImageUploadState("failed");
      setImageUploadNote("Detection failed.");
      setStatusMessage(error instanceof Error ? error.message : "Detection failed.");
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
        const params = (item.meta as { parkingParams?: any })?.parkingParams ?? {};
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

  const applyDetectionScale = useCallback(async () => {
    const distanceFt = parsePositiveNumber(detectionScaleFeet);
    const pixelDistance = parsePositiveNumber(detectionScalePixels);
    if (!distanceFt || !pixelDistance) {
      setStatusMessage("Provide both known distance and pixel distance to calibrate.");
      return;
    }
    const scale = distanceFt / pixelDistance;
    setDetectionScaleFtPerPx(scale);
    setDetectionScaleSource("manual");
    const currentInput = currentProject?.project_input ?? payloadPreview;
    const nextSiteInputs: SiteInputs = {
      ...(currentInput?.meta?.site_inputs ?? {}),
      detection_scale: {
        distance_ft: distanceFt,
        pixel_distance: pixelDistance,
        scale_ft_per_px: scale,
        calibrated: true,
        scale_source: "manual" as const,
      },
      site_alignment_locked: siteScaleLocked,
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
    setStatusMessage("Detection scale calibrated.");
  }, [currentProject, detectionScaleFeet, detectionScalePixels, payloadPreview, saveProject]);

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

  const handleToggleSiteLock = useCallback(() => {
    const next = !siteScaleLocked;
    setSiteScaleLocked(next);
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
            site_alignment_locked: next,
          },
        },
      },
    });
    setBuildingPlacements((prevPlacements) =>
      prevPlacements.map((item) =>
        item.type === "site"
          ? {
              ...item,
              locked: next,
              capabilities: {
                ...item.capabilities,
                movable: !next,
                resizable: !next,
                rotatable: !next,
              },
            }
          : item,
      ),
    );
    setStatusMessage(next ? "Site alignment locked." : "Site alignment unlocked.");
  }, [currentProject, payloadPreview, saveProject]);

  const estimateSurveySlope = async () => {
    if (!token || !surveyFileName) return;
    try {
      const pointsData = await postJson<SurveyPointsResponse>(
        "/api/survey/points",
        { filename: surveyFileName },
        { token },
      );
      const data = await postJson<SurveySlopeResponse>(
        "/api/survey/estimate-slope",
        { filename: surveyFileName },
        { token },
      );
      setSurveySlopeEstimate(data);
      if (data.slope_percent) {
        setMinSlopePct(String(data.slope_percent.toFixed(2)));
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        slope_estimate: data,
        survey_points: Array.isArray(pointsData.points) ? pointsData.points : [],
        survey_point_count: pointsData.point_count ?? (Array.isArray(pointsData.points) ? pointsData.points.length : 0),
        survey_point_warnings: pointsData.warnings ?? [],
        survey_point_columns: pointsData.recognized_columns ?? {},
        survey_invalid_rows: pointsData.invalid_rows ?? 0,
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          manual_fields: {
            ...(currentInput?.manual_fields ?? {}),
            grading: {
              ...(currentInput?.manual_fields?.grading ?? {}),
              min_slope_pct: data.slope_percent ?? currentInput?.manual_fields?.grading?.min_slope_pct,
            },
            terrain: data.direction && data.slope_percent
              ? `Estimated ${data.slope_percent.toFixed(2)}% slope toward ${data.direction}`
              : currentInput?.manual_fields?.terrain,
          },
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Slope estimated from survey.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Slope estimation failed.",
      );
    }
  };

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

  const saveSiteAddress = async () => {
    if (!token) return;
    const trimmed = siteAddress.trim();
    const hasSite = buildingPlacements.some((item) => item.type === "site");
    const currentInput = currentProject?.project_input ?? payloadPreview;
    const currentLotWidth = parsePositiveNumber(lotWidth);
    const currentLotHeight = parsePositiveNumber(lotHeight);
    const nextSiteInputs = {
      ...(currentInput?.meta?.site_inputs ?? {}),
      address: trimmed || undefined,
    };
    if (!trimmed) {
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
      setStatusMessage("Site address cleared.");
      return;
    }
    clearGeneratedPreview();
    try {
      const geocode = await postJson<{ lat: number; lng: number; display_name: string; provider: string }>(
        "/api/geocode",
        { address: trimmed },
        { token },
      );
      nextSiteInputs.geocode = {
        lat: geocode.lat,
        lng: geocode.lng,
        display_name: geocode.display_name,
        provider: geocode.provider,
      };
      nextSiteInputs.site_alignment_locked = false;
      const acres = 10;
      const side = Math.sqrt(acres * 43560);
      let nextSiteId: string | null = null;
      if (!hasSite) {
        setLotWidth((prev) => (prev ? prev : side.toFixed(0)));
        setLotHeight((prev) => (prev ? prev : side.toFixed(0)));
        setSiteScaleLocked(false);
        setBuildingPlacements((prev) => {
          const filtered = prev.filter((item) => item.type !== "site");
          const siteId = `site-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
          nextSiteId = siteId;
          return [
            ...filtered,
            {
              id: siteId,
              label: geocode.display_name || "Site Boundary",
              type: "site",
              w: currentLotWidth ?? side,
              d: currentLotHeight ?? side,
              x: 0,
              y: 0,
              rotation: 0,
              locked: false,
              placed: true,
              source: "user",
              generated: false,
              capabilities: {
                movable: true,
                resizable: true,
                rotatable: true,
                deletable: false,
              },
              systemDependencies: ["roads", "parking", "grading", "drainage", "utilities"],
              meta: { category: "site" },
            },
          ];
        });
        setFitToSiteRequest((value) => value + 1);
      } else {
        const existingSite = buildingPlacements.find((item) => item.type === "site");
        nextSiteId = existingSite?.id ?? null;
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
              w: currentLotWidth ?? side,
              h: currentLotHeight ?? side,
            },
          },
        },
      });
      if (nextSiteId) {
        setFocusObjectId(nextSiteId);
      }
      setFitToSiteRequest((value) => value + 1);
      setStatusMessage("Site address saved and site boundary initialized.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Geocoding failed.",
      );
    }
  };

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
    if (options?.track) {
      setPreviewRefreshing(true);
      setPreviewRefreshNote((prev) => prev || "Refreshing preview...");
    }
    const previewPayload = {
      ...payload,
      preview_quality: previewQuality,
      label_density: previewLabelDensity,
      render_labels: previewInteraction === "interactive" || previewQuality === "high",
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

  const siteInputs = (currentProject?.project_input?.meta?.site_inputs ?? {}) as SiteInputs;

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
    const context =
      issue.context && typeof issue.context === "object"
        ? (issue.context as Record<string, unknown>)
        : null;
    const explanation =
      typeof context?.explanation === "string"
        ? String(context.explanation)
        : null;
    const bestNextFix =
      typeof context?.best_next_fix === "string"
        ? String(context.best_next_fix)
        : null;
    const suggested =
      Array.isArray(context?.suggested_actions)
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
        return Boolean(pickBestLowPoint());
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
    }) => {
      if (!ensureSiteLocked("drainage")) return;
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

      const drainagePayload: PlanRequestPayload = {
        ...requestPayload,
        manual_fields: nextManualFields,
        meta: {
          ...(requestPayload.meta ?? {}),
          requested_system: "drainage",
        },
        prompt_text: null,
      };
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
          const deadline = Date.now() + 120_000;
          while (Date.now() < deadline) {
            const jobState = await getJson<{ job: JobSummary }>(
              `/api/jobs/${jobId}`,
              { token },
            );
            const status = String(jobState.job?.status || "");
            if (status === "completed") break;
            if (status === "failed" || status === "cancelled") {
              throw new Error(jobState.job?.error || "Drainage job failed.");
            }
            await new Promise((resolve) => window.setTimeout(resolve, 2000));
          }
          if (targetProjectId) {
            loadProjectResultInBackground({
              project_id: targetProjectId,
              name: currentProject?.name || siteName || "Untitled Project",
            } as ProjectRecord);
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : "Drainage autofix failed.";
          appendChatMessage("assistant", message, "status");
          setStatusMessage(message);
        }
      } else {
        await executePlanAction({
          mode: "run",
          requestPayload: drainagePayload,
          assistantPrefix: "Applying drainage fix…",
        });
      }
      setSystemStatuses((prev) => ({ ...prev, drainage: "fresh" }));
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
    ],
  );

  const handleGenerateSystem = useCallback(
    async (target: "roads" | "parking" | "grading" | "drainage" | "utilities" | "full") => {
      if (!hasSiteBoundary()) {
        askClarification(
          "I need a site boundary before generating systems. What size should the site be?",
          "set_site_then_generate",
          { target },
        );
        return;
      }
      if (!ensureSiteLocked(target)) {
        return;
      }
      const hasBasin =
        target === "drainage" || target === "full"
          ? buildingPlacements.some((item) => item.type === "basin" && item.placed)
          : true;
      if (!hasBasin && (target === "drainage" || target === "full")) {
        askClarification(
          "Drainage needs a basin or outfall target. Do you want me to add a basin object for you?",
          "drainage_missing_basin",
          { target },
        );
        return;
      }
      if (target === "roads") {
        const hasRoadAnchor = buildingPlacements.some((item) =>
          ["road", "driveway", "entrance", "building"].includes(item.type ?? ""),
        );
        if (!hasRoadAnchor) {
          setStatusMessage("Add a building or entrance before generating roads.");
          return;
        }
      }
      if (target === "grading" || target === "drainage" || target === "full") {
        const hasSurvey = Boolean(surveyFileName) && useSurveyForGrading;
        const hasMapTerrain = Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng);
        if (!hasSurvey && !hasMapTerrain && !surveySlopeEstimate?.slope_percent) {
          askClarification(
            "I need a terrain source for grading. Use survey, map terrain, or a first‑pass assumed slope?",
            "grading_source",
            { target },
          );
          return;
        }
      }
      const requestPayload = buildPayloadFromOverrides({}, undefined, projectId || null);
      const omitField = { source: "omit", value: null } as const;
      const nextManualFields = {
        ...(requestPayload.manual_fields ?? {}),
      } as Record<string, unknown>;

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
      await executePlanAction({
        mode: "run",
        requestPayload: {
          ...requestPayload,
          manual_fields: nextManualFields,
          meta: {
            ...(requestPayload.meta ?? {}),
            requested_system: target,
          },
          prompt_text: null,
        },
        assistantPrefix: `Generating ${systemLabel} around your placed layout...`,
      });
      setSystemStatuses((prev) => {
        if (target === "full") {
          return {
            roads: "fresh",
            parking: "fresh",
            grading: "fresh",
            drainage: "fresh",
            utilities: "fresh",
          };
        }
        return {
          ...prev,
          [target]: "fresh",
        };
      });
    },
    [
      askClarification,
      buildPayloadFromOverrides,
      buildingPlacements,
      executePlanAction,
      hasSiteBoundary,
      ensureSiteLocked,
      projectId,
      siteInputs?.geocode?.lat,
      siteInputs?.geocode?.lng,
      surveyFileName,
      surveySlopeEstimate?.slope_percent,
      useSurveyForGrading,
    ],
  );

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
        await runDrainageAutofix({ placementsOverride: [...buildingPlacements, inletPlacement], forcedInlets: nextForced });
        setStatusMessage("Applied inlet placement. Drainage regenerated.");
        return;
      }

      if (issueCode === "ORPHAN_INLETS") {
        if (drainageConnectOrphans) {
          setStatusMessage("Orphan inlet connection already queued. Regenerate drainage to apply.");
          return;
        }
        setDrainageConnectOrphans(true);
        await runDrainageAutofix({ connectOrphans: true });
        setStatusMessage("Applied orphan inlet connection. Drainage regenerated.");
        return;
      }

      if (issueCode === "POOR_SLOPE") {
        if (drainageAllowSlopeAdjust) {
          setStatusMessage("Slope adjustment already queued. Regenerate drainage to apply.");
          return;
        }
        setDrainageAllowSlopeAdjust(true);
        await runDrainageAutofix({ allowSlopeAdjust: true });
        setStatusMessage("Applied slope adjustment attempt. Drainage regenerated.");
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
        await runDrainageAutofix({
          placementsOverride: nextPlacements,
          forcedBasins,
        });
        setStatusMessage("Applied basin placement. Drainage regenerated.");
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
    if (!token) return;
    previewRefreshIntentRef.current = { reason, track: true };
  };

  const handlePreviewPlan = async () => {
    if (!token) return;
    setStatusMessage("Refreshing preview...");
    setBusy(true);
    try {
      await requestPreview(artifactPayload, { track: true });
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Preview generation failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleExplainPlan = () => {
    const explanationText =
      typeof currentExplanation?.summary === "string"
        ? currentExplanation.summary
        : typeof currentExplanation?.overview === "string"
          ? currentExplanation.overview
          : typeof selectedRun?.message === "string"
            ? selectedRun.message
            : "";
    const fallbackDetails = [
      currentManualFailures.length
        ? `Current blockers: ${currentManualFailures
            .slice(0, 3)
            .map((failure) => failure.code || failure.message || "manual validation issue")
            .join(", ")}.`
        : null,
      issues.length
        ? `Current warnings: ${issues
            .slice(0, 3)
            .map((issue) => issue.message)
            .join("; ")}.`
        : null,
      currentTruthAudit?.success === true
        ? "Truth checks are currently passing."
        : currentTruthAudit?.success === false
          ? "Truth checks still need review."
          : null,
    ]
      .filter(Boolean)
      .join(" ");

    if (!explanationText && !fallbackDetails) {
      setStatusMessage("Run Civora AI first so there is a plan to explain.");
      return;
    }

    appendChatMessage(
      "assistant",
      [
        explanationText || "Here’s where the current design stands.",
        typeof currentExplanation?.why === "string" ? currentExplanation.why : null,
        fallbackDetails || null,
      ]
        .filter(Boolean)
        .join(" "),
      "explanation",
    );
    setStatusMessage("Added the latest plan explanation to the conversation.");
  };

  const handleRunFix = () => {
    void runOrchestrator("fix");
  };

  const handleRunImprove = () => {
    void runOrchestrator("improve");
  };

  const resetWorkspaceState = useCallback(() => {
    debugLog("reset-workspace");
    setPlanPreviewUrl("");
    setPlanPreviewSummary(null);
    setPlanPreviewAnnotations(null);
    setPreviewRefreshing(false);
    setPreviewRefreshNote(null);
    setBackendResult(null);
    setUploadedImageApiUrl("");
    setUploadedImagePreviewUrl("");
    setImageUploadState("idle");
    setImageUploadNote(null);
    setSurveyFileName("");
    setSurveySlopeEstimate(null);
    setSurveyPoints([]);
    setSurveyPreviewPoints([]);
    setSurveyDiagnostics(null);
    setUseSurveyForGrading(true);
    setMapSnapshotPath("");
    setMapAnalysis(null);
    setSiteAddress("");
    setBuildingPlacements([]);
    setDetectedPlacements([]);
    setDetectionScaleFeet("");
    setDetectionScalePixels("");
    setDetectionScaleFtPerPx(null);
    setDetectionScaleSource("approximate");
    setSiteScaleLocked(false);
    setShowAdvancedCalibration(false);
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
  }, []);

  const handleNewProject = async () => {
    debugLog("new-project-start");
    projectLoadRequestRef.current += 1;
    suppressProjectAutoLoadRef.current = true;
    draftProjectPromiseRef.current = null;
    resolvedProjectIdRef.current = "";
    setProjectId("");
    setCurrentProject(null);
    setSelectedRunId("");
    setActiveJobId("");
    setPrompt("");
    setImageName("");
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
    const nextThread = [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(getChatThreadStorageKey("draft"));
      } catch {
        // Ignore local storage failures.
      }
    }
    setStatusMessage("Started a new project.");
    try {
      if (token) {
        draftProjectPromiseRef.current = saveProject({
          silent: true,
          projectIdOverride: null,
          nameOverride: "",
          fileNameOverride: "",
          projectInputOverride: {
            input_mode: "user",
            strict_mode: false,
            prompt_text: null,
            image_path: null,
            meta: {
              chat_thread: [createWelcomeMessage()],
              auto_named: false,
              auto_file_named: false,
            },
            manual_fields: {
              project_name: "",
              file_name: "",
              units: "ft",
              project_type: "",
              lot: { x: 0, y: 0, w: 0, h: 0 },
              setback: 0,
              building_width: 0,
              building_depth: 0,
              site_plan: { parking_count: 0 },
              disciplines: ["corridor", "grading", "drainage", "utility"],
            },
            allow_ai_fill_for_blanks: false,
          },
          latestResultOverride: {},
          autoNamedOverride: false,
          autoFileNamedOverride: false,
        });
        const createdProject = await draftProjectPromiseRef.current;
        if (createdProject?.project_id) {
          resolvedProjectIdRef.current = createdProject.project_id;
          setProjectId(createdProject.project_id);
          debugLog("new-project-created", { projectId: createdProject.project_id });
        }
      }
    } finally {
      draftProjectPromiseRef.current = null;
      suppressProjectAutoLoadRef.current = false;
    }
  };

  const handleDeleteProject = async (projectIdToDelete: string) => {
    if (!token) return;
    const target = projects.find((item) => item.project_id === projectIdToDelete);
    const confirmed = window.confirm(
      `Delete "${target?.name || "Untitled Project"}"? This cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      setStatusMessage("Deleting project...");
      await deleteJson<{ success: boolean }>(`/api/projects/${projectIdToDelete}`, {
        token,
      });
      if (typeof window !== "undefined") {
        try {
          window.localStorage.removeItem(getChatThreadStorageKey(projectIdToDelete));
        } catch {
          // Ignore local storage failures.
        }
      }
      removeProjectSummary(projectIdToDelete);
      if (currentProject?.project_id === projectIdToDelete || projectId === projectIdToDelete) {
        const remaining = projects.filter(
          (item) => item.project_id !== projectIdToDelete,
        );
        if (remaining.length) {
          const next = [...remaining].sort(
            (a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0),
          )[0];
          if (next?.project_id) {
            await loadProject(next.project_id);
          }
        } else {
          await handleNewProject();
        }
      }
      setStatusMessage("Project deleted.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Could not delete project.",
      );
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleExportDxf = async () => {
    if (!token) return;
    if (!backendResult && !projectId) {
      setStatusMessage("Run the planner first so there is something to export.");
      return;
    }
    setBusy(true);
    try {
      const { blob, filename } = await postBinary(
        "/api/export/dxf",
        artifactPayload,
        { token },
      );
      downloadBlob(blob, filename ?? "civora-ai-plan.dxf");
      setStatusMessage("DXF export downloaded.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "DXF export failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleExportReport = async () => {
    if (!token) return;
    if (!backendResult && !projectId) {
      setStatusMessage("Run the planner first so there is something to export.");
      return;
    }
    setBusy(true);
    try {
      const { blob, filename } = await postBinary(
        "/api/export/report",
        artifactPayload,
        { token },
      );
      downloadBlob(blob, filename ?? "civora-ai-report.json");
      setStatusMessage("Report export downloaded.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Report export failed.",
      );
    } finally {
      setBusy(false);
    }
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
    previewCompletedPhaseCount,
    previewTotalPhaseCount,
    previewRunningPhase,
    previewNextPendingPhase,
  } = usePreviewReview({ currentPlanMeta, planPreviewSummary });
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

  const previewLayersEffective = useMemo(() => {
    if (!gatingPhaseKey) return previewLayers;
    switch (gatingPhaseKey) {
      case "layout":
        return { ...previewLayers, grading: false, drainage: false, utilities: false };
      case "grading":
        return { ...previewLayers, drainage: false, utilities: false };
      case "drainage_storm":
        return { ...previewLayers, grading: false, utilities: false };
      case "utilities":
        return { ...previewLayers, grading: false, drainage: false };
      default:
        return previewLayers;
    }
  }, [gatingPhaseKey, previewLayers]);

  const previewLayerList = useMemo(() => {
    const layers = new Set<string>();
    if (previewLayersEffective.buildings) {
      [
        "BUILDING",
        "STRUCTURE",
        "PAD",
        "C-BUILDING",
        "C-BOUNDARY",
        "C-SETBACK",
      ].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.roads) {
      [
        "ROAD",
        "PAVEMENT",
        "PARKING",
        "WALK",
        "C-ROAD",
        "C-PAVEMENT",
        "C-PARKING",
        "C-DRIVEWAY",
        "C-SIDEWALK",
        "C-CENTERLINE",
      ].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.grading) {
      [
        "SURFACE",
        "FG_CONTOUR",
        "EG_CONTOUR",
        "SPOT_FG",
        "DRAIN_FLOW",
        "FLOW_ARROW",
        "C-CONTOUR",
        "C-SPOT-ELEV",
        "C-GRADING",
        "C-CUT",
        "C-FILL",
      ].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.drainage) {
      [
        "DRAIN",
        "PIPE",
        "STORM",
        "BASIN_BOUNDARY",
        "C-STRM-PIPE",
        "C-STRM-INLET",
        "C-STRM-MH",
        "C-DRAIN-FLOW",
        "C-LOW-POINT",
        "C-POND",
      ].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.utilities) {
      ["UTILITY", "WATER", "SAN", "C-WATR", "C-SAN", "C-UTIL", "C-HYDRANT"].forEach((layer) =>
        layers.add(layer),
      );
    }
    if (previewLayersEffective.structures) {
      ["BRIDGE", "POOL", "STRUCTURE"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.lots) {
      ["LOT", "OPEN_SPACE", "EASEMENT"].forEach((layer) => layers.add(layer));
    }
    return Array.from(layers);
  }, [previewLayersEffective]);

  useEffect(() => {
    if (!token) return;
    if (!backendResult && !planPreviewUrl && !projectId) return;
    const intent = previewRefreshIntentRef.current;
    if (intent) {
      previewRefreshIntentRef.current = null;
      setPreviewRefreshNote(intent.reason);
      requestPreviewInBackground(artifactPayload, {
        silentStatus: true,
        track: intent.track,
      });
      return;
    }
    requestPreviewInBackground(artifactPayload, { silentStatus: true });
  }, [
    previewQuality,
    previewLabelDensity,
    previewInteraction,
    previewLayerList,
    planPreviewUrl,
    token,
    artifactPayload,
    backendResult,
  ]);

  useEffect(() => {
    if (previewLabelDensityTouched) return;
    setPreviewLabelDensity(previewQuality === "high" ? "high" : "standard");
  }, [previewLabelDensityTouched, previewQuality]);

  const hasGradingSurface = useMemo(() => {
    const gradingMeta =
      (backendResult?.final_plan?.meta as { grading?: Record<string, unknown> } | undefined)?.grading ??
      (backendResult?.metadata as { grading_summary?: Record<string, unknown> } | undefined)?.grading_summary ??
      (backendResult?.metadata as { grading?: Record<string, unknown> } | undefined)?.grading ??
      null;
    if (!gradingMeta || typeof gradingMeta !== "object") return false;
    const record = gradingMeta as Record<string, unknown>;
    return Boolean(
      record.proposed_surface ||
        record.existing_surface ||
        (record.surface_controls as { grade_range_ft?: number } | undefined)?.grade_range_ft,
    );
  }, [backendResult]);

  const preview3DItems = useMemo<Preview3DItem[]>(() => {
    const actions = Array.isArray(backendResult?.final_plan?.actions)
      ? backendResult.final_plan.actions
      : [];
    const items: Preview3DItem[] = [];
    const gradingMeta =
      (backendResult?.final_plan?.meta as { grading?: Record<string, unknown> } | undefined)?.grading ??
      (backendResult?.metadata as { grading_summary?: Record<string, unknown> } | undefined)?.grading_summary ??
      (backendResult?.metadata as { grading?: Record<string, unknown> } | undefined)?.grading ??
      null;
    const surfaceControls =
      gradingMeta && typeof gradingMeta === "object"
        ? ((gradingMeta as { surface_controls?: Record<string, unknown> }).surface_controls ?? {})
        : {};
    const surfaceGuidance =
      gradingMeta && typeof gradingMeta === "object"
        ? ((gradingMeta as { surface_guidance?: Record<string, unknown> }).surface_guidance ?? {})
        : {};
    const gradeRangeFt = Number(
      (surfaceControls as { grade_range_ft?: number }).grade_range_ft ?? 0,
    );
    const downhillVector =
      (surfaceGuidance as { downhill_vector?: { x?: number; y?: number; dx?: number; dy?: number } })
        .downhill_vector ?? null;
    const baseTerrain = {
      minX: Number.POSITIVE_INFINITY,
      minY: Number.POSITIVE_INFINITY,
      maxX: Number.NEGATIVE_INFINITY,
      maxY: Number.NEGATIVE_INFINITY,
    };

    const addBounds = (bounds: [number, number, number, number]) => {
      baseTerrain.minX = Math.min(baseTerrain.minX, bounds[0]);
      baseTerrain.minY = Math.min(baseTerrain.minY, bounds[1]);
      baseTerrain.maxX = Math.max(baseTerrain.maxX, bounds[2]);
      baseTerrain.maxY = Math.max(baseTerrain.maxY, bounds[3]);
    };

    const elevationAt = (x: number, y: number) => {
      if (!gradeRangeFt) return 0;
      const spanX = Math.max(baseTerrain.maxX - baseTerrain.minX, 1);
      const spanY = Math.max(baseTerrain.maxY - baseTerrain.minY, 1);
      const nx = (x - baseTerrain.minX) / spanX - 0.5;
      const ny = (y - baseTerrain.minY) / spanY - 0.5;
      const dirX = Number(downhillVector?.x ?? downhillVector?.dx ?? 0);
      const dirY = Number(downhillVector?.y ?? downhillVector?.dy ?? -1);
      const norm = Math.hypot(dirX, dirY) || 1;
      const dot = (nx * dirX + ny * dirY) / norm;
      return dot * gradeRangeFt;
    };

    for (const action of actions) {
      if (!action || typeof action !== "object") continue;
      const actionRecord = action as Record<string, unknown>;
      const task = String(actionRecord.task || "").toLowerCase();
      const layerRaw = String(actionRecord.layer || "").toUpperCase();
      const normalizedLayer = layerRaw.startsWith("C-") ? layerRaw.slice(2) : layerRaw;
      const meta = actionRecord.meta as Record<string, unknown> | undefined;
      const previewRole = String(meta?.preview_role || (meta?.is_final ? "final" : "overlay"));
      if (previewRole !== "final") continue;

      let bounds: [number, number, number, number] | null = null;
      if (task === "rectangle") {
        const origin = Array.isArray(actionRecord.origin) ? (actionRecord.origin as number[]) : [];
        const width = Number(actionRecord.width || 0);
        const height = Number(actionRecord.height || 0);
        if (origin.length >= 2 && width > 0 && height > 0) {
          bounds = [Number(origin[0]), Number(origin[1]), Number(origin[0]) + width, Number(origin[1]) + height];
        }
      } else if (task === "polygon" || task === "polyline") {
        const points = Array.isArray(actionRecord.points) ? (actionRecord.points as number[][]) : [];
        if (points.length >= 2) {
          const xs = points.map((pt) => Number((pt as number[])[0] || 0));
          const ys = points.map((pt) => Number((pt as number[])[1] || 0));
          bounds = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
        }
      }
      if (!bounds) continue;

      addBounds(bounds);
      const [x1, y1, x2, y2] = bounds;
      const w = Math.max(1, x2 - x1);
      const h = Math.max(1, y2 - y1);
      const centerX = x1 + w / 2;
      const centerY = y1 + h / 2;
      const label = String(actionRecord.label || normalizedLayer);
      const system = String(meta?.system || "");
      const isBuilding = normalizedLayer === "BUILDING";
      const isRoad = ["ROAD", "PAVEMENT", "DRIVEWAY", "WALK", "SIDEWALK"].includes(normalizedLayer) || system === "roads";
      const isParking = normalizedLayer === "PARKING" || system === "parking";
      const isStructure = ["BRIDGE", "POOL", "STRUCTURE"].includes(normalizedLayer);
      const isDrainage = ["POND", "DRAIN_FLOW", "STRM-PIPE", "STRM-INLET", "STRM-MH"].includes(normalizedLayer) || system === "drainage";
      const isUtility = ["SAN", "UTIL", "WATR", "WATER"].includes(normalizedLayer) || system === "utilities";

      if (isBuilding && !previewLayersEffective.buildings) continue;
      if ((isRoad || isParking) && !previewLayersEffective.roads) continue;
      if (isDrainage && !previewLayersEffective.drainage) continue;
      if (isUtility && !previewLayersEffective.utilities) continue;
      if (isStructure && !previewLayersEffective.structures) continue;

      const color = isBuilding
        ? "#e2e8f0"
        : isStructure
          ? "#fde68a"
          : isDrainage
            ? "#bbf7d0"
            : isUtility
              ? "#fbcfe8"
              : isRoad || isParking
                ? "#c7d2fe"
                : "#dbeafe";
      const heightFt = isBuilding ? 28 : isStructure ? 10 : isDrainage ? 4 : isRoad ? 2 : isParking ? 1.5 : 1;
      const elevationOffset = elevationAt(centerX, centerY);
      const pondAdjustment = normalizedLayer === "POND" ? Math.max(1.5, gradeRangeFt * 0.12) : 0;
      items.push({
        x: x1,
        y: y1,
        w,
        h,
        height: heightFt,
        z: elevationOffset - pondAdjustment,
        color,
        label: label || normalizedLayer,
        layer: isBuilding ? "BUILDING" : isStructure ? "STRUCTURE" : isRoad ? "ROAD" : "PARKING",
      });
    }

    if (
      Number.isFinite(baseTerrain.minX) &&
      Number.isFinite(baseTerrain.minY) &&
      Number.isFinite(baseTerrain.maxX) &&
      Number.isFinite(baseTerrain.maxY)
    ) {
      const terrainWidth = Math.max(1, baseTerrain.maxX - baseTerrain.minX);
      const terrainHeight = Math.max(1, baseTerrain.maxY - baseTerrain.minY);
      const terrainZ = gradeRangeFt ? -gradeRangeFt * 0.4 : 0;
      items.unshift({
        x: baseTerrain.minX,
        y: baseTerrain.minY,
        w: terrainWidth,
        h: terrainHeight,
        height: 1,
        z: terrainZ,
        color: "#e5e7eb",
        label: "Terrain",
        layer: "TERRAIN",
      });
    }
    return items;
  }, [backendResult, previewLayersEffective]);
  const preview3DAnnotationItems = useMemo<Preview3DItem[]>(() => {
    const labels = Array.isArray(planPreviewAnnotations?.labels)
      ? planPreviewAnnotations?.labels
      : [];
    if (!labels.length) return [];
    const items: Preview3DItem[] = [];
    const scale = 100;
    for (const label of labels) {
      const bounds = (label as { bounds?: { x1?: number; y1?: number; x2?: number; y2?: number } })
        .bounds;
      if (!bounds) continue;
      const x1 = Number(bounds.x1 ?? 0);
      const y1 = Number(bounds.y1 ?? 0);
      const x2 = Number(bounds.x2 ?? 0);
      const y2 = Number(bounds.y2 ?? 0);
      const w = Math.max(0.01, (x2 - x1) * scale);
      const h = Math.max(0.01, (y2 - y1) * scale);
      const layer = String((label as { layer?: string }).layer || "").toUpperCase();
      const isBuilding = layer === "BUILDING";
      const isRoad = ["ROAD", "PAVEMENT", "PARKING", "WALK"].includes(layer);
      const isDrainage = ["DRAIN", "PIPE", "STORM", "BASIN_BOUNDARY"].includes(layer);
      const isUtility = ["SAN", "UTILITY", "WATER"].includes(layer);
      const isStructure = ["STRUCTURE", "BRIDGE", "POOL"].includes(layer);
      const isLot = layer === "LOT";

      if (isBuilding && !previewLayersEffective.buildings) continue;
      if (isRoad && !previewLayersEffective.roads) continue;
      if (isDrainage && !previewLayersEffective.drainage) continue;
      if (isUtility && !previewLayersEffective.utilities) continue;
      if (isStructure && !previewLayersEffective.structures) continue;
      if (isLot && !previewLayersEffective.lots) continue;

      const color = isBuilding
        ? "#e2e8f0"
        : isStructure
          ? "#fde68a"
          : isRoad
            ? "#c7d2fe"
            : isDrainage
              ? "#bbf7d0"
              : isUtility
                ? "#fbcfe8"
                : isLot
                  ? "#e2e8f0"
                  : "#dbeafe";
      const heightFt = isBuilding ? 26 : isStructure ? 8 : isRoad ? 2 : 1;
      items.push({
        x: x1 * scale,
        y: y1 * scale,
        w,
        h,
        height: heightFt,
        color,
        label: String((label as { label?: string }).label || layer || "Shape"),
        layer: isBuilding ? "BUILDING" : isStructure ? "STRUCTURE" : isRoad ? "ROAD" : "PARKING",
      });
    }
    return items;
  }, [planPreviewAnnotations, previewLayersEffective]);
  const preview3DEffectiveItems = preview3DItems.length
    ? preview3DItems
    : preview3DAnnotationItems;
  const usingAnnotation3D =
    preview3DItems.length === 0 && preview3DAnnotationItems.length > 0;
  const lotBounds = resolveLotBounds();
  const missingSite = !(lotBounds.w && lotBounds.h);
  const missingImage = !mapSnapshotPath;
  const hasBasinPlaced = buildingPlacements.some((item) => item.type === "basin" && item.placed);
  const hasTerrainSource =
    (Boolean(surveyFileName) && useSurveyForGrading) ||
    Boolean(siteInputs?.geocode?.lat && siteInputs?.geocode?.lng) ||
    Boolean(surveySlopeEstimate?.slope_percent);
  const gradingSourceSummary = useMemo(() => {
    const hasSurvey = Boolean(siteInputs?.survey_file?.stored_filename || siteInputs?.survey_file?.survey_url);
    const hasMapAnalysis = Boolean(siteInputs?.map_analysis);
    const hasMapSnapshot = Boolean(siteInputs?.map_snapshot?.stored_filename || siteInputs?.map_snapshot?.image_path);
    const hasAddress = Boolean(siteInputs?.address);
    if (hasSurvey) {
      return "Survey/topo (highest trust)";
    }
    if (hasMapAnalysis || hasMapSnapshot) {
      return "Image/map inferred (approximate)";
    }
    if (hasAddress) {
      return "Address-only context (approximate)";
    }
    return "Fallback assumptions";
  }, [siteInputs]);
  const drainageSurfaceSummary = useMemo(() => {
    if (!drainageSummary || typeof drainageSummary !== "object") {
      return {
        surfaceSource: "unknown",
        surfaceQuality: "",
        surfaceDetail: "",
        surfaceFromGrading: false,
      };
    }
    const guidance = (drainageSummary as { surface_guidance?: Record<string, unknown> }).surface_guidance ?? {};
    const surfaceSource = String(guidance.surface_source || "unknown");
    const surfaceQuality = String(guidance.surface_source_quality || "");
    const surfaceDetail = String(guidance.surface_source_detail || "");
    const surfaceFromGrading = Boolean(guidance.surface_from_grading);
    return { surfaceSource, surfaceQuality, surfaceDetail, surfaceFromGrading };
  }, [drainageSummary]);
  const mapAnalysisCounts = useMemo(() => {
    if (!mapAnalysis || typeof mapAnalysis !== "object") return { zones: 0, objects: 0, centerlines: 0 };
    const record = mapAnalysis as { counts?: { zones?: number; objects?: number; centerlines?: number } };
    return {
      zones: record.counts?.zones ?? 0,
      objects: record.counts?.objects ?? 0,
      centerlines: record.counts?.centerlines ?? 0,
    };
  }, [mapAnalysis]);
  const selectedAccessIssue = useMemo(
    () => analysisIssues.find((issue) => issue.id === analysisSelectedIssueId) ?? null,
    [analysisIssues, analysisSelectedIssueId],
  );
  const confirmedObjectCounts = useMemo(() => {
    const confirmed = buildingPlacements.filter(
      (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
    );
    const buildingTypes = new Set<SiteObjectType>([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
    ]);
    const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
    return {
      buildings: confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType)).length,
      access: confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType)).length,
    };
  }, [buildingPlacements]);
  const buildAnalysisReport = useCallback(
    (selectedOnly: boolean) => {
      const confirmed = buildingPlacements.filter(
        (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
      );
      const buildingTypes = new Set<SiteObjectType>([
        "building",
        "retail_building",
        "multifamily_building",
        "industrial_building",
        "office_building",
        "pad",
      ]);
      const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
      const buildings = confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType));
      const access = confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType));
      const selectedIssue = selectedOnly
        ? analysisIssues.find((issue) => issue.id === analysisSelectedIssueId) ?? null
        : null;
      const issues = selectedOnly && selectedIssue ? [selectedIssue] : analysisIssues;
      const paths = selectedOnly && selectedIssue
        ? analysisPaths.filter((path) => path.id === selectedIssue.pathId)
        : analysisPaths;
      const resolvedSurfaceSource =
        drainageSurfaceSummary.surfaceSource && drainageSurfaceSummary.surfaceSource !== "unknown"
          ? drainageSurfaceSummary.surfaceSource
          : gradingSourceSummary;
      return {
        generated_at: new Date().toISOString(),
        note: "Conceptual access analysis. Not a code compliance determination.",
        surface_source: resolvedSurfaceSource,
        threshold_ft: issues[0]?.thresholdFt ?? 150,
        buildings: buildings.map((b) => ({
          id: b.id,
          label: b.label,
          type: b.type,
          x: b.x,
          y: b.y,
          w: b.w,
          d: b.d,
        })),
        access_objects: access.map((a) => ({
          id: a.id,
          label: a.label,
          type: a.type,
          x: a.x,
          y: a.y,
          w: a.w,
          d: a.d,
        })),
        issues: issues.map((issue) => {
          const path = analysisPaths.find((candidate) => candidate.id === issue.pathId);
          return {
            issue_id: issue.id,
            issue_type: issue.issueType,
            building_id: issue.buildingId,
            access_object_id: issue.accessId,
            distance_ft: issue.distanceFt,
            threshold_ft: issue.thresholdFt,
            message: issue.message,
            surface_source: resolvedSurfaceSource,
            path_coordinates: path
              ? {
                  from: path.from,
                  to: path.to,
                  points: path.points ?? [path.from, path.to],
                }
              : null,
          };
        }),
        paths,
      };
    },
    [
      analysisIssues,
      analysisPaths,
      analysisSelectedIssueId,
      buildingPlacements,
      drainageSurfaceSummary,
      gradingSourceSummary,
    ],
  );

  const exportAnalysisReport = useCallback(() => {
    const report = buildAnalysisReport(false);
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "civora-access-analysis.json";
    link.click();
    URL.revokeObjectURL(url);
  }, [buildAnalysisReport]);

  const exportSelectedAnalysis = useCallback(() => {
    if (!analysisSelectedIssueId) return;
    const report = buildAnalysisReport(true);
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "civora-access-analysis-selected.json";
    link.click();
    URL.revokeObjectURL(url);
  }, [analysisSelectedIssueId, buildAnalysisReport]);

  const copyAnalysisJson = useCallback(async () => {
    const report = buildAnalysisReport(false);
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      setStatusMessage("Analysis JSON copied to clipboard.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Clipboard copy failed.",
      );
    }
  }, [buildAnalysisReport]);
  const filteredDetectedPlacements = useMemo(() => {
    const threshold = detectionConfidenceFilter === "high" ? 0.6 : detectionConfidenceFilter === "medium" ? 0.3 : 0.0;
    return detectedPlacements.filter((item) => (item.confidence ?? 0) >= threshold);
  }, [detectedPlacements, detectionConfidenceFilter]);
  const sortedProjects = useMemo(
    () => [...projects].sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0)),
    [projects],
  );

  if (!user) {
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
    <div className="min-h-screen bg-[#e9eaee] text-slate-950">
      <div className="flex min-h-screen flex-col">
        <AppHeader
          userEmail={user.email}
          onOpenProjects={() => setActiveSidePanel("projects")}
          onOpenSiteInputs={() => setActiveSidePanel("site")}
          onOpenDocs={() => setActiveSidePanel("docs")}
          onOpenChat={() => setActiveSidePanel("chat")}
          onLogout={handleLogout}
        />

        <div className="flex min-h-screen">
          {activeSidePanel ? (
            <aside className="flex w-[360px] flex-col border-r border-slate-200 bg-white/95">
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {activeSidePanel === "projects"
                      ? "Projects"
                      : activeSidePanel === "site"
                        ? "Site Inputs"
                      : activeSidePanel === "docs"
                        ? "Docs"
                        : "Chat"}
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    {activeSidePanel === "projects"
                      ? "Switch between projects."
                      : activeSidePanel === "site"
                        ? "Provide address, imagery, and survey data."
                      : activeSidePanel === "docs"
                        ? "Preview docs and exports."
                        : "Conversation and updates."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveSidePanel(null)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 hover:bg-slate-50"
                >
                  Close
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {activeSidePanel === "projects" ? (
                  <div className="space-y-3">
                    <button
                      type="button"
                      onClick={async () => {
                        await handleNewProject();
                        setActiveSidePanel(null);
                      }}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
                    >
                      + New Project
                    </button>
                    {sortedProjects.length ? (
                      sortedProjects.map((projectSummary) => (
                        <div
                          key={projectSummary.project_id}
                          className={`relative w-full rounded-2xl border px-4 py-3 text-left transition ${
                            projectSummary.project_id === projectId
                              ? "border-slate-900 bg-slate-950 text-white"
                              : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                          }`}
                        >
                          <button
                            type="button"
                            onClick={() => {
                              void loadProject(projectSummary.project_id);
                              setActiveSidePanel(null);
                            }}
                            className="block w-full text-left"
                          >
                            <p className="text-sm font-semibold">
                              {projectSummary.name || "Untitled Project"}
                            </p>
                            <p className="mt-1 text-xs uppercase tracking-[0.12em] opacity-70">
                              {projectSummary.description ||
                                (projectSummary.updated_at
                                  ? `Updated ${new Date(projectSummary.updated_at * 1000).toLocaleDateString()}`
                                  : "No description")}
                            </p>
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleDeleteProject(projectSummary.project_id)}
                            className={`absolute right-3 top-3 rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                              projectSummary.project_id === projectId
                                ? "border-white/40 text-white/80 hover:bg-white/10"
                                : "border-slate-200 text-slate-500 hover:bg-slate-50"
                            }`}
                          >
                            Delete
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No projects yet.</p>
                    )}
                  </div>
                ) : null}

                {activeSidePanel === "site" ? (
                  <div className="space-y-4">
                    <div>
                      <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Site address
                      </label>
                      <input
                        value={siteAddress}
                        onChange={(event) => setSiteAddress(event.target.value)}
                        onBlur={() => void saveSiteAddress()}
                        placeholder="123 Main St, City, State"
                        className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-slate-400 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => void saveSiteAddress()}
                        className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                      >
                        Save address
                      </button>
                      <div className="mt-3 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                        <span>
                          Alignment:{" "}
                          <span className="font-semibold text-slate-800">
                            {siteScaleLocked ? "Locked" : "Unlocked"}
                          </span>
                        </span>
                        <button
                          type="button"
                          onClick={handleToggleSiteLock}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          {siteScaleLocked ? "Unlock Site" : "Lock Site"}
                        </button>
                      </div>
                      {siteAddress ? (
                        <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          <p className="font-semibold text-slate-700">Next steps</p>
                          <p className="mt-1 text-[11px] text-slate-500">
                            Address adds context only. Create the site boundary or detect features to start modeling.
                          </p>
                          <div className="mt-2 flex flex-col gap-2">
                            <button
                              type="button"
                              onClick={() => handleAddObject("site")}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                            >
                              Create site boundary
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAddObject("building")}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                            >
                              Add building
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAddObject("road")}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                            >
                              Add road/access
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAnalyzeImageFeatures()}
                              disabled={!mapSnapshotPath}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              Detect site features
                            </button>
                            <button
                              type="button"
                              onClick={() => setStatusMessage("Adjust the site boundary by editing width/height above.")}
                              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                            >
                              Adjust site boundary
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </div>

                    <div className="space-y-2 text-sm text-slate-700">
                      <button
                        type="button"
                        onClick={() => mapSnapshotInputRef.current?.click()}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                      >
                        <span>Upload site image / map snapshot</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {uploadedImageApiUrl || uploadedImagePreviewUrl ? "Ready" : "Upload"}
                        </span>
                      </button>
                      {imageUploadState !== "idle" ? (
                        <p className="text-xs text-slate-500">
                          {imageUploadNote ||
                            (imageUploadState === "uploading"
                              ? "Uploading image…"
                              : imageUploadState === "detecting"
                                ? "Detecting site features…"
                                : imageUploadState === "failed"
                                  ? "Image upload failed."
                                  : "Image uploaded.")}
                        </p>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => surveyInputRef.current?.click()}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                      >
                        <span>Upload survey / topo file</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {surveyFileName ? "Ready" : "Upload"}
                        </span>
                      </button>
                      <p className="text-xs text-slate-500">
                        Supported: CSV survey points, DXF topo/contours (parsing pending).
                      </p>
                      <button
                        type="button"
                        onClick={estimateSurveySlope}
                        disabled={!surveyFileName}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span>Estimate slope from survey</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {surveySlopeEstimate?.slope_percent ? "Estimated" : "Compute"}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={analyzeMapSnapshot}
                        disabled={!mapSnapshotPath}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span>Analyze map snapshot</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {mapAnalysis?.success ? "Ready" : "Analyze"}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAnalyzeImageFeatures()}
                        disabled={!mapSnapshotPath}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span>Detect site features</span>
                        <span className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                          {missingImage ? "Needs image" : detectedPlacements.length ? "Detected" : "Run"}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={handleAnalyzeSiteAccess}
                        disabled={confirmedObjectCounts.buildings === 0 || confirmedObjectCounts.access === 0}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                      >
                        <span>Analyze site access</span>
                        <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                          {analysisIssues.length ? "Reviewed" : "Run"}
                        </span>
                      </button>
                      {confirmedObjectCounts.buildings === 0 || confirmedObjectCounts.access === 0 ? (
                        <p className="text-xs text-slate-500">
                          Address provides site context only. Add or confirm buildings and access objects to run analysis.
                        </p>
                      ) : null}
                      {surveyFileName ? (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          <p className="font-semibold text-slate-700">Survey loaded</p>
                          <p className="mt-1">
                            {surveyFileName}
                            {surveyDiagnostics?.fileType ? ` · ${surveyDiagnostics.fileType.toUpperCase()}` : ""}
                          </p>
                          {surveyDiagnostics?.parseSuccess !== undefined ? (
                            <p className="mt-1">
                              {surveyDiagnostics.parseSuccess ? "Parse success" : "Parse pending"} ·{" "}
                              {surveyDiagnostics.pointCount ?? 0} points
                            </p>
                          ) : null}
                          {surveyDiagnostics?.recognizedColumns ? (
                            <p className="mt-1">
                              Columns: {surveyDiagnostics.recognizedColumns.x || "x"} /{" "}
                              {surveyDiagnostics.recognizedColumns.y || "y"} /{" "}
                              {surveyDiagnostics.recognizedColumns.z || "z"} · Invalid rows:{" "}
                              {surveyDiagnostics.invalidRows ?? 0}
                            </p>
                          ) : null}
                          {surveyDiagnostics?.bounds ? (
                            <p className="mt-1">
                              Extents: [{surveyDiagnostics.bounds.min_x?.toFixed?.(1) ?? "?"},{" "}
                              {surveyDiagnostics.bounds.min_y?.toFixed?.(1) ?? "?"}] → [
                              {surveyDiagnostics.bounds.max_x?.toFixed?.(1) ?? "?"},{" "}
                              {surveyDiagnostics.bounds.max_y?.toFixed?.(1) ?? "?"}]
                            </p>
                          ) : null}
                          {surveyDiagnostics?.elevationRange ? (
                            <p className="mt-1">
                              Elevation: {surveyDiagnostics.elevationRange.min?.toFixed?.(2) ?? "?"}–{" "}
                              {surveyDiagnostics.elevationRange.max?.toFixed?.(2) ?? "?"} ft
                            </p>
                          ) : null}
                          {surveyDiagnostics?.warnings?.length ? (
                            <p className="mt-2 text-amber-600">
                              {surveyDiagnostics.warnings[0]}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                      {uploadedImageApiUrl || uploadedImagePreviewUrl ? (
                        <p className="text-xs text-slate-500">
                          Map snapshot loaded and ready for interpretation.
                        </p>
                      ) : null}
                      {mapAnalysis?.success ? (
                        <p className="text-xs text-slate-500">
                          Map analysis captured {mapAnalysisCounts.zones} zones,{" "}
                          {mapAnalysisCounts.objects} objects,{" "}
                          {mapAnalysisCounts.centerlines} centerlines.
                        </p>
                      ) : null}
                      {surveySlopeEstimate?.slope_percent ? (
                        <p className="text-xs text-slate-500">
                          Estimated {surveySlopeEstimate.slope_percent.toFixed(2)}% slope toward{" "}
                          {surveySlopeEstimate.direction || "N/A"} from {surveySlopeEstimate.point_count ?? 0} points.
                        </p>
                      ) : null}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Grading source
                      </p>
                      <p className="mt-2 text-sm font-semibold text-slate-800">
                        {gradingSourceSummary}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Survey data only comes from uploaded survey/topo files. Mapbox terrain is an approximate
                        fallback when no survey is active.
                      </p>
                      <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
                        <span>Use survey for grading</span>
                        <input
                          type="checkbox"
                          checked={useSurveyForGrading}
                          disabled={!surveyFileName}
                          onChange={(event) => {
                            const next = event.target.checked;
                            setUseSurveyForGrading(next);
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
                                    use_survey_for_grading: next,
                                  },
                                },
                              },
                            });
                          }}
                          className="h-4 w-4 accent-slate-900"
                        />
                      </label>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Detection scale calibration
                      </p>
                      <p className="mt-2 text-xs text-slate-500">
                        Auto scale source: {detectionScaleSource === "mapbox" ? "Mapbox (real-world)" : "Approximate"}
                      </p>
                      <p className="mt-2 text-xs text-slate-500">
                        Automatic scale is used when map context is available. Manual calibration is an advanced fallback.
                      </p>
                      <button
                        type="button"
                        onClick={() => setShowAdvancedCalibration((prev) => !prev)}
                        className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                      >
                        {showAdvancedCalibration ? "Hide Advanced" : "Advanced Calibration"}
                      </button>
                      {showAdvancedCalibration ? (
                        <div className="mt-3">
                          <div className="grid grid-cols-2 gap-3 text-xs text-slate-600">
                            <label className="flex flex-col gap-1">
                              Known distance (ft)
                              <input
                                type="number"
                                value={detectionScaleFeet}
                                onChange={(event) => setDetectionScaleFeet(event.target.value)}
                                className="rounded-lg border border-slate-200 px-2 py-1"
                              />
                            </label>
                            <label className="flex flex-col gap-1">
                              Pixel distance (px)
                              <input
                                type="number"
                                value={detectionScalePixels}
                                onChange={(event) => setDetectionScalePixels(event.target.value)}
                                className="rounded-lg border border-slate-200 px-2 py-1"
                              />
                            </label>
                          </div>
                          <button
                            type="button"
                            onClick={() => void applyDetectionScale()}
                            className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                          >
                            Apply scale
                          </button>
                          <p className="mt-2 text-xs text-slate-500">
                            {detectionScaleFtPerPx
                              ? `Calibrated (${detectionScaleSource === "mapbox" ? "Mapbox" : "Manual"}): 1 px ≈ ${detectionScaleFtPerPx.toFixed(3)} ft`
                              : "No calibration applied. Detection sizes are approximate."}
                          </p>
                          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
                            <p className="font-semibold text-slate-700">How to calibrate</p>
                            <p className="mt-1">
                              Pick two points in the uploaded image with a known real‑world distance, measure the pixel distance between them, then enter both values and apply.
                            </p>
                          </div>
                        </div>
                      ) : null}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Site rotation
                      </p>
                      <div className="mt-3 flex items-center gap-3">
                        <input
                          type="range"
                          min={-180}
                          max={180}
                          value={siteRotationDeg}
                          onChange={(event) => {
                            const value = Number(event.target.value);
                            setSiteRotationDeg(value);
                            setSiteRotationInput(String(value));
                            scheduleRotationSave(value);
                          }}
                          className="w-full"
                        />
                        <input
                          type="number"
                          value={siteRotationInput}
                          onChange={(event) => {
                            setSiteRotationInput(event.target.value);
                            const value = Number(event.target.value);
                            if (Number.isFinite(value)) {
                              setSiteRotationDeg(value);
                              scheduleRotationSave(value);
                            }
                          }}
                          className="w-24 rounded-lg border border-slate-200 px-2 py-1 text-sm"
                        />
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setFitToSiteRequest((value) => value + 1);
                          }}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Fit to Site
                        </button>
                        <button
                          type="button"
                          onClick={() => setMapCenterRequest((value) => value + 1)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Use Map Center
                        </button>
                        <button
                          type="button"
                          onClick={handleToggleSiteLock}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          {siteScaleLocked ? "Unlock Site" : "Lock Site"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowSiteBounds((value) => !value)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          {showSiteBounds ? "Hide Site Bounds" : "Show Site Bounds"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setAlignToRoadRequest((value) => value + 1)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Align to Nearest Road
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSiteRotationDeg(0);
                            setSiteRotationInput("0");
                            scheduleRotationSave(0);
                          }}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                        >
                          Reset Rotation
                        </button>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">
                        Hold <span className="font-semibold">R</span> and drag the canvas to rotate the site.
                      </p>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Survey intake
                      </p>
                      <p className="mt-2 text-sm font-semibold text-slate-800">
                        {siteInputs?.survey_point_count ? `${siteInputs.survey_point_count} points` : "No survey points parsed yet"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Columns: {siteInputs?.survey_point_columns?.x || "x"} / {siteInputs?.survey_point_columns?.y || "y"} / {siteInputs?.survey_point_columns?.z || "z"} ·
                        Invalid rows: {siteInputs?.survey_invalid_rows ?? 0}
                      </p>
                      {surveyDiagnostics?.bounds ? (
                        <p className="mt-1 text-xs text-slate-500">
                          Extents: [{surveyDiagnostics.bounds.min_x?.toFixed?.(1) ?? "?"},{" "}
                          {surveyDiagnostics.bounds.min_y?.toFixed?.(1) ?? "?"}] → [
                          {surveyDiagnostics.bounds.max_x?.toFixed?.(1) ?? "?"},{" "}
                          {surveyDiagnostics.bounds.max_y?.toFixed?.(1) ?? "?"}]
                        </p>
                      ) : null}
                      {surveyDiagnostics?.elevationRange ? (
                        <p className="mt-1 text-xs text-slate-500">
                          Elevation range: {surveyDiagnostics.elevationRange.min?.toFixed?.(2) ?? "?"}–{" "}
                          {surveyDiagnostics.elevationRange.max?.toFixed?.(2) ?? "?"} ft
                        </p>
                      ) : null}
                      {Array.isArray(siteInputs?.survey_point_warnings) && siteInputs.survey_point_warnings.length ? (
                        <p className="mt-2 text-xs text-amber-600">
                          {siteInputs.survey_point_warnings[0]}
                        </p>
                      ) : null}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Drainage surface usage
                      </p>
                      <p className="mt-2 text-sm font-semibold text-slate-800">
                        {drainageSurfaceSummary.surfaceFromGrading ? "Using grading surface" : "Surface source unknown"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Source: {drainageSurfaceSummary.surfaceSource}
                        {drainageSurfaceSummary.surfaceQuality
                          ? ` · ${drainageSurfaceSummary.surfaceQuality.replace(/_/g, " ")}`
                          : ""}
                      </p>
                      {drainageSurfaceSummary.surfaceDetail ? (
                        <p className="mt-1 text-xs text-slate-500">
                          {drainageSurfaceSummary.surfaceDetail}
                        </p>
                      ) : null}
                    </div>

                    <input
                      ref={mapSnapshotInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={async (event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) {
                          await uploadImage(file);
                        }
                        event.currentTarget.value = "";
                      }}
                    />
                    <input
                      ref={surveyInputRef}
                      type="file"
                      accept=".csv,.dxf"
                      className="hidden"
                      onChange={async (event) => {
                        const file = event.currentTarget.files?.[0];
                        if (file) {
                          await uploadSurvey(file);
                        }
                        event.currentTarget.value = "";
                      }}
                    />
                  </div>
                ) : null}

                {activeSidePanel === "docs" ? (
                  <div className="space-y-3">
                    {sortedProjects.length ? (
                      sortedProjects.map((projectSummary) => (
                        <div
                          key={projectSummary.project_id}
                          className="rounded-2xl border border-slate-200 bg-white p-4"
                        >
                          <p className="text-sm font-semibold text-slate-900">
                            {projectSummary.name || "Untitled Project"}
                          </p>
                          <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500">
                            {projectSummary.description ||
                              (projectSummary.updated_at
                                ? `Updated ${new Date(projectSummary.updated_at * 1000).toLocaleDateString()}`
                                : "No description")}
                          </p>
                          <button
                            type="button"
                            onClick={async () => {
                              await loadProject(projectSummary.project_id);
                              await handlePreviewPlan();
                              setPreviewFullscreenOpen(true);
                              setActiveSidePanel(null);
                            }}
                            className="mt-3 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
                          >
                            View Docs
                          </button>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No docs available yet.</p>
                    )}
                  </div>
                ) : null}

                {activeSidePanel === "chat" ? (
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
                    onToggleCollapsed={() => setActiveSidePanel(null)}
                    summaryText={chatSummary}
                  />
                ) : null}
              </div>
            </aside>
          ) : null}
          <main className="flex min-w-0 flex-1 flex-col">
            <div className="border-b border-slate-200 bg-white/85">
              <div className="mx-auto w-full max-w-7xl px-4 py-5 md:px-6">
                <ProjectControls
                  siteName={siteName}
                  fileName={fileName}
                  onSiteNameChange={setSiteName}
                  onFileNameChange={setFileName}
                  onSiteNameEdited={() => setSiteNameAuto(false)}
                  onFileNameEdited={() => setFileNameAuto(false)}
                  onSaveProjectNames={() =>
                    void saveProject({
                      nameOverride: siteName.trim(),
                      fileNameOverride: fileName.trim(),
                      autoNamedOverride: false,
                      autoFileNamedOverride: false,
                    })
                  }
                  disciplineToggles={disciplineToggles.map((item) => ({
                    label: item.label,
                    checked: item.checked,
                    onToggle: () => item.setter(!item.checked),
                  }))}
                />
              </div>
            </div>

            <WorkspaceToolbar onRefreshWorkspace={handleRefreshWorkspace} />

            <div className="flex w-full flex-1 flex-col gap-6 px-4 py-6 md:px-6">
              <div className="flex w-full flex-col">
                <div className="mb-3 flex flex-wrap items-center gap-3 text-xs text-slate-600">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Preview height
                  </span>
                  <input
                    type="range"
                    min={360}
                    max={900}
                    step={10}
                    value={previewHeightPx}
                    onChange={(event) => {
                      const next = Number(event.target.value);
                      if (Number.isFinite(next)) setPreviewHeightPx(next);
                    }}
                    className="h-2 w-44 accent-slate-900"
                  />
                  <input
                    type="number"
                    min={360}
                    max={900}
                    step={10}
                    value={previewHeightPx}
                    onChange={(event) => {
                      const next = Number(event.target.value);
                      if (Number.isFinite(next)) setPreviewHeightPx(next);
                    }}
                    className="h-8 w-20 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                  />
                  <span className="text-[11px] uppercase tracking-[0.12em] text-slate-400">px</span>
                </div>
                <div
                  className="mx-auto w-full border-2 border-black"
                  style={{
                    width: "calc(100vw - 96px)",
                    height: `${previewHeightPx}px`,
                  }}
                >
                  <div className="h-full w-full">
                    <PreviewPanel
                previewReview={previewReview}
                previewTotalPhaseCount={previewTotalPhaseCount}
                previewCompletedPhaseCount={previewCompletedPhaseCount}
                previewRunningPhase={previewRunningPhase}
                previewNextPendingPhase={previewNextPendingPhase}
                onRefreshPreview={handlePreviewPlan}
                busy={busy}
                planPreviewUrl={planPreviewUrl}
                planPreviewProjectId={planPreviewProjectId}
                currentProjectId={projectId || currentProject?.project_id || null}
                previewMode={previewMode}
                previewInteraction={previewInteraction}
                previewQuality={previewQuality}
                previewLabelDensity={previewLabelDensity}
                hasGeneratedPlan={Boolean(planPreviewUrl && backendResult)}
                placementMode={placementModeEnabled || Boolean(activePlacementId)}
                externalRectUndo={externalRectUndo}
              onPlaceBuilding={handlePlaceBuilding}
              onPlaceObject={handlePlaceObject}
              buildingPlacements={buildingPlacements}
              suggestedPlacements={filteredDetectedPlacements}
              selectedBuildingId={activePlacementId}
              focusDetectedId={focusDetectedId}
              onClearFocusDetected={() => setFocusDetectedId(null)}
              focusObjectId={focusObjectId}
              onClearFocusObject={() => setFocusObjectId(null)}
              lotWidth={lotBounds.w}
              lotHeight={lotBounds.h}
              onUpdateBuilding={handleUpdateBuilding}
              onUpdateSuggested={(id, updates) => {
                setDetectedPlacements((prev) => {
                  const nextDetected = prev.map((item) =>
                    item.id === id ? { ...item, ...updates } : item,
                  );
                  persistDetectedPlacements(nextDetected);
                  return nextDetected;
                });
              }}
              analysisPaths={analysisPaths}
              analysisHighlight={
                selectedAccessIssue
                  ? {
                      buildingId: selectedAccessIssue.buildingId,
                      accessId: selectedAccessIssue.accessId,
                      pathId: selectedAccessIssue.pathId,
                    }
                  : null
              }
              analysisFocusLocked={analysisFocusLocked}
              onClearHighlights={() => {
                setAnalysisSelectedIssueId(null);
                setAnalysisFocusLocked(false);
              }}
              onResetView={() => {
                setAnalysisSelectedIssueId(null);
                setFocusDetectedId(null);
                setAnalysisFocusLocked(false);
              }}
              onRemoveBuilding={handleRemoveBuilding}
              onRestoreBuilding={handleRestoreBuilding}
              onSelectBuilding={setActivePlacementId}
                onSetPreviewMode={setPreviewMode}
                onSetPreviewInteraction={setPreviewInteraction}
                onSetPreviewQuality={setPreviewQuality}
                onSetPreviewLabelDensity={(value) => {
                  setPreviewLabelDensityTouched(true);
                  setPreviewLabelDensity(value);
                }}
                onQueuePreviewRefresh={queuePreviewRefresh}
                previewRefreshing={previewRefreshing}
                previewRefreshNote={previewRefreshNote}
                preview3DEffectiveItems={preview3DEffectiveItems}
                usingAnnotation3D={usingAnnotation3D}
                hasGradingSurface={hasGradingSurface}
                onOpenFullscreen={() => setPreviewFullscreenOpen(true)}
                previewFullscreenOpen={previewFullscreenOpen}
                onCloseFullscreen={() => setPreviewFullscreenOpen(false)}
                onExportDxf={handleExportDxf}
                onExportReport={handleExportReport}
                planPreviewAnnotations={planPreviewAnnotations}
                selectedIssueLabel={selectedIssueLabel}
                showMeasurements={showMeasurements}
                showCalculations={showCalculations}
                measurementOverlayStats={measurementOverlayStats}
                calculationOverlayStats={calculationOverlayStats}
                geocode={siteInputs?.geocode ?? null}
                siteRotationDeg={siteInputs?.site_rotation_deg ?? 0}
                showSiteBounds={showSiteBounds}
                fitToSiteRequest={fitToSiteRequest}
                mapCenterRequest={mapCenterRequest}
                alignToRoadRequest={alignToRoadRequest}
                onMapCenter={handleMapCenter}
                siteLocked={siteScaleLocked}
                onSetSiteRotationDeg={(value) => {
                  setSiteRotationDeg(value);
                  setSiteRotationInput(String(value));
                  scheduleRotationSave(value);
                }}
                surveyPoints={surveyPreviewPoints}
                onMapScaleUpdate={({ ftPerPx, source }) => {
                  if (siteScaleLocked) return;
                  if (!Number.isFinite(ftPerPx) || ftPerPx <= 0) return;
                  setDetectionScaleFtPerPx(ftPerPx);
                  setDetectionScaleSource(source);
                  scheduleScaleSave(ftPerPx, source);
                }}
                debugStats={{
                  enabled: debugPreview,
                  projectId: projectId || currentProject?.project_id || "",
                  canonicalCount: buildingPlacements.length,
                  placedCount: placedObjectCount,
                  previewImageActive: Boolean(planPreviewUrl),
                  placementMode: placementModeEnabled || Boolean(activePlacementId),
                  selectedId: activePlacementId,
                }}
              />
                  </div>
                </div>
              </div>

              <div className="rounded-[24px] border border-slate-200 bg-white/95 p-4 shadow-[0_12px_35px_-28px_rgba(15,23,42,0.45)]">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Object Tray
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      Drag objects onto the site. Place the site first, then add buildings and anchors.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={handleTogglePlacementMode}
                      className={`rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition ${
                        placementModeEnabled
                          ? "border-slate-900 bg-slate-950 text-white"
                          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      {placementModeEnabled ? "Placement On" : "Placement Off"}
                    </button>
                    <button
                      type="button"
                      onClick={handleAutoPlaceBuildings}
                      className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                    >
                      Auto-place
                    </button>
                    <button
                      type="button"
                      onClick={handleSuggestLayouts}
                      className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                    >
                      Suggest Layouts
                    </button>
                    <button
                      type="button"
                      onClick={handleNextSuggestion}
                      className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                    >
                      Next Suggestion
                    </button>
                  </div>
                </div>

                  <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Add Objects
                        </p>
                        <p className="mt-1 text-sm text-slate-600">
                          Choose a category to add real, scaled site objects.
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleAddObject("site")}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
                        >
                          Add Site
                        </button>
                        {missingSite ? (
                        <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                          Needs site
                        </span>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => setAdvancedAddOpen((value) => !value)}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 hover:bg-slate-50"
                        >
                          {advancedAddOpen ? "Hide Advanced" : "Show Advanced"}
                        </button>
                      </div>
                    </div>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    {ADD_MENU_SECTIONS.filter(
                      (section) => !section.collapsible || advancedAddOpen,
                    ).map((section) => (
                      <div key={section.key} className="rounded-2xl border border-slate-200 bg-white p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          {section.title}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {section.items.map((itemType) => {
                            const label = SITE_OBJECT_CATALOG[itemType]?.label ?? "Object";
                            return (
                              <button
                                key={itemType}
                                type="button"
                                onClick={() => handleAddObject(itemType)}
                                className="rounded-full border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                              >
                                {label}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr,2fr]">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Site</p>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-600">
                      <label className="flex flex-col gap-1">
                        Length (ft)
                        <input
                          type="number"
                          value={lotWidth}
                          onChange={(event) => {
                            const nextValue = event.target.value;
                            setLotWidth(nextValue);
                            setBuildingPlacements((prev) =>
                              prev.map((item) =>
                                item.type === "site"
                                  ? {
                                      ...item,
                                      w:
                                        parsePositiveNumber(nextValue) ??
                                        item.w,
                                    }
                                  : item,
                              ),
                            );
                          }}
                          className="rounded-lg border border-slate-200 px-2 py-1"
                        />
                      </label>
                      <label className="flex flex-col gap-1">
                        Width (ft)
                        <input
                          type="number"
                          value={lotHeight}
                          onChange={(event) => {
                            const nextValue = event.target.value;
                            setLotHeight(nextValue);
                            setBuildingPlacements((prev) =>
                              prev.map((item) =>
                                item.type === "site"
                                  ? {
                                      ...item,
                                      d:
                                        parsePositiveNumber(nextValue) ??
                                        item.d,
                                    }
                                  : item,
                              ),
                            );
                          }}
                          className="rounded-lg border border-slate-200 px-2 py-1"
                        />
                      </label>
                    </div>
                    <div className="mt-3 text-xs text-slate-500">
                      Area:{" "}
                      {(() => {
                        const w = parsePositiveNumber(lotWidth) ?? 0;
                        const h = parsePositiveNumber(lotHeight) ?? 0;
                        const acres = w && h ? (w * h) / 43560 : 0;
                        return acres ? `${acres.toFixed(2)} acres` : "Set dimensions to compute acreage";
                      })()}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Objects</p>
                    {detectedPlacements.length ? (
                      <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50/70 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-700">
                          Detected Objects (Review Required)
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(["high", "medium", "all"] as const).map((level) => (
                            <button
                              key={level}
                              type="button"
                              onClick={() => setDetectionConfidenceFilter(level)}
                              className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                                detectionConfidenceFilter === level
                                  ? "border-amber-400 bg-amber-100 text-amber-800"
                                  : "border-amber-200 bg-white text-amber-700"
                              }`}
                            >
                              {level === "high" ? "High only" : level === "medium" ? "Medium+" : "All"}
                            </button>
                          ))}
                        </div>
                        <div className="mt-3 space-y-2">
                          {filteredDetectedPlacements.map((item) => (
                            <div
                              key={item.id}
                              className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs text-slate-700"
                            >
                              <div>
                                <p className="font-semibold text-slate-800">{item.label}</p>
                                <p className="text-[11px] text-slate-500">
                                  {item.w.toFixed(1)} ft × {item.d.toFixed(1)} ft ·{" "}
                                  {item.confidence ? `${Math.round(item.confidence * 100)}%` : "Approx."} ·{" "}
                                  {detectionScaleFtPerPx ? "Calibrated" : "Approx scale"}
                                </p>
                              </div>
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  onClick={() => setFocusDetectedId(item.id)}
                                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600"
                                >
                                  Zoom
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleAcceptDetected(item.id)}
                                  className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-700"
                                >
                                  Accept
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleRejectDetected(item.id)}
                                  className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-700"
                                >
                                  Reject
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                        <p className="mt-2 text-[11px] text-amber-700/80">
                          Detected features are approximate and must be confirmed.
                        </p>
                      </div>
                    ) : null}
                    {analysisIssues.length ? (
                      <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50/70 p-3">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-rose-700">
                            Access Analysis (Conceptual)
                          </p>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={exportAnalysisReport}
                              className="rounded-full border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600"
                            >
                              Export analysis
                            </button>
                            {analysisSelectedIssueId ? (
                              <button
                                type="button"
                                onClick={exportSelectedAnalysis}
                                className="rounded-full border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600"
                              >
                                Export selected
                              </button>
                            ) : null}
                            <button
                              type="button"
                              onClick={copyAnalysisJson}
                              className="rounded-full border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600"
                            >
                              Copy JSON
                            </button>
                            <div
                              className="rounded-full border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600"
                              title="Access analysis checks distance from confirmed buildings to nearest confirmed access. Threshold 150 ft."
                            >
                              Explain
                            </div>
                          </div>
                        </div>
                        <p className="mt-2 text-[11px] text-rose-700/80">
                          Uses confirmed buildings + access objects. Calculates nearest access distance and compares to 150 ft threshold.
                        </p>
                        {selectedAccessIssue ? (
                          <p className="mt-2 text-[11px] text-rose-700">
                            Selected: {Math.round(selectedAccessIssue.distanceFt)} ft (threshold {selectedAccessIssue.thresholdFt} ft)
                          </p>
                        ) : null}
                        <ul className="mt-3 space-y-1 text-[11px] text-rose-700">
                          {analysisIssues.map((issue) => (
                            <li key={issue.id}>
                              <button
                                type="button"
                                onClick={() => {
                                  setAnalysisSelectedIssueId(issue.id);
                                  setAnalysisFocusLocked(true);
                                }}
                                className={`w-full text-left ${analysisSelectedIssueId === issue.id ? "font-semibold underline" : ""}`}
                              >
                                {issue.message}
                              </button>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : analysisEmptyReason ? (
                      <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                        <p className="font-semibold text-slate-700">Access analysis needs objects</p>
                        <p className="mt-1">{analysisEmptyReason}</p>
                      </div>
                    ) : null}
                    {issues.length ? (
                      <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-3">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-700">
                            Engineering Issues
                          </p>
                          <span className="text-[10px] uppercase tracking-[0.12em] text-slate-400">
                            Apply fixes
                          </span>
                        </div>
                        <div className="mt-3 space-y-2 text-xs text-slate-700">
                          {issues.map((issue, idx) => {
                            const applyLabel = drainageIssueApplyLabel(issue);
                            const canApply = applyLabel ? canApplyDrainageIssue(issue) : false;
                            const guidance = getIssueGuidance(issue);
                            return (
                              <div
                                key={`${issue.message}-${idx}`}
                                className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2"
                              >
                                <div>
                                  <p className="font-semibold text-slate-800">{issue.message}</p>
                                  {issue.code ? (
                                    <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-400">
                                      {issue.code}
                                    </p>
                                  ) : null}
                                  {guidance.explanation ? (
                                    <p className="mt-2 text-[11px] text-slate-600">
                                      {guidance.explanation}
                                    </p>
                                  ) : null}
                                  {guidance.bestNextFix ? (
                                    <p className="mt-2 text-[11px] font-semibold text-slate-700">
                                      Best next fix: {guidance.bestNextFix}
                                    </p>
                                  ) : null}
                                  {guidance.suggested && guidance.suggested.length ? (
                                    <div className="mt-2 space-y-1 text-[11px] text-slate-600">
                                      {guidance.suggested.map((item) => (
                                        <p key={item}>• {item}</p>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                                {applyLabel ? (
                                  <button
                                    type="button"
                                    onClick={() => handleApplyDrainageIssue(issue)}
                                    disabled={!canApply}
                                    className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                                      canApply
                                        ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                                        : "border-slate-200 bg-white text-slate-400 cursor-not-allowed"
                                    }`}
                                  >
                                    {applyLabel}
                                  </button>
                                ) : (
                                  <span className="text-[10px] uppercase tracking-[0.12em] text-slate-400">
                                    Review
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                    <div className="mt-2 max-h-72 space-y-3 overflow-y-auto pr-1">
                      <div className="flex w-full gap-3 overflow-x-auto pb-2">
                        {buildingPlacements
                          .filter((item) => !item.placed)
                          .map((item) => (
                            <div
                              key={item.id}
                              draggable={!item.locked}
                              onDragStart={(event) => {
                                if (item.locked) return;
                                event.dataTransfer?.setData("civora-object-id", item.id);
                                setPlacementModeEnabled(true);
                              }}
                              className={`min-w-[220px] rounded-2xl border bg-white p-3 text-xs text-slate-600 shadow-sm ${
                                activePlacementId === item.id
                                  ? "border-amber-400 ring-2 ring-amber-200"
                                  : "border-slate-200"
                              }`}
                              title={`${item.label} • ${item.w} ft x ${item.d} ft`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-800">{item.label}</span>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveBuilding(item.id)}
                                  className="text-xs font-semibold text-rose-500"
                                >
                                  Delete
                                </button>
                              </div>
                              <div className="mt-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                                <span>{SITE_OBJECT_CATALOG[item.type ?? "building"]?.label ?? "Building"}</span>
                                <span>•</span>
                                <span>{item.w} ft x {item.d} ft</span>
                              </div>
                              {item.type !== "site" ? (
                                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                                  <label className="flex flex-col gap-1">
                                    Length
                                    <input
                                      type="number"
                                      value={item.w}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          w: parsePositiveNumber(event.target.value) ?? item.w,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  <label className="flex flex-col gap-1">
                                    Width
                                    <input
                                      type="number"
                                      value={item.d}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          d: parsePositiveNumber(event.target.value) ?? item.d,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  {SITE_OBJECT_CATALOG[item.type ?? "building"]?.defaultH !== undefined ? (
                                    <label className="col-span-2 flex flex-col gap-1">
                                      Height (ft)
                                      <input
                                        type="number"
                                        value={item.h ?? ""}
                                        onChange={(event) =>
                                          handleUpdateBuilding(item.id, {
                                            h:
                                              parsePositiveNumber(event.target.value) ??
                                              item.h,
                                          })
                                        }
                                        className="rounded-md border border-slate-200 px-2 py-1"
                                      />
                                    </label>
                                  ) : null}
                                  {item.type === "parking" ? (
                                    <>
                                      <label className="col-span-2 flex flex-col gap-1">
                                        Stalls
                                        <input
                                          type="number"
                                          value={item.stallCount ?? ""}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              stallCount:
                                                parsePositiveNumber(event.target.value) ?? 0,
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Stall W
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.stallWidth ??
                                              parkingStallWidth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  stallWidth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingStallWidth) ??
                                                    9,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Stall D
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.stallDepth ??
                                              parkingStallDepth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  stallDepth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingStallDepth) ??
                                                    18,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Aisle
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.aisleWidth ??
                                              parkingAisleWidth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  aisleWidth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingAisleWidth) ??
                                                    24,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        ADA Count
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.adaCount ??
                                              parkingAdaCount,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  adaCount:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingAdaCount) ??
                                                    0,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        ADA Aisle
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.adaAisleWidth ??
                                              parkingAdaAisleWidth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  adaAisleWidth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingAdaAisleWidth) ??
                                                    8,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Compact Count
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.compactCount ??
                                              parkingCompactCount,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  compactCount:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingCompactCount) ??
                                                    0,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Compact W
                                        <input
                                          type="number"
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.compactWidth ??
                                              parkingCompactWidth,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  compactWidth:
                                                    parsePositiveNumber(event.target.value) ??
                                                    parsePositiveNumber(parkingCompactWidth) ??
                                                    8,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        />
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Angle
                                        <select
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.angleDeg ??
                                              parkingAngle,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  angleDeg: parsePositiveNumber(event.target.value) ?? 90,
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        >
                                          <option value="90">90°</option>
                                          <option value="60">60°</option>
                                          <option value="45">45°</option>
                                        </select>
                                      </label>
                                      <label className="flex flex-col gap-1">
                                        Loading
                                        <select
                                          value={String(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.loading ??
                                              parkingLoading,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  loading: event.target.value === "single" ? "single" : "double",
                                                },
                                              },
                                            })
                                          }
                                          className="rounded-md border border-slate-200 px-2 py-1"
                                        >
                                          <option value="double">Double</option>
                                          <option value="single">Single</option>
                                        </select>
                                      </label>
                                      <label className="col-span-2 flex items-center justify-between gap-2 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-600">
                                        <span>Mixed angle zones</span>
                                        <input
                                          type="checkbox"
                                          checked={Boolean(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.useMixedAngles,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  useMixedAngles: event.target.checked,
                                                },
                                              },
                                            })
                                          }
                                        />
                                      </label>
                                      <label className="col-span-2 flex items-center justify-between gap-2 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-600">
                                        <span>Compact zone grouping</span>
                                        <input
                                          type="checkbox"
                                          checked={Boolean(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.compactZone ?? true,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  compactZone: event.target.checked,
                                                },
                                              },
                                            })
                                          }
                                        />
                                      </label>
                                      <label className="col-span-2 flex items-center justify-between gap-2 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-600">
                                        <span>Auto-resize to fit count</span>
                                        <input
                                          type="checkbox"
                                          checked={Boolean(
                                            (item.meta as { parkingParams?: any })?.parkingParams?.autoResizeToFitCount,
                                          )}
                                          onChange={(event) =>
                                            handleUpdateBuilding(item.id, {
                                              meta: {
                                                ...(item.meta ?? {}),
                                                parkingParams: {
                                                  ...(item.meta as { parkingParams?: any })?.parkingParams,
                                                  autoResizeToFitCount: event.target.checked,
                                                },
                                              },
                                            })
                                          }
                                        />
                                      </label>
                                      {!(item.meta as { parkingParams?: any })?.parkingParams?.autoResizeToFitCount &&
                                      typeof item.stallCount === "number" &&
                                      typeof (item.meta as { parkingCapacity?: number })?.parkingCapacity === "number" &&
                                      item.stallCount >
                                        Number((item.meta as { parkingCapacity?: number })?.parkingCapacity) ? (
                                        <div className="col-span-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-700">
                                          Max fits{" "}
                                          {Number(
                                            (item.meta as { parkingCapacity?: number })?.parkingCapacity,
                                          )}{" "}
                                          stalls at current size.
                                        </div>
                                      ) : null}
                                    </>
                                  ) : null}
                                </div>
                              ) : null}
                              <div className="mt-2 flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleSelectPlacementTarget(item.id)}
                                  disabled={item.type === "site"}
                                  className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                    item.type === "site"
                                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  {item.type === "site" ? "Configured" : item.placed ? "Re-place" : "Place"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleToggleBuildingLock(item.id)}
                                  disabled={item.type === "site"}
                                  className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                    item.type === "site"
                                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                      : item.locked
                                        ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  {item.locked ? "Locked" : "Unlock"}
                                </button>
                              </div>
                            </div>
                          ))}
                      </div>
                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        {buildingPlacements
                          .filter((item) => item.placed)
                          .map((item) => (
                            <div
                              key={item.id}
                              className={`rounded-2xl border bg-slate-50 p-3 text-xs text-slate-600 shadow-sm ${
                                activePlacementId === item.id
                                  ? "border-amber-400 ring-2 ring-amber-200"
                                  : "border-slate-200"
                              }`}
                              title={`${item.label} • ${item.w} ft x ${item.d} ft`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-800">{item.label}</span>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveBuilding(item.id)}
                                  className="text-xs font-semibold text-rose-500"
                                >
                                  Delete
                                </button>
                              </div>
                              <div className="mt-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                                <span>{SITE_OBJECT_CATALOG[item.type ?? "building"]?.label ?? "Building"}</span>
                                <span>•</span>
                                <span>{item.w} ft x {item.d} ft</span>
                              </div>
                              {typeof item.x === "number" && typeof item.y === "number" ? (
                                <div className="mt-1 text-[11px] text-slate-500">
                                  X {item.x.toFixed(1)} ft • Y {item.y.toFixed(1)} ft
                                  {lotBounds.w > 0 && lotBounds.h > 0 ? (
                                    <span className="ml-2 text-[10px] uppercase tracking-[0.12em] text-slate-400">
                                      {((item.x / lotBounds.w) * 100).toFixed(1)}% · {((item.y / lotBounds.h) * 100).toFixed(1)}%
                                    </span>
                                  ) : null}
                                </div>
                              ) : null}
                              {item.type !== "site" ? (
                                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                                  <label className="flex flex-col gap-1">
                                    Length
                                    <input
                                      type="number"
                                      value={item.w}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          w: parsePositiveNumber(event.target.value) ?? item.w,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  <label className="flex flex-col gap-1">
                                    Width
                                    <input
                                      type="number"
                                      value={item.d}
                                      onChange={(event) =>
                                        handleUpdateBuilding(item.id, {
                                          d: parsePositiveNumber(event.target.value) ?? item.d,
                                        })
                                      }
                                      className="rounded-md border border-slate-200 px-2 py-1"
                                    />
                                  </label>
                                  {SITE_OBJECT_CATALOG[item.type ?? "building"]?.defaultH !== undefined ? (
                                    <label className="col-span-2 flex flex-col gap-1">
                                      Height (ft)
                                      <input
                                        type="number"
                                        value={item.h ?? ""}
                                        onChange={(event) =>
                                          handleUpdateBuilding(item.id, {
                                            h:
                                              parsePositiveNumber(event.target.value) ??
                                              item.h,
                                          })
                                        }
                                        className="rounded-md border border-slate-200 px-2 py-1"
                                      />
                                    </label>
                                  ) : null}
                                  {item.type === "parking" ? (
                                    <label className="col-span-2 flex flex-col gap-1">
                                      Stalls
                                      <input
                                        type="number"
                                        value={item.stallCount ?? ""}
                                        onChange={(event) =>
                                          handleUpdateBuilding(item.id, {
                                            stallCount:
                                              parsePositiveNumber(event.target.value) ?? 0,
                                          })
                                        }
                                        className="rounded-md border border-slate-200 px-2 py-1"
                                      />
                                    </label>
                                  ) : null}
                                </div>
                              ) : null}
                              <div className="mt-2 flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleSelectPlacementTarget(item.id)}
                                  disabled={item.type === "site"}
                                  className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                                    item.type === "site"
                                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  {item.type === "site" ? "Configured" : "Re-place"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleToggleBuildingLock(item.id)}
                                  disabled={item.type === "site"}
                                  className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                                    item.type === "site"
                                      ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                      : item.locked
                                        ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                                  }`}
                                >
                                  {item.locked ? "Locked" : "Unlock"}
                                </button>
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-4 border-t border-slate-200 pt-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Generate Systems</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600">
                    {(
                      ["roads", "parking", "grading", "drainage", "utilities"] as const
                    ).map((system) => {
                      const status = systemStatuses[system];
                      const tone =
                        status === "fresh"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : status === "stale"
                            ? "border-amber-200 bg-amber-50 text-amber-700"
                            : "border-slate-200 bg-slate-50 text-slate-500";
                      return (
                        <span
                          key={system}
                          className={`rounded-full border px-3 py-1 ${tone}`}
                        >
                          {system} · {status.replace("_", " ")}
                        </span>
                      );
                    })}
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 md:grid-cols-3">
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("roads")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Roads</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("parking")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Parking</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("grading")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Grading</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : !hasTerrainSource ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs terrain</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("drainage")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Drainage</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : !hasTerrainSource ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs terrain</span>
                        ) : !hasBasinPlaced ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs basin</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("utilities")}
                      className="rounded-xl border border-slate-200 bg-white px-2 py-2 transition hover:bg-slate-50"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Utilities</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-600">Needs site</span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateSystem("full")}
                      className="rounded-xl border border-slate-900 bg-slate-950 px-2 py-2 text-white transition hover:bg-slate-800"
                    >
                      <div className="flex flex-col items-center gap-1">
                        <span>Full Site</span>
                        {missingSite ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-200">Needs site</span>
                        ) : !hasTerrainSource ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-200">Needs terrain</span>
                        ) : !hasBasinPlaced ? (
                          <span className="text-[10px] uppercase tracking-[0.12em] text-amber-200">Needs basin</span>
                        ) : null}
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
