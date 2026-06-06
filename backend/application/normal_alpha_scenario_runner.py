from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any, Dict

from backend.planning.construction_package import build_construction_document_support_package
from backend.planning.engine_depth_audit import run_engine_depth_audit_for_scenario
from backend.planning.engine_readiness import evaluate_engine_readiness
from backend.planning.engineer_review_package import build_engineer_review_package
from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.production_depth import enrich_storm_production_depth
from backend.planning.production_evidence import build_production_evidence
from core.civil_design import civil_design_readiness


RUNNER_VERSION = "normal_alpha_scenario_runner_v1"
REAL_PROJECT_SUITE_VERSION = "real_project_scenario_suite_v1"
HEAVY_EXPORT_BLOCKER = "heavy_cad_dxf_export_skipped_review_only"
LICENSED_ENGINEER_REVIEW_BLOCKER = "external_licensed_engineer_review_required"

RESPONSIBILITY_LABEL = (
    "Civora prepares engineer-review-ready evidence only; Civora does not stamp, seal, sign, "
    "certify, approve construction, submit construction documents, or act as engineer of record."
)


def _storm_fixture() -> tuple[Dict[str, Any], Dict[str, Any]]:
    storm = {
        "success": True,
        "source": "storm_network_engine",
        "segments": [
            {
                "id": "STM-ALPHA-1",
                "pipe": "STM-ALPHA-1",
                "from": "CB-ALPHA-1",
                "to": "OUT-ALPHA-1",
                "path": [[620.0, 500.0], [710.0, 590.0]],
                "length_ft": 100.0,
                "diameter_in": 24.0,
                "flow_cfs": 1.0,
                "slope_ft_ft": 0.01,
                "mannings_n": 0.013,
                "start_invert_ft": 100.0,
                "end_invert_ft": 99.0,
                "tributary_area_sf": 12000.0,
            }
        ],
        "target_outfall": {"name": "OUT-ALPHA-1", "target_name": "OUT-ALPHA-1", "x": 710.0, "y": 590.0, "z": 98.5},
        "graph_validation": {"valid": True},
        "hydraulic_validation": {"valid": True},
        "missing_data_segments": [],
    }
    drainage = {
        "success": True,
        "source": "drainage_engine",
        "coordination": {"preferred_outfall": {"name": "OUT-ALPHA-1", "target_name": "OUT-ALPHA-1", "x": 710.0, "y": 590.0, "z": 98.5}},
        "surface_controls": {"primary_low_point": {"x": 710.0, "y": 590.0, "z": 98.5}},
        "surface_guidance": {"surface_source": "review_fixture", "surface_from_grading": True},
        "catchments": [{"name": "C-ALPHA-1", "runoff_c": 0.82, "runoff_coefficient": 0.82}],
        "stats": {
            "total_basin_runoff_cfs": 1.0,
            "total_estimated_inlet_flow_cfs": 1.0,
            "total_contributing_area_sf": 12000.0,
        },
        "structures": [{"name": "CB-ALPHA-1", "x": 620.0, "y": 500.0, "estimated_flow_cfs": 1.0, "capacity_cfs": 20.0}],
        "basins": [{"name": "BASIN-1", "target_name": "OUT-ALPHA-1"}],
        "low_points": [{"name": "LP-ALPHA-1", "x": 710.0, "y": 590.0, "z": 98.5}],
        "flow_paths": [{"from": "CB-ALPHA-1", "to": "OUT-ALPHA-1", "points": [[620.0, 500.0], [710.0, 590.0]]}],
        "detention_routing": [
            {
                "basin": "BASIN-1",
                "routing_source": "review_fixture",
                "routing_method": "stage_storage_hydrograph",
                "required_storage_cf": 4200.0,
                "provided_storage_cf": 5000.0,
                "release_cfs": 1.0,
                "outlet": {"type": "orifice", "release_cfs": 1.0, "source": "review_fixture_outlet"},
                "drawdown_hours": 18.0,
                "stage_storage": [
                    {"elevation_ft": 96.0, "storage_cf": 0.0},
                    {"elevation_ft": 98.0, "storage_cf": 2500.0},
                    {"elevation_ft": 99.0, "storage_cf": 5000.0},
                ],
            }
        ],
        "overflow_paths": [{"name": "OF-ALPHA-1", "capacity_valid": True, "capacity_cfs": 5.0, "required_capacity_cfs": 4.0, "source": "review_fixture_spillway"}],
        "overflow_analysis": {"valid": True, "production_valid": True},
    }
    return storm, drainage


