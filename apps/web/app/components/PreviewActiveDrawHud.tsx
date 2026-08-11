import type { DrawMode } from "../utils/cadToolTypes";

type PreviewActiveDrawHudProps = {
  drawMode: DrawMode;
  activeDrawToolLabel: string;
  activeDrawToolDetail: string;
  draftPointCount: number;
  siteLocked: boolean;
  canDrawObjects: boolean;
  drawObjectsDisabledLabel: string;
  cursorSitePoint: { x: number; y: number } | null;
  canvasScale: number;
  lastCommandLabel?: string;
  finishDraftBlockedReason: string | null;
  canFinishDraftGeometry: boolean;
  onFinishDraftGeometry: () => void;
  onCancelDraw: () => void;
};

export function PreviewActiveDrawHud({
  drawMode,
  activeDrawToolLabel,
  activeDrawToolDetail,
  draftPointCount,
  siteLocked,
  canDrawObjects,
  drawObjectsDisabledLabel,
  cursorSitePoint,
  canvasScale,
  lastCommandLabel,
  finishDraftBlockedReason,
  canFinishDraftGeometry,
  onFinishDraftGeometry,
  onCancelDraw,
}: PreviewActiveDrawHudProps) {
  const isPanMode = drawMode === "pan";
  const statusLabel =
    isPanMode
      ? "Map navigation"
      : drawMode === "site" && draftPointCount
        ? "Draft site boundary"
        : siteLocked
          ? "Locked canonical site"
          : drawMode === "site"
            ? "Draft site boundary mode"
            : draftPointCount
              ? "Draft geometry"
              : canDrawObjects
                ? "Canonical project geometry after finish"
                : drawObjectsDisabledLabel;
  const guidance = activeDrawToolDetail || statusLabel;

  return (
    <div
      className={`${drawMode !== "select" ? "pointer-events-auto" : "pointer-events-none"} relative z-[80] grid h-12 min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 overflow-hidden px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500`}
      data-testid="active-draw-hud"
    >
      <span className="shrink-0 rounded-md border border-slate-900 bg-white px-2 py-1 text-slate-900" data-testid="draw-active-tool">
        {activeDrawToolLabel}
      </span>
      <span className="flex min-w-0 items-center gap-2 overflow-hidden normal-case tracking-normal">
        <span className="truncate text-slate-600" data-testid="draw-active-tool-detail" title={guidance}>
          {guidance}
        </span>
        {cursorSitePoint ? (
          <span className="hidden shrink-0 tabular-nums text-slate-500 xl:inline">
            X {cursorSitePoint.x.toFixed(1)} / Y {cursorSitePoint.y.toFixed(1)} ft
          </span>
        ) : null}
        <span className="hidden shrink-0 text-slate-400 2xl:inline">
          {Math.round(canvasScale * 100)}% · {lastCommandLabel || statusLabel}
        </span>
      </span>
      {drawMode !== "select" && !isPanMode ? (
        <span className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            data-testid="canvas-quick-finish"
            onClick={onFinishDraftGeometry}
            disabled={!canFinishDraftGeometry}
            title={finishDraftBlockedReason ?? "Finish drawn geometry"}
            className={`inline-flex h-8 items-center rounded-lg border px-3 text-[11px] font-semibold normal-case tracking-normal ${
              !canFinishDraftGeometry
                ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                : "border-blue-600 bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            Finish
          </button>
          <button
            type="button"
            data-testid="canvas-quick-cancel"
            onClick={onCancelDraw}
            className="inline-flex h-8 items-center rounded-[6px] border border-slate-200 bg-white px-3 text-[11px] font-semibold normal-case tracking-normal text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
        </span>
      ) : null}
    </div>
  );
}
