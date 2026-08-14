# Civora Imagery Detection Gateway Deploy

Use this to deploy Civora's imagery detector and isolated learned-model shadow evaluator as a separate hosted service.

## What This Service Does

- Receives Civora's address/site bbox payload at `/detect`.
- Creates a source imagery request from the active bbox/site boundary.
- Runs a fingerprinted, promoted ONNX model when `CIVORA_GATEWAY_DETECTOR_KIND=civora_model`.
- Can sample a blocked candidate in a bounded background shadow queue without changing or delaying user-visible candidates.
- Supports semantic segmentation so irregular roofs, roads, walks, water, and landscape regions can remain polygons instead of becoming generic boxes.
- Reports the exact model/version/hash and whether learned inference or an explicitly enabled heuristic fallback produced the candidates.
- Returns normalized visual candidates for buildings, roads, parking, sidewalks, trees/landscape, basins/ponds, and visible utility structures where detected.
- Keeps every output as review-required visual context only.

It does not create survey/control evidence, utility locates, professional acceptance, or final reliance evidence.

The repository ships one explicitly blocked Chat 246 shadow artifact with its test evidence and SpaceNet attribution. It is
not valid as a primary detector. A primary learned runtime without a promoted manifest and matching weights returns an
unavailable health state; it does not silently call the heuristic a learned model.

## Detector Modes

| Mode | Behavior |
| --- | --- |
| `civora_model` | Strict learned ONNX inference. Health returns 503 when the model is missing, unpromoted, tampered, or cannot load. |
| `civora_hybrid` | Learned inference first. It may use the heuristic only when `CIVORA_GATEWAY_ALLOW_HEURISTIC_FALLBACK=true`; responses identify the fallback. |
| `civora_heuristic` | Explicit approximate color/edge detector for development or continuity only. Never presented as learned inference. |
| `roboflow` | External Roboflow inference with normalized Civora outputs. |
| `generic` | External model service using Civora's normalized JSON adapter. |

Shadow is not another detector mode. With a heuristic baseline, `CIVORA_GATEWAY_SHADOW_ENABLED=true` samples requests,
queues learned inference after the baseline path, and stores aggregate agreement only. Shadow geometry never enters the
response candidate list. The queue is bounded and drops work rather than slowing or accumulating behind user traffic.
Attach a small persistent volume at `/data` before enabling shadow if metrics must survive a deployment restart. The
metrics file contains only counts, per-class agreement/IoU summaries, timestamps, and model identity. It never stores
imagery bytes, source URLs, addresses, bounding boxes, coordinates, or shadow geometry. Agreement between two detectors
is not an accuracy measurement and cannot promote a model.

Persisted shadow evidence uses `civora_vision_shadow_metrics_v2`, declares the aggregate-only storage scope, and carries
a SHA-256 integrity checksum. Readiness remains blocked until health proves a valid record was restored after a real
process restart. Missing, unreadable, version-mismatched, scope-mismatched, or tampered records are rejected.
Repository tests create the record in one Python process and restore it in a second independent process. That proves the
software path, not a hosted volume. A deployment still needs a mounted persistent volume and post-restart health capture.

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
CIVORA_GATEWAY_DETECTOR_KIND=civora
CIVORA_GATEWAY_MAPBOX_TOKEN=your_mapbox_token
CIVORA_GATEWAY_MAPBOX_STYLE=mapbox/satellite-v9
CIVORA_GATEWAY_IMAGE_SIZE=1024x1024
CIVORA_GATEWAY_CIVORA_MAX_SIZE=768
CIVORA_GATEWAY_MODEL_MANIFEST=/app/vision/models/civora_vision_model_manifest.json
CIVORA_GATEWAY_MODEL_PATH=/models/civora_semantic.onnx
CIVORA_GATEWAY_REQUIRE_PROMOTED_MODEL=true
CIVORA_GATEWAY_ALLOW_HEURISTIC_FALLBACK=false
CIVORA_GATEWAY_SHADOW_ENABLED=true
CIVORA_GATEWAY_SHADOW_MODE=async
CIVORA_GATEWAY_SHADOW_SAMPLE_RATE=0.05
CIVORA_GATEWAY_SHADOW_IOU_THRESHOLD=0.25
CIVORA_GATEWAY_ALLOW_SHADOW_FORCE=false
CIVORA_GATEWAY_SHADOW_MODEL_MANIFEST=/app/vision/models/shadow/chat246/candidate-manifest.json
CIVORA_GATEWAY_SHADOW_METRICS_PATH=/data/vision-shadow-metrics.json
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
CIVORA_IMAGERY_DETECTION_PROVIDER=civora_heuristic
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

