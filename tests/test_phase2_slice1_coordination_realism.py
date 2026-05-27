import unittest
from copy import deepcopy
from unittest.mock import patch

from core.geometry_core import ProjectModel
from core.project_manager import ProjectManager
from planner import (
    _apply_conflict_resolution,
    _attach_canonical_stage_outputs,
    _detect_coordination_conflicts,
    _preferred_corridors,
)


def _manager_with_summaries():
    project = ProjectModel()
    manager = ProjectManager(project)
    grading = {"proposed_surface": None}
    manager.latest_outputs["grading"] = deepcopy(grading)
    project.meta["grading_summary"] = deepcopy(grading)
    manager.latest_outputs["storm_pipe_summary"] = {"segments": []}
    project.meta["storm_pipe_summary"] = {"segments": []}
    manager.latest_outputs["sanitary"] = {"segments": [], "stats": {}, "manholes": []}
    project.meta["sanitary_summary"] = {"segments": [], "stats": {}, "manholes": []}
    return project, manager


def _seed_water_building_conflict(*, ada_walk: bool = False, preferred_corridor: bool = False):
    project, manager = _manager_with_summaries()
    actions = [
        {"task": "rectangle", "layer": "BUILDING", "origin": [8.0, 8.0], "width": 10.0, "height": 10.0, "label": "BLDG-1"}
    ]
    if ada_walk:
        actions.append({"task": "rectangle", "layer": "WALK", "origin": [0.0, 0.0], "width": 40.0, "height": 6.0, "label": "ADA-1"})
    project.meta["_expanded_plan"] = {"actions": actions}
    if preferred_corridor:
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
    manager.latest_outputs["utilities"] = deepcopy(utilities)
    project.meta["utility_summary"] = deepcopy(utilities)
    conflicts = _detect_coordination_conflicts(project, manager)
    geometry = next(conflict for conflict in conflicts if conflict["conflict_type"] == "water_building_pad_geometry")
    return project, manager, geometry


