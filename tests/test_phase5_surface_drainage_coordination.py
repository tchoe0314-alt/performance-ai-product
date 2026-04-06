import unittest

import planner
from engines.storm.hydraulic_engine import analyze_storm_hydraulics
from engines.storm.storm_network_engine import StormNetworkEngine, build_storm_network
from engines.storm.basin_connection import BasinConnectionEngine
from engines.storm.storm_types import (
    BasinConnectionRequest,
    HydraulicAnalysisRequest,
    StormBasin,
    StormCatchment,
    StormInlet,
    StormNetworkRequest,
    StormNode,
    StormNodeType,
    StormPoint,
)


class Phase5SurfaceDrainageCoordinationTests(unittest.TestCase):
    def test_drainage_engine_carries_basin_runoff_into_inlet_context(self) -> None:
        from engines.drainage_engine import DrainageEngine, HydraulicInputs
        from engines.surface_engine import GridSurface

        surface = GridSurface(
            x_min=0.0,
            y_min=0.0,
            x_max=40.0,
            y_max=40.0,
            cell_size=10.0,
            ncols=5,
            nrows=5,
            values=[
                [104.0, 103.0, 102.0, 101.0, 100.0],
                [103.0, 102.0, 101.0, 100.0, 99.0],
                [102.0, 101.0, 100.0, 99.0, 98.0],
                [101.0, 100.0, 99.0, 98.0, 97.0],
                [100.0, 99.0, 98.0, 97.0, 96.0],
            ],
        )
        engine = DrainageEngine(surface)
        engine.add_pond_target("POND-1", 40.0, 0.0, radius=8.0)

        summary = engine.design_network(
            mode=DrainageEngine.ASSISTED_MODE,
            hydraulic=HydraulicInputs(runoff_c=0.85, intensity_in_hr=4.0, min_pipe_slope=0.003),
            inlet_min_spacing=5.0,
            max_inlets=4,
            sample_step=1,
        )

        self.assertTrue(summary.success)
        self.assertTrue(summary.basin_records)
        self.assertTrue(summary.inlet_records)
        self.assertTrue(any((record.estimated_runoff_cfs or 0.0) > 0.0 for record in summary.basin_records))
        self.assertTrue(any(safe_name for safe_name in [getattr(record.inlet, "tributary_basin_name", None) for record in summary.inlet_records]))
        self.assertTrue(all((record.inlet.estimated_flow_cfs or 0.0) > 0.0 for record in summary.inlet_records))

    def test_inlet_selection_prefers_stronger_basin_runoff_context(self) -> None:
        from engines.drainage_engine import DrainageEngine, HydraulicInputs, BasinRecord
        from engines.surface_engine import GridSurface

        surface = GridSurface(
            x_min=0.0,
            y_min=0.0,
            x_max=40.0,
            y_max=40.0,
            cell_size=10.0,
            ncols=5,
            nrows=5,
            values=[
                [105.0, 104.0, 103.0, 102.0, 101.0],
                [104.0, 103.0, 102.0, 101.0, 100.0],
                [103.0, 102.0, 101.0, 100.0, 99.0],
                [102.0, 101.0, 100.0, 99.0, 98.0],
                [101.0, 100.0, 99.0, 98.0, 97.0],
            ],
        )
        engine = DrainageEngine(surface)
        hydraulic = HydraulicInputs(runoff_c=0.85, intensity_in_hr=4.0, min_pipe_slope=0.003)
        basin_records = [
            BasinRecord(
                sink=(4, 4),
                sink_name="SINK_BIG",
                area_sf=2400.0,
                contributing_cells=24,
                centroid_xy=(40.0, 40.0),
                target_name="POND-1",
                estimated_runoff_cfs=0.19,
            ),
            BasinRecord(
                sink=(0, 4),
                sink_name="SINK_SMALL",
                area_sf=100.0,
                contributing_cells=1,
                centroid_xy=(40.0, 0.0),
                target_name="POND-1",
                estimated_runoff_cfs=0.03,
            ),
        ]

        inlets = engine.place_inlets(
            basin_records=basin_records,
            hydraulic=hydraulic,
            min_spacing=5.0,
            max_inlets=1,
            use_flow_accumulation=True,
            min_contributing_cells=1,
            min_slope=0.001,
        )

        self.assertEqual(len(inlets), 1)
        self.assertEqual(inlets[0].tributary_basin_name, "SINK_BIG")
        self.assertGreater(inlets[0].estimated_flow_cfs or 0.0, 0.1)

    def test_drainage_export_validation_requires_surface_driven_topology(self) -> None:
        project = planner.ProjectModel(
            name="Drainage Export Gate",
            units="ft",
        )
        project.meta["grading_summary"] = {
            "success": True,
            "fallback_used": False,
            "existing_surface": {"nrows": 5, "ncols": 5},
            "proposed_surface": {"nrows": 5, "ncols": 5},
            "stats": {"proposed_contour_count": 3, "spot_grade_count": 2, "flow_arrow_count": 1},
        }
        project.meta["drainage_canonical"] = {
            "success": True,
            "source": "drainage_engine",
            "structures": [{"name": "INLET-1", "x": 10.0, "y": 10.0}],
            "basins": [{"id": "BASIN-1", "name": "BASIN-1", "engineering_role": "primary_detention", "exportable": True}],
            "stats": {"low_point_count": 0, "flow_path_count": 0},
        }
        project.meta["storm_pipe_summary"] = {
            "segments": [{"name": "PIPE-1"}],
            "graph_validation": {"valid": True},
            "hydraulic_validation": {"valid": True},
            "missing_data_segments": [],
        }

        validation = planner._drainage_export_validation(project)

        self.assertFalse(validation.get("ready"))
        self.assertIn("drainage_low_points_missing", validation.get("reasons", []))
        self.assertIn("drainage_flow_paths_missing", validation.get("reasons", []))

    def test_drainage_and_storm_export_validation_block_inadequate_basin_design(self) -> None:
        project = planner.ProjectModel(name="Basin Adequacy Gate", units="ft")
        project.meta["grading_summary"] = {
            "success": True,
            "fallback_used": False,
            "existing_surface": {"nrows": 5, "ncols": 5},
            "proposed_surface": {"nrows": 5, "ncols": 5},
            "stats": {"proposed_contour_count": 3, "spot_grade_count": 2, "flow_arrow_count": 1},
            "surface_controls": {
                "has_primary_drainage_direction": True,
                "primary_low_point": {"x": 10.0, "y": 10.0, "z": 95.0},
            },
        }
        project.meta["drainage_canonical"] = {
            "success": True,
            "source": "drainage_engine",
            "surface_guidance": {"downhill_vector": {"dx": 1.0, "dy": -1.0}},
            "structures": [{"name": "INLET-1", "x": 10.0, "y": 10.0}],
            "basins": [
                {
                    "id": "BASIN-1",
                    "name": "BASIN-1",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]],
                    "detention_design": {"adequacy_status": "deficient"},
                    "overflow_spillway": {"assumed_capacity_cfs": 0.0},
                }
            ],
            "stats": {
                "low_point_count": 1,
                "flow_path_count": 1,
                "total_contributing_area_sf": 1000.0,
                "total_estimated_inlet_flow_cfs": 0.2,
                "total_basin_runoff_cfs": 0.3,
            },
        }
        project.meta["storm_pipe_summary"] = {
            "segments": [{"name": "PIPE-1"}],
            "graph_validation": {"valid": True},
            "hydraulic_validation": {"valid": True},
            "missing_data_segments": [],
            "explain": {"implied_target_used": False},
        }

        drainage_validation = planner._drainage_export_validation(project)
        storm_validation = planner._storm_export_validation(project)

        self.assertFalse(drainage_validation.get("ready"))
        self.assertIn("primary_detention_inadequate", drainage_validation.get("reasons", []))
        self.assertIn("primary_detention_overflow_missing", drainage_validation.get("reasons", []))
        self.assertFalse(storm_validation.get("ready"))
        self.assertIn("primary_detention_inadequate", storm_validation.get("reasons", []))

    def test_drainage_and_storm_export_validation_block_weak_basin_geometry(self) -> None:
        project = planner.ProjectModel(name="Weak Basin Geometry")
        project.meta["grading_summary"] = {
            "success": True,
            "fallback_used": False,
            "existing_surface": {"nrows": 5, "ncols": 5},
            "proposed_surface": {"nrows": 5, "ncols": 5},
            "stats": {"proposed_contour_count": 3, "spot_grade_count": 2, "flow_arrow_count": 1},
            "surface_controls": {
                "has_primary_drainage_direction": True,
                "primary_low_point": {"x": 10.0, "y": 10.0, "z": 95.0},
            },
        }
        project.meta["drainage_canonical"] = {
            "success": True,
            "source": "drainage_engine",
            "surface_guidance": {"downhill_vector": {"dx": 1.0, "dy": -1.0}},
            "structures": [{"name": "INLET-1", "x": 10.0, "y": 10.0}],
            "basins": [
                {
                    "id": "BASIN-1",
                    "name": "BASIN-1",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]],
                    "detention_design": {"adequacy_status": "adequate"},
                    "geometry_quality": {"has_bottom": True, "footprint_consistency_ratio": 0.35},
                    "overflow_spillway": {"assumed_capacity_cfs": 1.5},
                }
            ],
            "stats": {
                "low_point_count": 1,
                "flow_path_count": 1,
                "total_contributing_area_sf": 1000.0,
                "total_estimated_inlet_flow_cfs": 0.2,
                "total_basin_runoff_cfs": 0.3,
            },
        }
        project.meta["storm_pipe_summary"] = {
            "segments": [{"name": "PIPE-1"}],
            "graph_validation": {"valid": True},
            "hydraulic_validation": {"valid": True},
            "missing_data_segments": [],
            "explain": {"implied_target_used": False},
        }

        drainage_validation = planner._drainage_export_validation(project)
        storm_validation = planner._storm_export_validation(project)

        self.assertFalse(drainage_validation.get("ready"))
        self.assertIn("primary_detention_geometry_weak", drainage_validation.get("reasons", []))
        self.assertGreaterEqual(int(drainage_validation.get("weak_geometry_basin_count") or 0), 1)
        self.assertFalse(storm_validation.get("ready"))
        self.assertIn("primary_detention_geometry_weak", storm_validation.get("reasons", []))

    def test_drainage_export_validation_accepts_engineered_detention_candidates_without_primary_role(self) -> None:
        project = planner.ProjectModel(name="Fallback Detention Candidate")
        project.meta["grading_summary"] = {
            "success": True,
            "fallback_used": False,
            "existing_surface": {"nrows": 5, "ncols": 5},
            "proposed_surface": {"nrows": 5, "ncols": 5},
            "stats": {"proposed_contour_count": 3, "spot_grade_count": 2, "flow_arrow_count": 1},
            "surface_controls": {
                "has_primary_drainage_direction": True,
                "primary_low_point": {"x": 10.0, "y": 10.0, "z": 95.0},
            },
        }
        project.meta["drainage_canonical"] = {
            "success": True,
            "source": "drainage_engine",
            "surface_guidance": {"downhill_vector": {"dx": 1.0, "dy": -1.0}},
            "structures": [{"name": "INLET-1", "x": 10.0, "y": 10.0}],
            "basins": [
                {
                    "id": "BASIN-1",
                    "name": "BASIN-1",
                    "canonical_type": "detention_basin",
                    "exportable": True,
                    "boundary_points": [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]],
                    "detention_design": {"adequacy_status": "adequate"},
                    "geometry_quality": {"has_bottom": True, "footprint_consistency_ratio": 0.75},
                    "overflow_spillway": {"assumed_capacity_cfs": 1.5},
                }
            ],
            "stats": {
                "low_point_count": 1,
                "flow_path_count": 1,
                "total_contributing_area_sf": 1000.0,
                "total_estimated_inlet_flow_cfs": 0.2,
                "total_basin_runoff_cfs": 0.3,
            },
        }
        project.meta["storm_pipe_summary"] = {
            "segments": [{"name": "PIPE-1"}],
            "graph_validation": {"valid": True},
            "hydraulic_validation": {"valid": True},
            "missing_data_segments": [],
            "explain": {"implied_target_used": False},
            "stats": {"selected_basin_name": "BASIN-1"},
        }

        drainage_validation = planner._drainage_export_validation(project)

        self.assertTrue(drainage_validation.get("ready"))
        self.assertNotIn("primary_detention_missing", drainage_validation.get("reasons", []))
        self.assertEqual(drainage_validation.get("primary_basin_count"), 1)

    def test_utility_export_validation_blocks_shallow_and_weak_gravity_segments(self) -> None:
        project = planner.ProjectModel(name="Utility Export Guard")
        project.meta["utility_summary"] = {
            "success": True,
            "fallback_used": False,
            "route_count": 2,
            "shallow_segment_count": 1,
            "gravity_slope_issue_count": 1,
            "conflict_hooks": {
                "utility_segments": [
                    {
                        "name": "SAN-1",
                        "hydraulic_mode": "gravity",
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.2,
                        "slope_ft_ft": 0.002,
                    }
                ]
            },
        }

        validation = planner._utility_export_validation(project)

        self.assertFalse(validation.get("ready"))
        self.assertIn("utility_cover_weak", validation.get("reasons", []))
        self.assertIn("utility_gravity_slope_weak", validation.get("reasons", []))
        self.assertEqual(validation.get("shallow_segment_count"), 1)
        self.assertEqual(validation.get("gravity_slope_issue_count"), 1)

    def test_utility_export_validation_blocks_unresolved_utility_coordination(self) -> None:
        project = planner.ProjectModel(name="Utility Coordination Guard")
        project.meta["coordination_summary"] = {
            "resolved_count": 1,
            "unresolved_conflicts": [
                {
                    "conflict_type": "sanitary_water_clearance",
                    "systems_involved": ["sanitary", "water"],
                    "required_horizontal_clearance_ft": 3.0,
                    "actual_horizontal_clearance_ft": 2.0,
                    "required_vertical_clearance_ft": 1.0,
                    "actual_vertical_clearance_ft": 0.6,
                }
            ],
            "resolved_conflicts": [],
            "post_resolution_validations": {
                "valid": False,
                "systems": {
                    "utilities": {"valid": False},
                    "storm": {"valid": True},
                    "storm_hydraulics": {"valid": True},
                    "sanitary": {"valid": True},
                },
            },
            "resolution_history": [
                {
                    "changed_systems": ["sanitary", "water"],
                    "selected_group_strategy": "hierarchy_first",
                    "selected_candidate_mode": "vertical_adjustment",
                    "notes": ["vertical_adjustment", "reroute_around_obstacle"],
                    "engineering_deltas": {
                        "added_structures": 1,
                        "grading_adjustments": [{"system": "sanitary"}],
                        "crossing_hierarchy": {"total_checks": 1, "compliant_checks": 0},
                    },
                }
            ],
        }
        project.meta["utility_summary"] = planner._enrich_utility_summary_with_coordination(
            {
                "success": True,
                "fallback_used": False,
                "route_count": 1,
                "shallow_segment_count": 0,
                "gravity_slope_issue_count": 0,
                "conflict_hooks": {
                    "minimum_horizontal_separation_ft": 3.0,
                    "minimum_vertical_separation_ft": 1.0,
                    "utility_segments": [
                        {
                            "name": "WATER-1",
                            "segment_role": "service",
                            "hydraulic_mode": "pressurized",
                            "cover_start_ft": 4.0,
                            "cover_end_ft": 4.0,
                        }
                    ],
                },
            },
            project,
        )

        validation = planner._utility_export_validation(project)

        self.assertFalse(validation.get("ready"))
        self.assertIn("utility_coordination_unresolved", validation.get("reasons", []))
        self.assertIn("utility_post_validation_failed", validation.get("reasons", []))
        self.assertEqual(validation.get("utility_related_unresolved_conflict_count"), 1)
        self.assertFalse(validation.get("post_validation_valid"))
        coordination = dict((project.meta.get("utility_summary") or {}).get("coordination") or {})
        self.assertEqual(coordination.get("vertical_adjustment_count"), 1)
        self.assertEqual(coordination.get("reroute_resolution_count"), 1)
        self.assertEqual(coordination.get("added_structures_from_coordination"), 1)
        self.assertEqual(coordination.get("grading_adjustment_count"), 1)
        self.assertEqual(coordination.get("selected_candidate_mode"), "vertical_adjustment")
        self.assertEqual(coordination.get("clearance_total_checks"), 1)
        self.assertEqual(coordination.get("clearance_compliant_checks"), 0)
        self.assertEqual(coordination.get("min_achieved_horizontal_clearance_ft"), 2.0)
        self.assertEqual(coordination.get("min_achieved_vertical_clearance_ft"), 0.6)
        self.assertEqual(coordination.get("max_horizontal_clearance_deficit_ft"), 1.0)
        self.assertEqual(coordination.get("max_vertical_clearance_deficit_ft"), 0.4)
        self.assertFalse(coordination.get("post_validation_valid"))
        self.assertFalse(dict(coordination.get("post_validation_systems") or {}).get("utilities"))

    def test_clearance_resolution_steps_prefer_vertical_for_gravity_and_reroute_for_water(self) -> None:
        ordered_targets = [
            ("storm", "storm_main"),
            ("sanitary", "sanitary_main"),
            ("water", "water_main"),
        ]

        steps = planner._clearance_resolution_steps(
            "crossing",
            "default_crossing",
            ordered_targets,
            preferred_lower="sanitary",
        )

        self.assertLess(steps.index(("vertical", "sanitary")), steps.index(("reroute", "sanitary")))
        self.assertLess(steps.index(("reroute", "water")), steps.index(("vertical", "water")))

    def test_drainage_stage_persists_surface_low_points_and_flow_paths(self) -> None:
        payload = {
            "project_name": "Drainage Surface Records",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "6% slope NW to SE",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        out = planner.build_plan(payload)
        drainage = out.get("meta", {}).get("drainage", {})
        stats = drainage.get("stats", {})

        self.assertGreater(len(drainage.get("low_points", [])), 0)
        self.assertGreater(len(drainage.get("flow_paths", [])), 0)
        self.assertGreater(stats.get("low_point_count", 0), 0)
        self.assertGreater(stats.get("flow_path_count", 0), 0)
        self.assertTrue(drainage.get("surface_guidance"))
        self.assertTrue(drainage.get("surface_guidance", {}).get("downhill_vector"))
        self.assertGreater(stats.get("total_contributing_area_sf", 0.0), 0.0)
        self.assertGreater(stats.get("total_estimated_inlet_flow_cfs", 0.0), 0.0)
        self.assertGreater(stats.get("total_basin_runoff_cfs", 0.0), 0.0)
        self.assertTrue(any((item or {}).get("tributary_basin_name") for item in drainage.get("structures", [])))
        export_validation = drainage.get("export_validation", {})
        self.assertGreater(export_validation.get("low_point_count", 0), 0)
        self.assertGreater(export_validation.get("flow_path_count", 0), 0)
        self.assertTrue(export_validation.get("grading_export_ready"))
        self.assertTrue((export_validation.get("surface_controls") or {}).get("has_primary_drainage_direction"))
        self.assertGreaterEqual(int(((export_validation.get("surface_controls") or {}).get("control_counts") or {}).get("pad", 0)), 1)
        self.assertGreaterEqual(int(((export_validation.get("surface_controls") or {}).get("control_counts") or {}).get("parking", 0)), 1)
        self.assertGreaterEqual(
            int((export_validation.get("surface_alignment") or {}).get("matched_low_points", 0)),
            1,
        )
        self.assertGreater(export_validation.get("total_estimated_inlet_flow_cfs", 0.0), 0.0)
        self.assertGreater(export_validation.get("total_basin_runoff_cfs", 0.0), 0.0)

    def test_drainage_coordination_uses_grading_surface_targets(self) -> None:
        payload = {
            "project_name": "Surface Drainage Coordination",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "6% slope NW to SE",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        out = planner.build_plan(payload)
        drainage = out.get("meta", {}).get("drainage", {})
        coordination = drainage.get("coordination", {})
        preferred = coordination.get("preferred_outfall", {})

        self.assertTrue(coordination)
        self.assertGreaterEqual(coordination.get("grading_low_point_count", 0), 1)
        self.assertGreater(preferred.get("x", 0.0), 90.0)
        self.assertLess(preferred.get("y", 999.0), 70.0)
        self.assertTrue((coordination.get("surface_controls") or {}).get("has_primary_drainage_direction"))
        self.assertTrue((coordination.get("surface_controls") or {}).get("primary_low_point"))
        self.assertGreaterEqual(int((coordination.get("grading_control_counts") or {}).get("pad", 0)), 1)

    def test_storm_pipes_honor_surface_driven_outfall(self) -> None:
        payload = {
            "project_name": "Storm Outfall Coordination",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "5% slope toward southeast",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        out = planner.build_plan(payload)
        storm = out.get("meta", {}).get("storm_pipes", {})
        stage_map = {item["stage_name"]: item for item in out.get("meta", {}).get("stage_results", [])}
        storm_stage = stage_map.get("storm_pipes", {})
        storm_meta = storm_stage.get("meta", {})
        selected_outfall = str((storm.get("explain") or {}).get("selected_outfall_name") or "")
        selected_node = next((node for node in storm.get("nodes", []) if node.get("name") == selected_outfall), {})

        self.assertTrue(selected_outfall)
        self.assertTrue(selected_node)
        self.assertAlmostEqual(storm_meta.get("outfall_x", 0.0), float(selected_node.get("x", 0.0)), places=3)
        self.assertAlmostEqual(storm_meta.get("outfall_y", 0.0), float(selected_node.get("y", 0.0)), places=3)

    def test_storm_network_uses_engineered_basin_outlet_geometry_when_available(self) -> None:
        drainage_meta = {
            "structures": [
                {"name": "INLET-1", "object_type": "inlet", "structure_type": "inlet", "x": 40.0, "y": 30.0, "z": 102.0, "contributing_area_sf": 4000.0, "estimated_flow_cfs": 0.1},
                {"name": "INLET-2", "object_type": "inlet", "structure_type": "inlet", "x": 95.0, "y": 45.0, "z": 101.0, "contributing_area_sf": 6000.0, "estimated_flow_cfs": 0.12},
            ],
            "basins": [
                {
                    "name": "BASIN-1",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[150.0, 10.0], [190.0, 10.0], [190.0, 40.0], [150.0, 40.0]],
                    "bottom_elev_ft": 94.0,
                    "top_of_bank_elev_ft": 100.0,
                    "detention_design": {"required_storage_cf": 3800.0, "provided_storage_cf": 4000.0, "drawdown_hours": 18.0, "depth_ft": 4.0, "release_cfs": 0.3},
                    "outlet_structure": {"name": "OUTLET-1", "x": 170.0, "y": 20.0, "rim_elev_ft": 96.0, "invert_out_ft": 93.0},
                }
            ],
        }

        basins = planner._storm_basins_from_drainage(drainage_meta)
        self.assertEqual(len(basins), 1)

        network_result = build_storm_network(
            StormNetworkRequest(
                network_name="Storm Basin Outlet Test",
                catchments=planner._storm_catchments_from_drainage(drainage_meta, runoff_c=0.85, intensity_in_hr=4.0),
                inlets=planner._storm_inlets_from_drainage(drainage_meta),
                basins=basins,
                outfalls=[],
                default_pipe_material="RCP",
                default_mannings_n=planner.PIPE_MANNINGS_N,
                min_pipe_slope=planner.PIPE_MIN_SLOPE,
                min_cover_ft=planner.PIPE_MIN_COVER_FT,
                min_diameter_in=12.0,
                auto_route=True,
                route_system_type="storm",
                use_trunks=True,
                use_laterals=True,
                connect_to_basin=True,
                meta={"surface_driven": True},
            )
        )
        storm = planner._storm_summary_from_network_result(
            network_result,
            analyze_storm_hydraulics(
                HydraulicAnalysisRequest(
                    pipes=list(getattr(getattr(network_result, "network", None), "pipes", [])),
                    nodes=list(getattr(getattr(network_result, "network", None), "nodes", [])),
                    conservative=True,
                    compute_hgl=True,
                    compute_egl=True,
                    allow_partial_flow=True,
                )
            ),
        )
        selected_outfall_name = storm.get("explain", {}).get("selected_outfall_name")
        selected_node = next((node for node in storm.get("nodes", []) if node.get("name") == selected_outfall_name), {})

        self.assertEqual(selected_outfall_name, "OUTLET-1")
        self.assertAlmostEqual(float(selected_node.get("x", 0.0)), 170.0, places=3)
        self.assertAlmostEqual(float(selected_node.get("y", 0.0)), 20.0, places=3)

    def test_storm_engine_keeps_all_primary_basins_but_only_selected_target_in_network(self) -> None:
        drainage_meta = {
            "coordination": {"preferred_outfall": {"target_name": "OUTLET-B"}},
            "basins": [
                {
                    "name": "BASIN-A",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[100.0, 10.0], [130.0, 10.0], [130.0, 35.0], [100.0, 35.0]],
                    "area_sf": 750.0,
                    "detention_design": {"provided_storage_cf": 1800.0, "required_storage_cf": 1700.0},
                    "outlet_structure": {"name": "OUTLET-A", "x": 115.0, "y": 18.0, "rim_elev_ft": 96.0, "invert_out_ft": 93.0},
                },
                {
                    "name": "BASIN-B",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[150.0, 10.0], [190.0, 10.0], [190.0, 40.0], [150.0, 40.0]],
                    "area_sf": 1200.0,
                    "detention_design": {"provided_storage_cf": 4000.0, "required_storage_cf": 3800.0},
                    "outlet_structure": {"name": "OUTLET-B", "x": 170.0, "y": 20.0, "rim_elev_ft": 96.0, "invert_out_ft": 93.0},
                },
            ],
        }

        basins = planner._storm_basins_from_drainage(drainage_meta)
        self.assertEqual(len(basins), 2)

        network_result = build_storm_network(
            StormNetworkRequest(
                network_name="Storm Basin Selection Test",
                catchments=[],
                inlets=planner._storm_inlets_from_drainage(
                    {
                        "structures": [
                            {
                                "name": "INLET-1",
                                "object_type": "inlet",
                                "structure_type": "inlet",
                                "x": 40.0,
                                "y": 30.0,
                                "z": 102.0,
                                "contributing_area_sf": 4000.0,
                                "estimated_flow_cfs": 0.1,
                            }
                        ]
                    }
                ),
                basins=basins,
                outfalls=[],
                default_pipe_material="RCP",
                default_mannings_n=planner.PIPE_MANNINGS_N,
                min_pipe_slope=planner.PIPE_MIN_SLOPE,
                min_cover_ft=planner.PIPE_MIN_COVER_FT,
                min_diameter_in=12.0,
                auto_route=True,
                route_system_type="storm",
                use_trunks=True,
                use_laterals=True,
                connect_to_basin=True,
                meta={"surface_driven": True, "preferred_target_name": "OUTLET-B"},
            )
        )
        storm = planner._storm_summary_from_network_result(
            network_result,
            analyze_storm_hydraulics(
                HydraulicAnalysisRequest(
                    pipes=list(getattr(getattr(network_result, "network", None), "pipes", [])),
                    nodes=list(getattr(getattr(network_result, "network", None), "nodes", [])),
                    conservative=True,
                    compute_hgl=True,
                    compute_egl=True,
                    allow_partial_flow=True,
                )
            ),
        )

        node_names = {str(node.get("name") or "") for node in storm.get("nodes", [])}
        self.assertEqual(storm.get("explain", {}).get("selected_outfall_name"), "OUTLET-B")
        self.assertIn("OUTLET-B", node_names)
        self.assertNotIn("OUTLET-A", node_names)

    def test_storm_engine_prefers_storage_adequate_basin_with_real_outlet_geometry(self) -> None:
        drainage_meta = {
            "basins": [
                {
                    "name": "BASIN-A",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[100.0, 10.0], [150.0, 10.0], [150.0, 50.0], [100.0, 50.0]],
                    "area_sf": 2000.0,
                    "detention_design": {"provided_storage_cf": 2500.0, "required_storage_cf": 4000.0, "depth_ft": 2.5},
                },
                {
                    "name": "BASIN-B",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[150.0, 10.0], [190.0, 10.0], [190.0, 40.0], [150.0, 40.0]],
                    "area_sf": 1200.0,
                    "detention_design": {
                        "provided_storage_cf": 4200.0,
                        "required_storage_cf": 3800.0,
                        "depth_ft": 4.0,
                        "release_cfs": 0.3,
                    },
                    "outlet_structure": {"name": "OUTLET-B", "x": 170.0, "y": 20.0, "rim_elev_ft": 96.0, "invert_out_ft": 93.0},
                },
            ]
        }

        basins = planner._storm_basins_from_drainage(drainage_meta)
        network_result = build_storm_network(
            StormNetworkRequest(
                network_name="Storm Basin Quality Test",
                catchments=[],
                inlets=planner._storm_inlets_from_drainage(
                    {
                        "structures": [
                            {
                                "name": "INLET-1",
                                "object_type": "inlet",
                                "structure_type": "inlet",
                                "x": 40.0,
                                "y": 30.0,
                                "z": 102.0,
                                "contributing_area_sf": 4000.0,
                                "estimated_flow_cfs": 0.1,
                            }
                        ]
                    }
                ),
                basins=basins,
                outfalls=[],
                default_pipe_material="RCP",
                default_mannings_n=planner.PIPE_MANNINGS_N,
                min_pipe_slope=planner.PIPE_MIN_SLOPE,
                min_cover_ft=planner.PIPE_MIN_COVER_FT,
                min_diameter_in=12.0,
                auto_route=True,
                route_system_type="storm",
                use_trunks=True,
                use_laterals=True,
                connect_to_basin=True,
                meta={"surface_driven": True},
            )
        )
        storm = planner._storm_summary_from_network_result(
            network_result,
            analyze_storm_hydraulics(
                HydraulicAnalysisRequest(
                    pipes=list(getattr(getattr(network_result, "network", None), "pipes", [])),
                    nodes=list(getattr(getattr(network_result, "network", None), "nodes", [])),
                    conservative=True,
                    compute_hgl=True,
                    compute_egl=True,
                    allow_partial_flow=True,
                )
            ),
        )

        self.assertEqual(storm.get("explain", {}).get("selected_outfall_name"), "OUTLET-B")

    def test_storm_engine_prefers_adequate_basin_with_better_drawdown_and_spillway(self) -> None:
        drainage_meta = {
            "basins": [
                {
                    "name": "BASIN-A",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[100.0, 10.0], [150.0, 10.0], [150.0, 50.0], [100.0, 50.0]],
                    "area_sf": 1800.0,
                    "detention_design": {
                        "provided_storage_cf": 4100.0,
                        "required_storage_cf": 3800.0,
                        "drawdown_hours": 60.0,
                        "adequacy_status": "adequate",
                        "release_cfs": 0.22,
                    },
                    "overflow_spillway": {"assumed_capacity_cfs": 1.2},
                    "outlet_structure": {"name": "OUTLET-A", "x": 115.0, "y": 18.0, "rim_elev_ft": 96.0, "invert_out_ft": 93.0},
                },
                {
                    "name": "BASIN-B",
                    "engineering_role": "primary_detention",
                    "exportable": True,
                    "boundary_points": [[150.0, 10.0], [190.0, 10.0], [190.0, 40.0], [150.0, 40.0]],
                    "area_sf": 1500.0,
                    "detention_design": {
                        "provided_storage_cf": 4050.0,
                        "required_storage_cf": 3800.0,
                        "drawdown_hours": 24.0,
                        "adequacy_status": "adequate",
                        "release_cfs": 0.32,
                    },
                    "overflow_spillway": {"assumed_capacity_cfs": 3.4},
                    "outlet_structure": {"name": "OUTLET-B", "x": 170.0, "y": 20.0, "rim_elev_ft": 96.0, "invert_out_ft": 93.0},
                },
            ]
        }

        basins = planner._storm_basins_from_drainage(drainage_meta)
        network_result = build_storm_network(
            StormNetworkRequest(
                network_name="Storm Basin Adequacy Test",
                catchments=[],
                inlets=planner._storm_inlets_from_drainage(
                    {
                        "structures": [
                            {
                                "name": "INLET-1",
                                "object_type": "inlet",
                                "structure_type": "inlet",
                                "x": 40.0,
                                "y": 30.0,
                                "z": 102.0,
                                "contributing_area_sf": 4000.0,
                                "estimated_flow_cfs": 0.1,
                            }
                        ]
                    }
                ),
                basins=basins,
                outfalls=[],
                default_pipe_material="RCP",
                default_mannings_n=planner.PIPE_MANNINGS_N,
                min_pipe_slope=planner.PIPE_MIN_SLOPE,
                min_cover_ft=planner.PIPE_MIN_COVER_FT,
                min_diameter_in=12.0,
                auto_route=True,
                route_system_type="storm",
                use_trunks=True,
                use_laterals=True,
                connect_to_basin=True,
                meta={"surface_driven": True},
            )
        )
        storm = planner._storm_summary_from_network_result(
            network_result,
            analyze_storm_hydraulics(
                HydraulicAnalysisRequest(
                    pipes=list(getattr(getattr(network_result, "network", None), "pipes", [])),
                    nodes=list(getattr(getattr(network_result, "network", None), "nodes", [])),
                    conservative=True,
                    compute_hgl=True,
                    compute_egl=True,
                    allow_partial_flow=True,
                )
            ),
        )

        self.assertEqual(storm.get("explain", {}).get("selected_outfall_name"), "OUTLET-B")
        stats = storm.get("stats", {})
        self.assertEqual(stats.get("selected_basin_name"), "BASIN-B")
        self.assertEqual(stats.get("selected_basin_adequacy_status"), "adequate")
        self.assertGreater(float(stats.get("selected_basin_target_drawdown_hours") or 0.0), 0.0)
        self.assertGreater(float(stats.get("selected_basin_spillway_capacity_cfs") or 0.0), 0.0)

    def test_storm_stage_builds_real_network_topology_from_surface_driven_drainage(self) -> None:
        drainage_meta = {
            "surface_guidance": {
                "preferred_targets": [
                    {"target_name": "OUTLET-1", "x": 170.0, "y": 20.0},
                ]
            },
            "structures": [
                {"name": "INLET-1", "object_type": "inlet", "structure_type": "inlet", "x": 40.0, "y": 30.0, "z": 102.0, "contributing_area_sf": 4000.0, "estimated_flow_cfs": 0.1},
                {"name": "INLET-2", "object_type": "inlet", "structure_type": "inlet", "x": 95.0, "y": 45.0, "z": 101.0, "contributing_area_sf": 6000.0, "estimated_flow_cfs": 0.12},
                {"name": "INLET-3", "object_type": "inlet", "structure_type": "inlet", "x": 125.0, "y": 62.0, "z": 100.5, "contributing_area_sf": 5000.0, "estimated_flow_cfs": 0.11},
                {"name": "OUTLET-1", "object_type": "outlet_structure", "structure_type": "outlet_structure", "x": 170.0, "y": 20.0, "z": 96.0},
            ],
            "basins": [
                {
                    "name": "BASIN-1",
                    "is_primary": True,
                    "boundary": [[150.0, 10.0], [190.0, 10.0], [190.0, 40.0], [150.0, 40.0]],
                    "bottom_polygon": [[158.0, 16.0], [182.0, 16.0], [182.0, 34.0], [158.0, 34.0]],
                    "bottom_elev_ft": 94.0,
                    "top_of_bank_elev_ft": 100.0,
                    "storage_cf": 4000.0,
                    "detention": {"storage_cf": 4000.0, "required_storage_cf": 3800.0, "drawdown_hours": 18.0},
                    "outlet_structure": {"name": "OUTLET-1", "x": 170.0, "y": 20.0, "rim_elev_ft": 96.0, "invert_out_ft": 93.0},
                }
            ],
        }

        inlets = planner._storm_inlets_from_drainage(drainage_meta)
        basins = planner._storm_basins_from_drainage(drainage_meta)
        catchments = planner._storm_catchments_from_drainage(
            drainage_meta,
            runoff_c=0.85,
            intensity_in_hr=4.0,
        )
        outfall = StormNode(
            name="OUTFALL-1",
            node_type=StormNodeType.OUTFALL.value,
            point=StormPoint(170.0, 20.0, 96.0),
            rim_elev_ft=96.0,
            invert_elev_ft=93.0,
        )
        network_result = build_storm_network(
            StormNetworkRequest(
                network_name="Storm Test",
                catchments=catchments,
                inlets=inlets,
                basins=basins,
                outfalls=[outfall],
                default_pipe_material="RCP",
                default_mannings_n=planner.PIPE_MANNINGS_N,
                min_pipe_slope=planner.PIPE_MIN_SLOPE,
                min_cover_ft=planner.PIPE_MIN_COVER_FT,
                min_diameter_in=12.0,
                auto_route=True,
                route_system_type="storm",
                use_trunks=True,
                use_laterals=True,
                connect_to_basin=True,
                meta={"surface_driven": True},
            )
        )
        hydraulic_result = analyze_storm_hydraulics(
            HydraulicAnalysisRequest(
                pipes=list(getattr(getattr(network_result, "network", None), "pipes", [])),
                nodes=list(getattr(getattr(network_result, "network", None), "nodes", [])),
                conservative=True,
                compute_hgl=True,
                compute_egl=True,
                allow_partial_flow=True,
            )
        )
        storm = planner._storm_summary_from_network_result(network_result, hydraulic_result)
        segments = storm.get("segments", [])
        nodes = storm.get("nodes", [])
        segment_roles = {str(seg.get("segment_role") or "") for seg in segments}

        self.assertTrue(storm.get("graph_validation", {}).get("valid"))
        self.assertGreater(len(nodes), 0)
        self.assertIn("trunk", segment_roles)
        self.assertIn("lateral", segment_roles)

    def test_storm_builders_preserve_surface_guidance_targets(self) -> None:
        drainage_meta = {
            "surface_guidance": {
                "preferred_targets": [
                    {"target_name": "OUTLET-A", "x": 180.0, "y": 20.0},
                    {"target_name": "OUTLET-B", "x": 40.0, "y": 20.0},
                ]
            },
            "structures": [
                {
                    "name": "INLET-1",
                    "object_type": "inlet",
                    "structure_type": "inlet",
                    "x": 175.0,
                    "y": 30.0,
                    "z": 102.0,
                    "contributing_area_sf": 4000.0,
                    "estimated_flow_cfs": 0.1,
                }
            ],
        }

        inlets = planner._storm_inlets_from_drainage(drainage_meta)
        catchments = planner._storm_catchments_from_drainage(drainage_meta, runoff_c=0.85, intensity_in_hr=4.0)

        self.assertEqual(inlets[0].meta.get("target_name"), "OUTLET-A")
        self.assertEqual(catchments[0].meta.get("preferred_target_name"), "OUTLET-A")

    def test_storm_engine_prefers_surface_aligned_inlet_assignment(self) -> None:
        from engines.storm.storm_types import StormCatchment, StormInlet

        inlet_a = StormInlet(
            name="INLET-A",
            node_type=StormNodeType.INLET.value,
            point=StormPoint(100.0, 0.0, 100.0),
            rim_elev_ft=100.0,
            meta={"target_name": "OUTLET-A"},
        )
        inlet_b = StormInlet(
            name="INLET-B",
            node_type=StormNodeType.INLET.value,
            point=StormPoint(10.0, 0.0, 100.0),
            rim_elev_ft=100.0,
            meta={"target_name": "OUTLET-B"},
        )
        catchment = StormCatchment(
            name="CATCH-1",
            area_sf=5000.0,
            runoff_c=0.85,
            tc_minutes=10.0,
            intensity_in_hr=4.0,
            peak_runoff_cfs=0.2,
            centroid=StormPoint(20.0, 0.0, 100.0),
            meta={"preferred_target_name": "OUTLET-A"},
        )

        engine = StormNetworkEngine()
        chosen = engine._nearest_inlet(catchment, [inlet_a, inlet_b])
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.name, "INLET-A")

    def test_storm_engine_prefers_lower_load_inlet_when_target_matches(self) -> None:
        from engines.storm.storm_types import StormCatchment, StormInlet

        inlet_loaded = StormInlet(
            name="INLET-LOADED",
            node_type=StormNodeType.INLET.value,
            point=StormPoint(10.0, 0.0, 100.0),
            rim_elev_ft=100.0,
            contributing_area_sf=22000.0,
            contributing_runoff_cfs=1.8,
            incoming_catchment_names=["C1", "C2", "C3"],
            meta={
                "target_name": "OUTLET-A",
                "tributary_area_sf": 22000.0,
                "tributary_runoff_cfs": 1.8,
                "tributary_catchment_count": 3,
            },
        )
        inlet_lighter = StormInlet(
            name="INLET-LIGHT",
            node_type=StormNodeType.INLET.value,
            point=StormPoint(28.0, 0.0, 100.0),
            rim_elev_ft=100.0,
            contributing_area_sf=3000.0,
            contributing_runoff_cfs=0.15,
            incoming_catchment_names=["C4"],
            meta={
                "target_name": "OUTLET-A",
                "tributary_area_sf": 3000.0,
                "tributary_runoff_cfs": 0.15,
                "tributary_catchment_count": 1,
            },
        )
        catchment = StormCatchment(
            name="CATCH-LOAD",
            area_sf=4000.0,
            runoff_c=0.85,
            tc_minutes=10.0,
            intensity_in_hr=4.0,
            peak_runoff_cfs=0.2,
            centroid=StormPoint(12.0, 0.0, 100.0),
            meta={"preferred_target_name": "OUTLET-A"},
        )

        engine = StormNetworkEngine()
        chosen = engine._nearest_inlet(catchment, [inlet_loaded, inlet_lighter])
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.name, "INLET-LIGHT")

    def test_storm_export_validation_blocks_implied_outfall_networks(self) -> None:
        inlets = planner._storm_inlets_from_drainage(
            {
                "structures": [
                    {
                        "name": "INLET-1",
                        "object_type": "inlet",
                        "structure_type": "inlet",
                        "x": 40.0,
                        "y": 30.0,
                        "z": 102.0,
                        "contributing_area_sf": 4000.0,
                        "estimated_flow_cfs": 0.1,
                    }
                ]
            }
        )
        network_result = build_storm_network(
            StormNetworkRequest(
                network_name="Implied Outfall Test",
                catchments=[],
                inlets=inlets,
                basins=[],
                outfalls=[],
                default_pipe_material="RCP",
                default_mannings_n=planner.PIPE_MANNINGS_N,
                min_pipe_slope=planner.PIPE_MIN_SLOPE,
                min_cover_ft=planner.PIPE_MIN_COVER_FT,
                min_diameter_in=12.0,
                auto_route=True,
                route_system_type="storm",
                use_trunks=True,
                use_laterals=True,
                connect_to_basin=True,
                meta={"surface_driven": True},
            )
        )
        storm = planner._storm_summary_from_network_result(
            network_result,
            analyze_storm_hydraulics(
                HydraulicAnalysisRequest(
                    pipes=list(getattr(getattr(network_result, "network", None), "pipes", [])),
                    nodes=list(getattr(getattr(network_result, "network", None), "nodes", [])),
                    conservative=True,
                    compute_hgl=True,
                    compute_egl=True,
                    allow_partial_flow=True,
                )
            ),
        )
        project = planner.ProjectModel(name="Implied Outfall Validation")
        project.meta["storm_pipe_summary"] = storm

        validation = planner._storm_export_validation(project)

        self.assertTrue(storm.get("explain", {}).get("implied_target_used"))
        self.assertFalse(validation.get("ready"))
        self.assertIn("storm_downstream_target_implied", validation.get("reasons", []))

    def test_trunk_sizing_uses_tributary_demand_context(self) -> None:
        catchments = [
            StormCatchment(
                name=f"CATCH-{idx}",
                area_sf=20000.0,
                runoff_c=0.85,
                tc_minutes=10.0,
                intensity_in_hr=4.0,
                peak_runoff_cfs=1.6,
                centroid=StormPoint(x=20.0 * idx, y=20.0, z=100.0, label=f"CATCH-{idx}"),
                meta={"tributary_basin_name": f"BASIN-{idx}"},
            )
            for idx in range(1, 5)
        ]
        inlets = [
            StormInlet(
                name=f"INLET-{idx}",
                node_type=StormNodeType.INLET.value,
                point=StormPoint(x=20.0 * idx, y=40.0, z=100.0, label=f"INLET-{idx}"),
                rim_elev_ft=100.0,
                invert_elev_ft=97.0,
                contributing_area_sf=20000.0,
                contributing_runoff_cfs=1.6,
                meta={"tributary_basin_names": [f"BASIN-{idx}"], "tributary_catchment_count": 1},
            )
            for idx in range(1, 5)
        ]
        outfall = StormNode(
            name="OUTFALL-1",
            node_type=StormNodeType.OUTFALL.value,
            point=StormPoint(x=140.0, y=0.0, z=95.0, label="OUTFALL-1"),
            rim_elev_ft=98.0,
            invert_elev_ft=95.0,
        )
        result = build_storm_network(
            StormNetworkRequest(
                network_name="Demand Sized Trunk",
                catchments=catchments,
                inlets=inlets,
                outfalls=[outfall],
                min_diameter_in=12.0,
            )
        )

        self.assertTrue(result.success)
        trunk = next(pipe for pipe in result.network.pipes if pipe.pipe_type == "trunk")
        self.assertGreaterEqual(trunk.diameter_in, 18.0)
        self.assertEqual(int(dict(trunk.meta).get("tributary_catchment_count", 0)), 4)
        self.assertEqual(len(list(dict(trunk.meta).get("tributary_basin_names") or [])), 4)

    def test_storm_summary_preserves_tributary_demand_context(self) -> None:
        payload = {
            "project_name": "Storm Tributary Context",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "5% slope toward southeast",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        out = planner.build_plan(payload)
        storm = out.get("meta", {}).get("storm_pipes", {})
        segments = storm.get("segments", [])
        self.assertTrue(segments)
        self.assertTrue(any(int(seg.get("tributary_catchment_count", 0)) > 0 for seg in segments))
        self.assertTrue(any((seg.get("tributary_basin_names") or []) for seg in segments))
        nodes = storm.get("nodes", [])
        self.assertTrue(any((node.get("tributary_basin_names") or []) for node in nodes if node.get("node_type") == "inlet"))
        hydraulic_summary = storm.get("hydraulic_summary", {})
        self.assertGreater(hydraulic_summary.get("system_tributary_area_sf", 0.0), 0.0)
        self.assertGreater(hydraulic_summary.get("system_tributary_runoff_cfs", 0.0), 0.0)
        self.assertGreater(hydraulic_summary.get("system_tributary_catchment_count", 0), 0)
        self.assertTrue(hydraulic_summary.get("system_tributary_basin_names"))

    def test_hydraulic_summary_preserves_tributary_context_for_critical_pipes(self) -> None:
        catchments = [
            StormCatchment(
                name=f"CATCH-{idx}",
                area_sf=18000.0,
                runoff_c=0.85,
                tc_minutes=10.0,
                intensity_in_hr=4.0,
                peak_runoff_cfs=1.2,
                centroid=StormPoint(x=20.0 * idx, y=20.0, z=100.0, label=f"CATCH-{idx}"),
                meta={"tributary_basin_name": f"BASIN-{idx}"},
            )
            for idx in range(1, 4)
        ]
        inlets = [
            StormInlet(
                name=f"INLET-{idx}",
                node_type=StormNodeType.INLET.value,
                point=StormPoint(x=20.0 * idx, y=40.0, z=100.0, label=f"INLET-{idx}"),
                rim_elev_ft=100.0,
                invert_elev_ft=97.0,
                contributing_area_sf=18000.0,
                contributing_runoff_cfs=1.2,
                meta={"tributary_basin_names": [f"BASIN-{idx}"], "tributary_catchment_count": 1},
            )
            for idx in range(1, 4)
        ]
        outfall = StormNode(
            name="OUTFALL-1",
            node_type=StormNodeType.OUTFALL.value,
            point=StormPoint(x=120.0, y=0.0, z=95.0, label="OUTFALL-1"),
            rim_elev_ft=98.0,
            invert_elev_ft=95.0,
        )
        network_result = build_storm_network(
            StormNetworkRequest(
                network_name="Hydraulic Tributary Summary",
                catchments=catchments,
                inlets=inlets,
                outfalls=[outfall],
                min_diameter_in=12.0,
            )
        )
        hydraulic = analyze_storm_hydraulics(
            HydraulicAnalysisRequest(
                pipes=list(getattr(getattr(network_result, "network", None), "pipes", [])),
                nodes=list(getattr(getattr(network_result, "network", None), "nodes", [])),
                conservative=True,
                compute_hgl=True,
                compute_egl=True,
                allow_partial_flow=True,
            )
        )
        summary = getattr(hydraulic, "summary", {})

        self.assertGreater(summary.get("system_tributary_area_sf", 0.0), 0.0)
        self.assertGreater(summary.get("system_tributary_runoff_cfs", 0.0), 0.0)
        self.assertGreater(summary.get("system_tributary_catchment_count", 0), 0)
        self.assertTrue(summary.get("system_tributary_basin_names"))
        critical_pipes = summary.get("critical_pipes", [])
        self.assertTrue(critical_pipes)
        self.assertTrue(any(float(pipe.get("tributary_area_sf", 0.0)) > 0.0 for pipe in critical_pipes))
        self.assertTrue(any(int(pipe.get("tributary_catchment_count", 0)) > 0 for pipe in critical_pipes))

    def test_pipe_demand_context_propagates_downstream_cumulative_loads(self) -> None:
        catchments = [
            StormCatchment(
                name=f"CATCH-{idx}",
                area_sf=12000.0,
                runoff_c=0.85,
                tc_minutes=10.0,
                intensity_in_hr=4.0,
                peak_runoff_cfs=0.9,
                centroid=StormPoint(x=20.0 * idx, y=20.0, z=100.0, label=f"CATCH-{idx}"),
                meta={"tributary_basin_name": f"BASIN-{idx}"},
            )
            for idx in range(1, 4)
        ]
        inlets = [
            StormInlet(
                name=f"INLET-{idx}",
                node_type=StormNodeType.INLET.value,
                point=StormPoint(x=20.0 * idx, y=40.0, z=100.0, label=f"INLET-{idx}"),
                rim_elev_ft=100.0,
                invert_elev_ft=97.0,
                contributing_area_sf=12000.0,
                contributing_runoff_cfs=0.9,
                meta={"tributary_basin_names": [f"BASIN-{idx}"], "tributary_catchment_count": 1},
            )
            for idx in range(1, 4)
        ]
        outfall = StormNode(
            name="OUTFALL-1",
            node_type=StormNodeType.OUTFALL.value,
            point=StormPoint(x=120.0, y=0.0, z=95.0, label="OUTFALL-1"),
            rim_elev_ft=98.0,
            invert_elev_ft=95.0,
        )
        result = build_storm_network(
            StormNetworkRequest(
                network_name="Cumulative Trunk Load",
                catchments=catchments,
                inlets=inlets,
                outfalls=[outfall],
                min_diameter_in=12.0,
            )
        )

        self.assertTrue(result.success)
        trunk = next(pipe for pipe in result.network.pipes if pipe.pipe_type == "trunk")
        self.assertGreater(float(dict(trunk.meta).get("upstream_cumulative_area_sf", 0.0)), 30000.0)
        self.assertGreater(float(dict(trunk.meta).get("upstream_cumulative_runoff_cfs", 0.0)), 2.0)
        self.assertGreaterEqual(int(dict(trunk.meta).get("upstream_cumulative_catchment_count", 0)), 3)
        self.assertEqual(len(list(dict(trunk.meta).get("upstream_cumulative_basin_names") or [])), 3)

    def test_storm_summary_preserves_upstream_cumulative_demand_context(self) -> None:
        payload = {
            "project_name": "Storm Cumulative Context",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "5% slope toward southeast",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        out = planner.build_plan(payload)
        storm = out.get("meta", {}).get("storm_pipes", {})
        segments = storm.get("segments", [])
        self.assertTrue(segments)
        self.assertTrue(any(float(seg.get("upstream_cumulative_area_sf", 0.0)) > 0.0 for seg in segments))
        self.assertTrue(any(float(seg.get("upstream_cumulative_runoff_cfs", 0.0)) > 0.0 for seg in segments))
        self.assertTrue(any(int(seg.get("upstream_cumulative_catchment_count", 0)) > 0 for seg in segments))
        nodes = storm.get("nodes", [])
        self.assertTrue(any(float(node.get("upstream_cumulative_area_sf", 0.0)) > 0.0 for node in nodes))
        self.assertGreater(storm.get("stats", {}).get("max_governing_flow_cfs", 0.0), 0.0)
        self.assertGreater(storm.get("stats", {}).get("max_governing_area_sf", 0.0), 0.0)
        self.assertIn("deficient_count", storm.get("stats", {}))
        self.assertIn("marginal_count", storm.get("stats", {}))

    def test_trunk_hydraulic_status_uses_governing_demand(self) -> None:
        catchments = [
            StormCatchment(
                name=f"CATCH-{idx}",
                area_sf=26000.0,
                runoff_c=0.85,
                tc_minutes=10.0,
                intensity_in_hr=4.0,
                peak_runoff_cfs=2.2,
                centroid=StormPoint(x=20.0 * idx, y=20.0, z=100.0, label=f"CATCH-{idx}"),
                meta={"tributary_basin_name": f"BASIN-{idx}"},
            )
            for idx in range(1, 4)
        ]
        inlets = [
            StormInlet(
                name=f"INLET-{idx}",
                node_type=StormNodeType.INLET.value,
                point=StormPoint(x=20.0 * idx, y=40.0, z=100.0, label=f"INLET-{idx}"),
                rim_elev_ft=100.0,
                invert_elev_ft=97.0,
                contributing_area_sf=26000.0,
                contributing_runoff_cfs=2.2,
                meta={"tributary_basin_names": [f"BASIN-{idx}"], "tributary_catchment_count": 1},
            )
            for idx in range(1, 4)
        ]
        outfall = StormNode(
            name="OUTFALL-1",
            node_type=StormNodeType.OUTFALL.value,
            point=StormPoint(x=120.0, y=0.0, z=95.0, label="OUTFALL-1"),
            rim_elev_ft=98.0,
            invert_elev_ft=95.0,
        )
        result = build_storm_network(
            StormNetworkRequest(
                network_name="Governing Trunk Demand",
                catchments=catchments,
                inlets=inlets,
                outfalls=[outfall],
                min_diameter_in=12.0,
            )
        )
        trunk = next(pipe for pipe in result.network.pipes if pipe.pipe_type == "trunk")

        self.assertGreater(float(dict(trunk.meta).get("governing_flow_cfs", 0.0)), 0.0)
        self.assertGreaterEqual(float(dict(trunk.meta).get("governing_flow_cfs", 0.0)), float(trunk.assigned_runoff_cfs))
        self.assertIn(trunk.hydraulic.capacity_status, {"marginal", "deficient", "ok"})

    def test_basin_connection_preserves_release_and_spillway_design_context(self) -> None:
        basin = StormBasin(
            name="BASIN-1",
            basin_type="detention",
            bottom_area_sf=800.0,
            top_area_sf=1800.0,
            depth_ft=4.5,
            side_slope_h_to_1v=4.0,
            bottom_elev_ft=94.0,
            overflow_elev_ft=100.0,
            release_cfs=0.28,
            required_storage_cf=3800.0,
            provided_storage_cf=4200.0,
            drawdown_hours=24.0,
            boundary_points=[(150.0, 10.0), (190.0, 10.0), (190.0, 40.0), (150.0, 40.0)],
            meta={
                "detention_design": {
                    "release_basis": "target_drawdown",
                    "target_drawdown_hours": 48.0,
                    "adequacy_status": "adequate",
                },
                "overflow_spillway": {
                    "crest_elev_ft": 99.5,
                    "assumed_capacity_cfs": 3.2,
                },
            },
        )
        inflow = StormNode(
            name="INLET-1",
            node_type=StormNodeType.INLET.value,
            point=StormPoint(120.0, 25.0, 100.0),
            rim_elev_ft=100.0,
            invert_elev_ft=97.0,
            contributing_runoff_cfs=0.35,
        )
        outfall = StormNode(
            name="OUTFALL-1",
            node_type=StormNodeType.OUTFALL.value,
            point=StormPoint(220.0, 0.0, 96.0),
            rim_elev_ft=96.0,
            invert_elev_ft=93.0,
        )

        result = BasinConnectionEngine().connect(
            BasinConnectionRequest(
                basin=basin,
                inflow_nodes=[inflow],
                outfall_node=outfall,
                allow_overflow_path=True,
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.summary.get("release_basis"), "target_drawdown")
        self.assertEqual(result.summary.get("adequacy_status"), "adequate")
        self.assertGreater(float(result.summary.get("spillway_capacity_cfs", 0.0)), 0.0)
        explain = dict((result.basin.meta or {}).get("explain") or {})
        self.assertEqual(dict(explain.get("outlet_summary") or {}).get("release_basis"), "target_drawdown")
        self.assertEqual(dict(explain.get("outlet_summary") or {}).get("adequacy_status"), "adequate")
        self.assertGreater(float(dict(explain.get("overflow_summary") or {}).get("spillway_capacity_cfs", 0.0)), 0.0)

    def test_planner_utility_summary_preserves_cover_and_separation_stats(self) -> None:
        out = planner.build_plan(
            {
                "project_name": "Utility Summary Stats",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "terrain": "4% slope west to east",
                "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
            }
        )
        utilities = dict((out.get("meta") or {}).get("utilities") or {})

        self.assertGreaterEqual(int(utilities.get("route_count") or 0), 0)
        self.assertIn("min_cover_ft", utilities)
        self.assertIn("min_horizontal_separation_ft", utilities)
        self.assertIn("min_vertical_separation_ft", utilities)
        self.assertIn("trunk_count", utilities)
        self.assertIn("service_count", utilities)
        self.assertIn("coordination", utilities)
        self.assertIn("sanitary_storm_conflict_count", dict(utilities.get("coordination") or {}))
        self.assertIn("utility_related_unresolved_conflict_count", dict(utilities.get("coordination") or {}))
        self.assertIn("reroute_resolution_count", dict(utilities.get("coordination") or {}))
        self.assertIn("vertical_adjustment_count", dict(utilities.get("coordination") or {}))


if __name__ == "__main__":
    unittest.main()
