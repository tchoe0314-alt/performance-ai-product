from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.config import (
    CELL_SIZE,
    DEFAULT_LOT_HEIGHT,
    DEFAULT_LOT_WIDTH,
    DEFAULT_LOT_X,
    DEFAULT_LOT_Y,
    DEFAULT_PAD_ELEV,
    DEFAULT_PARK_START_ELEV,
    DEFAULT_PARK_SLOPE_Y,
    DEFAULT_ROAD_SLOPE_X,
    DEFAULT_ROAD_START_ELEV,
    POND_RADIUS,
    SURFACE_PADDING,
    TEXT_HEIGHT_SMALL,
)
from core.geometry_core import Point3D, ProjectModel, ZoneType
from engines.grading_engine import GradeElement
from engines.surface_engine import GridSurface

from .common import safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import field_path_is_omitted


def build_existing_surface(
    parsed: Dict[str, Any],
    *,
    infer_surface_profile: Any,
    normalize_vector: Any,
) -> GridSurface:
    lot = safe_dict(parsed.get("lot"))
    x_min = safe_float(lot.get("x"), DEFAULT_LOT_X) - SURFACE_PADDING
    y_min = safe_float(lot.get("y"), DEFAULT_LOT_Y) - SURFACE_PADDING
    x_max = safe_float(lot.get("x"), DEFAULT_LOT_X) + safe_float(lot.get("w"), DEFAULT_LOT_WIDTH) + SURFACE_PADDING
    y_max = safe_float(lot.get("y"), DEFAULT_LOT_Y) + safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT) + SURFACE_PADDING
    cell = max(1.0, safe_float(CELL_SIZE, 5.0))

    ncols = max(2, int(round((x_max - x_min) / cell)) + 1)
    nrows = max(2, int(round((y_max - y_min) / cell)) + 1)
    profile = infer_surface_profile(parsed)
    ux, uy = normalize_vector(profile["downhill_dx"], profile["downhill_dy"])
    slope_ratio = max(0.002, safe_float(profile["slope_ratio"], 0.02))
    center_x = (x_min + x_max) / 2.0
    center_y = (y_min + y_max) / 2.0

    values: List[List[float]] = []
    for row in range(nrows):
        y = y_min + row * cell
        row_vals: List[float] = []
        for col in range(ncols):
            x = x_min + col * cell
            signed_run = (x - center_x) * ux + (y - center_y) * uy
            z = (DEFAULT_PAD_ELEV + 1.0) - slope_ratio * signed_run
            row_vals.append(float(z))
        values.append(row_vals)

    surface = GridSurface(
        x_min=x_min,
        y_min=y_min,
        x_max=x_min + (ncols - 1) * cell,
        y_max=y_min + (nrows - 1) * cell,
        cell_size=cell,
        ncols=ncols,
        nrows=nrows,
        values=values,
    )
    setattr(surface, "_inferred_profile", profile)
    return surface


def surface_range(surface: Optional[GridSurface]) -> Tuple[float, float]:
    if surface is None or not getattr(surface, "values", None):
        return 0.0, 0.0
    min_z = float("inf")
    max_z = float("-inf")
    for row in getattr(surface, "values", []) or []:
        for value in row:
            z = safe_float(value, 0.0)
            min_z = min(min_z, z)
            max_z = max(max_z, z)
    if min_z == float("inf") or max_z == float("-inf"):
        return 0.0, 0.0
    return min_z, max_z


