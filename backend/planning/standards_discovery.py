from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
from html.parser import HTMLParser
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus, urlparse

import requests

from .common import readiness_issue_explanations, safe_dict, safe_list, safe_str


@dataclass(frozen=True)
class StandardsSource:
    source_id: str
    name: str
    scope: str
    url: str
    status: str
    notes: str


@dataclass(frozen=True)
class StandardsSourceRegistryEntry:
    source_id: str
    jurisdiction: Dict[str, str]
    agency: str
    discipline: str
    source_url: str
    document_title: str
    version_or_effective_date: str
    retrieved_at: str
    source_type: str
    confidence: str
    candidate_rule_ids: Tuple[str, ...]
    acceptance_status: str
    stale_after_days: int
    age_days: Optional[int]
    stale: bool


@dataclass(frozen=True)
class StandardsRuleCandidate:
    rule_id: str
    discipline: str
    topic: str
    candidate_value: str
    source_id: str
    source_url: str
    source_section: str
    retrieved_date: str
    retrieved_at: str
    confidence: str
    status: str
    acceptance_status: str
    source_type: str
    needs_human_confirmation: bool


@dataclass(frozen=True)
class NumericThreshold:
    value: float
    unit: str
    comparator: str
    raw_text: str


BASELINE_US_CONCEPT_RULES: Tuple[StandardsRuleCandidate, ...] = (
    StandardsRuleCandidate(
        rule_id="us_baseline_ada_cross_slope",
        discipline="grading",
        topic="ADA cross slope",
        candidate_value="2 percent maximum cross slope for accessible pedestrian route concept check.",
        source_id="civora_us_baseline",
        source_url="internal://civora/us-baseline-concept-standards",
        source_section="ADA concept baseline",
        retrieved_date="static",
        retrieved_at="static",
        confidence="baseline",
        status="candidate",
        acceptance_status="candidate",
        source_type="internal_baseline",
        needs_human_confirmation=True,
    ),
    StandardsRuleCandidate(
        rule_id="us_baseline_utility_cover",
        discipline="utilities",
        topic="Minimum utility cover",
        candidate_value="3.0 ft minimum cover concept check unless jurisdiction/provider standard overrides.",
        source_id="civora_us_baseline",
        source_url="internal://civora/us-baseline-concept-standards",
        source_section="Utility concept baseline",
        retrieved_date="static",
        retrieved_at="static",
        confidence="baseline",
        status="candidate",
        acceptance_status="candidate",
        source_type="internal_baseline",
        needs_human_confirmation=True,
    ),
    StandardsRuleCandidate(
        rule_id="us_baseline_pipe_capacity",
        discipline="storm",
        topic="Pipe capacity ratio",
        candidate_value="Flag gravity pipe segments above 0.95 capacity ratio for review.",
        source_id="civora_us_baseline",
        source_url="internal://civora/us-baseline-concept-standards",
        source_section="Hydraulic concept baseline",
        retrieved_date="static",
        retrieved_at="static",
        confidence="baseline",
        status="candidate",
        acceptance_status="candidate",
        source_type="internal_baseline",
        needs_human_confirmation=True,
    ),
)

STANDARDS_REGISTRY_STALE_DAYS = 365
STANDARDS_LIVE_SOURCE_REFRESH_DAYS = 180
ALLOWED_LIVE_SOURCE_TYPES = {
    "official_city",
    "official_county",
    "official_state_dot",
    "official_utility",
    "official_federal",
    "company_uploaded",
}
BLOCKED_LIVE_SOURCE_TYPES = {
    "blogs",
    "forums",
    "ai_summaries",
    "unofficial_mirrors",
    "unknown_pdf_without_source_owner",
}
LIVE_SOURCE_CONFIDENCE_ORDER = {
    "blocked": 0,
    "low": 1,
    "official_candidate": 2,
    "trusted_candidate": 3,
}


def _today() -> str:
    return date.today().isoformat()


def standards_live_source_policy() -> Dict[str, Any]:
    return {
        "version": "standards_live_source_policy_v1",
        "allowed_source_types": sorted(ALLOWED_LIVE_SOURCE_TYPES),
        "blocked_source_types": sorted(BLOCKED_LIVE_SOURCE_TYPES),
        "default_refresh_after_days": STANDARDS_LIVE_SOURCE_REFRESH_DAYS,
        "candidate_only": True,
        "acceptance_status": "unaccepted",
        "network_fetch_default": "disabled_until_explicit_single_source_request",
        "truth_label": "Live standards sources are discovery candidates only. Fetching or extracting a rule does not imply code compliance, construction approval, or accepted standards.",
    }


def trusted_standards_source_allowlist(entries: Optional[Iterable[Dict[str, Any]]] = None) -> Dict[str, Any]:
    normalized_entries = []
    for entry in entries or []:
        rec = safe_dict(entry)
        normalized_entries.append(
            {
                "jurisdiction": deepcopy(safe_dict(rec.get("jurisdiction"))),
                "agency": safe_str(rec.get("agency")),
                "allowed_domains": sorted({_normalize_domain(item) for item in safe_list(rec.get("allowed_domains")) if _normalize_domain(item)}),
                "allowed_source_types": sorted({_normalize_live_source_type(item) for item in safe_list(rec.get("allowed_source_types")) if _normalize_live_source_type(item)}),
                "disciplines": sorted({safe_str(item).lower() for item in safe_list(rec.get("disciplines")) if safe_str(item)}),
                "effective_from": safe_str(rec.get("effective_from")),
                "effective_to": safe_str(rec.get("effective_to")),
                "configured_by": safe_str(rec.get("configured_by")),
                "configured_at": safe_str(rec.get("configured_at"), _today()),
                "confidence_cap": _cap_confidence(safe_str(rec.get("confidence_cap"), "official_candidate")),
            }
        )
    return {
        "version": "trusted_standards_source_allowlist_v1",
        "entries": normalized_entries,
        "entry_count": len(normalized_entries),
        "candidate_only": True,
        "acceptance_status": "unaccepted",
        "truth_label": "Trusted source allowlist configuration can raise candidate-source confidence only; it is not standards acceptance, code compliance, or construction approval.",
    }


def _parse_date(value: Any) -> Optional[date]:
    text = safe_str(value)
    if not text or text == "static":
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _staleness_fields(value: Any, *, stale_after_days: int = STANDARDS_REGISTRY_STALE_DAYS) -> Dict[str, Any]:
    parsed = _parse_date(value)
    if parsed is None:
        return {
            "stale_after_days": stale_after_days,
            "age_days": None,
            "stale": False,
            "staleness_evaluated": False,
        }
    age_days = max(0, (date.today() - parsed).days)
    return {
        "stale_after_days": stale_after_days,
        "age_days": age_days,
        "stale": age_days > stale_after_days,
        "staleness_evaluated": True,
    }


def _domain_from_url(url: str) -> str:
    parsed = urlparse(safe_str(url))
    return safe_str(parsed.netloc).lower()


def _normalize_domain(value: Any) -> str:
    text = safe_str(value).lower().strip()
    if not text:
        return ""
    if "://" in text:
        return _domain_from_url(text)
    return text.strip("/")


def _domain_matches(domain: str, allowed_domain: str) -> bool:
    normalized_domain = _normalize_domain(domain)
    allowed = _normalize_domain(allowed_domain)
    return bool(normalized_domain and allowed and (normalized_domain == allowed or normalized_domain.endswith(f".{allowed}")))


def _cap_confidence(value: str) -> str:
    normalized = safe_str(value).lower()
    return normalized if normalized in LIVE_SOURCE_CONFIDENCE_ORDER else "official_candidate"


def _min_confidence(left: str, right: str) -> str:
    left_norm = _cap_confidence(left)
    right_norm = _cap_confidence(right)
    if LIVE_SOURCE_CONFIDENCE_ORDER[left_norm] <= LIVE_SOURCE_CONFIDENCE_ORDER[right_norm]:
        return left_norm
    return right_norm


def _jurisdiction_matches(source_jurisdiction: Dict[str, Any], allowlist_jurisdiction: Dict[str, Any]) -> bool:
    expected = {safe_str(key).lower(): safe_str(value).lower() for key, value in allowlist_jurisdiction.items() if safe_str(value)}
    if not expected:
        return True
    actual = {safe_str(key).lower(): safe_str(value).lower() for key, value in source_jurisdiction.items() if safe_str(value)}
    return all(actual.get(key) == value for key, value in expected.items())


