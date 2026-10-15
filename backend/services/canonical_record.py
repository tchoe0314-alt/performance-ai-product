"""Authoritative project aggregate and explicit legacy compatibility projections.

Editable geometry stays in the canvas adapter. Result facets are owned once in
their canonical collections; legacy planner/UI shapes are reconstructed views.
Archived calculations remain immutable records referenced by project identity.
"""
from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

from .canonical_project import PROJECT_DOCUMENT_KEY, ProjectDocumentError, new_project_document, validate_project_document

OWNER = "project_record_v1"
FACETS = {
    "quantities": ("quantities", "cost_estimate"),
    "alternatives": ("design_alternatives_v1",),
    "sources": ("source_confidence_map_v1",),
    "assumptions": ("assumptions",),
}


def with_model_snapshot(project_input: dict) -> dict:
    """Explicit adapter for existing legacy input writers, never a second owner."""
    inputs = deepcopy(project_input)
    document = inputs.get(PROJECT_DOCUMENT_KEY)
    if not isinstance(document, dict) or OWNER not in document.get("extensions", {}):
        return inputs
    state = document["extensions"][OWNER]
    meta = deepcopy(inputs.get("meta") or {})
    document["site"]["site_inputs_v1"] = meta.pop("site_inputs", {})
    state["input_meta"] = meta
    state["input_controls"] = {key: deepcopy(value) for key, value in inputs.items()
                               if key not in {PROJECT_DOCUMENT_KEY, "manual_fields", "meta"}}
    if "canvas_workspace_v1" not in document["extensions"]:
        state["legacy_manual_fields"] = deepcopy(inputs.get("manual_fields") or {})
        if "units" in state["legacy_manual_fields"]:
            document["units"]["length"] = state["legacy_manual_fields"]["units"]
    return inputs


def migration_report(record: dict) -> dict:
    """A conversion report, deliberately not a survey/engineering assertion."""
    inputs = record.get("project_input") or {}
    fields = inputs.get("manual_fields") or {}
    document = inputs.get(PROJECT_DOCUMENT_KEY) or {}
    return {"version": 1, "backup_key": "legacy_project_backup_v1", "lossless_compatibility_adapter": True,
            "engineering_verified": False, "length_units": fields.get("units") or document.get("units", {}).get("length"),
            "coordinate_system": deepcopy(document.get("coordinate_system") or {"horizontal_crs": None, "vertical_datum": None, "origin": None}),
            "canvas_object_count": len(fields.get("site_objects") or []), "has_saved_result": bool(record.get("latest_result"))}


def resolve_model_input(project_input: dict) -> dict:
    document = project_input.get(PROJECT_DOCUMENT_KEY)
    state = (document or {}).get("extensions", {}).get(OWNER)
    if not isinstance(state, dict):
        return deepcopy(project_input)
    if type(state.get("version")) is not int or state.get("version") != 1 or not isinstance(state.get("input_controls"), dict) or not isinstance(state.get("input_meta"), dict):
        raise ProjectDocumentError("Saved project model adapter is invalid.")
    if not isinstance(document.get("site", {}).get("site_inputs_v1", {}), dict) or ("legacy_manual_fields" in state and not isinstance(state["legacy_manual_fields"], dict)):
        raise ProjectDocumentError("Saved project model inputs are invalid.")
    active_id = state.get("active_result_id")
    if active_id is not None:
        matches = [item for item in document["calculation_results"] if item.get("owner") == OWNER and item.get("id") == active_id]
        if not isinstance(active_id, str) or len(matches) != 1 or not any(key in matches[0] for key in ("result_v1", "result_reference_v1")):
            raise ProjectDocumentError("Saved project result reference is invalid.")
    result = {**deepcopy(state["input_controls"]), PROJECT_DOCUMENT_KEY: deepcopy(document)}
    result["meta"] = {**deepcopy(state["input_meta"]), "site_inputs": deepcopy(document["site"].get("site_inputs_v1") or {})}
    if "legacy_manual_fields" in state:
        result["manual_fields"] = deepcopy(state["legacy_manual_fields"])
        if "units" in result["manual_fields"] or document["units"].get("length") is not None:
            result["manual_fields"]["units"] = document["units"].get("length")
    elif "manual_fields" in project_input:
        result["manual_fields"] = deepcopy(project_input["manual_fields"])
    return result


