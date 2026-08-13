from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError


DEFAULT_CIVORA_IMAGE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
# This is a URL-host denylist, not a listener bind.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}  # nosec B104
MIN_RENDERER_TOKEN_LENGTH = 32
MAX_RENDERED_IMAGE_BYTES = 15 * 1024 * 1024
MAX_RENDERED_IMAGE_PIXELS = 4_000_000
SUPPORTED_IMAGE_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


class ImageProviderUnavailableError(RuntimeError):
    pass


class ImageGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedImage:
    image_base64: str
    mime_type: str
    provider: str
    model: str
    request_id: str = ""
    revised_prompt: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ImageProvider(Protocol):
    name: str
    model: str

    def generate(
        self,
        *,
        prompt: str,
        reference_png: bytes,
        control_png: bytes | None = None,
        depth_png: bytes | None = None,
        user_id: str = "",
        request_context: Mapping[str, Any] | None = None,
    ) -> GeneratedImage:
        ...


class DisabledImageProvider:
    name = "none"
    model = ""

    def generate(
        self,
        *,
        prompt: str,
        reference_png: bytes,
        control_png: bytes | None = None,
        depth_png: bytes | None = None,
        user_id: str = "",
        request_context: Mapping[str, Any] | None = None,
    ) -> GeneratedImage:
        _ = prompt, reference_png, control_png, depth_png, user_id, request_context
        raise ImageProviderUnavailableError(
            "Photorealistic visualization is not configured for this deployment."
        )


class OpenAIImageProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-image-2",
        quality: str = "medium",
        output_format: str = "webp",
        client: Any = None,
        timeout_seconds: float = 180.0,
    ) -> None:
        if not str(api_key or "").strip():
            raise ImageProviderUnavailableError(
                "OPENAI_API_KEY is required when CIVORA_IMAGE_PROVIDER=openai."
            )
        self.model = str(model or "gpt-image-2").strip()
        self.quality = quality if quality in {"low", "medium", "high", "auto"} else "medium"
        self.output_format = output_format if output_format in {"png", "jpeg", "webp"} else "webp"
        self.timeout_seconds = max(30.0, min(float(timeout_seconds), 300.0))
        if client is None:
            try:
                from openai import OpenAI
            except Exception as exc:  # pragma: no cover - dependency failure is deployment-specific
                raise ImageProviderUnavailableError(
                    "The OpenAI image client is unavailable in this deployment."
                ) from exc
            client = OpenAI(api_key=api_key)
        self.client = client

    def generate(
        self,
        *,
        prompt: str,
        reference_png: bytes,
        control_png: bytes | None = None,
        depth_png: bytes | None = None,
        user_id: str = "",
        request_context: Mapping[str, Any] | None = None,
    ) -> GeneratedImage:
        _ = control_png, depth_png, request_context
        if not reference_png:
            raise ImageGenerationError("The layout reference image is empty.")

        reference_file = BytesIO(reference_png)
        reference_file.name = "civora-site-layout-reference.png"
        request_options: dict[str, Any] = {
            "model": self.model,
            "image": reference_file,
            "prompt": prompt,
            "size": "1536x1024",
            "quality": self.quality,
            "output_format": self.output_format,
            "user": str(user_id or "")[:128] or "civora-user",
            "timeout": self.timeout_seconds,
        }
        # GPT Image responses already return base64 image data. The legacy
        # response_format option is accepted by the SDK signature but rejected
        # by the current GPT Image API.
        if self.model.lower().startswith("dall-e"):
            request_options["response_format"] = "b64_json"
        if self.output_format in {"jpeg", "webp"}:
            request_options["output_compression"] = 82
        try:
            response = self.client.images.edit(**request_options)
        except Exception as exc:
            raise ImageGenerationError(
                "The external visualization provider could not complete the image. Retry in a moment."
            ) from exc

        data = list(getattr(response, "data", None) or [])
        first = data[0] if data else None
        image_base64 = str(getattr(first, "b64_json", "") or "")
        if not image_base64:
            raise ImageGenerationError(
                "The external visualization provider returned no image data. Retry the visualization."
            )

        mime_type = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }[self.output_format]
        return GeneratedImage(
            image_base64=image_base64,
            mime_type=mime_type,
            provider=self.name,
            model=self.model,
            request_id=str(getattr(response, "_request_id", "") or ""),
            revised_prompt=str(getattr(first, "revised_prompt", "") or ""),
            metadata={"self_hosted": False, "photorealistic": True},
        )


