import { useCallback, useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import type { CadPoint } from "../components/previewPanelTypes";
import type { CadSnapKind } from "../utils/cadGeometryKernel";

/** Owns transient frame queues, not project geometry or persistence. */
export function usePreviewPointerScheduling({ setCursorSitePoint, setDraftPreviewPoint, setActiveSnapPoint, setCanvasView }: {
  setCursorSitePoint: Dispatch<SetStateAction<CadPoint | null>>;
  setDraftPreviewPoint: Dispatch<SetStateAction<[number, number] | null>>;
  setActiveSnapPoint: Dispatch<SetStateAction<(CadPoint & { kind: CadSnapKind }) | null>>;
  setCanvasView: Dispatch<SetStateAction<{ scale: number; offsetX: number; offsetY: number }>>;
}) {
  const cursorSitePointRafRef = useRef<number | null>(null);
  const pendingCursorSitePointRef = useRef<CadPoint | null>(null);
  const draftPointerRafRef = useRef<number | null>(null);
  const pendingDraftPointerRef = useRef<(CadPoint & { kind: CadSnapKind }) | null>(null);
  const canvasPanRafRef = useRef<number | null>(null);
  const pendingCanvasPanViewRef = useRef<{ offsetX: number; offsetY: number } | null>(null);
  const applyCursorSitePoint = useCallback((nextPoint: CadPoint | null) => {
    setCursorSitePoint((current) => {
      if (!nextPoint) return current === null ? current : null;
      return current &&
        Math.abs(current.x - nextPoint.x) < 0.5 &&
        Math.abs(current.y - nextPoint.y) < 0.5
        ? current
        : { x: nextPoint.x, y: nextPoint.y };
    });
  }, [setCursorSitePoint]);
  const scheduleCursorSitePoint = useCallback(
    (nextPoint: CadPoint | null) => {
      pendingCursorSitePointRef.current = nextPoint;
      if (cursorSitePointRafRef.current !== null) return;
      cursorSitePointRafRef.current = window.requestAnimationFrame(() => {
        cursorSitePointRafRef.current = null;
        applyCursorSitePoint(pendingCursorSitePointRef.current);
      });
    },
    [applyCursorSitePoint],
  );
  const clearScheduledPointerState = useCallback(() => {
    if (cursorSitePointRafRef.current !== null) {
      window.cancelAnimationFrame(cursorSitePointRafRef.current);
      cursorSitePointRafRef.current = null;
    }
    if (draftPointerRafRef.current !== null) {
      window.cancelAnimationFrame(draftPointerRafRef.current);
      draftPointerRafRef.current = null;
    }
    pendingCursorSitePointRef.current = null;
    pendingDraftPointerRef.current = null;
    setCursorSitePoint(null);
    setDraftPreviewPoint(null);
    setActiveSnapPoint(null);
  }, [setCursorSitePoint, setDraftPreviewPoint, setActiveSnapPoint]);
  const scheduleCanvasPanView = useCallback((nextView: { offsetX: number; offsetY: number }) => {
    pendingCanvasPanViewRef.current = nextView;
    if (canvasPanRafRef.current !== null) return;
    canvasPanRafRef.current = window.requestAnimationFrame(() => {
      canvasPanRafRef.current = null;
      const pending = pendingCanvasPanViewRef.current;
      pendingCanvasPanViewRef.current = null;
      if (!pending) return;
      setCanvasView((prev) =>
        Math.abs(prev.offsetX - pending.offsetX) < 0.5 && Math.abs(prev.offsetY - pending.offsetY) < 0.5
          ? prev
          : { ...prev, offsetX: pending.offsetX, offsetY: pending.offsetY },
      );
    });
  }, [setCanvasView]);
  const clearScheduledCanvasPan = useCallback(() => {
    if (canvasPanRafRef.current !== null) {
      window.cancelAnimationFrame(canvasPanRafRef.current);
      canvasPanRafRef.current = null;
    }
    pendingCanvasPanViewRef.current = null;
  }, []);
  const scheduleDraftPointerState = useCallback(
    (sitePoint: (CadPoint & { kind: CadSnapKind }) | null) => {
      pendingDraftPointerRef.current = sitePoint;
      if (draftPointerRafRef.current !== null) return;
      draftPointerRafRef.current = window.requestAnimationFrame(() => {
        draftPointerRafRef.current = null;
        const nextPoint = pendingDraftPointerRef.current;
        setDraftPreviewPoint(nextPoint ? [nextPoint.x, nextPoint.y] : null);
        setActiveSnapPoint(nextPoint);
        applyCursorSitePoint(nextPoint);
      });
    },
    [applyCursorSitePoint, setDraftPreviewPoint, setActiveSnapPoint],
  );
  useEffect(
    () => () => {
      if (cursorSitePointRafRef.current !== null) {
        window.cancelAnimationFrame(cursorSitePointRafRef.current);
      }
      if (draftPointerRafRef.current !== null) {
        window.cancelAnimationFrame(draftPointerRafRef.current);
      }
      if (canvasPanRafRef.current !== null) {
        window.cancelAnimationFrame(canvasPanRafRef.current);
      }
    },
    [],
  );
  return { scheduleCursorSitePoint, clearScheduledPointerState, scheduleCanvasPanView, clearScheduledCanvasPan, scheduleDraftPointerState };
}
