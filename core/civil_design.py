from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from math import hypot
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


Point = Tuple[float, float]


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


def _truthy_mapping(value: Any) -> bool:
    return bool(_safe_dict(value))


def _first_number(*values: Any, default: float = 0.0) -> float:
    for value in values:
        number = _safe_float(value, float("nan"))
        if number == number:
            return number
    return float(default)


def _has_number(value: Any) -> bool:
    try:
        if value is None:
            return False
        float(value)
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class CivilDesignStandards:
    """Concept-level civil design standards used for deterministic engine checks.

    These are not jurisdictional rules. They are intentionally conservative
    coordination defaults so the engines can explain when a design is ready,
    incomplete, or assumption-driven.
    """

    version: str = "civil_design_v1"
    min_site_slope: float = 0.005
    max_parking_slope: float = 0.06
    max_ada_cross_slope: float = 0.02
    max_road_grade: float = 0.10
    min_gravity_pipe_slope: float = 0.003
    max_pipe_capacity_ratio: float = 0.95
    min_utility_cover_ft: float = 3.0
    min_gravity_utility_horizontal_separation_ft: float = 10.0
    min_pressure_gravity_horizontal_separation_ft: float = 10.0
    min_electric_gas_horizontal_separation_ft: float = 3.0
    min_vertical_crossing_separation_ft: float = 1.5
    max_sanitary_manhole_spacing_ft: float = 400.0
    max_storm_structure_spacing_ft: float = 400.0
    min_detention_freeboard_ft: float = 1.0
    max_detention_drawdown_hours: float = 72.0
    min_emergency_overflow_freeboard_ft: float = 0.5
    max_sanitary_capacity_ratio: float = 0.85
    min_water_sanitary_vertical_separation_ft: float = 1.5
    max_water_velocity_fps: float = 8.0
    min_water_residual_pressure_psi: float = 20.0
    max_hydrant_spacing_ft: float = 500.0
    min_fire_flow_gpm: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_STANDARDS = CivilDesignStandards()


def _ratio_from_rule_text(text: str) -> Optional[float]:
    match = None
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(%|percent)?", text, re.IGNORECASE):
        pass
    if match is None:
        return None
    value = _safe_float(match.group(1), 0.0)
    unit = _safe_str(match.group(2)).lower()
    if unit in {"%", "percent"} or value > 1.0:
        return value / 100.0
    return value


