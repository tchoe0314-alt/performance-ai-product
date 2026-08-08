from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
import json
import os
import time

from backend.application.production_env_validator_v1 import validate_production_env_v1
from backend.services.backup_restore import hosted_backup_evidence


RC1_READINESS_VERSION = "civora_rc1_readiness_v1"

TECHNICAL_EVIDENCE_KEYS = (
    "backend_regression",
    "frontend_quality",
    "security_dependency",
    "data_lifecycle",
    "backup_restore_local",
    "engineering_real_files",
    "browser_core",
    "browser_cross_device_accessibility",
    "long_session_concurrency",
    "hosted_end_to_end",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _first(source: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = str(source.get(name) or "").strip()
        if value:
            return value
    return ""


def _record(code: str, message: str, *, owner: str = "", evidence_key: str = "") -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "owner": owner,
        "evidence_key": evidence_key,
    }


def _load_json(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not Path(path).is_file():
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_rc1_readiness_report(
    *,
    evidence_manifest: Optional[Dict[str, Any]] = None,
    env: Optional[Mapping[str, str]] = None,
    revision: str = "",
) -> Dict[str, Any]:
    source_env = dict(os.environ if env is None else env)
    manifest = deepcopy(evidence_manifest or {})
    evidence = dict(manifest.get("evidence") or {})
    technical_blockers = []
    for key in TECHNICAL_EVIDENCE_KEYS:
        record = dict(evidence.get(key) or {})
        if not record:
            technical_blockers.append(
                _record(
                    f"{key}_evidence_missing",
                    f"Required RC1 evidence is missing: {key.replace('_', ' ')}.",
                    evidence_key=key,
                )
            )
        elif not bool(record.get("success")):
            technical_blockers.append(
                _record(
                    f"{key}_failed",
                    str(record.get("message") or f"RC1 evidence failed: {key.replace('_', ' ')}."),
                    evidence_key=key,
                )
            )

    support_contact = _first(source_env, "CIVORA_SUPPORT_CONTACT_URL", "CIVORA_SUPPORT_EMAIL", "CIVORA_SUPPORT_CONTACT")
    bug_report = _first(source_env, "CIVORA_BUG_REPORT_URL", "CIVORA_BUG_REPORT_FORM_URL")
    operational_checks = {
        "support_contact": bool(support_contact),
        "bug_report": bool(bug_report),
        "escalation_owner": bool(_first(source_env, "CIVORA_ESCALATION_CONTACT")),
        "monitoring_owner": bool(_first(source_env, "CIVORA_MONITORING_OWNER")),
        "rollback_owner": bool(_first(source_env, "CIVORA_ROLLBACK_OWNER")),
    }
    operational_blockers = [
        _record(f"{key}_missing", f"Controlled release needs a configured {key.replace('_', ' ')}.")
        for key, ready in operational_checks.items()
        if not ready
    ]
    backup = hosted_backup_evidence(source_env)
    if backup["status"] != "ready":
        operational_blockers.append(
            _record(
                "hosted_backup_restore_not_proven",
                "Controlled release needs provider backup retention evidence and a completed hosted restore drill.",
                owner=_first(source_env, "CIVORA_DATABASE_BACKUP_OWNER"),
            )
        )

    human_checks = {
        "engineer_uat": bool(_first(source_env, "CIVORA_ENGINEER_UAT_EVIDENCE_URL"))
        and bool(_first(source_env, "CIVORA_ENGINEER_UAT_OWNER")),
        "pilot_terms": _truthy(source_env.get("CIVORA_PILOT_TERMS_READY")),
        "terms_privacy": _truthy(source_env.get("CIVORA_TERMS_PRIVACY_READY")),
        "data_retention_policy": _truthy(source_env.get("CIVORA_DATA_RETENTION_POLICY_READY")),
    }
    human_blockers = [
        _record(
            f"{key}_not_accepted",
            f"Human or counsel acceptance is still required for {key.replace('_', ' ')}; automation cannot approve it.",
        )
        for key, ready in human_checks.items()
        if not ready
    ]

    billing_checks = {
        "billing_legal_docs": _truthy(source_env.get("CIVORA_BILLING_LEGAL_DOCS_READY")),
        "billing_provider": str(source_env.get("CIVORA_BILLING_PROVIDER") or "none").strip().lower()
        not in {"", "none", "disabled", "off"},
        "real_charging_explicit": _truthy(source_env.get("CIVORA_ENABLE_REAL_CHARGING")),
    }
    billing_blockers = [
        _record(f"{key}_not_ready", f"Paid charging remains disabled until {key.replace('_', ' ')} is ready.")
        for key, ready in billing_checks.items()
        if not ready
    ]

    technical_ready = not technical_blockers
    operations_ready = not operational_blockers
    human_ready = not human_blockers
    controlled_release_allowed = technical_ready and operations_ready and human_ready
    paid_release_allowed = controlled_release_allowed and not billing_blockers
    env_report = validate_production_env_v1(source_env, deployment_target=str(source_env.get("CIVORA_DEPLOYMENT_TARGET") or ""))
    product_mode = str(source_env.get("CIVORA_PRODUCT_MODE") or "private_alpha").strip().lower()
    public_beta_allowed = (
        controlled_release_allowed
        and product_mode in {"public_beta", "production"}
        and _truthy(source_env.get("CIVORA_PUBLIC_BETA_RELEASE_GATES_GREEN"))
        and not env_report["release_blocked"]
    )
    return {
        "version": RC1_READINESS_VERSION,
        "generated_at": time.time(),
        "revision": revision or str(manifest.get("revision") or ""),
        "technical_rc_ready": technical_ready,
        "controlled_invite_only_release_allowed": controlled_release_allowed,
        "controlled_paid_release_allowed": paid_release_allowed,
        "public_beta_allowed": public_beta_allowed,
        "construction_ready": False,
        "evidence": evidence,
        "technical_blockers": technical_blockers,
        "operational_checks": operational_checks,
        "operational_blockers": operational_blockers,
        "hosted_backup_evidence": backup,
        "human_checks": human_checks,
        "human_blockers": human_blockers,
        "billing_checks": billing_checks,
        "billing_blockers": billing_blockers,
        "production_env_report": env_report,
        "next_action": (
            "Fix failed or missing technical evidence."
            if technical_blockers
            else "Configure and prove hosted support, monitoring, rollback, and backup recovery."
            if operational_blockers
            else "Complete named engineer UAT and counsel/business acceptance."
            if human_blockers
            else "RC1 is cleared for the recorded controlled invite-only scope."
        ),
        "truth_label": "RC1 automation can prove technical evidence and configuration presence. It cannot self-approve engineer UAT, legal terms, billing, provider backups, or public release ownership.",
    }


def run_rc1_readiness(
    *,
    evidence_manifest_path: Optional[Path],
    output_path: Path,
    env: Optional[Mapping[str, str]] = None,
    revision: str = "",
) -> Dict[str, Any]:
    report = build_rc1_readiness_report(
        evidence_manifest=_load_json(evidence_manifest_path),
        env=env,
        revision=revision,
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


__all__ = [
    "RC1_READINESS_VERSION",
    "TECHNICAL_EVIDENCE_KEYS",
    "build_rc1_readiness_report",
    "run_rc1_readiness",
]
