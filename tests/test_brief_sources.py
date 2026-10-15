from copy import deepcopy
import pytest
from backend.services.brief_sources import validate_brief_sources, KEY, TYPES
from backend.services.canonical_project import validate_project_input, ProjectDocumentError
from backend.services.canonical_canvas import with_canvas_snapshot, resolve_canvas_input


def source():
    return {"id": "source-1", "name": "Pilot survey", "type": "survey", "origin": "Original survey file", "jurisdiction": "", "effective_date": "", "imported_at": "2026-10-12T12:00:00Z", "version": "v1", "accepted": False, "verification": "unverified", "verified_by": "", "verification_reference": "", "superseded": False, "rights": "unknown", "rights_reference": "", "object_ids": [], "calculation_ids": [], "requirement_ids": ["setbacks"]}


@pytest.mark.parametrize("kind", sorted(TYPES))
def test_source_categories_roundtrip_without_becoming_verified(kind):
    row = source()
    row["type"] = kind
    register = {"version": 1, "records": [row]}
    sealed = with_canvas_snapshot({"manual_fields": {"units": "ft", "site_objects": []}, "meta": {"site_inputs": {KEY: register}}})
    restored = resolve_canvas_input(sealed)["meta"]["site_inputs"][KEY]
    assert restored == register
    assert restored["records"][0]["verification"] == "unverified"
    assert restored["records"][0]["accepted"] is False


@pytest.mark.parametrize("patch", [{"accepted": "yes"}, {"verification": "verified"}, {"verification": "verification_recorded"}, {"rights": "permission_recorded"}, {"effective_date": "2026-02-31"}, {"imported_at": "bad"}, {"requirement_ids": ["invented"]}, {"object_ids": ["a", "a"]}, {"name": " "}, {"origin": ""}])
def test_invalid_source_metadata_rejected_at_save_boundary(patch):
    with pytest.raises(ProjectDocumentError):
        validate_project_input({"meta": {"site_inputs": {KEY: {"version": 1, "records": [{**source(), **patch}]}}}})


def test_source_records_are_detached_and_duplicate_ids_rejected():
    register = {"version": 1, "records": [source()]}
    cloned = validate_brief_sources(register)
    cloned["records"][0]["name"] = "Changed"
    assert register["records"][0]["name"] == "Pilot survey"
    duplicate = deepcopy(register)
    duplicate["records"].append(source())
    with pytest.raises(ProjectDocumentError):
        validate_brief_sources(duplicate)
