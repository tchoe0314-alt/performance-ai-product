import unittest
from copy import deepcopy
from unittest.mock import patch

from core.geometry_core import ProjectModel
from core.project_manager import ProjectManager
from planner import (
    _apply_local_grading_repair,
    _apply_conflict_resolution,
    _detect_coordination_conflicts,
    _group_cluster_groups,
    _group_conflict_clusters,
    _path_hits_buffered_rect,
    _point_inside_buffered_rect,
    _refresh_conflict_resolved_state,
    _solve_conflict_cluster,
    _solve_conflict_cluster_group,
    build_plan,
)


def _manual_payload(**overrides):
    payload = {
        "project_name": "Conflict Resolution Test",
        "units": "ft",
        "mode": "site_plan",
        "project_type": "commercial_pad",
        "site_type": "commercial_pad",
        "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
        "setback": 10.0,
        "street_edge": "bottom",
        "layout_strategy": "front_parking",
        "site_plan": {"building_width": 48.0, "building_depth": 34.0, "parking_count": 24},
        "meta": {"input_mode": "manual", "source_input_mode": "manual", "manual_mode": True},
    }
    payload.update(overrides)
    return payload


def _failure_codes(plan):
    return [item.get("code") for item in (((plan.get("meta") or {}).get("manual_validation") or {}).get("failures") or [])]


def _manager_with_summaries():
    project = ProjectModel()
    manager = ProjectManager(project)
    grading = {"proposed_surface": None}
    manager.latest_outputs["grading"] = deepcopy(grading)
    project.meta["grading_summary"] = deepcopy(grading)
    return project, manager


