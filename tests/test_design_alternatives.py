import unittest

from backend.application.chat_workflows import decide_chat
from backend.application.project_workflows import update_project_design_alternatives
from backend.planning.design_alternatives import (
    append_revised_design_alternative,
    build_design_alternatives,
    compare_design_alternatives,
    select_design_alternative,
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
        "candidate_review_accepted_drafts_v1": [
            {
                "candidate_id": "parcel-1",
                "candidate_type": "parcel_site_boundary",
                "label": "Accepted parcel boundary",
                "status": "draft_review_required",
            }
        ],
        "source_confidence_map_v1": {
            "entries": [
                {
                    "entry_id": "survey-control",
                    "label": "Verified survey/control",
                    "source_type": "survey-backed",
                    "confidence_band": "higher",
                    "status": "verified",
                }
            ]
        },
        "existing_conditions_package": {"metadata_only": False},
        "quantities": {
            "totals": {
                "paving_area_sf": 10000,
                "storm_pipe_lf": 800,
                "utility_length_lf": 500,
                "earthwork_cy": 1200,
            }
        },
        "cost_estimate": {"status": "review_only", "line_items": [{"item": "paving"}]},
    }


def _record():
    return {
        "project_id": "project-1",
        "user_id": "u1",
        "name": "Alternatives Project",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {},
        "latest_result": {"final_plan": {"meta": _meta()}},
        "session_state": {},
        "metadata": {},
    }


class DesignAlternativesTests(unittest.TestCase):
    def test_builds_review_required_design_alternatives_with_all_categories(self) -> None:
        alternatives = build_design_alternatives(_meta(), requested_count=3)

        self.assertEqual(alternatives["version"], "design_alternatives_v1")
        self.assertEqual(alternatives["alternative_count"], 3)
        self.assertFalse(alternatives["construction_release_allowed"])
        self.assertFalse(alternatives["construction_readiness_implied"])
        self.assertIn("review-required concepts", alternatives["truth_label"])
        first = alternatives["alternatives"][0]
        self.assertTrue(first["review_required"])
        self.assertEqual(first["input_support_state"], "supported_by_accepted_inputs")
        self.assertIn("parking_layouts", first["concepts"])
        self.assertIn("road_circulation_layouts", first["concepts"])
        self.assertIn("basin_placement", first["concepts"])
        self.assertIn("utility_routing", first["concepts"])
        self.assertIn("grading_drainage_concepts", first["concepts"])
        self.assertIn("site_organization", first["concepts"])
        self.assertTrue(first["cost_quantity_comparison"]["available"])
        self.assertIn("paving", first["cost_quantity_comparison"]["estimated_review_deltas"])

    def test_compare_select_and_revise_preserve_review_only_boundary(self) -> None:
        meta = _meta()
        alternatives = build_design_alternatives(meta, requested_count=3)
        meta["design_alternatives_v1"] = alternatives

        comparison = compare_design_alternatives(meta)
        self.assertEqual(len(comparison["rows"]), 3)
        self.assertFalse(comparison["construction_release_allowed"])

        selected = select_design_alternative(meta, option_number=2, action="choose", reviewer_id="u1")
        record = selected["design_alternatives_v1"]
        self.assertEqual(record["selected_alternative"]["option_number"], 2)
        self.assertEqual(record["selected_alternative"]["status"], "selected_review_required_concept")
        self.assertFalse(record["selected_alternative"]["construction_release_allowed"])
        self.assertIn("review-required concept", selected["truth_label"])

        revised = append_revised_design_alternative(selected["updated_meta"], basis_option_number=2, reviewer_id="u1")
        self.assertEqual(revised["design_alternatives_v1"]["alternative_count"], 4)
        self.assertEqual(revised["revised_alternative"]["status"], "review_required_concept")

    def test_project_workflow_persists_generate_and_choose(self) -> None:
        store = _FakeStore(_record())

        generated = update_project_design_alternatives(
            project_store=store,
            user_id="u1",
            project_id="project-1",
            action="generate",
            requested_count=3,
        )
        self.assertTrue(generated["success"])
        self.assertEqual(generated["design_alternatives_v1"]["alternative_count"], 3)

        chosen = update_project_design_alternatives(
            project_store=store,
            user_id="u1",
            project_id="project-1",
            action="choose",
            option_number=2,
            reason="Use option 2.",
        )
        saved_meta = store.record["latest_result"]["final_plan"]["meta"]
        self.assertEqual(chosen["design_alternatives_v1"]["selected_alternative"]["option_number"], 2)
        self.assertEqual(saved_meta["design_alternatives_v1"]["selected_alternative"]["option_number"], 2)
        self.assertEqual(saved_meta["design_alternative_decisions_v1"][-1]["action"], "choose")

    def test_chat_supports_show_compare_use_and_another_layout(self) -> None:
        store = _FakeStore(_record())

        shown = decide_chat(
            {"message": "show me 3 options", "context": {"current_project": {"project_id": "project-1"}}},
            decide_chat_message=lambda payload: {"assistant_message": "fallback", "intent": "conversation", "run_mode": "none"},
            project_store=store,
            user_id="u1",
        )
        self.assertIn("review-required design alternatives", shown["assistant_message"])
        self.assertEqual(shown["response_metadata"]["action_taken"], "generated_design_alternatives")
        self.assertEqual(shown["response_metadata"]["command_payload"]["design_alternatives_v1"]["alternative_count"], 3)

        compared = decide_chat(
            {"message": "compare these", "context": {"current_project": {"project_id": "project-1"}}},
            decide_chat_message=lambda payload: {"assistant_message": "fallback", "intent": "conversation", "run_mode": "none"},
            project_store=store,
            user_id="u1",
        )
        self.assertEqual(compared["response_metadata"]["action_taken"], "compared_design_alternatives")
        self.assertIn("design_alternatives_comparison_v1", compared["response_metadata"]["command_payload"])

        selected = decide_chat(
            {"message": "use option 2", "context": {"current_project": {"project_id": "project-1"}}},
            decide_chat_message=lambda payload: {"assistant_message": "fallback", "intent": "conversation", "run_mode": "none"},
            project_store=store,
            user_id="u1",
        )
        self.assertIn("draft review direction", selected["assistant_message"])
        self.assertIn("review-required concept", selected["assistant_message"])
        self.assertEqual(store.record["latest_result"]["final_plan"]["meta"]["design_alternatives_v1"]["selected_alternative"]["option_number"], 2)

        revised = decide_chat(
            {"message": "make another layout", "context": {"current_project": {"project_id": "project-1"}}},
            decide_chat_message=lambda payload: {"assistant_message": "fallback", "intent": "conversation", "run_mode": "none"},
            project_store=store,
            user_id="u1",
        )
        self.assertEqual(revised["response_metadata"]["action_taken"], "revised_design_alternative")
        self.assertEqual(store.record["latest_result"]["final_plan"]["meta"]["design_alternatives_v1"]["alternative_count"], 4)


if __name__ == "__main__":
    unittest.main()