Promotion additionally requires at least 0.85 precision and 0.75 recall overall and per required class, 100 held-out
objects overall, 25 per class, five geographies, two seasons, two imagery-quality bands, an independently excluded test
split, and a traceable human-reviewed or third-party benchmark attestation. Passing promotion authorizes visual review
candidates only.

Use [the example manifest](../vision/models/civora_vision_model_manifest.example.json) only as a schema reference. It is intentionally blocked and is not deployable.

## Rights-Cleared Training Pipeline

Use Python 3.11, matching the backend Docker image, for the training environment.

### Public weak-supervision bootstrap

The public bootstrap is useful for proving the data and training machinery before a reviewed corpus exists. It downloads
exact USDA NAIP catalog records from the USGS National Map and aligns separately licensed Microsoft building footprints
as weak labels. Image exports are locked to catalog raster IDs; unidentified or fallback imagery is rejected. The images
and labels retain independent source-rights records. Weak packages always use
`weak_labels_pending_review`, set `promotion_eligible=false`, and cannot produce a deployable model manifest.

Build the committed five-geography collection plan in one reproducible run:

```bash
PYTHONPATH=. python3 backend/scripts/bootstrap_public_vision_collection.py \
  --plan vision/datasets/us-conus-building-seed-v1.json \
  --source-registry vision/datasets/public-source-registry-v1.json \
  --output-root private/vision/collections/us-conus-building-seed-v1
```

This creates the merged weak package, source manifest, coverage report, zero-ground-truth review sprint, and standalone
review gallery. Source images and reviewer artifacts remain outside Git under `private/vision`.

Build the separate core-segmentation seed for buildings, approximate road corridors, and surface-water polygons:

```bash
PYTHONPATH=. python3 backend/scripts/bootstrap_public_vision_collection.py \
  --plan vision/datasets/us-conus-core-segmentation-seed-v1.json \
  --source-registry vision/datasets/public-source-registry-v1.json \
  --output-root private/vision/collections/us-conus-core-segmentation-seed-v1
```

The road source is U.S. Census TIGERweb centerline data buffered into approximate corridors, not pavement-edge truth.
The surface-water source is USGS NHD mapped hydrography. Both can differ from the contemporaneous aerial frame, remain
weak proposals, and require accept/reject/redraw review before training. Empty classes at a location remain empty.

For the broader V3 diagnostic, use `vision/datasets/us-conus-core-segmentation-v3.json` with `--resume`. The merger writes
separate training/validation and frozen-test packages. Train only from `training-validation-coco-package.json`, select
thresholds on its three validation geographies, and pass `frozen-test-coco-package.json` only to the final evaluator. The
five frozen test geographies are opened once. Even a strong weak-label diagnostic remains blocked until reviewed
correction coverage, independent attested ground truth, durable live shadow evidence, baseline comparison, and named
approval all pass. The measured V3 candidate was rejected before deployment; see
`vision/datasets/us-conus-core-segmentation-diagnostic-v3-report.json`.

### Independent SpaceNet benchmark import

The SpaceNet 2 importer converts official RGB PanSharpen imagery and building polygons into a traceable COCO package.
It preserves source/label/output hashes, attribution, license, four geography-balanced splits, and an independently held-out
test set. Source imagery remains outside Git.

```bash
PYTHONPATH=. python3 -m backend.scripts.import_spacenet_benchmark \
  --root private/vision/source/spacenet2 \
  --output-dir private/vision/benchmarks/spacenet2
```

SpaceNet 2 alone does not meet Civora's production coverage gate because the sample lacks season metadata, has one imagery
quality band, and covers four geographies. The bundled Chat 246 candidate also failed precision and recall gates; it is
retained only to prove safe shadow operations.

Build small, geographically varied packages under the ignored `private/vision` directory:

```bash
PYTHONPATH=. python3 backend/scripts/bootstrap_public_vision_dataset.py \
  --center-lat 41.1852405 \
  --center-lon -96.2370225 \
  --rows 4 \
  --columns 4 \
  --tile-meters 320 \
  --image-pixels 512 \
  --output-root private/vision/bootstrap/gretna-v1
```

