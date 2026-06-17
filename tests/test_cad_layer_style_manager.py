from backend.application.chat_workflows import decide_chat
from backend.planning.cad_entity_model import (
    CAD_ENTITY_CHAT_OPERATION_VERSION,
    CAD_ENTITY_MODEL_VERSION,
    apply_cad_entity_operation,
    build_cad_entity_model,
)
from parsers.chat_intent_parser import decide_chat_message


def _entity(layer_id="layer_existing", style_id="style_by_layer"):
    return {
        "id": "cad-line-1",
        "type": "line",
        "geometry": {"start": {"x": 0, "y": 0}, "end": {"x": 10, "y": 0}},
        "layer_id": layer_id,
        "style_id": style_id,
        "source": "manual_drawn",
        "source_confidence": "survey-backed",
        "review_status": "draft_review_required",
        "draft_review_required": True,
        "construction_release_allowed": False,
    }


def _model():
    return {
        "layers": [
            {"layer_id": "layer_existing", "name": "Existing", "color": "#888888", "linetype": "DASHED", "lineweight": "0.25mm", "locked": False},
            {"layer_id": "layer_utilities", "name": "Utilities", "color": "#00aa66", "visible": True, "printable": False},
            {"layer_id": "layer_drainage", "name": "Drainage", "color": "#0066cc"},
        ],
        "styles": [
            {"style_id": "style_by_layer", "name": "By Layer", "entity_types_supported": ["line"], "lineweight": "by_layer"},
            {"style_id": "style_company", "name": "Company", "entity_types_supported": ["line"], "linetype": "DASHED"},
        ],
        "entities": [_entity()],
        "selected_entity_ids": ["cad-line-1"],
    }


def _record():
    return {
        "project_id": "project_123",
        "name": "Saved Project",
        "project_input": {"manual_fields": {}},
        "latest_result": {"success": True, "final_plan": {"meta": {CAD_ENTITY_MODEL_VERSION: _model()}}},
        "session_state": {},
        "metadata": {},
    }


class Store:
    def __init__(self):
        self.record = _record()
        self.saved = []

    def get_project(self, *, user_id, project_id):
        return self.record

    def save_project(self, **kwargs):
        self.saved.append(kwargs)
        self.record = {**self.record, "project_input": kwargs["project_input"], "latest_result": kwargs["latest_result"]}
        return self.record


def _chat(message, store=None):
    store = store or Store()
    return decide_chat(
        {"message": message, "context": {"current_project": {"project_id": "project_123"}}},
        decide_chat_message=decide_chat_message,
        project_store=store,
        user_id="user_1",
    )


def test_layer_style_registry_contract_visibility_and_printable_trace():
    model = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: _model()})

    utilities = next(layer for layer in model["layers"] if layer["id"] == "layer_utilities")
    assert utilities["layer_id"] == "layer_utilities"
    assert utilities["color"] == "#00aa66"
    assert utilities["linetype"] == "CONTINUOUS"
    assert utilities["lineweight"] == "0.18mm"
    assert utilities["visible"] is True
    assert utilities["locked"] is False
    assert utilities["printable"] is False
    assert utilities["review_required"] is True
    assert utilities["construction_release_allowed"] is False
    assert "layer_utilities" in model["sheet_export_trace"]["non_printable_layer_ids"]
    assert model["sheet_export_trace"]["construction_release_allowed"] is False

    style = next(item for item in model["styles"] if item["id"] == "style_company")
    assert style["style_id"] == "style_company"
    assert "line" in style["entity_types_supported"]
    assert style["defaults"]["linetype"] == "DASHED"
    assert style["review_required"] is True


def test_hidden_layer_marks_entity_render_metadata_without_engineering_release():
    source = _model()
    source["layers"][0]["visible"] = False
    model = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: source})

    entity = model["entities"][0]
    assert entity["render_metadata"]["visible"] is False
    assert entity["render_metadata"]["hidden_by_layer"] is True
    assert model["render_metadata"]["hidden_entity_ids"] == ["cad-line-1"]
    assert model["construction_release_allowed"] is False


