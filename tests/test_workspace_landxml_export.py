import pytest
from fastapi import HTTPException
from backend.services.artifact_service import ArtifactService
from backend.planning.landxml_io import import_landxml
from backend.application.artifact_workflows import export_dxf_artifact
from test_atomic_export_finalization import setup, edit
from backend.services.canonical_results import ENGINE_REVISION

def pipe_plan():
    return {"project_name":"Pipe review","units":"ft","actions":[{"task":"polyline","layer":"STORM","points":[[0,0],[100,0]]}],"meta":{"storm_pipes":{"segments":[{"id":"p1","length_ft":100,"diameter_in":18,"slope_ft_ft":0.01,"path":[[0,0],[100,0]]}]}}}

def test_landxml_artifact_validates_supported_data_and_round_trips(tmp_path):
    service=ArtifactService(tmp_path)
    path=service.export_landxml(user_id="test-user",final_plan=pipe_plan())
    imported=import_landxml(path)
    assert imported["success"] and imported["pipe_network_count"]==1
    assert 'civoraReviewOnly="true"' in path.read_text()
    with pytest.raises(ValueError,match="supported pipe-network data"):
        service.export_landxml(user_id="test-user",final_plan={"units":"ft","meta":{}})
    plan=pipe_plan();del plan["meta"]["storm_pipes"]["segments"][0]["diameter_in"]
    with pytest.raises(ValueError,match="known positive length and diameter"):
        service.export_landxml(user_id="test-user",final_plan=plan)

def test_workspace_landxml_uses_current_result_and_atomic_history(setup,tmp_path,monkeypatch):
    _,store,_,user,pid,source,_=setup
    result=store.save_calculation_result(user_id=user,project_id=pid,source_input=source,result={"success":True,"metadata":{"calculation_engine_revision":ENGINE_REVISION},"final_plan":pipe_plan()})
    service=ArtifactService(tmp_path)
    path=export_dxf_artifact(artifact_service=service,project_store=store,user_id=user,project_id=pid,result_data=result,export_scope="review",export_format="landxml")
    assert path.suffix==".landxml" and path.exists()
    project=store.get_project(user_id=user,project_id=pid)
    assert project["metadata"]["workflow"]["artifacts"][0]["kind"]=="landxml"
    import importlib
    api=importlib.import_module("backend.api.app")
    monkeypatch.setattr(api,"PROJECT_STORE",store);monkeypatch.setattr(api,"ARTIFACTS",service)
    response=api.export_landxml(api.ArtifactPayload(project_id=pid),{"user_id":user})
    assert response.media_type=="application/xml" and response.path.exists()
    with pytest.raises(HTTPException) as denied:
        api.export_landxml(api.ArtifactPayload(project_id=pid),{"user_id":"outsider"})
    assert denied.value.status_code==404
    edit(store,user,pid,source)
    with pytest.raises(HTTPException) as rejected:
        export_dxf_artifact(artifact_service=service,project_store=store,user_id=user,project_id=pid,result_data=result,export_scope="review",export_format="landxml")
    assert rejected.value.status_code==409
