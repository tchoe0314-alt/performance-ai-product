from __future__ import annotations

from typing import Any, Dict, Iterable, Sequence

from .common import readiness_issue_explanations, safe_dict, safe_list, safe_str


DASHBOARD_VERSION = "engine_depth_dashboard_v1"


def _engine_fix_link(engine_id: str, blockers: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    first = safe_dict(blockers[0]) if blockers else {}
    scenario_id = safe_str(first.get("scenario_id"))
    field = safe_str(first.get("field") or first.get("area") or "engine_depth")
    return {
        "label": f"Fix {engine_id.replace('_', ' ')} evidence",
        "target_panel": _target_panel_for_engine(engine_id),
        "blocker_anchor": ":".join(item for item in [scenario_id, engine_id, field] if item),
        "suggested_next_action": safe_str(
            first.get("suggested_next_action"),
            "Restore deterministic backend evidence, rerun the affected engine, then rerun the engine depth audit.",
        ),
    }


def _target_panel_for_engine(engine_id: str) -> str:
    if engine_id in {"grading", "terrain_surface", "earthwork"}:
        return "grading"
    if engine_id in {"drainage", "storm_pipe", "hydrology"}:
        return "drainage"
    if engine_id == "sanitary":
        return "sanitary"
    if engine_id in {"water", "utility_coordination", "conflict_resolution"}:
        return "utilities"
    if engine_id == "roadway_corridor":
        return "roadway"
    if engine_id in {"export_cad", "profile_section", "quantity", "qa_validation"}:
        return "deliverables"
    if engine_id in {"gis_existing_conditions", "geometry"}:
        return "site_existing"
    return "analysis"


def _proof_item_from_blocker(blocker: Dict[str, Any], index: int) -> Dict[str, Any]:
    engine_id = safe_str(blocker.get("engine_id"))
    scenario_id = safe_str(blocker.get("scenario_id"))
    field = safe_str(blocker.get("field") or blocker.get("area"), "proof")
    return {
        "id": ":".join(item for item in ["proof", scenario_id, engine_id, field, str(index)] if item),
        "engine_id": engine_id,
        "scenario_id": scenario_id,
        "label": safe_str(blocker.get("message"), f"Missing proof for {field.replace('_', ' ')}"),
        "status": "missing",
        "severity": safe_str(blocker.get("severity"), "blocker"),
        "why_needed": safe_str(blocker.get("why_needed") or blocker.get("message")),
        "suggested_next_action": safe_str(blocker.get("suggested_next_action")),
        "target_panel": _target_panel_for_engine(engine_id),
        "blocker_anchor": ":".join(item for item in [scenario_id, engine_id, field] if item),
    }


def _history_point(report: Dict[str, Any], index: int) -> Dict[str, Any]:
    summary = safe_dict(report.get("summary"))
    return {
        "index": index,
        "version": safe_str(report.get("version")),
        "status": safe_str(report.get("status") or summary.get("status"), "unknown"),
        "overall_depth_score": float(summary.get("overall_depth_score") or 0.0),
        "scenario_count": int(report.get("scenario_count") or 0),
        "blocker_count": int(report.get("blocker_count") or 0),
        "failed_check_count": int(report.get("failed_deterministic_check_count") or 0),
    }


def build_engine_depth_dashboard(
    report: Dict[str, Any],
    *,
    history_reports: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Build a compact dashboard contract from an engine_depth_audit_report_v1."""

    source = safe_dict(report)
    summary = safe_dict(source.get("summary"))
    engine_rows = [safe_dict(row) for row in safe_list(source.get("engine_rows"))]
    scenario_results = [safe_dict(row) for row in safe_list(source.get("scenario_results"))]
    blockers = [safe_dict(item) for item in safe_list(source.get("blockers"))]
    failed_checks = [safe_dict(item) for item in safe_list(source.get("deterministic_checks")) if not bool(safe_dict(item).get("passed"))]

    per_engine = []
    for row in sorted(engine_rows, key=lambda item: (float(item.get("score") or 0.0), safe_str(item.get("engine_id")))):
        row_blockers = [safe_dict(item) for item in safe_list(row.get("blockers"))]
        required_scenarios = safe_list(row.get("required_scenario_ids"))
        proof_checklist = [safe_dict(item) for item in safe_list(row.get("proof_checklist"))]
        missing_proof = [safe_dict(item) for item in safe_list(row.get("missing_proof"))]
        per_engine.append(
            {
                "engine_id": safe_str(row.get("engine_id")),
                "name": safe_str(row.get("name") or row.get("engine_id")),
                "score": float(row.get("score") or 0.0),
                "classification": safe_str(row.get("classification") or row.get("actual_depth_classification")),
                "required_scenario_ids": required_scenarios,
                "scenario_coverage_count": len(required_scenarios),
                "failed_check_count": int(row.get("failed_check_count") or 0),
                "blocker_count": len(row_blockers),
                "launch_gate": safe_str(row.get("launch_gate")),
                "confidence": float(row.get("confidence") or 0.0),
                "first_failing_layer": safe_str(row.get("first_failing_layer")),
                "proof_checklist": proof_checklist,
                "missing_proof": missing_proof,
                "exact_fixes": safe_list(row.get("exact_fixes")),
                "engineer_review_required": True,
                "proof_status": "missing_proof" if missing_proof else "proof_present",
                "fix_link": _engine_fix_link(safe_str(row.get("engine_id")), row_blockers),
            }
        )

    scenario_coverage = []
    for scenario in scenario_results:
        required_engine_ids = safe_list(scenario.get("required_engine_ids"))
        required_engine_results = safe_dict(scenario.get("required_engine_results"))
        passed_engines = [
            engine_id
            for engine_id, row in required_engine_results.items()
            if safe_dict(row).get("failed_check_count") in (0, None) and safe_str(safe_dict(row).get("classification")) != "concept"
        ]
        coverage_percent = (len(passed_engines) / len(required_engine_ids) * 100.0) if required_engine_ids else 0.0
        scenario_coverage.append(
            {
                "scenario_id": safe_str(scenario.get("scenario_id")),
                "name": safe_str(scenario.get("name") or scenario.get("scenario_id")),
                "status": safe_str(scenario.get("status"), "unknown"),
                "depth_score": float(scenario.get("depth_score") or 0.0),
                "required_engine_count": len(required_engine_ids),
                "covered_engine_count": len(passed_engines),
                "coverage_percent": round(coverage_percent, 2),
                "failed_check_ids": safe_list(scenario.get("failed_check_ids")),
                "blocker_count": len(safe_list(scenario.get("blockers"))),
                "blocker_link": {
                    "label": "Open scenario blockers",
                    "target_panel": "analysis",
                    "blocker_anchor": safe_str(scenario.get("scenario_id")),
                },
            }
        )

    proof_items = [_proof_item_from_blocker(blocker, index) for index, blocker in enumerate(blockers)]
    proof_index = len(proof_items)
    for row in engine_rows:
        for missing in safe_list(row.get("missing_proof")):
            rec = safe_dict(missing)
            proof_items.append(
                {
                    "id": f"missing-proof:{safe_str(row.get('engine_id'))}:{safe_str(rec.get('id'))}:{proof_index}",
                    "engine_id": safe_str(row.get("engine_id")),
                    "scenario_id": ",".join(safe_list(row.get("required_scenario_ids"))),
                    "label": f"Missing {safe_str(rec.get('label'), 'discipline proof')}",
                    "status": "missing",
                    "severity": "blocker",
                    "why_needed": "Discipline depth cannot be treated as production-depth without this proof surface.",
                    "suggested_next_action": (safe_list(row.get("exact_fixes")) or ["Provide missing proof and rerun the engine depth audit."])[0],
                    "target_panel": _target_panel_for_engine(safe_str(row.get("engine_id"))),
                    "blocker_anchor": f"{safe_str(row.get('engine_id'))}:{safe_str(rec.get('id'))}",
                }
            )
            proof_index += 1
    for index, check in enumerate(failed_checks):
        if safe_str(check.get("engine_id")):
            proof_items.append(
                {
                    "id": f"failed-check:{safe_str(check.get('check_id')) or index}",
                    "engine_id": safe_str(check.get("engine_id")),
                    "scenario_id": safe_str(check.get("scenario_id")),
                    "label": f"Failed deterministic check: {safe_str(check.get('check_id'))}",
                    "status": "missing",
                    "severity": "blocker",
                    "why_needed": safe_str(check.get("truth_label")),
                    "suggested_next_action": "Inspect the failing expected-vs-actual record, restore deterministic evidence, and rerun the audit.",
                    "target_panel": _target_panel_for_engine(safe_str(check.get("engine_id"))),
                    "blocker_anchor": safe_str(check.get("check_id")),
                }
            )

    history_sources = [safe_dict(item) for item in (history_reports or []) if safe_dict(item)]
    if not history_sources:
        history_sources = [source]
    trend_history = [_history_point(item, index) for index, item in enumerate(history_sources)]

    return {
        "version": DASHBOARD_VERSION,
        "source_report_version": safe_str(source.get("version")),
        "status": safe_str(source.get("status") or summary.get("status"), "unknown"),
        "overall_depth_score": float(summary.get("overall_depth_score") or 0.0),
        "engine_count": int(source.get("engine_count") or len(engine_rows)),
        "scenario_count": int(source.get("scenario_count") or len(scenario_results)),
        "failed_check_count": int(source.get("failed_deterministic_check_count") or len(failed_checks)),
        "blocker_count": int(source.get("blocker_count") or len(blockers)),
        "per_engine_scores": per_engine,
        "scenario_coverage": scenario_coverage,
        "missing_proof_checklist": proof_items,
        "trend_history": trend_history,
        "blocker_details": readiness_issue_explanations(blockers),
        "fix_links": [row["fix_link"] for row in per_engine if row.get("blocker_count")],
        "construction_release_allowed": False,
        "truth_label": (
            "Engine depth dashboard summarizes deterministic backend audit evidence for review. "
            "It does not certify construction readiness or replace licensed professional review."
        ),
    }


__all__ = ["DASHBOARD_VERSION", "build_engine_depth_dashboard"]
