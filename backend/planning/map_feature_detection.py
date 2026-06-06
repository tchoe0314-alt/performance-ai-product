from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from .common import safe_dict, safe_float, safe_list, safe_str


REPORT_VERSION = "map_feature_detection_report_v1"

FEATURE_TYPES = {
    "building_footprint",
    "road_or_drive",
    "parking_area",
    "parcel_or_site_boundary",
    "sidewalk_or_path",
    "water/pond/basin",
    "vegetation/tree_area",
    "constraint_area",
}

SOURCE_TYPES = {"official_gis", "map_imagery_detected", "inferred", "user_drawn", "unavailable"}

GIS_LAYER_FEATURE_TYPES = {
    "building_footprints": "building_footprint",
    "buildings": "building_footprint",
    "roads": "road_or_drive",
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
    "existing_utilities": "constraint_area",
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
    "sidewalk_or_path": "sidewalk",
    "water/pond/basin": "basin",
    "vegetation/tree_area": "open_space",
    "constraint_area": "constraint_area",
}


def location_context_from_geocode(*, address: str = "", geocode: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rec = safe_dict(geocode)
    lat = rec.get("lat")
    lng = rec.get("lng")
    return {
        "address": safe_str(address or rec.get("address") or rec.get("display_name") or rec.get("matched_address")),
        "matched_address": safe_str(rec.get("matched_address") or rec.get("display_name") or rec.get("place_name")),
        "geocode": {
            "lat": safe_float(lat) if lat not in (None, "") else None,
            "lng": safe_float(lng) if lng not in (None, "") else None,
            "provider": safe_str(rec.get("provider") or rec.get("source_type")),
            "source": safe_str(rec.get("source")),
            "confidence": rec.get("confidence"),
        },
        "evidence_source": safe_str(rec.get("source") or rec.get("source_type") or rec.get("provider"), "address_geocode"),
        "truth_label": "Address/geocode is location context only; it is not a site boundary, survey, control, or construction approval.",
    }


def build_map_feature_detection_report(
    *,
    location_context: Optional[Dict[str, Any]] = None,
    gis_layers: Optional[Dict[str, Any]] = None,
    image_detections: Optional[List[Dict[str, Any]]] = None,
    inferred_candidates: Optional[List[Dict[str, Any]]] = None,
    source_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    blockers: List[Dict[str, Any]] = []
    layers = safe_dict(gis_layers)
    for layer_name, raw_layer in layers.items():
        feature_type = GIS_LAYER_FEATURE_TYPES.get(safe_str(layer_name))
        if not feature_type:
            continue
        for idx, feature in enumerate(_layer_features(raw_layer)):
            rec = safe_dict(feature)
            source = safe_str(rec.get("source") or safe_dict(raw_layer).get("source"), f"gis_layer:{layer_name}")
            accepted = _official_source_accepted(rec) or _official_source_accepted(safe_dict(raw_layer))
            candidates.append(
                _candidate(
                    feature_type=feature_type,
                    source_type="official_gis",
                    geometry=rec.get("geometry"),
                    confidence=0.95 if accepted else 0.88,
                    evidence_source=source,
                    blockers=[] if accepted else ["Official GIS source is candidate evidence until the user/licensed engineer accepts the source for this project."],
                    needs_user_confirmation=not accepted,
                    seed=f"gis:{layer_name}:{idx}:{source}:{rec.get('id')}",
                    source_feature_id=safe_str(rec.get("id")),
                    properties=safe_dict(rec.get("properties")),
                )
            )

    for idx, detection in enumerate(safe_list(image_detections)):
        rec = safe_dict(detection)
        kind = safe_str(rec.get("kind") or rec.get("feature_type") or rec.get("type"))
        feature_type = IMAGE_KIND_FEATURE_TYPES.get(kind, kind if kind in FEATURE_TYPES else "")
        if not feature_type:
            continue
        confidence = min(max(safe_float(rec.get("confidence"), 0.35), 0.05), 0.7)
        candidates.append(
            _candidate(
                feature_type=feature_type,
                source_type="map_imagery_detected",
                geometry=rec.get("geometry") or rec.get("bbox"),
                confidence=confidence,
                evidence_source=safe_str(rec.get("evidence_source") or rec.get("source") or rec.get("image_path"), "map_image_detection"),
                blockers=["Map imagery detection is approximate and must be confirmed/classified before it can affect engineering objects."],
                needs_user_confirmation=True,
                seed=f"image:{idx}:{kind}:{rec.get('bbox')}:{rec.get('geometry')}",
            )
        )

    for idx, item in enumerate(safe_list(inferred_candidates)):
        rec = safe_dict(item)
        feature_type = safe_str(rec.get("feature_type"))
        if feature_type not in FEATURE_TYPES:
            continue
        candidates.append(
            _candidate(
                feature_type=feature_type,
                source_type="inferred",
                geometry=rec.get("geometry"),
                confidence=min(max(safe_float(rec.get("confidence"), 0.3), 0.05), 0.55),
                evidence_source=safe_str(rec.get("evidence_source"), "inference_without_official_source"),
                blockers=["Inferred feature candidate is not trusted engineering geometry until user confirmation and source review."],
                needs_user_confirmation=True,
                seed=f"inferred:{idx}:{feature_type}:{rec.get('geometry')}",
            )
        )

    if not candidates:
        blockers.append(
            {
                "code": "no_gis_or_imagery_feature_source",
                "message": "No official GIS layer, map imagery detection result, or user-drawn/imported feature source is available.",
                "next_action": "Upload a map image, configure/import GIS sources, or draw existing features manually.",
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
        "feature_candidates": candidates,
        "candidate_count": len(candidates),
        "blockers": blockers,
        "trusted_canonical_object_count": 0,
        "construction_release_allowed": False,
        "construction_release_blocked": True,
        "engineer_review_required": True,
        "truth_label": (
            "Feature candidates are evidence for engineer/user review. Civora does not stamp, seal, sign, certify, approve "
            "construction, submit construction documents, or act as engineer of record."
        ),
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
        "confidence": safe_float(rec.get("confidence")),
        "status": "draft_review_required",
        "trusted_canonical": False,
        "needs_engineer_review": True,
        "accepted_by": safe_str(accepted_by, "user"),
        "construction_release_allowed": False,
        "truth_label": "Accepted candidate became a draft/review-required object only; it is not construction-ready or sealed engineering truth.",
    }


def _candidate(
    *,
    feature_type: str,
    source_type: str,
    geometry: Any,
    confidence: float,
    evidence_source: str,
    blockers: List[str],
    needs_user_confirmation: bool,
    seed: str,
    source_feature_id: str = "",
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "candidate_id": f"mfd_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}",
        "feature_type": feature_type if feature_type in FEATURE_TYPES else "constraint_area",
        "geometry": geometry if geometry not in ("", {}, []) else None,
        "source_type": source_type if source_type in SOURCE_TYPES else "unavailable",
        "confidence": round(min(max(safe_float(confidence), 0.0), 1.0), 3),
        "needs_user_confirmation": bool(needs_user_confirmation),
        "evidence_source": evidence_source or "unavailable",
        "blockers": [safe_str(item) for item in blockers if safe_str(item)],
        "source_feature_id": source_feature_id,
        "properties": safe_dict(properties),
    }


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


__all__ = [
    "REPORT_VERSION",
    "accept_feature_candidate_as_draft_object",
    "build_map_feature_detection_report",
    "location_context_from_geocode",
]
