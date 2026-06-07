from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set

from .common import readiness_issue_explanations, safe_dict, safe_list, safe_str
from .engine_contracts import EngineContract, engine_contracts
from .engine_depth_dashboard import build_engine_depth_dashboard
from .engine_readiness import evaluate_engine_readiness
from .golden_runner import run_golden_scenario
from .golden_scenarios import GoldenScenario, get_golden_scenario, golden_scenarios
from .production_evidence import build_production_evidence


BuildPlanFn = Callable[[Dict[str, Any]], Dict[str, Any]]

REPORT_VERSION = "engine_depth_audit_report_v1"
CLASS_CONCEPT = "concept"
CLASS_REVIEW = "review"
CLASS_PRODUCTION_DEPTH = "production-depth"
CLASS_NOT_APPLICABLE = "not-applicable"
CLASS_NOT_AUDITED = "not-audited"

CLASSIFICATION_SCORES = {
    CLASS_CONCEPT: 0.0,
    CLASS_REVIEW: 70.0,
    CLASS_PRODUCTION_DEPTH: 100.0,
    CLASS_NOT_APPLICABLE: 100.0,
    CLASS_NOT_AUDITED: 0.0,
}


def _default_build_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    import planner

    return planner.build_plan(payload)


def _deep_merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(safe_dict(base))
    for key, value in safe_dict(updates).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(safe_dict(merged.get(key)), safe_dict(value))
        else:
            merged[key] = deepcopy(value)
    return merged


def _blocker(area: str, field: str, message: str, *, next_action: str, scenario_id: str = "", engine_id: str = "") -> Dict[str, Any]:
    blocker = {
        "area": area,
        "field": field,
        "message": message,
        "why_needed": message,
        "suggested_next_action": next_action,
        "severity": "blocker",
    }
    if scenario_id:
        blocker["scenario_id"] = scenario_id
    if engine_id:
        blocker["engine_id"] = engine_id
    return blocker


def _depth_classification(engine_row: Dict[str, Any]) -> str:
    status = safe_str(engine_row.get("status"))
    if status == "production_ready":
        return CLASS_PRODUCTION_DEPTH
    if status in {"concept_ready_needs_production_depth", "needs_engineering_review"}:
        return CLASS_REVIEW
    if status == "not_applicable":
        return CLASS_NOT_APPLICABLE
    return CLASS_CONCEPT


def _backend_gate_label(classification: str, *, required: bool = True) -> str:
    if not required:
        return "backend_gate_not_audited_for_selected_scenarios"
    if classification == CLASS_PRODUCTION_DEPTH:
        return "backend_ready_production_depth"
    if classification == CLASS_REVIEW:
        return "backend_ready_review_only"
    if classification == CLASS_NOT_APPLICABLE and not required:
        return "backend_ready_not_applicable"
    return "backend_blocked_concept_or_missing"


def _launch_gate_label(classification: str, *, required: bool, checks_passed: bool, blockers: Sequence[Dict[str, Any]]) -> str:
    if not required:
        return "not_in_selected_scenario_scope"
    if not checks_passed:
        return "blocked"
    if classification == CLASS_PRODUCTION_DEPTH:
        return "production_depth_gate_clear"
    if classification == CLASS_REVIEW:
        return "review_launch_allowed"
    if classification == CLASS_NOT_APPLICABLE:
        return "not_applicable"
    return "blocked"


def _confidence_for_row(classification: str, *, required: bool, checks_passed: bool, evidence_count: int, blocker_count: int) -> float:
    if not required:
        return 0.0
    if classification == CLASS_PRODUCTION_DEPTH and checks_passed and blocker_count == 0:
        return 0.95
    if classification == CLASS_REVIEW and checks_passed:
        return min(0.82, 0.62 + min(evidence_count, 4) * 0.04)
    if classification == CLASS_NOT_APPLICABLE:
        return 0.8
    if checks_passed and blocker_count == 0:
        return 0.45
    return 0.2


