from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Mapping, Protocol


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


class ImageProvider(Protocol):
    name: str
    model: str

    def generate(
        self,
        *,
        prompt: str,
        reference_png: bytes,
        user_id: str = "",
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
        user_id: str = "",
    ) -> GeneratedImage:
        _ = prompt, reference_png, user_id
        raise ImageProviderUnavailableError(
            "External photorealistic visualization is not configured for this deployment."
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
        user_id: str = "",
    ) -> GeneratedImage:
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
            "response_format": "b64_json",
            "user": str(user_id or "")[:128] or "civora-user",
            "timeout": self.timeout_seconds,
        }
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
        )


def image_provider_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if env is None else env
    provider = str(source.get("CIVORA_IMAGE_PROVIDER") or "none").strip().lower()
    model = str(source.get("CIVORA_IMAGE_MODEL") or "gpt-image-2").strip()
    if provider in {"", "none", "disabled", "off"}:
        return {
            "configured": False,
            "provider": "none",
            "model": model,
            "external": False,
            "reason": "External photorealistic visualization is not configured for this deployment.",
        }
    if provider != "openai":
        return {
            "configured": False,
            "provider": provider,
            "model": model,
            "external": True,
            "reason": f"Unsupported image provider '{provider}'.",
        }
    if not str(source.get("OPENAI_API_KEY") or "").strip():
        return {
            "configured": False,
            "provider": provider,
            "model": model,
            "external": True,
            "reason": "OPENAI_API_KEY is required when CIVORA_IMAGE_PROVIDER=openai.",
        }
    return {
        "configured": True,
        "provider": provider,
        "model": model,
        "external": True,
        "reason": "",
    }


def build_image_provider(env: Mapping[str, str] | None = None) -> ImageProvider:
    source = os.environ if env is None else env
    status = image_provider_status(source)
    if not status["configured"]:
        return DisabledImageProvider()
    try:
        timeout_seconds = float(str(source.get("CIVORA_IMAGE_TIMEOUT_SECONDS") or "180"))
    except ValueError:
        timeout_seconds = 180.0
    return OpenAIImageProvider(
        api_key=str(source.get("OPENAI_API_KEY") or ""),
        model=str(status["model"]),
        quality=str(source.get("CIVORA_IMAGE_QUALITY") or "medium").strip().lower(),
        output_format=str(source.get("CIVORA_IMAGE_OUTPUT_FORMAT") or "webp").strip().lower(),
        timeout_seconds=timeout_seconds,
    )
