import unittest
from copy import deepcopy

import planner
from backend.planning.runtime import PlannerExecutionContext, RoutingDecision, sanitize_plan
from core.project_manager import ProjectManager


def _drainage_with_targets(selected_name: str = "OUTLET-CANON") -> dict:
    return {
        "success": True,
        "hydrology": {
            "method": "rational_method",
            "drainage_area_sf": 30000.0,
            "intensity_in_hr": 4.0,
            "time_of_concentration_min": 11.0,
            "rainfall_source": "accepted_city_idf_fixture",
            "standard_id": "CITY-STORM-2026",
            "standard_status": "adopted",
            "source_confidence": "accepted_controlled_fixture",
            "assumptions": {"runoff_method": "rational_method", "time_of_concentration_min": 11.0},
        },
        "catchments": [
            {"name": "C-INLET-1", "area_sf": 12000.0, "runoff_c": 0.85, "time_of_concentration_min": 11.0},
            {"name": "C-INLET-2", "area_sf": 18000.0, "runoff_c": 0.85, "time_of_concentration_min": 11.0},
        ],
        "structures": [
            {
                "name": "INLET-1",
                "object_type": "inlet",
                "structure_type": "area_inlet",
                "x": 24.0,
                "y": 42.0,
                "z": 101.0,
                "contributing_area_sf": 12000.0,
                "estimated_flow_cfs": 0.9,
                "capacity_cfs": 10.0,
                "gutter_spread_limit_ft": 8.0,
                "target_name": selected_name,
                "tributary_basin_name": "BASIN-CANON",
            },
            {
                "name": "INLET-2",
                "object_type": "inlet",
                "structure_type": "area_inlet",
                "x": 64.0,
                "y": 48.0,
                "z": 100.5,
                "contributing_area_sf": 18000.0,
                "estimated_flow_cfs": 1.25,
                "capacity_cfs": 10.0,
                "gutter_spread_limit_ft": 8.0,
                "target_name": selected_name,
                "tributary_basin_name": "BASIN-CANON",
            },
        ],
        "basins": [
            {
                "name": "BASIN-CANON",
                "target_name": selected_name,
                "engineering_role": "primary_detention",
                "exportable": True,
                "boundary_points": [[120.0, 8.0], [160.0, 8.0], [160.0, 42.0], [120.0, 42.0]],
                "area_sf": 1360.0,
                "bottom_area_sf": 900.0,
                "top_of_bank_area_sf": 1360.0,
                "bottom_elev_ft": 95.0,
                "top_of_bank_elev_ft": 100.0,
                "detention_design": {
                    "required_storage_cf": 3200.0,
                    "provided_storage_cf": 3600.0,
                    "depth_ft": 4.0,
                    "release_cfs": 0.35,
                    "drawdown_hours": 18.0,
                    "adequacy_status": "adequate",
                    "routing_source": "hydrograph_engine",
                    "routing_method": "stage_storage_hydrograph",
                    "peak_inflow_cfs": 2.15,
                    "stage_storage": [
                        {"elevation_ft": 95.0, "storage_cf": 0.0},
                        {"elevation_ft": 98.0, "storage_cf": 1800.0},
                        {"elevation_ft": 100.0, "storage_cf": 3600.0},
                    ],
                    "outlet_structure": {
                        "type": "orifice",
                        "invert_elev_ft": 94.0,
                        "release_cfs": 0.35,
                        "source": "approved_outlet_fixture",
                    },
                    "overflow_elev_ft": 100.5,
                    "overflow_spillway": {
                        "crest_elev_ft": 100.5,
                        "capacity_cfs": 5.0,
                        "required_capacity_cfs": 3.0,
                        "source": "approved_spillway_fixture",
                    },
                },
                "outlet_structure": {
                    "name": selected_name,
                    "x": 140.0,
                    "y": 18.0,
                    "rim_elev_ft": 97.0,
                    "invert_out_ft": 94.0,
                },
            },
            {
                "name": "BASIN-STALE",
                "target_name": "OUTLET-STALE",
                "engineering_role": "primary_detention",
                "exportable": True,
                "boundary_points": [[220.0, 8.0], [260.0, 8.0], [260.0, 42.0], [220.0, 42.0]],
                "area_sf": 1360.0,
                "detention_design": {"required_storage_cf": 3200.0, "provided_storage_cf": 3600.0},
                "outlet_structure": {"name": "OUTLET-STALE", "x": 240.0, "y": 18.0, "invert_out_ft": 94.0},
            },
        ],
        "coordination": {
            "preferred_outfall": {"target_name": selected_name, "x": 140.0, "y": 18.0, "z": 94.0},
        },
        "surface_guidance": {
            "preferred_targets": [{"target_name": selected_name, "x": 140.0, "y": 18.0, "z": 94.0}],
            "surface_source": "terrain",
        },
        "surface_controls": {
            "primary_low_point": {"x": 140.0, "y": 18.0, "z": 94.0},
            "source": "accepted_survey_control_fixture",
            "accepted_control": True,
        },
    }


