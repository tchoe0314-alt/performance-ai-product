from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Sequence

from core.civil_design import construction_readiness
from core.config import PRODUCT_MODE, REVIEW_ONLY_PRODUCT_MODES
from core.professional_release import validate_professional_release

from .common import construction_package_record, readiness_issue_explanations, safe_dict, safe_list, safe_str
from .dwg_compatibility import DWG_UNSUPPORTED_STATUS, dwg_strategy_from_meta


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


CONSTRUCTION_DOCUMENT_SUPPORT_SECTIONS: Sequence[Dict[str, Any]] = (
    {
        "section_id": "site_plan",
        "label": "Site Plan",
        "evidence_keys": ("layout", "site_plan", "actions"),
        "blocker_areas": ("layout", "civil_design", "site_plan"),
        "artifact_keys": ("sheet_registry", "export_package_report_v1", "review_package_manifest"),
        "review_when_present": False,
    },
    {
        "section_id": "grading_plan",
        "label": "Grading Plan",
        "evidence_keys": ("grading", "grading_summary", "surfaces", "contours"),
        "blocker_areas": ("grading", "grading_detail", "surface", "terrain"),
        "artifact_keys": ("sheet_registry", "export_package_report_v1"),
        "review_when_present": False,
    },
    {
        "section_id": "drainage_plan",
        "label": "Drainage Plan",
        "evidence_keys": ("drainage", "storm_pipes", "storm_summary", "hydrology"),
        "blocker_areas": ("drainage", "storm", "storm_pipe", "hydrology", "hydraulics"),
        "artifact_keys": ("sheet_registry", "export_package_report_v1"),
        "review_when_present": False,
    },
    {
        "section_id": "utility_plan",
        "label": "Utility Plan",
        "evidence_keys": ("utilities", "sanitary", "water", "utility_summary", "sanitary_summary", "water_summary"),
        "blocker_areas": ("utilities", "utility", "sanitary", "water", "coordination"),
        "artifact_keys": ("sheet_registry", "export_package_report_v1"),
        "review_when_present": False,
    },
    {
        "section_id": "profiles",
        "label": "Profiles",
        "evidence_keys": ("profiles", "road_profiles"),
        "blocker_areas": ("profiles", "roadway", "corridor"),
        "blocker_fields": ("profiles", "road_profiles", "profile_section", "depth_validation"),
        "artifact_keys": ("export_package_report_v1",),
        "artifact_record_key": "profile_packages",
        "review_when_present": False,
    },
    {
        "section_id": "sections",
        "label": "Sections",
        "evidence_keys": ("cross_sections", "corridor_sections"),
        "blocker_areas": ("sections", "cross_sections", "roadway", "corridor"),
        "blocker_fields": ("sections", "cross_sections", "corridor_sections", "profile_section", "depth_validation"),
        "artifact_keys": ("export_package_report_v1",),
        "artifact_record_key": "section_packages",
        "review_when_present": False,
    },
    {
        "section_id": "quantities",
        "label": "Quantities",
        "evidence_keys": ("quantities", "quantity_summary", "cost_estimate"),
        "blocker_areas": ("quantity", "quantities", "cost"),
        "artifact_keys": ("export_package_report_v1", "cost_package_status"),
        "artifact_record_key": "quantity_line_items",
        "review_when_present": False,
    },
    {
        "section_id": "assumptions",
        "label": "Assumptions",
        "evidence_keys": ("assumptions", "assumption_log", "assumption_summary"),
        "blocker_areas": ("assumptions",),
        "artifact_keys": ("engineer_review_package", "engineer_review_package_v1"),
        "review_when_present": True,
    },
    {
        "section_id": "qa_blockers",
        "label": "QA Blockers",
        "evidence_keys": ("qa", "truth_audit", "manual_validation", "blockers", "construction_readiness"),
        "blocker_areas": ("qa", "manual_validation", "reactive_model", "deliverables", "professional_review"),
        "artifact_keys": ("export_audit", "review_package_manifest", "construction_package_manifest"),
        "review_when_present": False,
    },
    {
        "section_id": "standards_sources",
        "label": "Standards Sources",
        "evidence_keys": ("standards_package", "standards_review_packet", "standards_acceptance", "standards"),
        "blocker_areas": ("standards",),
        "artifact_keys": ("standards_package",),
        "review_when_present": True,
    },
    {
        "section_id": "existing_conditions",
        "label": "Existing Conditions",
        "evidence_keys": ("existing_conditions_package", "existing_conditions_summary", "existing_conditions"),
        "blocker_areas": ("existing_conditions",),
        "artifact_keys": ("existing_conditions_package",),
        "review_when_present": True,
    },
    {
        "section_id": "engineer_review_checklist",
        "label": "Engineer Review Checklist",
        "evidence_keys": ("engineer_review_package", "engineer_review_package_v1"),
        "blocker_areas": ("engineer_approval", "professional_review"),
        "artifact_keys": ("engineer_review_package", "engineer_review_package_v1"),
        "review_when_present": True,
    },
)

