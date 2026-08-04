from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_gpu_container_pins_a_supported_cuda_pytorch_pair() -> None:
    dockerfile = (ROOT / "Dockerfile.ai-renderer").read_text()

    assert "FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04" in dockerfile
    assert "--index-url https://download.pytorch.org/whl/cu128" in dockerfile
    assert "torch==2.11.0 torchvision==0.26.0" in dockerfile
    assert "--workers 1" in dockerfile
    assert "backend.scripts.ai_renderer_gateway:app" in dockerfile


def test_renderer_dependencies_satisfy_diffusers_runtime_floor() -> None:
    requirements = {
        line.strip()
        for line in (ROOT / "requirements_ai_renderer.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "diffusers==0.39.0" in requirements
    assert "safetensors==0.8.0" in requirements
    assert "accelerate==1.14.0" in requirements
    assert "transformers==5.14.1" in requirements


def test_compose_contract_requires_gpu_token_license_and_persistent_model_cache() -> None:
    compose = (ROOT / "compose.ai-renderer.yaml").read_text()

    assert "dockerfile: Dockerfile.ai-renderer" in compose
    assert "gpus: all" in compose
    assert "CIVORA_RENDERER_SERVICE_TOKEN:" in compose
    assert "CIVORA_RENDERER_MODEL_LICENSE_ACKNOWLEDGED:" in compose
    assert "civora-renderer-model-cache:/models" in compose
    assert not (ROOT / "railway.ai-renderer.toml").exists()
