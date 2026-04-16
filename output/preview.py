# output/preview.py

from __future__ import annotations

from io import BytesIO
import re

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle, Arc

from core.utils import (
    clean_label,
    safe_center,
    safe_num,
    safe_origin,
    safe_points,
    safe_text,
)


# ----------------------------------------
# Styling helpers (matches DXF intent)
# ----------------------------------------

LAYER_LINEWIDTH = {
    "BUILDING": 2.5,
    "PAD": 1.4,
    "PAVEMENT": 2.0,
    "ROAD": 2.0,
    "PARKING": 1.0,
    "WALK": 1.2,
    "FIRE": 1.4,
    "SITE": 1.2,
    "SETBACK": 1.0,
    "PIPE": 2.0,
    "DRAIN": 2.0,
    "DRAIN_FLOW": 1.5,
    "SURFACE": 1.0,
    "EG_CONTOUR": 1.0,
    "FG_CONTOUR": 1.2,
    "BASIN_BOUNDARY": 1.8,
    "UTILITY": 1.8,
    "WATER": 1.8,
    "SAN": 1.8,
    "STORM": 2.0,
    "STRUCTURE": 1.6,
    "DEFAULT": 2.0,
}

LAYER_COLORS = {
    "BUILDING": "#0f172a",
    "PAD": "#94a3b8",
    "PAVEMENT": "#64748b",
    "ROAD": "#475569",
    "PARKING": "#cbd5e1",
    "WALK": "#0f766e",
    "FIRE": "#dc2626",
    "SITE": "#94a3b8",
    "SETBACK": "#d1d5db",
    "PIPE": "#1d4ed8",
    "DRAIN": "#0f766e",
    "STORM": "#0369a1",
    "SAN": "#7c3aed",
    "UTILITY": "#6d28d9",
    "WATER": "#0ea5e9",
    "DRAIN_FLOW": "#0f766e",
    "SURFACE": "#94a3b8",
    "EG_CONTOUR": "#cbd5e1",
    "FG_CONTOUR": "#f59e0b",
    "BASIN_BOUNDARY": "#15803d",
    "STRUCTURE": "#dc2626",
    "DEFAULT": "#334155",
}

LAYER_LINESTYLE = {
    "PAD": (0, (6, 4)),
    "SETBACK": (0, (8, 4)),
    "EG_CONTOUR": "--",
    "FG_CONTOUR": "-.",
    "DRAIN_FLOW": (0, (4, 4)),
    "SURFACE": (0, (2, 4)),
}

SUPPRESSED_AUTO_LABEL_LAYERS = {
    "PAD",
    "SITE",
    "SETBACK",
    "PARKING",
    "WALK",
    "FIRE",
    "PIPE",
    "DRAIN",
    "SAN",
    "EG_CONTOUR",
    "FG_CONTOUR",
    "DRAIN_FLOW",
    "BASIN_BOUNDARY",
    "STRUCTURE",
    "UTILITY",
    "WATER",
    "STORM",
}
SUPPRESSED_TEXT_LAYERS = {"DRAIN_FLOW", "LOW_POINTS", "UTILITY", "WATER"}
FOCUS_EXCLUDED_LAYERS = {"ANNO", "SYMBOL", "SITE", "PAD", "SETBACK", "UTILITY", "WATER", "DRAIN_FLOW", "EG_CONTOUR", "FG_CONTOUR", "LOW_POINTS"}
SUPPRESSED_LABEL_TOKENS = (
    "AISLE-",
    "BUILDABLE_AREA",
    "GENERIC_UTILITY",
    "SERVICE_TIE",
    "SOURCE_SERVICE",
    "BUILDING_SERVICE",
    "UTILITY-",
)
PRIMARY_LAYOUT_LAYERS = {"BUILDING", "PAVEMENT", "PARKING", "WALK"}
PRIMARY_VIEW_LAYERS = {"BUILDING", "PAVEMENT", "PARKING", "WALK", "PAD"}
KEY_ENGINEERING_VIEW_LAYERS = {"BASIN_BOUNDARY", "DRAIN", "PIPE", "STORM", "SAN", "UTILITY", "WATER", "STRUCTURE"}
SECONDARY_ENGINEERING_LAYERS = {
    "ANNO",
    "BASIN_BOUNDARY",
    "DRAIN",
    "PIPE",
    "STORM",
    "SAN",
    "UTILITY",
    "WATER",
    "STRUCTURE",
    "DRAIN_FLOW",
    "EG_CONTOUR",
    "FG_CONTOUR",
    "SPOT_EG",
    "SPOT_FG",
    "LOW_POINTS",
    "PAD",
    "SURFACE",
    "ROUTE",
}

