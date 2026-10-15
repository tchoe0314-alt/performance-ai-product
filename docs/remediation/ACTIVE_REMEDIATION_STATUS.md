# Active full-audit remediation

This is an execution ledger, not a replacement for the eight master plans or
the original audit. The full objective remains active. No release gate has
passed. Local commits are not deployed or pushed.

## Committed repair groups

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
