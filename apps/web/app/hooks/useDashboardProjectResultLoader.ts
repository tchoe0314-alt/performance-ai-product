import { useCallback } from "react";
import type { MutableRefObject } from "react";

import { getJson } from "../../lib/api";
import type { JobSummary, PlanResponse, PreviewResponse, ProjectRecord } from "../types";
import { shouldDiscardSavedResultResponse } from "../utils/savedResultHydration";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type PreviewRequest = {
  project_id: string | null;
  result: PlanResponse;
  filename_stem: string;
};

type UseDashboardProjectResultLoaderOptions = {
  applyBackendResult: (data: PlanResponse) => void;
  isLiveResultCurrent: (data: PlanResponse) => Promise<boolean>;
  backendResult: PlanResponse | null;
  currentProject: ProjectRecord | null;
  fileName: string;
  planPreviewUrl: string;
  projectId: string;
  projectLoadRequestRef: MutableRefObject<number>;
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
  setSavedResultTruthState: (state: "missing" | "failed" | "historical" | "unverified" | "stale" | "current") => void;
  setPlanPreviewSummary: StateSetter<PreviewResponse["summary"] | null>;
  setPlanPreviewUrl: StateSetter<string>;
  setStatusMessage: (message: string) => void;
  systemStatuses: Record<string, string>;
  token: string | null;
  visibleActiveJob?: JobSummary | null;
};

export function useDashboardProjectResultLoader({
  applyBackendResult,
  isLiveResultCurrent,
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
  setSavedResultTruthState,
  setPlanPreviewSummary,
  setPlanPreviewUrl,
  setStatusMessage,
  systemStatuses,
  token,
  visibleActiveJob,
}: UseDashboardProjectResultLoaderOptions) {
  const loadProjectResultInBackground = useCallback((project: ProjectRecord) => {
    if (!token) return;
    const workspaceGeneration = projectLoadRequestRef.current;
    const requestId = projectResultLoadRequestRef.current + 1;
    projectResultLoadRequestRef.current = requestId;
    const shouldDiscardResponse = () => shouldDiscardSavedResultResponse({
      requestId,
      latestRequestId: projectResultLoadRequestRef.current,
      workspaceGeneration,
      latestWorkspaceGeneration: projectLoadRequestRef.current,
      requestedProjectId: project.project_id,
      activeProjectId: resolvedProjectIdRef.current || projectId || currentProject?.project_id || "",
    });
    void getJson<{ project_id: string; latest_result: PlanResponse; result_freshness_v1?: { status: string } | null }>(
      `/api/projects/${project.project_id}/result`,
      { token },
    )
      .then(async (data) => {
        if (shouldDiscardResponse()) return;
        const latestResult = data.latest_result ?? {};
        if (latestResult && Object.keys(latestResult).length) {
          const disposition = String(latestResult.metadata?.calculation_save_v1?.disposition ?? "").toLowerCase();
          setSavedResultTruthState(latestResult.success === false ? "failed" : disposition === "archived" ? "historical" : data.result_freshness_v1?.status === "current" ? "current" : "unverified");
          const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
          const hasStaleSystems = Object.values(systemStatuses).some(
            (status) => status === "stale",
          );
          const shouldSuppressLatestResult =
            hasStaleSystems &&
            data.result_freshness_v1?.status !== "current" &&
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
          // Hydrate a server-authorized result before the asynchronous local
          // fingerprint check. Large saved plans can otherwise finish that
          // check after workspace restoration advances its generation, leaving
          // a valid result labelled "missing". The local check may only
          // downgrade this hydrated result to stale; it never promotes one.
          const liveCurrent = await isLiveResultCurrent(latestResult);
          if (shouldDiscardResponse()) return;
          if (!liveCurrent || data.result_freshness_v1?.status === "stale") {
            setSavedResultTruthState("stale");
            setStatusMessage("Saved results are out of date. Recalculate for this layout.");
          }
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
          // The result endpoint may withhold latest_result after a canonical
          // edit even though this workspace still holds the prior saved
          // calculation. Keep that prior output visible as stale history;
          // clearing it would incorrectly turn "recalculate" into "missing".
          if (backendResult && Object.keys(backendResult).length) {
            setSavedResultTruthState("stale");
            setStatusMessage("Saved results are out of date. Recalculate for this layout.");
            return;
          }
          setSavedResultTruthState(
            data.result_freshness_v1?.status === "stale"
              ? "stale"
              : data.result_freshness_v1?.status === "failed"
                ? "failed"
                : "missing",
          );
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
        if (shouldDiscardResponse()) return;
        setSavedResultTruthState("failed");
        setStatusMessage(
          error instanceof Error ? error.message : "Project result load failed.",
        );
      });
  }, [
    applyBackendResult,
    isLiveResultCurrent,
    backendResult,
    currentProject?.project_id,
    fileName,
    planPreviewUrl,
    projectId,
    projectLoadRequestRef,
    projectResultLoadRequestRef,
    requestPreviewInBackground,
    resolvedProjectIdRef,
    setBackendResult,
    setSavedResultTruthState,
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
