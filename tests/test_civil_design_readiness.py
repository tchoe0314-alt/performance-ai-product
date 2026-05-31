import unittest

from backend.planning.standards_discovery import (
    accept_standards_rules,
    build_standards_review_packet,
    standards_pack_from_acceptance,
)
import planner
from core.civil_design import (
    civil_design_readiness,
    construction_readiness,
    path_clearance,
    path_length,
    sample_path,
    standards_from_meta,
    station_point,
    utility_pairing_rule,
)
from engines.cost_engine import compute_cost_estimate


def _complete_meta() -> dict:
    return {
        "grading": {
            "success": True,
            "source_quality": "terrain",
            "source_detail": "Mapbox Terrain-RGB",
            "low_points": [{"x": 10.0, "y": 0.0, "z": 98.0}],
            "high_points": [{"x": 0.0, "y": 10.0, "z": 104.0}],
            "slope_summary": {"direction": "southeast", "average_slope": 0.025},
        },
        "site_boundary": {"w": 220.0, "h": 160.0, "area_sf": 35200.0},
        "drainage": {
            "success": True,
            "source": "drainage_engine",
            "structures": [{"name": "INLET-1", "x": 15.0, "y": 12.0, "estimated_flow_cfs": 0.8}],
            "basins": [{"name": "BASIN-1", "target_name": "OUTLET-1"}],
            "low_points": [{"x": 12.0, "y": 8.0}],
            "flow_paths": [{"from": "INLET-1", "to": "OUTLET-1", "points": [[15.0, 12.0], [40.0, 8.0]]}],
            "stats": {
                "total_contributing_area_sf": 12000.0,
                "total_estimated_inlet_flow_cfs": 0.8,
                "total_basin_runoff_cfs": 1.2,
            },
            "surface_guidance": {"surface_source": "terrain", "surface_from_grading": True},
            "coordination": {"preferred_outfall": {"target_name": "OUTLET-1"}},
        },
        "storm_pipes": {
            "success": True,
            "source": "storm_network_engine",
            "hydraulic_source": "storm_network_engine+hydraulic_engine",
            "selected_outfall": "OUTLET-1",
            "target_outfall_name": "OUTLET-1",
            "segments": [
                {
                    "pipe": "P-1",
                    "length_ft": 80.0,
                    "capacity_cfs": 4.0,
                    "flow_cfs": 1.2,
                    "slope_ft_ft": 0.006,
                    "capacity_ratio": 0.3,
                    "tributary_area_sf": 12000.0,
                }
            ],
            "total_system_flow_cfs": 1.2,
            "total_system_capacity_cfs": 4.0,
            "controlling_segment": "P-1",
            "max_capacity_ratio": 0.3,
            "graph_validation": {"valid": True},
            "hydraulic_validation": {"valid": True},
            "missing_data_segments": [],
        },
        "sanitary": {
            "success": True,
            "source": "sanitary_engine",
            "route_count": 1,
            "service_count": 1,
            "segments": [{"name": "SAN-1", "length_ft": 90.0, "slope": 0.01}],
            "manholes": [{"name": "MH-1", "x": 0.0, "y": 0.0}, {"name": "MH-2", "x": 90.0, "y": 0.0}],
            "graph_validation": {"valid": True},
            "network_validation": {"valid": True},
            "missing_service_buildings": [],
            "missing_data_segments": [],
        },
        "utilities": {
            "source": "utility_engine",
            "segments": [{"name": "W-1", "system": "water", "length_ft": 100.0}],
            "min_cover_ft": 3.5,
            "coordination": {"unresolved_conflict_count": 0},
        },
        "coordination": {
            "source": "coordination_engine",
            "detected_conflicts": 2,
            "resolved_count": 2,
            "unresolved_count": 0,
            "assumption_resolutions": [],
        },
    }


