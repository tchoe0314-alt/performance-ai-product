from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from backend.planning.engine_depth_audit import (
    CLASS_CONCEPT,
    CLASS_PRODUCTION_DEPTH,
    CLASS_REVIEW,
    REPORT_VERSION,
    run_engine_depth_audit,
    run_engine_depth_audit_for_scenario,
    run_engine_depth_audit_scenario,
)
from backend.planning.engine_readiness import evaluate_engine_readiness
from backend.planning.engine_contracts import engine_contracts
from backend.planning.depth_validators import validate_roadway_corridor_depth
from backend.planning.golden_runner import run_golden_scenario
from backend.planning.production_depth import enrich_storm_production_depth
from core.civil_design import civil_design_readiness
from tests.test_civil_design_readiness import _complete_meta
from tests.test_depth_validators import _complete_grading_depth_meta


def _review_depth_meta() -> dict:
    meta = _complete_meta()
    meta["lot"] = {"w": 220.0, "h": 160.0, "area_sf": 35200.0}
    meta["building_count"] = 1
    meta["parking_program"] = {"stall_count": 36}
    meta["truth_audit"] = {"success": True}
    meta["manual_validation"] = {"success": True, "failures": []}
    meta["quantities"] = {
        "success": True,
        "totals": {"lot_area_sf": 35200.0, "pipe_length_ft": 80.0, "estimated_parking_stalls": 36},
        "explain": {
            "meta_summary": {"quantity_traceability_complete": True},
            "quantity_audit": {"pipe_length_ft": {"source_object_ids": ["storm-1"]}},
            "trace_gaps": {},
        },
    }
    meta["cost_estimate"] = {
        "success": False,
        "totals": {},
        "explain": {"pricing": {"production_usable": False}, "trace_gaps": {}, "pricing_coverage_gaps": {}},
    }
    meta["export_audit"] = {
        "ready": True,
        "production_export_ready": False,
        "export_blocked": False,
        "canonical_id_traceability": {"ready": True},
    }
    meta["construction_readiness"] = {
        "ready": False,
        "status": "not_construction_ready",
        "blockers": [{"area": "existing_conditions", "field": "survey_surface"}],
    }
    meta["construction_package_manifest"] = {
        "release_allowed": False,
        "construction_ready": False,
        "blockers": [{"area": "existing_conditions", "field": "survey_surface"}],
    }
    return meta


def _review_depth_plan(payload: dict) -> dict:
    meta = _review_depth_meta()
    meta["lot"] = payload.get("lot") or meta["lot"]
    plan = {
        "project_name": payload.get("project_name"),
        "actions": [
            {
                "task": "rectangle",
                "layer": "SITE",
                "canonical_source_type": "site",
                "canonical_source_id": "site-1",
                "width": 220.0,
                "height": 160.0,
            }
        ],
        "meta": meta,
    }
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    return plan


