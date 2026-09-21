from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from backend.planning.gis_provider_registry import builtin_provider_records, provider_packs_for_location


SOURCE_INFRASTRUCTURE_EVIDENCE_VERSION = "source_infrastructure_evidence_v1"
TARGET_MARKETS = (
    "Gretna, NE",
    "Omaha, NE",
    "Austin, TX",
    "Atlanta, GA",
    "Dallas, TX",
    "Houston, TX",
    "Denver, CO",
    "Phoenix, AZ",
    "Charlotte, NC",
)


def build_source_infrastructure_evidence(*, rights_review: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    packs = []
    providers: Dict[str, Dict[str, Any]] = {}
    known_gaps = []
    for address in TARGET_MARKETS:
        for pack in provider_packs_for_location(address=address):
            packs.append(deepcopy(pack))
            for provider in pack.get("providers") or []:
                providers[str(provider.get("id") or provider.get("service_url"))] = deepcopy(provider)
            known_gaps.extend(deepcopy(pack.get("known_gaps") or []))
    for provider in builtin_provider_records():
        providers[str(provider.get("id") or provider.get("service_url"))] = deepcopy(provider)
    provider_rows = list(providers.values())
    queryable = [row for row in provider_rows if row.get("queryable") is True and row.get("service_url")]
    traceable = all(
        row.get("id")
        and row.get("name")
        and row.get("source_type")
        and row.get("service_url")
        and row.get("truth_label")
        and row.get("review_required") is True
        for row in provider_rows
    )
    gaps_truthful = bool(known_gaps) and all(
        gap.get("source_type") and gap.get("status") and gap.get("message")
        for gap in known_gaps
    )
    return {
        "version": SOURCE_INFRASTRUCTURE_EVIDENCE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_count": len({pack.get("pack_id") for pack in packs}),
        "provider_count": len(provider_rows),
        "queryable_source_count": len(queryable),
        "source_types": sorted({str(row.get("source_type")) for row in provider_rows if row.get("source_type")}),
        "source_traceability_verified": traceable,
        "missing_source_behavior_verified": gaps_truthful,
        "provider_packs": packs,
        "providers": provider_rows,
        "known_gaps": known_gaps,
        "rights_review": deepcopy(dict(rights_review or {})),
        "review_required": True,
        "survey_backed": False,
        "truth_label": "This inventory proves configured source records and explicit coverage gaps. It does not prove provider uptime, license rights, survey control, or acceptance for a particular project.",
    }


__all__ = ["SOURCE_INFRASTRUCTURE_EVIDENCE_VERSION", "TARGET_MARKETS", "build_source_infrastructure_evidence"]
