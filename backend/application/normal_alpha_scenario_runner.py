from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any, Dict

from backend.planning.construction_package import build_construction_document_support_package
from backend.planning.engine_depth_audit import run_engine_depth_audit_for_scenario
from backend.planning.engine_readiness import evaluate_engine_readiness
from backend.planning.engineer_review_package import build_engineer_review_package
from backend.planning.export_package_report import build_export_package_report_v1
from backend.planning.production_depth import enrich_storm_production_depth, enrich_water_production_depth
from backend.planning.production_evidence import build_production_evidence
from core.civil_design import civil_design_readiness
from engines.cost_engine import build_cost_package_status, compute_cost_estimate


RUNNER_VERSION = "normal_alpha_scenario_runner_v1"
REAL_PROJECT_SUITE_VERSION = "real_project_scenario_suite_v1"
HEAVY_EXPORT_BLOCKER = "heavy_cad_dxf_export_skipped_review_only"
LICENSED_ENGINEER_REVIEW_BLOCKER = "external_licensed_engineer_review_required"
STANDARDS_DEPENDENCY_BLOCKER = "adopted_jurisdictional_standards_required"
SURVEY_CONTROL_DEPENDENCY_BLOCKER = "accepted_project_survey_control_required"

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


def _depth_proof(
    *,
    discipline: str,
    production_depth: list[str],
    review_depth: list[str],
    blockers: list[str],
) -> Dict[str, Any]:
    return {
        "discipline": discipline,
        "production_depth_proves": production_depth,
        "review_depth_limits": review_depth,
        "exact_blockers": blockers,
        "construction_release_allowed": False,
        "engineer_review_required": True,
        "source_confidence": "deterministic_fixture_not_external_acceptance",
        "native_blockers_exposed": True,
        "standards_dependency": STANDARDS_DEPENDENCY_BLOCKER,
        "survey_control_dependency": SURVEY_CONTROL_DEPENDENCY_BLOCKER,
        "truth_label": "Fixture proof demonstrates deterministic engine depth only; every output remains review-required.",
    }


def _apply_grading_depth_fixture(meta: Dict[str, Any]) -> None:
    grading = meta["grading"]
    grading.update(
        {
            "proposed_surface_source": "tin_surface_engine",
            "proposed_surface_confidence": "calculated_from_accepted_surfaces",
            "contour_interval_ft": 2.0,
            "existing_surface": {
                "id": "EG-REVIEW-1",
                "source_quality": "tin_terrain_fixture",
                "tin": {
                    "surface_id": "EG-REVIEW-1",
                    "triangle_count": 8,
                    "breaklines": ["BL-NORTH", "BL-SWALE"],
                    "source": "deterministic_tin_fixture",
                },
            },
            "proposed_surface": {
                "id": "FG-REVIEW-1",
                "source": "tin_surface_engine",
                "confidence": "calculated_from_accepted_surfaces",
                "tin": {"surface_id": "FG-REVIEW-1", "triangle_count": 10, "source": "grading_tin_fixture"},
            },
            "earthwork": {
                "expected_cut_cf": 1850.0,
                "actual_cut_cf": 1850.0,
                "expected_fill_cf": 2140.0,
                "actual_fill_cf": 2140.0,
                "expected_net_cf": 290.0,
                "actual_net_cf": 290.0,
                "volume_tolerance_cf": 0.5,
                "source_surface_ids": ["EG-REVIEW-1", "FG-REVIEW-1"],
                "source": "earthwork_grid_engine",
            },
            "slope_summary": {
                "expected_min_slope": 0.01,
                "actual_min_slope": 0.012,
                "expected_max_slope": 0.05,
                "actual_max_slope": 0.048,
                "expected_average_slope": 0.024,
                "actual_average_slope": 0.024,
                "source": "tin_slope_analysis",
            },
            "pad_tie_ins": [
                {
                    "building_id": "BLDG-1",
                    "proposed_surface_id": "FG-REVIEW-1",
                    "pad_elev_ft": 101.2,
                    "positive_drainage": True,
                    "expected_max_tie_slope": 0.05,
                    "actual_tie_slope": 0.034,
                    "tie_in_elevations_ft": [101.2, 100.9, 100.6, 100.4],
                    "valid": True,
                    "source": "pad_tie_engine",
                }
            ],
            "contours": [
                {
                    "contour_id": "FG-100",
                    "interval_ft": 2.0,
                    "proposed_surface_id": "FG-REVIEW-1",
                    "contour_count": 3,
                    "actual_contour_count": 3,
                    "expected_min_contour_count": 2,
                    "sample_elevations_ft": [98.0, 100.0, 102.0],
                    "source": "tin_contour_engine",
                }
            ],
            "drainage_aware_repairs": [
                {
                    "repair_id": "GR-REPAIR-1",
                    "valid": True,
                    "reason": "restored_positive_drainage_to_basin_outfall",
                    "drainage_evidence_id": "BASIN-1",
                    "before": {"low_point_count": 2, "min_slope": 0.004},
                    "after": {"low_point_count": 1, "min_slope": 0.012},
                    "source": "grading_repair_engine",
                }
            ],
            "slope_issues": [
                {
                    "id": "SLOPE-1",
                    "issue": "localized_4.8_percent_tie_slope_near_pad",
                    "status": "resolved_for_review",
                    "engineer_review_required": True,
                }
            ],
            "retaining_walls": [
                {
                    "wall_id": "RW-1",
                    "trigger": "pad_tie_in_exceeds_preferred_free_slope_without_wall",
                    "height_ft": 3.2,
                    "status": "triggered_review_required",
                }
            ],
            "wall_tie_in_checks": [
                {
                    "wall_id": "RW-1",
                    "proposed_surface_id": "FG-REVIEW-1",
                    "top_tie_elev_ft": 101.2,
                    "bottom_tie_elev_ft": 98.0,
                    "valid": True,
                    "source": "retaining_wall_tie_engine",
                }
            ],
        }
    )
    meta["earthwork"] = grading["earthwork"]


