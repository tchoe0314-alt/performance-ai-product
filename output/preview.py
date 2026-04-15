# output/preview.py

from __future__ import annotations

from io import BytesIO

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
SUPPRESSED_TEXT_LAYERS = {"EG_CONTOUR", "FG_CONTOUR", "DRAIN_FLOW", "LOW_POINTS", "UTILITY", "WATER"}
FOCUS_EXCLUDED_LAYERS = {"ANNO", "SYMBOL", "SITE", "PAD", "SETBACK", "UTILITY", "WATER", "DRAIN_FLOW", "EG_CONTOUR", "FG_CONTOUR", "SPOT_EG", "SPOT_FG", "LOW_POINTS"}
SUPPRESSED_LABEL_TOKENS = ("BUILDABLE_AREA", "GENERIC_UTILITY", "SERVICE_TIE", "SOURCE_SERVICE", "BUILDING_SERVICE", "UTILITY-")
PRIMARY_LAYOUT_LAYERS = {"BUILDING", "PAVEMENT", "PARKING", "WALK"}
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


def _is_tiny_marker_circle(action):
    task = str(action.get("task") or "").lower()
    layer = str(action.get("layer") or "").upper()
    radius = safe_num(action.get("radius"))
    if task != "circle" or radius <= 0.0:
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


def _engineering_overlay_actions(records):
    basin_candidates = []
    line_candidates = []
    structure_candidates = []
    utility_candidates = []
    layout_bounds = _merge_bounds(
        [
            _action_bounds(action)
            for action in records
            if str(action.get("layer") or "").upper() in {"BUILDING", "PARKING", "PAVEMENT", "WALK"}
        ]
    )
    layout_diag = 0.0 if not layout_bounds else ((layout_bounds[2] - layout_bounds[0]) ** 2 + (layout_bounds[3] - layout_bounds[1]) ** 2) ** 0.5

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
        if layer == "BASIN_BOUNDARY" and task in {"circle", "polygon", "rectangle", "polyline"}:
            if _is_oversized_for_layout(action):
                continue
            basin_candidates.append((_bounds_area(bounds), action))
        elif layer in {"PIPE", "STORM", "DRAIN"} and task in {"polyline", "polygon"}:
            if _is_oversized_for_layout(action):
                continue
            points = safe_points(action)
            if points:
                points_in_layout = sum(
                    1 for point in points if _point_within_layout(point, layout_bounds, padding=12.0)
                )
                if points_in_layout <= 1 and len(points) >= 2:
                    continue
            line_candidates.append((_polyline_length(action), action))
        elif layer == "STRUCTURE" and task in {"circle", "rectangle"}:
            if _is_tiny_marker_circle(action):
                continue
            structure_candidates.append((_bounds_area(bounds), action))
        elif layer in {"UTILITY", "WATER"} and task in {"polyline", "polygon"}:
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
            utility_candidates.append((_polyline_length(action), action))

    selected = []
    seen = set()

    for _, action in sorted(basin_candidates, key=lambda item: item[0], reverse=True)[:1]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(line_candidates, key=lambda item: item[0], reverse=True)[:2]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(structure_candidates, key=lambda item: item[0], reverse=True)[:4]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    for _, action in sorted(utility_candidates, key=lambda item: item[0], reverse=True)[:1]:
        key = repr(action)
        if key not in seen:
            seen.add(key)
            selected.append(action)

    return selected


def _filtered_preview_actions(actions):
    records = [action for action in actions if isinstance(action, dict)]
    records = _synthesize_layout_preview_actions(records)
    has_primary_site_geometry = _has_primary_site_geometry(records)
    has_layout_scene = _has_layout_scene(records)
    engineering_overlay_keys = {
        repr(action)
        for action in (_engineering_overlay_actions(records) if has_layout_scene else [])
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
        fill_alpha = 0.14
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
        stripe_spacing = max(16.0, min(22.0, w / 6.0))
        stripe_x = x + stripe_spacing
        stripe_y1 = y + max(1.5, h * 0.12)
        stripe_y2 = y + h - max(1.5, h * 0.12)
        while stripe_x < x + w - stripe_spacing * 0.35:
            ax.plot(
                [stripe_x, stripe_x],
                [stripe_y1, stripe_y2],
                linewidth=0.8,
                color="#ffffff",
                alpha=0.65,
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
    label = clean_label(action.get("label"), "")

    if r <= 0:
        return None

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


def _draw_plan(ax, plan):
    actions = _filtered_preview_actions(plan.get("actions", []))
    if not actions:
        return False

    all_min_x, all_min_y = float("inf"), float("inf")
    all_max_x, all_max_y = float("-inf"), float("-inf")
    focus_min_x, focus_min_y = float("inf"), float("inf")
    focus_max_x, focus_max_y = float("-inf"), float("-inf")

    for action in actions:
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

        x1, y1, x2, y2 = bounds

        all_min_x = min(all_min_x, x1)
        all_min_y = min(all_min_y, y1)
        all_max_x = max(all_max_x, x2)
        all_max_y = max(all_max_y, y2)

        layer = (action.get("layer") or "").upper()
        if layer not in FOCUS_EXCLUDED_LAYERS:
            focus_min_x = min(focus_min_x, x1)
            focus_min_y = min(focus_min_y, y1)
            focus_max_x = max(focus_max_x, x2)
            focus_max_y = max(focus_max_y, y2)

    if all_min_x == float("inf"):
        return False

    all_bounds = (all_min_x, all_min_y, all_max_x, all_max_y)
    focus_available = focus_min_x != float("inf")
    selected_bounds = all_bounds
    if focus_available:
        all_width = max(all_max_x - all_min_x, 1.0)
        all_height = max(all_max_y - all_min_y, 1.0)
        focus_width = max(focus_max_x - focus_min_x, 1.0)
        focus_height = max(focus_max_y - focus_min_y, 1.0)
        if all_width / focus_width > 2.5 or all_height / focus_height > 2.5:
            selected_bounds = (focus_min_x, focus_min_y, focus_max_x, focus_max_y)

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
    if len(actions) >= 60:
        figsize = (7.2, 7.2)
        dpi = min(dpi, 120)
    fig = Figure(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor("#f8fafc")
    FigureCanvasAgg(fig)
    ax = fig.subplots()

    if not _draw_plan(ax, plan):
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

    fig, ax = plt.subplots(figsize=(8, 8))

    if not _draw_plan(ax, plan):
        print("Nothing drawable found.")
        return

    plt.tight_layout()
    plt.show()
