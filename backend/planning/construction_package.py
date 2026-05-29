from __future__ import annotations

import hashlib
import json
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


REQUIRED_CONSTRUCTION_ARTIFACTS: Sequence[Dict[str, Any]] = (
    {"artifact_id": "sheets", "aliases": {"sheets", "sheet_set", "sheet_registry", "pdf_sheets"}},
    {"artifact_id": "cad_export", "aliases": {"cad_export", "dxf", "dwg", "civil3d", "landxml"}},
    {"artifact_id": "qa_report", "aliases": {"qa_report", "truth_audit", "validation_report"}},
    {"artifact_id": "cost_estimate", "aliases": {"cost_estimate", "takeoff", "quantity_cost"}},
    {"artifact_id": "construction_manifest", "aliases": {"construction_manifest", "release_manifest", "package_manifest"}},
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


def _artifact_type(rec: Dict[str, Any]) -> str:
    return safe_str(rec.get("type") or rec.get("artifact_type") or rec.get("kind") or rec.get("name")).lower()


def _model_reference(rec: Dict[str, Any]) -> str:
    return safe_str(
        rec.get("canonical_model_id")
        or rec.get("canonical_model_hash")
        or rec.get("source_model_id")
        or rec.get("source_model_hash")
        or rec.get("final_model_id")
        or rec.get("final_model_hash")
    )


def _package_identity(rec: Dict[str, Any]) -> str:
    return safe_str(
        rec.get("id")
        or rec.get("package_id")
        or rec.get("manifest_id")
        or rec.get("name")
        or rec.get("filename")
        or rec.get("path")
    )


def _cost_artifact_aliases() -> set:
    for required in REQUIRED_CONSTRUCTION_ARTIFACTS:
        if safe_str(required.get("artifact_id")) == "cost_estimate":
            return set(required.get("aliases") or ())
    return {"cost_estimate", "takeoff", "quantity_cost"}


def _current_cost_reference(meta: Dict[str, Any]) -> Dict[str, Any]:
    cost = safe_dict(meta.get("cost_estimate"))
    if not cost:
        return {}
    explain = safe_dict(cost.get("explain"))
    reference = safe_dict(explain.get("cost_estimate_reference"))
    quantity_reference = safe_dict(explain.get("quantity_model_reference"))
    pricing = safe_dict(explain.get("pricing"))
    cost_hash = safe_str(
        reference.get("cost_estimate_hash")
        or safe_dict(cost.get("totals")).get("cost_estimate_hash")
        or cost.get("cost_estimate_hash")
        or cost.get("hash")
    )
    quantity_hash = safe_str(reference.get("quantity_model_hash") or quantity_reference.get("quantity_model_hash"))
    price_hash = safe_str(reference.get("price_book_hash") or pricing.get("price_book_hash"))
    if not cost_hash:
        payload = {
            "totals": safe_dict(cost.get("totals")),
            "line_items": safe_list(cost.get("line_items")),
            "category_subtotals": safe_dict(cost.get("category_subtotals")),
            "quantity_model_hash": quantity_hash,
            "price_book_hash": price_hash,
        }
        if any(payload.values()):
            cost_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "cost_estimate_hash": cost_hash,
        "quantity_model_hash": quantity_hash,
        "price_book_hash": price_hash,
        "cost_success": cost.get("success"),
        "production_usable": safe_dict(cost.get("totals")).get("production_usable"),
    }


