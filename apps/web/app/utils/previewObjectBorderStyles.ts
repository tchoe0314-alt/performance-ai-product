import type { BuildingPlacement } from "../types";

const STANDARD_BORDER_COLORS: Record<string, string> = {
  site: "border-slate-400",
  setback_zone: "border-slate-300",
  no_build_zone: "border-rose-400",
  basin: "border-emerald-500",
  entrance: "border-amber-500",
  driveway: "border-orange-400",
  road: "border-blue-500",
  parking: "border-violet-500",
  sidewalk: "border-teal-500",
  pool: "border-cyan-500",
  pad: "border-stone-400",
};

const HIGH_QUALITY_BORDER_COLORS: Record<string, string> = {
  ...STANDARD_BORDER_COLORS,
  site: "border-white/70",
  basin: "border-sky-300",
};

export function getPreviewObjectBorderColor(
  item: BuildingPlacement,
  options: { highQuality?: boolean; fallback?: string } = {},
) {
  const palette = options.highQuality ? HIGH_QUALITY_BORDER_COLORS : STANDARD_BORDER_COLORS;
  return (item.type && palette[item.type]) || options.fallback || "border-slate-900/70";
}

export function getPreviewObjectOutlineColor(item: BuildingPlacement) {
  return (item.meta as { style?: { outline_color?: string } } | undefined)?.style?.outline_color;
}
