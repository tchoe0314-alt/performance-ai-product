import unittest

from backend.planning.engine_contracts import GOLDEN_SCENARIOS
from backend.planning.golden_scenarios import (
    golden_scenarios,
    scenario_engine_coverage,
    validate_golden_scenarios,
)


class GoldenScenarioTests(unittest.TestCase):
    def test_registry_matches_contract_scenarios(self) -> None:
        scenarios = golden_scenarios()

        self.assertEqual(tuple(item.scenario_id for item in scenarios), GOLDEN_SCENARIOS)
        self.assertEqual(validate_golden_scenarios(), [])

    def test_every_scenario_has_backend_proof_requirements(self) -> None:
        for scenario in golden_scenarios():
            self.assertGreaterEqual(len(scenario.required_engine_ids), 3)
            self.assertTrue(scenario.required_canonical_signals)
            self.assertTrue(scenario.production_gates)
            self.assertTrue(scenario.blocked_without)
            self.assertTrue(scenario.benchmark_expectations)
            self.assertTrue(all(item.get("metric") for item in scenario.benchmark_expectations))
            self.assertTrue(scenario.benchmark_payload.get("project_name"))

    def test_manual_gate_scenario_preserves_manual_mode(self) -> None:
        manual = next(item for item in golden_scenarios() if item.scenario_id == "manual_production_gate_case")

        self.assertTrue((manual.benchmark_payload.get("meta") or {}).get("manual_mode"))
        self.assertIn("stale_output_blocking", manual.blocked_without)

    def test_contract_coverage_and_registry_are_aligned(self) -> None:
        coverage = scenario_engine_coverage()

        self.assertEqual(set(coverage), set(GOLDEN_SCENARIOS))
        self.assertTrue(all(len(engines) >= 3 for engines in coverage.values()))


if __name__ == "__main__":
    unittest.main()