def _base_meta() -> Dict[str, Any]:
    lot = {"x": 0.0, "y": 0.0, "w": 875.0, "h": 700.0, "area_sf": 612500.0}
    storm, drainage = _storm_fixture()
    return {
        "project_id": "normal-alpha-scenario",
        "source_project_id": "normal-alpha-scenario",
        "canonical_model_id": "canon-normal-alpha-scenario",
        "canonical_model_hash": "hash-normal-alpha-scenario-001",
        "canonical_revision": "rev-normal-alpha-scenario-001",
        "product_mode": "private_alpha",
        "ready_language": "ready_for_engineer_review",
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "construction_release_required": True,
        "responsibility_label": RESPONSIBILITY_LABEL,
        "site_locked": True,
        "site_boundary": {"id": "SITE-ALPHA", **lot, "locked": True},
        "site": {"lot": lot, "locked": True},
        "lot": lot,
        "building_count": 4,
        "parking_count": 180,
        "parking_program": {"stall_count": 180},
        "layout": {"success": True, "objects": ["SITE-ALPHA", "BLDG-1", "BLDG-2", "BLDG-3", "RETAIL-1", "PARK-1", "BASIN-1"]},
        "alignments": [{"id": "ALG-LOOP-1", "type": "internal_loop_road", "length_ft": 620.0, "points": [[80.0, 80.0], [680.0, 80.0], [680.0, 560.0], [80.0, 560.0], [80.0, 80.0]]}],
        "grading": {
            "success": True,
            "source_quality": "review_fixture",
            "source_detail": "deterministic normal alpha review state",
            "accepted_existing_surface_id": "EG-REVIEW-1",
            "accepted_proposed_surface_id": "FG-REVIEW-1",
            "surface_traceability": {
                "valid": True,
                "accepted_surfaces": True,
                "existing_surface_id": "EG-REVIEW-1",
                "proposed_surface_id": "FG-REVIEW-1",
            },
            "existing_surface": {"id": "EG-REVIEW-1", "source_quality": "review_fixture"},
            "proposed_surface": {"id": "FG-REVIEW-1", "source": "deterministic_review_fixture"},
            "low_points": [{"id": "LP-1", "x": 710.0, "y": 590.0, "z": 98.5}],
            "spot_grades": [{"id": "SG-1", "x": 120.0, "y": 120.0, "z": 101.2, "surface_id": "FG-REVIEW-1"}],
            "contours": [{"contour_id": "FG-100", "interval_ft": 2.0, "proposed_surface_id": "FG-REVIEW-1", "contour_count": 2}],
        },
        "drainage": drainage,
        "storm_pipes": enrich_storm_production_depth(storm, drainage),
        "sanitary": {
            "success": True,
            "source": "sanitary_engine_review_fixture",
            "route_count": 8,
            "service_count": 4,
            "manhole_count": 5,
            "expected_service_buildings": ["BLDG-1", "BLDG-2", "BLDG-3", "RETAIL-1"],
            "served_buildings": ["BLDG-1", "BLDG-2", "BLDG-3", "RETAIL-1"],
            "tie_in_node": "SAN_TIE_IN",
            "segments": [
                {
                    "id": "SAN-LAT-1",
                    "name": "SAN-LAT-1",
                    "segment_role": "lateral",
                    "served_building": "BLDG-1",
                    "from": "BLDG-1",
                    "to": "NODE-A",
                    "start_name": "BLDG-1",
                    "end_name": "NODE-A",
                    "route_points": [[120.0, 120.0], [120.0, 80.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.02,
                    "capacity_cfs": 1.8,
                    "capacity_ratio": 0.011,
                    "slope_ft_ft": 0.02,
                    "cover_start_ft": 4.0,
                    "cover_end_ft": 4.8,
                    "post_reroute_recalculated": True,
                    "upstream_service_flow_cfs": 0.02,
                },
                {
                    "id": "SAN-LAT-2",
                    "name": "SAN-LAT-2",
                    "segment_role": "lateral",
                    "served_building": "BLDG-2",
                    "from": "BLDG-2",
                    "to": "NODE-B",
                    "start_name": "BLDG-2",
                    "end_name": "NODE-B",
                    "route_points": [[270.0, 120.0], [270.0, 80.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.02,
                    "capacity_cfs": 1.8,
                    "capacity_ratio": 0.011,
                    "slope_ft_ft": 0.02,
                    "cover_start_ft": 4.0,
                    "cover_end_ft": 4.8,
                    "post_reroute_recalculated": True,
                    "upstream_service_flow_cfs": 0.02,
                },
                {
                    "id": "SAN-LAT-3",
                    "name": "SAN-LAT-3",
                    "segment_role": "lateral",
                    "served_building": "BLDG-3",
                    "from": "BLDG-3",
                    "to": "NODE-C",
                    "start_name": "BLDG-3",
                    "end_name": "NODE-C",
                    "route_points": [[420.0, 120.0], [420.0, 80.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.02,
                    "capacity_cfs": 1.8,
                    "capacity_ratio": 0.011,
                    "slope_ft_ft": 0.02,
                    "cover_start_ft": 4.0,
                    "cover_end_ft": 4.8,
                    "post_reroute_recalculated": True,
                    "upstream_service_flow_cfs": 0.02,
                },
                {
                    "id": "SAN-LAT-4",
                    "name": "SAN-LAT-4",
                    "segment_role": "lateral",
                    "served_building": "RETAIL-1",
                    "from": "RETAIL-1",
                    "to": "NODE-D",
                    "start_name": "RETAIL-1",
                    "end_name": "NODE-D",
                    "route_points": [[130.0, 450.0], [180.0, 360.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.03,
                    "capacity_cfs": 1.8,
                    "capacity_ratio": 0.017,
                    "slope_ft_ft": 0.018,
                    "cover_start_ft": 4.0,
                    "cover_end_ft": 5.0,
                    "post_reroute_recalculated": True,
                    "upstream_service_flow_cfs": 0.03,
                },
                {
                    "id": "SAN-MAIN-1",
                    "name": "SAN-MAIN-1",
                    "segment_role": "main",
                    "from": "NODE-A",
                    "to": "NODE-B",
                    "start_name": "NODE-A",
                    "end_name": "NODE-B",
                    "route_points": [[120.0, 80.0], [270.0, 80.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.02,
                    "capacity_cfs": 1.2,
                    "capacity_ratio": 0.017,
                    "slope_ft_ft": 0.01,
                    "cover_start_ft": 5.2,
                    "cover_end_ft": 6.7,
                    "post_reroute_recalculated": True,
                    "upstream_service_flow_cfs": 0.02,
                },
                {
                    "id": "SAN-MAIN-2",
                    "name": "SAN-MAIN-2",
                    "segment_role": "main",
                    "from": "NODE-B",
                    "to": "NODE-C",
                    "start_name": "NODE-B",
                    "end_name": "NODE-C",
                    "route_points": [[270.0, 80.0], [420.0, 80.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.04,
                    "capacity_cfs": 1.2,
                    "capacity_ratio": 0.033,
                    "slope_ft_ft": 0.01,
                    "cover_start_ft": 6.7,
                    "cover_end_ft": 8.2,
                    "post_reroute_recalculated": True,
                    "upstream_service_flow_cfs": 0.04,
                },
                {
                    "id": "SAN-MAIN-3",
                    "name": "SAN-MAIN-3",
                    "segment_role": "main",
                    "from": "NODE-C",
                    "to": "NODE-D",
                    "start_name": "NODE-C",
                    "end_name": "NODE-D",
                    "route_points": [[420.0, 80.0], [180.0, 360.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.06,
                    "capacity_cfs": 1.2,
                    "capacity_ratio": 0.05,
                    "slope_ft_ft": 0.008,
                    "cover_start_ft": 8.2,
                    "cover_end_ft": 10.0,
                    "post_reroute_recalculated": True,
                    "upstream_service_flow_cfs": 0.06,
                },
                {
                    "id": "SAN-MAIN-4",
                    "name": "SAN-MAIN-4",
                    "segment_role": "main",
                    "from": "NODE-D",
                    "to": "SAN_TIE_IN",
                    "start_name": "NODE-D",
                    "end_name": "SAN_TIE_IN",
                    "route_points": [[180.0, 360.0], [120.0, 610.0]],
                    "diameter_in": 8.0,
                    "flow_cfs": 0.09,
                    "capacity_cfs": 1.2,
                    "capacity_ratio": 0.075,
                    "slope_ft_ft": 0.008,
                    "cover_start_ft": 10.0,
                    "cover_end_ft": 12.0,
                    "post_reroute_recalculated": True,
                    "upstream_service_flow_cfs": 0.09,
                    "tie_in_validated": True,
                },
            ],
            "manholes": [
                {"name": "SMH-A", "node_id": "NODE-A", "x": 120.0, "y": 80.0},
                {"name": "SMH-B", "node_id": "NODE-B", "x": 270.0, "y": 80.0},
                {"name": "SMH-C", "node_id": "NODE-C", "x": 420.0, "y": 80.0},
                {"name": "SMH-D", "node_id": "NODE-D", "x": 180.0, "y": 360.0},
                {"name": "SAN_TIE_IN", "node_id": "SAN_TIE_IN", "x": 120.0, "y": 610.0},
            ],
            "service_coverage": {
                "expected_buildings": ["BLDG-1", "BLDG-2", "BLDG-3", "RETAIL-1"],
                "served_buildings": ["BLDG-1", "BLDG-2", "BLDG-3", "RETAIL-1"],
                "missing_buildings": [],
                "valid": True,
            },
            "post_reroute_recalculation": {
                "service_flow_total_cfs": 0.09,
                "main_segments_recomputed": 4,
                "service_segments_recomputed": 4,
                "node_inflow_cfs": {"NODE-A": 0.02, "NODE-B": 0.04, "NODE-C": 0.06, "NODE-D": 0.09, "SAN_TIE_IN": 0.09},
                "disconnected_service_count": 0,
                "all_segments_recalculated": True,
            },
            "structure_spacing_validation": {"valid": True, "max_spacing_ft": 400.0, "generated_manhole_count": 0},
            "network_validation": {
                "valid": True,
                "slope_violations": [],
                "invalid_cover_segments": [],
                "tie_in_issues": [],
                "invalid_capacity_segments": [],
                "missing_recalculation_evidence": [],
                "missing_service_buildings": [],
                "service_coverage": {"valid": True, "missing_buildings": []},
                "tie_in_validation": {"valid": True, "tie_in_node": "SAN_TIE_IN", "outfall_nodes": ["SAN_TIE_IN"]},
                "capacity_validation": {"valid": True, "invalid_capacity_segments": [], "max_capacity_ratio": 0.075},
                "post_reroute_recalculation_evidence": {"all_segments_recalculated": True},
            },
            "graph_validation": {"valid": True},
        },
        "utilities": {
            "success": True,
            "source": "utility_engine_review_fixture",
            "segments": [{"id": "WAT-1", "type": "water", "length_ft": 410.0}],
            "conflict_hooks": {
                "minimum_horizontal_separation_ft": 10.0,
                "minimum_vertical_separation_ft": 1.5,
                "utility_segments": [
                    {
                        "id": "WAT-1",
                        "name": "WAT-1",
                        "system_type": "water",
                        "segment_role": "main",
                        "hydraulic_mode": "pressure",
                        "route_points": [[90.0, 110.0], [660.0, 110.0]],
                        "cover_start_ft": 4.0,
                        "cover_end_ft": 4.0,
                    }
                ],
            },
            "coordination": {
                "post_validation_valid": True,
                "clearance_total_checks": 2,
                "clearance_compliant_checks": 2,
                "required_horizontal_separation_ft": 10.0,
                "required_vertical_separation_ft": 1.5,
            },
        },
        "coordination": {"success": True, "detected_conflicts": 0, "resolved_conflicts": [], "unresolved_conflicts": []},
        "truth_audit": {"success": True},
        "manual_validation": {"success": True, "failures": []},
        "quantities": {
            "success": True,
            "totals": {"lot_area_sf": 612500.0, "estimated_parking_stalls": 180, "pipe_length_ft": 100.0},
            "explain": {
                "meta_summary": {"quantity_traceability_complete": True},
                "quantity_audit": {
                    "pipe_length_ft": {"source_object_ids": ["STM-ALPHA-1"]},
                    "roadway_area_sf": {"source_object_ids": ["ALG-LOOP-1"]},
                    "utility_length_ft": {"source_object_ids": ["WAT-1", "SAN-MAIN-1", "SAN-MAIN-2", "SAN-MAIN-3", "SAN-MAIN-4"]},
                },
                "trace_gaps": {},
            },
        },
        "export_audit": {
            "ready": False,
            "production_export_ready": False,
            "export_blocked": True,
            "blocked_reasons": [HEAVY_EXPORT_BLOCKER],
            "heavy_export_skipped": True,
            "truth_label": "Heavy CAD/DXF export is intentionally skipped in the lightweight alpha runner; no CAD export success is claimed.",
        },
        "standards_package": {
            "status": "blocked_review_required",
            "production_usable": False,
            "construction_release_allowed": False,
            "construction_release_blocked": True,
            "blockers": [
                {
                    "area": "standards",
                    "field": "adopted_jurisdictional_standards",
                    "message": "No externally accepted jurisdictional standards package is attached.",
                    "severity": "blocker",
                    "engineer_review_required": True,
                }
            ],
            "truth_label": "Fixture scenarios do not fake adopted standards or jurisdictional approval.",
        },
        "cad_interop": {"dxf": False, "landxml": False, "civil3d": False, "dwg": False},
        "deliverables": {
            "requested": ["site_plan", "grading_plan", "drainage_plan", "storm_pipe_plan", "utility_plan", "dxf", "report", "engineer_review_package"],
            "produced": ["site_plan", "grading_plan", "drainage_plan", "storm_pipe_plan", "utility_plan", "report", "engineer_review_package"],
            "failed": [],
            "skipped": ["dxf"],
            "missing": ["dxf"],
        },
        "stage_completeness": {
            "statuses": {
                "layout": "complete",
                "grading": "complete",
                "drainage": "complete",
                "storm_pipes": "complete",
                "sanitary": "complete",
                "utility_network": "complete",
                "coordination_resolution": "complete",
                "qa": "complete",
            }
        },
        "construction_readiness": {"ready": False, "status": "engineer_review_required", "blockers": [{"area": "deliverables", "field": HEAVY_EXPORT_BLOCKER}]},
        "construction_package_manifest": {"release_allowed": False, "construction_ready": False, "blockers": [{"area": "deliverables", "field": HEAVY_EXPORT_BLOCKER}]},
    }


def build_normal_alpha_scenario_plan(*, attach_audit: bool = True) -> Dict[str, Any]:
    meta = _base_meta()
    lot = meta["lot"]
    plan = {
        "project_id": "normal-alpha-scenario",
        "project_name": "Normal Alpha Scenario Runner",
        "units": "ft",
        "actions": [
            {"task": "rectangle", "layer": "SITE", "canonical_source_type": "site", "canonical_source_id": "SITE-ALPHA", "x": 0, "y": 0, "w": lot["w"], "h": lot["h"]},
            {"task": "rectangle", "layer": "BUILDING", "canonical_source_type": "building", "canonical_source_id": "BLDG-1", "x": 120, "y": 120, "w": 110, "h": 58},
            {"task": "rectangle", "layer": "BUILDING", "canonical_source_type": "building", "canonical_source_id": "BLDG-2", "x": 270, "y": 120, "w": 110, "h": 58},
            {"task": "rectangle", "layer": "BUILDING", "canonical_source_type": "building", "canonical_source_id": "BLDG-3", "x": 420, "y": 120, "w": 110, "h": 58},
            {"task": "rectangle", "layer": "BUILDING", "canonical_source_type": "retail", "canonical_source_id": "RETAIL-1", "x": 130, "y": 450, "w": 70, "h": 45},
            {"task": "polyline", "layer": "ROAD", "canonical_source_type": "road_alignment", "canonical_source_id": "ALG-LOOP-1", "points": [[80, 80], [680, 80], [680, 560], [80, 560], [80, 80]]},
            {"task": "rectangle", "layer": "PARKING", "canonical_source_type": "parking", "canonical_source_id": "PARK-1", "x": 240, "y": 430, "w": 260, "h": 120},
            {"task": "rectangle", "layer": "BASIN_BOUNDARY", "canonical_source_type": "detention_basin", "canonical_source_id": "BASIN-1", "x": 650, "y": 545, "w": 130, "h": 110},
            {"task": "polyline", "layer": "STORM", "canonical_source_type": "storm_pipe_segment", "canonical_source_id": "STM-ALPHA-1", "points": [[620, 500], [710, 590]]},
            {"task": "polyline", "layer": "SAN", "canonical_source_type": "sanitary_segment", "canonical_source_id": "SAN-MAIN-1", "points": [[120, 80], [270, 80]]},
            {"task": "polyline", "layer": "WATER", "canonical_source_type": "water_segment", "canonical_source_id": "WAT-1", "points": [[90, 110], [660, 110]]},
        ],
        "meta": meta,
    }
    meta["production_evidence"] = build_production_evidence(plan)
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    meta["export_package_report_v1"] = build_export_package_report_v1(plan, export_type="report")
    meta["engineer_review_package_v1"] = build_engineer_review_package(plan)
    meta["construction_document_support_package_v1"] = build_construction_document_support_package(plan)
    if attach_audit:
        meta["engine_depth_audit_report_v1"] = run_engine_depth_audit_for_scenario(
            "mixed_use_14_acre_site",
            build_plan_fn=lambda _payload: build_normal_alpha_scenario_plan(attach_audit=False),
        )
    return plan


def run_normal_alpha_scenario() -> Dict[str, Any]:
    started = perf_counter()
    plan = build_normal_alpha_scenario_plan()
    meta = plan["meta"]
    audit = deepcopy(meta["engine_depth_audit_report_v1"])
    blockers = [
        {
            "area": "deliverables",
            "field": HEAVY_EXPORT_BLOCKER,
            "message": "Heavy CAD/DXF export was skipped by the lightweight alpha runner; no CAD export success is claimed.",
            "severity": "blocker",
            "engineer_review_required": True,
        }
    ]
    blockers.extend(deepcopy(audit.get("blockers") or []))
    elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
    return {
        "version": RUNNER_VERSION,
        "status": "completed_with_blockers",
        "success": True,
        "elapsed_ms": elapsed_ms,
        "construction_release_allowed": False,
        "ready_language": "ready_for_engineer_review",
        "heavy_exports": {
            "skipped": ["dxf"],
            "blocker": HEAVY_EXPORT_BLOCKER,
            "truth_label": "The lightweight runner skips heavy CAD/DXF export and records a review-only blocker instead of claiming export success.",
        },
        "plan": plan,
        "export_package_report_v1": deepcopy(meta["export_package_report_v1"]),
        "engineer_review_package_v1": deepcopy(meta["engineer_review_package_v1"]),
        "construction_document_support_package_v1": deepcopy(meta["construction_document_support_package_v1"]),
        "engine_depth_audit_report_v1": audit,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "remaining_engine_depth_blockers": deepcopy(audit.get("failed_check_ids") or []),
        "truth_label": "Normal alpha scenario runner exercises review package contracts only; Civora does not stamp, seal, sign, certify, approve, submit, or act as engineer of record.",
    }


def _review_blocker(area: str, field: str, message: str) -> Dict[str, Any]:
    return {
        "area": area,
        "field": field,
        "message": message,
        "severity": "blocker",
        "engineer_review_required": True,
    }


def _scenario_fixture_inputs(scenario_id: str) -> list[Dict[str, Any]]:
    root = "backend/fixtures/real_input_benchmarks"
    fixture_map = {
        "survey_backed_commercial_pad": [
            {"type": "survey_csv", "path": f"{root}/survey_points.csv", "fixture": True},
            {"type": "constraints_geojson", "path": f"{root}/constraints.geojson", "fixture": True},
            {"type": "landxml_metadata", "path": f"{root}/surface_pipe.landxml", "fixture": True},
        ],
        "dem_backed_drainage_detention_site": [
            {"type": "dem_grid", "path": "deterministic_inline_2x2_dem_fixture", "fixture": True},
            {"type": "constraints_geojson", "path": f"{root}/constraints.geojson", "fixture": True},
        ],
        "utility_heavy_site": [
            {"type": "utility_conflict_rows", "path": "deterministic_inline_utility_crossings", "fixture": True},
            {"type": "survey_csv", "path": f"{root}/survey_points.csv", "fixture": True},
        ],
        "roadway_corridor": [
            {"type": "alignment_profile_sections", "path": "deterministic_inline_corridor_fixture", "fixture": True},
            {"type": "landxml_metadata", "path": f"{root}/surface_pipe.landxml", "fixture": True},
        ],
        "incomplete_bad_input_case": [
            {"type": "incomplete_payload", "path": "missing_site_boundary_missing_control_missing_standards", "fixture": True}
        ],
    }
    return deepcopy(fixture_map[scenario_id])


def _base_project_plan(project_id: str, project_name: str) -> Dict[str, Any]:
    plan = build_normal_alpha_scenario_plan(attach_audit=False)
    meta = plan["meta"]
    plan["project_id"] = project_id
    plan["project_name"] = project_name
    meta["project_id"] = project_id
    meta["source_project_id"] = project_id
    meta["canonical_model_id"] = f"canon-{project_id}"
    meta["canonical_model_hash"] = f"hash-{project_id}-001"
    meta["canonical_revision"] = f"rev-{project_id}-001"
    return plan


def _attach_survey_control_fixture(meta: Dict[str, Any]) -> None:
    meta["survey"] = {
        "point_count": 5,
        "benchmark": "REAL-BM-1",
        "benchmark_elevation": 612.42,
        "horizontal_datum": "NAD83",
        "datum": "NAVD88",
        "control_verified": True,
        "survey_date": "2026-06-01",
        "surveyor": "Fixture Surveyor",
        "surveyor_license": "TX-00000",
        "fixture_only": True,
    }
    meta["coordinate_system"] = {"epsg": "EPSG:2276", "units": "ft", "horizontal_datum": "NAD83", "source": "deterministic_fixture"}
    meta["existing_conditions_import_validation"] = {
        "production_usable": False,
        "blockers": [_review_blocker("existing_conditions", "fixture_control_not_external_project_control", "Fixture survey control is deterministic test evidence, not externally verified project control.")],
    }
    meta["survey_control_package"] = {
        "version": "survey_control_package_v1",
        "production_usable": False,
        "status": "fixture_control_review_required",
        "control_verified": True,
        "construction_release_allowed": False,
        "blockers": [_review_blocker("survey_control", "external_project_control_required", "Fixture control must be replaced or accepted by the licensed engineer for a real project.")],
    }


def _add_roadway_depth(meta: Dict[str, Any]) -> None:
    meta["alignments"] = [
        {
            "id": "ROAD-A1",
            "alignment_id": "ROAD-A1",
            "type": "roadway_corridor",
            "points": [[0.0, 100.0], [450.0, 105.0], [900.0, 100.0]],
            "length_ft": 900.0,
        }
    ]
    meta["profiles"] = [
        {
            "id": "PROF-A1",
            "alignment_id": "ROAD-A1",
            "profile_points": [{"station": 0.0, "elevation_ft": 612.0}, {"station": 900.0, "elevation_ft": 606.5}],
        }
    ]
    meta["cross_sections"] = [
        {
            "id": "XS-10",
            "alignment_id": "ROAD-A1",
            "station": 100.0,
            "existing_surface_id": "EG-REVIEW-1",
            "proposed_surface_id": "FG-REVIEW-1",
            "section_points": [{"offset_ft": -30, "elevation_ft": 611}, {"offset_ft": 0, "elevation_ft": 612}, {"offset_ft": 30, "elevation_ft": 611}],
        }
    ]
    meta["intersections"] = [{"id": "INT-1", "alignment_ids": ["ROAD-A1"], "valid": True}]
    meta["curb_returns"] = [{"id": "CR-1", "radius_ft": 25.0, "valid": True}]
    meta["pedestrian_paths"] = [{"id": "SW-1", "points": [[0.0, 120.0], [900.0, 120.0]], "width_ft": 5.0, "valid": True}]
    meta["grading"]["road_crown_controls"] = [{"road_id": "ROAD-A1", "expected_cross_slope": 0.02, "actual_cross_slope": 0.02, "valid": True}]
    meta["grading"]["curb_gutter_controls"] = [{"road_id": "ROAD-A1", "gutter_slope": 0.01, "valid": True}]
    meta["grading"]["ada_path_checks"] = [{"path_id": "SW-1", "max_running_slope": 0.04, "max_cross_slope": 0.015, "valid": True}]
    meta["grading"]["pad_tie_ins"] = [{"pad_id": "PAD-1", "proposed_surface_id": "FG-REVIEW-1", "valid": True}]
    meta["profile_bands"] = [
        {"system": "storm_pipe", "alignment_id": "ROAD-A1", "valid": True},
        {"system": "sanitary", "alignment_id": "ROAD-A1", "valid": True},
        {"system": "water", "alignment_id": "ROAD-A1", "valid": True},
    ]


def _scenario_plan(scenario_id: str) -> Dict[str, Any]:
    names = {
        "survey_backed_commercial_pad": "Survey-Backed Commercial Pad",
        "dem_backed_drainage_detention_site": "DEM-Backed Drainage/Detention Site",
        "utility_heavy_site": "Utility-Heavy Site",
        "roadway_corridor": "Roadway Corridor",
        "incomplete_bad_input_case": "Incomplete/Bad Input Case",
    }
    plan = _base_project_plan(scenario_id, names[scenario_id])
    meta = plan["meta"]
    meta["real_project_scenario_id"] = scenario_id
    meta["input_fixtures"] = _scenario_fixture_inputs(scenario_id)
    meta["construction_release_allowed"] = False
    meta["construction_release_blocked"] = True
    meta["construction_release_required"] = True
    meta["construction_release_blockers"] = [LICENSED_ENGINEER_REVIEW_BLOCKER, HEAVY_EXPORT_BLOCKER]

    if scenario_id == "survey_backed_commercial_pad":
        _attach_survey_control_fixture(meta)
        meta["systems_completed_override"] = ["layout", "grading", "drainage", "storm_pipes", "sanitary", "utility_network", "coordination_resolution", "qa"]
        meta["systems_blocked_override"] = ["standards_acceptance", "heavy_cad_export", "external_engineer_release"]
    elif scenario_id == "dem_backed_drainage_detention_site":
        meta["survey_control_package"] = {
            "version": "survey_control_package_v1",
            "production_usable": False,
            "status": "dem_fixture_no_survey_control",
            "blockers": [_review_blocker("survey_control", "survey_control_missing", "DEM fixture is not a sealed survey/control source.")],
        }
        meta["grading"]["existing_surface"]["source_quality"] = "dem_fixture"
        meta["systems_completed_override"] = ["grading", "drainage", "storm_pipes", "hydrology", "earthwork"]
        meta["systems_blocked_override"] = ["survey_control", "standards_acceptance", "heavy_cad_export", "external_engineer_release"]
    elif scenario_id == "utility_heavy_site":
        _attach_survey_control_fixture(meta)
        meta["coordination"] = {
            "success": True,
            "detected_conflicts": 3,
            "resolved_conflicts": [{"id": "UC-1", "method": "reroute"}],
            "unresolved_conflicts": [{"id": "UC-2", "severity": "review_required"}],
            "resolution_history": [{"id": "UC-1", "post_validation": "passed"}, {"id": "UC-2", "post_validation": "blocked"}],
        }
        meta["systems_completed_override"] = ["storm_pipes", "sanitary", "utility_network", "coordination_resolution"]
        meta["systems_blocked_override"] = ["unresolved_utility_conflict_review", "standards_acceptance", "heavy_cad_export", "external_engineer_release"]
    elif scenario_id == "roadway_corridor":
        _attach_survey_control_fixture(meta)
        _add_roadway_depth(meta)
        meta["deliverables"]["requested"].extend(["road_profile", "cross_sections"])
        meta["deliverables"]["produced"].extend(["road_profile", "cross_sections"])
        meta["systems_completed_override"] = ["roadway_corridor", "profile_section", "grading", "utility_coordination"]
        meta["systems_blocked_override"] = ["standards_acceptance", "civil3d_corridor_export", "external_engineer_release"]
    elif scenario_id == "incomplete_bad_input_case":
        meta["site_locked"] = False
        meta["site_boundary"] = {}
        meta["survey_control_package"] = {
            "version": "survey_control_package_v1",
            "production_usable": False,
            "status": "missing_required_input",
            "blockers": [_review_blocker("survey_control", "missing_control", "No survey/control fixture or accepted control source was provided.")],
        }
        meta["truth_audit"] = {"success": False, "failures": ["missing_site_boundary", "missing_control", "missing_standards"]}
        meta["manual_validation"] = {"success": False, "failures": ["missing_site_boundary", "missing_control", "missing_standards"]}
        meta["systems_completed_override"] = []
        meta["systems_blocked_override"] = ["site_boundary", "survey_control", "standards_acceptance", "engine_depth", "exports", "engineer_review_package", "construction_document_support_package"]

    meta["production_evidence"] = build_production_evidence(plan)
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    meta["export_package_report_v1"] = build_export_package_report_v1(plan, export_type="report")
    meta["engineer_review_package_v1"] = build_engineer_review_package(plan)
    meta["construction_document_support_package_v1"] = build_construction_document_support_package(plan)
    return plan


def _status_from_package(package: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = package.get(key)
        if value not in (None, ""):
            return str(value)
    return "present"


def _scenario_report(scenario_id: str) -> Dict[str, Any]:
    plan = _scenario_plan(scenario_id)
    meta = plan["meta"]
    engine_readiness = deepcopy(meta["engine_readiness"])
    export_report = deepcopy(meta["export_package_report_v1"])
    review_package = deepcopy(meta["engineer_review_package_v1"])
    support_package = deepcopy(meta["construction_document_support_package_v1"])
    blockers = [
        _review_blocker("professional_responsibility", LICENSED_ENGINEER_REVIEW_BLOCKER, "Only the licensed engineer/user can review, approve, stamp, seal, sign, submit, and take legal responsibility."),
        _review_blocker("deliverables", HEAVY_EXPORT_BLOCKER, "Heavy CAD/DXF export is intentionally skipped in this deterministic scenario suite."),
    ]
    blockers.extend(deepcopy(meta.get("survey_control_package", {}).get("blockers") or []))
    blockers.extend(deepcopy(meta.get("standards_package", {}).get("blockers") or []))
    blockers.extend(
        _review_blocker("scenario_system", str(field), f"Scenario system remains blocked: {field}.")
        for field in deepcopy(meta.get("systems_blocked_override") or [])
    )
    ready_for_review = scenario_id != "incomplete_bad_input_case"
    return {
        "scenario_id": scenario_id,
        "name": plan["project_name"],
        "inputs_used": deepcopy(meta["input_fixtures"]),
        "survey_control_status": _status_from_package(deepcopy(meta.get("survey_control_package") or {}), "status"),
        "standards_status": _status_from_package(deepcopy(meta.get("standards_package") or {}), "status"),
        "systems_completed": deepcopy(meta.get("systems_completed_override") or []),
        "systems_blocked": deepcopy(meta.get("systems_blocked_override") or []),
        "engine_depth_summary": {
            "contract_version": engine_readiness["contract_version"],
            "review_state": engine_readiness["review_state"],
            "production_ready_count": engine_readiness["production_ready_count"],
            "production_blocked_engine_ids": deepcopy(engine_readiness["production_blocked_engine_ids"]),
            "blocked_engine_ids": deepcopy(engine_readiness["blocked_engine_ids"]),
            "not_evidenced_engine_ids": deepcopy(engine_readiness["not_evidenced_engine_ids"][:8]),
        },
        "production_evidence_v1": deepcopy(meta["production_evidence"]),
        "production_evidence_status": "ready" if meta["production_evidence"].get("production_evidence_ready") is True else "blocked",
        "export_package_status": _status_from_package(export_report, "status", "export_status"),
        "engineer_review_package_status": _status_from_package(review_package, "review_status", "status"),
        "construction_document_support_package_status": support_package["package_status"],
        "blockers": blockers,
        "ready_for_engineer_review": ready_for_review,
        "construction_release_allowed": False,
        "plan": plan,
        "export_package_report_v1": export_report,
        "engineer_review_package_v1": review_package,
        "construction_document_support_package_v1": support_package,
        "truth_label": RESPONSIBILITY_LABEL,
    }


def run_real_project_scenario_suite() -> Dict[str, Any]:
    scenario_ids = [
        "survey_backed_commercial_pad",
        "dem_backed_drainage_detention_site",
        "utility_heavy_site",
        "roadway_corridor",
        "incomplete_bad_input_case",
    ]
    scenarios = [_scenario_report(scenario_id) for scenario_id in scenario_ids]
    return {
        "version": REAL_PROJECT_SUITE_VERSION,
        "runner_version": RUNNER_VERSION,
        "status": "completed_with_blockers",
        "scenario_count": len(scenarios),
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "scenarios": scenarios,
        "scenario_matrix": [
            {
                "scenario_id": row["scenario_id"],
                "survey_control_status": row["survey_control_status"],
                "standards_status": row["standards_status"],
                "systems_completed": row["systems_completed"],
                "systems_blocked": row["systems_blocked"],
                "export_package_status": row["export_package_status"],
                "engineer_review_package_status": row["engineer_review_package_status"],
                "construction_document_support_package_status": row["construction_document_support_package_status"],
                "ready_for_engineer_review": row["ready_for_engineer_review"],
                "construction_release_allowed": False,
            }
            for row in scenarios
        ],
        "truth_label": RESPONSIBILITY_LABEL,
    }


__all__ = [
    "HEAVY_EXPORT_BLOCKER",
    "LICENSED_ENGINEER_REVIEW_BLOCKER",
    "REAL_PROJECT_SUITE_VERSION",
    "RUNNER_VERSION",
    "build_normal_alpha_scenario_plan",
    "run_real_project_scenario_suite",
    "run_normal_alpha_scenario",
]
