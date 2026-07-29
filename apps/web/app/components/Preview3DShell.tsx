"use client";

import { Suspense, lazy } from "react";

import type { Preview3DItem } from "../types";

const Preview3DCanvas = lazy(() => import("./Preview3DCanvas"));

type Preview3DShellProps = {
  items: Preview3DItem[];
  allowEdits: boolean;
  previewQuality: "standard" | "high";
  selectedItemId: string | null;
  hasTerrainSource: boolean;
  hasGradingSurface: boolean;
  usingAnnotation3D: boolean;
  onSelectItem: (id: string | null) => void;
  onOpenFullscreen: () => void;
};

export function Preview3DShell({
  items,
  allowEdits,
  previewQuality,
  selectedItemId,
  hasTerrainSource,
  hasGradingSurface,
  usingAnnotation3D,
  onSelectItem,
  onOpenFullscreen,
}: Preview3DShellProps) {
  const hasReviewContourSurface = items.some(
    (item) => item.terrainSample && /review contour/i.test(String(item.source || "")),
  );

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
      <div className="absolute right-4 top-4 z-[120] flex max-w-[min(260px,calc(100%-2rem))] flex-col items-end gap-2">
        <button
          type="button"
          onClick={onOpenFullscreen}
          className="rounded-full border border-white/40 bg-slate-900/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm transition hover:bg-slate-900"
        >
          Open Fullscreen
        </button>
        {!hasGradingSurface && !hasReviewContourSurface ? (
          <div className="pointer-events-none rounded-full border border-white/40 bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white shadow-sm">
            Flat preview surface
          </div>
        ) : null}
      </div>
    </div>
  );
}
