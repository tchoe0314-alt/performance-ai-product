from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Mapping, Protocol

from PIL import Image, ImageEnhance, ImageFilter


DEFAULT_MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
DEFAULT_MODEL_REVISION = "462165984030d82259a11f4367a4eed129e94a7b"
DEFAULT_CANNY_CONTROLNET_ID = "diffusers/controlnet-canny-sdxl-1.0"
DEFAULT_CANNY_CONTROLNET_REVISION = "eb115a19a10d14909256db740ed109532ab1483c"
DEFAULT_DEPTH_CONTROLNET_ID = "diffusers/controlnet-depth-sdxl-1.0-small"
DEFAULT_DEPTH_CONTROLNET_REVISION = "daf3835d036574dff7c158882e8e77b75b024ee5"


class HybridRendererError(RuntimeError):
    pass


@dataclass(frozen=True)
class HybridRenderResult:
    image_bytes: bytes
    mime_type: str
    model: str
    metadata: Mapping[str, Any]


class HybridRendererEngine(Protocol):
    def status(self) -> Mapping[str, Any]:
        ...

    def warmup(self) -> None:
        ...

    def render(
        self,
        *,
        prompt: str,
        negative_prompt: str,
        reference_image: Image.Image,
        control_image: Image.Image,
        depth_image: Image.Image,
        seed: int,
        output_format: str,
    ) -> HybridRenderResult:
        ...


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(minimum, min(maximum, result))


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    return max(minimum, min(maximum, result))


def _encode_image(image: Image.Image, output_format: str) -> tuple[bytes, str]:
    normalized = output_format if output_format in {"png", "jpeg", "webp"} else "webp"
    output = BytesIO()
    if normalized == "png":
        image.save(output, format="PNG", optimize=True)
        return output.getvalue(), "image/png"
    if normalized == "jpeg":
        image.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue(), "image/jpeg"
    image.convert("RGB").save(output, format="WEBP", quality=86, method=6)
    return output.getvalue(), "image/webp"


class ReferenceHybridRendererEngine:
    """Deterministic contract renderer for local development and CI only."""

    model = "civora-reference-renderer"

    def status(self) -> Mapping[str, Any]:
        return {
            "configured": True,
            "ready": True,
            "state": "development_reference",
            "engine": "reference",
            "model": self.model,
            "photorealistic": False,
            "self_hosted": True,
            "no_image_retention": True,
        }

    def warmup(self) -> None:
        return None

    def render(
        self,
        *,
        prompt: str,
        negative_prompt: str,
        reference_image: Image.Image,
        control_image: Image.Image,
        depth_image: Image.Image,
        seed: int,
        output_format: str,
    ) -> HybridRenderResult:
        _ = prompt, negative_prompt, control_image, seed
        image = reference_image.convert("RGB")
        shaded = depth_image.convert("L").filter(ImageFilter.GaussianBlur(radius=10))
        shaded = ImageEnhance.Contrast(shaded).enhance(0.45)
        image = Image.blend(image, Image.merge("RGB", (shaded, shaded, shaded)), 0.12)
        image_bytes, mime_type = _encode_image(image, output_format)
        return HybridRenderResult(
            image_bytes=image_bytes,
            mime_type=mime_type,
            model=self.model,
            metadata={
                "photorealistic": False,
                "self_hosted": True,
                "engine": "reference",
                "seed": seed,
                "no_image_retention": True,
            },
        )


