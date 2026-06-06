from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

from .common import safe_dict, safe_float, safe_list, safe_str
from .depth_validators import (
    validate_grading_depth,
    validate_profile_section_depth,
    validate_roadway_corridor_depth,
    validate_stormwater_depth,
)
from .production_depth import enrich_storm_production_depth


EVIDENCE_VERSION = "production_evidence_v1"


def _dedupe(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _blocker(area: str, field: str, message: str) -> Dict[str, Any]:
    return {
        "area": area,
        "field": field,
        "message": message,
        "reason": message,
        "severity": "blocker",
        "engineer_review_required": True,
    }


def _accepted_surface_evidence(meta: Dict[str, Any]) -> Dict[str, Any]:
    grading = safe_dict(meta.get("grading") or meta.get("grading_summary"))
    scope_exists = bool(
        grading
        or safe_list(meta.get("alignments") or meta.get("road_alignments"))
        or safe_list(meta.get("profiles") or meta.get("road_profiles"))
        or safe_list(meta.get("cross_sections") or meta.get("corridor_sections"))
    )
    grading_depth = safe_dict(safe_dict(meta.get("depth_validation")).get("grading"))
    roadway_depth = safe_dict(safe_dict(meta.get("depth_validation")).get("roadway_corridor"))
    surface_trace = (
        safe_dict(grading_depth.get("surface_traceability"))
        or safe_dict(roadway_depth.get("surface_traceability"))
        or safe_dict(grading.get("surface_traceability"))
    )
    existing_id = safe_str(
        surface_trace.get("existing_surface_id")
        or grading.get("accepted_existing_surface_id")
        or grading.get("existing_surface_id")
        or safe_dict(grading.get("existing_surface")).get("id")
        or meta.get("accepted_existing_surface_id")
        or meta.get("existing_surface_id")
    )
    proposed_id = safe_str(
        surface_trace.get("proposed_surface_id")
        or grading.get("accepted_proposed_surface_id")
        or grading.get("proposed_surface_id")
        or safe_dict(grading.get("proposed_surface")).get("id")
        or meta.get("accepted_proposed_surface_id")
        or meta.get("proposed_surface_id")
    )
    accepted = bool(
        surface_trace.get("valid") is True
        or surface_trace.get("accepted_surfaces") is True
        or grading.get("accepted_surfaces") is True
    )
    missing = [] if not scope_exists else [
        name
        for name, ok in (
            ("accepted_surfaces", accepted),
            ("existing_surface_id", bool(existing_id)),
            ("proposed_surface_id", bool(proposed_id)),
        )
        if not ok
    ]
    return {
        "ready": not missing,
        "scope_exists": scope_exists,
        "accepted_surfaces": accepted,
        "existing_surface_id": existing_id,
        "proposed_surface_id": proposed_id,
        "source": "depth_validation_or_grading_surface_traceability",
        "feeds": ["grading", "roadway_corridor", "profile_section"],
        "missing_inputs": missing,
        "blockers": [
            _blocker(
                "accepted_surfaces",
                field,
                f"Accepted surface evidence is missing required field: {field}.",
            )
            for field in missing
        ],
        "truth_label": "Accepted surface evidence is only true when existing/proposed surface IDs are explicitly accepted; Civora does not infer acceptance.",
    }


def _storm_hydraulic_evidence(meta: Dict[str, Any]) -> Dict[str, Any]:
    storm = safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))
    drainage = safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
    if storm and not safe_dict(storm.get("hydraulic_profile_evidence")):
        storm = enrich_storm_production_depth(storm, drainage)
    validation = safe_dict(safe_dict(meta.get("depth_validation")).get("stormwater")) or (
        validate_stormwater_depth(meta) if storm or drainage else {}
    )
    profile_evidence = safe_dict(storm.get("hydraulic_profile_evidence"))
    hgl_rows = [safe_dict(row) for row in safe_list(storm.get("hgl_profile"))]
    egl_rows = [safe_dict(row) for row in safe_list(storm.get("egl_profile"))]
    scope_exists = bool(storm or drainage)
    missing_profile_inputs = [safe_dict(row) for row in safe_list(profile_evidence.get("missing_profile_inputs"))]
    missing_fields = _dedupe(
        field
        for row in missing_profile_inputs
        for field in safe_list(row.get("missing_fields"))
    )
    if scope_exists and not hgl_rows:
        missing_fields.append("storm_pipes.hgl_profile")
    if scope_exists and not egl_rows:
        missing_fields.append("storm_pipes.egl_profile")
    if storm and not safe_dict(storm.get("backwater_validation")).get("valid") and storm.get("tailwater_elev_ft") in (None, ""):
        missing_fields.append("tailwater_elev_ft")
    missing_fields = _dedupe(missing_fields)
    ready = bool(validation.get("production_ready") is True and hgl_rows and egl_rows) if scope_exists else True
    return {
        "ready": ready,
        "scope_exists": scope_exists,
        "hydraulic_source": safe_str(storm.get("hydraulic_source")),
        "hydraulic_depth_source": safe_str(storm.get("hydraulic_depth_source")),
        "hgl_row_count": len(hgl_rows),
        "egl_row_count": len(egl_rows),
        "hgl_profile": deepcopy(hgl_rows),
        "egl_profile": deepcopy(egl_rows),
        "hydraulic_profile_evidence": deepcopy(profile_evidence),
        "hydraulic_engine_summary": deepcopy(safe_dict(storm.get("hydraulic_engine_summary"))),
        "validation": deepcopy(validation),
        "missing_required_hydraulic_inputs": missing_fields,
        "blockers": [
            _blocker(
                "storm_hydraulics",
                field,
                f"Storm hydraulic evidence is missing required input: {field}.",
            )
            for field in missing_fields
            if not ready
        ],
        "truth_label": "HGL/EGL evidence is copied only from explicit storm hydraulic profile rows produced by canonical storm inputs.",
    }