def _match_trusted_allowlist_entry(
    *,
    domain: str,
    jurisdiction: Optional[Dict[str, Any]],
    agency: str,
    source_type: str,
    allowlist_entries: Optional[Iterable[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    normalized_type = _normalize_live_source_type(source_type)
    normalized_agency = safe_str(agency).lower()
    source_jurisdiction = safe_dict(jurisdiction)
    for entry in trusted_standards_source_allowlist(allowlist_entries).get("entries", []):
        allowed_domains = safe_list(entry.get("allowed_domains"))
        allowed_types = set(safe_list(entry.get("allowed_source_types")))
        entry_agency = safe_str(entry.get("agency")).lower()
        if allowed_domains and not any(_domain_matches(domain, item) for item in allowed_domains):
            continue
        if allowed_types and normalized_type not in allowed_types:
            continue
        if entry_agency and normalized_agency != entry_agency:
            continue
        if not _jurisdiction_matches(source_jurisdiction, safe_dict(entry.get("jurisdiction"))):
            continue
        return safe_dict(entry)
    return None


def _next_refresh_due(retrieved_at: str, refresh_after_days: int) -> str:
    parsed = _parse_date(retrieved_at)
    if parsed is None:
        return ""
    return date.fromordinal(parsed.toordinal() + refresh_after_days).isoformat()


def _normalize_live_source_type(source_type: Any) -> str:
    return safe_str(source_type).lower().replace("-", "_").replace(" ", "_")


def classify_live_standards_source(
    *,
    source_url: str,
    source_type: str = "",
    jurisdiction: Optional[Dict[str, Any]] = None,
    agency: str = "",
    source_owner: str = "",
    uploaded_by: str = "",
    allowlist_entries: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalized_type = _normalize_live_source_type(source_type)
    url = safe_str(source_url)
    domain = _domain_from_url(url)
    parsed_path = safe_str(urlparse(url).path).lower()
    reasons: List[str] = []
    allowed = normalized_type in ALLOWED_LIVE_SOURCE_TYPES
    blocked = normalized_type in BLOCKED_LIVE_SOURCE_TYPES
    if normalized_type == "company_uploaded" and not safe_str(source_owner or uploaded_by):
        blocked = True
        reasons.append("Company-uploaded standards require uploaded_by or source_owner metadata.")
    if parsed_path.endswith(".pdf") and not safe_str(agency or source_owner) and not allowed:
        normalized_type = "unknown_pdf_without_source_owner"
        blocked = True
        reasons.append("PDF source has no traceable owner/agency metadata.")
    if not url.startswith("https://") and normalized_type != "company_uploaded":
        blocked = True
        reasons.append("Live standards sources must use HTTPS unless they are company-uploaded files.")
    if not normalized_type:
        reasons.append("Source type is missing and must be classified before live research.")
    if normalized_type in {"blogs", "forums", "ai_summaries", "unofficial_mirrors"}:
        reasons.append("Source type is not an official standards authority.")
    allowlist_match = None
    if allowed and not blocked:
        allowlist_match = _match_trusted_allowlist_entry(
            domain=domain,
            jurisdiction=jurisdiction,
            agency=agency or source_owner,
            source_type=normalized_type,
            allowlist_entries=allowlist_entries,
        )
        if allowlist_match:
            confidence = _min_confidence("trusted_candidate", safe_str(allowlist_match.get("confidence_cap"), "official_candidate"))
        else:
            confidence = "low"
            reasons.append("Source is allowed by type but does not match trusted jurisdiction/agency/domain allowlist configuration.")
    else:
        confidence = "blocked" if blocked else "low"
    return {
        "version": "standards_live_source_policy_v1",
        "allowlist_version": "trusted_standards_source_allowlist_v1",
        "source_url": url,
        "domain": domain,
        "source_type": normalized_type or "unknown",
        "allowed": allowed and not blocked,
        "blocked": blocked or not allowed,
        "confidence": confidence,
        "allowlist_matched": bool(allowlist_match),
        "allowlist_entry": allowlist_match or {},
        "review_only": confidence in {"low", "blocked"},
        "candidate_only": True,
        "acceptance_status": "unaccepted",
        "reasons": reasons,
        "truth_label": "Source classification is not standards acceptance and does not imply code compliance or construction approval.",
    }


def build_live_source_fetch_record(
    *,
    source_url: str,
    resolved_url: str = "",
    jurisdiction: Optional[Dict[str, Any]] = None,
    agency: str = "",
    source_type: str = "",
    document_title: str = "",
    effective_date: str = "",
    version: str = "",
    fetch_status: str = "not_fetched",
    confidence: str = "",
    content: str = "",
    retrieved_at: str = "",
    source_owner: str = "",
    uploaded_by: str = "",
    allowlist_entries: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    url = safe_str(source_url)
    resolved = safe_str(resolved_url) or url
    retrieved = safe_str(retrieved_at, _today())
    classification = classify_live_standards_source(
        source_url=resolved,
        source_type=source_type,
        jurisdiction=jurisdiction,
        agency=agency,
        source_owner=source_owner,
        uploaded_by=uploaded_by,
        allowlist_entries=allowlist_entries,
    )
    refresh_after_days = STANDARDS_LIVE_SOURCE_REFRESH_DAYS
    staleness = _staleness_fields(retrieved, stale_after_days=refresh_after_days)
    policy_confidence = safe_str(confidence) or safe_str(classification.get("confidence"))
    content_text = safe_str(content)
    needs_review = bool(classification.get("blocked")) or bool(staleness.get("stale")) or policy_confidence in {"", "low", "blocked"}
    return {
        "version": "standards_live_source_fetch_record_v1",
        "policy_version": "standards_live_source_policy_v1",
        "allowlist_version": "trusted_standards_source_allowlist_v1",
        "source_url": url,
        "resolved_url": resolved,
        "domain": _domain_from_url(resolved),
        "jurisdiction": deepcopy(safe_dict(jurisdiction)),
        "agency": safe_str(agency or source_owner),
        "source_type": safe_str(classification.get("source_type")),
        "retrieved_at": retrieved,
        "content_hash": hashlib.sha256(content_text.encode("utf-8")).hexdigest() if content_text else "",
        "document_title": safe_str(document_title),
        "effective_date": safe_str(effective_date),
        "version_or_effective_date": safe_str(version or effective_date),
        "fetch_status": safe_str(fetch_status),
        "confidence": policy_confidence,
        "review_only": bool(classification.get("review_only")),
        "candidate_only": True,
        "acceptance_status": "unaccepted",
        "refresh_after_days": refresh_after_days,
        "next_refresh_due": _next_refresh_due(retrieved, refresh_after_days),
        "staleness": staleness,
        "needs_review": needs_review,
        "policy_decision": classification,
        "truth_label": "Fetched source records are candidate evidence only and do not imply code compliance or construction approval.",
    }


def fetch_live_standards_source_candidate(
    *,
    source_url: str,
    source_id: str = "live_source",
    source_type: str = "",
    jurisdiction: Optional[Dict[str, Any]] = None,
    agency: str = "",
    document_title: str = "",
    effective_date: str = "",
    version: str = "",
    session: Any = requests,
    allow_network_fetch: bool = False,
    source_owner: str = "",
    uploaded_by: str = "",
    allowlist_entries: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    policy = standards_live_source_policy()
    allowlist = trusted_standards_source_allowlist(allowlist_entries)
    classification = classify_live_standards_source(
        source_url=source_url,
        source_type=source_type,
        jurisdiction=jurisdiction,
        agency=agency,
        source_owner=source_owner,
        uploaded_by=uploaded_by,
        allowlist_entries=allowlist_entries,
    )
    body = ""
    resolved_url = safe_str(source_url)
    fetch_status = "blocked_by_policy" if classification.get("blocked") else "deferred_by_policy"
    warnings: List[str] = []
    if classification.get("blocked"):
        warnings.extend(safe_list(classification.get("reasons")) or ["Source is not allowed by live-source policy."])
    elif not allow_network_fetch:
        warnings.append("Network fetch deferred; controlled live fetching requires explicit single-source enablement.")
    else:
        try:
            response = session.get(source_url, timeout=20)
            response.raise_for_status()
            body = safe_str(getattr(response, "text", ""))
            resolved_url = safe_str(getattr(response, "url", "")) or safe_str(source_url)
            fetch_status = "fetched"
        except Exception as exc:
            fetch_status = "fetch_failed"
            warnings.append(safe_str(exc))
    fetch_record = build_live_source_fetch_record(
        source_url=source_url,
        resolved_url=resolved_url,
        jurisdiction=jurisdiction,
        agency=agency,
        source_type=source_type,
        document_title=document_title or source_id,
        effective_date=effective_date,
        version=version,
        fetch_status=fetch_status,
        confidence=safe_str(classification.get("confidence")),
        content=body,
        source_owner=source_owner,
        uploaded_by=uploaded_by,
        allowlist_entries=allowlist_entries,
    )
    candidates = extract_rule_candidates_from_text(body, source_id=source_id, source_url=resolved_url) if body else []
    for candidate in candidates:
        candidate["source_type"] = safe_str(classification.get("source_type"))
        candidate["confidence"] = "live_source_candidate"
        candidate["acceptance_status"] = "candidate"
        candidate["status"] = "candidate"
        candidate["requires_user_acceptance"] = True
        candidate["source_document_title"] = safe_str(document_title or source_id)
        candidate["source_version_or_effective_date"] = safe_str(version or effective_date)
    source_registry = build_standards_source_registry(
        jurisdiction=jurisdiction,
        sources=[
            {
                "source_id": source_id,
                "agency": agency,
                "discipline": "general",
                "source_url": resolved_url,
                "document_title": document_title or source_id,
                "version_or_effective_date": version or effective_date,
                "retrieved_at": fetch_record["retrieved_at"],
                "source_type": safe_str(classification.get("source_type")),
                "confidence": safe_str(classification.get("confidence")),
                "acceptance_status": "unaccepted",
                "source_owner": safe_str(source_owner),
                "uploaded_by": safe_str(uploaded_by),
                "allowlist_matched": bool(classification.get("allowlist_matched")),
            }
        ],
        candidate_rules=candidates,
    )
    candidate_rule_report = build_candidate_rule_report(candidates, source_registry=source_registry)
    return {
        "success": fetch_status == "fetched",
        "policy": policy,
        "trusted_allowlist": allowlist,
        "source_classification": classification,
        "fetch_record": fetch_record,
        "source_registry": source_registry,
        "candidate_rule_report": candidate_rule_report,
        "candidate_rules": candidate_rule_report["candidate_rules"],
        "candidate_count": len(candidate_rule_report["candidate_rules"]),
        "warnings": warnings,
        "truth_label": "Controlled live-source discovery returns candidate evidence only; engineer/user acceptance is required before production standards gates can use any rule.",
    }


def _controlled_lookup_blocked_response(
    *,
    source_url: str,
    source_id: str,
    source_type: str,
    jurisdiction: Optional[Dict[str, Any]],
    agency: str,
    discipline: str,
    fetch_status: str,
    reason: str,
    classification: Optional[Dict[str, Any]] = None,
    allowlist: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fetch_record = build_live_source_fetch_record(
        source_url=source_url,
        jurisdiction=jurisdiction,
        agency=agency,
        source_type=source_type,
        document_title=source_id,
        fetch_status=fetch_status,
        confidence=safe_str(safe_dict(classification).get("confidence")),
    )
    if classification:
        fetch_record["policy_decision"] = safe_dict(classification)
    return {
        "success": False,
        "workflow_version": "controlled_single_source_lookup_v1",
        "source_id": safe_str(source_id),
        "discipline": safe_str(discipline),
        "source_classification": safe_dict(classification),
        "trusted_allowlist": safe_dict(allowlist),
        "fetch_record": fetch_record,
        "source_registry": build_standards_source_registry(jurisdiction=jurisdiction, sources=[], candidate_rules=[]),
        "candidate_rule_report": build_candidate_rule_report([]),
        "candidate_rules": [],
        "candidate_count": 0,
        "warnings": [safe_str(reason)],
        "blockers": [{"field": fetch_status, "reason": safe_str(reason)}],
        "production_usable": False,
        "construction_release_allowed": False,
        "truth_label": "Single-source lookup is disabled unless explicitly operator-authorized and remains candidate evidence only.",
    }


def controlled_single_source_lookup(
    *,
    source_url: str,
    source_id: str = "single_source_lookup",
    jurisdiction: Optional[Dict[str, Any]] = None,
    agency: str = "",
    source_type: str = "",
    discipline: str = "",
    operator_authorized: bool = False,
    document_title: str = "",
    effective_date: str = "",
    version: str = "",
    session: Any = requests,
    source_owner: str = "",
    uploaded_by: str = "",
    allowlist_entries: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    url = safe_str(source_url)
    source_id_text = safe_str(source_id, "single_source_lookup")
    jurisdiction_rec = safe_dict(jurisdiction)
    agency_text = safe_str(agency)
    source_type_text = safe_str(source_type)
    discipline_text = safe_str(discipline)
    allowlist = trusted_standards_source_allowlist(allowlist_entries)
    if not operator_authorized:
        return _controlled_lookup_blocked_response(
            source_url=url,
            source_id=source_id_text,
            source_type=source_type_text,
            jurisdiction=jurisdiction_rec,
            agency=agency_text,
            discipline=discipline_text,
            fetch_status="blocked_by_operator_authorization",
            reason="operator_authorized must be true for controlled single-source lookup.",
            allowlist=allowlist,
        )
    missing = []
    for field, value in (
        ("source_url", url),
        ("jurisdiction", jurisdiction_rec),
        ("agency", agency_text),
        ("source_type", source_type_text),
        ("discipline", discipline_text),
    ):
        if not value:
            missing.append(field)
    if missing:
        return _controlled_lookup_blocked_response(
            source_url=url,
            source_id=source_id_text,
            source_type=source_type_text,
            jurisdiction=jurisdiction_rec,
            agency=agency_text,
            discipline=discipline_text,
            fetch_status="blocked_by_missing_required_metadata",
            reason=f"Controlled single-source lookup requires: {', '.join(missing)}.",
            allowlist=allowlist,
        )
    classification = classify_live_standards_source(
        source_url=url,
        source_type=source_type_text,
        jurisdiction=jurisdiction_rec,
        agency=agency_text,
        source_owner=source_owner,
        uploaded_by=uploaded_by,
        allowlist_entries=allowlist_entries,
    )
    if classification.get("blocked"):
        reason = "; ".join(safe_list(classification.get("reasons"))) or "Source is blocked by live-source policy."
        return _controlled_lookup_blocked_response(
            source_url=url,
            source_id=source_id_text,
            source_type=source_type_text,
            jurisdiction=jurisdiction_rec,
            agency=agency_text,
            discipline=discipline_text,
            fetch_status="blocked_by_policy",
            reason=reason,
            classification=classification,
            allowlist=allowlist,
        )
    if not classification.get("allowlist_matched"):
        return _controlled_lookup_blocked_response(
            source_url=url,
            source_id=source_id_text,
            source_type=source_type_text,
            jurisdiction=jurisdiction_rec,
            agency=agency_text,
            discipline=discipline_text,
            fetch_status="blocked_by_allowlist",
            reason="Source does not match trusted jurisdiction/agency/domain allowlist.",
            classification=classification,
            allowlist=allowlist,
        )
    body = ""
    resolved_url = url
    headers: Dict[str, Any] = {}
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        body = safe_str(getattr(response, "text", ""))
        resolved_url = safe_str(getattr(response, "url", "")) or url
        headers = safe_dict(getattr(response, "headers", {}))
    except Exception as exc:
        return _controlled_lookup_blocked_response(
            source_url=url,
            source_id=source_id_text,
            source_type=source_type_text,
            jurisdiction=jurisdiction_rec,
            agency=agency_text,
            discipline=discipline_text,
            fetch_status="fetch_failed",
            reason=safe_str(exc, "Network fetch failed."),
            classification=classification,
            allowlist=allowlist,
        )
    content_type = safe_str(headers.get("content-type")).lower()
    is_pdf = "pdf" in content_type or safe_str(urlparse(resolved_url).path).lower().endswith(".pdf")
    is_html_or_text = "html" in content_type or content_type.startswith("text/") or "<html" in body.lower()
    if not is_pdf and not is_html_or_text:
        return _controlled_lookup_blocked_response(
            source_url=url,
            source_id=source_id_text,
            source_type=source_type_text,
            jurisdiction=jurisdiction_rec,
            agency=agency_text,
            discipline=discipline_text,
            fetch_status="unsupported_content_type",
            reason="Controlled single-source lookup supports HTML, text, or PDF sources only.",
            classification=classification,
            allowlist=allowlist,
        )
    extractable_text = "" if is_pdf else extract_text_from_html(body) if "<html" in body.lower() else body
    candidates = extract_rule_candidates_from_text(extractable_text, source_id=source_id_text, source_url=resolved_url) if extractable_text else []
    for candidate in candidates:
        candidate["source_type"] = safe_str(classification.get("source_type"))
        candidate["confidence"] = "live_source_candidate"
        candidate["acceptance_status"] = "candidate"
        candidate["status"] = "candidate"
        candidate["requires_user_acceptance"] = True
        candidate["source_document_title"] = safe_str(document_title or source_id_text)
        candidate["source_version_or_effective_date"] = safe_str(version or effective_date)
        candidate["lookup_discipline"] = discipline_text
        candidate["needs_review"] = True
    fetch_record = build_live_source_fetch_record(
        source_url=url,
        resolved_url=resolved_url,
        jurisdiction=jurisdiction_rec,
        agency=agency_text,
        source_type=source_type_text,
        document_title=document_title or source_id_text,
        effective_date=effective_date,
        version=version,
        fetch_status="fetched_pdf_candidate" if is_pdf else "fetched",
        confidence=safe_str(classification.get("confidence")),
        content=body,
        source_owner=source_owner,
        uploaded_by=uploaded_by,
        allowlist_entries=allowlist_entries,
    )
    source_registry = build_standards_source_registry(
        jurisdiction=jurisdiction_rec,
        sources=[
            {
                "source_id": source_id_text,
                "agency": agency_text,
                "discipline": discipline_text,
                "source_url": resolved_url,
                "document_title": document_title or source_id_text,
                "version_or_effective_date": version or effective_date,
                "retrieved_at": fetch_record["retrieved_at"],
                "source_type": safe_str(classification.get("source_type")),
                "confidence": safe_str(classification.get("confidence")),
                "acceptance_status": "unaccepted",
                "allowlist_matched": True,
            }
        ],
        candidate_rules=candidates,
    )
    candidate_rule_report = build_candidate_rule_report(candidates, source_registry=source_registry)
    warnings = ["PDF extraction is deferred; source is recorded as candidate evidence only."] if is_pdf else []
    return {
        "success": True,
        "workflow_version": "controlled_single_source_lookup_v1",
        "source_id": source_id_text,
        "discipline": discipline_text,
        "source_classification": classification,
        "trusted_allowlist": allowlist,
        "fetch_record": fetch_record,
        "source_registry": source_registry,
        "candidate_rule_report": candidate_rule_report,
        "candidate_rules": candidate_rule_report["candidate_rules"],
        "candidate_count": len(candidate_rule_report["candidate_rules"]),
        "warnings": warnings,
        "blockers": [],
        "production_usable": False,
        "construction_release_allowed": False,
        "truth_label": "Controlled single-source lookup returns candidate evidence only; engineer/user acceptance and all broader gates are still required.",
    }


def _candidate_acceptance_status(raw: Any = "") -> str:
    status = safe_str(raw).lower()
    return status if status in {"candidate", "unaccepted"} else "candidate"


def _registry_source_type(source: Dict[str, Any]) -> str:
    explicit = safe_str(source.get("source_type")).lower()
    if explicit:
        return explicit
    source_url = safe_str(source.get("source_url") or source.get("url")).lower()
    source_id = safe_str(source.get("source_id")).lower()
    if source_url.startswith("internal://") or source_id == "civora_us_baseline":
        return "internal_baseline"
    if "google.com/search" in source_url or "bing.com/search" in source_url or source_id.endswith("_search"):
        return "search_candidate"
    return "official_candidate"


def _registry_confidence(source: Dict[str, Any], source_type: str) -> str:
    explicit = safe_str(source.get("confidence")).lower()
    if explicit:
        return explicit
    if source_type == "internal_baseline":
        return "baseline"
    if source_type == "search_candidate":
        return "search"
    return "candidate"


def _source_registry_by_id(source_registry: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        safe_str(source.get("source_id")): safe_dict(source)
        for source in safe_list(safe_dict(source_registry).get("sources"))
        if safe_str(safe_dict(source).get("source_id"))
    }


def _numeric_thresholds_from_text(text: str) -> List[Dict[str, Any]]:
    thresholds: List[Dict[str, Any]] = []
    haystack = safe_str(text)
    pattern = re.compile(
        r"(?i)(?P<prefix>.{0,45}?)(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|percent|feet|foot|ft|'|inches|inch|in|hours|hour|hrs|hr|gpm|gallons per minute|psi|fps|ft/s|feet per second)"
    )
    for match in pattern.finditer(haystack):
        prefix = " ".join(match.group("prefix").lower().split())
        comparator = "stated"
        if any(token in prefix for token in ("maximum", "max", "not exceed", "shall not exceed", "no greater", "up to")):
            comparator = "max"
        elif any(token in prefix for token in ("minimum", "min", "at least", "not less", "greater than")):
            comparator = "min"
        raw_text = safe_str(match.group(0)).strip()
        thresholds.append(
            asdict(
                NumericThreshold(
                    value=float(match.group("value")),
                    unit=safe_str(match.group("unit")).lower(),
                    comparator=comparator,
                    raw_text=raw_text,
                )
            )
        )
    return thresholds


def _duplicate_signature(rule: Dict[str, Any]) -> Tuple[Any, ...]:
    thresholds = []
    for threshold in safe_list(rule.get("numeric_thresholds")):
        rec = safe_dict(threshold)
        thresholds.append(
            (
                rec.get("value"),
                safe_str(rec.get("unit")).lower(),
                safe_str(rec.get("comparator")).lower(),
            )
        )
    text = re.sub(r"\s+", " ", safe_str(rule.get("extracted_text_or_summary") or rule.get("candidate_value")).lower()).strip()
    return (
        safe_str(rule.get("discipline")).lower(),
        safe_str(rule.get("topic")).lower(),
        tuple(sorted(thresholds)),
        text[:180],
    )


def _normalize_candidate_rule(
    raw_rule: Dict[str, Any],
    *,
    source_registry_lookup: Dict[str, Dict[str, Any]],
    index: int,
) -> Dict[str, Any]:
    rule = safe_dict(raw_rule)
    source_id = safe_str(rule.get("source_id"), "unknown_source")
    source = safe_dict(source_registry_lookup.get(source_id))
    extracted = safe_str(
        rule.get("extracted_text_or_summary")
        or rule.get("candidate_value")
        or rule.get("value")
        or rule.get("summary")
    )
    numeric_thresholds = safe_list(rule.get("numeric_thresholds")) or _numeric_thresholds_from_text(extracted)
    retrieved_at = safe_str(rule.get("retrieved_at") or rule.get("retrieved_date") or source.get("retrieved_at"), _today())
    source_stale = bool(source.get("stale"))
    acceptance_status = _candidate_acceptance_status(rule.get("acceptance_status"))
    normalized = {
        "rule_id": safe_str(rule.get("rule_id"), f"candidate_rule_{index}"),
        "discipline": safe_str(rule.get("discipline"), "general"),
        "topic": safe_str(rule.get("topic"), "Unclassified standard"),
        "extracted_text_or_summary": extracted,
        "candidate_value": extracted,
        "numeric_thresholds": numeric_thresholds,
        "source_id": source_id,
        "source_url": safe_str(rule.get("source_url") or source.get("source_url")),
        "source_document_title": safe_str(
            rule.get("source_document_title")
            or rule.get("document_title")
            or source.get("document_title")
            or source.get("agency")
        ),
        "source_version_or_effective_date": safe_str(
            rule.get("source_version_or_effective_date")
            or rule.get("version_or_effective_date")
            or source.get("version_or_effective_date")
        ),
        "source_section": safe_str(rule.get("source_section")),
        "retrieved_date": safe_str(rule.get("retrieved_date") or retrieved_at),
        "retrieved_at": retrieved_at,
        "confidence": safe_str(rule.get("confidence"), "candidate"),
        "status": safe_str(rule.get("status"), "candidate"),
        "acceptance_status": acceptance_status,
        "requires_user_acceptance": True,
        "needs_human_confirmation": True,
        "source_type": safe_str(rule.get("source_type")) or _registry_source_type(rule),
        "needs_review": source_stale or acceptance_status in {"candidate", "unaccepted"},
        "review_reasons": [],
    }
    if source_stale:
        normalized["review_reasons"].append("source_stale")
    if acceptance_status in {"candidate", "unaccepted"}:
        normalized["review_reasons"].append("requires_user_acceptance")
    return normalized


def build_candidate_rule_report(
    candidate_rules: Iterable[Dict[str, Any]],
    *,
    source_registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    registry = safe_dict(source_registry)
    source_lookup = _source_registry_by_id(registry)
    normalized_rules = [
        _normalize_candidate_rule(raw_rule, source_registry_lookup=source_lookup, index=index)
        for index, raw_rule in enumerate(candidate_rules or (), start=1)
        if safe_dict(raw_rule)
    ]
    by_discipline: Dict[str, List[Dict[str, Any]]] = {}
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    duplicate_lookup: Dict[Tuple[Any, ...], List[str]] = {}
    for rule in normalized_rules:
        by_discipline.setdefault(safe_str(rule.get("discipline"), "general"), []).append(rule)
        by_source.setdefault(safe_str(rule.get("source_id"), "unknown_source"), []).append(rule)
        duplicate_lookup.setdefault(_duplicate_signature(rule), []).append(safe_str(rule.get("rule_id")))

    duplicate_groups = [
        {"rule_ids": sorted(rule_ids), "duplicate_count": len(rule_ids)}
        for rule_ids in duplicate_lookup.values()
        if len(rule_ids) > 1
    ]
    duplicate_rule_ids = sorted({rule_id for group in duplicate_groups for rule_id in group["rule_ids"]})
    stale_rule_ids = sorted(
        safe_str(rule.get("rule_id"))
        for rule in normalized_rules
        if "source_stale" in safe_list(rule.get("review_reasons"))
    )
    needs_review_rule_ids = sorted(
        safe_str(rule.get("rule_id"))
        for rule in normalized_rules
        if bool(rule.get("needs_review"))
    )
    for rule in normalized_rules:
        rule["duplicate_candidate"] = safe_str(rule.get("rule_id")) in set(duplicate_rule_ids)
        if rule["duplicate_candidate"] and "duplicate_candidate" not in rule["review_reasons"]:
            rule["review_reasons"].append("duplicate_candidate")

    return {
        "version": "standards_candidate_rule_report_v1",
        "candidate_count": len(normalized_rules),
        "candidate_rules": normalized_rules,
        "by_discipline": by_discipline,
        "by_source": by_source,
        "duplicate_rule_ids": duplicate_rule_ids,
        "duplicate_groups": duplicate_groups,
        "duplicate_count": len(duplicate_rule_ids),
        "stale_rule_ids": stale_rule_ids,
        "needs_review_rule_ids": needs_review_rule_ids,
        "requires_user_acceptance": True,
        "acceptance_status": "candidate",
        "accepted_rule_count": 0,
        "production_usable": False,
        "truth_label": "Candidate standards are review inputs only and cannot satisfy production compliance until explicitly accepted through the standards acceptance workflow.",
    }


def build_standards_source_registry(
    *,
    jurisdiction: Optional[Dict[str, Any]] = None,
    sources: Optional[Iterable[Dict[str, Any]]] = None,
    candidate_rules: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build review-only source metadata for jurisdiction/company standards discovery."""

    jurisdiction_rec = safe_dict(jurisdiction)
    rules_by_source: Dict[str, List[str]] = {}
    for raw_rule in candidate_rules or ():
        rule = safe_dict(raw_rule)
        source_id = safe_str(rule.get("source_id"), "unknown_source")
        rule_id = safe_str(rule.get("rule_id"))
        if rule_id:
            rules_by_source.setdefault(source_id, []).append(rule_id)

    source_records = [safe_dict(item) for item in (sources or ()) if safe_dict(item)]
    known_source_ids = {safe_str(source.get("source_id") or source.get("id")) for source in source_records}
    for raw_rule in candidate_rules or ():
        rule = safe_dict(raw_rule)
        source_id = safe_str(rule.get("source_id"))
        if not source_id or source_id in known_source_ids:
            continue
        known_source_ids.add(source_id)
        source_records.append(
            {
                "source_id": source_id,
                "agency": safe_str(rule.get("agency")),
                "discipline": safe_str(rule.get("discipline"), "general"),
                "source_url": safe_str(rule.get("source_url")),
                "document_title": safe_str(rule.get("document_title") or rule.get("source_section") or source_id),
                "version_or_effective_date": safe_str(rule.get("version_or_effective_date")),
                "retrieved_at": safe_str(rule.get("retrieved_at") or rule.get("retrieved_date"), _today()),
                "source_type": safe_str(rule.get("source_type")) or _registry_source_type(rule),
                "confidence": safe_str(rule.get("confidence")),
            }
        )

    entries: List[Dict[str, Any]] = []
    for index, raw_source in enumerate(source_records, start=1):
        source = safe_dict(raw_source)
        source_id = safe_str(source.get("source_id") or source.get("id"), f"source_{index}")
        source_url = safe_str(source.get("source_url") or source.get("url"))
        retrieved_at = safe_str(source.get("retrieved_at") or source.get("retrieved_date"), _today())
        source_type = _registry_source_type({"source_id": source_id, **source, "source_url": source_url})
        confidence = _registry_confidence(source, source_type)
        staleness = _staleness_fields(retrieved_at)
        entry = StandardsSourceRegistryEntry(
            source_id=source_id,
            jurisdiction={
                "city": safe_str(jurisdiction_rec.get("city")),
                "county": safe_str(jurisdiction_rec.get("county")),
                "state": safe_str(jurisdiction_rec.get("state")),
                "utility_provider": safe_str(jurisdiction_rec.get("utility_provider")),
            },
            agency=safe_str(source.get("agency") or source.get("name")),
            discipline=safe_str(source.get("discipline") or source.get("scope"), "general"),
            source_url=source_url,
            document_title=safe_str(source.get("document_title") or source.get("name")),
            version_or_effective_date=safe_str(source.get("version_or_effective_date")),
            retrieved_at=retrieved_at,
            source_type=source_type,
            confidence=confidence,
            candidate_rule_ids=tuple(sorted(set(rules_by_source.get(source_id, [])))),
            acceptance_status=_candidate_acceptance_status(source.get("acceptance_status") or source.get("status")),
            stale_after_days=int(staleness["stale_after_days"]),
            age_days=staleness["age_days"],
            stale=bool(staleness["stale"]),
        )
        rec = asdict(entry)
        rec["candidate_rule_ids"] = list(entry.candidate_rule_ids)
        rec["staleness"] = staleness
        entries.append(rec)

    return {
        "version": "standards_source_registry_v1",
        "retrieved_at": _today(),
        "source_count": len(entries),
        "candidate_source_count": sum(1 for item in entries if item["acceptance_status"] in {"candidate", "unaccepted"}),
        "accepted_source_count": 0,
        "sources": entries,
        "truth_label": "Source registry entries are discovery metadata only; candidate or unaccepted sources cannot satisfy production acceptance.",
    }


def deepcopy_source_registry_for_acceptance(review_packet: Dict[str, Any], accepted_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    registry = safe_dict(review_packet.get("source_registry") or safe_dict(review_packet.get("discovery")).get("source_registry"))
    if not registry:
        return build_standards_source_registry(
            jurisdiction=safe_dict(safe_dict(review_packet.get("discovery")).get("jurisdiction")),
            sources=safe_list(safe_dict(review_packet.get("discovery")).get("sources")),
            candidate_rules=accepted_rules,
        )
    copied = deepcopy(registry)
    copied["accepted_source_count"] = 0
    copied["truth_label"] = (
        "Source registry entries remain discovery metadata. Rule acceptance does not automatically accept a source document."
    )
    return copied


def discover_standards_sources(
    *,
    city: str = "",
    county: str = "",
    state: str = "",
    utility_provider: str = "",
) -> Dict[str, Any]:
    city_name = safe_str(city)
    county_name = safe_str(county)
    state_name = safe_str(state)
    utility_name = safe_str(utility_provider)
    query_bits = " ".join(item for item in (city_name, county_name, state_name) if item)
    sources: List[StandardsSource] = [
        StandardsSource(
            source_id="civora_us_baseline",
            name="Civora U.S. Baseline Concept Standards",
            scope="concept",
            url="internal://civora/us-baseline-concept-standards",
            status="available",
            notes="Fallback concept checks only; not a permit authority.",
        )
    ]
    if query_bits:
        encoded = quote_plus(query_bits)
        sources.extend(
            [
                StandardsSource(
                    source_id="municipal_code_search",
                    name="Municipal code search",
                    scope="local",
                    url=f"https://www.google.com/search?q={encoded}+municipal+code+stormwater+engineering+standards",
                    status="candidate_source",
                    notes="Use to locate the official city/county code or standards page; user must confirm exact source.",
                ),
                StandardsSource(
                    source_id="public_works_search",
                    name="Public works standards search",
                    scope="local",
                    url=f"https://www.google.com/search?q={encoded}+public+works+design+manual+engineering+standards",
                    status="candidate_source",
                    notes="Use to locate drainage, utility, roadway, and construction standards.",
                ),
            ]
        )
    if state_name:
        sources.append(
            StandardsSource(
                source_id="state_dot_search",
                name="State DOT standards search",
                scope="state",
                url=f"https://www.google.com/search?q={quote_plus(state_name)}+DOT+roadway+design+manual+drainage+standards",
                status="candidate_source",
                notes="State roadway/drainage standards can govern work in or near DOT ROW.",
            )
        )
    if utility_name:
        sources.append(
            StandardsSource(
                source_id="utility_provider_search",
                name="Utility provider standards search",
                scope="utility",
                url=f"https://www.google.com/search?q={quote_plus(utility_name)}+water+sewer+design+standards",
                status="candidate_source",
                notes="Utility provider standards often govern water/sewer cover, separation, materials, and details.",
            )
        )
    discovery = {
        "success": True,
        "source_type": "standards_discovery_registry",
        "retrieved_date": _today(),
        "retrieved_at": _today(),
        "jurisdiction": {
            "city": city_name,
            "county": county_name,
            "state": state_name,
            "utility_provider": utility_name,
        },
        "sources": [asdict(source) for source in sources],
        "truth_label": "These are candidate sources. Civora must not apply jurisdiction rules until the user accepts or edits extracted rules.",
    }
    discovery["source_registry"] = build_standards_source_registry(
        jurisdiction=discovery["jurisdiction"],
        sources=discovery["sources"],
    )
    return discovery


def baseline_us_rule_candidates() -> List[Dict[str, Any]]:
    return [asdict(rule) for rule in BASELINE_US_CONCEPT_RULES]


def build_standards_review_packet(
    *,
    city: str = "",
    county: str = "",
    state: str = "",
    utility_provider: str = "",
    extracted_rules: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    discovery = discover_standards_sources(city=city, county=county, state=state, utility_provider=utility_provider)
    candidates = baseline_us_rule_candidates()
    for index, raw in enumerate(extracted_rules or (), start=1):
        rec = safe_dict(raw)
        if not rec:
            continue
        candidates.append(
            {
                "rule_id": safe_str(rec.get("rule_id"), f"extracted_rule_{index}"),
                "discipline": safe_str(rec.get("discipline"), "general"),
                "topic": safe_str(rec.get("topic"), "Unclassified standard"),
                "candidate_value": safe_str(rec.get("candidate_value") or rec.get("value")),
                "extracted_text_or_summary": safe_str(rec.get("extracted_text_or_summary") or rec.get("candidate_value") or rec.get("value")),
                "numeric_thresholds": deepcopy(safe_list(rec.get("numeric_thresholds"))),
                "source_id": safe_str(rec.get("source_id"), "user_supplied_source"),
                "source_url": safe_str(rec.get("source_url")),
                "source_document_title": safe_str(rec.get("source_document_title") or rec.get("document_title")),
                "source_version_or_effective_date": safe_str(rec.get("source_version_or_effective_date") or rec.get("version_or_effective_date")),
                "source_section": safe_str(rec.get("source_section")),
                "retrieved_date": safe_str(rec.get("retrieved_date"), _today()),
                "retrieved_at": safe_str(rec.get("retrieved_at") or rec.get("retrieved_date"), _today()),
                "confidence": safe_str(rec.get("confidence"), "extracted"),
                "status": safe_str(rec.get("status"), "candidate"),
                "acceptance_status": _candidate_acceptance_status(rec.get("acceptance_status")),
                "source_type": safe_str(rec.get("source_type")) or _registry_source_type(rec),
                "needs_human_confirmation": True,
            }
        )
    source_registry = build_standards_source_registry(
        jurisdiction=discovery.get("jurisdiction"),
        sources=safe_list(discovery.get("sources")),
        candidate_rules=candidates,
    )
    candidate_rule_report = build_candidate_rule_report(candidates, source_registry=source_registry)
    return {
        "success": True,
        "source_type": "standards_review_packet",
        "discovery": discovery,
        "source_registry": source_registry,
        "candidate_rule_report": candidate_rule_report,
        "candidate_rules": candidate_rule_report["candidate_rules"],
        "accepted_rules": [],
        "rejected_rules": [],
        "truth_label": "Candidate standards require user acceptance/editing before production QA can rely on them.",
    }


def _reviewer_identity(*values: Any) -> str:
    for value in values:
        text = safe_str(value)
        if text:
            return text
    return ""


def _review_action(rule_id: str, actions_by_rule: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return safe_dict(actions_by_rule.get(rule_id))


def _accepted_candidate_rule(
    candidate: Dict[str, Any],
    *,
    action: Dict[str, Any],
    reviewer_id: str,
    approval_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    accepted_by = _reviewer_identity(
        action.get("accepted_by"),
        action.get("reviewed_by"),
        action.get("reviewer_id"),
        reviewer_id,
        approval_metadata.get("accepted_by"),
        approval_metadata.get("reviewed_by"),
        approval_metadata.get("approved_by"),
        approval_metadata.get("user_id"),
    )
    accepted_at = safe_str(action.get("accepted_at") or action.get("reviewed_at") or approval_metadata.get("accepted_at"), _today())
    accepted = deepcopy(candidate)
    accepted.update(
        {
            "status": "accepted",
            "acceptance_status": "accepted",
            "requires_user_acceptance": False,
            "needs_human_confirmation": False,
            "accepted_at": accepted_at,
            "accepted_date": accepted_at[:10],
            "accepted_by": accepted_by,
            "acceptance_note": safe_str(action.get("acceptance_note") or action.get("note") or approval_metadata.get("acceptance_note")),
            "approval_metadata": deepcopy(approval_metadata),
            "source_id": safe_str(candidate.get("source_id")),
            "source_url": safe_str(candidate.get("source_url")),
            "source_version_or_effective_date": safe_str(candidate.get("source_version_or_effective_date")),
            "candidate_rule_id": safe_str(candidate.get("rule_id")),
        }
    )
    return accepted


def review_candidate_standards(
    review_packet: Dict[str, Any],
    review_actions: Iterable[Dict[str, Any]],
    *,
    reviewer_id: str = "",
    approval_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply explicit candidate standards review actions without auto-accepting rules."""

    approval = safe_dict(approval_metadata)
    actions_by_rule = {
        safe_str(action.get("rule_id")): safe_dict(action)
        for action in review_actions or ()
        if safe_str(safe_dict(action).get("rule_id"))
    }
    candidate_rules = [
        safe_dict(rule)
        for rule in safe_list(
            safe_dict(review_packet.get("candidate_rule_report")).get("candidate_rules")
            or review_packet.get("candidate_rules")
        )
        if safe_dict(rule)
    ]
    accepted_rules: List[Dict[str, Any]] = []
    rejected_rules: List[Dict[str, Any]] = []
    pending_rules: List[Dict[str, Any]] = []
    audit_trail: List[Dict[str, Any]] = []
    action_errors: List[Dict[str, Any]] = []
    seen_rule_ids = {safe_str(rule.get("rule_id")) for rule in candidate_rules if safe_str(rule.get("rule_id"))}
    for rule_id, action in actions_by_rule.items():
        if rule_id not in seen_rule_ids:
            action_errors.append(
                {
                    "rule_id": rule_id,
                    "action": safe_str(action.get("action")),
                    "reason": "Review action references a candidate rule ID that is not in the review packet.",
                }
            )

    for candidate in candidate_rules:
        rule_id = safe_str(candidate.get("rule_id"))
        action = _review_action(rule_id, actions_by_rule)
        raw_decision = safe_str(action.get("action") or action.get("decision") or action.get("status"), "pending").lower()
        decision = {
            "accept": "accepted",
            "accepted": "accepted",
            "approve": "accepted",
            "approved": "accepted",
            "reject": "rejected",
            "rejected": "rejected",
            "decline": "rejected",
            "pending": "pending",
            "defer": "pending",
            "left_pending": "pending",
        }.get(raw_decision, "pending")
        audit_record = {
            "rule_id": rule_id,
            "requested_action": raw_decision,
            "decision": decision,
            "reviewed_at": safe_str(action.get("reviewed_at") or action.get("accepted_at") or approval.get("reviewed_at"), _today()),
            "reviewed_by": _reviewer_identity(
                action.get("reviewed_by"),
                action.get("accepted_by"),
                action.get("reviewer_id"),
                reviewer_id,
                approval.get("reviewed_by"),
                approval.get("approved_by"),
                approval.get("user_id"),
            ),
            "approval_metadata": deepcopy(approval),
            "note": safe_str(action.get("acceptance_note") or action.get("rejection_reason") or action.get("note")),
            "source_id": safe_str(candidate.get("source_id")),
            "source_url": safe_str(candidate.get("source_url")),
        }
        if decision == "accepted":
            accepted_by = _reviewer_identity(
                action.get("accepted_by"),
                action.get("reviewed_by"),
                action.get("reviewer_id"),
                reviewer_id,
                approval.get("accepted_by"),
                approval.get("reviewed_by"),
                approval.get("approved_by"),
                approval.get("user_id"),
            )
            if not accepted_by and not approval:
                pending = deepcopy(candidate)
                pending["status"] = "pending"
                pending["acceptance_status"] = "candidate"
                pending["requires_user_acceptance"] = True
                pending["pending_reason"] = "Acceptance requires reviewer identity or approval metadata."
                pending_rules.append(pending)
                audit_record["decision"] = "pending"
                audit_record["blocked_reason"] = pending["pending_reason"]
                action_errors.append({"rule_id": rule_id, "action": "accepted", "reason": pending["pending_reason"]})
            else:
                accepted_rules.append(
                    _accepted_candidate_rule(
                        candidate,
                        action=action,
                        reviewer_id=reviewer_id,
                        approval_metadata=approval,
                    )
                )
        elif decision == "rejected":
            rejected = deepcopy(candidate)
            rejected["status"] = "rejected"
            rejected["acceptance_status"] = "unaccepted"
            rejected["requires_user_acceptance"] = False
            rejected["rejected_at"] = safe_str(action.get("rejected_at") or action.get("reviewed_at"), _today())
            rejected["rejected_by"] = audit_record["reviewed_by"]
            rejected["rejection_reason"] = safe_str(action.get("rejection_reason") or action.get("reason") or action.get("note"))
            rejected_rules.append(rejected)
        else:
            pending = deepcopy(candidate)
            pending["status"] = "pending"
            pending["acceptance_status"] = _candidate_acceptance_status(pending.get("acceptance_status"))
            pending["requires_user_acceptance"] = True
            pending["pending_reason"] = safe_str(action.get("pending_reason") or action.get("reason"), "No explicit accept/reject action was recorded.")
            pending_rules.append(pending)
        audit_trail.append(audit_record)

    source_urls = sorted({safe_str(rule.get("source_url")) for rule in accepted_rules if safe_str(rule.get("source_url"))})
    accepted_retrieved_dates = [
        safe_str(rule.get("retrieved_date") or rule.get("retrieved_at"))
        for rule in accepted_rules
        if safe_str(rule.get("retrieved_date") or rule.get("retrieved_at"))
    ]
    official_source_count = sum(
        1
        for url in source_urls
        if url.startswith("https://")
        and not any(blocked in url.lower() for blocked in ("google.com/search", "bing.com/search", "internal://"))
    )
    result = {
        "success": bool(accepted_rules or rejected_rules or pending_rules) and not action_errors,
        "source": "candidate_standards_review_workflow",
        "version": "standards_candidate_acceptance_v1",
        "retrieved_date": accepted_retrieved_dates[0] if accepted_retrieved_dates else safe_str(review_packet.get("retrieved_date"), _today()),
        "accepted_rule_count": len(accepted_rules),
        "rejected_rule_count": len(rejected_rules),
        "pending_rule_count": len(pending_rules),
        "accepted_rules": accepted_rules,
        "rejected_rules": rejected_rules,
        "pending_rules": pending_rules,
        "source_urls": source_urls,
        "source_registry": deepcopy_source_registry_for_acceptance(review_packet, accepted_rules),
        "candidate_rule_report": deepcopy(safe_dict(review_packet.get("candidate_rule_report"))),
        "official_source_count": official_source_count,
        "needs_source_review": bool(accepted_rules and official_source_count <= 0),
        "accepted_for_qa": bool(accepted_rules),
        "reviewer_id": safe_str(reviewer_id),
        "approval_metadata": deepcopy(approval),
        "audit_trail": audit_trail,
        "action_errors": action_errors,
        "truth_label": "Candidate standards review records explicit decisions only; rejected and pending candidates remain review-only and cannot satisfy production compliance.",
    }
    validation = validate_standards_acceptance_for_production(result)
    result["production_validation"] = validation
    result["production_usable"] = bool(validation.get("production_usable"))
    return result


def accept_standards_rules(
    review_packet: Dict[str, Any],
    accepted_rule_ids: Iterable[str],
    edits: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    accepted_by: str = "",
) -> Dict[str, Any]:
    accepted = {safe_str(item) for item in accepted_rule_ids if safe_str(item)}
    edit_map = safe_dict(edits)
    candidates = [safe_dict(item) for item in safe_list(review_packet.get("candidate_rules"))]
    accepted_rules: List[Dict[str, Any]] = []
    rejected_rules: List[Dict[str, Any]] = []
    pending_rules: List[Dict[str, Any]] = []
    action_errors: List[Dict[str, Any]] = []
    audit_trail: List[Dict[str, Any]] = []
    reviewer = safe_str(accepted_by)
    for rule in candidates:
        rule_id = safe_str(rule.get("rule_id"))
        edited = dict(rule)
        if rule_id in edit_map:
            edited.update(safe_dict(edit_map[rule_id]))
        audit_record = {
            "rule_id": rule_id,
            "requested_action": "accepted" if rule_id in accepted else "rejected",
            "decision": "pending",
            "reviewed_at": _today(),
            "reviewed_by": reviewer,
            "source_id": safe_str(edited.get("source_id")),
            "source_url": safe_str(edited.get("source_url")),
            "source_section": safe_str(edited.get("source_section")),
        }
        if rule_id in accepted:
            if reviewer:
                edited["status"] = "accepted"
                edited["acceptance_status"] = "accepted"
                edited["accepted_date"] = _today()
                edited["accepted_at"] = _today()
                edited["accepted_by"] = reviewer
                edited["requires_user_acceptance"] = False
                edited["needs_human_confirmation"] = False
                accepted_rules.append(edited)
                audit_record["decision"] = "accepted"
            else:
                edited["status"] = "pending"
                edited["acceptance_status"] = "candidate"
                edited["requires_user_acceptance"] = True
                edited["pending_reason"] = "Acceptance requires reviewer identity or approval metadata."
                pending_rules.append(edited)
                action_errors.append({"rule_id": rule_id, "action": "accepted", "reason": edited["pending_reason"]})
                audit_record["decision"] = "pending"
                audit_record["blocked_reason"] = edited["pending_reason"]
        else:
            edited["status"] = "not_accepted"
            edited["acceptance_status"] = "unaccepted"
            edited["requires_user_acceptance"] = False
            rejected_rules.append(edited)
            audit_record["decision"] = "rejected"
        audit_trail.append(audit_record)
    source_urls = sorted({safe_str(rule.get("source_url")) for rule in accepted_rules if safe_str(rule.get("source_url"))})
    official_source_count = sum(
        1
        for url in source_urls
        if url.startswith("https://")
        and not any(blocked in url.lower() for blocked in ("google.com/search", "bing.com/search", "internal://"))
    )
    result = {
        "success": bool(accepted_rules),
        "source": "standards_discovery_engine",
        "version": "standards_acceptance_v1",
        "retrieved_date": safe_str(review_packet.get("retrieved_date"), _today()),
        "accepted_rule_count": len(accepted_rules),
        "accepted_rules": accepted_rules,
        "rejected_rules": rejected_rules,
        "pending_rules": pending_rules,
        "source_urls": source_urls,
        "source_registry": deepcopy_source_registry_for_acceptance(review_packet, accepted_rules),
        "official_source_count": official_source_count,
        "needs_source_review": bool(accepted_rules and official_source_count <= 0),
        "accepted_for_qa": bool(accepted_rules),
        "reviewer_id": reviewer,
        "audit_trail": audit_trail,
        "action_errors": action_errors,
        "truth_label": "Only explicitly accepted rules with reviewer identity are eligible for production QA; baseline rules remain concept-only unless explicitly accepted.",
    }
    validation = validate_standards_acceptance_for_production(result)
    result["production_validation"] = validation
    result["production_usable"] = bool(validation.get("production_usable"))
    return result


def standards_pack_from_acceptance(acceptance: Dict[str, Any]) -> Dict[str, Any]:
    accepted_rules = [safe_dict(item) for item in safe_list(acceptance.get("accepted_rules"))]
    pack = {
        "source": "accepted_standards_review_packet",
        "version": safe_str(acceptance.get("version"), "standards_acceptance_v1"),
        "accepted_rule_count": len(accepted_rules),
        "rules": accepted_rules,
        "source_urls": list(safe_list(acceptance.get("source_urls"))),
        "official_source_count": safe_dict(acceptance).get("official_source_count", 0),
        "source_registry": deepcopy(safe_dict(acceptance.get("source_registry"))),
        "rejected_rules": deepcopy(safe_list(acceptance.get("rejected_rules"))),
        "pending_rules": deepcopy(safe_list(acceptance.get("pending_rules"))),
        "audit_trail": deepcopy(safe_list(acceptance.get("audit_trail"))),
        "needs_source_review": bool(acceptance.get("needs_source_review")),
        "accepted_for_qa": bool(accepted_rules),
        "truth_label": "User-accepted standards pack. Engineer review is still required for permit use.",
    }
    pack["production_validation"] = validate_standards_acceptance_for_production(pack)
    pack["production_usable"] = bool(pack["production_validation"].get("production_usable"))
    return pack


def _company_standards_trace_ready(company: Dict[str, Any]) -> bool:
    rec = safe_dict(company)
    source_present = any(
        safe_str(rec.get(key))
        for key in ("source", "source_url", "file", "document_title", "standard_id", "cad_layer_standard", "cad_layers")
    )
    approved_by = safe_str(rec.get("approved_by") or rec.get("reviewed_by"))
    approval_date = safe_str(rec.get("approval_date") or rec.get("reviewed_at") or rec.get("accepted_date"))
    return bool(rec.get("production_usable") is True and source_present and approved_by and approval_date)


def standards_project_evidence_from_acceptance(
    acceptance: Dict[str, Any],
    *,
    review_packet: Optional[Dict[str, Any]] = None,
    company_standards: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pack = standards_pack_from_acceptance(acceptance)
    discovery = safe_dict(safe_dict(review_packet).get("discovery"))
    jurisdiction = safe_dict(discovery.get("jurisdiction"))
    source_urls = list(safe_list(pack.get("source_urls")))
    jurisdiction_profile = {
        "source": "standards_discovery_engine",
        "city": safe_str(jurisdiction.get("city")),
        "county": safe_str(jurisdiction.get("county")),
        "state": safe_str(jurisdiction.get("state")),
        "utility_provider": safe_str(jurisdiction.get("utility_provider")),
        "source_urls": source_urls,
        "official_source_count": pack.get("official_source_count", 0),
        "production_usable": bool(pack.get("production_usable")) and bool(source_urls),
    }
    company_profile = safe_dict(company_standards)
    if not company_profile:
        company_profile = {
            "source": "civora_default_company_standards_placeholder",
            "production_usable": False,
            "truth_label": "Company standards were not supplied; attach CAD/layer/sheet/detail standards before final issue.",
        }
    return {
        "success": bool(acceptance.get("success")),
        "standards_acceptance": acceptance,
        "design_standards": pack,
        "standards_source_registry": deepcopy(safe_dict(acceptance.get("source_registry"))),
        "jurisdiction_standards": jurisdiction_profile,
        "company_standards": company_profile,
        "production_usable": (
            bool(pack.get("production_usable"))
            and bool(jurisdiction_profile.get("production_usable"))
            and _company_standards_trace_ready(company_profile)
        ),
        "truth_label": "Project standards evidence is production-usable only after accepted official rules and jurisdiction traceability are present.",
    }


def _source_url_is_official(url: str) -> bool:
    lowered = safe_str(url).lower()
    return (
        lowered.startswith("https://")
        and "google.com/search" not in lowered
        and "bing.com/search" not in lowered
        and "internal://civora" not in lowered
    )


def _rule_is_inferred(rule: Dict[str, Any]) -> bool:
    source_url = safe_str(rule.get("source_url")).lower()
    source_id = safe_str(rule.get("source_id")).lower()
    confidence = safe_str(rule.get("confidence")).lower()
    source_type = safe_str(rule.get("source_type")).lower()
    source_status = safe_str(rule.get("source_status") or rule.get("authority_status")).lower()
    return (
        source_url.startswith("internal://")
        or "google.com/search" in source_url
        or "bing.com/search" in source_url
        or confidence in {"baseline", "inferred", "candidate", "assumed"}
        or source_type in {"internal_baseline", "search_candidate", "scraped_candidate"}
        or source_status in {"candidate", "candidate_source", "inferred", "assumed"}
        or source_id in {"civora_us_baseline", "municipal_code_search", "public_works_search", "state_dot_search", "utility_provider_search"}
    )


def validate_standards_acceptance_for_production(standards: Dict[str, Any]) -> Dict[str, Any]:
    """Validate accepted standards before production QA is allowed to rely on them."""

    rec = safe_dict(standards)
    rules = [safe_dict(item) for item in safe_list(rec.get("accepted_rules") or rec.get("rules")) if safe_dict(item)]
    blockers: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not rules:
        blockers.append({"field": "accepted_rules", "reason": "No user-accepted standards rules are available."})
    source_urls = [safe_str(url) for url in safe_list(rec.get("source_urls")) if safe_str(url)]
    if not source_urls:
        source_urls = [safe_str(rule.get("source_url")) for rule in rules if safe_str(rule.get("source_url"))]
    official_urls = [url for url in source_urls if _source_url_is_official(url)]
    baseline_rules = [
        safe_str(rule.get("rule_id"))
        for rule in rules
        if safe_str(rule.get("source_url")).startswith("internal://")
        or safe_str(rule.get("confidence")).lower() == "baseline"
        or safe_str(rule.get("source_id")) == "civora_us_baseline"
    ]
    inferred_rules = [
        safe_str(rule.get("rule_id"), f"rule_{index}")
        for index, rule in enumerate(rules, start=1)
        if _rule_is_inferred(rule)
    ]
    non_accepted_status_rules = []
    stale_rules = []
    for index, rule in enumerate(rules, start=1):
        status = safe_str(rule.get("status")).lower()
        acceptance_status = safe_str(rule.get("acceptance_status")).lower()
        if status != "accepted" or acceptance_status != "accepted":
            non_accepted_status_rules.append(
                {
                    "rule_id": safe_str(rule.get("rule_id"), f"rule_{index}"),
                    "status": status,
                    "acceptance_status": acceptance_status,
                }
            )
        staleness = _staleness_fields(rule.get("retrieved_at") or rule.get("retrieved_date"))
        if bool(staleness.get("stale")):
            stale_rules.append(
                {
                    "rule_id": safe_str(rule.get("rule_id"), f"rule_{index}"),
                    "retrieved_at": safe_str(rule.get("retrieved_at") or rule.get("retrieved_date")),
                    "age_days": staleness.get("age_days"),
                    "stale_after_days": staleness.get("stale_after_days"),
                }
            )
    if rules and not official_urls:
        blockers.append(
            {
                "field": "official_sources",
                "reason": "Accepted rules do not cite an official HTTPS source.",
                "source_urls": source_urls,
            }
        )
    if baseline_rules:
        blockers.append(
            {
                "field": "baseline_rules",
                "reason": "Baseline concept rules cannot be production authority without an official source.",
                "rule_ids": baseline_rules,
            }
        )
    non_baseline_inferred = [rule_id for rule_id in inferred_rules if rule_id not in set(baseline_rules)]
    if non_baseline_inferred:
        blockers.append(
            {
                "field": "inferred_rules",
                "reason": "Accepted rules still trace to inferred/search/candidate sources, not selected official standards.",
                "rule_ids": non_baseline_inferred,
            }
        )
    if non_accepted_status_rules:
        blockers.append(
            {
                "field": "rule_acceptance_status",
                "reason": "Candidate or unaccepted rules cannot satisfy standards acceptance.",
                "rules": non_accepted_status_rules,
            }
        )
    if stale_rules:
        blockers.append(
            {
                "field": "standards_stale",
                "reason": "Accepted standards source evidence is stale and must be refreshed or reaccepted before production QA.",
                "rules": stale_rules,
            }
        )
    incomplete_rules = []
    for rule in rules:
        missing = [
            key
            for key in ("discipline", "topic", "candidate_value", "source_id", "source_url", "source_section", "accepted_by", "accepted_date")
            if not safe_str(rule.get(key))
        ]
        if missing:
            incomplete_rules.append({"rule_id": safe_str(rule.get("rule_id")), "missing": missing})
    if incomplete_rules:
        blockers.append(
            {
                "field": "rule_metadata",
                "reason": "Accepted rules are missing traceable metadata.",
                "rules": incomplete_rules,
            }
        )
    if bool(rec.get("needs_source_review")):
        warnings.append("Accepted standards still need source review before permit use.")
    return {
        "success": not blockers,
        "production_usable": not blockers,
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warnings": warnings,
        "accepted_rule_count": len(rules),
        "accepted_rule_ids": [safe_str(rule.get("rule_id"), f"rule_{index}") for index, rule in enumerate(rules, start=1)],
        "inferred_rule_count": len(set(inferred_rules)),
        "inferred_rule_ids": sorted(set(inferred_rules)),
        "official_source_count": len(set(official_urls)),
        "official_source_urls": sorted(set(official_urls)),
        "truth_label": "Standards are production-usable only after user acceptance plus official-source traceability.",
    }


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(self.parts)


RULE_PATTERNS: Tuple[Tuple[str, str, str], ...] = (
    ("grading", "ADA slope", r"(?i)(ADA|accessible)[^.]{0,80}(slope|cross slope)[^.]{0,80}(\d+(?:\.\d+)?)\s*(%|percent)"),
    ("utilities", "minimum cover", r"(?i)(minimum|min\.?)[^.]{0,80}(cover)[^.]{0,80}(\d+(?:\.\d+)?)\s*(feet|foot|ft|'|inches|inch|in)"),
    ("utilities", "vertical separation", r"(?i)(vertical)[^.]{0,80}(separation)[^.]{0,80}(\d+(?:\.\d+)?)\s*(feet|foot|ft|'|inches|inch|in)"),
    ("utilities", "utility separation", r"(?i)(water|sewer|sanitary|storm)[^.]{0,80}(separation)[^.]{0,80}(\d+(?:\.\d+)?)\s*(feet|foot|ft|'|inches|inch|in)"),
    ("storm", "detention drawdown", r"(?i)(detention|retention|stormwater)[^.]{0,100}(drawdown|release)[^.]{0,80}(\d+(?:\.\d+)?)\s*(hours|hour|hrs|hr)"),
    ("roadway", "maximum grade", r"(?i)(maximum|max\.?)[^.]{0,80}(grade|slope)[^.]{0,80}(\d+(?:\.\d+)?)\s*(%|percent)"),
    ("sanitary", "manhole spacing", r"(?i)(manhole)[^.]{0,80}(spacing)[^.]{0,80}(\d+(?:\.\d+)?)\s*(feet|foot|ft|'|inches|inch|in)"),
    ("water", "hydrant spacing", r"(?i)(hydrant)[^.]{0,80}(spacing)[^.]{0,80}(\d+(?:\.\d+)?)\s*(feet|foot|ft|'|inches|inch|in)"),
    ("water", "fire flow", r"(?i)(fire\s*flow)[^.]{0,80}(\d+(?:\.\d+)?)\s*(gpm|gallons per minute)"),
    ("water", "residual pressure", r"(?i)(residual\s*pressure|minimum\s*pressure)[^.]{0,80}(\d+(?:\.\d+)?)\s*(psi)"),
    ("water", "maximum velocity", r"(?i)(water)[^.]{0,80}(velocity)[^.]{0,80}(\d+(?:\.\d+)?)\s*(fps|ft/s|feet per second)"),
)


def extract_text_from_html(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html or "")
    return parser.text()


def extract_rule_candidates_from_text(
    text: str,
    *,
    source_id: str,
    source_url: str,
    source_section: str = "",
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    haystack = safe_str(text)
    for pattern_index, (discipline, topic, pattern) in enumerate(RULE_PATTERNS, start=1):
        for match_index, match in enumerate(re.finditer(pattern, haystack), start=1):
            start = max(0, match.start() - 120)
            end = min(len(haystack), match.end() + 120)
            excerpt = " ".join(haystack[start:end].split())
            numeric_thresholds = _numeric_thresholds_from_text(safe_str(match.group(0)))
            candidates.append(
                {
                    "rule_id": f"{source_id}_{discipline}_{pattern_index}_{match_index}",
                    "discipline": discipline,
                    "topic": topic,
                    "extracted_text_or_summary": excerpt,
                    "candidate_value": excerpt,
                    "numeric_thresholds": numeric_thresholds,
                    "source_id": source_id,
                    "source_url": source_url,
                    "source_document_title": "",
                    "source_version_or_effective_date": "",
                    "source_section": source_section or topic,
                    "retrieved_date": _today(),
                    "retrieved_at": _today(),
                    "confidence": "text_pattern_candidate",
                    "status": "candidate",
                    "acceptance_status": "candidate",
                    "requires_user_acceptance": True,
                    "source_type": "scraped_candidate",
                    "needs_review": True,
                    "review_reasons": ["requires_user_acceptance"],
                    "needs_human_confirmation": True,
                }
            )
    return candidates


def fetch_and_extract_rule_candidates(
    source_url: str,
    *,
    source_id: str = "official_source",
    session: Any = requests,
) -> Dict[str, Any]:
    url = safe_str(source_url)
    if not url:
        return {"success": False, "source_url": "", "candidate_rules": [], "warnings": ["Source URL is required."]}
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        content_type = safe_str(getattr(response, "headers", {}).get("content-type", "")).lower()
        body = response.text
    except Exception as exc:
        return {"success": False, "source_url": url, "candidate_rules": [], "warnings": [safe_str(exc)]}
    if "html" in content_type or "<html" in body.lower():
        text = extract_text_from_html(body)
    else:
        text = body
    source_record = {
        "source_id": source_id,
        "source_url": url,
        "document_title": source_id,
        "retrieved_at": _today(),
        "source_type": "scraped_candidate",
        "confidence": "text_pattern_candidate",
        "status": "candidate",
    }
    candidates = extract_rule_candidates_from_text(text, source_id=source_id, source_url=url)
    source_registry = build_standards_source_registry(
        sources=[source_record],
        candidate_rules=candidates,
    )
    candidate_rule_report = build_candidate_rule_report(candidates, source_registry=source_registry)
    return {
        "success": True,
        "source_url": url,
        "source_id": source_id,
        "source_metadata": source_record,
        "source_registry": source_registry,
        "candidate_rule_report": candidate_rule_report,
        "candidate_rules": candidate_rule_report["candidate_rules"],
        "candidate_count": len(candidates),
        "retrieved_date": _today(),
        "retrieved_at": _today(),
        "truth_label": "Extracted rules are candidates only. User acceptance/editing is required before production QA can use them.",
    }


__all__ = [
    "BASELINE_US_CONCEPT_RULES",
    "accept_standards_rules",
    "baseline_us_rule_candidates",
    "build_candidate_rule_report",
    "build_live_source_fetch_record",
    "build_standards_source_registry",
    "build_standards_review_packet",
    "classify_live_standards_source",
    "controlled_single_source_lookup",
    "discover_standards_sources",
    "extract_rule_candidates_from_text",
    "extract_text_from_html",
    "fetch_and_extract_rule_candidates",
    "fetch_live_standards_source_candidate",
    "review_candidate_standards",
    "standards_live_source_policy",
    "standards_pack_from_acceptance",
    "standards_project_evidence_from_acceptance",
    "trusted_standards_source_allowlist",
    "validate_standards_acceptance_for_production",
]
