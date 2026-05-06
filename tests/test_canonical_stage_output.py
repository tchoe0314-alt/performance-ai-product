from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from backend.planning.coordination_state import snapshot_coordination_state
from backend.planning.late_stage_runners import run_qa_stage
from backend.planning.runtime import PlannerExecutionContext, RoutingDecision
from backend.planning.sheet_stage import run_sheet_stage
from core.geometry_core import ProjectModel
from core.project_manager import ProjectManager
from planner import _attach_canonical_stage_outputs, _manual_gate_plan


def _surface(tag: str) -> dict:
    base = 100.0 if tag == "canonical" else 999.0
    return {
        "tag": tag,
        "source_quality": "terrain" if tag == "canonical" else "stale",
        "nrows": 2,
        "ncols": 2,
        "origin": [0.0, 0.0],
        "cell_size": 50.0,
        "values": [[base, base + 0.5], [base + 1.0, base + 1.5]],
    }


def _seed_canonical_project() -> tuple[ProjectModel, ProjectManager]:
    project = ProjectModel(name="Canonical Truth Test")
    manager = ProjectManager(project)
    project.meta["grading_summary"] = {
        "source": "project-meta",
        "existing_surface": _surface("canonical"),
        "proposed_surface": _surface("canonical"),
        "local_adjustments": [{"id": "canonical-adjustment"}],
    }
    project.meta["drainage_canonical"] = {
        "source": "project-meta",
        "structures": [{"name": "CAN_IN", "x": 0.0, "y": 0.0, "z": 100.0}],
        "stats": {"source": "canonical-drainage"},
        "export_validation": {"ok": True},
    }
    project.meta["storm_pipe_summary"] = {
        "segments": [
            {
                "pipe": "CAN_STORM",
                "from": "CAN_IN",
                "to": "CAN_IN",
                "path": [[0.0, 0.0], [100.0, 0.0]],
                "length_ft": 100.0,
                "start_invert": 96.0,
                "end_invert": 95.0,
            }
        ]
    }
    project.meta["sanitary_summary"] = {"segments": [{"name": "CAN_SAN"}], "manholes": []}
    project.meta["utility_summary"] = {"segments": [{"name": "CAN_UTIL"}]}
    project.meta["coordination_summary"] = {"source": "project-meta"}
    project.meta["parking_program"] = {"source": "project-meta"}
    project.meta["profiles"] = [{"name": "CAN_PROFILE"}]
    project.meta["cross_sections"] = [{"name": "CAN_SECTION"}]

    manager.latest_outputs["grading"] = {
        "source": "stale-cache",
        "existing_surface": _surface("stale"),
        "proposed_surface": _surface("stale"),
        "local_adjustments": [{"id": "stale-adjustment"}],
    }
    manager.latest_outputs["drainage"] = {
        "source": "stale-cache",
        "structures": [{"name": "STALE_IN", "x": 0.0, "y": 0.0, "z": 99.0}],
        "stats": {"source": "stale-drainage"},
        "export_validation": {"ok": False},
    }
    manager.latest_outputs["storm_pipe_summary"] = {"segments": [{"pipe": "STALE_STORM", "path": [[0.0, 0.0], [10.0, 0.0]], "length_ft": 10.0}]}
    manager.latest_outputs["sanitary"] = {"segments": [{"name": "STALE_SAN"}], "manholes": []}
    manager.latest_outputs["utilities"] = {"segments": [{"name": "STALE_UTIL"}]}
    manager.latest_outputs["coordination"] = {"source": "stale-cache"}
    manager.latest_outputs["parking_program"] = {"source": "stale-cache"}
    manager.latest_outputs["profiles"] = [{"name": "STALE_PROFILE"}]
    manager.latest_outputs["cross_sections"] = [{"name": "STALE_SECTION"}]
    return project, manager


def _ctx(manager: ProjectManager) -> PlannerExecutionContext:
    return PlannerExecutionContext(
        parsed={
            "project_name": "Canonical Truth Test",
            "manual_fields": {"lot": {"x": 0, "y": 0, "w": 120, "h": 120}},
            "lot": {"x": 0, "y": 0, "w": 120, "h": 120},
        },
        manager=manager,
        route=RoutingDecision(path="test", reasons=[]),
    )


