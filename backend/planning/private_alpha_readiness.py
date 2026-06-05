from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

from core.config import PRODUCT_MODE, REVIEW_ONLY_PRODUCT_MODES

from .common import readiness_issue_explanations, safe_dict, safe_list, safe_str


def _normalize_product_mode(value: Any) -> str:
    text = safe_str(value or PRODUCT_MODE or "private_alpha").lower().replace("-", "_")
    aliases = {
        "alpha": "private_alpha",
        "review": "private_alpha",
        "review_only": "private_alpha",
        "beta": "public_beta",
    }
    return aliases.get(text, text or "private_alpha")


def _guard_from_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    package = safe_dict(meta.get("construction_package_manifest"))
    guard = safe_dict(package.get("construction_release_guard"))
    if guard:
        return deepcopy(guard)
    product_mode = _normalize_product_mode(meta.get("product_mode") or meta.get("deployment_mode"))
    review_only = product_mode in REVIEW_ONLY_PRODUCT_MODES
    construction_release_enabled = product_mode == "production" and not review_only
    return {
        "product_mode": product_mode,
        "review_only": review_only,
        "construction_release_enabled": construction_release_enabled,
        "construction_release_blocked": review_only or not construction_release_enabled,
        "guard_reason": (
            "Private alpha/review-only mode blocks construction release."
            if review_only
            else "Construction release requires production mode plus package and professional review gates."
            if not construction_release_enabled
            else ""
        ),
        "truth_label": (
            "Review packages may be generated in private alpha, but construction release remains blocked."
            if review_only or not construction_release_enabled
            else "Production mode still requires every construction package gate before release."
        ),
    }


def _blocker(area: str, field: str, message: str, *, severity: str = "blocker", next_action: str = "") -> Dict[str, Any]:
    return {
        "area": area,
        "field": field,
        "message": message,
        "why_needed": message,
        "suggested_next_action": next_action or "Attach the missing evidence, rerun the affected backend checks, and regenerate readiness.",
        "severity": severity,
    }


def _status_from_section(ready: bool, blockers: List[Dict[str, Any]], warnings: List[Dict[str, Any]] | None = None) -> str:
    if blockers:
        return "blocked"
    if ready and not (warnings or []):
        return "ready"
    return "needs_review"


def _engine_section(meta: Dict[str, Any]) -> Dict[str, Any]:
    engine = safe_dict(meta.get("engine_readiness"))
    alpha = safe_dict(safe_dict(engine.get("summary")).get("alpha_readiness"))
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    if not alpha:
        blockers.append(
            _blocker(
                "engines",
                "engine_readiness",
                "Private alpha readiness needs the engine readiness rollup.",
                next_action="Run engine readiness evaluation and attach engine_readiness.summary.alpha_readiness.",
            )
        )
    elif safe_str(alpha.get("status")) == "blocked":
        blockers.append(
            _blocker(
                "engines",
                "alpha_engine_rollup",
                "One or more required engines are blocked for private alpha.",
                next_action="Resolve blocked engine rows before claiming full-system alpha readiness.",
            )
        )
    elif safe_str(alpha.get("status")) != "ready":
        warnings.append(
            _blocker(
                "engines",
                "alpha_engine_review",
                "One or more engines still need review for private alpha.",
                severity="warning",
                next_action="Review alpha engine warnings and close unproven engine evidence gaps.",
            )
        )
    return {
        "status": _status_from_section(bool(alpha) and safe_str(alpha.get("status")) == "ready", blockers, warnings),
        "alpha_readiness": deepcopy(alpha),
        "blockers": blockers,
        "warnings": warnings,
    }


