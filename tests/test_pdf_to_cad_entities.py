from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import backend.planning.plan_pdf_understanding as pdfu
from backend.application.chat_workflows import decide_chat
from backend.planning.cad_entity_model import CAD_ENTITY_MODEL_VERSION, build_cad_entity_model, plan_pdf_elements_to_cad_entities
from backend.planning.candidate_review_inbox import build_candidate_review_inbox
from backend.planning.plan_pdf_understanding import analyze_plan_pdf, merge_plan_pdf_analysis_into_meta, update_editable_sheet_element


def _write_text_pdf(path: Path, lines: list[str]) -> None:
    content = "BT /F1 12 Tf 72 720 Td " + " Tj 0 -18 Td ".join(f"({line})" for line in lines) + " Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}\nendstream".encode("latin-1"),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.write_bytes(bytes(out))


class FakeProjectStore:
    def __init__(self, record: Dict[str, Any]) -> None:
        self.record = record

    def get_project(self, *, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        return self.record if self.record.get("user_id") == user_id and self.record.get("project_id") == project_id else None

    def save_project(self, **kwargs: Any) -> Dict[str, Any]:
        self.record = {
            "project_id": kwargs["project_id"],
            "user_id": kwargs["user_id"],
            "name": kwargs["name"],
            "description": kwargs["description"],
            "session_id": kwargs["session_id"],
            "tags": kwargs["tags"],
            "project_input": kwargs["project_input"],
            "latest_result": kwargs["latest_result"],
            "session_state": kwargs["session_state"],
            "metadata": kwargs["metadata"],
        }
        return self.record


def _record(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "project_id": "project_pdf_cad",
        "user_id": "user_1",
        "name": "PDF CAD",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {},
        "latest_result": {"final_plan": {"actions": [], "meta": meta}},
        "session_state": {},
        "metadata": {},
    }


def test_embedded_pdf_text_becomes_review_required_cad_text_and_annotations(tmp_path: Path) -> None:
    pdf = tmp_path / "plan.pdf"
    _write_text_pdf(pdf, ["POOL LABEL", "DIMENSION 24 ft", "SCALE: 1\" = 10'", "MATCHLINE SEE SHEET C2"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="plan.pdf"))

    model = build_cad_entity_model(meta)
    pdf_entities = [item for item in model["entities"] if item["source"] == "plan_pdf_extraction"]

    assert len(pdf_entities) >= 4
    assert any(item["type"] == "text" and item["original_text"] == "POOL LABEL" for item in pdf_entities)
    assert any(item["type"] == "dimension" and item["pdf_annotation_kind"] == "dimension" for item in pdf_entities)
    assert all(item["source_pdf"]["sha256"] for item in pdf_entities)
    assert all(item["source_pdf"]["original_bounds"] for item in pdf_entities)
    assert all(item["imported_pdf_review_required"] is True for item in pdf_entities)
    assert all(item["construction_release_allowed"] is False for item in pdf_entities)
    scale = next(item for item in pdf_entities if item.get("pdf_annotation_kind") == "scale_calibration")
    assert scale["calibration"]["can_calibrate_sheet_model_conversion"] is True
    assert scale["calibration"]["status"] == "review_required"


def test_accepted_scale_candidate_remains_review_required_calibration(tmp_path: Path) -> None:
    pdf = tmp_path / "scale.pdf"
    _write_text_pdf(pdf, ["SCALE: 1\" = 20'"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="scale.pdf"))
    scale_element = next(item for item in meta["plan_pdf_editable_sheet_v1"]["elements"] if item["type"] == "scale_calibration_candidate")

    accepted = update_editable_sheet_element(meta, scale_element["element_id"], {"review_status": "accepted"})
    scale_entity = next(item for item in plan_pdf_elements_to_cad_entities(accepted) if item.get("pdf_annotation_kind") == "scale_calibration")

    assert scale_entity["calibration"]["status"] == "accepted_review_required"
    assert scale_entity["calibration"]["review_required"] is True
    assert scale_entity["calibration"]["construction_release_allowed"] is False


def test_ocr_text_and_unavailable_vector_linework_do_not_fake_cad_geometry(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "scan.pdf"
    _write_text_pdf(pdf, [])
    monkeypatch.setattr(pdfu, "_detect_ocr_engine", lambda config: {"engine": "tesseract", "available": True, "status": "available", "config": config, "blockers": []})
    monkeypatch.setattr(pdfu, "_render_page_previews", lambda path, pages, *, file_url="": ([{**pages[0], "preview_status": "available"}], [{"page_index": 0, "image": object()}], []))
    monkeypatch.setattr(
        pdfu,
        "_ocr_images",
        lambda images, engine, *, min_confidence: (
            [pdfu._TextEvidence(text="POOL DECK ELEVATION 102.50", page_index=0, bbox={"x0": 1, "y0": 2, "x1": 40, "y1": 12}, source="ocr_tesseract", confidence="ocr_tesseract_review_required", confidence_score=0.9)],
            [],
            [],
        ),
    )

    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="scan.pdf"))
    model = build_cad_entity_model(meta)

    assert not [item for item in model["entities"] if item["source"] == "plan_pdf_extraction"]
    assert "vector_geometry_extraction_blocked:no_vector_parser_configured" in meta["plan_pdf_analysis_v1"]["blockers"]
    assert any(item["type"] == "linework_geometry_candidate" for item in meta["plan_pdf_editable_sheet_v1"]["elements"])


