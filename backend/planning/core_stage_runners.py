from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Sequence

from core.config import (
    DEFAULT_LOT_HEIGHT,
    DEFAULT_LOT_WIDTH,
    DEFAULT_LOT_X,
    DEFAULT_LOT_Y,
    DEFAULT_PAD_DEPTH,
    DEFAULT_PAD_ELEV,
    DEFAULT_PAD_WIDTH,
)
from core.geometry_core import EngineeringDomain, EngineeringObject, Point3D, ZoneType, rect_zone
from core.project_manager import ConflictRecord, ConflictSeverity, DependencyState
from engines.grading_engine import GradingEngine, GradingRequest
from engines.surface_engine import GridSurface

from .common import lower_text, safe_dict, safe_float, safe_int, safe_list, safe_str
from .field_contract import (
    field_path_is_omitted,
    filter_actions_by_field_intent,
    preserve_field_states,
    unwrap_fields_for_execution,
)
from .runtime import PlannerExecutionContext, _lot_area, _mark_dependency_state, collect_plan_stats


def _program_building_specs(parsed: Dict[str, Any], site_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    execution_payload = unwrap_fields_for_execution(parsed)
    buildings = safe_list(execution_payload.get("buildings"))
    specs: List[Dict[str, Any]] = []
    default_w = max(20.0, safe_float(site_plan.get("building_width"), DEFAULT_PAD_WIDTH))
    default_d = max(20.0, safe_float(site_plan.get("building_depth"), DEFAULT_PAD_DEPTH))
    for idx, raw in enumerate(buildings, start=1):
        rec = safe_dict(raw)
        if not rec:
            continue
        specs.append(
            {
                "name": safe_str(rec.get("name"), f"Building {idx}"),
                "use": lower_text(rec.get("use")) or "generic",
                "w": max(20.0, safe_float(rec.get("w"), default_w)),
                "d": max(20.0, safe_float(rec.get("d"), default_d)),
            }
        )
    if specs:
        return specs
    return [{"name": "BUILDING", "use": "generic", "w": default_w, "d": default_d}]


def _place_row(
    specs: Sequence[Dict[str, Any]],
    *,
    min_x: float,
    max_x: float,
    base_y: float,
    row_height: float,
) -> List[Dict[str, Any]]:
    if not specs:
        return []
    span_w = max(max_x - min_x, 1.0)
    widths = [safe_float(spec.get("w"), 20.0) for spec in specs]
    spacing = max(30.0, min(span_w * 0.06, 90.0))
    total_w = sum(widths) + spacing * max(len(widths) - 1, 0)
    if total_w > span_w and len(widths) > 1:
        spacing = max(16.0, (span_w - sum(widths)) / max(len(widths) - 1, 1))
        total_w = sum(widths) + spacing * max(len(widths) - 1, 0)
    start_x = min_x + max((span_w - total_w) / 2.0, 0.0)
    placements: List[Dict[str, Any]] = []
    cursor_x = start_x
    for spec in specs:
        w = safe_float(spec.get("w"), 20.0)
        d = safe_float(spec.get("d"), 20.0)
        y = base_y + max((row_height - d) / 2.0, 0.0)
        placements.append(
            {
                "name": safe_str(spec.get("name"), "BUILDING"),
                "use": lower_text(spec.get("use")) or "generic",
                "w": w,
                "d": d,
                "x": round(cursor_x, 3),
                "y": round(y, 3),
            }
        )
        cursor_x += w + spacing
    return placements


def _synthesized_program_layout(
    *,
    lot_x: float,
    lot_y: float,
    lot_w: float,
    lot_h: float,
    street_edge: str,
    specs: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not specs:
        return []
    margin_x = max(35.0, lot_w * 0.06)
    margin_y = max(35.0, lot_h * 0.06)
    min_x = lot_x + margin_x
    max_x = lot_x + lot_w - margin_x
    min_y = lot_y + margin_y
    max_y = lot_y + lot_h - margin_y

    frontage_uses = {"retail", "commercial", "pad"}
    frontage = [spec for spec in specs if (lower_text(spec.get("use")) or "generic") in frontage_uses]
    primary = [spec for spec in specs if spec not in frontage]
    if not primary:
        primary, frontage = frontage, []

    placements: List[Dict[str, Any]] = []
    frontage_on_bottom = lower_text(street_edge) != "top"
    if frontage_on_bottom:
        core_ceiling_ratio = 0.54 if frontage else 0.6
        max_y = min(max_y, lot_y + lot_h * core_ceiling_ratio)
    else:
        core_floor_ratio = 0.46 if frontage else 0.4
        min_y = max(min_y, lot_y + lot_h * core_floor_ratio)
    vertical_span = max(max_y - min_y, 1.0)

    def _fit_row_bands(
        upper_h: float,
        lower_h: float,
        gap: float,
    ) -> Tuple[float, float, float, float]:
        total_h = upper_h + lower_h + gap
        if total_h > vertical_span:
            scale = max(0.6, vertical_span / max(total_h, 1.0))
            upper_h *= scale
            lower_h *= scale
            gap *= scale
        frontage_shift = min(vertical_span * 0.36, 240.0)
        if frontage_on_bottom:
            cluster_center = min_y + vertical_span * 0.5 - frontage_shift
        else:
            cluster_center = min_y + vertical_span * 0.5 + frontage_shift
        lower_y = cluster_center - (gap / 2.0) - lower_h
        upper_y = cluster_center + (gap / 2.0)
        shift = 0.0
        if lower_y < min_y:
            shift = min_y - lower_y
        elif upper_y + upper_h > max_y:
            shift = max_y - (upper_y + upper_h)
        lower_y += shift
        upper_y += shift
        return upper_y, upper_h, lower_y, lower_h

    if frontage and len(primary) == 3:
        upper_h = max(max(safe_float(spec.get("d"), 20.0) for spec in primary[:2]) + 10.0, min(vertical_span * 0.1, 76.0))
        middle_h = max(max(safe_float(spec.get("d"), 20.0) for spec in primary[2:]) + 8.0, min(vertical_span * 0.085, 64.0))
        lower_h = max(max(safe_float(spec.get("d"), 20.0) for spec in frontage) + 8.0, min(vertical_span * 0.075, 52.0))
        gap = max(8.0, min(vertical_span * 0.018, 12.0))
        total_h = upper_h + middle_h + lower_h + gap * 2.0
        if total_h > vertical_span:
            scale = max(0.6, vertical_span / max(total_h, 1.0))
            upper_h *= scale
            middle_h *= scale
            lower_h *= scale
            gap *= scale
        if frontage_on_bottom:
            lower_y = min_y
            middle_y = lower_y + lower_h + gap
            upper_y = middle_y + middle_h + gap
            if upper_y + upper_h > max_y:
                shift = max_y - (upper_y + upper_h)
                lower_y += shift
                middle_y += shift
                upper_y += shift
            placements.extend(_place_row(primary[:2], min_x=min_x, max_x=max_x, base_y=upper_y, row_height=upper_h))
            placements.extend(_place_row(primary[2:], min_x=min_x, max_x=max_x, base_y=middle_y, row_height=middle_h))
            placements.extend(_place_row(frontage, min_x=min_x, max_x=max_x, base_y=lower_y, row_height=lower_h))
        else:
            upper_y = max_y - upper_h
            middle_y = upper_y - gap - middle_h
            lower_y = middle_y - gap - lower_h
            if lower_y < min_y:
                shift = min_y - lower_y
                upper_y += shift
                middle_y += shift
                lower_y += shift
            placements.extend(_place_row(primary[:2], min_x=min_x, max_x=max_x, base_y=lower_y, row_height=lower_h))
            placements.extend(_place_row(primary[2:], min_x=min_x, max_x=max_x, base_y=middle_y, row_height=middle_h))
            placements.extend(_place_row(frontage, min_x=min_x, max_x=max_x, base_y=upper_y, row_height=upper_h))
    elif frontage:
        upper_h = max(max(safe_float(spec.get("d"), 20.0) for spec in primary) + 10.0, min(vertical_span * 0.11, 82.0))
        lower_h = max(max(safe_float(spec.get("d"), 20.0) for spec in frontage) + 8.0, min(vertical_span * 0.08, 56.0))
        gap = max(8.0, min(vertical_span * 0.02, 14.0))
        top_row_y, top_row_h, bottom_row_y, bottom_row_h = _fit_row_bands(upper_h, lower_h, gap)
    else:
        top_row_h = max(max(safe_float(spec.get("d"), 20.0) for spec in primary) + 34.0, min(vertical_span * 0.2, 140.0))
        top_row_y = min_y + max((vertical_span - top_row_h) / 2.0, 0.0)
        bottom_row_y = min_y
        bottom_row_h = max(vertical_span * 0.22, 40.0)

    if frontage and len(primary) == 3:
        return placements
    if len(primary) > 3:
        split = (len(primary) + 1) // 2
        upper_specs = primary[:split]
        lower_specs = primary[split:]
        if frontage_on_bottom:
            placements.extend(_place_row(upper_specs, min_x=min_x, max_x=max_x, base_y=top_row_y, row_height=top_row_h))
            placements.extend(_place_row(lower_specs, min_x=min_x, max_x=max_x, base_y=bottom_row_y + bottom_row_h * 0.35, row_height=bottom_row_h * 0.5))
        else:
            placements.extend(_place_row(upper_specs, min_x=min_x, max_x=max_x, base_y=bottom_row_y + bottom_row_h * 0.35, row_height=bottom_row_h * 0.5))
            placements.extend(_place_row(lower_specs, min_x=min_x, max_x=max_x, base_y=top_row_y, row_height=top_row_h))
    else:
        placements.extend(_place_row(primary, min_x=min_x, max_x=max_x, base_y=top_row_y, row_height=top_row_h))

    if frontage:
        frontage_y = bottom_row_y if frontage_on_bottom else top_row_y
        frontage_h = bottom_row_h if frontage_on_bottom else top_row_h * 0.5
        placements.extend(_place_row(frontage, min_x=min_x, max_x=max_x, base_y=frontage_y, row_height=frontage_h))
    return placements


def _layout_fallback_actions(
    placements: Sequence[Dict[str, Any]],
    *,
    lot_x: float,
    lot_y: float,
    lot_w: float,
    lot_h: float,
    street_edge: str,
    culdesac_count: int = 0,
) -> List[Dict[str, Any]]:
    if not placements:
        return []
    actions: List[Dict[str, Any]] = []
    frontage_on_bottom = lower_text(street_edge) != "top"
    parking_entries: List[Dict[str, Any]] = []
    for placement in placements:
        px = safe_float(placement.get("x"), 0.0)
        py = safe_float(placement.get("y"), 0.0)
        pw = safe_float(placement.get("w"), 20.0)
        pd = safe_float(placement.get("d"), 20.0)
        frontage_use = lower_text(placement.get("use")) in {"retail", "commercial", "pad"}
        if frontage_use:
            lot_depth = max(20.0, min(30.0, pd * 0.42))
        else:
            lot_depth = max(24.0, min(34.0, pd * 0.5))
        setback_gap = 10.0 if frontage_use else 12.0
        pavement_y = max(lot_y + 15.0, py - lot_depth - setback_gap) if frontage_on_bottom else min(lot_y + lot_h - lot_depth - 15.0, py + pd + setback_gap)
        side_buffer = 8.0 if frontage_use else 6.0
        park_x = round(max(lot_x + 15.0, px - side_buffer), 3)
        park_y = round(pavement_y, 3)
        park_w = round(min(lot_w - 30.0, pw + side_buffer * 2.0), 3)
        park_h = round(lot_depth, 3)
        parking_entries.append(
            {
                "use": lower_text(placement.get("use")),
                "frontage": frontage_use,
                "rect": (park_x, park_y, park_w, park_h),
            }
        )
        walk_width = round(max(6.0, min(10.0, pw * 0.12)), 3)
        walk_x = round(px + (pw - walk_width) / 2.0, 3)
        if frontage_on_bottom:
            walk_y = round(park_y + park_h, 3)
            walk_h = round(max(6.0, py - walk_y), 3)
        else:
            walk_y = round(py + pd, 3)
            walk_h = round(max(6.0, park_y - walk_y), 3)
        actions.append(
            {
                "task": "rectangle",
                "layer": "WALK",
                "origin": [walk_x, walk_y],
                "width": walk_width,
                "height": walk_h,
            }
        )

    def _merge_courts(
        rects: Sequence[Tuple[float, float, float, float]],
        *,
        shared: bool = False,
    ) -> Optional[Tuple[float, float, float, float]]:
        if not rects:
            return None
        min_x = min(x for x, _, _, _ in rects)
        min_y = min(y for _, y, _, _ in rects)
        max_x = max(x + w for x, _, w, _ in rects)
        max_y = max(y + h for _, y, _, h in rects)
        width = max_x - min_x
        height = max_y - min_y
        if shared and width > 0:
            side_inset = min(max(26.0, width * 0.14), 50.0)
            min_x += side_inset
            max_x -= side_inset
            width = max(max_x - min_x, 48.0)
        return (
            round(min_x, 3),
            round(min_y, 3),
            round(width, 3),
            round(height, 3),
        )

    residential_rects = [
        entry["rect"]
        for entry in parking_entries
        if not bool(entry.get("frontage")) and entry.get("rect")
    ]
    frontage_rects = [
        entry["rect"]
        for entry in parking_entries
        if bool(entry.get("frontage")) and entry.get("rect")
    ]

    parking_rects: List[Tuple[float, float, float, float]] = []
    if len(residential_rects) >= 3:
        residential_rects = sorted(residential_rects, key=lambda rect: rect[0] + rect[2] / 2.0)
        split = (len(residential_rects) + 1) // 2
        for group in (residential_rects[:split], residential_rects[split:]):
            merged = _merge_courts(group, shared=len(group) > 1)
            if merged:
                parking_rects.append(merged)
    else:
        parking_rects.extend(residential_rects)
    parking_rects.extend(frontage_rects)

    if not parking_rects:
        return actions

    for park_x, park_y, park_w, park_h in parking_rects:
        actions.append(
            {
                "task": "rectangle",
                "layer": "PARKING",
                "origin": [park_x, park_y],
                "width": park_w,
                "height": park_h,
            }
        )

    def _collector_for_rect(rect: Tuple[float, float, float, float]) -> Optional[Tuple[float, float, float, float]]:
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return None
        collector_h = round(max(8.0, min(12.0, h * 0.22)), 3)
        collector_y = round(max(lot_y + 12.0, y - collector_h - 5.0), 3)
        collector_w = round(max(24.0, min(w - 8.0, w * 0.9)), 3)
        collector_x = round(min(max(lot_x + 12.0, x + (w - collector_w) / 2.0), lot_x + lot_w - collector_w - 12.0), 3)
        return (collector_x, collector_y, collector_w, collector_h)

    def _append_surface(rect: Optional[Tuple[float, float, float, float]], *, layer: str) -> None:
        if not rect:
            return
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return
        actions.append(
            {
                "task": "rectangle",
                "layer": layer,
                "origin": [round(x, 3), round(y, 3)],
                "width": round(w, 3),
                "height": round(h, 3),
            }
        )

    residential_collectors = [_collector_for_rect(rect) for rect in parking_rects[: len(parking_rects) - len(frontage_rects)]]
    frontage_collectors = [_collector_for_rect(rect) for rect in frontage_rects]
    residential_collectors = [rect for rect in residential_collectors if rect]
    frontage_collectors = [rect for rect in frontage_collectors if rect]

    for collector in residential_collectors + frontage_collectors:
        _append_surface(collector, layer="PAVEMENT")

    residential_access_target = _merge_courts(residential_collectors)
    access_targets = [rect for rect in [residential_access_target, *frontage_collectors] if rect]
    for idx, target in enumerate(access_targets):
        ax, ay, aw, ah = target
        access_w = round(max(14.0, min(20.0, aw * 0.12)), 3)
        if len(access_targets) == 1:
            target_center_x = ax + aw / 2.0
            lot_center_x = lot_x + lot_w / 2.0
            if target_center_x >= lot_center_x:
                access_x = round(lot_x + lot_w - access_w - 18.0, 3)
            else:
                access_x = round(lot_x + 18.0, 3)
        elif idx == 0:
            access_x = round(lot_x + lot_w - access_w - 18.0, 3)
        else:
            access_x = round(lot_x + 18.0, 3)
        if frontage_on_bottom:
            access_y = round(max(lot_y + 8.0, ay - 28.0), 3)
            access_h = round(min(max(18.0, ay - access_y), 32.0), 3)
        else:
            access_y = round(ay + ah, 3)
            access_h = round(min(max(18.0, lot_y + lot_h - access_y - 8.0), 32.0), 3)
        access = (access_x, access_y, access_w, access_h)
        _append_surface(access, layer="PAVEMENT")
    return actions


def _merge_layout_actions(existing: Sequence[Dict[str, Any]], new_actions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for action in list(existing) + list(new_actions):
        rec = safe_dict(action)
        if not rec:
            continue
        key = repr(rec)
        if key in seen:
            continue
        seen.add(key)
        merged.append(deepcopy(rec))
    return merged


def _rectangle_bounds(action: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    if lower_text(action.get("task")) != "rectangle":
        return None
    origin = safe_list(action.get("origin"))
    if len(origin) < 2:
        return None
    x = safe_float(origin[0], 0.0)
    y = safe_float(origin[1], 0.0)
    w = max(0.0, safe_float(action.get("width"), 0.0))
    h = max(0.0, safe_float(action.get("height"), 0.0))
    return x, y, w, h


def _rect_center(bounds: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x, y, w, h = bounds
    return x + w / 2.0, y + h / 2.0


def _rect_gap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> Tuple[float, float]:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    gap_x = max(0.0, max(bx - (ax + aw), ax - (bx + bw)))
    gap_y = max(0.0, max(by - (ay + ah), ay - (by + bh)))
    return gap_x, gap_y


def _polyline_bounds(points: Sequence[Sequence[Any]]) -> Optional[Tuple[float, float, float, float]]:
    coords = [safe_list(point) for point in safe_list(points)]
    coords = [point for point in coords if len(point) >= 2]
    if len(coords) < 2:
        return None
    xs = [safe_float(point[0], 0.0) for point in coords]
    ys = [safe_float(point[1], 0.0) for point in coords]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    return min_x, min_y, max_x - min_x, max_y - min_y


def _action_shape_signature(action: Dict[str, Any]) -> Tuple[Any, ...]:
    task = lower_text(action.get("task"))
    if task == "rectangle":
        bounds = _rectangle_bounds(action)
        return ("rectangle", bounds)
    if task in {"polyline", "polygon"}:
        pts = tuple(
            (round(safe_float(point[0], 0.0), 3), round(safe_float(point[1], 0.0), 3))
            for point in safe_list(action.get("points"))
            if len(safe_list(point)) >= 2
        )
        return (task, pts)
    if task == "circle":
        center = safe_list(action.get("center"))
        if len(center) >= 2:
            return ("circle", round(safe_float(center[0], 0.0), 3), round(safe_float(center[1], 0.0), 3), round(safe_float(action.get("radius"), 0.0), 3))
        return ("circle", None)
    return (task, repr(safe_dict(action)))


def _synthesize_layout_collectors(
    parking_rects: Sequence[Tuple[Tuple[float, float, float, float], Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    if not parking_rects:
        return []

    rows = sorted(
        [
            {
                "bounds": bounds,
                "cx": _rect_center(bounds)[0],
                "cy": _rect_center(bounds)[1],
            }
            for bounds, _ in parking_rects
        ],
        key=lambda item: item["cy"],
        reverse=True,
    )
    centers_y = [item["cy"] for item in rows]
    split_y = (max(centers_y) + min(centers_y)) / 2.0 if centers_y else 0.0
    upper_row = [item["bounds"] for item in rows if item["cy"] >= split_y]
    lower_row = [item["bounds"] for item in rows if item["cy"] < split_y]
    if not upper_row:
        upper_row = [item["bounds"] for item in rows]

    actions: List[Dict[str, Any]] = []

    def _append_rect(bounds: Optional[Tuple[float, float, float, float]], layer: str) -> None:
        if not bounds:
            return
        x, y, w, h = bounds
        if w <= 0 or h <= 0:
            return
        actions.append(
            {
                "task": "rectangle",
                "layer": layer,
                "origin": [round(x, 3), round(y, 3)],
                "width": round(w, 3),
                "height": round(h, 3),
                "synthetic_layout_collector": True,
                "semantic_surface_role": "circulation",
            }
        )

    def _collector_for_row(row: Sequence[Tuple[float, float, float, float]]) -> Optional[Tuple[float, float, float, float]]:
        if not row:
            return None
        row_min_x = min(x for x, _, _, _ in row)
        row_max_x = max(x + w for x, _, w, _ in row)
        row_min_y = min(y for _, y, _, _ in row)
        parking_height = max(h for _, _, _, h in row)
        collector_h = round(max(8.0, min(12.0, parking_height * 0.18)), 3)
        collector_y = round(row_min_y - collector_h - 3.0, 3)
        collector_x = round(row_min_x - 2.0, 3)
        collector_w = round((row_max_x - row_min_x) + 4.0, 3)
        return (collector_x, collector_y, collector_w, collector_h)

    upper_collector = _collector_for_row(upper_row)
    lower_collector = _collector_for_row(lower_row) if lower_row else None
    _append_rect(upper_collector, "PAVEMENT")
    _append_rect(lower_collector, "PAVEMENT")

    return actions


def _synthesize_layout_semantics(actions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen: set[str] = set()

    building_rects: List[Tuple[Tuple[float, float, float, float], Dict[str, Any]]] = []
    pavement_rects: List[Tuple[Tuple[float, float, float, float], Dict[str, Any]]] = []
    road_actions: List[Dict[str, Any]] = []
    has_parking = False
    has_walk = False
    has_fire = False

    def _has_parking_semantics(action: Dict[str, Any]) -> bool:
        label = safe_str(action.get("label")).upper()
        if action.get("semantic_surface_role") == "circulation":
            return False
        if label in {"DRIVE", "ROAD", "FIRE", "FRONTAGE", "ACCESS"}:
            return False
        if label.startswith("PARK") or label.startswith("STALL"):
            return True
        if safe_int(action.get("stall_count"), 0) > 0:
            return True
        item_type = lower_text(action.get("type"))
        if item_type in {"frontage", "access_drive", "collector_aisle", "parking_aisle", "fire_lane"}:
            return False
        return item_type in {"parking", "parking_area", "parking_module", ""}

    def _looks_like_parking_module(bounds: Tuple[float, float, float, float]) -> bool:
        x, y, w, h = bounds
        if w <= 0.0 or h <= 0.0:
            return False
        min_dim = min(w, h)
        max_dim = max(w, h)
        if min_dim < 12.0 or max_dim < 30.0:
            return False
        if (w * h) < 500.0:
            return False
        aspect = max_dim / max(min_dim, 1e-6)
        near_building = any(
            (_rect_gap(bounds, b_bounds)[0] + _rect_gap(bounds, b_bounds)[1]) <= 140.0
            for b_bounds, _ in building_rects
        )
        return near_building and (aspect >= 1.6 or max_dim >= 70.0)

    for action in safe_list(actions):
        rec = safe_dict(action)
        if not rec:
            continue
        layer = safe_str(rec.get("layer")).upper()
        bounds = _rectangle_bounds(rec)
        if layer == "BUILDING" and bounds is not None:
            building_rects.append((bounds, rec))
        elif layer == "PAVEMENT" and bounds is not None:
            pavement_rects.append((bounds, rec))
        elif layer == "ROAD":
            road_actions.append(rec)
        elif layer == "PARKING":
            has_parking = True
        elif layer == "WALK":
            has_walk = True
        elif layer == "FIRE":
            has_fire = True

    for action in safe_list(actions):
        rec = safe_dict(action)
        if not rec:
            continue
        layer = safe_str(rec.get("layer")).upper()
        task = lower_text(rec.get("task"))
        bounds = _rectangle_bounds(rec)
        if layer in {"ROAD", "FIRE"} and task in {"circle", "polyline"}:
            continue
        out = deepcopy(rec)
        if layer == "ROAD" and bounds is not None:
            out["layer"] = "PAVEMENT"
            out["semantic_surface_role"] = "circulation"
        if layer == "FIRE":
            out["layer"] = "PAVEMENT"
            out["semantic_surface_role"] = "circulation"
        if layer == "PAVEMENT" and bounds is not None and building_rects and not has_parking and _has_parking_semantics(rec):
            nearest_gap = min((_rect_gap(bounds, b_bounds) for b_bounds, _ in building_rects), key=lambda pair: pair[0] + pair[1])
            center_x, _ = _rect_center(bounds)
            overlaps_building_band = any(
                abs(center_x - _rect_center(b_bounds)[0]) <= max(bounds[2], b_bounds[2]) * 0.7
                for b_bounds, _ in building_rects
            )
            if nearest_gap[1] <= 120.0 and overlaps_building_band and _looks_like_parking_module(bounds):
                out["layer"] = "PARKING"
        key = repr(out)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(out)

    if building_rects and not any(safe_str(safe_dict(a).get("layer")).upper() == "PARKING" for a in normalized):
        for bounds, rec in pavement_rects:
            if not _has_parking_semantics(rec):
                continue
            if not _looks_like_parking_module(bounds):
                continue
            out = deepcopy(rec)
            out["layer"] = "PARKING"
            key = repr(out)
            if key not in seen:
                seen.add(key)
                normalized.append(out)

    parking_rects = [
        (_rectangle_bounds(safe_dict(action)), safe_dict(action))
        for action in normalized
        if safe_str(safe_dict(action).get("layer")).upper() == "PARKING" and _rectangle_bounds(safe_dict(action)) is not None
    ]
    has_pavement_surface = any(
        safe_str(safe_dict(action).get("layer")).upper() == "PAVEMENT"
        and _rectangle_bounds(safe_dict(action)) is not None
        for action in normalized
    )

    if building_rects and parking_rects and not has_walk:
        for building_bounds, _ in building_rects:
            bx, by, bw, bh = building_bounds
            bcx, _ = _rect_center(building_bounds)
            nearest_parking_bounds, _ = min(
                parking_rects,
                key=lambda item: (_rect_gap(building_bounds, item[0])[0] + _rect_gap(building_bounds, item[0])[1]),
            )
            px, py, pw, ph = nearest_parking_bounds
            walk_width = round(max(6.0, min(10.0, bw * 0.12)), 3)
            walk_x = round(bcx - walk_width / 2.0, 3)
            if py + ph <= by:
                walk_y = round(py + ph, 3)
                walk_h = round(max(6.0, by - walk_y), 3)
            elif by + bh <= py:
                walk_y = round(by + bh, 3)
                walk_h = round(max(6.0, py - walk_y), 3)
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
                normalized.append(walk_action)

    if building_rects and parking_rects:
        schematic_road_actions: List[Dict[str, Any]] = []
        for action in normalized:
            layer = safe_str(safe_dict(action).get("layer")).upper()
            task = lower_text(safe_dict(action).get("task"))
            if layer not in {"ROAD", "FIRE"}:
                continue
            if task == "circle":
                schematic_road_actions.append(action)
                continue
            if task == "polyline":
                bounds = _polyline_bounds(safe_list(safe_dict(action).get("points")))
                if not bounds:
                    continue
                _, _, w, h = bounds
                if w > 300.0 and h > 300.0:
                    schematic_road_actions.append(action)
                    continue
                if max(w, h) > 120.0 and min(w, h) < 24.0:
                    schematic_road_actions.append(action)
                    continue

        if schematic_road_actions:
            bad_signatures = {_action_shape_signature(safe_dict(action)) for action in schematic_road_actions}
            normalized = [
                action
                for action in normalized
                if not (
                    safe_str(safe_dict(action).get("layer")).upper() in {"ROAD", "PAVEMENT", "FIRE"}
                    and _action_shape_signature(safe_dict(action)) in bad_signatures
                )
            ]
            seen = {repr(safe_dict(action)) for action in normalized}
            for action in _synthesize_layout_collectors(parking_rects):
                key = repr(action)
                if key not in seen:
                    seen.add(key)
                    normalized.append(action)
        elif not has_pavement_surface:
            for action in _synthesize_layout_collectors(parking_rects):
                key = repr(action)
                if key not in seen:
                    seen.add(key)
                    normalized.append(action)

    return normalized


def run_layout_stage(
    ctx: PlannerExecutionContext,
    *,
    legacy_expand_payload: Callable[[Dict[str, Any]], Dict[str, Any]],
    store_expanded_plan: Callable[[Any, Dict[str, Any]], None],
    project_model_to_plan: Callable[[Any, str], Dict[str, Any]],
) -> None:
    manager = ctx.manager
    project = manager.project
    parsed = preserve_field_states(ctx.parsed)
    lot = safe_dict(unwrap_fields_for_execution(parsed.get("lot")))
    site_plan = safe_dict(unwrap_fields_for_execution(parsed.get("site_plan")))

    try:
        execution_payload = unwrap_fields_for_execution(parsed)
        expanded = legacy_expand_payload(execution_payload)
        if isinstance(expanded, dict):
            expanded_actions = filter_actions_by_field_intent(parsed, safe_list(expanded.get("actions")))
            expanded_actions = _synthesize_layout_semantics(expanded_actions)
            expanded["actions"] = expanded_actions
        if safe_list(expanded.get("actions")):
            store_expanded_plan(project, expanded)

        build_w = max(20.0, safe_float(site_plan.get("building_width"), DEFAULT_PAD_WIDTH))
        build_d = max(20.0, safe_float(site_plan.get("building_depth"), DEFAULT_PAD_DEPTH))
        lot_x = safe_float(lot.get("x"), DEFAULT_LOT_X)
        lot_y = safe_float(lot.get("y"), DEFAULT_LOT_Y)
        lot_w = safe_float(lot.get("w"), DEFAULT_LOT_WIDTH)
        lot_h = safe_float(lot.get("h"), DEFAULT_LOT_HEIGHT)
        street_edge = safe_str(execution_payload.get("street_edge"), "bottom")
        building_specs = _program_building_specs(parsed, site_plan)

        building_actions: List[Dict[str, Any]] = []
        for action in safe_list(expanded.get("actions")):
            if not isinstance(action, dict):
                continue
            if lower_text(action.get("task")) == "rectangle" and safe_str(action.get("layer")).upper() == "BUILDING":
                building_actions.append(action)

        placements: List[Dict[str, Any]] = []
        if len(building_actions) >= len(building_specs) and building_actions:
            for idx, building_action in enumerate(building_actions[: len(building_specs)]):
                origin = safe_list(building_action.get("origin"))
                bx = safe_float(origin[0], lot_x) if len(origin) >= 2 else lot_x
                by = safe_float(origin[1], lot_y) if len(origin) >= 2 else lot_y
                placements.append(
                    {
                        "name": safe_str(building_specs[idx].get("name"), safe_str(building_action.get("label"), f"BUILDING-{idx + 1}")),
                        "use": lower_text(building_specs[idx].get("use")) or "generic",
                        "x": bx,
                        "y": by,
                        "w": max(1.0, safe_float(building_action.get("width"), safe_float(building_specs[idx].get("w"), build_w))),
                        "d": max(1.0, safe_float(building_action.get("height"), safe_float(building_specs[idx].get("d"), build_d))),
                    }
                )
        else:
            placements = _synthesized_program_layout(
                lot_x=lot_x,
                lot_y=lot_y,
                lot_w=lot_w,
                lot_h=lot_h,
                street_edge=street_edge,
                specs=building_specs,
            )
            fallback_actions = []
            for placement in placements:
                fallback_actions.append(
                    {
                        "task": "rectangle",
                        "layer": "BUILDING",
                        "label": safe_str(placement.get("name"), "BUILDING"),
                        "origin": [round(safe_float(placement.get("x"), 0.0), 3), round(safe_float(placement.get("y"), 0.0), 3)],
                        "width": round(safe_float(placement.get("w"), build_w), 3),
                        "height": round(safe_float(placement.get("d"), build_d), 3),
                    }
                )
            fallback_actions.extend(
                _layout_fallback_actions(
                    placements,
                    lot_x=lot_x,
                    lot_y=lot_y,
                    lot_w=lot_w,
                    lot_h=lot_h,
                    street_edge=street_edge,
                    culdesac_count=max(0, safe_int(safe_dict(execution_payload.get("subdivision")).get("culdesac_count"), 0)),
                )
            )
            if fallback_actions:
                store_expanded_plan(
                    project,
                    {
                        "project_name": safe_str(parsed.get("project_name"), "Generated Plan"),
                        "units": safe_str(parsed.get("units"), "ft"),
                        "actions": _merge_layout_actions(safe_list(expanded.get("actions")), fallback_actions),
                        "meta": dict(expanded.get("meta") or {}),
                        "assumptions": list(expanded.get("assumptions") or []),
                    },
                )

        if not placements:
            bx = lot_x + max(5.0, (lot_w - build_w) / 2.0)
            by = lot_y + max(5.0, (lot_h - build_d) / 2.0)
            placements = [{"name": "BUILDING", "use": "generic", "x": bx, "y": by, "w": build_w, "d": build_d}]

        for placement in placements:
            px = safe_float(placement.get("x"), 0.0)
            py = safe_float(placement.get("y"), 0.0)
            pw = max(1.0, safe_float(placement.get("w"), build_w))
            pd = max(1.0, safe_float(placement.get("d"), build_d))
            pname = safe_str(placement.get("name"), "BUILDING")
            puse = lower_text(placement.get("use")) or "generic"
            zone = rect_zone(px, py, pw, pd, zone_type=ZoneType.BUILDING, name=pname)
            project.add_zone(zone)
            project.add_object(
                EngineeringObject(
                    kind=f"{puse}_building" if puse and puse != "generic" else "building",
                    name=pname,
                    anchor=Point3D(px + pw / 2.0, py + pd / 2.0, DEFAULT_PAD_ELEV),
                    boundary=zone.boundary,
                    tags=["layout", "building", puse] if puse else ["layout", "building"],
                    domain=EngineeringDomain.BUILDING,
                    properties={"width": pw, "depth": pd, "use": puse},
                )
            )

        if field_path_is_omitted(parsed, "site_plan.parking_count"):
            parking_count = 0
        else:
            parking_count = max(
                0,
                safe_int(
                    safe_dict(expanded.get("meta")).get("parking_count"),
                    safe_int(site_plan.get("parking_count"), 24),
                ),
            )
        layout_stats = collect_plan_stats(
            expanded if expanded else project_model_to_plan(project, parsed.get("project_name") or "Generated Plan")
        )
        manager.set_metric("parking_count", parking_count, category="layout")
        manager.set_metric("lot_area_sf", _lot_area(parsed), units="sf", category="layout")
        manager.set_metric("layout_success", 1.0, category="layout")
        manager.set_metric("layout_action_count", len(safe_list(expanded.get("actions"))), category="layout")
        manager.set_metric("layout_building_area_sf", safe_float(layout_stats.get("estimated_building_area_sf"), 0.0), category="layout")
        manager.set_metric("layout_parking_area_sf", safe_float(layout_stats.get("estimated_parking_area_sf"), 0.0), category="layout")
        manager.set_metric("layout_road_area_sf", safe_float(layout_stats.get("estimated_road_area_sf"), 0.0), category="layout")
        manager.set_metric("layout_impervious_area_sf", safe_float(layout_stats.get("estimated_impervious_area_sf"), 0.0), category="layout")
        _mark_dependency_state(manager, "layout", "grading", DependencyState.FRESH, reason="Layout updated.")
        manager.mark_system_complete("layout", "Layout stage completed.")
        manager.invalidate_from("layout")
        ctx.add_stage(
            "layout",
            True,
            "Layout stage completed.",
            parking_count=parking_count,
            building_width=max((safe_float(item.get("w"), 0.0) for item in placements), default=build_w),
            building_depth=max((safe_float(item.get("d"), 0.0) for item in placements), default=build_d),
            building_count=len(placements),
            expanded_action_count=len(safe_list(expanded.get("actions"))),
        )
    except Exception as exc:
        ctx.record_warning(f"Layout stage failed: {exc}")
        manager.add_conflict(
            ConflictRecord(
                code="LAYOUT_STAGE_FAILED",
                message=str(exc),
                severity=ConflictSeverity.WARNING,
                category="layout",
            )
        )
        ctx.add_stage("layout", False, f"Layout stage failed: {exc}")


def run_grading_stage(
    ctx: PlannerExecutionContext,
    hydrology: Dict[str, Any],
    *,
    strict_mode_enabled: Callable[[Dict[str, Any]], bool],
    build_existing_surface: Callable[[Dict[str, Any]], GridSurface],
    build_grade_elements: Callable[[Any, Dict[str, Any]], List[Any]],
    grading_surface_actions: Callable[[Any, Optional[GridSurface], Optional[GridSurface]], Any],
    canonical_grading_payload: Callable[..., Dict[str, Any]],
    record_strict_stage_failure: Callable[..., None],
    install_minimum_grading_actions: Callable[[Any, Dict[str, Any]], int],
    merge_actions_into_expanded_plan: Callable[[Any, Any], None],
    call_with_compatible_kwargs: Callable[..., Any],
) -> None:
    manager = ctx.manager
    project = manager.project
    parsed = ctx.parsed
    strict_mode = strict_mode_enabled(parsed)

    try:
        if field_path_is_omitted(parsed, "grading"):
            ctx.record_assumption("Grading omitted by user intent; planner preserved omission and skipped grading stage.")
            ctx.add_stage("grading", True, "Grading stage skipped because source=omit.")
            return

        execution_payload = unwrap_fields_for_execution(parsed)
        existing_surface = build_existing_surface(execution_payload)
        project.meta["existing_surface"] = existing_surface

        engine = GradingEngine(existing_surface)
        grade_elements = build_grade_elements(project, execution_payload)

        if hasattr(engine, "extend_elements"):
            engine.extend_elements(grade_elements)
        elif hasattr(engine, "elements"):
            current = list(getattr(engine, "elements", []) or [])
            current.extend(grade_elements)
            engine.elements = current

        result = None
        build_kwargs = {
            "request": GradingRequest(create_project_objects=False, create_project_zones=False),
            "project": project,
        }
        for caller in (
            lambda: call_with_compatible_kwargs(engine.build, **build_kwargs),
            lambda: call_with_compatible_kwargs(engine.build, GradingRequest(create_project_objects=False, create_project_zones=False)),
            lambda: call_with_compatible_kwargs(engine.build),
        ):
            try:
                result = caller()
                if result is not None:
                    break
            except Exception:
                continue

        if result is None and hasattr(engine, "apply_to_project"):
            result = engine.apply_to_project(
                project,
                GradingRequest(create_project_objects=False, create_project_zones=False),
            )

        if result is None:
            if strict_mode:
                manager.set_metric("grading_success", 0.0, category="grading")
                record_strict_stage_failure(
                    ctx,
                    "grading",
                    "STRICT_GRADING_FALLBACK_BLOCKED",
                    "STRICT mode blocked grading fallback because the grading engine did not produce a real surface solution.",
                    category="grading",
                    dependency="grading_engine",
                    computation_step="surface_generation",
                )
                return
            fallback_count = install_minimum_grading_actions(project, parsed)
            manager.set_metric("grading_success", 1.0, category="grading")
            manager.set_metric("grading_low_point_count", 1, category="grading")
            ctx.record_assumption("Grading engine could not build a full surface; planner installed minimum grading geometry fallback.")
            ctx.add_stage(
                "grading",
                True,
                "Grading stage completed using minimum grading fallback.",
                low_point_count=1,
                cut_cf=0.0,
                fill_cf=0.0,
                net_cf=0.0,
                added_actions=fallback_count,
                fallback_used=True,
                fallback_type="minimum_grading_geometry",
                dependency="grading_engine",
                computation_step="surface_generation",
            )
            return

        proposed_surface = getattr(result, "proposed_surface", None)
        project.meta["proposed_surface"] = proposed_surface

        low_points = safe_list(getattr(result, "low_points", []))
        flow_samples = safe_list(getattr(result, "flow_samples", []))
        cut_volume = safe_float(getattr(result, "cut_volume", 0.0), 0.0)
        fill_volume = safe_float(getattr(result, "fill_volume", 0.0), 0.0)
        net_volume = safe_float(getattr(result, "net_volume", 0.0), 0.0)
        success = bool(getattr(result, "success", True))
        message = safe_str(getattr(result, "message", "Grading stage completed."))
        grade_actions, grading_action_stats = grading_surface_actions(
            result,
            existing_surface,
            proposed_surface,
            grade_elements=grade_elements,
        )
        merge_actions_into_expanded_plan(project, grade_actions, grading_surface_export=True)
        grading_payload = canonical_grading_payload(
            existing_surface=existing_surface,
            result=result,
            derived_action_stats=grading_action_stats,
            grade_elements=grade_elements,
        )
        project.meta["grading_summary"] = grading_payload
        manager.latest_outputs["grading"] = deepcopy(grading_payload)

        manager.set_metric("grading_success", 1.0 if success else 0.0, category="grading")
        manager.set_metric("grading_low_point_count", len(low_points), category="grading")
        manager.set_metric("grading_flow_sample_count", len(flow_samples), category="grading")
        manager.set_metric("grading_proposed_contour_count", safe_int(grading_action_stats.get("proposed_contour_count"), 0), category="grading")
        manager.set_metric("grading_existing_contour_count", safe_int(grading_action_stats.get("existing_contour_count"), 0), category="grading")
        manager.set_metric("grading_spot_grade_count", safe_int(grading_action_stats.get("spot_grade_count"), 0), category="grading")
        manager.set_metric("earthwork_cut_cf", cut_volume, units="cf", category="earthwork")
        manager.set_metric("earthwork_fill_cf", fill_volume, units="cf", category="earthwork")
        manager.set_metric("earthwork_net_cf", net_volume, units="cf", category="earthwork")

        _mark_dependency_state(manager, "layout", "grading", DependencyState.FRESH, reason="Grading rebuilt from layout.")
        _mark_dependency_state(manager, "grading", "drainage", DependencyState.STALE, reason="Drainage depends on grading.")
        manager.invalidate_from("grading")

        ctx.add_stage(
            "grading",
            success,
            message,
            low_point_count=len(low_points),
            flow_sample_count=len(flow_samples),
            cut_cf=round(cut_volume, 2),
            fill_cf=round(fill_volume, 2),
            net_cf=round(net_volume, 2),
            added_actions=len(grade_actions),
            contour_count=safe_int(grading_action_stats.get("proposed_contour_count"), 0),
            spot_grade_count=safe_int(grading_action_stats.get("spot_grade_count"), 0),
            flow_arrow_count=safe_int(grading_action_stats.get("flow_arrow_count"), 0),
            terrain_inferred=bool(safe_dict(grading_payload.get("existing_surface")).get("terrain_inferred")),
        )
    except Exception as exc:
        message = f"Grading stage failed: {exc}"
        manager.set_metric("grading_success", 0.0, category="grading")
        if strict_mode:
            record_strict_stage_failure(
                ctx,
                "grading",
                "STRICT_GRADING_STAGE_FAILED",
                message,
                category="grading",
                dependency="grading_engine",
                computation_step="stage_execution",
            )
        else:
            ctx.record_warning(message)
            manager.add_conflict(
                ConflictRecord(
                    code="GRADING_STAGE_FAILED",
                    message=str(exc),
                    severity=ConflictSeverity.WARNING,
                    category="grading",
                )
            )
            ctx.add_stage("grading", False, message)