def _existing_conditions_section(meta: Dict[str, Any]) -> Dict[str, Any]:
    existing = safe_dict(meta.get("existing_conditions_summary"))
    package = safe_dict(meta.get("existing_conditions_package"))
    package_status = safe_str(package.get("status")).lower()
    ready = bool(existing.get("production_ready")) and package_status == "ready" and bool(package.get("accepted"))
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    if not package:
        blockers.append(
            _blocker(
                "existing_conditions",
                "existing_conditions_package",
                "Private alpha needs an existing-conditions package, not only loose survey/GIS metadata.",
                next_action="Build the existing-conditions package from imported survey, terrain, GIS, CRS, and acceptance evidence.",
            )
        )
    elif package_status == "blocked":
        blockers.extend(safe_list(package.get("blockers")))
        if not blockers:
            blockers.append(
                _blocker(
                    "existing_conditions",
                    "existing_conditions_package",
                    "Existing-conditions package is blocked.",
                    next_action="Resolve existing-conditions package blockers before full-system alpha readiness.",
                )
            )
    elif package_status == "needs_review":
        warnings.append(
            _blocker(
                "existing_conditions",
                "existing_conditions_package_acceptance",
                "Existing-conditions package exists but still needs acceptance/review.",
                severity="warning",
                next_action="Accept the package for private-alpha review use or keep downstream systems in needs-review.",
            )
        )
    if package and not bool(existing.get("production_ready")):
        blockers.append(
            _blocker(
                "existing_conditions",
                "existing_conditions_summary",
                "Private alpha needs a real existing-conditions package state: survey/control, terrain, GIS constraints, and coordinate system must be validated or explicitly missing.",
                next_action="Import or validate survey/control, terrain source, GIS constraints, and coordinate system before full-system alpha readiness.",
            )
        )
    return {
        "status": _status_from_section(ready, blockers, warnings),
        "production_ready": ready,
        "package_status": package_status or "missing",
        "package": deepcopy(package),
        "summary": deepcopy(existing),
        "blockers": blockers,
        "warnings": warnings,
    }


def _standards_section(meta: Dict[str, Any]) -> Dict[str, Any]:
    package = safe_dict(meta.get("standards_package"))
    package_status = safe_str(package.get("status")).lower()
    acceptance = safe_dict(meta.get("standards_acceptance"))
    validation = safe_dict(acceptance.get("production_validation"))
    civil = safe_dict(meta.get("civil_design_readiness"))
    standards_system = safe_dict(safe_dict(civil.get("systems")).get("standards"))
    metrics = safe_dict(standards_system.get("metrics"))
    state = safe_str(
        validation.get("status")
        or validation.get("readiness")
        or metrics.get("acceptance_state")
        or acceptance.get("status")
    ).lower()
    ready = package_status == "ready" and bool(package.get("production_usable"))
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    if not package:
        blockers.append(
            _blocker(
                "standards",
                "standards_package",
                "Private alpha needs a standards package, not only inferred or scattered standards metadata.",
                next_action="Build standards_package from selected jurisdiction, official source evidence, accepted rules, overrides, and company standards.",
            )
        )
    elif package_status == "blocked":
        blockers.extend(safe_list(package.get("blockers")))
        if not blockers:
            blockers.append(
                _blocker(
                    "standards",
                    "standards_package",
                    "Standards package is blocked.",
                    next_action="Resolve standards package blockers before alpha readiness.",
                )
            )
    elif package_status == "needs_review":
        warnings.append(
            _blocker(
                "standards",
                "standards_package_review",
                "Standards package exists but still needs review.",
                severity="warning",
                next_action="Review standards source evidence and overrides before alpha readiness.",
            )
        )
    if package and not ready:
        blockers.append(
            _blocker(
                "standards",
                "standards_package",
                "Private alpha needs explicit jurisdiction/company standards acceptance; Civora must not imply fake code compliance.",
                next_action="Select official or user-accepted standards, record assumptions, and rerun standards validation.",
            )
        )
    return {
        "status": _status_from_section(ready, blockers, warnings),
        "acceptance_state": state or "missing",
        "package_status": package_status or "missing",
        "package": deepcopy(package),
        "production_validation": deepcopy(validation),
        "blockers": blockers,
        "warnings": warnings,
    }


