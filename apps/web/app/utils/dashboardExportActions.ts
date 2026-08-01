import { postJson, toApiUrl } from "../../lib/api";
import type { ChatMessage, JobSummary, PlanMeta, ProjectRecord } from "../types";
import { panelErrorMessage } from "./dashboardStatus";
import type { QuantityReviewRow } from "./workflowConstants";
import type { SidePanelKey, WorkspaceMode } from "./workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

export type DashboardExportActionsConfig = {
  appendChatMessage: AppendChatMessage;
  artifactPayload: Record<string, unknown>;
  backendResultPresent: boolean;
  busy: boolean;
  costEstimate: {
    explain?: {
      cost_estimate_reference?: Record<string, unknown>;
      pricing_coverage_gaps?: Record<string, unknown>;
      quantity_model_reference?: Record<string, unknown>;
      trace_gaps?: Record<string, unknown>;
    };
  };
  currentPlanMeta: PlanMeta;
  currentProject: ProjectRecord | null;
  projectId: string;
  quantityExplain: {
    quantity_model_reference?: Record<string, unknown>;
    trace_gaps?: Record<string, unknown>;
  };
  quantityRows: QuantityReviewRow[];
  setActiveJobId: StateSetter<string>;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setBusy: StateSetter<boolean>;
  setExportActionMessage: StateSetter<string>;
  setStatusMessage: StateSetter<string>;
  siteName: string;
  token: string | null;
  visibleActiveJob: JobSummary | null | undefined;
};

