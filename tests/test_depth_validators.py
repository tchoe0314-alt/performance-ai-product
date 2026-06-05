import unittest

from backend.planning.production_depth import enrich_drainage_production_depth, enrich_water_production_depth
from backend.planning.depth_validators import (
    validate_roadway_corridor_depth,
    validate_stormwater_depth,
    validate_water_system_depth,
)


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

        self.assertTrue(result["production_ready"])

    def test_stormwater_depth_accepts_enriched_production_detention_outlet_drawdown(self) -> None:
        drainage = enrich_drainage_production_depth(
            {
                "coordination": {"preferred_outfall": {"name": "OUTFALL-1", "x": 120.0, "y": 20.0}},
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

    def test_water_depth_requires_pressure_fire_flow_looping_and_velocity(self) -> None:
        water = enrich_water_production_depth(
            {
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

        self.assertTrue(result["production_ready"])

    def test_roadway_depth_blocks_concept_crown_controls(self) -> None:
        result = validate_roadway_corridor_depth(
            {
                "meta": {
                    "alignments": [{"name": "Road A"}],
                    "profiles": [{"name": "Road A Profile"}],
                    "intersections": [{"id": "INT-1"}],
                    "curb_returns": [{"id": "CR-1"}],
                    "grading_detail": {
                        "road_crown_controls": [
                            {
                                "road": "Road A",
                                "control_source": "grade_element",
                                "truth_label": "concept road crown control; verify profile and cross-slope against road standard.",
                            }
                        ],
                        "ada_path_checks": [{"path": "SW-1", "valid": True}],
                    },
                    "sidewalks": [{"id": "SW-1"}],
                    "cross_sections": [{"station_ft": 0.0}],
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs verified road crown controls tied to a profile or standard.", result["blockers"])

    def test_roadway_depth_blocks_failed_ada_checks(self) -> None:
        result = validate_roadway_corridor_depth(
            {
                "meta": {
                    "alignments": [{"name": "Road A"}],
                    "profiles": [{"name": "Road A Profile"}],
                    "intersections": [{"id": "INT-1"}],
                    "curb_returns": [{"id": "CR-1"}],
                    "grading_detail": {
                        "road_crown_controls": [{"road": "Road A", "profile_id": "PROF-A", "standard": "City local street"}],
                        "ada_path_checks": [{"path": "SW-1", "valid": False}],
                    },
                    "sidewalks": [{"id": "SW-1"}],
                    "cross_sections": [{"station_ft": 0.0}],
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Roadway depth needs passing ADA checks.", result["blockers"])


if __name__ == "__main__":
    unittest.main()
