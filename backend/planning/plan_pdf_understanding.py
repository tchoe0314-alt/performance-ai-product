from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.planning.common import safe_dict, safe_list, safe_str


TRUTH_LABEL = (
    "PDF-derived plan data is imported source evidence and review-required draft content only. "
    "Civora provides no field-use release and does not act as engineer of record."
)
SOURCE_CONFIDENCE = "imported_pdf_review_required"
ANALYSIS_VERSION = "plan_pdf_analysis_v1"
EDITABLE_VERSION = "plan_pdf_editable_sheet_v1"

DIMENSION_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s*(?:'|ft|feet|in|\"|inch|inches|lf|sf)|\d+\s*[- ]?\d*/\d+\s*(?:\"|in)?)\b",
    re.IGNORECASE,
)
ELEVATION_RE = re.compile(
    r"\b(?:elev(?:ation)?|el\.?|ff|ffe|spot|tc|bc|rim|inv)\s*[:=]?\s*[-+]?\d{1,4}(?:\.\d{1,3})?\b",
    re.IGNORECASE,
)
SCALE_RE = re.compile(
    r"(?:\bscale\s*[:=]?\s*)?(?:\d+\s*(?:\"|in)\s*=\s*\d+\s*(?:'|ft|feet)|\b1\s*:\s*\d+\b|\bnot\s+to\s+scale\b|\bnts\b)",
    re.IGNORECASE,
)
MATCHLINE_RE = re.compile(r"\bmatch\s*line|matchline|see\s+sheet\b", re.IGNORECASE)
TITLE_FIELD_RE = re.compile(
    r"\b(?:owner|client|project|sheet|drawn|checked|date|revision|rev\.?|contact|address|phone|email)\b",
    re.IGNORECASE,
)
NOTE_RE = re.compile(r"\b(?:note|notes|general notes|construction notes|keynotes)\b", re.IGNORECASE)
DETAIL_RE = re.compile(r"\b(?:detail|section|enlargement|typ\.?|typical|diagram)\b", re.IGNORECASE)
STAMP_RE = re.compile(r"\b(?:seal|stamp|signature|signed|professional engineer|engineer of record|p\.?e\.?)\b", re.IGNORECASE)


@dataclass
class _TextEvidence:
    text: str
    page_index: int
    bbox: Optional[Dict[str, float]]
    source: str
    confidence: str = "embedded_text"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": _stable_id("evidence", self.page_index, self.text, self.bbox),
            "text": self.text,
            "page_index": self.page_index,
            "bbox": self.bbox,
            "source": self.source,
            "confidence": self.confidence,
            "review_required": True,
        }


def _stable_id(*parts: Any, prefix: str = "pdf") -> str:
    seed = "|".join(safe_str(part) for part in parts if safe_str(part))
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _now() -> float:
    return time.time()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split())


def _truncate(value: str, limit: int = 220) -> str:
    text = _clean_text(value)
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}..."


def _rect_to_bbox(rect: Any) -> Optional[Dict[str, float]]:
    if rect is None:
        return None
    try:
        values = list(rect)
    except Exception:
        return None
    if len(values) < 4:
        return None
    try:
        return {
            "x0": round(float(values[0]), 3),
            "y0": round(float(values[1]), 3),
            "x1": round(float(values[2]), 3),
            "y1": round(float(values[3]), 3),
        }
    except Exception:
        return None


def _fallback_page_count(path: Path) -> int:
    try:
        raw = path.read_bytes()
    except Exception:
        return 0
    return max(0, len(re.findall(rb"/Type\s*/Page\b", raw)) - len(re.findall(rb"/Type\s*/Pages\b", raw)))