class DiffusersHybridRendererEngine:
    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        source = os.environ if env is None else env
        self.model = str(source.get("CIVORA_RENDERER_MODEL") or DEFAULT_MODEL_ID).strip()
        self.model_revision = str(
            source.get("CIVORA_RENDERER_MODEL_REVISION") or DEFAULT_MODEL_REVISION
        ).strip()
        self.canny_model = str(
            source.get("CIVORA_RENDERER_CANNY_MODEL") or DEFAULT_CANNY_CONTROLNET_ID
        ).strip()
        self.canny_revision = str(
            source.get("CIVORA_RENDERER_CANNY_REVISION") or DEFAULT_CANNY_CONTROLNET_REVISION
        ).strip()
        self.depth_model = str(
            source.get("CIVORA_RENDERER_DEPTH_MODEL") or DEFAULT_DEPTH_CONTROLNET_ID
        ).strip()
        self.depth_revision = str(
            source.get("CIVORA_RENDERER_DEPTH_REVISION") or DEFAULT_DEPTH_CONTROLNET_REVISION
        ).strip()
        self.model_license = str(source.get("CIVORA_RENDERER_MODEL_LICENSE") or "openrail++").strip()
        self.license_acknowledged = _truthy(
            source.get("CIVORA_RENDERER_MODEL_LICENSE_ACKNOWLEDGED")
        )
        self.require_cuda = not _truthy(source.get("CIVORA_RENDERER_ALLOW_CPU"))
        self.local_files_only = _truthy(source.get("CIVORA_RENDERER_LOCAL_FILES_ONLY"))
        self.use_depth_control = not str(
            source.get("CIVORA_RENDERER_USE_DEPTH_CONTROL") or "true"
        ).strip().lower() in {"0", "false", "no", "off"}
        self.cpu_offload = _truthy(source.get("CIVORA_RENDERER_CPU_OFFLOAD"))
        self.width = _bounded_int(
            source.get("CIVORA_RENDERER_WIDTH"), default=1344, minimum=768, maximum=1536
        )
        self.height = _bounded_int(
            source.get("CIVORA_RENDERER_HEIGHT"), default=896, minimum=512, maximum=1024
        )
        self.width -= self.width % 8
        self.height -= self.height % 8
        self.steps = _bounded_int(
            source.get("CIVORA_RENDERER_INFERENCE_STEPS"), default=36, minimum=12, maximum=80
        )
        self.guidance_scale = _bounded_float(
            source.get("CIVORA_RENDERER_GUIDANCE_SCALE"), default=6.5, minimum=1.0, maximum=15.0
        )
        self.strength = _bounded_float(
            source.get("CIVORA_RENDERER_STRENGTH"), default=0.48, minimum=0.15, maximum=0.8
        )
        self.canny_scale = _bounded_float(
            source.get("CIVORA_RENDERER_CANNY_SCALE"), default=0.95, minimum=0.1, maximum=1.5
        )
        self.depth_scale = _bounded_float(
            source.get("CIVORA_RENDERER_DEPTH_SCALE"), default=0.65, minimum=0.1, maximum=1.5
        )
        self._pipeline: Any = None
        self._torch: Any = None
        self._device = "unloaded"
        self._gpu_name = ""
        self._load_error = ""
        self._load_lock = threading.Lock()

    def status(self) -> Mapping[str, Any]:
        configured = self.license_acknowledged
        return {
            "configured": configured,
            "ready": self._pipeline is not None,
            "state": "ready" if self._pipeline is not None else "blocked" if not configured else "cold",
            "engine": "diffusers_sdxl_controlnet",
            "model": self.model,
            "model_revision": self.model_revision,
            "model_license": self.model_license,
            "model_license_acknowledged": self.license_acknowledged,
            "controlnets": [
                {"model": self.canny_model, "revision": self.canny_revision, "kind": "edge"},
                *(
                    [{"model": self.depth_model, "revision": self.depth_revision, "kind": "height_depth"}]
                    if self.use_depth_control
                    else []
                ),
            ],
            "device": self._device,
            "gpu_name": self._gpu_name,
            "photorealistic": True,
            "self_hosted": True,
            "no_image_retention": True,
            "load_error": self._load_error,
        }

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        with self._load_lock:
            if self._pipeline is not None:
                return
            if not self.license_acknowledged:
                raise HybridRendererError(
                    "The configured renderer model license has not been acknowledged by the deployment owner."
                )
            try:
                import torch
                from diffusers import (
                    ControlNetModel,
                    DPMSolverMultistepScheduler,
                    StableDiffusionXLControlNetImg2ImgPipeline,
                )
            except Exception as exc:  # pragma: no cover - exercised only in GPU image
                self._load_error = "Renderer dependencies are unavailable."
                raise HybridRendererError(self._load_error) from exc

            if self.require_cuda and not torch.cuda.is_available():
                self._load_error = "A CUDA GPU is required for the production hybrid renderer."
                raise HybridRendererError(self._load_error)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32
            load_options: dict[str, Any] = {
                "torch_dtype": dtype,
                "use_safetensors": True,
                "local_files_only": self.local_files_only,
            }
            pipeline_load_options = dict(load_options)
            if device == "cuda":
                pipeline_load_options["variant"] = "fp16"
            try:
                canny = ControlNetModel.from_pretrained(
                    self.canny_model,
                    revision=self.canny_revision,
                    **load_options,
                )
                controlnets: list[Any] = [canny]
                if self.use_depth_control:
                    controlnets.append(
                        ControlNetModel.from_pretrained(
                            self.depth_model,
                            revision=self.depth_revision,
                            **load_options,
                        )
                    )
                pipeline = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
                    self.model,
                    revision=self.model_revision,
                    controlnet=controlnets if len(controlnets) > 1 else controlnets[0],
                    **pipeline_load_options,
                )
                pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
                    pipeline.scheduler.config,
                    use_karras_sigmas=True,
                )
                pipeline.enable_attention_slicing()
                pipeline.enable_vae_slicing()
                pipeline.enable_vae_tiling()
                if device == "cuda" and self.cpu_offload:
                    pipeline.enable_model_cpu_offload()
                else:
                    pipeline.to(device)
                pipeline.set_progress_bar_config(disable=True)
            except Exception as exc:  # pragma: no cover - exercised only in GPU image
                self._load_error = "The pinned renderer model could not be loaded."
                raise HybridRendererError(self._load_error) from exc
            self._pipeline = pipeline
            self._torch = torch
            self._device = device
            self._gpu_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU development mode"
            self._load_error = ""

    def warmup(self) -> None:
        self._load()

    def render(
        self,
        *,
        prompt: str,
        negative_prompt: str,
        reference_image: Image.Image,
        control_image: Image.Image,
        depth_image: Image.Image,
        seed: int,
        output_format: str,
    ) -> HybridRenderResult:
        self._load()
        reference = reference_image.convert("RGB").resize((self.width, self.height), Image.Resampling.LANCZOS)
        edge = control_image.convert("RGB").resize((self.width, self.height), Image.Resampling.NEAREST)
        depth = depth_image.convert("RGB").resize((self.width, self.height), Image.Resampling.BILINEAR)
        controls: Any = [edge, depth] if self.use_depth_control else edge
        scales: Any = [self.canny_scale, self.depth_scale] if self.use_depth_control else self.canny_scale
        generator_device = "cuda" if self._device == "cuda" else "cpu"
        generator = self._torch.Generator(device=generator_device).manual_seed(int(seed) % (2**31))
        try:
            output = self._pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=reference,
                control_image=controls,
                strength=self.strength,
                controlnet_conditioning_scale=scales,
                num_inference_steps=self.steps,
                guidance_scale=self.guidance_scale,
                generator=generator,
                width=self.width,
                height=self.height,
            )
            image = output.images[0]
        except Exception as exc:  # pragma: no cover - exercised only in GPU image
            raise HybridRendererError(
                "The private GPU renderer could not complete this visualization."
            ) from exc
        image_bytes, mime_type = _encode_image(image, output_format)
        return HybridRenderResult(
            image_bytes=image_bytes,
            mime_type=mime_type,
            model=self.model,
            metadata={
                "photorealistic": True,
                "self_hosted": True,
                "engine": "diffusers_sdxl_controlnet",
                "model_revision": self.model_revision,
                "model_license": self.model_license,
                "controlnet_revisions": [
                    self.canny_revision,
                    *([self.depth_revision] if self.use_depth_control else []),
                ],
                "control_kinds": ["edge", *(["height_depth"] if self.use_depth_control else [])],
                "seed": int(seed) % (2**31),
                "width": self.width,
                "height": self.height,
                "inference_steps": self.steps,
                "guidance_scale": self.guidance_scale,
                "reference_strength": self.strength,
                "device": self._device,
                "gpu_name": self._gpu_name,
                "no_image_retention": True,
            },
        )


