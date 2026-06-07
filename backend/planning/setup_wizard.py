from __future__ import annotations

from typing import Any, Dict, List, Optional


SETUP_WIZARD_VERSION = "setup_wizard_state_v1"

SETUP_WIZARD_STEP_ORDER = [
    "address_location",
    "site_boundary",
    "online_sources_candidates",
    "survey_terrain_control",
    "standards",
    "objects_program",
    "run_systems",
    "review_export_package",
]

VALID_SETUP_WIZARD_STATUSES = {"complete", "blocked", "needs_review", "pending", "not_started"}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truthy_source(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return False


def _status_is_done(value: Any) -> bool:
    status = _text(value).lower()
    return status in {
        "accepted",
        "complete",
        "completed",
        "verified",
        "ready",
        "ready_for_review",
        "externally_verified_review_only",
        "passed",
    }


def _status_needs_review(value: Any) -> bool:
    status = _text(value).lower()
    return any(token in status for token in ["review", "pending", "draft", "candidate"])


def _record_blockers(*records: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    for record in records:
        for key in ("blockers", "warnings", "missing_inputs", "blocked_reasons", "failures"):
            for item in _safe_list(record.get(key)):
                if isinstance(item, dict):
                    text = _text(
                        item.get("message")
                        or item.get("reason")
                        or item.get("field")
                        or item.get("code")
                    )
                else:
                    text = _text(item)
                if text and text not in blockers:
                    blockers.append(text)
    return blockers


def _find_capability(context: Dict[str, Any], key: str) -> Dict[str, Any]:
    for item in _safe_list(context.get("capability_statuses")):
        rec = _safe_dict(item)
        if _text(rec.get("key")) == key:
            return rec
    return {}


def _step(
    step_id: str,
    label: str,
    status: str,
    next_action: str,
    why_blocked: str = "",
    review_required: bool = False,
    panel: str = "",
    primary_action_label: str = "",
    missing_inputs: Optional[List[str]] = None,
    blockers: Optional[List[str]] = None,
    safe_actions: Optional[List[Dict[str, Any]]] = None,
    depends_on: Optional[List[str]] = None,
    source_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    normalized = status if status in VALID_SETUP_WIZARD_STATUSES else "pending"
    blocker_list = [item for item in (blockers or []) if _text(item)]
    if why_blocked and why_blocked not in blocker_list:
        blocker_list.insert(0, why_blocked)
    return {
        "id": step_id,
        "label": label,
        "status": normalized,
        "next_action": next_action,
        "why_blocked": why_blocked,
        "review_required": bool(review_required),
        "panel": panel,
        "primary_action_label": primary_action_label or "Open step",
        "missing_inputs": [item for item in (missing_inputs or []) if _text(item)],
        "blockers": blocker_list,
        "safe_actions": safe_actions or [],
        "depends_on": depends_on or [],
        "source_refs": source_refs or [],
        "can_auto_complete": False,
    }


def _open_action(label: str, panel: str) -> Dict[str, Any]:
    return {
        "id": f"open_{panel}",
        "label": label,
        "kind": "open_panel",
        "panel": panel,
        "safe": True,
    }


def _ui_action(label: str, action: str, panel: str, *, disabled_reason: str = "") -> Dict[str, Any]:
    return {
        "id": action,
        "label": label,
        "kind": action,
        "panel": panel,
        "safe": True,
        "disabled_reason": disabled_reason,
    }


def build_setup_wizard_state(
    *,
    project_input: Optional[Dict[str, Any]] = None,
    latest_result: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    project_input = _safe_dict(project_input)
    latest_result = _safe_dict(latest_result)
    context = _safe_dict(context)
    final_plan = _safe_dict(latest_result.get("final_plan"))
    meta = _safe_dict(final_plan.get("meta") or latest_result.get("metadata") or latest_result.get("meta"))
    input_meta = _safe_dict(project_input.get("meta"))
    site_inputs = _safe_dict(input_meta.get("site_inputs"))
    manual_fields = _safe_dict(project_input.get("manual_fields"))
    lot = _safe_dict(manual_fields.get("lot") or project_input.get("lot"))
    canonical_site = _safe_dict(meta.get("canonical_site_state"))
    location_context = _safe_dict(meta.get("location_context"))
    map_report = _safe_dict(meta.get("map_feature_detection_report_v1"))
    existing_package = _safe_dict(meta.get("existing_conditions_package"))
    survey_control = _safe_dict(meta.get("survey_control_package"))
    standards_package = _safe_dict(meta.get("standards_package"))
    standards_registry = _safe_dict(meta.get("standards_source_registry"))
    standards_acceptance = _safe_dict(meta.get("standards_acceptance_report") or meta.get("standards_acceptance"))
    export_package = _safe_dict(meta.get("export_package_report_v1") or meta.get("export_audit"))
    review_package = _safe_dict(meta.get("engineer_review_package_v1"))

    lot_width = lot.get("w") or lot.get("width") or canonical_site.get("lot_width") or context.get("lot_width")
    lot_height = lot.get("h") or lot.get("height") or canonical_site.get("lot_height") or context.get("lot_height")
    has_site_size = _truthy_source(lot_width) and _truthy_source(lot_height)
    has_address = any(
        _truthy_source(value)
        for value in [
            site_inputs.get("address"),
            location_context.get("address"),
            canonical_site.get("address"),
            context.get("site_address"),
            context.get("address"),
        ]
    )
    has_geocode = any(
        _truthy_source(value)
        for value in [
            _safe_dict(site_inputs.get("geocode")).get("lat"),
            _safe_dict(location_context.get("geocode")).get("lat"),
            context.get("has_location_evidence"),
        ]
    )
    location_blockers = _record_blockers(location_context, map_report)
    address_status = _text(context.get("address_status") or location_context.get("status")).lower()
    location_failed = any(token in address_status for token in ["fail", "blocked", "error", "not_found"])
    if location_failed:
        address_step = _step(
            "address_location",
            "Address / Location",
            "blocked",
            "Correct the address, provide coordinates, or start from a blank site.",
            location_blockers[0] if location_blockers else "Address/location evidence could not be verified.",
            panel="site_existing",
            primary_action_label="Fix location",
            missing_inputs=["valid address or coordinates"],
            blockers=location_blockers,
            safe_actions=[_open_action("Open site setup", "site_existing")],
        )
    elif has_address or has_geocode:
        address_step = _step(
            "address_location",
            "Address / Location",
            "needs_review",
            "Review the geocode/source and continue to site boundary.",
            review_required=True,
            panel="site_existing",
            primary_action_label="Review location",
            safe_actions=[
                _open_action("Open site setup", "site_existing"),
                _ui_action("Run source discovery", "run_source_discovery", "data"),
            ],
            source_refs=["location_context", "site_inputs.geocode"],
        )
    else:
        address_step = _step(
            "address_location",
            "Address / Location",
            "not_started",
            "Enter an address, provide coordinates, or choose a blank site.",
            panel="site_existing",
            primary_action_label="Add location",
            missing_inputs=["address, coordinates, or blank-site dimensions"],
            safe_actions=[_open_action("Open site setup", "site_existing")],
        )

    boundary_status = _text(canonical_site.get("boundary_status") or lot.get("boundary_status")).lower()
    has_drawn_boundary = any(
        _truthy_source(value)
        for value in [
            context.get("has_site_boundary"),
            canonical_site.get("site_boundary"),
            meta.get("site_boundary"),
        ]
    )
    site_locked = context.get("site_locked")
    if site_locked is None:
        site_locked = boundary_status in {"locked", "review_locked"}
    if site_locked is True:
        boundary_step = _step(
            "site_boundary",
            "Site Boundary",
            "complete",
            "Review source candidates and survey/control evidence next.",
            panel="site_existing",
            primary_action_label="Review sources",
            safe_actions=[_open_action("Open source review", "data")],
            depends_on=["address_location"],
        )
    elif has_site_size or has_drawn_boundary:
        boundary_step = _step(
            "site_boundary",
            "Site Boundary",
            "pending",
            "Review and lock the site boundary before using it for systems.",
            panel="site_existing",
            primary_action_label="Lock boundary",
            missing_inputs=["reviewed boundary lock"],
            safe_actions=[
                _open_action("Open boundary tools", "site_existing"),
                _ui_action("Draw boundary", "draw_boundary", "site_existing"),
                _ui_action("Lock current boundary", "lock_boundary", "site_existing"),
            ],
            depends_on=["address_location"],
        )
    else:
        boundary_step = _step(
            "site_boundary",
            "Site Boundary",
            "blocked",
            "Set dimensions or draw/import the boundary.",
            "A trusted boundary has not been defined.",
            panel="site_existing",
            primary_action_label="Define boundary",
            missing_inputs=["site dimensions, drawn boundary, or imported boundary"],
            blockers=["A trusted boundary has not been defined."],
            safe_actions=[
                _open_action("Open boundary tools", "site_existing"),
                _ui_action("Draw boundary", "draw_boundary", "site_existing"),
            ],
            depends_on=["address_location"],
        )

    candidate_count = int(map_report.get("candidate_count") or len(_safe_list(map_report.get("feature_candidates"))) or 0)
    pending_candidates = [
        item
        for item in _safe_list(map_report.get("feature_candidates"))
        if _text(_safe_dict(item).get("acceptance_status")).lower() != "accepted"
    ]
    online_source_present = any(
        _truthy_source(value)
        for value in [
            map_report,
            site_inputs.get("map_analysis"),
            site_inputs.get("map_snapshot"),
            context.get("has_online_source_candidates"),
            context.get("map_analysis_success"),
        ]
    )
    if candidate_count or pending_candidates:
        candidates_step = _step(
            "online_sources_candidates",
            "Online Sources / Candidates",
            "needs_review",
            "Review each online/GIS candidate before turning it into a draft object.",
            review_required=True,
            panel="data",
            primary_action_label="Review candidates",
            missing_inputs=["accept, reject, or leave each candidate pending"],
            blockers=["Online/GIS candidates remain review-required."],
            safe_actions=[_open_action("Open candidate inbox", "data")],
            depends_on=["address_location"],
            source_refs=["candidate_review_inbox_v1", "map_feature_detection_report_v1"],
        )
    elif online_source_present:
        candidates_step = _step(
            "online_sources_candidates",
            "Online Sources / Candidates",
            "needs_review",
            "Review the source result; no online/GIS candidate is auto-accepted.",
            review_required=True,
            panel="data",
            primary_action_label="Review source result",
            blockers=["Online/GIS source output remains review-required."],
            safe_actions=[_open_action("Open source review", "data")],
            depends_on=["address_location"],
            source_refs=["map_feature_detection_report_v1"],
        )
    elif address_step["status"] in {"not_started", "blocked"}:
        candidates_step = _step(
            "online_sources_candidates",
            "Online Sources / Candidates",
            "blocked",
            "Add address/location evidence before source discovery.",
            "Online/source discovery needs a location or uploaded source.",
            panel="data",
            primary_action_label="Add location first",
            missing_inputs=["address, coordinates, or uploaded source"],
            blockers=["Online/source discovery needs a location or uploaded source."],
            safe_actions=[_open_action("Open site setup", "site_existing")],
            depends_on=["address_location"],
        )
    else:
        candidates_step = _step(
            "online_sources_candidates",
            "Online Sources / Candidates",
            "not_started",
            "Run online/source discovery or upload a map/GIS source.",
            panel="data",
            primary_action_label="Find sources",
            missing_inputs=["online/source discovery result or uploaded GIS/map source"],
            safe_actions=[
                _open_action("Open source review", "data"),
                _ui_action("Run source discovery", "run_source_discovery", "data"),
            ],
            depends_on=["address_location"],
        )

    survey_capability = _find_capability(context, "survey_control_package")
    has_terrain = bool(context.get("has_terrain_source")) or _truthy_source(site_inputs.get("survey_file")) or _truthy_source(site_inputs.get("survey_points")) or _truthy_source(meta.get("grading"))
    has_control = bool(context.get("has_verified_survey_control")) or bool(survey_control) or _status_is_done(survey_capability.get("status"))
    if has_control and _status_is_done(survey_control.get("status") or survey_capability.get("status")):
        survey_step = _step(
            "survey_terrain_control",
            "Survey / Terrain / Control",
            "complete",
            "Continue to standards acceptance.",
            panel="import_survey",
            primary_action_label="Open standards",
            safe_actions=[_open_action("Open standards", "standards")],
            source_refs=["survey_control_package"],
        )
    elif has_terrain or has_control:
        survey_step = _step(
            "survey_terrain_control",
            "Survey / Terrain / Control",
            "needs_review",
            "Review survey/control, datum, benchmark, coordinate system, and terrain source.",
            review_required=True,
            panel="import_survey",
            primary_action_label="Review survey/control",
            missing_inputs=["explicit survey/control review"],
            blockers=["Survey/control remains an explicit gate."],
            safe_actions=[_open_action("Open survey import", "import_survey")],
            source_refs=["survey_control_package", "existing_conditions_package"],
        )
    else:
        survey_step = _step(
            "survey_terrain_control",
            "Survey / Terrain / Control",
            "blocked",
            "Upload survey/topo/control evidence or explicitly choose an assumed terrain path.",
            "Survey/control remains an explicit gate.",
            panel="import_survey",
            primary_action_label="Add survey/control",
            missing_inputs=["survey/topo/control evidence or an explicit assumed terrain path"],
            blockers=["Survey/control remains an explicit gate."],
            safe_actions=[_open_action("Open survey import", "import_survey")],
        )

    accepted_sources = standards_registry.get("accepted_source_count")
    accepted_rules = standards_acceptance.get("accepted_rule_count")
    if accepted_rules is None:
        rules = _safe_dict(standards_acceptance.get("rules"))
        accepted_rules = rules.get("accepted_rule_count") or len(_safe_list(rules.get("accepted"))) or len(_safe_list(standards_acceptance.get("accepted_rules")))
    standards_blockers = _record_blockers(standards_package, standards_registry, standards_acceptance)
    if (accepted_sources or accepted_rules) and not standards_blockers:
        standards_step = _step(
            "standards",
            "Standards",
            "complete",
            "Add or review project objects/program next.",
            panel="standards",
            primary_action_label="Open objects",
            safe_actions=[_open_action("Open objects", "objects")],
            source_refs=["standards_acceptance_report", "standards_source_registry"],
        )
    elif standards_package or standards_registry or standards_acceptance:
        standards_step = _step(
            "standards",
            "Standards",
            "needs_review",
            "Review standards sources and accept/reject applicable candidate rules.",
            "; ".join(standards_blockers[:2]),
            review_required=True,
            panel="standards",
            primary_action_label="Review standards",
            missing_inputs=["explicit standards source/rule review"],
            blockers=standards_blockers or ["Standards acceptance remains an explicit gate."],
            safe_actions=[_open_action("Open standards", "standards")],
            source_refs=["standards_acceptance_report", "standards_source_registry"],
        )
    else:
        standards_step = _step(
            "standards",
            "Standards",
            "blocked",
            "Review jurisdiction/company standards sources and accept the applicable rules.",
            "Standards acceptance remains an explicit gate.",
            panel="standards",
            primary_action_label="Add standards",
            missing_inputs=["accepted applicable standards/rules"],
            blockers=["Standards acceptance remains an explicit gate."],
            safe_actions=[_open_action("Open standards", "standards")],
        )

    site_objects = _safe_list(manual_fields.get("site_objects")) + _safe_list(meta.get("canonical_draft_geometry"))
    object_count = int(context.get("placed_object_count") or len(site_objects) or 0)
    has_program = any(
        _truthy_source(value)
        for value in [
            _safe_dict(manual_fields.get("site_plan")).get("parking_count"),
            project_input.get("parking_count"),
            context.get("parking_count"),
            context.get("building_count"),
        ]
    )
    if object_count > 1 and has_program:
        objects_step = _step(
            "objects_program",
            "Objects / Program",
            "complete",
            "Run systems when survey/control and standards gates are ready.",
            panel="objects",
            primary_action_label="Run systems",
            safe_actions=[_open_action("Open systems", "generate")],
            depends_on=["site_boundary"],
        )
    elif boundary_step["status"] != "complete":
        objects_step = _step(
            "objects_program",
            "Objects / Program",
            "blocked",
            "Lock the site boundary before placing relied-on objects.",
            "Objects/program depends on a locked boundary.",
            panel="objects",
            primary_action_label="Lock boundary first",
            missing_inputs=["locked boundary"],
            blockers=["Objects/program depends on a locked boundary."],
            safe_actions=[_open_action("Open boundary tools", "site_existing")],
            depends_on=["site_boundary"],
        )
    else:
        objects_step = _step(
            "objects_program",
            "Objects / Program",
            "pending",
            "Add buildings, parking/program, roads/access, basin/outfall, and utility points as needed.",
            panel="objects",
            primary_action_label="Add objects",
            missing_inputs=["building, parking/program, access, drainage, or utility objects"],
            safe_actions=[_open_action("Open objects", "objects")],
            depends_on=["site_boundary"],
        )

    system_statuses = _safe_dict(context.get("system_statuses"))
    has_fresh_system = any(_text(value).lower() == "fresh" for value in system_statuses.values()) or bool(final_plan.get("actions"))
    prerequisite_blockers = [
        step["label"]
        for step in [boundary_step, survey_step, standards_step, objects_step]
        if step["status"] == "blocked"
    ]
    if has_fresh_system:
        systems_step = _step(
            "run_systems",
            "Run Systems",
            "complete",
            "Review blockers and prepare the review/export package.",
            panel="generate",
            primary_action_label="Review package",
            safe_actions=[_open_action("Open review package", "deliverables")],
        )
    elif prerequisite_blockers:
        systems_step = _step(
            "run_systems",
            "Run Systems",
            "blocked",
            "Clear setup gates before running systems.",
            "Blocked by " + ", ".join(prerequisite_blockers[:3]) + ".",
            panel="generate",
            primary_action_label="Clear gates",
            missing_inputs=prerequisite_blockers,
            blockers=["Blocked by " + ", ".join(prerequisite_blockers[:3]) + "."],
            safe_actions=[_open_action("Open setup", "site_existing")],
            depends_on=["site_boundary", "survey_terrain_control", "standards", "objects_program"],
        )
    else:
        systems_step = _step(
            "run_systems",
            "Run Systems",
            "pending",
            "Run the selected systems and review any returned blockers.",
            panel="generate",
            primary_action_label="Run systems",
            safe_actions=[_open_action("Open systems", "generate"), _ui_action("Run systems", "run_systems", "generate")],
            depends_on=["site_boundary", "survey_terrain_control", "standards", "objects_program"],
        )

    export_blockers = _record_blockers(export_package, review_package)
    if not has_fresh_system and not final_plan:
        review_step = _step(
            "review_export_package",
            "Review / Export Package",
            "blocked",
            "Run systems before preparing the review/export package.",
            "No system run evidence is available yet.",
            panel="deliverables",
            primary_action_label="Run systems first",
            missing_inputs=["system run evidence"],
            blockers=["No system run evidence is available yet."],
            safe_actions=[_open_action("Open systems", "generate")],
            depends_on=["run_systems"],
        )
    elif export_blockers:
        review_step = _step(
            "review_export_package",
            "Review / Export Package",
            "blocked",
            "Resolve listed package blockers, then regenerate review/export materials.",
            "; ".join(export_blockers[:3]),
            panel="deliverables",
            primary_action_label="Resolve package blockers",
            missing_inputs=export_blockers[:3],
            blockers=export_blockers,
            safe_actions=[_open_action("Open deliverables", "deliverables")],
            depends_on=["run_systems"],
        )
    elif export_package or review_package:
        review_step = _step(
            "review_export_package",
            "Review / Export Package",
            "needs_review",
            "Review the package contents and unresolved notes.",
            review_required=True,
            panel="deliverables",
            primary_action_label="Review package",
            missing_inputs=["explicit package review"],
            safe_actions=[_open_action("Open deliverables", "deliverables")],
            depends_on=["run_systems"],
        )
    else:
        review_step = _step(
            "review_export_package",
            "Review / Export Package",
            "pending",
            "Prepare the review/export package after systems run.",
            panel="deliverables",
            primary_action_label="Prepare package",
            safe_actions=[_open_action("Open deliverables", "deliverables")],
            depends_on=["run_systems"],
        )

    steps_by_id = {
        item["id"]: item
        for item in [
            address_step,
            boundary_step,
            candidates_step,
            survey_step,
            standards_step,
            objects_step,
            systems_step,
            review_step,
        ]
    }
    steps = [steps_by_id[step_id] for step_id in SETUP_WIZARD_STEP_ORDER]
    current_step = next((item for item in steps if item["status"] in {"blocked", "needs_review", "pending", "not_started"}), steps[-1])
    blocked_steps = [item for item in steps if item["status"] == "blocked"]
    review_steps = [item for item in steps if item["status"] == "needs_review"]
    completed_count = len([item for item in steps if item["status"] == "complete"])
    exact_blockers = [
        blocker
        for item in blocked_steps
        for blocker in item.get("blockers", [])
        if _text(blocker)
    ]
    missing_inputs = [
        missing
        for item in steps
        if item["status"] in {"blocked", "needs_review", "pending", "not_started"}
        for missing in item.get("missing_inputs", [])
        if _text(missing)
    ]
    return {
        "schema_version": SETUP_WIZARD_VERSION,
        "steps": steps,
        "current_step_id": current_step["id"],
        "current_step_label": current_step["label"],
        "current_status": current_step["status"],
        "next_action": current_step["next_action"],
        "why_blocked": current_step["why_blocked"],
        "blocked_step_ids": [item["id"] for item in blocked_steps],
        "needs_review_step_ids": [item["id"] for item in review_steps],
        "exact_blockers": exact_blockers,
        "missing_inputs": missing_inputs,
        "primary_action_label": current_step.get("primary_action_label"),
        "safe_actions": current_step.get("safe_actions", []),
        "completed_count": completed_count,
        "total_count": len(steps),
        "truth_rules": [
            "Online/GIS candidates remain review-required.",
            "Survey/control and standards remain explicit gates.",
            "The wizard records only real inputs and visible review state.",
        ],
    }