def _run_storm_stage(project: object, manager: ProjectManager) -> PlannerExecutionContext:
    ctx = PlannerExecutionContext(
        parsed={"project_name": "Storm Hardening", "drainage": {}},
        manager=manager,
        route=RoutingDecision(path="model_first", reasons=[]),
    )
    planner._run_storm_pipe_stage(ctx, {"runoff_c": 0.85, "intensity_in_hr": 4.0})
    return ctx


class EngineHardeningStormTests(unittest.TestCase):
    def test_storm_stage_reads_canonical_drainage_before_stale_cache(self) -> None:
        manager = ProjectManager()
        project = manager.project
        project.name = "Canonical Storm Handoff"
        project.meta["drainage_summary"] = object()
        project.meta["drainage_canonical"] = _drainage_with_targets("OUTLET-CANON")
        manager.latest_outputs["drainage"] = _drainage_with_targets("OUTLET-STALE")

        ctx = _run_storm_stage(project, manager)
        storm = project.meta["storm_pipe_summary"]

        self.assertTrue(ctx.stage_results[-1].success)
        self.assertEqual(storm["explain"]["selected_outfall_name"], "OUTLET-CANON")
        self.assertEqual(storm["selected_outfall"], "OUTLET-CANON")
        self.assertEqual(storm["target_outfall_name"], "OUTLET-CANON")
        self.assertGreater(storm["total_system_flow_cfs"], 0.0)
        self.assertGreater(storm["total_system_capacity_cfs"], 0.0)
        self.assertTrue(storm["segments"])

    def test_storm_summary_preserves_tributary_and_cumulative_context(self) -> None:
        manager = ProjectManager()
        project = manager.project
        project.meta["drainage_summary"] = object()
        project.meta["drainage_canonical"] = _drainage_with_targets()

        _run_storm_stage(project, manager)
        storm = project.meta["storm_pipe_summary"]
        segments = storm["segments"]
        nodes = storm["nodes"]

        self.assertTrue(any(float(seg.get("tributary_area_sf", 0.0)) > 0.0 for seg in segments))
        self.assertTrue(any(float(seg.get("tributary_runoff_cfs", 0.0)) > 0.0 for seg in segments))
        self.assertTrue(any(seg.get("tributary_basin_names") for seg in segments))
        self.assertTrue(any(float(seg.get("upstream_cumulative_area_sf", 0.0)) > 0.0 for seg in segments))
        self.assertTrue(any(float(seg.get("upstream_cumulative_runoff_cfs", 0.0)) > 0.0 for seg in segments))
        self.assertTrue(any(float(node.get("upstream_cumulative_area_sf", 0.0)) > 0.0 for node in nodes))
        self.assertGreater(storm["hydraulic_summary"]["system_tributary_area_sf"], 0.0)
        self.assertGreater(storm["hydraulic_summary"]["system_tributary_runoff_cfs"], 0.0)
        self.assertEqual(project.meta["drainage_canonical"]["hydrology"]["standard_status"], "adopted")
        self.assertEqual(project.meta["drainage_canonical"]["hydrology"]["time_of_concentration_min"], 11.0)
        self.assertTrue(storm["graph_validation"])
        self.assertTrue(storm["hydraulic_validation"])
        self.assertIn("controlling_segment", storm)
        self.assertIn("max_capacity_ratio", storm)

    def test_storm_relative_inverts_respect_minimum_cover_before_hgl_review(self) -> None:
        manager = ProjectManager()
        project = manager.project
        project.meta["drainage_summary"] = object()
        project.meta["drainage_canonical"] = _drainage_with_targets()

        _run_storm_stage(project, manager)
        storm = project.meta["storm_pipe_summary"]
        summary = storm["hydraulic_engine_summary"]

        self.assertEqual(summary["surcharge_node_count"], 0)
        for node in storm["nodes"]:
            rim = float(node.get("rim_elev_ft", 0.0))
            invert = float(node.get("invert_elev_ft", 0.0))
            self.assertGreaterEqual(rim - invert, 3.0)

    def test_missing_drainage_outfall_returns_structured_failure(self) -> None:
        manager = ProjectManager()
        project = manager.project
        project.meta["drainage_summary"] = object()
        project.meta["drainage_canonical"] = {
            "success": True,
            "structures": [
                {
                    "name": "INLET-1",
                    "object_type": "inlet",
                    "x": 10.0,
                    "y": 10.0,
                    "z": 100.0,
                    "contributing_area_sf": 1000.0,
                    "estimated_flow_cfs": 0.1,
                }
            ],
            "basins": [],
            "coordination": {},
        }

        ctx = _run_storm_stage(project, manager)
        storm = project.meta["storm_pipe_summary"]

        self.assertFalse(ctx.stage_results[-1].success)
        self.assertFalse(storm["success"])
        self.assertEqual(storm["source_detail"], "missing_drainage_outfall")
        self.assertIn("missing_requirements", storm)
        self.assertIn("drainage.coordination.preferred_outfall", storm["missing_requirements"]["missing_fields"])

    def test_post_reroute_recompute_preserves_storm_truth_fields(self) -> None:
        manager = ProjectManager()
        project = manager.project
        project.meta["drainage_summary"] = object()
        project.meta["drainage_canonical"] = _drainage_with_targets()
        _run_storm_stage(project, manager)
        before = deepcopy(project.meta["storm_pipe_summary"])

        planner._recompute_storm_summary(project, manager)
        after = project.meta["storm_pipe_summary"]

        self.assertEqual(after["selected_outfall"], before["selected_outfall"])
        self.assertEqual(after["target_outfall_name"], before["target_outfall_name"])
        self.assertTrue(after["segments"])
        self.assertTrue(any(float(seg.get("tributary_area_sf", 0.0)) > 0.0 for seg in after["segments"]))
        self.assertTrue(any(float(seg.get("upstream_cumulative_area_sf", 0.0)) > 0.0 for seg in after["segments"]))
        self.assertIn("controlling_segment", after)
        self.assertIn("max_capacity_ratio", after)

    def test_hydraulic_validation_fails_explicit_backwater_surcharge(self) -> None:
        validation = planner._validate_storm_hydraulics(
            {
                "segments": [
                    {
                        "pipe": "P-1",
                        "from": "INLET-1",
                        "to": "OUTLET-1",
                        "flow_cfs": 1.0,
                        "capacity_cfs": 3.0,
                        "capacity_ratio": 0.33,
                        "slope_ft_ft": 0.01,
                        "contributing_area_ac": 0.5,
                    }
                ],
                "backwater_validation": {
                    "valid": False,
                    "max_tailwater_surcharge_ft": 1.2,
                    "surcharged_segments": [{"segment": "P-1", "max_hgl_above_crown_ft": 0.4}],
                },
            }
        )

        self.assertFalse(validation["valid"])
        self.assertEqual(validation["backwater_failures"][0]["reason"], "tailwater_surcharges_pipe_crown")

    def test_hydraulic_validation_fails_node_surcharge_from_engine_summary(self) -> None:
        validation = planner._validate_storm_hydraulics(
            {
                "segments": [
                    {
                        "pipe": "P-1",
                        "from": "INLET-1",
                        "to": "OUTLET-1",
                        "flow_cfs": 1.0,
                        "capacity_cfs": 3.0,
                        "capacity_ratio": 0.33,
                        "slope_ft_ft": 0.01,
                        "contributing_area_ac": 0.5,
                    }
                ],
                "hydraulic_engine_summary": {
                    "critical_nodes": [
                        {"name": "INLET-1", "surcharge_risk": True, "max_hgl_ft": 102.2, "rim_elev_ft": 101.0}
                    ]
                },
            }
        )

        self.assertFalse(validation["valid"])
        self.assertEqual(validation["surcharge_failures"][0]["reason"], "node_hgl_exceeds_rim_threshold")

    def test_final_plan_sanitizer_preserves_canonical_storm_summary(self) -> None:
        storm = {
            "success": True,
            "source": "engine",
            "hydraulic_source": "engine",
            "source_detail": "storm_network_engine+hydraulic_engine",
            "pipe_count": 1,
            "segments": [{"pipe": "P-1", "tributary_area_sf": 12000.0, "upstream_cumulative_area_sf": 12000.0}],
            "nodes": [{"name": "OUTLET-CANON", "node_type": "basin_connection"}],
            "selected_outfall": "OUTLET-CANON",
            "target_outfall_name": "OUTLET-CANON",
            "target_outfall": {"target_name": "OUTLET-CANON"},
            "outfall_target_metadata": {"target_name": "OUTLET-CANON"},
            "hydraulic_summary": {"system_tributary_area_sf": 12000.0},
            "graph_validation": {"valid": True},
            "hydraulic_validation": {"valid": True},
            "missing_data_segments": [],
            "controlling_segment": "P-1",
            "max_capacity_ratio": 0.42,
            "stats": {"selected_outfall_name": "OUTLET-CANON"},
        }

        plan = sanitize_plan(
            {
                "project_name": "Sanitize Storm",
                "units": "ft",
                "actions": [],
                "assumptions": [],
                "meta": {"storm_pipes": storm},
            }
        )
        clean = plan["meta"]["storm_pipes"]

        self.assertEqual(clean["selected_outfall"], "OUTLET-CANON")
        self.assertTrue(clean["segments"])
        self.assertTrue(clean["nodes"])
        self.assertEqual(clean["hydraulic_summary"]["system_tributary_area_sf"], 12000.0)


if __name__ == "__main__":
    unittest.main()