def test_locked_layer_blocks_entity_edit_with_exact_blocker():
    source = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: _model()})
    next(layer for layer in source["layers"] if layer["id"] == "layer_existing")["locked"] = True

    next_model, result = apply_cad_entity_operation(
        source,
        {"action": "move_selected", "target_entity_ids": ["cad-line-1"], "dx": 1, "dy": 1},
        actor="user_1",
    )

    assert result["safety_blockers"] == ["locked_layer_prevents_cad_entity_edit:layer_existing"]
    assert result["updated_entity_ids"] == []
    assert next_model["entities"][0]["geometry"]["start"] == {"x": 0, "y": 0}


def test_entity_layer_and_style_assignments_update_model_and_history_events():
    source = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: _model()})

    layer_model, layer_result = apply_cad_entity_operation(
        source,
        {"action": "change_layer", "target_entity_ids": ["cad-line-1"], "layer_id": "layer_drainage"},
        actor="user_1",
    )
    style_model, style_result = apply_cad_entity_operation(
        layer_model,
        {"action": "change_style", "target_entity_ids": ["cad-line-1"], "style_id": "style_company"},
        actor="user_1",
    )

    assert layer_result["updated_entity_ids"] == ["cad-line-1"]
    assert style_result["updated_entity_ids"] == ["cad-line-1"]
    assert style_model["entities"][0]["layer_id"] == "layer_drainage"
    assert style_model["entities"][0]["style_id"] == "style_company"
    assert [event["event_type"] for event in style_model["history"][-2:]] == ["entity_layer_changed", "entity_style_changed"]


def test_customer_template_seeds_layers_styles_without_compliance_claim():
    template = {
        "template_id": "acme_template",
        "name": "ACME CAD",
        "firm_name": "ACME Civil",
        "source_reference": "internal://template.json",
        "sections": {
            "layer_standards": {"layers": [{"name": "C-UTIL", "color": "#00ff00", "lineweight": "0.30mm"}]},
            "annotation_standards": {"linetype_styles": [{"target": "utility", "linetype": "DASHED"}]},
        },
    }

    model = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: {"active_customer_template": template}})

    layer = next(item for item in model["layers"] if item["name"] == "C-UTIL")
    assert layer["source"] == "customer_template"
    assert layer["template_trace"]["customer_standard_only"] is True
    assert layer["template_trace"]["jurisdiction_compliance_claim"] is False
    style = next(item for item in model["styles"] if item["name"] == "utility")
    assert style["source"] == "customer_template"
    assert style["defaults"]["linetype"] == "DASHED"


def test_chat_layer_commands_answer_and_persist_registry_changes():
    store = Store()

    shown = _chat("show layers", store)
    assert shown["action_taken"] == "reported_cad_layers"
    assert "layer_utilities" in shown["assistant_message"]

    hidden = _chat("hide utilities layer", store)
    assert hidden["action_taken"] == "executed_cad_entity_command"
    op = hidden["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert op["selected_action"] == "set_layer_visibility"
    assert op["updated_layer_ids"] == ["layer_utilities"]
    saved_model = store.record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION]
    utilities = next(layer for layer in saved_model["layers"] if layer["id"] == "layer_utilities")
    assert utilities["visible"] is False
    assert saved_model["render_metadata"]["construction_release_allowed"] is False

    locked = _chat("lock existing layer", store)
    assert locked["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]["updated_layer_ids"] == ["layer_existing"]
    why = _chat("why can't I edit this layer?", store)
    assert why["action_taken"] == "explained_cad_layer_edit_blocker"
    assert why["response_metadata"]["blocker"] == "locked_layer_prevents_cad_entity_edit:layer_existing"


def test_chat_moves_selected_to_drainage_layer_and_uses_company_layer_style():
    store = Store()

    moved = _chat("move selected to drainage layer", store)
    op = moved["response_metadata"]["command_payload"][CAD_ENTITY_CHAT_OPERATION_VERSION]
    assert op["selected_action"] == "change_layer"
    assert op["updated_entity_ids"] == ["cad-line-1"]
    saved_model = store.record["latest_result"]["final_plan"]["meta"][CAD_ENTITY_MODEL_VERSION]
    assert saved_model["entities"][0]["layer_id"] == "layer_drainage"
    assert saved_model["history"][-1]["event_type"] == "entity_layer_changed"

    company = _chat("use my company layer style", store)
    assert company["action_taken"] == "executed_cad_entity_command"
    assert "construction_release_allowed=false" in company["assistant_message"]
