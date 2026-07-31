import type { Dispatch, MouseEvent as ReactMouseEvent, MutableRefObject, Ref, SetStateAction } from "react";

import type { BuildingPlacement } from "../types";
import { resolveSourceState } from "../utils/previewGeometryTruth";
import type { PreviewSemanticLayer } from "../utils/previewSemanticLayers";
import {
  isPreviewSemanticLayerVisible,
  semanticLayerForPlacement,
} from "../utils/previewSemanticLayers";
import {
  getPreviewObjectBorderColor,
  getPreviewObjectOutlineColor,
} from "../utils/previewObjectBorderStyles";
import { resolvePreviewVisualKind } from "../utils/previewVisualStyles";
import { PreviewObjectHoverCard } from "./PreviewObjectHoverCard";
import { PreviewRectObjectChrome } from "./PreviewRectObjectChrome";
import { PreviewSelectedObjectQuickToolbar } from "./PreviewSelectedObjectQuickToolbar";
import { PreviewSelectionAffordances } from "./PreviewSelectionAffordances";
import type { PreviewHoverDetail } from "../utils/previewHoverDetails";

type SelectionIndex = { id: string; index: number } | null;
type PreviewRectPercent = { left: number; top: number; width: number; height: number };
type PreviewEditCapabilities = {
  movable: boolean;
  resizable: boolean;
  rotatable: boolean;
  deletable: boolean;
};
type LastPolylineEdit = {
  id: string;
  geometry: Array<[number, number]>;
  x: number;
  y: number;
  w: number;
  d: number;
  ts: number;
};
type LastRectEdit = {
  id: string;
  snapshot: BuildingPlacement;
  action: "update" | "delete" | "add";
  ts: number;
};

type PreviewEditableObjectHitTargetsProps = {
  visibleCadObjects: BuildingPlacement[];
  semanticLayerVisibility?: Partial<Record<PreviewSemanticLayer, boolean>>;
  previewInteraction: "static" | "edit";
  siteLocked: boolean;
  showSiteBounds: boolean;
  showMap: boolean;
  drawMode: string;
  selectedBuildingId: string | null;
  analysisHighlight?: { buildingId: string; accessId: string; pathId: string } | null;
  previewQuality: "standard" | "high";
  isHighQuality: boolean;
  allowEdits: boolean;
  passiveOverlayPointerEvents: string;
  drawingOwnsCanvasHits: boolean;
  draggingMode: string | null;
  draggingVertex: SelectionIndex;
  hoveredVertex: SelectionIndex;
  selectedVertex: SelectionIndex;
  hoveredSegment: SelectionIndex;
  lastPolylineEdit: LastPolylineEdit | null;
  lastRectEdit: LastRectEdit | null;
  polylineInsertHintDismissed: boolean;
  polylineSegmentRef?: Ref<SVGSVGElement>;
  hoveredObjectId: string | null;
  objectHoverDetails: PreviewHoverDetail[];
  selectedDeletableObject: BuildingPlacement | null;
  cadCommandStatusDisplay: string;
  suppressNextObjectClickRef: MutableRefObject<boolean>;
  getEditCapabilities: (item: BuildingPlacement) => PreviewEditCapabilities;
  interactiveRectPercent: (item: BuildingPlacement) => PreviewRectPercent;
  rectIntersectsPreview: (rect: PreviewRectPercent) => boolean;
  resolveObjectHitZIndex: (item: BuildingPlacement, rect: PreviewRectPercent, selected: boolean) => number;
  shouldRevealObjectLabel: (item: BuildingPlacement) => boolean;
  handleBuildingMouseDown: (
    event: ReactMouseEvent<HTMLElement>,
    item: BuildingPlacement,
    mode?: "move" | "resize" | "rotate",
  ) => void;
  onSelectBuilding: (id: string | null) => void;
  setSelectedVertex: Dispatch<SetStateAction<SelectionIndex>>;
  setHoveredObjectId: Dispatch<SetStateAction<string | null>>;
  setHoveredVertex: Dispatch<SetStateAction<SelectionIndex>>;
  setHoveredSegment: Dispatch<SetStateAction<SelectionIndex>>;
  setLastPolylineEdit: Dispatch<SetStateAction<LastPolylineEdit | null>>;
  setLastRectEdit: Dispatch<SetStateAction<LastRectEdit | null>>;
  setDraggingBuildingId: Dispatch<SetStateAction<string | null>>;
  setDraggingMode: Dispatch<SetStateAction<"move" | "resize" | "rotate" | "vertex" | null>>;
  setDraggingVertex: Dispatch<SetStateAction<SelectionIndex>>;
  runCadCommand: (commandOverride?: string) => void;
  copySelectedCadObjectsByVector: (vector: [number, number]) => void;
  transformSelectedCadObjects: (transform: "move" | "rotate" | "scale") => void;
  pushCadCommandFeedback: (command: string, status: "applied" | "blocked" | "info", message: string) => void;
  onRemoveBuilding: (id: string) => void;
  onUpdateSuggested: (id: string, updates: Partial<BuildingPlacement>) => void;
  onUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  insertVertexOnSegment: (
    event: ReactMouseEvent<SVGLineElement>,
    item: BuildingPlacement,
    index: number,
  ) => void;
  applyPolylineUndo: () => void;
  deleteSelectedVertex: () => void;
  applyRectUndo: () => void;
};

