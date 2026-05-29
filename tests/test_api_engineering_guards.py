import unittest

from fastapi import HTTPException

from backend.api.app import (
    OrchestratePayload,
    QueueOrchestratePayload,
    SaveProjectPayload,
    UnitPriceBookCsvPayload,
    UnitPriceBookPayload,
    _final_plan_from_result,
    _model_to_dict,
    _queue_request_payload_with_project,
    _run_orchestration,
    normalize_unit_price_book,
    unit_price_book_from_csv,
    validate_unit_price_book,
)
from backend.planning.runtime import sanitize_plan


class ApiEngineeringGuardsTest(unittest.TestCase):
    def test_queue_request_payload_uses_nested_project_id_when_outer_missing(self) -> None:
        project_id, request_payload = _queue_request_payload_with_project(
            QueueOrchestratePayload(
                project_id=None,
                request=OrchestratePayload(
                    project_id="p_nested",
                    input_mode="assisted",
                    prompt_text="Design a mixed-use site.",
                ),
            )
        )
        self.assertEqual(project_id, "p_nested")
        self.assertEqual(request_payload["project_id"], "p_nested")

    def test_queue_request_payload_prefers_outer_project_id(self) -> None:
        project_id, request_payload = _queue_request_payload_with_project(
            QueueOrchestratePayload(
                project_id="p_outer",
                request=OrchestratePayload(
                    project_id="p_nested",
                    input_mode="assisted",
                    prompt_text="Design a mixed-use site.",
                ),
            )
        )
        self.assertEqual(project_id, "p_outer")
        self.assertEqual(request_payload["project_id"], "p_outer")

    def test_queue_request_payload_promotes_prompt_alias_to_prompt_text(self) -> None:
        project_id, request_payload = _queue_request_payload_with_project(
            QueueOrchestratePayload(
                project_id="p_outer",
                request=OrchestratePayload(
                    project_id="p_nested",
                    input_mode="assisted",
                    prompt="Design a mixed-use site from the prompt alias.",
                ),
            )
        )
        self.assertEqual(project_id, "p_outer")
        self.assertEqual(request_payload["project_id"], "p_outer")
        self.assertEqual(
            request_payload["prompt_text"],
            "Design a mixed-use site from the prompt alias.",
        )

    def test_queue_request_payload_preserves_full_design_mode(self) -> None:
        project_id, request_payload = _queue_request_payload_with_project(
            QueueOrchestratePayload(
                project_id="p_outer",
                request=OrchestratePayload(
                    project_id="p_nested",
                    full_design_mode=True,
                    input_mode="assisted",
                    prompt_text="Run the full staged design.",
                ),
            )
        )
        self.assertEqual(project_id, "p_outer")
        self.assertTrue(request_payload["full_design_mode"])

    def test_manual_orchestration_asks_for_clarification_when_prompt_is_underspecified(self) -> None:
        result = _run_orchestration(
            {
                "input_mode": "manual",
                "strict_mode": False,
                "prompt_text": "Design a fully coordinated civil site with grading, drainage, utilities, and a detention basin.",
                "manual_fields": {},
                "meta": {},
            }
        )
        self.assertFalse(result["success"])
        self.assertTrue((result.get("metadata") or {}).get("needs_clarification"))
        self.assertIn("need", result["message"].lower())

    def test_export_requires_stable_engineered_storm_and_drainage_state(self) -> None:
        with self.assertRaises(HTTPException) as exc_info:
            _final_plan_from_result(
                {
                    "final_plan": {
                        "project_name": "Unstable Plan",
                        "actions": [
                            {"task": "polyline", "layer": "PIPE", "points": [[0.0, 0.0], [10.0, 0.0]]},
                            {"task": "polyline", "layer": "BASIN_BOUNDARY", "points": [[0.0, 0.0], [0.0, 5.0], [5.0, 5.0]]},
                        ],
                        "meta": {
                            "deliverables": {"requested": ["storm_pipe_plan", "drainage_plan"], "produced": ["storm_pipe_plan", "drainage_plan"]},
                            "drainage": {"export_validation": {"ready": False, "reasons": ["primary_detention_missing"]}},
                            "storm_pipes": {
                                "graph_validation": {"valid": False},
                                "hydraulic_validation": {"valid": False},
                                "missing_data_segments": ["P-1"],
                            },
                        },
                    }
                }
            )
        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertIn("stable drainage/storm state", str(exc_info.exception.detail))

    def test_export_no_longer_falls_back_to_fake_drawable_geometry(self) -> None:
        with self.assertRaises(HTTPException) as exc_info:
            _final_plan_from_result({"final_plan": {"project_name": "No Actions", "actions": []}})
        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertIn("stable engineered plan actions", str(exc_info.exception.detail))

    def test_sanitize_plan_preserves_runtime_phase_checkpoint(self) -> None:
        plan = sanitize_plan(
            {
                "project_name": "Checkpoint Plan",
                "actions": [],
                "meta": {
                    "planner_workflow": "model_first",
                    "runtime_phase_checkpoint": {
                        "stage_name": "layout",
                        "status": "complete",
                        "message": "Layout checkpoint saved.",
                        "yielded": True,
                    },
                },
            }
        )
        self.assertEqual(
            plan["meta"]["runtime_phase_checkpoint"],
            {
                "stage_name": "layout",
                "status": "complete",
                "message": "Layout checkpoint saved.",
                "yielded": True,
            },
        )

    def test_sanitize_plan_preserves_canonical_sheet_metadata(self) -> None:
        plan = sanitize_plan(
            {
                "project_name": "Sheet Metadata Plan",
                "actions": [],
                "meta": {
                    "profiles": [{"name": "ROAD PROFILE 1", "alignment_owner": "ROAD ALIGNMENT 1"}],
                    "cross_sections": [{"name": "ROAD SECTION 1", "section_context": {"feature_types": ["travel_lane"]}}],
                    "alignments": [{"name": "ROAD ALIGNMENT 1", "points": [[0.0, 0.0], [10.0, 0.0]]}],
                    "sheet_registry": [{"layout_name": "SITE PLAN", "sheet_kind": "site_plan"}],
                    "export_audit": {"success": True},
                },
            }
        )
        self.assertTrue(plan["meta"]["profiles"])
        self.assertTrue(plan["meta"]["cross_sections"])
        self.assertTrue(plan["meta"]["alignments"])
        self.assertTrue(plan["meta"]["sheet_registry"])
        self.assertEqual(plan["meta"]["export_audit"], {"success": True})

    def test_save_project_payload_keeps_omitted_latest_result_as_none(self) -> None:
        payload = SaveProjectPayload(
            name="Demo Project",
            project_input={"prompt_text": "keep the staged checkpoint"},
        )
        data = _model_to_dict(payload)
        self.assertIn("latest_result", data)
        self.assertIsNone(data["latest_result"])

    def test_cost_price_book_api_helpers_validate_csv_and_json_payloads(self) -> None:
        current_user = {"user_id": "u1"}
        csv_response = unit_price_book_from_csv(
            UnitPriceBookCsvPayload(
                csv_text="metric,item,category,unit,unit_cost\npipe_length_ft,RCP storm pipe,storm,ft,125\n",
                source="company_2026_bid_book",
                location="Austin, TX",
                effective_date="2026-05-01",
                approved_by="Estimator",
                approval_date="2026-05-02",
            ),
            current_user=current_user,
        )
        validation_response = validate_unit_price_book(
            UnitPriceBookPayload(unit_price_book=csv_response["unit_price_book"]),
            current_user=current_user,
        )
        normalized_response = normalize_unit_price_book(
            UnitPriceBookPayload(unit_price_book={"unit_prices": {}}),
            current_user=current_user,
        )

        self.assertTrue(csv_response["validation"]["production_usable"])
        self.assertTrue(validation_response["success"])
        self.assertFalse(normalized_response["unit_price_book"]["production_usable"])


if __name__ == "__main__":
    unittest.main()
