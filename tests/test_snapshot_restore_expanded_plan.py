import unittest
from copy import deepcopy

from planner import (
    PlannerExecutionContext,
    _bootstrap_manager,
    _ingest_parsed_into_model,
    _register_default_dependencies,
    _run_layout_stage,
    choose_routing_path,
    triple_check_parsed_payload,
)


class SnapshotRestoreExpandedPlanTest(unittest.TestCase):
    def test_restore_snapshot_preserves_expanded_plan_meta(self) -> None:
        parsed = triple_check_parsed_payload(
            {
                "project_name": "Snapshot Restore Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {
                    "building_width": 48.0,
                    "building_depth": 34.0,
                    "parking_count": 24,
                },
            }
        )
        manager = _bootstrap_manager(parsed)
        _register_default_dependencies(manager)
        ctx = PlannerExecutionContext(
            parsed=deepcopy(parsed),
            manager=manager,
            route=choose_routing_path(parsed),
            option_name="Base",
            option_family="base",
        )

        _ingest_parsed_into_model(ctx)
        _run_layout_stage(ctx)

        before = manager.project.meta.get("_expanded_plan") or {}
        self.assertGreater(len(before.get("actions") or []), 0)

        snapshot_id = manager.snapshot("expanded_plan_debug")
        manager.restore_snapshot(snapshot_id)

        after = manager.project.meta.get("_expanded_plan") or {}
        self.assertEqual(len(after.get("actions") or []), len(before.get("actions") or []))

    def test_snapshot_handles_recursive_runtime_metadata(self) -> None:
        parsed = triple_check_parsed_payload(
            {
                "project_name": "Snapshot Recursive Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "commercial_pad",
                "site_type": "commercial_pad",
                "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 150.0},
                "setback": 10.0,
                "street_edge": "bottom",
                "layout_strategy": "front_parking",
                "site_plan": {
                    "building_width": 60.0,
                    "building_depth": 40.0,
                    "parking_count": 30,
                },
            }
        )
        manager = _bootstrap_manager(parsed)
        _register_default_dependencies(manager)
        ctx = PlannerExecutionContext(
            parsed=deepcopy(parsed),
            manager=manager,
            route=choose_routing_path(parsed),
            option_name="Base",
            option_family="base",
        )

        _ingest_parsed_into_model(ctx)
        _run_layout_stage(ctx)

        recursive_meta = {"kind": "runtime_recursive"}
        recursive_meta["self"] = recursive_meta
        manager.project.meta["runtime_recursive"] = recursive_meta
        manager.latest_outputs["recursive_output"] = recursive_meta

        snapshot_id = manager.snapshot("recursive_debug")
        restored = manager.restore_snapshot(snapshot_id)

        self.assertIsInstance(restored, dict)
        self.assertIn("project", restored)
        project_meta = (((restored.get("project") or {}).get("meta")) or {})
        self.assertEqual(project_meta.get("runtime_recursive", {}).get("kind"), "runtime_recursive")
        self.assertIn("self", project_meta.get("runtime_recursive", {}))

    def test_snapshot_payload_omits_recursive_history_state(self) -> None:
        parsed = triple_check_parsed_payload(
            {
                "project_name": "Snapshot Lean State Test",
                "units": "ft",
                "mode": "site_plan",
                "project_type": "mixed_use",
                "site_type": "mixed_use",
                "lot": {"x": 0.0, "y": 0.0, "w": 600.0, "h": 600.0},
                "setback": 15.0,
                "street_edge": "bottom",
                "layout_strategy": "balanced",
                "site_plan": {
                    "building_width": 120.0,
                    "building_depth": 60.0,
                    "parking_count": 64,
                },
            }
        )
        manager = _bootstrap_manager(parsed)
        _register_default_dependencies(manager)
        ctx = PlannerExecutionContext(
            parsed=deepcopy(parsed),
            manager=manager,
            route=choose_routing_path(parsed),
            option_name="Base",
            option_family="base",
        )

        _ingest_parsed_into_model(ctx)
        _run_layout_stage(ctx)
        first_snapshot_id = manager.snapshot("baseline")
        second_snapshot_id = manager.snapshot("best_pass")

        second_snapshot = manager.state.snapshots[second_snapshot_id]
        second_state = second_snapshot.project_state.get("state") or {}

        self.assertEqual(second_state.get("snapshots"), {})
        self.assertEqual(second_state.get("variants"), {})
        self.assertEqual(second_state.get("audit_log"), [])

        manager.restore_snapshot(first_snapshot_id)
        self.assertIn(first_snapshot_id, manager.state.snapshots)
        self.assertIn(second_snapshot_id, manager.state.snapshots)


if __name__ == "__main__":
    unittest.main()
