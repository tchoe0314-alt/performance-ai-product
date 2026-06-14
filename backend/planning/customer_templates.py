from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
import json
import re
from typing import Any, Dict, List, Optional


TEMPLATE_REGISTRY_VERSION = "customer_template_registry_v1"
TEMPLATE_EXPORT_VERSION = "customer_template_export_v1"
TEMPLATE_TYPES = {
    "layer_standards",
    "title_block",
    "label_style",
    "annotation_standards",
    "symbol_library",
    "report_template",
    "cost_book_link",
    "pipe_template_hook",
    "roadway_template_hook",
}
ACCEPTED_TEMPLATE_STATUSES = {"accepted_for_workspace", "company_reviewed"}
RELEASE_LANGUAGE = (
    "construction-ready",
    "construction ready",
    "stamp",
    "seal",
    "sealed",
    "signed",
    "sign",
    "certify",
    "certified",
    "approval",
    "approved for construction",
)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _normalized_id(value: str) -> str:
    raw = _safe_str(value).lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "template"


def _contains_release_language(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, default=str).lower()
    for term in RELEASE_LANGUAGE:
        if " " in term or "-" in term:
            if term in text:
                return True
            continue
        if re.search(rf"\b{re.escape(term)}\b", text):
            return True
    return False


def _section(template: Dict[str, Any], key: str) -> Dict[str, Any]:
    sections = _safe_dict(template.get("sections"))
    return _safe_dict(sections.get(key))


@dataclass
class CustomerTemplate:
    template_id: str
    name: str
    firm_id: str
    firm_name: str
    version: str = ""
    review_status: str = "needs_review"
    accepted_by: str = ""
    accepted_date: str = ""
    source_reference: str = ""
    sections: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CustomerTemplate":
        name = _safe_str(payload.get("name"), "Company template")
        firm_name = _safe_str(payload.get("firm_name") or payload.get("company"), "Company")
        return cls(
            template_id=_safe_str(payload.get("template_id"), f"{_normalized_id(firm_name)}_{_normalized_id(name)}"),
            name=name,
            firm_id=_safe_str(payload.get("firm_id"), _normalized_id(firm_name)),
            firm_name=firm_name,
            version=_safe_str(payload.get("version"), "draft"),
            review_status=_safe_str(payload.get("review_status"), "needs_review"),
            accepted_by=_safe_str(payload.get("accepted_by")),
            accepted_date=_safe_str(payload.get("accepted_date")),
            source_reference=_safe_str(payload.get("source_reference")),
            sections=_safe_dict(payload.get("sections")),
            notes=[_safe_str(item) for item in _safe_list(payload.get("notes")) if _safe_str(item)],
        )

    def accepted_for_workspace(self) -> bool:
        return self.review_status in ACCEPTED_TEMPLATE_STATUSES and bool(self.accepted_by and self.accepted_date)

    def validate(self) -> List[str]:
        issues: List[str] = []
        if not self.template_id:
            issues.append("template_id is required")
        if not self.name:
            issues.append("name is required")
        if not self.firm_name:
            issues.append("firm_name is required")
        if self.review_status not in ACCEPTED_TEMPLATE_STATUSES and self.review_status != "needs_review":
            issues.append("review_status must be needs_review, company_reviewed, or accepted_for_workspace")
        if self.review_status in ACCEPTED_TEMPLATE_STATUSES and not self.accepted_by:
            issues.append("accepted_by is required for accepted template status")
        if self.review_status in ACCEPTED_TEMPLATE_STATUSES and not self.accepted_date:
            issues.append("accepted_date is required for accepted template status")
        policy_free_payload = {
            "template_id": self.template_id,
            "name": self.name,
            "firm_id": self.firm_id,
            "firm_name": self.firm_name,
            "version": self.version,
            "review_status": self.review_status,
            "accepted_by": self.accepted_by,
            "accepted_date": self.accepted_date,
            "source_reference": self.source_reference,
            "sections": self.sections,
            "notes": self.notes,
        }
        if _contains_release_language(policy_free_payload):
            issues.append("template content cannot include construction-ready, stamp, seal, sign, certify, or approval wording")
        for section_key in self.sections:
            if section_key not in TEMPLATE_TYPES:
                issues.append(f"unsupported template section: {section_key}")
        return issues

    def to_dict(self, *, include_validation: bool = True) -> Dict[str, Any]:
        data = {
            "template_id": self.template_id,
            "name": self.name,
            "firm_id": self.firm_id,
            "firm_name": self.firm_name,
            "version": self.version,
            "review_status": self.review_status,
            "accepted_by": self.accepted_by,
            "accepted_date": self.accepted_date,
            "accepted_for_workspace": self.accepted_for_workspace(),
            "source_reference": self.source_reference,
            "sections": deepcopy(self.sections),
            "notes": list(self.notes),
            "policy": template_policy(),
        }
        if include_validation:
            data["validation_issues"] = self.validate()
        return data


