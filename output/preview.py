# output/preview.py

from __future__ import annotations

from io import BytesIO
import re
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle, Arc

from core.utils import (
    clean_label,
    safe_center,
    safe_dict,
    safe_num,
    safe_origin,
    safe_points,
    safe_text,
)


# ----------------------------------------
# Styling helpers (aligned with civil CAD layer standard)
# ----------------------------------------

PREVIEW_ALLOW_HEURISTICS_DEFAULT = False
PREVIEW_ALLOW_SYNTHESIS_DEFAULT = False
PREVIEW_ALLOW_PROFILE_INFERENCE_DEFAULT = False
PREVIEW_MODE_DEFAULT = "production"

FINAL_GEOMETRY_LAYERS = {
    "C-BOUNDARY",
    "C-SETBACK",
    "C-CENTERLINE",
    "C-BUILDING",
    "C-PAVEMENT",
    "C-PARKING",
    "C-DRIVEWAY",
    "C-ROAD",
    "C-SIDEWALK",
    "C-CONTOUR",
    "C-SPOT-ELEV",
    "C-GRADING",
    "C-CUT",
    "C-FILL",
    "C-STRM-PIPE",
    "C-STRM-INLET",
    "C-STRM-MH",
    "C-DRAIN-FLOW",
    "C-LOW-POINT",
    "C-POND",
    "C-WATR",
    "C-SAN",
    "C-UTIL",
    "C-HYDRANT",
}

PROFILE_LAYER_VISIBILITY = {
    "layout": {
        "C-BOUNDARY",
        "C-SETBACK",
        "C-CENTERLINE",
        "C-BUILDING",
        "C-PAVEMENT",
        "C-PARKING",
        "C-DRIVEWAY",
        "C-ROAD",
        "C-SIDEWALK",
    },
    "grading": {
        "C-BOUNDARY",
        "C-SETBACK",
        "C-CENTERLINE",
        "C-BUILDING",
        "C-PAVEMENT",
        "C-PARKING",
        "C-DRIVEWAY",
        "C-ROAD",
        "C-SIDEWALK",
        "C-CONTOUR",
        "C-SPOT-ELEV",
        "C-GRADING",
        "C-CUT",
        "C-FILL",
    },
    "drainage": {
        "C-BOUNDARY",
        "C-SETBACK",
        "C-CENTERLINE",
        "C-BUILDING",
        "C-PAVEMENT",
        "C-PARKING",
        "C-DRIVEWAY",
        "C-ROAD",
        "C-SIDEWALK",
        "C-CONTOUR",
        "C-SPOT-ELEV",
        "C-GRADING",
        "C-CUT",
        "C-FILL",
        "C-STRM-INLET",
        "C-DRAIN-FLOW",
        "C-LOW-POINT",
        "C-POND",
    },
    "storm": {
        "C-BOUNDARY",
        "C-SETBACK",
        "C-CENTERLINE",
        "C-BUILDING",
        "C-PAVEMENT",
        "C-PARKING",
        "C-DRIVEWAY",
        "C-ROAD",
        "C-SIDEWALK",
        "C-CONTOUR",
        "C-SPOT-ELEV",
        "C-GRADING",
        "C-CUT",
        "C-FILL",
        "C-STRM-PIPE",
        "C-STRM-INLET",
        "C-STRM-MH",
        "C-DRAIN-FLOW",
        "C-LOW-POINT",
        "C-POND",
    },
    "utilities": {
        "C-BOUNDARY",
        "C-SETBACK",
        "C-CENTERLINE",
        "C-BUILDING",
        "C-PAVEMENT",
        "C-PARKING",
        "C-DRIVEWAY",
        "C-ROAD",
        "C-SIDEWALK",
        "C-CONTOUR",
        "C-SPOT-ELEV",
        "C-GRADING",
        "C-CUT",
        "C-FILL",
        "C-STRM-PIPE",
        "C-STRM-INLET",
        "C-STRM-MH",
        "C-DRAIN-FLOW",
        "C-LOW-POINT",
        "C-POND",
        "C-WATR",
        "C-SAN",
        "C-UTIL",
        "C-HYDRANT",
    },
    "complete": FINAL_GEOMETRY_LAYERS,
    "baseline": FINAL_GEOMETRY_LAYERS,
}

STANDARD_LAYERS = {
    "C-BOUNDARY",
    "C-SETBACK",
    "C-CENTERLINE",
    "C-BUILDING",
    "C-PAVEMENT",
    "C-PARKING",
    "C-DRIVEWAY",
    "C-ROAD",
    "C-SIDEWALK",
    "C-CONTOUR",
    "C-SPOT-ELEV",
    "C-GRADING",
    "C-CUT",
    "C-FILL",
    "C-STRM-PIPE",
    "C-STRM-INLET",
    "C-STRM-MH",
    "C-DRAIN-FLOW",
    "C-LOW-POINT",
    "C-POND",
    "C-WATR",
    "C-SAN",
    "C-UTIL",
    "C-HYDRANT",
    "C-TEXT",
    "C-DIMS",
    "C-LABEL",
}

LEGACY_LAYER_ALIASES = {
    "PARK": "PARKING",
    "WALKWAY": "WALK",
    "SIDEWALK": "WALK",
    "PAD": "SITE",
    "BASIN": "BASIN_BOUNDARY",
    "STAIRS": "SYMBOL",
    "ELEVATOR": "SYMBOL",
}

LEGACY_TO_STANDARD_LAYER = {
    "SITE": "C-BOUNDARY",
    "LOT": "C-BOUNDARY",
    "SETBACK": "C-SETBACK",
    "ROUTE": "C-CENTERLINE",
    "BUILDING": "C-BUILDING",
    "PAVEMENT": "C-PAVEMENT",
    "PARKING": "C-PARKING",
    "ROAD": "C-ROAD",
    "FIRE": "C-ROAD",
    "WALK": "C-SIDEWALK",
    "SURFACE": "C-GRADING",
    "EG_CONTOUR": "C-CONTOUR",
    "FG_CONTOUR": "C-CONTOUR",
    "SPOT_EG": "C-SPOT-ELEV",
    "SPOT_FG": "C-SPOT-ELEV",
    "PIPE": "C-STRM-PIPE",
    "STORM": "C-STRM-PIPE",
    "DRAIN": "C-STRM-INLET",
    "STRUCTURE": "C-STRM-MH",
    "BASIN_BOUNDARY": "C-POND",
    "DRAIN_FLOW": "C-DRAIN-FLOW",
    "LOW_POINTS": "C-LOW-POINT",
    "WATER": "C-WATR",
    "SAN": "C-SAN",
    "UTILITY": "C-UTIL",
    "ANNO": "C-TEXT",
    "TITLE": "C-TEXT",
    "SHEET": "C-TEXT",
    "DIM": "C-DIMS",
    "GRID": "C-DIMS",
    "AXIS": "C-DIMS",
    "VIEWPORT": "C-DIMS",
    "MATCHLINE": "C-DIMS",
    "HATCH": "C-DIMS",
    "SYMBOL": "C-LABEL",
    "LABEL": "C-LABEL",
    "SKETCH_ZONE": "C-LABEL",
    "SKETCH_OBS": "C-LABEL",
    "SKETCH_LINE": "C-LABEL",
    "SKETCH_PTS": "C-LABEL",
    "SKETCH_BLDG": "C-BUILDING",
    "SKETCH_PARK": "C-PARKING",
    "SKETCH_ROAD": "C-ROAD",
    "SKETCH_DRAIN": "C-STRM-PIPE",
    "SKETCH_UTIL": "C-UTIL",
    "SKETCH_PAD": "C-PAVEMENT",
    "SKETCH_BLDG_PTS": "C-LABEL",
    "SKETCH_DRAIN_PTS": "C-LABEL",
    "SKETCH_UTIL_PTS": "C-LABEL",
    "SKETCH_ROAD_PTS": "C-LABEL",
}

STANDARD_LAYER_COLORS = {
    "C-BOUNDARY": "#94a3b8",
    "C-SETBACK": "#d1d5db",
    "C-CENTERLINE": "#64748b",
    "C-BUILDING": "#0f172a",
    "C-PAVEMENT": "#64748b",
    "C-PARKING": "#cbd5e1",
    "C-DRIVEWAY": "#475569",
    "C-ROAD": "#475569",
    "C-SIDEWALK": "#0f766e",
    "C-CONTOUR": "#cbd5e1",
    "C-SPOT-ELEV": "#f59e0b",
    "C-GRADING": "#94a3b8",
    "C-CUT": "#dc2626",
    "C-FILL": "#f59e0b",
    "C-STRM-PIPE": "#1d4ed8",
    "C-STRM-INLET": "#0f766e",
    "C-STRM-MH": "#dc2626",
    "C-DRAIN-FLOW": "#0f766e",
    "C-LOW-POINT": "#1f2937",
    "C-POND": "#15803d",
    "C-WATR": "#0ea5e9",
    "C-SAN": "#7c3aed",
    "C-UTIL": "#6d28d9",
    "C-HYDRANT": "#dc2626",
    "C-TEXT": "#334155",
    "C-DIMS": "#475569",
    "C-LABEL": "#334155",
}

STANDARD_LAYER_LINEWIDTH = {
    "C-BOUNDARY": 1.2,
    "C-SETBACK": 1.0,
    "C-CENTERLINE": 1.2,
    "C-BUILDING": 2.5,
    "C-PAVEMENT": 2.0,
    "C-PARKING": 1.0,
    "C-DRIVEWAY": 2.0,
    "C-ROAD": 2.0,
    "C-SIDEWALK": 1.2,
    "C-CONTOUR": 1.0,
    "C-SPOT-ELEV": 1.1,
    "C-GRADING": 1.0,
    "C-CUT": 1.2,
    "C-FILL": 1.2,
    "C-STRM-PIPE": 2.0,
    "C-STRM-INLET": 1.8,
    "C-STRM-MH": 1.6,
    "C-DRAIN-FLOW": 1.5,
    "C-LOW-POINT": 1.5,
    "C-POND": 1.8,
    "C-WATR": 1.8,
    "C-SAN": 1.8,
    "C-UTIL": 1.8,
    "C-HYDRANT": 1.5,
    "C-TEXT": 1.0,
    "C-DIMS": 1.0,
    "C-LABEL": 1.0,
    "DEFAULT": 1.8,
}

STANDARD_LAYER_LINESTYLE = {
    "C-SETBACK": (0, (8, 4)),
    "C-CONTOUR": "--",
    "C-DRAIN-FLOW": (0, (4, 4)),
    "C-GRADING": (0, (2, 4)),
}

SUPPRESSED_AUTO_LABEL_LAYERS = {
    "C-BOUNDARY",
    "C-SETBACK",
    "C-PARKING",
    "C-SIDEWALK",
    "C-STRM-PIPE",
    "C-STRM-INLET",
    "C-STRM-MH",
    "C-DRAIN-FLOW",
    "C-POND",
    "C-UTIL",
    "C-WATR",
    "C-SAN",
    "C-CONTOUR",
    "C-SPOT-ELEV",
}
SUPPRESSED_TEXT_LAYERS = {"C-DRAIN-FLOW", "C-LOW-POINT", "C-UTIL", "C-WATR"}
FOCUS_EXCLUDED_LAYERS = {
    "C-TEXT",
    "C-DIMS",
    "C-BOUNDARY",
    "C-SETBACK",
    "C-UTIL",
    "C-WATR",
    "C-DRAIN-FLOW",
    "C-CONTOUR",
    "C-LOW-POINT",
}
SUPPRESSED_LABEL_TOKENS = (
    "AISLE-",
    "BUILDABLE_AREA",
    "GENERIC_UTILITY",
    "SERVICE_TIE",
    "SOURCE_SERVICE",
    "BUILDING_SERVICE",
    "UTILITY-",
)
PRIMARY_LAYOUT_LAYERS = {"C-BUILDING", "C-PAVEMENT", "C-PARKING", "C-SIDEWALK"}
PRIMARY_VIEW_LAYERS = {"C-BUILDING", "C-PAVEMENT", "C-PARKING", "C-SIDEWALK"}
KEY_ENGINEERING_VIEW_LAYERS = {"C-POND", "C-STRM-INLET", "C-STRM-PIPE", "C-STRM-MH", "C-SAN", "C-UTIL", "C-WATR", "C-DRAIN-FLOW", "C-LOW-POINT"}
SECONDARY_ENGINEERING_LAYERS = {
    "C-TEXT",
    "C-POND",
    "C-STRM-INLET",
    "C-STRM-PIPE",
    "C-STRM-MH",
    "C-SAN",
    "C-UTIL",
    "C-WATR",
    "C-DRAIN-FLOW",
    "C-CONTOUR",
    "C-SPOT-ELEV",
    "C-LOW-POINT",
    "C-GRADING",
    "C-CENTERLINE",
}

