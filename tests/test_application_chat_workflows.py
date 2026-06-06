import unittest

from backend.application.chat_workflows import decide_chat
from parsers.chat_intent_parser import decide_chat_message


def _record(project_id="project_123"):
    return {
        "project_id": project_id,
        "name": "Saved Project",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {
            "project_type": "mixed_use",
            "manual_fields": {
                "lot": {"w": 500, "h": 400},
                "site_plan": {"building_count": 1, "parking_count": 20},
            },
        },
        "latest_result": {
            "success": True,
            "final_plan": {
                "meta": {
                    "canonical_revision": "rev-1",
                    "drainage_canonical": {
                        "basins": [{"id": "BASIN-1", "label": "Detention basin"}]
                    },
                    "convergence_summary": {},
                }
            },
        },
        "session_state": {},
        "metadata": {},
    }


def _handoff(object_id="drawn-1", geometry_id="geom-1", *, valid=True, blockers=None):
    return {
        "schema_version": "canonical_geometry_handoff_v1",
        "object_id": object_id,
        "geometry_id": geometry_id,
        "object_name": "Drawn polygon",
        "object_type": "custom",
        "geometry_type": "polygon",
        "vertices": [
            {"id": f"{geometry_id}-v-1", "x": 0.0, "y": 0.0, "units": "ft"},
            {"id": f"{geometry_id}-v-2", "x": 80.0, "y": 0.0, "units": "ft"},
            {"id": f"{geometry_id}-v-3", "x": 80.0, "y": 60.0, "units": "ft"},
            {"id": f"{geometry_id}-v-close", "x": 0.0, "y": 0.0, "units": "ft"},
        ],
        "units": "ft",
        "coordinate_system": "site_local_ft",
        "source": "manual_drawn",
        "confidence": "user_drawn_review_required",
        "engineering_status": "draft_review_required",
        "metrics": {"area_sf": 4800.0, "width_ft": 80.0, "depth_ft": 60.0},
        "source_ui_mode": "canvas_draw",
        "valid": valid,
        "blockers": list(blockers or []),
    }


def _record_with_handoffs(handoffs):
    record = _record()
    manual_fields = record["project_input"]["manual_fields"]
    manual_fields["canonical_geometry_handoff_v1"] = list(handoffs)
    manual_fields["site_objects"] = [
        {
            "id": item["object_id"],
            "name": item["object_name"],
            "type": "custom",
            "source": "manual_drawn",
            "canonical_geometry_handoff_v1": item,
        }
        for item in handoffs
    ]
    return record


class RecordingProjectStore:
    def __init__(self, record=None):
        self.record = record or _record()
        self.saved = []

    def get_project(self, *, user_id, project_id):
        return self.record

    def save_project(self, **kwargs):
        self.saved.append(kwargs)
        self.record = {
            **self.record,
            "project_input": kwargs["project_input"],
            "latest_result": kwargs["latest_result"],
        }
        return self.record


