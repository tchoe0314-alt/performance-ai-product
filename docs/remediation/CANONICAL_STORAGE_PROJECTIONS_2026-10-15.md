# Lossless active-project storage projections

Parent `6db05b91`; CAN-01/CAN-04 follow-up. No release gate passed.

## Evidence and repair

Active project JSON stored canonical state plus duplicated legacy geometry/meta
projections, including edit history. Existing view adapters already reconstruct
those projections. `storage_project_input` now removes shadows only for adopted
records whose canonical document reconstructs exactly the same projection AND
every raw top-level field. Unknown/unmodeled raw data is retained even when the
current renderer ignores it. Legacy/non-equivalent records remain unchanged.

Active input writers use that storage boundary. Shell saves read their existing
input through the hydrated record instead of merging against stripped storage.
Account exports hydrate project rows too. API/view geometry, custom fields,
revision tokens, result sidecars, immutable history and canonical formatv1 remain.
No history truncation, numerical change, schema migration or bulk database rewrite.
Only subsequent authorized saves qualify for compaction; no real project touched.

## Isolated verification

Disposable tracked-source/SQLite under `/tmp/civora-repair-verification.NBAOtD`,
guarded against outside writes/network/subprocesses; no production/customer data,
paid service or deployment.

- `results/storage-150.xml`:1 failed on duplicated stored shadow keys; earlier
  roundtrip assertions passed. Original evidence preserved.
- `storage-151.xml`:91 passed; initial affected selection.
- `storage-152.xml`:92 passed; legacy and measured size cases added.
- `storage-153.xml`:96 passed; workflow/history/import/lifecycle selection.
- `storage-154.xml`: **188 passed**,22 dependency deprecation warnings,9.56s,
  final combined source including raw-unknown-field preservation. Earlier
  selections overlap; do not sum their totals.
- Fixture:20 objects,3 sequential edits, exact lossless reopen/resolve/token and
 3 retained transactions. Stored33,982bytes vs hydrated42,680bytes: **20.38% smaller**.
  The test requires at least20% reduction for this fixture, not all projects.
- `git diff --check`:PASS. Not full browser/PostgreSQL/current-release acceptance.

Coverage includes full/shell/candidate/metadata/calculation writes, stale revision
checks, canonical gateway, activation/history, atomic exports, duplication,
sharing/memory/history, imports, jobs and account export/deletion/backup tests.

## Limits / recovery

Inline execution checkpoints, duplicated branch-recovery storage, before/after
history growth, measured large-project CPU/RSS/latency and archival architecture
remain open. Losslessness checking itself adds CPU/copies; no latency or memory
improvement is claimed. This is not complete CAN-04 closure.

Rollback:review/revert isolated code change. Existing canonical-only storage
rehydrates through the pre-existing view adapters; qualify rollback against exact
candidate binaries before deployment. Never replace the database or delete history
as rollback. No production or bulk-migration action was performed.

Progress:0/5 release gates approved (0%), not coding completion. The20.38% is
fixture storage savings, not overall remediation completion.
