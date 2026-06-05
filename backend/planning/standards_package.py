from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from .common import readiness_issue_explanations, safe_dict, safe_list, safe_str
from .standards_discovery import validate_standards_acceptance_for_production

STANDARDS_STALE_DAYS = 365


def _blocker(field: str, reason: str, *, next_action: str = "", severity: str = "blocker") -> Dict[str, Any]:
    return {
        "area": "standards",
        "field": field,
        "reason": reason,
        "message": reason,
        "why_needed": reason,
        "suggested_next_action": next_action or "Resolve this standards package issue and rerun standards validation.",
        "severity": severity,
    }


def _source_urls(*values: Iterable[Any]) -> List[str]:
    urls: List[str] = []
    for value in values:
        for item in safe_list(value):
            url = safe_str(item)
            if url and url not in urls:
                urls.append(url)
    return urls


def _jurisdiction(meta: Dict[str, Any]) -> Dict[str, Any]:
    jurisdiction = safe_dict(meta.get("jurisdiction_standards"))
    packet = safe_dict(meta.get("standards_review_packet"))
    discovery = safe_dict(packet.get("discovery"))
    discovered = safe_dict(discovery.get("jurisdiction"))
    return {
        "city": safe_str(jurisdiction.get("city") or discovered.get("city")),
        "county": safe_str(jurisdiction.get("county") or discovered.get("county")),
        "state": safe_str(jurisdiction.get("state") or discovered.get("state")),
        "utility_provider": safe_str(jurisdiction.get("utility_provider") or discovered.get("utility_provider")),
        "source": safe_str(jurisdiction.get("source") or "standards_package"),
        "source_urls": _source_urls(jurisdiction.get("source_urls")),
        "production_usable": bool(jurisdiction.get("production_usable")),
    }