def result_from_document(document: dict, sidecar: dict | None = None) -> dict:
    state = document.get("extensions", {}).get(OWNER) or {}
    active_id = state.get("active_result_id")
    active = next((item for item in document["calculation_results"] if item.get("owner") == OWNER and item.get("id") == active_id and ("result_v1" in item or "result_reference_v1" in item)), None)
    if active is None:
        return {}
    result = deepcopy(active.get("result_v1") if "result_v1" in active else sidecar or {})
    for section in FACETS:
        item = next((item for item in document[section] if item.get("owner") == OWNER and item.get("result_id") == active_id), None)
        if item:
            if item.get("plan_facets_v1"):
                result.setdefault("final_plan", {}).setdefault("meta", {}).update(deepcopy(item["plan_facets_v1"]))
            if "root_assumptions_v1" in item:
                result["assumptions"] = deepcopy(item["root_assumptions_v1"])
    return result


def seal_record(record: dict, *, previous: dict | None = None, latest_result_supplied: bool = True, actor_user_id: str | None = None) -> dict:
    """Called only at locked persistence boundaries; leaves unknown records intact."""
    from .canonical_canvas import with_canvas_snapshot, seal_canvas_objects
    sealed = deepcopy(record)
    inputs = sealed.get("project_input") or {}
    previous_document = ((previous or {}).get("project_input") or {}).get(PROJECT_DOCUMENT_KEY)
    document = inputs.get(PROJECT_DOCUMENT_KEY)
    if document is None:
        document = new_project_document(name=sealed.get("name", ""))
        inputs = with_canvas_snapshot(inputs, document)
        document = inputs.get(PROJECT_DOCUMENT_KEY, document)
    document = validate_project_document(document)
    prior_ids = {item.get("id") for item in (((previous or {}).get("project_input") or {}).get("manual_fields") or {}).get("site_objects", []) if isinstance(item,dict) and isinstance(item.get("id"),str)}
    document = seal_canvas_objects(document, previous_document, actor_user_id=actor_user_id, prior_object_ids=prior_ids)
    # Canonical server-owned result/history facets cannot be erased by an old
    # browser's otherwise-valid canvas snapshot.
    if previous_document:
        for section in ("calculation_results", *FACETS, "revisions", "export_history"):
            retained = [deepcopy(item) for item in previous_document[section] if item.get("owner") == OWNER]
            document[section] = [item for item in document[section] if item.get("owner") != OWNER] + retained
    input_meta = deepcopy(inputs.get("meta") or {})
    from .edit_transactions import seal_edit_history
    from .canonical_canvas import resolve_canvas_input
    history_document = deepcopy(document)
    history_document["extensions"].pop(OWNER, None)
    history_inputs = resolve_canvas_input({**inputs, PROJECT_DOCUMENT_KEY: history_document})
    from .dependency_graph import validate_fixed_changes
    prior_inputs=resolve_canvas_input((previous or {}).get("project_input") or {})
    validate_fixed_changes((prior_inputs.get("manual_fields") or {}).get("site_objects") or [], (history_inputs.get("manual_fields") or {}).get("site_objects") or [])
    input_meta["edit_history_v1"] = seal_edit_history(history_inputs, (previous or {}).get("project_input") or {}, actor_user_id)
    prior_history=(((previous or {}).get("project_input") or {}).get("meta") or {}).get("edit_history_v1") or {}
    history=input_meta["edit_history_v1"]
    if not latest_result_supplied and (history["head"]!=prior_history.get("head") or len(history["transactions"])!=len(prior_history.get("transactions",[]))):
        current_heads={history["head"],prior_history.get("head")}
        invalidations={system for tx in history["transactions"] if tx["id"] in current_heads for system in tx["calculation_invalidations"]}
        statuses=deepcopy(input_meta.get("system_dirty_state") or {})
        if not isinstance(statuses,dict):statuses={}
        for system in invalidations:
            if statuses.get(system)=="fresh":statuses[system]="stale"
        if statuses:input_meta["system_dirty_state"]=statuses
    inputs["meta"] = deepcopy(input_meta)
    document["site"]["site_inputs_v1"] = input_meta.pop("site_inputs", {})
    controls = {key: deepcopy(value) for key, value in inputs.items() if key not in {PROJECT_DOCUMENT_KEY, "manual_fields", "meta"}}
    state = {"version": 1, "input_controls": controls, "input_meta": input_meta}
    if "canvas_workspace_v1" not in document["extensions"]:
        state["legacy_manual_fields"] = deepcopy(inputs.get("manual_fields") or {})
        if "units" in (inputs.get("manual_fields") or {}):
            document["units"]["length"] = inputs["manual_fields"]["units"]
    old_state = (previous_document or {}).get("extensions", {}).get(OWNER) or {}
    incoming_state = document["extensions"].get(OWNER) or {}
    state["active_result_id"] = old_state.get("active_result_id") or incoming_state.get("active_result_id")
    document["project"].update({key: deepcopy(sealed.get(key)) for key in ("project_id", "name", "description", "organization_id")})
    result = deepcopy(sealed.get("latest_result") or {})
    if not result and not previous and state["active_result_id"]:
        result = result_from_document(document)
        inline = next((item for item in document["calculation_results"] if item.get("owner") == OWNER and item.get("id") == state["active_result_id"] and "result_v1" in item), None)
        if inline is None:
            raise ProjectDocumentError("A copied project must include its saved result or a hydrated canonical document.")
        latest_result_supplied = bool(result)
    if result and latest_result_supplied:
        result_id = str((result.get("metadata") or {}).get("calculation_save_v1", {}).get("calculation_id") or
                        "result_" + sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24])
        state["active_result_id"] = result_id
        payload = deepcopy(result)
        meta = dict((payload.get("final_plan") or {}).get("meta") or {})
        for section, keys in FACETS.items():
            values = {key: meta.pop(key) for key in keys if key in meta}
            item = {"owner": OWNER, "id": f"{section}_{result_id}", "result_id": result_id, "plan_facets_v1": values}
            if section == "assumptions" and "assumptions" in payload:
                item["root_assumptions_v1"] = payload.pop("assumptions")
            document[section] = [old for old in document[section] if old.get("owner") != OWNER]
            if values or "root_assumptions_v1" in item:
                document[section].append(item)
        if "meta" in (payload.get("final_plan") or {}):
            payload["final_plan"]["meta"] = meta
        sealed["latest_result"] = payload
        document["calculation_results"] = [item for item in document["calculation_results"] if item.get("owner") != OWNER]
        document["calculation_results"].append({"owner": OWNER, "id": result_id, "result_reference_v1": {
            "storage": "project_result_sidecar", "id": result_id,
        }})
    document["calculation_results"] = [item for item in document["calculation_results"] if not (item.get("owner") == OWNER and "history_reference_v1" in item)]
    document["calculation_results"].append({"owner": OWNER, "id": "calculation_history", "history_reference_v1": {
        "project_id": sealed.get("project_id"), "collection": "project_calculation_history", "immutable": True,
    }})
    workflow = dict((sealed.get("metadata") or {}).get("workflow") or {})
    document["export_history"] = [item for item in document["export_history"] if item.get("owner") != OWNER]
    document["export_history"].extend({"owner": OWNER, "artifact_v1": deepcopy(item)} for item in workflow.get("artifacts") or [])
    document["revisions"] = [item for item in document["revisions"] if item.get("owner") != OWNER]
    if workflow.get("version_history"):
        document["revisions"].append({"owner": OWNER, "workflow_history_v1": deepcopy(workflow["version_history"])})
    if (sealed.get("metadata") or {}).get("branch_recovery_v1"):
        document["revisions"].append({"owner": OWNER, "branch_recovery_v1": deepcopy(sealed["metadata"]["branch_recovery_v1"])})
    document["extensions"][OWNER] = state
    sealed["project_input"] = {**inputs, PROJECT_DOCUMENT_KEY: validate_project_document(document)}
    return sealed


