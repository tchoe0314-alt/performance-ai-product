from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from backend.planning.common import canonical_stage_output
from backend.planning.coordination_state import full_coordination_state_snapshot, restore_full_coordination_state
from backend.planning.execution_control import canonical_state_diff, canonical_state_snapshot
from backend.planning.finalization import canonical_truth_audit
from backend.planning.late_stage_runners import run_qa_stage
from backend.planning.runtime import PlannerExecutionContext, RoutingDecision, collect_plan_stats
from core.geometry_core import ProjectModel
from core.project_manager import ConflictRecord, ConflictSeverity, ProjectManager
from engines.quantity_engine import compute_plan_quantities
from output.dxf_exporter import finalize_export_metadata, save_dxf
from planner import _run_manual_gate


def _surface() -> dict:
    return {
        "source_quality": "terrain",
        "source_detail": "Mapbox Terrain-RGB",
        "nrows": 2,
        "ncols": 2,
        "origin": [0.0, 0.0],
        "cell_size": 50.0,
        "values": [[100.0, 100.5], [101.0, 101.5]],
    }


def _canonical_grading() -> dict:
    return {
        "success": True,
        "source_quality": "terrain",
        "source_detail": "Mapbox Terrain-RGB",
        "existing_surface": _surface(),
        "proposed_surface": _surface(),
        "local_adjustments": [{"id": "grade-1", "kind": "tie_in"}],
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
        "source": "canonical",
        "structures": [
            {
                "id": "inlet-1",
                "name": "CAN_INLET",
                "object_type": "inlet",
                "structure_type": "inlet",
                "x": 0.0,
                "y": 0.0,
                "z": 101.0,
            },
            {
                "id": "outfall-1",
                "name": "CAN_OUTFALL",
                "object_type": "outfall",
                "structure_type": "outfall",
                "x": 100.0,
                "y": 0.0,
                "z": 98.0,
            },
        ],
        "pipes": [{"id": "drain-1", "name": "CAN_DRAIN", "length_ft": 30.0}],
        "pipe_runs": [{"id": "drain-run-1", "name": "CAN_DRAIN_RUN", "length_ft": 30.0}],
        "basins": [{"id": "basin-1", "name": "CAN_BASIN", "centroid_xy": [110.0, -20.0]}],
        "stats": {"structure_count": 2, "inlet_count": 1, "pipe_count": 1, "pipe_total_length_ft": 30.0},
        "coordination": {
            "preferred_outfall": {"name": "CAN_OUTFALL"},
            "preferred_targets": [{"name": "CAN_BASIN"}],
        },
        "export_validation": {"ready": True},
    }


