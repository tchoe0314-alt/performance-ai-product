export type UserRecord = {
  user_id: string;
  email: string;
  name: string;
};

export type Assumption = {
  field: string;
  value: string;
  reason: string;
};

export type Issue = {
  severity: "warning" | "error";
  message: string;
  code?: string;
  context?: Record<string, unknown>;
};

export type BackendIssue = {
  severity?: string;
  message?: string;
  code?: string;
  context?: Record<string, unknown>;
};

export type BackendAssumption = {
  field_name?: string;
  field?: string;
  assumed_value?: unknown;
  reason?: string;
};

export type ProjectSummary = {
  project_id: string;
  name: string;
  description?: string;
  has_result?: boolean;
  updated_at?: number;
};

export type ProjectRecord = {
  project_id: string;
  name: string;
  description?: string;
  updated_at?: number;
  project_input?: ProjectInput;
  latest_result?: PlanResponse;
  metadata?: ProjectMetadata;
  has_result?: boolean;
};

export type JobSummary = {
  job_id: string;
  status: string;
  job_type?: string;
  project_id?: string | null;
  updated_at?: number;
  error?: string | null;
  result?: PlanResponse | null;
  stage?: string;
  stage_detail?: string;
  progress?: number;
  queue_position?: number | null;
  queued_count?: number;
  running_count?: number;
};

export type WorkflowRunSummary = {
  run_id: string;
  source?: string;
  created_at?: number;
  success?: boolean;
  message?: string;
  input_mode?: string;
  strict_mode?: boolean;
  engineering_status?: {
    success?: boolean;
    status?: string;
    trust_score?: number;
  };
  truth_success?: boolean;
  all_required_complete?: boolean;
  requested_deliverables?: string[];
  produced_deliverables?: string[];
  failed_deliverables?: string[];
  manual_failures?: Array<{
    code?: string;
    message?: string;
    system?: string;
    rule?: string;
    location?: string;
    reason?: string;
  }>;
  coordination_summary?: {
    unresolved_conflicts?: number;
    selected_strategy?: string;
  };
  stage_summary?: {
    statuses?: Record<string, string>;
  };
};

export type WorkflowArtifact = {
  artifact_id: string;
  kind?: string;
  filename?: string;
  created_at?: number;
  download_path?: string;
};

export type WorkflowReviewDashboard = {
  version?: string;
  release_ready?: boolean;
  operational_state?: string;
  primary_attention?: string;
  release_blockers?: string[];
  release_blocker_details?: Array<Record<string, unknown>>;
  run_count?: number;
  artifact_count?: number;
  latest_run?: Record<string, unknown>;
  latest_artifact?: Record<string, unknown>;
  recent_runs?: Array<Record<string, unknown>>;
  recent_artifacts?: Array<Record<string, unknown>>;
  phase_checkpoints?: Record<string, PhaseCheckpoint>;
  combined_view?: PhaseCheckpoint;
  deliverable_manager?: {
    requested?: string[];
    produced?: string[];
    ready?: string[];
    failed?: string[];
    missing?: string[];
    extra?: string[];
    latest_artifact_release_ready?: boolean;
    latest_artifact_release_status?: string;
    latest_artifact_release_blockers?: string[];
  };
  assumption_review?: {
    summary?: Record<string, unknown>;
    requires_approval?: boolean;
    examples?: string[];
  };
  conflict_review?: {
    unresolved_conflict_count?: number;
    blocked_exports?: number;
    primary_attention?: string;
  };
};

export type ManualFailure = {
  code?: string;
  message?: string;
  system?: string;
  rule?: string;
  location?: string;
  reason?: string;
};

export type IterationRecord = Record<string, unknown> & {
  stage?: string;
  status?: string;
  phase?: string;
};

export type MetricValue = number | { value?: number } | null;
export type ManagerMetrics = Record<string, MetricValue>;
export type QuantityTotals = Record<string, number | null | undefined>;

export type PipeSegment = {
  length_ft?: number;
  slope_pct?: number;
  slope_ft_ft?: number;
};

export type StormSummary = {
  segments?: PipeSegment[];
  pipe_segments?: PipeSegment[];
  storm_pipe_segments?: PipeSegment[];
  total_system_flow_cfs?: number;
  total_system_capacity_cfs?: number;
};

export type PlanExplanation = {
  summary?: string;
  overview?: string;
  why?: string;
  reasoning?: string;
};

export type ConvergenceSummary = {
  assumption_summary?: {
    examples?: string[];
  };
  fix_summary?: {
    autofix_actions?: string[];
  };
  blocked_reasons?: string[];
  blocked_exports?: string[];
  unresolved_issue_categories?: string[];
  dominant_issue_categories?: string[];
  unresolved_conflict_count?: number;
};

