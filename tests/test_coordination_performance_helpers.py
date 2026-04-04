import unittest

import planner


class CoordinationPerformanceHelperTests(unittest.TestCase):
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