def _complete_storm_hgl_fixture() -> tuple:
    slope = 0.01
    mannings_n = 0.013
    design_flow = 1.0
    storm = {
        "success": True,
        "source": "storm_network_engine",
        "segments": [
            {
                "id": "STM-HGL-1",
                "pipe": "STM-HGL-1",
                "from": "CB-HGL-1",
                "to": "OUT-HGL-1",
                "path": [[0.0, 0.0], [100.0, 0.0]],
                "length_ft": 100.0,
                "diameter_in": 24.0,
                "flow_cfs": design_flow,
                "slope_ft_ft": slope,
                "mannings_n": mannings_n,
                "start_invert_ft": 100.0,
                "end_invert_ft": 99.0,
                "tributary_area_sf": 12000.0,
            }
        ],
        "target_outfall": {"name": "OUT-HGL-1", "target_name": "OUT-HGL-1", "x": 100.0, "y": 0.0, "z": 98.5},
        "graph_validation": {"valid": True},
        "hydraulic_validation": {"valid": True},
        "missing_data_segments": [],
    }
    drainage = {
        "success": True,
        "source": "drainage_engine",
        "coordination": {"preferred_outfall": {"name": "OUT-HGL-1", "target_name": "OUT-HGL-1", "x": 100.0, "y": 0.0, "z": 98.5}},
        "surface_controls": {"primary_low_point": {"x": 100.0, "y": 0.0, "z": 98.5}},
        "surface_guidance": {"surface_source": "terrain", "surface_from_grading": True},
        "catchments": [{"name": "C-HGL-1", "runoff_c": 0.8, "runoff_coefficient": 0.8}],
        "stats": {
            "total_basin_runoff_cfs": design_flow,
            "total_estimated_inlet_flow_cfs": design_flow,
            "total_contributing_area_sf": 12000.0,
        },
        "structures": [{"name": "CB-HGL-1", "x": 0.0, "y": 0.0, "estimated_flow_cfs": design_flow, "capacity_cfs": 20.0, "gutter_spread_limit_ft": 9.0}],
        "basins": [{"name": "B-HGL-1", "target_name": "OUT-HGL-1"}],
        "low_points": [{"name": "LP-HGL-1", "x": 100.0, "y": 0.0, "z": 98.5}],
        "flow_paths": [{"from": "CB-HGL-1", "to": "OUT-HGL-1", "points": [[0.0, 0.0], [100.0, 0.0]]}],
        "detention_routing": [
            {
                "basin": "B-HGL-1",
                "routing_source": "hydrograph_engine",
                "routing_method": "stage_storage_hydrograph",
                "required_storage_cf": 4200.0,
                "provided_storage_cf": 5000.0,
                "release_cfs": 1.0,
                "outlet": {"type": "orifice", "release_cfs": 1.0, "source": "approved_outlet_fixture"},
                "drawdown_hours": 18.0,
                "stage_storage": [
                    {"elevation_ft": 96.0, "storage_cf": 0.0},
                    {"elevation_ft": 98.0, "storage_cf": 2500.0},
                    {"elevation_ft": 99.0, "storage_cf": 5000.0},
                ],
            }
        ],
        "overflow_paths": [
            {"name": "OF-HGL-1", "capacity_valid": True, "capacity_cfs": 5.0, "required_capacity_cfs": 4.0, "source": "approved_spillway_fixture"}
        ],
        "overflow_analysis": {"valid": True, "production_valid": True},
    }
    return storm, drainage


def _complete_sanitary_depth_fixture() -> dict:
    return {
        "success": True,
        "source": "sanitary_depth_fixture",
        "route_count": 4,
        "service_count": 2,
        "manhole_count": 3,
        "expected_service_buildings": ["BLDG-1", "BLDG-2"],
        "served_buildings": ["BLDG-1", "BLDG-2"],
        "tie_in_node": "SAN_TIE_IN",
        "segments": [
            {
                "name": "LAT-1",
                "segment_role": "lateral",
                "served_building": "BLDG-1",
                "start_name": "BLDG-1",
                "end_name": "NODE-A",
                "route_points": [[0.0, 0.0], [40.0, 0.0]],
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
                "name": "LAT-2",
                "segment_role": "lateral",
                "served_building": "BLDG-2",
                "start_name": "BLDG-2",
                "end_name": "NODE-B",
                "route_points": [[0.0, 30.0], [80.0, 0.0]],
                "diameter_in": 8.0,
                "flow_cfs": 0.03,
                "capacity_cfs": 1.8,
                "capacity_ratio": 0.017,
                "slope_ft_ft": 0.015,
                "cover_start_ft": 4.0,
                "cover_end_ft": 5.2,
                "post_reroute_recalculated": True,
                "upstream_service_flow_cfs": 0.03,
            },
            {
                "name": "SAN-MAIN-1",
                "segment_role": "main",
                "start_name": "NODE-A",
                "end_name": "NODE-B",
                "route_points": [[40.0, 0.0], [80.0, 0.0]],
                "diameter_in": 8.0,
                "flow_cfs": 0.02,
                "capacity_cfs": 1.2,
                "capacity_ratio": 0.017,
                "slope_ft_ft": 0.015,
                "cover_start_ft": 5.4,
                "cover_end_ft": 6.0,
                "post_reroute_recalculated": True,
                "upstream_service_flow_cfs": 0.02,
                "flow_topology": {"from_node": "NODE-A", "to_node": "NODE-B", "incoming_service_flow_cfs": 0.02},
            },
            {
                "name": "SAN-MAIN-2",
                "segment_role": "main",
                "start_name": "NODE-B",
                "end_name": "SAN_TIE_IN",
                "route_points": [[80.0, 0.0], [160.0, 0.0]],
                "diameter_in": 8.0,
                "flow_cfs": 0.05,
                "capacity_cfs": 1.2,
                "capacity_ratio": 0.042,
                "slope_ft_ft": 0.015,
                "cover_start_ft": 6.2,
                "cover_end_ft": 7.4,
                "post_reroute_recalculated": True,
                "upstream_service_flow_cfs": 0.05,
                "flow_topology": {"from_node": "NODE-B", "to_node": "SAN_TIE_IN", "incoming_service_flow_cfs": 0.05},
                "tie_in_validated": True,
            },
        ],
        "manholes": [
            {"name": "SMH-A", "node_id": "SMH-A", "x": 40.0, "y": 0.0},
            {"name": "SMH-B", "node_id": "SMH-B", "x": 80.0, "y": 0.0},
            {"name": "SAN_TIE_IN", "node_id": "SAN_TIE_IN", "x": 160.0, "y": 0.0},
        ],
        "service_coverage": {
            "expected_buildings": ["BLDG-1", "BLDG-2"],
            "served_buildings": ["BLDG-1", "BLDG-2"],
            "missing_buildings": [],
            "valid": True,
        },
        "post_reroute_recalculation": {
            "service_flow_total_cfs": 0.05,
            "main_segments_recomputed": 2,
            "service_segments_recomputed": 2,
            "node_inflow_cfs": {"NODE-A": 0.02, "NODE-B": 0.05, "SAN_TIE_IN": 0.05},
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
            "capacity_validation": {"valid": True, "invalid_capacity_segments": [], "max_capacity_ratio": 0.042},
            "post_reroute_recalculation_evidence": {"all_segments_recalculated": True},
        },
        "graph_validation": {"valid": True},
    }


