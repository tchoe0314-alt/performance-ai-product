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

MISSING_INPUT_GATES: Sequence[str] = (
    "standards",
    "existing_conditions",
    "engine_depth",
    "exports",
    "calculations",
    "engineer_approval",
)

APPROVAL_SYSTEM_GENERATED = "system_generated_check"
APPROVAL_ENGINEER_MANUAL = "engineer_manual_review_required"
APPROVAL_EXTERNAL_RECORD = "external_engineer_approval_record_required"


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


def _discipline_for_text(*values: Any) -> str:
    text = " ".join(safe_str(value).lower() for value in values if safe_str(value))
    for discipline, areas in DISCIPLINE_AREAS.items():
        if discipline in text or any(area in text for area in areas):
            return discipline
    return "general"


def _matches_discipline(item: Any, discipline: str, areas: Sequence[str]) -> bool:
    rec = safe_dict(item)
    values = [
        rec.get("discipline"),
        rec.get("area"),
        rec.get("field"),
        rec.get("artifact_id"),
        rec.get("id"),
        rec.get("name"),
        rec.get("source"),
        rec.get("field_name"),
        rec.get("system"),
    ]
    text = " ".join(safe_str(value).lower() for value in values if safe_str(value))
    return discipline in text or any(area in text for area in areas)


def _canonical_ids_from_value(value: Any) -> List[str]:
    ids: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = safe_str(key).lower()
            if key_text in {
                "canonical_id",
                "canonical_ids",
                "canonical_model_id",
                "canonical_model_hash",
                "canonical_source_id",
                "canonical_source_ids",
                "source_object_id",
                "source_object_ids",
                "object_id",
                "object_ids",
                "pipe_id",
                "pipe_ids",
                "structure_id",
                "structure_ids",
                "surface_id",
                "surface_ids",
                "quantity_model_hash",
                "cost_estimate_hash",
                "price_book_hash",
            }:
                ids.extend(_canonical_ids_from_value(item))
            elif isinstance(item, (dict, list)):
                ids.extend(_canonical_ids_from_value(item))
        return _dedupe_strings(ids)
    if isinstance(value, list):
        for item in value:
            ids.extend(_canonical_ids_from_value(item))
        return _dedupe_strings(ids)
    text = safe_str(value)
    return [text] if text else []