def template_policy() -> Dict[str, Any]:
    return {
        "customer_standard_only": True,
        "jurisdiction_compliance_claim": False,
        "requires_explicit_company_acceptance": True,
        "release_language_blocked": list(RELEASE_LANGUAGE),
        "truth_label": "Templates are user/company standards only. Civora does not infer legal compliance or field-use readiness from template presence.",
    }


def sample_customer_template() -> Dict[str, Any]:
    return CustomerTemplate(
        template_id="civora_demo_company_template",
        name="Demo company CAD package",
        firm_id="civora_demo",
        firm_name="Civora Demo Firm",
        version="2026.06",
        review_status="needs_review",
        source_reference="local fixture for template manager testing",
        sections={
            "layer_standards": {
                "layers": [
                    {"name": "C-ROAD", "color": "gray", "lineweight": "0.35mm", "description": "Roadway and pavement geometry"},
                    {"name": "C-PIPE-STORM", "color": "green", "lineweight": "0.25mm", "description": "Storm pipe geometry"},
                    {"name": "C-ANNO", "color": "white", "lineweight": "0.18mm", "description": "Plan annotation"},
                ]
            },
            "title_block": {
                "sheet_size": "24x36",
                "fields": ["project_name", "project_number", "drawn_by", "checked_by", "revision"],
            },
            "label_style": {
                "styles": [
                    {"key": "pipe_callout", "format": "{network} {diameter_in} in {material}"},
                    {"key": "spot_grade", "format": "FG {elevation_ft}"},
                ]
            },
            "annotation_standards": {
                "dimension_styles": [
                    {"key": "linear_feet", "kind": "linear", "precision": 2, "units": "ft", "suffix": "'", "layer": "C-ANNO-DIMS"},
                    {"key": "aligned_feet", "kind": "aligned", "precision": 2, "units": "ft", "suffix": "'", "layer": "C-ANNO-DIMS"},
                    {"key": "angular_degrees", "kind": "angular", "precision": 1, "units": "deg", "suffix": " deg", "layer": "C-ANNO-DIMS"},
                ],
                "text_styles": [
                    {"key": "plan_label", "family": "Arial", "size": 0.10, "size_units": "in_paper", "alignment": "middle_center"},
                    {"key": "callout", "family": "Arial", "size": 0.12, "size_units": "in_paper", "alignment": "left"},
                ],
                "leader_callout_styles": [{"key": "object_callout", "connected_to_objects": True, "arrowhead": "closed_filled"}],
                "hatch_fill_styles": [
                    {"target": "pavement", "pattern": "ANSI31"},
                    {"target": "building", "pattern": "SOLID"},
                    {"target": "basin", "pattern": "GRAVEL"},
                    {"target": "landscape", "pattern": "AR-SAND"},
                    {"target": "easement_constraint", "pattern": "DOTS"},
                ],
                "linetype_styles": [
                    {"target": "existing", "linetype": "CONTINUOUS"},
                    {"target": "proposed", "linetype": "CONTINUOUS"},
                    {"target": "utility", "linetype": "DASHED"},
                    {"target": "row", "linetype": "PHANTOM"},
                    {"target": "easement", "linetype": "HIDDEN"},
                    {"target": "existing_contours", "linetype": "DASHED"},
                    {"target": "proposed_contours", "linetype": "CONTINUOUS"},
                ],
            },
            "symbol_library": {
                "blocks": [
                    {"block_id": "storm_inlet_plan", "name": "Storm inlet"},
                    {"block_id": "water_valve_plan", "name": "Water valve"},
                ]
            },
            "report_template": {
                "reports": [
                    {"key": "engineering_review_summary", "sections": ["inputs", "assumptions", "open_items", "quantities"]},
                ]
            },
            "cost_book_link": {
                "links": [
                    {"label": "Company unit price book", "cost_book_id": "demo_cost_book", "status": "needs_review"},
                ]
            },
            "pipe_template_hook": {
                "defaults": {"storm": {"label_style": "pipe_callout", "layer": "C-PIPE-STORM"}},
            },
            "roadway_template_hook": {
                "defaults": {"roadway_layer": "C-ROAD", "centerline_label_style": "station_offset"},
            },
        },
        notes=["Sample template for workflow testing; replace with firm-owned standards before relying on it."],
    ).to_dict()


