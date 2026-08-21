"use client";

import { useEffect, useRef } from "react";
import {
  Eye,
  EyeOff,
  Layers3,
  Lock,
  MoreHorizontal,
  MousePointer2,
  RefreshCw,
  RotateCcw,
  Ruler,
  Unlock,
  X,
} from "lucide-react";

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
  precisionToolsVisible: boolean;
  transientMenuCloseToken?: string;
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
  onTogglePrecisionTools: () => void;
};

const controlClass = (active: boolean) =>
  `inline-flex h-8 items-center justify-center rounded-[6px] px-2.5 text-xs font-semibold transition ${
    active
      ? "bg-slate-950 text-white"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
  }`;

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
  isHighQuality,
  aiRealismEnabled,
  useLightHighQuality,
  busy,
  analysisHighlight,
  semanticLayerVisibility,
  sourceLayerVisibility,
  sourceLayerCounts,
  precisionToolsVisible,
  transientMenuCloseToken,
  onSetPreviewQuality,
  onSetPreviewMode,
  onSetAiVisualizationOff,
  onSetAiVisualizationOn,
  onSetPreviewInteraction,
  onSetMapOverlayEnabled,
  onSetMapLocked,
  onActivateDrawTool,
  onPushCadCommandFeedback,
  onSetFocusTransform,
  onResetView,
  onRefreshPreview,
  onClearHighlights,
  onToggleSemanticLayer,
  onShowAllSemanticLayers,
  onToggleSourceLayer,
  onTogglePrecisionTools,
}: PreviewCanvasHeaderControlsProps) {
  const layerMenuRef = useRef<HTMLDetailsElement>(null);
  const viewMenuRef = useRef<HTMLDetailsElement>(null);
  const closeHeaderMenus = () => {
    if (layerMenuRef.current) layerMenuRef.current.open = false;
    if (viewMenuRef.current) viewMenuRef.current.open = false;
  };

  useEffect(() => {
    if (!canUse3D) return;
    const preloadTimer = window.setTimeout(() => void loadPreview3DCanvas(), 1500);
    return () => window.clearTimeout(preloadTimer);
  }, [canUse3D]);

  useEffect(() => {
    closeHeaderMenus();
  }, [transientMenuCloseToken]);

  return (
    <div className="pointer-events-auto relative flex min-w-0 items-center gap-1 rounded-[8px] border border-slate-200/90 bg-white/96 p-1 shadow-[0_16px_44px_-30px_rgba(15,23,42,0.55)] backdrop-blur-xl">
      <span className="sr-only" data-testid="site-status">
        {siteLocked ? "Site Locked" : "Site Editable"}; {coordinateModeLabel(coordinateMode)}
      </span>
      <button
        type="button"
        data-testid="preview-interaction-edit"
        aria-label="Select and edit objects"
        aria-pressed={allowEdits && drawMode === "select"}
        title="Select"
        onClick={() => {
          closeHeaderMenus();
          if (aiRealismEnabled) onSetAiVisualizationOff();
          onSetPreviewInteraction("edit");
          onActivateDrawTool("select");
        }}
        className={`${controlClass(allowEdits && drawMode === "select")} w-8 px-0`}
      >
        <MousePointer2 className="h-4 w-4" />
      </button>
      <span className="mx-0.5 h-5 w-px bg-slate-200" aria-hidden="true" />
      <button
        type="button"
        data-testid="preview-mode-2d"
        aria-pressed={previewMode === "2d"}
        onClick={() => {
          closeHeaderMenus();
          onSetPreviewMode("2d");
        }}
        className={controlClass(previewMode === "2d")}
      >
        2D
      </button>
      <button
        type="button"
        data-testid="preview-mode-3d"
        aria-pressed={previewMode === "3d"}
        onPointerEnter={() => canUse3D && void loadPreview3DCanvas()}
        onFocus={() => canUse3D && void loadPreview3DCanvas()}
        onClick={() => {
          closeHeaderMenus();
          if (canUse3D) onSetPreviewMode("3d");
        }}
        disabled={!canUse3D}
        className={`${controlClass(previewMode === "3d")} disabled:cursor-not-allowed disabled:opacity-35`}
      >
        3D
      </button>
      <button
        type="button"
        data-testid="preview-inner-map-toggle"
        aria-pressed={mapOverlayEnabled}
        onClick={() => {
          closeHeaderMenus();
          onSetMapOverlayEnabled((value) => !value);
        }}
        disabled={!mapAvailable}
        title={mapAvailable ? "Toggle map context" : "Apply an address to enable map context"}
        className={`${controlClass(mapOverlayEnabled)} disabled:cursor-not-allowed disabled:opacity-35`}
      >
        Map
      </button>

      <details
        ref={layerMenuRef}
        data-testid="preview-layer-menu"
        className="group relative"
        onToggle={(event) => {
          if (event.currentTarget.open && viewMenuRef.current) viewMenuRef.current.open = false;
        }}
      >
        <summary className={`${controlClass(false)} cursor-pointer list-none gap-1.5 marker:hidden`}>
          <Layers3 className="h-3.5 w-3.5" />
          Layers
        </summary>
        <div
          data-testid="preview-semantic-layer-controls"
          className="absolute right-0 top-[calc(100%+0.45rem)] z-[320] w-[min(19rem,calc(100vw-1.5rem))] rounded-[8px] border border-slate-200 bg-white p-3 text-slate-700 shadow-[0_22px_64px_-32px_rgba(15,23,42,0.55)]"
        >
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2">
            <div>
              <p className="text-xs font-semibold text-slate-950">Layers</p>
              <p className="mt-0.5 text-[11px] text-slate-500" data-testid="preview-layer-visibility-summary" aria-live="polite">
                Existing {sourceLayerVisibility.detectedExisting ? "shown" : "hidden"}; design {sourceLayerVisibility.proposedDesign ? "shown" : "hidden"}
              </p>
            </div>
            <button
              type="button"
              data-testid="preview-layer-show-all"
              onClick={onShowAllSemanticLayers}
              className="text-[11px] font-semibold text-blue-600"
            >
              Show all
            </button>
          </div>
          <div className="divide-y divide-slate-100">
            <button
              type="button"
              data-testid="preview-source-layer-existing"
              aria-pressed={sourceLayerVisibility.detectedExisting}
              onClick={() => onToggleSourceLayer("detectedExisting")}
              className="flex w-full items-center justify-between py-2.5 text-left"
            >
              <span>
                <span className="block text-xs font-semibold text-slate-800">Existing context</span>
                <span className="block text-[10px] text-slate-500">{sourceLayerCounts.detectedExisting} objects</span>
              </span>
              {sourceLayerVisibility.detectedExisting ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4 text-slate-400" />}
            </button>
            {sourceLayerVisibility.detectedExisting ? (
              <div className="grid grid-cols-4 gap-1 pb-2" data-testid="preview-existing-sublayers">
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
                    className={`h-7 rounded-[5px] border px-1 text-[9px] font-semibold ${
                      sourceLayerVisibility[key] ? "border-slate-300 bg-white text-slate-700" : "border-slate-200 bg-slate-50 text-slate-400"
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
              className="flex w-full items-center justify-between py-2.5 text-left"
            >
              <span>
                <span className="block text-xs font-semibold text-slate-800">Proposed design</span>
                <span className="block text-[10px] text-slate-500">{sourceLayerCounts.proposedDesign} objects</span>
              </span>
              {sourceLayerVisibility.proposedDesign && !aiRealismEnabled ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4 text-slate-400" />}
            </button>
          </div>
          <div className="flex flex-wrap gap-1 border-t border-slate-100 pt-2">
            {PRIMARY_PREVIEW_SEMANTIC_LAYERS.map((layer) => {
              const visible = semanticLayerVisibility[layer] !== false;
              return (
                <button
                  key={layer}
                  type="button"
                  data-testid={`preview-layer-toggle-${layer}`}
                  aria-pressed={visible}
                  onClick={() => onToggleSemanticLayer(layer)}
                  className={`h-7 rounded-[5px] border px-2 text-[10px] font-semibold ${
                    visible ? "border-slate-300 bg-white text-slate-700" : "border-slate-200 bg-slate-50 text-slate-400"
                  }`}
                >
                  {PREVIEW_SEMANTIC_LAYER_LABELS[layer]}
                </button>
              );
            })}
          </div>
        </div>
      </details>

      <details
        ref={viewMenuRef}
        className="group relative"
        onToggle={(event) => {
          if (event.currentTarget.open && layerMenuRef.current) layerMenuRef.current.open = false;
        }}
      >
        <summary aria-label="Preview view options" title="View options" className={`${controlClass(false)} w-8 cursor-pointer list-none px-0 marker:hidden`}>
          <MoreHorizontal className="h-4 w-4" />
        </summary>
        <div className="absolute right-0 top-[calc(100%+0.45rem)] z-[320] w-[17rem] rounded-[8px] border border-slate-200 bg-white p-3 shadow-[0_22px_64px_-32px_rgba(15,23,42,0.55)]">
          <p className="text-xs font-semibold text-slate-950">View</p>
          <div className="mt-2">
            <PreviewQualityToggle
              value={previewQuality}
              onChange={onSetPreviewQuality}
              standardTestId="preview-quality-standard"
              highTestId="preview-quality-high"
              standardLabel="Standard"
              highLabel="High"
            />
          </div>
          <button
            type="button"
            data-testid="preview-precision-tools-toggle"
            aria-pressed={precisionToolsVisible}
            onClick={onTogglePrecisionTools}
            className="mt-2 inline-flex h-9 w-full items-center gap-2 rounded-[6px] border-t border-slate-100 px-2 text-left text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Ruler className="h-3.5 w-3.5" />
            {precisionToolsVisible ? "Hide precision & commands" : "Precision & commands"}
          </button>
          <div data-testid="ai-realism-toggle" className="mt-2 flex items-center justify-between border-t border-slate-100 pt-2">
            <span className="text-xs font-medium text-slate-700">AI Visualization</span>
            <div className="flex rounded-[6px] bg-slate-100 p-0.5">
              <button type="button" data-testid="ai-realism-off" onClick={onSetAiVisualizationOff} aria-pressed={!aiRealismEnabled} className={controlClass(!aiRealismEnabled)}>Off</button>
              <button
                type="button"
                data-testid="ai-realism-on"
                onClick={() => {
                  if (drawMode !== "select") {
                    onPushCadCommandFeedback("VISUAL", "info", "Finish or cancel the active drawing before opening AI Visualization.");
                    return;
                  }
                  if (mapAvailable) onSetMapOverlayEnabled(() => true);
                  onSetAiVisualizationOn();
                }}
                aria-pressed={aiRealismEnabled}
                className={controlClass(aiRealismEnabled)}
              >
                On
              </button>
            </div>
          </div>
          {isHighQuality ? (
            <p data-testid="high-quality-preview-only-label" className="mt-2 text-[10px] leading-4 text-slate-500">
              Visual preview only. Project geometry is unchanged; not engineering evidence.
            </p>
          ) : null}
          {useLightHighQuality ? <p className="mt-1 text-[10px] text-sky-700">High Quality Lite is active.</p> : null}
          <div className="mt-2 grid grid-cols-2 gap-1 border-t border-slate-100 pt-2">
            {showMap ? (
              <button
                type="button"
                data-testid="preview-map-lock-toggle"
                aria-pressed={mapLocked}
                onClick={() => onSetMapLocked(() => !mapLocked)}
                className="inline-flex h-8 items-center justify-center gap-1.5 rounded-[6px] text-xs font-semibold text-slate-600 hover:bg-slate-100"
              >
                {mapLocked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                {mapLocked ? "Unlock map" : "Lock map"}
              </button>
            ) : null}
            <button type="button" onClick={() => { onSetFocusTransform(null); onResetView?.(); }} className="inline-flex h-8 items-center justify-center gap-1.5 rounded-[6px] text-xs font-semibold text-slate-600 hover:bg-slate-100">
              <RotateCcw className="h-3.5 w-3.5" /> Reset
            </button>
            <button type="button" onClick={onRefreshPreview} disabled={busy} className="inline-flex h-8 items-center justify-center gap-1.5 rounded-[6px] text-xs font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-40">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </button>
            {analysisHighlight ? (
              <button type="button" onClick={() => { onSetFocusTransform(null); onClearHighlights?.(); }} className="inline-flex h-8 items-center justify-center gap-1.5 rounded-[6px] text-xs font-semibold text-slate-600 hover:bg-slate-100">
                <X className="h-3.5 w-3.5" /> Clear
              </button>
            ) : null}
          </div>
        </div>
      </details>
    </div>
  );
}
