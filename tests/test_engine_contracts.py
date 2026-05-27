import unittest
from pathlib import Path

from backend.planning.engine_contracts import (
    GOLDEN_SCENARIOS,
    downstream_closure,
    engine_contracts,
    planner_stage_engine_ids,
    reactive_dependency_graph,
    validate_engine_contracts,
)
from backend.planning.runtime import PLANNER_STAGE_ORDER


class EngineContractTests(unittest.TestCase):
    def test_all_master_backend_engines_have_valid_contracts(self) -> None:
        contracts = engine_contracts()

        self.assertEqual(len(contracts), 20)
        self.assertEqual(validate_engine_contracts(), [])
        self.assertEqual(len({contract.engine_id for contract in contracts}), 20)
        self.assertTrue(all(contract.final_capabilities for contract in contracts))
        self.assertTrue(all(contract.required_validations for contract in contracts))
        self.assertTrue(all(contract.production_readiness_gates for contract in contracts))
        self.assertTrue(all(contract.manual_mode_forbidden for contract in contracts))

    def test_contracts_cover_every_planner_stage(self) -> None:
        missing = [
            stage_name
            for stage_name in PLANNER_STAGE_ORDER
            if not planner_stage_engine_ids(stage_name)
        ]

        self.assertEqual(missing, [])
        self.assertIn("grading", planner_stage_engine_ids("grading"))
        self.assertIn("drainage", planner_stage_engine_ids("drainage"))
        self.assertIn("storm_pipe", planner_stage_engine_ids("storm_pipes"))
        self.assertIn("sanitary", planner_stage_engine_ids("sanitary"))
        self.assertIn("water", planner_stage_engine_ids("utility_network"))
        self.assertIn("utility_coordination", planner_stage_engine_ids("coordination_resolution"))
        self.assertIn("qa_validation", planner_stage_engine_ids("qa"))
        self.assertIn("export_cad", planner_stage_engine_ids("sheets"))

    def test_reactive_graph_declares_core_living_model_propagation(self) -> None:
        graph = reactive_dependency_graph()

        self.assertTrue({"grading", "drainage", "storm_pipes", "utility_network", "qa", "exports"}.issubset(graph["roadway_corridor"]))
        self.assertTrue({"drainage", "storm_pipes", "earthwork", "qa", "exports"}.issubset(graph["grading"]))
        self.assertTrue({"storm_pipes", "qa", "exports"}.issubset(graph["drainage"]))
        self.assertTrue({"sanitary", "utility_network", "coordination_resolution", "qa", "exports"}.issubset(graph["storm_pipe"]))
        self.assertTrue({"coordination_resolution", "earthwork", "qa", "exports"}.issubset(graph["water"]))
        self.assertTrue({"earthwork", "sheets", "qa", "quantities", "exports"}.issubset(graph["utility_coordination"]))

    def test_downstream_closure_reports_transitive_engine_impacts(self) -> None:
        closure = downstream_closure("geometry")

        self.assertIn("grading", closure)
        self.assertIn("drainage", closure)
        self.assertIn("coordination_resolution", closure)
        self.assertIn("qa", closure)
        self.assertIn("exports", closure)

    def test_contract_modules_point_to_existing_backend_files_or_globs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        missing = []
        for contract in engine_contracts():
            for module_path in contract.current_modules:
                if "*" in module_path:
                    if not list(repo_root.glob(module_path)):
                        missing.append((contract.engine_id, module_path))
                elif not (repo_root / module_path).exists():
                    missing.append((contract.engine_id, module_path))

        self.assertEqual(missing, [])

    def test_golden_scenarios_are_exercised_by_multiple_engines(self) -> None:
        coverage = {scenario: 0 for scenario in GOLDEN_SCENARIOS}
        for contract in engine_contracts():
            for scenario in contract.golden_scenarios:
                coverage[scenario] += 1

        undercovered = {scenario: count for scenario, count in coverage.items() if count < 3}
        self.assertEqual(undercovered, {})


if __name__ == "__main__":
    unittest.main()
