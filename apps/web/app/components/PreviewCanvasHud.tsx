import { Navigation, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";

import type { CadSnapKind } from "../utils/cadGeometryKernel";
import { displayLength, type DisplayUnits } from "../utils/workspaceEnvironment";

type DraftPrecisionReadout = {
  currentPoint: [number, number] | null;
  lastSegment: { length: number; angle: number } | null;
  totalLength: number;
  polygonArea: number | null;
  pointCount: number;
  finishReady: boolean;
} | null;

type PreviewCanvasHudProps = {
  displayUnits?: DisplayUnits;
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
  displayUnits = "ft",
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
      <div className="pointer-events-none absolute left-3 top-14 z-[45] flex items-start gap-1.5 max-md:left-2 max-md:top-16">
        <div
          aria-label="Plan north arrow"
          data-testid="plan-north-arrow"
          role="img"
          className="flex h-12 w-10 flex-col items-center justify-center rounded-md border border-slate-300 bg-white/92 text-slate-800 shadow-sm backdrop-blur"
        >
          <Navigation className="h-4 w-4 -rotate-45" />
          <span className="mt-0.5 text-[9px] font-bold uppercase tracking-[0.14em]">N</span>
        </div>
        <div
          aria-label="Plan scale bar"
          data-testid="plan-scale-bar"
          className="rounded-md border border-slate-300 bg-white/92 px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-600 shadow-sm backdrop-blur"
        >
          <div className="mb-1 flex items-center justify-between gap-4">
            <span>Scale</span>
            <span>{displayLength(scaleLengthFt, displayUnits)}</span>
          </div>
          <div className="flex h-2.5 w-20 overflow-hidden rounded-sm border border-slate-800 bg-white">
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
        className="civora-preview-zoom-controls absolute right-3 top-[4.25rem] z-[45] flex flex-col overflow-hidden rounded-md border border-slate-300 bg-white/92 shadow-sm backdrop-blur max-md:right-2"
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          aria-label="Zoom in canvas"
          title="Zoom in canvas"
          onClick={onZoomIn}
          className="inline-flex h-10 w-10 items-center justify-center border-b border-slate-200 text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 md:h-8 md:w-8"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Zoom out canvas"
          title="Zoom out canvas"
          onClick={onZoomOut}
          className="inline-flex h-10 w-10 items-center justify-center border-b border-slate-200 text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 md:h-8 md:w-8"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Reset canvas view"
          title="Reset canvas view"
          onClick={onResetView}
          className="inline-flex h-10 w-10 items-center justify-center text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 md:h-8 md:w-8"
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
          SITE {displayLength(lotWidth, displayUnits)} x {displayLength(lotHeight, displayUnits)}
        </div>
        <div>
          <span data-testid="canvas-scale-source">{scaleTruthLabel}</span>
        </div>
        <div>
          X {cursorSitePoint ? displayLength(cursorSitePoint.x, displayUnits, 1, true) : "--"} / Y{" "}
          {cursorSitePoint ? displayLength(cursorSitePoint.y, displayUnits, 1, true) : "--"}
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
              X {draftPrecisionReadout.currentPoint ? displayLength(draftPrecisionReadout.currentPoint[0], displayUnits, 1, true) : "--"} / Y{" "}
              {draftPrecisionReadout.currentPoint ? displayLength(draftPrecisionReadout.currentPoint[1], displayUnits, 1, true) : "--"}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-slate-200">
            <span>
              SEG{" "}
              {draftPrecisionReadout.lastSegment
                ? `${displayLength(draftPrecisionReadout.lastSegment.length, displayUnits, 1, true)} @ ${draftPrecisionReadout.lastSegment.angle.toFixed(1)} deg`
                : "--"}
            </span>
            {draftPrecisionReadout.polygonArea !== null ? (
              <span>AREA {(draftPrecisionReadout.polygonArea * (displayUnits === "m" ? 0.09290304 : 1)).toFixed(0)} {displayUnits === "m" ? "m²" : "sf"}</span>
            ) : (
              <span>TOTAL {displayLength(draftPrecisionReadout.totalLength, displayUnits, 1, true)}</span>
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