Merge independent locations without losing their image IDs, split assignments, licenses, or fingerprints:

```bash
PYTHONPATH=. python3 backend/scripts/merge_public_vision_datasets.py \
  --package private/vision/bootstrap/gretna-v1/weak-coco-package.json \
  --package private/vision/bootstrap/dallas-v1/weak-coco-package.json \
  --package private/vision/bootstrap/denver-v1/weak-coco-package.json \
  --output-root private/vision/bootstrap/multi-city-v1
```

Train and run the physically separated weak-label diagnostic:

```bash
python3.11 -m venv private/vision/training-venv
private/vision/training-venv/bin/pip install \
  -r requirements_vision_training.txt \
  -r requirements_imagery_gateway.txt

PYTHONPATH=. private/vision/training-venv/bin/python vision/train_semantic_model.py \
  --dataset private/vision/bootstrap/multi-city-v1/training-validation-coco-package.json \
  --image-root private/vision/bootstrap/multi-city-v1/images \
  --output-dir private/vision/runs/multi-city-building-v1

PYTHONPATH=. private/vision/training-venv/bin/python -m backend.scripts.run_vision_model_diagnostic \
  --model private/vision/runs/multi-city-building-v1/civora_semantic.onnx \
  --classes private/vision/runs/multi-city-building-v1/classes.json \
  --dataset private/vision/bootstrap/multi-city-v1/training-validation-coco-package.json \
  --image-root private/vision/bootstrap/multi-city-v1/images \
  --output-dir private/vision/runs/multi-city-building-v1/validation \
  --split validation

PYTHONPATH=. private/vision/training-venv/bin/python -m backend.scripts.calibrate_vision_model_thresholds \
  --predictions private/vision/runs/multi-city-building-v1/validation/predictions.json \
  --ground-truth private/vision/runs/multi-city-building-v1/validation/ground-truth.json \
  --dataset private/vision/bootstrap/multi-city-v1/training-validation-coco-package.json \
  --output private/vision/runs/multi-city-building-v1/threshold-calibration.json

PYTHONPATH=. private/vision/training-venv/bin/python -m backend.scripts.run_vision_model_diagnostic \
  --model private/vision/runs/multi-city-building-v1/civora_semantic.onnx \
  --classes private/vision/runs/multi-city-building-v1/classes.json \
  --dataset private/vision/bootstrap/multi-city-v1/frozen-test-coco-package.json \
  --training-dataset private/vision/bootstrap/multi-city-v1/training-validation-coco-package.json \
  --evaluation-reservation-manifest private/vision/bootstrap/multi-city-v1/evaluation-reservation-manifest.json \
  --calibration private/vision/runs/multi-city-building-v1/threshold-calibration.json \
  --image-root private/vision/bootstrap/multi-city-v1/images \
  --test-consumption-ledger private/vision/evidence/frozen-test-consumption-ledger.json \
  --output-dir private/vision/runs/multi-city-building-v1/diagnostic
```

The test runner first validates the candidate class map, ONNX load, synthetic inference, validation-only calibration, and
the exact development-package bytes. Calibration records must exactly match the reviewed validation annotations in that
package, and the calibration is bound to the package and model SHA-256 values. These failures do not consume the test set. It then atomically reserves the frozen
evidence before parsing frozen records or opening image bytes, records a label-blind tamper-evident receipt bound to the
exact validation calibration in a durable
ledger, and runs the heuristic baseline in the same campaign as the learned candidate using the same verified image bytes.
A second use of those source identities fails closed, including after repackaging. The reservation and receipt disclose no
test annotation counts, class counts, source URLs, or locations. Standalone test evaluation and standalone test-baseline
commands are disabled so two separate runs cannot quietly create incompatible comparison evidence. Validation runs remain
available for diagnostics and threshold selection. The diagnostic deliberately scopes matching by image ID. Its precision/recall are weak-label
diagnostics, not independent ground-truth measurements. Review every candidate image, correct omissions and geometry,
reserve multiple untouched geographies for evaluation, export a `reviewer_labeled` package, and only then use the promotion
command below.

1. Collect candidate accept/reject/correct/redraw feedback through Civora Vision.
2. Register only local source images whose licenses permit both storage and model training. The asset registry must map `imagery_frame_id` to a safe relative `file_name`, dimensions, SHA-256, and source-rights record.
3. Export a deterministic COCO package:

