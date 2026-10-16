import json
from copy import deepcopy
from backend.services.auth_store import AuthStore
from backend.services.database import Database
from backend.services.project_store import ProjectStore
from backend.services.canonical_canvas import with_canvas_snapshot, resolve_canvas_input


def test_active_storage_avoids_duplicate_projections_and_reopens_losslessly(tmp_path):
    db = Database(tmp_path / "storage.db")
    user = AuthStore(db).register_user(email="storage@example.test", password="Synthetic-only-123", name="Storage")["user"]["user_id"]
    store = ProjectStore(db)
    inputs = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [
        {"id": str(index), "type": "office_building", "x": index * 20, "y": 0, "w": 10, "d": 10}
        for index in range(20)]}, "meta": {"site_inputs": {"source": "synthetic"}},
        "custom_input": {"preserve": [1, 2, 3]}})
    saved = store.save_project(user_id=user, project_id=None, name="Storage", project_input=inputs)
    for index in range(3):
        current = store.get_project(user_id=user, project_id=saved["project_id"])
        changed = deepcopy(current["project_input"])
        changed["manual_fields"]["site_objects"][0]["x"] = index + 1
        changed = with_canvas_snapshot(changed)
        saved = store.save_project_shell(user_id=user, project_id=saved["project_id"], name="Storage",
            project_input=changed, expected_revision=current["revision_token"])
    connection = db.connect()
    try:
        raw = connection.execute("SELECT project_input_json FROM projects WHERE project_id = ?", (saved["project_id"],)).fetchone()["project_input_json"]
    finally:
        connection.close()
    stored = json.loads(raw)
    reopened = ProjectStore(db).get_project(user_id=user, project_id=saved["project_id"])
    assert resolve_canvas_input(stored) == reopened["project_input"]
    assert reopened["project_input"] == saved["project_input"]
    assert reopened["revision_token"] == saved["revision_token"]
    assert len(reopened["project_input"]["meta"]["edit_history_v1"]["transactions"]) == 3
    assert reopened["project_input"]["custom_input"] == {"preserve": [1, 2, 3]}
    assert set(stored) == {"canonical_project_v1"}
    hydrated_bytes = len(json.dumps(reopened["project_input"], separators=(",", ":")).encode())
    assert len(raw.encode()) < hydrated_bytes * 0.8
    print({"stored_bytes": len(raw.encode()), "hydrated_bytes": hydrated_bytes,
           "saved_percent": round(100 * (1 - len(raw.encode()) / hydrated_bytes), 2)})


def test_legacy_and_non_reconstructable_inputs_are_retained_without_mutation():
    from backend.services.canonical_record import storage_project_input, OWNER
    from backend.services.canonical_project import new_project_document
    legacy = {"manual_fields": {"custom": [1, 2, 3]}, "extension": {"preserve": True}}
    document = new_project_document()
    document["extensions"][OWNER] = {"version": 1, "input_controls": {}, "input_meta": {}}
    adopted_without_manual_adapter = {"canonical_project_v1": document,
                                     "manual_fields": {"unprojected": [1, 2, 3]}}
    unmodeled_raw_extension = {"canonical_project_v1": document,
                              "unmodeled_source_data": {"preserve": "even if not rendered"}}
    for source in (legacy, adopted_without_manual_adapter, unmodeled_raw_extension):
        before = deepcopy(source)
        result = storage_project_input(source)
        assert result == source == before
        assert result is not source
