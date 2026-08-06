import type { SiteInputs } from "../types";

const ADDRESS_SOURCE_CONTEXT_KEYS = [
  "geocode",
  "location_context",
  "online_existing_conditions_discovery_v1",
  "map_feature_detection_report_v1",
  "existing_conditions_package",
  "existing_conditions_summary",
  "candidate_review_inbox_v1",
  "candidate_review_decisions_v1",
  "candidate_review_accepted_drafts_v1",
  "candidate_review_rejected_v1",
  "source_confidence_map_v1",
  "civora_vision_training_dataset_v1",
  "civora_vision_quality_report_v1",
  "civora_vision_ground_truth_ledger_v1",
  "civora_vision_ground_truth_dataset_v1",
  "civora_vision_split_registry_v1",
  "civora_vision_active_learning_queue_v1",
  "civora_vision_ground_truth_coverage_v1",
  "civora_vision_review_workspace_v1",
  "source_context_detection_coverage_v1",
  "source_context_fetch_metrics_v1",
  "source_context_cache_v1",
  "auto_existing_conditions_v1",
  "imagery_object_detection_report_v1",
  "site_intelligence_summary_v1",
  "location_source_strategy_v1",
  "map_analysis",
  "map_snapshot",
  "slope_estimate",
] as const;

export function clearAddressSourceContext(siteInputs: SiteInputs): SiteInputs {
  const next = { ...(siteInputs ?? {}) } as Record<string, unknown>;
  ADDRESS_SOURCE_CONTEXT_KEYS.forEach((key) => delete next[key]);
  return next as SiteInputs;
}
