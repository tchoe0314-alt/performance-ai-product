# Active full-audit remediation

This is an execution ledger, not a replacement for the eight master plans or
the original audit. The full objective remains active. No release gate has
passed. Local commits are not deployed or pushed.

## Committed repair groups

Route-length evidence: explicit zero preserved, metre route points converted,
ambiguous/invalid dimensional inputs reject without partial totals.137 scoped
tests pass; build v8 keeps prior calculations historical. See
`QUANTITY_ROUTE_UNITS_2026-10-15.md`. Stage inheritance/summary consistency and
independent qualification remain open. Release approval:0/5 gates (0%).

Drawing-unit takeoffs: metric drawing measures convert before imperial aggregation;
explicit imperial summaries remain unchanged.112 affected tests passed across two
non-overlapping suites. Build v7 retains old results unverified. See
`QUANTITY_DRAWING_UNITS_2026-10-15.md`; stage route-point units, mixed units,
full numerical qualification and independent review remain open.0/5 release gates.

Polygon takeoff follow-up: replaced bounding-box area with validated enclosed
simple-ring area.98 affected tests passed after18 original failures. Build v6
retains older results as unverified; see `QUANTITY_POLYGON_AREA_2026-10-15.md`.
Metric/mixed-unit quantities, broader engine qualification and independent review
remain open. Release approval progress:0/5 gates (0%), not coding completion.

Displayed review evidence now must match the selected candidates in the saved
project associated with its revision. Offline actual-action/builder checks and
TypeScript pass; see `REVIEW_DISPLAYED_EVIDENCE_2026-10-15.md`. Full browser races,
usability and PostgreSQL validation remain open.

Browser review preconditions: public review requests require the loaded project's
revision and reject stale-before-request decisions.93 non-overlapping backend
cases, offline actual-action checks and TypeScript passed. See
`BROWSER_REVIEW_PRECONDITION_2026-10-15.md`; complete UI/source-association and
PostgreSQL acceptance remain open.

Candidate-review generation follow-up: every committed review write now consumes
its source revision, including identical-content writes.97 affected tests passed;
see `CANDIDATE_REVIEW_GENERATION_2026-10-15.md`. Client inbox tokens and PostgreSQL
qualification remain open; this is not full CAN-03 closure.

Latest follow-up: shell saves require a source revision (`da48d1e9`;160 scoped
tests passed). Metadata callbacks now receive a detached commit snapshot;
146 affected tests passed after reproducing a valid geometry mutation. See
`SHELL_SAVE_REVISION_REQUIRED_2026-10-15.md` and
`METADATA_CALLBACK_ISOLATION_2026-10-15.md`. These scoped results do not supersede
historical failures or establish all-writer/PostgreSQL/full-release acceptance.

