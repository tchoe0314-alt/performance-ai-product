import type { MutableRefObject } from "react";
import { useCallback, useEffect } from "react";

import { getJson } from "../../lib/api";
import type { Issue, JobSummary, PlanResponse, PreviewResponse, ProjectInput, ProjectRecord } from "../types";
import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import { ACTIVE_PROJECT_STORAGE_KEY } from "../utils/workflowConstants";
import type { ProjectStatusSummary } from "../utils/workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;

type UseDashboardProjectLoadOptions = {
  activeJob: JobSummary | null | undefined;
  activeJobId: string;
  applyProjectInput: (projectInput: ProjectInput) => void;
  autosaveSuspendRef: MutableRefObject<boolean>;
  chatAutosaveTimeoutRef: MutableRefObject<number | null>;
  controlAutosaveTimeoutRef: MutableRefObject<number | null>;
  currentProject: ProjectRecord | null;
  currentProjectActiveJob: JobSummary | null | undefined;
  effectiveDemoWorkspaceEnabled: boolean;
  loadJobRef: MutableRefObject<((id: string) => Promise<void> | void) | null>;
  loadProjectResultInBackgroundRef: MutableRefObject<((project: ProjectRecord) => void) | null>;
  projectId: string;
  projectLoadRequestRef: MutableRefObject<number>;
  resetWorkspaceStateRef: MutableRefObject<(() => void) | null>;
  resolvedProjectIdRef: MutableRefObject<string>;
  restoredActiveProjectRef: MutableRefObject<boolean>;
  setBackendResult: StateSetter<PlanResponse | null>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setIssues: StateSetter<Issue[]>;
  setPlanPreviewSummary: StateSetter<PreviewResponse["summary"] | null>;
  setPlanPreviewUrl: StateSetter<string>;
  setProjectDrawerNotice: (message: string) => void;
  setProjectId: StateSetter<string>;
  setSiteName: StateSetter<string>;
  setWorkspaceRestoreState: StateSetter<"idle" | "restored" | "failed">;
  token: string | null;
  updateProjectStatus: UpdateProjectStatus;
};

export function useDashboardProjectLoad({
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
}: UseDashboardProjectLoadOptions) {
  const loadProject = useCallback(async (id: string) => {
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
      resetWorkspaceStateRef.current?.();
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
      loadProjectResultInBackgroundRef.current?.(project);
      if (activeJobId && (!projectId || currentProjectActiveJob?.project_id === id || activeJob?.project_id === id)) {
        void loadJobRef.current?.(activeJobId);
      }
    } catch (error) {
      const errorStatus =
        typeof error === "object" && error !== null && "status" in error
          ? Number((error as { status?: unknown }).status)
          : undefined;
      const missingProject =
        errorStatus === 404 ||
        (error instanceof Error && /project not found/i.test(error.message));
      if (missingProject) {
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
        }
        resolvedProjectIdRef.current = "";
        setCurrentProject(null);
        setProjectId("");
        setWorkspaceRestoreState("idle");
        setProjectDrawerNotice(
          "The previously saved project no longer exists. Started a clean unsaved workspace.",
        );
        updateProjectStatus({
          state: "ready",
          area: "projects",
          title: "Clean workspace ready",
          detail: "The stale saved-project reference was cleared from this browser.",
          nextAction: "Start a new project or open another saved project.",
        });
        measureCivoraInteractionAfterPaint("projects.drawer.open_project.missing", loadStartedAt, {
          projectId: id,
        });
        return;
      }
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
  }, [
    activeJob?.project_id,
    activeJobId,
    applyProjectInput,
    autosaveSuspendRef,
    chatAutosaveTimeoutRef,
    controlAutosaveTimeoutRef,
    currentProjectActiveJob?.project_id,
    loadJobRef,
    loadProjectResultInBackgroundRef,
    projectId,
    projectLoadRequestRef,
    resetWorkspaceStateRef,
    resolvedProjectIdRef,
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
  ]);

  useEffect(() => {
    if (!token || effectiveDemoWorkspaceEnabled || restoredActiveProjectRef.current) return;
    if (currentProject?.project_id || projectId) return;
    if (typeof window === "undefined") return;
    const savedProjectId = window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
    if (!savedProjectId) return;
    restoredActiveProjectRef.current = true;
    void loadProject(savedProjectId);
  }, [
    currentProject?.project_id,
    effectiveDemoWorkspaceEnabled,
    loadProject,
    projectId,
    restoredActiveProjectRef,
    token,
  ]);

  return { loadProject };
}
