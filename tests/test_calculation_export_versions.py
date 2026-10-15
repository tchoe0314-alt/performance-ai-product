from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.application.artifact_workflows import (
    assert_current_export_result, export_dxf_artifact, export_report_artifact, export_review_pdf_artifact,
)
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import bind_canvas_result
from backend.application.project_workflows import artifact_summary


def source():
    return with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": [
        {"id": "building", "type": "office_building", "x": 100, "y": 0, "w": 40, "d": 30}
    ]}})


def check(result, project_input):
    store = SimpleNamespace(get_project_shell=lambda **_: {"project_input": project_input})
    assert_current_export_result(project_store=store, user_id="owner", project_id="pilot", result_data=result)


def test_quantity_binding_references_exact_result_without_mutating_original():
    original = {"metadata": {"_workflow_run_id": "run-1"}, "final_plan": {"meta": {
        "quantities": {"totals": {"building_area_sf": 1200}}, "cost_estimate": {"total": 5000}
    }}}
    bound = bind_canvas_result(original, source())
    binding = bound["metadata"]["quantity_binding_v1"]
    assert binding["workflow_run_id"] == "run-1"
    assert binding["quantities_path"] == "final_plan.meta.quantities"
    assert binding["cost_estimate_path"] == "final_plan.meta.cost_estimate"
    assert binding["input_signature"] == bound["metadata"]["canvas_result_binding_v1"]["input_signature"]
    assert bound["final_plan"] == original["final_plan"]
    assert "quantity_binding_v1" not in original["metadata"]


def test_artifact_history_keeps_calculation_reference():
    bound = bind_canvas_result({"metadata": {"_workflow_run_id": "run-1"}, "final_plan": {}}, source())
    bound["metadata"]["calculation_save_v1"] = {"calculation_id": "calculation-1"}
    artifact = artifact_summary(path=Path("pilot.json"), artifact_kind="report", project_id="pilot", result_data=bound)
    assert artifact["calculation_reference"]["calculation_id"] == "calculation-1"
    assert artifact["calculation_reference"]["workflow_run_id"] == "run-1"
    assert bound["metadata"]["quantity_binding_v1"].get("calculation_id") is None


def test_current_export_allowed_but_geometry_change_blocks_old_result():
    inputs = source()
    bound = bind_canvas_result({"metadata": {}}, inputs)
    check(bound, inputs)
    changed = deepcopy(inputs)
    changed["manual_fields"]["site_objects"][0]["x"] = 200
    changed = with_canvas_snapshot(changed)
    with pytest.raises(HTTPException) as exc:
        check(bound, changed)
    assert exc.value.status_code == 409
    assert "out of date" in exc.value.detail


@pytest.mark.parametrize("project_id", [None, "pilot"])
def test_archived_result_cannot_be_exported_as_current_even_when_inputs_match(project_id):
    inputs = source()
    bound = bind_canvas_result({"metadata": {}}, inputs)
    bound["metadata"]["calculation_save_v1"] = {"disposition": "archived"}
    with pytest.raises(HTTPException) as exc:
        assert_current_export_result(project_store=None, user_id="owner", project_id=project_id, result_data=bound)
    assert exc.value.status_code == 409


def test_legacy_unbound_export_remains_compatible():
    check({"metadata": {}, "final_plan": {}}, source())


def test_missing_project_does_not_export():
    store = SimpleNamespace(get_project_shell=lambda **_: None)
    with pytest.raises(HTTPException) as exc:
        assert_current_export_result(project_store=store, user_id="owner", project_id="missing", result_data={})
    assert exc.value.status_code == 404


@pytest.mark.parametrize("export", [export_dxf_artifact, export_report_artifact, export_review_pdf_artifact])
def test_all_export_entry_points_recheck_saved_inputs_before_generating(export):
    inputs = source()
    bound = bind_canvas_result({"metadata": {}}, inputs)
    changed = deepcopy(inputs)
    changed["manual_fields"]["site_objects"][0]["x"] = 250
    changed = with_canvas_snapshot(changed)
    store = SimpleNamespace(get_project_shell=lambda **_: {"project_input": changed})
    args = {"artifact_service": None, "project_store": store, "user_id": "owner",
            "project_id": "pilot", "result_data": bound}
    if export is export_review_pdf_artifact:
        args["review_sheet_set"] = {}
    with pytest.raises(HTTPException) as exc:
        export(**args)
    assert exc.value.status_code == 409