def _dedupe_strings(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _missing_inputs_by_gate(missing_inputs: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {gate: [] for gate in MISSING_INPUT_GATES}
    aliases = {
        "standards": "standards",
        "existing_conditions": "existing_conditions",
        "depth_validation": "engine_depth",
        "engine_depth": "engine_depth",
        "deliverables": "exports",
        "exports": "exports",
        "calculations": "calculations",
        "engineer_approval": "engineer_approval",
        "professional_review": "engineer_approval",
    }
    for item in missing_inputs:
        rec = safe_dict(item)
        area = safe_str(rec.get("area")).lower()
        gate = aliases.get(area, area if area in grouped else "calculations")
        grouped.setdefault(gate, []).append(deepcopy(rec))
    return grouped


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
        "truth_label": "Standards evidence is a review input only; engineer/user acceptance is always required and Civora does not certify code compliance.",
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
        "review_package_only": True,
        "external_engineer_approval_record_present": bool(
            safe_dict(meta.get("engineer_approval_record"))
            or safe_dict(meta.get("manual_engineer_approval"))
            or safe_dict(meta.get("professional_review"))
        ),
        "truth_label": "Exports are review packages only unless a separate external licensed-engineer approval record is provided; Civora does not authorize construction release.",
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
        trace = deepcopy(rec.get("explain") or rec.get("trace") or rec.get("canonical_id_traceability") or {})
        artifacts.append(
            {
                "artifact_id": key,
                "discipline": _discipline_for_text(key, rec.get("discipline"), rec.get("area")),
                "present": True,
                "success": rec.get("success"),
                "status": safe_str(rec.get("status")),
                "review_required": True,
                "canonical_ids": _dedupe_strings(
                    [
                        rec.get("canonical_id"),
                        rec.get("canonical_model_id"),
                        rec.get("canonical_model_hash"),
                        rec.get("canonical_source_id"),
                    ]
                    + _canonical_ids_from_value(trace)
                ),
                "trace": trace,
            }
        )
        if key == "depth_validation":
            for child_key, child_value in rec.items():
                child = safe_dict(child_value)
                if not child:
                    continue
                child_trace = deepcopy(child.get("explain") or child.get("trace") or child.get("canonical_id_traceability") or {})
                artifacts.append(
                    {
                        "artifact_id": f"depth_validation.{child_key}",
                        "discipline": _discipline_for_text(child_key),
                        "present": True,
                        "success": child.get("success"),
                        "status": safe_str(child.get("status")),
                        "review_required": True,
                        "canonical_ids": _dedupe_strings(
                            [
                                child.get("canonical_id"),
                                child.get("canonical_model_id"),
                                child.get("canonical_model_hash"),
                                child.get("canonical_source_id"),
                            ]
                            + _canonical_ids_from_value(child_trace)
                            + _canonical_ids_from_value(child.get("blockers"))
                        ),
                        "trace": child_trace,
                    }
                )
    for item in safe_list(meta.get("calculation_artifacts")):
        rec = safe_dict(item)
        if rec:
            copied = deepcopy(rec)
            copied.setdefault("review_required", True)
            copied.setdefault("discipline", _discipline_for_text(copied.get("artifact_id"), copied.get("area"), copied.get("discipline")))
            copied["canonical_ids"] = _dedupe_strings(
                safe_list(copied.get("canonical_ids"))
                + [
                    copied.get("canonical_id"),
                    copied.get("canonical_model_id"),
                    copied.get("canonical_model_hash"),
                    copied.get("canonical_source_id"),
                ]
                + _canonical_ids_from_value(copied.get("trace"))
                + _canonical_ids_from_value(copied.get("explain"))
            )
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
            discipline = _discipline_for_text(rec.get("discipline"), rec.get("area"), rec.get("field"), comment)
            comments.append(
                {
                    "source": source,
                    "comment_id": safe_str(rec.get("comment_id") or rec.get("id"), f"{source}_{index}"),
                    "discipline": discipline,
                    "area": safe_str(rec.get("area")),
                    "field": safe_str(rec.get("field")),
                    "comment": comment,
                    "severity": safe_str(rec.get("severity"), "review"),
                    "resolved": rec.get("resolved") is True,
                    "requires_engineer_review": True,
                }
            )
    return comments


def _comments_by_key(comments: Sequence[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in comments:
        rec = safe_dict(item)
        group = safe_str(rec.get(key), "general")
        grouped.setdefault(group, []).append(deepcopy(rec))
    return grouped


def _source_confidence_for_discipline(
    discipline: str,
    *,
    standards_summary: Dict[str, Any],
    existing_summary: Dict[str, Any],
    engine_summary: Dict[str, Any],
    export_summary: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "standards_status": safe_str(standards_summary.get("status"), "missing"),
        "standards_production_usable": standards_summary.get("production_usable") is True,
        "existing_conditions_status": safe_str(existing_summary.get("status"), "missing"),
        "existing_conditions_production_ready": existing_summary.get("production_ready") is True,
        "terrain_source_confidence": safe_str(existing_summary.get("terrain_source_confidence"), "missing")
        if discipline in {"grading", "drainage", "storm", "roadway", "earthwork"}
        else "",
        "engine_depth_status": safe_str(engine_summary.get("engine_readiness_status"), "missing"),
        "engine_depth_audit_present": engine_summary.get("engine_depth_audit_present") is True,
        "export_review_ready": export_summary.get("review_ready") is True if discipline == "exports" else None,
        "truth_label": "Source confidence summarizes package evidence for review; it is not professional approval and does not make Civora responsible for the design.",
    }


def _discipline_sections(
    blockers: Sequence[Dict[str, Any]],
    assumptions: Sequence[Any],
    calculations: Sequence[Dict[str, Any]],
    comments: Sequence[Dict[str, Any]],
    *,
    standards_summary: Dict[str, Any],
    existing_summary: Dict[str, Any],
    engine_summary: Dict[str, Any],
    export_summary: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    sections: Dict[str, Dict[str, Any]] = {}
    for discipline, areas in DISCIPLINE_AREAS.items():
        matched_blockers = [
            deepcopy(item)
            for item in blockers
            if _matches_discipline(item, discipline, areas)
        ]
        matched_assumptions = [
            deepcopy(item)
            for item in assumptions
            if _matches_discipline(item, discipline, areas)
        ]
        matched_calcs = [
            deepcopy(item)
            for item in calculations
            if _matches_discipline(item, discipline, areas)
        ]
        matched_comments = [
            deepcopy(item)
            for item in comments
            if _matches_discipline(item, discipline, areas)
        ]
        sections[discipline] = {
            "status": "blocked" if matched_blockers else "ready_for_engineer_review",
            "required_engineer_review": True,
            "blockers": matched_blockers,
            "assumptions": matched_assumptions,
            "calculation_artifacts": matched_calcs,
            "reviewer_comments": matched_comments,
            "source_confidence": _source_confidence_for_discipline(
                discipline,
                standards_summary=standards_summary,
                existing_summary=existing_summary,
                engine_summary=engine_summary,
                export_summary=export_summary,
            ),
            "canonical_ids": _dedupe_strings(
                canonical_id
                for artifact in matched_calcs
                for canonical_id in safe_list(safe_dict(artifact).get("canonical_ids"))
            ),
            "review_notes": [],
            "truth_label": "Discipline section is ready for licensed engineer review only; Civora is not the engineer of record.",
        }
    return sections


def _approval_item(
    item_id: str,
    label: str,
    *,
    status: str,
    check_type: str,
    evidence: Any = None,
    external_manual: bool = False,
) -> Dict[str, Any]:
    return {
        "item_id": item_id,
        "label": label,
        "check_type": check_type,
        "system_generated": check_type == APPROVAL_SYSTEM_GENERATED,
        "engineer_manual_review_required": check_type == APPROVAL_ENGINEER_MANUAL,
        "external_engineer_approval_required": check_type == APPROVAL_EXTERNAL_RECORD,
        "status": status,
        "complete": status == "complete",
        "required": True,
        "external_manual": external_manual,
        "civora_signoff_allowed": False,
        "evidence": deepcopy(evidence),
    }


def _external_engineer_approval(meta: Dict[str, Any]) -> Dict[str, Any]:
    professional = safe_dict(
        meta.get("engineer_approval_record")
        or meta.get("manual_engineer_approval")
        or meta.get("professional_review")
    )
    validation = validate_professional_release(professional)
    complete = validation.get("released_for_construction") is True and (
        professional.get("manual_external_record") is True
        or professional.get("external_engineer_approval_record") is True
    )
    return {
        "present": bool(professional),
        "complete": bool(complete),
        "required": True,
        "engineer_approval_required": True,
        "civora_signoff_allowed": False,
        "construction_release_allowed_by_civora": False,
        "validation": validation,
        "truth_label": "Engineer approval is an external licensed-engineer/user responsibility; Civora does not sign, certify, seal, approve, or take engineering responsibility.",
    }


def _approval_checklist(
    *,
    standards_summary: Dict[str, Any],
    existing_summary: Dict[str, Any],
    engine_summary: Dict[str, Any],
    export_summary: Dict[str, Any],
    assumptions: Sequence[Any],
    blockers: Sequence[Dict[str, Any]],
    external_engineer_approval: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        _approval_item("standards_ready_for_engineer_review", "standards ready for engineer/user acceptance", status="manual_required" if standards_summary["production_usable"] else "blocked", check_type=APPROVAL_ENGINEER_MANUAL, evidence=standards_summary, external_manual=True),
        _approval_item("survey_control_verified", "survey/control verified", status="complete" if existing_summary["production_ready"] and existing_summary["accepted"] else "blocked", check_type=APPROVAL_SYSTEM_GENERATED, evidence=existing_summary),
        _approval_item("terrain_verified", "terrain verified", status="complete" if existing_summary["terrain_source_confidence"] not in {"", "missing", "metadata_only"} else "blocked", check_type=APPROVAL_SYSTEM_GENERATED, evidence=existing_summary),
        _approval_item("calculations_reviewed", "calculations reviewed", status="manual_required", check_type=APPROVAL_ENGINEER_MANUAL, external_manual=True),
        _approval_item("conflicts_reviewed", "conflicts reviewed", status="blocked" if any(safe_str(item.get("area")) == "coordination" for item in blockers) else "manual_required", check_type=APPROVAL_ENGINEER_MANUAL, external_manual=True),
        _approval_item("exports_ready_for_engineer_review", "exports ready for engineer review", status="manual_required" if export_summary["review_ready"] else "blocked", check_type=APPROVAL_ENGINEER_MANUAL, evidence=export_summary, external_manual=True),
        _approval_item("assumptions_accepted", "assumptions accepted", status="manual_required" if assumptions else "complete", check_type=APPROVAL_ENGINEER_MANUAL if assumptions else APPROVAL_SYSTEM_GENERATED, evidence=list(assumptions), external_manual=bool(assumptions)),
        _approval_item("external_engineer_approval_record", "external engineer/user approval record", status="complete" if external_engineer_approval["complete"] else "manual_required", check_type=APPROVAL_EXTERNAL_RECORD, evidence=external_engineer_approval, external_manual=True),
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
    if not safe_dict(meta.get("standards_package")):
        missing_inputs.append(
            _missing_input(
                "standards",
                "standards_package",
                "Standards package evidence is missing.",
                next_action="Build standards_package from accepted official-source standards before engineer review.",
            )
        )
    if not safe_dict(meta.get("existing_conditions_package")):
        missing_inputs.append(
            _missing_input(
                "existing_conditions",
                "existing_conditions_package",
                "Existing-conditions package evidence is missing.",
                next_action="Build existing_conditions_package from survey/GIS/terrain import validation before engineer review.",
            )
        )
    blockers.extend(_gate_blockers(safe_dict(meta.get("standards_package")), area="standards", field="standards_package"))
    blockers.extend(_gate_blockers(safe_dict(meta.get("existing_conditions_package")), area="existing_conditions", field="existing_conditions_package"))
    if not engine_summary["engine_depth_audit_present"] and not engine_summary["engine_readiness_present"] and not engine_summary["depth_validation_present"]:
        missing_inputs.append(
            _missing_input(
                "engine_depth",
                "engine_depth_evidence",
                "Engine depth evidence is missing.",
                next_action="Run engine readiness/depth validation before packaging engineer review.",
            )
        )
        blockers.append(
            _blocker(
                "depth_validation",
                "engine_depth_evidence",
                "Engineer review package needs engine depth audit, engine readiness, or depth validation evidence.",
                next_action="Run engine readiness/depth validation before packaging engineer review.",
            )
        )
    elif engine_summary["depth_validation_blockers"]:
        for discipline_key, items in safe_dict(engine_summary.get("depth_validation_blockers")).items():
            for item in safe_list(items):
                rec = safe_dict(item)
                if rec:
                    copied = deepcopy(rec)
                    copied.setdefault("area", _discipline_for_text(discipline_key, rec.get("area"), rec.get("field")))
                    copied.setdefault("field", safe_str(rec.get("field"), "depth_validation"))
                    copied.setdefault("reason", safe_str(rec.get("reason") or rec.get("message") or rec.get("why_needed"), "Depth validation blocker requires engineer review."))
                    copied.setdefault("severity", "blocker")
                    blockers.append(copied)
        blockers.append(
            _blocker(
                "depth_validation",
                "depth_validation_blockers",
                "Depth validation has discipline blockers that must be resolved or explicitly documented.",
                next_action="Resolve depth validation blockers or document why they remain review-only.",
            )
        )
    if not export_summary["present"] or not export_summary["review_ready"]:
        missing_inputs.append(
            _missing_input(
                "exports",
                "export_package",
                "Review-ready export package evidence is missing or blocked.",
                next_action="Generate review package manifest and export audit before engineer review.",
            )
        )
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
                "Standards include inferred rule IDs that must be accepted or removed before engineer/user acceptance.",
                next_action="Replace inferred standards with accepted official-source rules.",
            )
        )
    if existing_summary["metadata_only"]:
        missing_inputs.append(
            _missing_input(
                "existing_conditions",
                "metadata_only_existing_conditions",
                "Existing conditions include metadata-only evidence that cannot support engineer/user acceptance.",
                next_action="Attach parsed survey/GIS/terrain evidence before engineer/user acceptance.",
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
    external_engineer_approval = _external_engineer_approval(meta)
    if not external_engineer_approval["complete"]:
        missing_inputs.append(
            _missing_input(
                "engineer_approval",
                "external_engineer_approval_record",
                "Licensed engineer/user approval is external/manual and has not been provided.",
                next_action="Have the responsible licensed engineer/user review and approve the package outside Civora.",
            )
        )
    missing_inputs = _unique_records(missing_inputs)
    missing_inputs_by_gate = _missing_inputs_by_gate(missing_inputs)
    automated_gate_status = {
        "standards": not any(safe_str(item.get("area")) == "standards" for item in blockers)
        and not any(safe_str(item.get("area")) == "standards" for item in missing_inputs),
        "existing_conditions": not any(safe_str(item.get("area")) == "existing_conditions" for item in blockers)
        and not any(safe_str(item.get("area")) == "existing_conditions" for item in missing_inputs),
        "engine_depth": not any(safe_str(item.get("area")) in {"depth_validation", "engine_depth"} for item in blockers)
        and not any(safe_str(item.get("area")) in {"depth_validation", "engine_depth"} for item in missing_inputs),
        "exports": not any(safe_str(item.get("area")) in {"deliverables", "exports"} for item in blockers)
        and not any(safe_str(item.get("area")) in {"deliverables", "exports"} for item in missing_inputs),
        "calculations": not any(safe_str(item.get("area")) == "calculations" for item in blockers)
        and not any(safe_str(item.get("area")) == "calculations" for item in missing_inputs),
    }
    automated_gates_review_ready = all(automated_gate_status.values())
    checklist = _approval_checklist(
        standards_summary=standards_summary,
        existing_summary=existing_summary,
        engine_summary=engine_summary,
        export_summary=export_summary,
        assumptions=assumptions,
        blockers=blockers,
        external_engineer_approval=external_engineer_approval,
    )
    non_approval_missing = [item for item in missing_inputs if safe_str(item.get("area")) != "engineer_approval"]
    review_status = "blocked" if blockers else "needs_more_information" if non_approval_missing else "ready_for_engineer_review" if automated_gates_review_ready else "needs_more_information"
    construction_release_blocked = True
    reviewer_comments = _reviewer_comments(meta, standards_summary)
    reviewer_comments_by_severity = _comments_by_key(reviewer_comments, "severity")
    reviewer_comments_by_discipline = _comments_by_key(reviewer_comments, "discipline")

    return {
        "version": REVIEW_PACKAGE_VERSION,
        "project_id": _project_id(plan_or_meta, meta),
        "generated_at": _generated_at(),
        "review_status": review_status,
        "ready_for_engineer_review": review_status == "ready_for_engineer_review",
        "ready_for_construction": False,
        "construction_release_blocked": construction_release_blocked,
        "construction_release_allowed": False,
        "required_engineer_review": True,
        "engineer_approval_required": True,
        "civora_signoff_allowed": False,
        "civora_engineer_of_record": False,
        "standards_acceptance_summary": standards_summary,
        "existing_conditions_summary": existing_summary,
        "engine_depth_summary": engine_summary,
        "export_package_summary": export_summary,
        "automated_gate_status": automated_gate_status,
        "automated_gates_review_ready": automated_gates_review_ready,
        "assumptions": deepcopy(assumptions),
        "missing_inputs": missing_inputs,
        "missing_inputs_by_gate": missing_inputs_by_gate,
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "calculation_artifacts": calculation_artifacts,
        "reviewer_comments": reviewer_comments,
        "reviewer_comments_by_severity": reviewer_comments_by_severity,
        "reviewer_comments_by_discipline": reviewer_comments_by_discipline,
        "discipline_sections": _discipline_sections(
            blockers,
            assumptions,
            calculation_artifacts,
            reviewer_comments,
            standards_summary=standards_summary,
            existing_summary=existing_summary,
            engine_summary=engine_summary,
            export_summary=export_summary,
        ),
        "approval_checklist": checklist,
        "external_engineer_approval": external_engineer_approval,
        "truth_label": (
            "This package is a licensed-engineer/user review handoff. Civora never signs off, certifies, seals, "
            "approves construction, or acts as engineer of record; inferred, missing, stale, and review-only evidence remains explicit."
        ),
    }


__all__ = ["REVIEW_PACKAGE_VERSION", "build_engineer_review_package"]
