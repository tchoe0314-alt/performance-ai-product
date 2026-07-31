from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from .common import safe_dict, safe_float, safe_list, safe_str


REPORT_VERSION = "imagery_object_detection_report_v1"


def build_imagery_object_detection_report(
    *,
    detections: Optional[List[Dict[str, Any]]] = None,
    provider: str = "",
    source_url: str = "",
    source_image: str = "",
    status: str = "",
    message: str = "",
    missing: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    normalized = [_normalize_detection(item, index, provider=provider, source_url=source_url, source_image=source_image) for index, item in enumerate(safe_list(detections))]
    normalized = [item for item in normalized if item]
    state = safe_str(status) or ("detected" if normalized else "ready_empty" if provider or source_url else "not_configured")
    missing_items = [safe_str(item) for item in safe_list(missing) if safe_str(item)]
    if state == "not_configured" and "imagery_object_detection_provider" not in missing_items:
        missing_items.append("imagery_object_detection_provider")
    if state in {"source_missing", "not_configured"} and "imagery_source_or_tile_access" not in missing_items:
        missing_items.append("imagery_source_or_tile_access")
    return {
        "version": REPORT_VERSION,
        "status": state,
        "provider": safe_str(provider, "unconfigured"),
        "source_url": safe_str(source_url),
        "source_image": safe_str(source_image),
        "detection_count": len(normalized),
        "detections": normalized,
        "missing": missing_items,
        "warnings": [safe_str(item) for item in safe_list(warnings) if safe_str(item)],
        "message": safe_str(message) or _message_for_status(state, len(normalized)),
        "review_required": True,
        "survey_control_satisfied": False,
        "canonical_geometry_allowed": False,
        "truth_label": "Imagery/object detection creates visual review candidates only; verify against survey, source files, utility records, and professional review before relying on it.",
    }


def fetch_imagery_object_detection(
    *,
    address: str = "",
    bbox: Optional[Dict[str, Any]] = None,
    location_context: Optional[Dict[str, Any]] = None,
    active_site_boundary: Optional[Dict[str, Any]] = None,
    provider_url: str = "",
    provider_token: str = "",
    provider_name: str = "",
    session: Any = requests,
) -> Dict[str, Any]:
    url = safe_str(provider_url)
    name = safe_str(provider_name, "configured_imagery_object_detector" if url else "unconfigured")
    if not url:
        return build_imagery_object_detection_report(
            provider=name,
            status="not_configured",
            missing=["imagery_object_detection_provider", "imagery_source_or_tile_access"],
            message="Imagery/object detection is not configured; Civora will use GIS/source candidates and uploaded-image detections only.",
        )
    payload = {
        "address": safe_str(address),
        "bbox": safe_dict(bbox),
        "location_context": safe_dict(location_context),
        "active_site_boundary": safe_dict(active_site_boundary),
        "candidate_types": [
            "building",
            "road",
            "driveway",
            "parking",
            "sidewalk",
            "tree",
            "vegetation",
            "basin",
            "pond",
            "utility",
            "inlet",
            "outfall",
            "manhole",
            "hydrant",
            "fence",
            "wall",
            "pole",
            "sign",
            "retaining_wall",
            "ditch",
            "swale",
        ],
        "truth_mode": "review_candidates_only",
    }
    headers = {"Authorization": f"Bearer {provider_token}"} if safe_str(provider_token) else {}
    try:
        response = session.post(url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        data = safe_dict(response.json())
    except Exception as exc:
        return build_imagery_object_detection_report(
            provider=name,
            source_url=url,
            status="failed",
            warnings=[safe_str(exc)],
            message="Imagery/object detection could not complete; GIS/source candidates are still usable where available.",
        )
    detections = safe_list(data.get("detections") or data.get("features") or data.get("objects"))
    return build_imagery_object_detection_report(
        detections=detections,
        provider=safe_str(data.get("provider"), name),
        source_url=safe_str(data.get("source_url") or data.get("imagery_url") or url),
        source_image=safe_str(data.get("source_image") or data.get("image_url")),
        status=safe_str(data.get("status")) or ("detected" if detections else "ready_empty"),
        message=safe_str(data.get("message")),
        missing=safe_list(data.get("missing")),
        warnings=safe_list(data.get("warnings")),
    )


def _normalize_detection(
    detection: Dict[str, Any],
    index: int,
    *,
    provider: str,
    source_url: str,
    source_image: str,
) -> Dict[str, Any]:
    rec = safe_dict(detection)
    kind = safe_str(rec.get("kind") or rec.get("feature_type") or rec.get("type") or rec.get("label"))
    if not kind:
        return {}
    geometry = rec.get("geometry") or rec.get("bbox") or rec.get("bounds")
    confidence = min(max(safe_float(rec.get("confidence"), 0.35), 0.05), 0.92)
    return {
        "detection_id": safe_str(rec.get("detection_id") or rec.get("id"), f"imagery_{index + 1}"),
        "kind": kind,
        "geometry": geometry,
        "bbox": rec.get("bbox") or rec.get("bounds"),
        "confidence": round(confidence, 3),
        "source_url": safe_str(rec.get("source_url") or rec.get("image_url") or source_url),
        "source_image": safe_str(rec.get("source_image") or rec.get("image_path") or source_image),
        "provider": safe_str(rec.get("provider") or rec.get("source") or provider, "imagery_object_detection"),
        "properties": safe_dict(rec.get("properties")),
        "review_required": True,
        "accepted": False,
    }


def _message_for_status(status: str, count: int) -> str:
    if status == "detected" and count:
        return f"Imagery/object detection found {count} visual review candidate{'s' if count != 1 else ''}."
    if status == "ready_empty":
        return "Imagery/object detection ran but returned no usable visual candidates."
    if status == "failed":
        return "Imagery/object detection could not complete."
    if status == "source_missing":
        return "Imagery/object detection needs imagery source access."
    return "Imagery/object detection is not configured."


__all__ = ["REPORT_VERSION", "build_imagery_object_detection_report", "fetch_imagery_object_detection"]
