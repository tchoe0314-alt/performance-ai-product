import type {
  BuildingPlacement,
  GradingEarthworkUx,
  ManagerMetrics,
  MetricValue,
  SiteInputs,
} from "../types";
import { readMetricValue } from "./formatting";

type GradingResultSummary = {
  sourceQuality?: string;
  sourceDetail?: string;
};

type LotBoundsForGrading = {
  w?: number;
  h?: number;
};

function finiteSurfaceNumber(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string" || value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatSignedElevationDelta(value: number, digits = 2): string {
  const normalized = Object.is(value, -0) ? 0 : value;
  return `${normalized > 0 ? "+" : ""}${normalized.toFixed(digits)}`;
}

export function shouldShowCurrentGradingComparison({
  hasGradingSurface,
  gradingStatus,
  resultCurrent,
}: {
  hasGradingSurface: boolean;
  gradingStatus: "not_generated" | "fresh" | "stale";
  resultCurrent: boolean;
}): boolean {
  return hasGradingSurface && resultCurrent && gradingStatus !== "stale";
}

export function buildDashboardGradingSourceSummary(siteInputs: SiteInputs | null | undefined): string {
  const hasSurvey = Boolean(siteInputs?.survey_file?.stored_filename || siteInputs?.survey_file?.survey_url);
  const hasMapAnalysis = Boolean(siteInputs?.map_analysis);
  const hasMapSnapshot = Boolean(siteInputs?.map_snapshot?.stored_filename || siteInputs?.map_snapshot?.image_path);
  const hasAddress = Boolean(siteInputs?.address);
  if (hasSurvey) {
    return "Survey/topo (highest trust)";
  }
  if (hasMapAnalysis || hasMapSnapshot) {
    return "Image/map inferred (approximate)";
  }
  if (hasAddress) {
    return "Address-only context (approximate)";
  }
  return "Fallback assumptions";
}

