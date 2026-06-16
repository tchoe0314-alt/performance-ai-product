from backend.planning.cad_entity_model import (
    CAD_ENTITY_MODEL_VERSION,
    build_cad_entity_model,
    cad_entities_to_site_object_candidates,
    hit_test_entities,
    import_candidates_to_cad_entities,
    manual_drawn_objects_to_cad_entities,
    validate_cad_entity,
)


def _handoff():
    return {
        "schema_version": "canonical_geometry_handoff_v1",
        "object_id": "drawn-1",
        "geometry_id": "geom-1",
        "object_name": "Drawn polygon",
        "object_type": "custom",
        "geometry_type": "polygon",
        "vertices": [
            {"x": 0, "y": 0},
            {"x": 40, "y": 0},
            {"x": 40, "y": 30},
            {"x": 0, "y": 30},
        ],
        "units": "ft",
        "source": "manual_drawn",
        "confidence": "user_drawn_review_required",
        "engineering_status": "draft_review_required",
        "valid": True,
    }


def test_manual_drawn_handoff_converts_to_review_only_cad_entity():
    project_input = {"manual_fields": {"canonical_geometry_handoff_v1": [_handoff()]}}

    entities = manual_drawn_objects_to_cad_entities(project_input, created_by="user_1")

    assert len(entities) == 1
    entity = entities[0]
    assert entity["type"] == "polygon"
    assert entity["linked_object_id"] == "drawn-1"
    assert entity["draft_review_required"] is True
    assert entity["construction_release_allowed"] is False
    assert entity["dirty"] is True
    assert entity["canonical_geometry_handoff"]["geometry_id"] == "geom-1"


def test_model_normalizes_layers_styles_selection_bboxes_and_blockers():
    meta = {
        CAD_ENTITY_MODEL_VERSION: {
            "entities": [
                {
                    "id": "cad-line-1",
                    "type": "line",
                    "geometry": {"start": {"x": 0, "y": 0}, "end": {"x": 10, "y": 0}},
                    "layer_id": "missing-layer",
                    "style_id": "missing-style",
                    "source": "manual_drawn",
                    "source_confidence": "user_drawn_review_required",
                    "review_status": "draft_review_required",
                    "draft_review_required": True,
                    "construction_release_allowed": False,
                }
            ],
            "selected_entity_ids": ["cad-line-1", "not-present"],
        }
    }

    model = build_cad_entity_model(meta)

    assert model["version"] == CAD_ENTITY_MODEL_VERSION
    assert model["entities"][0]["layer_id"] == "missing-layer"
    assert model["selected_entity_ids"] == ["cad-line-1"]
    assert model["entity_bounding_boxes"]["cad-line-1"]["max_x"] == 10
    assert model["validation"]["valid"] is False
    reasons = [item["reason"] for item in model["validation"]["blockers"]]
    assert "source_confidence_blocker:user_drawn_review_required" in reasons
    assert model["construction_release_allowed"] is False


def test_validation_blocks_self_intersection_and_construction_release():
    entity = {
        "id": "cad-poly-1",
        "type": "polygon",
        "geometry": {
            "points": [
                {"x": 0, "y": 0},
                {"x": 10, "y": 10},
                {"x": 0, "y": 10},
                {"x": 10, "y": 0},
            ]
        },
        "layer_id": "layer_draft",
        "style_id": "style_by_layer",
        "source_confidence": "survey-backed",
        "draft_review_required": True,
        "construction_release_allowed": True,
        "review_status": "draft_review_required",
    }

    result = validate_cad_entity(entity, known_layer_ids=["layer_draft"], known_style_ids=["style_by_layer"])

    assert result["valid"] is False
    assert "self_intersection" in result["blockers"]
    assert "construction_release_blocked" in result["blockers"]


def test_imported_candidates_are_review_required_cad_entities_only():
    entities = import_candidates_to_cad_entities(
        [{"file_name": "plan.pdf", "geometry": {"origin": {"x": 0, "y": 0}, "width": 100, "height": 80}}],
        source="pdf_import",
    )

    assert entities[0]["type"] == "underlay_reference"
    assert entities[0]["review_status"] == "imported_review_required"
    assert entities[0]["construction_release_allowed"] is False
    assert entities[0]["dirty"] is True


def test_hit_test_and_site_object_candidate_conversion_stay_review_required():
    meta = {
        CAD_ENTITY_MODEL_VERSION: {
            "entities": [
                {
                    "id": "cad-rect-1",
                    "type": "rectangle",
                    "geometry": {"origin": {"x": 0, "y": 0}, "width": 20, "height": 10},
                    "source_confidence": "survey-backed",
                    "review_status": "draft_review_required",
                    "draft_review_required": True,
                    "construction_release_allowed": False,
                }
            ]
        }
    }
    model = build_cad_entity_model(meta)

    assert hit_test_entities(model["entities"], {"x": 5, "y": 5}) == ["cad-rect-1"]
    candidates = cad_entities_to_site_object_candidates(model)
    assert candidates[0]["cad_entity_id"] == "cad-rect-1"
    assert candidates[0]["draft_review_required"] is True
    assert candidates[0]["construction_release_allowed"] is False
