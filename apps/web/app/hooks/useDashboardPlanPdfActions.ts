import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import { useCallback } from "react";

import { getJson, patchJson, postForm } from "../../lib/api";
import type {
  CandidateReviewInbox,
  ChatMessage,
  PlanMeta,
  PlanPdfAnalysis,
  PlanPdfChangedElements,
  PlanPdfEditableSheet,
  PlanResponse,
  ProjectRecord,
  UploadPlanPdfResponse,
} from "../types";
import { uploadStatusMessage } from "../utils/dashboardStatus";
import type { WorkspaceMode } from "../utils/workspaceShell";

type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;

type UseDashboardPlanPdfActionsOptions = {
  appendChatMessage: AppendChatMessage;
  currentProject: ProjectRecord | null;
  ensureProjectDraft: () => Promise<string | null>;
  planPdfExtractionSummaryRows: Array<[string, number]>;
  projectId: string;
  resolvedProjectIdRef: MutableRefObject<string>;
  setActiveWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>;
  setBackendResult: Dispatch<SetStateAction<PlanResponse | null>>;
  setCurrentProject: Dispatch<SetStateAction<ProjectRecord | null>>;
  setPlanPdfUploadMessage: Dispatch<SetStateAction<string>>;
  setPlanPdfUploadState: Dispatch<SetStateAction<"idle" | "uploading" | "uploaded" | "failed">>;
  setProjectId: Dispatch<SetStateAction<string>>;
  setStatusMessage: (message: string) => void;
  token: string | null;
};

const escapeReviewHtml = (value: unknown) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

