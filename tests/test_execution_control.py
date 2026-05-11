import unittest

from backend.planning.execution_control import mark_stage_skipped_clean, stage_should_run
from backend.planning.runtime import PLANNER_STAGE_DEPENDENCIES, PLANNER_STAGE_ORDER, PlannerExecutionContext, RoutingDecision, _register_default_dependencies
from core.project_manager import ProjectManager


class _DummyManager:
    def __init__(self) -> None:
        self.system_dirty_state = {}

    def is_system_dirty(self, name: str) -> bool:
        row = self.system_dirty_state.get(name) or {}
        return str(row.get("state", "")).lower() == "dirty"


class ExecutionControlTest(unittest.TestCase):
    def _clean_second_pass_context(self) -> PlannerExecutionContext:
        manager = _DummyManager()
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

    def _record_pass_run(self, ctx: PlannerExecutionContext, stage_name: str) -> None:
        ctx.manager.system_dirty_state[stage_name] = {"state": "clean", "reasons": []}
        ctx.add_stage(
            stage_name,
            True,
            f"{stage_name} completed on pass {ctx.pass_index}.",
            pass_index=ctx.pass_index,
            action="run",
        )

    def test_default_dependencies_match_runtime_declarations(self):
        manager = ProjectManager()
        _register_default_dependencies(manager)
        registered = {}
        for dep in manager.dependencies:
            registered.setdefault(dep.target, set()).add(dep.source)

        for stage_name, dependencies in PLANNER_STAGE_DEPENDENCIES.items():
            self.assertEqual(
                registered.get(stage_name, set()),
                set(dependencies),
                f"Dependency mismatch for {stage_name}",
            )

    def test_skipped_clean_preserves_completed_resumed_stage(self):
        ctx = PlannerExecutionContext(
            parsed={},
            manager=_DummyManager(),
            route=RoutingDecision(path="test", reasons=[]),
        )
        ctx.add_stage(
            "layout",
            True,
            "Restored layout state from saved checkpoint.",
            resumed_from_checkpoint=True,
            completeness="complete",
        )

        mark_stage_skipped_clean(ctx, "layout")

        latest = ctx.stage_results[-1]
        self.assertEqual(latest.stage_name, "layout")
        self.assertEqual(latest.meta.get("completeness"), "complete")

    def test_grading_dirty_reruns_dependent_chain_only(self):
        ctx = self._clean_second_pass_context()
        ctx.manager.system_dirty_state["grading"] = {"state": "dirty", "reasons": ["grading changed"]}

        self.assertFalse(stage_should_run(ctx, "layout"))
        self.assertTrue(stage_should_run(ctx, "grading"))
        self._record_pass_run(ctx, "grading")

        for stage_name in ["drainage", "utility_network", "earthwork", "qa"]:
            self.assertTrue(stage_should_run(ctx, stage_name), stage_name)

        self._record_pass_run(ctx, "drainage")
        self.assertTrue(stage_should_run(ctx, "storm_pipes"))

    def test_drainage_dirty_reruns_storm_and_downstream_only(self):
        ctx = self._clean_second_pass_context()
        ctx.manager.system_dirty_state["drainage"] = {"state": "dirty", "reasons": ["drainage changed"]}

        self.assertFalse(stage_should_run(ctx, "grading"))
        self.assertTrue(stage_should_run(ctx, "drainage"))
        self._record_pass_run(ctx, "drainage")

        self.assertTrue(stage_should_run(ctx, "storm_pipes"))
        self._record_pass_run(ctx, "storm_pipes")
        self.assertTrue(stage_should_run(ctx, "sanitary"))
        self.assertTrue(stage_should_run(ctx, "utility_network"))
        self.assertTrue(stage_should_run(ctx, "qa"))

    def test_coordination_dirty_reruns_sheets_earthwork_and_qa(self):
        ctx = self._clean_second_pass_context()
        ctx.manager.system_dirty_state["coordination_resolution"] = {
            "state": "dirty",
            "reasons": ["coordination changed"],
        }

        self.assertTrue(stage_should_run(ctx, "coordination_resolution"))
        self._record_pass_run(ctx, "coordination_resolution")

        self.assertTrue(stage_should_run(ctx, "sheets"))
        self.assertTrue(stage_should_run(ctx, "earthwork"))
        self.assertTrue(stage_should_run(ctx, "qa"))
        self.assertFalse(stage_should_run(ctx, "layout"))


if __name__ == "__main__":
    unittest.main()