def _sanitary_depth_plan(payload: dict) -> dict:
    plan = _review_depth_plan(payload)
    meta = plan["meta"]
    meta["sanitary"] = _complete_sanitary_depth_fixture()
    meta["quantities"]["totals"]["pipe_length_ft"] = 260.0
    meta["quantities"]["explain"]["quantity_audit"]["pipe_length_ft"] = {"source_object_ids": ["SAN-MAIN-1", "SAN-MAIN-2"]}
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    return plan


def _hgl_egl_depth_plan(payload: dict) -> dict:
    meta = _review_depth_meta()
    meta["lot"] = payload.get("lot") or meta["lot"]
    storm, drainage = _complete_storm_hgl_fixture()
    meta["drainage"] = drainage
    meta["storm_pipes"] = enrich_storm_production_depth(storm, drainage)
    meta["quantities"]["totals"]["pipe_length_ft"] = 100.0
    meta["quantities"]["explain"]["quantity_audit"]["pipe_length_ft"] = {"source_object_ids": ["STM-HGL-1"]}
    plan = {
        "project_name": payload.get("project_name"),
        "actions": [
            {
                "task": "polyline",
                "layer": "STORM",
                "canonical_source_type": "storm_pipe_segment",
                "canonical_source_id": "STM-HGL-1",
                "points": [[0.0, 0.0], [100.0, 0.0]],
            }
        ],
        "meta": meta,
    }
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    return plan


def _complete_roadway_grading_fixture_meta() -> dict:
    meta = deepcopy(_complete_grading_depth_meta())
    grading = meta["grading"]
    grading["source"] = "roadway_grading_depth_fixture"
    grading["accepted_existing_surface_id"] = "EG-ACCEPTED-1"
    grading["accepted_proposed_surface_id"] = "FG-ACCEPTED-1"
    grading["grading_source"] = {
        "accepted_existing_surface_id": "EG-ACCEPTED-1",
        "accepted_proposed_surface_id": "FG-ACCEPTED-1",
        "source_status": "accepted_for_engine_depth_fixture",
    }
    grading["surface_traceability"]["contour_interval_ft"] = 2.0
    grading["pad_tie_ins"][0]["pad_id"] = "PAD-BLDG-1"
    grading["contours"][0]["contour_values_ft"] = [100.0, 102.0]
    grading["contours"][0]["actual_contour_count"] = 2
    return meta


