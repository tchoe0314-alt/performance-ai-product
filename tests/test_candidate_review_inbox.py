import unittest

from backend.application.chat_workflows import decide_chat
from backend.application.project_workflows import review_project_candidates
from backend.planning.candidate_review_inbox import (
    apply_candidate_review_decision,
    build_candidate_review_inbox,
)


class _FakeStore:
    def __init__(self, record):
        self.record = record

    def get_project(self, *, user_id, project_id):
        if user_id == self.record["user_id"] and project_id == self.record["project_id"]:
            return self.record
        return None

    def save_project(self, **kwargs):
        self.record = {
            "project_id": kwargs["project_id"],
            "user_id": kwargs["user_id"],
            "name": kwargs["name"],
            "description": kwargs.get("description", ""),
            "session_id": kwargs.get("session_id"),
            "tags": kwargs.get("tags", []),
            "project_input": kwargs.get("project_input", {}),
            "latest_result": kwargs.get("latest_result", {}),
            "session_state": kwargs.get("session_state", {}),
            "metadata": kwargs.get("metadata", {}),
        }
        return self.record


def _meta():
    return {
        "map_feature_detection_report_v1": {
            "feature_candidates": [
                {
                    "candidate_id": "parcel-1",
                    "feature_type": "parcel_or_site_boundary",
                    "source_type": "official_gis",
                    "source_name": "county_parcels",
                    "source_url": "https://county.example/parcels",
                    "confidence": 0.88,
                    "acceptance_status": "pending",
                    "blockers": ["Parcel GIS is candidate evidence until reviewed."],
                },
                {
                    "candidate_id": "building-1",
                    "feature_type": "building_footprint",
                    "source_type": "official_gis",
                    "source_name": "county_buildings",
                    "source_url": "https://county.example/buildings",
                    "confidence": 0.9,
                    "acceptance_status": "pending",
                    "blockers": ["Building GIS is candidate evidence until reviewed."],
                },
            ],
        },
        "candidate_rule_report": {
            "candidate_rules": [
                {
                    "rule_id": "utility_cover",
                    "discipline": "utilities",
                    "topic": "Minimum utility cover",
                    "candidate_value": "3 ft",
                    "source_id": "city_manual",
                    "source_url": "https://city.example/standards",
                    "retrieved_date": "2026-06-01",
                    "confidence": "official_candidate",
                    "status": "candidate",
                    "acceptance_status": "candidate",
                }
            ]
        },
    }


def _record():
    return {
        "project_id": "project-1",
        "user_id": "u1",
        "name": "Candidate Project",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {},
        "latest_result": {"final_plan": {"meta": _meta()}},
        "session_state": {},
        "metadata": {},
    }


