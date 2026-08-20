"use client";

import type { ComponentProps } from "react";

import { PreviewActiveDrawHud } from "./PreviewActiveDrawHud";
import { PreviewCanvasHeaderControls } from "./PreviewCanvasHeaderControls";

type PreviewCanvasControlStackProps = {
  activeDrawHudProps: ComponentProps<typeof PreviewActiveDrawHud>;
  headerProps: ComponentProps<typeof PreviewCanvasHeaderControls>;
};

export function PreviewCanvasControlStack({
  activeDrawHudProps,
  headerProps,
}: PreviewCanvasControlStackProps) {
  return (
    <div
      data-testid="preview-control-stack"
      className="pointer-events-none absolute inset-0 z-[220] overflow-visible"
    >
      <div className="civora-preview-view-toolbar absolute right-3 top-3 z-[250]">
        <PreviewCanvasHeaderControls {...headerProps} />
      </div>
      {activeDrawHudProps.drawMode !== "select" ? (
        <div className="civora-active-draw-hud absolute left-1/2 top-20 z-[250] hidden w-[min(36rem,calc(100%-1.5rem))] -translate-x-1/2 overflow-hidden rounded-[8px] border border-slate-200 bg-white/97 shadow-[0_16px_46px_-28px_rgba(15,23,42,0.55)] backdrop-blur-xl md:block">
          <PreviewActiveDrawHud {...activeDrawHudProps} />
        </div>
      ) : null}
    </div>
  );
}
