from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from .common import safe_dict, safe_list, safe_str


SYMBOL_LIBRARY_VERSION = "symbol_block_library_v1"
SYMBOL_TRACE_VERSION = "symbol_block_reference_trace_v1"
SYMBOL_ATTRIBUTE_FIELDS = ["id", "label", "elevation", "material", "size", "source", "review_note"]
SUPPORTED_SYMBOL_KINDS = [
    "hydrant",
    "inlet",
    "manhole",
    "valve",
    "tree",
    "light",
    "sign",
    "utility_marker",
    "benchmark",
    "note_callout",
]
SYMBOL_LABELS = {
    "hydrant": "Hydrant",
    "inlet": "Inlet",
    "manhole": "Manhole",
    "valve": "Valve",
    "tree": "Tree",
    "light": "Light",
    "sign": "Sign",
    "utility_marker": "Utility marker",
    "benchmark": "Benchmark",
    "note_callout": "Note / callout",
}


def _unique(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _symbol_id(kind: str) -> str:
    return safe_str(kind).lower().replace("-", "_").replace(" ", "_")


def _default_symbol_block(kind: str) -> Dict[str, Any]:
    symbol_id = _symbol_id(kind)
    return {
        "block_id": f"civora_{symbol_id}",
        "symbol_id": symbol_id,
        "kind": symbol_id,
        "name": SYMBOL_LABELS.get(symbol_id, symbol_id.replace("_", " ").title()),
        "attribute_fields": list(SYMBOL_ATTRIBUTE_FIELDS),
        "source": "civora_default_review_aid",
        "source_confidence": "draft_review_required",
        "review_required": True,
        "construction_release_allowed": False,
        "native_dwg_block_parity": False,
    }


def default_symbol_library() -> Dict[str, Any]:
    return {
        "version": SYMBOL_LIBRARY_VERSION,
        "source": "civora_default_review_aid",
        "blocks": [_default_symbol_block(kind) for kind in SUPPORTED_SYMBOL_KINDS],
        "attribute_fields": list(SYMBOL_ATTRIBUTE_FIELDS),
        "manager_behavior": {
            "supports_insert": True,
            "supports_attribute_edit": True,
            "supports_candidate_conversion": True,
            "supports_source_only_references": True,
            "native_dwg_block_parity": False,
            "native_xref_parity": False,
            "truth_label": "Symbols, blocks, and references are drafting/review aids unless backed by accepted external source evidence.",
        },
    }


def normalize_symbol_library(template: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    template = safe_dict(template)
    sections = safe_dict(template.get("sections"))
    raw_library = safe_dict(template.get("symbol_library") or sections.get("symbol_library"))
    defaults = default_symbol_library()
    raw_blocks = safe_list(raw_library.get("blocks")) or safe_list(raw_library.get("symbols"))
    blocks: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_blocks, start=1):
        rec = safe_dict(item)
        kind = _symbol_id(rec.get("kind") or rec.get("symbol_id") or rec.get("block_id") or rec.get("name"))
        if not kind:
            kind = f"custom_symbol_{index}"
        fields = _unique(safe_list(rec.get("attribute_fields") or rec.get("attributes")) + SYMBOL_ATTRIBUTE_FIELDS)
        blocks.append(
            {
                "block_id": safe_str(rec.get("block_id"), f"template_{kind}"),
                "symbol_id": safe_str(rec.get("symbol_id"), kind),
                "kind": kind,
                "name": safe_str(rec.get("name") or rec.get("label"), SYMBOL_LABELS.get(kind, kind.replace("_", " ").title())),
                "attribute_fields": fields,
                "layer": safe_str(rec.get("layer")),
                "source": safe_str(rec.get("source") or template.get("template_id"), "customer_template"),
                "source_confidence": safe_str(rec.get("source_confidence"), "customer_template_review_required"),
                "review_required": True,
                "construction_release_allowed": False,
                "native_dwg_block_parity": False,
            }
        )
    by_kind = {safe_str(item.get("kind")): item for item in blocks}
    for default in defaults["blocks"]:
        if safe_str(default.get("kind")) not in by_kind:
            blocks.append(default)
    return {
        "version": SYMBOL_LIBRARY_VERSION,
        "source": "customer_template" if raw_blocks else "civora_default_review_aid",
        "template_id": safe_str(template.get("template_id")),
        "blocks": blocks,
        "attribute_fields": list(SYMBOL_ATTRIBUTE_FIELDS),
        "supported_symbol_kinds": list(SUPPORTED_SYMBOL_KINDS),
        "manager_behavior": deepcopy(defaults["manager_behavior"]),
    }


def build_symbol_instance(
    kind: str,
    *,
    attributes: Optional[Dict[str, Any]] = None,
    source: str = "manual_drawn",
    source_confidence: str = "user_drawn_review_required",
    origin: str = "chat_or_canvas_insert",
) -> Dict[str, Any]:
    symbol_kind = _symbol_id(kind)
    attrs = {field: safe_str(safe_dict(attributes).get(field)) for field in SYMBOL_ATTRIBUTE_FIELDS}
    attrs["label"] = attrs["label"] or SYMBOL_LABELS.get(symbol_kind, symbol_kind.replace("_", " ").title())
    attrs["source"] = attrs["source"] or source
    return {
        "schema_version": SYMBOL_TRACE_VERSION,
        "symbol_id": safe_str(attrs["id"], f"{symbol_kind}-draft"),
        "kind": symbol_kind,
        "block_id": f"civora_{symbol_kind}",
        "label": attrs["label"],
        "attributes": attrs,
        "source": source,
        "source_confidence": source_confidence,
        "origin": origin,
        "editable_attributes": list(SYMBOL_ATTRIBUTE_FIELDS),
        "manual_drawn": source == "manual_drawn",
        "engineering_status": "draft_review_required",
        "review_required": True,
        "construction_release_allowed": False,
        "native_dwg_block_parity": False,
    }


def convert_candidate_to_symbol(candidate: Dict[str, Any], kind: str = "") -> Dict[str, Any]:
    rec = safe_dict(candidate)
    symbol_kind = _symbol_id(kind or rec.get("kind") or rec.get("candidate_type") or "utility_marker")
    attrs = {
        "id": safe_str(rec.get("candidate_id") or rec.get("id"), f"{symbol_kind}-candidate"),
        "label": safe_str(rec.get("label") or rec.get("name"), SYMBOL_LABELS.get(symbol_kind, "Utility marker")),
        "elevation": safe_str(rec.get("elevation") or rec.get("elevation_ft")),
        "material": safe_str(rec.get("material")),
        "size": safe_str(rec.get("size") or rec.get("diameter") or rec.get("diameter_in")),
        "source": safe_str(rec.get("source") or rec.get("provider"), "imported_candidate"),
        "review_note": safe_str(rec.get("review_note") or rec.get("blocker_review_reason"), "Converted candidate remains draft/review-required."),
    }
    symbol = build_symbol_instance(
        symbol_kind,
        attributes=attrs,
        source=safe_str(rec.get("source"), "imported_candidate"),
        source_confidence=safe_str(rec.get("source_confidence") or rec.get("confidence"), "candidate_review_required"),
        origin="candidate_conversion",
    )
    symbol["converted_from_candidate"] = True
    symbol["candidate_id"] = attrs["id"]
    symbol["manual_drawn"] = False
    return symbol


def build_reference_underlay(record: Dict[str, Any]) -> Dict[str, Any]:
    rec = safe_dict(record)
    file_type = safe_str(rec.get("file_type") or rec.get("type") or rec.get("format"), "external")
    editable = bool(rec.get("editable"))
    return {
        "reference_id": safe_str(rec.get("reference_id") or rec.get("id"), f"{file_type}-underlay"),
        "label": safe_str(rec.get("label") or rec.get("name"), f"{file_type.upper()} underlay"),
        "file_type": file_type.lower(),
        "source": safe_str(rec.get("source") or rec.get("uri") or rec.get("path")),
        "source_confidence": safe_str(rec.get("source_confidence") or rec.get("confidence"), "source_underlay_review_required"),
        "not_editable": not editable,
        "source_only": not editable,
        "review_required": True,
        "construction_release_allowed": False,
        "native_xref_parity": False,
        "truth_label": "External PDF/DXF/image references are underlay/source context until reviewed against accepted evidence.",
    }


def build_symbol_block_reference_trace(meta: Dict[str, Any]) -> Dict[str, Any]:
    template = safe_dict(meta.get("active_customer_template") or meta.get("customer_template"))
    library = normalize_symbol_library(template)
    symbol_instances: List[Dict[str, Any]] = []
    for key in ("symbol_instances", "block_instances", "cad_symbol_instances"):
        for item in safe_list(meta.get(key)):
            rec = safe_dict(item)
            if rec:
                symbol_instances.append(rec if rec.get("schema_version") == SYMBOL_TRACE_VERSION else build_symbol_instance(safe_str(rec.get("kind") or rec.get("cad_symbol") or "utility_marker"), attributes=safe_dict(rec.get("attributes") or rec)))
    for item in safe_list(meta.get("converted_symbol_candidates")):
        rec = safe_dict(item)
        if rec:
            symbol_instances.append(convert_candidate_to_symbol(rec, safe_str(rec.get("kind"))))
    references = []
    for key in ("reference_underlays", "xref_references", "external_references", "underlays"):
        for item in safe_list(meta.get(key)):
            rec = safe_dict(item)
            if rec:
                references.append(build_reference_underlay(rec))
    return {
        "version": SYMBOL_TRACE_VERSION,
        "symbol_library": library,
        "supported_symbols": list(SUPPORTED_SYMBOL_KINDS),
        "attribute_fields": list(SYMBOL_ATTRIBUTE_FIELDS),
        "symbol_instances": symbol_instances,
        "reference_underlays": references,
        "symbol_count": len(symbol_instances),
        "reference_count": len(references),
        "candidate_conversion_policy": {
            "imported_pdf_gis_cad_candidates_convert_to_symbols": "draft_review_required_only",
            "survey_backed_by_conversion": False,
            "engineer_review_required": True,
            "construction_release_allowed": False,
        },
        "export_support": {
            "dxf": "symbol/reference metadata is traceable where exporter and sidecar support it; native AutoCAD block/xref parity is not claimed",
            "dwg": "unsupported_no_native_writer",
            "report": "metadata trace included",
        },
        "native_dwg_block_parity": False,
        "native_xref_parity": False,
        "truth_label": "Blocks, symbols, and xref-like references are drafting/review aids only unless accepted external evidence backs them.",
    }


__all__ = [
    "SYMBOL_ATTRIBUTE_FIELDS",
    "SUPPORTED_SYMBOL_KINDS",
    "build_reference_underlay",
    "build_symbol_block_reference_trace",
    "build_symbol_instance",
    "convert_candidate_to_symbol",
    "default_symbol_library",
    "normalize_symbol_library",
]
