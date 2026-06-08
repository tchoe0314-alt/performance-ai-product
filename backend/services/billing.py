from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional, Protocol


BILLING_STATUS_VERSION = "billing_status_v1"
BLOCKED_LEGAL_DOCS = "legal_business_docs_missing"
BLOCKED_PROVIDER_DISABLED = "provider_disabled"
BLOCKED_PILOT_MODE_DISABLED = "paid_pilot_mode_disabled"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        value = int(str(os.getenv(name) or "").strip())
    except Exception:
        return int(default)
    return value if value >= 0 else int(default)


def _clean_list(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


class BillingProvider(Protocol):
    provider_name: str

    def configured(self) -> bool:
        ...

    def status(self) -> Dict[str, Any]:
        ...

    def invoice_placeholder(self) -> Dict[str, Any]:
        ...


@dataclass(frozen=True)
class DisabledBillingProvider:
    provider_name: str = "none"

    def configured(self) -> bool:
        return False

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "configured": False,
            "charging_enabled": False,
            "status": "disabled",
        }

    def invoice_placeholder(self) -> Dict[str, Any]:
        return {
            "status": "placeholder",
            "provider": self.provider_name,
            "message": "No payment provider is configured. Invoices and payment collection remain manual placeholders.",
        }


@dataclass(frozen=True)
class StripeBillingProvider:
    publishable_key: str
    secret_key: str
    price_id: str
    webhook_secret: str

    provider_name: str = "stripe"

    def configured(self) -> bool:
        return bool(self.publishable_key and self.secret_key and self.price_id and self.webhook_secret)

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "configured": self.configured(),
            "charging_enabled": False,
            "status": "configured_disabled",
            "missing": [
                name
                for name, value in {
                    "STRIPE_PUBLISHABLE_KEY": self.publishable_key,
                    "STRIPE_SECRET_KEY": self.secret_key,
                    "STRIPE_PILOT_PRICE_ID": self.price_id,
                    "STRIPE_WEBHOOK_SECRET": self.webhook_secret,
                }.items()
                if not value
            ],
        }

    def invoice_placeholder(self) -> Dict[str, Any]:
        return {
            "status": "provider_ready_placeholder" if self.configured() else "placeholder",
            "provider": self.provider_name,
            "message": "Stripe keys are only used for status readiness here. Checkout, subscriptions, and charges are not active by default.",
        }


@dataclass(frozen=True)
class BillingConfig:
    paid_pilot_mode: bool
    charging_enabled: bool
    legal_docs_ready: bool
    terms_url: str
    privacy_url: str
    order_form_url: str
    provider_name: str
    plan_code: str
    plan_label: str
    monthly_project_limit: int
    monthly_export_limit: int
    monthly_job_limit: int
    pilot_user_ids: List[str]
    pilot_emails: List[str]

    @classmethod
    def from_env(cls) -> "BillingConfig":
        return cls(
            paid_pilot_mode=_env_flag("CIVORA_PAID_PILOT_MODE", False),
            charging_enabled=_env_flag("CIVORA_ENABLE_REAL_CHARGING", False),
            legal_docs_ready=_env_flag("CIVORA_BILLING_LEGAL_DOCS_READY", False),
            terms_url=str(os.getenv("CIVORA_TERMS_URL") or "").strip(),
            privacy_url=str(os.getenv("CIVORA_PRIVACY_URL") or "").strip(),
            order_form_url=str(os.getenv("CIVORA_ORDER_FORM_URL") or "").strip(),
            provider_name=str(os.getenv("CIVORA_BILLING_PROVIDER") or "none").strip().lower(),
            plan_code=str(os.getenv("CIVORA_PILOT_PLAN_CODE") or "pilot_manual").strip(),
            plan_label=str(os.getenv("CIVORA_PILOT_PLAN_LABEL") or "Paid pilot manual billing").strip(),
            monthly_project_limit=_env_int("CIVORA_PILOT_MONTHLY_PROJECT_LIMIT", 5),
            monthly_export_limit=_env_int("CIVORA_PILOT_MONTHLY_EXPORT_LIMIT", 20),
            monthly_job_limit=_env_int("CIVORA_PILOT_MONTHLY_JOB_LIMIT", 40),
            pilot_user_ids=_clean_list(str(os.getenv("CIVORA_PAID_PILOT_USER_IDS") or "")),
            pilot_emails=[item.lower() for item in _clean_list(str(os.getenv("CIVORA_PAID_PILOT_EMAILS") or ""))],
        )


