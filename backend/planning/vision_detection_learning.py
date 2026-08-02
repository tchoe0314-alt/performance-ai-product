from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .common import safe_dict, safe_float, safe_list, safe_str


FRAME_VERSION = "civora_imagery_frame_v2"
DETECTION_VERSION = "civora_vision_detection_report_v2"
DATASET_VERSION = "civora_vision_training_dataset_v1"
QUALITY_VERSION = "civora_vision_quality_report_v1"

TRAINABLE_FEATURE_TYPES = {
    "building_footprint",
    "road_or_drive",
    "parking_area",
    "sidewalk_or_path",
    "water/pond/basin",
    "vegetation/tree_area",
    "constraint_area",
    "utility",
}

SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "key",
    "signature",
    "sig",
    "token",
}

SENSITIVE_FIELD_KEYS = SENSITIVE_QUERY_KEYS | {
    "authorization",
    "cookie",
    "password",
    "secret",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, *parts: Any) -> str:
    seed = "|".join(safe_str(part) for part in parts if safe_str(part))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def sanitize_source_url(value: Any) -> str:
    """Remove credentials while retaining enough source identity for audit."""

    raw = safe_str(value)
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        query = [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in SENSITIVE_QUERY_KEYS
        ]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
    except Exception:
        return raw.split("?", 1)[0]


