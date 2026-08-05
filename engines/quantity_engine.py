
from __future__ import annotations

"""
quantity_engine.py (FINAL TRUE MAX ALIGNED VERSION)

Purpose
-------
Commercial-grade concept quantity / takeoff engine for the AI civil / CAD platform.

This file is aligned to planner.py and exposes the exact public function:
    compute_plan_quantities(plan)

Design intent
-------------
- preserve planner compatibility
- produce stable totals / tables / warnings payloads
- support concept-level site / civil / utility / drainage / pipe / grading quantities
- remain robust even when plan geometry is incomplete
- provide strong metadata for planner / orchestrator / system runner / UI use
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple
import math


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class QuantityLineItem:
    category: str
    name: str
    quantity: float
    units: str
    formula: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuantityResult:
    success: bool = True
    message: str = ""
    totals: Dict[str, Any] = field(default_factory=dict)
    tables: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    explain: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SMALL HELPERS
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


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def _dedupe_keep_order(values: Sequence[Any]) -> List[Any]:
    out: List[Any] = []
    seen = set()
    for value in values:
        key = repr(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _manager_export(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("manager_export"))


def _manager_metrics(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_manager_export(plan).get("metrics"))


def _metric_value(metrics: Dict[str, Any], name: str, default: float = 0.0) -> float:
    return _safe_float(_safe_dict(metrics.get(name)).get("value"), default)


def _drainage_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("drainage"))


def _storm_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    meta = _safe_dict(plan.get("meta"))
    storm_pipes = _safe_dict(meta.get("storm_pipes"))
    if storm_pipes:
        return storm_pipes
    return _safe_dict(meta.get("storm_pipe_summary"))


def _sanitary_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("sanitary"))


def _utilities_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("utilities"))


def _coordination_meta(plan: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(plan.get("meta")).get("coordination"))


def _polyline_length(points: Sequence[Sequence[Any]]) -> float:
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


def _primary_engineered_basins(drainage_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    primary: List[Dict[str, Any]] = []
    for item in _safe_list(drainage_meta.get("basins")):
        rec = _safe_dict(item)
        if not rec:
            continue
        if _safe_str(rec.get("engineering_role")) != "primary_detention":
            continue
        if not bool(rec.get("exportable")):
            continue
        if len(_safe_list(rec.get("boundary_points"))) < 3:
            continue
        primary.append(rec)
    return primary


def _rect_area(action: Dict[str, Any]) -> float:
    return max(0.0, _safe_float(action.get("width"), 0.0)) * max(0.0, _safe_float(action.get("height"), 0.0))


def _circle_area(action: Dict[str, Any]) -> float:
    r = max(0.0, _safe_float(action.get("radius"), 0.0))
    return math.pi * r * r


def _bbox_area_from_polygon(points: Sequence[Sequence[Any]]) -> float:
    xs: List[float] = []
    ys: List[float] = []
    for p in points:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            xs.append(_safe_float(p[0], 0.0))
            ys.append(_safe_float(p[1], 0.0))
    if not xs or not ys:
        return 0.0
    return max(0.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))


def _action_center(action: Dict[str, Any]) -> Tuple[float, float]:
    origin = _safe_list(action.get("origin"))
    if len(origin) >= 2:
        x = _safe_float(origin[0], 0.0)
        y = _safe_float(origin[1], 0.0)
        w = _safe_float(action.get("width"), 0.0)
        h = _safe_float(action.get("height"), 0.0)
        return x + w / 2.0, y + h / 2.0
    center = _safe_list(action.get("center"))
    if len(center) >= 2:
        return _safe_float(center[0], 0.0), _safe_float(center[1], 0.0)
    pts = _safe_list(action.get("points"))
    if pts:
        xs = [_safe_float(p[0], 0.0) for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2]
        ys = [_safe_float(p[1], 0.0) for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2]
        if xs and ys:
            return sum(xs) / len(xs), sum(ys) / len(ys)
    return 0.0, 0.0


def _canonical_action_id(action: Dict[str, Any], index: int) -> str:
    canonical_id = _safe_str(action.get("canonical_source_id"))
    if canonical_id:
        return canonical_id
    layer = _safe_str(action.get("layer"), "SITE").upper()
    label = _safe_str(action.get("label") or action.get("text"), "ACTION")
    return f"action::{index}::{layer}::{label}"


def _canonical_action_type(action: Dict[str, Any]) -> str:
    source_type = _safe_str(action.get("canonical_source_type"))
    if source_type:
        return source_type
    return "action_proxy"


# =============================================================================
# CLASSIFICATION HELPERS
# =============================================================================

def _classify_action(action: Dict[str, Any]) -> Dict[str, str]:
    layer = _safe_str(action.get("layer"), "SITE").upper()
    label = _safe_str(action.get("label"), "").upper()
    text = _safe_str(action.get("text"), "").upper()
    canonical_type = _safe_str(action.get("canonical_source_type"), "").upper()
    identity = " ".join((label, text, canonical_type))
    task = _lower(action.get("task"))

    out = {
        "layer": layer,
        "task": task,
        "discipline": "site",
        "subcategory": "generic",
    }

    if (
        "MANHOLE" in identity
        or canonical_type in {"SANITARY_MANHOLE", "STORM_MANHOLE"}
        or label.startswith("SMH-")
    ):
        out["discipline"] = "utility"
        out["subcategory"] = "manhole"
    elif "INLET" in identity or canonical_type in {"INLET", "DRAINAGE_INLET"}:
        out["discipline"] = "drainage"
        out["subcategory"] = "inlet"
    elif "OUTFALL" in identity or canonical_type in {"OUTFALL", "DRAINAGE_OUTFALL"}:
        out["discipline"] = "drainage"
        out["subcategory"] = "outfall"
    elif "HYDRANT" in identity or canonical_type in {"HYDRANT", "FIRE_HYDRANT"}:
        out["discipline"] = "utility"
        out["subcategory"] = "hydrant"
    elif layer == "BUILDING" or "BLDG" in label or "BUILDING" in label or canonical_type == "BUILDING":
        out["discipline"] = "building"
        out["subcategory"] = "building"
    elif layer in {"BRIDGE"} or "BRIDGE" in label:
        out["discipline"] = "structure"
        out["subcategory"] = "bridge"
    elif layer in {"POOL"} or "POOL" in label:
        out["discipline"] = "recreation"
        out["subcategory"] = "pool"
    elif layer in {"LOT"}:
        out["discipline"] = "site"
        out["subcategory"] = "lot"
    elif layer in {"PARKING"} or "PARK" in label or "STALLS" in text:
        out["discipline"] = "parking"
        out["subcategory"] = "parking"
    elif layer in {"ROAD", "PAVEMENT", "FIRE"} or "ROAD" in label or "DRIVE" in label or "LANE" in label:
        out["discipline"] = "road"
        out["subcategory"] = "road"
    elif layer in {"WALK"}:
        out["discipline"] = "walk"
        out["subcategory"] = "sidewalk"
    elif layer in {"PIPE", "STORM"}:
        out["discipline"] = "pipe"
        out["subcategory"] = layer.lower()
    elif layer in {"UTILITY", "WATER", "SAN"}:
        out["discipline"] = "utility"
        out["subcategory"] = layer.lower()
    elif layer in {"DRAIN", "DRAIN_FLOW", "BASIN_BOUNDARY"} or "POND" in label or "INLET" in label:
        out["discipline"] = "drainage"
        out["subcategory"] = "drainage"
    elif layer in {"FG_CONTOUR", "EG_CONTOUR", "SURFACE", "SPOT_FG", "SPOT_EG"}:
        out["discipline"] = "grading"
        out["subcategory"] = "grading"
    elif task == "text_note":
        out["discipline"] = "annotation"
        out["subcategory"] = "annotation"

    return out


# =============================================================================
# CORE TAKEOFF
# =============================================================================

class QuantityEngine:
    """
    Concept quantity engine aligned to planner.py.

    Computes:
    - counts by discipline
    - simple planimetrics (area / length)
    - concept parking estimates
    - pipe / utility lengths
    - drainage / grading signal metrics
    - UI/planner-friendly tables
    """

    STALL_AREA_SF = 325.0
    SIDEWALK_DEFAULT_WIDTH_FT = 5.0
    ROAD_DEFAULT_WIDTH_FT = 24.0
    UTILITY_DEFAULT_TRENCH_WIDTH_FT = 4.0
    PIPE_DEFAULT_TRENCH_WIDTH_FT = 4.0

    def compute(self, plan: Dict[str, Any]) -> QuantityResult:
        if not isinstance(plan, dict):
            return QuantityResult(
                success=False,
                message="Plan must be a dictionary.",
                totals={},
                tables={},
                warnings=["Invalid plan payload passed to quantity engine."],
            )

        actions = [a for a in _safe_list(plan.get("actions")) if isinstance(a, dict)]
        meta = _safe_dict(plan.get("meta"))
        manager_metrics = _manager_metrics(plan)
        drainage_meta = _drainage_meta(plan)
        sanitary_meta = _sanitary_meta(plan)
        storm_meta = _storm_meta(plan)
        utilities_meta = _utilities_meta(plan)
        coordination_meta = _coordination_meta(plan)
        drainage_stats = _safe_dict(drainage_meta.get("stats"))
        sanitary_stats = _safe_dict(sanitary_meta.get("stats"))
        storm_stats = _safe_dict(storm_meta.get("stats"))
        utilities_stats = _safe_dict(utilities_meta.get("stats"))
        canonical_integrity = _safe_dict(meta.get("canonical_integrity") or _safe_dict(meta.get("truth_audit")).get("canonical_integrity"))
        canonical_integrity_blocked = bool(canonical_integrity.get("blocked"))
        primary_basins = _primary_engineered_basins(drainage_meta)
        canonical_basins = [_safe_dict(item) for item in _safe_list(drainage_meta.get("basins")) if _safe_dict(item)]
        drainage_export_validation = _safe_dict(drainage_meta.get("export_validation"))
        if primary_basins and not drainage_export_validation:
            storm_segments = _safe_list(storm_meta.get("segments"))
            drainage_export_validation = {
                "ready": bool(
                    _safe_dict(drainage_meta).get("success")
                    and storm_segments
                    and _safe_dict(storm_meta.get("graph_validation")).get("valid", False)
                    and _safe_dict(storm_meta.get("hydraulic_validation")).get("valid", False)
                    and not _safe_list(storm_meta.get("missing_data_segments"))
                ),
            }
        warnings: List[str] = []
        assumptions: List[str] = [
            "Quantities prefer accepted canonical stage summaries and use ProjectManager metrics only as fallback where canonical values are missing.",
            "Where widths are not explicit for linear features, discipline defaults are used.",
        ]
        if canonical_integrity_blocked:
            warnings.append("Canonical state is dirty, stale, invalid, or cache-only; quantity totals are blocked from production signoff.")

        quantity_audit: Dict[str, Dict[str, Any]] = {}

        counts = {
            "action_count": len(actions),
            "building_count": 0,
            "parking_area_count": 0,
            "road_feature_count": 0,
            "sidewalk_feature_count": 0,
            "pipe_feature_count": 0,
            "utility_feature_count": 0,
            "sanitary_feature_count": 0,
            "drainage_feature_count": 0,
            "grading_feature_count": 0,
            "annotation_count": 0,
            "bridge_feature_count": 0,
            "pool_feature_count": 0,
            "lot_feature_count": 0,
        }

        areas = {
            "building_area_sf": 0.0,
            "parking_area_sf": 0.0,
            "road_area_sf": 0.0,
            "sidewalk_area_sf": 0.0,
            "pond_area_sf": 0.0,
            "surface_area_sf": 0.0,
            "estimated_impervious_area_sf": 0.0,
            "bridge_area_sf": 0.0,
            "pool_area_sf": 0.0,
        }

        lengths = {
            "road_length_ft": 0.0,
            "drive_length_ft": 0.0,
            "sidewalk_length_ft": 0.0,
            "pipe_length_ft": 0.0,
            "utility_length_ft": 0.0,
            "sanitary_length_ft": 0.0,
            "sanitary_main_length_ft": 0.0,
            "sanitary_lateral_length_ft": 0.0,
            "drainage_flow_length_ft": 0.0,
            "grading_contour_length_ft": 0.0,
        }

        unit_counts = {
            "estimated_parking_stalls": 0,
            "inlet_count": 0,
            "pond_count": 0,
            "sanitary_manhole_count": 0,
            "sanitary_service_count": 0,
            "text_note_count": 0,
            "fg_contour_count": 0,
            "eg_contour_count": 0,
            "coordination_resolved_conflict_count": 0,
            "coordination_unresolved_conflict_count": 0,
        }

        # ---------------------------------------------------------------------
        # Pass 1: classify every action and compute base metrics
        # ---------------------------------------------------------------------
        for index, action in enumerate(actions):
            info = _classify_action(action)
            layer = info["layer"]
            task = info["task"]
            discipline = info["discipline"]
            label = _safe_str(action.get("label"), "")
            text = _safe_str(action.get("text"), "")
            points = _safe_list(action.get("points"))
            canonical_id = _canonical_action_id(action, index)
            canonical_type = _canonical_action_type(action)

            area = 0.0
            length = 0.0

            if task == "rectangle":
                area = _rect_area(action)
            elif task == "circle":
                area = _circle_area(action)
            elif task in {"polygon"}:
                area = _bbox_area_from_polygon(points)
                length = _polyline_length(points + points[:1]) if len(points) >= 3 else 0.0
            elif task in {"polyline"}:
                length = _polyline_length(points)

            if discipline == "building":
                counts["building_count"] += 1
                areas["building_area_sf"] += area
                audit = quantity_audit.setdefault(
                    "building_area_sf",
                    {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_building_geometry", "assumptions_involved": False},
                )
                audit["source_object_ids"].append(canonical_id)
                audit["source_object_types"].append(canonical_type)

            elif discipline == "parking":
                counts["parking_area_count"] += 1
                areas["parking_area_sf"] += area
                audit = quantity_audit.setdefault(
                    "parking_area_sf",
                    {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_parking_geometry", "assumptions_involved": False},
                )
                audit["source_object_ids"].append(canonical_id)
                audit["source_object_types"].append(canonical_type)
                if "STALLS" in text.upper():
                    tokens = "".join(ch if ch.isdigit() else " " for ch in text).split()
                    for token in tokens:
                        try:
                            unit_counts["estimated_parking_stalls"] = max(unit_counts["estimated_parking_stalls"], int(token))
                        except Exception:
                            pass

            elif discipline == "road":
                counts["road_feature_count"] += 1
                if area > 0:
                    areas["road_area_sf"] += area
                    audit = quantity_audit.setdefault(
                        "road_area_sf",
                        {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_road_geometry", "assumptions_involved": False},
                    )
                    audit["source_object_ids"].append(canonical_id)
                    audit["source_object_types"].append(canonical_type)
                if length > 0:
                    lengths["road_length_ft"] += length
                    audit = quantity_audit.setdefault(
                        "road_length_ft",
                        {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_road_centerline_length", "assumptions_involved": False},
                    )
                    audit["source_object_ids"].append(canonical_id)
                    audit["source_object_types"].append(canonical_type)
                    if "DRIVE" in label.upper():
                        lengths["drive_length_ft"] += length

            elif discipline == "walk":
                counts["sidewalk_feature_count"] += 1
                if area > 0:
                    areas["sidewalk_area_sf"] += area
                    audit = quantity_audit.setdefault(
                        "sidewalk_area_sf",
                        {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_sidewalk_geometry", "assumptions_involved": False},
                    )
                    audit["source_object_ids"].append(canonical_id)
                    audit["source_object_types"].append(canonical_type)
                elif length > 0:
                    lengths["sidewalk_length_ft"] += length
                    areas["sidewalk_area_sf"] += length * self.SIDEWALK_DEFAULT_WIDTH_FT
                    audit = quantity_audit.setdefault(
                        "sidewalk_length_ft",
                        {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_sidewalk_length", "assumptions_involved": False},
                    )
                    audit["source_object_ids"].append(canonical_id)
                    audit["source_object_types"].append(canonical_type)
                    area_audit = quantity_audit.setdefault(
                        "sidewalk_area_sf",
                        {"source_object_ids": [], "source_object_types": [], "derivation_method": "length_x_default_width", "assumptions_involved": True},
                    )
                    area_audit["source_object_ids"].append(canonical_id)
                    area_audit["source_object_types"].append(canonical_type)
                    area_audit["assumptions_involved"] = True

            elif discipline == "pipe":
                counts["pipe_feature_count"] += 1
                lengths["pipe_length_ft"] += length
                audit = quantity_audit.setdefault(
                    "pipe_length_ft",
                    {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_storm_pipe_lengths", "assumptions_involved": False},
                )
                audit["source_object_ids"].append(canonical_id)
                audit["source_object_types"].append(canonical_type)
                if "INLET" in label.upper() or "CI-" in label.upper() or "INLET" in text.upper() or "CI-" in text.upper():
                    unit_counts["inlet_count"] += 1

            elif discipline == "utility":
                counts["utility_feature_count"] += 1
                lengths["utility_length_ft"] += length
                audit = quantity_audit.setdefault(
                    "utility_length_ft",
                    {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_utility_lengths", "assumptions_involved": False},
                )
                audit["source_object_ids"].append(canonical_id)
                audit["source_object_types"].append(canonical_type)
                if layer == "SAN":
                    counts["sanitary_feature_count"] += 1
                    lengths["sanitary_length_ft"] += length
                    san_audit = quantity_audit.setdefault(
                        "sanitary_length_ft",
                        {"source_object_ids": [], "source_object_types": [], "derivation_method": "sum_sanitary_lengths", "assumptions_involved": False},
                    )
                    san_audit["source_object_ids"].append(canonical_id)
                    san_audit["source_object_types"].append(canonical_type)

            elif discipline == "drainage":
                counts["drainage_feature_count"] += 1
                if "INLET" in label.upper() or "INLET" in text.upper():
                    unit_counts["inlet_count"] += 1
                    audit = quantity_audit.setdefault(
                        "inlet_count",
                        {"source_object_ids": [], "source_object_types": [], "derivation_method": "count_inlet_structures", "assumptions_involved": False},
                    )
                    audit["source_object_ids"].append(canonical_id)
                    audit["source_object_types"].append(canonical_type)
                if "POND" in label.upper() or layer == "BASIN_BOUNDARY":
                    unit_counts["pond_count"] += 1
                    areas["pond_area_sf"] += area
                    audit = quantity_audit.setdefault(
                        "pond_count",
                        {"source_object_ids": [], "source_object_types": [], "derivation_method": "count_basin_objects", "assumptions_involved": False},
                    )
                    audit["source_object_ids"].append(canonical_id)
                    audit["source_object_types"].append(canonical_type)
                if layer == "DRAIN_FLOW":
                    lengths["drainage_flow_length_ft"] += length

            elif discipline == "grading":
                counts["grading_feature_count"] += 1
                if layer == "FG_CONTOUR":
                    unit_counts["fg_contour_count"] += 1
                    lengths["grading_contour_length_ft"] += length
                if layer == "EG_CONTOUR":
                    unit_counts["eg_contour_count"] += 1
                if layer in {"SURFACE", "SPOT_FG", "SPOT_EG"}:
                    areas["surface_area_sf"] += area

            elif discipline == "annotation":
                counts["annotation_count"] += 1
                unit_counts["text_note_count"] += 1
            elif discipline == "structure" and info["subcategory"] == "bridge":
                counts["bridge_feature_count"] += 1
                if area > 0:
                    areas["bridge_area_sf"] += area
            elif discipline == "recreation" and info["subcategory"] == "pool":
                counts["pool_feature_count"] += 1
                if area > 0:
                    areas["pool_area_sf"] += area
            elif discipline == "site" and info["subcategory"] == "lot":
                counts["lot_feature_count"] += 1

        # ---------------------------------------------------------------------
        # Pass 2: fill inferred metrics
        # ---------------------------------------------------------------------
        if unit_counts["estimated_parking_stalls"] <= 0 and areas["parking_area_sf"] > 0:
            unit_counts["estimated_parking_stalls"] = max(0, int(round(areas["parking_area_sf"] / self.STALL_AREA_SF)))
            quantity_audit.setdefault(
                "estimated_parking_stalls",
                {
                    "source_object_ids": list(quantity_audit.get("parking_area_sf", {}).get("source_object_ids", [])),
                    "source_object_types": list(quantity_audit.get("parking_area_sf", {}).get("source_object_types", [])),
                    "derivation_method": "parking_area_divided_by_stall_area",
                    "assumptions_involved": True,
                },
            )

        if manager_metrics:
            canonical_parking_count = _safe_int(_metric_value(manager_metrics, "parking_count", 0.0), 0)
            counts["action_count"] = max(counts["action_count"], _safe_int(_metric_value(manager_metrics, "layout_action_count", 0.0), counts["action_count"]))
            if canonical_parking_count > 0:
                unit_counts["estimated_parking_stalls"] = canonical_parking_count
                quantity_audit["estimated_parking_stalls"] = {
                    "source_object_ids": [f"metric::parking_count"],
                    "source_object_types": ["manager_metric"],
                    "derivation_method": "canonical_manager_metric",
                    "assumptions_involved": False,
                }
            counts["building_count"] = max(
                counts["building_count"],
                _safe_int(1 if _metric_value(manager_metrics, "layout_building_area_sf", 0.0) > 0 else 0, counts["building_count"]),
            )
            if not storm_meta:
                counts["pipe_feature_count"] = max(
                    counts["pipe_feature_count"],
                    _safe_int(_metric_value(manager_metrics, "storm_pipe_count", 0.0), counts["pipe_feature_count"]),
                )
            if not utilities_meta:
                counts["utility_feature_count"] = max(
                    counts["utility_feature_count"],
                    _safe_int(_metric_value(manager_metrics, "utility_route_count", 0.0), counts["utility_feature_count"]),
                )
            if not sanitary_meta:
                counts["sanitary_feature_count"] = max(
                    counts["sanitary_feature_count"],
                    _safe_int(_metric_value(manager_metrics, "sanitary_route_count", 0.0), counts["sanitary_feature_count"]),
                )
            if not drainage_meta:
                counts["drainage_feature_count"] = max(
                    counts["drainage_feature_count"],
                    _safe_int(_metric_value(manager_metrics, "drainage_pipe_count", 0.0), counts["drainage_feature_count"]),
                )
            counts["grading_feature_count"] = max(
                counts["grading_feature_count"],
                _safe_int(_metric_value(manager_metrics, "grading_low_point_count", 0.0), counts["grading_feature_count"]),
            )

            areas["building_area_sf"] = max(areas["building_area_sf"], _metric_value(manager_metrics, "layout_building_area_sf", 0.0))
            areas["parking_area_sf"] = max(areas["parking_area_sf"], _metric_value(manager_metrics, "layout_parking_area_sf", 0.0))
            areas["road_area_sf"] = max(areas["road_area_sf"], _metric_value(manager_metrics, "layout_road_area_sf", 0.0))
            areas["sidewalk_area_sf"] = max(areas["sidewalk_area_sf"], _metric_value(manager_metrics, "layout_sidewalk_area_sf", 0.0))
            areas["estimated_impervious_area_sf"] = max(
                areas["estimated_impervious_area_sf"],
                _metric_value(manager_metrics, "layout_impervious_area_sf", 0.0),
            )

            if not storm_meta:
                lengths["pipe_length_ft"] = max(lengths["pipe_length_ft"], _metric_value(manager_metrics, "storm_pipe_length_ft", 0.0))
            if not utilities_meta:
                lengths["utility_length_ft"] = max(lengths["utility_length_ft"], _metric_value(manager_metrics, "utility_total_length_ft", 0.0))
            if not sanitary_meta:
                lengths["sanitary_length_ft"] = max(lengths["sanitary_length_ft"], _metric_value(manager_metrics, "sanitary_total_length_ft", 0.0))
                lengths["sanitary_main_length_ft"] = max(lengths["sanitary_main_length_ft"], _metric_value(manager_metrics, "sanitary_main_length_ft", 0.0))
                lengths["sanitary_lateral_length_ft"] = max(lengths["sanitary_lateral_length_ft"], _metric_value(manager_metrics, "sanitary_lateral_length_ft", 0.0))

            if not drainage_meta:
                unit_counts["inlet_count"] = max(unit_counts["inlet_count"], _safe_int(_metric_value(manager_metrics, "drainage_low_point_count", 0.0)))
                unit_counts["pond_count"] = max(unit_counts["pond_count"], _safe_int(_metric_value(manager_metrics, "drainage_basin_count", 0.0)))
            if not sanitary_meta:
                unit_counts["sanitary_manhole_count"] = max(unit_counts["sanitary_manhole_count"], _safe_int(_metric_value(manager_metrics, "sanitary_manhole_count", 0.0)))
                unit_counts["sanitary_service_count"] = max(unit_counts["sanitary_service_count"], _safe_int(_metric_value(manager_metrics, "sanitary_service_count", 0.0)))

        if drainage_meta:
            counts["drainage_feature_count"] = max(
                counts["drainage_feature_count"],
                _safe_int(drainage_stats.get("structure_count"), 0) + max(len(primary_basins), len(canonical_basins)),
            )
            counts["pipe_feature_count"] = max(counts["pipe_feature_count"], _safe_int(drainage_stats.get("pipe_count"), 0))
            unit_counts["inlet_count"] = max(unit_counts["inlet_count"], _safe_int(drainage_stats.get("inlet_count"), 0))
            if drainage_export_validation.get("ready", False):
                unit_counts["pond_count"] = max(
                    len(primary_basins),
                    _safe_int(drainage_stats.get("primary_detention_count"), 0),
                )
            else:
                unit_counts["pond_count"] = max(
                    unit_counts["pond_count"],
                    len(canonical_basins),
                    _safe_int(drainage_stats.get("basin_count"), 0),
                    _safe_int(drainage_stats.get("primary_detention_count"), 0),
                )
            lengths["pipe_length_ft"] = max(lengths["pipe_length_ft"], _safe_float(drainage_stats.get("pipe_total_length_ft"), 0.0))
            structures = [_safe_dict(item) for item in _safe_list(drainage_meta.get("structures"))]
            basins = primary_basins if drainage_export_validation.get("ready", False) else canonical_basins
            if structures:
                quantity_audit["inlet_count"] = {
                    "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("name"), "STRUCT")) for item in structures if _safe_str(item.get("id") or item.get("name"))],
                    "source_object_types": [_safe_str(item.get("canonical_type") or item.get("structure_type"), "drainage_structure") for item in structures if _safe_str(item.get("id") or item.get("name"))],
                    "derivation_method": "count_canonical_drainage_structures",
                    "assumptions_involved": False,
                }
            if basins:
                areas["pond_area_sf"] = max(
                    areas["pond_area_sf"],
                    sum(_safe_float(item.get("top_of_bank_area_sf"), _safe_float(item.get("area_sf"), 0.0)) for item in basins),
                )
                quantity_audit["pond_count"] = {
                    "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("name"), "BASIN")) for item in basins if _safe_str(item.get("id") or item.get("name"))],
                    "source_object_types": [_safe_str(item.get("canonical_type") or item.get("object_type"), "detention_basin") for item in basins if _safe_str(item.get("id") or item.get("name"))],
                    "derivation_method": "count_primary_engineered_detention_basins" if drainage_export_validation.get("ready", False) else "count_canonical_drainage_basins",
                    "assumptions_involved": False,
                }
                quantity_audit["pond_area_sf"] = {
                    "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("name"), "BASIN")) for item in basins if _safe_str(item.get("id") or item.get("name"))],
                    "source_object_types": ["detention_basin" for item in basins if _safe_str(item.get("id") or item.get("name"))],
                    "derivation_method": "sum_primary_engineered_detention_basin_area",
                    "assumptions_involved": False,
                }

        if storm_meta:
            storm_segments = [_safe_dict(item) for item in _safe_list(storm_meta.get("segments"))]
            if storm_segments:
                segment_pipe_length = sum(
                    _safe_float(item.get("length_ft"), 0.0)
                    or _polyline_length(_safe_list(item.get("path") or item.get("route_points")))
                    for item in storm_segments
                )
                canonical_pipe_length = next(
                    (
                        value
                        for value in (
                            _safe_float(storm_meta.get("total_length_ft"), 0.0),
                            _safe_float(storm_stats.get("total_length_ft"), 0.0),
                            segment_pipe_length,
                        )
                        if value > 0.0
                    ),
                    0.0,
                )
                counts["pipe_feature_count"] = len(storm_segments)
                if canonical_pipe_length > 0.0:
                    lengths["pipe_length_ft"] = canonical_pipe_length
                quantity_audit["pipe_length_ft"] = {
                    "source_object_ids": [
                        _safe_str(item.get("id"), _safe_str(item.get("pipe") or item.get("name"), "PIPE"))
                        for item in storm_segments
                        if _safe_str(item.get("id") or item.get("pipe") or item.get("name"))
                    ],
                    "source_object_types": [
                        "storm_pipe_segment"
                        for item in storm_segments
                        if _safe_str(item.get("id") or item.get("pipe") or item.get("name"))
                    ],
                    "derivation_method": "sum_canonical_storm_segments",
                    "assumptions_involved": False,
                }

        if sanitary_meta:
            counts["sanitary_feature_count"] = max(counts["sanitary_feature_count"], _safe_int(sanitary_stats.get("segment_count"), 0))
            counts["utility_feature_count"] = max(counts["utility_feature_count"], _safe_int(sanitary_meta.get("route_count"), 0))
            lengths["sanitary_length_ft"] = max(lengths["sanitary_length_ft"], _safe_float(sanitary_stats.get("total_length_ft"), 0.0), _safe_float(sanitary_meta.get("total_length_ft"), 0.0))
            lengths["sanitary_main_length_ft"] = max(lengths["sanitary_main_length_ft"], _safe_float(sanitary_stats.get("main_length_ft"), 0.0), _safe_float(sanitary_meta.get("main_length_ft"), 0.0))
            lengths["sanitary_lateral_length_ft"] = max(lengths["sanitary_lateral_length_ft"], _safe_float(sanitary_stats.get("lateral_length_ft"), 0.0), _safe_float(sanitary_meta.get("lateral_length_ft"), 0.0))
            unit_counts["sanitary_manhole_count"] = max(unit_counts["sanitary_manhole_count"], _safe_int(sanitary_stats.get("manhole_count"), 0), _safe_int(sanitary_meta.get("manhole_count"), 0))
            unit_counts["sanitary_service_count"] = max(unit_counts["sanitary_service_count"], _safe_int(sanitary_stats.get("service_count"), 0), _safe_int(sanitary_meta.get("service_count"), 0))
            sanitary_segments = [_safe_dict(item) for item in _safe_list(sanitary_meta.get("segments"))]
            if sanitary_segments:
                quantity_audit["sanitary_length_ft"] = {
                    "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("name"), "SAN")) for item in sanitary_segments if _safe_str(item.get("id") or item.get("name"))],
                    "source_object_types": ["sanitary_segment" for item in sanitary_segments if _safe_str(item.get("id") or item.get("name"))],
                    "derivation_method": "sum_canonical_sanitary_segments",
                    "assumptions_involved": False,
                }
                quantity_audit["sanitary_main_length_ft"] = {
                    "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("name"), "SAN")) for item in sanitary_segments if _safe_str(item.get("segment_role")) == "main" and _safe_str(item.get("id") or item.get("name"))],
                    "source_object_types": ["sanitary_main" for item in sanitary_segments if _safe_str(item.get("segment_role")) == "main" and _safe_str(item.get("id") or item.get("name"))],
                    "derivation_method": "sum_canonical_sanitary_mains",
                    "assumptions_involved": False,
                }
                quantity_audit["sanitary_lateral_length_ft"] = {
                    "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("name"), "SAN")) for item in sanitary_segments if _safe_str(item.get("segment_role")) == "lateral" and _safe_str(item.get("id") or item.get("name"))],
                    "source_object_types": ["sanitary_lateral" for item in sanitary_segments if _safe_str(item.get("segment_role")) == "lateral" and _safe_str(item.get("id") or item.get("name"))],
                    "derivation_method": "sum_canonical_sanitary_laterals",
                    "assumptions_involved": False,
                }
            manholes = [_safe_dict(item) for item in _safe_list(sanitary_meta.get("manholes"))]
            if manholes:
                quantity_audit["sanitary_manhole_count"] = {
                    "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("name"), "SMH")) for item in manholes if _safe_str(item.get("id") or item.get("name"))],
                    "source_object_types": ["sanitary_manhole" for item in manholes if _safe_str(item.get("id") or item.get("name"))],
                    "derivation_method": "count_canonical_sanitary_manholes",
                    "assumptions_involved": False,
                }

        if utilities_meta:
            utility_segments = [
                _safe_dict(item)
                for item in _safe_list(_safe_dict(utilities_meta.get("conflict_hooks")).get("utility_segments"))
                if _safe_dict(item)
            ]
            if not utility_segments:
                utility_segments = [_safe_dict(item) for item in _safe_list(utilities_meta.get("segments")) if _safe_dict(item)]
            canonical_utility_length = max(
                _safe_float(utilities_meta.get("total_length_ft"), 0.0),
                _safe_float(utilities_stats.get("total_length_ft"), 0.0),
                sum(
                    _safe_float(item.get("length_ft"), 0.0)
                    or _polyline_length(_safe_list(item.get("route_points") or item.get("path")))
                    for item in utility_segments
                ),
            )
            if utility_segments:
                counts["utility_feature_count"] = len(utility_segments)
                if canonical_utility_length > 0.0:
                    lengths["utility_length_ft"] = canonical_utility_length
                quantity_audit["utility_length_ft"] = {
                    "source_object_ids": [
                        _safe_str(item.get("id"), _safe_str(item.get("name"), "UTILITY"))
                        for item in utility_segments
                        if _safe_str(item.get("id") or item.get("name"))
                    ],
                    "source_object_types": [
                        _safe_str(item.get("system_type"), "utility_segment")
                        for item in utility_segments
                        if _safe_str(item.get("id") or item.get("name"))
                    ],
                    "derivation_method": "sum_canonical_utility_segments",
                    "assumptions_involved": False,
                }

        if coordination_meta:
            unit_counts["coordination_resolved_conflict_count"] = max(
                unit_counts["coordination_resolved_conflict_count"],
                _safe_int(coordination_meta.get("resolved_count"), 0),
                _safe_int(_metric_value(manager_metrics, "coordination_resolved_conflict_count", 0.0), 0),
            )
            unit_counts["coordination_unresolved_conflict_count"] = max(
                unit_counts["coordination_unresolved_conflict_count"],
                _safe_int(coordination_meta.get("unresolved_count"), 0),
                _safe_int(_metric_value(manager_metrics, "coordination_unresolved_conflict_count", 0.0), 0),
            )

        areas["estimated_impervious_area_sf"] = (
            areas["building_area_sf"]
            + areas["parking_area_sf"]
            + areas["road_area_sf"]
            + areas["sidewalk_area_sf"]
        )
        quantity_audit["estimated_impervious_area_sf"] = {
            "source_object_ids": _dedupe_keep_order(
                list(quantity_audit.get("building_area_sf", {}).get("source_object_ids", []))
                + list(quantity_audit.get("parking_area_sf", {}).get("source_object_ids", []))
                + list(quantity_audit.get("road_area_sf", {}).get("source_object_ids", []))
                + list(quantity_audit.get("sidewalk_area_sf", {}).get("source_object_ids", []))
            ),
            "source_object_types": _dedupe_keep_order(
                list(quantity_audit.get("building_area_sf", {}).get("source_object_types", []))
                + list(quantity_audit.get("parking_area_sf", {}).get("source_object_types", []))
                + list(quantity_audit.get("road_area_sf", {}).get("source_object_types", []))
                + list(quantity_audit.get("sidewalk_area_sf", {}).get("source_object_types", []))
            ),
            "derivation_method": "sum_impervious_component_quantities",
            "assumptions_involved": bool(quantity_audit.get("sidewalk_area_sf", {}).get("assumptions_involved")),
        }

        lot_area_sf = self._extract_lot_area(actions)
        lot_area_sf = max(lot_area_sf, _metric_value(manager_metrics, "lot_area_sf", 0.0))
        if lot_area_sf > 0:
            impervious_ratio = areas["estimated_impervious_area_sf"] / lot_area_sf
        else:
            impervious_ratio = 0.0
            warnings.append("Lot area could not be determined from plan actions; coverage ratio may be incomplete.")

        # ---------------------------------------------------------------------
        # Tables
        # ---------------------------------------------------------------------
        summary_table = [
            {"metric": "Action count", "value": counts["action_count"], "units": "ea"},
            {"metric": "Buildings", "value": counts["building_count"], "units": "ea"},
            {"metric": "Parking areas", "value": counts["parking_area_count"], "units": "ea"},
            {"metric": "Estimated parking stalls", "value": unit_counts["estimated_parking_stalls"], "units": "ea"},
            {"metric": "Building area", "value": _round(areas["building_area_sf"]), "units": "sf"},
            {"metric": "Parking area", "value": _round(areas["parking_area_sf"]), "units": "sf"},
            {"metric": "Road area", "value": _round(areas["road_area_sf"]), "units": "sf"},
            {"metric": "Sidewalk area", "value": _round(areas["sidewalk_area_sf"]), "units": "sf"},
            {"metric": "Bridge area", "value": _round(areas["bridge_area_sf"]), "units": "sf"},
            {"metric": "Pool area", "value": _round(areas["pool_area_sf"]), "units": "sf"},
            {"metric": "Pipe length", "value": _round(lengths["pipe_length_ft"]), "units": "ft"},
            {"metric": "Utility length", "value": _round(lengths["utility_length_ft"]), "units": "ft"},
            {"metric": "Sanitary length", "value": _round(lengths["sanitary_length_ft"]), "units": "ft"},
            {"metric": "Impervious area", "value": _round(areas["estimated_impervious_area_sf"]), "units": "sf"},
            {"metric": "Impervious ratio", "value": _round(impervious_ratio, 4), "units": "ratio"},
        ]

        discipline_table = [
            {"discipline": "building", "count": counts["building_count"]},
            {"discipline": "parking", "count": counts["parking_area_count"]},
            {"discipline": "road", "count": counts["road_feature_count"]},
            {"discipline": "walk", "count": counts["sidewalk_feature_count"]},
            {"discipline": "pipe", "count": counts["pipe_feature_count"]},
            {"discipline": "utility", "count": counts["utility_feature_count"]},
            {"discipline": "sanitary", "count": counts["sanitary_feature_count"]},
            {"discipline": "drainage", "count": counts["drainage_feature_count"]},
            {"discipline": "grading", "count": counts["grading_feature_count"]},
            {"discipline": "annotation", "count": counts["annotation_count"]},
            {"discipline": "bridge", "count": counts["bridge_feature_count"]},
            {"discipline": "pool", "count": counts["pool_feature_count"]},
            {"discipline": "lot", "count": counts["lot_feature_count"]},
        ]

        area_table = [
            {"category": "building_area_sf", "value": _round(areas["building_area_sf"]), "units": "sf"},
            {"category": "parking_area_sf", "value": _round(areas["parking_area_sf"]), "units": "sf"},
            {"category": "road_area_sf", "value": _round(areas["road_area_sf"]), "units": "sf"},
            {"category": "sidewalk_area_sf", "value": _round(areas["sidewalk_area_sf"]), "units": "sf"},
            {"category": "pond_area_sf", "value": _round(areas["pond_area_sf"]), "units": "sf"},
            {"category": "bridge_area_sf", "value": _round(areas["bridge_area_sf"]), "units": "sf"},
            {"category": "pool_area_sf", "value": _round(areas["pool_area_sf"]), "units": "sf"},
            {"category": "surface_area_sf", "value": _round(areas["surface_area_sf"]), "units": "sf"},
            {"category": "estimated_impervious_area_sf", "value": _round(areas["estimated_impervious_area_sf"]), "units": "sf"},
        ]

        linear_table = [
            {"category": "road_length_ft", "value": _round(lengths["road_length_ft"]), "units": "ft"},
            {"category": "drive_length_ft", "value": _round(lengths["drive_length_ft"]), "units": "ft"},
            {"category": "sidewalk_length_ft", "value": _round(lengths["sidewalk_length_ft"]), "units": "ft"},
            {"category": "pipe_length_ft", "value": _round(lengths["pipe_length_ft"]), "units": "ft"},
            {"category": "utility_length_ft", "value": _round(lengths["utility_length_ft"]), "units": "ft"},
            {"category": "sanitary_length_ft", "value": _round(lengths["sanitary_length_ft"]), "units": "ft"},
            {"category": "sanitary_main_length_ft", "value": _round(lengths["sanitary_main_length_ft"]), "units": "ft"},
            {"category": "sanitary_lateral_length_ft", "value": _round(lengths["sanitary_lateral_length_ft"]), "units": "ft"},
            {"category": "drainage_flow_length_ft", "value": _round(lengths["drainage_flow_length_ft"]), "units": "ft"},
            {"category": "grading_contour_length_ft", "value": _round(lengths["grading_contour_length_ft"]), "units": "ft"},
        ]

        feature_table = [
            {"feature": "inlets", "count": unit_counts["inlet_count"], "units": "ea"},
            {"feature": "ponds", "count": unit_counts["pond_count"], "units": "ea"},
            {"feature": "sanitary_manholes", "count": unit_counts["sanitary_manhole_count"], "units": "ea"},
            {"feature": "sanitary_services", "count": unit_counts["sanitary_service_count"], "units": "ea"},
            {"feature": "coordination_conflicts_resolved", "count": unit_counts["coordination_resolved_conflict_count"], "units": "ea"},
            {"feature": "coordination_conflicts_unresolved", "count": unit_counts["coordination_unresolved_conflict_count"], "units": "ea"},
            {"feature": "fg_contours", "count": unit_counts["fg_contour_count"], "units": "ea"},
            {"feature": "eg_contours", "count": unit_counts["eg_contour_count"], "units": "ea"},
            {"feature": "text_notes", "count": unit_counts["text_note_count"], "units": "ea"},
        ]

        totals = {
            "action_count": counts["action_count"],
            "building_count": counts["building_count"],
            "parking_area_count": counts["parking_area_count"],
            "estimated_parking_stalls": unit_counts["estimated_parking_stalls"],
            "road_feature_count": counts["road_feature_count"],
            "sidewalk_feature_count": counts["sidewalk_feature_count"],
            "pipe_feature_count": counts["pipe_feature_count"],
            "utility_feature_count": counts["utility_feature_count"],
            "sanitary_feature_count": counts["sanitary_feature_count"],
            "drainage_feature_count": counts["drainage_feature_count"],
            "grading_feature_count": counts["grading_feature_count"],
            "annotation_count": counts["annotation_count"],
            "bridge_feature_count": counts["bridge_feature_count"],
            "pool_feature_count": counts["pool_feature_count"],
            "lot_feature_count": counts["lot_feature_count"],
            "lot_area_sf": _round(lot_area_sf),
            "building_area_sf": _round(areas["building_area_sf"]),
            "parking_area_sf": _round(areas["parking_area_sf"]),
            "road_area_sf": _round(areas["road_area_sf"]),
            "sidewalk_area_sf": _round(areas["sidewalk_area_sf"]),
            "pond_area_sf": _round(areas["pond_area_sf"]),
            "bridge_area_sf": _round(areas["bridge_area_sf"]),
            "pool_area_sf": _round(areas["pool_area_sf"]),
            "surface_area_sf": _round(areas["surface_area_sf"]),
            "estimated_impervious_area_sf": _round(areas["estimated_impervious_area_sf"]),
            "estimated_impervious_coverage_ratio": _round(impervious_ratio, 4),
            "road_length_ft": _round(lengths["road_length_ft"]),
            "drive_length_ft": _round(lengths["drive_length_ft"]),
            "sidewalk_length_ft": _round(lengths["sidewalk_length_ft"]),
            "pipe_length_ft": _round(lengths["pipe_length_ft"]),
            "utility_length_ft": _round(lengths["utility_length_ft"]),
            "sanitary_length_ft": _round(lengths["sanitary_length_ft"]),
            "sanitary_main_length_ft": _round(lengths["sanitary_main_length_ft"]),
            "sanitary_lateral_length_ft": _round(lengths["sanitary_lateral_length_ft"]),
            "drainage_flow_length_ft": _round(lengths["drainage_flow_length_ft"]),
            "grading_contour_length_ft": _round(lengths["grading_contour_length_ft"]),
            "inlet_count": unit_counts["inlet_count"],
            "pond_count": unit_counts["pond_count"],
            "sanitary_manhole_count": unit_counts["sanitary_manhole_count"],
            "sanitary_service_count": unit_counts["sanitary_service_count"],
            "coordination_resolved_conflict_count": unit_counts["coordination_resolved_conflict_count"],
            "coordination_unresolved_conflict_count": unit_counts["coordination_unresolved_conflict_count"],
            "fg_contour_count": unit_counts["fg_contour_count"],
            "eg_contour_count": unit_counts["eg_contour_count"],
        }

        tables = {
            "summary": summary_table,
            "discipline_breakdown": discipline_table,
            "area_takeoff": area_table,
            "linear_takeoff": linear_table,
            "feature_counts": feature_table,
        }

        explain = {
            "method": "concept_quantity_takeoff",
            "key_logic": [
                "Read accepted canonical stage summaries first, then use manager metrics only when canonical values are missing.",
                "Computed rectangle and circle areas directly from geometry.",
                "Computed polyline lengths directly from points.",
                "Estimated parking stalls from explicit text first, then parking area proxy if needed.",
                "Computed impervious area from buildings, parking, roads, and sidewalks.",
            ],
            "meta_summary": {
                "project_name": _safe_str(plan.get("project_name"), "Generated Plan"),
                "units": _safe_str(plan.get("units"), "ft"),
                "planner_score_total": _safe_float(_safe_dict(meta.get("planner_score")).get("total"), 0.0),
                "canonical_coordination_used": bool(coordination_meta),
                "quantity_traceability_complete": True,
                "canonical_integrity_blocked": canonical_integrity_blocked,
            },
        }

        storm_segments = [_safe_dict(item) for item in _safe_list(_safe_dict(meta.get("storm_pipes")).get("segments"))]
        if storm_segments:
            quantity_audit["pipe_length_ft"] = {
                "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("pipe") or item.get("name"), "PIPE")) for item in storm_segments if _safe_str(item.get("id") or item.get("pipe") or item.get("name"))],
                "source_object_types": ["storm_pipe_segment" for item in storm_segments if _safe_str(item.get("id") or item.get("pipe") or item.get("name"))],
                "derivation_method": "sum_canonical_storm_segments",
                "assumptions_involved": False,
            }
        utility_segments = [_safe_dict(item) for item in _safe_list(_safe_dict(_safe_dict(meta.get("utilities")).get("conflict_hooks")).get("utility_segments"))]
        if utility_segments:
            quantity_audit["utility_length_ft"] = {
                "source_object_ids": [_safe_str(item.get("id"), _safe_str(item.get("name"), "UTILITY")) for item in utility_segments if _safe_str(item.get("id") or item.get("name"))],
                "source_object_types": [_safe_str(item.get("system_type"), "utility_segment") for item in utility_segments if _safe_str(item.get("id") or item.get("name"))],
                "derivation_method": "sum_canonical_utility_segments",
                "assumptions_involved": False,
            }

        for metric_name, audit in list(quantity_audit.items()):
            audit["source_object_ids"] = list(dict.fromkeys([_safe_str(item) for item in _safe_list(audit.get("source_object_ids")) if _safe_str(item)]))
            audit["source_object_types"] = list(dict.fromkeys([_safe_str(item) for item in _safe_list(audit.get("source_object_types")) if _safe_str(item)]))
            audit["trace_complete"] = bool(audit["source_object_ids"])
            if any(item == "action_proxy" for item in audit["source_object_types"]):
                audit["assumptions_involved"] = True
            if metric_name in totals:
                audit["value"] = totals[metric_name]
        materially_positive = {
            name: row for name, row in quantity_audit.items()
            if _safe_float(totals.get(name), 0.0) > 0.0 or _safe_int(totals.get(name), 0) > 0
        }
        trace_gaps = {
            name: {
                "value": row.get("value"),
                "derivation_method": row.get("derivation_method"),
                "source_object_types": list(row.get("source_object_types") or []),
            }
            for name, row in materially_positive.items()
            if not bool(row.get("trace_complete"))
        }
        explain["quantity_audit"] = quantity_audit
        explain["trace_gaps"] = trace_gaps
        explain["canonical_integrity"] = canonical_integrity
        explain["meta_summary"]["quantity_traceability_complete"] = not bool(trace_gaps)
        quantity_traceability_blocked = bool(trace_gaps)

        if counts["action_count"] == 0:
            warnings.append("Plan contains no actions; quantity totals are empty or zero.")
        if counts["building_count"] == 0:
            warnings.append("No building geometry was detected.")
        if counts["parking_area_count"] == 0 and unit_counts["estimated_parking_stalls"] == 0:
            warnings.append("No parking geometry was detected.")
        if counts["pipe_feature_count"] == 0 and counts["drainage_feature_count"] > 0:
            warnings.append("Drainage features were detected without explicit pipe linework.")
        if counts["utility_feature_count"] == 0 and counts["building_count"] > 0:
            warnings.append("Buildings were detected without explicit utility linework.")
        if quantity_traceability_blocked:
            warnings.append("Material quantity totals have missing source object IDs; quantity takeoff is blocked from production signoff.")

        return QuantityResult(
            success=not canonical_integrity_blocked and not quantity_traceability_blocked,
            message=(
                "Concept quantity takeoff completed, but production signoff is blocked by canonical integrity."
                if canonical_integrity_blocked
                else "Concept quantity takeoff completed, but production signoff is blocked by missing quantity traceability."
                if quantity_traceability_blocked
                else "Concept quantity takeoff completed."
            ),
            totals=totals,
            tables=tables,
            warnings=sorted(set(warnings)),
            assumptions=assumptions,
            explain=explain,
        )

    # -------------------------------------------------------------------------
    # internal helpers
    # -------------------------------------------------------------------------

    def _extract_lot_area(self, actions: Sequence[Dict[str, Any]]) -> float:
        lot_candidates: List[float] = []
        for action in actions:
            if _lower(action.get("task")) != "rectangle":
                continue
            layer = _safe_str(action.get("layer"), "").upper()
            label = _safe_str(action.get("label"), "").upper()
            if layer == "SITE" or label == "LOT":
                area = _rect_area(action)
                if area > 0:
                    lot_candidates.append(area)
        if not lot_candidates:
            return 0.0
        return max(lot_candidates)


# =============================================================================
# PUBLIC API
# =============================================================================

def compute_plan_quantities(plan: Dict[str, Any]) -> QuantityResult:
    return QuantityEngine().compute(plan)
