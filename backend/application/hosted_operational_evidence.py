from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping


HOSTED_OPERATIONAL_EVIDENCE_VERSION = "civora_hosted_operational_evidence_v1"


def _record(code: str, message: str, *, area: str) -> Dict[str, str]:
    return {"code": code, "message": message, "area": area}


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _integer(*values: Any) -> int:
    for value in values:
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _revision_matches(expected: str, actual: str) -> bool:
    expected_clean = str(expected or "").strip().lower()
    actual_clean = str(actual or "").strip().lower()
    if len(expected_clean) < 7 or len(actual_clean) < 7:
        return False
    return expected_clean.startswith(actual_clean) or actual_clean.startswith(expected_clean)


def build_hosted_operational_evidence(
    *,
    health: Mapping[str, Any],
    runtime: Mapping[str, Any],
    expected_revision: str,
    base_url: str,
) -> Dict[str, Any]:
    health_payload = _mapping(health)
    runtime_payload = _mapping(runtime)
    deployment = _mapping(health_payload.get("deployment"))
    support = _mapping(health_payload.get("support"))
    recovery = _mapping(runtime_payload.get("recovery") or health_payload.get("recovery"))
    monitoring = _mapping(runtime_payload.get("monitoring"))
    process = _mapping(monitoring.get("process"))
    runtime_queue = _mapping(runtime_payload.get("job_queue"))
    queue_monitoring = _mapping(runtime_queue.get("monitoring"))
    monitoring_queue = _mapping(monitoring.get("job_queue"))
    alpha_report = _mapping(runtime_payload.get("alpha_monitoring_report"))
    alpha_queue = _mapping(alpha_report.get("job_queue_monitoring_evidence"))

    actual_revision = str(deployment.get("commit_sha") or deployment.get("build_version") or "").strip()
    queue_status = str(
        alpha_queue.get("status")
        or queue_monitoring.get("status")
        or monitoring_queue.get("status")
        or "missing"
    ).strip().lower()
    queued_count = _integer(
        queue_monitoring.get("queued_count"),
        queue_monitoring.get("pending_count"),
        monitoring_queue.get("queued_count"),
        runtime_queue.get("queued_count"),
    )
    running_count = _integer(
        queue_monitoring.get("running_count"),
        monitoring_queue.get("running_count"),
        runtime_queue.get("running_count"),
    )
    failed_recent_count = _integer(
        queue_monitoring.get("failed_recent_count"),
        monitoring_queue.get("failed_recent_count"),
        runtime_queue.get("failed_recent_count"),
    )
    stale_count = _integer(
        queue_monitoring.get("stale_job_count"),
        queue_monitoring.get("timeout_count"),
        monitoring_queue.get("stale_job_count"),
        runtime_queue.get("stale_job_count"),
    )

    runtime_blockers = []
    if health_payload.get("success") is not True:
        runtime_blockers.append(_record("hosted_health_not_ready", "Hosted health did not return a successful liveness record.", area="health"))
    if str(runtime_payload.get("status") or "").lower() != "ok":
        runtime_blockers.append(_record("authenticated_runtime_not_ready", "Authenticated runtime evidence did not return status ok.", area="auth_runtime"))
    if not str(expected_revision or "").strip():
        runtime_blockers.append(_record("expected_revision_missing", "Exact-revision hosted evidence requires an expected Git revision.", area="revision"))
    elif not _revision_matches(expected_revision, actual_revision):
        runtime_blockers.append(_record("hosted_revision_mismatch", "The hosted backend revision does not match the revision under review.", area="revision"))
    if str(health_payload.get("storage") or runtime_payload.get("storage_kind") or "").lower() != "postgres":
        runtime_blockers.append(_record("hosted_storage_not_postgres", "Hosted evidence did not prove PostgreSQL storage.", area="storage"))
    if queue_status not in {"ready", "healthy"}:
        runtime_blockers.append(_record("queue_monitoring_not_ready", "Authenticated queue monitoring is not ready.", area="queue"))
    if failed_recent_count:
        runtime_blockers.append(_record("queue_recent_failures", "The hosted queue has recent failed jobs that need investigation.", area="queue"))
    if stale_count:
        runtime_blockers.append(_record("queue_stale_jobs", "The hosted queue has stale or timed-out jobs.", area="queue"))
    if process and process.get("previous_shutdown_clean") is False:
        runtime_blockers.append(_record("previous_shutdown_unclean", "The previous hosted process did not record a clean shutdown.", area="process"))

    operational_blockers = []
    if not bool(support.get("support_contact_configured")):
        operational_blockers.append(_record("support_contact_missing", "A user-visible support contact is not configured on the hosted backend.", area="support"))
    if not bool(support.get("bug_report_configured")):
        operational_blockers.append(_record("bug_report_path_missing", "A user-visible bug report path is not configured on the hosted backend.", area="support"))
    if str(recovery.get("status") or "").lower() != "ready" or not bool(recovery.get("provider_backups_enabled")):
        operational_blockers.append(_record("provider_backup_restore_not_proven", "Hosted provider backups and a restore drill are not proven.", area="recovery"))
    if not bool(recovery.get("owner_configured")):
        operational_blockers.append(_record("backup_owner_missing", "A hosted database backup owner is not configured.", area="recovery"))
    if not bool(recovery.get("evidence_url_configured")):
        operational_blockers.append(_record("backup_evidence_url_missing", "Hosted backup evidence is not attached.", area="recovery"))

    runtime_ready = not runtime_blockers
    operations_ready = not operational_blockers
    return {
        "version": HOSTED_OPERATIONAL_EVIDENCE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": str(base_url or "").rstrip("/"),
        "expected_revision": str(expected_revision or "").strip(),
        "hosted_revision": actual_revision,
        "revision_matches": _revision_matches(expected_revision, actual_revision),
        "hosted_runtime_ready": runtime_ready,
        "operational_configuration_ready": operations_ready,
        "success": runtime_ready and operations_ready,
        "status": "ready" if runtime_ready and operations_ready else "blocked",
        "runtime_blockers": runtime_blockers,
        "operational_blockers": operational_blockers,
        "checks": {
            "health_reachable": health_payload.get("success") is True,
            "authenticated_runtime_reachable": str(runtime_payload.get("status") or "").lower() == "ok",
            "storage_kind": str(health_payload.get("storage") or runtime_payload.get("storage_kind") or ""),
            "support_contact_configured": bool(support.get("support_contact_configured")),
            "bug_report_configured": bool(support.get("bug_report_configured")),
            "queue_monitoring_status": queue_status,
            "queued_count": queued_count,
            "running_count": running_count,
            "failed_recent_count": failed_recent_count,
            "stale_job_count": stale_count,
            "previous_shutdown_clean": process.get("previous_shutdown_clean") if process else None,
            "provider_backups_enabled": bool(recovery.get("provider_backups_enabled")),
            "backup_owner_configured": bool(recovery.get("owner_configured")),
            "backup_evidence_url_configured": bool(recovery.get("evidence_url_configured")),
            "restore_drill_at": str(recovery.get("restore_drill_at") or ""),
            "backup_retention_days": recovery.get("retention_days"),
        },
        "construction_ready": False,
        "truth_label": "This report proves selected hosted runtime and configuration facts without storing credentials. It cannot self-approve provider recovery, human ownership, legal terms, billing, professional review, or construction use.",
    }


__all__ = ["HOSTED_OPERATIONAL_EVIDENCE_VERSION", "build_hosted_operational_evidence"]
