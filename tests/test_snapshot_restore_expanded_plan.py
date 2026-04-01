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


if __name__ == "__main__":
    unittest.main()
