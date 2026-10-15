"""Bind results to canvas/manual inputs without duplicating planner payloads.

This proves input association, not engineering validity or concurrency safety.
"""
from copy import deepcopy
import hashlib
import json
import struct
from typing import Any

from backend.services.canonical_canvas import resolve_canvas_input
from backend.services.canonical_project import PROJECT_DOCUMENT_KEY, ProjectDocumentError

BINDING_KEY = "canvas_result_binding_v1"


def canvas_live_input_signature(project_input: dict) -> str:
    """Portable binary-number encoding: identical in Python and browser JS."""
    resolved = resolve_canvas_input(project_input)
    fields = deepcopy(resolved.get("manual_fields") or {})
    fields.pop("project_name", None)
    fields.pop("file_name", None)
    value = {"manual_fields": fields, "site_inputs": (resolved.get("meta") or {}).get("site_inputs") or {}}
    def encode(item: Any) -> Any:
        if item is None: return ["null"]
        if isinstance(item, bool): return ["bool", item]
        if isinstance(item, (int, float)):
            return ["number", struct.pack(">d", float(item) if item else 0.0).hex()]
        if isinstance(item, str): return ["string", item]
        if isinstance(item, list): return ["array", [encode(value) for value in item]]
        if isinstance(item, dict):
            return ["object", [[key, encode(item[key])] for key in sorted(item, key=lambda key: key.encode("utf-16-be", errors="surrogatepass"))]]
        raise ValueError("Unsupported calculation input.")
    serialized = json.dumps(encode(value), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("ascii")).hexdigest()


def canvas_input_signature(project_input: dict) -> str | None:
    document = project_input.get(PROJECT_DOCUMENT_KEY)
    if not isinstance(document, dict) or not any(key in document.get("extensions", {}) for key in ("canvas_workspace_v1", "project_record_v1")):
        return None
    resolved = resolve_canvas_input(project_input)
    fields = deepcopy(resolved.get("manual_fields") or {})
    # Labels do not change geometry or engineering quantities.
    fields.pop("project_name", None)
    fields.pop("file_name", None)
    value = {"manual_fields": fields, "site_inputs": (resolved.get("meta") or {}).get("site_inputs") or {}}

    def normalize(item: Any) -> Any:
        if isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, dict):
            return {key: normalize(value) for key, value in item.items()}
        if isinstance(item, list):
            return [normalize(value) for value in item]
        return item

    serialized = json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def bind_canvas_result(result: dict, project_input: dict) -> dict:
    signature = canvas_input_signature(project_input)
    if signature is None:
        return result
    bound = deepcopy(result)
    bound.setdefault("metadata", {})[BINDING_KEY] = {
        "version": 1, "scope": "canvas_manual_fields_and_site_inputs", "input_signature": signature,
        "live_input_key_v1": canvas_live_input_signature(project_input),
    }
    bound["metadata"]["quantity_binding_v1"] = {
        "version": 1,
        "workflow_run_id": bound["metadata"].get("_workflow_run_id"),
        "input_signature": signature,
        "live_input_key_v1": bound["metadata"][BINDING_KEY]["live_input_key_v1"],
        "quantities_path": "final_plan.meta.quantities",
        "cost_estimate_path": "final_plan.meta.cost_estimate",
    }
    return bound


def canvas_result_freshness(result: dict, project_input: dict) -> dict | None:
    try:
        signature = canvas_input_signature(project_input)
    except (ProjectDocumentError, ValueError, TypeError):
        return {"version": 1, "status": "unverified", "reason": "invalid_project_inputs"}
    if signature is None or not result:
        return None
    binding = (result.get("metadata") or {}).get(BINDING_KEY)
    if not isinstance(binding, dict) or binding.get("version") != 1 or binding.get("scope") != "canvas_manual_fields_and_site_inputs":
        return {"version": 1, "status": "unverified", "reason": "missing_input_binding"}
    return {"version": 1, "status": "current" if binding.get("input_signature") == signature else "stale",
            "scope": binding["scope"]}
