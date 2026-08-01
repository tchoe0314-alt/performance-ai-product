import type {
  CostEstimate,
  CostLineItem,
  QuantityAuditEntry,
  QuantityExplain,
} from "../types";
import {
  COST_APPLICABLE_QUANTITY_METRICS,
  QUANTITY_METRIC_LABELS,
  QUANTITY_METRIC_ORDER,
  quantityMetricFallbackUnit,
  quantityMetricLabel,
  readNumberOrNull,
  uniqueStrings,
  type QuantityReviewRow,
  type QuantityReviewStatus,
} from "./workflowConstants";

export function buildDashboardQuantityRows({
  costEstimate,
  quantityExplain,
  quantityTotals,
}: {
  costEstimate: CostEstimate;
  quantityExplain: QuantityExplain;
  quantityTotals: Record<string, unknown>;
}): QuantityReviewRow[] {
  const audit = quantityExplain.quantity_audit ?? {};
  const costLines = Array.isArray(costEstimate.line_items) ? costEstimate.line_items : [];
  const costByMetric = new Map<string, CostLineItem>();
  costLines.forEach((item) => {
    if (item.metric) costByMetric.set(item.metric, item);
  });
  const pricingGaps = costEstimate.explain?.pricing_coverage_gaps ?? {};
  const traceGaps = {
    ...(quantityExplain.trace_gaps ?? {}),
    ...(costEstimate.explain?.trace_gaps ?? {}),
  };
  const metricKeys = uniqueStrings([
    ...QUANTITY_METRIC_ORDER,
    ...Object.keys(quantityTotals),
    ...Object.keys(audit),
    ...costLines.map((item) => item.metric),
    ...Object.keys(pricingGaps),
    ...Object.keys(traceGaps),
  ]);

  return metricKeys
    .map((metric): QuantityReviewRow | null => {
      const quantity = readNumberOrNull(quantityTotals[metric]);
      if (quantity === null || quantity <= 0) return null;
      const auditEntry: QuantityAuditEntry = audit[metric] ?? {};
      const costLine = costByMetric.get(metric);
      const unit = costLine?.unit || QUANTITY_METRIC_LABELS[metric]?.unit || quantityMetricFallbackUnit(metric);
      const canonicalIds = uniqueStrings([
        ...(auditEntry.canonical_object_ids ?? []),
        ...(auditEntry.canonical_ids ?? []),
        ...(auditEntry.source_object_ids ?? []),
        ...(costLine?.source_object_ids ?? []),
      ]);
      const sourceIds = uniqueStrings([
        ...(auditEntry.source_ids ?? []),
        ...(auditEntry.source_object_ids ?? []),
        ...(costLine?.source_object_ids ?? []),
      ]);
      const previousQuantity =
        readNumberOrNull(auditEntry.previous_quantity) ??
        readNumberOrNull(auditEntry.before) ??
        null;
      const currentQuantity =
        readNumberOrNull(auditEntry.current_quantity) ??
        readNumberOrNull(auditEntry.after) ??
        quantity;
      const explicitDelta = readNumberOrNull(auditEntry.delta);
      const delta =
        explicitDelta !== null
          ? explicitDelta
          : previousQuantity !== null && currentQuantity !== null
            ? currentQuantity - previousQuantity
            : null;
      const costApplicable = Boolean(
        costLine || pricingGaps[metric] || COST_APPLICABLE_QUANTITY_METRICS.has(metric),
      );
      const traceRequired = Boolean(
        costApplicable || Object.prototype.hasOwnProperty.call(audit, metric) || traceGaps[metric],
      );
      const missingCost = costApplicable && (Boolean(pricingGaps[metric]) || !costLine);
      const traceComplete = !traceRequired || Boolean(
        auditEntry.trace_complete ??
          costLine?.trace_complete ??
          (canonicalIds.length > 0 && !traceGaps[metric]),
      );
      const status: QuantityReviewStatus = missingCost
        ? "missing_cost"
        : !traceComplete
          ? "untraced"
          : delta !== null && Math.abs(delta) > 0.0001
            ? "stale"
            : costLine?.production_price
              ? "ok"
              : costApplicable
                ? "review"
                : "reference";
      return {
        metric,
        label: quantityMetricLabel(metric),
        quantity,
        unit,
        canonicalIds,
        sourceIds,
        sourceStage: String(auditEntry.source_stage || auditEntry.source || "canonical quantity model"),
        sourceLayer: String(auditEntry.source_layer || costLine?.category || "model"),
        method: String(auditEntry.method || auditEntry.formula || "quantity audit"),
        confidence: String(auditEntry.confidence || costLine?.unit_price_source?.confidence || "review"),
        costApplicable,
        traceRequired,
        traceComplete,
        delta,
        previousQuantity,
        currentQuantity,
        costItem: costLine?.item || (costApplicable ? "Unmapped" : "Reference total"),
        unitCost: readNumberOrNull(costLine?.unit_cost),
        amount: readNumberOrNull(costLine?.amount),
        currency: costLine?.currency || "USD",
        priceSource: costLine?.unit_price_source?.source_name || costLine?.pricing_source || (costApplicable ? "Missing unit-price mapping" : "Not costed separately"),
        priceSourceItemId: costLine?.unit_price_source?.source_item_id || costLine?.unit_price_source_item_id || "",
        productionPrice: Boolean(costLine?.production_price),
        missingCost,
        status,
      };
    })
    .filter((row): row is QuantityReviewRow => Boolean(row));
}
