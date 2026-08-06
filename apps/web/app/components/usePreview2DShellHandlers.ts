import { useMemo } from "react";
import type {
  Dispatch,
  DragEvent as ReactDragEvent,
  MouseEvent as ReactMouseEvent,
  MutableRefObject,
  RefObject,
  SetStateAction,
  WheelEvent as ReactWheelEvent,
} from "react";

import type { CanvasCamera } from "../utils/geometryTransforms";
import type { CadSnapKind } from "../utils/cadGeometryKernel";
import type { PreviewAnnotationLabel } from "../utils/previewHoverDetails";
import type { PreviewOverlayBounds } from "../utils/previewOverlayBounds";
import type { CadPoint } from "./previewPanelTypes";

type CadWindowSelect = {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  containerLeft: number;
  containerTop: number;
} | null;

type HoverPoint = { x: number; y: number };
type RotateDragStart = { x: number; value: number } | null;
type CanvasPanStart = { x: number; y: number; offsetX: number; offsetY: number } | null;

type Preview2DShellHandlersOptions = {
  allowMapInteraction: boolean;
  drawMode: string;
  overlayBoundsResolved: PreviewOverlayBounds | null;
  previewRef: RefObject<HTMLDivElement | null>;
  previewContainerBounds: PreviewOverlayBounds | null;
  previewMode: "2d" | "3d";
  showMap: boolean;
  lotWidth: number;
  lotHeight: number;
  draftPoints: Array<[number, number]>;
  canvasView: CanvasCamera;
  placementMode: boolean;
  showHover: boolean;
  hoverPoint: HoverPoint | null;
  hoveredAnnotation: PreviewAnnotationLabel | null;
  hoveredObjectId: string | null;
  cadWindowSelect: CadWindowSelect;
  cadWindowSelectRef: MutableRefObject<CadWindowSelect>;
  rotateDragStart: RotateDragStart;
  canvasPanStart: CanvasPanStart;
  suppressNextDrawClickRef: MutableRefObject<boolean>;
  suppressNextObjectClickRef: MutableRefObject<boolean>;
  userAdjustedCanvasViewRef: MutableRefObject<boolean>;
  onSetSiteRotationDeg?: (value: number) => void;
  handleDrawPointer: (event: ReactMouseEvent<HTMLDivElement>, bounds: PreviewOverlayBounds | null) => boolean;
  beginCadWindowSelect: (event: ReactMouseEvent<HTMLDivElement>) => boolean;
  finishCadWindowSelect: (windowRect: NonNullable<CadWindowSelect>) => void;
  onPlaceObject: (id: string, position: { x: number; y: number }) => void;
  screenToSitePoint: (
    clientX: number,
    clientY: number,
    containerRef: RefObject<HTMLDivElement | null>,
    bounds: PreviewOverlayBounds | null,
  ) => (CadPoint & { relX?: number; relY?: number }) | null;
  resolveCadSnapPoint: (point: CadPoint, basePoint: CadPoint | null) => CadPoint & { kind: CadSnapKind };
  scheduleDraftPointerState: (sitePoint: (CadPoint & { kind: CadSnapKind }) | null) => void;
  scheduleCanvasPanView: (nextView: { offsetX: number; offsetY: number }) => void;
  updateDraggedBuilding: (event: ReactMouseEvent<HTMLDivElement>, bounds: PreviewOverlayBounds) => void;
  resolveHover: (
    event: ReactMouseEvent<HTMLDivElement>,
    containerRef: RefObject<HTMLDivElement | null>,
    bounds: PreviewOverlayBounds | null,
    setPoint: Dispatch<SetStateAction<HoverPoint | null>>,
  ) => void;
  resolvePlacement: (
    event: ReactMouseEvent<HTMLDivElement>,
    containerRef: RefObject<HTMLDivElement | null>,
    bounds: PreviewOverlayBounds | null,
  ) => void;
  clearScheduledHoverAnnotationState: (setter: Dispatch<SetStateAction<HoverPoint | null>>) => void;
  scheduleCursorSitePoint: (point: CadPoint | null) => void;
  finishCanvasPanInteraction: () => void;
  clearScheduledPointerState: () => void;
  finishDraftGeometry: () => void;
  setHoverPoint: Dispatch<SetStateAction<HoverPoint | null>>;
  setHoveredObjectId: Dispatch<SetStateAction<string | null>>;
  setCadWindowSelect: Dispatch<SetStateAction<CadWindowSelect>>;
  setRotateDragStart: Dispatch<SetStateAction<RotateDragStart>>;
  setCanvasPanStart: Dispatch<SetStateAction<CanvasPanStart>>;
  setDraggingBuildingId: Dispatch<SetStateAction<string | null>>;
  setDraggingMode: Dispatch<SetStateAction<"move" | "resize" | "rotate" | "vertex" | null>>;
  setPinnedAnnotation: Dispatch<SetStateAction<PreviewAnnotationLabel | null>>;
  setCanvasView: Dispatch<SetStateAction<CanvasCamera>>;
};

