from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import ezdxf

from core.utils import (
    clean_label,
    safe_center,
    safe_dict,
    safe_list,
    safe_num,
    safe_origin,
    safe_points,
    safe_text,
    timestamped_filename,
)


ALLOWED_LAYERS = {
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
    "DRAIN_FLOW",
    "LOW_POINTS",
    "SPOT_EG",
    "SPOT_FG",
    "PIPE",
    "BASIN_BOUNDARY",
    "UTILITY",
    "SAN",
    "STORM",
    "DRAIN",
    "ROUTE",
    "SKETCH_ZONE",
    "SKETCH_OBS",
    "SKETCH_LINE",
    "SKETCH_PTS",
    "SKETCH_BLDG",
    "SKETCH_PARK",
    "SKETCH_ROAD",
    "SKETCH_DRAIN",
    "SKETCH_UTIL",
    "SKETCH_PAD",
    "SKETCH_BLDG_PTS",
    "SKETCH_DRAIN_PTS",
    "SKETCH_UTIL_PTS",
    "SKETCH_ROAD_PTS",
    "WALK",
    "SHEET",
    "TITLE",
    "GRID",
    "AXIS",
    "VIEWPORT",
    "DIM",
    "MATCHLINE",
    "HATCH",
}


LAYER_ALIASES = {
    "PARKING": "PAVEMENT",
    "PARK": "PAVEMENT",
    "WALKWAY": "WALK",
    "SIDEWALK": "WALK",
    "FIRE": "ROAD",
    "PAD": "SITE",
    "BASIN": "BASIN_BOUNDARY",
    "STAIRS": "SYMBOL",
    "ELEVATOR": "SYMBOL",
}


LAYER_COLORS = {
    "SITE": 7,
    "SETBACK": 8,
    "BUILDING": 2,
    "PAVEMENT": 6,
    "ANNO": 7,
    "SYMBOL": 3,
    "STRUCTURE": 1,
    "WATER": 5,
    "ROAD": 4,
    "LOT": 7,
    "SURFACE": 8,
    "EG_CONTOUR": 8,
    "FG_CONTOUR": 3,
    "DRAIN_FLOW": 5,
    "LOW_POINTS": 1,
    "SPOT_EG": 8,
    "SPOT_FG": 2,
    "PIPE": 4,
    "BASIN_BOUNDARY": 6,
    "UTILITY": 5,
    "SAN": 1,
    "STORM": 4,
    "DRAIN": 6,
    "ROUTE": 3,
    "SKETCH_ZONE": 8,
    "SKETCH_OBS": 1,
    "SKETCH_LINE": 5,
    "SKETCH_PTS": 2,
    "SKETCH_BLDG": 2,
    "SKETCH_PARK": 6,
    "SKETCH_ROAD": 4,
    "SKETCH_DRAIN": 6,
    "SKETCH_UTIL": 5,
    "SKETCH_PAD": 3,
    "SKETCH_BLDG_PTS": 2,
    "SKETCH_DRAIN_PTS": 6,
    "SKETCH_UTIL_PTS": 5,
    "SKETCH_ROAD_PTS": 4,
    "WALK": 3,
    "SHEET": 8,
    "TITLE": 7,
    "GRID": 8,
    "AXIS": 7,
    "VIEWPORT": 9,
    "DIM": 2,
    "MATCHLINE": 6,
    "HATCH": 8,
}


LAYER_LINEWEIGHTS = {
    "SITE": 35,
    "SETBACK": 18,
    "BUILDING": 40,
    "PAVEMENT": 30,
    "ANNO": 18,
    "SYMBOL": 20,
    "STRUCTURE": 40,
    "WATER": 25,
    "ROAD": 35,
    "LOT": 25,
    "SURFACE": 13,
    "EG_CONTOUR": 13,
    "FG_CONTOUR": 18,
    "DRAIN_FLOW": 15,
    "LOW_POINTS": 20,
    "SPOT_EG": 13,
    "SPOT_FG": 13,
    "PIPE": 30,
    "BASIN_BOUNDARY": 25,
    "UTILITY": 25,
    "SAN": 30,
    "STORM": 30,
    "DRAIN": 25,
    "ROUTE": 25,
    "SKETCH_ZONE": 13,
    "SKETCH_OBS": 25,
    "SKETCH_LINE": 18,
    "SKETCH_PTS": 18,
    "SKETCH_BLDG": 25,
    "SKETCH_PARK": 25,
    "SKETCH_ROAD": 25,
    "SKETCH_DRAIN": 20,
    "SKETCH_UTIL": 20,
    "SKETCH_PAD": 20,
    "SKETCH_BLDG_PTS": 18,
    "SKETCH_DRAIN_PTS": 18,
    "SKETCH_UTIL_PTS": 18,
    "SKETCH_ROAD_PTS": 18,
    "WALK": 20,
    "SHEET": 20,
    "TITLE": 25,
    "GRID": 9,
    "AXIS": 18,
    "VIEWPORT": 13,
    "DIM": 18,
    "MATCHLINE": 25,
    "HATCH": 9,
}


PAGE_WIDTH_MM = 420.0
PAGE_HEIGHT_MM = 297.0
PAGE_MARGIN_MM = 8.0
TITLE_BLOCK_HEIGHT_MM = 24.0
STANDARD_ENGINEERING_SCALES_FT_PER_IN = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 80.0, 100.0, 150.0, 200.0]
LABEL_STYLES = {
    "structure": {"height": 1.8, "layer": "ANNO", "prefix": ""},
    "pipe": {"height": 1.7, "layer": "ANNO", "prefix": ""},
    "slope": {"height": 1.7, "layer": "ANNO", "prefix": ""},
    "elevation": {"height": 1.7, "layer": "ANNO", "prefix": ""},
}
DEFAULT_REVISION = "BETA"
CAD_BLOCKS = {
    "CIVIL_NORTH_ARROW",
    "CIVIL_MANHOLE",
    "CIVIL_INLET",
    "CIVIL_OUTFALL",
    "CIVIL_JUNCTION",
}


def get_layer(action: Dict[str, Any], fallback: str) -> str:
    raw = safe_text(action.get("layer"), fallback).upper().strip()
    raw = LAYER_ALIASES.get(raw, raw)
    return raw if raw in ALLOWED_LAYERS else fallback


def ensure_layers(doc) -> None:
    for layer_name in sorted(ALLOWED_LAYERS):
        if layer_name not in doc.layers:
            doc.layers.add(
                name=layer_name,
                color=LAYER_COLORS.get(layer_name, 7),
                lineweight=LAYER_LINEWEIGHTS.get(layer_name, 18),
            )


def ensure_text_styles(doc) -> None:
    if "CIVIL" not in doc.styles:
        doc.styles.add("CIVIL", font="txt")
    if "CIVIL-BOLD" not in doc.styles:
        doc.styles.add("CIVIL-BOLD", font="txt")
    if "CIVIL-NARROW" not in doc.styles:
        doc.styles.add("CIVIL-NARROW", font="txt")


def ensure_blocks(doc) -> None:
    if "CIVIL_NORTH_ARROW" not in doc.blocks:
        block = doc.blocks.new(name="CIVIL_NORTH_ARROW")
        block.add_line((0.0, -6.0), (0.0, 6.0), dxfattribs={"layer": "SYMBOL"})
        block.add_line((0.0, 6.0), (-1.6, 3.0), dxfattribs={"layer": "SYMBOL"})
        block.add_line((0.0, 6.0), (1.6, 3.0), dxfattribs={"layer": "SYMBOL"})
        block.add_circle((0.0, 0.0), 1.9, dxfattribs={"layer": "SYMBOL"})
        text = block.add_text("N", dxfattribs={"height": 3.0, "layer": "TITLE", "style": "CIVIL-BOLD"})
        text.dxf.insert = (-1.2, 8.0)
    if "CIVIL_MANHOLE" not in doc.blocks:
        block = doc.blocks.new(name="CIVIL_MANHOLE")
        block.add_circle((0.0, 0.0), 2.1, dxfattribs={"layer": "STRUCTURE"})
        block.add_circle((0.0, 0.0), 1.0, dxfattribs={"layer": "STRUCTURE"})
        block.add_line((-2.1, 0.0), (2.1, 0.0), dxfattribs={"layer": "STRUCTURE"})
        block.add_line((0.0, -2.1), (0.0, 2.1), dxfattribs={"layer": "STRUCTURE"})
    if "CIVIL_INLET" not in doc.blocks:
        block = doc.blocks.new(name="CIVIL_INLET")
        block.add_lwpolyline([(-2.0, -1.2), (2.0, -1.2), (2.0, 1.2), (-2.0, 1.2)], close=True, dxfattribs={"layer": "STRUCTURE"})
        block.add_line((-1.4, -1.2), (1.4, 1.2), dxfattribs={"layer": "STRUCTURE"})
        block.add_line((-1.4, 1.2), (1.4, -1.2), dxfattribs={"layer": "STRUCTURE"})
    if "CIVIL_OUTFALL" not in doc.blocks:
        block = doc.blocks.new(name="CIVIL_OUTFALL")
        block.add_lwpolyline([(-2.2, -1.6), (2.2, 0.0), (-2.2, 1.6)], dxfattribs={"layer": "STRUCTURE"})
        block.add_line((-3.2, 0.0), (-2.2, 0.0), dxfattribs={"layer": "STRUCTURE"})
    if "CIVIL_JUNCTION" not in doc.blocks:
        block = doc.blocks.new(name="CIVIL_JUNCTION")
        block.add_lwpolyline([(-1.8, -1.8), (1.8, -1.8), (1.8, 1.8), (-1.8, 1.8)], close=True, dxfattribs={"layer": "STRUCTURE"})
        block.add_line((-1.3, 0.0), (1.3, 0.0), dxfattribs={"layer": "STRUCTURE"})
        block.add_line((0.0, -1.3), (0.0, 1.3), dxfattribs={"layer": "STRUCTURE"})


def _insert_block(space, block_name: str, x: float, y: float, layer: str = "SYMBOL", scale: float = 1.0, rotation: float = 0.0) -> None:
    try:
        space.add_blockref(
            block_name,
            (x, y),
            dxfattribs={
                "layer": layer,
                "xscale": scale,
                "yscale": scale,
                "rotation": rotation,
            },
        )
    except Exception:
        return


def add_text(
    space,
    text: str,
    x: float,
    y: float,
    height: float = 2.0,
    layer: str = "ANNO",
    rotation: float = 0.0,
    style: str = "CIVIL",
) -> None:
    text = safe_text(text, "")
    if not text:
        return

    txt = space.add_text(
        text,
        dxfattribs={
            "height": max(height, 0.35),
            "layer": layer,
            "rotation": rotation,
            "style": style,
        },
    )
    txt.dxf.insert = (x, y)


def _polyline_center(points: Iterable[Tuple[float, float]]) -> Tuple[float, float]:
    pts = list(points)
    if not pts:
        return 0.0, 0.0
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return cx, cy


def _normalize_points(points: Iterable[Tuple[float, float]]) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    for p in points:
        if len(p) < 2:
            continue
        out.append((float(p[0]), float(p[1])))
    return out


def _dedupe_consecutive_points(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if not points:
        return []
    cleaned = [points[0]]
    for p in points[1:]:
        if abs(p[0] - cleaned[-1][0]) > 1e-9 or abs(p[1] - cleaned[-1][1]) > 1e-9:
            cleaned.append(p)
    return cleaned


def _safe_closed(action: Dict[str, Any], default: bool = False) -> bool:
    value = action.get("closed", default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _plan_bbox(actions: List[Dict[str, Any]]) -> Tuple[float, float, float, float] | None:
    xs: List[float] = []
    ys: List[float] = []

    for action in actions:
        task = safe_text(action.get("task"), "").strip().lower()
        if task == "rectangle":
            x, y = safe_origin(action)
            w = safe_num(action.get("width"))
            h = safe_num(action.get("height"))
            if w > 0 and h > 0:
                xs.extend([x, x + w])
                ys.extend([y, y + h])
        elif task in {"polyline", "polygon"}:
            pts = _dedupe_consecutive_points(_normalize_points(safe_points(action)))
            if pts:
                xs.extend([p[0] for p in pts])
                ys.extend([p[1] for p in pts])
        elif task in {"circle", "arc"}:
            cx, cy = safe_center(action)
            r = safe_num(action.get("radius"))
            if r > 0:
                xs.extend([cx - r, cx + r])
                ys.extend([cy - r, cy + r])
        elif task in {"text_note", "point", "north_arrow"}:
            x, y = safe_origin(action)
            xs.append(x)
            ys.append(y)

    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _summary_anchor(actions: List[Dict[str, Any]]) -> Tuple[float, float]:
    bbox = _plan_bbox(actions)
    if bbox is None:
        return 0.0, 0.0
    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    height = max_y - min_y
    x = min_x
    y = max_y + max(6.0, height * 0.04)
    return x, y


def _draw_rectangle(msp, action: Dict[str, Any], layer: str) -> None:
    x, y = safe_origin(action)
    w = safe_num(action.get("width"))
    h = safe_num(action.get("height"))
    label = clean_label(action.get("label"), "")
    if w <= 0 or h <= 0:
        return
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})
    if label:
        add_text(msp, label, x + w / 2.0, y + h / 2.0, 1.4, "ANNO")


def _draw_polyline(msp, action: Dict[str, Any], layer: str) -> None:
    pts = _dedupe_consecutive_points(_normalize_points(safe_points(action)))
    label = clean_label(action.get("label"), "")
    closed = _safe_closed(action, False)
    if len(pts) < 2:
        return
    msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer})
    if label:
        cx, cy = _polyline_center(pts)
        add_text(msp, label, cx, cy, 1.0, "ANNO")


def _draw_polygon(msp, action: Dict[str, Any], layer: str) -> None:
    pts = _dedupe_consecutive_points(_normalize_points(safe_points(action)))
    label = clean_label(action.get("label"), "")
    if len(pts) < 3:
        return
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})
    if label:
        cx, cy = _polyline_center(pts)
        add_text(msp, label, cx, cy, 1.0, "ANNO")


def _draw_circle(msp, action: Dict[str, Any], layer: str) -> None:
    cx, cy = safe_center(action)
    r = safe_num(action.get("radius"))
    label = clean_label(action.get("label"), "")
    if r <= 0:
        return
    msp.add_circle((cx, cy), r, dxfattribs={"layer": layer})
    if label:
        add_text(msp, label, cx, cy, 1.0, "ANNO")


def _draw_arc(msp, action: Dict[str, Any], layer: str) -> None:
    cx, cy = safe_center(action)
    r = safe_num(action.get("radius"))
    a1 = safe_num(action.get("start_angle"))
    a2 = safe_num(action.get("end_angle"))
    label = clean_label(action.get("label"), "")
    if r <= 0:
        return
    msp.add_arc(center=(cx, cy), radius=r, start_angle=a1, end_angle=a2, dxfattribs={"layer": layer})
    if label:
        add_text(msp, label, cx, cy, 1.0, "ANNO")


