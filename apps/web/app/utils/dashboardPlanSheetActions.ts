import type {
  PlanSheet,
  PlanSheetAnnotation,
  PlanSheetReference,
  PlanSheetScale,
  PlanSheetSet,
  PlanSheetTitleBlock,
  PlanSheetViewport,
} from "../components/PlanSheetEditor";
import type { ChatMessage, PlanResponse, ProjectRecord } from "../types";
import type { AutoSiteContextFlowSummary, ReviewPackageFlowSummary } from "./dashboardDataTypes";
import type { RecentChange } from "./dashboardTypes";
import { toReadableLabel } from "./formatting";
import { createDefaultPlanSheet } from "./planSheetDefaults";
import { uniqueStrings } from "./workflowConstants";
import type { ProjectStatusSummary, SidePanelKey, WorkspaceMode } from "./workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type DownloadBlob = (blob: Blob, filename: string) => void;
type AppendChatMessage = (
  role: ChatMessage["role"],
  content: string,
  kind?: ChatMessage["kind"],
  feedback?: ChatMessage["feedback"],
) => void;

export type DashboardPlanSheetActionsConfig = {
  analysisIssues: unknown[];
  appendChatMessage: AppendChatMessage;
  autoSiteContextFlowSummary: AutoSiteContextFlowSummary;
  backendResult: PlanResponse | null;
  currentProject: ProjectRecord | null;
  downloadBlob: DownloadBlob;
  issues: unknown[];
  persistFlowMetadata: (metadata: Record<string, unknown>) => Promise<void> | void;
  planPreviewUrl: string;
  planSheetSet: PlanSheetSet;
  previewBlockedReasons: string[];
  recordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  reviewPackageFlowSummary: ReviewPackageFlowSummary | null;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setPlanSheetSet: StateSetter<PlanSheetSet>;
  setReviewPackageFlowSummary: StateSetter<ReviewPackageFlowSummary | null>;
  setStatusMessage: (message: string) => void;
  siteName: string;
  updateProjectStatus: (summary: Omit<ProjectStatusSummary, "updatedAt">) => void;
};