```bash
PYTHONPATH=. python3 backend/scripts/export_vision_training_dataset.py \
  --learning-package reports/vision/learning-package.json \
  --asset-registry private/vision/asset-registry.json \
  --output private/vision/reviewed-coco-package.json
```

When all three deterministic splits are present, this command also writes
`reviewed-coco-package-training-validation.json`, `reviewed-coco-package-frozen-test.json`, and
`reviewed-coco-package-evaluation-reservation.json`. If the reviewed corpus is too small or misses a split/class, the
combined audit manifest is still written, but `split_artifacts_ready` is false with an exact reason. Do not train or
promote from the combined audit manifest.

4. Train Civora's semantic model on a GPU-capable training machine:

```bash
python3 -m pip install -r requirements_vision_training.txt
PYTHONPATH=. python3 vision/train_semantic_model.py \
  --dataset private/vision/reviewed-coco-package-training-validation.json \
  --image-root private/vision/images \
  --output-dir private/vision/runs/v1
```

The trainer emits ONNX weights and run metrics, but deliberately marks the model unready for promotion. Training loss or pixel IoU alone is not deployment proof.

5. Run the candidate against validation and freeze its thresholds without opening test evidence:

```bash
PYTHONPATH=. python3 -m backend.scripts.run_vision_model_diagnostic \
  --model private/vision/runs/v1/civora_semantic.onnx \
  --classes private/vision/runs/v1/classes.json \
  --dataset private/vision/reviewed-coco-package-training-validation.json \
  --image-root private/vision/images \
  --output-dir private/vision/runs/v1/validation \
  --split validation

PYTHONPATH=. python3 -m backend.scripts.calibrate_vision_model_thresholds \
  --predictions private/vision/runs/v1/validation/predictions.json \
  --ground-truth private/vision/runs/v1/validation/ground-truth.json \
  --dataset private/vision/reviewed-coco-package-training-validation.json \
  --output private/vision/runs/v1/threshold-calibration.json
```

6. Run object-level evaluation once against a separate rights-cleared ground-truth set. Use a new empty output directory:

```bash
PYTHONPATH=. python3 -m backend.scripts.run_vision_model_diagnostic \
  --model private/vision/runs/v1/civora_semantic.onnx \
  --classes private/vision/runs/v1/classes.json \
  --dataset private/vision/reviewed-coco-package-frozen-test.json \
  --training-dataset private/vision/reviewed-coco-package-training-validation.json \
  --evaluation-reservation-manifest private/vision/reviewed-coco-package-evaluation-reservation.json \
  --calibration private/vision/runs/v1/threshold-calibration.json \
  --image-root private/vision/images \
  --test-consumption-ledger private/vision/evidence/frozen-test-consumption-ledger.json \
  --output-dir private/vision/evaluation
```

7. Create the fingerprinted model manifest. Promotion fails if ground-truth metrics, provenance, license, dataset fingerprint, or approver are missing:

```bash
PYTHONPATH=. python3 backend/scripts/promote_vision_model.py \
  --model private/vision/runs/v1/civora_semantic.onnx \
  --quality-report private/vision/evaluation/quality.json \
  --training-dataset-package private/vision/reviewed-coco-package-training-validation.json \
  --evaluation-dataset-package private/vision/reviewed-coco-package-frozen-test.json \
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
10. For a promoted primary model, confirm `/detect` metadata says `learned_model_used: true` and `fallback_used: false`.
11. For shadow, confirm the response keeps baseline providers, `shadow_influenced_user_candidates: false`, and health shows
    bounded submitted/completed/failed/dropped counts. Never use shadow agreement as an accuracy metric.

The gateway image enables the bundled blocked candidate only as a five-percent asynchronous shadow by default. It cannot
add, replace, or modify user-visible candidates. Set `CIVORA_GATEWAY_SHADOW_ENABLED=false` for immediate rollback. Keep
`CIVORA_GATEWAY_ALLOW_SHADOW_FORCE=false` on hosted services; the force switch exists only for explicit local diagnostics.
Attach a persistent volume at `/data` if aggregate metrics must survive deployment replacement.

The feedback manifest does not claim model accuracy. Precision/recall are reported only after a separate rights-cleared ground-truth set is evaluated. The current geometric score is explicitly class-aware bounding-box IoU.

If imagery scan says not configured, check `CIVORA_IMAGERY_DETECTION_URL` on the main backend and `CIVORA_GATEWAY_MAPBOX_TOKEN` on the gateway service.
