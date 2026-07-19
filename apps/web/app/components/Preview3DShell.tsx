"use client";

import { Suspense, lazy } from "react";

import type { Preview3DItem } from "../types";
import { PreviewQualityToggle } from "./PreviewQualityToggle";

const Preview3DCanvas = lazy(() => import("./Preview3DCanvas"));

type Preview3DShellProps = {
  items: Preview3DItem[];
  allowEdits: boolean;
  previewQuality: "standard" | "high";
  selectedItemId: string | null;
  hasTerrainSource: boolean;
  hasGradingSurface: boolean;
  usingAnnotation3D: boolean;
  isHighQuality: boolean;
  aiRealismEnabled: boolean;
  onSetPreviewMode: (value: "2d" | "3d") => void;
  onSetPreviewQuality: (value: "standard" | "high") => void;
  onQueuePreviewRefresh: (reason: string) => void;
  onSelectItem: (id: string | null) => void;
  onOpenFullscreen: () => void;
  onSetAiVisualizationOff: () => void;
  onSetAiVisualizationOn: () => void;
};

export function Preview3DShell({
  items,
  allowEdits,
  previewQuality,
  selectedItemId,
  hasTerrainSource,
  hasGradingSurface,
  usingAnnotation3D,
  isHighQuality,
  aiRealismEnabled,
  onSetPreviewMode,
  onSetPreviewQuality,
  onQueuePreviewRefresh,
  onSelectItem,
  onOpenFullscreen,
  onSetAiVisualizationOff,
  onSetAiVisualizationOn,
}: Preview3DShellProps) {
  if (!items.length) {
    return (
      <div className="relative flex min-h-0 w-full flex-1 items-center justify-center overflow-hidden rounded-[24px] bg-white shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)]">
        <div className="pointer-events-none absolute left-6 top-6 rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 shadow-sm">
          3D geometry not ready yet
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-w-0">
      <div className="absolute left-1/2 top-3 z-[120] flex max-w-[calc(100%-8rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white/94 p-1 shadow-[0_16px_45px_-28px_rgba(15,23,42,0.65)] backdrop-blur">
        <button
          type="button"
          data-testid="preview-mode-2d"
          aria-label="Show 2D plan preview"
          onClick={() => onSetPreviewMode("2d")}
          className="h-8 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600"
        >
          2D
        </button>
        <button
          type="button"
          data-testid="preview-mode-3d"
          aria-label="Show 3D model preview"
          onClick={() => onSetPreviewMode("3d")}
          className="h-8 rounded-md border border-slate-900 bg-slate-950 px-2.5 text-xs font-semibold text-white"
        >
          3D
        </button>
        <PreviewQualityToggle
          value={previewQuality}
          onChange={onSetPreviewQuality}
          onQueuePreviewRefresh={onQueuePreviewRefresh}
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
            <span className="px-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">AI Visualization</span>
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
      </div>
      <Suspense
        fallback={
          <div
            data-testid="civil-3d-viewer-loading"
            className="flex min-h-[520px] items-center justify-center rounded-xl border border-slate-200 bg-slate-950 text-xs font-semibold uppercase tracking-[0.18em] text-white"
          >
            Loading 3D preview...
          </div>
        }
      >
        <Preview3DCanvas
          items={items}
          interactive={allowEdits}
          previewQuality={previewQuality}
          selectedItemId={selectedItemId}
          hasTerrainSource={hasTerrainSource}
          hasGradingSurface={hasGradingSurface}
          onSelectItem={onSelectItem}
          onOpenFullscreen={onOpenFullscreen}
        />
      </Suspense>
      {usingAnnotation3D ? (
        <div className="pointer-events-none absolute left-4 top-4 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm">
          Approximate 3D
        </div>
      ) : null}
      {!hasGradingSurface ? (
        <div
          className={`pointer-events-none absolute right-4 rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm ${
            usingAnnotation3D ? "top-14" : "top-4"
          }`}
        >
          Grading surface missing
        </div>
      ) : null}
      <button
        type="button"
        onClick={onOpenFullscreen}
        className="absolute right-4 top-4 rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm transition hover:bg-slate-900"
      >
        Open Fullscreen
      </button>
    </div>
  );
}
