import unittest

from backend.planning.source_confidence_map import build_source_confidence_map


class SourceConfidenceMapTests(unittest.TestCase):
    def test_does_not_call_survey_backed_without_verified_control(self) -> None:
        confidence_map = build_source_confidence_map(
            {
                "survey": {"source": "survey.csv", "point_count": 4},
                "survey_control_package": {
                    "version": "survey_control_package_v1",
                    "status": "blocked",
                    "control_verified": False,
                },
            }
        )

        labels = {entry["source_type"] for entry in confidence_map["entries"]}
        self.assertIn("survey-unverified", labels)
        self.assertNotIn("survey-backed", labels)
        survey_entry = next(entry for entry in confidence_map["entries"] if entry["source_type"] == "survey-unverified")
        self.assertTrue(survey_entry["needs_survey_control"])
        self.assertIn("verified survey/control", survey_entry["why_low_confidence"])

    def test_verified_control_can_mark_survey_backed(self) -> None:
        confidence_map = build_source_confidence_map(
            {
                "existing_conditions_summary": {
                    "survey": {"source": "survey.csv", "point_count": 4},
                },
                "survey_control_package": {
                    "version": "survey_control_package_v1",
                    "status": "ready",
                    "control_verified": True,
                    "production_usable": True,
                },
            }
        )

        survey_entry = next(entry for entry in confidence_map["entries"] if entry["label"] == "Survey / topo")
        self.assertEqual(survey_entry["source_type"], "survey-backed")
        self.assertEqual(survey_entry["confidence_band"], "higher")
        self.assertFalse(survey_entry["needs_survey_control"])

    def test_aggregates_candidates_user_drawn_stale_and_missing(self) -> None:
        confidence_map = build_source_confidence_map(
            {
                "candidate_review_inbox_v1": {
                    "candidates": [
                        {
                            "candidate_id": "parcel-1",
                            "candidate_type": "parcel_site_boundary",
                            "label": "Parcel boundary",
                            "source": "county GIS",
                            "status": "pending",
                            "blocker_review_reason": "Needs parcel review.",
                        }
                    ]
                },
                "reactive_update_report": {"stale_outputs": ["grading"]},
            },
            project_input={
                "manual_fields": {
                    "canonical_geometry_handoff_v1": [
                        {
                            "object_id": "obj-1",
                            "geometry_id": "geo-1",
                            "object_name": "Drawn basin",
                            "object_type": "basin",
                            "source": "manual_drawn",
                            "confidence": "user_drawn_review_required",
                            "engineering_status": "draft_review_required",
                            "source_ui_mode": "canvas_draw",
                            "blockers": [],
                        }
                    ]
                }
            },
        )

        labels = {entry["source_type"] for entry in confidence_map["entries"]}
        self.assertIn("GIS candidate", labels)
        self.assertIn("user-drawn", labels)
        self.assertIn("stale/dirty", labels)
        self.assertIn("missing", labels)
        self.assertGreaterEqual(confidence_map["summary"]["needs_survey_control_count"], 3)
        self.assertIn("Drawn basin", confidence_map["answer_cards"]["what_is_user_drawn"])
        self.assertIn("Stale output: grading", confidence_map["answer_cards"]["show_stale_or_missing_sources"])
        self.assertFalse(confidence_map["construction_release_allowed"])


if __name__ == "__main__":
    unittest.main()
