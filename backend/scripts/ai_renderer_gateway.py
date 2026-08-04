from __future__ import annotations

import base64
import hmac
import os
import threading
from io import BytesIO
from typing import Any, Literal, Mapping, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from backend.ai.hybrid_renderer_engine import (
    HybridRendererEngine,
    HybridRendererError,
    build_hybrid_renderer_engine,
)


RENDER_CONTRACT = "civora_hybrid_render_v1"
MAX_ENCODED_IMAGE_CHARACTERS = 12_000_000
MAX_DECODED_IMAGE_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 4_000_000
MAX_REQUEST_BYTES = 40 * 1024 * 1024
MIN_SERVICE_TOKEN_LENGTH = 32
SUPPORTED_INPUT_FORMATS = {"JPEG", "PNG", "WEBP"}
SUPPORTED_OUTPUT_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class HybridRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: str = Field(max_length=64)
    request_id: str = Field(min_length=1, max_length=128)
    source_layout_hash: str = Field(min_length=4, max_length=128)
    prompt: str = Field(min_length=1, max_length=4_000)
    negative_prompt: str = Field(default="", max_length=2_000)
    reference_image_base64: str = Field(max_length=MAX_ENCODED_IMAGE_CHARACTERS)
    control_image_base64: str = Field(max_length=MAX_ENCODED_IMAGE_CHARACTERS)
    depth_image_base64: str = Field(max_length=MAX_ENCODED_IMAGE_CHARACTERS)
    output_format: Literal["webp", "png", "jpeg"] = "webp"
    seed: int = Field(default=0, ge=0, le=2**32 - 1)
    user_fingerprint: str = Field(default="", max_length=64)
    map_context_included: bool = False


def _decode_image(value: str, *, label: str) -> Image.Image:
    try:
        payload = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"{label} is not valid base64 image data.") from exc
    if not payload or len(payload) > MAX_DECODED_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail=f"{label} is empty or exceeds the 8 MB limit.")
    try:
        image = Image.open(BytesIO(payload))
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise HTTPException(status_code=422, detail=f"{label} exceeds the pixel limit.")
        if str(image.format or "").upper() not in SUPPORTED_INPUT_FORMATS:
            raise HTTPException(status_code=422, detail=f"{label} must be PNG, JPEG, or WebP.")
        image.load()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{label} is not a supported image.") from exc
    return image.convert("RGB")


def _service_token(env: Mapping[str, str]) -> str:
    return str(env.get("CIVORA_RENDERER_SERVICE_TOKEN") or "").strip()


def create_ai_renderer_app(
    *,
    engine: Optional[HybridRendererEngine] = None,
    env: Optional[Mapping[str, str]] = None,
) -> FastAPI:
    source = dict(os.environ if env is None else env)
    renderer = engine or build_hybrid_renderer_engine(source)
    render_lock = threading.BoundedSemaphore(value=1)
    app = FastAPI(title="Civora Private Hybrid Renderer", version="1.0.0")

    @app.middleware("http")
    async def limit_request_size(request: Request, call_next: Any) -> Any:
        content_length = request.headers.get("content-length")
        if request.url.path == "/v1/render" and content_length is None:
            return JSONResponse(status_code=411, content={"detail": "Content-Length is required."})
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BYTES:
                    return JSONResponse(status_code=413, content={"detail": "Renderer request exceeds 40 MB."})
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
        if request.url.path == "/v1/render":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_REQUEST_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Renderer request exceeds 40 MB."},
                    )
            request._body = bytes(body)
        return await call_next(request)

    @app.get("/health")
    def health() -> Any:
        status = dict(renderer.status())
        service_auth_configured = len(_service_token(source)) >= MIN_SERVICE_TOKEN_LENGTH
        payload = {
            "success": (
                bool(status.get("configured"))
                and not bool(status.get("load_error"))
                and service_auth_configured
            ),
            "service": "civora-private-hybrid-renderer",
            "contract": RENDER_CONTRACT,
            "service_auth_configured": service_auth_configured,
            "status": status,
        }
        if not payload["success"]:
            return JSONResponse(status_code=503, content=payload)
        return payload

    @app.post("/v1/render")
    def render(
        payload: HybridRenderRequest,
        authorization: Optional[str] = Header(default=None),
        x_civora_render_contract: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        expected_token = _service_token(source)
        supplied_token = str(authorization or "")
        if supplied_token.lower().startswith("bearer "):
            supplied_token = supplied_token[7:].strip()
        if len(expected_token) < MIN_SERVICE_TOKEN_LENGTH or not hmac.compare_digest(
            supplied_token, expected_token
        ):
            raise HTTPException(status_code=401, detail="Renderer service authentication failed.")
        if payload.contract != RENDER_CONTRACT or x_civora_render_contract != RENDER_CONTRACT:
            raise HTTPException(status_code=422, detail="Unsupported renderer contract.")
        if payload.map_context_included:
            raise HTTPException(
                status_code=422,
                detail="Map or satellite imagery must not be sent to the private renderer without a cleared source-rights contract.",
            )
        if not render_lock.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="Renderer is busy with another visualization.")
        try:
            reference = _decode_image(payload.reference_image_base64, label="Reference image")
            control = _decode_image(payload.control_image_base64, label="Control image")
            depth = _decode_image(payload.depth_image_base64, label="Depth image")
            if control.size != reference.size or depth.size != reference.size:
                raise HTTPException(
                    status_code=422,
                    detail="Reference, edge-control, and depth-control images must have matching dimensions.",
                )
            result = renderer.render(
                prompt=payload.prompt,
                negative_prompt=payload.negative_prompt,
                reference_image=reference,
                control_image=control,
                depth_image=depth,
                seed=payload.seed,
                output_format=payload.output_format,
            )
        except HybridRendererError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="The private GPU renderer could not complete this visualization.",
            ) from exc
        finally:
            render_lock.release()
        if (
            not result.image_bytes
            or len(result.image_bytes) > MAX_OUTPUT_IMAGE_BYTES
            or result.mime_type not in SUPPORTED_OUTPUT_MIME_TYPES
        ):
            raise HTTPException(status_code=502, detail="Renderer output is empty or exceeds 15 MB.")
        return {
            "success": True,
            "contract": RENDER_CONTRACT,
            "request_id": payload.request_id,
            "source_layout_hash": payload.source_layout_hash,
            "image_base64": base64.b64encode(result.image_bytes).decode("ascii"),
            "mime_type": result.mime_type,
            "model": result.model,
            "metadata": {
                **dict(result.metadata),
                "source_layout_hash": payload.source_layout_hash,
                "map_context_included": False,
                "input_images_retained": False,
                "output_image_retained": False,
            },
        }

    if str(source.get("CIVORA_RENDERER_EAGER_LOAD") or "").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            renderer.warmup()
        except HybridRendererError:
            pass
    return app


app = create_ai_renderer_app()
