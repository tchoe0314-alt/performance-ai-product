
# core/utils.py
# TRUE MAX MERGED CIVIL-GRADE VERSION

from __future__ import annotations

import math
import time
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# =========================================================
# SAFE / NORMALIZATION HELPERS
# =========================================================

def safe_num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    return int(round(safe_num(value, default)))


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = safe_text(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def ensure_dict(value: Any) -> Dict[str, Any]:
    return safe_dict(value)


def ensure_list(value: Any) -> List[Any]:
    return safe_list(value)


def normalize_text(value: Any, default: str = "") -> str:
    text = safe_text(value, default).strip().lower()
    return " ".join(text.split())


def safe_get(container: Any, path: Sequence[Any], default: Any = None) -> Any:
    current = container
    for key in path:
        if isinstance(current, dict):
            if key not in current:
                return default
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int):
            if key < 0 or key >= len(current):
                return default
            current = current[key]
        else:
            return default
    return current


def safe_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(safe_dict(base))
    for key, value in safe_dict(override).items():
        if key not in out:
            out[key] = deepcopy(value)
        elif isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = safe_merge_dicts(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def dedupe_list(items: Iterable[Any]) -> List[Any]:
    out: List[Any] = []
    seen: set[str] = set()
    for item in items:
        key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


# =========================================================
# GEOMETRY SAFE READERS
# =========================================================

def safe_origin(obj: Dict[str, Any], key: str = "origin") -> Tuple[float, float]:
    value = safe_dict(obj).get(key)
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return 0.0, 0.0
    return safe_num(value[0]), safe_num(value[1])


def safe_center(obj: Dict[str, Any], key: str = "center") -> Tuple[float, float]:
    value = safe_dict(obj).get(key)
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return 0.0, 0.0
    return safe_num(value[0]), safe_num(value[1])


def safe_points(obj: Dict[str, Any], key: str = "points") -> List[Tuple[float, float]]:
    pts = safe_dict(obj).get(key)
    if not isinstance(pts, (list, tuple)):
        return []

    out: List[Tuple[float, float]] = []
    for p in pts:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            out.append((safe_num(p[0]), safe_num(p[1])))
    return out


# =========================================================
# LABEL / STRING HELPERS
# =========================================================

def clean_label(label: Any, fallback: str = "") -> str:
    text = safe_text(label, fallback).upper().strip()
    if not text:
        return fallback

    replacements = {
        "BUILDING": "BLDG",
        "DRIVEWAY": "DRIVE",
        "PARKING": "PARK",
        "CENTERED": "",
        " FEET": "",
        " FT": "",
        "  ": " ",
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    text = " ".join(text.split())
    return text[:24]


def timestamped_filename(prefix: str = "output", ext: str = "dxf") -> str:
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.{ext}"


# =========================================================
# CAD / ACTION HELPERS
# =========================================================

def get_layer(action: Dict[str, Any], fallback: str) -> str:
    allowed = {
        "SITE",
        "SETBACK",
        "BUILDING",
        "PAVEMENT",
        "ANNO",
        "SYMBOL",
        "STRUCTURE",
        "WATER",
        "ROAD",
        "LOT",
        "SURFACE",
        "EG_CONTOUR",
        "FG_CONTOUR",
        "SPOT_EG",
        "SPOT_FG",
        "DRAIN_FLOW",
        "LOW_POINTS",
        "BASIN_BOUNDARY",
        "PIPE",
        "UTILITY",
        "SAN",
        "STORM",
    }
    layer = safe_text(safe_dict(action).get("layer"), fallback).upper()
    return layer if layer in allowed else fallback


def action_bbox(action: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    action = safe_dict(action)
    task = normalize_text(action.get("task"))

    if task == "rectangle":
        x, y = safe_origin(action)
        w = max(0.0, safe_num(action.get("width"), 0.0))
        h = max(0.0, safe_num(action.get("height"), 0.0))
        return (x, y, x + w, y + h)

    if task in {"polyline", "polygon"}:
        pts = safe_points(action)
        return bbox_from_points(pts)

    if task in {"circle", "arc"}:
        cx, cy = safe_center(action)
        r = max(0.0, safe_num(action.get("radius"), 0.0))
        return (cx - r, cy - r, cx + r, cy + r)

    if task in {"text_note", "point", "north_arrow"}:
        x, y = safe_origin(action)
        return (x, y, x, y)

    return None


# =========================================================
# GEOMETRY HELPERS
# =========================================================

def rect_area(width: Any, height: Any) -> float:
    return max(0.0, safe_num(width, 0.0)) * max(0.0, safe_num(height, 0.0))


def polygon_area(points: List[Tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    pts = points[:]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    area = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def polyline_length(points: Sequence[Tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        x1, y1 = points[i - 1]
        x2, y2 = points[i]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def bbox_from_points(points: Sequence[Tuple[float, float]]) -> Optional[Tuple[float, float, float, float]]:
    if not points:
        return None
    xs = [safe_num(p[0]) for p in points]
    ys = [safe_num(p[1]) for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def combine_bboxes(*bboxes: Optional[Tuple[float, float, float, float]]) -> Optional[Tuple[float, float, float, float]]:
    valid = [b for b in bboxes if b is not None]
    if not valid:
        return None
    min_x = min(b[0] for b in valid)
    min_y = min(b[1] for b in valid)
    max_x = max(b[2] for b in valid)
    max_y = max(b[3] for b in valid)
    return (min_x, min_y, max_x, max_y)


def bbox_width(bbox: Optional[Tuple[float, float, float, float]]) -> float:
    if bbox is None:
        return 0.0
    return max(0.0, bbox[2] - bbox[0])


def bbox_height(bbox: Optional[Tuple[float, float, float, float]]) -> float:
    if bbox is None:
        return 0.0
    return max(0.0, bbox[3] - bbox[1])


def bbox_area(bbox: Optional[Tuple[float, float, float, float]]) -> float:
    return rect_area(bbox_width(bbox), bbox_height(bbox))


# =========================================================
# PLAN SUMMARY HELPERS
# =========================================================

def summarize_layers(actions: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for action in actions:
        layer = safe_text(safe_dict(action).get("layer"), "SITE").upper()
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def summarize_action_count_by_task(actions: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for action in actions:
        task = normalize_text(safe_dict(action).get("task"), "unknown")
        counts[task] = counts.get(task, 0) + 1
    return counts


def estimate_plan_bbox(actions: Sequence[Dict[str, Any]]) -> Optional[Tuple[float, float, float, float]]:
    bboxes = [action_bbox(action) for action in actions]
    return combine_bboxes(*bboxes)
