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
    return {
        "success": bool(accepted_rules),
        "source": "standards_discovery_engine",
        "version": "standards_acceptance_v1",
        "retrieved_date": safe_str(review_packet.get("retrieved_date"), _today()),
        "accepted_rule_count": len(accepted_rules),
        "accepted_rules": accepted_rules,
        "rejected_rules": rejected_rules,
        "production_usable": bool(accepted_rules),
        "truth_label": "Only accepted rules are eligible for production QA; baseline rules remain concept-only unless explicitly accepted.",
    }


def standards_pack_from_acceptance(acceptance: Dict[str, Any]) -> Dict[str, Any]:
    accepted_rules = [safe_dict(item) for item in safe_list(acceptance.get("accepted_rules"))]
    return {
        "source": "accepted_standards_review_packet",
        "version": safe_str(acceptance.get("version"), "standards_acceptance_v1"),
        "accepted_rule_count": len(accepted_rules),
        "rules": accepted_rules,
        "production_usable": bool(accepted_rules),
        "truth_label": "User-accepted standards pack. Engineer review is still required for permit use.",
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
    ("utilities", "utility separation", r"(?i)(water|sewer|sanitary|storm)[^.]{0,80}(separation)[^.]{0,80}(\d+(?:\.\d+)?)\s*(feet|foot|ft|'|inches|inch|in)"),
    ("storm", "detention drawdown", r"(?i)(detention|retention|stormwater)[^.]{0,100}(drawdown|release)[^.]{0,80}(\d+(?:\.\d+)?)\s*(hours|hour|hrs|hr)"),
    ("roadway", "maximum grade", r"(?i)(maximum|max\.?)[^.]{0,80}(grade|slope)[^.]{0,80}(\d+(?:\.\d+)?)\s*(%|percent)"),
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
]