def _first_failing_layer(checks: Sequence[Dict[str, Any]], blockers: Sequence[Dict[str, Any]]) -> str:
    for check in checks:
        if not bool(safe_dict(check).get("passed")):
            rec = safe_dict(check)
            return safe_str(rec.get("check_type") or rec.get("engine_id") or rec.get("canonical_signal") or rec.get("metric"), "deterministic_check")
    for blocker in blockers:
        rec = safe_dict(blocker)
        return safe_str(rec.get("field") or rec.get("area"), "blocker")
    return ""


def _required_gate_label(classification: str) -> str:
    if classification == CLASS_PRODUCTION_DEPTH:
        return "expected_production_depth_actual_production_depth"
    if classification == CLASS_REVIEW:
        return "expected_engine_depth_actual_review"
    if classification == CLASS_NOT_APPLICABLE:
        return "expected_engine_depth_actual_not_applicable"
    return "expected_engine_depth_actual_concept"


def _required_gate_passed(classification: str) -> bool:
    return classification in {CLASS_REVIEW, CLASS_PRODUCTION_DEPTH}


def _engine_checks(
    *,
    scenario_id: str,
    scenario: GoldenScenario,
    readiness: Dict[str, Any],
) -> List[Dict[str, Any]]:
    engines = safe_dict(readiness.get("engines"))
    checks: List[Dict[str, Any]] = []
    for engine_id in sorted(scenario.required_engine_ids):
        row = safe_dict(engines.get(engine_id))
        classification = _depth_classification(row) if row else CLASS_CONCEPT
        passed = bool(row) and _required_gate_passed(classification)
        checks.append(
            {
                "check_id": f"{scenario_id}:{engine_id}:required_engine_depth",
                "scenario_id": scenario_id,
                "engine_id": engine_id,
                "check_type": "expected_vs_actual_engine_depth",
                "expected": "review-or-production-depth",
                "actual": classification,
                "backend_readiness_gate_label": _required_gate_label(classification),
                "passed": passed,
                "truth_label": "Required scenario engines must produce deterministic review or production-depth evidence; concept/missing output blocks backend readiness.",
            }
        )
    return checks


