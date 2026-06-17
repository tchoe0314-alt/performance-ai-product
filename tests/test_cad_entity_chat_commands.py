from backend.application.chat_workflows import decide_chat
from backend.planning.cad_entity_model import CAD_ENTITY_CHAT_OPERATION_VERSION, CAD_ENTITY_MODEL_VERSION
from parsers.chat_intent_parser import decide_chat_message


def _record():
    return {
        "project_id": "project_123",
        "name": "Saved Project",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {"project_type": "mixed_use", "manual_fields": {}},
        "latest_result": {"success": True, "final_plan": {"meta": {}}},
        "session_state": {},
        "metadata": {},
    }


def _record_with_line():
    record = _record()
    record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION] = {
        "entities": [
            {
                "id": "cad-line-1",
                "type": "line",
                "geometry": {"start": {"x": 0, "y": 0}, "end": {"x": 10, "y": 0}},
                "source": "manual_drawn",
                "source_confidence": "user_drawn_review_required",
                "review_status": "draft_review_required",
                "draft_review_required": True,
                "construction_release_allowed": False,
            }
        ],
        "selected_entity_ids": ["cad-line-1"],
    }
    return record


class RecordingProjectStore:
    def __init__(self, record):
        self.record = record
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


def _chat(message, store, context=None):
    return decide_chat(
        {
            "message": message,
            "context": {
                "current_project": {"project_id": "project_123"},
                **(context or {}),
            },
        },
        decide_chat_message=decide_chat_message,
        project_store=store,
        user_id="user_1",
    )


def test_chat_creates_line_in_persistent_cad_entity_model():
    store = RecordingProjectStore(_record())

    result = _chat("create line from 0,0 to 25,0", store)

    assert result["action_taken"] == "executed_cad_entity_command"
    operation = result["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert operation["selected_action"] == "create_line"
    assert operation["review_required"] is True
    assert operation["construction_release_allowed"] is False
    assert len(operation["created_entity_ids"]) == 1
    saved_model = store.record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION]
    entity = saved_model["entities"][0]
    assert entity["type"] == "line"
    assert entity["geometry"]["end"]["x"] == 25.0
    assert entity["source"] == "chat_cad_command"
    assert entity["construction_release_allowed"] is False


def test_chat_moves_selected_cad_entity_and_marks_it_stale_review_required():
    store = RecordingProjectStore(_record_with_line())

    result = _chat("move selected CAD entity by 5,2", store)

    operation = result["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert operation["selected_action"] == "move_selected"
    assert operation["target_entities"] == ["cad-line-1"]
    assert operation["updated_entity_ids"] == ["cad-line-1"]
    saved_entity = store.record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION]["entities"][0]
    assert saved_entity["geometry"]["start"] == {"x": 5.0, "y": 2.0}
    assert saved_entity["geometry"]["end"] == {"x": 15.0, "y": 2.0}
    assert saved_entity["review_status"] == "stale"
    assert saved_entity["construction_release_allowed"] is False


def test_chat_reports_selected_cad_entity_ids_and_grips():
    store = RecordingProjectStore(_record_with_line())

    result = _chat("what is selected?", store)

    assert result["action_taken"] == "reported_selected_cad_entities"
    assert "cad-line-1" in result["assistant_message"]
    model = result["response_metadata"]["command_payload"][CAD_ENTITY_MODEL_VERSION]
    assert model["selection"]["selected_entity_ids"] == ["cad-line-1"]
    assert [grip["grip_id"] for grip in model["selection"]["grips"]] == ["start", "end", "midpoint"]


def test_chat_moves_selected_grip_and_records_geometry_event():
    store = RecordingProjectStore(_record_with_line())

    result = _chat(
        "move this grip by 5,2",
        store,
        {"selected_cad_entity_ids": ["cad-line-1"], "selected_cad_grip_entity_id": "cad-line-1", "selected_cad_grip_id": "end"},
    )

    operation = result["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert operation["selected_action"] == "move_grip"
    assert operation["updated_entity_ids"] == ["cad-line-1"]
    saved_model = store.record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION]
    saved_entity = saved_model["entities"][0]
    assert saved_entity["geometry"]["end"] == {"x": 15.0, "y": 2.0}
    assert saved_model["history"][-1]["event_type"] == "entity_geometry_changed"
    assert saved_entity["draft_review_required"] is True
    assert saved_entity["construction_release_allowed"] is False


def test_chat_explains_grip_blocker_for_locked_reference_entity():
    record = _record_with_line()
    record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION]["entities"][0]["locked"] = True
    store = RecordingProjectStore(record)

    result = _chat("why can't I edit this grip?", store)

    assert result["action_taken"] == "explained_cad_grip_edit_blocker"
    assert "locked/reference/underlay entity" in result["assistant_message"]
    assert result["response_metadata"]["blocker"] == "locked/reference/underlay entity"


def test_chat_deletes_selected_cad_objects_review_only():
    store = RecordingProjectStore(_record_with_line())

    result = _chat("delete selected CAD objects", store)

    operation = result["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert operation["selected_action"] == "delete_selected"
    assert operation["deleted_entity_ids"] == ["cad-line-1"]
    saved_model = store.record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION]
    assert saved_model["entities"] == []
    assert saved_model["history"][-1]["event_type"] == "entity_deleted"
    assert saved_model["construction_release_allowed"] is False


def test_chat_asks_specific_question_for_ambiguous_line_command_without_mutating():
    store = RecordingProjectStore(_record())

    result = _chat("create a CAD line", store)

    operation = result["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert result["action_taken"] == "asked_cad_entity_command_clarifying_question"
    assert operation["missing_inputs"] == ["line start point", "line end point"]
    assert operation["created_entity_ids"] == []
    assert store.saved == []
    assert "line start point" in result["assistant_message"]


def test_chat_blocks_cad_stamp_or_construction_release_request():
    store = RecordingProjectStore(_record_with_line())

    result = _chat("move selected CAD entity by 1,1 and stamp it", store)

    operation = result["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert result["action_taken"] == "blocked_cad_entity_command"
    assert operation["safety_blockers"] == ["chat_cad_commands_cannot_stamp_seal_certify_approve_submit_or_act_as_engineer_of_record"]
    assert operation["review_required"] is True
    assert operation["construction_release_allowed"] is False
    assert store.saved == []


def test_chat_reports_unsupported_persistent_cad_entity_command_with_reason():
    store = RecordingProjectStore(_record_with_line())

    result = _chat("trim selected CAD entity", store)

    operation = result["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert result["action_taken"] == "blocked_cad_entity_command"
    assert operation["safety_blockers"] == ["unsupported_persistent_cad_entity_command:trim"]
    assert "not run" in result["assistant_message"]
    assert store.saved == []
