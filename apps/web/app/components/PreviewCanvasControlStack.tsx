"use client";

import type { ComponentProps } from "react";

import { PreviewActiveDrawHud } from "./PreviewActiveDrawHud";
import { PreviewCanvasHeaderControls } from "./PreviewCanvasHeaderControls";
import { PreviewObjectManagerOverlay } from "./PreviewObjectManagerOverlay";

type PreviewCanvasControlStackProps = {
  activeDrawHudProps: ComponentProps<typeof PreviewActiveDrawHud>;
  allowEdits: boolean;
  drawMode: ComponentProps<typeof PreviewActiveDrawHud>["drawMode"];
  headerProps: ComponentProps<typeof PreviewCanvasHeaderControls>;
  objectManagerProps: ComponentProps<typeof PreviewObjectManagerOverlay>;
  previewMode: "2d" | "3d";
  selectedObjectPresent: boolean;
};

export function PreviewCanvasControlStack({
  activeDrawHudProps,
  allowEdits,
  drawMode,
  headerProps,
  objectManagerProps,
  previewMode,
  selectedObjectPresent,
}: PreviewCanvasControlStackProps) {
  return (
    <div className="relative isolate z-[220] mb-3 overflow-visible rounded-xl border border-slate-200 bg-white/95 shadow-sm">
      <PreviewCanvasHeaderControls {...headerProps} />
      <div className="pointer-events-none relative z-[220] flex min-w-0 max-w-full flex-wrap items-stretch gap-2 px-3 py-2">
        {previewMode === "2d" ? (
          <PreviewObjectManagerOverlay
            {...objectManagerProps}
            visible={allowEdits && drawMode === "select" && selectedObjectPresent}
          />
        ) : null}
      </div>
      <PreviewActiveDrawHud {...activeDrawHudProps} />
    </div>
  );
}