export type SetupWizardStatus =
  | "complete"
  | "blocked"
  | "needs_review"
  | "pending"
  | "not_started";

export type SetupWizardStep = {
  id: string;
  label: string;
  status: SetupWizardStatus;
  next_action: string;
  why_blocked?: string;
  review_required?: boolean;
  panel?: string;
};

export type SetupWizardStateV1 = {
  schema_version?: "setup_wizard_state_v1" | string;
  steps?: SetupWizardStep[];
  current_step_id?: string;
  current_step_label?: string;
  current_status?: SetupWizardStatus;
  next_action?: string;
  why_blocked?: string;
  blocked_step_ids?: string[];
  needs_review_step_ids?: string[];
  completed_count?: number;
  total_count?: number;
};

export type ProgressTimelineStatus =
  | "completed"
  | "blocked"
  | "needs_review"
  | "current"
  | "pending"
  | "not_started";

export type ProgressTimelineStep = {
  id: string;
  label: string;
  status: ProgressTimelineStatus;
  summary?: string;
  blockers?: string[];
  action_label?: string;
  action_panel?: string;
  action?: {
    type?: string;
    target?: string;
    label?: string;
  };
  source_refs?: string[];
};

export type ProgressTimelineV1 = {
  schema_version?: "progress_timeline_v1" | string;
  order?: string[];
  steps?: ProgressTimelineStep[];
  current_step_id?: string;
  current_step_label?: string;
  current_status?: ProgressTimelineStatus;
  current_panel?: string;
  next_action?: string;
  exact_blockers?: string[];
  blocked_step_ids?: string[];
  needs_review_step_ids?: string[];
  completed_count?: number;
  total_count?: number;
  can_export?: boolean;
  export_blockers?: string[];
  chat_summary?: {
    where_am_i?: string;
    phase?: string;
    whats_left?: string[];
    why_cant_export_yet?: string[];
    what_should_i_do_next?: string;
  };
  truth_label?: string;
};

export type PhaseCheckpoint = {
  label?: string;
  status?: string;
  ready?: boolean;
  deliverables?: string[];
  messages?: string[];
  blockers?: string[];
  has_data?: boolean;
  stages?: string[];
  completed_phase_count?: number;
  total_phase_count?: number;
  blocked_exports?: string[];
  blocked_reasons?: string[];
  deliverables_ready?: string[];
  deliverables_extra?: string[];
  note?: string;
  current_stage?: string;
  current_status?: string;
  job_progress?: number;
};

export type ReactiveRunPolicy = {
  version?: string;
  rerun_mode?: "none" | "auto_live" | "debounced_validation" | "manual_confirm_required" | string;
  estimated_cost?: "none" | "quick" | "moderate" | "heavy" | string;
  estimated_cost_score?: number;
  live_visual_update?: boolean;
  cheap_validation_auto_run?: boolean;
  debounced_validation_ms?: number;
  automatic_engineering_rerun?: boolean;
  requires_user_confirmation?: boolean;
  impact_preview_required?: boolean;
  heavy_impacted_stages?: string[];
  changed_stages?: string[];
  impacted_stages?: string[];
  stale_outputs?: string[];
  export_policy?: string;
  recommended_next_action?: string;
  user_message?: string;
};

export type ReactiveUpdateReport = {
  version?: string;
  changed_engine_ids?: string[];
  changed_stages?: string[];
  impacted_engine_ids?: string[];
  impacted_stages?: string[];
  execution_mode?: string;
  partial_rerun_executed?: boolean;
  partial_rerun_supported?: boolean;
  ran_stages?: string[];
  stale_outputs?: string[];
  export_blocked?: boolean;
  run_policy?: ReactiveRunPolicy;
  post_rerun_stale_outputs?: string[];
  post_rerun_export_blocked?: boolean;
  post_rerun_production_ready?: boolean;
  post_rerun_release_blockers?: string[];
  partial_rerun_telemetry?: {
    elapsed_ms?: number;
    rerun_stages?: string[];
    skipped_stages?: string[];
    quick_threshold_ms?: number;
    within_quick_threshold?: boolean;
  };
};

export type ReactivePartialRerun = {
  enabled?: boolean;
  checkpoint_restored?: boolean;
  impacted_stages?: string[];
  rerun_stages?: string[];
  skipped_stages?: string[];
  telemetry?: {
    elapsed_ms?: number;
    rerun_stages?: string[];
    skipped_stages?: string[];
    quick_threshold_ms?: number;
    within_quick_threshold?: boolean;
  };
};

