"use client";

import { useEffect } from "react";
import { Eye, EyeOff, Layers3, Lock, MousePointer2, RefreshCw, RotateCcw, Unlock, X } from "lucide-react";

import type { CoordinateMode } from "../utils/geometryTransforms";
import { coordinateModeLabel } from "../utils/geometryTransforms";
import type { DrawMode } from "../utils/cadToolTypes";
import type { PreviewSemanticLayer } from "../utils/previewSemanticLayers";
import {
  PREVIEW_SEMANTIC_LAYER_LABELS,
  PRIMARY_PREVIEW_SEMANTIC_LAYERS,
} from "../utils/previewSemanticLayers";
import type { PreviewSourceLayerVisibility } from "../utils/previewSourceLayers";
import { PreviewQualityToggle } from "./PreviewQualityToggle";
import { loadPreview3DCanvas } from "./preview3DLoader";

type PreviewCanvasHeaderControlsProps = {
  previewMode: "2d" | "3d";
  previewQuality: "standard" | "high";
  coordinateMode: CoordinateMode;
  canUse3D: boolean;
  mapAvailable: boolean;
  mapOverlayEnabled: boolean;
  mapLocked: boolean;
  showMap: boolean;
  allowEdits: boolean;
  drawMode: DrawMode;
  siteLocked?: boolean;
  showDrawTools?: boolean;
  isHighQuality: boolean;
  aiRealismEnabled: boolean;
  useLightHighQuality: boolean;
  busy: boolean;
  analysisHighlight: unknown;
  semanticLayerVisibility: Partial<Record<PreviewSemanticLayer, boolean>>;
  sourceLayerVisibility: PreviewSourceLayerVisibility;
  sourceLayerCounts: { detectedExisting: number; proposedDesign: number };
  onSetPreviewQuality: (value: "standard" | "high") => void;
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetAiVisualizationOff: () => void;
  onSetAiVisualizationOn: () => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  onSetMapOverlayEnabled: (updater: (value: boolean) => boolean) => void;
  onSetMapLocked: (updater: (value: boolean) => boolean) => void;
  onActivateDrawTool: (mode: DrawMode, blockedMessage?: string) => void;
  onPushCadCommandFeedback: (command: string, status: "applied" | "blocked" | "info", message: string) => void;
  onUnlockSite?: () => void;
  onClearDraftGeometry: () => void;
  onSetDrawMode: (mode: DrawMode) => void;
  onSetFocusTransform: (value: null) => void;
  onResetView?: () => void;
  onRefreshPreview: () => void;
  onClearHighlights?: () => void;
  onToggleSemanticLayer: (layer: PreviewSemanticLayer) => void;
  onShowAllSemanticLayers: () => void;
  onToggleSourceLayer: (layer: keyof PreviewSourceLayerVisibility) => void;
};

