from __future__ import annotations

"""
error_check_engine.py

Expanded engineering QA / diagnostics layer for the AI civil engineering design platform.

Design intent:
- Preserve compatibility with existing grading/surface workflows
- Keep the original run_checks(existing, proposed, ...) entrypoint
- Add broader engineering checks that planner.py and planner_intelligence.py can use
- Return structured, severity-aware warnings/errors suitable for:
  - Explain Design
  - Fix Plan
  - Optimize Layout
  - UI issue panels
- Support both:
  - surface/grid-based checks
  - action/plan-based checks

This file intentionally goes well beyond basic flat/ponding checks.
"""

from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)
import math


EPS = 1e-9

# Parking / site assumptions used for concept-level checks when explicit
# geometry metadata is unavailable.
STALL_WIDTH_FT = 9.0
STALL_DEPTH_FT = 18.0
ADA_STALL_WIDTH_FT = 12.0
AISLE_WIDTH_FT = 24.0
PARKING_EFFICIENCY_SF_PER_STALL = 325.0

# Grading / circulation assumptions
DEFAULT_MIN_SITE_SLOPE = 0.005
DEFAULT_MAX_PARKING_SLOPE = 0.05
DEFAULT_MAX_ADA_CROSS_SLOPE = 0.02
DEFAULT_MAX_ROAD_GRADE = 0.06

# Hydrology / utility assumptions
DEFAULT_MIN_PIPE_SLOPE = 0.003
DEFAULT_MAX_PIPE_CAPACITY_RATIO = 1.10
DEFAULT_MAX_IMPERVIOUS_COVERAGE_RATIO = 0.95


# =============================================================================
# STRUCTURED ISSUE MODEL
# =============================================================================

@dataclass
class EngineeringCheckIssue:
    code: str
    severity: str
    message: str
    category: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "category": self.category,
            "context": dict(self.context),
        }


# =============================================================================
# BASIC HELPERS
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


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _lower(value: Any) -> str:
    return _safe_str(value).lower()


def _rect_area(width: Any, height: Any) -> float:
    w = max(0.0, _safe_float(width, 0.0))
    h = max(0.0, _safe_float(height, 0.0))
    return w * h


def _rect_from_action(action: Dict[str, Any]) -> Optional[Dict[str, float]]:
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
    return {"x": x, "y": y, "w": w, "h": h}


def _rect_right(rect: Dict[str, float]) -> float:
    return rect["x"] + rect["w"]


def _rect_top(rect: Dict[str, float]) -> float:
    return rect["y"] + rect["h"]


def _rect_center(rect: Dict[str, float]) -> Tuple[float, float]:
    return rect["x"] + rect["w"] / 2.0, rect["y"] + rect["h"] / 2.0


def _rects_overlap(a: Dict[str, float], b: Dict[str, float], clearance: float = 0.0) -> bool:
    return not (
        _rect_right(a) <= b["x"] - clearance + EPS
        or a["x"] >= _rect_right(b) + clearance - EPS
        or _rect_top(a) <= b["y"] - clearance + EPS
        or a["y"] >= _rect_top(b) + clearance - EPS
    )


