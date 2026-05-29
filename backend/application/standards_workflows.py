from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from backend.planning.golden_runner import run_golden_scenarios
from backend.planning.standards_discovery import (
    accept_standards_rules,
    build_standards_review_packet,
    discover_standards_sources,
    fetch_and_extract_rule_candidates,
    standards_pack_from_acceptance,
    standards_project_evidence_from_acceptance,
)


def discover_standards_response(
    *,
    city: str = "",
    county: str = "",
    state: str = "",
    utility_provider: str = "",
) -> Dict[str, Any]:
    return discover_standards_sources(city=city, county=county, state=state, utility_provider=utility_provider)


def standards_review_packet_response(
    *,
    city: str = "",
    county: str = "",
    state: str = "",
    utility_provider: str = "",
    extracted_rules: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return build_standards_review_packet(
        city=city,
        county=county,
        state=state,
        utility_provider=utility_provider,
        extracted_rules=extracted_rules,
    )


def accept_standards_response(
    *,
    review_packet: Dict[str, Any],
    accepted_rule_ids: Iterable[str],
    edits: Optional[Dict[str, Dict[str, Any]]] = None,
    company_standards: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    acceptance = accept_standards_rules(review_packet, accepted_rule_ids, edits=edits)
    evidence = standards_project_evidence_from_acceptance(
        acceptance,
        review_packet=review_packet,
        company_standards=company_standards,
    )
    evidence["design_standards"] = standards_pack_from_acceptance(acceptance)
    return evidence


def extract_standards_candidates_response(*, source_url: str, source_id: str = "official_source") -> Dict[str, Any]:
    return fetch_and_extract_rule_candidates(source_url, source_id=source_id)


def run_golden_scenarios_response(*, scenario_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    return run_golden_scenarios(scenario_ids)


__all__ = [
    "accept_standards_response",
    "discover_standards_response",
    "extract_standards_candidates_response",
    "run_golden_scenarios_response",
    "standards_review_packet_response",
]
