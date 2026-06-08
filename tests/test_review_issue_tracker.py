import unittest

from backend.planning.review_issue_tracker import (
    apply_review_issue_update,
    build_review_issue_tracker,
    select_review_issues,
)


def _meta():
    return {
        "blockers": [
            {
                "area": "drainage",
                "field": "outfall",
                "reason": "Drainage outfall is missing.",
                "suggested_next_action": "Add or confirm a drainage outfall.",
            }
        ],
        "issues": [{"severity": "warning", "message": "Parking aisle QA needs review.", "code": "parking_aisle_qa"}],
        "smart_fix_recommendations_v1": {
            "version": "smart_fix_recommendations_v1",
            "recommendations": [
                {
                    "recommendation_id": "sf_drainage",
                    "label": "Fix drainage",
                    "reason": "Drainage fix pass is recommended.",
                    "category": "drainage",
                    "status": "ready",
                }
            ],
        },
        "engine_depth_dashboard_v1": {
            "blockers": [
                {
                    "engine_id": "grading",
                    "field": "surface",
                    "reason": "Grading surface depth needs accepted surface ids.",
                    "severity": "blocker",
                }
            ]
        },
        "export_package_report_v1": {
            "blocked_reasons": ["sheet_index_missing"],
            "blockers": [{"area": "exports", "field": "dxf_trace", "reason": "DXF trace is incomplete."}],
        },
        "candidate_review_inbox_v1": {
            "version": "candidate_review_inbox_v1",
            "candidates": [
                {
                    "candidate_id": "cand_parcel",
                    "candidate_type": "parcel_site_boundary",
                    "label": "Parcel boundary",
                    "status": "pending",
                    "blocker_review_reason": "Parcel must be reviewed before use.",
                }
            ],
        },
        "reviewer_comments": [
            {
                "id": "review_comment_1",
                "discipline": "water",
                "comment": "Water reviewer should check hydrant spacing source.",
                "severity": "review",
            }
        ],
    }


class ReviewIssueTrackerTests(unittest.TestCase):
    def test_builds_tracker_from_review_sources(self):
        tracker = build_review_issue_tracker({"meta": _meta()})

        self.assertEqual(tracker["version"], "review_issue_tracker_v1")
        self.assertGreaterEqual(tracker["open_count"], 7)
        disciplines = {item["discipline"] for item in tracker["issues"]}
        self.assertIn("drainage", disciplines)
        self.assertIn("grading", disciplines)
        self.assertIn("exports", disciplines)
        self.assertIn("existing_conditions", disciplines)
        self.assertFalse(tracker["field_use_allowed"])
        self.assertIn("Resolved only means", tracker["truth_label"])

    def test_status_updates_preserve_history_and_do_not_change_field_boundary(self):
        meta = _meta()
        tracker = build_review_issue_tracker({"meta": meta})
        drainage_issue = select_review_issues(tracker, discipline="drainage", status="open")[0]

        resolved = apply_review_issue_update(
            meta,
            action="resolve",
            issue_id=drainage_issue["issue_id"],
            actor="reviewer@example.com",
            note="Drainage evidence added.",
        )
        resolved_issue = select_review_issues(resolved["review_issue_tracker_v1"], drainage_issue["issue_id"])[0]
        self.assertEqual(resolved_issue["status"], "resolved")
        self.assertFalse(resolved_issue["field_use_allowed"])
        self.assertGreaterEqual(len(resolved_issue["history"]), 2)

        reopened = apply_review_issue_update(
            resolved["updated_meta"],
            action="reopen",
            issue_id=drainage_issue["issue_id"],
            actor="reviewer@example.com",
            note="Evidence needs another pass.",
        )
        reopened_issue = select_review_issues(reopened["review_issue_tracker_v1"], drainage_issue["issue_id"])[0]
        self.assertEqual(reopened_issue["status"], "reopened")

    def test_waiver_creates_review_required_record(self):
        meta = _meta()
        issue = select_review_issues(build_review_issue_tracker({"meta": meta}), discipline="exports", status="open")[0]

        waived = apply_review_issue_update(
            meta,
            action="waive",
            issue_id=issue["issue_id"],
            actor="reviewer@example.com",
            note="Accepted for review package tracking only.",
        )
        waived_issue = select_review_issues(waived["review_issue_tracker_v1"], issue["issue_id"])[0]

        self.assertEqual(waived_issue["status"], "waived_review_required")
        self.assertTrue(waived_issue["waiver_record"]["review_required"])
        self.assertFalse(waived_issue["waiver_record"]["field_use_allowed"])


if __name__ == "__main__":
    unittest.main()
