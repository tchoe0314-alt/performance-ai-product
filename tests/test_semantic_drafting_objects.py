from backend.planning.cad_entity_model import (
    CAD_ENGINEERING_OBJECTS_VERSION,
    attach_cad_entity_model_to_result,
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


def _project_handoff(
    object_id: str,
    object_type: str,
    geometry_type: str,
    points: list[tuple[float, float]],
):
    return {
        "schema_version": "canonical_geometry_handoff_v1",
        "object_id": object_id,
        "geometry_id": f"geometry-{object_id}",
        "object_name": object_id.replace("-", " ").title(),
        "object_type": object_type,
        "canonical_object_type": object_type,
        "geometry_type": geometry_type,
        "vertices": [
            {"id": f"{object_id}-v{index}", "x": x, "y": y, "units": "ft"}
            for index, (x, y) in enumerate(points)
        ],
        "units": "ft",
        "coordinate_system": "site_local_ft",
        "source": "manual_drawn",
        "confidence": "user_drawn_review_required",
        "engineering_status": "draft_review_required",
        "metrics": {},
        "source_ui_mode": "canvas_draw",
        "valid": True,
        "blockers": [],
    }


def test_saved_canvas_objects_converge_into_one_engineering_graph():
    project_input = {
        "manual_fields": {
            "canonical_geometry_handoff_v1": [
                _project_handoff("office-a", "office_building", "polygon", [(0, 0), (80, 0), (80, 60), (0, 60), (0, 0)]),
                _project_handoff("road-a", "road", "polyline", [(0, 100), (200, 100)]),
                _project_handoff("hydrant-a", "hydrant", "point", [(25, 90)]),
                _project_handoff("unclassified-a", "custom", "polygon", [(0, 0), (10, 0), (10, 10), (0, 0)]),
            ]
        }
    }

    model = build_cad_entity_model({}, project_input=project_input)
    objects = model[CAD_ENGINEERING_OBJECTS_VERSION]["objects"]
    by_type = {item["object_type"]: item for item in objects}

    assert set(by_type) == {"building", "road_centerline", "hydrant"}
    assert len(model["entities"]) == 4
    assert by_type["building"]["source_object_type"] == "office_building"
    assert "finished-floor elevation" in by_type["building"]["missing_inputs"]
    assert "fire_flow" in by_type["hydrant"]["affected_systems"]
    assert "roadway" in by_type["road_centerline"]["affected_systems"]

    graph = model["engineering_project_graph_v1"]
    assert graph["node_count"] == 3
    assert graph["edge_count"] > graph["node_count"]
    assert {"drainage", "roadway", "water", "fire_flow"}.issubset(set(graph["stale_systems"]))
    assert graph["construction_release_allowed"] is False

    linked_entities = [item for item in model["entities"] if item.get("linked_engineering_object_id")]
    assert len(linked_entities) == 3
    assert all(item["semantic_geometry_state"] == "engineering_object_geometry" for item in linked_entities)


def test_result_attachment_carries_canvas_object_graph_into_saved_plan():
    project_input = {
        "manual_fields": {
            "canonical_geometry_handoff_v1": [
                _project_handoff("parking-a", "parking", "polygon", [(0, 0), (120, 0), (120, 60), (0, 60), (0, 0)]),
            ]
        }
    }
    result = attach_cad_entity_model_to_result(
        {"final_plan": {"meta": {}}},
        project_input=project_input,
    )

    model = result["final_plan"]["meta"]["cad_entity_model_v1"]
    assert model[CAD_ENGINEERING_OBJECTS_VERSION]["object_count"] == 1
    assert model[CAD_ENGINEERING_OBJECTS_VERSION]["objects"][0]["object_type"] == "parking_area"
    assert "parking" in model["engineering_project_graph_v1"]["selective_rerun_candidates"]


def test_semantic_move_copy_and_delete_survive_model_rebuild_without_resurrection():
    project_input = {
        "manual_fields": {
            "canonical_geometry_handoff_v1": [
                _project_handoff("office-a", "office_building", "polygon", [(0, 0), (80, 0), (80, 60), (0, 60), (0, 0)]),
            ]
        }
    }
    model = build_cad_entity_model({}, project_input=project_input)
    entity_id = model["entities"][0]["id"]
    object_id = model[CAD_ENGINEERING_OBJECTS_VERSION]["objects"][0]["object_id"]

    moved_source, moved_result = apply_cad_entity_operation(
        model,
        {"action": "move_selected", "target_entity_ids": [entity_id], "dx": 25, "dy": 10},
        actor="tester",
    )
    assert object_id in moved_result["engineering_object_ids"]
    moved_model = build_cad_entity_model({"cad_entity_model_v1": moved_source}, project_input=project_input)
    moved_entity = next(item for item in moved_model["entities"] if item["id"] == entity_id)
    assert moved_entity["geometry"]["points"][0] == {"x": 25.0, "y": 10.0}
    assert moved_model["engineering_project_graph_v1"]["export_blocked_until_rerun"] is True
    assert moved_model["engineering_project_graph_v1"]["change_impacts"][0]["object_id"] == object_id

    copied_source, copied_result = apply_cad_entity_operation(
        moved_model,
        {"action": "copy_selected", "target_entity_ids": [entity_id], "dx": 100, "dy": 0},
        actor="tester",
    )
    assert len(copied_result["created_entity_ids"]) == 1
    assert len(copied_result["engineering_object_ids"]) == 1
    copied_model = build_cad_entity_model({"cad_entity_model_v1": copied_source}, project_input=project_input)
    assert copied_model[CAD_ENGINEERING_OBJECTS_VERSION]["object_count"] == 2

    deleted_source, deleted_result = apply_cad_entity_operation(
        copied_model,
        {"action": "delete_selected", "target_entity_ids": [entity_id]},
        actor="tester",
    )
    assert deleted_result["deleted_entity_ids"] == [entity_id]
    rebuilt = build_cad_entity_model({"cad_entity_model_v1": deleted_source}, project_input=project_input)
    assert entity_id in rebuilt["deleted_entity_ids"]
    assert object_id in rebuilt["deleted_engineering_object_ids"]
    assert all(item["id"] != entity_id for item in rebuilt["entities"])
    assert all(item["object_id"] != object_id for item in rebuilt[CAD_ENGINEERING_OBJECTS_VERSION]["objects"])
    assert rebuilt[CAD_ENGINEERING_OBJECTS_VERSION]["object_count"] == 1


def test_engineering_object_updates_preserve_history_and_scoped_impact():
    project_input = {
        "manual_fields": {
            "canonical_geometry_handoff_v1": [
                _project_handoff("office-a", "office_building", "polygon", [(0, 0), (80, 0), (80, 60), (0, 60), (0, 0)]),
            ]
        }
    }
    model = build_cad_entity_model({}, project_input=project_input)
    entity_id = model["entities"][0]["id"]
    object_id = model[CAD_ENGINEERING_OBJECTS_VERSION]["objects"][0]["object_id"]

    updated_source, result = apply_cad_entity_operation(
        model,
        {
            "action": "update_engineering_object",
            "target_entity_ids": [entity_id],
            "display_name": "Office Building A",
            "engineering_attributes": {"use_type": "office", "floor_count": 2, "finished_floor_elevation": 1042.5},
        },
        actor="tester",
    )

    assert result["safety_blockers"] == []
    assert result["engineering_object_ids"] == [object_id]
    rebuilt = build_cad_entity_model({"cad_entity_model_v1": updated_source}, project_input=project_input)
    updated = rebuilt[CAD_ENGINEERING_OBJECTS_VERSION]["objects"][0]
    assert updated["display_name"] == "Office Building A"
    assert updated["engineering_attributes"]["floor_count"] == 2
    assert updated["engineering_attributes"]["finished_floor_elevation"] == 1042.5
    assert updated["history"][-1]["action"] == "engineering_object_updated"
    assert rebuilt["engineering_project_graph_v1"]["change_impacts"][0]["changed_fields"] == [
        "display_name",
        "engineering_attributes",
    ]


def test_persistent_advanced_drafting_operations_preserve_geometry_and_history():
    polyline = normalize_cad_entity(
        {
            "id": "pline-a",
            "type": "polyline",
            "geometry": {
                "points": [
                    {"x": 10, "y": 10},
                    {"x": 60, "y": 10},
                    {"x": 60, "y": 50},
                ],
                "units": "ft",
            },
            "source": "manual_drawn",
            "source_confidence": "user_drawn_review_required",
        },
        created_by="tester",
    )
    model = build_cad_entity_model({"cad_entity_model_v1": {"entities": [polyline]}})

    filleted, result = apply_cad_entity_operation(
        model,
        {"action": "fillet_selected", "target_entity_ids": ["pline-a"], "radius_ft": 5, "vertex_index": 1},
        actor="tester",
    )
    assert result["safety_blockers"] == []
    assert result["updated_entity_ids"] == ["pline-a"]
    edited = next(item for item in filleted["entities"] if item["id"] == "pline-a")
    assert len(edited["geometry"]["points"]) == 4
    assert edited["curve_storage"] == "tangent_chord_vertices"

    offset, offset_result = apply_cad_entity_operation(
        filleted,
        {"action": "offset_selected", "target_entity_ids": ["pline-a"], "distance_ft": 8},
        actor="tester",
    )
    assert offset_result["safety_blockers"] == []
    assert len(offset_result["created_entity_ids"]) == 1
    offset_entity = next(item for item in offset["entities"] if item["id"] == offset_result["created_entity_ids"][0])
    assert offset_entity["offset_from_entity_id"] == "pline-a"
    assert offset_entity["offset_distance_ft"] == 8

    mirrored, mirror_result = apply_cad_entity_operation(
        offset,
        {"action": "mirror_selected", "target_entity_ids": ["pline-a"], "axis": "horizontal"},
        actor="tester",
    )
    assert mirror_result["updated_entity_ids"] == ["pline-a"]
    assert mirrored["history"][-1]["details"]["mirror_axis"] == "horizontal"
    mirrored_points = next(item for item in mirrored["entities"] if item["id"] == "pline-a")["geometry"]["points"]
    source_points = next(item for item in offset["entities"] if item["id"] == "pline-a")["geometry"]["points"]
    assert [point["x"] for point in mirrored_points] == [point["x"] for point in source_points]
    assert mirrored_points[0]["y"] == 50.0
    assert mirrored_points[-1]["y"] == 10.0

    vertical_mirror, vertical_result = apply_cad_entity_operation(
        offset,
        {"action": "mirror_selected", "target_entity_ids": ["pline-a"], "axis": "vertical"},
        actor="tester",
    )
    assert vertical_result["updated_entity_ids"] == ["pline-a"]
    vertical_points = next(item for item in vertical_mirror["entities"] if item["id"] == "pline-a")["geometry"]["points"]
    assert [point["y"] for point in vertical_points] == [point["y"] for point in source_points]
    assert vertical_points[0]["x"] == 60.0
    assert vertical_points[-1]["x"] == 10.0


def test_persistent_join_split_array_close_and_hatch_are_reversible_and_bounded():
    model = build_cad_entity_model(
        {
            "cad_entity_model_v1": {
                "entities": [
                    _line("line-a", (0, 0), (40, 0)),
                    _line("line-b", (40, 0), (40, 30)),
                    _line("line-c", (40, 30), (0, 30)),
                ]
            }
        }
    )

    joined, join_result = apply_cad_entity_operation(
        model,
        {"action": "join_selected", "target_entity_ids": ["line-a", "line-b", "line-c"]},
        actor="tester",
    )
    assert join_result["safety_blockers"] == []
    joined_id = join_result["created_entity_ids"][0]
    assert joined["selected_entity_ids"] == [joined_id]
    joined_entity = next(item for item in joined["entities"] if item["id"] == joined_id)
    assert joined_entity["joined_from_entity_ids"] == ["line-a", "line-b", "line-c"]

    closed, close_result = apply_cad_entity_operation(
        joined,
        {"action": "close_selected", "target_entity_ids": [joined_id]},
        actor="tester",
    )
    assert close_result["safety_blockers"] == []
    closed_entity = next(item for item in closed["entities"] if item["id"] == joined_id)
    assert closed_entity["type"] == "polygon"

    hatched, hatch_result = apply_cad_entity_operation(
        closed,
        {"action": "hatch_selected", "target_entity_ids": [joined_id], "pattern": "diagonal"},
        actor="tester",
    )
    assert hatch_result["safety_blockers"] == []
    assert next(item for item in hatched["entities"] if item["id"] == hatch_result["created_entity_ids"][0])["type"] == "hatch"

    arrayed, array_result = apply_cad_entity_operation(
        model,
        {"action": "array_selected", "target_entity_ids": ["line-a"], "rows": 2, "columns": 3, "spacing_x": 20, "spacing_y": 15},
        actor="tester",
    )
    assert array_result["safety_blockers"] == []
    assert len(array_result["created_entity_ids"]) == 5
    _, blocked_array = apply_cad_entity_operation(
        arrayed,
        {"action": "array_selected", "target_entity_ids": ["line-a"], "rows": 20, "columns": 20, "spacing_x": 5, "spacing_y": 5},
        actor="tester",
    )
    assert blocked_array["safety_blockers"] == ["array_entity_limit_exceeded:250"]

    split, split_result = apply_cad_entity_operation(
        joined,
        {"action": "split_joined", "target_entity_ids": [joined_id]},
        actor="tester",
    )
    assert split_result["deleted_entity_ids"] == [joined_id]
    assert split["selected_entity_ids"] == ["line-a", "line-b", "line-c"]
