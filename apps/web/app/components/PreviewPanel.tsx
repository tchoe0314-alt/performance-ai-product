"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Maximize2, X } from "lucide-react";

import type {
  Preview3DItem,
  PreviewResponse,
  PreviewReview,
} from "../types";
import { formatCount, formatMetric } from "../utils/formatting";
import Preview3DCanvas from "./Preview3DCanvas";

type PreviewPhaseLabel = { label: string } | null;

type PreviewPanelProps = {
  previewReview: PreviewReview | null;
  previewTotalPhaseCount: number;
  previewCompletedPhaseCount: number;
  previewRunningPhase: PreviewPhaseLabel;
  previewNextPendingPhase: PreviewPhaseLabel;
  onRefreshPreview: () => void;
  busy: boolean;
  planPreviewUrl: string;
  previewMode: "2d" | "3d";
  previewInteraction: "static" | "interactive";
  previewQuality: "standard" | "high";
  previewRenderMode: "production" | "engineering" | "debug";
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewInteraction: (value: "static" | "interactive") => void;
  onSetPreviewQuality: (value: "standard" | "high") => void;
  onSetPreviewRenderMode: (value: "production" | "engineering" | "debug") => void;
  onQueuePreviewRefresh: (reason: string) => void;
  previewRefreshing: boolean;
  previewRefreshNote: string | null;
  preview3DEffectiveItems: Preview3DItem[];
  usingAnnotation3D: boolean;
  onOpenFullscreen: () => void;
  previewFullscreenOpen: boolean;
  onCloseFullscreen: () => void;
  onExportDxf: () => void;
  onExportReport: () => void;
  planPreviewAnnotations: PreviewResponse["preview_annotations"] | null;
  selectedIssueLabel: string;
  showMeasurements: boolean;
  showCalculations: boolean;
  measurementOverlayStats: Array<{ label: string; value: number | null; unit: string }>;
  calculationOverlayStats: Array<{ label: string; value: number | null; unit: string }>;
};