PHASE_ENGINEERING_FOCUS_LAYERS = {
    "layout": set(),
    "grading": {"C-CONTOUR", "C-SPOT-ELEV", "C-GRADING"},
    "drainage": {"C-STRM-INLET", "C-DRAIN-FLOW"},
    "storm": {"C-STRM-PIPE", "C-STRM-INLET", "C-STRM-MH", "C-POND", "C-DRAIN-FLOW"},
    "utilities": {"C-STRM-PIPE", "C-STRM-INLET", "C-STRM-MH", "C-POND", "C-DRAIN-FLOW", "C-SAN", "C-UTIL", "C-WATR"},
    "complete": {"C-STRM-PIPE", "C-STRM-INLET", "C-STRM-MH", "C-POND", "C-DRAIN-FLOW", "C-SAN", "C-UTIL", "C-WATR", "C-CONTOUR", "C-SPOT-ELEV"},
    "baseline": {"C-STRM-PIPE", "C-STRM-INLET", "C-STRM-MH", "C-POND", "C-SAN", "C-UTIL", "C-WATR"},
}


def _preview_options(plan: Dict[str, Any]) -> Dict[str, bool]:
    meta = safe_dict(plan.get("meta"))
    preview_options = safe_dict(meta.get("preview_options"))
    return {
        "preview_mode": safe_text(preview_options.get("preview_mode"), "") or PREVIEW_MODE_DEFAULT,
        "allow_heuristics": bool(
            preview_options.get("allow_heuristics", PREVIEW_ALLOW_HEURISTICS_DEFAULT)
        ),
        "allow_synthesis": bool(
            preview_options.get("allow_synthesis", PREVIEW_ALLOW_SYNTHESIS_DEFAULT)
        ),
        "allow_profile_inference": bool(
            preview_options.get("allow_profile_inference", PREVIEW_ALLOW_PROFILE_INFERENCE_DEFAULT)
        ),
    }


def _normalize_layer(raw_layer: str) -> str:
    raw = safe_text(raw_layer, "").upper().strip()
    if raw in STANDARD_LAYERS:
        return raw
    raw = LEGACY_LAYER_ALIASES.get(raw, raw)
    return LEGACY_TO_STANDARD_LAYER.get(raw, "C-TEXT")


def get_layer(action: Dict[str, Any], fallback: str = "C-TEXT") -> str:
    raw = safe_text(action.get("layer"), fallback).upper().strip()
    if not raw:
        return _normalize_layer(fallback)
    return _normalize_layer(raw)


def get_raw_layer(action: Dict[str, Any], fallback: str = "") -> str:
    raw = safe_text(action.get("layer"), fallback).upper().strip()
    raw = LEGACY_LAYER_ALIASES.get(raw, raw)
    return raw or safe_text(fallback, "").upper().strip()


def _layer_variant(action: Dict[str, Any]) -> str:
    raw = get_raw_layer(action)
    if raw in {"FG_CONTOUR", "SPOT_FG"}:
        return "FG"
    if raw in {"EG_CONTOUR", "SPOT_EG"}:
        return "EG"
    return ""


def _normalize_include_layers(include_layers: Optional[set[str]]) -> Optional[set[str]]:
    if not include_layers:
        return None
    normalized: set[str] = set()
    for layer in include_layers:
        if not layer:
            continue
        normalized.add(_normalize_layer(layer))
    return normalized or None

def _normalize_engineering_profile(profile):
    if profile is True:
        return "complete"
    if profile is False:
        return "baseline"
    if profile in (None, ""):
        return "layout"
    normalized = str(profile).strip().lower()
    return normalized or "layout"


def _normalize_preview_mode(mode: Optional[str]) -> str:
    if mode is None:
        return PREVIEW_MODE_DEFAULT
    normalized = str(mode).strip().lower()
    if normalized in {"production", "engineering", "debug"}:
        return normalized
    return PREVIEW_MODE_DEFAULT


def _is_final_geometry(action: Dict[str, Any]) -> bool:
    meta = safe_dict(action.get("meta"))
    if "is_final" in meta:
        return bool(meta.get("is_final"))
    if "final" in meta:
        return bool(meta.get("final"))
    return True


def _is_helper_geometry(action: Dict[str, Any]) -> bool:
    meta = safe_dict(action.get("meta"))
    if meta.get("is_helper") or meta.get("helper") or meta.get("debug"):
        return True
    role = safe_text(meta.get("role"), "").upper()
    if role and role in {"HELPER", "DEBUG", "ANCHOR", "CANDIDATE", "GUIDE", "TARGET"}:
        return True
    tags = action.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            tag_text = safe_text(tag, "").upper()
            if tag_text in {"HELPER", "DEBUG", "ANCHOR", "CANDIDATE", "GUIDE", "TARGET"}:
                return True
    label = clean_label(action.get("label"), "").upper()
    text = safe_text(action.get("text"), "").upper()
    canonical_source_type = safe_text(action.get("canonical_source_type"), "").upper()
    helper_signature = " ".join(part for part in (label, text, canonical_source_type) if part)
    if helper_signature:
        for token in (
            "ANCHOR",
            "CANDIDATE",
            "GUIDE",
            "RAY",
            "DEBUG",
            "HELPER",
            "EVAL",
            "EVALUATION",
            "TARGET",
            "CONNECTION",
            "CONNECTOR",
            "CONCEPT",
            "CONCEPTUAL",
            "BASIN_TARGET",
            "ACCESS_RAY",
            "FLOW_GUIDE",
        ):
            if token in helper_signature:
                return True
    raw_layer = get_raw_layer(action)
    if raw_layer.startswith("SKETCH_"):
        return True
    if raw_layer in {"ROUTE", "SKETCH_LINE", "SKETCH_PTS"}:
        return True
    if action.get("exportable") is False:
        return True
    return False


def _action_bounds(action):
    task = str(action.get("task") or "").lower()
    if task == "rectangle":
        x, y = safe_origin(action)
        w = safe_num(action.get("width"))
        h = safe_num(action.get("height"))
        if w <= 0 or h <= 0:
            return None
        return (x, y, x + w, y + h)
    if task in {"polygon", "polyline"}:
        points = safe_points(action)
        if len(points) < 2:
            return None
        xs = [safe_num(px) for px, _ in points]
        ys = [safe_num(py) for _, py in points]
        return (min(xs), min(ys), max(xs), max(ys))
    if task == "circle":
        center = safe_center(action)
        radius = safe_num(action.get("radius"))
        if center is None or radius <= 0:
            return None
        cx, cy = center
        return (cx - radius, cy - radius, cx + radius, cy + radius)
    if task in {"text_note", "point"}:
        x, y = safe_origin(action)
        return (x, y, x, y)
    return None


def _bounds_area(bounds):
    if not bounds:
        return 0.0
    min_x, min_y, max_x, max_y = bounds
    return max(0.0, max_x - min_x) * max(0.0, max_y - min_y)


def _contains_bounds(outer, inner, *, tolerance=0.0):
    if not outer or not inner:
        return False
    outer_min_x, outer_min_y, outer_max_x, outer_max_y = outer
    inner_min_x, inner_min_y, inner_max_x, inner_max_y = inner
    return (
        outer_min_x - tolerance <= inner_min_x
        and outer_min_y - tolerance <= inner_min_y
        and outer_max_x + tolerance >= inner_max_x
        and outer_max_y + tolerance >= inner_max_y
    )


def _is_wrapper_layout_shape(action, building_bounds):
    layer = get_raw_layer(action)
    task = str(action.get("task") or "").lower()
    label = clean_label(action.get("label"), "").upper()
    text = safe_text(action.get("text"), "").upper()
    if layer not in {"SITE", "SETBACK", "ROAD", "PAVEMENT", "PAD", "FIRE"}:
        return False
    if task not in {"rectangle", "polygon", "polyline"}:
        return False
    if label and label not in {"SITE", "LOT", "BUILDABLE_AREA", "DRIVE", "ROAD", "PAVEMENT"}:
        return False
    if text:
        return False
    if task == "polyline":
        points = safe_points(action)
        if len(points) < 4:
            return False
        first_x, first_y = points[0]
        last_x, last_y = points[-1]
        if abs(first_x - last_x) > 1e-6 or abs(first_y - last_y) > 1e-6:
            return False
    bounds = _action_bounds(action)
    if not bounds:
        return False
    contained_buildings = [item for item in building_bounds if _contains_bounds(bounds, item["bounds"], tolerance=1.0)]
    if len(contained_buildings) < max(2, len(building_bounds) - 1):
        return False
    wrapper_area = _bounds_area(bounds)
    if wrapper_area <= 0:
        return False
    max_building_area = max((_bounds_area(item["bounds"]) for item in contained_buildings), default=0.0)
    total_building_area = sum(_bounds_area(item["bounds"]) for item in contained_buildings)
    if max_building_area <= 0:
        return False
    min_building_x = min(item["bounds"][0] for item in contained_buildings)
    min_building_y = min(item["bounds"][1] for item in contained_buildings)
    max_building_x = max(item["bounds"][2] for item in contained_buildings)
    max_building_y = max(item["bounds"][3] for item in contained_buildings)
    wrapper_extends_past_layout = (
        bounds[0] < min_building_x - 10.0
        or bounds[1] < min_building_y - 10.0
        or bounds[2] > max_building_x + 10.0
        or bounds[3] > max_building_y + 10.0
    )
    return wrapper_extends_past_layout and wrapper_area >= max(max_building_area * 3.0, total_building_area * 1.1)


def _is_schematic_access_shape(action, building_bounds):
    layer = get_raw_layer(action)
    task = str(action.get("task") or "").lower()
    label = clean_label(action.get("label"), "").upper()
    if layer not in {"ROAD", "FIRE"}:
        return False
    if task == "rectangle":
        bounds = _action_bounds(action)
        if not bounds or not building_bounds or label:
            return False
        min_building_x = min(item["bounds"][0] for item in building_bounds)
        min_building_y = min(item["bounds"][1] for item in building_bounds)
        max_building_x = max(item["bounds"][2] for item in building_bounds)
        max_building_y = max(item["bounds"][3] for item in building_bounds)
        line_min_x, line_min_y, line_max_x, line_max_y = bounds
        width = max(1e-6, line_max_x - line_min_x)
        height = max(1e-6, line_max_y - line_min_y)
        if layer == "FIRE" and not label:
            if width > 40.0 and height <= 16.0:
                bar_y = (line_min_y + line_max_y) / 2.0
                if min_building_y - 60.0 <= bar_y <= max_building_y + 30.0:
                    return True
            if height > 80.0 and width <= 18.0:
                bar_x = (line_min_x + line_max_x) / 2.0
                if bar_x >= max_building_x + 10.0 or bar_x <= min_building_x - 10.0:
                    return True
        if layer == "FIRE" and width > 60.0 and height <= 12.0:
            bar_y = (line_min_y + line_max_y) / 2.0
            if min_building_y - 45.0 <= bar_y <= max_building_y + 25.0:
                return True
        if width > 120.0 and height <= 14.0:
            bar_y = (line_min_y + line_max_y) / 2.0
            return min_building_y - 40.0 <= bar_y <= max_building_y + 20.0
        if height > 120.0 and width <= 14.0:
            bar_x = (line_min_x + line_max_x) / 2.0
            return bar_x >= max_building_x + 20.0 or bar_x <= min_building_x - 20.0
        return False
    if task == "circle":
        if label:
            return False
        radius = safe_num(action.get("radius"))
        if not building_bounds or radius < 6.0:
            return False
        center = safe_center(action)
        bounds = _action_bounds(action)
        if not bounds or center is None:
            return False
        min_building_x = min(item["bounds"][0] for item in building_bounds)
        min_building_y = min(item["bounds"][1] for item in building_bounds)
        max_building_x = max(item["bounds"][2] for item in building_bounds)
        max_building_y = max(item["bounds"][3] for item in building_bounds)
        cx, cy = center
        line_min_x, line_min_y, line_max_x, line_max_y = bounds
        near_layout = (
            line_max_x >= min_building_x - 30.0
            and line_min_x <= max_building_x + 30.0
            and line_max_y >= min_building_y - 30.0
            and line_min_y <= max_building_y + 30.0
        )
        extends_outside_layout = (
            line_min_x < min_building_x - 10.0
            or line_max_x > max_building_x + 10.0
            or line_min_y < min_building_y - 10.0
            or line_max_y > max_building_y + 10.0
        )
        is_side_circle = (
            radius >= 20.0
            and min_building_y - 80.0 <= cy <= max_building_y + 80.0
            and (
                abs(cx - min_building_x) <= radius + 10.0
                or abs(cx - max_building_x) <= radius + 10.0
            )
        )
        return (near_layout and extends_outside_layout) or is_side_circle
    if task != "polyline":
        return False
    points = safe_points(action)
    if len(points) < 2:
        return False
    if label:
        return False
    bounds = _action_bounds(action)
    if not bounds:
        return False
    if not building_bounds:
        return False
    min_building_x = min(item["bounds"][0] for item in building_bounds)
    min_building_y = min(item["bounds"][1] for item in building_bounds)
    max_building_x = max(item["bounds"][2] for item in building_bounds)
    max_building_y = max(item["bounds"][3] for item in building_bounds)
    line_min_x, line_min_y, line_max_x, line_max_y = bounds
    width = max(1e-6, line_max_x - line_min_x)
    height = max(1e-6, line_max_y - line_min_y)
    is_axis_aligned = min(width, height) <= max(width, height) * 0.15
    layout_w = max(1.0, max_building_x - min_building_x)
    layout_h = max(1.0, max_building_y - min_building_y)
    if not is_axis_aligned:
        points = safe_points(action)
        first_point = points[0] if points else None
        last_point = points[-1] if points else None
        endpoint_outside = 0
        if first_point and not _point_within_layout(first_point, (min_building_x, min_building_y, max_building_x, max_building_y), padding=12.0):
            endpoint_outside += 1
        if last_point and not _point_within_layout(last_point, (min_building_x, min_building_y, max_building_x, max_building_y), padding=12.0):
            endpoint_outside += 1
        spans_multiple_sides = sum(
            (
                line_min_x < min_building_x - 20.0,
                line_max_x > max_building_x + 20.0,
                line_min_y < min_building_y - 20.0,
                line_max_y > max_building_y + 20.0,
            )
        ) >= 2
        diagonal_cross = (
            width >= layout_w * 0.45
            and height >= layout_h * 0.45
            and endpoint_outside >= 1
            and spans_multiple_sides
        )
        return diagonal_cross
    spans_into_layout = not (
        line_max_x < min_building_x
        or line_min_x > max_building_x
        or line_max_y < min_building_y
        or line_min_y > max_building_y
    )
    near_layout = (
        line_max_x >= min_building_x - 20.0
        and line_min_x <= max_building_x + 20.0
        and line_max_y >= min_building_y - 20.0
        and line_min_y <= max_building_y + 20.0
    )
    extends_outside_layout = (
        line_min_x < min_building_x - 40.0
        or line_max_x > max_building_x + 40.0
        or line_min_y < min_building_y - 40.0
        or line_max_y > max_building_y + 40.0
    )
    crosses_layout_center = (
        min_building_x <= (line_min_x + line_max_x) / 2.0 <= max_building_x
        or min_building_y <= (line_min_y + line_max_y) / 2.0 <= max_building_y
    )
    return ((spans_into_layout or near_layout) and extends_outside_layout) or (is_axis_aligned and extends_outside_layout and crosses_layout_center)


