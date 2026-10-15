import pytest
from backend.services.brief_editing import validate_brief_originals, KEY
from backend.services.canonical_project import ProjectDocumentError, validate_project_input


def test_preserved_originals_are_detached_and_validated_at_save_boundary():
    originals = {"version": 1, "fields": {"setbacks": {"value": 0}}}
    cloned = validate_brief_originals(originals)
    cloned["fields"]["setbacks"]["value"] = 10
    assert originals["fields"]["setbacks"]["value"] == 0
    assert validate_project_input({"meta": {"site_inputs": {KEY: originals}}})


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), {}, [], "x" * 201])
def test_invalid_originals_cannot_be_saved(bad):
    with pytest.raises(ProjectDocumentError):
        validate_project_input({"meta": {"site_inputs": {KEY: {"version": 1, "fields": {"setbacks": {"value": bad}}}}}})


def test_original_cannot_carry_invalid_source_confirmation():
    with pytest.raises(ProjectDocumentError):
        validate_brief_originals({"version": 1, "fields": {"setbacks": {"value": 20, "classification": {"priority": "required", "trust": "sourced", "value_key": "20"}}}})
