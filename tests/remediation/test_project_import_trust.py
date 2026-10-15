from copy import deepcopy
import importlib
import pytest
from fastapi import HTTPException
from backend.services.project_imports import unverify_project_import
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import ENGINE_REVISION,bind_canvas_result,canvas_result_freshness


def test_claimed_execution_is_preserved_as_unverified_for_sidecar_and_inline():
    inputs=with_canvas_snapshot({"manual_fields":{"units":"ft","site_objects":[
        {"id":"b","type":"office_building","x":0,"y":0,"w":10,"d":10}]}})
    result=bind_canvas_result({"success":True,"final_plan":{"actions":[{"type":"sentinel"}]}},inputs,calculation_executed=True)
    inputs["canonical_project_v1"]["calculation_results"].append({"id":"imported","result_v1":deepcopy(result)})
    payload={"project_input":inputs,"latest_result":result}
    before=deepcopy(payload)
    imported=unverify_project_import(payload)
    assert payload == before
    assert imported["project_input"]["manual_fields"] == inputs["manual_fields"]
    for candidate in (imported["latest_result"],imported["project_input"]["canonical_project_v1"]["calculation_results"][0]["result_v1"]):
        assert "calculation_engine_revision" not in candidate["metadata"]
        assert "calculation_engine_revision" not in candidate["final_plan"]["meta"]
        assert candidate["metadata"]["client_import_v1"]["claimed_engine_revision"] == ENGINE_REVISION
        assert candidate["final_plan"]["actions"] == result["final_plan"]["actions"]
        assert canvas_result_freshness(candidate,inputs)["status"] == "unverified"


@pytest.mark.parametrize("metadata", [1,"invalid",[]])
def test_malformed_import_metadata_rejects_before_storage(monkeypatch,metadata):
    api=importlib.import_module("backend.api.app")
    monkeypatch.setattr(api,"application_save_project_record",lambda **kw:pytest.fail("Malformed import reached storage"))
    with pytest.raises(HTTPException) as error:
        api.save_project(api.SaveProjectPayload(name="Import",latest_result={"metadata":metadata}),{"user_id":"synthetic"})
    assert error.value.status_code == 422


def test_public_import_stays_unverified_after_save_reopen_and_managed_duplicate_unchanged(tmp_path,monkeypatch):
    from backend.services.auth_store import AuthStore
    from backend.services.database import Database
    from backend.services.project_store import ProjectStore
    from backend.services.canonical_results import has_current_engine_revision
    db=Database(tmp_path/"imports.db")
    user=AuthStore(db).register_user(email="import@example.test",password="Synthetic-only-123",name="Importer")["user"]
    store=ProjectStore(db)
    api=importlib.import_module("backend.api.app")
    monkeypatch.setattr(api,"PROJECT_STORE",store)
    monkeypatch.setattr(api,"_maybe_export_session",lambda _: {})
    inputs=with_canvas_snapshot({"manual_fields":{"units":"ft","site_objects":[
        {"id":"b","type":"office_building","x":0,"y":0,"w":10,"d":10}]}})
    result=bind_canvas_result({"success":True,"final_plan":{"actions":[]}},inputs,calculation_executed=True)
    response=api.save_project(api.SaveProjectPayload(name="Imported",project_input=inputs,latest_result=result),user)
    reopened=ProjectStore(Database(db.db_path)).get_project(user_id=user["user_id"],project_id=response["project"]["project_id"])
    assert has_current_engine_revision(reopened["latest_result"]) is False
    assert canvas_result_freshness(reopened["latest_result"],reopened["project_input"])["status"] == "unverified"
    trusted=store.save_project(user_id=user["user_id"],project_id=None,name="Trusted fixture",project_input=inputs,latest_result=result)
    duplicate=store.duplicate_project(user_id=user["user_id"],project_id=trusted["project_id"])
    assert has_current_engine_revision(duplicate["latest_result"]) is True
    assert duplicate["project_input"]["manual_fields"]["site_objects"] == trusted["project_input"]["manual_fields"]["site_objects"]
