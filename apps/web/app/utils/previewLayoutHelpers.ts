export type PreviewBounds = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export type PreviewSurveyPoint = { x: number; y: number; z?: number };

const clampSvgPercent = (value: number) => Math.min(Math.max(value, 0.8), 99.2);

export function buildSourceBackedSurveySpots({
  lotHeight,
  lotWidth,
  maxLabels = 9,
  points,
}: {
  lotHeight: number;
  lotWidth: number;
  maxLabels?: number;
  points?: PreviewSurveyPoint[];
}) {
  const width = Math.max(lotWidth, 1);
  const height = Math.max(lotHeight, 1);
  const finitePoints = (points ?? [])
    .map((point) => ({
      x: Number(point.x),
      y: Number(point.y),
      z: typeof point.z === "number" ? Number(point.z) : undefined,
    }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  const pointsWithElevation = finitePoints.filter((point) => Number.isFinite(point.z));
  if (!pointsWithElevation.length) return [];

  const step = Math.max(1, Math.ceil(pointsWithElevation.length / maxLabels));
  return pointsWithElevation
    .filter((_, index) => index % step === 0)
    .slice(0, maxLabels)
    .map((point, index) => ({
      id: `source-spot-${index}-${Math.round(point.x)}-${Math.round(point.y)}`,
      x: clampSvgPercent((point.x / width) * 100),
      y: clampSvgPercent((point.y / height) * 100),
      label: `x ${point.z!.toFixed(2)}`,
    }));
}

export function buildSourceBackedSurveyTrace({
  lotHeight,
  lotWidth,
  maxPoints = 80,
  points,
}: {
  lotHeight: number;
  lotWidth: number;
  maxPoints?: number;
  points?: PreviewSurveyPoint[];
}) {
  const width = Math.max(lotWidth, 1);
  const height = Math.max(lotHeight, 1);
  const finitePoints = (points ?? [])
    .map((point) => ({
      x: Number(point.x),
      y: Number(point.y),
      z: typeof point.z === "number" ? Number(point.z) : undefined,
    }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (!finitePoints.length) return [];
  const step = Math.max(1, Math.ceil(finitePoints.length / maxPoints));
  return finitePoints
    .filter((_, index) => index % step === 0)
    .slice(0, maxPoints)
    .map((point, index) => ({
      id: `source-point-${index}-${Math.round(point.x)}-${Math.round(point.y)}`,
      x: clampSvgPercent((point.x / width) * 100),
      y: clampSvgPercent((point.y / height) * 100),
      hasElevation: Number.isFinite(point.z),
    }));
}

const clampPercent = (value: number) => Math.min(Math.max(value * 100, 0), 100);

export const buildPreviewBoundsStyle = (bounds: PreviewBounds) => {
  const left = clampPercent(bounds.x1);
  const right = clampPercent(bounds.x2);
  const top = clampPercent(bounds.y1);
  const bottom = clampPercent(bounds.y2);
  return {
    left: `${left}%`,
    top: `${top}%`,
    width: `${Math.max(right - left, 1)}%`,
    height: `${Math.max(bottom - top, 1)}%`,
  };
};

export const buildPlanScaleBar = (siteSize: { width: number; height: number }) => {
  const span = Math.max(siteSize.width, siteSize.height, 1);
  const target = span / 5;
  const candidates = [10, 20, 25, 40, 50, 100, 200, 400, 500, 1000];
  const lengthFt = candidates.find((candidate) => candidate >= target) ?? candidates[candidates.length - 1];
  const widthPct = Math.min(36, Math.max(12, (lengthFt / Math.max(siteSize.width, 1)) * 100));
  return { lengthFt, widthPct };
};

export const buildScaleTruthLabel = ({
  geocode,
  mapScaleFtPerPx,
  mapScaleSource,
}: {
  geocode: { lat?: number; lng?: number } | null | undefined;
  mapScaleFtPerPx?: number | null;
  mapScaleSource?: string | null;
}) => {
  const hasLiveMapScale =
    mapScaleSource === "mapbox" &&
    typeof mapScaleFtPerPx === "number" &&
    Number.isFinite(mapScaleFtPerPx) &&
    mapScaleFtPerPx > 0;
  if (hasLiveMapScale) return `LIVE MAP SCALE · ${mapScaleFtPerPx.toFixed(2)} FT/PX`;
  if (geocode?.lat && geocode?.lng) return "ADDRESS APPLIED · LOCAL DRAWING SCALE";
  return "LOCAL SITE SCALE";
};
