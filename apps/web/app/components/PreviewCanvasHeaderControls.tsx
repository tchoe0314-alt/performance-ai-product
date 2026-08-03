"use client";

import { useEffect } from "react";
import { Lock, RefreshCw, RotateCcw, Unlock, X } from "lucide-react";

import type { CoordinateMode } from "../utils/geometryTransforms";
import { coordinateModeLabel } from "../utils/geometryTransforms";
import type { DrawMode } from "../utils/cadToolTypes";
import type { PreviewSemanticLayer } from "../utils/previewSemanticLayers";
import {
  PREVIEW_SEMANTIC_LAYER_LABELS,
  PRIMARY_PREVIEW_SEMANTIC_LAYERS,
} from "../utils/previewSemanticLayers";
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
    <div className="flex min-w-0 flex-wrap items-center gap-2 px-3 py-2">
      <div className="pointer-events-auto relative z-[120] flex min-w-0 max-w-full flex-wrap items-center gap-2">
        <span className="inline-flex items-center rounded-md bg-slate-950 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
          Canvas
        </span>
        <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          {modeLabel} / {previewQuality === "high" ? "High Quality" : "Standard"} / {previewMode.toUpperCase()} /{" "}
          {coordinateModeLabel(coordinateMode)}
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
            aria-label="Use canvas edit tool"
            onClick={() => onSetPreviewInteraction("edit")}
            className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
              allowEdits ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            Edit
          </button>
          {isHighQuality ? (
            <div
              data-testid="ai-realism-toggle"
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white p-0.5"
              aria-label="AI Visualization toggle"
            >
              <span className="px-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">
                AI Visualization
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
                Off
              </button>
              <button
                type="button"
                data-testid="ai-realism-on"
                onClick={onSetAiVisualizationOn}
                aria-pressed={aiRealismEnabled}
                className={`h-7 rounded-md border px-2 text-[11px] font-semibold ${
                  aiRealismEnabled
                    ? "border-slate-900 bg-slate-950 text-white"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                On
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
        <div className="flex min-w-0 flex-wrap items-center gap-1.5" data-testid="preview-semantic-layer-controls">
          <span className="px-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Layers
          </span>
          {PRIMARY_PREVIEW_SEMANTIC_LAYERS.map((layer) => {
            const visible = semanticLayerVisibility[layer] !== false;
            return (
              <button
                key={layer}
                type="button"
                data-testid={`preview-layer-toggle-${layer}`}
                aria-pressed={visible}
                onClick={() => onToggleSemanticLayer(layer)}
                className={`inline-flex h-7 items-center rounded-full border px-2 text-[10px] font-semibold uppercase tracking-[0.1em] ${
                  visible
                    ? "border-slate-300 bg-white text-slate-700"
                    : "border-slate-200 bg-slate-100 text-slate-400"
                }`}
              >
                {PREVIEW_SEMANTIC_LAYER_LABELS[layer]}
              </button>
            );
          })}
          <button
            type="button"
            data-testid="preview-layer-show-all"
            onClick={onShowAllSemanticLayers}
            className="inline-flex h-7 items-center rounded-full border border-slate-200 bg-white px-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500"
          >
            All
          </button>
        </div>
        {isHighQuality ? (
          <span
            data-testid="high-quality-preview-only-label"
            className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-800"
          >
            {aiRealismEnabled ? "Presentation" : "Plan Sheet"} mode. Visual preview only. Canonical geometry unchanged. Not engineering evidence.
          </span>
        ) : null}
        {useLightHighQuality ? (
          <span className="inline-flex items-center rounded-md border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-sky-800">
            High Quality Lite
          </span>
        ) : null}
      </div>
      <div className="pointer-events-auto flex min-w-0 max-w-full flex-wrap items-center gap-2">
        {showMap ? (
          <button
            type="button"
            onClick={() => onSetMapLocked((prev) => !prev)}
            className={`inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-xs font-semibold transition ${
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
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          <RotateCcw className="h-4 w-4" />
          Reset
        </button>
        <button
          type="button"
          onClick={onRefreshPreview}
          disabled={busy}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
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
            className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <X className="h-4 w-4" />
            Clear
          </button>
        ) : null}
      </div>
    </div>
  );
}
