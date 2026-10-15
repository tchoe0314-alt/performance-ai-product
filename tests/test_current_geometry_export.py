from copy import deepcopy
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from backend.application.current_geometry_export import prepare_current_geometry_result, queue_current_geometry_export, SCOPE, build_current_geometry_export_runner, export_current_geometry_artifact
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.project_revision import project_revision
from backend.planning.preliminary_export import has_valid_preliminary_disclosure


def project():
    record = {"project_id": "pilot", "name": "Current drawing", "access_role": "owner", "project_input": with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [{"id": "office", "type": "office_building", "x": 10, "y": 20, "w": 100, "d": 60}, {"id": "pipe", "type": "utility_corridor", "x": 120, "y": 30, "w": 40, "d": 8}]}, "meta": {"system_dirty_state": {"grading": "stale", "roads": "not_generated"}}}), "latest_result": {"final_plan": {"actions": [{"task": "rectangle", "layer": "OLD_RESULT", "origin": [999, 999], "width": 1000, "height": 1000}], "meta": {"quantities": {"invented": 99}}}}}
    record["revision_token"] = project_revision(record)
    return record


def test_drawing_snapshot_is_current_geometry_not_an_enriched_old_calculation():
    original = project()
    before = deepcopy(original)
    result = prepare_current_geometry_result(original)
    plan = result["final_plan"]
    assert [a["canonical_source_id"] for a in plan["actions"]] == ["office", "pipe"]
    assert plan["actions"][1]["task"] == "rectangle"  # A corridor footprint is not silently replaced with a pipe centerline.
    assert plan["actions"][0]["origin"] == [10, 20]
    assert plan["meta"]["quantities"]["status"] == "not_included"
    assert plan["meta"]["preliminary_export_v1"]["geometry_scope"] == SCOPE
    assert "grading" in plan["meta"]["preliminary_export_v1"]["stale_systems"]
    assert has_valid_preliminary_disclosure(plan)
    assert original == before


@pytest.mark.parametrize("change", [{"units": "unknown"}, {"site_objects": []}, {"site_objects": [{"id": "broken", "type": "building", "x": 0, "y": 0, "w": 0, "d": 1}]}])
def test_invalid_drawing_not_waived_by_preliminary_acknowledgement(change):
    record = project()
    raw = deepcopy(record["project_input"])
    raw["manual_fields"].update(change)
    record["project_input"] = with_canvas_snapshot(raw)
    with pytest.raises(HTTPException) as error:
        prepare_current_geometry_result(record)
    assert error.value.status_code == 409


@pytest.mark.parametrize("role", ["viewer", "reviewer"])
def test_view_only_roles_cannot_create_drawing_exports(role):
    record = project()
    record["access_role"] = role
    store = SimpleNamespace(get_project=lambda **_: record)
    queue = SimpleNamespace(submit_job=lambda **_: pytest.fail("Read-only user must not queue an export"))
    with pytest.raises(HTTPException) as error:
        queue_current_geometry_export(project_store=store, job_queue=queue, user_id="viewer", project_id="pilot", expected_revision=record["revision_token"], export_format="dxf", acknowledged=True)
    assert error.value.status_code == 403


def test_acknowledgement_and_revision_are_checked_before_queuing():
    record = project()
    store = SimpleNamespace(get_project=lambda **_: record)
    queue = SimpleNamespace(submit_job=lambda **kwargs: {"job_id": "queued", **kwargs})
    with pytest.raises(HTTPException):
        queue_current_geometry_export(project_store=store, job_queue=queue, user_id="owner", project_id="pilot", expected_revision=record["revision_token"], export_format="dxf", acknowledged=False)
    with pytest.raises(HTTPException) as error:
        queue_current_geometry_export(project_store=store, job_queue=queue, user_id="owner", project_id="pilot", expected_revision="old", export_format="dxf", acknowledged=True)
    assert error.value.status_code == 409
    queued = queue_current_geometry_export(project_store=store, job_queue=queue, user_id="owner", project_id="pilot", expected_revision=record["revision_token"], export_format="dxf", acknowledged=True)
    assert queued["job"]["job_type"] == "export_current_geometry_dxf"
    assert "result" not in queued["job"]["payload"]


def test_worker_refuses_changed_revision_before_artifact_generation():
    record = project()
    runner = build_current_geometry_export_runner(artifact_service=None, project_store=SimpleNamespace(get_project=lambda **_: record), update_job_progress=lambda *a, **kw: None, export_format="dxf")
    with pytest.raises(HTTPException) as error:
        runner({"project_id": "pilot", "user_id": "owner", "job_id": "job", "payload": {"expected_revision": "old", "preliminary_acknowledged": True, "result": {"forged": True}}})
    assert error.value.status_code == 409


