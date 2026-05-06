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

## Active Phase

Active phase: **Phase 1 only**

Current implementation priority inside Phase 1:

1. Canonical truth consistency
2. Dependency-aware reruns and rollback safety
3. Cluster-aware conflict solving
4. Storm / sanitary post-reroute truth
5. Assisted-off failure truth
6. QA / quantities / export consistency