def portable_document(record: dict) -> dict:
    """Detached current aggregate, with its result hydrated for JSON round trips.

    Immutable archive/file references remain explicit references, not fictional
    embedded file contents or engineering verification.
    """
    document = validate_project_document(record["project_input"][PROJECT_DOCUMENT_KEY])
    state = document["extensions"].get(OWNER) or {}
    active_id = state.get("active_result_id")
    payload = deepcopy(record.get("latest_result") or {})
    meta = (payload.get("final_plan") or {}).get("meta") or {}
    for keys in FACETS.values():
        for key in keys:
            meta.pop(key, None)
    payload.pop("assumptions", None)
    for item in document["calculation_results"]:
        if item.get("owner") == OWNER and item.get("id") == active_id:
            item.pop("result_reference_v1", None)
            item["result_v1"] = payload
    return validate_project_document(document)


def project_view(record: dict, *, include_result: bool = True) -> dict:
    document = (record.get("project_input") or {}).get(PROJECT_DOCUMENT_KEY)
    if not isinstance(document, dict) or OWNER not in document.get("extensions", {}):
        return record
    from .canonical_canvas import resolve_canvas_input
    viewed = deepcopy(record)
    viewed["project_input"] = resolve_canvas_input(record["project_input"])
    if include_result:
        viewed["latest_result"] = result_from_document(document, record.get("latest_result"))
    workflow = viewed.setdefault("metadata", {}).setdefault("workflow", {})
    workflow["artifacts"] = [deepcopy(item["artifact_v1"]) for item in document["export_history"] if item.get("owner") == OWNER and "artifact_v1" in item]
    for item in document["revisions"]:
        if item.get("owner") == OWNER:
            if "workflow_history_v1" in item:
                workflow["version_history"] = deepcopy(item["workflow_history_v1"])
            if "branch_recovery_v1" in item:
                viewed["metadata"]["branch_recovery_v1"] = deepcopy(item["branch_recovery_v1"])
    return viewed
