"""Server-authored disclosures for a specific, representable review snapshot.

This does not refresh calculations or claim that unsaved canvas edits are in a
generated plan. Production and cache-only integrity gates remain independent.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any

from fastapi import HTTPException


def _object(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list:
    if isinstance(value, list):
        return value
    return [] if value is None else [value]


def validate_review_geometry(plan: dict) -> str:
    units = str(plan.get("units") or "").lower().strip()
    if units not in {"ft", "feet", "m", "meters", "metres"}:
        raise HTTPException(409, "Review export blocked: drawing units are unknown or unsupported.")
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        raise HTTPException(409, "Review export blocked: no representable drawing geometry.")
    supported = {"rectangle", "polyline", "polygon", "circle", "arc", "text_note", "north_arrow", "point"}
    numeric_fields = {"x", "y", "width", "height", "w", "h", "radius", "r", "rotation", "start_angle", "end_angle"}
    try:
        for action in actions:
            if not isinstance(action, dict) or action.get("task") not in supported:
                raise ValueError("unsupported drawing entity")
            for field in numeric_fields.intersection(action):
                if not math.isfinite(float(action[field])):
                    raise ValueError("nonfinite coordinate or dimension")
            for field in ("points", "origin", "center"):
                if field not in action:
                    continue
                points = action[field] if field == "points" else [action[field]]
                if not isinstance(points, list):
                    raise ValueError("invalid coordinate array")
                for point in points:
                    if not isinstance(point, (list, tuple)) or len(point) < 2 or not all(math.isfinite(float(v)) for v in point):
                        raise ValueError("invalid coordinate")
            if action["task"] in {"polyline", "polygon"}:
                if len(action.get("points") or []) < (3 if action["task"] == "polygon" else 2):
                    raise ValueError("incomplete line or polygon")
                if len({tuple(point[:2]) for point in action["points"]}) < (3 if action["task"] == "polygon" else 2):
                    raise ValueError("degenerate line or polygon")
            if action["task"] == "rectangle":
                if float(action.get("width", action.get("w", 0))) <= 0 or float(action.get("height", action.get("h", 0))) <= 0:
                    raise ValueError("rectangle dimensions must be positive")
            if action["task"] in {"circle", "arc"} and float(action.get("radius", action.get("r", 0))) <= 0:
                raise ValueError("radius must be positive")
        encoded = json.dumps({"units": units, "actions": actions}, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(409, f"Review export blocked: corrupt or unrepresentable geometry ({exc}).") from exc
    return sha256(encoded.encode()).hexdigest()


def has_valid_preliminary_disclosure(plan: dict) -> bool:
    disclosure = _object(_object(plan.get("meta")).get("preliminary_export_v1"))
    try:
        return (
            disclosure.get("version") == 1
            and disclosure.get("construction_release_allowed") is False
            and disclosure.get("source_geometry_sha256") == validate_review_geometry(plan)
            and not review_integrity_blockers(_object(plan.get("meta")))
        )
    except HTTPException:
        return False


def review_integrity_blockers(meta: dict) -> list[str]:
    integrity = _object(meta.get("canonical_integrity") or _object(meta.get("truth_audit")).get("canonical_integrity"))
    cache_only = _items(integrity.get("cache_only_stages")) + [
        stage for stage, row in _object(meta.get("canonical_state_warnings")).items()
        if _object(row).get("cache_only")
    ]
    blockers = [f"cache_only_{stage}" for stage in cache_only]
    if integrity.get("blocked") and not (integrity.get("dirty_stages") or integrity.get("dirty_state") or integrity.get("invalidated_targets") or cache_only):
        blockers.append("unresolved_canonical_integrity")
    return sorted(set(blockers))


def prepare_preliminary_snapshot(plan: dict, result: dict | None = None, *, notes: list | None = None) -> dict:
    plan = deepcopy(plan)
    geometry_hash = validate_review_geometry(plan)
    meta = _object(plan.get("meta"))
    blockers = review_integrity_blockers(meta)
    if blockers:
        raise HTTPException(409, "Review export blocked by data integrity: " + ", ".join(blockers))
    result = _object(result)
    context = _object(result.get("preliminary_export_context_v1"))
    dirty = deepcopy(_object(meta.get("system_dirty_state")))
    for stage, status in _object(context.get("system_statuses")).items():
        if status == "stale":
            dirty[str(stage)] = {"state": "stale", "source": "workspace_export_context"}
    meta["system_dirty_state"] = dirty
    integrity = _object(meta.get("canonical_integrity") or _object(meta.get("truth_audit")).get("canonical_integrity"))
    stale = _items(meta.get("stale_outputs")) + _items(context.get("stale_outputs")) + _items(integrity.get("dirty_stages")) + _items(integrity.get("invalidated_targets"))
    stale += [stage for stage, row in dirty.items() if str(_object(row).get("state") or _object(row).get("status") or row).lower() in {"dirty", "stale", "invalid", "failed", "not_generated"}]
    meta["stale_outputs"] = sorted({str(item) for item in stale if item})
    warnings = _items(meta.get("warnings")) + _items(result.get("warnings")) + _items(_object(meta.get("preliminary_export_v1")).get("warnings")) + list(notes or [])
    warnings += ["This file contains the generated/saved export snapshot, not newer unsaved canvas edits.", "Calculations were not rerun by exporting. Stale or incomplete results must not be used for construction."]
    warnings = list({json.dumps(item, sort_keys=True, default=str): item for item in warnings}.values())
    disclosure = {
        "version": 1,
        "designation": "PRELIMINARY - REVIEW ONLY - NOT FOR CONSTRUCTION",
        "geometry_scope": "generated_or_saved_snapshot_not_unsaved_canvas",
        "source_project_id": str(meta.get("project_id") or "not supplied"),
        "source_revision": str(meta.get("source_canonical_revision") or meta.get("canonical_revision") or meta.get("revision") or f"snapshot:{geometry_hash}"),
        "source_geometry_sha256": geometry_hash,
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "units": plan["units"],
        "stale_systems": meta["stale_outputs"],
        "conflict_summary": _items(meta.get("conflicts")) + _items(meta.get("constraint_violations")) or ["No independent conflict verification supplied; absence of listed conflicts is not clearance."],
        "assumption_log": _items(meta.get("assumptions")) + _items(result.get("assumptions")) or ["No assumption log supplied; source completeness is unverified."],
        "verification_status": "Unverified for engineering or construction; professional and external CAD review required.",
        "warnings": warnings,
        "construction_release_allowed": False,
    }
    meta.update(preliminary_export_v1=disclosure, export_scope="review", review_only=True, construction_release_allowed=False)
    plan["meta"] = meta
    return plan


def preliminary_disclosure_lines(disclosure: dict) -> list[str]:
    lines = [disclosure["designation"], f"Geometry: {disclosure['geometry_scope']}", f"Project: {disclosure['source_project_id']}", f"Source revision: {disclosure['source_revision']}", f"Geometry SHA-256: {disclosure['source_geometry_sha256']}", f"Exported (UTC): {disclosure['export_timestamp']}", f"Drawing units: {disclosure['units']}", f"Verification: {disclosure['verification_status']}"]
    for title, key in (("Stale/incomplete systems", "stale_systems"), ("Conflicts", "conflict_summary"), ("Assumptions", "assumption_log"), ("Warnings", "warnings")):
        lines.append(title + ":")
        for item in disclosure[key] or ["None recorded; not independently verified."]:
            lines.append("- " + (item if isinstance(item, str) else json.dumps(item, sort_keys=True, default=str)))
    return lines
