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
  presentationActive: boolean;
  showMap: boolean;
  mapLocked: boolean;
  previewInteraction: "static" | "edit";
  mapRef: MutableRefObject<mapboxgl.Map | null>;
  analysisFocusLocked?: boolean;
  showProposedOverlays: boolean;
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
  presentationActive,
  showMap,
  mapLocked,
  previewInteraction,
  mapRef,
  analysisFocusLocked,
  showProposedOverlays,
  onClearHighlights,
  beginCadWindowSelect,
  planCanvasLayersProps,
  waterFireFlowHitTargetsProps,
  editableObjectHitTargetsProps,
  suggestedObjectHitTargetsProps,
  analysisPathsOverlayProps,
}: Preview2DOverlayStackProps) {
  const interactionBounds = planCanvasLayersProps.overlayBoundsResolved;
  return (
    <>
      <PreviewPlanCanvasLayers {...planCanvasLayersProps} />
      {!presentationActive ? (
        <>
          <div
            data-testid="preview-drawing-surface"
            data-draw-mode={drawMode}
            data-draft-point-count={draftPointCount}
            role="region"
            aria-label="Drawing surface"
            className={`absolute inset-0 ${drawMode !== "select" && drawMode !== "pan" ? "z-[35]" : "z-[14]"} ${
              drawMode === "select"
                ? "pointer-events-none"
                : drawMode === "pan"
                  ? showMap
                    ? "pointer-events-none"
                    : "pointer-events-auto cursor-grab active:cursor-grabbing"
                  : "pointer-events-auto cursor-crosshair"
            }`}
          />
          <div
            data-testid="preview-drawing-overlays"
            className={`${overlayPointerEvents} absolute z-[15]`}
            style={{
              left: interactionBounds?.left ?? 0,
              top: interactionBounds?.top ?? 0,
              width: interactionBounds?.width ?? "100%",
              height: interactionBounds?.height ?? "100%",
              transformOrigin: "top left",
              transform: viewportTransformStyle.transform,
            }}
            onMouseDown={(event) => {
              beginCadWindowSelect(event);
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
            {showProposedOverlays ? <PreviewWaterFireFlowHitTargets {...waterFireFlowHitTargetsProps} /> : null}
            <PreviewEditableObjectHitTargets {...editableObjectHitTargetsProps} />
            <PreviewSuggestedObjectHitTargets {...suggestedObjectHitTargetsProps} />
            {showProposedOverlays ? <PreviewAnalysisPathsOverlay {...analysisPathsOverlayProps} /> : null}
          </div>
        </>
      ) : null}
    </>
  );
}
