# Coordinate learning-log appends with redaction and rollback

Parent `b4de469f`; SEC-05 / CAN-03 data-lifecycle follow-up. Collection remains off.

## Reproduction

Deletion read a learning file and replaced it atomically. A different user's
append between the read and replacement was discarded. Locking the log inode
does not protect a replacement file with a different inode. Restoring an older
backup after database failure had the same unrelated-data-loss risk.

A deterministic synthetic deletion pauses immediately before replace, starts an
append, then completes deletion or forces database failure. The original code
erased the other user's record. The regression requires that record to survive
both commit and rollback and requires the deleted user's original record restored
only on rollback. No production/account data was accessed.

## Repair

A private regular no-follow sidecar holds the stable advisory lock identity.
Append and export reads share it; public account deletion acquires all learning
path locks in sorted order and retains them through redaction, database commit,
any restoration and cleanup. Sidecars must never be unlinked during normal use.
Deletion confirmation is checked before creating/acquiring locks. Existing owner,
consent, regular-file and0600 protections remain. No activation/environment/schema
change. Private redaction helpers are called under this public orchestration;
direct maintenance uses must follow that same lock contract.

## Evidence

Guarded disposable source/SQLite/files under `/tmp/civora-repair-verification.NBAOtD`.
No external services, paid calls, deployment or customer data.

- `results/learning-race-142.xml`:1 failed; record list was empty after the race,
  causing the initial expected-record lookup to fail. Regression now first asserts
  the retained-record count explicitly; expected retention was not weakened.
- `results/learning-race-143.xml`:31 passed,1.01s, initial affected selection.
- `results/learning-race-144.xml`:56 passed/40 subtests,1.54s, commit/rollback race.
- `results/learning-race-145.xml`: **56 passed / 40 subtests**,1.48s, final source.
  Includes log safety/concurrency, consent/default-off, core repairs and account
  export/deletion/backup/restoration. Selections overlap; do not add pass counts.
- `git diff --check`:PASS. Not full release or multi-host acceptance.

## Remaining issues and recovery

This prevents unrelated appends from being lost to replace/rollback. It does NOT
revalidate a stale consent snapshot or prove that a deleted user's in-flight
event cannot be appended later. A server-side live consent/account boundary is
still required before optional collection is enabled. Organization policy,
retention/minimization, hard-link/same-user filesystem attacks, bounded lock waits,
cross-process/multi-host filesystem deployment and privacy review remain open.

No historical log migration/cleanup performed. POSIX lock semantics remain the
existing supported implementation target; unsupported primitives fail closed.
Rollback requires reviewed code revert, no schema migration. Do not delete stable
lock sidecars while any writer/export/deletion may be active. Reverting reopens
unrelated-user data loss. Preserve all original failed evidence.

Progress:0/5 release gates approved (0%), not coding completion.
