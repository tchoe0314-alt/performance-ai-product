from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from backend.planning.canonical_export import canonical_export_actions
from backend.planning.finalization import canonical_truth_audit
from backend.planning.late_stage_runners import run_qa_stage
from backend.planning.runtime import PlannerExecutionContext, RoutingDecision
from core.geometry_core import ProjectModel
from core.project_manager import ProjectManager
from engines.quantity_engine import compute_plan_quantities


def _metric(value: float) -> dict:
    return {"value": value, "units": "ft", "category": "test", "meta": {}}


def _seed_project_and_manager() -> tuple[ProjectModel, ProjectManager]:
    project = ProjectModel(name="Slice 5 Canonical Consistency")
    manager = ProjectManager(project)
    project.meta["drainage_canonical"] = {
        "success": True,
        "source": "canonical",
        "structures": [
            {"id": "inlet-1", "name": "CAN_INLET", "object_type": "inlet", "x": 0.0, "y": 0.0, "z": 101.0}
        ],
        "pipes": [{"id": "drain-1", "name": "CAN_DRAIN", "length_ft": 15.0}],
        "basins": [],
        "stats": {"structure_count": 1, "inlet_count": 1, "pipe_count": 1, "pipe_total_length_ft": 15.0},
        "export_validation": {"ready": True},
    }
    project.meta["storm_pipe_summary"] = {
        "source": "canonical",
        "pipe_count": 1,
        "total_length_ft": 100.0,
        "total_system_flow_cfs": 1.5,
        "total_system_capacity_cfs": 4.5,
        "max_capacity_ratio": 0.333,
        "controlling_segment": "CAN_STORM",
        "graph_validation": {"valid": True},
        "hydraulic_validation": {"valid": True},
        "missing_data_segments": [],
        "segments": [
            {
                "id": "storm-1",
                "pipe": "CAN_STORM",
                "path": [[0.0, 0.0], [100.0, 0.0]],
                "length_ft": 100.0,
                "diameter_in": 18.0,
                "flow_cfs": 1.5,
                "capacity_cfs": 4.5,
                "slope_ft_ft": 0.01,
                "start_invert": 99.0,
                "end_invert": 98.0,
            }
        ],
    }
    project.meta["sanitary_summary"] = {
        "source": "canonical",
        "route_count": 1,
        "total_length_ft": 80.0,
        "main_length_ft": 80.0,
        "lateral_length_ft": 0.0,
        "service_count": 1,
        "manhole_count": 2,
        "graph_validation": {"valid": True},
        "network_validation": {"valid": True},
        "missing_service_buildings": [],
        "stats": {"segment_count": 1, "total_length_ft": 80.0, "main_length_ft": 80.0, "service_count": 1, "manhole_count": 2},
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
        "manholes": [
            {"id": "mh-1", "name": "CAN_MH_1", "x": 0.0, "y": 10.0},
            {"id": "mh-2", "name": "CAN_MH_2", "x": 80.0, "y": 10.0},
        ],
    }
    project.meta["utility_summary"] = {
        "source": "canonical",
        "route_count": 1,
        "total_length_ft": 40.0,
        "system_type": "water",
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
    project.meta["coordination_summary"] = {"resolved_count": 0, "unresolved_conflicts": []}

    manager.latest_outputs["drainage"] = {"source": "stale", "structures": [{"name": "STALE_INLET"}], "stats": {"inlet_count": 99}}
    manager.latest_outputs["storm_pipe_summary"] = {
        "source": "stale",
        "total_length_ft": 999.0,
        "segments": [{"id": "storm-stale", "pipe": "STALE_STORM", "length_ft": 999.0}],
    }
    manager.latest_outputs["sanitary"] = {"source": "stale", "total_length_ft": 888.0}
    manager.latest_outputs["utilities"] = {"source": "stale", "total_length_ft": 777.0}
    manager.set_metric("storm_pipe_length_ft", 999.0, units="ft", category="storm")
    manager.set_metric("storm_pipe_count", 9, category="storm")
    manager.set_metric("drainage_low_point_count", 99, category="drainage")
    manager.set_metric("sanitary_total_length_ft", 888.0, units="ft", category="sanitary")
    manager.set_metric("sanitary_manhole_count", 88, category="sanitary")
    manager.set_metric("utility_total_length_ft", 777.0, units="ft", category="utilities")
    manager.set_metric("utility_route_count", 77, category="utilities")
    return project, manager


def _ctx(manager: ProjectManager) -> PlannerExecutionContext:
    return PlannerExecutionContext(
        parsed={"project_name": "Slice 5 Canonical Consistency", "mode": "site_plan"},
        manager=manager,
        route=RoutingDecision(path="test", reasons=[]),
    )


class Phase1Slice5ConsistencyTest(unittest.TestCase):
    def test_quantities_qa_export_and_truth_prefer_canonical_over_stale_metrics(self) -> None:
        project, manager = _seed_project_and_manager()
        actions = canonical_export_actions(project)
        plan = {
            "project_name": "Slice 5 Canonical Consistency",
            "units": "ft",
            "actions": actions,
            "meta": {
                "drainage": deepcopy(project.meta["drainage_canonical"]),
                "storm_pipes": deepcopy(project.meta["storm_pipe_summary"]),
                "sanitary": deepcopy(project.meta["sanitary_summary"]),
                "utilities": deepcopy(project.meta["utility_summary"]),
                "coordination": deepcopy(project.meta["coordination_summary"]),
                "manager_export": manager.export_metrics(),
                "qa": {
                    "stats": {
                        "estimated_pipe_length_ft": 100.0,
                        "estimated_utility_length_ft": 40.0,
                    }
                },
            },
        }

        quantities = compute_plan_quantities(plan)

        self.assertTrue(quantities.success)
        self.assertEqual(quantities.totals["pipe_length_ft"], 100.0)
        self.assertEqual(quantities.totals["pipe_feature_count"], 1)
        self.assertEqual(quantities.totals["inlet_count"], 1)
        self.assertEqual(quantities.totals["sanitary_length_ft"], 80.0)
        self.assertEqual(quantities.totals["sanitary_manhole_count"], 2)
        self.assertEqual(quantities.totals["utility_length_ft"], 40.0)
        self.assertEqual(quantities.explain["quantity_audit"]["pipe_length_ft"]["source_object_ids"], ["storm-1"])
        self.assertEqual(quantities.explain["quantity_audit"]["sanitary_length_ft"]["source_object_ids"], ["san-1"])
        self.assertEqual(quantities.explain["quantity_audit"]["utility_length_ft"]["source_object_ids"], ["util-1"])

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
                _ctx(manager),
                project_model_to_plan=lambda _project, _name: {"actions": actions, "meta": {}},
                manual_mode_enabled=lambda _parsed: False,
            )

        qa_plan = captured["plan"]
        self.assertEqual(qa_plan["meta"]["storm_pipes"]["segments"][0]["pipe"], "CAN_STORM")
        self.assertEqual(qa_plan["meta"]["drainage"]["structures"][0]["name"], "CAN_INLET")
        self.assertEqual(qa_plan["meta"]["sanitary"]["segments"][0]["name"], "CAN_SAN")

        labels = {action.get("label") for action in actions}
        self.assertIn("CAN_STORM", labels)
        self.assertIn("CAN_SAN", labels)
        self.assertNotIn("STALE_STORM", labels)

        plan["meta"]["quantities"] = {
            "success": True,
            "totals": deepcopy(quantities.totals),
            "explain": deepcopy(quantities.explain),
        }
        truth = canonical_truth_audit(
            {"mode": "site_plan"},
            plan,
            manager=manager,
            sanitary_requested=lambda _parsed: True,
        )
        checks = {item["code"]: item for item in truth["checks"]}
        self.assertTrue(checks["PIPE_LENGTH_CONSISTENT"]["ok"])
        self.assertTrue(checks["SANITARY_LENGTH_CONSISTENT"]["ok"])
        self.assertTrue(checks["EXPORT_OBJECT_MAPPING_COMPLETE"]["ok"])

    def test_truth_audit_rejects_stale_quantity_lengths_that_disagree_with_canonical(self) -> None:
        project, manager = _seed_project_and_manager()
        actions = canonical_export_actions(project)
        plan = {
            "project_name": "Slice 5 Stale Quantities",
            "units": "ft",
            "actions": actions,
            "meta": {
                "drainage": deepcopy(project.meta["drainage_canonical"]),
                "storm_pipes": deepcopy(project.meta["storm_pipe_summary"]),
                "sanitary": deepcopy(project.meta["sanitary_summary"]),
                "utilities": deepcopy(project.meta["utility_summary"]),
                "coordination": deepcopy(project.meta["coordination_summary"]),
                "manager_export": manager.export_metrics(),
                "qa": {
                    "stats": {
                        "estimated_pipe_length_ft": 100.0,
                        "estimated_utility_length_ft": 40.0,
                    }
                },
                "quantities": {
                    "success": True,
                    "totals": {
                        "pipe_length_ft": 77.0,
                        "utility_length_ft": 41.0,
                        "sanitary_length_ft": 120.0,
                    },
                },
            },
        }

        truth = canonical_truth_audit(
            {"mode": "site_plan"},
            plan,
            manager=manager,
            sanitary_requested=lambda _parsed: True,
        )
        checks = {item["code"]: item for item in truth["checks"]}

        self.assertFalse(truth["success"])
        self.assertFalse(checks["PIPE_LENGTH_CONSISTENT"]["ok"])
        self.assertFalse(checks["UTILITY_LENGTH_CONSISTENT"]["ok"])
        self.assertFalse(checks["SANITARY_LENGTH_CONSISTENT"]["ok"])
        self.assertEqual(checks["PIPE_LENGTH_CONSISTENT"]["context"]["quantity_delta_ft"], -23.0)
        self.assertEqual(checks["SANITARY_LENGTH_CONSISTENT"]["context"]["quantity_delta_ft"], 40.0)


if __name__ == "__main__":
    unittest.main()
