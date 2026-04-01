
from __future__ import annotations

"""
conflict_engine.py (TRUE MAX VERSION)

Purpose
-------
Cross-discipline conflict detection, grouping, severity ranking, and
planner-ready conflict intelligence for the AI civil engineering platform.

This version expands the prior conflict engine by adding:
- crossing-aware utility conflicts
- vertical/separation metadata hooks
- corridor / easement preference conflicts
- grading / shallow cover hooks
- service / access realism checks
- conflict clustering and grouping
- autofix / reroute recommendation hooks
- optimization penalty hooks
- explain/report-ready summaries

Design intent
-------------
- planner remains the orchestration brain
- conflict_engine only detects, classifies, groups, and summarizes
- deterministic and explainable logic
- ready for planner / intelligence / compliance / autofix integration
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
import math


# =============================================================================
# DEFAULT THRESHOLDS
# =============================================================================

DEFAULT_BUILDING_CLEARANCE_TO_ROAD_FT = 5.0
DEFAULT_BUILDING_CLEARANCE_TO_PARKING_FT = 3.0
DEFAULT_UTILITY_CLEARANCE_TO_BUILDING_FT = 5.0
DEFAULT_UTILITY_CLEARANCE_TO_ROAD_FT = 2.0
DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT = 3.0
DEFAULT_STORM_SAN_VERTICAL_SEPARATION_FT = 1.0
DEFAULT_WATER_SAN_VERTICAL_SEPARATION_FT = 1.5
DEFAULT_UTILITY_MIN_COVER_FT = 3.0
DEFAULT_INLET_CLEARANCE_TO_BUILDING_FT = 4.0
DEFAULT_BASIN_CLEARANCE_TO_BUILDING_FT = 10.0
DEFAULT_BASIN_CLEARANCE_TO_PAVEMENT_FT = 4.0
DEFAULT_DUPLICATE_NODE_TOLERANCE_FT = 0.5
DEFAULT_CIRCULATION_CONNECTION_TOLERANCE_FT = 8.0
DEFAULT_BUILDING_SERVICE_DISTANCE_FT = 180.0
DEFAULT_BUILDING_FRONTAGE_DISTANCE_FT = 40.0
DEFAULT_CORRIDOR_DEVIATION_FT = 12.0


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ConflictIssue:
    code: str
    severity: str
    message: str
    category: str = "general"
    object_ids: List[str] = field(default_factory=list)
    layers: List[str] = field(default_factory=list)
    system_tags: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    autofix_hints: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "category": self.category,
            "object_ids": list(self.object_ids),
            "layers": list(self.layers),
            "system_tags": list(self.system_tags),
            "suggested_actions": list(self.suggested_actions),
            "autofix_hints": [dict(x) for x in self.autofix_hints],
            "context": dict(self.context),
        }


@dataclass
class ConflictCluster:
    cluster_id: str
    category: str
    issue_codes: List[str] = field(default_factory=list)
    object_ids: List[str] = field(default_factory=list)
    weighted_penalty: float = 0.0
    issue_count: int = 0
    summary: str = ""


@dataclass
class ConflictSummary:
    issue_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_code: Dict[str, int] = field(default_factory=dict)
    weighted_penalty: float = 0.0
    critical_codes: List[str] = field(default_factory=list)
    clusters: List[ConflictCluster] = field(default_factory=list)
    top_critical_issues: List[Dict[str, Any]] = field(default_factory=list)
    recommended_next_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_count": self.issue_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "by_category": dict(self.by_category),
            "by_code": dict(self.by_code),
            "weighted_penalty": float(self.weighted_penalty),
            "critical_codes": list(self.critical_codes),
            "clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "category": c.category,
                    "issue_codes": list(c.issue_codes),
                    "object_ids": list(c.object_ids),
                    "weighted_penalty": c.weighted_penalty,
                    "issue_count": c.issue_count,
                    "summary": c.summary,
                }
                for c in self.clusters
            ],
            "top_critical_issues": [dict(x) for x in self.top_critical_issues],
            "recommended_next_actions": list(self.recommended_next_actions),
        }


@dataclass
class ConflictResult:
    success: bool
    issues: List[ConflictIssue] = field(default_factory=list)
    summary: ConflictSummary = field(default_factory=ConflictSummary)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": bool(self.success),
            "issues": [i.to_dict() for i in self.issues],
            "summary": self.summary.to_dict(),
            "meta": dict(self.meta),
        }


# =============================================================================
# HELPERS
# =============================================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(round(float(value)))
    except Exception:
        return int(default)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _lower(value: Any) -> str:
    return _safe_str(value).lower()


def _severity_weight(severity: str) -> float:
    sev = _lower(severity)
    if sev == "error":
        return 10.0
    if sev == "warning":
        return 3.0
    return 1.0


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def _orientation(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a1, a2, b1, b2) -> bool:
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)
    return (o1 == 0 or o2 == 0 or o3 == 0 or o4 == 0) or ((o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0))


def _point_to_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx = bx - ax
    dy = by - ay
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)


def _polyline_length(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        total += _distance(
            (_safe_float(points[i - 1][0]), _safe_float(points[i - 1][1])),
            (_safe_float(points[i][0]), _safe_float(points[i][1])),
        )
    return total


def _append_issue(
    out: List[ConflictIssue],
    *,
    code: str,
    severity: str,
    message: str,
    category: str,
    object_ids: Optional[List[str]] = None,
    layers: Optional[List[str]] = None,
    system_tags: Optional[List[str]] = None,
    suggested_actions: Optional[List[str]] = None,
    autofix_hints: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    seen: Optional[Set[str]] = None,
) -> None:
    key = f"{code}|{message}|{'|'.join(sorted([x for x in (object_ids or []) if x]))}"
    if seen is not None:
        if key in seen:
            return
        seen.add(key)
    out.append(
        ConflictIssue(
            code=code,
            severity=severity,
            message=message,
            category=category,
            object_ids=list(object_ids or []),
            layers=list(layers or []),
            system_tags=list(system_tags or []),
            suggested_actions=list(suggested_actions or []),
            autofix_hints=[dict(x) for x in (autofix_hints or [])],
            context=dict(context or {}),
        )
    )


# =============================================================================
# ACTION EXTRACTION
# =============================================================================

def _rect_from_action(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if _lower(action.get("task")) != "rectangle":
        return None
    origin = action.get("origin")
    if not isinstance(origin, list) or len(origin) < 2:
        return None
    x = _safe_float(origin[0], 0.0)
    y = _safe_float(origin[1], 0.0)
    w = _safe_float(action.get("width"), 0.0)
    h = _safe_float(action.get("height"), 0.0)
    if w <= 0.0 or h <= 0.0:
        return None
    return {
        "id": _safe_str(action.get("id"), ""),
        "label": _safe_str(action.get("label"), ""),
        "layer": _safe_str(action.get("layer"), "SITE").upper(),
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "props": _safe_dict(action.get("meta")),
    }


def _circle_from_action(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if _lower(action.get("task")) != "circle":
        return None
    center = action.get("center")
    if not isinstance(center, list) or len(center) < 2:
        return None
    radius = _safe_float(action.get("radius"), 0.0)
    if radius <= 0.0:
        return None
    return {
        "id": _safe_str(action.get("id"), ""),
        "label": _safe_str(action.get("label"), ""),
        "layer": _safe_str(action.get("layer"), "SITE").upper(),
        "x": _safe_float(center[0], 0.0),
        "y": _safe_float(center[1], 0.0),
        "z": _safe_float(action.get("elevation"), None),
        "r": radius,
        "props": _safe_dict(action.get("meta")),
    }


def _polyline_from_action(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    task = _lower(action.get("task"))
    if task not in {"polyline", "polygon"}:
        return None
    pts = _safe_list(action.get("points"))
    clean: List[List[float]] = []
    for p in pts:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            clean.append([_safe_float(p[0], 0.0), _safe_float(p[1], 0.0)])
    if len(clean) < 2:
        return None
    return {
        "id": _safe_str(action.get("id"), ""),
        "label": _safe_str(action.get("label"), ""),
        "layer": _safe_str(action.get("layer"), "SITE").upper(),
        "task": task,
        "points": clean,
        "invert_in": _safe_float(action.get("invert_in"), None),
        "invert_out": _safe_float(action.get("invert_out"), None),
        "cover_ft": _safe_float(action.get("cover_ft"), None),
        "corridor_name": _safe_str(action.get("corridor_name"), ""),
        "props": _safe_dict(action.get("meta")),
    }


def _rect_center(rect: Dict[str, Any]) -> Tuple[float, float]:
    return (rect["x"] + rect["w"] / 2.0, rect["y"] + rect["h"] / 2.0)


def _rect_right(rect: Dict[str, Any]) -> float:
    return rect["x"] + rect["w"]


def _rect_top(rect: Dict[str, Any]) -> float:
    return rect["y"] + rect["h"]


def _rects_overlap(a: Dict[str, Any], b: Dict[str, Any], clearance: float = 0.0) -> bool:
    return not (
        _rect_right(a) <= b["x"] - clearance
        or a["x"] >= _rect_right(b) + clearance
        or _rect_top(a) <= b["y"] - clearance
        or a["y"] >= _rect_top(b) + clearance
    )


def _rect_to_rect_clearance(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    dx = max(b["x"] - _rect_right(a), a["x"] - _rect_right(b), 0.0)
    dy = max(b["y"] - _rect_top(a), a["y"] - _rect_top(b), 0.0)
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return math.hypot(dx, dy)


def _circle_to_rect_clearance(circle: Dict[str, Any], rect: Dict[str, Any]) -> float:
    cx, cy, r = circle["x"], circle["y"], circle["r"]
    nearest_x = min(max(cx, rect["x"]), _rect_right(rect))
    nearest_y = min(max(cy, rect["y"]), _rect_top(rect))
    d = math.hypot(cx - nearest_x, cy - nearest_y) - r
    return max(0.0, d)


def _polyline_to_rect_clearance(poly: Dict[str, Any], rect: Dict[str, Any]) -> float:
    pts = poly["points"]
    best = float("inf")
    for i in range(1, len(pts)):
        ax, ay = pts[i - 1]
        bx, by = pts[i]
        test_pts = [
            (rect["x"], rect["y"]),
            (_rect_right(rect), rect["y"]),
            (rect["x"], _rect_top(rect)),
            (_rect_right(rect), _rect_top(rect)),
            _rect_center(rect),
        ]
        for px, py in test_pts:
            best = min(best, _point_to_segment_distance(px, py, ax, ay, bx, by))
    return 0.0 if best == float("inf") else best


def _polyline_to_polyline_min_distance(poly_a: Dict[str, Any], poly_b: Dict[str, Any]) -> float:
    pts_a = poly_a["points"]
    pts_b = poly_b["points"]
    best = float("inf")
    for i in range(1, len(pts_a)):
        ax, ay = pts_a[i - 1]
        bx, by = pts_a[i]
        for p in pts_b:
            best = min(best, _point_to_segment_distance(_safe_float(p[0]), _safe_float(p[1]), ax, ay, bx, by))
    for j in range(1, len(pts_b)):
        ax, ay = pts_b[j - 1]
        bx, by = pts_b[j]
        for p in pts_a:
            best = min(best, _point_to_segment_distance(_safe_float(p[0]), _safe_float(p[1]), ax, ay, bx, by))
    return 0.0 if best == float("inf") else best


def _polylines_cross(poly_a: Dict[str, Any], poly_b: Dict[str, Any]) -> bool:
    pts_a = poly_a["points"]
    pts_b = poly_b["points"]
    for i in range(1, len(pts_a)):
        a1 = (pts_a[i - 1][0], pts_a[i - 1][1])
        a2 = (pts_a[i][0], pts_a[i][1])
        for j in range(1, len(pts_b)):
            b1 = (pts_b[j - 1][0], pts_b[j - 1][1])
            b2 = (pts_b[j][0], pts_b[j][1])
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _layer_group(layer: str, label: str = "") -> str:
    layer_u = _safe_str(layer, "SITE").upper()
    label_l = _lower(label)

    if layer_u in {"BUILDING", "STRUCTURE"} or "building" in label_l or "bldg" in label_l:
        return "building"
    if layer_u in {"ROAD"} or "road" in label_l:
        return "road"
    if layer_u in {"PARKING", "PAVEMENT"} or "park" in label_l:
        return "parking"
    if layer_u in {"PIPE", "STORM"}:
        return "storm"
    if layer_u in {"WATER"}:
        return "water"
    if layer_u in {"SAN", "SEWER"}:
        return "sanitary"
    if layer_u in {"UTILITY"}:
        return "utility"
    if layer_u in {"BASIN_BOUNDARY"} or "pond" in label_l or "basin" in label_l:
        return "basin"
    if layer_u in {"WALK", "SIDEWALK"} or "sidewalk" in label_l:
        return "walk"
    if layer_u in {"CORRIDOR"} or "corridor" in label_l or "easement" in label_l:
        return "corridor"
    if layer_u in {"SYMBOL"} and ("inlet" in label_l or "manhole" in label_l or "hydrant" in label_l or "cleanout" in label_l):
        return "node"
    return "other"


# =============================================================================
# CONFLICT DETECTORS
# =============================================================================

def _detect_rect_conflicts(rects: Sequence[Dict[str, Any]], issues: List[ConflictIssue], seen: Set[str]) -> None:
    for i in range(len(rects)):
        a = rects[i]
        group_a = _layer_group(a["layer"], a["label"])
        for j in range(i + 1, len(rects)):
            b = rects[j]
            group_b = _layer_group(b["layer"], b["label"])

            overlap = _rects_overlap(a, b)
            clearance = _rect_to_rect_clearance(a, b)

            if overlap:
                code = "GEOMETRY_OVERLAP"
                category = "geometry"
                if {"building", "parking"} == {group_a, group_b}:
                    code = "BUILDING_PARKING_OVERLAP"; category = "site"
                elif {"building", "road"} == {group_a, group_b}:
                    code = "BUILDING_ROAD_OVERLAP"; category = "circulation"
                elif {"basin", "building"} == {group_a, group_b}:
                    code = "BASIN_BUILDING_OVERLAP"; category = "drainage"
                elif {"basin", "parking"} == {group_a, group_b}:
                    code = "BASIN_PARKING_OVERLAP"; category = "drainage"
                _append_issue(
                    issues,
                    code=code,
                    severity="error",
                    message=f"'{a['label'] or a['layer']}' overlaps '{b['label'] or b['layer']}'.",
                    category=category,
                    object_ids=[a["id"], b["id"]],
                    layers=[a["layer"], b["layer"]],
                    system_tags=[group_a, group_b],
                    suggested_actions=["shift geometry", "resize geometry", "reroute adjacent systems"],
                    autofix_hints=[{"strategy": "separate_rectangles", "priority": "high"}],
                    context={"clearance_ft": 0.0},
                    seen=seen,
                )
                continue

            if {"building", "road"} == {group_a, group_b} and clearance < DEFAULT_BUILDING_CLEARANCE_TO_ROAD_FT:
                _append_issue(
                    issues,
                    code="BUILDING_ROAD_CLEARANCE_LOW",
                    severity="warning",
                    message=f"Building and road clearance is low ({clearance:.2f} ft).",
                    category="circulation",
                    object_ids=[a["id"], b["id"]],
                    layers=[a["layer"], b["layer"]],
                    system_tags=[group_a, group_b],
                    suggested_actions=["shift building edge", "adjust road alignment", "reduce roadway envelope locally"],
                    autofix_hints=[{"strategy": "increase_building_road_clearance", "priority": "medium"}],
                    context={"clearance_ft": round(clearance, 3), "min_clearance_ft": DEFAULT_BUILDING_CLEARANCE_TO_ROAD_FT},
                    seen=seen,
                )

            if {"building", "parking"} == {group_a, group_b} and clearance < DEFAULT_BUILDING_CLEARANCE_TO_PARKING_FT:
                _append_issue(
                    issues,
                    code="BUILDING_PARKING_CLEARANCE_LOW",
                    severity="warning",
                    message=f"Building and parking clearance is low ({clearance:.2f} ft).",
                    category="site",
                    object_ids=[a["id"], b["id"]],
                    layers=[a["layer"], b["layer"]],
                    system_tags=[group_a, group_b],
                    suggested_actions=["pull parking back", "widen building edge setback", "insert walkway buffer"],
                    autofix_hints=[{"strategy": "increase_building_parking_clearance", "priority": "medium"}],
                    context={"clearance_ft": round(clearance, 3), "min_clearance_ft": DEFAULT_BUILDING_CLEARANCE_TO_PARKING_FT},
                    seen=seen,
                )

            if {"basin", "building"} == {group_a, group_b} and clearance < DEFAULT_BASIN_CLEARANCE_TO_BUILDING_FT:
                _append_issue(
                    issues,
                    code="BASIN_BUILDING_CLEARANCE_LOW",
                    severity="warning",
                    message=f"Basin and building clearance is low ({clearance:.2f} ft).",
                    category="drainage",
                    object_ids=[a["id"], b["id"]],
                    layers=[a["layer"], b["layer"]],
                    system_tags=[group_a, group_b],
                    suggested_actions=["shift basin", "shift building", "adjust grading to create separation"],
                    autofix_hints=[{"strategy": "increase_basin_building_clearance", "priority": "medium"}],
                    context={"clearance_ft": round(clearance, 3), "min_clearance_ft": DEFAULT_BASIN_CLEARANCE_TO_BUILDING_FT},
                    seen=seen,
                )

            if {"basin", "parking"} == {group_a, group_b} and clearance < DEFAULT_BASIN_CLEARANCE_TO_PAVEMENT_FT:
                _append_issue(
                    issues,
                    code="BASIN_PAVEMENT_CLEARANCE_LOW",
                    severity="warning",
                    message=f"Basin and pavement clearance is low ({clearance:.2f} ft).",
                    category="drainage",
                    object_ids=[a["id"], b["id"]],
                    layers=[a["layer"], b["layer"]],
                    system_tags=[group_a, group_b],
                    suggested_actions=["shift basin edge", "pull pavement back", "insert curb/buffer"],
                    autofix_hints=[{"strategy": "increase_basin_pavement_clearance", "priority": "medium"}],
                    context={"clearance_ft": round(clearance, 3), "min_clearance_ft": DEFAULT_BASIN_CLEARANCE_TO_PAVEMENT_FT},
                    seen=seen,
                )


def _detect_circle_vs_rect_conflicts(circles: Sequence[Dict[str, Any]], rects: Sequence[Dict[str, Any]], issues: List[ConflictIssue], seen: Set[str]) -> None:
    for c in circles:
        cgroup = _layer_group(c["layer"], c["label"])
        label_l = _lower(c["label"])
        for r in rects:
            rgroup = _layer_group(r["layer"], r["label"])
            clearance = _circle_to_rect_clearance(c, r)

            if cgroup == "node" and "inlet" in label_l and rgroup == "building" and clearance < DEFAULT_INLET_CLEARANCE_TO_BUILDING_FT:
                _append_issue(
                    issues,
                    code="INLET_BUILDING_CLEARANCE_LOW",
                    severity="warning",
                    message=f"Inlet is too close to building ({clearance:.2f} ft).",
                    category="drainage",
                    object_ids=[c["id"], r["id"]],
                    layers=[c["layer"], r["layer"]],
                    system_tags=["inlet", "building"],
                    suggested_actions=["shift inlet", "adjust local grading catch point"],
                    autofix_hints=[{"strategy": "move_inlet_away_from_building", "priority": "medium"}],
                    context={"clearance_ft": round(clearance, 3), "min_clearance_ft": DEFAULT_INLET_CLEARANCE_TO_BUILDING_FT},
                    seen=seen,
                )

            if cgroup == "node" and any(x in label_l for x in ("hydrant", "cleanout", "manhole")) and rgroup == "building" and clearance < DEFAULT_UTILITY_CLEARANCE_TO_BUILDING_FT:
                _append_issue(
                    issues,
                    code="UTILITYNODE_BUILDING_CLEARANCE_LOW",
                    severity="warning",
                    message=f"Utility node is too close to building ({clearance:.2f} ft).",
                    category="utilities",
                    object_ids=[c["id"], r["id"]],
                    layers=[c["layer"], r["layer"]],
                    system_tags=["node", "building"],
                    suggested_actions=["shift utility node", "relocate service tie"],
                    autofix_hints=[{"strategy": "move_utility_node_from_building", "priority": "medium"}],
                    context={"clearance_ft": round(clearance, 3), "min_clearance_ft": DEFAULT_UTILITY_CLEARANCE_TO_BUILDING_FT},
                    seen=seen,
                )


def _detect_duplicate_node_conflicts(circles: Sequence[Dict[str, Any]], issues: List[ConflictIssue], seen: Set[str]) -> None:
    for i in range(len(circles)):
        a = circles[i]
        pa = (a["x"], a["y"])
        for j in range(i + 1, len(circles)):
            b = circles[j]
            pb = (b["x"], b["y"])
            d = _distance(pa, pb)
            if d <= DEFAULT_DUPLICATE_NODE_TOLERANCE_FT:
                _append_issue(
                    issues,
                    code="DUPLICATE_NODE_LOCATION",
                    severity="warning",
                    message=f"Node locations are nearly duplicated ({d:.2f} ft apart).",
                    category="utilities",
                    object_ids=[a["id"], b["id"]],
                    layers=[a["layer"], b["layer"]],
                    system_tags=["node"],
                    suggested_actions=["merge node definitions", "remove duplicate symbol", "separate utility structures"],
                    autofix_hints=[{"strategy": "deduplicate_nodes", "priority": "low"}],
                    context={"distance_ft": round(d, 3), "tolerance_ft": DEFAULT_DUPLICATE_NODE_TOLERANCE_FT},
                    seen=seen,
                )


def _detect_line_vs_rect_conflicts(polys: Sequence[Dict[str, Any]], rects: Sequence[Dict[str, Any]], issues: List[ConflictIssue], seen: Set[str]) -> None:
    for poly in polys:
        pgroup = _layer_group(poly["layer"], poly["label"])
        for rect in rects:
            rgroup = _layer_group(rect["layer"], rect["label"])
            clearance = _polyline_to_rect_clearance(poly, rect)

            if pgroup in {"storm", "sanitary", "water", "utility"} and rgroup == "building" and clearance < DEFAULT_UTILITY_CLEARANCE_TO_BUILDING_FT:
                _append_issue(
                    issues,
                    code="UTILITY_BUILDING_CONFLICT",
                    severity="warning",
                    message=f"Utility/pipe line is too close to building ({clearance:.2f} ft).",
                    category="utilities",
                    object_ids=[poly["id"], rect["id"]],
                    layers=[poly["layer"], rect["layer"]],
                    system_tags=[pgroup, "building"],
                    suggested_actions=["reroute line", "shift building edge", "assign line to preferred corridor"],
                    autofix_hints=[{"strategy": "reroute_line_from_building", "priority": "high"}],
                    context={"clearance_ft": round(clearance, 3), "min_clearance_ft": DEFAULT_UTILITY_CLEARANCE_TO_BUILDING_FT},
                    seen=seen,
                )

            if pgroup in {"storm", "sanitary", "water", "utility"} and rgroup == "road" and clearance < DEFAULT_UTILITY_CLEARANCE_TO_ROAD_FT:
                _append_issue(
                    issues,
                    code="UTILITY_ROAD_CONFLICT",
                    severity="info",
                    message=f"Utility/pipe line is very close to road geometry ({clearance:.2f} ft).",
                    category="utilities",
                    object_ids=[poly["id"], rect["id"]],
                    layers=[poly["layer"], rect["layer"]],
                    system_tags=[pgroup, "road"],
                    suggested_actions=["shift line to road edge corridor", "verify crossing intent"],
                    autofix_hints=[{"strategy": "edge_route_line", "priority": "medium"}],
                    context={"clearance_ft": round(clearance, 3), "min_clearance_ft": DEFAULT_UTILITY_CLEARANCE_TO_ROAD_FT},
                    seen=seen,
                )


def _detect_line_vs_line_conflicts(polys: Sequence[Dict[str, Any]], issues: List[ConflictIssue], seen: Set[str]) -> None:
    for i in range(len(polys)):
        a = polys[i]
        agroup = _layer_group(a["layer"], a["label"])
        for j in range(i + 1, len(polys)):
            b = polys[j]
            bgroup = _layer_group(b["layer"], b["label"])

            if agroup not in {"storm", "sanitary", "water", "utility"} or bgroup not in {"storm", "sanitary", "water", "utility"}:
                continue

            d = _polyline_to_polyline_min_distance(a, b)
            crossing = _polylines_cross(a, b)

            if {agroup, bgroup} == {"storm", "sanitary"}:
                if crossing:
                    vert_sep = abs(_safe_float(a.get("invert_out"), 0.0) - _safe_float(b.get("invert_out"), 0.0)) if a.get("invert_out") is not None and b.get("invert_out") is not None else None
                    bad_vert = vert_sep is not None and vert_sep < DEFAULT_STORM_SAN_VERTICAL_SEPARATION_FT
                    _append_issue(
                        issues,
                        code="STORM_SANITARY_CROSSING",
                        severity="error" if bad_vert else "warning",
                        message="Storm and sanitary lines cross or strongly intersect.",
                        category="utilities",
                        object_ids=[a["id"], b["id"]],
                        layers=[a["layer"], b["layer"]],
                        system_tags=["storm", "sanitary"],
                        suggested_actions=["adjust crossing elevation", "reroute one system", "increase separation"],
                        autofix_hints=[{"strategy": "separate_storm_sanitary_crossing", "priority": "high"}],
                        context={"crossing": True, "vertical_separation_ft": vert_sep, "required_vertical_separation_ft": DEFAULT_STORM_SAN_VERTICAL_SEPARATION_FT},
                        seen=seen,
                    )
                elif d < DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT:
                    _append_issue(
                        issues,
                        code="STORM_SANITARY_CONFLICT",
                        severity="warning",
                        message=f"Storm and sanitary lines are too close ({d:.2f} ft).",
                        category="utilities",
                        object_ids=[a["id"], b["id"]],
                        layers=[a["layer"], b["layer"]],
                        system_tags=["storm", "sanitary"],
                        suggested_actions=["increase lateral separation", "assign systems to distinct corridors"],
                        autofix_hints=[{"strategy": "increase_storm_sanitary_clearance", "priority": "high"}],
                        context={"clearance_ft": round(d, 3), "min_clearance_ft": DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT},
                        seen=seen,
                    )

            elif {agroup, bgroup} == {"water", "sanitary"}:
                if crossing:
                    vert_sep = abs(_safe_float(a.get("invert_out"), 0.0) - _safe_float(b.get("invert_out"), 0.0)) if a.get("invert_out") is not None and b.get("invert_out") is not None else None
                    bad_vert = vert_sep is not None and vert_sep < DEFAULT_WATER_SAN_VERTICAL_SEPARATION_FT
                    _append_issue(
                        issues,
                        code="WATER_SANITARY_CROSSING",
                        severity="error" if bad_vert else "warning",
                        message="Water and sanitary lines cross or strongly intersect.",
                        category="utilities",
                        object_ids=[a["id"], b["id"]],
                        layers=[a["layer"], b["layer"]],
                        system_tags=["water", "sanitary"],
                        suggested_actions=["increase vertical separation", "reroute sanitary or water alignment"],
                        autofix_hints=[{"strategy": "separate_water_sanitary_crossing", "priority": "high"}],
                        context={"crossing": True, "vertical_separation_ft": vert_sep, "required_vertical_separation_ft": DEFAULT_WATER_SAN_VERTICAL_SEPARATION_FT},
                        seen=seen,
                    )
                elif d < DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT:
                    _append_issue(
                        issues,
                        code="WATER_SANITARY_CONFLICT",
                        severity="warning",
                        message=f"Water and sanitary lines are too close ({d:.2f} ft).",
                        category="utilities",
                        object_ids=[a["id"], b["id"]],
                        layers=[a["layer"], b["layer"]],
                        system_tags=["water", "sanitary"],
                        suggested_actions=["increase separation", "move one line to opposite corridor edge"],
                        autofix_hints=[{"strategy": "increase_water_sanitary_clearance", "priority": "high"}],
                        context={"clearance_ft": round(d, 3), "min_clearance_ft": DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT},
                        seen=seen,
                    )

            else:
                if d < DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT:
                    _append_issue(
                        issues,
                        code="UTILITY_UTILITY_CONFLICT",
                        severity="info",
                        message=f"Utility lines are close together ({d:.2f} ft).",
                        category="utilities",
                        object_ids=[a["id"], b["id"]],
                        layers=[a["layer"], b["layer"]],
                        system_tags=[agroup, bgroup],
                        suggested_actions=["space utility systems apart", "confirm shared corridor intent"],
                        autofix_hints=[{"strategy": "spread_utility_alignments", "priority": "medium"}],
                        context={"clearance_ft": round(d, 3), "min_clearance_ft": DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT, "crossing": crossing},
                        seen=seen,
                    )


def _detect_cover_and_vertical_risks(polys: Sequence[Dict[str, Any]], issues: List[ConflictIssue], seen: Set[str]) -> None:
    for poly in polys:
        pgroup = _layer_group(poly["layer"], poly["label"])
        if pgroup not in {"storm", "sanitary", "water", "utility"}:
            continue
        cover = poly.get("cover_ft")
        if cover is not None and _safe_float(cover, 0.0) < DEFAULT_UTILITY_MIN_COVER_FT:
            _append_issue(
                issues,
                code="LOW_UTILITY_COVER",
                severity="warning",
                message=f"Utility line cover is below concept minimum ({_safe_float(cover):.2f} ft).",
                category="grading",
                object_ids=[poly["id"]],
                layers=[poly["layer"]],
                system_tags=[pgroup],
                suggested_actions=["deepen line", "adjust grading", "shift alignment"],
                autofix_hints=[{"strategy": "increase_utility_cover", "priority": "high"}],
                context={"cover_ft": round(_safe_float(cover), 3), "min_cover_ft": DEFAULT_UTILITY_MIN_COVER_FT},
                seen=seen,
            )


def _detect_corridor_preference_conflicts(polys: Sequence[Dict[str, Any]], issues: List[ConflictIssue], seen: Set[str]) -> None:
    for poly in polys:
        pgroup = _layer_group(poly["layer"], poly["label"])
        if pgroup not in {"storm", "sanitary", "water", "utility"}:
            continue
        corridor = _safe_str(poly.get("corridor_name"))
        if not corridor:
            _append_issue(
                issues,
                code="UTILITY_CORRIDOR_UNASSIGNED",
                severity="info",
                message="Utility line has no assigned corridor/easement preference.",
                category="utilities",
                object_ids=[poly["id"]],
                layers=[poly["layer"]],
                system_tags=[pgroup],
                suggested_actions=["assign utility corridor", "reserve easement path"],
                autofix_hints=[{"strategy": "assign_corridor_to_line", "priority": "low"}],
                context={},
                seen=seen,
            )


def _detect_access_connectivity_conflicts(rects: Sequence[Dict[str, Any]], polys: Sequence[Dict[str, Any]], issues: List[ConflictIssue], seen: Set[str]) -> None:
    buildings = [r for r in rects if _layer_group(r["layer"], r["label"]) == "building"]
    roads = [r for r in rects if _layer_group(r["layer"], r["label"]) == "road"]
    parking = [r for r in rects if _layer_group(r["layer"], r["label"]) == "parking"]
    walks = [p for p in polys if _layer_group(p["layer"], p["label"]) == "walk"]

    if buildings and not roads and not parking:
        _append_issue(
            issues,
            code="BUILDING_WITHOUT_ACCESS_SYSTEM",
            severity="warning",
            message="Buildings exist without obvious road or parking access geometry.",
            category="circulation",
            suggested_actions=["add road frontage", "add parking access", "introduce driveway/circulation spine"],
            autofix_hints=[{"strategy": "introduce_access_system", "priority": "high"}],
            seen=seen,
        )

    if buildings and parking and not walks:
        _append_issue(
            issues,
            code="PARKING_WITHOUT_PEDESTRIAN_CONNECTION",
            severity="warning",
            message="Buildings and parking exist, but no obvious pedestrian/sidewalk connection was found.",
            category="ada",
            suggested_actions=["add sidewalk spine", "connect entries to parking fields"],
            autofix_hints=[{"strategy": "add_pedestrian_connections", "priority": "high"}],
            seen=seen,
        )

    for b in buildings:
        bcenter = _rect_center(b)
        nearest_access = float("inf")
        for r in roads + parking:
            nearest_access = min(nearest_access, _distance(bcenter, _rect_center(r)))
        if nearest_access == float("inf"):
            continue
        if nearest_access > DEFAULT_BUILDING_SERVICE_DISTANCE_FT:
            _append_issue(
                issues,
                code="BUILDING_SERVICE_DISTANCE_HIGH",
                severity="warning",
                message=f"Building is far from the nearest road/parking access ({nearest_access:.2f} ft).",
                category="circulation",
                object_ids=[b["id"]],
                layers=[b["layer"]],
                system_tags=["building", "access"],
                suggested_actions=["add closer circulation access", "add internal drive", "relocate building"],
                autofix_hints=[{"strategy": "reduce_building_access_distance", "priority": "medium"}],
                context={"distance_ft": round(nearest_access, 3), "max_preferred_distance_ft": DEFAULT_BUILDING_SERVICE_DISTANCE_FT},
                seen=seen,
            )


# =============================================================================
# CLUSTERING / SUMMARY / REPORTING
# =============================================================================

def _cluster_conflicts(issues: Sequence[ConflictIssue]) -> List[ConflictCluster]:
    buckets: Dict[Tuple[str, Tuple[str, ...]], List[ConflictIssue]] = {}
    for issue in issues:
        key = (issue.category, tuple(sorted([x for x in issue.object_ids if x])))
        buckets.setdefault(key, []).append(issue)

    clusters: List[ConflictCluster] = []
    idx = 1
    for (category, object_ids), group in buckets.items():
        penalty = sum(_severity_weight(i.severity) for i in group)
        issue_codes = list(dict.fromkeys(i.code for i in group))
        cluster = ConflictCluster(
            cluster_id=f"cluster_{idx}",
            category=category,
            issue_codes=issue_codes,
            object_ids=list(object_ids),
            weighted_penalty=penalty,
            issue_count=len(group),
            summary=f"{category.title()} conflict cluster with {len(group)} issue(s).",
        )
        clusters.append(cluster)
        idx += 1

    clusters.sort(key=lambda c: c.weighted_penalty, reverse=True)
    return clusters


def summarize_conflicts(issues: Sequence[ConflictIssue]) -> ConflictSummary:
    summary = ConflictSummary()
    summary.issue_count = len(issues)
    critical: List[str] = []

    for issue in issues:
        sev = _lower(issue.severity)
        if sev == "error":
            summary.error_count += 1
            critical.append(issue.code)
        elif sev == "warning":
            summary.warning_count += 1
        else:
            summary.info_count += 1

        summary.by_category[issue.category] = summary.by_category.get(issue.category, 0) + 1
        summary.by_code[issue.code] = summary.by_code.get(issue.code, 0) + 1
        summary.weighted_penalty += _severity_weight(issue.severity)

    summary.critical_codes = list(dict.fromkeys(critical))
    summary.clusters = _cluster_conflicts(issues)

    ranked = sorted(
        issues,
        key=lambda i: (_severity_weight(i.severity), len(i.object_ids), len(i.suggested_actions)),
        reverse=True,
    )
    summary.top_critical_issues = [i.to_dict() for i in ranked[:5]]

    actions: List[str] = []
    if any(i.category == "utilities" for i in issues):
        actions.append("Resolve utility conflicts first and reroute storm/sanitary/water alignments as needed.")
    if any(i.category == "circulation" for i in issues):
        actions.append("Improve building access, frontage, and circulation connectivity.")
    if any(i.category == "drainage" for i in issues):
        actions.append("Reposition detention/drainage features to restore clearances and flow organization.")
    if any(i.category == "ada" for i in issues):
        actions.append("Add pedestrian / ADA connections between parking and building entries.")
    summary.recommended_next_actions = actions[:5]
    return summary


# =============================================================================
# PUBLIC ENTRYPOINT
# =============================================================================

def detect_plan_conflicts(
    parsed: Optional[Dict[str, Any]],
    plan: Dict[str, Any],
    *,
    building_clearance_to_road_ft: float = DEFAULT_BUILDING_CLEARANCE_TO_ROAD_FT,
    building_clearance_to_parking_ft: float = DEFAULT_BUILDING_CLEARANCE_TO_PARKING_FT,
    utility_clearance_to_building_ft: float = DEFAULT_UTILITY_CLEARANCE_TO_BUILDING_FT,
    utility_clearance_to_road_ft: float = DEFAULT_UTILITY_CLEARANCE_TO_ROAD_FT,
    utility_clearance_to_other_utility_ft: float = DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT,
    storm_san_vertical_separation_ft: float = DEFAULT_STORM_SAN_VERTICAL_SEPARATION_FT,
    water_san_vertical_separation_ft: float = DEFAULT_WATER_SAN_VERTICAL_SEPARATION_FT,
    utility_min_cover_ft: float = DEFAULT_UTILITY_MIN_COVER_FT,
    inlet_clearance_to_building_ft: float = DEFAULT_INLET_CLEARANCE_TO_BUILDING_FT,
    basin_clearance_to_building_ft: float = DEFAULT_BASIN_CLEARANCE_TO_BUILDING_FT,
    basin_clearance_to_pavement_ft: float = DEFAULT_BASIN_CLEARANCE_TO_PAVEMENT_FT,
    duplicate_node_tolerance_ft: float = DEFAULT_DUPLICATE_NODE_TOLERANCE_FT,
    circulation_connection_tolerance_ft: float = DEFAULT_CIRCULATION_CONNECTION_TOLERANCE_FT,
    building_service_distance_ft: float = DEFAULT_BUILDING_SERVICE_DISTANCE_FT,
    building_frontage_distance_ft: float = DEFAULT_BUILDING_FRONTAGE_DISTANCE_FT,
    corridor_deviation_ft: float = DEFAULT_CORRIDOR_DEVIATION_FT,
) -> ConflictResult:
    """
    Main public conflict detection entrypoint.
    """
    # runtime overrides
    global DEFAULT_BUILDING_CLEARANCE_TO_ROAD_FT
    global DEFAULT_BUILDING_CLEARANCE_TO_PARKING_FT
    global DEFAULT_UTILITY_CLEARANCE_TO_BUILDING_FT
    global DEFAULT_UTILITY_CLEARANCE_TO_ROAD_FT
    global DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT
    global DEFAULT_STORM_SAN_VERTICAL_SEPARATION_FT
    global DEFAULT_WATER_SAN_VERTICAL_SEPARATION_FT
    global DEFAULT_UTILITY_MIN_COVER_FT
    global DEFAULT_INLET_CLEARANCE_TO_BUILDING_FT
    global DEFAULT_BASIN_CLEARANCE_TO_BUILDING_FT
    global DEFAULT_BASIN_CLEARANCE_TO_PAVEMENT_FT
    global DEFAULT_DUPLICATE_NODE_TOLERANCE_FT
    global DEFAULT_CIRCULATION_CONNECTION_TOLERANCE_FT
    global DEFAULT_BUILDING_SERVICE_DISTANCE_FT
    global DEFAULT_BUILDING_FRONTAGE_DISTANCE_FT
    global DEFAULT_CORRIDOR_DEVIATION_FT

    DEFAULT_BUILDING_CLEARANCE_TO_ROAD_FT = building_clearance_to_road_ft
    DEFAULT_BUILDING_CLEARANCE_TO_PARKING_FT = building_clearance_to_parking_ft
    DEFAULT_UTILITY_CLEARANCE_TO_BUILDING_FT = utility_clearance_to_building_ft
    DEFAULT_UTILITY_CLEARANCE_TO_ROAD_FT = utility_clearance_to_road_ft
    DEFAULT_UTILITY_CLEARANCE_TO_OTHER_UTILITY_FT = utility_clearance_to_other_utility_ft
    DEFAULT_STORM_SAN_VERTICAL_SEPARATION_FT = storm_san_vertical_separation_ft
    DEFAULT_WATER_SAN_VERTICAL_SEPARATION_FT = water_san_vertical_separation_ft
    DEFAULT_UTILITY_MIN_COVER_FT = utility_min_cover_ft
    DEFAULT_INLET_CLEARANCE_TO_BUILDING_FT = inlet_clearance_to_building_ft
    DEFAULT_BASIN_CLEARANCE_TO_BUILDING_FT = basin_clearance_to_building_ft
    DEFAULT_BASIN_CLEARANCE_TO_PAVEMENT_FT = basin_clearance_to_pavement_ft
    DEFAULT_DUPLICATE_NODE_TOLERANCE_FT = duplicate_node_tolerance_ft
    DEFAULT_CIRCULATION_CONNECTION_TOLERANCE_FT = circulation_connection_tolerance_ft
    DEFAULT_BUILDING_SERVICE_DISTANCE_FT = building_service_distance_ft
    DEFAULT_BUILDING_FRONTAGE_DISTANCE_FT = building_frontage_distance_ft
    DEFAULT_CORRIDOR_DEVIATION_FT = corridor_deviation_ft

    actions = [a for a in _safe_list(plan.get("actions")) if isinstance(a, dict)]
    rects = [r for a in actions if (r := _rect_from_action(a)) is not None]
    circles = [c for a in actions if (c := _circle_from_action(a)) is not None]
    polys = [p for a in actions if (p := _polyline_from_action(a)) is not None]

    issues: List[ConflictIssue] = []
    seen: Set[str] = set()

    _detect_rect_conflicts(rects, issues, seen)
    _detect_circle_vs_rect_conflicts(circles, rects, issues, seen)
    _detect_duplicate_node_conflicts(circles, issues, seen)
    _detect_line_vs_rect_conflicts(polys, rects, issues, seen)
    _detect_line_vs_line_conflicts(polys, issues, seen)
    _detect_cover_and_vertical_risks(polys, issues, seen)
    _detect_corridor_preference_conflicts(polys, issues, seen)
    _detect_access_connectivity_conflicts(rects, polys, issues, seen)

    summary = summarize_conflicts(issues)

    meta = {
        "action_count": len(actions),
        "rectangle_count": len(rects),
        "circle_count": len(circles),
        "linework_count": len(polys),
        "optimization_hooks": {
            "weighted_penalty": summary.weighted_penalty,
            "critical_codes": list(summary.critical_codes),
            "cluster_count": len(summary.clusters),
            "by_category": dict(summary.by_category),
        },
        "explain_hooks": {
            "top_critical_issues": [dict(x) for x in summary.top_critical_issues],
            "recommended_next_actions": list(summary.recommended_next_actions),
        },
        "autofix_hooks": {
            "issue_fix_map": {
                issue.code: list(issue.suggested_actions)
                for issue in issues[:50]
            }
        },
        "thresholds": {
            "building_clearance_to_road_ft": building_clearance_to_road_ft,
            "building_clearance_to_parking_ft": building_clearance_to_parking_ft,
            "utility_clearance_to_building_ft": utility_clearance_to_building_ft,
            "utility_clearance_to_road_ft": utility_clearance_to_road_ft,
            "utility_clearance_to_other_utility_ft": utility_clearance_to_other_utility_ft,
            "storm_san_vertical_separation_ft": storm_san_vertical_separation_ft,
            "water_san_vertical_separation_ft": water_san_vertical_separation_ft,
            "utility_min_cover_ft": utility_min_cover_ft,
            "inlet_clearance_to_building_ft": inlet_clearance_to_building_ft,
            "basin_clearance_to_building_ft": basin_clearance_to_building_ft,
            "basin_clearance_to_pavement_ft": basin_clearance_to_pavement_ft,
            "duplicate_node_tolerance_ft": duplicate_node_tolerance_ft,
            "circulation_connection_tolerance_ft": circulation_connection_tolerance_ft,
            "building_service_distance_ft": building_service_distance_ft,
            "building_frontage_distance_ft": building_frontage_distance_ft,
            "corridor_deviation_ft": corridor_deviation_ft,
        },
    }

    return ConflictResult(
        success=summary.error_count == 0,
        issues=issues,
        summary=summary,
        meta=meta,
    )
