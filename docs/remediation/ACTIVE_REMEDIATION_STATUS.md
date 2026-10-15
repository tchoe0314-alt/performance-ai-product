# Active full-audit remediation

This is an execution ledger, not a replacement for the eight master plans or
the original audit. The full objective remains active. No release gate has
passed. Local commits are not deployed or pushed.

## Committed repair groups

|Finding family|Implementation/evidence|Still open|
|---|---|---|
|ENG-01/02/03/04/05|`c3f23ed6`: hydrology contracts/validation, exact basin storage, supported-domain routing, shared spatial integration. Analytical oracles and old24 assertions pass|Independent full-method benchmarks, all engine families, professional review; unsupported-domain conversion|
|SEC-01|`f9c7b85d`: public HTTPS validation, pinned IP/TLS host, redirect/DNS/size/time limits.59 tests+19 subtests pass|Independent AppSec/egress deployment review and other outbound clients|
|SEC-02/04/06/07|`53af2cf6`: stable source key, bounded local counters, expiring hashed sessions, rotation/revocation, operator-only diagnostics|Shared/account-target limits, proxy validation, browser storage policy, operator auditing|
|SEC-08/05|`eb4e120b`: immutable uploads/hash/no-replace publication; learning collection requires explicit consent.17 focused tests pass|Complete source-hash lineage; optional learning org/retention/withdrawal qualification; collection remains contained/off|
|CAN-03/SEC-10|`7e7b31f2`: revision-required public saves and guarded internal snapshots|Low-level legacy writers, client result replacement, full PostgreSQL concurrency and all-writer enforcement|
|Result identity/staleness|`44e0ac0e`: old-method results archive, current execution stamps, legacy checkpoint cannot recertify inherited results|Full recalculation/dependency/engine-version qualification|
|Raster/units/CAN-01.C1|`e3482dc4`: cell extent/orientation/registration, NoData rejection, non-foot output protection, strict adapter version.54 tests pass|Full units/CRS/datum/reprojection/TIN/clip qualification and compatibility migration review|
|SEC-03 backend boundary|`64e1fdf6`: single-use address/invite proof, owner-only resend/revoke, fake sender, no automatic matching-email grants.50 tests pass|Frontend confirmation flow, invitation-based enrollment, recovery, qualified delivery, legacy grants review and PostgreSQL/AppSec verification|
|Drawing/export regression|`3f0cf44e`: reconstruct authorized drawing rather than passing calculation gate; stale/tampered snapshots reject.48 targeted+64 integration checks pass in overlapping suites|Full browser/export compatibility and final candidate regression|
|Evidence|`7ae22a26`:90 focused checks, preserved with candidate fingerprint and manifest|Not independent acceptance; cannot certify later commits|

## Remaining sequence (not optional scope reductions)

1. Qualify the latest frozen candidate through backend and browser suites;
   safely scoped local-server verification now passes5 tests. Preserve failures and
   distinguish environment limitations from product failures.
2. Complete invitation/enrollment/recovery UI/API integration using the approved
   fake sender only; do not expose an outbox/code endpoint or purchase delivery.
3. Complete mandatory all-writer concurrency, shared/account-target abuse
   limits and reviewed proxy/session/browser controls.
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

One pre-existing sidebar color change remains uncommitted pending actual
browser verification. No unfinished source was discarded to clean Git status.
Original plans and historical evidence are preserved. Disk cleanup removed
only generated/duplicate files in the disposable test directory, never original
workspace/customer data. No paid/external API or production access was used.