def _canonical_signal_checks(scenario_id: str, golden_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for item in safe_list(golden_result.get("canonical_signal_results")):
        rec = safe_dict(item)
        signal = safe_str(rec.get("signal"))
        if not signal:
            continue
        present = bool(rec.get("present"))
        checks.append(
            {
                "check_id": f"{scenario_id}:signal:{signal}",
                "scenario_id": scenario_id,
                "check_type": "expected_vs_actual_canonical_signal",
                "expected": "present",
                "actual": "present" if present else "missing",
                "canonical_signal": signal,
                "backend_readiness_gate_label": "canonical_signal_present" if present else "canonical_signal_missing",
                "passed": present,
                "truth_label": "Canonical signal checks are deterministic backend evidence checks, not professional approval.",
            }
        )
    return checks


def _benchmark_checks(scenario_id: str, golden_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for item in safe_list(golden_result.get("benchmark_expectation_results")):
        rec = safe_dict(item)
        metric = safe_str(rec.get("metric"))
        if not metric:
            continue
        passed = bool(rec.get("passed"))
        expected = {
            key: rec.get(key)
            for key in ("min", "max", "equals")
            if rec.get(key) is not None
        }
        checks.append(
            {
                "check_id": f"{scenario_id}:metric:{metric}",
                "scenario_id": scenario_id,
                "check_type": "expected_vs_actual_metric",
                "expected": expected,
                "actual": rec.get("value"),
                "metric": metric,
                "backend_readiness_gate_label": "metric_expectation_met" if passed else "metric_expectation_failed",
                "passed": passed,
                "truth_label": "Metric checks compare deterministic expected values to actual backend outputs.",
            }
        )
    return checks


def _scenario_blockers(scenario_id: str, checks: Sequence[Dict[str, Any]], golden_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    for check in checks:
        if bool(check.get("passed")):
            continue
        blockers.append(
            _blocker(
                safe_str(check.get("check_type"), "engine_depth_audit"),
                safe_str(check.get("engine_id") or check.get("canonical_signal") or check.get("metric") or "deterministic_check"),
                f"Engine depth audit failed deterministic check {safe_str(check.get('check_id'))}.",
                next_action="Inspect the scenario engine output, restore required backend evidence, and rerun the Phase 1 depth audit.",
                scenario_id=scenario_id,
                engine_id=safe_str(check.get("engine_id")),
            )
        )
    for failure in safe_list(golden_result.get("hard_failures")):
        code = safe_str(failure)
        if not code:
            continue
        blockers.append(
            _blocker(
                "golden_scenario",
                code,
                f"Golden scenario hard failure remained during engine depth audit: {code}.",
                next_action="Fix the backend regression reported by the golden scenario runner, then rerun the Phase 1 depth audit.",
                scenario_id=scenario_id,
            )
        )
    return blockers


def _stable_golden_result_summary(golden_result: Dict[str, Any]) -> Dict[str, Any]:
    """Keep golden evidence useful without embedding nondeterministic load samples."""

    return {
        "success": bool(golden_result.get("success")),
        "scenario_id": safe_str(golden_result.get("scenario_id")),
        "name": safe_str(golden_result.get("name")),
        "required_engine_ids": safe_list(golden_result.get("required_engine_ids")),
        "required_canonical_signals": safe_list(golden_result.get("required_canonical_signals")),
        "production_gates": safe_list(golden_result.get("production_gates")),
        "gate_results": deepcopy(safe_list(golden_result.get("gate_results"))),
        "canonical_signal_results": deepcopy(safe_list(golden_result.get("canonical_signal_results"))),
        "missing_canonical_signals": safe_list(golden_result.get("missing_canonical_signals")),
        "benchmark_expectation_results": deepcopy(safe_list(golden_result.get("benchmark_expectation_results"))),
        "failed_benchmark_expectations": safe_list(golden_result.get("failed_benchmark_expectations")),
        "failed_load_thresholds": safe_list(golden_result.get("failed_load_thresholds")),
        "hard_failures": safe_list(golden_result.get("hard_failures")),
        "benchmark_status": safe_str(golden_result.get("benchmark_status")),
        "engine_depth_audit": deepcopy(safe_dict(golden_result.get("engine_depth_audit"))),
        "truth_label": "Stable golden summary excludes runtime/load sample values so engine depth reports are CI-comparable.",
    }


def _checks_for_engine(engine_id: str, checks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        deepcopy(safe_dict(check))
        for check in checks
        if safe_str(safe_dict(check).get("engine_id")) == engine_id
    ]


def _blockers_for_engine(engine_id: str, blockers: Sequence[Dict[str, Any]], engine_row: Dict[str, Any]) -> List[Dict[str, Any]]:
    row_blockers = [
        deepcopy(safe_dict(blocker))
        for blocker in blockers
        if safe_str(safe_dict(blocker).get("engine_id")) == engine_id
    ]
    row_blockers.extend(deepcopy(item) for item in safe_list(engine_row.get("missing_requirements")) if safe_dict(item))
    row_blockers.extend(deepcopy(item) for item in safe_list(engine_row.get("production_blockers")) if safe_dict(item))
    return row_blockers


def _engine_report_row(
    *,
    contract: EngineContract,
    readiness_engine_row: Dict[str, Any],
    scenario_ids: Sequence[str],
    checks: Sequence[Dict[str, Any]],
    blockers: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    required = bool(scenario_ids)
    row_checks = _checks_for_engine(contract.engine_id, checks)
    checks_passed = all(bool(check.get("passed")) for check in row_checks) if row_checks else not required
    classification = _depth_classification(readiness_engine_row) if required else CLASS_NOT_AUDITED
    row_blockers = _blockers_for_engine(contract.engine_id, blockers, readiness_engine_row) if required else []
    first_failing_layer = _first_failing_layer(row_checks, row_blockers)
    evidence = safe_list(readiness_engine_row.get("evidence"))
    score = CLASSIFICATION_SCORES.get(classification, 0.0)
    if required and (not checks_passed or classification == CLASS_CONCEPT):
        score = min(score, 25.0)
    confidence = _confidence_for_row(
        classification,
        required=required,
        checks_passed=checks_passed,
        evidence_count=len(evidence),
        blocker_count=len(row_blockers),
    )
    return {
        "engine_id": contract.engine_id,
        "name": contract.name,
        "maturity": contract.maturity,
        "score": round(float(score), 2),
        "classification": classification,
        "actual_depth_classification": classification,
        "expected_depth_classification": "review-or-production-depth" if required else "not-required-for-selected-scenarios",
        "checks": row_checks,
        "check_count": len(row_checks),
        "failed_check_count": len([check for check in row_checks if not bool(check.get("passed"))]),
        "blockers": row_blockers,
        "blocker_details": readiness_issue_explanations(row_blockers),
        "first_failing_layer": first_failing_layer,
        "confidence": round(confidence, 3),
        "launch_gate": _launch_gate_label(
            classification,
            required=required,
            checks_passed=checks_passed,
            blockers=row_blockers,
        ),
        "backend_readiness_gate_label": _backend_gate_label(classification, required=required),
        "required_scenario_ids": list(scenario_ids),
        "status": safe_str(readiness_engine_row.get("status"), "not_audited" if not required else "missing"),
        "review_state": safe_str(readiness_engine_row.get("review_state"), "not_audited" if not required else "blocked"),
        "evidence": evidence,
        "first_missing_or_blocker": (safe_list(readiness_engine_row.get("missing_requirements")) or safe_list(readiness_engine_row.get("production_blockers")) or [{}])[0],
        "truth_label": "Engine depth row is deterministic backend evidence for CI and chat handoff; it is not construction approval.",
    }


def _scenario_payload(scenario: GoldenScenario, payload_overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from .golden_real_file_fixtures import golden_real_file_payload_overrides

    payload = _deep_merge_dicts(scenario.benchmark_payload, golden_real_file_payload_overrides(scenario.scenario_id))
    if payload_overrides:
        payload = _deep_merge_dicts(payload, payload_overrides)
    return payload


def _production_evidence_summary(plan: Dict[str, Any]) -> Dict[str, Any]:
    evidence = safe_dict(safe_dict(plan.get("meta")).get("production_evidence")) or build_production_evidence(plan)
    accepted = safe_dict(evidence.get("accepted_surfaces"))
    storm = safe_dict(evidence.get("storm_hydraulics"))
    profile = safe_dict(evidence.get("profile_section"))
    reactive = safe_dict(evidence.get("reactive_dirty_state"))
    quantity = safe_dict(evidence.get("quantity_cost"))
    return {
        "version": safe_str(evidence.get("version")),
        "production_evidence_ready": evidence.get("production_evidence_ready") is True,
        "blocker_count": len(safe_list(evidence.get("blockers"))),
        "accepted_surface_ready": accepted.get("ready") is True,
        "accepted_existing_surface_id": safe_str(accepted.get("existing_surface_id")),
        "accepted_proposed_surface_id": safe_str(accepted.get("proposed_surface_id")),
        "storm_hgl_row_count": storm.get("hgl_row_count", 0),
        "storm_egl_row_count": storm.get("egl_row_count", 0),
        "missing_required_hydraulic_inputs": safe_list(storm.get("missing_required_hydraulic_inputs")),
        "profile_count": profile.get("profile_count", 0),
        "cross_section_count": profile.get("cross_section_count", 0),
        "reactive_dirty_count": len(safe_list(reactive.get("dirty_state"))),
        "quantity_line_item_count": quantity.get("quantity_line_item_count", 0),
        "approved_cost_source": quantity.get("approved_cost_source") is True,
        "truth_label": "Audit summary references canonical production evidence and blockers without turning them into construction approval.",
    }


def run_engine_depth_audit_scenario(
    scenario_id: str,
    *,
    build_plan_fn: Optional[BuildPlanFn] = None,
    payload_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scenario = get_golden_scenario(scenario_id)
    runner = build_plan_fn or _default_build_plan
    payload = _scenario_payload(scenario, payload_overrides)
    plan = runner(payload)
    evidence_summary = _production_evidence_summary(plan)
    readiness = evaluate_engine_readiness(plan)
    golden_result = run_golden_scenario(
        scenario_id,
        build_plan_fn=runner,
        payload_overrides=payload_overrides,
    )
    checks = [
        *_engine_checks(scenario_id=scenario_id, scenario=scenario, readiness=readiness),
        *_canonical_signal_checks(scenario_id, golden_result),
        *_benchmark_checks(scenario_id, golden_result),
    ]
    blockers = _scenario_blockers(scenario_id, checks, golden_result)
    status = "passed" if not blockers else "failed"
    engines = safe_dict(readiness.get("engines"))
    required_engine_results = {}
    for contract in engine_contracts():
        if contract.engine_id not in scenario.required_engine_ids:
            continue
        row = _engine_report_row(
            contract=contract,
            readiness_engine_row=safe_dict(engines.get(contract.engine_id)),
            scenario_ids=[scenario_id],
            checks=checks,
            blockers=blockers,
        )
        row["backend_readiness_gate_label"] = _required_gate_label(row["classification"])
        required_engine_results[contract.engine_id] = row
    scenario_score_rows = [row for row in required_engine_results.values() if row.get("classification") != CLASS_NOT_APPLICABLE]
    scenario_depth_score = (
        sum(float(row.get("score") or 0.0) for row in scenario_score_rows) / len(scenario_score_rows)
        if scenario_score_rows
        else 0.0
    )
    return {
        "scenario_id": scenario.scenario_id,
        "name": scenario.name,
        "status": status,
        "success": status == "passed",
        "depth_score": round(scenario_depth_score, 2),
        "required_engine_ids": sorted(scenario.required_engine_ids),
        "required_engine_results": required_engine_results,
        "deterministic_checks": checks,
        "production_evidence_summary": evidence_summary,
        "failed_check_ids": [safe_str(item.get("check_id")) for item in checks if not bool(item.get("passed"))],
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "golden_result": _stable_golden_result_summary(golden_result),
        "truth_label": "Scenario engine depth audit measures deterministic backend evidence only; it does not approve construction use.",
    }


def _engine_depth_summary(
    *,
    contracts: Sequence[EngineContract],
    scenario_results: Sequence[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    required_by_engine: Dict[str, Set[str]] = {contract.engine_id: set() for contract in contracts}
    classifications_by_engine: Dict[str, Set[str]] = {contract.engine_id: set() for contract in contracts}
    rows_by_engine: Dict[str, List[Dict[str, Any]]] = {contract.engine_id: [] for contract in contracts}
    for result in scenario_results:
        scenario_id = safe_str(result.get("scenario_id"))
        for engine_id, row_value in safe_dict(result.get("required_engine_results")).items():
            row = safe_dict(row_value)
            required_by_engine.setdefault(engine_id, set()).add(scenario_id)
            classifications_by_engine.setdefault(engine_id, set()).add(safe_str(row.get("actual_depth_classification"), CLASS_CONCEPT))
            rows_by_engine.setdefault(engine_id, []).append(row)

    engine_results: Dict[str, Dict[str, Any]] = {}
    for contract in contracts:
        scenario_rows = rows_by_engine.get(contract.engine_id, [])
        required_scenarios = sorted(required_by_engine.get(contract.engine_id, set()))
        classifications = classifications_by_engine.get(contract.engine_id, set())
        if not required_scenarios:
            actual = CLASS_NOT_AUDITED
        elif CLASS_CONCEPT in classifications:
            actual = CLASS_CONCEPT
        elif CLASS_REVIEW in classifications:
            actual = CLASS_REVIEW
        elif CLASS_PRODUCTION_DEPTH in classifications:
            actual = CLASS_PRODUCTION_DEPTH
        elif CLASS_NOT_APPLICABLE in classifications:
            actual = CLASS_NOT_APPLICABLE
        else:
            actual = CLASS_CONCEPT
        checks = [check for row in scenario_rows for check in safe_list(row.get("checks"))]
        blockers = [blocker for row in scenario_rows for blocker in safe_list(row.get("blockers"))]
        evidence = sorted(
            {
                safe_str(item)
                for row in scenario_rows
                for item in safe_list(row.get("evidence"))
                if safe_str(item)
            }
        )
        checks_passed = all(bool(check.get("passed")) for check in checks) if checks else not required_scenarios
        score_rows = [row for row in scenario_rows if row.get("classification") != CLASS_NOT_APPLICABLE]
        score = (
            sum(float(row.get("score") or 0.0) for row in score_rows) / len(score_rows)
            if score_rows
            else CLASSIFICATION_SCORES.get(actual, 0.0)
        )
        confidence = (
            sum(float(row.get("confidence") or 0.0) for row in scenario_rows) / len(scenario_rows)
            if scenario_rows
            else 0.0
        )
        engine_results[contract.engine_id] = _engine_report_row(
            contract=contract,
            readiness_engine_row={"status": actual, "review_state": actual, "evidence": evidence},
            scenario_ids=required_scenarios,
            checks=checks,
            blockers=blockers,
        )
        engine_results[contract.engine_id].update(
            {
                "score": round(score, 2),
                "classification": actual,
                "actual_depth_classification": actual,
                "checks": checks,
                "check_count": len(checks),
                "failed_check_count": len([check for check in checks if not bool(check.get("passed"))]),
                "blockers": blockers,
                "evidence": evidence,
                "blocker_details": readiness_issue_explanations(blockers),
                "first_failing_layer": _first_failing_layer(checks, blockers),
                "confidence": round(confidence, 3),
                "launch_gate": _launch_gate_label(actual, required=bool(required_scenarios), checks_passed=checks_passed, blockers=blockers),
                "backend_readiness_gate_label": _backend_gate_label(actual, required=bool(required_scenarios)),
                "required_scenario_ids": required_scenarios,
                "scenario_row_count": len(scenario_rows),
            }
        )
    return engine_results


def _gate_recommendations(
    *,
    status: str,
    overall_depth_score: float,
    failed_check_count: int,
    blocker_count: int,
    required_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    all_required_production_depth = bool(required_rows) and all(
        row.get("classification") in {CLASS_PRODUCTION_DEPTH, CLASS_NOT_APPLICABLE}
        for row in required_rows
    )
    no_failures = status == "passed" and failed_check_count == 0 and blocker_count == 0
    return {
        "private_alpha": {
            "recommendation": "allow_backend_private_alpha" if no_failures and overall_depth_score >= 60.0 else "block_private_alpha",
            "minimum_depth_score": 60.0,
            "truth_label": "Private-alpha gate is backend evidence only and still requires review-only labeling.",
        },
        "public_beta": {
            "recommendation": "allow_backend_public_beta_review_only" if no_failures and overall_depth_score >= 75.0 else "block_public_beta",
            "minimum_depth_score": 75.0,
            "truth_label": "Public-beta gate requires stronger deterministic depth evidence but is not construction approval.",
        },
        "construction": {
            "recommendation": (
                "construction_candidate_requires_package_and_professional_review"
                if no_failures and all_required_production_depth
                else "block_construction_not_production_depth"
            ),
            "minimum_depth_score": 100.0,
            "production_depth_requirements_met": bool(no_failures and all_required_production_depth),
            "truth_label": "No construction-ready label is emitted unless selected required engines meet production-depth requirements.",
        },
    }


def sanitize_engine_depth_audit_report(report: Dict[str, Any]) -> Dict[str, Any]:
    return safe_dict(report)


def write_engine_depth_audit_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(sanitize_engine_depth_audit_report(report), handle, indent=2, sort_keys=True)


def run_engine_depth_audit(
    *,
    scenario_ids: Optional[Iterable[str]] = None,
    build_plan_fn: Optional[BuildPlanFn] = None,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run Phase 1 backend-only engine depth truth measurement."""

    selected_ids = [safe_str(item) for item in scenario_ids or [scenario.scenario_id for scenario in golden_scenarios()] if safe_str(item)]
    results = [
        run_engine_depth_audit_scenario(scenario_id, build_plan_fn=build_plan_fn)
        for scenario_id in selected_ids
    ]
    blockers = [blocker for result in results for blocker in safe_list(result.get("blockers"))]
    deterministic_checks = [check for result in results for check in safe_list(result.get("deterministic_checks"))]
    failed_checks = [check for check in deterministic_checks if not bool(safe_dict(check).get("passed"))]
    contracts = list(engine_contracts())
    engine_results = _engine_depth_summary(contracts=contracts, scenario_results=results)
    production_depth_count = len(
        [
            row
            for row in engine_results.values()
            if row.get("actual_depth_classification") == CLASS_PRODUCTION_DEPTH
        ]
    )
    review_count = len([row for row in engine_results.values() if row.get("actual_depth_classification") == CLASS_REVIEW])
    concept_count = len([row for row in engine_results.values() if row.get("actual_depth_classification") == CLASS_CONCEPT])
    required_rows = [row for row in engine_results.values() if safe_list(row.get("required_scenario_ids"))]
    scored_rows = [row for row in required_rows if row.get("classification") != CLASS_NOT_APPLICABLE]
    overall_depth_score = (
        sum(float(row.get("score") or 0.0) for row in scored_rows) / len(scored_rows)
        if scored_rows
        else 0.0
    )
    status = "passed" if not blockers and not failed_checks else "failed"
    gate_recommendations = _gate_recommendations(
        status=status,
        overall_depth_score=overall_depth_score,
        failed_check_count=len(failed_checks),
        blocker_count=len(blockers),
        required_rows=required_rows,
    )
    report = {
        "version": REPORT_VERSION,
        "phase": "phase_1_engine_depth_audit",
        "status": status,
        "success": status == "passed",
        "backend_readiness_gate_label": "phase_1_backend_depth_audit_passed" if status == "passed" else "phase_1_backend_depth_audit_blocked",
        "construction_ready": False,
        "construction_release_allowed": False,
        "construction_depth_requirements_met": bool(gate_recommendations["construction"]["production_depth_requirements_met"]),
        "engine_count": len(engine_results),
        "scenario_count": len(results),
        "deterministic_check_count": len(deterministic_checks),
        "failed_deterministic_check_count": len(failed_checks),
        "classification_counts": {
            CLASS_CONCEPT: concept_count,
            CLASS_REVIEW: review_count,
            CLASS_PRODUCTION_DEPTH: production_depth_count,
        },
        "summary": {
            "overall_depth_score": round(overall_depth_score, 2),
            "status": status,
            "backend_readiness_gate_label": "phase_1_backend_depth_audit_passed" if status == "passed" else "phase_1_backend_depth_audit_blocked",
            "private_alpha_gate_recommendation": gate_recommendations["private_alpha"]["recommendation"],
            "public_beta_gate_recommendation": gate_recommendations["public_beta"]["recommendation"],
            "construction_gate_recommendation": gate_recommendations["construction"]["recommendation"],
            "gate_recommendations": gate_recommendations,
            "required_engine_count": len(required_rows),
            "production_depth_engine_count": production_depth_count,
            "review_engine_count": review_count,
            "concept_engine_count": concept_count,
            "truth_label": "Summary is designed for CI and chat handoff; construction remains blocked unless production-depth requirements are met.",
        },
        "engine_rows": list(engine_results.values()),
        "engine_results": engine_results,
        "scenario_results": results,
        "deterministic_checks": deterministic_checks,
        "failed_check_ids": [safe_str(item.get("check_id")) for item in failed_checks],
        "blocker_count": len(blockers),
        "blockers": blockers,
        "blocker_details": readiness_issue_explanations(blockers),
        "truth_label": (
            "Phase 1 Engine Depth Audit measures backend evidence depth with deterministic expected-vs-actual checks. "
            "It does not modify UI, import standards, deepen engines, or authorize construction release."
        ),
    }
    report["engine_depth_dashboard_v1"] = build_engine_depth_dashboard(report)
    if output_path is not None:
        write_engine_depth_audit_report(Path(output_path), report)
    return report


def run_engine_depth_audit_for_scenario(
    scenario_id: str,
    *,
    build_plan_fn: Optional[BuildPlanFn] = None,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return a full engine_depth_audit_report_v1 scoped to one scenario."""

    return run_engine_depth_audit(
        scenario_ids=[scenario_id],
        build_plan_fn=build_plan_fn,
        output_path=output_path,
    )


__all__ = [
    "CLASS_CONCEPT",
    "CLASS_NOT_APPLICABLE",
    "CLASS_NOT_AUDITED",
    "CLASS_PRODUCTION_DEPTH",
    "CLASS_REVIEW",
    "REPORT_VERSION",
    "run_engine_depth_audit",
    "run_engine_depth_audit_for_scenario",
    "run_engine_depth_audit_scenario",
    "sanitize_engine_depth_audit_report",
    "write_engine_depth_audit_report",
]
