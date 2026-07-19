import type { BuildingPlacement, SmartFixRecommendation } from "../types";
import CivilReviewSheet from "./CivilReviewSheet";
import PlanSheetEditor, {
  type PlanSheetReference,
  type PlanSheetScale,
  type PlanSheetSet,
  type PlanSheetTitleBlock,
  type PlanSheetViewport,
} from "./PlanSheetEditor";
import { DisclosurePanel, PanelCard } from "./ui";

type AutoSiteContextFlowSummary = {
  candidateCount: number;
  candidateLabels: string[];
  missingLabels: string[];
  status: string;
  message: string;
  reviewRequired: boolean;
};

type ReviewPackageFlowSummary = {
  version: "review_package_flow_summary_v1";
  generated_at: string;
  outputs_created: string[];
  missing: string[];
  blocked: boolean;
  next_action: string;
  auto_site_context: AutoSiteContextFlowSummary;
  review_only: true;
  engineer_review_required: true;
  safety_wording: string;
};

type ReviewGateItem = {
  label: string;
  value: string;
  status: string;
};

type DeliverPanelProps = {
  reviewPackageFlowSummary: ReviewPackageFlowSummary | null;
  planPreviewUrl: string;
  hasBackendResult: boolean;
  placedObjectCount: number;
  sidebarTrustScore: string;
  exportActionMessage: string;
  exportBlockReason: string;
  planSheetSet: PlanSheetSet;
  planSheetBlockers: string[];
  projectName: string;
  addressLabel: string;
  lotWidth: number;
  lotHeight: number;
  placements: BuildingPlacement[];
  autoSiteContextFlowSummary: AutoSiteContextFlowSummary;
  sidebarReleaseStatus: string;
  reviewGateItems: readonly ReviewGateItem[];
  topSmartFix?: SmartFixRecommendation | null;
  onMakeReviewPackage: () => void;
  onPlanSheetExportPdf: () => void;
  onExportDxf: () => void;
  onExportReport: () => void;
  onOpenQuantities: () => void;
  onPlanSheetTitleBlockUpdate: (updates: Partial<PlanSheetTitleBlock>) => void;
  onPlanSheetScaleChange: (viewportId: string, scale: PlanSheetScale) => void;
  onPlanSheetViewportUpdate: (viewportId: string, updates: Partial<PlanSheetViewport>) => void;
  onPlanSheetViewportDelete: (viewportId: string) => void;
  onPlanSheetAddNote: (text?: string) => void;
  onPlanSheetAddLabel: () => void;
  onPlanSheetAddCallout: () => void;
  onPlanSheetAddDimension: () => void;
  onPlanSheetAddViewport: () => void;
  onPlanSheetViewportLayerToggle: (viewportId: string, layer: string) => void;
  onPlanSheetViewportScaleLockToggle: (viewportId: string) => void;
  onPlanSheetGrayscaleToggle: () => void;
  onPlanSheetAddRevision: () => void;
  onPlanSheetAddTable: () => void;
  onPlanSheetAddDetailBlock: () => void;
  onPlanSheetAddReference: (kind: PlanSheetReference["kind"]) => void;
  onPlanSheetSelectSheet: (sheetId: string) => void;
  onCreateReviewSheet: () => void;
  onPlanSheetExportJson: () => void;
  onSmartFixAction: (recommendation: SmartFixRecommendation) => void;
};

