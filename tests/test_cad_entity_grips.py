from backend.planning.cad_entity_model import (
    CAD_ENTITY_MODEL_VERSION,
    apply_cad_entity_operation,
    build_cad_entity_model,
    entity_grip_points,
    hit_test_entities,
    window_select_entities,
)


def _entity(entity_id="cad-line-1", entity_type="line", geometry=None, **extra):
    if geometry is None:
        geometry = {"start": {"x": 0, "y": 0}, "end": {"x": 10, "y": 0}}
    return {
        "id": entity_id,
        "type": entity_type,
        "geometry": geometry,
        "layer_id": "layer_draft",
        "style_id": "style_by_layer",
        "source": "manual_drawn",
        "source_confidence": "survey-backed",
        "review_status": "draft_review_required",
        "draft_review_required": True,
        "construction_release_allowed": False,
        **extra,
    }


def test_grip_points_cover_core_entity_types_and_selected_model_feedback():
    model = build_cad_entity_model(
        {
            CAD_ENTITY_MODEL_VERSION: {
                "entities": [
                    _entity("cad-line-1"),
                    _entity("cad-poly-1", "polyline", {"points": [{"x": 0, "y": 0}, {"x": 5, "y": 5}]}),
                    _entity("cad-rect-1", "rectangle", {"origin": {"x": 0, "y": 0}, "width": 20, "height": 10}),
                    _entity("cad-circle-1", "circle", {"center": {"x": 5, "y": 5}, "radius": 3}),
                    _entity("cad-text-1", "text", {"insert": {"x": 2, "y": 2}, "text": "FFE"}),
                    _entity("cad-dim-1", "dimension", {"start": {"x": 0, "y": 0}, "end": {"x": 8, "y": 0}, "points": [{"x": 0, "y": 0}, {"x": 8, "y": 0}]}, dimension={"dimension_type": "linear", "measurement_value": 8}),
                    _entity("cad-block-1", "block_reference", {"insert": {"x": 7, "y": 7}}),
                ],
                "selected_entity_ids": ["cad-line-1", "cad-rect-1", "cad-circle-1"],
            }
        }
    )

    assert [grip["grip_id"] for grip in entity_grip_points(model["entities"][0])] == ["start", "end", "midpoint"]
    assert "corner:nw" in [grip["grip_id"] for grip in entity_grip_points(model["entities"][2])]
    assert "edge:e" in [grip["grip_id"] for grip in entity_grip_points(model["entities"][2])]
    assert "radius:e" in [grip["grip_id"] for grip in entity_grip_points(model["entities"][3])]
    assert "insert" in [grip["grip_id"] for grip in entity_grip_points(model["entities"][4])]
    assert "start" in [grip["grip_id"] for grip in entity_grip_points(model["entities"][5])]
    assert "insert" in [grip["grip_id"] for grip in entity_grip_points(model["entities"][6])]
    assert model["selection"]["selected_entity_ids"] == ["cad-line-1", "cad-rect-1", "cad-circle-1"]
    assert model["selection"]["grips"]
    assert model["selection"]["grip_feedback"].startswith("Grip edits are drafting/review actions only")


def test_hit_test_and_window_selection_return_persistent_entity_ids():
    entities = [
        _entity("cad-line-1"),
        _entity("cad-rect-1", "rectangle", {"origin": {"x": 30, "y": 30}, "width": 10, "height": 10}),
    ]

    assert hit_test_entities(entities, {"x": 5, "y": 0}) == ["cad-line-1"]
    assert window_select_entities(entities, {"start": {"x": 25, "y": 25}, "end": {"x": 45, "y": 45}}) == ["cad-rect-1"]


def test_move_grip_stretches_line_records_geometry_history_and_keeps_review_required():
    source = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: {"entities": [_entity()], "selected_entity_ids": ["cad-line-1"]}})

    next_model, result = apply_cad_entity_operation(
        source,
        {"action": "move_grip", "target_entity_ids": ["cad-line-1"], "entity_id": "cad-line-1", "grip_id": "end", "point": {"x": 15, "y": 5}},
        actor="user_1",
    )

    assert result["updated_entity_ids"] == ["cad-line-1"]
    assert result["safety_blockers"] == []
    entity = next_model["entities"][0]
    assert entity["geometry"]["end"] == {"x": 15.0, "y": 5.0}
    assert entity["dirty"] is True
    assert entity["stale"] is True
    assert entity["draft_review_required"] is True
    assert entity["construction_release_allowed"] is False
    assert next_model["history"][-1]["event_type"] == "entity_geometry_changed"


def test_move_grip_blocks_self_intersection_and_locked_underlay_exact_reasons():
    polygon = _entity(
        "cad-poly-1",
        "polygon",
        {"points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}, {"x": 0, "y": 10}], "closed": True},
    )
    source = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: {"entities": [polygon]}})

    _, result = apply_cad_entity_operation(
        source,
        {"action": "move_grip", "target_entity_ids": ["cad-poly-1"], "entity_id": "cad-poly-1", "grip_id": "vertex:2", "point": {"x": 5, "y": -5}},
        actor="user_1",
    )

    assert result["safety_blockers"] == ["self-intersection"]

    underlay = _entity("cad-underlay-1", "underlay_reference", {"origin": {"x": 0, "y": 0}}, source="underlay")
    source = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: {"entities": [underlay]}})

    _, blocked = apply_cad_entity_operation(
        source,
        {"action": "move_grip", "target_entity_ids": ["cad-underlay-1"], "entity_id": "cad-underlay-1", "grip_id": "insert", "point": {"x": 2, "y": 2}},
        actor="user_1",
    )

    assert blocked["safety_blockers"] == ["locked/reference/underlay entity"]


def test_delete_selected_removes_entity_and_records_deleted_history():
    source = build_cad_entity_model(
        {CAD_ENTITY_MODEL_VERSION: {"entities": [_entity("cad-line-1"), _entity("cad-line-2")], "selected_entity_ids": ["cad-line-1", "cad-line-2"]}}
    )

    next_model, result = apply_cad_entity_operation(
        source,
        {"action": "delete_selected", "target_entity_ids": ["cad-line-1"]},
        actor="user_1",
    )

    assert result["deleted_entity_ids"] == ["cad-line-1"]
    assert [entity["id"] for entity in next_model["entities"]] == ["cad-line-2"]
    assert next_model["selected_entity_ids"] == ["cad-line-2"]
    assert next_model["history"][-1]["event_type"] == "entity_deleted"
    assert next_model["history"][-1]["construction_release_allowed"] is False
