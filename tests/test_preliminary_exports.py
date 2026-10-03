from copy import deepcopy

import pytest
from fastapi import HTTPException

from backend.planning.preliminary_export import (
    has_valid_preliminary_disclosure,
    prepare_preliminary_snapshot,
    preliminary_disclosure_lines,
)


def source():
    return {
        "units": "ft",
        "actions": [{"task": "rectangle", "origin": [0, 0], "width": 30, "height": 50}],
        "meta": {"canonical_revision": "revision-7", "system_dirty_state": {"grading": {"state": "stale"}}},
    }


def test_snapshot_is_immutable_and_discloses_source_and_all_warnings():
    original = source()
    before = deepcopy(original)
    plan = prepare_preliminary_snapshot(original, notes=[f"Warning {i}" for i in range(100)])
    repeated = prepare_preliminary_snapshot(plan, notes=["Original workflow note"])
    assert original == before
    assert plan["actions"] == original["actions"]
    disclosure = repeated["meta"]["preliminary_export_v1"]
    assert disclosure["source_revision"] == "revision-7"
    assert disclosure["stale_systems"] == ["grading"]
    assert disclosure["construction_release_allowed"] is False
    assert "- Warning 99" in preliminary_disclosure_lines(disclosure)
    assert "- Original workflow note" in preliminary_disclosure_lines(disclosure)
    assert has_valid_preliminary_disclosure(repeated)
    repeated["actions"][0]["width"] = 40
    assert not has_valid_preliminary_disclosure(repeated)


@pytest.mark.parametrize("change", [
    {"units": "unknown"},
    {"actions": []},
    {"actions": [{"task": "unsupported"}]},
    {"actions": [{"task": "rectangle", "width": 0, "height": 5}]},
    {"actions": [{"task": "circle", "radius": -1}]},
    {"actions": [{"task": "polyline", "points": [[0, 0], [0, 0]]}]},
    {"actions": [{"task": "point", "x": float("nan"), "y": 0}]},
    {"meta": {"canonical_integrity": {"blocked": True, "cache_only_stages": ["grading"]}}},
    {"meta": {"canonical_integrity": {"blocked": True}}},
])
def test_invalid_geometry_and_integrity_remain_blocked(change):
    plan = source()
    plan.update(change)
    with pytest.raises(HTTPException) as error:
        prepare_preliminary_snapshot(plan)
    assert error.value.status_code == 409


def test_forged_disclosure_does_not_waive_integrity():
    plan = source()
    plan["meta"]["preliminary_export_v1"] = {"version": 1}
    assert not has_valid_preliminary_disclosure(plan)


def test_dxf_file_contains_source_and_stale_disclosure(tmp_path):
    import ezdxf
    from output.dxf_exporter import save_dxf

    plan = prepare_preliminary_snapshot(source(), notes=["FINAL_WARNING_MARKER"])
    path = save_dxf(plan, str(tmp_path / "review.dxf"))
    document = ezdxf.readfile(path)
    text = "\n".join(entity.plain_text() for entity in document.modelspace().query("MTEXT"))
    assert "NOT FOR CONSTRUCTION" in text
    assert "revision-7" in text
    assert "grading" in text
    assert "FINAL_WARNING_MARKER" in text
    assert plan["meta"]["export_audit"]["export_blocked"] is False


@pytest.mark.parametrize("preview", [None, b"not an image"])
def test_pdf_never_succeeds_with_missing_or_invalid_drawing(tmp_path, preview):
    from unittest.mock import patch
    from backend.services.artifact_service import ArtifactService

    service = ArtifactService(tmp_path)
    with patch.object(service, "build_preview_png", return_value=preview):
        with pytest.raises(HTTPException) as error:
            service.export_review_pdf(
                user_id="review-user", result_data={"final_plan": source()},
                sheet_set={}, auto_site_context_summary={}, review_package_summary={}, stem="invalid-preview",
            )
    assert error.value.status_code == 409
    assert not list(tmp_path.rglob("*.pdf"))
