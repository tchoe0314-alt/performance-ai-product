import { useMemo } from "react";

import type {
  Issue,
  ManualFailure,
  ManagerMetrics,
  PlanExplanation,
  PlanMeta,
  PreviewResponse,
  QuantityTotals,
  SmartFixRecommendation,
  StormSummary,
} from "../types";
import {
  buildDashboardCalculationOverlayStats,
  buildDashboardEngineeringMetrics,
  buildDashboardMeasurementOverlayStats,
} from "../utils/dashboardEngineeringMetrics";
import {
  buildDashboardGradingBlocker,
  buildDashboardIssueTargets,
} from "../utils/dashboardIssueTargets";
import { buildDashboardSuggestedImproveGoal } from "../utils/dashboardPlanResultView";
import { buildDashboardQuantityRows } from "../utils/dashboardQuantityRows";
import {
  buildDrainageLowPoints,
  buildGradingResultSummary,
  buildStormHydrologyReview,
  buildStormPipeSegments,
  buildWaterFireFlowReview,
} from "../utils/dashboardReviewSummaries";
import { buildRoadwayWorkbenchData } from "../components/CivilRoadwayWorkbench";

type DashboardEngineeringReviewStateOptions = {
  currentPlanMeta: PlanMeta;
  issues: Issue[];
  planPreviewAnnotations: PreviewResponse["preview_annotations"] | null;
  selectedIssueId: string | null;
  smartFixItems: SmartFixRecommendation[];
};

export function useDashboardEngineeringReviewState({
  currentPlanMeta,
  issues,
  planPreviewAnnotations,
  selectedIssueId,
  smartFixItems,
}: DashboardEngineeringReviewStateOptions) {
  const managerMetrics = useMemo<ManagerMetrics>(
    () => currentPlanMeta?.manager_export?.metrics ?? {},
    [currentPlanMeta],
  );
  const quantityTotals = useMemo<QuantityTotals>(
    () => currentPlanMeta?.quantities?.totals ?? {},
    [currentPlanMeta],
  );
  const quantityExplain = useMemo(
    () => currentPlanMeta?.quantities?.explain ?? {},
    [currentPlanMeta],
  );
  const costEstimate = useMemo(
    () => currentPlanMeta?.cost_estimate ?? {},
    [currentPlanMeta],
  );
  const stormSummary = useMemo<StormSummary>(() => currentPlanMeta?.storm_pipes ?? {}, [currentPlanMeta]);
  const pipeSegments = useMemo(() => buildStormPipeSegments(stormSummary), [stormSummary]);
  const drainageSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.drainage ?? {}, [currentPlanMeta]);
  const gradingSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.grading ?? {}, [currentPlanMeta]);
  const roadwayWorkbenchData = useMemo(
    () => buildRoadwayWorkbenchData(currentPlanMeta),
    [currentPlanMeta],
  );
  const drainageLowPoints = useMemo(
    () => buildDrainageLowPoints({ drainageSummary, gradingSummary }),
    [drainageSummary, gradingSummary],
  );
  const stormHydrologyReview = useMemo(
    () => buildStormHydrologyReview({ stormSummary, drainageSummary, pipeSegments, smartFixItems }),
    [drainageSummary, pipeSegments, smartFixItems, stormSummary],
  );
  const waterFireFlowReview = useMemo(
    () => buildWaterFireFlowReview(planPreviewAnnotations),
    [planPreviewAnnotations],
  );
  const gradingResultSummary = useMemo(
    () => buildGradingResultSummary(gradingSummary),
    [gradingSummary],
  );
  const previewLabels = useMemo(
    () => planPreviewAnnotations?.labels ?? [],
    [planPreviewAnnotations],
  );
  const issueTargets = useMemo(
    () => buildDashboardIssueTargets(issues, previewLabels),
    [issues, previewLabels],
  );
  const gradingBlocker = useMemo(() => buildDashboardGradingBlocker(issues), [issues]);
  const selectedIssueLabel = issueTargets.find((item) => item.id === selectedIssueId)?.label ?? "";
  const engineeringMetrics = useMemo(
    () => buildDashboardEngineeringMetrics({
      managerMetrics,
      pipeSegments,
      stormSummary,
      gradingSummary,
      drainageSummary,
    }),
    [drainageSummary, gradingSummary, managerMetrics, pipeSegments, stormSummary],
  );
  const { totalPipeLength, maxSlope, minSlope, flowCfs, cutFillNet, basinSize } = engineeringMetrics;
  const quantityRows = useMemo(
    () => buildDashboardQuantityRows({ costEstimate, quantityExplain, quantityTotals }),
    [costEstimate, quantityExplain, quantityTotals],
  );
  const measurementOverlayStats = useMemo(
    () => buildDashboardMeasurementOverlayStats(quantityTotals),
    [quantityTotals],
  );
  const calculationOverlayStats = useMemo(
    () => buildDashboardCalculationOverlayStats(engineeringMetrics),
    [engineeringMetrics],
  );
  const currentTruthAudit = useMemo(
    () => currentPlanMeta?.truth_audit ?? {},
    [currentPlanMeta],
  );
  const currentManualFailures = useMemo<ManualFailure[]>(
    () =>
      Array.isArray(currentPlanMeta?.manual_validation?.failures)
        ? currentPlanMeta.manual_validation.failures
        : [],
    [currentPlanMeta],
  );
  const currentExplanation = useMemo<PlanExplanation>(
    () => currentPlanMeta?.explanation ?? {},
    [currentPlanMeta],
  );
  const suggestedImproveGoal = useMemo(
    () => buildDashboardSuggestedImproveGoal({ currentManualFailures, issues }),
    [currentManualFailures, issues],
  );

  return {
    basinSize,
    calculationOverlayStats,
    costEstimate,
    currentExplanation,
    currentManualFailures,
    currentTruthAudit,
    cutFillNet,
    drainageLowPoints,
    drainageSummary,
    engineeringMetrics,
    flowCfs,
    gradingBlocker,
    gradingResultSummary,
    gradingSummary,
    issueTargets,
    managerMetrics,
    maxSlope,
    measurementOverlayStats,
    minSlope,
    pipeSegments,
    previewLabels,
    quantityExplain,
    quantityRows,
    quantityTotals,
    roadwayWorkbenchData,
    selectedIssueLabel,
    stormHydrologyReview,
    stormSummary,
    suggestedImproveGoal,
    totalPipeLength,
    waterFireFlowReview,
  };
}