def _polyline_length(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        x1 = _safe_float(points[i - 1][0], 0.0)
        y1 = _safe_float(points[i - 1][1], 0.0)
        x2 = _safe_float(points[i][0], 0.0)
        y2 = _safe_float(points[i][1], 0.0)
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def _layer_counts(actions: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for action in actions:
        layer = _safe_str(action.get("layer"), "SITE").upper()
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def _text_contains(action: Dict[str, Any], fragment: str) -> bool:
    frag = fragment.lower()
    return frag in _lower(action.get("label")) or frag in _lower(action.get("text"))


def _neighbor_indices(nrows: int, ncols: int, row: int, col: int) -> List[Tuple[int, int]]:
    neighbors: List[Tuple[int, int]] = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr = row + dr
            cc = col + dc
            if 0 <= rr < nrows and 0 <= cc < ncols:
                neighbors.append((rr, cc))
    return neighbors


def _append_issue(out: List[Dict[str, Any]], issue: EngineeringCheckIssue, seen: Optional[Set[str]] = None) -> None:
    key = f"{issue.code}|{issue.message}"
    if seen is not None:
        if key in seen:
            return
        seen.add(key)
    out.append(issue.to_dict())


def _canonical_drainage(plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = _safe_dict(plan.get("meta"))
    drainage = _safe_dict(meta.get("drainage"))
    if drainage:
        return drainage
    manager_export = _safe_dict(meta.get("manager_export"))
    latest_outputs = _safe_dict(manager_export.get("latest_outputs"))
    return _safe_dict(latest_outputs.get("drainage"))


def _canonical_sanitary(plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = _safe_dict(plan.get("meta"))
    sanitary = _safe_dict(meta.get("sanitary"))
    if sanitary:
        return sanitary
    manager_export = _safe_dict(meta.get("manager_export"))
    latest_outputs = _safe_dict(manager_export.get("latest_outputs"))
    return _safe_dict(latest_outputs.get("sanitary"))


def _manager_metrics(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(_safe_dict(plan.get("meta")).get("manager_export")).get("metrics"))


def _metric_value(plan: Dict[str, Any], name: str, default: float = 0.0) -> float:
    return _safe_float(_safe_dict(_manager_metrics(plan).get(name)).get("value"), default)


# =============================================================================
# ORIGINAL SURFACE CHECK ENTRYPOINT (PRESERVED / EXPANDED)
# =============================================================================

def run_checks(
    existing,
    proposed,
    min_slope: float = DEFAULT_MIN_SITE_SLOPE,
    max_warnings: int = 200,
) -> List[Dict]:
    """
    Expanded grading/surface checks.

    Detects:
    - flat areas
    - potential ponding / local low points
    - steep slope transitions
    - abrupt grade breaks
    - suspicious isolated depressions

    Returns list[dict] for compatibility with the existing planner stack.
    """
    warnings: List[Dict[str, Any]] = []
    seen_locations: Set[str] = set()

    if proposed is None:
        return warnings

    cell_size = max(_safe_float(getattr(proposed, "cell_size", 0.0), 0.0), EPS)

    for row in range(proposed.nrows):
        for col in range(proposed.ncols):
            z = proposed.values[row][col]
            neighbors = _neighbor_indices(proposed.nrows, proposed.ncols, row, col)
            if not neighbors:
                continue

            neighbor_zs = [proposed.values[rr][cc] for rr, cc in neighbors]
            min_neighbor = min(neighbor_zs)
            max_neighbor = max(neighbor_zs)
            avg_neighbor = sum(neighbor_zs) / len(neighbor_zs)

            x = proposed.x_at(col)
            y = proposed.y_at(row)

            # ---------------------------------------------------------
            # FLAT AREA CHECK
            # ---------------------------------------------------------
            dz_min = abs(z - min_neighbor)
            slope_min = dz_min / cell_size if cell_size > 0 else 0.0
            if slope_min < min_slope:
                key = f"FLAT|{row // 3}|{col // 3}"
                if key not in seen_locations:
                    seen_locations.add(key)
                    warnings.append(
                        {
                            "type": "FLAT",
                            "severity": "warning",
                            "category": "grading",
                            "msg": f"Flat area near ({x:.1f}, {y:.1f}) slope={slope_min:.3f}",
                            "context": {"x": round(x, 2), "y": round(y, 2), "slope": round(slope_min, 5)},
                        }
                    )

            # ---------------------------------------------------------
            # PONDING / LOW POINT CHECK
            # ---------------------------------------------------------
            if z <= min_neighbor and z <= avg_neighbor:
                key = f"LOW|{row // 3}|{col // 3}"
                if key not in seen_locations:
                    seen_locations.add(key)
                    warnings.append(
                        {
                            "type": "LOW",
                            "severity": "warning",
                            "category": "grading",
                            "msg": f"Potential ponding at ({x:.1f}, {y:.1f}) elev={z:.2f}",
                            "context": {"x": round(x, 2), "y": round(y, 2), "elev": round(z, 3)},
                        }
                    )

            # ---------------------------------------------------------
            # STEEP TRANSITION CHECK
            # ---------------------------------------------------------
            dz_max = abs(max_neighbor - min_neighbor)
            slope_max = dz_max / cell_size if cell_size > 0 else 0.0
            if slope_max > 0.25:
                key = f"STEEP|{row // 4}|{col // 4}"
                if key not in seen_locations:
                    seen_locations.add(key)
                    warnings.append(
                        {
                            "type": "STEEP",
                            "severity": "warning",
                            "category": "grading",
                            "msg": f"Steep local grade transition near ({x:.1f}, {y:.1f}) slope={slope_max:.3f}",
                            "context": {"x": round(x, 2), "y": round(y, 2), "slope": round(slope_max, 5)},
                        }
                    )

            # ---------------------------------------------------------
            # ISOLATED DEPRESSION CHECK
            # ---------------------------------------------------------
            diff_from_avg = avg_neighbor - z
            if diff_from_avg > 1.0:
                key = f"DEP|{row // 4}|{col // 4}"
                if key not in seen_locations:
                    seen_locations.add(key)
                    warnings.append(
                        {
                            "type": "DEP",
                            "severity": "warning",
                            "category": "grading",
                            "msg": f"Localized depression near ({x:.1f}, {y:.1f}) depth={diff_from_avg:.2f}",
                            "context": {"x": round(x, 2), "y": round(y, 2), "depth": round(diff_from_avg, 3)},
                        }
                    )

            if len(warnings) >= max_warnings:
                return warnings

    return warnings


# =============================================================================
# PLAN / ACTION LEVEL ENGINEERING CHECKS
# =============================================================================

def run_plan_checks(
    parsed: Optional[Dict[str, Any]],
    plan: Dict[str, Any],
    *,
    max_issues: int = 300,
    min_site_slope: float = DEFAULT_MIN_SITE_SLOPE,
    max_parking_slope: float = DEFAULT_MAX_PARKING_SLOPE,
    max_ada_cross_slope: float = DEFAULT_MAX_ADA_CROSS_SLOPE,
    max_road_grade: float = DEFAULT_MAX_ROAD_GRADE,
    min_pipe_slope: float = DEFAULT_MIN_PIPE_SLOPE,
    max_pipe_capacity_ratio: float = DEFAULT_MAX_PIPE_CAPACITY_RATIO,
    max_impervious_coverage_ratio: float = DEFAULT_MAX_IMPERVIOUS_COVERAGE_RATIO,
) -> List[Dict]:
    """
    Broad engineering QA for action-based plans.

    Returns structured issue dicts suitable for planner / intelligence scoring.
    """
    parsed = _safe_dict(parsed)
    grading = _safe_dict(parsed.get("grading"))
    drainage = _safe_dict(parsed.get("drainage"))
    override_min_site = _safe_float(grading.get("min_slope_pct"), 0.0)
    override_max_parking = _safe_float(grading.get("max_parking_slope_pct"), 0.0)
    override_max_ada = _safe_float(grading.get("max_ada_cross_slope_pct"), 0.0)
    override_max_road = _safe_float(grading.get("max_road_grade_pct"), 0.0)
    override_min_pipe = _safe_float(drainage.get("min_pipe_slope_pct"), 0.0)

    if override_min_site > 0:
        min_site_slope = max(min_site_slope, override_min_site / 100.0)
    if override_max_parking > 0:
        max_parking_slope = override_max_parking / 100.0
    if override_max_ada > 0:
        max_ada_cross_slope = override_max_ada / 100.0
    if override_max_road > 0:
        max_road_grade = override_max_road / 100.0
    if override_min_pipe > 0:
        min_pipe_slope = max(min_pipe_slope, override_min_pipe / 100.0)
    actions = [a for a in _safe_list(plan.get("actions")) if isinstance(a, dict)]

    issues: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    _check_empty_plan(actions, issues, seen)
    _check_basic_action_integrity(actions, issues, seen)
    _check_site_coverage(parsed, plan, actions, issues, seen, max_impervious_coverage_ratio)
    _check_building_presence(parsed, actions, issues, seen)
    _check_parking_program(parsed, plan, actions, issues, seen)
    _check_parking_geometry_reasonableness(actions, issues, seen)
    _check_drainage_completeness(parsed, plan, actions, issues, seen)
    _check_pipe_reasonableness(parsed, plan, actions, issues, seen, min_pipe_slope, max_pipe_capacity_ratio)
    _check_grading_reasonableness(parsed, plan, actions, issues, seen, min_site_slope, max_parking_slope, max_ada_cross_slope, max_road_grade)
    _check_circulation_reasonableness(parsed, plan, actions, issues, seen)
    _check_sanitary_completeness(parsed, plan, actions, issues, seen)
    _check_utility_coordination_hooks(parsed, plan, actions, issues, seen)
    _check_sheet_output_hooks(parsed, plan, actions, issues, seen)

    return issues[:max_issues]


# =============================================================================
# INDIVIDUAL CHECKERS
# =============================================================================

def _check_empty_plan(actions: Sequence[Dict[str, Any]], issues: List[Dict[str, Any]], seen: Set[str]) -> None:
    if not actions:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="EMPTY_PLAN",
                severity="error",
                message="Plan contains no actions.",
                category="general",
            ),
            seen,
        )


def _check_basic_action_integrity(actions: Sequence[Dict[str, Any]], issues: List[Dict[str, Any]], seen: Set[str]) -> None:
    for idx, action in enumerate(actions):
        task = _lower(action.get("task"))
        layer = _safe_str(action.get("layer"), "SITE").upper()

        if task not in {"rectangle", "polyline", "polygon", "circle", "arc", "text_note", "point", "north_arrow"}:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="UNKNOWN_TASK",
                    severity="warning",
                    message=f"Action {idx} uses unknown task '{task}'.",
                    category="geometry",
                    context={"index": idx, "task": task},
                ),
                seen,
            )

        if task == "rectangle":
            rect = _rect_from_action(action)
            if rect is None:
                _append_issue(
                    issues,
                    EngineeringCheckIssue(
                        code="RECTANGLE_INVALID",
                        severity="error",
                        message=f"Rectangle action {idx} is missing valid origin/size data.",
                        category="geometry",
                        context={"index": idx, "layer": layer},
                    ),
                    seen,
                )

        elif task in {"polyline", "polygon"}:
            points = _safe_list(action.get("points"))
            required = 3 if task == "polygon" else 2
            if len(points) < required:
                _append_issue(
                    issues,
                    EngineeringCheckIssue(
                        code="LINEWORK_TOO_SHORT",
                        severity="error",
                        message=f"{task.title()} action {idx} has insufficient points.",
                        category="geometry",
                        context={"index": idx, "point_count": len(points)},
                    ),
                    seen,
                )

        elif task in {"circle", "arc"}:
            center = _safe_list(action.get("center"))
            radius = _safe_float(action.get("radius"), 0.0)
            if len(center) < 2 or radius <= 0.0:
                _append_issue(
                    issues,
                    EngineeringCheckIssue(
                        code="CIRCLE_INVALID",
                        severity="error",
                        message=f"{task.title()} action {idx} is missing valid center/radius data.",
                        category="geometry",
                        context={"index": idx},
                    ),
                    seen,
                )
        elif task in {"text_note", "point", "north_arrow"}:
            origin = _safe_list(action.get("origin"))
            if len(origin) < 2:
                _append_issue(
                    issues,
                    EngineeringCheckIssue(
                        code="ORIGIN_INVALID",
                        severity="error",
                        message=f"{task.title()} action {idx} is missing a valid origin.",
                        category="geometry",
                        context={"index": idx, "layer": layer},
                    ),
                    seen,
                )