export type CandidateReviewItem = {
  candidate_id: string;
  candidate_type?: string;
  label?: string;
  source?: string;
  provider?: string;
  source_url?: string;
  source_date?: string;
  confidence?: number | string;
  status?: "accepted" | "rejected" | "pending" | string;
  blocker_review_reason?: string;
  review_required?: boolean;
  accepted_as?: string;
  construction_release_allowed?: boolean;
  audit_trail?: Array<Record<string, unknown>>;
};

export type CandidateReviewInbox = {
  version?: "candidate_review_inbox_v1" | string;
  candidate_count?: number;
  counts?: {
    accepted?: number;
    rejected?: number;
    pending?: number;
  };
  by_type?: Record<string, number>;
  candidates?: CandidateReviewItem[];
  truth_label?: string;
  construction_release_allowed?: boolean;
  construction_release_blocked?: boolean;
};

export type SourceConfidenceEntry = {
  entry_id: string;
  label?: string;
  category?: "source" | "layer" | "object" | "candidate" | "standards" | "production_evidence" | string;
  object_id?: string;
  layer?: string;
  source_type?:
    | "survey-backed"
    | "survey-unverified"
    | "GIS candidate"
    | "official GIS source"
    | "map imagery candidate"
    | "user-drawn"
    | "imported CAD"
    | "DEM-backed"
    | "LiDAR-backed"
    | "inferred"
    | "metadata-only"
    | "missing"
    | "stale/dirty"
    | string;
  source_name?: string;
  confidence_score?: number;
  confidence_band?: "higher" | "review" | "low" | "missing" | string;
  visible_badge?: string;
  status?: string;
  accepted?: boolean;
  verified?: boolean;
  needs_verification?: boolean;
  needs_survey_control?: boolean;
  stale?: boolean;
  dirty?: boolean;
  missing?: boolean;
  low_confidence_reasons?: string[];
  why_low_confidence?: string;
  next_action?: string;
  evidence?: Record<string, unknown>;
  construction_release_allowed?: boolean;
  construction_readiness_implied?: boolean;
  truth_label?: string;
};

export type SourceConfidenceMap = {
  version?: "source_confidence_map_v1" | string;
  generated_on?: string;
  entries?: SourceConfidenceEntry[];
  summary?: {
    entry_count?: number;
    counts_by_source_type?: Record<string, number>;
    counts_by_confidence_band?: Record<string, number>;
    trusted_count?: number;
    low_confidence_count?: number;
    user_drawn_count?: number;
    needs_survey_control_count?: number;
    stale_or_missing_count?: number;
    highest_confidence_labels?: string[];
    low_confidence_labels?: string[];
    user_drawn_labels?: string[];
    needs_survey_control_labels?: string[];
    stale_or_missing_labels?: string[];
  };
  answer_cards?: Record<string, string[]>;
  construction_release_allowed?: boolean;
  construction_readiness_implied?: boolean;
  truth_label?: string;
};

export type SmartFixRecommendation = {
  id?: string;
  blocker_code?: string;
  category?: string;
  severity?: string;
  what_is_wrong?: string;
  why_it_matters?: string;
  can_civora_fix?: boolean;
  fix_mode?: "auto_supported" | "manual_input_required" | string;
  supported_action_id?: string;
  supported_action?: Record<string, unknown>;
  one_action_needed_next?: string;
  missing_user_input_or_source?: string;
  what_happens_after_fix?: string;
  ui_action?: {
    type?: "open_panel" | "run_fix" | "generate_system" | "export_report" | "export_dxf" | "chat_prompt" | string;
    panel?: string;
    target?: string;
    prompt?: string;
  };
  chat_prompt?: string;
  engineer_review_required?: boolean;
};

export type SmartFixRecommendationsV1 = {
  version?: "smart_fix_recommendations_v1" | string;
  recommendation_count?: number;
  auto_fix_action_count?: number;
  manual_action_count?: number;
  recommendations?: SmartFixRecommendation[];
  supported_auto_fix_actions?: Array<Record<string, unknown>>;
  blocked_manual_only_actions?: Array<Record<string, unknown>>;
  next_best_recommendation?: SmartFixRecommendation;
  truth_label?: string;
};

