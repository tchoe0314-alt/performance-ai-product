import unittest
from types import SimpleNamespace

import planner
from backend.planning.production_depth import (
    build_cad_interop_metadata,
    build_grading_detail_controls,
    build_optimization_alternatives,
    enrich_drainage_production_depth,
    enrich_storm_production_depth,
    enrich_water_production_depth,
)
from core.civil_design import civil_design_readiness


class ProductionDepthArtifactTests(unittest.TestCase):
    def test_drainage_adds_detention_routing_and_stage_storage(self) -> None:
        drainage = {
            "success": True,
            "coordination": {"preferred_outfall": {"name": "OUTFALL-1", "x": 120.0, "y": 20.0}},
            "basins": [
                {
                    "name": "BASIN-1",
                    "x": 20.0,
                    "y": 10.0,
                    "detention_design": {
                        "required_storage_cf": 4200.0,
                        "provided_storage_cf": 5100.0,
                        "release_cfs": 1.1,
                        "drawdown_hours": 18.0,
                        "bottom_elev_ft": 96.0,
                        "normal_pool_elev_ft": 99.0,
                        "top_of_bank_elev_ft": 101.0,
                        "overflow_elev_ft": 100.5,
                    },
                }
            ],
        }

        enriched = enrich_drainage_production_depth(drainage)

        self.assertEqual(enriched["detention_routing"][0]["basin"], "BASIN-1")
        self.assertEqual(enriched["detention_routing"][0]["status"], "adequate")
        self.assertGreaterEqual(len(enriched["stage_storage"]), 3)
        self.assertTrue(enriched["overflow_analysis"]["valid"])
        self.assertEqual(enriched["overflow_paths"][0]["basin"], "BASIN-1")

    def test_drainage_computes_production_detention_outlet_drawdown_and_overflow_capacity(self) -> None:
        drainage = {
            "success": True,
            "coordination": {"preferred_outfall": {"name": "OUTFALL-1", "x": 120.0, "y": 20.0}},
            "basins": [
                {
                    "name": "BASIN-1",
                    "x": 20.0,
                    "y": 10.0,
                    "source": "imported_detention_design",
                    "detention_design": {
                        "routing_source": "hydrograph_engine",
                        "required_storage_cf": 5400.0,
                        "provided_storage_cf": 7200.0,
                        "peak_inflow_cfs": 5.0,
                        "release_cfs": 1.0,
                        "bottom_elev_ft": 96.0,
                        "normal_pool_elev_ft": 99.0,
                        "top_of_bank_elev_ft": 101.0,
                        "overflow_elev_ft": 100.5,
                        "outlet_structure": {
                            "type": "orifice",
                            "invert_elev_ft": 96.2,
                            "diameter_in": 8.0,
                            "release_cfs": 1.0,
                            "source": "approved_outlet_fixture",
                        },
                        "overflow_spillway": {
                            "crest_elev_ft": 100.5,
                            "capacity_cfs": 6.0,
                            "required_capacity_cfs": 4.0,
                            "source": "approved_spillway_fixture",
                        },
                    },
                }
            ],
        }

        enriched = enrich_drainage_production_depth(drainage)
        route = enriched["detention_routing"][0]
        overflow = enriched["overflow_paths"][0]

        self.assertEqual(route["routing_source"], "hydrograph_engine")
        self.assertEqual(route["routing_method"], "stage_storage_outlet_drawdown")
        self.assertEqual(route["drawdown_source"], "computed_storage_release")
        self.assertAlmostEqual(route["drawdown_hours"], 2.0)
        self.assertEqual(route["outlet"]["type"], "orifice")
        self.assertEqual(route["outlet"]["source"], "approved_outlet_fixture")
        self.assertEqual(route["storage_margin_cf"], 1800.0)
        self.assertTrue(enriched["overflow_analysis"]["production_valid"])
        self.assertTrue(overflow["capacity_valid"])
        self.assertEqual(overflow["capacity_status"], "adequate")
        self.assertEqual(overflow["capacity_margin_cfs"], 2.0)

    def test_storm_adds_hgl_egl_tailwater_and_inlet_checks(self) -> None:
        storm = {
            "success": True,
            "hydraulic_source": "engine",
            "segments": [
                {
                    "pipe": "P-1",
                    "path": [[0.0, 0.0], [80.0, 0.0]],
                    "diameter_in": 18.0,
                    "flow_cfs": 1.4,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.35,
                    "velocity_fps": 3.0,
                    "start_invert_ft": 97.0,
                    "end_invert_ft": 96.2,
                    "tributary_area_sf": 10000.0,
                }
            ],
            "target_outfall": {"name": "BASIN-1", "z": 96.0},
        }
        drainage = {"structures": [{"name": "INLET-1", "estimated_flow_cfs": 1.4}]}

        enriched = enrich_storm_production_depth(storm, drainage)

        self.assertTrue(enriched["hgl_profile"])
        self.assertTrue(enriched["egl_profile"])
        self.assertEqual(enriched["tailwater_elev_ft"], 96.0)
        self.assertEqual(enriched["inlet_capacity_checks"][0]["inlet"], "INLET-1")
        self.assertEqual(enriched["inlet_capacity_checks"][0]["capacity_source"], "storm_inlet_engine_default")
        self.assertIn("capture_efficiency", enriched["inlet_capacity_checks"][0])
        self.assertEqual(enriched["controlling_segment"], "P-1")

    def test_storm_depth_uses_hydraulic_engine_for_capacity_velocity_and_hgl(self) -> None:
        storm = {
            "success": True,
            "segments": [
                {
                    "pipe": "P-ENGINE",
                    "from": "INLET-1",
                    "to": "OUTLET-1",
                    "path": [[0.0, 0.0], [100.0, 0.0]],
                    "diameter_in": 18.0,
                    "flow_cfs": 2.0,
                    "start_invert_ft": 98.0,
                    "end_invert_ft": 97.0,
                    "tributary_area_sf": 12000.0,
                }
            ],
        }

        enriched = enrich_storm_production_depth(storm, {})
        segment = enriched["segments"][0]

        self.assertEqual(enriched["hydraulic_source"], "engine")
        self.assertEqual(segment["hydraulic_depth_source"], "storm_hydraulic_engine")
        self.assertGreater(segment["capacity_cfs"], 0.0)
        self.assertGreater(segment["velocity_fps"], 0.0)
        self.assertTrue(enriched["hydraulic_engine_summary"]["truth_label"])

    def test_storm_backwater_validation_blocks_tailwater_surcharged_pipe(self) -> None:
        storm = {
            "success": True,
            "hydraulic_source": "engine",
            "segments": [
                {
                    "pipe": "P-BACKWATER",
                    "path": [[0.0, 0.0], [80.0, 0.0]],
                    "diameter_in": 12.0,
                    "flow_cfs": 1.0,
                    "capacity_cfs": 3.0,
                    "capacity_ratio": 0.33,
                    "velocity_fps": 3.0,
                    "start_invert_ft": 97.0,
                    "end_invert_ft": 96.5,
                    "tributary_area_sf": 10000.0,
                }
            ],
            "target_outfall": {"name": "BASIN-1", "z": 99.0},
        }

        enriched = enrich_storm_production_depth(storm, {})

        self.assertFalse(enriched["backwater_validation"]["valid"])
        self.assertTrue(enriched["backwater_validation"]["tailwater_controls_hgl"])
        self.assertEqual(enriched["backwater_validation"]["surcharged_segments"][0]["segment"], "P-BACKWATER")

    def test_water_depth_validates_pressure_fire_flow_hydrants_and_velocity(self) -> None:
        utilities = {
            "source_pressure_psi": 72.0,
            "source_node": "SRC",
            "available_fire_flow_gpm": 1600.0,
            "fire_flow_demand_gpm": 1250.0,
            "hydrants": [
                {"name": "H-1", "x": 0.0, "y": 0.0},
                {"name": "H-2", "x": 280.0, "y": 0.0},
            ],
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "W-1",
                        "system_type": "water",
                        "start_node": "SRC",
                        "end_node": "A",
                        "route_points": [[0.0, 0.0], [220.0, 0.0]],
                        "diameter_in": 8.0,
                        "flow_gpm": 450.0,
                    },
                    {
                        "name": "W-2",
                        "system_type": "water",
                        "start_node": "A",
                        "end_node": "SRC",
                        "route_points": [[220.0, 0.0], [0.0, 0.0]],
                        "diameter_in": 8.0,
                        "flow_gpm": 300.0,
                    },
                ],
            },
        }

        enriched = enrich_water_production_depth(utilities)

        self.assertTrue(enriched["pressure_validation"]["valid"])
        self.assertTrue(enriched["fire_flow_validation"]["valid"])
        self.assertTrue(enriched["hydrant_spacing_validation"]["valid"])
        self.assertTrue(enriched["looped"])
        self.assertEqual(enriched["water_depth_status"], "ready")
        self.assertEqual(enriched["velocity_checks"][0]["segment"], "W-1")
        self.assertEqual(enriched["pressure_validation"]["source"], "water_pressure_graph")
        self.assertGreater(enriched["pressure_validation"]["residual_pressure_margin_psi"], 0.0)
        self.assertEqual(enriched["fire_flow_validation"]["source"], "water_fire_flow_check")
        self.assertEqual(enriched["fire_flow_validation"]["fire_flow_margin_gpm"], 350.0)

    def test_water_depth_blocks_missing_pressure_and_fire_flow_inputs(self) -> None:
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "W-MISSING",
                        "system_type": "water",
                        "route_points": [[0.0, 0.0], [100.0, 0.0]],
                        "diameter_in": 8.0,
                    }
                ],
            }
        }

        enriched = enrich_water_production_depth(utilities)

        self.assertFalse(enriched["pressure_validation"]["valid"])
        self.assertIn("pressure_inputs_missing", enriched["water_depth_blockers"])
        self.assertIn("fire_flow_not_validated", enriched["water_depth_blockers"])
        self.assertEqual(
            {item["code"] for item in enriched["water_depth_blocker_details"]},
            set(enriched["water_depth_blockers"]),
        )
        self.assertEqual(enriched["water_depth_status"], "blocked_missing_inputs")

    def test_grading_detail_controls_are_derived_from_grade_elements(self) -> None:
        controls = build_grading_detail_controls(
            grade_elements=[
                SimpleNamespace(kind="road", name="Road A", slope_x=0.01, slope_y=0.02, width=24.0, depth=120.0),
                SimpleNamespace(kind="walk", name="ADA-1", slope_x=0.01, slope_y=0.01, width=5.0, depth=80.0),
                SimpleNamespace(kind="pad", name="Building Pad", base_elev=102.0, slope_x=0.01, slope_y=0.0, transition_zone=8.0),
            ],
            derived_action_stats={"proposed_contour_count": 2},
            downhill_vector={"dx": 0.7, "dy": -0.7},
            existing_high_points=[{"x": 0.0, "y": 10.0, "z": 104.0}],
            existing_low_points=[{"x": 10.0, "y": 0.0, "z": 98.0}],
            proposed_range_ft=6.0,
        )

        self.assertEqual(controls["road_crown_controls"][0]["road"], "Road A")
        self.assertEqual(controls["ada_path_checks"][0]["path"], "ADA-1")
        self.assertEqual(controls["pad_tie_ins"][0]["building"], "Building Pad")
        self.assertTrue(controls["contours"])

    def test_cad_interop_metadata_is_truthful_about_dxf_vs_civil3d(self) -> None:
        plan = {
            "meta": {
                "sheet_registry": [{"sheet_id": "C-100"}],
                "export_audit": {"ready": True},
                "grading": {"success": True},
                "storm_pipes": {"success": True},
            }
        }

        cad = build_cad_interop_metadata(plan)

        self.assertTrue(cad["dxf"])
        self.assertFalse(cad["civil3d"])
        self.assertIn("civil3d_landxml_contract_not_implemented", cad["contract_status"])
        checks = {item["format"]: item for item in cad["compatibility_checks"]}
        self.assertEqual(checks["dxf"]["status"], "audited_review_ready")
        self.assertEqual(checks["landxml"]["status"], "pipe_network_contract_review_ready_not_civil3d_verified")
        self.assertEqual(checks["civil3d"]["status"], "not_implemented_not_verified")
        self.assertEqual(checks["dwg"]["status"], "unsupported_no_writer")
        self.assertEqual(cad["unsupported_formats"], ["civil3d", "dwg"])

    def test_baseline_optimization_recommendations_do_not_fake_production_ready(self) -> None:
        summary = build_optimization_alternatives(
            {
                "overall_score": 80.0,
                "component_scores": {"grading": 82.0, "drainage": 78.0},
                "metrics": {"earthwork_net_cf": 1200.0, "total_linear_utility_ft": 900.0},
                "recommendations": ["Refine grading."],
            }
        )
        meta = {
            "optimization_summary": summary,
            "export_audit": {"ready": True},
            "sheet_registry": {"sheets": [{"id": "C-100"}]},
            "cad_interop": build_cad_interop_metadata({"meta": {"export_audit": {"ready": True}, "sheet_registry": [{"id": "C-100"}]}}),
        }

        readiness = civil_design_readiness({"meta": meta})
        gaps = {(item["area"], item["field"]) for item in readiness["production_blockers"]}

        self.assertIn(("optimization", "committed_alternatives"), gaps)
        self.assertIn(("cad_interop", "civil3d_landxml"), gaps)

    def test_assisted_site_smoke_produces_coordinated_canonical_engineering_truth(self) -> None:
        plan = planner.build_plan(
            {
                "project_name": "Engine Readiness Smoke",
                "units": "ft",
                "mode": "site_plan",
                "assisted": True,
                "lot": {"x": 0.0, "y": 0.0, "w": 520.0, "h": 420.0},
                "site_plan": {
                    "building_width": 110.0,
                    "building_depth": 58.0,
                    "parking_count": 90,
                    "building_count": 3,
                },
                "drainage": {"runoff_c": 0.85, "intensity_in_hr": 4.0},
                "project_type": "mixed_use",
            }
        )
        meta = plan.get("meta") or {}
        grading = meta.get("grading") or {}
        storm = meta.get("storm_pipes") or {}
        drainage = meta.get("drainage") or {}
        sanitary = meta.get("sanitary") or {}
        readiness = meta.get("civil_design_readiness") or {}

        self.assertTrue(grading.get("success"))
        self.assertTrue(grading.get("road_crown_controls"))
        self.assertTrue(grading.get("curb_gutter_controls"))
        self.assertTrue(grading.get("ada_path_checks"))
        self.assertTrue(grading.get("pad_tie_ins"))
        self.assertTrue(grading.get("contours"))
        self.assertTrue(drainage.get("detention_routing"))
        self.assertTrue(storm.get("hgl_profile"))
        self.assertTrue(storm.get("egl_profile"))
        self.assertTrue(storm.get("inlet_capacity_checks"))
        self.assertTrue(sanitary.get("success"))
        self.assertFalse((meta.get("coordination") or {}).get("unresolved_conflicts") or [])
        self.assertFalse(readiness.get("critical_blockers") or [])
        self.assertEqual(readiness.get("status"), "needs_engineering_review")
        self.assertFalse(readiness.get("production_ready"))


if __name__ == "__main__":
    unittest.main()
