from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any, Dict, List, Optional

from .common import safe_dict, safe_float, safe_list, safe_str


REPORT_VERSION = "map_feature_detection_report_v1"

FEATURE_TYPES = {
    "building_footprint",
    "road_or_drive",
    "parking_area",
    "parcel_or_site_boundary",
    "terrain",
    "sidewalk_or_path",
    "water/pond/basin",
    "vegetation/tree_area",
    "constraint_area",
    "utility",
}

SOURCE_TYPES = {
    "official_gis",
    "image_detected_candidate",
    "user_drawn",
    "unavailable",
}

SOURCE_TYPES_REQUIRED = {
    "parcels": {"label": "parcel/site boundary", "candidate_type": "parcel_or_site_boundary"},
    "roads_row": {"label": "roads/right-of-way", "candidate_type": "road_or_drive"},
    "building_footprints": {"label": "building footprints", "candidate_type": "building_footprint"},
    "easements": {"label": "easements", "candidate_type": "constraint_area"},
    "floodplain": {"label": "floodplain", "candidate_type": "constraint_area"},
    "wetlands": {"label": "wetlands", "candidate_type": "constraint_area"},
    "zoning": {"label": "zoning", "candidate_type": "constraint_area"},
    "existing_utilities": {"label": "existing utilities", "candidate_type": "utility"},
}

GIS_LAYER_FEATURE_TYPES = {
    "building_footprints": "building_footprint",
    "buildings": "building_footprint",
    "roads": "road_or_drive",
    "roadways": "road_or_drive",
    "roads_row": "road_or_drive",
    "right_of_way": "road_or_drive",
    "driveways": "road_or_drive",
    "parking": "parking_area",
    "parking_areas": "parking_area",
    "parcels": "parcel_or_site_boundary",
    "site_boundaries": "parcel_or_site_boundary",
    "sidewalks": "sidewalk_or_path",
    "paths": "sidewalk_or_path",
    "water": "water/pond/basin",
    "ponds": "water/pond/basin",
    "basins": "water/pond/basin",
    "tree_canopy": "vegetation/tree_area",
    "vegetation": "vegetation/tree_area",
    "easements": "constraint_area",
    "row": "constraint_area",
    "floodplain": "constraint_area",
    "wetlands": "constraint_area",
    "existing_utilities": "utility",
    "utilities": "utility",
    "zoning": "constraint_area",
    "constraints": "constraint_area",
}

IMAGE_KIND_FEATURE_TYPES = {
    "building": "building_footprint",
    "road": "road_or_drive",
    "driveway": "road_or_drive",
    "parking": "parking_area",
    "sidewalk": "sidewalk_or_path",
    "path": "sidewalk_or_path",
    "basin": "water/pond/basin",
    "pond": "water/pond/basin",
    "water": "water/pond/basin",
    "vegetation": "vegetation/tree_area",
    "tree_area": "vegetation/tree_area",
    "constraint": "constraint_area",
}

DRAFT_OBJECT_TYPES = {
    "building_footprint": "building",
    "road_or_drive": "road",
    "parking_area": "parking",
    "parcel_or_site_boundary": "site_boundary_candidate",
    "terrain": "terrain_candidate",
    "sidewalk_or_path": "sidewalk",
    "water/pond/basin": "basin",
    "vegetation/tree_area": "open_space",
    "constraint_area": "constraint_area",
    "utility": "existing_utility",
}

FEATURE_TYPE_LABELS = {
    "building_footprint": "building footprint",
    "road_or_drive": "road/ROW",
    "parking_area": "parking area",
    "parcel_or_site_boundary": "parcel/site boundary",
    "terrain": "terrain/elevation",
    "sidewalk_or_path": "sidewalk/path",
    "water/pond/basin": "water/wetland/floodplain constraint",
    "vegetation/tree_area": "vegetation/tree area",
    "constraint_area": "constraint",
    "utility": "existing utility",
}