class CanonicalStageOutputTest(unittest.TestCase):
    def test_planner_stage_meta_uses_project_meta_over_stale_latest_outputs(self) -> None:
        project, manager = _seed_canonical_project()
        plan = {"meta": {}}

        _attach_canonical_stage_outputs(plan, project, manager)

        self.assertEqual(plan["meta"]["grading"]["source"], "project-meta")
        self.assertEqual(plan["meta"]["drainage"]["structures"][0]["name"], "CAN_IN")
        self.assertEqual(plan["meta"]["storm_pipes"]["segments"][0]["pipe"], "CAN_STORM")
        self.assertEqual(plan["meta"]["profiles"][0]["name"], "CAN_PROFILE")
        self.assertTrue(project.meta["canonical_state_warnings"]["grading"]["cache_differs"])
        self.assertTrue(project.meta["canonical_state_warnings"]["drainage"]["cache_differs"])

    def test_manual_gate_plan_uses_canonical_project_meta(self) -> None:
        project, manager = _seed_canonical_project()

        plan = _manual_gate_plan(_ctx(manager))

        self.assertEqual(plan["meta"]["grading"]["source"], "project-meta")
        self.assertEqual(plan["meta"]["drainage"]["stats"]["source"], "canonical-drainage")
        self.assertEqual(plan["meta"]["profiles"][0]["name"], "CAN_PROFILE")

    def test_qa_stage_reads_canonical_project_meta(self) -> None:
        project, manager = _seed_canonical_project()
        captured: dict = {}

        def capture_stats(plan: dict) -> dict:
            captured["plan"] = deepcopy(plan)
            return {}

        with (
            patch("backend.planning.late_stage_runners.collect_plan_stats", side_effect=capture_stats),
            patch("backend.planning.late_stage_runners.validate_site_layout"),
            patch("backend.planning.late_stage_runners.validate_expanded_site_plan"),
            patch("backend.planning.late_stage_runners.run_plan_checks", return_value={}),
        ):
            run_qa_stage(
                _ctx(manager),
                project_model_to_plan=lambda _project, _name: {"actions": [], "meta": {}},
                manual_mode_enabled=lambda _parsed: False,
            )

        qa_plan = captured["plan"]
        self.assertEqual(qa_plan["meta"]["grading"]["source"], "project-meta")
        self.assertEqual(qa_plan["meta"]["drainage"]["structures"][0]["name"], "CAN_IN")

    def test_sheet_stage_uses_canonical_grading_and_drainage(self) -> None:
        project, manager = _seed_canonical_project()

        run_sheet_stage(
            _ctx(manager),
            requested_profile_or_sections=lambda _parsed: (True, False),
            build_existing_surface=lambda _parsed: _surface("fallback"),
            expanded_obstacle_rectangles=lambda _project: [],
            path_hits_buffered_rect=lambda _path, _rect: False,
            grading_local_adjustments=lambda _project: project.meta["grading_summary"]["local_adjustments"],
            station_text=lambda value: f"{value:.2f}",
            sample_grid_surface=lambda surface, _x, _y, default: surface.get("values", [[default]])[0][0],
            preferred_corridor_for_segment=lambda _project, _segment: {},
            sheet_alignment=lambda _project, _parsed: ([[0.0, 0.0], [100.0, 0.0]], True, "test"),
        )

        profiles = manager.latest_outputs["profiles"]
        road_profile = next(item for item in profiles if item["name"] == "ROAD PROFILE 1")
        storm_profile = next(item for item in profiles if item["name"] == "CAN_STORM PROFILE")
        self.assertEqual(road_profile["stations"][0]["existing_elev_ft"], 100.0)
        self.assertEqual(storm_profile["structure_marks"][0]["label"], "CAN_IN")

    def test_coordination_snapshot_uses_canonical_project_meta(self) -> None:
        project, manager = _seed_canonical_project()

        snapshot = snapshot_coordination_state(project, manager)

        self.assertEqual(snapshot["grading"]["source"], "project-meta")
        self.assertEqual(snapshot["drainage_mutable"]["structures"][0]["name"], "CAN_IN")
        self.assertEqual(snapshot["storm"]["segments"][0]["pipe"], "CAN_STORM")
        self.assertEqual(snapshot["sanitary"]["segments"][0]["name"], "CAN_SAN")
        self.assertEqual(snapshot["utilities"]["segments"][0]["name"], "CAN_UTIL")


if __name__ == "__main__":
    unittest.main()