def _draw_text_note(msp, action: Dict[str, Any], layer: str) -> None:
    x, y = safe_origin(action)
    txt = safe_text(action.get("text"), "")
    h = max(safe_num(action.get("text_height"), 1.0), 0.35)
    add_text(msp, txt, x, y, h, layer)


def _draw_north_arrow(msp, action: Dict[str, Any]) -> None:
    x, y = safe_origin(action)
    msp.add_line((x, y), (x, y + 8), dxfattribs={"layer": "SYMBOL"})
    msp.add_line((x, y + 8), (x - 1, y + 6.5), dxfattribs={"layer": "SYMBOL"})
    msp.add_line((x, y + 8), (x + 1, y + 6.5), dxfattribs={"layer": "SYMBOL"})
    add_text(msp, "N", x, y + 9, 2.5, "ANNO")


def _draw_point_marker(msp, action: Dict[str, Any], layer: str) -> None:
    x, y = safe_origin(action)
    label = clean_label(action.get("label"), "")
    size = max(safe_num(action.get("radius"), 0.75), 0.2)
    msp.add_line((x - size, y), (x + size, y), dxfattribs={"layer": layer})
    msp.add_line((x, y - size), (x, y + size), dxfattribs={"layer": layer})
    if label:
        add_text(msp, label, x + size + 0.2, y + size + 0.2, 0.9, "ANNO")


def _write_summary_block(msp, plan: Dict[str, Any], actions: List[Dict[str, Any]]) -> None:
    x, y = _summary_anchor(actions)
    project_name = safe_text(plan.get("project_name"), "")
    if project_name:
        add_text(msp, project_name, x, y, 2.5, "ANNO", style="CIVIL-BOLD")
        y -= 3.0
    units = safe_text(plan.get("units"), "")
    if units:
        add_text(msp, f"Units: {units}", x, y, 1.2, "ANNO")
        y -= 1.8
    assumptions = plan.get("assumptions", [])
    if isinstance(assumptions, list):
        for item in assumptions[:6]:
            txt = safe_text(item, "")
            if txt:
                add_text(msp, txt, x, y, 1.0, "ANNO")
                y -= 1.5


def _draw_action_to_modelspace(msp, action: Dict[str, Any]) -> None:
    task = safe_text(action.get("task"), "").strip().lower()
    layer = get_layer(action, "SITE")
    if task == "rectangle":
        _draw_rectangle(msp, action, layer)
    elif task == "polyline":
        _draw_polyline(msp, action, layer)
    elif task == "polygon":
        _draw_polygon(msp, action, layer)
    elif task == "circle":
        _draw_circle(msp, action, layer)
    elif task == "arc":
        _draw_arc(msp, action, layer)
    elif task == "text_note":
        _draw_text_note(msp, action, layer)
    elif task == "north_arrow":
        _draw_north_arrow(msp, action)
    elif task == "point":
        _draw_point_marker(msp, action, layer)


def _draw_box(space, x0: float, y0: float, x1: float, y1: float, layer: str = "SHEET") -> None:
    space.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer})


