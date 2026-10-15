import pytest
from backend.services.brief_classification import KEY, validate_brief_classifications
from backend.services.canonical_project import ProjectDocumentError, validate_project_input
from backend.services.canonical_canvas import with_canvas_snapshot, resolve_canvas_input
from backend.services.edit_transactions import editable_input


def valid(trust="unverified"):
    return {"version": 1, "fields": {"setbacks": {"priority": "required", "trust": trust, "value_key": "bound-to-value"}}}


@pytest.mark.parametrize("change", [
    {"version": True, "fields": {}}, {"version": 2, "fields": {}},
    {"version": 1, "fields": {"__proto__": {}}},
    {"version": 1, "fields": {"setbacks": {"priority": "guessed", "trust": "unverified", "value_key": "x"}}},
    {"version": 1, "fields": {"setbacks": {"priority": "required", "trust": "externally_verified", "value_key": "x"}}},
    {"version": 1, "fields": {"setbacks": {"priority": "required", "trust": "sourced", "value_key": "x", "source_reference": " "}}},
])
def test_rejects_invalid_classification(change):
    with pytest.raises(ProjectDocumentError):
        validate_project_input({"meta": {"site_inputs": {KEY: change}}})


def test_canonical_roundtrip_and_edit_snapshots_preserve_classifications():
    inputs = {"manual_fields": {"units": "ft", "site_objects": []}, "meta": {"site_inputs": {KEY: valid()}}}
    sealed = with_canvas_snapshot(inputs)
    restored = resolve_canvas_input(sealed)
    assert restored["meta"]["site_inputs"][KEY] == valid()
    assert editable_input(restored)["meta"]["site_inputs"][KEY] == valid()
    sealed["canonical_project_v1"]["site"]["site_inputs_v1"] = {KEY: valid()}
    sealed["canonical_project_v1"]["site"]["site_inputs_v1"][KEY]["fields"]["setbacks"]["trust"] = "magic"
    with pytest.raises(ProjectDocumentError):
        resolve_canvas_input(sealed)


def test_external_status_requires_recorded_reference_not_platform_certification():
    record = valid("externally_verified")
    record["fields"]["setbacks"]["source_reference"] = "Engineer review record 12"
    assert validate_brief_classifications(record) == record
