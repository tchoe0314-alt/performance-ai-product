# Unbound background calculation publication

Parent revision: `121bd7d9107dd11e3133c21820cb401441cc0fc1`.
Finding: CAN-03/SEC-10, legacy job full-record fallback (confirmed in code).

## Root cause and change

`ProjectStore.save_calculation_result` previously returned None when a job's
source inputs lacked a canonical calculation binding. The job helper then used
`save_project`, potentially restoring stale input geometry, labels and session
state over newer edits. Re-fetching the project at completion did not prove the
job's input correspondence.

The real store now archives unbound results in existing calculation history,
using a namespaced deterministic hash of the exact finite JSON source input.
The hash establishes historical identity only, not compatibility with the live
design. Such results always have disposition `archived` and reason
`input_binding_unverified`, whether the calculation reported success or failure.
No result sidecar, geometry, metadata or project timestamp is changed. The helper
receives the persisted result and no longer reaches its full-save fallback for
this case. Canonical input matching and current-engine requirements are unchanged.

No schema/data migration, deletion, formula or standard change was performed.
Old results and their inputs remain retrievable. A migrated-input rerun is needed
before activation; silently activating an unbound execution is intentionally not
preserved as compatibility behavior. The old test asserting None/no history was
replaced with explicit preservation/archive assertions because that expectation
encoded the unsafe fallback, not correct engineering behavior.

## Verification

Fresh isolated, synthetic-only reports under
`/tmp/civora-repair-verification.NBAOtD/results/`:

- `unbound-37.xml`: 37 tests passed: new real-store helper integration for
  successful/failed legacy executions, reopening retained inputs/output,
  nonfinite input rejection, calculation history, stale/concurrent revisions and
  browser result ownership.
- `unbound-38.xml`: 43 tests passed: job application workflows and store fast paths.

No external services, production/customer data, payments or deployments used.
The invariant is exact project equality before/after late unbound publication,
with history independently reopened from the disposable database. A monkeypatch
makes any attempted full-save fallback fail the regression immediately.

## Remaining risks / rollback

This does not qualify PostgreSQL races, all low-level writers or new-project
result trust. Test doubles/alternate store implementations that return None can
still use the compatibility fallback; production uses the repaired ProjectStore.
Persisted legacy jobs should be rerun after migration, not re-labeled as verified.
No engineering or release gate is declared passed.

Rollback is an isolated commit revert, with no schema rollback required. Preserve
new history records. Reverting restores an unsafe publication path and must not
be used as a production compatibility workaround without equivalent protection.
