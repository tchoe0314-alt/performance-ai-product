import type { MutableRefObject } from "react";
import { useCallback, useRef, useState } from "react";

import { getJson, postJson } from "../../lib/api";
import type { ChatMessage, PlanResponse, ProjectInput, ProjectRecord, ProjectIdentity } from "../types";
import { panelErrorMessage } from "../utils/dashboardStatus";
import { ACTIVE_PROJECT_STORAGE_KEY } from "../utils/workflowConstants";
import type { ProjectStatusSummary } from "../utils/workspaceShell";
import { enqueueDashboardProjectSave, type DashboardProjectSaveQueue } from "../utils/dashboardProjectSaveQueue";
import { withCanonicalCanvasSnapshot } from "../utils/canonicalCanvasProject";
import { useProjectTabBranch } from "./useProjectTabBranch";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;

export type DashboardSaveProjectOptions = {
  silent?: boolean;
  projectIdOverride?: string | null;
  nameOverride?: string;
  fileNameOverride?: string;
  projectInputOverride?: ProjectInput;
  identityOverride?: ProjectIdentity;
  latestResultOverride?: PlanResponse;
  autoNamedOverride?: boolean;
  autoFileNamedOverride?: boolean;
};

type UseDashboardProjectSaveOptions = {
  exportDraftHistory?: (input:ProjectInput)=>unknown;
  chatMessagesRef: MutableRefObject<ChatMessage[]>;
  currentProject: ProjectRecord | null;
  effectiveDemoWorkspaceEnabled: boolean;
  fileName: string;
  fileNameAuto: boolean;
  isSeededDemoProjectId: (projectId: string | null) => boolean;
  payloadPreviewRef: MutableRefObject<ProjectInput>;
  projectId: string;
  projectLoadRequestRef: MutableRefObject<number>;
  resolvedProjectIdRef: MutableRefObject<string>;
  setBusy: StateSetter<boolean>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setProjectDrawerNotice: (message: string) => void;
  setProjectId: StateSetter<string>;
  setSiteName: StateSetter<string>;
  setWorkspaceRestoreState: StateSetter<"idle" | "restored" | "failed">;
  setupWizardStateRef: MutableRefObject<unknown>;
  siteName: string;
  siteNameAuto: boolean;
  token: string | null;
  updateProjectStatus: UpdateProjectStatus;
  upsertProjectSummary: (project: ProjectRecord) => void;
};

