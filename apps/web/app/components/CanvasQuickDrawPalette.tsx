"use client";

import type { DrawMode } from "../utils/cadToolTypes";

type CanvasQuickDrawPaletteProps = {
  visible: boolean;
  drawMode: DrawMode;
  siteLocked?: boolean;
  hasDrawableSiteSize: boolean;
  onActivateDrawTool: (mode: DrawMode, blockedMessage?: string) => void;
  onUnlockSite?: () => void;
  onLockSite?: () => void;
  onClearDraftGeometry: () => void;
  onSetDrawMode: (mode: DrawMode) => void;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  onPushCadCommandFeedback: (command: string, status: "applied" | "blocked" | "info", message: string) => void;
};

export function CanvasQuickDrawPalette({
  visible,
  drawMode,
  siteLocked,
  hasDrawableSiteSize,
  onActivateDrawTool,
  onUnlockSite,
  onLockSite,
  onClearDraftGeometry,
  onSetDrawMode,
  onSetPreviewInteraction,
  onPushCadCommandFeedback,
}: CanvasQuickDrawPaletteProps) {
  if (!visible) return null;

  return (
    <div
      data-testid="canvas-quick-draw-palette"
      className="pointer-events-auto absolute bottom-4 left-1/2 z-[220] flex max-w-[calc(100%-2rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white/96 p-1.5 shadow-[0_18px_55px_-34px_rgba(15,23,42,0.75)] backdrop-blur"
      onMouseDown={(event) => event.stopPropagation()}
      onPointerDown={(event) => event.stopPropagation()}
      onTouchStart={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
    >
      <button
        type="button"
        data-testid="draw-site-boundary-toolbar"
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
        className={`inline-flex h-8 shrink-0 items-center rounded-lg border px-2.5 text-[11px] font-semibold ${
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
          className="inline-flex h-8 shrink-0 items-center rounded-lg border border-slate-200 bg-white px-2.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
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
          className="inline-flex h-8 shrink-0 items-center rounded-lg border border-slate-950 bg-slate-950 px-2.5 text-[11px] font-semibold text-white hover:bg-slate-800"
        >
          Lock Site
        </button>
      ) : null}
    </div>
  );
}