def _check_site_coverage(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
    max_impervious_coverage_ratio: float,
) -> None:
    lot = _safe_dict(parsed.get("lot"))
    lot_area = _rect_area(lot.get("w"), lot.get("h"))
    if lot_area <= 0.0:
        return

    meta = _safe_dict(plan.get("meta"))
    canonical_stats = _safe_dict(meta.get("stats"))
    canonical_qty = _safe_dict(_safe_dict(meta.get("quantities")).get("totals"))
    canonical_impervious = max(
        _safe_float(canonical_stats.get("estimated_impervious_area_sf"), 0.0),
        _safe_float(canonical_qty.get("estimated_impervious_area_sf"), 0.0),
        _metric_value(plan, "layout_impervious_area_sf", 0.0),
    )
    if canonical_impervious > 0.0:
        coverage_ratio = canonical_impervious / lot_area if lot_area > 0.0 else 0.0
        if coverage_ratio > 1.05:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="OVERCOVERAGE",
                    severity="error",
                    message="Estimated developed impervious area exceeds lot area.",
                    category="site",
                    context={
                        "lot_area_sf": round(lot_area, 2),
                        "estimated_impervious_area_sf": round(canonical_impervious, 2),
                        "coverage_ratio": round(coverage_ratio, 4),
                        "source": "canonical_state",
                    },
                ),
                seen,
            )
        elif coverage_ratio > max_impervious_coverage_ratio:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="TIGHT_COVERAGE",
                    severity="warning",
                    message="Estimated impervious coverage is very high relative to lot area.",
                    category="site",
                    context={
                        "lot_area_sf": round(lot_area, 2),
                        "estimated_impervious_area_sf": round(canonical_impervious, 2),
                        "coverage_ratio": round(coverage_ratio, 4),
                        "source": "canonical_state",
                    },
                ),
                seen,
            )
        return

    estimated_impervious = 0.0
    building_area = 0.0
    parking_area = 0.0
    road_area = 0.0

    for action in actions:
        rect = _rect_from_action(action)
        if rect is None:
            continue
        layer = _safe_str(action.get("layer"), "").upper()
        label = _lower(action.get("label"))
        area = rect["w"] * rect["h"]

        if layer in {"BUILDING", "STRUCTURE"} or "bldg" in label or "building" in label:
            building_area += area
            estimated_impervious += area
        elif layer in {"PARKING", "PAVEMENT"} or "park" in label:
            parking_area += area
            estimated_impervious += area
        elif layer == "ROAD" or "road" in label:
            road_area += area
            estimated_impervious += area

    coverage_ratio = estimated_impervious / lot_area if lot_area > 0.0 else 0.0

    if coverage_ratio > 1.05:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="OVERCOVERAGE",
                severity="error",
                message="Estimated developed impervious area exceeds lot area.",
                category="site",
                context={
                    "lot_area_sf": round(lot_area, 2),
                    "estimated_impervious_area_sf": round(estimated_impervious, 2),
                    "coverage_ratio": round(coverage_ratio, 4),
                },
            ),
            seen,
        )
    elif coverage_ratio > max_impervious_coverage_ratio:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="TIGHT_COVERAGE",
                severity="warning",
                message="Estimated impervious coverage is very high relative to lot area.",
                category="site",
                context={
                    "lot_area_sf": round(lot_area, 2),
                    "estimated_impervious_area_sf": round(estimated_impervious, 2),
                    "coverage_ratio": round(coverage_ratio, 4),
                },
            ),
            seen,
        )


