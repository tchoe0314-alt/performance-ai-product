export type PreviewBounds = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export const SURVEY_SHEET_SPOT_ELEVATIONS = [
  { x: 12, y: 18, label: "x 952.4" },
  { x: 35, y: 26, label: "x 953.1" },
  { x: 63, y: 20, label: "x 954.6" },
  { x: 78, y: 38, label: "x 951.8" },
  { x: 20, y: 58, label: "x 950.2" },
  { x: 45, y: 70, label: "x 949.7" },
  { x: 68, y: 78, label: "x 948.9" },
] as const;

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
