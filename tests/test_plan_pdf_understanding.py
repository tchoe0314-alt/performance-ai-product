from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any, Dict, Optional

import backend.planning.plan_pdf_understanding as pdfu
from backend.application.chat_workflows import decide_chat
from backend.planning.plan_pdf_understanding import (
    SOURCE_CONFIDENCE,
    analyze_plan_pdf,
    merge_plan_pdf_analysis_into_meta,
    plan_pdf_report,
    update_editable_sheet_element,
)


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


def _write_blank_pdf(path: Path) -> None:
    _write_text_pdf(path, [])


def _write_image_pdf(path: Path, text: str = "POOL DECK ELEVATION 102.50") -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 120), text, fill="black")
    draw.rectangle((70, 105, 620, 160), outline="black", width=3)
    image.save(path, "PDF", resolution=150.0)


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


def test_embedded_text_pdf_extracts_title_notes_scale_and_dimensions(tmp_path: Path) -> None:
    pdf = tmp_path / "Pool Geometric.pdf"
    _write_text_pdf(
        pdf,
        [
            "OWNER: ACME HOMES",
            "SCALE: 1\" = 10'",
            "POOL DECK ELEVATION 102.50",
            "GENERAL NOTES",
            "DETAIL A - POOL COPING",
            "DIMENSION 24 ft",
            "MATCHLINE SEE SHEET C2",
        ],
    )

    analysis = analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="user_pool.pdf")

    assert analysis["page_count"] == 1
    assert analysis["source_confidence"] == SOURCE_CONFIDENCE
    assert analysis["summary"]["title_block_count"] >= 1
    assert analysis["summary"]["note_block_count"] >= 1
    assert analysis["summary"]["scale_candidate_count"] >= 1
    assert analysis["summary"]["dimension_count"] >= 1
    assert analysis["editable_sheet"]["summary"]["editable_count"] >= 4
    assert all(item["review_required"] for item in analysis["editable_sheet"]["elements"])


def test_image_like_pdf_records_ocr_and_geometry_blockers(tmp_path: Path) -> None:
    pdf = tmp_path / "scanned.pdf"
    _write_blank_pdf(pdf)

    analysis = analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="scan.pdf")

    assert analysis["page_count"] == 1
    assert "ocr_fallback_blocked:no_ocr_engine_configured" in analysis["blockers"]
    assert "vector_geometry_extraction_blocked:no_vector_parser_configured" in analysis["blockers"]
    assert analysis["summary"]["embedded_text_found"] is False
    assert analysis["ocr"]["engine"]["available"] is False


def test_generated_image_pdf_does_not_fake_ocr_when_engine_unavailable(tmp_path: Path) -> None:
    pdf = tmp_path / "generated-scan.pdf"
    _write_image_pdf(pdf)

    analysis = analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="scan.pdf")

    assert analysis["summary"]["embedded_text_found"] is False
    assert analysis["summary"]["ocr_text_found"] is False
    assert analysis["ocr"]["text_evidence_count"] == 0
    assert analysis["classifications"]["elevation_callouts"] == []
    assert any(item.startswith("ocr_engine_unavailable") or item.startswith("ocr_fallback_blocked") for item in analysis["blockers"])


def test_scanned_pdf_ocr_path_records_bbox_confidence_unreadable_and_review_candidates(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "fake-ocr-scan.pdf"
    _write_image_pdf(pdf)

    def fake_detect(config):
        return {
            "engine": "tesseract",
            "available": True,
            "status": "available",
            "config": config,
            "blockers": [],
        }

    def fake_render(path, pages, *, file_url=""):
        page = dict(pages[0])
        page.update({"preview_status": "available", "preview_path": str(tmp_path / "page.png"), "preview_blocker": ""})
        return [page], [{"page_index": 0, "image": object()}], []

    def fake_ocr(images, engine, *, min_confidence):
        return (
            [
                pdfu._TextEvidence(
                    text="POOL DECK ELEVATION 102.50",
                    page_index=0,
                    bbox={"x0": 80, "y0": 120, "x1": 350, "y1": 145},
                    source="ocr_tesseract",
                    confidence="ocr_tesseract_review_required",
                    confidence_score=0.91,
                )
            ],
            [
                {
                    "page_index": 0,
                    "bbox": {"x0": 420, "y0": 120, "x1": 470, "y1": 145},
                    "raw_text": "??",
                    "confidence_score": 0.21,
                    "reason": "below_ocr_confidence_threshold",
                    "review_required": True,
                }
            ],
            [],
        )

    monkeypatch.setattr(pdfu, "_detect_ocr_engine", fake_detect)
    monkeypatch.setattr(pdfu, "_render_page_previews", fake_render)
    monkeypatch.setattr(pdfu, "_ocr_images", fake_ocr)

    analysis = analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="scan.pdf")
    meta = merge_plan_pdf_analysis_into_meta({}, analysis)
    from backend.planning.candidate_review_inbox import build_candidate_review_inbox

    inbox = build_candidate_review_inbox(meta)

    assert analysis["summary"]["ocr_text_found"] is True
    assert analysis["ocr"]["status"] == "extracted_review_required"
    assert analysis["ocr"]["unreadable_count"] == 1
    assert analysis["raw_text_evidence"][0]["bbox"]["x0"] == 80
    assert analysis["raw_text_evidence"][0]["confidence_score"] == 0.91
    assert analysis["classifications"]["elevation_callouts"][0]["source"] == "ocr_tesseract"
    assert any(item["candidate_type"] == "plan_pdf_elevation_callout" for item in inbox["candidates"])


