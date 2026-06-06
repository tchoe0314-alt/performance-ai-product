from __future__ import annotations

import hashlib
import json
import multiprocessing
import queue
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from backend.application.memory_logging import current_rss_mb, peak_rss_mb
from backend.planning.common import blocker_explanations, readiness_issue_explanations, safe_dict, safe_float, safe_list, safe_str
from backend.planning.golden_real_file_fixtures import golden_real_file_payload_overrides
from backend.planning.golden_runner import run_golden_scenario
from backend.planning.golden_scenarios import GoldenScenario, get_golden_scenario

from .alpha_smoke_soak import sanitize_alpha_smoke_soak_report


BuildPlanFn = Callable[[Dict[str, Any]], Dict[str, Any]]

DEFAULT_GOLDEN_LOAD_SCENARIO_IDS = (
    "small_commercial_pad",
    "multifamily_site",
    "sloped_detention_site",
    "roadway_corridor",
    "utility_conflict_heavy_site",
    "floodplain_wetland_constrained_site",
)

DEFAULT_SCENARIO_TIMEOUT_SECONDS = 120.0
HEAVY_REAL_FILE_SCENARIO_IDS = frozenset({"roadway_corridor"})


def _deep_merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(safe_dict(base))
    for key, value in safe_dict(updates).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(safe_dict(merged.get(key)), safe_dict(value))
        else:
            merged[key] = deepcopy(value)
    return merged