def surface_actions_from_grid(surface: Optional[GridSurface], *, layer: str, note_prefix: str, sample_lines: int = 6) -> List[Dict[str, Any]]:
    if surface is None or not all(hasattr(surface, attr) for attr in ("nrows", "ncols", "x_at", "y_at", "values")):
        return []
    actions: List[Dict[str, Any]] = []
    nrows = max(0, safe_int(getattr(surface, "nrows", 0), 0))
    ncols = max(0, safe_int(getattr(surface, "ncols", 0), 0))
    if nrows <= 1 or ncols <= 1:
        return actions
    step = max(1, nrows // max(1, sample_lines))
    counter = 0
    for row in range(0, nrows, step):
        pts: List[List[float]] = []
        z_vals: List[float] = []
        for col in range(ncols):
            pts.append([float(surface.x_at(col)), float(surface.y_at(row))])
            z_vals.append(safe_float(surface.values[row][col], 0.0))
        if len(pts) < 2:
            continue
        avg_z = sum(z_vals) / max(len(z_vals), 1)
        counter += 1
        actions.append({
            "task": "polyline",
            "origin": None,
            "points": pts,
            "closed": False,
            "width": None,
            "height": None,
            "label": f"{note_prefix}-{counter}",
            "layer": layer,
            "text": None,
            "text_height": None,
            "center": None,
            "radius": None,
            "start_angle": None,
            "end_angle": None,
        })
        label_idx = len(pts) // 2
        label_pt = pts[label_idx]
        actions.append({
            "task": "text_note",
            "origin": [label_pt[0], label_pt[1]],
            "points": None,
            "closed": None,
            "width": None,
            "height": None,
            "label": None,
            "layer": layer,
            "text": f"{note_prefix} {avg_z:.2f}",
            "text_height": TEXT_HEIGHT_SMALL,
            "center": None,
            "radius": None,
            "start_angle": None,
            "end_angle": None,
        })
    return actions


def _sample_surface_nearest(surface: Optional[GridSurface], x: float, y: float, default: float = DEFAULT_PAD_ELEV) -> float:
    if surface is None or not getattr(surface, "values", None):
        return float(default)
    cell = max(1.0, safe_float(getattr(surface, "cell_size", 0.0), 0.0))
    col = int(round((x - safe_float(getattr(surface, "x_min", 0.0), 0.0)) / cell))
    row = int(round((y - safe_float(getattr(surface, "y_min", 0.0), 0.0)) / cell))
    ncols = max(1, safe_int(getattr(surface, "ncols", 1), 1))
    nrows = max(1, safe_int(getattr(surface, "nrows", 1), 1))
    col = max(0, min(ncols - 1, col))
    row = max(0, min(nrows - 1, row))
    try:
        return safe_float(surface.values[row][col], default)
    except Exception:
        return float(default)


def _control_spot_grade_actions(
    grade_elements: Optional[List[GradeElement]],
    proposed_surface: Optional[GridSurface],
    *,
    limit: int = 12,
) -> List[Dict[str, Any]]:
    if not grade_elements or proposed_surface is None:
        return []
    actions: List[Dict[str, Any]] = []
    seen: List[Tuple[float, float]] = []

    def _too_close(x: float, y: float) -> bool:
        return any(abs(px - x) <= 18.0 and abs(py - y) <= 18.0 for px, py in seen)

    priority_kinds = {"pad": 0, "parking": 1, "road": 2, "pond": 3, "basin": 3}
    filtered = []
    for elem in grade_elements:
        kind = safe_str(getattr(elem, "kind", ""), "").lower()
        name = safe_str(getattr(elem, "name", ""), "")
        if kind not in priority_kinds:
            continue
        upper_name = name.upper()
        if upper_name in {"BUILDABLE_AREA", "SITE", "LOT"} or "BUILDABLE" in upper_name:
            continue
        filtered.append((priority_kinds[kind], -safe_float(getattr(elem, "width", 0.0), 0.0) * safe_float(getattr(elem, "depth", 0.0), 0.0), elem))

    for _, _, elem in sorted(filtered):
        x = safe_float(getattr(elem, "x", 0.0), 0.0) + safe_float(getattr(elem, "width", 0.0), 0.0) / 2.0
        y = safe_float(getattr(elem, "y", 0.0), 0.0) + safe_float(getattr(elem, "depth", 0.0), 0.0) / 2.0
        if _too_close(x, y):
            continue
        z = _sample_surface_nearest(proposed_surface, x, y, DEFAULT_PAD_ELEV)
        actions.append({
            "task": "text_note",
            "origin": [round(x, 3), round(y, 3)],
            "points": None,
            "closed": None,
            "width": None,
            "height": None,
            "label": None,
            "layer": "SPOT_FG",
            "text": f"FG {z:.2f}",
            "text_height": TEXT_HEIGHT_SMALL,
            "center": None,
            "radius": None,
            "start_angle": None,
            "end_angle": None,
        })
        seen.append((x, y))
        if len(actions) >= limit:
            break
    return actions


def _focus_bounds_from_grade_elements(
    grade_elements: Optional[List[GradeElement]],
    proposed_surface: Optional[GridSurface],
) -> Tuple[float, float, float, float]:
    coords: List[Tuple[float, float]] = []
    for elem in grade_elements or []:
        kind = safe_str(getattr(elem, "kind", ""), "").lower()
        if kind not in {"pad", "parking", "road", "pond", "basin"}:
            continue
        name = safe_str(getattr(elem, "name", ""), "").upper()
        if name in {"BUILDABLE_AREA", "SITE", "LOT"} or "BUILDABLE" in name:
            continue
        x = safe_float(getattr(elem, "x", 0.0), 0.0)
        y = safe_float(getattr(elem, "y", 0.0), 0.0)
        w = safe_float(getattr(elem, "width", 0.0), 0.0)
        d = safe_float(getattr(elem, "depth", 0.0), 0.0)
        coords.append((x, y))
        coords.append((x + w, y + d))

    if coords:
        xs = [pt[0] for pt in coords]
        ys = [pt[1] for pt in coords]
        return min(xs), min(ys), max(xs), max(ys)

    if proposed_surface is None:
        return 0.0, 0.0, DEFAULT_LOT_WIDTH, DEFAULT_LOT_HEIGHT

    return (
        safe_float(getattr(proposed_surface, "x_min", 0.0), 0.0),
        safe_float(getattr(proposed_surface, "y_min", 0.0), 0.0),
        safe_float(getattr(proposed_surface, "x_max", DEFAULT_LOT_WIDTH), DEFAULT_LOT_WIDTH),
        safe_float(getattr(proposed_surface, "y_max", DEFAULT_LOT_HEIGHT), DEFAULT_LOT_HEIGHT),
    )


def _select_low_point_spot_grades(
    low_points: Sequence[Any],
    *,
    focus_bounds: Tuple[float, float, float, float],
    existing_origins: Sequence[Tuple[float, float]],
    limit: int,
) -> List[Dict[str, Any]]:
    min_x, min_y, max_x, max_y = focus_bounds
    focus_cx = (min_x + max_x) / 2.0
    focus_cy = (min_y + max_y) / 2.0
    focus_w = max(max_x - min_x, 1.0)
    focus_h = max(max_y - min_y, 1.0)
    seen: List[Tuple[float, float]] = list(existing_origins)

    def _too_close(x: float, y: float) -> bool:
        return any(abs(px - x) <= 18.0 and abs(py - y) <= 18.0 for px, py in seen)

    def _edge_penalty(x: float, y: float) -> float:
        edge_dx = min(abs(x - min_x), abs(max_x - x))
        edge_dy = min(abs(y - min_y), abs(max_y - y))
        return min(edge_dx / max(focus_w, 1.0), edge_dy / max(focus_h, 1.0))

    ranked: List[Tuple[Tuple[float, float, float, float], int, Any]] = []
    for idx, point in enumerate(low_points):
        x = safe_float(getattr(point, "x", 0.0), 0.0)
        y = safe_float(getattr(point, "y", 0.0), 0.0)
        z = safe_float(getattr(point, "z", 0.0), 0.0)
        basin_score = safe_float(getattr(point, "local_basin_score", 0.0), 0.0)
        dist = abs(x - focus_cx) + abs(y - focus_cy)
        edge_score = _edge_penalty(x, y)
        ranked.append(((-edge_score, dist, z, -basin_score), idx, point))

    actions: List[Dict[str, Any]] = []
    for _, _, point in sorted(ranked):
        x = safe_float(getattr(point, "x", 0.0), 0.0)
        y = safe_float(getattr(point, "y", 0.0), 0.0)
        if _too_close(x, y):
            continue
        z = safe_float(getattr(point, "z", 0.0), 0.0)
        actions.append(
            {
                "task": "text_note",
                "origin": [round(x, 3), round(y, 3)],
                "points": None,
                "closed": None,
                "width": None,
                "height": None,
                "label": None,
                "layer": "SPOT_FG",
                "text": f"FG {z:.2f}",
                "text_height": TEXT_HEIGHT_SMALL,
                "center": None,
                "radius": None,
                "start_angle": None,
                "end_angle": None,
            }
        )
        seen.append((x, y))
        if len(actions) >= limit:
            break
    return actions


def grading_surface_actions(
    result: Any,
    existing_surface: Optional[GridSurface],
    proposed_surface: Optional[GridSurface],
    *,
    grade_elements: Optional[List[GradeElement]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    actions: List[Dict[str, Any]] = []
    existing_actions = surface_actions_from_grid(existing_surface, layer="EG_CONTOUR", note_prefix="EG")
    proposed_actions = surface_actions_from_grid(proposed_surface, layer="FG_CONTOUR", note_prefix="FG")
    actions.extend(existing_actions)
    actions.extend(proposed_actions)

    control_spot_actions = _control_spot_grade_actions(grade_elements, proposed_surface, limit=12)
    actions.extend(control_spot_actions)
    control_spot_origins = {
        tuple(action.get("origin") or [])
        for action in control_spot_actions
        if isinstance(action.get("origin"), list)
    }

    low_points = safe_list(getattr(result, "low_points", []))
    focus_bounds = _focus_bounds_from_grade_elements(grade_elements, proposed_surface)
    remaining_spot_budget = max(0, 16 - len(control_spot_actions))
    low_point_actions = _select_low_point_spot_grades(
        low_points,
        focus_bounds=focus_bounds,
        existing_origins=list(control_spot_origins),
        limit=remaining_spot_budget,
    )
    actions.extend(low_point_actions)

    flow_samples = sorted(
        safe_list(getattr(result, "flow_samples", [])),
        key=lambda sample: safe_float(getattr(sample, "magnitude", 0.0), 0.0),
        reverse=True,
    )
    for sample in flow_samples[:16]:
        x = safe_float(getattr(sample, "x", 0.0), 0.0)
        y = safe_float(getattr(sample, "y", 0.0), 0.0)
        dx = safe_float(getattr(sample, "downhill_dx", 0.0), 0.0)
        dy = safe_float(getattr(sample, "downhill_dy", 0.0), 0.0)
        mag = safe_float(getattr(sample, "magnitude", 0.0), 0.0)
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            continue
        arrow_len = max(6.0, min(18.0, mag * 200.0))
        actions.append({
            "task": "polyline",
            "origin": None,
            "points": [[x, y], [x + dx * arrow_len, y + dy * arrow_len]],
            "closed": False,
            "width": None,
            "height": None,
            "label": None,
            "layer": "DRAIN_FLOW",
            "text": None,
            "text_height": None,
            "center": None,
            "radius": None,
            "start_angle": None,
            "end_angle": None,
        })

    stats = {
        "existing_contour_count": sum(1 for action in existing_actions if safe_str(action.get("task")) == "polyline"),
        "proposed_contour_count": sum(1 for action in proposed_actions if safe_str(action.get("task")) == "polyline"),
        "spot_grade_count": len(control_spot_actions) + len(low_point_actions),
        "flow_arrow_count": min(len(flow_samples), 16),
    }
    return actions, stats


def canonical_grading_payload(
    *,
    existing_surface: Optional[GridSurface],
    result: Any,
    derived_action_stats: Dict[str, int],
    grade_elements: Optional[List[GradeElement]] = None,
    normalize_vector: Any,
) -> Dict[str, Any]:
    proposed_surface = getattr(result, "proposed_surface", None)
    checks = safe_list(getattr(result, "checks", []))
    low_points = safe_list(getattr(result, "low_points", []))
    flow_samples = safe_list(getattr(result, "flow_samples", []))
    existing_min, existing_max = surface_range(existing_surface)
    proposed_min, proposed_max = surface_range(proposed_surface)
    inferred_profile = getattr(existing_surface, "_inferred_profile", {}) if existing_surface is not None else {}
    if flow_samples:
        ranked_samples = sorted(
            flow_samples,
            key=lambda sample: safe_float(getattr(sample, "magnitude", 0.0), 0.0),
            reverse=True,
        )[:12]
        avg_dx = sum(safe_float(getattr(sample, "downhill_dx", 0.0), 0.0) for sample in ranked_samples) / max(len(ranked_samples), 1)
        avg_dy = sum(safe_float(getattr(sample, "downhill_dy", 0.0), 0.0) for sample in ranked_samples) / max(len(ranked_samples), 1)
    else:
        avg_dx = safe_float(safe_dict(inferred_profile).get("downhill_dx"), 0.0)
        avg_dy = safe_float(safe_dict(inferred_profile).get("downhill_dy"), 0.0)
    downhill_dx, downhill_dy = normalize_vector(avg_dx, avg_dy)
    ranked_low_points = sorted(
        low_points,
        key=lambda point: (
            safe_float(getattr(point, "z", 0.0), 0.0),
            -safe_float(getattr(point, "local_basin_score", 0.0), 0.0),
        ),
    )
    primary_low_point = ranked_low_points[0] if ranked_low_points else None
    controls = list(grade_elements or [])
    kind_counts: Dict[str, int] = {}
    for elem in controls:
        kind = safe_str(getattr(elem, "kind", ""), "")
        if kind:
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
    return {
        "schema_version": "v1",
        "source": "grading_engine",
        "success": bool(getattr(result, "success", True)),
        "message": safe_str(getattr(result, "message", "Grading stage completed.")),
        "warnings": [safe_str(item) for item in safe_list(getattr(result, "warnings", [])) if safe_str(item)],
        "existing_surface": {
            "nrows": safe_int(getattr(existing_surface, "nrows", 0), 0) if existing_surface is not None else 0,
            "ncols": safe_int(getattr(existing_surface, "ncols", 0), 0) if existing_surface is not None else 0,
            "cell_size": safe_float(getattr(existing_surface, "cell_size", 0.0), 0.0) if existing_surface is not None else 0.0,
            "min_z": round(existing_min, 3),
            "max_z": round(existing_max, 3),
            "range_z": round(existing_max - existing_min, 3),
            "terrain_inferred": bool(safe_dict(inferred_profile).get("inferred")),
            "terrain_profile": deepcopy(safe_dict(inferred_profile)),
        },
        "proposed_surface": {
            "nrows": safe_int(getattr(proposed_surface, "nrows", 0), 0) if proposed_surface is not None else 0,
            "ncols": safe_int(getattr(proposed_surface, "ncols", 0), 0) if proposed_surface is not None else 0,
            "cell_size": safe_float(getattr(proposed_surface, "cell_size", 0.0), 0.0) if proposed_surface is not None else 0.0,
            "min_z": round(proposed_min, 3),
            "max_z": round(proposed_max, 3),
            "range_z": round(proposed_max - proposed_min, 3),
        },
        "earthwork": {
            "cut_cf": round(safe_float(getattr(result, "cut_volume", 0.0), 0.0), 3),
            "fill_cf": round(safe_float(getattr(result, "fill_volume", 0.0), 0.0), 3),
            "net_cf": round(safe_float(getattr(result, "net_volume", 0.0), 0.0), 3),
        },
        "checks": [
            {
                "name": safe_str(getattr(check, "name", "")),
                "passed": bool(getattr(check, "passed", False)),
                "value": safe_float(getattr(check, "value", 0.0), 0.0),
                "threshold": getattr(check, "threshold", None),
                "message": safe_str(getattr(check, "message", "")),
            }
            for check in checks
        ],
        "low_points": [
            {
                "name": f"LOW-{index}",
                "x": round(safe_float(getattr(point, "x", 0.0), 0.0), 3),
                "y": round(safe_float(getattr(point, "y", 0.0), 0.0), 3),
                "z": round(safe_float(getattr(point, "z", 0.0), 0.0), 3),
                "row": safe_int(getattr(point, "row", 0), 0),
                "col": safe_int(getattr(point, "col", 0), 0),
                "local_basin_score": round(safe_float(getattr(point, "local_basin_score", 0.0), 0.0), 3),
            }
            for index, point in enumerate(low_points[:25], start=1)
        ],
        "flow_samples": [
            {
                "x": round(safe_float(getattr(sample, "x", 0.0), 0.0), 3),
                "y": round(safe_float(getattr(sample, "y", 0.0), 0.0), 3),
                "z": round(safe_float(getattr(sample, "z", 0.0), 0.0), 3),
                "slope_x": round(safe_float(getattr(sample, "slope_x", 0.0), 0.0), 6),
                "slope_y": round(safe_float(getattr(sample, "slope_y", 0.0), 0.0), 6),
                "magnitude": round(safe_float(getattr(sample, "magnitude", 0.0), 0.0), 6),
                "downhill_dx": round(safe_float(getattr(sample, "downhill_dx", 0.0), 0.0), 6),
                "downhill_dy": round(safe_float(getattr(sample, "downhill_dy", 0.0), 0.0), 6),
            }
            for sample in flow_samples[:50]
        ],
        "surface_controls": {
            "has_primary_drainage_direction": bool(abs(downhill_dx) > 1e-9 or abs(downhill_dy) > 1e-9),
            "downhill_vector": {
                "dx": round(downhill_dx, 6),
                "dy": round(downhill_dy, 6),
            },
            "primary_low_point": (
                {
                    "x": round(safe_float(getattr(primary_low_point, "x", 0.0), 0.0), 3),
                    "y": round(safe_float(getattr(primary_low_point, "y", 0.0), 0.0), 3),
                    "z": round(safe_float(getattr(primary_low_point, "z", 0.0), 0.0), 3),
                    "local_basin_score": round(safe_float(getattr(primary_low_point, "local_basin_score", 0.0), 0.0), 3),
                }
                if primary_low_point is not None
                else {}
            ),
            "grade_range_ft": round(proposed_max - proposed_min, 3),
            "control_counts": {
                "pad": kind_counts.get("pad", 0),
                "road": kind_counts.get("road", 0),
                "parking": kind_counts.get("parking", 0),
                "pond": kind_counts.get("pond", 0),
            },
            "control_summary": [
                {
                    "kind": safe_str(getattr(elem, "kind", ""), ""),
                    "name": safe_str(getattr(elem, "name", ""), ""),
                    "base_elev": round(safe_float(getattr(elem, "base_elev", 0.0), 0.0), 3) if getattr(elem, "base_elev", None) is not None else None,
                    "slope_x": round(safe_float(getattr(elem, "slope_x", 0.0), 0.0), 6) if getattr(elem, "slope_x", None) is not None else None,
                    "slope_y": round(safe_float(getattr(elem, "slope_y", 0.0), 0.0), 6) if getattr(elem, "slope_y", None) is not None else None,
                    "transition_zone": round(safe_float(getattr(elem, "transition_zone", 0.0), 0.0), 3) if getattr(elem, "transition_zone", None) is not None else None,
                    "width": round(safe_float(getattr(elem, "width", 0.0), 0.0), 3),
                    "depth": round(safe_float(getattr(elem, "depth", 0.0), 0.0), 3),
                }
                for elem in controls[:16]
            ],
        },
        "drainage_hints": deepcopy(safe_dict(getattr(result, "drainage_hints", {}))),
        "explain": deepcopy(safe_dict(getattr(result, "explain", {}))),
        "optimize_hooks": deepcopy(safe_dict(getattr(result, "optimize_hooks", {}))),
        "conflict_hooks": deepcopy(safe_dict(getattr(result, "conflict_hooks", {}))),
        "stats": {
            "low_point_count": len(low_points),
            "flow_sample_count": len(flow_samples),
            "failed_check_count": sum(1 for check in checks if not bool(getattr(check, "passed", False))),
            **derived_action_stats,
        },
    }


def point_on_lot_edge(lot: Dict[str, Any], direction: Tuple[float, float], *, normalize_vector: Any, inset: float = 8.0) -> Tuple[float, float]:
    x = safe_float(lot.get("x"), DEFAULT_LOT_X)
    y = safe_float(lot.get("y"), DEFAULT_LOT_Y)
    w = max(1.0, safe_float(lot.get("w"), DEFAULT_LOT_WIDTH))
    h = max(1.0, safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT))
    cx = x + w / 2.0
    cy = y + h / 2.0
    dx, dy = normalize_vector(direction[0], direction[1])

    candidates: List[Tuple[float, float, float]] = []
    if abs(dx) > 1e-9:
        tx = (x + w - inset - cx) / dx if dx > 0 else (x + inset - cx) / dx
        if tx > 0:
            px = cx + dx * tx
            py = cy + dy * tx
            if (y + inset) <= py <= (y + h - inset):
                candidates.append((tx, px, py))
    if abs(dy) > 1e-9:
        ty = (y + h - inset - cy) / dy if dy > 0 else (y + inset - cy) / dy
        if ty > 0:
            px = cx + dx * ty
            py = cy + dy * ty
            if (x + inset) <= px <= (x + w - inset):
                candidates.append((ty, px, py))

    if not candidates:
        return x + w - inset, y + inset
    _, px, py = min(candidates, key=lambda item: item[0])
    return round(px, 3), round(py, 3)


def grading_drainage_coordination(parsed: Dict[str, Any], project: ProjectModel, *, normalize_vector: Any) -> Dict[str, Any]:
    grading = safe_dict(project.meta.get("grading_summary"))
    existing = safe_dict(grading.get("existing_surface"))
    surface_controls = safe_dict(grading.get("surface_controls"))
    terrain_profile = safe_dict(existing.get("terrain_profile"))
    lot = safe_dict(parsed.get("lot"))

    low_points = [item for item in safe_list(grading.get("low_points")) if isinstance(item, dict)]
    flow_samples = [item for item in safe_list(grading.get("flow_samples")) if isinstance(item, dict)]

    downhill_vector = safe_dict(surface_controls.get("downhill_vector"))
    if safe_float(downhill_vector.get("dx"), 0.0) or safe_float(downhill_vector.get("dy"), 0.0):
        avg_dx = safe_float(downhill_vector.get("dx"), 0.0)
        avg_dy = safe_float(downhill_vector.get("dy"), 0.0)
    elif flow_samples:
        ranked = sorted(flow_samples, key=lambda item: safe_float(item.get("magnitude"), 0.0), reverse=True)[:12]
        avg_dx = sum(safe_float(item.get("downhill_dx"), 0.0) for item in ranked) / max(len(ranked), 1)
        avg_dy = sum(safe_float(item.get("downhill_dy"), 0.0) for item in ranked) / max(len(ranked), 1)
    else:
        avg_dx = safe_float(terrain_profile.get("downhill_dx"), 1.0)
        avg_dy = safe_float(terrain_profile.get("downhill_dy"), -0.3)
    downhill_dx, downhill_dy = normalize_vector(avg_dx, avg_dy)
    outfall_x, outfall_y = point_on_lot_edge(lot, (downhill_dx, downhill_dy), normalize_vector=normalize_vector)

    preferred_targets: List[Dict[str, Any]] = []
    ranked_low_points = sorted(low_points, key=lambda item: (safe_float(item.get("z"), 0.0), -safe_float(item.get("local_basin_score"), 0.0)))
    for index, item in enumerate(ranked_low_points[:2], start=1):
        preferred_targets.append({
            "name": f"BASIN_TARGET_{index}",
            "x": round(safe_float(item.get("x"), 0.0), 3),
            "y": round(safe_float(item.get("y"), 0.0), 3),
            "z": round(safe_float(item.get("z"), 0.0), 3),
            "radius": POND_RADIUS,
            "source": "grading_low_point",
        })

    preferred_targets.append({
        "name": "OUTFALL_A",
        "x": outfall_x,
        "y": outfall_y,
        "z": round(min([safe_float(item.get("z"), 0.0) for item in ranked_low_points[:1]] or [DEFAULT_PAD_ELEV - 1.0]), 3),
        "radius": POND_RADIUS,
        "source": "grading_flow_edge",
    })

    return {
        "downhill_vector": {"dx": round(downhill_dx, 6), "dy": round(downhill_dy, 6)},
        "preferred_targets": preferred_targets,
        "preferred_outfall": deepcopy(preferred_targets[-1]),
        "grading_low_point_count": len(low_points),
        "grading_flow_sample_count": len(flow_samples),
        "surface_controls": deepcopy(surface_controls),
        "grading_control_counts": deepcopy(safe_dict(surface_controls.get("control_counts"))),
    }


def build_grade_elements(project: ProjectModel, parsed: Dict[str, Any]) -> List[GradeElement]:
    elems: List[GradeElement] = []
    for zone in project.zones.values():
        bbox = zone.boundary.bbox
        zt = zone.zone_type

        if zt in {ZoneType.BUILDING, ZoneType.BUILDING_PAD, ZoneType.PAD}:
            elems.append(
                GradeElement(
                    kind="pad",
                    x=bbox.min_x,
                    y=bbox.min_y,
                    width=bbox.width,
                    depth=bbox.height,
                    base_elev=DEFAULT_PAD_ELEV,
                    priority=10,
                    transition_zone=15.0,
                    name=zone.name or "BUILDING_PAD",
                )
            )
        elif zt in {ZoneType.ROAD, ZoneType.ROADWAY, ZoneType.CORRIDOR}:
            elems.append(
                GradeElement(
                    kind="road",
                    x=bbox.min_x,
                    y=bbox.min_y,
                    width=bbox.width,
                    depth=bbox.height,
                    base_elev=DEFAULT_ROAD_START_ELEV,
                    slope_x=DEFAULT_ROAD_SLOPE_X,
                    crown=0.02,
                    priority=8,
                    transition_zone=12.0,
                    orientation="x",
                    name=zone.name or "ROAD",
                )
            )
        elif zt in {ZoneType.PARKING}:
            elems.append(
                GradeElement(
                    kind="parking",
                    x=bbox.min_x,
                    y=bbox.min_y,
                    width=bbox.width,
                    depth=bbox.height,
                    base_elev=DEFAULT_PARK_START_ELEV,
                    slope_y=DEFAULT_PARK_SLOPE_Y,
                    priority=6,
                    transition_zone=10.0,
                    name=zone.name or "PARKING",
                )
            )
        elif zt in {ZoneType.DETENTION, ZoneType.DRAINAGE}:
            elems.append(
                GradeElement(
                    kind="pond",
                    x=bbox.min_x,
                    y=bbox.min_y,
                    width=bbox.width,
                    depth=bbox.height,
                    base_elev=DEFAULT_PAD_ELEV - 1.0,
                    priority=5,
                    transition_zone=10.0,
                    name=zone.name or "POND",
                )
            )
    return elems
