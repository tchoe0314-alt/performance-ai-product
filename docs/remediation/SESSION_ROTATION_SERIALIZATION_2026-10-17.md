# Rotation validation after storage waits

Base: `d567b16bda89233209607a25f28e7f29598f70b2`.
Follow-up to SEC-04 and `SESSION_CONCURRENCY_2026-10-17.md`.

## Reproduction and repair

Rotation also validated against a timestamp captured before database work. Two
deterministic interleavings demonstrate:

1. Another request touches the session while rotation waits: valid rotation was
   rejected because its previously captured timestamp was older than activity.
2. The idle deadline passes while rotation waits: rotation incorrectly succeeded
   against the old timestamp. A session expired at execution must not rotate.

Before repair: **2 failed / 9 passed** in `rotation-before.xml`. No oracle changed.

Rotation now obtains a SQLite write lock (`BEGIN IMMEDIATE`) or PostgreSQL row
lock (`SELECT ... FOR UPDATE`), reads the session, then captures the validation
time. Validation and replacement remain in that transaction. The conditional
single-winner update remains as defense in depth. Absolute lifetime is not reset;
hashing, expiry boundaries and invalid-token failure remain unchanged. The same
database-specific locking pattern already exists in identity proof operations.

## Executed verification

**35 passed**, 1.93s, one existing Starlette/httpx deprecation warning:
session security, auth store, application auth/health/session workflows, identity
proofs, session API and identity API. Includes original single-winner rotation,
absolute/idle expiry, future-token, revoke-all and both new interleavings.
Reports are retained under `session-concurrency-2026-10-17/`; final newlines are
normalized by the patch writer, and original pytest traceback whitespace is
preserved. Source/test whitespace check passes.

Executed on copied source in `/tmp/civora-session-verification.pW76oM`, disposable
SQLite only. OS sandbox denied all networking and writes outside that root;
Python guard denied subprocesses and external .env/database reads. No installs,
production/customer access, paid calls, deployment or migration.

## Limits / rollback

PostgreSQL SQL path inspected, not executed; real PostgreSQL races, latency and
multi-host clock behavior require separate qualification. SQLite now serializes
rotation with writes; contention/timeout behavior under representative load is
not certified. Already authorized in-flight requests are not retroactively revoked.
Browser evidence is a separate workstream, not implied by these tests.

Rollback only this repair/test group with a new commit; no schema recovery is
needed. Reverting reintroduces both defects. Preserve reports and prior browser
test work. Original reconstructed audit checks last verified24/24 (100%), not
rerun here. Release gates remain0/5 (0%). Overall remediation remains active.
