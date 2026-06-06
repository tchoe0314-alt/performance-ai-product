from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus

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


def _today() -> str:
    return date.today().isoformat()


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
                "source_id": safe_str(rec.get("source_id"), "user_supplied_source"),
                "source_url": safe_str(rec.get("source_url")),
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


def accept_standards_rules(
    review_packet: Dict[str, Any],
    accepted_rule_ids: Iterable[str],
    edits: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    accepted_by: str = "user",
) -> Dict[str, Any]:
    accepted = {safe_str(item) for item in accepted_rule_ids if safe_str(item)}
    edit_map = safe_dict(edits)
    candidates = [safe_dict(item) for item in safe_list(review_packet.get("candidate_rules"))]
    accepted_rules: List[Dict[str, Any]] = []
    rejected_rules: List[Dict[str, Any]] = []
    for rule in candidates:
        rule_id = safe_str(rule.get("rule_id"))
        edited = dict(rule)
        if rule_id in edit_map:
            edited.update(safe_dict(edit_map[rule_id]))
        if rule_id in accepted:
            edited["status"] = "accepted"
            edited["acceptance_status"] = "accepted"
            edited["accepted_date"] = _today()
            edited["accepted_by"] = safe_str(accepted_by, "user")
            edited["needs_human_confirmation"] = False
            accepted_rules.append(edited)
        else:
            edited["status"] = "not_accepted"
            edited["acceptance_status"] = "unaccepted"
            rejected_rules.append(edited)
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
        "source_urls": source_urls,
        "source_registry": deepcopy_source_registry_for_acceptance(review_packet, accepted_rules),
        "official_source_count": official_source_count,
        "needs_source_review": bool(accepted_rules and official_source_count <= 0),
        "accepted_for_qa": bool(accepted_rules),
        "truth_label": "Only accepted rules are eligible for production QA; baseline rules remain concept-only unless explicitly accepted.",
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
        "needs_source_review": bool(acceptance.get("needs_source_review")),
        "accepted_for_qa": bool(accepted_rules),
        "truth_label": "User-accepted standards pack. Engineer review is still required for permit use.",
    }
    pack["production_validation"] = validate_standards_acceptance_for_production(pack)
    pack["production_usable"] = bool(pack["production_validation"].get("production_usable"))
    return pack


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
            and bool(company_profile.get("production_usable"))
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
    incomplete_rules = []
    for rule in rules:
        missing = [
            key
            for key in ("discipline", "topic", "candidate_value", "source_url", "source_section", "accepted_by", "accepted_date")
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
    "build_standards_source_registry",
    "build_standards_review_packet",
    "discover_standards_sources",
    "extract_rule_candidates_from_text",
    "extract_text_from_html",
    "fetch_and_extract_rule_candidates",
    "standards_pack_from_acceptance",
    "standards_project_evidence_from_acceptance",
    "validate_standards_acceptance_for_production",
]
