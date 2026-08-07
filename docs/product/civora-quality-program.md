# Civora Quality Program

## Purpose

This program turns the Civora North Star into measurable product work. It does
not define "perfect" as having every possible civil or drafting feature. It
defines it as:

- no known P0 or P1 defect in a supported workflow;
- one canonical project model across the canvas, map, 3D, persistence,
  engineering requests, review packages, and exports;
- predictable interaction with visible recovery paths;
- honest source and professional-review boundaries;
- repeatable success on the deployed product, not only in mocked tests.

## Non-Negotiable Product Rules

1. One capability has one primary UI home.
2. One stage has one primary action.
3. 2D, map, 3D, saved state, engineering requests, and exports use the same
   canonical object identity and geometry.
4. A visual fallback is labeled and never substituted for sourced geometry.
5. Missing evidence is explained without flooding the default workspace.
6. Chat and visible controls call the same action contracts.
7. Every meaningful edit is recorded, reversible where supported, and marks
   affected outputs stale.
8. A passing unit test is not hosted proof. A visible hosted result is not
   engineering correctness proof. Both are required for release-critical paths.

## Severity

- **P0:** loss, corruption, security exposure, false professional claim, or a
  core workflow that cannot complete.
- **P1:** a supported primary workflow is confusing, inconsistent, inaccurate,
  or unreliable enough to break user trust.
- **P2:** important depth, polish, performance, or coverage improvement that has
  a clear workaround and does not invalidate current output.

## Phase 0: Reproducible Baseline

### Work

- Use a clean worktree from current `origin/main`.
- Install frontend dependencies with `npm ci`.
- Run the complete backend suite.
- Run lint, exact TypeScript, production build, and release regression.
- Record dependency, build, test, and file-size baselines.
- Maintain a fast per-change gate and a full release gate.

### Exit Criteria

- Fresh install succeeds without manual dependency borrowing.
- Backend suite has no failures.
- Lint, TypeScript, and production build pass.
- No generated build artifacts dirty tracked source.

## Phase 1: Canonical Geometry And Visual Truth

### Work

- Establish an object-by-object parity contract for 2D, map, 3D, persistence,
  Generate input, review package, and export.
- Remove duplicate overlays and mismatched fallback bounds.
- Preserve exact polygons, polylines, points, rotation, height, and source.
- Keep site scale and object alignment stable through pan, zoom, resize, and
  2D/3D switching.
- Give detected-existing and proposed-design geometry independent layer controls.

### Exit Criteria

- Every supported object keeps the same ID and geometry signature in all
  applicable surfaces.
- Switching modes 25 times changes no canonical geometry.
- Reload and export preserve the same object count and geometry signature.
- No unexplained duplicate outline is visible in reference screenshots.

## Phase 2: Professional 2D And 3D Preview

### Work

- Make buildings, parking, roads, sidewalks, utilities, structures, basins,
  grading, and terrain visually legible in 3D.
- Use actual object footprints instead of generic rectangles when geometry exists.
- Support building height, floors, finished-floor elevation, and roof form.
- Improve civil lineweights, symbols, contours, labels, hatching, materials,
  camera framing, and selection highlighting.
- Keep AI Visualization separate from measurable geometry and source evidence.

### Exit Criteria

- A mixed civil program visibly contains every supported semantic layer in 2D
  and 3D.
- 3D WebGL pixel and object-layer checks prove a nonblank perspective scene.
- Standard, High Quality, and AI Visualization do not mutate project geometry.
- Desktop and tablet screenshots pass visual review at multiple aspect ratios.

## Phase 3: Interaction And Drafting Reliability

### Work

- Guarantee cursor-to-world mapping over empty canvas, imagery, dense overlays,
  labels, and generated systems.
- Make Select, Finish, Cancel, Escape, and right-click completion predictable.
- Complete selection, window/crossing selection, snaps, coordinate input, ortho,
  polar guidance, and active-tool feedback.
- Complete move, copy, paste, duplicate, rotate, scale, mirror, array, join,
  close, split, trim, extend, offset, fillet, chamfer, hatch, and supported
  explode behavior.
- Cover each reversible operation with undo and redo.

### Exit Criteria

- Every visible drafting action has a passing positive, misuse, cancel, and undo
  path.
- No visible control is intercepted by a canvas or map layer.
- A dense drawing can be edited for 30 minutes without cursor drift or tool-state
  ambiguity.

## Phase 4: Semantic Objects And Reactive Model

### Work

