from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from .common import readiness_issue_explanations, safe_dict, safe_list, safe_str
from .standards_discovery import validate_standards_acceptance_for_production

STANDARDS_STALE_DAYS = 365

REQUIRED_STANDARDS_RULE_TOPICS = (
    {
        "rule_key": "jurisdiction_selection",
        "label": "Selected jurisdiction/provider",
        "matches": ("jurisdiction",),
    },
    {
        "rule_key": "official_source_selection",
        "label": "Selected official standards source",
        "matches": ("official source", "source url", "manual", "standards"),
    },
    {
        "rule_key": "company_cad_standards",
        "label": "Company CAD/sheet/detail standards",
        "matches": ("company", "cad", "sheet", "detail"),
    },
)


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


def _is_official_source_url(url: str) -> bool:
    lowered = safe_str(url).lower()
    return (
        lowered.startswith("https://")
        and "google.com/search" not in lowered
        and "bing.com/search" not in lowered
        and not lowered.startswith("internal://")
    )


def _jurisdiction(meta: Dict[str, Any]) -> Dict[str, Any]:
    jurisdiction = safe_dict(meta.get("jurisdiction_standards"))
    packet = safe_dict(meta.get("standards_review_packet"))
    discovery = safe_dict(packet.get("discovery"))
    discovered = safe_dict(discovery.get("jurisdiction"))
    explicit = bool(jurisdiction)
    source = safe_str(jurisdiction.get("source") or ("jurisdiction_standards" if explicit else "standards_review_packet_inferred"))
    return {
        "agency": safe_str(jurisdiction.get("agency") or discovered.get("agency")),
        "city": safe_str(jurisdiction.get("city") or discovered.get("city")),
        "county": safe_str(jurisdiction.get("county") or discovered.get("county")),
        "state": safe_str(jurisdiction.get("state") or discovered.get("state")),
        "utility_provider": safe_str(jurisdiction.get("utility_provider") or discovered.get("utility_provider")),
        "source": source,
        "source_urls": _source_urls(jurisdiction.get("source_urls")),
        "explicitly_selected": explicit,
        "selection_status": "selected" if explicit else "inferred_from_review_packet",
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


def _source_registry(meta: Dict[str, Any]) -> Dict[str, Any]:
    packet = safe_dict(meta.get("standards_review_packet"))
    discovery = safe_dict(packet.get("discovery"))
    acceptance = safe_dict(meta.get("standards_acceptance"))
    design = safe_dict(meta.get("design_standards"))
    registry = safe_dict(
        meta.get("standards_source_registry")
        or packet.get("source_registry")
        or discovery.get("source_registry")
        or acceptance.get("source_registry")
        or design.get("source_registry")
    )
    return deepcopy(registry)


def _source_registry_staleness(registry: Dict[str, Any]) -> Dict[str, Any]:
    sources = [safe_dict(item) for item in safe_list(registry.get("sources")) if safe_dict(item)]
    stale_sources = [
        {
            "source_id": safe_str(source.get("source_id")),
            "source_url": safe_str(source.get("source_url")),
            "retrieved_at": safe_str(source.get("retrieved_at")),
            "age_days": source.get("age_days"),
        }
        for source in sources
        if bool(source.get("stale"))
    ]
    unevaluated_sources = [
        {
            "source_id": safe_str(source.get("source_id")),
            "source_url": safe_str(source.get("source_url")),
            "retrieved_at": safe_str(source.get("retrieved_at")),
        }
        for source in sources
        if source.get("age_days") is None and safe_str(source.get("retrieved_at")) not in {"", "static"}
    ]
    return {
        "source_count": len(sources),
        "stale_source_count": len(stale_sources),
        "stale_sources": stale_sources,
        "unevaluated_source_count": len(unevaluated_sources),
        "unevaluated_sources": unevaluated_sources,
    }


def _candidate_rule_report(meta: Dict[str, Any]) -> Dict[str, Any]:
    packet = safe_dict(meta.get("standards_review_packet"))
    report = safe_dict(
        meta.get("standards_candidate_rule_report")
        or packet.get("candidate_rule_report")
        or safe_dict(meta.get("standards_package")).get("candidate_rule_report")
    )
    return deepcopy(report)


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


def _missing_input(field: str, reason: str, next_action: str) -> Dict[str, Any]:
    return {
        "field": field,
        "reason": reason,
        "next_action": next_action,
    }


def _source_selection(
    meta: Dict[str, Any],
    *,
    source_urls: List[str],
    official_source_urls: List[str],
    accepted_rule_count: int,
) -> Dict[str, Any]:
    explicit = safe_dict(
        meta.get("selected_standards_source")
        or meta.get("standards_source_selection")
        or safe_dict(meta.get("standards_acceptance")).get("selected_source")
    )
    explicit_url = safe_str(explicit.get("url") or explicit.get("source_url") or explicit.get("official_source_url"))
    selected_urls = _source_urls([explicit_url], explicit.get("source_urls"), official_source_urls)
    has_explicit_record = bool(explicit)
    has_official_selection = bool(selected_urls and any(_is_official_source_url(url) for url in selected_urls))
    explicit_selection = has_explicit_record or (accepted_rule_count > 0 and bool(official_source_urls))
    return {
        "explicitly_selected": explicit_selection and has_official_selection,
        "selection_status": "selected" if explicit_selection and has_official_selection else "missing",
        "source_id": safe_str(explicit.get("source_id") or explicit.get("id") or ("accepted_official_source" if official_source_urls else "")),
        "name": safe_str(explicit.get("name") or explicit.get("label")),
        "source_urls": selected_urls or source_urls,
        "official_source_urls": official_source_urls,
        "source_record": deepcopy(explicit),
        "truth_label": "A standards source is selected only when it traces to an accepted official source; search and baseline sources remain inferred.",
    }


def _missing_rule_inputs(
    *,
    accepted_rules: List[Dict[str, Any]],
    inferred_rule_ids: List[str],
    jurisdiction: Dict[str, Any],
    source_selection: Dict[str, Any],
    company: Dict[str, Any],
) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    for topic in REQUIRED_STANDARDS_RULE_TOPICS:
        rule_key = safe_str(topic.get("rule_key"))
        label = safe_str(topic.get("label"))
        if rule_key == "jurisdiction_selection":
            if jurisdiction.get("explicitly_selected") is True and jurisdiction.get("production_usable") is True:
                continue
            missing.append(
                {
                    "rule_key": rule_key,
                    "label": label,
                    "reason": "Jurisdiction/provider selection is missing, inferred, or not production-usable.",
                }
            )
            continue
        if rule_key == "official_source_selection":
            if source_selection.get("explicitly_selected") is True:
                continue
            missing.append(
                {
                    "rule_key": rule_key,
                    "label": label,
                    "reason": "No explicit accepted official standards source is selected.",
                }
            )
            continue
        if rule_key == "company_cad_standards":
            if company and company.get("production_usable") is True:
                continue
            missing.append(
                {
                    "rule_key": rule_key,
                    "label": label,
                    "reason": "Company CAD/sheet/detail standards are missing or not production-usable.",
                }
            )
            continue
    if not accepted_rules:
        missing.append(
            {
                "rule_key": "accepted_rules",
                "label": "Accepted official standards rules",
                "reason": "No accepted official standards rules are visible.",
            }
        )
    return missing


def _reviewer_comments(
    *,
    blockers: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    missing_inputs: List[Dict[str, Any]],
    missing_rules: List[Dict[str, Any]],
    inferred_rule_ids: List[str],
) -> List[Dict[str, Any]]:
    comments: List[Dict[str, Any]] = []
    for item in missing_inputs:
        rec = safe_dict(item)
        comments.append(
            {
                "severity": "blocker",
                "field": safe_str(rec.get("field"), "standards_input"),
                "comment": safe_str(rec.get("reason"), "A required standards input is missing."),
                "next_action": safe_str(rec.get("next_action"), "Provide this standards input and rerun the standards gate."),
            }
        )
    for item in missing_rules:
        rec = safe_dict(item)
        comments.append(
            {
                "severity": "blocker",
                "field": safe_str(rec.get("rule_key"), "missing_rule"),
                "comment": safe_str(rec.get("reason"), "A required standards rule input is missing."),
                "next_action": f"Accept an official-source rule for {safe_str(rec.get('label'), 'this standards topic')} or document it as not applicable.",
            }
        )
    if inferred_rule_ids:
        comments.append(
            {
                "severity": "blocker",
                "field": "inferred_rules",
                "comment": "The following rule IDs are inferred/search/baseline and cannot be treated as accepted compliance standards: "
                + ", ".join(inferred_rule_ids),
                "next_action": "Replace inferred/search/baseline rules with accepted rules from selected official sources.",
            }
        )
    for collection, severity in ((blockers, "blocker"), (warnings, "warning")):
        for item in collection:
            rec = safe_dict(item)
            comments.append(
                {
                    "severity": safe_str(rec.get("severity"), severity),
                    "field": safe_str(rec.get("field"), "standards_gate"),
                    "comment": safe_str(rec.get("reason") or rec.get("message"), "Standards gate issue remains."),
                    "next_action": safe_str(rec.get("suggested_next_action"), "Resolve this standards gate issue and rerun validation."),
                }
            )
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for comment in comments:
        key = (comment["severity"], comment["field"], comment["comment"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(comment)
    return deduped


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
    source_registry = _source_registry(meta)
    source_registry_staleness = _source_registry_staleness(source_registry)
    candidate_rule_report = _candidate_rule_report(meta)
    overrides = _overrides(meta)
    source_urls = _source_urls(
        acceptance.get("source_urls"),
        design.get("source_urls"),
        jurisdiction.get("source_urls"),
        [rule.get("source_url") for rule in accepted_rules],
    )
    official_source_urls = deepcopy(validation.get("official_source_urls") or [url for url in source_urls if _is_official_source_url(url)])
    inferred_rule_ids = deepcopy(validation.get("inferred_rule_ids") or [])
    source_selection = _source_selection(
        meta,
        source_urls=source_urls,
        official_source_urls=official_source_urls,
        accepted_rule_count=len(accepted_rules),
    )
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    missing_inputs: List[Dict[str, Any]] = []

    if not accepted_rules:
        missing_inputs.append(
            _missing_input(
                "accepted_rules",
                "No user-accepted standards rules are recorded.",
                "Accept or edit standards rules from official sources before standards QA.",
            )
        )
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
    if not official_source_urls:
        missing_inputs.append(
            _missing_input(
                "official_sources",
                "No accepted official HTTPS standards source is attached.",
                "Attach the official city/county/DOT/utility source URL or uploaded official source file.",
            )
        )
        blockers.append(
            _blocker(
                "official_sources",
                "Standards package needs at least one accepted official HTTPS source; search links and internal baselines are not code compliance.",
                next_action="Attach the official city/county/DOT/utility standards source URL or uploaded official source file.",
            )
        )
    if source_selection.get("explicitly_selected") is not True:
        blockers.append(
            _blocker(
                "standards_source_selection",
                "Selected standards source is missing or not tied to an accepted official source.",
                next_action="Select the official standards source used for accepted rules before production QA.",
            )
        )
    jurisdiction_identity_present = any(safe_str(jurisdiction.get(key)) for key in ("agency", "city", "county", "state", "utility_provider"))
    if not jurisdiction_identity_present:
        missing_inputs.append(
            _missing_input(
                "jurisdiction",
                "No city/county/state/DOT/utility jurisdiction context is selected.",
                "Select the governing jurisdiction/provider before standards QA.",
            )
        )
        blockers.append(
            _blocker(
                "jurisdiction",
                "Standards package needs selected jurisdiction/provider context.",
                next_action="Select city, county, state, DOT, or utility-provider context before standards QA.",
            )
        )
    elif jurisdiction.get("explicitly_selected") is not True:
        blockers.append(
            _blocker(
                "jurisdiction_selection",
                "Jurisdiction context is inferred from the review packet and has not been explicitly selected for the project.",
                next_action="Persist jurisdiction_standards with selected city/county/state/utility provider and production_usable status.",
            )
        )
    elif jurisdiction.get("production_usable") is not True:
        blockers.append(
            _blocker(
                "jurisdiction_selection",
                "Selected jurisdiction standards are not marked production-usable.",
                next_action="Accept official jurisdiction rules and mark jurisdiction_standards.production_usable true, or keep output review-only.",
            )
        )
    if not company:
        missing_inputs.append(
            _missing_input(
                "company_standards",
                "No company CAD/design/detail standards are attached.",
                "Attach company standards or keep deliverables in review-only mode.",
            )
        )
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
    if source_registry_staleness.get("stale_source_count"):
        warnings.append(
            _blocker(
                "standards_source_registry_stale",
                "One or more discovered standards source records are stale and need refresh before selection.",
                next_action="Refresh the candidate source registry, then review and accept applicable official-source rules.",
                severity="warning",
            )
        )
    if candidate_rule_report.get("candidate_count"):
        duplicate_count = int(candidate_rule_report.get("duplicate_count") or 0)
        stale_count = len(safe_list(candidate_rule_report.get("stale_rule_ids")))
        reason = f"{candidate_rule_report.get('candidate_count')} candidate standards rules need user acceptance before they can be used for production QA."
        if duplicate_count:
            reason += f" {duplicate_count} candidate rule IDs are flagged as duplicates."
        if stale_count:
            reason += f" {stale_count} candidate rule IDs come from stale source records."
        warnings.append(
            _blocker(
                "candidate_standards",
                reason,
                next_action="Review candidate rules, resolve duplicates/stale sources, then explicitly accept applicable official-source rules.",
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
    missing_rules = _missing_rule_inputs(
        accepted_rules=accepted_rules,
        inferred_rule_ids=inferred_rule_ids,
        jurisdiction=jurisdiction,
        source_selection=source_selection,
        company=company,
    )
    if missing_rules and status == "ready":
        status = "needs_review"
    production_usable = status == "ready" and bool(validation.get("production_usable")) and company.get("production_usable") is True
    construction_blockers = blockers + ([] if production_usable else [
        _blocker(
            "construction_release",
            "Construction release is blocked until standards are selected, accepted, official-source traceable, current, and company-approved.",
            next_action="Resolve standards blockers or issue the package as review-only.",
        )
    ])
    qa_status = "ready" if production_usable else "blocked" if blockers else "needs_review"
    reviewer_comments = _reviewer_comments(
        blockers=blockers,
        warnings=warnings,
        missing_inputs=missing_inputs,
        missing_rules=missing_rules,
        inferred_rule_ids=inferred_rule_ids,
    )
    acceptance_report = {
        "version": "standards_acceptance_report_v1",
        "status": qa_status,
        "qa_status": qa_status,
        "selected_jurisdiction": jurisdiction,
        "selected_standards_source": source_selection,
        "rules": {
            "accepted": deepcopy(accepted_rules),
            "candidates": deepcopy(candidate_rule_report),
            "accepted_rule_ids": deepcopy(validation.get("accepted_rule_ids") or [safe_str(rule.get("rule_id")) for rule in accepted_rules if safe_str(rule.get("rule_id"))]),
            "inferred_rule_ids": inferred_rule_ids,
            "missing_rules": missing_rules,
        },
        "reviewer_comments": reviewer_comments,
        "construction_release_blocked": not production_usable,
        "review_only": not production_usable,
        "compliance_statement": "This report records standards acceptance evidence only. It is not a code-compliance certification and does not treat inferred/search/baseline standards as accepted.",
    }
    return {
        "version": "standards_package_v1",
        "status": status,
        "production_usable": production_usable,
        "review_only": not production_usable,
        "construction_release_blocked": not production_usable,
        "construction_release_blockers": construction_blockers,
        "requirements_gate": {
            "status": "construction_ready" if production_usable else "construction_blocked",
            "qa_status": qa_status,
            "review_allowed": bool(accepted_rules),
            "construction_allowed": production_usable,
            "missing_inputs": deepcopy(missing_inputs),
            "accepted_rule_ids": deepcopy(validation.get("accepted_rule_ids") or [safe_str(rule.get("rule_id")) for rule in accepted_rules if safe_str(rule.get("rule_id"))]),
            "inferred_rule_ids": inferred_rule_ids,
            "missing_rules": deepcopy(missing_rules),
            "official_source_urls": official_source_urls,
            "reviewer_comments": deepcopy(reviewer_comments),
            "truth_label": "Review may use accepted rules, but construction is blocked unless every accepted rule is official-source traceable and jurisdiction/company standards are explicit.",
        },
        "standards_acceptance_report": acceptance_report,
        "qa": {
            "status": qa_status,
            "ready": qa_status == "ready",
            "blocked": qa_status == "blocked",
            "needs_review": qa_status == "needs_review",
            "reviewer_comments": deepcopy(reviewer_comments),
        },
        "accepted_for_qa": bool(accepted_rules),
        "selected_jurisdiction": jurisdiction,
        "selected_standards_source": source_selection,
        "source_urls": source_urls,
        "standards_source_registry": source_registry,
        "source_registry_staleness": source_registry_staleness,
        "candidate_rule_report": candidate_rule_report,
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
