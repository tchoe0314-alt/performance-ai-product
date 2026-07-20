import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, MouseEvent as ReactMouseEvent, RefObject, SetStateAction } from "react";
import type { PreviewAnnotationLabel } from "../utils/previewHoverDetails";

type HoverPoint = { x: number; y: number };
type HoverPointSetter = Dispatch<SetStateAction<HoverPoint | null>>;

type UsePreviewAnnotationHoverOptions = {
  labels: PreviewAnnotationLabel[];
  showHover: boolean;
  hasInteractiveLabels: boolean;
};

export function usePreviewAnnotationHover({
  labels,
  showHover,
  hasInteractiveLabels,
}: UsePreviewAnnotationHoverOptions) {
  const [hoveredAnnotation, setHoveredAnnotation] = useState<PreviewAnnotationLabel | null>(null);
  const [pinnedAnnotation, setPinnedAnnotation] = useState<PreviewAnnotationLabel | null>(null);
  const [hoverPoint, setHoverPoint] = useState<HoverPoint | null>(null);
  const [fullscreenHoverPoint, setFullscreenHoverPoint] = useState<HoverPoint | null>(null);
  const hoverAnnotationRafRef = useRef<number | null>(null);
  const pendingHoverAnnotationRef = useRef<{
    annotation: PreviewAnnotationLabel | null;
    point: HoverPoint | null;
    setter: HoverPointSetter;
  } | null>(null);

  const scheduleHoverAnnotationState = useCallback(
    (
      annotation: PreviewAnnotationLabel | null,
      point: HoverPoint | null,
      setter: HoverPointSetter,
    ) => {
      pendingHoverAnnotationRef.current = { annotation, point, setter };
      if (hoverAnnotationRafRef.current !== null) return;
      hoverAnnotationRafRef.current = window.requestAnimationFrame(() => {
        hoverAnnotationRafRef.current = null;
        const pending = pendingHoverAnnotationRef.current;
        pendingHoverAnnotationRef.current = null;
        if (!pending) return;
        setHoveredAnnotation((current) =>
          current?.label === pending.annotation?.label ? current : pending.annotation,
        );
        pending.setter((current) => {
          if (!pending.point) return current === null ? current : null;
          return current &&
            Math.abs(current.x - pending.point.x) < 6 &&
            Math.abs(current.y - pending.point.y) < 6
            ? current
            : pending.point;
        });
      });
    },
    [],
  );

  const clearScheduledHoverAnnotationState = useCallback((setter: HoverPointSetter) => {
    if (hoverAnnotationRafRef.current !== null) {
      window.cancelAnimationFrame(hoverAnnotationRafRef.current);
      hoverAnnotationRafRef.current = null;
    }
    pendingHoverAnnotationRef.current = null;
    setHoveredAnnotation(null);
    setter((current) => (current === null ? current : null));
  }, []);

  const resolveHover = useCallback(
    (
      event: ReactMouseEvent<HTMLDivElement>,
      containerRef: RefObject<HTMLDivElement | null>,
      imageBounds: { left: number; top: number; width: number; height: number } | null,
      setPoint: HoverPointSetter,
    ) => {
      if (!showHover || !containerRef.current || !hasInteractiveLabels) {
        clearScheduledHoverAnnotationState(setPoint);
        return;
      }
      const rect = containerRef.current.getBoundingClientRect();
      const bounds = imageBounds || { left: 0, top: 0, width: rect.width, height: rect.height };
      const relativeX = (event.clientX - rect.left - bounds.left) / Math.max(bounds.width, 1);
      const relativeY = (event.clientY - rect.top - bounds.top) / Math.max(bounds.height, 1);
      if (relativeX < 0 || relativeX > 1 || relativeY < 0 || relativeY > 1) {
        clearScheduledHoverAnnotationState(setPoint);
        return;
      }
      const matches = labels
        .filter((label) => {
          const bounds = label.bounds;
          if (!bounds) return false;
          return (
            relativeX >= bounds.x1 &&
            relativeX <= bounds.x2 &&
            relativeY >= bounds.y1 &&
            relativeY <= bounds.y2
          );
        })
        .sort((a, b) => {
          const aBounds = a.bounds;
          const bBounds = b.bounds;
          if (!aBounds || !bBounds) return 0;
          const aArea = Math.max(0, aBounds.x2 - aBounds.x1) * Math.max(0, aBounds.y2 - aBounds.y1);
          const bArea = Math.max(0, bBounds.x2 - bBounds.x1) * Math.max(0, bBounds.y2 - bBounds.y1);
          return aArea - bArea;
        });
      const next = matches[0] ?? null;
      if (!next) {
        clearScheduledHoverAnnotationState(setPoint);
        return;
      }
      const nextPoint = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      scheduleHoverAnnotationState(next, nextPoint, setPoint);
    },
    [clearScheduledHoverAnnotationState, hasInteractiveLabels, labels, scheduleHoverAnnotationState, showHover],
  );

  useEffect(
    () => () => {
      if (hoverAnnotationRafRef.current !== null) {
        window.cancelAnimationFrame(hoverAnnotationRafRef.current);
      }
    },
    [],
  );

  return {
    hoveredAnnotation,
    pinnedAnnotation,
    setPinnedAnnotation,
    hoverPoint,
    setHoverPoint,
    fullscreenHoverPoint,
    setFullscreenHoverPoint,
    activeAnnotation: pinnedAnnotation ?? hoveredAnnotation,
    clearScheduledHoverAnnotationState,
    resolveHover,
  };
}