def _apply_water_fire_flow_fixture(meta: Dict[str, Any]) -> None:
    water = {
        "success": True,
        "source": "water_fire_flow_fixture",
        "standard_accepted": True,
        "standard_id": "fixture-water-criteria",
        "source_pressure_psi": 72.0,
        "min_residual_pressure_psi": 20.0,
        "max_hydrant_spacing_ft": 300.0,
        "fire_flow_demand_gpm": 1250.0,
        "available_fire_flow_gpm": 1800.0,
        "source_node": "SRC",
        "fire_flow_node": "H2",
        "water_segments": [
            {"name": "W-1", "start_node": "SRC", "end_node": "H1", "length_ft": 220.0, "diameter_in": 8.0, "flow_gpm": 350.0},
            {"name": "W-2", "start_node": "H1", "end_node": "H2", "length_ft": 240.0, "diameter_in": 8.0, "flow_gpm": 425.0},
            {"name": "W-3", "start_node": "H2", "end_node": "SRC", "length_ft": 260.0, "diameter_in": 8.0, "flow_gpm": 375.0},
        ],
        "hydrants": [
            {"id": "H1", "x": 120.0, "y": 110.0},
            {"id": "H2", "x": 340.0, "y": 120.0},
            {"id": "H3", "x": 560.0, "y": 130.0},
        ],
        "pressure_zones": [{"name": "Zone A", "source_node": "SRC", "source_pressure_psi": 72.0}],
    }
    enriched = enrich_water_production_depth(water)
    meta["water"] = enriched
    meta["utilities"]["water"] = enriched
    meta["utilities"]["segments"] = [
        {"id": row["name"], "type": "water", "length_ft": row["length_ft"]}
        for row in enriched["water_segments"]
    ]
    meta["utilities"].update(
        {
            "hydrants": enriched["hydrants"],
            "pressure_zones": enriched["pressure_zones"],
            "hydrant_spacing_validation": enriched["hydrant_spacing_validation"],
            "fire_flow_validation": enriched["fire_flow_validation"],
            "pressure_validation": enriched["pressure_validation"],
            "velocity_checks": enriched["velocity_checks"],
            "looped": enriched["looped"],
            "dead_end_validation": enriched["dead_end_validation"],
            "sizing_optimization": enriched["sizing_optimization"],
        }
    )