export type PlanMeta = {
  setup_wizard_state_v1?: SetupWizardStateV1;
  progress_timeline_v1?: ProgressTimelineV1;
  explanation?: PlanExplanation;
  convergence_summary?: ConvergenceSummary;
  deliverables?: {
    produced?: string[];
    failed?: string[];
  };
  produced_deliverables?: string[];
  failed_deliverables?: string[];
  release_review?: PreviewReview;
  release_status?: string;
  release_note?: string;
  phase_checkpoints?: Record<string, PhaseCheckpoint>;
  runtime_phase_checkpoint?: {
    stage_name?: string;
  };
  engineering_status?: {
    success?: boolean;
    status?: string;
    trust_score?: number;
  };
  manager_export?: {
    metrics?: ManagerMetrics;
  };
  quantities?: {
    totals?: QuantityTotals;
  };
  storm_pipes?: StormSummary;
  drainage?: Record<string, unknown>;
  grading?: Record<string, unknown>;
  utilities?: Record<string, unknown>;
  truth_audit?: {
    success?: boolean;
  };
  manual_validation?: {
    failures?: ManualFailure[];
  };
  coordination?: Record<string, unknown>;
  reactive_update_report?: ReactiveUpdateReport;
  reactive_partial_rerun?: ReactivePartialRerun;
  export_audit?: Record<string, unknown>;
  candidate_review_inbox_v1?: CandidateReviewInbox;
  source_confidence_map_v1?: SourceConfidenceMap;
  smart_fix_recommendations_v1?: SmartFixRecommendationsV1;
  map_feature_detection_report_v1?: {
    candidate_count?: number;
    feature_candidates?: Array<Record<string, unknown>>;
  };
  online_existing_conditions_discovery_v1?: OnlineExistingConditionsDiscovery;
  existing_conditions_package?: Record<string, unknown>;
  existing_conditions_summary?: Record<string, unknown>;
  candidate_rule_report?: {
    candidate_count?: number;
    candidate_rules?: Array<Record<string, unknown>>;
  };
  standards_candidate_rule_report?: {
    candidate_count?: number;
    candidate_rules?: Array<Record<string, unknown>>;
  };
  iterations?: IterationRecord[];
};

export type PlanAction = {
  geometry?: {
    origin?: [number, number];
    width?: number;
    height?: number;
  };
  label?: string;
  layer?: string;
};

export type PlanResponse = {
  success?: boolean;
  final_plan?: {
    meta?: PlanMeta;
    actions?: PlanAction[];
  };
  assumptions?: BackendAssumption[];
  issues?: BackendIssue[];
  message?: string;
  missing_requirements?: {
    missing_fields?: string[];
    why_needed?: Record<string, string>;
    suggested_next_actions?: string[];
    can_assist_if_enabled?: boolean;
  };
  metadata?: {
    iterations?: IterationRecord[];
    missing_requirements?: {
      missing_fields?: string[];
      why_needed?: Record<string, string>;
      suggested_next_actions?: string[];
      can_assist_if_enabled?: boolean;
    };
  };
  job_progress?: {
    stage?: string;
    [key: string]: unknown;
  };
};

export type SurveyFileInput = {
  filename?: string;
  stored_filename?: string;
  survey_url?: string;
};

export type MapSnapshotInput = {
  filename?: string;
  stored_filename?: string;
  image_path?: string;
  image_url?: string;
};

export type MapAnalysis = Record<string, unknown>;

export type OnlineExistingConditionsSource = {
  key?: string;
  label?: string;
  source_url?: string;
  agency?: string;
  provider?: string;
  confidence?: string | number;
  source_type?: string;
  status?: string;
  candidate_count?: number;
  review_required?: boolean;
  acceptance_status?: string;
  blockers?: string[];
};

export type OnlineExistingConditionsDiscovery = {
  version?: "online_existing_conditions_discovery_v1" | string;
  status?: string;
  source_type?: string;
  location_context?: Record<string, unknown>;
  supported_live_providers?: Array<Record<string, unknown>>;
  fixture_provider_only_sources?: Array<Record<string, unknown>>;
  sources?: OnlineExistingConditionsSource[];
  candidate_count?: number;
  missing_sources?: Array<Record<string, unknown>>;
  failed_sources?: Array<Record<string, unknown>>;
  blockers?: string[];
  survey_control?: Record<string, unknown>;
  review_required?: boolean;
  acceptance_status?: string;
  truth_label?: string;
};

