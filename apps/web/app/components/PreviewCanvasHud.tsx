import { Navigation, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";

import type { CadSnapKind } from "../utils/cadGeometryKernel";

type DraftPrecisionReadout = {
  currentPoint: [number, number] | null;
  lastSegment: { length: number; angle: number } | null;
  totalLength: number;
  polygonArea: number | null;
  pointCount: number;
  finishReady: boolean;
} | null;

type PreviewCanvasHudProps = {
  scaleLengthFt: number;
  zoomScale: number;
  zoomLabel?: string;
  lotWidth: number;
  lotHeight: number;
  scaleTruthLabel: string;
  cursorSitePoint: { x: number; y: number } | null;
  draftPrecisionReadout: DraftPrecisionReadout;
  activeDrawToolLabel: string;
  activeSnapKind?: CadSnapKind | null;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetView: () => void;
};

export function PreviewCanvasHud({
  scaleLengthFt,
  zoomScale,
  zoomLabel,
  lotWidth,
  lotHeight,
  scaleTruthLabel,
  cursorSitePoint,
  draftPrecisionReadout,
  activeDrawToolLabel,
  activeSnapKind,
  onZoomIn,
  onZoomOut,
  onResetView,
}: PreviewCanvasHudProps) {
  return (
    <>
      <div className="pointer-events-none absolute left-4 top-16 z-[45] flex items-start gap-2 max-md:top-20">
        <div
          aria-label="Plan north arrow"
          data-testid="plan-north-arrow"
          role="img"
          className="flex h-16 w-12 flex-col items-center justify-center rounded-lg border border-slate-300 bg-white/92 text-slate-800 shadow-sm backdrop-blur"
        >
          <Navigation className="h-5 w-5 -rotate-45" />
          <span className="mt-1 text-[10px] font-bold uppercase tracking-[0.16em]">N</span>
        </div>
        <div
          aria-label="Plan scale bar"
          data-testid="plan-scale-bar"
          className="rounded-lg border border-slate-300 bg-white/92 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600 shadow-sm backdrop-blur"
        >
          <div className="mb-1 flex items-center justify-between gap-4">
            <span>Scale</span>
            <span>{scaleLengthFt} ft</span>
          </div>
          <div className="flex h-3 w-28 overflow-hidden rounded-sm border border-slate-800 bg-white">
            {[0, 1, 2, 3].map((segment) => (
              <span
                key={`scale-segment-${segment}`}
                className={`h-full flex-1 ${segment % 2 === 0 ? "bg-slate-900" : "bg-white"}`}
              />
            ))}
          </div>
        </div>
      </div>
      <div
        className="civora-preview-zoom-controls absolute right-4 top-[4.75rem] z-[45] flex flex-col overflow-hidden rounded-lg border border-slate-300 bg-white/92 shadow-sm backdrop-blur"
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          aria-label="Zoom in canvas"
          title="Zoom in canvas"
          onClick={onZoomIn}
          className="inline-flex h-9 w-9 items-center justify-center border-b border-slate-200 text-slate-700 transition hover:bg-slate-50"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Zoom out canvas"
          title="Zoom out canvas"
          onClick={onZoomOut}
          className="inline-flex h-9 w-9 items-center justify-center border-b border-slate-200 text-slate-700 transition hover:bg-slate-50"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Reset canvas view"
          title="Reset canvas view"
          onClick={onResetView}
          className="inline-flex h-9 w-9 items-center justify-center text-slate-700 transition hover:bg-slate-50"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      </div>
      <div
        aria-label="Canvas coordinate readout"
        data-testid="canvas-coordinate-readout"
        className="civora-preview-coordinate-readout pointer-events-none absolute bottom-4 left-4 z-[45] rounded-lg border border-slate-300 bg-white/92 px-3 py-2 font-mono text-[11px] text-slate-700 shadow-sm backdrop-blur"
      >
        <div>{zoomLabel ?? `ZOOM ${Math.round(zoomScale * 100)}%`}</div>
        <div>
          SITE {Math.round(lotWidth)} ft x {Math.round(lotHeight)} ft
        </div>
        <div>
          <span data-testid="canvas-scale-source">{scaleTruthLabel}</span>
        </div>
        <div>
          X {cursorSitePoint ? cursorSitePoint.x.toFixed(1) : "--"} ft / Y{" "}
          {cursorSitePoint ? cursorSitePoint.y.toFixed(1) : "--"} ft
        </div>
      </div>
      {draftPrecisionReadout ? (
        <div
          aria-label="Draft precision readout"
          data-testid="draft-precision-readout"
          className="pointer-events-none absolute bottom-4 left-[13.5rem] z-[45] max-w-[min(360px,calc(100%-15rem))] rounded-lg border border-slate-300 bg-slate-950/86 px-3 py-2 font-mono text-[11px] text-white shadow-sm backdrop-blur max-md:left-4 max-md:bottom-24 max-md:max-w-[calc(100%-2rem)]"
        >
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            <span>{activeDrawToolLabel}</span>
            <span>PTS {draftPrecisionReadout.pointCount}</span>
            <span>
              X {draftPrecisionReadout.currentPoint ? draftPrecisionReadout.currentPoint[0].toFixed(1) : "--"} / Y{" "}
              {draftPrecisionReadout.currentPoint ? draftPrecisionReadout.currentPoint[1].toFixed(1) : "--"}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-slate-200">
            <span>
              SEG{" "}
              {draftPrecisionReadout.lastSegment
                ? `${draftPrecisionReadout.lastSegment.length.toFixed(1)} ft @ ${draftPrecisionReadout.lastSegment.angle.toFixed(1)} deg`
                : "--"}
            </span>
            {draftPrecisionReadout.polygonArea !== null ? (
              <span>AREA {draftPrecisionReadout.polygonArea.toFixed(0)} sf</span>
            ) : (
              <span>TOTAL {draftPrecisionReadout.totalLength.toFixed(1)} ft</span>
            )}
            <span>SNAP {activeSnapKind || "none"}</span>
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-300">
            Enter {draftPrecisionReadout.finishReady ? "finish" : "when ready"} · Esc cancel
          </div>
        </div>
      ) : null}
    </>
  );
}
