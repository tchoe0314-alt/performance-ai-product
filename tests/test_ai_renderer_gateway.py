from __future__ import annotations

import base64
from io import BytesIO
from typing import Any, Mapping

from fastapi.testclient import TestClient
from PIL import Image

from backend.ai.hybrid_renderer_engine import (
    BlockedHybridRendererEngine,
    DEFAULT_CANNY_CONTROLNET_REVISION,
    DEFAULT_DEPTH_CONTROLNET_REVISION,
    DEFAULT_MODEL_REVISION,
    DiffusersHybridRendererEngine,
    HybridRenderResult,
    ReferenceHybridRendererEngine,
    build_hybrid_renderer_engine,
)
from backend.scripts.ai_renderer_gateway import RENDER_CONTRACT, create_ai_renderer_app


TOKEN = "test-renderer-token-" + "x" * 32


def _image_base64(*, size: tuple[int, int] = (64, 48), color: tuple[int, int, int] = (40, 90, 140)) -> str:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


class FakePhotorealisticEngine:
    def __init__(self) -> None:
        self.calls: list[Mapping[str, Any]] = []

    def status(self) -> Mapping[str, Any]:
        return {
            "configured": True,
            "ready": True,
            "engine": "fake_diffusers",
            "photorealistic": True,
            "no_image_retention": True,
        }

    def warmup(self) -> None:
        return None

    def render(self, **kwargs: Any) -> HybridRenderResult:
        self.calls.append(kwargs)
        output = BytesIO()
        Image.new("RGB", (96, 64), (80, 130, 90)).save(output, format="WEBP")
        return HybridRenderResult(
            image_bytes=output.getvalue(),
            mime_type="image/webp",
            model="pinned-test-model",
            metadata={
                "photorealistic": True,
                "self_hosted": True,
                "engine": "fake_diffusers",
                "model_revision": "revision-1",
                "seed": kwargs["seed"],
                "no_image_retention": True,
            },
        )


def _request_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "contract": RENDER_CONTRACT,
        "request_id": "job-123",
        "source_layout_hash": "layout-1234",
        "prompt": "Render a realistic orthographic site concept.",
        "negative_prompt": "labels, duplicate buildings",
        "reference_image_base64": _image_base64(color=(20, 30, 40)),
        "control_image_base64": _image_base64(color=(255, 255, 255)),
        "depth_image_base64": _image_base64(color=(100, 100, 100)),
        "output_format": "webp",
        "seed": 42,
        "user_fingerprint": "hashed-user",
        "map_context_included": False,
    }
    payload.update(overrides)
    return payload


def _headers(token: str = TOKEN) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Civora-Render-Contract": RENDER_CONTRACT,
    }


def test_health_requires_renderer_auth_configuration_without_exposing_token() -> None:
    engine = FakePhotorealisticEngine()
    missing = TestClient(create_ai_renderer_app(engine=engine, env={}))
    missing_response = missing.get("/health")
    assert missing_response.status_code == 503
    assert missing_response.json()["service_auth_configured"] is False

    client = TestClient(
        create_ai_renderer_app(engine=engine, env={"CIVORA_RENDERER_SERVICE_TOKEN": TOKEN})
    )
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["service_auth_configured"] is True
    assert TOKEN not in response.text


def test_render_requires_service_auth_and_exact_contract() -> None:
    client = TestClient(
        create_ai_renderer_app(
            engine=FakePhotorealisticEngine(),
            env={"CIVORA_RENDERER_SERVICE_TOKEN": TOKEN},
        )
    )

    assert client.post("/v1/render", json=_request_payload()).status_code == 401
    bad_contract = client.post(
        "/v1/render",
        json=_request_payload(),
        headers={**_headers(), "X-Civora-Render-Contract": "wrong-contract"},
    )
    assert bad_contract.status_code == 422

    invalid_length = client.post(
        "/v1/render",
        content=b"{}",
        headers={**_headers(), "Content-Length": "not-a-number", "Content-Type": "application/json"},
    )
    assert invalid_length.status_code == 400


def test_render_rejects_map_imagery_and_mismatched_controls() -> None:
    engine = FakePhotorealisticEngine()
    client = TestClient(
        create_ai_renderer_app(engine=engine, env={"CIVORA_RENDERER_SERVICE_TOKEN": TOKEN})
    )

    map_response = client.post(
        "/v1/render",
        json=_request_payload(map_context_included=True),
        headers=_headers(),
    )
    assert map_response.status_code == 422
    assert "Map or satellite imagery" in map_response.json()["detail"]

    mismatched = client.post(
        "/v1/render",
        json=_request_payload(depth_image_base64=_image_base64(size=(32, 32))),
        headers=_headers(),
    )
    assert mismatched.status_code == 422
    assert "matching dimensions" in mismatched.json()["detail"]
    assert engine.calls == []


def test_render_returns_photorealistic_provenance_without_retaining_images() -> None:
    engine = FakePhotorealisticEngine()
    client = TestClient(
        create_ai_renderer_app(engine=engine, env={"CIVORA_RENDERER_SERVICE_TOKEN": TOKEN})
    )

    response = client.post("/v1/render", json=_request_payload(), headers=_headers())

    assert response.status_code == 200
    result = response.json()
    assert result["contract"] == RENDER_CONTRACT
    assert result["request_id"] == "job-123"
    assert result["source_layout_hash"] == "layout-1234"
    assert result["mime_type"] == "image/webp"
    assert base64.b64decode(result["image_base64"], validate=True).startswith(b"RIFF")
    assert result["metadata"]["photorealistic"] is True
    assert result["metadata"]["input_images_retained"] is False
    assert result["metadata"]["output_image_retained"] is False
    assert result["metadata"]["map_context_included"] is False
    assert result["metadata"]["source_layout_hash"] == "layout-1234"
    assert len(engine.calls) == 1
    assert engine.calls[0]["reference_image"].size == (64, 48)
    assert engine.calls[0]["control_image"].size == (64, 48)
    assert engine.calls[0]["depth_image"].size == (64, 48)


def test_reference_engine_requires_explicit_nonproduction_opt_in() -> None:
    blocked = build_hybrid_renderer_engine(
        {
            "CIVORA_RENDERER_ENGINE": "reference",
            "CIVORA_PRODUCT_MODE": "production",
            "CIVORA_RENDERER_ALLOW_REFERENCE_ENGINE": "true",
        }
    )
    assert isinstance(blocked, BlockedHybridRendererEngine)
    assert blocked.status()["photorealistic"] is False

    allowed = build_hybrid_renderer_engine(
        {
            "CIVORA_RENDERER_ENGINE": "reference",
            "CIVORA_PRODUCT_MODE": "local",
            "CIVORA_RENDERER_ALLOW_REFERENCE_ENGINE": "true",
        }
    )
    assert isinstance(allowed, ReferenceHybridRendererEngine)
    assert allowed.status()["photorealistic"] is False


def test_diffusers_engine_reports_pinned_models_before_loading_gpu_dependencies() -> None:
    engine = DiffusersHybridRendererEngine(
        {"CIVORA_RENDERER_MODEL_LICENSE_ACKNOWLEDGED": "true"}
    )

    status = engine.status()

    assert status["configured"] is True
    assert status["ready"] is False
    assert status["state"] == "cold"
    assert status["model_revision"] == DEFAULT_MODEL_REVISION
    assert [item["revision"] for item in status["controlnets"]] == [
        DEFAULT_CANNY_CONTROLNET_REVISION,
        DEFAULT_DEPTH_CONTROLNET_REVISION,
    ]
    assert status["photorealistic"] is True
    assert status["no_image_retention"] is True