export function useDashboardPlanPdfActions({
  appendChatMessage,
  currentProject,
  ensureProjectDraft,
  planPdfExtractionSummaryRows,
  projectId,
  resolvedProjectIdRef,
  setActiveWorkspaceMode,
  setBackendResult,
  setCurrentProject,
  setPlanPdfUploadMessage,
  setPlanPdfUploadState,
  setProjectId,
  setStatusMessage,
  token,
}: UseDashboardPlanPdfActionsOptions) {
  const activeProjectId = useCallback(
    () => projectId || currentProject?.project_id || "",
    [currentProject?.project_id, projectId],
  );

  const uploadPlanPdf = useCallback(async (file: File) => {
    if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
      const message = "PDF upload failed: Unsupported file. Use a PDF plan file.";
      setPlanPdfUploadState("failed");
      setPlanPdfUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    if (!token) {
      const message = "PDF upload failed: Sign in/connect backend to upload plan PDFs.";
      setPlanPdfUploadState("failed");
      setPlanPdfUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    setPlanPdfUploadState("uploading");
    setPlanPdfUploadMessage("Uploading PDF for review extraction...");
    setStatusMessage("Uploading plan PDF...");
    try {
      const savedProjectId = activeProjectId() || (await ensureProjectDraft());
      if (!savedProjectId) {
        throw new Error("Save or create a project before importing a plan PDF.");
      }
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", savedProjectId);
      const data = await postForm<UploadPlanPdfResponse>("/api/upload-plan-pdf", formData, { token });
      if (data.project) {
        setCurrentProject(data.project);
        setProjectId(data.project.project_id);
        resolvedProjectIdRef.current = data.project.project_id;
        if (data.project.latest_result) {
          setBackendResult(data.project.latest_result);
        }
      } else if (data.plan_pdf_analysis_v1) {
        setBackendResult((current) => ({
          ...(current ?? { success: true }),
          final_plan: {
            ...(current?.final_plan ?? { actions: [] }),
            meta: {
              ...(current?.final_plan?.meta ?? {}),
              plan_pdf_analysis_v1: data.plan_pdf_analysis_v1,
              plan_pdf_editable_sheet_v1: data.plan_pdf_editable_sheet_v1,
              candidate_review_inbox_v1: data.candidate_review_inbox_v1,
            },
          },
        }));
      }
      setPlanPdfUploadState("uploaded");
      setPlanPdfUploadMessage("Plan PDF analyzed. Extracted objects are review-required.");
      setActiveWorkspaceMode("data");
      setStatusMessage("Plan PDF analyzed. All extracted objects are review-required.");
      appendChatMessage(
        "assistant",
        "Plan PDF imported. I extracted review-required sheet candidates where embedded text was available and recorded needs for OCR, raster preview, and vector geometry where unsupported.",
        "status",
      );
    } catch (error) {
      setPlanPdfUploadState("failed");
      const message = uploadStatusMessage("pdf", error);
      setPlanPdfUploadMessage(message);
      setStatusMessage(message);
    }
  }, [
    activeProjectId,
    appendChatMessage,
    ensureProjectDraft,
    resolvedProjectIdRef,
    setActiveWorkspaceMode,
    setBackendResult,
    setCurrentProject,
    setPlanPdfUploadMessage,
    setPlanPdfUploadState,
    setProjectId,
    setStatusMessage,
    token,
  ]);

  const updatePlanPdfElement = useCallback(async (
    elementId: string,
    updates: { text?: string; review_status?: string; move_target?: { x0: number; y0: number } },
  ) => {
    if (!token) return;
    const savedProjectId = activeProjectId();
    if (!savedProjectId) {
      setStatusMessage("Save or load a project before editing PDF-derived sheet elements.");
      return;
    }
    try {
      const data = await patchJson<{
        success?: boolean;
        project?: ProjectRecord;
        plan_pdf_editable_sheet_v1?: PlanMeta["plan_pdf_editable_sheet_v1"];
        plan_pdf_changed_elements_v1?: PlanMeta["plan_pdf_changed_elements_v1"];
        candidate_review_inbox_v1?: CandidateReviewInbox;
      }>(`/api/projects/${savedProjectId}/plan-pdf/elements/${elementId}`, updates, { token });
      if (data.project) {
        setCurrentProject(data.project);
        if (data.project.latest_result) setBackendResult(data.project.latest_result);
      } else if (data.plan_pdf_editable_sheet_v1) {
        setBackendResult((current) => ({
          ...(current ?? { success: true }),
          final_plan: {
            ...(current?.final_plan ?? { actions: [] }),
            meta: {
              ...(current?.final_plan?.meta ?? {}),
              plan_pdf_editable_sheet_v1: data.plan_pdf_editable_sheet_v1,
              plan_pdf_changed_elements_v1: data.plan_pdf_changed_elements_v1,
              candidate_review_inbox_v1: data.candidate_review_inbox_v1,
            },
          },
        }));
      }
      setStatusMessage("PDF-derived sheet element updated. Review is still required.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "PDF element update failed.");
    }
  }, [
    activeProjectId,
    setBackendResult,
    setCurrentProject,
    setStatusMessage,
    token,
  ]);

  const exportPlanPdfReport = useCallback(async () => {
    const savedProjectId = activeProjectId();
    if (!token || !savedProjectId) {
      setStatusMessage("Save or load a project before exporting the PDF extraction report.");
      return;
    }
    try {
      const data = await getJson<{ success?: boolean; report?: Record<string, unknown> }>(
        `/api/projects/${savedProjectId}/plan-pdf/report`,
        { token },
      );
      const blob = new Blob([JSON.stringify(data.report ?? {}, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${savedProjectId}_plan_pdf_extraction_report.json`;
      link.click();
      window.URL.revokeObjectURL(url);
      setStatusMessage("PDF extraction report exported.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "PDF extraction report export failed.");
    }
  }, [activeProjectId, setStatusMessage, token]);

  const exportPlanPdfReviewPdf = useCallback(async () => {
    const savedProjectId = activeProjectId();
    if (!token || !savedProjectId) {
      setStatusMessage("Save or load a project before exporting the PDF review sheet.");
      return;
    }
    try {
      const data = await getJson<{ success?: boolean; report?: Record<string, unknown> }>(
        `/api/projects/${savedProjectId}/plan-pdf/report`,
        { token },
      );
      const report = (data.report ?? {}) as Record<string, unknown>;
      const analysis = (report.analysis ?? {}) as PlanPdfAnalysis;
      const sheet = (report.editable_sheet ?? {}) as PlanPdfEditableSheet;
      const changed = (report.changed_elements ?? {}) as PlanPdfChangedElements;
      const elements = sheet.elements ?? [];
      const changedElements = changed.elements ?? [];
      const blockedCapabilities = Array.isArray(report.blocked_capabilities)
        ? report.blocked_capabilities.map(String)
        : [];
      const popup = window.open("", "_blank", "width=1200,height=900");
      if (!popup) {
        setStatusMessage("Browser blocked the PDF review sheet window.");
        return;
      }
      popup.document.write(`<!doctype html>
<html>
<head>
  <title>${escapeReviewHtml(analysis.source_pdf?.filename || "Plan PDF")} review extraction</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; color: #0f172a; }
    h1, h2, p { margin: 0; }
    h1 { font-size: 22px; }
    h2 { color: #475569; font-size: 12px; letter-spacing: .12em; margin-top: 18px; text-transform: uppercase; }
    p, li, td, th { font-size: 12px; line-height: 1.45; }
    .banner { background: #fffbeb; border: 1px solid #f59e0b; color: #92400e; margin: 12px 0; padding: 10px; }
    .sheet { border: 2px solid #0f172a; min-height: 720px; padding: 24px; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
    .metric { border: 1px solid #cbd5e1; padding: 8px; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th, td { border: 1px solid #cbd5e1; padding: 6px; text-align: left; vertical-align: top; }
    th { background: #f8fafc; }
    @media print { button { display: none; } body { margin: 0.25in; } }
  </style>
</head>
<body>
  <button onclick="window.print()">Print PDF review sheet</button>
  <div class="sheet">
    <h1>${escapeReviewHtml(analysis.source_pdf?.filename || "Plan PDF")} extraction review</h1>
    <p>${escapeReviewHtml(analysis.page_count ?? 0)} page(s) · ${escapeReviewHtml(analysis.source_confidence || "imported_pdf_review_required")} · review required</p>
    <div class="banner">
      PDF-derived labels, dimensions, title blocks, and edits are imported source evidence only. They are not survey-backed, engineer-approved, stamped, sealed, signed, certified, approved for construction, or construction-release evidence.
    </div>
    <div class="grid">
      ${planPdfExtractionSummaryRows
        .map(([label, value]) => `<div class="metric"><p>${escapeReviewHtml(label)}</p><strong>${escapeReviewHtml(value)}</strong></div>`)
        .join("")}
    </div>
    <h2>Editable / Review Candidates</h2>
    <table>
      <thead><tr><th>Type</th><th>Text</th><th>Status</th><th>Source Confidence</th></tr></thead>
      <tbody>${(elements.length ? elements.slice(0, 80) : [])
        .map(
          (element) =>
            `<tr><td>${escapeReviewHtml(element.type || "element")}</td><td>${escapeReviewHtml(element.text || "")}</td><td>${escapeReviewHtml(element.review_status || "pending")}</td><td>${escapeReviewHtml(element.source_confidence || analysis.source_confidence || "imported_pdf_review_required")}</td></tr>`,
        )
        .join("") || `<tr><td colspan="4">No extracted editable candidates were recorded.</td></tr>`}</tbody>
    </table>
    <h2>Changed Elements</h2>
    <table>
      <thead><tr><th>Type</th><th>Original</th><th>Current</th><th>Status</th></tr></thead>
      <tbody>${(changedElements.length ? changedElements.slice(0, 40) : [])
        .map(
          (element) =>
            `<tr><td>${escapeReviewHtml(element.type || "element")}</td><td>${escapeReviewHtml(element.original_text || "")}</td><td>${escapeReviewHtml(element.text || "")}</td><td>${escapeReviewHtml(element.review_status || "pending")}${element.moved ? " / moved" : ""}${element.changed_text ? " / text edited" : ""}</td></tr>`,
        )
        .join("") || `<tr><td colspan="4">No PDF-derived sheet edits have been recorded.</td></tr>`}</tbody>
    </table>
    <h2>Unreadable / OCR / Vector Blockers</h2>
    <ul>${(blockedCapabilities.length ? blockedCapabilities : ["No extraction blockers recorded."])
      .map((item) => `<li>${escapeReviewHtml(item)}</li>`)
      .join("")}</ul>
  </div>
</body>
</html>`);
      popup.document.close();
      setStatusMessage("Opened PDF extraction review sheet.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "PDF review sheet export failed.");
    }
  }, [activeProjectId, planPdfExtractionSummaryRows, setStatusMessage, token]);

  return {
    exportPlanPdfReport,
    exportPlanPdfReviewPdf,
    updatePlanPdfElement,
    uploadPlanPdf,
  };
}
