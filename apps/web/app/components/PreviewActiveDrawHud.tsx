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

  return (
    <div className={`${drawMode !== "select" ? "pointer-events-auto relative z-[80] flex" : "hidden"} min-w-0 flex-wrap items-center gap-3 border-t border-slate-200 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500`}>
      <span className="rounded-md border border-slate-900 bg-white px-2 py-1 text-slate-900" data-testid="draw-active-tool">
        {activeDrawToolLabel}
      </span>
      <span className="max-w-[320px] truncate normal-case tracking-normal text-slate-600" data-testid="draw-active-tool-detail">
        {activeDrawToolDetail}
      </span>
      <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-slate-600">
        {statusLabel}
      </span>
      {cursorSitePoint ? (
        <span>X {cursorSitePoint.x.toFixed(1)} ft / Y {cursorSitePoint.y.toFixed(1)} ft</span>
      ) : null}
      <span>{Math.round(canvasScale * 100)}%</span>
      <span>{lastCommandLabel || "No command"}</span>
      {!isPanMode && finishDraftBlockedReason ? (
        <span className="max-w-56 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700">
          {finishDraftBlockedReason}
        </span>
      ) : null}
      {!isPanMode ? (
        <span className="ml-auto flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            data-testid="canvas-quick-finish"
            onClick={onFinishDraftGeometry}
            disabled={!canFinishDraftGeometry}
            title={finishDraftBlockedReason ?? "Finish drawn geometry"}
            className={`inline-flex h-8 items-center rounded-lg border px-3 text-[11px] font-semibold normal-case tracking-normal ${
              !canFinishDraftGeometry
                ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-800"
                : "border-slate-900 bg-slate-950 text-white"
            }`}
          >
            Finish
          </button>
          <button
            type="button"
            data-testid="canvas-quick-cancel"
            onClick={onCancelDraw}
            className="inline-flex h-8 items-center rounded-lg border border-slate-200 bg-white px-3 text-[11px] font-semibold normal-case tracking-normal text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
        </span>
      ) : null}
    </div>
  );
}
