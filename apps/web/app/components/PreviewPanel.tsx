"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Maximize2, X } from "lucide-react";

import type {
  Preview3DItem,
  PreviewResponse,
  PreviewReview,
  BuildingPlacement,
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
  previewLabelDensity: "low" | "standard" | "high";
  previewRenderMode: "production" | "engineering" | "debug";
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewInteraction: (value: "static" | "interactive") => void;
  onSetPreviewQuality: (value: "standard" | "high") => void;
  onSetPreviewLabelDensity: (value: "low" | "standard" | "high") => void;
  onSetPreviewRenderMode: (value: "production" | "engineering" | "debug") => void;
  onQueuePreviewRefresh: (reason: string) => void;
  previewRefreshing: boolean;
  previewRefreshNote: string | null;
  preview3DEffectiveItems: Preview3DItem[];
  usingAnnotation3D: boolean;
  hasGradingSurface: boolean;
  placementMode: boolean;
  onPlaceBuilding: (position: { x: number; y: number }) => void;
  onPlaceObject: (id: string, position: { x: number; y: number }) => void;
  buildingPlacements: BuildingPlacement[];
  lotWidth: number;
  lotHeight: number;
  onUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  onSelectBuilding: (id: string | null) => void;
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
  previewLabelDensity,
  previewRenderMode,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onSetPreviewQuality,
  onSetPreviewLabelDensity,
  onSetPreviewRenderMode,
  onQueuePreviewRefresh,
  previewRefreshing,
  previewRefreshNote,
  preview3DEffectiveItems,
  usingAnnotation3D,
  hasGradingSurface,
  placementMode,
  onPlaceBuilding,
  onPlaceObject,
  buildingPlacements,
  lotWidth,
  lotHeight,
  onUpdateBuilding,
  onSelectBuilding,
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
  const issueHighlightBounds = useMemo(() => {
    if (!selectedIssueLabel || !previewLabels.length) return null;
    const target = previewLabels.find(
      (item) =>
        item.bounds &&
        (item.label === selectedIssueLabel || item.label.includes(selectedIssueLabel)),
    );
    return target?.bounds ?? null;
  }, [previewLabels, selectedIssueLabel]);
  const [hoveredAnnotation, setHoveredAnnotation] = useState<(typeof previewLabels)[number] | null>(null);
  const [pinnedAnnotation, setPinnedAnnotation] = useState<(typeof previewLabels)[number] | null>(null);
  const [hoverPoint, setHoverPoint] = useState<{ x: number; y: number } | null>(null);
  const [fullscreenHoverPoint, setFullscreenHoverPoint] = useState<{ x: number; y: number } | null>(null);
  const [previewImageBounds, setPreviewImageBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [fullscreenImageBounds, setFullscreenImageBounds] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const [draggingBuildingId, setDraggingBuildingId] = useState<string | null>(null);
  const [draggingMode, setDraggingMode] = useState<"move" | "resize" | "rotate" | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const previewRef = useRef<HTMLDivElement | null>(null);
  const fullscreenRef = useRef<HTMLDivElement | null>(null);
  const previewImageRef = useRef<HTMLImageElement | null>(null);
  const fullscreenImageRef = useRef<HTMLImageElement | null>(null);
  const activeAnnotation = pinnedAnnotation ?? hoveredAnnotation;
  const hasInteractiveLabels = previewLabels.length > 0;
  const showInteractive = previewInteraction === "interactive";
  const previewModeDescription =
    previewRenderMode === "debug"
      ? "Debug shows helper geometry, routing guides, and audit details."
      : previewRenderMode === "engineering"
        ? "Engineering shows final geometry with overlays like grades, labels, and system annotations."
        : "Production shows final, client-facing geometry only.";
  const legendPalette = {
    building: "#0f172a",
    parking: "#cbd5e1",
    road: "#475569",
    drainage: "#1d4ed8",
    utilities: "#7c3aed",
  } as const;
  const activeHighlightBounds = activeAnnotation?.bounds ?? null;
  const clampPercent = (value: number) => Math.min(Math.max(value * 100, 0), 100);
  const buildBoundsStyle = (bounds: { x1: number; y1: number; x2: number; y2: number }) => {
    const left = clampPercent(bounds.x1);
    const right = clampPercent(bounds.x2);
    const top = clampPercent(bounds.y1);
    const bottom = clampPercent(bounds.y2);
    return {
      left: `${left}%`,
      top: `${top}%`,
      width: `${Math.max(right - left, 1)}%`,
      height: `${Math.max(bottom - top, 1)}%`,
    };
  };
  const updateImageBounds = useCallback(
    (
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageRef: React.RefObject<HTMLImageElement | null>,
      setter: React.Dispatch<React.SetStateAction<{ left: number; top: number; width: number; height: number } | null>>,
    ) => {
      if (!containerRef.current || !imageRef.current) {
        setter(null);
        return;
      }
      const containerRect = containerRef.current.getBoundingClientRect();
      const imageRect = imageRef.current.getBoundingClientRect();
      const width = Math.max(imageRect.width, 1);
      const height = Math.max(imageRect.height, 1);
      setter({
        left: imageRect.left - containerRect.left,
        top: imageRect.top - containerRect.top,
        width,
        height,
      });
    },
    [],
  );
  const resolveHover = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageBounds: { left: number; top: number; width: number; height: number } | null,
      setPoint: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>,
    ) => {
      if (!showInteractive || !containerRef.current || !hasInteractiveLabels) {
        setHoveredAnnotation(null);
        setPoint(null);
        return;
      }
      const rect = containerRef.current.getBoundingClientRect();
      const bounds = imageBounds || { left: 0, top: 0, width: rect.width, height: rect.height };
      const relativeX = (event.clientX - rect.left - bounds.left) / Math.max(bounds.width, 1);
      const relativeY = (event.clientY - rect.top - bounds.top) / Math.max(bounds.height, 1);
      if (relativeX < 0 || relativeX > 1 || relativeY < 0 || relativeY > 1) {
        setHoveredAnnotation(null);
        setPoint(null);
        return;
      }
      const matches = previewLabels
        .filter((label) => {
          const bounds = label.bounds;
          if (!bounds) return false;
          return (
            relativeX >= bounds.x1 &&
            relativeX <= bounds.x2 &&
            relativeY >= bounds.y1 &&
            relativeY <= bounds.y2
          );
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

  const resolvePlacement = useCallback(
    (
      event: React.MouseEvent<HTMLDivElement>,
      containerRef: React.RefObject<HTMLDivElement | null>,
      imageBounds: { left: number; top: number; width: number; height: number } | null,
    ) => {
      if (!placementMode || !containerRef.current) {
        return;
      }
      const rect = containerRef.current.getBoundingClientRect();
      const bounds = imageBounds || { left: 0, top: 0, width: rect.width, height: rect.height };
      const relativeX = (event.clientX - rect.left - bounds.left) / Math.max(bounds.width, 1);
      const relativeY = (event.clientY - rect.top - bounds.top) / Math.max(bounds.height, 1);
      if (relativeX < 0 || relativeX > 1 || relativeY < 0 || relativeY > 1) {
        return;
      }
      onPlaceBuilding({ x: relativeX, y: relativeY });
    },
    [onPlaceBuilding, placementMode],
  );

  const clampValue = (value: number, min: number, max: number) =>
    Math.min(Math.max(value, min), max);

  const snapValue = (value: number, step: number) => {
    if (!step) return value;
    return Math.round(value / step) * step;
  };

  const updateDraggedBuilding = useCallback(
    (event: React.MouseEvent<HTMLDivElement>, bounds: { left: number; top: number; width: number; height: number }) => {
      if (!draggingBuildingId || !placementMode || !draggingMode) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const localX = event.clientX - rect.left - bounds.left;
      const localY = event.clientY - rect.top - bounds.top;
      const target = buildingPlacements.find((item) => item.id === draggingBuildingId);
      if (!target) return;
      if (draggingMode === "move") {
        const x = snapValue(
          clampValue(((localX - dragOffset.x) / Math.max(bounds.width, 1)) * lotWidth, 0, Math.max(lotWidth - target.w, 0)),
          5,
        );
        const y = snapValue(
          clampValue(((localY - dragOffset.y) / Math.max(bounds.height, 1)) * lotHeight, 0, Math.max(lotHeight - target.d, 0)),
          5,
        );
        onUpdateBuilding(draggingBuildingId, { x, y, placed: true });
        return;
      }
      if (draggingMode === "resize") {
        const rawW = clampValue((localX / Math.max(bounds.width, 1)) * lotWidth, 10, lotWidth);
        const rawD = clampValue((localY / Math.max(bounds.height, 1)) * lotHeight, 10, lotHeight);
        const nextW = Math.max(10, snapValue(rawW - (target.x ?? 0), 5));
        const nextD = Math.max(10, snapValue(rawD - (target.y ?? 0), 5));
        onUpdateBuilding(draggingBuildingId, { w: nextW, d: nextD });
        return;
      }
      if (draggingMode === "rotate") {
        const centerX = bounds.left + ((target.x ?? 0) + target.w / 2) / Math.max(lotWidth, 1) * bounds.width;
        const centerY = bounds.top + ((target.y ?? 0) + target.d / 2) / Math.max(lotHeight, 1) * bounds.height;
        const angle = Math.atan2(localY + bounds.top - centerY, localX + bounds.left - centerX);
        const deg = (angle * 180) / Math.PI;
        const normalized = (deg + 360) % 360;
        const snapped = snapValue(normalized, 15);
        onUpdateBuilding(draggingBuildingId, { rotation: snapped });
      }
    },
    [
      buildingPlacements,
      dragOffset.x,
      dragOffset.y,
      draggingBuildingId,
      draggingMode,
      lotHeight,
      lotWidth,
      onUpdateBuilding,
      placementMode,
    ],
  );

  const handleBuildingMouseDown = useCallback(
    (
      event: React.MouseEvent<HTMLElement>,
      building: BuildingPlacement,
      mode: "move" | "resize" | "rotate" = "move",
    ) => {
      if (!placementMode) return;
      event.preventDefault();
      event.stopPropagation();
      setDraggingBuildingId(building.id);
      setDraggingMode(mode);
      onSelectBuilding(building.id);
      const rect = event.currentTarget.getBoundingClientRect();
      setDragOffset({ x: event.clientX - rect.left, y: event.clientY - rect.top });
    },
    [onSelectBuilding, placementMode],
  );

  const formatHoverValue = (value: number | null | undefined, suffix: string) => {
    if (value === null || value === undefined || Number.isNaN(value)) return null;
    return `${value.toFixed(2)}${suffix}`;
  };
  const hoverDetails = useMemo(() => {
    if (!activeAnnotation?.meta) return [];
    const meta = activeAnnotation.meta;
    const sourceLabel = meta.preview_role
      ? meta.preview_role === "final"
        ? "Final geometry"
        : meta.preview_role === "overlay"
          ? "Overlay"
          : "Debug"
      : "Unknown";
    const inferredLabel = meta.inferred ? "Inferred" : "";
    const entries = [
      { label: "Entity ID", value: meta.entity_id },
      { label: "System", value: meta.system },
      { label: "Layer", value: activeAnnotation.layer },
      { label: "Type", value: meta.entity_type },
      { label: "Source", value: inferredLabel ? `${sourceLabel} (${inferredLabel})` : sourceLabel },
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
  const debugHoverDetails = useMemo(() => {
    if (!activeAnnotation?.meta || previewRenderMode !== "debug") return [];
    const meta = activeAnnotation.meta;
    const entries = [
      { label: "Entity ID", value: meta.entity_id },
      { label: "Source stage", value: meta.source_stage },
      { label: "Source type", value: meta.source_type },
      { label: "Preview role", value: meta.preview_role },
      { label: "Inferred", value: meta.inferred ? "Yes" : "No" },
    ];
    return entries.filter((entry) => entry.value);
  }, [activeAnnotation, previewRenderMode]);

  useEffect(() => {
    if (!planPreviewUrl) return;
    const handleUpdate = () => updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds);
    handleUpdate();
    if (!previewRef.current) return;
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleUpdate) : null;
    if (observer) observer.observe(previewRef.current);
    window.addEventListener("resize", handleUpdate);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener("resize", handleUpdate);
    };
  }, [planPreviewUrl, previewMode, updateImageBounds]);

  useEffect(() => {
    if (!previewFullscreenOpen || !planPreviewUrl) return;
    const handleUpdate = () => updateImageBounds(fullscreenRef, fullscreenImageRef, setFullscreenImageBounds);
    handleUpdate();
    if (!fullscreenRef.current) return;
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleUpdate) : null;
    if (observer) observer.observe(fullscreenRef.current);
    window.addEventListener("resize", handleUpdate);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener("resize", handleUpdate);
    };
  }, [planPreviewUrl, previewFullscreenOpen, updateImageBounds]);
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
                {previewRenderMode === "debug" && previewAudit.stage_diagnostics ? (
                  <div className="mt-3 border-t border-slate-200 pt-3 text-[11px] text-slate-600">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Stage Diagnostics
                    </p>
                    {Object.values(previewAudit.stage_diagnostics).map((entry) => {
                      if (!entry || typeof entry !== "object") return null;
                      const stage = String((entry as any).stage || "");
                      const status = String((entry as any).status || "");
                      const message = String((entry as any).message || "");
                      const generated = (entry as any).generated || {};
                      const rendered = (entry as any).rendered || {};
                      return (
                        <div key={stage} className="mt-2 rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <div className="flex items-center justify-between text-[11px] font-semibold text-slate-700">
                            <span className="uppercase tracking-[0.14em] text-slate-500">{stage || "stage"}</span>
                            <span>{status || "pending"}</span>
                          </div>
                          {message ? <p className="mt-1 text-[10px] text-slate-500">{message}</p> : null}
                          <p className="mt-1 text-[10px] text-slate-500">
                            Generated: {formatCount(generated.total ?? 0)} · Final: {formatCount(generated.final ?? 0)} · Overlay:{" "}
                            {formatCount(generated.overlay ?? 0)}
                          </p>
                          <p className="mt-1 text-[10px] text-slate-500">
                            Rendered: {formatCount(rendered.total ?? 0)} · Final: {formatCount(rendered.final ?? 0)} · Overlay:{" "}
                            {formatCount(rendered.overlay ?? 0)}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                ) : null}
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
          <div className="rounded-[28px] border border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
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
              <span>Labels</span>
              {(["low", "standard", "high"] as const).map((density) => (
                <button
                  key={density}
                  type="button"
                  onClick={() => {
                    if (previewLabelDensity === density) return;
                    onQueuePreviewRefresh("Updating label density...");
                    onSetPreviewLabelDensity(density);
                  }}
                  className={`rounded-full border px-2.5 py-1 ${
                    previewLabelDensity === density
                      ? "border-slate-900 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-600"
                  }`}
                >
                  {density === "standard" ? "Standard" : density.charAt(0).toUpperCase() + density.slice(1)}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              <span>Render Mode</span>
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
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
            <span className="font-semibold text-slate-900">Mode:</span>
            <span>{previewModeDescription}</span>
            <span className="font-semibold text-slate-900">Quality:</span>
            <span>{previewQuality === "high" ? "High" : "Standard"}</span>
            <span className="font-semibold text-slate-900">Labels:</span>
            <span>
              {previewLabelDensity === "standard"
                ? "Standard"
                : previewLabelDensity.charAt(0).toUpperCase() + previewLabelDensity.slice(1)}
            </span>
            <span className="font-semibold text-slate-900">Interactive:</span>
            <span>{previewInteraction === "interactive" ? "Hover enabled" : "Static"}</span>
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
                {!hasGradingSurface ? (
                  <div
                    className={`pointer-events-none absolute right-4 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm ${
                      previewRenderMode !== "production" || usingAnnotation3D ? "top-14" : "top-4"
                    }`}
                  >
                    Grading surface missing
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
              <div className="relative flex min-h-[640px] items-center justify-center overflow-hidden rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={planPreviewUrl}
                  alt="Generated plan preview"
                  className="max-h-[640px] w-full origin-center -skew-y-1 scale-[0.98] object-contain"
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
              className={`relative flex min-h-[640px] items-center justify-center rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)] ${
                previewInteraction === "interactive" ? "cursor-crosshair" : "cursor-default"
              }`}
              onDragOver={(event) => {
                event.preventDefault();
              }}
              onDrop={(event) => {
                event.preventDefault();
                const payload = event.dataTransfer?.getData("civora-object-id");
                if (!payload) return;
                onPlaceObject(payload, {
                  x: Math.min(Math.max((event.clientX - (previewImageBounds?.left ?? 0)) / Math.max(previewImageBounds?.width ?? 1, 1), 0), 1),
                  y: Math.min(Math.max((event.clientY - (previewImageBounds?.top ?? 0)) / Math.max(previewImageBounds?.height ?? 1, 1), 0), 1),
                });
              }}
              onMouseMove={(event) => {
                if (previewImageBounds) {
                  updateDraggedBuilding(event, previewImageBounds);
                }
                resolveHover(event, previewRef, previewImageBounds, setHoverPoint);
              }}
              onMouseLeave={() => {
                setHoveredAnnotation(null);
                setHoverPoint(null);
                setDraggingBuildingId(null);
                setDraggingMode(null);
              }}
              onMouseUp={() => {
                setDraggingBuildingId(null);
                setDraggingMode(null);
              }}
              onClick={(event) => {
                if (placementMode) {
                  resolvePlacement(event, previewRef, previewImageBounds);
                  return;
                }
                if (!showInteractive || !hoveredAnnotation) return;
                setPinnedAnnotation((prev) =>
                  prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
                );
              }}
            >
              <div className="relative flex h-full w-full items-center justify-center overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  ref={previewImageRef}
                  src={planPreviewUrl}
                  alt="Generated plan preview"
                  className={`max-h-[640px] w-full object-contain ${
                    previewInteraction === "interactive" ? "cursor-crosshair" : "cursor-default"
                  }`}
                  onLoad={() => updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds)}
                  onClick={onOpenFullscreen}
                />
                {previewImageBounds && previewMode === "2d" ? (
                  <div
                    className="pointer-events-none absolute"
                    style={{
                      left: previewImageBounds.left,
                      top: previewImageBounds.top,
                      width: previewImageBounds.width,
                      height: previewImageBounds.height,
                    }}
                  >
                    {lotWidth > 0 && lotHeight > 0 ? (
                      <div className="absolute inset-0 rounded-[16px] border-2 border-dashed border-slate-300/70" />
                    ) : null}
                    {buildingPlacements
                      .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                      .map((item) => {
                        const left = ((item.x || 0) / Math.max(lotWidth, 1)) * 100;
                        const top = ((item.y || 0) / Math.max(lotHeight, 1)) * 100;
                        const rotated = (item.rotation ?? 0) % 180 !== 0;
                        const displayW = rotated ? item.d : item.w;
                        const displayD = rotated ? item.w : item.d;
                        const width = (displayW / Math.max(lotWidth, 1)) * 100;
                        const height = (displayD / Math.max(lotHeight, 1)) * 100;
                        const rotation = item.rotation ?? 0;
                        const borderColor =
                          item.type === "basin"
                            ? "border-emerald-500"
                            : item.type === "entrance"
                              ? "border-amber-500"
                              : "border-slate-900/70";
                        return (
                          <div
                            key={item.id}
                            className="pointer-events-auto absolute"
                            style={{
                              left: `${left}%`,
                              top: `${top}%`,
                              width: `${width}%`,
                              height: `${height}%`,
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: placementMode ? "move" : "default",
                            }}
                            onMouseDown={(event) => handleBuildingMouseDown(event, item, "move")}
                            onClick={(event) => {
                              if (!placementMode) return;
                              event.stopPropagation();
                              onSelectBuilding(item.id);
                            }}
                          >
                            <div
                              className={`h-full w-full rounded-[8px] border-2 bg-slate-900/10 transition ${borderColor}`}
                            />
                            <button
                              type="button"
                              className="absolute -right-3 -top-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                              onMouseDown={(event) => handleBuildingMouseDown(event, item, "rotate")}
                            >
                              R
                            </button>
                            <button
                              type="button"
                              className="absolute -right-3 -bottom-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                              onMouseDown={(event) => handleBuildingMouseDown(event, item, "resize")}
                            >
                              Z
                            </button>
                            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
                              Snap 5ft
                            </div>
                            <div className="absolute -top-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-600 shadow">
                              {item.label}
                            </div>
                          </div>
                        );
                      })}
                  </div>
                ) : null}
                {planPreviewAnnotations?.labels?.length && previewImageBounds ? (
                  <div
                    className="pointer-events-none absolute"
                    style={{
                      left: previewImageBounds.left,
                      top: previewImageBounds.top,
                      width: previewImageBounds.width,
                      height: previewImageBounds.height,
                    }}
                  >
                    {activeHighlightBounds ? (
                      <div
                        className="absolute rounded-[14px] border-2 border-sky-400/90 bg-sky-400/10 shadow-[0_0_0_6px_rgba(56,189,248,0.18)]"
                        style={buildBoundsStyle(activeHighlightBounds)}
                      />
                    ) : null}
                    {issueHighlightBounds ? (
                      <div
                        className="absolute rounded-[12px] border-2 border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_6px_rgba(244,63,94,0.12)]"
                        style={buildBoundsStyle(issueHighlightBounds)}
                      />
                    ) : null}
                    {previewInteraction === "interactive"
                      ? planPreviewAnnotations.labels.map((item, idx) => (
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
                        ))
                      : null}
                  </div>
                ) : null}
              </div>
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
                      <div className="space-y-1 text-slate-500">
                        <div className="flex items-center justify-between gap-2">
                          <span>Layer</span>
                          <span className="font-semibold text-slate-900">
                            {activeAnnotation.layer || "Unknown"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Type</span>
                          <span className="font-semibold text-slate-900">
                            {activeAnnotation.meta?.entity_type || "Shape"}
                          </span>
                        </div>
                      </div>
                    )}
                    {debugHoverDetails.length ? (
                      <div className="mt-3 border-t border-slate-100 pt-2 text-[11px]">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          Debug
                        </p>
                        <div className="mt-2 space-y-1">
                          {debugHoverDetails.map((detail) => (
                            <div key={detail.label} className="flex items-center justify-between gap-2">
                              <span className="text-slate-500">{detail.label}</span>
                              <span className="font-semibold text-slate-900">{detail.value}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
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
              {previewInteraction === "interactive" && !planPreviewAnnotations?.labels?.length ? (
                <div className="pointer-events-none absolute right-6 top-6 hidden rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white lg:block">
                  Hover labels pending
                </div>
              ) : null}
              {placementMode ? (
                <div className="pointer-events-none absolute left-6 top-6 hidden rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-800 lg:block">
                  Placement mode: click to drop the selected object
                </div>
              ) : previewInteraction === "interactive" ? (
                <div
                  className={`pointer-events-none absolute left-6 hidden rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white lg:block ${
                    previewRenderMode !== "production" ? "top-16" : "top-6"
                  }`}
                >
                  Hover geometry for details
                </div>
              ) : null}
              <div className="pointer-events-none absolute bottom-6 right-6 hidden rounded-2xl border border-white/40 bg-white/85 px-3 py-2 text-[11px] text-slate-700 shadow-sm backdrop-blur lg:block">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Legend
                </p>
                <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.building }} />
                    <span>Buildings</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.parking }} />
                    <span>Parking</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.road }} />
                    <span>Roads</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.drainage }} />
                    <span>Drainage</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: legendPalette.utilities }} />
                    <span>Utilities</span>
                  </div>
                </div>
              </div>
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
                onDragOver={(event) => {
                  event.preventDefault();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  const payload = event.dataTransfer?.getData("civora-object-id");
                  if (!payload) return;
                  onPlaceObject(payload, {
                    x: Math.min(Math.max((event.clientX - (fullscreenImageBounds?.left ?? 0)) / Math.max(fullscreenImageBounds?.width ?? 1, 1), 0), 1),
                    y: Math.min(Math.max((event.clientY - (fullscreenImageBounds?.top ?? 0)) / Math.max(fullscreenImageBounds?.height ?? 1, 1), 0), 1),
                  });
                }}
                onMouseMove={(event) => {
                  if (fullscreenImageBounds) {
                    updateDraggedBuilding(event, fullscreenImageBounds);
                  }
                  resolveHover(event, fullscreenRef, fullscreenImageBounds, setFullscreenHoverPoint);
                }}
                onMouseLeave={() => {
                  setHoveredAnnotation(null);
                  setFullscreenHoverPoint(null);
                  setDraggingBuildingId(null);
                  setDraggingMode(null);
                }}
                onMouseUp={() => {
                  setDraggingBuildingId(null);
                  setDraggingMode(null);
                }}
                onClick={(event) => {
                  if (placementMode) {
                    resolvePlacement(event, fullscreenRef, fullscreenImageBounds);
                    return;
                  }
                  if (!showInteractive || !hoveredAnnotation) return;
                  setPinnedAnnotation((prev) =>
                    prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
                  );
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  ref={fullscreenImageRef}
                  src={planPreviewUrl}
                  alt="Generated plan preview fullscreen"
                  className="max-h-full w-full rounded-[20px] bg-white object-contain shadow-2xl"
                  onLoad={() => updateImageBounds(fullscreenRef, fullscreenImageRef, setFullscreenImageBounds)}
                />
                {previewInteraction === "interactive" &&
                !planPreviewAnnotations?.labels?.length ? (
                  <div className="pointer-events-none absolute right-6 top-6 rounded-2xl border border-white/20 bg-slate-900/80 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white">
                    No hover labels yet. Refresh the preview to generate them.
                  </div>
                ) : null}
                {planPreviewAnnotations?.labels?.length && fullscreenImageBounds ? (
                  <div
                    className="pointer-events-none absolute"
                    style={{
                      left: fullscreenImageBounds.left,
                      top: fullscreenImageBounds.top,
                      width: fullscreenImageBounds.width,
                      height: fullscreenImageBounds.height,
                    }}
                  >
                    {lotWidth > 0 && lotHeight > 0 ? (
                      <div className="absolute inset-0 rounded-[16px] border-2 border-dashed border-slate-300/70" />
                    ) : null}
                    {activeHighlightBounds ? (
                      <div
                        className="absolute rounded-[14px] border-2 border-sky-400/90 bg-sky-400/10 shadow-[0_0_0_6px_rgba(56,189,248,0.18)]"
                        style={buildBoundsStyle(activeHighlightBounds)}
                      />
                    ) : null}
                    {issueHighlightBounds ? (
                      <div
                        className="absolute rounded-[12px] border-2 border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_6px_rgba(244,63,94,0.12)]"
                        style={buildBoundsStyle(issueHighlightBounds)}
                      />
                    ) : null}
                    {previewInteraction === "interactive"
                      ? planPreviewAnnotations.labels.map((item, idx) => (
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
                        ))
                      : null}
                    {buildingPlacements
                      .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                      .map((item) => {
                        const left = ((item.x || 0) / Math.max(lotWidth, 1)) * 100;
                        const top = ((item.y || 0) / Math.max(lotHeight, 1)) * 100;
                        const rotated = (item.rotation ?? 0) % 180 !== 0;
                        const displayW = rotated ? item.d : item.w;
                        const displayD = rotated ? item.w : item.d;
                        const width = (displayW / Math.max(lotWidth, 1)) * 100;
                        const height = (displayD / Math.max(lotHeight, 1)) * 100;
                        const rotation = item.rotation ?? 0;
                        const borderColor =
                          item.type === "basin"
                            ? "border-emerald-500"
                            : item.type === "entrance"
                              ? "border-amber-500"
                              : "border-slate-900/70";
                        return (
                          <div
                            key={item.id}
                            className="pointer-events-auto absolute"
                            style={{
                              left: `${left}%`,
                              top: `${top}%`,
                              width: `${width}%`,
                              height: `${height}%`,
                              transform: `rotate(${rotation}deg)`,
                              transformOrigin: "center",
                              cursor: placementMode ? "move" : "default",
                            }}
                            onMouseDown={(event) => handleBuildingMouseDown(event, item, "move")}
                            onClick={(event) => {
                              if (!placementMode) return;
                              event.stopPropagation();
                              onSelectBuilding(item.id);
                            }}
                          >
                            <div className={`h-full w-full rounded-[8px] border-2 bg-slate-900/10 transition ${borderColor}`} />
                            <button
                              type="button"
                              className="absolute -right-3 -top-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                              onMouseDown={(event) => handleBuildingMouseDown(event, item, "rotate")}
                            >
                              R
                            </button>
                            <button
                              type="button"
                              className="absolute -right-3 -bottom-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
                              onMouseDown={(event) => handleBuildingMouseDown(event, item, "resize")}
                            >
                              Z
                            </button>
                            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
                              Snap 5ft
                            </div>
                          </div>
                        );
                      })}
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
                      <div className="space-y-1 text-slate-500">
                        <div className="flex items-center justify-between gap-2">
                          <span>Layer</span>
                          <span className="font-semibold text-slate-900">
                            {activeAnnotation.layer || "Unknown"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span>Type</span>
                          <span className="font-semibold text-slate-900">
                            {activeAnnotation.meta?.entity_type || "Shape"}
                          </span>
                        </div>
                      </div>
                    )}
                    {debugHoverDetails.length ? (
                      <div className="mt-3 border-t border-slate-100 pt-2 text-[11px]">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                          Debug
                        </p>
                        <div className="mt-2 space-y-1">
                          {debugHoverDetails.map((detail) => (
                            <div key={detail.label} className="flex items-center justify-between gap-2">
                              <span className="text-slate-500">{detail.label}</span>
                              <span className="font-semibold text-slate-900">{detail.value}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
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
