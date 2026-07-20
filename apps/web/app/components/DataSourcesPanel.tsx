import type { RefObject } from "react";

import type {
  CandidateReviewInbox,
  CandidateReviewItem,
  MapAnalysis,
  OnlineExistingConditionsSource,
  PlanPdfAnalysis,
  PlanPdfChangedElements,
  PlanPdfElement,
  SourceConfidenceEntry,
} from "../types";
import type { AddressSuggestion, AutoExistingConditionsUiStatus } from "../utils/dashboardDataTypes";
import type { CapabilityExposure } from "../utils/dashboardTypes";
import type { SidePanelKey } from "../utils/workspaceShell";
import type { SystemGenerationTarget } from "../utils/workflowConstants";
import { OVERSIZED_SITE_MESSAGE } from "../utils/workflowConstants";
import { formatCalmActionMessage } from "../utils/objectGeometry";
import { PlanPdfWorkflowPanel } from "./PlanPdfWorkflowPanel";
import { SourceDataReviewPanel } from "./SourceDataReviewPanel";
import { SourceHubPanel } from "./SourceHubPanel";

type PlanPdfPage = NonNullable<PlanPdfAnalysis["pages"]>[number];
type PlanPdfChangedElement = NonNullable<PlanPdfChangedElements["elements"]>[number];
type PlanPdfSummaryRow = readonly [string, number];
type PlanPdfClassificationRow = {
  label: string;
  value: string;
};
type PlanPdfElementPatch = {
  text?: string;
  review_status?: "accepted" | "rejected" | "pending";
  move_target?: {
    x0: number;
    y0: number;
  };
};

export type DataSourcesPanelProps = {
  sourceHubLinks: Array<readonly [SidePanelKey, string]>;
  sourceHubMetrics: Array<readonly [string, string | number]>;
  sourceConfidenceEntryCount: number;
  sourceConfidenceRows: SourceConfidenceEntry[];
  onOpenPanel: (panel: SidePanelKey) => void;
  planPdfAnalysis: PlanPdfAnalysis | undefined;
  planPdfSourceUrl: string;
  planPdfFirstPage: PlanPdfPage | null;
  planPdfElements: PlanPdfElement[];
  selectedPlanPdfElement: PlanPdfElement | null;
  planPdfChangedReport: PlanPdfChangedElements | null;
  planPdfChangedElements: PlanPdfChangedElement[];
  planPdfUnreadableItems: string[];
  planPdfBlockers: string[];
  planPdfUploadState: "idle" | "uploading" | "uploaded" | "failed";
  planPdfUploadMessage: string;
  planPdfElementDraftText: string;
  planPdfMoveX: string;
  planPdfMoveY: string;
  planPdfExtractionSummaryRows: PlanPdfSummaryRow[];
  planPdfClassificationPreviewRows: PlanPdfClassificationRow[];
  planPdfInputRef: RefObject<HTMLInputElement | null>;
  onUploadPlanPdf: (file: File) => Promise<void>;
  onSelectPlanPdfElement: (elementId: string) => void;
  onPlanPdfDraftTextChange: (value: string) => void;
  onPlanPdfMoveXChange: (value: string) => void;
  onPlanPdfMoveYChange: (value: string) => void;
  onUpdatePlanPdfElement: (elementId: string, patch: PlanPdfElementPatch) => void;
  onExportPlanPdfJson: () => void;
  onExportPlanPdf: () => void;
  onEditPdfByChat: () => void;
  onWhatChanged: () => void;
  onAskUnreadable: () => void;
  onInvalidPlanPdfMove: () => void;
  capabilityAuditRows: CapabilityExposure[];
  onlineDiscoveryStatus: string;
  onlineDiscoveryRan: boolean;
  onlineDiscoverySources: OnlineExistingConditionsSource[];
  candidateReviewCounts: NonNullable<CandidateReviewInbox["counts"]>;
  candidateReviewItems: CandidateReviewItem[];
  onCandidateDecision: (candidateId: string, decision: "accept" | "reject" | "pending") => void;
  siteAddress: string;
  selectedAddressSuggestion: AddressSuggestion | null;
  addressSuggestions: AddressSuggestion[];
  onSiteAddressChange: (value: string) => void;
  onSelectedAddressSuggestionChange: (value: AddressSuggestion | null) => void;
  onAddressSuggestionsChange: (value: AddressSuggestion[]) => void;
  onApplyAddress: () => void;
  autoExistingConditionsStatus: AutoExistingConditionsUiStatus;
  mapSnapshotInputRef: RefObject<HTMLInputElement | null>;
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
  imageUploadState: "idle" | "uploading" | "uploaded" | "detecting" | "failed";
  imageUploadNote: string | null;
  mapSnapshotPath: string | null;
  mapAnalysis: MapAnalysis | null;
  onAnalyzeMapSnapshot: () => void;
  siteScaleLocked: boolean;
  onUnlockSite: () => void;
  onApplySite: () => void;
  lotBounds: { w: number; h: number };
  siteTooLargeForWarning: boolean;
  missingSite: boolean;
  hasTerrainSource: boolean;
  siteTooLargeForGrading: boolean;
  onGenerateSystem: (target: SystemGenerationTarget) => void;
  onAnalyzeImageFeatures: () => void;
  missingImage: boolean;
  detectedPlacementsCount: number;
  siteSelectionMode: boolean;
  hasSiteObject: boolean;
  detectionChoices: {
    roads: boolean;
    buildings: boolean;
    parking: boolean;
    grading: boolean;
  };
  onDetectionChoicesChange: (updater: (previous: DataSourcesPanelProps["detectionChoices"]) => DataSourcesPanelProps["detectionChoices"]) => void;
  onRunSelectedDetections: () => void;
  onAnalyzeSiteAccess: () => void;
  confirmedObjectCounts: { buildings: number; access: number };
  analysisIssueCount: number;
  mapAnalysisCounts: { zones: number; objects: number; centerlines: number };
  siteRotationDeg: number;
  siteRotationInput: string;
  onSiteRotationDegChange: (value: number) => void;
  onSiteRotationInputChange: (value: string) => void;
  onScheduleRotationSave: (value: number) => void;
  onFitToSite: () => void;
  onUseMapCenter: () => void;
  onAlignToRoad: () => void;
  drainageSourceOverride: "civora" | "user";
  drainageSurfaceSummary: {
    surfaceSource: string;
    surfaceQuality: string;
    surfaceDetail: string;
  };
  onDrainageSourceOverrideChange: (value: "civora" | "user") => void;
  mapSnapshotUploadInputRef: RefObject<HTMLInputElement | null>;
  onUploadImage: (file: File) => Promise<void>;
};