def _check_building_presence(
    parsed: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    project_type = _lower(parsed.get("project_type"))
    building_project_types = {
        "commercial_pad",
        "office_site",
        "multifamily_site",
        "strip_center",
        "industrial_site",
        "generic_site",
    }
    if project_type not in building_project_types:
        return

    has_building = False
    for action in actions:
        layer = _safe_str(action.get("layer"), "").upper()
        label = _lower(action.get("label"))
        if layer in {"BUILDING", "STRUCTURE"} or "bldg" in label or "building" in label:
            has_building = True
            break

    if not has_building:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="MISSING_BUILDING_GEOMETRY",
                severity="warning",
                message="Building-oriented project type produced no obvious building geometry.",
                category="site",
                context={"project_type": project_type},
            ),
            seen,
        )


def _check_parking_program(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    if _lower(parsed.get("mode")) != "site_plan":
        return

    meta = _safe_dict(plan.get("meta"))
    parking_program = _safe_dict(meta.get("parking_program"))
    target_count = _safe_int(parking_program.get("requested_target"), 0)
    achieved_count = _safe_int(parking_program.get("achieved_count"), 0)
    variance = achieved_count - target_count if target_count > 0 else 0
    if target_count > 0 and parking_program:
        if variance < 0:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="PARKING_SHORTFALL",
                    severity="warning",
                    message="Estimated parking appears below the requested target.",
                    category="parking",
                    context={
                        "target_count": target_count,
                        "actual_estimated_count": achieved_count,
                        "variance": variance,
                        "method": _safe_str(parking_program.get("method")),
                    },
                ),
                seen,
            )
        elif variance > max(target_count * 0.50, 30):
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="PARKING_EXCESSIVE",
                    severity="warning",
                    message="Estimated parking appears substantially above the requested target.",
                    category="parking",
                    context={
                        "target_count": target_count,
                        "actual_estimated_count": achieved_count,
                        "variance": variance,
                        "method": _safe_str(parking_program.get("method")),
                    },
                ),
                seen,
            )
        return

    site_plan = _safe_dict(parsed.get("site_plan"))
    target_count = _safe_int(site_plan.get("parking_count"), 0)

    estimated_parking_area = 0.0
    for action in actions:
        rect = _rect_from_action(action)
        if rect is None:
            continue
        layer = _safe_str(action.get("layer"), "").upper()
        label = _lower(action.get("label"))
        if layer in {"PARKING", "PAVEMENT"} or "park" in label:
            estimated_parking_area += rect["w"] * rect["h"]

    actual_estimated_count = int(round(estimated_parking_area / PARKING_EFFICIENCY_SF_PER_STALL)) if estimated_parking_area > 0.0 else 0

    if target_count > 0 and actual_estimated_count < target_count:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="PARKING_SHORTFALL",
                severity="warning",
                message="Estimated parking appears below the requested target.",
                category="parking",
                context={
                    "target_count": target_count,
                    "actual_estimated_count": actual_estimated_count,
                    "estimated_parking_area_sf": round(estimated_parking_area, 2),
                },
            ),
            seen,
        )

    if target_count > 0 and actual_estimated_count > max(target_count * 1.50, target_count + 30):
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="PARKING_EXCESSIVE",
                severity="warning",
                message="Estimated parking appears substantially above the requested target.",
                category="parking",
                context={
                    "target_count": target_count,
                    "actual_estimated_count": actual_estimated_count,
                },
            ),
            seen,
        )


