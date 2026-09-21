from __future__ import annotations

from backend.application.major_change_confirmation import (
    MAJOR_CHANGE_POLICIES,
    build_confirmation_evidence,
    build_major_change_preview,
    confirm_major_change,
)
from backend.application.source_infrastructure_evidence import build_source_infrastructure_evidence


def test_source_inventory_records_queryable_sources_and_truthful_gaps_without_claiming_rights() -> None:
    evidence = build_source_infrastructure_evidence()
    assert evidence["market_count"] >= 8
    assert evidence["queryable_source_count"] > 0
    assert evidence["source_traceability_verified"] is True
    assert evidence["missing_source_behavior_verified"] is True
    assert evidence["known_gaps"]
    assert evidence["rights_review"] == {}
    assert evidence["survey_backed"] is False


def test_every_major_change_is_previewed_blocked_and_reversible_until_exact_confirmation() -> None:
    for action in MAJOR_CHANGE_POLICIES:
        preview = build_major_change_preview(action, target_ids=["object-1"], affected_systems=["grading"])
        assert preview["status"] == "awaiting_confirmation"
        assert preview["can_apply"] is False
        assert preview["policy"]["preview_required"] is True
        assert preview["policy"]["reversible"] is True
        assert preview["history_preserved"] is True
        assert confirm_major_change(preview, confirmation_token="yes")["can_apply"] is False
        confirmed = confirm_major_change(preview, confirmation_token="CONFIRM CHANGE")
        assert confirmed["can_apply"] is True
        assert confirmed["status"] == "confirmed"
        assert confirmed["confirmation_token_recorded"] is False


def test_confirmation_evidence_stays_blocked_until_tests_are_explicitly_recorded() -> None:
    assert build_confirmation_evidence(tests_passed=False)["tests_passed"] is False
    evidence = build_confirmation_evidence(tests_passed=True)
    assert evidence["tests_passed"] is True
    assert set(evidence["covered_actions"]) == set(MAJOR_CHANGE_POLICIES)
    assert evidence["integration_complete"] is False
    assert evidence["browser_verification_complete"] is False


def test_confirmation_evidence_requires_every_action_to_be_integrated_and_browser_verified() -> None:
    actions = list(MAJOR_CHANGE_POLICIES)
    evidence = build_confirmation_evidence(
        tests_passed=True,
        integrated_actions=actions,
        browser_verified_actions=actions,
    )
    assert evidence["integration_complete"] is True
    assert evidence["browser_verification_complete"] is True
