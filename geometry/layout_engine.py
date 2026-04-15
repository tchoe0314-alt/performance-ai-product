
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple


Rect = Dict[str, float]
Point = Tuple[float, float]


# =============================================================================
# basic coercion / safety helpers
# =============================================================================

def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return int(default)
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def _safe_optional_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _safe_str(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))


def _nonempty_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


# =============================================================================
# rectangle / geometry helpers
# =============================================================================

def _rect(x: float, y: float, w: float, h: float) -> Rect:
    return {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}


def _rect_right(r: Rect) -> float:
    return r["x"] + r["w"]


def _rect_top(r: Rect) -> float:
    return r["y"] + r["h"]


def _rect_center(r: Rect) -> Point:
    return (r["x"] + r["w"] / 2.0, r["y"] + r["h"] / 2.0)


def _rect_area(r: Rect) -> float:
    return max(0.0, r["w"]) * max(0.0, r["h"])


def _rect_fits_inside(inner: Rect, outer: Rect, tol: float = 0.0) -> bool:
    return (
        inner["x"] >= outer["x"] - tol
        and inner["y"] >= outer["y"] - tol
        and _rect_right(inner) <= _rect_right(outer) + tol
        and _rect_top(inner) <= _rect_top(outer) + tol
    )


def _rects_overlap(a: Rect, b: Rect, tol: float = 0.0) -> bool:
    return not (
        _rect_right(a) <= b["x"] + tol
        or _rect_right(b) <= a["x"] + tol
        or _rect_top(a) <= b["y"] + tol
        or _rect_top(b) <= a["y"] + tol
    )


def _move_rect_inside(r: Rect, outer: Rect) -> Rect:
    r = dict(r)
    r["x"] = _clamp(r["x"], outer["x"], _rect_right(outer) - r["w"])
    r["y"] = _clamp(r["y"], outer["y"], _rect_top(outer) - r["h"])
    return r


def _centered_in(parent: Rect, w: float, h: float) -> Rect:
    return _rect(
        parent["x"] + (parent["w"] - w) / 2.0,
        parent["y"] + (parent["h"] - h) / 2.0,
        w,
        h,
    )


def _expand_rect(r: Rect, offset: float) -> Rect:
    return _rect(r["x"] - offset, r["y"] - offset, r["w"] + 2.0 * offset, r["h"] + 2.0 * offset)


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _polyline_length(points: Sequence[Point]) -> float:
    total = 0.0
    for i in range(1, len(points)):
        total += _distance(points[i - 1], points[i])
    return total


def _buildable_area(lot: Rect, setback: float) -> Rect:
    return _rect(
        lot["x"] + setback,
        lot["y"] + setback,
        max(0.0, lot["w"] - 2.0 * setback),
        max(0.0, lot["h"] - 2.0 * setback),
    )


# =============================================================================
# normalization
# =============================================================================

def _normalize_site_type(site_type: str) -> str:
    st = (site_type or "commercial_pad").lower().strip()
    aliases = {
        "retail": "commercial_pad",
        "restaurant": "commercial_pad",
        "pad": "commercial_pad",
        "commercial": "commercial_pad",
        "office": "office_site",
        "warehouse": "industrial_site",
        "industrial": "industrial_site",
        "stripmall": "strip_center",
        "strip_center": "strip_center",
        "mixed_use": "mixed_use",
        "mixed-use": "mixed_use",
        "mixed_use_site": "mixed_use",
        "multifamily": "multifamily_site",
        "multi_family": "multifamily_site",
        "apartment": "multifamily_site",
        "residential_subdivision": "subdivision_site",
        "subdivision": "subdivision_site",
    }
    return aliases.get(st, st)


def _normalize_layout_strategy(layout_strategy: str) -> str:
    ls = (layout_strategy or "front_parking").lower().strip()
    aliases = {
        "front": "front_parking",
        "front parking": "front_parking",
        "rear": "rear_parking",
        "rear parking": "rear_parking",
        "rear building": "rear_building",
        "side": "side_parking",
        "side parking": "side_parking",
        "street": "street_building",
        "street building": "street_building",
        "building courts": "building_courts",
        "courts": "building_courts",
        "cluster": "building_courts",
        "double_loaded": "double_loaded_court",
        "court": "double_loaded_court",
    }
    return aliases.get(ls, ls)


def _normalize_street_edge(street_edge: str) -> str:
    se = (street_edge or "bottom").lower().strip()
    aliases = {
        "north": "top",
        "north side": "top",
        "north frontage": "top",
        "south": "bottom",
        "south side": "bottom",
        "south frontage": "bottom",
        "east": "right",
        "east side": "right",
        "east frontage": "right",
        "west": "left",
        "west side": "left",
        "west frontage": "left",
        "front": "bottom",
    }
    se = aliases.get(se, se)
    if se not in {"bottom", "top", "left", "right"}:
        return "bottom"
    return se


def _opposite_edge(edge: str) -> str:
    edge = _normalize_street_edge(edge)
    return {"bottom": "top", "top": "bottom", "left": "right", "right": "left"}[edge]


# =============================================================================
# program defaults / standards
# =============================================================================