export type SiteInputs = {
  address?: string;
  geocode?: {
    lat?: number;
    lng?: number;
    display_name?: string;
    provider?: string;
    source?: string;
    confidence?: number | string | null;
    crs?: Record<string, unknown>;
    location_context?: Record<string, unknown>;
  };
  location_context?: Record<string, unknown>;
  online_existing_conditions_discovery_v1?: OnlineExistingConditionsDiscovery;
  map_feature_detection_report_v1?: Record<string, unknown>;
  existing_conditions_package?: Record<string, unknown>;
  viewport_bounds?: {
    north?: number;
    south?: number;
    east?: number;
    west?: number;
    center_lat?: number;
    center_lng?: number;
    width_ft?: number;
    height_ft?: number;
  };
  map_snapshot?: MapSnapshotInput;
  map_analysis?: MapAnalysis;
  survey_file?: SurveyFileInput;
  survey_file_type?: string;
  survey_parse_success?: boolean;
  slope_estimate?: SurveySlopeResponse | null;
  survey_points?: number[][];
  survey_point_count?: number;
  survey_point_warnings?: string[];
  survey_bounds?: { min_x?: number; min_y?: number; max_x?: number; max_y?: number } | null;
  survey_elevation_range?: { min?: number; max?: number } | null;
  survey_point_columns?: {
    x?: string;
    y?: string;
    z?: string;
  };
  survey_invalid_rows?: number;
  use_survey_for_grading?: boolean;
  detected_objects?: BuildingPlacement[];
  detection_scale?: {
    distance_ft?: number;
    pixel_distance?: number;
    scale_ft_per_px?: number;
    calibrated?: boolean;
    scale_source?: "mapbox" | "manual" | "approximate";
  };
  site_alignment_locked?: boolean;
  site_boundary_source?: "manual_drawn" | "dimensions" | "map_viewport" | "imported";
  site_boundary_state?: "draft_editable" | "locked_canonical";
  site_boundary_acres?: number;
  site_boundary_geometry?: {
    type: "polygon";
    source: "manual_drawn";
    units: string;
    engineering_status: "review_required";
    construction_release_allowed: false;
    vertices: Array<{ x: number; y: number; units: string }>;
    bounds: { x: number; y: number; w: number; h: number };
  };
  site_rotation_deg?: number;
  drainage_source_override?: "civora" | "user";
};

export type ProjectInputMeta = Record<string, unknown> & {
  site_inputs?: SiteInputs;
  chat_thread?: ChatMessage[];
  auto_named?: boolean;
  auto_file_named?: boolean;
  reactive_edit_policy_preference?: {
    live_visual_update?: boolean;
    cheap_validation_auto_run?: boolean;
    auto_engineering_rerun_max_cost?: "quick" | "moderate" | "heavy";
    debounced_validation_ms?: number;
    require_confirmation_for_heavy_engineering?: boolean;
    stale_exports_block_download?: boolean;
  };
};

export type CanonicalGeometryType = "polyline" | "polygon" | "rect" | "point";

export type CanonicalGeometryHandoffVertexV1 = {
  id: string;
  x: number;
  y: number;
  units: string;
};

export type CanonicalGeometryHandoffMetricsV1 = {
  length_ft?: number;
  area_sf?: number;
  width_ft?: number;
  depth_ft?: number;
};

export type CanonicalGeometryHandoffV1 = {
  schema_version: "canonical_geometry_handoff_v1";
  object_id: string;
  geometry_id: string;
  object_name: string;
  object_type: string;
  geometry_type: CanonicalGeometryType;
  vertices: CanonicalGeometryHandoffVertexV1[];
  units: string;
  coordinate_system: string;
  source: "manual_drawn";
  confidence: "user_drawn_review_required";
  engineering_status: "draft_review_required";
  metrics: CanonicalGeometryHandoffMetricsV1;
  created_at?: string;
  updated_at?: string;
  source_ui_mode: "canvas_draw";
  valid: boolean;
  blockers: string[];
};

