import type { BuildingPlacement } from "../types";
import { resolveSourceState, utilityStrokeColor } from "./previewGeometryTruth";

export function resolvePreviewVisualKind(item: BuildingPlacement) {
  const type = String(item.type || "building");
  if (type.includes("building") || type === "pad" || !item.type) return "building";
  if (type === "lot_block") return "lot";
  if (type === "setback_zone" || type === "no_build_zone") return "constraint";
  if (String(item.meta?.preview_kind || "").toLowerCase() === "contour") return "contour";
  if (type === "road" || type === "driveway") return "road";
  if (type === "parking") return "parking";
  if (type === "basin" || type === "pond" || type === "pool") return "water";
  if (type === "open_space" || type === "landscape" || type === "amenity") return "landscape";
  if (type === "sidewalk") return "sidewalk";
  if (
    type === "inlet" ||
    type === "outfall" ||
    type === "hydrant" ||
    type === "manhole" ||
    type === "utility_corridor"
  ) {
    return "utility";
  }
  return "fallback";
}

export function resolvePreviewSvgVisualStyle(
  item: BuildingPlacement,
  options: { selected?: boolean; highQuality?: boolean; cadReferenceMode?: boolean } = {},
) {
  const selected = Boolean(options.selected);
  const kind = resolvePreviewVisualKind(item);
  const sourceState = resolveSourceState(item);
  const blocked = sourceState === "blocked";
  const lowConfidence = sourceState === "inferred" || sourceState === "fallback";
  const reviewConcept = Boolean(item.meta?.generated_review_concept || item.meta?.visual_concept_only);
  const imported = sourceState === "imported";
  const stale = sourceState === "stale";
  const solidCadSymbol = Boolean(item.meta?.cad_solid_symbol);
  const customStroke =
    typeof item.meta?.ui_color === "string" && /^#[0-9a-f]{6}$/i.test(item.meta.ui_color)
      ? item.meta.ui_color
      : null;
  const dash =
    blocked ? "1.2 0.8" : reviewConcept ? "1.7 1.2" : stale ? "2.2 0.9 0.5 0.9" : lowConfidence ? "1.4 1.1" : imported ? "2.4 1" : undefined;
  const stateStroke = (fallback: string) => (
    selected ? "#0f766e" : blocked ? "#dc2626" : sourceState === "fallback" ? "#64748b" : customStroke ?? fallback
  );
  const stateOpacity = blocked ? 0.9 : reviewConcept ? 0.64 : lowConfidence ? 0.86 : 1;
  const reviewWidth = (normal: number, selectedWidth: number) =>
    reviewConcept ? (selected ? selectedWidth * 0.78 : normal * 0.82) : selected ? selectedWidth : normal;

  if (options.highQuality && options.cadReferenceMode) {
    const cadStroke = (fallback: string) => (selected ? "#22d3ee" : blocked ? "#fb7185" : customStroke ?? fallback);
    if (kind === "road") {
      return { fill: "rgba(255,255,255,0.09)", stroke: cadStroke("#f8fafc"), strokeWidth: reviewWidth(0.055, 0.13), strokeDasharray: undefined, opacity: 0.98 };
    }
    if (kind === "parking") {
      return { fill: "rgba(37,99,235,0.38)", stroke: cadStroke("#f8fafc"), strokeWidth: reviewWidth(0.055, 0.12), strokeDasharray: undefined, opacity: 0.98 };
    }
    if (kind === "water") {
      return { fill: "rgba(56,189,248,0.22)", stroke: cadStroke("#38bdf8"), strokeWidth: reviewWidth(0.055, 0.12), strokeDasharray: undefined, opacity: 0.98 };
    }
    if (kind === "landscape") {
      return { fill: "rgba(34,197,94,0.16)", stroke: cadStroke("#22c55e"), strokeWidth: reviewWidth(0.055, 0.12), strokeDasharray: undefined, opacity: 0.98 };
    }
    if (kind === "sidewalk") {
      return { fill: "rgba(255,255,255,0.02)", stroke: cadStroke("#e5e7eb"), strokeWidth: reviewWidth(0.04, 0.1), strokeDasharray: undefined, opacity: 0.94 };
    }
    if (kind === "utility") {
      return { fill: "none", stroke: cadStroke(utilityStrokeColor(item)), strokeWidth: reviewWidth(0.07, 0.14), strokeDasharray: "1.05 0.48", opacity: 0.98 };
    }
    if (kind === "lot") {
      return { fill: "rgba(255,255,255,0.01)", stroke: cadStroke("#f8fafc"), strokeWidth: reviewWidth(0.045, 0.1), strokeDasharray: undefined, opacity: 0.98 };
    }
    if (kind === "contour") {
      return { fill: "none", stroke: cadStroke("#facc15"), strokeWidth: reviewWidth(0.06, 0.1), strokeDasharray: undefined, opacity: 0.95 };
    }
    if (kind === "constraint") {
      return { fill: "rgba(239,68,68,0.36)", stroke: cadStroke("#ef4444"), strokeWidth: reviewWidth(0.055, 0.12), strokeDasharray: "0.8 0.34", opacity: 0.98 };
    }
    if (kind === "building") {
      return { fill: "rgba(255,255,255,0.05)", stroke: cadStroke("#f8fafc"), strokeWidth: reviewWidth(0.06, 0.14), strokeDasharray: undefined, opacity: 0.98 };
    }
    return { fill: "rgba(255,255,255,0.02)", stroke: cadStroke("#e5e7eb"), strokeWidth: reviewWidth(0.05, 0.12), strokeDasharray: undefined, opacity: 0.95 };
  }

  if (!options.highQuality) {
    const standardPalette: Record<string, { fill: string; stroke: string }> = {
      building: { fill: "rgba(255, 255, 255, 0.42)", stroke: "#111827" },
      parking: { fill: "rgba(248, 250, 252, 0.2)", stroke: "#64748b" },
      road: { fill: "rgba(71, 85, 105, 0.08)", stroke: "#334155" },
      water: { fill: "rgba(186, 230, 253, 0.18)", stroke: "#0369a1" },
      landscape: { fill: "rgba(220, 252, 231, 0.14)", stroke: "#15803d" },
      sidewalk: { fill: "rgba(248, 250, 252, 0.36)", stroke: "#94a3b8" },
      utility: { fill: "rgba(59, 130, 246, 0.035)", stroke: "#1d4ed8" },
      lot: { fill: "rgba(255, 255, 255, 0.05)", stroke: "#475569" },
      contour: { fill: "rgba(250, 204, 21, 0.01)", stroke: "#ca8a04" },
      constraint: { fill: "rgba(248, 113, 113, 0.08)", stroke: "#dc2626" },
      fallback: { fill: "rgba(248, 250, 252, 0.025)", stroke: "#94a3b8" },
    };
    const style = standardPalette[kind] ?? standardPalette.fallback;
    return {
      fill: style.fill,
      stroke: selected ? "#0f766e" : blocked ? "#dc2626" : customStroke ?? style.stroke,
      strokeWidth: selected ? (kind === "utility" ? 0.16 : 0.26) : reviewConcept ? 0.095 : kind === "fallback" ? 0.09 : kind === "building" ? 0.16 : kind === "road" || kind === "sidewalk" ? 0.18 : kind === "utility" ? 0.085 : 0.12,
      strokeDasharray: dash,
      opacity: stateOpacity,
    };
  }
  if (solidCadSymbol) {
    return {
      fill: selected ? "rgba(34,211,238,0.28)" : "rgba(51,65,85,0.7)",
      stroke: selected ? "#22d3ee" : "rgba(15,23,42,0.78)",
      strokeWidth: selected ? 0.1 : 0.038,
      strokeDasharray: undefined,
      opacity: 0.78,
    };
  }
  if (kind === "road") {
    return { fill: "rgba(71, 85, 105, 0.045)", stroke: stateStroke("#334155"), strokeWidth: reviewWidth(0.115, 0.22), strokeDasharray: dash, opacity: Math.max(stateOpacity, 0.78) };
  }
  if (kind === "parking") {
    return { fill: "rgba(226, 232, 240, 0.13)", stroke: stateStroke("#334155"), strokeWidth: reviewWidth(0.085, 0.18), strokeDasharray: dash, opacity: stateOpacity };
  }
  if (kind === "water") {
    return { fill: "rgba(125, 211, 252, 0.11)", stroke: stateStroke("#0284c7"), strokeWidth: reviewWidth(0.09, 0.18), strokeDasharray: dash, opacity: stateOpacity };
  }
  if (kind === "landscape") {
    return { fill: "rgba(134, 239, 172, 0.12)", stroke: stateStroke("#15803d"), strokeWidth: reviewWidth(0.085, 0.18), strokeDasharray: dash, opacity: Math.max(stateOpacity, 0.82) };
  }
  if (kind === "sidewalk") {
    return { fill: "rgba(248, 250, 252, 0.16)", stroke: stateStroke("#64748b"), strokeWidth: reviewWidth(0.055, 0.13), strokeDasharray: dash, opacity: stateOpacity };
  }
  if (kind === "utility") {
    return { fill: "rgba(37, 99, 235, 0.006)", stroke: stateStroke(utilityStrokeColor(item)), strokeWidth: reviewWidth(0.048, 0.11), strokeDasharray: dash, opacity: Math.max(stateOpacity, 0.82) };
  }
  if (kind === "lot") {
    return { fill: "rgba(255, 255, 255, 0.018)", stroke: stateStroke("#64748b"), strokeWidth: reviewWidth(0.052, 0.13), strokeDasharray: dash, opacity: Math.max(stateOpacity, 0.78) };
  }
  if (kind === "contour") {
    return { fill: "none", stroke: stateStroke("#b45309"), strokeWidth: reviewWidth(0.032, 0.065), strokeDasharray: undefined, opacity: 0.72 };
  }
  if (kind === "constraint") {
    return { fill: "rgba(248, 113, 113, 0.08)", stroke: stateStroke("#dc2626"), strokeWidth: reviewWidth(0.075, 0.14), strokeDasharray: dash, opacity: stateOpacity };
  }
  if (kind === "building") {
    return { fill: "rgba(255, 255, 255, 0.64)", stroke: stateStroke("#334155"), strokeWidth: reviewWidth(0.105, 0.19), strokeDasharray: dash, opacity: stateOpacity };
  }
  return { fill: "rgba(248, 250, 252, 0.028)", stroke: stateStroke("#64748b"), strokeWidth: reviewWidth(0.085, 0.18), strokeDasharray: dash, opacity: stateOpacity };
}

