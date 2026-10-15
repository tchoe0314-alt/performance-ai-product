from copy import deepcopy
import importlib
import json

import pytest
from fastapi import HTTPException

from backend.services.auth_store import AuthStore
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_project import ProjectDocumentError, dumps_project_document, loads_project_document
from backend.services.canonical_record import OWNER, portable_document
from backend.services.database import Database
from backend.services.project_store import ProjectStore


@pytest.fixture
def setup(tmp_path):
    db = Database(tmp_path / "aggregate.db")
    user = AuthStore(db).register_user(email="aggregate@example.test", password="Disposable-123", name="Aggregate")["user"]["user_id"]
    store = ProjectStore(db)
    inputs = with_canvas_snapshot({"input_mode": "user", "manual_fields": {"units": "ft", "site_objects": [
        {"id": "road", "type": "road", "x": 30, "y": 40, "w": 30, "d": 100},
    ]}, "meta": {"site_inputs": {"address": "Fixture", "source": {"verified": False}}}})
    result = {"success": True, "assumptions": ["Unverified concept"], "final_plan": {"meta": {
        "quantities": {"area": 3000}, "cost_estimate": {"total": 1},
        "design_alternatives_v1": {"selected": "a"}, "source_confidence_map_v1": {"verified": False},
        "assumptions": ["Needs review"],
    }}}
    project = store.save_project(user_id=user, project_id=None, name="Fixture", project_input=inputs, latest_result=result)
    return db, store, user, project, result


def test_result_facets_have_one_owner_and_compatibility_reads_reconstruct_them(setup):
    db, store, user, project, result = setup
    document = project["project_input"]["canonical_project_v1"]
    assert document["quantities"][0]["plan_facets_v1"]["quantities"] == {"area": 3000}
    assert document["alternatives"][0]["plan_facets_v1"]["design_alternatives_v1"] == {"selected": "a"}
    assert document["sources"][0]["plan_facets_v1"]["source_confidence_map_v1"] == {"verified": False}
    connection = db.connect()
    try:
        raw = json.loads(connection.execute("SELECT latest_result_json FROM projects WHERE project_id = ?", (project["project_id"],)).fetchone()["latest_result_json"])
    finally:
        connection.close()
    assert "quantities" not in raw["final_plan"]["meta"]
    assert "assumptions" not in raw
    assert store.get_project_latest_result(user_id=user, project_id=project["project_id"]) == result
    shell = store.get_project_shell(user_id=user, project_id=project["project_id"])
    assert shell["latest_result"] == {}


def test_document_round_trip_preserves_geometry_results_and_unverified_status(setup):
    _, store, user, project, result = setup
    document = loads_project_document(dumps_project_document(portable_document(project)))
    imported = store.save_project(user_id=user, project_id=None, name="Imported", project_input={"canonical_project_v1": document})
    assert imported["project_input"]["manual_fields"] == project["project_input"]["manual_fields"]
    assert imported["latest_result"] == result
    assert imported["project_input"]["meta"]["site_inputs"]["source"]["verified"] is False
    assert imported["project_input"]["canonical_project_v1"]["coordinate_system"]["horizontal_crs"] is None
    history = imported["project_input"]["canonical_project_v1"]["calculation_results"][-1]
    assert history["history_reference_v1"]["project_id"] == imported["project_id"]


def test_unhydrated_result_reference_cannot_be_imported_as_a_partial_result(setup):
    _, store, user, project, _ = setup
    with pytest.raises(ProjectDocumentError, match="hydrated"):
        store.save_project(user_id=user, project_id=None, name="Incomplete import", project_input=project["project_input"])


def test_canonical_site_and_controls_override_stale_compatibility_shadows(setup):
    _, store, user, project, _ = setup
    incoming = deepcopy(project["project_input"])
    incoming["canonical_project_v1"]["site"]["site_inputs_v1"]["address"] = "Canonical edit"
    incoming["canonical_project_v1"]["extensions"][OWNER]["input_controls"]["input_mode"] = "ai"
    saved = store.save_project_shell(user_id=user, project_id=project["project_id"], name="Fixture", project_input=incoming)
    assert saved["project_input"]["meta"]["site_inputs"]["address"] == "Canonical edit"
    assert saved["project_input"]["input_mode"] == "ai"


