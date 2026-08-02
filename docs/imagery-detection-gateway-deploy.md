# Civora Imagery Detection Gateway Deploy

Use this to deploy Civora's learned imagery detector as a separate hosted service.

## What This Service Does

- Receives Civora's address/site bbox payload at `/detect`.
- Creates a source imagery request from the active bbox/site boundary.
- Runs a fingerprinted, promoted ONNX model when `CIVORA_GATEWAY_DETECTOR_KIND=civora_model`.
- Supports semantic segmentation so irregular roofs, roads, walks, water, and landscape regions can remain polygons instead of becoming generic boxes.
- Reports the exact model/version/hash and whether learned inference or an explicitly enabled heuristic fallback produced the candidates.
- Returns normalized visual candidates for buildings, roads, parking, sidewalks, trees/landscape, basins/ponds, and visible utility structures where detected.
- Keeps every output as review-required visual context only.

It does not create survey/control evidence, utility locates, professional acceptance, or final reliance evidence.

The repository does not ship trained weights. A runtime without a valid promoted manifest and matching weights returns an unavailable health state; it does not silently call the heuristic a learned model.

## Detector Modes

| Mode | Behavior |
| --- | --- |
| `civora_model` | Strict learned ONNX inference. Health returns 503 when the model is missing, unpromoted, tampered, or cannot load. |
| `civora_hybrid` | Learned inference first. It may use the heuristic only when `CIVORA_GATEWAY_ALLOW_HEURISTIC_FALLBACK=true`; responses identify the fallback. |
| `civora_heuristic` | Explicit approximate color/edge detector for development or continuity only. Never presented as learned inference. |
| `roboflow` | External Roboflow inference with normalized Civora outputs. |
| `generic` | External model service using Civora's normalized JSON adapter. |

`civora` remains a backward-compatible alias for `civora_heuristic`. New deployments should use an explicit mode.

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
CIVORA_GATEWAY_DETECTOR_KIND=civora_model
CIVORA_GATEWAY_MAPBOX_TOKEN=your_mapbox_token
CIVORA_GATEWAY_MAPBOX_STYLE=mapbox/satellite-v9
CIVORA_GATEWAY_IMAGE_SIZE=1024x1024
CIVORA_GATEWAY_CIVORA_MAX_SIZE=768
CIVORA_GATEWAY_MODEL_MANIFEST=/app/vision/models/civora_vision_model_manifest.json
CIVORA_GATEWAY_MODEL_PATH=/models/civora_semantic.onnx
CIVORA_GATEWAY_REQUIRE_PROMOTED_MODEL=true
CIVORA_GATEWAY_ALLOW_HEURISTIC_FALLBACK=false
CIVORA_GATEWAY_BEARER_TOKEN=generate-a-long-random-service-token
CIVORA_GATEWAY_IMAGE_HOST_ALLOWLIST=api.mapbox.com
CIVORA_GATEWAY_MAX_IMAGE_BYTES=15728640
CIVORA_GATEWAY_ALLOW_PRIVATE_IMAGE_URLS=false
CIVORA_GATEWAY_ALLOW_INSECURE_IMAGE_URLS=false
CIVORA_GATEWAY_ALLOW_UNKNOWN_IMAGE_CONTENT_TYPE=false
CIVORA_GATEWAY_SOURCE_LICENSE=unconfirmed
CIVORA_GATEWAY_SOURCE_ATTRIBUTION=
CIVORA_GATEWAY_SOURCE_RIGHTS_URL=
CIVORA_GATEWAY_TRAINING_USE_ALLOWED=false
CIVORA_GATEWAY_SOURCE_STORAGE_ALLOWED=false
CIVORA_GATEWAY_TRUST_REQUEST_SOURCE_RIGHTS=false
```

The rights flags default to `false`. Do not enable training or source-image storage merely because an image can be fetched. Confirm the provider license and record the supporting rights URL first. `CIVORA_GATEWAY_TRUST_REQUEST_SOURCE_RIGHTS` should remain `false` for a public gateway; otherwise an untrusted request could claim rights it does not have.

After Railway deploys it, copy the public gateway URL, for example:

```text
https://civora-imagery-gateway.up.railway.app
```

Then set these variables on the main Civora backend service:

```bash
CIVORA_IMAGERY_DETECTION_PROVIDER=civora_learned
CIVORA_IMAGERY_DETECTION_URL=https://civora-imagery-gateway.up.railway.app/detect
CIVORA_IMAGERY_DETECTION_TOKEN=the-same-service-token
```

The gateway token is optional for local development but should be required on a hosted service. The main API already sends `CIVORA_IMAGERY_DETECTION_TOKEN` as a bearer token. Keep source-image hosts allowlisted; private/non-routable addresses, non-HTTPS URLs, non-image responses, and oversized downloads are rejected by default.

## Model Contract

The runtime accepts two adapters:

- `civora_semantic_v1`: ONNX output `logits` shaped `[batch, classes, height, width]`. Class 0 is normally background. Civora polygonizes connected semantic regions.
- `civora_detection_v1`: ONNX outputs `boxes`, `scores`, `class_ids`, and optional `masks`.

Promoted manifests default to overlapping `tile_mode: auto` inference. Large aerial frames are processed at native model tile resolution, shifted back into the full image coordinate space, and class-aware deduplicated. This prevents small site features from disappearing solely because a 1024px source was squeezed into a smaller model input.

Every deployed manifest must include:

- model name/version and ONNX adapter;
- class map and input/output names;
- exact weights SHA-256;
- rights-cleared dataset fingerprint and model license;
- measured ground-truth metrics;
- `approved_for_review_candidates` promotion status and approver.

Use [the example manifest](../vision/models/civora_vision_model_manifest.example.json) only as a schema reference. It is intentionally blocked and is not deployable.

## Rights-Cleared Training Pipeline

1. Collect candidate accept/reject/correct/redraw feedback through Civora Vision.
2. Register only local source images whose licenses permit both storage and model training. The asset registry must map `imagery_frame_id` to a safe relative `file_name`, dimensions, SHA-256, and source-rights record.
3. Export a deterministic COCO package:

```bash
PYTHONPATH=. python3 backend/scripts/export_vision_training_dataset.py \
  --learning-package reports/vision/learning-package.json \
  --asset-registry private/vision/asset-registry.json \
  --output private/vision/coco-package.json
