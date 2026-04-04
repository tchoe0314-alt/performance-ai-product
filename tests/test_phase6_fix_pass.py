import unittest
from types import SimpleNamespace

from backend.planning.runtime import PlanQualityReport, PlannerExecutionContext, RoutingDecision
from planner import _apply_fix_pass


class _DummyManager:
    def __init__(self) -> None:
        self.project = SimpleNamespace(meta={})
        self.invalidated = []

    def unresolved_conflicts_by_category(self, _category: str):
        return []

    def invalidate_from(self, target: str, include_source: bool = True) -> None:
        self.invalidated.append((target, include_source))


class Phase6FixPassTest(unittest.TestCase):
    def test_fix_pass_targets_systems_from_qa_error_categories(self) -> None:
        manager = _DummyManager()
        ctx = PlannerExecutionContext(
            parsed={"meta": {}},
            manager=manager,  # type: ignore[arg-type]
            route=RoutingDecision(path="unit_test", reasons=[]),
        )
        report = PlanQualityReport()
        report.add("STORM_HYDRAULIC_COMPLETE", "error", "storm invalid")
        report.add("SANITARY_GRAPH_VALID", "error", "sanitary invalid")
        report.add("DRAINAGE_VALIDATION", "error", "drainage invalid")

        _apply_fix_pass(ctx, report)

        fix_summary = manager.project.meta.get("fix_summary") or {}
        self.assertTrue(fix_summary.get("effective_change"))
        self.assertIn("storm_validation_retry", fix_summary.get("autofix_actions") or [])
        self.assertIn("sanitary_validation_retry", fix_summary.get("autofix_actions") or [])
        self.assertIn("drainage_validation_retry", fix_summary.get("autofix_actions") or [])
        changed_targets = fix_summary.get("changed_targets") or []
        self.assertIn("storm_pipes", changed_targets)
        self.assertIn("sanitary", changed_targets)
        self.assertIn("drainage", changed_targets)
        self.assertTrue(any(target == "storm_pipes" for target, _include_source in manager.invalidated))


if __name__ == "__main__":
    unittest.main()