export function createDashboardExportActions(config: DashboardExportActionsConfig) {
  const {
    appendChatMessage,
    artifactPayload,
    backendResultPresent,
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
  } = config;

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

  const downloadArtifactPath = async (downloadPath: string, fallbackFilename: string) => {
    const response = await fetch(toApiUrl(downloadPath), {
      method: "GET",
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const detail =
        typeof payload?.detail === "string"
          ? payload.detail
          : typeof payload?.message === "string"
            ? payload.message
            : `Artifact download failed with status ${response.status}`;
      throw new Error(detail);
    }
    const disposition = response.headers.get("content-disposition");
    const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
    const filename = filenameMatch?.[1] || fallbackFilename;
    downloadBlob(await response.blob(), filename);
  };

  const handleArtifactDownload = async (downloadPath: string, fallbackFilename: string) => {
    try {
      await downloadArtifactPath(downloadPath, fallbackFilename);
      setExportActionMessage("Artifact downloaded. Review-only output; professional review is still required.");
      setStatusMessage("Artifact downloaded. Review-only output; professional review is still required.");
    } catch (error) {
      const message = `Artifact download failed: ${panelErrorMessage(error, "Download the artifact again after the backend is reachable.")}`;
      setExportActionMessage(message);
      setStatusMessage(message);
      setActiveWorkspaceMode("deliver");
      setActiveSidePanel("deliverables");
    }
  };

  const handleExportQuantityReviewReport = () => {
    const safeProjectName = (siteName || currentProject?.name || "civora-project")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 64);
    const report = {
      schema_version: "quantity_takeoff_review_report_v1",
      generated_at: new Date().toISOString(),
      project: {
        project_id: currentProject?.project_id || projectId || "",
        name: siteName || currentProject?.name || "Untitled Project",
      },
      review_only: true,
      engineer_review_required: true,
      quantity_success: currentPlanMeta.quantities?.success ?? false,
      quantity_model_reference: quantityExplain.quantity_model_reference ?? costEstimate.explain?.quantity_model_reference ?? {},
      cost_estimate_reference: costEstimate.explain?.cost_estimate_reference ?? {},
      pricing_coverage_gaps: costEstimate.explain?.pricing_coverage_gaps ?? {},
      trace_gaps: {
        ...(quantityExplain.trace_gaps ?? {}),
        ...(costEstimate.explain?.trace_gaps ?? {}),
      },
      reactive_update: {
        changed_stages: currentPlanMeta.reactive_update_report?.changed_stages ?? [],
        impacted_stages: currentPlanMeta.reactive_update_report?.impacted_stages ?? [],
        partial_rerun_executed: currentPlanMeta.reactive_update_report?.partial_rerun_executed ?? false,
        stale_outputs: currentPlanMeta.reactive_update_report?.stale_outputs ?? [],
      },
      rows: quantityRows.map((row) => ({
        metric: row.metric,
        label: row.label,
        quantity: row.quantity,
        unit: row.unit,
        delta: row.delta,
        previous_quantity: row.previousQuantity,
        current_quantity: row.currentQuantity,
        canonical_ids: row.canonicalIds,
        source_ids: row.sourceIds,
        source_stage: row.sourceStage,
        source_layer: row.sourceLayer,
        method: row.method,
        trace_complete: row.traceComplete,
        cost_item: row.costItem,
        unit_cost: row.unitCost,
        amount: row.amount,
        currency: row.currency,
        price_source: row.priceSource,
        price_source_item_id: row.priceSourceItemId,
        production_price: row.productionPrice,
        missing_cost_mapping: row.missingCost,
        status: row.status,
      })),
      warning:
        "This is a traceable review report only. Independent licensed-professional review is required before field use.",
    };
    downloadBlob(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
      `${safeProjectName || "civora"}-quantity-takeoff-review.json`,
    );
    setStatusMessage("Quantity takeoff review report exported.");
  };

  const getExportBlockReason = () => {
    if (!token) {
      return "authenticate with a backend session before exporting review packages";
    }
    if (busy) {
      return "wait for the current operation to finish";
    }
    if (!backendResultPresent) {
      return projectId
        ? "run systems or load a generated review package before exporting"
        : "run the planner or load a saved project before exporting";
    }
    return "";
  };

  const queueExportJob = async ({
    endpoint,
    failureLabel,
    queuedLabel,
    chatLabel,
    exportScope,
  }: {
    endpoint: string;
    failureLabel: string;
    queuedLabel: string;
    chatLabel: string;
    exportScope?: "review" | "construction";
  }) => {
    const blockReason = getExportBlockReason();
    if (blockReason) {
      setExportActionMessage(`Export needs input: ${blockReason}`);
      setStatusMessage(`Export needs input: ${blockReason}`);
      return;
    }
    if (visibleActiveJob) {
      setExportActionMessage("Export is waiting for the current export or generation job to finish.");
      setStatusMessage("An export or generation job is already running. Wait for it to finish before starting another export.");
      return;
    }
    setBusy(true);
    try {
      const queued = await postJson<{ job: JobSummary }>(
        endpoint,
        exportScope ? { ...artifactPayload, export_scope: exportScope } : artifactPayload,
        { token },
      );
      setActiveJobId(queued.job.job_id);
      setExportActionMessage(`${queuedLabel} queued as ${queued.job.job_id}.`);
      setStatusMessage(`${queuedLabel} queued as ${queued.job.job_id}.`);
      appendChatMessage(
        "assistant",
        `Queued ${chatLabel} as ${queued.job.job_id}. Progress will stay visible here for review tracking.`,
        "status",
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : `${failureLabel} failed.`;
      setExportActionMessage(message);
      setStatusMessage(message);
    } finally {
      setBusy(false);
    }
  };

  const handleExportDxf = () =>
    queueExportJob({
      endpoint: "/api/jobs/export/dxf",
      failureLabel: "DXF export",
      queuedLabel: "DXF review export",
      chatLabel: "DXF review export",
      exportScope: "review",
    });

  const handleExportReport = () =>
    queueExportJob({
      endpoint: "/api/jobs/export/report",
      failureLabel: "Report export",
      queuedLabel: "Engineer-review report",
      chatLabel: "engineer-review report export",
    });

  return {
    downloadBlob,
    downloadArtifactPath,
    getExportBlockReason,
    handleArtifactDownload,
    handleExportDxf,
    handleExportQuantityReviewReport,
    handleExportReport,
  };
}
