import unittest
from types import SimpleNamespace

from backend.planning.grading_support import build_existing_surface, canonical_grading_payload
from engines.surface_engine import Breakline, GridSurface, SurfaceEngine, SurveyPoint, compare_surfaces


def _normalize_vector(dx: float, dy: float) -> tuple[float, float]:
    mag = (dx * dx + dy * dy) ** 0.5
    if mag <= 1e-9:
        return 0.0, 0.0
    return dx / mag, dy / mag


def _flat_profile(_parsed):
    return {"downhill_dx": 1.0, "downhill_dy": -1.0, "slope_ratio": 0.02, "inferred": True}


class TinSurfaceEngineTests(unittest.TestCase):
    def test_tin_interpolates_triangle_plane_and_generates_artifacts(self) -> None:
        engine = SurfaceEngine(
            [
                SurveyPoint(0.0, 0.0, 100.0),
                SurveyPoint(100.0, 0.0, 110.0),
                SurveyPoint(0.0, 100.0, 120.0),
                SurveyPoint(100.0, 100.0, 130.0),
            ],
            control_verified=True,
            source_type="survey",
        )

        tin = engine.build_tin()
        artifact = engine.surface_artifact(tin=tin, contour_interval=5.0, spot_spacing=50.0, flow_step=50.0)

        self.assertGreaterEqual(len(tin.triangles), 2)
        self.assertAlmostEqual(tin.elevation_at(50.0, 50.0) or 0.0, 115.0, places=6)
        self.assertEqual(artifact["model"], "tin")
        self.assertEqual(artifact["source_type"], "survey-backed")
        self.assertTrue(artifact["control_verified"])
        self.assertTrue(artifact["contours"])
        self.assertTrue(artifact["spot_elevations"])
        self.assertTrue(artifact["slope_arrows"])
        self.assertTrue(artifact["flow_paths"])

    def test_breaklines_are_sampled_and_boundary_clips_tin(self) -> None:
        engine = SurfaceEngine(
            [
                SurveyPoint(0.0, 0.0, 100.0),
                SurveyPoint(100.0, 0.0, 100.0),
                SurveyPoint(0.0, 100.0, 100.0),
                SurveyPoint(100.0, 100.0, 100.0),
            ],
            breaklines=[Breakline(points=[(0.0, 50.0, 95.0), (100.0, 50.0, 95.0)], breakline_id="swale")],
            boundary=[(0.0, 0.0), (100.0, 0.0), (100.0, 75.0), (0.0, 75.0)],
        )

        tin = engine.build_tin()
        artifact = engine.surface_artifact(tin=tin, contour_interval=1.0, spot_spacing=25.0, flow_step=25.0)

        self.assertGreater(tin.metadata["point_count"], 4)
        self.assertTrue(tin.metadata["boundary_clipped"])
        self.assertTrue(any(triangle.confidence == "breakline_control" for triangle in tin.triangles))
        self.assertTrue(artifact["breaklines"])
        self.assertTrue(all(sum(point[1] for point in triangle["points"]) / 3.0 <= 75.0 for triangle in artifact["triangles"]))

    def test_surface_comparison_reports_cut_fill_cells(self) -> None:
        existing = GridSurface(0.0, 0.0, 10.0, 10.0, 10.0, 2, 2, [[100.0, 100.0], [100.0, 100.0]])
        proposed = GridSurface(0.0, 0.0, 10.0, 10.0, 10.0, 2, 2, [[101.0, 99.0], [100.0, 102.0]])

        comparison = compare_surfaces(existing, proposed)

        self.assertEqual(comparison["fill_cf"], 300.0)
        self.assertEqual(comparison["cut_cf"], 100.0)
        self.assertEqual(comparison["net_cf"], 200.0)
        self.assertEqual({cell["mode"] for cell in comparison["cells"]}, {"cut", "fill", "balanced"})

    def test_grading_payload_carries_tin_and_unverified_control_label(self) -> None:
        parsed = {
            "lot": {"x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0},
            "meta": {
                "site_inputs": {
                    "survey_points": [[0.0, 0.0, 100.0], [100.0, 0.0, 101.0], [0.0, 100.0, 102.0], [100.0, 100.0, 103.0]],
                    "survey_file": {"stored_filename": "topo.csv"},
                },
                "survey_control_package": {"control_verified": False},
            },
        }
        existing = build_existing_surface(parsed, infer_surface_profile=_flat_profile, normalize_vector=_normalize_vector)
        result = SimpleNamespace(
            proposed_surface=existing.copy(),
            checks=[],
            low_points=[],
            flow_samples=[],
            cut_volume=0.0,
            fill_volume=0.0,
            net_volume=0.0,
            success=True,
            message="ok",
            warnings=[],
        )

        payload = canonical_grading_payload(
            existing_surface=existing,
            result=result,
            derived_action_stats={"proposed_contour_count": 1, "spot_grade_count": 1, "flow_arrow_count": 1},
            normalize_vector=_normalize_vector,
        )

        self.assertEqual(payload["surface_model"]["model"], "tin")
        self.assertEqual(payload["surface_model"]["source_type"], "survey-unverified")
        self.assertFalse(payload["surface_model"]["control_verified"])
        self.assertIn("verified survey/control", payload["surface_model"]["confidence"]["not_survey_backed_reason"])


if __name__ == "__main__":
    unittest.main()
