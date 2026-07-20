import { useCallback, useEffect, useRef, useState } from "react";
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
  lastMapResizeRef: RefObject<number>;
  showMap: boolean;
  showGeneratedPlan: boolean;
  planPreviewUrl: string | null;
  previewMode: "2d" | "3d";
  previewFullscreenOpen: boolean;
};

export function usePreviewResizeObservers({
  previewRef,
  previewImageRef,
  fullscreenRef,
  fullscreenImageRef,
  mapRef,
  fullscreenMapRef,
  lastMapResizeRef,
  showMap,
  showGeneratedPlan,
  planPreviewUrl,
  previewMode,
  previewFullscreenOpen,
}: PreviewResizeObserverOptions) {
  const [previewImageBounds, setPreviewImageBounds] = useState<PreviewBounds | null>(null);
  const [fullscreenImageBounds, setFullscreenImageBounds] = useState<PreviewBounds | null>(null);
  const [previewContainerBounds, setPreviewContainerBounds] = useState<PreviewBounds | null>(null);
  const previewSizeRef = useRef<PreviewSize | null>(null);
  const fullscreenSizeRef = useRef<PreviewSize | null>(null);
  const previewResizeRafRef = useRef<number | null>(null);
  const fullscreenResizeRafRef = useRef<number | null>(null);

  const updateImageBounds = useCallback(
    (
      containerRef: RefObject<HTMLDivElement | null>,
      imageRef: RefObject<HTMLImageElement | null>,
      setter: Dispatch<SetStateAction<PreviewBounds | null>>,
    ) => {
      if (!containerRef.current || !imageRef.current) {
        setter((current) => (current === null ? current : null));
        return;
      }
      const containerRect = containerRef.current.getBoundingClientRect();
      const imageRect = imageRef.current.getBoundingClientRect();
      const width = Math.max(imageRect.width, 1);
      const height = Math.max(imageRect.height, 1);
      const nextBounds = {
        left: imageRect.left - containerRect.left,
        top: imageRect.top - containerRect.top,
        width,
        height,
      };
      setter((current) =>
        current &&
        Math.abs(current.left - nextBounds.left) < 0.5 &&
        Math.abs(current.top - nextBounds.top) < 0.5 &&
        Math.abs(current.width - nextBounds.width) < 0.5 &&
        Math.abs(current.height - nextBounds.height) < 0.5
          ? current
          : nextBounds,
      );
    },
    [],
  );

  const updateContainerBounds = useCallback(() => {
    if (!previewRef.current) return;
    const rect = previewRef.current.getBoundingClientRect();
    const nextBounds = { left: 0, top: 0, width: rect.width, height: rect.height };
    setPreviewContainerBounds((current) =>
      current &&
      Math.abs(current.width - nextBounds.width) < 0.5 &&
      Math.abs(current.height - nextBounds.height) < 0.5
        ? current
        : nextBounds,
    );
  }, [previewRef]);

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

  return {
    previewImageBounds,
    setPreviewImageBounds,
    fullscreenImageBounds,
    setFullscreenImageBounds,
    previewContainerBounds,
    updateImageBounds,
    updateContainerBounds,
  };
}
