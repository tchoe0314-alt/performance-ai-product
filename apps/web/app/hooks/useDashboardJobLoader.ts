import { useCallback } from "react";
import type { MutableRefObject } from "react";

import { getJson } from "../../lib/api";
import type { ChatMessage, JobSummary, PlanResponse, ProjectInput, ProjectRecord } from "../types";
import {
  artifactFromJob,
  isArtifactExportJob,
  panelErrorMessage,
} from "../utils/dashboardStatus";
import { summarizePlanResponse, toReadableLabel } from "../utils/formatting";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type ProjectSummary = Pick<ProjectRecord, "project_id" | "name" | "description" | "has_result" | "updated_at">;

type PreviewRequest = {
  project_id: string | null;
  result: PlanResponse;
  filename_stem: string;
};

type UseDashboardJobLoaderOptions = {
  activeJobProjectSyncRef: MutableRefObject<string>;
  appendChatMessage: AppendChatMessage;
  applyBackendResult: (data: PlanResponse) => void;
  applyProjectInput: (projectInput: ProjectInput) => void;
  autosaveSuspendRef: MutableRefObject<boolean>;
  currentProject: ProjectRecord | null;
  fileName: string;
  handleArtifactDownload: (downloadPath: string, filename: string) => Promise<void>;
  lastJobPartialResultRefreshRef: MutableRefObject<Record<string, number>>;
  lastJobPhaseSignatureRef: MutableRefObject<Record<string, string>>;
  lastJobStatusRef: MutableRefObject<Record<string, string>>;
  lastProjectResultRefreshRef: MutableRefObject<Record<string, number>>;
  loadProjectResultInBackground: (project: ProjectRecord) => void;
  projectId: string;
  projectLoadRequestRef: MutableRefObject<number>;
  requestPreviewInBackground: (
    request: PreviewRequest,
    options?: {
      loadingMessage?: string;
      silentStatus?: boolean;
      successMessage?: string;
    },
  ) => void;
  resolvedProjectIdRef: MutableRefObject<string>;
  setActiveJobId: StateSetter<string>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setJobs: StateSetter<JobSummary[]>;
  setJobsPanelStatusMessage: (message: string) => void;
  setSelectedJobId: StateSetter<string>;
  setProjectId: StateSetter<string>;
  setSiteName: StateSetter<string>;
  setStatusMessage: (message: string) => void;
  siteName: string;
  token: string | null;
  upsertProjectSummary: (project: ProjectSummary) => void;
};

export function useDashboardJobLoader({
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
  setSelectedJobId,
  setProjectId,
  setSiteName,
  setStatusMessage,
  siteName,
  token,
  upsertProjectSummary,
}: UseDashboardJobLoaderOptions) {
  const loadJob = useCallback(async (id: string, options?: { selectionOnly?: boolean }) => {
    if (!token) return;
    const workspaceGeneration = projectLoadRequestRef.current;
    try {
      const data = await getJson<{ job: JobSummary }>(`/api/jobs/${id}`, { token });
      if (projectLoadRequestRef.current !== workspaceGeneration) {
        return;
      }
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
      if (options?.selectionOnly) {
        setJobsPanelStatusMessage("");
        return;
      }
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
      if (projectLoadRequestRef.current !== workspaceGeneration) {
        return;
      }
      const message = `Job refresh failed: ${panelErrorMessage(error, "Could not refresh job detail.")}`;
      setJobsPanelStatusMessage(message);
      setStatusMessage(message);
    }
  }, [
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
  ]);

  const handleSelectJob = useCallback((jobId: string) => {
    if (jobId) {
      setSelectedJobId(jobId);
      void loadJob(jobId, { selectionOnly: true });
    }
  }, [loadJob, setSelectedJobId]);

  return {
    handleSelectJob,
    loadJob,
  };
}
