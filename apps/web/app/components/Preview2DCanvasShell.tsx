import type { ComponentProps, HTMLAttributes, RefObject } from "react";

import { AiRealismPreviewOverlay } from "./AiRealismPreviewOverlay";
import { CanvasQuickDrawPalette } from "./CanvasQuickDrawPalette";
import { Preview2DSurface } from "./Preview2DSurface";
import { PreviewAnnotationHoverCard } from "./PreviewAnnotationHoverCard";
import { PreviewMobileDrawToolbar } from "./PreviewMobileDrawToolbar";
import { PreviewFullscreenHeader } from "./PreviewPlanAnnotationOverlay";
import { WaterFireFlowEvidenceDock } from "./WaterFireFlowEvidenceDock";

type Preview2DCanvasShellProps = {
  previewRef: RefObject<HTMLDivElement | null>;
  previewFullscreenOpen: boolean;
  showMap: boolean;
  placementMode: boolean;
  allowEdits: boolean;
  drawMode: string;
  shellHandlers: HTMLAttributes<HTMLDivElement>;
  quickDrawPaletteProps: ComponentProps<typeof CanvasQuickDrawPalette>;
  aiRealismPreviewOverlayProps?: ComponentProps<typeof AiRealismPreviewOverlay>;
  mobileDrawToolbarProps?: ComponentProps<typeof PreviewMobileDrawToolbar>;
  surfaceProps: ComponentProps<typeof Preview2DSurface>;
  annotationHoverCardProps?: ComponentProps<typeof PreviewAnnotationHoverCard>;
  waterFireFlowEvidenceDockProps: ComponentProps<typeof WaterFireFlowEvidenceDock>;
  fullscreenHeaderProps?: ComponentProps<typeof PreviewFullscreenHeader>;
};

export function Preview2DCanvasShell({
  previewRef,
  previewFullscreenOpen,
  showMap,
  placementMode,
  allowEdits,
  drawMode,
  shellHandlers,
  quickDrawPaletteProps,
  aiRealismPreviewOverlayProps,
  mobileDrawToolbarProps,
  surfaceProps,
  annotationHoverCardProps,
  waterFireFlowEvidenceDockProps,
  fullscreenHeaderProps,
}: Preview2DCanvasShellProps) {
  return (
    <div
      ref={previewRef}
      className={`civora-preview-shell relative flex min-h-[260px] w-full min-w-0 flex-1 items-center justify-center overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-[0_16px_40px_-34px_rgba(15,23,42,0.45)] ${
        previewFullscreenOpen && showMap
          ? "fixed inset-0 z-[120] rounded-none border-0 bg-slate-950 p-0"
          : ""
      } ${
        placementMode || allowEdits ? "cursor-crosshair" : "cursor-default"
      }`}
      style={{ touchAction: drawMode === "select" ? "auto" : "none" }}
      {...shellHandlers}
    >
      <CanvasQuickDrawPalette {...quickDrawPaletteProps} />
      {aiRealismPreviewOverlayProps ? <AiRealismPreviewOverlay {...aiRealismPreviewOverlayProps} /> : null}
      {mobileDrawToolbarProps ? <PreviewMobileDrawToolbar {...mobileDrawToolbarProps} /> : null}
      <Preview2DSurface {...surfaceProps} />
      {annotationHoverCardProps ? <PreviewAnnotationHoverCard {...annotationHoverCardProps} /> : null}
      <WaterFireFlowEvidenceDock {...waterFireFlowEvidenceDockProps} />
      {/* Status panel removed: keep preview visually clean. */}
      {fullscreenHeaderProps ? (
        <div className="pointer-events-auto absolute left-0 right-0 top-0 z-40 border-b border-white/10 bg-slate-950/88 backdrop-blur">
          <PreviewFullscreenHeader {...fullscreenHeaderProps} />
        </div>
      ) : null}
    </div>
  );
}
