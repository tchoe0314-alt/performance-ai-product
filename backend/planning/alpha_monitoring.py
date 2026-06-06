from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List

from .common import readiness_issue_explanations, safe_dict, safe_float, safe_int, safe_list, safe_str


def _env_float(name: str, default: float) -> float:
    raw = safe_str(os.getenv(name))
    if not raw:
        return float(default)
    return safe_float(raw, default)


def _thresholds(overrides: Dict[str, Any] | None = None) -> Dict[str, float]:
    rec = safe_dict(overrides)
    return {
        "max_rss_mb": safe_float(rec.get("max_rss_mb"), _env_float("CIVORA_ALPHA_MAX_RSS_MB", 512.0)),
        "max_peak_rss_mb": safe_float(rec.get("max_peak_rss_mb"), _env_float("CIVORA_ALPHA_MAX_PEAK_RSS_MB", 768.0)),
        "max_recent_start_count": safe_float(rec.get("max_recent_start_count"), _env_float("CIVORA_ALPHA_MAX_RECENT_START_COUNT", 2.0)),
        "max_failed_recent_count": safe_float(rec.get("max_failed_recent_count"), _env_float("CIVORA_ALPHA_MAX_FAILED_RECENT_COUNT", 0.0)),
        "max_stale_job_count": safe_float(rec.get("max_stale_job_count"), _env_float("CIVORA_ALPHA_MAX_STALE_JOB_COUNT", 0.0)),
        "max_oldest_active_age_sec": safe_float(rec.get("max_oldest_active_age_sec"), _env_float("CIVORA_ALPHA_MAX_ACTIVE_JOB_AGE_SEC", 900.0)),
    }


def _readiness_mode(value: Any = "") -> str:
    text = safe_str(value or "private_alpha_review").lower().replace("-", "_")
    aliases = {
        "dev": "local_dev",
        "local": "local_dev",
        "alpha": "private_alpha_review",
        "private_alpha": "private_alpha_review",
        "review": "private_alpha_review",
        "review_only": "private_alpha_review",
        "prod": "production",
    }
    return aliases.get(text, text if text in {"local_dev", "private_alpha_review", "production"} else "private_alpha_review")


def readiness_mode_policy() -> Dict[str, Any]:
    return {
        "version": "readiness_mode_policy_v1",
        "modes": {
            "local_dev": {
                "queue_monitoring_requirement": "Queue evidence may be unavailable_local when no live queue is configured; this does not clear private-alpha readiness.",
                "construction_release_allowed": False,
            },
            "private_alpha_review": {
                "queue_monitoring_requirement": "Async jobs require real queue monitoring evidence with job types and pending/failed/timeout counts.",
                "construction_release_allowed": False,
            },
            "production": {
                "queue_monitoring_requirement": "Async jobs require live runtime queue monitoring evidence with job types, counts, and worker/runtime source confidence.",
                "construction_release_allowed": False,
            },
        },
    }


def _blocker(field: str, reason: str, *, value: Any = None, limit: Any = None) -> Dict[str, Any]:
    rec = {
        "area": "monitoring",
        "field": field,
        "reason": reason,
        "message": reason,
        "why_needed": reason,
        "suggested_next_action": "Fix the operational issue, rerun the backend smoke/soak check, and attach a fresh alpha monitoring report.",
        "severity": "blocker",
    }
    if value is not None:
        rec["value"] = value
    if limit is not None:
        rec["limit"] = limit
    return rec


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _queue_count(queue: Dict[str, Any], key: str, fallback_key: str = "") -> int | None:
    if key in queue:
        return safe_int(queue.get(key), 0)
    if fallback_key and fallback_key in queue:
        return safe_int(queue.get(fallback_key), 0)
    counts = safe_dict(queue.get("counts"))
    if fallback_key and fallback_key in counts:
        return safe_int(counts.get(fallback_key), 0)
    return None