```

4. Train Civora's semantic model on a GPU-capable training machine:

```bash
python3 -m pip install -r requirements_vision_training.txt
PYTHONPATH=. python3 vision/train_semantic_model.py \
  --dataset private/vision/coco-package.json \
  --image-root private/vision/images \
  --output-dir private/vision/runs/v1
```

The trainer emits ONNX weights and run metrics, but deliberately marks the model unready for promotion. Training loss or pixel IoU alone is not deployment proof.

5. Run object-level evaluation against a separate rights-cleared ground-truth set:

```bash
PYTHONPATH=. python3 backend/scripts/evaluate_vision_model.py \
  --predictions private/vision/evaluation/predictions.json \
  --ground-truth private/vision/evaluation/ground-truth.json \
  --output private/vision/evaluation/quality.json
```

6. Create the fingerprinted model manifest. Promotion fails if ground-truth metrics, provenance, license, dataset fingerprint, or approver are missing:

```bash
PYTHONPATH=. python3 backend/scripts/promote_vision_model.py \
  --model private/vision/runs/v1/civora_semantic.onnx \
  --quality-report private/vision/evaluation/quality.json \
  --dataset-package private/vision/coco-package.json \
  --classes private/vision/runs/v1/classes.json \
  --name civora-aerial-segmentation \
  --version v1 \
  --approved-by model-reviewer-id \
  --model-license internal-rights-cleared \
  --training-code-revision GIT_SHA \
  --adapter civora_semantic_v1 \
  --input-size 512 \
  --output private/vision/runs/v1/model-manifest.json
```

Do not commit licensed source imagery, private asset registries, or model artifacts unless their storage/distribution rights explicitly permit it.

## Local Runtime Proof

Run:

```bash
python3 -m pip install -r requirements_backend.txt
CIVORA_GATEWAY_DETECTOR_KIND=civora_model \
CIVORA_GATEWAY_MODEL_MANIFEST=/absolute/path/model-manifest.json \
CIVORA_GATEWAY_MODEL_PATH=/absolute/path/civora_semantic.onnx \
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
7. Correct a visual candidate's type, or select a user-drawn outline and save it as the corrected geometry.
8. Export the Civora Vision feedback manifest and confirm it contains review labels/provenance but no source image bytes or access tokens.
9. Confirm `/health` says `learned_model_ready: true`, `capability_level: learned_model_review_candidates`, and shows the expected model hash.
10. Confirm `/detect` metadata says `learned_model_used: true` and `fallback_used: false`.

The feedback manifest does not claim model accuracy. Precision/recall are reported only after a separate rights-cleared ground-truth set is evaluated. The current geometric score is explicitly class-aware bounding-box IoU.

If imagery scan says not configured, check `CIVORA_IMAGERY_DETECTION_URL` on the main backend and `CIVORA_GATEWAY_MAPBOX_TOKEN` on the gateway service.