SUPPORT_PACKAGE_RESPONSIBILITY_LABEL = (
    "Construction-document-support package only. Civora never stamps, seals, signs, certifies, approves "
    "construction, submits construction documents, or acts as engineer of record. The engineer/user must "
    "review, approve, sign, seal, and submit externally where required."
)


def _normalize_product_mode(value: str) -> str:
    normalized = safe_str(value or "private_alpha").lower().replace("-", "_")
    aliases = {
        "alpha": "private_alpha",
        "review": "private_alpha",
        "review_only": "private_alpha",
        "beta": "public_beta",
    }
    return aliases.get(normalized, normalized or "private_alpha")


def _construction_release_guard(meta: Dict[str, Any]) -> Dict[str, Any]:
    product_mode = _normalize_product_mode(
        safe_str(meta.get("product_mode") or meta.get("deployment_mode") or PRODUCT_MODE)
    )
    review_only = product_mode in REVIEW_ONLY_PRODUCT_MODES
    construction_release_enabled = product_mode == "production"
    blocked = review_only or not construction_release_enabled
    return {
        "product_mode": product_mode,
        "review_only": review_only,
        "construction_release_enabled": construction_release_enabled and not review_only,
        "construction_release_blocked": blocked,
        "guard_reason": (
            "Private alpha/review-only mode blocks construction release."
            if review_only
            else "Construction release requires production mode plus package and professional review gates."
            if blocked
            else ""
        ),
        "truth_label": (
            "Review packages may be generated in private alpha, but construction release remains blocked."
            if blocked
            else "Production mode still requires every construction package gate before release."
        ),
    }


def _construction_release_guard_blocker(guard: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "area": "professional_review",
        "field": "alpha_review_only_guard",
        "why_needed": "Private alpha is review-only and must not issue construction-release packages.",
        "suggested_next_action": "Keep review package output blocked until Civora is explicitly configured for production release and all construction gates pass.",
        "severity": "blocker",
        "message": safe_str(guard.get("guard_reason")),
    }


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


