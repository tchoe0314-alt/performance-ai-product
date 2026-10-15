"""Recorded preliminary requirements. This schema does not certify code compliance."""
from copy import deepcopy
from math import isfinite

KEY = "brief_requirements_v1"
DEFINITIONS = {
    "usable-acreage": ("ac", "number"), "storeys": ("storeys", "integer"),
    "parking-ratio": ("spaces/ksf", "number"), "drive-aisles": ("text", "text"),
    "access": ("text", "text"), "egress": ("text", "text"), "height": ("ft", "number"),
    "lot-coverage": ("%", "percentage"), "impervious": ("%", "percentage"),
    "open-space": ("%", "percentage"), "stormwater": ("text", "text"), "priorities": ("text", "text"),
}


def validate_brief_requirements(value):
    from .canonical_project import ProjectDocumentError
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or set(value) != {"version", "fields"} or not isinstance(value["fields"], dict):
        raise ProjectDocumentError("Invalid additional brief requirements.")
    for field, entry in value["fields"].items():
        if field not in DEFINITIONS or not isinstance(entry, dict) or set(entry) != {"value", "unit"}:
            raise ProjectDocumentError("Invalid brief requirement.")
        unit, kind = DEFINITIONS[field]
        if entry["unit"] != unit:
            raise ProjectDocumentError("Invalid requirement units.")
        raw = entry["value"]
        if raw is None:
            continue
        if kind == "text":
            if not isinstance(raw, str) or not raw.strip() or len(raw) > 2000:
                raise ProjectDocumentError("Invalid requirement notes.")
        elif type(raw) not in (int, float) or raw < 0 or raw > 1.7976931348623157e308 or not isfinite(raw) or kind == "integer" and (raw != int(raw) or raw > 9007199254740991) or kind == "percentage" and raw > 100:
            raise ProjectDocumentError("Invalid numeric requirement.")
    return deepcopy(value)


def attach_brief_requirement_review(result, inputs):
    stored = ((inputs.get("meta") or {}).get("site_inputs") or {}).get(KEY)
    if stored is None:
        return result
    requirements = validate_brief_requirements(stored)
    fields = {key: entry for key, entry in requirements["fields"].items() if entry["value"] is not None}
    if not fields:
        return result
    result = deepcopy(result)
    report = {"version": 1, "requirements": fields, "automatic_validation": "not_implemented", "professional_review_required": True, "construction_release_allowed": False}
    result.setdefault("metadata", {})["brief_requirement_review_v1"] = report
    plan = result.get("final_plan")
    if isinstance(plan, dict):
        meta = plan.setdefault("meta", {})
        meta["brief_requirement_review_v1"] = deepcopy(report)
        meta["construction_release_allowed"] = False
        note = "Additional recorded requirements were not automatically checked: " + ", ".join(fields) + ". Independent professional review remains required."
        meta["warnings"] = [*list(meta.get("warnings") or []), note]
        result["warnings"] = [*list(result.get("warnings") or []), note]
        readiness = meta.get("private_alpha_readiness")
        if isinstance(readiness, dict):
            blocker = "additional_brief_requirements_not_automatically_checked"
            next_action = "Have a qualified designer check the recorded brief requirements against this concept."
            readiness["status"] = "blocked"
            readiness["full_system_private_alpha_ready"] = False
            readiness["review_only"] = True
            readiness["construction_release_allowed"] = False
            readiness["construction_release_blocked"] = True
            readiness["construction_ready"] = False
            readiness["launch_recommendation"] = "blocked_before_private_alpha"
            readiness["blockers"] = list(dict.fromkeys([*list(readiness.get("blockers") or []), blocker]))
            readiness["blocker_count"] = len(readiness["blockers"])
            readiness["next_actions"] = [next_action, *list(readiness.get("next_actions") or [])]
            readiness.setdefault("sections", {})["additional_brief_requirements"] = {"status": "blocked", "blockers": [blocker], "warnings": [], "automatic_validation": "not_implemented"}
            if isinstance(result["metadata"].get("private_alpha_readiness"), dict):
                result["metadata"]["private_alpha_readiness"] = deepcopy(readiness)
    return result
