import type { CandidateReviewInbox, CivoraVisionReviewWorkspace, OnlineExistingConditionsDiscovery } from "../types";
import type { SystemGenerationTarget } from "./workflowConstants";

export type AddressSuggestion = {
  success?: boolean;
  status?: string;
  blocked?: boolean;
  lat?: number;
  lng?: number;
  display_name?: string;
  provider?: string;
  message?: string;
  confidence?: number | string | null;
  crs?: Record<string, unknown>;
  location_context?: Record<string, unknown>;
  blockers?: Array<{ area?: string; code?: string; message?: string }>;
};
export type OnlineExistingConditionsFetchResponse = {
  success?: boolean;
  status?: string;
  online_existing_conditions_discovery_v1?: OnlineExistingConditionsDiscovery;
  map_feature_detection_report_v1?: Record<string, unknown>;
  existing_conditions_package?: Record<string, unknown>;
  existing_conditions_summary?: Record<string, unknown>;
  canonical_existing_conditions?: Record<string, unknown>;
  candidate_review_inbox_v1?: CandidateReviewInbox;
  civora_vision_review_workspace_v1?: CivoraVisionReviewWorkspace;
  source_context_detection_coverage_v1?: Record<string, unknown>;
  warnings?: string[];
};
export type AutoExistingConditionsUiStatus = {
  status: "idle" | "waiting" | "running" | "ready" | "blocked";
  message: string;
  candidateCount: number;
  missing: string[];
};
export type AutoSiteContextFlowSummary = {
  candidateCount: number;
  candidateLabels: string[];
  missingLabels: string[];
  status: string;
  message: string;
  reviewRequired: boolean;
};
export type GenerateFlowSummary = {
  version: "generate_flow_summary_v1";
  generated_at: string;
  target: SystemGenerationTarget;
  ran: string[];
  skipped: string[];
  needs_review: string[];
  notes: string[];
  blocked: boolean;
  next_action: string;
  auto_site_context: AutoSiteContextFlowSummary;
  user_layout_context?: {
    count: number;
    semantic_count: number;
    labels: string[];
    drawn_labels?: string[];
    affected_systems: string[];
    review_required: boolean;
  } | null;
  safety_wording: string;
};
export type ReviewPackageFlowSummary = {
  version: "review_package_flow_summary_v1";
  generated_at: string;
  outputs_created: string[];
  missing: string[];
  blocked: boolean;
  next_action: string;
  auto_site_context: AutoSiteContextFlowSummary;
  review_only: true;
  engineer_review_required: true;
  safety_wording: string;
};
export type UtilityCatalogSource = {
  source_name?: string;
  source_type?: string;
  source_reference?: string;
  jurisdiction?: string;
  company?: string;
  effective_date?: string;
  reviewed_by?: string;
  review_date?: string;
  notes?: string;
};
export type UtilityPipeCatalogItem = {
  item_id?: string;
  network?: string;
  material?: string;
  sizes_in?: number[];
  pressure_class?: string;
  source?: UtilityCatalogSource;
  review_status?: string;
  accepted_for_workspace?: boolean;
  limitations?: string[];
};
export type UtilityPartCatalogItem = {
  item_id?: string;
  network?: string;
  part_type?: string;
  name?: string;
  compatible_materials?: string[];
  compatible_sizes_in?: number[];
  source?: UtilityCatalogSource;
  review_status?: string;
  accepted_for_workspace?: boolean;
  limitations?: string[];
};
export type UtilityCatalogResponse = {
  version?: string;
  pipes?: UtilityPipeCatalogItem[];
  parts?: UtilityPartCatalogItem[];
  policy?: Record<string, unknown>;
  summary?: {
    pipe_catalog_count?: number;
    part_catalog_count?: number;
    accepted_pipe_catalog_count?: number;
    accepted_part_catalog_count?: number;
    review_required_count?: number;
  };
};
export type CustomerTemplateSummary = {
  template_id?: string;
  name?: string;
  firm_name?: string;
  review_status?: string;
  accepted_for_workspace?: boolean;
  present_sections?: string[];
  missing_sections?: string[];
  layer_count?: number;
  title_block_count?: number;
  label_style_count?: number;
  symbol_count?: number;
  report_template_count?: number;
  cost_book_link_count?: number;
  pipe_hook_ready?: boolean;
  roadway_hook_ready?: boolean;
};
export type CustomerTemplateRegistryResponse = {
  version?: string;
  active_template_id?: string;
  summaries?: CustomerTemplateSummary[];
  active_template?: Record<string, unknown> | null;
  behavior?: {
    status?: string;
    template_behavior?: string[];
    blockers?: string[];
    active_template?: CustomerTemplateSummary | null;
  };
  policy?: {
    truth_label?: string;
    customer_standard_only?: boolean;
    jurisdiction_compliance_claim?: boolean;
  };
};
export const hasAddressCoordinates = (
  value: AddressSuggestion | null | undefined,
): value is AddressSuggestion & { lat: number; lng: number; display_name: string } =>
  Boolean(
    value &&
      !value.blocked &&
      Number.isFinite(value.lat) &&
      Number.isFinite(value.lng) &&
      value.display_name,
  );
export const sourceStatusLabel = (value: string | undefined) =>
  String(value || "missing").replace(/_/g, " ");
