from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Sequence

from .common import dedupe_keep_order, safe_dict, safe_float, safe_int, safe_list, safe_str


def _protected_hits_from_candidate(candidate: Dict[str, Any], deltas: Dict[str, Any]) -> list[Dict[str, Any]]:
    hits = [deepcopy(safe_dict(item)) for item in safe_list(candidate.get("protected_zone_hits")) if safe_dict(item)]
    if hits:
        return hits
    impact = safe_dict(deltas.get("protected_zone_impact"))
    return [
        {
            "kind": safe_str(kind),
            "name": "",
            "penalty": 0.0,
            "avoid": False,
        }
        for kind in safe_list(impact.get("hit_kinds"))
        if safe_str(kind)
    ]


def _crossing_issues(candidate: Dict[str, Any], deltas: Dict[str, Any]) -> list[Dict[str, Any]]:
    crossing = safe_dict(candidate.get("crossing_hierarchy")) or safe_dict(deltas.get("crossing_hierarchy"))
    if not crossing:
        return []
    issues: list[Dict[str, Any]] = []
    total_checks = safe_int(crossing.get("total_checks"), 0)
    compliant_checks = safe_int(crossing.get("compliant_checks"), 0)
    if bool(crossing.get("blocked")) or safe_float(crossing.get("penalty"), 0.0) > 0.0 or (total_checks and compliant_checks < total_checks) or crossing.get("compliant") is False:
        issues.append(
            {
                "rule": safe_str(crossing.get("rule"), "crossing_hierarchy"),
                "blocked": bool(crossing.get("blocked")),
                "penalty": round(safe_float(crossing.get("penalty"), 0.0), 3),
                "preferred_lower_system": safe_str(crossing.get("preferred_lower_system")),
                "preferred_crossing_angle_deg": safe_float(crossing.get("preferred_crossing_angle_deg"), 0.0),
                "actual_crossing_angle_deg": safe_float(crossing.get("actual_crossing_angle_deg"), 0.0),
                "interaction_types": deepcopy(safe_list(crossing.get("interaction_types"))),
                "reason": safe_str(crossing.get("reason")),
            }
        )
    return issues


