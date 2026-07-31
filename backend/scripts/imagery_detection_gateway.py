from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests


MAPBOX_STATIC_URL = "https://api.mapbox.com/styles/v1/{style}/static/{bbox}/{size}"


def build_mapbox_static_image_url(
    payload: Dict[str, Any],
    *,
    token: str,
    style: str = "mapbox/satellite-v9",
    size: str = "1024x1024",
) -> str:
    bbox = _bbox_from_payload(payload)
    if not token:
        raise ValueError("MAPBOX_TOKEN or CIVORA_GATEWAY_MAPBOX_TOKEN is required for Mapbox static imagery.")
    if not bbox:
        raise ValueError("A bbox or active_site_boundary is required to request a static imagery source.")
    bbox_text = f"[{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}]"
    params = urlencode({"access_token": token})
    return f"{MAPBOX_STATIC_URL.format(style=style, bbox=bbox_text, size=size)}?{params}"


def normalize_roboflow_response(response: Dict[str, Any], *, source_url: str = "", provider: str = "roboflow") -> List[Dict[str, Any]]:
    detections: List[Dict[str, Any]] = []
    for index, prediction in enumerate(_list(response.get("predictions"))):
        rec = _dict(prediction)
        label = str(rec.get("class") or rec.get("class_name") or rec.get("label") or rec.get("kind") or "").strip()
        if not label:
            continue
        points = _list(rec.get("points"))
        geometry: Any = None
        if points:
            ring = [
                [float(_dict(point).get("x") or 0), float(_dict(point).get("y") or 0)]
                for point in points
            ]
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            geometry = {"type": "Polygon", "coordinates": [ring]}
        x = float(rec.get("x") or 0)
        y = float(rec.get("y") or 0)
        width = float(rec.get("width") or rec.get("w") or 0)
        height = float(rec.get("height") or rec.get("h") or 0)
        bbox = [round(x - width / 2, 3), round(y - height / 2, 3), round(width, 3), round(height, 3)] if width and height else rec.get("bbox")
        detections.append(
            {
                "detection_id": str(rec.get("detection_id") or rec.get("prediction_id") or f"{provider}_{index + 1}"),
                "kind": _normalize_kind(label),
                "bbox": bbox,
                "geometry": geometry or rec.get("geometry"),
                "confidence": float(rec.get("confidence") or 0.35),
                "source_url": source_url,
                "provider": provider,
                "properties": {"raw_label": label},
            }
        )
    return detections


def normalize_generic_response(response: Dict[str, Any], *, source_url: str = "", provider: str = "generic") -> List[Dict[str, Any]]:
    raw = _list(response.get("detections") or response.get("features") or response.get("objects") or response.get("predictions"))
    detections: List[Dict[str, Any]] = []
    for index, item in enumerate(raw):
        rec = _dict(item)
        kind = str(rec.get("kind") or rec.get("feature_type") or rec.get("type") or rec.get("label") or "").strip()
        if not kind:
            continue
        detections.append(
            {
                "detection_id": str(rec.get("detection_id") or rec.get("id") or f"{provider}_{index + 1}"),
                "kind": _normalize_kind(kind),
                "bbox": rec.get("bbox") or rec.get("bounds"),
                "geometry": rec.get("geometry"),
                "confidence": float(rec.get("confidence") or 0.35),
                "source_url": str(rec.get("source_url") or source_url),
                "provider": str(rec.get("provider") or provider),
                "properties": _dict(rec.get("properties")),
            }
        )
    return detections


def run_detection_gateway(payload: Dict[str, Any], *, session: Any = requests) -> Dict[str, Any]:
    provider = os.getenv("CIVORA_GATEWAY_DETECTOR_KIND", "generic").strip().lower() or "generic"
    image_url = str(payload.get("image_url") or payload.get("source_image") or "")
    source_mode = os.getenv("CIVORA_GATEWAY_SOURCE_MODE", "mapbox_static").strip().lower()
    if not image_url and source_mode == "mapbox_static":
        image_url = build_mapbox_static_image_url(
            payload,
            token=os.getenv("CIVORA_GATEWAY_MAPBOX_TOKEN") or os.getenv("MAPBOX_TOKEN") or "",
            style=os.getenv("CIVORA_GATEWAY_MAPBOX_STYLE", "mapbox/satellite-v9"),
            size=os.getenv("CIVORA_GATEWAY_IMAGE_SIZE", "1024x1024"),
        )
    if not image_url:
        return _gateway_response(
            status="source_missing",
            provider=provider,
            source_url="",
            detections=[],
            missing=["source_image_or_static_imagery"],
            warnings=["No imagery source URL could be created for detection."],
        )
    if provider in {"civora", "civora_heuristic", "local"}:
        detections = _call_civora_detector(image_url=image_url, session=session)
        provider = "civora_heuristic"
    elif provider == "roboflow":
        response = _call_roboflow(image_url=image_url, session=session)
        detections = normalize_roboflow_response(response, source_url=image_url, provider="roboflow")
    else:
        response = _call_generic_detector(payload=payload, image_url=image_url, session=session)
        detections = normalize_generic_response(response, source_url=image_url, provider=provider)
    return _gateway_response(
        status="detected" if detections else "ready_empty",
        provider=provider,
        source_url=image_url,
        detections=detections,
        warnings=[] if detections else ["Detector returned no usable visual candidates."],
    )


