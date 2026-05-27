from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple


GOLDEN_SCENARIOS: Tuple[str, ...] = (
    "small_commercial_pad",
    "multifamily_site",
    "mixed_use_14_acre_site",
    "sloped_detention_site",
    "roadway_corridor",
    "utility_conflict_heavy_site",
    "floodplain_wetland_constrained_site",
    "retaining_wall_site",
    "incomplete_bad_input_case",
    "manual_production_gate_case",
)


@dataclass(frozen=True)
class EngineContract:
    engine_id: str
    name: str
    purpose: str
    current_modules: Tuple[str, ...]
    stage_name: Optional[str]
    owns: FrozenSet[str]
    reads: FrozenSet[str]
    dirty_downstream: FrozenSet[str]
    final_capabilities: Tuple[str, ...]
    required_validations: Tuple[str, ...]
    manual_mode_forbidden: Tuple[str, ...]
    production_readiness_gates: Tuple[str, ...]
    golden_scenarios: Tuple[str, ...]
    maturity: str


def _fs(*items: str) -> FrozenSet[str]:
    return frozenset(item for item in items if item)


def _contract(
    *,
    engine_id: str,
    name: str,
    purpose: str,
    current_modules: Iterable[str],
    stage_name: Optional[str],
    owns: Iterable[str],
    reads: Iterable[str],
    dirty_downstream: Iterable[str],
    final_capabilities: Iterable[str],
    required_validations: Iterable[str],
    manual_mode_forbidden: Iterable[str],
    production_readiness_gates: Iterable[str],
    golden_scenarios: Iterable[str],
    maturity: str,
) -> EngineContract:
    return EngineContract(
        engine_id=engine_id,
        name=name,
        purpose=purpose,
        current_modules=tuple(current_modules),
        stage_name=stage_name,
        owns=frozenset(owns),
        reads=frozenset(reads),
        dirty_downstream=frozenset(dirty_downstream),
        final_capabilities=tuple(final_capabilities),
        required_validations=tuple(required_validations),
        manual_mode_forbidden=tuple(manual_mode_forbidden),
        production_readiness_gates=tuple(production_readiness_gates),
        golden_scenarios=tuple(golden_scenarios),
        maturity=maturity,
    )


