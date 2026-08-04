from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Callable, Dict, Mapping, Optional

from fastapi import HTTPException

from backend.ai.image_provider import (
    ImageProvider,
    build_image_provider,
    image_provider_status,
)
from backend.planning.ai_visualization_reference import render_ai_visualization_reference


MAX_SOURCE_OBJECTS = 300
MAX_GEOMETRY_POINTS_PER_OBJECT = 800
MAX_TOTAL_GEOMETRY_POINTS = 20_000
MAX_GENERATED_IMAGE_BYTES = 15 * 1024 * 1024
AI_VISUALIZATION_WATERMARK = (
    "AI visualization from current review layout - visual concept only, not engineering evidence."
)


def _finite_number(value: Any, *, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _clean_text(value: Any, *, limit: int = 160) -> str:
    return " ".join(str(value or "").split())[:limit]


def _clean_object_type(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "_", _clean_text(value, limit=64).lower()).strip("_")
    return normalized[:64] or "custom"


def _normalize_source_object(raw: Mapping[str, Any]) -> Dict[str, Any]:
    geometry: list[list[float]] = []
    for point in list(raw.get("geometry") or [])[:MAX_GEOMETRY_POINTS_PER_OBJECT]:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        x = _finite_number(point[0], default=float("nan"))
        y = _finite_number(point[1], default=float("nan"))
        if isfinite(x) and isfinite(y):
            geometry.append([round(x, 4), round(y, 4)])
    return {
        "id": _clean_text(raw.get("id"), limit=128),
        "label": _clean_text(raw.get("label") or raw.get("id") or "Object"),
        "type": _clean_object_type(raw.get("type") or "custom"),
        "x": round(_finite_number(raw.get("x")), 4),
        "y": round(_finite_number(raw.get("y")), 4),
        "w": round(max(0.0, _finite_number(raw.get("w"))), 4),
        "d": round(max(0.0, _finite_number(raw.get("d"))), 4),
        "h": round(max(0.0, _finite_number(raw.get("h"))), 4),
        "rotation": round(_finite_number(raw.get("rotation")), 4),
        "geometryType": _clean_text(raw.get("geometryType") or raw.get("geometry_type") or "rect", limit=32),
        "geometry": geometry,
        "roofProfile": _clean_text(raw.get("roofProfile") or "flat", limit=40),
        "stallCount": int(max(0.0, _finite_number(raw.get("stallCount")))) if raw.get("stallCount") is not None else None,
        "source": _clean_text(raw.get("source") or "unknown", limit=64),
        "confidence": raw.get("confidence") if isinstance(raw.get("confidence"), (int, float)) else None,
    }


def normalize_ai_visualization_request(payload: Mapping[str, Any]) -> Dict[str, Any]:
    source_layout_hash = _clean_text(payload.get("source_layout_hash"), limit=128)
    if not source_layout_hash or not re.fullmatch(r"[A-Za-z0-9_.:-]{4,128}", source_layout_hash):
        raise HTTPException(status_code=422, detail="A valid source layout hash is required.")

    raw_objects = list(payload.get("source_objects") or [])
    if not raw_objects:
        raise HTTPException(
            status_code=422,
            detail="Add or generate proposed design objects before creating AI visualization.",
        )
    if len(raw_objects) > MAX_SOURCE_OBJECTS:
        raise HTTPException(
            status_code=422,
            detail=f"AI visualization supports at most {MAX_SOURCE_OBJECTS} proposed objects per request.",
        )
    if not all(isinstance(item, Mapping) for item in raw_objects):
        raise HTTPException(status_code=422, detail="AI visualization source objects must be structured records.")
    source_objects = [_normalize_source_object(item) for item in raw_objects]
    total_geometry_points = sum(len(item["geometry"]) for item in source_objects)
    if total_geometry_points > MAX_TOTAL_GEOMETRY_POINTS:
        raise HTTPException(
            status_code=422,
            detail="AI visualization geometry is too dense. Simplify the visual reference and retry.",
        )

    site_frame = dict(payload.get("site_frame") or {})
    width_ft = _finite_number(site_frame.get("width_ft"))
    height_ft = _finite_number(site_frame.get("height_ft"))
    if not (1.0 <= width_ft <= 100_000.0 and 1.0 <= height_ft <= 100_000.0):
        raise HTTPException(status_code=422, detail="Site width and height must be between 1 ft and 100,000 ft.")

    summary = dict(payload.get("source_objects_summary") or {})
    missing_inputs = [
        _clean_text(item, limit=160)
        for item in list(payload.get("missing_inputs") or [])[:30]
        if _clean_text(item, limit=160)
    ]
    geocode = dict(payload.get("geocode") or {})
    lat = _finite_number(geocode.get("lat"), default=float("nan"))
    lng = _finite_number(geocode.get("lng"), default=float("nan"))
    map_context_available = isfinite(lat) and isfinite(lng)
    return {
        "source_layout_hash": source_layout_hash,
        "source_objects": source_objects,
        "source_objects_summary": {
            "total": len(source_objects),
            "objects_included": [
                _clean_text(item, limit=160)
                for item in list(summary.get("objects_included") or [])[:MAX_SOURCE_OBJECTS]
            ],
            "counts_by_type": {
                _clean_object_type(key): int(max(0, _finite_number(value)))
                for key, value in dict(summary.get("counts_by_type") or {}).items()
            },
        },
        "missing_inputs": missing_inputs,
        "site_frame": {
            "width_ft": width_ft,
            "height_ft": height_ft,
            "rotation_deg": _finite_number(site_frame.get("rotation_deg")),
            "map_context_available": map_context_available,
        },
        "geocode": {"lat": lat, "lng": lng} if map_context_available else {},
        "visual_style": _clean_text(payload.get("visual_style") or "orthographic aerial site concept", limit=80),
    }


def build_ai_visualization_prompt(payload: Mapping[str, Any]) -> str:
    source_objects = list(payload.get("source_objects") or [])
    type_counts: Dict[str, int] = {}
    heights: list[str] = []
    for item in source_objects:
        object_type = _clean_object_type(item.get("type") or "custom")
        type_counts[object_type] = type_counts.get(object_type, 0) + 1
        if "building" in object_type and _finite_number(item.get("h")) > 0:
            heights.append(f"{_finite_number(item.get('h')):.0f} ft")
    inventory = ", ".join(f"{count} {name}" for name, count in sorted(type_counts.items()))
    height_note = "; ".join(heights[:20]) or "use restrained one-story massing where height is unspecified"
    return (
        "Create a polished photorealistic orthographic aerial visualization of this proposed civil site layout. "
        "Use the attached plan reference as the controlling composition guide. Preserve every footprint, path, "
        "relative position, orientation, and site-boundary relationship as closely as image generation allows. "
        "Do not add, remove, duplicate, relocate, merge, or resize major site objects. Do not invent buildings or roads. "
        "Render buildings with realistic roofs and shadows, paved roads and driveways, legible parking striping, "
        "landscape materials, and natural detention-basin treatment. Keep underground utilities visually subtle. "
        "Use realistic daylight, materials, and vegetation suitable for a professional site-design concept. "
        "Avoid labels, dimensions, logos, legends, property text, decorative borders, dramatic perspective, and fantasy architecture. "
        f"Site dimensions are {payload['site_frame']['width_ft']:.1f} ft by {payload['site_frame']['height_ft']:.1f} ft. "
        f"Object inventory: {inventory}. Building heights: {height_note}. "
        "The result is a visual concept only; technical linework remains the authoritative layout."
    )


def queue_ai_visualization_job(
    *,
    project_store: Any,
    job_queue: Any,
    user_id: str,
    project_id: Optional[str],
    request_payload: Mapping[str, Any],
    provider_status: Callable[[], Mapping[str, Any]] = image_provider_status,
) -> Dict[str, Any]:
    status = dict(provider_status())
    if not status.get("configured"):
        raise HTTPException(status_code=503, detail=str(status.get("reason") or "External image provider is unavailable."))
    if project_id and project_store.get_project(user_id=user_id, project_id=project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    normalized = normalize_ai_visualization_request(request_payload)
    job = job_queue.submit_job(
        user_id=user_id,
        job_type="ai_visualization",
        payload=normalized,
        project_id=project_id,
    )
    return {
        "success": True,
        "job": job,
        "provider": {
            "name": status.get("provider"),
            "model": status.get("model"),
            "external": True,
        },
        "operational_summary": {
            "status": str(job.get("status") or "queued"),
            "job_type": "ai_visualization",
            "job_id": job.get("job_id"),
            "project_id": project_id,
            "retryable": True,
            "visualization_only": True,
            "not_engineering_evidence": True,
        },
    }


def build_ai_visualization_job_runner(
    *,
    update_job_progress: Callable[..., None],
    provider_factory: Callable[[], ImageProvider] = build_image_provider,
    reference_renderer: Callable[..., bytes] = render_ai_visualization_reference,
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def runner(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = normalize_ai_visualization_request(dict(job.get("payload") or {}))
        job_id = str(job.get("job_id") or "")
        if job_id:
            update_job_progress(
                job_id,
                stage="Preparing Visual Reference",
                detail="Building a bounded image reference from the current canonical site layout.",
                progress=30,
            )
        reference_png = reference_renderer(
            site_width_ft=payload["site_frame"]["width_ft"],
            site_height_ft=payload["site_frame"]["height_ft"],
            source_objects=payload["source_objects"],
        )
        if job_id:
            update_job_progress(
                job_id,
                stage="Generating Photorealistic Visualization",
                detail="The external image provider is rendering a visual concept. This can take up to two minutes.",
                progress=58,
            )
        generated = provider_factory().generate(
            prompt=build_ai_visualization_prompt(payload),
            reference_png=reference_png,
            user_id=str(job.get("user_id") or ""),
        )
        try:
            decoded_image = base64.b64decode(generated.image_base64, validate=True)
        except Exception as exc:
            raise RuntimeError("The external visualization provider returned invalid image data.") from exc
        if not decoded_image or len(decoded_image) > MAX_GENERATED_IMAGE_BYTES:
            raise RuntimeError(
                "The external visualization image is empty or exceeds the 15 MB result limit."
            )
        if job_id:
            update_job_progress(
                job_id,
                stage="Finalizing Visualization",
                detail="Attaching source and freshness metadata to the visual concept.",
                progress=92,
            )
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        artifact = {
            "type": "high_quality_ai_render_v2",
            "project_id": str(job.get("project_id") or "unsaved-review-layout"),
            "source_layout_hash": payload["source_layout_hash"],
            "site_frame": payload["site_frame"],
            "source_objects_summary": payload["source_objects_summary"],
            "missing_inputs": payload["missing_inputs"],
            "stale": False,
            "generated_timestamp": timestamp,
            "review_only": True,
            "not_site_evidence": True,
            "construction_release_allowed": False,
            "visualization_only": True,
            "not_engineering_evidence": True,
            "renderer": "external",
            "provider": generated.provider,
            "model": generated.model,
            "request_id": generated.request_id,
            "mime_type": generated.mime_type,
            "map_context_used": False,
            "image_data_url": f"data:{generated.mime_type};base64,{generated.image_base64}",
            "watermark": AI_VISUALIZATION_WATERMARK,
        }
        return {
            "success": True,
            "artifact": artifact,
            "metadata": {
                "visualization_only": True,
                "not_engineering_evidence": True,
                "source_layout_hash": payload["source_layout_hash"],
                "provider": generated.provider,
                "model": generated.model,
            },
        }

    return runner
