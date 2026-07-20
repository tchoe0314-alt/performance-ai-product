import { useCallback, useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { BuildingPlacement } from "../types";
import type { PreviewPanelProps } from "./previewPanelTypes";

type FocusTransform = { scale: number; tx: number; ty: number };

type PreviewFocusTransformOptions = {
  focusDetectedId?: string | null;
  focusObjectId?: string | null;
  buildingPlacements: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
  analysisPaths?: PreviewPanelProps["analysisPaths"];
  analysisHighlight?: PreviewPanelProps["analysisHighlight"];
  lotWidth: number;
  lotHeight: number;
  onSelectBuilding: (id: string | null) => void;
  onClearFocusDetected?: () => void;
  onClearFocusObject?: () => void;
  setHoveredObjectId: Dispatch<SetStateAction<string | null>>;
};

export function usePreviewFocusTransform({
  focusDetectedId,
  focusObjectId,
  buildingPlacements,
  suggestedPlacements,
  analysisPaths,
  analysisHighlight,
  lotWidth,
  lotHeight,
  onSelectBuilding,
  onClearFocusDetected,
  onClearFocusObject,
  setHoveredObjectId,
}: PreviewFocusTransformOptions) {
  const [focusTransform, setFocusTransform] = useState<FocusTransform | null>(null);

  const updateFocusTransform = useCallback((nextTransform: FocusTransform) => {
    setFocusTransform((current) =>
      current &&
      Math.abs(current.scale - nextTransform.scale) < 0.001 &&
      Math.abs(current.tx - nextTransform.tx) < 0.001 &&
      Math.abs(current.ty - nextTransform.ty) < 0.001
        ? current
        : nextTransform,
    );
  }, []);

  useEffect(() => {
    if (!focusDetectedId) return;
    const target = suggestedPlacements.find((item) => item.id === focusDetectedId);
    let frame: number | null = null;
    if (target) {
      frame = window.requestAnimationFrame(() => {
        setHoveredObjectId((current) => (current === target.id ? current : target.id));
        onSelectBuilding(target.id);
      });
    }
    if (onClearFocusDetected) {
      const timer = window.setTimeout(() => onClearFocusDetected(), 400);
      return () => {
        if (frame !== null) window.cancelAnimationFrame(frame);
        window.clearTimeout(timer);
      };
    }
    return () => {
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, [focusDetectedId, onClearFocusDetected, onSelectBuilding, setHoveredObjectId, suggestedPlacements]);

  useEffect(() => {
    if (!focusObjectId) return;
    const target = buildingPlacements.find((item) => item.id === focusObjectId);
    if (!target || !lotWidth || !lotHeight) return;
    const minX = target.x ?? 0;
    const minY = target.y ?? 0;
    const maxX = minX + target.w;
    const maxY = minY + target.d;
    const padding = 0.15;
    const boxW = Math.max((maxX - minX) / lotWidth, 0.02);
    const boxH = Math.max((maxY - minY) / lotHeight, 0.02);
    const scale = Math.min(1 / (boxW + padding), 1 / (boxH + padding));
    const centerX = (minX + maxX) / 2 / lotWidth;
    const centerY = (minY + maxY) / 2 / lotHeight;
    const nextTransform = { scale: Math.min(Math.max(scale, 1), 1.6), tx: centerX, ty: centerY };
    const handle = window.requestAnimationFrame(() => updateFocusTransform(nextTransform));
    if (onClearFocusObject) {
      const timer = window.setTimeout(() => onClearFocusObject(), 500);
      return () => {
        window.cancelAnimationFrame(handle);
        window.clearTimeout(timer);
      };
    }
    return () => window.cancelAnimationFrame(handle);
  }, [buildingPlacements, focusObjectId, lotHeight, lotWidth, onClearFocusObject, updateFocusTransform]);

  useEffect(() => {
    if (!analysisHighlight || !lotWidth || !lotHeight) return;
    const focusItems = [...buildingPlacements, ...suggestedPlacements].filter(
      (item) => item.id === analysisHighlight.buildingId || item.id === analysisHighlight.accessId,
    );
    if (!focusItems.length) return;
    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    focusItems.forEach((item) => {
      const x = item.x ?? 0;
      const y = item.y ?? 0;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + item.w);
      maxY = Math.max(maxY, y + item.d);
    });
    const path = analysisPaths?.find((p) => p.id === analysisHighlight.pathId);
    if (path) {
      minX = Math.min(minX, path.from.x, path.to.x);
      minY = Math.min(minY, path.from.y, path.to.y);
      maxX = Math.max(maxX, path.from.x, path.to.x);
      maxY = Math.max(maxY, path.from.y, path.to.y);
    }
    if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) return;
    const padding = 0.1;
    const boxW = Math.max((maxX - minX) / lotWidth, 0.02);
    const boxH = Math.max((maxY - minY) / lotHeight, 0.02);
    const scale = Math.min(1 / (boxW + padding), 1 / (boxH + padding));
    const centerX = (minX + maxX) / 2 / lotWidth;
    const centerY = (minY + maxY) / 2 / lotHeight;
    const nextTransform = { scale: Math.min(Math.max(scale, 1), 3), tx: centerX, ty: centerY };
    const handle = window.requestAnimationFrame(() => updateFocusTransform(nextTransform));
    return () => window.cancelAnimationFrame(handle);
  }, [analysisHighlight, analysisPaths, buildingPlacements, lotHeight, lotWidth, suggestedPlacements, updateFocusTransform]);

  return { focusTransform, setFocusTransform };
}