def build_job_queue_monitoring_evidence(
    job_queue: Dict[str, Any] | None = None,
    *,
    monitoring_source: str = "",
    last_check_at: str = "",
    readiness_mode: str = "private_alpha_review",
    async_jobs_enabled: bool = True,
) -> Dict[str, Any]:
    queue = safe_dict(job_queue)
    monitoring = safe_dict(queue.get("monitoring")) or queue
    mode = _readiness_mode(readiness_mode)
    monitored_job_types = [
        safe_str(item)
        for item in safe_list(
            queue.get("registered_handlers")
            or queue.get("monitored_job_types")
            or monitoring.get("monitored_job_types")
        )
        if safe_str(item)
    ]
    pending_count = _queue_count(monitoring, "pending_count", "queued")
    if pending_count is None:
        pending_count = _queue_count(monitoring, "queued_count")
    failed_count = _queue_count(monitoring, "failed_count", "failed")
    if failed_count is None:
        failed_count = _queue_count(monitoring, "failed_recent_count")
    timeout_count = _queue_count(monitoring, "timeout_count", "stale_job_count")
    queue_system_present = bool(queue or monitoring)
    source = safe_str(monitoring_source or queue.get("monitoring_source") or monitoring.get("monitoring_source"))
    if not source:
        source = "runtime_monitoring.job_queue" if queue_system_present else "missing"
    status = safe_str(monitoring.get("status"), "missing" if not queue_system_present else "healthy").lower()
    blockers: List[Dict[str, Any]] = []
    applicability = "required" if async_jobs_enabled else "not_applicable"
    not_applicable_reason = ""
    if not async_jobs_enabled:
        not_applicable_reason = "Async jobs are disabled or not configured for this readiness sample."
    elif mode == "local_dev" and not queue_system_present:
        applicability = "unavailable_local"
        not_applicable_reason = "Local dev sampling did not connect to a live job queue or runtime endpoint."
    if async_jobs_enabled and not queue_system_present and applicability != "unavailable_local":
        blockers.append(_blocker("job_queue", f"{mode} monitoring needs queue monitoring evidence."))
    if async_jobs_enabled and queue_system_present and status not in {"healthy", "ok"}:
        blockers.append(_blocker("job_queue_status", "Job queue monitoring is not healthy.", value=status))
    if async_jobs_enabled and queue_system_present and not monitored_job_types:
        blockers.append(_blocker("monitored_job_types", "Job queue monitoring needs explicit monitored job types."))
    if async_jobs_enabled and applicability == "required" and pending_count is None:
        blockers.append(_blocker("pending_count", "Job queue monitoring needs pending job count evidence."))
    if async_jobs_enabled and applicability == "required" and failed_count is None:
        blockers.append(_blocker("failed_count", "Job queue monitoring needs failed job count evidence."))
    if async_jobs_enabled and applicability == "required" and timeout_count is None:
        blockers.append(_blocker("timeout_count", "Job queue monitoring needs timeout or stale job count evidence."))

    live_runtime = bool(queue.get("registered_handlers") or queue.get("alive_workers") is not None)
    confidence = "missing"
    if queue_system_present:
        confidence = "live_runtime" if live_runtime else "runtime_snapshot"
    if mode == "production" and async_jobs_enabled and confidence != "live_runtime":
        blockers.append(
            _blocker(
                "monitoring_confidence",
                "Production queue monitoring needs live runtime evidence, not only an aggregated snapshot.",
                value=confidence,
            )
        )
    queue_monitoring_ready = bool(not blockers and (queue_system_present or applicability == "not_applicable"))
    alpha_ready = bool(mode == "private_alpha_review" and queue_system_present and not blockers)
    mode_ready = bool(queue_monitoring_ready and mode != "local_dev")
    return {
        "version": "job_queue_monitoring_evidence_v1",
        "readiness_mode": mode,
        "queue_system_present": queue_system_present,
        "async_jobs_enabled": bool(async_jobs_enabled),
        "applicability": applicability,
        "not_applicable_reason": not_applicable_reason,
        "monitored_job_types": monitored_job_types,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "timeout_count": timeout_count,
        "last_check_at": safe_str(last_check_at) or _utc_now(),
        "monitoring_source": source,
        "confidence": confidence,
        "status": "ready" if mode_ready else ("unavailable_local" if applicability == "unavailable_local" else "blocked"),
        "blockers": blockers,
        "queue_monitoring_ready": queue_monitoring_ready,
        "mode_ready": mode_ready,
        "alpha_ready": alpha_ready,
        "how_to_clear_blocker": (
            "Run the readiness audit against a live runtime endpoint with JobQueueService.runtime_stats() exposed at /api/debug/runtime, "
            "or disable async jobs explicitly for the target mode and document why queue monitoring is not applicable."
        ),
        "truth_label": "Job queue monitoring evidence reports operational queue health only; it does not prove engineering or construction readiness.",
    }