export function cadHatchPatternForPreviewItem(item: BuildingPlacement) {
  if (!item.meta?.cad_hatch_enabled) return null;
  const pattern = String(item.meta?.cad_hatch_pattern || "").toLowerCase();
  if (pattern === "water") return "url(#cad-hatch-water)";
  if (pattern === "landscape") return "url(#cad-hatch-landscape)";
  return "url(#cad-hatch-diagonal)";
}

export function roundedSiteShapePath(
  rect: { left: number; top: number; width: number; height: number },
  kind: "water" | "landscape" | "road" | "sidewalk",
) {
  const x = rect.left;
  const y = rect.top;
  const w = Math.max(rect.width, 0.1);
  const h = Math.max(rect.height, 0.1);
  if (kind === "road" || kind === "sidewalk") {
    const r = Math.min(w, h) * 0.22;
    return `M ${x + r} ${y} L ${x + w - r} ${y} Q ${x + w} ${y} ${x + w} ${y + r} L ${x + w} ${y + h - r} Q ${x + w} ${y + h} ${x + w - r} ${y + h} L ${x + r} ${y + h} Q ${x} ${y + h} ${x} ${y + h - r} L ${x} ${y + r} Q ${x} ${y} ${x + r} ${y} Z`;
  }
  const wobble = kind === "water" ? 0.13 : 0.18;
  return [
    `M ${x + w * 0.18} ${y + h * 0.18}`,
    `C ${x + w * 0.32} ${y - h * wobble} ${x + w * 0.7} ${y - h * 0.04} ${x + w * 0.84} ${y + h * 0.22}`,
    `C ${x + w * 1.04} ${y + h * 0.42} ${x + w * 0.96} ${y + h * 0.78} ${x + w * 0.76} ${y + h * 0.9}`,
    `C ${x + w * 0.54} ${y + h * 1.05} ${x + w * 0.2} ${y + h * 0.94} ${x + w * 0.08} ${y + h * 0.7}`,
    `C ${x - w * 0.04} ${y + h * 0.48} ${x + w * 0.02} ${y + h * 0.28} ${x + w * 0.18} ${y + h * 0.18}`,
    "Z",
  ].join(" ");
}

