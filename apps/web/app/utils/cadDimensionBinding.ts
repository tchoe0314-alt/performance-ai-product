import type { BuildingPlacement } from "../types";
import { getPreviewObjectGeometryPoints } from "./previewCadObjectHelpers";

/** Automatic dimensions reference the first segment, matching the DIM tool. */
export function automaticCadDimensionLabel(item: BuildingPlacement): string | null {
  const [a, b] = getPreviewObjectGeometryPoints(item);
  if (!a || !b || ![...a, ...b].every(Number.isFinite)) return null;
  const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const units = item.meta?.coordinate_units === "m" ? "m" : "ft";
  const angle = ((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI + 360) % 360;
  return item.meta?.cad_dimension_mode === "aligned"
    ? `${length.toFixed(1)} ${units} @ ${angle.toFixed(1)} deg`
    : `${length.toFixed(1)} ${units}`;
}

export function synchronizeCadDimension(previous: BuildingPlacement, next: BuildingPlacement): BuildingPlacement {
  if (!next.meta?.cad_dimension_label) return next;
  if (next.meta.cad_dimension_auto === true) {
    const label = automaticCadDimensionLabel(next);
    return { ...next, meta: { ...next.meta, cad_dimension_label: label ?? "Dimension unavailable", cad_dimension_review_required: label === null } };
  }
  const before = getPreviewObjectGeometryPoints(previous), after = getPreviewObjectGeometryPoints(next);
  const changed = before.length !== after.length || before.some((p, i) => p.some((value, j) => value !== after[i]?.[j]));
  // Do not silently reinterpret legacy/imported text or a user's custom override.
  return changed ? { ...next, meta: { ...next.meta, cad_dimension_review_required: true } } : next;
}

export function displayedCadDimensionLabel(item: BuildingPlacement): string {
  const label = item.meta?.cad_dimension_auto === true ? automaticCadDimensionLabel(item) : String(item.meta?.cad_dimension_label ?? "");
  const shown = item.meta?.cad_dimension_auto === true ? label : label?.slice(0, 24);
  return `${shown ?? "Dimension unavailable"}${item.meta?.cad_dimension_review_required || label === null ? " · review" : ""}`;
}