def _length_ft_from_rule_text(text: str) -> Optional[float]:
    match = None
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(feet|foot|ft|'|inches|inch|in)?", text, re.IGNORECASE):
        pass
    if match is None:
        return None
    value = _safe_float(match.group(1), 0.0)
    unit = _safe_str(match.group(2), "ft").lower()
    if unit in {"inches", "inch", "in"}:
        return value / 12.0
    return value


def _hours_from_rule_text(text: str) -> Optional[float]:
    match = None
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(hours|hour|hrs|hr)?", text, re.IGNORECASE):
        pass
    if match is None:
        return None
    return _safe_float(match.group(1), 0.0)


def _flow_gpm_from_rule_text(text: str) -> Optional[float]:
    match = None
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(gpm|gallons per minute)?", text, re.IGNORECASE):
        pass
    if match is None:
        return None
    return _safe_float(match.group(1), 0.0)


def _plain_number_from_rule_text(text: str) -> Optional[float]:
    match = None
    for match in re.finditer(r"(\d+(?:\.\d+)?)", text, re.IGNORECASE):
        pass
    if match is None:
        return None
    return _safe_float(match.group(1), 0.0)


def _psi_from_rule_text(text: str) -> Optional[float]:
    match = None
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(psi)?", text, re.IGNORECASE):
        pass
    if match is None:
        return None
    return _safe_float(match.group(1), 0.0)


def _accepted_rules_from_meta(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    for source in (
        _safe_dict(meta.get("design_standards")),
        _safe_dict(meta.get("jurisdiction_standards")),
        _safe_dict(meta.get("company_standards")),
    ):
        for item in _safe_list(source.get("rules")):
            rule = _safe_dict(item)
            if rule and _safe_str(rule.get("status"), "accepted").lower() == "accepted":
                rules.append(rule)
    acceptance = _safe_dict(meta.get("standards_acceptance"))
    for item in _safe_list(acceptance.get("accepted_rules")):
        rule = _safe_dict(item)
        if rule and _safe_str(rule.get("status"), "accepted").lower() == "accepted":
            rules.append(rule)
    return rules


def standards_from_meta(meta: Dict[str, Any], base: CivilDesignStandards = DEFAULT_STANDARDS) -> CivilDesignStandards:
    values = base.to_dict()
    for rule in _accepted_rules_from_meta(meta):
        topic = _safe_str(rule.get("topic")).lower()
        text = " ".join(
            _safe_str(rule.get(key))
            for key in ("topic", "candidate_value", "value", "notes")
            if _safe_str(rule.get(key))
        ).lower()
        if "ada" in text and "cross slope" in text:
            ratio = _ratio_from_rule_text(text)
            if ratio is not None:
                values["max_ada_cross_slope"] = ratio
        elif "road" in text and ("grade" in text or "slope" in text):
            ratio = _ratio_from_rule_text(text)
            if ratio is not None:
                values["max_road_grade"] = ratio
        elif "pipe capacity" in text or ("capacity ratio" in text and "storm" in topic):
            ratio = _ratio_from_rule_text(text)
            if ratio is not None:
                values["max_pipe_capacity_ratio"] = ratio
        elif "sanitary" in text and "capacity" in text:
            ratio = _ratio_from_rule_text(text)
            if ratio is not None:
                values["max_sanitary_capacity_ratio"] = ratio
        elif "cover" in text:
            length = _length_ft_from_rule_text(text)
            if length is not None:
                values["min_utility_cover_ft"] = length
        elif "vertical" in text and "separation" in text:
            length = _length_ft_from_rule_text(text)
            if length is not None:
                values["min_vertical_crossing_separation_ft"] = length
        elif "separation" in text:
            length = _length_ft_from_rule_text(text)
            if length is not None:
                values["min_gravity_utility_horizontal_separation_ft"] = length
                values["min_pressure_gravity_horizontal_separation_ft"] = length
        elif "manhole" in text and "spacing" in text:
            length = _length_ft_from_rule_text(text)
            if length is not None:
                values["max_sanitary_manhole_spacing_ft"] = length
        elif "hydrant" in text and "spacing" in text:
            length = _length_ft_from_rule_text(text)
            if length is not None:
                values["max_hydrant_spacing_ft"] = length
        elif "fire flow" in text:
            flow = _flow_gpm_from_rule_text(text)
            if flow is not None:
                values["min_fire_flow_gpm"] = flow
        elif "residual pressure" in text or "minimum pressure" in text:
            pressure = _psi_from_rule_text(text)
            if pressure is not None:
                values["min_water_residual_pressure_psi"] = pressure
        elif "water" in text and "velocity" in text:
            velocity = _plain_number_from_rule_text(text)
            if velocity is not None:
                values["max_water_velocity_fps"] = velocity
        elif "drawdown" in text:
            hours = _hours_from_rule_text(text)
            if hours is not None:
                values["max_detention_drawdown_hours"] = hours
    version = _safe_str(_safe_dict(meta.get("design_standards")).get("version"), base.version)
    return replace(base, version=version, **{key: value for key, value in values.items() if key != "version"})


def coerce_point(value: Any) -> Optional[Point]:
    if isinstance(value, dict):
        if "x" in value and "y" in value:
            return (_safe_float(value.get("x")), _safe_float(value.get("y")))
        if "lng" in value and "lat" in value:
            return (_safe_float(value.get("lng")), _safe_float(value.get("lat")))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (_safe_float(value[0]), _safe_float(value[1]))
    return None


def coerce_path(value: Any) -> List[Point]:
    points: List[Point] = []
    for item in _safe_list(value):
        point = coerce_point(item)
        if point is not None:
            points.append(point)
    return points


def path_length(points: Sequence[Point]) -> float:
    total = 0.0
    for index in range(1, len(points)):
        total += hypot(points[index][0] - points[index - 1][0], points[index][1] - points[index - 1][1])
    return total


def path_bbox(points: Sequence[Point]) -> Optional[Tuple[float, float, float, float]]:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def station_point(points: Sequence[Point], distance_ft: float) -> Optional[Point]:
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    remaining = max(0.0, _safe_float(distance_ft))
    for index in range(1, len(points)):
        start = points[index - 1]
        end = points[index]
        seg_len = hypot(end[0] - start[0], end[1] - start[1])
        if seg_len <= 0.0:
            continue
        if remaining <= seg_len:
            t = remaining / seg_len
            return (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
        remaining -= seg_len
    return points[-1]


def sample_path(points: Sequence[Point], *, spacing_ft: float = 50.0, max_samples: int = 120) -> List[Point]:
    if not points:
        return []
    total = path_length(points)
    if total <= 0.0:
        return [points[0]]
    spacing = max(1.0, _safe_float(spacing_ft, 50.0))
    count = min(max_samples, max(2, int(total / spacing) + 2))
    if count <= 2:
        return [points[0], points[-1]]
    return [station_point(points, total * i / (count - 1)) or points[-1] for i in range(count)]


def _point_segment_distance(point: Point, start: Point, end: Point) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    denom = dx * dx + dy * dy
    if denom <= 0.0:
        return hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    qx = ax + t * dx
    qy = ay + t * dy
    return hypot(px - qx, py - qy)


def segment_clearance(a1: Point, a2: Point, b1: Point, b2: Point) -> float:
    return min(
        _point_segment_distance(a1, b1, b2),
        _point_segment_distance(a2, b1, b2),
        _point_segment_distance(b1, a1, a2),
        _point_segment_distance(b2, a1, a2),
    )


def path_clearance(path_a: Sequence[Point], path_b: Sequence[Point]) -> float:
    if not path_a or not path_b:
        return 0.0
    if len(path_a) == 1 or len(path_b) == 1:
        return min(hypot(a[0] - b[0], a[1] - b[1]) for a in path_a for b in path_b)
    best = float("inf")
    for ai in range(1, len(path_a)):
        for bi in range(1, len(path_b)):
            best = min(best, segment_clearance(path_a[ai - 1], path_a[ai], path_b[bi - 1], path_b[bi]))
    return 0.0 if best == float("inf") else best


def rect_from_action(action: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    origin = _safe_list(action.get("origin"))
    if len(origin) >= 2:
        width = _safe_float(action.get("width"), _safe_float(action.get("w"), 0.0))
        height = _safe_float(action.get("height"), _safe_float(action.get("h"), 0.0))
        if width > 0.0 and height > 0.0:
            x = _safe_float(origin[0])
            y = _safe_float(origin[1])
            return (x, y, x + width, y + height)
    center = coerce_point(action.get("center"))
    radius = _safe_float(action.get("radius"), 0.0)
    if center is not None and radius > 0.0:
        return (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    return None


def rect_area(rect: Optional[Tuple[float, float, float, float]]) -> float:
    if rect is None:
        return 0.0
    x1, y1, x2, y2 = rect
    return max(0.0, abs(x2 - x1)) * max(0.0, abs(y2 - y1))


def action_path(action: Dict[str, Any]) -> List[Point]:
    for key in ("points", "path", "route_points", "polyline"):
        path = coerce_path(action.get(key))
        if path:
            return path
    rect = rect_from_action(action)
    if rect is not None:
        x1, y1, x2, y2 = rect
        return [(x1, y1), (x2, y2)]
    center = coerce_point(action.get("center"))
    return [center] if center else []


def segment_path(record: Dict[str, Any]) -> List[Point]:
    for key in ("route_points", "path", "points", "polyline"):
        path = coerce_path(record.get(key))
        if path:
            return path
    start = coerce_point(record.get("start") or record.get("from_point") or record.get("upstream_point"))
    end = coerce_point(record.get("end") or record.get("to_point") or record.get("downstream_point"))
    if start and end:
        return [start, end]
    return []


def max_spacing_along_path(points: Sequence[Point], structures: Sequence[Dict[str, Any]]) -> float:
    if len(points) < 2 or len(structures) < 2:
        return path_length(points)
    stations: List[float] = []
    total = path_length(points)
    samples = sample_path(points, spacing_ft=max(total / 80.0, 1.0), max_samples=90)
    running: Dict[Point, float] = {}
    cumulative = 0.0
    for index, point in enumerate(samples):
        if index > 0:
            cumulative += hypot(point[0] - samples[index - 1][0], point[1] - samples[index - 1][1])
        running[point] = cumulative
    for structure in structures:
        p = coerce_point(structure)
        if not p:
            continue
        nearest = min(samples, key=lambda item: hypot(item[0] - p[0], item[1] - p[1]))
        stations.append(running.get(nearest, 0.0))
    if len(stations) < 2:
        return total
    stations = sorted(max(0.0, min(total, station)) for station in stations)
    return max(stations[index] - stations[index - 1] for index in range(1, len(stations)))


def classify_action_system(action: Dict[str, Any]) -> str:
    layer = _safe_str(action.get("layer")).lower()
    label = _safe_str(action.get("label")).lower()
    canonical = _safe_str(action.get("canonical_source_type")).lower()
    haystack = " ".join([layer, label, canonical])
    if "sanitary" in haystack or "sewer" in haystack:
        return "sanitary"
    if "storm" in haystack or "drainage" in haystack or "basin" in haystack or "pond" in haystack:
        return "drainage"
    if "water" in haystack or "utility" in haystack or "gas" in haystack or "electric" in haystack:
        return "utilities"
    if "road" in haystack:
        return "road"
    if "parking" in haystack or "pavement" in haystack:
        return "parking"
    if "building" in haystack or "structure" in haystack:
        return "building"
    return "site"


def utility_pairing_rule(system_a: str, system_b: str, standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    pair = {system_a.lower(), system_b.lower()}
    if {"water", "sanitary"} <= pair or {"water", "storm"} <= pair:
        return {
            "horizontal_separation_ft": standards.min_pressure_gravity_horizontal_separation_ft,
            "vertical_separation_ft": standards.min_vertical_crossing_separation_ft,
            "priority": "pressure_utility_protected",
            "lower_owner": "gravity",
        }
    if {"storm", "sanitary"} <= pair:
        return {
            "horizontal_separation_ft": standards.min_gravity_utility_horizontal_separation_ft,
            "vertical_separation_ft": standards.min_vertical_crossing_separation_ft,
            "priority": "sanitary_service_continuity",
            "lower_owner": "storm_where_feasible",
        }
    if {"electric", "gas"} <= pair:
        return {
            "horizontal_separation_ft": standards.min_electric_gas_horizontal_separation_ft,
            "vertical_separation_ft": standards.min_vertical_crossing_separation_ft,
            "priority": "joint_trench_review",
            "lower_owner": "jurisdictional_standard",
        }
    return {
        "horizontal_separation_ft": standards.min_gravity_utility_horizontal_separation_ft,
        "vertical_separation_ft": standards.min_vertical_crossing_separation_ft,
        "priority": "coordinate_crossing",
        "lower_owner": "case_by_case",
    }


def _missing(system: str, field: str, why: str, action: str) -> Dict[str, Any]:
    return {
        "system": system,
        "field": field,
        "why_needed": why,
        "suggested_next_action": action,
    }


def _system_result(
    *,
    status: str,
    source: str = "missing",
    missing: Optional[List[Dict[str, Any]]] = None,
    warnings: Optional[List[str]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "source": source,
        "missing": missing or [],
        "warnings": warnings or [],
        "metrics": metrics or {},
    }


def _production_gap(area: str, field: str, why: str, action: str) -> Dict[str, Any]:
    return {
        "area": area,
        "field": field,
        "why_needed": why,
        "suggested_next_action": action,
    }


def _standards_official_url(url: str) -> bool:
    lowered = _safe_str(url).lower()
    return (
        lowered.startswith("https://")
        and "google.com/search" not in lowered
        and "bing.com/search" not in lowered
        and not lowered.startswith("internal://")
    )


def _standards_production_blockers(standards: Dict[str, Any], accepted_rules: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    validation = _safe_dict(standards.get("production_validation"))
    blockers = [_safe_dict(item) for item in _safe_list(validation.get("blockers")) if _safe_dict(item)]
    if blockers:
        return blockers
    if standards.get("production_usable") is True:
        source_urls = [_safe_str(url) for url in _safe_list(standards.get("source_urls")) if _safe_str(url)]
        if not source_urls:
            source_urls = [_safe_str(rule.get("source_url")) for rule in accepted_rules if _safe_str(rule.get("source_url"))]
        has_official = any(_standards_official_url(url) for url in source_urls)
        has_rules = bool(accepted_rules or _safe_list(standards.get("rules")))
        has_traceable_authority = has_official and has_rules
        if has_traceable_authority:
            return []
    derived: List[Dict[str, Any]] = []
    if not accepted_rules and not _safe_list(standards.get("rules")):
        derived.append({"field": "accepted_rules", "reason": "No accepted standards rules are available."})
    source_urls = [_safe_str(url) for url in _safe_list(standards.get("source_urls")) if _safe_str(url)]
    if not source_urls:
        source_urls = [_safe_str(rule.get("source_url")) for rule in accepted_rules if _safe_str(rule.get("source_url"))]
    if not any(_standards_official_url(url) for url in source_urls):
        derived.append({"field": "official_sources", "reason": "Accepted standards do not cite an official HTTPS source.", "source_urls": source_urls})
    baseline_rules = [
        _safe_str(rule.get("rule_id"))
        for rule in accepted_rules
        if _safe_str(rule.get("source_url")).startswith("internal://")
        or _safe_str(rule.get("confidence")).lower() == "baseline"
        or _safe_str(rule.get("source_id")) == "civora_us_baseline"
    ]
    if baseline_rules:
        derived.append({"field": "baseline_rules", "reason": "Baseline concept rules cannot be production authority without an official source.", "rule_ids": baseline_rules})
    incomplete = []
    for rule in accepted_rules:
        missing = [
            key
            for key in ("discipline", "topic", "candidate_value", "source_url", "source_section")
            if not _safe_str(rule.get(key))
        ]
        if missing:
            incomplete.append({"rule_id": _safe_str(rule.get("rule_id"), "unnamed"), "missing": missing})
    if incomplete:
        derived.append({"field": "rule_metadata", "reason": "Accepted standards are missing traceable metadata.", "rules": incomplete})
    return derived


def _coordinate_system_blockers(coordinate: Dict[str, Any]) -> List[Dict[str, Any]]:
    rec = _safe_dict(coordinate)
    blockers = [_safe_dict(item) for item in _safe_list(rec.get("blockers")) if _safe_dict(item)]
    if blockers:
        return blockers
    epsg_text = " ".join(
        _safe_str(rec.get(key)).lower()
        for key in ("epsg", "epsg_code", "srid", "name", "crs", "projection")
        if _safe_str(rec.get(key))
    )
    units = _safe_str(rec.get("units")).lower().replace(" ", "_")
    is_geographic = (
        "4326" in epsg_text
        or "4269" in epsg_text
        or "4258" in epsg_text
        or units in {"degree", "degrees", "decimal_degrees"}
        or rec.get("is_geographic") is True
    )
    if is_geographic:
        blockers.append(
            {
                "field": "coordinate_system",
                "reason": "Latitude/longitude CRS is not production-usable for civil engineering distances; use a projected site CRS.",
            }
        )
    if rec.get("production_usable") is False:
        blockers.append(
            {
                "field": "coordinate_system",
                "reason": "Coordinate system is marked not production-usable.",
            }
        )
    return blockers


def _has_any(mapping: Dict[str, Any], keys: Iterable[str]) -> bool:
    return any(mapping.get(key) not in (None, "", [], {}) for key in keys)


def check_standards_truth(meta: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    gaps: List[Dict[str, Any]] = []
    acceptance = _safe_dict(meta.get("standards_acceptance"))
    accepted_rules = [_safe_dict(item) for item in _safe_list(acceptance.get("accepted_rules")) if _safe_dict(item)]
    standards = _safe_dict(meta.get("design_standards") or meta.get("standards"))
    if not standards and accepted_rules:
        standards = {
            "source": "accepted_standards_review_packet",
            "accepted_rule_count": len(accepted_rules),
            "rules": accepted_rules,
            "production_validation": _safe_dict(acceptance.get("production_validation")),
            "production_usable": bool(acceptance.get("production_usable")),
        }
    jurisdiction = _safe_dict(meta.get("jurisdiction_standards"))
    company = _safe_dict(meta.get("company_standards"))
    if not standards:
        gaps.append(
            _production_gap(
                "standards",
                "design_standards",
                "Production civil design needs a standards pack for slopes, cover, separation, ADA, stormwater, sanitary, and CAD conventions.",
                "Attach a jurisdiction/company standards profile before permit-grade design.",
            )
        )
    else:
        if not accepted_rules:
            accepted_rules = [_safe_dict(item) for item in _safe_list(standards.get("rules")) if _safe_dict(item)]
        for blocker in _standards_production_blockers(standards, accepted_rules):
            field = _safe_str(blocker.get("field"), "standards_traceability")
            reason = _safe_str(blocker.get("reason"), "Standards pack is not traceable enough for production QA.")
            gaps.append(
                _production_gap(
                    "standards",
                    field,
                    reason,
                    "Accept or edit standards rules from official jurisdiction/company sources before production QA.",
                )
            )
    if not jurisdiction:
        warnings.append("No jurisdiction standards profile is attached.")
    if not company:
        warnings.append("No company CAD/design standards profile is attached.")
    if _safe_dict(meta.get("standards_review_packet")) and not accepted_rules:
        warnings.append("Standards candidates exist, but no rules have been accepted for production QA.")
    if standards and bool(standards.get("needs_source_review")):
        warnings.append("Accepted standards still need source review before permit use.")
    status = "ready" if not gaps else "needs_production_input"
    return _system_result(
        status=status,
        source=_safe_str(standards.get("source"), "default_concept_standards"),
        warnings=warnings,
        metrics={
            "has_design_standards": bool(standards),
            "accepted_rule_count": len(accepted_rules),
            "has_jurisdiction_standards": bool(jurisdiction),
            "has_company_standards": bool(company),
            "production_gaps": gaps,
        },
    )


def check_existing_conditions_truth(meta: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    gaps: List[Dict[str, Any]] = []
    grading = _safe_dict(meta.get("grading") or meta.get("grading_summary"))
    summary = _safe_dict(meta.get("existing_conditions_summary"))
    summary_survey = _safe_dict(summary.get("survey"))
    summary_gis = _safe_dict(summary.get("gis"))
    summary_coordinate = _safe_dict(summary.get("coordinate_system"))
    source = (
        _safe_str(summary_survey.get("surface_source"))
        or _safe_str(grading.get("source_quality"))
        or _safe_str(grading.get("grading_source_quality"))
        or _safe_str(_safe_dict(grading.get("existing_surface")).get("source_quality"))
        or "missing"
    )
    survey = _safe_dict(meta.get("survey") or meta.get("survey_file") or _safe_dict(grading.get("existing_surface")).get("survey"))
    gis = _safe_dict(meta.get("gis_layers") or meta.get("existing_conditions"))
    survey_ready = bool(summary_survey.get("ready")) or bool(survey) or source == "survey"
    gis_ready = bool(summary_gis.get("ready")) or _has_any(gis, ("parcels", "easements", "row", "floodplain", "wetlands", "existing_utilities"))
    meta_coordinate = _safe_dict(meta.get("coordinate_system"))
    coordinate_ready = bool(summary_coordinate.get("ready")) or bool(meta_coordinate)
    coordinate_blockers = _coordinate_system_blockers(summary_coordinate or meta_coordinate)
    if source != "survey" and not survey_ready:
        gaps.append(
            _production_gap(
                "existing_conditions",
                "survey_surface",
                "Terrain is useful for concept work, but permit-ready grading needs survey/control or an explicitly approved data source.",
                "Import survey points, breaklines, contours, or a stamped existing surface.",
            )
        )
    if not gis_ready:
        gaps.append(
            _production_gap(
                "existing_conditions",
                "gis_layers",
                "Real coordination needs parcels, ROW/easements, floodplain/wetlands, and existing utilities where available.",
                "Attach GIS/existing-condition layers before production coordination.",
            )
        )
    if not coordinate_ready:
        gaps.append(
            _production_gap(
                "existing_conditions",
                "coordinate_system",
                "Production civil design needs a real CRS/EPSG/projection so survey, GIS, utilities, and exports share one coordinate truth.",
                "Attach the project coordinate system or mark the design as local-coordinate concept only.",
            )
        )
    for blocker in coordinate_blockers:
        gaps.append(
            _production_gap(
                "existing_conditions",
                _safe_str(blocker.get("field"), "coordinate_system"),
                _safe_str(blocker.get("reason"), "Coordinate system is not production-usable."),
                "Attach a projected engineering CRS with distance units before production coordination/export.",
            )
        )
    if source in {"terrain", "image_inferred", "address_context"}:
        warnings.append(f"Existing surface is {source}-derived, not survey.")
    warnings.extend(_safe_list(summary.get("warnings")))
    return _system_result(
        status="ready" if not gaps else "needs_production_input",
        source=source,
        warnings=warnings,
        metrics={
            "surface_source": source,
            "has_survey": survey_ready,
            "has_gis_layers": gis_ready,
            "has_coordinate_system": coordinate_ready,
            "production_gaps": gaps,
        },
    )


def check_hydraulic_depth_truth(meta: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    gaps: List[Dict[str, Any]] = []
    storm = _safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary"))
    drainage = _safe_dict(meta.get("drainage") or meta.get("drainage_canonical"))
    if storm and _safe_list(storm.get("segments")):
        source_text = " ".join(
            _safe_str(storm.get(key)).lower()
            for key in ("hydraulic_depth_source", "hydraulic_source", "source_detail", "source")
            if _safe_str(storm.get(key))
        )
        if source_text and "concept" in source_text and "proxy" in source_text:
            gaps.append(
                _production_gap(
                    "hydraulics",
                    "hydraulic_depth_source",
                    "Concept proxy HGL/EGL is not production hydraulic evidence.",
                    "Run the storm hydraulic engine or attach traceable external hydraulic calculations.",
                )
            )
        required = {
            "hgl_profile": "Storm production design needs HGL to verify surcharging and inlet/junction elevations.",
            "egl_profile": "Storm production design needs EGL/energy losses for hydraulic grade review.",
            "tailwater": "Storm production design needs tailwater/backwater assumptions at the outfall.",
            "inlet_capacity_checks": "Production drainage needs inlet capacity, spread, and bypass checks.",
        }
        for field, why in required.items():
            if field == "tailwater":
                present = _has_any(storm, ("tailwater_elev_ft", "tailwater_condition", "tailwater"))
            else:
                present = bool(storm.get(field))
            if not present:
                gaps.append(_production_gap("hydraulics", field, why, f"Run or attach {field.replace('_', ' ')} calculations."))
        inlet_checks = [_safe_dict(item) for item in _safe_list(storm.get("inlet_capacity_checks"))]
        invalid_inlets = [
            _safe_str(item.get("inlet"), f"inlet_{index}")
            for index, item in enumerate(inlet_checks, start=1)
            if item.get("valid") is False
        ]
        if invalid_inlets:
            gaps.append(
                _production_gap(
                    "hydraulics",
                    "inlet_capacity_validity",
                    "Inlet spread, capacity, and bypass checks must pass before storm production review.",
                    "Adjust inlet type/count/capacity or revise catchment routing.",
                )
            )
        backwater = _safe_dict(storm.get("backwater_validation"))
        if backwater and backwater.get("valid") is False:
            gaps.append(
                _production_gap(
                    "hydraulics",
                    "backwater_validation",
                    "Tailwater/backwater validation shows one or more storm segments are surcharged.",
                    "Revise outfall/tailwater assumptions, pipe slope/size, or detention outlet controls.",
                )
            )
        engine_summary = _safe_dict(storm.get("hydraulic_engine_summary"))
        surcharged_nodes = [
            _safe_dict(node)
            for node in _safe_list(engine_summary.get("critical_nodes"))
            if _safe_dict(node).get("surcharge_risk")
        ]
        if surcharged_nodes:
            gaps.append(
                _production_gap(
                    "hydraulics",
                    "node_surcharge",
                    "Storm hydraulic engine reports node HGL surcharge risk.",
                    "Lower HGL, add capacity, revise profile, or document a permitted surcharge condition.",
                )
            )
    else:
        warnings.append("Storm network is not present; hydraulic depth checks are waiting on storm design.")
    detention_routes = _safe_list(drainage.get("detention_routing")) or _safe_list(drainage.get("stage_storage"))
    if drainage and _safe_list(drainage.get("basins")) and not detention_routes:
        gaps.append(
            _production_gap(
                "hydraulics",
                "detention_routing",
                "Permit-grade stormwater needs stage-storage, outlet, drawdown, and overflow routing.",
                "Run detention routing for the selected basin/outfall.",
            )
        )
    return _system_result(
        status="ready" if not gaps else "needs_production_input",
        source=_safe_str(storm.get("hydraulic_source") or storm.get("source"), "missing"),
        warnings=warnings,
        metrics={"production_gaps": gaps, "gap_count": len(gaps)},
    )


def check_grading_detail_truth(meta: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    gaps: List[Dict[str, Any]] = []
    grading = _safe_dict(meta.get("grading") or meta.get("grading_summary"))
    detail_fields = {
        "road_crown_controls": "Roadway grading needs crown/cross-slope controls.",
        "curb_gutter_controls": "Curb/gutter grading is needed for pavement drainage and gutter flow.",
        "ada_path_checks": "ADA routes need running slope and cross-slope checks.",
        "pad_tie_ins": "Building pads need tie-in elevations and positive drainage away from doors/foundations.",
        "contours": "Production grading needs contour output with traceable interval/source.",
    }
    for field, why in detail_fields.items():
        if not grading.get(field):
            gaps.append(_production_gap("grading_detail", field, why, f"Generate {field.replace('_', ' ')} from the finished surface."))
    if not _has_any(grading, ("contour_interval_ft", "contours")):
        warnings.append("Contour interval/output is incomplete.")
    if _safe_list(grading.get("retaining_walls")):
        if not grading.get("wall_tie_in_checks"):
            gaps.append(_production_gap("grading_detail", "wall_tie_in_checks", "Retaining walls need top/bottom tie-in checks.", "Run retaining wall tie-in validation."))
    return _system_result(
        status="ready" if not gaps else "needs_production_input",
        source=_safe_str(grading.get("source_quality") or grading.get("grading_source_quality"), "missing"),
        warnings=warnings,
        metrics={"production_gaps": gaps, "gap_count": len(gaps)},
    )


def check_cad_interop_truth(meta: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    gaps: List[Dict[str, Any]] = []
    export_audit = _safe_dict(meta.get("export_audit"))
    sheet_registry_raw = meta.get("sheet_registry")
    sheet_registry = _safe_dict(sheet_registry_raw)
    has_sheet_registry = bool(sheet_registry) or bool(_safe_list(sheet_registry_raw))
    cad = _safe_dict(meta.get("cad_interop") or meta.get("export_interop"))
    if not export_audit:
        gaps.append(_production_gap("cad_interop", "export_audit", "Export truth needs an audit before production deliverables.", "Finalize export metadata before artifact generation."))
    else:
        traceability = _safe_dict(export_audit.get("canonical_id_traceability"))
        if export_audit.get("export_blocked") is True or export_audit.get("production_export_ready") is False:
            gaps.append(
                _production_gap(
                    "cad_interop",
                    "export_readiness",
                    "Production deliverables must be generated from current, non-stale canonical engineering state.",
                    "Resolve export audit blockers and regenerate deliverables from the final canonical model.",
                )
            )
        if not traceability or traceability.get("ready") is not True:
            gaps.append(
                _production_gap(
                    "cad_interop",
                    "canonical_ids",
                    "Production exports need stable canonical IDs for every exported engineering object.",
                    "Attach canonical source IDs to export entities and final engineering summaries before export.",
                )
            )
    if not has_sheet_registry:
        gaps.append(_production_gap("cad_interop", "sheet_registry", "Production sheets need a sheet registry matching final canonical state.", "Finalize sheet registry before export."))
    interop_ready = (
        cad.get("civil3d") is True
        or cad.get("landxml") is True
        or cad.get("dwg") is True
        or _safe_str(cad.get("contract_status")) == "production_interop_ready"
    )
    if not interop_ready:
        gaps.append(
            _production_gap(
                "cad_interop",
                "civil3d_landxml",
                "Production civil workflows need Civil 3D/LandXML/DWG-compatible surfaces, profiles, and pipe networks.",
                "Add Civil 3D/LandXML export contracts for surfaces, alignments, profiles, and pipe networks.",
            )
        )
    if not cad:
        warnings.append("DXF is available, but Civil 3D/LandXML interoperability metadata is not attached.")
    return _system_result(
        status="ready" if not gaps else "needs_production_input",
        source=_safe_str(cad.get("source"), "dxf_concept_export"),
        warnings=warnings,
        metrics={
            "production_gaps": gaps,
            "gap_count": len(gaps),
            "has_export_audit": bool(export_audit),
            "has_sheet_registry": has_sheet_registry,
            "production_export_ready": export_audit.get("production_export_ready") if export_audit else False,
        },
    )


def check_optimization_truth(meta: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    gaps: List[Dict[str, Any]] = []
    optimization = _safe_dict(meta.get("optimization_summary"))
    if not optimization:
        gaps.append(_production_gap("optimization", "optimization_summary", "Production design should compare buildable alternatives, not only one generated option.", "Run multi-option optimization after core systems are ready."))
    else:
        if not _safe_dict(optimization.get("component_scores")):
            gaps.append(_production_gap("optimization", "component_scores", "Optimization needs scored tradeoffs across grading, drainage, utilities, parking, and constructability.", "Compute component scores for alternatives."))
        alternatives = _safe_list(optimization.get("alternatives"))
        comparison = _safe_dict(optimization.get("comparison_summary"))
        committed_alternatives = [
            item for item in alternatives
            if _safe_dict(item).get("geometry_committed", True) is not False
        ]
        if not (comparison or alternatives):
            gaps.append(_production_gap("optimization", "alternatives", "Production design needs a best option and runner-up/tradeoff explanation.", "Generate and compare design alternatives."))
        elif _safe_str(comparison.get("comparison_mode")) == "baseline_plus_uncommitted_recommendations" or len(committed_alternatives) < 2:
            gaps.append(_production_gap("optimization", "committed_alternatives", "Optimization recommendations are not accepted alternative geometry yet.", "Run and accept at least two buildable alternatives before production optimization signoff."))
        if not optimization.get("recommendations"):
            warnings.append("Optimization has no recommendations.")
    return _system_result(
        status="ready" if not gaps else "needs_production_input",
        source=_safe_str(optimization.get("source"), "planner_optimization_summary" if optimization else "missing"),
        warnings=warnings,
        metrics={"production_gaps": gaps, "gap_count": len(gaps), "overall_score": _safe_float(optimization.get("overall_score"), 0.0)},
    )


def check_grading_truth(grading: Dict[str, Any], standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    source = (
        _safe_str(grading.get("source_quality"))
        or _safe_str(grading.get("grading_source_quality"))
        or _safe_str(_safe_dict(grading.get("existing_surface")).get("source_quality"))
        or "missing"
    )
    low_points = _safe_list(grading.get("low_points"))
    high_points = _safe_list(grading.get("high_points"))
    slope_summary = _safe_dict(grading.get("slope_summary")) or _safe_dict(grading.get("surface_controls"))
    if not grading:
        missing.append(_missing("grading", "grading", "Drainage and earthwork need an existing/proposed surface.", "Run Detect Grading or upload survey/terrain."))
    if not low_points:
        missing.append(_missing("grading", "low_points", "Drainage needs low points to route flow.", "Generate or import a surface with low-point analysis."))
    if not high_points:
        warnings.append("No high points were reported; grading review is less complete.")
    if not slope_summary:
        missing.append(_missing("grading", "slope_summary", "Civil checks need slope direction and surface controls.", "Run grading analysis from terrain or survey."))
    if source in {"assumed", "fallback", "synthetic"}:
        warnings.append(f"Grading source is {source}; do not treat it as survey.")
    slope_value = _first_number(
        _safe_dict(grading.get("slope_summary")).get("average_slope"),
        _safe_dict(grading.get("surface_controls")).get("average_slope"),
        grading.get("average_slope"),
        default=0.0,
    )
    if slope_value > 0.0 and slope_value < standards.min_site_slope:
        warnings.append("Average surface slope is below concept minimum; drainage may pond without local grading controls.")
    if slope_value > standards.max_road_grade:
        warnings.append("Average site slope exceeds concept road-grade limit; road/pad tie-ins need detailed grading.")
    earthwork = _safe_dict(grading.get("earthwork"))
    if earthwork and not any(key in earthwork for key in ("cut_cf", "fill_cf", "net_cf")):
        warnings.append("Earthwork exists but cut/fill/net quantities are incomplete.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={
            "low_point_count": len(low_points),
            "high_point_count": len(high_points),
            "average_slope": round(slope_value, 6),
            "cut_cf": _safe_float(earthwork.get("cut_cf"), 0.0),
            "fill_cf": _safe_float(earthwork.get("fill_cf"), 0.0),
            "net_cf": _safe_float(earthwork.get("net_cf"), 0.0),
        },
    )


def check_drainage_truth(drainage: Dict[str, Any], standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    structures = _safe_list(drainage.get("structures"))
    basins = _safe_list(drainage.get("basins"))
    low_points = _safe_list(drainage.get("low_points"))
    flow_paths = _safe_list(drainage.get("flow_paths"))
    surface_guidance = _safe_dict(drainage.get("surface_guidance"))
    source = _safe_str(surface_guidance.get("surface_source")) or _safe_str(drainage.get("surface_source")) or _safe_str(drainage.get("source")) or "missing"
    if not drainage or not bool(drainage.get("success", bool(structures or basins))):
        missing.append(_missing("drainage", "success", "Storm and grading coordination need a valid drainage network.", "Run drainage after grading and basin/outfall placement."))
    if not basins and not _truthy_mapping(_safe_dict(drainage.get("coordination")).get("preferred_outfall")):
        missing.append(_missing("drainage", "basin_or_outfall", "Storm pipes need a detention basin or outfall target.", "Add or identify a basin/outfall."))
    if not low_points:
        missing.append(_missing("drainage", "low_points", "Drainage routing needs surface low points.", "Run terrain-based grading first."))
    if not flow_paths:
        missing.append(_missing("drainage", "flow_paths", "Drainage needs flow paths to connect inlets to basins/outfalls.", "Run drainage on the current surface."))
    if not (source and source != "missing"):
        missing.append(_missing("drainage", "surface_source", "Drainage needs to state whether it used survey, terrain, or assumptions.", "Run drainage from the canonical grading surface."))
    stats = _safe_dict(drainage.get("stats"))
    if not any(_has_number(stats.get(key)) for key in ("total_basin_runoff_cfs", "total_estimated_inlet_flow_cfs", "total_contributing_area_sf")):
        warnings.append("Drainage runoff/tributary demand metrics are incomplete.")
    for basin in basins:
        detention = _safe_dict(_safe_dict(basin).get("detention_design"))
        if detention:
            provided = _safe_float(detention.get("provided_storage_cf"), 0.0)
            required = _safe_float(detention.get("required_storage_cf"), 0.0)
            if required > 0.0 and provided < required:
                missing.append(_missing("drainage", "detention_storage", "Detention basin storage is below required concept storage.", "Resize basin or revise release/outlet assumptions."))
            drawdown = _safe_float(detention.get("drawdown_hours"), 0.0)
            if drawdown > standards.max_detention_drawdown_hours:
                warnings.append("Detention drawdown exceeds concept maximum; outlet design needs review.")
    issue_codes = {_safe_str(item.get("code")) for item in _safe_list(drainage.get("issues")) if isinstance(item, dict)}
    if "DRAINAGE_BLOCKED_BY_GRADING" in issue_codes:
        warnings.append("Drainage is blocked by grading and needs a spatial grading fix before final storm design.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={
            "structure_count": len(structures),
            "basin_count": len(basins),
            "low_point_count": len(low_points),
            "flow_path_count": len(flow_paths),
            "total_contributing_area_sf": _safe_float(stats.get("total_contributing_area_sf"), 0.0),
            "total_estimated_inlet_flow_cfs": _safe_float(stats.get("total_estimated_inlet_flow_cfs"), 0.0),
            "total_basin_runoff_cfs": _safe_float(stats.get("total_basin_runoff_cfs"), 0.0),
        },
    )


def check_storm_truth(storm: Dict[str, Any], standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    segments = _safe_list(storm.get("segments"))
    source = _safe_str(storm.get("hydraulic_source")) or _safe_str(storm.get("source")) or "missing"
    if not storm or not bool(storm.get("success", bool(segments))):
        missing.append(_missing("storm_pipes", "success", "Storm design needs a valid pipe network.", "Run storm after drainage target selection."))
    if not (_safe_str(storm.get("selected_outfall")) or _safe_str(storm.get("target_outfall_name")) or _truthy_mapping(storm.get("target_outfall"))):
        missing.append(_missing("storm_pipes", "selected_outfall", "Storm pipes need the drainage-selected outfall/basin.", "Confirm drainage outfall and rerun storm."))
    for field in ("total_system_flow_cfs", "total_system_capacity_cfs", "controlling_segment", "max_capacity_ratio"):
        if field not in storm:
            missing.append(_missing("storm_pipes", field, f"Storm hydraulic truth requires {field}.", "Run storm hydraulic sizing/checking."))
    max_capacity_ratio = _safe_float(storm.get("max_capacity_ratio"), 0.0)
    if max_capacity_ratio > standards.max_pipe_capacity_ratio:
        missing.append(_missing("storm_pipes", "max_capacity_ratio", "Storm pipe utilization exceeds concept capacity threshold.", "Upsize controlling pipe or revise catchments/outfall."))
    incomplete_segments: List[Dict[str, Any]] = []
    for segment in segments:
        rec = _safe_dict(segment)
        missing_fields = [
            field
            for field in ("length_ft", "slope", "capacity_cfs", "flow_cfs", "capacity_ratio")
            if not _has_number(rec.get(field))
        ]
        if missing_fields:
            incomplete_segments.append({"segment": _safe_str(rec.get("pipe") or rec.get("name"), "unnamed"), "missing_fields": missing_fields})
        ratio = _safe_float(rec.get("capacity_ratio"), 0.0)
        if ratio > standards.max_pipe_capacity_ratio:
            missing.append(_missing("storm_pipes", f"segment.{_safe_str(rec.get('pipe') or rec.get('name'), 'unnamed')}.capacity_ratio", "Storm segment exceeds concept capacity utilization.", "Upsize pipe or reduce tributary demand."))
    graph = _safe_dict(storm.get("graph_validation"))
    hydraulics = _safe_dict(storm.get("hydraulic_validation"))
    if segments and not bool(graph.get("valid", False)):
        missing.append(_missing("storm_pipes", "graph_validation", "Storm graph must be connected and directionally valid.", "Repair storm graph connectivity."))
    if segments and not bool(hydraulics.get("valid", False)):
        missing.append(_missing("storm_pipes", "hydraulic_validation", "Storm pipe capacities and slopes must be checked.", "Run hydraulic validation."))
    missing_segments = _safe_list(storm.get("missing_data_segments"))
    if incomplete_segments and not missing_segments:
        missing_segments = incomplete_segments
    if missing_segments:
        warnings.append("Storm has segments with missing hydraulic fields.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={
            "segment_count": len(segments),
            "missing_data_segment_count": len(missing_segments),
            "max_capacity_ratio": max_capacity_ratio,
            "total_system_flow_cfs": _safe_float(storm.get("total_system_flow_cfs"), 0.0),
            "total_system_capacity_cfs": _safe_float(storm.get("total_system_capacity_cfs"), 0.0),
        },
    )


def check_sanitary_truth(sanitary: Dict[str, Any], standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    segments = _safe_list(sanitary.get("segments"))
    manholes = _safe_list(sanitary.get("manholes"))
    source = _safe_str(sanitary.get("source")) or "missing"
    if not sanitary or not bool(sanitary.get("success", bool(segments or manholes))):
        missing.append(_missing("sanitary", "success", "Sanitary design needs a valid service network.", "Run sanitary design for buildings requiring service."))
    if not segments:
        missing.append(_missing("sanitary", "segments", "Sanitary design needs main/service segments.", "Generate sanitary routes."))
    if not manholes:
        missing.append(_missing("sanitary", "manholes", "Sanitary graph needs manholes for constructible service routing.", "Generate sanitary manholes."))
    graph = _safe_dict(sanitary.get("graph_validation"))
    network = _safe_dict(sanitary.get("network_validation"))
    if segments and not bool(graph.get("valid", False)):
        missing.append(_missing("sanitary", "graph_validation", "Sanitary graph must be connected and directionally valid.", "Repair sanitary graph connectivity."))
    if segments and not bool(network.get("valid", False)):
        missing.append(_missing("sanitary", "network_validation", "Sanitary must prove building services connect to the network.", "Run sanitary service validation."))
    if _safe_list(sanitary.get("missing_service_buildings")):
        missing.append(_missing("sanitary", "missing_service_buildings", "All served buildings need sanitary service coverage.", "Add missing services or mark buildings unserved."))
    if _safe_list(sanitary.get("missing_data_segments")):
        warnings.append("Sanitary has segments with missing design fields.")
    max_capacity_ratio = _safe_float(sanitary.get("max_capacity_ratio"), 0.0)
    if max_capacity_ratio > standards.max_sanitary_capacity_ratio:
        missing.append(_missing("sanitary", "max_capacity_ratio", "Sanitary utilization exceeds concept design threshold.", "Upsize sanitary pipe or split contributing service area."))
    service_count = _safe_int(sanitary.get("service_count"), 0)
    if service_count <= 0 and segments:
        missing.append(_missing("sanitary", "service_count", "Sanitary readiness needs service laterals/building coverage count.", "Run sanitary service generation/validation."))
    slope_violations = _safe_list(sanitary.get("slope_violations"))
    if slope_violations:
        missing.append(_missing("sanitary", "slope_violations", "Sanitary gravity pipes must satisfy minimum slope.", "Adjust inverts or reroute sanitary runs."))
    longest_spacing = 0.0
    for segment in segments:
        path = segment_path(_safe_dict(segment))
        if path:
            longest_spacing = max(longest_spacing, max_spacing_along_path(path, manholes))
    if longest_spacing > standards.max_sanitary_manhole_spacing_ft:
        warnings.append("Sanitary manhole spacing exceeds concept maximum; add intermediate manholes.")
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={
            "segment_count": len(segments),
            "manhole_count": len(manholes),
            "route_count": _safe_int(sanitary.get("route_count"), len(segments)),
            "service_count": service_count,
            "max_capacity_ratio": max_capacity_ratio,
            "max_manhole_spacing_ft": round(longest_spacing, 3),
        },
    )


def check_utility_truth(utilities: Dict[str, Any], standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    hooks = _safe_dict(utilities.get("conflict_hooks"))
    segments = _safe_list(utilities.get("segments")) or _safe_list(hooks.get("utility_segments"))
    source = _safe_str(utilities.get("source")) or "missing"
    if not utilities:
        missing.append(_missing("utilities", "utility_summary", "Coordination needs utility paths and conflicts.", "Run utility network coordination."))
    if utilities and not segments:
        missing.append(_missing("utilities", "segments", "Utility coordination needs utility segments.", "Generate utility segments."))
    coordination = _safe_dict(utilities.get("coordination"))
    if _safe_int(coordination.get("unresolved_conflict_count"), 0) > 0:
        warnings.append("Utilities still have unresolved conflicts.")
    if _safe_float(utilities.get("min_cover_ft"), 999.0) < standards.min_utility_cover_ft:
        warnings.append("Utility cover is below concept minimum.")
    shallow_segments = [
        _safe_str(_safe_dict(segment).get("name"), f"utility_{idx}")
        for idx, segment in enumerate(segments, start=1)
        if _has_number(_safe_dict(segment).get("cover_ft"))
        and _safe_float(_safe_dict(segment).get("cover_ft"), 0.0) < standards.min_utility_cover_ft
    ]
    if shallow_segments:
        missing.append(_missing("utilities", "cover_ft", "One or more utilities are below concept minimum cover.", "Lower shallow utilities or revise finished grade."))
    separation_warnings: List[Dict[str, Any]] = []
    for index, left in enumerate(segments):
        left_rec = _safe_dict(left)
        left_system = _safe_str(left_rec.get("system") or left_rec.get("utility_type") or left_rec.get("type"), "utility")
        left_path = segment_path(left_rec)
        if not left_path:
            continue
        for right in segments[index + 1 :]:
            right_rec = _safe_dict(right)
            right_system = _safe_str(right_rec.get("system") or right_rec.get("utility_type") or right_rec.get("type"), "utility")
            if left_system == right_system:
                continue
            right_path = segment_path(right_rec)
            if not right_path:
                continue
            rule = utility_pairing_rule(left_system, right_system, standards)
            clearance = path_clearance(left_path, right_path)
            if clearance < _safe_float(rule.get("horizontal_separation_ft"), 0.0):
                separation_warnings.append(
                    {
                        "left": _safe_str(left_rec.get("name"), left_system),
                        "right": _safe_str(right_rec.get("name"), right_system),
                        "clearance_ft": round(clearance, 3),
                        "required_ft": rule.get("horizontal_separation_ft"),
                        "priority": rule.get("priority"),
                    }
                )
    if separation_warnings:
        warnings.append("Utility horizontal separation needs review for one or more pairings.")
    velocity_failures = [
        _safe_str(_safe_dict(check).get("segment"), f"water_velocity_{index}")
        for index, check in enumerate(_safe_list(utilities.get("velocity_checks")), start=1)
        if _has_number(_safe_dict(check).get("velocity_fps"))
        and _safe_float(_safe_dict(check).get("velocity_fps"), 0.0) > standards.max_water_velocity_fps
    ]
    if velocity_failures:
        missing.append(_missing("utilities", "water_velocity", "Water velocity exceeds the active standards threshold.", "Upsize water pipe or revise demand allocation."))
    pressure = _safe_dict(utilities.get("pressure_validation"))
    if pressure and pressure.get("valid") is False:
        missing.append(_missing("utilities", "water_pressure", "Water pressure validation failed or is missing required inputs.", "Provide source pressure and solve pressure graph."))
    elif pressure and _has_number(pressure.get("min_pressure_psi")) and _safe_float(pressure.get("min_pressure_psi"), 0.0) < standards.min_water_residual_pressure_psi:
        missing.append(_missing("utilities", "water_pressure", "Water residual pressure is below the active standards threshold.", "Upsize, loop, boost, or revise water source assumptions."))
    hydrants = _safe_dict(utilities.get("hydrant_spacing_validation"))
    if hydrants and _has_number(hydrants.get("max_spacing_ft")) and _safe_float(hydrants.get("max_spacing_ft"), 0.0) > standards.max_hydrant_spacing_ft:
        missing.append(_missing("utilities", "hydrant_spacing", "Hydrant spacing exceeds the active standards threshold.", "Add hydrants or revise water main layout."))
    fire = _safe_dict(utilities.get("fire_flow_validation"))
    if fire and fire.get("valid") is False:
        missing.append(_missing("utilities", "fire_flow", "Fire-flow validation failed or is missing required inputs.", "Provide required/available fire flow and residual pressure evidence."))
    elif fire and standards.min_fire_flow_gpm > 0.0 and _safe_float(fire.get("available_fire_flow_gpm"), 0.0) < standards.min_fire_flow_gpm:
        missing.append(_missing("utilities", "fire_flow", "Available fire flow is below the active standards threshold.", "Revise water source, loop, or pipe sizing."))
    return _system_result(
        status="ready" if not missing else "missing",
        source=source,
        missing=missing,
        warnings=warnings,
        metrics={
            "segment_count": len(segments),
            "unresolved_conflict_count": _safe_int(coordination.get("unresolved_conflict_count"), 0),
            "shallow_segment_count": len(shallow_segments),
            "separation_warning_count": len(separation_warnings),
            "separation_warnings": separation_warnings[:12],
            "water_velocity_failure_count": len(velocity_failures),
        },
    )


def check_coordination_truth(coordination: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    unresolved_count = _safe_int(coordination.get("unresolved_count"), _safe_int(coordination.get("unresolved_conflict_count"), 0))
    detected_count = _safe_int(coordination.get("detected_conflicts"), 0)
    if unresolved_count > 0:
        missing.append(_missing("coordination", "unresolved_conflicts", "Open conflicts mean final systems are not coordinated.", "Resolve or explicitly document unresolved conflicts."))
    if _safe_list(coordination.get("assumption_resolutions")):
        warnings.append("Coordination used assumption-based resolutions.")
    status = "ready"
    if missing:
        status = "missing"
    elif not coordination and detected_count <= 0:
        status = "not_run"
        warnings.append("Coordination summary was not present.")
    return _system_result(
        status=status,
        source=_safe_str(coordination.get("source"), "coordination"),
        missing=missing,
        warnings=warnings,
        metrics={"detected_conflict_count": detected_count, "unresolved_conflict_count": unresolved_count},
    )


def check_site_truth(plan_or_meta: Dict[str, Any]) -> Dict[str, Any]:
    plan = plan_or_meta if "actions" in plan_or_meta else {}
    meta = _safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else _safe_dict(plan_or_meta)
    actions = _safe_list(plan.get("actions"))
    missing: List[Dict[str, Any]] = []
    warnings: List[str] = []
    site_rects = [rect_from_action(_safe_dict(action)) for action in actions if classify_action_system(_safe_dict(action)) == "site"]
    building_rects = [rect_from_action(_safe_dict(action)) for action in actions if classify_action_system(_safe_dict(action)) == "building"]
    site_area = max([rect_area(rect) for rect in site_rects if rect] or [0.0])
    if site_area <= 0.0:
        lot = _safe_dict(meta.get("lot") or meta.get("site_boundary"))
        site_area = _safe_float(lot.get("area_sf"), 0.0) or (_safe_float(lot.get("w"), 0.0) * _safe_float(lot.get("h"), 0.0))
    if site_area <= 0.0:
        missing.append(_missing("site", "site_boundary", "All civil systems need a real site boundary.", "Apply/Lock Site from map viewport or import a survey boundary."))
    if not building_rects and actions:
        warnings.append("No building/pad footprint was found in canonical actions.")
    return _system_result(
        status="ready" if not missing else "missing",
        source="canonical_actions" if actions else "meta",
        missing=missing,
        warnings=warnings,
        metrics={"site_area_sf": round(site_area, 3), "building_count": len([rect for rect in building_rects if rect])},
    )


def readiness_score(systems: Dict[str, Dict[str, Any]], warnings: Sequence[Dict[str, Any]]) -> float:
    weights = {
        "site": 1.0,
        "grading": 1.25,
        "drainage": 1.25,
        "storm_pipes": 1.25,
        "sanitary": 1.0,
        "utilities": 1.0,
        "coordination": 1.25,
    }
    total_weight = sum(weights.values())
    score = 0.0
    for system, weight in weights.items():
        status = _safe_str(_safe_dict(systems.get(system)).get("status"))
        if status == "ready":
            score += weight
        elif status in {"not_run", "missing"}:
            score += 0.0
        else:
            score += weight * 0.4
    penalty = min(len(warnings) * 0.02, 0.18)
    return round(max(0.0, min(1.0, score / max(total_weight, 1e-9) - penalty)) * 100.0, 1)


def civil_design_readiness(plan_or_meta: Dict[str, Any], *, standards: CivilDesignStandards = DEFAULT_STANDARDS) -> Dict[str, Any]:
    meta = _safe_dict(plan_or_meta.get("meta")) if "meta" in plan_or_meta else _safe_dict(plan_or_meta)
    active_standards = standards_from_meta(meta, standards)
    systems = {
        "site": check_site_truth(plan_or_meta),
        "standards": check_standards_truth(meta),
        "existing_conditions": check_existing_conditions_truth(meta),
        "grading": check_grading_truth(_safe_dict(meta.get("grading") or meta.get("grading_summary")), active_standards),
        "grading_detail": check_grading_detail_truth(meta),
        "drainage": check_drainage_truth(_safe_dict(meta.get("drainage") or meta.get("drainage_canonical")), active_standards),
        "storm_pipes": check_storm_truth(_safe_dict(meta.get("storm_pipes") or meta.get("storm_pipe_summary")), active_standards),
        "hydraulic_depth": check_hydraulic_depth_truth(meta),
        "sanitary": check_sanitary_truth(_safe_dict(meta.get("sanitary") or meta.get("sanitary_summary")), active_standards),
        "utilities": check_utility_truth(_safe_dict(meta.get("utilities") or meta.get("utility_summary")), active_standards),
        "coordination": check_coordination_truth(_safe_dict(meta.get("coordination") or meta.get("coordination_summary"))),
        "cad_interop": check_cad_interop_truth(meta),
        "optimization": check_optimization_truth(meta),
    }
    missing_requirements: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    production_blockers: List[Dict[str, Any]] = []
    truth_sources: Dict[str, str] = {}
    for system, result in systems.items():
        truth_sources[system] = _safe_str(result.get("source"), "missing")
        missing_requirements.extend(_safe_list(result.get("missing")))
        production_blockers.extend(_safe_list(_safe_dict(result.get("metrics")).get("production_gaps")))
        for warning in _safe_list(result.get("warnings")):
            warnings.append({"system": system, "message": _safe_str(warning)})
    critical_blockers = [
        item
        for item in missing_requirements
        if item.get("system") in {"site", "grading", "drainage", "storm_pipes", "sanitary", "coordination"}
    ]
    ready_systems = [system for system, result in systems.items() if result.get("status") == "ready"]
    success = not critical_blockers
    status = "ready" if success else "blocked"
    if success and warnings:
        status = "needs_engineering_review"
    score = readiness_score(systems, warnings)
    production_ready = success and not production_blockers and score >= 85.0
    return {
        "success": success,
        "status": status,
        "score": score,
        "real_world_readiness": (
            "production_review_candidate"
            if production_ready
            else "concept_design_ready"
            if score >= 65.0
            else "engineering_inputs_incomplete"
        ),
        "production_ready": production_ready,
        "production_blockers": production_blockers,
        "standards_version": active_standards.version,
        "standards": active_standards.to_dict(),
        "systems": systems,
        "ready_systems": ready_systems,
        "missing_requirements": missing_requirements,
        "critical_blockers": critical_blockers,
        "warnings": warnings,
        "truth_sources": truth_sources,
        "can_assist_if_enabled": bool(missing_requirements),
        "message": (
            "Canonical engineering state is ready for coordinated review."
            if success
            else "Civora needs additional canonical engineering inputs before this is final-design ready."
        ),
        "next_actions": [item.get("suggested_next_action") for item in missing_requirements[:8] if item.get("suggested_next_action")],
    }


__all__ = [
    "CivilDesignStandards",
    "DEFAULT_STANDARDS",
    "civil_design_readiness",
    "standards_from_meta",
    "check_coordination_truth",
    "check_cad_interop_truth",
    "check_drainage_truth",
    "check_existing_conditions_truth",
    "check_grading_truth",
    "check_grading_detail_truth",
    "check_hydraulic_depth_truth",
    "check_optimization_truth",
    "check_sanitary_truth",
    "check_site_truth",
    "check_standards_truth",
    "check_storm_truth",
    "check_utility_truth",
    "classify_action_system",
    "coerce_path",
    "coerce_point",
    "path_bbox",
    "path_clearance",
    "path_length",
    "readiness_score",
    "rect_from_action",
    "segment_path",
    "sample_path",
    "station_point",
    "utility_pairing_rule",
]