def redact_sensitive_provenance(value: Any, *, field_name: str = "") -> Any:
    """Recursively remove credentials while preserving auditable detector metadata."""

    normalized_field = field_name.strip().lower()
    if normalized_field in SENSITIVE_FIELD_KEYS or normalized_field.endswith(("_token", "_secret", "_password")):
        return None
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = safe_str(key).lower()
            redacted = redact_sensitive_provenance(item, field_name=normalized_key)
            if redacted is not None:
                cleaned[safe_str(key)] = redacted
        return cleaned
    if isinstance(value, list):
        return [redact_sensitive_provenance(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive_provenance(item) for item in value]
    if isinstance(value, str) and (
        normalized_field.endswith(("_url", "_uri"))
        or normalized_field in {"url", "uri", "source_image"}
        or ("://" in value and "?" in value)
    ):
        return sanitize_source_url(value)
    return deepcopy(value)


def _source_fingerprint(value: Any) -> str:
    raw = safe_str(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else ""


def _bbox(value: Any) -> Dict[str, float]:
    rec = safe_dict(value)
    west = rec.get("west", rec.get("min_lng", rec.get("xmin")))
    south = rec.get("south", rec.get("min_lat", rec.get("ymin")))
    east = rec.get("east", rec.get("max_lng", rec.get("xmax")))
    north = rec.get("north", rec.get("max_lat", rec.get("ymax")))
    if any(item in (None, "") for item in (west, south, east, north)):
        return {}
    result = {
        "west": safe_float(west),
        "south": safe_float(south),
        "east": safe_float(east),
        "north": safe_float(north),
    }
    if result["east"] <= result["west"] or result["north"] <= result["south"]:
        return {}
    return result


def build_imagery_frame_v2(
    payload: Optional[Dict[str, Any]] = None,
    *,
    source_url: str = "",
    provider: str = "",
    image_width: Any = 0,
    image_height: Any = 0,
    source_rights: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    request = safe_dict(payload)
    bounds = _bbox(request.get("active_site_boundary")) or _bbox(request.get("bbox"))
    width = max(0, int(safe_float(image_width or request.get("image_width"))))
    height = max(0, int(safe_float(image_height or request.get("image_height"))))
    rights = {
        **safe_dict(request.get("source_rights")),
        **safe_dict(source_rights),
    }
    training_allowed = rights.get("training_use_allowed") is True
    storage_allowed = rights.get("storage_allowed") is True
    sanitized_url = sanitize_source_url(source_url or request.get("image_url") or request.get("source_image"))
    frame_id = _stable_id(
        "frame",
        sanitized_url,
        bounds,
        width,
        height,
        provider,
    )
    blockers: List[str] = []
    if not bounds:
        blockers.append("imagery_frame_missing_geographic_bounds")
    if not width or not height:
        blockers.append("imagery_frame_missing_pixel_dimensions")
    if not training_allowed:
        blockers.append("imagery_source_training_rights_not_confirmed")
    return {
        "version": FRAME_VERSION,
        "frame_id": frame_id,
        "provider": safe_str(provider, "unknown_imagery_provider"),
        "source_url": sanitized_url,
        "source_fingerprint_sha256": _source_fingerprint(source_url or sanitized_url),
        "captured_at": safe_str(request.get("imagery_date") or request.get("source_date")),
        "retrieved_at": _now_iso(),
        "image_width_px": width,
        "image_height_px": height,
        "bbox_wgs84": bounds,
        "crs": {"epsg": "EPSG:4326", "axis_order": "longitude_latitude"} if bounds else {},
        "pixel_transform": {
            "origin": "top_left",
            "x_axis": "east",
            "y_axis": "south",
            "pixel_coordinates_are_edges": False,
        },
        "georeference_ready": bool(bounds and width and height),
        "source_rights": {
            "license": safe_str(rights.get("license") or rights.get("license_name"), "unconfirmed"),
            "attribution": safe_str(rights.get("attribution")),
            "training_use_allowed": training_allowed,
            "storage_allowed": storage_allowed,
            "rights_source": safe_str(rights.get("rights_source")),
            "reviewed_by": safe_str(rights.get("reviewed_by")),
            "reviewed_at": safe_str(rights.get("reviewed_at")),
            "request_attestation_trusted": rights.get("request_attestation_trusted") is True,
        },
        "training_blockers": blockers,
        "truth_label": (
            "The imagery frame preserves pixel-to-map provenance. Model training is permitted only when source rights "
            "explicitly allow it; map location alone does not create training rights."
        ),
    }


def _pixel_point_to_wgs84(point: Any, frame: Dict[str, Any]) -> Optional[List[float]]:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    # A coordinate collection can also have length >= 2. Reject nested values
    # here so LineString and Polygon arrays recurse instead of collapsing into
    # one bogus point at the image origin.
    if any(isinstance(value, (list, tuple, dict, set)) or isinstance(value, bool) for value in point[:2]):
        return None
    try:
        x = float(point[0])
        y = float(point[1])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    bounds = _bbox(frame.get("bbox_wgs84"))
    width = safe_float(frame.get("image_width_px"))
    height = safe_float(frame.get("image_height_px"))
    if not bounds or width <= 0 or height <= 0:
        return None
    x = min(max(x, 0.0), width)
    y = min(max(y, 0.0), height)
    lng = bounds["west"] + (x / width) * (bounds["east"] - bounds["west"])
    lat = bounds["north"] - (y / height) * (bounds["north"] - bounds["south"])
    return [round(lng, 9), round(lat, 9)]


def _transform_coordinates(value: Any, frame: Dict[str, Any]) -> Any:
    point = _pixel_point_to_wgs84(value, frame)
    if point is not None:
        return point
    if isinstance(value, list):
        transformed = [_transform_coordinates(item, frame) for item in value]
        return [item for item in transformed if item not in (None, [], {})]
    return None


def georeference_pixel_geometry(geometry: Any, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rec = safe_dict(geometry)
    if not rec or not frame.get("georeference_ready"):
        return None
    geometry_type = safe_str(rec.get("type"))
    if geometry_type == "Feature":
        nested = georeference_pixel_geometry(rec.get("geometry"), frame)
        return {"type": "Feature", "geometry": nested, "properties": safe_dict(rec.get("properties"))} if nested else None
    if geometry_type not in {"Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"}:
        return None
    coordinates = _transform_coordinates(rec.get("coordinates"), frame)
    if coordinates in (None, [], {}):
        return None
    return {"type": geometry_type, "coordinates": coordinates}


def _bbox_polygon(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, (list, tuple)) or len(value) < 4:
        return None
    x, y, width, height = (safe_float(value[0]), safe_float(value[1]), safe_float(value[2]), safe_float(value[3]))
    if width <= 0 or height <= 0:
        return None
    return {
        "type": "Polygon",
        "coordinates": [[[x, y], [x + width, y], [x + width, y + height], [x, y + height], [x, y]]],
    }


def _pixel_geometry(detection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    geometry = safe_dict(detection.get("pixel_geometry") or detection.get("geometry"))
    if geometry.get("type") and geometry.get("coordinates") not in (None, [], {}):
        return geometry
    return _bbox_polygon(detection.get("bbox") or detection.get("bounds"))


def build_vision_detection_report_v2(
    *,
    detections: Optional[Iterable[Dict[str, Any]]] = None,
    imagery_frame: Optional[Dict[str, Any]] = None,
    provider: str = "",
    detector_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    frame = deepcopy(safe_dict(imagery_frame))
    detector = {
        "provider": safe_str(provider or safe_dict(detector_metadata).get("provider"), "unknown_detector"),
        "model_name": safe_str(safe_dict(detector_metadata).get("model_name"), safe_str(provider, "unknown_detector")),
        "model_version": safe_str(safe_dict(detector_metadata).get("model_version"), "unversioned"),
        "detector_kind": safe_str(safe_dict(detector_metadata).get("detector_kind"), "unknown"),
        "inference_parameters": safe_dict(safe_dict(detector_metadata).get("inference_parameters")),
    }
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(detections or []):
        rec = safe_dict(redact_sensitive_provenance(safe_dict(item)))
        label = safe_str(rec.get("kind") or rec.get("feature_type") or rec.get("label"))
        if not label:
            continue
        pixel_geometry = _pixel_geometry(rec)
        geo_geometry = safe_dict(rec.get("geo_geometry")) or (
            georeference_pixel_geometry(pixel_geometry, frame) if pixel_geometry else None
        )
        detection_id = safe_str(rec.get("detection_id") or rec.get("id"), f"vision_{index + 1}")
        normalized.append(
            {
                **deepcopy(rec),
                "detection_id": detection_id,
                "kind": label,
                "confidence": round(min(max(safe_float(rec.get("confidence"), 0.35), 0.0), 1.0), 4),
                "imagery_frame_id": safe_str(frame.get("frame_id")),
                "pixel_geometry": pixel_geometry,
                "geo_geometry": geo_geometry or None,
                "geometry_space": "EPSG:4326" if geo_geometry else "image_pixels",
                "review_status": safe_str(rec.get("review_status"), "pending"),
                "review_required": True,
            }
        )
    by_kind: Dict[str, int] = {}
    for rec in normalized:
        kind = safe_str(rec.get("kind"), "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    georeferenced = sum(1 for rec in normalized if safe_dict(rec.get("geo_geometry")))
    return {
        "version": DETECTION_VERSION,
        "status": "detected" if normalized else "ready_empty",
        "imagery_frame": frame,
        "detector": detector,
        "detection_count": len(normalized),
        "georeferenced_detection_count": georeferenced,
        "by_kind": by_kind,
        "detections": normalized,
        "review_required": True,
        "canonical_geometry_allowed": False,
        "training_ready": bool(
            normalized
            and frame.get("georeference_ready")
            and safe_dict(frame.get("source_rights")).get("training_use_allowed") is True
        ),
        "truth_label": (
            "Civora vision detections are georeferenced visual candidates. They become training examples only after "
            "a review decision and explicit source-rights clearance."
        ),
    }


def _geometry_bbox(geometry: Any) -> Optional[Tuple[float, float, float, float]]:
    rec = safe_dict(geometry)
    if rec.get("type") == "Feature":
        return _geometry_bbox(rec.get("geometry"))
    points: List[Tuple[float, float]] = []

    def collect(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(value[i], (int, float)) for i in (0, 1)):
            points.append((float(value[0]), float(value[1])))
        elif isinstance(value, (list, tuple)):
            for child in value:
                collect(child)

    collect(rec.get("coordinates"))
    if not points:
        return None
    return (min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points))


def _bbox_iou(a: Optional[Tuple[float, float, float, float]], b: Optional[Tuple[float, float, float, float]]) -> float:
    if not a or not b:
        return 0.0
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    intersection = (x2 - x1) * (y2 - y1)
    area_a = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    return intersection / max(area_a + area_b - intersection, 1e-12)


def _source_priority(candidate: Dict[str, Any]) -> int:
    source_type = safe_str(candidate.get("source_type"))
    if source_type == "official_gis" and safe_str(candidate.get("acceptance_status")) == "accepted":
        return 50
    return {
        "official_gis": 40,
        "community_mapped": 30,
        "user_drawn": 25,
        "image_detected_candidate": 20,
        "public_dem": 10,
    }.get(source_type, 0)


def resolve_detection_source_conflicts(
    candidates: Iterable[Dict[str, Any]],
    *,
    overlap_threshold: float = 0.55,
) -> Dict[str, Any]:
    records = [deepcopy(safe_dict(item)) for item in candidates if safe_dict(item)]
    conflicts: List[Dict[str, Any]] = []
    corroborating_ids: set[str] = set()
    for left_index, left in enumerate(records):
        left_box = _geometry_bbox(left.get("geometry"))
        if not left_box:
            continue
        for right_index in range(left_index + 1, len(records)):
            right = records[right_index]
            right_box = _geometry_bbox(right.get("geometry"))
            overlap = _bbox_iou(left_box, right_box)
            if overlap < overlap_threshold:
                continue
            left_id = safe_str(left.get("candidate_id"))
            right_id = safe_str(right.get("candidate_id"))
            same_type = safe_str(left.get("feature_type")) == safe_str(right.get("feature_type"))
            if same_type:
                primary, supporting = (left, right) if _source_priority(left) >= _source_priority(right) else (right, left)
                supporting["render_as_primary"] = False
                supporting["corroborates_candidate_id"] = safe_str(primary.get("candidate_id"))
                supporting["source_relationship"] = "corroborating_overlap"
                corroborating_ids.add(safe_str(supporting.get("candidate_id")))
                relation = "corroborating_overlap"
            else:
                left["source_conflict"] = True
                right["source_conflict"] = True
                left["conflicting_candidate_ids"] = sorted(set(safe_list(left.get("conflicting_candidate_ids")) + [right_id]))
                right["conflicting_candidate_ids"] = sorted(set(safe_list(right.get("conflicting_candidate_ids")) + [left_id]))
                relation = "classification_disagreement"
            conflicts.append(
                {
                    "left_candidate_id": left_id,
                    "right_candidate_id": right_id,
                    "relation": relation,
                    "overlap_iou": round(overlap, 4),
                    "review_required": True,
                }
            )
    return {
        "candidates": records,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "corroborating_candidate_count": len(corroborating_ids),
        "classification_disagreement_count": sum(1 for rec in conflicts if rec["relation"] == "classification_disagreement"),
        "truth_label": "Overlapping sources are preserved and ranked; source priority never silently turns a detection into authoritative geometry.",
    }


def _latest_decisions(meta: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for item in safe_list(meta.get("candidate_review_decisions_v1")):
        rec = safe_dict(item)
        candidate_id = safe_str(rec.get("candidate_id"))
        if candidate_id:
            result[candidate_id] = rec
    return result


def _site_object_corrections(project_input: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    manual = safe_dict(safe_dict(project_input).get("manual_fields"))
    result: Dict[str, Dict[str, Any]] = {}
    for item in safe_list(manual.get("site_objects")):
        rec = safe_dict(item)
        meta = safe_dict(rec.get("meta"))
        candidate_id = safe_str(meta.get("source_candidate_id") or rec.get("source_candidate_id"))
        if candidate_id:
            result[candidate_id] = rec
    return result


def build_vision_training_dataset(
    meta: Dict[str, Any],
    *,
    project_input: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source_meta = safe_dict(meta)
    map_report = safe_dict(source_meta.get("map_feature_detection_report_v1"))
    imagery_report = safe_dict(map_report.get("imagery_object_detection_report_v1"))
    vision_report = safe_dict(
        map_report.get(DETECTION_VERSION)
        or imagery_report.get(DETECTION_VERSION)
        or source_meta.get(DETECTION_VERSION)
    )
    frame = safe_dict(vision_report.get("imagery_frame"))
    decisions = _latest_decisions(source_meta)
    object_corrections = _site_object_corrections(project_input)
    detections_by_id = {
        safe_str(safe_dict(item).get("detection_id")): safe_dict(item)
        for item in safe_list(vision_report.get("detections"))
        if safe_str(safe_dict(item).get("detection_id"))
    }
    examples: List[Dict[str, Any]] = []
    rights = safe_dict(frame.get("source_rights"))
    rights_allowed = rights.get("training_use_allowed") is True
    for item in safe_list(map_report.get("feature_candidates")):
        candidate = safe_dict(item)
        if safe_str(candidate.get("source_type")) != "image_detected_candidate":
            continue
        candidate_id = safe_str(candidate.get("candidate_id"))
        properties = safe_dict(candidate.get("properties"))
        detection_id = safe_str(candidate.get("source_feature_id") or properties.get("vision_detection_id"))
        detection = detections_by_id.get(detection_id, {})
        decision = decisions.get(candidate_id, {})
        placement = object_corrections.get(candidate_id, {})
        action = safe_str(decision.get("action"), "pending")
        corrected_label = safe_str(decision.get("corrected_feature_type"))
        corrected_geometry = decision.get("corrected_geometry")
        correction_space = safe_str(decision.get("correction_coordinate_space"))
        if placement:
            placement_geometry = placement.get("geometry")
            if placement_geometry not in (None, [], {}):
                corrected_geometry = placement_geometry
                correction_space = safe_str(safe_dict(placement.get("meta")).get("coordinate_space"), "project_local")
            corrected_label = corrected_label or safe_str(placement.get("type"))
        reviewed = action in {"accept", "reject", "correct", "reclassify", "redraw"}
        geometry_available = bool(
            safe_dict(detection.get("pixel_geometry"))
            or safe_dict(detection.get("geo_geometry"))
            or safe_dict(candidate.get("geometry"))
        )
        blockers: List[str] = []
        if not rights_allowed:
            blockers.append("imagery_source_training_rights_not_confirmed")
        if not reviewed:
            blockers.append("candidate_review_decision_missing")
        if not geometry_available:
            blockers.append("candidate_geometry_missing")
        if corrected_geometry not in (None, [], {}) and correction_space not in {"image_pixels", "EPSG:4326"}:
            blockers.append("corrected_geometry_needs_imagery_registration")
        training_eligible = not blockers
        examples.append(
            {
                "example_id": _stable_id("vision_example", candidate_id, action, corrected_label, corrected_geometry),
                "candidate_id": candidate_id,
                "detection_id": detection_id,
                "imagery_frame_id": safe_str(frame.get("frame_id")),
                "original_feature_type": safe_str(candidate.get("feature_type")),
                "corrected_feature_type": corrected_label,
                "review_action": action,
                "reviewer_id": safe_str(decision.get("reviewed_by")),
                "reviewed_at": safe_str(decision.get("reviewed_at")),
                "review_reason": safe_str(decision.get("reason")),
                "confidence": candidate.get("confidence"),
                "pixel_geometry": detection.get("pixel_geometry"),
                "geo_geometry": detection.get("geo_geometry") or candidate.get("geometry"),
                "corrected_geometry": corrected_geometry,
                "correction_coordinate_space": correction_space,
                "source_provider": safe_str(candidate.get("source_name")),
                "source_url": sanitize_source_url(candidate.get("source_url")),
                "training_eligible": training_eligible,
                "training_blockers": blockers,
                "review_required": True,
            }
        )
    reviewed_examples = [item for item in examples if item["review_action"] != "pending"]
    eligible_examples = [item for item in examples if item["training_eligible"]]
    rights_blockers = sorted({blocker for item in examples for blocker in safe_list(item.get("training_blockers")) if "rights" in safe_str(blocker)})
    return {
        "version": DATASET_VERSION,
        "generated_at": _now_iso(),
        "imagery_frames": [frame] if frame else [],
        "example_count": len(examples),
        "reviewed_example_count": len(reviewed_examples),
        "training_eligible_example_count": len(eligible_examples),
        "counts": {
            "accepted": sum(1 for item in examples if item["review_action"] == "accept"),
            "rejected": sum(1 for item in examples if item["review_action"] == "reject"),
            "corrected": sum(1 for item in examples if item["review_action"] in {"correct", "reclassify", "redraw"}),
            "pending": sum(1 for item in examples if item["review_action"] == "pending"),
        },
        "examples": examples,
        "source_rights_blockers": rights_blockers,
        "contains_image_bytes": False,
        "export_safe": True,
        "truth_label": (
            "This manifest contains review labels and geometry provenance, not source image bytes. Training examples remain "
            "excluded until the imagery license permits training and required coordinate registration is complete."
        ),
    }


def evaluate_detection_quality(
    predictions: Iterable[Dict[str, Any]],
    ground_truth: Iterable[Dict[str, Any]],
    *,
    iou_threshold: float = 0.5,
) -> Dict[str, Any]:
    predicted = [safe_dict(item) for item in predictions if safe_dict(item)]
    truth = [safe_dict(item) for item in ground_truth if safe_dict(item)]
    matched_truth: set[int] = set()
    matched_ious: List[float] = []
    true_positive = 0
    for prediction in sorted(predicted, key=lambda item: safe_float(item.get("confidence")), reverse=True):
        pred_label = safe_str(prediction.get("feature_type") or prediction.get("kind") or prediction.get("label"))
        pred_box = _geometry_bbox(prediction.get("geometry") or prediction.get("geo_geometry"))
        prediction_scope = _evaluation_scope(prediction)
        best_index = -1
        best_iou = 0.0
        for index, annotation in enumerate(truth):
            if index in matched_truth:
                continue
            annotation_scope = _evaluation_scope(annotation)
            if prediction_scope and annotation_scope and prediction_scope != annotation_scope:
                continue
            truth_label = safe_str(annotation.get("feature_type") or annotation.get("kind") or annotation.get("label"))
            if pred_label != truth_label:
                continue
            overlap = _bbox_iou(pred_box, _geometry_bbox(annotation.get("geometry") or annotation.get("geo_geometry")))
            if overlap > best_iou:
                best_iou = overlap
                best_index = index
        if best_index >= 0 and best_iou >= iou_threshold:
            matched_truth.add(best_index)
            matched_ious.append(best_iou)
            true_positive += 1
    false_positive = len(predicted) - true_positive
    false_negative = len(truth) - true_positive
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return {
        "evaluation_status": "measured_against_ground_truth",
        "geometry_metric": "class_aware_bounding_box_iou",
        "iou_threshold": iou_threshold,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "mean_matched_iou": round(sum(matched_ious) / len(matched_ious), 4) if matched_ious else 0.0,
    }


def _evaluation_scope(item: Dict[str, Any]) -> str:
    if item.get("image_id") not in (None, ""):
        return f"image:{item.get('image_id')}"
    frame_id = safe_str(item.get("imagery_frame_id") or item.get("frame_id"))
    if frame_id:
        return f"frame:{frame_id}"
    file_name = safe_str(item.get("file_name"))
    return f"file:{file_name}" if file_name else ""


def build_vision_quality_report(
    dataset: Dict[str, Any],
    *,
    predictions: Optional[Iterable[Dict[str, Any]]] = None,
    ground_truth: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    counts = safe_dict(dataset.get("counts"))
    reviewed = max(0, int(safe_float(dataset.get("reviewed_example_count"))))
    accepted_or_corrected = int(safe_float(counts.get("accepted"))) + int(safe_float(counts.get("corrected")))
    evaluation = (
        evaluate_detection_quality(predictions or [], ground_truth or [])
        if ground_truth is not None
        else {
            "evaluation_status": "ground_truth_not_attached",
            "geometry_metric": "class_aware_bounding_box_iou",
            "precision": None,
            "recall": None,
            "f1": None,
            "mean_matched_iou": None,
        }
    )
    return {
        "version": QUALITY_VERSION,
        "generated_at": _now_iso(),
        "reviewed_example_count": reviewed,
        "review_agreement_rate": round(accepted_or_corrected / reviewed, 4) if reviewed else None,
        "review_rejection_rate": round(int(safe_float(counts.get("rejected"))) / reviewed, 4) if reviewed else None,
        "training_eligible_example_count": int(safe_float(dataset.get("training_eligible_example_count"))),
        **evaluation,
        "quality_claim_allowed": evaluation.get("evaluation_status") == "measured_against_ground_truth",
        "truth_label": (
            "Accept/reject rates are reviewer feedback, not precision or recall. Accuracy metrics remain unavailable until "
            "a rights-cleared ground-truth annotation set is attached."
        ),
    }


def build_vision_learning_package(
    meta: Dict[str, Any],
    *,
    project_input: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    dataset = build_vision_training_dataset(meta, project_input=project_input)
    quality = build_vision_quality_report(dataset)
    return {
        "success": True,
        DATASET_VERSION: dataset,
        QUALITY_VERSION: quality,
        "truth_label": dataset.get("truth_label"),
    }


__all__ = [
    "DATASET_VERSION",
    "DETECTION_VERSION",
    "FRAME_VERSION",
    "QUALITY_VERSION",
    "build_imagery_frame_v2",
    "build_vision_detection_report_v2",
    "build_vision_learning_package",
    "build_vision_quality_report",
    "build_vision_training_dataset",
    "evaluate_detection_quality",
    "georeference_pixel_geometry",
    "redact_sensitive_provenance",
    "resolve_detection_source_conflicts",
    "sanitize_source_url",
]
