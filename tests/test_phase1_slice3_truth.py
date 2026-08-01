import unittest
from copy import deepcopy

from backend.planning.coordination_stage_runner import run_conflict_resolution_stage
from backend.planning.runtime import PlannerExecutionContext, RoutingDecision
from core.project_manager import ProjectManager
from planner import (
    _recompute_sanitary_summary,
    _recompute_storm_summary,
    _run_manual_gate,
)


class Phase1Slice3TruthTest(unittest.TestCase):
    def test_final_coordination_validation_refreshes_changed_systems_first(self) -> None:
        manager = ProjectManager()
        ctx = PlannerExecutionContext(parsed={}, manager=manager, route=RoutingDecision(path="test", reasons=[]))
        call_order = []
        conflict = {"conflict_type": "forced", "involved_objects": ["A", "B"], "severity": "warning"}

        def detect(_project, _manager):
            return [conflict] if not call_order else []

        def solve_group(*_args, **_kwargs):
            return {
                "success": True,
                "changed_systems": ["storm"],
                "resolution_rows": [],
                "engineering_deltas": {},
                "remaining_cluster_conflicts": [],
            }

        def refresh(_project, _manager, changed_systems):
            call_order.append(("refresh", tuple(changed_systems)))
            _manager.latest_outputs["storm_pipe_summary"] = {"segments": [], "refreshed": True}

        def validate(_project, _manager, changed_systems):
            call_order.append(("validate", tuple(changed_systems), bool(_manager.latest_outputs.get("storm_pipe_summary", {}).get("refreshed"))))
            return {"valid": True, "systems": {}, "consistency": {}}

        run_conflict_resolution_stage(
            ctx,
            {},
            manual_mode_enabled=lambda _parsed: False,
            new_coordination_metrics=lambda: {},
            detect_coordination_conflicts=detect,
            conflict_priority_key=lambda _item: (0, ""),
            group_conflict_clusters=lambda conflicts, _project: [{"cluster_id": "C1", "conflicts": list(conflicts)}],
            group_cluster_groups=lambda clusters: [{"cluster_group_id": "G1", "clusters": list(clusters)}],
            snapshot_coordination_state=lambda _project, _manager: {},
            full_coordination_state_snapshot=lambda _project, _manager: deepcopy(_manager.to_dict()),
            cluster_group_remaining_conflicts=lambda _conflicts, _group: [],
            solve_conflict_cluster_group=solve_group,
            refresh_conflict_resolved_state=refresh,
            coordination_metric_inc=lambda *_args, **_kwargs: None,
            restore_full_coordination_state=lambda *_args, **_kwargs: None,
            conflict_cluster_id=lambda _cluster: "C1",
            post_reroute_validations=validate,
            count_conflicts_by_type=lambda _conflicts: {},
            grading_local_adjustments=lambda _project: [],
        )

        self.assertEqual(call_order[-2], ("refresh", ("storm",)))
        self.assertEqual(call_order[-1], ("validate", ("storm",), True))

    def test_sanitary_recompute_exposes_complete_canonical_truth_fields(self) -> None:
        manager = ProjectManager()
        project = manager.project
        summary = {
            "segments": [
                {
                    "name": "SAN-1",
                    "segment_role": "main",
                    "route_points": [[0.0, 0.0], [100.0, 0.0]],
                    "diameter_in": 8.0,
                    "start_invert_ft": 100.0,
                    "end_invert_ft": 99.0,
                    "flow_cfs": 0.3,
                }
            ],
            "manholes": [],
        }
        manager.latest_outputs["sanitary"] = deepcopy(summary)
        project.meta["sanitary_summary"] = deepcopy(summary)

        _recompute_sanitary_summary(project, manager)
        sanitary = manager.latest_outputs["sanitary"]

        self.assertEqual(sanitary["manhole_count"], len(sanitary["manholes"]))
        self.assertIn("disconnected_segments", sanitary)
        self.assertIn("missing_data_segments", sanitary)
        self.assertGreater(sanitary["total_system_capacity_cfs"], 0)
        self.assertGreaterEqual(sanitary["max_capacity_ratio"], 0)
        self.assertEqual(sanitary["controlling_segment"], "SAN-1")

    def test_storm_missing_data_segments_include_missing_field_names(self) -> None:
        manager = ProjectManager()
        project = manager.project
        summary = {
            "segments": [
                {
                    "pipe": "P-1",
                    "path": [[0.0, 0.0], [40.0, 0.0]],
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "diameter_in": 12.0,
                }
            ]
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(summary)
        project.meta["storm_pipe_summary"] = deepcopy(summary)

        _recompute_storm_summary(project, manager)
        missing = manager.latest_outputs["storm_pipe_summary"]["missing_data_segments"]

        self.assertEqual(missing[0]["segment"], "P-1")
        self.assertIn("flow_cfs", missing[0]["missing_fields"])
        self.assertIn("from", missing[0]["missing_fields"])

    def test_assisted_off_fails_on_incomplete_storm_and_sanitary_truth(self) -> None:
        manager = ProjectManager()
        ctx = PlannerExecutionContext(
            parsed={
                "deliverables": ["sanitary_plan"],
                "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
            },
            manager=manager,
            route=RoutingDecision(path="test", reasons=[]),
        )
        manager.latest_outputs["storm_pipe_summary"] = {
            "segments": [{"pipe": "P-1", "path": [[0.0, 0.0], [40.0, 0.0]], "start_invert": 100.0, "end_invert": 99.0}]
        }
        manager.project.meta["storm_pipe_summary"] = deepcopy(manager.latest_outputs["storm_pipe_summary"])
        manager.latest_outputs["sanitary"] = {
            "segments": [{"name": "SAN-1", "route_points": [[0.0, 0.0], [100.0, 0.0]], "flow_cfs": 0.2}],
            "manholes": [],
        }
        manager.project.meta["sanitary_summary"] = deepcopy(manager.latest_outputs["sanitary"])

        self.assertFalse(_run_manual_gate(ctx, "storm_pipe_gate"))
        self.assertFalse(_run_manual_gate(ctx, "sanitary_gate"))
        failures = [item for stage in ctx.stage_results for item in (stage.meta.get("failures") or [])]
        codes = {item.get("code") for item in failures}

        self.assertIn("MANUAL_STORM_SEGMENT_DATA_MISSING", codes)
        self.assertIn("MANUAL_SANITARY_SEGMENT_DATA_MISSING", codes)


if __name__ == "__main__":
    unittest.main()
