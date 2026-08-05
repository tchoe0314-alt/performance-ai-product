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
import {
  customerFacingReviewNotes,
  normalizeReviewSheetSetForProject,
} from "./reviewPackagePresentation";
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
    const blockers = new Set<string>(customerFacingReviewNotes(sheetSetOverride.blockers));
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
    return customerFacingReviewNotes(blockers);
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
      const projectName = currentProject?.name || siteName || "Untitled Project";
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
    const missing = customerFacingReviewNotes(uniqueStrings([
      ...blockers,
      !backendResult ? "generated system result is missing" : "",
      !planPreviewUrl ? "model preview is missing" : "",
      ...autoSiteContextFlowSummary.missingLabels.map((item) => `Auto Site Context source missing: ${item}`),
    ]));
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
      safety_wording: "Review package output is prepared for qualified professional review.",
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
      const projectName = currentProject?.name || siteName || "Untitled Project";
      const sheets = current.sheets.length ? current.sheets : [createDefaultPlanSheet(0, projectName)];
      const activeSheetId = current.activeSheetId || sheets[0]?.id || "";
      const activeSheet = sheets.find((sheet) => sheet.id === activeSheetId) ?? sheets[0];
      const sourceNote = autoSiteContextFlowSummary.candidateCount
        ? `Auto Site Context: ${autoSiteContextFlowSummary.candidateCount} review-required source candidate(s). Missing: ${autoSiteContextFlowSummary.missingLabels.join(", ") || "source evidence not available yet"}.`
        : `Auto Site Context: no accepted source candidates. Missing: ${autoSiteContextFlowSummary.missingLabels.join(", ") || "source evidence not available yet"}.`;
      const nextSheets = sheets.map((sheet) =>
        sheet.id === activeSheet?.id
          ? {
              ...sheet,
              titleBlock: {
                ...sheet.titleBlock,
                projectName,
              },
              annotations: [
                ...sheet.annotations.filter((item) => !item.text.startsWith("Auto Site Context:")),
                {
                  id: `auto-site-context-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                  type: "note" as const,
                  text: sourceNote,
                  x: 10,
                  y: 18,
                },
              ],
              detailBlocks: [
                ...sheet.detailBlocks.filter((item) => !item.id.startsWith("review-package-")),
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
      return normalizeReviewSheetSetForProject({
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
      }, projectName);
    });
    appendChatMessage(
      "assistant",
      [
        `Made a review-only package from what exists: ${summary.outputs_created.join(", ")}.`,
        summary.missing.length ? `Missing: ${summary.missing.slice(0, 5).join("; ")}.` : "Missing: none currently recorded.",
        "Prepared for qualified professional review.",
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
    const projectName = currentProject?.name || siteName || "civora-project";
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
    handlePlanSheetGrayscaleToggle,
    handlePlanSheetScaleChange,
    handlePlanSheetTitleBlockUpdate,
    handlePlanSheetViewportDelete,
    handlePlanSheetViewportLayerToggle,
    handlePlanSheetViewportScaleLockToggle,
    handlePlanSheetViewportUpdate,
  };
}
