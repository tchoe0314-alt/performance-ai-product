import type { DrawMode } from "../utils/cadToolTypes";
import { PreviewDrawToolButtons } from "./PreviewDrawToolButtons";

type PreviewStableDrawToolbarProps = {
  drawMode: DrawMode;
  siteLocked: boolean;
  hasDrawableSiteSize: boolean;
  canDrawObjects: boolean;
  drawObjectsDisabledLabel: string;
  onUnlockSite?: () => void;
  onLockSite?: () => void;
  onClearDraftGeometry: () => void;
  onSetDrawMode: (mode: DrawMode) => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  onActivateDrawTool: (mode: DrawMode, blockedMessage?: string) => void;
  onPushCadCommandFeedback: (command: string, status: "applied" | "blocked" | "info", message: string) => void;
};

export function PreviewStableDrawToolbar({
  drawMode,
  siteLocked,
  hasDrawableSiteSize,
  canDrawObjects,
  drawObjectsDisabledLabel,
  onUnlockSite,
  onLockSite,
  onClearDraftGeometry,
  onSetDrawMode,
  onSetPreviewInteraction,
  onActivateDrawTool,
  onPushCadCommandFeedback,
}: PreviewStableDrawToolbarProps) {
  return (
    <div className="pointer-events-auto relative z-[82] flex min-w-0 flex-wrap items-center gap-2 border-t border-slate-200 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
      <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-slate-600">Draw</span>
      <button
        type="button"
        data-testid="draw-site-boundary-toolbar-top"
        aria-pressed={drawMode === "site"}
        title={siteLocked ? "Site is locked. Use Change Site before drawing a new boundary." : "Draw the site boundary"}
        onClick={() => {
          if (siteLocked) {
            onPushCadCommandFeedback("SITE", "blocked", "SITE boundary is locked. Use Change Site before drawing a replacement boundary.");
            return;
          }
          onActivateDrawTool("site");
        }}
        className={`pointer-events-auto inline-flex h-8 items-center rounded-md border px-2.5 text-xs font-semibold ${
          drawMode === "site"
            ? "border-slate-900 bg-slate-950 text-white"
            : siteLocked
              ? "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              : "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
        }`}
      >
        Draw Site
      </button>
      {siteLocked && onUnlockSite ? (
        <button
          type="button"
          data-testid="change-site-boundary-toolbar"
          aria-label="Change Site Boundary"
          onClick={() => {
            onUnlockSite();
            onClearDraftGeometry();
            onSetDrawMode("select");
            onSetPreviewInteraction("edit");
          }}
          className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
        >
          Change Site
        </button>
      ) : null}
      {!siteLocked && drawMode === "select" && hasDrawableSiteSize && onLockSite ? (
        <button
          type="button"
          data-testid="lock-site-boundary-toolbar"
          aria-label="Lock Site Boundary"
          onClick={() => {
            onClearDraftGeometry();
            onSetDrawMode("select");
            onLockSite();
          }}
          className="inline-flex h-8 items-center rounded-md border border-slate-950 bg-slate-950 px-2.5 text-xs font-semibold text-white hover:bg-slate-800"
        >
          Lock Site
        </button>
      ) : null}
      <PreviewDrawToolButtons
        drawMode={drawMode}
        disabled={!canDrawObjects}
        disabledLabel={drawObjectsDisabledLabel}
        onActivate={onActivateDrawTool}
        inactiveClassName="border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
        itemKeyPrefix="canvas-stable-draw"
        includePan
      />
    </div>
  );
}