export function DataSourcesPanel({
  sourceHubLinks,
  sourceHubMetrics,
  sourceConfidenceEntryCount,
  sourceConfidenceRows,
  onOpenPanel,
  planPdfAnalysis,
  planPdfSourceUrl,
  planPdfFirstPage,
  planPdfElements,
  selectedPlanPdfElement,
  planPdfChangedReport,
  planPdfChangedElements,
  planPdfUnreadableItems,
  planPdfBlockers,
  planPdfUploadState,
  planPdfUploadMessage,
  planPdfElementDraftText,
  planPdfMoveX,
  planPdfMoveY,
  planPdfExtractionSummaryRows,
  planPdfClassificationPreviewRows,
  planPdfInputRef,
  onUploadPlanPdf,
  onSelectPlanPdfElement,
  onPlanPdfDraftTextChange,
  onPlanPdfMoveXChange,
  onPlanPdfMoveYChange,
  onUpdatePlanPdfElement,
  onExportPlanPdfJson,
  onExportPlanPdf,
  onEditPdfByChat,
  onWhatChanged,
  onAskUnreadable,
  onInvalidPlanPdfMove,
  capabilityAuditRows,
  onlineDiscoveryStatus,
  onlineDiscoveryRan,
  onlineDiscoverySources,
  candidateReviewCounts,
  candidateReviewItems,
  onCandidateDecision,
  siteAddress,
  selectedAddressSuggestion,
  addressSuggestions,
  onSiteAddressChange,
  onSelectedAddressSuggestionChange,
  onAddressSuggestionsChange,
  onApplyAddress,
  autoExistingConditionsStatus,
  mapSnapshotInputRef,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  imageUploadState,
  imageUploadNote,
  mapSnapshotPath,
  mapAnalysis,
  onAnalyzeMapSnapshot,
  siteScaleLocked,
  onUnlockSite,
  onApplySite,
  lotBounds,
  siteTooLargeForWarning,
  missingSite,
  hasTerrainSource,
  siteTooLargeForGrading,
  onGenerateSystem,
  onAnalyzeImageFeatures,
  missingImage,
  detectedPlacementsCount,
  siteSelectionMode,
  hasSiteObject,
  detectionChoices,
  onDetectionChoicesChange,
  onRunSelectedDetections,
  onAnalyzeSiteAccess,
  confirmedObjectCounts,
  analysisIssueCount,
  mapAnalysisCounts,
  siteRotationDeg,
  siteRotationInput,
  onSiteRotationDegChange,
  onSiteRotationInputChange,
  onScheduleRotationSave,
  onFitToSite,
  onUseMapCenter,
  onAlignToRoad,
  drainageSourceOverride,
  drainageSurfaceSummary,
  onDrainageSourceOverrideChange,
  mapSnapshotUploadInputRef,
  onUploadImage,
}: DataSourcesPanelProps) {
  return (
    <div className="space-y-4">
      <details className="rounded-2xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Detailed source evidence and import tools
        </summary>
        <div className="mt-3 space-y-4">
          <SourceHubPanel
            links={sourceHubLinks}
            metrics={sourceHubMetrics}
            entryCount={sourceConfidenceEntryCount}
            entries={sourceConfidenceRows}
            onOpenPanel={onOpenPanel}
          />
          <PlanPdfWorkflowPanel
            analysis={planPdfAnalysis}
            sourceUrl={planPdfSourceUrl}
            firstPage={planPdfFirstPage}
            elements={planPdfElements}
            selectedElement={selectedPlanPdfElement}
            changedReport={planPdfChangedReport}
            changedElements={planPdfChangedElements}
            unreadableItems={planPdfUnreadableItems}
            blockers={planPdfBlockers}
            uploadState={planPdfUploadState}
            uploadMessage={planPdfUploadMessage}
            draftText={planPdfElementDraftText}
            moveX={planPdfMoveX}
            moveY={planPdfMoveY}
            extractionSummaryRows={planPdfExtractionSummaryRows}
            classificationPreviewRows={planPdfClassificationPreviewRows}
            inputRef={planPdfInputRef}
            onUploadFile={onUploadPlanPdf}
            onSelectElement={onSelectPlanPdfElement}
            onDraftTextChange={onPlanPdfDraftTextChange}
            onMoveXChange={onPlanPdfMoveXChange}
            onMoveYChange={onPlanPdfMoveYChange}
            onUpdateElement={(elementId, patch) => onUpdatePlanPdfElement(elementId, patch)}
            onExportJson={onExportPlanPdfJson}
            onExportPdf={onExportPlanPdf}
            onEditByChat={onEditPdfByChat}
            onWhatChanged={onWhatChanged}
            onAskUnreadable={onAskUnreadable}
            onInvalidMove={onInvalidPlanPdfMove}
          />
          <SourceDataReviewPanel
            capabilityRows={capabilityAuditRows}
            onlineDiscoveryStatus={onlineDiscoveryStatus}
            onlineDiscoveryRan={onlineDiscoveryRan}
            onlineDiscoverySources={onlineDiscoverySources}
            candidateCounts={candidateReviewCounts}
            candidateItems={candidateReviewItems}
            onCandidateDecision={(candidateId, decision) => onCandidateDecision(candidateId, decision)}
          />
          <div>
            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Site address
            </label>
            <input
              value={siteAddress}
              onChange={(event) => {
                onSiteAddressChange(event.target.value);
                onSelectedAddressSuggestionChange(null);
              }}
              placeholder="123 Main St, City, State"
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-slate-400 focus:outline-none"
            />
            {addressSuggestions.length ? (
              <div className="mt-2 max-h-40 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-2 text-xs text-slate-600">
                {addressSuggestions.map((suggestion) => (
                  <button
                    key={`${suggestion.lat ?? "lat"}-${suggestion.lng ?? "lng"}-${suggestion.display_name ?? "address"}`}
                    type="button"
                    aria-label={`Use address suggestion ${suggestion.display_name ?? "address"}`}
                    onClick={() => {
                      onSelectedAddressSuggestionChange(suggestion);
                      onSiteAddressChange(suggestion.display_name ?? siteAddress);
                      onAddressSuggestionsChange([]);
                    }}
                    className={`w-full rounded-xl px-3 py-2 text-left text-[12px] transition ${
                      selectedAddressSuggestion?.display_name === suggestion.display_name
                        ? "bg-slate-900 text-white"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <span className="block truncate">{suggestion.display_name ?? "Address suggestion"}</span>
                  </button>
                ))}
              </div>
            ) : null}
            <button
              type="button"
              onClick={onApplyAddress}
              disabled={!siteAddress.trim()}
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Apply address
            </button>
            {autoExistingConditionsStatus.status === "blocked" ? (
              <p data-testid="apply-address-status" className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
                {formatCalmActionMessage(autoExistingConditionsStatus.message)}
              </p>
            ) : null}
          </div>

          <div className="space-y-2 text-sm text-slate-700">
            <button
              type="button"
              onClick={() => mapSnapshotInputRef.current?.click()}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
            >
              <span>Upload site image / map snapshot</span>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                {uploadedImageApiUrl || uploadedImagePreviewUrl ? "Ready" : "Upload"}
              </span>
            </button>
            {imageUploadState !== "idle" ? (
              <p data-testid="image-upload-status" className={`rounded-xl border px-3 py-2 text-xs font-semibold ${
                imageUploadState === "failed"
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-slate-200 bg-slate-50 text-slate-600"
              }`}>
                {imageUploadNote ||
                  (imageUploadState === "uploading"
                    ? "Uploading image..."
                    : imageUploadState === "detecting"
                      ? "Detecting site features..."
                      : imageUploadState === "failed"
                        ? "Image upload failed."
                        : "Image uploaded.")}
              </p>
            ) : null}
            <button
              type="button"
              onClick={onAnalyzeMapSnapshot}
              disabled={!mapSnapshotPath}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span>Analyze map snapshot</span>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                {mapAnalysis?.success ? "Ready" : "Analyze"}
              </span>
            </button>
            {siteScaleLocked ? (
              <button
                type="button"
                onClick={onUnlockSite}
                className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
              >
                <span>Change Site</span>
                <span className="text-xs uppercase tracking-[0.14em] text-slate-400">Unlock</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={onApplySite}
                className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
              >
                <span>Lock Site</span>
                <span className="text-xs uppercase tracking-[0.14em] text-slate-400">Apply</span>
              </button>
            )}
            <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-600">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                Site
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-800">
                {lotBounds.w && lotBounds.h
                  ? `Site: ${lotBounds.w.toFixed(0)} ft x ${lotBounds.h.toFixed(0)} ft`
                  : "Site: -"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Status: {siteScaleLocked ? "Site Locked" : "Selecting Site"}
              </p>
              {siteTooLargeForWarning ? (
                <p className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-700">
                  {OVERSIZED_SITE_MESSAGE}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => onGenerateSystem("grading")}
              disabled={missingSite || !hasTerrainSource || siteTooLargeForGrading}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span>Detect grading</span>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                {missingSite
                  ? "Needs site"
                  : !hasTerrainSource
                    ? "Needs terrain"
                    : siteTooLargeForGrading
                      ? "Too large"
                      : "Run"}
              </span>
            </button>
            <button
              type="button"
              onClick={onAnalyzeImageFeatures}
              disabled={!mapSnapshotPath}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span>Detect site features</span>
              <span className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-slate-400">
                {missingImage ? "Needs image" : detectedPlacementsCount ? "Detected" : "Run"}
              </span>
            </button>
            {!siteSelectionMode && hasSiteObject ? (
              <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-600">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Detect existing context
                </p>
                <div className="mt-2 grid gap-2">
                  {(["roads", "buildings", "parking"] as const).map((key) => (
                    <label key={key} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={detectionChoices[key]}
                        onChange={(event) =>
                          onDetectionChoicesChange((prev) => ({
                            ...prev,
                            [key]: event.target.checked,
                          }))
                        }
                      />
                      <span className="capitalize">{key}</span>
                    </label>
                  ))}
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={detectionChoices.grading}
                      onChange={(event) =>
                        onDetectionChoicesChange((prev) => ({
                          ...prev,
                          grading: event.target.checked,
                        }))
                      }
                    />
                    <span>Detect grading</span>
                  </label>
                </div>
                <button
                  type="button"
                  onClick={onRunSelectedDetections}
                  className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
                >
                  Run selected detection
                </button>
              </div>
            ) : null}
            <button
              type="button"
              onClick={onAnalyzeSiteAccess}
              disabled={confirmedObjectCounts.buildings === 0 || confirmedObjectCounts.access === 0}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
            >
              <span>Analyze site access</span>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                {analysisIssueCount ? "Reviewed" : "Run"}
              </span>
            </button>
            {confirmedObjectCounts.buildings === 0 || confirmedObjectCounts.access === 0 ? (
              <p className="text-xs text-slate-500">
                Address provides site context only. Add or confirm buildings and access objects to run analysis.
              </p>
            ) : null}
            {uploadedImageApiUrl || uploadedImagePreviewUrl ? (
              <p className="text-xs text-slate-500">
                Map snapshot loaded and ready for interpretation.
              </p>
            ) : null}
            {mapAnalysis?.success ? (
              <p className="text-xs text-slate-500">
                Map analysis captured {mapAnalysisCounts.zones} zones,{" "}
                {mapAnalysisCounts.objects} objects,{" "}
                {mapAnalysisCounts.centerlines} centerlines.
              </p>
            ) : null}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              Site rotation
            </p>
            <div className="mt-3 flex items-center gap-3">
              <input
                type="range"
                min={-180}
                max={180}
                value={siteRotationDeg}
                disabled={siteScaleLocked}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  onSiteRotationDegChange(value);
                  onSiteRotationInputChange(String(value));
                  onScheduleRotationSave(value);
                }}
                className="w-full disabled:cursor-not-allowed disabled:opacity-50"
              />
              <input
                type="number"
                value={siteRotationInput}
                disabled={siteScaleLocked}
                onChange={(event) => {
                  onSiteRotationInputChange(event.target.value);
                  const value = Number(event.target.value);
                  if (Number.isFinite(value)) {
                    onSiteRotationDegChange(value);
                    onScheduleRotationSave(value);
                  }
                }}
                className="w-24 rounded-lg border border-slate-200 px-2 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={onFitToSite} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50">
                Fit to Site
              </button>
              <button type="button" onClick={onUseMapCenter} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50">
                Use Map Center
              </button>
              <button type="button" onClick={onAlignToRoad} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50">
                Align to Nearest Road
              </button>
              <button
                type="button"
                onClick={() => {
                  onSiteRotationDegChange(0);
                  onSiteRotationInputChange("0");
                  onScheduleRotationSave(0);
                }}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600 hover:bg-slate-50"
              >
                Reset Rotation
              </button>
            </div>
            {!siteScaleLocked ? (
              <p className="mt-2 text-xs text-slate-500">
                Hold <span className="font-semibold">R</span> and drag the canvas to rotate the site.
              </p>
            ) : null}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              Drainage source
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-800">
              {drainageSourceOverride === "user" ? "User provided" : "Civora generated"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Source: {drainageSurfaceSummary.surfaceSource}
              {drainageSurfaceSummary.surfaceQuality
                ? ` · ${drainageSurfaceSummary.surfaceQuality.replace(/_/g, " ")}`
                : ""}
            </p>
            {drainageSurfaceSummary.surfaceDetail ? (
              <p className="mt-1 text-xs text-slate-500">
                {drainageSurfaceSummary.surfaceDetail}
              </p>
            ) : null}
            <label className="mt-3 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
              <span>Source override</span>
              <select
                value={drainageSourceOverride}
                onChange={(event) => onDrainageSourceOverrideChange(event.target.value === "user" ? "user" : "civora")}
                className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700"
              >
                <option value="civora">Civora</option>
                <option value="user">User</option>
              </select>
            </label>
          </div>

          <input
            ref={mapSnapshotUploadInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={async (event) => {
              const file = event.currentTarget.files?.[0];
              if (file) {
                await onUploadImage(file);
              }
              event.currentTarget.value = "";
            }}
          />
        </div>
      </details>
    </div>
  );
}