def _apply_review_only_cost_fixture(meta: Dict[str, Any]) -> None:
    meta["quantities"] = {
        "success": True,
        "totals": {
            "lot_area_sf": 612500.0,
            "estimated_parking_stalls": 180,
            "pipe_length_ft": 100.0,
            "road_area_sf": 18600.0,
            "utility_length_ft": 720.0,
            "sanitary_length_ft": 690.0,
            "sanitary_manhole_count": 5,
            "sanitary_service_count": 4,
        },
        "stale_or_reactive_status": {"upstream_blocked_systems": ["standards_acceptance", "external_engineer_release"]},
        "explain": {
            "meta_summary": {"quantity_traceability_complete": True},
            "quantity_audit": {
                "pipe_length_ft": {"source_object_ids": ["STM-ALPHA-1"]},
                "road_area_sf": {"source_object_ids": ["ALG-LOOP-1"]},
                "utility_length_ft": {"source_object_ids": ["W-1", "W-2", "W-3"]},
                "sanitary_length_ft": {"source_object_ids": ["SAN-MAIN-1", "SAN-MAIN-2", "SAN-MAIN-3", "SAN-MAIN-4"]},
                "sanitary_manhole_count": {"source_object_ids": ["SMH-A", "SMH-B", "SMH-C", "SMH-D", "SAN_TIE_IN"]},
                "sanitary_service_count": {"source_object_ids": ["SAN-LAT-1", "SAN-LAT-2", "SAN-LAT-3", "SAN-LAT-4"]},
                "estimated_parking_stalls": {"source_object_ids": ["PARK-1"]},
            },
            "trace_gaps": {},
        },
    }
    meta["cost_pricing"] = {
        "source_name": "chat_169_current_cost_book_fixture",
        "source_type": "company_bid_book",
        "location": "Austin, TX",
        "effective_date": "2026-06-01",
        "accepted_by": "Alpha Estimator",
        "approved_by": "Alpha Estimator",
        "approval_date": "2026-06-02",
        "contingency_pct": 8.0,
        "unit_prices": {
            "pipe_length_ft": {"item": "RCP storm pipe", "category": "storm", "unit": "ft", "unit_cost": 125.0, "source_item_id": "ST-125"},
            "road_area_sf": {"item": "Roadway pavement", "category": "pavement", "unit": "sf", "unit_cost": 9.25, "source_item_id": "PV-0925"},
            "utility_length_ft": {"item": "Water main", "category": "utilities", "unit": "ft", "unit_cost": 90.0, "source_item_id": "UT-090"},
            "sanitary_length_ft": {"item": "Sanitary sewer", "category": "sanitary", "unit": "ft", "unit_cost": 105.0, "source_item_id": "SAN-105"},
            "sanitary_manhole_count": {"item": "Sanitary manhole", "category": "sanitary", "unit": "ea", "unit_cost": 6500.0, "source_item_id": "SAN-MH"},
            "sanitary_service_count": {"item": "Sanitary lateral", "category": "sanitary", "unit": "ea", "unit_cost": 1900.0, "source_item_id": "SAN-LAT"},
            "estimated_parking_stalls": {"item": "Parking stall striping", "category": "pavement", "unit": "ea", "unit_cost": 80.0, "source_item_id": "PK-ST"},
        },
    }
    result = compute_cost_estimate({"meta": meta})
    meta["cost_estimate"] = {
        "success": result.success,
        "message": result.message,
        "totals": result.totals,
        "line_items": result.line_items,
        "category_subtotals": result.category_subtotals,
        "warnings": result.warnings,
        "assumptions": result.assumptions,
        "explain": result.explain,
    }
    meta["cost_package_status"] = build_cost_package_status({"meta": meta})


def _recompute_cost_package(meta: Dict[str, Any]) -> None:
    result = compute_cost_estimate({"meta": meta})
    meta["cost_estimate"] = {
        "success": result.success,
        "message": result.message,
        "totals": result.totals,
        "line_items": result.line_items,
        "category_subtotals": result.category_subtotals,
        "warnings": result.warnings,
        "assumptions": result.assumptions,
        "explain": result.explain,
    }
    meta["cost_package_status"] = build_cost_package_status({"meta": meta})


