import type { DrawMode } from "../utils/cadToolTypes";
import { PreviewDrawToolButtons } from "./PreviewDrawToolButtons";
import { PreviewQualityToggle, type PreviewQualityValue } from "./PreviewQualityToggle";

type PreviewFloatingToolbarProps = {
  previewMode: "2d" | "3d";
  activePreviewMode: "2d" | "3d";
  previewQuality: PreviewQualityValue;
  canUse3D: boolean;
  isHighQuality: boolean;
  aiRealismEnabled: boolean;
  allowEdits: boolean;
  siteLocked: boolean;
  canDrawObjects: boolean;
  drawObjectsDisabledLabel: string;
  drawMode: DrawMode;
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewQuality: (value: PreviewQualityValue) => void;
  onSetAiVisualizationOff: () => void;
  onSetAiVisualizationOn: () => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  onUnlockSite?: () => void;
  onClearDraftGeometry: () => void;
  onSetDrawMode: (mode: DrawMode) => void;
  onActivateDrawTool: (mode: DrawMode, blockedMessage?: string) => void;
};

export function PreviewFloatingToolbar({
  previewMode,
  activePreviewMode,
  previewQuality,
  canUse3D,
  isHighQuality,
  aiRealismEnabled,
  allowEdits,
  siteLocked,
  canDrawObjects,
  drawObjectsDisabledLabel,
  drawMode,
  onSetPreviewMode,
  onSetPreviewQuality,
  onSetAiVisualizationOff,
  onSetAiVisualizationOn,
  onSetPreviewInteraction,
  onUnlockSite,
  onClearDraftGeometry,
  onSetDrawMode,
  onActivateDrawTool,
}: PreviewFloatingToolbarProps) {
  return (
    <div className="absolute left-1/2 top-3 z-[220] flex max-w-[calc(100%-8rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white/94 p-1 shadow-[0_16px_45px_-28px_rgba(15,23,42,0.65)] backdrop-blur">
      <button
        type="button"
        data-testid="preview-mode-2d"
        aria-label="Show 2D plan preview"
        onClick={() => onSetPreviewMode("2d")}
        className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
          previewMode === "2d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
        }`}
      >
        2D
      </button>
      <button
        type="button"
        data-testid="preview-mode-3d"
        aria-label="Show 3D model preview"
        onClick={() => {
          if (!canUse3D) return;
          onSetPreviewMode("3d");
        }}
        disabled={!canUse3D}
        className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
          activePreviewMode === "3d" ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600 disabled:text-slate-300"
        }`}
      >
        3D
      </button>
      <PreviewQualityToggle
        value={previewQuality}
        onChange={onSetPreviewQuality}
        standardTestId="preview-quality-standard"
        highTestId="preview-quality-high"
        buttonClassName="h-8 rounded-md border px-2.5 text-xs font-semibold"
      />
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
              !aiRealismEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
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
              aiRealismEnabled ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            On
          </button>
        </div>
      ) : null}
      <button
        type="button"
        data-testid="preview-interaction-edit"
        aria-label="Use canvas edit tool"
        onClick={() => onSetPreviewInteraction("edit")}
        className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
          allowEdits ? "border-slate-900 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-600"
        }`}
      >
        Edit
      </button>
      {siteLocked && onUnlockSite ? (
        <button
          type="button"
          title="Unlock the site boundary for editing"
          aria-label="Change Site Boundary"
          onClick={() => {
            onUnlockSite();
            onClearDraftGeometry();
            onSetDrawMode("select");
            onSetPreviewInteraction("edit");
          }}
          className="h-8 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600"
        >
          Change Site
        </button>
      ) : null}
      {previewMode === "2d" && allowEdits ? (
        <>
          {!siteLocked ? (
            <button
              type="button"
              data-testid="draw-site-boundary-toolbar-compact"
              aria-pressed={drawMode === "site"}
              title="Draw the site boundary"
              onClick={() => onActivateDrawTool("site")}
              className={`h-8 rounded-md border px-2.5 text-xs font-semibold ${
                drawMode === "site"
                  ? "border-slate-900 bg-slate-950 text-white"
                  : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              Draw Site
            </button>
          ) : null}
          <PreviewDrawToolButtons
            drawMode={drawMode}
            disabled={!canDrawObjects}
            disabledLabel={drawObjectsDisabledLabel}
            onActivate={onActivateDrawTool}
            buttonClassName="h-8 rounded-md border px-2.5 text-xs font-semibold"
            itemKeyPrefix="generated-draw"
          />
        </>
      ) : null}
    </div>
  );
}
