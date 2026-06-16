from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from math import isfinite
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .common import safe_dict, safe_float, safe_list, safe_str


CAD_ENTITY_MODEL_VERSION = "cad_entity_model_v1"
CAD_DEFAULT_LAYER_ID = "layer_draft"
CAD_DEFAULT_STYLE_ID = "style_by_layer"
CAD_ENTITY_TYPES = {
    "line",
    "polyline",
    "polygon",
    "rectangle",
    "circle",
    "arc",
    "text",
    "dimension",
    "hatch",
    "block_reference",
    "underlay_reference",
}
CAD_HISTORY_ACTIONS = {
    "entity_created",
    "entity_updated",
    "entity_deleted",
    "entity_converted",
    "entity_imported",
}
LOW_CONFIDENCE_LABELS = {"", "missing", "metadata-only", "metadata_only", "inferred", "GIS candidate", "map imagery candidate"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(prefix: str, *parts: Any) -> str:
    seed = "|".join(safe_str(part) for part in parts if safe_str(part))
    if not seed:
        seed = f"{prefix}|cad"
    return f"{prefix}_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}"


def _dedupe(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _point(value: Any) -> Optional[Dict[str, float]]:
    if isinstance(value, dict):
        x = safe_float(value.get("x"), None)
        y = safe_float(value.get("y"), None)
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        x = safe_float(value[0], None)
        y = safe_float(value[1], None)
    else:
        return None
    if x is None or y is None or not isfinite(x) or not isfinite(y):
        return None
    return {"x": float(x), "y": float(y)}


def _points(values: Any) -> List[Dict[str, float]]:
    return [point for point in (_point(item) for item in safe_list(values)) if point is not None]


def _bbox_from_points(points: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
    if not points:
        return None
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)}


def _expand_bbox(bbox: Dict[str, float], amount: float) -> Dict[str, float]:
    return {
        "min_x": bbox["min_x"] - amount,
        "min_y": bbox["min_y"] - amount,
        "max_x": bbox["max_x"] + amount,
        "max_y": bbox["max_y"] + amount,
    }


def entity_bounding_box(entity: Dict[str, Any]) -> Optional[Dict[str, float]]:
    geometry = safe_dict(entity.get("geometry"))
    entity_type = safe_str(entity.get("type"))
    if entity_type == "line":
        bbox = _bbox_from_points([point for point in (_point(geometry.get("start")), _point(geometry.get("end"))) if point])
    elif entity_type in {"polyline", "polygon", "hatch"}:
        bbox = _bbox_from_points(_points(geometry.get("points") or geometry.get("vertices") or geometry.get("boundary")))
    elif entity_type == "rectangle":
        origin = _point(geometry.get("origin") or geometry.get("min"))
        width = safe_float(geometry.get("width"), None)
        height = safe_float(geometry.get("height"), None)
        if origin and width is not None and height is not None:
            bbox = _bbox_from_points([origin, {"x": origin["x"] + width, "y": origin["y"] + height}])
        else:
            bbox = _bbox_from_points(_points(geometry.get("points") or geometry.get("vertices")))
    elif entity_type in {"circle", "arc"}:
        center = _point(geometry.get("center"))
        radius = safe_float(geometry.get("radius"), None)
        bbox = _expand_bbox({"min_x": center["x"], "min_y": center["y"], "max_x": center["x"], "max_y": center["y"]}, radius) if center and radius and radius > 0 else None
    elif entity_type in {"text", "dimension", "block_reference", "underlay_reference"}:
        insert = _point(geometry.get("insert") or geometry.get("position") or geometry.get("origin"))
        width = abs(safe_float(geometry.get("width"), 0.0))
        height = abs(safe_float(geometry.get("height"), 0.0))
        bbox = _bbox_from_points([insert, {"x": insert["x"] + width, "y": insert["y"] + height}]) if insert else None
    else:
        bbox = None
    if bbox is None:
        return None
    bbox["width"] = bbox["max_x"] - bbox["min_x"]
    bbox["height"] = bbox["max_y"] - bbox["min_y"]
    return bbox


def hit_test_entities(entities: List[Dict[str, Any]], point: Dict[str, Any], *, tolerance: float = 2.0) -> List[str]:
    hit = _point(point)
    if hit is None:
        return []
    matches: List[str] = []
    for entity in entities:
        bbox = entity_bounding_box(entity)
        if not bbox:
            continue
        expanded = _expand_bbox(bbox, abs(tolerance))
        if expanded["min_x"] <= hit["x"] <= expanded["max_x"] and expanded["min_y"] <= hit["y"] <= expanded["max_y"]:
            matches.append(safe_str(entity.get("id")))
    return [item for item in matches if item]


def _orientation(a: Dict[str, float], b: Dict[str, float], c: Dict[str, float]) -> float:
    return (b["y"] - a["y"]) * (c["x"] - b["x"]) - (b["x"] - a["x"]) * (c["y"] - b["y"])


def _segments_intersect(a: Dict[str, float], b: Dict[str, float], c: Dict[str, float], d: Dict[str, float]) -> bool:
    return (_orientation(a, b, c) * _orientation(a, b, d) < 0) and (_orientation(c, d, a) * _orientation(c, d, b) < 0)


def _has_self_intersection(points: List[Dict[str, float]], *, closed: bool) -> bool:
    if len(points) < 4:
        return False
    segments = list(zip(points, points[1:]))
    if closed:
        segments.append((points[-1], points[0]))
    for i, (a, b) in enumerate(segments):
        for j, (c, d) in enumerate(segments):
            if abs(i - j) <= 1 or (closed and {i, j} == {0, len(segments) - 1}):
                continue
            if _segments_intersect(a, b, c, d):
                return True
    return False


def _source_confidence_blocker(entity: Dict[str, Any]) -> List[str]:
    confidence = safe_str(entity.get("source_confidence"))
    if confidence in LOW_CONFIDENCE_LABELS or "review_required" in confidence:
        return [f"source_confidence_blocker:{confidence or 'missing'}"]
    return []


def validate_cad_entity(entity: Dict[str, Any], *, known_layer_ids: Optional[Iterable[str]] = None, known_style_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    entity_id = safe_str(entity.get("id"))
    entity_type = safe_str(entity.get("type"))
    geometry = safe_dict(entity.get("geometry"))
    blockers: List[str] = []
    warnings: List[str] = []

    if not entity_id:
        blockers.append("missing_entity_id")
    if entity_type not in CAD_ENTITY_TYPES:
        blockers.append("unsupported_entity_type")
    if not geometry:
        blockers.append("invalid_geometry")

    layer_ids = set(known_layer_ids or [])
    style_ids = set(known_style_ids or [])
    if safe_str(entity.get("layer_id")) not in layer_ids:
        warnings.append("missing_layer_fallback_applied")
    if safe_str(entity.get("style_id")) not in style_ids:
        warnings.append("missing_style_fallback_applied")

    if entity_type == "line":
        if not _point(geometry.get("start")) or not _point(geometry.get("end")):
            blockers.append("invalid_geometry:line_requires_start_and_end")
    elif entity_type in {"polyline", "polygon", "hatch"}:
        points = _points(geometry.get("points") or geometry.get("vertices") or geometry.get("boundary"))
        min_points = 3 if entity_type in {"polygon", "hatch"} else 2
        if len(points) < min_points:
            blockers.append(f"invalid_geometry:{entity_type}_requires_{min_points}_points")
        if entity_type in {"polygon", "hatch"} and _has_self_intersection(points, closed=True):
            blockers.append("self_intersection")
        if entity_type == "polyline" and _has_self_intersection(points, closed=bool(geometry.get("closed"))):
            blockers.append("self_intersection")
    elif entity_type == "rectangle":
        if entity_bounding_box(entity) is None:
            blockers.append("invalid_geometry:rectangle_requires_origin_width_height_or_vertices")
    elif entity_type in {"circle", "arc"}:
        if not _point(geometry.get("center")) or safe_float(geometry.get("radius"), 0.0) <= 0:
            blockers.append(f"invalid_geometry:{entity_type}_requires_center_and_positive_radius")
    elif entity_type == "text":
        if not _point(geometry.get("insert") or geometry.get("position")) or not safe_str(geometry.get("text")):
            blockers.append("invalid_geometry:text_requires_insert_and_text")
    elif entity_type == "dimension":
        if len(_points(geometry.get("points"))) < 2 and not (_point(geometry.get("start")) and _point(geometry.get("end"))):
            blockers.append("invalid_geometry:dimension_requires_measurement_points")
    elif entity_type in {"block_reference", "underlay_reference"}:
        if not _point(geometry.get("insert") or geometry.get("origin")):
            blockers.append(f"invalid_geometry:{entity_type}_requires_insert")

    blockers.extend(_source_confidence_blocker(entity))
    if entity.get("construction_release_allowed") is not False:
        blockers.append("construction_release_blocked")
    if entity.get("draft_review_required") is not True:
        blockers.append("draft_review_required_missing")
    if safe_str(entity.get("review_status")) not in {"draft_review_required", "review_required", "imported_review_required", "stale", "invalid"}:
        warnings.append("review_status_normalized_to_draft_review_required")
    bbox = entity_bounding_box(entity)
    if bbox is None:
        blockers.append("invalid_geometry:no_bounding_box")
    return {
        "entity_id": entity_id,
        "valid": not blockers,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "bounding_box": bbox,
        "construction_release_allowed": False,
        "review_required": True,
    }


def _normalized_layer(layer: Dict[str, Any]) -> Dict[str, Any]:
    layer_id = safe_str(layer.get("id") or layer.get("layer_id"), CAD_DEFAULT_LAYER_ID)
    return {
        "id": layer_id,
        "name": safe_str(layer.get("name"), "Draft"),
        "visible": layer.get("visible") is not False,
        "locked": bool(layer.get("locked")),
        "source": safe_str(layer.get("source"), "cad_entity_model"),
        "review_only": True,
    }


def _normalized_style(style: Dict[str, Any]) -> Dict[str, Any]:
    style_id = safe_str(style.get("id") or style.get("style_id"), CAD_DEFAULT_STYLE_ID)
    return {
        "id": style_id,
        "name": safe_str(style.get("name"), "By Layer"),
        "source": safe_str(style.get("source"), "cad_entity_model"),
        "review_only": True,
    }


def normalize_cad_entity(raw_entity: Dict[str, Any], *, created_by: str = "system", updated_at: Optional[str] = None) -> Dict[str, Any]:
    rec = deepcopy(safe_dict(raw_entity))
    entity_type = safe_str(rec.get("type"))
    entity_id = safe_str(rec.get("id")) or _stable_id("cad", entity_type, rec.get("geometry"), rec.get("linked_object_id"))
    source = safe_str(rec.get("source"), "manual_drawn")
    review_status = safe_str(rec.get("review_status") or rec.get("status"), "draft_review_required")
    if review_status not in {"draft_review_required", "review_required", "imported_review_required", "stale", "invalid"}:
        review_status = "draft_review_required"
    rec.update(
        {
            "id": entity_id,
            "type": entity_type,
            "geometry": safe_dict(rec.get("geometry")),
            "layer_id": safe_str(rec.get("layer_id"), CAD_DEFAULT_LAYER_ID),
            "style_id": safe_str(rec.get("style_id"), CAD_DEFAULT_STYLE_ID),
            "source": source,
            "source_confidence": safe_str(rec.get("source_confidence"), "user-drawn" if source == "manual_drawn" else "imported CAD" if "import" in source or source in {"dxf", "pdf", "gis"} else "inferred"),
            "review_status": review_status,
            "draft_review_required": True,
            "construction_release_allowed": False,
            "created_by": safe_str(rec.get("created_by"), created_by or "system"),
            "updated_at": safe_str(rec.get("updated_at"), updated_at or now_iso()),
            "canonical_geometry_handoff": safe_dict(rec.get("canonical_geometry_handoff") or rec.get("canonical_geometry_handoff_v1")),
            "linked_object_id": safe_str(rec.get("linked_object_id") or rec.get("object_id")),
            "dirty": bool(rec.get("dirty")),
            "stale": bool(rec.get("stale")),
        }
    )
    return rec


def build_cad_entity_model(meta: Dict[str, Any], *, project_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source_model = safe_dict(meta.get(CAD_ENTITY_MODEL_VERSION) or meta.get("cad_entity_model") or {})
    layers = [_normalized_layer(item) for item in safe_list(source_model.get("layers")) if safe_dict(item)]
    styles = [_normalized_style(item) for item in safe_list(source_model.get("styles")) if safe_dict(item)]
    if not any(item["id"] == CAD_DEFAULT_LAYER_ID for item in layers):
        layers.insert(0, _normalized_layer({"id": CAD_DEFAULT_LAYER_ID, "name": "Draft"}))
    if not any(item["id"] == CAD_DEFAULT_STYLE_ID for item in styles):
        styles.insert(0, _normalized_style({"id": CAD_DEFAULT_STYLE_ID, "name": "By Layer"}))
    layer_ids = {item["id"] for item in layers}
    style_ids = {item["id"] for item in styles}
    entities = [normalize_cad_entity(item) for item in safe_list(source_model.get("entities")) if safe_dict(item)]
    validation = [validate_cad_entity(item, known_layer_ids=layer_ids, known_style_ids=style_ids) for item in entities]
    validation_by_id = {item["entity_id"]: item for item in validation}
    for entity in entities:
        result = safe_dict(validation_by_id.get(entity["id"]))
        entity["bounding_box"] = result.get("bounding_box")
        entity["validation_status"] = "valid" if result.get("valid") else "invalid"
        entity["validation_blockers"] = safe_list(result.get("blockers"))
        if entity["dirty"] or entity["stale"]:
            entity["review_status"] = "stale"
    selected_ids = _dedupe(source_model.get("selected_entity_ids") or [])
    history = []
    for item in safe_list(source_model.get("history")):
        rec = safe_dict(item)
        if safe_str(rec.get("action")) in CAD_HISTORY_ACTIONS:
            history.append(rec)
    invalid = [item for item in validation if not item.get("valid")]
    stale = [entity for entity in entities if entity.get("dirty") or entity.get("stale") or entity.get("review_status") == "stale"]
    blockers = []
    for item in invalid:
        for blocker in safe_list(item.get("blockers")):
            blockers.append({"entity_id": item.get("entity_id"), "reason": blocker})
    for entity in stale:
        blockers.append({"entity_id": entity.get("id"), "reason": "cad_entity_stale_or_dirty"})
    return {
        "version": CAD_ENTITY_MODEL_VERSION,
        "layers": layers,
        "styles": styles,
        "entities": entities,
        "selected_entity_ids": [entity_id for entity_id in selected_ids if entity_id in {entity["id"] for entity in entities}],
        "entity_bounding_boxes": {entity["id"]: entity.get("bounding_box") for entity in entities if entity.get("bounding_box")},
        "validation": {
            "valid": not blockers,
            "entity_count": len(entities),
            "invalid_count": len(invalid),
            "stale_or_dirty_count": len(stale),
            "entities": validation,
            "blockers": blockers,
            "construction_release_allowed": False,
        },
        "source_confidence": cad_source_confidence_summary(entities),
        "history": history,
        "selection": {
            "selected_entity_ids": [entity_id for entity_id in selected_ids if entity_id in {entity["id"] for entity in entities}],
            "hit_test_helper": "Use hit_test_entities with entity_bounding_boxes; this helper is bbox-based until grips/snaps add precise kernels.",
        },
        "issue_blockers": blockers,
        "review_only": True,
        "draft_review_required": True,
        "construction_release_allowed": False,
        "truth_label": "CAD entities are drafting/review objects only unless backed by accepted source evidence; Civora does not approve construction from CAD edits.",
    }


def attach_cad_entity_model_to_result(latest_result: Dict[str, Any], *, project_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result = deepcopy(safe_dict(latest_result))
    final_plan = safe_dict(result.get("final_plan"))
    if not final_plan:
        return result
    meta = safe_dict(final_plan.get("meta"))
    meta[CAD_ENTITY_MODEL_VERSION] = build_cad_entity_model(meta, project_input=project_input)
    final_plan["meta"] = meta
    result["final_plan"] = final_plan
    return result


def history_event(action: str, entity_id: str, *, actor: str = "system", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "action": action if action in CAD_HISTORY_ACTIONS else "entity_updated",
        "entity_id": entity_id,
        "actor": actor,
        "at": now_iso(),
        "details": deepcopy(details or {}),
        "review_only": True,
        "construction_release_allowed": False,
    }


def manual_drawn_objects_to_cad_entities(project_input: Dict[str, Any], latest_result: Optional[Dict[str, Any]] = None, *, created_by: str = "user") -> List[Dict[str, Any]]:
    latest_result = safe_dict(latest_result)
    manual = safe_dict(project_input.get("manual_fields"))
    handoffs = safe_list(manual.get("canonical_geometry_handoff_v1")) + safe_list(project_input.get("canonical_geometry_handoff_v1"))
    for source in (manual, project_input, safe_dict(safe_dict(latest_result.get("final_plan")).get("meta"))):
        for item in safe_list(safe_dict(source).get("site_objects")):
            handoff = safe_dict(safe_dict(item).get("canonical_geometry_handoff_v1"))
            if handoff:
                handoffs.append(handoff)
    entities: List[Dict[str, Any]] = []
    seen = set()
    for handoff in handoffs:
        rec = safe_dict(handoff)
        key = safe_str(rec.get("geometry_id") or rec.get("object_id"))
        if not key or key in seen:
            continue
        seen.add(key)
        geometry_type = safe_str(rec.get("geometry_type"), "polyline")
        vertices = _points(rec.get("vertices") or rec.get("points"))
        entity_type = "polygon" if geometry_type == "polygon" else "polyline" if geometry_type in {"polyline", "path"} else geometry_type
        geometry: Dict[str, Any]
        if entity_type == "line" and len(vertices) >= 2:
            geometry = {"start": vertices[0], "end": vertices[1], "units": safe_str(rec.get("units"), "ft")}
        elif entity_type in {"polygon", "polyline"}:
            geometry = {"points": vertices, "closed": entity_type == "polygon", "units": safe_str(rec.get("units"), "ft")}
        elif entity_type == "rectangle" and vertices:
            bbox = _bbox_from_points(vertices) or {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0}
            geometry = {"origin": {"x": bbox["min_x"], "y": bbox["min_y"]}, "width": bbox["max_x"] - bbox["min_x"], "height": bbox["max_y"] - bbox["min_y"], "units": safe_str(rec.get("units"), "ft")}
        else:
            entity_type = "polyline"
            geometry = {"points": vertices, "closed": False, "units": safe_str(rec.get("units"), "ft")}
        entities.append(
            normalize_cad_entity(
                {
                    "id": _stable_id("cad", "manual", key),
                    "type": entity_type,
                    "geometry": geometry,
                    "source": "manual_drawn",
                    "source_confidence": safe_str(rec.get("confidence"), "user_drawn_review_required"),
                    "review_status": "draft_review_required",
                    "canonical_geometry_handoff": rec,
                    "linked_object_id": safe_str(rec.get("object_id")),
                    "dirty": True,
                },
                created_by=created_by,
            )
        )
    return entities


def cad_entities_to_site_object_candidates(model: Dict[str, Any], *, requested_entity_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    requested = set(requested_entity_ids or [])
    candidates: List[Dict[str, Any]] = []
    for entity in safe_list(safe_dict(model).get("entities")):
        rec = safe_dict(entity)
        if requested and safe_str(rec.get("id")) not in requested:
            continue
        if rec.get("validation_status") == "invalid" or rec.get("type") not in {"polygon", "rectangle", "circle", "polyline"}:
            continue
        candidates.append(
            {
                "candidate_id": _stable_id("cadsite", rec.get("id")),
                "cad_entity_id": safe_str(rec.get("id")),
                "object_type": "draft_site_object_candidate",
                "geometry": deepcopy(safe_dict(rec.get("geometry"))),
                "source": "cad_entity",
                "source_confidence": safe_str(rec.get("source_confidence"), "user-drawn"),
                "review_status": "draft_review_required",
                "draft_review_required": True,
                "construction_release_allowed": False,
                "needs_user_acceptance": True,
                "truth_label": "Converted CAD geometry is a review-required site object candidate, not accepted engineering evidence.",
            }
        )
    return candidates


def import_candidates_to_cad_entities(candidates: List[Dict[str, Any]], *, source: str, created_by: str = "importer") -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        rec = safe_dict(candidate)
        entity_type = safe_str(rec.get("entity_type") or rec.get("type"), "underlay_reference")
        if entity_type not in CAD_ENTITY_TYPES:
            entity_type = "underlay_reference"
        entities.append(
            normalize_cad_entity(
                {
                    "id": safe_str(rec.get("id")) or _stable_id("cadimp", source, index, rec.get("geometry") or rec.get("file_name")),
                    "type": entity_type,
                    "geometry": safe_dict(rec.get("geometry")) or {"origin": {"x": 0.0, "y": 0.0}, "file_name": safe_str(rec.get("file_name") or rec.get("source_name"), source)},
                    "source": source,
                    "source_confidence": safe_str(rec.get("source_confidence"), "imported CAD" if "dxf" in source.lower() or "cad" in source.lower() else "GIS candidate" if "gis" in source.lower() else "metadata-only"),
                    "review_status": "imported_review_required",
                    "draft_review_required": True,
                    "dirty": True,
                },
                created_by=created_by,
            )
        )
    return entities


def cad_source_confidence_summary(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    blockers: List[Dict[str, Any]] = []
    for entity in entities:
        confidence = safe_str(safe_dict(entity).get("source_confidence"), "missing")
        counts[confidence] = counts.get(confidence, 0) + 1
        for blocker in _source_confidence_blocker(entity):
            blockers.append({"entity_id": safe_str(safe_dict(entity).get("id")), "reason": blocker})
    return {
        "entity_count": len(entities),
        "counts_by_source_confidence": counts,
        "blockers": blockers,
        "construction_release_allowed": False,
        "truth_label": "CAD entity source confidence explains drafting evidence only; it does not make CAD geometry survey-backed or construction-ready.",
    }


__all__ = [
    "CAD_ENTITY_MODEL_VERSION",
    "CAD_ENTITY_TYPES",
    "attach_cad_entity_model_to_result",
    "build_cad_entity_model",
    "cad_entities_to_site_object_candidates",
    "cad_source_confidence_summary",
    "entity_bounding_box",
    "history_event",
    "hit_test_entities",
    "import_candidates_to_cad_entities",
    "manual_drawn_objects_to_cad_entities",
    "normalize_cad_entity",
    "validate_cad_entity",
]
