from __future__ import annotations

from backend.services.billing import BillingConfig, build_billing_status, paid_pilot_access_gate, usage_gate


def _config(**overrides):
    base = {
        "paid_pilot_mode": False,
        "charging_enabled": False,
        "legal_docs_ready": False,
        "terms_url": "",
        "privacy_url": "",
        "order_form_url": "",
        "provider_name": "none",
        "plan_code": "pilot_manual",
        "plan_label": "Paid pilot manual billing",
        "monthly_project_limit": 5,
        "monthly_export_limit": 20,
        "monthly_job_limit": 40,
        "pilot_user_ids": [],
        "pilot_emails": [],
    }
    base.update(overrides)
    return BillingConfig(**base)


def test_billing_status_disabled_by_default_blocks_real_charging() -> None:
    status = build_billing_status(user={"user_id": "user_1", "email": "pilot@example.com"}, config=_config())

    assert status["version"] == "billing_status_v1"
    assert status["paid_pilot_mode"] is False
    assert status["operational_state"] == "blocked"
    assert status["real_charging_enabled"] is False
    assert status["charging_guard"]["real_charging_allowed"] is False
    assert "Real charging is blocked" in status["charging_guard"]["user_safe_message"]
    assert status["provider"]["configured"] is False
    assert "legal_business_docs_missing" in status["blocked_reasons"]
    assert "paid_pilot_mode_disabled" in status["blocked_reasons"]
    assert status["invoice"]["status"] == "placeholder"


def test_paid_pilot_mode_without_legal_docs_stays_blocked() -> None:
    status = build_billing_status(
        user={"user_id": "user_1", "email": "pilot@example.com"},
        config=_config(paid_pilot_mode=True, legal_docs_ready=False, pilot_emails=["pilot@example.com"]),
    )

    assert status["status"] == "blocked"
    assert status["operational_state"] == "blocked"
    assert status["plan"]["access"] == "pilot"
    assert status["real_charging_enabled"] is False
    assert "legal_business_docs_missing" in status["blocked_reasons"]


def test_real_charging_flag_alone_is_not_enough() -> None:
    status = build_billing_status(
        user={"user_id": "user_1", "email": "pilot@example.com"},
        config=_config(
            paid_pilot_mode=True,
            charging_enabled=True,
            legal_docs_ready=True,
            provider_name="none",
            pilot_emails=["pilot@example.com"],
        ),
    )

    assert status["charging_config_requested"] is True
    assert status["real_charging_enabled"] is False
    assert status["operational_state"] == "blocked"
    assert "provider_disabled" in status["blocked_reasons"]


def test_usage_gate_is_hook_only_for_private_alpha() -> None:
    gate = usage_gate(action="orchestrate", user={"user_id": "user_1"}, config=_config())

    assert gate["allowed"] is True
    assert gate["mode"] == "hook_only"
    assert gate["billing_status_v1"]["usage_limits"]["enforcement"] == "hook_only"


def test_paid_pilot_access_gate_requires_docs_and_enrollment() -> None:
    gate = paid_pilot_access_gate(
        user={"user_id": "user_1", "email": "pilot@example.com"},
        config=_config(
            paid_pilot_mode=True,
            legal_docs_ready=True,
            pilot_emails=["pilot@example.com"],
        ),
    )

    assert gate["allowed"] is False
    assert "provider_disabled" in gate["reasons"]
