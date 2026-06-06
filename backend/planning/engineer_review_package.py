from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence

from core.professional_release import validate_professional_release

from .common import readiness_issue_explanations, safe_dict, safe_list, safe_str


REVIEW_PACKAGE_VERSION = "engineer_review_package_v1"

DISCIPLINE_AREAS: Dict[str, Sequence[str]] = {
    "grading": ("grading", "grading_detail", "surface", "terrain"),
    "drainage": ("drainage", "hydrology"),
    "storm": ("storm", "storm_pipe", "hydraulics"),
    "sanitary": ("sanitary",),
    "water": ("water", "utilities"),
    "roadway": ("roadway", "corridor"),
    "utilities": ("utilities", "coordination"),
    "earthwork": ("earthwork",),
    "quantities": ("quantities", "cost"),
    "exports": ("deliverables", "cad_interop", "exports"),
}


def _generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_id(plan_or_meta: Dict[str, Any], meta: Dict[str, Any]) -> str:
    return safe_str(
        plan_or_meta.get("project_id")
        or plan_or_meta.get("id")
        or meta.get("project_id")
        or meta.get("id")
        or plan_or_meta.get("project_name")
        or meta.get("project_name"),
        "unknown_project",
    )


def _blocker(area: str, field: str, reason: str, *, next_action: str = "") -> Dict[str, Any]:
    return {
        "area": area,
        "field": field,
        "reason": reason,
        "message": reason,
        "why_needed": reason,
        "suggested_next_action": next_action or "Resolve this review-package issue and regenerate the engineer review package.",
        "severity": "blocker",
    }


def _missing_input(area: str, field: str, reason: str, *, next_action: str = "") -> Dict[str, Any]:
    rec = _blocker(area, field, reason, next_action=next_action)
    rec["severity"] = "missing_input"
    return rec


