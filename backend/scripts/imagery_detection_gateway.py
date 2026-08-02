from __future__ import annotations

import hashlib
import os
import ipaddress
import queue
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlsplit

import requests

from backend.planning.vision_detection_learning import (
    DETECTION_VERSION,
    FRAME_VERSION,
    build_imagery_frame_v2,
    build_vision_detection_report_v2,
    sanitize_source_url,
)
from backend.planning.vision_shadow_evaluation import (
    SHADOW_REPORT_VERSION,
    build_shadow_comparison_report,
    build_shadow_status_report,
)
from vision.model_runtime import LearnedVisionRuntime, VisionModelRuntimeError, runtime_from_environment


MAPBOX_STATIC_URL = "https://api.mapbox.com/styles/v1/{style}/static/{bbox}/{size}"
LEARNED_DETECTOR_KINDS = {"civora_model", "civora_learned", "onnx"}
HYBRID_DETECTOR_KINDS = {"civora_hybrid", "hybrid"}
HEURISTIC_DETECTOR_KINDS = {"civora", "civora_heuristic", "local"}
_RUNTIME_CACHE: Dict[tuple[str, str, str], LearnedVisionRuntime] = {}
_RUNTIME_CACHE_LOCK = threading.Lock()
_SHADOW_RUNTIME_CACHE: Dict[str, LearnedVisionRuntime] = {}
_SHADOW_RUNTIME_CACHE_LOCK = threading.Lock()
_SHADOW_QUEUE: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=4)
_SHADOW_WORKER_LOCK = threading.Lock()
_SHADOW_WORKER_STARTED = False
_SHADOW_STATS_LOCK = threading.Lock()
_SHADOW_STATS: Dict[str, Any] = {
    "submitted_count": 0,
    "completed_count": 0,
    "failed_count": 0,
    "dropped_count": 0,
    "last_completed_at": "",
    "last_report": {},
}