def _check_parking_geometry_reasonableness(
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    parking_rects: List[Dict[str, Any]] = []

    for idx, action in enumerate(actions):
        rect = _rect_from_action(action)
        if rect is None:
            continue
        layer = _safe_str(action.get("layer"), "").upper()
        label = _lower(action.get("label"))
        if layer == "PARKING" or "park" in label:
            parking_rects.append({"index": idx, "rect": rect, "label": _safe_str(action.get("label"), "PARK")})

    for item in parking_rects:
        rect = item["rect"]
        w = rect["w"]
        h = rect["h"]
        short_dim = min(w, h)
        long_dim = max(w, h)

        if short_dim < STALL_DEPTH_FT:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="PARKING_TOO_THIN",
                    severity="warning",
                    message=f"Parking rectangle '{item['label']}' is thinner than a realistic stall depth.",
                    category="parking",
                    context={"index": item["index"], "width": round(w, 2), "height": round(h, 2)},
                ),
                seen,
            )

        if long_dim < AISLE_WIDTH_FT + STALL_DEPTH_FT:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="PARKING_MODULE_SMALL",
                    severity="warning",
                    message=f"Parking rectangle '{item['label']}' appears too small for a full parking module.",
                    category="parking",
                    context={"index": item["index"], "width": round(w, 2), "height": round(h, 2)},
                ),
                seen,
            )

        est_stalls = int(round((w * h) / PARKING_EFFICIENCY_SF_PER_STALL))
        if est_stalls == 0:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="PARKING_ZERO_STALL_PROXY",
                    severity="warning",
                    message=f"Parking rectangle '{item['label']}' yields essentially zero stalls by area proxy.",
                    category="parking",
                    context={"index": item["index"], "width": round(w, 2), "height": round(h, 2)},
                ),
                seen,
            )