def test_chat_supports_scanned_plan_unreadable_and_elevation_queries(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "fake-ocr-chat.pdf"
    _write_image_pdf(pdf)

    monkeypatch.setattr(
        pdfu,
        "_detect_ocr_engine",
        lambda config: {"engine": "tesseract", "available": True, "status": "available", "config": config, "blockers": []},
    )
    monkeypatch.setattr(
        pdfu,
        "_render_page_previews",
        lambda path, pages, *, file_url="": ([{**pages[0], "preview_status": "available", "preview_blocker": ""}], [{"page_index": 0, "image": object()}], []),
    )
    monkeypatch.setattr(
        pdfu,
        "_ocr_images",
        lambda images, engine, *, min_confidence: (
            [
                pdfu._TextEvidence(
                    text="POOL DECK ELEVATION 102.50",
                    page_index=0,
                    bbox={"x0": 80, "y0": 120, "x1": 350, "y1": 145},
                    source="ocr_tesseract",
                    confidence="ocr_tesseract_review_required",
                    confidence_score=0.91,
                )
            ],
            [{"page_index": 0, "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}, "raw_text": "??", "confidence_score": 0.21}],
            [],
        ),
    )
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="scan.pdf"))
    record = {
        "project_id": "project_ocr",
        "user_id": "user_1",
        "name": "Scan",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {},
        "latest_result": {"final_plan": {"actions": [], "meta": meta}},
        "session_state": {},
        "metadata": {},
    }
    store = FakeProjectStore(record)

    scanned = decide_chat(
        {"message": "read this scanned plan", "context": {"current_project": {"project_id": "project_ocr"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )
    elevations = decide_chat(
        {"message": "find all elevations", "context": {"current_project": {"project_id": "project_ocr"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )
    unreadable = decide_chat(
        {"message": "what could you not read?", "context": {"current_project": {"project_id": "project_ocr"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )

    assert "OCR status: extracted_review_required" in scanned["assistant_message"]
    assert "POOL DECK ELEVATION 102.50" in elevations["assistant_message"]
    assert "??" in unreadable["assistant_message"]


def test_dependency_blocked_path_is_clean(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "blocked.pdf"
    _write_text_pdf(pdf, ["SCALE: 1\" = 20'"])
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    analysis = analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="blocked.pdf")

    assert any(item.startswith("embedded_text_extraction_unavailable:pypdf_missing") for item in analysis["blockers"])
    assert analysis["source_confidence"] == SOURCE_CONFIDENCE


def test_merge_creates_candidate_review_and_source_confidence(tmp_path: Path) -> None:
    pdf = tmp_path / "pool.pdf"
    _write_text_pdf(pdf, ["OWNER: ACME HOMES", "SCALE: 1\" = 10'", "DIMENSION 24 ft"])
    analysis = analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="pool.pdf")

    meta = merge_plan_pdf_analysis_into_meta({}, analysis)
    from backend.planning.candidate_review_inbox import build_candidate_review_inbox

    inbox = build_candidate_review_inbox(meta)
    assert inbox["candidate_count"] >= 3
    assert any(str(item["candidate_type"]).startswith("plan_pdf_") for item in inbox["candidates"])
    assert meta["source_confidence_map_v1"]["entries"][0]["source_type"] == SOURCE_CONFIDENCE


def test_chat_answers_pdf_questions_and_edits_review_required_element(tmp_path: Path) -> None:
    pdf = tmp_path / "pool.pdf"
    _write_text_pdf(pdf, ["OWNER: OLD OWNER", "SCALE: 1\" = 10'", "POOL DECK ELEVATION 102.50"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="pool.pdf"))
    record = {
        "project_id": "project_1",
        "user_id": "user_1",
        "name": "Pool",
        "description": "",
        "session_id": None,
        "tags": [],
        "project_input": {},
        "latest_result": {"final_plan": {"actions": [], "meta": meta}},
        "session_state": {},
        "metadata": {},
    }
    store = FakeProjectStore(record)

    summary = decide_chat(
        {"message": "what is on this plan?", "context": {"current_project": {"project_id": "project_1"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )
    assert "review-required plan PDF analysis" in summary["assistant_message"]

    edited = decide_chat(
        {"message": "edit the owner block to NEW OWNER", "context": {"current_project": {"project_id": "project_1"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )
    assert edited["action_taken"] == "updated_pdf_derived_sheet_element"
    elements = store.record["latest_result"]["final_plan"]["meta"]["plan_pdf_editable_sheet_v1"]["elements"]
    assert any(item.get("text") == "NEW OWNER" and item.get("review_required") for item in elements)

    changed = decide_chat(
        {"message": "what changed?", "context": {"current_project": {"project_id": "project_1"}}},
        decide_chat_message=lambda payload: {},
        project_store=store,
        user_id="user_1",
    )
    assert changed["action_taken"] == "answered_plan_pdf_understanding_question"
    assert "changed PDF-derived element" in changed["assistant_message"]


def test_select_edit_pdf_text_candidate_records_changed_elements(tmp_path: Path) -> None:
    pdf = tmp_path / "pool.pdf"
    _write_text_pdf(pdf, ["OWNER: OLD OWNER", "POOL DECK ELEVATION 102.50"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="pool.pdf"))
    element = next(item for item in meta["plan_pdf_editable_sheet_v1"]["elements"] if item["type"] == "title_block_field")

    updated = update_editable_sheet_element(meta, element["element_id"], {"text": "OWNER: NEW OWNER"})
    changed = updated["plan_pdf_changed_elements_v1"]

    assert changed["changed_count"] == 1
    assert changed["text_edit_count"] == 1
    assert changed["elements"][0]["original_text"] == "OWNER: OLD OWNER"
    assert changed["elements"][0]["text"] == "OWNER: NEW OWNER"
    assert changed["elements"][0]["review_required"] is True


def test_accept_reject_pdf_candidate_updates_review_report(tmp_path: Path) -> None:
    pdf = tmp_path / "pool.pdf"
    _write_text_pdf(pdf, ["OWNER: ACME HOMES", "POOL DECK ELEVATION 102.50"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="pool.pdf"))
    elements = meta["plan_pdf_editable_sheet_v1"]["elements"]

    accepted = update_editable_sheet_element(meta, elements[0]["element_id"], {"review_status": "accepted"})
    rejected = update_editable_sheet_element(accepted, elements[1]["element_id"], {"review_status": "rejected"})
    report = plan_pdf_report(rejected)

    assert report["changed_elements"]["accepted_count"] == 1
    assert report["changed_elements"]["rejected_count"] == 1
    assert report["review_only_edited_sheet_export"]["review_required"] is True


def test_changed_elements_report_includes_move_and_review_export(tmp_path: Path) -> None:
    pdf = tmp_path / "pool.pdf"
    _write_text_pdf(pdf, ["POOL DECK ELEVATION 102.50"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="pool.pdf"))
    element = next(item for item in meta["plan_pdf_editable_sheet_v1"]["elements"] if item.get("bbox"))

    moved = update_editable_sheet_element(meta, element["element_id"], {"move_target": {"x0": 120, "y0": 640}})
    report = plan_pdf_report(moved)

    assert report["changed_elements"]["moved_count"] == 1
    assert report["changed_elements"]["elements"][0]["moved"] is True
    assert report["review_only_edited_sheet_export"]["changed_elements"][0]["bbox"]["x0"] == 120


def test_move_pdf_candidate_without_target_is_blocked(tmp_path: Path) -> None:
    pdf = tmp_path / "pool.pdf"
    _write_text_pdf(pdf, ["POOL DECK ELEVATION 102.50"])
    meta = merge_plan_pdf_analysis_into_meta({}, analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="pool.pdf"))
    element = next(item for item in meta["plan_pdf_editable_sheet_v1"]["elements"] if item.get("bbox"))

    try:
        update_editable_sheet_element(meta, element["element_id"], {"move_target": {}})
    except ValueError as exc:
        assert "explicit target x0/y0 coordinates" in str(exc)
    else:
        raise AssertionError("Expected targetless PDF move to be blocked.")


def test_pdf_analysis_never_uses_unsafe_release_wording(tmp_path: Path) -> None:
    pdf = tmp_path / "sealed.pdf"
    _write_text_pdf(pdf, ["ENGINEER SEAL", "SIGNATURE", "OWNER: ACME"])

    analysis = analyze_plan_pdf(pdf, original_filename=pdf.name, stored_filename="sealed.pdf")

    assert analysis["construction_release_allowed"] is False
    assert analysis["contains_possible_stamp_seal_signature"] is True
    rendered = str(plan_pdf_report(merge_plan_pdf_analysis_into_meta({}, analysis))).lower()
    for unsafe in ("construction-ready", "construction ready", "approved for construction", "certified for construction"):
        assert unsafe not in rendered
    assert "field-use release" in analysis["truth_label"]