class CivoraHybridImageProvider:
    name = "civora"

    def __init__(
        self,
        *,
        renderer_url: str,
        service_token: str,
        model: str = DEFAULT_CIVORA_IMAGE_MODEL,
        timeout_seconds: float = 240.0,
        output_format: str = "webp",
        session: Any = requests,
    ) -> None:
        base_url = str(renderer_url or "").strip().rstrip("/")
        if not base_url:
            raise ImageProviderUnavailableError(
                "CIVORA_IMAGE_RENDERER_URL is required when CIVORA_IMAGE_PROVIDER=civora."
            )
        if len(str(service_token or "").strip()) < MIN_RENDERER_TOKEN_LENGTH:
            raise ImageProviderUnavailableError(
                "CIVORA_IMAGE_RENDERER_TOKEN must contain at least 32 characters when "
                "CIVORA_IMAGE_PROVIDER=civora."
            )
        self.renderer_url = f"{base_url}/v1/render"
        self.service_token = str(service_token).strip()
        self.model = str(model or DEFAULT_CIVORA_IMAGE_MODEL).strip()
        self.timeout_seconds = max(60.0, min(float(timeout_seconds), 600.0))
        self.output_format = output_format if output_format in {"png", "jpeg", "webp"} else "webp"
        self.session = session

    def generate(
        self,
        *,
        prompt: str,
        reference_png: bytes,
        control_png: bytes | None = None,
        depth_png: bytes | None = None,
        user_id: str = "",
        request_context: Mapping[str, Any] | None = None,
    ) -> GeneratedImage:
        if not reference_png:
            raise ImageGenerationError("The layout reference image is empty.")
        context = dict(request_context or {})
        request_fingerprint = hashlib.sha256(
            f"{context.get('source_layout_hash', '')}:{context.get('job_id', '')}".encode("utf-8")
        ).hexdigest()
        user_fingerprint = hashlib.sha256(str(user_id or "anonymous").encode("utf-8")).hexdigest()[:24]
        payload = {
            "contract": "civora_hybrid_render_v1",
            "request_id": str(context.get("job_id") or request_fingerprint[:24]),
            "source_layout_hash": str(context.get("source_layout_hash") or "")[:128],
            "prompt": str(prompt or "")[:4_000],
            "negative_prompt": (
                "labels, text, dimensions, logos, extra buildings, duplicate objects, relocated roads, "
                "distorted footprints, fantasy architecture, dramatic perspective, low resolution"
            ),
            "reference_image_base64": base64.b64encode(reference_png).decode("ascii"),
            "control_image_base64": base64.b64encode(control_png or reference_png).decode("ascii"),
            "depth_image_base64": base64.b64encode(depth_png or control_png or reference_png).decode("ascii"),
            "output_format": self.output_format,
            "seed": int(request_fingerprint[:8], 16),
            "user_fingerprint": user_fingerprint,
            "map_context_included": False,
        }
        try:
            response = self.session.post(
                self.renderer_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.service_token}",
                    "Content-Type": "application/json",
                    "X-Civora-Render-Contract": "civora_hybrid_render_v1",
                },
                timeout=(10.0, self.timeout_seconds),
            )
        except requests.RequestException as exc:
            raise ImageGenerationError(
                "The private Civora renderer is temporarily unreachable. Retry in a moment."
            ) from exc
        except Exception as exc:
            raise ImageGenerationError(
                "The private Civora renderer could not be contacted. Retry in a moment."
            ) from exc

        if response.status_code == 429:
            raise ImageGenerationError(
                "The private Civora renderer is busy. Retry after the current visualization finishes."
            )
        if response.status_code in {401, 403}:
            raise ImageGenerationError(
                "The private Civora renderer rejected service authentication."
            )
        if response.status_code >= 400:
            raise ImageGenerationError(
                "The private Civora renderer could not complete this visualization. Retry in a moment."
            )
        try:
            result_value = response.json()
            if not isinstance(result_value, Mapping):
                raise TypeError("Renderer response must be an object.")
            result = dict(result_value)
            metadata_value = result.get("metadata") or {}
            if not isinstance(metadata_value, Mapping):
                raise TypeError("Renderer metadata must be an object.")
            metadata = dict(metadata_value)
        except Exception as exc:
            raise ImageGenerationError(
                "The private Civora renderer returned an unreadable response."
            ) from exc

        image_base64 = str(result.get("image_base64") or "")
        if not image_base64:
            raise ImageGenerationError("The private Civora renderer returned no image data.")
        if metadata.get("photorealistic") is not True:
            raise ImageGenerationError(
                "The private renderer returned a non-photorealistic development result."
            )
        try:
            image_bytes = base64.b64decode(image_base64, validate=True)
            if not image_bytes or len(image_bytes) > MAX_RENDERED_IMAGE_BYTES:
                raise ValueError("Rendered image is empty or too large.")
            image = Image.open(BytesIO(image_bytes))
            if image.width * image.height > MAX_RENDERED_IMAGE_PIXELS:
                raise ValueError("Rendered image exceeds the pixel limit.")
            image_format = str(image.format or "").upper()
            mime_type = SUPPORTED_IMAGE_MIME_TYPES.get(image_format)
            if not mime_type:
                raise ValueError("Rendered image format is unsupported.")
            image.verify()
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageGenerationError(
                "The private Civora renderer returned invalid image data."
            ) from exc
        return GeneratedImage(
            image_base64=image_base64,
            mime_type=mime_type,
            provider=self.name,
            model=str(result.get("model") or self.model),
            request_id=str(result.get("request_id") or context.get("job_id") or ""),
            metadata={
                **metadata,
                "self_hosted": True,
                "map_context_included": False,
            },
        )


