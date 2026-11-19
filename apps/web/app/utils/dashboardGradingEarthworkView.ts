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
    const x = Number(value[0]);
    const y = Number(value[1]);
    return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
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
                const level = Number(rec.level);
                return Number.isFinite(level) && points.length >= 2 ? { level, points } : null;
              })
              .filter((item): item is NonNullable<typeof item> => Boolean(item))
              .slice(0, 180)
          : [],
        spotElevations: Array.isArray(rawSurfaceModel.spot_elevations)
          ? rawSurfaceModel.spot_elevations
              .map((item) => {
                const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                const x = Number(rec.x);
                const y = Number(rec.y);
                const z = Number(rec.z);
                return Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z) ? { x, y, z } : null;
              })
              .filter((item): item is NonNullable<typeof item> => Boolean(item))
              .slice(0, 48)
          : [],
        slopeArrows: Array.isArray(rawSurfaceModel.slope_arrows)
          ? rawSurfaceModel.slope_arrows
              .map((item) => {
                const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                const x = Number(rec.x);
                const y = Number(rec.y);
                const dx = Number(rec.dx);
                const dy = Number(rec.dy);
                const slopePct = Number(rec.slope_pct);
                return [x, y, dx, dy, slopePct].every(Number.isFinite) ? { x, y, dx, dy, slopePct } : null;
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
                        const x = Number(pointRec.x);
                        const y = Number(pointRec.y);
                        const z = Number(pointRec.z);
                        return Number.isFinite(x) && Number.isFinite(y) ? { x, y, z: Number.isFinite(z) ? z : undefined } : null;
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
                const x = Number(rec.x);
                const y = Number(rec.y);
                const width = Number(rec.width);
                const height = Number(rec.height);
                const existingElevationFt = Number(rec.existing_elevation_ft);
                const proposedElevationFt = Number(rec.proposed_elevation_ft);
                const deltaFt = Number(rec.delta_ft);
                const cutCf = Number(rec.cut_cf);
                const fillCf = Number(rec.fill_cf);
                const mode = String(rec.mode || "balanced");
                const normalizedMode: "cut" | "fill" | "balanced" =
                  mode === "cut" || mode === "fill" ? mode : "balanced";
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
  const bounds = Array.isArray(rawSurfaceModel.bounds) ? rawSurfaceModel.bounds.map(Number) : [];
  const [surfaceXMin, surfaceYMin, surfaceXMax, surfaceYMax] = bounds;
  const surfaceWidth = surfaceXMax - surfaceXMin;
  const surfaceHeight = surfaceYMax - surfaceYMin;
  const heatmapCells: GradingEarthworkUx["heatmapCells"] = surfaceModel &&
    [surfaceXMin, surfaceYMin, surfaceXMax, surfaceYMax].every(Number.isFinite) && surfaceWidth > 0 && surfaceHeight > 0
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
