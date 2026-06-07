import unittest

from backend.planning.progress_timeline import build_progress_timeline


class ProgressTimelineTest(unittest.TestCase):
    def test_progress_timeline_reports_current_blocked_phase_and_export_blockers(self):
        latest_result = {
            "final_plan": {
                "actions": [{"label": "grading"}],
                "meta": {
                    "export_audit": {
                        "export_blocked": True,
                        "blocked_reasons": ["accepted_standards_missing"],
                    },
                    "deliverables": {
                        "requested": ["site_plan", "drainage_report"],
                        "produced": ["site_plan"],
                    },
                    "convergence_summary": {
                        "blocked_reasons": ["drainage_outfall_missing"],
                    },
                },
            }
        }

        timeline = build_progress_timeline(
            project_input={"manual_fields": {"lot": {"w": 300, "h": 200}}},
            latest_result=latest_result,
            context={"site_locked": False},
        )

        self.assertEqual(timeline["schema_version"], "progress_timeline_v1")
        self.assertEqual([step["id"] for step in timeline["steps"]], [
            "setup",
            "sources",
            "candidates",
            "design_objects",
            "systems",
            "qa",
            "review_package",
            "deliverables",
        ])
        self.assertEqual(timeline["current_step_id"], "setup")
        self.assertFalse(timeline["can_export"])
        self.assertIn("accepted_standards_missing", timeline["export_blockers"])
        self.assertIn("Missing deliverable: drainage_report", timeline["export_blockers"])
        self.assertIn("Setup", timeline["chat_summary"]["where_am_i"])

    def test_progress_timeline_ties_pending_candidates_to_candidate_phase(self):
        latest_result = {
            "final_plan": {
                "meta": {
                    "candidate_review_inbox_v1": {
                        "candidate_count": 2,
                        "counts": {"pending": 1, "accepted": 1, "rejected": 0},
                        "candidates": [],
                    }
                }
            }
        }

        timeline = build_progress_timeline(latest_result=latest_result)
        by_id = {step["id"]: step for step in timeline["steps"]}

        self.assertEqual(by_id["candidates"]["status"], "needs_review")
        self.assertIn("Review pending source candidates", by_id["candidates"]["blockers"][0])


if __name__ == "__main__":
    unittest.main()
