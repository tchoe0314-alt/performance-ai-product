from __future__ import annotations

from typing import Any, Dict

from backend.planning.alpha_monitoring import build_alpha_monitoring_report


REVIEW_ONLY_PRODUCT_MODES = {"development", "private_alpha", "public_beta", "alpha", "review", "review_only"}


def _normalize_product_mode(value: str) -> str:
    normalized = str(value or "private_alpha").strip().lower().replace("-", "_") or "private_alpha"
    aliases = {
        "alpha": "private_alpha",
        "review": "private_alpha",
        "review_only": "private_alpha",
        "beta": "public_beta",
    }
    return aliases.get(normalized, normalized)


def _readiness_mode_for_product_mode(product_mode: str) -> str:
    normalized = _normalize_product_mode(product_mode)
    if normalized in {"development", "local_dev", "dev"}:
        return "local_dev"
    if normalized == "production":
        return "production"
    return "private_alpha_review"


def health_response(
    *,
    app_name: str,
    app_version: str,
    product_mode: str,
    user_count: int,
    storage: str = "sqlite",
    runtime_monitoring: Dict[str, Any] | None = None,
    release_guard: Dict[str, Any] | None = None,
    deployment: Dict[str, Any] | None = None,
    support: Dict[str, Any] | None = None,
) -> Dict[str, object]:
    normalized_mode = _normalize_product_mode(product_mode)
    normalized_storage = str(storage or "sqlite").strip().lower() or "sqlite"
    review_only = normalized_mode in REVIEW_ONLY_PRODUCT_MODES
    monitoring = runtime_monitoring or {}
    release = release_guard or {}
    monitoring_status = str(monitoring.get("status") or "healthy").strip().lower() or "healthy"
    readiness_mode = _readiness_mode_for_product_mode(normalized_mode)
    alpha_monitoring_report = build_alpha_monitoring_report(monitoring, readiness_mode=readiness_mode)
    alpha_ready = str(alpha_monitoring_report.get("readiness") or "").strip().lower() == "ready"
    if not monitoring:
        operational_status = "blocked"
    elif not alpha_ready:
        operational_status = "blocked"
    elif monitoring_status in {"healthy", "ok"}:
        operational_status = "healthy"
    else:
        operational_status = "degraded"
    queue_evidence = alpha_monitoring_report.get("job_queue_monitoring_evidence") or {}
    queue_status = str(queue_evidence.get("status") or monitoring.get("job_queue", {}).get("status") or "unknown")
    monitoring_queue = monitoring.get("job_queue", {}) if isinstance(monitoring.get("job_queue", {}), dict) else {}
    queue_counts = monitoring_queue.get("counts") if isinstance(monitoring_queue.get("counts"), dict) else {}
    deployment_meta = deployment or {}
    support_meta = support or {}
    build_version = str(deployment_meta.get("build_version") or app_version or "").strip()
    last_deploy_time = str(deployment_meta.get("last_deploy_time") or "").strip()
    api_base_url = str(deployment_meta.get("api_base_url") or "").strip()
    frontend_status = str(deployment_meta.get("frontend_status") or "unknown").strip() or "unknown"
    backend_status = "online" if operational_status in {"healthy", "degraded"} else "down"
    api_status = "configured" if api_base_url else "missing_url"
    build_status = "known" if build_version else "unknown"
    service_messages = []
    if backend_status == "down":
        service_messages.append("Backend health checks are blocked. Some workspace actions may be unavailable.")
    if queue_status not in {"healthy", "ready", "ok"}:
        service_messages.append("Background jobs may be delayed. Queued runs can be retried when service recovers.")
    if not api_base_url:
        service_messages.append("The API base URL is not published in health metadata.")
    if not service_messages:
        service_messages.append("All visible deployment checks are reachable.")
    return {
        "success": True,
        "message": "Civora AI backend is running.",
        "app_name": app_name,
        "version": app_version,
        "product_mode": normalized_mode,
        "launch_stage": "private_alpha" if review_only else normalized_mode,
        "review_only": review_only,
        "auth_enabled": True,
        "storage": normalized_storage,
        "user_count": int(user_count),
        "deployment": {
            "frontend_status": frontend_status,
            "backend_status": backend_status,
            "api_status": api_status,
            "api_base_url": api_base_url,
            "auth_status": "enabled",
            "queue_status": queue_status,
            "build_status": build_status,
            "build_version": build_version,
            "commit_sha": str(deployment_meta.get("commit_sha") or "").strip(),
            "commit_ref": str(deployment_meta.get("commit_ref") or "").strip(),
            "environment": str(deployment_meta.get("environment") or "").strip(),
            "provider": str(deployment_meta.get("provider") or "").strip(),
            "last_deploy_time": last_deploy_time,
            "user_safe_messages": service_messages,
        },
        "support": {
            "support_contact_configured": bool(support_meta.get("support_contact_configured")),
            "support_contact": str(support_meta.get("support_contact") or "support@civora.ai").strip(),
            "bug_report_configured": bool(support_meta.get("bug_report_configured")),
            "bug_report_url": str(support_meta.get("bug_report_url") or "").strip(),
            "escalation_configured": bool(support_meta.get("escalation_configured")),
            "escalation_contact": str(support_meta.get("escalation_contact") or "").strip(),
            "user_safe_message": str(
                support_meta.get("user_safe_message")
                or "Use the support contact or bug report path for pilot issues; stop relying on affected outputs when source, review, or export status is unclear."
            ),
        },
        "alpha_review_guard": {
            "review_only": review_only,
            "construction_release_enabled": bool(release.get("construction_release_enabled")) and not review_only,
            "construction_release_blocked": review_only or bool(release.get("construction_release_blocked")),
            "truth_label": (
                "Private alpha is review-only; construction release remains blocked."
                if review_only
                else "Production mode may release only through construction package and professional review gates."
            ),
        },
        "monitoring": monitoring,
        "alpha_monitoring_report": alpha_monitoring_report,
        "operational_summary": {
            "status": operational_status,
            "mode": normalized_mode,
            "readiness_mode": readiness_mode,
            "launch_stage": "private_alpha" if review_only else normalized_mode,
            "review_only": review_only,
            "auth_enabled": True,
            "storage": normalized_storage,
            "user_count": int(user_count),
            "monitoring_status": monitoring_status,
            "alpha_monitoring_status": str(alpha_monitoring_report.get("readiness") or ""),
            "alpha_monitoring_blocker_count": len(alpha_monitoring_report.get("blockers") or []),
            "job_queue_evidence_status": str(queue_evidence.get("status") or ""),
            "queue_status": queue_status,
            "queue_counts": queue_counts,
            "queued_count": queue_evidence.get("pending_count", monitoring_queue.get("queued_count", queue_counts.get("queued"))),
            "running_count": monitoring_queue.get("running_count", queue_counts.get("running", 0)),
            "stale_job_count": monitoring_queue.get("stale_job_count", queue_evidence.get("timeout_count", 0)),
            "job_queue_monitoring_ready": bool(queue_evidence.get("queue_monitoring_ready")),
            "async_jobs_enabled": bool(queue_evidence.get("async_jobs_enabled", True)),
            "timeout_count": queue_evidence.get("timeout_count"),
            "failed_count": queue_evidence.get("failed_count"),
            "failed_recent_count": queue_evidence.get("failed_recent_count"),
            "historical_failed_count": queue_evidence.get("historical_failed_count"),
            "pending_count": queue_evidence.get("pending_count"),
            "construction_release_enabled": bool(release.get("construction_release_enabled")) and not review_only,
            "construction_release_blocked": review_only or bool(release.get("construction_release_blocked")),
            "ready_for_ui": operational_status in {"healthy", "degraded"},
            "ready_for_public_launch": False,
            "public_beta_blocked": True,
            "public_beta_block_reason": "Public beta remains blocked until support, bug intake, billing/legal, monitoring, rollback, production storage/queue, and release gates are green.",
        },
    }
