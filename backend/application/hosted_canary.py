from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse
import time

from backend.application.hosted_operational_evidence import build_hosted_operational_evidence


HOSTED_CANARY_VERSION = "civora_hosted_canary_v1"


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _record(code: str, message: str, *, area: str) -> Dict[str, str]:
    return {"code": code, "message": message, "area": area}


def _revision_matches(expected: str, actual: str) -> bool:
    expected_clean = str(expected or "").strip().lower()
    actual_clean = str(actual or "").strip().lower()
    if len(expected_clean) < 7 or len(actual_clean) < 7:
        return False
    return expected_clean.startswith(actual_clean) or actual_clean.startswith(expected_clean)


def build_hosted_canary_report(
    *,
    frontend_url: str,
    api_base_url: str,
    expected_revision: str,
    expected_product_mode: str,
    frontend: Mapping[str, Any],
    health: Mapping[str, Any],
    auth_status: Mapping[str, Any],
    cors: Mapping[str, Any],
    unauthenticated_runtime_status: int,
    unauthenticated_production_env_status: int,
    authenticated_runtime: Optional[Mapping[str, Any]] = None,
    require_authenticated: bool = False,
) -> Dict[str, Any]:
    frontend_record = _mapping(frontend)
    health_record = _mapping(health)
    auth_record = _mapping(auth_status)
    cors_record = _mapping(cors)
    deployment = _mapping(health_record.get("deployment"))
    support = _mapping(health_record.get("support"))
    recovery = _mapping(health_record.get("recovery"))
    storage_pool = _mapping(health_record.get("storage_pool"))
    operational_summary = _mapping(health_record.get("operational_summary"))
    actual_revision = str(deployment.get("commit_sha") or deployment.get("build_version") or "").strip()
    frontend_origin = f"{urlparse(frontend_url).scheme}://{urlparse(frontend_url).netloc}"

    public_blockers = []
    if int(frontend_record.get("status") or 0) not in range(200, 400):
        public_blockers.append(_record("frontend_unreachable", "The hosted frontend did not return a successful response.", area="frontend"))
    if not bool(frontend_record.get("body_has_civora")):
        public_blockers.append(_record("frontend_shell_missing", "The hosted frontend response did not contain the Civora application shell marker.", area="frontend"))
    if health_record.get("success") is not True:
        public_blockers.append(_record("health_not_ready", "The hosted health endpoint did not return success.", area="health"))
    if str(health_record.get("storage") or "").lower() != "postgres":
        public_blockers.append(_record("hosted_storage_not_postgres", "The hosted health endpoint did not prove PostgreSQL storage.", area="storage"))
    if storage_pool and str(storage_pool.get("status") or "").lower() != "available":
        public_blockers.append(_record("storage_pool_not_available", "The hosted database pool is not available.", area="storage"))
    if int(storage_pool.get("requests_errors") or 0) > 0:
        public_blockers.append(_record("storage_pool_request_errors", "The hosted database pool reports request errors.", area="storage"))
    if str(health_record.get("product_mode") or "").lower() != str(expected_product_mode or "").lower():
        public_blockers.append(_record("product_mode_mismatch", "The hosted product mode does not match the canary expectation.", area="release"))
    if not _revision_matches(expected_revision, actual_revision):
        public_blockers.append(_record("hosted_revision_mismatch", "The hosted backend revision does not match the canary revision.", area="revision"))
    if deployment.get("backend_status") != "online" or deployment.get("api_status") != "configured":
        public_blockers.append(_record("deployment_not_ready", "The hosted deployment summary is not online and configured.", area="deployment"))
    if operational_summary.get("ready_for_ui") is not True:
        public_blockers.append(_record("ui_backend_not_ready", "The hosted backend does not report itself ready for the UI.", area="deployment"))
    if not bool(support.get("support_contact_configured")) or not bool(support.get("bug_report_configured")):
        public_blockers.append(_record("support_paths_missing", "Hosted support and bug-report paths are not both configured.", area="support"))
    if str(recovery.get("status") or "").lower() != "ready" or not bool(recovery.get("provider_backups_enabled")):
        public_blockers.append(_record("recovery_not_ready", "Hosted recovery evidence is not ready.", area="recovery"))
    if auth_record.get("success") is not True or auth_record.get("auth_enabled") is not True:
        public_blockers.append(_record("auth_status_not_ready", "Hosted authentication status is not ready.", area="auth"))
    if int(unauthenticated_runtime_status or 0) != 401 or int(unauthenticated_production_env_status or 0) != 401:
        public_blockers.append(_record("debug_routes_not_protected", "Hosted debug routes did not reject unauthenticated access.", area="security"))
    if int(cors_record.get("status") or 0) != 200 or str(cors_record.get("allow_origin") or "") != frontend_origin:
        public_blockers.append(_record("cors_not_ready", "Hosted CORS did not approve the exact frontend origin.", area="cors"))

    authenticated_report: Dict[str, Any] = {}
    authenticated_blockers = []
    authenticated_status = "not_configured"
    if authenticated_runtime is not None:
        authenticated_report = build_hosted_operational_evidence(
            health=health_record,
            runtime=authenticated_runtime,
            expected_revision=expected_revision,
            base_url=api_base_url,
        )
        authenticated_blockers = list(authenticated_report.get("runtime_blockers") or []) + list(authenticated_report.get("operational_blockers") or [])
        authenticated_status = "ready" if not authenticated_blockers else "blocked"
    elif require_authenticated:
        authenticated_blockers.append(_record("authenticated_canary_missing", "Authenticated canary evidence was required but credentials were not configured.", area="auth"))
        authenticated_status = "blocked"

    success = not public_blockers and not authenticated_blockers
    return {
        "version": HOSTED_CANARY_VERSION,
        "generated_at": time.time(),
        "frontend_url": str(frontend_url or "").rstrip("/"),
        "api_base_url": str(api_base_url or "").rstrip("/"),
        "expected_revision": str(expected_revision or ""),
        "hosted_revision": actual_revision,
        "revision_matches": _revision_matches(expected_revision, actual_revision),
        "expected_product_mode": str(expected_product_mode or ""),
        "hosted_product_mode": str(health_record.get("product_mode") or ""),
        "success": success,
        "status": "ready" if success else "blocked",
        "public_checks_ready": not public_blockers,
        "authenticated_checks_status": authenticated_status,
        "public_blockers": public_blockers,
        "authenticated_blockers": authenticated_blockers,
        "checks": {
            "frontend_status": int(frontend_record.get("status") or 0),
            "frontend_shell_present": bool(frontend_record.get("body_has_civora")),
            "health_success": health_record.get("success") is True,
            "storage": str(health_record.get("storage") or ""),
            "storage_pool_status": str(storage_pool.get("status") or ""),
            "support_contact_configured": bool(support.get("support_contact_configured")),
            "bug_report_configured": bool(support.get("bug_report_configured")),
            "recovery_status": str(recovery.get("status") or ""),
            "auth_enabled": auth_record.get("auth_enabled") is True,
            "runtime_auth_guard_status": int(unauthenticated_runtime_status or 0),
            "production_env_auth_guard_status": int(unauthenticated_production_env_status or 0),
            "cors_status": int(cors_record.get("status") or 0),
            "cors_allow_origin": str(cors_record.get("allow_origin") or ""),
        },
        "authenticated_evidence": {
            "captured": authenticated_runtime is not None,
            "status": authenticated_status,
            "hosted_runtime_ready": authenticated_report.get("hosted_runtime_ready") if authenticated_report else None,
            "operational_configuration_ready": authenticated_report.get("operational_configuration_ready") if authenticated_report else None,
            "checks": authenticated_report.get("checks") if authenticated_report else {},
        },
        "construction_ready": False,
        "public_beta_allowed": False,
        "truth_label": "The hosted canary proves selected availability, security, revision, recovery, and optional authenticated runtime facts. It does not approve public launch, billing, professional review, or construction use.",
    }


__all__ = ["HOSTED_CANARY_VERSION", "build_hosted_canary_report"]
