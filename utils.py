import time
from typing import Any, Dict, List, Tuple


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


def safe_origin(obj: Dict[str, Any], key: str = "origin") -> Tuple[float, float]:
    value = obj.get(key)
    if not isinstance(value, list) or len(value) < 2:
        return 0.0, 0.0
    return safe_num(value[0]), safe_num(value[1])


def safe_center(obj: Dict[str, Any], key: str = "center") -> Tuple[float, float]:
    value = obj.get(key)
    if not isinstance(value, list) or len(value) < 2:
        return 0.0, 0.0
    return safe_num(value[0]), safe_num(value[1])


def safe_points(obj: Dict[str, Any], key: str = "points") -> List[Tuple[float, float]]:
    pts = obj.get(key)
    if not isinstance(pts, list):
        return []
    out: List[Tuple[float, float]] = []
    for p in pts:
        if isinstance(p, list) and len(p) >= 2:
            out.append((safe_num(p[0]), safe_num(p[1])))
    return out


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
    }
    layer = safe_text(action.get("layer"), fallback).upper()
    return layer if layer in allowed else fallback


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