def _draw_polyline_points(space, points: Sequence[Sequence[float]], layer: str, close: bool = False) -> None:
    pts = [(safe_num(pt[0]), safe_num(pt[1])) for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    if len(pts) < 2:
        return
    space.add_lwpolyline(pts, close=close, dxfattribs={"layer": layer})


def _draw_north_arrow_sheet(space, x: float, y: float, size: float = 14.0) -> None:
    _insert_block(space, "CIVIL_NORTH_ARROW", x, y + size * 0.45, layer="SYMBOL", scale=max(size / 12.0, 0.5))


def _polyline_length(points: Sequence[Sequence[float]]) -> float:
    total = 0.0
    cleaned = [(safe_num(pt[0]), safe_num(pt[1])) for pt in points if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    for idx in range(1, len(cleaned)):
        dx = cleaned[idx][0] - cleaned[idx - 1][0]
        dy = cleaned[idx][1] - cleaned[idx - 1][1]
        total += (dx * dx + dy * dy) ** 0.5
    return total


def _station_text(station_ft: float) -> str:
    total = max(0, int(round(safe_num(station_ft))))
    return f"{total // 100}+{total % 100:02d}"


def _sample_grid_surface_payload(surface: Any, x: float, y: float, default: float) -> float:
    rec = safe_dict(surface)
    if not rec:
        return default
    try:
        cell = max(1.0, safe_num(rec.get("cell_size"), 1.0))
        x_min = safe_num(rec.get("x_min"), 0.0)
        y_min = safe_num(rec.get("y_min"), 0.0)
        row = int(round((y - y_min) / cell))
        col = int(round((x - x_min) / cell))
        values = safe_list(rec.get("values"))
        if not values:
            return default
        row = max(0, min(len(values) - 1, row))
        row_values = safe_list(values[row])
        if not row_values:
            return default
        col = max(0, min(len(row_values) - 1, col))
        return safe_num(row_values[col], default)
    except Exception:
        return default


def _polyline_station_samples(path: Sequence[Sequence[float]], count: int) -> List[Dict[str, Any]]:
    points = [[safe_num(pt[0]), safe_num(pt[1])] for pt in path if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    if len(points) < 2:
        return []
    lengths = [0.0]
    for idx in range(1, len(points)):
        lengths.append(lengths[-1] + _polyline_length([points[idx - 1], points[idx]]))
    total = lengths[-1]
    if total <= 0.0:
        return [{"station_ft": 0.0, "point": points[0], "segment_index": 0}]
    out: List[Dict[str, Any]] = []
    sample_count = max(2, count)
    for sample_idx in range(sample_count):
        target = total * (sample_idx / max(sample_count - 1, 1))
        for idx in range(1, len(points)):
            if lengths[idx] + 1e-9 < target:
                continue
            segment_length = max(lengths[idx] - lengths[idx - 1], 1e-9)
            ratio = (target - lengths[idx - 1]) / segment_length
            x0, y0 = points[idx - 1]
            x1, y1 = points[idx]
            out.append(
                {
                    "station_ft": round(target, 3),
                    "point": [round(x0 + (x1 - x0) * ratio, 3), round(y0 + (y1 - y0) * ratio, 3)],
                    "segment_index": idx - 1,
                }
            )
            break
    return out


def _perpendicular_cut_line(path: Sequence[Sequence[float]], station_point: Sequence[float], station_segment_index: int, half_width_ft: float) -> List[List[float]]:
    points = [[safe_num(pt[0]), safe_num(pt[1])] for pt in path if isinstance(pt, (list, tuple)) and len(pt) >= 2]
    if len(points) < 2:
        px = safe_num(station_point[0])
        py = safe_num(station_point[1])
        return [[px - half_width_ft, py], [px + half_width_ft, py]]
    idx = max(0, min(len(points) - 2, int(station_segment_index)))
    x0, y0 = points[idx]
    x1, y1 = points[idx + 1]
    dx = x1 - x0
    dy = y1 - y0
    mag = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    nx = -dy / mag
    ny = dx / mag
    px = safe_num(station_point[0])
    py = safe_num(station_point[1])
    return [
        [round(px - nx * half_width_ft, 3), round(py - ny * half_width_ft, 3)],
        [round(px + nx * half_width_ft, 3), round(py + ny * half_width_ft, 3)],
    ]


def _sample_along_line(start: Sequence[float], end: Sequence[float], count: int) -> List[List[float]]:
    if count <= 1:
        return [[safe_num(start[0]), safe_num(start[1])]]
    sx, sy = safe_num(start[0]), safe_num(start[1])
    ex, ey = safe_num(end[0]), safe_num(end[1])
    return [[sx + (ex - sx) * (idx / max(count - 1, 1)), sy + (ey - sy) * (idx / max(count - 1, 1))] for idx in range(count)]


def _road_alignment_from_actions(actions: Sequence[Dict[str, Any]]) -> Optional[Tuple[List[List[float]], str]]:
    preferred: Optional[List[List[float]]] = None
    road_rect: Optional[Tuple[float, float, float, float]] = None
    for action in actions:
        rec = safe_dict(action)
        task = safe_text(rec.get("task"), "").lower()
        layer = safe_text(rec.get("layer"), "").upper()
        if task == "polyline" and layer == "ROAD":
            points = [[safe_num(pt[0]), safe_num(pt[1])] for pt in safe_list(rec.get("points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
            if len(points) < 2:
                continue
            label = safe_text(rec.get("label"), "").lower()
            if "cl" in label or "centerline" in label:
                return points, "road_centerline"
            if preferred is None:
                preferred = points
        elif task == "rectangle" and layer == "ROAD":
            x, y = safe_origin(rec)
            w = safe_num(rec.get("width"))
            h = safe_num(rec.get("height"))
            if w > 0.0 and h > 0.0 and (road_rect is None or max(w, h) > max(road_rect[2], road_rect[3])):
                road_rect = (x, y, w, h)
    if preferred is not None:
        return preferred, "road_polyline"
    if road_rect is not None:
        x, y, w, h = road_rect
        if w >= h:
            return [[x, y + h / 2.0], [x + w, y + h / 2.0]], "road_rectangle"
        return [[x + w / 2.0, y], [x + w / 2.0, y + h]], "road_rectangle"
    return None


def _nice_interval(span: float, target_steps: int = 6) -> float:
    span = max(span, 1e-6)
    rough = span / max(target_steps, 1)
    magnitude = 10.0 ** math.floor(math.log10(rough))
    for multiplier in (1.0, 2.0, 5.0, 10.0):
        candidate = magnitude * multiplier
        if candidate >= rough - 1e-9:
            return candidate
    return rough


def _nice_floor(value: float, interval: float) -> float:
    if interval <= 0.0:
        return value
    return math.floor(value / interval) * interval


def _nice_ceil(value: float, interval: float) -> float:
    if interval <= 0.0:
        return value
    return math.ceil(value / interval) * interval


def _pick_engineering_scale_ft_per_in(span_x_ft: float, span_y_ft: float, width_mm: float, height_mm: float, padding_factor: float = 1.12) -> float:
    need_x = max(span_x_ft, 1.0) * padding_factor
    need_y = max(span_y_ft, 1.0) * padding_factor
    for scale in STANDARD_ENGINEERING_SCALES_FT_PER_IN:
        if width_mm * scale / 25.4 >= need_x and height_mm * scale / 25.4 >= need_y:
            return scale
    return max(need_x * 25.4 / max(width_mm, 1.0), need_y * 25.4 / max(height_mm, 1.0), STANDARD_ENGINEERING_SCALES_FT_PER_IN[-1])


def _format_scale(scale_ft_per_in: float) -> str:
    return f'1"={scale_ft_per_in:.0f}\''


def _scale_bar_length_ft(scale_ft_per_in: float) -> float:
    if scale_ft_per_in <= 10.0:
        return 20.0
    if scale_ft_per_in <= 40.0:
        return 50.0
    if scale_ft_per_in <= 100.0:
        return 100.0
    return 200.0


def _draw_scale_bar(space, x: float, y: float, scale_ft_per_in: float) -> None:
    segment_ft = _scale_bar_length_ft(scale_ft_per_in) / 4.0
    segment_mm = segment_ft * 25.4 / max(scale_ft_per_in, 1e-9)
    bar_height = 3.5
    for idx in range(4):
        x0 = x + idx * segment_mm
        x1 = x0 + segment_mm
        _draw_box(space, x0, y, x1, y + bar_height, layer="GRID")
        if idx % 2 == 0:
            space.add_lwpolyline([(x0, y), (x1, y), (x1, y + bar_height), (x0, y + bar_height)], close=True, dxfattribs={"layer": "ANNO"})
        add_text(space, f"{int(round(segment_ft * idx))}", x0 - 1.0, y - 4.0, 2.2, "ANNO")
    add_text(space, f"{int(round(segment_ft * 4))} FT", x + segment_mm * 4 + 2.0, y - 4.0, 2.2, "ANNO")
    add_text(space, "SCALE BAR", x, y + bar_height + 2.5, 2.3, "TITLE", style="CIVIL-BOLD")


def _draw_table_grid(space, x0: float, y0: float, widths: Sequence[float], row_height: float, rows: Sequence[Sequence[str]], title: str = "") -> None:
    total_width = sum(widths)
    total_height = row_height * max(len(rows), 1)
    _draw_box(space, x0, y0, x0 + total_width, y0 + total_height, layer="SHEET")
    if title:
        add_text(space, title, x0, y0 + total_height + 2.5, 2.3, "TITLE", style="CIVIL-BOLD")
    running_x = x0
    for width in widths[:-1]:
        running_x += width
        space.add_line((running_x, y0), (running_x, y0 + total_height), dxfattribs={"layer": "SHEET"})
    for idx in range(1, len(rows)):
        y = y0 + idx * row_height
        space.add_line((x0, y), (x0 + total_width, y), dxfattribs={"layer": "SHEET"})
    for row_idx, row in enumerate(rows):
        text_y = y0 + total_height - (row_idx + 0.7) * row_height
        cx = x0
        for col_idx, width in enumerate(widths):
            value = safe_text(row[col_idx] if col_idx < len(row) else "", "")
            if value:
                add_text(space, value, cx + 1.5, text_y, 1.9 if row_idx else 2.0, "ANNO" if row_idx else "TITLE", style="CIVIL-BOLD" if row_idx == 0 else "CIVIL")
            cx += width


def _nearest_station_text(stations: Sequence[Dict[str, Any]], target_station: float) -> str:
    best = None
    best_delta = float("inf")
    for station in stations:
        rec = safe_dict(station)
        station_ft = safe_num(rec.get("station_ft"))
        delta = abs(station_ft - target_station)
        if delta < best_delta:
            best_delta = delta
            best = rec
    if best is None:
        return _station_text(target_station)
    return safe_text(best.get("station_text"), _station_text(safe_num(best.get("station_ft"))))


def _label_text(label_type: str, text: str) -> Tuple[str, float, str]:
    style = LABEL_STYLES.get(label_type, LABEL_STYLES["structure"])
    return safe_text(text, ""), float(style["height"]), safe_text(style["layer"], "ANNO")


def _sheet_content_rect() -> Tuple[float, float, float, float]:
    return (
        PAGE_MARGIN_MM + 10.0,
        PAGE_MARGIN_MM + TITLE_BLOCK_HEIGHT_MM + 10.0,
        PAGE_WIDTH_MM - PAGE_MARGIN_MM - 10.0,
        PAGE_HEIGHT_MM - PAGE_MARGIN_MM - 10.0,
    )


def _draw_title_block(
    space,
    plan: Dict[str, Any],
    sheet_title: str,
    sheet_name: str,
    scale_label: str,
    subtitle: str = "",
    *,
    sheet_code: str = "",
    sheet_number: int = 1,
    sheet_total: int = 1,
    discipline: str = "CIVIL",
    revision: str = DEFAULT_REVISION,
    issue_date: str = "",
) -> None:
    outer_x0 = PAGE_MARGIN_MM
    outer_y0 = PAGE_MARGIN_MM
    outer_x1 = PAGE_WIDTH_MM - PAGE_MARGIN_MM
    outer_y1 = PAGE_HEIGHT_MM - PAGE_MARGIN_MM
    block_top = outer_y0 + TITLE_BLOCK_HEIGHT_MM

    _draw_box(space, outer_x0, outer_y0, outer_x1, outer_y1, layer="SHEET")
    space.add_line((outer_x0, block_top), (outer_x1, block_top), dxfattribs={"layer": "SHEET"})
    for split_x in (220.0, 285.0, 340.0, 380.0):
        space.add_line((split_x, outer_y0), (split_x, block_top), dxfattribs={"layer": "SHEET"})

    add_text(space, safe_text(plan.get("project_name"), "Civora AI"), outer_x0 + 4.0, outer_y0 + 14.5, 5.1, "TITLE", style="CIVIL-BOLD")
    add_text(space, sheet_title, outer_x0 + 4.0, outer_y0 + 6.2, 4.0, "TITLE", style="CIVIL-BOLD")
    if subtitle:
        add_text(space, subtitle, outer_x0 + 104.0, outer_y0 + 6.3, 2.25, "TITLE", style="CIVIL-NARROW")

    add_text(space, "SHEET", 223.0, outer_y0 + 15.0, 2.2, "TITLE", style="CIVIL-BOLD")
    add_text(space, safe_text(sheet_code, sheet_name), 223.0, outer_y0 + 8.0, 2.8, "ANNO")
    add_text(space, "NO.", 288.0, outer_y0 + 15.0, 2.2, "TITLE", style="CIVIL-BOLD")
    add_text(space, f"{sheet_number}/{max(sheet_total, 1)}", 288.0, outer_y0 + 8.0, 2.8, "ANNO")
    add_text(space, "SCALE", 343.0, outer_y0 + 15.0, 2.2, "TITLE", style="CIVIL-BOLD")
    add_text(space, scale_label, 343.0, outer_y0 + 8.0, 2.8, "ANNO")
    add_text(space, "UNITS", 383.0, outer_y0 + 15.0, 2.2, "TITLE", style="CIVIL-BOLD")
    add_text(space, safe_text(plan.get("units"), "ft"), 383.0, outer_y0 + 8.0, 2.8, "ANNO")
    add_text(space, safe_text(sheet_name, ""), 138.0, outer_y0 + 6.3, 2.1, "ANNO", style="CIVIL-NARROW")
    add_text(space, "DISC", 223.0, outer_y0 + 20.0, 1.8, "TITLE", style="CIVIL-BOLD")
    add_text(space, discipline, 240.0, outer_y0 + 20.0, 1.8, "ANNO")
    add_text(space, "REV", 288.0, outer_y0 + 20.0, 1.8, "TITLE", style="CIVIL-BOLD")
    add_text(space, revision, 304.0, outer_y0 + 20.0, 1.8, "ANNO")
    add_text(space, "DATE", 343.0, outer_y0 + 20.0, 1.8, "TITLE", style="CIVIL-BOLD")
    add_text(space, issue_date or datetime.now().strftime("%Y-%m-%d"), 358.0, outer_y0 + 20.0, 1.8, "ANNO")


def _layout_names(doc) -> set[str]:
    return {layout.name for layout in doc.layouts}


def _fresh_layout(doc, preferred_name: str):
    name = safe_text(preferred_name, "SHEET").strip()[:60] or "SHEET"
    if name in _layout_names(doc):
        doc.layouts.delete(name)
    layout = doc.layouts.new(name)
    layout.page_setup(size=(PAGE_WIDTH_MM, PAGE_HEIGHT_MM), margins=(0, 0, 0, 0), units="mm", rotation=0, scale=16)
    return layout


def _make_unique_layout_name(doc, preferred_name: str) -> str:
    base = safe_text(preferred_name, "SHEET").strip()[:52] or "SHEET"
    names = _layout_names(doc)
    if base not in names:
        return base
    idx = 2
    while True:
        candidate = f"{base[:48]} {idx}"
        if candidate not in names:
            return candidate
        idx += 1


def _site_plan_view_bbox(actions: List[Dict[str, Any]]) -> Tuple[float, float, float, float] | None:
    filtered: List[Dict[str, Any]] = []
    for action in actions:
        if safe_text(action.get("task"), "").strip().lower() == "text_note":
            continue
        filtered.append(action)
    return _plan_bbox(filtered)


def _add_site_plan_layout(doc, plan: Dict[str, Any], actions: List[Dict[str, Any]], sheet_meta: Optional[Dict[str, Any]] = None) -> None:
    layout = _fresh_layout(doc, "SITE PLAN")
    bbox = _site_plan_view_bbox(actions)

    view_x0, view_y0, view_x1, view_y1 = 26.0, 42.0, 388.0, 265.0
    view_w = view_x1 - view_x0
    view_h = view_y1 - view_y0
    scale_label = "NTS"
    scale_ft_per_in = 20.0
    title = "SITE PLAN"

    if bbox is not None:
        min_x, min_y, max_x, max_y = bbox
        center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
        scale_ft_per_in = _pick_engineering_scale_ft_per_in(max_x - min_x, max_y - min_y, view_w, view_h)
        view_height = view_h * scale_ft_per_in / 25.4
        layout.add_viewport(
            center=((view_x0 + view_x1) / 2.0, (view_y0 + view_y1) / 2.0),
            size=(view_w, view_h),
            view_center_point=center,
            view_height=view_height,
            dxfattribs={"layer": "VIEWPORT"},
        )
        scale_label = _format_scale(scale_ft_per_in)

    sheet_meta = safe_dict(sheet_meta)
    _draw_title_block(
        layout,
        plan,
        title,
        safe_text(sheet_meta.get("sheet_name"), "SITE PLAN"),
        scale_label,
        sheet_code=safe_text(sheet_meta.get("sheet_code"), "C-100"),
        sheet_number=int(safe_num(sheet_meta.get("sheet_number"), 1)),
        sheet_total=int(safe_num(sheet_meta.get("sheet_total"), 1)),
        discipline=safe_text(sheet_meta.get("discipline"), "CIVIL"),
        revision=safe_text(sheet_meta.get("revision"), DEFAULT_REVISION),
        issue_date=safe_text(sheet_meta.get("issue_date"), ""),
    )
    _draw_box(layout, view_x0, view_y0, view_x1, view_y1, layer="SHEET")
    add_text(layout, "MODEL SPACE VIEW", view_x0, view_y1 + 4.0, 2.6, "TITLE", style="CIVIL-BOLD")
    add_text(layout, "Canonical geometry, grading, drainage, and utilities are shown in model space.", view_x0 + 56.0, view_y1 + 4.0, 2.3, "ANNO")
    _draw_scale_bar(layout, 30.0, 36.0, scale_ft_per_in)
    _draw_north_arrow_sheet(layout, 370.0, 30.0, size=16.0)
    _draw_site_plan_detailing(layout, plan, actions, view_x0, view_y0, view_x1, view_y1)
    if bbox is not None:
        min_x, min_y, max_x, max_y = bbox
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        viewport_center_x = (view_x0 + view_x1) / 2.0
        viewport_center_y = (view_y0 + view_y1) / 2.0

        def map_to_sheet(model_x: float, model_y: float) -> Tuple[float, float]:
            return (
                viewport_center_x + (model_x - center_x) * 25.4 / max(scale_ft_per_in, 1e-9),
                viewport_center_y + (model_y - center_y) * 25.4 / max(scale_ft_per_in, 1e-9),
            )

        _draw_structure_callouts(layout, plan, map_to_sheet, view_x0, view_y0, view_x1, view_y1)


def _site_plan_summary_rows(plan: Dict[str, Any], actions: List[Dict[str, Any]]) -> List[List[str]]:
    meta = safe_dict(plan.get("meta"))
    stats = safe_dict(meta.get("stats"))
    storm = safe_dict(meta.get("storm_pipes"))
    sanitary = safe_dict(meta.get("sanitary"))
    utilities = safe_dict(meta.get("utilities"))
    drainage = safe_dict(meta.get("drainage"))
    rows = [["DISCIPLINE", "KEY VALUE", "CHECK / STATUS"]]
    rows.append(["SITE", f"Imperv {safe_num(stats.get('impervious_area_sf')):.0f} SF", safe_text(meta.get("engineering_status"), "concept").upper()])
    rows.append(["GRADING", f"Contours {safe_num(stats.get('contour_count')):.0f}", f"Spot grades {safe_num(stats.get('spot_grade_count')):.0f}"])
    rows.append(["STORM", f"Pipe {safe_num(storm.get('total_length_ft')):.1f} LF", f"Cap ratio {safe_num(storm.get('max_capacity_ratio')):.2f}"])
    rows.append(["SAN", f"Pipe {safe_num(sanitary.get('total_length_ft')):.1f} LF", f"MH {int(round(safe_num(sanitary.get('manhole_count'))))} | Svc {int(round(safe_num(sanitary.get('service_count'))))}"])
    rows.append(["UTIL", f"Routes {int(round(safe_num(utilities.get('route_count'))))}", f"Coord {safe_text(utilities.get('source'), 'canonical')}"])
    rows.append(["DRAIN", f"Structures {int(round(safe_num(drainage.get('structure_count'))))}", f"Basins {int(round(safe_num(drainage.get('pond_count'))))}"])
    return rows


def _legend_items(plan: Dict[str, Any], actions: List[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
    used_layers = {get_layer(safe_dict(action), "SITE") for action in actions}
    items: List[Tuple[str, str, str]] = []
    if "FG_CONTOUR" in used_layers:
        items.append(("line", "FG_CONTOUR", "FG / proposed"))
    if "EG_CONTOUR" in used_layers:
        items.append(("line", "EG_CONTOUR", "EG / existing"))
    if "PIPE" in used_layers:
        items.append(("line", "PIPE", "Storm pipe"))
    if "SAN" in used_layers:
        items.append(("line", "SAN", "Sanitary pipe"))
    if "UTILITY" in used_layers:
        items.append(("line", "UTILITY", "Water / utility"))
    kinds = {safe_text(item.get("kind"), "") for item in _collect_structure_callouts(plan)}
    if any("inlet" in kind for kind in kinds):
        items.append(("block", "CIVIL_INLET", "Inlet structure"))
    if any("manhole" in kind for kind in kinds):
        items.append(("block", "CIVIL_MANHOLE", "Manhole"))
    if any("outfall" in kind for kind in kinds):
        items.append(("block", "CIVIL_OUTFALL", "Outfall"))
    if any("junction" in kind or "box" in kind for kind in kinds):
        items.append(("block", "CIVIL_JUNCTION", "Junction box"))
    return items


def _draw_site_plan_legend(space, plan: Dict[str, Any], actions: List[Dict[str, Any]], x0: float, y0: float) -> None:
    add_text(space, "LEGEND", x0, y0 + 20.0, 2.3, "TITLE", style="CIVIL-BOLD")
    items = _legend_items(plan, actions)
    y = y0 + 14.0
    line_items = [(symbol, label) for item_type, symbol, label in items if item_type == "line"]
    block_items = [(symbol, label) for item_type, symbol, label in items if item_type == "block"]
    if line_items:
        add_text(space, "LINEWORK", x0, y, 1.8, "TITLE", style="CIVIL-BOLD")
        space.add_line((x0, y - 0.8), (x0 + 26.0, y - 0.8), dxfattribs={"layer": "TITLE"})
        y -= 3.4
    for symbol, label in line_items:
        space.add_line((x0, y), (x0 + 12.0, y), dxfattribs={"layer": symbol})
        add_text(space, label, x0 + 15.0, y - 1.0, 1.9, "ANNO")
        y -= 4.0
    if block_items:
        y -= 1.0
        add_text(space, "STRUCTURES", x0, y, 1.8, "TITLE", style="CIVIL-BOLD")
        space.add_line((x0, y - 0.8), (x0 + 30.0, y - 0.8), dxfattribs={"layer": "TITLE"})
        y -= 3.4
    for symbol, label in block_items:
        _insert_block(space, symbol, x0 + 6.0, y, layer="SYMBOL", scale=1.0)
        add_text(space, label, x0 + 15.0, y - 1.0, 1.9, "ANNO")
        y -= 4.0


def _collect_structure_callouts(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = safe_dict(plan.get("meta"))
    drainage = safe_dict(meta.get("drainage"))
    sanitary = safe_dict(meta.get("sanitary"))
    storm = safe_dict(meta.get("storm_pipes"))

    invert_map: Dict[str, List[float]] = {}
    for segment in safe_list(storm.get("segments")):
        rec = safe_dict(segment)
        for node_name, invert_key in (("from", "start_invert"), ("to", "end_invert")):
            name = safe_text(rec.get(node_name), "")
            if not name:
                continue
            invert_map.setdefault(name, []).append(safe_num(rec.get(invert_key)))
    for segment in safe_list(sanitary.get("segments")):
        rec = safe_dict(segment)
        for node_name, invert_key in (("start_name", "start_invert_ft"), ("end_name", "end_invert_ft")):
            name = safe_text(rec.get(node_name), "")
            if not name:
                continue
            invert_map.setdefault(name, []).append(safe_num(rec.get(invert_key)))

    callouts: List[Dict[str, Any]] = []
    for structure in safe_list(drainage.get("structures")):
        rec = safe_dict(structure)
        name = safe_text(rec.get("name"), "")
        rim = safe_num(rec.get("z"))
        inverts = invert_map.get(name, [])
        callouts.append(
            {
                "name": name or safe_text(rec.get("structure_type"), "DRAIN"),
                "label_type": "structure",
                "kind": safe_text(rec.get("object_type") or rec.get("canonical_type") or rec.get("structure_type"), "drain"),
                "x": safe_num(rec.get("x")),
                "y": safe_num(rec.get("y")),
                "rim_elev_ft": rim,
                "invert_in_ft": min(inverts) if inverts else None,
                "invert_out_ft": max(inverts) if len(inverts) > 1 else (inverts[0] if inverts else None),
                "symbol": "CIVIL_OUTFALL" if "outfall" in safe_text(rec.get("structure_type"), "").lower() else ("CIVIL_INLET" if "inlet" in safe_text(rec.get("structure_type"), "").lower() else "CIVIL_JUNCTION"),
            }
        )
    for manhole in safe_list(sanitary.get("manholes")):
        rec = safe_dict(manhole)
        name = safe_text(rec.get("name"), "")
        inverts = invert_map.get(name, [])
        callouts.append(
            {
                "name": name or "SMH",
                "label_type": "structure",
                "kind": "sanitary_manhole",
                "x": safe_num(rec.get("x")),
                "y": safe_num(rec.get("y")),
                "rim_elev_ft": safe_num(rec.get("rim_elev_ft")),
                "invert_in_ft": min(inverts) if inverts else None,
                "invert_out_ft": max(inverts) if len(inverts) > 1 else (inverts[0] if inverts else None),
                "symbol": "CIVIL_MANHOLE",
            }
        )
    return [callout for callout in callouts if callout.get("name")]


def _draw_structure_callouts(space, plan: Dict[str, Any], map_to_sheet, view_x0: float, view_y0: float, view_x1: float, view_y1: float) -> None:
    callouts = _collect_structure_callouts(plan)
    occupied: List[Tuple[float, float]] = []
    for idx, callout in enumerate(callouts):
        anchor_x, anchor_y = map_to_sheet(callout["x"], callout["y"])
        side = 1.0 if anchor_x <= (view_x0 + view_x1) / 2.0 else -1.0
        target_x = anchor_x + side * 18.0
        target_y = anchor_y + (12.0 if idx % 2 == 0 else -12.0)
        target_x = max(view_x0 + 8.0, min(view_x1 - 52.0, target_x))
        target_y = max(view_y0 + 10.0, min(view_y1 - 12.0, target_y))
        _, text_height, text_layer = _label_text("structure", "")
        while any(abs(target_x - ox) < 28.0 and abs(target_y - oy) < 9.0 for ox, oy in occupied):
            target_y += 7.0 if target_y < (view_y0 + view_y1) / 2.0 else -7.0
            target_y = max(view_y0 + 10.0, min(view_y1 - 12.0, target_y))
        occupied.append((target_x, target_y))

        elbow_x = anchor_x + side * 8.0
        _insert_block(space, safe_text(callout.get("symbol"), "CIVIL_JUNCTION"), anchor_x, anchor_y, layer="STRUCTURE", scale=0.7)
        space.add_line((anchor_x, anchor_y), (elbow_x, anchor_y), dxfattribs={"layer": "STRUCTURE"})
        space.add_line((elbow_x, anchor_y), (target_x, target_y), dxfattribs={"layer": "STRUCTURE"})

        kind = safe_text(callout.get("kind"), "").replace("_", " ").upper()
        header, _, _ = _label_text("structure", f"{safe_text(callout.get('name'))} ({kind})")
        add_text(space, header, target_x, target_y + 4.3, 1.85, text_layer, style="CIVIL-BOLD")
        rim = safe_num(callout.get("rim_elev_ft"))
        add_text(space, f"RIM {rim:.2f}", target_x, target_y + 1.1, text_height, text_layer)
        invert_in = callout.get("invert_in_ft")
        invert_out = callout.get("invert_out_ft")
        if invert_in is not None and invert_out is not None and abs(safe_num(invert_in) - safe_num(invert_out)) > 1e-6:
            add_text(space, f"INV IN {safe_num(invert_in):.2f}", target_x, target_y - 2.1, text_height, text_layer)
            add_text(space, f"INV OUT {safe_num(invert_out):.2f}", target_x, target_y - 5.3, text_height, text_layer)
        elif invert_in is not None:
            add_text(space, f"INV {safe_num(invert_in):.2f}", target_x, target_y - 2.1, text_height, text_layer)


def _draw_site_plan_detailing(space, plan: Dict[str, Any], actions: List[Dict[str, Any]], view_x0: float, view_y0: float, view_x1: float, view_y1: float) -> None:
    rows = _site_plan_summary_rows(plan, actions)
    _draw_table_grid(space, 24.0, 266.0, [42.0, 62.0, 84.0], 5.0, rows, title="PLAN SUMMARY")
    _draw_site_plan_legend(space, plan, actions, 245.0, 268.0)
    notes = [
        "1. VERIFY UTILITY TIE-IN AND HORIZONTAL SEPARATION IN FINAL DESIGN.",
        "2. PROFILE AND SECTION SHEETS CONTROL PIPE INVERT AND SURFACE GRADE INTENT.",
        "3. GENERATED SHEETS REPRESENT CANONICAL PROJECT STATE AT EXPORT TIME.",
    ]
    add_text(space, "GENERAL NOTES", 24.0, 28.0, 2.3, "TITLE", style="CIVIL-BOLD")
    note_y = 23.0
    for note in notes:
        add_text(space, note, 24.0, note_y, 1.9, "ANNO")
        note_y -= 4.0


def _profile_values(profile: Dict[str, Any]) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]], List[Tuple[float, float]]]:
    existing: List[Tuple[float, float]] = []
    proposed: List[Tuple[float, float]] = []
    pipe: List[Tuple[float, float]] = []
    for station in safe_list(profile.get("stations")):
        rec = safe_dict(station)
        station_ft = safe_num(rec.get("station_ft"))
        existing.append((station_ft, safe_num(rec.get("existing_elev_ft"))))
        proposed.append((station_ft, safe_num(rec.get("proposed_elev_ft"))))
        if "pipe_invert_ft" in rec:
            pipe.append((station_ft, safe_num(rec.get("pipe_invert_ft"))))
    return existing, proposed, pipe


def _place_label(clearances: List[Tuple[float, float]], x: float, y: float, min_dx: float = 18.0, min_dy: float = 5.0) -> Tuple[float, float]:
    ny = y
    while any(abs(x - px) < min_dx and abs(ny - py) < min_dy for px, py in clearances):
        ny += min_dy
    clearances.append((x, ny))
    return x, ny


def _draw_grid(space, x0: float, y0: float, x1: float, y1: float, x_values: Sequence[float], y_values: Sequence[float], map_x, map_y) -> None:
    for value in x_values:
        x = map_x(value)
        space.add_line((x, y0), (x, y1), dxfattribs={"layer": "GRID"})
    for value in y_values:
        y = map_y(value)
        space.add_line((x0, y), (x1, y), dxfattribs={"layer": "GRID"})


def _profile_structure_marks(plan: Dict[str, Any], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    explicit_marks = [safe_dict(item) for item in safe_list(profile.get("structure_marks")) if safe_dict(item)]
    if explicit_marks:
        return explicit_marks
    meta = safe_dict(plan.get("meta"))
    alignment_type = safe_text(profile.get("alignment_type"), "")
    stations = [safe_dict(item) for item in safe_list(profile.get("stations"))]
    if len(stations) < 2:
        return []
    marks: List[Dict[str, Any]] = []
    if alignment_type == "storm_pipe":
        storm = safe_dict(meta.get("storm_pipes"))
        for segment in safe_list(storm.get("segments")):
            rec = safe_dict(segment)
            name = safe_text(rec.get("pipe"), "")
            if name and name not in safe_text(profile.get("alignment_name"), ""):
                continue
            for label, target_station, rim, invert in (
                (safe_text(rec.get("from"), "UP"), safe_num(stations[0].get("station_ft")), safe_num(rec.get("hgl_start"), 0.0), safe_num(rec.get("start_invert"), 0.0)),
                (safe_text(rec.get("to"), "DN"), safe_num(stations[-1].get("station_ft")), safe_num(rec.get("hgl_end"), 0.0), safe_num(rec.get("end_invert"), 0.0)),
            ):
                marks.append({"label": label, "station_ft": target_station, "rim_elev_ft": rim, "invert_ft": invert})
            break
    elif alignment_type == "sanitary_pipe":
        sanitary = safe_dict(meta.get("sanitary"))
        for mh in safe_list(sanitary.get("manholes")):
            rec = safe_dict(mh)
            mark_station = None
            for station in stations:
                point = safe_list(station.get("point"))
                if len(point) < 2:
                    continue
                dx = safe_num(point[0]) - safe_num(rec.get("x"))
                dy = safe_num(point[1]) - safe_num(rec.get("y"))
                if (dx * dx + dy * dy) ** 0.5 <= 8.0:
                    mark_station = safe_num(station.get("station_ft"))
                    break
            if mark_station is not None:
                marks.append({"label": safe_text(rec.get("name"), "SMH"), "station_ft": mark_station, "rim_elev_ft": safe_num(rec.get("rim_elev_ft"), 0.0)})
    if alignment_type == "roadway":
        for idx in (0, len(stations) - 1):
            station = stations[idx]
            marks.append({"label": "CL", "station_ft": safe_num(station.get("station_ft")), "rim_elev_ft": safe_num(station.get("proposed_elev_ft"), 0.0)})
    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for mark in marks:
        key = (safe_text(mark.get("label")), int(round(safe_num(mark.get("station_ft")))))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(mark)
    return deduped


def _pipe_band_records(plan: Dict[str, Any], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    explicit_records = [safe_dict(item) for item in safe_list(profile.get("pipe_band_records")) if safe_dict(item)]
    if explicit_records:
        return explicit_records
    meta = safe_dict(plan.get("meta"))
    alignment_type = safe_text(profile.get("alignment_type"), "")
    stations = [safe_dict(item) for item in safe_list(profile.get("stations"))]
    if len(stations) < 2:
        return []
    if alignment_type == "storm_pipe":
        storm = safe_dict(meta.get("storm_pipes"))
        segments = [safe_dict(item) for item in safe_list(storm.get("segments")) if safe_dict(item)]
        if not segments:
            return []
        segment = max(segments, key=lambda item: safe_num(item.get("length_ft"), 0.0))
        assumed = any(
            key not in segment or segment.get(key) in (None, "")
            for key in ("diameter_in", "slope_pct", "start_invert", "end_invert", "flow_cfs", "capacity_cfs", "capacity_ratio")
        )
        return [
            {
                "start_station_ft": safe_num(stations[0].get("station_ft")),
                "end_station_ft": safe_num(stations[-1].get("station_ft")),
                "start_station_text": safe_text(stations[0].get("station_text"), _station_text(safe_num(stations[0].get("station_ft")))),
                "end_station_text": safe_text(stations[-1].get("station_text"), _station_text(safe_num(stations[-1].get("station_ft")))),
                "diameter_in": safe_num(segment.get("diameter_in")),
                "slope_pct": safe_num(segment.get("slope_pct")),
                "from_structure": safe_text(segment.get("from"), ""),
                "to_structure": safe_text(segment.get("to"), ""),
                "rim_in_ft": 0.0,
                "rim_out_ft": 0.0,
                "invert_in_ft": safe_num(segment.get("start_invert")),
                "invert_out_ft": safe_num(segment.get("end_invert")),
                "cover_in_ft": safe_num(segment.get("cover_start_ft")),
                "cover_out_ft": safe_num(segment.get("cover_end_ft")),
                "flow_cfs": safe_num(segment.get("flow_cfs")),
                "capacity_cfs": safe_num(segment.get("capacity_cfs")),
                "capacity_ratio": safe_num(segment.get("capacity_ratio")),
                "assumed": assumed,
            }
        ]
    if alignment_type == "sanitary_pipe":
        sanitary = safe_dict(meta.get("sanitary"))
        segments = [safe_dict(item) for item in safe_list(sanitary.get("segments")) if safe_dict(item) and safe_text(item.get("segment_role")) == "main"]
        if not segments:
            return []
        segment = segments[0]
        slope_pct = safe_num(segment.get("slope_pct"))
        if abs(slope_pct) <= 1e-9 and "slope_ft_ft" in segment:
            slope_pct = safe_num(segment.get("slope_ft_ft")) * 100.0
        assumed = any(
            key not in segment or segment.get(key) in (None, "")
            for key in ("diameter_in", "start_invert_ft", "end_invert_ft")
        ) or ("flow_cfs" not in segment or "capacity_cfs" not in segment or "capacity_ratio" not in segment)
        return [
            {
                "start_station_ft": safe_num(stations[0].get("station_ft")),
                "end_station_ft": safe_num(stations[-1].get("station_ft")),
                "start_station_text": safe_text(stations[0].get("station_text"), _station_text(safe_num(stations[0].get("station_ft")))),
                "end_station_text": safe_text(stations[-1].get("station_text"), _station_text(safe_num(stations[-1].get("station_ft")))),
                "diameter_in": safe_num(segment.get("diameter_in")),
                "slope_pct": slope_pct,
                "from_structure": safe_text(segment.get("start_name"), ""),
                "to_structure": safe_text(segment.get("end_name"), ""),
                "rim_in_ft": 0.0,
                "rim_out_ft": 0.0,
                "invert_in_ft": safe_num(segment.get("start_invert_ft")),
                "invert_out_ft": safe_num(segment.get("end_invert_ft")),
                "cover_in_ft": safe_num(segment.get("cover_start_ft")),
                "cover_out_ft": safe_num(segment.get("cover_end_ft")),
                "flow_cfs": safe_num(segment.get("flow_cfs")),
                "capacity_cfs": safe_num(segment.get("capacity_cfs")),
                "capacity_ratio": safe_num(segment.get("capacity_ratio")),
                "assumed": assumed,
            }
        ]
    return []


def _band_text_x(left: float, right: float, text: str) -> float:
    width = max(right - left, 1.0)
    estimated = max(len(safe_text(text, "")) * 0.75, 0.0)
    centered = (left + right) / 2.0 - estimated / 2.0
    return max(left + min(width * 0.06, 3.0), centered)


def _band_cell_left(left: float, right: float, text: str, padding: float = 1.6) -> float:
    width = max(right - left, 1.0)
    estimated = max(len(safe_text(text, "")) * 0.72, 0.0)
    return min(left + padding, right - estimated - 0.8 if estimated < width else left + padding)


def _section_feature_label(feature_type: str) -> str:
    return {
        "travel_lane": "PAVEMENT",
        "curb_gutter": "CURB & GUTTER",
        "sidewalk": "SIDEWALK",
        "pipe_centerline": "PIPE CL",
        "section_edge": "TIE-IN",
    }.get(safe_text(feature_type), safe_text(feature_type).replace("_", " ").upper() or "SECTION")


def _edge_condition_label(kind: str) -> str:
    return {
        "roadway": "ROAD EDGE",
        "building_pad": "PAD TIE-IN",
        "ada_path": "ADA PATH",
        "fire_lane": "FIRE LANE",
        "parking_field": "PARKING EDGE",
        "retaining_sensitive": "RETAINING",
    }.get(safe_text(kind), safe_text(kind).replace("_", " ").upper() or "EDGE")


def _draw_profile_bands(space, profile: Dict[str, Any], graph_x0: float, graph_y0: float, graph_x1: float, band_top: float, map_x, map_y) -> None:
    stations = [safe_dict(item) for item in safe_list(profile.get("stations"))]
    if not stations:
        return
    include_pipe = any("pipe_invert_ft" in rec for rec in stations)
    band_heights = [5.5, 5.5, 5.5, 5.5, 5.5] if include_pipe else [5.5, 5.5, 5.5, 5.5]
    left_col = 24.0
    total_h = sum(band_heights)
    _draw_box(space, graph_x0, band_top - total_h, graph_x1, band_top, layer="SHEET")
    space.add_line((graph_x0 + left_col, band_top - total_h), (graph_x0 + left_col, band_top), dxfattribs={"layer": "SHEET"})
    running_y = band_top
    for height in band_heights[:-1]:
        running_y -= height
        space.add_line((graph_x0, running_y), (graph_x1, running_y), dxfattribs={"layer": "SHEET"})
    rows = [
        ("STATION", lambda rec: safe_text(rec.get("station_text"), "")),
        ("EG", lambda rec: f"{safe_num(rec.get('existing_elev_ft')):.2f}"),
        ("FG", lambda rec: f"{safe_num(rec.get('proposed_elev_ft')):.2f}"),
        ("DELTA", lambda rec: f"{safe_num(rec.get('proposed_elev_ft')) - safe_num(rec.get('existing_elev_ft')):+.2f}"),
    ]
    if include_pipe:
        rows.append(
            (
                "COVER",
                lambda rec: f"{safe_num(rec.get('proposed_elev_ft')) - safe_num(rec.get('pipe_invert_ft')):.2f}"
                if "pipe_invert_ft" in rec
                else "--",
            )
        )
    current_top = band_top
    for idx, (label, formatter) in enumerate(rows):
        row_y = current_top - band_heights[idx] + 1.7
        add_text(space, label, graph_x0 + 2.0, row_y, 1.8, "TITLE", style="CIVIL-BOLD")
        station_edges = [map_x(safe_num(station.get("station_ft"))) for station in stations]
        for station_idx, station in enumerate(stations):
            station_ft = safe_num(station.get("station_ft"))
            x = map_x(station_ft)
            space.add_line((x, current_top - band_heights[idx]), (x, current_top), dxfattribs={"layer": "SHEET"})
            left = graph_x0 + left_col if station_idx == 0 else (station_edges[station_idx - 1] + x) / 2.0
            right = graph_x1 if station_idx == len(stations) - 1 else (x + station_edges[station_idx + 1]) / 2.0
            value = formatter(station)
            add_text(space, value, _band_text_x(left, right, value), row_y, 1.45 if len(value) > 12 else 1.55, "ANNO", style="CIVIL-NARROW" if len(value) > 12 else "CIVIL")
        current_top -= band_heights[idx]


def _draw_pipe_profile_bands(space, plan: Dict[str, Any], profile: Dict[str, Any], graph_x0: float, graph_x1: float, band_bottom: float, map_x) -> None:
    records = _pipe_band_records(plan, profile)
    if not records:
        return
    row_height = 4.7
    header_h = 5.2
    label_col = 25.0
    rows = [
        ("STA", "pair"),
        ("STRUCT", "pair"),
        ("RIM", "pair"),
        ("INV", "pair"),
        ("DIA", "single"),
        ("SLOPE", "single"),
        ("COVER", "pair"),
        ("FLOW/CAP", "single"),
        ("RATIO", "single"),
    ]
    total_h = header_h + row_height * len(rows)
    _draw_box(space, graph_x0, band_bottom, graph_x1, band_bottom + total_h, layer="SHEET")
    space.add_line((graph_x0 + label_col, band_bottom), (graph_x0 + label_col, band_bottom + total_h), dxfattribs={"layer": "SHEET"})
    header_y = band_bottom + total_h - header_h
    space.add_line((graph_x0, header_y), (graph_x1, header_y), dxfattribs={"layer": "SHEET"})
    for idx in range(1, len(rows)):
        y = header_y - idx * row_height
        space.add_line((graph_x0, y), (graph_x1, y), dxfattribs={"layer": "SHEET"})
    for idx in (4, 6):
        y = header_y - idx * row_height
        space.add_line((graph_x0, y), (graph_x1, y), dxfattribs={"layer": "TITLE"})
    system_label = safe_text(profile.get("source_system"), safe_text(profile.get("alignment_type"), "PIPE")).replace("_", " ").upper()
    add_text(space, f"{system_label} DATA BAND", graph_x0 + 2.0, header_y + 1.8, 2.0, "TITLE", style="CIVIL-BOLD")
    add_text(space, "FROM", graph_x0 + label_col + 6.0, header_y + 1.8, 1.55, "ANNO", style="CIVIL-BOLD")
    add_text(space, "TO", graph_x0 + label_col + 48.0, header_y + 1.8, 1.55, "ANNO", style="CIVIL-BOLD")
    add_text(space, "PIPE DATA", graph_x1 - 30.0, header_y + 1.8, 1.5, "ANNO", style="CIVIL-NARROW")
    space.add_line((graph_x0, header_y + 0.6), (graph_x1, header_y + 0.6), dxfattribs={"layer": "TITLE"})
    for idx, (label, _mode) in enumerate(rows):
        y = header_y - (idx + 0.72) * row_height
        add_text(space, label, graph_x0 + 1.5, y, 1.55, "TITLE", style="CIVIL-BOLD")

    for record in records:
        start_station = safe_num(record.get("start_station_ft"))
        end_station = safe_num(record.get("end_station_ft"))
        left_x = map_x(start_station)
        right_x = map_x(end_station)
        band_left = min(left_x, right_x)
        band_right = max(left_x, right_x)
        band_mid = (band_left + band_right) / 2.0
        for x in (band_left, band_right):
            space.add_line((x, band_bottom), (x, band_bottom + total_h), dxfattribs={"layer": "SHEET"})
        if band_right - band_left > 24.0:
            space.add_line((band_mid, band_bottom), (band_mid, header_y), dxfattribs={"layer": "GRID"})
        left_cell = (band_left, band_mid)
        right_cell = (band_mid, band_right)
        row_values = [
            (safe_text(record.get("start_station_text")), safe_text(record.get("end_station_text")), None),
            (safe_text(record.get("from_structure")), safe_text(record.get("to_structure")), None),
            (f'{safe_num(record.get("rim_in_ft")):.2f}', f'{safe_num(record.get("rim_out_ft")):.2f}', None),
            (f'{safe_num(record.get("invert_in_ft")):.2f}', f'{safe_num(record.get("invert_out_ft")):.2f}', None),
            (None, None, f'{safe_num(record.get("diameter_in")):.0f}"'),
            (None, None, f'{safe_num(record.get("slope_pct")):+.2f}%'),
            (f'{safe_num(record.get("cover_in_ft")):.2f}', f'{safe_num(record.get("cover_out_ft")):.2f}', None),
            (None, None, f'{safe_num(record.get("flow_cfs")):.2f} / {safe_num(record.get("capacity_cfs")):.2f} CFS'),
            (None, None, f'{safe_num(record.get("capacity_ratio")):.2f}' + (" ASSUMED" if bool(record.get("assumed")) else "")),
        ]
        for idx, (left_value, right_value, single_value) in enumerate(row_values):
            y = header_y - (idx + 0.72) * row_height
            if single_value is not None:
                add_text(
                    space,
                    single_value,
                    _band_cell_left(band_left, band_right, single_value),
                    y,
                    1.32 if len(single_value) > 20 else 1.48,
                    "ANNO",
                    style="CIVIL-NARROW" if len(single_value) > 16 else "CIVIL",
                )
                continue
            if left_value is not None:
                add_text(
                    space,
                    left_value,
                    _band_cell_left(left_cell[0], left_cell[1], left_value),
                    y,
                    1.4 if len(left_value) > 14 else 1.5,
                    "ANNO",
                    style="CIVIL-NARROW" if len(left_value) > 12 else "CIVIL",
                )
            if right_value is not None:
                add_text(
                    space,
                    right_value,
                    _band_cell_left(right_cell[0], right_cell[1], right_value),
                    y,
                    1.4 if len(right_value) > 14 else 1.5,
                    "ANNO",
                    style="CIVIL-NARROW" if len(right_value) > 12 else "CIVIL",
                )


def _feature_runs(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    context_runs = [safe_dict(item) for item in safe_list(safe_dict(section.get("section_context")).get("feature_runs")) if safe_dict(item)]
    if context_runs:
        return context_runs
    runs: List[Dict[str, Any]] = []
    rows = _section_offsets(section)
    current: Optional[Dict[str, Any]] = None
    for offset, _eg, fg, _pipe, feature_type in rows:
        feature = safe_text(feature_type, "section_edge")
        if current is None or current["feature_type"] != feature:
            if current is not None:
                runs.append(current)
            current = {
                "feature_type": feature,
                "start_offset_ft": offset,
                "end_offset_ft": offset,
                "avg_fg_ft": fg,
                "count": 1,
            }
        else:
            current["end_offset_ft"] = offset
            current["avg_fg_ft"] += fg
            current["count"] += 1
    if current is not None:
        current["avg_fg_ft"] = safe_num(current.get("avg_fg_ft")) / max(int(current.get("count", 1)), 1)
        runs.append(current)
    return runs


def _draw_profile_layout(doc, plan: Dict[str, Any], profile: Dict[str, Any], sheet_index: int, sheet_meta: Optional[Dict[str, Any]] = None) -> None:
    name = _make_unique_layout_name(doc, f"PROFILE {sheet_index}")
    layout = _fresh_layout(doc, name)
    stations_existing, stations_proposed, stations_pipe = _profile_values(profile)
    if not stations_existing or not stations_proposed:
        return

    graph_x0, graph_y0, graph_x1, graph_y1 = 28.0, 82.0, 390.0, 244.0
    graph_w = graph_x1 - graph_x0
    graph_h = graph_y1 - graph_y0
    station_min = min(value[0] for value in stations_proposed)
    station_max = max(value[0] for value in stations_proposed)
    station_span = max(station_max - station_min, 1.0)

    elevations = [value[1] for value in stations_existing + stations_proposed + stations_pipe]
    elev_interval = _nice_interval(max(max(elevations) - min(elevations), 1.0), 6)
    elev_min = _nice_floor(min(elevations) - elev_interval * 0.5, elev_interval)
    elev_max = _nice_ceil(max(elevations) + elev_interval * 0.5, elev_interval)
    elev_span = max(elev_max - elev_min, elev_interval)

    h_scale = _pick_engineering_scale_ft_per_in(station_span, 1.0, graph_w, graph_h)
    desired_ve = max(safe_num(profile.get("vertical_exaggeration"), 5.0), 1.0)
    target_v_scale = max(h_scale / desired_ve, 0.25)
    min_v_scale = elev_span * 25.4 / max(graph_h, 1.0)
    v_scale = max(target_v_scale, min_v_scale)
    vertical_exaggeration = h_scale / max(v_scale, 1e-9)

    def map_x(station_ft: float) -> float:
        return graph_x0 + (station_ft - station_min) * 25.4 / h_scale

    def map_y(elev_ft: float) -> float:
        return graph_y0 + (elev_ft - elev_min) * 25.4 / v_scale

    station_interval = _nice_interval(station_span, 6)
    station_ticks: List[float] = []
    tick = _nice_floor(station_min, station_interval)
    while tick <= station_max + 1e-9:
        station_ticks.append(round(tick, 6))
        tick += station_interval

    elev_ticks: List[float] = []
    tick = elev_min
    while tick <= elev_max + 1e-9:
        elev_ticks.append(round(tick, 6))
        tick += elev_interval

    scale_label = f'H {_format_scale(h_scale)}  V {_format_scale(v_scale)}  VE {vertical_exaggeration:.1f}x'
    sheet_meta = safe_dict(sheet_meta)
    _draw_title_block(
        layout,
        plan,
        safe_text(profile.get("sheet_title"), "PROFILE"),
        safe_text(profile.get("sheet_name"), name),
        scale_label,
        subtitle=safe_text(profile.get("alignment_name"), ""),
        sheet_code=safe_text(sheet_meta.get("sheet_code"), f"C-{300 + sheet_index:03d}"),
        sheet_number=int(safe_num(sheet_meta.get("sheet_number"), sheet_index)),
        sheet_total=int(safe_num(sheet_meta.get("sheet_total"), sheet_index)),
        discipline=safe_text(sheet_meta.get("discipline"), "CIVIL"),
        revision=safe_text(sheet_meta.get("revision"), DEFAULT_REVISION),
        issue_date=safe_text(sheet_meta.get("issue_date"), ""),
    )
    _draw_box(layout, graph_x0, graph_y0, graph_x1, graph_y1, layer="AXIS")
    _draw_grid(layout, graph_x0, graph_y0, graph_x1, graph_y1, station_ticks, elev_ticks, map_x, map_y)

    layout.add_line((graph_x0, graph_y0), (graph_x1, graph_y0), dxfattribs={"layer": "AXIS"})
    layout.add_line((graph_x0, graph_y0), (graph_x0, graph_y1), dxfattribs={"layer": "AXIS"})

    existing_pts = [(map_x(sta), map_y(elev)) for sta, elev in stations_existing]
    proposed_pts = [(map_x(sta), map_y(elev)) for sta, elev in stations_proposed]
    _draw_polyline_points(layout, existing_pts, "EG_CONTOUR")
    _draw_polyline_points(layout, proposed_pts, "FG_CONTOUR")
    if stations_pipe:
        pipe_pts = [(map_x(sta), map_y(elev)) for sta, elev in stations_pipe]
        pipe_layer = "SAN" if "sanitary" in safe_text(profile.get("alignment_type"), "").lower() else "PIPE"
        _draw_polyline_points(layout, pipe_pts, pipe_layer)

    structure_marks = _profile_structure_marks(plan, profile)
    for mark in structure_marks:
        station_ft = safe_num(mark.get("station_ft"))
        x = map_x(station_ft)
        layout.add_line((x, graph_y0), (x, graph_y1), dxfattribs={"layer": "STRUCTURE"})
        add_text(layout, safe_text(mark.get("label"), "STR"), x - 4.0, graph_y1 + 3.0, 2.0, "STRUCTURE", style="CIVIL-BOLD")
        if safe_num(mark.get("rim_elev_ft"), 0.0):
            add_text(layout, f"RIM {safe_num(mark.get('rim_elev_ft')):.2f}", x - 6.0, graph_y1 - 6.0, 1.7, "ANNO")
        if safe_num(mark.get("invert_ft"), 0.0):
            add_text(layout, f"INV {safe_num(mark.get('invert_ft')):.2f}", x - 6.0, graph_y0 + 4.0, 1.7, "ANNO")

    label_clearances: List[Tuple[float, float]] = []
    station_records = [safe_dict(item) for item in safe_list(profile.get("stations"))]
    step = 1 if len(station_records) <= 7 else 2
    for idx, station in enumerate(station_records):
        if idx % step != 0 and idx not in {0, len(station_records) - 1}:
            continue
        station_ft = safe_num(station.get("station_ft"))
        x = map_x(station_ft)
        layout.add_line((x, graph_y0), (x, graph_y0 - 3.0), dxfattribs={"layer": "AXIS"})
        add_text(layout, safe_text(station.get("station_text"), f"{station_ft:.0f}"), x - 5.0, graph_y0 - 8.0, 2.2, "ANNO")

        fg = safe_num(station.get("proposed_elev_ft"))
        eg = safe_num(station.get("existing_elev_ft"))
        lx, ly = _place_label(label_clearances, x + 2.0, map_y(fg) + 2.5)
        add_text(layout, f"FG {fg:.2f}", lx, ly, 2.0, "ANNO")
        if idx in {0, len(station_records) - 1}:
            lx, ly = _place_label(label_clearances, x + 2.0, map_y(eg) - 4.0)
            add_text(layout, f"EG {eg:.2f}", lx, ly, 2.0, "ANNO")
        if "pipe_invert_ft" in station:
            invert = safe_num(station.get("pipe_invert_ft"))
            lx, ly = _place_label(label_clearances, x + 2.0, map_y(invert) - 4.5)
            add_text(layout, f"INV {invert:.2f}", lx, ly, 2.0, "ANNO")

    for tick_value in elev_ticks:
        y = map_y(tick_value)
        layout.add_line((graph_x0 - 3.0, y), (graph_x0, y), dxfattribs={"layer": "AXIS"})
        add_text(layout, f"{tick_value:.1f}", graph_x0 - 18.0, y - 1.0, 2.0, "ANNO")

    fg_points = stations_proposed
    for idx in range(len(fg_points) - 1):
        sta0, elev0 = fg_points[idx]
        sta1, elev1 = fg_points[idx + 1]
        run = max(sta1 - sta0, 1e-9)
        slope = (elev1 - elev0) / run * 100.0
        mx = map_x((sta0 + sta1) / 2.0)
        my = map_y((elev0 + elev1) / 2.0)
        lx, ly = _place_label(label_clearances, mx - 4.0, my + 6.0)
        add_text(layout, f"FG {slope:+.2f}%", lx, ly, 1.9, "ANNO")

    if stations_pipe:
        for idx in range(len(stations_pipe) - 1):
            sta0, elev0 = stations_pipe[idx]
            sta1, elev1 = stations_pipe[idx + 1]
            run = max(sta1 - sta0, 1e-9)
            slope = (elev1 - elev0) / run * 100.0
            mx = map_x((sta0 + sta1) / 2.0)
            my = map_y((elev0 + elev1) / 2.0)
            lx, ly = _place_label(label_clearances, mx - 4.0, my - 7.0)
            prefix = "SAN" if "sanitary" in safe_text(profile.get("alignment_type"), "").lower() else "PIPE"
            add_text(layout, f"{prefix} {slope:+.2f}%", lx, ly, 1.9, "ANNO")

    add_text(layout, "STATION (FT)", (graph_x0 + graph_x1) / 2.0 - 12.0, graph_y0 - 14.0, 2.4, "TITLE", style="CIVIL-BOLD")
    add_text(layout, "ELEVATION (FT)", graph_x0 - 28.0, (graph_y0 + graph_y1) / 2.0 - 10.0, 2.4, "TITLE", rotation=90.0, style="CIVIL-BOLD")

    legend_y = graph_y1 + 4.0
    layout.add_line((graph_x1 - 95.0, legend_y), (graph_x1 - 80.0, legend_y), dxfattribs={"layer": "EG_CONTOUR"})
    add_text(layout, "EG", graph_x1 - 77.0, legend_y - 1.0, 2.1, "ANNO")
    layout.add_line((graph_x1 - 60.0, legend_y), (graph_x1 - 45.0, legend_y), dxfattribs={"layer": "FG_CONTOUR"})
    add_text(layout, "FG", graph_x1 - 42.0, legend_y - 1.0, 2.1, "ANNO")
    if stations_pipe:
        pipe_layer = "SAN" if "sanitary" in safe_text(profile.get("alignment_type"), "").lower() else "PIPE"
        layout.add_line((graph_x1 - 25.0, legend_y), (graph_x1 - 10.0, legend_y), dxfattribs={"layer": pipe_layer})
        add_text(layout, "PIPE", graph_x1 - 7.0, legend_y - 1.0, 2.1, "ANNO")
    _draw_profile_bands(layout, profile, graph_x0, graph_y0, graph_x1, 74.0, map_x, map_y)
    if stations_pipe:
        _draw_pipe_profile_bands(layout, plan, profile, graph_x0, graph_x1, 48.0, map_x)
    note_rows = [["ITEM", "VALUE", "COMMENT"]]
    note_rows.append(["ALIGN", safe_text(profile.get("source"), "canonical").upper(), safe_text(profile.get("alignment_name"), "")])
    note_rows.append(["RANGE", f"{station_min:.0f} - {station_max:.0f} FT", f"VE {vertical_exaggeration:.1f}X"])
    if stations_pipe:
        note_rows.append(["PIPE", f"{len(stations_pipe)} sampled pts", "Invert and slope shown"])
    else:
        note_rows.append(["SURFACE", f"{len(station_records)} sampled pts", "EG/FG only"])
    _draw_table_grid(layout, 28.0, 48.0, [28.0, 42.0, 82.0], 5.2, note_rows, title="PROFILE DATA")


def _section_offsets(section: Dict[str, Any]) -> List[Tuple[float, float, float, Optional[float], str]]:
    rows: List[Tuple[float, float, float, Optional[float], str]] = []
    samples = [safe_dict(item) for item in safe_list(section.get("samples"))]
    width = max(safe_num(section.get("width_ft")), 1.0)
    for idx, sample in enumerate(samples):
        if "offset_ft" in sample:
            offset_ft = safe_num(sample.get("offset_ft"))
        else:
            offset_ft = -width / 2.0 + width * (idx / max(len(samples) - 1, 1))
        rows.append(
            (
                offset_ft,
                safe_num(sample.get("existing_elev_ft")),
                safe_num(sample.get("proposed_elev_ft")),
                safe_num(sample.get("pipe_invert_ft")) if "pipe_invert_ft" in sample else None,
                safe_text(sample.get("feature_type"), ""),
            )
        )
    return rows


def _chunks(items: Sequence[Any], size: int) -> List[List[Any]]:
    return [list(items[idx : idx + size]) for idx in range(0, len(items), size)]


def _draw_cross_section_panel(space, section: Dict[str, Any], panel: Tuple[float, float, float, float], h_scale: float, v_scale: float) -> None:
    x0, y0, x1, y1 = panel
    _draw_box(space, x0, y0, x1, y1, layer="SHEET")
    add_text(space, safe_text(section.get("name"), "SECTION"), x0 + 3.0, y1 - 7.0, 2.8, "TITLE", style="CIVIL-BOLD")
    add_text(space, f"STA {safe_text(section.get('station_text'), '')}", x0 + 3.0, y1 - 13.0, 2.2, "ANNO")

    graph_x0, graph_y0 = x0 + 12.0, y0 + 12.0
    graph_x1, graph_y1 = x1 - 8.0, y1 - 20.0
    graph_w = graph_x1 - graph_x0
    graph_h = graph_y1 - graph_y0
    rows = _section_offsets(section)
    if len(rows) < 2:
        return

    offsets = [row[0] for row in rows]
    eg_vals = [row[1] for row in rows]
    fg_vals = [row[2] for row in rows]
    pipe_vals = [row[3] for row in rows if row[3] is not None]
    all_elevs = eg_vals + fg_vals + pipe_vals
    elev_interval = _nice_interval(max(max(all_elevs) - min(all_elevs), 1.0), 4)
    elev_min = _nice_floor(min(all_elevs) - elev_interval * 0.5, elev_interval)
    elev_max = _nice_ceil(max(all_elevs) + elev_interval * 0.5, elev_interval)
    elev_span = max(elev_max - elev_min, elev_interval)

    def map_x(offset_ft: float) -> float:
        return graph_x0 + (offset_ft - min(offsets)) * 25.4 / h_scale

    def map_y(elev_ft: float) -> float:
        return graph_y0 + (elev_ft - elev_min) * 25.4 / v_scale

    x_interval = _nice_interval(max(max(offsets) - min(offsets), 1.0), 4)
    x_ticks: List[float] = []
    tick = _nice_floor(min(offsets), x_interval)
    while tick <= max(offsets) + 1e-9:
        x_ticks.append(round(tick, 6))
        tick += x_interval

    y_ticks: List[float] = []
    tick = elev_min
    while tick <= elev_max + 1e-9:
        y_ticks.append(round(tick, 6))
        tick += elev_interval

    _draw_grid(space, graph_x0, graph_y0, graph_x1, graph_y1, x_ticks, y_ticks, map_x, map_y)
    space.add_line((graph_x0, graph_y0), (graph_x1, graph_y0), dxfattribs={"layer": "AXIS"})
    space.add_line((graph_x0, graph_y0), (graph_x0, graph_y1), dxfattribs={"layer": "AXIS"})

    eg_pts = [(map_x(offset), map_y(eg)) for offset, eg, _, _, _ in rows]
    fg_pts = [(map_x(offset), map_y(fg)) for offset, _, fg, _, _ in rows]
    _draw_polyline_points(space, eg_pts, "EG_CONTOUR")
    _draw_polyline_points(space, fg_pts, "FG_CONTOUR")

    pipe_pts = [(map_x(offset), map_y(pipe)) for offset, _, _, pipe, _ in rows if pipe is not None]
    if len(pipe_pts) >= 2:
        pipe_layer = "SAN" if "sanitary" in safe_text(section.get("alignment_type"), "").lower() else "PIPE"
        _draw_polyline_points(space, pipe_pts, pipe_layer)

    feature_band_y0 = y0 + 4.0
    feature_band_y1 = y0 + 10.0
    feature_layer_map = {
        "travel_lane": "ROAD",
        "curb_gutter": "PAVEMENT",
        "sidewalk": "WALK",
        "pipe_centerline": "PIPE",
        "section_edge": "SITE",
    }
    for run in _feature_runs(section):
        left = map_x(safe_num(run.get("start_offset_ft")))
        right = map_x(safe_num(run.get("end_offset_ft")))
        if abs(right - left) < 1.0:
            continue
        layer = feature_layer_map.get(safe_text(run.get("feature_type")), "SITE")
        _draw_box(space, min(left, right), feature_band_y0, max(left, right), feature_band_y1, layer=layer)
        label = _section_feature_label(safe_text(run.get("feature_type"), "section_edge"))
        add_text(
            space,
            label,
            _band_text_x(min(left, right), max(left, right), label),
            feature_band_y0 + 1.3,
            1.3 if len(label) > 12 else 1.45,
            "ANNO",
            style="CIVIL-NARROW" if len(label) > 10 else "CIVIL",
        )
        if safe_text(run.get("feature_type")) in {"curb_gutter", "section_edge"}:
            edge_x = min(left, right) if safe_text(run.get("feature_type")) == "section_edge" else max(left, right)
            space.add_line((edge_x, graph_y0), (edge_x, graph_y1), dxfattribs={"layer": "DIM"})

    for tick_val in x_ticks:
        x = map_x(tick_val)
        add_text(space, f"{tick_val:.0f}", x - 4.0, graph_y0 - 5.0, 1.8, "ANNO")
    for tick_val in y_ticks:
        y = map_y(tick_val)
        add_text(space, f"{tick_val:.1f}", graph_x0 - 12.0, y - 1.0, 1.8, "ANNO")

    feature_labels = {"travel_lane": "LANE", "curb_gutter": "C&G", "sidewalk": "SW", "pipe_centerline": "PIPE"}
    for offset, eg, fg, pipe, feature_type in rows:
        x = map_x(offset)
        if feature_type in feature_labels:
            label_y = map_y(pipe if pipe is not None and feature_type == "pipe_centerline" else fg) + 3.5
            add_text(space, feature_labels[feature_type], x - 4.0, label_y, 1.6, "ANNO")

    center_index = len(rows) // 2
    left = rows[0]
    center = rows[center_index]
    right = rows[-1]
    left_slope = (center[2] - left[2]) / max(center[0] - left[0], 1e-9) * 100.0
    right_slope = (right[2] - center[2]) / max(right[0] - center[0], 1e-9) * 100.0
    add_text(space, f"L {left_slope:+.2f}%", graph_x0 + 6.0, graph_y1 + 2.5, 1.9, "ANNO")
    add_text(space, f"R {right_slope:+.2f}%", graph_x1 - 28.0, graph_y1 + 2.5, 1.9, "ANNO")

    if safe_text(section.get("alignment_type"), "") == "roadway":
        section_context = safe_dict(section.get("section_context"))
        modeled_widths = safe_dict(section_context.get("modeled_widths"))
        edge_conditions = safe_dict(section_context.get("edge_conditions"))
        notes = []
        lane = safe_num(modeled_widths.get("lane_width_ft"), safe_num(section.get("lane_width_ft")))
        curb = safe_num(modeled_widths.get("curb_gutter_width_ft"), safe_num(section.get("curb_gutter_width_ft")))
        walk = safe_num(modeled_widths.get("sidewalk_total_width_ft"), safe_num(section.get("sidewalk_width_ft")))
        improved = safe_num(modeled_widths.get("improved_width_ft"), lane + curb + walk)
        if lane > 0:
            notes.append(f"Lane {lane:.1f}'")
        if curb > 0:
            notes.append(f"C&G {curb:.1f}'")
        if walk > 0:
            notes.append(f"SW {walk:.1f}'")
        if improved > 0:
            notes.append(f"Imp {improved:.1f}'")
        if safe_list(edge_conditions.get("kinds")):
            notes.append("Edge " + " / ".join(_edge_condition_label(item) for item in safe_list(edge_conditions.get("kinds"))[:2]))
        if notes:
            add_text(space, " | ".join(notes), graph_x0, y0 + 4.0, 1.9, "ANNO")
        zone_labels = [
            _edge_condition_label(safe_text(item.get("kind")))
            for item in safe_list(edge_conditions.get("zones"))[:2]
            if safe_text(safe_dict(item).get("kind"))
        ]
        if zone_labels:
            edge_specs = [
                (map_x(min(offsets)), zone_labels[0], -1.0),
                (map_x(max(offsets)), zone_labels[1] if len(zone_labels) > 1 else zone_labels[0], 1.0),
            ]
            for anchor_x, label, direction in edge_specs:
                label_x = max(x0 + 3.0, min(x1 - 42.0, anchor_x + direction * 16.0))
                label_y = graph_y1 - 5.0 if direction < 0 else graph_y1 - 10.0
                space.add_line((anchor_x, graph_y1 - 1.0), (label_x + (8.0 if direction < 0 else 0.0), label_y - 1.0), dxfattribs={"layer": "DIM"})
                add_text(space, label, label_x, label_y, 1.55, "TITLE", style="CIVIL-NARROW")
                space.add_circle((anchor_x, graph_y1 - 1.0), radius=0.8, dxfattribs={"layer": "DIM"})
        datum_rows = [["OFFSET", "FG", "EG"]]
        for idx in (0, center_index, len(rows) - 1):
            offset, eg, fg, _, _ = rows[idx]
            datum_rows.append([f"{offset:.1f}", f"{fg:.2f}", f"{eg:.2f}"])
        _draw_table_grid(space, x1 - 66.0, y0 + 12.0, [18.0, 18.0, 18.0], 4.2, datum_rows, title="SECTION BAND")
        dimension_runs = [run for run in _feature_runs(section) if safe_num(safe_dict(run).get("width_ft"), 0.0) > 1.0]
        dim_y = graph_y0 - 2.0
        for run in dimension_runs[:4]:
            left_x = map_x(safe_num(run.get("start_offset_ft")))
            right_x = map_x(safe_num(run.get("end_offset_ft")))
            label = _section_feature_label(safe_text(run.get("feature_type"), "section_edge"))
            width = safe_num(run.get("width_ft"), 0.0)
            space.add_line((left_x, dim_y), (right_x, dim_y), dxfattribs={"layer": "AXIS"})
            space.add_line((left_x, dim_y - 0.8), (left_x, dim_y + 0.8), dxfattribs={"layer": "DIM"})
            space.add_line((right_x, dim_y - 0.8), (right_x, dim_y + 0.8), dxfattribs={"layer": "DIM"})
            dim_text = f"{label} {width:.1f}'"
            add_text(
                space,
                dim_text,
                _band_text_x(min(left_x, right_x), max(left_x, right_x), dim_text),
                dim_y - 3.0,
                1.6 if len(dim_text) > 16 else 1.7,
                "ANNO",
                style="CIVIL-NARROW",
            )
            dim_y -= 4.5
        space.add_line((graph_x0, graph_y0 - 7.2), (graph_x1, graph_y0 - 7.2), dxfattribs={"layer": "SHEET"})
    elif pipe_pts:
        add_text(space, "Utility section includes pipe invert trace.", graph_x0, y0 + 4.0, 1.9, "ANNO")
        datum_rows = [["OFFSET", "FG", "PIPE"]]
        for idx in (0, center_index, len(rows) - 1):
            offset, _, fg, pipe, _ = rows[idx]
            datum_rows.append([f"{offset:.1f}", f"{fg:.2f}", f"{safe_num(pipe):.2f}" if pipe is not None else "--"])
        _draw_table_grid(space, x1 - 66.0, y0 + 12.0, [18.0, 18.0, 18.0], 4.2, datum_rows, title="SECTION BAND")


def _group_sections_for_sheets(sections: Sequence[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for section in sections:
        key = safe_text(section.get("sheet_name") or section.get("alignment_name") or section.get("sheet_title"), "CROSS SECTIONS")
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(section)
    chunks: List[List[Dict[str, Any]]] = []
    for key in order:
        chunks.extend(_chunks(grouped[key], 4))
    return chunks


def _draw_cross_section_layout(doc, plan: Dict[str, Any], sections: List[Dict[str, Any]], sheet_index: int, sheet_meta: Optional[Dict[str, Any]] = None) -> None:
    if not sections:
        return
    name = _make_unique_layout_name(doc, f"CROSS SECTIONS {sheet_index}")
    layout = _fresh_layout(doc, name)

    max_width = max(max(safe_num(section.get("width_ft")), 1.0) for section in sections)
    max_elev_span = 1.0
    for section in sections:
        rows = _section_offsets(section)
        elevs = [row[1] for row in rows] + [row[2] for row in rows] + [row[3] for row in rows if row[3] is not None]
        if elevs:
            max_elev_span = max(max_elev_span, max(elevs) - min(elevs))

    panel_w = 172.0
    panel_h = 92.0
    h_scale = _pick_engineering_scale_ft_per_in(max_width, 1.0, panel_w - 24.0, panel_h - 28.0)
    target_v_scale = max(h_scale / 5.0, 0.25)
    min_v_scale = max_elev_span * 25.4 / max(panel_h - 30.0, 1.0)
    v_scale = max(target_v_scale, min_v_scale)

    scale_label = f'H {_format_scale(h_scale)}  V {_format_scale(v_scale)}'
    sheet_meta = safe_dict(sheet_meta)
    _draw_title_block(
        layout,
        plan,
        safe_text(sections[0].get("sheet_title"), "CROSS SECTIONS"),
        safe_text(sheet_meta.get("sheet_name"), f"XS-{sheet_index:03d}"),
        scale_label,
        subtitle=safe_text(sections[0].get("alignment_name"), ""),
        sheet_code=safe_text(sheet_meta.get("sheet_code"), f"C-{500 + sheet_index:03d}"),
        sheet_number=int(safe_num(sheet_meta.get("sheet_number"), sheet_index)),
        sheet_total=int(safe_num(sheet_meta.get("sheet_total"), sheet_index)),
        discipline=safe_text(sheet_meta.get("discipline"), "CIVIL"),
        revision=safe_text(sheet_meta.get("revision"), DEFAULT_REVISION),
        issue_date=safe_text(sheet_meta.get("issue_date"), ""),
    )

    panels = [
        (24.0, 157.0, 196.0, 249.0),
        (220.0, 157.0, 392.0, 249.0),
        (24.0, 48.0, 196.0, 140.0),
        (220.0, 48.0, 392.0, 140.0),
    ]
    for panel, section in zip(panels, sections):
        _draw_cross_section_panel(layout, section, panel, h_scale, v_scale)


def _export_profiles(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = safe_dict(plan.get("meta"))
    existing_profiles = [safe_dict(item) for item in safe_list(meta.get("profiles")) if safe_dict(item)]
    if existing_profiles:
        return existing_profiles

    grading = safe_dict(meta.get("grading"))
    existing_surface = grading.get("existing_surface")
    proposed_surface = grading.get("proposed_surface") or existing_surface
    default_elev = safe_num(safe_dict(grading.get("checks")).get("pad_elev_ft"), 100.0) or 100.0
    actions = [safe_dict(item) for item in safe_list(plan.get("actions"))]
    profiles: List[Dict[str, Any]] = []

    road_alignment = _road_alignment_from_actions(actions)
    if road_alignment is not None:
        points, source = road_alignment
        samples = _polyline_station_samples(points, 5)
        profile_stations: List[Dict[str, Any]] = []
        for sample in samples:
            point = safe_list(sample.get("point"))
            if len(point) < 2:
                continue
            station_ft = safe_num(sample.get("station_ft"))
            profile_stations.append(
                {
                    "station_ft": station_ft,
                    "station_text": _station_text(station_ft),
                    "point": [round(safe_num(point[0]), 3), round(safe_num(point[1]), 3)],
                    "segment_index": int(sample.get("segment_index", 0)),
                    "existing_elev_ft": round(_sample_grid_surface_payload(existing_surface, point[0], point[1], default_elev), 3),
                    "proposed_elev_ft": round(_sample_grid_surface_payload(proposed_surface, point[0], point[1], default_elev), 3),
                }
            )
        if profile_stations:
            profiles.append(
                {
                    "name": "ROAD PROFILE 1",
                    "sheet_name": "ROAD PROFILE 1",
                    "sheet_title": "GRADING PROFILE",
                    "alignment_name": "ROAD ALIGNMENT 1",
                    "alignment_type": "roadway",
                    "alignment_points": points,
                    "stations": profile_stations,
                    "source": source,
                    "vertical_exaggeration": 5.0,
                }
            )

    storm_meta = safe_dict(meta.get("storm_pipes"))
    storm_segments = [safe_dict(item) for item in safe_list(storm_meta.get("segments")) if safe_dict(item)]
    if storm_segments:
        segment = max(storm_segments, key=lambda item: safe_num(item.get("length_ft"), 0.0))
        points = [[safe_num(pt[0]), safe_num(pt[1])] for pt in safe_list(segment.get("path") or segment.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(points) >= 2:
            samples = _polyline_station_samples(points, 5)
            start_invert = safe_num(segment.get("start_invert"), default_elev - 4.0)
            end_invert = safe_num(segment.get("end_invert"), start_invert - 1.0)
            total_length = max(_polyline_length(points), 1e-9)
            profile_stations = []
            for sample in samples:
                point = safe_list(sample.get("point"))
                if len(point) < 2:
                    continue
                station_ft = safe_num(sample.get("station_ft"))
                ratio = station_ft / total_length
                profile_stations.append(
                    {
                        "station_ft": station_ft,
                        "station_text": _station_text(station_ft),
                        "point": [round(safe_num(point[0]), 3), round(safe_num(point[1]), 3)],
                        "segment_index": int(sample.get("segment_index", 0)),
                        "existing_elev_ft": round(_sample_grid_surface_payload(existing_surface, point[0], point[1], default_elev), 3),
                        "proposed_elev_ft": round(_sample_grid_surface_payload(proposed_surface, point[0], point[1], default_elev), 3),
                        "pipe_invert_ft": round(start_invert + (end_invert - start_invert) * ratio, 3),
                    }
                )
            if profile_stations:
                name = safe_text(segment.get("pipe"), "STORM MAIN")
                profiles.append(
                    {
                        "name": f"{name} PROFILE",
                        "sheet_name": f"{name} PROFILE",
                        "sheet_title": "UTILITY PROFILE",
                        "alignment_name": name,
                        "alignment_type": "storm_pipe",
                        "alignment_points": points,
                        "stations": profile_stations,
                        "source": "storm_pipe",
                        "vertical_exaggeration": 8.0,
                    }
                )

    sanitary_meta = safe_dict(meta.get("sanitary"))
    sanitary_segments = [safe_dict(item) for item in safe_list(sanitary_meta.get("segments")) if safe_dict(item)]
    sanitary_main = next((item for item in sanitary_segments if safe_text(item.get("segment_role"), "") == "main"), None)
    if sanitary_main:
        points = [[safe_num(pt[0]), safe_num(pt[1])] for pt in safe_list(sanitary_main.get("route_points")) if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(points) >= 2:
            samples = _polyline_station_samples(points, 5)
            start_invert = safe_num(sanitary_main.get("start_invert_ft"), default_elev - 5.0)
            end_invert = safe_num(sanitary_main.get("end_invert_ft"), start_invert - 1.0)
            total_length = max(_polyline_length(points), 1e-9)
            profile_stations = []
            for sample in samples:
                point = safe_list(sample.get("point"))
                if len(point) < 2:
                    continue
                station_ft = safe_num(sample.get("station_ft"))
                ratio = station_ft / total_length
                profile_stations.append(
                    {
                        "station_ft": station_ft,
                        "station_text": _station_text(station_ft),
                        "point": [round(safe_num(point[0]), 3), round(safe_num(point[1]), 3)],
                        "segment_index": int(sample.get("segment_index", 0)),
                        "existing_elev_ft": round(_sample_grid_surface_payload(existing_surface, point[0], point[1], default_elev), 3),
                        "proposed_elev_ft": round(_sample_grid_surface_payload(proposed_surface, point[0], point[1], default_elev), 3),
                        "pipe_invert_ft": round(start_invert + (end_invert - start_invert) * ratio, 3),
                    }
                )
            if profile_stations:
                name = safe_text(sanitary_main.get("name"), "SANITARY MAIN")
                profiles.append(
                    {
                        "name": f"{name} PROFILE",
                        "sheet_name": f"{name} PROFILE",
                        "sheet_title": "UTILITY PROFILE",
                        "alignment_name": name,
                        "alignment_type": "sanitary_pipe",
                        "alignment_points": points,
                        "stations": profile_stations,
                        "source": "sanitary_pipe",
                        "vertical_exaggeration": 8.0,
                    }
                )

    return profiles


def _export_cross_sections(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = safe_dict(plan.get("meta"))
    existing_sections = [safe_dict(item) for item in safe_list(meta.get("cross_sections")) if safe_dict(item)]
    if existing_sections:
        return existing_sections

    grading = safe_dict(meta.get("grading"))
    existing_surface = grading.get("existing_surface")
    proposed_surface = grading.get("proposed_surface") or existing_surface
    default_elev = safe_num(safe_dict(grading.get("checks")).get("pad_elev_ft"), 100.0) or 100.0
    sections: List[Dict[str, Any]] = []

    for profile in _export_profiles(plan):
        alignment_type = safe_text(profile.get("alignment_type"), "roadway")
        alignment_points = safe_list(profile.get("alignment_points"))
        half_width = 18.0 if alignment_type == "roadway" else 12.0
        stations = [safe_dict(item) for item in safe_list(profile.get("stations"))]
        for index, station in enumerate(stations[1:-1], start=1):
            point = safe_list(station.get("point"))
            if len(point) < 2:
                continue
            cut_line = _perpendicular_cut_line(alignment_points, point, int(station.get("segment_index", 0)), half_width)
            section_samples = _sample_along_line(cut_line[0], cut_line[-1], 7)
            section_width = max(_polyline_length(cut_line), 1e-9)
            sample_rows = []
            lane_width = 24.0 if alignment_type == "roadway" else None
            sidewalk_width = 5.0 if alignment_type == "roadway" else None
            curb_width = 2.0 if alignment_type == "roadway" else None
            for sample_idx, sample_pt in enumerate(section_samples):
                offset_ft = -section_width / 2.0 + section_width * (sample_idx / max(len(section_samples) - 1, 1))
                existing_elev = round(_sample_grid_surface_payload(existing_surface, sample_pt[0], sample_pt[1], default_elev), 3)
                proposed_elev = round(_sample_grid_surface_payload(proposed_surface, sample_pt[0], sample_pt[1], default_elev), 3)
                feature_type = "section_edge"
                if alignment_type == "roadway":
                    lane_half = safe_num(lane_width, 24.0) / 2.0
                    curb_limit = lane_half + safe_num(curb_width, 2.0)
                    walk_limit = curb_limit + safe_num(sidewalk_width, 5.0)
                    abs_offset = abs(offset_ft)
                    if abs_offset <= lane_half:
                        feature_type = "travel_lane"
                    elif abs_offset <= curb_limit:
                        feature_type = "curb_gutter"
                    elif abs_offset <= walk_limit:
                        feature_type = "sidewalk"
                elif abs(offset_ft) <= 1.0:
                    feature_type = "pipe_centerline"
                row = {
                    "point": [round(sample_pt[0], 3), round(sample_pt[1], 3)],
                    "offset_ft": round(offset_ft, 3),
                    "existing_elev_ft": existing_elev,
                    "proposed_elev_ft": proposed_elev,
                    "feature_type": feature_type,
                }
                if "pipe_invert_ft" in station:
                    row["pipe_invert_ft"] = round(safe_num(station.get("pipe_invert_ft"), proposed_elev - 5.0), 3)
                sample_rows.append(row)
            sections.append(
                {
                    "name": f"{safe_text(profile.get('alignment_name'), alignment_type.upper())} SECTION {index}",
                    "sheet_name": f"{safe_text(profile.get('alignment_name'), alignment_type.upper())} SECTIONS",
                    "sheet_title": "CROSS SECTIONS" if alignment_type == "roadway" else "UTILITY CROSS SECTIONS",
                    "alignment_name": safe_text(profile.get("alignment_name"), alignment_type.upper()),
                    "alignment_type": alignment_type,
                    "station_ft": safe_num(station.get("station_ft")),
                    "station_text": safe_text(station.get("station_text"), _station_text(safe_num(station.get("station_ft")))),
                    "anchor_point": [round(safe_num(point[0]), 3), round(safe_num(point[1]), 3)],
                    "cut_line_points": [[round(safe_num(pt[0]), 3), round(safe_num(pt[1]), 3)] for pt in cut_line],
                    "width_ft": round(section_width, 3),
                    "lane_width_ft": lane_width,
                    "sidewalk_width_ft": sidewalk_width,
                    "curb_gutter_width_ft": curb_width,
                    "samples": sample_rows,
                }
            )
    return sections


def _build_sheet_registry(plan: Dict[str, Any], profiles: List[Dict[str, Any]], section_groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    revision = safe_text(safe_dict(plan.get("meta")).get("revision"), DEFAULT_REVISION)
    issue_date = safe_text(safe_dict(plan.get("meta")).get("issue_date"), datetime.now().strftime("%Y-%m-%d"))
    registry: List[Dict[str, Any]] = [
        {
            "layout_name": "SITE PLAN",
            "sheet_name": "SITE PLAN",
            "sheet_title": "SITE PLAN",
            "sheet_code": "C-100",
            "discipline": "CIVIL",
            "revision": revision,
            "issue_date": issue_date,
            "sheet_kind": "site_plan",
        }
    ]
    for index, profile in enumerate(profiles, start=1):
        registry.append(
            {
                "layout_name": f"PROFILE {index}",
                "sheet_name": safe_text(profile.get("sheet_name"), f"PROFILE {index}"),
                "sheet_title": safe_text(profile.get("sheet_title"), "PROFILE"),
                "sheet_code": f"C-{300 + index:03d}",
                "discipline": "CIVIL",
                "revision": revision,
                "issue_date": issue_date,
                "sheet_kind": "profile",
            }
        )
    for index, sections in enumerate(section_groups, start=1):
        first = safe_dict(sections[0]) if sections else {}
        registry.append(
            {
                "layout_name": f"CROSS SECTIONS {index}",
                "sheet_name": safe_text(first.get("sheet_name"), f"XS-{index:03d}"),
                "sheet_title": safe_text(first.get("sheet_title"), "CROSS SECTIONS"),
                "sheet_code": f"C-{500 + index:03d}",
                "discipline": "CIVIL",
                "revision": revision,
                "issue_date": issue_date,
                "sheet_kind": "cross_sections",
            }
        )
    total = len(registry)
    for idx, row in enumerate(registry, start=1):
        row["sheet_number"] = idx
        row["sheet_total"] = total
    return registry


def _add_profile_layouts(doc, plan: Dict[str, Any], profiles: List[Dict[str, Any]], sheet_registry: Sequence[Dict[str, Any]]) -> None:
    profile_sheets = [safe_dict(item) for item in sheet_registry if safe_text(item.get("sheet_kind")) == "profile"]
    for index, profile in enumerate(profiles, start=1):
        _draw_profile_layout(doc, plan, profile, index, profile_sheets[index - 1] if index - 1 < len(profile_sheets) else None)


def _add_cross_section_layouts(doc, plan: Dict[str, Any], section_groups: List[List[Dict[str, Any]]], sheet_registry: Sequence[Dict[str, Any]]) -> None:
    section_sheets = [safe_dict(item) for item in sheet_registry if safe_text(item.get("sheet_kind")) == "cross_sections"]
    for index, chunk in enumerate(section_groups, start=1):
        _draw_cross_section_layout(doc, plan, chunk, index, section_sheets[index - 1] if index - 1 < len(section_sheets) else None)


def _prune_default_layouts(doc) -> None:
    paper_layouts = [layout.name for layout in doc.layouts if layout.name != "Model"]
    if len(paper_layouts) <= 1:
        return
    for name in ("Layout1", "Layout2"):
        if name in _layout_names(doc):
            doc.layouts.delete(name)


def _build_export_audit(doc, plan: Dict[str, Any], actions: List[Dict[str, Any]], profiles: List[Dict[str, Any]], section_groups: List[List[Dict[str, Any]]], sheet_registry: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    meta = safe_dict(plan.get("meta"))
    canonical_profiles = [safe_dict(item) for item in safe_list(meta.get("profiles")) if safe_dict(item)]
    canonical_sections = [safe_dict(item) for item in safe_list(meta.get("cross_sections")) if safe_dict(item)]
    canonical_alignments = [safe_dict(item) for item in safe_list(meta.get("alignments")) if safe_dict(item)]
    deliverables = safe_dict(meta.get("deliverables"))
    requested = [safe_text(item) for item in safe_list(deliverables.get("requested")) if safe_text(item)]
    produced = [safe_text(item) for item in safe_list(deliverables.get("produced")) if safe_text(item)]
    layout_names = [layout.name for layout in doc.layouts if layout.name != "Model"]
    registry_names = [safe_text(item.get("layout_name")) for item in sheet_registry if safe_text(item.get("layout_name"))]
    registry_matches_outputs = layout_names == registry_names
    sheet_numbers = [int(safe_num(item.get("sheet_number"), 0)) for item in sheet_registry]
    sheet_codes = [safe_text(item.get("sheet_code")) for item in sheet_registry if safe_text(item.get("sheet_code"))]
    numbering_consistent = sheet_numbers == list(range(1, len(sheet_registry) + 1))
    plan_registry = [safe_dict(item) for item in safe_list(meta.get("sheet_registry")) if safe_dict(item)]
    registry_meta_matches_plan = plan_registry == [deepcopy(safe_dict(item)) for item in sheet_registry]
    title_block_metadata_complete = all(
        safe_text(item.get("sheet_name"))
        and safe_text(item.get("sheet_title"))
        and safe_text(item.get("sheet_code"))
        and safe_text(item.get("discipline"))
        and safe_text(item.get("revision"))
        and safe_text(item.get("issue_date"))
        and int(safe_num(item.get("sheet_number"), 0)) > 0
        and int(safe_num(item.get("sheet_total"), 0)) == len(sheet_registry)
        for item in sheet_registry
    )
    registry_order_kinds = [safe_text(item.get("sheet_kind")) for item in sheet_registry]
    registry_order_consistent = (
        registry_order_kinds[:1] == ["site_plan"]
        and registry_order_kinds[1 : 1 + len(profiles)] == ["profile"] * len(profiles)
        and registry_order_kinds[1 + len(profiles) :] == ["cross_sections"] * len(section_groups)
    )
    metadata_consistent = (
        len(sheet_codes) == len(set(sheet_codes))
        and numbering_consistent
        and registry_meta_matches_plan
        and title_block_metadata_complete
        and registry_order_consistent
    )
    legend_items = _legend_items(plan, actions)
    used_layers = sorted({get_layer(safe_dict(action), "SITE") for action in actions})
    legend_matches_content = True
    for item_type, symbol, _label in legend_items:
        if item_type == "line" and symbol not in used_layers:
            legend_matches_content = False
        if item_type == "block" and symbol not in CAD_BLOCKS:
            legend_matches_content = False
    canonical_profile_ids = {safe_text(item.get("name")) for item in canonical_profiles if safe_text(item.get("name"))}
    canonical_section_ids = {safe_text(item.get("name")) for item in canonical_sections if safe_text(item.get("name"))}
    exported_profile_ids = {safe_text(item.get("name")) for item in profiles if safe_text(item.get("name"))}
    exported_section_ids = {
        safe_text(section.get("name"))
        for group in section_groups
        for section in group
        if safe_text(safe_dict(section).get("name"))
    }
    profile_alignment = (not canonical_profiles and not profiles) or exported_profile_ids.issubset(canonical_profile_ids)
    section_alignment = (not canonical_sections and not exported_section_ids) or exported_section_ids.issubset(canonical_section_ids)
    mapped_actions = [safe_dict(action) for action in actions if safe_text(safe_dict(action).get("canonical_source_id"))]
    engineering_layers = {"PIPE", "SAN", "UTILITY", "STRUCTURE", "BASIN_BOUNDARY", "EG_CONTOUR", "FG_CONTOUR", "DRAIN_FLOW", "SPOT_EG", "SPOT_FG"}
    engineering_actions = [
        safe_dict(action)
        for action in actions
        if get_layer(safe_dict(action), "SITE") in engineering_layers
    ]
    mapped_engineering_actions = [action for action in engineering_actions if safe_text(action.get("canonical_source_id"))]
    action_mapping_complete = len(mapped_engineering_actions) == len(engineering_actions)
    callouts = _collect_structure_callouts(plan)
    site_callouts_canonical = bool(callouts) and all(safe_text(item.get("name")) and safe_text(item.get("symbol")) for item in callouts)
    expected_profile = any(item in {"road_profile", "profiles"} for item in requested)
    expected_sections = any(item in {"cross_sections", "cross_sections_plan"} for item in requested)
    missing_requested: List[str] = []
    if expected_profile and not canonical_profiles:
        missing_requested.append("profile deliverables")
    if expected_sections and not canonical_sections:
        missing_requested.append("cross-section deliverables")
    requested_vs_produced = {
        "requested": requested,
        "produced": produced,
        "missing_requested_profiles": expected_profile and not canonical_profiles,
        "missing_requested_sections": expected_sections and not canonical_sections,
        "profile_deliverable_consistent": (not expected_profile and "road_profile" not in produced and "profiles" not in produced) or bool(canonical_profiles),
        "section_deliverable_consistent": (not expected_sections and "cross_sections" not in produced) or bool(canonical_sections),
        "missing_requested_deliverables": missing_requested,
    }
    warnings: List[str] = []
    if canonical_profiles and not any(name.startswith("PROFILE") for name in layout_names):
        warnings.append("Canonical profiles exist but no profile layouts were exported.")
    if canonical_sections and not any(name.startswith("CROSS SECTIONS") for name in layout_names):
        warnings.append("Canonical cross sections exist, but no CROSS SECTIONS layouts were exported. Check sheet grouping and registry ordering.")
    if not registry_matches_outputs:
        warnings.append("Sheet registry does not match actual exported layouts. Check layout_name ordering in the exported registry.")
    if not metadata_consistent:
        warnings.append("Sheet metadata numbering/codes were inconsistent. Check sheet numbers, sheet codes, and title-block metadata completeness.")
    if not registry_meta_matches_plan:
        warnings.append("Sheet registry in plan metadata did not match the exported registry. Regenerate the registry before export.")
    if not title_block_metadata_complete:
        warnings.append("One or more sheet title-block metadata fields were incomplete. Required fields include sheet name, title, code, discipline, revision, date, and numbering.")
    if not registry_order_consistent:
        warnings.append("Sheet registry ordering did not match site/profile/section output ordering. Site should lead, followed by profiles, then cross sections.")
    if not legend_matches_content:
        warnings.append("Legend items did not match the actual exported content. Remove unused legend entries or add the missing content.")
    if not profile_alignment:
        warnings.append("Exported profiles did not map cleanly to canonical profile objects. Check profile naming and canonical alignment linkage.")
    if not section_alignment:
        warnings.append("Exported cross sections did not map cleanly to canonical cross-section objects. Check section naming and canonical section linkage.")
    if requested_vs_produced["missing_requested_profiles"]:
        warnings.append("Requested profile deliverables were not backed by canonical profile data. Generate canonical profiles before export.")
    if requested_vs_produced["missing_requested_sections"]:
        warnings.append("Requested cross-section deliverables were not backed by canonical section data. Generate canonical cross sections before export.")
    return {
        "success": not warnings,
        "layout_order": layout_names,
        "sheet_total": len(sheet_registry),
        "sheet_titles": [safe_text(item.get("sheet_title")) for item in sheet_registry],
        "sheet_registry": [deepcopy(safe_dict(item)) for item in sheet_registry],
        "sheet_registry_matches_outputs": registry_matches_outputs,
        "sheet_metadata_consistent": metadata_consistent,
        "sheet_registry_meta_matches_plan": registry_meta_matches_plan,
        "title_block_metadata_complete": title_block_metadata_complete,
        "sheet_registry_order_consistent": registry_order_consistent,
        "profile_layout_count": len([name for name in layout_names if name.startswith("PROFILE")]),
        "cross_section_layout_count": len([name for name in layout_names if name.startswith("CROSS SECTIONS")]),
        "canonical_profile_count": len(canonical_profiles),
        "canonical_cross_section_count": len(canonical_sections),
        "canonical_alignment_count": len(canonical_alignments),
        "exported_profile_count": len(profiles),
        "exported_cross_section_sheet_count": len(section_groups),
        "block_definitions": sorted(name for name in CAD_BLOCKS if name in doc.blocks),
        "text_styles": sorted(name for name in ("CIVIL", "CIVIL-BOLD", "CIVIL-NARROW") if name in doc.styles),
        "modelspace_layers": used_layers,
        "legend_items": [{"type": item_type, "symbol": symbol, "label": label} for item_type, symbol, label in legend_items],
        "legend_matches_content": legend_matches_content,
        "requested_vs_produced": requested_vs_produced,
        "canonical_sheet_alignment": {
            "profile_alignment": profile_alignment,
            "section_alignment": section_alignment,
            "site_callouts_canonical": site_callouts_canonical,
            "sheet_element_alignment_complete": profile_alignment and section_alignment and site_callouts_canonical and registry_matches_outputs,
        },
        "canonical_action_alignment": {
            "total_actions": len(actions),
            "canonical_sourced_actions": len(mapped_actions),
            "engineering_action_count": len(engineering_actions),
            "mapped_engineering_actions": len(mapped_engineering_actions),
            "all_engineering_actions_mapped": action_mapping_complete,
        },
        "warnings": warnings,
    }


def save_dxf(plan: Dict[str, Any], filename: str | None = None) -> str:
    actions = safe_list(plan.get("actions"))
    if not actions:
        raise ValueError("No actions found in plan.")

    if filename is None:
        filename = timestamped_filename("output", "dxf")

    doc = ezdxf.new("R2010")
    ensure_layers(doc)
    ensure_text_styles(doc)
    ensure_blocks(doc)

    msp = doc.modelspace()
    for action in actions:
        _draw_action_to_modelspace(msp, safe_dict(action))
    _write_summary_block(msp, plan, actions)

    profiles = _export_profiles(plan)
    sections = _export_cross_sections(plan)
    section_groups = _group_sections_for_sheets(sections)
    sheet_registry = _build_sheet_registry(plan, profiles, section_groups)
    plan.setdefault("meta", {})
    plan["meta"]["sheet_registry"] = [dict(item) for item in sheet_registry]

    site_sheet = next((safe_dict(item) for item in sheet_registry if safe_text(item.get("sheet_kind")) == "site_plan"), {})
    _add_site_plan_layout(doc, plan, actions, site_sheet)
    _add_profile_layouts(doc, plan, profiles, sheet_registry)
    _add_cross_section_layouts(doc, plan, section_groups, sheet_registry)
    _prune_default_layouts(doc)
    plan["meta"]["export_audit"] = _build_export_audit(doc, plan, actions, profiles, section_groups, sheet_registry)

    doc.saveas(filename)
    return filename