class CandidateReviewInboxTests(unittest.TestCase):
    def test_inbox_aggregates_map_and_standards_candidates_as_pending(self) -> None:
        inbox = build_candidate_review_inbox(_meta())

        self.assertEqual(inbox["version"], "candidate_review_inbox_v1")
        self.assertEqual(inbox["candidate_count"], 3)
        self.assertEqual(inbox["counts"]["pending"], 3)
        self.assertEqual(inbox["counts"]["accepted"], 0)
        self.assertEqual(inbox["counts"]["rejected"], 0)
        self.assertFalse(inbox["construction_release_allowed"])
        by_id = {item["candidate_id"]: item for item in inbox["candidates"]}
        self.assertEqual(by_id["parcel-1"]["candidate_type"], "parcel_site_boundary")
        self.assertEqual(by_id["std_utility_cover"]["candidate_type"], "standards")
        self.assertIn("review-required evidence only", inbox["truth_label"])

    def test_accept_reject_and_pending_preserve_audit_and_do_not_imply_construction_readiness(self) -> None:
        meta = _meta()
        accepted = apply_candidate_review_decision(meta, candidate_ids=["parcel-1"], action="accept", reviewer_id="u1")
        inbox = accepted["candidate_review_inbox_v1"]
        by_id = {item["candidate_id"]: item for item in inbox["candidates"]}

        self.assertEqual(by_id["parcel-1"]["status"], "accepted")
        self.assertEqual(by_id["parcel-1"]["accepted_as"], "project_draft_review_required_evidence")
        self.assertFalse(by_id["parcel-1"]["construction_release_allowed"])
        self.assertFalse(by_id["parcel-1"]["construction_readiness_implied"])
        self.assertEqual(accepted["accepted_drafts"][0]["status"], "draft_review_required")
        self.assertEqual(accepted["audit_trail"][0]["action"], "accept")

        rejected = apply_candidate_review_decision(
            accepted["updated_meta"],
            candidate_ids=["building-1"],
            action="reject",
            reviewer_id="u1",
            reason="Wrong building set.",
        )
        by_id = {item["candidate_id"]: item for item in rejected["candidate_review_inbox_v1"]["candidates"]}
        self.assertEqual(by_id["building-1"]["status"], "rejected")
        self.assertEqual(rejected["rejected_candidates"][0]["rejection_reason"], "Wrong building set.")
        self.assertEqual(rejected["audit_trail"][-1]["action"], "reject")
        self.assertEqual(by_id["std_utility_cover"]["status"], "pending")

    def test_project_workflow_persists_candidate_decisions(self) -> None:
        store = _FakeStore(_record())

        result = review_project_candidates(
            project_store=store,
            user_id="u1",
            project_id="project-1",
            candidate_ids=["building-1"],
            action="reject",
            reason="Not applicable.",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["candidate_review_inbox_v1"]["counts"]["rejected"], 1)
        saved_meta = store.record["latest_result"]["final_plan"]["meta"]
        self.assertEqual(saved_meta["candidate_review_rejected_v1"][0]["candidate_id"], "building-1")
        self.assertEqual(saved_meta["candidate_review_decisions_v1"][0]["action"], "reject")

    def test_chat_reports_pending_and_accepts_parcel_boundary_as_draft_evidence(self) -> None:
        store = _FakeStore(_record())

        report = decide_chat(
            {"message": "what candidates are pending?", "context": {"current_project": {"project_id": "project-1"}}},
            decide_chat_message=lambda payload: {"assistant_message": "fallback", "intent": "conversation", "run_mode": "none"},
            project_store=store,
            user_id="u1",
        )
        self.assertIn("3 pending", report["assistant_message"])
        self.assertEqual(report["response_metadata"]["action_taken"], "reported_candidate_review_inbox")

        accepted = decide_chat(
            {"message": "use the parcel boundary", "context": {"current_project": {"project_id": "project-1"}}},
            decide_chat_message=lambda payload: {"assistant_message": "fallback", "intent": "conversation", "run_mode": "none"},
            project_store=store,
            user_id="u1",
        )
        self.assertIn("draft/review-required evidence", accepted["assistant_message"])
        self.assertIn("does not make the project survey-true or ready for final reliance", accepted["assistant_message"])
        saved_meta = store.record["latest_result"]["final_plan"]["meta"]
        self.assertEqual(saved_meta["candidate_review_inbox_v1"]["counts"]["accepted"], 1)

    def test_chat_rejects_building_candidates_and_preserves_audit(self) -> None:
        store = _FakeStore(_record())

        rejected = decide_chat(
            {"message": "reject those buildings", "context": {"current_project": {"project_id": "project-1"}}},
            decide_chat_message=lambda payload: {"assistant_message": "fallback", "intent": "conversation", "run_mode": "none"},
            project_store=store,
            user_id="u1",
        )

        self.assertIn("rejected and preserved in the audit trail", rejected["assistant_message"])
        saved_meta = store.record["latest_result"]["final_plan"]["meta"]
        self.assertEqual(saved_meta["candidate_review_inbox_v1"]["counts"]["rejected"], 1)
        self.assertEqual(saved_meta["candidate_review_decisions_v1"][0]["candidate_id"], "building-1")


if __name__ == "__main__":
    unittest.main()