function clampSheetPercent(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, Number.isFinite(value) ? value : min));
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function createDashboardPlanSheetActions(config: DashboardPlanSheetActionsConfig) {
  const {
    analysisIssues,
    appendChatMessage,
    autoSiteContextFlowSummary,
    backendResult,
    currentProject,
    downloadBlob,
    issues,
    persistFlowMetadata,
    planPreviewUrl,
    planSheetSet,
    previewBlockedReasons,
    recordRecentChange,
    reviewPackageFlowSummary,
    setActiveSidePanel,
    setActiveWorkspaceMode,
    setPlanSheetSet,
    setReviewPackageFlowSummary,
    setStatusMessage,
    siteName,
    updateProjectStatus,
  } = config;

  const getPlanSheetBlockers = (sheetSetOverride = planSheetSet) => {
    const activeSheet =
      sheetSetOverride.sheets.find((sheet) => sheet.id === sheetSetOverride.activeSheetId) ??
      sheetSetOverride.sheets[0];
    const blockers = new Set<string>(sheetSetOverride.blockers);
    if (!activeSheet) {
      blockers.add("Add at least one review sheet.");
      return Array.from(blockers);
    }
    if (!activeSheet.titleBlock.projectName.trim()) blockers.add("Fill in the project name.");
    if (!activeSheet.titleBlock.sheetTitle.trim()) blockers.add("Fill in the sheet title.");
    if (!activeSheet.titleBlock.sheetNumber.trim()) blockers.add("Fill in the sheet number.");
    if (!activeSheet.viewports.length) blockers.add("Add at least one viewport.");
    if (activeSheet.viewports.some((viewport) => !viewport.scaleLocked)) blockers.add("Lock viewport scales before plotting.");
    if (!planSheetSet.sheetIndex.length) blockers.add("Build the sheet index/table of contents.");
    if (!planSheetSet.revisions.length) blockers.add("Add a revision/review history entry.");
    if (!planPreviewUrl && !backendResult) blockers.add("Link a generated model preview or source package.");
    if (issues.length || analysisIssues.length) blockers.add("Resolve or acknowledge current model review issues.");
    if (previewBlockedReasons.length) blockers.add(previewBlockedReasons[0]);
    return Array.from(blockers).filter(Boolean);
  };

  const refreshPlanSheet = (updater: (sheet: PlanSheet) => PlanSheet) => {
    setPlanSheetSet((current) => ({
      ...current,
      sheets: current.sheets.map((sheet) =>
        sheet.id === current.activeSheetId ? updater(sheet) : sheet,
      ),
      updatedAt: new Date().toISOString(),
    }));
  };

  const handlePlanSheetTitleBlockUpdate = (updates: Partial<PlanSheetTitleBlock>) => {
    setPlanSheetSet((current) => {
      const sheets = current.sheets.map((sheet) =>
        sheet.id === current.activeSheetId ? { ...sheet, titleBlock: { ...sheet.titleBlock, ...updates } } : sheet,
      );
      return {
        ...current,
        sheets,
        sheetIndex: sheets.map((sheet) => ({
          sheetNumber: sheet.titleBlock.sheetNumber,
          title: sheet.titleBlock.sheetTitle,
        })),
        updatedAt: new Date().toISOString(),
      };
    });
    setStatusMessage("Updated sheet title block fields.");
  };

  const handlePlanSheetScaleChange = (viewportId: string, scale: PlanSheetScale) => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      viewports: sheet.viewports.map((viewport) =>
        viewport.id === viewportId ? { ...viewport, scale, scaleLocked: true } : viewport,
      ),
    }));
    setStatusMessage(`Changed sheet viewport scale to ${scale}.`);
  };

  const handlePlanSheetViewportLayerToggle = (viewportId: string, layer: string) => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      viewports: sheet.viewports.map((viewport) =>
        viewport.id === viewportId
          ? {
              ...viewport,
              layerVisibility: {
                ...viewport.layerVisibility,
                [layer]: !viewport.layerVisibility[layer],
              },
            }
          : viewport,
      ),
    }));
    setStatusMessage(`Updated ${layer} viewport visibility.`);
  };

  const handlePlanSheetViewportScaleLockToggle = (viewportId: string) => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      viewports: sheet.viewports.map((viewport) =>
        viewport.id === viewportId ? { ...viewport, scaleLocked: !viewport.scaleLocked } : viewport,
      ),
    }));
    setStatusMessage("Updated viewport scale lock.");
  };

  const handlePlanSheetGrayscaleToggle = () => {
    setPlanSheetSet((current) => ({
      ...current,
      plotStyles: {
        ...current.plotStyles,
        grayscale: !current.plotStyles.grayscale,
      },
      updatedAt: new Date().toISOString(),
    }));
    setStatusMessage("Updated review plot grayscale option.");
  };

  const handlePlanSheetAddRevision = (note = "Review revision note added; verify before package handoff.") => {
    setPlanSheetSet((current) => ({
      ...current,
      revisions: [
        ...current.revisions,
        {
          id: `revision-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          revision: `REV-${current.revisions.length + 1}`,
          note,
          date: new Date().toISOString().slice(0, 10),
          reviewer: "Reviewer",
        },
      ],
      updatedAt: new Date().toISOString(),
    }));
    setStatusMessage("Added review revision history note.");
  };

  const handlePlanSheetViewportUpdate = (viewportId: string, updates: Partial<PlanSheetViewport>) => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      viewports: sheet.viewports.map((viewport) => {
        if (viewport.id !== viewportId) return viewport;
        const next = { ...viewport, ...updates };
        return {
          ...next,
          label: String(next.label ?? "").trim() ? next.label : viewport.label,
          source: String(next.source ?? "").trim() ? next.source : viewport.source,
          target: String(next.target ?? "").trim() ? next.target : (viewport.target || "Review viewport target"),
          x: clampSheetPercent(next.x, 0, 85),
          y: clampSheetPercent(next.y, 0, 85),
          w: clampSheetPercent(next.w, 10, 90),
          h: clampSheetPercent(next.h, 10, 90),
        };
      }),
    }));
    setStatusMessage("Updated active sheet viewport.");
  };

  const handlePlanSheetViewportDelete = (viewportId: string) => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      viewports: sheet.viewports.filter((viewport) => viewport.id !== viewportId),
    }));
    setStatusMessage("Deleted a sheet viewport. Blockers will stay visible until a viewport is added.");
  };

  const addPlanSheetAnnotation = (type: PlanSheetAnnotation["type"], text: string) => {
    refreshPlanSheet((sheet) => {
      const offset = sheet.annotations.length % 5;
      return {
        ...sheet,
        annotations: [
          ...sheet.annotations,
          {
            id: `annotation-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            type,
            text,
            x: 12 + offset * 8,
            y: 24 + offset * 9,
          },
        ],
      };
    });
  };

  const handlePlanSheetAddNote = (text = "Review note: confirm source before package handoff.") => {
    addPlanSheetAnnotation("note", text);
    setStatusMessage("Added a review note to the active sheet.");
  };

  const handlePlanSheetAddViewport = () => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      viewports: [
        ...sheet.viewports,
        {
          id: `viewport-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          label: `Viewport ${sheet.viewports.length + 1}`,
          source: "Model layer selection",
          target: sheet.viewports.length % 2 === 0 ? "Enlarged site review area" : "Utility or grading review area",
          scale: "1:50",
          scaleLocked: true,
          layerVisibility: {
            "C-ANNO": true,
            "C-ROAD": true,
            "C-PIPE-STORM": true,
            "C-UTIL": true,
            "X-REFERENCE": sheet.viewports.length % 2 === 0,
          },
          northArrow: true,
          scaleBar: true,
          x: 12 + (sheet.viewports.length % 2) * 32,
          y: 18 + (sheet.viewports.length % 3) * 16,
          w: 30,
          h: 24,
        },
      ],
    }));
    setStatusMessage("Added a sheet viewport.");
  };

  const handlePlanSheetAddTable = () => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      legends: [
        ...sheet.legends,
        {
          id: `legend-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          title: `Legend ${sheet.legends.length + 1}`,
          rows: [["Linework", "Review layer"], ["Labels", "Visible callouts"]],
        },
      ],
    }));
    setStatusMessage("Added a legend/table block.");
  };

  const handlePlanSheetAddDetailBlock = () => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      detailBlocks: [
        ...sheet.detailBlocks,
        {
          id: `detail-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          title: `Detail ${sheet.detailBlocks.length + 1}`,
          rows: [["Reference", "Detail block pending source"], ["Status", "For review"]],
        },
      ],
    }));
    setStatusMessage("Added a detail block.");
  };

  const handlePlanSheetAddReference = (kind: PlanSheetReference["kind"]) => {
    refreshPlanSheet((sheet) => ({
      ...sheet,
      references: [
        ...sheet.references,
        {
          id: `${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          kind,
          label: `${toReadableLabel(kind)} reference`,
          target: `${toReadableLabel(kind)} pending source`,
        },
      ],
    }));
    setStatusMessage(`Added ${toReadableLabel(kind).toLowerCase()} reference.`);
  };

  const handleCreateReviewSheet = () => {
    setPlanSheetSet((current) => {
      const projectName = siteName || currentProject?.name || "Untitled Project";
      const nextSheet = createDefaultPlanSheet(current.sheets.length, projectName);
      const sheets = [...current.sheets, nextSheet];
      return {
        ...current,
        name: `${projectName} Review Sheet Package`,
        sheets,
        activeSheetId: nextSheet.id,
        sheetIndex: sheets.map((sheet) => ({
          sheetNumber: sheet.titleBlock.sheetNumber,
          title: sheet.titleBlock.sheetTitle,
        })),
        updatedAt: new Date().toISOString(),
      };
    });
    setActiveWorkspaceMode("deliver");
    setActiveSidePanel("deliverables");
    appendChatMessage("assistant", "Made a new review sheet and opened the sheet editor.", "status");
    setStatusMessage("New review sheet added.");
  };

  const handleMakeReviewPackage = () => {
    updateProjectStatus({
      state: "working",
      area: "deliver",
      title: "Creating review package",
      detail: "Civora is assembling available review deliverables and missing-item notes.",
      nextAction: "Wait for the package summary to show created items or exact needs.",
    });
    const blockers = getPlanSheetBlockers();
    const missing = uniqueStrings([
      ...blockers,
      !backendResult ? "generated system result is missing" : "",
      !planPreviewUrl ? "model preview is missing" : "",
      ...autoSiteContextFlowSummary.missingLabels.map((item) => `Auto Site Context source missing: ${item}`),
    ]);
    const outputsCreated = uniqueStrings([
      "review sheet package",
      planSheetSet.sheets.length ? "sheet index" : "",
      planPreviewUrl ? "model preview reference" : "",
      backendResult ? "generated result summary" : "",
      autoSiteContextFlowSummary.candidateCount > 0 ? "Auto Site Context source/missing summary" : "",
    ]);
    const summary: ReviewPackageFlowSummary = {
      version: "review_package_flow_summary_v1",
      generated_at: new Date().toISOString(),
      outputs_created: outputsCreated.length ? outputsCreated : ["review package shell"],
      missing,
      blocked: !outputsCreated.length || (!backendResult && !planPreviewUrl && !planSheetSet.sheets.length),
      next_action: missing.length
        ? `Review missing package inputs: ${missing.slice(0, 3).join("; ")}.`
        : "Export the review-only package or send it for qualified review.",
      auto_site_context: autoSiteContextFlowSummary,
      review_only: true,
      engineer_review_required: true,
      safety_wording:
        "Review package output is review-only and engineer-review-required. Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.",
    };
    setReviewPackageFlowSummary(summary);
    recordRecentChange({
      type: "review_package_recorded",
      label: summary.blocked ? "Review package needs input" : "Review package created",
      detail: summary.blocked
        ? `Review package needs input: ${summary.next_action}`
        : `Review package created: ${summary.outputs_created.join(", ")}.`,
      undoBlockedReason: "Review package history is a review record. Revise drafts and make the package again if needed.",
    });
    void persistFlowMetadata({ review_package_flow_summary_v1: summary });
    setPlanSheetSet((current) => {
      const projectName = siteName || currentProject?.name || "Untitled Project";
      const sheets = current.sheets.length ? current.sheets : [createDefaultPlanSheet(0, projectName)];
      const activeSheetId = current.activeSheetId || sheets[0]?.id || "";
      const activeSheet = sheets.find((sheet) => sheet.id === activeSheetId) ?? sheets[0];
      const sourceNote = autoSiteContextFlowSummary.candidateCount
        ? `Auto Site Context: ${autoSiteContextFlowSummary.candidateCount} review-required source candidate(s). Missing: ${autoSiteContextFlowSummary.missingLabels.join(", ") || "source evidence not available yet"}.`
        : `Auto Site Context: no accepted source candidates. Missing: ${autoSiteContextFlowSummary.missingLabels.join(", ") || "source evidence not available yet"}.`;
      const existingSourceNote = activeSheet?.annotations.some((item) => item.text.startsWith("Auto Site Context:"));
      const nextSheets = sheets.map((sheet) =>
        sheet.id === activeSheet?.id && !existingSourceNote
          ? {
              ...sheet,
              annotations: [
                ...sheet.annotations,
                {
                  id: `auto-site-context-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                  type: "note" as const,
                  text: sourceNote,
                  x: 10,
                  y: 18,
                },
              ],
              detailBlocks: [
                ...sheet.detailBlocks,
                {
                  id: `review-package-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                  title: "Review Package Source Summary",
                  rows: [
                    ["Review candidates", String(autoSiteContextFlowSummary.candidateCount)],
                    ["Missing sources", autoSiteContextFlowSummary.missingLabels.join(", ") || "Source evidence not available yet"],
                    ["Package status", summary.blocked ? "Needs package inputs" : "Review package created"],
                  ] as Array<[string, string]>,
                },
              ],
            }
          : sheet,
      );
      return {
        ...current,
        name: `${projectName} Review Package`,
        status: "review",
        mode: "sheet_layout",
        sheets: nextSheets,
        activeSheetId: activeSheet?.id || activeSheetId,
        sheetIndex: nextSheets.map((sheet) => ({
          sheetNumber: sheet.titleBlock.sheetNumber,
          title: sheet.titleBlock.sheetTitle,
        })),
        revisions: current.revisions.length
          ? current.revisions
          : [
              {
                id: `revision-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                revision: "REV-1",
                note: "Review package assembled from available outputs; missing inputs remain listed for reviewer action.",
                date: new Date().toISOString().slice(0, 10),
                reviewer: "Reviewer",
              },
            ],
        blockers: missing,
        updatedAt: summary.generated_at,
      };
    });
    appendChatMessage(
      "assistant",
      [
        `Made a review-only package from what exists: ${summary.outputs_created.join(", ")}.`,
        summary.missing.length ? `Missing: ${summary.missing.slice(0, 5).join("; ")}.` : "Missing: none currently recorded.",
        "Engineer review is required; Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.",
      ].join(" "),
      "status",
    );
    updateProjectStatus({
      state: summary.blocked ? "blocked" : "needs review",
      area: "deliver",
      title: summary.blocked ? "Review package needs input" : "Review package needs review",
      detail: summary.blocked
        ? `Missing package inputs: ${summary.missing.slice(0, 3).join("; ") || "no usable output created"}.`
        : "Review package created from available outputs.",
      nextAction: summary.next_action,
    });
  };

  const handlePlanSheetExportJson = () => {
    const projectName = siteName || currentProject?.name || "civora-project";
    const safeProjectName = projectName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 64);
    const payload = {
      schema_version: "plan_sheet_set_review_v1",
      generated_at: new Date().toISOString(),
      review_only: true,
      engineer_review_required: true,
      not_for_construction: true,
      civora_limitations: [
        "Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.",
        "Review sheets are review-only plan-production aids and are not approved construction documents.",
      ],
      review_package_summary: reviewPackageFlowSummary,
      auto_site_context_summary: autoSiteContextFlowSummary,
      sheet_set: {
        ...planSheetSet,
        mode: "sheet_layout",
        blockers: getPlanSheetBlockers(),
        sheetIndex: planSheetSet.sheets.map((sheet) => ({
          sheetNumber: sheet.titleBlock.sheetNumber,
          title: sheet.titleBlock.sheetTitle,
        })),
        model_space: {
          purpose: "Source civil geometry and annotations in model coordinates.",
          review_required: true,
        },
        sheet_layout: {
          purpose: "Paper/layout composition with locked viewports into model space.",
          review_required: true,
        },
        sheets: planSheetSet.sheets.map((sheet) => ({
          ...sheet,
          viewports: sheet.viewports.map((viewport) => ({
            ...viewport,
            target: viewport.target || "Review viewport target",
            scale_locked: viewport.scaleLocked,
            layer_visibility: viewport.layerVisibility,
            north_arrow: viewport.northArrow,
            scale_bar: viewport.scaleBar,
          })),
        })),
      },
    };
    downloadBlob(
      new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
      `${safeProjectName || "civora"}-review-sheets.json`,
    );
    setStatusMessage("Review sheet JSON exported.");
  };

  const handlePlanSheetExportPdf = () => {
    const blockers = getPlanSheetBlockers();
    const activeSheet =
      planSheetSet.sheets.find((sheet) => sheet.id === planSheetSet.activeSheetId) ??
      planSheetSet.sheets[0];
    if (!activeSheet) {
      setStatusMessage("Add a review sheet before exporting PDF.");
      return;
    }
    const popup = window.open("", "_blank", "noopener,noreferrer,width=1200,height=900");
    if (!popup) {
      setStatusMessage("Browser blocked the review PDF window.");
      return;
    }
    popup.document.write(`<!doctype html>
<html>
<head>
  <title>${escapeHtml(activeSheet.titleBlock.sheetNumber)} review sheet</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; color: #0f172a; }
    .sheet { border: 2px solid #0f172a; min-height: 720px; padding: 24px; position: relative; }
    .title { border-top: 2px solid #0f172a; margin-top: 24px; padding-top: 12px; display: grid; grid-template-columns: 1fr 140px; gap: 12px; }
    .notice { border: 1px solid #f59e0b; background: #fffbeb; color: #92400e; padding: 10px; margin: 12px 0; font-weight: 700; }
    .viewport { border: 2px solid #334155; background: #f8fafc; padding: 12px; margin: 12px 0; min-height: 180px; position: relative; }
    .watermark { position: absolute; inset: 45% 8%; transform: rotate(-18deg); color: rgba(180,83,9,.16); font-size: 48px; font-weight: 900; text-align: center; pointer-events: none; }
    .north { position: absolute; right: 16px; top: 16px; border: 1px solid #334155; border-radius: 999px; width: 42px; height: 42px; display: grid; place-items: center; font-weight: 800; }
    .scale { position: absolute; left: 16px; bottom: 16px; font-weight: 700; }
    .bar { width: 120px; height: 10px; border-left: 2px solid #0f172a; border-right: 2px solid #0f172a; border-bottom: 2px solid #0f172a; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    h1, h2, p { margin: 0; }
    h1 { font-size: 22px; }
    h2 { font-size: 13px; letter-spacing: .12em; text-transform: uppercase; color: #64748b; margin-top: 18px; }
    p, li { font-size: 12px; line-height: 1.5; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    td { border: 1px solid #cbd5e1; padding: 6px; font-size: 12px; }
    @media print { button { display: none; } body { margin: 0.25in; } }
  </style>
</head>
<body>
  <button onclick="window.print()">Print review PDF</button>
  <div class="sheet">
    <div class="watermark">${escapeHtml(planSheetSet.plotStyles.reviewWatermark)}</div>
    <h1>${escapeHtml(activeSheet.titleBlock.sheetTitle)}</h1>
    <p>${escapeHtml(planSheetSet.name)} · ${escapeHtml(activeSheet.size)} · Review package only</p>
    <div class="notice">Review-required plan-production aid only. Not an approved construction document. Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.</div>
    <h2>Viewports</h2>
    ${activeSheet.viewports
      .map(
        (viewport) =>
          `<div class="viewport"><strong>${escapeHtml(viewport.label)}</strong><p>${escapeHtml(viewport.source)}</p><p>Target: ${escapeHtml(viewport.target || "Review viewport target")}</p><p>Scale ${escapeHtml(viewport.scale)} · ${viewport.scaleLocked ? "Locked scale" : "Scale editable"} · Position ${Math.round(viewport.x)}%, ${Math.round(viewport.y)}% · Size ${Math.round(viewport.w)}% x ${Math.round(viewport.h)}%</p><p>Visible layers: ${escapeHtml(Object.entries(viewport.layerVisibility).filter(([, visible]) => visible).map(([layer]) => layer).join(", ") || "none")}</p><div class="north">N</div><div class="scale"><div class="bar"></div><p>Scale ${escapeHtml(viewport.scale)}</p></div></div>`,
      )
      .join("")}
    <h2>Sheet Index</h2>
    <table>${planSheetSet.sheetIndex.map((item) => `<tr><td>${escapeHtml(item.sheetNumber)}</td><td>${escapeHtml(item.title)}</td></tr>`).join("")}</table>
    <h2>Auto Site Context</h2>
    <table>
      <tr><td>Review candidates</td><td>${autoSiteContextFlowSummary.candidateCount}</td></tr>
      <tr><td>Candidate sources</td><td>${escapeHtml(autoSiteContextFlowSummary.candidateLabels.join(", ") || "None recorded")}</td></tr>
      <tr><td>Missing sources</td><td>${escapeHtml(autoSiteContextFlowSummary.missingLabels.join(", ") || "Source evidence not available yet")}</td></tr>
      <tr><td>Status</td><td>${escapeHtml(autoSiteContextFlowSummary.status)}</td></tr>
    </table>
    <h2>Plot Styles</h2>
    <table>${planSheetSet.plotStyles.mappings
      .map((item) => `<tr><td>${escapeHtml(item.layer)}</td><td>${escapeHtml(item.color)}</td><td>${escapeHtml(item.lineweight)}</td><td>${escapeHtml(item.linetype)}</td></tr>`)
      .join("")}<tr><td>Grayscale</td><td colspan="3">${planSheetSet.plotStyles.grayscale ? "Enabled" : "Optional"}</td></tr></table>
    <h2>Revision History</h2>
    <ul>${planSheetSet.revisions.map((item) => `<li>${escapeHtml(item.revision)} ${escapeHtml(item.date)}: ${escapeHtml(item.note)} (${escapeHtml(item.reviewer)})</li>`).join("")}</ul>
    <div class="grid">
      <div>
        <h2>Notes and Callouts</h2>
        <ul>${activeSheet.annotations.map((item) => `<li>${escapeHtml(item.type)}: ${escapeHtml(item.text)}</li>`).join("")}</ul>
      </div>
      <div>
        <h2>References</h2>
        <ul>${activeSheet.references.map((item) => `<li>${escapeHtml(item.kind)}: ${escapeHtml(item.target)}</li>`).join("")}</ul>
      </div>
    </div>
    <h2>Legends and Details</h2>
    ${[...activeSheet.legends, ...activeSheet.detailBlocks]
      .map(
        (table) =>
          `<table><caption>${escapeHtml(table.title)}</caption>${table.rows
            .map(([label, value]) => `<tr><td>${escapeHtml(label)}</td><td>${escapeHtml(value)}</td></tr>`)
            .join("")}</table>`,
      )
      .join("")}
    <h2>Sheet Blockers</h2>
    <ul>${(blockers.length ? blockers : ["No sheet blockers recorded."]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <div class="title">
      <div>
        <p><strong>Project:</strong> ${escapeHtml(activeSheet.titleBlock.projectName)}</p>
        <p><strong>Stage:</strong> ${escapeHtml(activeSheet.titleBlock.reviewStage)}</p>
        <p><strong>By:</strong> ${escapeHtml(activeSheet.titleBlock.preparedBy)} · <strong>Check:</strong> ${escapeHtml(activeSheet.titleBlock.checkedBy)}</p>
      </div>
      <div>
        <p><strong>${escapeHtml(activeSheet.titleBlock.sheetNumber)}</strong></p>
        <p>${escapeHtml(activeSheet.titleBlock.date)}</p>
      </div>
    </div>
  </div>
</body>
</html>`);
    popup.document.close();
    setStatusMessage("Opened review PDF print view.");
  };

  return {
    addPlanSheetAnnotation,
    getPlanSheetBlockers,
    handleCreateReviewSheet,
    handleMakeReviewPackage,
    handlePlanSheetAddDetailBlock,
    handlePlanSheetAddNote,
    handlePlanSheetAddReference,
    handlePlanSheetAddRevision,
    handlePlanSheetAddTable,
    handlePlanSheetAddViewport,
    handlePlanSheetExportJson,
    handlePlanSheetExportPdf,
    handlePlanSheetGrayscaleToggle,
    handlePlanSheetScaleChange,
    handlePlanSheetTitleBlockUpdate,
    handlePlanSheetViewportDelete,
    handlePlanSheetViewportLayerToggle,
    handlePlanSheetViewportScaleLockToggle,
    handlePlanSheetViewportUpdate,
  };
}