def _export_section(meta: Dict[str, Any]) -> Dict[str, Any]:
    audit = safe_dict(meta.get("export_audit"))
    ready = bool(audit.get("production_export_ready") or audit.get("ready")) and not bool(audit.get("export_blocked"))
    blockers: List[Dict[str, Any]] = []
    if not audit:
        blockers.append(
            _blocker(
                "deliverables",
                "export_audit",
                "Private alpha needs an export audit proving deliverables match canonical state.",
                next_action="Generate export metadata and attach export_audit before alpha readiness.",
            )
        )
    elif not ready:
        blockers.append(
            _blocker(
                "deliverables",
                "export_audit",
                "Export audit is blocked, stale, or not production-export ready.",
                next_action="Resolve export audit blockers and regenerate deliverables from the current canonical model.",
            )
        )
    return {
        "status": _status_from_section(ready, blockers),
        "production_export_ready": ready,
        "export_blocked": bool(audit.get("export_blocked")),
        "audit": deepcopy(audit),
        "blockers": blockers,
    }


def _cost_section(meta: Dict[str, Any]) -> Dict[str, Any]:
    package = safe_dict(meta.get("cost_package_status"))
    status = safe_str(package.get("status")).lower()
    ready = status == "ready" and bool(package.get("production_usable"))
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    if not package:
        blockers.append(
            _blocker(
                "cost",
                "cost_package_status",
                "Private alpha needs a cost package status tying quantities, unit prices, and cost output together.",
                next_action="Build cost_package_status from the current quantity model and cost estimate.",
            )
        )
    elif status == "blocked":
        blockers.extend(safe_list(package.get("blockers")))
        if not blockers:
            blockers.append(
                _blocker(
                    "cost",
                    "cost_package_status",
                    "Cost package is blocked.",
                    next_action="Resolve cost package blockers and rerun cost validation.",
                )
            )
    elif status == "needs_review":
        warnings.append(
            _blocker(
                "cost",
                "cost_package_review",
                "Cost package exists but remains review-only because pricing, coverage, or traceability is incomplete.",
                severity="warning",
                next_action="Attach an approved complete unit-price book or keep costs labeled review-only.",
            )
        )
    if package and not ready:
        blockers.append(
            _blocker(
                "cost",
                "cost_package_production_usable",
                "Private alpha cost claims need approved pricing coverage and matching cost/quantity/price hashes.",
                next_action="Resolve cost package blockers before showing cost output as alpha-ready.",
            )
        )
    return {
        "status": _status_from_section(ready, blockers, warnings),
        "package_status": status or "missing",
        "production_usable": ready,
        "package": deepcopy(package),
        "blockers": blockers,
        "warnings": warnings,
    }


def _golden_section(meta: Dict[str, Any]) -> Dict[str, Any]:
    report = safe_dict(meta.get("golden_scenario_report") or meta.get("golden_scenarios_report") or meta.get("golden_scenarios"))
    status = safe_str(report.get("status") or report.get("readiness") or ("passed" if report.get("success") is True else ""))
    ready = status.lower() in {"passed", "ready", "success"} or bool(report.get("passed"))
    blockers: List[Dict[str, Any]] = []
    if not ready:
        blockers.append(
            _blocker(
                "golden_scenarios",
                "golden_scenario_report",
                "Private alpha needs a current golden scenario report covering the full backend system.",
                next_action="Run backend golden scenarios and attach the report with pass/fail and blocked systems.",
            )
        )
    return {
        "status": _status_from_section(ready, blockers),
        "report": deepcopy(report),
        "blockers": blockers,
    }


def _monitoring_section(meta: Dict[str, Any]) -> Dict[str, Any]:
    monitoring = safe_dict(
        meta.get("alpha_monitoring_report")
        or meta.get("runtime_monitoring")
        or meta.get("monitoring")
    )
    status = safe_str(monitoring.get("status") or monitoring.get("readiness")).lower()
    ready = status in {"healthy", "ready", "ok", "pass", "passed"} or monitoring.get("success") is True
    blockers: List[Dict[str, Any]] = []
    if not ready:
        blockers.append(
            _blocker(
                "monitoring",
                "alpha_monitoring_report",
                "Private alpha needs runtime monitoring evidence for memory, runtime, crashes, and queue timeout risk.",
                next_action="Attach runtime monitoring snapshots and alpha deployment health status.",
            )
        )
    return {
        "status": _status_from_section(ready, blockers),
        "monitoring": deepcopy(monitoring),
        "blockers": blockers,
    }


