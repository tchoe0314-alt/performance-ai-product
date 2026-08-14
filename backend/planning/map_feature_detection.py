from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any, Dict, List, Optional

from .common import safe_dict, safe_float, safe_int, safe_list, safe_str
from .imagery_object_detection import build_imagery_object_detection_report
from .vision_detection_learning import DETECTION_VERSION, resolve_detection_source_conflicts, sanitize_source_url


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
    "community_mapped",
    "public_dem",
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
    "terrain_breaklines": "terrain",
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
    "surface_water": "water/pond/basin",
    "vegetation": "vegetation/tree_area",
    "tree_area": "vegetation/tree_area",
    "tree": "vegetation/tree_area",
    "trees": "vegetation/tree_area",
    "landscape": "vegetation/tree_area",
    "constraint": "constraint_area",
    "utility": "utility",
    "utilities": "utility",
    "inlet": "utility",
    "outfall": "utility",
    "manhole": "utility",
    "hydrant": "utility",
    "pole": "utility",
    "sign": "constraint_area",
    "fence": "constraint_area",
    "wall": "constraint_area",
    "retaining_wall": "constraint_area",
    "ditch": "water/pond/basin",
    "swale": "water/pond/basin",
    "building_footprint": "building_footprint",
    "road_or_drive": "road_or_drive",
}

DRAFT_OBJECT_TYPES = {
    "building_footprint": "building",
    "road_or_drive": "road",
    "parking_area": "parking",
    "parcel_or_site_boundary": "site_boundary_candidate",
    "terrain": "terrain_candidate",
    "sidewalk_or_path": "sidewalk",
    "water/pond/basin": "surface_water_candidate",
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
    "water/pond/basin": "surface water (classification required)",
    "vegetation/tree_area": "vegetation/tree area",
    "constraint_area": "constraint",
    "utility": "existing utility",
}