def test_existing_legacy_input_writer_refreshes_the_canonical_adapter(setup):
    _, store, user, project, _ = setup
    saved = store.save_project_shell(user_id=user, project_id=project["project_id"], name="Fixture", project_input={
        "meta": {"site_inputs": {"address": "Legacy writer edit"}}, "input_mode": "ai",
    })
    doc = saved["project_input"]["canonical_project_v1"]
    assert doc["site"]["site_inputs_v1"]["address"] == "Legacy writer edit"
    assert doc["extensions"][OWNER]["input_controls"]["input_mode"] == "ai"


def test_invalid_result_reference_is_rejected_without_overwriting_project(setup):
    _, store, user, project, _ = setup
    incoming = deepcopy(project["project_input"])
    incoming["canonical_project_v1"]["extensions"][OWNER]["active_result_id"] = "missing"
    with pytest.raises(ProjectDocumentError):
        store.save_project_shell(user_id=user, project_id=project["project_id"], name="Bad", project_input=incoming)
    assert store.get_project(user_id=user, project_id=project["project_id"])["revision_token"] == project["revision_token"]


def test_document_endpoint_is_detached_and_access_scoped(setup, monkeypatch):
    _, store, user, project, _ = setup
    api = importlib.import_module("backend.api.app")
    monkeypatch.setattr(api, "PROJECT_STORE", store)
    exported = api.get_project_document(project["project_id"], {"user_id": user})
    exported["document"]["roads"].clear()
    assert store.get_project(user_id=user, project_id=project["project_id"])["project_input"]["canonical_project_v1"]["roads"]
    with pytest.raises(HTTPException) as exc:
        api.get_project_document(project["project_id"], {"user_id": "stranger"})
    assert exc.value.status_code == 404


def test_legacy_metadata_update_does_not_migrate_or_hide_results_and_save_keeps_backup(setup):
    db, store, user, project, result = setup
    legacy_input = {"manual_fields": {"units": "ft", "building_width": 100}, "meta": {"site_inputs": {"address": "Legacy"}}}
    connection = db.connect()
    try:
        connection.execute("UPDATE projects SET project_input_json = ?, latest_result_json = ? WHERE project_id = ?",
                           (json.dumps(legacy_input), json.dumps(result), project["project_id"]))
        connection.commit()
    finally:
        connection.close()
    store.update_project_metadata(user_id=user, project_id=project["project_id"], update_metadata=lambda record: {"note": "Preserve legacy"})
    legacy = store.get_project(user_id=user, project_id=project["project_id"])
    assert legacy["project_input"] == legacy_input
    assert legacy["latest_result"] == result
    store.save_project_shell(user_id=user, project_id=project["project_id"], name="Migrated", project_input=legacy_input)
    migrated = store.get_project(user_id=user, project_id=project["project_id"])
    assert migrated["latest_result"] == result
    backup = migrated["metadata"]["legacy_project_backup_v1"]
    assert backup["project_input"] == legacy_input
    assert backup["latest_result"] == result
    assert migrated["project_input"]["canonical_project_v1"]["units"]["length"] == "ft"


def test_program_only_units_use_the_model_and_explicit_unknown_does_not_retain_feet(setup):
    _, store, user, _, _ = setup
    program = store.save_project(user_id=user, project_id=None, name="Program", project_input={"manual_fields": {"units": "ft", "building_width": 30}})
    incoming = deepcopy(program["project_input"])
    incoming["canonical_project_v1"]["units"]["length"] = "m"
    metric = store.save_project_shell(user_id=user, project_id=program["project_id"], name="Program", project_input=incoming)
    assert metric["project_input"]["manual_fields"]["units"] == "m"
    incoming = deepcopy(metric["project_input"])
    incoming["canonical_project_v1"]["units"]["length"] = None
    unknown = store.save_project_shell(user_id=user, project_id=program["project_id"], name="Program", project_input=incoming)
    assert unknown["project_input"]["manual_fields"]["units"] is None
    assert unknown["project_input"]["canonical_project_v1"]["units"]["length"] is None
