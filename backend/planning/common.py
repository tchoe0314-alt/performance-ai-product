from __future__ import annotations

import importlib
import inspect
from typing import Any, Dict, Iterable, List, Sequence


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(round(float(value)))
    except Exception:
        return int(default)


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


_CANONICAL_STAGE_KEYS: Dict[str, tuple[str, str]] = {
    "grading": ("grading_summary", "grading"),
    "drainage": ("drainage_canonical", "drainage"),
    "storm": ("storm_pipe_summary", "storm_pipe_summary"),
    "storm_pipes": ("storm_pipe_summary", "storm_pipe_summary"),
    "storm_pipe_summary": ("storm_pipe_summary", "storm_pipe_summary"),
    "sanitary": ("sanitary_summary", "sanitary"),
    "utilities": ("utility_summary", "utilities"),
    "utility_network": ("utility_summary", "utilities"),
    "coordination": ("coordination_summary", "coordination"),
    "parking_program": ("parking_program", "parking_program"),
    "profiles": ("profiles", "profiles"),
    "cross_sections": ("cross_sections", "cross_sections"),
    "alignments": ("alignments", "alignments"),
}


def bounded_copy(value: Any, *, max_depth: int = 8, max_items: int = 600) -> Any:
    """Copy JSON-like stage payloads without chasing huge/cyclic graphs.

    Canonical stage summaries can include rich engine metadata. During
    coordination solving these summaries are read repeatedly for candidate
    snapshots, so an unbounded ``deepcopy`` can become the bottleneck or hang on
    accidental cycles. This helper preserves normal scalar/list/dict payloads
    while placing a hard ceiling on traversal.
    """

    seen: set[int] = set()

    def _copy(item: Any, depth: int) -> Any:
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        if depth <= 0:
            return "<truncated>"
        item_id = id(item)
        if item_id in seen:
            return "<cycle>"
        if isinstance(item, dict):
            seen.add(item_id)
            out: Dict[Any, Any] = {}
            for index, (key, nested) in enumerate(item.items()):
                if index >= max_items:
                    out["__truncated__"] = True
                    out["__truncated_count__"] = max(0, len(item) - max_items)
                    break
                out[key] = _copy(nested, depth - 1)
            seen.discard(item_id)
            return out
        if isinstance(item, (list, tuple)):
            seen.add(item_id)
            out = [_copy(nested, depth - 1) for nested in list(item)[:max_items]]
            if len(item) > max_items:
                out.append({"__truncated__": True, "__truncated_count__": len(item) - max_items})
            seen.discard(item_id)
            return out
        return str(item)

    return _copy(value, max_depth)


def _bounded_differs(left: Any, right: Any) -> bool:
    return bounded_copy(left, max_depth=3, max_items=80) != bounded_copy(right, max_depth=3, max_items=80)


def canonical_stage_output(project: Any, manager: Any, stage: str) -> Any:
    """Return accepted canonical stage state.

    ProjectModel.meta is authoritative. ProjectManager.latest_outputs is a
    convenience cache and is only used when project.meta does not contain an
    accepted value yet.
    """

    stage_key = safe_str(stage)
    meta_key, cache_key = _CANONICAL_STAGE_KEYS.get(stage_key, (stage_key, stage_key))
    project_meta = safe_dict(getattr(project, "meta", {}))
    latest_outputs = safe_dict(getattr(manager, "latest_outputs", {}))
    has_meta_value = meta_key in project_meta and project_meta.get(meta_key) is not None
    has_cache_value = cache_key in latest_outputs and latest_outputs.get(cache_key) is not None

    if has_meta_value:
        canonical_value = project_meta.get(meta_key)
        if has_cache_value and _bounded_differs(latest_outputs.get(cache_key), canonical_value):
            warnings = project_meta.setdefault("canonical_state_warnings", {})
            warnings[stage_key] = {
                "stage": stage_key,
                "canonical_meta_key": meta_key,
                "cache_key": cache_key,
                "cache_differs": True,
                "message": "manager.latest_outputs differs from project.meta; using project.meta as canonical accepted state.",
            }
        else:
            safe_dict(project_meta.get("canonical_state_warnings")).pop(stage_key, None)
        return bounded_copy(canonical_value)

    if has_cache_value:
        warnings = project_meta.setdefault("canonical_state_warnings", {})
        warnings[stage_key] = {
            "stage": stage_key,
            "canonical_meta_key": meta_key,
            "cache_key": cache_key,
            "cache_only": True,
            "message": "project.meta has no accepted stage summary; using manager.latest_outputs cache fallback.",
        }
        return bounded_copy(latest_outputs.get(cache_key))

    return [] if stage_key in {"profiles", "cross_sections", "alignments"} else {}


def lower_text(value: Any) -> str:
    return safe_str(value).lower()


def dedupe_keep_order(items: Iterable[Any]) -> List[Any]:
    out: List[Any] = []
    seen: set[str] = set()
    for item in items:
        key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def polyline_length(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        x1, y1 = safe_float(points[i - 1][0]), safe_float(points[i - 1][1])
        x2, y2 = safe_float(points[i][0]), safe_float(points[i][1])
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return total


def rect_area(width: Any, height: Any) -> float:
    return max(0.0, safe_float(width, 0.0)) * max(0.0, safe_float(height, 0.0))


def _call_with_compatible_kwargs(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    sig = inspect.signature(fn)
    params = sig.parameters
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return fn(*args, **kwargs)
    filtered = {k: v for k, v in kwargs.items() if k in params}
    return fn(*args, **filtered)


def _install_rect_obstacle_compatibility() -> None:
    try:
        geom_mod = importlib.import_module("core.geometry_core")
        rect_obstacle = getattr(geom_mod, "rect_obstacle", None)
        if rect_obstacle is None:
            return

        sig = inspect.signature(rect_obstacle)
        if getattr(rect_obstacle, "_codex_compat_wrapped", False):
            return

        supported_kwargs = {name for name in sig.parameters if name not in {"x", "y", "width", "height", "w", "h"}}

        def rect_obstacle_compat(x: float, y: float, w: float, h: float, **kwargs: Any) -> Any:
            filtered = {key: value for key, value in kwargs.items() if key in supported_kwargs}
            try:
                return rect_obstacle(x, y, w, h, **filtered)
            except Exception:
                if not filtered:
                    raise
            return {
                "type": "rectangle",
                "x": float(x),
                "y": float(y),
                "w": float(w),
                "h": float(h),
                **filtered,
            }

        setattr(rect_obstacle_compat, "_codex_compat_wrapped", True)
        setattr(geom_mod, "rect_obstacle", rect_obstacle_compat)
    except Exception:
        return
