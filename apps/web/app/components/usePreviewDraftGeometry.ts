import { useCallback, useEffect, useMemo } from "react";
import type { Dispatch, MouseEvent as ReactMouseEvent, MutableRefObject, RefObject, SetStateAction } from "react";

import type { BuildingPlacement } from "../types";
import { cleanupPolygon, validatePolygon, type CadSnapKind } from "../utils/cadGeometryKernel";
import type { DrawMode } from "../utils/cadToolTypes";
import {
  buildDraftGeometryFinishBlockedMessage,
  buildDraftGeometryViewModel,
  buildDrawToolLabel,
  getDraftGeometryMinPointCount,
  resolveDraftGeometryEffectivePoints,
} from "../utils/previewDraftGeometryHelpers";
import { buildPreviewDrawModeButtons } from "../utils/previewDrawModeButtons";
import { markCivoraInteraction } from "../utils/performanceProbes";
import type { CadActiveCommand, CadCommandHistoryEntry, CadPoint, PreviewPanelProps } from "./previewPanelTypes";
import { buildDraftGeometryCreatedMessage } from "../utils/previewCadCommandParsing";

type DraftPoint = [number, number];
type PreviewBounds = { left: number; top: number; width: number; height: number };
type CanvasView = { scale: number; offsetX: number; offsetY: number };
type CanvasPanStart = { x: number; y: number; offsetX: number; offsetY: number } | null;
type LastPolylineEdit = {
  id: string;
  geometry: Array<[number, number]>;
  x: number;
  y: number;
  w: number;
  d: number;
  ts: number;
} | null;
type LastRectEdit = NonNullable<PreviewPanelProps["externalRectUndo"]>;

type UsePreviewDraftGeometryOptions = {
  draftPoints: DraftPoint[];
  setDraftPoints: Dispatch<SetStateAction<DraftPoint[]>>;
  draftPointsRef: MutableRefObject<DraftPoint[]>;
  draftPreviewPoint: DraftPoint | null;
  setDraftPreviewPoint: Dispatch<SetStateAction<DraftPoint | null>>;
  lastDraftPreviewPointRef: MutableRefObject<DraftPoint | null>;
  drawMode: DrawMode;
  setDrawMode: Dispatch<SetStateAction<DrawMode>>;
  drawAutoFinishPointCount: number | null;
  setDrawAutoFinishPointCount: Dispatch<SetStateAction<number | null>>;
  setCadActiveCommand: Dispatch<SetStateAction<CadActiveCommand | null>>;
  setCadCommandStatus: Dispatch<SetStateAction<string>>;
  pushCadCommandFeedback: (
    command: string,
    status: CadCommandHistoryEntry["status"],
    message: string,
  ) => void;
  cursorSitePoint: CadPoint | null;
  siteDrawRequest: number;
  cadToolRequest?: PreviewPanelProps["cadToolRequest"];
  lastSiteDrawRequestRef: MutableRefObject<number>;
  siteLocked?: boolean;
  onSetPreviewInteraction: (value: "static" | "edit") => void;
  onCreateCustomGeometry: PreviewPanelProps["onCreateCustomGeometry"];
  onCreateSiteBoundary?: PreviewPanelProps["onCreateSiteBoundary"];
  previewRef: RefObject<HTMLDivElement | null>;
  userAdjustedCanvasViewRef: MutableRefObject<boolean>;
  canvasPanStartedAtRef: MutableRefObject<number | null>;
  setCanvasPanStart: Dispatch<SetStateAction<CanvasPanStart>>;
  canvasView: CanvasView;
  canDrawObjects: boolean;
  screenToSitePoint: (
    clientX: number,
    clientY: number,
    previewRef: RefObject<HTMLDivElement | null>,
    bounds: PreviewBounds,
  ) => CadPoint | null;
  resolveCadSnapPoint: (rawPoint: CadPoint, basePoint: CadPoint | null) => CadPoint & { kind: CadSnapKind };
  setActiveSnapPoint: Dispatch<SetStateAction<(CadPoint & { kind: CadSnapKind }) | null>>;
  drawObjectsDisabledLabel: string;
  onSelectBuilding: (id: string | null) => void;
  setManagedObjectId: Dispatch<SetStateAction<string | null>>;
  setHoveredObjectId: Dispatch<SetStateAction<string | null>>;
  setSelectedVertex: Dispatch<SetStateAction<{ id: string; index: number } | null>>;
  setCadSelectionSet: Dispatch<SetStateAction<string[]>>;
  externalRectUndo?: PreviewPanelProps["externalRectUndo"];
  setLastRectEdit: Dispatch<SetStateAction<LastRectEdit | null>>;
  lastPolylineEdit: LastPolylineEdit;
  lastRectEdit: LastRectEdit | null;
  applyPolylineUndo: () => void;
  applyRectUndo: () => void;
  selectedBuildingId: string | null;
  selectedVertex: { id: string; index: number } | null;
  buildingPlacements: BuildingPlacement[];
  onRemoveBuilding: (id: string) => void;
};