def _extract_with_pypdf(path: Path) -> Tuple[List[Dict[str, Any]], List[_TextEvidence], List[str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        return [], [], [f"embedded_text_extraction_unavailable:pypdf_missing:{exc.__class__.__name__}"]

    pages: List[Dict[str, Any]] = []
    evidence: List[_TextEvidence] = []
    reader = PdfReader(str(path))
    for page_index, page in enumerate(reader.pages):
        media_box = getattr(page, "mediabox", None)
        width = float(getattr(media_box, "width", 0) or 0)
        height = float(getattr(media_box, "height", 0) or 0)
        rotation = int(page.get("/Rotate", 0) or 0)
        page_record: Dict[str, Any] = {
            "page_index": page_index,
            "page_number": page_index + 1,
            "width": round(width, 3),
            "height": round(height, 3),
            "rotation": rotation,
            "size_units": "pdf_points",
            "preview_url": "",
            "preview_status": "blocked",
            "preview_blocker": "Raster preview requires PyMuPDF/poppler or a configured PDF renderer.",
        }
        fragments: List[str] = []

        def visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
            cleaned = _clean_text(text)
            if not cleaned:
                return
            fragments.append(cleaned)
            bbox = None
            try:
                x = float(tm[4])
                y = float(tm[5])
                fs = float(font_size or 10)
                bbox = {"x0": round(x, 3), "y0": round(y, 3), "x1": round(x + max(4.0, len(cleaned) * fs * 0.45), 3), "y1": round(y + fs, 3)}
            except Exception:
                bbox = None
            evidence.append(_TextEvidence(text=cleaned, page_index=page_index, bbox=bbox, source="embedded_pdf_text"))

        try:
            page.extract_text(visitor_text=visitor)
        except TypeError:
            text = _clean_text(page.extract_text() or "")
            if text:
                fragments.append(text)
                evidence.append(_TextEvidence(text=text, page_index=page_index, bbox=None, source="embedded_pdf_text"))
        except Exception:
            text = ""
        page_record["embedded_text_present"] = bool(fragments)
        page_record["embedded_text_excerpt"] = _truncate(" ".join(fragments), 600)
        pages.append(page_record)
    return pages, evidence, []


def _classify_evidence(evidence: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "title_blocks": [],
        "note_blocks": [],
        "detail_blocks": [],
        "dimensions": [],
        "labels": [],
        "elevation_callouts": [],
        "scale_candidates": [],
        "matchlines": [],
        "stamp_or_seal_source_imagery": [],
    }
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        text = safe_str(item.get("text"))
        if not text:
            continue
        checks = [
            ("title_blocks", TITLE_FIELD_RE),
            ("note_blocks", NOTE_RE),
            ("detail_blocks", DETAIL_RE),
            ("dimensions", DIMENSION_RE),
            ("elevation_callouts", ELEVATION_RE),
            ("scale_candidates", SCALE_RE),
            ("matchlines", MATCHLINE_RE),
            ("stamp_or_seal_source_imagery", STAMP_RE),
        ]
        matched = False
        for bucket, pattern in checks:
            if not pattern.search(text):
                continue
            key = (bucket, _clean_text(text).lower())
            if key in seen:
                continue
            seen.add(key)
            rec = dict(item)
            rec["classification"] = bucket
            rec["review_required"] = True
            rec["source_confidence"] = SOURCE_CONFIDENCE
            buckets[bucket].append(rec)
            matched = True
        if not matched and len(text) <= 120:
            key = ("labels", _clean_text(text).lower())
            if key not in seen:
                seen.add(key)
                rec = dict(item)
                rec["classification"] = "labels"
                rec["review_required"] = True
                rec["source_confidence"] = SOURCE_CONFIDENCE
                buckets["labels"].append(rec)
    return {key: values[:80] for key, values in buckets.items()}


def _element_from_evidence(item: Dict[str, Any], element_type: str, index: int) -> Dict[str, Any]:
    text = safe_str(item.get("text"))
    bbox = safe_dict(item.get("bbox")) or None
    return {
        "element_id": _stable_id("sheet_element", element_type, index, item.get("page_index"), item.get("text"), prefix="pse"),
        "type": element_type,
        "page_index": int(item.get("page_index") or 0),
        "text": text,
        "original_text": text,
        "bbox": bbox,
        "original_bbox": deepcopy(bbox),
        "source_evidence_id": safe_str(item.get("evidence_id")),
        "source_confidence": SOURCE_CONFIDENCE,
        "review_status": "pending",
        "review_required": True,
        "editable": element_type not in {"stamp_or_seal_source_imagery"},
        "construction_release_allowed": False,
        "truth_label": TRUTH_LABEL,
    }


def build_editable_sheet_from_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    classifications = safe_dict(analysis.get("classifications"))
    elements: List[Dict[str, Any]] = []
    mapping = {
        "labels": "text_label",
        "note_blocks": "note",
        "dimensions": "dimension",
        "detail_blocks": "detail_block",
        "title_blocks": "title_block_field",
        "scale_candidates": "scale_calibration_candidate",
        "elevation_callouts": "elevation_callout",
        "matchlines": "matchline",
        "stamp_or_seal_source_imagery": "stamp_or_seal_source_imagery",
    }
    for bucket, element_type in mapping.items():
        for item in safe_list(classifications.get(bucket)):
            elements.append(_element_from_evidence(safe_dict(item), element_type, len(elements)))
    linework_candidates: List[Dict[str, Any]] = []
    if safe_list(classifications.get("dimensions")) or safe_list(classifications.get("scale_candidates")):
        linework_candidates.append(
            {
                "element_id": _stable_id("linework", analysis.get("source_pdf", {}).get("sha256"), prefix="pse"),
                "type": "linework_geometry_candidate",
                "page_index": 0,
                "source_confidence": SOURCE_CONFIDENCE,
                "review_status": "pending",
                "review_required": True,
                "editable": False,
                "geometry": None,
                "blockers": ["Vector/linework extraction is not available without a configured PDF vector parser."],
                "truth_label": TRUTH_LABEL,
            }
        )
    elements.extend(linework_candidates)
    counts: Dict[str, int] = {}
    for element in elements:
        counts[element["type"]] = counts.get(element["type"], 0) + 1
    return {
        "version": EDITABLE_VERSION,
        "source_analysis_id": safe_str(analysis.get("analysis_id")),
        "source_pdf_id": safe_str(safe_dict(analysis.get("source_pdf")).get("source_pdf_id")),
        "source_confidence": SOURCE_CONFIDENCE,
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": TRUTH_LABEL,
        "elements": elements,
        "change_log": [],
        "summary": {
            "element_count": len(elements),
            "counts_by_type": counts,
            "editable_count": len([item for item in elements if item.get("editable")]),
            "pending_review_count": len([item for item in elements if item.get("review_required")]),
            "accepted_count": 0,
            "rejected_count": 0,
            "changed_count": 0,
            "moved_count": 0,
            "text_edit_count": 0,
        },
    }


def analyze_plan_pdf(
    path: Path,
    *,
    original_filename: str,
    stored_filename: str,
    file_url: str = "",
    content_type: str = "application/pdf",
    byte_count: Optional[int] = None,
) -> Dict[str, Any]:
    source_pdf_id = _stable_id("source_pdf", stored_filename, original_filename, path.stat().st_size, prefix="pdfsrc")
    pages, text_evidence, extraction_blockers = _extract_with_pypdf(path)
    if not pages:
        fallback_count = _fallback_page_count(path)
        pages = [
            {
                "page_index": idx,
                "page_number": idx + 1,
                "width": None,
                "height": None,
                "rotation": 0,
                "size_units": "unknown",
                "embedded_text_present": False,
                "embedded_text_excerpt": "",
                "preview_url": "",
                "preview_status": "blocked",
                "preview_blocker": "PDF page metadata requires pypdf or another configured PDF parser.",
            }
            for idx in range(fallback_count)
        ]
    evidence_records = [item.to_dict() for item in text_evidence]
    classifications = _classify_evidence(evidence_records)
    blockers = list(extraction_blockers)
    if not evidence_records:
        blockers.append("ocr_fallback_blocked:no_ocr_engine_configured")
    blockers.extend(
        [
            "raster_preview_blocked:no_pdf_renderer_configured",
            "vector_geometry_extraction_blocked:no_vector_parser_configured",
            "field_use_release_blocked:pdf_import_is_source_imagery_only",
        ]
    )
    has_stamp = bool(classifications.get("stamp_or_seal_source_imagery"))
    analysis = {
        "version": ANALYSIS_VERSION,
        "analysis_id": _stable_id("analysis", stored_filename, _now(), prefix="pdfa"),
        "created_at": _now(),
        "source_confidence": SOURCE_CONFIDENCE,
        "review_required": True,
        "construction_release_allowed": False,
        "stamp_seal_signature_policy": "source_imagery_only_protected_mark_area_not_editable",
        "contains_possible_stamp_seal_signature": has_stamp,
        "truth_label": TRUTH_LABEL,
        "source_pdf": {
            "source_pdf_id": source_pdf_id,
            "filename": original_filename,
            "stored_filename": stored_filename,
            "file_url": file_url,
            "content_type": content_type,
            "byte_count": int(byte_count or path.stat().st_size),
            "sha256": _file_sha256(path),
        },
        "page_count": len(pages),
        "pages": pages,
        "raw_text_evidence": evidence_records[:500],
        "classifications": classifications,
        "blockers": blockers,
        "summary": {
            "embedded_text_found": bool(evidence_records),
            "text_evidence_count": len(evidence_records),
            "title_block_count": len(classifications.get("title_blocks", [])),
            "note_block_count": len(classifications.get("note_blocks", [])),
            "detail_block_count": len(classifications.get("detail_blocks", [])),
            "dimension_count": len(classifications.get("dimensions", [])),
            "label_count": len(classifications.get("labels", [])),
            "elevation_callout_count": len(classifications.get("elevation_callouts", [])),
            "scale_candidate_count": len(classifications.get("scale_candidates", [])),
            "matchline_count": len(classifications.get("matchlines", [])),
            "possible_stamp_seal_signature_count": len(classifications.get("stamp_or_seal_source_imagery", [])),
        },
    }
    analysis["editable_sheet"] = build_editable_sheet_from_analysis(analysis)
    return analysis


def merge_plan_pdf_analysis_into_meta(meta: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(meta or {})
    analyses = [safe_dict(item) for item in safe_list(updated.get("plan_pdf_analyses_v1")) if safe_dict(item)]
    analyses = [item for item in analyses if safe_str(safe_dict(item.get("source_pdf")).get("source_pdf_id")) != safe_str(safe_dict(analysis.get("source_pdf")).get("source_pdf_id"))]
    analyses.append(analysis)
    updated["plan_pdf_analysis_v1"] = analysis
    updated["plan_pdf_analyses_v1"] = analyses[-10:]
    updated["plan_pdf_editable_sheet_v1"] = safe_dict(analysis.get("editable_sheet"))
    entries = safe_list(safe_dict(updated.get("source_confidence_map_v1")).get("entries"))
    source = safe_dict(analysis.get("source_pdf"))
    entries.append(
        {
            "entry_id": safe_str(source.get("source_pdf_id")) or _stable_id("source_confidence_pdf", source.get("filename"), prefix="scm"),
            "label": safe_str(source.get("filename"), "Plan PDF"),
            "category": "source",
            "object_id": safe_str(source.get("source_pdf_id")),
            "source_type": SOURCE_CONFIDENCE,
            "source_name": "Uploaded plan PDF",
            "confidence_score": 0.35,
            "confidence_band": "review",
            "visible_badge": "PDF review required",
            "status": "review_required",
            "accepted": False,
            "verified": False,
            "needs_verification": True,
            "needs_survey_control": True,
            "low_confidence_reasons": safe_list(analysis.get("blockers")),
            "why_low_confidence": "PDF extraction is imported source evidence and needs reviewer verification.",
            "next_action": "Review extracted sheet elements and accept/reject candidates before relying on them.",
            "construction_release_allowed": False,
            "construction_readiness_implied": False,
            "truth_label": TRUTH_LABEL,
        }
    )
    updated["source_confidence_map_v1"] = {
        "version": "source_confidence_map_v1",
        "generated_on": time.strftime("%Y-%m-%d"),
        "entries": entries[-100:],
        "summary": {
            "entry_count": len(entries[-100:]),
            "counts_by_source_type": {SOURCE_CONFIDENCE: len([item for item in entries[-100:] if safe_str(safe_dict(item).get("source_type")) == SOURCE_CONFIDENCE])},
            "counts_by_confidence_band": {"review": len(entries[-100:])},
            "low_confidence_count": len(entries[-100:]),
            "needs_survey_control_count": len(entries[-100:]),
        },
        "construction_release_allowed": False,
        "truth_label": TRUTH_LABEL,
    }
    return updated


def _bbox_changed(element: Dict[str, Any]) -> bool:
    bbox = safe_dict(element.get("bbox"))
    original = safe_dict(element.get("original_bbox"))
    if not bbox and not original:
        return False
    return bbox != original


def _element_changed(element: Dict[str, Any]) -> bool:
    return (
        safe_str(element.get("text")) != safe_str(element.get("original_text"))
        or _bbox_changed(element)
        or safe_str(element.get("review_status"), "pending") in {"accepted", "rejected"}
    )


def _changed_element_record(element: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "element_id": safe_str(element.get("element_id")),
        "type": safe_str(element.get("type")),
        "page_index": int(element.get("page_index") or 0),
        "original_text": safe_str(element.get("original_text")),
        "text": safe_str(element.get("text")),
        "original_bbox": safe_dict(element.get("original_bbox")) or None,
        "bbox": safe_dict(element.get("bbox")) or None,
        "review_status": safe_str(element.get("review_status"), "pending"),
        "changed_text": safe_str(element.get("text")) != safe_str(element.get("original_text")),
        "moved": _bbox_changed(element),
        "review_required": True,
        "source_confidence": SOURCE_CONFIDENCE,
    }


def _sheet_change_summary(elements: List[Dict[str, Any]], change_log: List[Dict[str, Any]]) -> Dict[str, Any]:
    changed = [_changed_element_record(item) for item in elements if _element_changed(item)]
    return {
        "version": "plan_pdf_changed_elements_v1",
        "source_confidence": SOURCE_CONFIDENCE,
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": TRUTH_LABEL,
        "changed_count": len(changed),
        "accepted_count": len([item for item in elements if safe_str(item.get("review_status")) == "accepted"]),
        "rejected_count": len([item for item in elements if safe_str(item.get("review_status")) == "rejected"]),
        "moved_count": len([item for item in changed if item.get("moved")]),
        "text_edit_count": len([item for item in changed if item.get("changed_text")]),
        "elements": changed,
        "change_log": change_log[-100:],
    }


def update_editable_sheet_element(meta: Dict[str, Any], element_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(meta or {})
    sheet = safe_dict(updated.get("plan_pdf_editable_sheet_v1"))
    if not sheet:
        raise ValueError("No editable PDF sheet is available on this project.")
    elements = [safe_dict(item) for item in safe_list(sheet.get("elements")) if safe_dict(item)]
    change_log = [safe_dict(item) for item in safe_list(sheet.get("change_log")) if safe_dict(item)]
    found = False
    for element in elements:
        if safe_str(element.get("element_id")) != element_id:
            continue
        found = True
        if safe_str(element.get("type")) == "stamp_or_seal_source_imagery":
            raise ValueError("Protected professional mark imagery cannot be edited.")
        if element.get("editable") is False and any(key in updates for key in ("text", "bbox", "move_target")):
            raise ValueError("This PDF-derived element is not editable.")
        before = deepcopy(element)
        if "text" in updates:
            element["text"] = safe_str(updates.get("text"))
        if "review_status" in updates:
            status = safe_str(updates.get("review_status")).lower()
            if status not in {"pending", "accepted", "rejected"}:
                raise ValueError("review_status must be pending, accepted, or rejected.")
            element["review_status"] = status
        if "move_target" in updates:
            target = safe_dict(updates.get("move_target"))
            bbox = safe_dict(element.get("bbox"))
            if not bbox:
                raise ValueError("This PDF-derived element has no extracted bounds to move.")
            try:
                target_x = float(target["x0"])
                target_y = float(target["y0"])
            except Exception as exc:
                raise ValueError("Moving a PDF-derived element requires explicit target x0/y0 coordinates.") from exc
            width = max(1.0, float(bbox.get("x1", target_x + 1.0)) - float(bbox.get("x0", target_x)))
            height = max(1.0, float(bbox.get("y1", target_y + 1.0)) - float(bbox.get("y0", target_y)))
            element["bbox"] = {
                "x0": round(target_x, 3),
                "y0": round(target_y, 3),
                "x1": round(target_x + width, 3),
                "y1": round(target_y + height, 3),
            }
        if "bbox" in updates and isinstance(updates.get("bbox"), dict):
            element["bbox"] = safe_dict(updates.get("bbox"))
        element["review_required"] = True
        element["source_confidence"] = SOURCE_CONFIDENCE
        element["construction_release_allowed"] = False
        changed_fields = [
            field
            for field in ("text", "bbox", "review_status")
            if safe_dict(before.get(field)) != safe_dict(element.get(field))
            or safe_str(before.get(field)) != safe_str(element.get(field))
        ]
        if changed_fields:
            change_log.append(
                {
                    "changed_at": _now(),
                    "element_id": element_id,
                    "changed_fields": sorted(set(changed_fields)),
                    "before": {
                        "text": safe_str(before.get("text")),
                        "bbox": safe_dict(before.get("bbox")) or None,
                        "review_status": safe_str(before.get("review_status"), "pending"),
                    },
                    "after": {
                        "text": safe_str(element.get("text")),
                        "bbox": safe_dict(element.get("bbox")) or None,
                        "review_status": safe_str(element.get("review_status"), "pending"),
                    },
                    "review_required": True,
                    "source_confidence": SOURCE_CONFIDENCE,
                }
            )
    if not found:
        raise ValueError("Editable PDF sheet element was not found.")
    sheet["elements"] = elements
    sheet["change_log"] = change_log[-100:]
    changed_report = _sheet_change_summary(elements, change_log)
    sheet["summary"] = {
        **safe_dict(sheet.get("summary")),
        "element_count": len(elements),
        "editable_count": len([item for item in elements if item.get("editable")]),
        "pending_review_count": len([item for item in elements if safe_str(item.get("review_status")) not in {"accepted", "rejected"}]),
        "accepted_count": changed_report["accepted_count"],
        "rejected_count": changed_report["rejected_count"],
        "changed_count": changed_report["changed_count"],
        "moved_count": changed_report["moved_count"],
        "text_edit_count": changed_report["text_edit_count"],
    }
    sheet["changed_elements"] = changed_report
    updated["plan_pdf_editable_sheet_v1"] = sheet
    updated["plan_pdf_changed_elements_v1"] = changed_report
    analysis = safe_dict(updated.get("plan_pdf_analysis_v1"))
    if analysis:
        analysis["editable_sheet"] = sheet
        updated["plan_pdf_analysis_v1"] = analysis
    return updated


def plan_pdf_report(meta: Dict[str, Any]) -> Dict[str, Any]:
    analysis = safe_dict(meta.get("plan_pdf_analysis_v1"))
    sheet = safe_dict(meta.get("plan_pdf_editable_sheet_v1"))
    changed = safe_dict(meta.get("plan_pdf_changed_elements_v1")) or safe_dict(sheet.get("changed_elements"))
    return {
        "version": "plan_pdf_extraction_report_v1",
        "source_confidence": SOURCE_CONFIDENCE,
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": TRUTH_LABEL,
        "analysis": analysis,
        "editable_sheet": sheet,
        "changed_elements": changed,
        "review_only_edited_sheet_export": {
            "version": "plan_pdf_review_only_edited_sheet_export_v1",
            "source_confidence": SOURCE_CONFIDENCE,
            "review_required": True,
            "construction_release_allowed": False,
            "truth_label": TRUTH_LABEL,
            "elements": safe_list(sheet.get("elements")),
            "changed_elements": safe_list(changed.get("elements")),
            "blocked_capabilities": safe_list(analysis.get("blockers")),
        },
        "blocked_capabilities": safe_list(analysis.get("blockers")),
    }


def report_json_bytes(meta: Dict[str, Any]) -> bytes:
    return json.dumps(plan_pdf_report(meta), indent=2, sort_keys=True).encode("utf-8")