export function buildDashboardGradingEarthworkUx({
  lotBounds,
  gradingSummary,
  cutFillNet,
  managerMetrics,
  buildingPlacements,
  gradingBlocker,
  siteTooLargeForGrading,
  gradingResultSummary,
  gradingSourceSummary,
  hasGradingSurface,
}: {
  lotBounds: LotBoundsForGrading;
  gradingSummary: Record<string, unknown>;
  cutFillNet: number | null | undefined;
  managerMetrics: ManagerMetrics;
  buildingPlacements: BuildingPlacement[];
  gradingBlocker: unknown;
  siteTooLargeForGrading: boolean;
  gradingResultSummary: GradingResultSummary;
  gradingSourceSummary: string;
  hasGradingSurface: boolean;
}): GradingEarthworkUx {
  if (!hasGradingSurface) {
    return {
      heatmapCells: [],
      surfaceComparison: { existing: gradingSourceSummary, proposed: "Not calculated",
        deltaLabel: "Surface comparison not calculated", confidence: "Calculate grading before reviewing earthwork." },
      padTieIns: [],
      retainingWall: { triggered: false, label: "Not assessed", tradeoff: "Grading results required.", risk: "low" },
      haulBalance: { netCf: null, cutCf: null, fillCf: null, balancePct: 0,
        direction: "unknown", label: "Haul pending" },
    };
  }
  void lotBounds;
  void buildingPlacements;
  void gradingBlocker;
  void siteTooLargeForGrading;
  const earthwork =
    gradingSummary?.earthwork && typeof gradingSummary.earthwork === "object"
      ? (gradingSummary.earthwork as Record<string, unknown>)
      : {};
  const rawSurfaceModel =
    gradingSummary?.surface_model && typeof gradingSummary.surface_model === "object"
      ? (gradingSummary.surface_model as Record<string, unknown>)
      : {};
  const rawSurfaceConfidence =
    rawSurfaceModel.confidence && typeof rawSurfaceModel.confidence === "object"
      ? (rawSurfaceModel.confidence as Record<string, unknown>)
      : {};
  const rawSurfaceComparison =
    rawSurfaceModel.surface_comparison && typeof rawSurfaceModel.surface_comparison === "object"
      ? (rawSurfaceModel.surface_comparison as Record<string, unknown>)
      : {};
  const parseSurfacePoint = (value: unknown): [number, number] | null => {
    if (!Array.isArray(value) || value.length < 2) return null;
    const x = finiteSurfaceNumber(value[0]);
    const y = finiteSurfaceNumber(value[1]);
    return x !== null && y !== null ? [x, y] : null;
  };
  const surfaceModel: GradingEarthworkUx["surfaceModel"] | undefined = rawSurfaceModel.schema_version
    ? {
        model: String(rawSurfaceModel.model || "surface"),
        sourceType: String(rawSurfaceModel.source_type || rawSurfaceConfidence.source_type || ""),
        controlVerified: Boolean(rawSurfaceModel.control_verified || rawSurfaceConfidence.control_verified),
        confidenceNote: String(rawSurfaceConfidence.not_survey_backed_reason || rawSurfaceModel.truth_label || ""),
        contours: Array.isArray(rawSurfaceModel.contours)
          ? rawSurfaceModel.contours
              .map((item) => {
                const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                const points = Array.isArray(rec.points)
                  ? rec.points.map(parseSurfacePoint).filter((pt): pt is [number, number] => Boolean(pt))
                  : [];
                const level = finiteSurfaceNumber(rec.level);
                return level !== null && points.length >= 2 ? { level, points } : null;
              })
              .filter((item): item is NonNullable<typeof item> => Boolean(item))
              .slice(0, 180)
          : [],
        spotElevations: Array.isArray(rawSurfaceModel.spot_elevations)
          ? rawSurfaceModel.spot_elevations
              .map((item) => {
                const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                const x = finiteSurfaceNumber(rec.x);
                const y = finiteSurfaceNumber(rec.y);
                const z = finiteSurfaceNumber(rec.z);
                return x !== null && y !== null && z !== null ? { x, y, z } : null;
              })
              .filter((item): item is NonNullable<typeof item> => Boolean(item))
              .slice(0, 48)
          : [],
        slopeArrows: Array.isArray(rawSurfaceModel.slope_arrows)
          ? rawSurfaceModel.slope_arrows
              .map((item) => {
                const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                const x = finiteSurfaceNumber(rec.x);
                const y = finiteSurfaceNumber(rec.y);
                const dx = finiteSurfaceNumber(rec.dx);
                const dy = finiteSurfaceNumber(rec.dy);
                const slopePct = finiteSurfaceNumber(rec.slope_pct);
                return x !== null && y !== null && dx !== null && dy !== null && slopePct !== null ? { x, y, dx, dy, slopePct } : null;
              })
              .filter((item): item is NonNullable<typeof item> => Boolean(item))
              .slice(0, 64)
          : [],
        flowPaths: Array.isArray(rawSurfaceModel.flow_paths)
          ? rawSurfaceModel.flow_paths
              .map((item, index) => {
                const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                const points = Array.isArray(rec.points)
                  ? rec.points
                      .map((point) => {
                        const pointRec = point && typeof point === "object" ? (point as Record<string, unknown>) : {};
                        const x = finiteSurfaceNumber(pointRec.x);
                        const y = finiteSurfaceNumber(pointRec.y);
                        const z = finiteSurfaceNumber(pointRec.z);
                        return x !== null && y !== null ? { x, y, z: z ?? undefined } : null;
                      })
                      .filter((point): point is NonNullable<typeof point> => Boolean(point))
                  : [];
                return points.length >= 2 ? { id: String(rec.id || `flow-${index}`), points } : null;
              })
              .filter((item): item is NonNullable<typeof item> => Boolean(item))
              .slice(0, 16)
          : [],
        comparisonCells: Array.isArray(rawSurfaceComparison.cells)
          ? rawSurfaceComparison.cells
              .map((item, index) => {
                const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                const x = finiteSurfaceNumber(rec.x);
                const y = finiteSurfaceNumber(rec.y);
                const width = finiteSurfaceNumber(rec.width);
                const height = finiteSurfaceNumber(rec.height);
                const existingElevationFt = finiteSurfaceNumber(rec.existing_elevation_ft);
                const proposedElevationFt = finiteSurfaceNumber(rec.proposed_elevation_ft);
                const deltaFt = finiteSurfaceNumber(rec.delta_ft);
                const cutCf = finiteSurfaceNumber(rec.cut_cf);
                const fillCf = finiteSurfaceNumber(rec.fill_cf);
                if (x === null || y === null || width === null || height === null || existingElevationFt === null ||
                    proposedElevationFt === null || deltaFt === null || cutCf === null || fillCf === null ||
                    width <= 0 || height <= 0 || cutCf < 0 || fillCf < 0) return null;
                const normalizedMode: "cut" | "fill" | "balanced" = deltaFt < 0 ? "cut" : deltaFt > 0 ? "fill" : "balanced";
                return [x, y, width, height, existingElevationFt, proposedElevationFt, deltaFt, cutCf, fillCf].every(Number.isFinite)
                  ? ({ id: `surface-cell-${index}`, x, y, width, height, existingElevationFt,
                      proposedElevationFt, deltaFt, cutCf, fillCf, mode: normalizedMode })
                  : null;
              })
              .filter((item): item is NonNullable<typeof item> => Boolean(item))
              .slice(0, 96)
          : [],
      }
    : undefined;
  const earthworkNet = readMetricValue(earthwork.net_cf as MetricValue | undefined);
  const netCf = earthworkNet ?? (typeof cutFillNet === "number" ? cutFillNet : null);
  const cutCf =
    readMetricValue(managerMetrics.earthwork_cut_cf) ??
    readMetricValue(earthwork.cut_cf as MetricValue | undefined) ??
    null;
  const fillCf =
    readMetricValue(managerMetrics.earthwork_fill_cf) ??
    readMetricValue(earthwork.fill_cf as MetricValue | undefined) ??
    null;
  const balancePct =
    cutCf && fillCf ? Math.max(0, Math.min(100, (Math.min(cutCf, fillCf) / Math.max(cutCf, fillCf)) * 100)) : 0;
  const direction = "unknown" as const;
  const bounds = Array.isArray(rawSurfaceModel.bounds) ? rawSurfaceModel.bounds.map(finiteSurfaceNumber) : [];
  const hasSurfaceBounds = bounds.length >= 4 && bounds.slice(0, 4).every((value) => value !== null);
  const surfaceXMin = hasSurfaceBounds ? bounds[0]! : 0;
  const surfaceYMin = hasSurfaceBounds ? bounds[1]! : 0;
  const surfaceXMax = hasSurfaceBounds ? bounds[2]! : 0;
  const surfaceYMax = hasSurfaceBounds ? bounds[3]! : 0;
  const surfaceWidth = surfaceXMax - surfaceXMin;
  const surfaceHeight = surfaceYMax - surfaceYMin;
  const heatmapCells: GradingEarthworkUx["heatmapCells"] = surfaceModel &&
    hasSurfaceBounds && surfaceWidth > 0 && surfaceHeight > 0
    ? surfaceModel.comparisonCells.map((cell) => ({
        id: cell.id,
        xPct: ((cell.x - cell.width / 2 - surfaceXMin) / surfaceWidth) * 100,
        yPct: ((cell.y - cell.height / 2 - surfaceYMin) / surfaceHeight) * 100,
        wPct: (cell.width / surfaceWidth) * 100,
        hPct: (cell.height / surfaceHeight) * 100,
        mode: cell.mode,
        deltaFt: cell.deltaFt,
      }))
    : [];
  const padTieIns: GradingEarthworkUx["padTieIns"] = [];
  const comparedDeltas = surfaceModel?.comparisonCells.map((cell) => Math.abs(cell.deltaFt)) ?? [];
  const maxComparedDelta = comparedDeltas.length ? Math.max(...comparedDeltas) : null;
  const wallTriggered = false;
  const wallRisk: GradingEarthworkUx["retainingWall"]["risk"] = "low";
  return {
    heatmapCells,
    surfaceComparison: {
      existing: gradingResultSummary.sourceQuality || gradingSourceSummary,
      proposed: hasGradingSurface ? "Proposed grading surface" : "Concept surface",
      deltaLabel: maxComparedDelta === null
        ? "Surface comparison unavailable"
        : `Compared depth up to ${maxComparedDelta.toFixed(2)} ft`,
      confidence: gradingResultSummary.sourceDetail || gradingSourceSummary,
    },
    padTieIns,
    retainingWall: {
      triggered: wallTriggered,
      label: "Not assessed",
      tradeoff: "A verified retaining-wall assessment is not available in this surface comparison.",
      risk: wallRisk,
    },
    haulBalance: {
      netCf,
      cutCf,
      fillCf,
      balancePct,
      direction,
      label: "Haul not assessed",
    },
    surfaceModel,
  };
}
