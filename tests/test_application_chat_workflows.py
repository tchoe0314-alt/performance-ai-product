import unittest
from unittest.mock import patch

from backend.application.chat_workflows import decide_chat
from backend.planning.cad_entity_model import CAD_ENTITY_MODEL_VERSION, history_event
from backend.planning.plan_pdf_understanding import SOURCE_CONFIDENCE
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
            "metadata": kwargs.get("metadata", self.record.get("metadata", {})),
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

    def test_chat_answers_dwg_export_without_claiming_native_support(self):
        store = RecordingProjectStore()

        result = decide_chat(
            {"message": "can I export DWG?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_dwg_export_capability")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("cannot export DWG natively", result["assistant_message"])
        self.assertIn("unsupported_no_native_writer", result["assistant_message"])
        self.assertFalse(result["response_metadata"]["command_payload"]["dwg_strategy"]["native_dwg_supported"])

    def test_chat_answers_dxf_roundtrip_preserved_and_lost_from_report(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"]["dxf_roundtrip_report_v1"] = {
            "source": "dxf_roundtrip_report_v1",
            "preserved": {"layers": True, "text_labels": True, "canonical_cad_entity_ids": True},
            "roundtrip_preservation_matrix": {"entity_count": "passed", "dimensions": "passed"},
            "lost_limited": [{"field": "symbol_block_placeholders", "expected": 1, "parsed": 0}],
            "unsupported": [{"entity_id": "cad-underlay-1", "type": "underlay_reference", "reason": "unsupported_entity_type"}],
            "blockers": [],
            "review_required": True,
            "construction_release_allowed": False,
        }
        context = {"current_project": {"project_id": "project_123", "latest_result": record["latest_result"]}}

        preserved = decide_chat(
            {"message": "what did the DXF preserve?", "context": context},
            decide_chat_message=decide_chat_message,
        )
        lost = decide_chat(
            {"message": "what was lost in DXF?", "context": context},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(preserved["action_taken"], "answered_dxf_roundtrip_preservation")
        self.assertIn("layers=True", preserved["assistant_message"])
        self.assertIn("local review evidence", preserved["assistant_message"])
        self.assertEqual(lost["action_taken"], "answered_dxf_roundtrip_loss")
        self.assertIn("cad-underlay-1", lost["assistant_message"])
        self.assertIn("construction-release", lost["assistant_message"])

    def test_chat_answers_autocad_open_and_dxf_review_only_without_overclaim(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"]["export_package_report_v1"] = {
            "supported_deliverables": {"dxf": {"roundtrip_status": "passed_review_only"}}
        }
        context = {"current_project": {"project_id": "project_123", "latest_result": record["latest_result"]}}

        open_result = decide_chat(
            {"message": "can this open in AutoCAD?", "context": context},
            decide_chat_message=decide_chat_message,
        )
        review_result = decide_chat(
            {"message": "why is DXF review-only?", "context": context},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(open_result["action_taken"], "answered_autocad_dxf_open_status")
        self.assertIn("may open in AutoCAD as a DXF review exchange artifact", open_result["assistant_message"])
        self.assertIn("cannot claim AutoCAD acceptance", open_result["assistant_message"])
        self.assertEqual(review_result["action_taken"], "explained_dxf_review_only")
        self.assertIn("does not prove AutoCAD or Civil 3D acceptance", review_result["assistant_message"])
        self.assertNotIn("construction ready", review_result["assistant_message"].lower())

    def test_chat_reports_persistent_cad_entities_review_only(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION] = {
            "entities": [
                {
                    "id": "cad-line-1",
                    "type": "line",
                    "geometry": {"start": {"x": 0, "y": 0}, "end": {"x": 25, "y": 0}},
                    "source": "manual_drawn",
                    "source_confidence": "user_drawn_review_required",
                    "review_status": "draft_review_required",
                    "draft_review_required": True,
                    "construction_release_allowed": False,
                }
            ]
        }
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "what CAD entities are in this project?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "reported_cad_entities")
        self.assertIn("cad-line-1", result["assistant_message"])
        self.assertIn("construction_release_allowed=false", result["assistant_message"])
        model = result["response_metadata"]["command_payload"][CAD_ENTITY_MODEL_VERSION]
        self.assertFalse(model["construction_release_allowed"])

    def test_chat_converts_drawn_object_to_persistent_cad_entity(self):
        record = _record_with_handoffs([_handoff()])
        store = RecordingProjectStore(record)

        result = decide_chat(
            {
                "message": "convert this drawn object to a CAD entity",
                "context": {
                    "current_project": {"project_id": "project_123"},
                    "selected_object_id": "drawn-1",
                },
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "converted_drawn_object_to_cad_entity")
        self.assertIn("draft_review_required", result["assistant_message"])
        saved_meta = store.record["latest_result"]["final_plan"]["meta"]
        entities = saved_meta[CAD_ENTITY_MODEL_VERSION]["entities"]
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["linked_object_id"], "drawn-1")
        self.assertFalse(entities[0]["construction_release_allowed"])
        history = saved_meta[CAD_ENTITY_MODEL_VERSION]["history"]
        self.assertEqual(history[0]["event_type"], "entity_converted")
        self.assertTrue(history[0]["review_required"])
        self.assertFalse(history[0]["construction_release_allowed"])
        self.assertTrue(saved_meta[CAD_ENTITY_MODEL_VERSION]["undo_redo"]["can_undo"])

    def test_chat_reports_cad_history_and_revision_timeline(self):
        record = _record()
        entity = {
            "id": "cad-line-1",
            "type": "line",
            "geometry": {"start": {"x": 0, "y": 0}, "end": {"x": 25, "y": 0}},
            "source": "manual_drawn",
            "source_confidence": "survey-backed",
            "review_status": "draft_review_required",
            "draft_review_required": True,
            "construction_release_allowed": False,
            "dirty": True,
        }
        record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION] = {
            "entities": [entity],
            "history": [history_event("entity_geometry_changed", "cad-line-1", actor="user_1", after=entity)],
        }
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "what changed in CAD?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "reported_cad_revision_changes")
        self.assertIn("cad-line-1", result["assistant_message"])
        self.assertIn("construction_release_allowed=false", result["assistant_message"])
        timeline = result["response_metadata"]["command_payload"]["cad_revision_timeline"]
        self.assertEqual(timeline["changed_entities"], ["cad-line-1"])
        self.assertFalse(timeline["construction_release_allowed"])

    def test_chat_blocks_cad_undo_without_safe_replay(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION] = {
            "entities": [
                {
                    "id": "cad-line-1",
                    "type": "line",
                    "geometry": {"start": {"x": 0, "y": 0}, "end": {"x": 25, "y": 0}},
                    "source_confidence": "survey-backed",
                    "review_status": "draft_review_required",
                    "draft_review_required": True,
                    "construction_release_allowed": False,
                }
            ]
        }
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "undo last CAD edit", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "blocked_cad_undo_requires_safe_snapshot_review")
        self.assertIn("blocked", result["assistant_message"])
        self.assertIn("draft_review_required", result["assistant_message"])
        self.assertFalse(result["response_metadata"]["command_payload"]["cad_undo_redo"]["construction_release_allowed"])

    def test_chat_reports_stale_or_invalid_cad_entities(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION] = {
            "entities": [
                {
                    "id": "cad-bad-1",
                    "type": "polygon",
                    "geometry": {"points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]},
                    "source_confidence": "missing",
                    "review_status": "stale",
                    "draft_review_required": True,
                    "construction_release_allowed": False,
                    "stale": True,
                }
            ]
        }
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "what CAD entities are stale or invalid?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "reported_stale_invalid_cad_entities")
        self.assertIn("cad-bad-1", result["assistant_message"])
        self.assertIn("review-only", result["assistant_message"])

    def test_chat_explains_why_dwg_is_unsupported(self):
        result = decide_chat(
            {"message": "why is DWG unsupported?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "explained_dwg_unsupported_status")
        self.assertIn("does not include a native DWG writer", result["assistant_message"])
        self.assertIn("separate licensing", result["assistant_message"])
        self.assertNotIn("verified Civil 3D", result["assistant_message"])

    def test_chat_handles_symbol_insert_attribute_edit_and_underlay(self):
        insert = decide_chat(
            {"message": "insert hydrant symbol", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )
        self.assertEqual(insert["action_taken"], "prepared_symbol_insert")
        symbol_payload = insert["response_metadata"]["command_payload"]["symbol_insert_v1"]
        self.assertEqual(symbol_payload["kind"], "hydrant")
        self.assertEqual(symbol_payload["editable_attributes"], ["id", "label", "elevation", "material", "size", "source", "review_note"])
        self.assertEqual(symbol_payload["engineering_status"], "draft_review_required")
        self.assertFalse(symbol_payload["native_dwg_block_parity"])

        edit = decide_chat(
            {
                "message": "edit this block attribute",
                "context": {
                    "current_project": {"project_id": "project_123"},
                    "selected_object_id": "hydrant-1",
                },
            },
            decide_chat_message=decide_chat_message,
        )
        self.assertEqual(edit["action_taken"], "answered_block_attribute_edit_path")
        self.assertIn("review_note", edit["response_metadata"]["command_payload"]["symbol_attribute_edit_v1"]["editable_fields"])
        self.assertFalse(edit["response_metadata"]["command_payload"]["symbol_attribute_edit_v1"]["construction_release_allowed"])

        underlay = decide_chat(
            {"message": "attach this PDF as underlay", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )
        self.assertEqual(underlay["action_taken"], "prepared_reference_underlay_attachment")
        reference = underlay["response_metadata"]["command_payload"]["reference_underlay_v1"]
        self.assertEqual(reference["file_type"], "pdf")
        self.assertTrue(reference["not_editable"])
        self.assertTrue(reference["source_only"])
        self.assertFalse(reference["native_xref_parity"])

    def test_chat_blocks_hydrant_catalog_insert_without_source_review(self):
        result = decide_chat(
            {
                "message": "insert hydrant from catalog",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "blocked_catalog_missing_source_review")
        self.assertEqual(result["response_metadata"]["required_missing_inputs"], ["catalog source and review metadata"])
        self.assertFalse(result["response_metadata"]["state_changed"])
        self.assertNotEqual(result["action_taken"], "prepared_symbol_insert")

    def test_chat_reports_open_review_issues(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"].update(
            {
                "blockers": [
                    {
                        "area": "drainage",
                        "field": "outfall",
                        "reason": "Drainage outfall is missing.",
                    }
                ],
                "export_package_report_v1": {"blocked_reasons": ["sheet_index_missing"]},
            }
        )
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "what issues are open?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "reported_review_issue_tracker")
        self.assertIn("Open review issues", result["assistant_message"])
        tracker = result["response_metadata"]["command_payload"]["review_issue_tracker_v1"]
        self.assertGreaterEqual(tracker["open_count"], 2)
        self.assertFalse(tracker["field_use_allowed"])

    def test_chat_filters_drainage_blockers_and_engineer_queue(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"].update(
            {
                "blockers": [
                    {"area": "drainage", "field": "outfall", "reason": "Drainage outfall is missing."},
                    {"area": "grading", "field": "surface", "reason": "Grading surface is missing."},
                ]
            }
        )
        store = RecordingProjectStore(record)

        drainage = decide_chat(
            {"message": "show drainage blockers", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        self.assertIn("Drainage blockers", drainage["assistant_message"])
        self.assertIn("Drainage outfall", drainage["assistant_message"])

        queue = decide_chat(
            {"message": "what does the engineer need to review?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        self.assertIn("Engineer review queue", queue["assistant_message"])

    def test_chat_answers_discipline_depth_blocker_with_exact_fix(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"].update(
            {
                "engine_readiness": {
                    "engines": {
                        "storm_pipe": {
                            "status": "concept_ready_needs_production_depth",
                            "evidence": ["storm_segments"],
                            "production_blockers": [
                                {
                                    "area": "storm_depth",
                                    "field": "depth_validation",
                                    "message": "Storm depth needs HGL and EGL profiles from production hydraulic evidence.",
                                }
                            ],
                            "discipline_depth_proof": {
                                "version": "discipline_depth_proof_v1",
                                "engine_id": "storm_pipe",
                                "engineer_review_required": True,
                                "proof_checklist": [
                                    {"id": "hgl_egl", "label": "HGL/EGL evidence", "status": "missing"}
                                ],
                                "missing_proof": [
                                    {"id": "hgl_egl", "label": "HGL/EGL evidence", "status": "missing"}
                                ],
                                "exact_fixes": [
                                    "Provide hgl/egl evidence proof and rerun storm pipe depth validation."
                                ],
                            },
                        }
                    }
                }
            }
        )
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "why is storm blocked and what is the exact fix?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_discipline_depth_blocker")
        self.assertIn("HGL/EGL evidence", result["assistant_message"])
        self.assertIn("Exact fix", result["assistant_message"])
        self.assertIn("does not stamp, seal, certify", result["assistant_message"])
        self.assertEqual(result["response_metadata"]["command_payload"]["engine_id"], "storm_pipe")

    def test_chat_resolves_and_reopens_review_issue(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"].update(
            {"blockers": [{"area": "drainage", "field": "outfall", "reason": "Drainage outfall is missing."}]}
        )
        store = RecordingProjectStore(record)
        listed = decide_chat(
            {"message": "what issues are open?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        issue_id = listed["response_metadata"]["command_payload"]["review_issue_tracker_v1"]["open_issues"][0]["issue_id"]

        resolved = decide_chat(
            {"message": f"resolve issue {issue_id}", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        self.assertEqual(resolved["action_taken"], "resolve_review_issue")
        tracker = resolved["response_metadata"]["command_payload"]["review_issue_tracker_v1"]
        resolved_issue = [item for item in tracker["issues"] if item["issue_id"] == issue_id][0]
        self.assertEqual(resolved_issue["status"], "resolved")
        self.assertFalse(resolved_issue["field_use_allowed"])

        reopened = decide_chat(
            {"message": f"reopen issue {issue_id}", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        reopened_issue = [
            item
            for item in reopened["response_metadata"]["command_payload"]["review_issue_tracker_v1"]["issues"]
            if item["issue_id"] == issue_id
        ][0]
        self.assertEqual(reopened_issue["status"], "reopened")

    def test_chat_assigns_issue_and_reports_review_owner(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"].update(
            {"blockers": [{"area": "drainage", "field": "outfall", "reason": "Drainage outfall is missing."}]}
        )
        store = RecordingProjectStore(record)

        assigned = decide_chat(
            {"message": "assign drainage issue to reviewer", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(assigned["action_taken"], "assign_review_issue")
        tracker = assigned["response_metadata"]["command_payload"]["review_issue_tracker_v1"]
        issue = [item for item in tracker["issues"] if item["discipline"] == "drainage"][0]
        self.assertEqual(issue["assigned_to"], "reviewer")
        self.assertEqual(issue["history"][-1]["action"], "assign")
        self.assertFalse(issue["field_use_allowed"])

        who = decide_chat(
            {"message": "who needs to review this?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        self.assertEqual(who["action_taken"], "reported_review_issue_tracker")
        self.assertIn("Review assignments", who["assistant_message"])
        self.assertIn("reviewer", who["assistant_message"])

    def test_chat_reports_version_changes_and_review_history(self):
        record = _record()
        record["metadata"] = {
            "workflow": {
                "version_history": {
                    "version": "project_version_history_v1",
                    "latest_revision_id": "rev_2",
                    "snapshots": [{"revision_id": "rev_2"}, {"revision_id": "rev_1"}],
                    "latest_comparison": {
                        "added_objects": ["inlet-1"],
                        "removed_objects": [],
                        "changed_objects": ["pipe-1"],
                        "added_blockers": ["issue-grading"],
                        "removed_blockers": ["issue-drainage"],
                        "changed_quantities": [{"key": "pipe_length_ft", "before": 80, "after": 120}],
                        "truth_label": "Version comparison is an audit/workflow aid only.",
                    },
                    "review_package_history": [{"artifact_id": "artifact_1", "revision_id": "rev_2"}],
                }
            }
        }
        record["latest_result"]["final_plan"]["meta"].update(
            {
                "blockers": [{"area": "drainage", "field": "outfall", "reason": "Drainage outfall is missing."}],
                "candidate_review_inbox_v1": {
                    "version": "candidate_review_inbox_v1",
                    "candidates": [],
                },
                "candidate_review_decisions_v1": [{"action": "accept", "candidate_id": "cand-1", "reviewer_id": "user_1"}],
            }
        )
        store = RecordingProjectStore(record)

        changes = decide_chat(
            {"message": "what changed since last version?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        self.assertEqual(changes["action_taken"], "reported_project_version_comparison")
        self.assertIn("1 added object", changes["assistant_message"])
        self.assertIn("1 quantity change", changes["assistant_message"])
        self.assertIn("project_version_history_v1", changes["response_metadata"]["command_payload"])

        history = decide_chat(
            {"message": "show review history", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        self.assertEqual(history["action_taken"], "reported_project_review_history")
        payload = history["response_metadata"]["command_payload"]["project_review_history_v1"]
        self.assertEqual(len(payload["candidate_audit"]), 1)
        self.assertEqual(len(payload["review_package_history"]), 1)
        self.assertIn("not Civora approval", payload["truth_label"])

    def test_chat_explains_civil3d_requirements(self):
        result = decide_chat(
            {"message": "what do I need for Civil3D?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_civil3d_compatibility_requirements")
        self.assertIn("target-workflow record", result["assistant_message"])
        self.assertIn("verifier identity", result["assistant_message"])
        self.assertIn("tool and version", result["assistant_message"])
        self.assertIn("source artifacts", result["assistant_message"])
        self.assertIn("artifact hashes", result["assistant_message"])
        self.assertIn("workflow steps", result["assistant_message"])
        self.assertIn("screenshots/evidence URI", result["assistant_message"])
        self.assertIn("not_verified", result["assistant_message"])
        self.assertIn("blocked_needs_review", result["assistant_message"])
        self.assertIn("externally_verified_review_only", result["assistant_message"])

    def test_chat_answers_will_this_open_in_civil3d_without_overclaiming(self):
        result = decide_chat(
            {"message": "will this open in Civil3D?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_civil3d_open_status")
        self.assertIn("might open as a review artifact", result["assistant_message"])
        self.assertIn("cannot claim it will open correctly", result["assistant_message"])
        self.assertIn("not_verified", result["assistant_message"])

    def test_chat_answers_civil3d_preserved_elements_from_external_record(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"]["export_package_report_v1"] = {
            "external_verification": {
                "civil3d": {
                    "status": "externally_verified_review_only",
                    "preserved_elements": ["alignments", "pipe runs", "structure labels"],
                    "lost_limited_elements": ["Civil 3D styles require remapping"],
                }
            }
        }
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "what did Civil3D preserve?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_civil3d_preservation_status")
        self.assertIn("externally_verified_review_only", result["assistant_message"])
        self.assertIn("pipe runs", result["assistant_message"])
        self.assertIn("Civil 3D styles require remapping", result["assistant_message"])
        self.assertIn("engineer review is still required", result["assistant_message"])

    def test_chat_answers_civil3d_ready_without_overclaiming(self):
        result = decide_chat(
            {"message": "is this Civil3D ready?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_civil3d_ready_status")
        self.assertIn("not Civil3D-ready", result["assistant_message"])
        self.assertIn("not_verified", result["assistant_message"])
        self.assertIn("DXF and LandXML remain the exchange paths", result["assistant_message"])
        self.assertIn("not approval", result["assistant_message"])
        self.assertNotIn("is Civil3D-ready", result["assistant_message"])

    def test_chat_answers_dxf_roundtrip_preservation_scope(self):
        result = decide_chat(
            {"message": "what did the DXF roundtrip preserve?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_dxf_roundtrip_preservation")
        self.assertIn("layer preservation", result["assistant_message"])
        self.assertIn("supported object types", result["assistant_message"])
        self.assertIn("canonical ID traceability", result["assistant_message"])
        self.assertIn("does not verify Civil 3D or DWG", result["assistant_message"])

    def test_chat_answers_sheet_plotting_commands_without_construction_claims(self):
        messages = [
            ("make a sheet set", "answered_make_review_sheet_set"),
            ("set viewport scale to 1 inch equals 50 feet", "answered_set_viewport_scale"),
            ("add revision note revise storm callouts", "answered_add_revision_note"),
            ("plot this review set", "answered_plot_review_set"),
            ("why is this not for construction?", "answered_not_for_construction_sheet_limit"),
        ]
        for message, action in messages:
            with self.subTest(message=message):
                result = decide_chat(
                    {"message": message, "context": {"current_project": {"project_id": "project_123"}}},
                    decide_chat_message=decide_chat_message,
                )
                self.assertEqual(result["action_taken"], action)
                payload = result["response_metadata"]["command_payload"]
                self.assertFalse(payload["construction_release_allowed"])
                self.assertTrue(payload["engineer_review_required"])
                self.assertIn("paper_model_plotting_standards_v1", payload)
                self.assertIn("review", result["assistant_message"].lower())
                self.assertNotIn("approved construction document", result["assistant_message"].replace("not an approved construction document", ""))
                if action == "answered_set_viewport_scale":
                    self.assertEqual(payload["viewport_scale"], "1:50")
                    self.assertTrue(payload["scale_locked"])
                if action == "answered_plot_review_set":
                    self.assertFalse(payload["exports"]["approved_construction_documents"])
                    self.assertEqual(payload["plot_styles"]["review_watermark"], "REVIEW ONLY - NOT FOR CONSTRUCTION")

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
        self.assertEqual(saved_meta["setup_wizard_state_v1"]["schema_version"], "setup_wizard_state_v1")
        self.assertEqual(saved_meta["setup_wizard_state_v1"]["current_step_id"], "address_location")
        self.assertIn("Review", saved_meta["setup_wizard_state_v1"]["next_action"])
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

    def test_chat_reports_saved_online_discovery(self):
        record = _record()
        discovery = {
            "version": "online_existing_conditions_discovery_v1",
            "candidate_count": 2,
            "sources": [
                {
                    "key": "terrain_dem_lidar",
                    "label": "terrain/DEM/LiDAR",
                    "provider": "USGS 3DEP EPQS",
                    "status": "candidates_found",
                    "candidate_count": 1,
                    "blockers": ["terrain candidates are review-required"],
                },
                {
                    "key": "building_footprints",
                    "label": "building footprints",
                    "provider": "configured_building_footprints_arcgis",
                    "status": "unconfigured",
                    "candidate_count": 0,
                    "blockers": ["No building footprint GIS source is configured."],
                },
            ],
            "survey_control": {"survey_control_satisfied": False},
        }
        record["project_input"]["meta"] = {
            "site_inputs": {
                "address": "1 Main St",
                "online_existing_conditions_discovery_v1": discovery,
            }
        }
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "what did you find online?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "reported_online_existing_conditions_discovery")
        self.assertTaxonomyMetadata(result, "understood_and_answered")
        self.assertIn("terrain/DEM/LiDAR", result["assistant_message"])
        self.assertIn("No building footprint GIS source is configured.", result["assistant_message"])
        self.assertIn("candidate/review-required", result["assistant_message"])

    def test_chat_answers_auto_site_context_questions(self):
        record = _record()
        discovery = {
            "version": "online_existing_conditions_discovery_v1",
            "candidate_count": 3,
            "sources": [
                {"key": "parcel_site_boundary", "label": "parcel/site boundary", "provider": "county parcels", "candidate_count": 1, "blockers": ["parcel candidates are review-required"]},
                {"key": "road_row", "label": "road/ROW data", "provider": "county roads", "candidate_count": 1, "blockers": ["road candidates are review-required"]},
                {"key": "terrain_dem_lidar", "label": "terrain/DEM/LiDAR", "provider": "USGS 3DEP EPQS", "candidate_count": 1, "blockers": ["terrain candidates are review-required"]},
                {"key": "building_footprints", "label": "building footprints", "status": "unconfigured", "candidate_count": 0, "blockers": ["No building footprint GIS source is configured."]},
                {"key": "public_utilities", "label": "public utility layers", "status": "unconfigured", "candidate_count": 0, "blockers": ["No existing utilities GIS source is configured."]},
            ],
            "missing_sources": [
                {"key": "building_footprints", "label": "building footprints", "missing": ["No building footprint GIS source is configured."]},
                {"key": "public_utilities", "label": "public utility layers", "missing": ["No existing utilities GIS source is configured."]},
            ],
            "survey_control": {"survey_control_satisfied": False},
        }
        record["project_input"]["meta"] = {"site_inputs": {"online_existing_conditions_discovery_v1": discovery}}
        store = RecordingProjectStore(record)

        questions = {
            "what did you find?": ["Found candidates", "parcel/site boundary", "road/ROW data", "terrain/DEM/LiDAR"],
            "why didn't it find buildings?": ["buildings", "provider", "will not report source success"],
            "why didn't it find utilities?": ["utilities", "provider", "will not report source success"],
            "is this survey control?": ["No.", "do not establish survey control"],
            "what is missing from this site?": ["Missing from this site context", "building footprints", "public utility layers"],
        }

        for question, expected_parts in questions.items():
            result = decide_chat(
                {"message": question, "context": {"current_project": {"project_id": "project_123"}}},
                decide_chat_message=decide_chat_message,
                project_store=store,
                user_id="user_1",
            )
            for expected in expected_parts:
                self.assertIn(expected, result["assistant_message"])
            self.assertNotIn("construction-ready", result["assistant_message"].lower())

    def test_chat_explains_why_buildings_were_not_found(self):
        record = _record()
        record["project_input"]["meta"] = {
            "site_inputs": {
                "online_existing_conditions_discovery_v1": {
                    "version": "online_existing_conditions_discovery_v1",
                    "candidate_count": 0,
                    "sources": [
                        {
                            "key": "building_footprints",
                            "label": "building footprints",
                            "status": "unconfigured",
                            "candidate_count": 0,
                            "blockers": ["No building footprint GIS source is configured."],
                        }
                    ],
                }
            }
        }
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "why didn't it find buildings?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "explained_missing_local_gis_source")
        self.assertIn("No configured local GIS provider is registered for buildings", result["assistant_message"])

    def test_chat_reports_configured_gis_provider_registry(self):
        record = _record()
        record["project_input"]["meta"] = {
            "site_inputs": {
                "local_gis_provider_registry_v1": {
                    "version": "local_gis_provider_registry_v1",
                    "providers": [
                        {
                            "id": "parcel-provider",
                            "name": "County parcel provider",
                            "source_type": "parcels",
                            "jurisdiction_level": "county",
                            "provider_kind": "arcgis_rest",
                            "service_url": "https://county.example/arcgis/rest/services/Parcels/MapServer",
                            "arcgis": {"service_url": "https://county.example/arcgis/rest/services/Parcels/MapServer", "layer_id": 0},
                            "status": "configured",
                            "health": {"status": "unchecked"},
                            "freshness": {"status": "unknown"},
                        }
                    ],
                }
            }
        }

        result = decide_chat(
            {"message": "what online sources are configured?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=RecordingProjectStore(record),
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "reported_local_gis_provider_registry")
        self.assertIn("County parcel provider", result["assistant_message"])
        self.assertIn("review-required", result["assistant_message"])

    def test_chat_adds_parcel_provider_record(self):
        store = RecordingProjectStore(_record())

        result = decide_chat(
            {
                "message": "add a parcel provider https://county.example/arcgis/rest/services/Parcels/MapServer",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "added_local_gis_provider")
        saved_registry = store.saved[-1]["project_input"]["meta"]["site_inputs"]["local_gis_provider_registry_v1"]
        self.assertTrue(any(item["source_type"] == "parcels" for item in saved_registry["providers"]))
        self.assertIn("not survey-backed", result["assistant_message"])

    def test_chat_checks_provider_health_without_source_success(self):
        record = _record()
        record["project_input"]["meta"] = {
            "site_inputs": {
                "local_gis_provider_registry_v1": {
                    "version": "local_gis_provider_registry_v1",
                    "providers": [
                        {
                            "id": "building-provider",
                            "name": "City building provider",
                            "source_type": "buildings",
                            "provider_kind": "arcgis_rest",
                            "service_url": "https://city.example/arcgis/rest/services/Buildings/MapServer",
                            "arcgis": {"service_url": "https://city.example/arcgis/rest/services/Buildings/MapServer", "layer_id": 0},
                            "status": "configured",
                        }
                    ],
                }
            }
        }
        fake_health = {
            "version": "local_gis_provider_registry_v1",
            "provider_count": 1,
            "healthy_provider_count": 1,
            "stale_provider_count": 1,
            "providers": [],
        }
        with patch("backend.application.chat_workflows.check_registry_health", return_value=fake_health):
            result = decide_chat(
                {"message": "check provider health", "context": {"current_project": {"project_id": "project_123"}}},
                decide_chat_message=decide_chat_message,
                project_store=RecordingProjectStore(record),
                user_id="user_1",
            )

        self.assertEqual(result["action_taken"], "checked_local_gis_provider_health")
        self.assertIn("1 of 1 healthy", result["assistant_message"])
        self.assertIn("reachability/config only", result["assistant_message"])

    def test_chat_explains_missing_building_provider(self):
        result = decide_chat(
            {"message": "why didn't it find buildings?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=RecordingProjectStore(_record()),
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "explained_missing_local_gis_source")
        self.assertIn("No configured local GIS provider is registered for buildings", result["assistant_message"])
        self.assertIn("will not report source success", result["assistant_message"])

    def test_chat_reports_configured_gis_provider_registry(self):
        record = _record()
        record["project_input"]["meta"] = {
            "site_inputs": {
                "local_gis_provider_registry_v1": {
                    "version": "local_gis_provider_registry_v1",
                    "providers": [
                        {
                            "id": "parcel-provider",
                            "name": "County parcel provider",
                            "source_type": "parcels",
                            "jurisdiction_level": "county",
                            "provider_kind": "arcgis_rest",
                            "service_url": "https://county.example/arcgis/rest/services/Parcels/MapServer",
                            "arcgis": {"service_url": "https://county.example/arcgis/rest/services/Parcels/MapServer", "layer_id": 0},
                            "status": "configured",
                            "health": {"status": "unchecked"},
                            "freshness": {"status": "unknown"},
                        }
                    ],
                }
            }
        }

        result = decide_chat(
            {"message": "what online sources are configured?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=RecordingProjectStore(record),
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "reported_local_gis_provider_registry")
        self.assertIn("County parcel provider", result["assistant_message"])
        self.assertIn("review-required", result["assistant_message"])

    def test_chat_adds_parcel_provider_record(self):
        store = RecordingProjectStore(_record())

        result = decide_chat(
            {
                "message": "add a parcel provider https://county.example/arcgis/rest/services/Parcels/MapServer",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "added_local_gis_provider")
        saved_registry = store.saved[-1]["project_input"]["meta"]["site_inputs"]["local_gis_provider_registry_v1"]
        self.assertTrue(any(item["source_type"] == "parcels" for item in saved_registry["providers"]))
        self.assertIn("not survey-backed", result["assistant_message"])

    def test_chat_checks_provider_health_without_source_success(self):
        record = _record()
        record["project_input"]["meta"] = {
            "site_inputs": {
                "local_gis_provider_registry_v1": {
                    "version": "local_gis_provider_registry_v1",
                    "providers": [
                        {
                            "id": "building-provider",
                            "name": "City building provider",
                            "source_type": "buildings",
                            "provider_kind": "arcgis_rest",
                            "service_url": "https://city.example/arcgis/rest/services/Buildings/MapServer",
                            "arcgis": {"service_url": "https://city.example/arcgis/rest/services/Buildings/MapServer", "layer_id": 0},
                            "status": "configured",
                        }
                    ],
                }
            }
        }
        fake_health = {
            "version": "local_gis_provider_registry_v1",
            "provider_count": 1,
            "healthy_provider_count": 1,
            "stale_provider_count": 1,
            "providers": [],
        }
        with patch("backend.application.chat_workflows.check_registry_health", return_value=fake_health):
            result = decide_chat(
                {"message": "check provider health", "context": {"current_project": {"project_id": "project_123"}}},
                decide_chat_message=decide_chat_message,
                project_store=RecordingProjectStore(record),
                user_id="user_1",
            )

        self.assertEqual(result["action_taken"], "checked_local_gis_provider_health")
        self.assertIn("1 of 1 healthy", result["assistant_message"])
        self.assertIn("reachability/config only", result["assistant_message"])

    def test_chat_fetches_and_persists_online_discovery_from_address(self):
        store = RecordingProjectStore()
        fake_result = {
            "online_existing_conditions_discovery_v1": {
                "version": "online_existing_conditions_discovery_v1",
                "candidate_count": 1,
                "sources": [
                    {
                        "key": "parcel_site_boundary",
                        "label": "parcel/site boundary",
                        "provider": "county",
                        "status": "candidates_found",
                        "candidate_count": 1,
                        "blockers": ["parcel candidates are review-required"],
                    }
                ],
            },
            "map_feature_detection_report_v1": {"candidate_count": 1, "feature_candidates": []},
            "existing_conditions_package": {"status": "blocked"},
            "location_context": {"address": "1 Main St"},
        }
        with patch("backend.application.chat_workflows.fetch_online_existing_conditions", return_value=fake_result) as fetch:
            result = decide_chat(
                {"message": "find site data from this address 1 Main St", "context": {"current_project": {"project_id": "project_123"}}},
                decide_chat_message=decide_chat_message,
                project_store=store,
                user_id="user_1",
            )

        self.assertEqual(result["action_taken"], "fetched_online_existing_conditions_candidates")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        fetch.assert_called_once()
        saved_meta = store.saved[-1]["latest_result"]["final_plan"]["meta"]
        saved_site_inputs = store.saved[-1]["project_input"]["meta"]["site_inputs"]
        self.assertEqual(saved_meta["online_existing_conditions_discovery_v1"]["candidate_count"], 1)
        self.assertEqual(saved_site_inputs["online_existing_conditions_discovery_v1"]["candidate_count"], 1)

    def test_chat_answers_gretna_online_source_and_candidate_review_prompts(self):
        record = _record()
        discovery = {
            "version": "online_existing_conditions_discovery_v1",
            "candidate_count": 2,
            "configured_provider_count": 6,
            "local_gis_provider_registry_v1": {
                "version": "local_gis_provider_registry_v1",
                "providers": [
                    {
                        "id": "sarpy-parcels",
                        "name": "Sarpy County tax parcels",
                        "source_type": "parcels",
                        "jurisdiction_level": "county",
                        "provider_kind": "arcgis_rest",
                        "service_url": "https://services.arcgis.com/OiG7dbwhQEWoy77N/arcgis/rest/services/Sarpy_Parcels_WFL1/FeatureServer",
                        "arcgis": {
                            "service_url": "https://services.arcgis.com/OiG7dbwhQEWoy77N/arcgis/rest/services/Sarpy_Parcels_WFL1/FeatureServer",
                            "layer_id": 0,
                        },
                        "status": "configured",
                        "health": {"status": "unchecked"},
                        "freshness": {"status": "stale"},
                    },
                    {
                        "id": "sarpy-buildings",
                        "name": "Sarpy County building footprints",
                        "source_type": "buildings",
                        "jurisdiction_level": "county",
                        "provider_kind": "arcgis_rest",
                        "service_url": "https://geodata.sarpy.gov/arcgis/rest/services/Cadastral/LandRecordsDynamic/MapServer",
                        "arcgis": {
                            "service_url": "https://geodata.sarpy.gov/arcgis/rest/services/Cadastral/LandRecordsDynamic/MapServer",
                            "layer_id": 42,
                        },
                        "status": "configured",
                        "health": {"status": "unchecked"},
                        "freshness": {"status": "unknown"},
                    },
                ],
            },
            "sources": [
                {
                    "key": "parcel_site_boundary",
                    "label": "parcel/site boundary",
                    "provider": "Sarpy County tax parcels",
                    "status": "candidates_found",
                    "candidate_count": 1,
                    "blockers": ["parcel/site boundary candidates are review-required and not survey-backed."],
                    "review_required": True,
                },
                {
                    "key": "road_row",
                    "label": "road/ROW data",
                    "provider": "Sarpy County road centerlines",
                    "status": "candidates_found",
                    "candidate_count": 1,
                    "blockers": ["road/ROW data candidates are review-required and not survey-backed."],
                    "review_required": True,
                },
                {
                    "key": "building_footprints",
                    "label": "building footprints",
                    "provider": "Sarpy County building footprints",
                    "status": "ready",
                    "candidate_count": 0,
                    "blockers": ["building footprints provider responded but returned no features inside the address search area."],
                    "review_required": True,
                },
            ],
        }
        record["project_input"]["meta"] = {
            "site_inputs": {
                "address": "20525 Margo St, Gretna, NE",
                "online_existing_conditions_discovery_v1": discovery,
                "local_gis_provider_registry_v1": discovery["local_gis_provider_registry_v1"],
            }
        }
        record["latest_result"]["final_plan"]["meta"].update(
            {
                "online_existing_conditions_discovery_v1": discovery,
                "local_gis_provider_registry_v1": discovery["local_gis_provider_registry_v1"],
                "map_feature_detection_report_v1": {
                    "version": "map_feature_detection_report_v1",
                    "feature_candidates": [
                        {
                            "candidate_id": "gis-parcel-1",
                            "feature_type": "parcel_or_site_boundary",
                            "source_type": "official_gis",
                            "source_name": "Sarpy County tax parcels",
                            "source_url": "https://services.arcgis.com/OiG7dbwhQEWoy77N/arcgis/rest/services/Sarpy_Parcels_WFL1/FeatureServer/0/query",
                            "confidence": 0.88,
                            "acceptance_status": "pending",
                            "blockers": ["Official GIS source is candidate evidence until reviewed."],
                        }
                    ],
                },
            }
        )
        store = RecordingProjectStore(record)

        configured = decide_chat(
            {"message": "what online sources are configured?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        found = decide_chat(
            {"message": "what did you find online?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        buildings = decide_chat(
            {"message": "why didn't it find buildings?", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        parcel = decide_chat(
            {"message": "use the parcel boundary", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertIn("Sarpy County tax parcels", configured["assistant_message"])
        self.assertIn("review-required", configured["assistant_message"])
        self.assertIn("parcel/site boundary", found["assistant_message"])
        self.assertIn("building footprints provider responded but returned no features", found["assistant_message"])
        self.assertIn("provider record(s) are configured", buildings["assistant_message"])
        self.assertIn("will not report source success", buildings["assistant_message"])
        self.assertEqual(parcel["action_taken"], "accepted_candidate_review_items")
        self.assertIn("accepted as draft/review-required evidence", parcel["assistant_message"])
        self.assertNotIn("construction-ready", parcel["assistant_message"].lower())

    def test_chat_reports_national_gis_sources_without_project(self):
        result = decide_chat(
            {"message": "what national sources can you use?", "context": {}},
            decide_chat_message=decide_chat_message,
            project_store=None,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "reported_national_gis_sources")
        self.assertIn("US Census Geocoder", result["assistant_message"])
        self.assertIn("USGS 3DEP", result["assistant_message"])
        self.assertIn("FEMA NFHL", result["assistant_message"])
        self.assertIn("USFWS NWI", result["assistant_message"])
        self.assertIn("not survey/control", result["assistant_message"])

    def test_chat_answers_gis_data_is_not_survey_control(self):
        result = decide_chat(
            {"message": "is this GIS data survey control?", "context": {}},
            decide_chat_message=decide_chat_message,
            project_store=None,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "explained_gis_not_survey_control")
        self.assertIn("No.", result["assistant_message"])
        self.assertIn("candidate/review-required", result["assistant_message"])
        self.assertIn("does not establish survey control", result["assistant_message"])

    def test_chat_finds_providers_for_address(self):
        record = _record()
        store = RecordingProjectStore(record)
        fake_result = {
            "online_existing_conditions_discovery_v1": {
                "version": "online_existing_conditions_discovery_v1",
                "candidate_count": 1,
                "provider_packs": [{"pack_id": "austin_tx_city", "label": "Austin, TX provider pack"}],
                "sources": [
                    {
                        "key": "building_footprints",
                        "label": "building footprints",
                        "provider": "City of Austin building footprints 2023",
                        "status": "candidates_found",
                        "candidate_count": 1,
                        "blockers": ["building footprints candidates are review-required and not survey-backed."],
                    }
                ],
            },
            "map_feature_detection_report_v1": {"candidate_count": 1, "feature_candidates": []},
            "existing_conditions_package": {"status": "blocked"},
            "location_context": {"address": "301 W 2nd St, Austin, TX"},
        }
        with patch("backend.application.chat_workflows.fetch_online_existing_conditions", return_value=fake_result) as fetch:
            result = decide_chat(
                {"message": "find providers for this address 301 W 2nd St, Austin, TX", "context": {"current_project": {"project_id": "project_123"}}},
                decide_chat_message=decide_chat_message,
                project_store=store,
                user_id="user_1",
            )

        self.assertEqual(result["action_taken"], "fetched_online_existing_conditions_candidates")
        fetch.assert_called_once()
        self.assertIn("Austin, TX provider pack", result["assistant_message"])
        self.assertIn("candidate/review-required", result["assistant_message"])

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

    def test_cad_geometry_edit_chat_answers_selected_draft_operations(self):
        phrases = [
            ("trim this", "answered_cad_trim_edit_path", "trim"),
            ("offset this line 10 feet", "answered_cad_offset_edit_path", "offset"),
            ("fillet this corner", "answered_cad_fillet_edit_path", "fillet"),
            ("why can't this polygon close?", "explained_polygon_close_blockers", "self-intersection"),
            ("fix the geometry if you can", "answered_safe_geometry_fix_path", "cleanup"),
        ]
        for message, action, expected_text in phrases:
            with self.subTest(message=message):
                store = RecordingProjectStore(_record_with_handoffs([_handoff("drawn-cad", "geom-cad")]))

                result = decide_chat(
                    {
                        "message": message,
                        "context": {
                            "current_project": {"project_id": "project_123"},
                            "selected_object_ids": ["drawn-cad"],
                            "selected_geometry_ids": ["geom-cad"],
                        },
                    },
                    decide_chat_message=decide_chat_message,
                    project_store=store,
                    user_id="user_1",
                )

                self.assertEqual(result["action_taken"], action)
                self.assertTaxonomyMetadata(result, "understood_and_answered")
                self.assertEqual(result["run_mode"], "none")
                self.assertFalse(result["response_metadata"]["state_changed"])
                self.assertIn(expected_text, result["assistant_message"].lower())
                self.assertIn("review", result["assistant_message"].lower())
                self.assertNotIn("construction-ready", result["assistant_message"].lower())
                self.assertEqual(store.saved, [])

    def test_cad_geometry_edit_blocks_missing_selection_and_distance(self):
        store = RecordingProjectStore(_record_with_handoffs([_handoff("drawn-cad", "geom-cad")]))

        missing_selection = decide_chat(
            {"message": "trim this", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )
        missing_distance = decide_chat(
            {
                "message": "offset this line",
                "context": {
                    "current_project": {"project_id": "project_123"},
                    "selected_object_ids": ["drawn-cad"],
                    "selected_geometry_ids": ["geom-cad"],
                },
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(missing_selection["action_taken"], "blocked_geometry_edit_missing_selection")
        self.assertTaxonomyMetadata(missing_selection, "understood_needs_more_info")
        self.assertEqual(missing_distance["action_taken"], "blocked_geometry_edit_missing_distance")
        self.assertTaxonomyMetadata(missing_distance, "understood_needs_more_info")
        self.assertFalse(missing_selection["response_metadata"]["state_changed"])
        self.assertFalse(missing_distance["response_metadata"]["state_changed"])
        self.assertEqual(store.saved, [])

    def test_cad_command_line_chat_explains_commands_and_blockers_without_mutation(self):
        help_result = decide_chat(
            {
                "message": "What CAD command line commands are available?",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=RecordingProjectStore(_record_with_handoffs([_handoff("drawn-cad", "geom-cad")])),
            user_id="user_1",
        )
        blocked_result = decide_chat(
            {
                "message": "Why is MOVE selected blocked in the CAD command line?",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=RecordingProjectStore(_record_with_handoffs([_handoff("drawn-cad", "geom-cad")])),
            user_id="user_1",
        )

        self.assertEqual(help_result["action_taken"], "answered_cad_command_line_help")
        self.assertTaxonomyMetadata(help_result, "understood_and_answered")
        self.assertIn("LINE", help_result["assistant_message"])
        self.assertIn("manual_drawn", help_result["assistant_message"])
        self.assertIn("draft_review_required", help_result["assistant_message"])
        self.assertFalse(help_result["response_metadata"]["state_changed"])
        self.assertEqual(blocked_result["action_taken"], "answered_cad_command_line_blocked_reason")
        self.assertTaxonomyMetadata(blocked_result, "understood_needs_more_info")
        self.assertIn("selected", blocked_result["assistant_message"].lower())
        self.assertIn("20,0", blocked_result["assistant_message"])
        self.assertNotIn("construction-ready", blocked_result["assistant_message"].lower())
        self.assertFalse(blocked_result["response_metadata"]["state_changed"])


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

    def test_plan_pdf_vague_edit_requires_exact_replacement(self):
        record = _record()
        record["latest_result"]["final_plan"]["meta"]["plan_pdf_analysis_v1"] = {
            "version": "plan_pdf_analysis_v1",
            "page_count": 1,
            "source_confidence": SOURCE_CONFIDENCE,
            "summary": {"elevation_callout_count": 1},
            "source_pdf": {"filename": "Pool Geometric.pdf"},
            "blockers": ["vector_geometry_extraction_blocked:no_vector_parser_configured"],
        }
        record["latest_result"]["final_plan"]["meta"]["plan_pdf_editable_sheet_v1"] = {
            "version": "plan_pdf_editable_sheet_v1",
            "review_required": True,
            "construction_release_allowed": False,
            "elements": [
                {
                    "element_id": "pse_pool_elevation",
                    "type": "elevation_callout",
                    "text": "POOL DECK ELEVATION 102.50",
                    "original_text": "POOL DECK ELEVATION 102.50",
                    "bbox": {"x0": 72, "y0": 680, "x1": 260, "y1": 692},
                    "review_status": "pending",
                    "review_required": True,
                    "source_confidence": SOURCE_CONFIDENCE,
                    "editable": True,
                    "construction_release_allowed": False,
                }
            ],
            "summary": {"element_count": 1, "editable_count": 1},
        }
        store = RecordingProjectStore(record)

        result = decide_chat(
            {"message": "change pool deck elevation", "context": {"current_project": {"project_id": "project_123"}}},
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "blocked_pdf_edit_missing_replacement")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("exact replacement", result["assistant_message"])
        self.assertIn(SOURCE_CONFIDENCE, result["assistant_message"])

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

    def test_chat_explains_real_survey_control_package_status(self):
        store = RecordingProjectStore(
            _record()
            | {
                "latest_result": {
                    "success": True,
                    "final_plan": {
                        "meta": {
                            "survey_control_package": {
                                "status": "blocked",
                                "blockers": [{"field": "survey_control_verified"}],
                            },
                        }
                    },
                }
            }
        )

        result = decide_chat(
            {
                "message": "explain survey control status",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertIn("Survey control package", result["assistant_message"])
        self.assertIn("survey_control_verified", result["assistant_message"])
        self.assertIn("exact fix", result["assistant_message"])

    def test_chat_answers_source_confidence_questions(self):
        record = _record_with_handoffs([_handoff(object_id="drawn-source-1")])
        record["latest_result"]["final_plan"]["meta"].update(
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
            }
        )
        store = RecordingProjectStore(record)

        for prompt, expected in (
            ("what can I trust?", "does not imply field-use readiness"),
            ("why is this low confidence?", "Low confidence sources"),
            ("what is user drawn?", "Drawn polygon"),
            ("what needs survey control?", "Needs survey control"),
            ("show me stale or missing sources", "Stale output: grading"),
        ):
            result = decide_chat(
                {
                    "message": prompt,
                    "context": {"current_project": {"project_id": "project_123"}},
                },
                decide_chat_message=decide_chat_message,
                project_store=store,
                user_id="user_1",
            )

            self.assertEqual(result["action_taken"], "reported_source_confidence_map")
            self.assertIn(expected, result["assistant_message"])
            command_payload = result["response_metadata"]["command_payload"]
            self.assertEqual(command_payload["source_confidence_map_v1"]["version"], "source_confidence_map_v1")
            self.assertEqual(command_payload["requested_ui_mode"], "data")

    def test_chat_explains_cost_pricing_blockers(self):
        store = RecordingProjectStore(
            _record()
            | {
                "latest_result": {
                    "success": True,
                    "final_plan": {
                        "meta": {
                            "production_evidence": {
                                "quantity_cost": {
                                    "ready": False,
                                    "blockers": [{"field": "approved_cost_source"}],
                                },
                            },
                        }
                    },
                }
            }
        )

        result = decide_chat(
            {
                "message": "what is the cost pricing status?",
                "context": {"current_project": {"project_id": "project_123"}},
            },
            decide_chat_message=decide_chat_message,
            project_store=store,
            user_id="user_1",
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertIn("Cost book / pricing", result["assistant_message"])
        self.assertIn("approved_cost_source", result["assistant_message"])

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
        self.assertIn("Address / Location", result["assistant_message"])
        self.assertIn("Enter an address", result["assistant_message"])
        self.assertIn("Enter an address", result["response_metadata"]["next_best_action"])

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

    def test_chat_answers_progress_timeline_location_and_next_action(self):
        timeline = {
            "schema_version": "progress_timeline_v1",
            "current_step_id": "candidates",
            "current_step_label": "Candidates",
            "current_status": "needs_review",
            "current_panel": "data",
            "next_action": "Review candidates: Review pending source candidates before relying on them.",
            "exact_blockers": ["Review pending source candidates before relying on them."],
            "steps": [
                {"id": "setup", "label": "Setup", "status": "completed", "blockers": []},
                {
                    "id": "candidates",
                    "label": "Candidates",
                    "status": "needs_review",
                    "blockers": ["Review pending source candidates before relying on them."],
                },
                {"id": "deliverables", "label": "Deliverables", "status": "pending", "blockers": []},
            ],
            "chat_summary": {
                "where_am_i": "Candidates (needs_review)",
                "phase": "Candidates",
                "whats_left": ["Candidates", "Deliverables"],
                "what_should_i_do_next": "Review candidates: Review pending source candidates before relying on them.",
            },
        }

        result = decide_chat(
            {"message": "where am I?", "context": {"progress_timeline_v1": timeline}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("Candidates", result["assistant_message"])
        self.assertIn("Review pending source candidates", result["assistant_message"])

        result = decide_chat(
            {"message": "what's left?", "context": {"progress_timeline_v1": timeline}},
            decide_chat_message=decide_chat_message,
        )

        self.assertIn("Candidates, Deliverables", result["assistant_message"])

    def test_chat_answers_why_export_blocked_from_progress_timeline(self):
        timeline = {
            "schema_version": "progress_timeline_v1",
            "current_step_id": "review_package",
            "current_step_label": "Review Package",
            "current_status": "blocked",
            "current_panel": "reports",
            "next_action": "Open review package: accepted_standards_missing",
            "can_export": False,
            "export_blockers": ["accepted_standards_missing", "Missing deliverable: drainage_report"],
            "steps": [],
            "chat_summary": {
                "where_am_i": "Review Package (blocked)",
                "phase": "Review Package",
                "why_cant_export_yet": ["accepted_standards_missing", "Missing deliverable: drainage_report"],
                "what_should_i_do_next": "Open review package: accepted_standards_missing",
            },
        }

        result = decide_chat(
            {"message": "why can't I export yet?", "context": {"progress_timeline_v1": timeline}},
            decide_chat_message=decide_chat_message,
        )

        self.assertEqual(result["action_taken"], "answered_from_project_context")
        self.assertTaxonomyMetadata(result, "understood_and_executed")
        self.assertIn("accepted_standards_missing", result["assistant_message"])
        self.assertIn("Missing deliverable: drainage_report", result["assistant_message"])

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