export function usePreviewDraftGeometry({
  draftPoints,
  setDraftPoints,
  draftPointsRef,
  draftPreviewPoint,
  setDraftPreviewPoint,
  lastDraftPreviewPointRef,
  drawMode,
  setDrawMode,
  drawAutoFinishPointCount,
  setDrawAutoFinishPointCount,
  setCadActiveCommand,
  setCadCommandStatus,
  pushCadCommandFeedback,
  cursorSitePoint,
  siteDrawRequest,
  cadToolRequest,
  lastSiteDrawRequestRef,
  siteLocked,
  onSetPreviewInteraction,
  onCreateCustomGeometry,
  onCreateSiteBoundary,
  previewRef,
  userAdjustedCanvasViewRef,
  canvasPanStartedAtRef,
  setCanvasPanStart,
  canvasView,
  canDrawObjects,
  screenToSitePoint,
  resolveCadSnapPoint,
  setActiveSnapPoint,
  drawObjectsDisabledLabel,
  onSelectBuilding,
  setManagedObjectId,
  setHoveredObjectId,
  setSelectedVertex,
  setCadSelectionSet,
  externalRectUndo,
  setLastRectEdit,
  lastPolylineEdit,
  lastRectEdit,
  applyPolylineUndo,
  applyRectUndo,
  selectedBuildingId,
  selectedVertex,
  buildingPlacements,
  onRemoveBuilding,
}: UsePreviewDraftGeometryOptions) {
  const clearDraftGeometry = useCallback(() => {
    draftPointsRef.current = [];
    setDraftPoints([]);
    setDraftPreviewPoint(null);
    lastDraftPreviewPointRef.current = null;
    setCadActiveCommand(null);
  }, [draftPointsRef, lastDraftPreviewPointRef, setCadActiveCommand, setDraftPoints, setDraftPreviewPoint]);

  useEffect(() => {
    draftPointsRef.current = draftPoints;
  }, [draftPoints, draftPointsRef]);

  useEffect(() => {
    if (draftPreviewPoint) {
      lastDraftPreviewPointRef.current = draftPreviewPoint;
    }
  }, [draftPreviewPoint, lastDraftPreviewPointRef]);

  useEffect(() => {
    if (siteDrawRequest === lastSiteDrawRequestRef.current) return;
    lastSiteDrawRequestRef.current = siteDrawRequest;
    if (cadToolRequest?.tool === "select" && cadToolRequest.id > siteDrawRequest) return;
    if (siteLocked) return;
    const handle = window.requestAnimationFrame(() => {
      clearDraftGeometry();
      setDrawMode("site");
      onSetPreviewInteraction("edit");
    });
    return () => window.cancelAnimationFrame(handle);
  }, [cadToolRequest?.id, cadToolRequest?.tool, clearDraftGeometry, lastSiteDrawRequestRef, onSetPreviewInteraction, setDrawMode, siteDrawRequest, siteLocked]);

  const finishDraftGeometry = useCallback(() => {
    if (drawMode !== "site" && drawMode !== "polyline" && drawMode !== "polygon" && drawMode !== "rect") {
      pushCadCommandFeedback("FINISH", "blocked", "FINISH blocked: start Add Line, Add Area, Add Box, Add Point, or Draw Site Boundary first.");
      return;
    }
    const cursorFinishPoint = cursorSitePoint ? ([cursorSitePoint.x, cursorSitePoint.y] as [number, number]) : null;
    const rectFinishPreviewPoint = draftPreviewPoint ?? lastDraftPreviewPointRef.current ?? cursorFinishPoint;
    const currentDraftPoints = draftPointsRef.current.length ? draftPointsRef.current : draftPoints;
    const effectivePoints = resolveDraftGeometryEffectivePoints(drawMode, currentDraftPoints, rectFinishPreviewPoint);
    const minPoints = getDraftGeometryMinPointCount(drawMode);
    if (effectivePoints.length < minPoints) {
      pushCadCommandFeedback("FINISH", "blocked", buildDraftGeometryFinishBlockedMessage(drawMode, effectivePoints.length));
      return;
    }
    if (drawMode === "site" || drawMode === "polygon") {
      const cleaned = cleanupPolygon(effectivePoints, 0.5);
      if (!cleaned.ok) {
        setCadCommandStatus(`POLYGON blocked: ${cleaned.reason}`);
        pushCadCommandFeedback(
          drawMode === "site" ? "SITE" : "AREA",
          "blocked",
          `${drawMode === "site" ? "SITE" : "AREA"} blocked: ${cleaned.reason}`,
        );
        return;
      }
      const validation = validatePolygon(cleaned.value);
      if (!validation.ok) {
        setCadCommandStatus(`POLYGON blocked: ${validation.issues.join(", ")}`);
        pushCadCommandFeedback(
          drawMode === "site" ? "SITE" : "AREA",
          "blocked",
          `${drawMode === "site" ? "SITE" : "AREA"} blocked: ${validation.issues.join(", ")}`,
        );
        return;
      }
      if (drawMode === "site") {
        onCreateSiteBoundary?.({ points: cleaned.value });
      } else {
        const created = onCreateCustomGeometry({
          mode: drawMode,
          points: cleaned.value,
          meta: {
            geometry_cleanup: "duplicate_vertices_removed_and_gap_closed_within_tolerance",
            polygon_holes_supported: false,
            polygon_holes_blocked_reason: "Canvas polygon editor supports one exterior ring only.",
          },
        });
        if (!created) {
          pushCadCommandFeedback("AREA", "blocked", "AREA was not added. Confirm and lock the site boundary, then try again.");
          return;
        }
      }
      setCadCommandStatus("POLYGON cleaned and stored as draft review geometry.");
      pushCadCommandFeedback(
        drawMode === "site" ? "SITE" : "AREA",
        "applied",
        drawMode === "site"
          ? "Site boundary captured from drawn points."
          : buildDraftGeometryCreatedMessage("AREA"),
      );
      setDraftPoints([]);
      setDraftPreviewPoint(null);
      setCadActiveCommand(null);
      draftPointsRef.current = [];
      setDrawMode("select");
      return;
    }
    const created = onCreateCustomGeometry({ mode: drawMode, points: effectivePoints });
    if (!created) {
      pushCadCommandFeedback(
        drawMode === "rect" ? "BOX" : "LINE",
        "blocked",
        `${drawMode === "rect" ? "BOX" : "LINE"} was not added. Confirm and lock the site boundary, then try again.`,
      );
      return;
    }
    pushCadCommandFeedback(
      drawMode === "rect" ? "BOX" : "LINE",
      "applied",
      buildDraftGeometryCreatedMessage(drawMode === "rect" ? "BOX" : "LINE"),
    );
    clearDraftGeometry();
    setDrawMode("select");
  }, [
    clearDraftGeometry,
    cursorSitePoint,
    draftPoints,
    draftPointsRef,
    draftPreviewPoint,
    drawMode,
    lastDraftPreviewPointRef,
    onCreateCustomGeometry,
    onCreateSiteBoundary,
    pushCadCommandFeedback,
    setCadActiveCommand,
    setCadCommandStatus,
    setDraftPoints,
    setDraftPreviewPoint,
    setDrawMode,
  ]);

  const draftGeometryViewModel = useMemo(() => {
    const cursorPoint = cursorSitePoint ? ([cursorSitePoint.x, cursorSitePoint.y] as [number, number]) : null;
    // Preserve the prior rect-finish fallback that intentionally reads the last pointer ref for render status.
    // eslint-disable-next-line react-hooks/refs
    const previewPoint = draftPreviewPoint ?? lastDraftPreviewPointRef.current ?? cursorPoint;
    return buildDraftGeometryViewModel({
      cursorPoint,
      draftPoints,
      draftPreviewPoint,
      drawMode,
      finishPreviewPoint: previewPoint,
    });
  }, [cursorSitePoint, draftPoints, draftPreviewPoint, drawMode, lastDraftPreviewPointRef]);

  const handleDrawPointer = useCallback(
    (
      event: ReactMouseEvent<HTMLDivElement>,
      bounds: PreviewBounds | null,
    ) => {
      if (drawMode === "select") return false;
      if (event.button !== 0) return false;
      if (!bounds || !previewRef.current) return false;
      if (drawMode === "pan") {
        event.preventDefault();
        userAdjustedCanvasViewRef.current = true;
        canvasPanStartedAtRef.current = markCivoraInteraction();
        setCanvasPanStart({
          x: event.clientX,
          y: event.clientY,
          offsetX: canvasView.offsetX,
          offsetY: canvasView.offsetY,
        });
        return true;
      }
      if (drawMode !== "site" && !canDrawObjects) {
        event.preventDefault();
        event.stopPropagation();
        return true;
      }
      const rawSitePoint = screenToSitePoint(event.clientX, event.clientY, previewRef, bounds);
      if (!rawSitePoint) return true;
      event.preventDefault();
      event.stopPropagation();
      const currentDraftPoints = draftPointsRef.current.length ? draftPointsRef.current : draftPoints;
      const basePoint = currentDraftPoints.length
        ? { x: currentDraftPoints[currentDraftPoints.length - 1][0], y: currentDraftPoints[currentDraftPoints.length - 1][1] }
        : null;
      const sitePoint = resolveCadSnapPoint(rawSitePoint, basePoint);
      setActiveSnapPoint(sitePoint);
      const point: [number, number] = [sitePoint.x, sitePoint.y];
      if (drawMode === "point") {
        const created = onCreateCustomGeometry({ mode: "point", points: [point] });
        if (!created) {
          pushCadCommandFeedback("POINT", "blocked", "POINT was not added. Confirm and lock the site boundary, then try again.");
          return true;
        }
        clearDraftGeometry();
        setDrawMode("select");
        return true;
      }
      if (drawMode === "rect") {
        if (!currentDraftPoints.length) {
          draftPointsRef.current = [point];
          setDraftPoints([point]);
          return true;
        }
        const created = onCreateCustomGeometry({ mode: "rect", points: [currentDraftPoints[0], point] });
        if (!created) {
          pushCadCommandFeedback("BOX", "blocked", "BOX was not added. Confirm and lock the site boundary, then try again.");
          return true;
        }
        pushCadCommandFeedback("BOX", "applied", buildDraftGeometryCreatedMessage("BOX"));
        setDrawMode("select");
        setDraftPreviewPoint(null);
        draftPointsRef.current = [];
        setDraftPoints([]);
        return true;
      }
      const nextPoints = [...currentDraftPoints, point];
      if (
        drawAutoFinishPointCount &&
        nextPoints.length >= drawAutoFinishPointCount &&
        (drawMode === "polyline" || drawMode === "polygon")
      ) {
        if (drawMode === "polygon") {
          const cleaned = cleanupPolygon(nextPoints, 0.5);
          if (!cleaned.ok) {
            setCadCommandStatus(`AREA blocked: ${cleaned.reason}`);
            pushCadCommandFeedback("AREA", "blocked", `AREA blocked: ${cleaned.reason}`);
            return true;
          }
          const validation = validatePolygon(cleaned.value);
          if (!validation.ok) {
            const reason = validation.issues.join(", ");
            setCadCommandStatus(`AREA blocked: ${reason}`);
            pushCadCommandFeedback("AREA", "blocked", `AREA blocked: ${reason}`);
            return true;
          }
          const created = onCreateCustomGeometry({
            mode: "polygon",
            points: cleaned.value,
            meta: {
              geometry_cleanup: "auto_finished_after_three_points",
              polygon_holes_supported: false,
              polygon_holes_blocked_reason: "Canvas polygon editor supports one exterior ring only.",
            },
          });
          if (!created) {
            pushCadCommandFeedback("AREA", "blocked", "AREA was not added. Confirm and lock the site boundary, then try again.");
            return true;
          }
          pushCadCommandFeedback("AREA", "applied", buildDraftGeometryCreatedMessage("AREA"));
        } else {
          const created = onCreateCustomGeometry({ mode: "polyline", points: nextPoints });
          if (!created) {
            pushCadCommandFeedback("LINE", "blocked", "LINE was not added. Confirm and lock the site boundary, then try again.");
            return true;
          }
          pushCadCommandFeedback("LINE", "applied", buildDraftGeometryCreatedMessage("LINE"));
        }
        setDrawMode("select");
        setDraftPreviewPoint(null);
        draftPointsRef.current = [];
        setDraftPoints([]);
        setDrawAutoFinishPointCount(null);
        setCadActiveCommand(null);
        return true;
      }
      draftPointsRef.current = nextPoints;
      setDraftPoints(nextPoints);
      return true;
    },
    [
      canvasPanStartedAtRef,
      canvasView.offsetX,
      canvasView.offsetY,
      canDrawObjects,
      clearDraftGeometry,
      drawAutoFinishPointCount,
      draftPoints,
      draftPointsRef,
      drawMode,
      onCreateCustomGeometry,
      previewRef,
      pushCadCommandFeedback,
      resolveCadSnapPoint,
      screenToSitePoint,
      setActiveSnapPoint,
      setCadActiveCommand,
      setCadCommandStatus,
      setCanvasPanStart,
      setDraftPoints,
      setDraftPreviewPoint,
      setDrawAutoFinishPointCount,
      setDrawMode,
      userAdjustedCanvasViewRef,
    ],
  );

  const activateDrawTool = useCallback(
    (mode: DrawMode, disabledLabel?: string) => {
      if (disabledLabel) {
        pushCadCommandFeedback("TOOL", "blocked", disabledLabel);
        return;
      }
      setDrawMode(mode);
      setDrawAutoFinishPointCount(mode === "polyline" ? 2 : null);
      clearDraftGeometry();
      if (mode !== "pan") {
        onSetPreviewInteraction("edit");
      }
      if (mode !== "select") {
        onSelectBuilding(null);
        setManagedObjectId(null);
        setHoveredObjectId(null);
        setSelectedVertex(null);
        setCadSelectionSet([]);
      }
      const label = buildDrawToolLabel(mode);
      pushCadCommandFeedback(
        "TOOL",
        "info",
        `${label} active. ${
          mode === "select"
            ? "Click an object or choose one from Object Manager."
            : mode === "polyline"
              ? "Pick two points on the canvas to create a draft line."
              : mode === "polygon"
                ? "Pick area vertices on the canvas, then Finish."
                : "Use the canvas; Finish appears when needed."
        }`,
      );
    },
    [
      clearDraftGeometry,
      onSelectBuilding,
      onSetPreviewInteraction,
      pushCadCommandFeedback,
      setCadSelectionSet,
      setDrawAutoFinishPointCount,
      setDrawMode,
      setHoveredObjectId,
      setManagedObjectId,
      setSelectedVertex,
    ],
  );

  const drawModeButtons = useMemo(
    () =>
      buildPreviewDrawModeButtons({
        siteLocked: Boolean(siteLocked),
        canDrawObjects,
        drawObjectsDisabledLabel,
      }),
    [canDrawObjects, drawObjectsDisabledLabel, siteLocked],
  );

  useEffect(() => {
    if (!externalRectUndo) return;
    const handle = window.requestAnimationFrame(() => {
      setLastRectEdit(externalRectUndo);
    });
    return () => window.cancelAnimationFrame(handle);
  }, [externalRectUndo, setLastRectEdit]);

  useEffect(() => {
    const handleUndo = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      const isUndo = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z";
      if (!isUndo) return;
      if (!lastPolylineEdit && !lastRectEdit) return;
      event.preventDefault();
      const polyTs = lastPolylineEdit?.ts ?? 0;
      const rectTs = lastRectEdit?.ts ?? 0;
      if (polyTs >= rectTs) {
        applyPolylineUndo();
      } else {
        applyRectUndo();
      }
    };
    window.addEventListener("keydown", handleUndo);
    return () => window.removeEventListener("keydown", handleUndo);
  }, [applyPolylineUndo, applyRectUndo, lastPolylineEdit, lastRectEdit]);

  useEffect(() => {
    const cancelDraft = () => {
      if (!draftPoints.length && drawMode === "select") return;
      clearDraftGeometry();
      setDrawMode("select");
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest?.("input, textarea, select, [contenteditable='true']")) return;
      if (event.key === "Escape") {
        if (draftPoints.length || drawMode !== "select") {
          event.preventDefault();
          cancelDraft();
        }
        return;
      }
      if (event.key === "Enter") {
        if (drawMode === "site" || drawMode === "polyline" || drawMode === "polygon" || drawMode === "rect") {
          event.preventDefault();
          finishDraftGeometry();
        }
        return;
      }
      if ((event.key === "Backspace" || event.key === "Delete") && selectedBuildingId && !selectedVertex) {
        const targetObject = buildingPlacements.find((item) => item.id === selectedBuildingId);
        if (!targetObject || targetObject.type === "site" || targetObject.locked) return;
        event.preventDefault();
        setLastRectEdit({
          id: targetObject.id,
          snapshot: { ...targetObject },
          action: "delete",
          ts: Date.now(),
        });
        onRemoveBuilding(targetObject.id);
      }
    };
    window.addEventListener("keydown", handleKey);
    window.addEventListener("civora:cancel-active-tool", cancelDraft);
    return () => {
      window.removeEventListener("keydown", handleKey);
      window.removeEventListener("civora:cancel-active-tool", cancelDraft);
    };
  }, [
    buildingPlacements,
    clearDraftGeometry,
    draftPoints.length,
    drawMode,
    finishDraftGeometry,
    onRemoveBuilding,
    selectedBuildingId,
    selectedVertex,
    setDrawMode,
    setLastRectEdit,
  ]);

  return {
    ...draftGeometryViewModel,
    activateDrawTool,
    clearDraftGeometry,
    drawModeButtons,
    finishDraftGeometry,
    handleDrawPointer,
  };
}
