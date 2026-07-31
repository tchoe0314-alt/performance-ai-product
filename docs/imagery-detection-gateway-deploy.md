# Civora Imagery Detection Gateway Deploy

Use this to deploy the built-in Civora Detector v1 as a separate hosted service.

## What This Service Does

- Receives Civora's address/site bbox payload at `/detect`.
- Creates a source imagery request from the active bbox/site boundary.
- Runs Civora's built-in heuristic detector when `CIVORA_GATEWAY_DETECTOR_KIND=civora`.
- Returns normalized visual candidates for buildings, roads, parking, sidewalks, trees/landscape, basins/ponds, and visible utility structures where detected.
- Keeps every output as review-required visual context only.

It does not create survey/control evidence, utility locates, professional acceptance, or final reliance evidence.

## Railway Service Setup

Create a second Railway service from the same GitHub repo.

Set the Railway config file path to:

```text
railway.imagery-gateway.toml
```

Use:

```text
Dockerfile.imagery-gateway
```

Set the health check path to:

```text
/health
```

Set these variables on the gateway service:

```bash
CIVORA_GATEWAY_DETECTOR_KIND=civora
CIVORA_GATEWAY_MAPBOX_TOKEN=your_mapbox_token
CIVORA_GATEWAY_MAPBOX_STYLE=mapbox/satellite-v9
CIVORA_GATEWAY_IMAGE_SIZE=1024x1024
CIVORA_GATEWAY_CIVORA_MAX_SIZE=768
```

After Railway deploys it, copy the public gateway URL, for example:

```text
https://civora-imagery-gateway.up.railway.app
```

Then set these variables on the main Civora backend service:

```bash
CIVORA_IMAGERY_DETECTION_PROVIDER=civora_heuristic
CIVORA_IMAGERY_DETECTION_URL=https://civora-imagery-gateway.up.railway.app/detect
CIVORA_IMAGERY_DETECTION_TOKEN=
```

## Local Proof

Run:

```bash
python3 -m pip install -r requirements_backend.txt
CIVORA_GATEWAY_DETECTOR_KIND=civora \
CIVORA_GATEWAY_SOURCE_MODE=direct \
python3 -m uvicorn backend.scripts.imagery_detection_gateway:app --host 127.0.0.1 --port 8090
```

Health:

```bash
curl --fail http://127.0.0.1:8090/health
```

Detect with a direct source image:

```bash
curl --fail -X POST http://127.0.0.1:8090/detect \
  -H 'Content-Type: application/json' \
  -d '{"image_url":"https://example.com/aerial-image.png"}'
```

For address/bbox-driven detection, remove `CIVORA_GATEWAY_SOURCE_MODE=direct` and provide `CIVORA_GATEWAY_MAPBOX_TOKEN`.

## Validation

After both services are deployed:

1. Open Civora.
2. Start a new project.
3. Apply an address and site boundary.
4. Confirm Auto Site Context shows an `Imagery scan` row.
5. Confirm detected items are candidates, not automatically trusted objects.
6. Accept/reject candidates from source review/Object Manager.

If imagery scan says not configured, check `CIVORA_IMAGERY_DETECTION_URL` on the main backend and `CIVORA_GATEWAY_MAPBOX_TOKEN` on the gateway service.