def _valid_renderer_url(url: str, *, allow_local: bool) -> bool:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = str(parsed.hostname or "").lower()
    if parsed.scheme == "http" and not (allow_local and host in LOCAL_HOSTS):
        return False
    return allow_local or host not in LOCAL_HOSTS


def image_provider_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if env is None else env
    provider = str(source.get("CIVORA_IMAGE_PROVIDER") or "none").strip().lower()
    if provider in {"hybrid", "internal", "self_hosted", "self-hosted"}:
        provider = "civora"
    default_model = DEFAULT_CIVORA_IMAGE_MODEL if provider == "civora" else "gpt-image-2"
    model = str(source.get("CIVORA_IMAGE_MODEL") or default_model).strip()
    if provider in {"", "none", "disabled", "off"}:
        return {
            "configured": False,
            "provider": "none",
            "model": model,
            "external": False,
            "self_hosted": False,
            "reason": "Photorealistic visualization is not configured for this deployment.",
        }
    if provider == "openai":
        if not str(source.get("OPENAI_API_KEY") or "").strip():
            return {
                "configured": False,
                "provider": provider,
                "model": model,
                "external": True,
                "self_hosted": False,
                "reason": "OPENAI_API_KEY is required when CIVORA_IMAGE_PROVIDER=openai.",
            }
        return {
            "configured": True,
            "provider": provider,
            "model": model,
            "external": True,
            "self_hosted": False,
            "reason": "",
        }
    if provider != "civora":
        return {
            "configured": False,
            "provider": provider,
            "model": model,
            "external": False,
            "self_hosted": False,
            "reason": f"Unsupported image provider '{provider}'.",
        }

    renderer_url = str(source.get("CIVORA_IMAGE_RENDERER_URL") or "").strip()
    renderer_token = str(source.get("CIVORA_IMAGE_RENDERER_TOKEN") or "").strip()
    deployment_target = str(source.get("CIVORA_DEPLOYMENT_TARGET") or "local").strip().lower()
    allow_local = deployment_target in {"", "development", "local"}
    if not renderer_url:
        reason = "CIVORA_IMAGE_RENDERER_URL is required when CIVORA_IMAGE_PROVIDER=civora."
    elif not _valid_renderer_url(renderer_url, allow_local=allow_local):
        reason = "CIVORA_IMAGE_RENDERER_URL must use HTTPS outside local development."
    elif len(renderer_token) < MIN_RENDERER_TOKEN_LENGTH:
        reason = (
            "CIVORA_IMAGE_RENDERER_TOKEN must contain at least 32 characters when "
            "CIVORA_IMAGE_PROVIDER=civora."
        )
    else:
        reason = ""
    return {
        "configured": not reason,
        "provider": provider,
        "model": model,
        "external": False,
        "self_hosted": True,
        "renderer_url_configured": bool(renderer_url),
        "reason": reason,
    }


def build_image_provider(env: Mapping[str, str] | None = None) -> ImageProvider:
    source = os.environ if env is None else env
    status = image_provider_status(source)
    if not status["configured"]:
        return DisabledImageProvider()
    try:
        timeout_seconds = float(str(source.get("CIVORA_IMAGE_TIMEOUT_SECONDS") or "240"))
    except ValueError:
        timeout_seconds = 240.0
    output_format = str(source.get("CIVORA_IMAGE_OUTPUT_FORMAT") or "webp").strip().lower()
    if status["provider"] == "civora":
        return CivoraHybridImageProvider(
            renderer_url=str(source.get("CIVORA_IMAGE_RENDERER_URL") or ""),
            service_token=str(source.get("CIVORA_IMAGE_RENDERER_TOKEN") or ""),
            model=str(status["model"]),
            timeout_seconds=timeout_seconds,
            output_format=output_format,
        )
    return OpenAIImageProvider(
        api_key=str(source.get("OPENAI_API_KEY") or ""),
        model=str(status["model"]),
        quality=str(source.get("CIVORA_IMAGE_QUALITY") or "medium").strip().lower(),
        output_format=output_format,
        timeout_seconds=timeout_seconds,
    )
