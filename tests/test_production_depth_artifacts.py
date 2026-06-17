import math
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
from backend.planning.depth_validators import validate_stormwater_depth, validate_water_system_depth
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
                    "from": "INLET-1",
                    "to": "BASIN-1",
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
        drainage = {
            "coordination": {"preferred_outfall": {"name": "BASIN-1", "x": 80.0, "y": 0.0, "z": 96.0}},
            "structures": [{"name": "INLET-1", "estimated_flow_cfs": 1.4}],
            "overflow_paths": [{"name": "OF-1", "capacity_valid": True, "capacity_cfs": 4.0, "required_capacity_cfs": 3.0, "source": "approved_spillway_fixture"}],
            "overflow_analysis": {"valid": True, "production_valid": True},
            "surface_controls": {"primary_low_point": {"x": 80.0, "y": 0.0}},
        }

        enriched = enrich_storm_production_depth(storm, drainage)

        self.assertTrue(enriched["drainage_target_validation"]["valid"])
        self.assertEqual(enriched["drainage_target_validation"]["target_name"], "BASIN-1")
        self.assertEqual(enriched["target_outfall"]["truth_source"], "drainage_target_validation")
        self.assertTrue(enriched["hgl_profile"])
        self.assertTrue(enriched["egl_profile"])
        self.assertEqual(enriched["tailwater_elev_ft"], 96.0)
        self.assertTrue(enriched["overflow_analysis"]["production_valid"])
        self.assertEqual(enriched["overflow_analysis"]["missing_inputs"], [])
        self.assertEqual(enriched["inlet_capacity_checks"][0]["inlet"], "INLET-1")
        self.assertEqual(enriched["inlet_capacity_checks"][0]["capacity_source"], "storm_inlet_engine_default")
        self.assertIn("capture_efficiency", enriched["inlet_capacity_checks"][0])
        self.assertEqual(enriched["controlling_segment"], "P-1")

    def test_storm_depth_blocks_target_and_overflow_without_drainage_terrain_evidence(self) -> None:
        storm = {
            "success": True,
            "segments": [
                {
                    "pipe": "P-NO-TARGET",
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
        }
        drainage = {
            "overflow_paths": [{"name": "OF-1", "capacity_valid": True, "capacity_cfs": 4.0, "required_capacity_cfs": 3.0, "source": "approved_spillway_fixture"}],
            "overflow_analysis": {"valid": True, "production_valid": True},
        }

        enriched = enrich_storm_production_depth(storm, drainage)

        self.assertFalse(enriched["drainage_target_validation"]["valid"])
        self.assertEqual(enriched["drainage_target_validation"]["missing_inputs"], ["drainage.coordination.preferred_outfall", "drainage.basins"])
        self.assertFalse(enriched["overflow_analysis"]["production_valid"])
        self.assertEqual(enriched["overflow_analysis"]["missing_inputs"], ["drainage.terrain_evidence"])

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
        self.assertIn("missing_tailwater", enriched["hydraulic_profile_evidence"]["labels"])
        self.assertNotIn("tailwater_elev_ft", enriched)
        self.assertFalse(enriched["backwater_validation"]["valid"])
        self.assertTrue(enriched["hydraulic_engine_summary"]["truth_label"])

    def test_storm_depth_generates_traceable_hgl_egl_from_complete_network(self) -> None:
        diameter_ft = 2.0
        slope = 0.01
        mannings_n = 0.013
        full_capacity = (1.486 / mannings_n) * (math.pi * diameter_ft**2 / 4.0) * (0.5 ** (2.0 / 3.0)) * (slope**0.5)
        design_flow = full_capacity / 2.0
        flow_area = math.pi * diameter_ft**2 / 8.0
        velocity = design_flow / flow_area
        velocity_head = (velocity * velocity) / (2.0 * 32.2)
        minor_loss = 0.2 * velocity_head
        expected_hgl_start = 100.0 + 1.0 + minor_loss
        expected_hgl_end = 99.0 + 1.0
        expected_egl_start = expected_hgl_start + velocity_head
        expected_egl_end = expected_hgl_end + velocity_head
        storm = {
            "success": True,
            "segments": [
                {
                    "pipe": "P-HGL",
                    "from": "IN-1",
                    "to": "OUT-1",
                    "path": [[0.0, 0.0], [100.0, 0.0]],
                    "diameter_in": 24.0,
                    "flow_cfs": design_flow,
                    "slope_ft_ft": slope,
                    "mannings_n": mannings_n,
                    "start_invert_ft": 100.0,
                    "end_invert_ft": 99.0,
                    "tributary_area_sf": 12000.0,
                }
            ],
            "target_outfall": {"name": "OUT-1", "z": 98.5},
        }
        drainage = {
            "coordination": {"preferred_outfall": {"name": "OUT-1", "x": 100.0, "y": 0.0, "z": 98.5}},
            "surface_controls": {"primary_low_point": {"x": 100.0, "y": 0.0}, "source": "accepted_survey_control_fixture", "accepted_control": True},
            "hydrology": {
                "method": "rational_method",
                "drainage_area_sf": 12000.0,
                "intensity_in_hr": 4.25,
                "time_of_concentration_min": 12.0,
                "rainfall_source": "accepted_city_idf_fixture",
                "standard_id": "CITY-STORM-2026",
                "standard_status": "adopted",
                "source_confidence": "accepted_controlled_fixture",
                "assumptions": {"runoff_method": "rational_method", "time_of_concentration_min": 12.0},
            },
            "catchments": [{"name": "C-1", "runoff_c": 0.8, "area_sf": 12000.0}],
            "structures": [{"name": "IN-1", "estimated_flow_cfs": design_flow}],
            "detention_routing": [
                {
                    "basin": "B-1",
                    "routing_source": "hydrograph_engine",
                    "routing_method": "stage_storage_hydrograph",
                    "provided_storage_cf": 5000.0,
                    "release_cfs": 1.0,
                    "drawdown_hours": 18.0,
                    "stage_storage": [
                        {"elevation_ft": 96.0, "storage_cf": 0.0},
                        {"elevation_ft": 99.0, "storage_cf": 5000.0},
                    ],
                }
            ],
            "overflow_paths": [
                {"name": "OF-1", "capacity_valid": True, "capacity_cfs": 5.0, "required_capacity_cfs": 4.0, "source": "approved_spillway_fixture"}
            ],
            "overflow_analysis": {"valid": True, "production_valid": True},
        }

        enriched = enrich_storm_production_depth(storm, drainage)
        evidence = enriched["hydraulic_profile_evidence"]
        hgl = enriched["hgl_profile"]
        egl = enriched["egl_profile"]

        self.assertEqual(evidence["confidence"], "calculated_from_available_network")
        self.assertEqual(evidence["missing_profile_inputs"], [])
        self.assertNotIn("missing_tailwater", evidence["labels"])
        self.assertEqual(hgl[0]["segment_id"], "P-HGL")
        self.assertEqual(hgl[0]["node_id"], "IN-1")
        self.assertEqual(hgl[1]["node_id"], "OUT-1")
        self.assertAlmostEqual(hgl[0]["hgl_ft"], round(expected_hgl_start, 3), places=3)
        self.assertAlmostEqual(hgl[1]["hgl_ft"], round(expected_hgl_end, 3), places=3)
        self.assertAlmostEqual(egl[0]["egl_ft"], round(expected_egl_start, 3), places=3)
        self.assertAlmostEqual(egl[1]["egl_ft"], round(expected_egl_end, 3), places=3)

        validation = validate_stormwater_depth({"meta": {"storm_pipes": enriched, "drainage": drainage}})
        self.assertEqual(validation["hgl_egl_trace"]["actual_hgl_count"], 2)
        self.assertEqual(validation["hgl_egl_trace"]["actual_egl_count"], 2)
        self.assertEqual(validation["hgl_egl_trace"]["confidence"], "calculated_from_available_network")
        self.assertTrue(validation["hgl_egl_trace"]["valid"])
        self.assertEqual(enriched["hydrology_hydraulics_evidence"]["standard_id"], "CITY-STORM-2026")
        self.assertEqual(enriched["hydrology_hydraulics_evidence"]["time_of_concentration_min"], 12.0)
        self.assertEqual(enriched["hydrology_hydraulics_evidence"]["construction_release_allowed"], False)
        self.assertIn("accepted rainfall/standard", validation["evidence"])
        self.assertIn("runoff method/time of concentration assumptions", validation["evidence"])

    def test_sparse_storm_inputs_surface_native_hydrology_hydraulics_blockers(self) -> None:
        storm = {
            "success": True,
            "segments": [{"pipe": "P-SPARSE", "path": [[0.0, 0.0], [60.0, 0.0]], "flow_cfs": 1.0}],
        }
        drainage = {"structures": [{"name": "CB-SPARSE"}], "basins": []}

        enriched = enrich_storm_production_depth(storm, drainage)
        validation = validate_stormwater_depth({"meta": {"storm_pipes": enriched, "drainage": drainage}})

        self.assertFalse(validation["production_ready"])
        self.assertFalse(enriched["hydrology_hydraulics_evidence"]["construction_release_allowed"])
        self.assertTrue(enriched["hydrology_hydraulics_evidence"]["engineer_review_required"])
        self.assertIn("accepted_rainfall.standard", enriched["hydrology_hydraulics_evidence"]["missing_inputs"])
        self.assertIn("time_of_concentration_min", enriched["hydrology_hydraulics_evidence"]["missing_inputs"])
        for blocker in (
            "Storm depth needs accepted rainfall/standard evidence.",
            "Storm depth needs drainage area evidence.",
            "Storm depth needs runoff method and time-of-concentration assumptions.",
            "Storm depth needs drainage-selected basin/outfall target evidence.",
            "Storm depth needs tailwater/backwater evidence.",
            "Storm depth needs passing inlet capacity, spread, and bypass checks.",
            "Storm depth needs HGL and EGL profiles from production hydraulic evidence.",
            "Storm depth needs production detention stage-storage/outlet/drawdown routing.",
            "Storm depth needs overflow routing evidence.",
            "Storm depth needs survey/control/terrain evidence.",
        ):
            self.assertIn(blocker, validation["blockers"])

    def test_storm_backwater_validation_blocks_tailwater_surcharged_pipe(self) -> None:
        storm = {
            "success": True,
            "hydraulic_source": "engine",
            "segments": [
                {
                    "pipe": "P-BACKWATER",
                    "from": "INLET-1",
                    "to": "BASIN-1",
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
            "source_pressure_source": "hydrant_flow_test_2026_accepted",
            "source_node": "SRC",
            "min_residual_pressure_psi": 20.0,
            "residual_pressure_source": "CITY-WATER-2026 fire-flow residual table",
            "standard_id": "CITY-WATER-2026",
            "standard_status": "adopted",
            "utility_owner": "City Water",
            "utility_owner_criteria": "City Water public-main criteria 2026",
            "utility_owner_criteria_status": "accepted",
            "fire_flow_criteria_source": "CITY-WATER-2026 Table FF-1",
            "hydrant_evidence_source": "surveyed_hydrant_fixture",
            "available_fire_flow_gpm": 1600.0,
            "fire_flow_demand_gpm": 1250.0,
            "pressure_zones": [
                {"id": "PZ-1", "source": "City Water pressure-zone map", "source_pressure_psi": 72.0, "min_pressure_psi": 45.0}
            ],
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
                        "material": "DIP",
                        "source": "accepted_utility_plan",
                        "flow_gpm": 450.0,
                    },
                    {
                        "name": "W-2",
                        "system_type": "water",
                        "start_node": "A",
                        "end_node": "SRC",
                        "route_points": [[220.0, 0.0], [0.0, 0.0]],
                        "diameter_in": 8.0,
                        "material": "DIP",
                        "source": "accepted_utility_plan",
                        "flow_gpm": 300.0,
                    },
                ],
            },
        }

        enriched = enrich_water_production_depth(utilities)

        self.assertTrue(enriched["pressure_validation"]["valid"])
        self.assertTrue(enriched["fire_flow_validation"]["valid"])
        self.assertTrue(enriched["hydrant_spacing_validation"]["valid"])
        self.assertTrue(enriched["pressure_zone_validation"]["valid"])
        self.assertTrue(enriched["water_fire_flow_proof"]["engineer_review_required"])
        self.assertFalse(enriched["water_fire_flow_proof"]["construction_release_allowed"])
        self.assertTrue(enriched["looped"])
        self.assertEqual(enriched["water_depth_status"], "ready")
        self.assertEqual(enriched["velocity_checks"][0]["segment"], "W-1")
        self.assertEqual(enriched["pressure_validation"]["source"], "water_pressure_graph")
        self.assertGreater(enriched["pressure_validation"]["residual_pressure_margin_psi"], 0.0)
        self.assertEqual(enriched["fire_flow_validation"]["source"], "water_fire_flow_residual_calculation")
        self.assertEqual(enriched["fire_flow_validation"]["fire_flow_margin_gpm"], 350.0)
        self.assertTrue(enriched["dead_end_validation"]["valid"])
        self.assertEqual(enriched["dead_end_validation"]["dead_end_nodes"], [])
        validation = validate_water_system_depth({"meta": {"water_summary": enriched}})
        self.assertTrue(validation["production_ready"])
        self.assertIn("utility owner criteria", validation["evidence"])

    def test_water_depth_calculates_available_fire_flow_from_residual_pressure(self) -> None:
        utilities = {
            "source_pressure_psi": 72.0,
            "source_pressure_source": "hydrant_flow_test_2026_accepted",
            "source_node": "SRC",
            "fire_flow_node": "H-1",
            "min_residual_pressure_psi": 20.0,
            "residual_pressure_source": "CITY-WATER-2026 residual pressure requirement",
            "standard_id": "CITY-WATER-2026",
            "standard_status": "adopted",
            "utility_owner": "City Water",
            "utility_owner_criteria": "City Water public-main criteria 2026",
            "utility_owner_criteria_status": "accepted",
            "fire_flow_criteria_source": "CITY-WATER-2026 Table FF-1",
            "hydrant_evidence_source": "surveyed_hydrant_fixture",
            "fire_flow_demand_gpm": 1000.0,
            "pressure_zones": [
                {"id": "PZ-1", "source": "City Water pressure-zone map", "source_pressure_psi": 72.0, "min_pressure_psi": 45.0}
            ],
            "hydrants": [
                {"name": "H-1", "x": 0.0, "y": 0.0},
                {"name": "H-2", "x": 250.0, "y": 0.0},
            ],
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "W-1",
                        "system_type": "water",
                        "start_node": "SRC",
                        "end_node": "H-1",
                        "route_points": [[0.0, 0.0], [300.0, 0.0]],
                        "diameter_in": 8.0,
                        "material": "DIP",
                        "source": "accepted_utility_plan",
                        "flow_gpm": 300.0,
                    },
                    {
                        "name": "W-2",
                        "system_type": "water",
                        "start_node": "H-1",
                        "end_node": "SRC",
                        "route_points": [[300.0, 0.0], [0.0, 0.0]],
                        "diameter_in": 8.0,
                        "material": "DIP",
                        "source": "accepted_utility_plan",
                        "flow_gpm": 300.0,
                    },
                ],
            },
        }

        enriched = enrich_water_production_depth(utilities)

        self.assertTrue(enriched["fire_flow_validation"]["valid"])
        self.assertGreaterEqual(enriched["fire_flow_validation"]["available_fire_flow_gpm"], 1000.0)
        self.assertEqual(enriched["fire_flow_validation"]["fire_flow_path"], ["W-1"])

    def test_water_depth_reports_dead_end_nodes_and_blocks_ready_status(self) -> None:
        utilities = {
            "source_pressure_psi": 72.0,
            "source_pressure_source": "hydrant_flow_test_2026_accepted",
            "source_node": "SRC",
            "fire_flow_node": "H-1",
            "min_residual_pressure_psi": 20.0,
            "residual_pressure_source": "CITY-WATER-2026 residual pressure requirement",
            "standard_id": "CITY-WATER-2026",
            "standard_status": "adopted",
            "utility_owner": "City Water",
            "utility_owner_criteria": "City Water public-main criteria 2026",
            "utility_owner_criteria_status": "accepted",
            "fire_flow_criteria_source": "CITY-WATER-2026 Table FF-1",
            "hydrant_evidence_source": "surveyed_hydrant_fixture",
            "fire_flow_demand_gpm": 750.0,
            "pressure_zones": [
                {"id": "PZ-1", "source": "City Water pressure-zone map", "source_pressure_psi": 72.0, "min_pressure_psi": 45.0}
            ],
            "hydrants": [
                {"name": "H-1", "x": 300.0, "y": 0.0},
                {"name": "H-2", "x": 450.0, "y": 0.0},
            ],
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "W-DEAD",
                        "system_type": "water",
                        "start_node": "SRC",
                        "end_node": "H-1",
                        "route_points": [[0.0, 0.0], [300.0, 0.0]],
                        "diameter_in": 8.0,
                        "material": "DIP",
                        "source": "accepted_utility_plan",
                        "flow_gpm": 250.0,
                    }
                ],
            },
        }

        enriched = enrich_water_production_depth(utilities)

        self.assertFalse(enriched["looped"])
        self.assertEqual(enriched["dead_end_validation"]["dead_end_nodes"], ["H-1", "SRC"])
        self.assertEqual(enriched["dead_end_validation"]["unresolved_dead_end_nodes"], ["H-1", "SRC"])
        self.assertIn("water_dead_ends_present", enriched["water_depth_blockers"])
        self.assertEqual(enriched["water_depth_status"], "blocked_missing_inputs")

    def test_water_fire_flow_blocks_without_source_pressure_and_accepted_standard(self) -> None:
        utilities = {
            "source_node": "SRC",
            "fire_flow_node": "H-1",
            "available_fire_flow_gpm": 1500.0,
            "fire_flow_demand_gpm": 1000.0,
            "hydrants": [
                {"name": "H-1", "x": 0.0, "y": 0.0},
                {"name": "H-2", "x": 250.0, "y": 0.0},
            ],
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "W-1",
                        "system_type": "water",
                        "start_node": "SRC",
                        "end_node": "H-1",
                        "route_points": [[0.0, 0.0], [300.0, 0.0]],
                        "diameter_in": 8.0,
                        "flow_gpm": 300.0,
                    }
                ],
            },
        }

        enriched = enrich_water_production_depth(utilities)

        self.assertFalse(enriched["fire_flow_validation"]["valid"])
        self.assertIn("source_pressure_psi", enriched["fire_flow_validation"]["missing_inputs"])
        self.assertIn("accepted_standard", enriched["fire_flow_validation"]["missing_inputs"])
        self.assertIn("utility_owner_criteria_missing", enriched["water_depth_blockers"])
        self.assertIn("accepted_water_standard_missing", enriched["water_depth_blockers"])

    def test_water_hydrant_spacing_reports_expected_max_spacing_and_standard_limit(self) -> None:
        utilities = {
            "source_pressure_psi": 72.0,
            "source_pressure_source": "hydrant_flow_test_2026_accepted",
            "source_node": "SRC",
            "min_residual_pressure_psi": 20.0,
            "residual_pressure_source": "CITY-WATER-2026 residual pressure requirement",
            "standard_id": "CITY-WATER-2026",
            "standard_status": "adopted",
            "utility_owner": "City Water",
            "utility_owner_criteria": "City Water public-main criteria 2026",
            "utility_owner_criteria_status": "accepted",
            "fire_flow_criteria_source": "CITY-WATER-2026 Table FF-1",
            "hydrant_evidence_source": "surveyed_hydrant_fixture",
            "max_hydrant_spacing_ft": 300.0,
            "available_fire_flow_gpm": 1500.0,
            "fire_flow_demand_gpm": 1000.0,
            "pressure_zones": [
                {"id": "PZ-1", "source": "City Water pressure-zone map", "source_pressure_psi": 72.0, "min_pressure_psi": 45.0}
            ],
            "hydrants": [
                {"name": "H-1", "x": 0.0, "y": 0.0},
                {"name": "H-2", "x": 180.0, "y": 0.0},
                {"name": "H-3", "x": 420.0, "y": 0.0},
            ],
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {"name": "W-1", "system_type": "water", "start_node": "SRC", "end_node": "A", "route_points": [[0.0, 0.0], [200.0, 0.0]], "diameter_in": 8.0, "material": "DIP", "source": "accepted_utility_plan", "flow_gpm": 300.0},
                    {"name": "W-2", "system_type": "water", "start_node": "A", "end_node": "SRC", "route_points": [[200.0, 0.0], [0.0, 0.0]], "diameter_in": 8.0, "material": "DIP", "source": "accepted_utility_plan", "flow_gpm": 300.0},
                ],
            },
        }

        enriched = enrich_water_production_depth(utilities)
        spacing = enriched["hydrant_spacing_validation"]

        self.assertTrue(spacing["valid"])
        self.assertEqual(spacing["hydrant_count"], 3)
        self.assertEqual(spacing["max_spacing_ft"], 240.0)
        self.assertEqual(spacing["limit_ft"], 300.0)
        self.assertEqual(
            spacing["spacing_rows"],
            [
                {"from": "H-1", "to": "H-2", "spacing_ft": 180.0},
                {"from": "H-2", "to": "H-3", "spacing_ft": 240.0},
            ],
        )

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
        self.assertIn("source_pressure_missing", enriched["water_depth_blockers"])
        self.assertIn("residual_target_missing", enriched["water_depth_blockers"])
        self.assertIn("hydrant_evidence_missing", enriched["water_depth_blockers"])
        self.assertIn("demand_fire_flow_criteria_missing", enriched["water_depth_blockers"])
        self.assertIn("pressure_zone_missing", enriched["water_depth_blockers"])
        self.assertIn("loop_dead_end_proof_missing", enriched["water_depth_blockers"])
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
        self.assertEqual(checks["civil3d"]["status"], "not_verified")
        self.assertEqual(checks["dwg"]["status"], "unsupported_no_native_writer")
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