def _roadway_grading_depth_plan(payload: dict) -> dict:
    meta = _review_depth_meta()
    fixture = _complete_roadway_grading_fixture_meta()
    meta.update(fixture)
    meta["lot"] = payload.get("lot") or meta["lot"]
    meta["quantities"]["explain"]["quantity_audit"]["roadway_area_sf"] = {"source_object_ids": ["ALG-ROAD-A"]}
    plan = {
        "project_name": payload.get("project_name"),
        "actions": [
            {
                "task": "polyline",
                "layer": "ROAD",
                "canonical_source_type": "road_alignment",
                "canonical_source_id": "ALG-ROAD-A",
                "points": [[0.0, 0.0], [100.0, 0.0]],
            },
            {
                "task": "rectangle",
                "layer": "BUILDING",
                "canonical_source_type": "building_pad",
                "canonical_source_id": "PAD-BLDG-1",
                "width": 50.0,
                "height": 40.0,
            },
        ],
        "meta": meta,
    }
    meta["civil_design_readiness"] = civil_design_readiness(plan)
    meta["engine_readiness"] = evaluate_engine_readiness(plan)
    return plan


def _concept_plan(payload: dict) -> dict:
    return {
        "project_name": payload.get("project_name"),
        "meta": {
            "civil_design_readiness": {
                "status": "blocked",
                "success": False,
                "production_ready": False,
                "production_blockers": [{"area": "site", "field": "site_boundary"}],
                "missing_requirements": [{"system": "site", "field": "site_boundary"}],
            },
            "construction_readiness": {"ready": False, "blockers": [{"area": "site", "field": "site_boundary"}]},
            "construction_package_manifest": {"release_allowed": False, "construction_ready": False},
        },
    }