def _check_drainage_completeness(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    mode = _lower(parsed.get("mode"))
    if mode not in {"drainage", "site_plan", "subdivision"}:
        return

    drainage = _canonical_drainage(plan)
    drainage_stats = _safe_dict(drainage.get("stats"))
    structures = [item for item in _safe_list(drainage.get("structures")) if isinstance(item, dict)]
    basins = [item for item in _safe_list(drainage.get("basins")) if isinstance(item, dict)]
    pipes = [item for item in _safe_list(drainage.get("pipes")) if isinstance(item, dict)]

    inlet_count = max(
        0,
        _safe_int(drainage_stats.get("inlet_count"), 0),
        sum(1 for item in structures if _lower(item.get("object_type")) == "inlet"),
    )
    has_pipe = bool(pipes) or _safe_int(drainage_stats.get("pipe_count"), 0) > 0
    has_pond = bool(basins) or _safe_int(drainage_stats.get("basin_count"), 0) > 0
    has_flow = bool(drainage_stats.get("has_flow_paths")) or has_pipe

    for action in actions:
        layer = _safe_str(action.get("layer"), "").upper()
        if layer == "DRAIN_FLOW":
            has_flow = True
        if layer == "PIPE":
            has_pipe = True
        if layer == "BASIN_BOUNDARY":
            has_pond = True
        if _text_contains(action, "inlet"):
            inlet_count += 1
        if _text_contains(action, "pond"):
            has_pond = True

    if mode == "drainage":
        if not has_flow:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="DRAINAGE_FLOW_MISSING",
                    severity="warning",
                    message="Drainage-mode plan lacks obvious flow path geometry.",
                    category="drainage",
                ),
                seen,
            )
        if not has_pipe:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="PIPE_LAYOUT_MISSING",
                    severity="warning",
                    message="Drainage-mode plan lacks obvious concept pipe routing.",
                    category="drainage",
                ),
                seen,
            )
        if not has_pond:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="POND_OR_OUTFALL_MISSING",
                    severity="warning",
                    message="Drainage-mode plan lacks obvious pond / basin / outfall indication.",
                    category="drainage",
                ),
                seen,
            )

    if inlet_count == 0 and mode in {"drainage", "site_plan"}:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="INLET_SIGNAL_WEAK",
                severity="warning",
                message="No obvious inlet objects or inlet notes were detected.",
                category="drainage",
                context={"canonical_structure_count": len(structures), "canonical_pipe_count": len(pipes), "canonical_basin_count": len(basins)},
            ),
            seen,
        )


def _check_pipe_reasonableness(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
    min_pipe_slope: float,
    max_pipe_capacity_ratio: float,
) -> None:
    meta = _safe_dict(plan.get("meta"))
    engineering_metrics = _safe_dict(meta.get("engineering_metrics"))
    storm_meta = _safe_dict(meta.get("storm_pipes"))
    runoff_cfs = max(
        _safe_float(engineering_metrics.get("rational_runoff_cfs"), 0.0),
        _safe_float(storm_meta.get("total_system_flow_cfs"), 0.0),
    )
    total_capacity = max(
        _safe_float(engineering_metrics.get("pipe_capacity_total_cfs"), 0.0),
        _safe_float(storm_meta.get("total_system_capacity_cfs"), 0.0),
        _metric_value(plan, "pipe_capacity_total_cfs", 0.0),
    )
    capacity_ratio = runoff_cfs / max(total_capacity, EPS) if total_capacity > 0.0 else None

    pipe_count = sum(1 for action in actions if _safe_str(action.get("layer"), "").upper() in {"PIPE", "STORM"})
    if pipe_count <= 0:
        pipe_count = _safe_int(storm_meta.get("pipe_count"), 0)

    if pipe_count > 0 and total_capacity <= 0.0:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="PIPE_CAPACITY_UNKNOWN",
                severity="warning",
                message="Pipe geometry exists but aggregate capacity was not computed.",
                category="pipes",
                context={"pipe_count": pipe_count, "source": "qa_fallback"},
            ),
            seen,
        )

    if capacity_ratio is not None and capacity_ratio > max_pipe_capacity_ratio:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="RUNOFF_EXCEEDS_PIPE_CAPACITY",
                severity="warning",
                message="Concept runoff exceeds estimated total pipe capacity.",
                category="pipes",
                context={
                    "rational_runoff_cfs": round(runoff_cfs, 3),
                    "pipe_capacity_total_cfs": round(total_capacity, 3),
                    "capacity_ratio": round(capacity_ratio, 3),
                },
            ),
            seen,
        )

    # Text-based slope heuristics from plan labels/notes
    for action in actions:
        if _safe_str(action.get("layer"), "").upper() != "ANNO":
            continue
        text = _safe_str(action.get("text"), "")
        upper = text.upper()
        if " S=" in upper:
            try:
                slope_token = upper.split(" S=")[1].split()[0].replace('"', "")
                slope = float(slope_token)
                if slope < min_pipe_slope:
                    _append_issue(
                        issues,
                        EngineeringCheckIssue(
                            code="PIPE_SLOPE_LOW",
                            severity="warning",
                            message=f"Pipe annotation indicates slope below minimum concept threshold ({slope:.3f}).",
                            category="pipes",
                            context={"annotated_slope": round(slope, 5), "min_pipe_slope": min_pipe_slope},
                        ),
                        seen,
                    )
            except Exception:
                pass


