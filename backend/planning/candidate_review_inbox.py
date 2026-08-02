from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .cad_entity_model import plan_pdf_elements_to_cad_entities
from .common import safe_dict, safe_float, safe_list, safe_str
from .map_feature_detection import accept_feature_candidate_as_draft_object
from .vision_detection_learning import TRAINABLE_FEATURE_TYPES
from .vision_ground_truth_flywheel import (
    ACTIVE_QUEUE_VERSION as VISION_ACTIVE_QUEUE_VERSION,
    COVERAGE_VERSION as VISION_COVERAGE_VERSION,
    DATASET_VERSION as VISION_GROUND_TRUTH_DATASET_VERSION,
    LEDGER_VERSION as VISION_GROUND_TRUTH_LEDGER_VERSION,
    SPLIT_REGISTRY_VERSION as VISION_SPLIT_REGISTRY_VERSION,
    WORKSPACE_VERSION as VISION_REVIEW_WORKSPACE_VERSION,
    append_ground_truth_review_event,
    attach_vision_ground_truth_flywheel,
)


INBOX_VERSION = "candidate_review_inbox_v1"

ACCEPTED_STATUSES = {"accepted", "draft_review_required"}
REJECTED_STATUSES = {"rejected", "unaccepted_rejected"}
PENDING_STATUSES = {"", "pending", "candidate", "unaccepted", "review_required"}

AREA_CORRECTION_TYPES = {
    "building_footprint",
    "parking_area",
    "water/pond/basin",
    "vegetation/tree_area",
    "constraint_area",
}

MAP_KIND_BY_FEATURE_TYPE = {
    "parcel_or_site_boundary": "parcel_site_boundary",
    "building_footprint": "building_footprint",
    "road_or_drive": "road_row",
    "road_row": "road_row",
    "right_of_way": "road_row",
    "parking": "parking_object",
    "parking_area": "parking_object",
    "parking_stall": "parking_object",
    "object": "parking_object",
    "detected_object": "parking_object",
    "terrain": "terrain_dem",
    "dem": "terrain_dem",
    "lidar": "terrain_dem",
    "water/pond/basin": "floodplain_wetland_constraint",
    "floodplain": "floodplain_wetland_constraint",
    "wetland": "floodplain_wetland_constraint",
    "constraint_area": "floodplain_wetland_constraint",
    "utility": "utility",
}

IMPORT_SOURCE_TYPE_BY_CANDIDATE_TYPE = {
    "surface_xyz_csv": "terrain_dem",
    "geotiff_surface": "terrain_dem",
    "las_point_cloud": "terrain_dem",
    "lidar_point_cloud": "terrain_dem",
    "dem_raster": "terrain_dem",
    "landxml": "uploaded_imported_layer",
    "landxml_surface": "terrain_dem",
    "dxf": "uploaded_imported_layer",
    "dxf_existing_conditions": "uploaded_imported_layer",
    "dwg_existing_conditions": "uploaded_imported_layer",
    "geojson": "uploaded_imported_layer",
    "geospatial_vector": "uploaded_imported_layer",
    "shapefile": "uploaded_imported_layer",
    "survey_csv": "uploaded_imported_layer",
    "image_detection": "uploaded_image_map_detection",
    "map_snapshot_detection": "uploaded_image_map_detection",
    "uploaded_image_detection": "uploaded_image_map_detection",
}


def _today() -> str:
    return date.today().isoformat()


