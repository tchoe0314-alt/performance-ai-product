import unittest

from tests.benchmark_suite import run_benchmark_suite


class BenchmarkSuiteRegressionTests(unittest.TestCase):
    def test_controlled_benchmarks_preserve_truthful_trust_scores(self) -> None:
        results = {item["name"]: item for item in run_benchmark_suite()}

        healthy = results["healthy_clean"]
        self.assertTrue(healthy["manual"]["pass"], healthy)
        self.assertGreaterEqual(healthy["manual"]["trust_score"], 90.0)
        self.assertTrue(healthy["manual"]["truth_success"], healthy)
        self.assertGreaterEqual(healthy["assisted"]["trust_score"], 90.0)

        conflict_heavy = results["conflict_heavy_trench"]
        self.assertTrue(conflict_heavy["manual"]["pass"], conflict_heavy)
        self.assertEqual(conflict_heavy["manual"]["unresolved_conflicts"], 0)
        self.assertGreaterEqual(conflict_heavy["manual"]["trust_score"], 90.0)

        degraded = results["degraded_invalid"]
        self.assertFalse(degraded["manual"]["pass"], degraded)
        self.assertFalse(degraded["manual"]["truth_success"], degraded)
        self.assertLess(degraded["manual"]["trust_score"], 70.0)
        self.assertIn("MANUAL_STORM_HYDRAULIC_INVALID", degraded["manual"]["manual_failures"])
        self.assertFalse(degraded["assisted"]["truth_success"], degraded)
        self.assertLess(degraded["assisted"]["trust_score"], 90.0)


if __name__ == "__main__":
    unittest.main()
