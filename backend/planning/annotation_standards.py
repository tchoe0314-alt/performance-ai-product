from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from .common import safe_dict, safe_list, safe_str


ANNOTATION_STANDARDS_VERSION = "annotation_standards_v1"


DEFAULT_ANNOTATION_STANDARDS: Dict[str, Any] = {
    "dimension_styles": [
        {
            "key": "linear_feet",
            "kind": "linear",
            "precision": 2,
            "units": "ft",
            "prefix": "",
            "suffix": "'",
            "scale_behavior": "paper_space_constant_model_space_scaled",
            "layer": "C-ANNO-DIMS",
        },
        {
            "key": "aligned_feet",
            "kind": "aligned",
            "precision": 2,
            "units": "ft",
            "prefix": "",
            "suffix": "'",
            "scale_behavior": "paper_space_constant_model_space_scaled",
            "layer": "C-ANNO-DIMS",
        },
        {
            "key": "angular_degrees",
            "kind": "angular",
            "precision": 1,
            "units": "deg",
            "prefix": "",
            "suffix": " deg",
            "scale_behavior": "paper_space_constant_model_space_scaled",
            "layer": "C-ANNO-DIMS",
        },
    ],
    "text_styles": [
        {
            "key": "plan_label",
            "family": "Arial",
            "size": 0.10,
            "size_units": "in_paper",
            "rotation": "object_or_sheet_readable",
            "alignment": "middle_center",
            "layer": "C-ANNO-TEXT",
        },
        {
            "key": "callout",
            "family": "Arial",
            "size": 0.12,
            "size_units": "in_paper",
            "rotation": "sheet_readable",
            "alignment": "left",
            "leader_style": "arrow_closed_filled",
            "layer": "C-ANNO-CALL",
        },
    ],
    "leader_callout_styles": [
        {
            "key": "object_callout",
            "leader_type": "straight",
            "arrowhead": "closed_filled",
            "landing": True,
            "connected_to_objects": True,
            "layer": "C-ANNO-CALL",
        }
    ],
    "hatch_fill_styles": [
        {"target": "pavement", "pattern": "ANSI31", "scale": 1.0, "layer": "C-HATCH-PAVE"},
        {"target": "building", "pattern": "SOLID", "scale": 1.0, "layer": "C-HATCH-BLDG"},
        {"target": "basin", "pattern": "GRAVEL", "scale": 1.0, "layer": "C-HATCH-BASN"},
        {"target": "landscape", "pattern": "AR-SAND", "scale": 1.0, "layer": "C-HATCH-LAND"},
        {"target": "easement_constraint", "pattern": "DOTS", "scale": 1.0, "layer": "C-HATCH-ESMT"},
    ],
    "linetype_styles": [
        {"target": "existing", "linetype": "CONTINUOUS", "layer": "C-EXIST"},
        {"target": "proposed", "linetype": "CONTINUOUS", "layer": "C-PROP"},
        {"target": "utility", "linetype": "DASHED", "layer": "C-UTIL"},
        {"target": "row", "linetype": "PHANTOM", "layer": "C-ROW"},
        {"target": "easement", "linetype": "HIDDEN", "layer": "C-ESMT"},
        {"target": "existing_contours", "linetype": "DASHED", "layer": "C-TOPO-EG"},
        {"target": "proposed_contours", "linetype": "CONTINUOUS", "layer": "C-TOPO-FG"},
    ],
    "scale_rules": {
        "model_space": "labels store intended plotted height and compute model height from viewport scale",
        "sheet_viewports": "labels retain paper-space plotted size where sheet viewport scale is known",
    },
    "annotation_layers": ["C-ANNO-DIMS", "C-ANNO-TEXT", "C-ANNO-CALL"],
}


def _count(values: Any) -> int:
    return len(safe_list(values))