def _check_grading_reasonableness(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
    min_site_slope: float,
    max_parking_slope: float,
    max_ada_cross_slope: float,
    max_road_grade: float,
) -> None:
    engineering_metrics = _safe_dict(_safe_dict(plan.get("meta")).get("engineering_metrics"))
    grading_warning_count = _safe_int(engineering_metrics.get("grading_warning_count"), 0)

    if grading_warning_count >= 8:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="GRADING_WARNING_LOAD_HIGH",
                severity="warning",
                message="Grading engine reported a high number of grading warnings.",
                category="grading",
                context={"grading_warning_count": grading_warning_count},
            ),
            seen,
        )

    has_fg = any(_safe_str(a.get("layer"), "").upper() in {"FG_CONTOUR", "SURFACE", "SPOT_FG"} for a in actions)
    if _lower(parsed.get("mode")) in {"site_plan", "drainage", "subdivision"} and not has_fg:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="FG_SIGNAL_WEAK",
                severity="warning",
                message="Plan lacks obvious finished-grade contour / surface / spot grade signals.",
                category="grading",
            ),
            seen,
        )


def _check_circulation_reasonableness(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    layers = _layer_counts(actions)
    mode = _lower(parsed.get("mode"))

    if mode in {"road", "subdivision"} and layers.get("ROAD", 0) == 0:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="ROAD_SIGNAL_MISSING",
                severity="warning",
                message="Road-oriented plan lacks obvious ROAD geometry.",
                category="circulation",
            ),
            seen,
        )

    if mode == "site_plan":
        has_walk = layers.get("WALK", 0) > 0 or any(_text_contains(a, "sidewalk") for a in actions)
        if not has_walk:
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="SIDEWALK_SIGNAL_WEAK",
                    severity="warning",
                    message="Site-plan output lacks obvious sidewalk / walk network signal.",
                    category="circulation",
                ),
                seen,
            )


def _check_utility_coordination_hooks(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    project_type = _lower(parsed.get("project_type"))
    utility_expected_types = {
        "commercial_pad",
        "office_site",
        "multifamily_site",
        "strip_center",
        "industrial_site",
        "residential_subdivision",
        "corridor_roadway",
    }

    if project_type not in utility_expected_types:
        return

    layers = _layer_counts(actions)
    utility_layers_present = (
        layers.get("UTILITY", 0)
        + layers.get("WATER", 0)
        + layers.get("SEWER", 0)
        + layers.get("SAN", 0)
        + layers.get("STORM", 0)
        + layers.get("PIPE", 0)
    )

    if utility_layers_present == 0:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="UTILITY_SIGNAL_WEAK",
                severity="warning",
                message="Utility-supporting project type lacks obvious utility or pipe network signals.",
                category="utilities",
                context={"project_type": project_type},
            ),
            seen,
        )


