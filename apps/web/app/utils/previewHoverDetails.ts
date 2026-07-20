import type { BuildingPlacement, PreviewResponse } from "../types";
import {
  geometryTruthLabel,
  resolveSourceState,
  sourceStateLabel,
} from "./previewGeometryTruth";

export type PreviewHoverDetail = {
  label: string;
  value: string;
};

export type PreviewAnnotationLabel = NonNullable<
  NonNullable<PreviewResponse["preview_annotations"]>["labels"]
>[number];

const formatHoverValue = (value: number | null | undefined, suffix: string) => {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return `${value.toFixed(2)}${suffix}`;
};

export function buildPreviewAnnotationHoverDetails(
  activeAnnotation: PreviewAnnotationLabel | null | undefined,
): PreviewHoverDetail[] {
  if (!activeAnnotation?.meta) return [];
  const meta = activeAnnotation.meta;
  const sourceLabel = meta.preview_role
    ? meta.preview_role === "final"
      ? "Final geometry"
      : meta.preview_role === "overlay"
        ? "Overlay"
        : "Debug"
    : "Unknown";
  const inferredLabel = meta.inferred ? "Inferred" : "";
  const entries = [
    { label: "System", value: meta.system },
    { label: "Layer", value: activeAnnotation.layer },
    { label: "Type", value: meta.entity_type },
    { label: "Source", value: inferredLabel ? `${sourceLabel} (${inferredLabel})` : sourceLabel },
    { label: "Length", value: formatHoverValue(meta.length_ft ?? null, " ft") },
    { label: "Width", value: formatHoverValue(meta.width_ft ?? null, " ft") },
    { label: "Height", value: formatHoverValue(meta.height_ft ?? null, " ft") },
    { label: "Area", value: formatHoverValue(meta.area_sf ?? null, " sf") },
    { label: "Slope", value: formatHoverValue(meta.slope_pct ?? null, "%") },
    { label: "Diameter", value: formatHoverValue(meta.diameter_in ?? null, " in") },
    { label: "Flow", value: formatHoverValue(meta.flow_cfs ?? null, " cfs") },
    { label: "Elevation", value: formatHoverValue(meta.elevation_ft ?? null, " ft") },
    { label: "Invert Start", value: formatHoverValue(meta.invert_start_ft ?? null, " ft") },
    { label: "Invert End", value: formatHoverValue(meta.invert_end_ft ?? null, " ft") },
  ];
  return entries.filter((entry): entry is PreviewHoverDetail => Boolean(entry.value));
}

export function buildPreviewObjectHoverDetails({
  hoveredObject,
  lotWidth,
  lotHeight,
}: {
  hoveredObject: BuildingPlacement | null | undefined;
  lotWidth: number;
  lotHeight: number;
}): PreviewHoverDetail[] {
  if (!hoveredObject) return [];
  const type = hoveredObject.type ?? "building";
  const name = hoveredObject.label || type;
  const dims = `${hoveredObject.w.toFixed(1)} ft x ${hoveredObject.d.toFixed(1)} ft`;
  const height =
    typeof hoveredObject.h === "number" && Number.isFinite(hoveredObject.h)
      ? `${hoveredObject.h.toFixed(1)} ft`
      : null;
  const source = hoveredObject.generated ? "generated" : hoveredObject.source || "user";
  const sourceState = resolveSourceState(hoveredObject);
  const confidence =
    typeof hoveredObject.confidence === "number"
      ? `${Math.round(hoveredObject.confidence * 100)}%`
      : null;
  const position =
    typeof hoveredObject.x === "number" && typeof hoveredObject.y === "number"
      ? `X ${hoveredObject.x.toFixed(1)} ft • Y ${hoveredObject.y.toFixed(1)} ft`
      : null;
  const positionRelative =
    position && lotWidth > 0 && lotHeight > 0
      ? `(${(((hoveredObject.x ?? 0) / lotWidth) * 100).toFixed(1)}%, ${(
          ((hoveredObject.y ?? 0) / lotHeight) *
          100
        ).toFixed(1)}%)`
      : null;
  return [
    { label: "Name", value: name },
    { label: "Type", value: type },
    { label: "Dimensions", value: dims },
    ...(position
      ? [
          {
            label: "Position",
            value: positionRelative ? `${position} ${positionRelative}` : position,
          },
        ]
      : []),
    ...(height ? [{ label: "Height", value: height }] : []),
    { label: "Source", value: source },
    { label: "Geometry", value: geometryTruthLabel(hoveredObject) },
    { label: "Review state", value: sourceStateLabel(sourceState) },
    ...(confidence ? [{ label: "Confidence", value: confidence }] : []),
  ];
}