def gateway_health_status() -> Dict[str, Any]:
    detector_kind = os.getenv("CIVORA_GATEWAY_DETECTOR_KIND", "generic").strip().lower() or "generic"
    provider = "civora_heuristic" if detector_kind in HEURISTIC_DETECTOR_KINDS else detector_kind
    runtime_status: Dict[str, Any] = {}
    fallback_allowed = _env_true("CIVORA_GATEWAY_ALLOW_HEURISTIC_FALLBACK")
    if detector_kind in LEARNED_DETECTOR_KINDS | HYBRID_DETECTOR_KINDS:
        try:
            runtime_status = _get_learned_runtime().health(load_session=True)
        except Exception as exc:
            runtime_status = {
                "ready": False,
                "provider": "civora_learned",
                "capability_level": "model_unavailable",
                "error": str(exc),
            }
        if runtime_status.get("ready") is True:
            provider = "civora_learned"
        elif detector_kind in HYBRID_DETECTOR_KINDS and fallback_allowed:
            provider = "civora_heuristic"
    success = bool(
        runtime_status.get("ready") is True
        or detector_kind not in LEARNED_DETECTOR_KINDS | HYBRID_DETECTOR_KINDS
        or (detector_kind in HYBRID_DETECTOR_KINDS and fallback_allowed)
    )
    capability_level = (
        "learned_model_review_candidates"
        if runtime_status.get("ready") is True
        else "heuristic_visual_candidates"
        if provider == "civora_heuristic"
        else "external_model_review_candidates"
        if detector_kind in {"generic", "roboflow"}
        else "model_unavailable"
    )
    shadow_enabled = _env_true("CIVORA_GATEWAY_SHADOW_ENABLED")
    shadow_status = build_shadow_status_report("disabled", reason="shadow_inference_disabled")
    if shadow_enabled:
        try:
            shadow_health = _get_shadow_runtime().health(load_session=True)
            shadow_status = {
                **build_shadow_status_report(
                    "ready" if shadow_health.get("ready") is True else "failed",
                    reason="" if shadow_health.get("ready") is True else "shadow_model_unavailable",
                    shadow_model=shadow_health,
                ),
                "sample_rate": _shadow_sample_rate(),
                "classes": _list(shadow_health.get("classes")),
                "runtime_statistics": _shadow_runtime_statistics(),
            }
        except Exception:
            shadow_status = {
                **build_shadow_status_report("failed", reason="shadow_model_unavailable"),
                "sample_rate": _shadow_sample_rate(),
                "runtime_statistics": _shadow_runtime_statistics(),
            }
    return {
        "success": success,
        "detector_kind": detector_kind,
        "provider": provider,
        "capability_level": capability_level,
        "learned_model_ready": runtime_status.get("ready") is True,
        "heuristic_fallback_allowed": fallback_allowed,
        "detect_auth_required": bool(str(os.getenv("CIVORA_GATEWAY_BEARER_TOKEN") or "").strip()),
        "model_runtime": runtime_status,
        "imagery_frame_version": FRAME_VERSION,
        "detection_contract_version": DETECTION_VERSION,
        "model_name": runtime_status.get("model_name") or os.getenv("CIVORA_GATEWAY_MODEL_NAME") or provider,
        "model_version": runtime_status.get("model_version") or os.getenv("CIVORA_GATEWAY_MODEL_VERSION")
        or ("heuristic-v1" if provider == "civora_heuristic" else "unversioned"),
        "source_rights": {
            "license": os.getenv("CIVORA_GATEWAY_SOURCE_LICENSE") or "unconfirmed",
            "training_use_allowed": _env_true("CIVORA_GATEWAY_TRAINING_USE_ALLOWED"),
            "storage_allowed": _env_true("CIVORA_GATEWAY_SOURCE_STORAGE_ALLOWED"),
            "request_attestation_trusted": _env_true("CIVORA_GATEWAY_TRUST_REQUEST_SOURCE_RIGHTS"),
        },
        "shadow_inference": shadow_status,
    }


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
    detector_kind = provider
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
    runtime_metadata: Dict[str, Any] = {}
    detection_warnings: List[str] = []
    shadow_enabled = _env_true("CIVORA_GATEWAY_SHADOW_ENABLED")
    shadow_selected = shadow_enabled and detector_kind in HEURISTIC_DETECTOR_KINDS and _shadow_request_selected(
        payload,
        image_url=image_url,
    )
    shared_image: Optional[tuple[bytes, str]] = None
    shadow_report = build_shadow_status_report(
        "disabled" if not shadow_enabled else "not_sampled" if detector_kind in HEURISTIC_DETECTOR_KINDS else "not_run",
        reason=(
            "shadow_inference_disabled"
            if not shadow_enabled
            else "request_not_selected_for_shadow_sample"
            if detector_kind in HEURISTIC_DETECTOR_KINDS
            else "shadow_only_runs_beside_heuristic_baseline"
        ),
    )
    if provider in HEURISTIC_DETECTOR_KINDS:
        if shadow_selected:
            shared_image = _fetch_image(image_url=image_url, session=session)
        detections = _call_civora_detector(
            image_url=image_url,
            session=session,
            image_content=shared_image[0] if shared_image else None,
            content_type=shared_image[1] if shared_image else "",
        )
        provider = "civora_heuristic"
        runtime_metadata = {
            "capability_level": "heuristic_visual_candidates",
            "learned_model_used": False,
            "fallback_used": False,
        }
    elif provider in LEARNED_DETECTOR_KINDS:
        detections, runtime_metadata = _call_civora_learned_detector(
            image_url=image_url,
            session=session,
            requested_kinds=_list(payload.get("candidate_types")),
        )
        provider = "civora_learned"
    elif provider in HYBRID_DETECTOR_KINDS:
        try:
            detections, runtime_metadata = _call_civora_learned_detector(
                image_url=image_url,
                session=session,
                requested_kinds=_list(payload.get("candidate_types")),
            )
            provider = "civora_learned"
        except Exception as exc:
            if not _env_true("CIVORA_GATEWAY_ALLOW_HEURISTIC_FALLBACK"):
                raise
            detections = _call_civora_detector(image_url=image_url, session=session)
            provider = "civora_heuristic"
            runtime_metadata = {
                "capability_level": "heuristic_visual_candidates",
                "learned_model_used": False,
                "fallback_used": True,
                "fallback_reason": str(exc),
            }
            detection_warnings.append("Learned model was unavailable; explicit heuristic fallback produced these candidates.")
    elif provider == "roboflow":
        response = _call_roboflow(image_url=image_url, session=session)
        detections = normalize_roboflow_response(response, source_url=image_url, provider="roboflow")
    else:
        response = _call_generic_detector(payload=payload, image_url=image_url, session=session)
        detections = normalize_generic_response(response, source_url=image_url, provider=provider)
    if shadow_selected:
        if str(os.getenv("CIVORA_GATEWAY_SHADOW_MODE") or "async").strip().lower() == "inline":
            shadow_report = _run_shadow_comparison(
                baseline_detections=detections,
                baseline_provider=provider,
                image_url=image_url,
                image_content=shared_image[0] if shared_image else b"",
                requested_kinds=_list(payload.get("candidate_types")),
            )
        else:
            queued = _enqueue_shadow_comparison(
                baseline_detections=detections,
                baseline_provider=provider,
                image_url=image_url,
                image_content=shared_image[0] if shared_image else b"",
                requested_kinds=_list(payload.get("candidate_types")),
            )
            shadow_report = build_shadow_status_report(
                "queued" if queued else "dropped",
                reason="background_shadow_inference_queued" if queued else "shadow_queue_at_capacity",
            )
    image_width, image_height = _image_dimensions(payload, detections)
    requested_source_rights = _dict(payload.get("source_rights"))
    trust_request_source_rights = _env_true("CIVORA_GATEWAY_TRUST_REQUEST_SOURCE_RIGHTS")
    trusted_request_source_rights = requested_source_rights if trust_request_source_rights else {}
    source_rights = {
        "license": str(
            trusted_request_source_rights.get("license")
            or os.getenv("CIVORA_GATEWAY_SOURCE_LICENSE")
            or "unconfirmed"
        ),
        "attribution": str(
            trusted_request_source_rights.get("attribution")
            or os.getenv("CIVORA_GATEWAY_SOURCE_ATTRIBUTION")
            or ""
        ),
        "training_use_allowed": _env_true("CIVORA_GATEWAY_TRAINING_USE_ALLOWED")
        or trusted_request_source_rights.get("training_use_allowed") is True,
        "storage_allowed": _env_true("CIVORA_GATEWAY_SOURCE_STORAGE_ALLOWED")
        or trusted_request_source_rights.get("storage_allowed") is True,
        "rights_source": str(
            trusted_request_source_rights.get("rights_source")
            or os.getenv("CIVORA_GATEWAY_SOURCE_RIGHTS_URL")
            or ""
        ),
        "request_attestation_trusted": trust_request_source_rights,
    }
    imagery_frame = build_imagery_frame_v2(
        payload,
        source_url=image_url,
        provider=provider,
        image_width=image_width,
        image_height=image_height,
        source_rights=source_rights,
    )
    detector_metadata = {
        "provider": provider,
        "model_name": runtime_metadata.get("model_name") or os.getenv("CIVORA_GATEWAY_MODEL_NAME") or provider,
        "model_version": runtime_metadata.get("model_version") or os.getenv("CIVORA_GATEWAY_MODEL_VERSION")
        or ("heuristic-v1" if provider == "civora_heuristic" else "unversioned"),
        "model_sha256": runtime_metadata.get("model_sha256") or "",
        "detector_kind": os.getenv("CIVORA_GATEWAY_DETECTOR_KIND") or provider,
        "capability_level": runtime_metadata.get("capability_level") or (
            "external_model_review_candidates" if provider not in {"civora_heuristic"} else "heuristic_visual_candidates"
        ),
        "learned_model_used": runtime_metadata.get("learned_model_used") is True,
        "fallback_used": runtime_metadata.get("fallback_used") is True,
        "fallback_reason": runtime_metadata.get("fallback_reason") or "",
        "inference_parameters": {
            "requested_candidate_types": _list(payload.get("candidate_types")),
            "image_size": os.getenv("CIVORA_GATEWAY_IMAGE_SIZE", "1024x1024"),
            "civora_max_size": os.getenv("CIVORA_GATEWAY_CIVORA_MAX_SIZE", "768"),
        },
        "shadow_status": shadow_report.get("status"),
        "shadow_sampled": shadow_selected,
        "shadow_influenced_user_candidates": False,
    }
    vision_report = build_vision_detection_report_v2(
        detections=detections,
        imagery_frame=imagery_frame,
        provider=provider,
        detector_metadata=detector_metadata,
    )
    return _gateway_response(
        status="detected" if detections else "ready_empty",
        provider=provider,
        source_url=sanitize_source_url(image_url),
        detections=_list(vision_report.get("detections")),
        warnings=detection_warnings + ([] if detections else ["Detector returned no usable visual candidates."]),
        imagery_frame=imagery_frame,
        detector_metadata=detector_metadata,
        vision_report=vision_report,
        shadow_report=shadow_report,
    )