|Finding family|Implementation/evidence|Still open|
|---|---|---|
|ENG-01/02/03/04/05|`c3f23ed6`: hydrology contracts/validation, exact basin storage, supported-domain routing, shared spatial integration. Analytical oracles and old24 assertions pass|Independent full-method benchmarks, all engine families, professional review; unsupported-domain conversion|
|SEC-01|`f9c7b85d`: public HTTPS validation, pinned IP/TLS host, redirect/DNS/size/time limits.59 tests+19 subtests pass|Independent AppSec/egress deployment review and other outbound clients|
|SEC-02/04/06/07|`53af2cf6`: hashed expiring sessions and operator diagnostics; `18c8791d`: shared bounded sliding-window/source/account-target limits.45 tests+5 subtests pass|PostgreSQL races/throughput, proxy validation, browser storage policy, operator auditing|
|SEC-08/05|`eb4e120b`: immutable uploads/hash/no-replace publication; learning collection requires explicit consent.17 focused tests pass|Complete source-hash lineage; optional learning org/retention/withdrawal qualification; collection remains contained/off|
|CAN-03/SEC-10|`7e7b31f2`: revision-required public saves and guarded internal snapshots|Low-level legacy writers, client result replacement, full PostgreSQL concurrency and all-writer enforcement|
|CAN-03 browser result ownership|Existing-project public saves now preserve server results through locked shell save; 80 tests+11 subtests across two non-overlapping scoped runs. See BROWSER_RESULT_OWNERSHIP_2026-10-15.md|New-project/import trust boundary, legacy job fallback and all-writer enforcement remain open|
|CAN-03 unbound job publication|Real-store legacy job results now archive exact inputs/output rather than fall back to full project save;80 focused tests pass. See UNBOUND_JOB_PUBLICATION_2026-10-15.md|Legacy rerun/migration qualification, alternate-store fallback, remaining low-level writers and PostgreSQL concurrency|
|CAN-03 candidate review|Source revision checked under write lock; stale review computation returns409.68 scoped tests pass. See CANDIDATE_REVIEW_CONCURRENCY_2026-10-15.md|Client-visible inbox revision, PostgreSQL races and remaining writers|
|CAN-04 queue checkpoint ownership|Queue-generated resume checkpoints no longer injected into saved editable request; job keeps full checkpoint.64 scoped tests pass,100 boundary submissions constant-size. See QUEUE_CHECKPOINT_OWNERSHIP_2026-10-15.md|Existing/caller-supplied snapshots, result/history duplication, measured lifecycle/RSS/storage budgets and reference architecture|
|CAN-02/03 checkpoint precedence|Explicit server checkpoint now wins over client aliases, including empty/full cases;84 tests+5 subtests pass. See SERVER_CHECKPOINT_PRECEDENCE_2026-10-15.md|Complete lifecycle snapshot isolation, direct API trust and inherited-stage qualification|
|Combined regression checkpoint|Revision de0a0149:305 tests+65 subtests passed in two non-overlapping isolated selections. See COMBINED_REGRESSION_2026-10-15.md|Not full backend/browser/PG, independent engineering or release acceptance|
|SEC-01 standards outbound clients|Three direct standards fetch paths now use pinned bounded public HTTPS;144 tests+13 subtests pass. See STANDARDS_OUTBOUND_SECURITY_2026-10-15.md|Other outbound clients, deployment egress, independent AppSec/source-rights review|
|SEC-01 worldwide sources|Configurable worldwide JSON endpoints use shared bounded pinned transport;26 tests+13 subtests pass. See WORLDWIDE_OUTBOUND_SECURITY_2026-10-15.md|Binary terrain/imagery, configured AI/operator clients and deployed egress review|
|SEC-01 imagery gateway|Image downloads now pinned/public with per-hop host policy and capped binary budgets;57 tests+13 subtests pass. See IMAGERY_OUTBOUND_SECURITY_2026-10-15.md|Detector POST/provider trust, model/image resource qualification, independent AppSec and deployed egress|
|Detector POST redirects|Roboflow/generic credential-bearing POST redirects disabled; non-2xx rejects before parsing.47 tests pass. See DETECTOR_REDIRECT_SECURITY_2026-10-15.md|Configured endpoint trust, response budgets, data-sharing policy and deployed egress|
|ENG-06 water pressure units|Removed duplicate0.433 conversion in GPM/inch Hazen–Williams pressure loss; four independent EPA-unit cases and41 focused tests pass. Build v4 invalidates v3 history without deleting it. See WATER_PRESSURE_UNITS_2026-10-15.md|Full water/network/domain/standards qualification and independent PE/reference software acceptance|
|ENG-06 water inputs|Finite/domain validation and graph preflight; explicit zero-flow alias preserved.39 focused tests pass. See WATER_INPUT_VALIDATION_2026-10-15.md|Topology/path logic, extreme finite overflow, object identities, standards and PE/reference acceptance|
|ENG-06 water topology|Unsupported looped/multiply supplied/disconnected graphs reject before pressure output; branch-tree order invariance tested.46 focused tests pass. See WATER_GRAPH_TOPOLOGY_2026-10-15.md|General network equilibrium, continuity, signed static pressure, numeric limits and independent qualification|
|ENG-06 water demand dependencies|Repeated25-pass downstream double-counting replaced with validated bottom-up fixture-set accumulation;57 focused tests pass. See WATER_DEMAND_DEPENDENCIES_2026-10-15.md|Sizing residual path pressure, signed static head, demand standards, final build identity and independent qualification|
|ENG-06 sizing pressure paths|Validated supply-path propagation replaces own-segment-only residuals and parallel-branch summation;59 focused tests pass. See WATER_SIZING_PRESSURE_PATHS_2026-10-15.md|Signed static head, fixture-pressure acceptance, standards/real network solver and independent qualification|
|ENG-06 fixture pressure|Per-fixture unrounded endpoint requirement checks; inadequate/unconnected/unmodeled branches cannot qualify.66 focused tests pass. See WATER_FIXTURE_PRESSURE_2026-10-15.md|Actual outlet branch/minor losses, UI/report projection, signed static head and independent qualification|
|ENG-06 static head|Signed elevation pressure changes retained in sizing and graph;70 focused tests pass, including rise/fall conservation. See WATER_STATIC_HEAD_2026-10-15.md|Datum-compatible elevations, outlet losses, final version/invalidation and independent qualification|
|ENG-06 fire flow|Finite/domain/topology preflight and consistent generated pipe identity; unnamed-pipe demand omission repaired.78 focused tests pass. See FIRE_FLOW_VALIDATION_2026-10-15.md|Reference/calibrated benchmark, convergence/production projection, final identity and PE acceptance|
|ENG-06 production integration|Explicit zero pressure preserved; failed graph pressure/margin stay unknown. See WATER_PRODUCTION_EVIDENCE_2026-10-15.md|Two loop-ready production tests fail: general equilibrium solver/demand contract is missing; not waived by focused passes|
|Water repair build v5|357 tests+81 subtests pass across complete remediation, history/export-version and design workflows. Prior v2–v4 cannot activate or be recertified by rebinding. See WATER_REPAIR_BUILD_V5_2026-10-15.md|Two production loop tests still fail; explicit demand/supply model decision requested; full release/PE/PG/browser acceptance open|
|CAN-03 server metadata CAS|Snapshot helper/chat-memory writer now guard metadata-only concurrent changes under write lock;173 tests+10 subtests pass across two non-overlapping selections. See SERVER_METADATA_CAS_2026-10-15.md|All-writer enforcement, public metadata ownership and PostgreSQL/independent concurrency qualification|
|CAN-03 browser metadata|Existing-project public autosaves admit only validated naming flags and preserve newer server metadata;66 focused tests pass. See BROWSER_METADATA_OWNERSHIP_2026-10-15.md|New-project/import trust, metadata namespace roles, all writers and PostgreSQL/browser qualification|
|Public imported result trust|Client-provided current-build stamps become preserved unverified claims for sidecar/inline new-project results;71 focused tests pass including save/reopen and trusted duplication. See PROJECT_IMPORT_TRUST_2026-10-15.md|Transient execution receipts, other import/approval extensions and browser/independent qualification|
|CAN-03 design save ABA|Server-owned generation in full/shell save tokens prevents change-and-restore reviving stale requests; metadata patches preserve it.135 focused tests pass. See DESIGN_SAVE_GENERATION_2026-10-15.md|Other operation generations, mandatory low-level checks, PostgreSQL and browser/legacy qualification|
|CAN-03 full-save revision|Existing-project full store writes now require a source revision;158 tests pass across two non-overlapping selections. See FULL_SAVE_REVISION_REQUIRED_2026-10-15.md|Low-level shell-save requirement, alternate stores, result/metadata ownership and PostgreSQL/browser qualification|
|Terrain tile boundary|Bounded pinned binary fetch plus512px PNG/mode/opacity checks;84 tests+13 subtests pass. See TERRAIN_TILE_BOUNDARY_2026-10-15.md|Terrain vertical-unit/datum contract, total tile budgets, other imagery and deployed provider validation|
|Terrain missing data|Any unavailable tile now prevents partial terrain from reaching the grading mean-fill path;13 tests+13 subtests pass. See TERRAIN_MISSING_DATA_2026-10-15.md|User-facing diagnostics/fallback gates, units/datum and independent control verification|
|Terrain resource/fallback follow-up|Grid admission bounds, explicit unavailable-source provenance and immediate stop on failed tile. Latest23 focused tests pass; see TERRAIN_GRID_BUDGET, TERRAIN_FALLBACK_PROVENANCE and TERRAIN_FAILURE_SHORT_CIRCUIT documents|Overall deadline/distinct tile budget, browser visibility, units/datum, fallback release gates|
|Terrain units/build identity|Provider metres converted to grading feet; source/datum explicitly unverified. Request deadline/tile caps added. Build v3 makes prior v2 results unverified without rewriting history;70 version/persistence tests pass. See TERRAIN_VERTICAL_UNITS, TERRAIN_REQUEST_BUDGET and TERRAIN_RESULT_VERSION|Datum/control alignment, full fresh candidate qualification, per-engine version granularity and browser/export verification|
|Result identity/staleness|`44e0ac0e`: old-method results archive, current execution stamps, legacy checkpoint cannot recertify inherited results|Full recalculation/dependency/engine-version qualification|
|Raster/units/CAN-01.C1|`e3482dc4`: cell extent/orientation/registration, NoData rejection, non-foot output protection, strict adapter version.54 tests pass|Full units/CRS/datum/reprojection/TIN/clip qualification and compatibility migration review|
|SEC-03 enrollment/recovery|`64e1fdf6` proof boundary plus current enrollment/recovery integration:51 tests+5 subtests; real Chromium identity flow and three-viewport responsive checks pass. See ENROLLMENT_RECOVERY_REPAIR_2026-10-15.md|Qualified delivery, legacy grants review, full atomic enrollment and PostgreSQL/AppSec verification|
|Drawing/export regression|`3f0cf44e`: reconstruct authorized drawing rather than passing calculation gate; stale/tampered snapshots reject.48 targeted+64 integration checks pass in overlapping suites|Full browser/export compatibility and final candidate regression|
|Evidence|`7ae22a26`:90 focused checks, preserved with candidate fingerprint and manifest|Not independent acceptance; cannot certify later commits|

