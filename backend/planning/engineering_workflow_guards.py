from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Sequence

from .common import dedupe_keep_order, lower_text, safe_dict, safe_float, safe_list, safe_str


WORKFLOW_REVIEW_VERSION = "engineering_generation_review_v1"

SYSTEM_META_KEYS: Dict[str, str] = {
    "grading": "grading",
    "drainage": "drainage",
    "storm": "storm_pipes",
    "sanitary": "sanitary",
    "water": "utilities",
    "utilities": "utilities",
    "roadway": "roadway",
    "quantities": "quantities",
    "qa_review": "qa",
}

SYSTEM_LABELS: Dict[str, str] = {
    "grading": "grading",
    "drainage": "drainage",
    "storm": "storm drainage",
    "sanitary": "sanitary sewer",
    "water": "water service",
    "utilities": "utility coordination",
    "roadway": "roadway",
    "quantities": "quantities",
    "qa_review": "QA/review",
}

INPUT_DEPENDENCIES: Dict[str, Sequence[str]] = {
    "grading": ("lot_geometry", "terrain", "standards"),
    "drainage": ("lot_geometry", "terrain", "basin_outfall", "standards"),
    "storm": ("lot_geometry", "terrain", "basin_outfall", "standards"),
    "sanitary": ("lot_geometry", "terrain", "utility_service", "standards"),
    "water": ("lot_geometry", "terrain", "utility_service", "standards"),
    "utilities": ("lot_geometry", "terrain", "utility_service", "standards"),
    "roadway": ("lot_geometry", "terrain", "survey_control", "standards"),
    "quantities": ("lot_geometry", "survey_control"),
    "qa_review": ("lot_geometry", "terrain", "basin_outfall", "standards", "survey_control"),
}

DOWNSTREAM_SYSTEMS: Dict[str, Sequence[str]] = {
    "grading": ("drainage", "storm", "sanitary", "water", "utilities", "roadway", "quantities", "qa_review"),
    "drainage": ("storm", "quantities", "qa_review"),
    "storm": ("sanitary", "water", "utilities", "quantities", "qa_review"),
    "sanitary": ("utilities", "quantities", "qa_review"),
    "water": ("utilities", "quantities", "qa_review"),
    "utilities": ("quantities", "qa_review"),
    "roadway": ("grading", "drainage", "water", "utilities", "quantities", "qa_review"),
    "quantities": ("qa_review",),
}


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _valid_rect(record: Any, *, require_position: bool = False) -> bool:
    rec = safe_dict(record)
    if require_position and (_float_or_none(rec.get("x")) is None or _float_or_none(rec.get("y")) is None):
        return False
    width = _float_or_none(rec.get("w") if rec.get("w") is not None else rec.get("width"))
    depth = _float_or_none(rec.get("d") if rec.get("d") is not None else rec.get("height"))
    return bool(width is not None and depth is not None and width > 0.0 and depth > 0.0)


def _has_lot_geometry(parsed: Dict[str, Any]) -> bool:
    if safe_dict(safe_dict(parsed.get("meta")).get("input_validation")).get("lot_geometry"):
        if safe_dict(safe_dict(parsed.get("meta")).get("input_validation")).get("lot_geometry", {}).get("valid") is False:
            return False
    lot = safe_dict(parsed.get("lot"))
    if not lot:
        return False
    width = _float_or_none(lot.get("w") if lot.get("w") is not None else lot.get("width"))
    height = _float_or_none(lot.get("h") if lot.get("h") is not None else lot.get("height"))
    return bool(width is not None and height is not None and width > 0.0 and height > 0.0)