def create_app() -> Any:
    try:
        from fastapi import FastAPI, Header, HTTPException
        from fastapi.responses import JSONResponse
    except Exception as exc:  # pragma: no cover - import-time deployment guard
        raise RuntimeError("FastAPI is required to run the imagery detection gateway.") from exc

    app = FastAPI(title="Civora Imagery Detection Gateway", version="1.0")

    @app.get("/health")
    def health() -> Any:
        status = gateway_health_status()
        if status.get("success") is not True:
            return JSONResponse(status_code=503, content=status)
        return status

    @app.post("/detect")
    def detect(payload: Dict[str, Any], authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        expected_token = str(os.getenv("CIVORA_GATEWAY_BEARER_TOKEN") or "").strip()
        supplied_token = ""
        if authorization and authorization.lower().startswith("bearer "):
            supplied_token = authorization[7:].strip()
        if expected_token and not secrets.compare_digest(supplied_token, expected_token):
            raise HTTPException(status_code=401, detail="Imagery detection gateway authentication required.")
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


def _call_civora_detector(
    *,
    image_url: str,
    session: Any,
    image_content: Optional[bytes] = None,
    content_type: str = "",
) -> List[Dict[str, Any]]:
    try:
        from vision.feature_detection_engine import FeatureDetectionEngine
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("Civora detector could not import FeatureDetectionEngine.") from exc
    content = image_content
    if content is None:
        content, content_type = _fetch_image(image_url=image_url, session=session)
    suffix = ".jpg"
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
    return _filter_civora_detections(detections)


def _call_civora_learned_detector(
    *,
    image_url: str,
    session: Any,
    requested_kinds: Optional[List[Any]] = None,
    image_content: Optional[bytes] = None,
    runtime: Optional[LearnedVisionRuntime] = None,
    provider_name: str = "civora_learned",
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    runtime = runtime or _get_learned_runtime()
    health = runtime.health(load_session=True)
    if health.get("ready") is not True:
        raise VisionModelRuntimeError(str(health.get("error") or "Learned vision model is unavailable."))
    content = image_content
    if content is None:
        content, _ = _fetch_image(image_url=image_url, session=session)
    result = runtime.detect(content, requested_kinds=[str(item) for item in requested_kinds or []])
    detections = []
    for detection in result.detections:
        rec = dict(detection)
        rec["source_url"] = image_url
        rec["provider"] = provider_name
        detections.append(rec)
    return detections, {
        "capability_level": "shadow_model_review_candidates" if provider_name == "civora_shadow" else "learned_model_review_candidates",
        "learned_model_used": True,
        "fallback_used": False,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "model_sha256": result.model_sha256,
    }


def _fetch_image(*, image_url: str, session: Any) -> tuple[bytes, str]:
    _validate_image_url(image_url)
    try:
        response = session.get(image_url, timeout=60, stream=True)
    except TypeError:
        response = session.get(image_url, timeout=60)
    response.raise_for_status()
    final_url = str(getattr(response, "url", "") or image_url)
    _validate_image_url(final_url)
    maximum_bytes = max(1024, int(float(os.getenv("CIVORA_GATEWAY_MAX_IMAGE_BYTES") or 15 * 1024 * 1024)))
    content_length = str(getattr(response, "headers", {}).get("content-length", "")).strip()
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = 0
        if declared_length > maximum_bytes:
            raise ValueError("Source image exceeds the configured imagery gateway size limit.")
    if hasattr(response, "iter_content"):
        chunks: List[bytes] = []
        byte_count = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            byte_count += len(chunk)
            if byte_count > maximum_bytes:
                raise ValueError("Source image exceeds the configured imagery gateway size limit.")
            chunks.append(chunk)
        content = b"".join(chunks)
    else:
        content = getattr(response, "content", b"")
    if not content:
        raise ValueError("Source image response was empty.")
    if len(content) > maximum_bytes:
        raise ValueError("Source image exceeds the configured imagery gateway size limit.")
    content_type = str(getattr(response, "headers", {}).get("content-type", "")).lower()
    if content_type and not content_type.startswith("image/") and not _env_true("CIVORA_GATEWAY_ALLOW_UNKNOWN_IMAGE_CONTENT_TYPE"):
        raise ValueError("Source URL did not return an image content type.")
    return content, content_type


def _validate_image_url(value: str) -> None:
    parsed = urlsplit(str(value or "").strip())
    allow_insecure = _env_true("CIVORA_GATEWAY_ALLOW_INSECURE_IMAGE_URLS")
    if parsed.scheme not in ({"http", "https"} if allow_insecure else {"https"}):
        raise ValueError("Source image URL must use HTTPS.")
    hostname = str(parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("Source image URL is missing a host.")
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        if not _env_true("CIVORA_GATEWAY_ALLOW_PRIVATE_IMAGE_URLS"):
            raise ValueError("Private or non-routable source image addresses are not allowed.")
    allowlist = [item.strip().lower().lstrip(".") for item in str(os.getenv("CIVORA_GATEWAY_IMAGE_HOST_ALLOWLIST") or "").split(",") if item.strip()]
    if allowlist and not any(hostname == item or hostname.endswith(f".{item}") for item in allowlist):
        raise ValueError("Source image host is not in the configured gateway allowlist.")
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ) and not _env_true("CIVORA_GATEWAY_ALLOW_PRIVATE_IMAGE_URLS"):
        raise ValueError("Private or non-routable source image addresses are not allowed.")


def _get_learned_runtime() -> LearnedVisionRuntime:
    key = (
        str(os.getenv("CIVORA_GATEWAY_MODEL_MANIFEST") or ""),
        str(os.getenv("CIVORA_GATEWAY_MODEL_PATH") or ""),
        str(os.getenv("CIVORA_GATEWAY_REQUIRE_PROMOTED_MODEL") or "true"),
    )
    with _RUNTIME_CACHE_LOCK:
        runtime = _RUNTIME_CACHE.get(key)
        if runtime is None:
            runtime = runtime_from_environment()
            _RUNTIME_CACHE.clear()
            _RUNTIME_CACHE[key] = runtime
        return runtime


def _get_shadow_runtime() -> LearnedVisionRuntime:
    manifest_path = str(os.getenv("CIVORA_GATEWAY_SHADOW_MODEL_MANIFEST") or "").strip()
    if not manifest_path:
        raise VisionModelRuntimeError("Shadow model manifest is not configured.")
    with _SHADOW_RUNTIME_CACHE_LOCK:
        runtime = _SHADOW_RUNTIME_CACHE.get(manifest_path)
        if runtime is None:
            runtime = LearnedVisionRuntime(manifest_path=manifest_path, require_promoted=False)
            deployment_scope = _dict(runtime.manifest.get("deployment_scope"))
            if deployment_scope.get("shadow_only") is not True:
                raise VisionModelRuntimeError("Shadow model manifest must declare deployment_scope.shadow_only=true.")
            if deployment_scope.get("user_visible_candidates_allowed") is not False:
                raise VisionModelRuntimeError(
                    "Shadow model manifest must declare deployment_scope.user_visible_candidates_allowed=false."
                )
            _SHADOW_RUNTIME_CACHE.clear()
            _SHADOW_RUNTIME_CACHE[manifest_path] = runtime
        return runtime


def _run_shadow_comparison(
    *,
    baseline_detections: List[Dict[str, Any]],
    baseline_provider: str,
    image_url: str,
    image_content: bytes,
    requested_kinds: List[Any],
) -> Dict[str, Any]:
    try:
        shadow_runtime = _get_shadow_runtime()
        shadow_detections, shadow_metadata = _call_civora_learned_detector(
            image_url=image_url,
            session=requests,
            requested_kinds=requested_kinds,
            image_content=image_content,
            runtime=shadow_runtime,
            provider_name="civora_shadow",
        )
        shadow_health = shadow_runtime.health(load_session=False)
        return build_shadow_comparison_report(
            baseline_detections,
            shadow_detections,
            baseline_provider=baseline_provider,
            shadow_model={
                **shadow_metadata,
                "promotion_status": shadow_health.get("promotion_status") or "candidate_shadow_only",
            },
            iou_threshold=_shadow_iou_threshold(),
        )
    except Exception:
        return build_shadow_status_report("failed", reason="shadow_model_unavailable_or_inference_failed")


def _enqueue_shadow_comparison(
    *,
    baseline_detections: List[Dict[str, Any]],
    baseline_provider: str,
    image_url: str,
    image_content: bytes,
    requested_kinds: List[Any],
) -> bool:
    _ensure_shadow_worker()
    job = {
        "baseline_detections": [dict(item) for item in baseline_detections],
        "baseline_provider": baseline_provider,
        "image_url": image_url,
        "image_content": image_content,
        "requested_kinds": list(requested_kinds),
    }
    try:
        _SHADOW_QUEUE.put_nowait(job)
    except queue.Full:
        with _SHADOW_STATS_LOCK:
            _SHADOW_STATS["dropped_count"] += 1
        return False
    with _SHADOW_STATS_LOCK:
        _SHADOW_STATS["submitted_count"] += 1
    return True


def _ensure_shadow_worker() -> None:
    global _SHADOW_WORKER_STARTED
    with _SHADOW_WORKER_LOCK:
        if _SHADOW_WORKER_STARTED:
            return
        worker = threading.Thread(target=_shadow_worker_loop, name="civora-vision-shadow", daemon=True)
        worker.start()
        _SHADOW_WORKER_STARTED = True


def _shadow_worker_loop() -> None:
    while True:
        job = _SHADOW_QUEUE.get()
        try:
            try:
                report = _run_shadow_comparison(**job)
            except Exception:
                report = build_shadow_status_report("failed", reason="unexpected_shadow_worker_failure")
            with _SHADOW_STATS_LOCK:
                if report.get("status") == "ready":
                    _SHADOW_STATS["completed_count"] += 1
                else:
                    _SHADOW_STATS["failed_count"] += 1
                _SHADOW_STATS["last_completed_at"] = _now_iso()
                _SHADOW_STATS["last_report"] = report
        finally:
            _SHADOW_QUEUE.task_done()


def _shadow_runtime_statistics() -> Dict[str, Any]:
    with _SHADOW_STATS_LOCK:
        return {
            "submitted_count": int(_SHADOW_STATS["submitted_count"]),
            "completed_count": int(_SHADOW_STATS["completed_count"]),
            "failed_count": int(_SHADOW_STATS["failed_count"]),
            "dropped_count": int(_SHADOW_STATS["dropped_count"]),
            "queue_depth": _SHADOW_QUEUE.qsize(),
            "last_completed_at": str(_SHADOW_STATS["last_completed_at"]),
            "last_report": _dict(_SHADOW_STATS["last_report"]),
        }


def _shadow_request_selected(payload: Dict[str, Any], *, image_url: str) -> bool:
    if _env_true("CIVORA_GATEWAY_SHADOW_FORCE"):
        return True
    sample_rate = _shadow_sample_rate()
    if sample_rate <= 0:
        return False
    if sample_rate >= 1:
        return True
    sample_key = "|".join(
        [
            sanitize_source_url(image_url),
            str(payload.get("address") or "").strip().lower(),
            json_safe_bbox(_bbox_from_payload(payload)),
        ]
    )
    bucket = int(hashlib.sha256(sample_key.encode("utf-8")).hexdigest()[:12], 16) / float(16**12)
    return bucket < sample_rate


def _shadow_sample_rate() -> float:
    try:
        value = float(os.getenv("CIVORA_GATEWAY_SHADOW_SAMPLE_RATE") or 0.05)
    except ValueError:
        value = 0.05
    configured = max(0.0, min(1.0, value))
    maximum = 0.05
    try:
        deployment_scope = _dict(_get_shadow_runtime().manifest.get("deployment_scope"))
        maximum = max(0.0, min(1.0, float(deployment_scope.get("sample_rate_maximum", maximum))))
    except (TypeError, ValueError, VisionModelRuntimeError):
        pass
    return min(configured, maximum)


def _shadow_iou_threshold() -> float:
    try:
        value = float(os.getenv("CIVORA_GATEWAY_SHADOW_IOU_THRESHOLD") or 0.25)
    except ValueError:
        value = 0.25
    return max(0.0, min(1.0, value))


def json_safe_bbox(value: Dict[str, Any]) -> str:
    if not value:
        return ""
    return ",".join(f"{key}:{float(value[key]):.8f}" for key in ("west", "south", "east", "north"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _filter_civora_detections(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    priority = {
        "building": 11,
        "basin": 10,
        "pool": 9,
        "road": 8,
        "parking": 8,
        "sidewalk": 7,
        "driveway": 6,
        "tree": 3,
        "open_space": 2,
    }
    for detection in detections:
        bbox = _bbox_list(detection.get("bbox"))
        props = _dict(detection.get("properties"))
        image_width = float(props.get("image_width") or 0)
        image_height = float(props.get("image_height") or 0)
        kind = str(detection.get("kind") or "")
        if bbox and image_width and image_height:
            area_ratio = (bbox[2] * bbox[3]) / max(image_width * image_height, 1.0)
            if area_ratio > 0.45 and kind not in {"road"}:
                continue
            if area_ratio > 0.32 and kind in {"parking", "open_space"}:
                continue
            detection.setdefault("properties", {})["area_ratio"] = round(area_ratio, 4)
        duplicate = False
        for kept in filtered:
            if _bbox_iou(bbox, _bbox_list(kept.get("bbox"))) < 0.72:
                continue
            kept_kind = str(kept.get("kind") or "")
            if priority.get(kind, 0) > priority.get(kept_kind, 0):
                kept.update(detection)
            duplicate = True
            break
        if not duplicate:
            filtered.append(detection)
    return filtered[:24]


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
    imagery_frame: Optional[Dict[str, Any]] = None,
    detector_metadata: Optional[Dict[str, Any]] = None,
    vision_report: Optional[Dict[str, Any]] = None,
    shadow_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "provider": provider,
        "source_url": source_url,
        "detection_count": len(detections),
        "detections": detections,
        "missing": missing or [],
        "warnings": warnings or [],
        "imagery_frame": _dict(imagery_frame),
        "detector_metadata": _dict(detector_metadata),
        "civora_vision_detection_report_v2": _dict(vision_report),
        SHADOW_REPORT_VERSION: _dict(shadow_report) or build_shadow_status_report("not_run", reason="shadow_status_unavailable"),
        "review_required": True,
        "truth_label": "Gateway detections are visual review candidates only, not survey/control or engineering evidence.",
    }


def _image_dimensions(payload: Dict[str, Any], detections: List[Dict[str, Any]]) -> tuple[int, int]:
    width = int(float(payload.get("image_width") or 0))
    height = int(float(payload.get("image_height") or 0))
    for detection in detections:
        props = _dict(detection.get("properties"))
        width = width or int(float(props.get("image_width") or 0))
        height = height or int(float(props.get("image_height") or 0))
        if width and height:
            return width, height
    size = str(os.getenv("CIVORA_GATEWAY_IMAGE_SIZE") or "1024x1024").lower().split("x", 1)
    if len(size) == 2:
        try:
            width = width or int(size[0])
            height = height or int(size[1])
        except ValueError:
            pass
    return width, height


def _env_true(key: str) -> bool:
    return str(os.getenv(key) or "").strip().lower() in {"1", "true", "yes", "on"}


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
    if "pond" in text or "basin" in text or "water" in text or "pool" in text:
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


def _bbox_list(value: Any) -> List[float]:
    if not isinstance(value, list) or len(value) < 4:
        return []
    try:
        return [float(value[0]), float(value[1]), float(value[2]), float(value[3])]
    except Exception:
        return []


def _bbox_iou(a: List[float], b: List[float]) -> float:
    if len(a) < 4 or len(b) < 4:
        return 0.0
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8090")))
