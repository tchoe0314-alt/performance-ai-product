import type {
  ComponentProps,
  Dispatch,
  MouseEvent as ReactMouseEvent,
  RefObject,
  SetStateAction,
} from "react";

import { Preview2DOverlayStack } from "./Preview2DOverlayStack";
import { PreviewCanvasHud } from "./PreviewCanvasHud";
import { PreviewMapStatusOverlay } from "./PreviewMapStatusOverlay";
import { PreviewPlanAnnotationOverlay } from "./PreviewPlanAnnotationOverlay";

type CadWindowSelect = {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  containerLeft: number;
  containerTop: number;
} | null;

type PreviewImageBounds = { left: number; top: number; width: number; height: number };

type Preview2DSurfaceProps = {
  mapContainerRef: RefObject<HTMLDivElement | null>;
  showMap: boolean;
  previewMode: "2d" | "3d";
  showGeneratedPlan: boolean;
  planPreviewUrl?: string | null;
  hasLiveObjects: boolean;
  placementMode: boolean;
  allowEdits: boolean;
  overlayBoundsResolved: boolean;
  cadWindowSelect: CadWindowSelect;
  previewImageRef: RefObject<HTMLImageElement | null>;
  previewRef: RefObject<HTMLDivElement | null>;
  setPreviewImageBounds: Dispatch<SetStateAction<PreviewImageBounds | null>>;
  updateImageBounds: (
    containerRef: RefObject<HTMLDivElement | null>,
    imageRef: RefObject<HTMLImageElement | null>,
    setBounds: Dispatch<SetStateAction<PreviewImageBounds | null>>,
  ) => void;
  onMouseDown: (event: ReactMouseEvent<HTMLDivElement>) => void;
  mapStatusOverlayProps: ComponentProps<typeof PreviewMapStatusOverlay>;
  canvasHudProps: ComponentProps<typeof PreviewCanvasHud>;
  overlayStackProps: ComponentProps<typeof Preview2DOverlayStack>;
  planAnnotationOverlayProps?: ComponentProps<typeof PreviewPlanAnnotationOverlay>;
};

export function Preview2DSurface({
  mapContainerRef,
  showMap,
  previewMode,
  showGeneratedPlan,
  planPreviewUrl,
  hasLiveObjects,
  placementMode,
  allowEdits,
  overlayBoundsResolved,
  cadWindowSelect,
  previewImageRef,
  previewRef,
  setPreviewImageBounds,
  updateImageBounds,
  onMouseDown,
  mapStatusOverlayProps,
  canvasHudProps,
  overlayStackProps,
  planAnnotationOverlayProps,
}: Preview2DSurfaceProps) {
  return (
    <div
      className="relative flex h-full w-full items-center justify-center overflow-hidden"
      onMouseDown={onMouseDown}
    >
      <div
        ref={mapContainerRef}
        className={`absolute inset-0 overflow-hidden rounded-[24px] ${
          showMap ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        style={{ width: "100%", height: "100%" }}
      />
      <PreviewMapStatusOverlay {...mapStatusOverlayProps} />
      {previewMode === "2d" ? <PreviewCanvasHud {...canvasHudProps} /> : null}
      {showGeneratedPlan && planPreviewUrl && !showMap ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          ref={previewImageRef}
          data-testid="generated-plan-preview"
          src={planPreviewUrl}
          alt="Generated plan preview"
          className={`pointer-events-none h-full w-full object-contain ${
            placementMode || allowEdits ? "cursor-crosshair" : "cursor-default"
          }`}
          onLoad={() => updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds)}
        />
      ) : !showMap && !hasLiveObjects ? (
        <div className="flex h-full w-full items-center justify-center text-sm text-slate-400">
          Add objects to start building the site. Then click Place and drop them here.
        </div>
      ) : null}
      {overlayBoundsResolved && previewMode === "2d" && !showGeneratedPlan ? (
        <Preview2DOverlayStack {...overlayStackProps} />
      ) : null}
      {cadWindowSelect ? (
        <div
          data-testid="cad-window-select-marquee"
          data-selection-mode={cadWindowSelect.currentX < cadWindowSelect.startX ? "crossing" : "window"}
          className={`pointer-events-none absolute z-[65] rounded-sm border shadow-[0_0_0_1px_rgba(14,165,233,0.18)] ${
            cadWindowSelect.currentX < cadWindowSelect.startX
              ? "border-emerald-500 bg-emerald-400/12"
              : "border-sky-500 bg-sky-400/12"
          }`}
          style={{
            left: Math.min(cadWindowSelect.startX, cadWindowSelect.currentX) - cadWindowSelect.containerLeft,
            top: Math.min(cadWindowSelect.startY, cadWindowSelect.currentY) - cadWindowSelect.containerTop,
            width: Math.abs(cadWindowSelect.currentX - cadWindowSelect.startX),
            height: Math.abs(cadWindowSelect.currentY - cadWindowSelect.startY),
          }}
        />
      ) : null}
      {planAnnotationOverlayProps ? <PreviewPlanAnnotationOverlay {...planAnnotationOverlayProps} /> : null}
    </div>
  );
}
