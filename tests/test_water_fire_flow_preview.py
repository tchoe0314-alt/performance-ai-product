import unittest

from backend.planning.production_depth import enrich_water_production_depth
from output.preview import build_preview_annotations


class WaterFireFlowPreviewTest(unittest.TestCase):
    def test_ui_payload_extracts_hydrant_spacing_pressure_zone_and_fire_flow(self) -> None:
        water = enrich_water_production_depth(
            {
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
                "max_hydrant_spacing_ft": 300.0,
                "fire_flow_demand_gpm": 1000.0,
                "hydrants": [
                    {"name": "H-1", "x": 0.0, "y": 0.0, "zone_id": "PZ-1"},
                    {"name": "H-2", "x": 180.0, "y": 0.0, "zone_id": "PZ-1"},
                ],
                "pressure_zones": [
                    {
                        "id": "PZ-1",
                        "name": "Zone 1",
                        "min_pressure_psi": 44.0,
                        "max_pressure_psi": 72.0,
                        "source_pressure_psi": 72.0,
                        "geometry": [[0.0, 0.0], [180.0, 0.0]],
                    }
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
        )

        annotations = build_preview_annotations({"actions": [], "meta": {"water_summary": water}})
        review = annotations["water_fire_flow"]

        self.assertEqual([hydrant["id"] for hydrant in review["hydrants"]], ["H-1", "H-2"])
        self.assertEqual(review["pressure_zones"][0]["id"], "PZ-1")
        self.assertTrue(review["spacing_checks"][0]["valid"])
        self.assertEqual(review["scenario_runs"][0]["status"], "pass")
        self.assertTrue(review["readiness"]["pressure_valid"])
        self.assertTrue(review["readiness"]["fire_flow_valid"])
        self.assertTrue(review["readiness"]["hydrant_spacing_valid"])
        self.assertTrue(review["readiness"]["engineer_review_required"])
        self.assertFalse(review["readiness"]["construction_release_allowed"])
        self.assertEqual(review["scenario_runs"][0]["source_pressure_source"], "hydrant_flow_test_2026_accepted")
        self.assertEqual(review["scenario_runs"][0]["utility_owner"], "City Water")

    def test_ui_payload_reports_low_pressure_dead_end_and_fire_flow_blockers(self) -> None:
        water = enrich_water_production_depth(
            {
                "source_pressure_psi": 35.0,
                "source_pressure_source": "hydrant_flow_test_2026_accepted",
                "min_residual_pressure_psi": 50.0,
                "residual_pressure_source": "CITY-WATER-2026 residual pressure requirement",
                "source_node": "SRC",
                "fire_flow_node": "H-1",
                "standard_id": "CITY-WATER-2026",
                "standard_status": "adopted",
                "utility_owner": "City Water",
                "utility_owner_criteria": "City Water public-main criteria 2026",
                "utility_owner_criteria_status": "accepted",
                "fire_flow_criteria_source": "CITY-WATER-2026 Table FF-1",
                "hydrant_evidence_source": "surveyed_hydrant_fixture",
                "fire_flow_demand_gpm": 1500.0,
                "pressure_zones": [
                    {"id": "PZ-1", "source": "City Water pressure-zone map", "source_pressure_psi": 35.0, "min_pressure_psi": 50.0}
                ],
                "hydrants": [{"name": "H-1", "x": 300.0, "y": 0.0}],
                "conflict_hooks": {
                    "utility_system_type": "water",
                    "utility_segments": [
                        {
                            "name": "W-DEAD",
                            "system_type": "water",
                            "start_node": "SRC",
                            "end_node": "H-1",
                            "route_points": [[0.0, 0.0], [300.0, 0.0]],
                            "diameter_in": 6.0,
                            "material": "DIP",
                            "source": "accepted_utility_plan",
                            "flow_gpm": 400.0,
                        }
                    ],
                },
            }
        )

        annotations = build_preview_annotations({"actions": [], "meta": {"water_summary": water}})
        review = annotations["water_fire_flow"]

        self.assertFalse(review["readiness"]["pressure_valid"])
        self.assertFalse(review["readiness"]["dead_end_valid"])
        self.assertIn("water_dead_ends_present", review["readiness"]["blockers"])
        self.assertGreater(len(review["blocker_cards"]), 0)
        self.assertEqual(review["network_segments"][0]["network_type"], "dead_end")
        self.assertEqual(review["scenario_runs"][0]["status"], "review")
        self.assertIn("available_fire_flow_gpm_or_calculable_fire_flow_path", review["scenario_runs"][0]["missing_inputs"])

    def test_ui_payload_extracts_velocity_and_water_main_status_without_defaults(self) -> None:
        water = enrich_water_production_depth(
            {
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
                    {"name": "H-1", "x": 0.0, "y": 0.0},
                    {"name": "H-2", "x": 220.0, "y": 0.0},
                ],
                "water_segments": [
                    {
                        "id": "W-REVIEW",
                        "system_type": "water",
                        "start_node": "SRC",
                        "end_node": "H-1",
                        "diameter_in": 4.0,
                        "material": "DIP",
                        "source": "accepted_utility_plan",
                        "flow_gpm": 900.0,
                        "velocity_fps": 18.0,
                        "end_pressure_psi": 41.0,
                        "route_points": [[0.0, 0.0], [100.0, 0.0]],
                    }
                ],
                "velocity_checks": [
                    {
                        "segment": "W-REVIEW",
                        "velocity_fps": 18.0,
                        "valid": False,
                        "reason": "velocity_exceeds_limit",
                    }
                ],
            }
        )

        annotations = build_preview_annotations({"actions": [], "meta": {"water_summary": water}})
        review = annotations["water_fire_flow"]

        self.assertEqual(review["network_segments"][0]["id"], "W-REVIEW")
        self.assertGreater(review["network_segments"][0]["velocity_fps"], 8.0)
        self.assertGreater(review["network_segments"][0]["end_pressure_psi"], 0.0)
        self.assertNotEqual(review["network_segments"][0]["end_pressure_psi"], 41.0)
        self.assertFalse(review["velocity_checks"][0]["valid"])


if __name__ == "__main__":
    unittest.main()
