import unittest
from copy import deepcopy
from unittest.mock import patch

import planner
from core.project_manager import ProjectManager
from backend.planning.production_depth import enrich_storm_production_depth


class CoordinationPerformanceHelperTests(unittest.TestCase):
    def test_owned_storm_enrichment_matches_isolated_default(self) -> None:
        storm = {"segments": [{"pipe": "ST-1", "path": [[0, 0], [20, 0]], "diameter_in": 12, "flow_cfs": 1, "start_invert": 100, "end_invert": 99}], "source": "engine"}
        drainage = {"basins": [{"name": "B-1", "area_ac": 0.5}], "coordination": {"preferred_outfall": {"name": "OUT", "x": 20, "y": 0}}}
        original, original_drainage = deepcopy(storm), deepcopy(drainage)
        expected = enrich_storm_production_depth(storm, drainage)
        self.assertEqual(storm, original)
        owned = deepcopy(storm)
        actual = enrich_storm_production_depth(owned, drainage, copy_input=False)
        self.assertIs(actual, owned)
        self.assertEqual(actual, expected)
        self.assertEqual(drainage, original_drainage)
        actual["segments"][0]["path"][0][0] = 999
        self.assertEqual(storm, original)
        self.assertNotEqual(actual, expected)

    def test_detection_prepares_each_path_and_pair_once_without_stale_reuse(self) -> None:
        manager = ProjectManager()
        rows = [
            {"name": f"PIPE-{index}", "system": "water", "path": [[0, index], [20, index]], "start_invert": 0, "end_invert": 0}
            for index in range(6)
        ]
        before = deepcopy(rows)
        rule = {"required_horizontal_clearance_ft": 3, "required_vertical_clearance_ft": 2}
        with patch.object(planner, "_normalized_summary_segments", return_value=rows), patch.object(planner, "_expanded_obstacle_rectangles", return_value=[]), patch.object(planner, "_crossing_rule_for", return_value=rule) as rules, patch.object(planner, "_sample_coordination_path", wraps=planner._sample_coordination_path) as sample:
            first = planner._detect_coordination_conflicts(manager.project, manager)
            self.assertEqual(sample.call_count, len(rows))
            self.assertEqual(rules.call_count, 1)
            self.assertTrue(first)
            self.assertEqual(
                [item["involved_objects"] for item in first],
                [[f"PIPE-{a}", f"PIPE-{b}"] for a in range(6) for b in range(a + 1, 6) if b - a < 3],
            )
            self.assertEqual(rows, before)
            self.assertEqual(rule, {"required_horizontal_clearance_ft": 3, "required_vertical_clearance_ft": 2})
            rows[-1]["path"] = [[0, 100], [20, 100]]
            second = planner._detect_coordination_conflicts(manager.project, manager)
            self.assertEqual(sample.call_count, 2 * len(rows))
            self.assertEqual(rules.call_count, 2)
            self.assertLess(len(second), len(first))
            self.assertFalse(any("PIPE-5" in item["involved_objects"] for item in second))

    def test_geometry_candidate_pruning_reduces_duplicates_and_caps_breadth(self) -> None:
        base_path = [[0.0, 0.0], [20.0, 0.0]]
        candidates = [
            {"strategy": "terminal_shift", "path": [[0.0, 0.0], [20.0, 0.0]], "added_length_ft": 0.0, "bend_count": 0, "protected_hits": [], "protected_penalty": 0.0, "corridor_penalty": 0.0},
            {"strategy": "reroute", "path": [[0.0, 0.0], [10.0, 8.0], [20.0, 0.0]], "added_length_ft": 5.6, "bend_count": 1, "protected_hits": [], "protected_penalty": 0.0, "corridor_penalty": 2.0},
            {"strategy": "reroute", "path": [[0.0, 0.0], [10.2, 8.1], [20.0, 0.0]], "added_length_ft": 5.9, "bend_count": 1, "protected_hits": [], "protected_penalty": 0.0, "corridor_penalty": 2.2},
            {"strategy": "reroute", "path": [[0.0, 0.0], [5.0, 15.0], [10.0, -15.0], [15.0, 15.0], [20.0, 0.0]], "added_length_ft": 38.0, "bend_count": 3, "protected_hits": [], "protected_penalty": 0.0, "corridor_penalty": 8.0},
            {"strategy": "reroute", "path": [[0.0, 0.0], [5.0, 6.0], [10.0, 6.0], [15.0, 6.0], [20.0, 0.0]], "added_length_ft": 10.0, "bend_count": 2, "protected_hits": [], "protected_penalty": 0.0, "corridor_penalty": 3.0},
            {"strategy": "reroute", "path": [[0.0, 0.0], [3.0, 7.0], [8.0, 7.0], [14.0, 7.0], [20.0, 0.0]], "added_length_ft": 11.0, "bend_count": 2, "protected_hits": [], "protected_penalty": 0.0, "corridor_penalty": 3.5},
        ]
        metrics = planner._new_coordination_metrics()

        kept = planner._prune_geometry_candidate_rows(candidates, base_path, metrics=metrics, breadth_cap=2)

        self.assertEqual(len(kept), 2)
        self.assertEqual(metrics["candidate_counts"]["geometry_candidates_generated"], len(candidates))
        self.assertEqual(metrics["candidate_counts"]["geometry_candidates_evaluated"], 2)
        self.assertGreaterEqual(metrics["candidate_counts"]["geometry_candidates_pruned"], 3)
        self.assertGreaterEqual(metrics["prune_reasons"].get("near_equivalent_duplicate", 0), 1)
        self.assertGreaterEqual(metrics["prune_reasons"].get("breadth_cap", 0), 1)

    def test_structure_insertion_analysis_cache_records_hits(self) -> None:
        path = [[0.0, 0.0], [40.0, 0.0]]
        metrics = planner._new_coordination_metrics()
        cache = {}

        first = planner._apply_structure_insertion_rules(None, None, "storm", "SEG-1", path, metrics=metrics, analysis_cache=cache)
        second = planner._apply_structure_insertion_rules(None, None, "storm", "SEG-1", path, metrics=metrics, analysis_cache=cache)

        self.assertEqual(first["added_count"], 0)
        self.assertEqual(second["added_count"], 0)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(metrics["structure_insertion"]["analysis_cache_misses"], 1)
        self.assertEqual(metrics["structure_insertion"]["analysis_cache_hits"], 1)


if __name__ == "__main__":
    unittest.main()
