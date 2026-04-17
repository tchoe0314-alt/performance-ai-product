"use client";

import React, { useMemo, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, MessageSquarePlus } from "lucide-react";

import type { ChatMessage, LearningReport } from "../types";
import {
  computeLearningScore,
  formatCount,
  formatMetric,
  joinNatural,
  toReadableLabel,
} from "../utils/formatting";

type WhatYouNeedSummary = {
  note: string;
  neededNow: string[];
  supporting: string[];
  inScope: string[];
};

type IssueItem = {
  severity: "warning" | "error";
  message: string;
};

type IssueTarget = {
  id: string;
  label: string;
};

type QuantityRow = {
  label: string;
  value: number | null;
  unit: string;
};

type ProjectSidebarProps = {
  onNewProject: () => void;
  chatMessages: ChatMessage[];
  learningReport: LearningReport | null;
  learningReportUpdatedAt: number | null;
  onRefreshLearningReport: () => void;
  previewAssumptionCategories: string[];
  previewFixActions: string[];
  previewFixTargets: string[];
  previewReviewCategories: string[];
  previewBlockedReasons: string[];
  previewReadyDeliverables: string[];
  previewFailedDeliverables: string[];
  previewExtraDeliverables: string[];
  previewReviewReadyCount: number;
  previewReviewRequestedCount: number;
  previewRerunTotal: number;
  whatYouNeedSummary: WhatYouNeedSummary;
  previewRerunSignals: string[];
  issues: IssueItem[];
  issueTargets: IssueTarget[];
  previewInteraction: "static" | "interactive";
  selectedIssueId: string | null;
  onSelectIssue: (value: string) => void;
  totalPipeLength: number | null;
  maxSlope: number | null;
  minSlope: number | null;
  flowCfs: number | null;
  cutFillNet: number | null;
  basinSize: number | null;
  showMeasurements: boolean;
  showCalculations: boolean;
  onToggleMeasurements: () => void;
  onToggleCalculations: () => void;
  previewLayers: {
    buildings: boolean;
    roads: boolean;
    grading: boolean;
    drainage: boolean;
    utilities: boolean;
    structures: boolean;
    lots: boolean;
  };
  onTogglePreviewLayer: (key: keyof ProjectSidebarProps["previewLayers"]) => void;
  onQueuePreviewRefresh: (reason: string) => void;
  mapSnapshotInputRef: React.RefObject<HTMLInputElement | null>;
  surveyInputRef: React.RefObject<HTMLInputElement | null>;
  onUploadImage: (file: File) => Promise<void>;
  onUploadSurvey: (file: File) => Promise<void>;
  surveyFileName: string;
  surveySlopeEstimate: { slope_percent?: number; direction?: string; point_count?: number } | null;
  mapSnapshotPath: string;
  mapAnalysis: {
    success?: boolean;
    counts?: { zones?: number; objects?: number; centerlines?: number };
  } | null;
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
  onEstimateSurveySlope: () => void;
  onAnalyzeMapSnapshot: () => void;
  quantityRollupsEnabled: boolean;
  onToggleQuantityRollups: () => void;
  quantityRows: QuantityRow[];
};

