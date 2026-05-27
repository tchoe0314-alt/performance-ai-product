from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, List, Optional

from .common import safe_dict, safe_list, safe_str
from .golden_scenarios import GoldenScenario, get_golden_scenario, golden_scenarios


BuildPlanFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def _default_build_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    import planner

    return planner.build_plan(payload)


def _readiness_summary(plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    civil = safe_dict(meta.get("civil_design_readiness"))
    engine = safe_dict(meta.get("engine_readiness"))
    return {
        "civil_status": safe_str(civil.get("status")),
        "civil_success": bool(civil.get("success")),
        "civil_production_ready": bool(civil.get("production_ready")),
        "critical_blocker_count": len(safe_list(civil.get("critical_blockers"))),
        "production_blocker_count": len(safe_list(civil.get("production_blockers"))),
        "engine_production_ready": bool(engine.get("production_ready")),
        "blocked_engine_ids": safe_list(engine.get("blocked_engine_ids")),
        "production_blocked_engine_ids": safe_list(engine.get("production_blocked_engine_ids")),
    }


def _scenario_gate_results(scenario: GoldenScenario, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = safe_dict(plan.get("meta"))
    readiness = safe_dict(meta.get("civil_design_readiness"))
    production_blockers = safe_list(readiness.get("production_blockers"))
    missing_fields = {
        safe_str(item.get("field"))
        for item in production_blockers
        if isinstance(item, dict)
    } | {
        safe_str(item.get("field"))
        for item in safe_list(readiness.get("missing_requirements"))
        if isinstance(item, dict)
    }
    results: List[Dict[str, Any]] = []
    for field in scenario.blocked_without:
        status = "blocked_expected" if field in missing_fields or not bool(readiness.get("production_ready")) else "passed"
        results.append(
            {
                "gate": field,
                "status": status,
                "truth_label": "Golden scenario gates are regression expectations, not permit approval.",
            }
        )
    return results


def run_golden_scenario(
    scenario_id: str,
    *,
    build_plan_fn: Optional[BuildPlanFn] = None,
    payload_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scenario = get_golden_scenario(scenario_id)
    payload = deepcopy(scenario.benchmark_payload)
    if payload_overrides:
        payload.update(deepcopy(payload_overrides))
    runner = build_plan_fn or _default_build_plan
    plan = runner(payload)
    summary = _readiness_summary(plan)
    gates = _scenario_gate_results(scenario, plan)
    false_production_ready = bool(summary.get("civil_production_ready")) and bool(gates)
    hard_failures = []
    if false_production_ready:
        hard_failures.append("scenario_reported_production_ready_while_expected_blockers_exist")
    if not safe_dict(plan.get("meta")).get("engine_readiness"):
        hard_failures.append("engine_readiness_missing")
    if not safe_dict(plan.get("meta")).get("civil_design_readiness"):
        hard_failures.append("civil_design_readiness_missing")
    return {
        "success": not hard_failures,
        "scenario_id": scenario.scenario_id,
        "name": scenario.name,
        "required_engine_ids": sorted(scenario.required_engine_ids),
        "required_canonical_signals": list(scenario.required_canonical_signals),
        "production_gates": list(scenario.production_gates),
        "readiness_summary": summary,
        "gate_results": gates,
        "hard_failures": hard_failures,
        "benchmark_status": "failed" if hard_failures else "passed_with_expected_blockers",
        "truth_label": "Golden benchmark runner checks backend truth signals and blockers; it does not certify engineering design.",
    }


def run_golden_scenarios(
    scenario_ids: Optional[Iterable[str]] = None,
    *,
    build_plan_fn: Optional[BuildPlanFn] = None,
) -> Dict[str, Any]:
    ids = [safe_str(item) for item in scenario_ids or [scenario.scenario_id for scenario in golden_scenarios()]]
    results = [run_golden_scenario(item, build_plan_fn=build_plan_fn) for item in ids if item]
    return {
        "success": all(bool(item.get("success")) for item in results),
        "scenario_count": len(results),
        "results": results,
        "truth_label": "Golden scenarios are executable regression cases with explicit blockers and production-readiness expectations.",
    }


__all__ = ["run_golden_scenario", "run_golden_scenarios"]
