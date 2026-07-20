import type { Dispatch, MouseEvent as ReactMouseEvent, RefObject, SetStateAction } from "react";

import type { BuildingPlacement } from "../types";
import type { PreviewAnnotationLabel, PreviewHoverDetail } from "../utils/previewHoverDetails";
import {
  getPreviewObjectBorderColor,
  getPreviewObjectOutlineColor,
} from "../utils/previewObjectBorderStyles";
import { formatCount, formatMetric } from "../utils/formatting";
import { PreviewAnnotationHoverCard } from "./PreviewAnnotationHoverCard";
import {
  PreviewFullscreenEditableObjectOverlay,
  PreviewFullscreenSuggestedObjectOverlay,
} from "./PreviewFullscreenObjectOverlays";
import {
  PreviewFullscreenHeader,
  PreviewPlanAnnotationOverlay,
} from "./PreviewPlanAnnotationOverlay";
import { PreviewMetricOverlayCard } from "./PreviewMetricOverlayCard";
import type { PreviewPanelProps } from "./previewPanelTypes";

type PreviewBounds = { left: number; top: number; width: number; height: number };
type PercentRect = { left: number; top: number; width: number; height: number };

type PreviewGeneratedPlanFullscreenProps = {
  open: boolean;
  planPreviewUrl: string;
  fullscreenRef: RefObject<HTMLDivElement | null>;
  fullscreenImageRef: RefObject<HTMLImageElement | null>;
  fullscreenImageBounds: PreviewBounds | null;
  setFullscreenImageBounds: Dispatch<SetStateAction<PreviewBounds | null>>;
  updateImageBounds: (
    containerRef: RefObject<HTMLDivElement | null>,
    imageRef: RefObject<HTMLImageElement | null>,
    setBounds: Dispatch<SetStateAction<PreviewBounds | null>>,
  ) => void;
  onCloseFullscreen: () => void;
  onPlaceObject: PreviewPanelProps["onPlaceObject"];
  updateDraggedBuilding: (event: ReactMouseEvent<HTMLDivElement>, bounds: PreviewBounds) => void;
  resolveHover: (
    event: ReactMouseEvent<HTMLDivElement>,
    containerRef: RefObject<HTMLDivElement | null>,
    bounds: PreviewBounds | null,
    setPoint: Dispatch<SetStateAction<{ x: number; y: number } | null>>,
  ) => void;
  clearScheduledHoverAnnotationState: (
    setPoint: Dispatch<SetStateAction<{ x: number; y: number } | null>>,
  ) => void;
  setFullscreenHoverPoint: Dispatch<SetStateAction<{ x: number; y: number } | null>>;
  setDraggingBuildingId: Dispatch<SetStateAction<string | null>>;
  setDraggingMode: Dispatch<SetStateAction<"move" | "resize" | "rotate" | "vertex" | null>>;
  setDraggingVertex: Dispatch<SetStateAction<{ id: string; index: number } | null>>;
  resolvePlacement: (
    event: ReactMouseEvent<HTMLDivElement>,
    containerRef: RefObject<HTMLDivElement | null>,
    bounds: PreviewBounds | null,
  ) => void;
  placementMode: boolean;
  showHover: boolean;
  hoveredAnnotation: PreviewAnnotationLabel | null;
  setPinnedAnnotation: Dispatch<SetStateAction<PreviewAnnotationLabel | null>>;
  planPreviewAnnotations: PreviewPanelProps["planPreviewAnnotations"];
  selectedIssueLabel: string;
  activeHighlightBounds: PreviewAnnotationLabel["bounds"] | null | undefined;
  issueHighlightBounds: PreviewAnnotationLabel["bounds"] | null | undefined;
  siteLocked: boolean;
  lotWidth: number;
  lotHeight: number;
  visibleCadObjects: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
  interactiveRectPercent: (item: BuildingPlacement, map: null) => PercentRect;
  rectIntersectsPreview: (rect: PercentRect) => boolean;
  resolveObjectHitZIndex: (item: BuildingPlacement, rect: PercentRect, selected: boolean) => number;
  selectedBuildingId: string | null;
  drawMode: string;
  previewInteraction: "static" | "edit";
  handleBuildingMouseDown: (
    event: ReactMouseEvent<HTMLElement>,
    item: BuildingPlacement,
    mode?: "move" | "resize" | "rotate",
  ) => void;
  onSelectBuilding: PreviewPanelProps["onSelectBuilding"];
  setLastRectEdit: Dispatch<
    SetStateAction<{ id: string; snapshot: BuildingPlacement; action: "update" | "delete" | "add"; ts: number } | null>
  >;
  onUpdateSuggested: PreviewPanelProps["onUpdateSuggested"];
  onUpdateBuilding: PreviewPanelProps["onUpdateBuilding"];
  setHoveredObjectId: Dispatch<SetStateAction<string | null>>;
  activeAnnotation: PreviewAnnotationLabel | null;
  hoverDetails: PreviewHoverDetail[];
  fullscreenHoverPoint: { x: number; y: number } | null;
  allowEdits: boolean;
  showMeasurements: boolean;
  showCalculations: boolean;
  measurementOverlayStats: PreviewPanelProps["measurementOverlayStats"];
  calculationOverlayStats: PreviewPanelProps["calculationOverlayStats"];
};

