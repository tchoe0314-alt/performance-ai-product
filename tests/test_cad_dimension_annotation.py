from backend.application.chat_workflows import decide_chat
from backend.planning.cad_entity_model import (
    CAD_ENTITY_MODEL_VERSION,
    apply_cad_entity_operation,
    build_cad_entity_model,
)
from backend.planning.export_package_report import build_export_package_report_v1
from parsers.chat_intent_parser import decide_chat_message


def _line(entity_id="cad-line-1", end_x=10):
    return {
        "id": entity_id,
        "type": "line",
        "geometry": {"start": {"x": 0, "y": 0}, "end": {"x": end_x, "y": 0}},
        "layer_id": "layer_draft",
        "style_id": "style_by_layer",
        "source": "manual_drawn",
        "source_confidence": "survey-backed",
        "review_status": "draft_review_required",
        "draft_review_required": True,
        "construction_release_allowed": False,
    }


def _record():
    return {
        "project_id": "project_123",
        "name": "Saved Project",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {},
        "latest_result": {
            "success": True,
            "final_plan": {
                "meta": {
                    "canonical_revision": "rev-1",
                    CAD_ENTITY_MODEL_VERSION: {
                        "entities": [_line()],
                        "selected_entity_ids": ["cad-line-1"],
                    },
                }
            },
        },
        "session_state": {},
        "metadata": {},
    }


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


def test_dimension_entity_records_measurement_and_review_flags():
    model = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: {"entities": [_line()]}})

    next_model, result = apply_cad_entity_operation(
        model,
        {
            "action": "create_dimension",
            "entity_type": "dimension",
            "dimension_type": "aligned",
            "target_entity_ids": ["cad-line-1"],
            "units": "ft",
            "precision": 2,
            "suffix": "'",
        },
        actor="user_1",
    )

    assert result["created_entity_ids"]
    dim = [entity for entity in next_model["entities"] if entity["type"] == "dimension"][0]
    assert dim["dimension"]["measured_entity_refs"] == ["cad-line-1"]
    assert dim["dimension"]["measurement_value"] == 10
    assert dim["dimension"]["units"] == "ft"
    assert dim["dimension"]["precision"] == 2
    assert dim["dimension"]["suffix"] == "'"
    assert dim["dimension"]["review_required"] is True
    assert dim["dimension"]["construction_release_allowed"] is False
    assert dim["construction_release_allowed"] is False


def test_dimension_marks_stale_when_measured_entity_changes():
    model = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: {"entities": [_line()]}})
    with_dimension, _ = apply_cad_entity_operation(
        model,
        {"action": "create_dimension", "entity_type": "dimension", "dimension_type": "aligned", "target_entity_ids": ["cad-line-1"]},
        actor="user_1",
    )

    moved, result = apply_cad_entity_operation(
        {**with_dimension, "selected_entity_ids": ["cad-line-1"]},
        {"action": "move_selected", "target_entity_ids": ["cad-line-1"], "dx": 5, "dy": 0},
        actor="user_1",
    )

    dim = [entity for entity in moved["entities"] if entity["type"] == "dimension"][0]
    assert dim["stale"] is True
    assert dim["dirty"] is True
    assert dim["review_status"] == "stale"
    assert dim["dimension"]["association_dirty_reason"] == "measured_cad_entity_changed_review_required"
    assert "engineering quantities" in dim["dimension"]["truth_label"]
    assert dim["id"] in result["updated_entity_ids"]


def test_annotation_entities_include_callout_note_label_records():
    model = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: {"entities": []}})

    next_model, result = apply_cad_entity_operation(
        model,
        {
            "action": "create_callout",
            "entity_type": "callout",
            "text": "Review inlet",
            "geometry": {"points": [{"x": 0, "y": 0}, {"x": 4, "y": 2}], "text": "Review inlet"},
        },
        actor="user_1",
    )

    assert result["created_entity_ids"]
    callout = next_model["entities"][0]
    assert callout["type"] == "callout"
    assert callout["annotation"]["annotation_type"] == "callout"
    assert callout["annotation"]["construction_release_allowed"] is False


def test_export_report_includes_dimension_annotation_trace():
    meta_model = {
        "entities": [
            _line(),
            {
                "id": "cad-label-1",
                "type": "label",
                "geometry": {"insert": {"x": 1, "y": 1}, "text": "Label"},
                "source_confidence": "survey-backed",
                "draft_review_required": True,
                "construction_release_allowed": False,
            },
        ],
        "selected_entity_ids": ["cad-line-1"],
    }
    model, _ = apply_cad_entity_operation(
        build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: meta_model}),
        {"action": "create_dimension", "entity_type": "dimension", "target_entity_ids": ["cad-line-1"]},
        actor="user_1",
    )
    plan = {
        "project_id": "project-1",
        "meta": {
            "project_id": "project-1",
            "canonical_revision": "rev-1",
            "canonical_model_hash": "hash-1",
            CAD_ENTITY_MODEL_VERSION: model,
        },
    }

    report = build_export_package_report_v1(plan, export_type="report", generated_at="2026-06-16T00:00:00Z")

    trace = report["cad_dimension_annotation_trace"]
    assert trace["dimension_count"] == 1
    assert trace["annotation_count"] == 1
    assert trace["construction_release_allowed"] is False


def test_chat_dimensions_callout_and_stale_dimension_answers():
    store = RecordingProjectStore()

    dimensioned = decide_chat(
        {
            "message": "dimension this line",
            "context": {"current_project": {"project_id": "project_123"}, "selected_cad_entity_ids": ["cad-line-1"]},
        },
        decide_chat_message=decide_chat_message,
        project_store=store,
        user_id="user_1",
    )
    assert dimensioned["action_taken"] == "executed_cad_entity_command"
    dim = [entity for entity in store.record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION]["entities"] if entity["type"] == "dimension"][0]
    assert dim["dimension"]["measured_entity_refs"] == ["cad-line-1"]

    callout = decide_chat(
        {
            "message": 'add callout "review this" from 0,0 to 5,5',
            "context": {"current_project": {"project_id": "project_123"}},
        },
        decide_chat_message=decide_chat_message,
        project_store=store,
        user_id="user_1",
    )
    assert callout["action_taken"] == "executed_cad_entity_command"

    updated = decide_chat(
        {
            "message": "move selected CAD entity by 5,0",
            "context": {"current_project": {"project_id": "project_123"}, "selected_cad_entity_ids": ["cad-line-1"]},
        },
        decide_chat_message=decide_chat_message,
        project_store=store,
        user_id="user_1",
    )
    assert updated["action_taken"] == "executed_cad_entity_command"

    why = decide_chat(
        {"message": "why is this dimension stale?", "context": {"current_project": {"project_id": "project_123"}}},
        decide_chat_message=decide_chat_message,
        project_store=store,
        user_id="user_1",
    )
    assert why["action_taken"] == "explained_stale_dimension_status"
    assert "review-only" in why["assistant_message"]

    refresh = decide_chat(
        {"message": "update stale dimensions", "context": {"current_project": {"project_id": "project_123"}}},
        decide_chat_message=decide_chat_message,
        project_store=store,
        user_id="user_1",
    )
    assert refresh["action_taken"] == "updated_stale_dimension_associations"
    assert "engineering quantities were not updated" in refresh["assistant_message"]
