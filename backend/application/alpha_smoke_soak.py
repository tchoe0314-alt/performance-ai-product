from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.request import Request, urlopen

from backend.application.memory_logging import runtime_monitoring_snapshot, runtime_process_monitoring_snapshot
from backend.planning.alpha_monitoring import build_alpha_monitoring_report, build_job_queue_monitoring_evidence
from backend.planning.common import readiness_issue_explanations, safe_dict, safe_float, safe_int, safe_list, safe_str


RuntimeSampleFn = Callable[[], Dict[str, Any]]

_LOCAL_PATH_FIELDS = {"state_file", "storage_dir"}
_SENSITIVE_PREFIX_FIELDS = {"mapbox_token_prefix"}


def _status_rank(value: Any) -> int:
    text = safe_str(value, "healthy").lower()
    return {"healthy": 0, "ok": 0, "warning": 1, "degraded": 2, "blocked": 3, "critical": 4}.get(text, 3)


def _worst_status(values: Iterable[Any]) -> str:
    statuses = [safe_str(item, "healthy").lower() for item in values]
    if not statuses:
        return "missing"
    return max(statuses, key=_status_rank)


def _max_from_samples(samples: List[Dict[str, Any]], key: str) -> float:
    return max([safe_float(safe_dict(item.get("monitoring")).get(key), 0.0) for item in samples] or [0.0])


def _observed_int_max(records: Iterable[Dict[str, Any]], key: str) -> int | None:
    values = [safe_int(record.get(key), 0) for record in records if key in record]
    return max(values) if values else None


def _observed_float_max(records: Iterable[Dict[str, Any]], key: str) -> float | None:
    values = [safe_float(record.get(key), 0.0) for record in records if key in record]
    return max(values) if values else None


def _aggregate_runtime(
    samples: List[Dict[str, Any]],
    *,
    readiness_mode: str = "private_alpha_review",
    async_jobs_enabled: bool = True,
) -> Dict[str, Any]:
    monitorings = [safe_dict(item.get("monitoring")) for item in samples]
    queues = [safe_dict(item.get("job_queue") or safe_dict(item.get("monitoring")).get("job_queue")) for item in samples]
    queue_monitorings = [safe_dict(queue.get("monitoring")) or queue for queue in queues]
    processes = [safe_dict(safe_dict(item.get("monitoring")).get("process")) for item in samples]
    monitored_job_types = sorted(
        {
            safe_str(job_type)
            for queue in queues
            for job_type in safe_list(
                queue.get("registered_handlers")
                or queue.get("monitored_job_types")
                or safe_dict(queue.get("monitoring")).get("monitored_job_types")
            )
            if safe_str(job_type)
        }
    )
    live_registered_handlers = sorted(
        {
            safe_str(job_type)
            for queue in queues
            for job_type in safe_list(queue.get("registered_handlers"))
            if safe_str(job_type)
        }
    )
    observed_queue_monitorings = [queue for queue in queue_monitorings if queue]
    queue_monitoring = {
        "status": _worst_status(queue.get("status") for queue in queue_monitorings if queue),
        "monitored_job_types": monitored_job_types,
        "sample_count": len([queue for queue in queues if queue]),
    }
    observed_counts = {
        "failed_recent_count": _observed_int_max(observed_queue_monitorings, "failed_recent_count"),
        "stale_job_count": _observed_int_max(observed_queue_monitorings, "stale_job_count"),
        "oldest_active_age_sec": _observed_float_max(observed_queue_monitorings, "oldest_active_age_sec"),
        "queued_count": _observed_int_max(observed_queue_monitorings, "queued_count"),
    }
    queue_monitoring.update({key: value for key, value in observed_counts.items() if value is not None})
    alive_workers = _observed_int_max(queues, "alive_workers")
    if alive_workers is not None:
        queue_monitoring["alive_workers"] = alive_workers
    if live_registered_handlers:
        queue_monitoring["registered_handlers"] = live_registered_handlers
    process_monitoring = {
        "status": _worst_status(process.get("status") for process in processes if process),
        "previous_shutdown_clean": all(bool(process.get("previous_shutdown_clean", True)) for process in processes if process),
        "sample_count": len([process for process in processes if process]),
    }
    recent_start_count = _observed_int_max([process for process in processes if process], "recent_start_count")
    if recent_start_count is not None:
        process_monitoring["recent_start_count"] = recent_start_count
    if queue_monitoring["sample_count"] <= 0:
        queue_monitoring = {}
    if process_monitoring["sample_count"] <= 0:
        process_monitoring = {}
    queue_evidence = build_job_queue_monitoring_evidence(
        queue_monitoring,
        monitoring_source="alpha_smoke_soak.aggregate_runtime",
        readiness_mode=readiness_mode,
        async_jobs_enabled=async_jobs_enabled,
    )
    return {
        "readiness_mode": readiness_mode,
        "status": _worst_status(monitoring.get("status") for monitoring in monitorings if monitoring),
        "rss_mb": _max_from_samples(samples, "rss_mb"),
        "peak_rss_mb": _max_from_samples(samples, "peak_rss_mb"),
        "warnings": sorted(
            {
                safe_str(warning)
                for monitoring in monitorings
                for warning in safe_list(monitoring.get("warnings"))
                if safe_str(warning)
            }
        ),
        "job_queue": queue_monitoring,
        "job_queue_monitoring_evidence": queue_evidence,
        "process": process_monitoring,
        "truth_label": "Aggregated alpha smoke/soak runtime sample. Missing queue or process evidence keeps alpha monitoring blocked.",
    }