def _unique_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in records:
        rec = safe_dict(item)
        key = (
            safe_str(rec.get("area")),
            safe_str(rec.get("field")),
            safe_str(rec.get("reason") or rec.get("why_needed") or rec.get("message")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(deepcopy(rec))
    return out


def _gate_blockers(package: Dict[str, Any], *, area: str, field: str, status_key: str = "status") -> List[Dict[str, Any]]:
    if not package:
        return [
            _blocker(
                area,
                field,
                f"{field} is missing from the engineer review evidence package.",
                next_action=f"Build and attach {field} before engineer review.",
            )
        ]
    blockers = [safe_dict(item) for item in safe_list(package.get("blockers")) if safe_dict(item)]
    if blockers:
        return blockers
    status = safe_str(package.get(status_key)).lower()
    if status and status not in {"ready", "passed"}:
        return [
            _blocker(
                area,
                field,
                f"{field} is {status}, not ready.",
                next_action=f"Resolve {field} review issues before engineer review.",
            )
        ]
    return []


def _standards_summary(meta: Dict[str, Any]) -> Dict[str, Any]:
    package = safe_dict(meta.get("standards_package"))
    report = safe_dict(package.get("standards_acceptance_report"))
    return {
        "present": bool(package),
        "version": safe_str(package.get("version")),
        "status": safe_str(package.get("status"), "missing"),
        "qa_status": safe_str(report.get("qa_status") or report.get("status")),
        "production_usable": package.get("production_usable") is True,
        "construction_release_blocked": package.get("construction_release_blocked") is not False,
        "accepted_rule_count": package.get("accepted_rule_count", 0),
        "official_source_count": package.get("official_source_count", 0),
        "inferred_rule_ids": deepcopy(safe_dict(report.get("rules")).get("inferred_rule_ids") or []),
        "missing_rules": deepcopy(safe_dict(report.get("rules")).get("missing_rules") or []),
        "reviewer_comments": deepcopy(safe_list(report.get("reviewer_comments"))),
        "truth_label": "Standards evidence is a review input only; it is not engineer signoff or code-compliance certification.",
    }


def _existing_conditions_summary(meta: Dict[str, Any]) -> Dict[str, Any]:
    package = safe_dict(meta.get("existing_conditions_package"))
    gate = safe_dict(package.get("gate"))
    return {
        "present": bool(package),
        "version": safe_str(package.get("version")),
        "status": safe_str(package.get("status"), "missing"),
        "production_ready": package.get("production_ready") is True,
        "review_usable": package.get("review_usable") is True,
        "accepted": package.get("accepted") is True,
        "survey_ready": package.get("survey_ready") is True,
        "gis_ready": package.get("gis_ready") is True,
        "coordinate_system_ready": package.get("coordinate_system_ready") is True,
        "terrain_source_confidence": safe_str(gate.get("terrain_source_confidence") or safe_dict(package.get("terrain_source_confidence")).get("label"), "missing"),
        "metadata_only": package.get("metadata_only") is True,
        "source_count": package.get("source_count", 0),
        "truth_label": "Existing conditions remain review inputs until survey/control, terrain, GIS, and professional verification are complete.",
    }


def _engine_depth_summary(meta: Dict[str, Any]) -> Dict[str, Any]:
    audit = safe_dict(meta.get("engine_depth_audit_report") or meta.get("engine_depth_audit"))
    readiness = safe_dict(meta.get("engine_readiness"))
    alpha = safe_dict(safe_dict(readiness.get("summary")).get("alpha_readiness"))
    depth_validation = safe_dict(meta.get("depth_validation"))
    validation_blockers = {
        key: safe_list(safe_dict(value).get("blockers"))
        for key, value in depth_validation.items()
        if safe_list(safe_dict(value).get("blockers"))
    }
    return {
        "engine_depth_audit_present": bool(audit),
        "engine_depth_audit_status": safe_str(audit.get("status"), "missing") if audit else "missing",
        "engine_depth_audit_success": audit.get("success") is True if audit else False,
        "engine_readiness_present": bool(readiness),
        "engine_readiness_status": safe_str(alpha.get("status") or readiness.get("status"), "missing"),
        "ready_engine_count": alpha.get("ready_engine_count"),
        "applicable_engine_count": alpha.get("applicable_engine_count"),
        "depth_validation_present": bool(depth_validation),
        "depth_validation_blockers": validation_blockers,
        "truth_label": "Engine depth evidence supports engineer review; it does not replace professional calculation review.",
    }


def _export_package_summary(meta: Dict[str, Any]) -> Dict[str, Any]:
    review_manifest = safe_dict(meta.get("review_package_manifest"))
    construction_manifest = safe_dict(meta.get("construction_package_manifest"))
    export_audit = safe_dict(meta.get("export_audit"))
    return {
        "present": bool(review_manifest or construction_manifest or export_audit),
        "review_manifest_status": "ready" if review_manifest.get("review_ready") is True else "blocked" if review_manifest else "missing",
        "review_package_id": safe_str(review_manifest.get("review_package_id")),
        "review_ready": review_manifest.get("review_ready") is True,
        "export_audit_present": bool(export_audit),
        "export_audit_ready": export_audit.get("ready") is True or export_audit.get("production_export_ready") is True,
        "export_blocked": export_audit.get("export_blocked") is True,
        "construction_manifest_present": bool(construction_manifest),
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "truth_label": "Exports may be reviewable, but this engineer package does not authorize construction release.",
    }


def _calculation_artifacts(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for key in (
        "grading_summary",
        "drainage_summary",
        "storm_summary",
        "sanitary_summary",
        "water_summary",
        "roadway_summary",
        "earthwork",
        "earthwork_summary",
        "quantities",
        "cost_estimate",
        "depth_validation",
    ):
        value = meta.get(key)
        if value is None:
            continue
        rec = safe_dict(value)
        artifacts.append(
            {
                "artifact_id": key,
                "present": True,
                "success": rec.get("success"),
                "status": safe_str(rec.get("status")),
                "review_required": True,
                "trace": deepcopy(rec.get("explain") or rec.get("trace") or rec.get("canonical_id_traceability") or {}),
            }
        )
    for item in safe_list(meta.get("calculation_artifacts")):
        rec = safe_dict(item)
        if rec:
            copied = deepcopy(rec)
            copied.setdefault("review_required", True)
            artifacts.append(copied)
    return artifacts


def _assumptions(meta: Dict[str, Any]) -> List[Any]:
    items: List[Any] = []
    for key in ("assumptions", "assumption_log", "assumption_summary"):
        value = meta.get(key)
        if isinstance(value, list):
            items.extend(deepcopy(value))
        elif isinstance(value, dict):
            items.append(deepcopy(value))
    return items


def _reviewer_comments(meta: Dict[str, Any], standards_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    comments: List[Dict[str, Any]] = []
    for source, values in (
        ("standards_acceptance_report", standards_summary.get("reviewer_comments")),
        ("reviewer_comments", meta.get("reviewer_comments")),
        ("qa_reviewer_comments", meta.get("qa_reviewer_comments")),
    ):
        for index, item in enumerate(safe_list(values), start=1):
            rec = safe_dict(item)
            comment = safe_str(rec.get("comment") or rec.get("message") or rec.get("reason") or item)
            if not comment:
                continue
            comments.append(
                {
                    "source": source,
                    "comment_id": safe_str(rec.get("comment_id") or rec.get("id"), f"{source}_{index}"),
                    "area": safe_str(rec.get("area")),
                    "field": safe_str(rec.get("field")),
                    "comment": comment,
                    "severity": safe_str(rec.get("severity"), "review"),
                    "resolved": rec.get("resolved") is True,
                    "requires_engineer_review": True,
                }
            )
    return comments


def _discipline_sections(blockers: Sequence[Dict[str, Any]], calculations: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    calculation_ids = [safe_str(item.get("artifact_id")) for item in calculations if safe_str(item.get("artifact_id"))]
    sections: Dict[str, Dict[str, Any]] = {}
    for discipline, areas in DISCIPLINE_AREAS.items():
        matched_blockers = [
            deepcopy(item)
            for item in blockers
            if safe_str(item.get("area")).lower() in areas or safe_str(item.get("field")).lower() in areas
        ]
        matched_calcs = [item for item in calculation_ids if discipline in item or any(area in item for area in areas)]
        sections[discipline] = {
            "status": "blocked" if matched_blockers else "ready_for_review",
            "required_engineer_review": True,
            "calculation_artifacts": matched_calcs,
            "blockers": matched_blockers,
            "review_notes": [],
            "truth_label": "Discipline section is packaged for licensed engineer review; it is not signed off by Civora.",
        }
    return sections


def _signoff_item(item_id: str, label: str, *, status: str, evidence: Any = None, external_manual: bool = False) -> Dict[str, Any]:
    return {
        "item_id": item_id,
        "label": label,
        "status": status,
        "complete": status == "complete",
        "required": True,
        "external_manual": external_manual,
        "evidence": deepcopy(evidence),
    }


def _manual_signoff(meta: Dict[str, Any]) -> Dict[str, Any]:
    professional = safe_dict(meta.get("engineer_signoff") or meta.get("manual_engineer_signoff") or meta.get("professional_review"))
    validation = validate_professional_release(professional)
    complete = validation.get("released_for_construction") is True and professional.get("manual_external_record") is True
    return {
        "present": bool(professional),
        "complete": bool(complete),
        "validation": validation,
        "truth_label": "Engineer seal/signature can only be completed by an external/manual professional record.",
    }


def _signoff_checklist(
    *,
    standards_summary: Dict[str, Any],
    existing_summary: Dict[str, Any],
    engine_summary: Dict[str, Any],
    export_summary: Dict[str, Any],
    assumptions: Sequence[Any],
    blockers: Sequence[Dict[str, Any]],
    manual_signoff: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        _signoff_item("standards_accepted", "standards accepted", status="complete" if standards_summary["production_usable"] else "blocked", evidence=standards_summary),
        _signoff_item("survey_control_verified", "survey/control verified", status="complete" if existing_summary["production_ready"] and existing_summary["accepted"] else "blocked", evidence=existing_summary),
        _signoff_item("terrain_verified", "terrain verified", status="complete" if existing_summary["terrain_source_confidence"] not in {"", "missing", "metadata_only"} else "blocked", evidence=existing_summary),
        _signoff_item("calculations_reviewed", "calculations reviewed", status="manual_required", external_manual=True),
        _signoff_item("conflicts_reviewed", "conflicts reviewed", status="blocked" if any(safe_str(item.get("area")) == "coordination" for item in blockers) else "manual_required", external_manual=True),
        _signoff_item("exports_reviewed", "exports reviewed", status="complete" if export_summary["review_ready"] else "blocked", evidence=export_summary),
        _signoff_item("assumptions_accepted", "assumptions accepted", status="manual_required" if assumptions else "complete", evidence=list(assumptions), external_manual=bool(assumptions)),
        _signoff_item("engineer_seal_signature_external_manual", "engineer seal/signature external/manual", status="complete" if manual_signoff["complete"] else "manual_required", evidence=manual_signoff, external_manual=True),
    ]


def build_engineer_review_package(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if isinstance(plan_or_meta, dict) and "meta" in plan_or_meta else safe_dict(plan_or_meta)
    standards_summary = _standards_summary(meta)
    existing_summary = _existing_conditions_summary(meta)
    engine_summary = _engine_depth_summary(meta)
    export_summary = _export_package_summary(meta)
    assumptions = _assumptions(meta)
    calculation_artifacts = _calculation_artifacts(meta)

    blockers: List[Dict[str, Any]] = []
    missing_inputs: List[Dict[str, Any]] = []
    blockers.extend(_gate_blockers(safe_dict(meta.get("standards_package")), area="standards", field="standards_package"))
    blockers.extend(_gate_blockers(safe_dict(meta.get("existing_conditions_package")), area="existing_conditions", field="existing_conditions_package"))
    if not engine_summary["engine_depth_audit_present"] and not engine_summary["engine_readiness_present"] and not engine_summary["depth_validation_present"]:
        blockers.append(
            _blocker(
                "depth_validation",
                "engine_depth_evidence",
                "Engineer review package needs engine depth audit, engine readiness, or depth validation evidence.",
                next_action="Run engine readiness/depth validation before packaging engineer review.",
            )
        )
    elif engine_summary["depth_validation_blockers"]:
        blockers.append(
            _blocker(
                "depth_validation",
                "depth_validation_blockers",
                "Depth validation has discipline blockers that must be resolved or explicitly documented.",
                next_action="Resolve depth validation blockers or document why they remain review-only.",
            )
        )
    if not export_summary["present"] or not export_summary["review_ready"]:
        blockers.append(
            _blocker(
                "deliverables",
                "export_package",
                "Engineer review package needs a review-ready export package or audited export manifest.",
                next_action="Generate review package manifest and export audit before engineer review.",
            )
        )

    if standards_summary["inferred_rule_ids"]:
        missing_inputs.append(
            _missing_input(
                "standards",
                "inferred_rules",
                "Standards include inferred rule IDs that must be accepted or removed before signoff.",
                next_action="Replace inferred standards with accepted official-source rules.",
            )
        )
    if existing_summary["metadata_only"]:
        missing_inputs.append(
            _missing_input(
                "existing_conditions",
                "metadata_only_existing_conditions",
                "Existing conditions include metadata-only evidence that cannot support signoff.",
                next_action="Attach parsed survey/GIS/terrain evidence before signoff.",
            )
        )
    if not calculation_artifacts:
        missing_inputs.append(
            _missing_input(
                "calculations",
                "calculation_artifacts",
                "No calculation artifacts are attached for engineer review.",
                next_action="Attach calculation summaries or explicit calculation artifacts for each applicable discipline.",
            )
        )

    blockers = _unique_records(blockers)
    missing_inputs = _unique_records(missing_inputs)
    manual_signoff = _manual_signoff(meta)
    checklist = _signoff_checklist(
        standards_summary=standards_summary,
        existing_summary=existing_summary,
        engine_summary=engine_summary,
        export_summary=export_summary,
        assumptions=assumptions,
        blockers=blockers,
        manual_signoff=manual_signoff,
    )
    review_status = "blocked" if blockers else "needs_more_information" if missing_inputs else "ready_for_review"
    construction_release_blocked = bool(blockers or missing_inputs or not manual_signoff["complete"])
    reviewer_comments = _reviewer_comments(meta, standards_summary)

    return {
        "version": REVIEW_PACKAGE_VERSION,
        "project_id": _project_id(plan_or_meta, meta),
        "generated_at": _generated_at(),
        "review_status": review_status,
        "construction_release_blocked": construction_release_blocked,
        "construction_release_allowed": False,
        "required_engineer_review": True,
        "standards_acceptance_summary": standards_summary,
        "existing_conditions_summary": existing_summary,
        "engine_depth_summary": engine_summary,
        "export_package_summary": export_summary,
        "assumptions": deepcopy(assumptions),
        "missing_inputs": missing_inputs,
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "calculation_artifacts": calculation_artifacts,
        "reviewer_comments": reviewer_comments,
        "discipline_sections": _discipline_sections(blockers, calculation_artifacts),
        "signoff_checklist": checklist,
        "manual_engineer_signoff": manual_signoff,
        "truth_label": (
            "This package is a licensed-engineer review handoff. Civora never completes engineer signoff, seal, "
            "or construction release automatically; inferred, missing, stale, and review-only evidence remains explicit."
        ),
    }


__all__ = ["REVIEW_PACKAGE_VERSION", "build_engineer_review_package"]
