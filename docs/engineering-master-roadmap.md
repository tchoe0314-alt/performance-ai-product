# Engineering Implementation Plan

## Intent

This plan replaces feature sprawl with a strict phased build order.

Rules:

- Work only one phase at a time.
- Do not prioritize frontend polish, scaling, or UX expansion before backend engineering truth is reliable.
- Prefer the minimum set of changes that most improves engineering trustworthiness.
- `ProjectModel` and `ProjectManager` remain the source of truth.
- Actions, DXF packaging, preview, QA, and quantities must all reflect canonical state.

## Phase 1: Core Engineering Truth Engine

### Goal

Make the backend trustworthy enough that Assisted-off operation means real engineering validation instead of best-effort output.

### Deliverables

- Canonical state hardening
  - Stable canonical state in `ProjectModel` / `ProjectManager`
  - Canonical planner metadata carried through final plan output
  - Canonical state used as primary source for QA, quantities, and exports
- Dependency-aware reruns
  - Stages declare dependencies
  - Dirty/clean state tracked per system
  - Only affected downstream stages rerun after changes
- Safe rollback
  - Candidate solves operate on copied/snapshotted canonical state
  - Only the best accepted state is committed
  - Failed candidates cannot partially corrupt the main state
- Explicit failure reasoning
  - Assisted-off failures identify exact system, rule, location, and why resolution failed
- Multi-candidate conflict-cluster solver
  - Solve related conflicts as clusters, not only as isolated signatures
  - Evaluate multiple candidate orders/strategies per cluster
  - Keep best valid cluster solution and report best near-valid candidate when none pass
- Conflict-cost scoring
  - Candidate scoring includes unresolved conflicts, constructability cost, and downstream validation penalties
- Storm hydraulics completion
  - Aggregate flow/capacity metrics
  - Controlling segment
  - Max utilization ratio
  - Missing-data tracking
  - Post-reroute pipe resizing/checking
- Sanitary completion
  - Canonical sanitary segments and manholes
  - Slope/connectivity/service checks
  - Post-reroute sanitary sizing/checking
- Assisted-off hard gates
  - Assisted-off validation asks for missing information on unresolved conflicts, incomplete hydraulics, incomplete sanitary, inconsistent quantities, and missing requested deliverables
- Quantities / QA / export consistency
  - Quantities read canonical state first
  - QA reads canonical state first
  - Export reflects final resolved state, not stale geometry
- Graph-based validation
  - Storm and sanitary graph validation after accepted fixes
- Local grading repair triggers
  - Local grading updates only where reroutes or depth changes require them
- Post-reroute resizing/checking
  - Storm resizing
  - Sanitary recheck
  - Utility continuity recheck

### Dependencies

- Existing planner stage framework
- Existing ProjectManager dependency/rerun support
- Existing canonical summaries for grading, drainage, storm, sanitary, utilities

### Acceptance Criteria

- Assisted-off validation returns structured missing-information reasoning when engineering truth is incomplete.
- Accepted conflict-resolution candidates are snapshot-isolated and rollback-safe.
- Conflict resolution reports cluster-level chosen candidate and best near-valid fallback.
- Storm summary always exposes aggregate hydraulic metrics when storm geometry exists.
- Sanitary summary exposes completeness checks and stays consistent after reroutes.
- Quantities, QA, and DXF/export metadata match final canonical resolved state.
- Only dirty downstream systems rerun after accepted fixes.

### Regression Tests

- Dependency-aware rerun tests
- Assisted-off missing-information reasoning tests
- Conflict resolution engine tests
- Cluster grouping / cluster solver tests
- Coordination-to-quantities consistency tests
- Planner smoke test

### Exit Gate Before Phase 2

Do not start Phase 2 until all of these are true:

- Assisted-off validation has zero hidden fallback behavior for critical engineering systems.
- Conflict solving is cluster-aware, rollback-safe, and reports explicit failure reasons.
- Storm hydraulics and sanitary completeness are available in canonical summaries.
- QA, quantities, and export all reflect the chosen solved state.
- Focused Phase 1 regression suite is green.