export function PreviewGeneratedPlanFullscreen({
  open,
  planPreviewUrl,
  fullscreenRef,
  fullscreenImageRef,
  fullscreenImageBounds,
  setFullscreenImageBounds,
  updateImageBounds,
  onCloseFullscreen,
  onPlaceObject,
  updateDraggedBuilding,
  resolveHover,
  clearScheduledHoverAnnotationState,
  setFullscreenHoverPoint,
  setDraggingBuildingId,
  setDraggingMode,
  setDraggingVertex,
  resolvePlacement,
  placementMode,
  showHover,
  hoveredAnnotation,
  setPinnedAnnotation,
  planPreviewAnnotations,
  selectedIssueLabel,
  activeHighlightBounds,
  issueHighlightBounds,
  siteLocked,
  lotWidth,
  lotHeight,
  visibleCadObjects,
  suggestedPlacements,
  interactiveRectPercent,
  rectIntersectsPreview,
  resolveObjectHitZIndex,
  selectedBuildingId,
  drawMode,
  previewInteraction,
  handleBuildingMouseDown,
  onSelectBuilding,
  setLastRectEdit,
  onUpdateSuggested,
  onUpdateBuilding,
  setHoveredObjectId,
  activeAnnotation,
  hoverDetails,
  fullscreenHoverPoint,
  allowEdits,
  showMeasurements,
  showCalculations,
  measurementOverlayStats,
  calculationOverlayStats,
}: PreviewGeneratedPlanFullscreenProps) {
  if (!open || !planPreviewUrl) return null;

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/92 backdrop-blur-sm">
      <div className="flex h-full w-full flex-col bg-slate-950">
        <PreviewFullscreenHeader
          description="Inspect the latest engineered plan without the sidebar chrome."
          onClose={onCloseFullscreen}
        />
        <div className="flex min-h-0 flex-1 items-center justify-center p-0">
          <div
            ref={fullscreenRef}
            className="relative h-full w-full"
            onDragOver={(event) => {
              event.preventDefault();
            }}
            onDrop={(event) => {
              event.preventDefault();
              const payload = event.dataTransfer?.getData("civora-object-id");
              if (!payload) return;
              onPlaceObject(payload, {
                x: Math.min(Math.max((event.clientX - (fullscreenImageBounds?.left ?? 0)) / Math.max(fullscreenImageBounds?.width ?? 1, 1), 0), 1),
                y: Math.min(Math.max((event.clientY - (fullscreenImageBounds?.top ?? 0)) / Math.max(fullscreenImageBounds?.height ?? 1, 1), 0), 1),
              });
            }}
            onMouseMove={(event) => {
              if (fullscreenImageBounds) {
                updateDraggedBuilding(event, fullscreenImageBounds);
              }
              resolveHover(event, fullscreenRef, fullscreenImageBounds, setFullscreenHoverPoint);
            }}
            onMouseLeave={() => {
              clearScheduledHoverAnnotationState(setFullscreenHoverPoint);
              setDraggingBuildingId(null);
              setDraggingMode(null);
              setDraggingVertex(null);
            }}
            onMouseUp={() => {
              setDraggingBuildingId(null);
              setDraggingMode(null);
              setDraggingVertex(null);
            }}
            onClick={(event) => {
              if (placementMode) {
                resolvePlacement(event, fullscreenRef, fullscreenImageBounds);
                return;
              }
              if (!showHover || !hoveredAnnotation) return;
              setPinnedAnnotation((prev) =>
                prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
              );
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={fullscreenImageRef}
              src={planPreviewUrl}
              alt="Generated plan preview fullscreen"
              className="h-full w-full bg-white object-contain"
              onLoad={() => updateImageBounds(fullscreenRef, fullscreenImageRef, setFullscreenImageBounds)}
            />
            {showHover && !planPreviewAnnotations?.labels?.length ? (
              <div className="pointer-events-none absolute right-6 top-6 rounded-2xl border border-white/20 bg-slate-900/80 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-white">
                No hover labels yet. Refresh the preview to generate them.
              </div>
            ) : null}
            {planPreviewAnnotations?.labels?.length && fullscreenImageBounds ? (
              <>
                <PreviewPlanAnnotationOverlay
                  imageBounds={fullscreenImageBounds}
                  labels={planPreviewAnnotations.labels}
                  selectedIssueLabel={selectedIssueLabel}
                  showHover={showHover}
                  activeHighlightBounds={activeHighlightBounds ?? null}
                  issueHighlightBounds={issueHighlightBounds ?? null}
                  showUnlockedSiteFrame={!siteLocked && lotWidth > 0 && lotHeight > 0}
                />
                {visibleCadObjects
                  .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                  .map((item) => {
                    const rectPct = interactiveRectPercent(item, null);
                    if (!rectIntersectsPreview(rectPct)) return null;
                    const rotation = item.rotation ?? 0;
                    const isSite = item.type === "site";
                    const allowItemInteraction =
                      drawMode === "select" && (!isSite || (previewInteraction === "edit" && !siteLocked));
                    const hitZIndex = resolveObjectHitZIndex(item, rectPct, selectedBuildingId === item.id);
                    const borderColor = getPreviewObjectBorderColor(item);
                    const outlineColor = getPreviewObjectOutlineColor(item);
                    return (
                      <PreviewFullscreenEditableObjectOverlay
                        key={item.id}
                        rectPct={rectPct}
                        rotation={rotation}
                        hitZIndex={hitZIndex}
                        allowMapInteraction={false}
                        allowItemInteraction={allowItemInteraction}
                        placementMode={Boolean(placementMode)}
                        borderColor={borderColor}
                        outlineColor={outlineColor}
                        onMoveMouseDown={(event) => {
                          if (!allowItemInteraction) return;
                          handleBuildingMouseDown(event, item, "move");
                        }}
                        onSelect={(event) => {
                          if (!allowItemInteraction) return;
                          if (!placementMode) return;
                          event.stopPropagation();
                          onSelectBuilding(item.id);
                        }}
                        onRotateMouseDown={(event) => handleBuildingMouseDown(event, item, "rotate")}
                        onRotateClick={(event) => {
                          event.stopPropagation();
                          setLastRectEdit({
                            id: item.id,
                            snapshot: { ...item },
                            action: "update",
                            ts: Date.now(),
                          });
                          const nextRotation = (((item.rotation ?? 0) + 15) % 360 + 360) % 360;
                          if (item.source === "detected_from_image") {
                            onUpdateSuggested(item.id, { rotation: nextRotation });
                          } else {
                            onUpdateBuilding(item.id, { rotation: nextRotation });
                          }
                        }}
                        onResizeMouseDown={(event) => handleBuildingMouseDown(event, item, "resize")}
                      />
                    );
                  })}
                {suggestedPlacements
                  .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
                  .map((item) => {
                    const rectPct = interactiveRectPercent(item, null);
                    if (!rectIntersectsPreview(rectPct)) return null;
                    const rotation = item.rotation ?? 0;
                    const hitZIndex = resolveObjectHitZIndex(item, rectPct, selectedBuildingId === item.id);
                    const borderColor = getPreviewObjectBorderColor(item, { fallback: "border-slate-400" });
                    return (
                      <PreviewFullscreenSuggestedObjectOverlay
                        key={item.id}
                        item={item}
                        rectPct={rectPct}
                        rotation={rotation}
                        hitZIndex={hitZIndex}
                        borderColor={borderColor}
                        onHover={setHoveredObjectId}
                        onSelect={(event) => {
                          event.stopPropagation();
                          onSelectBuilding(item.id);
                        }}
                      />
                    );
                  })}
              </>
            ) : null}
            {showHover && activeAnnotation && fullscreenHoverPoint ? (
              <PreviewAnnotationHoverCard
                annotation={activeAnnotation}
                details={hoverDetails}
                point={fullscreenHoverPoint}
                maxLeft={620}
                maxTop={520}
              />
            ) : null}
            {allowEdits && showMeasurements ? (
              <PreviewMetricOverlayCard
                title="Measurements"
                position="top-left"
                stats={measurementOverlayStats}
                formatMetric={formatMetric}
                formatCount={formatCount}
              />
            ) : null}
            {allowEdits && showCalculations ? (
              <PreviewMetricOverlayCard
                title="Calculations"
                position="bottom-left"
                stats={calculationOverlayStats}
                formatMetric={formatMetric}
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
