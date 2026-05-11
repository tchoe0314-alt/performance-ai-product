from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from core.project_manager import ConflictRecord, ConflictSeverity, ProjectManager
from planner import _solve_conflict_cluster


class CoordinationCandidateIsolationTest(unittest.TestCase):
    def test_failed_cluster_candidate_restores_full_manager_state(self) -> None:
        manager = ProjectManager()
        project = manager.project
        project.meta["preferred_corridors"] = {"storm": {"source": "canonical"}}
        project.meta["system_dirty_state"] = {"storm_pipes": {"state": "clean", "reasons": []}}
        project.meta["storm_pipe_summary"] = {"segments": []}
        project.meta["sanitary_summary"] = {"segments": []}
        project.meta["utility_summary"] = {"conflict_hooks": {"utility_segments": []}}
        project.meta["grading_summary"] = {"local_adjustments": []}
        project.meta["drainage_canonical"] = {"structures": [], "stats": {}, "export_validation": {}}
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": []}
        manager.latest_outputs["utilities"] = {"conflict_hooks": {"utility_segments": []}}
        manager.latest_outputs["grading"] = {"local_adjustments": []}
        manager.latest_outputs["drainage"] = {"structures": [], "stats": {}, "export_validation": {}}
        manager.set_metric("baseline_metric", 1.0, category="test")
        manager.add_conflict(
            ConflictRecord(
                code="BASELINE",
                message="Baseline conflict",
                severity=ConflictSeverity.WARNING,
                category="test",
            )
        )
        manager.record_event("baseline_event", "Baseline audit event.", category="test")
        before = deepcopy(manager.to_dict())

        conflict = {
            "conflict_type": "forced_geometry",
            "involved_objects": ["PIPE-1", "BLDG-1"],
            "cluster_id": "cluster::forced",
        }
        cluster = {
            "cluster_id": "cluster::forced",
            "conflicts": [conflict],
            "objects": ["PIPE-1", "BLDG-1"],
        }

        def mutating_failed_candidate(*_args, **_kwargs):
            project.meta["preferred_corridors"] = {"storm": {"source": "leaked-candidate"}}
            project.meta["system_dirty_state"] = {"storm_pipes": {"state": "dirty", "reasons": ["leak"]}}
            project.drawing_entities.append({"leaked": True})
            manager.latest_outputs["storm_pipe_summary"] = {"segments": [{"pipe": "LEAK"}]}
            manager.latest_outputs["utilities"] = {"conflict_hooks": {"utility_segments": [{"name": "LEAK"}]}}
            manager.set_metric("candidate_metric", 999.0, category="candidate")
            manager.add_conflict(
                ConflictRecord(
                    code="LEAKED_CONFLICT",
                    message="Candidate conflict should roll back.",
                    severity=ConflictSeverity.ERROR,
                    category="candidate",
                )
            )
            manager.record_event("leaked_event", "Candidate audit should roll back.", category="candidate")
            manager.mark_system_dirty("storm_pipes", reason="candidate leak", source="candidate")
            return {"success": False, "failure_reason": "forced candidate failure"}

        with (
            patch("planner._cluster_candidate_orders", return_value=[{"name": "forced", "candidate_mode": "balanced", "conflicts": [conflict]}]),
            patch("planner._cluster_remaining_conflicts", return_value=[conflict]),
            patch("planner._detect_coordination_conflicts", return_value=[conflict]),
            patch("planner._apply_conflict_resolution", side_effect=mutating_failed_candidate),
            patch("planner._refresh_conflict_resolved_state", return_value={}),
            patch("planner._post_reroute_validations", return_value={"valid": False}),
        ):
            result = _solve_conflict_cluster(project, manager, cluster, assisted_mode=False)

        self.assertFalse(result["success"])
        self.assertEqual(manager.to_dict(), before)
        self.assertIs(manager.project, project)


if __name__ == "__main__":
    unittest.main()