def _expected_model_reference(plan_or_meta: Dict[str, Any], meta: Dict[str, Any]) -> str:
    explicit = _model_reference(meta)
    if explicit:
        return explicit

    actions = safe_list(plan_or_meta.get("actions"))
    if not actions:
        return ""
    canonical_actions: List[Dict[str, str]] = []
    for action in actions:
        rec = safe_dict(action)
        source_id = safe_str(rec.get("canonical_source_id"))
        source_type = safe_str(rec.get("canonical_source_type"))
        if not source_id and not source_type:
            continue
        canonical_actions.append(
            {
                "canonical_source_id": source_id,
                "canonical_source_type": source_type,
                "layer": safe_str(rec.get("layer")),
                "task": safe_str(rec.get("task")),
            }
        )
    if not canonical_actions:
        return ""
    payload = {
        "project_name": safe_str(plan_or_meta.get("project_name") or meta.get("project_name")),
        "revision": safe_str(meta.get("revision")),
        "issue_date": safe_str(meta.get("issue_date")),
        "canonical_actions": sorted(
            canonical_actions,
            key=lambda item: (
                item["canonical_source_type"],
                item["canonical_source_id"],
                item["layer"],
                item["task"],
            ),
        ),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"plan-sha256:{digest[:16]}"


def _construction_package_record(meta: Dict[str, Any]) -> Dict[str, Any]:
    package = safe_dict(
        meta.get("construction_deliverable_package")
        or meta.get("construction_package")
        or meta.get("deliverable_package")
    )
    packages = safe_list(meta.get("deliverable_packages"))
    if not package and packages:
        package = safe_dict(packages[-1])
    return package


def _construction_package_artifacts(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    artifacts = [safe_dict(item) for item in safe_list(package.get("artifacts"))]
    if not artifacts:
        artifacts = [safe_dict(item) for item in safe_list(package.get("files"))]
    return artifacts


def _construction_package_artifact_status(plan_or_meta: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    package = _construction_package_record(meta)
    artifacts = _construction_package_artifacts(package)
    artifact_types = {_artifact_type(item) for item in artifacts if _artifact_type(item)}
    cost_aliases = _cost_artifact_aliases()
    current_cost_reference = _current_cost_reference(meta)
    package_identity = _package_identity(package)
    package_model_reference = _model_reference(package)
    expected_model_reference = _expected_model_reference(plan_or_meta, meta)
    missing: List[str] = []
    present: List[str] = []
    for required in REQUIRED_CONSTRUCTION_ARTIFACTS:
        artifact_id = safe_str(required.get("artifact_id"))
        aliases = set(required.get("aliases") or ())
        if artifact_types.intersection(aliases):
            present.append(artifact_id)
        else:
            missing.append(artifact_id)
    anonymous = [
        safe_str(item.get("type") or item.get("artifact_type"), "artifact")
        for item in artifacts
        if not safe_str(item.get("id") or item.get("artifact_id") or item.get("name") or item.get("filename") or item.get("path"))
    ]
    stale = [
        safe_str(item.get("id") or item.get("name") or item.get("type") or item.get("artifact_type"), "artifact")
        for item in artifacts
        if safe_dict(item).get("stale") is True or safe_dict(item).get("current") is False
    ]
    untraced: List[str] = []
    mismatched: List[str] = []
    if package_model_reference and (not expected_model_reference or package_model_reference == expected_model_reference):
        for item in artifacts:
            artifact_name = safe_str(item.get("id") or item.get("name") or item.get("type") or item.get("artifact_type"), "artifact")
            artifact_model_reference = _model_reference(item)
            if not artifact_model_reference:
                untraced.append(artifact_name)
            elif artifact_model_reference != package_model_reference:
                mismatched.append(artifact_name)
    cost_untraced: List[str] = []
    cost_mismatched: List[str] = []
    if safe_str(current_cost_reference.get("cost_estimate_hash")) or safe_str(current_cost_reference.get("quantity_model_hash")):
        for item in artifacts:
            if _artifact_type(item) not in cost_aliases:
                continue
            artifact_name = safe_str(item.get("id") or item.get("name") or item.get("type") or item.get("artifact_type"), "cost_estimate")
            artifact_cost_hash = safe_str(item.get("cost_estimate_hash") or item.get("source_cost_estimate_hash") or item.get("cost_hash"))
            artifact_quantity_hash = safe_str(item.get("quantity_model_hash") or item.get("source_quantity_model_hash"))
            artifact_price_hash = safe_str(item.get("price_book_hash") or item.get("source_price_book_hash"))
            current_cost_hash = safe_str(current_cost_reference.get("cost_estimate_hash"))
            current_quantity_hash = safe_str(current_cost_reference.get("quantity_model_hash"))
            current_price_hash = safe_str(current_cost_reference.get("price_book_hash"))
            matches_cost_hash = bool(artifact_cost_hash and current_cost_hash and artifact_cost_hash == current_cost_hash)
            matches_quantity_and_price = bool(
                artifact_quantity_hash
                and current_quantity_hash
                and artifact_quantity_hash == current_quantity_hash
                and (not current_price_hash or artifact_price_hash == current_price_hash)
            )
            if not artifact_cost_hash and not artifact_quantity_hash:
                cost_untraced.append(artifact_name)
            elif not matches_cost_hash and not matches_quantity_and_price:
                cost_mismatched.append(artifact_name)
    release_flag = package.get("release_ready")
    production_flag = package.get("production_ready")
    explicit_release_block = release_flag is False or production_flag is False
    model_matches_expected = bool(
        package_model_reference and (not expected_model_reference or package_model_reference == expected_model_reference)
    )
    complete_for_release = bool(
        package
        and package_identity
        and not missing
        and not anonymous
        and not stale
        and package_model_reference
        and model_matches_expected
        and not untraced
        and not mismatched
        and not cost_untraced
        and not cost_mismatched
        and not explicit_release_block
    )
    return {
        "package_present": bool(package),
        "package_identity": package_identity,
        "package_identity_present": bool(package_identity),
        "artifact_count": len(artifacts),
        "required": [safe_str(item.get("artifact_id")) for item in REQUIRED_CONSTRUCTION_ARTIFACTS],
        "present": present,
        "missing": missing,
        "anonymous": anonymous,
        "stale": stale,
        "untraced": untraced,
        "mismatched": mismatched,
        "cost_untraced": cost_untraced,
        "cost_mismatched": cost_mismatched,
        "current_cost_reference": current_cost_reference,
        "package_model_reference": package_model_reference,
        "expected_model_reference": expected_model_reference,
        "model_reference_present": bool(package_model_reference),
        "model_matches_expected": model_matches_expected,
        "release_ready_flag": release_flag,
        "production_ready_flag": production_flag,
        "complete_for_release": complete_for_release,
        "review_package_state": "assembled_traceable" if complete_for_release else "review_only_incomplete",
}


def _professional_package_release_status(meta: Dict[str, Any], package: Dict[str, Any], artifact_status: Dict[str, Any]) -> Dict[str, Any]:
    professional = safe_dict(meta.get("professional_review") or meta.get("engineer_review"))
    package_identity = safe_str(artifact_status.get("package_identity")) or _package_identity(package)
    package_model_reference = safe_str(artifact_status.get("package_model_reference")) or _model_reference(package)
    professional_model_reference = _model_reference(professional)
    professional_package_reference = safe_str(
        professional.get("construction_package_id")
        or professional.get("reviewed_package_id")
        or professional.get("package_id")
        or professional.get("released_package_id")
    )
    return {
        "professional_review_present": bool(professional),
        "professional_model_reference": professional_model_reference,
        "professional_package_reference": professional_package_reference,
        "model_matches_package": bool(
            professional_model_reference and package_model_reference and professional_model_reference == package_model_reference
        ),
        "package_matches_review": bool(
            professional_package_reference and package_identity and professional_package_reference == package_identity
        ),
    }


def _construction_package_blockers(plan_or_meta: Dict[str, Any], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    package = _construction_package_record(meta)
    if not package:
        return [
            {
                "area": "deliverables",
                "field": "construction_package_artifacts",
                "why_needed": "Construction release requires an assembled deliverable package, not only readiness metadata.",
                "suggested_next_action": "Assemble sheets, CAD exports, QA report, cost estimate, and package manifest artifacts.",
            }
        ]
    artifact_status = _construction_package_artifact_status(plan_or_meta, meta)
    professional_release_status = _professional_package_release_status(meta, package, artifact_status)
    package_model_reference = _model_reference(package)
    expected_model_reference = safe_str(artifact_status.get("expected_model_reference"))
    blockers: List[Dict[str, Any]] = []
    if not bool(artifact_status.get("package_identity_present")):
        blockers.append(
            {
                "area": "deliverables",
                "field": "construction_package_identity",
                "why_needed": "Construction package needs a stable package ID/name/path so professional signoff can trace the released package.",
                "suggested_next_action": "Assign a stable construction package ID or manifest ID before release.",
            }
        )
    missing = [safe_str(item) for item in safe_list(artifact_status.get("missing")) if safe_str(item)]
    if missing:
        blockers.append(
            {
                "area": "deliverables",
                "field": "construction_package_artifacts",
                "why_needed": "Construction package is missing required artifact types: " + ", ".join(missing) + ".",
                "suggested_next_action": "Regenerate the construction deliverable package with every required artifact type.",
            }
        )
    anonymous = [safe_str(item) for item in safe_list(artifact_status.get("anonymous")) if safe_str(item)]
    if anonymous:
        blockers.append(
            {
                "area": "deliverables",
                "field": "construction_package_artifact_identity",
                "why_needed": "Construction package artifacts need stable IDs, names, filenames, or paths for release traceability: "
                + ", ".join(anonymous[:5])
                + ".",
                "suggested_next_action": "Regenerate or annotate package artifacts with stable IDs/filenames before release.",
            }
        )
    stale = [safe_str(item) for item in safe_list(artifact_status.get("stale")) if safe_str(item)]
    if stale:
        blockers.append(
            {
                "area": "deliverables",
                "field": "stale_construction_package_artifacts",
                "why_needed": "Construction package contains stale artifacts: " + ", ".join(stale[:5]) + ".",
                "suggested_next_action": "Regenerate stale package artifacts from the final canonical model.",
            }
        )
    if not package_model_reference:
        blockers.append(
            {
                "area": "deliverables",
                "field": "construction_package_model_reference",
                "why_needed": "Construction package must identify the final canonical model used to generate its artifacts.",
                "suggested_next_action": "Attach canonical_model_id/hash or source_model_id/hash to the assembled package.",
            }
        )
    elif expected_model_reference and package_model_reference != expected_model_reference:
        blockers.append(
            {
                "area": "deliverables",
                "field": "construction_package_model_mismatch",
                "why_needed": "Construction package model reference does not match the final canonical model fingerprint.",
                "suggested_next_action": "Regenerate the package from the current final model and attach its canonical model fingerprint.",
            }
        )
    else:
        untraced_artifacts = [safe_str(item) for item in safe_list(artifact_status.get("untraced")) if safe_str(item)]
        mismatched_artifacts = [safe_str(item) for item in safe_list(artifact_status.get("mismatched")) if safe_str(item)]
        if untraced_artifacts:
            blockers.append(
                {
                    "area": "deliverables",
                    "field": "untraced_construction_package_artifacts",
                    "why_needed": "Construction package artifacts are missing final canonical model traceability: "
                    + ", ".join(untraced_artifacts[:5])
                    + ".",
                    "suggested_next_action": "Regenerate or annotate package artifacts with the final canonical model reference.",
                }
            )
        if mismatched_artifacts:
            blockers.append(
                {
                    "area": "deliverables",
                    "field": "mismatched_construction_package_artifacts",
                    "why_needed": "Construction package artifacts do not all reference the package final canonical model: "
                    + ", ".join(mismatched_artifacts[:5])
                    + ".",
                    "suggested_next_action": "Regenerate mismatched package artifacts from the final canonical model.",
                }
            )
        cost_untraced = [safe_str(item) for item in safe_list(artifact_status.get("cost_untraced")) if safe_str(item)]
        cost_mismatched = [safe_str(item) for item in safe_list(artifact_status.get("cost_mismatched")) if safe_str(item)]
        if cost_untraced:
            blockers.append(
                {
                    "area": "cost",
                    "field": "cost_estimate_artifact_traceability",
                    "why_needed": "Cost estimate artifacts must identify the exact cost estimate or quantity/price-book hashes they package: "
                    + ", ".join(cost_untraced[:5])
                    + ".",
                    "suggested_next_action": "Regenerate the cost artifact from the current cost estimate and attach cost_estimate_hash or quantity_model_hash/price_book_hash.",
                }
            )
        if cost_mismatched:
            blockers.append(
                {
                    "area": "cost",
                    "field": "cost_estimate_artifact_mismatch",
                    "why_needed": "Cost estimate artifacts do not match the current cost estimate: "
                    + ", ".join(cost_mismatched[:5])
                    + ".",
                    "suggested_next_action": "Regenerate stale cost artifacts from the current canonical quantity model and unit-price book.",
                }
            )
    if package.get("production_ready") is False or package.get("release_ready") is False:
        blockers.append(
            {
                "area": "deliverables",
                "field": "construction_package_release_ready",
                "why_needed": "Construction package is explicitly marked not ready for release.",
                "suggested_next_action": "Resolve package assembly blockers and mark the package release-ready.",
            }
        )
    if not bool(professional_release_status.get("professional_review_present")):
        blockers.append(
            {
                "area": "professional_review",
                "field": "released_package_reference",
                "why_needed": "Construction package release requires professional review evidence tied to the released package.",
                "suggested_next_action": "Attach professional_review metadata with reviewed package and canonical model references.",
            }
        )
    elif not safe_str(professional_release_status.get("professional_model_reference")):
        blockers.append(
            {
                "area": "professional_review",
                "field": "released_model_reference",
                "why_needed": "Professional release must identify the final canonical model it reviewed.",
                "suggested_next_action": "Attach canonical_model_id/hash to professional_review before release.",
            }
        )
    elif not bool(professional_release_status.get("model_matches_package")):
        blockers.append(
            {
                "area": "professional_review",
                "field": "released_model_mismatch",
                "why_needed": "Professional release canonical model reference does not match the construction package model.",
                "suggested_next_action": "Reissue professional release evidence against the current final package model reference.",
            }
        )
    if bool(professional_release_status.get("professional_review_present")):
        if not safe_str(professional_release_status.get("professional_package_reference")):
            blockers.append(
                {
                    "area": "professional_review",
                    "field": "released_package_reference",
                    "why_needed": "Professional release must identify the construction package it reviewed.",
                    "suggested_next_action": "Attach reviewed_package_id or construction_package_id to professional_review.",
                }
            )
        elif not bool(professional_release_status.get("package_matches_review")):
            blockers.append(
                {
                    "area": "professional_review",
                    "field": "released_package_mismatch",
                    "why_needed": "Professional release package reference does not match the assembled construction package.",
                    "suggested_next_action": "Reissue professional release evidence against the current construction package ID.",
                }
            )
    return blockers


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
    expected_model_reference = _expected_model_reference(plan_or_meta, meta)
    artifact_status = _construction_package_artifact_status(plan_or_meta, meta)
    professional_release_status = _professional_package_release_status(
        meta,
        _construction_package_record(meta),
        artifact_status,
    )
    package_blockers = _construction_package_blockers(plan_or_meta, meta) if readiness.get("ready") is True else []
    blockers = _unique_blockers([*blockers, *package_blockers])
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
        "expected_canonical_model_reference": expected_model_reference,
        "construction_package_artifact_status": artifact_status,
        "professional_package_release_status": professional_release_status,
        "sections": sections,
        "blocked_sections": blocked_sections,
        "review_sections": review_sections,
        "blockers": blockers,
        "warnings": warnings,
        "package_artifact_requirements": [
            {
                "artifact_id": safe_str(item.get("artifact_id")),
                "aliases": sorted(str(alias) for alias in (item.get("aliases") or ())),
            }
            for item in REQUIRED_CONSTRUCTION_ARTIFACTS
        ],
        "next_actions": [safe_str(item.get("suggested_next_action")) for item in blockers[:10] if safe_str(item.get("suggested_next_action"))],
        "truth_label": (
            "Review packages may be generated while blocked, but construction release requires all sections ready "
            "plus licensed professional release evidence. Civora does not stamp drawings."
        ),
    }


__all__ = ["CONSTRUCTION_PACKAGE_SECTIONS", "REQUIRED_CONSTRUCTION_ARTIFACTS", "build_construction_package_manifest"]