export function usePreview2DShellHandlers({
  allowMapInteraction,
  drawMode,
  overlayBoundsResolved,
  previewRef,
  previewContainerBounds,
  previewMode,
  showMap,
  lotWidth,
  lotHeight,
  draftPoints,
  canvasView,
  placementMode,
  showHover,
  hoverPoint,
  hoveredAnnotation,
  hoveredObjectId,
  cadWindowSelect,
  cadWindowSelectRef,
  rotateDragStart,
  canvasPanStart,
  suppressNextDrawClickRef,
  suppressNextObjectClickRef,
  userAdjustedCanvasViewRef,
  onSetSiteRotationDeg,
  handleDrawPointer,
  beginCadWindowSelect,
  finishCadWindowSelect,
  onPlaceObject,
  screenToSitePoint,
  resolveCadSnapPoint,
  scheduleDraftPointerState,
  scheduleCanvasPanView,
  updateDraggedBuilding,
  resolveHover,
  resolvePlacement,
  clearScheduledHoverAnnotationState,
  scheduleCursorSitePoint,
  finishCanvasPanInteraction,
  clearScheduledPointerState,
  finishDraftGeometry,
  setHoverPoint,
  setHoveredObjectId,
  setCadWindowSelect,
  setRotateDragStart,
  setCanvasPanStart,
  setDraggingBuildingId,
  setDraggingMode,
  setPinnedAnnotation,
  setCanvasView,
}: Preview2DShellHandlersOptions) {
  return useMemo(() => ({
    onDragOver: (event: ReactDragEvent<HTMLDivElement>) => {
      event.preventDefault();
    },
    onMouseDownCapture: (event: ReactMouseEvent<HTMLDivElement>) => {
      if (allowMapInteraction) return;
      const target = event.target as HTMLElement | null;
      if (
        drawMode !== "select" &&
        !target?.closest?.("button,input,textarea,select,[role='button'],[data-no-window-select]")
      ) {
        if (handleDrawPointer(event, overlayBoundsResolved)) {
          suppressNextDrawClickRef.current = true;
          return;
        }
      }
      beginCadWindowSelect(event);
    },
    onDrop: (event: ReactDragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const payload = event.dataTransfer?.getData("civora-object-id");
      if (!payload) return;
      const rect = previewRef.current?.getBoundingClientRect();
      const bounds = overlayBoundsResolved ?? {
        left: 0,
        top: 0,
        width: rect?.width ?? 1,
        height: rect?.height ?? 1,
      };
      onPlaceObject(payload, {
        x: Math.min(
          Math.max((event.clientX - (rect?.left ?? 0) - bounds.left) / Math.max(bounds.width, 1), 0),
          1,
        ),
        y: Math.min(
          Math.max((event.clientY - (rect?.top ?? 0) - bounds.top) / Math.max(bounds.height, 1), 0),
          1,
        ),
      });
    },
    onMouseMove: (event: ReactMouseEvent<HTMLDivElement>) => {
      if (allowMapInteraction) return;
      if (cadWindowSelect) {
        setCadWindowSelect((current) =>
          current ? { ...current, currentX: event.clientX, currentY: event.clientY } : current,
        );
        return;
      }
      if (rotateDragStart && previewContainerBounds && onSetSiteRotationDeg) {
        const deltaX = event.clientX - rotateDragStart.x;
        const width = Math.max(previewContainerBounds.width, 1);
        const deltaDeg = (deltaX / width) * 180;
        const nextValue = rotateDragStart.value + deltaDeg;
        onSetSiteRotationDeg(Math.max(-180, Math.min(180, nextValue)));
        return;
      }
      if (canvasPanStart) {
        scheduleCanvasPanView({
          offsetX: canvasPanStart.offsetX + event.clientX - canvasPanStart.x,
          offsetY: canvasPanStart.offsetY + event.clientY - canvasPanStart.y,
        });
        return;
      }
      if (drawMode !== "select" && drawMode !== "pan" && overlayBoundsResolved) {
        const rawSitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, overlayBoundsResolved);
        const basePoint = draftPoints.length
          ? { x: draftPoints[draftPoints.length - 1][0], y: draftPoints[draftPoints.length - 1][1] }
          : null;
        const sitePoint = rawSitePoint ? resolveCadSnapPoint(rawSitePoint, basePoint) : null;
        scheduleDraftPointerState(sitePoint);
        return;
      }
      if (overlayBoundsResolved) {
        updateDraggedBuilding(event, overlayBoundsResolved);
      }
      if (showHover) {
        resolveHover(event, previewRef, overlayBoundsResolved, setHoverPoint);
      } else {
        if (hoverPoint || hoveredAnnotation) clearScheduledHoverAnnotationState(setHoverPoint);
        if (hoveredObjectId) setHoveredObjectId(null);
      }
      if (showHover && overlayBoundsResolved && lotWidth > 0 && lotHeight > 0 && previewRef.current) {
        const sitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, overlayBoundsResolved);
        scheduleCursorSitePoint(sitePoint);
      } else if (!showHover) {
        scheduleCursorSitePoint(null);
      } else {
        scheduleCursorSitePoint(null);
      }
    },
    onMouseLeave: () => {
      clearScheduledHoverAnnotationState(setHoverPoint);
      setHoveredObjectId(null);
      setDraggingBuildingId(null);
      setDraggingMode(null);
      finishCanvasPanInteraction();
      setCanvasPanStart(null);
      clearScheduledPointerState();
      if (!cadWindowSelect) setCadWindowSelect(null);
    },
    onMouseUp: () => {
      if (cadWindowSelect) {
        finishCadWindowSelect(cadWindowSelect);
        cadWindowSelectRef.current = null;
        setCadWindowSelect(null);
      }
      setDraggingBuildingId(null);
      setDraggingMode(null);
      setRotateDragStart(null);
      finishCanvasPanInteraction();
      setCanvasPanStart(null);
    },
    onClick: (event: ReactMouseEvent<HTMLDivElement>) => {
      if (suppressNextObjectClickRef.current) {
        suppressNextObjectClickRef.current = false;
        event.stopPropagation();
        return;
      }
      if (allowMapInteraction) return;
      if (drawMode !== "select") {
        if (suppressNextDrawClickRef.current) {
          suppressNextDrawClickRef.current = false;
          return;
        }
        if (handleDrawPointer(event, overlayBoundsResolved)) return;
      }
      if (placementMode) {
        resolvePlacement(event, previewRef, overlayBoundsResolved);
        return;
      }
      if (!showHover || !hoveredAnnotation) return;
      setPinnedAnnotation((prev) =>
        prev?.label === hoveredAnnotation.label ? null : hoveredAnnotation,
      );
    },
    onDoubleClick: (event: ReactMouseEvent<HTMLDivElement>) => {
      if (drawMode !== "site" && drawMode !== "polyline" && drawMode !== "polygon" && drawMode !== "rect") return;
      event.preventDefault();
      event.stopPropagation();
      finishDraftGeometry();
    },
    onWheel: (event: ReactWheelEvent<HTMLDivElement>) => {
      if (previewMode !== "2d" || !overlayBoundsResolved || showMap) return;
      userAdjustedCanvasViewRef.current = true;
      const nextScale = Math.min(
        Math.max(canvasView.scale + (event.deltaY < 0 ? 0.12 : -0.12), 0.55),
        4,
      );
      const rect = previewRef.current?.getBoundingClientRect();
      if (!rect) {
        setCanvasView((prev) => ({ ...prev, scale: nextScale }));
        return;
      }
      const localX = event.clientX - rect.left - overlayBoundsResolved.left;
      const localY = event.clientY - rect.top - overlayBoundsResolved.top;
      setCanvasView((prev) => {
        const ratio = nextScale / Math.max(prev.scale, 0.1);
        return {
          scale: nextScale,
          offsetX: localX - (localX - prev.offsetX) * ratio,
          offsetY: localY - (localY - prev.offsetY) * ratio,
        };
      });
    },
  }), [
    allowMapInteraction,
    beginCadWindowSelect,
    cadWindowSelect,
    cadWindowSelectRef,
    canvasPanStart,
    canvasView.scale,
    clearScheduledHoverAnnotationState,
    clearScheduledPointerState,
    draftPoints,
    drawMode,
    finishCadWindowSelect,
    finishCanvasPanInteraction,
    finishDraftGeometry,
    handleDrawPointer,
    hoverPoint,
    hoveredAnnotation,
    hoveredObjectId,
    lotHeight,
    lotWidth,
    onPlaceObject,
    onSetSiteRotationDeg,
    overlayBoundsResolved,
    placementMode,
    previewContainerBounds,
    previewMode,
    previewRef,
    resolveCadSnapPoint,
    resolveHover,
    resolvePlacement,
    rotateDragStart,
    scheduleCanvasPanView,
    scheduleCursorSitePoint,
    scheduleDraftPointerState,
    screenToSitePoint,
    setCadWindowSelect,
    setCanvasPanStart,
    setCanvasView,
    setDraggingBuildingId,
    setDraggingMode,
    setHoverPoint,
    setHoveredObjectId,
    setPinnedAnnotation,
    setRotateDragStart,
    showHover,
    showMap,
    suppressNextDrawClickRef,
    suppressNextObjectClickRef,
    updateDraggedBuilding,
    userAdjustedCanvasViewRef,
  ]);
}
