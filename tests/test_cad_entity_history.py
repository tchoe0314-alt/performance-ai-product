from backend.planning.cad_entity_model import (
    CAD_ENTITY_MODEL_VERSION,
    build_cad_entity_model,
    build_cad_history_snapshot,
    history_event,
)


def _entity(entity_id="cad-line-1", *, end_x=10, dirty=False):
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
        "dirty": dirty,
    }


def test_history_event_contract_is_review_only_and_summarized():
    before = _entity(end_x=10)
    after = _entity(end_x=25, dirty=True)

    event = history_event(
        "entity_geometry_changed",
        "cad-line-1",
        actor="user_1",
        before=before,
        after=after,
    )

    assert event["event_id"].startswith("cadevt_")
    assert event["entity_id"] == "cad-line-1"
    assert event["event_type"] == "entity_geometry_changed"
    assert event["timestamp"]
    assert event["actor"] == "user_1"
    assert event["before_summary"]["type"] == "line"
    assert event["after_summary"]["dirty"] is True
    assert "geometry" in event["changed_fields"]
    assert event["review_required"] is True
    assert event["construction_release_allowed"] is False


def test_revision_timeline_counts_changed_stale_invalid_and_removed_entities():
    valid_dirty = _entity("cad-line-1", dirty=True)
    invalid = {
        **_entity("cad-bad-1"),
        "type": "polygon",
        "geometry": {"points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]},
        "source_confidence": "missing",
    }
    meta = {
        "canonical_revision": "rev-42",
        CAD_ENTITY_MODEL_VERSION: {
            "entities": [valid_dirty, invalid],
            "history": [
                history_event("entity_created", "cad-line-1", actor="user_1", after=valid_dirty),
                history_event("entity_deleted", "cad-old-1", actor="user_1", before=_entity("cad-old-1")),
            ],
        },
    }

    model = build_cad_entity_model(meta)
    timeline = model["revision_timeline"]

    assert timeline["latest_revision_id"] == "rev-42"
    assert timeline["entity_counts"]["total"] == 2
    assert timeline["entity_counts"]["invalid"] == 1
    assert timeline["entity_counts"]["stale_or_dirty"] == 1
    assert timeline["changed_entities"] == ["cad-line-1", "cad-old-1"]
    assert timeline["added_entities"] == ["cad-line-1"]
    assert timeline["removed_entities"] == ["cad-old-1"]
    assert "cad-line-1" in timeline["stale_dirty_entities"]
    assert "cad-bad-1" in timeline["invalid_entities"]
    assert timeline["construction_release_allowed"] is False
    assert model["history"][0]["review_required"] is True


def test_history_snapshots_expose_safe_undo_hook_without_release():
    source_model = build_cad_entity_model({CAD_ENTITY_MODEL_VERSION: {"entities": [_entity()]}})
    snapshot = build_cad_history_snapshot(source_model, actor="user_1", revision_id="rev-before-edit")

    model = build_cad_entity_model(
        {
            CAD_ENTITY_MODEL_VERSION: {
                "entities": [_entity(end_x=25, dirty=True)],
                "history_snapshots": [snapshot],
            }
        }
    )

    assert model["undo_redo"]["can_undo"] is True
    assert model["undo_redo"]["latest_undo_snapshot_id"] == snapshot["snapshot_id"]
    assert model["history_snapshots"][0]["revision_id"] == "rev-before-edit"
    assert model["history_snapshots"][0]["construction_release_allowed"] is False