PHASE_ENGINEERING_FOCUS_LAYERS = {
    "layout": set(),
    "grading": {"FG_CONTOUR", "EG_CONTOUR", "SPOT_FG", "SPOT_EG", "PAD"},
    "drainage": {"DRAIN", "DRAIN_FLOW", "STRUCTURE"},
    "storm": {"DRAIN", "PIPE", "STORM", "BASIN_BOUNDARY", "STRUCTURE", "DRAIN_FLOW"},
    "utilities": {"DRAIN", "PIPE", "STORM", "SAN", "UTILITY", "WATER", "BASIN_BOUNDARY", "STRUCTURE", "DRAIN_FLOW"},
    "complete": {"DRAIN", "PIPE", "STORM", "SAN", "UTILITY", "WATER", "BASIN_BOUNDARY", "STRUCTURE", "DRAIN_FLOW", "FG_CONTOUR", "SPOT_FG"},
    "baseline": {"DRAIN", "PIPE", "STORM", "SAN", "UTILITY", "WATER", "BASIN_BOUNDARY", "STRUCTURE"},
}


def _normalize_engineering_profile(profile):
    if profile is True:
        return "complete"
    if profile is False:
        return "baseline"
    if profile in (None, ""):
        return "layout"
    normalized = str(profile).strip().lower()
    return normalized or "layout"


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
    layer = (action.get("layer") or "").upper()
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
    layer = (action.get("layer") or "").upper()
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
    layer = (action.get("layer") or "").upper()
    return LAYER_LINEWIDTH.get(layer, LAYER_LINEWIDTH["DEFAULT"])


def get_color(action):
    layer = (action.get("layer") or "").upper()
    return LAYER_COLORS.get(layer, LAYER_COLORS["DEFAULT"])


def get_linestyle(action):
    layer = (action.get("layer") or "").upper()
    return LAYER_LINESTYLE.get(layer, "-")


_GENERIC_BUILDING_LABEL_RE = re.compile(r"^(?:BLDG|BUILDING)\s*-?\s*\d+[A-Z]?$")
_GENERIC_SURFACE_LABEL_RE = re.compile(r"^(?:LOT\s+[A-Z0-9]+|PARK(?:ING)?(?:\s+LOT)?\s*-?\s*[A-Z0-9]*|LOT\s+BASE)$")