def provider_from_env(config: Optional[BillingConfig] = None) -> BillingProvider:
    config = config or BillingConfig.from_env()
    if config.provider_name == "stripe":
        return StripeBillingProvider(
            publishable_key=str(os.getenv("STRIPE_PUBLISHABLE_KEY") or "").strip(),
            secret_key=str(os.getenv("STRIPE_SECRET_KEY") or "").strip(),
            price_id=str(os.getenv("STRIPE_PILOT_PRICE_ID") or "").strip(),
            webhook_secret=str(os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip(),
        )
    return DisabledBillingProvider()


def build_billing_status(
    *,
    user: Optional[Dict[str, Any]] = None,
    config: Optional[BillingConfig] = None,
    provider: Optional[BillingProvider] = None,
) -> Dict[str, Any]:
    config = config or BillingConfig.from_env()
    provider = provider or provider_from_env(config)
    user = dict(user or {})
    user_id = str(user.get("user_id") or "").strip()
    email = str(user.get("email") or "").strip().lower()
    is_pilot_user = bool(
        config.paid_pilot_mode
        and (
            not config.pilot_user_ids
            and not config.pilot_emails
            or user_id in config.pilot_user_ids
            or email in config.pilot_emails
        )
    )

    blocked_reasons: List[str] = []
    if not config.legal_docs_ready:
        blocked_reasons.append(BLOCKED_LEGAL_DOCS)
    if not config.paid_pilot_mode:
        blocked_reasons.append(BLOCKED_PILOT_MODE_DISABLED)
    if not provider.configured():
        blocked_reasons.append(BLOCKED_PROVIDER_DISABLED)

    real_charging_allowed = bool(config.charging_enabled and config.legal_docs_ready and provider.configured())
    status = "active_manual" if is_pilot_user and config.legal_docs_ready else "blocked"
    if not is_pilot_user and config.paid_pilot_mode:
        status = "not_enrolled"
    if not config.paid_pilot_mode:
        status = "disabled"

    return {
        "version": BILLING_STATUS_VERSION,
        "success": True,
        "status": status,
        "paid_pilot_mode": config.paid_pilot_mode,
        "real_charging_enabled": real_charging_allowed,
        "charging_config_requested": config.charging_enabled,
        "legal_business_docs_ready": config.legal_docs_ready,
        "blocked": bool(blocked_reasons) or not is_pilot_user,
        "blocked_reasons": blocked_reasons if is_pilot_user or not config.paid_pilot_mode else ["user_not_enrolled_for_paid_pilot"],
        "plan": {
            "code": config.plan_code,
            "label": config.plan_label,
            "access": "pilot" if is_pilot_user else "private_alpha",
            "gates": {
                "planner": "allowed",
                "jobs": "allowed",
                "exports": "allowed_with_usage_hooks",
                "billing_admin": "visible_status_only",
            },
        },
        "usage_limits": {
            "monthly_projects": config.monthly_project_limit,
            "monthly_exports": config.monthly_export_limit,
            "monthly_jobs": config.monthly_job_limit,
            "enforcement": "hook_only",
        },
        "provider": provider.status(),
        "invoice": provider.invoice_placeholder(),
        "payment": {
            "status": "disabled" if not real_charging_allowed else "configured_but_not_started",
            "message": "No real charges are created by this API without explicit charging configuration and legal/business readiness.",
        },
        "legal": {
            "terms_url": config.terms_url,
            "privacy_url": config.privacy_url,
            "order_form_url": config.order_form_url,
            "required": ["terms", "privacy", "paid pilot order form"],
        },
    }


def usage_gate(
    *,
    action: str,
    user: Optional[Dict[str, Any]] = None,
    config: Optional[BillingConfig] = None,
) -> Dict[str, Any]:
    status = build_billing_status(user=user, config=config)
    return {
        "action": action,
        "allowed": True,
        "mode": "hook_only",
        "billing_status_v1": status,
        "reasons": [],
    }


def paid_pilot_access_gate(
    *,
    user: Optional[Dict[str, Any]] = None,
    config: Optional[BillingConfig] = None,
) -> Dict[str, Any]:
    status = build_billing_status(user=user, config=config)
    allowed = bool(status["paid_pilot_mode"] and not status["blocked_reasons"] and status["plan"]["access"] == "pilot")
    return {
        "allowed": allowed,
        "billing_status_v1": status,
        "reasons": [] if allowed else list(status.get("blocked_reasons") or []),
    }


__all__ = [
    "BILLING_STATUS_VERSION",
    "BillingConfig",
    "build_billing_status",
    "paid_pilot_access_gate",
    "provider_from_env",
    "usage_gate",
]
