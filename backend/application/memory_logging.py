from __future__ import annotations

import logging
import os
import resource
from typing import Any, Dict


LOGGER = logging.getLogger("uvicorn.error")


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def current_rss_mb() -> float:
    """Return current resident memory when available.

    Linux exposes current RSS in /proc/self/status. Fall back to ru_maxrss,
    which is peak RSS rather than current RSS, when /proc is unavailable.
    """
    status_path = "/proc/self/status"
    if os.path.exists(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1]) / 1024.0
        except OSError:
            pass

    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if os.uname().sysname == "Darwin":
        rss = rss / 1024.0
    return rss / 1024.0


def peak_rss_mb() -> float:
    """Return peak resident memory for diagnostics."""
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if os.uname().sysname == "Darwin":
        rss = rss / 1024.0
    return rss / 1024.0


def log_memory(event: str, **fields: Any) -> None:
    payload = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    suffix = f" {payload}" if payload else ""
    LOGGER.info("MEMORY %s rss_mb=%.1f%s", event, current_rss_mb(), suffix)


def runtime_monitoring_snapshot(*, job_queue: Dict[str, Any] | None = None) -> Dict[str, Any]:
    current = round(current_rss_mb(), 1)
    peak = round(peak_rss_mb(), 1)
    warn_mb = _env_float("CIVORA_MEMORY_WARN_MB", 512.0)
    critical_mb = _env_float("CIVORA_MEMORY_CRITICAL_MB", 1024.0)
    warnings = []
    status = "healthy"
    if peak >= critical_mb or current >= critical_mb:
        status = "critical"
        warnings.append("memory_critical_threshold_exceeded")
    elif peak >= warn_mb or current >= warn_mb:
        status = "warning"
        warnings.append("memory_warning_threshold_exceeded")

    queue = dict(job_queue or {})
    queue_monitoring = dict(queue.get("monitoring") or {})
    if str(queue_monitoring.get("status") or "").lower() in {"warning", "critical", "degraded"}:
        status = "degraded" if status == "healthy" else status
        warnings.append("job_queue_monitoring_not_healthy")

    return {
        "status": status,
        "rss_mb": current,
        "peak_rss_mb": peak,
        "memory_warn_mb": warn_mb,
        "memory_critical_mb": critical_mb,
        "warnings": warnings,
        "job_queue": queue_monitoring,
        "truth_label": "Runtime monitoring reports operational risk only; it does not prove construction readiness.",
    }