def _check_sanitary_completeness(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    deliverables = {_lower(item) for item in _safe_list(parsed.get("deliverables"))}
    utility_network = _safe_list(parsed.get("utility_network"))
    sanitary_requested = any(any(token in item for token in ("sanitary", "sewer")) for item in deliverables)
    if not sanitary_requested:
        for feature in utility_network:
            rec = _safe_dict(feature)
            if _lower(rec.get("utility_type")) in {"sanitary", "sewer", "san"} or _safe_str(rec.get("layer"), "").upper() == "SAN":
                sanitary_requested = True
                break
    if not sanitary_requested:
        return

    sanitary = _canonical_sanitary(plan)
    if not sanitary:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="SANITARY_OUTPUT_MISSING",
                severity="warning",
                message="Sanitary deliverables were requested, but no canonical sanitary system was found.",
                category="sanitary",
            ),
            seen,
        )
        return

    if _safe_int(sanitary.get("route_count"), 0) <= 0:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="SANITARY_ROUTE_MISSING",
                severity="warning",
                message="Sanitary output lacks routed sanitary linework.",
                category="sanitary",
            ),
            seen,
        )
    missing_service_buildings = _safe_list(sanitary.get("missing_service_buildings"))
    if missing_service_buildings:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="SANITARY_BUILDING_SERVICE_MISSING",
                severity="warning",
                message="One or more buildings appear to be missing sanitary service.",
                category="sanitary",
                context={"missing_service_buildings": missing_service_buildings},
            ),
            seen,
        )
    slope_violations = _safe_list(sanitary.get("slope_violations"))
    if slope_violations:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="SANITARY_SLOPE_VIOLATION",
                severity="warning",
                message="Sanitary routing has one or more slope violations.",
                category="sanitary",
                context={"slope_violations": slope_violations[:10]},
            ),
            seen,
        )
    disconnected_segments = _safe_list(sanitary.get("disconnected_segments"))
    if disconnected_segments:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="SANITARY_DISCONNECTED",
                severity="warning",
                message="Sanitary routing has disconnected runs.",
                category="sanitary",
                context={"disconnected_segments": disconnected_segments[:10]},
            ),
            seen,
        )
    storm_conflicts = _safe_list(sanitary.get("storm_conflicts"))
    if storm_conflicts:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="SANITARY_STORM_CONFLICT",
                severity="warning",
                message="Sanitary routing appears to conflict with storm infrastructure.",
                category="sanitary",
                context={"storm_conflicts": storm_conflicts[:10]},
            ),
            seen,
        )
    if _safe_int(sanitary.get("manhole_count"), 0) <= 0:
        _append_issue(
            issues,
            EngineeringCheckIssue(
                code="SANITARY_MANHOLES_MISSING",
                severity="warning",
                message="Sanitary routing lacks manhole objects.",
                category="sanitary",
            ),
            seen,
        )


def _check_sheet_output_hooks(
    parsed: Dict[str, Any],
    plan: Dict[str, Any],
    actions: Sequence[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    deliverables = {_lower(x) for x in _safe_list(parsed.get("deliverables"))}
    if not deliverables:
        return

    if "roadway_plan" in deliverables or "road_profile" in deliverables:
        if not any(_text_contains(a, "profile") for a in actions):
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="PROFILE_HOOK_MISSING",
                    severity="warning",
                    message="Deliverables suggest profile support, but no profile-like signal was found.",
                    category="sheets",
                ),
                seen,
            )

    if "cross_sections" in deliverables:
        if not any(_text_contains(a, "section") for a in actions):
            _append_issue(
                issues,
                EngineeringCheckIssue(
                    code="CROSS_SECTION_HOOK_MISSING",
                    severity="warning",
                    message="Deliverables suggest cross-section support, but no cross-section-like signal was found.",
                    category="sheets",
                ),
                seen,
            )


# =============================================================================
# SUMMARY HELPERS
# =============================================================================

def summarize_issues(issues: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Produce compact rollup data for planners / UI / intelligence scoring.
    """
    out = {
        "issue_count": len(issues),
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "by_category": {},
        "by_code": {},
        "critical_codes": [],
    }

    for issue in issues:
        severity = _lower(issue.get("severity"))
        category = _safe_str(issue.get("category"), "general")
        code = _safe_str(issue.get("code"), "UNKNOWN")

        if severity == "error":
            out["error_count"] += 1
            out["critical_codes"].append(code)
        elif severity == "warning":
            out["warning_count"] += 1
        else:
            out["info_count"] += 1

        out["by_category"][category] = _safe_int(out["by_category"].get(category), 0) + 1
        out["by_code"][code] = _safe_int(out["by_code"].get(code), 0) + 1

    out["critical_codes"] = list(dict.fromkeys(out["critical_codes"]))
    return out


def run_combined_checks(
    existing,
    proposed,
    parsed: Optional[Dict[str, Any]],
    plan: Dict[str, Any],
    *,
    max_surface_warnings: int = 200,
    max_plan_issues: int = 300,
) -> Dict[str, Any]:
    """
    Convenience helper for callers that want both:
    - grid/surface warnings
    - plan/action-level engineering issues
    """
    surface_warnings = run_checks(existing, proposed, max_warnings=max_surface_warnings)
    plan_issues = run_plan_checks(parsed, plan, max_issues=max_plan_issues)
    return {
        "surface_warnings": surface_warnings,
        "plan_issues": plan_issues,
        "surface_summary": summarize_issues([
            {
                "code": w.get("type", "SURFACE_WARN"),
                "severity": w.get("severity", "warning"),
                "category": w.get("category", "grading"),
                "message": w.get("msg", ""),
                "context": _safe_dict(w.get("context")),
            }
            for w in surface_warnings
        ]),
        "plan_summary": summarize_issues(plan_issues),
    }