class ConflictResolutionEngineTest(unittest.TestCase):
    def test_storm_sanitary_crossing_is_detected_and_resolved(self) -> None:
        project, manager = _manager_with_summaries()
        storm = {
            "segments": [
                {
                    "pipe": "STORM-1",
                    "from": "INLET-1",
                    "to": "J-1",
                    "path": [[0.0, 0.0], [20.0, 0.0]],
                    "diameter_in": 12.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 0.5,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.125,
                    "slope_pct": 5.0,
                }
            ]
        }
        sanitary = {
            "segments": [
                {
                    "name": "SAN-MAIN-1",
                    "segment_role": "main",
                    "route_points": [[10.0, -10.0], [10.0, 10.0]],
                    "diameter_in": 8.0,
                    "start_invert_ft": 99.2,
                    "end_invert_ft": 98.8,
                    "slope_ft_ft": 0.02,
                    "start_name": "SMH-1",
                    "end_name": "SMH-2",
                }
            ],
            "manholes": [],
            "stats": {},
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm)
        project.meta["storm_pipe_summary"] = deepcopy(storm)
        manager.latest_outputs["sanitary"] = deepcopy(sanitary)
        project.meta["sanitary_summary"] = deepcopy(sanitary)
        manager.latest_outputs["utilities"] = {"conflict_hooks": {"utility_segments": []}}
        project.meta["utility_summary"] = {"conflict_hooks": {"utility_segments": []}}

        conflicts = _detect_coordination_conflicts(project, manager)
        clearance = next(conflict for conflict in conflicts if conflict["conflict_type"] == "sanitary_storm_clearance")
        result = _apply_conflict_resolution(project, manager, clearance, assisted_mode=False)
        self.assertTrue(result["success"])
        _refresh_conflict_resolved_state(project, manager)
        remaining = [conflict for conflict in _detect_coordination_conflicts(project, manager) if conflict["conflict_type"] == "sanitary_storm_clearance"]
        self.assertEqual(remaining, [])

    def test_water_crossing_resolution_lowers_utility(self) -> None:
        project, manager = _manager_with_summaries()
        storm = {
            "segments": [
                {
                    "pipe": "STORM-1",
                    "from": "INLET-1",
                    "to": "J-1",
                    "path": [[0.0, 0.0], [20.0, 0.0]],
                    "diameter_in": 12.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 0.5,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.125,
                    "slope_pct": 5.0,
                }
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[10.0, -10.0], [10.0, 10.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 99.5,
                        "end_invert_ft": 99.4,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm)
        project.meta["storm_pipe_summary"] = deepcopy(storm)
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        clearance = next(conflict for conflict in conflicts if conflict["conflict_type"] == "storm_water_clearance")
        before_storm = manager.latest_outputs["storm_pipe_summary"]["segments"][0]["start_invert"]
        before = manager.latest_outputs["utilities"]["conflict_hooks"]["utility_segments"][0]["start_invert_ft"]
        result = _apply_conflict_resolution(project, manager, clearance, assisted_mode=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["strategy"], "vertical_adjustment")
        after = manager.latest_outputs["utilities"]["conflict_hooks"]["utility_segments"][0]["start_invert_ft"]
        after_storm = manager.latest_outputs["storm_pipe_summary"]["segments"][0]["start_invert"]
        self.assertTrue(after < before or after_storm < before_storm)

    def test_reroute_around_building_pad(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"}
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [30.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        geometry = next(conflict for conflict in conflicts if conflict["conflict_type"] == "water_building_pad_geometry")
        result = _apply_conflict_resolution(project, manager, geometry, assisted_mode=False)
        self.assertTrue(result["success"])
        self.assertIn("constructability", result)
        self.assertIn("engineering_deltas", result)
        rerouted = manager.latest_outputs["utilities"]["conflict_hooks"]["utility_segments"][0]["route_points"]
        rect = {"x": 8.0, "y": 8.0, "w": 10.0, "h": 10.0, "buffer_ft": 2.0}
        self.assertGreater(len(rerouted), 2)
        self.assertFalse(any(_point_inside_buffered_rect(point, rect) for point in rerouted))

    def test_terminal_shift_moves_service_endpoint_out_of_building_pad(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [41.2, 73.0], "width": 57.6, "height": 27.0, "label": "BLDG"}
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "generic_utility_1",
                        "system_type": "water",
                        "route_points": [[0.0, 55.0], [70.0, 55.0], [70.0, 86.5]],
                        "diameter_in": 6.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        geometry = next(conflict for conflict in conflicts if conflict["conflict_type"] == "water_building_pad_geometry")
        result = _apply_conflict_resolution(project, manager, geometry, assisted_mode=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["strategy"], "terminal_shift")
        _refresh_conflict_resolved_state(project, manager)
        remaining = [conflict for conflict in _detect_coordination_conflicts(project, manager) if conflict["conflict_type"] == "water_building_pad_geometry"]
        self.assertEqual(remaining, [])

    def test_slope_violation_fixed_by_invert_adjustment(self) -> None:
        project, manager = _manager_with_summaries()
        sanitary = {
            "segments": [
                {
                    "name": "SAN-MAIN-1",
                    "segment_role": "main",
                    "route_points": [[0.0, 0.0], [20.0, 0.0]],
                    "diameter_in": 8.0,
                    "start_invert_ft": 100.0,
                    "end_invert_ft": 99.95,
                    "slope_ft_ft": 0.0025,
                    "start_name": "SMH-1",
                    "end_name": "SMH-2",
                }
            ],
            "manholes": [],
            "stats": {},
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = deepcopy(sanitary)
        project.meta["sanitary_summary"] = deepcopy(sanitary)
        manager.latest_outputs["utilities"] = {"conflict_hooks": {"utility_segments": []}}
        project.meta["utility_summary"] = {"conflict_hooks": {"utility_segments": []}}

        conflicts = _detect_coordination_conflicts(project, manager)
        slope = next(conflict for conflict in conflicts if conflict["conflict_type"] == "slope_violation")
        result = _apply_conflict_resolution(project, manager, slope, assisted_mode=False)
        self.assertTrue(result["success"])
        _refresh_conflict_resolved_state(project, manager)
        updated = manager.latest_outputs["sanitary"]["segments"][0]
        self.assertGreaterEqual(updated["slope_ft_ft"], 0.01)

    def test_related_conflicts_are_grouped_into_one_cluster(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"}
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [30.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 99.5,
                        "end_invert_ft": 99.4,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        storm = {
            "segments": [
                {
                    "pipe": "STORM-1",
                    "from": "INLET-1",
                    "to": "J-1",
                    "path": [[10.0, 0.0], [10.0, 20.0]],
                    "diameter_in": 12.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 0.5,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.125,
                    "slope_pct": 5.0,
                }
            ]
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm)
        project.meta["storm_pipe_summary"] = deepcopy(storm)
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        project.meta["preferred_corridors"] = {
            "storm": {"orientation": "horizontal", "axis_value": 22.0, "weight": 0.8},
            "water": {"orientation": "horizontal", "axis_value": 28.0, "weight": 0.7},
            "generic": {"orientation": "horizontal", "axis_value": 26.0, "weight": 0.5},
        }
        clusters = _group_conflict_clusters(conflicts, project)

        self.assertEqual(len(clusters), 1)
        self.assertGreaterEqual(clusters[0]["conflict_count"], 2)
        self.assertTrue(clusters[0]["trench_like"])
        self.assertTrue(clusters[0]["trench_group_id"].startswith("trench::"))
        self.assertIn(clusters[0]["corridor_axis"], {"horizontal", "vertical"})

    def test_cluster_solver_returns_best_candidate_for_related_conflicts(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"}
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [30.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 99.5,
                        "end_invert_ft": 99.4,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        storm = {
            "segments": [
                {
                    "pipe": "STORM-1",
                    "from": "INLET-1",
                    "to": "J-1",
                    "path": [[10.0, 0.0], [10.0, 20.0]],
                    "diameter_in": 12.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 0.5,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.125,
                    "slope_pct": 5.0,
                }
            ]
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm)
        project.meta["storm_pipe_summary"] = deepcopy(storm)
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        cluster = _group_conflict_clusters(conflicts)[0]
        result = _solve_conflict_cluster(project, manager, cluster, assisted_mode=False)

        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["candidate_count"], 1)
        self.assertTrue(result["resolution_rows"])
        self.assertIn("engineering_deltas", result)
        self.assertIn("candidate_summaries", result)
        self.assertTrue(result["selection_reason"])

    def test_multi_conflict_trench_cluster_prefers_coordinated_solution(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"},
                {"task": "rectangle", "layer": "BUILDING", "origin": [20.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-2"},
                {"task": "rectangle", "layer": "WALK", "origin": [0.0, 0.0], "width": 40.0, "height": 6.0, "label": "ADA-1"},
            ]
        }
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.5},
            "generic": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.0},
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [35.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.7,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        cluster = _group_conflict_clusters(conflicts, project)[0]
        result = _solve_conflict_cluster(project, manager, cluster, assisted_mode=False)

        self.assertTrue(result["success"])
        summaries = result["candidate_summaries"]
        trench = next(row for row in summaries if row["candidate_mode"] == "trench_cluster")
        balanced = next(row for row in summaries if row["candidate_mode"] == "balanced")
        self.assertLessEqual(trench["score"], balanced["score"])
        self.assertIn(result["selected_candidate_mode"], {"trench_cluster", "protected_zone_bias"})
        self.assertIn("added length", result["selection_reason"])

    def test_geometry_resolution_prefers_protected_zone_aware_corridor_candidate_over_naive_detour(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"},
                {"task": "rectangle", "layer": "WALK", "origin": [0.0, 0.0], "width": 40.0, "height": 6.0, "label": "ADA-1"},
            ]
        }
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.4},
            "generic": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.0},
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [30.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        geometry = next(conflict for conflict in conflicts if conflict["conflict_type"] == "water_building_pad_geometry")
        result = _apply_conflict_resolution(
            project,
            manager,
            geometry,
            assisted_mode=False,
            candidate_mode="protected_zone_bias",
            cluster_context={"corridor_axis": "horizontal", "axis_value": 24.0},
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["evaluated_candidates"])
        chosen = manager.latest_outputs["utilities"]["conflict_hooks"]["utility_segments"][0]["route_points"]
        ada_rect = {"x": 0.0, "y": 0.0, "w": 40.0, "h": 6.0, "buffer_ft": 2.0}
        self.assertFalse(_path_hits_buffered_rect(chosen, ada_rect))
        self.assertTrue(any(point[1] >= 24.0 for point in chosen))
        naive = next(row for row in result["evaluated_candidates"] if "ada_path" in row["protected_zone_hit_kinds"])
        chosen_row = next(row for row in result["evaluated_candidates"] if row["valid"] and row["score"] == min(item["score"] for item in result["evaluated_candidates"] if item["valid"]))
        self.assertIn("ada_path", naive["protected_zone_hit_kinds"])
        self.assertLess(chosen_row["score"], naive["score"])

    def test_crossing_hierarchy_prefers_moving_the_upper_system(self) -> None:
        project, manager = _manager_with_summaries()
        storm = {
            "segments": [
                {
                    "pipe": "STORM-1",
                    "from": "INLET-1",
                    "to": "J-1",
                    "path": [[0.0, 0.0], [20.0, 0.0]],
                    "diameter_in": 12.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 0.5,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.125,
                    "slope_pct": 5.0,
                }
            ]
        }
        sanitary = {
            "segments": [
                {
                    "name": "SAN-MAIN-1",
                    "segment_role": "main",
                    "route_points": [[10.0, -10.0], [10.0, 10.0]],
                    "diameter_in": 8.0,
                    "start_invert_ft": 99.2,
                    "end_invert_ft": 98.8,
                    "slope_ft_ft": 0.02,
                    "start_name": "SMH-1",
                    "end_name": "SMH-2",
                }
            ],
            "manholes": [],
            "stats": {},
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm)
        project.meta["storm_pipe_summary"] = deepcopy(storm)
        manager.latest_outputs["sanitary"] = deepcopy(sanitary)
        project.meta["sanitary_summary"] = deepcopy(sanitary)
        manager.latest_outputs["utilities"] = {"conflict_hooks": {"utility_segments": []}}
        project.meta["utility_summary"] = {"conflict_hooks": {"utility_segments": []}}

        conflicts = _detect_coordination_conflicts(project, manager)
        clearance = next(conflict for conflict in conflicts if conflict["conflict_type"] == "sanitary_storm_clearance")
        result = _apply_conflict_resolution(project, manager, clearance, assisted_mode=False, candidate_mode="balanced")

        self.assertTrue(result["success"])
        self.assertEqual(result["changed_systems"], ["storm"])
        self.assertEqual(result["strategy"], "vertical_adjustment")

    def test_grading_realism_can_invalidate_geometrically_valid_candidate(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"},
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [30.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        geometry = next(conflict for conflict in conflicts if conflict["conflict_type"] == "water_building_pad_geometry")
        with patch(
            "planner._apply_local_grading_repair",
            return_value={
                "disturbance_class": "high",
                "delta_depth_ft": 2.2,
                "cut_fill_delta_cf": 240.0,
                "repair_modes": ["ada_path_repair", "road_edge_transition"],
                "protected_zone_context": [],
            },
        ):
            result = _apply_conflict_resolution(project, manager, geometry, assisted_mode=False, candidate_mode="protected_zone_bias")
        self.assertFalse(result["success"])
        self.assertTrue(any(row["grading_blocked"] for row in result["evaluated_candidates"]))

    def test_selected_candidate_reasoning_reflects_real_tradeoff(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"},
                {"task": "rectangle", "layer": "WALK", "origin": [0.0, 0.0], "width": 40.0, "height": 6.0, "label": "ADA-1"},
            ]
        }
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.4},
            "generic": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.0},
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [30.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    }
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        cluster = _group_conflict_clusters(_detect_coordination_conflicts(project, manager), project)[0]
        result = _solve_conflict_cluster(project, manager, cluster, assisted_mode=False)
        self.assertTrue(result["success"])
        self.assertIn("added length", result["selection_reason"])
        self.assertIn("protected-zone penalty", result["selection_reason"])
        self.assertIn("crossing-rule penalty", result["selection_reason"])

    def test_trench_group_search_prefers_coordinated_solution_over_balanced_group(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"},
                {"task": "rectangle", "layer": "BUILDING", "origin": [56.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-2"},
                {"task": "rectangle", "layer": "WALK", "origin": [0.0, 0.0], "width": 90.0, "height": 6.0, "label": "ADA-1"},
            ]
        }
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.6},
            "generic": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.0},
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [36.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                    {
                        "name": "WATER-2",
                        "system_type": "water",
                        "route_points": [[46.0, 13.0], [88.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        clusters = _group_conflict_clusters(conflicts, project)
        self.assertEqual(len(clusters), 2)
        groups = _group_cluster_groups(clusters)
        self.assertEqual(len(groups), 1)

        result = _solve_conflict_cluster_group(project, manager, groups[0], assisted_mode=False)

        self.assertTrue(result["success"])
        self.assertNotEqual(result["group_plan"], "balanced_group")
        balanced = next(row for row in result["candidate_summaries"] if row["plan_name"].startswith("balanced_group"))
        self.assertLessEqual(result["score"], balanced["score"])
        self.assertLessEqual(result["cluster_group_summary"]["corridor_switch_count"], balanced["corridor_switch_count"])
        self.assertIn("clusters", result["selection_reason"])

    def test_trench_group_constructability_rejects_messier_valid_plan(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"},
                {"task": "rectangle", "layer": "BUILDING", "origin": [56.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-2"},
                {"task": "rectangle", "layer": "WALK", "origin": [0.0, 0.0], "width": 90.0, "height": 6.0, "label": "ADA-1"},
            ]
        }
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.6},
            "generic": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.0},
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [36.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                    {
                        "name": "WATER-2",
                        "system_type": "water",
                        "route_points": [[46.0, 13.0], [88.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        result = _solve_conflict_cluster_group(
            project,
            manager,
            _group_cluster_groups(_group_conflict_clusters(_detect_coordination_conflicts(project, manager), project))[0],
            assisted_mode=False,
        )

        self.assertTrue(result["success"])
        balanced = next(row for row in result["candidate_summaries"] if row["plan_name"].startswith("balanced_group"))
        self.assertTrue(balanced["valid"])
        self.assertLess(result["constructability_score"], balanced["constructability_score"])

    def test_trench_group_search_is_bounded_and_stable(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"},
                {"task": "rectangle", "layer": "BUILDING", "origin": [56.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-2"},
            ]
        }
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.6},
            "generic": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.0},
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 13.0], [36.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                    {
                        "name": "WATER-2",
                        "system_type": "water",
                        "route_points": [[46.0, 13.0], [88.0, 13.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 98.0,
                        "end_invert_ft": 97.8,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project.meta["storm_pipe_summary"] = {"segments": []}
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        group = _group_cluster_groups(_group_conflict_clusters(_detect_coordination_conflicts(project, manager), project))[0]
        result_one = _solve_conflict_cluster_group(project, manager, group, assisted_mode=False)

        project_two, manager_two = _manager_with_summaries()
        project_two.meta.update(deepcopy(project.meta))
        manager_two.latest_outputs["storm_pipe_summary"] = {"segments": []}
        project_two.meta["storm_pipe_summary"] = {"segments": []}
        manager_two.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project_two.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager_two.latest_outputs["utilities"] = deepcopy(utilities)
        project_two.meta["utility_summary"] = deepcopy(utilities)
        group_two = _group_cluster_groups(_group_conflict_clusters(_detect_coordination_conflicts(project_two, manager_two), project_two))[0]
        result_two = _solve_conflict_cluster_group(project_two, manager_two, group_two, assisted_mode=False)

        self.assertLessEqual(len(result_one["candidate_summaries"]), 12)
        self.assertEqual(
            [row["plan_name"] for row in result_one["candidate_summaries"]],
            [row["plan_name"] for row in result_two["candidate_summaries"]],
        )
        self.assertEqual(result_one["group_plan"], result_two["group_plan"])

    def test_multi_cluster_crossing_strategy_is_explicit_and_auditable(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.4},
            "storm": {"orientation": "horizontal", "axis_value": 0.0, "weight": 0.8},
            "generic": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.0},
        }
        storm = {
            "segments": [
                {
                    "pipe": "STORM-1",
                    "from": "A",
                    "to": "B",
                    "path": [[0.0, 0.0], [30.0, 0.0]],
                    "diameter_in": 18.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 1.0,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.25,
                    "slope_pct": 3.0,
                },
                {
                    "pipe": "STORM-2",
                    "from": "B",
                    "to": "C",
                    "path": [[40.0, 0.0], [70.0, 0.0]],
                    "diameter_in": 18.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 1.0,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.25,
                    "slope_pct": 3.0,
                },
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[10.0, -12.0], [10.0, 12.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 99.7,
                        "end_invert_ft": 99.6,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                    {
                        "name": "WATER-2",
                        "system_type": "water",
                        "route_points": [[50.0, -12.0], [50.0, 12.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 99.7,
                        "end_invert_ft": 99.6,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm)
        project.meta["storm_pipe_summary"] = deepcopy(storm)
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        group = _group_cluster_groups(_group_conflict_clusters(conflicts, project))[0]
        result = _solve_conflict_cluster_group(project, manager, group, assisted_mode=False)

        self.assertEqual(result["selected_group_strategy"], "hierarchy_first")
        upper = next(row for row in result["candidate_summaries"] if row["crossing_strategy"] == "upper_reroute_first")
        hierarchy = next(row for row in result["candidate_summaries"] if row["crossing_strategy"] == "hierarchy_first")
        self.assertTrue(upper["crossing_prefit_applied"])
        self.assertIn("utilities", upper["changed_systems"])
        self.assertLessEqual(hierarchy["score"], upper["score"])
        self.assertIn("hierarchy_first", result["selection_reason"])

    def test_multi_cluster_crossing_strategy_can_flip_to_upper_reroute_when_storm_lowering_is_costly(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["preferred_corridors"] = {
            "water": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.4},
            "storm": {"orientation": "horizontal", "axis_value": 0.0, "weight": 0.8},
            "generic": {"orientation": "horizontal", "axis_value": 24.0, "weight": 1.0},
        }
        storm = {
            "segments": [
                {
                    "pipe": "STORM-1",
                    "from": "A",
                    "to": "B",
                    "path": [[0.0, 0.0], [30.0, 0.0]],
                    "diameter_in": 18.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 1.0,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.25,
                    "slope_pct": 3.0,
                },
                {
                    "pipe": "STORM-2",
                    "from": "B",
                    "to": "C",
                    "path": [[40.0, 0.0], [70.0, 0.0]],
                    "diameter_in": 18.0,
                    "start_invert": 100.0,
                    "end_invert": 99.0,
                    "cover_start_ft": 3.0,
                    "cover_end_ft": 3.0,
                    "flow_cfs": 1.0,
                    "capacity_cfs": 4.0,
                    "capacity_ratio": 0.25,
                    "slope_pct": 3.0,
                },
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[10.0, -12.0], [10.0, 12.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 99.7,
                        "end_invert_ft": 99.6,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                    {
                        "name": "WATER-2",
                        "system_type": "water",
                        "route_points": [[50.0, -12.0], [50.0, 12.0]],
                        "diameter_in": 8.0,
                        "start_invert_ft": 99.7,
                        "end_invert_ft": 99.6,
                        "cover_start_ft": 3.0,
                        "cover_end_ft": 3.0,
                    },
                ],
            }
        }
        manager.latest_outputs["storm_pipe_summary"] = deepcopy(storm)
        project.meta["storm_pipe_summary"] = deepcopy(storm)
        manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
        project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        def fake_cluster_solver(_project, _manager, matched, assisted_mode=False, allowed_candidate_modes=None, crossing_strategy=""):
            strategy = crossing_strategy or "hierarchy_first"
            if strategy == "upper_reroute_first":
                return {
                    "success": True,
                    "cluster_id": matched.get("cluster_id"),
                    "candidate_count": 1,
                    "selected_order": "priority:corridor_bias",
                    "selected_candidate_mode": "corridor_bias",
                    "changed_systems": ["utilities"],
                    "resolution_rows": [{"strategy": "clearance_reroute"}],
                    "constructability_score": 24.0,
                    "engineering_deltas": {
                        "added_length_ft": 18.0,
                        "added_depth_ft": 0.0,
                        "added_structures": 0,
                        "grading_impact": {"score": 12.0, "blocked": False},
                        "crossing_hierarchy": {"penalty": 0.0, "blocked": False, "total_checks": 1, "compliant_checks": 1, "interaction_types": ["crossing"]},
                        "constructability_impact": {"score": 24.0, "bend_complexity": 2, "protected_zone_penalty": 0.0},
                    },
                    "best_near_valid_candidate": {},
                    "post_validation": {"valid": True, "systems": {}, "consistency": {"storm_summary_current": True, "sanitary_summary_current": True, "utility_summary_current": True, "drainage_summary_current": True}},
                    "remaining_cluster_conflicts": [],
                    "score": 24.0,
                    "candidate_summaries": [],
                    "selection_reason": "Upper reroute preserved crossing hierarchy with lower grading disruption.",
                    "crossing_strategy": strategy,
                }
            return {
                "success": True,
                "cluster_id": matched.get("cluster_id"),
                "candidate_count": 1,
                "selected_order": "priority:balanced",
                "selected_candidate_mode": "balanced",
                "changed_systems": ["storm"],
                "resolution_rows": [{"strategy": "vertical_adjustment"}],
                "constructability_score": 80.0,
                "engineering_deltas": {
                    "added_length_ft": 0.0,
                    "added_depth_ft": 3.2,
                    "added_structures": 0,
                    "grading_impact": {"score": 240.0, "blocked": False},
                    "crossing_hierarchy": {"penalty": 0.0, "blocked": False, "total_checks": 1, "compliant_checks": 1, "interaction_types": ["crossing"]},
                    "constructability_impact": {"score": 80.0, "bend_complexity": 0, "protected_zone_penalty": 0.0},
                },
                "best_near_valid_candidate": {},
                "post_validation": {"valid": True, "systems": {}, "consistency": {"storm_summary_current": True, "sanitary_summary_current": True, "utility_summary_current": True, "drainage_summary_current": True}},
                "remaining_cluster_conflicts": [],
                "score": 80.0,
                "candidate_summaries": [],
                "selection_reason": "Hierarchy-first lowering remained buildable but caused higher grading cost.",
                "crossing_strategy": strategy,
            }

        with patch("planner._solve_conflict_cluster", side_effect=fake_cluster_solver), patch("planner._cluster_group_remaining_conflicts", return_value=[]):
            conflicts = _detect_coordination_conflicts(project, manager)
            group = _group_cluster_groups(_group_conflict_clusters(conflicts, project))[0]
            result = _solve_conflict_cluster_group(project, manager, group, assisted_mode=False)

        self.assertEqual(result["selected_group_strategy"], "upper_reroute_first")
        self.assertIn("upper_reroute_first", result["selection_reason"])
        self.assertGreaterEqual(result["cluster_group_summary"]["crossing_strategy_prefit_reroutes"], 1)

    def test_local_grading_repair_carries_protected_zone_context(self) -> None:
        project, _manager = _manager_with_summaries()
        project.meta["_expanded_plan"] = {
            "actions": [
                {"task": "rectangle", "layer": "ROAD", "origin": [0.0, 0.0], "width": 50.0, "height": 14.0, "label": "ROAD-1"},
                {"task": "rectangle", "layer": "WALK", "origin": [8.0, 14.0], "width": 20.0, "height": 6.0, "label": "ADA-1"},
            ]
        }
        note = _apply_local_grading_repair(project, "TEST-SEG", delta_depth_ft=1.25, point=[12.0, 10.0])
        self.assertTrue(note["protected_zone_context"])
        self.assertIn("road_edge_transition", note["repair_modes"])
        self.assertIn("ada_path_repair", note["repair_modes"])

    def test_manual_mode_fails_when_coordination_cannot_be_resolved(self) -> None:
        def fake_coordination(ctx, hydrology):
            summary = {
                "success": False,
                "detected_conflicts": [{"conflict_type": "storm_sanitary_clearance"}],
                "resolved_conflicts": [],
                "unresolved_conflicts": [{"conflict_type": "storm_sanitary_clearance"}],
                "assumption_resolutions": [],
            }
            ctx.manager.latest_outputs["coordination"] = deepcopy(summary)
            ctx.manager.project.meta["coordination_summary"] = deepcopy(summary)
            ctx.add_stage("coordination_resolution", False, "Injected unresolved coordination conflict for regression.")

        with patch("planner._run_conflict_resolution_stage", side_effect=fake_coordination):
            plan = build_plan(_manual_payload())
        self.assertIn("MANUAL_COORDINATION_UNRESOLVED", _failure_codes(plan))

    def test_assisted_mode_qa_reports_resolved_vs_unresolved_conflicts(self) -> None:
        def fake_coordination(ctx, hydrology):
            summary = {
                "success": False,
                "detected_conflicts": [{"conflict_type": "storm_sanitary_clearance"}],
                "resolved_conflicts": [{"conflict_type": "storm_water_clearance"}],
                "unresolved_conflicts": [{"conflict_type": "storm_sanitary_clearance"}],
                "assumption_resolutions": [{"conflict_type": "storm_water_clearance"}],
            }
            ctx.manager.latest_outputs["coordination"] = deepcopy(summary)
            ctx.manager.project.meta["coordination_summary"] = deepcopy(summary)
            ctx.add_stage("coordination_resolution", False, "Injected assisted coordination summary.")

        assisted = deepcopy(_manual_payload())
        assisted["meta"] = {"input_mode": "assisted", "source_input_mode": "assisted", "manual_mode": False}
        with patch("planner._run_conflict_resolution_stage", side_effect=fake_coordination):
            plan = build_plan(assisted)
        messages = [item.get("message") for item in (((plan.get("meta") or {}).get("qa") or {}).get("issues") or [])]
        self.assertTrue(any("Unresolved coordination conflict remains" in (message or "") for message in messages))
        self.assertTrue(any("resolved using assisted-mode assumptions" in (message or "") for message in messages))


if __name__ == "__main__":
    unittest.main()