def build_alpha_monitoring_report(
    runtime_monitoring: Dict[str, Any] | None = None,
    *,
    thresholds: Dict[str, Any] | None = None,
    readiness_mode: str = "private_alpha_review",
    async_jobs_enabled: bool = True,
) -> Dict[str, Any]:
    runtime = safe_dict(runtime_monitoring)
    mode = _readiness_mode(readiness_mode or runtime.get("readiness_mode") or runtime.get("deployment_mode"))
    limits = _thresholds(thresholds)
    blockers: List[Dict[str, Any]] = []
    warnings = [safe_str(item) for item in safe_list(runtime.get("warnings")) if safe_str(item)]
    status = safe_str(runtime.get("status"), "missing").lower()
    if not runtime:
        blockers.append(_blocker("runtime_monitoring", "Alpha monitoring needs a runtime monitoring snapshot."))
    elif status not in {"healthy", "ok"}:
        blockers.append(_blocker("runtime_status", f"Runtime monitoring is {status}, not healthy.", value=status))

    rss = safe_float(runtime.get("rss_mb"), 0.0)
    peak = safe_float(runtime.get("peak_rss_mb"), 0.0)
    if rss > limits["max_rss_mb"]:
        blockers.append(_blocker("rss_mb", "Current memory exceeds the alpha threshold.", value=rss, limit=limits["max_rss_mb"]))
    if peak > limits["max_peak_rss_mb"]:
        blockers.append(_blocker("peak_rss_mb", "Peak memory exceeds the alpha threshold.", value=peak, limit=limits["max_peak_rss_mb"]))

    queue = safe_dict(runtime.get("job_queue"))
    queue_evidence = safe_dict(runtime.get("job_queue_monitoring_evidence"))
    if not queue_evidence:
        queue_evidence = build_job_queue_monitoring_evidence(
            queue,
            readiness_mode=mode,
            async_jobs_enabled=async_jobs_enabled,
        )
    elif safe_str(queue_evidence.get("readiness_mode")) != mode:
        queue_evidence = build_job_queue_monitoring_evidence(
            queue or queue_evidence,
            monitoring_source=queue_evidence.get("monitoring_source"),
            last_check_at=queue_evidence.get("last_check_at"),
            readiness_mode=mode,
            async_jobs_enabled=async_jobs_enabled,
        )
    if not (mode == "local_dev" and queue_evidence.get("applicability") == "unavailable_local"):
        blockers.extend([safe_dict(item) for item in safe_list(queue_evidence.get("blockers")) if safe_dict(item)])
    if queue:
        failed_recent = safe_int(queue.get("failed_recent_count"), safe_int(queue_evidence.get("failed_count"), 0))
        stale_count = safe_int(queue.get("stale_job_count"), safe_int(queue_evidence.get("timeout_count"), 0))
        oldest_age = safe_float(queue.get("oldest_active_age_sec"), 0.0)
        if failed_recent > limits["max_failed_recent_count"]:
            blockers.append(_blocker("failed_recent_count", "Recent failed jobs exceed the alpha threshold.", value=failed_recent, limit=limits["max_failed_recent_count"]))
        if stale_count > limits["max_stale_job_count"]:
            blockers.append(_blocker("stale_job_count", "Stale/timed-out jobs exceed the alpha threshold.", value=stale_count, limit=limits["max_stale_job_count"]))
        if oldest_age > limits["max_oldest_active_age_sec"]:
            blockers.append(_blocker("oldest_active_age_sec", "Oldest active job age exceeds the alpha threshold.", value=oldest_age, limit=limits["max_oldest_active_age_sec"]))

    process = safe_dict(runtime.get("process"))
    if process:
        if safe_str(process.get("status"), "healthy").lower() not in {"healthy", "ok"}:
            blockers.append(_blocker("process_status", "Process monitoring is not healthy.", value=process.get("status")))
        starts = safe_int(process.get("recent_start_count"), 0)
        if starts > limits["max_recent_start_count"]:
            blockers.append(_blocker("recent_start_count", "Recent process start count exceeds the alpha restart threshold.", value=starts, limit=limits["max_recent_start_count"]))
    else:
        blockers.append(_blocker("process", "Alpha monitoring needs process restart/crash-loop evidence."))

    report_status = "blocked" if blockers else "ready"
    return {
        "version": "alpha_monitoring_report_v1",
        "readiness_mode": mode,
        "readiness_mode_policy": readiness_mode_policy(),
        "status": "healthy" if report_status == "ready" else "blocked",
        "readiness": report_status,
        "success": report_status == "ready",
        "thresholds": limits,
        "runtime_monitoring": deepcopy(runtime),
        "job_queue_monitoring_evidence": deepcopy(queue_evidence),
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warnings": warnings,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "truth_label": "Alpha monitoring proves operational threshold status only; it does not prove engineering or construction readiness.",
    }


__all__ = ["build_alpha_monitoring_report", "build_job_queue_monitoring_evidence", "readiness_mode_policy"]
