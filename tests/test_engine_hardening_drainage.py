import unittest

import planner
from backend.planning.runtime import PlannerExecutionContext, RoutingDecision
from core.geometry_core import ProjectModel
from core.project_manager import ProjectManager
from engines.drainage_engine import DrainageEngine, HydraulicInputs
from engines.surface_engine import GridSurface


def _surface_to_southeast() -> GridSurface:
    return GridSurface(
        x_min=0.0,
        y_min=0.0,
        x_max=40.0,
        y_max=40.0,
        cell_size=10.0,
        ncols=5,
        nrows=5,
        values=[
            [104.0, 103.0, 102.0, 101.0, 100.0],
            [103.0, 102.0, 101.0, 100.0, 99.0],
            [102.0, 101.0, 100.0, 99.0, 98.0],
            [101.0, 100.0, 99.0, 98.0, 97.0],
            [100.0, 99.0, 98.0, 97.0, 96.0],
        ],
    )


def _surface_to_east_edge() -> GridSurface:
    return GridSurface(
        x_min=0.0,
        y_min=0.0,
        x_max=40.0,
        y_max=40.0,
        cell_size=10.0,
        ncols=5,
        nrows=5,
        values=[
            [104.0, 103.0, 102.0, 101.0, 100.0],
            [105.0, 104.0, 103.0, 102.0, 101.0],
            [106.0, 105.0, 104.0, 103.0, 102.0],
            [107.0, 106.0, 105.0, 104.0, 103.0],
            [108.0, 107.0, 106.0, 105.0, 104.0],
        ],
    )


class EngineHardeningDrainageTest(unittest.TestCase):
    def test_engine_reads_surface_and_connects_low_point_to_declared_basin(self) -> None:
        engine = DrainageEngine(_surface_to_southeast())
        engine.add_pond_target("POND-1", 40.0, 0.0, radius=8.0)

        summary = engine.design_network(
            mode=DrainageEngine.ASSISTED_MODE,
            hydraulic=HydraulicInputs(runoff_c=0.85, intensity_in_hr=4.0, min_pipe_slope=0.003),
            inlet_min_spacing=5.0,
            max_inlets=4,
            sample_step=1,
        )

        self.assertTrue(summary.success)
        self.assertTrue(summary.basin_records)
        self.assertTrue(summary.inlet_records)
        self.assertTrue(summary.pipe_runs)
        self.assertTrue(any(run.reached_target for run in summary.pipe_runs))
        self.assertTrue(any((record.inlet.estimated_flow_cfs or 0.0) > 0.0 for record in summary.inlet_records))
        self.assertIn("SURFACE_PATH_NEEDS_CONCEPT_PIPE", {issue.code for issue in summary.issues})

    def test_final_plan_meta_preserves_canonical_drainage_surface_records(self) -> None:
        payload = {
            "project_name": "Drainage Surface Records",
            "units": "ft",
            "mode": "site_plan",
            "project_type": "commercial_pad",
            "site_type": "commercial_pad",
            "terrain": "6% slope NW to SE",
            "lot": {"x": 0.0, "y": 0.0, "w": 180.0, "h": 140.0},
            "setback": 10.0,
            "street_edge": "bottom",
            "site_plan": {"building_width": 52.0, "building_depth": 38.0, "parking_count": 30},
        }

        plan = planner.build_plan(payload)
        drainage = plan.get("meta", {}).get("drainage", {})

        self.assertTrue(drainage.get("success"))
        self.assertEqual(drainage.get("source"), "drainage_engine")
        self.assertGreater(len(drainage.get("low_points", [])), 0)
        self.assertGreater(len(drainage.get("flow_paths", [])), 0)
        self.assertTrue(drainage.get("coordination"))
        self.assertTrue(drainage.get("surface_guidance", {}).get("surface_from_grading"))
        self.assertTrue(drainage.get("surface_guidance", {}).get("surface_source"))

    def test_user_basin_with_proposed_surface_blockage_emits_grading_blocker_context(self) -> None:
        project = ProjectModel(name="Blocked Drainage")
        manager = ProjectManager(project)
        project.meta["existing_surface"] = _surface_to_east_edge()
        project.meta["proposed_surface"] = _surface_to_southeast()
        project.meta["grading_summary"] = {
            "success": True,
            "grading_source_quality": "terrain",
            "grading_source_detail": "controlled fixture",
            "existing_surface": {"source_quality": "terrain"},
            "low_points": [{"x": 40.0, "y": 0.0, "z": 100.0, "local_basin_score": 1.0}],
            "flow_samples": [{"downhill_dx": 1.0, "downhill_dy": 0.0, "magnitude": 1.0}],
            "surface_controls": {
                "downhill_vector": {"dx": 1.0, "dy": 0.0},
                "control_counts": {"pad": 1, "parking": 1},
            },
        }
        parsed = {
            "project_name": "Blocked Drainage",
            "units": "ft",
            "mode": "site_plan",
            "lot": {"x": 0.0, "y": 0.0, "w": 40.0, "h": 40.0},
            "terrain": "controlled",
            "ponds": [{"name": "POND-1", "x": 36.0, "y": -4.0, "w": 8.0, "d": 8.0}],
            "site_plan": {"parking_count": 1},
        }
        ctx = PlannerExecutionContext(
            parsed=parsed,
            manager=manager,
            route=RoutingDecision(path="single_plan", reasons=[]),
        )

        planner._run_drainage_stage(ctx, {"runoff_c": 0.85, "intensity_in_hr": 4.0})
        drainage = project.meta.get("drainage_canonical", {})
        issues = drainage.get("issues", [])
        blocked = next((issue for issue in issues if issue.get("code") == "DRAINAGE_BLOCKED_BY_GRADING"), None)

        self.assertIsNotNone(blocked)
        context = blocked.get("context", {})
        self.assertEqual(context.get("reason"), "proposed_surface_needs_concept_pipe")
        self.assertTrue(context.get("source_point"))
        self.assertTrue(context.get("blocked_target"))
        self.assertTrue(context.get("suggested_fix_zone"))


if __name__ == "__main__":
    unittest.main()
