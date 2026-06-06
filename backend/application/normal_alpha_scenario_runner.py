from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any, Dict

from backend.planning.engine_depth_audit import run_engine_depth_audit_for_scenario
from backend.planning.engine_readiness import evaluate_engine_readiness
from backend.planning.engineer_review_package import build_engineer_review_package
from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.production_depth import enrich_storm_production_depth
from backend.planning.production_evidence import build_production_evidence
from core.civil_design import civil_design_readiness


RUNNER_VERSION = "normal_alpha_scenario_runner_v1"
HEAVY_EXPORT_BLOCKER = "heavy_cad_dxf_export_skipped_review_only"


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
        "ready_language": "ready_for_engineer_review",
        "construction_release_allowed": False,
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
            "segments": [{"id": "SAN-1", "from": "MH-1", "to": "MH-2", "length_ft": 260.0, "slope_ft_ft": 0.01}],
            "manholes": [{"name": "MH-1", "x": 120.0, "y": 80.0}, {"name": "MH-2", "x": 540.0, "y": 80.0}],
        },
        "utilities": {
            "success": True,
            "source": "utility_engine_review_fixture",
            "segments": [{"id": "WAT-1", "type": "water", "length_ft": 410.0}],
            "conflict_hooks": {"utility_segments": [{"id": "WAT-1"}]},
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
                    "utility_length_ft": {"source_object_ids": ["WAT-1", "SAN-1"]},
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
            {"task": "polyline", "layer": "SAN", "canonical_source_type": "sanitary_segment", "canonical_source_id": "SAN-1", "points": [[120, 80], [540, 80]]},
            {"task": "polyline", "layer": "WATER", "canonical_source_type": "water_segment", "canonical_source_id": "WAT-1", "points": [[90, 110], [660, 110]]},
        ],
        "meta": meta,
    }
    meta["production_evidence"] = build_production_evidence(plan)
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    meta["export_package_report_v1"] = build_export_package_report_v1(plan, export_type="report")
    meta["engineer_review_package_v1"] = build_engineer_review_package(plan)
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
        "engine_depth_audit_report_v1": audit,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "remaining_engine_depth_blockers": deepcopy(audit.get("failed_check_ids") or []),
        "truth_label": "Normal alpha scenario runner exercises review package contracts only; Civora does not stamp, seal, sign, certify, approve, submit, or act as engineer of record.",
    }


__all__ = [
    "HEAVY_EXPORT_BLOCKER",
    "RUNNER_VERSION",
    "build_normal_alpha_scenario_plan",
    "run_normal_alpha_scenario",
]
