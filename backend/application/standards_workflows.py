from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from backend.planning.golden_runner import run_golden_scenarios
from backend.planning.standards_discovery import (
    accept_standards_rules,
    build_standards_review_packet,
    controlled_single_source_lookup,
    discover_standards_sources,
    fetch_and_extract_rule_candidates,
    fetch_live_standards_source_candidate,
    review_candidate_standards,
    standards_live_source_policy,
    standards_pack_from_acceptance,
    standards_project_evidence_from_acceptance,
    trusted_standards_source_allowlist,
)
from backend.planning.standards_package import build_standards_package


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
    accepted_by: str = "",
) -> Dict[str, Any]:
    acceptance = accept_standards_rules(review_packet, accepted_rule_ids, edits=edits, accepted_by=accepted_by)
    evidence = standards_project_evidence_from_acceptance(
        acceptance,
        review_packet=review_packet,
        company_standards=company_standards,
    )
    evidence["design_standards"] = standards_pack_from_acceptance(acceptance)
    evidence["standards_package"] = build_standards_package(evidence)
    return evidence


def review_candidate_standards_response(
    *,
    review_packet: Dict[str, Any],
    review_actions: Iterable[Dict[str, Any]],
    reviewer_id: str = "",
    approval_metadata: Optional[Dict[str, Any]] = None,
    company_standards: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    acceptance = review_candidate_standards(
        review_packet,
        review_actions,
        reviewer_id=reviewer_id,
        approval_metadata=approval_metadata,
    )
    evidence = standards_project_evidence_from_acceptance(
        acceptance,
        review_packet=review_packet,
        company_standards=company_standards,
    )
    evidence["design_standards"] = standards_pack_from_acceptance(acceptance)
    evidence["standards_package"] = build_standards_package(evidence)
    return evidence


def extract_standards_candidates_response(*, source_url: str, source_id: str = "official_source") -> Dict[str, Any]:
    return fetch_and_extract_rule_candidates(source_url, source_id=source_id)


def standards_live_source_policy_response() -> Dict[str, Any]:
    policy = standards_live_source_policy()
    policy["trusted_allowlist"] = trusted_standards_source_allowlist()
    return policy


def fetch_live_standards_source_candidate_response(
    *,
    source_url: str,
    source_id: str = "live_source",
    source_type: str = "",
    jurisdiction: Optional[Dict[str, Any]] = None,
    agency: str = "",
    document_title: str = "",
    effective_date: str = "",
    version: str = "",
    allow_network_fetch: bool = False,
    source_owner: str = "",
    uploaded_by: str = "",
    allowlist_entries: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return fetch_live_standards_source_candidate(
        source_url=source_url,
        source_id=source_id,
        source_type=source_type,
        jurisdiction=jurisdiction,
        agency=agency,
        document_title=document_title,
        effective_date=effective_date,
        version=version,
        allow_network_fetch=allow_network_fetch,
        source_owner=source_owner,
        uploaded_by=uploaded_by,
        allowlist_entries=allowlist_entries,
    )


def controlled_single_source_lookup_response(
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
    source_owner: str = "",
    uploaded_by: str = "",
    allowlist_entries: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return controlled_single_source_lookup(
        source_url=source_url,
        source_id=source_id,
        jurisdiction=jurisdiction,
        agency=agency,
        source_type=source_type,
        discipline=discipline,
        operator_authorized=operator_authorized,
        document_title=document_title,
        effective_date=effective_date,
        version=version,
        source_owner=source_owner,
        uploaded_by=uploaded_by,
        allowlist_entries=allowlist_entries,
    )


def run_golden_scenarios_response(*, scenario_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    return run_golden_scenarios(scenario_ids)


__all__ = [
    "accept_standards_response",
    "controlled_single_source_lookup_response",
    "discover_standards_response",
    "extract_standards_candidates_response",
    "fetch_live_standards_source_candidate_response",
    "review_candidate_standards_response",
    "run_golden_scenarios_response",
    "standards_live_source_policy_response",
    "standards_review_packet_response",
]
