"use client";

import type { ComponentProps } from "react";

import { PreviewActiveDrawHud } from "./PreviewActiveDrawHud";
import { PreviewCanvasHeaderControls } from "./PreviewCanvasHeaderControls";
import { PreviewObjectManagerOverlay } from "./PreviewObjectManagerOverlay";

type PreviewCanvasControlStackProps = {
  activeDrawHudProps: ComponentProps<typeof PreviewActiveDrawHud>;
  allowEdits: boolean;
  headerProps: ComponentProps<typeof PreviewCanvasHeaderControls>;
  objectManagerProps: ComponentProps<typeof PreviewObjectManagerOverlay>;
  previewMode: "2d" | "3d";
  selectedObjectPresent: boolean;
};

export function PreviewCanvasControlStack({
  activeDrawHudProps,
  allowEdits,
  headerProps,
  objectManagerProps,
  previewMode,
  selectedObjectPresent,
}: PreviewCanvasControlStackProps) {
  return (
    <div
      data-testid="preview-control-stack"
      className="relative isolate z-[220] mb-2 overflow-visible rounded-[10px] border border-slate-200/90 bg-white/97 shadow-[0_12px_30px_-26px_rgba(15,23,42,0.45)]"
    >
      <PreviewCanvasHeaderControls {...headerProps} />
      {previewMode === "2d" && allowEdits && selectedObjectPresent ? (
        <div className="pointer-events-none relative z-[220] flex min-w-0 max-w-full flex-wrap items-stretch gap-2 border-t border-slate-100 px-3 py-2">
          <PreviewObjectManagerOverlay
            {...objectManagerProps}
            visible
          />
        </div>
      ) : null}
      <PreviewActiveDrawHud {...activeDrawHudProps} />
    </div>
  );
}
