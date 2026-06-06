from copy import deepcopy
import unittest

from backend.planning.production_depth import enrich_drainage_production_depth, enrich_water_production_depth
from backend.planning.depth_validators import (
    validate_profile_section_depth,
    validate_roadway_corridor_depth,
    validate_stormwater_depth,
    validate_water_system_depth,
)


def _complete_roadway_corridor_meta() -> dict:
    return {
        "alignments": [{"id": "ALG-ROAD-A", "name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
        "profiles": [
            {
                "id": "PROF-A",
                "name": "Road A Profile",
                "alignment_id": "ALG-ROAD-A",
                "profile_points": [
                    {"station_ft": 0.0, "elevation_ft": 100.0},
                    {"station_ft": 100.0, "elevation_ft": 101.0},
                ],
            }
        ],
        "intersections": [{"id": "INT-1", "point": {"x": 0.0, "y": 0.0}, "connected_alignments": ["ALG-ROAD-A", "Drive B"], "angle_deg": 90.0}],
        "curb_returns": [{"id": "CR-1", "intersection_id": "INT-1", "radius_ft": 25.0, "arc_points": [[0.0, 25.0], [7.3, 7.3], [25.0, 0.0]]}],
        "grading": {
            "surface_traceability": {
                "valid": True,
                "accepted_surfaces": True,
                "existing_surface_id": "EG-ACCEPTED-1",
                "proposed_surface_id": "FG-ACCEPTED-1",
            },
            "road_crown_controls": [
                {
                    "road_id": "ALG-ROAD-A",
                    "profile_id": "PROF-A",
                    "expected_crown_elev_ft": 100.25,
                    "actual_crown_elev_ft": 100.25,
                    "crown_tolerance_ft": 0.0,
                    "expected_cross_slope": 0.02,
                    "actual_cross_slope": 0.02,
                    "expected_left_cross_slope": 0.02,
                    "actual_left_cross_slope": 0.02,
                    "expected_right_cross_slope": 0.02,
                    "actual_right_cross_slope": 0.02,
                    "cross_slope_tolerance": 0.0,
                    "standard_id": "CITY-ROAD-2026",
                    "standard_status": "adopted",
                    "control_source": "roadway_profile_engine",
                }
            ],
            "curb_gutter_controls": [
                {
                    "road_id": "ALG-ROAD-A",
                    "alignment_id": "ALG-ROAD-A",
                    "expected_min_gutter_slope": 0.005,
                    "actual_gutter_slope": 0.006,
                    "standard_id": "CITY-ROAD-2026",
                    "standard_status": "adopted",
                    "control_source": "roadway_profile_engine",
                }
            ],
            "ada_path_checks": [
                {
                    "path_id": "SW-1",
                    "valid": True,
                    "expected_max_running_slope": 0.05,
                    "actual_running_slope": 0.04,
                    "expected_max_cross_slope": 0.02,
                    "actual_cross_slope": 0.015,
                    "standard_id": "ADA-2010",
                    "standard_status": "adopted",
                    "continuous": True,
                    "control_source": "finished_grade_surface",
                }
            ],
            "pad_tie_ins": [
                {
                    "building_id": "BLDG-1",
                    "valid": True,
                    "pad_elev_ft": 101.2,
                    "positive_drainage": True,
                    "proposed_surface_id": "FG-ACCEPTED-1",
                    "expected_max_tie_slope": 0.05,
                    "actual_tie_slope": 0.03,
                    "tie_in_elevations_ft": [101.2, 101.0],
                    "control_source": "accepted_proposed_surface",
                }
            ],
            "contours": [
                {
                    "contour_id": "FG-100",
                    "interval_ft": 2.0,
                    "proposed_surface_id": "FG-ACCEPTED-1",
                    "expected_min_contour_count": 1,
                    "contour_count": 2,
                    "sample_elevations_ft": [100.0, 102.0],
                    "source": "accepted_proposed_surface",
                }
            ],
            "contour_interval_ft": 2.0,
        },
        "sidewalks": [{"id": "SW-1", "path": [[0.0, 0.0], [100.0, 0.0]], "width_ft": 5.0, "continuity_validation": {"valid": True}}],
        "cross_sections": [
            {
                "station_ft": 0.0,
                "alignment_id": "ALG-ROAD-A",
                "section_points": [
                    {"offset_ft": -12.0, "elevation_ft": 99.8},
                    {"offset_ft": 0.0, "elevation_ft": 100.0},
                    {"offset_ft": 12.0, "elevation_ft": 99.8},
                ],
            }
        ],
    }


class DepthValidatorTests(unittest.TestCase):
    def test_stormwater_depth_blocks_missing_real_hydraulic_evidence(self) -> None:
        result = validate_stormwater_depth({"meta": {"storm_pipes": {"segments": [{"name": "P-1"}]}}})

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs HGL and EGL profiles from production hydraulic evidence.", result["blockers"])
        self.assertIn("Storm depth needs true tributary areas tied to pipes or catchments.", result["blockers"])
        self.assertEqual(len(result["blocker_details"]), len(result["blockers"]))
        self.assertTrue(result["blocker_details"][0]["next_action"])

    def test_stormwater_depth_passes_when_all_explicit_evidence_exists(self) -> None:
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1", "valid": True}],
                    },
                    "drainage": {
                        "coordination": {"preferred_outfall": {"name": "OUTFALL-1", "x": 120.0, "y": 20.0}},
                        "surface_controls": {"primary_low_point": {"x": 120.0, "y": 20.0}},
                        "catchments": [{"name": "A", "runoff_c": 0.8}],
                        "detention_routing": [
                            {
                                "basin": "B-1",
                                "routing_source": "hydrograph_engine",
                                "routing_method": "stage_storage_hydrograph",
                                "provided_storage_cf": 4200.0,
                                "release_cfs": 1.2,
                                "outlet_release_cfs": 1.2,
                                "outlet": {"type": "orifice", "release_cfs": 1.2, "source": "approved_outlet_fixture"},
                                "drawdown_hours": 18.0,
                                "stage_storage": [
                                    {"elevation_ft": 96.0, "storage_cf": 0.0},
                                    {"elevation_ft": 98.0, "storage_cf": 2100.0},
                                    {"elevation_ft": 100.0, "storage_cf": 4200.0},
                                ],
                            }
                        ],
                        "overflow_paths": [
                            {
                                "name": "OF-1",
                                "capacity_valid": True,
                                "capacity_cfs": 5.0,
                                "required_capacity_cfs": 4.0,
                                "source": "approved_spillway_fixture",
                            }
                        ],
                    },
                }
            }
        )

        self.assertTrue(result["production_ready"])
        self.assertEqual(result["hgl_egl_trace"]["expected"], "production_hgl_and_egl_profile_rows")
        self.assertEqual(result["hgl_egl_trace"]["actual_hgl_count"], 1)
        self.assertEqual(result["hgl_egl_trace"]["actual_egl_count"], 1)
        self.assertEqual(result["tailwater_backwater_trace"]["actual_tailwater_elev_ft"], 98.0)
        self.assertTrue(result["inlet_capacity_trace"][0]["actual_valid"])
        self.assertEqual(result["detention_routing_trace"][0]["expected_storage_cf"], 0.0)
        self.assertEqual(result["detention_routing_trace"][0]["actual_storage_cf"], 4200.0)
        self.assertEqual(result["overflow_capacity_trace"][0]["expected_capacity_cfs"], 4.0)
        self.assertEqual(result["overflow_capacity_trace"][0]["actual_capacity_cfs"], 5.0)
        self.assertTrue(result["expected_actual_checks"])

    def test_stormwater_depth_accepts_enriched_production_detention_outlet_drawdown(self) -> None:
        drainage = enrich_drainage_production_depth(
            {
                "coordination": {"preferred_outfall": {"name": "OUTFALL-1", "x": 120.0, "y": 20.0}},
                "surface_controls": {"primary_low_point": {"x": 120.0, "y": 20.0}},
                "catchments": [{"name": "A", "runoff_c": 0.8}],
                "basins": [
                    {
                        "name": "B-1",
                        "x": 20.0,
                        "y": 10.0,
                        "source": "survey_detention_design",
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
                                "release_cfs": 1.0,
                                "source": "approved_outlet_fixture",
                            },
                            "overflow_spillway": {
                                "capacity_cfs": 6.0,
                                "required_capacity_cfs": 4.0,
                                "source": "approved_spillway_fixture",
                            },
                        },
                    }
                ],
            }
        )
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1", "valid": True}],
                    },
                    "drainage": drainage,
                }
            }
        )

        self.assertTrue(result["production_ready"])

    def test_stormwater_depth_blocks_missing_basin_outfall_target(self) -> None:
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1", "valid": True}],
                    },
                    "drainage": {
                        "surface_controls": {"primary_low_point": {"x": 120.0, "y": 20.0}},
                        "catchments": [{"name": "A", "runoff_c": 0.8}],
                        "detention_routing": [
                            {
                                "basin": "B-1",
                                "routing_source": "hydrograph_engine",
                                "routing_method": "stage_storage_hydrograph",
                                "provided_storage_cf": 4200.0,
                                "release_cfs": 1.2,
                                "outlet_release_cfs": 1.2,
                                "outlet": {"type": "orifice", "release_cfs": 1.2, "source": "approved_outlet_fixture"},
                                "drawdown_hours": 18.0,
                                "stage_storage": [
                                    {"elevation_ft": 96.0, "storage_cf": 0.0},
                                    {"elevation_ft": 98.0, "storage_cf": 2100.0},
                                    {"elevation_ft": 100.0, "storage_cf": 4200.0},
                                ],
                            }
                        ],
                        "overflow_paths": [{"name": "OF-1", "capacity_valid": True, "capacity_cfs": 5.0, "required_capacity_cfs": 4.0, "source": "approved_spillway_fixture"}],
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs drainage-selected basin/outfall target evidence.", result["blockers"])

    def test_stormwater_depth_blocks_invalid_inlet_or_overflow_evidence(self) -> None:
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1", "valid": False, "bypass_cfs": 1.2}],
                    },
                    "drainage": {
                        "catchments": [{"name": "A", "runoff_c": 0.8}],
                        "detention_routing": [
                            {
                                "basin": "B-1",
                                "routing_source": "hydrograph_engine",
                                "routing_method": "stage_storage_hydrograph",
                                "provided_storage_cf": 4200.0,
                                "release_cfs": 1.2,
                                "outlet_release_cfs": 1.2,
                                "outlet": {"type": "orifice", "release_cfs": 1.2, "source": "approved_outlet_fixture"},
                                "drawdown_hours": 18.0,
                                "stage_storage": [
                                    {"elevation_ft": 96.0, "storage_cf": 0.0},
                                    {"elevation_ft": 98.0, "storage_cf": 2100.0},
                                    {"elevation_ft": 100.0, "storage_cf": 4200.0},
                                ],
                            }
                        ],
                        "overflow_analysis": {"valid": False, "missing_inputs": [{"basin": "B-1"}]},
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs passing inlet capacity, spread, and bypass checks.", result["blockers"])
        self.assertIn("Storm depth needs overflow routing evidence.", result["blockers"])

    def test_stormwater_depth_blocks_overflow_geometry_without_capacity(self) -> None:
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1", "valid": True}],
                    },
                    "drainage": {
                        "catchments": [{"name": "A", "runoff_c": 0.8}],
                        "detention_routing": [
                            {
                                "basin": "B-1",
                                "routing_source": "hydrograph_engine",
                                "routing_method": "stage_storage_outlet_drawdown",
                                "provided_storage_cf": 7200.0,
                                "release_cfs": 1.0,
                                "outlet_release_cfs": 1.0,
                                "outlet": {"type": "orifice", "release_cfs": 1.0, "source": "approved_outlet_fixture"},
                                "drawdown_hours": 2.0,
                                "stage_storage": [
                                    {"elevation_ft": 96.0, "storage_cf": 0.0},
                                    {"elevation_ft": 99.0, "storage_cf": 5400.0},
                                    {"elevation_ft": 101.0, "storage_cf": 7200.0},
                                ],
                            }
                        ],
                        "overflow_paths": [{"name": "OF-1"}],
                        "overflow_analysis": {
                            "valid": True,
                            "production_valid": False,
                            "capacity_status": "capacity_review_needed",
                        },
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs overflow routing evidence.", result["blockers"])

    def test_stormwater_depth_blocks_concept_hydraulic_and_detention_evidence(self) -> None:
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0, "hydraulic_depth_source": "concept_fallback"}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2, "hydraulic_depth_source": "concept_fallback"}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1", "valid": True}],
                    },
                    "drainage": {
                        "catchments": [{"name": "A", "runoff_c": 0.8}],
                        "detention_routing": [
                            {
                                "basin": "B-1",
                                "routing_source": "concept_detention_design",
                                "routing_method": "stage_storage_concept",
                            }
                        ],
                        "overflow_paths": [{"name": "OF-1"}],
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs HGL and EGL profiles from production hydraulic evidence.", result["blockers"])
        self.assertIn("Storm depth needs production detention stage-storage/outlet/drawdown routing.", result["blockers"])

    def test_stormwater_depth_blocks_unpassed_inlet_and_one_sided_concept_profiles(self) -> None:
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2, "hydraulic_depth_source": "concept_proxy"}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1"}],
                    },
                    "drainage": {
                        "catchments": [{"name": "A", "runoff_c": 0.8}],
                        "detention_routing": [
                            {
                                "basin": "B-1",
                                "routing_source": "hydrograph_engine",
                                "routing_method": "stage_storage_hydrograph",
                                "provided_storage_cf": 4200.0,
                                "release_cfs": 1.2,
                                "outlet_release_cfs": 1.2,
                                "outlet": {"type": "orifice", "release_cfs": 1.2, "source": "approved_outlet_fixture"},
                                "drawdown_hours": 18.0,
                                "stage_storage": [
                                    {"elevation_ft": 96.0, "storage_cf": 0.0},
                                    {"elevation_ft": 98.0, "storage_cf": 2100.0},
                                    {"elevation_ft": 100.0, "storage_cf": 4200.0},
                                ],
                            }
                        ],
                        "overflow_paths": [{"name": "OF-1"}],
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs HGL and EGL profiles from production hydraulic evidence.", result["blockers"])
        self.assertIn("Storm depth needs passing inlet capacity, spread, and bypass checks.", result["blockers"])

    def test_stormwater_depth_blocks_detention_routing_without_outlet_drawdown_or_storage(self) -> None:
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1", "valid": True}],
                    },
                    "drainage": {
                        "catchments": [{"name": "A", "runoff_c": 0.8}],
                        "detention_routing": [{"basin": "B-1", "routing_source": "hydrograph_engine"}],
                        "overflow_paths": [{"name": "OF-1"}],
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs production detention stage-storage/outlet/drawdown routing.", result["blockers"])
        self.assertFalse(result["detention_routing_trace"][0]["valid"])

    def test_stormwater_depth_blocks_under_sized_detention_storage(self) -> None:
        result = validate_stormwater_depth(
            {
                "meta": {
                    "storm_pipes": {
                        "segments": [{"name": "P-1", "tributary_area_sf": 10000.0}],
                        "hgl_profile": [{"station_ft": 0.0, "hgl_ft": 99.0}],
                        "egl_profile": [{"station_ft": 0.0, "egl_ft": 99.2}],
                        "tailwater_elev_ft": 98.0,
                        "inlet_capacity_checks": [{"inlet": "CB-1", "valid": True}],
                    },
                    "drainage": {
                        "catchments": [{"name": "A", "runoff_c": 0.8}],
                        "detention_routing": [
                            {
                                "basin": "B-1",
                                "routing_source": "hydrograph_engine",
                                "routing_method": "stage_storage_hydrograph",
                                "required_storage_cf": 8000.0,
                                "provided_storage_cf": 4200.0,
                                "release_cfs": 1.2,
                                "outlet_release_cfs": 1.2,
                                "outlet": {"type": "orifice", "release_cfs": 1.2, "source": "approved_outlet_fixture"},
                                "drawdown_hours": 18.0,
                                "stage_storage": [
                                    {"elevation_ft": 96.0, "storage_cf": 0.0},
                                    {"elevation_ft": 98.0, "storage_cf": 2100.0},
                                    {"elevation_ft": 100.0, "storage_cf": 4200.0},
                                ],
                            }
                        ],
                        "overflow_paths": [{"name": "OF-1"}],
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs production detention stage-storage/outlet/drawdown routing.", result["blockers"])

    def test_water_depth_requires_pressure_fire_flow_looping_and_velocity(self) -> None:
        water = enrich_water_production_depth(
            {
                "source_pressure_psi": 72.0,
                "source_node": "SRC",
                "standard_id": "CITY-WATER-2026",
                "standard_status": "adopted",
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
        )
        result = validate_water_system_depth(
            {
                "meta": {
                    "water": water
                }
            }
        )

        self.assertTrue(result["production_ready"])

    def test_water_depth_blocks_thin_boolean_validation_records(self) -> None:
        result = validate_water_system_depth(
            {
                "meta": {
                    "water": {
                        "segments": [
                            {"start_node": "A", "end_node": "B", "velocity_fps": 3.0},
                            {"start_node": "B", "end_node": "C", "velocity_fps": 3.1},
                            {"start_node": "C", "end_node": "A", "velocity_fps": 2.8},
                        ],
                        "pressure_zones": [{"name": "Z1"}],
                        "hydrants": [{"id": "H1"}, {"id": "H2"}],
                        "hydrant_spacing_validation": {"valid": True},
                        "fire_flow_validation": {"valid": True},
                        "pressure_validation": {"valid": True},
                        "velocity_checks": [{"segment": "W-1", "velocity_fps": 3.0, "valid": True}],
                        "sizing_optimization": {"status": "checked"},
                    }
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Water depth needs passing hydrant spacing coverage.", result["blockers"])
        self.assertIn("Water depth needs passing fire-flow validation.", result["blockers"])
        self.assertIn("Water depth needs passing pressure validation.", result["blockers"])

    def test_water_depth_blocks_failed_pressure_spacing_and_velocity_checks(self) -> None:
        result = validate_water_system_depth(
            {
                "meta": {
                    "water": {
                        "segments": [
                            {"start_node": "A", "end_node": "B", "velocity_fps": 0.0},
                            {"start_node": "B", "end_node": "C", "velocity_fps": 3.1},
                            {"start_node": "C", "end_node": "A", "velocity_fps": 2.8},
                        ],
                        "pressure_zones": [{"name": "Z1"}],
                        "hydrants": [{"id": "H1"}, {"id": "H2"}],
                        "hydrant_spacing_validation": {"valid": False},
                        "fire_flow_validation": {"valid": True},
                        "pressure_validation": {"valid": False},
                        "sizing_optimization": {"selected": "8-inch loop"},
                    }
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Water depth needs passing hydrant spacing coverage.", result["blockers"])
        self.assertIn("Water depth needs passing pressure validation.", result["blockers"])
        self.assertIn("Water depth needs passing velocity checks.", result["blockers"])

    def test_water_depth_blocks_available_fire_flow_without_validation(self) -> None:
        result = validate_water_system_depth(
            {
                "meta": {
                    "water": {
                        "segments": [
                            {"start_node": "A", "end_node": "B", "velocity_fps": 3.0},
                            {"start_node": "B", "end_node": "C", "velocity_fps": 3.1},
                            {"start_node": "C", "end_node": "A", "velocity_fps": 2.8},
                        ],
                        "pressure_zones": [{"name": "Z1"}],
                        "hydrants": [{"id": "H1"}, {"id": "H2"}],
                        "hydrant_spacing_validation": {"valid": True},
                        "available_fire_flow_gpm": 1500.0,
                        "pressure_validation": {"valid": True},
                        "sizing_optimization": {"selected": "8-inch loop"},
                    }
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Water depth needs passing fire-flow validation.", result["blockers"])

    def test_roadway_depth_blocks_missing_corridor_controls(self) -> None:
        result = validate_roadway_corridor_depth({"meta": {"alignments": [{"name": "Road A"}]}})

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs profiles.", result["blockers"])
        self.assertIn("Roadway depth needs corridor sections.", result["blockers"])

    def test_roadway_depth_passes_with_explicit_corridor_evidence(self) -> None:
        result = validate_roadway_corridor_depth({"meta": _complete_roadway_corridor_meta()})

        self.assertTrue(result["production_ready"])
        self.assertEqual(result["road_crown_trace"][0]["expected_crown_elev_ft"], 100.25)
        self.assertEqual(result["road_crown_trace"][0]["actual_crown_elev_ft"], 100.25)
        self.assertEqual(result["road_crown_trace"][0]["expected_cross_slope"], 0.02)
        self.assertEqual(result["road_crown_trace"][0]["actual_cross_slope"], 0.02)
        self.assertEqual(result["road_crown_trace"][0]["expected_left_cross_slope"], 0.02)
        self.assertEqual(result["road_crown_trace"][0]["actual_left_cross_slope"], 0.02)
        self.assertEqual(result["road_crown_trace"][0]["expected_right_cross_slope"], 0.02)
        self.assertEqual(result["road_crown_trace"][0]["actual_right_cross_slope"], 0.02)
        self.assertEqual(result["curb_gutter_trace"][0]["road_id"], "ALG-ROAD-A")
        self.assertEqual(result["curb_gutter_trace"][0]["expected_min_gutter_slope"], 0.005)
        self.assertEqual(result["curb_gutter_trace"][0]["actual_gutter_slope"], 0.006)
        self.assertEqual(result["ada_path_trace"][0]["expected_max_running_slope"], 0.05)
        self.assertEqual(result["ada_path_trace"][0]["actual_running_slope"], 0.04)
        self.assertEqual(result["ada_path_trace"][0]["expected_max_cross_slope"], 0.02)
        self.assertEqual(result["ada_path_trace"][0]["actual_cross_slope"], 0.015)
        self.assertEqual(result["pad_tie_in_trace"][0]["expected_proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertEqual(result["pad_tie_in_trace"][0]["actual_proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertEqual(result["pad_tie_in_trace"][0]["expected_max_tie_slope"], 0.05)
        self.assertEqual(result["pad_tie_in_trace"][0]["actual_tie_slope"], 0.03)
        self.assertEqual(result["contour_trace"][0]["expected_proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertEqual(result["contour_trace"][0]["actual_proposed_surface_id"], "FG-ACCEPTED-1")
        self.assertEqual(result["contour_trace"][0]["expected_min_contour_count"], 1)
        self.assertEqual(result["contour_trace"][0]["actual_contour_count"], 2)
        self.assertEqual(result["contour_trace"][0]["sample_elevations_ft"], [100.0, 102.0])
        self.assertTrue(result["expected_actual_checks"])

    def test_roadway_depth_blocks_missing_expected_actual_and_surface_trace(self) -> None:
        meta = deepcopy(_complete_roadway_corridor_meta())
        meta["grading"]["road_crown_controls"][0].pop("expected_cross_slope")
        meta["grading"]["curb_gutter_controls"][0].pop("alignment_id")
        meta["grading"]["surface_traceability"].pop("proposed_surface_id")
        meta["grading"]["pad_tie_ins"][0].pop("proposed_surface_id")
        meta["grading"]["contours"][0].pop("proposed_surface_id")

        result = validate_roadway_corridor_depth({"meta": meta})

        self.assertFalse(result["production_ready"])
        self.assertFalse(result["road_crown_trace"][0]["valid"])
        self.assertFalse(result["pad_tie_in_trace"][0]["valid"])
        self.assertFalse(result["contour_trace"][0]["valid"])
        self.assertIn("Roadway depth needs verified road crown controls with expected/actual crown and cross-slope values.", result["blockers"])
        self.assertIn("Roadway depth needs accepted grading surface traceability.", result["blockers"])
        self.assertIn("Roadway depth needs pad tie-ins tied to accepted proposed surface IDs.", result["blockers"])
        self.assertIn("Roadway depth needs contours tied to accepted proposed surface evidence.", result["blockers"])

    def test_roadway_depth_blocks_thin_corridor_presence(self) -> None:
        result = validate_roadway_corridor_depth(
            {
                "meta": {
                    "alignments": [{"name": "Road A"}],
                    "profiles": [{"name": "Road A Profile"}],
                    "intersections": [{"id": "INT-1"}],
                    "curb_returns": [{"id": "CR-1"}],
                    "grading_detail": {
                        "road_crown_controls": [{"road": "Road A", "profile_id": "PROF-A", "standard": "City local street"}],
                        "ada_path_checks": [{"path": "SW-1", "valid": True}],
                    },
                    "sidewalks": [{"id": "SW-1"}],
                    "cross_sections": [{"station_ft": 0.0}],
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs alignments.", result["blockers"])
        self.assertIn("Roadway depth needs profiles.", result["blockers"])
        self.assertIn("Roadway depth needs intersection geometry.", result["blockers"])
        self.assertIn("Roadway depth needs curb-return geometry.", result["blockers"])
        self.assertIn("Roadway depth needs sidewalk/path geometry.", result["blockers"])
        self.assertIn("Roadway depth needs corridor sections.", result["blockers"])

    def test_roadway_depth_blocks_concept_crown_controls(self) -> None:
        result = validate_roadway_corridor_depth(
            {
                "meta": {
                    "alignments": [{"name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
                    "profiles": [{"name": "Road A Profile", "alignment_owner": "Road A", "profile_points": [{"station_ft": 0.0, "elevation_ft": 100.0}, {"station_ft": 100.0, "elevation_ft": 101.0}]}],
                    "intersections": [{"id": "INT-1", "point": {"x": 0.0, "y": 0.0}, "connected_alignments": ["Road A", "Drive B"], "angle_deg": 90.0}],
                    "curb_returns": [{"id": "CR-1", "intersection_id": "INT-1", "radius_ft": 25.0, "arc_points": [[0.0, 25.0], [7.3, 7.3], [25.0, 0.0]]}],
                    "grading_detail": {
                        "road_crown_controls": [
                            {
                                "road": "Road A",
                                "control_source": "grade_element",
                                "truth_label": "concept road crown control; verify profile and cross-slope against road standard.",
                            }
                        ],
                        "ada_path_checks": [{"path": "SW-1", "valid": True, "max_running_slope": 0.04, "max_cross_slope": 0.015, "standard": "ADA", "standard_status": "adopted"}],
                    },
                    "sidewalks": [{"id": "SW-1", "path": [[0.0, 0.0], [100.0, 0.0]], "width_ft": 5.0, "continuity_validation": {"valid": True}}],
                    "cross_sections": [{"station_ft": 0.0, "alignment_owner": "Road A", "section_points": [{"offset_ft": -12.0}, {"offset_ft": 0.0}, {"offset_ft": 12.0}]}],
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs verified road crown controls with expected/actual crown and cross-slope values.", result["blockers"])

    def test_roadway_depth_blocks_failed_ada_checks(self) -> None:
        result = validate_roadway_corridor_depth(
            {
                "meta": {
                    "alignments": [{"name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
                    "profiles": [{"name": "Road A Profile", "alignment_owner": "Road A", "profile_points": [{"station_ft": 0.0, "elevation_ft": 100.0}, {"station_ft": 100.0, "elevation_ft": 101.0}]}],
                    "intersections": [{"id": "INT-1", "point": {"x": 0.0, "y": 0.0}, "connected_alignments": ["Road A", "Drive B"], "angle_deg": 90.0}],
                    "curb_returns": [{"id": "CR-1", "intersection_id": "INT-1", "radius_ft": 25.0, "arc_points": [[0.0, 25.0], [7.3, 7.3], [25.0, 0.0]]}],
                    "grading_detail": {
                        "road_crown_controls": [{"road": "Road A", "profile_id": "PROF-A", "standard": "City local street"}],
                        "ada_path_checks": [{"path": "SW-1", "valid": False}],
                    },
                    "sidewalks": [{"id": "SW-1", "path": [[0.0, 0.0], [100.0, 0.0]], "width_ft": 5.0, "continuity_validation": {"valid": True}}],
                    "cross_sections": [{"station_ft": 0.0, "alignment_owner": "Road A", "section_points": [{"offset_ft": -12.0}, {"offset_ft": 0.0}, {"offset_ft": 12.0}]}],
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs passing ADA checks.", result["blockers"])

    def test_roadway_depth_blocks_curb_return_without_arc_geometry(self) -> None:
        result = validate_roadway_corridor_depth(
            {
                "meta": {
                    "alignments": [{"name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
                    "profiles": [{"name": "Road A Profile", "alignment_owner": "Road A", "profile_points": [{"station_ft": 0.0, "elevation_ft": 100.0}, {"station_ft": 100.0, "elevation_ft": 101.0}]}],
                    "intersections": [{"id": "INT-1", "point": {"x": 0.0, "y": 0.0}, "connected_alignments": ["Road A", "Drive B"], "angle_deg": 90.0}],
                    "curb_returns": [{"id": "CR-1", "intersection_id": "INT-1", "radius_ft": 25.0}],
                    "grading_detail": {
                        "road_crown_controls": [{"road": "Road A", "profile_id": "PROF-A", "standard": "City local street"}],
                        "ada_path_checks": [{"path": "SW-1", "valid": True, "max_running_slope": 0.04, "max_cross_slope": 0.015, "standard": "ADA", "standard_status": "adopted"}],
                    },
                    "sidewalks": [{"id": "SW-1", "path": [[0.0, 0.0], [100.0, 0.0]], "width_ft": 5.0, "continuity_validation": {"valid": True}}],
                    "cross_sections": [{"station_ft": 0.0, "alignment_owner": "Road A", "section_points": [{"offset_ft": -12.0}, {"offset_ft": 0.0}, {"offset_ft": 12.0}]}],
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs curb-return geometry.", result["blockers"])

    def test_roadway_depth_blocks_intersection_without_angle_or_leg_geometry(self) -> None:
        result = validate_roadway_corridor_depth(
            {
                "meta": {
                    "alignments": [{"name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
                    "profiles": [{"name": "Road A Profile", "alignment_owner": "Road A", "profile_points": [{"station_ft": 0.0, "elevation_ft": 100.0}, {"station_ft": 100.0, "elevation_ft": 101.0}]}],
                    "intersections": [{"id": "INT-1", "point": {"x": 0.0, "y": 0.0}, "connected_alignments": ["Road A", "Drive B"]}],
                    "curb_returns": [{"id": "CR-1", "intersection_id": "INT-1", "radius_ft": 25.0, "arc_points": [[0.0, 25.0], [7.3, 7.3], [25.0, 0.0]]}],
                    "grading_detail": {
                        "road_crown_controls": [{"road": "Road A", "profile_id": "PROF-A", "standard": "City local street"}],
                        "ada_path_checks": [{"path": "SW-1", "valid": True, "max_running_slope": 0.04, "max_cross_slope": 0.015, "standard": "ADA", "standard_status": "adopted"}],
                    },
                    "sidewalks": [{"id": "SW-1", "path": [[0.0, 0.0], [100.0, 0.0]], "width_ft": 5.0, "continuity_validation": {"valid": True}}],
                    "cross_sections": [{"station_ft": 0.0, "alignment_owner": "Road A", "section_points": [{"offset_ft": -12.0}, {"offset_ft": 0.0}, {"offset_ft": 12.0}]}],
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs intersection geometry.", result["blockers"])

    def test_roadway_depth_blocks_broken_sidewalk_and_ada_continuity(self) -> None:
        result = validate_roadway_corridor_depth(
            {
                "meta": {
                    "alignments": [{"name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
                    "profiles": [{"name": "Road A Profile", "alignment_owner": "Road A", "profile_points": [{"station_ft": 0.0, "elevation_ft": 100.0}, {"station_ft": 100.0, "elevation_ft": 101.0}]}],
                    "intersections": [{"id": "INT-1", "point": {"x": 0.0, "y": 0.0}, "connected_alignments": ["Road A", "Drive B"], "angle_deg": 90.0}],
                    "curb_returns": [{"id": "CR-1", "intersection_id": "INT-1", "radius_ft": 25.0, "arc_points": [[0.0, 25.0], [7.3, 7.3], [25.0, 0.0]]}],
                    "grading_detail": {
                        "road_crown_controls": [{"road": "Road A", "profile_id": "PROF-A", "standard": "City local street"}],
                        "ada_path_checks": [{"path": "SW-1", "valid": True, "max_running_slope": 0.04, "max_cross_slope": 0.015, "standard": "ADA", "standard_status": "adopted", "continuity_validation": {"valid": False}}],
                    },
                    "sidewalks": [{"id": "SW-1", "path": [[0.0, 0.0], [100.0, 0.0]], "width_ft": 5.0, "continuity_validation": {"valid": False}}],
                    "cross_sections": [{"station_ft": 0.0, "alignment_owner": "Road A", "section_points": [{"offset_ft": -12.0}, {"offset_ft": 0.0}, {"offset_ft": 12.0}]}],
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs sidewalk/path geometry.", result["blockers"])
        self.assertIn("Roadway depth needs passing ADA checks.", result["blockers"])

    def test_profile_section_depth_passes_traceable_profiles_sections_and_bands(self) -> None:
        result = validate_profile_section_depth(
            {
                "meta": {
                    "alignments": [{"id": "ALG-ROAD-1", "name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
                    "grading": {
                        "surface_traceability": {
                            "valid": True,
                            "accepted_surfaces": True,
                            "existing_surface_id": "EG-1",
                            "proposed_surface_id": "FG-1",
                        }
                    },
                    "profiles": [
                        {
                            "name": "Road A Profile",
                            "alignment_id": "ALG-ROAD-1",
                            "stations": [{"station_ft": 0.0}, {"station_ft": 100.0}],
                            "profile_bands": [
                                {"system": "storm", "segment_id": "STM-1"},
                                {"system": "sanitary", "segment_id": "SAN-1"},
                                {"system": "water", "segment_id": "W-1"},
                            ],
                        }
                    ],
                    "cross_sections": [
                        {
                            "name": "Road A Section 1",
                            "alignment_id": "ALG-ROAD-1",
                            "station_ft": 50.0,
                            "existing_surface_id": "EG-1",
                            "proposed_surface_id": "FG-1",
                            "samples": [{"offset_ft": -12.0}, {"offset_ft": 0.0}, {"offset_ft": 12.0}],
                        }
                    ],
                    "storm_pipes": {"segments": [{"id": "STM-1"}]},
                    "sanitary": {"segments": [{"id": "SAN-1"}]},
                    "utilities": {"segments": [{"id": "W-1", "system": "water"}]},
                    "export_audit": {
                        "canonical_profile_count": 1,
                        "canonical_cross_section_count": 1,
                        "requested_vs_produced": {
                            "missing_requested_profiles": False,
                            "missing_requested_sections": False,
                        },
                    },
                }
            }
        )

        self.assertTrue(result["production_ready"])
        self.assertEqual(result["profile_trace_checks"][0]["expected_alignment_ids"], ["ALG-ROAD-1"])
        self.assertEqual(result["profile_trace_checks"][0]["actual_alignment_id"], "ALG-ROAD-1")
        self.assertEqual(result["section_trace_checks"][0]["expected_existing_surface_id"], "EG-1")
        self.assertEqual(result["section_trace_checks"][0]["actual_existing_surface_id"], "EG-1")
        self.assertEqual({row["system"]: row["actual_count"] for row in result["profile_band_checks"]}, {"storm": 1, "sanitary": 1, "water": 1})
        self.assertTrue(result["export_linkage"]["valid"])

    def test_profile_section_depth_blocks_missing_alignment_surface_bands_and_wall_evidence(self) -> None:
        result = validate_profile_section_depth(
            {
                "meta": {
                    "alignments": [{"id": "ALG-ROAD-1", "name": "Road A", "points": [[0.0, 0.0], [100.0, 0.0]]}],
                    "grading": {
                        "surface_traceability": {
                            "valid": False,
                            "accepted_surfaces": False,
                            "existing_surface_id": "EG-1",
                        }
                    },
                    "profiles": [{"name": "Road A Profile", "alignment_id": "ALG-MISSING", "stations": [{"station_ft": 0.0}, {"station_ft": 100.0}]}],
                    "cross_sections": [
                        {
                            "name": "Road A Section 1",
                            "alignment_id": "ALG-ROAD-1",
                            "station_ft": 50.0,
                            "existing_surface_id": "EG-1",
                            "samples": [{"offset_ft": -12.0}, {"offset_ft": 0.0}, {"offset_ft": 12.0}],
                        }
                    ],
                    "storm_pipes": {"segments": [{"id": "STM-1"}]},
                    "retaining_walls": [{"id": "RW-1"}],
                    "export_audit": {
                        "canonical_profile_count": 0,
                        "canonical_cross_section_count": 0,
                        "requested_vs_produced": {
                            "missing_requested_profiles": True,
                            "missing_requested_sections": True,
                        },
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertEqual(result["profile_trace_checks"][0]["expected_alignment_ids"], ["ALG-ROAD-1"])
        self.assertEqual(result["profile_trace_checks"][0]["actual_alignment_id"], "ALG-MISSING")
        self.assertEqual(result["surface_traceability"]["missing_inputs"], ["accepted_surfaces", "proposed_surface_id"])
        self.assertEqual(result["profile_band_checks"][0]["system"], "storm")
        self.assertEqual(result["profile_band_checks"][0]["actual_count"], 0)
        self.assertFalse(result["retaining_wall_section_check"]["valid"])
        self.assertFalse(result["export_linkage"]["valid"])
        self.assertIn("Profile/section depth needs every profile to trace a canonical alignment ID.", result["blockers"])
        self.assertIn("Profile/section depth needs accepted existing/proposed surface IDs.", result["blockers"])
        self.assertIn("Profile/section depth needs profile band rows for existing storm, sanitary, and water systems.", result["blockers"])
        self.assertIn("Profile/section depth needs retaining wall section and tie-in evidence when wall scope exists.", result["blockers"])
        self.assertIn("Profile/section depth needs export/profile-section linkage when profile or section deliverables are requested.", result["blockers"])


if __name__ == "__main__":
    unittest.main()