def _calculation_depth_proofs(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "grading": _depth_proof(
            discipline="grading",
            production_depth=[
                "TIN terrain fixture carries existing/proposed surface IDs.",
                "Cut/fill expected and actual volumes match accepted surface IDs.",
                "Pad tie-ins, slope repair, contours, and retaining-wall trigger are explicit.",
            ],
            review_depth=[
                "TIN fixture is deterministic test data, not accepted external survey/control.",
                "Retaining wall is a trigger and tie-in proof only; structural design remains outside Civora.",
            ],
            blockers=[STANDARDS_DEPENDENCY_BLOCKER, SURVEY_CONTROL_DEPENDENCY_BLOCKER, LICENSED_ENGINEER_REVIEW_BLOCKER],
        ),
        "storm": _depth_proof(
            discipline="storm",
            production_depth=[
                "Basin/outfall target, inlet spread/capacity, HGL/EGL rows, overflow path, and detention stage-storage routing are present.",
                "Tailwater/backwater evidence is surfaced in the storm hydraulic trace.",
            ],
            review_depth=[
                "Tailwater must be replaced by accepted receiving-system evidence for a real project.",
                "Drainage criteria and outfall approval are not externally accepted in this fixture.",
            ],
            blockers=["accepted_tailwater_or_receiving_system_required", STANDARDS_DEPENDENCY_BLOCKER, LICENSED_ENGINEER_REVIEW_BLOCKER],
        ),
        "sanitary": _depth_proof(
            discipline="sanitary",
            production_depth=[
                "Slope, cover, tie-in, capacity, manhole spacing, service coverage, and post-reroute recalculation are explicit.",
                "Capacity ratios and upstream service flows are traceable by segment.",
            ],
            review_depth=[
                "Downstream utility owner/tie-in acceptance is not attached.",
                "Sanitary design criteria remain fixture criteria until reviewed.",
            ],
            blockers=["utility_owner_tie_in_acceptance_required", STANDARDS_DEPENDENCY_BLOCKER, LICENSED_ENGINEER_REVIEW_BLOCKER],
        ),
        "water_fire_flow": _depth_proof(
            discipline="water_fire_flow",
            production_depth=[
                "Hydrant spacing, source pressure, residual pressure, fire-flow demand, pressure zones, velocities, looping, and dead-end checks are computed.",
                "Water segments include flow, diameter, length, and graph nodes.",
            ],
            review_depth=[
                "Fire authority criteria and source pressure must be accepted externally for a real project.",
                "Hydrant placement remains review-required.",
            ],
            blockers=["accepted_fire_authority_flow_test_required", STANDARDS_DEPENDENCY_BLOCKER, LICENSED_ENGINEER_REVIEW_BLOCKER],
        ),
        "roadway_corridor": _depth_proof(
            discipline="roadway_corridor",
            production_depth=[
                "Alignment, profile, cross section, crown/cross-slope, curb return, sidewalk/ADA, and max-grade controls are explicit.",
                "Roadway controls are tied back to accepted fixture surface IDs.",
            ],
            review_depth=[
                "Corridor export is intentionally skipped and jurisdiction roadway standards are not accepted.",
                "ADA and max-grade checks are deterministic review evidence only.",
            ],
            blockers=["civil3d_corridor_export_skipped", STANDARDS_DEPENDENCY_BLOCKER, LICENSED_ENGINEER_REVIEW_BLOCKER],
        ),
        "quantities_cost": _depth_proof(
            discipline="quantities_cost",
            production_depth=[
                "Quantities are traceable to canonical source IDs.",
                "Cost package exposes approved/current cost-book metadata, coverage, hash, and upstream blocked-system gates.",
            ],
            review_depth=[
                "Upstream standards and external release blockers keep cost output review-only.",
                "Bid or construction cost certification is not claimed.",
            ],
            blockers=["upstream_blocked_systems", "approved_current_cost_book_required", LICENSED_ENGINEER_REVIEW_BLOCKER],
        ),
    }