export function PreviewCanvasHeaderControls({
  previewMode,
  previewQuality,
  coordinateMode,
  canUse3D,
  mapAvailable,
  mapOverlayEnabled,
  mapLocked,
  showMap,
  allowEdits,
  drawMode,
  siteLocked,
  showDrawTools = true,
  isHighQuality,
  aiRealismEnabled,
  useLightHighQuality,
  busy,
  analysisHighlight,
  semanticLayerVisibility,
  sourceLayerVisibility,
  sourceLayerCounts,
  onSetPreviewQuality,
  onSetPreviewMode,
  onSetAiVisualizationOff,
  onSetAiVisualizationOn,
  onSetPreviewInteraction,
  onSetMapOverlayEnabled,
  onSetMapLocked,
  onActivateDrawTool,
  onPushCadCommandFeedback,
  onUnlockSite,
  onClearDraftGeometry,
  onSetDrawMode,
  onSetFocusTransform,
  onResetView,
  onRefreshPreview,
  onClearHighlights,
  onToggleSemanticLayer,
  onShowAllSemanticLayers,
  onToggleSourceLayer,
}: PreviewCanvasHeaderControlsProps) {
  useEffect(() => {
    if (!canUse3D) return;
    const preloadTimer = window.setTimeout(() => {
      void loadPreview3DCanvas();
    }, 1500);
    return () => window.clearTimeout(preloadTimer);
  }, [canUse3D]);

  const modeLabel = previewMode === "3d"
    ? "3D Model"
    : aiRealismEnabled && isHighQuality
      ? "Presentation"
      : previewQuality === "high"
        ? "Plan Sheet"
        : "Draft";

  return (
    <div className="relative z-[240] grid min-w-0 gap-2 px-3 py-2.5">
      <div className="pointer-events-auto relative z-[120] flex min-w-0 max-w-full flex-wrap items-center gap-1.5">
        <span className="inline-flex items-center px-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          Canvas
        </span>
        <span
          data-testid="site-status"
          className={`inline-flex items-center rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] ${
            siteLocked
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-amber-200 bg-amber-50 text-amber-700"
          }`}
        >
          {siteLocked ? "Site Locked" : "Site Editable"}
        </span>
        <span className="mr-1 inline-flex min-w-0 max-w-full items-center truncate px-1 text-[11px] font-medium text-slate-500">
          {modeLabel} · {previewMode.toUpperCase()} · {coordinateModeLabel(coordinateMode)}
        </span>
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <PreviewQualityToggle
            value={previewQuality}
            onChange={onSetPreviewQuality}
            standardTestId="preview-quality-standard"
            highTestId="preview-quality-high"
            standardLabel="Draft"
            highLabel="Plan Sheet"
          />
          <button
            type="button"
            data-testid="preview-mode-2d"
            onClick={() => onSetPreviewMode("2d")}
            className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
              previewMode === "2d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            2D
          </button>
          <button
            type="button"
            data-testid="preview-mode-3d"
            onPointerEnter={() => {
              if (canUse3D) void loadPreview3DCanvas();
            }}
            onFocus={() => {
              if (canUse3D) void loadPreview3DCanvas();
            }}
            onClick={() => {
              if (!canUse3D) return;
              onSetPreviewMode("3d");
            }}
            className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
              previewMode === "3d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
            }`}
            disabled={!canUse3D}
          >
            3D
          </button>
          <button
            type="button"
            data-testid="preview-inner-map-toggle"
            onClick={() => onSetMapOverlayEnabled((value) => !value)}
            disabled={!mapAvailable}
            title={mapAvailable ? "Toggle satellite/map context" : "Map context needs an applied geocoded address"}
            className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
              mapOverlayEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
            } disabled:cursor-not-allowed disabled:opacity-45`}
          >
            Map {mapOverlayEnabled ? "On" : "Off"}
          </button>
          <button
            type="button"
            data-testid="preview-interaction-edit"
            aria-label="Select and edit objects"
            aria-pressed={allowEdits && drawMode === "select"}
            title="Exit the active drawing tool and select objects"
            onClick={() => {
              if (aiRealismEnabled) onSetAiVisualizationOff();
              onActivateDrawTool("select");
            }}
            className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
              allowEdits && drawMode === "select" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            <MousePointer2 className="mr-1.5 h-3.5 w-3.5" />
            Select
          </button>
          {isHighQuality ? (
            <div
              data-testid="ai-realism-toggle"
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white p-0.5"
              aria-label="AI Visualization toggle"
            >
              <span className="px-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
                View
              </span>
              <button
                type="button"
                data-testid="ai-realism-off"
                onClick={onSetAiVisualizationOff}
                aria-pressed={!aiRealismEnabled}
                className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                  !aiRealismEnabled
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Plan
              </button>
              <button
                type="button"
                data-testid="ai-realism-on"
                onClick={() => {
                  if (drawMode !== "select") {
                    onPushCadCommandFeedback(
                      "VISUAL",
                      "info",
                      "Finish or cancel the active drawing before opening Visual view.",
                    );
                    return;
                  }
                  if (mapAvailable) onSetMapOverlayEnabled(() => true);
                  onSetAiVisualizationOn();
                }}
                aria-pressed={aiRealismEnabled}
                className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                  aiRealismEnabled
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Visual
              </button>
            </div>
          ) : null}
          {showDrawTools && previewMode === "2d" ? (
            <button
              type="button"
              data-testid="draw-site-boundary-canvas"
              aria-pressed={drawMode === "site"}
              title={siteLocked ? "Site is locked. Use Change Site before drawing a new boundary." : "Draw the site boundary"}
              onClick={() => {
                if (siteLocked) {
                  onPushCadCommandFeedback(
                    "SITE",
                    "blocked",
                    "SITE boundary is locked. Use Change Site before drawing a replacement boundary.",
                  );
                  return;
                }
                onActivateDrawTool("site");
              }}
              className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
                drawMode === "site"
                  ? "border-slate-900 bg-slate-950 text-white"
                  : siteLocked
                    ? "border-slate-200 bg-white text-slate-600"
                    : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              Draw Site Boundary
            </button>
          ) : null}
          {showDrawTools && previewMode === "2d" && siteLocked && onUnlockSite ? (
            <button
              type="button"
              data-testid="change-site-boundary-canvas"
              aria-label="Change Site Boundary"
              onClick={() => {
                onUnlockSite();
                onClearDraftGeometry();
                onSetDrawMode("select");
                onSetPreviewInteraction("edit");
              }}
              className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600"
            >
              Change Site
            </button>
          ) : null}
        </div>
        <details
          data-testid="preview-layer-menu"
          className="group pointer-events-auto static z-[210]"
        >
          <summary className="flex h-8 cursor-pointer list-none items-center gap-2 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600 shadow-sm marker:hidden hover:bg-slate-50">
            <Layers3 className="h-3.5 w-3.5" />
            Layers
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
              {(sourceLayerVisibility.detectedExisting ? 1 : 0) + (sourceLayerVisibility.proposedDesign ? 1 : 0)}/2
            </span>
          </summary>
          <div
            data-testid="preview-semantic-layer-controls"
            className="absolute right-3 top-[calc(100%+0.4rem)] z-[220] w-[min(22rem,calc(100%-1.5rem))] rounded-xl border border-slate-200 bg-white/96 p-3 text-slate-700 shadow-[0_22px_70px_-38px_rgba(15,23,42,0.65)] backdrop-blur-xl"
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">View layers</p>
            <p className="mt-1 text-xs font-medium text-slate-600" data-testid="preview-layer-visibility-summary" aria-live="polite">
              Existing context is {sourceLayerVisibility.detectedExisting ? "shown" : "hidden"}; proposed design is {sourceLayerVisibility.proposedDesign ? "shown" : "hidden"}.
            </p>
            <div className="mt-2 space-y-1.5">
              <button
                type="button"
                data-testid="preview-source-layer-existing"
                aria-pressed={sourceLayerVisibility.detectedExisting}
                onClick={() => onToggleSourceLayer("detectedExisting")}
                className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left"
              >
                <span>
                  <span className="block text-xs font-semibold text-slate-800">Detected existing context</span>
                  <span className="block text-[10px] text-slate-500">{sourceLayerCounts.detectedExisting} source object(s)</span>
                </span>
                <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
                  {sourceLayerVisibility.detectedExisting ? "Shown" : "Hidden"}
                  {sourceLayerVisibility.detectedExisting ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4 text-slate-400" />}
                </span>
              </button>
              {sourceLayerVisibility.detectedExisting ? (
                <div className="grid grid-cols-4 gap-1" data-testid="preview-existing-sublayers">
                  {([
                    ["detectedBuildings", "Buildings"],
                    ["detectedRoads", "Roads"],
                    ["detectedParcels", "Parcels"],
                    ["detectedOther", "Other"],
                  ] as Array<[keyof PreviewSourceLayerVisibility, string]>).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      data-testid={`preview-source-sublayer-${key.replace("detected", "").toLowerCase()}`}
                      aria-pressed={sourceLayerVisibility[key]}
                      onClick={() => onToggleSourceLayer(key)}
                      className={`h-7 rounded-md border px-1 text-[9px] font-semibold uppercase ${
                        sourceLayerVisibility[key]
                          ? "border-slate-300 bg-white text-slate-700"
                          : "border-slate-200 bg-slate-100 text-slate-400"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : null}
              <button
                type="button"
                data-testid="preview-source-layer-proposed"
                aria-pressed={sourceLayerVisibility.proposedDesign}
                onClick={() => onToggleSourceLayer("proposedDesign")}
                className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left"
              >
                <span>
                  <span className="block text-xs font-semibold text-slate-800">Proposed linework</span>
                  <span className="block text-[10px] text-slate-500">{sourceLayerCounts.proposedDesign} project object(s)</span>
                </span>
                <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
                  {sourceLayerVisibility.proposedDesign && !aiRealismEnabled ? "Shown" : "Hidden"}
                  {sourceLayerVisibility.proposedDesign && !aiRealismEnabled ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4 text-slate-400" />}
                </span>
              </button>
              {aiRealismEnabled ? (
                <p className="rounded-md bg-sky-50 px-2 py-1.5 text-[10px] text-sky-800">
                  Visual view replaces proposed linework to prevent duplicate geometry.
                </p>
              ) : null}
            </div>
            <div className="mt-3 border-t border-slate-100 pt-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Object types</p>
                <button
                  type="button"
                  data-testid="preview-layer-show-all"
                  onClick={onShowAllSemanticLayers}
                  className="text-[10px] font-semibold text-slate-500 hover:text-slate-900"
                >
                  Show all
                </button>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {PRIMARY_PREVIEW_SEMANTIC_LAYERS.map((layer) => {
                  const visible = semanticLayerVisibility[layer] !== false;
                  return (
                    <button
                      key={layer}
                      type="button"
                      data-testid={`preview-layer-toggle-${layer}`}
                      aria-pressed={visible}
                      onClick={() => onToggleSemanticLayer(layer)}
                      className={`inline-flex h-7 items-center rounded-full border px-2 text-[10px] font-semibold uppercase tracking-[0.08em] ${
                        visible
                          ? "border-slate-300 bg-white text-slate-700"
                          : "border-slate-200 bg-slate-100 text-slate-400"
                      }`}
                    >
                      {PREVIEW_SEMANTIC_LAYER_LABELS[layer]}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </details>
        {isHighQuality ? (
          <span
            data-testid="high-quality-preview-only-label"
            className="flex w-full items-center border-t border-slate-100 px-1 pt-2 text-[10px] font-medium text-slate-500"
          >
            {aiRealismEnabled ? "Presentation" : "Plan Sheet"} mode. Visual preview only. Canonical geometry unchanged. Not engineering evidence.
          </span>
        ) : null}
        {useLightHighQuality ? (
          <span className="inline-flex items-center rounded-md bg-sky-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-sky-800">
            High Quality Lite
          </span>
        ) : null}
      </div>
      <div className="pointer-events-auto flex min-w-0 max-w-full flex-wrap items-center justify-end gap-1.5 border-t border-slate-100 pt-2">
        {showMap ? (
          <button
            type="button"
            data-testid="preview-map-lock-toggle"
            aria-pressed={mapLocked}
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation();
              onSetMapLocked(() => !mapLocked);
            }}
            className={`inline-flex h-8 items-center gap-2 rounded-lg border px-2.5 text-xs font-semibold transition ${
              mapLocked ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            {mapLocked ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
            {mapLocked ? "Unlock Map" : "Lock Map"}
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => {
            onSetFocusTransform(null);
            onResetView?.();
          }}
          className="inline-flex h-8 items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          <RotateCcw className="h-4 w-4" />
          Reset
        </button>
        <button
          type="button"
          onClick={onRefreshPreview}
          disabled={busy}
          className="inline-flex h-8 items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
        {analysisHighlight ? (
          <button
            type="button"
            onClick={() => {
              onSetFocusTransform(null);
              onClearHighlights?.();
            }}
            className="inline-flex h-8 items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <X className="h-4 w-4" />
            Clear
          </button>
        ) : null}
      </div>
    </div>
  );
}
