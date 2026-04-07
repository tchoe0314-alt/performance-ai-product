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
    "DRAIN_FLOW": 1.5,
    "SURFACE": 1.0,
    "EG_CONTOUR": 1.0,
    "FG_CONTOUR": 1.2,
    "BASIN_BOUNDARY": 1.8,
    "UTILITY": 1.8,
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
    "STORM": "#0369a1",
    "SAN": "#7c3aed",
    "UTILITY": "#6d28d9",
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
    "SAN",
    "EG_CONTOUR",
    "FG_CONTOUR",
    "DRAIN_FLOW",
    "BASIN_BOUNDARY",
    "STRUCTURE",
    "UTILITY",
    "STORM",
}
SUPPRESSED_TEXT_LAYERS = {"EG_CONTOUR", "FG_CONTOUR", "DRAIN_FLOW", "LOW_POINTS", "UTILITY"}
FOCUS_EXCLUDED_LAYERS = {"ANNO", "SYMBOL", "SITE", "PAD", "SETBACK", "UTILITY", "DRAIN_FLOW", "EG_CONTOUR", "FG_CONTOUR", "SPOT_EG", "SPOT_FG", "LOW_POINTS"}
SUPPRESSED_LABEL_TOKENS = ("BUILDABLE_AREA", "GENERIC_UTILITY", "SERVICE_TIE", "SOURCE_SERVICE", "BUILDING_SERVICE")
PRIMARY_LAYOUT_LAYERS = {"BUILDING", "ROAD", "PAVEMENT", "PARKING", "WALK", "FIRE"}
SECONDARY_ENGINEERING_LAYERS = {
    "ANNO",
    "BASIN_BOUNDARY",
    "PIPE",
    "STORM",
    "SAN",
    "UTILITY",
    "STRUCTURE",
    "DRAIN_FLOW",
    "EG_CONTOUR",
    "FG_CONTOUR",
    "SPOT_EG",
    "SPOT_FG",
    "LOW_POINTS",
    "PAD",
    "SURFACE",
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
        points = safe_points(action.get("points"))
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
    if layer not in {"SITE", "SETBACK", "ROAD", "PAVEMENT", "PAD"}:
        return False
    if task != "rectangle":
        return False
    if label and label not in {"SITE", "LOT", "BUILDABLE_AREA", "DRIVE", "ROAD", "PAVEMENT"}:
        return False
    if text:
        return False
    bounds = _action_bounds(action)
    if not bounds:
        return False
    contained_buildings = [item for item in building_bounds if _contains_bounds(bounds, item["bounds"], tolerance=1.0)]
    if len(contained_buildings) < 2:
        return False
    wrapper_area = _bounds_area(bounds)
    if wrapper_area <= 0:
        return False
    max_building_area = max((_bounds_area(item["bounds"]) for item in contained_buildings), default=0.0)
    total_building_area = sum(_bounds_area(item["bounds"]) for item in contained_buildings)
    if max_building_area <= 0:
        return False
    return wrapper_area >= max(max_building_area * 6.0, total_building_area * 1.8)


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
        if layer in {"BUILDING", "PAVEMENT", "ROAD", "PARKING", "WALK"} and task in {"rectangle", "polygon", "polyline"}:
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


def _synthesize_layout_preview_actions(actions):
    records = [dict(action) for action in actions if isinstance(action, dict)]
    building_rects = []
    pavement_rects = []
    road_actions = []
    has_parking = False
    has_walk = False
    has_fire = False

    for action in records:
        layer = str(action.get("layer") or "").upper()
        bounds = _action_bounds(action)
        if layer == "BUILDING" and bounds:
            building_rects.append(bounds)
        elif layer == "PAVEMENT" and bounds:
            pavement_rects.append((bounds, action))
        elif layer == "ROAD":
            road_actions.append(action)
        elif layer == "PARKING":
            has_parking = True
        elif layer == "WALK":
            has_walk = True
        elif layer == "FIRE":
            has_fire = True

    synthesized = list(records)
    seen = {repr(action) for action in synthesized}

    if building_rects and not has_parking:
        for bounds, action in pavement_rects:
            center_x, _ = _rect_center(bounds)
            nearest_gap = min((_rect_gap(bounds, b_bounds) for b_bounds in building_rects), key=lambda pair: pair[0] + pair[1], default=(9999.0, 9999.0))
            overlaps_building_band = any(abs(center_x - _rect_center(b_bounds)[0]) <= max(bounds[2] - bounds[0], b_bounds[2] - b_bounds[0]) * 0.7 for b_bounds in building_rects)
            if nearest_gap[1] <= 120.0 and overlaps_building_band:
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

    if road_actions and not has_fire:
        for action in road_actions:
            out = dict(action)
            out["layer"] = "FIRE"
            key = repr(out)
            if key not in seen:
                seen.add(key)
                synthesized.append(out)

    return synthesized


def _filtered_preview_actions(actions):
    records = [action for action in actions if isinstance(action, dict)]
    records = _synthesize_layout_preview_actions(records)
    has_primary_site_geometry = _has_primary_site_geometry(records)
    has_layout_scene = _has_layout_scene(records)
    building_bounds = [
        {"action": action, "bounds": _action_bounds(action)}
        for action in records
        if (str(action.get("layer") or "").upper() == "BUILDING" and str(action.get("task") or "").lower() in {"rectangle", "polygon"})
    ]
    building_bounds = [item for item in building_bounds if item["bounds"]]
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
        if has_layout_scene and layer in SECONDARY_ENGINEERING_LAYERS:
            continue
        if has_layout_scene and layer == "BUILDING" and task == "text_note":
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
    elif layer == "PAVEMENT":
        fill_alpha = 0.06
        facecolor = get_color(action)

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
