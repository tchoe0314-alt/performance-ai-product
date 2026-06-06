import unittest
from unittest.mock import patch

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
    def assertTaxonomyMetadata(self, result, outcome):
        metadata = result["response_metadata"]
        self.assertEqual(metadata["outcome"], outcome)
        self.assertIn("confidence", metadata)
        self.assertIn("state_changed", metadata)
        self.assertIn("next_best_action", metadata)
        self.assertIn("understood_goal", metadata)
        self.assertIn("completed_actions", metadata)
        self.assertIn("blocked_actions", metadata)
        self.assertIn("exact_missing_inputs", metadata)
        self.assertIn("suggested_user_replies", metadata)
        self.assertIn("can_execute_now", metadata)
        if outcome == "unsupported_or_not_understood":
            self.assertTrue(metadata["unsupported_reason"])
        if outcome == "understood_but_blocked":
            self.assertTrue(metadata["blocker"])

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
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertTrue(result["response_metadata"]["state_changed"])
        self.assertEqual(result["response_metadata"]["intent"], "site_update")
        self.assertTrue(store.saved)
        saved_input = store.saved[-1]["project_input"]
        saved_meta = store.saved[-1]["latest_result"]["final_plan"]["meta"]
        self.assertEqual(saved_input["site_area_acres"], 14.0)
        self.assertEqual(saved_meta["canonical_site_state"]["site_area_acres"], 14.0)
        self.assertEqual(saved_meta["canonical_site_state"]["ready_language"], "ready_for_engineer_review")
        self.assertIn("engineer-review-required", result["assistant_message"])
        self.assertNotIn("construction-approved", result["assistant_message"])

    def test_site_setup_dimensions_and_address_persist_without_planner_queue(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "make the site size 1000x1000 and the address is 20525 Margo St gretna ne",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["intent"], "conversation")
        self.assertEqual(result["run_mode"], "none")
        self.assertEqual(result["action_taken"], "updated_site_dimensions_and_location_evidence")
        self.assertTaxonomyMetadata(result, "understood_and_answered")
        self.assertTrue(result["response_metadata"]["state_changed"])
        self.assertEqual(result["response_metadata"]["intent"], "site_setup")
        self.assertEqual(result["response_metadata"]["completed_actions"], ["updated_site_dimensions_and_location_evidence"])
        self.assertEqual(result["response_metadata"]["blocked_actions"], [])
        self.assertFalse(result["response_metadata"]["can_execute_now"])
        self.assertNotIn("land use", result["assistant_message"])
        self.assertNotIn("building", result["assistant_message"].lower())
        self.assertIn("Do you want to lock this 1000 ft x 1000 ft site boundary", result["assistant_message"])
        saved_input = store.saved[-1]["project_input"]
        saved_meta = store.saved[-1]["latest_result"]["final_plan"]["meta"]
        self.assertEqual(saved_input["manual_fields"]["lot"]["w"], 1000.0)
        self.assertEqual(saved_input["manual_fields"]["lot"]["h"], 1000.0)
        self.assertEqual(saved_input["meta"]["site_inputs"]["address"], "20525 Margo St, Gretna, NE")
        self.assertEqual(saved_meta["location_context"]["address"], "20525 Margo St, Gretna, NE")
        self.assertIn("not a site boundary", saved_meta["location_context"]["truth_label"])
        self.assertNotIn("chat_command_workflows", saved_meta)

    def test_site_setup_dimensions_only_changes_site_state(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "set site to 500 by 800",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "updated_site_dimensions_and_location_evidence")
        self.assertTaxonomyMetadata(result, "understood_and_answered")
        saved_lot = store.saved[-1]["project_input"]["manual_fields"]["lot"]
        self.assertEqual(saved_lot["w"], 500.0)
        self.assertEqual(saved_lot["h"], 800.0)

    def test_site_setup_address_only_changes_location_evidence(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "address is 123 Main St",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "updated_site_dimensions_and_location_evidence")
        self.assertTaxonomyMetadata(result, "understood_and_answered")
        self.assertTrue(result["needs_clarification"])
        saved_meta = store.saved[-1]["latest_result"]["final_plan"]["meta"]
        self.assertEqual(saved_meta["location_context"]["address"], "123 Main St")
        self.assertIn("not a trusted site boundary", result["assistant_message"])

    def test_site_setup_geocode_failure_does_not_change_state(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {
                "message": "address is 123 Main St",
                "context": {"current_project": {"project_id": "project_123"}, "address_status": "geocode_failed"},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "blocked_site_setup_geocode_failed")
        self.assertTaxonomyMetadata(result, "understood_but_blocked")
        self.assertFalse(result["response_metadata"]["state_changed"])
        self.assertEqual(store.saved, [])

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
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertTrue(result["response_metadata"]["state_changed"])
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
        self.assertTaxonomyMetadata(result, "understood_but_blocked")
        self.assertFalse(result["response_metadata"]["state_changed"])
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
        self.assertTaxonomyMetadata(result, "understood_needs_more_info")
        self.assertFalse(result["response_metadata"]["state_changed"])
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
        self.assertTaxonomyMetadata(result, "understood_and_executed")
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
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertTrue(result["response_metadata"]["state_changed"])
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
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertFalse(result["response_metadata"]["state_changed"])
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
        self.assertTaxonomyMetadata(result, "understood_and_executed")
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
        self.assertTaxonomyMetadata(result, "understood_and_executed")
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
        self.assertTaxonomyMetadata(result, "understood_needs_more_info")
        self.assertFalse(metadata["state_changed"])
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
        self.assertTaxonomyMetadata(result, "understood_but_blocked")
        self.assertFalse(metadata["state_changed"])
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
        self.assertTaxonomyMetadata(result, "understood_but_blocked")
        self.assertFalse(metadata["state_changed"])
        self.assertIn("Canonical road update edits are not supported", result["action_blocked_reason"])
        self.assertEqual(store.saved, [])

    def test_unsupported_random_command_returns_unsupported_taxonomy(self):
        result = decide_chat(
            {"message": "purple banana orbit sandwich", "context": {}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "unsupported_or_not_understood")
        self.assertTaxonomyMetadata(result, "unsupported_or_not_understood")
        self.assertIn("does not match a supported Civora chat command", result["response_metadata"]["unsupported_reason"])

    def test_natural_language_pond_low_spot_creates_draft_geometry(self):
        store = RecordingProjectStore(_record())

        with patch("parsers.chat_intent_parser._load_chat_client", side_effect=RuntimeError("AI disabled")):
            result = decide_chat(
                {
                    "message": "put that pond in the low spot",
                    "context": {"current_project": {"project_id": "project_123"}},
                },
                decide_chat_message=decide_chat_message,
                project_store=store,
                user_id="user_1",
            )

        self.assertEqual(result["action_taken"], "created_draft_geometry")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        planning = result["response_metadata"]["action_planning"]
        self.assertEqual(planning["selected_action_id"], "place_basin")
        drafts = store.saved[-1]["latest_result"]["final_plan"]["meta"]["canonical_draft_geometry"]
        self.assertEqual(drafts[-1]["object_type"], "basin")
        self.assertEqual(drafts[-1]["location_hint"], "low_corner")
        self.assertTrue(drafts[-1]["engineer_review_required"])

    def test_natural_language_polygon_parking_asks_for_selection(self):
        store = RecordingProjectStore(_record_with_handoffs([_handoff()]))

        with patch("parsers.chat_intent_parser._load_chat_client", side_effect=RuntimeError("AI disabled")):
            result = decide_chat(
                {
                    "message": "turn this polygon into parking",
                    "context": {"current_project": {"project_id": "project_123"}},
                },
                decide_chat_message=decide_chat_message,
                project_store=store,
                user_id="user_1",
            )

        self.assertEqual(result["action_taken"], "asked_targeted_geometry_selection_question")
        self.assertTaxonomyMetadata(result, "understood_needs_more_info")
        planning = result["response_metadata"]["action_planning"]
        self.assertEqual(planning["selected_action_id"], "classify_geometry_as_parking")
        self.assertIn("selected drawn geometry", planning["missing_inputs"])

    def test_natural_language_fix_drainage_queues_existing_workflow(self):
        store = RecordingProjectStore(_record())

        with patch("parsers.chat_intent_parser._load_chat_client", side_effect=RuntimeError("AI disabled")):
            result = decide_chat(
                {
                    "message": "fix the drainage",
                    "context": {"current_project": {"project_id": "project_123"}},
                },
                decide_chat_message=decide_chat_message,
                project_store=store,
                user_id="user_1",
            )

        self.assertEqual(result["action_taken"], "queued_engineering_workflow")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertEqual(result["response_metadata"]["command_payload"]["workflow"], "drainage")
        self.assertEqual(result["response_metadata"]["action_planning"]["selected_action_id"], "revise_drainage")

    def test_approve_this_blocks_responsibility_request(self):
        result = decide_chat(
            {"message": "approve this", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "blocked_responsibility_request")
        self.assertTaxonomyMetadata(result, "understood_but_blocked")
        self.assertIn("cannot approve", result["assistant_message"])
        self.assertNotIn("approved", result["assistant_message"].lower())

    def test_stamp_it_blocks_responsibility_request(self):
        result = decide_chat(
            {"message": "stamp it", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "blocked_responsibility_request")
        self.assertTaxonomyMetadata(result, "understood_but_blocked")
        self.assertIn("cannot approve, stamp, seal", result["assistant_message"])

    def test_full_construction_set_blocks_responsibility_request(self):
        result = decide_chat(
            {"message": "do full construction set", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "blocked_responsibility_request")
        self.assertTaxonomyMetadata(result, "understood_but_blocked")
        self.assertIn("cannot approve, stamp, seal", result["assistant_message"])
        self.assertNotIn("construction-ready", result["assistant_message"])

    def test_missing_standards_export_requirements_report_real_blockers(self):
        store = RecordingProjectStore(
            _record()
            | {
                "latest_result": {
                    "success": True,
                    "final_plan": {
                        "meta": {
                            "export_audit": {
                                "export_blocked": True,
                                "blocked_reasons": ["accepted_standards_missing", "survey_control_missing"],
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

        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("accepted_standards_missing", result["assistant_message"])
        self.assertIn("survey_control_missing", result["assistant_message"])

    def test_no_assumption_mode_asks_one_targeted_question(self):
        result = decide_chat(
            {
                "message": "add a building",
                "context": {
                    "strategy_mode": "user",
                    "has_plan": True,
                    "lot_width": "500",
                    "lot_height": "400",
                    "current_project": {"project_id": "project_123"},
                },
            },
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "asked_clarifying_question")
        self.assertTaxonomyMetadata(result, "understood_needs_more_info")
        self.assertIn("footprint dimensions", result["assistant_message"])

    def test_assisted_mode_assumption_labels_are_explicit(self):
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

        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertTrue(result["assumptions"])
        self.assertIn("draft geometry", " ".join(result["assumptions"]).lower())

    def test_next_step_guidance_before_site_is_locked(self):
        store = RecordingProjectStore(
            _record()
            | {
                "latest_result": {
                    "success": True,
                    "final_plan": {
                        "meta": {
                            "site_locked": False,
                            "address_status": "missing",
                            "site_size_status": "provided",
                        }
                    },
                }
            }
        )

        result = decide_chat(
            {
                "message": "what should I do next?",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("Lock the site boundary", result["assistant_message"])
        self.assertIn("Lock the site boundary", result["response_metadata"]["next_best_action"])

    def test_why_export_blocked_reads_review_package_blockers(self):
        store = RecordingProjectStore(
            _record()
            | {
                "latest_result": {
                    "success": True,
                    "final_plan": {
                        "meta": {
                            "export_audit": {
                                "export_blocked": True,
                                "blocked_reasons": [
                                    "engineer_review_required",
                                    "accepted_standards_missing",
                                ],
                            },
                            "engineer_review_status": "required",
                        }
                    },
                }
            }
        )

        result = decide_chat(
            {
                "message": "why can't I export?",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("engineer_review_required", result["assistant_message"])
        self.assertIn("accepted_standards_missing", result["response_metadata"]["blocker"])
        self.assertIn("next_best_action", result["response_metadata"])

    def test_what_am_i_doing_with_selected_geometry(self):
        result = decide_chat(
            {
                "message": "what am I doing?",
                "context": {
                    "active_workspace": "design_canvas",
                    "active_panel": "geometry",
                    "active_tool": "select",
                    "selected_geometry_ids": ["geom-basin"],
                    "selected_object_ids": ["drawn-basin"],
                    "site_locked": True,
                },
            },
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("tool select", result["assistant_message"])
        self.assertIn("selected geometry geom-basin", result["assistant_message"])

    def test_why_generate_drainage_blocked_cites_exact_blocker(self):
        store = RecordingProjectStore(
            _record()
            | {
                "latest_result": {
                    "success": True,
                    "final_plan": {
                        "meta": {
                            "convergence_summary": {
                                "blocked_exports": ["drainage"],
                                "blocked_reasons": ["drainage_outfall_missing"],
                            },
                            "next_best_action": "Select or draw an outfall target before rerunning drainage.",
                        }
                    },
                }
            }
        )

        result = decide_chat(
            {
                "message": "why generate drainage blocked",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("drainage_outfall_missing", result["assistant_message"])
        self.assertEqual(
            result["response_metadata"]["next_best_action"],
            "Select or draw an outfall target before rerunning drainage.",
        )

    def test_current_state_missing_context_says_state_missing(self):
        result = decide_chat(
            {"message": "what am I doing?", "context": {}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("not have enough workspace state", result["assistant_message"])

    def test_warning_question_uses_current_warning_context(self):
        result = decide_chat(
            {
                "message": "what does this warning mean?",
                "context": {
                    "issues": [{"severity": "warning", "message": "accepted_standards_missing"}],
                    "next_best_action": "Have the engineer/user accept the standards basis.",
                },
            },
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("accepted_standards_missing", result["assistant_message"])
        self.assertEqual(
            result["response_metadata"]["next_best_action"],
            "Have the engineer/user accept the standards basis.",
        )


if __name__ == "__main__":
    unittest.main()
