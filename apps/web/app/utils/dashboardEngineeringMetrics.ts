import type { ManagerMetrics, MetricValue, PipeSegment, StormSummary } from "../types";
import { readMetricValue } from "./formatting";
import { readNumberOrNull } from "./workflowConstants";

export type DashboardEngineeringMetrics = {
  totalPipeLength: number | null;
  maxSlope: number | null;
  minSlope: number | null;
  flowCfs: number | null;
  cutFillNet: number | null;
  basinSize: number | null;
};

export function buildDashboardEngineeringMetrics({
  managerMetrics,
  pipeSegments,
  stormSummary,
  gradingSummary,
  drainageSummary,
}: {
  managerMetrics: ManagerMetrics;
  pipeSegments: PipeSegment[];
  stormSummary: StormSummary;
  gradingSummary: Record<string, unknown>;
  drainageSummary: Record<string, unknown>;
}): DashboardEngineeringMetrics {
  const totalPipeLength =
    readMetricValue(managerMetrics.storm_pipe_length_ft) ??
    (pipeSegments.length
      ? pipeSegments.reduce((sum, seg) => sum + Number(seg.length_ft || 0), 0)
      : null);
  const maxSlope = pipeSegments.length
    ? Math.max(
        ...pipeSegments.map((seg) =>
          Number(seg.slope_pct ?? (seg.slope_ft_ft ?? 0) * 100),
        ),
      )
    : null;
  const minSlope = pipeSegments.length
    ? Math.min(
        ...pipeSegments.map((seg) =>
          Number(seg.slope_pct ?? (seg.slope_ft_ft ?? 0) * 100),
        ),
      )
    : null;
  const flowCfs =
    readMetricValue(managerMetrics.pipe_capacity_total_cfs) ??
    readMetricValue(stormSummary.total_system_flow_cfs) ??
    readMetricValue(stormSummary.total_system_capacity_cfs) ??
    null;
  const cutFillNet =
    readMetricValue(managerMetrics.earthwork_net_cf) ??
    readMetricValue((gradingSummary as { earthwork?: { net_cf?: MetricValue } })?.earthwork?.net_cf) ??
    null;
  const basinSize =
    (Array.isArray(drainageSummary?.basins) &&
      (readNumberOrNull(drainageSummary.basins[0]?.area_sf) ??
        readNumberOrNull(drainageSummary.basins[0]?.footprint_area_sf))) ||
    null;
  return { totalPipeLength, maxSlope, minSlope, flowCfs, cutFillNet, basinSize };
}

export function buildDashboardMeasurementOverlayStats(quantityTotals: Record<string, unknown>) {
  return [
    { label: "Lot area", value: readNumberOrNull(quantityTotals.lot_area_sf), unit: "sf" },
    { label: "Building area", value: readNumberOrNull(quantityTotals.building_area_sf), unit: "sf" },
    { label: "Parking area", value: readNumberOrNull(quantityTotals.parking_area_sf), unit: "sf" },
    { label: "Road length", value: readNumberOrNull(quantityTotals.road_length_ft), unit: "ft" },
    { label: "Impervious area", value: readNumberOrNull(quantityTotals.estimated_impervious_area_sf), unit: "sf" },
    { label: "Parking stalls", value: readNumberOrNull(quantityTotals.estimated_parking_stalls), unit: "stalls" },
  ];
}

export function buildDashboardCalculationOverlayStats(metrics: DashboardEngineeringMetrics) {
  return [
    { label: "Total pipe length", value: metrics.totalPipeLength, unit: "ft" },
    { label: "Max slope", value: metrics.maxSlope, unit: "%" },
    { label: "Min slope", value: metrics.minSlope, unit: "%" },
    { label: "Flow (CFS)", value: metrics.flowCfs, unit: "cfs" },
    { label: "Cut / fill net", value: metrics.cutFillNet, unit: "cf" },
    { label: "Pond size", value: metrics.basinSize, unit: "sf" },
  ];
}