export function PreviewEditableObjectHitTargets({
  visibleCadObjects,
  semanticLayerVisibility = {},
  previewInteraction,
  siteLocked,
  showSiteBounds,
  showMap,
  drawMode,
  selectedBuildingId,
  analysisHighlight,
  previewQuality,
  isHighQuality,
  allowEdits,
  passiveOverlayPointerEvents,
  drawingOwnsCanvasHits,
  draggingMode,
  draggingVertex,
  hoveredVertex,
  selectedVertex,
  hoveredSegment,
  lastPolylineEdit,
  lastRectEdit,
  polylineInsertHintDismissed,
  polylineSegmentRef,
  hoveredObjectId,
  objectHoverDetails,
  selectedDeletableObject,
  cadCommandStatusDisplay,
  suppressNextObjectClickRef,
  getEditCapabilities,
  interactiveRectPercent,
  rectIntersectsPreview,
  resolveObjectHitZIndex,
  shouldRevealObjectLabel,
  handleBuildingMouseDown,
  onSelectBuilding,
  setSelectedVertex,
  setHoveredObjectId,
  setHoveredVertex,
  setHoveredSegment,
  setLastPolylineEdit,
  setLastRectEdit,
  setDraggingBuildingId,
  setDraggingMode,
  setDraggingVertex,
  runCadCommand,
  copySelectedCadObjectsByVector,
  transformSelectedCadObjects,
  pushCadCommandFeedback,
  onRemoveBuilding,
  onUpdateSuggested,
  onUpdateBuilding,
  insertVertexOnSegment,
  applyPolylineUndo,
  deleteSelectedVertex,
  applyRectUndo,
}: PreviewEditableObjectHitTargetsProps) {
  return (
    <>
      {visibleCadObjects
        .filter((item) => {
          if (!isPreviewSemanticLayerVisible(semanticLayerForPlacement(item), semanticLayerVisibility)) {
            return false;
          }
          const editableSiteBox =
            item.type === "site" && previewInteraction === "edit" && !siteLocked && showSiteBounds && !showMap;
          return (
            (item.type !== "site" || editableSiteBox) &&
            item.placed &&
            Number.isFinite(item.x) &&
            Number.isFinite(item.y)
          );
        })
        .map((item) => {
          const caps = getEditCapabilities(item);
          const isSelected = selectedBuildingId === item.id;
          const rectPct = interactiveRectPercent(item);
          const rotation = showMap ? 0 : (item.rotation ?? 0);
          const borderColor = getPreviewObjectBorderColor(item, { highQuality: previewQuality === "high" });
          const outlineColor = getPreviewObjectOutlineColor(item);
          const isAccessHighlight =
            analysisHighlight &&
            (analysisHighlight.buildingId === item.id || analysisHighlight.accessId === item.id);
          const isPolyline = item.geometryType === "polyline";
          const isPolygon = item.geometryType === "polygon";
          const isEditableVertexGeometry = isPolyline || isPolygon;
          const isCustomArea = isPolygon;
          const showBox = !isPolyline && !isCustomArea;
          const showBoxChrome = showBox && (isSelected || Boolean(isAccessHighlight));
          const showQuickSelectionActions = isSelected && drawMode === "select";
          const showSelectionAffordances = showQuickSelectionActions && allowEdits;
          const isSite = item.type === "site";
          const visualKind = resolvePreviewVisualKind(item);
          const sourceState = resolveSourceState(item);
          if (!rectIntersectsPreview(rectPct)) return null;
          const allowItemInteraction =
            drawMode === "select" &&
            (!isSite || (previewInteraction === "edit" && !siteLocked));
          const hitZIndex = resolveObjectHitZIndex(item, rectPct, isSelected);
          const overlayZIndex = hitZIndex;
          const useSegmentHitTargets =
            allowItemInteraction &&
            isPolyline &&
            visualKind === "utility" &&
            Array.isArray(item.geometry) &&
            item.geometry.length >= 2 &&
            rectPct.width > 0 &&
            rectPct.height > 0;
          const polylineBounds = useSegmentHitTargets
            ? (item.geometry as Array<[number, number]>).reduce(
                (bounds, [x, y]) => ({
                  minX: Math.min(bounds.minX, x),
                  minY: Math.min(bounds.minY, y),
                  maxX: Math.max(bounds.maxX, x),
                  maxY: Math.max(bounds.maxY, y),
                }),
                {
                  minX: Number.POSITIVE_INFINITY,
                  minY: Number.POSITIVE_INFINITY,
                  maxX: Number.NEGATIVE_INFINITY,
                  maxY: Number.NEGATIVE_INFINITY,
                },
              )
            : null;
          const localPolylinePoints =
            useSegmentHitTargets && polylineBounds
              ? (item.geometry as Array<[number, number]>).map(([x, y]) => {
                  const spanX = Math.max(polylineBounds.maxX - polylineBounds.minX, 1);
                  const spanY = Math.max(polylineBounds.maxY - polylineBounds.minY, 1);
                  return {
                    x: ((x - polylineBounds.minX) / spanX) * 100,
                    y: ((y - polylineBounds.minY) / spanY) * 100,
                  };
                })
              : [];
          const overlayPointerClass =
            useSegmentHitTargets
              ? "pointer-events-none"
              : allowItemInteraction
                ? passiveOverlayPointerEvents
                : "pointer-events-none";
          return (
            <div
              key={item.id}
              data-object-overlay
              data-cad-object-id={item.id}
              data-semantic-layer={semanticLayerForPlacement(item)}
              aria-label={`Select ${item.label || item.type || "Draft object"}`}
              data-preview-quality={previewQuality}
              data-visual-kind={visualKind}
              data-source-state={sourceState}
              data-hit-priority={hitZIndex}
              className={`${overlayPointerClass} absolute z-[30]`}
              style={{
                left: `${rectPct.left}%`,
                top: `${rectPct.top}%`,
                width: `${rectPct.width}%`,
                height: `${rectPct.height}%`,
                zIndex: overlayZIndex,
                scrollMarginBottom: "10rem",
                transform: `rotate(${rotation}deg)`,
                transformOrigin: "center",
                cursor: caps.movable ? (isPolyline ? "grab" : "move") : "default",
              }}
              onMouseDown={(event) => {
                if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                if (draggingMode === "vertex" || hoveredSegment?.id === item.id) return;
                handleBuildingMouseDown(event, item, "move");
              }}
              onMouseEnter={() => {
                if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                setHoveredObjectId(item.id);
              }}
              onMouseLeave={() => {
                setHoveredObjectId(null);
                setHoveredVertex(null);
              }}
              onClick={(event) => {
                if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                if (suppressNextObjectClickRef.current) {
                  suppressNextObjectClickRef.current = false;
                  event.stopPropagation();
                  return;
                }
                event.stopPropagation();
                setSelectedVertex(null);
                onSelectBuilding(item.id);
              }}
            >
              {useSegmentHitTargets
                ? localPolylinePoints.slice(0, -1).map((point, segmentIndex) => {
                    const next = localPolylinePoints[segmentIndex + 1];
                    if (!next) return null;
                    const dx = next.x - point.x;
                    const dy = next.y - point.y;
                    const length = Math.max(Math.hypot(dx, dy), 1);
                    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
                    return (
                      <button
                        key={`polyline-hit-${item.id}-${segmentIndex}`}
                        type="button"
                        data-cad-object-hit-id={item.id}
                        aria-label={`Select ${item.label || item.type || "Draft object"} segment ${segmentIndex + 1}`}
                        className="pointer-events-auto absolute appearance-none border-0 p-0"
                        style={{
                          left: `${point.x}%`,
                          top: `${point.y}%`,
                          width: `${length}%`,
                          height: "12%",
                          minHeight: "12px",
                          transform: `translateY(-50%) rotate(${angle}deg)`,
                          transformOrigin: "left center",
                          backgroundColor: "rgba(15,23,42,0.001)",
                          cursor: caps.movable ? "grab" : "default",
                        }}
                        onMouseDown={(event) => {
                          if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                          event.stopPropagation();
                          setSelectedVertex(null);
                          onSelectBuilding(item.id);
                        }}
                        onMouseEnter={() => {
                          if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                          setHoveredObjectId(item.id);
                        }}
                        onClick={(event) => {
                          if (drawingOwnsCanvasHits || !allowItemInteraction) return;
                          event.stopPropagation();
                          setSelectedVertex(null);
                          onSelectBuilding(item.id);
                        }}
                      />
                    );
                  })
                : null}
              <PreviewRectObjectChrome
                showBox={showBox}
                showBoxChrome={showBoxChrome}
                selected={isSelected}
                accessHighlighted={Boolean(isAccessHighlight)}
                highQuality={isHighQuality}
                visualKind={visualKind}
                borderColor={borderColor}
                outlineColor={outlineColor}
              />
              {showQuickSelectionActions ? (
                <PreviewSelectedObjectQuickToolbar
                  item={item}
                  canDelete={Boolean(selectedDeletableObject && selectedDeletableObject.id === item.id)}
                  statusText={cadCommandStatusDisplay}
                  onMeasure={() => runCadCommand("DIST")}
                  onCopy={() => copySelectedCadObjectsByVector([10, 10])}
                  onRotate={() => transformSelectedCadObjects("rotate")}
                  onInspect={() => {
                    onSelectBuilding(item.id);
                    pushCadCommandFeedback("INSPECT", "info", `INSPECT selected ${item.label || "draft object"}. Use Object Manager for full properties.`);
                  }}
                  onDelete={() => {
                    if (!selectedDeletableObject || selectedDeletableObject.id !== item.id) {
                      pushCadCommandFeedback("DELETE", "blocked", "DELETE blocked: selected object is locked or required evidence.");
                      return;
                    }
                    setLastRectEdit({
                      id: item.id,
                      snapshot: { ...item },
                      action: "delete",
                      ts: Date.now(),
                    });
                    onRemoveBuilding(item.id);
                    pushCadCommandFeedback("DELETE", "applied", `DELETE removed ${item.label || "selected draft object"}.`);
                  }}
                />
              ) : null}
              <PreviewSelectionAffordances
                item={item}
                caps={caps}
                show={showSelectionAffordances}
                isEditableVertexGeometry={isEditableVertexGeometry}
                isPolyline={isPolyline}
                isPolygon={isPolygon}
                showObjectLabel={shouldRevealObjectLabel(item)}
                draggingMode={draggingMode}
                draggingVertex={draggingVertex}
                hoveredVertex={hoveredVertex}
                selectedVertex={selectedVertex}
                hoveredSegment={hoveredSegment}
                lastPolylineEditId={lastPolylineEdit?.id ?? null}
                lastRectEditId={lastRectEdit?.id ?? null}
                polylineInsertHintDismissed={polylineInsertHintDismissed}
                segmentRef={polylineSegmentRef}
                onVertexHover={setHoveredVertex}
                onSegmentHover={setHoveredSegment}
                onVertexMouseDown={(event, target, idx) => {
                  event.preventDefault();
                  event.stopPropagation();
                  if (Array.isArray(target.geometry)) {
                    setLastPolylineEdit({
                      id: target.id,
                      geometry: (target.geometry as Array<[number, number]>).map((pt) => [
                        pt[0],
                        pt[1],
                      ]),
                      x: target.x ?? 0,
                      y: target.y ?? 0,
                      w: target.w,
                      d: target.d,
                      ts: Date.now(),
                    });
                  }
                  setDraggingBuildingId(target.id);
                  setDraggingMode("vertex");
                  setDraggingVertex({ id: target.id, index: idx });
                  setSelectedVertex({ id: target.id, index: idx });
                  onSelectBuilding(target.id);
                }}
                onSegmentMouseDown={(event) => event.stopPropagation()}
                onSegmentClick={(event, target, idx) => {
                  event.preventDefault();
                  event.stopPropagation();
                  insertVertexOnSegment(event, target, idx);
                }}
                onPolylineUndo={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  applyPolylineUndo();
                }}
                onDeleteVertex={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  deleteSelectedVertex();
                }}
                onRectUndo={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  applyRectUndo();
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
                onDeleteClick={(event) => {
                  event.stopPropagation();
                  setLastRectEdit({
                    id: item.id,
                    snapshot: { ...item },
                    action: "delete",
                    ts: Date.now(),
                  });
                  onRemoveBuilding(item.id);
                }}
              />
              {hoveredObjectId === item.id ? <PreviewObjectHoverCard details={objectHoverDetails} /> : null}
            </div>
          );
        })}
    </>
  );
}
