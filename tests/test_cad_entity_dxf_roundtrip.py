from pathlib import Path

from backend.planning.cad_entity_dxf_roundtrip import (
    SUPPORTED_DXF_ENTITY_MAPPING,
    verify_cad_entity_dxf_roundtrip,
)
from backend.planning.cad_entity_model import CAD_ENTITY_MODEL_VERSION, build_cad_entity_model


def _model(*, dirty: bool = False) -> dict:
    return build_cad_entity_model(
        {
            CAD_ENTITY_MODEL_VERSION: {
                "layers": [
                    {"id": "layer_site", "name": "SITE", "color": "7", "linetype": "CONTINUOUS"},
                    {"id": "layer_anno", "name": "ANNO", "color": "2", "linetype": "CONTINUOUS"},
                    {"id": "layer_symbol", "name": "SYMBOL", "color": "4", "linetype": "CONTINUOUS"},
                    {"id": "layer_hatch", "name": "HATCH", "color": "8", "linetype": "CONTINUOUS"},
                ],
                "styles": [
                    {"id": "style_by_layer", "name": "By Layer"},
                    {"id": "style_red", "name": "Red", "defaults": {"color": "1", "linetype": "CONTINUOUS"}},
                ],
                "entities": [
                    {
                        "id": "cad-line-1",
                        "type": "line",
                        "geometry": {"start": {"x": 0, "y": 0}, "end": {"x": 10, "y": 0}},
                        "layer_id": "layer_site",
                        "style_id": "style_red",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                        "dirty": dirty,
                    },
                    {
                        "id": "cad-poly-1",
                        "type": "polyline",
                        "geometry": {"points": [{"x": 0, "y": 3}, {"x": 6, "y": 4}, {"x": 9, "y": 5}]},
                        "layer_id": "layer_site",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                    {
                        "id": "cad-rect-1",
                        "type": "rectangle",
                        "geometry": {"origin": {"x": 12, "y": 0}, "width": 4, "height": 3},
                        "layer_id": "layer_site",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                    {
                        "id": "cad-circle-1",
                        "type": "circle",
                        "geometry": {"center": {"x": 5, "y": 10}, "radius": 2},
                        "layer_id": "layer_site",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                    {
                        "id": "cad-arc-1",
                        "type": "arc",
                        "geometry": {"center": {"x": 12, "y": 10}, "radius": 2, "start_angle": 0, "end_angle": 90},
                        "layer_id": "layer_site",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                    {
                        "id": "cad-text-1",
                        "type": "text",
                        "geometry": {"insert": {"x": 0, "y": 14}, "text": "Review label", "height": 1.2},
                        "layer_id": "layer_anno",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                    {
                        "id": "cad-dim-1",
                        "type": "dimension",
                        "geometry": {"start": {"x": 0, "y": 18}, "end": {"x": 10, "y": 18}, "offset": 2},
                        "layer_id": "layer_anno",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                    {
                        "id": "cad-hatch-1",
                        "type": "hatch",
                        "geometry": {"points": [{"x": 20, "y": 0}, {"x": 24, "y": 0}, {"x": 24, "y": 4}, {"x": 20, "y": 4}]},
                        "layer_id": "layer_hatch",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                    {
                        "id": "cad-symbol-1",
                        "type": "block_reference",
                        "geometry": {"insert": {"x": 30, "y": 0}, "block_name": "HYDRANT_PLACEHOLDER"},
                        "layer_id": "layer_symbol",
                        "source_confidence": "survey-backed",
                        "review_status": "draft_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                    {
                        "id": "cad-underlay-1",
                        "type": "underlay_reference",
                        "geometry": {"insert": {"x": 0, "y": 0}},
                        "layer_id": "layer_site",
                        "source_confidence": "survey-backed",
                        "review_status": "imported_review_required",
                        "draft_review_required": True,
                        "construction_release_allowed": False,
                    },
                ],
            }
        }
    )


def test_persistent_cad_entities_export_parse_and_compare_roundtrip(tmp_path: Path) -> None:
    artifact_path = tmp_path / "cad-entities.dxf"

    report = verify_cad_entity_dxf_roundtrip(_model(), artifact_path)

    assert report["source"] == "dxf_roundtrip_report_v1"
    assert report["review_required"] is True
    assert report["construction_release_allowed"] is False
    assert report["supported_dxf_entity_mapping"] == SUPPORTED_DXF_ENTITY_MAPPING
    assert report["expected_entity_count"] == 9
    assert report["preserved"]["entity_count"] is True
    assert report["preserved"]["layers"] is True
    assert report["preserved"]["text_labels"] is True
    assert report["roundtrip_preservation_matrix"]["canonical_cad_entity_ids"] == "passed_via_sidecar"
    assert report["roundtrip_preservation_matrix"]["dimensions"] == "passed"
    assert report["roundtrip_preservation_matrix"]["symbol_block_placeholders"] == "passed"
    assert "Review label" in report["parsed_text_labels"]
    assert "cad-line-1" in report["canonical_cad_entity_ids"]
    assert report["unsupported"] == [{"entity_id": "cad-underlay-1", "type": "underlay_reference", "reason": "unsupported_entity_type"}]
    assert report["local_roundtrip_verified"] is True
    assert report["export_ready_claim_allowed"] is False
    assert "cad_entity_dxf_unsupported_entities" in report["blockers"]


def test_stale_dirty_cad_entities_block_export_ready_claims_but_not_local_parse(tmp_path: Path) -> None:
    report = verify_cad_entity_dxf_roundtrip(_model(dirty=True), tmp_path / "dirty-cad-entities.dxf")

    assert report["local_roundtrip_verified"] is True
    assert report["export_ready_claim_allowed"] is False
    assert "cad_entity_stale_or_dirty" in report["blockers"]
    assert "cad-line-1" in report["stale_dirty_entity_ids"]
    assert any(item["field"] == "export_ready_claim" for item in report["lost_limited"])