export default function PreviewPanel({
  previewReview,
  previewTotalPhaseCount,
  previewCompletedPhaseCount,
  previewRunningPhase,
  previewNextPendingPhase,
  onRefreshPreview,
  busy,
  planPreviewUrl,
  previewMode,
  previewInteraction,
  previewQuality,
  previewRenderMode,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onSetPreviewQuality,
  onSetPreviewRenderMode,
  onQueuePreviewRefresh,
  previewRefreshing,
  previewRefreshNote,
  preview3DEffectiveItems,
  usingAnnotation3D,
  onOpenFullscreen,
  previewFullscreenOpen,
  onCloseFullscreen,
  onExportDxf,
  onExportReport,
  planPreviewAnnotations,
  selectedIssueLabel,
  showMeasurements,
  showCalculations,
  measurementOverlayStats,
  calculationOverlayStats,
}: PreviewPanelProps) {
  const previewAudit = planPreviewAnnotations?.audit;
  const previewLabels = useMemo(
    () => (Array.isArray(planPreviewAnnotations?.labels) ? planPreviewAnnotations?.labels : []),
    [planPreviewAnnotations],
  );
  const [hoveredAnnotation, setHoveredAnnotation] = useState<(typeof previewLabels)[number] | null>(null);
  const [pinnedAnnotation, setPinnedAnnotation] = useState<(typeof previewLabels)[number] | null>(null);
  const [hoverPoint, setHoverPoint] = useState<{ x: number; y: number } | null>(null);
  const [fullscreenHoverPoint, setFullscreenHoverPoint] = useState<{ x: number; y: number } | null>(null);
  const previewRef = useRef<HTMLDivElement | null>(null);
  const fullscreenRef = useRef<HTMLDivElement | null>(null);
  const activeAnnotation = pinnedAnnotation ?? hoveredAnnotation;
  const hasInteractiveLabels = previewLabels.length > 0;
  const showInteractive = previewInteraction === "interactive";
  const resolveHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      containerRef: React.RefObject<HTMLDivElement | null>,
      setPoint: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>,
    ) => {
      if (!showInteractive || !containerRef.current || !hasInteractiveLabels) {
        setHoveredAnnotation(null);
        setPoint(null);
        return;
      }
      const rect = containerRef.current.getBoundingClientRect();
      const x = (event.clientX - rect.left) / Math.max(rect.width, 1);
      const y = (event.clientY - rect.top) / Math.max(rect.height, 1);
      const matches = previewLabels
        .filter((label) => {
          const bounds = label.bounds;
          if (!bounds) return false;
          return x >= bounds.x1 && x <= bounds.x2 && y >= bounds.y1 && y <= bounds.y2;
        })
        .sort((a, b) => {
          const aBounds = a.bounds;
          const bBounds = b.bounds;
          if (!aBounds || !bBounds) return 0;
          const aArea = Math.max(0, aBounds.x2 - aBounds.x1) * Math.max(0, aBounds.y2 - aBounds.y1);
          const bArea = Math.max(0, bBounds.x2 - bBounds.x1) * Math.max(0, bBounds.y2 - bBounds.y1);
          return aArea - bArea;
        });
      const next = matches[0] ?? null;
      setHoveredAnnotation(next);
      setPoint({ x: event.clientX - rect.left, y: event.clientY - rect.top });
    },
    [hasInteractiveLabels, previewLabels, showInteractive],
  );

  const formatHoverValue = (value: number | null | undefined, suffix: string) => {
    if (value === null || value === undefined || Number.isNaN(value)) return null;
    return `${value.toFixed(2)}${suffix}`;
  };
  const hoverDetails = useMemo(() => {
    if (!activeAnnotation?.meta) return [];
    const meta = activeAnnotation.meta;
    const entries = [
      { label: "System", value: meta.system },
      { label: "Layer", value: activeAnnotation.layer },
      { label: "Type", value: meta.entity_type },
      { label: "Length", value: formatHoverValue(meta.length_ft ?? null, " ft") },
      { label: "Width", value: formatHoverValue(meta.width_ft ?? null, " ft") },
      { label: "Height", value: formatHoverValue(meta.height_ft ?? null, " ft") },
      { label: "Area", value: formatHoverValue(meta.area_sf ?? null, " sf") },
      { label: "Slope", value: formatHoverValue(meta.slope_pct ?? null, "%") },
      { label: "Diameter", value: formatHoverValue(meta.diameter_in ?? null, " in") },
      { label: "Flow", value: formatHoverValue(meta.flow_cfs ?? null, " cfs") },
      { label: "Elevation", value: formatHoverValue(meta.elevation_ft ?? null, " ft") },
      { label: "Invert Start", value: formatHoverValue(meta.invert_start_ft ?? null, " ft") },
      { label: "Invert End", value: formatHoverValue(meta.invert_end_ft ?? null, " ft") },
    ];
    return entries.filter((entry) => entry.value);
  }, [activeAnnotation, formatHoverValue]);
  return (
    <div className="rounded-[28px] border border-slate-200 bg-white/90 p-4 shadow-[0_20px_60px_-40px_rgba(15,23,42,0.4)] backdrop-blur md:p-6">
      <div className="mb-4 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600">
              Preview Workspace
            </span>
            {previewReview && (
              <span
                className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                  previewReview.release_status === "ready"
                    ? "bg-emerald-100 text-emerald-800"
                    : previewReview.release_status === "blocked"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-slate-100 text-slate-700"
                }`}
              >
                {previewReview.release_status === "ready"
                  ? "Release Ready"
                  : previewReview.release_status === "blocked"
                    ? "Blocked"
                    : "Needs Review"}
              </span>
            )}
          </div>
          <p className="text-sm font-semibold text-slate-950">Live Preview</p>
          <p className="mt-1 text-sm text-slate-500">
            The preview shows the latest engineered plan even when final export is still under review.
          </p>
          {previewReview && (
            <div
              className={`inline-flex max-w-3xl items-start rounded-2xl border px-4 py-3 text-sm ${
                previewReview.release_status === "ready"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                  : previewReview.release_status === "blocked"
                    ? "border-amber-200 bg-amber-50 text-amber-900"
                    : "border-slate-200 bg-slate-50 text-slate-700"
              }`}
            >
              <div>
                <p className="font-semibold">
                  {previewReview.release_status === "ready"
                    ? "Release review is clear."
                    : previewReview.release_status === "blocked"
                      ? "Export is still blocked."
                      : "Preview needs follow-up review."}
                </p>
                <p className="mt-1 text-xs">
                  {previewReview.release_note ||
                    "Preview review summary is available for the latest engineering pass."}
                </p>
              </div>
            </div>
          )}
          {previewTotalPhaseCount > 0 && previewCompletedPhaseCount < previewTotalPhaseCount ? (
            <div className="inline-flex max-w-3xl items-start rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <div>
                <p className="font-semibold">Preview shows completed phases only.</p>
                <p className="mt-1 text-xs">
                  {previewRunningPhase
                    ? `${previewRunningPhase.label} is the current active phase. Systems like drainage, storm, and utilities appear after their phases finish.`
                    : previewNextPendingPhase
                      ? `${previewNextPendingPhase.label} is still pending. Systems like drainage, storm, and utilities appear after their phases finish.`
                      : "Additional systems appear as later phases complete."}
                </p>
              </div>
            </div>
          ) : null}
          {previewAudit ? (
            <div className="inline-flex max-w-3xl items-start rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
              <div>
                <p className="font-semibold uppercase tracking-[0.18em] text-[10px] text-slate-500">
                  Preview Audit
                </p>
                <p className="mt-2 text-xs">
                  Mode: <span className="font-semibold text-slate-900">{previewRenderMode}</span>
                </p>
                <p className="mt-1 text-xs">
                  Rendered final:{" "}
                  <span className="font-semibold text-slate-900">
                    {formatCount(previewAudit.rendered_final_count ?? 0)}
                  </span>
                  {" · "}
                  Filtered helper/debug:{" "}
                  <span className="font-semibold text-slate-900">
                    {formatCount(previewAudit.filtered_helper_count ?? 0)}
                  </span>
                  {" · "}
                  Hidden incomplete:{" "}
                  <span className="font-semibold text-slate-900">
                    {formatCount(previewAudit.hidden_incomplete_phase_count ?? 0)}
                  </span>
                </p>
              </div>
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onRefreshPreview}
            disabled={busy}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Refresh Preview
          </button>
          {planPreviewUrl ? (
            <button
              type="button"
              onClick={onOpenFullscreen}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              <Maximize2 className="h-4 w-4" />
              Fullscreen Preview
            </button>
          ) : null}
          <button
            type="button"
            onClick={onExportDxf}
            disabled={busy}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Export DXF
          </button>
          <button
            type="button"
            onClick={onExportReport}
            disabled={busy}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Export Report
          </button>
        </div>
      </div>

      {planPreviewUrl ? (
        <div className="rounded-[28px] border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#edf2f7_100%)] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Preview Mode</span>
              <button
                type="button"
                onClick={() => onSetPreviewMode("2d")}
                className={`rounded-full border px-2.5 py-1 ${
                  previewMode === "2d"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                2D
              </button>
              <button
                type="button"
                onClick={() => onSetPreviewMode("3d")}
                className={`rounded-full border px-2.5 py-1 ${
                  previewMode === "3d"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                3D
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Interaction</span>
              <button
                type="button"
                onClick={() => onSetPreviewInteraction("static")}
                className={`rounded-full border px-2.5 py-1 ${
                  previewInteraction === "static"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Static
              </button>
              <button
                type="button"
                onClick={() => {
                  if (previewInteraction === "interactive") return;
                  onQueuePreviewRefresh("Loading interactive labels...");
                  onSetPreviewInteraction("interactive");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewInteraction === "interactive"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Interactive
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Quality</span>
              <button
                type="button"
                onClick={() => {
                  if (previewQuality === "standard") return;
                  onQueuePreviewRefresh("Requesting standard-quality preview...");
                  onSetPreviewQuality("standard");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewQuality === "standard"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Standard
              </button>
              <button
                type="button"
                onClick={() => {
                  if (previewQuality === "high") return;
                  onQueuePreviewRefresh("Requesting high-quality preview...");
                  onSetPreviewQuality("high");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewQuality === "high"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                High
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Preview Mode</span>
              <button
                type="button"
                onClick={() => {
                  if (previewRenderMode === "production") return;
                  onQueuePreviewRefresh("Switching to production preview...");
                  onSetPreviewRenderMode("production");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewRenderMode === "production"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Production
              </button>
              <button
                type="button"
                onClick={() => {
                  if (previewRenderMode === "engineering") return;
                  onQueuePreviewRefresh("Switching to engineering preview...");
                  onSetPreviewRenderMode("engineering");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewRenderMode === "engineering"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Engineering
              </button>
              <button
                type="button"
                onClick={() => {
                  if (previewRenderMode === "debug") return;
                  onQueuePreviewRefresh("Switching to debug preview...");
                  onSetPreviewRenderMode("debug");
                }}
                className={`rounded-full border px-2.5 py-1 ${
                  previewRenderMode === "debug"
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Debug
              </button>
            </div>
          </div>
          {(previewRefreshing || previewRefreshNote) && (
            <div className="mb-4 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              <span>{previewRefreshNote || "Refreshing preview..."}</span>
            </div>
          )}
          {previewMode === "3d" ? (
            preview3DEffectiveItems.length ? (
              <div className="relative">
                <Preview3DCanvas
                  items={preview3DEffectiveItems}
                  interactive={previewInteraction === "interactive"}
                  onOpenFullscreen={onOpenFullscreen}
                />
                {previewRenderMode !== "production" ? (
                  <div className="pointer-events-none absolute left-4 top-4 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm">
                    {previewRenderMode === "debug" ? "Debug mode" : "Engineering overlays"}
                  </div>
                ) : null}
                {usingAnnotation3D ? (
                  <div
                    className={`pointer-events-none absolute left-4 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm ${
                      previewRenderMode !== "production" ? "top-14" : "top-4"
                    }`}
                  >
                    Approximate 3D
                  </div>
                ) : null}
                <button
                  type="button"
                  onClick={onOpenFullscreen}
                  className="absolute bottom-4 right-4 rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm transition hover:bg-slate-900"
                >
                  Open Fullscreen
                </button>
              </div>
            ) : (
              <div className="relative flex min-h-[560px] items-center justify-center overflow-hidden rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={planPreviewUrl}
                  alt="Generated plan preview"
                  className="max-h-[560px] w-full origin-center -skew-y-1 scale-[0.98] object-contain"
                  onClick={onOpenFullscreen}
                />
                <div className="pointer-events-none absolute left-6 top-6 rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 shadow-sm">
                  3D geometry not ready yet
                </div>
              </div>
            )
          ) : (
            <div
              ref={previewRef}
              className="relative flex min-h-[560px] items-center justify-center overflow-hidden rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)]"
              onMouseMove={(event) => resolveHover(event, previewRef, setHoverPoint)}
              onMouseLeave={() => {
                setHoveredAnnotation(null);
                setHoverPoint(null);
              }}
              onClick={() => {
                if (!showInteractive || !hoveredAnnotation) return;
                setPinnedAnnotation((prev) =>
                  prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
                );
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={planPreviewUrl}
                alt="Generated plan preview"
                className={`max-h-[560px] w-full object-contain ${
                  previewInteraction === "interactive" ? "cursor-crosshair" : "cursor-default"
                }`}
                onClick={onOpenFullscreen}
              />
              {showInteractive && activeAnnotation && hoverPoint ? (
                <div
                  className="pointer-events-none absolute z-20 min-w-[220px] max-w-[280px] rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg"
                  style={{
                    left: Math.min(Math.max(hoverPoint.x + 16, 16), 520),
                    top: Math.min(Math.max(hoverPoint.y + 16, 16), 420),
                  }}
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    {activeAnnotation.label}
                  </p>
                  <div className="mt-2 space-y-1">
                    {hoverDetails.length ? (
                      hoverDetails.map((detail) => (
                        <div key={detail.label} className="flex items-center justify-between gap-2">
                          <span className="text-slate-500">{detail.label}</span>
                          <span className="font-semibold text-slate-900">{detail.value}</span>
                        </div>
                      ))
                    ) : (
                      <span className="text-slate-500">No engineering metadata.</span>
                    )}
                  </div>
                </div>
              ) : null}
              <div className="pointer-events-none absolute bottom-6 left-6 hidden rounded-[18px] border border-white/20 bg-white/70 px-4 py-3 text-xs text-slate-700 shadow-[0_10px_30px_-20px_rgba(15,23,42,0.6)] backdrop-blur lg:block">
                <span className="font-semibold uppercase tracking-[0.18em] text-slate-500">
                  AI Layout + Generation
                </span>
              </div>
              {previewRenderMode !== "production" ? (
                <div className="pointer-events-none absolute left-6 top-6 hidden rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white lg:block">
                  {previewRenderMode === "debug" ? "Debug mode" : "Engineering overlays"}
                </div>
              ) : null}
              {previewInteraction === "interactive" ? (
                <div
                  className={`pointer-events-none absolute left-6 hidden rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white lg:block ${
                    previewRenderMode !== "production" ? "top-16" : "top-6"
                  }`}
                >
                  Hover geometry for details
                </div>
              ) : null}
            </div>
          )}
        </div>
      ) : (
        <div className="flex min-h-[360px] items-center justify-center rounded-[28px] border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500">
          Send a message and Civora AI will generate a plan preview here.
        </div>
      )}

      {previewFullscreenOpen && planPreviewUrl ? (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/88 p-4 backdrop-blur-sm">
          <div className="flex h-full w-full max-w-[96vw] flex-col rounded-[28px] border border-slate-700/60 bg-slate-950 shadow-[0_30px_90px_-40px_rgba(15,23,42,0.95)]">
            <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-5 py-4 text-white">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Fullscreen Preview
                </p>
                <p className="mt-1 text-sm text-slate-200">
                  Inspect the latest engineered plan without the sidebar chrome.
                </p>
              </div>
              <button
                type="button"
                onClick={onCloseFullscreen}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-100 transition hover:bg-slate-800"
              >
                <X className="h-4 w-4" />
                Close
              </button>
            </div>
            <div className="flex min-h-0 flex-1 items-center justify-center p-4">
              <div
                ref={fullscreenRef}
                className="relative max-h-full w-full"
                onMouseMove={(event) => resolveHover(event, fullscreenRef, setFullscreenHoverPoint)}
                onMouseLeave={() => {
                  setHoveredAnnotation(null);
                  setFullscreenHoverPoint(null);
                }}
                onClick={() => {
                  if (!showInteractive || !hoveredAnnotation) return;
                  setPinnedAnnotation((prev) =>
                    prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
                  );
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={planPreviewUrl}
                  alt="Generated plan preview fullscreen"
                  className="max-h-full w-full rounded-[20px] bg-white object-contain shadow-2xl"
                />
                {previewInteraction === "interactive" &&
                !planPreviewAnnotations?.labels?.length ? (
                  <div className="pointer-events-none absolute right-6 top-6 rounded-2xl border border-white/20 bg-slate-900/80 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white">
                    No hover labels yet. Refresh the preview to generate them.
                  </div>
                ) : null}
                {previewInteraction === "interactive" &&
                planPreviewAnnotations?.labels?.length ? (
                  <div className="pointer-events-none absolute inset-0">
                    {selectedIssueLabel ? (
                      (() => {
                        const target = planPreviewAnnotations.labels.find(
                          (item) => item.label === selectedIssueLabel && item.bounds,
                        );
                        if (!target?.bounds) return null;
                        const left = Math.min(Math.max(target.bounds.x1 * 100, 0), 100);
                        const top = Math.min(Math.max(target.bounds.y1 * 100, 0), 100);
                        const right = Math.min(Math.max(target.bounds.x2 * 100, 0), 100);
                        const bottom = Math.min(Math.max(target.bounds.y2 * 100, 0), 100);
                        return (
                          <div
                            className="absolute rounded-[12px] border-2 border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_6px_rgba(244,63,94,0.12)]"
                            style={{
                              left: `${left}%`,
                              top: `${top}%`,
                              width: `${Math.max(right - left, 2)}%`,
                              height: `${Math.max(bottom - top, 2)}%`,
                            }}
                          />
                        );
                      })()
                    ) : null}
                    {planPreviewAnnotations.labels.map((item, idx) => (
                      <div
                        key={`${item.label}-${idx}`}
                        className="group pointer-events-auto absolute"
                        style={{
                          left: `${Math.min(Math.max(item.x * 100, 0), 100)}%`,
                          top: `${Math.min(Math.max(item.y * 100, 0), 100)}%`,
                          transform: "translate(-50%, -50%)",
                        }}
                      >
                        <div
                          className={`h-2 w-2 rounded-full transition ${
                            item.label === selectedIssueLabel
                              ? "bg-rose-500/80 shadow-[0_0_0_6px_rgba(244,63,94,0.15)]"
                              : "bg-slate-900/30 opacity-0 group-hover:opacity-100"
                          }`}
                        />
                        <div className="pointer-events-none absolute left-1/2 top-0 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 shadow-sm group-hover:block">
                          {item.label}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
                {showInteractive && activeAnnotation && fullscreenHoverPoint ? (
                  <div
                    className="pointer-events-none absolute z-20 min-w-[220px] max-w-[280px] rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg"
                    style={{
                      left: Math.min(Math.max(fullscreenHoverPoint.x + 16, 16), 620),
                      top: Math.min(Math.max(fullscreenHoverPoint.y + 16, 16), 520),
                    }}
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      {activeAnnotation.label}
                    </p>
                    <div className="mt-2 space-y-1">
                      {hoverDetails.length ? (
                        hoverDetails.map((detail) => (
                          <div key={detail.label} className="flex items-center justify-between gap-2">
                            <span className="text-slate-500">{detail.label}</span>
                            <span className="font-semibold text-slate-900">{detail.value}</span>
                          </div>
                        ))
                      ) : (
                        <span className="text-slate-500">No engineering metadata.</span>
                      )}
                    </div>
                  </div>
                ) : null}
                {previewInteraction === "interactive" && showMeasurements ? (
                  <div className="pointer-events-none absolute left-6 top-6 w-[240px] rounded-2xl border border-slate-200/70 bg-white/90 p-3 text-xs text-slate-700 shadow-sm backdrop-blur">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Measurements
                    </p>
                    <div className="mt-2 space-y-1">
                      {measurementOverlayStats
                        .filter((item) => Number(item.value || 0) > 0)
                        .map((item) => (
                          <div key={item.label} className="flex items-center justify-between gap-2">
                            <span>{item.label}</span>
                            <span className="font-semibold">
                              {item.unit === "stalls"
                                ? formatCount(Number(item.value || 0), item.unit)
                                : formatMetric(Number(item.value || 0), item.unit)}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                ) : null}
                {previewInteraction === "interactive" && showCalculations ? (
                  <div className="pointer-events-none absolute bottom-6 left-6 w-[240px] rounded-2xl border border-slate-200/70 bg-white/90 p-3 text-xs text-slate-700 shadow-sm backdrop-blur">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Calculations
                    </p>
                    <div className="mt-2 space-y-1">
                      {calculationOverlayStats
                        .filter((item) => Number(item.value || 0) > 0)
                        .map((item) => (
                          <div key={item.label} className="flex items-center justify-between gap-2">
                            <span>{item.label}</span>
                            <span className="font-semibold">
                              {formatMetric(Number(item.value || 0), item.unit)}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