def get_linewidth(action):
    layer = get_layer(action, "C-TEXT")
    return STANDARD_LAYER_LINEWIDTH.get(layer, STANDARD_LAYER_LINEWIDTH["DEFAULT"])


def get_color(action):
    layer = get_layer(action, "C-TEXT")
    return STANDARD_LAYER_COLORS.get(layer, STANDARD_LAYER_COLORS["C-TEXT"])


def get_linestyle(action):
    layer = get_layer(action, "C-TEXT")
    return STANDARD_LAYER_LINESTYLE.get(layer, "-")


def _polyline_style(action):
    layer = get_layer(action, "C-TEXT")
    raw_layer = get_raw_layer(action)
    linewidth = get_linewidth(action)
    color = get_color(action)
    linestyle = get_linestyle(action)
    alpha = 1.0

    preview_profile = _normalize_engineering_profile(action.get("_preview_profile"))
    if preview_profile == "grading" and layer == "C-CONTOUR":
        variant = _layer_variant(action) or ("FG" if raw_layer == "FG_CONTOUR" else "EG")
        color = "#fbbf24" if variant == "FG" else "#dbe4ef"
        alpha = 0.2 if variant == "FG" else 0.12
        linewidth = max(0.5, linewidth * (0.58 if variant == "FG" else 0.55))

    return linewidth, color, linestyle, alpha


def _text_style(action):
    layer = get_layer(action, "C-TEXT")
    preview_profile = _normalize_engineering_profile(action.get("_preview_profile"))
    alpha = 0.8
    fontsize_adjust = 0.0
    bbox_alpha = 0.8

    if preview_profile == "grading" and layer == "C-SPOT-ELEV" and _layer_variant(action) == "FG":
        alpha = 0.5
        fontsize_adjust = -1.0
        bbox_alpha = 0.55

    return alpha, fontsize_adjust, bbox_alpha


def _rectangle_visual_style(action, w, h):
    layer = get_layer(action, "C-TEXT")
    preview_profile = _normalize_engineering_profile(action.get("_preview_profile"))
    label_upper = str(action.get("label") or "").upper()
    residential_court = layer == "C-PARKING" and label_upper.startswith("RES-PARK")
    retail_field = layer == "C-PARKING" and "RETAIL-PARK" in label_upper
    parking_area = w * h if layer == "C-PARKING" else 0.0

    fill_alpha = 0.0
    facecolor = "none"
    edge_alpha = 1.0
    linewidth_boost = 0.0
    stripe_alpha = None
    stripe_spacing = None
    stripe_gap = None

    if layer == "C-BUILDING":
        fill_alpha = 0.5 if preview_profile in {"layout", "grading"} else 0.2
        facecolor = get_color(action)
        linewidth_boost = 0.65 if preview_profile in {"layout", "grading"} else 0.3
    elif layer == "C-ROAD":
        fill_alpha = 0.06
        facecolor = get_color(action)
    elif layer == "C-PAVEMENT":
        fill_alpha = 0.055 if preview_profile in {"layout", "grading"} else 0.10
        facecolor = get_color(action)
    elif layer == "C-PARKING":
        if residential_court and (w >= 120.0 or parking_area >= 3000.0):
            fill_alpha = 0.002 if (preview_profile == "grading" or w >= 170.0 or parking_area >= 6500.0) else 0.006
        elif w >= 180.0 or h >= 40.0 or parking_area >= 7000.0:
            fill_alpha = 0.004 if preview_profile == "grading" else 0.006
        elif w >= 120.0 or parking_area >= 4000.0:
            fill_alpha = 0.01 if preview_profile == "grading" else 0.014
        else:
            fill_alpha = 0.018 if preview_profile == "grading" else 0.028
        facecolor = get_color(action)

        if residential_court and (w >= 120.0 or parking_area >= 3000.0):
            edge_alpha = 0.025 if (preview_profile == "grading" or w >= 170.0 or parking_area >= 6500.0) else 0.055
        elif w >= 180.0 or h >= 40.0 or parking_area >= 7000.0:
            edge_alpha = 0.04 if preview_profile == "grading" else 0.06
        elif w >= 120.0 or parking_area >= 4000.0:
            edge_alpha = 0.08 if preview_profile == "grading" else 0.12
        else:
            edge_alpha = 0.16 if preview_profile == "grading" else 0.22

        if w >= 24 and h >= 10:
            if residential_court and (w >= 120.0 or h >= 24.0):
                stripe_spacing = max(42.0, min(60.0, w / 4.8))
                stripe_alpha = 0.0 if (preview_profile == "grading" or w >= 170.0) else 0.012
                stripe_gap = max(86.0, min(150.0, w * 0.5))
            elif w >= 180.0 or h >= 40.0:
                stripe_spacing = max(52.0, min(68.0, w / 5.0))
                stripe_alpha = 0.0
                stripe_gap = max(160.0, min(320.0, w * 0.8))
            elif retail_field and (w >= 80.0 or parking_area >= 1800.0):
                stripe_spacing = max(22.0, min(28.0, w / 4.8))
                stripe_alpha = 0.04 if preview_profile == "grading" else 0.065
                stripe_gap = max(24.0, min(52.0, w * 0.18))
            elif w >= 160.0 or h >= 40.0:
                stripe_spacing = max(30.0, min(40.0, w / 6.5))
                stripe_alpha = 0.04 if preview_profile == "grading" else 0.06
                stripe_gap = max(70.0, min(120.0, w * 0.3))
            else:
                stripe_spacing = max(18.0, min(24.0, w / 5.0))
                stripe_alpha = 0.1 if preview_profile == "grading" else 0.14
                stripe_gap = 0.0
    elif layer == "C-SIDEWALK":
        fill_alpha = 0.03 if preview_profile == "grading" else 0.045
        facecolor = get_color(action)
    elif get_raw_layer(action) == "FIRE":
        fill_alpha = 0.0
        facecolor = "none"

    return {
        "fill_alpha": fill_alpha,
        "facecolor": facecolor,
        "edge_alpha": edge_alpha,
        "linewidth_boost": linewidth_boost,
        "stripe_alpha": stripe_alpha,
        "stripe_spacing": stripe_spacing,
        "stripe_gap": stripe_gap,
        "residential_court": residential_court,
        "retail_field": retail_field,
        "parking_area": parking_area,
    }


_GENERIC_BUILDING_LABEL_RE = re.compile(r"^(?:BLDG|BUILDING)\s*-?\s*\d+[A-Z]?$")
_GENERIC_SURFACE_LABEL_RE = re.compile(r"^(?:LOT\s+[A-Z0-9]+|PARK(?:ING)?(?:\s+LOT)?\s*-?\s*[A-Z0-9]*|LOT\s+BASE)$")


def _is_generic_default_label(layer: str, label: str) -> bool:
    upper = label.upper().strip()
    if layer == "C-BUILDING" and _GENERIC_BUILDING_LABEL_RE.fullmatch(upper):
        return True
    if layer in {"C-ROAD", "C-DRIVEWAY", "C-PAVEMENT"} and upper in {
        "DRIVE",
        "ROAD",
        "LOOP ROAD",
        "FRONTAGE",
        "ACCESS",
        "FIRE",
        "FIRE ACCESS",
        "ROAD-1",
        "FIRE-1",
    }:
        return True
    if layer in {"C-PARKING", "C-PAVEMENT"} and _GENERIC_SURFACE_LABEL_RE.fullmatch(upper):
        return True
    return False


def preview_label(action):
    layer = get_layer(action, "C-TEXT")
    label = clean_label(action.get("label"), "")
    if not label:
        return ""
    if layer in SUPPRESSED_AUTO_LABEL_LAYERS:
        return ""
    upper = label.upper()
    if any(token in upper for token in SUPPRESSED_LABEL_TOKENS):
        return ""
    if _is_generic_default_label(layer, label):
        return ""
    return label.replace("_", " ").strip()


def _should_draw_text_note(action):
    layer = get_layer(action, "C-TEXT")
    if layer in SUPPRESSED_TEXT_LAYERS:
        return False
    txt = safe_text(action.get("text"), "").strip()
    if not txt:
        return False
    upper = txt.upper()
    if len(txt) > 28:
        return False
    if any(token in upper for token in ("INV ", " S=", "LOW-", "GENERIC_UTILITY", "UTILITY-", "SERVICE_TIE", "SOURCE_SERVICE", "BUILDING_SERVICE")):
        return False
    return True


def _has_primary_site_geometry(actions):
    for action in actions:
        layer = get_layer(action, "C-TEXT")
        task = str(action.get("task") or "").lower()
        if layer in {"C-BUILDING", "C-PAVEMENT", "C-PARKING", "C-SIDEWALK"} and task in {"rectangle", "polygon", "polyline"}:
            return True
    return False


def _has_layout_scene(actions):
    for action in actions:
        layer = get_layer(action, "C-TEXT")
        task = str(action.get("task") or "").lower()
        if layer in PRIMARY_LAYOUT_LAYERS and task in {"rectangle", "polygon", "polyline"}:
            return True
    return False


def _rect_center(bounds):
    min_x, min_y, max_x, max_y = bounds
    return (min_x + max_x) / 2.0, (min_y + max_y) / 2.0


def _distance(a, b):
    if a is None or b is None:
        return 0.0
    ax, ay = a
    bx, by = b
    dx = safe_num(ax) - safe_num(bx)
    dy = safe_num(ay) - safe_num(by)
    return (dx * dx + dy * dy) ** 0.5


def _rect_gap(a, b):
    a_min_x, a_min_y, a_max_x, a_max_y = a
    b_min_x, b_min_y, b_max_x, b_max_y = b
    gap_x = max(0.0, max(b_min_x - a_max_x, a_min_x - b_max_x))
    gap_y = max(0.0, max(b_min_y - a_max_y, a_min_y - b_max_y))
    return gap_x, gap_y


