import { useEffect } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import type mapboxgl from "mapbox-gl";

type PreviewBounds = { left: number; top: number; width: number; height: number };
type PreviewSize = { w: number; h: number };

type PreviewResizeObserverOptions = {
  previewRef: RefObject<HTMLDivElement | null>;
  previewImageRef: RefObject<HTMLImageElement | null>;
  fullscreenRef: RefObject<HTMLDivElement | null>;
  fullscreenImageRef: RefObject<HTMLImageElement | null>;
  mapRef: RefObject<mapboxgl.Map | null>;
  fullscreenMapRef: RefObject<mapboxgl.Map | null>;
  previewResizeRafRef: RefObject<number | null>;
  fullscreenResizeRafRef: RefObject<number | null>;
  previewSizeRef: RefObject<PreviewSize | null>;
  fullscreenSizeRef: RefObject<PreviewSize | null>;
  lastMapResizeRef: RefObject<number>;
  showMap: boolean;
  showGeneratedPlan: boolean;
  planPreviewUrl: string | null;
  previewMode: "2d" | "3d";
  previewFullscreenOpen: boolean;
  updateContainerBounds: () => void;
  updateImageBounds: (
    containerRef: RefObject<HTMLDivElement | null>,
    imageRef: RefObject<HTMLImageElement | null>,
    setBounds: Dispatch<SetStateAction<PreviewBounds | null>>,
  ) => void;
  setPreviewImageBounds: Dispatch<SetStateAction<PreviewBounds | null>>;
  setFullscreenImageBounds: Dispatch<SetStateAction<PreviewBounds | null>>;
};

export function usePreviewResizeObservers({
  previewRef,
  previewImageRef,
  fullscreenRef,
  fullscreenImageRef,
  mapRef,
  fullscreenMapRef,
  previewResizeRafRef,
  fullscreenResizeRafRef,
  previewSizeRef,
  fullscreenSizeRef,
  lastMapResizeRef,
  showMap,
  showGeneratedPlan,
  planPreviewUrl,
  previewMode,
  previewFullscreenOpen,
  updateContainerBounds,
  updateImageBounds,
  setPreviewImageBounds,
  setFullscreenImageBounds,
}: PreviewResizeObserverOptions) {
  useEffect(() => {
    const handleUpdate = () => {
      if (previewResizeRafRef.current !== null) return;
      previewResizeRafRef.current = window.requestAnimationFrame(() => {
        previewResizeRafRef.current = null;
        updateContainerBounds();
        if (showMap && previewRef.current) {
          const rect = previewRef.current.getBoundingClientRect();
          const nextBounds = { left: 0, top: 0, width: rect.width, height: rect.height };
          setPreviewImageBounds((current) =>
            current &&
            Math.abs(current.width - nextBounds.width) < 0.5 &&
            Math.abs(current.height - nextBounds.height) < 0.5
              ? current
              : nextBounds,
          );
          const nextSize = { w: Math.round(rect.width), h: Math.round(rect.height) };
          const prev = previewSizeRef.current;
          if (!prev || prev.w !== nextSize.w || prev.h !== nextSize.h) {
            previewSizeRef.current = nextSize;
            const now = Date.now();
            if (now - lastMapResizeRef.current > 120) {
              lastMapResizeRef.current = now;
              mapRef.current?.resize();
            }
          }
        } else if (planPreviewUrl && showGeneratedPlan) {
          updateImageBounds(previewRef, previewImageRef, setPreviewImageBounds);
        } else {
          setPreviewImageBounds(null);
        }
      });
    };
    handleUpdate();
    if (!previewRef.current) return;
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleUpdate) : null;
    if (observer) observer.observe(previewRef.current);
    window.addEventListener("resize", handleUpdate);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener("resize", handleUpdate);
      if (previewResizeRafRef.current !== null) {
        cancelAnimationFrame(previewResizeRafRef.current);
        previewResizeRafRef.current = null;
      }
    };
  }, [
    lastMapResizeRef,
    mapRef,
    planPreviewUrl,
    previewImageRef,
    previewMode,
    previewRef,
    previewResizeRafRef,
    previewSizeRef,
    setPreviewImageBounds,
    showGeneratedPlan,
    showMap,
    updateContainerBounds,
    updateImageBounds,
  ]);

  useEffect(() => {
    if (!previewFullscreenOpen) return;
    const handleUpdate = () => {
      if (fullscreenResizeRafRef.current !== null) return;
      fullscreenResizeRafRef.current = window.requestAnimationFrame(() => {
        fullscreenResizeRafRef.current = null;
        if (showMap && fullscreenRef.current) {
          const rect = fullscreenRef.current.getBoundingClientRect();
          const nextBounds = { left: 0, top: 0, width: rect.width, height: rect.height };
          setFullscreenImageBounds((current) =>
            current &&
            Math.abs(current.width - nextBounds.width) < 0.5 &&
            Math.abs(current.height - nextBounds.height) < 0.5
              ? current
              : nextBounds,
          );
          const nextSize = { w: Math.round(rect.width), h: Math.round(rect.height) };
          const prev = fullscreenSizeRef.current;
          if (!prev || prev.w !== nextSize.w || prev.h !== nextSize.h) {
            fullscreenSizeRef.current = nextSize;
            const now = Date.now();
            if (now - lastMapResizeRef.current > 120) {
              lastMapResizeRef.current = now;
              fullscreenMapRef.current?.resize();
            }
          }
        } else if (planPreviewUrl) {
          updateImageBounds(fullscreenRef, fullscreenImageRef, setFullscreenImageBounds);
        }
      });
    };
    handleUpdate();
    if (!fullscreenRef.current) return;
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleUpdate) : null;
    if (observer) observer.observe(fullscreenRef.current);
    window.addEventListener("resize", handleUpdate);
    return () => {
      if (observer) observer.disconnect();
      window.removeEventListener("resize", handleUpdate);
      if (fullscreenResizeRafRef.current !== null) {
        cancelAnimationFrame(fullscreenResizeRafRef.current);
        fullscreenResizeRafRef.current = null;
      }
    };
  }, [
    fullscreenImageRef,
    fullscreenMapRef,
    fullscreenRef,
    fullscreenResizeRafRef,
    fullscreenSizeRef,
    lastMapResizeRef,
    planPreviewUrl,
    previewFullscreenOpen,
    setFullscreenImageBounds,
    showMap,
    updateImageBounds,
  ]);
}
