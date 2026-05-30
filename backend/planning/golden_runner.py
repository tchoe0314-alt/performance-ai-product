from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, List, Optional

from .common import safe_dict, safe_float, safe_int, safe_list, safe_str
from .golden_scenarios import GoldenScenario, get_golden_scenario, golden_scenarios


BuildPlanFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def _default_build_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    import planner

    return planner.build_plan(payload)


def _readiness_summary(plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    civil = safe_dict(meta.get("civil_design_readiness"))
    engine = safe_dict(meta.get("engine_readiness"))
    construction = safe_dict(meta.get("construction_readiness"))
    construction_package = safe_dict(meta.get("construction_package_manifest"))
    artifact_status = safe_dict(construction_package.get("construction_package_artifact_status"))
    professional_release = safe_dict(construction_package.get("professional_package_release_status"))
    return {
        "civil_status": safe_str(civil.get("status")),
        "civil_success": bool(civil.get("success")),
        "civil_production_ready": bool(civil.get("production_ready")),
        "construction_ready": bool(construction.get("ready")),
        "construction_release_allowed": bool(construction_package.get("release_allowed")),
        "construction_package_complete_for_release": bool(artifact_status.get("complete_for_release")),
        "construction_package_model_matches_expected": bool(artifact_status.get("model_matches_expected")),
        "construction_package_release_ready_flag": artifact_status.get("release_ready_flag") is True,
        "construction_package_production_ready_flag": artifact_status.get("production_ready_flag") is True,
        "construction_package_missing_artifacts": safe_list(artifact_status.get("missing")),
        "professional_review_present": bool(professional_release.get("professional_review_present")),
        "professional_release_valid": bool(professional_release.get("professional_release_valid")),
        "professional_release_model_matches_package": bool(professional_release.get("model_matches_package")),
        "professional_release_package_matches_review": bool(professional_release.get("package_matches_review")),
        "critical_blocker_count": len(safe_list(civil.get("critical_blockers"))),
        "production_blocker_count": len(safe_list(civil.get("production_blockers"))),
        "construction_blocker_count": len(safe_list(construction.get("blockers"))),
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


def _has_required_signal(signal: str, plan: Dict[str, Any]) -> bool:
    meta = safe_dict(plan.get("meta"))
    actions = safe_list(plan.get("actions"))
    signal_key = safe_str(signal)
    if not signal_key:
        return False

    if signal_key == "site_boundary":
        lot = safe_dict(meta.get("lot") or safe_dict(meta.get("site")).get("lot"))
        if safe_float(lot.get("w"), 0.0) > 0.0 and safe_float(lot.get("h"), 0.0) > 0.0:
            return True
        return any(safe_str(action.get("canonical_source_type")) == "site" or safe_str(action.get("layer")).upper() == "SITE" for action in actions)
    if signal_key == "building_count":
        return safe_int(meta.get("building_count"), 0) > 0 or any(safe_str(action.get("layer")).upper() in {"BUILDING", "STRUCTURE"} for action in actions)
    if signal_key == "existing_surface":
        grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
        return bool(safe_dict(grading.get("existing_surface")) or safe_dict(meta.get("existing_surface")) or safe_dict(meta.get("survey")))
    if signal_key == "proposed_surface":
        grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
        return bool(safe_dict(grading.get("proposed_surface")))
    if signal_key == "low_points":
        grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
        drainage = safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
        return bool(safe_list(grading.get("low_points")) or safe_list(drainage.get("low_points")))
    if signal_key == "basins":
        drainage = safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
        return bool(safe_list(drainage.get("basins")))
    if signal_key == "detention_routing":
        drainage = safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
        return bool(safe_list(drainage.get("detention_routing")) or safe_list(drainage.get("stage_storage")) or safe_dict(meta.get("detention_routing")))
    if signal_key == "floodplain_data":
        return bool(safe_dict(meta.get("floodplain")) or safe_dict(safe_dict(meta.get("existing_conditions")).get("floodplain")))
    if signal_key == "wetland_data":
        return bool(safe_dict(meta.get("wetlands")) or safe_dict(safe_dict(meta.get("existing_conditions")).get("wetlands")))
    if signal_key == "protected_zones":
        return bool(safe_list(meta.get("protected_zones")) or safe_list(safe_dict(meta.get("existing_conditions")).get("protected_zones")))
    if signal_key == "road_crown_controls":
        grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
        return bool(safe_list(grading.get("road_crown_controls")) or safe_list(meta.get("road_crown_controls")))
    if signal_key == "wall_tie_in_checks":
        structures = safe_dict(meta.get("structures"))
        grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
        return bool(safe_list(structures.get("wall_tie_in_checks")) or safe_list(grading.get("wall_tie_in_checks")))
    if signal_key == "retaining_walls":
        structures = safe_dict(meta.get("structures"))
        return bool(safe_list(structures.get("retaining_walls")) or safe_list(meta.get("retaining_walls")))
    if signal_key == "resolution_history":
        coordination = safe_dict(meta.get("coordination") or meta.get("coordination_summary"))
        return bool(safe_list(coordination.get("resolution_history")) or safe_list(coordination.get("resolved_conflicts")))
    if signal_key == "sheet_registry":
        return bool(safe_list(meta.get("sheet_registry")) or safe_dict(meta.get("sheet_registry")))
    if signal_key == "existing_conditions":
        return bool(safe_dict(meta.get("existing_conditions")) or safe_dict(meta.get("survey")) or safe_dict(meta.get("gis_layers")) or safe_dict(meta.get("existing_conditions_summary")))
    if signal_key == "earthwork":
        return bool(safe_dict(meta.get("earthwork")) or safe_dict(safe_dict(meta.get("grading") or meta.get("grading_summary")).get("earthwork")))
    if signal_key in {"manual_validation", "truth_audit", "civil_design_readiness", "engine_readiness", "parking_program", "quantities", "coordination"}:
        return bool(safe_dict(meta.get(signal_key)))
    if signal_key == "grading":
        return bool(safe_dict(meta.get("grading") or meta.get("grading_summary")))
    if signal_key == "drainage":
        return bool(safe_dict(meta.get("drainage") or meta.get("drainage_canonical")))
    if signal_key == "storm_pipes":
        return bool(safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary")))
    if signal_key == "sanitary":
        return bool(safe_dict(meta.get("sanitary") or meta.get("sanitary_summary")))
    if signal_key == "utilities":
        return bool(safe_dict(meta.get("utilities") or meta.get("utility_summary")))
    if signal_key == "alignments":
        return bool(safe_list(meta.get("alignments")))
    if signal_key == "profiles":
        return bool(safe_list(meta.get("profiles")))
    if signal_key == "cross_sections":
        return bool(safe_list(meta.get("cross_sections")))
    if signal_key == "hydrology_summary":
        return bool(safe_dict(meta.get("hydrology_summary")))
    if signal_key == "missing_requirements":
        readiness = safe_dict(meta.get("civil_design_readiness"))
        return bool(safe_list(readiness.get("missing_requirements")) or safe_list(readiness.get("production_blockers")))
    return bool(meta.get(signal_key))


def _canonical_signal_results(scenario: GoldenScenario, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "signal": signal,
            "present": _has_required_signal(signal, plan),
            "truth_label": "Required canonical signal must be produced or explicitly blocked for this golden scenario.",
        }
        for signal in scenario.required_canonical_signals
    ]


def _sum_lengths(items: Iterable[Any]) -> float:
    total = 0.0
    for item in items:
        rec = safe_dict(item)
        total += safe_float(rec.get("length_ft") or rec.get("length"), 0.0)
    return total


def _benchmark_metric_value(metric: str, plan: Dict[str, Any]) -> Any:
    meta = safe_dict(plan.get("meta"))
    actions = safe_list(plan.get("actions"))
    readiness = safe_dict(meta.get("civil_design_readiness"))
    quantities = safe_dict(meta.get("quantities"))
    totals = safe_dict(quantities.get("totals"))
    grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
    drainage = safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
    storm = safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))
    sanitary = safe_dict(meta.get("sanitary") or meta.get("sanitary_summary"))
    utilities = safe_dict(meta.get("utilities") or meta.get("utility_summary"))
    coordination = safe_dict(meta.get("coordination") or meta.get("coordination_summary"))
    signal = safe_str(metric)
    if signal == "civil_production_ready":
        return bool(readiness.get("production_ready"))
    if signal == "critical_blocker_count":
        return len(safe_list(readiness.get("critical_blockers")))
    if signal == "production_blocker_count":
        return len(safe_list(readiness.get("production_blockers")))
    if signal == "lot_area_sf":
        lot = safe_dict(meta.get("lot") or safe_dict(meta.get("site")).get("lot") or meta.get("site_boundary"))
        area = safe_float(totals.get("lot_area_sf"), 0.0)
        if area <= 0.0:
            area = safe_float(lot.get("area_sf") or lot.get("area"), 0.0)
        if area <= 0.0:
            area = safe_float(lot.get("w") or lot.get("width"), 0.0) * safe_float(lot.get("h") or lot.get("height"), 0.0)
        return area
    if signal == "building_count":
        value = safe_int(meta.get("building_count"), 0)
        if value <= 0:
            value = len([action for action in actions if safe_str(action.get("layer")).upper() in {"BUILDING", "STRUCTURE"}])
        return value
    if signal == "parking_count":
        return max(
            safe_int(meta.get("parking_count"), 0),
            safe_int(totals.get("estimated_parking_stalls"), 0),
            safe_int(safe_dict(meta.get("parking_program")).get("stall_count"), 0),
        )
    if signal == "storm_segment_count":
        return len(safe_list(storm.get("segments")))
    if signal == "sanitary_segment_count":
        return len(safe_list(sanitary.get("segments")))
    if signal == "utility_segment_count":
        return max(len(safe_list(utilities.get("segments"))), len(safe_list(safe_dict(utilities.get("conflict_hooks")).get("utility_segments"))))
    if signal == "pipe_length_ft":
        return max(safe_float(totals.get("pipe_length_ft"), 0.0), _sum_lengths(safe_list(storm.get("segments"))))
    if signal == "low_point_count":
        return max(len(safe_list(grading.get("low_points"))), len(safe_list(drainage.get("low_points"))))
    if signal == "basin_count":
        return len(safe_list(drainage.get("basins")))
    if signal == "alignment_count":
        return len(safe_list(meta.get("alignments")))
    if signal == "profile_count":
        return len(safe_list(meta.get("profiles")))
    if signal == "cross_section_count":
        return len(safe_list(meta.get("cross_sections")))
    if signal == "coordination_conflict_count":
        realism = safe_dict(coordination.get("coordination_realism") or meta.get("coordination_realism"))
        return max(
            safe_int(coordination.get("detected_conflicts"), 0),
            safe_int(coordination.get("conflict_count"), 0),
            len(safe_list(coordination.get("conflicts"))),
            len(safe_list(coordination.get("resolved_conflicts"))),
            len(safe_list(coordination.get("unresolved_conflicts"))),
            len(safe_list(realism.get("best_near_valid_candidates"))),
        )
    if signal == "protected_zone_count":
        return max(len(safe_list(meta.get("protected_zones"))), len(safe_list(safe_dict(meta.get("existing_conditions")).get("protected_zones"))))
    if signal == "retaining_wall_count":
        structures = safe_dict(meta.get("structures") or meta.get("structure_summary"))
        return max(len(safe_list(meta.get("retaining_walls"))), len(safe_list(structures.get("retaining_walls"))), len(safe_list(grading.get("retaining_walls"))))
    return meta.get(signal)


