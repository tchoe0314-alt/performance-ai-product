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
  --output reports/vision/ground-truth-dataset.json \
  --coverage-output reports/vision/ground-truth-coverage.json
```

The exporter fails closed when event integrity is invalid, frame split assignments conflict, source rights are missing, or reviewed geometry is not registered to imagery.

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

The collector reports proposal counts by class and permanent split. The trainer refuses a declared class that is absent
from train, validation, or test, and records measured class weights. The first 45-frame diagnostic is documented in
`vision/datasets/us-conus-core-segmentation-diagnostic-v2-report.json`. It was rejected before deployment: its held-out
weak-label F1 was `0.0208`, building and basin recall were zero, and no labels had completed human review. This report is
rejection evidence, not an accuracy claim.

Collect the planned corpus and create a zero-ground-truth review sprint:

```bash
PYTHONPATH=. python3 backend/scripts/bootstrap_public_vision_collection.py \
  --plan vision/datasets/us-conus-building-seed-v1.json \
  --source-registry vision/datasets/public-source-registry-v1.json \
  --output-root private/vision/collections/us-conus-building-seed-v1
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