def _unresolved_flags(candidate: Dict[str, Any], protected_hits: Sequence[Dict[str, Any]], crossing_issues: Sequence[Dict[str, Any]], grading: Dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if safe_int(candidate.get("remaining_related_conflicts"), 0) > 0 or safe_int(candidate.get("remaining_total_conflicts"), 0) > 0:
        flags.append("remaining_conflicts")
    if safe_dict(candidate.get("failure_breakdown")).get("remaining_conflict_ids"):
        flags.append("remaining_conflicts")
    if any(bool(safe_dict(hit).get("avoid")) for hit in protected_hits):
        flags.append("protected_zone_hit")
    if any(bool(safe_dict(issue).get("blocked")) for issue in crossing_issues):
        flags.append("crossing_hierarchy_blocked")
    if bool(grading.get("blocked")):
        flags.append("grading_blocked")
    if safe_dict(candidate.get("post_validation")).get("valid") is False:
        flags.append("post_validation_failed")
    if safe_dict(candidate.get("failure_breakdown")).get("assumption_used"):
        flags.append("assumption_used")
    return dedupe_keep_order(flags)


def coordination_realism_summary(
    candidate: Dict[str, Any],
    *,
    group: Dict[str, Any] | None = None,
    conflict: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Summarize coordination realism from already-computed candidate data."""

    rec = safe_dict(candidate)
    deltas = safe_dict(rec.get("engineering_deltas"))
    constructability = safe_dict(rec.get("constructability")) or safe_dict(deltas.get("constructability_impact"))
    protected_hits = _protected_hits_from_candidate(rec, deltas)
    crossing_issues = _crossing_issues(rec, deltas)
    grading = safe_dict(deltas.get("grading_impact"))
    inserted = safe_dict(rec.get("inserted_structures"))
    structure_count = max(
        safe_int(inserted.get("added_count"), 0),
        safe_int(constructability.get("added_structures"), 0),
        safe_int(safe_dict(deltas.get("crossing_strategy_prefit")).get("added_structures"), 0),
        safe_int(safe_dict(deltas.get("geometry_strategy_prefit")).get("added_structures"), 0),
        safe_int(deltas.get("added_structures"), 0),
    )
    group_rec = safe_dict(group)
    conflict_rec = safe_dict(conflict)
    ownership_class = safe_str(rec.get("ownership_class")) or safe_str(safe_dict(rec.get("ownership_impacts")).get("ownership_class"))
    changed_systems = [safe_str(item) for item in safe_list(rec.get("changed_systems")) if safe_str(item)]
    if not ownership_class and changed_systems:
        ownership_class = safe_str(changed_systems[0])
    notes = [safe_str(item) for item in safe_list(rec.get("notes")) if safe_str(item)]
    if safe_str(rec.get("why_failed")):
        notes.append(safe_str(rec.get("why_failed")))
    flags = _unresolved_flags(rec, protected_hits, crossing_issues, grading)
    return {
        "constructability_score": round(
            safe_float(rec.get("constructability_score"), safe_float(constructability.get("score"), 0.0)),
            3,
        ),
        "corridor_impact": deepcopy(safe_dict(deltas.get("corridor_impact"))) or {"penalty": round(safe_float(rec.get("corridor_penalty"), 0.0), 3)},
        "protected_zone_hits": protected_hits,
        "crossing_hierarchy_issues": crossing_issues,
        "ownership_class": ownership_class,
        "ownership_impacts": {
            "target": safe_str(rec.get("target")),
            "changed_systems": changed_systems,
            "ownership_class": ownership_class,
            "systems": deepcopy(safe_list(conflict_rec.get("systems") or group_rec.get("systems"))),
        },
        "structure_insertion_count": structure_count,
        "grading_impact": deepcopy(grading),
        "trench_grouping_context": {
            "cluster_id": safe_str(group_rec.get("cluster_id") or rec.get("cluster_id")),
            "cluster_group_id": safe_str(group_rec.get("cluster_group_id") or rec.get("cluster_group_id")),
            "trench_like": bool(group_rec.get("trench_like") or rec.get("group_prefit_applied")),
            "group_plan": safe_str(rec.get("group_plan") or rec.get("plan_name")),
            "selected_group_strategy": safe_str(rec.get("selected_group_strategy") or rec.get("crossing_strategy")),
            "geometry_strategy": safe_str(rec.get("geometry_strategy")),
        },
        "unresolved_realism_flags": flags,
        "realism_notes": dedupe_keep_order(notes),
    }


def coordination_realism_from_summary(coordination: Dict[str, Any]) -> Dict[str, Any]:
    """Build a final canonical coordination realism rollup from a coordination summary."""

    summary = safe_dict(coordination)
    resolved = [safe_dict(item) for item in safe_list(summary.get("resolved_conflicts")) if safe_dict(item)]
    unresolved = [safe_dict(item) for item in safe_list(summary.get("unresolved_clusters") or summary.get("unresolved_conflicts")) if safe_dict(item)]
    selected: list[Dict[str, Any]] = []
    best_near: list[Dict[str, Any]] = []
    flags: list[str] = []
    for row in resolved:
        realism = safe_dict(safe_dict(row.get("resolution")).get("coordination_realism"))
        if realism:
            selected.append(deepcopy(realism))
            flags.extend(safe_list(realism.get("unresolved_realism_flags")))
    for row in unresolved:
        realism = safe_dict(row.get("coordination_realism")) or safe_dict(safe_dict(row.get("best_near_valid_candidate")).get("coordination_realism"))
        if realism:
            best_near.append(deepcopy(realism))
            flags.extend(safe_list(realism.get("unresolved_realism_flags")))
    return {
        "selected_candidates": selected,
        "best_near_valid_candidates": best_near,
        "unresolved_realism_flags": dedupe_keep_order(safe_str(item) for item in flags if safe_str(item)),
        "resolved_count": safe_int(summary.get("resolved_count"), len(resolved)),
        "unresolved_count": safe_int(summary.get("unresolved_count"), len(unresolved)),
    }
