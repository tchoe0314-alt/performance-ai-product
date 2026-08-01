from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from math import atan2, cos, degrees, hypot, isfinite, radians, sin
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .common import safe_dict, safe_float, safe_list, safe_str


CAD_ENTITY_MODEL_VERSION = "cad_entity_model_v1"
CAD_DEFAULT_LAYER_ID = "layer_draft"
CAD_DEFAULT_STYLE_ID = "style_by_layer"
CAD_LAYER_LOCK_BLOCKER_PREFIX = "locked_layer_prevents_cad_entity_edit"
CAD_ENTITY_TYPES = {
    "line",
    "polyline",
    "polygon",
    "rectangle",
    "circle",
    "arc",
    "text",
    "dimension",
    "leader",
    "callout",
    "note",
    "label",
    "hatch",
    "hatch_reference",
    "block_reference",
    "underlay_reference",
}
CAD_HISTORY_ACTIONS = {
    "entity_created",
    "entity_updated",
    "entity_deleted",
    "entity_restored",
    "entity_converted",
    "entity_imported",
    "entity_layer_changed",
    "entity_style_changed",
    "entity_geometry_changed",
    "entity_attribute_changed",
    "entity_association_updated",
}
CAD_ENTITY_CHAT_OPERATION_VERSION = "cad_entity_chat_operation_v1"
CAD_ENGINEERING_OBJECTS_VERSION = "cad_engineering_objects_v1"
LOW_CONFIDENCE_LABELS = {"", "missing", "metadata-only", "metadata_only", "inferred", "GIS candidate", "map imagery candidate"}
PDF_SOURCE_CONFIDENCE = "imported_pdf_review_required"
AREA_ENGINEERING_OBJECT_TYPES = {
    "building",
    "parking_area",
    "basin",
    "pavement",
    "sidewalk",
    "landscape_area",
    "property_area",
    "drainage_area",
    "utility_easement",
    "custom_area",
}
PATH_ENGINEERING_OBJECT_TYPES = {
    "road_centerline",
    "driveway",
    "sidewalk_path",
    "storm_main",
    "water_main",
    "sanitary_main",
    "force_main",
    "swale",
    "ditch",
    "retaining_wall",
    "fence",
    "property_line",
    "utility_corridor",
    "custom_path",
}
POINT_ENGINEERING_OBJECT_TYPES = {
    "inlet",
    "manhole",
    "hydrant",
    "outfall",
    "cleanout",
    "utility_pole",
    "survey_point",
    "benchmark",
    "structure",
    "custom_point",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(prefix: str, *parts: Any) -> str:
    seed = "|".join(safe_str(part) for part in parts if safe_str(part))
    if not seed:
        seed = f"{prefix}|cad"
    return f"{prefix}_{hashlib.sha1(seed.encode('utf-8'), usedforsecurity=False).hexdigest()[:12]}"


def _dedupe(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = safe_str(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _summarize_entity(entity: Any) -> Dict[str, Any]:
    rec = safe_dict(entity)
    if not rec:
        return {}
    geometry = safe_dict(rec.get("geometry"))
    return {
        "id": safe_str(rec.get("id")),
        "type": safe_str(rec.get("type")),
        "layer_id": safe_str(rec.get("layer_id")),
        "style_id": safe_str(rec.get("style_id")),
        "source": safe_str(rec.get("source")),
        "source_confidence": safe_str(rec.get("source_confidence")),
        "review_status": safe_str(rec.get("review_status")),
        "dirty": bool(rec.get("dirty")),
        "stale": bool(rec.get("stale")),
        "geometry_keys": sorted([safe_str(key) for key in geometry.keys() if safe_str(key)]),
        "construction_release_allowed": False,
    }


def _polygon_area(points: List[Dict[str, float]]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point["x"] * nxt["y"] - nxt["x"] * point["y"]
    return abs(total) / 2.0


def _changed_fields(before: Any, after: Any) -> List[str]:
    before_rec = safe_dict(before)
    after_rec = safe_dict(after)
    keys = set(before_rec.keys()) | set(after_rec.keys())
    return sorted(
        key
        for key in keys
        if before_rec.get(key) != after_rec.get(key)
        and key not in {"updated_at", "bounding_box", "validation_blockers", "validation_status"}
    )


def _normalize_history_event(raw_event: Dict[str, Any], *, index: int = 0) -> Dict[str, Any]:
    rec = deepcopy(safe_dict(raw_event))
    event_type = safe_str(rec.get("event_type") or rec.get("action"), "entity_updated")
    if event_type not in CAD_HISTORY_ACTIONS:
        event_type = "entity_updated"
    entity_id = safe_str(rec.get("entity_id"))
    timestamp = safe_str(rec.get("timestamp") or rec.get("at"), now_iso())
    actor = safe_str(rec.get("actor") or rec.get("source"), "system")
    before = rec.get("before_summary")
    if before is None:
        before = rec.get("before")
    after = rec.get("after_summary")
    if after is None:
        after = rec.get("after")
    changed = _dedupe(rec.get("changed_fields") or safe_dict(rec.get("details")).get("changed_fields") or _changed_fields(before, after))
    event_id = safe_str(rec.get("event_id")) or _stable_id("cadevt", event_type, entity_id, timestamp, actor, index)
    return {
        "event_id": event_id,
        "entity_id": entity_id,
        "event_type": event_type,
        "action": event_type,
        "timestamp": timestamp,
        "at": timestamp,
        "actor": actor,
        "source": actor,
        "before_summary": _summarize_entity(before) if safe_dict(before) else safe_dict(before),
        "after_summary": _summarize_entity(after) if safe_dict(after) else safe_dict(after),
        "changed_fields": changed,
        "details": deepcopy(safe_dict(rec.get("details"))),
        "review_required": True,
        "review_only": True,
        "construction_release_allowed": False,
    }


def _normalize_history_snapshots(source_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []
    for index, item in enumerate(safe_list(source_model.get("history_snapshots") or source_model.get("undo_snapshots"))):
        rec = safe_dict(item)
        if not rec:
            continue
        snapshot_id = safe_str(rec.get("snapshot_id")) or _stable_id("cadsnap", rec.get("revision_id"), index)
        snapshots.append(
            {
                "snapshot_id": snapshot_id,
                "revision_id": safe_str(rec.get("revision_id"), snapshot_id),
                "timestamp": safe_str(rec.get("timestamp") or rec.get("at"), now_iso()),
                "actor": safe_str(rec.get("actor") or rec.get("source"), "system"),
                "entity_count": len(safe_list(rec.get("entities"))),
                "entities": deepcopy(safe_list(rec.get("entities"))),
                "layers": deepcopy(safe_list(rec.get("layers"))),
                "styles": deepcopy(safe_list(rec.get("styles"))),
                "review_required": True,
                "construction_release_allowed": False,
            }
        )
    return snapshots[-25:]


def build_cad_history_snapshot(model: Dict[str, Any], *, actor: str = "system", revision_id: Optional[str] = None) -> Dict[str, Any]:
    rec = safe_dict(model)
    timestamp = now_iso()
    snapshot_revision = safe_str(revision_id) or _stable_id("cadrev", timestamp, len(safe_list(rec.get("entities"))))
    return {
        "snapshot_id": _stable_id("cadsnap", snapshot_revision, timestamp, actor),
        "revision_id": snapshot_revision,
        "timestamp": timestamp,
        "actor": safe_str(actor, "system"),
        "entities": deepcopy(safe_list(rec.get("entities"))),
        "layers": deepcopy(safe_list(rec.get("layers"))),
        "styles": deepcopy(safe_list(rec.get("styles"))),
        "review_required": True,
        "construction_release_allowed": False,
    }


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


def _distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    return hypot(b["x"] - a["x"], b["y"] - a["y"])


def _angle_degrees(a: Dict[str, float], b: Dict[str, float], c: Dict[str, float]) -> float:
    v1 = atan2(a["y"] - b["y"], a["x"] - b["x"])
    v2 = atan2(c["y"] - b["y"], c["x"] - b["x"])
    angle = abs(degrees(v2 - v1)) % 360.0
    return 360.0 - angle if angle > 180.0 else angle


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
    elif entity_type in {"polyline", "polygon", "hatch", "hatch_reference"}:
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
    elif entity_type in {"text", "dimension", "leader", "callout", "note", "label", "block_reference", "underlay_reference"}:
        insert = _point(geometry.get("insert") or geometry.get("position") or geometry.get("origin"))
        width = abs(safe_float(geometry.get("width"), 0.0))
        height = abs(safe_float(geometry.get("height"), 0.0))
        leader_points = _points(geometry.get("points") or geometry.get("leader_points"))
        if entity_type in {"dimension", "leader", "callout"} and leader_points:
            bbox = _bbox_from_points(leader_points + ([insert] if insert else []))
        else:
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


def _bbox_intersects(a: Dict[str, float], b: Dict[str, float]) -> bool:
    return not (a["max_x"] < b["min_x"] or a["min_x"] > b["max_x"] or a["max_y"] < b["min_y"] or a["min_y"] > b["max_y"])


def window_select_entities(entities: List[Dict[str, Any]], window: Dict[str, Any]) -> List[str]:
    p1 = _point(window.get("start") or window.get("min") or window.get("p1"))
    p2 = _point(window.get("end") or window.get("max") or window.get("p2"))
    if p1 is None or p2 is None:
        return []
    selection_box = {
        "min_x": min(p1["x"], p2["x"]),
        "min_y": min(p1["y"], p2["y"]),
        "max_x": max(p1["x"], p2["x"]),
        "max_y": max(p1["y"], p2["y"]),
    }
    matches: List[str] = []
    for entity in entities:
        bbox = entity_bounding_box(entity)
        entity_id = safe_str(entity.get("id"))
        if bbox and entity_id and _bbox_intersects(selection_box, bbox):
            matches.append(entity_id)
    return matches


def _grip(grip_id: str, kind: str, point: Dict[str, float], *, label: str = "", index: Optional[int] = None) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "grip_id": grip_id,
        "kind": kind,
        "point": {"x": float(point["x"]), "y": float(point["y"])},
        "label": label or grip_id,
    }
    if index is not None:
        rec["index"] = index
    return rec


def entity_grip_points(entity: Dict[str, Any]) -> List[Dict[str, Any]]:
    geometry = safe_dict(entity.get("geometry"))
    entity_type = safe_str(entity.get("type"))
    grips: List[Dict[str, Any]] = []
    if entity_type == "line":
        start = _point(geometry.get("start"))
        end = _point(geometry.get("end"))
        if start and end:
            grips.append(_grip("start", "line_endpoint", start, label="start"))
            grips.append(_grip("end", "line_endpoint", end, label="end"))
            grips.append(_grip("midpoint", "line_midpoint", {"x": (start["x"] + end["x"]) / 2, "y": (start["y"] + end["y"]) / 2}, label="midpoint"))
    elif entity_type in {"polyline", "polygon", "hatch"}:
        for index, point in enumerate(_points(geometry.get("points") or geometry.get("vertices") or geometry.get("boundary"))):
            grips.append(_grip(f"vertex:{index}", f"{entity_type}_vertex", point, label=f"vertex {index + 1}", index=index))
    elif entity_type == "rectangle":
        bbox = entity_bounding_box(entity)
        if bbox:
            corners = [("corner:nw", {"x": bbox["min_x"], "y": bbox["min_y"]}), ("corner:ne", {"x": bbox["max_x"], "y": bbox["min_y"]}), ("corner:se", {"x": bbox["max_x"], "y": bbox["max_y"]}), ("corner:sw", {"x": bbox["min_x"], "y": bbox["max_y"]})]
            edges = [("edge:n", {"x": (bbox["min_x"] + bbox["max_x"]) / 2, "y": bbox["min_y"]}), ("edge:e", {"x": bbox["max_x"], "y": (bbox["min_y"] + bbox["max_y"]) / 2}), ("edge:s", {"x": (bbox["min_x"] + bbox["max_x"]) / 2, "y": bbox["max_y"]}), ("edge:w", {"x": bbox["min_x"], "y": (bbox["min_y"] + bbox["max_y"]) / 2})]
            for grip_id, point in corners:
                grips.append(_grip(grip_id, "rectangle_corner", point, label=grip_id.replace(":", " ")))
            for grip_id, point in edges:
                grips.append(_grip(grip_id, "rectangle_edge", point, label=grip_id.replace(":", " ")))
    elif entity_type == "circle":
        center = _point(geometry.get("center"))
        radius = safe_float(geometry.get("radius"), None)
        if center and radius and radius > 0:
            grips.append(_grip("center", "circle_center", center, label="center"))
            grips.append(_grip("radius:e", "circle_radius", {"x": center["x"] + radius, "y": center["y"]}, label="radius"))
    elif entity_type == "text":
        insert = _point(geometry.get("insert") or geometry.get("position"))
        if insert:
            grips.append(_grip("insert", "text_insertion", insert, label="insertion point"))
    elif entity_type == "dimension":
        start = _point(geometry.get("start"))
        end = _point(geometry.get("end"))
        points = _points(geometry.get("points"))
        if not start and len(points) >= 1:
            start = points[0]
        if not end and len(points) >= 2:
            end = points[1]
        if start:
            grips.append(_grip("start", "dimension_endpoint", start, label="start"))
        if end:
            grips.append(_grip("end", "dimension_endpoint", end, label="end"))
    elif entity_type == "block_reference":
        insert = _point(geometry.get("insert") or geometry.get("origin"))
        if insert:
            grips.append(_grip("insert", "block_insertion", insert, label="insertion point"))
    return [{"entity_id": safe_str(entity.get("id")), **item} for item in grips]


def selected_entity_grips(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    selected = set(_dedupe(safe_dict(model).get("selected_entity_ids") or safe_dict(safe_dict(model).get("selection")).get("selected_entity_ids") or []))
    grips: List[Dict[str, Any]] = []
    for entity in safe_list(safe_dict(model).get("entities")):
        rec = safe_dict(entity)
        if safe_str(rec.get("id")) in selected:
            grips.extend(entity_grip_points(rec))
    return grips


def _edit_blocker(entity: Dict[str, Any]) -> str:
    entity_type = safe_str(entity.get("type"))
    if bool(entity.get("locked")) or entity_type == "underlay_reference" or safe_str(entity.get("source")) in {"reference", "underlay", "external_reference"}:
        return "locked/reference/underlay entity"
    if entity_type not in {"line", "polyline", "polygon", "rectangle", "circle", "text", "dimension", "leader", "callout", "note", "label", "block_reference"}:
        return "unsupported entity type"
    return ""


def _normalized_edit_blockers(entity: Dict[str, Any]) -> List[str]:
    result = validate_cad_entity(entity, known_layer_ids=[safe_str(entity.get("layer_id"), CAD_DEFAULT_LAYER_ID)], known_style_ids=[safe_str(entity.get("style_id"), CAD_DEFAULT_STYLE_ID)])
    blockers: List[str] = []
    for blocker in safe_list(result.get("blockers")):
        reason = safe_str(blocker)
        if reason == "self_intersection":
            blockers.append("self-intersection")
        elif reason.startswith("invalid_geometry") or reason in {"missing_entity_id", "unsupported_entity_type"}:
            blockers.append("invalid geometry")
    return _dedupe(blockers)


def _geometry_points_key(geometry: Dict[str, Any]) -> str:
    for key in ("points", "vertices", "boundary"):
        if key in geometry:
            return key
    return "points"


def _move_entity_grip(entity: Dict[str, Any], grip_id: str, new_point: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    target = _point(new_point)
    if target is None:
        return None, ["invalid geometry"]
    edit_blocker = _edit_blocker(entity)
    if edit_blocker:
        return None, [edit_blocker]
    geometry = deepcopy(safe_dict(entity.get("geometry")))
    entity_type = safe_str(entity.get("type"))
    before_grips = {safe_str(item.get("grip_id")): item for item in entity_grip_points(entity)}
    active_grip = safe_dict(before_grips.get(grip_id))
    if not active_grip:
        return None, ["unsupported entity type"]
    current = _point(active_grip.get("point")) or target
    delta = {"x": target["x"] - current["x"], "y": target["y"] - current["y"]}
    if entity_type == "line":
        if grip_id in {"start", "end"}:
            geometry[grip_id] = target
        elif grip_id == "midpoint":
            geometry = _transform_geometry(geometry, dx=delta["x"], dy=delta["y"])
        else:
            return None, ["unsupported entity type"]
    elif entity_type in {"polyline", "polygon"}:
        index = safe_dict(active_grip).get("index")
        if not isinstance(index, int):
            return None, ["unsupported entity type"]
        key = _geometry_points_key(geometry)
        points = _points(geometry.get(key))
        if index < 0 or index >= len(points):
            return None, ["invalid geometry"]
        points[index] = target
        geometry[key] = points
    elif entity_type == "rectangle":
        bbox = entity_bounding_box(entity)
        if not bbox:
            return None, ["invalid geometry"]
        min_x, min_y, max_x, max_y = bbox["min_x"], bbox["min_y"], bbox["max_x"], bbox["max_y"]
        if grip_id == "corner:nw":
            min_x, min_y = target["x"], target["y"]
        elif grip_id == "corner:ne":
            max_x, min_y = target["x"], target["y"]
        elif grip_id == "corner:se":
            max_x, max_y = target["x"], target["y"]
        elif grip_id == "corner:sw":
            min_x, max_y = target["x"], target["y"]
        elif grip_id == "edge:n":
            min_y = target["y"]
        elif grip_id == "edge:e":
            max_x = target["x"]
        elif grip_id == "edge:s":
            max_y = target["y"]
        elif grip_id == "edge:w":
            min_x = target["x"]
        else:
            return None, ["unsupported entity type"]
        width = max_x - min_x
        height = max_y - min_y
        if abs(width) <= 0.000001 or abs(height) <= 0.000001:
            return None, ["invalid geometry"]
        geometry = {**geometry, "origin": {"x": min(min_x, max_x), "y": min(min_y, max_y)}, "width": abs(width), "height": abs(height)}
        geometry.pop("points", None)
        geometry.pop("vertices", None)
    elif entity_type == "circle":
        center = _point(geometry.get("center"))
        if grip_id == "center":
            geometry["center"] = target
        elif grip_id.startswith("radius") and center:
            radius = ((target["x"] - center["x"]) ** 2 + (target["y"] - center["y"]) ** 2) ** 0.5
            if radius <= 0.000001:
                return None, ["invalid geometry"]
            geometry["radius"] = radius
        else:
            return None, ["unsupported entity type"]
    elif entity_type == "text":
        key = "insert" if "insert" in geometry else "position"
        geometry[key] = target
    elif entity_type == "dimension":
        if grip_id not in {"start", "end"}:
            return None, ["unsupported entity type"]
        geometry[grip_id] = target
        points = _points(geometry.get("points"))
        if len(points) >= 2:
            points[0 if grip_id == "start" else 1] = target
            geometry["points"] = points
    elif entity_type == "block_reference":
        key = "insert" if "insert" in geometry else "origin"
        geometry[key] = target
    else:
        return None, ["unsupported entity type"]
    updated = normalize_cad_entity({**deepcopy(entity), "geometry": geometry, "dirty": True, "stale": True, "review_status": "draft_review_required", "draft_review_required": True, "construction_release_allowed": False}, created_by=safe_str(entity.get("created_by"), "user"))
    blockers = _normalized_edit_blockers(updated)
    if blockers:
        return None, blockers
    return updated, []


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
    elif entity_type in {"polyline", "polygon", "hatch", "hatch_reference"}:
        points = _points(geometry.get("points") or geometry.get("vertices") or geometry.get("boundary"))
        min_points = 3 if entity_type in {"polygon", "hatch", "hatch_reference"} else 2
        if len(points) < min_points:
            blockers.append(f"invalid_geometry:{entity_type}_requires_{min_points}_points")
        if entity_type in {"polygon", "hatch", "hatch_reference"} and _has_self_intersection(points, closed=True):
            blockers.append("self_intersection")
        if entity_type == "polyline" and _has_self_intersection(points, closed=bool(geometry.get("closed"))):
            blockers.append("self_intersection")
    elif entity_type == "rectangle":
        if entity_bounding_box(entity) is None:
            blockers.append("invalid_geometry:rectangle_requires_origin_width_height_or_vertices")
    elif entity_type in {"circle", "arc"}:
        if not _point(geometry.get("center")) or safe_float(geometry.get("radius"), 0.0) <= 0:
            blockers.append(f"invalid_geometry:{entity_type}_requires_center_and_positive_radius")
    elif entity_type in {"text", "note", "label"}:
        if not _point(geometry.get("insert") or geometry.get("position")) or not safe_str(geometry.get("text")):
            blockers.append(f"invalid_geometry:{entity_type}_requires_insert_and_text")
    elif entity_type in {"leader", "callout"}:
        if len(_points(geometry.get("points") or geometry.get("leader_points"))) < 2 or not safe_str(geometry.get("text")):
            blockers.append(f"invalid_geometry:{entity_type}_requires_leader_points_and_text")
    elif entity_type == "dimension":
        measurement = safe_dict(entity.get("dimension"))
        if len(_points(geometry.get("points"))) < 2 and not (_point(geometry.get("start")) and _point(geometry.get("end"))):
            blockers.append("invalid_geometry:dimension_requires_measurement_points")
        if safe_str(measurement.get("dimension_type")) not in {"linear", "aligned", "angular", "radius", "diameter"}:
            blockers.append("invalid_dimension_type")
        if measurement.get("measurement_value") is None:
            blockers.append("missing_dimension_measurement_value")
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


def _entity_segments_for_combine(entity: Dict[str, Any]) -> Tuple[List[Tuple[Dict[str, float], Dict[str, float]]], List[str]]:
    rec = safe_dict(entity)
    entity_type = safe_str(rec.get("type"))
    geometry = safe_dict(rec.get("geometry"))
    if _edit_blocker(rec):
        return [], [_edit_blocker(rec)]
    if entity_type == "line":
        start = _point(geometry.get("start"))
        end = _point(geometry.get("end"))
        if not start or not end:
            return [], ["invalid_geometry:line_requires_start_and_end"]
        return [(start, end)], []
    if entity_type == "rectangle":
        bbox = entity_bounding_box(rec)
        if not bbox:
            return [], ["invalid_geometry:rectangle_requires_origin_width_height_or_vertices"]
        points = [
            {"x": bbox["min_x"], "y": bbox["min_y"]},
            {"x": bbox["max_x"], "y": bbox["min_y"]},
            {"x": bbox["max_x"], "y": bbox["max_y"]},
            {"x": bbox["min_x"], "y": bbox["max_y"]},
        ]
        return list(zip(points, points[1:] + [points[0]])), []
    if entity_type in {"polyline", "polygon"}:
        points = _points(geometry.get("points") or geometry.get("vertices") or geometry.get("boundary"))
        if len(points) < 2:
            return [], [f"invalid_geometry:{entity_type}_requires_points"]
        closed = entity_type == "polygon" or bool(geometry.get("closed")) or _distance(points[0], points[-1]) <= 0.000001
        clean_points = points[:-1] if len(points) > 2 and _distance(points[0], points[-1]) <= 0.000001 else points
        if entity_type == "polygon" and len(clean_points) < 3:
            return [], ["invalid_geometry:polygon_requires_3_points"]
        segments = list(zip(clean_points, clean_points[1:]))
        if closed:
            segments.append((clean_points[-1], clean_points[0]))
        return segments, []
    return [], [f"unsupported_combine_entity_type:{entity_type}"]


def _segment_key(a: Dict[str, float], b: Dict[str, float], tolerance: float) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    scale = 1.0 / max(abs(tolerance), 0.000001)
    p1 = (round(a["x"] * scale), round(a["y"] * scale))
    p2 = (round(b["x"] * scale), round(b["y"] * scale))
    return tuple(sorted([p1, p2]))  # type: ignore[return-value]


def _ordered_closed_loop(
    segments: List[Tuple[Dict[str, float], Dict[str, float]]],
    *,
    tolerance: float,
    close_gaps: bool,
) -> Tuple[List[Dict[str, float]], List[str], List[Dict[str, Any]]]:
    if len(segments) < 3:
        return [], ["Select at least three connected segments to create an area."], []
    seen_segments = set()
    duplicate_count = 0
    for start, end in segments:
        key = _segment_key(start, end, tolerance)
        if key in seen_segments:
            duplicate_count += 1
        seen_segments.add(key)
    if duplicate_count:
        return [], ["Duplicate segments conflict with the selected loop."], [{"action": "remove_duplicate_segment"}]

    remaining = [(deepcopy(a), deepcopy(b)) for a, b in segments]
    first_start, first_end = remaining.pop(0)
    ordered = [first_start, first_end]
    corrections: List[Dict[str, Any]] = []
    max_gap = 0.0
    while remaining:
        current = ordered[-1]
        best_index = -1
        best_reverse = False
        best_gap = float("inf")
        for index, (start, end) in enumerate(remaining):
            start_gap = _distance(current, start)
            end_gap = _distance(current, end)
            if start_gap < best_gap:
                best_index = index
                best_reverse = False
                best_gap = start_gap
            if end_gap < best_gap:
                best_index = index
                best_reverse = True
                best_gap = end_gap
        if best_index < 0:
            return [], ["Select one connected set of lines."], []
        if best_gap > tolerance:
            return [], [f"Two endpoints do not meet. Gap is {best_gap:.2f} ft."], [{"action": "select_connected_geometry"}]
        start, end = remaining.pop(best_index)
        next_point = start if best_reverse else end
        if best_gap > 0.000001:
            max_gap = max(max_gap, best_gap)
            corrections.append({"action": "snap_endpoints", "gap_ft": round(best_gap, 3)})
            if close_gaps:
                current["x"] = (current["x"] + (end if best_reverse else start)["x"]) / 2.0
                current["y"] = (current["y"] + (end if best_reverse else start)["y"]) / 2.0
        ordered.append(deepcopy(next_point))

    close_gap = _distance(ordered[-1], ordered[0])
    if close_gap > tolerance:
        return [], [f"Shape is not closed. Final gap is {close_gap:.2f} ft."], [{"action": "close_gap"}]
    if close_gap > 0.000001:
        max_gap = max(max_gap, close_gap)
        corrections.append({"action": "close_gap", "gap_ft": round(close_gap, 3)})
        if close_gaps:
            ordered[-1] = deepcopy(ordered[0])
    if max_gap > 0.000001 and not close_gaps:
        return [], [f"Small gap requires permission before snapping endpoints. Largest gap is {max_gap:.2f} ft."], corrections
    loop = ordered[:-1] if len(ordered) > 3 and _distance(ordered[0], ordered[-1]) <= tolerance else ordered
    if len(loop) < 3:
        return [], ["Selected geometry does not form an area."], []
    if _has_self_intersection(loop, closed=True):
        return [], ["The selected shape crosses itself."], [{"action": "show_conflict"}]
    return loop, [], corrections


def validate_closed_geometry(
    entities: List[Dict[str, Any]],
    entity_ids: Iterable[Any],
    *,
    tolerance: float = 0.25,
    close_gaps: bool = False,
) -> Dict[str, Any]:
    requested_ids = _dedupe(entity_ids)
    by_id = {safe_str(entity.get("id")): normalize_cad_entity(entity) for entity in entities if safe_str(safe_dict(entity).get("id"))}
    selected = [by_id[entity_id] for entity_id in requested_ids if entity_id in by_id]
    missing = [entity_id for entity_id in requested_ids if entity_id not in by_id]
    blockers: List[str] = []
    suggested_actions: List[Dict[str, Any]] = []
    if missing:
        blockers.append("Selected geometry is missing: " + ", ".join(missing))
    if len(selected) < 1:
        blockers.append("Select linework before combining.")
    segments: List[Tuple[Dict[str, float], Dict[str, float]]] = []
    for entity in selected:
        entity_segments, entity_blockers = _entity_segments_for_combine(entity)
        segments.extend(entity_segments)
        blockers.extend(entity_blockers)
    if blockers:
        return {
            "version": "semantic_geometry_validation_v1",
            "valid": False,
            "geometry_kind": "area",
            "selected_entity_ids": requested_ids,
            "blockers": _dedupe(blockers),
            "suggested_actions": suggested_actions,
            "review_required": True,
            "construction_release_allowed": False,
        }
    loop, loop_blockers, corrections = _ordered_closed_loop(segments, tolerance=abs(tolerance), close_gaps=close_gaps)
    suggested_actions.extend(corrections)
    bbox = _bbox_from_points(loop)
    return {
        "version": "semantic_geometry_validation_v1",
        "valid": not loop_blockers,
        "geometry_kind": "area",
        "selected_entity_ids": requested_ids,
        "point_count": len(loop),
        "points": loop,
        "area_sf": round(_polygon_area(loop), 3),
        "bounding_box": bbox,
        "blockers": _dedupe(loop_blockers),
        "suggested_actions": suggested_actions,
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": "Closed geometry validation proves drafting topology only; it is not survey or engineering approval evidence.",
    }


def _engineering_object_defaults(object_type: str, geometry_kind: str) -> Dict[str, Any]:
    affected = {
        "building": ["parking", "drainage", "water", "sanitary", "grading", "quantities", "review_package"],
        "parking_area": ["parking", "drainage", "grading", "quantities", "review_package"],
        "basin": ["drainage", "grading", "storm", "quantities", "review_package"],
        "driveway": ["roadway", "drainage", "grading", "quantities", "review_package"],
        "storm_main": ["storm", "drainage", "coordination", "review_package"],
        "water_main": ["water", "coordination", "review_package"],
        "sanitary_main": ["sanitary", "coordination", "review_package"],
    }.get(object_type, ["quantities", "review_package"])
    return {
        "geometry_kind": geometry_kind,
        "affected_systems": affected,
        "missing_inputs": ["qualified review"],
        "assumptions": [],
        "standards_references": [],
        "relationships": [],
        "dependencies": [{"system": system, "status": "affected_by_object_geometry"} for system in affected],
    }


def normalize_engineering_object(raw_object: Dict[str, Any]) -> Dict[str, Any]:
    rec = deepcopy(safe_dict(raw_object))
    object_type = safe_str(rec.get("object_type") or rec.get("type"), "custom_area")
    geometry_kind = safe_str(rec.get("geometry_kind"), "area")
    defaults = _engineering_object_defaults(object_type, geometry_kind)
    object_id = safe_str(rec.get("object_id") or rec.get("id")) or _stable_id("engobj", object_type, rec.get("geometry_entity_id"), rec.get("display_name"))
    return {
        "object_id": object_id,
        "id": object_id,
        "object_type": object_type,
        "display_name": safe_str(rec.get("display_name") or rec.get("name"), object_type.replace("_", " ").title()),
        "geometry_kind": geometry_kind,
        "geometry_entity_id": safe_str(rec.get("geometry_entity_id")),
        "source_entity_ids": _dedupe(rec.get("source_entity_ids") or []),
        "source": safe_str(rec.get("source"), "converted_from_draft_geometry"),
        "source_confidence": safe_str(rec.get("source_confidence"), "user_drawn_review_required"),
        "creation_method": safe_str(rec.get("creation_method"), "semantic_conversion"),
        "engineering_attributes": deepcopy(safe_dict(rec.get("engineering_attributes"))),
        "relationships": deepcopy(safe_list(rec.get("relationships") or defaults["relationships"])),
        "dependencies": deepcopy(safe_list(rec.get("dependencies") or defaults["dependencies"])),
        "affected_systems": _dedupe(rec.get("affected_systems") or defaults["affected_systems"]),
        "assumptions": deepcopy(safe_list(rec.get("assumptions") or defaults["assumptions"])),
        "missing_inputs": _dedupe(rec.get("missing_inputs") or defaults["missing_inputs"]),
        "standards_references": deepcopy(safe_list(rec.get("standards_references") or defaults["standards_references"])),
        "export_mapping": deepcopy(safe_dict(rec.get("export_mapping"))) or {
            "dxf_layer": f"C-{object_type.upper().replace('_', '-')}",
            "review_package_section": object_type,
        },
        "visibility_state": safe_str(rec.get("visibility_state"), "visible"),
        "review_status": safe_str(rec.get("review_status"), "needs_review"),
        "review_required": True,
        "construction_release_allowed": False,
        "history": deepcopy(safe_list(rec.get("history"))),
        "truth_label": "Converted engineering objects carry project meaning for review workflows, but still require qualified review before reliance.",
    }


def _source_engineering_objects(source_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = source_model.get(CAD_ENGINEERING_OBJECTS_VERSION)
    if isinstance(raw, dict):
        raw_items = safe_list(raw.get("objects"))
    else:
        raw_items = safe_list(raw)
    raw_items += safe_list(source_model.get("engineering_objects"))
    objects: List[Dict[str, Any]] = []
    seen = set()
    for item in raw_items:
        rec = normalize_engineering_object(safe_dict(item))
        object_id = safe_str(rec.get("object_id"))
        if object_id and object_id not in seen:
            seen.add(object_id)
            objects.append(rec)
    return objects


def _normalized_layer(layer: Dict[str, Any]) -> Dict[str, Any]:
    layer_id = safe_str(layer.get("id") or layer.get("layer_id"), CAD_DEFAULT_LAYER_ID)
    source = safe_str(layer.get("source") or layer.get("template_source") or layer.get("source_reference"), "cad_entity_model")
    template_trace = safe_dict(layer.get("template_trace"))
    if not template_trace and (layer.get("template_id") or layer.get("source_reference")):
        template_trace = {
            "template_id": safe_str(layer.get("template_id")),
            "source_reference": safe_str(layer.get("source_reference")),
        }
    return {
        "id": layer_id,
        "layer_id": layer_id,
        "name": safe_str(layer.get("name"), "Draft"),
        "color": safe_str(layer.get("color"), "#ffffff"),
        "linetype": safe_str(layer.get("linetype"), "CONTINUOUS"),
        "lineweight": safe_str(layer.get("lineweight"), "0.18mm"),
        "visible": layer.get("visible") is not False,
        "locked": bool(layer.get("locked")),
        "printable": layer.get("printable") is not False,
        "source": source,
        "template_trace": template_trace,
        "source_trace": safe_dict(layer.get("source_trace")) or {"source": source, **template_trace},
        "review_required": True,
        "review_only": True,
        "construction_release_allowed": False,
    }


def _normalized_style(style: Dict[str, Any]) -> Dict[str, Any]:
    style_id = safe_str(style.get("id") or style.get("style_id"), CAD_DEFAULT_STYLE_ID)
    source = safe_str(style.get("source") or style.get("template_source") or style.get("source_reference"), "cad_entity_model")
    template_trace = safe_dict(style.get("template_trace"))
    if not template_trace and (style.get("template_id") or style.get("source_reference")):
        template_trace = {
            "template_id": safe_str(style.get("template_id")),
            "source_reference": safe_str(style.get("source_reference")),
        }
    return {
        "id": style_id,
        "style_id": style_id,
        "name": safe_str(style.get("name"), "By Layer"),
        "entity_types_supported": _dedupe(style.get("entity_types_supported") or style.get("supported_entity_types") or sorted(CAD_ENTITY_TYPES)),
        "defaults": {
            "color": safe_str(safe_dict(style.get("defaults")).get("color") or style.get("color"), "by_layer"),
            "linetype": safe_str(safe_dict(style.get("defaults")).get("linetype") or style.get("linetype"), "by_layer"),
            "lineweight": safe_str(safe_dict(style.get("defaults")).get("lineweight") or style.get("lineweight"), "by_layer"),
            "text": safe_dict(safe_dict(style.get("defaults")).get("text") or style.get("text_defaults")),
            "dimension": safe_dict(safe_dict(style.get("defaults")).get("dimension") or style.get("dimension_defaults")),
            "hatch": safe_dict(safe_dict(style.get("defaults")).get("hatch") or style.get("hatch_defaults")),
        },
        "source": source,
        "template_trace": template_trace,
        "source_trace": safe_dict(style.get("source_trace")) or {"source": source, **template_trace},
        "review_required": True,
        "review_only": True,
        "construction_release_allowed": False,
    }


def _normalized_lookup_id(value: Any) -> str:
    raw = safe_str(value).lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned


def _template_layers_styles(template: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rec = safe_dict(template)
    if not rec:
        return [], []
    sections = safe_dict(rec.get("sections"))
    source_reference = safe_str(rec.get("source_reference"), "customer_template")
    template_trace = {
        "template_id": safe_str(rec.get("template_id")),
        "template_name": safe_str(rec.get("name")),
        "firm_name": safe_str(rec.get("firm_name")),
        "source_reference": source_reference,
        "customer_standard_only": True,
        "jurisdiction_compliance_claim": False,
    }
    layers: List[Dict[str, Any]] = []
    for item in safe_list(safe_dict(sections.get("layer_standards")).get("layers")):
        layer = safe_dict(item)
        name = safe_str(layer.get("name") or layer.get("layer_id"))
        if not name:
            continue
        layers.append(
            _normalized_layer(
                {
                    **layer,
                    "id": safe_str(layer.get("layer_id") or layer.get("id")) or f"layer_{_normalized_lookup_id(name)}",
                    "name": name,
                    "source": "customer_template",
                    "source_reference": source_reference,
                    "template_trace": template_trace,
                }
            )
        )
    styles: List[Dict[str, Any]] = []
    annotation = safe_dict(sections.get("annotation_standards"))
    for collection, defaults_key, entity_types in (
        ("text_styles", "text", ["text"]),
        ("dimension_styles", "dimension", ["dimension"]),
        ("hatch_fill_styles", "hatch", ["hatch", "polygon"]),
        ("linetype_styles", "", sorted(CAD_ENTITY_TYPES)),
    ):
        for item in safe_list(annotation.get(collection)):
            style = safe_dict(item)
            key = safe_str(style.get("key") or style.get("target") or style.get("name"))
            if not key:
                continue
            defaults = {
                "color": safe_str(style.get("color"), "by_layer"),
                "linetype": safe_str(style.get("linetype"), "by_layer"),
                "lineweight": safe_str(style.get("lineweight"), "by_layer"),
                "text": style if defaults_key == "text" else {},
                "dimension": style if defaults_key == "dimension" else {},
                "hatch": style if defaults_key == "hatch" else {},
            }
            styles.append(
                _normalized_style(
                    {
                        "id": safe_str(style.get("style_id") or style.get("id")) or f"style_{_normalized_lookup_id(key)}",
                        "name": key,
                        "entity_types_supported": safe_list(style.get("entity_types_supported")) or entity_types,
                        "defaults": defaults,
                        "source": "customer_template",
                        "source_reference": source_reference,
                        "template_trace": template_trace,
                    }
                )
            )
    return layers, styles

def _measurement_points_for_entity(entity: Dict[str, Any]) -> List[Dict[str, float]]:
    rec = safe_dict(entity)
    geometry = safe_dict(rec.get("geometry"))
    entity_type = safe_str(rec.get("type"))
    if entity_type == "line":
        return [point for point in (_point(geometry.get("start")), _point(geometry.get("end"))) if point]
    if entity_type in {"polyline", "polygon", "hatch", "hatch_reference"}:
        return _points(geometry.get("points") or geometry.get("vertices") or geometry.get("boundary"))[:2]
    if entity_type == "rectangle":
        bbox = entity_bounding_box(rec)
        if bbox:
            return [{"x": bbox["min_x"], "y": bbox["min_y"]}, {"x": bbox["max_x"], "y": bbox["min_y"]}]
    if entity_type in {"circle", "arc"}:
        center = _point(geometry.get("center"))
        radius = safe_float(geometry.get("radius"), None)
        if center and radius and radius > 0:
            return [center, {"x": center["x"] + radius, "y": center["y"]}]
    return []


def _dimension_measurement(
    *,
    dimension_type: str,
    points: List[Dict[str, float]],
    measured_entities: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[float], List[str], str]:
    kind = safe_str(dimension_type, "aligned")
    entities = [safe_dict(item) for item in safe_list(measured_entities)]
    first_entity = entities[0] if entities else {}
    first_type = safe_str(first_entity.get("type"))
    first_geometry = safe_dict(first_entity.get("geometry"))
    if kind in {"radius", "diameter"} and first_type in {"circle", "arc"}:
        radius = safe_float(first_geometry.get("radius"), None)
        if radius and radius > 0:
            return (radius * 2.0 if kind == "diameter" else radius), [safe_str(first_entity.get("id"))], "safe_recalculated_from_circle_arc_geometry"
    if kind == "angular" and len(points) >= 3:
        return _angle_degrees(points[0], points[1], points[2]), [safe_str(item.get("id")) for item in entities], "safe_recalculated_from_points"
    if len(points) >= 2:
        if kind == "linear":
            return abs(points[1]["x"] - points[0]["x"]) or abs(points[1]["y"] - points[0]["y"]), [safe_str(item.get("id")) for item in entities], "safe_recalculated_from_points"
        return _distance(points[0], points[1]), [safe_str(item.get("id")) for item in entities], "safe_recalculated_from_points"
    return None, [safe_str(item.get("id")) for item in entities], "blocked_missing_measurement_geometry"


def create_cad_dimension_entity(
    *,
    dimension_type: str = "aligned",
    points: Optional[List[Dict[str, Any]]] = None,
    measured_entities: Optional[List[Dict[str, Any]]] = None,
    units: str = "ft",
    precision: int = 2,
    prefix: str = "",
    suffix: str = "",
    scale: float = 1.0,
    style_id: str = CAD_DEFAULT_STYLE_ID,
    layer_id: str = CAD_DEFAULT_LAYER_ID,
    entity_id: str = "",
    created_by: str = "system",
) -> Dict[str, Any]:
    parsed_points = _points(points)
    entities = [safe_dict(item) for item in safe_list(measured_entities)]
    if not parsed_points and entities:
        parsed_points = _measurement_points_for_entity(entities[0])
    kind = safe_str(dimension_type, "aligned")
    first_type = safe_str(entities[0].get("type")) if entities else ""
    if kind not in {"linear", "aligned", "angular", "radius", "diameter"}:
        kind = "aligned"
    if kind == "aligned" and first_type in {"circle", "arc"}:
        kind = "radius"
    measurement_value, measured_refs, association_status = _dimension_measurement(
        dimension_type=kind,
        points=parsed_points,
        measured_entities=entities,
    )
    dim_units = "deg" if kind == "angular" else safe_str(units, "ft")
    dimension_record = {
        "dimension_type": kind,
        "measured_entity_refs": _dedupe(measured_refs),
        "measured_points": deepcopy(parsed_points),
        "measurement_value": measurement_value,
        "units": dim_units,
        "precision": int(safe_float(precision, 2)),
        "prefix": safe_str(prefix),
        "suffix": safe_str(suffix),
        "scale": safe_float(scale, 1.0),
        "style_id": safe_str(style_id, CAD_DEFAULT_STYLE_ID),
        "layer_id": safe_str(layer_id, CAD_DEFAULT_LAYER_ID),
        "review_required": True,
        "construction_release_allowed": False,
        "association_status": association_status,
        "engineering_quantity_claim": False,
        "truth_label": "Dimension values are drafting/review measurements only and do not update or approve engineering quantities.",
    }
    geometry = {
        "points": parsed_points,
        "units": dim_units,
        "insert": parsed_points[-1] if parsed_points else {"x": 0.0, "y": 0.0},
    }
    if len(parsed_points) >= 2:
        geometry["start"] = parsed_points[0]
        geometry["end"] = parsed_points[1]
    return normalize_cad_entity(
        {
            "id": safe_str(entity_id) or _stable_id("caddim", kind, measured_refs, parsed_points, measurement_value),
            "type": "dimension",
            "geometry": geometry,
            "dimension": dimension_record,
            "layer_id": layer_id,
            "style_id": style_id,
            "source": "chat_cad_command",
            "source_confidence": "chat_drafted_review_required",
            "review_status": "draft_review_required",
            "dirty": True,
        },
        created_by=created_by,
    )


def create_cad_annotation_entity(
    *,
    annotation_type: str,
    text: str,
    points: Optional[List[Dict[str, Any]]] = None,
    layer_id: str = CAD_DEFAULT_LAYER_ID,
    style_id: str = CAD_DEFAULT_STYLE_ID,
    entity_id: str = "",
    created_by: str = "system",
) -> Dict[str, Any]:
    kind = safe_str(annotation_type, "text")
    if kind not in {"text", "leader", "callout", "note", "label"}:
        kind = "text"
    parsed_points = _points(points) or [{"x": 0.0, "y": 0.0}]
    insert = parsed_points[-1]
    geometry = {
        "insert": insert,
        "position": insert,
        "text": safe_str(text),
        "height": 1.0,
        "width": max(1.0, len(safe_str(text)) * 0.6),
        "units": "ft",
    }
    if kind in {"leader", "callout"}:
        geometry["leader_points"] = parsed_points if len(parsed_points) >= 2 else [parsed_points[0], parsed_points[0]]
        geometry["points"] = geometry["leader_points"]
    return normalize_cad_entity(
        {
            "id": safe_str(entity_id) or _stable_id("cadanno", kind, text, parsed_points),
            "type": kind,
            "geometry": geometry,
            "annotation": {
                "annotation_type": kind,
                "text": safe_str(text),
                "style_id": safe_str(style_id, CAD_DEFAULT_STYLE_ID),
                "layer_id": safe_str(layer_id, CAD_DEFAULT_LAYER_ID),
                "review_required": True,
                "construction_release_allowed": False,
                "truth_label": "Annotation entities are drafting/review aids and do not imply compliance, approval, or construction readiness.",
            },
            "layer_id": layer_id,
            "style_id": style_id,
            "source": "chat_cad_command",
            "source_confidence": "chat_drafted_review_required",
            "review_status": "draft_review_required",
            "dirty": True,
        },
        created_by=created_by,
    )


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
            "dimension": safe_dict(rec.get("dimension")),
            "annotation": safe_dict(rec.get("annotation")),
            "linked_object_id": safe_str(rec.get("linked_object_id") or rec.get("object_id")),
            "dirty": bool(rec.get("dirty")),
            "stale": bool(rec.get("stale")),
        }
    )
    if rec["type"] == "dimension":
        dim = safe_dict(rec.get("dimension"))
        dim["review_required"] = True
        dim["construction_release_allowed"] = False
        dim["engineering_quantity_claim"] = False
        dim["style_id"] = safe_str(dim.get("style_id"), rec["style_id"])
        dim["layer_id"] = safe_str(dim.get("layer_id"), rec["layer_id"])
        rec["dimension"] = dim
    if rec["type"] in {"text", "leader", "callout", "note", "label", "hatch", "hatch_reference"}:
        anno = safe_dict(rec.get("annotation"))
        if anno or rec["type"] in {"leader", "callout", "note", "label"}:
            anno["annotation_type"] = safe_str(anno.get("annotation_type"), rec["type"])
            anno["style_id"] = safe_str(anno.get("style_id"), rec["style_id"])
            anno["layer_id"] = safe_str(anno.get("layer_id"), rec["layer_id"])
            anno["review_required"] = True
            anno["construction_release_allowed"] = False
            rec["annotation"] = anno
    return rec


def refresh_dimension_associations(
    entities: List[Dict[str, Any]],
    *,
    changed_entity_ids: Optional[List[str]] = None,
    actor: str = "system",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    changed_ids = set(_dedupe(changed_entity_ids or []))
    by_id = {safe_str(entity.get("id")): normalize_cad_entity(entity, created_by=actor) for entity in entities if safe_str(safe_dict(entity).get("id"))}
    updated: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    for entity_id, entity in list(by_id.items()):
        if safe_str(entity.get("type")) != "dimension":
            updated.append(entity)
            continue
        dim = safe_dict(entity.get("dimension"))
        refs = _dedupe(dim.get("measured_entity_refs") or [])
        impacted = bool(changed_ids and any(ref in changed_ids for ref in refs))
        if not impacted:
            updated.append(entity)
            continue
        before = deepcopy(entity)
        measured_entities = [by_id[ref] for ref in refs if ref in by_id]
        points = _measurement_points_for_entity(measured_entities[0]) if len(measured_entities) == 1 else _points(dim.get("measured_points"))
        if refs and len(measured_entities) != len(refs):
            measurement_value = dim.get("measurement_value")
            association_status = "stale_missing_measured_entity_reference"
        else:
            measurement_value, _, association_status = _dimension_measurement(
                dimension_type=safe_str(dim.get("dimension_type"), "aligned"),
                points=points,
                measured_entities=measured_entities,
            )
        dim["measured_points"] = deepcopy(points)
        dim["measurement_value"] = measurement_value
        dim["association_status"] = association_status
        dim["association_dirty_reason"] = "measured_cad_entity_changed_review_required"
        dim["review_required"] = True
        dim["construction_release_allowed"] = False
        dim["engineering_quantity_claim"] = False
        entity["dimension"] = dim
        if len(points) >= 2:
            entity["geometry"] = {**safe_dict(entity.get("geometry")), "start": points[0], "end": points[1], "points": points, "insert": points[-1]}
        entity["dirty"] = True
        entity["stale"] = True
        entity["review_status"] = "stale"
        updated.append(normalize_cad_entity(entity, created_by=actor))
        events.append(
            history_event(
                "entity_association_updated",
                entity_id,
                actor=actor,
                before=before,
                after=entity,
                changed_fields=["dimension", "geometry", "stale", "dirty"],
                details={
                    "changed_measured_entity_ids": sorted(changed_ids.intersection(refs)),
                    "association_status": association_status,
                    "review_required": True,
                    "construction_release_allowed": False,
                    "truth_label": "Dimension association refresh is drafting/review metadata only and does not update engineering quantities.",
                },
            )
        )
    return updated, events


def build_dimension_annotation_trace(model: Dict[str, Any]) -> Dict[str, Any]:
    dimensions: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    for entity in safe_list(safe_dict(model).get("entities")):
        rec = safe_dict(entity)
        entity_type = safe_str(rec.get("type"))
        if entity_type == "dimension":
            dim = safe_dict(rec.get("dimension"))
            dimensions.append(
                {
                    "entity_id": safe_str(rec.get("id")),
                    "dimension_type": safe_str(dim.get("dimension_type")),
                    "measured_entity_refs": _dedupe(dim.get("measured_entity_refs") or []),
                    "measurement_value": dim.get("measurement_value"),
                    "units": safe_str(dim.get("units")),
                    "precision": dim.get("precision"),
                    "prefix": safe_str(dim.get("prefix")),
                    "suffix": safe_str(dim.get("suffix")),
                    "scale": dim.get("scale"),
                    "style_id": safe_str(dim.get("style_id") or rec.get("style_id")),
                    "layer_id": safe_str(dim.get("layer_id") or rec.get("layer_id")),
                    "stale": bool(rec.get("stale") or rec.get("dirty")),
                    "review_required": True,
                    "construction_release_allowed": False,
                }
            )
        elif entity_type in {"text", "leader", "callout", "note", "label", "hatch", "hatch_reference"}:
            anno = safe_dict(rec.get("annotation"))
            annotations.append(
                {
                    "entity_id": safe_str(rec.get("id")),
                    "annotation_type": safe_str(anno.get("annotation_type"), entity_type),
                    "text": safe_str(anno.get("text") or safe_dict(rec.get("geometry")).get("text")),
                    "style_id": safe_str(anno.get("style_id") or rec.get("style_id")),
                    "layer_id": safe_str(anno.get("layer_id") or rec.get("layer_id")),
                    "review_required": True,
                    "construction_release_allowed": False,
                }
            )
    return {
        "version": "cad_dimension_annotation_trace_v1",
        "dimension_count": len(dimensions),
        "annotation_count": len(annotations),
        "dimensions": dimensions,
        "annotations": annotations,
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": "CAD dimensions and annotations are drafting/review aids only and do not imply compliance, approval, or construction readiness.",
    }


def build_cad_entity_model(meta: Dict[str, Any], *, project_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source_model = safe_dict(meta.get(CAD_ENTITY_MODEL_VERSION) or meta.get("cad_entity_model") or {})
    layers = [_normalized_layer(item) for item in safe_list(source_model.get("layers")) if safe_dict(item)]
    styles = [_normalized_style(item) for item in safe_list(source_model.get("styles")) if safe_dict(item)]
    template_layers, template_styles = _template_layers_styles(
        safe_dict(source_model.get("active_customer_template") or meta.get("active_customer_template"))
    )
    existing_layer_ids = {item["id"] for item in layers}
    for layer in template_layers:
        if layer["id"] not in existing_layer_ids:
            layers.append(layer)
            existing_layer_ids.add(layer["id"])
    existing_style_ids = {item["id"] for item in styles}
    for style in template_styles:
        if style["id"] not in existing_style_ids:
            styles.append(style)
            existing_style_ids.add(style["id"])
    if not any(item["id"] == CAD_DEFAULT_LAYER_ID for item in layers):
        layers.insert(0, _normalized_layer({"id": CAD_DEFAULT_LAYER_ID, "name": "Draft"}))
    if not any(item["id"] == CAD_DEFAULT_STYLE_ID for item in styles):
        styles.insert(0, _normalized_style({"id": CAD_DEFAULT_STYLE_ID, "name": "By Layer"}))
    layer_ids = {item["id"] for item in layers}
    style_ids = {item["id"] for item in styles}
    layer_by_id = {item["id"]: item for item in layers}
    source_entities = [safe_dict(item) for item in safe_list(source_model.get("entities")) if safe_dict(item)]
    source_entities.extend(plan_pdf_elements_to_cad_entities(meta))
    entities = [normalize_cad_entity(item) for item in source_entities if safe_dict(item)]
    validation = [validate_cad_entity(item, known_layer_ids=layer_ids, known_style_ids=style_ids) for item in entities]
    validation_by_id = {item["entity_id"]: item for item in validation}
    for entity in entities:
        result = safe_dict(validation_by_id.get(entity["id"]))
        layer = safe_dict(layer_by_id.get(safe_str(entity.get("layer_id"))))
        visible = layer.get("visible") is not False
        printable = layer.get("printable") is not False
        entity["bounding_box"] = result.get("bounding_box")
        entity["validation_status"] = "valid" if result.get("valid") else "invalid"
        entity["validation_blockers"] = safe_list(result.get("blockers"))
        entity["render_metadata"] = {
            **safe_dict(entity.get("render_metadata")),
            "visible": visible,
            "hidden_by_layer": not visible,
            "layer_id": safe_str(entity.get("layer_id")),
            "style_id": safe_str(entity.get("style_id")),
        }
        entity["sheet_export_trace"] = {
            **safe_dict(entity.get("sheet_export_trace")),
            "printable": printable,
            "non_printable_by_layer": not printable,
            "construction_release_allowed": False,
            "truth_label": "Printable layer state affects sheet/export trace only and does not indicate construction readiness.",
        }
        if entity["dirty"] or entity["stale"]:
            entity["review_status"] = "stale"
    selected_ids = _dedupe(source_model.get("selected_entity_ids") or [])
    history = [
        _normalize_history_event(item, index=index)
        for index, item in enumerate(safe_list(source_model.get("history")))
        if safe_dict(item)
    ]
    history_snapshots = _normalize_history_snapshots(source_model)
    invalid = [item for item in validation if not item.get("valid")]
    stale = [entity for entity in entities if entity.get("dirty") or entity.get("stale") or entity.get("review_status") == "stale"]
    blockers = []
    for item in invalid:
        for blocker in safe_list(item.get("blockers")):
            blockers.append({"entity_id": item.get("entity_id"), "reason": blocker})
    for entity in stale:
        blockers.append({"entity_id": entity.get("id"), "reason": "cad_entity_stale_or_dirty"})
    entity_ids = {entity["id"] for entity in entities}
    changed_entity_ids = _dedupe(event.get("entity_id") for event in history if safe_str(event.get("entity_id")))
    added_entity_ids = _dedupe(
        event.get("entity_id")
        for event in history
        if safe_str(event.get("event_type")) in {"entity_created", "entity_imported", "entity_converted", "entity_restored"}
    )
    removed_entity_ids = _dedupe(event.get("entity_id") for event in history if safe_str(event.get("event_type")) == "entity_deleted")
    stale_entity_ids = _dedupe(entity.get("id") for entity in stale)
    invalid_entity_ids = _dedupe(item.get("entity_id") for item in invalid)
    selected_entity_ids = [entity_id for entity_id in selected_ids if entity_id in {entity["id"] for entity in entities}]
    selected_grips: List[Dict[str, Any]] = []
    selection_blockers: List[Dict[str, str]] = []
    for entity in entities:
        if entity["id"] not in selected_entity_ids:
            continue
        edit_blocker = _edit_blocker(entity)
        if edit_blocker:
            selection_blockers.append({"entity_id": entity["id"], "reason": edit_blocker})
        grips = entity_grip_points(entity)
        if grips:
            selected_grips.extend(grips)
        else:
            selection_blockers.append({"entity_id": entity["id"], "reason": "unsupported entity type"})
    latest_revision_id = (
        safe_str(source_model.get("latest_revision_id") or source_model.get("revision_id") or meta.get("canonical_revision"))
        or _stable_id("cadrev", len(history), ",".join(sorted(entity_ids)), ",".join(changed_entity_ids))
    )
    counts_by_type: Dict[str, int] = {}
    for entity in entities:
        entity_type = safe_str(entity.get("type"), "unknown")
        counts_by_type[entity_type] = counts_by_type.get(entity_type, 0) + 1
    visible_entity_ids = _dedupe(entity.get("id") for entity in entities if safe_dict(entity.get("render_metadata")).get("visible") is not False)
    hidden_entity_ids = _dedupe(entity.get("id") for entity in entities if safe_dict(entity.get("render_metadata")).get("hidden_by_layer"))
    printable_layer_ids = _dedupe(layer.get("id") for layer in layers if layer.get("printable") is not False)
    non_printable_layer_ids = _dedupe(layer.get("id") for layer in layers if layer.get("printable") is False)
    review_blockers = blockers + safe_list(safe_dict(cad_source_confidence_summary(entities)).get("blockers"))
    dimension_annotation_trace = build_dimension_annotation_trace({"entities": entities})
    engineering_objects = _source_engineering_objects(source_model)
    engineering_by_geometry = {safe_str(item.get("geometry_entity_id")): item for item in engineering_objects if safe_str(item.get("geometry_entity_id"))}
    for entity in entities:
        linked = safe_dict(engineering_by_geometry.get(safe_str(entity.get("id"))))
        if linked:
            entity["linked_engineering_object_id"] = safe_str(linked.get("object_id"))
            entity["semantic_geometry_state"] = "engineering_object_geometry"
            entity["canonical_object_type"] = safe_str(linked.get("object_type"))
    engineering_affected_systems = _dedupe(
        system
        for obj in engineering_objects
        for system in safe_list(obj.get("affected_systems"))
    )
    revision_timeline = {
        "latest_revision_id": latest_revision_id,
        "entity_counts": {
            "total": len(entities),
            "by_type": counts_by_type,
            "valid": len(entities) - len(invalid),
            "invalid": len(invalid),
            "stale_or_dirty": len(stale),
            "removed_in_history": len([entity_id for entity_id in removed_entity_ids if entity_id not in entity_ids]),
        },
        "changed_entities": changed_entity_ids,
        "added_entities": added_entity_ids,
        "removed_entities": removed_entity_ids,
        "stale_dirty_entities": stale_entity_ids,
        "invalid_entities": invalid_entity_ids,
        "review_blockers": review_blockers,
        "engineering_object_count": len(engineering_objects),
        "engineering_affected_systems": engineering_affected_systems,
        "event_count": len(history),
        "review_required": True,
        "construction_release_allowed": False,
        "truth_label": "CAD revision history tracks drafting/review changes only and does not approve construction or mutate engineering evidence.",
    }
    return {
        "version": CAD_ENTITY_MODEL_VERSION,
        "layers": layers,
        "styles": styles,
        "entities": entities,
        "selected_entity_ids": selected_entity_ids,
        "entity_bounding_boxes": {entity["id"]: entity.get("bounding_box") for entity in entities if entity.get("bounding_box")},
        "render_metadata": {
            "visible_entity_ids": visible_entity_ids,
            "hidden_entity_ids": hidden_entity_ids,
            "hidden_by_layer_count": len(hidden_entity_ids),
            "review_required": True,
            "construction_release_allowed": False,
        },
        "sheet_export_trace": {
            "printable_layer_ids": printable_layer_ids,
            "non_printable_layer_ids": non_printable_layer_ids,
            "printable_flag_scope": "sheet/export trace only",
            "review_required": True,
            "construction_release_allowed": False,
            "truth_label": "Layer printable flags control plotting/export trace only; they do not make CAD/manual/imported geometry construction-ready.",
        },
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
        "dimension_annotation_trace": dimension_annotation_trace,
        CAD_ENGINEERING_OBJECTS_VERSION: {
            "version": CAD_ENGINEERING_OBJECTS_VERSION,
            "object_count": len(engineering_objects),
            "objects": engineering_objects,
            "affected_systems": engineering_affected_systems,
            "review_required": True,
            "construction_release_allowed": False,
            "truth_label": "Engineering objects created from draft geometry carry project meaning for review workflows but are not professional approval evidence.",
        },
        "engineering_objects": engineering_objects,
        "history": history,
        "history_events": history,
        "history_snapshots": history_snapshots,
        "revision_timeline": revision_timeline,
        "undo_redo": {
            "can_undo": bool(history_snapshots),
            "can_redo": bool(safe_list(source_model.get("redo_snapshots"))),
            "latest_undo_snapshot_id": safe_str(history_snapshots[-1].get("snapshot_id")) if history_snapshots else "",
            "blocked_reason": "" if history_snapshots else "No persisted CAD history snapshot is available for safe undo/restore replay.",
            "review_required": True,
            "construction_release_allowed": False,
        },
        "selection": {
            "selected_entity_ids": selected_entity_ids,
            "selected_count": len(selected_entity_ids),
            "grips": selected_grips,
            "blockers": selection_blockers,
            "hit_test_helper": "Use hit_test_entities with cad_entity_model_v1 entity IDs and entity_bounding_boxes; point selection is bbox-based and window selection uses bbox intersection.",
            "window_select_helper": "Use window_select_entities with two window corner points to select persistent CAD entity IDs.",
            "grip_feedback": "Grip edits are drafting/review actions only and return exact blockers: invalid geometry, self-intersection, locked/reference/underlay entity, missing selected entity, unsupported entity type.",
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


def history_event(
    action: str,
    entity_id: str,
    *,
    actor: str = "system",
    details: Optional[Dict[str, Any]] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    changed_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    timestamp = now_iso()
    event_type = action if action in CAD_HISTORY_ACTIONS else "entity_updated"
    event = {
        "event_id": _stable_id("cadevt", event_type, entity_id, timestamp, actor),
        "entity_id": entity_id,
        "event_type": event_type,
        "action": event_type,
        "timestamp": timestamp,
        "at": timestamp,
        "actor": actor,
        "source": actor,
        "before_summary": _summarize_entity(before),
        "after_summary": _summarize_entity(after),
        "changed_fields": _dedupe(changed_fields or safe_list(safe_dict(details).get("changed_fields")) or _changed_fields(before, after)),
        "details": deepcopy(details or {}),
        "review_required": True,
        "review_only": True,
        "construction_release_allowed": False,
    }
    return event


def cad_entity_operation_result(
    *,
    understood_goal: str,
    selected_action: str,
    target_entities: Optional[List[str]] = None,
    selected_entity_ids: Optional[List[str]] = None,
    missing_inputs: Optional[List[str]] = None,
    safety_blockers: Optional[List[str]] = None,
    created_entity_ids: Optional[List[str]] = None,
    updated_entity_ids: Optional[List[str]] = None,
    deleted_entity_ids: Optional[List[str]] = None,
    combined_geometry_ids: Optional[List[str]] = None,
    engineering_object_ids: Optional[List[str]] = None,
    updated_layer_ids: Optional[List[str]] = None,
    updated_style_ids: Optional[List[str]] = None,
    next_best_action: str = "",
) -> Dict[str, Any]:
    return {
        "version": CAD_ENTITY_CHAT_OPERATION_VERSION,
        "understood_goal": safe_str(understood_goal),
        "selected_action": safe_str(selected_action),
        "target_entities": _dedupe(target_entities or []),
        "selected_entity_ids": _dedupe(selected_entity_ids or []),
        "missing_inputs": _dedupe(missing_inputs or []),
        "safety_blockers": _dedupe(safety_blockers or []),
        "created_entity_ids": _dedupe(created_entity_ids or []),
        "updated_entity_ids": _dedupe(updated_entity_ids or []),
        "deleted_entity_ids": _dedupe(deleted_entity_ids or []),
        "combined_geometry_ids": _dedupe(combined_geometry_ids or []),
        "engineering_object_ids": _dedupe(engineering_object_ids or []),
        "updated_layer_ids": _dedupe(updated_layer_ids or []),
        "updated_style_ids": _dedupe(updated_style_ids or []),
        "review_required": True,
        "construction_release_allowed": False,
        "next_best_action": safe_str(next_best_action),
    }


def _safe_history(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    for item in safe_list(safe_dict(model).get("history")):
        rec = safe_dict(item)
        if safe_str(rec.get("action") or rec.get("event_type")) in CAD_HISTORY_ACTIONS:
            history.append(rec)
    return history


def _matches_layer(layer: Dict[str, Any], target: Any) -> bool:
    needle = _normalized_lookup_id(target)
    if not needle:
        return False
    return needle in {
        _normalized_lookup_id(layer.get("id")),
        _normalized_lookup_id(layer.get("layer_id")),
        _normalized_lookup_id(layer.get("name")),
    }


def _matches_style(style: Dict[str, Any], target: Any) -> bool:
    needle = _normalized_lookup_id(target)
    if not needle:
        return False
    return needle in {
        _normalized_lookup_id(style.get("id")),
        _normalized_lookup_id(style.get("style_id")),
        _normalized_lookup_id(style.get("name")),
    }


def _resolve_layer_id(layers: List[Dict[str, Any]], target: Any, *, create_missing: bool = False) -> str:
    for layer in layers:
        if _matches_layer(layer, target):
            return safe_str(layer.get("id"))
    layer_id = safe_str(target)
    if not layer_id:
        return ""
    if create_missing:
        layers.append(
            _normalized_layer(
                {
                    "id": f"layer_{_normalized_lookup_id(layer_id)}",
                    "name": layer_id,
                    "source": "chat_cad_command",
                    "template_trace": {"customer_standard_only": True, "jurisdiction_compliance_claim": False},
                }
            )
        )
        return safe_str(layers[-1].get("id"))
    return layer_id


def _resolve_style_id(styles: List[Dict[str, Any]], target: Any, *, create_missing: bool = False) -> str:
    for style in styles:
        if _matches_style(style, target):
            return safe_str(style.get("id"))
    style_id = safe_str(target)
    if not style_id:
        return ""
    if create_missing:
        styles.append(
            _normalized_style(
                {
                    "id": f"style_{_normalized_lookup_id(style_id)}",
                    "name": style_id,
                    "source": "chat_cad_command",
                    "template_trace": {"customer_standard_only": True, "jurisdiction_compliance_claim": False},
                }
            )
        )
        return safe_str(styles[-1].get("id"))
    return style_id


def locked_layer_blocker(layer: Dict[str, Any]) -> str:
    return f"{CAD_LAYER_LOCK_BLOCKER_PREFIX}:{safe_str(layer.get('id') or layer.get('layer_id'), CAD_DEFAULT_LAYER_ID)}"


def _transform_point(
    point: Dict[str, Any],
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    angle_degrees: Optional[float] = None,
    scale_factor: Optional[float] = None,
    origin: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    parsed = _point(point) or {"x": 0.0, "y": 0.0}
    x = parsed["x"]
    y = parsed["y"]
    if origin and angle_degrees is not None:
        theta = radians(angle_degrees)
        rel_x = x - origin["x"]
        rel_y = y - origin["y"]
        x = origin["x"] + rel_x * cos(theta) - rel_y * sin(theta)
        y = origin["y"] + rel_x * sin(theta) + rel_y * cos(theta)
    if origin and scale_factor is not None:
        x = origin["x"] + (x - origin["x"]) * scale_factor
        y = origin["y"] + (y - origin["y"]) * scale_factor
    return {"x": x + dx, "y": y + dy}


def _transform_geometry(geometry: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    rec = deepcopy(safe_dict(geometry))
    for key in ("start", "end", "origin", "insert", "position", "center", "min"):
        if key in rec and _point(rec.get(key)):
            rec[key] = _transform_point(safe_dict(rec[key]), **kwargs)
    for key in ("points", "vertices", "boundary"):
        if key in rec:
            rec[key] = [_transform_point(point, **kwargs) for point in _points(rec.get(key))]
    return rec


def _entity_transform_origin(entity: Dict[str, Any]) -> Dict[str, float]:
    bbox = entity_bounding_box(entity) or {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0}
    return {"x": (bbox["min_x"] + bbox["max_x"]) / 2.0, "y": (bbox["min_y"] + bbox["max_y"]) / 2.0}


def apply_cad_entity_operation(
    model: Dict[str, Any],
    operation: Dict[str, Any],
    *,
    actor: str = "user",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    source_model = safe_dict(model)
    action = safe_str(operation.get("action"))
    understood_goal = safe_str(operation.get("understood_goal") or action)
    target_ids = _dedupe(operation.get("target_entity_ids") or [])
    missing_inputs = _dedupe(operation.get("missing_inputs") or [])
    safety_blockers = _dedupe(operation.get("safety_blockers") or [])
    if missing_inputs or safety_blockers or not action:
        return source_model, cad_entity_operation_result(understood_goal=understood_goal, selected_action=action or "unsupported", target_entities=target_ids, missing_inputs=missing_inputs, safety_blockers=safety_blockers, next_best_action=safe_str(operation.get("next_best_action")))

    layers = [_normalized_layer(item) for item in safe_list(source_model.get("layers")) if safe_dict(item)]
    styles = [_normalized_style(item) for item in safe_list(source_model.get("styles")) if safe_dict(item)]
    if not any(item["id"] == CAD_DEFAULT_LAYER_ID for item in layers):
        layers.insert(0, _normalized_layer({"id": CAD_DEFAULT_LAYER_ID, "name": "Draft"}))
    if not any(item["id"] == CAD_DEFAULT_STYLE_ID for item in styles):
        styles.insert(0, _normalized_style({"id": CAD_DEFAULT_STYLE_ID, "name": "By Layer"}))
    layer_by_id = {safe_str(layer.get("id")): layer for layer in layers}
    entities = [normalize_cad_entity(item, created_by=actor) for item in safe_list(source_model.get("entities")) if safe_dict(item)]
    by_id = {safe_str(entity.get("id")): entity for entity in entities if safe_str(entity.get("id"))}
    created_ids: List[str] = []
    updated_ids: List[str] = []
    deleted_ids: List[str] = []
    combined_geometry_ids: List[str] = []
    engineering_object_ids: List[str] = []
    updated_layer_ids: List[str] = []
    updated_style_ids: List[str] = []
    action_history: List[Dict[str, Any]] = []
    selected_entity_ids = _dedupe(source_model.get("selected_entity_ids") or [])
    engineering_objects = _source_engineering_objects(source_model)

    if action in {"select_single", "select_add", "select_multi", "select_window", "clear_selection"}:
        if action == "clear_selection":
            selected_entity_ids = []
        else:
            hit_ids: List[str] = []
            if action == "select_window":
                hit_ids = window_select_entities(entities, safe_dict(operation.get("window") or operation.get("selection_window")))
            elif operation.get("point"):
                hit_ids = hit_test_entities(entities, safe_dict(operation.get("point")), tolerance=abs(safe_float(operation.get("tolerance"), 2.0)))
            hit_ids = _dedupe(target_ids + hit_ids)
            existing_hits = [entity_id for entity_id in hit_ids if entity_id in by_id]
            if not existing_hits:
                missing_inputs.append("missing selected entity")
            elif action == "select_single":
                selected_entity_ids = existing_hits[:1]
            else:
                selected_entity_ids = _dedupe(selected_entity_ids + existing_hits)
    elif action in {"set_layer_visibility", "set_layer_locked", "set_layer_printable"}:
        layer_id = _resolve_layer_id(layers, operation.get("layer_id") or operation.get("layer_name"), create_missing=True)
        for index, layer in enumerate(layers):
            if safe_str(layer.get("id")) != layer_id:
                continue
            updated = deepcopy(layer)
            if action == "set_layer_visibility":
                updated["visible"] = bool(operation.get("visible"))
            elif action == "set_layer_locked":
                updated["locked"] = bool(operation.get("locked"))
            else:
                updated["printable"] = bool(operation.get("printable"))
            updated["review_required"] = True
            updated["construction_release_allowed"] = False
            layers[index] = _normalized_layer(updated)
            updated_layer_ids.append(layer_id)
            layer_by_id[layer_id] = layers[index]
            break
    elif action == "use_company_layer_style":
        updated_layer_ids.extend(safe_str(layer.get("id")) for layer in layers if safe_str(layer.get("source")) == "customer_template")
        updated_style_ids.extend(safe_str(style.get("id")) for style in styles if safe_str(style.get("source")) == "customer_template")
    elif action.startswith("create_"):
        entity_type = safe_str(operation.get("entity_type"))
        if entity_type == "dimension":
            measured_entities = [by_id[entity_id] for entity_id in target_ids if entity_id in by_id]
            entity = create_cad_dimension_entity(
                dimension_type=safe_str(operation.get("dimension_type"), "aligned"),
                points=_points(safe_dict(operation.get("geometry")).get("points") or operation.get("points")),
                measured_entities=measured_entities,
                units=safe_str(operation.get("units"), "ft"),
                precision=int(safe_float(operation.get("precision"), 2)),
                prefix=safe_str(operation.get("prefix")),
                suffix=safe_str(operation.get("suffix")),
                scale=safe_float(operation.get("scale"), 1.0),
                style_id=safe_str(operation.get("style_id"), CAD_DEFAULT_STYLE_ID),
                layer_id=safe_str(operation.get("layer_id"), CAD_DEFAULT_LAYER_ID),
                entity_id=safe_str(operation.get("entity_id")) or _stable_id("cadchat", action, operation.get("geometry"), target_ids, len(entities) + 1),
                created_by=actor,
            )
        elif entity_type in {"text", "leader", "callout", "note", "label"}:
            geometry = safe_dict(operation.get("geometry"))
            entity = create_cad_annotation_entity(
                annotation_type=entity_type,
                text=safe_str(operation.get("text") or geometry.get("text")),
                points=_points(geometry.get("points") or geometry.get("leader_points") or [geometry.get("insert")]),
                style_id=safe_str(operation.get("style_id"), CAD_DEFAULT_STYLE_ID),
                layer_id=safe_str(operation.get("layer_id"), CAD_DEFAULT_LAYER_ID),
                entity_id=safe_str(operation.get("entity_id")) or _stable_id("cadchat", action, operation.get("geometry"), len(entities) + 1),
                created_by=actor,
            )
        else:
            entity = normalize_cad_entity({"id": safe_str(operation.get("entity_id")) or _stable_id("cadchat", action, operation.get("geometry"), len(entities) + 1), "type": entity_type, "geometry": safe_dict(operation.get("geometry")), "layer_id": safe_str(operation.get("layer_id"), CAD_DEFAULT_LAYER_ID), "style_id": safe_str(operation.get("style_id"), CAD_DEFAULT_STYLE_ID), "source": "chat_cad_command", "source_confidence": "chat_drafted_review_required", "review_status": "draft_review_required", "dirty": True}, created_by=actor)
        by_id[entity["id"]] = entity
        created_ids.append(entity["id"])
        action_history.append(history_event("entity_created", entity["id"], actor=actor, details={"source": "chat", "review_required": True}))
    elif action == "combine_selected_geometry":
        selected_for_combine = target_ids or selected_entity_ids
        validation = validate_closed_geometry(
            list(by_id.values()),
            selected_for_combine,
            tolerance=abs(safe_float(operation.get("tolerance"), 0.25)),
            close_gaps=bool(operation.get("close_gaps") or operation.get("snap_gaps")),
        )
        if not validation.get("valid"):
            safety_blockers.extend(safe_str(item) for item in safe_list(validation.get("blockers")) if safe_str(item))
        else:
            points = _points(validation.get("points"))
            combined_id = safe_str(operation.get("entity_id")) or _stable_id("cadarea", ",".join(selected_for_combine), points, validation.get("area_sf"))
            combined = normalize_cad_entity(
                {
                    "id": combined_id,
                    "type": "polygon",
                    "geometry": {"points": points, "closed": True, "units": "ft"},
                    "layer_id": safe_str(operation.get("layer_id"), CAD_DEFAULT_LAYER_ID),
                    "style_id": safe_str(operation.get("style_id"), CAD_DEFAULT_STYLE_ID),
                    "source": "combined_draft_geometry",
                    "source_confidence": "user_drawn_review_required",
                    "review_status": "draft_review_required",
                    "semantic_geometry_state": "combined_geometry",
                    "combined_from_entity_ids": selected_for_combine,
                    "draft_review_required": True,
                    "dirty": True,
                    "stale": True,
                },
                created_by=actor,
            )
            combined["semantic_geometry_state"] = "combined_geometry"
            combined["combined_geometry_validation"] = validation
            combined["combined_from_entity_ids"] = selected_for_combine
            by_id[combined["id"]] = combined
            created_ids.append(combined["id"])
            combined_geometry_ids.append(combined["id"])
            selected_entity_ids = [combined["id"]]
            action_history.append(
                history_event(
                    "entity_converted",
                    combined["id"],
                    actor=actor,
                    details={
                        "semantic_action": "combine_selected_geometry",
                        "source_entity_ids": selected_for_combine,
                        "area_sf": validation.get("area_sf"),
                        "review_required": True,
                    },
                    before={},
                    after=combined,
                    changed_fields=["entity", "geometry", "semantic_geometry_state"],
                )
            )
    elif action == "convert_geometry_to_engineering_object":
        selected_for_conversion = target_ids or selected_entity_ids
        object_type = safe_str(operation.get("object_type"), "building")
        entity_id = safe_str(selected_for_conversion[0] if selected_for_conversion else "")
        entity = by_id.get(entity_id)
        if not entity:
            missing_inputs.append("selected combined geometry")
        else:
            entity_type = safe_str(entity.get("type"))
            geometry_kind = "area" if entity_type in {"polygon", "rectangle", "circle"} else "path" if entity_type == "polyline" else "point" if entity_type == "block_reference" else ""
            allowed = (
                object_type in AREA_ENGINEERING_OBJECT_TYPES and geometry_kind == "area"
                or object_type in PATH_ENGINEERING_OBJECT_TYPES and geometry_kind == "path"
                or object_type in POINT_ENGINEERING_OBJECT_TYPES and geometry_kind == "point"
            )
            if not allowed:
                safety_blockers.append(f"unsupported_conversion:{object_type}_requires_{'closed area' if object_type in AREA_ENGINEERING_OBJECT_TYPES else 'path' if object_type in PATH_ENGINEERING_OBJECT_TYPES else 'point'}")
            else:
                geometry_blockers = [
                    safe_str(blocker)
                    for blocker in safe_list(validate_cad_entity(entity).get("blockers"))
                    if safe_str(blocker).startswith("invalid_geometry")
                    or safe_str(blocker) in {"missing_entity_id", "unsupported_entity_type", "self_intersection"}
                ]
                if geometry_blockers:
                    safety_blockers.append("Cannot convert invalid geometry into an engineering object.")
                    safety_blockers.extend(geometry_blockers)
                    entity = {}
            if entity and not safety_blockers:
                engineering_attributes = safe_dict(operation.get("attributes"))
                if object_type == "building":
                    points = _points(safe_dict(entity.get("geometry")).get("points") or safe_dict(entity.get("geometry")).get("vertices"))
                    engineering_attributes = {
                        "footprint_area_sf": round(_polygon_area(points), 3) if points else None,
                        "use_type": safe_str(engineering_attributes.get("use_type")),
                        "floor_count": safe_float(engineering_attributes.get("floor_count"), 0.0) or None,
                        "finished_floor_elevation": engineering_attributes.get("finished_floor_elevation"),
                        **{k: v for k, v in engineering_attributes.items() if k not in {"use_type", "floor_count", "finished_floor_elevation"}},
                    }
                object_id = safe_str(operation.get("object_id")) or _stable_id("engobj", object_type, entity_id, operation.get("display_name"))
                eng_obj = normalize_engineering_object(
                    {
                        "object_id": object_id,
                        "object_type": object_type,
                        "display_name": safe_str(operation.get("display_name") or operation.get("name"), object_type.replace("_", " ").title()),
                        "geometry_kind": geometry_kind,
                        "geometry_entity_id": entity_id,
                        "source_entity_ids": safe_list(entity.get("combined_from_entity_ids")) or [entity_id],
                        "source": "converted_from_draft_geometry",
                        "source_confidence": safe_str(entity.get("source_confidence"), "user_drawn_review_required"),
                        "creation_method": "semantic_conversion",
                        "engineering_attributes": engineering_attributes,
                        "missing_inputs": _dedupe(operation.get("missing_inputs") or ["qualified review"]),
                        "review_status": "needs_review",
                        "history": [
                            {
                                "action": "object_converted_from_geometry",
                                "geometry_entity_id": entity_id,
                                "actor": actor,
                                "timestamp": now_iso(),
                                "review_required": True,
                                "construction_release_allowed": False,
                            }
                        ],
                    }
                )
                engineering_objects = [item for item in engineering_objects if safe_str(item.get("object_id")) != object_id] + [eng_obj]
                before = deepcopy(entity)
                updated = deepcopy(entity)
                updated["linked_engineering_object_id"] = object_id
                updated["semantic_geometry_state"] = "engineering_object_geometry"
                updated["canonical_object_type"] = object_type
                updated["dirty"] = True
                updated["stale"] = True
                updated["review_status"] = "draft_review_required"
                by_id[entity_id] = normalize_cad_entity(updated, created_by=actor)
                by_id[entity_id]["linked_engineering_object_id"] = object_id
                by_id[entity_id]["semantic_geometry_state"] = "engineering_object_geometry"
                by_id[entity_id]["canonical_object_type"] = object_type
                updated_ids.append(entity_id)
                engineering_object_ids.append(object_id)
                selected_entity_ids = [entity_id]
                action_history.append(
                    history_event(
                        "entity_converted",
                        entity_id,
                        actor=actor,
                        details={
                            "semantic_action": "convert_geometry_to_engineering_object",
                            "engineering_object_id": object_id,
                            "object_type": object_type,
                            "affected_systems": eng_obj.get("affected_systems"),
                            "review_required": True,
                        },
                        before=before,
                        after=by_id[entity_id],
                        changed_fields=["linked_engineering_object_id", "semantic_geometry_state", "canonical_object_type"],
                    )
                )
    elif action == "copy_selected":
        for index, entity_id in enumerate(target_ids):
            entity = by_id.get(entity_id)
            if not entity:
                continue
            layer = safe_dict(layer_by_id.get(safe_str(entity.get("layer_id"))))
            if layer.get("locked"):
                safety_blockers.append(locked_layer_blocker(layer))
                continue
            copied = normalize_cad_entity(
                {
                    **deepcopy(entity),
                    "id": _stable_id("cadcopy", entity_id, len(entities), index),
                    "source": "chat_cad_command",
                    "source_confidence": "chat_drafted_review_required",
                    "geometry": _transform_geometry(safe_dict(entity.get("geometry")), dx=safe_float(operation.get("dx"), 0.0), dy=safe_float(operation.get("dy"), 0.0)),
                    "dirty": True,
                    "stale": True,
                },
                created_by=actor,
            )
            by_id[copied["id"]] = copied
            created_ids.append(copied["id"])
            action_history.append(history_event("entity_created", copied["id"], actor=actor, details={"copied_from": entity_id, "review_required": True}))
    elif action == "delete_selected":
        for entity_id in target_ids:
            entity = by_id.get(entity_id)
            if not entity:
                safety_blockers.append("missing selected entity")
                continue
            edit_blocker = _edit_blocker(entity)
            if edit_blocker:
                safety_blockers.append(edit_blocker)
                continue
            deleted = by_id.pop(entity_id)
            deleted_ids.append(entity_id)
            action_history.append(history_event("entity_deleted", entity_id, actor=actor, details={"chat_action": action, "review_required": True}, before=deleted, changed_fields=["entity"]))
        selected_entity_ids = [entity_id for entity_id in selected_entity_ids if entity_id in by_id]
    elif action == "move_grip":
        entity_id = safe_str(operation.get("entity_id") or (target_ids[0] if target_ids else ""))
        if not entity_id or entity_id not in by_id:
            safety_blockers.append("missing selected entity")
        else:
            grip_id = safe_str(operation.get("grip_id") or safe_dict(operation.get("grip")).get("grip_id"))
            point = safe_dict(operation.get("point") or operation.get("new_point") or operation.get("to"))
            if not point and ("dx" in operation or "dy" in operation):
                grip_by_id = {safe_str(item.get("grip_id")): item for item in entity_grip_points(by_id[entity_id])}
                current = _point(safe_dict(grip_by_id.get(grip_id)).get("point"))
                if current:
                    point = {"x": current["x"] + safe_float(operation.get("dx"), 0.0), "y": current["y"] + safe_float(operation.get("dy"), 0.0)}
            before = by_id[entity_id]
            updated, blockers_for_edit = _move_entity_grip(before, grip_id, point)
            if blockers_for_edit:
                safety_blockers.extend(blockers_for_edit)
            elif updated:
                by_id[entity_id] = updated
                updated_ids.append(entity_id)
                action_history.append(history_event("entity_geometry_changed", entity_id, actor=actor, details={"chat_action": action, "grip_id": grip_id, "review_required": True}, before=before, after=updated, changed_fields=["geometry"]))
    elif action in {"move_selected", "rotate_selected", "scale_selected", "change_layer", "change_style"}:
        if action == "change_layer":
            operation["layer_id"] = _resolve_layer_id(layers, operation.get("layer_id") or operation.get("layer_name"), create_missing=True)
            layer_by_id = {safe_str(layer.get("id")): layer for layer in layers}
        if action == "change_style":
            operation["style_id"] = _resolve_style_id(styles, operation.get("style_id") or operation.get("style_name"), create_missing=True)
            updated_style_ids.append(safe_str(operation.get("style_id")))
        for entity_id in target_ids:
            entity = by_id.get(entity_id)
            if not entity:
                safety_blockers.append("missing selected entity")
                continue
            edit_blocker = _edit_blocker(entity)
            if edit_blocker:
                safety_blockers.append(edit_blocker)
                continue
            layer = safe_dict(layer_by_id.get(safe_str(entity.get("layer_id"))))
            if layer.get("locked"):
                safety_blockers.append(locked_layer_blocker(layer))
                continue
            before = deepcopy(entity)
            updated = deepcopy(entity)
            if action == "move_selected":
                updated["geometry"] = _transform_geometry(safe_dict(entity.get("geometry")), dx=safe_float(operation.get("dx"), 0.0), dy=safe_float(operation.get("dy"), 0.0))
            elif action == "rotate_selected":
                updated["geometry"] = _transform_geometry(safe_dict(entity.get("geometry")), angle_degrees=safe_float(operation.get("angle_degrees"), 0.0), origin=_entity_transform_origin(entity))
            elif action == "scale_selected":
                updated["geometry"] = _transform_geometry(safe_dict(entity.get("geometry")), scale_factor=safe_float(operation.get("scale_factor"), 1.0), origin=_entity_transform_origin(entity))
            elif action == "change_layer":
                updated["layer_id"] = safe_str(operation.get("layer_id"), CAD_DEFAULT_LAYER_ID)
            elif action == "change_style":
                updated["style_id"] = safe_str(operation.get("style_id"), CAD_DEFAULT_STYLE_ID)
            updated["dirty"] = True
            updated["stale"] = True
            updated["review_status"] = "draft_review_required"
            by_id[entity_id] = normalize_cad_entity(updated, created_by=actor)
            updated_ids.append(entity_id)
            event_type = "entity_geometry_changed" if action in {"move_selected", "rotate_selected", "scale_selected"} else "entity_layer_changed" if action == "change_layer" else "entity_style_changed"
            action_history.append(history_event(event_type, entity_id, actor=actor, details={"chat_action": action, "review_required": True}, before=before, after=by_id[entity_id]))
    else:
        safety_blockers.append(f"unsupported_cad_entity_operation:{action}")

    association_changed_ids = _dedupe(updated_ids + deleted_ids)
    if association_changed_ids:
        refreshed_entities, association_events = refresh_dimension_associations(
            list(by_id.values()),
            changed_entity_ids=association_changed_ids,
            actor=actor,
        )
        by_id = {safe_str(entity.get("id")): entity for entity in refreshed_entities if safe_str(entity.get("id"))}
        refreshed_dimension_ids = [safe_str(event.get("entity_id")) for event in association_events if safe_str(event.get("entity_id"))]
        updated_ids = _dedupe(updated_ids + refreshed_dimension_ids)
        action_history.extend(association_events)

    next_model = {
        **source_model,
        "entities": list(by_id.values()),
        "layers": layers,
        "styles": styles,
        CAD_ENGINEERING_OBJECTS_VERSION: engineering_objects,
        "engineering_objects": engineering_objects,
        "history": _safe_history(source_model) + action_history,
        "selected_entity_ids": [safe_str(entity_id) for entity_id in selected_entity_ids if safe_str(entity_id) in by_id],
    }
    result = cad_entity_operation_result(
        understood_goal=understood_goal,
        selected_action=action,
        target_entities=target_ids,
        selected_entity_ids=selected_entity_ids,
        safety_blockers=safety_blockers,
        created_entity_ids=created_ids,
        updated_entity_ids=updated_ids,
        deleted_entity_ids=deleted_ids,
        combined_geometry_ids=combined_geometry_ids,
        engineering_object_ids=engineering_object_ids,
        updated_layer_ids=updated_layer_ids,
        updated_style_ids=updated_style_ids,
        next_best_action=safe_str(operation.get("next_best_action"), "Review the changed CAD entities before using them in downstream workflows."),
    )
    return next_model, result

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


def _pdf_bbox_geometry(bounds: Dict[str, Any], *, text: str = "", page_index: int = 0) -> Optional[Dict[str, Any]]:
    x0 = safe_float(bounds.get("x0"), None)
    y0 = safe_float(bounds.get("y0"), None)
    x1 = safe_float(bounds.get("x1"), None)
    y1 = safe_float(bounds.get("y1"), None)
    if x0 is None or y0 is None or x1 is None or y1 is None:
        return None
    width = max(1.0, abs(x1 - x0))
    height = max(1.0, abs(y1 - y0))
    return {
        "insert": {"x": float(min(x0, x1)), "y": float(min(y0, y1))},
        "width": float(width),
        "height": float(height),
        "text": safe_str(text),
        "units": "pdf_points",
        "page_index": int(page_index),
    }


def _pdf_source_record(element: Dict[str, Any], analysis: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    source_pdf = safe_dict(analysis.get("source_pdf"))
    return {
        "source_pdf_id": safe_str(source_pdf.get("source_pdf_id")),
        "filename": safe_str(source_pdf.get("filename") or source_pdf.get("stored_filename")),
        "sha256": safe_str(source_pdf.get("sha256")),
        "page": int(element.get("page_index") or evidence.get("page_index") or 0) + 1,
        "page_index": int(element.get("page_index") or evidence.get("page_index") or 0),
        "original_text": safe_str(element.get("original_text") or element.get("text") or evidence.get("text")),
        "original_bounds": safe_dict(element.get("original_bbox") or element.get("bbox") or evidence.get("bbox")) or None,
        "confidence": safe_str(element.get("source_confidence") or evidence.get("source_confidence"), PDF_SOURCE_CONFIDENCE),
        "source_evidence_id": safe_str(element.get("source_evidence_id") or evidence.get("evidence_id")),
        "extraction_source": safe_str(evidence.get("source")),
        "imported_pdf_review_required": True,
        "review_required": True,
        "survey_backed": False,
        "engineer_approved": False,
        "construction_release_allowed": False,
    }


def _pdf_evidence_by_id(analysis: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for item in safe_list(analysis.get("raw_text_evidence")):
        rec = safe_dict(item)
        evidence_id = safe_str(rec.get("evidence_id"))
        if evidence_id:
            by_id[evidence_id] = rec
    return by_id


def _pdf_text_entity_type(element_type: str) -> str:
    return "dimension" if element_type == "dimension" else "text"


def _pdf_annotation_kind(element_type: str) -> str:
    mapping = {
        "dimension": "dimension",
        "elevation_callout": "elevation",
        "scale_calibration_candidate": "scale_calibration",
        "matchline": "matchline",
        "detail_block": "detail",
    }
    return mapping.get(element_type, "text")


def _pdf_element_to_cad_entity(element: Dict[str, Any], analysis: Dict[str, Any], evidence: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    element_type = safe_str(element.get("type"))
    if element_type in {"stamp_or_seal_source_imagery", "linework_geometry_candidate"}:
        return None
    if safe_str(evidence.get("source")) not in {"embedded_pdf_text", "embedded_pdf_text_fallback"}:
        return None
    bounds = safe_dict(element.get("original_bbox") or element.get("bbox") or evidence.get("bbox"))
    geometry = _pdf_bbox_geometry(bounds, text=safe_str(element.get("text") or evidence.get("text")), page_index=int(element.get("page_index") or 0))
    if geometry is None:
        return None
    entity_type = _pdf_text_entity_type(element_type)
    if entity_type == "dimension":
        insert = safe_dict(geometry.get("insert"))
        geometry["points"] = [
            {"x": insert["x"], "y": insert["y"]},
            {"x": insert["x"] + safe_float(geometry.get("width"), 1.0), "y": insert["y"]},
        ]
        geometry["label"] = safe_str(geometry.get("text"))
    source_record = _pdf_source_record(element, analysis, evidence)
    return {
        "id": _stable_id("cadpdf", source_record.get("source_pdf_id"), element.get("element_id"), source_record.get("sha256")),
        "type": entity_type,
        "geometry": geometry,
        "layer_id": safe_str(element.get("cad_layer_id"), CAD_DEFAULT_LAYER_ID),
        "style_id": safe_str(element.get("cad_style_id"), CAD_DEFAULT_STYLE_ID),
        "source": "plan_pdf_extraction",
        "source_confidence": PDF_SOURCE_CONFIDENCE,
        "review_status": "imported_review_required",
        "draft_review_required": True,
        "dirty": True,
        "pdf_annotation_kind": _pdf_annotation_kind(element_type),
        "calibration": {
            "kind": "sheet_model_scale_candidate",
            "status": "accepted_review_required" if element_type == "scale_calibration_candidate" and safe_str(element.get("review_status")) == "accepted" else "review_required",
            "can_calibrate_sheet_model_conversion": element_type == "scale_calibration_candidate",
            "source_text": source_record["original_text"],
            "review_required": True,
            "construction_release_allowed": False,
        }
        if element_type == "scale_calibration_candidate"
        else {},
        "linked_pdf_element_id": safe_str(element.get("element_id")),
        "source_pdf": source_record,
        "original_text": source_record["original_text"],
        "original_bounds": source_record["original_bounds"],
        "page": source_record["page"],
        "confidence": source_record["confidence"],
        "imported_pdf_review_required": True,
        "truth_label": "PDF-derived CAD entities are imported source evidence and review-required drafting objects only; they are not survey-backed, engineer-reviewed, or field-use release evidence.",
    }


def _pdf_vector_entity(candidate: Dict[str, Any], analysis: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    rec = safe_dict(candidate)
    entity_type = safe_str(rec.get("type") or rec.get("entity_type"))
    if entity_type not in {"line", "polyline"}:
        return None
    confidence = safe_str(rec.get("source_confidence") or rec.get("confidence"), PDF_SOURCE_CONFIDENCE)
    if "review_required" not in confidence:
        confidence = PDF_SOURCE_CONFIDENCE
    geometry = safe_dict(rec.get("geometry"))
    if entity_type == "line" and not geometry:
        points = _points(rec.get("points"))
        if len(points) >= 2:
            geometry = {"start": points[0], "end": points[1], "units": "pdf_points"}
    if entity_type == "polyline" and not geometry:
        points = _points(rec.get("points") or rec.get("vertices"))
        if len(points) >= 2:
            geometry = {"points": points, "closed": bool(rec.get("closed")), "units": "pdf_points"}
    if not geometry:
        return None
    source_pdf = safe_dict(analysis.get("source_pdf"))
    source_record = {
        "source_pdf_id": safe_str(source_pdf.get("source_pdf_id")),
        "filename": safe_str(source_pdf.get("filename") or source_pdf.get("stored_filename")),
        "sha256": safe_str(source_pdf.get("sha256")),
        "page": int(rec.get("page_index") or 0) + 1,
        "page_index": int(rec.get("page_index") or 0),
        "original_text": safe_str(rec.get("original_text") or rec.get("text")),
        "original_bounds": safe_dict(rec.get("original_bounds") or rec.get("bounds") or rec.get("bbox")) or None,
        "confidence": confidence,
        "imported_pdf_review_required": True,
        "review_required": True,
        "survey_backed": False,
        "engineer_approved": False,
        "construction_release_allowed": False,
    }
    return {
        "id": safe_str(rec.get("id")) or _stable_id("cadpdfvec", source_record.get("source_pdf_id"), index, geometry, source_record.get("sha256")),
        "type": entity_type,
        "geometry": geometry,
        "source": "plan_pdf_vector_extraction",
        "source_confidence": confidence,
        "review_status": "imported_review_required",
        "draft_review_required": True,
        "dirty": True,
        "source_pdf": source_record,
        "original_text": source_record["original_text"],
        "original_bounds": source_record["original_bounds"],
        "page": source_record["page"],
        "confidence": confidence,
        "imported_pdf_review_required": True,
        "truth_label": "PDF vector-derived CAD entities are review-required imported drafting objects only.",
    }


def plan_pdf_elements_to_cad_entities(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    analysis = safe_dict(meta.get("plan_pdf_analysis_v1"))
    sheet = safe_dict(meta.get("plan_pdf_editable_sheet_v1"))
    if not analysis or not sheet:
        return []
    existing_ids = {safe_str(item.get("linked_pdf_element_id")) for item in safe_list(safe_dict(meta.get(CAD_ENTITY_MODEL_VERSION)).get("entities")) if safe_str(safe_dict(item).get("linked_pdf_element_id"))}
    evidence_by_id = _pdf_evidence_by_id(analysis)
    entities: List[Dict[str, Any]] = []
    for element in safe_list(sheet.get("elements")):
        rec = safe_dict(element)
        element_id = safe_str(rec.get("element_id"))
        if element_id and element_id in existing_ids:
            continue
        evidence = safe_dict(evidence_by_id.get(safe_str(rec.get("source_evidence_id"))))
        entity = _pdf_element_to_cad_entity(rec, analysis, evidence)
        if entity:
            entities.append(entity)
    vector_records = (
        safe_list(safe_dict(analysis.get("vector_geometry")).get("entities"))
        + safe_list(safe_dict(analysis.get("vector_extraction")).get("entities"))
        + safe_list(analysis.get("vector_geometry_candidates"))
    )
    for index, candidate in enumerate(vector_records):
        entity = _pdf_vector_entity(safe_dict(candidate), analysis, index)
        if entity:
            entities.append(entity)
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
        "truth_label": "CAD entity source confidence explains drafting evidence only; it does not make CAD geometry survey-backed or construction-release evidence.",
    }


__all__ = [
    "CAD_ENTITY_CHAT_OPERATION_VERSION",
    "CAD_ENGINEERING_OBJECTS_VERSION",
    "CAD_ENTITY_MODEL_VERSION",
    "CAD_HISTORY_ACTIONS",
    "CAD_ENTITY_TYPES",
    "apply_cad_entity_operation",
    "attach_cad_entity_model_to_result",
    "build_cad_entity_model",
    "build_dimension_annotation_trace",
    "build_cad_history_snapshot",
    "cad_entity_operation_result",
    "cad_entities_to_site_object_candidates",
    "cad_source_confidence_summary",
    "create_cad_annotation_entity",
    "create_cad_dimension_entity",
    "entity_grip_points",
    "entity_bounding_box",
    "history_event",
    "hit_test_entities",
    "import_candidates_to_cad_entities",
    "locked_layer_blocker",
    "manual_drawn_objects_to_cad_entities",
    "normalize_cad_entity",
    "normalize_engineering_object",
    "plan_pdf_elements_to_cad_entities",
    "refresh_dimension_associations",
    "selected_entity_grips",
    "validate_closed_geometry",
    "validate_cad_entity",
    "window_select_entities",
]