def _base_meta() -> Dict[str, Any]:
    lot = {"x": 0.0, "y": 0.0, "w": 875.0, "h": 700.0, "area_sf": 612500.0}
    storm, drainage = _storm_fixture()
    meta = {
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
    _apply_grading_depth_fixture(meta)
    _apply_water_fire_flow_fixture(meta)
    _apply_review_only_cost_fixture(meta)
    meta["civil_calculation_fixture_proofs"] = _calculation_depth_proofs(meta)
    return meta


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
        "quantities_cost_blocked_site": [
            {"type": "quantity_takeoff_rows", "path": "deterministic_inline_quantity_fixture", "fixture": True},
            {"type": "unit_price_book", "path": "deterministic_inline_current_and_stale_cost_book_fixture", "fixture": True},
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
            "max_grade": 0.0062,
            "max_allowed_grade": 0.08,
        }
    ]
    meta["profiles"] = [
        {
            "id": "PROF-A1",
            "alignment_id": "ROAD-A1",
            "profile_points": [{"station_ft": 0.0, "elevation_ft": 612.0}, {"station_ft": 900.0, "elevation_ft": 606.5}],
            "max_grade": 0.0062,
            "max_allowed_grade": 0.08,
        }
    ]
    meta["cross_sections"] = [
        {
            "id": "XS-10",
            "alignment_id": "ROAD-A1",
            "station_ft": 100.0,
            "existing_surface_id": "EG-REVIEW-1",
            "proposed_surface_id": "FG-REVIEW-1",
            "section_points": [{"offset_ft": -30, "elevation_ft": 611}, {"offset_ft": 0, "elevation_ft": 612}, {"offset_ft": 30, "elevation_ft": 611}],
        }
    ]
    meta["intersections"] = [{"id": "INT-1", "connected_alignments": ["ROAD-A1", "ACCESS-1"], "x": 450.0, "y": 105.0, "angle_deg": 90.0, "valid": True}]
    meta["curb_returns"] = [{"id": "CR-1", "intersection_id": "INT-1", "radius_ft": 25.0, "arc_points": [[440.0, 95.0], [450.0, 105.0], [460.0, 95.0]], "valid": True}]
    meta["pedestrian_paths"] = [{"id": "SW-1", "points": [[0.0, 120.0], [900.0, 120.0]], "width_ft": 5.0, "continuous": True, "valid": True}]
    meta["grading"]["road_crown_controls"] = [{
        "road_id": "ROAD-A1",
        "profile_id": "PROF-A1",
        "expected_crown_elev_ft": 611.8,
        "actual_crown_elev_ft": 611.8,
        "expected_cross_slope": 0.02,
        "actual_cross_slope": 0.02,
        "expected_left_cross_slope": -0.02,
        "actual_left_cross_slope": -0.02,
        "expected_right_cross_slope": 0.02,
        "actual_right_cross_slope": 0.02,
        "crown_tolerance_ft": 0.01,
        "cross_slope_tolerance": 0.001,
        "standard_id": "fixture-roadway-criteria",
        "standard_accepted": True,
        "source": "roadway_crown_engine",
        "valid": True,
    }]
    meta["grading"]["curb_gutter_controls"] = [{
        "road_id": "ROAD-A1",
        "alignment_id": "ROAD-A1",
        "expected_min_gutter_slope": 0.005,
        "actual_gutter_slope": 0.01,
        "standard_id": "fixture-roadway-criteria",
        "standard_accepted": True,
        "source": "curb_gutter_engine",
        "valid": True,
    }]
    meta["grading"]["ada_path_checks"] = [{
        "path_id": "SW-1",
        "expected_max_running_slope": 0.05,
        "actual_running_slope": 0.035,
        "expected_max_cross_slope": 0.02,
        "actual_cross_slope": 0.015,
        "continuity_validation": {"valid": True},
        "standard_id": "fixture-ada-criteria",
        "standard_accepted": True,
        "source": "ada_path_engine",
        "valid": True,
    }]
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
        "quantities_cost_blocked_site": "Quantities/Cost Blocked Site",
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
    elif scenario_id == "quantities_cost_blocked_site":
        _attach_survey_control_fixture(meta)
        meta["cost_pricing"]["effective_date"] = "2024-01-01"
        meta["cost_pricing"]["approval_date"] = "2024-01-02"
        _recompute_cost_package(meta)
        meta["systems_completed_override"] = ["quantities", "cost_traceability", "cost_book_coverage"]
        meta["systems_blocked_override"] = [
            "upstream_blocked_systems",
            "stale_cost_book_refresh_required",
            "standards_acceptance",
            "external_engineer_release",
        ]
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
    blockers.extend(deepcopy(meta.get("cost_package_status", {}).get("blockers") or []))
    blockers.extend(
        _review_blocker("scenario_system", str(field), f"Scenario system remains blocked: {field}.")
        for field in deepcopy(meta.get("systems_blocked_override") or [])
    )
    ready_for_review = scenario_id != "incomplete_bad_input_case"
    calculation_proofs = deepcopy(meta.get("civil_calculation_fixture_proofs") or {})
    exact_blockers = sorted(
        {
            str(item.get("field") or item.get("area"))
            for item in blockers
            if isinstance(item, dict) and (item.get("field") or item.get("area"))
        }
    )
    return {
        "scenario_id": scenario_id,
        "name": plan["project_name"],
        "inputs_used": deepcopy(meta["input_fixtures"]),
        "assumptions": [
            "Deterministic fixture geometry and calculations are used for regression proof.",
            "No external jurisdiction acceptance, utility-owner approval, or licensed-engineer release is attached.",
        ],
        "source_confidence": "deterministic_fixture_not_external_acceptance",
        "native_blockers": exact_blockers,
        "exact_blockers": exact_blockers,
        "standards_dependency": STANDARDS_DEPENDENCY_BLOCKER,
        "survey_control_dependency": SURVEY_CONTROL_DEPENDENCY_BLOCKER,
        "engineer_review_required": True,
        "calculation_fixture_proofs": calculation_proofs,
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
        "quantities_cost_blocked_site",
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
                "proof_disciplines": sorted(row["calculation_fixture_proofs"].keys()),
                "exact_blockers": row["exact_blockers"],
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