def test_supported_pdf_vector_lines_and_polylines_convert_only_when_present(tmp_path: Path) -> None:
    pdf = tmp_path / "vector.pdf"
    _write_text_pdf(pdf, ["OWNER: ACME"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="vector.pdf"))
    meta["plan_pdf_analysis_v1"]["vector_geometry_candidates"] = [
        {"type": "line", "points": [{"x": 0, "y": 0}, {"x": 12, "y": 0}], "confidence": "vector_pdf_review_required", "bounds": {"x0": 0, "y0": 0, "x1": 12, "y1": 0}},
        {"type": "circle", "geometry": {"center": {"x": 2, "y": 2}, "radius": 1}, "confidence": "vector_pdf_review_required"},
    ]

    entities = plan_pdf_elements_to_cad_entities(meta)

    assert any(item["source"] == "plan_pdf_vector_extraction" and item["type"] == "line" for item in entities)
    assert not any(item["source"] == "plan_pdf_vector_extraction" and item["type"] == "circle" for item in entities)


def test_candidate_review_inbox_exposes_pdf_derived_cad_entity_candidates(tmp_path: Path) -> None:
    pdf = tmp_path / "inbox.pdf"
    _write_text_pdf(pdf, ["POOL LABEL", "DIMENSION 24 ft"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="inbox.pdf"))

    inbox = build_candidate_review_inbox(meta)

    assert any(item["candidate_type"].startswith("plan_pdf_cad_") for item in inbox["candidates"])
    cad_candidate = next(item for item in inbox["candidates"] if item["candidate_type"].startswith("plan_pdf_cad_"))
    assert cad_candidate["status"] == "pending"
    assert cad_candidate["construction_release_allowed"] is False
    assert cad_candidate["source_record"]["source_pdf"]["sha256"]


def test_chat_converts_reports_and_explains_unconverted_pdf_cad_items(tmp_path: Path) -> None:
    pdf = tmp_path / "chat.pdf"
    _write_text_pdf(pdf, ["POOL LABEL", "DIMENSION 24 ft"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="chat.pdf"))
    store = FakeProjectStore(_record(meta))

    converted = decide_chat(
        {"message": "turn PDF labels into CAD text", "context": {"current_project": {"project_id": "project_pdf_cad"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )
    listed = decide_chat(
        {"message": "what PDF elements became CAD entities?", "context": {"current_project": {"project_id": "project_pdf_cad"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )
    blocked = decide_chat(
        {"message": "why can't this raster line become CAD?", "context": {"current_project": {"project_id": "project_pdf_cad"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )

    assert converted["action_taken"] == "converted_pdf_candidates_to_review_required_cad_entities"
    saved_meta = store.record["latest_result"]["final_plan"]["meta"]
    assert CAD_ENTITY_MODEL_VERSION in saved_meta
    assert "PDF-derived CAD" in listed["assistant_message"]
    assert "raster line cannot become CAD linework" in blocked["assistant_message"]
    assert "vector_geometry_extraction_blocked:no_vector_parser_configured" in blocked["assistant_message"]
