import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { useCallback } from "react";

import { deleteJson } from "../../lib/api";
import type {
  Assumption,
  ChatMessage,
  Issue,
  MapAnalysis,
  ProjectRecord,
  ProjectSummary,
  SurveySlopeResponse,
} from "../types";
import type { PlanSheetSet } from "../components/PlanSheetEditor";
import { createWelcomeMessage, getChatThreadStorageKey } from "../utils/chat";
import { defaultAssumptions } from "../utils/formatting";
import { createDefaultPlanSheetSet } from "../utils/planSheetDefaults";
import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import { ACTIVE_PROJECT_STORAGE_KEY, DEFAULT_SYSTEM_STATUS, type EngineeringSystemKey, type SystemStatus } from "../utils/workflowConstants";
import type { ProjectStatusSummary, SidePanelKey } from "../utils/workspaceShell";

type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;

type UseDashboardProjectActionsOptions = {
  autosaveSuspendRef: MutableRefObject<boolean>;
  chatAutosaveTimeoutRef: MutableRefObject<number | null>;
  chatMessagesRef: MutableRefObject<ChatMessage[]>;
  controlAutosaveTimeoutRef: MutableRefObject<number | null>;
  currentProject: ProjectRecord | null;
  debugLog: (message: string, details?: Record<string, unknown>) => void;
  draftProjectPromiseRef: MutableRefObject<Promise<ProjectRecord | null> | null>;
  projectId: string;
  projectLoadRequestRef: MutableRefObject<number>;
  projects: ProjectSummary[];
  refreshProjects: (token: string) => Promise<void>;
  removeProjectSummary: (projectIdToRemove: string) => void;
  resetWorkspaceState: () => void;
  resolvedProjectIdRef: MutableRefObject<string>;
  setActiveJobId: Dispatch<SetStateAction<string>>;
  setActiveSidePanel: Dispatch<SetStateAction<SidePanelKey | null>>;
  setAssumptions: Dispatch<SetStateAction<Assumption[]>>;
  setBuildingCount: Dispatch<SetStateAction<string>>;
  setBuildingDepth: Dispatch<SetStateAction<string>>;
  setBuildingWidth: Dispatch<SetStateAction<string>>;
  setChatMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  setCurrentProject: Dispatch<SetStateAction<ProjectRecord | null>>;
  setDrainage: Dispatch<SetStateAction<boolean>>;
  setFileName: Dispatch<SetStateAction<string>>;
  setFileNameAuto: Dispatch<SetStateAction<boolean>>;
  setGrading: Dispatch<SetStateAction<boolean>>;
  setImageName: Dispatch<SetStateAction<string>>;
  setIssues: Dispatch<SetStateAction<Issue[]>>;
  setLeftSidebarOpen: Dispatch<SetStateAction<boolean>>;
  setLotHeight: Dispatch<SetStateAction<string>>;
  setLotWidth: Dispatch<SetStateAction<string>>;
  setMapAnalysis: Dispatch<SetStateAction<MapAnalysis | null>>;
  setMapSnapshotPath: Dispatch<SetStateAction<string>>;
  setMaxAdaCrossSlopePct: Dispatch<SetStateAction<string>>;
  setMaxParkingSlopePct: Dispatch<SetStateAction<string>>;
  setMaxRoadGradePct: Dispatch<SetStateAction<string>>;
  setMinSlopePct: Dispatch<SetStateAction<string>>;
  setParkingAdaAisleWidth: Dispatch<SetStateAction<string>>;
  setParkingAdaCount: Dispatch<SetStateAction<string>>;
  setParkingAisleWidth: Dispatch<SetStateAction<string>>;
  setParkingAngle: Dispatch<SetStateAction<"45" | "60" | "90">>;
  setParkingCompactCount: Dispatch<SetStateAction<string>>;
  setParkingCompactWidth: Dispatch<SetStateAction<string>>;
  setParkingCount: Dispatch<SetStateAction<string>>;
  setParkingLoading: Dispatch<SetStateAction<"single" | "double">>;
  setParkingStallDepth: Dispatch<SetStateAction<string>>;
  setParkingStallWidth: Dispatch<SetStateAction<string>>;
  setPipeMinSlopePct: Dispatch<SetStateAction<string>>;
  setPlanSheetSet: Dispatch<SetStateAction<PlanSheetSet>>;
  setProjectDrawerNotice: (message: string) => void;
  setProjectId: Dispatch<SetStateAction<string>>;
  setProjectType: Dispatch<SetStateAction<string>>;
  setPrompt: Dispatch<SetStateAction<string>>;
  setRenderedSidePanel: Dispatch<SetStateAction<SidePanelKey | null>>;
  setRightRailCollapsed: Dispatch<SetStateAction<boolean>>;
  setRoads: Dispatch<SetStateAction<boolean>>;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setSetback: Dispatch<SetStateAction<string>>;
  setSidePanelVisible: Dispatch<SetStateAction<boolean>>;
  setSiteName: Dispatch<SetStateAction<string>>;
  setSiteNameAuto: Dispatch<SetStateAction<boolean>>;
  setStatusMessage: (message: string) => void;
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
  setSystemStatuses: Dispatch<SetStateAction<Record<EngineeringSystemKey, SystemStatus>>>;
  setUnits: Dispatch<SetStateAction<string>>;
  setUploadedImageApiUrl: Dispatch<SetStateAction<string>>;
  setUploadedImagePreviewUrl: Dispatch<SetStateAction<string>>;
  setUseSurveyForGrading: Dispatch<SetStateAction<boolean>>;
  setUtilities: Dispatch<SetStateAction<boolean>>;
  setWorkspaceChromeMinimized: Dispatch<SetStateAction<boolean>>;
  setWorkspaceRestoreState: Dispatch<SetStateAction<"idle" | "restored" | "failed">>;
  suppressProjectAutoLoadRef: MutableRefObject<boolean>;
  token: string | null;
  updateProjectStatus: UpdateProjectStatus;
};

export function useDashboardProjectActions({
  autosaveSuspendRef,
  chatAutosaveTimeoutRef,
  chatMessagesRef,
  controlAutosaveTimeoutRef,
  currentProject,
  debugLog,
  draftProjectPromiseRef,
  projectId,
  projectLoadRequestRef,
  projects,
  refreshProjects,
  removeProjectSummary,
  resetWorkspaceState,
  resolvedProjectIdRef,
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
  setStatusMessage,
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
}: UseDashboardProjectActionsOptions) {
  const handleNewProject = useCallback(async () => {
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
    setSourceEffectRows([]);
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
  }, [
    autosaveSuspendRef,
    chatAutosaveTimeoutRef,
    chatMessagesRef,
    controlAutosaveTimeoutRef,
    debugLog,
    draftProjectPromiseRef,
    projectLoadRequestRef,
    resetWorkspaceState,
    resolvedProjectIdRef,
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
    setStatusMessage,
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
  ]);

  const handleDeleteProject = useCallback(async (projectIdToDelete: string) => {
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
  }, [
    currentProject?.project_id,
    handleNewProject,
    projectId,
    projects,
    refreshProjects,
    removeProjectSummary,
    setProjectDrawerNotice,
    token,
    updateProjectStatus,
  ]);

  return { handleDeleteProject, handleNewProject };
}