export type ManualFields = {
  project_name?: string;
  file_name?: string;
  units?: string;
  project_type?: string;
  lot?: { x: number; y: number; w: number; h: number };
  setback?: number;
  building_width?: number;
  building_depth?: number;
  buildings?: Array<{
    id?: string;
    name: string;
    label?: string;
    x?: number;
    y?: number;
    w?: number;
    d?: number;
    height_ft?: number;
    type?: string;
    use?: string;
    rotation?: number;
    locked?: boolean;
    source?: string;
    generated?: boolean;
    geometry_type?: "polygon" | "polyline" | "rect" | "point";
    geometry?: Array<[number, number]>;
    meta?: Record<string, unknown>;
    systemDependencies?: string[];
  }>;
  site_objects?: Array<{
    id?: string;
    name?: string;
    label?: string;
    type?: string;
    x?: number;
    y?: number;
    w?: number;
    d?: number;
    height_ft?: number;
    rotation?: number;
    locked?: boolean;
    source?: string;
    generated?: boolean;
    geometry_type?: "polygon" | "polyline" | "rect" | "point";
    geometry?: Array<[number, number]>;
    meta?: Record<string, unknown>;
    canonical_geometry_handoff_v1?: CanonicalGeometryHandoffV1;
    systemDependencies?: string[];
  }>;
  canonical_geometry_handoff_v1?: CanonicalGeometryHandoffV1[];
  site_plan?: { parking_count?: number };
  grading?: {
    min_slope_pct?: number;
    max_parking_slope_pct?: number;
    max_road_grade_pct?: number;
    max_ada_cross_slope_pct?: number;
  };
  drainage?: {
    min_pipe_slope_pct?: number;
    forced_inlets?: Array<Record<string, unknown>>;
    connect_orphans?: boolean;
    allow_slope_adjustment?: boolean;
    max_slope_adjust?: number;
  };
  ponds?: Array<{
    id?: string;
    name?: string;
    x?: number;
    y?: number;
    w?: number;
    d?: number;
    rotation?: number;
    locked?: boolean;
    source?: string;
    generated?: boolean;
    geometry_type?: "polygon" | "polyline" | "rect" | "point";
    geometry?: Array<[number, number]>;
    meta?: Record<string, unknown>;
    systemDependencies?: string[];
  }>;
  access_points?: Array<{
    id?: string;
    name?: string;
    x?: number;
    y?: number;
    w?: number;
    d?: number;
    rotation?: number;
    locked?: boolean;
    source?: string;
    generated?: boolean;
    geometry_type?: "polygon" | "polyline" | "rect" | "point";
    geometry?: Array<[number, number]>;
    meta?: Record<string, unknown>;
    systemDependencies?: string[];
  }>;
  disciplines?: string[];
  terrain?: string;
};

export type ProjectInput = {
  project_id?: string | null;
  full_design_mode?: boolean;
  input_mode?: StrategyMode;
  strict_mode?: boolean;
  prompt_text?: string | null;
  image_path?: string | null;
  manual_fields?: ManualFields;
  allow_ai_fill_for_blanks?: boolean;
  meta?: ProjectInputMeta;
};

export type ProjectMetadata = Record<string, unknown> & {
  workflow?: {
    runs?: WorkflowRunSummary[];
    artifacts?: WorkflowArtifact[];
    summary?: Record<string, unknown>;
    review_dashboard?: WorkflowReviewDashboard;
  };
};

export type PlanRequestPayload = Record<string, unknown> & {
  project_id?: string | null;
  full_design_mode?: boolean;
  input_mode?: StrategyMode;
  strict_mode?: boolean;
  prompt_text?: string | null;
  image_path?: string | null;
  manual_fields?: ManualFields;
  allow_ai_fill_for_blanks?: boolean;
  optimize_goal?: string | null;
  meta?: ProjectInputMeta;
};

export type PreviewRequestPayload = Record<string, unknown> & {
  project_id?: string | null;
  result?: PlanResponse;
  filename_stem?: string;
  preview_mode?: "production" | "engineering" | "debug";
  preview_style?: string;
  label_density?: "low" | "standard" | "high";
};

export type PhaseMetric = {
  label: string;
  value: number | null;
  unit: string;
  format?: "count";
};

export type PhaseStats = {
  layout: PhaseMetric[];
  grading: PhaseMetric[];
  drainage_storm: PhaseMetric[];
  utilities: PhaseMetric[];
  coordination_validation: PhaseMetric[];
};

export type AuthStatus = {
  auth_enabled: boolean;
  user_count: number;
};

export type DisciplineToggle = {
  label: string;
  checked: boolean;
  setter: React.Dispatch<React.SetStateAction<boolean>>;
  desc: string;
};

