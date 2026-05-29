from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Sequence

from core.civil_design import construction_readiness

from .common import safe_dict, safe_list, safe_str


CONSTRUCTION_PACKAGE_SECTIONS: Sequence[Dict[str, Any]] = (
    {
        "section_id": "existing_conditions",
        "label": "Existing Conditions",
        "areas": {"existing_conditions"},
        "evidence_keys": ("existing_conditions_production_ready",),
        "required": ("verified survey/control", "projected coordinate system", "GIS constraints/existing utilities"),
    },
    {
        "section_id": "standards",
        "label": "Standards",
        "areas": {"standards"},
        "evidence_keys": ("standards_production_usable",),
        "required": ("accepted official jurisdiction rules", "company standards"),
    },
    {
        "section_id": "engineering_depth",
        "label": "Engineering Depth",
        "areas": {"civil_design", "depth_validation", "grading_detail", "hydraulics", "optimization", "structures"},
        "evidence_keys": ("civil_production_ready",),
        "required": ("production civil readiness", "storm/water/roadway depth validation", "grading detail"),
    },
    {
        "section_id": "qa",
        "label": "QA / Truth Audit",
        "areas": {"qa", "reactive_model"},
        "evidence_keys": (),
        "required": ("truth audit clear", "manual gates clear", "no stale outputs"),
    },
    {
        "section_id": "deliverables",
        "label": "Deliverables",
        "areas": {"deliverables", "cad_interop"},
        "evidence_keys": ("export_production_ready",),
        "required": ("export audit", "sheet registry", "canonical ID traceability"),
    },
    {
        "section_id": "cost",
        "label": "Cost / Takeoff",
        "areas": {"cost"},
        "evidence_keys": ("cost_production_usable",),
        "required": ("traceable quantities", "approved unit-price book", "current cost estimate"),
    },
    {
        "section_id": "professional_release",
        "label": "Professional Release",
        "areas": {"professional_review"},
        "evidence_keys": ("professional_release",),
        "required": ("reviewer identity", "license number", "released-for-construction status"),
    },
)


def _unique_blockers(blockers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in blockers:
        rec = safe_dict(item)
        key = (
            safe_str(rec.get("area")),
            safe_str(rec.get("field")),
            safe_str(rec.get("why_needed") or rec.get("reason") or rec.get("message")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(deepcopy(rec))
    return out


def _section_status(
    *,
    section: Dict[str, Any],
    blockers: Sequence[Dict[str, Any]],
    warnings: Sequence[Dict[str, Any]],
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    areas = set(section.get("areas") or ())
    section_blockers = [deepcopy(item) for item in blockers if safe_str(item.get("area")) in areas]
    section_warnings = [deepcopy(item) for item in warnings if safe_str(item.get("area")) in areas]
    evidence_keys = [safe_str(item) for item in section.get("evidence_keys") or () if safe_str(item)]
    evidence_ready = all(bool(evidence.get(key)) for key in evidence_keys) if evidence_keys else not section_blockers
    ready = not section_blockers and evidence_ready
    if section_blockers:
        status = "blocked"
    elif section_warnings:
        status = "needs_review"
    elif ready:
        status = "ready"
    else:
        status = "pending"
    return {
        "section_id": safe_str(section.get("section_id")),
        "label": safe_str(section.get("label")),
        "status": status,
        "ready": ready,
        "required": list(section.get("required") or ()),
        "evidence": {key: bool(evidence.get(key)) for key in evidence_keys},
        "blockers": section_blockers,
        "warnings": section_warnings,
        "next_actions": [safe_str(item.get("suggested_next_action")) for item in section_blockers[:4] if safe_str(item.get("suggested_next_action"))],
    }


def build_construction_package_manifest(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Build the release manifest that gates construction package issue.

    This does not create permit approval and it does not stamp drawings. It is
    the machine-readable backend handoff that says whether a package may be
    released for construction, and exactly which evidence is still missing.
    """

    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    readiness = safe_dict(meta.get("construction_readiness"))
    if not readiness:
        readiness = construction_readiness(plan_or_meta)

    blockers = _unique_blockers(safe_list(readiness.get("blockers")))
    warnings = _unique_blockers(safe_list(readiness.get("warnings")))
    evidence = safe_dict(readiness.get("evidence"))
    sections = [
        _section_status(section=section, blockers=blockers, warnings=warnings, evidence=evidence)
        for section in CONSTRUCTION_PACKAGE_SECTIONS
    ]
    blocked_sections = [section["section_id"] for section in sections if section["status"] == "blocked"]
    review_sections = [section["section_id"] for section in sections if section["status"] == "needs_review"]
    ready = bool(readiness.get("ready")) and not blocked_sections
    release_state = "released_for_construction" if ready else "blocked_from_construction_release"
    return {
        "success": True,
        "source": "construction_package_manifest_v1",
        "release_state": release_state,
        "construction_ready": ready,
        "release_allowed": ready,
        "construction_export_allowed": ready,
        "review_package_allowed": True,
        "construction_readiness_status": safe_str(readiness.get("status"), "not_construction_ready"),
        "construction_readiness_score": readiness.get("score"),
        "sections": sections,
        "blocked_sections": blocked_sections,
        "review_sections": review_sections,
        "blockers": blockers,
        "warnings": warnings,
        "next_actions": [safe_str(item.get("suggested_next_action")) for item in blockers[:10] if safe_str(item.get("suggested_next_action"))],
        "truth_label": (
            "Review packages may be generated while blocked, but construction release requires all sections ready "
            "plus licensed professional release evidence. Civora does not stamp drawings."
        ),
    }


__all__ = ["CONSTRUCTION_PACKAGE_SECTIONS", "build_construction_package_manifest"]