def _parking_standards(parsed: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    parsed = parsed or {}
    site_plan = parsed.get("site_plan") or {}
    parking = parsed.get("parking") or {}

    stall_w = _safe_float(
        parking.get("stall_width", site_plan.get("stall_width")),
        9.0,
    )
    stall_d = _safe_float(
        parking.get("stall_depth", site_plan.get("stall_depth")),
        18.0,
    )
    aisle_w = _safe_float(
        parking.get("aisle_width", site_plan.get("aisle_width")),
        24.0,
    )
    landscape_island_w = _safe_float(parking.get("island_width"), 9.0)
    curb_offset = _safe_float(parking.get("curb_offset"), 0.5)
    sidewalk_w = _safe_float((parsed.get("sidewalk") or {}).get("width"), 5.0)

    return {
        "stall_width": max(8.5, stall_w),
        "stall_depth": max(17.0, stall_d),
        "aisle_width": max(22.0, aisle_w),
        "module_depth": max(17.0, stall_d) * 2.0 + max(22.0, aisle_w),
        "island_width": max(8.0, landscape_island_w),
        "curb_offset": max(0.0, curb_offset),
        "sidewalk_width": max(4.0, sidewalk_w),
    }


def _road_standards(parsed: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    parsed = parsed or {}
    road = parsed.get("road") or {}
    site_plan = parsed.get("site_plan") or {}
    return {
        "drive_width": max(24.0, _safe_float(road.get("drive_width", site_plan.get("drive_width")), 24.0)),
        "fire_lane_width": max(20.0, _safe_float(road.get("fire_lane_width"), 24.0)),
        "curb_return_radius": max(20.0, _safe_float(road.get("curb_return_radius"), 28.0)),
        "frontage_road_depth": max(24.0, _safe_float(road.get("frontage_road_depth"), 28.0)),
    }


def _choose_program_defaults(site_type: str, intensity: str) -> Dict[str, float]:
    site_type = _normalize_site_type(site_type)
    intensity = (intensity or "medium").lower().strip()

    if site_type == "strip_center":
        return {
            "building_width_ratio": 0.58 if intensity != "large" else 0.68,
            "building_depth_ratio": 0.20 if intensity != "large" else 0.24,
            "parking_depth": 60.0,
            "front_offset": 12.0,
            "target_stalls_per_ksf": 4.5,
        }

    if site_type == "industrial_site":
        return {
            "building_width_ratio": 0.52 if intensity != "large" else 0.62,
            "building_depth_ratio": 0.36 if intensity != "large" else 0.44,
            "parking_depth": 60.0,
            "front_offset": 16.0,
            "target_stalls_per_ksf": 1.2,
        }

    if site_type == "office_site":
        return {
            "building_width_ratio": 0.46 if intensity != "large" else 0.52,
            "building_depth_ratio": 0.28 if intensity != "large" else 0.34,
            "parking_depth": 60.0,
            "front_offset": 12.0,
            "target_stalls_per_ksf": 3.5,
        }

    if site_type == "multifamily_site":
        return {
            "building_width_ratio": 0.50 if intensity != "large" else 0.58,
            "building_depth_ratio": 0.30 if intensity != "large" else 0.34,
            "parking_depth": 60.0,
            "front_offset": 12.0,
            "target_stalls_per_ksf": 2.2,
        }

    if site_type == "subdivision_site":
        return {
            "building_width_ratio": 0.30,
            "building_depth_ratio": 0.20,
            "parking_depth": 0.0,
            "front_offset": 0.0,
            "target_stalls_per_ksf": 0.0,
        }

    return {
        "building_width_ratio": 0.48 if intensity != "large" else 0.56,
        "building_depth_ratio": 0.30 if intensity != "large" else 0.36,
        "parking_depth": 60.0,
        "front_offset": 12.0,
        "target_stalls_per_ksf": 4.0,
    }


# =============================================================================
# building sizing / placement
# =============================================================================

def _choose_building_size(
    buildable: Rect,
    site_type: str,
    intensity: str,
    building_width: Optional[float] = None,
    building_depth: Optional[float] = None,
) -> Dict[str, float]:
    defaults = _choose_program_defaults(site_type, intensity)

    if building_width is None:
        building_width = buildable["w"] * defaults["building_width_ratio"]
    if building_depth is None:
        building_depth = buildable["h"] * defaults["building_depth_ratio"]

    building_width = max(30.0, min(building_width, buildable["w"] * 0.88))
    building_depth = max(24.0, min(building_depth, buildable["h"] * 0.78))

    return {"w": building_width, "h": building_depth}


def _position_building(
    buildable: Rect,
    building_size: Dict[str, float],
    street_edge: str,
    layout_strategy: str,
    edge_margin: Optional[float] = None,
) -> Rect:
    street_edge = _normalize_street_edge(street_edge)
    layout_strategy = _normalize_layout_strategy(layout_strategy)

    b = _centered_in(buildable, building_size["w"], building_size["h"])
    if edge_margin is None:
        edge_margin = 0.0 if layout_strategy in {"front_parking", "rear_parking", "side_parking"} else 10.0

    if layout_strategy in {"street_building", "front_parking"}:
        if street_edge == "bottom":
            b["y"] = _rect_top(buildable) - b["h"] - edge_margin
        elif street_edge == "top":
            b["y"] = buildable["y"] + edge_margin
        elif street_edge == "left":
            b["x"] = _rect_right(buildable) - b["w"] - edge_margin
        elif street_edge == "right":
            b["x"] = buildable["x"] + edge_margin

    elif layout_strategy in {"rear_building", "rear_parking"}:
        if street_edge == "bottom":
            b["y"] = buildable["y"] + edge_margin
        elif street_edge == "top":
            b["y"] = _rect_top(buildable) - b["h"] - edge_margin
        elif street_edge == "left":
            b["x"] = buildable["x"] + edge_margin
        elif street_edge == "right":
            b["x"] = _rect_right(buildable) - b["w"] - edge_margin

    elif layout_strategy in {"side_parking", "building_courts", "double_loaded_court"}:
        if street_edge in {"bottom", "top"}:
            b["x"] = buildable["x"] + buildable["w"] * 0.62 - b["w"] / 2.0
        else:
            b["y"] = buildable["y"] + buildable["h"] * 0.62 - b["h"] / 2.0

    return _move_rect_inside(b, buildable)


# =============================================================================
# parking geometry
# =============================================================================

def _parking_count_from_program(
    building: Rect,
    site_type: str,
    intensity: str,
    explicit_count: Optional[int],
) -> int:
    if explicit_count is not None and explicit_count > 0:
        return explicit_count

    defaults = _choose_program_defaults(site_type, intensity)
    area_ksf = _rect_area(building) / 1000.0
    raw = area_ksf * defaults["target_stalls_per_ksf"]

    if site_type == "multifamily_site":
        return max(18, int(round(raw)))
    if site_type == "industrial_site":
        return max(12, int(round(raw)))
    return max(20, int(round(raw)))


def _effective_front_offset(
    building: Rect,
    buildable: Rect,
    street_edge: str,
    requested_offset: float,
    module_depth: float,
) -> float:
    street_edge = _normalize_street_edge(street_edge)

    if street_edge == "bottom":
        available = building["y"] - buildable["y"] - module_depth
    elif street_edge == "top":
        available = _rect_top(buildable) - _rect_top(building) - module_depth
    elif street_edge == "left":
        available = buildable["x"] + buildable["w"] - _rect_right(building) - module_depth
    else:
        available = building["x"] - buildable["x"] - module_depth

    if available <= 0.0:
        return 0.0
    return min(requested_offset, max(0.0, available))


def _parking_area_candidate_parallel_to_edge(
    building: Rect,
    buildable: Rect,
    street_edge: str,
    site_type: str,
    intensity: str,
    desired_count: int,
    standards: Dict[str, float],
) -> Rect:
    street_edge = _normalize_street_edge(street_edge)
    module_depth = standards["module_depth"]
    front_offset = _effective_front_offset(
        building,
        buildable,
        street_edge,
        _choose_program_defaults(site_type, intensity)["front_offset"],
        module_depth,
    )
    stall_width = standards["stall_width"]

    stalls_per_row = max(4, int(math.ceil(desired_count / 2.0)))
    width_needed = max(36.0, stalls_per_row * stall_width)

    if street_edge in {"bottom", "top"}:
        width = min(buildable["w"], max(width_needed, building["w"] * 1.10, buildable["w"] * 0.52))
        x = building["x"] - (width - building["w"]) / 2.0
        x = _clamp(x, buildable["x"], _rect_right(buildable) - width)

        if street_edge == "bottom":
            y = building["y"] - front_offset - module_depth
        else:
            y = _rect_top(building) + front_offset
        return _rect(x, y, width, module_depth)

    height = min(buildable["h"], max(width_needed, building["h"] * 1.15, buildable["h"] * 0.52))
    y = building["y"] - (height - building["h"]) / 2.0
    y = _clamp(y, buildable["y"], _rect_top(buildable) - height)

    if street_edge == "left":
        x = _rect_right(building) + front_offset
    else:
        x = building["x"] - front_offset - module_depth
    return _rect(x, y, module_depth, height)


def _side_parking_candidates(
    building: Rect,
    buildable: Rect,
    desired_count: int,
    standards: Dict[str, float],
) -> List[Rect]:
    module_depth = standards["module_depth"]
    stall_width = standards["stall_width"]

    stalls_single = max(4, int(math.ceil(desired_count / 2.0)))
    side_len = max(40.0, stalls_single * stall_width)
    side_len = min(side_len, buildable["h"] if buildable["h"] >= buildable["w"] else buildable["w"])

    left = _rect(
        building["x"] - 14.0 - module_depth,
        _clamp(building["y"] - 4.0, buildable["y"], _rect_top(buildable) - side_len),
        module_depth,
        min(side_len, buildable["h"]),
    )
    right = _rect(
        _rect_right(building) + 14.0,
        _clamp(building["y"] - 4.0, buildable["y"], _rect_top(buildable) - side_len),
        module_depth,
        min(side_len, buildable["h"]),
    )
    return [left, right]


def _gap_along_street_axis(building: Rect, parking: Rect, street_edge: str) -> float:
    if street_edge == "bottom":
        return building["y"] - _rect_top(parking)
    if street_edge == "top":
        return parking["y"] - _rect_top(building)
    if street_edge == "left":
        return parking["x"] - _rect_right(building)
    return building["x"] - _rect_right(parking)


def _score_parking_candidate(
    candidate: Rect,
    buildable: Rect,
    building: Rect,
    street_edge: str,
    preferred_front: bool,
    desired_count: int,
    standards: Dict[str, float],
) -> float:
    if not _rect_fits_inside(candidate, buildable):
        return -1e9
    if _rects_overlap(candidate, building, tol=0.01):
        return -1e9

    capacity = _estimate_parking_capacity(candidate, standards)
    if capacity <= 0:
        return -1e9

    cx, cy = _rect_center(candidate)
    bx, by = _rect_center(building)
    center_distance = abs(cx - bx) + abs(cy - by)
    area_score = candidate["w"] * candidate["h"] * 0.003
    front_gap = _gap_along_street_axis(building, candidate, street_edge)

    front_bonus = 55.0 if preferred_front else 0.0
    correct_side_bonus = 35.0 if front_gap >= 6.0 else -70.0
    capacity_bonus = -abs(capacity - desired_count) * 1.2
    compactness_penalty = max(candidate["w"], candidate["h"]) / max(1.0, min(candidate["w"], candidate["h"]))

    return area_score + front_bonus + correct_side_bonus + capacity_bonus - center_distance * 0.12 - compactness_penalty * 8.0


def _minimum_axis_gap(building: Rect, parking: Rect, street_edge: str, standards: Dict[str, float]) -> float:
    # keep a minimum separation so aisle/walk/front offset logic does not collapse into the building
    front_offset = max(6.0, standards.get("sidewalk_width", 5.0) + 4.0)
    if street_edge in {"bottom", "top"}:
        return front_offset
    return front_offset


def _separate_rect_from_building(
    parking: Rect,
    building: Rect,
    buildable: Rect,
    street_edge: str,
    standards: Dict[str, float],
) -> Rect:
    """
    Push parking away from the building along the controlling street axis first,
    then clamp back inside the buildable area. This is the hardening fix for the
    runtime failure where parking overlapped the building after candidate selection.
    """
    p = dict(parking)
    gap = _minimum_axis_gap(building, p, street_edge, standards)

    if street_edge == "bottom":
        desired_top = building["y"] - gap
        p["y"] = desired_top - p["h"]
    elif street_edge == "top":
        desired_y = _rect_top(building) + gap
        p["y"] = desired_y
    elif street_edge == "left":
        desired_x = _rect_right(building) + gap
        p["x"] = desired_x
    else:  # right
        desired_right = building["x"] - gap
        p["x"] = desired_right - p["w"]

    p = _move_rect_inside(p, buildable)
    return p


def _candidate_nudge_variants(base: Rect, buildable: Rect, step: float = 6.0, max_steps: int = 12) -> List[Rect]:
    variants: List[Rect] = [dict(base)]
    for i in range(1, max_steps + 1):
        d = step * i
        variants.extend([
            _move_rect_inside(_rect(base["x"], base["y"] + d, base["w"], base["h"]), buildable),
            _move_rect_inside(_rect(base["x"], base["y"] - d, base["w"], base["h"]), buildable),
            _move_rect_inside(_rect(base["x"] + d, base["y"], base["w"], base["h"]), buildable),
            _move_rect_inside(_rect(base["x"] - d, base["y"], base["w"], base["h"]), buildable),
        ])
    return variants


def _select_non_overlapping_candidate(
    candidates: List[Rect],
    buildable: Rect,
    building: Rect,
    street_edge: str,
    preferred_front: bool,
    desired_count: int,
    standards: Dict[str, float],
) -> Optional[Rect]:
    viable: List[Rect] = []

    for candidate in candidates:
        c = _move_rect_inside(candidate, buildable)
        if not _rects_overlap(c, building, tol=0.01):
            viable.append(c)

        separated = _separate_rect_from_building(c, building, buildable, street_edge, standards)
        if not _rects_overlap(separated, building, tol=0.01):
            viable.append(separated)

        for variant in _candidate_nudge_variants(separated, buildable):
            if not _rects_overlap(variant, building, tol=0.01):
                viable.append(variant)

    if not viable:
        return None

    return max(
        viable,
        key=lambda c: _score_parking_candidate(
            c, buildable, building, street_edge, preferred_front, desired_count, standards
        ),
    )


def _choose_best_parking(
    building: Rect,
    buildable: Rect,
    street_edge: str,
    layout_strategy: str,
    site_type: str,
    intensity: str,
    desired_count: int,
    standards: Dict[str, float],
) -> Rect:
    layout_strategy = _normalize_layout_strategy(layout_strategy)
    street_edge = _normalize_street_edge(street_edge)

    candidates: List[Rect] = []
    preferred_front = False

    if layout_strategy == "rear_parking":
        candidates.append(
            _parking_area_candidate_parallel_to_edge(
                building, buildable, _opposite_edge(street_edge), site_type, intensity, desired_count, standards
            )
        )
        candidates.extend(_side_parking_candidates(building, buildable, desired_count, standards))

    elif layout_strategy == "side_parking":
        candidates.extend(_side_parking_candidates(building, buildable, desired_count, standards))
        candidates.append(
            _parking_area_candidate_parallel_to_edge(
                building, buildable, street_edge, site_type, intensity, desired_count, standards
            )
        )

    elif layout_strategy == "street_building":
        candidates.append(
            _parking_area_candidate_parallel_to_edge(
                building, buildable, _opposite_edge(street_edge), site_type, intensity, desired_count, standards
            )
        )
        candidates.extend(_side_parking_candidates(building, buildable, desired_count, standards))

    else:
        candidates.append(
            _parking_area_candidate_parallel_to_edge(
                building, buildable, street_edge, site_type, intensity, desired_count, standards
            )
        )
        candidates.extend(_side_parking_candidates(building, buildable, desired_count, standards))
        candidates.append(
            _parking_area_candidate_parallel_to_edge(
                building, buildable, _opposite_edge(street_edge), site_type, intensity, desired_count, standards
            )
        )
        preferred_front = True

    chosen = _select_non_overlapping_candidate(
        candidates, buildable, building, street_edge, preferred_front, desired_count, standards
    )
    if chosen is not None:
        return chosen

    # Final defensive fallback: shrink the parking pad slightly and place it on the street side.
    fallback = _parking_area_candidate_parallel_to_edge(
        building, buildable, street_edge, site_type, intensity, desired_count, standards
    )
    fallback["w"] = min(fallback["w"], max(30.0, buildable["w"] * 0.42))
    fallback["h"] = min(fallback["h"], max(26.0, buildable["h"] * 0.30))
    fallback = _separate_rect_from_building(fallback, building, buildable, street_edge, standards)
    fallback = _move_rect_inside(fallback, buildable)
    return fallback


def _estimate_parking_capacity(parking: Rect, standards: Dict[str, float]) -> int:
    stall_w = standards["stall_width"]
    module_depth = standards["module_depth"]

    if parking["w"] >= parking["h"]:
        if parking["h"] >= module_depth - 1.0:
            return max(0, 2 * int(parking["w"] // stall_w))
        return max(0, int(parking["w"] // stall_w))
    else:
        if parking["w"] >= module_depth - 1.0:
            return max(0, 2 * int(parking["h"] // stall_w))
        return max(0, int(parking["h"] // stall_w))


def _parking_orientation(parking: Rect, standards: Dict[str, float]) -> str:
    if parking["h"] >= standards["module_depth"] - 1.0 and parking["w"] >= parking["h"]:
        return "horizontal"
    if parking["w"] >= standards["module_depth"] - 1.0 and parking["h"] > parking["w"]:
        return "vertical"
    if parking["w"] >= parking["h"]:
        return "horizontal_single"
    return "vertical_single"


def _generate_parking_stall_lines(parking: Rect, standards: Dict[str, float], requested_count: int) -> List[List[List[float]]]:
    stall_w = standards["stall_width"]
    stall_d = standards["stall_depth"]
    aisle_w = standards["aisle_width"]
    orient = _parking_orientation(parking, standards)
    lines: List[List[List[float]]] = []

    if orient.startswith("horizontal"):
        row_count = 2 if orient == "horizontal" else 1
        capacity_per_row = int(parking["w"] // stall_w)
        stall_count = min(requested_count, capacity_per_row * row_count)

        for i in range(capacity_per_row + 1):
            x = parking["x"] + i * stall_w
            if x > _rect_right(parking) + 0.01:
                break

            if row_count >= 1:
                y1 = parking["y"]
                y2 = parking["y"] + stall_d
                if y2 <= _rect_top(parking) + 0.01:
                    lines.append([[x, y1], [x, y2]])

            if row_count == 2:
                y3 = _rect_top(parking) - stall_d
                y4 = _rect_top(parking)
                if y3 >= parking["y"] - 0.01:
                    lines.append([[x, y3], [x, y4]])

        if row_count == 2:
            lines.append([[parking["x"], parking["y"] + stall_d], [_rect_right(parking), parking["y"] + stall_d]])
            lines.append([[parking["x"], _rect_top(parking) - stall_d], [_rect_right(parking), _rect_top(parking) - stall_d]])
            if parking["h"] >= 2.0 * stall_d + aisle_w:
                lines.append(
                    [
                        [parking["x"], parking["y"] + stall_d + aisle_w / 2.0],
                        [_rect_right(parking), parking["y"] + stall_d + aisle_w / 2.0],
                    ]
                )
        return lines[: max(0, stall_count * 2 + 4)]

    row_count = 2 if orient == "vertical" else 1
    capacity_per_row = int(parking["h"] // stall_w)
    stall_count = min(requested_count, capacity_per_row * row_count)

    for i in range(capacity_per_row + 1):
        y = parking["y"] + i * stall_w
        if y > _rect_top(parking) + 0.01:
            break

        if row_count >= 1:
            x1 = parking["x"]
            x2 = parking["x"] + stall_d
            if x2 <= _rect_right(parking) + 0.01:
                lines.append([[x1, y], [x2, y]])

        if row_count == 2:
            x3 = _rect_right(parking) - stall_d
            x4 = _rect_right(parking)
            if x3 >= parking["x"] - 0.01:
                lines.append([[x3, y], [x4, y]])

    if row_count == 2:
        lines.append([[parking["x"] + stall_d, parking["y"]], [parking["x"] + stall_d, _rect_top(parking)]])
        lines.append([[_rect_right(parking) - stall_d, parking["y"]], [_rect_right(parking) - stall_d, _rect_top(parking)]])
        if parking["w"] >= 2.0 * stall_d + aisle_w:
            lines.append(
                [
                    [parking["x"] + stall_d + aisle_w / 2.0, parking["y"]],
                    [parking["x"] + stall_d + aisle_w / 2.0, _rect_top(parking)],
                ]
            )
    return lines[: max(0, stall_count * 2 + 4)]


# =============================================================================
# road / driveway / sidewalks
# =============================================================================

def _driveway_from_bottom(lot: Rect, parking: Rect, road_standards: Dict[str, float]) -> Rect:
    drive_w = min(32.0, max(24.0, road_standards["drive_width"]))
    x = parking["x"] + (parking["w"] - drive_w) / 2.0
    return _rect(x, lot["y"], drive_w, max(18.0, parking["y"] - lot["y"]))


def _driveway_from_top(lot: Rect, parking: Rect, road_standards: Dict[str, float]) -> Rect:
    drive_w = min(32.0, max(24.0, road_standards["drive_width"]))
    x = parking["x"] + (parking["w"] - drive_w) / 2.0
    y = _rect_top(parking)
    return _rect(x, y, drive_w, max(18.0, _rect_top(lot) - y))


def _driveway_from_left(lot: Rect, parking: Rect, road_standards: Dict[str, float]) -> Rect:
    drive_h = min(26.0, max(20.0, road_standards["drive_width"]))
    y = parking["y"] + (parking["h"] - drive_h) / 2.0
    return _rect(lot["x"], y, max(18.0, parking["x"] - lot["x"]), drive_h)


def _driveway_from_right(lot: Rect, parking: Rect, road_standards: Dict[str, float]) -> Rect:
    drive_h = min(26.0, max(20.0, road_standards["drive_width"]))
    y = parking["y"] + (parking["h"] - drive_h) / 2.0
    x = _rect_right(parking)
    return _rect(x, y, max(18.0, _rect_right(lot) - x), drive_h)


def _choose_best_driveway(lot: Rect, parking: Rect, street_edge: str, road_standards: Dict[str, float]) -> Rect:
    street_edge = _normalize_street_edge(street_edge)
    if street_edge == "top":
        return _driveway_from_top(lot, parking, road_standards)
    if street_edge == "left":
        return _driveway_from_left(lot, parking, road_standards)
    if street_edge == "right":
        return _driveway_from_right(lot, parking, road_standards)
    return _driveway_from_bottom(lot, parking, road_standards)


def _frontage_road_rect(lot: Rect, street_edge: str, road_standards: Dict[str, float]) -> Rect:
    depth = road_standards["frontage_road_depth"]
    street_edge = _normalize_street_edge(street_edge)
    if street_edge == "bottom":
        return _rect(lot["x"], lot["y"], lot["w"], depth)
    if street_edge == "top":
        return _rect(lot["x"], _rect_top(lot) - depth, lot["w"], depth)
    if street_edge == "left":
        return _rect(lot["x"], lot["y"], depth, lot["h"])
    return _rect(_rect_right(lot) - depth, lot["y"], depth, lot["h"])


def _driveway_centerline(driveway: Rect) -> List[List[float]]:
    if driveway["w"] >= driveway["h"]:
        y = driveway["y"] + driveway["h"] / 2.0
        return [[driveway["x"], y], [_rect_right(driveway), y]]
    x = driveway["x"] + driveway["w"] / 2.0
    return [[x, driveway["y"]], [x, _rect_top(driveway)]]


def _local_collector_from_parking(parking: Rect, lot: Rect, street_edge: str, road_standards: Dict[str, float]) -> Rect:
    street_edge = _normalize_street_edge(street_edge)
    depth = min(18.0, max(10.0, road_standards["drive_width"] * 0.6))
    offset = 2.0

    if street_edge == "bottom":
        width = min(parking["w"] + 4.0, lot["w"] * 0.78)
        x = _clamp(parking["x"] - 2.0, lot["x"], _rect_right(lot) - width)
        y = max(lot["y"], parking["y"] - depth - offset)
        return _rect(x, y, width, depth)
    if street_edge == "top":
        width = min(parking["w"] + 4.0, lot["w"] * 0.78)
        x = _clamp(parking["x"] - 2.0, lot["x"], _rect_right(lot) - width)
        y = min(_rect_top(lot) - depth, _rect_top(parking) + offset)
        return _rect(x, y, width, depth)
    if street_edge == "left":
        height = min(parking["h"] + 4.0, lot["h"] * 0.78)
        y = _clamp(parking["y"] - 2.0, lot["y"], _rect_top(lot) - height)
        x = max(lot["x"], parking["x"] - depth - offset)
        return _rect(x, y, depth, height)

    height = min(parking["h"] + 4.0, lot["h"] * 0.78)
    y = _clamp(parking["y"] - 2.0, lot["y"], _rect_top(lot) - height)
    x = min(_rect_right(lot) - depth, _rect_right(parking) + offset)
    return _rect(x, y, depth, height)


def _building_entry_point(building: Rect, street_edge: str) -> Point:
    street_edge = _normalize_street_edge(street_edge)
    if street_edge == "bottom":
        return (building["x"] + building["w"] / 2.0, building["y"])
    if street_edge == "top":
        return (building["x"] + building["w"] / 2.0, _rect_top(building))
    if street_edge == "left":
        return (building["x"], building["y"] + building["h"] / 2.0)
    return (_rect_right(building), building["y"] + building["h"] / 2.0)


def _parking_connection_point(parking: Rect, building: Rect) -> Point:
    bx, by = _rect_center(building)
    px, py = _rect_center(parking)

    if parking["w"] >= parking["h"]:
        if py < by:
            return (px, _rect_top(parking))
        return (px, parking["y"])
    else:
        if px < bx:
            return (_rect_right(parking), py)
        return (parking["x"], py)


def _generate_sidewalks(layout: Dict[str, Any], standards: Dict[str, float]) -> List[Dict[str, Any]]:
    building = layout["building"]
    parking = layout["parking"]
    street_edge = layout["street_edge"]
    width = standards["sidewalk_width"]

    entry = _building_entry_point(building, street_edge)
    parking_pt = _parking_connection_point(parking, building)

    points = [list(entry), [parking_pt[0], parking_pt[1]]]
    return [
        {
            "label": "WALK-1",
            "points": points,
            "width": width,
            "ada_required": True,
            "layer": "WALK",
        }
    ]


def _generate_fire_lane(layout: Dict[str, Any], road_standards: Dict[str, float]) -> Optional[Dict[str, Any]]:
    building = layout["building"]
    buildable = layout["buildable"]
    street_edge = layout["street_edge"]
    width = road_standards["fire_lane_width"]

    if street_edge in {"bottom", "top"}:
        y = max(buildable["y"], building["y"] - width - 8.0)
        if street_edge == "top":
            y = min(_rect_top(buildable) - width, _rect_top(building) + 8.0)
        pts = [[buildable["x"], y + width / 2.0], [_rect_right(buildable), y + width / 2.0]]
    else:
        x = max(buildable["x"], building["x"] - width - 8.0)
        if street_edge == "right":
            x = min(_rect_right(buildable) - width, _rect_right(building) + 8.0)
        pts = [[x + width / 2.0, buildable["y"]], [x + width / 2.0, _rect_top(buildable)]]

    return {
        "label": "FIRE-1",
        "points": pts,
        "width": width,
        "type": "fire_lane",
        "layer": "PAVEMENT",
        "fire_access": True,
        "synthetic_fire_lane": True,
    }


# =============================================================================
# optional extras
# =============================================================================

def _generate_optional_site_objects(layout: Dict[str, Any], site_type: str) -> Dict[str, Any]:
    site_type = _normalize_site_type(site_type)
    lot = layout["lot"]
    building = layout["building"]
    parking = layout["parking"]
    buildable = layout["buildable"]

    extras: Dict[str, Any] = {
        "future_pad": None,
        "loading_area": None,
        "internal_lane": None,
    }

    if site_type == "industrial_site":
        candidate = _rect(building["x"], _rect_top(building) + 10.0, building["w"] * 0.60, 18.0)
        if _rect_fits_inside(candidate, buildable):
            extras["loading_area"] = candidate

    elif site_type == "strip_center":
        candidate = _rect(parking["x"], _rect_top(parking) + 6.0, parking["w"], 18.0)
        if _rect_fits_inside(candidate, buildable):
            extras["internal_lane"] = candidate

    else:
        candidate = _rect(
            lot["x"] + lot["w"] * 0.05,
            lot["y"] + lot["h"] * 0.05,
            min(22.0, lot["w"] * 0.18),
            min(16.0, lot["h"] * 0.14),
        )
        if _rect_fits_inside(candidate, buildable):
            extras["future_pad"] = candidate

    return extras


# =============================================================================
# public single-layout generation
# =============================================================================

def generate_smart_layout(
    lot: Rect,
    setback: float,
    building_width: Optional[float] = None,
    building_depth: Optional[float] = None,
    layout_strategy: str = "front_parking",
    street_edge: str = "bottom",
    intensity: str = "medium",
    site_type: str = "commercial_pad",
    parking_count: Optional[int] = None,
) -> Dict[str, Any]:
    site_type = _normalize_site_type(site_type)
    layout_strategy = _normalize_layout_strategy(layout_strategy)
    street_edge = _normalize_street_edge(street_edge)

    lot = _rect(
        _safe_float(lot.get("x"), 0.0),
        _safe_float(lot.get("y"), 0.0),
        _safe_float(lot.get("w"), 120.0),
        _safe_float(lot.get("h"), 100.0),
    )

    setback = max(0.0, _safe_float(setback, 10.0))
    buildable = _buildable_area(lot, setback)
    if buildable["w"] <= 0 or buildable["h"] <= 0:
        raise ValueError("Invalid buildable area. Check lot size and setback.")

    parsed_defaults = {
        "site_plan": {"parking_count": parking_count} if parking_count is not None else {},
    }
    parking_stds = _parking_standards(parsed_defaults)
    road_stds = _road_standards(parsed_defaults)

    building_size = _choose_building_size(
        buildable=buildable,
        site_type=site_type,
        intensity=intensity,
        building_width=building_width,
        building_depth=building_depth,
    )

    building = _position_building(
        buildable=buildable,
        building_size=building_size,
        street_edge=street_edge,
        layout_strategy=layout_strategy,
    )

    desired_count = _parking_count_from_program(building, site_type, intensity, parking_count)

    parking = _choose_best_parking(
        building=building,
        buildable=buildable,
        street_edge=street_edge,
        layout_strategy=layout_strategy,
        site_type=site_type,
        intensity=intensity,
        desired_count=desired_count,
        standards=parking_stds,
    )
    parking = _move_rect_inside(parking, buildable)

    if _rects_overlap(parking, building, tol=0.01):
        raise ValueError("Parking overlaps building after layout generation.")

    driveway = _choose_best_driveway(
        lot=lot,
        parking=parking,
        street_edge=street_edge,
        road_standards=road_stds,
    )

    frontage_road = _frontage_road_rect(lot, street_edge, road_stds)
    sidewalks = _generate_sidewalks(
        {
            "building": building,
            "parking": parking,
            "street_edge": street_edge,
        },
        parking_stds,
    )
    fire_lane = _generate_fire_lane(
        {
            "building": building,
            "buildable": buildable,
            "street_edge": street_edge,
        },
        road_stds,
    )

    layout = {
        "lot": lot,
        "setback": setback,
        "buildable": buildable,
        "building": building,
        "parking": parking,
        "driveway": driveway,
        "frontage_road": frontage_road,
        "sidewalks": sidewalks,
        "fire_lane": fire_lane,
        "parking_count": min(desired_count, _estimate_parking_capacity(parking, parking_stds)),
        "parking_stall_lines": _generate_parking_stall_lines(parking, parking_stds, desired_count),
        "parking_standards": parking_stds,
        "road_standards": road_stds,
        "layout_strategy": layout_strategy,
        "street_edge": street_edge,
        "intensity": intensity,
        "site_type": site_type,
    }

    layout.update(_generate_optional_site_objects(layout, site_type))
    return layout


def generate_ai_guided_layout(parsed: Dict[str, Any]) -> Dict[str, Any]:
    lot = parsed.get("lot") or {
        "x": 0.0,
        "y": 0.0,
        "w": 120.0,
        "h": 100.0,
    }

    safe_lot = {
        "x": _safe_float(lot.get("x"), 0.0),
        "y": _safe_float(lot.get("y"), 0.0),
        "w": _safe_float(lot.get("w"), 120.0),
        "h": _safe_float(lot.get("h"), 100.0),
    }

    site_plan = parsed.get("site_plan") or {}
    return generate_smart_layout(
        lot=safe_lot,
        setback=_safe_float(parsed.get("setback"), 10.0),
        building_width=_safe_optional_float(parsed.get("building_width")),
        building_depth=_safe_optional_float(parsed.get("building_depth")),
        layout_strategy=_safe_str(parsed.get("layout_strategy"), "front_parking"),
        street_edge=_safe_str(parsed.get("street_edge"), "bottom"),
        intensity=_safe_str(parsed.get("intensity"), "medium"),
        site_type=_safe_str(parsed.get("site_type"), "commercial_pad"),
        parking_count=_safe_int(site_plan.get("parking_count"), 0) or None,
    )


# =============================================================================
# actions
# =============================================================================

def _rect_action_from_obj(obj: Rect, label: str, layer: str) -> Dict[str, Any]:
    return {
        "task": "rectangle",
        "origin": [obj["x"], obj["y"]],
        "points": None,
        "closed": None,
        "width": obj["w"],
        "height": obj["h"],
        "label": label,
        "layer": layer,
        "text": None,
        "text_height": None,
        "center": None,
        "radius": None,
        "start_angle": None,
        "end_angle": None,
    }


def _text_action(x: float, y: float, text: str, layer: str = "ANNO", h: float = 1.0) -> Dict[str, Any]:
    return {
        "task": "text_note",
        "origin": [x, y],
        "points": None,
        "closed": None,
        "width": None,
        "height": None,
        "label": None,
        "layer": layer,
        "text": text,
        "text_height": h,
        "center": None,
        "radius": None,
        "start_angle": None,
        "end_angle": None,
    }


def _polyline_action(points: List[List[float]], layer: str, label: Optional[str] = None, closed: bool = False) -> Dict[str, Any]:
    return {
        "task": "polygon" if closed else "polyline",
        "origin": None,
        "points": points,
        "closed": closed,
        "width": None,
        "height": None,
        "label": label,
        "layer": layer,
        "text": None,
        "text_height": None,
        "center": None,
        "radius": None,
        "start_angle": None,
        "end_angle": None,
    }


def _circle_action(x: float, y: float, radius: float, layer: str, label: Optional[str] = None) -> Dict[str, Any]:
    return {
        "task": "circle",
        "origin": None,
        "points": None,
        "closed": None,
        "width": None,
        "height": None,
        "label": label,
        "layer": layer,
        "text": None,
        "text_height": None,
        "center": [x, y],
        "radius": radius,
        "start_angle": None,
        "end_angle": None,
    }


def _layout_to_actions(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    collector_action = _rect_action_from_obj(
        _local_collector_from_parking(
            layout["parking"],
            layout["lot"],
            layout["street_edge"],
            layout["road_standards"],
        ),
        None,
        "PAVEMENT",
    )
    collector_action["label"] = None
    collector_action["synthetic_layout_surface"] = True
    collector_action["semantic_surface_role"] = "circulation"
    actions: List[Dict[str, Any]] = [
        _rect_action_from_obj(layout["lot"], "LOT", "SITE"),
        _rect_action_from_obj(layout["buildable"], "BUILDABLE", "SETBACK"),
        _rect_action_from_obj(layout["building"], "BLDG", "BUILDING"),
        _rect_action_from_obj(layout["parking"], "PARK", "PARKING"),
        collector_action,
    ]

    for line in layout.get("parking_stall_lines", []):
        actions.append(_polyline_action(line, layer="PARKING", closed=False))

    for sidewalk in layout.get("sidewalks", []):
        actions.append(_polyline_action(sidewalk["points"], layer=sidewalk.get("layer", "WALK"), label=sidewalk.get("label")))
        mx, my = _midpoint(tuple(sidewalk["points"][0]), tuple(sidewalk["points"][-1]))
        actions.append(_text_action(mx, my, f'SW {sidewalk.get("width", 5.0):.1f}', layer=sidewalk.get("layer", "WALK"), h=0.85))

    if layout.get("fire_lane") and not (
        _safe_bool(layout["fire_lane"].get("synthetic_fire_lane"))
        or _safe_bool(layout["fire_lane"].get("fire_access"))
    ):
        fire_layer = "PAVEMENT" if _safe_bool(layout["fire_lane"].get("synthetic_fire_lane")) or _safe_bool(layout["fire_lane"].get("fire_access")) else layout["fire_lane"].get("layer", "FIRE")
        fire_label = None if fire_layer == "PAVEMENT" else layout["fire_lane"].get("label")
        actions.append(
            _polyline_action(
                layout["fire_lane"]["points"],
                layer=fire_layer,
                label=fire_label,
            )
        )

    if layout.get("future_pad"):
        actions.append(_rect_action_from_obj(layout["future_pad"], "FUTURE PAD", "SITE"))

    if layout.get("loading_area"):
        actions.append(_rect_action_from_obj(layout["loading_area"], "LOAD", "PAVEMENT"))

    if layout.get("internal_lane"):
        internal_lane_action = _rect_action_from_obj(layout["internal_lane"], None, "PAVEMENT")
        internal_lane_action["synthetic_layout_surface"] = True
        internal_lane_action["semantic_surface_role"] = "circulation"
        actions.append(internal_lane_action)

    bx, by = _rect_center(layout["building"])
    actions.append(_text_action(bx, by, "BLDG", layer="BUILDING", h=1.0))

    return actions


# =============================================================================
# expanded multi-object generation
# =============================================================================

def _site_box_from_parsed(parsed: Dict[str, Any]) -> Rect:
    lot = parsed.get("lot") or {}
    return _rect(
        _safe_float(lot.get("x"), 0.0),
        _safe_float(lot.get("y"), 0.0),
        _safe_float(lot.get("w"), 120.0),
        _safe_float(lot.get("h"), 100.0),
    )


def _has_expanded_content(parsed: Dict[str, Any]) -> bool:
    buildings = parsed.get("buildings")
    if isinstance(buildings, list):
        clean_buildings = [item for item in buildings if isinstance(item, dict)]
        if len(clean_buildings) > 1:
            return True
        if any(
            _safe_optional_float(item.get("x")) is not None
            and _safe_optional_float(item.get("y")) is not None
            for item in clean_buildings
        ):
            return True
    keys = [
        "buildings",
        "parking_areas",
        "drive_aisles",
        "roads_network",
        "sidewalks",
        "fire_lanes",
        "drainage_structures",
        "pipe_network",
        "ponds",
        "utility_network",
    ]
    return any(isinstance(parsed.get(k), list) and len(parsed.get(k)) > 0 for k in keys)


def _infer_buildings_from_legacy(parsed: Dict[str, Any], site_box: Rect) -> List[Dict[str, Any]]:
    buildable = _buildable_area(site_box, _safe_float(parsed.get("setback"), 10.0))
    bw = _safe_optional_float(parsed.get("building_width"))
    bd = _safe_optional_float(parsed.get("building_depth"))
    fallback_width = bw or 80.0
    fallback_depth = bd or 50.0
    site_type = _normalize_site_type(_safe_str(parsed.get("site_type"), parsed.get("project_type") or "commercial_pad"))
    intensity = _safe_str(parsed.get("intensity"), "medium")
    street_edge = _normalize_street_edge(_safe_str(parsed.get("street_edge"), "bottom"))

    program_specs: List[Dict[str, Any]] = []
    for idx, raw in enumerate(_nonempty_list(parsed.get("buildings")), start=1):
        rec = dict(raw) if isinstance(raw, dict) else {}
        if not rec:
            continue
        spec_w = max(
            20.0,
            _safe_float(
                rec.get("w"),
                _safe_float(rec.get("width"), fallback_width),
            ),
        )
        spec_d = max(
            20.0,
            _safe_float(
                rec.get("d"),
                _safe_float(rec.get("depth"), fallback_depth),
            ),
        )
        spec_use = _safe_str(
            rec.get("use"),
            _safe_str(rec.get("type"), _safe_str(parsed.get("project_type"), "building")),
        ).lower()
        program_specs.append(
            {
                "name": _safe_str(rec.get("name"), _safe_str(rec.get("label"), f"Building {idx}")),
                "use": spec_use,
                "w": spec_w,
                "d": spec_d,
                "floors": max(1, _safe_int(rec.get("floors"), _safe_int((parsed.get("building") or {}).get("floor_count"), 1))),
            }
        )

    if program_specs:
        frontage_uses = {"retail", "commercial", "pad"}
        primary_specs = [spec for spec in program_specs if spec.get("use") not in frontage_uses]
        frontage_specs = [spec for spec in program_specs if spec.get("use") in frontage_uses]
        if not primary_specs:
            primary_specs, frontage_specs = frontage_specs, []

        margin_x = max(24.0, buildable["w"] * 0.05)
        margin_y = max(24.0, buildable["h"] * 0.05)
        min_x = buildable["x"] + margin_x
        max_x = _rect_right(buildable) - margin_x
        min_y = buildable["y"] + margin_y
        max_y = _rect_top(buildable) - margin_y
        vertical_span = max(max_y - min_y, 1.0)
        frontage_on_bottom = street_edge != "top"
        top_row_y = min_y + vertical_span * (0.58 if frontage_specs else 0.45)
        top_row_h = max_y - top_row_y
        bottom_row_y = min_y
        bottom_row_h = max(top_row_y - min_y - max(buildable["h"] * 0.04, 18.0), vertical_span * 0.22)

        def _place_row_specs(specs: Sequence[Dict[str, Any]], *, base_y: float, row_height: float) -> List[Dict[str, Any]]:
            if not specs:
                return []
            span_w = max(max_x - min_x, 1.0)
            widths = [max(20.0, _safe_float(spec.get("w"), fallback_width)) for spec in specs]
            spacing = max(18.0, min(span_w * 0.06, 80.0))
            total_w = sum(widths) + spacing * max(len(widths) - 1, 0)
            if total_w > span_w and len(widths) > 1:
                spacing = max(12.0, (span_w - sum(widths)) / max(len(widths) - 1, 1))
                total_w = sum(widths) + spacing * max(len(widths) - 1, 0)
            start_x = min_x + max((span_w - total_w) / 2.0, 0.0)
            placements: List[Dict[str, Any]] = []
            cursor_x = start_x
            for spec in specs:
                w = max(20.0, _safe_float(spec.get("w"), fallback_width))
                d = max(20.0, _safe_float(spec.get("d"), fallback_depth))
                y = base_y + max((row_height - d) / 2.0, 0.0)
                placements.append(
                    {
                        "label": _safe_str(spec.get("name"), "BLDG"),
                        "x": round(cursor_x, 3),
                        "y": round(y, 3),
                        "w": round(w, 3),
                        "d": round(d, 3),
                        "floors": max(1, _safe_int(spec.get("floors"), 1)),
                        "use": _safe_str(spec.get("use"), parsed.get("project_type") or "building"),
                        "layer": "BUILDING",
                    }
                )
                cursor_x += w + spacing
            return placements

        placements: List[Dict[str, Any]] = []
        if len(primary_specs) > 3:
            split = (len(primary_specs) + 1) // 2
            upper_specs = primary_specs[:split]
            lower_specs = primary_specs[split:]
            if frontage_on_bottom:
                placements.extend(_place_row_specs(upper_specs, base_y=top_row_y, row_height=top_row_h))
                placements.extend(_place_row_specs(lower_specs, base_y=bottom_row_y + bottom_row_h * 0.35, row_height=bottom_row_h * 0.5))
            else:
                placements.extend(_place_row_specs(upper_specs, base_y=bottom_row_y + bottom_row_h * 0.35, row_height=bottom_row_h * 0.5))
                placements.extend(_place_row_specs(lower_specs, base_y=top_row_y, row_height=top_row_h))
        else:
            placements.extend(_place_row_specs(primary_specs, base_y=top_row_y, row_height=top_row_h))

        if frontage_specs:
            frontage_y = bottom_row_y if frontage_on_bottom else top_row_y
            frontage_h = bottom_row_h if frontage_on_bottom else top_row_h * 0.5
            placements.extend(_place_row_specs(frontage_specs, base_y=frontage_y, row_height=frontage_h))
        return placements

    if bw is None or bd is None:
        chosen = _choose_building_size(buildable, site_type, intensity, bw, bd)
        bw = chosen["w"]
        bd = chosen["h"]

    floors = max(1, _safe_int((parsed.get("building") or {}).get("floor_count"), 1))

    primary = _position_building(
        buildable=buildable,
        building_size={"w": bw, "h": bd},
        street_edge=street_edge,
        layout_strategy=_safe_str(parsed.get("layout_strategy"), "front_parking"),
    )

    buildings = [
        {
            "label": "BLDG-1",
            "x": primary["x"],
            "y": primary["y"],
            "w": primary["w"],
            "d": primary["h"],
            "floors": floors,
            "use": parsed.get("project_type") or "building",
            "layer": "BUILDING",
        }
    ]

    if site_type in {"multifamily_site", "strip_center"} and buildable["w"] > 240.0:
        second = dict(primary)
        second["x"] = _clamp(_rect_right(primary) + 24.0, buildable["x"], _rect_right(buildable) - second["w"])
        if not _rects_overlap(primary, second, tol=8.0):
            buildings.append(
                {
                    "label": "BLDG-2",
                    "x": second["x"],
                    "y": second["y"],
                    "w": second["w"],
                    "d": second["h"],
                    "floors": floors,
                    "use": parsed.get("project_type") or "building",
                    "layer": "BUILDING",
                }
            )

    return buildings


def _infer_parking_from_legacy(parsed: Dict[str, Any], site_box: Rect, buildings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    site_plan = parsed.get("site_plan") or {}
    parking_count = _safe_int(site_plan.get("parking_count"), 0)
    if parking_count <= 0 and not buildings:
        return []

    standards = _parking_standards(parsed)
    buildable = _buildable_area(site_box, _safe_float(parsed.get("setback"), 10.0))
    site_type = _normalize_site_type(_safe_str(parsed.get("site_type"), parsed.get("project_type") or "commercial_pad"))
    intensity = _safe_str(parsed.get("intensity"), "medium")
    street_edge = _normalize_street_edge(_safe_str(parsed.get("street_edge"), "bottom"))
    layout_strategy = _normalize_layout_strategy(_safe_str(parsed.get("layout_strategy"), "front_parking"))

    if len(buildings) > 1:
        areas: List[Dict[str, Any]] = []
        total_area = sum(max(1.0, _safe_float(b.get("w"), 0.0) * _safe_float(b.get("d"), 0.0)) for b in buildings)
        explicit_total = max(0, parking_count)
        for idx, building in enumerate(buildings, start=1):
            bx = _safe_float(building.get("x"), buildable["x"])
            by = _safe_float(building.get("y"), buildable["y"])
            bw_val = max(20.0, _safe_float(building.get("w"), 40.0))
            bd_val = max(20.0, _safe_float(building.get("d"), 40.0))
            b_rect = _rect(bx, by, bw_val, bd_val)
            lot_depth = max(46.0, min(72.0, bd_val * 0.9))
            park_w = max(36.0, min(buildable["w"] * 0.36, bw_val + 34.0))
            if street_edge in {"bottom", "top"}:
                park_x = _clamp(bx + (bw_val - park_w) / 2.0, buildable["x"], _rect_right(buildable) - park_w)
                if street_edge == "bottom":
                    park_y = _clamp(by - lot_depth - 14.0, buildable["y"], _rect_top(buildable) - lot_depth)
                else:
                    park_y = _clamp(by + bd_val + 14.0, buildable["y"], _rect_top(buildable) - lot_depth)
            else:
                park_y = _clamp(by + (bd_val - lot_depth) / 2.0, buildable["y"], _rect_top(buildable) - lot_depth)
                if street_edge == "left":
                    park_x = _clamp(bx + bw_val + 14.0, buildable["x"], _rect_right(buildable) - park_w)
                else:
                    park_x = _clamp(bx - park_w - 14.0, buildable["x"], _rect_right(buildable) - park_w)
            parking_rect = _rect(park_x, park_y, park_w, lot_depth)
            capacity = _estimate_parking_capacity(parking_rect, standards)
            if explicit_total > 0 and total_area > 0:
                share = max(1, int(round(explicit_total * ((bw_val * bd_val) / total_area))))
            else:
                use_type = _safe_str(building.get("use"), site_type).lower()
                program_site_type = "multifamily_site" if use_type == "multifamily" else "commercial_pad" if use_type == "retail" else site_type
                share = _parking_count_from_program(b_rect, program_site_type, intensity, None)
            areas.append(
                {
                    "label": f"PARK-{idx}",
                    "x": round(parking_rect["x"], 3),
                    "y": round(parking_rect["y"], 3),
                    "w": round(parking_rect["w"], 3),
                    "h": round(parking_rect["h"], 3),
                    "stall_count": min(max(1, share), capacity),
                    "stall_width": standards["stall_width"],
                    "stall_depth": standards["stall_depth"],
                    "aisle_width": standards["aisle_width"],
                    "layout": _parking_orientation(parking_rect, standards),
                    "layer": "PARKING",
                }
            )
        return areas

    if buildings:
        primary = buildings[0]
        b = _rect(primary["x"], primary["y"], primary["w"], primary["d"])
    else:
        chosen = _choose_building_size(buildable, site_type, intensity)
        b = _position_building(buildable, chosen, street_edge, layout_strategy)

    desired = _parking_count_from_program(b, site_type, intensity, parking_count or None)
    parking_rect = _choose_best_parking(
        building=b,
        buildable=buildable,
        street_edge=street_edge,
        layout_strategy=layout_strategy,
        site_type=site_type,
        intensity=intensity,
        desired_count=desired,
        standards=standards,
    )
    capacity = _estimate_parking_capacity(parking_rect, standards)

    return [
        {
            "label": "PARK-1",
            "x": parking_rect["x"],
            "y": parking_rect["y"],
            "w": parking_rect["w"],
            "h": parking_rect["h"],
            "stall_count": min(desired, capacity),
            "stall_width": standards["stall_width"],
            "stall_depth": standards["stall_depth"],
            "aisle_width": standards["aisle_width"],
            "layout": _parking_orientation(parking_rect, standards),
            "layer": "PARKING",
        }
    ]


def _infer_drive_aisles_from_legacy(parsed: Dict[str, Any], site_box: Rect, parking_areas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not parking_areas:
        return []

    road_stds = _road_standards(parsed)
    if len(parking_areas) > 1:
        aisles: List[Dict[str, Any]] = []
        rects = [
            _rect(_safe_float(p.get("x"), 0.0), _safe_float(p.get("y"), 0.0), _safe_float(p.get("w"), 0.0), _safe_float(p.get("h"), 0.0))
            for p in parking_areas
        ]
        rects = sorted(rects, key=lambda r: (-(r["y"] + r["h"] / 2.0), r["x"]))
        for idx, rect in enumerate(rects, start=1):
            aisle_y = max(site_box["y"] + 8.0, rect["y"] - max(10.0, road_stds["drive_width"] * 0.5))
            aisles.append(
                {
                    "label": f"AISLE-{idx}",
                    "points": [[rect["x"] - 2.0, aisle_y + road_stds["drive_width"] / 2.0], [_rect_right(rect) + 2.0, aisle_y + road_stds["drive_width"] / 2.0]],
                    "width": min(18.0, max(10.0, road_stds["drive_width"] * 0.6)),
                    "type": "parking_aisle",
                    "layer": "PAVEMENT",
                    "synthetic_layout_surface": True,
                }
            )
        return aisles

    p = parking_areas[0]
    p_rect = _rect(p["x"], p["y"], p["w"], p["h"])
    aisle_y = max(site_box["y"] + 8.0, p_rect["y"] - max(10.0, road_stds["drive_width"] * 0.5))
    return [
        {
            "label": "AISLE-1",
            "points": [[p_rect["x"] - 2.0, aisle_y + road_stds["drive_width"] / 2.0], [_rect_right(p_rect) + 2.0, aisle_y + road_stds["drive_width"] / 2.0]],
            "width": min(18.0, max(10.0, road_stds["drive_width"] * 0.6)),
            "type": "parking_aisle",
            "layer": "PAVEMENT",
            "synthetic_layout_surface": True,
        }
    ]


def _infer_roads_from_legacy(parsed: Dict[str, Any], site_box: Rect) -> List[Dict[str, Any]]:
    raw_buildings = parsed.get("buildings")
    raw_parking = parsed.get("parking_areas")
    if isinstance(raw_buildings, list) and any(isinstance(item, dict) for item in raw_buildings):
        return []
    if isinstance(raw_parking, list) and any(isinstance(item, dict) for item in raw_parking):
        return []
    road_stds = _road_standards(parsed)
    street_edge = _normalize_street_edge(_safe_str(parsed.get("street_edge"), "bottom"))
    road = _frontage_road_rect(site_box, street_edge, road_stds)

    if street_edge in {"bottom", "top"}:
        pts = [[road["x"], road["y"] + road["h"] / 2.0], [_rect_right(road), road["y"] + road["h"] / 2.0]]
    else:
        pts = [[road["x"] + road["w"] / 2.0, road["y"]], [road["x"] + road["w"] / 2.0, _rect_top(road)]]

    return [
        {
            "label": "ROAD-1",
            "points": pts,
            "width": road_stds["frontage_road_depth"],
            "type": "frontage",
            "layer": "PAVEMENT",
        }
    ]


def _is_schematic_frontage_item(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    label = _safe_str(item.get("label"), "").upper()
    item_type = _safe_str(item.get("type"), "").lower()
    if "FRONTAGE" in label or "ACCESS" in label:
        return True
    return item_type in {"frontage", "access_drive", "collector_aisle"}


def _is_schematic_layout_action(action: Any) -> bool:
    if not isinstance(action, dict):
        return False
    layer = _safe_str(action.get("layer"), "").upper()
    task = _safe_str(action.get("task"), "").lower()
    label = _safe_str(action.get("label"), "").upper()
    text = _safe_str(action.get("text"), "").upper()
    item_type = _safe_str(action.get("type"), "").lower()
    if "FRONTAGE" in label or "FRONTAGE" in text or "ACCESS" in label or "ACCESS" in text:
        return True
    if item_type in {"frontage", "access_drive", "collector_aisle", "parking_aisle", "fire_lane"}:
        return True
    if layer in {"ROAD", "FIRE"} and task in {"polyline", "polygon", "circle"}:
        return True
    if layer == "ROUTE":
        return True
    return False


def _is_layout_display_action(action: Any) -> bool:
    if not isinstance(action, dict):
        return False
    layer = _safe_str(action.get("layer"), "").upper()
    task = _safe_str(action.get("task"), "").lower()
    if layer in {"BUILDING", "PARKING", "PAVEMENT", "ROAD", "FIRE", "WALK", "SITE", "SETBACK", "PAD"}:
        return True
    if layer == "ANNO" and task == "text_note":
        return True
    return False


def _infer_sidewalks_from_legacy(buildings: List[Dict[str, Any]], parking_areas: List[Dict[str, Any]], parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not buildings:
        return []

    standards = _parking_standards(parsed)
    street_edge = _normalize_street_edge(_safe_str(parsed.get("street_edge"), "bottom"))
    walks: List[Dict[str, Any]] = []
    parking_rects = [
        _rect(_safe_float(pp.get("x"), 0.0), _safe_float(pp.get("y"), 0.0), _safe_float(pp.get("w"), 0.0), _safe_float(pp.get("h"), 0.0))
        for pp in parking_areas
    ]
    for idx, b in enumerate(buildings, start=1):
        building = _rect(_safe_float(b.get("x"), 0.0), _safe_float(b.get("y"), 0.0), _safe_float(b.get("w"), 20.0), _safe_float(b.get("d"), 20.0))
        entry = _building_entry_point(building, street_edge)
        target_rect = min(parking_rects, key=lambda p: (_parking_connection_point(p, building)[0] - entry[0]) ** 2 + (_parking_connection_point(p, building)[1] - entry[1]) ** 2) if parking_rects else None
        if target_rect is not None:
            target = _parking_connection_point(target_rect, building)
            points = [[entry[0], entry[1]], [target[0], target[1]]]
        else:
            points = [[entry[0], entry[1]], [entry[0], entry[1] - 20.0]]
        walks.append(
            {
                "label": f"WALK-{idx}",
                "points": points,
                "width": standards["sidewalk_width"],
                "ada_required": True,
                "layer": "WALK",
            }
        )
    return walks


def _infer_fire_lanes_from_legacy(buildings: List[Dict[str, Any]], parsed: Dict[str, Any], site_box: Rect) -> List[Dict[str, Any]]:
    if not buildings:
        return []
    if len(buildings) > 1:
        return []

    buildable = _buildable_area(site_box, _safe_float(parsed.get("setback"), 10.0))
    b = buildings[0]
    lane = _generate_fire_lane(
        {
            "building": _rect(b["x"], b["y"], b["w"], b["d"]),
            "buildable": buildable,
            "street_edge": _normalize_street_edge(_safe_str(parsed.get("street_edge"), "bottom")),
        },
        _road_standards(parsed),
    )
    return [lane] if lane else []


def _infer_drainage_from_legacy(parsed: Dict[str, Any], site_box: Rect) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    drainage = parsed.get("drainage") or {}
    inlet_count = _safe_int(drainage.get("inlet_count"), 0)
    pipe_count = _safe_int(drainage.get("pipe_count"), 0)
    pond_count = _safe_int(drainage.get("pond_count"), 0)
    pipe_diameter = _safe_float(drainage.get("pipe_diameter"), 18.0)
    outfall_side = _normalize_street_edge(_safe_str(drainage.get("outfall_side") or parsed.get("street_edge"), "bottom"))

    if inlet_count <= 0 and pipe_count <= 0 and pond_count <= 0:
        return [], [], []

    if pond_count <= 0 and (inlet_count > 0 or pipe_count > 0):
        pond_count = 1

    structures: List[Dict[str, Any]] = []
    pipes: List[Dict[str, Any]] = []
    ponds: List[Dict[str, Any]] = []

    pond_w = max(20.0, min(36.0, site_box["w"] * 0.18))
    pond_h = max(16.0, min(28.0, site_box["h"] * 0.16))
    pond_targets: List[Tuple[float, float]] = []

    for i in range(pond_count):
        if outfall_side == "top":
            px = site_box["x"] + site_box["w"] * (0.22 + 0.22 * i)
            py = _rect_top(site_box) - pond_h - 8.0
        elif outfall_side == "left":
            px = site_box["x"] + 8.0
            py = site_box["y"] + site_box["h"] * (0.22 + 0.18 * i)
        elif outfall_side == "right":
            px = _rect_right(site_box) - pond_w - 8.0
            py = site_box["y"] + site_box["h"] * (0.22 + 0.18 * i)
        else:
            px = site_box["x"] + site_box["w"] * (0.22 + 0.22 * i)
            py = site_box["y"] + 8.0

        ponds.append(
            {
                "label": f"POND-{i + 1}",
                "x": px,
                "y": py,
                "w": pond_w,
                "h": pond_h,
                "type": "detention",
                "layer": "BASIN_BOUNDARY",
            }
        )
        pond_targets.append((px + pond_w / 2.0, py + pond_h / 2.0))

    if inlet_count > 0:
        cols = max(2, min(4, inlet_count))
        rows = max(1, (inlet_count + cols - 1) // cols)
        usable_x = site_box["w"] * 0.70
        usable_y = site_box["h"] * 0.55
        start_x = site_box["x"] + site_box["w"] * 0.15
        start_y = site_box["y"] + site_box["h"] * 0.20

        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx >= inlet_count:
                    break
                ix = start_x + usable_x * ((c + 0.5) / cols)
                iy = start_y + usable_y * ((r + 0.5) / rows)
                structures.append(
                    {
                        "label": f"INLET-{idx + 1}",
                        "x": ix,
                        "y": iy,
                        "type": "inlet",
                        "rim_elev": None,
                        "invert_out": None,
                        "layer": "DRAIN",
                    }
                )
                idx += 1

    if structures and pond_targets:
        target = pond_targets[0]
        max_pipes = pipe_count if pipe_count > 0 else len(structures)
        for i, st in enumerate(structures[:max_pipes], start=1):
            pipes.append(
                {
                    "label": f"P-{i}",
                    "start": [st["x"], st["y"]],
                    "end": [target[0], target[1]],
                    "diameter": pipe_diameter,
                    "type": "storm",
                    "layer": "PIPE",
                }
            )

    return structures, pipes, ponds


def _append_building_actions(actions: List[Dict[str, Any]], buildings: List[Dict[str, Any]]) -> None:
    for b in buildings:
        x = _safe_float(b.get("x"), 0.0)
        y = _safe_float(b.get("y"), 0.0)
        w = _safe_float(b.get("w"), 40.0)
        d = _safe_float(b.get("d"), 60.0)
        label = _safe_str(b.get("label"), "BLDG")
        layer = _safe_str(b.get("layer"), "BUILDING")
        actions.append(_rect_action_from_obj(_rect(x, y, w, d), label, layer))


def _append_parking_actions(actions: List[Dict[str, Any]], parking_areas: List[Dict[str, Any]]) -> None:
    for p in parking_areas:
        x = _safe_float(p.get("x"), 0.0)
        y = _safe_float(p.get("y"), 0.0)
        w = _safe_float(p.get("w"), 50.0)
        h = _safe_float(p.get("h"), 30.0)
        label = _safe_str(p.get("label"), "PARK")
        stalls = _safe_int(p.get("stall_count"), 0)
        layer = _safe_str(p.get("layer"), "PARKING")
        actions.append(_rect_action_from_obj(_rect(x, y, w, h), label, layer))

        standards = {
            "stall_width": _safe_float(p.get("stall_width"), 9.0),
            "stall_depth": _safe_float(p.get("stall_depth"), 18.0),
            "aisle_width": _safe_float(p.get("aisle_width"), 24.0),
            "module_depth": 2.0 * _safe_float(p.get("stall_depth"), 18.0) + _safe_float(p.get("aisle_width"), 24.0),
        }
        p_rect = _rect(x, y, w, h)
        for line in _generate_parking_stall_lines(p_rect, standards, stalls):
            actions.append(_polyline_action(line, layer=layer, closed=False))


def _append_line_network_actions(actions: List[Dict[str, Any]], items: List[Dict[str, Any]], width_prefix: Optional[str] = None) -> None:
    for item in items:
        pts = item.get("points")
        if not isinstance(pts, list) or len(pts) < 2:
            continue

        clean_pts: List[List[float]] = []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                clean_pts.append([_safe_float(p[0], 0.0), _safe_float(p[1], 0.0)])

        if len(clean_pts) < 2:
            continue

        label = item.get("label")
        layer = _safe_str(item.get("layer"), "SITE")
        actions.append(_polyline_action(clean_pts, layer=layer, label=label, closed=False))

        if width_prefix is not None and item.get("width") is not None:
            mx = (clean_pts[0][0] + clean_pts[-1][0]) / 2.0
            my = (clean_pts[0][1] + clean_pts[-1][1]) / 2.0
            actions.append(_text_action(mx + 1.0, my + 1.0, f"{width_prefix} {_safe_float(item.get('width'), 0.0):.1f}", layer=layer, h=0.85))


def _surface_rect_from_line_item(item: Dict[str, Any], *, layer: str) -> Optional[Dict[str, Any]]:
    pts = item.get("points")
    if not isinstance(pts, list) or len(pts) < 2:
        return None
    start = pts[0]
    end = pts[-1]
    if not (
        isinstance(start, (list, tuple))
        and len(start) >= 2
        and isinstance(end, (list, tuple))
        and len(end) >= 2
    ):
        return None
    x1 = _safe_float(start[0], 0.0)
    y1 = _safe_float(start[1], 0.0)
    x2 = _safe_float(end[0], 0.0)
    y2 = _safe_float(end[1], 0.0)
    width = max(0.0, _safe_float(item.get("width"), 0.0))
    if width <= 0.0:
        return None
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dx <= 1e-6 and dy <= 1e-6:
        return None
    if dx >= dy:
        rect = _rect(min(x1, x2), min(y1, y2) - width / 2.0, max(dx, 1.0), width)
    else:
        rect = _rect(min(x1, x2) - width / 2.0, min(y1, y2), width, max(dy, 1.0))
    label = _safe_str(item.get("label"), "")
    return _rect_action_from_obj(rect, label, layer)


def _preferred_surface_layer_for_line_item(item: Dict[str, Any], default_layer: str) -> str:
    default_layer = _safe_str(default_layer, "SITE")
    item_type = _safe_str(item.get("type"), "").lower()
    if item_type in {"frontage", "access_drive", "fire_lane", "collector_aisle", "parking_aisle"}:
        return "PAVEMENT"
    if _safe_bool(item.get("synthetic_fire_lane")) or _safe_bool(item.get("fire_access")):
        return "PAVEMENT"
    return default_layer


def _append_drainage_structure_actions(actions: List[Dict[str, Any]], structures: List[Dict[str, Any]]) -> None:
    for s in structures:
        x = _safe_float(s.get("x"), 0.0)
        y = _safe_float(s.get("y"), 0.0)
        label = _safe_str(s.get("label"), "INLET")
        layer = _safe_str(s.get("layer"), "DRAIN")
        actions.append(_circle_action(x, y, 1.0, layer))
        actions.append(_text_action(x + 1.2, y + 1.2, label, layer=layer, h=0.9))


def _append_pipe_actions(actions: List[Dict[str, Any]], pipes: List[Dict[str, Any]]) -> None:
    for p in pipes:
        start = p.get("start")
        end = p.get("end")
        if not (
            isinstance(start, (list, tuple))
            and len(start) >= 2
            and isinstance(end, (list, tuple))
            and len(end) >= 2
        ):
            continue

        pts = [
            [_safe_float(start[0], 0.0), _safe_float(start[1], 0.0)],
            [_safe_float(end[0], 0.0), _safe_float(end[1], 0.0)],
        ]
        label = _safe_str(p.get("label"), "PIPE")
        layer = _safe_str(p.get("layer"), "PIPE")
        dia = _safe_float(p.get("diameter"), 18.0)

        actions.append(_polyline_action(pts, layer=layer, label=label, closed=False))
        mx = (pts[0][0] + pts[1][0]) / 2.0
        my = (pts[0][1] + pts[1][1]) / 2.0
        actions.append(_text_action(mx + 0.5, my + 0.5, f'{label} {dia:.0f}"', layer=layer, h=0.85))


def _append_pond_actions(actions: List[Dict[str, Any]], ponds: List[Dict[str, Any]]) -> None:
    for p in ponds:
        x = _safe_float(p.get("x"), 0.0)
        y = _safe_float(p.get("y"), 0.0)
        w = _safe_float(p.get("w"), 18.0)
        h = _safe_float(p.get("h"), 14.0)
        label = _safe_str(p.get("label"), "POND")
        layer = _safe_str(p.get("layer"), "BASIN_BOUNDARY")

        poly = [
            [x + w * 0.10, y],
            [x + w * 0.90, y],
            [x + w, y + h * 0.45],
            [x + w * 0.80, y + h],
            [x + w * 0.20, y + h],
            [x, y + h * 0.45],
        ]
        actions.append(_polyline_action(poly, layer=layer, label=label, closed=True))
        actions.append(_text_action(x + w / 2.0, y + h / 2.0, label, layer=layer))


def _append_utility_actions(actions: List[Dict[str, Any]], utilities: List[Dict[str, Any]]) -> None:
    for u in utilities:
        pts = u.get("points")
        if not isinstance(pts, list) or len(pts) < 2:
            continue

        clean_pts: List[List[float]] = []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                clean_pts.append([_safe_float(p[0], 0.0), _safe_float(p[1], 0.0)])
        if len(clean_pts) < 2:
            continue

        layer = _safe_str(u.get("layer"), "UTILITY")
        label = _safe_str(u.get("label"), _safe_str(u.get("utility_type"), "UTILITY").upper())
        actions.append(_polyline_action(clean_pts, layer=layer, label=label, closed=False))
        mx = (clean_pts[0][0] + clean_pts[-1][0]) / 2.0
        my = (clean_pts[0][1] + clean_pts[-1][1]) / 2.0
        actions.append(_text_action(mx + 0.6, my + 0.6, label, layer=layer, h=0.8))


def _append_grading_actions(actions: List[Dict[str, Any]], grading: Dict[str, Any], site_box: Rect, buildings: List[Dict[str, Any]], ponds: List[Dict[str, Any]]) -> None:
    contours_required = bool(grading.get("contours_required"))
    pad_count = _safe_int(grading.get("pad_count"), 0)
    flow_arrow_count = _safe_int(grading.get("flow_arrow_count"), 0)
    min_slope = _safe_float(grading.get("min_slope_pct"), 2.0)

    if pad_count > 0 and buildings:
        for i, b in enumerate(buildings[:pad_count], start=1):
            x = _safe_float(b.get("x"), 0.0) + 2.0
            y = _safe_float(b.get("y"), 0.0) + 2.0
            w = max(6.0, _safe_float(b.get("w"), 20.0) - 4.0)
            d = max(6.0, _safe_float(b.get("d"), 20.0) - 4.0)
            actions.append(_rect_action_from_obj(_rect(x, y, w, d), f"PAD-{i}", "SURFACE"))

    if flow_arrow_count > 0:
        targets: List[Tuple[float, float]] = []
        for pond in ponds:
            targets.append(
                (
                    _safe_float(pond.get("x"), 0.0) + _safe_float(pond.get("w"), 18.0) / 2.0,
                    _safe_float(pond.get("y"), 0.0) + _safe_float(pond.get("h"), 14.0) / 2.0,
                )
            )
        if not targets:
            targets.append((site_box["x"] + site_box["w"] / 2.0, site_box["y"]))

        for i in range(flow_arrow_count):
            sx = site_box["x"] + site_box["w"] * (0.15 + 0.7 * ((i % 4) / 4.0))
            sy = site_box["y"] + site_box["h"] * (0.25 + 0.5 * (((i // 4) % 3) / 3.0))
            tx, ty = min(targets, key=lambda p: (p[0] - sx) ** 2 + (p[1] - sy) ** 2)
            mx = (sx + tx) / 2.0
            my = (sy + ty) / 2.0
            actions.append(_polyline_action([[sx, sy], [tx, ty]], layer="DRAIN_FLOW", label=None, closed=False))
            actions.append(_text_action(mx, my, f"{min_slope:.1f}% FLOW", layer="DRAIN_FLOW", h=0.8))

    if contours_required:
        y_step = max(12.0, site_box["h"] / 5.0)
        for i in range(1, 5):
            y = site_box["y"] + i * y_step
            pts = [
                [site_box["x"] + 5.0, y],
                [site_box["x"] + site_box["w"] * 0.35, y + 2.0],
                [site_box["x"] + site_box["w"] * 0.7, y - 1.5],
                [_rect_right(site_box) - 5.0, y + 1.0],
            ]
            actions.append(_polyline_action(pts, layer="FG_CONTOUR", label=f"C{i}", closed=False))


def _build_expanded_plan(parsed: Dict[str, Any]) -> Dict[str, Any]:
    site_box = _site_box_from_parsed(parsed)
    actions: List[Dict[str, Any]] = [_rect_action_from_obj(site_box, "LOT", "SITE")]

    raw_buildings = _nonempty_list(parsed.get("buildings"))
    positioned_buildings = []
    for b in raw_buildings:
        if not isinstance(b, dict):
            continue
        bw = _safe_optional_float(b.get("w"))
        if bw is None:
            bw = _safe_optional_float(b.get("width"))
        bd = _safe_optional_float(b.get("d"))
        if bd is None:
            bd = _safe_optional_float(b.get("depth"))
        if (
            _safe_optional_float(b.get("x")) is not None
            and _safe_optional_float(b.get("y")) is not None
            and bw is not None
            and bd is not None
        ):
            normalized = dict(b)
            normalized["w"] = bw
            normalized["d"] = bd
            positioned_buildings.append(normalized)
    buildings = positioned_buildings if len(positioned_buildings) == len(raw_buildings) and raw_buildings else []
    if not buildings:
        buildings = _infer_buildings_from_legacy(parsed, site_box)
    is_multi_building_program = len(buildings) > 1 or len([item for item in raw_buildings if isinstance(item, dict)]) > 1

    parking_areas = _nonempty_list(parsed.get("parking_areas"))
    if not parking_areas:
        parking_areas = _infer_parking_from_legacy(parsed, site_box, buildings)

    drive_aisles = _nonempty_list(parsed.get("drive_aisles"))
    if is_multi_building_program:
        drive_aisles = [item for item in drive_aisles if not _is_schematic_frontage_item(item)]
    if not drive_aisles:
        drive_aisles = _infer_drive_aisles_from_legacy(parsed, site_box, parking_areas)

    roads_network = _nonempty_list(parsed.get("roads_network"))
    if is_multi_building_program:
        roads_network = [item for item in roads_network if not _is_schematic_frontage_item(item)]
    if not roads_network:
        roads_network = _infer_roads_from_legacy(parsed, site_box)

    sidewalks = _nonempty_list(parsed.get("sidewalks"))
    if not sidewalks and (buildings or parking_areas):
        sidewalks = _infer_sidewalks_from_legacy(buildings, parking_areas, parsed)

    fire_lanes = _nonempty_list(parsed.get("fire_lanes"))
    if is_multi_building_program:
        fire_lanes = [item for item in fire_lanes if not _is_schematic_frontage_item(item)]
    if not fire_lanes:
        fire_lanes = _infer_fire_lanes_from_legacy(buildings, parsed, site_box)

    drainage_structures = _nonempty_list(parsed.get("drainage_structures"))
    pipe_network = _nonempty_list(parsed.get("pipe_network"))
    ponds = _nonempty_list(parsed.get("ponds"))

    if not drainage_structures and not pipe_network and not ponds:
        ds, pn, pd = _infer_drainage_from_legacy(parsed, site_box)
        drainage_structures = ds
        pipe_network = pn
        ponds = pd

    utility_network = _nonempty_list(parsed.get("utility_network"))
    grading = parsed.get("grading") or {}

    _append_building_actions(actions, buildings)
    _append_parking_actions(actions, parking_areas)
    for item in drive_aisles:
        surface = _surface_rect_from_line_item(item, layer=_preferred_surface_layer_for_line_item(item, "PAVEMENT"))
        if surface:
            actions.append(surface)
        else:
            _append_line_network_actions(actions, [item], width_prefix="W")
    for item in roads_network:
        surface = _surface_rect_from_line_item(item, layer=_preferred_surface_layer_for_line_item(item, "ROAD"))
        if surface:
            actions.append(surface)
        else:
            _append_line_network_actions(actions, [item], width_prefix="RW")
    _append_line_network_actions(actions, sidewalks, width_prefix="SW")
    for item in fire_lanes:
        surface = _surface_rect_from_line_item(item, layer=_preferred_surface_layer_for_line_item(item, "FIRE"))
        if surface:
            actions.append(surface)
        else:
            _append_line_network_actions(actions, [item], width_prefix="FIRE")
    _append_drainage_structure_actions(actions, drainage_structures)
    _append_pipe_actions(actions, pipe_network)
    _append_pond_actions(actions, ponds)
    _append_utility_actions(actions, utility_network)
    _append_grading_actions(actions, grading, site_box, buildings, ponds)

    if parsed.get("actions"):
        extra_actions = _nonempty_list(parsed.get("actions"))
        if is_multi_building_program:
            extra_actions = [
                action
                for action in extra_actions
                if not _is_schematic_layout_action(action) and not _is_layout_display_action(action)
            ]
        actions.extend(extra_actions)

    assumptions = list(parsed.get("assumptions") or [])
    assumptions.extend(
        [
            "Expanded multi-object layout path used.",
            "Geometry is concept-level and intended for planning and DXF generation.",
            "Parking geometry upgraded with aisle/stall logic when possible.",
        ]
    )

    return {
        "project_name": _safe_str(parsed.get("project_name"), "Concept Plan"),
        "units": _safe_str(parsed.get("units"), "ft"),
        "actions": actions,
        "meta": {
            "layout_mode": "expanded_multi_object",
            "project_type": _safe_str(parsed.get("project_type"), parsed.get("site_type") or "commercial_pad"),
            "building_count": len(buildings),
            "parking_area_count": len(parking_areas),
            "drive_aisle_count": len(drive_aisles),
            "road_count": len(roads_network),
            "sidewalk_count": len(sidewalks),
            "fire_lane_count": len(fire_lanes),
            "drainage_structure_count": len(drainage_structures),
            "pipe_count": len(pipe_network),
            "pond_count": len(ponds),
            "utility_line_count": len(utility_network),
        },
        "assumptions": assumptions,
    }


# =============================================================================
# public entry
# =============================================================================

def expand_plan(parsed: Dict[str, Any]) -> Dict[str, Any]:
    project_name = _safe_str(parsed.get("project_name"), "Concept Plan")
    project_type = _safe_str(parsed.get("project_type"), parsed.get("site_type") or "commercial_pad")
    units = _safe_str(parsed.get("units"), "ft")
    mode = _safe_str(parsed.get("mode"), "site_plan")
    lot = parsed.get("lot")

    if _has_expanded_content(parsed):
        return _build_expanded_plan(parsed)

    should_use_layout = mode == "site_plan" or lot is not None

    if should_use_layout:
        layout = generate_ai_guided_layout(parsed)
        return {
            "project_name": project_name,
            "units": units,
            "actions": _layout_to_actions(layout),
            "meta": {
                "layout": layout,
                "layout_mode": "commercial_ai_guided",
                "layout_strategy": layout.get("layout_strategy", "front_parking"),
                "street_edge": layout.get("street_edge", "bottom"),
                "intensity": layout.get("intensity", "medium"),
                "site_type": layout.get("site_type", "commercial_pad"),
                "project_type": project_type,
                "parking_count": layout.get("parking_count", 0),
            },
            "assumptions": list(parsed.get("assumptions", []))
            + [
                "Single-layout path used.",
                "Parking modules and frontage access standardized from layout engine defaults.",
            ],
        }

    return {
        "project_name": project_name,
        "units": units,
        "actions": parsed.get("actions", []),
        "meta": {
            "layout_mode": "passthrough",
            "project_type": project_type,
        },
        "assumptions": parsed.get("assumptions", []),
    }
