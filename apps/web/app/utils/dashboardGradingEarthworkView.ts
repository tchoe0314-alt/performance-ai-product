import type {
  BuildingPlacement,
  GradingEarthworkUx,
  ManagerMetrics,
  MetricValue,
  SiteInputs,
} from "../types";
import {
  DEFAULT_BLANK_SITE_DEPTH_FT,
  DEFAULT_BLANK_SITE_WIDTH_FT,
} from "./workflowConstants";
import { readMetricValue } from "./formatting";

type GradingResultSummary = {
  sourceQuality?: string;
  sourceDetail?: string;
};

type LotBoundsForGrading = {
  w?: number;
  h?: number;
};

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
  const width = Math.max(lotBounds.w || DEFAULT_BLANK_SITE_WIDTH_FT, 1);
  const height = Math.max(lotBounds.h || DEFAULT_BLANK_SITE_DEPTH_FT, 1);
  const surfaceControls =
    gradingSummary?.surface_controls && typeof gradingSummary.surface_controls === "object"
      ? (gradingSummary.surface_controls as Record<string, unknown>)
      : {};
  const existingSurface =
    gradingSummary?.existing_surface && typeof gradingSummary.existing_surface === "object"
      ? (gradingSummary.existing_surface as Record<string, unknown>)
      : {};
  const proposedSurface =
    gradingSummary?.proposed_surface && typeof gradingSummary.proposed_surface === "object"
      ? (gradingSummary.proposed_surface as Record<string, unknown>)
      : {};
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
              .map((item) => {
                const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
                const x = Number(rec.x);
                const y = Number(rec.y);
                const deltaFt = Number(rec.delta_ft);
                const mode = String(rec.mode || "balanced");
                const normalizedMode: "cut" | "fill" | "balanced" =
                  mode === "cut" || mode === "fill" ? mode : "balanced";
                return Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(deltaFt)
                  ? ({ x, y, deltaFt, mode: normalizedMode } satisfies {
                      x: number;
                      y: number;
                      deltaFt: number;
                      mode: "cut" | "fill" | "balanced";
                    })
                  : null;
              })
              .filter((item): item is NonNullable<typeof item> => Boolean(item))
              .slice(0, 96)
          : [],
      }
    : undefined;
  const gradeRangeFt = Math.max(
    1,
    Number(surfaceControls.grade_range_ft ?? proposedSurface.range_z ?? existingSurface.range_z ?? 6),
  );
  const netCf = typeof cutFillNet === "number" ? cutFillNet : null;
  const cutCf =
    readMetricValue(managerMetrics.earthwork_cut_cf) ??
    readMetricValue(earthwork.cut_cf as MetricValue | undefined) ??
    (typeof netCf === "number" && netCf < 0 ? Math.abs(netCf) * 1.15 : null);
  const fillCf =
    readMetricValue(managerMetrics.earthwork_fill_cf) ??
    readMetricValue(earthwork.fill_cf as MetricValue | undefined) ??
    (typeof netCf === "number" && netCf > 0 ? netCf * 1.15 : null);
  const balancePct =
    cutCf && fillCf ? Math.max(0, Math.min(100, (Math.min(cutCf, fillCf) / Math.max(cutCf, fillCf)) * 100)) : 0;
  const direction =
    typeof netCf !== "number"
      ? "unknown"
      : Math.abs(netCf) < Math.max(500, width * height * 0.02)
        ? "balanced"
        : netCf < 0
          ? "export"
          : "import";
  const heatmapCells: GradingEarthworkUx["heatmapCells"] = Array.from({ length: 24 }, (_, idx) => {
    const col = idx % 6;
    const row = Math.floor(idx / 6);
    const normalized = (col / 5 - 0.5) * 0.7 + (row / 3 - 0.5) * 0.55;
    const netBias = typeof netCf === "number" ? Math.max(-0.45, Math.min(0.45, netCf / Math.max(width * height, 1))) : 0;
    const deltaFt = Number(((normalized - netBias) * gradeRangeFt).toFixed(2));
    const mode: GradingEarthworkUx["heatmapCells"][number]["mode"] =
      Math.abs(deltaFt) < gradeRangeFt * 0.09 ? "balanced" : deltaFt > 0 ? "cut" : "fill";
    return {
      id: `earthwork-cell-${idx}`,
      xPct: col * (100 / 6),
      yPct: row * 25,
      wPct: 100 / 6,
      hPct: 25,
      mode,
      deltaFt,
    };
  });
  const padTypes = new Set(["building", "retail_building", "multifamily_building", "industrial_building", "office_building", "pad"]);
  const padTieIns = buildingPlacements
    .filter((item) => item.placed && padTypes.has(String(item.type || "building")))
    .slice(0, 6)
    .map((item) => {
      const slopePct = Math.abs(((Number(item.x ?? 0) / width) - (Number(item.y ?? 0) / height)) * 4.5);
      const status: GradingEarthworkUx["padTieIns"][number]["status"] =
        slopePct > 4.5 ? "blocked" : slopePct > 2.5 ? "review" : "ok";
      return {
        id: item.id,
        label: item.label ?? "Pad",
        xPct: Math.max(0, Math.min(100, (Number(item.x ?? 0) / width) * 100)),
        yPct: Math.max(0, Math.min(100, (Number(item.y ?? 0) / height) * 100)),
        wPct: Math.max(1, Math.min(100, (Number(item.w ?? 1) / width) * 100)),
        hPct: Math.max(1, Math.min(100, (Number(item.d ?? 1) / height) * 100)),
        status,
        slopePct: Number(slopePct.toFixed(1)),
      };
    });
  const wallTriggered =
    Boolean(gradingBlocker) ||
    gradeRangeFt > 8 ||
    padTieIns.some((item) => item.status === "blocked") ||
    siteTooLargeForGrading;
  const wallRisk: GradingEarthworkUx["retainingWall"]["risk"] =
    siteTooLargeForGrading || gradeRangeFt > 14 ? "high" : wallTriggered ? "medium" : "low";
  return {
    heatmapCells,
    surfaceComparison: {
      existing: gradingResultSummary.sourceQuality || gradingSourceSummary,
      proposed: hasGradingSurface ? "Proposed grading surface" : "Concept surface",
      deltaLabel: `Surface delta range ${gradeRangeFt.toFixed(1)} ft`,
      confidence: gradingResultSummary.sourceDetail || gradingSourceSummary,
    },
    padTieIns,
    retainingWall: {
      triggered: wallTriggered,
      label: wallTriggered ? "Wall / bench review" : "No wall trigger",
      tradeoff: wallTriggered
        ? "Wall may reduce haul and protect tie-ins, but adds structural cost."
        : "Open grading likely cheaper than a retaining wall.",
      risk: wallRisk,
    },
    haulBalance: {
      netCf,
      cutCf,
      fillCf,
      balancePct,
      direction,
      label:
        direction === "export"
          ? "Export soil"
          : direction === "import"
            ? "Import fill"
            : direction === "balanced"
              ? "Balanced haul"
              : "Haul pending",
    },
    surfaceModel,
  };
}
