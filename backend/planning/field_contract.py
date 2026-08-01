from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Sequence

from .common import lower_text, safe_dict, safe_str


FIELD_SOURCE_USER = "user"
FIELD_SOURCE_INFER = "infer"
FIELD_SOURCE_OMIT = "omit"
FIELD_SOURCES = {FIELD_SOURCE_USER, FIELD_SOURCE_INFER, FIELD_SOURCE_OMIT}


def is_field_wrapper(value: Any) -> bool:
    return isinstance(value, dict) and "source" in value and "value" in value


def field_source(value: Any, default: str = FIELD_SOURCE_INFER) -> str:
    if is_field_wrapper(value) and value.get("source") in FIELD_SOURCES:
        return value.get("source")
    return default


def is_user_set(value: Any) -> bool:
    return field_source(value) == FIELD_SOURCE_USER


def is_inferable(value: Any) -> bool:
    return field_source(value) == FIELD_SOURCE_INFER


def is_omitted(value: Any) -> bool:
    return field_source(value) == FIELD_SOURCE_OMIT


def resolve_field(value: Any, default: Any = None, *, allow_infer: bool = True) -> Any:
    if not is_field_wrapper(value):
        return deepcopy(value if value is not None else default)
    src = field_source(value)
    if src == FIELD_SOURCE_OMIT:
        return None
    if src == FIELD_SOURCE_USER:
        return deepcopy(value.get("value", default))
    if src == FIELD_SOURCE_INFER:
        if allow_infer:
            return deepcopy(value.get("value", default))
        return None
    return deepcopy(default)


def make_field(value: Any = None, source: str = FIELD_SOURCE_INFER, assumption: str | None = None, confidence: float | None = None) -> Dict[str, Any]:
    return {"value": deepcopy(value), "source": source, "assumption": assumption, "confidence": confidence}


def preserve_field_states(parsed: Dict[str, Any]) -> Dict[str, Any]:
    parsed.setdefault("meta", {})
    field_states = dict(parsed["meta"].get("field_states") or {})

    def walk(node: Any, prefix: str = "") -> None:
        if prefix == "meta.field_states" or prefix.startswith("meta.field_states."):
            return
        if is_field_wrapper(node):
            field_states[prefix] = deepcopy(node)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else key
                walk(value, path)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
                walk(value, path)

    walk(parsed)
    parsed["meta"]["field_states"] = field_states
    parsed["meta"]["field_contract_version"] = parsed["meta"].get("field_contract_version") or "option2_v1"
    return parsed


def unwrap_fields_for_execution(value: Any) -> Any:
    if isinstance(value, dict):
        if "source" in value and "value" in value:
            if value.get("source") == FIELD_SOURCE_OMIT:
                return None
            return unwrap_fields_for_execution(value.get("value"))
        return {k: unwrap_fields_for_execution(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap_fields_for_execution(v) for v in value]
    return value


def wrap_fields_for_execution(value: Any) -> Any:
    if is_field_wrapper(value):
        return resolve_field(value)
    if isinstance(value, dict):
        return {k: unwrap_fields_for_execution(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap_fields_for_execution(v) for v in value]
    return value


def field_state(parsed: Dict[str, Any], path: str) -> Dict[str, Any] | None:
    return safe_dict(safe_dict(parsed.get("meta")).get("field_states")).get(path)


def field_path_is_omitted(parsed: Dict[str, Any], path: str) -> bool:
    return is_omitted(field_state(parsed, path))


def field_path_source(parsed: Dict[str, Any], path: str, default: str = FIELD_SOURCE_INFER) -> str:
    state = field_state(parsed, path)
    return lower_text(safe_dict(state).get("source") or default)


def field_path_is_inferred(parsed: Dict[str, Any], path: str) -> bool:
    return field_path_source(parsed, path) == FIELD_SOURCE_INFER


def field_path_is_user_locked(parsed: Dict[str, Any], path: str) -> bool:
    return field_path_source(parsed, path) == FIELD_SOURCE_USER


def omission_flags_from_parsed(parsed: Dict[str, Any]) -> Dict[str, bool]:
    return {
        "parking": field_path_is_omitted(parsed, "site_plan.parking_count"),
        "drainage": field_path_is_omitted(parsed, "drainage"),
        "utilities": field_path_is_omitted(parsed, "utility_network"),
        "grading": field_path_is_omitted(parsed, "grading"),
    }


def filter_actions_by_field_intent(parsed: Dict[str, Any], actions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    omit_parking = field_path_is_omitted(parsed, "site_plan.parking_count")
    omit_drainage = field_path_is_omitted(parsed, "drainage")
    omit_utilities = field_path_is_omitted(parsed, "utility_network")

    for action in actions:
        if not isinstance(action, dict):
            continue
        layer = safe_str(action.get("layer")).upper()
        if omit_parking and layer in {"PARKING"}:
            continue
        if omit_drainage and layer in {"DRAIN", "PIPE", "BASIN_BOUNDARY", "DRAIN_FLOW", "STORM"}:
            continue
        if omit_utilities and layer in {"UTILITY", "WATER", "SAN"}:
            continue
        filtered.append(action)
    return filtered