def _is_generic_default_label(layer: str, label: str) -> bool:
    upper = label.upper().strip()
    if layer == "BUILDING" and _GENERIC_BUILDING_LABEL_RE.fullmatch(upper):
        return True
    if layer in {"ROAD", "FIRE", "PAVEMENT"} and upper in {
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
    if layer in {"PARKING", "PAVEMENT"} and _GENERIC_SURFACE_LABEL_RE.fullmatch(upper):
        return True
    return False


def preview_label(action):
    layer = (action.get("layer") or "").upper()
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
    layer = (action.get("layer") or "").upper()
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
        layer = (action.get("layer") or "").upper()
        task = str(action.get("task") or "").lower()
        if layer in {"BUILDING", "PAVEMENT", "PARKING", "WALK"} and task in {"rectangle", "polygon", "polyline"}:
            return True
    return False


def _has_layout_scene(actions):
    for action in actions:
        layer = (action.get("layer") or "").upper()
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
    layer = str(action.get("layer") or "").upper()
    radius = safe_num(action.get("radius"))
    if task != "circle" or radius <= 0.0:
        return False
    if layer == "DRAIN":
        return False
    return layer in SECONDARY_ENGINEERING_LAYERS and radius <= 1.5


def _is_isolated_pavement_shape(action, building_bounds, parking_bounds):
    layer = str(action.get("layer") or "").upper()
    task = str(action.get("task") or "").lower()
    if layer != "PAVEMENT" or task not in {"rectangle", "polygon"}:
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
                "layer": "PAVEMENT",
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
        layer = str(action.get("layer") or "").upper()
        bounds = _action_bounds(action)
        if layer == "BUILDING" and bounds:
            building_rects.append(bounds)

    records = []
    for action in raw_records:
        rec = dict(action)
        layer = str(rec.get("layer") or "").upper()
        task = str(rec.get("task") or "").lower()
        label = clean_label(rec.get("label"), "").upper()
        if layer in {"ROAD", "FIRE"}:
            if task in {"circle", "polyline"}:
                if not label or label in {"ROAD", "DRIVE", "FIRE", "FIRE-1", "ROAD-1"}:
                    continue
            if task in {"rectangle", "polygon"} and (not label or label in {"ROAD", "DRIVE", "FIRE", "FIRE-1", "ROAD-1"}):
                rec["layer"] = "PAVEMENT"
                rec["semantic_surface_role"] = "circulation"
                layer = "PAVEMENT"
        bounds = _action_bounds(rec)
        if layer == "PAVEMENT" and bounds:
            pavement_rects.append((bounds, rec))
        elif layer == "PARKING":
            has_parking = True
        elif layer == "WALK":
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
                out["layer"] = "PARKING"
                key = repr(out)
                if key not in seen:
                    seen.add(key)
                    synthesized.append(out)

    parking_rects = [_action_bounds(action) for action in synthesized if str(action.get("layer") or "").upper() == "PARKING" and _action_bounds(action)]
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
                "layer": "WALK",
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


def _engineering_overlay_actions(records, *, engineering_profile="layout"):
    engineering_profile = _normalize_engineering_profile(engineering_profile)
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
        "grading": {"line": 0, "flow": 0, "drain_label": 0, "contour": 8, "contour_label": 6, "spot": 12, "structure": 0, "utility": 0, "basin": 0},
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
            if str(action.get("layer") or "").upper() in {"BUILDING", "PARKING", "PAVEMENT", "WALK"}
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
        layer = str(action.get("layer") or "").upper()
        task = str(action.get("task") or "").lower()
        bounds = _action_bounds(action)
        if not bounds:
            continue
        if allow_basin and layer == "BASIN_BOUNDARY" and task in {"circle", "polygon", "rectangle", "polyline"}:
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
                    (layer in {"PIPE", "STORM"} and allow_pipe)
                    or (layer == "DRAIN" and allow_drain)
                )
            )
            or (allow_drain and layer == "DRAIN" and task in {"circle", "rectangle"})
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
            phase_far = engineering_profile in {"storm", "utilities", "complete"} and layer in {"PIPE", "STORM"}
            score = _engineering_score(
                bounds,
                line_score / max(layout_span, 1.0),
                favor_far=phase_far,
                near_bonus=min(points_in_layout, 6) * 0.2,
            )
            line_candidates.append((score, action))
        elif allow_flow and layer == "DRAIN_FLOW" and task in {"polyline", "polygon"}:
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
        elif allow_drain and layer == "DRAIN" and task == "text_note":
            if not _bounds_near_layout(bounds, layout_bounds, padding=96.0):
                continue
            label_score = _engineering_score(bounds, 1.0)
            drain_label_candidates.append((label_score, action))
        elif allow_contours and layer in {"EG_CONTOUR", "FG_CONTOUR"} and task in {"polyline", "polygon"}:
            if engineering_profile in {"storm", "utilities", "complete"} and layer == "EG_CONTOUR":
                continue
            if engineering_profile == "grading":
                if not _bounds_near_layout(bounds, layout_bounds, padding=112.0):
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
            if engineering_profile in {"storm", "utilities", "complete"}:
                contour_bias = 0.35 if layer == "FG_CONTOUR" else -0.4
            contour_score = _engineering_score(
                bounds,
                contour_length / max(layout_span, 1.0) + contour_bias,
            )
            contour_candidates.append((contour_score, action))
        elif allow_contour_labels and layer in {"EG_CONTOUR", "FG_CONTOUR"} and task == "text_note":
            if engineering_profile == "complete" and layer == "EG_CONTOUR":
                continue
            padding = 132.0 if engineering_profile == "grading" else 140.0
            if not _bounds_near_layout(bounds, layout_bounds, padding=padding):
                if engineering_profile != "grading" or not layout_bounds:
                    continue
                x1, y1, x2, y2 = bounds
                lx1, ly1, lx2, ly2 = layout_bounds
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                horizontal_band = ly1 - 72.0 <= cy <= ly2 + 72.0
                vertical_band = lx1 - 72.0 <= cx <= lx2 + 72.0
                if not (horizontal_band or vertical_band):
                    continue
            label_bias = 0.0
            if engineering_profile == "complete":
                label_bias = 0.35 if layer == "FG_CONTOUR" else -0.4
            score = _engineering_score(bounds, 1.0 + label_bias)
            contour_label_candidates.append((score, action))
        elif allow_spot_grades and layer in {"SPOT_EG", "SPOT_FG"} and task in {"text_note", "point"}:
            if engineering_profile == "complete" and layer == "SPOT_EG":
                continue
            spot_padding = 48.0 if engineering_profile == "grading" else 36.0
            if not _bounds_near_layout(bounds, layout_bounds, padding=spot_padding):
                continue
            x1, y1, x2, y2 = bounds
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            if layout_bounds and not _point_within_layout((cx, cy), layout_bounds, padding=18.0):
                continue
            spot_bias = 0.0
            if engineering_profile == "complete":
                spot_bias = 0.35 if layer == "SPOT_FG" else -0.4
            score = _engineering_score(bounds, 1.0 + spot_bias)
            if task == "text_note":
                score += max(1.0, len(safe_text(action.get("text"), "").strip())) * 0.02
            spot_grade_candidates.append((score, action))
        elif (allow_drain or allow_pipe) and layer == "STRUCTURE" and task in {"circle", "rectangle"}:
            if _is_tiny_marker_circle(action):
                continue
            structure_score = _engineering_score(
                bounds,
                (_bounds_area(bounds) ** 0.5) / max(layout_span, 1.0),
            )
            structure_candidates.append((structure_score, action))
        elif rich_engineering and layer in {"UTILITY", "WATER"} and task in {"polyline", "polygon"}:
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

    for _, action in sorted(contour_label_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("contour_label", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(spot_grade_candidates, key=lambda item: item[0], reverse=True)[: int(overlay_limits.get("spot", 0))]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

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
    primary_layers = {"BUILDING", "PARKING", "PAVEMENT", "WALK"}
    for action in records:
        layer = str(action.get("layer") or "").upper()
        task = str(action.get("task") or "").lower()
        if layer not in primary_layers or task not in {"rectangle", "polygon"}:
            deduped.append(action)
            continue
        bounds = _action_bounds(action)
        if not bounds:
            deduped.append(action)
            continue
        label = clean_label(action.get("label"), "").upper()
        duplicate_idx = None
        for idx, existing in enumerate(deduped):
            existing_layer = str(existing.get("layer") or "").upper()
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


def _filtered_preview_actions(actions, *, rich_engineering=False):
    engineering_profile = _normalize_engineering_profile(rich_engineering)
    records = [action for action in actions if isinstance(action, dict)]
    records = _synthesize_layout_preview_actions(records)
    records = _dedupe_primary_layout_records(records)
    has_primary_site_geometry = _has_primary_site_geometry(records)
    has_layout_scene = _has_layout_scene(records)
    engineering_overlay_keys = {
        repr(action)
        for action in (_engineering_overlay_actions(records, engineering_profile=engineering_profile) if has_layout_scene else [])
    }
    building_bounds = [
        {"action": action, "bounds": _action_bounds(action)}
        for action in records
        if (str(action.get("layer") or "").upper() == "BUILDING" and str(action.get("task") or "").lower() in {"rectangle", "polygon"})
    ]
    building_bounds = [item for item in building_bounds if item["bounds"]]
    building_rects = [item["bounds"] for item in building_bounds]
    parking_bounds = [
        _action_bounds(action)
        for action in records
        if (str(action.get("layer") or "").upper() == "PARKING" and _action_bounds(action))
    ]
    has_building_shapes = any(
        (str(action.get("layer") or "").upper() == "BUILDING" and str(action.get("task") or "").lower() in {"rectangle", "polygon"})
        for action in records
    )
    filtered = []
    for action in records:
        layer = (action.get("layer") or "").upper()
        label = clean_label(action.get("label"), "").upper()
        text = safe_text(action.get("text"), "").upper()
        task = str(action.get("task") or "").lower()
        canonical_source_type = str(action.get("canonical_source_type") or "").upper()
        helper_signature = " ".join(part for part in (label, text, canonical_source_type) if part)
        if has_primary_site_geometry and layer == "SITE":
            continue
        if has_layout_scene and _is_wrapper_layout_shape(action, building_bounds):
            continue
        if has_layout_scene and _is_schematic_access_shape(action, building_bounds):
            continue
        if has_layout_scene and layer == "FIRE" and task == "rectangle" and not label:
            continue
        if has_layout_scene and layer == "SETBACK":
            continue
        if has_primary_site_geometry and layer == "PAD" and "BUILDABLE_AREA" in label:
            continue
        if has_primary_site_geometry and layer == "PAD" and task == "rectangle" and not label and not text:
            continue
        if has_building_shapes and layer == "BUILDING" and task == "text_note":
            continue
        if task == "text_note" and any(token in text for token in SUPPRESSED_LABEL_TOKENS):
            continue
        if layer == "UTILITY" and any(token in helper_signature for token in ("SERVICE", "TIE", "GENERIC_UTILITY")):
            continue
        if has_layout_scene and layer == "ROUTE":
            continue
        if has_layout_scene and _is_tiny_marker_circle(action):
            continue
        if has_layout_scene and layer in SECONDARY_ENGINEERING_LAYERS and repr(action) not in engineering_overlay_keys:
            continue
        if has_layout_scene and task == "point":
            continue
        if has_layout_scene and layer == "BUILDING" and task == "text_note":
            continue
        if has_layout_scene and _is_isolated_pavement_shape(action, building_rects, parking_bounds):
            continue
        filtered.append(action)
    return filtered


# ----------------------------------------
# Draw functions
# ----------------------------------------

def draw_rectangle(ax, action):
    x, y = safe_origin(action)
    w = safe_num(action.get("width"))
    h = safe_num(action.get("height"))
    label = clean_label(action.get("label"), "")

    if w <= 0 or h <= 0:
        return None

    layer = (action.get("layer") or "").upper()
    fill_alpha = 0.0
    facecolor = "none"
    if layer == "BUILDING":
        fill_alpha = 0.08
        facecolor = get_color(action)
    elif layer == "ROAD":
        fill_alpha = 0.06
        facecolor = get_color(action)
    elif layer == "PAVEMENT":
        fill_alpha = 0.10
        facecolor = get_color(action)
    elif layer == "PARKING":
        fill_alpha = 0.08
        facecolor = get_color(action)
    elif layer == "WALK":
        fill_alpha = 0.10
        facecolor = get_color(action)
    elif layer == "FIRE":
        fill_alpha = 0.0
        facecolor = "none"

    rect = Rectangle(
        (x, y),
        w,
        h,
        fill=fill_alpha > 0.0,
        facecolor=facecolor,
        alpha=fill_alpha if fill_alpha > 0.0 else 1.0,
        linewidth=get_linewidth(action),
        edgecolor=get_color(action),
        linestyle=get_linestyle(action),
    )
    ax.add_patch(rect)

    if layer == "PARKING" and w >= 24 and h >= 10:
        if w >= 220.0:
            stripe_spacing = max(28.0, min(36.0, w / 8.0))
            stripe_alpha = 0.16
            stripe_gap = max(52.0, min(104.0, w * 0.24))
        else:
            stripe_spacing = max(18.0, min(24.0, w / 5.0))
            stripe_alpha = 0.38
            stripe_gap = 0.0
        stripe_x = x + stripe_spacing
        stripe_y1 = y + max(1.5, h * 0.12)
        stripe_y2 = y + h - max(1.5, h * 0.12)
        gap_x1 = x + (w - stripe_gap) / 2.0 if stripe_gap > 0.0 else None
        gap_x2 = gap_x1 + stripe_gap if gap_x1 is not None else None
        while stripe_x < x + w - stripe_spacing * 0.35:
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
    if preview_text:
        ax.text(
            x + w / 2,
            y + h / 2,
            preview_text,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="semibold",
            color="#0f172a",
        )

    return x, y, x + w, y + h


def draw_polygon(ax, action):
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
    if label:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        ax.text(cx, cy, label, ha="center", va="center", fontsize=8, color=get_color(action))

    return min(xs_closed), min(ys_closed), max(xs_closed), max(ys_closed)


def draw_polyline(ax, action):
    pts = safe_points(action)
    if len(pts) < 2:
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    ax.plot(
        xs,
        ys,
        linewidth=get_linewidth(action),
        color=get_color(action),
        linestyle=get_linestyle(action),
    )

    label = preview_label(action)
    if label:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        ax.text(cx, cy, label, ha="center", va="center", fontsize=8, color=get_color(action))

    return min(xs), min(ys), max(xs), max(ys)


def draw_circle(ax, action):
    cx, cy = safe_center(action)
    r = safe_num(action.get("radius"))
    layer = (action.get("layer") or "").upper()

    if r <= 0:
        return None

    if layer == "DRAIN":
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
    if preview_text:
        ax.text(cx, cy, preview_text, ha="center", va="center", fontsize=8, color=get_color(action))

    return cx - r, cy - r, cx + r, cy + r


def draw_arc(ax, action):
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
    if preview_text:
        ax.text(cx, cy, preview_text, ha="center", va="center", fontsize=8, color=get_color(action))

    return cx - r, cy - r, cx + r, cy + r


def draw_text(ax, action):
    x, y = safe_origin(action)
    txt = safe_text(action.get("text"), "")
    h = max(safe_num(action.get("text_height"), 1.0), 0.5)

    if not _should_draw_text_note(action):
        return None

    ax.text(
        x,
        y,
        txt,
        fontsize=min(5 + h, 12),
        color=get_color(action),
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "none", "alpha": 0.8},
    )

    return x - 2, y - 2, x + 4, y + 2


def draw_point(ax, action):
    x, y = safe_origin(action)
    label = clean_label(action.get("label"), "")
    size = max(safe_num(action.get("radius"), 0.75), 0.25)

    ax.plot([x - size, x + size], [y, y], linewidth=get_linewidth(action), color=get_color(action))
    ax.plot([x, x], [y - size, y + size], linewidth=get_linewidth(action), color=get_color(action))

    preview_text = preview_label(action)
    if preview_text:
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


def draw_north_arrow(ax, action):
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
    pad_x = max(width * pad_ratio, min_pad)
    pad_y = max(height * pad_ratio, min_pad)
    return min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y


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
        if layer == "BUILDING":
            building_bounds = _update_bounds(building_bounds, bounds)
        elif layer == "WALK":
            walk_bounds = _update_bounds(walk_bounds, bounds)
        elif layer == "PAD":
            pad_bounds = _update_bounds(pad_bounds, bounds)
        elif layer == "PARKING":
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
    layer = (action.get("layer") or "").upper()
    task = str(action.get("task") or "").lower()
    if task in {"text_note", "point", "north_arrow"}:
        return 6
    if layer in {"DRAIN", "PIPE", "STORM", "SAN", "STRUCTURE", "UTILITY", "WATER", "BASIN_BOUNDARY", "DRAIN_FLOW", "EG_CONTOUR", "FG_CONTOUR"}:
        return 5
    if layer == "WALK":
        return 4
    if layer == "BUILDING":
        return 3
    if layer in {"PARKING", "PAVEMENT", "FIRE", "ROAD"}:
        return 2
    if layer in {"PAD", "SETBACK"}:
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


def _preview_scene(plan):
    engineering_profile = _preview_engineering_profile(plan)
    actions = _filtered_preview_actions(plan.get("actions", []), rich_engineering=engineering_profile)
    if not actions:
        return engineering_profile, actions, None

    drawn_items = []
    for action in actions:
        bounds = _action_bounds(action)
        if bounds is None:
            continue
        layer = (action.get("layer") or "").upper()
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
    ratio = max(1.0, min(2.6, width / height))
    return (round(base * ratio, 3), base)


def _draw_plan(ax, plan, *, actions=None, selected_bounds=None):
    if actions is None or selected_bounds is None:
        _, actions, selected_bounds = _preview_scene(plan)
    if not actions or selected_bounds is None:
        return False

    for action in sorted(actions, key=_preview_draw_priority):
        task = action.get("task")

        if task == "rectangle":
            bounds = draw_rectangle(ax, action)
        elif task == "polygon":
            bounds = draw_polygon(ax, action)
        elif task == "polyline":
            bounds = draw_polyline(ax, action)
        elif task == "circle":
            bounds = draw_circle(ax, action)
        elif task == "arc":
            bounds = draw_arc(ax, action)
        elif task == "text_note":
            bounds = draw_text(ax, action)
        elif task == "point":
            bounds = draw_point(ax, action)
        elif task == "north_arrow":
            bounds = draw_north_arrow(ax, action)
        else:
            continue

        if bounds is None:
            continue

        layer = (action.get("layer") or "").upper()
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

    ax.set_title(
        plan.get("project_name", "Plan Preview"),
        fontsize=13,
        fontweight="semibold",
        color="#0f172a",
        pad=12,
    )
    return True


def render_plan_preview_png(plan, *, figsize=(8, 8), dpi: int = 160) -> bytes:
    actions = [
        action
        for action in list(plan.get("actions") or [])
        if isinstance(action, dict)
    ]
    _, preview_actions, selected_bounds = _preview_scene({"actions": actions, **{k: v for k, v in plan.items() if k != "actions"}})
    if len(actions) >= 60:
        figsize = _preview_figure_size(selected_bounds, base=7.2)
        dpi = min(dpi, 120)
    elif selected_bounds:
        figsize = _preview_figure_size(selected_bounds, base=min(figsize[1], 8.0))
    fig = Figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor("#f8fafc")
    FigureCanvasAgg(fig)
    ax = fig.subplots()

    if not _draw_plan(ax, plan, actions=preview_actions, selected_bounds=selected_bounds):
        raise ValueError("No drawable actions found in plan.")

    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    fig.clear()
    return buffer.getvalue()


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
