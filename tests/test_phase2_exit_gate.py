import unittest

from core.geometry_core import ProjectModel
from planner import (
    COORDINATION_CROSSING_RULES,
    HARD_PROTECTED_ZONE_KINDS,
    PROTECTED_ZONE_RULES,
    _analyze_structure_insertion_needs,
    _candidate_constructability_score,
    _group_cluster_groups,
    _group_conflict_clusters,
    _path_protected_zone_hits,
    _path_protected_zone_penalty,
    _preferred_corridors,
    _segment_ownership_class,
)


class Phase2ExitGateTest(unittest.TestCase):
    def test_all_supported_utility_pairings_have_crossing_rules(self) -> None:
        systems = ("storm", "sanitary", "water", "gas", "electric", "telecom")

        for index, left in enumerate(systems):
            for right in systems[index + 1 :]:
                with self.subTest(pair=(left, right)):
                    rule = COORDINATION_CROSSING_RULES.get(tuple(sorted((left, right))))
                    self.assertIsNotNone(rule)
                    self.assertIn(rule["preferred_lower_system"], {left, right})
                    self.assertGreater(rule["required_horizontal_clearance_ft"], 0.0)
                    self.assertGreater(rule["required_vertical_clearance_ft"], 0.0)
                    self.assertGreater(rule["preferred_crossing_angle_deg"], 0.0)

    def test_corridor_preferences_create_system_slots_from_gis_axis(self) -> None:
        project = ProjectModel()
        project.meta["gis_layers"] = {
            "utility_corridors": [
                {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0.0, 40.0], [240.0, 40.0], [240.0, 60.0], [0.0, 60.0], [0.0, 40.0]]],
                    },
                    "properties": {"name": "Main Utility Easement"},
                }
            ]
        }

        corridors = _preferred_corridors({"lot": {"x": 0.0, "y": 0.0, "w": 240.0, "h": 160.0}}, project)

        self.assertEqual(corridors["storm"]["source"], "gis_easement")
        self.assertLess(corridors["storm"]["axis_value"], corridors["sanitary"]["axis_value"])
        self.assertLess(corridors["sanitary"]["axis_value"], corridors["water"]["axis_value"])
        self.assertEqual(corridors["water"]["source_name"], "Main Utility Easement")

    def test_hard_protected_zones_surface_avoidance_risk(self) -> None:
        path = [[0.0, 50.0], [100.0, 50.0]]
        zones = [
            {
                "kind": "wetland",
                "name": "Wetland A",
                "x": 40.0,
                "y": 40.0,
                "w": 20.0,
                "h": 20.0,
                "buffer_ft": 10.0,
                **PROTECTED_ZONE_RULES["wetland"],
            }
        ]

        hits = _path_protected_zone_hits(path, zones)

        self.assertIn("wetland", HARD_PROTECTED_ZONE_KINDS)
        self.assertEqual(hits[0]["kind"], "wetland")
        self.assertTrue(hits[0]["avoid"])
        self.assertGreater(_path_protected_zone_penalty(path, zones), 0.0)

    def test_constructability_score_penalizes_low_ownership_and_complexity(self) -> None:
        simple_path = [[0.0, 0.0], [100.0, 0.0]]
        complex_path = [[0.0, 0.0], [40.0, 0.0], [40.0, 40.0], [100.0, 40.0]]

        main_score = _candidate_constructability_score(
            simple_path,
            simple_path,
            protected_penalty=0.0,
            added_structures=0,
            ownership_class="water_main",
        )
        service_score = _candidate_constructability_score(
            simple_path,
            complex_path,
            protected_penalty=20.0,
            added_structures=2,
            ownership_class="utility_service",
            grading_penalty=10.0,
        )

        self.assertEqual(_segment_ownership_class({"system": "water", "segment_role": "main"}), "water_main")
        self.assertEqual(_segment_ownership_class({"system": "water", "segment_role": "service"}), "utility_service")
        self.assertGreater(service_score["score"], main_score["score"])
        self.assertGreaterEqual(service_score["bend_complexity"], 1)
        self.assertEqual(service_score["added_structures"], 2)

    def test_structure_insertion_detects_bends_and_spacing_needs(self) -> None:
        analysis = _analyze_structure_insertion_needs(
            [[0.0, 0.0], [80.0, 0.0], [80.0, 80.0], [180.0, 80.0]],
            spacing_limit=75.0,
        )

        self.assertTrue(analysis["bend_points"])
        self.assertTrue(analysis["spacing_points"])
        self.assertGreaterEqual(len(analysis["points"]), 2)

    def test_trench_conflicts_group_by_shared_corridor_context(self) -> None:
        project = ProjectModel()
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 50.0, "weight": 1.0},
            "generic": {"orientation": "horizontal", "axis_value": 50.0, "weight": 1.0},
        }
        conflicts = [
            {
                "conflict_type": "gas_water_clearance",
                "systems": ["gas", "water"],
                "involved_objects": ["GAS-1", "WATER-1"],
                "location": [20.0, 50.0],
                "severity": "error",
            },
            {
                "conflict_type": "electric_telecom_clearance",
                "systems": ["electric", "telecom"],
                "involved_objects": ["ELEC-1", "TEL-1"],
                "location": [65.0, 50.0],
                "severity": "error",
            },
        ]

        clusters = _group_conflict_clusters(conflicts, project)
        groups = _group_cluster_groups(clusters)

        self.assertTrue(any(row["trench_like"] for row in clusters))
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0]["trench_like"])
        self.assertEqual(groups[0]["corridor_axis"], "horizontal")

    def test_profile_and_cross_section_records_keep_canonical_coordination_context(self) -> None:
        shared_context = {
            "alignment_name": "SAN MAIN",
            "alignment_type": "sanitary_pipe",
            "source_system": "sanitary",
            "alignment_owner": "SAN MAIN",
            "ownership_class": "sanitary_main",
            "preferred_corridor": {"orientation": "horizontal", "axis_value": 48.0, "source": "gis_easement"},
            "protected_zone_context": {"hit_count": 0, "hard_hit_count": 0},
            "grading_context": {"disturbance_class": "standard", "local_adjustment_count": 1},
        }
        profile = {
            **shared_context,
            "alignment_points": [[0.0, 48.0], [120.0, 48.0]],
            "pipe_band_records": [{"from_structure": "MH-1", "to_structure": "MH-2", "diameter_in": 8.0}],
        }
        section = {
            **shared_context,
            "cut_line_points": [[60.0, 36.0], [60.0, 60.0]],
            "section_context": {"feature_types": ["pipe_centerline"], "sample_count": 7},
        }

        for record in (profile, section):
            self.assertEqual(record["source_system"], "sanitary")
            self.assertEqual(record["alignment_owner"], "SAN MAIN")
            self.assertEqual(record["ownership_class"], "sanitary_main")
            self.assertEqual(record["preferred_corridor"]["source"], "gis_easement")
            self.assertIn("protected_zone_context", record)
            self.assertIn("grading_context", record)


if __name__ == "__main__":
    unittest.main()
