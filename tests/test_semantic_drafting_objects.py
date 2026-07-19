from backend.planning.cad_entity_model import (
    CAD_ENGINEERING_OBJECTS_VERSION,
    apply_cad_entity_operation,
    build_cad_entity_model,
    normalize_cad_entity,
    validate_closed_geometry,
)


def _line(entity_id: str, start: tuple[float, float], end: tuple[float, float]):
    return normalize_cad_entity(
        {
            "id": entity_id,
            "type": "line",
            "geometry": {"start": {"x": start[0], "y": start[1]}, "end": {"x": end[0], "y": end[1]}, "units": "ft"},
            "source": "manual_drawn",
            "source_confidence": "user_drawn_review_required",
            "review_status": "draft_review_required",
            "draft_review_required": True,
            "construction_release_allowed": False,
        },
        created_by="tester",
    )


def _rectangle_lines(gap: float = 0.0):
    return [
        _line("l1", (0, 0), (80, 0)),
        _line("l2", (80, 0), (80, 60)),
        _line("l3", (80, 60), (0, 60)),
        _line("l4", (0, 60), (gap, 0)),
    ]


def test_validate_closed_geometry_accepts_four_exact_lines_as_area():
    validation = validate_closed_geometry(_rectangle_lines(), ["l1", "l2", "l3", "l4"])

    assert validation["valid"] is True
    assert validation["geometry_kind"] == "area"
    assert validation["area_sf"] == 4800
    assert validation["point_count"] == 4
    assert validation["construction_release_allowed"] is False


def test_validate_closed_geometry_reports_small_gap_until_user_allows_snap():
    blocked = validate_closed_geometry(_rectangle_lines(gap=0.18), ["l1", "l2", "l3", "l4"], tolerance=0.25)

    assert blocked["valid"] is False
    assert "Small gap requires permission" in blocked["blockers"][0]
    assert blocked["suggested_actions"][0]["action"] == "close_gap"

    fixed = validate_closed_geometry(
        _rectangle_lines(gap=0.18),
        ["l1", "l2", "l3", "l4"],
        tolerance=0.25,
        close_gaps=True,
    )

    assert fixed["valid"] is True
    assert fixed["area_sf"] > 4790


def test_validate_closed_geometry_rejects_self_intersection_plainly():
    entities = [
        _line("l1", (0, 0), (40, 40)),
        _line("l2", (40, 40), (0, 40)),
        _line("l3", (0, 40), (40, 0)),
        _line("l4", (40, 0), (0, 0)),
    ]

    validation = validate_closed_geometry(entities, ["l1", "l2", "l3", "l4"])

    assert validation["valid"] is False
    assert "The selected shape crosses itself." in validation["blockers"]
    assert validation["suggested_actions"][0]["action"] == "show_conflict"


def test_combine_then_convert_selected_area_to_canonical_building_object():
    model = build_cad_entity_model({"cad_entity_model_v1": {"entities": _rectangle_lines(), "selected_entity_ids": ["l1", "l2", "l3", "l4"]}})

    combined_source, combined_result = apply_cad_entity_operation(
        model,
        {"action": "combine_selected_geometry", "target_entity_ids": ["l1", "l2", "l3", "l4"]},
        actor="tester",
    )

    assert combined_result["safety_blockers"] == []
    assert len(combined_result["combined_geometry_ids"]) == 1
    combined_id = combined_result["combined_geometry_ids"][0]
    assert combined_source["selected_entity_ids"] == [combined_id]
    combined_entity = next(item for item in combined_source["entities"] if item["id"] == combined_id)
    assert combined_entity["semantic_geometry_state"] == "combined_geometry"

    converted_source, converted_result = apply_cad_entity_operation(
        combined_source,
        {
            "action": "convert_geometry_to_engineering_object",
            "target_entity_ids": [combined_id],
            "object_type": "building",
            "display_name": "Office Building A",
            "attributes": {"use_type": "office", "floor_count": 1},
        },
        actor="tester",
    )

    assert converted_result["safety_blockers"] == []
    assert len(converted_result["engineering_object_ids"]) == 1
    object_id = converted_result["engineering_object_ids"][0]
    final_model = build_cad_entity_model({"cad_entity_model_v1": converted_source})
    objects = final_model[CAD_ENGINEERING_OBJECTS_VERSION]["objects"]
    building = next(item for item in objects if item["object_id"] == object_id)
    assert building["object_type"] == "building"
    assert building["display_name"] == "Office Building A"
    assert building["geometry_entity_id"] == combined_id
    assert building["engineering_attributes"]["footprint_area_sf"] == 4800
    assert "drainage" in building["affected_systems"]
    assert "water" in building["affected_systems"]
    assert building["review_required"] is True
    assert building["construction_release_allowed"] is False
    linked_entity = next(item for item in final_model["entities"] if item["id"] == combined_id)
    assert linked_entity["linked_engineering_object_id"] == object_id
    assert linked_entity["canonical_object_type"] == "building"


def test_path_conversion_rejects_area_only_building_choice():
    model = build_cad_entity_model({"cad_entity_model_v1": {"entities": [_line("l1", (0, 0), (80, 0))], "selected_entity_ids": ["l1"]}})

    _, result = apply_cad_entity_operation(
        model,
        {"action": "convert_geometry_to_engineering_object", "target_entity_ids": ["l1"], "object_type": "building"},
        actor="tester",
    )

    assert result["engineering_object_ids"] == []
    assert result["safety_blockers"] == ["unsupported_conversion:building_requires_closed area"]