class EngineDepthAuditTests(unittest.TestCase):
    def test_scenario_report_classifies_required_engines_and_gate_labels(self) -> None:
        report = run_engine_depth_audit_scenario("small_commercial_pad", build_plan_fn=_review_depth_plan)

        self.assertTrue(report["success"], report)
        self.assertEqual(report["status"], "passed")
        self.assertIn("deterministic_checks", report)
        self.assertFalse(report["failed_check_ids"])
        storm = report["required_engine_results"]["storm_pipe"]
        self.assertIn(storm["actual_depth_classification"], {"review", "production-depth"})
        self.assertIn(
            storm["backend_readiness_gate_label"],
            {"expected_engine_depth_actual_review", "expected_production_depth_actual_production_depth"},
        )
        self.assertTrue(
            any(check["check_type"] == "expected_vs_actual_engine_depth" for check in report["deterministic_checks"])
        )
        self.assertTrue(
            any(check["check_type"] == "expected_vs_actual_metric" for check in report["deterministic_checks"])
        )

    def test_audit_report_contract_preserves_phase_1_truth_labels(self) -> None:
        report = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_review_depth_plan)

        self.assertEqual(report["version"], REPORT_VERSION)
        self.assertEqual(report["phase"], "phase_1_engine_depth_audit")
        self.assertTrue(report["success"], report)
        self.assertEqual(report["backend_readiness_gate_label"], "phase_1_backend_depth_audit_passed")
        self.assertFalse(report["construction_ready"])
        self.assertFalse(report["construction_release_allowed"])
        self.assertEqual(report["scenario_count"], 1)
        self.assertGreater(report["deterministic_check_count"], 0)
        self.assertIn("overall_depth_score", report["summary"])
        self.assertGreaterEqual(report["summary"]["overall_depth_score"], 60.0)
        self.assertEqual(report["summary"]["private_alpha_gate_recommendation"], "allow_backend_private_alpha")
        self.assertEqual(report["summary"]["public_beta_gate_recommendation"], "allow_backend_public_beta_review_only")
        self.assertEqual(report["summary"]["construction_gate_recommendation"], "block_construction_not_production_depth")
        self.assertFalse(report["construction_depth_requirements_met"])
        self.assertFalse(report["construction_ready"])
        self.assertIn(CLASS_REVIEW, report["classification_counts"])
        self.assertIn("storm_pipe", report["engine_results"])
        self.assertEqual(len(report["engine_rows"]), len(engine_contracts()))
        row = report["engine_results"]["storm_pipe"]
        for field in ("score", "classification", "checks", "blockers", "first_failing_layer", "confidence", "launch_gate"):
            self.assertIn(field, row)
        self.assertEqual(row["launch_gate"], "review_launch_allowed")
        self.assertGreater(row["confidence"], 0.0)
        self.assertIn("does not modify UI", report["truth_label"])

    def test_single_scenario_helper_returns_full_report_contract(self) -> None:
        report = run_engine_depth_audit_for_scenario("small_commercial_pad", build_plan_fn=_review_depth_plan)

        self.assertEqual(report["version"], REPORT_VERSION)
        self.assertEqual(report["scenario_count"], 1)
        self.assertEqual(report["scenario_results"][0]["scenario_id"], "small_commercial_pad")
        self.assertEqual(len(report["engine_rows"]), len(engine_contracts()))

    def test_concept_or_missing_required_engine_blocks_backend_gate(self) -> None:
        report = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_concept_plan)

        self.assertFalse(report["success"])
        self.assertEqual(report["backend_readiness_gate_label"], "phase_1_backend_depth_audit_blocked")
        self.assertGreater(report["failed_deterministic_check_count"], 0)
        self.assertGreater(report["blocker_count"], 0)
        self.assertEqual(report["engine_results"]["storm_pipe"]["actual_depth_classification"], CLASS_CONCEPT)
        self.assertEqual(
            report["engine_results"]["storm_pipe"]["backend_readiness_gate_label"],
            "backend_blocked_concept_or_missing",
        )
        self.assertTrue(report["blocker_details"][0]["next_action"])

    def test_profile_section_missing_evidence_is_review_depth_not_concept(self) -> None:
        report = run_engine_depth_audit_for_scenario("roadway_corridor", build_plan_fn=_review_depth_plan)

        row = report["engine_results"]["profile_section"]
        self.assertEqual(row["actual_depth_classification"], CLASS_REVIEW)
        self.assertEqual(row["score"], 70.0)
        self.assertEqual(row["first_failing_layer"], "depth_validation")
        self.assertIn("profile_section_depth", {item["area"] for item in row["blockers"]})

    def test_reactive_model_missing_evidence_is_review_depth_not_concept(self) -> None:
        report = run_engine_depth_audit_for_scenario("roadway_corridor", build_plan_fn=_review_depth_plan)

        row = report["engine_results"]["reactive_model"]
        self.assertEqual(row["actual_depth_classification"], CLASS_REVIEW)
        self.assertEqual(row["score"], 70.0)
        self.assertEqual(row["first_failing_layer"], "depth_validation")
        self.assertIn("reactive_model_depth", {item["area"] for item in row["blockers"]})

    def test_complete_storm_hgl_egl_fixture_proves_storm_and_hydrology_depth(self) -> None:
        report = run_engine_depth_audit(scenario_ids=["sloped_detention_site"], build_plan_fn=_hgl_egl_depth_plan)

        storm = report["engine_results"]["storm_pipe"]
        hydrology = report["engine_results"]["hydrology"]
        self.assertEqual(storm["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)
        self.assertEqual(hydrology["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)
        self.assertEqual(storm["score"], 100.0)
        self.assertEqual(hydrology["score"], 100.0)
        self.assertEqual(storm["first_failing_layer"], "")
        self.assertEqual(hydrology["first_failing_layer"], "")
        self.assertFalse(report["construction_release_allowed"])
        self.assertEqual(report["summary"]["construction_gate_recommendation"], "block_construction_not_production_depth")

    def test_complete_sanitary_fixture_proves_sanitary_depth_without_construction_release(self) -> None:
        report = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_sanitary_depth_plan)

        sanitary = report["engine_results"]["sanitary"]
        self.assertEqual(sanitary["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)
        self.assertEqual(sanitary["score"], 100.0)
        self.assertEqual(sanitary["first_failing_layer"], "")
        for evidence in (
            "service_coverage",
            "tie_in_validation",
            "capacity_validation",
            "post_reroute_recalculation",
            "manhole_spacing",
        ):
            self.assertIn(evidence, sanitary["evidence"])
        self.assertFalse(report["construction_release_allowed"])
        self.assertFalse(report["construction_ready"])
        self.assertFalse(report["construction_depth_requirements_met"])

    def test_storm_hgl_egl_fixture_missing_inputs_remain_blocked(self) -> None:
        storm, drainage = _complete_storm_hgl_fixture()
        storm["target_outfall"].pop("z", None)
        drainage["coordination"]["preferred_outfall"].pop("z", None)
        segment = storm["segments"][0]
        segment.pop("end_invert_ft")
        segment["velocity_fps"] = 0.0

        enriched = enrich_storm_production_depth(storm, drainage)
        plan = {"meta": {"storm_pipes": enriched, "drainage": drainage}}
        readiness = evaluate_engine_readiness(plan)
        storm_row = readiness["engines"]["storm_pipe"]

        self.assertEqual(storm_row["status"], "concept_ready_needs_production_depth")
        self.assertIn("missing_tailwater", enriched["hydraulic_profile_evidence"]["labels"])
        missing = enriched["hydraulic_profile_evidence"]["missing_profile_inputs"][0]["missing_fields"]
        self.assertIn("segment.end_invert_ft", missing)
        self.assertIn("segment.velocity_fps", missing)
        messages = {item["message"] for item in storm_row["production_blockers"] if item.get("area") == "storm_depth"}
        self.assertIn("Storm depth needs HGL and EGL profiles from production hydraulic evidence.", messages)
        self.assertIn("Storm depth needs tailwater/backwater evidence.", messages)

    def test_complete_roadway_grading_fixture_proves_roadway_depth(self) -> None:
        report = run_engine_depth_audit(scenario_ids=["roadway_corridor"], build_plan_fn=_roadway_grading_depth_plan)

        roadway = report["engine_results"]["roadway_corridor"]
        self.assertEqual(roadway["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)
        self.assertEqual(roadway["score"], 100.0)
        self.assertEqual(roadway["first_failing_layer"], "")
        self.assertFalse(report["construction_release_allowed"])
        self.assertEqual(report["summary"]["construction_gate_recommendation"], "block_construction_not_production_depth")

        plan = _roadway_grading_depth_plan({"project_name": "roadway grading depth fixture"})
        depth = validate_roadway_corridor_depth(plan)
        self.assertEqual(depth["road_crown_trace"][0]["road_id"], "ALG-ROAD-A")
        self.assertEqual(depth["road_crown_trace"][0]["expected_left_cross_slope"], 0.02)
        self.assertEqual(depth["road_crown_trace"][0]["actual_left_cross_slope"], 0.02)
        self.assertEqual(depth["road_crown_trace"][0]["expected_right_cross_slope"], 0.02)
        self.assertEqual(depth["road_crown_trace"][0]["actual_right_cross_slope"], 0.02)
        self.assertEqual(depth["curb_gutter_trace"][0]["alignment_id"], "ALG-ROAD-A")
        self.assertEqual(depth["curb_gutter_trace"][0]["expected_min_gutter_slope"], 0.005)
        self.assertEqual(depth["curb_gutter_trace"][0]["actual_gutter_slope"], 0.006)
        self.assertEqual(depth["ada_path_trace"][0]["expected_max_running_slope"], 0.05)
        self.assertEqual(depth["ada_path_trace"][0]["actual_running_slope"], 0.04)
        self.assertEqual(depth["ada_path_trace"][0]["expected_max_cross_slope"], 0.02)
        self.assertEqual(depth["ada_path_trace"][0]["actual_cross_slope"], 0.015)
        self.assertEqual(depth["pad_tie_in_trace"][0]["building_id"], "BLDG-1")
        self.assertEqual(depth["pad_tie_in_trace"][0]["expected_proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertEqual(depth["pad_tie_in_trace"][0]["actual_proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertEqual(depth["pad_tie_in_trace"][0]["expected_max_tie_slope"], 0.05)
        self.assertEqual(depth["pad_tie_in_trace"][0]["actual_tie_slope"], 0.03)
        self.assertEqual(depth["contour_trace"][0]["expected_proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertEqual(depth["contour_trace"][0]["actual_proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertEqual(depth["contour_trace"][0]["expected_min_contour_count"], 1)
        self.assertEqual(depth["contour_trace"][0]["actual_contour_count"], 2)
        self.assertEqual(depth["surface_traceability"]["existing_surface_id"], "EG-ACCEPTED-1")
        self.assertEqual(depth["surface_traceability"]["proposed_surface_id"], "FG-ACCEPTED-1")

    def test_complete_grading_fixture_proves_grading_depth(self) -> None:
        report = run_engine_depth_audit(scenario_ids=["roadway_corridor"], build_plan_fn=_roadway_grading_depth_plan)

        grading = report["engine_results"]["grading"]
        self.assertEqual(grading["actual_depth_classification"], CLASS_PRODUCTION_DEPTH)
        self.assertEqual(grading["score"], 100.0)
        self.assertEqual(grading["first_failing_layer"], "")
        self.assertFalse(report["construction_release_allowed"])
        self.assertEqual(report["summary"]["construction_gate_recommendation"], "block_construction_not_production_depth")

        plan = _roadway_grading_depth_plan({"project_name": "grading depth fixture"})
        grading_depth = plan["meta"]["engine_readiness"]["engines"]["grading"]
        self.assertEqual(grading_depth["status"], "production_ready")
        self.assertIn("depth_validation", grading_depth["evidence"])

    def test_roadway_grading_fixture_missing_evidence_remains_blocked(self) -> None:
        meta = _complete_roadway_grading_fixture_meta()
        meta["grading"]["road_crown_controls"][0].pop("actual_left_cross_slope")
        meta["grading"]["road_crown_controls"][0].pop("actual_cross_slope")
        meta["grading"]["curb_gutter_controls"][0].pop("alignment_id")
        meta["grading"]["surface_traceability"].pop("proposed_surface_id")
        meta["grading"].pop("proposed_surface_id", None)
        meta["grading"]["proposed_surface"].pop("id")
        meta["grading"]["pad_tie_ins"][0].pop("proposed_surface_id")
        meta["grading"]["contours"][0]["actual_contour_count"] = 0
        plan = {"meta": meta}

        readiness = evaluate_engine_readiness(plan)
        roadway = readiness["engines"]["roadway_corridor"]
        depth = validate_roadway_corridor_depth(plan)

        self.assertNotEqual(roadway["status"], "production_ready")
        self.assertFalse(depth["production_ready"])
        self.assertFalse(depth["road_crown_trace"][0]["valid"])
        self.assertFalse(depth["pad_tie_in_trace"][0]["valid"])
        self.assertFalse(depth["contour_trace"][0]["valid"])
        blockers = set(depth["blockers"])
        self.assertIn("Roadway depth needs verified road crown controls with expected/actual crown and cross-slope values.", blockers)
        self.assertIn("Roadway depth needs accepted grading surface traceability.", blockers)
        self.assertIn("Roadway depth needs pad tie-ins tied to accepted proposed surface IDs.", blockers)
        self.assertIn("Roadway depth needs contours tied to accepted proposed surface evidence.", blockers)

    def test_audit_writes_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "engine_depth_audit.json"
            report = run_engine_depth_audit(
                scenario_ids=["small_commercial_pad"],
                build_plan_fn=_review_depth_plan,
                output_path=target,
            )
            written = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(written["version"], REPORT_VERSION)
        self.assertEqual(written["status"], report["status"])
        self.assertIn("deterministic_checks", written)

    def test_report_serialization_is_stable_for_ci(self) -> None:
        first = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_review_depth_plan)
        second = run_engine_depth_audit(scenario_ids=["small_commercial_pad"], build_plan_fn=_review_depth_plan)

        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        golden = first["scenario_results"][0]["golden_result"]
        self.assertNotIn("load_threshold_results", golden)
        self.assertIn("failed_load_thresholds", golden)

    def test_golden_scenario_references_engine_depth_audit_contract(self) -> None:
        result = run_golden_scenario("small_commercial_pad", build_plan_fn=_review_depth_plan)

        reference = result["engine_depth_audit"]
        self.assertEqual(reference["report_version"], REPORT_VERSION)
        self.assertEqual(reference["scenario_id"], "small_commercial_pad")
        self.assertEqual(reference["helper"], "backend.planning.engine_depth_audit.run_engine_depth_audit_for_scenario")
        self.assertTrue(reference["reference_only"])


if __name__ == "__main__":
    unittest.main()
