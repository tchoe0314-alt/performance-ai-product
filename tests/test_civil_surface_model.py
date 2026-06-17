import unittest

from backend.planning.civil_surface_model import (
    FeatureLineContract,
    FeatureLineVertex,
    SurfaceDatum,
    build_surface_contract,
    compare_existing_proposed_surfaces,
    feature_line_from_dict,
    validate_feature_line,
)
from engines.surface_engine import GridSurface, SurfaceEngine, SurveyPoint


class CivilSurfaceModelTests(unittest.TestCase):
    def test_surface_contract_keeps_review_only_boundaries_with_metadata(self) -> None:
        engine = SurfaceEngine(
            [
                SurveyPoint(0.0, 0.0, 100.0),
                SurveyPoint(100.0, 0.0, 101.0),
                SurveyPoint(0.0, 100.0, 102.0),
                SurveyPoint(100.0, 100.0, 103.0),
            ],
            control_verified=False,
        )
        tin = engine.build_tin()
        grid = tin.build_grid(cell_size=50.0)
        breakline = FeatureLineContract(
            feature_line_id="BL-1",
            type="breakline",
            vertices=[FeatureLineVertex(0.0, 50.0, 99.5), FeatureLineVertex(100.0, 50.0, 100.5)],
            source="survey.csv",
            source_confidence="survey-unverified",
            linked_surface_id="EG",
        )

        contract = build_surface_contract(
            surface_id="EG",
            surface_role="existing",
            source_type="survey-unverified",
            source_confidence="survey-unverified",
            control_status="unverified",
            datum=SurfaceDatum(horizontal="NAD83", vertical="NAVD88", coordinate_system="EPSG:2276", status="accepted"),
            grid_surface=grid,
            tin_surface=tin,
            feature_lines=[breakline],
            contours=[{"elevation": 100.0, "polyline": [[0.0, 0.0], [10.0, 0.0]]}],
            spot_elevations=[{"x": 0.0, "y": 0.0, "z": 100.0}],
        )

        self.assertEqual(contract["surface_id"], "EG")
        self.assertEqual(contract["source_type"], "survey-unverified")
        self.assertEqual(contract["datum_status"], "accepted")
        self.assertGreaterEqual(contract["points_metadata"]["count"], 4)
        self.assertGreater(contract["triangles_metadata"]["count"], 0)
        self.assertTrue(contract["grid_metadata"]["available"])
        self.assertIn("BL-1", contract["breaklines"])
        self.assertTrue(contract["contours"])
        self.assertTrue(contract["spot_elevations"])
        self.assertIsNotNone(contract["slope_range"]["max_pct"])
        self.assertTrue(contract["review_required"])
        self.assertFalse(contract["construction_release_allowed"])
        self.assertIn("unverified_control", contract["blockers"])

    def test_feature_line_contract_validates_breakline_elevations_and_linked_surface(self) -> None:
        feature_line = feature_line_from_dict(
            {
                "id": "curb-1",
                "type": "breakline",
                "vertices": [{"x": 0.0, "y": 0.0}, {"x": 40.0, "y": 0.0, "z": 101.0}],
                "source": "user-drawn",
                "confidence": "user_drawn_review_required",
            }
        )

        validation = validate_feature_line(feature_line)
        contract = feature_line.to_dict()

        self.assertFalse(validation["valid"])
        self.assertIn("breakline_requires_vertex_elevations", validation["blockers"])
        self.assertIn("feature_line_missing_linked_surface", validation["blockers"])
        self.assertIn("feature_line_source_needs_survey_control_review", validation["warnings"])
        self.assertTrue(contract["review_required"])
        self.assertFalse(contract["construction_release_allowed"])

    def test_missing_datum_control_and_stale_source_block_surface_reliance(self) -> None:
        surface = GridSurface(0.0, 0.0, 10.0, 10.0, 10.0, 2, 2, [[100.0, 100.2], [100.1, 100.3]])

        contract = build_surface_contract(
            surface_id="FG",
            surface_role="proposed",
            source_type="gis",
            source_confidence="inferred",
            control_status="missing",
            datum={"status": "missing"},
            grid_surface=surface,
            source_revision="rev-2",
            last_validated_source_revision="rev-1",
        )

        self.assertIn("missing_datum", contract["blockers"])
        self.assertIn("missing_control", contract["blockers"])
        self.assertIn("not_survey_control_backed", contract["blockers"])
        self.assertIn("stale_or_dirty_surface_source", contract["blockers"])
        self.assertTrue(contract["validation"]["missing_datum_or_control"])
        self.assertTrue(contract["validation"]["stale_or_dirty"])
        self.assertFalse(contract["construction_release_allowed"])

    def test_existing_proposed_comparison_exposes_cut_fill_review_hook(self) -> None:
        existing = GridSurface(0.0, 0.0, 10.0, 10.0, 10.0, 2, 2, [[100.0, 100.0], [100.0, 100.0]])
        proposed = GridSurface(0.0, 0.0, 10.0, 10.0, 10.0, 2, 2, [[101.0, 99.0], [100.0, 102.0]])

        comparison = compare_existing_proposed_surfaces(existing, proposed)

        self.assertEqual(comparison["existing_surface_id"], "EG")
        self.assertEqual(comparison["proposed_surface_id"], "FG")
        self.assertEqual(comparison["comparison"]["fill_cf"], 300.0)
        self.assertEqual(comparison["comparison"]["cut_cf"], 100.0)
        self.assertEqual(comparison["cut_fill_summary_hook"]["net_cf"], 200.0)
        self.assertIn("accepted_surface_review_required", comparison["cut_fill_summary_hook"]["blockers"])
        self.assertTrue(comparison["review_required"])
        self.assertFalse(comparison["construction_release_allowed"])


if __name__ == "__main__":
    unittest.main()