class BlockedHybridRendererEngine:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def status(self) -> Mapping[str, Any]:
        return {
            "configured": False,
            "ready": False,
            "state": "blocked",
            "engine": "unavailable",
            "photorealistic": False,
            "self_hosted": True,
            "no_image_retention": True,
            "reason": self.reason,
        }

    def warmup(self) -> None:
        raise HybridRendererError(self.reason)

    def render(self, **_: Any) -> HybridRenderResult:
        raise HybridRendererError(self.reason)


def build_hybrid_renderer_engine(
    env: Mapping[str, str] | None = None,
) -> HybridRendererEngine:
    source = os.environ if env is None else env
    engine = str(source.get("CIVORA_RENDERER_ENGINE") or "diffusers").strip().lower()
    if engine in {"reference", "mock"}:
        mode = str(source.get("CIVORA_PRODUCT_MODE") or "local").strip().lower()
        allowed = _truthy(source.get("CIVORA_RENDERER_ALLOW_REFERENCE_ENGINE"))
        if mode not in {"development", "local", "private_alpha"} or not allowed:
            return BlockedHybridRendererEngine(
                "The reference renderer is restricted to explicitly enabled development environments."
            )
        return ReferenceHybridRendererEngine()
    if engine not in {"diffusers", "sdxl_controlnet", "civora"}:
        return BlockedHybridRendererEngine(f"Unsupported private renderer engine '{engine}'.")
    return DiffusersHybridRendererEngine(source)
