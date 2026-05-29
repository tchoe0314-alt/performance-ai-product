from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List
from unittest.mock import patch

from planner import build_plan


def _base_payload() -> Dict[str, Any]:
    return {
        "project_name": "Benchmark Case",
        "units": "ft",
        "mode": "site_plan",
        "project_type": "commercial_pad",
        "site_type": "commercial_pad",
        "lot": {"x": 0.0, "y": 0.0, "w": 140.0, "h": 110.0},
        "setback": 10.0,
        "street_edge": "bottom",
        "layout_strategy": "front_parking",
        "site_plan": {"building_width": 48.0, "building_depth": 34.0, "parking_count": 24},
    }


def _mode_payload(input_mode: str, **overrides: Any) -> Dict[str, Any]:
    payload = _base_payload()
    payload["meta"] = {
        "input_mode": input_mode,
        "source_input_mode": input_mode,
        "manual_mode": input_mode == "manual",
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


def _failure_codes(plan: Dict[str, Any]) -> List[str]:
    return [str(item.get("code") or "") for item in ((((plan.get("meta") or {}).get("manual_validation") or {}).get("failures")) or [])]


def _key_messages(plan: Dict[str, Any]) -> List[str]:
    failures = _failure_codes(plan)
    if failures:
        return failures[:4]
    qa_issues = (((plan.get("meta") or {}).get("qa") or {}).get("issues")) or []
    messages = [str(item.get("message") or "") for item in qa_issues if str(item.get("message") or "")]
    return messages[:4]


def _summarize(plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = plan.get("meta") or {}
    engineering = meta.get("engineering_status") or {}
    coordination = meta.get("coordination") or {}
    truth = meta.get("truth_audit") or {}
    completeness = meta.get("stage_completeness") or {}
    unresolved = coordination.get("unresolved_conflicts") or []
    if isinstance(unresolved, int):
        unresolved_count = unresolved
    else:
        unresolved_count = len(unresolved)
    return {
        "pass": bool(engineering.get("success")),
        "manual_failures": _failure_codes(plan),
        "unresolved_conflicts": unresolved_count,
        "selected_strategy": coordination.get("selected_group_strategy") or "none",
        "key_messages": _key_messages(plan),
        "trust_score": float(engineering.get("engineering_trust_score") or truth.get("engineering_trust_score") or 0.0),
        "all_required_complete": bool(completeness.get("all_required_complete")),
        "truth_success": bool(truth.get("success")),
    }


def _healthy_scenario() -> Dict[str, Any]:
    deliverables = ["road_profile", "cross_sections", "storm_pipe_plan", "utility_plan"]
    verified_drainage = {
        "verified_overflow_capacity_cfs": 12.0,
        "overflow_verification_source": "benchmark_controlled_fixture",
    }
    manual = build_plan(_mode_payload("manual", deliverables=deliverables, drainage=verified_drainage))
    assisted = build_plan(_mode_payload("assisted", deliverables=deliverables, drainage=verified_drainage))
    return {"name": "healthy_clean", "manual": _summarize(manual), "assisted": _summarize(assisted)}


def _conflict_heavy_scenario() -> Dict[str, Any]:
    payload_overrides = {
        "deliverables": ["road_profile", "cross_sections", "storm_pipe_plan", "sanitary_plan", "utility_plan"],
        "drainage": {
            "verified_overflow_capacity_cfs": 12.0,
            "overflow_verification_source": "benchmark_controlled_fixture",
        },
        "site_plan": {
            "building_width": 52.0,
            "building_depth": 36.0,
            "parking_count": 26,
        },
    }
    manual = build_plan(_mode_payload("manual", **payload_overrides))
    assisted = build_plan(_mode_payload("assisted", **payload_overrides))
    return {"name": "conflict_heavy_trench", "manual": _summarize(manual), "assisted": _summarize(assisted)}


def _degraded_invalid_scenario() -> Dict[str, Any]:
    import planner as planner_module

    original = planner_module._run_storm_pipe_stage

    def wrapped(ctx, hydrology):
        original(ctx, hydrology)
        storm = deepcopy(ctx.manager.latest_outputs.get("storm_pipe_summary", {}))
        storm["graph_validation"] = {
            "system": "storm",
            "segment_count": 1,
            "node_count": 3,
            "disconnected_runs": [],
            "loop_nodes": [],
            "duplicate_segments": [],
            "duplicate_edges": [],
            "invalid_direction_segments": [{"segment_id": "P-1"}],
            "illegal_branch_nodes": [],
            "orphan_nodes": ["ORPHAN-1"],
            "unreasonable_degree_nodes": [],
            "valid": False,
        }
        storm["hydraulic_validation"] = {
            "system": "storm",
            "geometry_only_segments": ["P-1"],
            "missing_accumulation_segments": ["P-1"],
            "invalid_capacity_ratio_segments": [],
            "downstream_total_inconsistencies": [],
            "valid": False,
        }
        ctx.manager.latest_outputs["storm_pipe_summary"] = storm
        ctx.manager.project.meta["storm_pipe_summary"] = deepcopy(storm)

    with patch("planner._run_storm_pipe_stage", side_effect=wrapped):
        manual = build_plan(_mode_payload("manual"))
        assisted = build_plan(_mode_payload("assisted"))
    return {"name": "degraded_invalid", "manual": _summarize(manual), "assisted": _summarize(assisted)}


def run_benchmark_suite() -> List[Dict[str, Any]]:
    return [
        _healthy_scenario(),
        _conflict_heavy_scenario(),
        _degraded_invalid_scenario(),
    ]


if __name__ == "__main__":
    for item in run_benchmark_suite():
        print(item)