def _stable_id(*parts: Any) -> str:
    seed = "|".join(safe_str(part) for part in parts if safe_str(part))
    digest = hashlib.sha1(seed.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    return f"cri_{digest}"


def _status(value: Any) -> str:
    text = safe_str(value).lower()
    if text in ACCEPTED_STATUSES:
        return "accepted"
    if text in REJECTED_STATUSES or "reject" in text:
        return "rejected"
    if text in PENDING_STATUSES:
        return "pending"
    return "pending"


def _confidence(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(max(0.0, min(1.0, safe_float(value))), 3)
    return safe_str(value) or "unknown"


def _validated_correction_geometry(
    value: Any,
    *,
    coordinate_space: str,
    feature_type: str,
) -> Dict[str, Any]:
    geometry = deepcopy(safe_dict(value))
    geometry_type = safe_str(geometry.get("type"))
    if geometry_type not in {"Point", "LineString", "Polygon"}:
        raise ValueError("corrected_geometry must be Point, LineString, or Polygon GeoJSON.")
    if coordinate_space not in {"image_pixels", "EPSG:4326", "project_local"}:
        raise ValueError("correction_coordinate_space must be image_pixels, EPSG:4326, or project_local.")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        point_groups = [[coordinates]]
    elif geometry_type == "LineString":
        point_groups = [coordinates]
    else:
        point_groups = coordinates
    if not isinstance(point_groups, list) or not point_groups:
        raise ValueError("corrected_geometry coordinates are missing.")
    normalized_groups: List[List[List[float]]] = []
    for group in point_groups:
        if not isinstance(group, list):
            raise ValueError("corrected_geometry coordinates are invalid.")
        normalized_points: List[List[float]] = []
        for point in group:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise ValueError("corrected_geometry points must contain x/y coordinates.")
            x = safe_float(point[0], float("nan"))
            y = safe_float(point[1], float("nan"))
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("corrected_geometry coordinates must be finite numbers.")
            if coordinate_space == "EPSG:4326" and not (-180 <= x <= 180 and -90 <= y <= 90):
                raise ValueError("EPSG:4326 correction coordinates must be valid longitude/latitude values.")
            if coordinate_space == "image_pixels" and (x < 0 or y < 0):
                raise ValueError("Image-pixel correction coordinates cannot be negative.")
            normalized_points.append([x, y])
        normalized_groups.append(normalized_points)
    points = normalized_groups[0]
    if geometry_type == "Point" and len(points) != 1:
        raise ValueError("Point correction geometry must contain exactly one point.")
    if geometry_type == "LineString" and len(points) < 2:
        raise ValueError("LineString correction geometry needs at least two points.")
    if geometry_type == "Polygon":
        if len(points) < 3:
            raise ValueError("Polygon correction geometry needs at least three unique points.")
        if points[0] != points[-1]:
            points.append(list(points[0]))
        if len({(point[0], point[1]) for point in points[:-1]}) < 3:
            raise ValueError("Polygon correction geometry needs at least three unique points.")
        signed_area = sum(
            points[index][0] * points[index + 1][1] - points[index + 1][0] * points[index][1]
            for index in range(len(points) - 1)
        ) / 2
        if abs(signed_area) <= 1e-9:
            raise ValueError("Polygon correction geometry cannot have zero area.")
        try:
            from shapely.geometry import shape

            if not shape({"type": "Polygon", "coordinates": normalized_groups}).is_valid:
                raise ValueError("Polygon correction geometry is self-intersecting or otherwise invalid.")
        except ImportError:
            pass
    if feature_type in AREA_CORRECTION_TYPES and geometry_type != "Polygon":
        raise ValueError(f"{feature_type} corrections require Polygon geometry.")
    if geometry_type == "Point":
        normalized_coordinates: Any = points[0]
    elif geometry_type == "LineString":
        normalized_coordinates = points
    else:
        normalized_coordinates = normalized_groups
    return {"type": geometry_type, "coordinates": normalized_coordinates}


def _candidate(
    *,
    candidate_id: str,
    candidate_type: str,
    label: str,
    source: str = "",
    provider: str = "",
    source_url: str = "",
    source_date: str = "",
    confidence: Any = "",
    status: str = "pending",
    object_count: Any = None,
    blocker_review_reason: str = "",
    source_record: Optional[Dict[str, Any]] = None,
    audit_trail: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "label": label,
        "source": source or source_url or provider or "unknown_source",
        "provider": provider or source or "unknown_provider",
        "source_url": source_url,
        "source_date": source_date,
        "confidence": _confidence(confidence),
        "status": _status(status),
        "object_count": max(1, int(safe_float(object_count))) if object_count not in (None, "") else 1,
        "blocker_review_reason": blocker_review_reason
        or "Review and accept, reject, or leave pending before relying on this candidate.",
        "review_required": True,
        "accepted_as": "project_draft_review_required_evidence" if _status(status) == "accepted" else "",
        "construction_release_allowed": False,
        "construction_readiness_implied": False,
        "source_record": deepcopy(source_record or {}),
        "audit_trail": [deepcopy(safe_dict(item)) for item in audit_trail or []],
        "truth_label": (
            "Candidate review decisions create project draft/review-required evidence only. "
            "They do not create survey truth, construction readiness, approval, stamp, seal, or engineer-of-record decisions."
        ),
    }


def _map_candidate_type(candidate: Dict[str, Any]) -> str:
    feature_type = safe_str(candidate.get("feature_type") or candidate.get("candidate_type"))
    mapped = MAP_KIND_BY_FEATURE_TYPE.get(feature_type, "uploaded_imported_layer")
    layer_hint = " ".join(
        safe_str(value).lower()
        for value in (
            candidate.get("source_name"),
            candidate.get("source_type"),
            safe_dict(candidate.get("properties")).get("layer"),
        )
        if safe_str(value)
    )
    if mapped == "floodplain_wetland_constraint" and "utility" in layer_hint:
        return "utility"
    if mapped == "floodplain_wetland_constraint" and ("row" in layer_hint or "right_of_way" in layer_hint):
        return "road_row"
    if mapped == "uploaded_imported_layer" and any(token in layer_hint for token in ("parking", "stall", "vehicle")):
        return "parking_object"
    if mapped == "uploaded_imported_layer" and any(token in layer_hint for token in ("terrain", "dem", "lidar", "contour", "surface")):
        return "terrain_dem"
    if mapped == "uploaded_imported_layer" and any(token in layer_hint for token in ("flood", "wetland", "constraint")):
        return "floodplain_wetland_constraint"
    return mapped


def _object_count(record: Dict[str, Any], *, fallback: int = 1) -> int:
    for key in ("object_count", "feature_count", "candidate_count", "detected_count", "count"):
        value = record.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(1, int(value))
    for key in ("features", "objects", "detections", "items", "geometries"):
        values = safe_list(record.get(key))
        if values:
            return len(values)
    return max(1, fallback)


def _map_feature_candidates(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    report = safe_dict(meta.get("map_feature_detection_report_v1"))
    candidates = []
    for rec in safe_list(report.get("feature_candidates")):
        candidate = safe_dict(rec)
        if not candidate:
            continue
        blocker = "; ".join(safe_str(item) for item in safe_list(candidate.get("blockers")) if safe_str(item))
        candidate_id = safe_str(candidate.get("candidate_id")) or _stable_id("map", candidate.get("source_feature_id"), candidate.get("geometry"))
        candidates.append(
            _candidate(
                candidate_id=candidate_id,
                candidate_type=_map_candidate_type(candidate),
                label=safe_str(candidate.get("feature_type")).replace("_", " ") or "Map/GIS candidate",
                source=safe_str(candidate.get("evidence_source") or candidate.get("source_name") or candidate.get("source_type")),
                provider=safe_str(candidate.get("source_name") or candidate.get("source_type")),
                source_url=safe_str(candidate.get("source_url")),
                source_date=safe_str(candidate.get("source_date") or safe_dict(candidate.get("properties")).get("date")),
                confidence=candidate.get("confidence"),
                status=candidate.get("acceptance_status"),
                object_count=_object_count(candidate),
                blocker_review_reason=blocker or "Map/GIS source is candidate evidence until explicitly reviewed for this project.",
                source_record=candidate,
                audit_trail=safe_list(candidate.get("audit_trail")),
            )
        )
    return candidates


def _candidate_rules_from_meta(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    reports = [
        safe_dict(meta.get("candidate_rule_report")),
        safe_dict(meta.get("standards_candidate_rule_report")),
        safe_dict(safe_dict(meta.get("standards_review_packet")).get("candidate_rule_report")),
        safe_dict(safe_dict(meta.get("standards_package")).get("candidate_rule_report")),
    ]
    candidates: List[Dict[str, Any]] = []
    seen = set()
    for report in reports:
        for rule in safe_list(report.get("candidate_rules")):
            rec = safe_dict(rule)
            rule_id = safe_str(rec.get("rule_id"))
            if not rule_id or rule_id in seen:
                continue
            candidates.append(rec)
            seen.add(rule_id)
    packet = safe_dict(meta.get("standards_review_packet"))
    for rule in safe_list(packet.get("candidate_rules")):
        rec = safe_dict(rule)
        rule_id = safe_str(rec.get("rule_id"))
        if rule_id and rule_id not in seen:
            candidates.append(rec)
            seen.add(rule_id)
    return candidates


def _standards_status_by_rule(meta: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, List[Dict[str, Any]]]]:
    acceptance = safe_dict(meta.get("standards_acceptance"))
    status_by_rule: Dict[str, str] = {}
    audit_by_rule: Dict[str, List[Dict[str, Any]]] = {}
    for key, status in (("accepted_rules", "accepted"), ("rejected_rules", "rejected"), ("pending_rules", "pending")):
        for item in safe_list(acceptance.get(key)):
            rec = safe_dict(item)
            rule_id = safe_str(rec.get("rule_id") or rec.get("candidate_rule_id"))
            if rule_id:
                status_by_rule[rule_id] = status
    for audit in safe_list(acceptance.get("audit_trail")):
        rec = safe_dict(audit)
        rule_id = safe_str(rec.get("rule_id"))
        if rule_id:
            audit_by_rule.setdefault(rule_id, []).append(rec)
    return status_by_rule, audit_by_rule


def _standards_candidates(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    status_by_rule, audit_by_rule = _standards_status_by_rule(meta)
    candidates = []
    for rule in _candidate_rules_from_meta(meta):
        rule_id = safe_str(rule.get("rule_id"))
        if not rule_id:
            continue
        status = status_by_rule.get(rule_id) or rule.get("acceptance_status") or rule.get("status")
        candidates.append(
            _candidate(
                candidate_id=f"std_{rule_id}",
                candidate_type="standards",
                label=safe_str(rule.get("topic") or rule.get("discipline") or "Standards candidate"),
                source=safe_str(rule.get("source_id") or rule.get("source_type")),
                provider=safe_str(rule.get("source_id") or rule.get("source_type")),
                source_url=safe_str(rule.get("source_url")),
                source_date=safe_str(rule.get("retrieved_date") or rule.get("retrieved_at")),
                confidence=rule.get("confidence"),
                status=status,
                object_count=1,
                blocker_review_reason="Candidate standards need explicit user/company/engineer review before any QA gate can rely on them.",
                source_record=rule,
                audit_trail=audit_by_rule.get(rule_id, []),
            )
        )
    return candidates


def _online_or_imported_candidates(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    online = safe_dict(meta.get("online_existing_conditions") or meta.get("existing_conditions_online"))
    elevation = safe_dict(online.get("elevation") or meta.get("dem_evidence") or meta.get("terrain_dem_candidate"))
    if elevation:
        candidates.append(
            _candidate(
                candidate_id=_stable_id("terrain_dem", elevation.get("source"), elevation.get("lat"), elevation.get("lng")),
                candidate_type="terrain_dem",
                label="Terrain/DEM candidate",
                source=safe_str(elevation.get("source") or elevation.get("source_type")),
                provider=safe_str(elevation.get("source_type") or "DEM"),
                source_url=safe_str(elevation.get("source")),
                source_date=safe_str(elevation.get("date") or elevation.get("retrieved_at")),
                confidence=elevation.get("confidence") or "public_context",
                status=elevation.get("acceptance_status") or "pending",
                object_count=_object_count(elevation),
                blocker_review_reason=safe_str(
                    elevation.get("truth_label"),
                    "Public DEM/terrain context remains review-required and is not a stamped topographic survey.",
                ),
                source_record=elevation,
                audit_trail=safe_list(elevation.get("audit_trail")),
            )
        )
    existing_package = safe_dict(meta.get("existing_conditions_package"))
    import_records = (
        safe_list(existing_package.get("import_records"))
        + safe_list(existing_package.get("source_records"))
        + safe_list(meta.get("imported_candidate_layers_v1"))
        + safe_list(meta.get("uploaded_candidate_layers_v1"))
    )
    for idx, layer in enumerate(import_records):
        rec = safe_dict(layer)
        if not rec:
            continue
        source_type = safe_str(rec.get("source_type"))
        candidate_type = safe_str(rec.get("candidate_type")) or IMPORT_SOURCE_TYPE_BY_CANDIDATE_TYPE.get(source_type)
        if candidate_type:
            candidates.append(
                _candidate(
                    candidate_id=_stable_id("import", idx, source_type, rec.get("source") or rec.get("file_name")),
                    candidate_type=candidate_type,
                    label=safe_str(rec.get("label") or source_type or "Imported candidate layer"),
                    source=safe_str(rec.get("source") or rec.get("file_name")),
                    provider=safe_str(rec.get("provider") or source_type),
                    source_url=safe_str(rec.get("source_url")),
                    source_date=safe_str(rec.get("date") or rec.get("imported_at")),
                    confidence=rec.get("confidence") or rec.get("source_quality") or "imported",
                    status=rec.get("acceptance_status") or rec.get("review_status") or "pending",
                    object_count=_object_count(rec),
                    blocker_review_reason=safe_str(
                        rec.get("truth_label"),
                        "Imported source/layer needs review before it can be treated as project evidence.",
                    ),
                    source_record=rec,
                    audit_trail=safe_list(rec.get("audit_trail")),
                )
            )
    for idx, layer in enumerate(safe_list(meta.get("uploaded_image_map_detections_v1")) + safe_list(meta.get("image_detection_candidates_v1"))):
        rec = safe_dict(layer)
        if not rec:
            continue
        candidates.append(
            _candidate(
                candidate_id=safe_str(rec.get("candidate_id")) or _stable_id("image_detection", idx, rec.get("source") or rec.get("file_name")),
                candidate_type=safe_str(rec.get("candidate_type")) or "uploaded_image_map_detection",
                label=safe_str(rec.get("label") or rec.get("feature_type") or "Uploaded image/map detection"),
                source=safe_str(rec.get("source") or rec.get("file_name") or rec.get("source_type")),
                provider=safe_str(rec.get("provider") or rec.get("source_type") or "uploaded image/map"),
                source_url=safe_str(rec.get("source_url")),
                source_date=safe_str(rec.get("date") or rec.get("detected_at") or rec.get("uploaded_at")),
                confidence=rec.get("confidence") or "image_detected",
                status=rec.get("acceptance_status") or rec.get("review_status") or "pending",
                object_count=_object_count(rec),
                blocker_review_reason=safe_str(
                    rec.get("truth_label"),
                    "Uploaded image/map detections are candidate evidence until reviewed and checked against survey/control.",
                ),
                source_record=rec,
                audit_trail=safe_list(rec.get("audit_trail")),
            )
        )
    return candidates


def _plan_pdf_candidates(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    sheet = safe_dict(meta.get("plan_pdf_editable_sheet_v1"))
    analysis = safe_dict(meta.get("plan_pdf_analysis_v1"))
    source = safe_dict(analysis.get("source_pdf"))
    candidates: List[Dict[str, Any]] = []
    for idx, element in enumerate(safe_list(sheet.get("elements"))):
        rec = safe_dict(element)
        if not rec:
            continue
        element_id = safe_str(rec.get("element_id")) or _stable_id("plan_pdf_element", idx, rec.get("text"))
        status = safe_str(rec.get("review_status") or rec.get("status") or "pending")
        element_type = safe_str(rec.get("type"), "pdf_sheet_element")
        text = safe_str(rec.get("text"))
        label = f"PDF {element_type.replace('_', ' ')}"
        if text:
            label = f"{label}: {text[:80]}"
        candidates.append(
            _candidate(
                candidate_id=element_id,
                candidate_type=f"plan_pdf_{element_type}",
                label=label,
                source=safe_str(source.get("filename") or source.get("stored_filename") or "uploaded plan PDF"),
                provider="plan_pdf_analysis_v1",
                source_url=safe_str(source.get("file_url")),
                source_date=safe_str(analysis.get("created_at")),
                confidence=safe_str(rec.get("source_confidence"), "imported_pdf_review_required"),
                status=status,
                object_count=1,
                blocker_review_reason=(
                    "PDF-derived sheet element must be reviewed before use. "
                    "It is not survey-backed or externally reviewed, and protected professional mark areas are not editable."
                ),
                source_record=rec,
                audit_trail=safe_list(rec.get("audit_trail")),
            )
        )
    return candidates


def _plan_pdf_cad_entity_candidates(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for idx, entity in enumerate(plan_pdf_elements_to_cad_entities(meta)):
        rec = safe_dict(entity)
        if not rec:
            continue
        source_pdf = safe_dict(rec.get("source_pdf"))
        annotation_kind = safe_str(rec.get("pdf_annotation_kind") or rec.get("type"), "cad_entity")
        label_text = safe_str(rec.get("original_text") or safe_dict(rec.get("geometry")).get("text"))
        label = f"PDF CAD {annotation_kind}"
        if label_text:
            label = f"{label}: {label_text[:80]}"
        candidates.append(
            _candidate(
                candidate_id=safe_str(rec.get("id")) or _stable_id("plan_pdf_cad_entity", idx, rec.get("linked_pdf_element_id")),
                candidate_type=f"plan_pdf_cad_{annotation_kind}",
                label=label,
                source=safe_str(source_pdf.get("filename"), "uploaded plan PDF"),
                provider="cad_entity_model_v1",
                confidence=safe_str(rec.get("source_confidence"), "imported_pdf_review_required"),
                status=safe_str(rec.get("review_status"), "pending"),
                object_count=1,
                blocker_review_reason=(
                    "PDF-derived CAD entity candidate is imported_pdf_review_required. "
                    "It is not survey-backed, engineer-reviewed, or construction-release evidence."
                ),
                source_record=rec,
            )
        )
    return candidates


def build_candidate_review_inbox(meta: Dict[str, Any]) -> Dict[str, Any]:
    candidates = (
        _map_feature_candidates(meta)
        + _standards_candidates(meta)
        + _online_or_imported_candidates(meta)
        + _plan_pdf_candidates(meta)
        + _plan_pdf_cad_entity_candidates(meta)
    )
    by_id: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        by_id[safe_str(candidate.get("candidate_id"))] = candidate
    ordered = list(by_id.values())
    counts = {"accepted": 0, "rejected": 0, "pending": 0}
    by_type: Dict[str, int] = {}
    for candidate in ordered:
        status = _status(candidate.get("status"))
        counts[status] = counts.get(status, 0) + 1
        ctype = safe_str(candidate.get("candidate_type"), "unknown")
        by_type[ctype] = by_type.get(ctype, 0) + 1
    inbox = {
        "version": INBOX_VERSION,
        "candidate_count": len(ordered),
        "counts": counts,
        "by_type": by_type,
        "candidates": ordered,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "truth_label": (
            "Accepted candidates are project draft/review-required evidence only. "
            "Rejected candidates remain preserved in the audit trail. Pending candidates remain pending."
        ),
    }
    decisions = safe_list(meta.get("candidate_review_decisions_v1"))
    return _inbox_with_decisions(inbox, decisions) if decisions else inbox


def _decision_audit(
    candidate: Dict[str, Any],
    *,
    action: str,
    reviewer_id: str,
    reason: str = "",
    corrected_feature_type: str = "",
    corrected_geometry: Any = None,
    correction_coordinate_space: str = "",
    replacement_geometries: Optional[Iterable[Dict[str, Any]]] = None,
    replacement_feature_types: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    record = {
        "action": action,
        "candidate_id": safe_str(candidate.get("candidate_id")),
        "candidate_type": safe_str(candidate.get("candidate_type")),
        "reviewed_by": reviewer_id,
        "reviewed_at": _today(),
        "reason": reason,
        "result_status": {
            "accept": "draft_review_required",
            "reject": "rejected",
            "pending": "pending",
            "correct": "draft_review_required",
            "reclassify": "draft_review_required",
            "redraw": "draft_review_required",
            "merge": "draft_review_required",
            "split": "draft_review_required",
        }.get(action, "pending"),
    }
    if corrected_feature_type:
        record["corrected_feature_type"] = corrected_feature_type
    if corrected_geometry not in (None, {}, []):
        record["corrected_geometry"] = deepcopy(corrected_geometry)
        record["correction_coordinate_space"] = safe_str(correction_coordinate_space, "project_local")
    normalized_replacements = [deepcopy(safe_dict(item)) for item in replacement_geometries or [] if safe_dict(item)]
    if normalized_replacements:
        record["replacement_geometries"] = normalized_replacements
        record["replacement_feature_types"] = [safe_str(item) for item in replacement_feature_types or []]
        record["correction_coordinate_space"] = safe_str(correction_coordinate_space, "project_local")
    return record


def apply_candidate_review_decision(
    meta: Dict[str, Any],
    *,
    candidate_ids: Iterable[str],
    action: str,
    reviewer_id: str = "",
    reason: str = "",
    corrected_feature_type: str = "",
    corrected_geometry: Any = None,
    correction_coordinate_space: str = "",
    replacement_geometries: Optional[Iterable[Dict[str, Any]]] = None,
    replacement_feature_types: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    # Candidate decisions only mutate the review-state slice. Keeping source
    # reports and geometry records by reference avoids cloning an entire site
    # context package for every Accept/Reject click.
    updated_meta = dict(safe_dict(meta))
    stored_inbox = safe_dict(updated_meta.get(INBOX_VERSION))
    inbox = dict(stored_inbox) if safe_list(stored_inbox.get("candidates")) else build_candidate_review_inbox(updated_meta)
    requested = {safe_str(item) for item in candidate_ids if safe_str(item)}
    if not requested:
        raise ValueError("At least one candidate_id is required.")
    normalized_action = safe_str(action).lower()
    if normalized_action not in {"accept", "reject", "pending", "correct", "reclassify", "redraw", "merge", "split"}:
        raise ValueError("action must be accept, reject, pending, correct, reclassify, redraw, merge, or split.")
    corrected_type = safe_str(corrected_feature_type)
    if corrected_type and corrected_type not in TRAINABLE_FEATURE_TYPES:
        raise ValueError(f"Unsupported corrected_feature_type: {corrected_type}")
    if normalized_action == "reclassify" and not corrected_type:
        raise ValueError("reclassify requires corrected_feature_type.")
    if normalized_action == "redraw" and corrected_geometry in (None, {}, []):
        raise ValueError("redraw requires corrected_geometry.")
    if normalized_action == "merge" and len(requested) < 2:
        raise ValueError("merge requires at least two candidate_ids.")
    if normalized_action == "merge" and corrected_geometry in (None, {}, []):
        raise ValueError("merge requires one reviewed corrected_geometry.")
    raw_replacement_geometries = [safe_dict(item) for item in replacement_geometries or [] if safe_dict(item)]
    raw_replacement_types = [safe_str(item) for item in replacement_feature_types or [] if safe_str(item)]
    if normalized_action == "split" and len(requested) != 1:
        raise ValueError("split requires exactly one candidate_id.")
    if normalized_action == "split" and len(raw_replacement_geometries) < 2:
        raise ValueError("split requires at least two replacement_geometries.")
    unsupported_replacement_types = sorted(set(raw_replacement_types) - TRAINABLE_FEATURE_TYPES)
    if unsupported_replacement_types:
        raise ValueError(f"Unsupported replacement_feature_type(s): {', '.join(unsupported_replacement_types)}")
    if normalized_action == "correct" and not corrected_type and corrected_geometry in (None, {}, []):
        raise ValueError("correct requires a corrected feature type or geometry.")
    reviewer = safe_str(reviewer_id, "user")
    found: List[Dict[str, Any]] = []
    missing = sorted(requested)
    for candidate in safe_list(inbox.get("candidates")):
        rec = safe_dict(candidate)
        if safe_str(rec.get("candidate_id")) in requested:
            found.append(rec)
            missing = [item for item in missing if item != safe_str(rec.get("candidate_id"))]
    if missing:
        raise ValueError(f"Unknown candidate_id(s): {', '.join(missing)}")

    decisions = safe_list(updated_meta.get("candidate_review_decisions_v1"))
    accepted_drafts = safe_list(updated_meta.get("candidate_review_accepted_drafts_v1"))
    rejected = safe_list(updated_meta.get("candidate_review_rejected_v1"))
    normalized_replacements: List[Dict[str, Any]] = []
    if raw_replacement_geometries:
        split_feature_type = corrected_type or safe_str(safe_dict(found[0].get("source_record")).get("feature_type"))
        for index, geometry in enumerate(raw_replacement_geometries):
            replacement_type = raw_replacement_types[index] if index < len(raw_replacement_types) else split_feature_type
            normalized_replacements.append(
                _validated_correction_geometry(
                    geometry,
                    coordinate_space=safe_str(correction_coordinate_space, "project_local"),
                    feature_type=replacement_type,
                )
            )
    for candidate in found:
        normalized_correction_space = safe_str(correction_coordinate_space, "project_local")
        normalized_correction_geometry = corrected_geometry
        if corrected_geometry not in (None, {}, []):
            source_feature_type = safe_str(safe_dict(candidate.get("source_record")).get("feature_type"))
            normalized_correction_geometry = _validated_correction_geometry(
                corrected_geometry,
                coordinate_space=normalized_correction_space,
                feature_type=corrected_type or source_feature_type,
            )
        audit = _decision_audit(
            candidate,
            action=normalized_action,
            reviewer_id=reviewer,
            reason=reason,
            corrected_feature_type=corrected_type,
            corrected_geometry=normalized_correction_geometry,
            correction_coordinate_space=normalized_correction_space,
            replacement_geometries=normalized_replacements,
            replacement_feature_types=raw_replacement_types,
        )
        decisions.append(audit)
        if normalized_action in {"accept", "correct", "reclassify", "redraw", "merge", "split"}:
            corrected_candidate = deepcopy(candidate)
            corrected_source = deepcopy(safe_dict(corrected_candidate.get("source_record")))
            if corrected_type:
                corrected_source["feature_type"] = corrected_type
                corrected_candidate["corrected_feature_type"] = corrected_type
            if normalized_correction_geometry not in (None, {}, []):
                corrected_source["geometry"] = deepcopy(normalized_correction_geometry)
                corrected_candidate["corrected_geometry"] = deepcopy(normalized_correction_geometry)
                corrected_candidate["correction_coordinate_space"] = normalized_correction_space
            corrected_candidate["source_record"] = corrected_source
            draft = _accepted_draft_from_candidate(corrected_candidate, accepted_by=reviewer)
            if normalized_action != "accept":
                draft["vision_correction_action"] = normalized_action
                draft["original_candidate_type"] = safe_str(candidate.get("candidate_type"))
                draft["corrected_feature_type"] = corrected_type
                if normalized_correction_geometry not in (None, {}, []):
                    draft["correction_coordinate_space"] = normalized_correction_space
            accepted_drafts = [item for item in accepted_drafts if safe_str(safe_dict(item).get("source_candidate_id")) != safe_str(candidate.get("candidate_id"))]
            accepted_drafts.append(draft)
            rejected = [
                item
                for item in rejected
                if safe_str(safe_dict(item).get("candidate_id")) != safe_str(candidate.get("candidate_id"))
            ]
        elif normalized_action == "reject":
            accepted_drafts = [
                item
                for item in accepted_drafts
                if safe_str(safe_dict(item).get("source_candidate_id")) != safe_str(candidate.get("candidate_id"))
            ]
            rec = deepcopy(candidate)
            rec["status"] = "rejected"
            rec["rejection_reason"] = reason
            rec["audit_trail"] = safe_list(rec.get("audit_trail")) + [audit]
            rejected = [item for item in rejected if safe_str(safe_dict(item).get("candidate_id")) != safe_str(candidate.get("candidate_id"))]
            rejected.append(rec)
        else:
            accepted_drafts = [
                item
                for item in accepted_drafts
                if safe_str(safe_dict(item).get("source_candidate_id")) != safe_str(candidate.get("candidate_id"))
            ]
            rejected = [
                item
                for item in rejected
                if safe_str(safe_dict(item).get("candidate_id")) != safe_str(candidate.get("candidate_id"))
            ]
    if normalized_action == "merge":
        source_ids = sorted(safe_str(item.get("candidate_id")) for item in found)
        accepted_drafts = [
            item
            for item in accepted_drafts
            if safe_str(safe_dict(item).get("source_candidate_id")) not in source_ids
        ]
        merged_candidate = deepcopy(found[0])
        merged_source = deepcopy(safe_dict(merged_candidate.get("source_record")))
        merged_source["geometry"] = deepcopy(normalized_correction_geometry)
        if corrected_type:
            merged_source["feature_type"] = corrected_type
        merged_candidate["source_record"] = merged_source
        merged_candidate["candidate_id"] = _stable_id("merge", *source_ids, normalized_correction_geometry)
        merged_draft = _accepted_draft_from_candidate(merged_candidate, accepted_by=reviewer)
        merged_draft["source_candidate_ids"] = source_ids
        merged_draft["vision_correction_action"] = "merge"
        merged_draft["correction_coordinate_space"] = safe_str(correction_coordinate_space, "project_local")
        accepted_drafts.append(merged_draft)
    elif normalized_action == "split":
        original_id = safe_str(found[0].get("candidate_id"))
        accepted_drafts = [
            item
            for item in accepted_drafts
            if safe_str(safe_dict(item).get("source_candidate_id")) != original_id
        ]
        for index, geometry in enumerate(normalized_replacements):
            split_candidate = deepcopy(found[0])
            split_source = deepcopy(safe_dict(split_candidate.get("source_record")))
            split_source["geometry"] = deepcopy(geometry)
            split_type = raw_replacement_types[index] if index < len(raw_replacement_types) else corrected_type
            if split_type:
                split_source["feature_type"] = split_type
            split_candidate["source_record"] = split_source
            split_candidate["candidate_id"] = _stable_id("split", original_id, index, geometry)
            split_draft = _accepted_draft_from_candidate(split_candidate, accepted_by=reviewer)
            split_draft["source_candidate_ids"] = [original_id]
            split_draft["vision_correction_action"] = "split"
            split_draft["split_part_index"] = index
            split_draft["correction_coordinate_space"] = safe_str(correction_coordinate_space, "project_local")
            accepted_drafts.append(split_draft)
    updated_meta[VISION_GROUND_TRUTH_LEDGER_VERSION] = append_ground_truth_review_event(
        updated_meta,
        candidates=found,
        action=normalized_action,
        reviewer_id=reviewer,
        reason=reason,
        corrected_feature_type=corrected_type,
        corrected_geometry=(normalized_correction_geometry if corrected_geometry not in (None, {}, []) else None),
        correction_coordinate_space=correction_coordinate_space,
        replacement_geometries=normalized_replacements,
        replacement_feature_types=raw_replacement_types,
    )
    updated_meta["candidate_review_decisions_v1"] = decisions
    updated_meta["candidate_review_accepted_drafts_v1"] = accepted_drafts
    updated_meta["candidate_review_rejected_v1"] = rejected
    updated_meta["candidate_review_inbox_v1"] = _inbox_with_decisions(inbox, decisions)
    updated_meta = attach_vision_ground_truth_flywheel(updated_meta)
    return {
        "success": True,
        "action": normalized_action,
        "candidate_ids": sorted(requested),
        "reviewed_by": reviewer,
        "candidate_review_inbox_v1": updated_meta["candidate_review_inbox_v1"],
        "updated_meta": updated_meta,
        "audit_trail": decisions,
        "accepted_drafts": accepted_drafts,
        "rejected_candidates": rejected,
        VISION_GROUND_TRUTH_LEDGER_VERSION: updated_meta[VISION_GROUND_TRUTH_LEDGER_VERSION],
        VISION_GROUND_TRUTH_DATASET_VERSION: updated_meta[VISION_GROUND_TRUTH_DATASET_VERSION],
        VISION_SPLIT_REGISTRY_VERSION: updated_meta[VISION_SPLIT_REGISTRY_VERSION],
        VISION_ACTIVE_QUEUE_VERSION: updated_meta[VISION_ACTIVE_QUEUE_VERSION],
        VISION_COVERAGE_VERSION: updated_meta[VISION_COVERAGE_VERSION],
        VISION_REVIEW_WORKSPACE_VERSION: updated_meta[VISION_REVIEW_WORKSPACE_VERSION],
        "truth_label": "Candidate decisions and corrections changed review evidence only. Vision corrections become training examples only when imagery rights and coordinate registration permit it.",
    }


def _accepted_draft_from_candidate(candidate: Dict[str, Any], *, accepted_by: str) -> Dict[str, Any]:
    source = safe_dict(candidate.get("source_record"))
    if source.get("candidate_id") and source.get("feature_type"):
        try:
            return accept_feature_candidate_as_draft_object(source, accepted_by=accepted_by)
        except Exception:
            pass
    return {
        "object_id": f"draft_{safe_str(candidate.get('candidate_id'), 'candidate')}",
        "object_type": safe_str(candidate.get("candidate_type"), "review_evidence"),
        "source_candidate_id": safe_str(candidate.get("candidate_id")),
        "source_type": safe_str(candidate.get("candidate_type")),
        "source_url": safe_str(candidate.get("source_url")),
        "source_name": safe_str(candidate.get("source")),
        "confidence": candidate.get("confidence"),
        "status": "draft_review_required",
        "review_required": True,
        "acceptance_status": "accepted",
        "trusted_canonical": False,
        "needs_engineer_review": True,
        "accepted_by": accepted_by,
        "construction_release_allowed": False,
        "audit_trail": [_decision_audit(candidate, action="accept", reviewer_id=accepted_by)],
        "truth_label": "Accepted candidate became draft/review-required evidence only; it is not survey truth or construction readiness.",
    }


def _inbox_with_decisions(inbox: Dict[str, Any], decisions: List[Any]) -> Dict[str, Any]:
    latest_by_id: Dict[str, Dict[str, Any]] = {}
    for item in decisions:
        rec = safe_dict(item)
        candidate_id = safe_str(rec.get("candidate_id"))
        if candidate_id:
            latest_by_id[candidate_id] = rec
    counts = {"accepted": 0, "rejected": 0, "pending": 0}
    candidates = []
    for candidate in safe_list(inbox.get("candidates")):
        rec = dict(safe_dict(candidate))
        latest = latest_by_id.get(safe_str(rec.get("candidate_id")))
        if latest:
            action = safe_str(latest.get("action"))
            rec["status"] = {
                "accept": "accepted",
                "correct": "accepted",
                "reclassify": "accepted",
                "redraw": "accepted",
                "merge": "accepted",
                "split": "accepted",
                "reject": "rejected",
                "pending": "pending",
            }.get(action, rec.get("status"))
            rec["accepted_as"] = "project_draft_review_required_evidence" if rec["status"] == "accepted" else ""
            rec["corrected_feature_type"] = safe_str(latest.get("corrected_feature_type"))
            if latest.get("corrected_geometry") not in (None, {}, []):
                rec["corrected_geometry"] = deepcopy(latest.get("corrected_geometry"))
                rec["correction_coordinate_space"] = safe_str(latest.get("correction_coordinate_space"))
            rec["blocker_review_reason"] = safe_str(latest.get("reason")) or rec.get("blocker_review_reason")
            rec["audit_trail"] = [dict(safe_dict(item)) for item in safe_list(rec.get("audit_trail"))] + [dict(latest)]
        counts[_status(rec.get("status"))] = counts.get(_status(rec.get("status")), 0) + 1
        candidates.append(rec)
    updated = dict(inbox)
    updated["candidates"] = candidates
    updated["counts"] = counts
    return updated


__all__ = [
    "INBOX_VERSION",
    "apply_candidate_review_decision",
    "build_candidate_review_inbox",
]
