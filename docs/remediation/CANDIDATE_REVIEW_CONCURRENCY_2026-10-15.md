# Candidate review write concurrency

Parent revision: `8d5aa140`. Finding: CAN-03/SEC-10, stale review publication.

The review workflow computes an updated candidate inbox, decisions and source
confidence from a project snapshot. Its fast-path updater previously locked the
current row but merged the old computed candidate state without comparing the
source revision. Locking alone does not protect a preceding read/compute phase.

The updater now requires the source revision, checks it against the locked row,
and only then merges/seals candidate state. The application passes its snapshot
revision and maps a mismatch to HTTP409 with reopen/retry guidance. No retry
silently replays an old decision against different inputs. Shell/result ownership,
roles, canonical fields and normal review behavior remain intact. No migrations
or existing records were changed.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/review-40.xml` reports68 passing
tests across new race regressions, existing review/store fast paths, application
project workflows and revision tests. `review-39.xml` is retained as the earlier
67-test run; these runs overlap and must not be summed.

New oracles: a second write from one snapshot conflicts; changing sources during
review yields409 and preserves the newer record exactly; simultaneous SQLite
review writes from one snapshot have exactly one winner. Normal candidate review
and generated-result preservation remain covered by existing fast-path tests.
All databases/data were disposable/synthetic with network guards enabled.

Limitations: this verifies the server read/compute/write window, not an old
browser's already-stale inbox before its request. Client-visible review revision
binding remains open, as do PostgreSQL execution, all low-level writers and full
release qualification. No professional/security acceptance is claimed.

Rollback: revert this isolated commit; no schema rollback needed. Reverting
reopens lost-review risk, so retain an equivalent conflict check before exposing
concurrent review. Never delete recorded decisions to reconcile conflicts.