def _canonical_storm() -> dict:
    return {
        "success": True,
        "source": "canonical",
        "pipe_count": 1,
        "total_length_ft": 100.0,
        "total_system_flow_cfs": 1.2,
        "total_system_capacity_cfs": 4.8,
        "max_capacity_ratio": 0.25,
        "controlling_segment": "CAN_STORM",
        "missing_data_segments": [],
        "hydraulic_source": "engine",
        "source_detail": "canonical test storm",
        "graph_validation": {"valid": True},
        "hydraulic_validation": {"valid": True},
        "segments": [
            {
                "id": "storm-1",
                "pipe": "CAN_STORM",
                "from": "CAN_INLET",
                "to": "CAN_OUTFALL",
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
        "source": "canonical",
        "route_count": 1,
        "service_count": 1,
        "manhole_count": 2,
        "total_length_ft": 80.0,
        "main_length_ft": 80.0,
        "lateral_length_ft": 0.0,
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
        "stats": {"segment_count": 1, "total_length_ft": 80.0, "main_length_ft": 80.0, "service_count": 1, "manhole_count": 2},
        "segments": [
            {
                "id": "san-1",
                "name": "CAN_SAN",
                "segment_role": "main",
                "start_name": "CAN_MH_1",
                "end_name": "CAN_MH_2",
                "route_points": [[0.0, 10.0], [80.0, 10.0]],
                "length_ft": 80.0,
                "diameter_in": 8.0,
                "slope_ft_ft": 0.004,
                "start_invert_ft": 97.0,
                "end_invert_ft": 96.68,
                "flow_cfs": 0.3,
            }
        ],
        "manholes": [
            {"id": "mh-1", "name": "CAN_MH_1", "x": 0.0, "y": 10.0, "rim_elev_ft": 101.0},
            {"id": "mh-2", "name": "CAN_MH_2", "x": 80.0, "y": 10.0, "rim_elev_ft": 100.5},
        ],
    }


def _canonical_utilities() -> dict:
    return {
        "success": True,
        "source": "canonical",
        "route_count": 1,
        "total_length_ft": 40.0,
        "system_type": "water",
        "fallback_used": False,
        "stats": {"total_length_ft": 40.0},
        "conflict_hooks": {
            "utility_segments": [
                {
                    "id": "util-1",
                    "name": "CAN_UTIL",
                    "system_type": "water",
                    "route_points": [[0.0, 20.0], [40.0, 20.0]],
                    "length_ft": 40.0,
                    "cover_start_ft": 4.0,
                    "cover_end_ft": 4.0,
                }
            ]
        },
    }


def _actions() -> list[dict]:
    return [
        {
            "task": "rectangle",
            "layer": "SITE",
            "origin": [0.0, 0.0],
            "width": 120.0,
            "height": 90.0,
            "label": "Site Boundary",
            "canonical_source_id": "site-1",
            "canonical_source_type": "site",
        },
        {
            "task": "polyline",
            "layer": "PIPE",
            "points": [[0.0, 0.0], [100.0, 0.0]],
            "label": "CAN_STORM",
            "canonical_source_id": "storm-1",
            "canonical_source_type": "storm_pipe",
        },
        {
            "task": "polyline",
            "layer": "SAN",
            "points": [[0.0, 10.0], [80.0, 10.0]],
            "label": "CAN_SAN",
            "canonical_source_id": "san-1",
            "canonical_source_type": "sanitary",
        },
        {
            "task": "polyline",
            "layer": "UTILITY",
            "points": [[0.0, 20.0], [40.0, 20.0]],
            "label": "CAN_UTIL",
            "canonical_source_id": "util-1",
            "canonical_source_type": "utility",
        },
    ]


def _seed_phase1_state() -> tuple[ProjectModel, ProjectManager]:
    project = ProjectModel(name="Phase 1 Exit Regression")
    manager = ProjectManager(project)
    project.meta["grading_summary"] = _canonical_grading()
    project.meta["drainage_canonical"] = _canonical_drainage()
    project.meta["storm_pipe_summary"] = _canonical_storm()
    project.meta["sanitary_summary"] = _canonical_sanitary()
    project.meta["utility_summary"] = _canonical_utilities()
    project.meta["coordination_summary"] = {
        "resolved_count": 1,
        "unresolved_conflicts": [],
        "best_near_valid_candidate": None,
    }
    project.meta["_expanded_plan"] = {"actions": deepcopy(_actions())}

    manager.latest_outputs["grading"] = {"success": False, "fallback_used": True}
    manager.latest_outputs["drainage"] = {"success": False, "stats": {"inlet_count": 0}, "structures": [{"name": "STALE_INLET"}]}
    manager.latest_outputs["storm_pipe_summary"] = {
        "source": "stale",
        "total_length_ft": 999.0,
        "segments": [{"id": "stale-storm", "pipe": "STALE_STORM", "length_ft": 999.0}],
        "missing_data_segments": [{"segment": "stale-storm", "missing_fields": ["flow_cfs"]}],
    }
    manager.latest_outputs["sanitary"] = {"source": "stale", "total_length_ft": 888.0, "segments": [{"name": "STALE_SAN"}]}
    manager.latest_outputs["utilities"] = {"source": "stale", "total_length_ft": 777.0, "conflict_hooks": {"utility_segments": [{"name": "STALE_UTIL"}]}}
    manager.set_metric("storm_pipe_length_ft", 999.0, units="ft", category="stale")
    manager.set_metric("sanitary_total_length_ft", 888.0, units="ft", category="stale")
    manager.set_metric("utility_total_length_ft", 777.0, units="ft", category="stale")
    manager.set_metric("layout_action_count", 99, category="stale")
    manager.set_metric("earthwork_cut_cf", 100.0, units="cf", category="grading")
    manager.set_metric("earthwork_fill_cf", 95.0, units="cf", category="grading")
    manager.set_metric("earthwork_net_cf", 5.0, units="cf", category="grading")
    return project, manager


def _manual_ctx(manager: ProjectManager) -> PlannerExecutionContext:
    return PlannerExecutionContext(
        parsed={
            "project_name": "Phase 1 Exit Regression",
            "mode": "site_plan",
            "lot": {"x": 0.0, "y": 0.0, "w": 120.0, "h": 90.0},
            "deliverables": ["sanitary_plan"],
            "meta": {"manual_mode": True, "input_mode": "manual", "source_input_mode": "manual"},
        },
        manager=manager,
        route=RoutingDecision(path="test", reasons=[]),
    )


def _plan(project: ProjectModel, manager: ProjectManager) -> dict:
    return {
        "project_name": "Phase 1 Exit Regression",
        "units": "ft",
        "actions": deepcopy(_actions()),
        "meta": {
            "grading": deepcopy(project.meta["grading_summary"]),
            "drainage": deepcopy(project.meta["drainage_canonical"]),
            "storm_pipes": deepcopy(project.meta["storm_pipe_summary"]),
            "sanitary": deepcopy(project.meta["sanitary_summary"]),
            "utilities": deepcopy(project.meta["utility_summary"]),
            "coordination": deepcopy(project.meta["coordination_summary"]),
            "manager_export": manager.export_metrics(),
            "deliverables": {"requested": ["site_plan", "storm_pipe_plan"], "produced": ["site_plan", "storm_pipe_plan"]},
        },
    }


class Phase1ExitRegressionTest(unittest.TestCase):
    def test_phase1_engineering_truth_is_stable_end_to_end(self) -> None:
        project, manager = _seed_phase1_state()

        self.assertEqual(canonical_stage_output(project, manager, "storm_pipes")["segments"][0]["pipe"], "CAN_STORM")
        self.assertEqual(canonical_stage_output(project, manager, "sanitary")["segments"][0]["name"], "CAN_SAN")
        self.assertEqual(canonical_stage_output(project, manager, "utilities")["conflict_hooks"]["utility_segments"][0]["name"], "CAN_UTIL")

        ctx = _manual_ctx(manager)
        gate_plan = _plan(project, manager)
        for gate_name in ["grading_gate", "drainage_gate", "storm_pipe_gate", "sanitary_gate", "utility_gate"]:
            self.assertTrue(_run_manual_gate(ctx, gate_name, deepcopy(gate_plan)), gate_name)

        incomplete_ctx = _manual_ctx(manager)
        project.meta["storm_pipe_summary"] = {
            "segments": [{"id": "storm-1", "pipe": "CAN_STORM"}],
            "total_system_flow_cfs": 0.0,
            "total_system_capacity_cfs": 0.0,
            "controlling_segment": "CAN_STORM",
            "max_capacity_ratio": 0.0,
            "missing_data_segments": [{"segment": "storm-1", "missing_fields": ["flow_cfs", "capacity_cfs"]}],
            "hydraulic_source": "engine",
            "source_detail": "incomplete canonical test storm",
            "pipe_count": 1,
            "graph_validation": {"valid": True},
            "hydraulic_validation": {"valid": True},
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(_canonical_storm())
        self.assertFalse(_run_manual_gate(incomplete_ctx, "storm_pipe_gate", deepcopy(gate_plan)))
        failures = [item for stage in incomplete_ctx.stage_results for item in (stage.meta.get("failures") or [])]
        self.assertIn("MANUAL_STORM_SEGMENT_DATA_MISSING", {item.get("code") for item in failures})
        project.meta["storm_pipe_summary"] = _canonical_storm()
        manager.latest_outputs["storm_pipe_summary"] = {
            "source": "stale",
            "total_length_ft": 999.0,
            "segments": [{"id": "stale-storm", "pipe": "STALE_STORM", "length_ft": 999.0}],
        }

        snapshot = canonical_state_snapshot(project, manager)
        self.assertEqual(snapshot["storm_total_length_ft"], 100.0)
        self.assertEqual(snapshot["sanitary_total_length_ft"], 80.0)
        self.assertEqual(snapshot["utility_total_length_ft"], 40.0)
        self.assertEqual(canonical_state_diff(snapshot, canonical_state_snapshot(project, manager))["changed_count"], 0)

        project.meta["system_dirty_state"] = {"storm_pipes": {"state": "clean", "reasons": []}}
        manager.mark_system_clean("storm_pipes", message="regression")
        manager.add_conflict(
            ConflictRecord(
                code="BASELINE",
                message="Baseline conflict",
                severity=ConflictSeverity.WARNING,
                category="regression",
            )
        )
        full_snapshot = full_coordination_state_snapshot(project, manager)
        before_failed_candidate = deepcopy(manager.to_dict())
        project.meta["preferred_corridors"] = {"storm": {"source": "leaked-candidate"}}
        project.meta["storm_pipe_summary"] = {"segments": [{"pipe": "LEAK"}]}
        manager.latest_outputs["storm_pipe_summary"] = {"segments": [{"pipe": "LEAK"}]}
        manager.set_metric("candidate_metric", 999.0, category="candidate")
        manager.add_conflict(
            ConflictRecord(
                code="LEAKED_CONFLICT",
                message="Failed candidate should not persist.",
                severity=ConflictSeverity.ERROR,
                category="candidate",
            )
        )
        manager.mark_system_dirty("storm_pipes", reason="candidate leak", source="candidate")
        restore_full_coordination_state(project, manager, full_snapshot)
        self.assertEqual(manager.to_dict(), before_failed_candidate)

        storm = project.meta["storm_pipe_summary"]
        sanitary = project.meta["sanitary_summary"]
        for field in ["total_system_flow_cfs", "total_system_capacity_cfs", "max_capacity_ratio", "controlling_segment", "missing_data_segments"]:
            self.assertIn(field, storm)
        for field in ["manhole_count", "disconnected_segments", "missing_data_segments", "total_system_capacity_cfs", "max_capacity_ratio", "controlling_segment"]:
            self.assertIn(field, sanitary)

        plan = _plan(project, manager)
        quantities = compute_plan_quantities(plan)
        self.assertTrue(quantities.success)
        self.assertEqual(quantities.totals["pipe_length_ft"], 100.0)
        self.assertEqual(quantities.totals["sanitary_length_ft"], 80.0)
        self.assertEqual(quantities.totals["utility_length_ft"], 40.0)
        self.assertEqual(quantities.explain["quantity_audit"]["pipe_length_ft"]["source_object_ids"], ["storm-1"])
        plan["meta"]["quantities"] = {
            "success": True,
            "totals": deepcopy(quantities.totals),
            "explain": deepcopy(quantities.explain),
        }
        plan["meta"]["qa"] = {"stats": {"estimated_pipe_length_ft": 100.0, "estimated_utility_length_ft": 40.0}}
        stats = collect_plan_stats(plan)
        self.assertEqual(stats["estimated_pipe_length_ft"], 100.0)
        self.assertEqual(stats["estimated_utility_length_ft"], 120.0)

        captured: dict = {}

        def capture_stats(qa_plan: dict) -> dict:
            captured["plan"] = deepcopy(qa_plan)
            return {"estimated_pipe_length_ft": 100.0, "estimated_utility_length_ft": 40.0}

        with (
            patch("backend.planning.late_stage_runners.collect_plan_stats", side_effect=capture_stats),
            patch("backend.planning.late_stage_runners.validate_site_layout"),
            patch("backend.planning.late_stage_runners.validate_expanded_site_plan"),
            patch("backend.planning.late_stage_runners.evaluate_constraints"),
            patch("backend.planning.late_stage_runners.run_plan_checks", return_value={}),
        ):
            run_qa_stage(
                PlannerExecutionContext(parsed={"project_name": "Phase 1 Exit Regression"}, manager=manager, route=RoutingDecision(path="test", reasons=[])),
                project_model_to_plan=lambda _project, _name: {"actions": deepcopy(_actions()), "meta": {}},
                manual_mode_enabled=lambda _parsed: False,
            )

        qa_plan = captured["plan"]
        self.assertEqual(qa_plan["meta"]["storm_pipes"]["segments"][0]["pipe"], "CAN_STORM")
        self.assertEqual(qa_plan["meta"]["sanitary"]["segments"][0]["name"], "CAN_SAN")
        self.assertNotEqual(qa_plan["meta"]["storm_pipes"]["segments"][0]["pipe"], "STALE_STORM")

        truth = canonical_truth_audit({"mode": "site_plan", "lot": {"w": 120.0, "h": 90.0}}, plan, manager=manager, sanitary_requested=lambda _parsed: True)
        checks = {item["code"]: item for item in truth["checks"]}
        self.assertTrue(checks["PIPE_LENGTH_CONSISTENT"]["ok"])
        self.assertEqual(checks["PIPE_LENGTH_CONSISTENT"]["context"]["truth_length_ft"], 100.0)
        self.assertTrue(checks["SANITARY_LENGTH_CONSISTENT"]["ok"])
        self.assertEqual(checks["SANITARY_LENGTH_CONSISTENT"]["context"]["truth_length_ft"], 80.0)
        self.assertTrue(checks["EXPORT_OBJECT_MAPPING_COMPLETE"]["ok"])

        self.assertNotIn("sheet_registry", plan["meta"])
        self.assertNotIn("export_audit", plan["meta"])
        finalized = finalize_export_metadata(plan)
        self.assertTrue(plan["meta"]["sheet_registry"])
        self.assertTrue(plan["meta"]["export_audit"])
        self.assertEqual(plan["meta"]["sheet_registry"], finalized["sheet_registry"])
        self.assertTrue(plan["meta"]["export_audit"]["sheet_registry_meta_matches_plan"])
        before_save_registry = deepcopy(plan["meta"]["sheet_registry"])
        before_save_audit = deepcopy(plan["meta"]["export_audit"])
        with tempfile.TemporaryDirectory() as tmpdir:
            save_dxf(plan, filename=str(Path(tmpdir) / "phase1-exit.dxf"))
        self.assertEqual(plan["meta"]["sheet_registry"], before_save_registry)
        self.assertEqual(plan["meta"]["export_audit"]["sheet_registry"], before_save_audit["sheet_registry"])
        self.assertEqual(plan["meta"]["storm_pipes"]["segments"][0]["pipe"], "CAN_STORM")
        self.assertEqual(plan["meta"]["sanitary"]["segments"][0]["name"], "CAN_SAN")


if __name__ == "__main__":
    unittest.main()