ENGINE_CONTRACTS: Tuple[EngineContract, ...] = (
    _contract(
        engine_id="geometry",
        name="Geometry Engine",
        purpose="Core spatial truth system for canonical geometry, topology, relationships, constraints, and buildable calculations.",
        current_modules=("core/geometry_core.py", "core/project_manager.py", "geometry/layout_engine.py"),
        stage_name="layout",
        owns=("project.zones", "project.objects.boundary", "project.graphs", "canonical_geometry", "buildable_area"),
        reads=("field_states", "site_inputs", "existing_conditions"),
        dirty_downstream=("layout", "grading", "drainage", "storm_pipes", "sanitary", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("robust geometry kernel", "topology-aware geometry", "intersections", "constraints", "snapping", "alignment ownership", "corridor modeling", "parcel/buildable calculations"),
        required_validations=("valid_geometry", "non_corrupting_snapshot_restore", "canonical_id_stability", "topology_consistency"),
        manual_mode_forbidden=("silent geometry repair without audit", "invalid canonical geometry", "preview-action-only truth"),
        production_readiness_gates=("all owned geometry valid", "topology checks passed", "canonical ids stable", "buildable calculations traceable"),
        golden_scenarios=("small_commercial_pad", "mixed_use_14_acre_site", "roadway_corridor", "incomplete_bad_input_case"),
        maturity="foundation",
    ),
    _contract(
        engine_id="terrain_surface",
        name="Terrain / Surface Engine",
        purpose="Represent existing/proposed terrain and surface intelligence for realistic grading and drainage.",
        current_modules=("engines/surface_engine.py", "backend/planning/terrain_provider.py", "backend/planning/grading_support.py"),
        stage_name="grading",
        owns=("existing_surface", "proposed_surface", "surface_breaklines", "surface_merge_audit"),
        reads=("canonical_geometry", "existing_conditions", "field_states"),
        dirty_downstream=("grading", "drainage", "storm_pipes", "sanitary", "utility_network", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("DEM/LiDAR ingestion", "terrain cleanup", "breaklines", "merged surfaces", "proposed surfaces", "slope analysis", "drainage-aware grading", "road crown modeling", "ADA-aware grading"),
        required_validations=("surface_extent_valid", "surface_grid_traceable", "slope_range_checked", "breakline_integrity"),
        manual_mode_forbidden=("assumed terrain without label", "surface fallback presented as survey truth"),
        production_readiness_gates=("existing surface source known", "proposed surface generated", "surface QA passed"),
        golden_scenarios=("sloped_detention_site", "roadway_corridor", "retaining_wall_site", "floodplain_wetland_constrained_site"),
        maturity="early",
    ),
    _contract(
        engine_id="grading",
        name="Grading Engine",
        purpose="Generate and coordinate finished grading, contours, spot elevations, and grading repairs.",
        current_modules=("engines/grading_engine.py", "backend/planning/core_stage_runners.py", "backend/planning/grading_support.py"),
        stage_name="grading",
        owns=("grading_summary", "finished_grade_surface", "spot_grades", "contours", "grading_adjustments"),
        reads=("canonical_geometry", "existing_surface", "road_alignments", "utility_networks"),
        dirty_downstream=("drainage", "storm_pipes", "sanitary", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("finished grade generation", "spot elevations", "contours", "ADA path grading", "road grading", "pad grading", "retaining wall integration", "local grading repairs", "constructability checks"),
        required_validations=("surface_created", "cut_fill_traceable", "drainage_direction_checked", "ADA_slope_checked", "building_drainage_clear"),
        manual_mode_forbidden=("grading fallback without failure", "untraceable proposed surface", "unvalidated ADA grades"),
        production_readiness_gates=("proposed surface ready", "critical slopes valid", "earthwork traceable", "grading QA complete"),
        golden_scenarios=("small_commercial_pad", "multifamily_site", "sloped_detention_site", "roadway_corridor", "retaining_wall_site"),
        maturity="active",
    ),
    _contract(
        engine_id="drainage",
        name="Drainage Engine",
        purpose="Understand surface water movement across terrain and target drainage features.",
        current_modules=("engines/drainage_engine.py", "backend/planning/hydrology_stage_runners.py"),
        stage_name="drainage",
        owns=("drainage_summary", "drainage_structures", "drainage_basins", "flow_paths", "low_points"),
        reads=("finished_grade_surface", "canonical_geometry", "hydrology_summary"),
        dirty_downstream=("storm_pipes", "hydrology", "coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("low point detection", "flow paths", "swales", "inlet placement", "runoff routing", "basin targeting", "ponding/overflow/blockage detection", "terrain-aware repairs"),
        required_validations=("low_points_traceable", "flow_paths_traceable", "basins_export_ready", "overflow_checked"),
        manual_mode_forbidden=("symbol-only basins", "untraceable flow paths", "hidden drainage assumptions"),
        production_readiness_gates=("drainage export validation ready", "primary detention basins engineered", "flow paths tied to surface"),
        golden_scenarios=("small_commercial_pad", "sloped_detention_site", "mixed_use_14_acre_site", "floodplain_wetland_constrained_site"),
        maturity="active",
    ),
    _contract(
        engine_id="storm_pipe",
        name="Storm Pipe Engine",
        purpose="Generate realistic stormwater pipe networks with truthful hydraulic validation.",
        current_modules=("engines/pipe_engine.py", "engines/storm/*", "backend/planning/hydrology_stage_runners.py"),
        stage_name="storm_pipes",
        owns=("storm_pipe_summary", "storm_segments", "storm_nodes", "storm_hydraulics", "storm_graph_validation"),
        reads=("drainage_summary", "hydrology_summary", "finished_grade_surface", "canonical_geometry"),
        dirty_downstream=("sanitary", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("inlet networks", "trunks", "pipe sizing", "cumulative upstream flow", "tributary calculations", "capacity", "HGL checks", "detention integration", "rerouting", "post-reroute recalculation", "graph/hydraulic validation"),
        required_validations=("graph_valid", "hydraulic_data_complete", "capacity_ratios_valid", "cover_valid", "detention_connected"),
        manual_mode_forbidden=("geometry-only pipe hydraulics", "missing segment data", "invalid storm graph", "unchecked reroute hydraulics"),
        production_readiness_gates=("storm graph valid", "hydraulic validation complete", "detention/outfall integrated", "export validation ready"),
        golden_scenarios=("small_commercial_pad", "multifamily_site", "mixed_use_14_acre_site", "sloped_detention_site", "utility_conflict_heavy_site"),
        maturity="active",
    ),
    _contract(
        engine_id="sanitary",
        name="Sanitary Engine",
        purpose="Generate fully connected sanitary sewer networks with service, slope, cover, capacity, and graph checks.",
        current_modules=("engines/sanitary_engine.py", "backend/planning/infrastructure_stage_runners.py"),
        stage_name="sanitary",
        owns=("sanitary_summary", "sanitary_segments", "sanitary_manholes", "sanitary_graph_validation", "sanitary_network_validation"),
        reads=("canonical_geometry", "finished_grade_surface", "storm_pipe_summary", "utility_corridors"),
        dirty_downstream=("utility_network", "coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("service laterals", "gravity flow", "slope validation", "manholes", "connectivity", "capacity", "cover checks", "tie-in logic", "service coverage", "rerouting", "conflict coordination"),
        required_validations=("graph_valid", "network_valid", "service_coverage_valid", "cover_valid", "slope_valid"),
        manual_mode_forbidden=("missing sanitary output", "invalid graph", "invalid network", "unchecked storm/sanitary conflict"),
        production_readiness_gates=("all served buildings connected", "graph/network valid", "manholes placed", "profile bands populated when requested"),
        golden_scenarios=("small_commercial_pad", "multifamily_site", "mixed_use_14_acre_site", "utility_conflict_heavy_site"),
        maturity="active",
    ),
    _contract(
        engine_id="water",
        name="Water Engine",
        purpose="Generate pressurized potable/fire systems with pressure, fire-flow, hydrant, looping, and coordination checks.",
        current_modules=("engines/utility_engine.py", "engines/water_sizing_engine.py", "backend/planning/infrastructure_stage_runners.py"),
        stage_name="utility_network",
        owns=("water_summary", "utility_summary", "water_segments", "pressure_zones", "hydrants", "fire_flow_validation"),
        reads=("canonical_geometry", "finished_grade_surface", "storm_pipe_summary", "sanitary_summary", "utility_corridors"),
        dirty_downstream=("coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("pressure zones", "hydrant spacing", "fire flow", "looping", "pressure validation", "velocity checks", "sizing optimization", "conflict rerouting"),
        required_validations=("route_count_valid", "service_coverage_valid", "pressure_or_assumption_labeled", "coordination_hooks_ready"),
        manual_mode_forbidden=("utility fallback routing", "missing utility output", "unlabeled pressure assumptions"),
        production_readiness_gates=("route output ready", "coordination hooks populated", "pressure/fire-flow checks complete or explicitly blocked"),
        golden_scenarios=("small_commercial_pad", "mixed_use_14_acre_site", "utility_conflict_heavy_site", "retaining_wall_site"),
        maturity="early",
    ),
    _contract(
        engine_id="utility_coordination",
        name="Utility Coordination Engine",
        purpose="Coordinate all underground systems using crossing rules, separation validation, corridors, ownership, and constructability scoring.",
        current_modules=("backend/planning/coordination_stage_runner.py", "planner.py", "core/coordination_engine.py"),
        stage_name="coordination_resolution",
        owns=("coordination_summary", "unresolved_conflicts", "resolved_conflicts", "coordination_realism", "resolution_history"),
        reads=("storm_pipe_summary", "sanitary_summary", "utility_summary", "grading_summary", "protected_zones"),
        dirty_downstream=("earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("crossing rules", "separation validation", "trench coordination", "protected-zone avoidance", "ownership logic", "corridors", "rerouting", "conflict grouping", "constructability scoring"),
        required_validations=("rollback_safe_candidates", "post_reroute_validations", "unresolved_conflicts_explicit", "assumptions_labeled"),
        manual_mode_forbidden=("assumption-based critical conflict closure", "unresolved critical conflicts", "partial candidate mutation"),
        production_readiness_gates=("critical conflicts resolved", "candidate isolation proved", "post-reroute validations passed", "failure reasoning complete"),
        golden_scenarios=("utility_conflict_heavy_site", "mixed_use_14_acre_site", "roadway_corridor", "retaining_wall_site"),
        maturity="active",
    ),
    _contract(
        engine_id="roadway_corridor",
        name="Roadway / Corridor Engine",
        purpose="Generate roadway alignments, profiles, sections, sidewalks, ADA, and corridor-aware grading/utility interactions.",
        current_modules=("engines/corridor_engine.py", "backend/planning/core_stage_runners.py", "backend/planning/sheet_stage.py"),
        stage_name="layout",
        owns=("road_alignments", "corridors", "road_profiles", "road_sections", "sidewalks", "ADA_paths"),
        reads=("canonical_geometry", "existing_surface", "field_states"),
        dirty_downstream=("grading", "drainage", "storm_pipes", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("alignments", "profiles", "intersections", "curb returns", "crowns", "superelevation", "sidewalks", "ADA compliance", "corridor grading", "section generation"),
        required_validations=("alignment_valid", "profile_traceable", "ADA_paths_checked", "corridor_sections_traceable"),
        manual_mode_forbidden=("untraceable road profile", "ADA assumed pass without slope evidence"),
        production_readiness_gates=("alignment/profile/section linked", "ADA checks complete", "corridor export ready"),
        golden_scenarios=("roadway_corridor", "mixed_use_14_acre_site", "sloped_detention_site"),
        maturity="early",
    ),
    _contract(
        engine_id="structure",
        name="Structure Engine",
        purpose="Coordinate retaining walls, foundations, bridge interfaces, excavation, grading, and utility interactions.",
        current_modules=("engines/structure_engine.py", "engines/bridge_engine.py"),
        stage_name=None,
        owns=("structure_summary", "retaining_walls", "foundations", "bridge_interfaces", "structure_conflicts"),
        reads=("canonical_geometry", "finished_grade_surface", "utility_summary", "earthwork_summary"),
        dirty_downstream=("grading", "drainage", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("retaining walls", "foundations", "bridge interfaces", "structure conflicts", "excavation interaction", "grading interaction", "utility interaction"),
        required_validations=("structure_geometry_valid", "grading_interaction_checked", "utility_clearance_checked"),
        manual_mode_forbidden=("unvalidated retaining wall assumption", "structure conflict hidden as warning"),
        production_readiness_gates=("structure conflicts resolved or blocked", "quantities traceable", "profile/section links ready"),
        golden_scenarios=("retaining_wall_site", "roadway_corridor", "utility_conflict_heavy_site"),
        maturity="early",
    ),
    _contract(
        engine_id="earthwork",
        name="Earthwork Engine",
        purpose="Understand material movement, excavation, balancing, haul, grading efficiency, walls, and phasing.",
        current_modules=("engines/earthwork_engine.py", "backend/planning/late_stage_runners.py"),
        stage_name="earthwork",
        owns=("earthwork_summary", "cut_fill", "excavation_limits", "haul_balance", "phasing_summary"),
        reads=("finished_grade_surface", "existing_surface", "utility_summary", "structure_summary", "coordination_summary"),
        dirty_downstream=("qa", "quantities", "exports"),
        final_capabilities=("cut/fill", "balancing", "haul optimization", "excavation limits", "grading efficiency", "retaining wall tradeoffs", "construction phasing"),
        required_validations=("cut_fill_traceable", "excavation_limits_checked", "earthwork_quantity_traceable"),
        manual_mode_forbidden=("untraceable cut/fill totals", "ignored utility excavation impacts"),
        production_readiness_gates=("cut/fill computed from surfaces", "excavation impacts included", "quantity traceability complete"),
        golden_scenarios=("sloped_detention_site", "retaining_wall_site", "mixed_use_14_acre_site"),
        maturity="active",
    ),
    _contract(
        engine_id="hydrology",
        name="Hydrology Engine",
        purpose="Understand runoff, storm events, detention sizing, coefficients, hydrographs, overflow, and flood routing.",
        current_modules=("engines/hydrology_engine.py", "engines/detention_engine.py", "backend/planning/hydrology_stage_runners.py"),
        stage_name="drainage",
        owns=("hydrology_summary", "runoff_coefficients", "storm_events", "detention_design", "hydrographs", "overflow_analysis"),
        reads=("drainage_summary", "finished_grade_surface", "existing_conditions", "catchments"),
        dirty_downstream=("drainage", "storm_pipes", "qa", "quantities", "exports"),
        final_capabilities=("Rational Method", "hydrographs", "detention sizing", "runoff coefficients", "storm event modeling", "overflow analysis", "flood routing"),
        required_validations=("runoff_coefficients_traceable", "storm_event_defined", "detention_adequacy_checked"),
        manual_mode_forbidden=("unlabeled runoff coefficient assumption", "detention sizing without basis"),
        production_readiness_gates=("hydrology basis traceable", "detention design checked", "overflow route reviewed"),
        golden_scenarios=("sloped_detention_site", "mixed_use_14_acre_site", "floodplain_wetland_constrained_site"),
        maturity="active",
    ),
    _contract(
        engine_id="conflict_resolution",
        name="Conflict Resolution Engine",
        purpose="Automatically solve engineering conflicts using cluster-aware, rollback-safe, constructability-aware candidates.",
        current_modules=("backend/planning/coordination_stage_runner.py", "backend/planning/coordination_state.py", "engines/conflict_engine.py"),
        stage_name="coordination_resolution",
        owns=("conflict_clusters", "candidate_summaries", "rollback_snapshots", "accepted_resolutions", "failure_reasoning"),
        reads=("coordination_summary", "canonical_geometry", "grading_summary", "utility_networks", "protected_zones"),
        dirty_downstream=("earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("cluster-aware solving", "rollback-safe candidates", "constructability scoring", "ownership rules", "corridor realism", "protected-zone handling", "grading-aware rerouting", "multi-system optimization"),
        required_validations=("snapshot_isolation", "candidate_post_validation", "failure_reasoning_present", "changed_systems_declared"),
        manual_mode_forbidden=("candidate mutation leak", "assumption closure of critical conflicts", "missing failure reasoning"),
        production_readiness_gates=("candidate accepted only after post-validation", "unresolved conflicts explained", "dirty downstream systems marked"),
        golden_scenarios=("utility_conflict_heavy_site", "roadway_corridor", "retaining_wall_site", "manual_production_gate_case"),
        maturity="active",
    ),
    _contract(
        engine_id="qa_validation",
        name="QA / Validation Engine",
        purpose="Truthfully validate engineering completeness, standards, constructability, missing data, and reviewer risk.",
        current_modules=("engines/error_check_engine.py", "review/plan_review_engine.py", "backend/planning/finalization.py"),
        stage_name="qa",
        owns=("qa_summary", "truth_audit", "civil_design_readiness", "engineering_status", "manual_validation"),
        reads=("all_canonical_summaries", "manager_export", "field_states", "deliverables"),
        dirty_downstream=("exports",),
        final_capabilities=("code checks", "hydraulic checks", "grading checks", "ADA checks", "utility checks", "constructability checks", "standards checks", "missing-data detection", "reviewer prediction"),
        required_validations=("manual_gates_run", "truth_audit_complete", "readiness_blockers_explicit", "critical_fallbacks_detected"),
        manual_mode_forbidden=("false production confidence", "hidden missing data", "warning-only critical failure"),
        production_readiness_gates=("zero critical blockers", "truth audit success", "manual gates success", "export readiness confirmed"),
        golden_scenarios=("manual_production_gate_case", "incomplete_bad_input_case", "utility_conflict_heavy_site", "small_commercial_pad"),
        maturity="active",
    ),
    _contract(
        engine_id="quantity",
        name="Quantity Engine",
        purpose="Generate real-time traceable quantities and future cost intelligence from canonical state.",
        current_modules=("engines/quantity_engine.py",),
        stage_name="qa",
        owns=("quantity_summary", "quantity_audit", "cost_estimate", "takeoff_items"),
        reads=("manager_export", "canonical_geometry", "grading_summary", "drainage_summary", "storm_pipe_summary", "sanitary_summary", "utility_summary", "earthwork_summary"),
        dirty_downstream=("exports", "qa"),
        final_capabilities=("earthwork totals", "pipe totals", "pavement totals", "retaining walls", "excavation", "materials", "cost estimation", "bid estimates"),
        required_validations=("quantity_traceability_complete", "canonical_precedence", "source_object_ids_present"),
        manual_mode_forbidden=("action-only quantities when canonical state exists", "untraceable critical quantities"),
        production_readiness_gates=("traceability complete", "canonical quantities preferred", "cost assumptions labeled"),
        golden_scenarios=("small_commercial_pad", "mixed_use_14_acre_site", "retaining_wall_site", "sloped_detention_site"),
        maturity="active",
    ),
    _contract(
        engine_id="export_cad",
        name="Export / CAD Engine",
        purpose="Generate production-quality deliverables from canonical engineering truth.",
        current_modules=("output/dxf_exporter.py", "backend/planning/canonical_export.py", "backend/planning/export_validation.py", "output/preview.py"),
        stage_name="sheets",
        owns=("export_audit", "cad_interop", "sheet_registry", "preview_actions", "deliverable_packages"),
        reads=("all_canonical_summaries", "profiles", "cross_sections", "quantity_summary", "qa_summary"),
        dirty_downstream=(),
        final_capabilities=("DXF/DWG", "Civil3D", "LandXML", "sheet generation", "profiles", "sections", "annotations", "standards", "title blocks"),
        required_validations=("export_audit_complete", "canonical_export_match", "sheet_registry_ready", "profile_section_links_valid"),
        manual_mode_forbidden=("export-ready claim with missing canonical data", "stale geometry export", "symbol-only engineered features"),
        production_readiness_gates=("export validation ready", "sheet/package audit complete", "canonical ids traceable"),
        golden_scenarios=("small_commercial_pad", "mixed_use_14_acre_site", "roadway_corridor", "manual_production_gate_case"),
        maturity="active",
    ),
    _contract(
        engine_id="profile_section",
        name="Profile / Section Engine",
        purpose="Generate live engineering profiles and sections tied to canonical alignments, surfaces, and utilities.",
        current_modules=("backend/planning/sheet_stage.py", "output/dxf_exporter.py"),
        stage_name="sheets",
        owns=("profiles", "cross_sections", "profile_bands", "section_samples"),
        reads=("road_alignments", "storm_pipe_summary", "sanitary_summary", "utility_summary", "finished_grade_surface"),
        dirty_downstream=("qa", "exports"),
        final_capabilities=("roadway profiles", "utility profiles", "grading sections", "retaining wall sections", "dynamic updates", "live coordination"),
        required_validations=("profiles_trace_canonical_alignment", "sections_trace_canonical_surface", "bands_have_required_data"),
        manual_mode_forbidden=("requested profile without canonical signal", "requested section without section data"),
        production_readiness_gates=("profiles/sections generated from canonical state", "bands complete", "export audit matches"),
        golden_scenarios=("roadway_corridor", "mixed_use_14_acre_site", "utility_conflict_heavy_site", "retaining_wall_site"),
        maturity="active",
    ),
    _contract(
        engine_id="gis_existing_conditions",
        name="GIS / Existing Conditions Engine",
        purpose="Understand parcels, zoning, floodplain, wetlands, imagery, survey, utilities, and coordinate systems.",
        current_modules=("backend/planning/existing_conditions_importers.py", "backend/planning/existing_conditions_online.py", "data/survey_points.csv", "vision/*", "parsers/sketch_parser.py"),
        stage_name=None,
        owns=("existing_conditions", "parcel_data", "zoning_data", "floodplain_data", "wetland_data", "survey_control", "existing_utilities", "coordinate_system"),
        reads=("user_inputs", "uploaded_files", "images"),
        dirty_downstream=("geometry", "layout", "terrain_surface", "grading", "drainage", "storm_pipes", "utility_network", "qa", "exports"),
        final_capabilities=("parcels", "zoning", "floodplain", "wetlands", "imagery", "survey", "existing utilities", "coordinate systems"),
        required_validations=("source_metadata_present", "coordinate_system_known_or_labeled", "survey_confidence_labeled"),
        manual_mode_forbidden=("real-world constraint assumed without source", "unlabeled coordinate transform"),
        production_readiness_gates=("existing condition sources cited", "coordinate system resolved", "constraints reflected in QA"),
        golden_scenarios=("floodplain_wetland_constrained_site", "incomplete_bad_input_case", "sloped_detention_site"),
        maturity="early",
    ),
    _contract(
        engine_id="ai_orchestration",
        name="AI Orchestration Engine",
        purpose="Coordinate prompt interpretation, subsystem orchestration, optimization, explanations, assumptions, reruns, and workflow guidance.",
        current_modules=("planner_orchestrator.py", "planner_intelligence.py", "backend/planning/orchestrator.py", "parsers/ai_parser.py"),
        stage_name=None,
        owns=("routing", "planner_workflow", "assumption_summary", "explanations", "optimization_summary", "workflow_guidance"),
        reads=("user_inputs", "field_states", "engine_contracts", "stage_results", "qa_summary"),
        dirty_downstream=("layout", "grading", "drainage", "storm_pipes", "sanitary", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa"),
        final_capabilities=("prompt interpretation", "subsystem orchestration", "optimization", "explanation", "assumptions", "reviewer prediction", "intelligent reruns", "workflow guidance"),
        required_validations=("field_intent_preserved", "stage_route_explained", "assumptions_labeled", "manual_mode_respected"),
        manual_mode_forbidden=("invented user intent", "silent field inference for locked/omitted fields", "unlabeled assumptions"),
        production_readiness_gates=("intent trace complete", "rerun reasons complete", "manual/assisted distinction preserved"),
        golden_scenarios=("manual_production_gate_case", "incomplete_bad_input_case", "mixed_use_14_acre_site"),
        maturity="active",
    ),
    _contract(
        engine_id="reactive_model",
        name="Reactive Model Engine",
        purpose="Make the entire project react intelligently to canonical changes with dependency invalidation and partial reruns.",
        current_modules=("backend/planning/runtime.py", "backend/planning/execution_control.py", "core/project_manager.py"),
        stage_name=None,
        owns=("system_dirty_state", "dependency_graph", "changed_targets", "rerun_history", "reactive_update_report"),
        reads=("engine_contracts", "stage_results", "manager_export", "canonical_snapshots"),
        dirty_downstream=("layout", "grading", "drainage", "storm_pipes", "sanitary", "utility_network", "coordination_resolution", "earthwork", "sheets", "qa", "quantities", "exports"),
        final_capabilities=("change propagation", "dirty reasons", "partial reruns", "rollback-safe reruns", "live update reports", "real-time model behavior"),
        required_validations=("dependency_graph_complete", "dirty_reason_traceable", "partial_rerun_safe", "downstream_closure_correct"),
        manual_mode_forbidden=("stale downstream output", "missing dirty reason", "unexplained rerun"),
        production_readiness_gates=("dirty graph complete", "all reruns explained", "stale outputs blocked from export"),
        golden_scenarios=("small_commercial_pad", "roadway_corridor", "utility_conflict_heavy_site", "manual_production_gate_case"),
        maturity="foundation",
    ),
)


ENGINE_CONTRACT_BY_ID: Dict[str, EngineContract] = {contract.engine_id: contract for contract in ENGINE_CONTRACTS}


PLANNER_STAGE_TO_ENGINE_IDS: Dict[str, Tuple[str, ...]] = {}
for _contract_row in ENGINE_CONTRACTS:
    if _contract_row.stage_name:
        PLANNER_STAGE_TO_ENGINE_IDS.setdefault(_contract_row.stage_name, ())
        PLANNER_STAGE_TO_ENGINE_IDS[_contract_row.stage_name] = (
            *PLANNER_STAGE_TO_ENGINE_IDS[_contract_row.stage_name],
            _contract_row.engine_id,
        )


def get_engine_contract(engine_id: str) -> EngineContract:
    return ENGINE_CONTRACT_BY_ID[engine_id]


def engine_contracts() -> Tuple[EngineContract, ...]:
    return ENGINE_CONTRACTS


def planner_stage_engine_ids(stage_name: str) -> Tuple[str, ...]:
    return PLANNER_STAGE_TO_ENGINE_IDS.get(stage_name, ())


def reactive_dependency_graph() -> Dict[str, Set[str]]:
    return {contract.engine_id: set(contract.dirty_downstream) for contract in ENGINE_CONTRACTS}


def downstream_closure(engine_id: str) -> Set[str]:
    graph = reactive_dependency_graph()
    seen: Set[str] = set()
    pending: List[str] = list(graph.get(engine_id, set()))
    while pending:
        node = pending.pop(0)
        if node in seen:
            continue
        seen.add(node)
        if node in graph:
            pending.extend(sorted(graph[node] - seen))
    return seen


def validate_engine_contracts() -> List[str]:
    issues: List[str] = []
    ids = [contract.engine_id for contract in ENGINE_CONTRACTS]
    if len(ids) != len(set(ids)):
        issues.append("engine ids must be unique")

    field_owners: Dict[str, str] = {}
    for contract in ENGINE_CONTRACTS:
        if not contract.purpose:
            issues.append(f"{contract.engine_id}: purpose missing")
        if not contract.current_modules:
            issues.append(f"{contract.engine_id}: current_modules missing")
        if not contract.owns:
            issues.append(f"{contract.engine_id}: owns missing")
        if not contract.required_validations:
            issues.append(f"{contract.engine_id}: required_validations missing")
        if not contract.production_readiness_gates:
            issues.append(f"{contract.engine_id}: production_readiness_gates missing")
        if not contract.golden_scenarios:
            issues.append(f"{contract.engine_id}: golden_scenarios missing")
        unknown_scenarios = sorted(set(contract.golden_scenarios) - set(GOLDEN_SCENARIOS))
        if unknown_scenarios:
            issues.append(f"{contract.engine_id}: unknown golden scenarios {unknown_scenarios}")
        for field_name in contract.owns:
            prior = field_owners.get(field_name)
            if prior and prior != contract.engine_id:
                issues.append(f"canonical field '{field_name}' has multiple owners: {prior}, {contract.engine_id}")
            field_owners[field_name] = contract.engine_id

    return issues