def _stable_digest(value: Dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _deterministic_payload(scenario: GoldenScenario, *, benchmark_seed: str) -> Dict[str, Any]:
    payload = _deep_merge_dicts(scenario.benchmark_payload, golden_real_file_payload_overrides(scenario.scenario_id))
    meta = _deep_merge_dicts(
        safe_dict(payload.get("meta")),
        {
            "benchmark_seed": benchmark_seed,
            "benchmark_scenario_id": scenario.scenario_id,
            "benchmark_suite": "golden_load",
            "deterministic_benchmark_project": True,
        },
    )
    payload["meta"] = meta
    digest = _stable_digest(payload)
    payload["project_id"] = f"golden-load-{scenario.scenario_id}-{digest[:12]}"
    return payload


def deterministic_benchmark_projects(
    scenario_ids: Optional[Iterable[str]] = None,
    *,
    benchmark_seed: str = "golden-load-v1",
) -> List[Dict[str, Any]]:
    ids = [safe_str(item) for item in scenario_ids or DEFAULT_GOLDEN_LOAD_SCENARIO_IDS if safe_str(item)]
    projects: List[Dict[str, Any]] = []
    for scenario_id in ids:
        scenario = get_golden_scenario(scenario_id)
        payload = _deterministic_payload(scenario, benchmark_seed=benchmark_seed)
        projects.append(
            {
                "scenario_id": scenario.scenario_id,
                "name": scenario.name,
                "project_id": safe_str(payload.get("project_id")),
                "project_name": safe_str(payload.get("project_name")),
                "project_type": safe_str(payload.get("project_type")),
                "payload_sha256": _stable_digest(payload),
                "benchmark_seed": benchmark_seed,
                "synthetic_project": not bool(golden_real_file_payload_overrides(scenario.scenario_id)),
                "truth_label": "Deterministic benchmark projects are stable regression inputs; they are not real client projects.",
            }
        )
    return projects


def _metric_value(result: Dict[str, Any], metric: str) -> float:
    for item in safe_list(result.get("load_threshold_results")):
        rec = safe_dict(item)
        if safe_str(rec.get("metric")) == metric:
            return safe_float(rec.get("value"), 0.0)
    return 0.0


def _load_threshold_results(
    *,
    elapsed_ms: float,
    rss_mb: float,
    peak_rss_mb: float,
    thresholds: Dict[str, Any],
) -> List[Dict[str, Any]]:
    checks = (
        ("elapsed_ms", elapsed_ms, thresholds.get("max_elapsed_ms")),
        ("rss_mb", rss_mb, thresholds.get("max_rss_mb")),
        ("peak_rss_mb", peak_rss_mb, thresholds.get("max_peak_rss_mb")),
    )
    results: List[Dict[str, Any]] = []
    for metric, value, threshold in checks:
        if threshold is None:
            continue
        limit = safe_float(threshold, 0.0)
        results.append(
            {
                "metric": metric,
                "value": round(max(0.0, safe_float(value, 0.0)), 3),
                "max": threshold,
                "passed": limit <= 0.0 or safe_float(value, 0.0) <= limit,
                "truth_label": "Golden load threshold checks runtime/memory regression risk only; it is not public-scale load proof.",
            }
        )
    return results


def _timeout_blocker(scenario_id: str, timeout_seconds: float, elapsed_ms: float) -> Dict[str, Any]:
    return {
        "area": "golden_load_benchmark",
        "field": "scenario_timeout",
        "scenario_id": scenario_id,
        "message": f"Golden scenario exceeded the per-scenario timeout of {timeout_seconds:.3f} seconds.",
        "why_needed": "Golden load benchmarks must fail with a blocker instead of hanging the backend benchmark process.",
        "suggested_next_action": "Profile or split the scenario runner, then rerun with an explicit timeout that reflects the benchmark tier.",
        "severity": "blocker",
        "elapsed_ms": round(max(0.0, elapsed_ms), 3),
    }


def _failure_blocker(scenario_id: str, error: str) -> Dict[str, Any]:
    return {
        "area": "golden_load_benchmark",
        "field": "scenario_execution_failure",
        "scenario_id": scenario_id,
        "message": "Golden scenario raised an exception during benchmark execution.",
        "why_needed": "Golden load benchmarks need executable backend scenarios before their outputs can be trusted.",
        "suggested_next_action": "Fix the scenario exception, rerun the benchmark, and inspect runtime/memory thresholds after the scenario completes.",
        "severity": "blocker",
        "error": error,
    }


def _skip_blocker(scenario_id: str) -> Dict[str, Any]:
    return {
        "area": "golden_load_benchmark",
        "field": "heavy_golden_initialization_skipped",
        "scenario_id": scenario_id,
        "message": "Heavy real-file golden initialization was skipped by benchmark configuration.",
        "why_needed": "Skipped heavy initialization must be explicit so the report never implies that DXF/LandXML-heavy golden coverage passed.",
        "suggested_next_action": "Run this scenario without skip_heavy_real_file_scenarios, or attach a separate timed real-file benchmark artifact.",
        "severity": "blocker",
    }


def _placeholder_load_thresholds(scenario_id: str, elapsed_ms: float, thresholds: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _load_threshold_results(
        elapsed_ms=elapsed_ms,
        rss_mb=current_rss_mb(),
        peak_rss_mb=peak_rss_mb(),
        thresholds=thresholds,
    )


def _scenario_thresholds(scenario: GoldenScenario, overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return _deep_merge_dicts(scenario.load_thresholds, safe_dict(overrides))


def _system_evidence_from_result(result: Dict[str, Any]) -> Dict[str, Any]:
    readiness = safe_dict(result.get("readiness_summary"))
    completed = [
        safe_str(item.get("signal"))
        for item in safe_list(result.get("canonical_signal_results"))
        if bool(safe_dict(item).get("present")) and safe_str(safe_dict(item).get("signal"))
    ]
    blocked = sorted(
        {
            safe_str(item)
            for item in (
                safe_list(readiness.get("blocked_engine_ids"))
                + safe_list(readiness.get("production_blocked_engine_ids"))
                + safe_list(result.get("missing_canonical_signals"))
                + safe_list(result.get("failed_benchmark_expectations"))
                + safe_list(result.get("failed_load_thresholds"))
            )
            if safe_str(item)
        }
    )
    missing_inputs = _dedupe_records([
        *safe_list(readiness.get("critical_blocker_details")),
        *safe_list(readiness.get("production_blocker_details")),
        *safe_list(readiness.get("construction_blocker_details")),
    ])
    export_blockers = [
        item
        for item in missing_inputs
        if safe_str(safe_dict(item).get("area")).lower() in {"cad_interop", "deliverables", "export", "exports"}
        or "export" in safe_str(safe_dict(item).get("field")).lower()
    ]
    standards_blockers = [
        item
        for item in missing_inputs
        if safe_str(safe_dict(item).get("area")).lower() == "standards"
        or "standards" in safe_str(safe_dict(item).get("field")).lower()
    ]
    return {
        "systems_completed": completed,
        "systems_blocked": blocked,
        "missing_inputs": missing_inputs,
        "export_readiness": {
            "status": "blocked" if export_blockers else "unknown",
            "blockers": export_blockers,
            "truth_label": "Export readiness is reported only when scenario output exposes export evidence or blockers.",
        },
        "standards_readiness": {
            "status": "blocked" if standards_blockers else "unknown",
            "blockers": standards_blockers,
            "truth_label": "Standards readiness is not inferred; absent standards package evidence stays unknown.",
        },
        "construction_release_blocked": True,
    }


def _result_with_system_evidence(result: Dict[str, Any]) -> Dict[str, Any]:
    enriched = deepcopy(safe_dict(result))
    enriched.update(_system_evidence_from_result(enriched))
    enriched["construction_ready"] = False
    enriched["construction_release_allowed"] = False
    enriched["construction_release_blocked"] = True
    return enriched


def _synthetic_failure_result(
    *,
    scenario: GoldenScenario,
    benchmark_iteration: int,
    project: Dict[str, Any],
    elapsed_ms: float,
    hard_failure: str,
    benchmark_status: str,
    blocker: Dict[str, Any],
    thresholds: Dict[str, Any],
    error: str = "",
) -> Dict[str, Any]:
    load_results = _placeholder_load_thresholds(scenario.scenario_id, elapsed_ms, thresholds)
    result = {
        "success": False,
        "scenario_id": scenario.scenario_id,
        "name": scenario.name,
        "required_engine_ids": sorted(scenario.required_engine_ids),
        "required_canonical_signals": list(scenario.required_canonical_signals),
        "production_gates": list(scenario.production_gates),
        "readiness_summary": {
            "civil_production_ready": False,
            "construction_ready": False,
            "construction_release_allowed": False,
            "critical_blocker_count": 1,
            "production_blocker_count": 1,
            "construction_blocker_count": 1,
            "critical_blocker_details": [blocker],
            "production_blocker_details": [blocker],
            "construction_blocker_details": [blocker],
            "blocked_engine_ids": [],
            "production_blocked_engine_ids": [],
        },
        "input_evidence": {},
        "real_file_fixture": bool(golden_real_file_payload_overrides(scenario.scenario_id)),
        "real_file_fixture_type": "",
        "gate_results": [],
        "canonical_signal_results": [],
        "missing_canonical_signals": list(scenario.required_canonical_signals),
        "benchmark_expectation_results": [],
        "failed_benchmark_expectations": [],
        "load_thresholds": thresholds,
        "load_threshold_results": load_results,
        "failed_load_thresholds": [safe_str(item.get("metric")) for item in load_results if not bool(safe_dict(item).get("passed"))],
        "hard_failures": [hard_failure],
        "hard_failure_details": blocker_explanations([hard_failure]),
        "benchmark_status": benchmark_status,
        "benchmark_iteration": benchmark_iteration,
        "benchmark_project_id": project.get("project_id"),
        "payload_sha256": project.get("payload_sha256"),
        "error": error,
        "truth_label": "Synthetic benchmark failure records timeout/skip/exception evidence only; it does not certify engineering design.",
    }
    return _result_with_system_evidence(result)


def _child_run_golden_scenario(
    output: multiprocessing.Queue,
    scenario_id: str,
    build_plan_fn: Optional[BuildPlanFn],
    payload_overrides: Dict[str, Any],
    load_threshold_overrides: Optional[Dict[str, Any]],
) -> None:
    try:
        result = run_golden_scenario(
            scenario_id,
            build_plan_fn=build_plan_fn,
            payload_overrides=payload_overrides,
            load_threshold_overrides=load_threshold_overrides,
        )
        output.put({"success": True, "result": result})
    except Exception as exc:
        output.put({"success": False, "error": safe_str(exc) or exc.__class__.__name__})


def _multiprocessing_context() -> multiprocessing.context.BaseContext:
    try:
        return multiprocessing.get_context("fork")
    except ValueError:
        return multiprocessing.get_context()


def _run_scenario_with_timeout(
    *,
    scenario: GoldenScenario,
    project: Dict[str, Any],
    benchmark_iteration: int,
    benchmark_seed: str,
    timeout_seconds: float,
    build_plan_fn: Optional[BuildPlanFn],
    load_threshold_overrides: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    thresholds = _scenario_thresholds(scenario, load_threshold_overrides)
    payload_overrides = {
        "project_id": project.get("project_id"),
        "meta": {
            "benchmark_iteration": benchmark_iteration,
            "benchmark_seed": benchmark_seed,
            "benchmark_scenario_id": scenario.scenario_id,
            "benchmark_suite": "golden_load",
            "deterministic_benchmark_project": True,
        },
    }
    context = _multiprocessing_context()
    output = context.Queue(maxsize=1)
    start = time.perf_counter()
    process = context.Process(
        target=_child_run_golden_scenario,
        args=(output, scenario.scenario_id, build_plan_fn, payload_overrides, load_threshold_overrides),
    )
    process.start()
    process.join(max(0.001, timeout_seconds))
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if process.is_alive():
        process.terminate()
        process.join(2.0)
        if process.is_alive():
            process.kill()
            process.join(2.0)
        return _synthetic_failure_result(
            scenario=scenario,
            benchmark_iteration=benchmark_iteration,
            project=project,
            elapsed_ms=elapsed_ms,
            hard_failure="golden_scenario_timeout",
            benchmark_status="timeout_blocked",
            blocker=_timeout_blocker(scenario.scenario_id, timeout_seconds, elapsed_ms),
            thresholds=thresholds,
        )
    try:
        message = output.get_nowait()
    except queue.Empty:
        message = {"success": False, "error": f"scenario exited with code {process.exitcode} without returning a result"}
    if not bool(message.get("success")):
        error = safe_str(message.get("error"), "scenario execution failed")
        return _synthetic_failure_result(
            scenario=scenario,
            benchmark_iteration=benchmark_iteration,
            project=project,
            elapsed_ms=elapsed_ms,
            hard_failure="golden_scenario_execution_failed",
            benchmark_status="execution_failed",
            blocker=_failure_blocker(scenario.scenario_id, error),
            thresholds=thresholds,
            error=error,
        )
    result = _result_with_system_evidence(safe_dict(message.get("result")))
    result["benchmark_iteration"] = benchmark_iteration
    result["benchmark_project_id"] = project.get("project_id")
    result["payload_sha256"] = project.get("payload_sha256")
    return result


def _scenario_blockers(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    for result in results:
        if bool(result.get("success")):
            continue
        blockers.append(
            {
                "area": "golden_load_benchmark",
                "field": safe_str(result.get("scenario_id")),
                "message": "Golden load scenario failed benchmark expectations or thresholds.",
                "why_needed": "Golden load benchmarks must preserve backend truth signals, expected blockers, runtime, and memory thresholds.",
                "suggested_next_action": "Inspect hard_failures, failed_benchmark_expectations, and failed_load_thresholds for this scenario, fix the backend regression, and rerun the benchmark report.",
                "severity": "blocker",
                "hard_failures": safe_list(result.get("hard_failures")),
                "failed_benchmark_expectations": safe_list(result.get("failed_benchmark_expectations")),
                "failed_load_thresholds": safe_list(result.get("failed_load_thresholds")),
                "runtime_ms": safe_dict(result.get("runtime_ms")) or {"elapsed_ms": _metric_value(result, "elapsed_ms")},
                "memory_mb": safe_dict(result.get("memory_mb")) or {
                    "rss_mb": _metric_value(result, "rss_mb"),
                    "peak_rss_mb": _metric_value(result, "peak_rss_mb"),
                },
            }
        )
    return blockers


def _aggregate_scenario_runs(scenario_id: str, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    elapsed_values = [_metric_value(item, "elapsed_ms") for item in runs]
    rss_values = [_metric_value(item, "rss_mb") for item in runs]
    peak_values = [_metric_value(item, "peak_rss_mb") for item in runs]
    blockers = _scenario_blockers(runs)
    successes = [bool(item.get("success")) for item in runs]
    return {
        "scenario_id": scenario_id,
        "status": "passed" if all(successes) else "failed",
        "success": all(successes),
        "iteration_count": len(runs),
        "pass_count": len([item for item in successes if item]),
        "fail_count": len([item for item in successes if not item]),
        "runtime_ms": {
            "min": round(min(elapsed_values or [0.0]), 3),
            "max": round(max(elapsed_values or [0.0]), 3),
            "avg": round(sum(elapsed_values) / max(1, len(elapsed_values)), 3),
        },
        "memory_mb": {
            "max_rss_mb": round(max(rss_values or [0.0]), 3),
            "max_peak_rss_mb": round(max(peak_values or [0.0]), 3),
        },
        "blocker_count": len(blockers),
        "blockers": blockers,
        "hard_failures": sorted({safe_str(code) for item in runs for code in safe_list(item.get("hard_failures")) if safe_str(code)}),
        "failed_benchmark_expectations": sorted(
            {safe_str(code) for item in runs for code in safe_list(item.get("failed_benchmark_expectations")) if safe_str(code)}
        ),
        "failed_load_thresholds": sorted(
            {safe_str(code) for item in runs for code in safe_list(item.get("failed_load_thresholds")) if safe_str(code)}
        ),
        "systems_completed": sorted(
            {safe_str(system) for item in runs for system in safe_list(item.get("systems_completed")) if safe_str(system)}
        ),
        "systems_blocked": sorted(
            {safe_str(system) for item in runs for system in safe_list(item.get("systems_blocked")) if safe_str(system)}
        ),
        "missing_inputs": _dedupe_records([
            safe_dict(item)
            for run in runs
            for item in safe_list(run.get("missing_inputs"))
            if safe_dict(item)
        ]),
        "export_readiness": _aggregate_readiness_status(runs, "export_readiness"),
        "standards_readiness": _aggregate_readiness_status(runs, "standards_readiness"),
        "construction_release_blocked": True,
    }


def _aggregate_readiness_status(runs: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    blockers = _dedupe_records([
        safe_dict(blocker)
        for run in runs
        for blocker in safe_list(safe_dict(run.get(key)).get("blockers"))
        if safe_dict(blocker)
    ])
    statuses = {safe_str(safe_dict(run.get(key)).get("status")) for run in runs if safe_str(safe_dict(run.get(key)).get("status"))}
    if "blocked" in statuses or blockers:
        status = "blocked"
    elif "ready" in statuses:
        status = "ready"
    else:
        status = "unknown"
    return {
        "status": status,
        "blockers": blockers,
        "truth_label": "Readiness status is summarized from scenario evidence only; missing evidence remains unknown.",
    }


def _load_engine_depth_audit_reference(
    *,
    report: Optional[Dict[str, Any]] = None,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    source_report = safe_dict(report)
    source_path = Path(path) if path is not None else None
    load_error = ""
    if not source_report and source_path is not None:
        try:
            with source_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            source_report = safe_dict(data)
        except Exception as exc:
            load_error = safe_str(exc) or exc.__class__.__name__
    version = safe_str(source_report.get("version"))
    valid = version == "engine_depth_audit_report_v1"
    return {
        "attached": bool(source_report),
        "valid": valid,
        "version": version,
        "status": safe_str(source_report.get("status")),
        "success": bool(source_report.get("success")) if source_report else False,
        "path": str(source_path) if source_path is not None else "",
        "engine_count": source_report.get("engine_count"),
        "scenario_count": source_report.get("scenario_count"),
        "blocker_count": source_report.get("blocker_count"),
        "failed_deterministic_check_count": source_report.get("failed_deterministic_check_count"),
        "load_error": load_error,
        "truth_label": "Engine depth audit reference is attached as evidence only; golden/load does not create or fake engine depth.",
    }


def _dedupe_records(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in items:
        rec = safe_dict(item)
        if not rec:
            continue
        key = json.dumps(rec, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rec)
    return deduped


def sanitize_golden_load_benchmark_report(report: Dict[str, Any]) -> Dict[str, Any]:
    return sanitize_alpha_smoke_soak_report(safe_dict(report))


def write_golden_load_benchmark_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(sanitize_golden_load_benchmark_report(report), handle, indent=2, sort_keys=True)


def run_golden_load_benchmarks(
    *,
    scenario_ids: Optional[Iterable[str]] = None,
    iterations: int = 1,
    interval_seconds: float = 0.0,
    build_plan_fn: Optional[BuildPlanFn] = None,
    output_path: Optional[Path] = None,
    benchmark_seed: str = "golden-load-v1",
    load_threshold_overrides: Optional[Dict[str, Any]] = None,
    scenario_timeout_seconds: float = DEFAULT_SCENARIO_TIMEOUT_SECONDS,
    skip_heavy_real_file_scenarios: bool = False,
    engine_depth_audit_report: Optional[Dict[str, Any]] = None,
    engine_depth_audit_report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    ids = [safe_str(item) for item in scenario_ids or DEFAULT_GOLDEN_LOAD_SCENARIO_IDS if safe_str(item)]
    count = max(1, int(iterations))
    projects = deterministic_benchmark_projects(ids, benchmark_seed=benchmark_seed)
    start = time.perf_counter()
    all_runs: List[Dict[str, Any]] = []
    by_scenario: Dict[str, List[Dict[str, Any]]] = {scenario_id: [] for scenario_id in ids}

    for iteration in range(count):
        for project in projects:
            scenario_id = safe_str(project.get("scenario_id"))
            scenario = get_golden_scenario(scenario_id)
            if skip_heavy_real_file_scenarios and scenario_id in HEAVY_REAL_FILE_SCENARIO_IDS:
                result = _synthetic_failure_result(
                    scenario=scenario,
                    benchmark_iteration=iteration + 1,
                    project=project,
                    elapsed_ms=0.0,
                    hard_failure="heavy_golden_initialization_skipped",
                    benchmark_status="heavy_initialization_skipped",
                    blocker=_skip_blocker(scenario_id),
                    thresholds=_scenario_thresholds(scenario, load_threshold_overrides),
                )
            else:
                result = _run_scenario_with_timeout(
                    scenario=scenario,
                    project=project,
                    benchmark_iteration=iteration + 1,
                    benchmark_seed=benchmark_seed,
                    timeout_seconds=scenario_timeout_seconds,
                    build_plan_fn=build_plan_fn,
                    load_threshold_overrides=load_threshold_overrides,
                )
            all_runs.append(result)
            by_scenario.setdefault(scenario_id, []).append(result)
        if iteration < count - 1 and interval_seconds > 0:
            time.sleep(interval_seconds)

    scenario_summaries = [_aggregate_scenario_runs(scenario_id, by_scenario.get(scenario_id, [])) for scenario_id in ids]
    blockers = [
        blocker
        for summary in scenario_summaries
        for blocker in safe_list(summary.get("blockers"))
    ]
    total_runtime_ms = (time.perf_counter() - start) * 1000.0
    success = all(bool(item.get("success")) for item in scenario_summaries)
    engine_depth_reference = _load_engine_depth_audit_reference(
        report=engine_depth_audit_report,
        path=engine_depth_audit_report_path,
    )
    report = {
        "version": "golden_load_benchmark_report_v1",
        "status": "passed" if success else "failed",
        "success": success,
        "backend_only": True,
        "scenario_count": len(ids),
        "iteration_count": count,
        "total_run_count": len(all_runs),
        "scenario_timeout_seconds": float(max(0.001, scenario_timeout_seconds)),
        "skip_heavy_real_file_scenarios": bool(skip_heavy_real_file_scenarios),
        "deterministic_project_count": len(projects),
        "deterministic_projects": projects,
        "runtime_ms": round(max(0.0, total_runtime_ms), 3),
        "engine_depth_audit_reference": engine_depth_reference,
        "scenario_summaries": scenario_summaries,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "hard_failure_details": blocker_explanations(
            [safe_str(code) for item in all_runs for code in safe_list(item.get("hard_failures")) if safe_str(code)]
        ),
        "systems_completed": sorted({safe_str(system) for run in all_runs for system in safe_list(run.get("systems_completed")) if safe_str(system)}),
        "systems_blocked": sorted({safe_str(system) for run in all_runs for system in safe_list(run.get("systems_blocked")) if safe_str(system)}),
        "missing_inputs": _dedupe_records([
            safe_dict(item)
            for run in all_runs
            for item in safe_list(run.get("missing_inputs"))
            if safe_dict(item)
        ]),
        "export_readiness": _aggregate_readiness_status(all_runs, "export_readiness"),
        "standards_readiness": _aggregate_readiness_status(all_runs, "standards_readiness"),
        "construction_ready": False,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "runs": all_runs,
        "truth_label": "Golden load benchmarks report backend regression readiness only. They do not certify construction readiness or public-scale capacity.",
    }
    if output_path is not None:
        write_golden_load_benchmark_report(Path(output_path), report)
    return report


__all__ = [
    "DEFAULT_GOLDEN_LOAD_SCENARIO_IDS",
    "DEFAULT_SCENARIO_TIMEOUT_SECONDS",
    "HEAVY_REAL_FILE_SCENARIO_IDS",
    "deterministic_benchmark_projects",
    "run_golden_load_benchmarks",
    "sanitize_golden_load_benchmark_report",
    "write_golden_load_benchmark_report",
]