export type PreviewResponse = {
  success: boolean;
  preview_image_data_url: string;
  preview_annotations?: {
    profile?: string;
    audit?: {
      rendered_final_count?: number;
      filtered_helper_count?: number;
      hidden_incomplete_phase_count?: number;
      filtered_reasons?: Record<string, number>;
      generated_counts?: Record<string, { total?: number; final?: number; overlay?: number; helper?: number; debug?: number }>;
      rendered_counts?: Record<string, { total?: number; final?: number; overlay?: number; helper?: number; debug?: number }>;
      stage_diagnostics?: Record<
        string,
        {
          stage?: string;
          started?: boolean;
          status?: string;
          message?: string;
          success?: boolean | null;
          generated?: { total?: number; final?: number; overlay?: number; helper?: number; debug?: number };
          rendered?: { total?: number; final?: number; overlay?: number; helper?: number; debug?: number };
          export_validation?: Record<string, unknown>;
          storm_export_validation?: Record<string, unknown>;
        }
      >;
    };
    labels?: {
      label: string;
      layer: string;
      x: number;
      y: number;
      bounds?: { x1: number; y1: number; x2: number; y2: number };
      meta?: {
        system?: string;
        preview_role?: string;
        entity_id?: string;
        source_stage?: string;
        source_type?: string;
        inferred?: boolean;
        entity_type?: string;
        canonical_source_type?: string;
        length_ft?: number | null;
        width_ft?: number | null;
        height_ft?: number | null;
        area_sf?: number | null;
        diameter_in?: number | null;
        slope_pct?: number | null;
        slope_ft_ft?: number | null;
        flow_cfs?: number | null;
        elevation_ft?: number | null;
        invert_start_ft?: number | null;
        invert_end_ft?: number | null;
      };
    }[];
  };
  summary?: {
    project_name?: string;
    units?: string;
    action_count?: number;
    review?: {
      trust_score?: number;
      converged?: boolean;
      passes_run?: number;
      unresolved_conflict_count?: number;
      assumption_count?: number;
      assumption_categories?: string[];
      assumption_examples?: string[];
      autofix_actions?: string[];
      dominant_fix_targets?: string[];
      review_categories?: string[];
      blocked_exports?: string[];
      blocked_reasons?: string[];
      requested_deliverables?: string[];
      ready_deliverables?: string[];
      produced_deliverables?: string[];
      extra_deliverables?: string[];
      failed_deliverables?: string[];
      rerun_total?: number;
      rerun_stages?: string[];
      rerun_reasons?: string[];
      phase_checkpoints?: Record<
        string,
        {
          label?: string;
          status?: string;
          ready?: boolean;
          deliverables?: string[];
          messages?: string[];
          blockers?: string[];
          has_data?: boolean;
          stages?: string[];
          completed_phase_count?: number;
          total_phase_count?: number;
          blocked_exports?: string[];
          blocked_reasons?: string[];
          deliverables_ready?: string[];
          deliverables_extra?: string[];
          note?: string;
          current_stage?: string;
          current_status?: string;
          job_progress?: number;
        }
      >;
      release_status?: "ready" | "review" | "blocked" | string;
      release_note?: string;
    };
  };
};

export type PreviewReview = NonNullable<PreviewResponse["summary"]>["review"];

export type UploadImageResponse = {
  success: boolean;
  image_path?: string;
  image_url?: string;
  filename?: string;
};

export type UploadSurveyResponse = {
  success: boolean;
  filename?: string;
  stored_filename?: string;
  survey_url?: string;
  file_type?: string;
  parse_success?: boolean;
  point_count?: number;
  contour_count?: number;
  recognized_columns?: { x?: string; y?: string; z?: string };
  invalid_rows?: number;
  bounds?: { min_x?: number; min_y?: number; max_x?: number; max_y?: number };
  elevation_range?: { min?: number; max?: number };
  warnings?: string[];
  message?: string;
};

export type ExistingConditionsImportMatrixRow = {
  source?: string;
  source_type?: string;
  success?: boolean;
  canonicalized?: boolean;
  metadata_only?: boolean;
  status?: "canonical" | "metadata_only" | "blocked" | "review_required" | string;
  review_required?: boolean;
  production_usable?: boolean;
  canonical_targets?: string[];
  dependency_blocked?: boolean;
  required_dependency?: string;
  blocker_messages?: string[];
};

export type UploadExistingConditionsResponse = {
  success: boolean;
  message?: string;
  filename?: string;
  stored_filename?: string;
  file_url?: string;
  file_type?: string;
  imports?: Array<Record<string, unknown>>;
  canonical_existing_conditions?: Record<string, unknown>;
  import_validation?: {
    production_usable?: boolean;
    blockers?: Array<Record<string, unknown>>;
    warnings?: string[];
    terrain_source_confidence?: Record<string, unknown>;
    import_matrix?: ExistingConditionsImportMatrixRow[];
    importer_production_matrix?: ExistingConditionsImportMatrixRow[];
    canonical_vs_metadata_only?: Record<string, unknown>;
  };
  import_matrix?: ExistingConditionsImportMatrixRow[];
  canonical_vs_metadata_only?: Record<string, unknown>;
  blockers?: Array<Record<string, unknown>>;
  blocker_details?: Array<Record<string, unknown>>;
  existing_conditions_summary?: Record<string, unknown>;
  existing_conditions_package?: Record<string, unknown>;
  warnings?: string[];
};

export type SurveySlopeResponse = {
  success: boolean;
  slope_ratio?: number;
  slope_percent?: number;
  downhill_dx?: number;
  downhill_dy?: number;
  direction?: string;
  point_count?: number;
  warnings?: string[];
  recognized_columns?: { x?: string; y?: string; z?: string };
  invalid_rows?: number;
};