def _accepted_rules(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    acceptance = safe_dict(meta.get("standards_acceptance"))
    design = safe_dict(meta.get("design_standards"))
    package = safe_dict(meta.get("standards_package"))
    return [
        safe_dict(item)
        for item in safe_list(
            acceptance.get("accepted_rules")
            or design.get("rules")
            or package.get("accepted_rules")
        )
        if safe_dict(item)
    ]


def _parse_date(value: Any) -> Optional[date]:
    text = safe_str(value)
    if not text or text == "static":
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _retrieved_date(meta: Dict[str, Any], accepted_rules: List[Dict[str, Any]]) -> str:
    acceptance = safe_dict(meta.get("standards_acceptance"))
    design = safe_dict(meta.get("design_standards"))
    package = safe_dict(meta.get("standards_package"))
    for value in (
        acceptance.get("retrieved_date"),
        design.get("retrieved_date"),
        package.get("retrieved_date"),
        safe_dict(meta.get("standards_review_packet")).get("retrieved_date"),
    ):
        text = safe_str(value)
        if text:
            return text
    for rule in accepted_rules:
        text = safe_str(rule.get("retrieved_date"))
        if text:
            return text
    return ""


def _staleness(retrieved_date: str, *, today: Optional[date] = None) -> Dict[str, Any]:
    parsed = _parse_date(retrieved_date)
    if parsed is None:
        return {
            "retrieved_date": safe_str(retrieved_date),
            "age_days": None,
            "stale": False,
            "evaluated": False,
        }
    current = today or date.today()
    age_days = max(0, (current - parsed).days)
    return {
        "retrieved_date": retrieved_date,
        "age_days": age_days,
        "stale": age_days > STANDARDS_STALE_DAYS,
        "stale_after_days": STANDARDS_STALE_DAYS,
        "evaluated": True,
    }


def _overrides(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        safe_dict(item)
        for item in safe_list(meta.get("standards_overrides") or safe_dict(meta.get("standards_acceptance")).get("overrides"))
        if safe_dict(item)
    ]


def _validation(meta: Dict[str, Any], accepted_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    acceptance = safe_dict(meta.get("standards_acceptance"))
    design = safe_dict(meta.get("design_standards"))
    validation = safe_dict(
        acceptance.get("production_validation")
        or design.get("production_validation")
        or safe_dict(meta.get("standards_package")).get("production_validation")
    )
    if validation:
        return deepcopy(validation)
    source_urls = _source_urls(
        acceptance.get("source_urls"),
        design.get("source_urls"),
        [rule.get("source_url") for rule in accepted_rules],
    )
    return validate_standards_acceptance_for_production(
        {
            "accepted_rules": accepted_rules,
            "source_urls": source_urls,
        }
    )


def build_standards_package(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if isinstance(plan_or_meta, dict) and "meta" in plan_or_meta else safe_dict(plan_or_meta)
    acceptance = safe_dict(meta.get("standards_acceptance"))
    design = safe_dict(meta.get("design_standards"))
    company = safe_dict(meta.get("company_standards"))
    jurisdiction = _jurisdiction(meta)
    accepted_rules = _accepted_rules(meta)
    validation = _validation(meta, accepted_rules)
    retrieved_date = _retrieved_date(meta, accepted_rules)
    staleness = _staleness(retrieved_date)
    overrides = _overrides(meta)
    source_urls = _source_urls(
        acceptance.get("source_urls"),
        design.get("source_urls"),
        jurisdiction.get("source_urls"),
        [rule.get("source_url") for rule in accepted_rules],
    )
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not accepted_rules:
        blockers.append(
            _blocker(
                "accepted_rules",
                "Standards package needs user-accepted jurisdiction/company rules.",
                next_action="Select standards candidates, accept applicable rules, and store the acceptance record.",
            )
        )
    for item in safe_list(validation.get("blockers")):
        rec = safe_dict(item)
        blockers.append(
            _blocker(
                safe_str(rec.get("field"), "production_validation"),
                safe_str(rec.get("reason"), "Standards production validation failed."),
                next_action="Fix standards acceptance metadata and rerun validation.",
            )
        )
    if not any(source_url.startswith("https://") for source_url in source_urls):
        blockers.append(
            _blocker(
                "official_sources",
                "Standards package needs at least one accepted official HTTPS source; search links and internal baselines are not code compliance.",
                next_action="Attach the official city/county/DOT/utility standards source URL or uploaded official source file.",
            )
        )
    if not any(safe_str(jurisdiction.get(key)) for key in ("city", "county", "state", "utility_provider")):
        blockers.append(
            _blocker(
                "jurisdiction",
                "Standards package needs selected jurisdiction/provider context.",
                next_action="Select city, county, state, DOT, or utility-provider context before standards QA.",
            )
        )
    if not company:
        blockers.append(
            _blocker(
                "company_standards",
                "Standards package needs company CAD/design/detail standards for production-style deliverables.",
                next_action="Attach company standards or keep deliverables in review-only mode.",
            )
        )
    elif company.get("production_usable") is not True:
        blockers.append(
            _blocker(
                "company_standards",
                "Company standards are attached but not marked production-usable.",
                next_action="Approve company CAD/layer/sheet/detail standards or record why they remain review-only.",
            )
        )
    if bool(acceptance.get("needs_source_review")):
        warnings.append(
            _blocker(
                "source_review",
                "Accepted standards still need source review.",
                next_action="Review the official source and clear needs_source_review before permit-style QA.",
                severity="warning",
            )
        )
    if staleness.get("stale"):
        warnings.append(
            _blocker(
                "standards_stale",
                "Accepted standards source evidence is stale and needs confirmation before permit-style QA.",
                next_action="Re-check the official source, refresh retrieved_date, or keep standards in review-only mode.",
                severity="warning",
            )
        )
    incomplete_overrides: List[Dict[str, Any]] = []
    for override in overrides:
        missing = [
            key
            for key in ("rule_id", "reason", "accepted_by", "accepted_date")
            if not safe_str(override.get(key))
        ]
        if missing:
            incomplete_overrides.append({"rule_id": safe_str(override.get("rule_id")), "missing": missing})
    if incomplete_overrides:
        blockers.append(
            _blocker(
                "override_history",
                "Standards overrides need traceable rule, reason, user, and date history.",
                next_action="Record override rule_id, reason, accepted_by, and accepted_date before relying on modified standards.",
            )
        )

    status = "blocked" if blockers else "needs_review" if warnings else "ready"
    return {
        "version": "standards_package_v1",
        "status": status,
        "production_usable": status == "ready" and bool(validation.get("production_usable")) and company.get("production_usable") is True,
        "accepted_for_qa": bool(accepted_rules),
        "selected_jurisdiction": jurisdiction,
        "source_urls": source_urls,
        "official_source_count": validation.get("official_source_count", 0),
        "accepted_rule_count": len(accepted_rules),
        "accepted_rules": deepcopy(accepted_rules),
        "override_count": len(overrides),
        "overrides": deepcopy(overrides),
        "override_history_complete": bool(overrides) and not incomplete_overrides if overrides else True,
        "reviewer_notes": safe_str(meta.get("standards_reviewer_notes") or safe_dict(meta.get("standards_acceptance")).get("reviewer_notes")),
        "retrieved_date": safe_str(retrieved_date),
        "staleness": staleness,
        "production_validation": deepcopy(validation),
        "company_standards": deepcopy(company),
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warnings": warnings,
        "truth_label": "Standards packages are accepted rule evidence, not automatic code compliance; official source and engineer review remain required.",
    }


__all__ = ["build_standards_package"]
