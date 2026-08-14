# Civora Vision Ground-Truth Flywheel

## Purpose

Civora Vision may propose visible-feature candidates such as buildings, roads, parking, sidewalks, surface water, vegetation, and visible site constraints. A proposal is not ground truth. The flywheel converts explicit reviewer work into auditable model-development evidence without changing the user-visible detector or making an accuracy claim.

Imagery cannot establish legal boundaries, survey control, datum, buried utilities, pipe elevations, final grading surfaces, code compliance, or engineering approval. Those require authoritative records, project uploads, field evidence, and qualified professional review.

## Review Workflow

1. Apply an address and collect source-backed site context.
2. Open Data and review visual candidates in priority order.
3. Accept or reject a correct/incorrect candidate.
4. Reclassify the detected type when the geometry is useful but the class is wrong.
5. Edit a user-drawn outline's vertices in Draw and attach that outline as a redraw.
6. Select two or more detections plus one edited outline to merge them.
7. Select one detection plus two or more edited outlines to split it.
8. Export the project learning manifest. Source image bytes are not included.

Every operation appends a hash-chained event. Events are never edited in place. A later review supersedes the active label while preserving the earlier event.

## Dataset Isolation

The imagery frame, rather than each polygon, receives a permanent deterministic split assignment. All labels from the same frame stay in one of `train`, `validation`, or `test`. Test labels cannot be used for training or model selection.

Use the aggregate exporter for reviewed project manifests:

```bash
python3 backend/scripts/export_vision_ground_truth_dataset.py \
  reports/project-a-vision.json reports/project-b-vision.json \
  --learning-consent reports/project-a-learning-consent.json \
  --learning-consent reports/project-b-learning-consent.json \
  --output reports/vision/ground-truth-dataset.json \
  --coverage-output reports/vision/ground-truth-coverage.json \
  --privacy-aggregate-output reports/vision/privacy-safe-correction-summary.json
```

The exporter fails closed when event integrity is invalid, frame split assignments conflict, source rights are missing, or reviewed geometry is not registered to imagery.
Each source package also needs explicit, revocable `model_training` and `cross_project_aggregation` consent from a data
owner or company administrator, bound to that package fingerprint. A privacy-safe correction summary may aggregate class,
action, split, and blocker counts; it excludes imagery, geometry, locations, source URLs, project/candidate identifiers,
and reviewer identities and is never itself training input.

## Data Rights And Provenance

Each usable label needs:

- a source frame identifier and sanitized source URL;
- provider and source fingerprint;
- explicit training-use rights and license;
- stored/retrievable imagery permission where required by the model pipeline;
- reviewer identity, time, action, and reason;
- original candidate and corrected geometry;
- coordinate space and imagery registration;
- geography, capture season, and imagery quality band when known.

Do not add a dataset merely because it is publicly downloadable. Record the license and whether model training, derivative labels, storage, and redistribution are allowed.

## Rights-Cleared Public Seed Collection

The committed source registry at `vision/datasets/public-source-registry-v1.json` is the machine-readable allowlist for
public bootstrap sources. The initial collection plan at `vision/datasets/us-conus-building-seed-v1.json` requests 20
tiles across Gretna, Dallas, Denver, Phoenix, and Charlotte. Source images and generated review artifacts stay under the
ignored `private/vision` directory.

The collector accepts only exact USDA NAIP catalog records from the registered USGS ImageServer. Every image export uses
an `esriMosaicLockRaster` rule with the selected catalog object IDs. Commercial, unidentified, non-NAIP, non-CONUS, or
fallback imagery is rejected. Microsoft Global ML Building Footprints are used only as separately licensed weak proposals.

The separate `vision/datasets/us-conus-core-segmentation-seed-v1.json` plan keeps those building proposals and adds U.S.
Census TIGERweb road centerlines buffered as approximate road corridors plus USGS NHD surface-water polygons. All three
classes remain weak proposals. Road corridors are not surveyed pavement edges, mapped water can be stale, and neither
source becomes ground truth without explicit review against the registered NAIP frame.

The V3 development plan at `vision/datasets/us-conus-core-segmentation-v3.json` expands the diagnostic corpus to 15
geography-disjoint regions: seven training, three validation, and five frozen test regions. Its merged package carries a
weak-package fingerprint and a separate canonical COCO evidence fingerprint. The merger emits physically separate
`training-validation-coco-package.json` and `frozen-test-coco-package.json` artifacts. The trainer accepts only the former.
Its held-out reference is label-blind: it includes immutable image-membership hashes but no test image records,
annotation records, annotation counts, per-class counts, source URLs, or locations. The sealed evaluation package SHA-256
binds the complete hidden package without exposing its labels to model development.
The development package is built from an explicit metadata allowlist rather than by copying the source package and deleting
known test fields. This prevents geography names, source-availability messages, or future unrecognized metadata from
crossing the frozen-test boundary. Tests reject arbitrary top-level side channels as well as label statistics in the
reservation, receipt, ledger, held-out commitment, or threshold-calibration artifact.