class ApplicationChatWorkflowsTest(unittest.TestCase):
    def test_decide_chat_requires_message(self):
        with self.assertRaises(ValueError):
            decide_chat({}, decide_chat_message=lambda payload: payload)

    def test_decide_chat_delegates_to_parser(self):
        called = {}

        def fake_decider(payload):
            called["payload"] = dict(payload)
            return {"success": True, "intent": "conversation"}

        result = decide_chat(
            {"message": "hello", "context": {"strategy_mode": "assisted"}},
            decide_chat_message=fake_decider,
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(called["payload"]["message"], "hello")

    def test_decide_chat_hydrates_canonical_project_context(self):
        called = {}

        class FakeProjectStore:
            def get_project(self, *, user_id, project_id):
                return {
                    "project_id": project_id,
                    "name": "Saved Project",
                    "description": "",
                    "session_id": None,
                    "tags": [],
                    "project_input": {"project_type": "mixed_use"},
                    "latest_result": {
                        "success": True,
                        "final_plan": {
                            "meta": {
                                "convergence_summary": {
                                    "blocked_reasons": ["storm_graph_invalid"],
                                },
                                "deliverables": {"produced": ["preview"]},
                            }
                        },
                    },
                    "session_state": {},
                    "metadata": {},
                }

            def save_project(self, **_kwargs):
                return {}

        def fake_decider(payload):
            called["context"] = dict(payload["context"])
            return {"success": True, "intent": "conversation"}

        result = decide_chat(
            {
                "message": "why is storm blocked",
                "context": {
                    "current_project": {"project_id": "project_123", "name": "Stale Project"},
                    "convergence_summary": {},
                },
            },
            decide_chat_message=fake_decider,
            project_store=FakeProjectStore(),
            user_id="user_1",
        )
        self.assertEqual(result["intent"], "conversation")
        self.assertTrue(called["context"]["has_plan"])
        self.assertEqual(called["context"]["current_project"]["name"], "Saved Project")
        self.assertEqual(called["context"]["convergence_summary"]["blocked_reasons"], ["storm_graph_invalid"])

    def test_decide_chat_hydrates_export_audit_blockers(self):
        called = {}

        class FakeProjectStore:
            def get_project(self, *, user_id, project_id):
                return {
                    "project_id": project_id,
                    "name": "Saved Project",
                    "description": "",
                    "session_id": None,
                    "tags": [],
                    "project_input": {},
                    "latest_result": {
                        "success": True,
                        "final_plan": {
                            "meta": {
                                "export_audit": {
                                    "export_blocked": True,
                                    "blocked_reasons": ["canonical_id_traceability_missing"],
                                },
                            }
                        },
                    },
                    "session_state": {},
                    "metadata": {},
                }

            def save_project(self, **_kwargs):
                return {}

        def fake_decider(payload):
            called["context"] = dict(payload["context"])
            return {"success": True, "intent": "conversation"}

        decide_chat(
            {
                "message": "what do I need before export",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=fake_decider,
            project_store=FakeProjectStore(),
            user_id="user_1",
        )
        self.assertEqual(called["context"]["current_export_audit"]["blocked_reasons"], ["canonical_id_traceability_missing"])
        self.assertIn("canonical_id_traceability_missing", called["context"]["convergence_summary"]["blocked_reasons"])
        self.assertIn("export", called["context"]["convergence_summary"]["blocked_exports"])

    def test_site_update_command_persists_canonical_state(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "make the site 14 acres",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "updated_canonical_site_state")
        self.assertEqual(result["response_metadata"]["intent"], "site_update")
        self.assertTrue(store.saved)
        saved_input = store.saved[-1]["project_input"]
        saved_meta = store.saved[-1]["latest_result"]["final_plan"]["meta"]
        self.assertEqual(saved_input["site_area_acres"], 14.0)
        self.assertEqual(saved_meta["canonical_site_state"]["site_area_acres"], 14.0)
        self.assertEqual(saved_meta["canonical_site_state"]["ready_language"], "ready_for_engineer_review")
        self.assertIn("engineer-review-required", result["assistant_message"])
        self.assertNotIn("construction-approved", result["assistant_message"])

    def test_object_creation_command_creates_draft_geometry_and_truthful_action(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "add a 100 by 60 building",
                "context": {"strategy_mode": "assisted", "current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "created_draft_geometry")
        self.assertEqual(result["response_metadata"]["intent"], "object_or_layout_command")
        self.assertEqual(result["response_metadata"]["command_payload"]["draft_id"], "draft-building-1")
        self.assertIn("draft", result["assistant_message"])
        drafts = store.saved[-1]["latest_result"]["final_plan"]["meta"]["canonical_draft_geometry"]
        self.assertEqual(drafts[0]["object_type"], "building")
        self.assertEqual(drafts[0]["width"], 100.0)
        self.assertEqual(drafts[0]["depth"], 60.0)
        self.assertTrue(drafts[0]["engineer_review_required"])
        self.assertFalse(drafts[0]["construction_release_allowed"])

    def test_command_parsed_but_blocks_when_canonical_edit_support_missing(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "move the road north",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertEqual(result["action_taken"], "blocked_missing_canonical_edit_support")
        self.assertIn("Canonical road update edits are not supported", result["action_blocked_reason"])
        self.assertEqual(store.saved, [])

    def test_strict_no_assumption_mode_blocks_executor_assumptions(self):
        store = RecordingProjectStore()

        def fake_decider(_payload):
            return {
                "success": True,
                "intent": "design",
                "assistant_message": "Prepared.",
                "run_mode": "run",
                "design_prompt": "add a building",
                "needs_clarification": False,
                "reason": "test",
                "confidence": 1.0,
                "control_overrides": {},
                "response_metadata": {
                    "intent": "object_or_layout_command",
                    "required_missing_inputs": [],
                    "action_taken": "prepared_canonical_edit",
                    "action_blocked_reason": "",
                    "affected_systems": ["layout"],
                    "assumptions": ["draft building location"],
                    "next_best_action": "",
                    "command_payload": {
                        "object_type": "building",
                        "operation": "create",
                        "width": 100,
                        "depth": 60,
                        "assumption_policy": "strict",
                    },
                },
            }

        result = decide_chat(
            {
                "message": "add a 100 by 60 building",
                "context": {"strategy_mode": "user", "current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=fake_decider,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["action_taken"], "asked_clarifying_question")
        self.assertIn("Strict/no-assumption mode", result["action_blocked_reason"])
        self.assertEqual(result["assumptions"], [])
        self.assertEqual(store.saved, [])

    def test_assisted_mode_records_assumptions_on_draft_geometry(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "add a 100 by 60 building",
                "context": {"strategy_mode": "assisted", "current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "created_draft_geometry")
        self.assertTrue(result["assumptions"])
        self.assertIn("planner-selected", " ".join(result["assumptions"]).replace(" ", "-").lower())

    def test_drainage_command_queues_workflow_when_evidence_exists(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "generate drainage",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "queued_engineering_workflow")
        self.assertEqual(result["response_metadata"]["command_payload"]["workflow"], "drainage")
        workflows = store.saved[-1]["latest_result"]["final_plan"]["meta"]["chat_command_workflows"]
        self.assertEqual(workflows[-1]["workflow"], "drainage")
        self.assertEqual(workflows[-1]["ready_language"], "ready_for_engineer_review")

    def test_export_readiness_uses_real_audit_blockers_without_owning_export(self):
        store = RecordingProjectStore(
            _record()
            | {
                "latest_result": {
                    "success": True,
                    "final_plan": {
                        "meta": {
                            "export_audit": {
                                "export_blocked": True,
                                "blocked_reasons": ["canonical_id_traceability_missing"],
                            },
                        }
                    },
                }
            }
        )

        result = decide_chat(
            {
                "message": "what do I need before export",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertEqual(result["response_metadata"]["intent"], "export_readiness")
        self.assertIn("canonical_id_traceability_missing", result["assistant_message"])
        self.assertEqual(store.saved, [])

    def test_drawn_geometry_reference_classifies_basin_draft(self):
        store = RecordingProjectStore(_record_with_handoffs([_handoff("drawn-basin", "geom-basin")]))

        result = decide_chat(
            {
                "message": "make this a basin",
                "context": {
                    "current_project": {"project_id": "project_123"},
                    "selected_object_ids": ["drawn-basin"],
                    "selected_geometry_ids": ["geom-basin"],
                },
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        metadata = result["response_metadata"]
        self.assertEqual(result["action_taken"], "classified_drawn_geometry")
        self.assertEqual(metadata["outcome"], "draft_canonical_classification_created")
        self.assertTrue(metadata["state_changed"])
        self.assertEqual(metadata["referenced_object_ids"], ["drawn-basin"])
        self.assertEqual(metadata["referenced_geometry_ids"], ["geom-basin"])
        self.assertEqual(result["run_mode"], "none")
        saved_meta = store.saved[-1]["latest_result"]["final_plan"]["meta"]
        update = saved_meta["canonical_geometry_classification_updates"][0]
        self.assertEqual(update["object_type"], "basin")
        self.assertEqual(update["source"], "manual_drawn")
        self.assertEqual(update["confidence"], "user_drawn_review_required")
        self.assertEqual(update["engineering_status"], "draft_review_required")
        self.assertFalse(update["construction_release_allowed"])
        self.assertIn("did not run engineering generation", result["assistant_message"])

    def test_drawn_geometry_reference_classifies_parking_draft(self):
        store = RecordingProjectStore(_record_with_handoffs([_handoff("drawn-parking", "geom-parking")]))

        result = decide_chat(
            {
                "message": "make that polygon a parking lot",
                "context": {
                    "current_project": {"project_id": "project_123"},
                    "selected_object_ids": ["drawn-parking"],
                    "selected_geometry_ids": ["geom-parking"],
                },
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        metadata = result["response_metadata"]
        self.assertEqual(result["action_taken"], "classified_drawn_geometry")
        self.assertTrue(metadata["state_changed"])
        update = store.saved[-1]["latest_result"]["final_plan"]["meta"]["canonical_geometry_classification_updates"][0]
        self.assertEqual(update["object_type"], "parking")
        self.assertEqual(update["source"], "manual_drawn")
        self.assertEqual(update["confidence"], "user_drawn_review_required")
        self.assertEqual(update["engineering_status"], "draft_review_required")

    def test_ambiguous_this_asks_for_selected_geometry(self):
        store = RecordingProjectStore(_record_with_handoffs([_handoff("drawn-1", "geom-1")]))

        result = decide_chat(
            {
                "message": "make this a basin",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        metadata = result["response_metadata"]
        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["action_taken"], "asked_targeted_geometry_selection_question")
        self.assertFalse(metadata["state_changed"])
        self.assertEqual(metadata["outcome"], "needs_geometry_selection")
        self.assertIn("Which drawn geometry", result["assistant_message"])
        self.assertEqual(store.saved, [])

    def test_invalid_referenced_geometry_blocks_with_exact_blocker(self):
        store = RecordingProjectStore(
            _record_with_handoffs([
                _handoff("drawn-invalid", "geom-invalid", valid=False, blockers=["vertices must include at least 4 points for polygon"])
            ])
        )

        result = decide_chat(
            {
                "message": "make this a basin",
                "context": {
                    "current_project": {"project_id": "project_123"},
                    "selected_object_ids": ["drawn-invalid"],
                    "selected_geometry_ids": ["geom-invalid"],
                },
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        metadata = result["response_metadata"]
        self.assertEqual(result["action_taken"], "blocked_invalid_geometry_handoff")
        self.assertFalse(metadata["state_changed"])
        self.assertEqual(metadata["outcome"], "invalid_geometry_handoff_blocked")
        self.assertIn("vertices must include at least 4 points for polygon", result["action_blocked_reason"])
        self.assertEqual(metadata["referenced_object_ids"], ["drawn-invalid"])
        self.assertEqual(metadata["referenced_geometry_ids"], ["geom-invalid"])
        self.assertEqual(store.saved, [])

    def test_unsupported_road_move_blocks_truthfully_and_does_not_change_state(self):
        store = RecordingProjectStore(_record_with_handoffs([_handoff("road-shape", "road-geom")]))

        result = decide_chat(
            {
                "message": "move the road north",
                "context": {
                    "current_project": {"project_id": "project_123"},
                    "selected_object_ids": ["road-shape"],
                    "selected_geometry_ids": ["road-geom"],
                },
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        metadata = result["response_metadata"]
        self.assertEqual(result["action_taken"], "blocked_missing_canonical_edit_support")
        self.assertEqual(metadata["outcome"], "unsupported_canonical_edit_blocked")
        self.assertFalse(metadata["state_changed"])
        self.assertIn("Canonical road update edits are not supported", result["action_blocked_reason"])
        self.assertEqual(store.saved, [])


if __name__ == "__main__":
    unittest.main()
