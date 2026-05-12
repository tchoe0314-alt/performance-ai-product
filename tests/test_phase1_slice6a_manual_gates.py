from __future__ import annotations

import unittest
from copy import deepcopy

from backend.planning.runtime import PlannerExecutionContext, RoutingDecision
from core.geometry_core import ProjectModel
from core.project_manager import ProjectManager
from planner import _run_manual_gate


def _surface() -> dict:
    return {
        "source_quality": "terrain",
        "nrows": 2,
        "ncols": 2,
        "origin": [0.0, 0.0],
        "cell_size": 50.0,
        "values": [[100.0, 100.5], [101.0, 101.5]],
    }


def _canonical_grading() -> dict:
    return {
        "success": True,
        "existing_surface": _surface(),
        "proposed_surface": _surface(),
        "derived_actions": {
            "proposed_contour_count": 4,
            "spot_grade_count": 4,
            "flow_arrow_count": 2,
        },
        "earthwork": {"cut_cf": 100.0, "fill_cf": 95.0, "net_cf": 5.0},
    }


def _canonical_drainage() -> dict:
    return {
        "success": True,
        "structures": [{"id": "inlet-1", "name": "CAN_INLET", "object_type": "inlet"}],
        "pipes": [{"id": "drain-1", "name": "CAN_DRAIN", "length_ft": 30.0}],
        "stats": {"inlet_count": 1, "pipe_count": 1, "structure_count": 1},
        "coordination": {
            "preferred_outfall": {"name": "CAN_OUTFALL"},
            "preferred_targets": [{"name": "CAN_BASIN"}],
        },
    }


def _canonical_storm() -> dict:
    return {
        "success": True,
        "pipe_count": 1,
        "total_length_ft": 100.0,
        "total_system_flow_cfs": 1.2,
        "total_system_capacity_cfs": 4.8,
        "controlling_segment": "CAN_STORM",
        "max_capacity_ratio": 0.25,
        "missing_data_segments": [],
        "hydraulic_source": "engine",
        "source_detail": "canonical test storm",
        "graph_validation": {"valid": True},
        "hydraulic_validation": {"valid": True},
        "segments": [
            {
                "id": "storm-1",
                "pipe": "CAN_STORM",
                "path": [[0.0, 0.0], [100.0, 0.0]],
                "length_ft": 100.0,
                "diameter_in": 18.0,
                "flow_cfs": 1.2,
                "capacity_cfs": 4.8,
                "capacity_ratio": 0.25,
                "slope_ft_ft": 0.01,
                "start_invert": 99.0,
                "end_invert": 98.0,
            }
        ],
    }


def _canonical_sanitary() -> dict:
    return {
        "success": True,
        "route_count": 1,
        "service_count": 1,
        "manhole_count": 2,
        "disconnected_segments": [],
        "missing_data_segments": [],
        "total_system_capacity_cfs": 2.0,
        "max_capacity_ratio": 0.3,
        "controlling_segment": "CAN_SAN",
        "missing_service_buildings": [],
        "slope_violations": [],
        "missing_manhole_points": [],
        "storm_conflicts": [],
        "graph_validation": {"valid": True},
        "network_validation": {"valid": True},
        "segments": [
            {
                "id": "san-1",
                "name": "CAN_SAN",
                "segment_role": "main",
                "route_points": [[0.0, 10.0], [80.0, 10.0]],
                "length_ft": 80.0,
                "diameter_in": 8.0,
                "slope_ft_ft": 0.004,
            }
        ],
        "manholes": [{"id": "mh-1", "name": "CAN_MH_1"}, {"id": "mh-2", "name": "CAN_MH_2"}],
    }


def _canonical_utilities() -> dict:
    return {
        "success": True,
        "route_count": 1,
        "total_length_ft": 40.0,
        "fallback_used": False,
        "conflict_hooks": {
            "utility_segments": [
                {
                    "id": "util-1",
                    "name": "CAN_UTIL",
                    "system_type": "water",
                    "route_points": [[0.0, 20.0], [40.0, 20.0]],
                    "length_ft": 40.0,
                }
            ]
        },
    }


def _base_ctx() -> PlannerExecutionContext:
    project = ProjectModel(name="Slice 6A Manual Gate Test")
    manager = ProjectManager(project)
    return PlannerExecutionContext(
        parsed={
            "project_name": "Slice 6A Manual Gate Test",
            "mode": "site_plan",
            "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 100.0},
            "deliverables": ["sanitary_plan"],
            "meta": {"manual_mode": True, "input_mode": "manual", "source_input_mode": "manual"},
        },
        manager=manager,
        route=RoutingDecision(path="test", reasons=[]),
    )


