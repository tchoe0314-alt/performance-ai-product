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
