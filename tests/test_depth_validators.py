import unittest

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
                        "detention_routing": [{"basin": "B-1", "routing_source": "hydrograph_engine"}],
                        "overflow_paths": [{"name": "OF-1"}],
                    },
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
                        "detention_routing": [{"basin": "B-1", "routing_source": "hydrograph_engine"}],
                        "overflow_analysis": {"valid": False, "missing_inputs": [{"basin": "B-1"}]},
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs passing inlet capacity, spread, and bypass checks.", result["blockers"])
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
                        "detention_routing": [{"basin": "B-1", "routing_source": "hydrograph_engine"}],
                        "overflow_paths": [{"name": "OF-1"}],
                    },
                }
            }
        )

        self.assertFalse(result["production_ready"])
        self.assertIn("Storm depth needs HGL and EGL profiles from production hydraulic evidence.", result["blockers"])
        self.assertIn("Storm depth needs passing inlet capacity, spread, and bypass checks.", result["blockers"])

    def test_water_depth_requires_pressure_fire_flow_looping_and_velocity(self) -> None:
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
                        "sizing_optimization": {"selected": "8-inch loop"},
                    }
                }
            }
        )

        self.assertTrue(result["production_ready"])

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