def build_annotation_standards_trace(
    meta: Dict[str, Any],
    *,
    active_template: Optional[Dict[str, Any]] = None,
    export_type: str = "",
) -> Dict[str, Any]:
    template = safe_dict(active_template) or safe_dict(meta.get("active_customer_template")) or safe_dict(meta.get("customer_template"))
    sections = safe_dict(template.get("sections"))
    template_standards = safe_dict(sections.get("annotation_standards"))
    standards = deepcopy(DEFAULT_ANNOTATION_STANDARDS)
    for key, value in template_standards.items():
        if value not in (None, "", [], {}):
            standards[key] = deepcopy(value)

    layer_names = {
        safe_str(layer.get("name"))
        for layer in safe_list(safe_dict(sections.get("layer_standards")).get("layers"))
        if safe_str(safe_dict(layer).get("name"))
    }
    symbol_blocks = safe_list(safe_dict(sections.get("symbol_library")).get("blocks"))
    label_styles = safe_list(safe_dict(sections.get("label_style")).get("styles"))
    export_format = safe_str(export_type, "report")
    return {
        "version": ANNOTATION_STANDARDS_VERSION,
        "source": "customer_template" if template_standards else "civora_workspace_defaults",
        "template_id": safe_str(template.get("template_id")),
        "template_review_status": safe_str(template.get("review_status"), "missing"),
        "template_accepted_for_workspace": bool(template.get("accepted_for_workspace")),
        "supported_annotation_styles": {
            "dimension_kinds": [safe_str(item.get("kind")) for item in safe_list(standards.get("dimension_styles")) if safe_str(safe_dict(item).get("kind"))],
            "text_style_count": _count(standards.get("text_styles")),
            "leader_callout_style_count": _count(standards.get("leader_callout_styles")),
            "hatch_targets": [safe_str(item.get("target")) for item in safe_list(standards.get("hatch_fill_styles")) if safe_str(safe_dict(item).get("target"))],
            "linetype_targets": [safe_str(item.get("target")) for item in safe_list(standards.get("linetype_styles")) if safe_str(safe_dict(item).get("target"))],
            "symbol_block_count": len(symbol_blocks),
            "label_style_count": len(label_styles),
        },
        "dimension_styles": deepcopy(safe_list(standards.get("dimension_styles"))),
        "text_styles": deepcopy(safe_list(standards.get("text_styles"))),
        "leader_callout_styles": deepcopy(safe_list(standards.get("leader_callout_styles"))),
        "hatch_fill_styles": deepcopy(safe_list(standards.get("hatch_fill_styles"))),
        "linetype_styles": deepcopy(safe_list(standards.get("linetype_styles"))),
        "scale_rules": deepcopy(safe_dict(standards.get("scale_rules"))),
        "annotation_layers": deepcopy(safe_list(standards.get("annotation_layers"))),
        "template_backed_behavior": {
            "uses_customer_layers_when_present": bool(layer_names),
            "uses_customer_label_styles_when_present": bool(label_styles),
            "uses_customer_symbol_blocks_when_present": bool(symbol_blocks),
            "customer_layer_names": sorted(layer_names),
            "symbol_blocks": deepcopy(symbol_blocks),
        },
        "export_support": {
            "sheet": "supported_as_review_annotation_metadata",
            "report": "supported_as_trace_metadata",
            "dxf": "supported_where_exporter_maps layers, linetypes, text, blocks, and hatch records; not a Civil3D style database",
            "requested_export_type": export_format,
        },
        "review_required": True,
        "engineer_review_required": True,
        "construction_release_allowed": False,
        "truth_label": "Annotation, dimensions, labels, hatches, linetypes, and symbols are drafting/review aids unless backed by accepted standards and engineer review.",
    }


def annotation_chat_response_payload(message: str, meta: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    normalized = " ".join(str(message or "").strip().lower().split())
    if not normalized:
        return None
    intents = {
        "add_dimensions": ("add dimensions" in normalized or "add dimension" in normalized),
        "make_labels_bigger": ("make labels bigger" in normalized or "make the labels bigger" in normalized or "increase label" in normalized),
        "use_company_label_style": ("use my company label style" in normalized or "company label style" in normalized),
        "show_proposed_utilities_dashed": ("show proposed utilities dashed" in normalized or "utilities dashed" in normalized),
        "add_hatch_to_parking": ("add hatch to parking" in normalized or "hatch parking" in normalized),
    }
    action = next((key for key, matched in intents.items() if matched), "")
    if not action:
        return None
    trace = build_annotation_standards_trace(safe_dict(meta), export_type="chat")
    messages = {
        "add_dimensions": "I can add review dimensions using linear, aligned, and angular styles where geometry supports them, with precision, units, prefix/suffix, scale behavior, and annotation layers tracked.",
        "make_labels_bigger": "I can increase label plotted size through the text style settings while preserving scale-aware model/sheet behavior.",
        "use_company_label_style": "I can use the active company label style when the customer template is accepted for the workspace; otherwise it stays a review-required template candidate.",
        "show_proposed_utilities_dashed": "I can map proposed utility annotations to the utility linetype style, typically dashed, and keep that layer/style traceable.",
        "add_hatch_to_parking": "I can apply the pavement/parking hatch style to parking areas as a drafting aid and trace the hatch target into sheet/report/DXF metadata where supported.",
    }
    return {
        "action": action,
        "assistant_message": (
            f"{messages[action]} These are drafting/review aids, not jurisdiction compliance or construction release."
        ),
        "trace": trace,
    }