export type SurveyPointsResponse = {
  points?: number[][];
  point_count?: number;
  warnings?: string[];
  recognized_columns?: { x?: string; y?: string; z?: string };
  invalid_rows?: number;
};

export type ImageFeatureDetection = {
  kind: string;
  bbox: [number, number, number, number];
  confidence?: number;
  geometry_type?: "polygon" | "polyline" | "rect";
  geometry?: Array<[number, number]>;
};

export type ImageDetectResponse = {
  success: boolean;
  message?: string;
  image_width?: number;
  image_height?: number;
  detections?: ImageFeatureDetection[];
  warnings?: string[];
};

export type PlanToolMode = "run" | "fix" | "improve";

export type BuildingPlacement = {
  id: string;
  label: string;
  x?: number;
  y?: number;
  w: number;
  d: number;
  h?: number;
  rotation?: number;
  type?: SiteObjectType;
  use?: string;
  stallCount?: number;
  source?: "user" | "manual_drawn" | "generated" | "inferred" | "detected_from_image" | "user_confirmed";
  generated?: boolean;
  confidence?: number;
  confirmed?: boolean;
  geometryType?: "polygon" | "polyline" | "rect" | "point";
  geometry?: Array<[number, number]>;
  capabilities?: {
    movable?: boolean;
    resizable?: boolean;
    rotatable?: boolean;
    deletable?: boolean;
  };
  systemDependencies?: Array<"roads" | "parking" | "grading" | "drainage" | "utilities">;
  meta?: Record<string, unknown>;
  locked?: boolean;
  placed?: boolean;
};

export type SiteObjectType =
  | "site"
  | "setback_zone"
  | "no_build_zone"
  | "building"
  | "retail_building"
  | "multifamily_building"
  | "industrial_building"
  | "office_building"
  | "pad"
  | "pool"
  | "amenity"
  | "open_space"
  | "entrance"
  | "driveway"
  | "road"
  | "parking"
  | "sidewalk"
  | "basin"
  | "outfall"
  | "inlet"
  | "manhole"
  | "hydrant"
  | "utility_corridor"
  | "lot_block"
  | "bridge"
  | "custom";

export type SiteObjectPlacement = BuildingPlacement & {
  type: SiteObjectType;
};
export type StrategyMode = "user" | "assisted";
export type ControlOverrides = Partial<{
  projectType: string;
  units: string;
  roads: boolean;
  grading: boolean;
  drainage: boolean;
  utilities: boolean;
  siteName: string;
  fileName: string;
  lotWidth: string | number;
  lotHeight: string | number;
  buildingWidth: string | number;
  buildingDepth: string | number;
  buildingCount: string | number;
  setback: string | number;
  parkingCount: string | number;
  minSlopePct: string | number;
  pipeMinSlopePct: string | number;
  maxParkingSlopePct: string | number;
  maxRoadGradePct: string | number;
  maxAdaCrossSlopePct: string | number;
}>;

export type ChatDecisionIntent =
  | "conversation"
  | "settings"
  | "design"
  | "explain"
  | "fix"
  | "improve";

export type ChatDecisionResponse = {
  success: boolean;
  intent: ChatDecisionIntent;
  assistant_message: string;
  run_mode: "none" | "run" | "fix" | "improve";
  design_prompt: string;
  needs_clarification: boolean;
  reason: string;
  confidence: number;
  control_overrides: ControlOverrides;
  response_metadata?: {
    intent?: string;
    outcome?: string;
    state_changed?: boolean;
    selected_action?: string;
    missing_inputs?: string[];
    blockers?: string[];
    ui_navigation_target?: string;
    requested_ui_mode?: string;
    requested_preview_mode?: string;
    requested_preview_quality?: string;
    requested_site_lock_state?: string;
    required_missing_inputs?: string[];
    action_taken?: string;
    action_blocked_reason?: string;
    affected_systems?: string[];
    assumptions?: string[];
    next_best_action?: string;
    command_payload?: Record<string, unknown>;
  };
  required_missing_inputs?: string[];
  action_taken?: string;
  action_blocked_reason?: string;
  affected_systems?: string[];
  assumptions?: string[];
  next_best_action?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: number;
  kind?: "message" | "status" | "explanation" | "action";
  feedback?: "up" | "down";
  phaseTag?: string;
};

export type LearningReport = {
  feedback?: {
    up?: number;
    down?: number;
    total?: number;
    score_percent?: number;
  };
  training_examples?: {
    count?: number;
    synthetic?: number;
    feedback_based?: number;
    interaction?: number;
  };
};

export type Preview3DItem = {
  x: number;
  y: number;
  w: number;
  h: number;
  height: number;
  z?: number;
  color: string;
  label: string;
  layer: string;
};