def _profile_section_evidence(meta: Dict[str, Any]) -> Dict[str, Any]:
    alignments = [safe_dict(row) for row in safe_list(meta.get("alignments") or meta.get("road_alignments")) if safe_dict(row)]
    profiles = [safe_dict(row) for row in safe_list(meta.get("profiles") or meta.get("road_profiles")) if safe_dict(row)]
    sections = [safe_dict(row) for row in safe_list(meta.get("cross_sections") or meta.get("corridor_sections")) if safe_dict(row)]
    utilities_exist = bool(
        safe_list(safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary")).get("segments"))
        or safe_list(safe_dict(meta.get("sanitary") or meta.get("sanitary_summary")).get("segments"))
        or safe_list(safe_dict(meta.get("utilities") or meta.get("utility_summary")).get("segments"))
    )
    scope_exists = bool(alignments or profiles or sections or utilities_exist)
    validation = safe_dict(safe_dict(meta.get("depth_validation")).get("profile_section")) or (
        validate_profile_section_depth(meta) if scope_exists else {}
    )
    blockers = [
        _blocker("profile_section", "depth_validation", safe_str(message))
        for message in safe_list(validation.get("blockers"))
        if safe_str(message)
    ]
    return {
        "ready": bool(validation.get("production_ready") is True),
        "scope_exists": scope_exists,
        "alignment_count": len(alignments),
        "profile_count": len(profiles),
        "cross_section_count": len(sections),
        "profiles": deepcopy(profiles),
        "cross_sections": deepcopy(sections),
        "validation": deepcopy(validation),
        "blockers": blockers,
        "truth_label": "Profile/section evidence is packaged from canonical alignments, profiles, sections, surfaces, and utility band rows only.",
    }


def _reactive_dirty_evidence(meta: Dict[str, Any]) -> Dict[str, Any]:
    report = safe_dict(meta.get("reactive_update_report"))
    dirty_state = safe_dict(meta.get("system_dirty_state"))
    manager_dirty = safe_dict(safe_dict(meta.get("manager_export")).get("dirty_state"))
    dirty_rows = []
    for source_name, source in (("system_dirty_state", dirty_state), ("manager_export.dirty_state", manager_dirty)):
        for key, value in source.items():
            rec = safe_dict(value) if isinstance(value, dict) else {"state": value}
            state = safe_str(rec.get("state") or rec.get("status") or rec.get("value")).lower()
            if state in {"dirty", "stale", "not_generated"}:
                dirty_rows.append(
                    {
                        "stage": safe_str(key),
                        "state": state,
                        "source": safe_str(rec.get("source"), source_name),
                        "reasons": _dedupe(safe_list(rec.get("reasons")) + [rec.get("reason")]),
                    }
                )
    blockers = [
        _blocker(
            "reactive_model",
            "dirty_state",
            f"Reactive dirty state remains for {safe_str(row.get('stage'))}.",
        )
        for row in dirty_rows
    ]
    blockers.extend(
        _blocker("reactive_model", "post_rerun_release_blocker", safe_str(item))
        for item in safe_list(report.get("post_rerun_release_blockers"))
        if safe_str(item)
    )
    return {
        "ready": bool(report) and not dirty_rows and not safe_list(report.get("post_rerun_release_blockers")),
        "report_present": bool(report),
        "reactive_update_report": deepcopy(report),
        "dirty_state": dirty_rows,
        "blockers": blockers,
        "truth_label": "Reactive evidence preserves dirty and stale downstream state; exports and readiness remain blocked until rerun evidence clears it.",
    }


def _quantity_cost_evidence(meta: Dict[str, Any]) -> Dict[str, Any]:
    quantities = safe_dict(meta.get("quantities"))
    cost = safe_dict(meta.get("cost_estimate"))
    package = safe_dict(meta.get("cost_package_status"))
    cost_explain = safe_dict(cost.get("explain"))
    pricing = safe_dict(cost_explain.get("pricing"))
    totals = safe_dict(quantities.get("totals"))
    line_items = safe_list(cost.get("line_items")) or safe_list(quantities.get("line_items") or quantities.get("items") or quantities.get("rows"))
    quantity_scope_exists = bool(line_items) or any(safe_float(value, 0.0) > 0.0 for value in totals.values())
    approved_cost_source = bool(
        package.get("production_usable") is True
        or (
            cost.get("success") is True
            and pricing.get("production_usable") is True
            and cost_explain.get("pricing_coverage_complete") is not False
            and cost_explain.get("traceability_complete") is not False
        )
    )
    blockers: List[Dict[str, Any]] = []
    if quantities and quantities.get("success") is False:
        blockers.append(_blocker("quantity", "quantity_success", "Quantity engine reported failure."))
    if safe_dict(safe_dict(quantities.get("explain")).get("trace_gaps")):
        blockers.append(_blocker("quantity", "trace_gaps", "Quantity line items have unresolved canonical trace gaps."))
    if quantities and quantity_scope_exists and not approved_cost_source:
        blockers.append(
            _blocker(
                "quantity",
                "approved_cost_source",
                "Production cost readiness is blocked because no approved unit-price source covers the current quantities.",
            )
        )
    blockers.extend(
        deepcopy(item)
        for item in safe_list(package.get("blockers"))
        if safe_dict(item)
    )
    return {
        "ready": bool(quantities) and not blockers and (approved_cost_source or not quantity_scope_exists),
        "quantity_scope_exists": quantity_scope_exists,
        "quantity_success": quantities.get("success"),
        "quantity_total_count": len(safe_dict(quantities.get("totals"))),
        "quantity_line_item_count": len(line_items),
        "quantity_line_items": deepcopy(line_items),
        "cost_success": cost.get("success"),
        "approved_cost_source": approved_cost_source,
        "pricing_source": safe_str(pricing.get("source")),
        "pricing_confidence": safe_str(pricing.get("confidence") or package.get("confidence"), "blocked" if blockers else "unknown"),
        "cost_package_status": deepcopy(package),
        "blockers": blockers,
        "truth_label": "Quantity/cost evidence is production-usable only with traceable quantities and an approved production unit-price source.",
    }


def build_production_evidence(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = safe_dict(plan_or_meta.get("meta")) if isinstance(plan_or_meta, dict) and "meta" in plan_or_meta else safe_dict(plan_or_meta)
    accepted_surfaces = _accepted_surface_evidence(meta)
    storm_hydraulics = _storm_hydraulic_evidence(meta)
    profile_section = _profile_section_evidence(meta)
    reactive_dirty_state = _reactive_dirty_evidence(meta)
    quantity_cost = _quantity_cost_evidence(meta)
    blockers = (
        safe_list(accepted_surfaces.get("blockers"))
        + safe_list(storm_hydraulics.get("blockers"))
        + safe_list(profile_section.get("blockers"))
        + safe_list(reactive_dirty_state.get("blockers"))
        + safe_list(quantity_cost.get("blockers"))
    )
    return {
        "version": EVIDENCE_VERSION,
        "accepted_surfaces": accepted_surfaces,
        "storm_hydraulics": storm_hydraulics,
        "profile_section": profile_section,
        "reactive_dirty_state": reactive_dirty_state,
        "quantity_cost": quantity_cost,
        "blockers": blockers,
        "production_evidence_ready": not blockers,
        "engineer_review_required": True,
        "construction_release_allowed": False,
        "truth_label": "Canonical production-depth evidence is traceable review evidence only; construction release remains blocked without external licensed engineer approval.",
    }


__all__ = ["EVIDENCE_VERSION", "build_production_evidence"]
