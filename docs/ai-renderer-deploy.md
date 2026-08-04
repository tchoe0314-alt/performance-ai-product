# Civora Private Hybrid Renderer

This service turns Civora's canonical site layout into a photorealistic visual concept without calling an external image-generation API.

`CIVORA_IMAGE_PROVIDER=civora` does not require an OpenAI key. `OPENAI_API_KEY` may remain unset unless OpenAI is separately selected for language features or as the optional image fallback.

## Architecture

1. The Civora backend renders a bounded material reference, an exact edge map, and a height-aware depth map from canonical project objects.
2. The private worker runs a pinned SDXL image-to-image pipeline with edge and depth ControlNets.
3. The worker returns the image and model/control provenance without retaining inputs or outputs.
4. Civora validates the source-layout hash and presents the result only in Visual view.

Satellite/map imagery is not sent to this worker. The live map remains a separate browser layer unless a future source-rights contract explicitly authorizes a different workflow.

## Model and License

The default deployment pins:

- `stabilityai/stable-diffusion-xl-base-1.0` at `462165984030d82259a11f4367a4eed129e94a7b`
- `diffusers/controlnet-canny-sdxl-1.0` at `eb115a19a10d14909256db740ed109532ab1483c`
- `diffusers/controlnet-depth-sdxl-1.0-small` at `daf3835d036574dff7c158882e8e77b75b024ee5`

All three model cards identify the license as OpenRAIL++. Review and accept the license terms before setting `CIVORA_RENDERER_MODEL_LICENSE_ACKNOWLEDGED=true`. Keep the revisions pinned until a replacement model passes visual fidelity, geometry preservation, security, and license review.

## GPU Service

The service needs an NVIDIA GPU. A 24 GB GPU is recommended for both edge and depth controls at the default 1344 x 896 output. Use a persistent volume mounted at `/models` so model weights survive restarts.

Railway may continue hosting Civora's main backend, but it must not host this renderer: [Railway's current GPU guidance](https://docs.railway.com/guides/ai-agent-workers#gpu-availability) states that Railway does not offer GPU instances. Run the renderer on an owned NVIDIA host or a GPU container platform, then give the main backend its authenticated HTTPS URL.

For an owned or local NVIDIA host with Docker Compose:

```bash
export CIVORA_RENDERER_SERVICE_TOKEN="$(openssl rand -hex 32)"
export CIVORA_RENDERER_MODEL_LICENSE_ACKNOWLEDGED=true
docker compose -f compose.ai-renderer.yaml up --build
```

For a managed GPU container host, build `Dockerfile.ai-renderer`, attach a persistent `/models` volume, expose the injected `PORT`, and configure HTTPS in front of it. The same container and environment contract applies.

The container pins the [officially published PyTorch 2.11.0 / torchvision 0.26.0 CUDA 12.8 pair](https://pytorch.org/get-started/previous-versions/#v2110). Keep that CUDA/PyTorch pair aligned when upgrading; do not independently bump only one side of the runtime.

Set these variables on the renderer service:

```bash
CIVORA_PRODUCT_MODE=production
CIVORA_RENDERER_ENGINE=diffusers
CIVORA_RENDERER_SERVICE_TOKEN=generate-a-random-token-with-at-least-32-characters
CIVORA_RENDERER_MODEL=stabilityai/stable-diffusion-xl-base-1.0
CIVORA_RENDERER_MODEL_REVISION=462165984030d82259a11f4367a4eed129e94a7b
CIVORA_RENDERER_CANNY_MODEL=diffusers/controlnet-canny-sdxl-1.0
CIVORA_RENDERER_CANNY_REVISION=eb115a19a10d14909256db740ed109532ab1483c
CIVORA_RENDERER_DEPTH_MODEL=diffusers/controlnet-depth-sdxl-1.0-small
CIVORA_RENDERER_DEPTH_REVISION=daf3835d036574dff7c158882e8e77b75b024ee5
CIVORA_RENDERER_MODEL_LICENSE=openrail++
CIVORA_RENDERER_MODEL_LICENSE_ACKNOWLEDGED=true
CIVORA_RENDERER_EAGER_LOAD=true
CIVORA_RENDERER_USE_DEPTH_CONTROL=true
CIVORA_RENDERER_WIDTH=1344
CIVORA_RENDERER_HEIGHT=896
CIVORA_RENDERER_INFERENCE_STEPS=36
CIVORA_RENDERER_STRENGTH=0.48
CIVORA_RENDERER_CANNY_SCALE=0.95
CIVORA_RENDERER_DEPTH_SCALE=0.65
CIVORA_RENDERER_LOCAL_FILES_ONLY=false
HF_HOME=/models/huggingface
```

`HF_TOKEN` is optional for public weights. If the deployment policy requires zero runtime model-host access, warm the persistent model cache once, verify its contents, then set `CIVORA_RENDERER_LOCAL_FILES_ONLY=true` and restrict worker egress.

The worker deliberately uses one process and one render at a time. Scale with additional single-GPU replicas instead of increasing Uvicorn workers on one GPU.

## Main Backend

Set these variables on the Civora backend service:

```bash
CIVORA_IMAGE_PROVIDER=civora
CIVORA_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0
CIVORA_IMAGE_RENDERER_URL=https://your-private-renderer.example.com
CIVORA_IMAGE_RENDERER_TOKEN=the-same-token-with-at-least-32-characters
CIVORA_IMAGE_OUTPUT_FORMAT=webp
CIVORA_IMAGE_TIMEOUT_SECONDS=240
```

Do not put the renderer token in Vercel or any `NEXT_PUBLIC_*` variable. The browser talks only to the authenticated Civora API and job queue.
Both services reject renderer tokens shorter than 32 characters.

## Health and Proof

`GET /health` reports the engine, pinned revisions, license acknowledgement, GPU device, readiness, and no-retention posture. It never returns service tokens, prompts, or image data.

Before enabling Visual view for users, prove:

1. The worker health endpoint reports the pinned model and `photorealistic=true`.
2. Unauthorized `/v1/render` requests return 401.
3. Requests containing map imagery declarations are rejected.
4. A complex test layout preserves object count, footprint positions, road paths, basin placement, and building-height ordering.
5. Editing the project makes the old image stale and regeneration uses the new layout hash.
6. Inputs and outputs are absent from worker disk and logs after the request.

The renderer produces a visual concept. It does not change project geometry, engineering calculations, quantities, source confidence, or review deliverables.
