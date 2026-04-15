import unittest
from types import SimpleNamespace

from backend.planning.coordination_state import restore_coordination_state, snapshot_coordination_state


class CoordinationStateTest(unittest.TestCase):
    def test_restore_preserves_full_grading_payload(self) -> None:
        grading = {
            "success": True,
            "message": "Proposed grading surface built.",
            "proposed_surface": {"nrows": 4, "ncols": 4},
            "earthwork": {"cut_cf": 12.0, "fill_cf": 8.0, "net_cf": -4.0},
            "stats": {"proposed_contour_count": 6, "spot_grade_count": 4, "flow_arrow_count": 3},
            "surface_controls": {
                "has_primary_drainage_direction": True,
                "primary_low_point": {"x": 10.0, "y": 8.0, "z": 101.2},
            },
            "local_adjustments": [{"kind": "tie_in", "note": "keep"}],
        }
        project = SimpleNamespace(
            meta={
                "grading_summary": grading.copy(),
                "drainage_canonical": {"structures": [], "stats": {}, "export_validation": {}},
                "storm_pipe_summary": {"segments": []},
                "sanitary_summary": {},
                "utility_summary": {},
            }
        )
        manager = SimpleNamespace(
            latest_outputs={
                "grading": grading.copy(),
                "drainage": {"structures": [], "stats": {}, "export_validation": {}},
                "storm_pipe_summary": {"segments": []},
                "sanitary": {},
                "utilities": {},
            }
        )

        snap = snapshot_coordination_state(project, manager)

        project.meta["grading_summary"] = {"local_adjustments": []}
        manager.latest_outputs["grading"] = {"local_adjustments": []}

        restore_coordination_state(project, manager, snap)

        restored = project.meta["grading_summary"]
        self.assertTrue(restored.get("success"))
        self.assertTrue(restored.get("proposed_surface"))
        self.assertTrue(restored.get("earthwork"))
        self.assertTrue(restored.get("surface_controls"))
        self.assertEqual(restored.get("local_adjustments"), [{"kind": "tie_in", "note": "keep"}])


if __name__ == "__main__":
    unittest.main()