def create_app() -> Any:
    try:
        from fastapi import FastAPI
    except Exception as exc:  # pragma: no cover - import-time deployment guard
        raise RuntimeError("FastAPI is required to run the imagery detection gateway.") from exc

    app = FastAPI(title="Civora Imagery Detection Gateway", version="1.0")

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"success": True, "provider": os.getenv("CIVORA_GATEWAY_DETECTOR_KIND", "generic")}

    @app.post("/detect")
    def detect(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return run_detection_gateway(payload)
        except Exception as exc:
            return _gateway_response(
                status="failed",
                provider=os.getenv("CIVORA_GATEWAY_DETECTOR_KIND", "generic"),
                source_url="",
                detections=[],
                warnings=[str(exc)],
            )

    return app


def _call_roboflow(*, image_url: str, session: Any) -> Dict[str, Any]:
    endpoint = os.getenv("ROBOFLOW_API_URL", "").strip()
    api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    if not endpoint or not api_key:
        raise ValueError("ROBOFLOW_API_URL and ROBOFLOW_API_KEY are required for Roboflow detection.")
    mode = os.getenv("ROBOFLOW_IMAGE_MODE", "url_param").strip().lower()
    if mode == "json":
        response = session.post(endpoint, json={"image": image_url, "api_key": api_key}, timeout=60)
    else:
        sep = "&" if "?" in endpoint else "?"
        response = session.post(f"{endpoint}{sep}{urlencode({'api_key': api_key, 'image': image_url})}", timeout=60)
    response.raise_for_status()
    return _dict(response.json())


def _call_civora_detector(*, image_url: str, session: Any) -> List[Dict[str, Any]]:
    try:
        from vision.feature_detection_engine import FeatureDetectionEngine
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("Civora detector could not import FeatureDetectionEngine.") from exc
    response = session.get(image_url, timeout=60)
    response.raise_for_status()
    content = getattr(response, "content", b"")
    if not content:
        raise ValueError("Source image response was empty.")
    suffix = ".jpg"
    content_type = str(getattr(response, "headers", {}).get("content-type", "")).lower()
    if "png" in content_type:
        suffix = ".png"
    elif "webp" in content_type:
        suffix = ".webp"
    with tempfile.NamedTemporaryFile(prefix="civora-imagery-", suffix=suffix, delete=False) as handle:
        handle.write(content)
        temp_path = handle.name
    try:
        result = FeatureDetectionEngine(max_size=int(os.getenv("CIVORA_GATEWAY_CIVORA_MAX_SIZE", "768") or "768")).detect(temp_path)
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
    detections: List[Dict[str, Any]] = []
    for index, detection in enumerate(result.detections):
        detections.append(
            {
                "detection_id": f"civora_{index + 1}",
                "kind": _normalize_kind(detection.kind),
                "bbox": list(detection.bbox),
                "geometry": {
                    "type": "Polygon" if detection.geometry_type == "polygon" else "LineString" if detection.geometry_type == "polyline" else "GeometryCollection",
                    "coordinates": [detection.geometry] if detection.geometry_type == "polygon" else detection.geometry,
                } if detection.geometry else None,
                "confidence": detection.confidence,
                "source_url": image_url,
                "provider": "civora_heuristic",
                "properties": {
                    "geometry_type": detection.geometry_type,
                    "detector_message": result.message,
                    "detector_warnings": result.warnings,
                    "image_width": result.image_width,
                    "image_height": result.image_height,
                },
            }
        )
    return detections


def _call_generic_detector(*, payload: Dict[str, Any], image_url: str, session: Any) -> Dict[str, Any]:
    endpoint = os.getenv("CIVORA_GATEWAY_GENERIC_DETECTOR_URL", "").strip()
    token = os.getenv("CIVORA_GATEWAY_GENERIC_DETECTOR_TOKEN", "").strip()
    if not endpoint:
        raise ValueError("CIVORA_GATEWAY_GENERIC_DETECTOR_URL is required for generic detection.")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = session.post(endpoint, json={**payload, "image_url": image_url}, headers=headers, timeout=60)
    response.raise_for_status()
    return _dict(response.json())


def _bbox_from_payload(payload: Dict[str, Any]) -> Dict[str, float]:
    for key in ("active_site_boundary", "bbox"):
        rec = _dict(payload.get(key))
        west = rec.get("west", rec.get("min_lng", rec.get("xmin")))
        south = rec.get("south", rec.get("min_lat", rec.get("ymin")))
        east = rec.get("east", rec.get("max_lng", rec.get("xmax")))
        north = rec.get("north", rec.get("max_lat", rec.get("ymax")))
        if all(value not in (None, "") for value in (west, south, east, north)):
            return {"west": float(west), "south": float(south), "east": float(east), "north": float(north)}
    return {}


def _gateway_response(
    *,
    status: str,
    provider: str,
    source_url: str,
    detections: List[Dict[str, Any]],
    missing: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "provider": provider,
        "source_url": source_url,
        "detection_count": len(detections),
        "detections": detections,
        "missing": missing or [],
        "warnings": warnings or [],
        "review_required": True,
        "truth_label": "Gateway detections are visual review candidates only, not survey/control or engineering evidence.",
    }


def _normalize_kind(value: str) -> str:
    text = value.strip().lower().replace("_", " ").replace("-", " ")
    if "building" in text or "roof" in text or "structure" in text:
        return "building"
    if "road" in text or "street" in text or "row" in text:
        return "road"
    if "drive" in text:
        return "driveway"
    if "parking" in text or "stall" in text:
        return "parking"
    if "sidewalk" in text or "path" in text:
        return "sidewalk"
    if "tree" in text or "vegetation" in text or "landscape" in text:
        return "tree"
    if "pond" in text or "basin" in text or "water" in text:
        return "basin"
    if "inlet" in text:
        return "inlet"
    if "outfall" in text:
        return "outfall"
    if "manhole" in text:
        return "manhole"
    if "hydrant" in text:
        return "hydrant"
    if "utility" in text:
        return "utility"
    return text.replace(" ", "_")


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8090")))
