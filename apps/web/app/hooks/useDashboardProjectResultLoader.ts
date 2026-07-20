import { useCallback } from "react";
import type { MutableRefObject } from "react";

import { getJson } from "../../lib/api";
import type { JobSummary, PlanResponse, PreviewResponse, ProjectRecord } from "../types";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type PreviewRequest = {
  project_id: string | null;
  result: PlanResponse;
  filename_stem: string;
};

type UseDashboardProjectResultLoaderOptions = {
  applyBackendResult: (data: PlanResponse) => void;
  backendResult: PlanResponse | null;
  currentProject: ProjectRecord | null;
  fileName: string;
  planPreviewUrl: string;
  projectId: string;
  projectResultLoadRequestRef: MutableRefObject<number>;
  requestPreviewInBackground: (
    request: PreviewRequest,
    options?: {
      loadingMessage?: string;
      silentStatus?: boolean;
      successMessage?: string;
    },
  ) => void;
  resolvedProjectIdRef: MutableRefObject<string>;
  setBackendResult: StateSetter<PlanResponse | null>;
  setPlanPreviewSummary: StateSetter<PreviewResponse["summary"] | null>;
  setPlanPreviewUrl: StateSetter<string>;
  setStatusMessage: (message: string) => void;
  systemStatuses: Record<string, string>;
  token: string | null;
  visibleActiveJob?: JobSummary | null;
};

export function useDashboardProjectResultLoader({
  applyBackendResult,
  backendResult,
  currentProject,
  fileName,
  planPreviewUrl,
  projectId,
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
}: UseDashboardProjectResultLoaderOptions) {
  const loadProjectResultInBackground = useCallback((project: ProjectRecord) => {
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
  }, [
    applyBackendResult,
    backendResult,
    currentProject?.project_id,
    fileName,
    planPreviewUrl,
    projectId,
    projectResultLoadRequestRef,
    requestPreviewInBackground,
    resolvedProjectIdRef,
    setBackendResult,
    setPlanPreviewSummary,
    setPlanPreviewUrl,
    setStatusMessage,
    systemStatuses,
    token,
    visibleActiveJob?.project_id,
    visibleActiveJob?.status,
  ]);

  return { loadProjectResultInBackground };
}
