"use client";

import { Suspense, lazy, useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import type { Preview3DItem } from "../types";
import { loadPreview3DCanvas } from "./preview3DLoader";

const Preview3DCanvas = lazy(loadPreview3DCanvas);

type Preview3DShellProps = {
  items: Preview3DItem[];
  allowEdits: boolean;
  previewQuality: "standard" | "high";
  selectedItemId: string | null;
  hasTerrainSource: boolean;
  hasGradingSurface: boolean;
  usingAnnotation3D: boolean;
  fullscreenOpen: boolean;
  onSelectItem: (id: string | null) => void;
  onOpenFullscreen: () => void;
  onCloseFullscreen: () => void;
};

export function Preview3DShell({
  items,
  allowEdits,
  previewQuality,
  selectedItemId,
  hasTerrainSource,
  hasGradingSurface,
  usingAnnotation3D,
  fullscreenOpen,
  onSelectItem,
  onOpenFullscreen,
  onCloseFullscreen,
}: Preview3DShellProps) {
  useEffect(() => {
    if (!fullscreenOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [fullscreenOpen]);

  const hasReviewContourSurface = items.some(
    (item) => item.terrainSample && /review contour/i.test(String(item.source || "")),
  );
  const hasSourceDemSurface = items.some(
    (item) => item.terrainSample && item.meta?.source_surface_ready === true,
  );

  if (!items.length) {
    return (
      <div className="relative flex min-h-0 w-full flex-1 items-center justify-center overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-[0_16px_40px_-34px_rgba(15,23,42,0.45)]">
        <div className="pointer-events-none absolute left-6 top-6 rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 shadow-sm">
          3D geometry not ready yet
        </div>
      </div>
    );
  }

  const shell = (
    <div
      className={
        fullscreenOpen
          ? "fixed inset-0 z-[500] min-w-0 overflow-hidden bg-slate-950"
          : "relative flex min-h-0 min-w-0 flex-1 overflow-hidden rounded-xl border border-slate-200/90 bg-white"
      }
      data-testid={fullscreenOpen ? "civil-3d-fullscreen" : undefined}
    >
      <Suspense
        fallback={
          <div
            data-testid="civil-3d-viewer-loading"
            className="flex h-full min-h-[300px] items-center justify-center bg-slate-950 text-xs font-semibold uppercase tracking-[0.18em] text-white"
          >
            Loading 3D preview...
          </div>
        }
      >
        <Preview3DCanvas
          items={items}
          interactive={allowEdits}
          fullscreen={fullscreenOpen}
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
      <div className="absolute right-4 top-4 z-[160] flex max-w-[min(260px,calc(100%-2rem))] flex-col items-end gap-2">
        {fullscreenOpen ? (
          <button
            type="button"
            onClick={onCloseFullscreen}
            aria-label="Close Fullscreen"
            title="Close Fullscreen"
            className="grid size-10 place-items-center rounded-full border border-white/40 bg-slate-900/80 text-white shadow-sm transition hover:bg-slate-900"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onOpenFullscreen}
            className="rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm transition hover:bg-slate-900"
          >
            Open Fullscreen
          </button>
        )}
        {!hasGradingSurface && !hasReviewContourSurface && !hasSourceDemSurface ? (
          <div className="pointer-events-none rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm">
            Flat preview surface
          </div>
        ) : null}
      </div>
    </div>
  );

  return fullscreenOpen && typeof document !== "undefined"
    ? createPortal(shell, document.body)
    : shell;
}