def summarize_template(template: Dict[str, Any]) -> Dict[str, Any]:
    sections = _safe_dict(template.get("sections"))
    present = [key for key in TEMPLATE_TYPES if _safe_dict(sections.get(key))]
    missing = [key for key in TEMPLATE_TYPES if key not in present]
    return {
        "template_id": _safe_str(template.get("template_id")),
        "name": _safe_str(template.get("name")),
        "firm_name": _safe_str(template.get("firm_name")),
        "review_status": _safe_str(template.get("review_status"), "needs_review"),
        "accepted_for_workspace": bool(template.get("accepted_for_workspace")),
        "present_sections": present,
        "missing_sections": missing,
        "layer_count": len(_safe_list(_section(template, "layer_standards").get("layers"))),
        "title_block_count": 1 if _section(template, "title_block") else 0,
        "label_style_count": len(_safe_list(_section(template, "label_style").get("styles"))),
        "dimension_style_count": len(_safe_list(_section(template, "annotation_standards").get("dimension_styles"))),
        "text_style_count": len(_safe_list(_section(template, "annotation_standards").get("text_styles"))),
        "hatch_style_count": len(_safe_list(_section(template, "annotation_standards").get("hatch_fill_styles"))),
        "linetype_style_count": len(_safe_list(_section(template, "annotation_standards").get("linetype_styles"))),
        "symbol_count": len(_safe_list(_section(template, "symbol_library").get("blocks"))),
        "report_template_count": len(_safe_list(_section(template, "report_template").get("reports"))),
        "cost_book_link_count": len(_safe_list(_section(template, "cost_book_link").get("links"))),
        "pipe_hook_ready": bool(_section(template, "pipe_template_hook")),
        "roadway_hook_ready": bool(_section(template, "roadway_template_hook")),
    }


