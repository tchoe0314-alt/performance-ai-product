"use client";

import { Lock, RefreshCw, RotateCcw, Unlock, X } from "lucide-react";

import type { CoordinateMode } from "../utils/geometryTransforms";
import { coordinateModeLabel } from "../utils/geometryTransforms";
import type { DrawMode } from "../utils/cadToolTypes";
import { PreviewDrawToolButtons } from "./PreviewDrawToolButtons";
import { PreviewQualityToggle } from "./PreviewQualityToggle";

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
  canDrawObjects: boolean;
  drawObjectsDisabledLabel: string;
  isHighQuality: boolean;
  useLightHighQuality: boolean;
  busy: boolean;
  analysisHighlight: unknown;
  onSetPreviewQuality: (value: "standard" | "high") => void;
  onQueuePreviewRefresh: (reason: string) => void;
  onSetPreviewMode: (value: "2d" | "3d") => void;
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
  canDrawObjects,
  drawObjectsDisabledLabel,
  isHighQuality,
  useLightHighQuality,
  busy,
  analysisHighlight,
  onSetPreviewQuality,
  onQueuePreviewRefresh,
  onSetPreviewMode,
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
}: PreviewCanvasHeaderControlsProps) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2 px-3 py-2">
      <div className="pointer-events-auto relative z-[120] flex min-w-0 max-w-full flex-wrap items-center gap-2">
        <span className="inline-flex items-center rounded-md bg-slate-950 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
          Canvas
        </span>
        <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          {previewQuality === "high" ? "High Quality" : "Standard"} / {previewMode.toUpperCase()} /{" "}
          {coordinateModeLabel(coordinateMode)}
        </span>
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <PreviewQualityToggle
            value={previewQuality}
            onChange={onSetPreviewQuality}
            onQueuePreviewRefresh={onQueuePreviewRefresh}
            standardTestId="preview-inner-quality-standard"
            highTestId="preview-inner-quality-high"
          />
          <button
            type="button"
            data-testid="preview-inner-mode-2d"
            onClick={() => onSetPreviewMode("2d")}
            className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
              previewMode === "2d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            2D
          </button>
          <button
            type="button"
            data-testid="preview-inner-mode-3d"
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
            data-testid="preview-inner-interaction-edit"
            aria-label="Use canvas edit tool"
            onClick={() => onSetPreviewInteraction("edit")}
            className={`inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
              allowEdits ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            Edit
          </button>
          {previewMode === "2d" ? (
            <button
              type="button"
              data-testid="preview-inner-draw-site-boundary"
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
          {previewMode === "2d" && siteLocked && onUnlockSite ? (
            <button
              type="button"
              data-testid="change-site-boundary-toolbar-hidden"
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
          {previewMode === "2d" ? (
            <PreviewDrawToolButtons
              drawMode={drawMode}
              disabled={!canDrawObjects}
              disabledLabel={drawObjectsDisabledLabel}
              onActivate={onActivateDrawTool}
              itemKeyPrefix="canvas-primary-draw"
            />
          ) : null}
        </div>
        {isHighQuality ? (
          <span
            data-testid="high-quality-preview-only-label"
            className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-800"
          >
            Presentation/realism mode. Visual preview only. Canonical geometry unchanged. Not engineering evidence.
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