## Remaining sequence (not optional scope reductions)

1. Qualify the latest frozen candidate through backend and browser suites;
   safely scoped local-server verification now passes5 tests. Preserve failures and
   distinguish environment limitations from product failures.
2. Qualify invitation/enrollment/recovery beyond the completed fake-sender local
   flow; do not expose an outbox/code endpoint or purchase delivery.
3. Complete mandatory all-writer concurrency, qualify shared abuse limits on
   PostgreSQL and review proxy/session/browser controls.
4. Resolve checkpoint/model payload growth and prove bounded save/load/history,
   job recovery, source consistency and dependent calculation propagation.
5. Validate every advertised engine and import/export workflow against
   independent oracles, units/control datasets and supported scenario limits.
6. Exercise supported-browser accessibility/usability, performance/load,
   artifact/database restore, deployment identity and rollback in approved
   isolated environments. Deployment still requires separate permission.
7. Finish commercial catalog/entitlements/sandbox billing, support/account
   lifecycle and source/IP/privacy/legal documentation. No real payments.
8. Obtain the independent engineering/security/legal/customer evidence required
   by the original gates. Civora never signs or seals customer work, but software
   correctness and clear scope still require evidence.

## Current working constraints

The broad intermediate run recorded2,312 passed/56 failed assertions; detailed
classification and subsequent targeted evidence are in
`BACKEND_REGRESSION_TRIAGE_2026-10-15.md`. It is not a current full-suite pass.
Latest invitation changes were tested separately. Do not sum overlapping tests
or silently declare original findings closed from a single green check.

The pre-existing sidebar color change passed responsive scoped contrast checks.
No unfinished source was discarded to clean Git status.
Original plans and historical evidence are preserved. Disk cleanup removed
only generated/duplicate files in the disposable test directory, never original
workspace/customer data. No paid/external API or production access was used.
