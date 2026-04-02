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
    "PAVEMENT": 2.0,
    "PIPE": 2.0,
    "DRAIN_FLOW": 1.5,
    "SURFACE": 1.0,
    "EG_CONTOUR": 1.0,
    "FG_CONTOUR": 1.2,
    "BASIN_BOUNDARY": 1.8,
    "DEFAULT": 2.0,
}


def get_linewidth(action):
    layer = (action.get("layer") or "").upper()
    return LAYER_LINEWIDTH.get(layer, LAYER_LINEWIDTH["DEFAULT"])


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

    rect = Rectangle((x, y), w, h, fill=False, linewidth=get_linewidth(action))
    ax.add_patch(rect)

    if label:
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=9)

    return x, y, x + w, y + h


def draw_polygon(ax, action):
    pts = safe_points(action)
    if len(pts) < 3:
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    xs_closed = xs + [pts[0][0]]
    ys_closed = ys + [pts[0][1]]

    ax.plot(xs_closed, ys_closed, linewidth=get_linewidth(action))

    label = clean_label(action.get("label"), "")
    if label:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        ax.text(cx, cy, label, ha="center", va="center", fontsize=9)

    return min(xs_closed), min(ys_closed), max(xs_closed), max(ys_closed)


def draw_polyline(ax, action):
    pts = safe_points(action)
    if len(pts) < 2:
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    ax.plot(xs, ys, linewidth=get_linewidth(action))

    label = clean_label(action.get("label"), "")
    if label:
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        ax.text(cx, cy, label, ha="center", va="center", fontsize=9)

    return min(xs), min(ys), max(xs), max(ys)


def draw_circle(ax, action):
    cx, cy = safe_center(action)
    r = safe_num(action.get("radius"))
    label = clean_label(action.get("label"), "")

    if r <= 0:
        return None

    circle = Circle((cx, cy), r, fill=False, linewidth=get_linewidth(action))
    ax.add_patch(circle)

    if label:
        ax.text(cx, cy, label, ha="center", va="center", fontsize=9)

    return cx - r, cy - r, cx + r, cy + r


def draw_arc(ax, action):
    cx, cy = safe_center(action)
    r = safe_num(action.get("radius"))
    a1 = safe_num(action.get("start_angle"))
    a2 = safe_num(action.get("end_angle"))
    label = clean_label(action.get("label"), "")

    if r <= 0:
        return None

    arc = Arc((cx, cy), 2 * r, 2 * r, angle=0, theta1=a1, theta2=a2, linewidth=get_linewidth(action))
    ax.add_patch(arc)

    if label:
        ax.text(cx, cy, label, ha="center", va="center", fontsize=9)

    return cx - r, cy - r, cx + r, cy + r


def draw_text(ax, action):
    x, y = safe_origin(action)
    txt = safe_text(action.get("text"), "")
    h = max(safe_num(action.get("text_height"), 1.0), 0.5)

    ax.text(x, y, txt, fontsize=min(6 + h, 16))

    return x - 2, y - 2, x + 4, y + 2


def draw_point(ax, action):
    x, y = safe_origin(action)
    label = clean_label(action.get("label"), "")
    size = max(safe_num(action.get("radius"), 0.75), 0.25)

    ax.plot([x - size, x + size], [y, y], linewidth=get_linewidth(action))
    ax.plot([x, x], [y - size, y + size], linewidth=get_linewidth(action))

    if label:
        ax.text(x + size + 0.2, y + size + 0.2, label, ha="left", va="bottom", fontsize=8)

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

def _draw_plan(ax, plan):
    actions = plan.get("actions", [])
    if not actions:
        return False

    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

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

        min_x = min(min_x, x1)
        min_y = min(min_y, y1)
        max_x = max(max_x, x2)
        max_y = max(max_y, y2)

    if min_x == float("inf"):
        return False

    pad_x = max((max_x - min_x) * 0.1, 5)
    pad_y = max((max_y - min_y) * 0.1, 5)

    ax.set_xlim(min_x - pad_x, max_x + pad_x)
    ax.set_ylim(min_y - pad_y, max_y + pad_y)

    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", linewidth=0.5)

    ax.set_title(plan.get("project_name", "Plan Preview"))
    return True


def render_plan_preview_png(plan, *, figsize=(8, 8), dpi: int = 160) -> bytes:
    fig = Figure(figsize=figsize, dpi=dpi)
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
