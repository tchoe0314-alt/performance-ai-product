from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


LINE_KINDS = {"road", "driveway", "sidewalk", "path"}


def normalize_detection_candidates(
    detections: Iterable[Dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    provider: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Clean detector geometry and reject shapes that are not safe review candidates.

    The strict policy is intentionally limited to the local heuristic detector. A
    promoted learned model or external provider keeps its own class confidence,
    while still receiving finite-coordinate, closure, simplification, and
    self-intersection checks.
    """

    accepted: List[Dict[str, Any]] = []
    rejected_reasons: Counter[str] = Counter()
    cleanup_actions: Counter[str] = Counter()
    provider_name = str(provider or "unknown_detector")
    strict = "heuristic" in provider_name.lower()
    input_rows = [deepcopy(item) for item in detections if isinstance(item, dict)]

    for detection in input_rows:
        normalized, reasons, actions = _normalize_detection(
            detection,
            image_width=image_width,
            image_height=image_height,
            strict=strict,
        )
        cleanup_actions.update(actions)
        if normalized is None:
            rejected_reasons.update(reasons or ["invalid_or_missing_geometry"])
            continue
        accepted.append(normalized)

    return accepted, {
        "version": "imagery_geometry_quality_v1",
        "provider": provider_name,
        "policy": "conservative_heuristic" if strict else "provider_geometry_validation",
        "input_count": len(input_rows),
        "accepted_count": len(accepted),
        "rejected_count": len(input_rows) - len(accepted),
        "rejected_by_reason": dict(sorted(rejected_reasons.items())),
        "cleanup_actions": dict(sorted(cleanup_actions.items())),
        "review_edit_supported": True,
        "truth_label": (
            "Geometry quality gates remove unusable visual guesses before review. "
            "Accepted detections remain editable visual candidates, not survey or engineering evidence."
        ),
    }


def _normalize_detection(
    detection: Dict[str, Any],
    *,
    image_width: int,
    image_height: int,
    strict: bool,
) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    rec = deepcopy(detection)
    kind = str(rec.get("kind") or rec.get("feature_type") or "").strip().lower()
    confidence = _finite_float(rec.get("confidence"), 0.35)
    properties = deepcopy(rec.get("properties")) if isinstance(rec.get("properties"), dict) else {}
    actions: List[str] = []

    # A provider can supply authoritative map-space geometry directly. Do not
    # clamp longitude/latitude coordinates to image dimensions.
    if rec.get("geo_geometry") and not rec.get("pixel_geometry") and not rec.get("geometry"):
        properties["geometry_quality_v1"] = {
            "status": "provider_map_geometry",
            "quality_score": round(max(0.0, min(1.0, confidence)), 3),
            "review_edit_supported": True,
        }
        rec["properties"] = properties
        return rec, [], actions

    geometry = _geometry_from_detection(rec, kind=kind)
    geometry_type = str(geometry.get("type") or "")
    if geometry_type == "Point":
        point = _normalize_point(geometry.get("coordinates"), image_width, image_height)
        if point is None:
            return None, ["invalid_point_geometry"], actions
        rec["geometry"] = {"type": "Point", "coordinates": point}
        rec["pixel_geometry"] = rec["geometry"]
        rec.pop("geo_geometry", None)
        rec["bbox"] = [point[0], point[1], 0.0, 0.0]
        properties["geometry_quality_v1"] = {
            "status": "usable_review_candidate",
            "quality_score": round(max(0.2, min(0.92, confidence)), 3),
            "geometry_type": "Point",
            "review_edit_supported": True,
        }
        rec["properties"] = properties
        return rec, [], actions

    if geometry_type == "Polygon":
        ring = _polygon_ring(geometry)
        points, point_actions = _normalize_points(ring, image_width, image_height)
        actions.extend(point_actions)
        points = _remove_consecutive_duplicates(points)
        if len(points) >= 2 and points[0] == points[-1]:
            points = points[:-1]
        if len(set(points)) < 3:
            return None, ["polygon_has_fewer_than_three_unique_points"], actions
        epsilon = max(0.75, _bbox_diagonal(points) * (0.008 if kind == "building" else 0.012))
        simplified = _simplify_closed_ring(points, epsilon=epsilon)
        if len(simplified) < len(points):
            actions.append("simplified_noisy_outline")
        points = simplified
        if _ring_self_intersects(points):
            repaired = _convex_hull(points)
            if len(repaired) < 3:
                return None, ["self_intersecting_polygon"], actions
            original_area = abs(_polygon_area(points))
            repaired_area = abs(_polygon_area(repaired))
            repair_ratio = original_area / max(repaired_area, 1e-9)
            if strict or repair_ratio < 0.65:
                return None, ["self_intersecting_polygon"], actions
            points = repaired
            actions.append("repaired_self_intersection_with_hull")
        if points[0] != points[-1]:
            points.append(points[0])
            actions.append("closed_polygon")

        metrics = _polygon_metrics(points, image_width=image_width, image_height=image_height)
        reasons = _polygon_rejection_reasons(
            kind=kind,
            metrics=metrics,
            confidence=confidence,
            strict=strict,
            source_properties=properties,
        )
        score = _polygon_quality_score(metrics, confidence=confidence, strict=strict)
        if score < (0.55 if strict and kind == "building" else 0.38):
            reasons.append("geometry_quality_below_threshold")
        reasons = sorted(set(reasons))
        if reasons:
            return None, reasons, actions

        cleaned_geometry: Dict[str, Any]
        if kind in LINE_KINDS:
            centerline = _polygon_centerline(points)
            if centerline is None:
                return None, ["road_geometry_has_no_usable_centerline"], actions
            line_length = _line_length(centerline)
            minimum_length = max(8.0, min(image_width or 512, image_height or 512) * (0.08 if strict else 0.02))
            if line_length < minimum_length:
                return None, ["road_candidate_too_short"], actions
            cleaned_geometry = {"type": "LineString", "coordinates": centerline}
            properties["source_polygon_geometry"] = {"type": "Polygon", "coordinates": [points]}
            properties["corridor_width_px"] = round(metrics["area_px2"] / max(line_length, 1.0), 2)
            properties["geometry_fidelity"] = "derived_centerline_from_visual_region"
            actions.append("derived_road_centerline")
        else:
            cleaned_geometry = {"type": "Polygon", "coordinates": [points]}
            properties.setdefault("geometry_fidelity", "cleaned_visual_outline")

        rec["geometry"] = cleaned_geometry
        rec["pixel_geometry"] = cleaned_geometry
        rec.pop("geo_geometry", None)
        rec["bbox"] = _bbox_list_from_points(points)
        properties["geometry_quality_v1"] = {
            **metrics,
            "status": "usable_review_candidate",
            "quality_score": round(score, 3),
            "cleanup_actions": sorted(set(actions)),
            "review_edit_supported": True,
        }
        properties["candidate_quality_score"] = round(score, 3)
        properties["review_edit_supported"] = True
        rec["properties"] = properties
        return rec, [], actions

    if geometry_type == "LineString":
        raw_points = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []
        points, point_actions = _normalize_points(raw_points, image_width, image_height)
        actions.extend(point_actions)
        points = _remove_consecutive_duplicates(points)
        if len(points) < 2:
            return None, ["line_has_fewer_than_two_points"], actions
        epsilon = max(0.75, _bbox_diagonal(points) * 0.006)
        simplified = _rdp(points, epsilon)
        if len(simplified) < len(points):
            actions.append("simplified_noisy_centerline")
        length = _line_length(simplified)
        minimum_length = max(6.0, min(image_width or 512, image_height or 512) * (0.08 if strict and kind in LINE_KINDS else 0.015))
        if length < minimum_length:
            return None, ["line_candidate_too_short"], actions
        if strict and kind not in LINE_KINDS:
            return None, ["unsupported_heuristic_line_class"], actions
        bbox = _bbox_list_from_points(simplified)
        score = min(0.9, max(0.35, 0.45 + min(length / max(min(image_width or 512, image_height or 512), 1), 1.0) * 0.25 + confidence * 0.2))
        cleaned_geometry = {"type": "LineString", "coordinates": simplified}
        rec["geometry"] = cleaned_geometry
        rec["pixel_geometry"] = cleaned_geometry
        rec.pop("geo_geometry", None)
        rec["bbox"] = bbox
        properties.setdefault("geometry_fidelity", "cleaned_visual_centerline")
        properties["geometry_quality_v1"] = {
            "status": "usable_review_candidate",
            "quality_score": round(score, 3),
            "geometry_type": "LineString",
            "length_px": round(length, 2),
            "cleanup_actions": sorted(set(actions)),
            "review_edit_supported": True,
        }
        properties["candidate_quality_score"] = round(score, 3)
        properties["review_edit_supported"] = True
        rec["properties"] = properties
        return rec, [], actions

    return None, ["unsupported_or_missing_geometry"], actions


def _geometry_from_detection(detection: Dict[str, Any], *, kind: str) -> Dict[str, Any]:
    geometry = detection.get("pixel_geometry") or detection.get("geometry")
    if isinstance(geometry, dict) and geometry.get("type") == "Feature":
        geometry = geometry.get("geometry")
    if isinstance(geometry, dict) and geometry.get("type") and geometry.get("coordinates") not in (None, [], {}):
        return deepcopy(geometry)
    bbox = detection.get("bbox") or detection.get("bounds")
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return {}
    x = _finite_float(bbox[0], float("nan"))
    y = _finite_float(bbox[1], float("nan"))
    width = _finite_float(bbox[2], float("nan"))
    height = _finite_float(bbox[3], float("nan"))
    if not all(math.isfinite(value) for value in (x, y, width, height)) or width <= 0 or height <= 0:
        return {}
    if kind in LINE_KINDS:
        if width >= height:
            return {"type": "LineString", "coordinates": [[x, y + height / 2], [x + width, y + height / 2]]}
        return {"type": "LineString", "coordinates": [[x + width / 2, y], [x + width / 2, y + height]]}
    return {
        "type": "Polygon",
        "coordinates": [[[x, y], [x + width, y], [x + width, y + height], [x, y + height], [x, y]]],
    }


def _polygon_ring(geometry: Dict[str, Any]) -> List[Any]:
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        return []
    first = coordinates[0]
    return first if isinstance(first, list) else []


def _normalize_point(value: Any, image_width: int, image_height: int) -> Optional[List[float]]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    x = _finite_float(value[0], float("nan"))
    y = _finite_float(value[1], float("nan"))
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return [_clamp(x, 0.0, float(image_width)) if image_width else x, _clamp(y, 0.0, float(image_height)) if image_height else y]


def _normalize_points(values: Any, image_width: int, image_height: int) -> Tuple[List[Tuple[float, float]], List[str]]:
    points: List[Tuple[float, float]] = []
    actions: List[str] = []
    for value in values if isinstance(values, list) else []:
        point = _normalize_point(value, image_width, image_height)
        if point is None:
            actions.append("removed_non_finite_point")
            continue
        original_x = _finite_float(value[0], point[0])
        original_y = _finite_float(value[1], point[1])
        if point[0] != original_x or point[1] != original_y:
            actions.append("clamped_point_to_image")
        points.append((round(point[0], 3), round(point[1], 3)))
    return points, actions


def _remove_consecutive_duplicates(points: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    output: List[Tuple[float, float]] = []
    for point in points:
        if not output or point != output[-1]:
            output.append(point)
    return output


def _polygon_rejection_reasons(
    *,
    kind: str,
    metrics: Dict[str, Any],
    confidence: float,
    strict: bool,
    source_properties: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []
    area_ratio = float(metrics["area_ratio"])
    fill_ratio = float(metrics["fill_ratio"])
    aspect_ratio = float(metrics["aspect_ratio"])
    touches_frame = bool(metrics["touches_frame"])
    vertex_count = int(metrics["vertex_count"])

    if area_ratio <= 0:
        reasons.append("zero_area_polygon")
    if kind == "building":
        minimum_area = 0.00012 if strict else 0.00002
        maximum_area = 0.12 if strict else 0.48
        if area_ratio < minimum_area:
            reasons.append("building_candidate_too_small")
        if area_ratio > maximum_area:
            reasons.append("oversized_building_candidate")
        if strict and touches_frame:
            reasons.append("building_candidate_connected_to_image_border")
        if fill_ratio < (0.48 if strict else 0.2):
            reasons.append("building_outline_too_irregular")
        if aspect_ratio > (10.0 if strict else 18.0):
            reasons.append("building_outline_too_elongated")
        if strict and vertex_count > 20:
            reasons.append("building_outline_too_noisy")
        component = source_properties.get("component_shape_v1")
        if strict and isinstance(component, dict):
            component_fill = _finite_float(component.get("fill_ratio"), fill_ratio)
            component_border = component.get("touches_frame") is True
            component_aspect = _finite_float(component.get("aspect_ratio"), aspect_ratio)
            if component_fill < 0.36:
                reasons.append("building_component_too_fragmented")
            if component_border:
                reasons.append("building_component_connected_to_image_border")
            if component_aspect > 10.0:
                reasons.append("building_component_too_elongated")
    elif kind in LINE_KINDS:
        if area_ratio > (0.42 if strict else 0.7):
            reasons.append("road_region_oversized")
        component = source_properties.get("component_shape_v1")
        if strict and isinstance(component, dict):
            component_aspect = _finite_float(component.get("aspect_ratio"), 1.0)
            if component_aspect < 1.7 and area_ratio > 0.015:
                reasons.append("road_region_not_corridor_shaped")
    elif kind in {"parking", "basin", "pond", "pool"}:
        if area_ratio > (0.34 if strict else 0.65):
            reasons.append("oversized_area_candidate")
        if strict and touches_frame:
            reasons.append("area_candidate_connected_to_image_border")
    elif kind in {"open_space", "tree", "vegetation"}:
        if area_ratio > (0.35 if strict else 0.75):
            reasons.append("oversized_vegetation_candidate")
        if strict and touches_frame and area_ratio > 0.05:
            reasons.append("vegetation_candidate_connected_to_image_border")
    elif strict and area_ratio > 0.55:
        reasons.append("oversized_visual_region")

    if not strict and confidence < 0.02:
        reasons.append("provider_confidence_below_minimum")
    return reasons


def _polygon_quality_score(metrics: Dict[str, Any], *, confidence: float, strict: bool) -> float:
    area_ratio = float(metrics["area_ratio"])
    fill_ratio = float(metrics["fill_ratio"])
    touches_frame = bool(metrics["touches_frame"])
    vertex_count = int(metrics["vertex_count"])
    size_score = 1.0 if 0.0005 <= area_ratio <= 0.12 else max(0.0, 1.0 - abs(area_ratio - 0.06) / 0.4)
    vertex_score = 1.0 if vertex_count <= 10 else max(0.0, 1.0 - (vertex_count - 10) / 30)
    score = (
        0.12
        + 0.30 * min(max(fill_ratio, 0.0), 1.0)
        + 0.18 * (0.0 if touches_frame else 1.0)
        + 0.14 * size_score
        + 0.12 * vertex_score
        + 0.14 * min(max(confidence, 0.0), 1.0)
    )
    if not strict:
        score += 0.08
    return min(max(score, 0.0), 1.0)


def _polygon_metrics(points: Sequence[Tuple[float, float]], *, image_width: int, image_height: int) -> Dict[str, Any]:
    open_points = list(points[:-1] if points and points[0] == points[-1] else points)
    bbox = _bbox_list_from_points(open_points)
    area = abs(_polygon_area(open_points))
    bbox_area = max(bbox[2] * bbox[3], 1e-9)
    image_area = max(float(image_width * image_height), 1.0)
    min_x, min_y, width, height = bbox
    margin = max(1.0, min(image_width or 512, image_height or 512) * 0.002)
    touches_frame = bool(
        image_width
        and image_height
        and (
            min_x <= margin
            or min_y <= margin
            or min_x + width >= image_width - margin
            or min_y + height >= image_height - margin
        )
    )
    return {
        "geometry_type": "Polygon",
        "vertex_count": len(open_points),
        "area_px2": round(area, 2),
        "area_ratio": round(area / image_area, 6),
        "bbox_area_ratio": round(bbox_area / image_area, 6),
        "fill_ratio": round(area / bbox_area, 4),
        "aspect_ratio": round(max(width, height) / max(min(width, height), 1e-9), 3),
        "touches_frame": touches_frame,
    }


def _polygon_centerline(points: Sequence[Tuple[float, float]]) -> Optional[List[Tuple[float, float]]]:
    open_points = list(points[:-1] if points and points[0] == points[-1] else points)
    if len(open_points) < 3:
        return None
    center_x = sum(point[0] for point in open_points) / len(open_points)
    center_y = sum(point[1] for point in open_points) / len(open_points)
    xx = sum((point[0] - center_x) ** 2 for point in open_points) / len(open_points)
    yy = sum((point[1] - center_y) ** 2 for point in open_points) / len(open_points)
    xy = sum((point[0] - center_x) * (point[1] - center_y) for point in open_points) / len(open_points)
    angle = 0.5 * math.atan2(2 * xy, xx - yy)
    axis = (math.cos(angle), math.sin(angle))
    projections = [(point[0] - center_x) * axis[0] + (point[1] - center_y) * axis[1] for point in open_points]
    minimum = min(projections)
    maximum = max(projections)
    if maximum - minimum <= 1e-6:
        return None
    return [
        (round(center_x + minimum * axis[0], 3), round(center_y + minimum * axis[1], 3)),
        (round(center_x + maximum * axis[0], 3), round(center_y + maximum * axis[1], 3)),
    ]


def _simplify_closed_ring(points: Sequence[Tuple[float, float]], *, epsilon: float) -> List[Tuple[float, float]]:
    if len(points) <= 4:
        return list(points)
    start = min(range(len(points)), key=lambda index: (points[index][0], points[index][1]))
    rotated = list(points[start:]) + list(points[:start])
    farthest = max(range(1, len(rotated)), key=lambda index: _distance(rotated[0], rotated[index]))
    first_path = _rdp(rotated[: farthest + 1], epsilon)
    second_path = _rdp(rotated[farthest:] + [rotated[0]], epsilon)
    merged = first_path[:-1] + second_path[:-1]
    return _remove_consecutive_duplicates(merged) if len(set(merged)) >= 3 else list(points)


def _rdp(points: Sequence[Tuple[float, float]], epsilon: float) -> List[Tuple[float, float]]:
    if len(points) < 3:
        return list(points)
    start = points[0]
    end = points[-1]
    max_distance = 0.0
    max_index = 0
    for index in range(1, len(points) - 1):
        distance = _point_line_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            max_index = index
    if max_distance > epsilon:
        left = _rdp(points[: max_index + 1], epsilon)
        right = _rdp(points[max_index:], epsilon)
        return left[:-1] + right
    return [start, end]


def _point_line_distance(point: Tuple[float, float], start: Tuple[float, float], end: Tuple[float, float]) -> float:
    if start == end:
        return _distance(point, start)
    numerator = abs((end[1] - start[1]) * point[0] - (end[0] - start[0]) * point[1] + end[0] * start[1] - end[1] * start[0])
    denominator = math.hypot(end[1] - start[1], end[0] - start[0])
    return numerator / max(denominator, 1e-9)


def _ring_self_intersects(points: Sequence[Tuple[float, float]]) -> bool:
    count = len(points)
    if count < 4:
        return False
    for index in range(count):
        a1 = points[index]
        a2 = points[(index + 1) % count]
        for other in range(index + 1, count):
            if other in {index, (index + 1) % count} or (other + 1) % count in {index, (index + 1) % count}:
                continue
            b1 = points[other]
            b2 = points[(other + 1) % count]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _segments_intersect(
    a1: Tuple[float, float],
    a2: Tuple[float, float],
    b1: Tuple[float, float],
    b2: Tuple[float, float],
) -> bool:
    def orientation(p: Tuple[float, float], q: Tuple[float, float], r: Tuple[float, float]) -> float:
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    o1 = orientation(a1, a2, b1)
    o2 = orientation(a1, a2, b2)
    o3 = orientation(b1, b2, a1)
    o4 = orientation(b1, b2, a2)
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _convex_hull(points: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    unique = sorted(set(points))
    if len(unique) <= 3:
        return unique

    def cross(origin: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

    lower: List[Tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: List[Tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _polygon_area(points: Sequence[Tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    return sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    ) / 2.0


def _bbox_list_from_points(points: Sequence[Tuple[float, float]]) -> List[float]:
    if not points:
        return []
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    minimum_x = min(xs)
    minimum_y = min(ys)
    return [
        round(minimum_x, 3),
        round(minimum_y, 3),
        round(max(xs) - minimum_x, 3),
        round(max(ys) - minimum_y, 3),
    ]


def _bbox_diagonal(points: Sequence[Tuple[float, float]]) -> float:
    bbox = _bbox_list_from_points(points)
    return math.hypot(bbox[2], bbox[3]) if len(bbox) >= 4 else 0.0


def _line_length(points: Sequence[Tuple[float, float]]) -> float:
    return sum(_distance(points[index - 1], points[index]) for index in range(1, len(points)))


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _finite_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


__all__ = ["normalize_detection_candidates"]
