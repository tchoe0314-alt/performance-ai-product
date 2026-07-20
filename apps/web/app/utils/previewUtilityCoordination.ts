import type { PreviewResponse } from "../types";
import {
  normalizeSystemLabel,
  readMetaNumber,
  toFiniteNumber,
} from "./previewGeometryTruth";
import type {
  CoordinationSeverity,
  UtilityCoordinationRow,
} from "../components/previewPanelTypes";

type PreviewLabels = NonNullable<NonNullable<PreviewResponse["preview_annotations"]>["labels"]>;

export function buildUtilityCoordinationRows(
  planPreviewAnnotations: PreviewResponse["preview_annotations"] | null,
  previewLabels: PreviewLabels,
): UtilityCoordinationRow[] {
  const explicit = (planPreviewAnnotations as Record<string, unknown> | null | undefined)?.utility_coordination;
  const explicitRows = Array.isArray(explicit)
    ? explicit
    : Array.isArray((explicit as { rows?: unknown[] } | undefined)?.rows)
      ? (explicit as { rows: unknown[] }).rows
      : [];
  const fromExplicit = explicitRows
    .map((item, index) => {
      const row = item as Record<string, unknown>;
      const clearance = readMetaNumber(row, ["clearance_ft", "clearance", "vertical_clearance_ft", "horizontal_clearance_ft"]);
      const required = readMetaNumber(row, ["required_clearance_ft", "minimum_clearance_ft", "min_clearance_ft"]);
      const score = toFiniteNumber(row.constructability_score) ?? (clearance !== null && required !== null ? Math.round(Math.min(Math.max((clearance / Math.max(required, 0.1)) * 82, 20), 96)) : 58);
      const status: CoordinationSeverity =
        String(row.status || row.severity || "").toLowerCase().includes("conflict") ||
        (clearance !== null && required !== null && clearance < required)
          ? "conflict"
          : clearance !== null && required !== null && clearance < required + 1
            ? "watch"
            : "clear";
      const crossingType: UtilityCoordinationRow["crossingType"] =
        String(row.crossing_type || row.clearance_type || "").toLowerCase().includes("horizontal")
          ? "horizontal"
          : String(row.crossing_type || row.clearance_type || "").toLowerCase().includes("vertical")
            ? "vertical"
            : "unknown";
      return {
        id: String(row.id || row.crossing_id || `coord-explicit-${index}`),
        label: String(row.label || row.name || `Crossing ${index + 1}`),
        systemA: normalizeSystemLabel(row.system_a || row.systemA || row.primary_system),
        systemB: normalizeSystemLabel(row.system_b || row.systemB || row.secondary_system),
        crossingType,
        clearanceFt: clearance,
        requiredFt: required,
        status,
        x: Math.min(Math.max(toFiniteNumber(row.x) ?? toFiniteNumber(row.relative_x) ?? 0.5, 0), 1),
        y: Math.min(Math.max(toFiniteNumber(row.y) ?? toFiniteNumber(row.relative_y) ?? 0.5, 0), 1),
        source: String(row.source || "coordination payload"),
        rerouteOptions: Array.isArray(row.reroute_options)
          ? row.reroute_options.map((value) => String(value)).slice(0, 3)
          : [],
        constructabilityScore: Math.round(Math.min(Math.max(score, 0), 100)),
      };
    });
  if (fromExplicit.length) return fromExplicit;

  const coordinationLabels = previewLabels.filter((item) => {
    const text = `${item.label} ${item.layer} ${item.meta?.system || ""} ${item.meta?.source_stage || ""}`.toLowerCase();
    return (
      text.includes("conflict") ||
      text.includes("crossing") ||
      text.includes("clearance") ||
      text.includes("utility") ||
      text.includes("storm") ||
      text.includes("sanitary") ||
      text.includes("water")
    );
  });
  const utilityLike = coordinationLabels.filter((item) => {
    const text = `${item.label} ${item.layer} ${item.meta?.system || ""}`.toLowerCase();
    return text.includes("utility") || text.includes("storm") || text.includes("sanitary") || text.includes("water");
  });
  const sourceRows = coordinationLabels.length ? coordinationLabels : utilityLike;
  return sourceRows.slice(0, 8).map((item, index) => {
    const meta = item.meta as Record<string, unknown> | undefined;
    const text = `${item.label} ${item.layer} ${meta?.system || ""}`.toLowerCase();
    const clearance = readMetaNumber(meta, [
      "clearance_ft",
      "vertical_clearance_ft",
      "horizontal_clearance_ft",
      "separation_ft",
    ]);
    const required = readMetaNumber(meta, ["required_clearance_ft", "minimum_clearance_ft", "min_clearance_ft"]);
    const isConflict = text.includes("conflict") || (clearance !== null && required !== null && clearance < required);
    const isWatch = text.includes("review") || text.includes("clearance") || (clearance !== null && required !== null && clearance < required + 1);
    const primary = normalizeSystemLabel(meta?.system || meta?.source_type || item.layer);
    const secondary = text.includes("storm")
      ? "Utility"
      : text.includes("sanitary")
        ? "Storm"
        : text.includes("water")
          ? "Storm"
          : "Drainage";
    const scoreBase = isConflict ? 42 : isWatch ? 68 : 84;
    const score = clearance !== null && required !== null
      ? Math.round(Math.min(Math.max((clearance / Math.max(required, 0.1)) * 78, 24), 94))
      : scoreBase;
    return {
      id: String(meta?.entity_id || `${item.layer}-${item.label}-${index}`),
      label: item.label || `Coordination item ${index + 1}`,
      systemA: primary,
      systemB: normalizeSystemLabel(secondary),
      crossingType: text.includes("horizontal") ? "horizontal" : text.includes("vertical") || text.includes("crossing") ? "vertical" : "unknown",
      clearanceFt: clearance,
      requiredFt: required,
      status: isConflict ? "conflict" : isWatch ? "watch" : "clear",
      x: Math.min(Math.max(item.x, 0), 1),
      y: Math.min(Math.max(item.y, 0), 1),
      source: String(meta?.source_stage || meta?.canonical_source_type || "preview annotation"),
      rerouteOptions: isConflict
        ? ["Shift laterally", "Raise/flatten crossing", "Split run around constraint"]
        : isWatch
          ? ["Verify invert", "Add survey-control check", "Hold route for engineer review"]
          : [],
      constructabilityScore: score,
    };
  });
}

export function summarizeUtilityCoordinationRows(rows: UtilityCoordinationRow[]) {
  const conflictCount = rows.filter((row) => row.status === "conflict").length;
  const watchCount = rows.filter((row) => row.status === "watch").length;
  const clearCount = rows.filter((row) => row.status === "clear").length;
  return {
    conflictCount,
    watchCount,
    clearCount,
    total: rows.length,
    status: (conflictCount > 0 ? "conflict" : watchCount > 0 ? "watch" : "clear") as CoordinationSeverity,
  };
}