export function architecturalFootprintPath(rect: { left: number; top: number; width: number; height: number }) {
  const x = rect.left;
  const y = rect.top;
  const w = Math.max(rect.width, 0.1);
  const h = Math.max(rect.height, 0.1);
  const notchW = Math.min(w * 0.18, Math.max(0.45, w * 0.08));
  const notchD = Math.min(h * 0.22, Math.max(0.38, h * 0.1));
  const entryW = Math.min(w * 0.14, Math.max(0.42, w * 0.07));
  const entryD = Math.min(h * 0.18, Math.max(0.34, h * 0.08));
  if (w < 2.2 || h < 1.6) {
    return `M ${x} ${y} L ${x + w} ${y} L ${x + w} ${y + h} L ${x} ${y + h} Z`;
  }
  return [
    `M ${x} ${y}`,
    `L ${x + w * 0.42} ${y}`,
    `L ${x + w * 0.42} ${y + entryD}`,
    `L ${x + w * 0.42 + entryW} ${y + entryD}`,
    `L ${x + w * 0.42 + entryW} ${y}`,
    `L ${x + w} ${y}`,
    `L ${x + w} ${y + h * 0.48}`,
    `L ${x + w - notchW} ${y + h * 0.48}`,
    `L ${x + w - notchW} ${y + h * 0.48 + notchD}`,
    `L ${x + w} ${y + h * 0.48 + notchD}`,
    `L ${x + w} ${y + h}`,
    `L ${x + w * 0.16} ${y + h}`,
    `L ${x + w * 0.16} ${y + h - entryD}`,
    `L ${x} ${y + h - entryD}`,
    `L ${x} ${y}`,
    "Z",
  ].join(" ");
}

export function rectCorridorAxis(rect: { left: number; top: number; width: number; height: number }) {
  const inset = 0.12;
  if (rect.width >= rect.height) {
    return {
      x1: rect.left + rect.width * inset,
      y1: rect.top + rect.height / 2,
      x2: rect.left + rect.width * (1 - inset),
      y2: rect.top + rect.height / 2,
      width: Math.max(0.85, Math.min(5.2, rect.height * 0.72)),
    };
  }
  return {
    x1: rect.left + rect.width / 2,
    y1: rect.top + rect.height * inset,
    x2: rect.left + rect.width / 2,
    y2: rect.top + rect.height * (1 - inset),
    width: Math.max(0.85, Math.min(5.2, rect.width * 0.72)),
  };
}