export function DeliverPanel({
  reviewPackageFlowSummary,
  planPreviewUrl,
  hasBackendResult,
  placedObjectCount,
  sidebarTrustScore,
  exportActionMessage,
  exportBlockReason,
  planSheetSet,
  planSheetBlockers,
  projectName,
  addressLabel,
  lotWidth,
  lotHeight,
  placements,
  autoSiteContextFlowSummary,
  sidebarReleaseStatus,
  reviewGateItems,
  topSmartFix,
  onMakeReviewPackage,
  onPlanSheetExportPdf,
  onExportDxf,
  onExportReport,
  onOpenQuantities,
  onPlanSheetTitleBlockUpdate,
  onPlanSheetScaleChange,
  onPlanSheetViewportUpdate,
  onPlanSheetViewportDelete,
  onPlanSheetAddNote,
  onPlanSheetAddLabel,
  onPlanSheetAddCallout,
  onPlanSheetAddDimension,
  onPlanSheetAddViewport,
  onPlanSheetViewportLayerToggle,
  onPlanSheetViewportScaleLockToggle,
  onPlanSheetGrayscaleToggle,
  onPlanSheetAddRevision,
  onPlanSheetAddTable,
  onPlanSheetAddDetailBlock,
  onPlanSheetAddReference,
  onPlanSheetSelectSheet,
  onCreateReviewSheet,
  onPlanSheetExportJson,
  onSmartFixAction,
}: DeliverPanelProps) {
  return (
    <div className="space-y-3" data-testid="clean-deliver-panel">
      <PanelCard testId="deliver-review-package-flow">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Deliver</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">Package your current project for review.</p>
            <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">
              Review-only and engineer-review-required.
            </p>
          </div>
          <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
            reviewPackageFlowSummary?.blocked ? "bg-amber-50 text-amber-700" : reviewPackageFlowSummary ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
          }`}>
            {reviewPackageFlowSummary?.blocked ? "Needs input" : reviewPackageFlowSummary ? "Made" : "Review"}
          </span>
        </div>
        <button
          type="button"
          aria-label="Make Review Package"
          onClick={onMakeReviewPackage}
          className="mt-4 flex w-full items-center justify-center rounded-xl border border-blue-600 bg-blue-600 px-3 py-3 text-center text-sm font-semibold text-white shadow-[0_14px_30px_-24px_rgba(37,99,235,0.85)] transition hover:bg-blue-700"
        >
          Make a review package
        </button>
        {reviewPackageFlowSummary ? (
          <div className={`mt-3 rounded-xl border px-3 py-2 text-xs ${reviewPackageFlowSummary.blocked ? "border-amber-200 bg-amber-50 text-amber-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`} data-testid="deliver-review-package-summary">
            <p className="font-semibold uppercase tracking-[0.12em]">{reviewPackageFlowSummary.blocked ? "Needs input" : "Package made"}</p>
            <p className="mt-1">Created: {reviewPackageFlowSummary.outputs_created.join(", ") || "none"}</p>
            <p className="mt-1">Missing: {reviewPackageFlowSummary.missing.slice(0, 4).join("; ") || "none recorded"}</p>
            <p className="mt-1 font-semibold">Next: {reviewPackageFlowSummary.next_action}</p>
          </div>
        ) : null}
      </PanelCard>

      <PanelCard testId="deliver-package-contents">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Package Contents</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-3">
            <p className="font-semibold uppercase tracking-[0.12em] text-emerald-700">Included</p>
            <p className="mt-1 text-lg font-semibold text-emerald-900">
              {[planPreviewUrl, hasBackendResult, placedObjectCount > 0, sidebarTrustScore].filter(Boolean).length}
            </p>
            <p className="mt-1 text-[11px] font-medium text-emerald-700">items ready for review</p>
          </div>
          <div className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-3">
            <p className="font-semibold uppercase tracking-[0.12em] text-amber-700">Missing</p>
            <p className="mt-1 text-lg font-semibold text-amber-900">
              {[
                !planPreviewUrl,
                !hasBackendResult,
                !placedObjectCount,
                ...planSheetBlockers.slice(0, 3).map(Boolean),
              ].filter(Boolean).length}
            </p>
            <p className="mt-1 text-[11px] font-medium text-amber-700">items to review or add</p>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          {[
            ["Plan preview", planPreviewUrl ? "Included" : "Missing"],
            ["Generated result", hasBackendResult ? "Included" : "Missing"],
            ["Objects", placedObjectCount ? `${placedObjectCount} placed` : "Missing"],
            ["Source notes", sidebarTrustScore || "Review"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
              <p className="mt-1 font-semibold text-slate-800">{value}</p>
            </div>
          ))}
        </div>
      </PanelCard>

      <PanelCard testId="deliver-export-actions">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Exports</p>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <button
            type="button"
            onClick={onPlanSheetExportPdf}
            className="rounded-xl border border-slate-200 bg-white px-2 py-3 text-center text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Review PDF
          </button>
          <button
            type="button"
            aria-label="Export DXF"
            onClick={onExportDxf}
            title={exportBlockReason || "Download DXF review export"}
            className="rounded-xl border border-slate-200 bg-white px-2 py-3 text-center text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            DXF
          </button>
          <button
            type="button"
            onClick={onExportReport}
            title={exportBlockReason || "Download review report"}
            className="rounded-xl border border-slate-200 bg-white px-2 py-3 text-center text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Report
          </button>
          <button
            type="button"
            onClick={onOpenQuantities}
            className="rounded-xl border border-slate-200 bg-white px-2 py-3 text-center text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Quantities
          </button>
        </div>
        {exportBlockReason ? (
          <p data-testid="deliver-export-blocker" className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
            Export needs input: {exportBlockReason}
          </p>
        ) : null}
        {exportActionMessage ? (
          <p data-testid="deliver-export-status" className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
            {exportActionMessage}
          </p>
        ) : null}
      </PanelCard>

      <DisclosurePanel
        testId="deliver-source-notes"
        title="Source notes"
        subtitle="Data sources and missing items included in this package"
        status={autoSiteContextFlowSummary.candidateCount}
      >
        <div className="space-y-2">
          {(planSheetBlockers.length ? planSheetBlockers.slice(0, 4) : ["No sheet-specific missing items recorded."]).map((item) => (
            <p key={item} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
              {item}
            </p>
          ))}
        </div>
      </DisclosurePanel>

      <DisclosurePanel
        testId="deliver-sheet-details"
        title="Review Sheet Details"
        subtitle="Sheets, labels, notes, viewports, and PDF/JSON export"
        status="Advanced"
        bodyClassName="px-3 py-3"
      >
        <PlanSheetEditor
          sheetSet={{ ...planSheetSet, blockers: planSheetBlockers }}
          onUpdateTitleBlock={onPlanSheetTitleBlockUpdate}
          onChangeScale={onPlanSheetScaleChange}
          onUpdateViewport={onPlanSheetViewportUpdate}
          onDeleteViewport={onPlanSheetViewportDelete}
          onAddNote={onPlanSheetAddNote}
          onAddLabel={onPlanSheetAddLabel}
          onAddCallout={onPlanSheetAddCallout}
          onAddDimension={onPlanSheetAddDimension}
          onAddViewport={onPlanSheetAddViewport}
          onToggleViewportLayer={onPlanSheetViewportLayerToggle}
          onToggleViewportScaleLock={onPlanSheetViewportScaleLockToggle}
          onToggleGrayscale={onPlanSheetGrayscaleToggle}
          onAddRevision={onPlanSheetAddRevision}
          onAddTable={onPlanSheetAddTable}
          onAddDetailBlock={onPlanSheetAddDetailBlock}
          onAddReference={onPlanSheetAddReference}
          onSelectSheet={onPlanSheetSelectSheet}
          onCreateSheet={onCreateReviewSheet}
          onExportJson={onPlanSheetExportJson}
          onExportPdf={onPlanSheetExportPdf}
        />
      </DisclosurePanel>

      <DisclosurePanel
        defaultOpen
        testId="deliver-review-sheet-preview"
        title="Review sheet preview"
        subtitle="Open only when you want sheet layout details"
        status="Preview"
      >
        <CivilReviewSheet
          projectName={projectName}
          addressLabel={addressLabel}
          lotWidth={lotWidth}
          lotHeight={lotHeight}
          placements={placements}
          sourceCandidateCount={autoSiteContextFlowSummary.candidateCount}
          missingSources={autoSiteContextFlowSummary.missingLabels}
          generatedAt={planSheetSet.updatedAt}
        />
      </DisclosurePanel>

      <DisclosurePanel
        testId="deliver-audit-details"
        title="Audit / Review Details"
        subtitle={sidebarReleaseStatus === "blocked" ? "Review package needs input" : "Review package"}
        status={sidebarReleaseStatus === "blocked" ? "Needs input" : "Review"}
        statusClassName="bg-amber-50 text-amber-700"
      >
        <div className="space-y-2">
          {reviewGateItems.map((item) => (
            <div key={item.label} className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              <span className="font-semibold text-slate-700">{item.label}</span>
              <span className={`text-right text-xs font-semibold uppercase tracking-[0.12em] ${item.status === "block" ? "text-red-600" : "text-amber-600"}`}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
        {topSmartFix ? (
          <button
            type="button"
            onClick={() => onSmartFixAction(topSmartFix)}
            className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50"
          >
            {topSmartFix.can_civora_fix ? "Fix Current Blocker" : "Show Needed Input"}
          </button>
        ) : null}
      </DisclosurePanel>
    </div>
  );
}