def _has_terrain(parsed: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    if safe_str(parsed.get("terrain")):
        return True
    if safe_dict(parsed.get("terrain_model")) or safe_dict(parsed.get("surface")):
        return True
    existing = safe_dict(parsed.get("existing_conditions"))
    if safe_dict(existing.get("surface")) or safe_list(existing.get("contours")) or safe_list(existing.get("survey_points")):
        return True
    return False


def _has_basin_outfall(parsed: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    for pond in safe_list(parsed.get("ponds")):
        if _valid_rect(pond, require_position=True):
            return True
    drainage = safe_dict(parsed.get("drainage"))
    if safe_dict(drainage.get("preferred_outfall")) or safe_dict(drainage.get("outfall")):
        return True
    if safe_list(drainage.get("basins")) or safe_list(drainage.get("outfalls")):
        return True
    return False


def _has_standards(parsed: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    for key in ("standards", "design_standards", "jurisdiction_standards", "company_standards", "standards_review_packet", "standards_acceptance"):
        if safe_dict(parsed.get(key)) or safe_list(parsed.get(key)) or safe_str(parsed.get(key)):
            return True
    parsed_meta = safe_dict(parsed.get("meta"))
    for key in ("standards", "design_standards", "jurisdiction_standards", "company_standards", "standards_review_packet", "standards_acceptance"):
        if safe_dict(parsed_meta.get(key)) or safe_list(parsed_meta.get(key)) or safe_str(parsed_meta.get(key)):
            return True
    package = safe_dict(meta.get("standards_package"))
    return bool(package and safe_str(package.get("status")) in {"ready", "needs_review"})


def _has_survey_control(parsed: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    control = safe_dict(parsed.get("survey_control") or parsed.get("control"))
    coordinate_system = safe_dict(parsed.get("coordinate_system") or safe_dict(parsed.get("meta")).get("coordinate_system"))
    survey = safe_dict(parsed.get("survey") or safe_dict(parsed.get("meta")).get("survey"))
    existing = safe_dict(parsed.get("existing_conditions"))
    if control and (safe_list(control.get("points")) or safe_str(control.get("benchmark")) or safe_str(control.get("datum"))):
        return True
    if coordinate_system and (safe_str(coordinate_system.get("crs")) or safe_str(coordinate_system.get("epsg")) or safe_str(coordinate_system.get("datum"))):
        return True
    if survey and (safe_list(survey.get("control_points")) or safe_list(survey.get("points")) or safe_str(survey.get("datum"))):
        return True
    if safe_list(existing.get("survey_points")) and safe_dict(existing.get("coordinate_system")):
        return True
    summary = safe_dict(meta.get("existing_conditions_summary"))
    return bool(summary.get("survey_present") and summary.get("coordinate_system_present"))


def _has_utility_service(parsed: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    for key in ("buildings", "utility_services", "service_points", "water_services", "sanitary_services"):
        if safe_list(parsed.get(key)):
            return True
    site_plan = safe_dict(parsed.get("site_plan"))
    if _float_or_none(site_plan.get("building_width")) and _float_or_none(site_plan.get("building_depth")):
        return True
    return False


def _input_presence(parsed: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, bool]:
    return {
        "lot_geometry": _has_lot_geometry(parsed),
        "terrain": _has_terrain(parsed, meta),
        "basin_outfall": _has_basin_outfall(parsed, meta),
        "standards": _has_standards(parsed, meta),
        "survey_control": _has_survey_control(parsed, meta),
        "utility_service": _has_utility_service(parsed, meta),
    }


def _missing_input_record(system: str, input_key: str) -> Dict[str, Any]:
    reasons = {
        "lot_geometry": "Valid lot geometry is required before civil systems can be generated.",
        "terrain": "Terrain/existing surface input is required for slope, drainage, cover, earthwork, and roadway review.",
        "basin_outfall": "Drainage basin or outfall input is required before drainage and storm systems can claim completion.",
        "standards": "Jurisdiction/company standards input is required before generated engineering can be review-ready.",
        "survey_control": "Survey/control or coordinate-system evidence is required before outputs can be traceable.",
        "utility_service": "Building/service destination input is required before sanitary, water, or utility routing can claim completion.",
    }
    fields = {
        "lot_geometry": ["lot.w", "lot.h"],
        "terrain": ["terrain", "existing_conditions.surface", "existing_conditions.survey_points"],
        "basin_outfall": ["ponds[*].x/y/w/d", "drainage.preferred_outfall", "drainage.outfalls"],
        "standards": ["standards", "design_standards", "jurisdiction_standards", "standards_acceptance"],
        "survey_control": ["survey_control.points", "survey.datum", "coordinate_system.crs"],
        "utility_service": ["buildings", "site_plan.building_width/building_depth", "utility_services", "service_points"],
    }
    return {
        "system": system,
        "input": input_key,
        "field": input_key,
        "missing_fields": list(fields.get(input_key, [input_key])),
        "reason": reasons.get(input_key, f"{input_key} is required."),
        "severity": "blocker",
        "engineer_review_required": True,
        "next_action": _next_action(input_key),
    }


def _next_action(input_key: str) -> str:
    actions = {
        "lot_geometry": "Provide a positive lot width and height, then rerun the full engineering workflow.",
        "terrain": "Attach terrain/survey surface evidence or enter a terrain description, then rerun grading and downstream systems.",
        "basin_outfall": "Draw or classify a detention basin/outfall or provide drainage preferred_outfall, then rerun drainage and storm.",
        "standards": "Attach accepted jurisdiction/company design standards or mark the standards package for explicit engineer review.",
        "survey_control": "Provide survey control points, datum/benchmark, or a projected coordinate system before review.",
        "utility_service": "Provide building/service destinations or service-point geometry before sanitary/water/utility routing.",
    }
    return actions.get(input_key, "Provide the missing input and rerun the affected workflow.")


def _output_has_trace(system: str, output: Dict[str, Any], plan: Dict[str, Any]) -> bool:
    if system == "roadway":
        return any(
            safe_str(safe_dict(action).get("layer")).upper() in {"ROAD", "PAVEMENT", "FIRE", "CENTERLINE"}
            for action in safe_list(plan.get("actions"))
        )
    if system == "grading":
        return bool(output.get("proposed_surface") or output.get("existing_surface") or safe_list(output.get("surface_ids")))
    if system == "drainage":
        return bool(safe_list(output.get("structures")) or safe_list(output.get("basins")) or safe_list(output.get("low_points")))
    if system == "storm":
        return bool(safe_list(output.get("segments")) or safe_list(output.get("nodes")))
    if system == "sanitary":
        return bool(safe_list(output.get("segments")) or safe_list(output.get("manholes")))
    if system in {"water", "utilities"}:
        return bool(safe_list(safe_dict(output.get("conflict_hooks")).get("utility_segments")) or safe_list(output.get("segments")))
    if system == "quantities":
        return bool(safe_dict(output.get("totals")) or safe_dict(safe_dict(output.get("explain")).get("quantity_audit")))
    if system == "qa_review":
        return "qa" in safe_dict(plan.get("meta"))
    return bool(output)


def _canonical_output_blocker(system: str) -> Dict[str, Any]:
    return {
        "system": system,
        "input": "canonical_output",
        "field": "canonical_output",
        "missing_fields": [SYSTEM_META_KEYS.get(system, system)],
        "reason": f"{SYSTEM_LABELS.get(system, system)} did not produce traceable canonical output.",
        "severity": "blocker",
        "engineer_review_required": True,
        "next_action": f"Rerun {SYSTEM_LABELS.get(system, system)} after resolving upstream blockers.",
    }


def _system_output(meta: Dict[str, Any], system: str) -> Dict[str, Any]:
    key = SYSTEM_META_KEYS.get(system, system)
    value = meta.get(key)
    return safe_dict(value)


def _annotate_output(meta: Dict[str, Any], system: str, row: Dict[str, Any]) -> None:
    key = SYSTEM_META_KEYS.get(system, system)
    if system == "roadway":
        meta[key] = deepcopy(row)
        return
    output = safe_dict(meta.get(key))
    if not output and key not in meta:
        output = {}
    output["engineer_review_required"] = True
    output["review_required"] = True
    output["review_status"] = row["status"]
    output["production_usable"] = False
    output["construction_release_blocked"] = True
    output["workflow_review"] = {
        "status": row["status"],
        "blocked": row["blocked"],
        "missing_inputs": deepcopy(row["missing_inputs"]),
        "blockers": deepcopy(row["blockers"]),
    }
    output.setdefault(
        "truth_label",
        "Generated engineering output is review-required evidence only and cannot be used as sealed or construction-ready design.",
    )
    meta[key] = output


def _blocked_downstream(rows: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    stale: Dict[str, List[str]] = {}
    for system, row in rows.items():
        if not bool(row.get("blocked")):
            continue
        for downstream in DOWNSTREAM_SYSTEMS.get(system, ()):
            stale.setdefault(downstream, []).append(system)
    return {key: dedupe_keep_order(value) for key, value in stale.items()}


def _unique_blockers(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in records:
        rec = safe_dict(item)
        key = (safe_str(rec.get("system")), safe_str(rec.get("input")), tuple(safe_list(rec.get("missing_fields"))))
        if key in seen:
            continue
        seen.add(key)
        out.append(deepcopy(rec))
    return out


def apply_engineering_generation_review(plan: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Attach an explicit no-fake-success review contract to engineering outputs."""

    meta = safe_dict(plan.setdefault("meta", {}))
    presence = _input_presence(parsed, meta)
    systems = ["grading", "drainage", "storm", "sanitary", "water", "utilities", "roadway", "quantities", "qa_review"]
    rows: Dict[str, Dict[str, Any]] = {}

    for system in systems:
        missing = [
            _missing_input_record(system, input_key)
            for input_key in INPUT_DEPENDENCIES.get(system, ())
            if not presence.get(input_key, False)
        ]
        output = _system_output(meta, system)
        if not missing and not _output_has_trace(system, output, plan):
            missing.append(_canonical_output_blocker(system))

        blockers = _unique_blockers(missing)
        status = "blocked_missing_inputs" if blockers else "review_required"
        rows[system] = {
            "system": system,
            "label": SYSTEM_LABELS.get(system, system),
            "status": status,
            "success": not blockers,
            "blocked": bool(blockers),
            "review_required": True,
            "engineer_review_required": True,
            "production_usable": False,
            "construction_release_blocked": True,
            "required_inputs": list(INPUT_DEPENDENCIES.get(system, ())),
            "present_inputs": {key: presence.get(key, False) for key in INPUT_DEPENDENCIES.get(system, ())},
            "missing_inputs": blockers,
            "blockers": blockers,
            "canonical_output_present": _output_has_trace(system, output, plan),
        }

    stale = _blocked_downstream(rows)
    for system, upstream in stale.items():
        row = rows.get(system)
        if not row:
            continue
        row["stale_or_reactive_status"] = {
            "stale": True,
            "upstream_blocked_systems": upstream,
            "reason": "Downstream output remains review-blocked until upstream missing-input blockers are resolved and rerun.",
        }
        if not row["blocked"]:
            reactive_blocker = {
                "system": system,
                "input": "upstream_current_state",
                "field": "stale_or_reactive_status",
                "missing_fields": upstream,
                "reason": "Downstream output depends on upstream systems that are currently blocked.",
                "severity": "blocker",
                "engineer_review_required": True,
                "next_action": "Resolve upstream blockers and rerun the downstream dependency chain.",
            }
            row["blocked"] = True
            row["success"] = False
            row["status"] = "blocked_stale_downstream"
            row["blockers"] = _unique_blockers(safe_list(row.get("blockers")) + [reactive_blocker])
            row["missing_inputs"] = deepcopy(row["blockers"])

    for system, row in rows.items():
        _annotate_output(meta, system, row)

    all_blockers = _unique_blockers(blocker for row in rows.values() for blocker in safe_list(row.get("blockers")))
    review = {
        "version": WORKFLOW_REVIEW_VERSION,
        "status": "blocked" if all_blockers else "review_required",
        "success": not bool(all_blockers),
        "review_required": True,
        "engineer_review_required": True,
        "construction_release_blocked": True,
        "production_usable": False,
        "input_presence": presence,
        "systems": rows,
        "blockers": all_blockers,
        "blocker_count": len(all_blockers),
        "blocked_systems": [system for system, row in rows.items() if bool(row.get("blocked"))],
        "review_required_systems": systems,
        "stale_or_reactive_status": {
            "downstream_blocked_by_upstream": stale,
            "export_blocked_until_rerun": bool(stale),
        },
        "truth_label": (
            "Every generated engineering system is either blocked by exact missing inputs or marked review-required; "
            "Civora does not certify, seal, approve, or release construction documents."
        ),
    }
    meta["engineering_generation_review"] = review
    if all_blockers:
        qa = safe_dict(meta.get("qa"))
        issues = safe_list(qa.get("issues"))
        existing_codes = {
            (safe_str(issue.get("code")), safe_str(issue.get("message")))
            for issue in issues
            if isinstance(issue, dict)
        }
        for blocker in all_blockers:
            code = f"ENGINEERING_INPUT_BLOCKED_{safe_str(blocker.get('system')).upper()}"
            message = safe_str(blocker.get("reason"))
            if (code, message) in existing_codes:
                continue
            issues.append({"code": code, "severity": "error", "message": message, "context": deepcopy(blocker)})
        qa["issues"] = issues
        qa["error_count"] = len([issue for issue in issues if lower_text(safe_dict(issue).get("severity")) == "error"])
        qa["warning_count"] = len([issue for issue in issues if lower_text(safe_dict(issue).get("severity")) == "warning"])
        qa["review_status"] = "blocked_missing_inputs"
        qa["engineer_review_required"] = True
        qa["production_usable"] = False
        meta["qa"] = qa
    plan["meta"] = meta
    return review


__all__ = ["WORKFLOW_REVIEW_VERSION", "apply_engineering_generation_review"]
