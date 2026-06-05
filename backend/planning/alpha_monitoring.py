from __future__ import annotations

import os
from copy import deepcopy
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


def build_alpha_monitoring_report(
    runtime_monitoring: Dict[str, Any] | None = None,
    *,
    thresholds: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    runtime = safe_dict(runtime_monitoring)
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
    if queue:
        if safe_str(queue.get("status"), "healthy").lower() not in {"healthy", "ok"}:
            blockers.append(_blocker("job_queue_status", "Job queue monitoring is not healthy.", value=queue.get("status")))
        failed_recent = safe_int(queue.get("failed_recent_count"), 0)
        stale_count = safe_int(queue.get("stale_job_count"), 0)
        oldest_age = safe_float(queue.get("oldest_active_age_sec"), 0.0)
        if failed_recent > limits["max_failed_recent_count"]:
            blockers.append(_blocker("failed_recent_count", "Recent failed jobs exceed the alpha threshold.", value=failed_recent, limit=limits["max_failed_recent_count"]))
        if stale_count > limits["max_stale_job_count"]:
            blockers.append(_blocker("stale_job_count", "Stale/timed-out jobs exceed the alpha threshold.", value=stale_count, limit=limits["max_stale_job_count"]))
        if oldest_age > limits["max_oldest_active_age_sec"]:
            blockers.append(_blocker("oldest_active_age_sec", "Oldest active job age exceeds the alpha threshold.", value=oldest_age, limit=limits["max_oldest_active_age_sec"]))
    else:
        blockers.append(_blocker("job_queue", "Alpha monitoring needs queue monitoring evidence."))

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
        "status": "healthy" if report_status == "ready" else "blocked",
        "readiness": report_status,
        "success": report_status == "ready",
        "thresholds": limits,
        "runtime_monitoring": deepcopy(runtime),
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "warnings": warnings,
        "truth_label": "Alpha monitoring proves operational threshold status only; it does not prove engineering or construction readiness.",
    }


__all__ = ["build_alpha_monitoring_report"]