def location_context_from_geocode(*, address: str = "", geocode: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rec = safe_dict(geocode)
    nested_context = safe_dict(rec.get("location_context"))
    nested_jurisdiction = safe_dict(nested_context.get("jurisdiction"))
    record_jurisdiction = safe_dict(rec.get("jurisdiction"))
    lat = rec.get("lat")
    lng = rec.get("lng")
    if lat in (None, ""):
        nested_lat = safe_dict(nested_context.get("coordinates")).get("lat")
        lat = nested_lat if nested_lat not in (None, "") else safe_dict(nested_context.get("geocode")).get("lat")
    if lng in (None, ""):
        nested_lng = safe_dict(nested_context.get("coordinates")).get("lng")
        lng = nested_lng if nested_lng not in (None, "") else safe_dict(nested_context.get("geocode")).get("lng")
    matched = safe_str(rec.get("matched_address") or rec.get("display_name") or rec.get("place_name"))
    if not matched:
        matched = safe_str(nested_context.get("matched_address") or nested_context.get("normalized_address"))
    normalized = safe_str(rec.get("normalized_address") or rec.get("formatted_address") or matched or address)
    crs = safe_dict(rec.get("crs") or rec.get("coordinate_system")) or {
        "epsg": safe_str(rec.get("epsg"), "EPSG:4326" if lat not in (None, "") and lng not in (None, "") else ""),
        "name": safe_str(rec.get("crs_name"), "WGS 84 geographic coordinates" if lat not in (None, "") and lng not in (None, "") else ""),
        "units": safe_str(rec.get("units"), "degrees" if lat not in (None, "") and lng not in (None, "") else ""),
        "source": safe_str(rec.get("source") or rec.get("source_type") or rec.get("provider")),
    }
    jurisdiction = {
        "country": safe_str(rec.get("country") or record_jurisdiction.get("country") or nested_jurisdiction.get("country") or nested_context.get("country")),
        "country_code": safe_str(rec.get("country_code") or record_jurisdiction.get("country_code") or nested_jurisdiction.get("country_code") or nested_context.get("country_code")).upper(),
        "region": safe_str(rec.get("region") or record_jurisdiction.get("region") or nested_jurisdiction.get("region") or nested_context.get("region")),
        "region_code": safe_str(rec.get("region_code") or record_jurisdiction.get("region_code") or nested_jurisdiction.get("region_code") or nested_context.get("region_code")),
        "place": safe_str(rec.get("place") or record_jurisdiction.get("place") or nested_jurisdiction.get("place") or nested_context.get("place")),
        "district": safe_str(rec.get("district") or record_jurisdiction.get("district") or nested_jurisdiction.get("district") or nested_context.get("district")),
        "postcode": safe_str(rec.get("postcode") or record_jurisdiction.get("postcode") or nested_jurisdiction.get("postcode") or nested_context.get("postcode")),
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
        "jurisdiction": jurisdiction,
        **jurisdiction,
        "evidence_source": safe_str(rec.get("source") or rec.get("source_type") or rec.get("provider"), "address_geocode"),
        "evidence": [
            {
                "source_type": safe_str(rec.get("source_type") or rec.get("provider"), "address_geocode"),
                "source_url": safe_str(rec.get("source")),
                "status": safe_str(rec.get("status"), "unknown"),
                "confidence": rec.get("confidence"),
            }
        ],
        "truth_label": "Address/geocode is location context only; it is not a site boundary, survey, control, or construction authorization.",
    }


def build_map_feature_detection_report(
    *,
    location_context: Optional[Dict[str, Any]] = None,
    gis_layers: Optional[Dict[str, Any]] = None,
    image_detections: Optional[List[Dict[str, Any]]] = None,
    imagery_object_detection_report: Optional[Dict[str, Any]] = None,
    inferred_candidates: Optional[List[Dict[str, Any]]] = None,
    source_results: Optional[Dict[str, Any]] = None,
    configured_sources: Optional[Dict[str, Any]] = None,
    active_site_boundary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    outside_site_candidates: List[Dict[str, Any]] = []
    blockers: List[Dict[str, Any]] = []
    imagery_report = safe_dict(imagery_object_detection_report)
    if not imagery_report and image_detections is not None:
        imagery_report = build_imagery_object_detection_report(detections=image_detections, provider="uploaded_or_supplied_imagery")
    source_discovery = build_source_discovery(
        source_results=source_results,
        configured_sources=configured_sources,
        gis_layers=gis_layers,
        imagery_object_detection_report=imagery_report,
    )
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
            properties = safe_dict(rec.get("properties"))
            source_tier = safe_str(rec.get("source_tier") or properties.get("source_tier") or safe_dict(raw_layer).get("source_tier"))
            accepted = _official_source_accepted(rec) or _official_source_accepted(safe_dict(raw_layer))
            community_mapped = source_tier == "community_global" or "openstreetmap" in source_name.lower()
            public_dem = source_tier in {"national_public_context", "global_public_context"}
            if community_mapped:
                candidate_source_type = "community_mapped"
                candidate_confidence = 0.76
                candidate_blockers = [
                    "Community-mapped context can be incomplete or outdated and must be checked against authoritative records and project survey before reliance."
                ]
                acceptance_status = "pending"
            elif public_dem:
                candidate_source_type = "public_dem"
                candidate_confidence = 0.72 if source_tier == "national_public_context" else 0.58
                candidate_blockers = [
                    "Public DEM-derived terrain context is not project survey/control or an accepted grading surface."
                ]
                acceptance_status = "pending"
            else:
                candidate_source_type = "official_gis"
                candidate_confidence = 0.95 if accepted else 0.88
                candidate_blockers = [] if accepted else ["Official GIS source is candidate evidence until the user/licensed engineer accepts the source for this project."]
                acceptance_status = "accepted" if accepted else "pending"
            add_candidate(
                _candidate(
                    feature_type=feature_type,
                    source_type=candidate_source_type,
                    geometry=rec.get("geometry"),
                    confidence=candidate_confidence,
                    source_url=source,
                    source_name=source_name,
                    blockers=candidate_blockers,
                    review_required=True,
                    acceptance_status=acceptance_status,
                    seed=f"gis:{layer_name}:{idx}:{source or source_name}:{rec.get('id')}",
                    source_feature_id=safe_str(rec.get("id")),
                    properties=properties,
                )
            )

    elevation = safe_dict(safe_dict(source_results).get("elevation"))
    if elevation.get("success"):
        terrain_source_type = (
            "public_dem"
            if safe_str(elevation.get("source_tier")) in {"global_public_context", "national_public_context"}
            else "official_gis"
        )
        add_candidate(
            _candidate(
                feature_type="terrain",
                source_type=terrain_source_type,
                geometry={"type": "Point", "coordinates": [safe_float(elevation.get("lng")), safe_float(elevation.get("lat"))]},
                confidence=0.58 if terrain_source_type == "public_dem" else 0.72,
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
                    "horizontal_resolution": elevation.get("horizontal_resolution"),
                    "attribution": elevation.get("attribution"),
                },
            )
        )

    combined_image_detections: List[Dict[str, Any]] = []
    seen_image_detections: set[str] = set()

    def add_image_detection(value: Any) -> None:
        rec = safe_dict(value)
        if not rec:
            return
        identity_geometry = rec.get("bbox") or rec.get("pixel_geometry") or rec.get("geometry")
        identity = hashlib.sha1(
            repr((safe_str(rec.get("kind") or rec.get("feature_type") or rec.get("type")), identity_geometry)).encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()
        if identity in seen_image_detections:
            return
        seen_image_detections.add(identity)
        combined_image_detections.append(rec)

    vision_frame = safe_dict(safe_dict(imagery_report.get(DETECTION_VERSION)).get("imagery_frame"))
    for detection in safe_list(imagery_report.get("detections")):
        rec = safe_dict(detection)
        if not rec:
            continue
        add_image_detection(
            {
                "detection_id": rec.get("detection_id"),
                "kind": rec.get("kind") or rec.get("feature_type"),
                "geometry": rec.get("geo_geometry") or rec.get("geometry"),
                "pixel_geometry": rec.get("pixel_geometry") or rec.get("geometry"),
                "geo_geometry": rec.get("geo_geometry"),
                "bbox": rec.get("bbox"),
                "confidence": rec.get("confidence"),
                "source_url": rec.get("source_url"),
                "image_url": rec.get("source_image"),
                "source": rec.get("provider"),
                "image_path": rec.get("source_image"),
                "properties": rec.get("properties"),
                "imagery_frame_id": rec.get("imagery_frame_id"),
            }
        )
    for detection in safe_list(image_detections):
        add_image_detection(detection)

    for idx, detection in enumerate(combined_image_detections):
        rec = safe_dict(detection)
        kind = safe_str(rec.get("kind") or rec.get("feature_type") or rec.get("type"))
        feature_type = IMAGE_KIND_FEATURE_TYPES.get(kind, kind if kind in FEATURE_TYPES else "")
        if not feature_type:
            continue
        confidence = min(max(safe_float(rec.get("confidence"), 0.35), 0.05), 0.7)
        detection_id = safe_str(rec.get("detection_id") or rec.get("id"), f"imagery-{idx + 1}")
        raw_detection_properties = safe_dict(rec.get("properties"))
        geometry_quality = safe_dict(raw_detection_properties.get("geometry_quality_v1"))
        geometry_quality_score = safe_float(
            geometry_quality.get("quality_score") or raw_detection_properties.get("candidate_quality_score"),
            0.0,
        )
        detection_properties = {
            **raw_detection_properties,
            "vision_detection_id": detection_id,
            "imagery_frame_id": safe_str(rec.get("imagery_frame_id")),
            "pixel_geometry": rec.get("pixel_geometry"),
            "geo_geometry": rec.get("geo_geometry"),
            "source_rights": safe_dict(vision_frame.get("source_rights")),
            "outline_quality_status": safe_str(geometry_quality.get("status"), "provider_candidate"),
            "outline_quality_score": round(geometry_quality_score, 3),
            "outline_edit_supported": True,
        }
        candidate_blockers = [
            "Imagery/object detection is approximate visual context and must be reviewed before it can affect project objects.",
            "Check the detected outline against the image; redraw or reclassify it before acceptance when the edges or type are wrong.",
        ]
        add_candidate(
            _candidate(
                feature_type=feature_type,
                source_type="image_detected_candidate",
                geometry=rec.get("geo_geometry") or rec.get("geometry") or rec.get("bbox"),
                confidence=confidence,
                source_url=safe_str(rec.get("source_url") or rec.get("image_url")),
                source_name=safe_str(rec.get("evidence_source") or rec.get("source") or rec.get("image_path"), "uploaded_map_snapshot"),
                blockers=candidate_blockers,
                review_required=True,
                acceptance_status="pending",
                seed=f"image:{detection_id}:{kind}:{rec.get('bbox')}:{rec.get('geometry')}",
                source_feature_id=detection_id,
                properties=detection_properties,
            )
        )

    _ = inferred_candidates
    conflict_resolution = resolve_detection_source_conflicts(candidates)
    candidates = safe_list(conflict_resolution.get("candidates"))

    if not candidates:
        blockers.append(
            {
                "code": "no_gis_or_imagery_feature_source",
                "message": "No official GIS layer, map imagery detection result, or user-drawn/imported feature source is available. Civora will not infer buildings, roads, parcels, utilities, or terrain from an address alone.",
                "next_action": "Upload a map image, configure/import GIS sources, or draw existing features manually.",
            }
        )
    if imagery_report:
        imagery_status = safe_str(imagery_report.get("status"))
        if imagery_status in {"not_configured", "source_missing", "failed", "ready_empty"}:
            blockers.append(
                {
                    "code": f"imagery_object_detection_{imagery_status}",
                    "source_type": "imagery_object_detection",
                    "message": safe_str(imagery_report.get("message"), "Imagery/object detection did not return visual candidates."),
                    "next_action": "Connect imagery/object-detection source access or upload a source image if visual detection is needed.",
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
        if key == "imagery_object_detection":
            continue
        rec = safe_dict(result)
        if rec and not rec.get("success") and safe_str(rec.get("status")) not in {"skipped"}:
            blockers.append(
                {
                    "code": f"source_{key}_unavailable",
                    "message": safe_str("; ".join(safe_str(item) for item in safe_list(rec.get("warnings")) if safe_str(item)), f"{key} source unavailable."),
                    "next_action": "Confirm source configuration or provide/import trusted project data.",
                }
            )

    intelligence = _site_intelligence_summary(
        candidates=candidates,
        outside_site_candidates=outside_site_candidates,
        blockers=blockers,
        source_discovery=source_discovery,
        active_site_boundary=boundary,
        source_results=safe_dict(source_results),
        location_context=safe_dict(location_context),
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
        "imagery_object_detection_report_v1": imagery_report or build_imagery_object_detection_report(status="not_configured"),
        DETECTION_VERSION: safe_dict(imagery_report.get(DETECTION_VERSION)),
        "source_conflict_resolution_v1": conflict_resolution,
        "blockers": blockers,
        "trusted_canonical_object_count": 0,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "engineer_review_required": True,
        "truth_label": (
            "Feature candidates are evidence for engineer/user review only. Civora prepares traceable review packages and does not act as engineer of record."
        ),
        "chat_panel_summary": _chat_panel_summary(candidates, blockers),
        "site_intelligence_summary_v1": intelligence,
    }


def accept_feature_candidate_as_draft_object(candidate: Dict[str, Any], *, accepted_by: str = "user") -> Dict[str, Any]:
    rec = safe_dict(candidate)
    feature_type = safe_str(rec.get("feature_type"))
    if feature_type not in DRAFT_OBJECT_TYPES:
        raise ValueError("Unsupported feature candidate type.")
    if safe_str(rec.get("source_type")) == "unavailable":
        raise ValueError("Unavailable feature candidates cannot become draft objects.")
    classification_required = feature_type == "water/pond/basin"
    return {
        "object_id": f"draft_{safe_str(rec.get('candidate_id'), 'feature')}",
        "object_type": DRAFT_OBJECT_TYPES[feature_type],
        "source_candidate_id": safe_str(rec.get("candidate_id")),
        "feature_type": feature_type,
        "geometry": rec.get("geometry"),
        "source_properties": deepcopy(safe_dict(rec.get("properties"))),
        "source_type": safe_str(rec.get("source_type")),
        "source_url": safe_str(rec.get("source_url")),
        "source_name": safe_str(rec.get("source_name") or rec.get("evidence_source")),
        "confidence": safe_float(rec.get("confidence")),
        "status": "draft_review_required",
        "review_required": True,
        "acceptance_status": "accepted",
        "trusted_canonical": False,
        "needs_engineer_review": True,
        "engineering_classification_required": classification_required,
        "allowed_reclassifications": ["detention_basin", "pond", "pool", "stream", "ditch", "other_surface_water"]
        if classification_required
        else [],
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
        "truth_label": (
            "Accepted surface water remains unclassified until a reviewer assigns its engineering meaning."
            if classification_required
            else "Accepted candidate became a draft/review-required object only; licensed engineer/user review remains required."
        ),
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
    imagery_object_detection_report: Optional[Dict[str, Any]] = None,
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
    imagery = safe_dict(imagery_object_detection_report)
    if imagery:
        imagery_count = safe_int(imagery.get("detection_count"))
        imagery_status = safe_str(imagery.get("status"), "not_configured")
        configured_imagery = imagery_status not in {"", "not_configured"}
        discovery["imagery_object_detection"] = {
            "source_type": "imagery_object_detection",
            "label": "imagery/object detection",
            "configured": configured_imagery,
            "status": "ready" if imagery_count > 0 else "configured_no_features" if configured_imagery else "missing_source",
            "feature_count": imagery_count,
            "source_url": safe_str(imagery.get("source_url")),
            "source_name": safe_str(imagery.get("provider"), "imagery_object_detection"),
            "candidate_type": "image_detected_candidate",
            "blocker": "" if imagery_count > 0 else safe_str(imagery.get("message"), "Imagery/object detection returned no visual candidates."),
            "next_action": "" if imagery_count > 0 else "Connect imagery/object-detection source access or upload a source image.",
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
        "candidate_id": f"mfd_{hashlib.sha1(seed.encode('utf-8'), usedforsecurity=False).hexdigest()[:12]}",
        "feature_type": feature_type if feature_type in FEATURE_TYPES else "constraint_area",
        "geometry": geometry if geometry not in ("", {}, []) else None,
        "source_type": source_type if source_type in SOURCE_TYPES else "unavailable",
        "source_url": sanitize_source_url(source_url),
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


def _site_intelligence_summary(
    *,
    candidates: List[Dict[str, Any]],
    outside_site_candidates: List[Dict[str, Any]],
    blockers: List[Dict[str, Any]],
    source_discovery: Dict[str, Dict[str, Any]],
    active_site_boundary: Dict[str, Any],
    source_results: Dict[str, Any],
    location_context: Dict[str, Any],
) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    labels: Dict[str, str] = {}
    for candidate in candidates:
        feature_type = safe_str(candidate.get("feature_type"), "unknown")
        counts[feature_type] = counts.get(feature_type, 0) + 1
        labels[feature_type] = FEATURE_TYPE_LABELS.get(feature_type, feature_type.replace("_", " "))

    found = [
        {
            "feature_type": feature_type,
            "label": labels.get(feature_type, feature_type),
            "count": count,
            "confidence": _confidence_for_feature(candidates, feature_type),
            "source_status": "source_backed_candidate",
            "review_required": True,
        }
        for feature_type, count in sorted(counts.items())
    ]
    missing = [
        {
            "source_type": source_type,
            "label": safe_str(record.get("label"), source_type),
            "status": safe_str(record.get("status"), "missing_source"),
            "next_action": safe_str(record.get("next_action") or record.get("blocker"), "Configure/import this source before relying on automatic detection."),
        }
        for source_type, record in source_discovery.items()
        if safe_str(record.get("status")) in {"missing_source", "configured_no_features"}
    ]
    outside = [
        {
            "candidate_id": safe_str(candidate.get("candidate_id")),
            "feature_type": safe_str(candidate.get("feature_type")),
            "label": FEATURE_TYPE_LABELS.get(safe_str(candidate.get("feature_type")), safe_str(candidate.get("feature_type"))),
            "source_feature_id": safe_str(candidate.get("source_feature_id")),
            "reason": "Outside the active site boundary; ignored for generation unless the site boundary changes.",
        }
        for candidate in outside_site_candidates[:12]
    ]
    assumed: List[Dict[str, Any]] = []
    terrain_grid = safe_dict(source_results.get("terrain_grid"))
    elevation = safe_dict(source_results.get("elevation"))
    if terrain_grid.get("success"):
        assumed.append(
            {
                "key": "terrain_direction",
                "label": "Terrain/drainage context",
                "status": "public_dem_surface_context",
                "value": f"{safe_int(terrain_grid.get('sample_count'))} samples; {safe_float(terrain_grid.get('elevation_range_ft')):.1f} ft range",
                "confidence": "source-backed-review-context",
                "review_required": True,
                "message": "A public DEM surface grid is available for terrain visualization and early review; it is not project survey/control.",
            }
        )
    elif elevation.get("success"):
        assumed.append(
            {
                "key": "terrain_direction",
                "label": "Terrain/drainage direction",
                "status": "single_point_context",
                "value": f"{elevation.get('elevation')} {safe_str(elevation.get('units'), 'Feet')}".strip(),
                "confidence": "low",
                "review_required": True,
                "message": "Only one public elevation sample is available; slope direction still needs survey, DEM grid, LiDAR, or user-approved terrain.",
            }
        )
    elif safe_str(elevation.get("status")) not in {"", "skipped"}:
        assumed.append(
            {
                "key": "terrain_direction",
                "label": "Terrain/drainage direction",
                "status": safe_str(elevation.get("status")),
                "confidence": "unavailable",
                "review_required": True,
                "message": "Terrain direction could not be inferred from available sources.",
            }
        )

    road_candidates = [
        candidate
        for candidate in [*candidates, *outside_site_candidates]
        if safe_str(candidate.get("feature_type")) == "road_or_drive"
    ]
    building_candidates = [candidate for candidate in candidates if safe_str(candidate.get("feature_type")) == "building_footprint"]
    parcel_candidates = [candidate for candidate in candidates if safe_str(candidate.get("feature_type")) == "parcel_or_site_boundary"]
    boundary_bbox = _geometry_bbox(active_site_boundary) or _bbox_from_mapping(active_site_boundary)
    road_frontage = _road_frontage_hint(road_candidates=road_candidates, boundary_bbox=boundary_bbox)
    suggested_site_box = _suggested_site_box_hint(boundary_bbox=boundary_bbox, parcel_candidates=parcel_candidates, location_context=location_context)
    driveway_suggestions = _driveway_suggestion_hints(road_candidates=road_candidates, boundary_bbox=boundary_bbox)
    grading_context = _grading_context_hint(terrain_grid=terrain_grid, elevation=elevation, boundary_bbox=boundary_bbox)
    confidence_labels = _confidence_labels(found=found, missing=missing, assumed=assumed, outside=outside)
    one_sentence = _site_intelligence_sentence(
        found=found,
        missing=missing,
        assumed=assumed,
        outside=outside,
        has_boundary=bool(boundary_bbox),
        building_count=len(building_candidates),
    )

    return {
        "version": "site_intelligence_summary_v1",
        "status": "ready_for_review" if found or assumed else "missing_sources",
        "one_sentence": one_sentence,
        "found": found,
        "missing": missing,
        "assumed": assumed,
        "outside_site": outside,
        "road_frontage": road_frontage,
        "driveway_suggestions": driveway_suggestions,
        "suggested_site_box": suggested_site_box,
        "grading_context": grading_context,
        "confidence_labels": confidence_labels,
        "blockers": [safe_str(item.get("message")) for item in blockers if safe_str(safe_dict(item).get("message"))][:12],
        "review_required": True,
        "survey_control_satisfied": False,
        "construction_release_allowed": False,
        "truth_label": "Auto Site Intelligence summarizes source-backed candidates and assumptions only; it is not survey/control, utility locate, professional authorization, certification, or construction release evidence.",
    }


def _confidence_for_feature(candidates: List[Dict[str, Any]], feature_type: str) -> str:
    values = [safe_float(candidate.get("confidence"), 0.0) for candidate in candidates if safe_str(candidate.get("feature_type")) == feature_type]
    if not values:
        return "unavailable"
    average = sum(values) / len(values)
    if average >= 0.85:
        return "source-backed"
    if average >= 0.65:
        return "medium"
    return "low"


def _road_frontage_hint(*, road_candidates: List[Dict[str, Any]], boundary_bbox: Optional[tuple[float, float, float, float]]) -> Dict[str, Any]:
    if not road_candidates:
        return {
            "status": "missing",
            "message": "No road/ROW candidate was found, so frontage and driveway side were not inferred.",
            "review_required": True,
        }
    if not boundary_bbox:
        return {
            "status": "candidate_without_site_box",
            "candidate_count": len(road_candidates),
            "message": "Road candidates were found, but no active site boundary was available to infer frontage side.",
            "review_required": True,
        }
    side_counts: Dict[str, int] = {"west": 0, "east": 0, "south": 0, "north": 0}
    for candidate in road_candidates:
        box = _geometry_bbox(candidate.get("geometry")) or _bbox_from_mapping(safe_dict(candidate.get("geometry")))
        if not box:
            continue
        side = _nearest_bbox_side(box, boundary_bbox)
        side_counts[side] = side_counts.get(side, 0) + 1
    side = max(side_counts, key=lambda item: side_counts[item]) if any(side_counts.values()) else "unknown"
    return {
        "status": "candidate",
        "candidate_count": len(road_candidates),
        "likely_frontage_side": side,
        "confidence": "medium" if side != "unknown" else "low",
        "message": f"Likely road frontage is on the {side} side based on source candidates." if side != "unknown" else "Road candidates were found, but frontage side could not be inferred from geometry.",
        "review_required": True,
    }


def _driveway_suggestion_hints(*, road_candidates: List[Dict[str, Any]], boundary_bbox: Optional[tuple[float, float, float, float]]) -> List[Dict[str, Any]]:
    frontage = _road_frontage_hint(road_candidates=road_candidates, boundary_bbox=boundary_bbox)
    side = safe_str(frontage.get("likely_frontage_side"))
    if safe_str(frontage.get("status")) != "candidate" or side in {"", "unknown"}:
        return [
            {
                "status": "blocked_missing_frontage",
                "message": "Add/confirm road frontage before Civora can suggest a driveway side.",
                "review_required": True,
            }
        ]
    return [
        {
            "status": "candidate",
            "label": f"Review driveway along {side} frontage",
            "frontage_side": side,
            "confidence": safe_str(frontage.get("confidence"), "medium"),
            "message": "Use this as a starting suggestion only; confirm access spacing, sight distance, and jurisdiction standards.",
            "review_required": True,
        }
    ]


def _suggested_site_box_hint(
    *,
    boundary_bbox: Optional[tuple[float, float, float, float]],
    parcel_candidates: List[Dict[str, Any]],
    location_context: Dict[str, Any],
) -> Dict[str, Any]:
    if boundary_bbox:
        return {
            "status": "active_site_boundary",
            "source": "locked_or_draft_site_boundary",
            "bbox": {"west": boundary_bbox[0], "south": boundary_bbox[1], "east": boundary_bbox[2], "north": boundary_bbox[3]},
            "message": "Using the active site boundary for inside/outside filtering.",
            "review_required": True,
        }
    if parcel_candidates:
        first_bbox = _geometry_bbox(parcel_candidates[0].get("geometry"))
        return {
            "status": "parcel_candidate",
            "source": "parcel_candidate",
            "bbox": {"west": first_bbox[0], "south": first_bbox[1], "east": first_bbox[2], "north": first_bbox[3]} if first_bbox else {},
            "message": "Use the parcel candidate as a starting site box only after review.",
            "review_required": True,
        }
    coords = safe_dict(location_context.get("coordinates"))
    if coords.get("lat") is not None and coords.get("lng") is not None:
        return {
            "status": "address_center_only",
            "source": "geocode",
            "center": {"lat": coords.get("lat"), "lng": coords.get("lng")},
            "message": "No parcel/site boundary candidate was found; start from the geocode center and draw or size the site.",
            "review_required": True,
        }
    return {
        "status": "missing",
        "message": "No address, parcel, or active site boundary is available for a suggested site box.",
        "review_required": True,
    }


def _grading_context_hint(
    *,
    terrain_grid: Dict[str, Any],
    elevation: Dict[str, Any],
    boundary_bbox: Optional[tuple[float, float, float, float]],
) -> Dict[str, Any]:
    if terrain_grid.get("success"):
        return {
            "status": "public_dem_surface_context",
            "source": safe_str(terrain_grid.get("source_type"), "public_dem_elevation_grid"),
            "sample_count": safe_int(terrain_grid.get("sample_count")),
            "min_elevation_ft": terrain_grid.get("min_elevation_ft"),
            "max_elevation_ft": terrain_grid.get("max_elevation_ft"),
            "elevation_range_ft": terrain_grid.get("elevation_range_ft"),
            "horizontal_resolution": terrain_grid.get("horizontal_resolution"),
            "vertical_datum": terrain_grid.get("vertical_datum"),
            "confidence": "source-backed-review-context",
            "message": "Public DEM samples support terrain visualization and preliminary drainage context, not survey-controlled grading.",
            "next_action": "Review the DEM source and replace or confirm it with project survey/control before production grading reliance.",
            "review_required": True,
            "site_boundary_present": bool(boundary_bbox),
        }
    if elevation.get("success"):
        return {
            "status": "single_point_elevation",
            "source": safe_str(elevation.get("source_type"), "usgs_3dep_epqs"),
            "elevation": elevation.get("elevation"),
            "units": safe_str(elevation.get("units"), "Feet"),
            "confidence": "low",
            "message": "Public point elevation gives vertical context, not a grading surface or drainage direction.",
            "next_action": "Add survey/topo, DEM grid, LiDAR, or an explicit review assumption before relying on grading direction.",
            "review_required": True,
            "site_boundary_present": bool(boundary_bbox),
        }
    return {
        "status": safe_str(elevation.get("status"), "missing"),
        "confidence": "unavailable",
        "message": "No terrain/elevation context is available yet.",
        "next_action": "Upload survey/topo, configure terrain sources, or use an explicit assumed slope for review.",
        "review_required": True,
        "site_boundary_present": bool(boundary_bbox),
    }


def _nearest_bbox_side(candidate: tuple[float, float, float, float], boundary: tuple[float, float, float, float]) -> str:
    candidate_x = (candidate[0] + candidate[2]) / 2.0
    candidate_y = (candidate[1] + candidate[3]) / 2.0
    distances = {
        "west": abs(candidate_x - boundary[0]),
        "east": abs(candidate_x - boundary[2]),
        "south": abs(candidate_y - boundary[1]),
        "north": abs(candidate_y - boundary[3]),
    }
    return min(distances, key=distances.get)


def _confidence_labels(*, found: List[Dict[str, Any]], missing: List[Dict[str, Any]], assumed: List[Dict[str, Any]], outside: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    labels = [
        {"label": "Found", "count": len(found), "meaning": "Source-backed candidates that still need review."},
        {"label": "Missing", "count": len(missing), "meaning": "Sources absent, failed, or returned no usable features."},
        {"label": "Assumed", "count": len(assumed), "meaning": "Helpful context or assumptions, not source proof."},
        {"label": "Outside site", "count": len(outside), "meaning": "Candidates outside the active site boundary; ignored unless boundary changes."},
    ]
    return labels


def _site_intelligence_sentence(
    *,
    found: List[Dict[str, Any]],
    missing: List[Dict[str, Any]],
    assumed: List[Dict[str, Any]],
    outside: List[Dict[str, Any]],
    has_boundary: bool,
    building_count: int,
) -> str:
    if found:
        found_labels = ", ".join(safe_str(item.get("label")) for item in found[:3] if safe_str(item.get("label")))
        suffix = " inside the active site" if has_boundary else " near the address"
        if building_count:
            return f"Found {found_labels}{suffix}; buildings and other source candidates stay review-required."
        return f"Found {found_labels}{suffix}; review missing and assumed items before generating."
    if assumed:
        return "No source-backed site features were found yet; only review assumptions/context are available."
    if missing:
        return "No source-backed site features were found because required providers are missing, unavailable, or empty."
    if outside:
        return "Source candidates were found outside the active site boundary and are ignored for generation."
    return "Apply an address, configure/import sources, or draw the site to build Auto Site Intelligence."


__all__ = [
    "REPORT_VERSION",
    "accept_feature_candidate_as_draft_object",
    "build_source_discovery",
    "build_map_feature_detection_report",
    "location_context_from_geocode",
    "reject_feature_candidate",
]