export function useDashboardProjectSave({
  exportDraftHistory,
  chatMessagesRef,
  currentProject,
  effectiveDemoWorkspaceEnabled,
  fileName,
  fileNameAuto,
  isSeededDemoProjectId,
  payloadPreviewRef,
  projectId,
  projectLoadRequestRef,
  resolvedProjectIdRef,
  setBusy,
  setCurrentProject,
  setProjectDrawerNotice,
  setProjectId,
  setSiteName,
  setWorkspaceRestoreState,
  setupWizardStateRef,
  siteName,
  siteNameAuto,
  token,
  updateProjectStatus,
  upsertProjectSummary,
}: UseDashboardProjectSaveOptions) {
  const saveQueueRef = useRef<DashboardProjectSaveQueue | null>(null);
  const [saveProgress, setSaveProgress] = useState<{generation:number; state:"saving"|"failed"|"idle"}>({generation:-1,state:"idle"});
  const revisionRef = useRef<{ generation: number; projectId: string; revision?: string } | null>(null);
  const forkRef = useRef<{ generation: number; original: string; copy: string } | null>(null);
  const getLiveInput = useCallback(() => payloadPreviewRef.current, [payloadPreviewRef]);
  const tabBranch = useProjectTabBranch(currentProject?.project_id ?? "", getLiveInput, projectLoadRequestRef.current);
  const { hasEdits, beforeSave, choose, markSaved } = tabBranch;
  const saveProject = useCallback(async ({
    silent = false,
    projectIdOverride,
    nameOverride,
    fileNameOverride,
    projectInputOverride,
    identityOverride,
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
    const workspaceGeneration = projectLoadRequestRef.current;
    return enqueueDashboardProjectSave(saveQueueRef, workspaceGeneration, async () => {
      if (projectLoadRequestRef.current !== workspaceGeneration) return null;
      let effectiveProjectId =
        projectIdOverride !== undefined
          ? projectIdOverride
          : resolvedProjectIdRef.current || projectId || currentProject?.project_id || null;
      if (forkRef.current?.generation === workspaceGeneration && effectiveProjectId === forkRef.current.original) {
        effectiveProjectId = forkRef.current.copy;
      }
      // Source imports may supply a new snapshot without changing the live
      // canvas first. Only deduplicate ordinary live-state autosaves.
      if (silent && effectiveProjectId && projectInputOverride === undefined && identityOverride === undefined && latestResultOverride === undefined && !hasEdits(effectiveProjectId)) return currentProject;
      const proposed = identityOverride ? {...payloadPreviewRef.current, manual_fields:{...payloadPreviewRef.current.manual_fields, project_name:nameOverride ?? payloadPreviewRef.current.manual_fields?.project_name}, meta:{...payloadPreviewRef.current.meta, project_identity_v1:identityOverride}} : projectInputOverride;
      const initialChoice = effectiveProjectId ? await beforeSave(effectiveProjectId, silent, proposed) : null;
      if (initialChoice === "cancel" || projectLoadRequestRef.current !== workspaceGeneration) return null;
      const liveInput = payloadPreviewRef.current;
      const resolvedName = (nameOverride ?? liveInput.manual_fields?.project_name ?? siteName).trim();
      const resolvedFileName = (fileNameOverride ?? liveInput.manual_fields?.file_name ?? fileName).trim();
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
      setSaveProgress({generation:workspaceGeneration,state:"saving"});
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
      const projectInputToSave: ProjectInput = projectInputOverride
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
            ...liveInput,
            manual_fields: {
              ...(liveInput.manual_fields ?? {}),
              project_name: resolvedName,
              file_name: resolvedFileName,
            },
            meta: {
              ...(liveInput.meta ?? {}),
              chat_thread: liveChatThread,
              auto_named: autoNamedOverride ?? siteNameAuto,
              auto_file_named: autoFileNamedOverride ?? fileNameAuto,
              setup_wizard_state_v1: setupWizardStateRef.current,
            },
          };
      const latestResultToSave =
        latestResultOverride !== undefined ? latestResultOverride : undefined;
      try {
        if(identityOverride)projectInputToSave.meta={...projectInputToSave.meta,project_identity_v1:identityOverride};
        if(exportDraftHistory)projectInputToSave.meta={...projectInputToSave.meta,edit_history_v1:exportDraftHistory(projectInputToSave)};
        const canonicalInput = withCanonicalCanvasSnapshot(
          projectInputToSave,
          currentProject?.project_id === effectiveProjectId ? currentProject.project_input?.canonical_project_v1 : undefined,
        );
        const requestBody: Record<string, unknown> = {
          project_id: effectiveProjectId,
          name: resolvedName,
          project_input: canonicalInput,
          metadata: {
            auto_named: autoNamedOverride ?? siteNameAuto,
            auto_file_named: autoFileNamedOverride ?? fileNameAuto,
          },
        };
        if (latestResultToSave !== undefined) {
          requestBody.latest_result = latestResultToSave;
        }
        if (!revisionRef.current || revisionRef.current.generation !== workspaceGeneration || revisionRef.current.projectId !== effectiveProjectId) {
          revisionRef.current = { generation: workspaceGeneration, projectId: effectiveProjectId ?? "",
            revision: currentProject?.project_id === effectiveProjectId ? currentProject.revision_token : undefined };
        }
        if (effectiveProjectId && revisionRef.current.revision) requestBody.expected_revision = revisionRef.current.revision;
        const applyChoice = async (choice: "copy" | "replace" | "cancel") => {
          if (choice === "cancel") throw new Error("Edits remain in this tab. Choose how to save them when ready.");
          if (projectLoadRequestRef.current !== workspaceGeneration) throw new Error("Workspace changed. Save was cancelled.");
          if (choice === "copy") {
            requestBody.project_id = null;
            requestBody.name = `${resolvedName || "Untitled Project"} Copy`;
            const copyInput = { ...projectInputToSave, manual_fields: { ...projectInputToSave.manual_fields, project_name: String(requestBody.name) } };
            if(exportDraftHistory)copyInput.meta={...copyInput.meta,edit_history_v1:exportDraftHistory(copyInput)};
            requestBody.project_input = withCanonicalCanvasSnapshot(copyInput, canonicalInput.canonical_project_v1);
            delete requestBody.expected_revision;
            delete requestBody.replace_original;
            requestBody.metadata = { ...(currentProject?.metadata ?? {}), ...(requestBody.metadata as object), duplicated_from_project_id: effectiveProjectId };
            if (latestResultToSave === undefined) {
              if (currentProject?.latest_result && Object.keys(currentProject.latest_result).length) {
                requestBody.latest_result = currentProject.latest_result;
              } else if (currentProject?.has_result) {
                const saved = await getJson<{ latest_result: PlanResponse }>(`/api/projects/${effectiveProjectId}/result`, { token });
                requestBody.latest_result = saved.latest_result;
              }
            }
          } else {
            const latest = await getJson<{ project: ProjectRecord }>(`/api/projects/${effectiveProjectId}`, { token });
            requestBody.expected_revision = latest.project.revision_token;
            requestBody.replace_original = true;
          }
        };
        if (initialChoice) await applyChoice(initialChoice);
        let data: { project: ProjectRecord };
        try {
          data = await postJson<{ project: ProjectRecord }>("/api/projects", requestBody, { token });
        } catch (error) {
          if ((error as { status?: number }).status !== 409 || !effectiveProjectId) throw error;
          const choice = await choose(effectiveProjectId);
          await applyChoice(choice);
          data = await postJson<{ project: ProjectRecord }>("/api/projects", requestBody, { token });
        }
        if (projectLoadRequestRef.current !== workspaceGeneration) {
          return null;
        }
        // Queued canvas saves must read these accepted details immediately,
        // before React publishes the saved project into the payload builder.
        if(identityOverride)payloadPreviewRef.current={...payloadPreviewRef.current,meta:{...payloadPreviewRef.current.meta,project_identity_v1:identityOverride},manual_fields:{...payloadPreviewRef.current.manual_fields,project_name:data.project.name}};
        resolvedProjectIdRef.current = data.project.project_id;
        markSaved(data.project.project_id,requestBody.project_input as ProjectInput,workspaceGeneration);
        revisionRef.current = { generation: workspaceGeneration, projectId: data.project.project_id, revision: data.project.revision_token };
        if (effectiveProjectId && data.project.project_id !== effectiveProjectId) {
          forkRef.current = { generation: workspaceGeneration, original: effectiveProjectId, copy: data.project.project_id };
          // A queued save can run before React publishes the copied name.
          // Update only identity here, preserving newer live geometry edits.
          payloadPreviewRef.current = { ...payloadPreviewRef.current, manual_fields: {
            ...payloadPreviewRef.current.manual_fields, project_name: data.project.name,
          } };
          setSiteName(data.project.name);
        }
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
            project_input: {
              ...payloadPreviewRef.current,
              canonical_project_v1: data.project.project_input?.canonical_project_v1,
            },
            latest_result: data.project.latest_result ?? existing.latest_result,
            has_result: data.project.has_result || existing.has_result,
          };
        });
        // A successful save makes the project reloadable, but it does not mean
        // this browser session restored it. Preserve that stronger claim only
        // when the project was actually loaded from saved state.
        setWorkspaceRestoreState((previous) => previous === "restored" ? "restored" : "idle");
        if (typeof window !== "undefined") {
          window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, data.project.project_id);
          window.sessionStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, data.project.project_id);
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
        setSaveProgress({generation:workspaceGeneration,state:"idle"});
        return data.project;
      } catch (error) {
        if (projectLoadRequestRef.current !== workspaceGeneration) return null;
        setSaveProgress({generation:workspaceGeneration,state:"failed"});
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
        if (projectLoadRequestRef.current === workspaceGeneration) setSaveProgress(previous => previous.state === "saving" ? {generation:workspaceGeneration,state:"idle"} : previous);
        if (!silent && projectLoadRequestRef.current === workspaceGeneration) setBusy(false);
      }
    });
  }, [
    exportDraftHistory,
    hasEdits,
    beforeSave,
    choose,
    markSaved,
    chatMessagesRef,
    currentProject,
    effectiveDemoWorkspaceEnabled,
    fileName,
    fileNameAuto,
    isSeededDemoProjectId,
    payloadPreviewRef,
    projectId,
    projectLoadRequestRef,
    resolvedProjectIdRef,
    setBusy,
    setCurrentProject,
    setProjectDrawerNotice,
    setProjectId,
    setSiteName,
    setWorkspaceRestoreState,
    setupWizardStateRef,
    siteName,
    siteNameAuto,
    token,
    updateProjectStatus,
    upsertProjectSummary,
  ]);

  return { saveProject, tabBranch, saveState:saveProgress.generation===projectLoadRequestRef.current?saveProgress.state:"idle" };
}