export default function ProjectSidebar({
  onNewProject,
  chatMessages,
  learningReport,
  learningReportUpdatedAt,
  onRefreshLearningReport,
  previewAssumptionCategories,
  previewFixActions,
  previewFixTargets,
  previewReviewCategories,
  previewBlockedReasons,
  previewReadyDeliverables,
  previewFailedDeliverables,
  previewExtraDeliverables,
  previewReviewReadyCount,
  previewReviewRequestedCount,
  previewRerunTotal,
  whatYouNeedSummary,
  previewRerunSignals,
  issues,
  issueTargets,
  previewInteraction,
  selectedIssueId,
  onSelectIssue,
  totalPipeLength,
  maxSlope,
  minSlope,
  flowCfs,
  cutFillNet,
  basinSize,
  showMeasurements,
  showCalculations,
  onToggleMeasurements,
  onToggleCalculations,
  previewLayers,
  onTogglePreviewLayer,
  onQueuePreviewRefresh,
  mapSnapshotInputRef,
  surveyInputRef,
  onUploadImage,
  onUploadSurvey,
  surveyFileName,
  surveySlopeEstimate,
  mapSnapshotPath,
  mapAnalysis,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  onEstimateSurveySlope,
  onAnalyzeMapSnapshot,
  quantityRollupsEnabled,
  onToggleQuantityRollups,
  quantityRows,
}: ProjectSidebarProps) {
  const [showLearningPanel, setShowLearningPanel] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarSections, setSidebarSections] = useState<Record<string, boolean>>({
    assumptions: true,
    fixes: false,
    needsReview: false,
    blockers: false,
    deliverables: true,
    whatYouNeed: true,
    runStability: false,
    issueNavigator: true,
    engineeringMetrics: true,
    overlays: false,
    siteInputs: false,
    materials: false,
    coverage: false,
  });

  const learningSummary = useMemo(() => {
    const sessionLearning = computeLearningScore(chatMessages);
    const reportScore = learningReport?.feedback?.score_percent;
    const reportTotal = learningReport?.feedback?.total;
    const datasetCount = learningReport?.training_examples?.count;
    const lastRun = learningReportUpdatedAt
      ? new Date(learningReportUpdatedAt).toLocaleString()
      : null;
    return { sessionLearning, reportScore, reportTotal, datasetCount, lastRun };
  }, [chatMessages, learningReport, learningReportUpdatedAt]);
  const hasDrainageMetrics =
    Number(totalPipeLength || 0) > 0 ||
    Number(maxSlope || 0) > 0 ||
    Number(minSlope || 0) > 0 ||
    Number(flowCfs || 0) > 0 ||
    Number(cutFillNet || 0) !== 0 ||
    Number(basinSize || 0) > 0;

  const toggleSidebarSection = (key: string) => {
    setSidebarSections((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const renderSidebarSection = (
    key: string,
    title: string,
    body: React.ReactNode,
    meta?: React.ReactNode,
  ) => {
    const isOpen = Boolean(sidebarSections[key]);
    return (
      <div className="rounded-2xl border border-slate-200 bg-white">
        <button
          type="button"
          onClick={() => toggleSidebarSection(key)}
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        >
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              {title}
            </span>
            {meta}
          </div>
          <ChevronDown
            className={`h-4 w-4 text-slate-400 transition ${
              isOpen ? "rotate-180" : ""
            }`}
          />
        </button>
        {isOpen ? <div className="px-4 pb-4">{body}</div> : null}
      </div>
    );
  };

  return (
    <aside
      className={`hidden shrink-0 border-r border-slate-200 bg-[#f1f2f6] lg:flex lg:flex-col ${
        collapsed ? "w-[64px]" : "w-[360px]"
      }`}
    >
      <div className="border-b border-slate-200 p-4">
        <div className="flex items-center justify-between">
          {!collapsed ? (
            <button
              type="button"
              onClick={onNewProject}
              className="flex w-full items-center justify-center rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              <MessageSquarePlus className="mr-2 h-4 w-4" />
              New Project
            </button>
          ) : (
            <button
              type="button"
              onClick={onNewProject}
              className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-950 text-white transition hover:bg-slate-800"
              aria-label="New Project"
            >
              <MessageSquarePlus className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setCollapsed((prev) => !prev)}
            className="ml-3 inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {collapsed ? null : (
        <div className="space-y-6 overflow-y-auto p-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Learning
            </p>
            <button
              type="button"
              onClick={() => setShowLearningPanel((value) => !value)}
              className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 transition hover:bg-slate-100"
            >
              {showLearningPanel ? "Hide" : "Show"}
            </button>
          </div>
          {showLearningPanel ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  {learningSummary.sessionLearning.total ? (
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700">
                      Session {learningSummary.sessionLearning.score}% (
                      {learningSummary.sessionLearning.total})
                    </span>
                  ) : null}
                  {typeof learningSummary.reportScore === "number" ? (
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700">
                      Global {learningSummary.reportScore}% (
                      {learningSummary.reportTotal ?? 0})
                    </span>
                  ) : null}
                  {typeof learningSummary.datasetCount === "number" ? (
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700">
                      Training {learningSummary.datasetCount}
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={onRefreshLearningReport}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    Refresh
                  </button>
                  {learningSummary.lastRun ? (
                    <span className="text-[11px] text-slate-400">
                      Last refresh: {learningSummary.lastRun}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {renderSidebarSection(
          "assumptions",
          "Assumptions",
          <p className="text-sm text-slate-600">
            {previewAssumptionCategories.length
              ? joinNatural(previewAssumptionCategories, 4)
              : "No assumptions were recorded on the latest pass."}
          </p>,
        )}

        {renderSidebarSection(
          "fixes",
          "Fixes Applied",
          <p className="text-sm text-slate-600">
            {previewFixActions.length
              ? joinNatural(previewFixActions, 4)
              : previewFixTargets.length
                ? joinNatural(previewFixTargets, 4)
                : "No corrective fix actions were recorded in the latest pass."}
          </p>,
        )}

        {renderSidebarSection(
          "needsReview",
          "Needs Review",
          <p className="text-sm text-slate-600">
            {previewReviewCategories.length
              ? joinNatural(previewReviewCategories, 4)
              : "No major review categories are currently flagged."}
          </p>,
        )}

        {renderSidebarSection(
          "blockers",
          "Blockers",
          <p className="text-sm text-slate-600">
            {previewBlockedReasons.length
              ? joinNatural(previewBlockedReasons, 4)
              : "No export blockers are currently recorded."}
          </p>,
        )}

        {renderSidebarSection(
          "deliverables",
          "Deliverables",
          <div className="space-y-3 text-sm text-slate-600">
            <div className="flex items-center justify-between text-sm font-semibold text-slate-900">
              <span>Ready</span>
              <span>
                {previewReviewReadyCount}/{previewReviewRequestedCount}
              </span>
            </div>
            <div>
              <p className="font-medium text-slate-900">Ready now</p>
              <p className="mt-1 text-slate-600">
                {previewReadyDeliverables.length
                  ? joinNatural(previewReadyDeliverables, 4)
                  : "No ready deliverables recorded yet."}
              </p>
            </div>
            <div>
              <p className="font-medium text-slate-900">Still blocked</p>
              <p className="mt-1 text-slate-600">
                {previewFailedDeliverables.length
                  ? joinNatural(previewFailedDeliverables, 4)
                  : "No requested deliverables are explicitly failed."}
              </p>
            </div>
            <div>
              <p className="font-medium text-slate-900">Extra preview outputs</p>
              <p className="mt-1 text-slate-600">
                {previewExtraDeliverables.length
                  ? joinNatural(previewExtraDeliverables, 4)
                  : "No extra preview-only outputs were recorded."}
              </p>
            </div>
          </div>,
        )}

        {renderSidebarSection(
          "whatYouNeed",
          "What You Need",
          <div className="space-y-3 text-sm text-slate-600">
            <p>{whatYouNeedSummary.note}</p>
            <div>
              <p className="font-medium text-slate-900">Needed now</p>
              <p className="mt-1">
                {whatYouNeedSummary.neededNow.length
                  ? joinNatural(whatYouNeedSummary.neededNow, 4)
                  : "No critical missing inputs are recorded right now."}
              </p>
            </div>
            <div>
              <p className="font-medium text-slate-900">Helpful next</p>
              <p className="mt-1">
                {whatYouNeedSummary.supporting.length
                  ? joinNatural(whatYouNeedSummary.supporting, 4)
                  : "No additional supporting files or field references are specifically requested."}
              </p>
            </div>
            <div>
              <p className="font-medium text-slate-900">Current scope</p>
              <p className="mt-1">
                {whatYouNeedSummary.inScope.length
                  ? joinNatural(whatYouNeedSummary.inScope, 4)
                  : "No active systems are selected yet."}
              </p>
            </div>
          </div>,
        )}

        {renderSidebarSection(
          "runStability",
          "Run Stability",
          <div className="space-y-2 text-sm text-slate-600">
            <p className="text-2xl font-semibold text-slate-950">
              {previewRerunTotal}
            </p>
            <p>Reruns across the latest engineering cycle</p>
            <p>
              {previewRerunSignals.length
                ? joinNatural(previewRerunSignals, 4)
                : "No repeated reruns were recorded in the latest pass."}
            </p>
          </div>,
        )}

        {renderSidebarSection(
          "issueNavigator",
          "Issues Found",
          <div className="space-y-3 text-sm text-slate-600">
            <p className="text-sm font-medium text-slate-900">
              {issues.length ? "Click an issue to highlight it in preview." : "Issues pending."}
            </p>
            {issues.length ? (
              <div className="space-y-2">
                {issues.map((issue, idx) => (
                  <button
                    key={`${issue.message}-${idx}`}
                    type="button"
                    onClick={() => {
                      if (previewInteraction !== "interactive") return;
                      onSelectIssue(`${issue.message}-${idx}`);
                    }}
                    disabled={previewInteraction !== "interactive"}
                    className={`flex w-full items-start justify-between gap-3 rounded-2xl border px-3 py-2 text-left transition ${
                      selectedIssueId === `${issue.message}-${idx}`
                        ? "border-slate-900 bg-slate-950 text-white"
                        : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                    } ${previewInteraction !== "interactive" ? "cursor-not-allowed opacity-60" : ""}`}
                  >
                    <div className="text-left">
                      <span className="font-medium">{issue.message}</span>
                      {issueTargets[idx]?.label ? (
                        <p className="mt-1 text-[11px] uppercase tracking-[0.12em] opacity-70">
                          Highlight: {issueTargets[idx]?.label}
                        </p>
                      ) : null}
                    </div>
                    <span className="text-xs uppercase tracking-[0.14em] opacity-60">
                      {issue.severity}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
                Issues pending.
              </div>
            )}
            <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
              <span>Allow override</span>
              <button
                type="button"
                className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600"
              >
                Override
              </button>
            </div>
          </div>,
        )}

        {renderSidebarSection(
          "engineeringMetrics",
          "Drainage Stats",
          hasDrainageMetrics ? (
            <div className="grid gap-2 text-sm text-slate-700">
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                <span>Total pipe length</span>
                <span className="font-semibold">{formatMetric(totalPipeLength, "ft")}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                <span>Max slope</span>
                <span className="font-semibold">{formatMetric(maxSlope, "%")}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                <span>Min slope</span>
                <span className="font-semibold">{formatMetric(minSlope, "%")}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                <span>Flow (CFS)</span>
                <span className="font-semibold">{formatMetric(flowCfs, "cfs")}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                <span>Cut / Fill</span>
                <span className="font-semibold">{formatMetric(cutFillNet, "cf")}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                <span>Pond size</span>
                <span className="font-semibold">{formatMetric(basinSize, "sf")}</span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-600">Drainage not generated yet.</p>
          ),
        )}

        {renderSidebarSection(
          "overlays",
          "Overlays",
          <div className="space-y-2 text-sm text-slate-700">
            <button
              type="button"
              onClick={onToggleMeasurements}
              className={`flex w-full items-center justify-between rounded-2xl border px-3 py-2 ${
                showMeasurements
                  ? "border-slate-900 bg-slate-950 text-white"
                  : "border-slate-200 bg-white text-slate-700"
              }`}
            >
              <span>Measurements overlay</span>
              <span className="text-xs uppercase tracking-[0.14em]">
                {showMeasurements ? "On" : "Off"}
              </span>
            </button>
            <button
              type="button"
              onClick={onToggleCalculations}
              className={`flex w-full items-center justify-between rounded-2xl border px-3 py-2 ${
                showCalculations
                  ? "border-slate-900 bg-slate-950 text-white"
                  : "border-slate-200 bg-white text-slate-700"
              }`}
            >
              <span>Calculations overlay</span>
              <span className="text-xs uppercase tracking-[0.14em]">
                {showCalculations ? "On" : "Off"}
              </span>
            </button>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3 text-xs text-slate-600">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                Preview Layers
              </p>
              <div className="mt-2 grid gap-2">
                {[
                  { key: "buildings", label: "Buildings" },
                  { key: "roads", label: "Roads + parking" },
                  { key: "grading", label: "Grading contours" },
                  { key: "drainage", label: "Drainage/storm" },
                  { key: "utilities", label: "Utilities" },
                  { key: "structures", label: "Structures + pools" },
                  { key: "lots", label: "Lots + parcels" },
                ].map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => {
                      onQueuePreviewRefresh("Updating preview layers...");
                      onTogglePreviewLayer(item.key as keyof ProjectSidebarProps["previewLayers"]);
                    }}
                    className={`flex w-full items-center justify-between rounded-2xl border px-3 py-2 text-sm ${
                      previewLayers[item.key as keyof ProjectSidebarProps["previewLayers"]]
                        ? "border-slate-900 bg-slate-950 text-white"
                        : "border-slate-200 bg-white text-slate-700"
                    }`}
                  >
                    <span>{item.label}</span>
                    <span className="text-xs uppercase tracking-[0.14em]">
                      {previewLayers[item.key as keyof ProjectSidebarProps["previewLayers"]]
                        ? "On"
                        : "Off"}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>,
        )}

        {renderSidebarSection(
          "siteInputs",
          "Site Inputs",
          <div className="space-y-2 text-sm text-slate-700">
            <button
              type="button"
              onClick={() => mapSnapshotInputRef.current?.click()}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
            >
              <span>Upload map snapshot</span>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                {uploadedImageApiUrl || uploadedImagePreviewUrl ? "Ready" : "Upload"}
              </span>
            </button>
            <button
              type="button"
              onClick={() => surveyInputRef.current?.click()}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
            >
              <span>Import survey file</span>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                {surveyFileName ? "Ready" : "Upload"}
              </span>
            </button>
            <button
              type="button"
              onClick={onEstimateSurveySlope}
              disabled={!surveyFileName}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span>Estimate slope automatically</span>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                {surveySlopeEstimate?.slope_percent ? "Estimated" : "Compute"}
              </span>
            </button>
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
            {surveyFileName ? (
              <p className="text-xs text-slate-500">Survey loaded: {surveyFileName}</p>
            ) : null}
            {uploadedImageApiUrl || uploadedImagePreviewUrl ? (
              <p className="text-xs text-slate-500">
                Map snapshot loaded and ready for interpretation.
              </p>
            ) : null}
            {mapAnalysis?.success ? (
              <p className="text-xs text-slate-500">
                Map analysis captured {mapAnalysis?.counts?.zones ?? 0} zones,{" "}
                {mapAnalysis?.counts?.objects ?? 0} objects,{" "}
                {mapAnalysis?.counts?.centerlines ?? 0} centerlines.
              </p>
            ) : null}
            {surveySlopeEstimate?.slope_percent ? (
              <p className="text-xs text-slate-500">
                Estimated {surveySlopeEstimate.slope_percent.toFixed(2)}% slope toward{" "}
                {surveySlopeEstimate.direction || "N/A"} from {surveySlopeEstimate.point_count ?? 0} points.
              </p>
            ) : null}
            <input
              ref={mapSnapshotInputRef}
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
            <input
              ref={surveyInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={async (event) => {
                const file = event.currentTarget.files?.[0];
                if (file) {
                  await onUploadSurvey(file);
                }
                event.currentTarget.value = "";
              }}
            />
          </div>,
        )}

        {renderSidebarSection(
          "materials",
          "Materials & Quantities",
          <div className="space-y-2 text-sm text-slate-600">
            <p>Live takeoffs from the current engineering run.</p>
            <button
              type="button"
              onClick={onToggleQuantityRollups}
              className={`mt-1 flex w-full items-center justify-between rounded-2xl border px-3 py-2 text-sm ${
                quantityRollupsEnabled
                  ? "border-slate-900 bg-slate-950 text-white"
                  : "border-slate-200 bg-white text-slate-700"
              }`}
            >
              <span>Quantity rollups</span>
              <span className="text-xs uppercase tracking-[0.14em]">
                {quantityRollupsEnabled ? "On" : "Off"}
              </span>
            </button>
            {quantityRollupsEnabled ? (
              quantityRows.length ? (
                <div className="mt-2 grid gap-2 text-sm text-slate-700">
                  {quantityRows.map((row) => (
                    <div
                      key={row.label}
                      className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2"
                    >
                      <span>{row.label}</span>
                      <span className="font-semibold">
                        {row.unit === "ea" || row.unit === "stalls"
                          ? formatCount(Number(row.value || 0), row.unit)
                          : formatMetric(Number(row.value || 0), row.unit)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-500">
                  Quantities will populate once the plan has run through the engine.
                </p>
              )
            ) : null}
          </div>,
        )}

        {renderSidebarSection(
          "coverage",
          "Coverage Scope",
          <div className="grid gap-2 text-sm text-slate-700">
            {[
              { label: "Roads", status: "Engineering" },
              { label: "Bridges / structural support", status: "Concept" },
              { label: "Recreational swimming pools", status: "Concept" },
              { label: "Subdivisions", status: "Concept" },
              { label: "Drainage / storm", status: "Engineering" },
              { label: "Utilities", status: "Engineering" },
              { label: "Geotechnical support", status: "Concept" },
              { label: "Environmental / regulatory", status: "Concept" },
              { label: "Erosion & sediment", status: "Concept" },
              { label: "Construction workflows", status: "Concept" },
              { label: "Inspection / operations", status: "Concept" },
            ].map((item) => (
              <div
                key={item.label}
                className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2"
              >
                <span>{item.label}</span>
                <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                  {item.status}
                </span>
              </div>
            ))}
          </div>,
        )}

        </div>
      )}
    </aside>
  );
}