def _construction_package_artifacts(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    artifacts = [safe_dict(item) for item in safe_list(package.get("artifacts"))]
    if not artifacts:
        artifacts = [safe_dict(item) for item in safe_list(package.get("files"))]
    return artifacts


def _construction_package_artifact_status(plan_or_meta: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    package = construction_package_record(meta)
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
    cost_artifacts = [item for item in artifacts if _artifact_type(item) in cost_aliases]
    if cost_artifacts and not (
        safe_str(current_cost_reference.get("cost_estimate_hash"))
        or safe_str(current_cost_reference.get("quantity_model_hash"))
    ):
        cost_untraced.extend(
            safe_str(item.get("id") or item.get("name") or item.get("type") or item.get("artifact_type"), "cost_estimate")
            for item in cost_artifacts
        )
    elif cost_artifacts:
        for item in cost_artifacts:
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
        and release_flag is True
        and production_flag is True
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


def _review_package_record(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Return a user-assembled deliverable package, excluding generated manifests."""

    for key in ("construction_package", "construction_deliverable_package", "deliverable_package"):
        package = safe_dict(meta.get(key))
        if package:
            return dict(package)
    packages = safe_list(meta.get("deliverable_packages"))
    if packages:
        return dict(safe_dict(packages[-1]))
    package_manifest = safe_dict(meta.get("construction_package_manifest"))
    if package_manifest and safe_str(package_manifest.get("source")) != "construction_package_manifest_v1":
        return dict(package_manifest)
    return {}


def _sheet_registry_ready(meta: Dict[str, Any]) -> bool:
    registry = meta.get("sheet_registry")
    if isinstance(registry, list):
        return bool(registry)
    record = safe_dict(registry)
    if not record:
        return False
    return bool(safe_list(record.get("sheets")) or safe_list(record.get("registry")) or record.get("sheet_total") or record.get("count"))


def _export_audit_ready(meta: Dict[str, Any]) -> bool:
    audit = safe_dict(meta.get("export_audit"))
    if not audit:
        return False
    ready_flag = audit.get("production_export_ready")
    if ready_flag is None:
        ready_flag = audit.get("ready")
    if ready_flag is None:
        ready_flag = audit.get("success")
    return bool(ready_flag) and audit.get("export_blocked") is not True


def _format_export_confidence(format_id: str, *, available: bool, review_ready: bool, status: str, blocker: str = "") -> Dict[str, Any]:
    blockers = [blocker] if blocker else []
    return {
        "format": format_id,
        "available": bool(available),
        "review_ready": bool(review_ready),
        "construction_ready": False,
        "status": status,
        "confidence": "audited_review" if review_ready else "blocked_or_unverified",
        "blockers": blockers,
    }


def _review_package_export_confidence(meta: Dict[str, Any]) -> Dict[str, Any]:
    cad = safe_dict(meta.get("cad_interop"))
    dwg_strategy = dwg_strategy_from_meta({**meta, "cad_interop": cad})
    audit = safe_dict(meta.get("export_audit"))
    audit_ready = _export_audit_ready(meta)
    export_blocked = bool(audit.get("export_blocked"))
    dxf_available = cad.get("dxf") is True
    dxf_ready = bool(dxf_available and audit_ready)
    pipe_contract = bool(cad.get("landxml_pipe_network_contract") or cad.get("landxml") is True)
    dwg_available = bool(dwg_strategy["dwg_export_supported"])
    civil3d_available = cad.get("civil3d") is True

    if dxf_ready:
        dxf_status = "audited_review_ready"
        dxf_blocker = ""
    elif not dxf_available:
        dxf_status = "not_available"
        dxf_blocker = "DXF exporter metadata is missing."
    elif not audit:
        dxf_status = "blocked_missing_export_audit"
        dxf_blocker = "DXF review requires a current export audit."
    elif export_blocked:
        dxf_status = "blocked_by_export_audit"
        dxf_blocker = "DXF review is blocked by the export audit."
    else:
        dxf_status = "blocked_export_audit_not_ready"
        dxf_blocker = "DXF review requires export_audit ready/production_export_ready true."

    landxml_status = (
        "pipe_network_contract_review_ready_not_civil3d_verified"
        if pipe_contract and audit_ready
        else "pipe_network_contract_available_not_audited"
        if pipe_contract
        else "not_available"
    )
    landxml_blocker = (
        ""
        if pipe_contract and audit_ready
        else "LandXML pipe-network contract requires a current export audit."
        if pipe_contract
        else "LandXML writer/contract is not available for this package."
    )

    civil3d_status = "available_not_verified" if civil3d_available else "not_verified"
    dwg_status = safe_str(dwg_strategy.get("dwg_status"), DWG_UNSUPPORTED_STATUS)

    formats = {
        "dxf": _format_export_confidence(
            "dxf",
            available=dxf_available,
            review_ready=dxf_ready,
            status=dxf_status,
            blocker=dxf_blocker,
        ),
        "landxml": _format_export_confidence(
            "landxml",
            available=pipe_contract,
            review_ready=bool(pipe_contract and audit_ready),
            status=landxml_status,
            blocker=landxml_blocker,
        ),
        "civil3d": _format_export_confidence(
            "civil3d",
            available=civil3d_available,
            review_ready=False,
            status=civil3d_status,
            blocker=(
                "Civil 3D compatibility is not verified by an implemented writer/checker."
                if civil3d_available
                else "Civil 3D export is not implemented and must remain blocked."
            ),
        ),
        "dwg": _format_export_confidence(
            "dwg",
            available=dwg_available,
            review_ready=bool(dwg_strategy["dwg_review_ready"]),
            status=dwg_status,
            blocker=(
                "DWG export requires the configured conversion hook and workflow record before it can be reviewed."
                if dwg_available
                else "DWG export is unsupported until a real DWG writer or configured external conversion hook exists."
            ),
        ),
    }
    return {
        "source": "review_package_export_confidence_v1",
        "export_audit_present": bool(audit),
        "export_audit_ready": audit_ready,
        "export_audit_blocked": export_blocked,
        "formats": formats,
        "primary_review_format": "dxf" if dxf_ready else "",
        "review_ready": dxf_ready,
        "dwg_strategy": dwg_strategy,
        "construction_confidence_blockers": [
            "Civil 3D export is not implemented/verified.",
            "DWG export is unsupported until a real DWG writer or configured external conversion hook exists.",
            "LandXML is review-only unless externally verified against the target Civil 3D workflow.",
        ],
        "truth_label": (
            "DXF is the only audited review export path when export_audit passes. LandXML is contract-level; "
            "Civil 3D and DWG are not production export paths."
        ),
    }


def build_review_package_manifest(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Build the private-alpha review package manifest.

    This manifest is deliberately separate from construction release. It says
    what an engineer/reviewer can inspect in alpha, and what remains blocked
    before any construction-grade deliverable claim.
    """

    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    package = _review_package_record(meta)
    expected_model_reference = _expected_model_reference(plan_or_meta, meta)
    package_identity = _package_identity(package)
    package_model_reference = _model_reference(package)
    model_matches_expected = bool(
        package_model_reference and (not expected_model_reference or package_model_reference == expected_model_reference)
    )
    sheet_ready = _sheet_registry_ready(meta)
    export_confidence = _review_package_export_confidence(meta)
    release_guard = _construction_release_guard(meta)
    review_blockers: List[Dict[str, Any]] = []

    if not sheet_ready:
        review_blockers.append(
            {
                "area": "deliverables",
                "field": "sheet_registry",
                "why_needed": "Alpha review package needs a sheet registry so reviewers can inspect the same drawing index.",
                "suggested_next_action": "Generate or attach the current sheet registry before assembling the review package.",
            }
        )
    if not bool(export_confidence.get("review_ready")):
        review_blockers.append(
            {
                "area": "deliverables",
                "field": "dxf_review_export",
                "why_needed": "Alpha review package needs an audited DXF export path; Civil3D/DWG cannot substitute for it yet.",
                "suggested_next_action": "Regenerate export metadata and resolve export_audit blockers.",
            }
        )
    if package and not package_identity:
        review_blockers.append(
            {
                "area": "deliverables",
                "field": "review_package_identity",
                "why_needed": "Reviewer handoff packages need a stable ID/name/path for traceability.",
                "suggested_next_action": "Attach a package ID or filename to the review package record.",
            }
        )
    if package and package_model_reference and not model_matches_expected:
        review_blockers.append(
            {
                "area": "deliverables",
                "field": "review_package_model_mismatch",
                "why_needed": "Review package model reference does not match the final canonical model fingerprint.",
                "suggested_next_action": "Regenerate the review package from the current final model.",
            }
        )

    generated_package_id = (
        package_identity
        or (f"review-{expected_model_reference}" if expected_model_reference else "review-package-pending-model-reference")
    )
    review_ready = bool(sheet_ready and export_confidence.get("review_ready") and not review_blockers)
    return {
        "success": True,
        "source": "review_package_manifest_v1",
        "package_type": "private_alpha_review",
        "review_package_id": generated_package_id,
        "review_ready": review_ready,
        "review_package_allowed": review_ready,
        "construction_ready": False,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "product_mode": release_guard["product_mode"],
        "review_only": True,
        "expected_canonical_model_reference": expected_model_reference,
        "package_present": bool(package),
        "package_identity": package_identity,
        "package_model_reference": package_model_reference,
        "package_model_matches_expected": model_matches_expected,
        "sheet_registry_ready": sheet_ready,
        "export_confidence": export_confidence,
        "review_blockers": _unique_blockers(review_blockers),
        "review_blocker_details": readiness_issue_explanations(review_blockers),
        "construction_confidence_blockers": safe_list(export_confidence.get("construction_confidence_blockers")),
        "construction_release_guard": release_guard,
        "truth_label": (
            "This is an alpha/review-only package manifest. It can describe reviewable DXF output, but it never "
            "authorizes construction release, stamping, DWG, or Civil 3D production confidence."
        ),
    }


def _professional_package_release_status(meta: Dict[str, Any], package: Dict[str, Any], artifact_status: Dict[str, Any]) -> Dict[str, Any]:
    professional = safe_dict(meta.get("professional_review") or meta.get("engineer_review"))
    validation = validate_professional_release(professional)
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
        "professional_release_valid": validation.get("released_for_construction") is True,
        "professional_release_validation": validation,
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
    package = construction_package_record(meta)
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
    if package.get("release_ready") is not True:
        blockers.append(
            {
                "area": "deliverables",
                "field": "construction_package_release_ready",
                "why_needed": "Construction package must be explicitly marked release_ready true after artifact assembly and audit.",
                "suggested_next_action": "Resolve package assembly blockers and mark the audited package release_ready true.",
            }
        )
    if package.get("production_ready") is not True:
        blockers.append(
            {
                "area": "deliverables",
                "field": "construction_package_production_ready",
                "why_needed": "Construction package must be explicitly marked production_ready true after release audit.",
                "suggested_next_action": "Resolve package assembly blockers and mark the audited package production_ready true.",
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
    elif not bool(professional_release_status.get("professional_release_valid")):
        validation = safe_dict(professional_release_status.get("professional_release_validation"))
        validation_fields = [
            safe_str(item.get("field"))
            for item in safe_list(validation.get("blockers"))
            if safe_str(safe_dict(item).get("field"))
        ]
        blockers.append(
            {
                "area": "professional_review",
                "field": "professional_release_validation",
                "why_needed": "Construction package release requires valid licensed professional release metadata, not only a package/model reference.",
                "suggested_next_action": (
                    "Complete professional release metadata before release"
                    + (": " + ", ".join(validation_fields[:6]) if validation_fields else ".")
                ),
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
        "blocker_details": readiness_issue_explanations(section_blockers),
        "warnings": section_warnings,
        "warning_details": readiness_issue_explanations(section_warnings),
        "next_actions": [safe_str(item.get("suggested_next_action")) for item in section_blockers[:4] if safe_str(item.get("suggested_next_action"))],
    }


def _value_present(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, bool):
        return value
    return value is not None and safe_str(value) != ""


def _support_canonical_ids_from_value(value: Any) -> List[str]:
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
                "alignment_id",
                "alignment_owner",
                "profile_id",
                "section_id",
                "pipe_id",
                "pipe_ids",
                "structure_id",
                "structure_ids",
                "surface_id",
                "surface_ids",
                "quantity_source_id",
                "quantity_source_ids",
                "quantity_model_hash",
                "cost_estimate_hash",
                "price_book_hash",
            }:
                ids.extend(_support_canonical_ids_from_value(item))
            elif isinstance(item, (dict, list)):
                ids.extend(_support_canonical_ids_from_value(item))
        return list(dict.fromkeys(safe_str(item) for item in ids if safe_str(item)))
    if isinstance(value, list):
        for item in value:
            ids.extend(_support_canonical_ids_from_value(item))
        return list(dict.fromkeys(safe_str(item) for item in ids if safe_str(item)))
    text = safe_str(value)
    return [text] if text else []


def _support_source_value(plan_or_meta: Dict[str, Any], meta: Dict[str, Any], key: str) -> tuple[str, Any]:
    if key == "actions":
        return ("plan", safe_list(plan_or_meta.get("actions")))
    if key in meta:
        return ("meta", meta.get(key))
    production_evidence = safe_dict(meta.get("production_evidence"))
    if key in production_evidence:
        return ("production_evidence", production_evidence.get(key))
    return ("", None)


def _meta_has_any(plan_or_meta: Dict[str, Any], meta: Dict[str, Any], keys: Sequence[str]) -> bool:
    for key in keys:
        if key == "actions" and safe_list(plan_or_meta.get("actions")):
            return True
        if _value_present(meta.get(key)):
            return True
    production_evidence = safe_dict(meta.get("production_evidence"))
    for key in keys:
        if _value_present(production_evidence.get(key)):
            return True
    return False


def _support_evidence_references(plan_or_meta: Dict[str, Any], meta: Dict[str, Any], keys: Sequence[str]) -> List[Dict[str, Any]]:
    references: List[Dict[str, Any]] = []
    for key in keys:
        source, value = _support_source_value(plan_or_meta, meta, key)
        if not source or not _value_present(value):
            continue
        rec = safe_dict(value)
        references.append(
            {
                "key": key,
                "source": source,
                "present": True,
                "record_type": "list" if isinstance(value, list) else "dict" if isinstance(value, dict) else type(value).__name__,
                "record_count": len(value) if isinstance(value, list) else len(rec) if rec else 1,
                "status": safe_str(rec.get("status") or rec.get("review_status") or rec.get("source")),
                "reference_id": safe_str(
                    rec.get("id")
                    or rec.get("package_id")
                    or rec.get("review_package_id")
                    or rec.get("manifest_id")
                    or rec.get("version")
                    or rec.get("source")
                ),
                "canonical_ids": _support_canonical_ids_from_value(value)[:25],
            }
        )
    return references


def _support_missing_inputs(keys: Sequence[str], evidence_present: Dict[str, bool]) -> List[Dict[str, Any]]:
    if any(evidence_present.get(key) for key in keys):
        return []
    missing_keys = [key for key in keys if not evidence_present.get(key)]
    return [
        {
            "field": "section_evidence",
            "missing_evidence_keys": missing_keys,
            "reason": "No source evidence is available for this construction-document-support package section.",
            "severity": "missing_input",
            "engineer_review_required": True,
        }
    ]


def _support_linked_artifacts(meta: Dict[str, Any], definition: Dict[str, Any]) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for key in definition.get("artifact_keys") or ():
        key_text = safe_str(key)
        value = meta.get(key_text)
        if not _value_present(value):
            continue
        rec = safe_dict(value)
        artifact = {
            "artifact_key": key_text,
            "present": True,
            "status": safe_str(rec.get("status") or rec.get("review_status") or rec.get("source")),
            "artifact_id": safe_str(rec.get("id") or rec.get("package_id") or rec.get("review_package_id") or rec.get("source")),
            "canonical_ids": _support_canonical_ids_from_value(value)[:25],
        }
        record_key = safe_str(definition.get("artifact_record_key"))
        if record_key and rec:
            records = safe_list(rec.get(record_key))
            artifact["linked_record_key"] = record_key
            artifact["linked_record_count"] = len(records)
            artifact["linked_record_ids"] = [
                safe_str(item.get("record_id") or item.get("id") or item.get("metric") or item.get("name"))
                for item in (safe_dict(row) for row in records)
                if safe_str(item.get("record_id") or item.get("id") or item.get("metric") or item.get("name"))
            ][:25]
        artifacts.append(artifact)
    return artifacts


def _support_stale_dirty_status(meta: Dict[str, Any], section_id: str, evidence_keys: Sequence[str]) -> Dict[str, Any]:
    export_audit = safe_dict(meta.get("export_audit"))
    reactive_report = safe_dict(meta.get("reactive_update_report"))
    stale_status = safe_dict(export_audit.get("stale_output_status"))
    canonical_integrity = safe_dict(export_audit.get("canonical_integrity"))
    dirty_values = (
        safe_list(stale_status.get("dirty_stages"))
        + safe_list(canonical_integrity.get("dirty_stages"))
        + safe_list(meta.get("stale_outputs"))
        + safe_list(meta.get("invalidated_targets") or meta.get("dependency_invalidated_targets"))
        + safe_list(reactive_report.get("dirty_engine_ids"))
        + safe_list(reactive_report.get("dirty_state"))
    )
    section_terms = {section_id, *evidence_keys}
    matched = [
        safe_str(item)
        for item in dirty_values
        if safe_str(item) and (safe_str(item) in section_terms or any(term and term in safe_str(item) for term in section_terms))
    ]
    export_report = safe_dict(meta.get("export_package_report_v1"))
    stale_report_values = safe_list(export_report.get("stale_outputs_detected"))
    matched.extend(
        safe_str(item)
        for item in stale_report_values
        if safe_str(item) and (safe_str(item) in section_terms or any(term and term in safe_str(item) for term in section_terms))
    )
    return {
        "stale": bool(matched),
        "dirty": bool(matched),
        "dirty_references": list(dict.fromkeys(item for item in matched if item)),
        "source": "export_audit/reactive_update_report/export_package_report_v1",
    }


def _support_confidence(*, present: bool, section_blockers: Sequence[Dict[str, Any]], missing_inputs: Sequence[Dict[str, Any]], stale_dirty: Dict[str, Any], linked_artifacts: Sequence[Dict[str, Any]]) -> str:
    if stale_dirty.get("stale") or stale_dirty.get("dirty"):
        return "stale_or_dirty"
    if not present:
        return "missing"
    if section_blockers:
        return "blocked"
    if missing_inputs:
        return "partial"
    if linked_artifacts:
        return "traceable_review_evidence"
    return "review_evidence_present"


def _support_package_blockers(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    for source_key in ("construction_readiness", "civil_design_readiness", "engineer_review_package"):
        source = safe_dict(meta.get(source_key))
        blockers.extend(safe_dict(item) for item in safe_list(source.get("blockers")) if safe_dict(item))
        blockers.extend(safe_dict(item) for item in safe_list(source.get("critical_blockers")) if safe_dict(item))
        blockers.extend(safe_dict(item) for item in safe_list(source.get("production_blockers")) if safe_dict(item))
    export_audit = safe_dict(meta.get("export_audit"))
    for item in safe_list(export_audit.get("blocked_reasons") or export_audit.get("blockers")):
        if isinstance(item, dict):
            blockers.append(safe_dict(item))
        elif safe_str(item):
            blockers.append({"area": "deliverables", "field": safe_str(item), "reason": safe_str(item)})
    for item in safe_list(meta.get("blockers")):
        if isinstance(item, dict):
            blockers.append(safe_dict(item))
        elif safe_str(item):
            blockers.append({"area": "qa", "field": safe_str(item), "reason": safe_str(item)})
    return _unique_blockers(blockers)


def _support_package_assumptions(meta: Dict[str, Any]) -> List[Any]:
    assumptions: List[Any] = []
    for key in ("assumptions", "assumption_log", "assumption_summary"):
        value = meta.get(key)
        if isinstance(value, list):
            assumptions.extend(deepcopy(value))
        elif isinstance(value, dict):
            assumptions.append(deepcopy(value))
        elif safe_str(value):
            assumptions.append(safe_str(value))
    return assumptions


def _support_section_record(
    plan_or_meta: Dict[str, Any],
    meta: Dict[str, Any],
    definition: Dict[str, Any],
    blockers: Sequence[Dict[str, Any]],
    assumptions: Sequence[Any],
) -> Dict[str, Any]:
    section_id = safe_str(definition.get("section_id"))
    evidence_keys = tuple(safe_str(item) for item in (definition.get("evidence_keys") or ()) if safe_str(item))
    blocker_areas = {safe_str(item) for item in (definition.get("blocker_areas") or ()) if safe_str(item)}
    blocker_fields = {safe_str(item) for item in (definition.get("blocker_fields") or ()) if safe_str(item)}
    present = _meta_has_any(plan_or_meta, meta, evidence_keys)
    evidence_present = {key: _meta_has_any(plan_or_meta, meta, (key,)) for key in evidence_keys}
    source_evidence_references = _support_evidence_references(plan_or_meta, meta, evidence_keys)
    canonical_ids = list(
        dict.fromkeys(
            canonical_id
            for reference in source_evidence_references
            for canonical_id in safe_list(reference.get("canonical_ids"))
            if safe_str(canonical_id)
        )
    )
    missing_inputs = _support_missing_inputs(evidence_keys, evidence_present)
    linked_artifacts = _support_linked_artifacts(meta, definition)
    for artifact in linked_artifacts:
        canonical_ids.extend(safe_list(artifact.get("canonical_ids")))
    canonical_ids = list(dict.fromkeys(safe_str(item) for item in canonical_ids if safe_str(item)))
    stale_dirty_status = _support_stale_dirty_status(meta, section_id, evidence_keys)

    def matches_section_blocker(item: Dict[str, Any]) -> bool:
        area = safe_str(item.get("area"))
        field = safe_str(item.get("field"))
        if field and field in blocker_fields:
            return True
        if field and field in blocker_areas:
            return True
        if area == "profile_section" and blocker_fields:
            return not field or field in blocker_fields
        return area in blocker_areas

    section_blockers = [deepcopy(item) for item in blockers if matches_section_blocker(item)]
    if missing_inputs:
        section_blockers.extend(
            {
                "area": section_id,
                "field": item["field"],
                "reason": item["reason"],
                "message": item["reason"],
                "severity": "missing_input",
                "engineer_review_required": True,
            }
            for item in missing_inputs
        )
    if stale_dirty_status["stale"] or stale_dirty_status["dirty"]:
        section_blockers.append(
            {
                "area": section_id,
                "field": "stale_dirty_evidence",
                "reason": "Section evidence is stale or dirty relative to current canonical state.",
                "message": "Section evidence is stale or dirty relative to current canonical state.",
                "severity": "blocker",
                "dirty_references": deepcopy(stale_dirty_status.get("dirty_references")),
                "engineer_review_required": True,
            }
        )
    review_reasons: List[str] = []
    if definition.get("review_when_present") and present:
        review_reasons.append("engineer_review_required")
    if section_id == "assumptions" and assumptions:
        review_reasons.append("assumptions_require_engineer_acceptance")
    if section_id == "qa_blockers" and present and not section_blockers:
        review_reasons.append("qa_record_requires_engineer_review")
    if section_id == "engineer_review_checklist" and present:
        checklist = safe_list(safe_dict(meta.get("engineer_review_package")).get("approval_checklist"))
        manual_required = [
            safe_str(item.get("item_id"))
            for item in checklist
            if safe_str(safe_dict(item).get("status")) == "manual_required"
        ]
        if manual_required:
            review_reasons.extend(manual_required[:6])
    if section_blockers:
        review_reasons.append("blockers_require_engineer_resolution")
    if missing_inputs:
        review_reasons.append("missing_inputs_require_engineer_review")
    if stale_dirty_status["stale"] or stale_dirty_status["dirty"]:
        review_reasons.append("stale_dirty_evidence_requires_rerun_or_engineer_review")

    if section_blockers:
        generated_missing_only = bool(section_blockers) and all(
            safe_str(item.get("severity")) == "missing_input" for item in section_blockers
        )
        status = "missing" if not present and generated_missing_only else "blocked"
    elif present and review_reasons:
        status = "review_required"
    elif present:
        status = "included"
    else:
        status = "missing"
    confidence = _support_confidence(
        present=present,
        section_blockers=section_blockers,
        missing_inputs=missing_inputs,
        stale_dirty=stale_dirty_status,
        linked_artifacts=linked_artifacts,
    )

    return {
        "section_id": section_id,
        "label": safe_str(definition.get("label")),
        "status": status,
        "included": status in {"included", "review_required", "blocked"} and present,
        "engineer_review_required": True,
        "evidence_keys": list(evidence_keys),
        "evidence_present": evidence_present,
        "source_evidence_references": source_evidence_references,
        "canonical_ids": canonical_ids,
        "missing_inputs": missing_inputs,
        "blocker_fields": sorted(blocker_fields),
        "blockers": section_blockers,
        "review_reasons": list(dict.fromkeys(review_reasons)),
        "review_required_reason": "; ".join(dict.fromkeys(review_reasons)) if review_reasons else "",
        "linked_export_report_artifacts": linked_artifacts,
        "confidence": confidence,
        "stale_dirty_status": stale_dirty_status,
        "no_construction_approval": True,
    }


def build_construction_document_support_package(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Build a review-only construction-document-support package scope matrix."""

    meta = safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else safe_dict(plan_or_meta)
    blockers = _support_package_blockers(meta)
    assumptions = _support_package_assumptions(meta)
    sections = [
        _support_section_record(plan_or_meta, meta, definition, blockers, assumptions)
        for definition in CONSTRUCTION_DOCUMENT_SUPPORT_SECTIONS
    ]
    section_status_matrix = {section["section_id"]: section["status"] for section in sections}
    statuses = set(section_status_matrix.values())
    package_status = "blocked" if "blocked" in statuses else "review_required" if "review_required" in statuses else "incomplete" if "missing" in statuses else "included"
    construction_manifest = safe_dict(meta.get("construction_package_manifest"))
    engineer_review_package = safe_dict(meta.get("engineer_review_package") or meta.get("engineer_review_package_v1"))
    return {
        "version": "construction_document_support_package_v1",
        "source": "construction_document_support_package_v1",
        "package_type": "construction_document_support",
        "package_status": package_status,
        "engineer_review_required": True,
        "required_engineer_review": True,
        "engineer_approval_required": True,
        "responsible_party": "licensed_engineer_or_user",
        "construction_approval": False,
        "construction_release_allowed": False,
        "construction_export_allowed": False,
        "civora_approval_authority": False,
        "civora_engineer_of_record": False,
        "civora_signoff_allowed": False,
        "simulated_seal_allowed": False,
        "simulated_signature_allowed": False,
        "submittal_by_civora_allowed": False,
        "sections": sections,
        "section_status_matrix": section_status_matrix,
        "status_counts": {status: sum(1 for item in sections if item["status"] == status) for status in ("included", "missing", "blocked", "review_required")},
        "assumptions": deepcopy(assumptions),
        "qa_blockers": deepcopy(blockers),
        "blockers": deepcopy(blockers),
        "construction_package_manifest_summary": {
            "present": bool(construction_manifest),
            "source": safe_str(construction_manifest.get("source")),
            "release_state": safe_str(construction_manifest.get("release_state")),
            "construction_release_allowed": False,
            "construction_release_blocked": True,
        },
        "engineer_review_checklist_summary": {
            "present": bool(engineer_review_package),
            "review_status": safe_str(engineer_review_package.get("review_status")),
            "checklist_count": len(safe_list(engineer_review_package.get("approval_checklist"))),
            "external_engineer_approval_required": True,
        },
        "truth_label": SUPPORT_PACKAGE_RESPONSIBILITY_LABEL,
        "no_construction_approval": True,
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
        construction_package_record(meta),
        artifact_status,
    )
    package_blockers = _construction_package_blockers(plan_or_meta, meta) if readiness.get("ready") is True else []
    blockers = _unique_blockers([*blockers, *package_blockers])
    release_guard = _construction_release_guard(meta)
    if release_guard["construction_release_blocked"]:
        blockers = _unique_blockers([*blockers, _construction_release_guard_blocker(release_guard)])
    sections = [
        _section_status(section=section, blockers=blockers, warnings=warnings, evidence=evidence)
        for section in CONSTRUCTION_PACKAGE_SECTIONS
    ]
    blocked_sections = [section["section_id"] for section in sections if section["status"] == "blocked"]
    review_sections = [section["section_id"] for section in sections if section["status"] == "needs_review"]
    ready = (
        bool(readiness.get("ready"))
        and not blocked_sections
        and not review_sections
        and not release_guard["construction_release_blocked"]
    )
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
        "construction_release_guard": release_guard,
        "product_mode": release_guard["product_mode"],
        "review_only": release_guard["review_only"],
        "sections": sections,
        "blocked_sections": blocked_sections,
        "review_sections": review_sections,
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warnings": warnings,
        "warning_details": readiness_issue_explanations(warnings),
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


__all__ = [
    "CONSTRUCTION_PACKAGE_SECTIONS",
    "CONSTRUCTION_DOCUMENT_SUPPORT_SECTIONS",
    "REQUIRED_CONSTRUCTION_ARTIFACTS",
    "build_construction_document_support_package",
    "build_construction_package_manifest",
    "build_review_package_manifest",
]
