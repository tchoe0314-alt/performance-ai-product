import type { BuildingPlacement } from "../types";

export type CadWindowSelectionRect = {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
};

export type CadSelectableElement = {
  dataset: { cadObjectId?: string };
  getBoundingClientRect: () => DOMRect;
};

export function isCadCrossingSelection(windowRect: CadWindowSelectionRect) {
  return windowRect.currentX < windowRect.startX;
}

export function getCadWindowSelectionBounds(windowRect: CadWindowSelectionRect) {
  return {
    left: Math.min(windowRect.startX, windowRect.currentX),
    right: Math.max(windowRect.startX, windowRect.currentX),
    top: Math.min(windowRect.startY, windowRect.currentY),
    bottom: Math.max(windowRect.startY, windowRect.currentY),
  };
}

export function isCadWindowSelectionTooSmall(windowRect: CadWindowSelectionRect) {
  const bounds = getCadWindowSelectionBounds(windowRect);
  return bounds.right - bounds.left < 8 || bounds.bottom - bounds.top < 8;
}

export function resolveCadWindowSelectedObjectIds(
  windowRect: CadWindowSelectionRect,
  elements: CadSelectableElement[],
  visibleCadObjects: BuildingPlacement[],
) {
  if (isCadWindowSelectionTooSmall(windowRect)) return [];
  const bounds = getCadWindowSelectionBounds(windowRect);
  const crossingSelect = isCadCrossingSelection(windowRect);
  const uniqueIds = Array.from(
    new Set(
      elements
        .filter((element) => {
          const rect = element.getBoundingClientRect();
          const intersects =
            rect.right >= bounds.left &&
            rect.left <= bounds.right &&
            rect.bottom >= bounds.top &&
            rect.top <= bounds.bottom;
          if (crossingSelect) return intersects;
          return (
            intersects &&
            rect.left >= bounds.left &&
            rect.right <= bounds.right &&
            rect.top >= bounds.top &&
            rect.bottom <= bounds.bottom
          );
        })
        .map((element) => element.dataset.cadObjectId)
        .filter((id): id is string => Boolean(id)),
    ),
  );
  return uniqueIds.filter((id) => {
    const item = visibleCadObjects.find((candidate) => candidate.id === id);
    return item && item.type !== "site" && !item.locked;
  });
}