def _local_runtime_sample(*, state_dir: Path | None = None, start_time: float | None = None) -> Dict[str, Any]:
    process = runtime_process_monitoring_snapshot(state_dir=state_dir, start_time=start_time or time.time())
    monitoring = runtime_monitoring_snapshot(process=process)
    return {
        "source": "local_runtime_monitoring",
        "status": "ok",
        "monitoring": monitoring,
        "alpha_monitoring_report": build_alpha_monitoring_report(monitoring),
        "truth_label": "Local smoke sample does not include live job queue evidence unless a runtime endpoint is used.",
    }


def fetch_runtime_debug_sample(base_url: str, *, timeout_seconds: float = 10.0) -> Dict[str, Any]:
    normalized = safe_str(base_url).rstrip("/")
    if not normalized:
        raise ValueError("base_url is required for runtime debug sampling.")
    request = Request(f"{normalized}/api/debug/runtime", headers={"Accept": "application/json"})
    with urlopen(request, timeout=max(1.0, timeout_seconds)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def sanitize_alpha_smoke_soak_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Return a commit-safe report copy with local paths and token prefixes redacted."""

    def scrub(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            clean: Dict[str, Any] = {}
            for child_key, child_value in value.items():
                text_key = safe_str(child_key)
                if text_key in _LOCAL_PATH_FIELDS:
                    clean[text_key] = "<local_runtime_path>" if safe_str(child_value) else child_value
                elif text_key in _SENSITIVE_PREFIX_FIELDS:
                    clean[text_key] = "<redacted>" if safe_str(child_value) else ""
                else:
                    clean[text_key] = scrub(child_value, text_key)
            return clean
        if isinstance(value, list):
            return [scrub(item, key) for item in value]
        if isinstance(value, str) and "/Users/" in value:
            return "<local_runtime_path>"
        return value

    return scrub(deepcopy(safe_dict(report)))


def write_alpha_smoke_soak_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(sanitize_alpha_smoke_soak_report(report), handle, indent=2, sort_keys=True)


def run_alpha_smoke_soak(
    *,
    iterations: int = 3,
    interval_seconds: float = 0.0,
    sample_runtime: Optional[RuntimeSampleFn] = None,
    base_url: str = "",
    output_path: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    thresholds: Optional[Dict[str, Any]] = None,
    readiness_mode: str = "private_alpha_review",
    async_jobs_enabled: bool = True,
) -> Dict[str, Any]:
    count = max(1, int(iterations))
    start = time.time()
    sampler = sample_runtime
    if sampler is None and safe_str(base_url):
        sampler = lambda: fetch_runtime_debug_sample(base_url)
    if sampler is None:
        sampler = lambda: _local_runtime_sample(state_dir=state_dir, start_time=start)

    samples: List[Dict[str, Any]] = []
    sample_failures: List[Dict[str, Any]] = []
    for index in range(count):
        try:
            sample = sampler()
            samples.append(deepcopy(safe_dict(sample)))
        except Exception as exc:
            sample_failures.append({"sample_index": index, "error": safe_str(exc)})
        if index < count - 1 and interval_seconds > 0:
            time.sleep(interval_seconds)

    aggregate_runtime = _aggregate_runtime(
        samples,
        readiness_mode=readiness_mode,
        async_jobs_enabled=async_jobs_enabled,
    )
    alpha_report = build_alpha_monitoring_report(
        aggregate_runtime,
        thresholds=thresholds,
        readiness_mode=readiness_mode,
        async_jobs_enabled=async_jobs_enabled,
    )
    if sample_failures:
        alpha_report = deepcopy(alpha_report)
        alpha_report.setdefault("blockers", []).append(
            {
                "area": "monitoring",
                "field": "sample_failures",
                "reason": "One or more alpha smoke/soak samples failed.",
                "message": "One or more alpha smoke/soak samples failed.",
                "why_needed": "Alpha monitoring evidence needs repeatable runtime samples.",
                "suggested_next_action": "Fix sampling failures, rerun the smoke/soak command, and attach a clean report.",
                "severity": "blocker",
                "failures": sample_failures,
            }
        )
        alpha_report["success"] = False
        alpha_report["status"] = "blocked"
        alpha_report["readiness"] = "blocked"
        alpha_report["blocker_details"] = readiness_issue_explanations(safe_list(alpha_report.get("blockers")))

    report = {
        "version": "alpha_smoke_soak_report_v1",
        "readiness_mode": readiness_mode,
        "status": "ready" if bool(alpha_report.get("success")) else "blocked",
        "success": bool(alpha_report.get("success")),
        "sample_count": len(samples),
        "requested_iterations": count,
        "sample_failure_count": len(sample_failures),
        "sample_failures": sample_failures,
        "duration_seconds": round(max(0.0, time.time() - start), 3),
        "aggregate_runtime_monitoring": aggregate_runtime,
        "alpha_monitoring_report": alpha_report,
        "samples": samples,
        "truth_label": "Alpha smoke/soak reports operational readiness only. It does not make Civora construction-ready.",
    }
    if output_path is not None:
        write_alpha_smoke_soak_report(Path(output_path), report)
    return report


__all__ = [
    "fetch_runtime_debug_sample",
    "run_alpha_smoke_soak",
    "sanitize_alpha_smoke_soak_report",
    "write_alpha_smoke_soak_report",
]
