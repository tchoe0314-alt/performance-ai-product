"use client";
/* eslint-disable react-hooks/exhaustive-deps */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getJson, postBinary, postForm, postJson } from "../lib/api";

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
  PlanAction,
  SurveySlopeResponse,
  MapAnalysis,
  PreviewResponse,
  UploadImageResponse,
  UploadSurveyResponse,
  PlanToolMode,
  StrategyMode,
  ControlOverrides,
  ChatDecisionResponse,
  ChatMessage,
  LearningReport,
  DisciplineToggle,
  Preview3DItem,
  PlanRequestPayload,
  PreviewRequestPayload,
} from "./types";

import {
  defaultAssumptions,
  toReadableLabel,
  joinNatural,
  toArray,
  toMetricValue,
  readPositiveNumber,
  parsePositiveNumber,
  readMetricValue,
  summarizePlanResponse,
} from "./utils/formatting";

import {
  createChatMessage,
  createWelcomeMessage,
  extractDesignMemory,
} from "./utils/chat";

import { uploadedImageSrc } from "./utils/auth";

import AppHeader from "./components/AppHeader";
import AuthScreen from "./components/AuthScreen";
import ProjectSidebar from "./components/ProjectSidebar";
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
  const [strategyMode, setStrategyMode] = useState<StrategyMode>("assisted");
  const [projectType, setProjectType] = useState("");
  const [units, setUnits] = useState("ft");
  const [prompt, setPrompt] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [
    createWelcomeMessage(),
  ]);
  const [learningReport, setLearningReport] = useState<LearningReport | null>(null);
  const [learningReportUpdatedAt, setLearningReportUpdatedAt] = useState<number | null>(null);
  const [, setQueuedPhaseNotes] = useState<string[]>([]);
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
  const [minSlopePct, setMinSlopePct] = useState("");
  const [pipeMinSlopePct, setPipeMinSlopePct] = useState("");
  const [maxParkingSlopePct, setMaxParkingSlopePct] = useState("");
  const [maxRoadGradePct, setMaxRoadGradePct] = useState("");
  const [maxAdaCrossSlopePct, setMaxAdaCrossSlopePct] = useState("");
  const [roads, setRoads] = useState(true);
  const [grading, setGrading] = useState(true);
  const [drainage, setDrainage] = useState(true);
  const [utilities, setUtilities] = useState(true);

  const [assumptions, setAssumptions] =
    useState<Assumption[]>(defaultAssumptions);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [backendResult, setBackendResult] = useState<PlanResponse | null>(null);
  const [uploadedImagePreviewUrl, setUploadedImagePreviewUrl] = useState("");
  const [uploadedImageApiUrl, setUploadedImageApiUrl] = useState("");
  const [surveyFileName, setSurveyFileName] = useState("");
  const [surveySlopeEstimate, setSurveySlopeEstimate] = useState<SurveySlopeResponse | null>(null);
  const [mapSnapshotPath, setMapSnapshotPath] = useState("");
  const [mapAnalysis, setMapAnalysis] = useState<MapAnalysis | null>(null);
  const [planPreviewUrl, setPlanPreviewUrl] = useState("");
  const [planPreviewSummary, setPlanPreviewSummary] =
    useState<PreviewResponse["summary"] | null>(null);
  const [planPreviewAnnotations, setPlanPreviewAnnotations] =
    useState<PreviewResponse["preview_annotations"] | null>(null);
  const [previewMode, setPreviewMode] = useState<"2d" | "3d">("2d");
  const [previewInteraction, setPreviewInteraction] = useState<"static" | "interactive">("interactive");
  const [previewQuality, setPreviewQuality] = useState<"standard" | "high">("standard");
  const [previewLabelDensity, setPreviewLabelDensity] = useState<"low" | "standard" | "high">("standard");
  const [previewLabelDensityTouched, setPreviewLabelDensityTouched] = useState(false);
  const [previewRenderMode, setPreviewRenderMode] = useState<"production" | "engineering" | "debug">("production");
  const [previewRefreshing, setPreviewRefreshing] = useState(false);
  const [previewRefreshNote, setPreviewRefreshNote] = useState<string | null>(null);
  const [approvalInFlight, setApprovalInFlight] = useState(false);
  const [approvalPhaseLabel, setApprovalPhaseLabel] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approvalPendingJobId, setApprovalPendingJobId] = useState<string | null>(null);
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [showCalculations, setShowCalculations] = useState(false);
  const [autoAdvancePhases, setAutoAdvancePhases] = useState(false);
  const [revisePhaseTarget, setRevisePhaseTarget] = useState<
    "layout" | "grading" | "drainage_storm" | "utilities" | "coordination_validation"
  >("layout");
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
  const queuedPhaseNotesRef = useRef<string[]>([]);
  const queuedNotesApplyingRef = useRef(false);
  const autoAdvanceByJobRef = useRef<Record<string, boolean>>({});
  const previewRecoveryKeyRef = useRef("");
  const lastSiteInputProjectRef = useRef("");
  const controlAutosaveTimeoutRef = useRef<number | null>(null);

  const {
    projects,
    setProjects,
    refreshProjects,
    upsertProjectSummary,
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
    strategy,
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
  }: {
    strategy: "manual" | "assisted";
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
    } else if (strategy === "manual") {
      manualFields.lot = { x: 0, y: 0, w: 0, h: 0 };
    }

    if (setbackValue !== null) {
      manualFields.setback = setbackValue;
    } else if (strategy === "manual") {
      manualFields.setback = 0;
    }

    if (buildingWidthValue !== null) {
      manualFields.building_width = buildingWidthValue;
    } else if (strategy === "manual") {
      manualFields.building_width = 0;
    }

    if (buildingDepthValue !== null) {
      manualFields.building_depth = buildingDepthValue;
    } else if (strategy === "manual") {
      manualFields.building_depth = 0;
    }

    if (buildingCountValue !== null) {
      manualFields.buildings = Array.from({ length: Math.max(1, Math.round(buildingCountValue)) }).map(
        (_, idx) => ({
          name: `Building ${idx + 1}`,
          w: buildingWidthValue ?? undefined,
          d: buildingDepthValue ?? undefined,
        }),
      );
    }

    if (parkingCountValue !== null) {
      manualFields.site_plan = { parking_count: parkingCountValue };
    } else if (strategy === "manual") {
      manualFields.site_plan = { parking_count: 0 };
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

    return manualFields;
  }, []);

  const payloadPreview = useMemo(
    () => ({
      project_id: projectId || null,
      full_design_mode: true,
      input_mode: strategyMode,
      strict_mode: strategyMode === "manual",
      prompt_text: prompt || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
      },
      manual_fields: buildManualFields({
        strategy: strategyMode,
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
      allow_ai_fill_for_blanks: strategyMode !== "manual",
    }),
    [
      projectId,
      strategyMode,
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

  const refreshLearningReport = async () => {
    if (!token) return;
    try {
      const data = await getJson<{ success: boolean; report: LearningReport | null }>(
        "/api/chat/learning-report",
        { token },
      );
      setLearningReport(data.report ?? null);
      setLearningReportUpdatedAt(Date.now());
    } catch {
      // Ignore learning report failures.
    }
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

  useEffect(() => {
    if (!token) return;
    void refreshLearningReport();
  }, [token]);

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
    const drainageFields = (manualFields.drainage ?? {}) as { min_pipe_slope_pct?: number };
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

    const nextMode = projectInput.input_mode ?? (projectInput.strict_mode ? "manual" : "assisted");
    setStrategyMode(nextMode === "manual" ? "manual" : "assisted");
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
    setParkingCount(String(sitePlan.parking_count ?? ""));
    setMinSlopePct(String(gradingFields.min_slope_pct ?? ""));
    setPipeMinSlopePct(String(drainageFields.min_pipe_slope_pct ?? ""));
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

  const applyControlOverrides = (overrides: ControlOverrides) => {
    if (overrides.strategyMode) {
      setStrategyMode(overrides.strategyMode);
    }
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
    const nextStrategy = overrides.strategyMode ?? strategyMode;
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
      strategy_mode: nextStrategy,
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
  ): PlanRequestPayload => {
    const nextStrategy = overrides.strategyMode ?? strategyMode;
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
      input_mode: nextStrategy,
      strict_mode: nextStrategy === "manual",
      prompt_text: (promptOverride ?? prompt) || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
      },
      manual_fields: buildManualFields({
        strategy: nextStrategy,
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
      }),
      allow_ai_fill_for_blanks: nextStrategy !== "manual",
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
      const nextStrategy = overrides.strategyMode ?? strategyMode;
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
          nextStrategy === "manual"
            ? "Civora AI needs a more explicit design request before running in Manual mode."
            : "Civora AI needs a little more direction before generating a design.",
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
    if (busy || visibleActiveJob) {
      appendChatMessage("user", trimmed || "Uploaded an image.");
      if (trimmed) {
        setQueuedPhaseNotes((current) => {
          const next = [...current, trimmed];
          queuedPhaseNotesRef.current = next;
          return next;
        });
        if (normalizedStatus === "awaiting_approval") {
          void applyQueuedPhaseNotes();
        } else {
          setStatusMessage("Queued your note to apply after the current phase finishes.");
        }
      }
      setPrompt("");
      return;
    }
    void runOrchestrator("run");
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
      previewNextPendingPhase?.label ||
      previewRunningPhase?.label ||
      toReadableLabel(revisePhaseTarget);
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

  const applyQueuedPhaseNotes = async () => {
    if (!visibleActiveJob?.job_id || !token) return;
    const queued = queuedPhaseNotesRef.current;
    if (!queued.length) return;
    if (queuedNotesApplyingRef.current) return;
    queuedNotesApplyingRef.current = true;
    const combinedNotes = queued.map((note) => `- ${note}`).join("\n");
    appendChatMessage(
      "assistant",
      `Applying queued notes to the next phase:\n${combinedNotes}`,
      "status",
    );
    const targetProjectId =
      projectId || visibleActiveJob.project_id || currentProject?.project_id || null;
    if (targetProjectId) {
      const baseInput = currentProject?.project_input ?? payloadPreview;
      const nextThread = [
        ...chatMessagesRef.current,
        createChatMessage("user", combinedNotes),
      ];
      await saveProject({
        silent: true,
        projectIdOverride: targetProjectId,
        projectInputOverride: {
          ...baseInput,
          prompt_text: combinedNotes,
          meta: {
            ...(baseInput.meta ?? {}),
            chat_thread: nextThread,
          },
        },
      });
    }
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${visibleActiveJob.job_id}/revise`,
        { target_phase: revisePhaseTarget },
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
      setActiveJobId(data.job.job_id);
      setQueuedPhaseNotes([]);
      queuedPhaseNotesRef.current = [];
      appendChatMessage(
        "assistant",
        `Queued notes applied. Requeued ${data.job.job_id} to revise ${toReadableLabel(revisePhaseTarget)}.`,
        "status",
      );
    } catch (error) {
      appendChatMessage(
        "assistant",
        error instanceof Error ? error.message : "Could not apply queued notes.",
        "status",
      );
    } finally {
      queuedNotesApplyingRef.current = false;
    }
  };

  useEffect(() => {
    const jobId = visibleActiveJob?.job_id;
    if (!jobId) return;
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") {
      autoAdvanceByJobRef.current[jobId] = false;
    }
  }, [visibleActiveJob?.job_id, visibleActiveJob?.status]);

  useEffect(() => {
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") return;
    if (!queuedPhaseNotesRef.current.length) return;
    void applyQueuedPhaseNotes();
  }, [visibleActiveJob?.status, visibleActiveJob?.job_id]);

  useEffect(() => {
    if (!autoAdvancePhases) return;
    const jobId = visibleActiveJob?.job_id;
    if (!jobId) return;
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") return;
    if (autoAdvanceByJobRef.current[jobId]) return;
    autoAdvanceByJobRef.current[jobId] = true;
    const timeoutId = window.setTimeout(() => {
      handleContinueActiveJob();
    }, 1200);
    return () => window.clearTimeout(timeoutId);
  }, [autoAdvancePhases, visibleActiveJob?.job_id, visibleActiveJob?.status]);

  const handleReviseActiveJob = async () => {
    if (!visibleActiveJob?.job_id || !token) return;
    try {
      const targetProjectId =
        projectId || visibleActiveJob.project_id || currentProject?.project_id || null;
      if (targetProjectId) {
        await saveProject({
          silent: true,
          projectIdOverride: targetProjectId,
        });
      }
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${visibleActiveJob.job_id}/revise`,
        { target_phase: revisePhaseTarget },
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
        `Saved your changes and requeued ${data.job.job_id} to revise ${toReadableLabel(revisePhaseTarget)}.`,
        "status",
      );
      setStatusMessage(
        `Saved your changes. Requeued ${data.job.job_id} to revise ${toReadableLabel(revisePhaseTarget)}.`,
      );
      if (data.job.job_id) {
        setActiveJobId(data.job.job_id);
      }
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Could not revise the current phase.",
      );
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
    setSurveyFileName(String(surveyFile?.stored_filename || ""));
    setSurveySlopeEstimate(slopeEstimate || null);
    const mapUrl = String(mapSnapshot?.image_url || "");
    if (mapUrl) {
      setUploadedImageApiUrl(uploadedImageSrc(mapUrl, token));
    }
    setMapSnapshotPath(String(mapSnapshot?.image_path || ""));
    setMapAnalysis(mapAnalysisResult || null);
  }, [currentProject, token]);

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
          const modeLabel = strategyMode === "manual" ? "Manual mode" : "Assisted mode";
          appendChatMessage(
            "assistant",
            `${toReadableLabel(stageLabel)} stage complete. Waiting for your approval. ${modeLabel}.`,
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
          const modeLabel = strategyMode === "manual" ? "Manual mode" : "Assisted mode";
          appendChatMessage(
            "assistant",
            `${toReadableLabel(stageLabel)} stage complete. Waiting for your approval. ${modeLabel}.`,
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
    try {
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
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Image uploaded.");
    } catch (error) {
      setImageName(file.name);
      setStatusMessage(
        error instanceof Error ? error.message : "Image upload failed.",
      );
    }
  };

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
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        survey_file: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          survey_url: data.survey_url || "",
        },
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Survey uploaded.");
    } catch (error) {
      setSurveyFileName(file.name);
      setStatusMessage(
        error instanceof Error ? error.message : "Survey upload failed.",
      );
    }
  };

  const estimateSurveySlope = async () => {
    if (!token || !surveyFileName) return;
    try {
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
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
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
      render_labels:
        previewInteraction === "interactive" ||
        previewRenderMode === "engineering" ||
        previewRenderMode === "debug" ||
        previewQuality === "high",
      preview_mode: previewRenderMode,
      preview_layers: previewLayerList,
    };
    try {
      const data = await postJson<PreviewResponse>("/api/preview", previewPayload, {
        token,
      });
      setPlanPreviewUrl(data.preview_image_data_url);
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

  const queuePreviewRefresh = (reason: string) => {
    if (!token) return;
    if (!backendResult && !projectId && !planPreviewUrl) {
      setStatusMessage("Run the planner first so there is something to preview.");
      return;
    }
    previewRefreshIntentRef.current = { reason, track: true };
  };

  const handlePreviewPlan = async () => {
    if (!token) return;
    if (!backendResult && !projectId) {
      setStatusMessage("Run the planner first so there is something to preview.");
      return;
    }
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

  const handleNewProject = async () => {
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
    setMapSnapshotPath("");
    setMapAnalysis(null);
    setBackendResult(null);
    setPlanPreviewUrl("");
    setPlanPreviewSummary(null);
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
    setMinSlopePct("");
    setPipeMinSlopePct("");
    setMaxParkingSlopePct("");
    setMaxRoadGradePct("");
    setMaxAdaCrossSlopePct("");
    setRoads(true);
    setGrading(true);
    setDrainage(true);
    setUtilities(true);
    setStrategyMode("assisted");
    const nextThread = [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
    setStatusMessage("Started a new project.");
    try {
      if (token) {
        draftProjectPromiseRef.current = saveProject({
          silent: true,
          projectIdOverride: null,
          nameOverride: "",
          fileNameOverride: "",
          projectInputOverride: {
            input_mode: "assisted",
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
            allow_ai_fill_for_blanks: true,
          },
          latestResultOverride: {},
          autoNamedOverride: false,
          autoFileNamedOverride: false,
        });
        const createdProject = await draftProjectPromiseRef.current;
        if (createdProject?.project_id) {
          resolvedProjectIdRef.current = createdProject.project_id;
          setProjectId(createdProject.project_id);
        }
      }
    } finally {
      draftProjectPromiseRef.current = null;
      suppressProjectAutoLoadRef.current = false;
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

  useEffect(() => {
    if (!token || projectId || projects.length === 0 || suppressProjectAutoLoadRef.current) return;
    const preferredProject =
      projects.find((project) => project.has_result) ?? projects[0];
    if (!preferredProject) return;
    void loadProject(preferredProject.project_id);
  }, [token, projectId, projects]);

  const {
    previewReview,
    previewAssumptionCategories,
    previewFixActions,
    previewFixTargets,
    previewReviewCategories,
    previewBlockedReasons,
    previewFailedDeliverables,
    previewExtraDeliverables,
    previewReadyDeliverables,
    previewPhaseEntries,
    combinedPreviewPhase,
    previewCompletedPhaseCount,
    previewTotalPhaseCount,
    previewRunningPhase,
    previewNextPendingPhase,
    previewRerunSignals,
  } = usePreviewReview({ currentPlanMeta, planPreviewSummary });
  const workflowStatus = useMemo(() => {
    const modeLabel = strategyMode === "manual" ? "Manual" : "Assisted";
    const normalizedStatus = String(visibleActiveJob?.status || "").toLowerCase();
    const phaseLabel =
      previewRunningPhase?.label ||
      previewNextPendingPhase?.label ||
      String(visibleActiveJob?.stage || "").trim() ||
      "Awaiting input";
    let stateLabel = "Waiting for input";
    let stateDetail = "Ready for a new request.";
    if (normalizedStatus === "queued") {
      stateLabel = "Queued";
      stateDetail = "Waiting for a worker to start the next phase.";
    } else if (normalizedStatus === "running") {
      stateLabel = "Running";
      stateDetail = String(visibleActiveJob?.stage_detail || "Engineering in progress.");
    } else if (normalizedStatus === "awaiting_approval") {
      stateLabel = "Waiting for approval";
      stateDetail = "Review the current phase and approve to continue.";
    } else if (normalizedStatus === "cancelling") {
      stateLabel = "Cancelling";
      stateDetail = "Stopping the current run.";
    } else if (normalizedStatus === "completed") {
      stateLabel = "Complete";
      stateDetail = "All requested phases are finished.";
    } else if (previewReview?.release_status === "blocked") {
      stateLabel = "Blocked";
      stateDetail = previewReview.release_note || "Review issues before continuing.";
    }
    return { modeLabel, phaseLabel, stateLabel, stateDetail };
  }, [previewNextPendingPhase?.label, previewReview?.release_note, previewReview?.release_status, previewRunningPhase?.label, strategyMode, visibleActiveJob?.stage, visibleActiveJob?.stage_detail, visibleActiveJob?.status]);
  const gatingPhaseKey =
    !autoAdvancePhases &&
    String(visibleActiveJob?.status || "").toLowerCase() === "awaiting_approval"
      ? previewRunningPhase?.key || previewNextPendingPhase?.key || revisePhaseTarget
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
      ["BUILDING", "STRUCTURE", "PAD"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.roads) {
      ["ROAD", "PAVEMENT", "PARKING", "WALK"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.grading) {
      ["SURFACE", "FG_CONTOUR", "EG_CONTOUR", "SPOT_FG", "DRAIN_FLOW", "FLOW_ARROW"].forEach((layer) =>
        layers.add(layer),
      );
    }
    if (previewLayersEffective.drainage) {
      ["DRAIN", "PIPE", "STORM", "BASIN_BOUNDARY"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.utilities) {
      ["UTILITY", "WATER", "SAN"].forEach((layer) => layers.add(layer));
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
    if (!backendResult && !planPreviewUrl) return;
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
    previewRenderMode,
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
      if (previewRenderMode === "production" && previewRole !== "final") continue;
      if (previewRenderMode === "engineering" && !["final", "overlay"].includes(previewRole)) continue;

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
  }, [backendResult, previewLayersEffective, previewRenderMode]);
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
  useEffect(() => {
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") return;
    const nextKey =
      previewRunningPhase?.key ||
      previewNextPendingPhase?.key ||
      revisePhaseTarget;
    if (nextKey) {
      setRevisePhaseTarget(nextKey as typeof revisePhaseTarget);
    }
  }, [visibleActiveJob?.status, previewRunningPhase?.key, previewNextPendingPhase?.key, revisePhaseTarget]);
  const whatYouNeedSummary = (() => {
    const manualFields =
      currentProject?.project_input?.manual_fields && typeof currentProject.project_input.manual_fields === "object"
        ? currentProject.project_input.manual_fields
        : {};
    const lot = (manualFields.lot && typeof manualFields.lot === "object" ? manualFields.lot : {}) as {
      w?: number;
      h?: number;
    };
    const sitePlan =
      (manualFields.site_plan && typeof manualFields.site_plan === "object"
        ? manualFields.site_plan
        : {}) as { parking_count?: number };
    const projectTypeValue = String(
      manualFields.project_type || projectType || "",
    ).trim();
    const lotWidthValue = readPositiveNumber(lot.w ?? lotWidth);
    const lotHeightValue = readPositiveNumber(lot.h ?? lotHeight);
    const parkingValue = readPositiveNumber(sitePlan.parking_count ?? parkingCount);
    const buildingWidthValue = readPositiveNumber(manualFields.building_width ?? buildingWidth);
    const buildingDepthValue = readPositiveNumber(manualFields.building_depth ?? buildingDepth);
    const requestedDeliverables = new Set(
      toArray(previewReview?.requested_deliverables)
        .map((item: unknown) => String(item || "").trim())
        .filter(Boolean),
    );
    const disciplineSet = new Set(
      [
        ...toArray(manualFields.disciplines),
        roads ? "corridor" : null,
        grading ? "grading" : null,
        drainage ? "drainage" : null,
        utilities ? "utility" : null,
      ]
        .map((item: unknown) => String(item || "").trim().toLowerCase())
        .filter(Boolean),
    );
    const neededNow: string[] = [];
    const supporting: string[] = [];
    const inScope: string[] = [];

    if (!projectTypeValue) {
      neededNow.push("site type or land use");
    }
    if (!lotWidthValue || !lotHeightValue) {
      neededNow.push("lot size or boundary dimensions");
    }
    if (!buildingWidthValue || !buildingDepthValue) {
      neededNow.push("building footprint dimensions");
    }
    if (!parkingValue) {
      neededNow.push("parking target or building program");
    }

    if (disciplineSet.has("corridor") || requestedDeliverables.has("site_plan")) {
      inScope.push("roads and site access");
      supporting.push("frontage access constraints");
    }
    if (disciplineSet.has("grading") || requestedDeliverables.has("grading_plan")) {
      inScope.push("grading");
      supporting.push("survey, slope, or benchmark elevations");
    }
    if (disciplineSet.has("drainage") || requestedDeliverables.has("storm_pipe_plan")) {
      inScope.push("drainage and storm");
      supporting.push("storm outfall or drainage direction");
      supporting.push("existing drainage patterns");
    }
    if (disciplineSet.has("utility") || requestedDeliverables.has("utility_plan")) {
      inScope.push("utilities");
      supporting.push("water and sanitary tie-in points");
      supporting.push("utility maps or known connection locations");
    }

    const blocked = previewBlockedReasons.filter(Boolean);
    const note =
      blocked.length > 0
        ? `The current blockers are ${joinNatural(blocked, 3)}.`
        : previewReview?.release_status === "ready"
          ? "The core design inputs look complete enough for release-ready review."
          : neededNow.length
            ? "Filling the missing inputs below will make the next run more reliable."
            : "The core design inputs are already in place. The supporting items below would sharpen the engineering output.";

    return {
      neededNow: Array.from(new Set(neededNow)),
      supporting: Array.from(new Set(supporting)).filter((item) => !neededNow.includes(item)),
      inScope: Array.from(new Set(inScope)),
      note,
    };
  })();

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
          projects={projects}
          activeProjectId={projectId}
          onSelectProject={(nextProjectId) => {
            void loadProject(nextProjectId);
          }}
          onViewDocs={async (nextProjectId) => {
            await loadProject(nextProjectId);
            await handlePreviewPlan();
            setPreviewFullscreenOpen(true);
          }}
          onLogout={handleLogout}
        />

        <div className="flex min-h-screen">
          <ProjectSidebar
            onNewProject={handleNewProject}
            chatMessages={chatMessages}
            learningReport={learningReport}
            learningReportUpdatedAt={learningReportUpdatedAt}
            onRefreshLearningReport={refreshLearningReport}
            previewAssumptionCategories={previewAssumptionCategories}
            previewFixActions={previewFixActions}
            previewFixTargets={previewFixTargets}
            previewReviewCategories={previewReviewCategories}
            previewBlockedReasons={previewBlockedReasons}
            previewReadyDeliverables={previewReadyDeliverables}
            previewFailedDeliverables={previewFailedDeliverables}
            previewExtraDeliverables={previewExtraDeliverables}
            previewReviewReadyCount={previewReadyDeliverables.length}
            previewReviewRequestedCount={
              (previewReview?.requested_deliverables ?? []).length ||
              previewReadyDeliverables.length
            }
            previewRerunTotal={previewReview?.rerun_total ?? 0}
            whatYouNeedSummary={whatYouNeedSummary}
            previewRerunSignals={previewRerunSignals}
            issues={issues}
            issueTargets={issueTargets}
            previewInteraction={previewInteraction}
            selectedIssueId={selectedIssueId}
            onSelectIssue={setSelectedIssueId}
            totalPipeLength={totalPipeLength}
            maxSlope={maxSlope}
            minSlope={minSlope}
            flowCfs={flowCfs}
            cutFillNet={cutFillNet}
            basinSize={basinSize}
            showMeasurements={showMeasurements}
            showCalculations={showCalculations}
            onToggleMeasurements={() => setShowMeasurements((prev) => !prev)}
            onToggleCalculations={() => setShowCalculations((prev) => !prev)}
            previewLayers={previewLayers}
            onTogglePreviewLayer={(key) =>
              setPreviewLayers((prev) => ({ ...prev, [key]: !prev[key] }))
            }
            onQueuePreviewRefresh={queuePreviewRefresh}
            mapSnapshotInputRef={mapSnapshotInputRef}
            surveyInputRef={surveyInputRef}
            onUploadImage={uploadImage}
            onUploadSurvey={uploadSurvey}
            surveyFileName={surveyFileName}
            surveySlopeEstimate={surveySlopeEstimate}
            mapSnapshotPath={mapSnapshotPath}
            mapAnalysis={mapAnalysis}
            uploadedImageApiUrl={uploadedImageApiUrl}
            uploadedImagePreviewUrl={uploadedImagePreviewUrl}
            onEstimateSurveySlope={estimateSurveySlope}
            onAnalyzeMapSnapshot={analyzeMapSnapshot}
            quantityRollupsEnabled={quantityRollupsEnabled}
            onToggleQuantityRollups={() => setQuantityRollupsEnabled((prev) => !prev)}
            quantityRows={quantityRows}
          />

          <main className="flex min-w-0 flex-1 flex-col">
            <WorkspaceToolbar
              onRefreshWorkspace={handleRefreshWorkspace}
            />

            <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-6 md:px-6">
              <ProjectControls
                strategyMode={strategyMode}
                onStrategyModeChange={setStrategyMode}
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

              <div className="rounded-[24px] border border-slate-200 bg-white/90 p-4 shadow-[0_14px_45px_-30px_rgba(15,23,42,0.4)]">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Workflow Status
                    </p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">
                      {workflowStatus.stateLabel}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      {workflowStatus.stateDetail}
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 text-sm text-slate-600">
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Mode: {workflowStatus.modeLabel}
                    </span>
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Phase: {workflowStatus.phaseLabel}
                    </span>
                  </div>
                </div>
              </div>

              <ChatPanel
                chatMessages={chatMessages}
                chatScrollRef={chatScrollRef}
                onSetMessageFeedback={setMessageFeedback}
                thinkingState={thinkingState}
                busy={busy}
                activePlanTool={activePlanTool}
                visibleActiveJobStatus={visibleActiveJob?.status ?? ""}
                hasDirectRunInFlight={hasDirectRunInFlight}
                autoAdvancePhases={autoAdvancePhases}
                onToggleAutoAdvance={() => setAutoAdvancePhases((prev) => !prev)}
                revisePhaseTarget={revisePhaseTarget}
                onRevisePhaseTargetChange={setRevisePhaseTarget}
                onCancelJob={handleCancelActiveJob}
                onReviseJob={handleReviseActiveJob}
                onContinueJob={handleContinueActiveJob}
                prompt={prompt}
                imageName={imageName}
                onPromptChange={setPrompt}
                onPromptKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey &&
                    !(event.nativeEvent as KeyboardEvent).isComposing
                  ) {
                    event.preventDefault();
                    if (prompt.trim() || imageName) {
                      handleSendMessage();
                    }
                  }
                }}
                onSendMessage={handleSendMessage}
                onUploadImage={uploadImage}
                onExplainPlan={handleExplainPlan}
                onRunFix={() => void runOrchestrator("fix")}
                onRunImprove={() => void runOrchestrator("improve")}
                onSaveProject={() => void saveProject()}
                canExplain={Boolean(backendResult || selectedRun)}
                statusMessage={statusMessage}
                hasVisibleActiveJob={Boolean(visibleActiveJob)}
                approvalState={approvalStatus.state}
                approvalPhaseLabel={approvalStatus.label}
                approvalError={approvalError}
              />

            <PreviewPanel
              previewReview={previewReview}
              previewTotalPhaseCount={previewTotalPhaseCount}
              previewCompletedPhaseCount={previewCompletedPhaseCount}
              previewRunningPhase={previewRunningPhase}
              previewNextPendingPhase={previewNextPendingPhase}
              onRefreshPreview={handlePreviewPlan}
              busy={busy}
              planPreviewUrl={planPreviewUrl}
              previewMode={previewMode}
              previewInteraction={previewInteraction}
              previewQuality={previewQuality}
              previewLabelDensity={previewLabelDensity}
              previewRenderMode={previewRenderMode}
              onSetPreviewMode={setPreviewMode}
              onSetPreviewInteraction={setPreviewInteraction}
              onSetPreviewQuality={setPreviewQuality}
              onSetPreviewLabelDensity={(value) => {
                setPreviewLabelDensityTouched(true);
                setPreviewLabelDensity(value);
              }}
              onSetPreviewRenderMode={setPreviewRenderMode}
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
              />
            </div>
          </main>
      </div>
    </div>
    </div>
  );
}
