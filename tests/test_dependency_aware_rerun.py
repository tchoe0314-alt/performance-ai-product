import unittest

from backend.planning.execution_control import stage_dirty_reasons, stage_should_run
from backend.planning.runtime import PLANNER_STAGE_ORDER, PlannerExecutionContext, RoutingDecision


class _DirtyStateManager:
    def __init__(self) -> None:
        self.system_dirty_state = {}

    def is_system_dirty(self, name: str) -> bool:
        row = self.system_dirty_state.get(name) or {}
        return str(row.get("state", "")).lower() == "dirty"


class DependencyAwareRerunTest(unittest.TestCase):
    def _ctx(self) -> PlannerExecutionContext:
        manager = _DirtyStateManager()
        ctx = PlannerExecutionContext(
            parsed={},
            manager=manager,
            route=RoutingDecision(path="test", reasons=[]),
            pass_index=2,
        )
        for stage_name in PLANNER_STAGE_ORDER:
            manager.system_dirty_state[stage_name] = {"state": "clean", "reasons": []}
            ctx.add_stage(
                stage_name,
                True,
                f"{stage_name} completed on pass 1.",
                pass_index=1,
                action="run",
            )
        return ctx

    def _mark_ran_this_pass(self, ctx: PlannerExecutionContext, stage_name: str) -> None:
        ctx.manager.system_dirty_state[stage_name] = {"state": "clean", "reasons": []}
        ctx.add_stage(
            stage_name,
            True,
            f"{stage_name} completed on pass {ctx.pass_index}.",
            pass_index=ctx.pass_index,
            action="run",
        )

    def test_second_pass_skips_clean_unrelated_stages(self) -> None:
        ctx = self._ctx()
        ctx.manager.system_dirty_state["qa"] = {"state": "dirty", "reasons": ["Targeted QA rerun."]}

        self.assertFalse(stage_should_run(ctx, "layout"))
        self.assertFalse(stage_should_run(ctx, "grading"))
        self.assertTrue(stage_should_run(ctx, "qa"))

    def test_dependency_rerun_reason_flows_after_upstream_reruns_clean(self) -> None:
        ctx = self._ctx()
        ctx.manager.system_dirty_state["grading"] = {"state": "dirty", "reasons": ["Grading changed."]}

        self.assertTrue(stage_should_run(ctx, "grading"))
        self._mark_ran_this_pass(ctx, "grading")

        self.assertTrue(stage_should_run(ctx, "drainage"))
        self.assertIn("Dependency 'grading' reran this pass.", stage_dirty_reasons(ctx, "drainage"))
        self._mark_ran_this_pass(ctx, "drainage")

        self.assertTrue(stage_should_run(ctx, "storm_pipes"))
        self.assertIn("Dependency 'drainage' reran this pass.", stage_dirty_reasons(ctx, "storm_pipes"))


if __name__ == "__main__":
    unittest.main()
