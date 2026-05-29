from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus

import requests

from .common import safe_dict, safe_list, safe_str


@dataclass(frozen=True)
class StandardsSource:
    source_id: str
    name: str
    scope: str
    url: str
    status: str
    notes: str


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
    confidence: str
    status: str
    needs_human_confirmation: bool


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
        confidence="baseline",
        status="candidate",
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
        confidence="baseline",
        status="candidate",
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
        confidence="baseline",
        status="candidate",
        needs_human_confirmation=True,
    ),
)


def _today() -> str:
    return date.today().isoformat()


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
    return {
        "success": True,
        "source_type": "standards_discovery_registry",
        "retrieved_date": _today(),
        "jurisdiction": {
            "city": city_name,
            "county": county_name,
            "state": state_name,
            "utility_provider": utility_name,
        },
        "sources": [asdict(source) for source in sources],
        "truth_label": "These are candidate sources. Civora must not apply jurisdiction rules until the user accepts or edits extracted rules.",
    }


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
                "confidence": safe_str(rec.get("confidence"), "extracted"),
                "status": safe_str(rec.get("status"), "candidate"),
                "needs_human_confirmation": True,
            }
        )
    return {
        "success": True,
        "source_type": "standards_review_packet",
        "discovery": discovery,
        "candidate_rules": candidates,
        "accepted_rules": [],
        "rejected_rules": [],
        "truth_label": "Candidate standards require user acceptance/editing before production QA can rely on them.",
    }


def accept_standards_rules(review_packet: Dict[str, Any], accepted_rule_ids: Iterable[str], edits: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
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
            edited["accepted_date"] = _today()
            edited["needs_human_confirmation"] = False
            accepted_rules.append(edited)
        else:
            edited["status"] = "not_accepted"
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
    incomplete_rules = []
    for rule in rules:
        missing = [
            key
            for key in ("discipline", "topic", "candidate_value", "source_url", "source_section")
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
        "warnings": warnings,
        "accepted_rule_count": len(rules),
        "official_source_count": len(set(official_urls)),
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
            candidates.append(
                {
                    "rule_id": f"{source_id}_{discipline}_{pattern_index}_{match_index}",
                    "discipline": discipline,
                    "topic": topic,
                    "candidate_value": excerpt,
                    "source_id": source_id,
                    "source_url": source_url,
                    "source_section": source_section or topic,
                    "retrieved_date": _today(),
                    "confidence": "text_pattern_candidate",
                    "status": "candidate",
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
    candidates = extract_rule_candidates_from_text(text, source_id=source_id, source_url=url)
    return {
        "success": True,
        "source_url": url,
        "source_id": source_id,
        "candidate_rules": candidates,
        "candidate_count": len(candidates),
        "retrieved_date": _today(),
        "truth_label": "Extracted rules are candidates only. User acceptance/editing is required before production QA can use them.",
    }


__all__ = [
    "BASELINE_US_CONCEPT_RULES",
    "accept_standards_rules",
    "baseline_us_rule_candidates",
    "build_standards_review_packet",
    "discover_standards_sources",
    "extract_rule_candidates_from_text",
    "extract_text_from_html",
    "fetch_and_extract_rule_candidates",
    "standards_pack_from_acceptance",
    "standards_project_evidence_from_acceptance",
    "validate_standards_acceptance_for_production",
]
