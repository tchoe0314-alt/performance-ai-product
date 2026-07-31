import type { ComponentProps, MouseEvent as ReactMouseEvent, MutableRefObject } from "react";
import type mapboxgl from "mapbox-gl";

import { PreviewAnalysisPathsOverlay } from "./PreviewAnalysisPathsOverlay";
import { PreviewEditableObjectHitTargets } from "./PreviewEditableObjectHitTargets";
import { PreviewPlanCanvasLayers } from "./PreviewPlanCanvasLayers";
import { PreviewSuggestedObjectHitTargets } from "./PreviewSuggestedObjectHitTargets";
import { PreviewWaterFireFlowHitTargets } from "./PreviewWaterFireFlowHitTargets";

type Preview2DOverlayStackProps = {
  drawMode: string;
  draftPointCount: number;
  overlayPointerEvents: string;
  viewportTransformStyle: { transform: string };
  focusTransform: { scale: number; tx: number; ty: number } | null;
  showMap: boolean;
  mapLocked: boolean;
  previewInteraction: "static" | "edit";
  placementMode: boolean;
  mapRef: MutableRefObject<mapboxgl.Map | null>;
  mapDragActiveRef: MutableRefObject<boolean>;
  mapDragRef: MutableRefObject<{ x: number; y: number } | null>;
  analysisFocusLocked?: boolean;
  onClearHighlights?: () => void;
  beginCadWindowSelect: (event: ReactMouseEvent<HTMLDivElement>) => boolean;
  planCanvasLayersProps: ComponentProps<typeof PreviewPlanCanvasLayers>;
  waterFireFlowHitTargetsProps: ComponentProps<typeof PreviewWaterFireFlowHitTargets>;
  editableObjectHitTargetsProps: ComponentProps<typeof PreviewEditableObjectHitTargets>;
  suggestedObjectHitTargetsProps: ComponentProps<typeof PreviewSuggestedObjectHitTargets>;
  analysisPathsOverlayProps: ComponentProps<typeof PreviewAnalysisPathsOverlay>;
};

export function Preview2DOverlayStack({
  drawMode,
  draftPointCount,
  overlayPointerEvents,
  viewportTransformStyle,
  focusTransform,
  showMap,
  mapLocked,
  previewInteraction,
  placementMode,
  mapRef,
  mapDragActiveRef,
  mapDragRef,
  analysisFocusLocked,
  onClearHighlights,
  beginCadWindowSelect,
  planCanvasLayersProps,
  waterFireFlowHitTargetsProps,
  editableObjectHitTargetsProps,
  suggestedObjectHitTargetsProps,
  analysisPathsOverlayProps,
}: Preview2DOverlayStackProps) {
  return (
    <>
      <PreviewPlanCanvasLayers {...planCanvasLayersProps} />
      <div
        data-testid="preview-drawing-surface"
        data-draw-mode={drawMode}
        data-draft-point-count={draftPointCount}
        aria-label="Drawing surface"
        className={`absolute inset-0 ${drawMode !== "select" && drawMode !== "pan" ? "z-[35]" : "z-[14]"} ${
          drawMode === "select"
            ? "pointer-events-none"
            : drawMode === "pan"
              ? "pointer-events-auto cursor-grab active:cursor-grabbing"
              : "pointer-events-auto cursor-crosshair"
        }`}
      />
      <div
        data-testid="preview-drawing-overlays"
        className={`${overlayPointerEvents} absolute inset-0 z-[15]`}
        style={{
          transformOrigin: "top left",
          transform: `${viewportTransformStyle.transform}${
            focusTransform
              ? ` translate(50%, 50%) scale(${focusTransform.scale}) translate(-${focusTransform.tx * 100}%, -${focusTransform.ty * 100}%)`
              : ""
          }`,
        }}
        onMouseDown={(event) => {
          if (beginCadWindowSelect(event)) return;
          if (!showMap || mapLocked) return;
          if (previewInteraction !== "edit") return;
          if (placementMode) return;
          if ((event.target as HTMLElement)?.closest?.("[data-object-overlay]")) return;
          mapDragActiveRef.current = true;
          mapDragRef.current = { x: event.clientX, y: event.clientY };
        }}
        onWheel={(event) => {
          if (!showMap || mapLocked) return;
          if (previewInteraction !== "edit") return;
          if (!mapRef.current) return;
          event.preventDefault();
          const map = mapRef.current;
          const zoom = map.getZoom();
          const nextZoom = zoom + (event.deltaY < 0 ? 0.4 : -0.4);
          map.zoomTo(nextZoom, { animate: false });
        }}
        onClick={() => {
          if (analysisFocusLocked) return;
          onClearHighlights?.();
        }}
      >
        <PreviewWaterFireFlowHitTargets {...waterFireFlowHitTargetsProps} />
        <PreviewEditableObjectHitTargets {...editableObjectHitTargetsProps} />
        <PreviewSuggestedObjectHitTargets {...suggestedObjectHitTargetsProps} />
        <PreviewAnalysisPathsOverlay {...analysisPathsOverlayProps} />
      </div>
    </>
  );
}
