from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from backend.planning.common import readiness_issue_explanations, safe_dict, safe_list, safe_str
from backend.planning.golden_runner import run_golden_scenarios

from .alpha_smoke_soak import RuntimeSampleFn, run_alpha_smoke_soak, sanitize_alpha_smoke_soak_report


BuildPlanFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def _blocker(area: str, field: str, message: str, *, next_action: str) -> Dict[str, Any]:
    return {
        "area": area,
        "field": field,
        "message": message,
        "why_needed": message,
        "suggested_next_action": next_action,
        "severity": "blocker",
    }


def _golden_blockers(report: Dict[str, Any]) -> list[Dict[str, Any]]:
    if bool(report.get("success")):
        return []
    blockers = [
        _blocker(
            "golden_scenarios",
            "golden_scenario_report",
            "One or more golden scenarios failed backend truth, load, or regression expectations.",
            next_action="Inspect failed scenario hard_failures, fix the backend regression, and rerun the private-alpha readiness audit.",
        )
    ]
    failed = [
        safe_str(item.get("scenario_id"))
        for item in safe_list(report.get("results"))
        if safe_str(item.get("scenario_id")) and not bool(safe_dict(item).get("success"))
    ]
    if failed:
        blockers[0]["failed_scenario_ids"] = failed
    return blockers


def _monitoring_blockers(report: Dict[str, Any]) -> list[Dict[str, Any]]:
    if bool(report.get("success")):
        return []
    alpha = safe_dict(report.get("alpha_monitoring_report"))
    blockers = [safe_dict(item) for item in safe_list(alpha.get("blockers")) if safe_dict(item)]
    if blockers:
        return blockers
    return [
        _blocker(
            "monitoring",
            "alpha_smoke_soak_report",
            "Alpha smoke/soak monitoring failed or did not produce enough evidence.",
            next_action="Fix runtime monitoring, queue, process, or sampling blockers and rerun the private-alpha readiness audit.",
        )
    ]


def sanitize_private_alpha_backend_readiness_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Return a commit-safe private-alpha readiness report."""

    return sanitize_alpha_smoke_soak_report(safe_dict(report))


def write_private_alpha_backend_readiness_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(sanitize_private_alpha_backend_readiness_report(report), handle, indent=2, sort_keys=True)


def run_private_alpha_backend_readiness_audit(
    *,
    iterations: int = 3,
    interval_seconds: float = 0.0,
    sample_runtime: Optional[RuntimeSampleFn] = None,
    base_url: str = "",
    scenario_ids: Optional[Iterable[str]] = None,
    build_plan_fn: Optional[BuildPlanFn] = None,
    output_path: Optional[Path] = None,
    thresholds: Optional[Dict[str, Any]] = None,
    readiness_mode: str = "private_alpha_review",
    async_jobs_enabled: bool = True,
    runtime_bearer_token: str = "",
) -> Dict[str, Any]:
    """Run the backend-only private-alpha evidence audit.

    This combines operational smoke/soak monitoring with golden scenario
    regression proof. It intentionally does not produce construction release.
    """

    smoke = run_alpha_smoke_soak(
        iterations=iterations,
        interval_seconds=interval_seconds,
        sample_runtime=sample_runtime,
        base_url=base_url,
        thresholds=thresholds,
        readiness_mode=readiness_mode,
        async_jobs_enabled=async_jobs_enabled,
        runtime_bearer_token=runtime_bearer_token,
    )
    golden = run_golden_scenarios(scenario_ids=scenario_ids, build_plan_fn=build_plan_fn)
    blockers = [
        *_monitoring_blockers(smoke),
        *_golden_blockers(golden),
    ]
    status = "ready" if not blockers else "blocked"
    report = {
        "version": "private_alpha_backend_readiness_report_v1",
        "readiness_mode": readiness_mode,
        "status": status,
        "success": status == "ready",
        "private_alpha_backend_ready": status == "ready",
        "construction_ready": False,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "sections": {
            "monitoring": {
                "readiness_mode": readiness_mode,
                "status": "ready" if bool(smoke.get("success")) else "blocked",
                "sample_count": smoke.get("sample_count"),
                "sample_failure_count": smoke.get("sample_failure_count"),
                "alpha_monitoring_readiness": safe_dict(smoke.get("alpha_monitoring_report")).get("readiness"),
                "job_queue_monitoring_evidence": safe_dict(safe_dict(smoke.get("alpha_monitoring_report")).get("job_queue_monitoring_evidence")),
                "blockers": _monitoring_blockers(smoke),
            },
            "golden_scenarios": {
                "status": safe_str(golden.get("status"), "missing"),
                "success": bool(golden.get("success")),
                "scenario_count": golden.get("scenario_count"),
                "real_file_fixture_count": golden.get("real_file_fixture_count"),
                "failed_load_threshold_count": golden.get("failed_load_threshold_count"),
                "blockers": _golden_blockers(golden),
            },
        },
        "blocker_count": len(blockers),
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "alpha_smoke_soak_report": deepcopy(smoke),
        "golden_scenario_report": deepcopy(golden),
        "next_actions": [
            safe_str(item.get("suggested_next_action"))
            for item in blockers
            if safe_str(item.get("suggested_next_action"))
        ][:8],
        "how_to_clear_queue_monitoring_blocker": (
            "For private_alpha_review, run this audit with --base-url pointing at a live backend whose /api/debug/runtime "
            "includes JobQueueService.runtime_stats() with monitored job types and pending/failed/timeout counts. "
            "For local_dev, missing queue evidence is recorded as unavailable_local and does not prove alpha readiness. "
            "For production, live runtime queue evidence is required when async jobs are enabled."
        ),
        "truth_label": (
            "This backend evidence report proves private-alpha operational and golden-regression readiness only. "
            "It does not make Civora construction-ready or authorize construction release."
        ),
    }
    if output_path is not None:
        write_private_alpha_backend_readiness_report(Path(output_path), report)
    return report


__all__ = [
    "run_private_alpha_backend_readiness_audit",
    "sanitize_private_alpha_backend_readiness_report",
    "write_private_alpha_backend_readiness_report",
]
