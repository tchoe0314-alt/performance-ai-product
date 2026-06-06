from __future__ import annotations

import json
import logging
import os
import resource
import time
from pathlib import Path
from typing import Any, Dict

from backend.planning.alpha_monitoring import build_job_queue_monitoring_evidence


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


def _monitor_file(state_dir: str | Path | None) -> Path | None:
    override = str(os.getenv("CIVORA_RUNTIME_MONITOR_FILE") or "").strip()
    if override:
        return Path(override)
    if state_dir is None:
        return None
    return Path(state_dir) / "runtime_monitoring.json"


def _load_runtime_state(path: Path | None) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_runtime_state(path: Path | None, state: Dict[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True)
    except Exception:
        LOGGER.warning("RUNTIME_MONITOR write_failed path=%s", path, exc_info=True)


def _merge_monitoring_status(current: str, incoming: str) -> str:
    normalized = str(incoming or "healthy").strip().lower()
    if normalized == "ok":
        normalized = "healthy"
    order = {"healthy": 0, "warning": 1, "degraded": 2, "critical": 3}
    if order.get(normalized, 0) > order.get(current, 0):
        return normalized
    return current


def record_process_start(
    *,
    state_dir: str | Path | None,
    start_time: float | None = None,
    instance_id: str | None = None,
) -> Dict[str, Any]:
    now = float(start_time or time.time())
    path = _monitor_file(state_dir)
    state = _load_runtime_state(path)
    window = _env_float("CIVORA_RESTART_WINDOW_SECONDS", 900.0)
    previous_clean_shutdown = bool(state.get("clean_shutdown", True))
    starts = [
        item
        for item in state.get("starts", [])
        if isinstance(item, dict) and now - float(item.get("started_at") or now) <= window
    ]
    starts.append(
        {
            "instance_id": str(instance_id or ""),
            "started_at": now,
            "previous_clean_shutdown": previous_clean_shutdown,
        }
    )
    state.update(
        {
            "active_instance_id": str(instance_id or ""),
            "clean_shutdown": False,
            "last_start_at": now,
            "starts": starts,
        }
    )
    _write_runtime_state(path, state)
    return runtime_process_monitoring_snapshot(
        state_dir=state_dir,
        start_time=now,
        now=now,
        instance_id=instance_id,
    )


def record_process_shutdown(
    *,
    state_dir: str | Path | None,
    instance_id: str | None = None,
    now: float | None = None,
) -> Dict[str, Any]:
    timestamp = float(now or time.time())
    path = _monitor_file(state_dir)
    state = _load_runtime_state(path)
    state.update(
        {
            "active_instance_id": str(instance_id or state.get("active_instance_id") or ""),
            "clean_shutdown": True,
            "last_shutdown_at": timestamp,
        }
    )
    _write_runtime_state(path, state)
    return runtime_process_monitoring_snapshot(
        state_dir=state_dir,
        start_time=float(state.get("last_start_at") or timestamp),
        now=timestamp,
        instance_id=instance_id,
    )


def runtime_process_monitoring_snapshot(
    *,
    state_dir: str | Path | None,
    start_time: float | None = None,
    now: float | None = None,
    instance_id: str | None = None,
) -> Dict[str, Any]:
    timestamp = float(now or time.time())
    path = _monitor_file(state_dir)
    state = _load_runtime_state(path)
    window = _env_float("CIVORA_RESTART_WINDOW_SECONDS", 900.0)
    warn_count = int(max(1.0, _env_float("CIVORA_RESTART_WARNING_COUNT", 3.0)))
    critical_count = int(max(float(warn_count), _env_float("CIVORA_RESTART_CRITICAL_COUNT", 5.0)))
    starts = [
        item
        for item in state.get("starts", [])
        if isinstance(item, dict) and timestamp - float(item.get("started_at") or timestamp) <= window
    ]
    previous_shutdown_clean = True
    if starts:
        previous_shutdown_clean = bool(starts[-1].get("previous_clean_shutdown", True))
    recent_start_count = len(starts)
    warnings = []
    status = "healthy"
    if recent_start_count >= critical_count:
        status = "critical"
        warnings.append("process_restart_critical_threshold_exceeded")
    elif recent_start_count >= warn_count:
        status = "warning"
        warnings.append("process_restart_warning_threshold_exceeded")
    if not previous_shutdown_clean:
        if status == "healthy":
            status = "warning"
        warnings.append("previous_process_did_not_shutdown_cleanly")

    active_start = float(start_time or state.get("last_start_at") or timestamp)
    return {
        "status": status,
        "instance_id": str(instance_id or state.get("active_instance_id") or ""),
        "uptime_seconds": round(max(0.0, timestamp - active_start), 3),
        "restart_window_seconds": window,
        "recent_start_count": recent_start_count,
        "restart_warning_count": warn_count,
        "restart_critical_count": critical_count,
        "previous_shutdown_clean": previous_shutdown_clean,
        "last_start_at": state.get("last_start_at"),
        "last_shutdown_at": state.get("last_shutdown_at"),
        "state_file": str(path) if path else "",
        "warnings": warnings,
        "truth_label": "Process monitoring flags crash/restart risk; it must be paired with deploy logs for root cause.",
    }


def runtime_monitoring_snapshot(
    *,
    job_queue: Dict[str, Any] | None = None,
    process: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
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
    if queue_monitoring and queue.get("registered_handlers"):
        queue_monitoring["monitored_job_types"] = [
            str(item)
            for item in queue.get("registered_handlers", [])
            if str(item)
        ]
    queue_evidence = build_job_queue_monitoring_evidence(
        queue,
        monitoring_source="runtime_monitoring_snapshot.job_queue",
    )
    if str(queue_monitoring.get("status") or "").lower() in {"warning", "critical", "degraded"}:
        status = _merge_monitoring_status(status, str(queue_monitoring.get("status")))
        warnings.append("job_queue_monitoring_not_healthy")
    process_monitoring = dict(process or {})
    process_status = str(process_monitoring.get("status") or "").lower()
    if process_status in {"warning", "critical", "degraded"}:
        status = _merge_monitoring_status(status, process_status)
        warnings.append("process_monitoring_not_healthy")

    return {
        "status": status,
        "rss_mb": current,
        "peak_rss_mb": peak,
        "memory_warn_mb": warn_mb,
        "memory_critical_mb": critical_mb,
        "warnings": warnings,
        "job_queue": queue_monitoring,
        "job_queue_monitoring_evidence": queue_evidence,
        "process": process_monitoring,
        "truth_label": "Runtime monitoring reports operational risk only; it does not prove construction readiness.",
    }