def _plan(ctx: PlannerExecutionContext) -> dict:
    return {
        "project_name": "Slice 6A Manual Gate Test",
        "units": "ft",
        "actions": [],
        "meta": {
            "manager_export": {
                "metrics": {
                    "earthwork_cut_cf": {"value": 100.0},
                    "earthwork_fill_cf": {"value": 95.0},
                    "earthwork_net_cf": {"value": 5.0},
                }
            }
        },
    }


def _failure_codes(ctx: PlannerExecutionContext) -> list[str]:
    codes: list[str] = []
    for stage in ctx.stage_results:
        for failure in (stage.meta or {}).get("failures") or []:
            codes.append(str(failure.get("code")))
    return codes


class Phase1Slice6AManualGateTest(unittest.TestCase):
    def test_stale_latest_outputs_grading_cannot_override_canonical_grading(self) -> None:
        ctx = _base_ctx()
        ctx.manager.project.meta["grading_summary"] = _canonical_grading()
        ctx.manager.latest_outputs["grading"] = {"fallback_used": True}

        self.assertTrue(_run_manual_gate(ctx, "grading_gate", _plan(ctx)))
        self.assertEqual(_failure_codes(ctx), [])

    def test_stale_latest_outputs_drainage_cannot_override_canonical_drainage(self) -> None:
        ctx = _base_ctx()
        ctx.manager.project.meta["grading_summary"] = _canonical_grading()
        ctx.manager.project.meta["drainage_canonical"] = _canonical_drainage()
        ctx.manager.latest_outputs["grading"] = {"fallback_used": True}
        ctx.manager.latest_outputs["drainage"] = {"success": False, "stats": {"inlet_count": 0, "pipe_count": 0}}

        self.assertTrue(_run_manual_gate(ctx, "drainage_gate", _plan(ctx)))
        self.assertEqual(_failure_codes(ctx), [])

    def test_stale_latest_outputs_storm_cannot_override_canonical_storm(self) -> None:
        ctx = _base_ctx()
        ctx.manager.project.meta["storm_pipe_summary"] = _canonical_storm()
        ctx.manager.latest_outputs["storm_pipe_summary"] = {
            "segments": [{"id": "stale", "pipe": "STALE_STORM"}],
            "missing_data_segments": [{"segment": "stale", "missing_fields": ["flow_cfs"]}],
        }

        self.assertTrue(_run_manual_gate(ctx, "storm_pipe_gate", _plan(ctx)))
        self.assertEqual(_failure_codes(ctx), [])

    def test_stale_latest_outputs_sanitary_cannot_override_canonical_sanitary(self) -> None:
        ctx = _base_ctx()
        ctx.manager.project.meta["sanitary_summary"] = _canonical_sanitary()
        ctx.manager.latest_outputs["sanitary"] = {"success": False, "fallback_used": True, "route_count": 0}

        self.assertTrue(_run_manual_gate(ctx, "sanitary_gate", _plan(ctx)))
        self.assertEqual(_failure_codes(ctx), [])

    def test_stale_latest_outputs_utilities_cannot_override_canonical_utilities(self) -> None:
        ctx = _base_ctx()
        ctx.manager.project.meta["utility_summary"] = _canonical_utilities()
        ctx.manager.latest_outputs["utilities"] = {"fallback_used": True, "route_count": 0}

        self.assertTrue(_run_manual_gate(ctx, "utility_gate", _plan(ctx)))
        self.assertEqual(_failure_codes(ctx), [])

    def test_assisted_off_still_fails_when_canonical_state_is_incomplete(self) -> None:
        ctx = _base_ctx()
        ctx.manager.project.meta["storm_pipe_summary"] = {
            "segments": [{"id": "storm-1", "pipe": "CAN_STORM"}],
            "missing_data_segments": [{"segment": "storm-1", "missing_fields": ["flow_cfs", "capacity_cfs"]}],
        }
        ctx.manager.latest_outputs["storm_pipe_summary"] = deepcopy(_canonical_storm())

        self.assertFalse(_run_manual_gate(ctx, "storm_pipe_gate", _plan(ctx)))
        self.assertIn("MANUAL_STORM_SEGMENT_DATA_MISSING", _failure_codes(ctx))


if __name__ == "__main__":
    unittest.main()
