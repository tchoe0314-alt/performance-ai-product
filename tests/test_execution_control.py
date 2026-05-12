import unittest

from backend.planning.execution_control import canonical_state_diff, canonical_state_snapshot, mark_stage_skipped_clean, stage_should_run
from backend.planning.runtime import PLANNER_STAGE_DEPENDENCIES, PLANNER_STAGE_ORDER, PlannerExecutionContext, RoutingDecision, _register_default_dependencies
from core.geometry_core import ProjectModel
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

    def test_canonical_state_snapshot_prefers_project_meta_over_stale_latest_outputs(self):
        project = ProjectModel(name="Slice 6C Snapshot")
        manager = ProjectManager(project)
        project.meta["grading_summary"] = {
            "local_adjustments": [{"id": "canonical-grade"}],
            "proposed_surface": {"source": "canonical"},
        }
        project.meta["drainage_canonical"] = {
            "structures": [{"id": "canonical-inlet"}],
            "basins": [{"id": "canonical-basin"}],
            "pipe_runs": [{"id": "canonical-run"}],
        }
        project.meta["storm_pipe_summary"] = {
            "segments": [{"id": "canonical-storm", "length_ft": 100.0}],
            "total_length_ft": 100.0,
        }
        project.meta["sanitary_summary"] = {
            "segments": [{"id": "canonical-san", "length_ft": 80.0}],
            "manholes": [{"id": "canonical-mh"}],
            "total_length_ft": 80.0,
        }
        project.meta["utility_summary"] = {
            "conflict_hooks": {
                "utility_segments": [{"id": "canonical-util", "length_ft": 40.0}],
            },
            "structures": [{"id": "canonical-valve"}],
            "total_length_ft": 40.0,
        }
        manager.latest_outputs["grading"] = {"local_adjustments": [{"id": "stale-grade"}], "proposed_surface": {}}
        manager.latest_outputs["drainage"] = {
            "structures": [{"id": "stale-inlet"}],
            "basins": [],
            "pipe_runs": [],
        }
        manager.latest_outputs["storm_pipe_summary"] = {
            "segments": [{"id": "stale-storm", "length_ft": 999.0}],
            "total_length_ft": 999.0,
        }
        manager.latest_outputs["sanitary"] = {
            "segments": [{"id": "stale-san", "length_ft": 888.0}],
            "manholes": [],
            "total_length_ft": 888.0,
        }
        manager.latest_outputs["utilities"] = {
            "conflict_hooks": {
                "utility_segments": [{"id": "stale-util", "length_ft": 777.0}],
            },
            "structures": [],
            "total_length_ft": 777.0,
        }

        snapshot = canonical_state_snapshot(project, manager)

        self.assertEqual(snapshot["drainage_structure_count"], 1)
        self.assertEqual(snapshot["drainage_basin_count"], 1)
        self.assertEqual(snapshot["drainage_pipe_run_count"], 1)
        self.assertEqual(snapshot["storm_segment_count"], 1)
        self.assertEqual(snapshot["storm_total_length_ft"], 100.0)
        self.assertEqual(snapshot["sanitary_segment_count"], 1)
        self.assertEqual(snapshot["sanitary_manhole_count"], 1)
        self.assertEqual(snapshot["sanitary_total_length_ft"], 80.0)
        self.assertEqual(snapshot["utility_segment_count"], 1)
        self.assertEqual(snapshot["utility_structure_count"], 1)
        self.assertEqual(snapshot["utility_total_length_ft"], 40.0)
        self.assertEqual(snapshot["grading_adjustment_count"], 1)
        self.assertTrue(snapshot["has_proposed_surface"])

        diff = canonical_state_diff(snapshot, canonical_state_snapshot(project, manager))
        self.assertEqual(diff["changed_count"], 0)


if __name__ == "__main__":
    unittest.main()