def _expectation_passes(expectation: Dict[str, Any], value: Any) -> bool:
    if "equals" in expectation:
        expected = expectation.get("equals")
        if isinstance(expected, bool):
            return bool(value) is expected
        return value == expected
    if value in (None, ""):
        return False
    numeric = safe_float(value, 0.0)
    if "min" in expectation and numeric < safe_float(expectation.get("min"), 0.0):
        return False
    if "max" in expectation and numeric > safe_float(expectation.get("max"), 0.0):
        return False
    return True


def _benchmark_expectation_results(scenario: GoldenScenario, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for expectation in scenario.benchmark_expectations:
        rec = safe_dict(expectation)
        metric = safe_str(rec.get("metric"))
        value = _benchmark_metric_value(metric, plan)
        results.append(
            {
                "metric": metric,
                "value": value,
                "min": rec.get("min"),
                "max": rec.get("max"),
                "equals": rec.get("equals") if "equals" in rec else None,
                "passed": _expectation_passes(rec, value),
                "truth_label": "Golden numeric expectations check plausible canonical engineering outputs, not permit approval.",
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
    signal_results = _canonical_signal_results(scenario, plan)
    expectation_results = _benchmark_expectation_results(scenario, plan)
    false_production_ready = bool(summary.get("civil_production_ready")) and bool(gates)
    hard_failures = []
    if false_production_ready:
        hard_failures.append("scenario_reported_production_ready_while_expected_blockers_exist")
    missing_signals = [item["signal"] for item in signal_results if not bool(item.get("present"))]
    if missing_signals:
        hard_failures.append("required_canonical_signals_missing")
    failed_expectations = [item["metric"] for item in expectation_results if not bool(item.get("passed"))]
    if failed_expectations:
        hard_failures.append("benchmark_numeric_expectations_failed")
    if not safe_dict(plan.get("meta")).get("engine_readiness"):
        hard_failures.append("engine_readiness_missing")
    if not safe_dict(plan.get("meta")).get("civil_design_readiness"):
        hard_failures.append("civil_design_readiness_missing")
    if not safe_dict(plan.get("meta")).get("construction_readiness"):
        hard_failures.append("construction_readiness_missing")
    if not safe_dict(plan.get("meta")).get("construction_package_manifest"):
        hard_failures.append("construction_package_manifest_missing")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("construction_ready")):
        hard_failures.append("construction_release_allowed_without_readiness")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("civil_production_ready")):
        hard_failures.append("construction_release_allowed_without_civil_production_ready")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("construction_package_complete_for_release")):
        hard_failures.append("construction_release_allowed_with_incomplete_package")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("construction_package_model_matches_expected")):
        hard_failures.append("construction_release_allowed_with_unverified_package_model")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("construction_package_release_ready_flag")):
        hard_failures.append("construction_release_allowed_without_explicit_package_release_flag")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("construction_package_production_ready_flag")):
        hard_failures.append("construction_release_allowed_without_explicit_package_production_flag")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("professional_review_present")):
        hard_failures.append("construction_release_allowed_without_professional_review")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("professional_release_valid")):
        hard_failures.append("construction_release_allowed_without_valid_professional_release")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("professional_release_model_matches_package")):
        hard_failures.append("construction_release_allowed_with_professional_model_mismatch")
    if bool(summary.get("construction_release_allowed")) and not bool(summary.get("professional_release_package_matches_review")):
        hard_failures.append("construction_release_allowed_with_professional_package_mismatch")
    return {
        "success": not hard_failures,
        "scenario_id": scenario.scenario_id,
        "name": scenario.name,
        "required_engine_ids": sorted(scenario.required_engine_ids),
        "required_canonical_signals": list(scenario.required_canonical_signals),
        "production_gates": list(scenario.production_gates),
        "readiness_summary": summary,
        "gate_results": gates,
        "canonical_signal_results": signal_results,
        "missing_canonical_signals": missing_signals,
        "benchmark_expectation_results": expectation_results,
        "failed_benchmark_expectations": failed_expectations,
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