def _construction_guard_section(meta: Dict[str, Any]) -> Dict[str, Any]:
    guard = _guard_from_meta(meta)
    product_mode = _normalize_product_mode(guard.get("product_mode"))
    review_only = bool(guard.get("review_only"))
    construction_release_blocked = bool(guard.get("construction_release_blocked"))
    blockers: List[Dict[str, Any]] = []
    if product_mode in REVIEW_ONLY_PRODUCT_MODES and not review_only:
        blockers.append(
            _blocker(
                "release_guard",
                "review_only_guard",
                "Review-only product mode must explicitly label alpha outputs as review-only.",
                next_action="Restore the alpha review-only construction guard before generating alpha outputs.",
            )
        )
    if product_mode in REVIEW_ONLY_PRODUCT_MODES and not construction_release_blocked:
        blockers.append(
            _blocker(
                "release_guard",
                "construction_release_guard",
                "Private alpha must block construction release even when review artifacts are allowed.",
                next_action="Keep construction_release_blocked true until production release mode and all professional gates pass.",
            )
        )
    return {
        "status": _status_from_section(not blockers, blockers),
        "guard": guard,
        "product_mode": product_mode,
        "review_only": review_only,
        "construction_release_blocked": construction_release_blocked,
        "construction_release_allowed": bool(guard.get("construction_release_enabled")) and not construction_release_blocked,
        "blockers": blockers,
    }


def _unique_blockers(blockers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in blockers:
        rec = safe_dict(item)
        key = (safe_str(rec.get("area")), safe_str(rec.get("field")), safe_str(rec.get("message") or rec.get("why_needed")))
        if key in seen:
            continue
        seen.add(key)
        out.append(deepcopy(rec))
    return out


def _next_actions(blockers: Iterable[Dict[str, Any]]) -> List[str]:
    actions: List[str] = []
    for blocker in blockers:
        action = safe_str(safe_dict(blocker).get("suggested_next_action"))
        if action and action not in actions:
            actions.append(action)
    return actions[:12]


def build_private_alpha_readiness(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if isinstance(plan_or_meta, dict) and "meta" in plan_or_meta else safe_dict(plan_or_meta)
    sections = {
        "construction_release_guard": _construction_guard_section(meta),
        "engines": _engine_section(meta),
        "existing_conditions": _existing_conditions_section(meta),
        "standards": _standards_section(meta),
        "cost": _cost_section(meta),
        "exports": _export_section(meta),
        "golden_scenarios": _golden_section(meta),
        "monitoring": _monitoring_section(meta),
    }
    blockers = _unique_blockers(
        blocker
        for section in sections.values()
        for blocker in safe_list(section.get("blockers"))
    )
    warnings = _unique_blockers(
        warning
        for section in sections.values()
        for warning in safe_list(section.get("warnings"))
    )
    if blockers:
        status = "blocked"
    elif warnings or any(safe_str(section.get("status")) == "needs_review" for section in sections.values()):
        status = "needs_review"
    else:
        status = "ready"
    guard = sections["construction_release_guard"]
    return {
        "version": "private_alpha_readiness_v1",
        "status": status,
        "full_system_private_alpha_ready": status == "ready",
        "product_mode": safe_str(guard.get("product_mode"), _normalize_product_mode(meta.get("product_mode"))),
        "review_only": bool(guard.get("review_only")),
        "construction_release_blocked": bool(guard.get("construction_release_blocked")),
        "construction_release_allowed": bool(guard.get("construction_release_allowed")),
        "construction_ready": False,
        "launch_recommendation": (
            "private_alpha_review_ready"
            if status == "ready"
            else "blocked_before_private_alpha"
            if status == "blocked"
            else "private_alpha_needs_review"
        ),
        "sections": sections,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warning_count": len(warnings),
        "warnings": warnings,
        "next_actions": _next_actions(blockers or warnings),
        "truth_label": (
            "Private alpha can represent the full Civora system only as a review-only workflow. "
            "Construction release remains blocked until production mode, real inputs, accepted standards, "
            "current deliverables, monitoring, golden scenarios, and licensed review all pass."
        ),
    }


__all__ = ["build_private_alpha_readiness"]