def location_context_from_geocode(*, address: str = "", geocode: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rec = safe_dict(geocode)
    lat = rec.get("lat")
    lng = rec.get("lng")
    matched = safe_str(rec.get("matched_address") or rec.get("display_name") or rec.get("place_name"))
    normalized = safe_str(rec.get("normalized_address") or rec.get("formatted_address") or matched or address)
    crs = safe_dict(rec.get("crs") or rec.get("coordinate_system")) or {
        "epsg": safe_str(rec.get("epsg"), "EPSG:4326" if lat not in (None, "") and lng not in (None, "") else ""),
        "name": safe_str(rec.get("crs_name"), "WGS 84 geographic coordinates" if lat not in (None, "") and lng not in (None, "") else ""),
        "units": safe_str(rec.get("units"), "degrees" if lat not in (None, "") and lng not in (None, "") else ""),
        "source": safe_str(rec.get("source") or rec.get("source_type") or rec.get("provider")),
    }
    return {
        "address": safe_str(address or rec.get("address") or normalized),
        "normalized_address": normalized,
        "matched_address": matched,
        "coordinates": {
            "lat": safe_float(lat) if lat not in (None, "") else None,
            "lng": safe_float(lng) if lng not in (None, "") else None,
        },
        "crs": crs,
        "geocode": {
            "lat": safe_float(lat) if lat not in (None, "") else None,
            "lng": safe_float(lng) if lng not in (None, "") else None,
            "provider": safe_str(rec.get("provider") or rec.get("source_type")),
            "source": safe_str(rec.get("source")),
            "confidence": rec.get("confidence"),
            "status": safe_str(rec.get("status")),
        },
        "confidence": rec.get("confidence"),
        "evidence_source": safe_str(rec.get("source") or rec.get("source_type") or rec.get("provider"), "address_geocode"),
        "evidence": [
            {
                "source_type": safe_str(rec.get("source_type") or rec.get("provider"), "address_geocode"),
                "source_url": safe_str(rec.get("source")),
                "status": safe_str(rec.get("status"), "unknown"),
                "confidence": rec.get("confidence"),
            }
        ],
        "truth_label": "Address/geocode is location context only; it is not a site boundary, survey, control, or construction approval.",
    }


def build_map_feature_detection_report(
    *,
    location_context: Optional[Dict[str, Any]] = None,
    gis_layers: Optional[Dict[str, Any]] = None,
    image_detections: Optional[List[Dict[str, Any]]] = None,
    inferred_candidates: Optional[List[Dict[str, Any]]] = None,
    source_results: Optional[Dict[str, Any]] = None,
    configured_sources: Optional[Dict[str, Any]] = None,
    active_site_boundary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    outside_site_candidates: List[Dict[str, Any]] = []
    blockers: List[Dict[str, Any]] = []
    source_discovery = build_source_discovery(source_results=source_results, configured_sources=configured_sources, gis_layers=gis_layers)
    layers = safe_dict(gis_layers)
    boundary = safe_dict(active_site_boundary)

    def add_candidate(candidate: Dict[str, Any]) -> None:
        relation = _site_relation(candidate.get("geometry"), boundary)
        if relation == "outside_site":
            candidate["site_relation"] = "outside_site"
            candidate["outside_site"] = True
            outside_site_candidates.append(candidate)
            return
        if relation:
            candidate["site_relation"] = relation
            candidate["outside_site"] = False
        candidates.append(candidate)

    for layer_name, raw_layer in layers.items():
        feature_type = GIS_LAYER_FEATURE_TYPES.get(safe_str(layer_name))
        if not feature_type:
            continue
        for idx, feature in enumerate(_layer_features(raw_layer)):
            rec = safe_dict(feature)
            source = safe_str(rec.get("source_url") or rec.get("source") or safe_dict(raw_layer).get("source_url") or safe_dict(raw_layer).get("source"), "")
            source_name = safe_str(rec.get("source_name") or rec.get("source_type") or safe_dict(raw_layer).get("source_name") or safe_dict(raw_layer).get("source_type"), f"gis_layer:{layer_name}")
            accepted = _official_source_accepted(rec) or _official_source_accepted(safe_dict(raw_layer))
            add_candidate(
                _candidate(
                    feature_type=feature_type,
                    source_type="official_gis",
                    geometry=rec.get("geometry"),
                    confidence=0.95 if accepted else 0.88,
                    source_url=source,
                    source_name=source_name,
                    blockers=[] if accepted else ["Official GIS source is candidate evidence until the user/licensed engineer accepts the source for this project."],
                    review_required=True,
                    acceptance_status="accepted" if accepted else "pending",
                    seed=f"gis:{layer_name}:{idx}:{source or source_name}:{rec.get('id')}",
                    source_feature_id=safe_str(rec.get("id")),
                    properties=safe_dict(rec.get("properties")),
                )
            )

    elevation = safe_dict(safe_dict(source_results).get("elevation"))
    if elevation.get("success"):
        add_candidate(
            _candidate(
                feature_type="terrain",
                source_type="official_gis",
                geometry={"type": "Point", "coordinates": [safe_float(elevation.get("lng")), safe_float(elevation.get("lat"))]},
                confidence=0.72,
                source_url=safe_str(elevation.get("source")),
                source_name=safe_str(elevation.get("source_type"), "usgs_3dep_epqs"),
                blockers=[safe_str(elevation.get("truth_label"), "Public DEM/elevation context is not a topographic survey.")],
                review_required=True,
                acceptance_status="pending",
                seed=f"terrain:{elevation.get('source')}:{elevation.get('lat')}:{elevation.get('lng')}:{elevation.get('elevation')}",
                source_feature_id="terrain-elevation-sample",
                properties={
                    "elevation": elevation.get("elevation"),
                    "units": elevation.get("units"),
                    "source_date": elevation.get("source_date"),
                },
            )
        )

    for idx, detection in enumerate(safe_list(image_detections)):
        rec = safe_dict(detection)
        kind = safe_str(rec.get("kind") or rec.get("feature_type") or rec.get("type"))
        feature_type = IMAGE_KIND_FEATURE_TYPES.get(kind, kind if kind in FEATURE_TYPES else "")
        if not feature_type:
            continue
        confidence = min(max(safe_float(rec.get("confidence"), 0.35), 0.05), 0.7)
        add_candidate(
            _candidate(
                feature_type=feature_type,
                source_type="image_detected_candidate",
                geometry=rec.get("geometry") or rec.get("bbox"),
                confidence=confidence,
                source_url=safe_str(rec.get("source_url") or rec.get("image_url")),
                source_name=safe_str(rec.get("evidence_source") or rec.get("source") or rec.get("image_path"), "uploaded_map_snapshot"),
                blockers=["Map imagery detection is approximate and must be confirmed/classified before it can affect engineering objects."],
                review_required=True,
                acceptance_status="pending",
                seed=f"image:{idx}:{kind}:{rec.get('bbox')}:{rec.get('geometry')}",
            )
        )

    _ = inferred_candidates

    if not candidates:
        blockers.append(
            {
                "code": "no_gis_or_imagery_feature_source",
                "message": "No official GIS layer, map imagery detection result, or user-drawn/imported feature source is available. Civora will not infer buildings, roads, parcels, utilities, or terrain from an address alone.",
                "next_action": "Upload a map image, configure/import GIS sources, or draw existing features manually.",
            }
        )
    for key, source in source_discovery.items():
        rec = safe_dict(source)
        if rec.get("configured"):
            continue
        blockers.append(
            {
                "code": f"missing_{key}_source",
                "source_type": key,
                "message": f"No configured {rec.get('label') or key} source is available.",
                "next_action": safe_str(rec.get("next_action"), "Configure/import this source before asking Civora to detect this feature type."),
            }
        )
    for key, result in safe_dict(source_results).items():
        rec = safe_dict(result)
        if rec and not rec.get("success") and safe_str(rec.get("status")) not in {"skipped"}:
            blockers.append(
                {
                    "code": f"source_{key}_unavailable",
                    "message": safe_str("; ".join(safe_str(item) for item in safe_list(rec.get("warnings")) if safe_str(item)), f"{key} source unavailable."),
                    "next_action": "Confirm source configuration or provide/import trusted project data.",
                }
            )

    return {
        "version": REPORT_VERSION,
        "status": "candidates_found" if candidates else "blocked_no_feature_source",
        "location_context": safe_dict(location_context),
        "source_discovery": source_discovery,
        "feature_candidates": candidates,
        "candidate_count": len(candidates),
        "outside_site_candidates": outside_site_candidates,
        "outside_site_candidate_count": len(outside_site_candidates),
        "blockers": blockers,
        "trusted_canonical_object_count": 0,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "engineer_review_required": True,
        "truth_label": (
            "Feature candidates are evidence for engineer/user review only. Civora prepares traceable review packages and does not act as engineer of record."
        ),
        "chat_panel_summary": _chat_panel_summary(candidates, blockers),
    }


def accept_feature_candidate_as_draft_object(candidate: Dict[str, Any], *, accepted_by: str = "user") -> Dict[str, Any]:
    rec = safe_dict(candidate)
    feature_type = safe_str(rec.get("feature_type"))
    if feature_type not in DRAFT_OBJECT_TYPES:
        raise ValueError("Unsupported feature candidate type.")
    if safe_str(rec.get("source_type")) == "unavailable":
        raise ValueError("Unavailable feature candidates cannot become draft objects.")
    return {
        "object_id": f"draft_{safe_str(rec.get('candidate_id'), 'feature')}",
        "object_type": DRAFT_OBJECT_TYPES[feature_type],
        "source_candidate_id": safe_str(rec.get("candidate_id")),
        "feature_type": feature_type,
        "geometry": rec.get("geometry"),
        "source_type": safe_str(rec.get("source_type")),
        "source_url": safe_str(rec.get("source_url")),
        "source_name": safe_str(rec.get("source_name") or rec.get("evidence_source")),
        "confidence": safe_float(rec.get("confidence")),
        "status": "draft_review_required",
        "review_required": True,
        "acceptance_status": "accepted",
        "trusted_canonical": False,
        "needs_engineer_review": True,
        "accepted_by": safe_str(accepted_by, "user"),
        "construction_release_allowed": False,
        "audit_trail": [
            {
                "action": "accepted_candidate_as_draft",
                "candidate_id": safe_str(rec.get("candidate_id")),
                "accepted_by": safe_str(accepted_by, "user"),
                "result_status": "draft_review_required",
            }
        ],
        "truth_label": "Accepted candidate became a draft/review-required object only; licensed engineer/user review remains required.",
    }


def reject_feature_candidate(candidate: Dict[str, Any], *, rejected_by: str = "user", reason: str = "") -> Dict[str, Any]:
    rec = deepcopy(safe_dict(candidate))
    audit_entry = {
        "action": "rejected_candidate",
        "candidate_id": safe_str(rec.get("candidate_id")),
        "rejected_by": safe_str(rejected_by, "user"),
        "reason": safe_str(reason, "Rejected by user/reviewer."),
    }
    audit = safe_list(rec.get("audit_trail"))
    audit.append(audit_entry)
    rec["acceptance_status"] = "rejected"
    rec["review_required"] = True
    rec["audit_trail"] = audit
    return rec


def build_source_discovery(
    *,
    source_results: Optional[Dict[str, Any]] = None,
    configured_sources: Optional[Dict[str, Any]] = None,
    gis_layers: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    configured = safe_dict(configured_sources)
    results = safe_dict(source_results)
    layers = safe_dict(gis_layers)
    discovery: Dict[str, Dict[str, Any]] = {}
    aliases = {
        "roads_row": ("roads_row", "roads", "roadways", "row", "right_of_way"),
        "building_footprints": ("building_footprints", "buildings"),
    }
    for source_type, spec in SOURCE_TYPES_REQUIRED.items():
        keys = aliases.get(source_type, (source_type,))
        layer_has_features = any(bool(_layer_features(layers.get(key))) for key in keys)
        configured_rec = _first_source_record(configured, keys)
        result_rec = _first_source_record(results, keys)
        result_status = safe_str(result_rec.get("status"))
        source_url = safe_str(configured_rec.get("source_url") or configured_rec.get("url") or configured_rec.get("service_url") or result_rec.get("source"))
        source_name = safe_str(configured_rec.get("source_name") or configured_rec.get("name") or (result_rec.get("source_type") if result_status not in {"unconfigured", "skipped"} else ""))
        result_success = bool(result_rec.get("success")) and result_status not in {"unconfigured", "skipped"}
        is_configured = layer_has_features or result_success or bool(source_url or source_name or configured_rec.get("configured") is True)
        status = "ready" if layer_has_features else "configured_no_features" if is_configured else "missing_source"
        discovery[source_type] = {
            "source_type": source_type,
            "label": spec["label"],
            "configured": is_configured,
            "status": status,
            "feature_count": sum(len(_layer_features(layers.get(key))) for key in keys),
            "source_url": source_url,
            "source_name": source_name,
            "candidate_type": spec["candidate_type"],
            "blocker": "" if is_configured else f"No configured {spec['label']} source is available.",
            "next_action": "" if is_configured else f"Configure/import a {spec['label']} GIS source before detecting {spec['label']} features.",
        }
    return discovery


def _candidate(
    *,
    feature_type: str,
    source_type: str,
    geometry: Any,
    confidence: float,
    source_url: str,
    source_name: str,
    blockers: List[str],
    review_required: bool,
    acceptance_status: str,
    seed: str,
    source_feature_id: str = "",
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = source_url or source_name or "unavailable"
    return {
        "candidate_id": f"mfd_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}",
        "feature_type": feature_type if feature_type in FEATURE_TYPES else "constraint_area",
        "geometry": geometry if geometry not in ("", {}, []) else None,
        "source_type": source_type if source_type in SOURCE_TYPES else "unavailable",
        "source_url": source_url,
        "source_name": source_name,
        "confidence": round(min(max(safe_float(confidence), 0.0), 1.0), 3),
        "review_required": bool(review_required),
        "needs_user_confirmation": bool(review_required and acceptance_status != "accepted"),
        "acceptance_status": acceptance_status if acceptance_status in {"pending", "accepted", "rejected"} else "pending",
        "evidence_source": source,
        "blockers": [safe_str(item) for item in blockers if safe_str(item)],
        "source_feature_id": source_feature_id,
        "properties": safe_dict(properties),
        "canonical_object_allowed": False,
        "draft_object_allowed_after_acceptance": True,
    }


def _site_relation(geometry: Any, boundary: Dict[str, Any]) -> str:
    if not boundary:
        return ""
    boundary_bbox = _geometry_bbox(boundary) or _bbox_from_mapping(boundary)
    candidate_bbox = _geometry_bbox(geometry) or _bbox_from_mapping(safe_dict(geometry))
    if not boundary_bbox or not candidate_bbox:
        return "site_boundary_present_unchecked"
    if _bboxes_intersect(candidate_bbox, boundary_bbox):
        return "inside_or_intersects_site"
    return "outside_site"


def _bbox_from_mapping(value: Dict[str, Any]) -> Optional[tuple[float, float, float, float]]:
    west = value.get("west", value.get("min_lng", value.get("xmin")))
    south = value.get("south", value.get("min_lat", value.get("ymin")))
    east = value.get("east", value.get("max_lng", value.get("xmax")))
    north = value.get("north", value.get("max_lat", value.get("ymax")))
    if any(item in (None, "") for item in (west, south, east, north)):
        return None
    return (safe_float(west), safe_float(south), safe_float(east), safe_float(north))


def _geometry_bbox(geometry: Any) -> Optional[tuple[float, float, float, float]]:
    rec = safe_dict(geometry)
    if not rec:
        return None
    raw_bbox = rec.get("bbox")
    if isinstance(raw_bbox, list) and len(raw_bbox) >= 4:
        return (safe_float(raw_bbox[0]), safe_float(raw_bbox[1]), safe_float(raw_bbox[2]), safe_float(raw_bbox[3]))
    if rec.get("type") == "Feature":
        return _geometry_bbox(rec.get("geometry"))
    if rec.get("type") == "FeatureCollection":
        boxes = [_geometry_bbox(feature) for feature in safe_list(rec.get("features"))]
        boxes = [box for box in boxes if box]
        if not boxes:
            return None
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
    points: List[tuple[float, float]] = []

    def collect(coords: Any) -> None:
        if (
            isinstance(coords, (list, tuple))
            and len(coords) >= 2
            and isinstance(coords[0], (int, float))
            and isinstance(coords[1], (int, float))
        ):
            points.append((safe_float(coords[0]), safe_float(coords[1])))
            return
        for item in safe_list(coords):
            collect(item)

    collect(rec.get("coordinates"))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _bboxes_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _layer_features(raw_layer: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_layer, list):
        return [safe_dict(item) for item in raw_layer if safe_dict(item)]
    layer = safe_dict(raw_layer)
    features = safe_list(layer.get("features") or layer.get("items") or layer.get("records"))
    if features:
        return [safe_dict(item) for item in features if safe_dict(item)]
    if layer.get("geometry"):
        return [layer]
    return []


def _official_source_accepted(rec: Dict[str, Any]) -> bool:
    value = (
        rec.get("accepted_for_engineering")
        or rec.get("accepted_for_project")
        or rec.get("source_accepted")
        or rec.get("user_confirmed_source")
        or rec.get("engineer_accepted_source")
    )
    return value is True


def _first_source_record(mapping: Dict[str, Any], keys: tuple[str, ...]) -> Dict[str, Any]:
    for key in keys:
        rec = safe_dict(mapping.get(key))
        if rec:
            return rec
    return {}


def _chat_panel_summary(candidates: List[Dict[str, Any]], blockers: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for candidate in candidates:
        key = safe_str(candidate.get("feature_type"), "unknown")
        counts[key] = counts.get(key, 0) + 1
    if candidates:
        first_type = next(iter(counts))
        first_label = FEATURE_TYPE_LABELS.get(first_type, first_type.replace("_", " "))
        source_phrase = "from GIS" if any(safe_str(item.get("source_type")) == "official_gis" for item in candidates) else "from uploaded imagery"
        if len(counts) == 1:
            noun = first_label if counts[first_type] == 1 else f"{first_label} candidates"
            pronoun = "it" if counts[first_type] == 1 else "them"
            message = f"I found {counts[first_type]} {noun} {source_phrase}. Do you want to use {pronoun}?"
        else:
            message = f"I found {len(candidates)} map/GIS feature candidates. Review them before use."
        return {
            "status": "candidates_found",
            "message": message,
            "candidate_counts": counts,
            "primary_feature_type": first_type,
        }
    blocker = next(
        (
            safe_dict(item)
            for item in blockers
            if safe_str(safe_dict(item).get("code")) == "missing_building_footprints_source"
        ),
        safe_dict(blockers[0]) if blockers else {},
    )
    if safe_str(blocker.get("code")) == "missing_building_footprints_source":
        message = "No building footprint source is configured."
    else:
        message = safe_str(blocker.get("message"), "I cannot detect features because no supported source is configured.")
    return {
        "status": "blocked",
        "message": message,
        "candidate_counts": {},
    }


__all__ = [
    "REPORT_VERSION",
    "accept_feature_candidate_as_draft_object",
    "build_source_discovery",
    "build_map_feature_detection_report",
    "location_context_from_geocode",
    "reject_feature_candidate",
]