def _production_ready_meta() -> dict:
    meta = _complete_meta()
    packet = build_standards_review_packet(
        extracted_rules=[
            {
                "rule_id": "city_storm_capacity",
                "discipline": "storm",
                "topic": "Pipe capacity ratio",
                "candidate_value": "Flag storm pipe segments above 95 percent capacity ratio.",
                "source_url": "https://city.example.gov/drainage-manual",
                "source_section": "Storm Drainage 5.2",
            },
            {
                "rule_id": "city_utility_cover",
                "discipline": "utilities",
                "topic": "Minimum utility cover",
                "candidate_value": "Minimum utility cover is 3 feet.",
                "source_url": "https://city.example.gov/utility-standards",
                "source_section": "Utilities 2.1",
            },
        ]
    )
    accepted = accept_standards_rules(packet, ["city_storm_capacity", "city_utility_cover"])
    meta["standards_acceptance"] = accepted
    meta["design_standards"] = standards_pack_from_acceptance(accepted)
    meta["jurisdiction_standards"] = {
        "agency": "Test City",
        "source_url": "https://city.example.gov/engineering-standards",
        "production_usable": True,
    }
    meta["company_standards"] = {
        "source": "company_manual",
        "version": "2026.05",
        "cad_layer_standard": "CIVORA_TEST",
        "title_block": "CIVORA",
        "approved_by": "QA Manager",
        "approval_date": "2026-05-01",
        "production_usable": True,
    }
    meta["survey"] = {
        "point_count": 18,
        "source": "survey_points",
        "benchmark": "BM-1",
        "datum": "NAVD88",
        "control_verified": True,
    }
    meta["gis_layers"] = {
        "parcels": [{}],
        "easements": [{}],
        "row": [{}],
        "floodplain": [{}],
        "wetlands": [{}],
        "existing_utilities": [{}],
    }
    meta["coordinate_system"] = {"epsg": "EPSG:2276", "units": "ft", "source": "survey_control", "production_usable": True}
    meta["existing_conditions_summary"] = {
        "production_ready": True,
        "survey_ready": True,
        "gis_ready": True,
        "coordinate_system_ready": True,
    }
    meta["grading"]["source_quality"] = "survey"
    meta["grading"]["road_crown_controls"] = [{"road": "A", "cross_slope": 0.02}]
    meta["grading"]["curb_gutter_controls"] = [{"road": "A", "gutter_slope": 0.01}]
    meta["grading"]["ada_path_checks"] = [{"path": "ADA-1", "valid": True}]
    meta["grading"]["pad_tie_ins"] = [{"building": "B-1", "valid": True}]
    meta["grading"]["contours"] = [{"elev": 100.0, "points": [[0.0, 0.0], [10.0, 0.0]]}]
    meta["grading"]["contour_interval_ft"] = 2.0
    meta["drainage"]["detention_routing"] = [{"basin": "BASIN-1", "valid": True}]
    meta["storm_pipes"]["hgl_profile"] = [{"station": 0.0, "hgl_ft": 98.0}]
    meta["storm_pipes"]["egl_profile"] = [{"station": 0.0, "egl_ft": 98.2}]
    meta["storm_pipes"]["tailwater_elev_ft"] = 96.0
    meta["storm_pipes"]["inlet_capacity_checks"] = [{"inlet": "INLET-1", "spread_ft": 4.0, "bypass_cfs": 0.0, "valid": True}]
    meta["storm_pipes"]["backwater_validation"] = {"valid": True, "surcharged_segments": []}
    meta["depth_validation"] = {
        "stormwater": {"production_ready": True, "blockers": [], "canonical_model_id": "MODEL-FINAL-1"},
        "water": {"production_ready": True, "blockers": [], "canonical_model_id": "MODEL-FINAL-1"},
        "roadway_corridor": {"production_ready": True, "blockers": [], "canonical_model_id": "MODEL-FINAL-1"},
    }
    meta["canonical_model_id"] = "MODEL-FINAL-1"
    meta["truth_audit"] = {"success": True, "canonical_model_id": "MODEL-FINAL-1"}
    meta["manual_validation"] = {
        "success": True,
        "failed": False,
        "failures": [],
        "canonical_model_id": "MODEL-FINAL-1",
    }
    meta["reactive_update_report"] = {
        "export_blocked": False,
        "post_rerun_stale_outputs": [],
        "canonical_model_id": "MODEL-FINAL-1",
    }
    meta["export_audit"] = {
        "ready": True,
        "production_export_ready": True,
        "export_blocked": False,
        "canonical_id_traceability": {"ready": True},
        "canonical_model_id": "MODEL-FINAL-1",
    }
    meta["sheet_registry"] = {
        "ready": True,
        "sheets": [
            {
                "id": "C-100",
                "title": "Civil Site Plan",
                "current": True,
                "canonical_model_id": "MODEL-FINAL-1",
            }
        ],
    }
    meta["quantities"] = {
        "success": True,
        "canonical_model_id": "MODEL-FINAL-1",
        "totals": {"pipe_length_ft": 1000.0},
        "explain": {
            "meta_summary": {"quantity_traceability_complete": True},
            "quantity_audit": {"pipe_length_ft": {"source_object_ids": ["storm-1"]}},
            "trace_gaps": {},
        },
    }
    meta["cost_pricing"] = {
        "source": "company_2026_bid_book",
        "location": "Test City",
        "effective_date": "2026-05-01",
        "approved_by": "Estimator",
        "approval_date": "2026-05-02",
        "unit_prices": {
            "pipe_length_ft": {
                "item": "RCP storm pipe",
                "category": "storm",
                "unit": "ft",
                "unit_cost": 125.0,
                "source_item_id": "ST-125",
            }
        },
    }
    cost = compute_cost_estimate({"meta": meta})
    meta["cost_estimate"] = {
        "success": cost.success,
        "canonical_model_id": "MODEL-FINAL-1",
        "totals": cost.totals,
        "explain": cost.explain,
        "line_items": cost.line_items,
    }
    meta["cad_interop"] = {"source": "test", "civil3d": True, "landxml": True, "pipe_network_export": True}
    meta["optimization_summary"] = {
        "source": "test",
        "overall_score": 92.0,
        "component_scores": {"grading": 90.0, "drainage": 93.0},
        "alternatives": [
            {
                "id": "ALT-A",
                "name": "A",
                "geometry_committed": True,
                "accepted": True,
                "canonical_model_id": "MODEL-FINAL-1",
            },
            {
                "id": "ALT-B",
                "name": "B",
                "geometry_committed": True,
                "accepted": True,
                "canonical_model_id": "MODEL-FINAL-1",
                "geometry_snapshot_id": "SNAP-B",
            },
        ],
        "comparison_summary": {"recommended_option_name": "A", "runner_up_option_name": "B"},
        "recommendations": ["Use option A."],
    }
    return meta


