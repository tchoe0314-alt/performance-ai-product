import unittest

from backend.planning.runtime import collect_plan_stats
from core.project_manager import ConflictRecord, ProjectManager
from engines.quantity_engine import compute_plan_quantities


class Phase1StateContractTests(unittest.TestCase):
    def test_manager_export_is_structured(self) -> None:
        manager = ProjectManager()
        manager.set_metric("layout_building_area_sf", 1250.0, units="sf", category="layout")
        manager.set_metric("utility_total_length_ft", 80.0, units="ft", category="utilities")
        manager.add_conflict(ConflictRecord(code="TEST_WARNING", message="warning", category="qa"))
        manager.mark_system_dirty("grading", reason="Test dirtied grading.")

        export = manager.export_metrics()

        self.assertIn("metrics", export)
        self.assertIn("conflict_counts", export)
        self.assertIn("dependency_counts", export)
        self.assertIn("system_counts", export)
        self.assertIn("dirty_state", export)
        self.assertEqual(export["metrics"]["layout_building_area_sf"]["value"], 1250.0)
        self.assertEqual(export["conflict_counts"]["warning"], 1)
        self.assertEqual(export["dirty_state"]["grading"]["state"], "dirty")

    def test_quantities_prefer_manager_metrics_when_actions_are_sparse(self) -> None:
        manager = ProjectManager()
        manager.set_metric("parking_count", 24, category="layout")
        manager.set_metric("layout_building_area_sf", 1632.0, units="sf", category="layout")
        manager.set_metric("layout_parking_area_sf", 7800.0, units="sf", category="layout")
        manager.set_metric("layout_road_area_sf", 2100.0, units="sf", category="layout")
        manager.set_metric("layout_impervious_area_sf", 11532.0, units="sf", category="layout")
        manager.set_metric("storm_pipe_length_ft", 140.0, units="ft", category="pipes")
        manager.set_metric("utility_total_length_ft", 95.0, units="ft", category="utilities")

        plan = {
            "project_name": "Phase 1 Contract",
            "units": "ft",
            "actions": [],
            "meta": {"manager_export": manager.export_metrics()},
        }

        quantities = compute_plan_quantities(plan)
        stats = collect_plan_stats({
            **plan,
            "meta": {
                **plan["meta"],
                "quantities": {"totals": quantities.totals},
            },
        })

        self.assertEqual(quantities.totals["estimated_parking_stalls"], 24)
        self.assertEqual(quantities.totals["building_area_sf"], 1632.0)
        self.assertEqual(quantities.totals["pipe_length_ft"], 140.0)
        self.assertEqual(quantities.totals["utility_length_ft"], 95.0)
        self.assertEqual(stats["estimated_building_area_sf"], 1632.0)
        self.assertEqual(stats["estimated_parking_area_sf"], 7800.0)
        self.assertEqual(stats["estimated_road_area_sf"], 2100.0)
        self.assertEqual(stats["estimated_pipe_length_ft"], 140.0)
        self.assertEqual(stats["estimated_utility_length_ft"], 95.0)
        self.assertEqual(stats["estimated_impervious_area_sf"], 11532.0)


if __name__ == "__main__":
    unittest.main()