def template_behavior(template: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not template:
        return {
            "active_template": None,
            "status": "missing",
            "template_behavior": [
                "No company template is active.",
                "Generated layers, labels, reports, cost links, pipe defaults, and roadway defaults use Civora workspace defaults.",
            ],
            "blockers": ["customer_template_missing"],
            "policy": template_policy(),
        }
    summary = summarize_template(template)
    missing = list(summary["missing_sections"])
    accepted = bool(summary["accepted_for_workspace"])
    return {
        "active_template": summary,
        "status": "active_reviewed" if accepted else "active_needs_review",
        "template_behavior": [
            "Layer standards guide generated CAD layer names, colors, and lineweights where matching systems exist.",
            "Title block templates provide sheet metadata fields for deliverable setup.",
            "Label style templates guide plan labels and callouts.",
            "Annotation standards guide dimensions, text, leaders/callouts, hatches, linetypes, scale behavior, and annotation layer assignment as review/drafting aids.",
            "Symbol/block libraries expose reusable firm blocks for plan objects.",
            "Report templates select report sections and ordering.",
            "Cost book template links connect estimates to firm price-book references after separate cost-book review.",
            "Pipe and roadway hooks provide default layer/label settings for those engines.",
        ],
        "blockers": [f"missing_{key}" for key in missing] + ([] if accepted else ["template_not_accepted_for_workspace"]),
        "policy": template_policy(),
    }


class CustomerTemplateManager:
    def __init__(self, initial_registry: Optional[Dict[str, Any]] = None) -> None:
        registry = deepcopy(initial_registry or {})
        templates = _safe_list(registry.get("templates")) or [sample_customer_template()]
        self.templates: Dict[str, Dict[str, Any]] = {}
        self.active_template_id = _safe_str(registry.get("active_template_id"))
        for item in templates:
            result = self.import_template(_safe_dict(item), replace=True)
            if result.get("success") and not self.active_template_id:
                self.active_template_id = _safe_str(result.get("template", {}).get("template_id"))

    def snapshot(self) -> Dict[str, Any]:
        templates = [deepcopy(value) for value in self.templates.values()]
        active = self.templates.get(self.active_template_id)
        return {
            "version": TEMPLATE_REGISTRY_VERSION,
            "active_template_id": self.active_template_id,
            "templates": templates,
            "summaries": [summarize_template(item) for item in templates],
            "active_template": deepcopy(active) if active else None,
            "behavior": template_behavior(active),
            "policy": template_policy(),
        }

    def import_template(self, payload: Dict[str, Any], *, replace: bool = False) -> Dict[str, Any]:
        template = CustomerTemplate.from_payload(payload)
        issues = template.validate()
        if issues:
            return {"success": False, "status": "rejected", "issues": issues, "template": template.to_dict()}
        if template.template_id in self.templates and not replace:
            return {"success": False, "status": "duplicate", "issues": ["template_id already exists"], "template": template.to_dict()}
        self.templates[template.template_id] = template.to_dict()
        if not self.active_template_id:
            self.active_template_id = template.template_id
        return {"success": True, "status": "imported", "template": deepcopy(self.templates[template.template_id]), "registry": self.snapshot()}

    def activate(self, template_id: str = "") -> Dict[str, Any]:
        selected_id = _safe_str(template_id)
        if not selected_id:
            accepted = [item for item in self.templates.values() if bool(item.get("accepted_for_workspace"))]
            selected_id = _safe_str((accepted[0] if accepted else next(iter(self.templates.values()), {})).get("template_id"))
        if selected_id not in self.templates:
            return {
                "success": False,
                "status": "missing",
                "issues": [f"template not found: {selected_id or 'no template id provided'}"],
                "registry": self.snapshot(),
            }
        self.active_template_id = selected_id
        return {"success": True, "status": "active", "template": deepcopy(self.templates[selected_id]), "registry": self.snapshot()}

    def explain_missing(self, template_id: str = "") -> Dict[str, Any]:
        template = self.templates.get(_safe_str(template_id) or self.active_template_id)
        behavior = template_behavior(template)
        return {
            "success": bool(template),
            "status": behavior["status"],
            "message": (
                "Template is missing because no firm template is registered or active."
                if not template
                else "Template is present but some sections or workspace acceptance are missing."
            ),
            "behavior": behavior,
        }

    def export_json(self) -> Dict[str, Any]:
        return {
            "version": TEMPLATE_EXPORT_VERSION,
            "exported_date": date.today().isoformat(),
            "registry": self.snapshot(),
        }


GLOBAL_CUSTOMER_TEMPLATE_MANAGER = CustomerTemplateManager()
