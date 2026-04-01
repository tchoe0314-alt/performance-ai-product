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
