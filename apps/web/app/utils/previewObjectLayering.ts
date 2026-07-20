import type { BuildingPlacement } from "../types";
import { resolveSourceState } from "./previewGeometryTruth";
import type { PreviewOverlayBounds } from "./previewOverlayBounds";

export function resolvePreviewObjectHitZIndex({
  item,
  rectPct,
  visualKind,
  selected = false,
}: {
  item: BuildingPlacement;
  rectPct: PreviewOverlayBounds;
  visualKind: string;
  selected?: boolean;
}) {
  if (selected) return 86;
  if (item.type === "site") return 18;
  const sourceState = resolveSourceState(item);
  const area = Math.max(rectPct.width * rectPct.height, 0.01);
  const compactShapeBoost = Math.max(0, Math.min(18, 18 - area * 0.9));
  const pointLike =
    item.geometryType === "point" ||
    Boolean(item.meta?.cad_symbol) ||
    ["hydrant", "inlet", "outfall", "manhole"].includes(String(item.type || ""));
  const kindBoost =
    pointLike ? 24 : visualKind === "utility" ? 16 : visualKind === "water" ? 10 : visualKind === "road" ? 8 : 0;
  const stateBoost = sourceState === "fallback" ? -8 : sourceState === "blocked" ? 4 : 0;
  return Math.max(22, Math.min(84, Math.round(42 + compactShapeBoost + kindBoost + stateBoost)));
}

export function previewRectIntersectsViewport(rectPct: PreviewOverlayBounds) {
  return (
    rectPct.left < 100 &&
    rectPct.top < 100 &&
    rectPct.left + Math.max(rectPct.width, 0) > 0 &&
    rectPct.top + Math.max(rectPct.height, 0) > 0
  );
}