class Phase2Slice1CoordinationRealismTest(unittest.TestCase):
    def test_selected_candidate_and_final_plan_meta_include_coordination_realism(self) -> None:
        project, manager, geometry = _seed_water_building_conflict()

        result = _apply_conflict_resolution(project, manager, geometry, assisted_mode=False)

        self.assertTrue(result["success"])
        realism = result["coordination_realism"]
        self.assertIn("constructability_score", realism)
        self.assertIn("corridor_impact", realism)
        self.assertIn("ownership_class", realism)
        self.assertIn("ownership_impacts", realism)
        self.assertIn("structure_insertion_count", realism)
        self.assertIn("trench_grouping_context", realism)
        self.assertIn("unresolved_realism_flags", realism)
        self.assertIn("realism_notes", realism)

        coordination = {
            "resolved_conflicts": [{"resolution": deepcopy(result)}],
            "unresolved_clusters": [],
            "resolved_count": 1,
            "unresolved_count": 0,
        }
        project.meta["coordination_summary"] = deepcopy(coordination)
        manager.latest_outputs["coordination"] = {"resolved_conflicts": [], "stale": True}
        plan = {"meta": {}}

        _attach_canonical_stage_outputs(plan, project, manager)

        final_realism = plan["meta"]["coordination_realism"]
        self.assertEqual(final_realism["resolved_count"], 1)
        self.assertEqual(len(final_realism["selected_candidates"]), 1)
        self.assertEqual(final_realism["selected_candidates"][0]["ownership_class"], realism["ownership_class"])

    def test_best_near_candidate_reports_grading_impact(self) -> None:
        project, manager, geometry = _seed_water_building_conflict()

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
        realism = result["best_near_valid_candidate"]["coordination_realism"]
        self.assertTrue(realism["grading_impact"]["blocked"])
        self.assertIn("grading_blocked", realism["unresolved_realism_flags"])
        self.assertTrue(realism["realism_notes"])

    def test_protected_zone_and_corridor_candidates_report_realism_context(self) -> None:
        project, manager, geometry = _seed_water_building_conflict(ada_walk=True, preferred_corridor=True)

        result = _apply_conflict_resolution(
            project,
            manager,
            geometry,
            assisted_mode=False,
            candidate_mode="protected_zone_bias",
            cluster_context={"corridor_axis": "horizontal", "axis_value": 24.0},
        )

        self.assertTrue(result["success"])
        protected_rows = [
            row
            for row in result["evaluated_candidates"]
            if row["coordination_realism"]["protected_zone_hits"]
        ]
        self.assertTrue(protected_rows)
        self.assertTrue(any(hit["kind"] == "ada_path" for hit in protected_rows[0]["coordination_realism"]["protected_zone_hits"]))
        selected = result["coordination_realism"]
        self.assertIn("before_deviation_ft", selected["corridor_impact"])
        self.assertIn("after_deviation_ft", selected["corridor_impact"])
        self.assertGreaterEqual(selected["structure_insertion_count"], 0)

    def test_gis_wetlands_become_hard_protected_coordination_zones(self) -> None:
        project, manager = _manager_with_summaries()
        project.meta["gis_layers"] = {
            "wetlands": [
                {
                    "id": "WET-1",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[10.0, 0.0], [22.0, 0.0], [22.0, 20.0], [10.0, 20.0], [10.0, 0.0]]],
                    },
                    "properties": {"name": "Wetland A"},
                }
            ]
        }
        utilities = {
            "conflict_hooks": {
                "utility_system_type": "water",
                "utility_segments": [
                    {
                        "name": "WATER-WET",
                        "system_type": "water",
                        "route_points": [[0.0, 10.0], [35.0, 10.0]],
                        "start_invert_ft": 97.0,
                        "end_invert_ft": 97.0,
                    }
                ],
            }
        }
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        wetland_conflicts = [row for row in conflicts if row["conflict_type"] == "water_wetland_geometry"]

        self.assertTrue(wetland_conflicts)
        self.assertIn("wetland", wetland_conflicts[0]["systems"])
        self.assertIn("Wetland A", wetland_conflicts[0]["involved_objects"])

    def test_non_water_utilities_use_their_own_crossing_rules(self) -> None:
        project, manager = _manager_with_summaries()
        utilities = {
            "conflict_hooks": {
                "utility_segments": [
                    {
                        "name": "WATER-1",
                        "system_type": "water",
                        "route_points": [[0.0, 0.0], [40.0, 0.0]],
                        "start_invert_ft": 97.0,
                        "end_invert_ft": 97.0,
                    },
                    {
                        "name": "GAS-1",
                        "system_type": "gas",
                        "route_points": [[20.0, -8.0], [20.0, 8.0]],
                        "start_invert_ft": 97.4,
                        "end_invert_ft": 97.4,
                    },
                ],
            }
        }
        manager.latest_outputs["utilities"] = deepcopy(utilities)
        project.meta["utility_summary"] = deepcopy(utilities)

        conflicts = _detect_coordination_conflicts(project, manager)
        gas_water = [row for row in conflicts if row["conflict_type"] == "gas_water_clearance"]

        self.assertTrue(gas_water)
        self.assertEqual(gas_water[0]["preferred_lower_system"], "gas")
        self.assertEqual(gas_water[0]["interaction_type"], "crossing")

    def test_preferred_corridors_use_gis_easement_axis_when_available(self) -> None:
        project = ProjectModel()
        project.meta["gis_layers"] = {
            "easements": [
                {
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0.0, 90.0], [300.0, 90.0], [300.0, 110.0], [0.0, 110.0], [0.0, 90.0]]],
                    },
                    "properties": {"name": "Utility Easement A"},
                }
            ]
        }

        corridors = _preferred_corridors(
            {"lot": {"x": 0.0, "y": 0.0, "w": 300.0, "h": 200.0}, "street_edge": "bottom"},
            project,
        )

        self.assertEqual(corridors["water"]["source"], "gis_easement")
        self.assertEqual(corridors["water"]["source_name"], "Utility Easement A")
        self.assertEqual(corridors["water"]["orientation"], "horizontal")
        self.assertAlmostEqual(corridors["sanitary"]["axis_value"], 100.0, places=3)
        self.assertGreater(corridors["water"]["axis_value"], corridors["sanitary"]["axis_value"])


if __name__ == "__main__":
    unittest.main()