The final evaluator requires the V2 `evaluation-reservation-manifest.json` emitted beside those packages. Before consuming
the test set it validates the model artifact and class map, loads the ONNX runtime, runs synthetic inference, verifies the
validation-only calibration, and validates the exact development-package bytes against the reservation. It then atomically
records the candidate, model hash, exact validation-calibration fingerprint, evaluation fingerprint, image-membership commitment, and hashed source identities in a
durable one-way ledger. Only after reservation succeeds may it parse the frozen package or open test image bytes. It gives
the exact same verified image bytes to the learned candidate and heuristic baseline in that single campaign, then refuses
every subsequent use of those source identities even when repackaged under another dataset fingerprint.
The ledger stores only SHA-256 digests of source identities, not source URLs or locations, and blocks reuse even if the same
images are repackaged under a different dataset fingerprint. Standalone test evaluation is disabled. `--resume` reuses a
region only after validating its package, manifest, geography, split, every registered image file, and complete per-source
availability status. Legacy packages without that status must be recollected rather than silently accepted.
Candidate weights, class map, reservation, calibration, development package, frozen package, image root, ledger, and
diagnostic output must remain physically distinct. The evaluator rejects aliases, hard links, evidence files placed inside
the image root, a disposable ledger, and non-empty test output directories before opening frozen records.
Calibration accepts only reviewed validation annotations that exactly match the development package and binds its result to
the exact development-package SHA-256, model SHA-256, validation fingerprint, and training fingerprint. Editing a copied
ground-truth file, changing the package bytes, or adding undeclared calibration fields fails closed.

V3 calls the visible class `surface_water`. A surface-water polygon is not automatically a detention basin, pond,
wetland, stream, pool, or drainage facility. A reviewer must assign that engineering meaning after accepting it.

The collector reports proposal counts by class and permanent split. The trainer refuses a declared class that is absent
from train or validation and records measured class weights. Frozen-test class depth is checked independently by the
evaluation and promotion gates, never by training. The first 45-frame diagnostic is documented in
`vision/datasets/us-conus-core-segmentation-diagnostic-v2-report.json`. It was rejected before deployment: its held-out
weak-label F1 was `0.0208`, building and basin recall were zero, and no labels had completed human review. This report is
rejection evidence, not an accuracy claim.

The expanded 135-frame V3 run is documented in
`vision/datasets/us-conus-core-segmentation-diagnostic-v3-report.json`. Its physical split isolation and frozen-manifest
integrity passed, but it was also rejected. Against 45 untouched test frames with weak, unattested labels, the learned
candidate produced F1 `0.0037` versus the existing heuristic's `0.0147`, with zero building and road recall. No candidate
weights or manifest were deployed as primary or shadow. These values are weak-label diagnostics, not accuracy estimates.
Because this one-way test package was opened for V3, it is recorded as consumed and is not untouched evidence for a future
candidate. This first V3 run predates both the atomic ledger and the label-blind V2 reservation. Its legacy reservation
exposed aggregate label statistics, so its durable receipt is explicitly historical post-hoc rejection evidence and can
never satisfy a current promotion gate. A later candidate requires a newly sealed geography-disjoint test package, a V2
label-blind reservation, and a pre-evaluation atomic receipt.
The legacy V3 development artifact also inherited one test-geography source-availability message through permissive
top-level metadata copying. It did not contain test image or annotation records, but it still violated the intended
label-blind development boundary. The current allowlisted package builder fixes that defect; the historical V3 result
remains rejected and cannot be reclassified as current-protocol evidence.

Collect the planned corpus and create a zero-ground-truth review sprint:

```bash
PYTHONPATH=. python3 backend/scripts/bootstrap_public_vision_collection.py \
  --plan vision/datasets/us-conus-building-seed-v1.json \
  --source-registry vision/datasets/public-source-registry-v1.json \
  --output-root private/vision/collections/us-conus-building-seed-v1
```

Build or resume the V3 diagnostic corpus:

```bash
python3 backend/scripts/bootstrap_public_vision_collection.py \
  --plan vision/datasets/us-conus-core-segmentation-v3.json \
  --source-registry vision/datasets/public-source-registry-v1.json \
  --output-root private/vision/collections/us-conus-core-segmentation-v3 \
  --resume
```

Open the generated reviewer from an HTTP server so its checksum exporter is available:

```bash
cd private/vision/collections/us-conus-building-seed-v1/merged
python3 -m http.server 8088
```

Reviewers compare each outline with the registered image, enter a reviewer identity, attest that the source frame was
inspected, and export `vision-review-decisions.json`. Accept and reject are supported in the gallery. Geometry correction,
split, and merge work belongs in Civora Draw so the edited geometry is itself reviewable.

Apply the checksum-protected decision file to the append-only ledger:

```bash
PYTHONPATH=. python3 backend/scripts/apply_public_vision_review_decisions.py \
  --review-sprint private/vision/collections/us-conus-building-seed-v1/merged/vision-review-sprint.json \
  --decisions /path/to/vision-review-decisions.json \
  --output private/vision/collections/us-conus-building-seed-v1/merged/review-result.json
```

The handoff fails closed for changed source packages, changed sprints, missing attestation, duplicate candidates, unknown
actions, or a changed decision checksum. A valid result creates reviewer-attributed training evidence only. It does not
approve a model, establish survey/control, or change any project output.

## AI-Assisted Review Triage

AI-assisted triage can make a large review sprint easier to inspect without impersonating a reviewer. It verifies every
registered image fingerprint, measures each proposal against local image context, renders one evidence crop per proposal,
and produces contact sheets ordered for review. Its only recommendations are `likely_accept`, `likely_reject`, and
`redraw_or_human_review`.

Run triage against a verified sprint:

```bash
PYTHONPATH=. python3 backend/scripts/triage_public_vision_review_sprint.py \
  --review-sprint private/vision/collections/us-conus-building-seed-v1/merged/vision-review-sprint.json \
  --image-root private/vision/collections/us-conus-building-seed-v1/merged/images \
  --output-root private/vision/triage/us-conus-building-seed-v1
```

Optional AI visual overrides use `civora_public_vision_ai_triage_overrides_v1` and must declare
`reviewer_type: ai_assisted_non_human`. They can only change recommendation priority; they cannot claim human review.
The resulting `civora_public_vision_ai_triage_v1` artifact always records:

- `human_attestation_present: false`;
- `ground_truth_eligible: false`;
- `ledger_append_allowed: false`;
- `promotion_eligible: false`;
- `human_review_required: true` on every candidate.

The human decision importer rejects AI triage artifacts because they use a separate version and do not contain a named
reviewer attestation. A person must still inspect each submitted decision against its registered source frame before it can
enter the append-only ledger.

## Coverage Targets

The reviewer workspace reports a development target of 500 reviewed annotations per supported class, at least five geographies, two seasons, and two imagery-quality bands. These are collection targets, not model promotion gates and not a promise that 500 labels are sufficient. Dense or diverse classes may require thousands of reviewed examples.

Supported learning classes are:

- building footprint;
- road or driveway;
- parking area;
- sidewalk or path;
- water, pond, or basin;
- vegetation or tree area;
- visible utility object;
- visible constraint area.

## Active Learning

The queue prioritizes pending candidates using uncertainty, source disagreement, baseline-versus-shadow disagreement, class underrepresentation, overlap with other sources, and rights-cleared learning value. Priority only orders review work. It never accepts a candidate or changes visible geometry.

## Model Promotion

Promotion is per class. A class remains blocked until it has:

- adequate reviewed coverage;
- independent held-out precision, recall, F1, and geometry metrics;
- permanent split isolation;
- license and dataset attestations;
- a reproducible model artifact and training revision;
- explicit named human approval.

Even a promoted class may create visual review candidates only. It does not become survey, control, utility-locate, compliance, or engineering evidence.

## Safe Deployment Sequence

1. Keep the heuristic provider visible.
2. Run an unpromoted candidate on a bounded background shadow sample.
3. Collect disagreement cases through the active-learning queue.
4. Train a new candidate from train frames only.
5. Select thresholds with validation frames only.
6. Evaluate once on untouched test frames.
7. Review per-class gates and provenance.
8. Require named human approval for each class.
9. Roll out the approved class gradually while retaining rollback and monitoring.

The fail-closed V3 readiness report has five independent lanes: durable privacy-safe shadow monitoring, consented
reviewed corrections, reviewed training evidence, frozen independent evaluation, and model promotion. Shadow evidence
must survive a restart with a valid checksum and aggregate-only storage scope, include at least 100 samples, cover every
required class, and remain below the bounded failure/drop-rate gate. Shadow agreement is operational evidence only; it
cannot substitute for ground-truth precision or recall. If any lane is blocked, do not deploy the candidate.

Generate the readiness report with the physically isolated packages and explicit evidence inputs:

```bash
PYTHONPATH=. python3 backend/scripts/report_vision_v3_readiness.py \
  --training-dataset private/vision/collections/us-conus-core-segmentation-v3/merged/training-validation-coco-package.json \
  --evaluation-dataset private/vision/collections/us-conus-core-segmentation-v3/merged/frozen-test-coco-package.json \
  --quality-report private/vision/runs/us-conus-core-segmentation-v3/test-diagnostic/diagnostic-quality.json \
  --correction-coverage private/vision/reviewed-corrections/ground-truth-coverage.json \
  --gateway-health-file private/vision/evidence/gateway-health-after-restart.json \
  --output private/vision/evidence/vision-v3-readiness.json \
  --allow-blocked
```

`--allow-blocked` only permits the CLI to save a truthful blocked report for inspection. It does not relax a gate or
authorize deployment.