## Phase 2: Deeper Coordination Realism

### Goal

Make the engineering coordination engine more realistic before spending effort on sheet polish or product growth.

### Deliverables

- Soft corridor preferences
- Crossing-rule tables by utility pairing
- Protected-zone logic
- Constructability scoring as a first-class metric
- Alignment ownership rules
- Structure insertion refinement
- Trench conflict grouping
- Better grading realism around roads, pads, and ADA paths
- Stronger canonical profile/cross-section linkage

### Dependencies

- Phase 1 exit gate complete
- Stable canonical solver output
- Reliable post-reroute validations

### Acceptance Criteria

- Major systems start in preferred corridors before cleanup.
- Solver avoids protected zones unless no valid alternative exists.
- Constructability score materially influences candidate selection.
- Profile/cross-section metadata is tied to canonical alignments and systems.

### Regression Tests

- Corridor-preference route tests
- Protected-zone avoidance tests
- Structure insertion refinement tests
- Post-reroute grading adjustment tests
- Profile/cross-section canonical linkage tests

### Exit Gate Before Phase 3

- Route bias and protected-zone penalties are stable.
- Constructability and ownership rules affect chosen candidates predictably.
- Canonical alignments drive profile/section content consistently.

## Phase 3: Deliverable / Output Realism

### Goal

Make outputs look and behave like real engineering deliverables without changing the engineering truth model underneath them.

### Deliverables

- Richer profile bands
- Better section realism
- Cleaner sheet intelligence
- Stronger CAD standards / blocks / styles
- Legends, title blocks, and sheet ordering
- Export audit and reporting polish

### Dependencies

- Phase 2 exit gate complete
- Stable canonical profile/section linkage
- Stable solved-state export metadata

### Acceptance Criteria

- Profiles and sections draw from canonical state only.
- DXF sheets, labels, and bands stay consistent with final solved geometry.
- Export audit catches canonical/export mismatches.

### Regression Tests

- DXF sheet layout tests
- Export packaging richness tests
- Profile/section sheet-content assertions
- Export audit tests

### Exit Gate Before Phase 4

- Deliverables are faithful to canonical state.
- Export/reporting mismatch checks are in place.
- Sheet output is consistent enough that UI can trust it.

## Phase 4: Product / UI / Ops Expansion

### Goal

Build product, workflow, and operational capability only after the backend engineering core is reliable.

### Deliverables

- Dashboard and run history
- Conflict review UI
- Deliverable manager
- Assumption approval UI
- Saved runs / versioning UX
- Auth, data, and ops scaling
- Background workers
- Postgres / storage improvements

### Dependencies

- Phase 3 exit gate complete
- Stable backend summaries and export artifacts
- Stable manual-mode validation behavior

### Acceptance Criteria

- Users can inspect runs, compare revisions, review conflicts, and manage deliverables.
- Operational backend can persist, queue, and retrieve runs reliably for multiple users.

### Regression Tests

- API persistence tests
- Job queue tests
- Project history/versioning tests
- UI integration tests for run review and deliverable management

## Phase Status

Current truth standard, 2026-06-05:

- The historical phase exit gates below describe regression milestones that were reached during backend hardening.
- They do **not** mean Civora is public-beta ready or construction-ready.
- The active backend target is now full-system private alpha in review-only mode.
- The authoritative current blocker inventory is `docs/private-alpha-backend-blockers.md`.
- Construction release must remain blocked in private alpha even when review package generation is allowed.

Phase 1 status: **Complete / exit gate verified**

Verification run:

- Date: 2026-06-04
- Focused Phase 1 regression: `76 passed`
- Full backend regression: `839 passed`
- Remaining Phase 1 note: warnings are third-party/deprecation warnings and do not block the Phase 1 exit gate.

Phase 2 status: **Complete / exit gate verified**

Phase 2 progress:

