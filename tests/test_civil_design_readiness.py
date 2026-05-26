import unittest

import planner
from core.civil_design import (
    civil_design_readiness,
    path_clearance,
    path_length,
    sample_path,
    station_point,
    utility_pairing_rule,
)


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


class CivilDesignReadinessTests(unittest.TestCase):
    def test_complete_canonical_meta_is_ready(self) -> None:
        readiness = civil_design_readiness({"meta": _complete_meta()})

        self.assertTrue(readiness["success"])
        self.assertIn(readiness["status"], {"ready", "needs_engineering_review"})
        self.assertEqual(readiness["truth_sources"]["grading"], "terrain")
        self.assertGreaterEqual(readiness["score"], 80.0)
        self.assertIn(readiness["real_world_readiness"], {"concept_design_ready", "production_review_candidate"})
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

        self.assertIsInstance(readiness, dict)
        self.assertIn("systems", readiness)
        self.assertIn("missing_requirements", readiness)
        self.assertIn(readiness.get("status"), {"ready", "needs_engineering_review", "blocked"})


if __name__ == "__main__":
    unittest.main()