@pytest.mark.parametrize("export_format", ["dxf", "pdf"])
def test_completed_job_manifest_identifies_its_exact_saved_drawing(tmp_path, monkeypatch, export_format):
    record = project()
    path = tmp_path / f"drawing.{export_format}"
    monkeypatch.setattr("backend.application.current_geometry_export.export_current_geometry_artifact", lambda **_: path)
    runner = build_current_geometry_export_runner(artifact_service=None, project_store=SimpleNamespace(get_project=lambda **_: record), update_job_progress=lambda *a, **kw: None, export_format=export_format)
    result = runner({"project_id": "pilot", "user_id": "owner", "job_id": "job", "payload": {"expected_revision": record["revision_token"], "preliminary_acknowledged": True}})
    assert result["export_manifest_v1"] == {
        "version": 1, "project_id": "pilot", "source_canonical_revision": record["revision_token"],
        "units": "ft", "geometry_scope": SCOPE, "object_ids": ["office", "pipe"],
        "calculation_results_included": False, "construction_release_allowed": False,
    }


@pytest.mark.parametrize("export_format", ["dxf", "pdf"])
def test_real_artifacts_preserve_the_old_calculation_and_drawing_history(tmp_path, export_format):
    from backend.services.database import Database
    from backend.services.auth_store import AuthStore
    from backend.services.project_store import ProjectStore
    from backend.services.artifact_service import ArtifactService
    db = Database(tmp_path / "drawing.db")
    user = AuthStore(db).register_user(email="drawing@example.test", password="Disposable-123", name="Drawing fixture")["user"]["user_id"]
    store = ProjectStore(db)
    seed = project()
    record = store.save_project(user_id=user, project_id=None, name="Drawing specimen", project_input=seed["project_input"], latest_result=seed["latest_result"])
    before = deepcopy(store.get_project(user_id=user, project_id=record["project_id"]))
    result = prepare_current_geometry_result(before)
    path = export_current_geometry_artifact(artifact_service=ArtifactService(tmp_path / "artifacts"), project_store=store, user_id=user, project_id=record["project_id"], result_data=result, export_format=export_format)
    assert path.exists()
    after = store.get_project(user_id=user, project_id=record["project_id"])
    assert after["latest_result"] == before["latest_result"]
    assert after["revision_token"] == before["revision_token"]
    assert after["project_input"]["manual_fields"] == before["project_input"]["manual_fields"]
    assert after["metadata"]["workflow"]["artifacts"][0]["kind"] == f"drawing_{export_format}"
    if export_format == "pdf":
        assert path.read_bytes().startswith(b"%PDF")
    else:
        import ezdxf
        drawing = ezdxf.readfile(path)
        assert drawing.header["$INSUNITS"] == ezdxf.units.FT
        footprints = list(drawing.modelspace().query('LWPOLYLINE[layer=="BUILDING"]'))
        assert footprints, [(entity.dxftype(), entity.dxf.layer) for entity in drawing.modelspace()]
        assert tuple(footprints[0].get_points()[0][:2]) == (10, 20)
        notes = "\n".join(entity.plain_text() for entity in drawing.modelspace().query("MTEXT"))
        assert "NOT FOR CONSTRUCTION" in notes
        assert "Current saved drawing; calculations excluded" in notes
        assert "parking" in notes.lower()


@pytest.mark.parametrize("declared, code, measurement", [("ft", 2, 0), ("m", 6, 1), ("mm", 4, 1), ("in", 1, 0)])
def test_dxf_header_matches_declared_units_without_rescaling_coordinates(tmp_path, declared, code, measurement):
    import ezdxf
    from output.dxf_exporter import save_dxf
    plan = {"units": declared, "actions": [{"task": "rectangle", "layer": "BUILDING", "origin": [10, 20], "width": 30, "height": 40}], "meta": {}}
    path = save_dxf(plan, str(tmp_path / "units.dxf"), finalize_metadata=False)
    drawing = ezdxf.readfile(path)
    assert drawing.header["$INSUNITS"] == code
    assert drawing.header["$MEASUREMENT"] == measurement
    footprint = list(drawing.modelspace().query('LWPOLYLINE[layer=="BUILDING"]'))[0]
    assert tuple(footprint.get_points()[0][:2]) == (10, 20)