- Validate and combine geometry into areas, paths, and point sets.
- Convert geometry into canonical civil objects with source and history.
- Report gaps, overlaps, duplicate segments, self-intersections, disconnected
  sets, and unsupported topology in plain language.
- Build object relationships and dependency impact summaries.
- Mark only affected systems stale and rerun only supported affected systems.

### Exit Criteria

- Building, parking, basin, roadway, sidewalk, storm, water, and sanitary proof
  objects survive create, edit, conversion, reload, Generate, export, and undo.
- Moving a proof object produces the expected dependency and stale-state changes
  without changing unrelated systems.

## Phase 5: Address, Detection, And Source Truth

### Work

- Route locations to the strongest available local and worldwide providers.
- Combine provider data, imagery detection, terrain, and accepted uploads.
- Deduplicate, clip, and rank candidates against the active site.
- Support Accept, Reject, Edit, Merge, Reclassify, Hide, and Add to Project.
- Preserve source, confidence, rights, timestamp, geometry, and review state.
- Improve DEM, LiDAR, contours, survey points, control, datum, and coordinate
  system handling without equating public data to accepted survey evidence.

### Exit Criteria

- Representative urban, suburban, rural, and provider-sparse addresses return a
  truthful Found/Missing summary.
- Candidate decisions persist and do not silently affect engineering evidence.
- Provider failure, no-feature, unsupported, and offline states are distinct.

## Phase 6: Flexible Chat And Command Actions

### Work

- Parse long instructions, misspellings, incomplete grammar, follow-up references,
  selections, dimensions, counts, placement, systems, and review questions.
- Ask only for information truly absent from the request and project.
- Use structured, validated action contracts shared with the UI.
- Preview and confirm meaningful multi-step edits and preserve undo history.
- Explain changes, stale outputs, sources, assumptions, and next actions.

### Exit Criteria

- A corpus of realistic and adversarial user requests reaches the same project
  state as equivalent visible-control actions.
- Repeated commands are idempotent unless the user explicitly asks for another
  object.
- Safety refusals do not block ordinary review, drafting, or analysis work.

## Phase 7: Engineering And Deliverable Depth

### Work

- Prove terrain, grading, drainage, storm, sanitary, water/fire-flow, roadway,
  utility coordination, earthwork, quantities, and cost behavior with complete
  and incomplete evidence.
- Link every result to canonical object IDs, inputs, assumptions, standards, and
  source confidence.
- Build professional plan, profile, section, quantity, QA, standards, source,
  assumption, and change-summary deliverables.
- Verify DXF, LandXML, PDF, CSV, and project archive handoffs.

### Exit Criteria

- Complete deterministic fixtures produce reproducible review evidence.
- Incomplete fixtures remain explicit and never fabricate success.
- Stale geometry cannot enter a current review package or export unnoticed.
- External roundtrip checks document preserved, lost, and unsupported content.

## Phase 8: Persistence, Performance, Security, And Operations

### Work

- Prove clean New Project, autosave, refresh, reopen, switching, duplicate,
  archive, delete, restore, and cross-device continuation.
- Continue splitting state domains where broad rerenders remain measurable.
- Establish load, panel, canvas FPS, drag, hover, 3D, Generate, long-session, and
  memory-growth budgets.
- Harden authorization, isolation, uploads, backups, audit logs, rate limits,
  debug protection, deletion, and recovery.

### Exit Criteria

- A user completes the primary workflow twice without intervention or stale data.
- Long-session memory and interaction latency stay within documented budgets.
- Authenticated and unauthenticated hosted checks match the intended access model.
- Recovery exercises demonstrate that project data can be restored.

## Phase 9: Final Human And Adversarial Proof

### Required Scenarios

- Multiple addresses, regions, site sizes, and irregular boundaries.
- Blank, imported, detected, drawn, command-created, and mixed projects.
- Normal use, rapid use, incorrect use, interruption, retries, offline/provider
  failure, expired auth, and concurrent jobs.
- Desktop and supported tablet/mobile layouts.
- Two consecutive full workflows from New Project to saved review package.

### Evidence

- Exact commands and results.
- Browser telemetry and failed-request classification.
- Performance timings and memory measurements.
- Screenshots for every workflow stage and 2D/3D/quality mode.
- Videos for representative end-to-end workflows.
- Proven versus assumed table.
- P0/P1/P2 list and readiness scores.

## Release Rule

A phase may land when its focused tests pass and no known regression remains. The
program is complete only when the final hosted gauntlet has no P0/P1 issue and
all remaining P2 limitations are documented truthfully. "Perfect" never means
hiding limitations; it means the product behaves predictably and tells the truth
about what it knows.
