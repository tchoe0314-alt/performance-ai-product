from copy import deepcopy
from types import SimpleNamespace

from backend.application.design_workflows import run_orchestration
from backend.application.project_workflows import get_project_result
from backend.services.canonical_canvas import with_canvas_snapshot
from backend.services.canonical_results import bind_canvas_result, canvas_input_signature, canvas_result_freshness, canvas_live_input_signature


def test_portable_live_input_signature_matches_browser_unicode_decimal_fixture():
    source = {"manual_fields": {"units": "ft", "site_objects": [{"id": "a", "type": "office_building", "x": 1e-7, "y": -0.0, "label": "Café 🚧"}]}, "meta": {"site_inputs": {"note": "測量"}}}
    assert canvas_live_input_signature(source) == "052aebb38581c85b637a7274049c880f2593f2957fdeb25f9e431004ed028281"


def fixture():
    return with_canvas_snapshot({"manual_fields": {"units": "ft", "project_name": "Pilot",
        "site_objects": [{"id": "building", "type": "office_building", "x": 100, "y": 0, "w": 40, "d": 30}]}})


def test_binding_is_detached_and_reload_stable():
    source = fixture()
    original = {"success": True, "metadata": {}, "final_plan": {"meta": {"quantities": {"area": 1200}}}}
    bound = bind_canvas_result(original, source)
    assert original["metadata"] == {}
    assert canvas_result_freshness(bound, deepcopy(source))["status"] == "current"
    source["manual_fields"]["site_objects"][0]["x"] = 999
    assert canvas_result_freshness(bound, source)["status"] == "current"  # canonical wins


def test_geometry_units_and_sources_invalidate_results():
    source = fixture()
    bound = bind_canvas_result({"metadata": {}}, source)
    for change in ("geometry", "units", "sources"):
        changed = deepcopy(source)
        if change == "geometry":
            changed["manual_fields"]["site_objects"][0]["x"] = 150
            changed = with_canvas_snapshot(changed)
        elif change == "units":
            changed["canonical_project_v1"]["units"]["length"] = "m"
        else:
            changed["meta"] = {"site_inputs": {"survey": "new survey"}}
        assert canvas_result_freshness(bound, changed)["status"] == "stale"


def test_label_and_numeric_representation_do_not_invalidate():
    source = fixture()
    renamed = deepcopy(source)
    renamed["manual_fields"]["project_name"] = "Renamed"
    renamed["manual_fields"]["site_objects"][0]["x"] = 100.0
    renamed = with_canvas_snapshot(renamed)
    assert canvas_input_signature(source) == canvas_input_signature(renamed)


def test_legacy_missing_binding_and_invalid_input_are_not_proven_current():
    assert canvas_result_freshness({"success": True}, {}) is None
    assert canvas_result_freshness({"success": True}, fixture())["status"] == "unverified"
    assert canvas_result_freshness({"success": True}, {"canonical_project_v1": {"extensions": {"canvas_workspace_v1": {}}}})["status"] == "unverified"
    assert canvas_result_freshness({}, fixture()) is None


def test_engine_result_is_bound_and_result_endpoint_checks_saved_geometry():
    source = fixture()
    def engine(request):
        return SimpleNamespace(success=True, message="ok", parsed_payload={}, final_plan={}, warnings=[], errors=[], issues=[], assumptions=[], metadata={})
    result = run_orchestration(source, load_orchestrator=lambda: (SimpleNamespace, engine), assess_design_readiness=lambda *_: None)
    changed = deepcopy(source)
    changed["manual_fields"]["site_objects"][0]["x"] = 200
    changed = with_canvas_snapshot(changed)
    store = SimpleNamespace(get_project_shell=lambda **_: {"project_input": changed}, get_project_latest_result=lambda **_: result)
    response = get_project_result(project_store=store, user_id="owner", project_id="pilot")
    assert response["result_freshness_v1"]["status"] == "stale"
    assert response["latest_result"]["metadata"] == result["metadata"]
