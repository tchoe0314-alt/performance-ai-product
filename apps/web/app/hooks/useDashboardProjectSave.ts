import type { MutableRefObject } from "react";
import { useCallback } from "react";

import { postJson } from "../../lib/api";
import type { ChatMessage, PlanResponse, ProjectInput, ProjectRecord } from "../types";
import { panelErrorMessage } from "../utils/dashboardStatus";
import { ACTIVE_PROJECT_STORAGE_KEY } from "../utils/workflowConstants";
import type { ProjectStatusSummary } from "../utils/workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;

export type DashboardSaveProjectOptions = {
  silent?: boolean;
  projectIdOverride?: string | null;
  nameOverride?: string;
  fileNameOverride?: string;
  projectInputOverride?: ProjectInput;
  latestResultOverride?: PlanResponse;
  autoNamedOverride?: boolean;
  autoFileNamedOverride?: boolean;
};

type UseDashboardProjectSaveOptions = {
  chatMessagesRef: MutableRefObject<ChatMessage[]>;
  currentProject: ProjectRecord | null;
  effectiveDemoWorkspaceEnabled: boolean;
  fileName: string;
  fileNameAuto: boolean;
  isSeededDemoProjectId: (projectId: string | null) => boolean;
  payloadPreview: ProjectInput;
  payloadPreviewRef: MutableRefObject<ProjectInput>;
  projectId: string;
  projectLoadRequestRef: MutableRefObject<number>;
  resolvedProjectIdRef: MutableRefObject<string>;
  setBusy: StateSetter<boolean>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setProjectDrawerNotice: (message: string) => void;
  setProjectId: StateSetter<string>;
  setWorkspaceRestoreState: StateSetter<"idle" | "restored" | "failed">;
  setupWizardStateRef: MutableRefObject<unknown>;
  siteName: string;
  siteNameAuto: boolean;
  token: string | null;
  updateProjectStatus: UpdateProjectStatus;
  upsertProjectSummary: (project: ProjectRecord) => void;
};

export function useDashboardProjectSave({
  chatMessagesRef,
  currentProject,
  effectiveDemoWorkspaceEnabled,
  fileName,
  fileNameAuto,
  isSeededDemoProjectId,
  payloadPreview,
  payloadPreviewRef,
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
}: UseDashboardProjectSaveOptions) {
  const saveProject = useCallback(async ({
    silent = false,
    projectIdOverride,
    nameOverride,
    fileNameOverride,
    projectInputOverride,
    latestResultOverride,
    autoNamedOverride,
    autoFileNamedOverride,
  }: DashboardSaveProjectOptions = {}): Promise<ProjectRecord | null> => {
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
            setup_wizard_state_v1: setupWizardStateRef.current,
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
            setup_wizard_state_v1: setupWizardStateRef.current,
          },
        };
    const latestResultToSave =
      latestResultOverride !== undefined ? latestResultOverride : undefined;
    const workspaceGeneration = projectLoadRequestRef.current;
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
      if (projectLoadRequestRef.current !== workspaceGeneration) {
        return null;
      }
      resolvedProjectIdRef.current = data.project.project_id;
      setProjectId(data.project.project_id);
      setCurrentProject((existing) => {
        if (!silent || !existing || existing.project_id !== data.project.project_id) {
          return data.project;
        }
        return {
          ...data.project,
          // Silent object autosaves may finish after another canvas edit. Keep
          // the live workspace input so an older response cannot remove or
          // reselect newer draft geometry while the queued save catches up.
          project_input: payloadPreviewRef.current,
          latest_result: data.project.latest_result ?? existing.latest_result,
          has_result: data.project.has_result || existing.has_result,
        };
      });
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
  }, [
    chatMessagesRef,
    currentProject,
    effectiveDemoWorkspaceEnabled,
    fileName,
    fileNameAuto,
    isSeededDemoProjectId,
    payloadPreview,
    payloadPreviewRef,
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
  ]);

  return { saveProject };
}