def _merge_bounds(bounds_list):
    valid = [bounds for bounds in bounds_list if bounds]
    if not valid:
        return None
    min_x = min(bounds[0] for bounds in valid)
    min_y = min(bounds[1] for bounds in valid)
    max_x = max(bounds[2] for bounds in valid)
    max_y = max(bounds[3] for bounds in valid)
    return (min_x, min_y, max_x, max_y)


def _clip_segment_to_rect(p1, p2, rect):
    x_min, y_min, x_max, y_max = rect
    x1, y1 = p1
    x2, y2 = p2

    INSIDE = 0
    LEFT = 1
    RIGHT = 2
    BOTTOM = 4
    TOP = 8

    def _code(x, y):
        code = INSIDE
        if x < x_min:
            code |= LEFT
        elif x > x_max:
            code |= RIGHT
        if y < y_min:
            code |= BOTTOM
        elif y > y_max:
            code |= TOP
        return code

    code1 = _code(x1, y1)
    code2 = _code(x2, y2)

    while True:
        if not (code1 | code2):
            return (round(x1, 3), round(y1, 3)), (round(x2, 3), round(y2, 3))
        if code1 & code2:
            return None

        code_out = code1 or code2
        if code_out & TOP:
            x = x1 + (x2 - x1) * (y_max - y1) / max(y2 - y1, 1e-9)
            y = y_max
        elif code_out & BOTTOM:
            x = x1 + (x2 - x1) * (y_min - y1) / max(y2 - y1, 1e-9)
            y = y_min
        elif code_out & RIGHT:
            y = y1 + (y2 - y1) * (x_max - x1) / max(x2 - x1, 1e-9)
            x = x_max
        else:
            y = y1 + (y2 - y1) * (x_min - x1) / max(x2 - x1, 1e-9)
            x = x_min

        if code_out == code1:
            x1, y1 = x, y
            code1 = _code(x1, y1)
        else:
            x2, y2 = x, y
            code2 = _code(x2, y2)


def _clip_polyline_points(points, rect):
    if len(points) < 2:
        return []

    clipped = []
    for start, end in zip(points, points[1:]):
        clipped_segment = _clip_segment_to_rect(start, end, rect)
        if not clipped_segment:
            continue
        seg_start, seg_end = clipped_segment
        if not clipped or clipped[-1] != seg_start:
            clipped.append(seg_start)
        if clipped[-1] != seg_end:
            clipped.append(seg_end)
    return clipped


def _clip_grading_contour_action(action, layout_bounds):
    if not layout_bounds:
        return action
    if str(action.get("task") or "").lower() != "polyline":
        return action

    min_x, min_y, max_x, max_y = layout_bounds
    layout_w = max(max_x - min_x, 1.0)
    layout_h = max(max_y - min_y, 1.0)
    x_pad = min(max(12.0, layout_w * 0.025), 20.0)
    y_pad = min(max(40.0, layout_h * 0.42), 60.0)
    clip_rect = (
        min_x - x_pad,
        min_y - y_pad,
        max_x + x_pad,
        max_y + y_pad,
    )
    clipped_points = _clip_polyline_points(safe_points(action), clip_rect)
    if len(clipped_points) < 2:
        return None
    clipped = dict(action)
    clipped["points"] = [[x, y] for x, y in clipped_points]
    return clipped


def _grading_focus_bounds_from_buildings(building_rects, layout_bounds):
    bounds = _merge_bounds(building_rects) or layout_bounds
    if not bounds:
        return layout_bounds
    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    if width > height * 1.45:
        building_count = len(building_rects)
        if building_count >= 4:
            inset_x = min(max(96.0, width * 0.24), 160.0)
        elif building_count == 3:
            inset_x = min(max(60.0, width * 0.18), 112.0)
        else:
            inset_x = min(max(18.0, width * 0.11), 42.0)
        min_x += inset_x
        max_x -= inset_x
        if max_x - min_x < 80.0:
            mid_x = (bounds[0] + bounds[2]) / 2.0
            min_x = mid_x - 40.0
            max_x = mid_x + 40.0
    return (min_x, min_y, max_x, max_y)


def _point_within_layout(point, layout_bounds, padding=0.0):
    if not point or not layout_bounds:
        return False
    x, y = point
    min_x, min_y, max_x, max_y = layout_bounds
    return (
        min_x - padding <= x <= max_x + padding
        and min_y - padding <= y <= max_y + padding
    )


def _bounds_near_layout(bounds, layout_bounds, padding=0.0):
    if not bounds or not layout_bounds:
        return False
    min_x, min_y, max_x, max_y = bounds
    layout_min_x, layout_min_y, layout_max_x, layout_max_y = layout_bounds
    return not (
        max_x < layout_min_x - padding
        or min_x > layout_max_x + padding
        or max_y < layout_min_y - padding
        or min_y > layout_max_y + padding
    )


def _is_tiny_marker_circle(action):
    task = str(action.get("task") or "").lower()
    layer = get_layer(action, "C-TEXT")
    radius = safe_num(action.get("radius"))
    if task != "circle" or radius <= 0.0:
        return False
    if layer == "C-STRM-INLET":
        return False
    return layer in SECONDARY_ENGINEERING_LAYERS and radius <= 1.5


def _is_isolated_pavement_shape(action, building_bounds, parking_bounds):
    layer = get_layer(action, "C-TEXT")
    task = str(action.get("task") or "").lower()
    if layer != "C-PAVEMENT" or task not in {"rectangle", "polygon"}:
        return False
    bounds = _action_bounds(action)
    if not bounds:
        return False
    width = max(1e-6, bounds[2] - bounds[0])
    height = max(1e-6, bounds[3] - bounds[1])
    if min(width, height) > 18.0:
        return False
    layout_items = [*building_bounds, *parking_bounds]
    if not layout_items:
        return False
    nearest = min(
        (_rect_gap(bounds, other)[0] + _rect_gap(bounds, other)[1])
        for other in layout_items
    )
    center_x, center_y = _rect_center(bounds)
    min_x = min(item[0] for item in layout_items)
    min_y = min(item[1] for item in layout_items)
    max_x = max(item[2] for item in layout_items)
    max_y = max(item[3] for item in layout_items)
    outside_cluster = (
        center_x < min_x - 10.0
        or center_x > max_x + 10.0
        or center_y < min_y - 10.0
        or center_y > max_y + 10.0
    )
    return nearest >= 10.0 and outside_cluster


def _synthesize_drive_aisles(building_rects, parking_rects):
    if not parking_rects:
        return []
    parking_with_centers = [(_rect_center(bounds), bounds) for bounds in parking_rects]
    centers_y = [center[1] for center, _ in parking_with_centers]
    if not centers_y:
        return []
    max_center_y = max(centers_y)
    min_center_y = min(centers_y)
    row_split = (max_center_y + min_center_y) / 2.0
    upper_row = [bounds for (center, bounds) in parking_with_centers if center[1] >= row_split]
    lower_row = [bounds for (center, bounds) in parking_with_centers if center[1] < row_split]
    if not upper_row:
        upper_row = [bounds for _, bounds in parking_with_centers]
    drive_actions = []

    def _row_aisles(row_bounds):
        row_bounds = sorted(row_bounds, key=lambda bounds: _rect_center(bounds)[0])
        if not row_bounds:
            return [], 0.0, 0.0
        row_min_y = min(bounds[1] for bounds in row_bounds)
        row_max_y = max(bounds[3] for bounds in row_bounds)
        row_min_x = min(bounds[0] for bounds in row_bounds)
        row_max_x = max(bounds[2] for bounds in row_bounds)
        parking_height = max(bounds[3] - bounds[1] for bounds in row_bounds)
        aisle_height = round(max(4.0, min(7.0, parking_height * 0.18)), 3)
        aisle_y = round(row_min_y - aisle_height - 2.0, 3)
        aisles = []
        gap = 8.0
        for idx, bounds in enumerate(row_bounds):
            px1, _, px2, _ = bounds
            start_x = px1 + 2.0
            end_x = px2 - 2.0
            if idx > 0:
                prev_px2 = row_bounds[idx - 1][2]
                start_x = min(start_x, prev_px2 + gap)
            if idx + 1 < len(row_bounds):
                next_px1 = row_bounds[idx + 1][0]
                end_x = max(end_x, next_px1 - gap)
            aisle = {
                "task": "rectangle",
                "layer": "C-PAVEMENT",
                "origin": [round(start_x, 3), aisle_y],
                "width": round(min(max(14.0, end_x - start_x), max(120.0, (px2 - px1) + 24.0), 180.0), 3),
                "height": aisle_height,
            }
            aisles.append(aisle)
        return aisles, aisle_y, aisle_height, (row_min_x, row_min_y, row_max_x, row_max_y)

    upper_aisles, upper_aisle_y, upper_aisle_height, upper_span = _row_aisles(upper_row)
    drive_actions.extend(upper_aisles)

    lower_aisles = []
    lower_aisle_y = 0.0
    lower_aisle_height = 0.0
    lower_span = None
    if lower_row:
        lower_aisles, lower_aisle_y, lower_aisle_height, lower_span = _row_aisles(lower_row)
        drive_actions.extend(lower_aisles)

    return drive_actions


def _looks_like_parking_module(
    bounds: tuple[float, float, float, float],
    building_rects: Sequence[tuple[float, float, float, float]],
) -> bool:
    x1, y1, x2, y2 = bounds
    w = x2 - x1
    h = y2 - y1
    if w <= 0.0 or h <= 0.0:
        return False
    min_dim = min(w, h)
    max_dim = max(w, h)
    if min_dim < 12.0:
        return False
    if max_dim < 30.0:
        return False
    if (w * h) < 500.0:
        return False
    aspect = max_dim / max(min_dim, 1e-6)
    near_building = any(
        (_rect_gap(bounds, b_bounds)[0] + _rect_gap(bounds, b_bounds)[1]) <= 140.0
        for b_bounds in building_rects
    )
    return near_building and (aspect >= 1.6 or max_dim >= 70.0)


def _synthesize_layout_preview_actions(actions):
    # Heuristic-only preview synthesis. Disabled by default; keep for explicit opt-in.
    raw_records = [dict(action) for action in actions if isinstance(action, dict)]
    building_rects = []
    pavement_rects = []
    has_parking = False
    has_walk = False

    def _has_parking_semantics(action):
        label = clean_label(action.get("label"), "").upper()
        if action.get("semantic_surface_role") == "circulation":
            return False
        if label in {"DRIVE", "ROAD", "FIRE", "FRONTAGE", "ACCESS"}:
            return False
        if label.startswith("PARK") or label.startswith("STALL"):
            return True
        if safe_num(action.get("stall_count")) > 0:
            return True
        item_type = str(action.get("type") or "").strip().lower()
        if item_type in {"frontage", "access_drive", "collector_aisle", "parking_aisle", "fire_lane"}:
            return False
        return item_type in {"parking", "parking_area", "parking_module", ""}

    for action in raw_records:
        layer = get_layer(action, "C-TEXT")
        bounds = _action_bounds(action)
        if layer == "C-BUILDING" and bounds:
            building_rects.append(bounds)

    records = []
    for action in raw_records:
        rec = dict(action)
        layer = get_layer(rec, "C-TEXT")
        task = str(rec.get("task") or "").lower()
        label = clean_label(rec.get("label"), "").upper()
        if layer == "C-ROAD":
            if task in {"circle", "polyline"}:
                if not label or label in {"ROAD", "DRIVE", "FIRE", "FIRE-1", "ROAD-1"}:
                    continue
            if task in {"rectangle", "polygon"} and (not label or label in {"ROAD", "DRIVE", "FIRE", "FIRE-1", "ROAD-1"}):
                rec["layer"] = "C-PAVEMENT"
                rec["semantic_surface_role"] = "circulation"
                layer = "C-PAVEMENT"
        bounds = _action_bounds(rec)
        if layer == "C-PAVEMENT" and bounds:
            pavement_rects.append((bounds, rec))
        elif layer == "C-PARKING":
            has_parking = True
        elif layer == "C-SIDEWALK":
            has_walk = True
        records.append(rec)

    synthesized = list(records)
    seen = {repr(action) for action in synthesized}

    if building_rects and not has_parking:
        for bounds, action in pavement_rects:
            if not _has_parking_semantics(action):
                continue
            center_x, _ = _rect_center(bounds)
            nearest_gap = min((_rect_gap(bounds, b_bounds) for b_bounds in building_rects), key=lambda pair: pair[0] + pair[1], default=(9999.0, 9999.0))
            overlaps_building_band = any(abs(center_x - _rect_center(b_bounds)[0]) <= max(bounds[2] - bounds[0], b_bounds[2] - b_bounds[0]) * 0.7 for b_bounds in building_rects)
            if nearest_gap[1] <= 120.0 and overlaps_building_band and _looks_like_parking_module(bounds, building_rects):
                out = dict(action)
                out["layer"] = "C-PARKING"
                key = repr(out)
                if key not in seen:
                    seen.add(key)
                    synthesized.append(out)

    parking_rects = [
        _action_bounds(action)
        for action in synthesized
        if get_layer(action, "C-TEXT") == "C-PARKING" and _action_bounds(action)
    ]
    if building_rects and parking_rects and not has_walk:
        for building_bounds in building_rects:
            bx1, by1, bx2, by2 = building_bounds
            bcx, _ = _rect_center(building_bounds)
            nearest_parking = min(parking_rects, key=lambda item: (_rect_gap(building_bounds, item)[0] + _rect_gap(building_bounds, item)[1]))
            px1, py1, px2, py2 = nearest_parking
            walk_width = round(max(6.0, min(10.0, (bx2 - bx1) * 0.12)), 3)
            walk_x = round(bcx - walk_width / 2.0, 3)
            if py2 <= by1:
                walk_y = round(py2, 3)
                walk_h = round(max(6.0, by1 - walk_y), 3)
            elif by2 <= py1:
                walk_y = round(by2, 3)
                walk_h = round(max(6.0, py1 - walk_y), 3)
            else:
                continue
            walk_action = {
                "task": "rectangle",
                "layer": "C-SIDEWALK",
                "origin": [walk_x, walk_y],
                "width": walk_width,
                "height": walk_h,
            }
            key = repr(walk_action)
            if key not in seen:
                seen.add(key)
                synthesized.append(walk_action)

    synthesized_circulation = []
    if building_rects and parking_rects:
        for action in _synthesize_drive_aisles(building_rects, parking_rects):
            key = repr(action)
            if key not in seen:
                seen.add(key)
                synthesized.append(action)
                synthesized_circulation.append(action)

    return synthesized