class CivilDesignReadinessTests(unittest.TestCase):
    def test_complete_canonical_meta_is_ready(self) -> None:
        readiness = civil_design_readiness({"meta": _complete_meta()})

        self.assertTrue(readiness["success"])
        self.assertIn(readiness["status"], {"ready", "needs_engineering_review"})
        self.assertEqual(readiness["truth_sources"]["grading"], "terrain")
        self.assertGreaterEqual(readiness["score"], 80.0)
        self.assertEqual(readiness["real_world_readiness"], "concept_design_ready")
        self.assertFalse(readiness["production_ready"])
        self.assertTrue(readiness["production_blockers"])
        self.assertEqual(readiness["systems"]["storm_pipes"]["metrics"]["segment_count"], 1)
        self.assertEqual(readiness["systems"]["sanitary"]["metrics"]["manhole_count"], 2)
        self.assertFalse(readiness["critical_blockers"])

    def test_missing_engineering_truth_returns_structured_requirements(self) -> None:
        readiness = civil_design_readiness({"meta": {"grading": {"source_quality": "fallback"}}})

        self.assertFalse(readiness["success"])
        self.assertEqual(readiness["status"], "blocked")
        self.assertTrue(readiness["missing_requirements"])
        fields = {(item["system"], item["field"]) for item in readiness["missing_requirements"]}
        self.assertIn(("grading", "low_points"), fields)
        self.assertIn(("site", "site_boundary"), fields)
        self.assertIn(("drainage", "basin_or_outfall"), fields)
        self.assertIn(("storm_pipes", "selected_outfall"), fields)
        self.assertTrue(readiness["can_assist_if_enabled"])
        detail_fields = {(item["area"], item["field"]) for item in readiness["missing_requirement_details"]}
        self.assertIn(("site", "site_boundary"), detail_fields)
        site_detail = next(item for item in readiness["critical_blocker_details"] if item["field"] == "site_boundary")
        self.assertTrue(site_detail["next_action"])

    def test_coordination_unresolved_blocks_readiness(self) -> None:
        meta = _complete_meta()
        meta["coordination"] = {"unresolved_count": 1, "assumption_resolutions": [{"reason": "concept"}]}

        readiness = civil_design_readiness({"meta": meta})

        self.assertFalse(readiness["success"])
        self.assertIn(("coordination", "unresolved_conflicts"), {(item["system"], item["field"]) for item in readiness["critical_blockers"]})
        self.assertTrue(any(item["system"] == "coordination" for item in readiness["warnings"]))

    def test_geometry_and_rule_helpers_are_deterministic(self) -> None:
        path = [(0.0, 0.0), (30.0, 0.0), (30.0, 40.0)]
        self.assertEqual(path_length(path), 70.0)
        self.assertEqual(station_point(path, 15.0), (15.0, 0.0))
        self.assertEqual(station_point(path, 50.0), (30.0, 20.0))
        self.assertEqual(len(sample_path(path, spacing_ft=25.0, max_samples=5)), 4)
        self.assertEqual(path_clearance([(0.0, 0.0), (10.0, 0.0)], [(0.0, 5.0), (10.0, 5.0)]), 5.0)

        rule = utility_pairing_rule("water", "sanitary")
        self.assertEqual(rule["priority"], "pressure_utility_protected")
        self.assertGreaterEqual(rule["horizontal_separation_ft"], 10.0)

    def test_capacity_cover_and_service_gaps_are_reported_without_fake_success(self) -> None:
        meta = _complete_meta()
        meta["storm_pipes"]["max_capacity_ratio"] = 1.12
        meta["storm_pipes"]["segments"][0]["capacity_ratio"] = 1.12
        meta["sanitary"]["service_count"] = 0
        meta["sanitary"]["max_capacity_ratio"] = 0.92
        meta["utilities"]["segments"] = [
            {"name": "W-1", "system": "water", "cover_ft": 2.0, "path": [[0.0, 0.0], [100.0, 0.0]]},
            {"name": "SAN-1", "system": "sanitary", "cover_ft": 4.0, "path": [[0.0, 4.0], [100.0, 4.0]]},
        ]

        readiness = civil_design_readiness({"meta": meta})
        fields = {(item["system"], item["field"]) for item in readiness["missing_requirements"]}

        self.assertFalse(readiness["success"])
        self.assertIn(("storm_pipes", "max_capacity_ratio"), fields)
        self.assertIn(("sanitary", "service_count"), fields)
        self.assertIn(("sanitary", "max_capacity_ratio"), fields)
        self.assertIn(("utilities", "cover_ft"), fields)
        self.assertGreater(readiness["systems"]["utilities"]["metrics"]["separation_warning_count"], 0)

    def test_accepted_standards_pack_tightens_qa_thresholds(self) -> None:
        meta = _complete_meta()
        meta["design_standards"] = {
            "source": "accepted_standards_review_packet",
            "version": "city_manual_2026",
            "rules": [
                {
                    "rule_id": "city_storm_capacity",
                    "topic": "Pipe capacity ratio",
                    "candidate_value": "Flag storm pipe segments above 0.25 capacity ratio.",
                    "status": "accepted",
                },
                {
                    "rule_id": "city_cover",
                    "topic": "Minimum utility cover",
                    "candidate_value": "Minimum utility cover shall be 48 inches.",
                    "status": "accepted",
                },
            ],
            "production_usable": True,
        }
        meta["storm_pipes"]["max_capacity_ratio"] = 0.3
        meta["utilities"]["segments"] = [{"name": "W-1", "system": "water", "cover_ft": 3.5, "path": [[0.0, 0.0], [10.0, 0.0]]}]

        active = standards_from_meta(meta)
        readiness = civil_design_readiness({"meta": meta})
        fields = {(item["system"], item["field"]) for item in readiness["missing_requirements"]}

        self.assertEqual(active.version, "city_manual_2026")
        self.assertAlmostEqual(active.max_pipe_capacity_ratio, 0.25)
        self.assertAlmostEqual(active.min_utility_cover_ft, 4.0)
        self.assertIn(("storm_pipes", "max_capacity_ratio"), fields)
        self.assertIn(("utilities", "cover_ft"), fields)

    def test_accepted_water_standards_tighten_utility_qa(self) -> None:
        meta = _complete_meta()
        meta["design_standards"] = {
            "source": "accepted_standards_review_packet",
            "version": "water_manual_2026",
            "rules": [
                {
                    "rule_id": "hydrant_spacing",
                    "topic": "Hydrant spacing",
                    "candidate_value": "Hydrant spacing shall not exceed 300 feet.",
                    "status": "accepted",
                },
                {
                    "rule_id": "fire_flow",
                    "topic": "Fire flow",
                    "candidate_value": "Minimum required fire flow is 1500 gpm.",
                    "status": "accepted",
                },
                {
                    "rule_id": "residual_pressure",
                    "topic": "Residual pressure",
                    "candidate_value": "Minimum residual pressure shall be 35 psi.",
                    "status": "accepted",
                },
                {
                    "rule_id": "water_velocity",
                    "topic": "Water velocity",
                    "candidate_value": "Water velocity shall not exceed 6 fps.",
                    "status": "accepted",
                },
            ],
            "production_usable": True,
        }
        meta["utilities"].update(
            {
                "pressure_validation": {"valid": True, "min_pressure_psi": 30.0},
                "fire_flow_validation": {"valid": True, "available_fire_flow_gpm": 1200.0},
                "hydrant_spacing_validation": {"valid": True, "max_spacing_ft": 360.0},
                "velocity_checks": [{"segment": "W-1", "velocity_fps": 7.1}],
            }
        )

        active = standards_from_meta(meta)
        readiness = civil_design_readiness({"meta": meta})
        fields = {(item["system"], item["field"]) for item in readiness["missing_requirements"]}

        self.assertEqual(active.version, "water_manual_2026")
        self.assertAlmostEqual(active.max_hydrant_spacing_ft, 300.0)
        self.assertAlmostEqual(active.min_fire_flow_gpm, 1500.0)
        self.assertAlmostEqual(active.min_water_residual_pressure_psi, 35.0)
        self.assertAlmostEqual(active.max_water_velocity_fps, 6.0)
        self.assertIn(("utilities", "water_velocity"), fields)
        self.assertIn(("utilities", "water_pressure"), fields)
        self.assertIn(("utilities", "hydrant_spacing"), fields)
        self.assertIn(("utilities", "fire_flow"), fields)

    def test_claimed_production_standards_without_traceability_are_blocked(self) -> None:
        meta = _complete_meta()
        meta["design_standards"] = {
            "source": "manual_override",
            "version": "untraceable",
            "rules": [{"rule_id": "cover", "topic": "Minimum utility cover", "candidate_value": "Minimum cover is 4 ft.", "status": "accepted"}],
            "production_usable": True,
        }

        readiness = civil_design_readiness({"meta": meta})
        fields = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("standards", "official_sources"), fields)
        self.assertIn(("standards", "rule_metadata"), fields)

    def test_production_depth_gates_clear_when_real_design_evidence_exists(self) -> None:
        meta = _production_ready_meta()

        readiness = civil_design_readiness({"meta": meta})

        self.assertTrue(readiness["success"])
        self.assertTrue(readiness["production_ready"])
        self.assertEqual(readiness["real_world_readiness"], "production_review_candidate")
        self.assertFalse(readiness["production_blockers"])

    def test_construction_readiness_blocks_unsealed_production_candidate(self) -> None:
        meta = _production_ready_meta()
        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["status"], "not_construction_ready")
        self.assertIn(("professional_review", "sealed_release"), blockers)
        detail_fields = {(item["area"], item["field"]) for item in readiness["blocker_details"]}
        self.assertIn(("professional_review", "sealed_release"), detail_fields)
        self.assertIn("Civora does not stamp drawings", readiness["truth_label"])

    def test_construction_readiness_blocks_unapproved_cost_book(self) -> None:
        meta = _production_ready_meta()
        meta["cost_estimate"]["totals"]["production_usable"] = False
        meta["cost_estimate"]["explain"]["pricing"] = {
            "production_usable": False,
            "source": "civora_concept_default_unit_prices",
            "production_validation": {
                "production_usable": False,
                "blockers": [{"field": "source", "reason": "Missing approved price source."}],
            },
        }

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("cost", "production_unit_price_book"), blockers)
        self.assertIn(("cost", "source"), blockers)
        self.assertFalse(readiness["evidence"]["cost_production_usable"])

    def test_construction_readiness_blocks_cost_without_quantity_model(self) -> None:
        meta = _production_ready_meta()
        meta.pop("quantities", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("cost", "quantity_model"), blockers)

    def test_construction_readiness_blocks_stale_cost_quantity_model(self) -> None:
        meta = _production_ready_meta()
        meta["quantities"]["totals"]["pipe_length_ft"] = 1200.0

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("cost", "cost_quantity_model_mismatch"), blockers)

    def test_construction_readiness_blocks_cost_missing_quantity_hash(self) -> None:
        meta = _production_ready_meta()
        meta["cost_estimate"]["explain"].pop("quantity_model_reference", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("cost", "cost_quantity_trace"), blockers)

    def test_construction_readiness_blocks_quantity_without_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["quantities"].pop("canonical_model_id", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("cost", "quantity_model_trace"), blockers)

    def test_construction_readiness_blocks_cost_estimate_model_mismatch(self) -> None:
        meta = _production_ready_meta()
        meta["cost_estimate"]["canonical_model_id"] = "MODEL-OLD"

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("cost", "cost_estimate_model_trace"), blockers)

    def test_construction_readiness_requires_survey_control_metadata(self) -> None:
        meta = _production_ready_meta()
        meta["survey"] = {"point_count": 18, "source": "survey_points"}

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("existing_conditions", "survey_benchmark"), blockers)
        self.assertIn(("existing_conditions", "survey_datum"), blockers)
        self.assertIn(("existing_conditions", "survey_control_verified"), blockers)

    def test_construction_readiness_requires_survey_control_verified_true(self) -> None:
        meta = _production_ready_meta()
        meta["survey"].pop("control_verified", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("existing_conditions", "survey_control_verified"), blockers)

    def test_civil_readiness_blocks_survey_file_without_points_or_approval(self) -> None:
        meta = _production_ready_meta()
        meta["grading"]["source_quality"] = "terrain"
        meta["survey"] = {"source": "survey.csv"}
        meta["existing_conditions_summary"] = {}

        readiness = civil_design_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("existing_conditions", "survey_surface"), blockers)

    def test_construction_readiness_requires_complete_gis_layer_evidence(self) -> None:
        meta = _production_ready_meta()
        meta["gis_layers"] = {
            "parcels": [{"id": "P-1"}],
            "easements": [{"id": "E-1"}],
            "row": [{"id": "ROW-1"}],
            "floodplain": {"verified_absent": True, "source": "FEMA FIRM"},
        }

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("existing_conditions", "gis_wetlands"), blockers)
        self.assertIn(("existing_conditions", "gis_existing_utilities"), blockers)

    def test_construction_readiness_requires_production_usable_coordinate_source(self) -> None:
        meta = _production_ready_meta()
        meta["coordinate_system"] = {"epsg": "EPSG:2276", "units": "ft"}

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("existing_conditions", "coordinate_system_production_usable"), blockers)
        self.assertIn(("existing_conditions", "coordinate_system_source"), blockers)

    def test_construction_readiness_requires_jurisdiction_standards_traceability(self) -> None:
        meta = _production_ready_meta()
        meta["jurisdiction_standards"] = {"production_usable": True}

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("standards", "jurisdiction_standards_traceability"), blockers)

    def test_construction_readiness_requires_jurisdiction_standards_production_usable(self) -> None:
        meta = _production_ready_meta()
        meta["jurisdiction_standards"].pop("production_usable", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("standards", "jurisdiction_standards_production_usable"), blockers)

    def test_construction_readiness_requires_company_standards_production_evidence(self) -> None:
        meta = _production_ready_meta()
        meta["company_standards"] = {"cad_layer_standard": "CIVORA_TEST"}

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("standards", "company_standards_production_usable"), blockers)
        self.assertIn(("standards", "company_standards_traceability"), blockers)
        self.assertIn(("standards", "company_standards_approval"), blockers)

    def test_construction_readiness_blocks_unapproved_company_standards(self) -> None:
        meta = _production_ready_meta()
        meta["company_standards"].pop("approved_by", None)
        meta["company_standards"].pop("approval_date", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("standards", "company_standards_approval"), blockers)

    def test_construction_readiness_requires_qa_and_reactive_reports_to_exist(self) -> None:
        meta = _production_ready_meta()
        meta.pop("truth_audit")
        meta.pop("manual_validation")
        meta.pop("reactive_update_report")

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("qa", "truth_audit"), blockers)
        self.assertIn(("qa", "manual_validation"), blockers)
        self.assertIn(("reactive_model", "reactive_update_report"), blockers)

    def test_construction_readiness_blocks_stale_depth_validation_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["depth_validation"]["stormwater"]["canonical_model_id"] = "MODEL-OLD"
        meta["depth_validation"]["water"].pop("canonical_model_id", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("depth_validation", "stormwater_model_trace"), blockers)
        self.assertIn(("depth_validation", "water_model_trace"), blockers)

    def test_construction_readiness_blocks_stale_qa_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["truth_audit"] = {"success": True, "canonical_model_id": "MODEL-OLD"}
        meta["manual_validation"] = {
            "success": True,
            "failed": False,
            "failures": [],
            "canonical_model_id": "MODEL-OLD",
        }

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("qa", "truth_audit_model_trace"), blockers)
        self.assertIn(("qa", "manual_validation_model_trace"), blockers)

    def test_construction_readiness_blocks_stale_reactive_update_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["reactive_update_report"] = {
            "export_blocked": False,
            "post_rerun_stale_outputs": [],
            "canonical_model_id": "MODEL-OLD",
        }

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("reactive_model", "reactive_update_model_trace"), blockers)

    def test_construction_readiness_blocks_post_rerun_release_blockers(self) -> None:
        meta = _production_ready_meta()
        meta["reactive_update_report"] = {
            "export_blocked": False,
            "post_rerun_stale_outputs": [],
            "post_rerun_production_ready": False,
            "post_rerun_release_blockers": ["manual_validation_manual_storm_hydraulic_invalid"],
            "canonical_model_id": "MODEL-FINAL-1",
        }

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("reactive_model", "post_rerun_release_blockers"), blockers)

    def test_construction_readiness_requires_accepted_coordination_conflict_signoff_and_trace(self) -> None:
        meta = _production_ready_meta()
        meta["coordination"]["accepted_conflicts"] = [{"id": "UC-1", "status": "accepted", "resolved": False}]

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("coordination", "accepted_coordination_conflict_signoff"), blockers)
        self.assertIn(("coordination", "accepted_coordination_conflict_model_trace"), blockers)

    def test_construction_readiness_blocks_stale_accepted_utility_conflict_trace(self) -> None:
        meta = _production_ready_meta()
        meta["utilities"]["coordination"]["accepted_conflicts"] = [
            {
                "id": "UC-1",
                "status": "accepted",
                "resolved": False,
                "accepted_by": "Alex Morgan",
                "accepted_date": "2026-05-28",
                "canonical_model_id": "MODEL-OLD",
            }
        ]

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("coordination", "accepted_coordination_conflict_model_trace"), blockers)

    def test_construction_readiness_accepts_signed_coordination_conflict_acceptance(self) -> None:
        meta = _production_ready_meta()
        meta["coordination"]["accepted_conflicts"] = [
            {
                "id": "UC-1",
                "status": "accepted",
                "resolved": False,
                "accepted_by": "Alex Morgan",
                "accepted_date": "2026-05-28",
                "canonical_model_id": "MODEL-FINAL-1",
            }
        ]
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }

        readiness = construction_readiness({"meta": meta})

        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["blockers"])

    def test_construction_readiness_blocks_stale_professional_release_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-OLD",
        }

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("professional_review", "professional_release_model_trace"), blockers)

    def test_construction_readiness_requires_export_traceability_and_sheet_items(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["export_audit"] = {"production_export_ready": True, "export_blocked": False}
        meta["sheet_registry"] = {"source": "placeholder"}

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("deliverables", "canonical_id_traceability"), blockers)
        self.assertIn(("deliverables", "sheet_registry"), blockers)

    def test_construction_readiness_blocks_stale_export_audit_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["export_audit"]["canonical_model_id"] = "MODEL-OLD"

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("deliverables", "export_audit_model_trace"), blockers)

    def test_construction_readiness_blocks_export_audit_without_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["export_audit"].pop("canonical_model_id", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("deliverables", "export_audit_model_trace"), blockers)

    def test_construction_readiness_blocks_sheet_registry_without_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["sheet_registry"] = {"ready": True, "sheets": [{"id": "C-100", "title": "Civil Site Plan", "current": True}]}

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("deliverables", "sheet_registry_model_trace"), blockers)

    def test_construction_readiness_blocks_sheet_registry_model_mismatch(self) -> None:
        meta = _production_ready_meta()
        meta["sheet_registry"]["sheets"][0]["canonical_model_id"] = "MODEL-OLD"

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("deliverables", "sheet_registry_model_trace"), blockers)

    def test_construction_readiness_blocks_retaining_wall_without_tie_ins_and_structural_review(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["retaining_walls"] = [{"id": "RW-1", "max_height_ft": 6.5}]

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("structures", "retaining_wall_tie_ins"), blockers)
        self.assertIn(("structures", "retaining_wall_structural_review"), blockers)

    def test_construction_readiness_accepts_retaining_wall_with_traceable_review(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["retaining_walls"] = [{"id": "RW-1", "max_height_ft": 6.5}]
        meta["structures"] = {"wall_tie_in_checks": [{"wall_id": "RW-1", "valid": True}]}
        meta["retaining_wall_design_review"] = {
            "sealed": True,
            "reviewed_by": "Structural Engineer",
            "review_date": "2026-05-28",
            "canonical_model_id": "MODEL-FINAL-1",
        }

        readiness = construction_readiness({"meta": meta})

        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["blockers"])

    def test_construction_readiness_blocks_stale_retaining_wall_review_trace(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["retaining_walls"] = [{"id": "RW-1", "max_height_ft": 6.5}]
        meta["structures"] = {"wall_tie_in_checks": [{"wall_id": "RW-1", "valid": True}]}
        meta["retaining_wall_design_review"] = {
            "sealed": True,
            "reviewed_by": "Structural Engineer",
            "review_date": "2026-05-28",
            "canonical_model_id": "MODEL-OLD",
        }

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("structures", "retaining_wall_structural_review_model_trace"), blockers)

    def test_construction_readiness_blocks_foundations_without_coordination_evidence(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["foundations"] = [{"id": "F-1", "building_id": "B-1"}]

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("structures", "foundation_footing_elevations"), blockers)
        self.assertIn(("structures", "foundation_utility_clearance"), blockers)
        self.assertIn(("structures", "foundation_excavation_limits"), blockers)

    def test_construction_readiness_blocks_bridge_interfaces_without_sealed_coordination(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["bridge_interfaces"] = [{"id": "BR-IF-1", "bridge_id": "BR-1"}]

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("structures", "bridge_grading_interaction"), blockers)
        self.assertIn(("structures", "bridge_utility_clearance"), blockers)
        self.assertIn(("structures", "bridge_interface_structural_review"), blockers)

    def test_construction_readiness_blocks_unresolved_structure_conflicts(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["structure_conflicts"] = [{"id": "SC-1", "status": "open", "resolved": False}]

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("structures", "structure_conflicts"), blockers)

    def test_construction_readiness_requires_accepted_structure_conflict_signoff_and_trace(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["structure_conflicts"] = [{"id": "SC-1", "status": "accepted", "resolved": False}]

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("structures", "accepted_structure_conflict_signoff"), blockers)
        self.assertIn(("structures", "accepted_structure_conflict_model_trace"), blockers)

    def test_construction_readiness_blocks_stale_accepted_structure_conflict_trace(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["structure_conflicts"] = [
            {
                "id": "SC-1",
                "status": "accepted",
                "resolved": False,
                "accepted_by": "Alex Morgan",
                "accepted_date": "2026-05-28",
                "canonical_model_id": "MODEL-OLD",
            }
        ]

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("structures", "accepted_structure_conflict_model_trace"), blockers)

    def test_construction_readiness_accepts_signed_structure_conflict_acceptance(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["structure_conflicts"] = [
            {
                "id": "SC-1",
                "status": "accepted",
                "resolved": False,
                "accepted_by": "Alex Morgan",
                "accepted_date": "2026-05-28",
                "canonical_model_id": "MODEL-FINAL-1",
            }
        ]

        readiness = construction_readiness({"meta": meta})

        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["blockers"])

    def test_construction_readiness_accepts_foundation_and_bridge_with_traceable_coordination(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["foundations"] = [{"id": "F-1", "building_id": "B-1"}]
        meta["foundation_coordination_review"] = {
            "canonical_model_id": "MODEL-FINAL-1",
            "footing_elevations": [{"foundation_id": "F-1", "bottom_elev_ft": 98.0}],
            "utility_clearance_checks": [{"foundation_id": "F-1", "clear": True}],
            "excavation_limits": [{"foundation_id": "F-1", "offset_ft": 5.0}],
        }
        meta["bridge_interfaces"] = [{"id": "BR-IF-1", "bridge_id": "BR-1"}]
        meta["bridge_interface_review"] = {
            "sealed": True,
            "reviewed_by": "Bridge Engineer",
            "review_date": "2026-05-28",
            "canonical_model_id": "MODEL-FINAL-1",
            "grading_interaction_checks": [{"interface_id": "BR-IF-1", "valid": True}],
            "utility_clearance_checks": [{"interface_id": "BR-IF-1", "clear": True}],
        }
        meta["structure_conflicts"] = [{"id": "SC-1", "status": "resolved", "resolved": True}]

        readiness = construction_readiness({"meta": meta})

        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["blockers"])

    def test_construction_readiness_blocks_stale_foundation_and_bridge_review_trace(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }
        meta["foundations"] = [{"id": "F-1", "building_id": "B-1"}]
        meta["foundation_coordination_review"] = {
            "canonical_model_id": "MODEL-OLD",
            "footing_elevations": [{"foundation_id": "F-1", "bottom_elev_ft": 98.0}],
            "utility_clearance_checks": [{"foundation_id": "F-1", "clear": True}],
            "excavation_limits": [{"foundation_id": "F-1", "offset_ft": 5.0}],
        }
        meta["bridge_interfaces"] = [{"id": "BR-IF-1", "bridge_id": "BR-1"}]
        meta["bridge_interface_review"] = {
            "sealed": True,
            "reviewed_by": "Bridge Engineer",
            "review_date": "2026-05-28",
            "canonical_model_id": "MODEL-OLD",
            "grading_interaction_checks": [{"interface_id": "BR-IF-1", "valid": True}],
            "utility_clearance_checks": [{"interface_id": "BR-IF-1", "clear": True}],
        }

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("structures", "foundation_coordination_model_trace"), blockers)
        self.assertIn(("structures", "bridge_interface_review_model_trace"), blockers)

    def test_construction_readiness_can_clear_with_verified_professional_release(self) -> None:
        meta = _production_ready_meta()
        meta["professional_review"] = {
            "status": "released_for_construction",
            "sealed": True,
            "engineer_name": "Alex Morgan",
            "license_number": "TX-123456",
            "review_date": "2026-05-28",
            "jurisdiction": "Test City",
            "license_jurisdiction": "TX",
            "discipline": "civil",
            "review_scope": "civil_site_construction_documents",
            "canonical_model_id": "MODEL-FINAL-1",
        }

        readiness = construction_readiness({"meta": meta})

        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["status"], "construction_ready")
        self.assertFalse(readiness["blockers"])
        self.assertTrue(readiness["evidence"]["professional_release"])

    def test_civil_readiness_blocks_missing_final_model_identity(self) -> None:
        meta = _production_ready_meta()
        meta.pop("canonical_model_id", None)

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("canonical_model", "final_model_identity"), gaps)

    def test_construction_readiness_blocks_missing_final_model_identity(self) -> None:
        meta = _production_ready_meta()
        meta.pop("canonical_model_id", None)

        readiness = construction_readiness({"meta": meta})
        blockers = {(item["area"], item["field"]) for item in readiness["blockers"]}

        self.assertFalse(readiness["ready"])
        self.assertIn(("canonical_model", "final_model_identity"), blockers)

    def test_production_depth_gates_name_every_major_real_world_gap(self) -> None:
        readiness = civil_design_readiness({"meta": _complete_meta()})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertIn(("standards", "design_standards"), gaps)
        self.assertIn(("existing_conditions", "survey_surface"), gaps)
        self.assertIn(("existing_conditions", "gis_layers"), gaps)
        self.assertIn(("existing_conditions", "coordinate_system"), gaps)
        self.assertIn(("hydraulics", "hgl_profile"), gaps)
        self.assertIn(("hydraulics", "detention_routing"), gaps)
        self.assertIn(("grading_detail", "ada_path_checks"), gaps)
        self.assertIn(("cad_interop", "civil3d_landxml"), gaps)
        self.assertIn(("optimization", "optimization_summary"), gaps)

    def test_civil_readiness_blocks_geographic_coordinate_system_for_production(self) -> None:
        meta = _complete_meta()
        meta["survey"] = {"point_count": 8, "source": "survey_points"}
        meta["gis_layers"] = {"parcels": [{}], "easements": [{}], "row": [{}], "existing_utilities": [{}]}
        meta["coordinate_system"] = {"epsg": "EPSG:4326", "units": "degrees", "source": "geojson"}

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("existing_conditions", "coordinate_system"), gaps)

    def test_civil_readiness_blocks_exports_without_canonical_traceability(self) -> None:
        meta = _complete_meta()
        meta["export_audit"] = {
            "ready": True,
            "production_export_ready": False,
            "canonical_id_traceability": {
                "ready": False,
                "orphaned_action_source_ids": ["storm-from-stale-plan"],
            },
        }
        meta["sheet_registry"] = {"sheets": [{"id": "C-100"}]}
        meta["cad_interop"] = {"source": "test", "civil3d": True, "landxml": True}

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("cad_interop", "export_readiness"), gaps)
        self.assertIn(("cad_interop", "canonical_ids"), gaps)

    def test_civil_readiness_blocks_stale_export_audit_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["export_audit"]["canonical_model_id"] = "MODEL-OLD"

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("cad_interop", "export_audit_model_trace"), gaps)

    def test_civil_readiness_blocks_export_audit_without_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["export_audit"].pop("canonical_model_id", None)

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("cad_interop", "export_audit_model_trace"), gaps)

    def test_civil_readiness_blocks_placeholder_or_stale_sheet_registry(self) -> None:
        meta = _production_ready_meta()
        meta["sheet_registry"] = {"source": "placeholder", "sheets": [{"id": "C-100", "title": "Civil Site Plan"}]}

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("cad_interop", "sheet_registry"), gaps)

        meta = _production_ready_meta()
        meta["sheet_registry"] = {"ready": True, "sheets": [{"id": "C-100", "title": "Civil Site Plan", "current": False}]}

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("cad_interop", "sheet_registry"), gaps)

    def test_civil_readiness_blocks_sheet_registry_export_mismatch(self) -> None:
        meta = _production_ready_meta()
        meta["export_audit"]["sheet_registry_matches_outputs"] = False

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("cad_interop", "sheet_registry_consistency"), gaps)

    def test_civil_readiness_blocks_sheet_registry_without_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["sheet_registry"] = {"ready": True, "sheets": [{"id": "C-100", "title": "Civil Site Plan", "current": True}]}

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("cad_interop", "sheet_registry_model_trace"), gaps)

    def test_civil_readiness_blocks_uncommitted_optimization_alternatives(self) -> None:
        meta = _production_ready_meta()
        meta["optimization_summary"]["alternatives"] = [{"name": "A"}, {"name": "B", "geometry_committed": True}]

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("optimization", "committed_alternatives"), gaps)

    def test_civil_readiness_blocks_stale_optimization_alternative_model_trace(self) -> None:
        meta = _production_ready_meta()
        meta["optimization_summary"]["alternatives"][1]["canonical_model_id"] = "MODEL-OLD"

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("optimization", "alternative_model_trace"), gaps)

    def test_civil_readiness_blocks_optimization_without_runner_up(self) -> None:
        meta = _production_ready_meta()
        meta["optimization_summary"]["comparison_summary"] = {"recommended_option_name": "A"}

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("optimization", "alternatives"), gaps)

    def test_hydraulic_depth_blocks_surcharged_backwater_and_concept_proxy(self) -> None:
        meta = _complete_meta()
        meta["storm_pipes"].update(
            {
                "hydraulic_depth_source": "concept_hgl_egl_proxy",
                "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2}],
                "tailwater_elev_ft": 101.0,
                "inlet_capacity_checks": [{"inlet": "INLET-1", "valid": True}],
                "backwater_validation": {
                    "valid": False,
                    "surcharged_segments": [{"segment": "P-1", "max_hgl_above_crown_ft": 0.6}],
                },
                "hydraulic_engine_summary": {
                    "critical_nodes": [{"name": "INLET-1", "surcharge_risk": True}],
                },
            }
        )

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertIn(("hydraulics", "hydraulic_depth_source"), gaps)
        self.assertIn(("hydraulics", "backwater_validation"), gaps)
        self.assertIn(("hydraulics", "node_surcharge"), gaps)

    def test_civil_readiness_blocks_incomplete_hydraulic_depth_evidence(self) -> None:
        meta = _production_ready_meta()
        meta["storm_pipes"]["egl_profile"] = [
            {"station_ft": 0.0, "egl_ft": 98.2, "hydraulic_depth_source": "concept_hgl_egl_proxy"}
        ]
        meta["storm_pipes"]["inlet_capacity_checks"] = [{"inlet": "INLET-1", "spread_ft": 4.0, "bypass_cfs": 0.0}]
        meta["drainage"]["detention_routing"] = [
            {
                "basin": "BASIN-1",
                "routing_source": "concept_detention_design",
                "routing_method": "stage_storage_concept",
            }
        ]

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("hydraulics", "hydraulic_depth_source"), gaps)
        self.assertIn(("hydraulics", "inlet_capacity_validity"), gaps)
        self.assertIn(("hydraulics", "detention_routing"), gaps)

    def test_civil_readiness_blocks_concept_grading_detail_evidence(self) -> None:
        meta = _production_ready_meta()
        meta["grading"]["road_crown_controls"] = [
            {
                "road": "A",
                "control_source": "grade_element",
                "truth_label": "concept road crown control; verify profile and cross-slope against road standard.",
            }
        ]
        meta["grading"]["ada_path_checks"] = [{"path": "ADA-1", "valid": False}]
        meta["grading"]["pad_tie_ins"] = [{"building": "B-1", "valid": False}]
        meta["grading"]["retaining_walls"] = [{"id": "RW-1"}]
        meta["grading"]["wall_tie_in_checks"] = [{"wall_id": "RW-1", "valid": False}]

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertFalse(readiness["production_ready"])
        self.assertIn(("grading_detail", "road_crown_controls"), gaps)
        self.assertIn(("grading_detail", "ada_path_checks"), gaps)
        self.assertIn(("grading_detail", "pad_tie_ins"), gaps)
        self.assertIn(("grading_detail", "wall_tie_in_checks"), gaps)

    def test_build_plan_attaches_civil_design_readiness_without_fake_success(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Readiness Smoke",
                "units": "ft",
                "mode": "site_plan",
                "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
                "site_plan": {"building_width": 40.0, "building_depth": 30.0, "parking_count": 12},
            }
        )
        readiness = plan["meta"].get("civil_design_readiness")
        construction = plan["meta"].get("construction_readiness")
        release_summary = plan["meta"].get("release_readiness_summary")
        sheet_registry = plan["meta"].get("sheet_registry") or []
        export_audit = plan["meta"].get("export_audit") or {}

        self.assertIsInstance(readiness, dict)
        self.assertTrue(plan["meta"].get("canonical_model_id"))
        self.assertTrue(plan["meta"].get("canonical_model_hash"))
        self.assertEqual(sheet_registry[0]["canonical_model_id"], plan["meta"]["canonical_model_id"])
        self.assertEqual(export_audit["canonical_model_id"], plan["meta"]["canonical_model_id"])
        for key in ("truth_audit", "reactive_update_report", "quantities", "cost_estimate"):
            self.assertEqual(plan["meta"][key]["canonical_model_id"], plan["meta"]["canonical_model_id"])
            self.assertEqual(plan["meta"][key]["canonical_model_hash"], plan["meta"]["canonical_model_hash"])
        for result in plan["meta"]["depth_validation"].values():
            self.assertEqual(result["canonical_model_id"], plan["meta"]["canonical_model_id"])
            self.assertEqual(result["canonical_model_hash"], plan["meta"]["canonical_model_hash"])
        self.assertIn("systems", readiness)
        self.assertIn("missing_requirements", readiness)
        self.assertIn(readiness.get("status"), {"ready", "needs_engineering_review", "blocked"})
        self.assertIsInstance(construction, dict)
        self.assertEqual(construction.get("status"), "not_construction_ready")
        self.assertIsInstance(release_summary, dict)
        self.assertEqual(release_summary["version"], "planner_release_readiness_v1")
        self.assertFalse(release_summary["release_ready"])
        self.assertTrue(release_summary["blocker_details"])
        self.assertTrue(release_summary["primary_attention_detail"]["next_action"])


if __name__ == "__main__":
    unittest.main()
