from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from .common import safe_dict, safe_list, safe_str


PLOTTING_STANDARDS_VERSION = "paper_model_plotting_standards_v1"
REVIEW_WATERMARK = "REVIEW ONLY - NOT FOR CONSTRUCTION"


def _title_block_fields(meta: Dict[str, Any]) -> List[str]:
    template = safe_dict(meta.get("active_customer_template") or meta.get("customer_template"))
    title_block = safe_dict(safe_dict(template.get("sections")).get("title_block"))
    fields = [safe_str(item) for item in safe_list(title_block.get("fields")) if safe_str(item)]
    if fields:
        return fields
    return ["project_name", "project_number", "sheet_title", "sheet_number", "drawn_by", "checked_by", "date", "revision"]


def _sheet_records(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    registry = meta.get("sheet_registry")
    if isinstance(registry, list):
        records = registry
    else:
        registry_dict = safe_dict(registry)
        records = safe_list(registry_dict.get("sheets") or registry_dict.get("registry"))
    if not records:
        records = [
            {"sheet_id": "R-01", "title": "REVIEW SITE PLAN"},
            {"sheet_id": "R-02", "title": "REVIEW PROFILES AND SECTIONS"},
        ]
    out: List[Dict[str, Any]] = []
    for index, item in enumerate(records, start=1):
        rec = safe_dict(item)
        sheet_id = safe_str(rec.get("sheet_id") or rec.get("id") or rec.get("sheet_number"), f"R-{index:02d}")
        title = safe_str(rec.get("title") or rec.get("layout_name") or rec.get("name"), f"Review Sheet {index}")
        out.append(
            {
                "sheet_id": sheet_id,
                "sheet_number": sheet_id,
                "title": title,
                "layout_mode": "sheet_layout",
                "model_space_reference": safe_str(rec.get("canonical_model_id") or meta.get("canonical_model_id") or meta.get("model_id")),
                "current": rec.get("current", True) is not False,
                "review_only": True,
                "construction_release_allowed": False,
            }
        )
    return out


def _viewport_records(sheets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    viewports = []
    for index, sheet in enumerate(sheets, start=1):
        scale = "1:50" if index == 1 else "1:100"
        viewports.append(
            {
                "viewport_id": f"{sheet['sheet_id']}-VP1",
                "sheet_id": sheet["sheet_id"],
                "label": "Model view viewport" if index == 1 else "Profile/section review viewport",
                "mode": "paper_space_viewport",
                "model_space_view": "civil_model_space",
                "view_target": "overall site plan" if index == 1 else "profile and cross-section deliverables",
                "scale": scale,
                "scale_locked": True,
                "layer_visibility": {
                    "C-ANNO": True,
                    "C-ROAD": True,
                    "C-PIPE-STORM": True,
                    "C-UTIL": True,
                    "X-REFERENCE": index == 1,
                },
                "north_arrow": True,
                "scale_bar": True,
                "review_only": True,
                "construction_release_allowed": False,
            }
        )
    return viewports


def build_plotting_standards(meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(meta)
    existing = safe_dict(meta.get(PLOTTING_STANDARDS_VERSION) or meta.get("plotting_standards"))
    if existing:
        return deepcopy(existing)
    sheets = _sheet_records(meta)
    viewports = _viewport_records(sheets)
    title_fields = _title_block_fields(meta)
    sheet_index = [
        {
            "sheet_id": sheet["sheet_id"],
            "sheet_number": sheet["sheet_number"],
            "title": sheet["title"],
            "review_only": True,
            "construction_release_allowed": False,
        }
        for sheet in sheets
    ]
    revision_history = safe_list(meta.get("sheet_revision_history") or meta.get("revision_history"))
    if not revision_history:
        revision_history = [
            {
                "revision": safe_str(meta.get("revision") or meta.get("canonical_revision"), "REV-REVIEW"),
                "note": "Initial review sheet package generated for licensed/user review.",
                "review_required": True,
                "civora_approval": False,
            }
        ]
    return {
        "version": PLOTTING_STANDARDS_VERSION,
        "workspace_modes": {
            "model_space": {
                "purpose": "source civil geometry and annotations in model coordinates",
                "editable_geometry_space": True,
                "plotted_sheet_space": False,
            },
            "sheet_layout": {
                "purpose": "paper/layout composition with viewports into model space",
                "editable_geometry_space": False,
                "plotted_sheet_space": True,
            },
        },
        "sheet_manager": {
            "sheet_count": len(sheets),
            "active_sheet_id": sheets[0]["sheet_id"] if sheets else "",
            "sheets": sheets,
            "sheet_index": sheet_index,
            "table_of_contents": sheet_index,
        },
        "viewports": viewports,
        "plot_styles": {
            "lineweight_color_linetype_mapping": [
                {"layer": "C-ROAD", "color": "black", "lineweight": "0.35mm", "linetype": "CONTINUOUS"},
                {"layer": "C-PIPE-STORM", "color": "green", "lineweight": "0.25mm", "linetype": "DASHED"},
                {"layer": "C-UTIL", "color": "blue", "lineweight": "0.25mm", "linetype": "DASHED"},
                {"layer": "C-ANNO", "color": "black", "lineweight": "0.18mm", "linetype": "CONTINUOUS"},
            ],
            "grayscale_option": True,
            "review_watermark": REVIEW_WATERMARK,
            "plot_output_status": "review_only_print_package",
        },
        "title_block": {
            "source": "customer_template" if safe_dict(meta.get("active_customer_template") or meta.get("customer_template")) else "civora_review_default",
            "fields": title_fields,
            "review_required": True,
            "construction_release_allowed": False,
        },
        "revision_block": {
            "history": deepcopy(revision_history),
            "review_history_required": True,
            "civora_approval": False,
        },
        "exports": {
            "review_pdf_print_package": True,
            "sheet_json": True,
            "approved_construction_documents": False,
            "submission_ready": False,
        },
        "limitations": {
            "review_only": True,
            "engineer_review_required": True,
            "civora_signoff_allowed": False,
            "construction_release_allowed": False,
            "truth_label": "Sheets and plots are review-only production aids, not approved construction documents.",
        },
    }


__all__ = ["PLOTTING_STANDARDS_VERSION", "REVIEW_WATERMARK", "build_plotting_standards"]