- 2026-06-04: Expanded utility crossing-rule coverage so telecom conflicts with sanitary, storm, gas, and electric are explicitly detected and assigned hierarchy preferences.
- Verification: focused Phase 2/coordination regression `38 passed`; full backend regression `840 passed`.
- 2026-06-04: Added Phase 2 exit-gate regression coverage for utility-pair crossing tables, GIS/road corridor slots, hard protected-zone risk, constructability ownership scoring, structure insertion needs, trench grouping, and profile/cross-section canonical coordination context.
- Verification: focused Phase 2 exit-gate regression `19 passed`.

Phase 3 status: **Complete / exit gate verified**

Phase 3 progress:

- 2026-06-04: Added Phase 3 exit-gate regression coverage for profile pipe data bands, section feature runs, site/profile/section sheet ordering, title-block metadata, CAD styles/blocks, legend alignment, canonical sheet alignment, and export traceability.
- 2026-06-04: Fixed the DXF legend builder so legacy-layer exports such as `PIPE`, `SAN`, `WATER`, `UTILITY`, `EG_CONTOUR`, and `FG_CONTOUR` produce matching legend entries, not only standard `C-*` layers.
- Verification: focused Phase 3/export regression `52 passed`.

Active phase: **Phase 4 complete**

Phase 4 status: **Complete / exit gate verified**

Phase 4 progress:

- 2026-06-04: Added the reactive run policy contract so product surfaces can distinguish live visual updates, debounced cheap validation, quick auto-reruns, and heavy engineering changes that require explicit user confirmation.
- 2026-06-04: Wired the web request metadata to declare the preferred edit behavior: live visual movement, debounced validation, quick-only automatic engineering reruns, confirmed heavy reruns, and stale-export blocking.
- Verification: focused Phase 4/reactive policy regression `4 passed`; reactive contract regression `13 passed`; full backend regression `855 passed`; web lint completed with existing warnings and no errors.
- 2026-06-04: Added persisted workflow review dashboard metadata that groups run history, latest artifact state, phase checkpoints, deliverable manager status, assumption review, conflict review, and release blockers into one UI-ready contract.
- 2026-06-04: Wired the web dashboard panel to read the persisted workflow review dashboard so saved projects surface run/artifact counts, release state, deliverable readiness, assumption review state, and unresolved conflict counts.
- Verification: focused Phase 4/application workflow regression `108 passed`; full backend regression `856 passed`; web lint completed with existing warnings and no errors.

Phase 4 exit gate:

- Dashboard and run history are backed by persisted workflow metadata and surfaced in the UI.
- Conflict review, deliverable manager, and assumption review state are available from the persisted workflow review dashboard.
- Saved runs, artifacts, release blockers, and phase checkpoints are retained with bounded history.
- Auth-scoped project storage, job queue workflows, artifact workflows, and project retrieval paths are covered by application regression tests.

Post-Phase 4 follow-up:

- 2026-06-04: Added true isolated downstream partial rerun execution from checkpointed canonical state. Reactive edits now mark impacted stages dirty, restore the last final-plan checkpoint, rerun only dirty downstream stages through the planner runtime-resume path, and route checkpointed orchestrator requests away from full `build_plan`.
- Verification: focused reactive/orchestrator regression `31 passed`; full backend regression `861 passed`.
- 2026-06-04: Wired product/API reactive rerun requests to send checkpointed final-plan state and changed downstream targets. Unsaved browser workspaces attach the current backend result; saved direct and queued requests recover the latest stored project result before orchestration.
- Verification: focused application/reactive routing regression `126 passed`; full backend regression `864 passed`; web lint completed with existing warnings and no errors.
- 2026-06-04: Completed the remaining reactive product loop: object-aware edit-to-stage dirty mapping, debounced cheap validation without automatic engineering reruns, confirmation for broad downstream reruns, UI stage/telemetry display, partial rerun timing/skipped-stage telemetry, and a browser proof that focused generate requests carry checkpoint metadata.
- Verification: focused reactive/application regression `82 passed`; full backend regression `864 passed`; web lint completed with existing warnings and no errors; Playwright reactive rerun proof `1 passed`.