def _polyline_length(action):
    points = safe_points(action)
    if len(points) < 2:
        return 0.0
    length = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx = safe_num(x2) - safe_num(x1)
        dy = safe_num(y2) - safe_num(y1)
        length += (dx * dx + dy * dy) ** 0.5
    return length


def _engineering_overlay_actions(records, *, engineering_profile="layout", allow_heuristics: bool = False):
    engineering_profile = _normalize_engineering_profile(engineering_profile)
    if not allow_heuristics:
        return []
    allow_basin = engineering_profile in {"baseline", "storm", "utilities", "complete"}
    allow_pipe = engineering_profile in {"baseline", "storm", "utilities", "complete"}
    allow_drain = engineering_profile in {"baseline", "drainage", "storm", "utilities", "complete"}
    allow_contours = engineering_profile in {"grading", "storm", "utilities", "complete"}
    allow_contour_labels = engineering_profile in {"grading", "complete"}
    allow_spot_grades = engineering_profile in {"grading", "complete"}
    allow_flow = engineering_profile in {"drainage", "storm", "utilities", "complete"}
    rich_engineering = engineering_profile in {"baseline", "utilities", "complete"}
    overlay_limits = {
        "layout": {"line": 0, "flow": 0, "drain_label": 0, "contour": 0, "contour_label": 0, "spot": 0, "structure": 0, "utility": 0, "basin": 0},
        "grading": {"line": 0, "flow": 0, "drain_label": 0, "contour": 4, "contour_label": 0, "spot": 6, "structure": 0, "utility": 0, "basin": 0},
        "drainage": {"line": 4, "flow": 4, "drain_label": 6, "contour": 0, "contour_label": 0, "spot": 0, "structure": 6, "utility": 0, "basin": 0},
        "storm": {"line": 5, "flow": 3, "drain_label": 3, "contour": 3, "contour_label": 0, "spot": 0, "structure": 6, "utility": 0, "basin": 1},
        "utilities": {"line": 5, "flow": 2, "drain_label": 0, "contour": 3, "contour_label": 0, "spot": 0, "structure": 6, "utility": 3, "basin": 1},
        "complete": {"line": 5, "flow": 2, "drain_label": 0, "contour": 4, "contour_label": 4, "spot": 6, "structure": 6, "utility": 3, "basin": 2},
        "baseline": {"line": 4, "flow": 0, "drain_label": 0, "contour": 0, "contour_label": 0, "spot": 0, "structure": 6, "utility": 2, "basin": 1},
    }.get(engineering_profile, {})
    basin_candidates = []
    line_candidates = []
    flow_candidates = []
    contour_candidates = []
    contour_label_candidates = []
    spot_grade_candidates = []
    structure_candidates = []
    utility_candidates = []
    drain_label_candidates = []
    layout_bounds = _merge_bounds(
        [
            _action_bounds(action)
            for action in records
            if get_layer(action, "C-TEXT") in {"C-BUILDING", "C-PARKING", "C-PAVEMENT", "C-SIDEWALK"}
        ]
    )
    layout_center = None
    if layout_bounds:
        layout_center = (
            (layout_bounds[0] + layout_bounds[2]) / 2.0,
            (layout_bounds[1] + layout_bounds[3]) / 2.0,
        )
    layout_diag = 0.0 if not layout_bounds else ((layout_bounds[2] - layout_bounds[0]) ** 2 + (layout_bounds[3] - layout_bounds[1]) ** 2) ** 0.5
    layout_span = max(1.0, layout_diag)

    def _proximity_score(bounds, *, invert=False):
        if not bounds or layout_center is None:
            return 0.0
        center = _rect_center(bounds)
        distance = _distance(center, layout_center)
        normalized = distance / layout_span
        return normalized if invert else -normalized

    def _engineering_score(bounds, magnitude=0.0, *, favor_far=False, near_bonus=0.0):
        return magnitude + _proximity_score(bounds, invert=favor_far) + near_bonus

    def _grading_vertical_bias(bounds):
        if not bounds or layout_center is None:
            return 0.0
        _, cy = _rect_center(bounds)
        _, layout_cy = layout_center
        vertical_distance = abs(cy - layout_cy) / max(layout_span, 1.0)
        return -vertical_distance * 4.0

    def _is_oversized_for_layout(action):
        if not layout_bounds:
            return False
        bounds = _action_bounds(action)
        if not bounds:
            return False
        layout_min_x, layout_min_y, layout_max_x, layout_max_y = layout_bounds
        line_min_x, line_min_y, line_max_x, line_max_y = bounds
        layout_w = max(1.0, layout_max_x - layout_min_x)
        layout_h = max(1.0, layout_max_y - layout_min_y)
        width = max(1e-6, line_max_x - line_min_x)
        height = max(1e-6, line_max_y - line_min_y)
        encloses_layout = (
            line_min_x <= layout_min_x - 10.0
            and line_min_y <= layout_min_y - 10.0
            and line_max_x >= layout_max_x + 10.0
            and line_max_y >= layout_max_y + 10.0
        )
        oversized_diagonal = width >= layout_w * 0.65 and height >= layout_h * 0.45
        points = safe_points(action)
        first_point = points[0] if points else None
        last_point = points[-1] if points else None
        endpoint_outside = 0
        if first_point and not _point_within_layout(first_point, layout_bounds, padding=8.0):
            endpoint_outside += 1
        if last_point and not _point_within_layout(last_point, layout_bounds, padding=8.0):
            endpoint_outside += 1
        spans_multiple_sides = sum(
            (
                line_min_x < layout_min_x - 20.0,
                line_max_x > layout_max_x + 20.0,
                line_min_y < layout_min_y - 20.0,
                line_max_y > layout_max_y + 20.0,
            )
        ) >= 2
        line_length = _polyline_length(action) if points else max(width, height)
        diagonal_fanout = (
            line_length >= max(layout_w, layout_h) * 1.8
            and width >= layout_w * 0.55
            and height >= layout_h * 0.55
            and endpoint_outside >= 1
            and spans_multiple_sides
        )
        oversized_span = (
            line_length >= layout_w * 1.1
            and width >= layout_w * 0.9
            and height <= max(10.0, layout_h * 0.25)
            and endpoint_outside >= 2
        )
        midpoint_outside = False
        if points and layout_bounds:
            mid_idx = len(points) // 2
            midpoint_outside = not _point_within_layout(points[mid_idx], layout_bounds, padding=10.0)
        long_cross_site = (
            line_length >= max(layout_diag * 0.9, max(layout_w, layout_h) * 1.1)
            and endpoint_outside >= 1
            and midpoint_outside
            and (width >= layout_w * 0.45 or height >= layout_h * 0.45)
        )
        return encloses_layout or oversized_diagonal or diagonal_fanout or oversized_span or long_cross_site

    for action in records:
        layer = get_layer(action, "C-TEXT")
        variant = _layer_variant(action)
        task = str(action.get("task") or "").lower()
        bounds = _action_bounds(action)
        if not bounds:
            continue
        if allow_basin and layer == "C-POND" and task in {"circle", "polygon", "rectangle", "polyline"}:
            if _is_oversized_for_layout(action):
                continue
            basin_score = _engineering_score(
                bounds,
                (_bounds_area(bounds) ** 0.5) / max(layout_span, 1.0),
                favor_far=engineering_profile in {"storm", "utilities", "complete"},
            )
            basin_candidates.append((basin_score, action))
        elif (
            (
                task in {"polyline", "polygon"}
                and (
                    (layer == "C-STRM-PIPE" and allow_pipe)
                    or (layer == "C-STRM-INLET" and allow_drain)
                )
            )
            or (allow_drain and layer == "C-STRM-INLET" and task in {"circle", "rectangle"})
        ):
            if _is_oversized_for_layout(action):
                continue
            points = safe_points(action)
            if points:
                points_in_layout = sum(
                    1 for point in points if _point_within_layout(point, layout_bounds, padding=12.0)
                )
                if points_in_layout <= 1 and len(points) >= 2:
                    continue
            line_score = _polyline_length(action) if points else max(2.0, (_bounds_area(bounds) ** 0.5))
            if points and layout_bounds:
                points_in_layout = sum(
                    1 for point in points if _point_within_layout(point, layout_bounds, padding=12.0)
                )
            else:
                points_in_layout = 0
            phase_far = engineering_profile in {"storm", "utilities", "complete"} and layer == "C-STRM-PIPE"
            score = _engineering_score(
                bounds,
                line_score / max(layout_span, 1.0),
                favor_far=phase_far,
                near_bonus=min(points_in_layout, 6) * 0.2,
            )
            line_candidates.append((score, action))
        elif allow_flow and layer == "C-DRAIN-FLOW" and task in {"polyline", "polygon"}:
            if _is_oversized_for_layout(action) and not _bounds_near_layout(bounds, layout_bounds, padding=24.0):
                continue
            points = safe_points(action)
            if points:
                points_in_layout = sum(
                    1 for point in points if _point_within_layout(point, layout_bounds, padding=12.0)
                )
                if points_in_layout <= 1 and len(points) >= 2 and not _bounds_near_layout(bounds, layout_bounds, padding=18.0):
                    continue
            flow_score = _engineering_score(
                bounds,
                _polyline_length(action) / max(layout_span, 1.0),
                near_bonus=min(points_in_layout if points else 0, 6) * 0.25,
            )
            flow_candidates.append((flow_score, action))
        elif allow_drain and layer == "C-STRM-INLET" and task == "text_note":
            if not _bounds_near_layout(bounds, layout_bounds, padding=96.0):
                continue
            label_score = _engineering_score(bounds, 1.0)
            drain_label_candidates.append((label_score, action))
        elif allow_contours and layer == "C-CONTOUR" and task in {"polyline", "polygon"}:
            if engineering_profile == "grading" and variant == "EG":
                continue
            if engineering_profile in {"storm", "utilities", "complete"} and variant == "EG":
                continue
            if engineering_profile == "grading":
                if not _bounds_near_layout(bounds, layout_bounds, padding=112.0):
                    continue
                if layout_bounds:
                    x1, y1, x2, y2 = bounds
                    _, ly1, _, ly2 = layout_bounds
                    cy = (y1 + y2) / 2.0
                    if not (ly1 - 56.0 <= cy <= ly2 + 56.0):
                        continue
                if _is_oversized_for_layout(action) and not _bounds_near_layout(bounds, layout_bounds, padding=40.0):
                    continue
            else:
                if not _bounds_near_layout(bounds, layout_bounds, padding=140.0):
                    continue
                if _is_oversized_for_layout(action) and not _bounds_near_layout(bounds, layout_bounds, padding=32.0):
                    continue
                points = safe_points(action)
                if points:
                    points_in_layout = sum(
                        1 for point in points if _point_within_layout(point, layout_bounds, padding=16.0)
                    )
                    if points_in_layout <= 1 and len(points) >= 2 and not _bounds_near_layout(bounds, layout_bounds, padding=24.0):
                        continue
            contour_length = _polyline_length(action)
            contour_bias = 0.0
            if engineering_profile == "grading":
                contour_bias += _grading_vertical_bias(bounds)
            if engineering_profile in {"storm", "utilities", "complete"}:
                contour_bias = 0.35 if variant == "FG" else -0.4
            contour_score = _engineering_score(
                bounds,
                contour_length / max(layout_span, 1.0) + contour_bias,
            )
            contour_candidates.append((contour_score, action))
        elif allow_contour_labels and layer == "C-CONTOUR" and task == "text_note":
            if engineering_profile in {"grading", "complete"} and variant == "EG":
                continue
            padding = 132.0 if engineering_profile == "grading" else 140.0
            if not _bounds_near_layout(bounds, layout_bounds, padding=padding):
                if engineering_profile != "grading" or not layout_bounds:
                    continue
                x1, y1, x2, y2 = bounds
                lx1, ly1, lx2, ly2 = layout_bounds
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                horizontal_band = ly1 - 48.0 <= cy <= ly2 + 48.0
                if not horizontal_band:
                    continue
            elif engineering_profile == "grading" and layout_bounds:
                x1, y1, x2, y2 = bounds
                lx1, ly1, lx2, ly2 = layout_bounds
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                horizontal_band = ly1 - 42.0 <= cy <= ly2 + 42.0
                if not horizontal_band:
                    continue
            label_bias = 0.0
            if engineering_profile == "grading":
                label_bias += _grading_vertical_bias(bounds)
            if engineering_profile == "complete":
                label_bias = 0.35 if variant == "FG" else -0.4
            score = _engineering_score(bounds, 1.0 + label_bias)
            contour_label_candidates.append((score, action))
        elif allow_spot_grades and layer == "C-SPOT-ELEV" and task in {"text_note", "point"}:
            if engineering_profile in {"grading", "complete"} and variant == "EG":
                continue
            spot_padding = 28.0 if engineering_profile == "grading" else 36.0
            if not _bounds_near_layout(bounds, layout_bounds, padding=spot_padding):
                continue
            x1, y1, x2, y2 = bounds
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            if engineering_profile == "grading" and layout_bounds:
                lx1, ly1, lx2, ly2 = layout_bounds
                horizontal_band = ly1 - 28.0 <= cy <= ly2 + 28.0
                vertical_band = lx1 - 18.0 <= cx <= lx2 + 18.0
                if not (horizontal_band and vertical_band):
                    continue
            elif layout_bounds and not _point_within_layout((cx, cy), layout_bounds, padding=18.0):
                continue
            spot_bias = 0.0
            if engineering_profile == "complete":
                spot_bias = 0.35 if variant == "FG" else -0.4
            score = _engineering_score(bounds, 1.0 + spot_bias)
            if task == "text_note":
                score += max(1.0, len(safe_text(action.get("text"), "").strip())) * 0.02
            spot_grade_candidates.append((score, action))
        elif (allow_drain or allow_pipe) and layer == "C-STRM-MH" and task in {"circle", "rectangle"}:
            if _is_tiny_marker_circle(action):
                continue
            structure_score = _engineering_score(
                bounds,
                (_bounds_area(bounds) ** 0.5) / max(layout_span, 1.0),
            )
            structure_candidates.append((structure_score, action))
        elif rich_engineering and layer in {"C-UTIL", "C-WATR"} and task in {"polyline", "polygon"}:
            label = clean_label(action.get("label"), "").upper()
            text = safe_text(action.get("text"), "").upper()
            canonical_source_type = str(action.get("canonical_source_type") or "").upper()
            helper_signature = " ".join(part for part in (label, text, canonical_source_type) if part)
            if not helper_signature:
                continue
            if any(token in helper_signature for token in ("SERVICE", "TIE", "GENERIC_UTILITY", "BUILDING_SERVICE", "SOURCE_SERVICE", "UTILITY-")):
                continue
            if _is_oversized_for_layout(action):
                continue
            points = safe_points(action)
            if points:
                points_in_layout = sum(
                    1 for point in points if _point_within_layout(point, layout_bounds, padding=12.0)
                )
                if points_in_layout <= 1 and len(points) >= 2:
                    continue
            utility_score = _engineering_score(
                bounds,
                _polyline_length(action) / max(layout_span, 1.0),
                favor_far=engineering_profile in {"utilities", "complete"},
            )
            utility_candidates.append((utility_score, action))

    selected = []
    seen = set()

    for _, action in sorted(basin_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("basin", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(line_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("line", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(flow_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("flow", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(drain_label_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("drain_label", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(contour_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("contour", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    contour_label_limit = int(overlay_limits.get("contour_label", 0))
    kept_contour_texts = set()
    kept_contour_labels = 0
    for _, action in sorted(contour_label_candidates, key=lambda item: item[0], reverse=True):
        if kept_contour_labels >= contour_label_limit:
            break
        label_text = safe_text(action.get("text"), "").strip().upper()
        if engineering_profile == "grading" and label_text:
            if label_text in kept_contour_texts:
                continue
            kept_contour_texts.add(label_text)
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)
            kept_contour_labels += 1

    spot_limit = int(overlay_limits.get("spot", 0))
    kept_spot_texts = set()
    kept_spots = 0
    for _, action in sorted(spot_grade_candidates, key=lambda item: item[0], reverse=True):
        if kept_spots >= spot_limit:
            break
        spot_text = safe_text(action.get("text"), "").strip().upper()
        if engineering_profile == "grading" and spot_text:
            if spot_text in kept_spot_texts:
                continue
            kept_spot_texts.add(spot_text)
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)
            kept_spots += 1

    for _, action in sorted(structure_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("structure", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(utility_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("utility", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    return selected


def _bounds_overlap_ratio(a, b):
    if not a or not b:
        return 0.0
    ix1 = max(safe_num(a[0]), safe_num(b[0]))
    iy1 = max(safe_num(a[1]), safe_num(b[1]))
    ix2 = min(safe_num(a[2]), safe_num(b[2]))
    iy2 = min(safe_num(a[3]), safe_num(b[3]))
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    intersection = (ix2 - ix1) * (iy2 - iy1)
    return intersection / max(min(_bounds_area(a), _bounds_area(b)), 1e-6)


def _dedupe_primary_layout_records(records):
    deduped = []
    for action in records:
        layer = get_layer(action, "C-TEXT")
        task = str(action.get("task") or "").lower()
        if layer not in PRIMARY_LAYOUT_LAYERS or task not in {"rectangle", "polygon"}:
            deduped.append(action)
            continue
        bounds = _action_bounds(action)
        if not bounds:
            deduped.append(action)
            continue
        label = clean_label(action.get("label"), "").upper()
        duplicate_idx = None
        for idx, existing in enumerate(deduped):
            existing_layer = get_layer(existing, "C-TEXT")
            existing_task = str(existing.get("task") or "").lower()
            if existing_layer != layer or existing_task not in {"rectangle", "polygon"}:
                continue
            existing_bounds = _action_bounds(existing)
            if not existing_bounds:
                continue
            existing_label = clean_label(existing.get("label"), "").upper()
            labels_match = bool(label and existing_label and label == existing_label)
            if not labels_match and _bounds_overlap_ratio(bounds, existing_bounds) < 0.92:
                continue
            existing_is_canonical = bool(existing.get("canonical_source_id"))
            current_is_canonical = bool(action.get("canonical_source_id"))
            if current_is_canonical and not existing_is_canonical:
                duplicate_idx = idx
            elif current_is_canonical == existing_is_canonical and _bounds_area(bounds) > _bounds_area(existing_bounds):
                duplicate_idx = idx
            else:
                duplicate_idx = -1
            break
        if duplicate_idx is None:
            deduped.append(action)
        elif duplicate_idx >= 0:
            deduped[duplicate_idx] = action
    return deduped


def _filtered_preview_actions(
    actions,
    *,
    rich_engineering=False,
    include_layers: Optional[set[str]] = None,
    allow_heuristics: bool = PREVIEW_ALLOW_HEURISTICS_DEFAULT,
    allow_synthesis: bool = PREVIEW_ALLOW_SYNTHESIS_DEFAULT,
    preview_mode: Optional[str] = None,
):
    engineering_profile = _normalize_engineering_profile(rich_engineering)
    include_layers = _normalize_include_layers(include_layers)
    preview_mode = _normalize_preview_mode(preview_mode)
    profile_layers = PROFILE_LAYER_VISIBILITY.get(engineering_profile, FINAL_GEOMETRY_LAYERS)
    records = [action for action in actions if isinstance(action, dict)]
    if allow_synthesis:
        records = _synthesize_layout_preview_actions(records)
    records = _dedupe_primary_layout_records(records)
    has_primary_site_geometry = _has_primary_site_geometry(records)
    has_layout_scene = _has_layout_scene(records)
    engineering_overlay_keys = {
        repr(action)
        for action in (
            _engineering_overlay_actions(
                records,
                engineering_profile=engineering_profile,
                allow_heuristics=allow_heuristics,
            )
            if has_layout_scene
            else []
        )
    }
    building_bounds = [
        {"action": action, "bounds": _action_bounds(action)}
        for action in records
        if (
            get_layer(action, "C-TEXT") == "C-BUILDING"
            and str(action.get("task") or "").lower() in {"rectangle", "polygon"}
        )
    ]
    building_bounds = [item for item in building_bounds if item["bounds"]]
    building_rects = [item["bounds"] for item in building_bounds]
    parking_bounds = [
        _action_bounds(action)
        for action in records
        if (get_layer(action, "C-TEXT") == "C-PARKING" and _action_bounds(action))
    ]
    layout_bounds = _merge_bounds(
        [
            _action_bounds(action)
            for action in records
            if get_layer(action, "C-TEXT") in {"C-BUILDING", "C-PARKING", "C-PAVEMENT", "C-SIDEWALK"}
        ]
    )
    grading_focus_bounds = _grading_focus_bounds_from_buildings(building_rects, layout_bounds)
    has_building_shapes = any(
        (
            get_layer(action, "C-TEXT") == "C-BUILDING"
            and str(action.get("task") or "").lower() in {"rectangle", "polygon"}
        )
        for action in records
    )
    filtered = []
    for action in records:
        layer = get_layer(action, "C-TEXT")
        raw_layer = get_raw_layer(action)
        label = clean_label(action.get("label"), "").upper()
        text = safe_text(action.get("text"), "").upper()
        task = str(action.get("task") or "").lower()
        canonical_source_type = str(action.get("canonical_source_type") or "").upper()
        helper_signature = " ".join(part for part in (label, text, canonical_source_type) if part)
        if preview_mode != "debug" and _is_helper_geometry(action):
            continue
        if preview_mode == "production" and not _is_final_geometry(action):
            continue
        if preview_mode == "production" and layer not in FINAL_GEOMETRY_LAYERS:
            continue
        if preview_mode in {"production", "engineering"} and layer not in profile_layers:
            continue
        if allow_heuristics:
            if has_primary_site_geometry and layer == "C-BOUNDARY":
                continue
            if has_layout_scene and _is_wrapper_layout_shape(action, building_bounds):
                continue
            if has_layout_scene and _is_schematic_access_shape(action, building_bounds):
                continue
            if has_layout_scene and raw_layer == "FIRE" and task == "rectangle" and not label:
                continue
            if has_layout_scene and layer == "C-SETBACK":
                continue
            if has_primary_site_geometry and raw_layer == "PAD" and "BUILDABLE_AREA" in label:
                continue
            if has_primary_site_geometry and raw_layer == "PAD" and task == "rectangle" and not label and not text:
                continue
            if has_building_shapes and layer == "C-BUILDING" and task == "text_note":
                continue
            if task == "text_note" and any(token in text for token in SUPPRESSED_LABEL_TOKENS):
                continue
            if layer == "C-UTIL" and any(token in helper_signature for token in ("SERVICE", "TIE", "GENERIC_UTILITY")):
                continue
            if has_layout_scene and raw_layer == "ROUTE":
                continue
            if has_layout_scene and _is_tiny_marker_circle(action):
                continue
            if engineering_profile == "layout" and layer == "C-POND":
                if not include_layers or layer not in include_layers:
                    continue
            if has_layout_scene and layer in SECONDARY_ENGINEERING_LAYERS and repr(action) not in engineering_overlay_keys:
                if not include_layers or layer not in include_layers:
                    continue
            if has_layout_scene and task == "point":
                if not include_layers or layer not in include_layers:
                    continue
            if has_layout_scene and layer == "C-BUILDING" and task == "text_note":
                continue
            if has_layout_scene and _is_isolated_pavement_shape(action, building_rects, parking_bounds):
                continue
        if preview_mode == "production" and layer in SECONDARY_ENGINEERING_LAYERS:
            if not include_layers or layer not in include_layers:
                continue
        if include_layers and layer not in include_layers:
            continue
        if engineering_profile in {"layout", "grading"} and layer in {"C-BUILDING", "C-PARKING", "C-PAVEMENT", "C-SIDEWALK"} and "_preview_profile" not in action:
            action = dict(action)
            action["_preview_profile"] = engineering_profile
        if (
            allow_heuristics
            and engineering_profile == "grading"
            and layer == "C-CONTOUR"
            and task == "polyline"
        ):
            action = _clip_grading_contour_action(action, grading_focus_bounds)
            if action is None:
                continue
            if "_preview_profile" not in action:
                action = dict(action)
            action["_preview_profile"] = engineering_profile
        elif allow_heuristics and engineering_profile == "grading" and layer == "C-SPOT-ELEV" and task == "text_note" and _layer_variant(action) == "FG":
            if "_preview_profile" not in action:
                action = dict(action)
            action["_preview_profile"] = engineering_profile
        filtered.append(action)
    return filtered


# ----------------------------------------
# Draw functions
# ----------------------------------------

def draw_rectangle(ax, action, *, render_labels: bool = True):
    x, y = safe_origin(action)
    w = safe_num(action.get("width"))
    h = safe_num(action.get("height"))
    label = clean_label(action.get("label"), "")

    if w <= 0 or h <= 0:
        return None

    layer = get_layer(action, "C-TEXT")
    style = _rectangle_visual_style(action, w, h)
    fill_alpha = style["fill_alpha"]
    facecolor = style["facecolor"]
    residential_court = style["residential_court"]
    retail_field = style["retail_field"]
    parking_area = style["parking_area"]
    edge_alpha = style["edge_alpha"]

    rect = Rectangle(
        (x, y),
        w,
        h,
        fill=fill_alpha > 0.0,
        facecolor=facecolor,
        alpha=fill_alpha if fill_alpha > 0.0 else 1.0,
        linewidth=get_linewidth(action) + style["linewidth_boost"],
        edgecolor=get_color(action),
        linestyle=get_linestyle(action),
    )
    rect.set_edgecolor(get_color(action))
    rect.set_alpha(fill_alpha if fill_alpha > 0.0 else 1.0)
    ax.add_patch(rect)
    if layer == "C-PARKING":
        rect.set_edgecolor((0.396, 0.455, 0.569, edge_alpha))

    if layer == "C-PARKING" and w >= 24 and h >= 10:
        stripe_spacing = style["stripe_spacing"]
        stripe_alpha = style["stripe_alpha"]
        stripe_gap = style["stripe_gap"] if style["stripe_gap"] is not None else 0.0
        stripe_x = x + stripe_spacing
        stripe_y1 = y + max(1.5, h * 0.12)
        stripe_y2 = y + h - max(1.5, h * 0.12)
        gap_x1 = x + (w - stripe_gap) / 2.0 if stripe_gap > 0.0 else None
        gap_x2 = gap_x1 + stripe_gap if gap_x1 is not None else None
        while stripe_alpha > 0.0 and stripe_x < x + w - stripe_spacing * 0.35:
            if gap_x1 is not None and gap_x1 <= stripe_x <= gap_x2:
                stripe_x += stripe_spacing
                continue
            ax.plot(
                [stripe_x, stripe_x],
                [stripe_y1, stripe_y2],
                linewidth=0.7,
                color="#ffffff",
                alpha=stripe_alpha,
            )
            stripe_x += stripe_spacing

    preview_text = preview_label(action)
    if render_labels and preview_text:
        ax.text(
            x + w / 2,
            y + h / 2,
            preview_text,
            ha="center",
            va="center",
            fontsize=9 if layer != "C-BUILDING" else 10,
            fontweight="semibold",
            color="#0f172a",
        )

    return x, y, x + w, y + h


def draw_polygon(ax, action, *, render_labels: bool = True):
    pts = safe_points(action)
    if len(pts) < 3:
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    xs_closed = xs + [pts[0][0]]
    ys_closed = ys + [pts[0][1]]

    ax.plot(
        xs_closed,
        ys_closed,
        linewidth=get_linewidth(action),
        color=get_color(action),
        linestyle=get_linestyle(action),
    )

    label = preview_label(action)
    if render_labels and label:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        ax.text(cx, cy, label, ha="center", va="center", fontsize=8, color=get_color(action))

    return min(xs_closed), min(ys_closed), max(xs_closed), max(ys_closed)


def draw_polyline(ax, action, *, render_labels: bool = True):
    pts = safe_points(action)
    if len(pts) < 2:
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    linewidth, color, linestyle, alpha = _polyline_style(action)

    ax.plot(
        xs,
        ys,
        linewidth=linewidth,
        color=color,
        linestyle=linestyle,
        alpha=alpha,
    )

    label = preview_label(action)
    if render_labels and label:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        ax.text(cx, cy, label, ha="center", va="center", fontsize=8, color=get_color(action))

    return min(xs), min(ys), max(xs), max(ys)


def draw_circle(ax, action, *, render_labels: bool = True):
    cx, cy = safe_center(action)
    r = safe_num(action.get("radius"))
    layer = get_layer(action, "C-TEXT")

    if r <= 0:
        return None

    if layer == "C-STRM-INLET":
        r = max(r, 2.5)

    circle = Circle(
        (cx, cy),
        r,
        fill=False,
        linewidth=get_linewidth(action),
        edgecolor=get_color(action),
        linestyle=get_linestyle(action),
    )
    ax.add_patch(circle)

    preview_text = preview_label(action)
    if render_labels and preview_text:
        ax.text(cx, cy, preview_text, ha="center", va="center", fontsize=8, color=get_color(action))

    return cx - r, cy - r, cx + r, cy + r


def draw_arc(ax, action, *, render_labels: bool = True):
    cx, cy = safe_center(action)
    r = safe_num(action.get("radius"))
    a1 = safe_num(action.get("start_angle"))
    a2 = safe_num(action.get("end_angle"))
    label = clean_label(action.get("label"), "")

    if r <= 0:
        return None

    arc = Arc(
        (cx, cy),
        2 * r,
        2 * r,
        angle=0,
        theta1=a1,
        theta2=a2,
        linewidth=get_linewidth(action),
        edgecolor=get_color(action),
        linestyle=get_linestyle(action),
    )
    ax.add_patch(arc)

    preview_text = preview_label(action)
    if render_labels and preview_text:
        ax.text(cx, cy, preview_text, ha="center", va="center", fontsize=8, color=get_color(action))

    return cx - r, cy - r, cx + r, cy + r


def draw_text(ax, action, *, render_labels: bool = True):
    x, y = safe_origin(action)
    txt = safe_text(action.get("text"), "")
    h = max(safe_num(action.get("text_height"), 1.0), 0.5)

    if not render_labels or not _should_draw_text_note(action):
        return None

    alpha, fontsize_adjust, bbox_alpha = _text_style(action)
    ax.text(
        x,
        y,
        txt,
        fontsize=max(4.0, min(5 + h + fontsize_adjust, 12)),
        color=get_color(action),
        alpha=alpha,
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "none", "alpha": bbox_alpha},
    )

    return x - 2, y - 2, x + 4, y + 2


def draw_point(ax, action, *, render_labels: bool = True):
    x, y = safe_origin(action)
    label = clean_label(action.get("label"), "")
    size = max(safe_num(action.get("radius"), 0.75), 0.25)

    ax.plot([x - size, x + size], [y, y], linewidth=get_linewidth(action), color=get_color(action))
    ax.plot([x, x], [y - size, y + size], linewidth=get_linewidth(action), color=get_color(action))

    preview_text = preview_label(action)
    if render_labels and preview_text:
        ax.text(
            x + size + 0.2,
            y + size + 0.2,
            preview_text,
            ha="left",
            va="bottom",
            fontsize=7,
            color=get_color(action),
        )

    return x - size, y - size, x + size, y + size


def draw_north_arrow(ax, action, *, render_labels: bool = True):
    x, y = safe_origin(action)

    ax.plot([x, x], [y, y + 8], linewidth=2)
    ax.plot([x, x - 1], [y + 8, y + 6.5], linewidth=2)
    ax.plot([x, x + 1], [y + 8, y + 6.5], linewidth=2)

    ax.text(x, y + 9, "N", ha="center", va="bottom", fontsize=12)

    return x - 2, y, x + 2, y + 10


# ----------------------------------------
# Main preview
# ----------------------------------------

def _expand_bounds(bounds, pad_ratio=0.08, min_pad=8.0):
    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    aspect = width / height if height > 0 else 1.0
    if aspect >= 1.8:
        pad_x = max(width * min(pad_ratio, 0.06), max(6.0, min_pad * 0.75))
        pad_y_top = max(height * min(pad_ratio * 0.25, 0.02), max(2.5, min_pad * 0.3))
        pad_y_bottom = max(height * min(pad_ratio * 0.7, 0.05), max(5.0, min_pad * 0.65))
    elif aspect >= 1.35:
        pad_x = max(width * min(pad_ratio, 0.07), max(7.0, min_pad * 0.85))
        pad_y_top = max(height * min(pad_ratio * 0.4, 0.032), max(3.0, min_pad * 0.4))
        pad_y_bottom = max(height * min(pad_ratio * 0.8, 0.06), max(5.0, min_pad * 0.7))
    else:
        pad_x = max(width * pad_ratio, min_pad)
        pad_y_top = max(height * pad_ratio * 0.75, min_pad * 0.75)
        pad_y_bottom = max(height * pad_ratio, min_pad)
    return min_x - pad_x, min_y - pad_y_bottom, max_x + pad_x, max_y + pad_y_top


def _update_bounds(current, bounds):
    if not bounds:
        return current
    if current is None:
        return bounds
    return (
        min(current[0], bounds[0]),
        min(current[1], bounds[1]),
        max(current[2], bounds[2]),
        max(current[3], bounds[3]),
    )


def _choose_view_bounds(drawn_items, *, engineering_profile="layout"):
    engineering_profile = _normalize_engineering_profile(engineering_profile)
    rich_engineering = engineering_profile != "layout"
    phase_focus_layers = PHASE_ENGINEERING_FOCUS_LAYERS.get(
        engineering_profile,
        PHASE_ENGINEERING_FOCUS_LAYERS["layout"],
    )
    all_bounds = None
    focus_bounds = None
    primary_bounds = None
    building_bounds = None
    walk_bounds = None
    pad_bounds = None
    parking_items = []
    engineering_bounds = None
    phase_engineering_bounds = None

    for layer, task, bounds in drawn_items:
        if not bounds:
            continue
        if task not in {"text_note", "point", "north_arrow"}:
            all_bounds = _update_bounds(all_bounds, bounds)
        if layer not in FOCUS_EXCLUDED_LAYERS:
            focus_bounds = _update_bounds(focus_bounds, bounds)
        if layer in PRIMARY_VIEW_LAYERS:
            primary_bounds = _update_bounds(primary_bounds, bounds)
        if layer == "C-BUILDING":
            building_bounds = _update_bounds(building_bounds, bounds)
        elif layer == "C-SIDEWALK":
            walk_bounds = _update_bounds(walk_bounds, bounds)
        elif layer == "C-BOUNDARY":
            pass
        elif layer == "C-PARKING":
            parking_items.append(bounds)
        elif layer in KEY_ENGINEERING_VIEW_LAYERS:
            engineering_bounds = _update_bounds(engineering_bounds, bounds)
        if layer in phase_focus_layers:
            phase_engineering_bounds = _update_bounds(phase_engineering_bounds, bounds)

    if all_bounds is None:
        return None

    clustered_primary_bounds = primary_bounds
    if building_bounds:
        clustered_primary_bounds = _merge_bounds([building_bounds, walk_bounds, pad_bounds]) or building_bounds
        for bounds in parking_items:
            merged_cluster = _merge_bounds([clustered_primary_bounds, bounds])
            if not merged_cluster:
                continue
            cluster_area = _bounds_area(clustered_primary_bounds)
            merged_area = _bounds_area(merged_cluster)
            if cluster_area <= 0:
                clustered_primary_bounds = merged_cluster
                continue
            width_gain = max(merged_cluster[2] - merged_cluster[0], 1.0) / max(clustered_primary_bounds[2] - clustered_primary_bounds[0], 1.0)
            height_gain = max(merged_cluster[3] - merged_cluster[1], 1.0) / max(clustered_primary_bounds[3] - clustered_primary_bounds[1], 1.0)
            if merged_area <= cluster_area * 1.6 and width_gain <= 1.18 and height_gain <= 1.45:
                clustered_primary_bounds = merged_cluster

    preferred_bounds = clustered_primary_bounds or primary_bounds or focus_bounds or all_bounds
    if primary_bounds and phase_engineering_bounds:
        preferred_bounds = (
            _merge_bounds([primary_bounds, phase_engineering_bounds]) or preferred_bounds
        )
    if rich_engineering and engineering_profile not in {"grading", "drainage"} and primary_bounds and engineering_bounds:
        merged_rich_bounds = _merge_bounds([primary_bounds, engineering_bounds])
        if merged_rich_bounds:
            current_area = _bounds_area(preferred_bounds)
            merged_area = _bounds_area(merged_rich_bounds)
            if current_area <= 0 or merged_area <= current_area * 1.75:
                preferred_bounds = merged_rich_bounds

    preferred_width = max(preferred_bounds[2] - preferred_bounds[0], 1.0)
    preferred_height = max(preferred_bounds[3] - preferred_bounds[1], 1.0)
    all_width = max(all_bounds[2] - all_bounds[0], 1.0)
    all_height = max(all_bounds[3] - all_bounds[1], 1.0)
    zoom_gain = max(all_width / preferred_width, all_height / preferred_height)

    # Favor the primary layout/engineering cluster once it yields a materially tighter frame.
    if engineering_profile in {"grading", "drainage"} and phase_engineering_bounds:
        return preferred_bounds
    if zoom_gain >= (1.15 if rich_engineering else 1.25):
        return preferred_bounds
    return focus_bounds or preferred_bounds or all_bounds


def _preview_draw_priority(action):
    layer = get_layer(action, "C-TEXT")
    task = str(action.get("task") or "").lower()
    if task in {"text_note", "point", "north_arrow"}:
        return 6
    if layer in {"C-STRM-INLET", "C-STRM-PIPE", "C-STRM-MH", "C-SAN", "C-UTIL", "C-WATR", "C-POND", "C-DRAIN-FLOW", "C-CONTOUR", "C-SPOT-ELEV", "C-GRADING"}:
        return 5
    if layer == "C-SIDEWALK":
        return 4
    if layer == "C-BUILDING":
        return 3
    if layer in {"BRIDGE", "POOL", "LOT"}:
        return 3
    if layer in {"C-PARKING", "C-PAVEMENT", "C-ROAD", "C-DRIVEWAY"}:
        return 2
    if layer in {"C-BOUNDARY", "C-SETBACK"}:
        return 1
    return 0


def _preview_engineering_profile(plan):
    meta = plan.get("meta") or {}
    phase_checkpoints = meta.get("phase_checkpoints") or {}
    combined_view = phase_checkpoints.get("combined_view") or {}
    completed_phases = safe_num(combined_view.get("completed_phase_count"))
    total_phases = safe_num(combined_view.get("total_phase_count"))
    engineering_status = safe_text(meta.get("engineering_status"), "").lower()
    release_status = safe_text(meta.get("release_status"), "").lower()
    runtime_checkpoint = meta.get("runtime_phase_checkpoint") or {}
    checkpoint_stage = safe_text(runtime_checkpoint.get("stage_name"), "").lower()
    grading_complete = bool((phase_checkpoints.get("grading") or {}).get("ready"))
    drainage_complete = bool((phase_checkpoints.get("drainage_storm") or {}).get("ready"))
    utilities_complete = bool((phase_checkpoints.get("utilities") or {}).get("ready"))
    coordination_complete = bool((phase_checkpoints.get("coordination_validation") or {}).get("ready"))
    engineering_profile = "layout"
    if (
        (total_phases > 0 and completed_phases >= total_phases)
        or release_status == "ready"
        or engineering_status in {"complete", "ready", "release_ready"}
        or coordination_complete
    ):
        engineering_profile = "complete"
    elif utilities_complete or checkpoint_stage in {"sanitary", "utility_network"}:
        engineering_profile = "utilities"
    elif checkpoint_stage == "storm_pipes":
        engineering_profile = "storm"
    elif drainage_complete or checkpoint_stage == "drainage":
        engineering_profile = "drainage"
    elif grading_complete or checkpoint_stage == "grading":
        engineering_profile = "grading"
    return engineering_profile


def _infer_profile_from_actions(actions, current_profile, *, allow_profile_inference: bool = False):
    if not allow_profile_inference or current_profile != "layout":
        return current_profile
    layers = {
        get_layer(action, "C-TEXT")
        for action in actions
        if isinstance(action, dict)
    }
    has_grading = bool(layers.intersection({"C-CONTOUR", "C-SPOT-ELEV", "C-DRAIN-FLOW"}))
    has_drainage = bool(layers.intersection({"C-STRM-PIPE", "C-STRM-INLET", "C-STRM-MH"}))
    has_utilities = bool(layers.intersection({"C-UTIL", "C-WATR", "C-SAN"}))
    active = sum((has_grading, has_drainage, has_utilities))
    if active >= 2:
        return "complete"
    if has_utilities:
        return "utilities"
    if has_drainage:
        return "drainage"
    if has_grading:
        return "grading"
    return current_profile


def _preview_scene(plan, *, include_layers: Optional[set[str]] = None, preview_mode: Optional[str] = None):
    preview_options = _preview_options(plan)
    resolved_preview_mode = _normalize_preview_mode(preview_mode or preview_options.get("preview_mode"))
    allow_heuristics = preview_options["allow_heuristics"]
    allow_synthesis = preview_options["allow_synthesis"]
    allow_profile_inference = preview_options["allow_profile_inference"]
    if resolved_preview_mode == "production":
        allow_heuristics = False
        allow_synthesis = False
        allow_profile_inference = False
    elif resolved_preview_mode == "engineering":
        allow_heuristics = True
        allow_synthesis = False
        allow_profile_inference = False
    elif resolved_preview_mode == "debug":
        allow_heuristics = True
        allow_synthesis = True
        allow_profile_inference = True

    engineering_profile = _preview_engineering_profile(plan)
    raw_actions = list(plan.get("actions", []) or [])
    engineering_profile = _infer_profile_from_actions(
        raw_actions,
        engineering_profile,
        allow_profile_inference=allow_profile_inference,
    )
    normalized_layers = _normalize_include_layers(include_layers)
    actions = _filtered_preview_actions(
        raw_actions,
        rich_engineering=engineering_profile,
        include_layers=normalized_layers,
        allow_heuristics=allow_heuristics,
        allow_synthesis=allow_synthesis,
        preview_mode=resolved_preview_mode,
    )
    if not actions:
        return engineering_profile, actions, None

    drawn_items = []
    for action in actions:
        bounds = _action_bounds(action)
        if bounds is None:
            continue
        layer = get_layer(action, "C-TEXT")
        drawn_items.append((layer, str(action.get("task") or "").lower(), bounds))

    selected_bounds = _choose_view_bounds(
        drawn_items,
        engineering_profile=engineering_profile,
    )
    return engineering_profile, actions, selected_bounds


def _preview_figure_size(selected_bounds, *, base=7.2):
    if not selected_bounds:
        return (base, base)
    min_x, min_y, max_x, max_y = selected_bounds
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    ratio = max(1.0, min(3.6, width / height))
    return (round(base * ratio, 3), base)


def _draw_plan(ax, plan, *, actions=None, selected_bounds=None, render_labels: bool = True):
    if actions is None or selected_bounds is None:
        _, actions, selected_bounds = _preview_scene(plan)
    if not actions or selected_bounds is None:
        return False

    for action in sorted(actions, key=_preview_draw_priority):
        task = action.get("task")

        if task == "rectangle":
            bounds = draw_rectangle(ax, action, render_labels=render_labels)
        elif task == "polygon":
            bounds = draw_polygon(ax, action, render_labels=render_labels)
        elif task == "polyline":
            bounds = draw_polyline(ax, action, render_labels=render_labels)
        elif task == "circle":
            bounds = draw_circle(ax, action, render_labels=render_labels)
        elif task == "arc":
            bounds = draw_arc(ax, action, render_labels=render_labels)
        elif task == "text_note":
            bounds = draw_text(ax, action, render_labels=render_labels)
        elif task == "point":
            bounds = draw_point(ax, action, render_labels=render_labels)
        elif task == "north_arrow":
            bounds = draw_north_arrow(ax, action, render_labels=render_labels)
        else:
            continue

        if bounds is None:
            continue

    min_x, min_y, max_x, max_y = _expand_bounds(selected_bounds)

    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)

    ax.set_aspect("equal")
    ax.set_facecolor("#f8fafc")
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    return True


def render_plan_preview_png(
    plan,
    *,
    figsize=(8, 8),
    dpi: int = 160,
    render_labels: bool = True,
    include_layers: Optional[set[str]] = None,
    preview_mode: Optional[str] = None,
) -> bytes:
    actions = [
        action
        for action in list(plan.get("actions") or [])
        if isinstance(action, dict)
    ]
    allowed = None
    if include_layers:
        allowed = _normalize_include_layers(include_layers) or set()
        always_allow = {"C-BOUNDARY", "C-TEXT", "C-DIMS", "C-LABEL"}
        actions = [
            action
            for action in actions
            if get_layer(action, "C-TEXT") in allowed
            or get_layer(action, "C-TEXT") in always_allow
            or not str(action.get("layer") or "").strip()
        ]
    _, preview_actions, selected_bounds = _preview_scene(
        {"actions": actions, **{k: v for k, v in plan.items() if k != "actions"}},
        include_layers=allowed if include_layers else None,
        preview_mode=preview_mode,
    )
    if len(actions) >= 60:
        figsize = _preview_figure_size(selected_bounds, base=7.2)
        dpi = min(dpi, 120)
    elif selected_bounds:
        figsize = _preview_figure_size(selected_bounds, base=min(figsize[1], 8.0))
    fig = Figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor("#f8fafc")
    FigureCanvasAgg(fig)
    ax = fig.subplots()

    if not _draw_plan(
        ax,
        plan,
        actions=preview_actions,
        selected_bounds=selected_bounds,
        render_labels=render_labels,
    ):
        raise ValueError("No drawable actions found in plan.")

    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    fig.clear()
    return buffer.getvalue()


def build_preview_annotations(plan, *, include_layers: Optional[set[str]] = None, preview_mode: Optional[str] = None) -> Dict[str, Any]:
    actions = [
        action
        for action in list(plan.get("actions") or [])
        if isinstance(action, dict)
    ]
    allowed = None
    if include_layers:
        allowed = _normalize_include_layers(include_layers) or set()
        actions = [
            action
            for action in actions
            if get_layer(action, "C-TEXT") in allowed or not str(action.get("layer") or "").strip()
        ]
    engineering_profile, preview_actions, selected_bounds = _preview_scene(
        {"actions": actions, **{k: v for k, v in plan.items() if k != "actions"}},
        include_layers=allowed if include_layers else None,
        preview_mode=preview_mode,
    )
    if not preview_actions or not selected_bounds:
        return {"profile": engineering_profile, "labels": []}
    min_x, min_y, max_x, max_y = selected_bounds
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    allowed_layers = {
        "C-BUILDING",
        "C-PARKING",
        "C-ROAD",
        "C-PAVEMENT",
        "C-SIDEWALK",
        "C-DRIVEWAY",
        "C-STRM-INLET",
        "C-STRM-PIPE",
        "C-STRM-MH",
        "C-SAN",
        "C-UTIL",
        "C-WATR",
        "C-POND",
        "BRIDGE",
        "POOL",
        "LOT",
    }
    labels: List[Dict[str, Any]] = []
    for action in preview_actions:
        layer = get_layer(action, "C-TEXT")
        if layer not in allowed_layers:
            continue
        label = preview_label(action)
        if not label:
            continue
        bounds = _action_bounds(action)
        if not bounds:
            continue
        cx = (bounds[0] + bounds[2]) / 2.0
        cy = (bounds[1] + bounds[3]) / 2.0
        labels.append(
            {
                "label": label,
                "layer": layer,
                "x": (cx - min_x) / span_x,
                "y": (cy - min_y) / span_y,
                "bounds": {
                    "x1": (bounds[0] - min_x) / span_x,
                    "y1": (bounds[1] - min_y) / span_y,
                    "x2": (bounds[2] - min_x) / span_x,
                    "y2": (bounds[3] - min_y) / span_y,
                },
            }
        )
    return {"profile": engineering_profile, "labels": labels}


def preview_plan(plan):
    actions = plan.get("actions", [])
    if not actions:
        print("No actions to preview.")
        return

    _, actions, selected_bounds = _preview_scene(plan)
    fig, ax = plt.subplots(figsize=_preview_figure_size(selected_bounds, base=8.0))

    if not _draw_plan(ax, plan, actions=actions, selected_bounds=selected_bounds):
        print("Nothing drawable found.")
        return

    plt.tight_layout()
    plt.show()
