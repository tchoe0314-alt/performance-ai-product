# Existing-project browser result ownership

Parent: `fa5f9c52c8419f2b5ae87f0a399d630bcd0b7ade`.
Finding: CAN-03 / SEC-10, client result replacement (confirmed in code).

## Cause and repair

The public save endpoint required a design revision but passed the browser's
`latest_result` to the full-save workflow. Design revisions intentionally exclude
calculation publication, so an old browser result could replace a newer server
calculation while its design revision still matched.

Existing-project public saves now discard the echoed `latest_result` before
invoking the existing application workflow. The real ProjectStore therefore uses
its locked shell save, which does not update the result sidecar and retains
server-owned canonical result collections. This avoids a second read/write race.
Normal browser clients need not stop echoing their cached result immediately.
Design changes, explicit replacement recovery and authorization remain governed
by their existing policies. A browser save is not an execution-publication API.

No numerical formulas, data migrations or stored projects changed.
New-project/import/copy result acceptance is deliberately unchanged and still
requires a separate provenance/trust review; this is not global result-authenticity
or all-writer concurrency closure. Legacy background-job fallback saves and
optional low-level revision checks remain open.

## Fresh verification

Only synthetic disposable databases were used. Network/process guards remained
enabled; no providers, production/customer data, deployments or payments used.

Under `/tmp/civora-repair-verification.NBAOtD/results/`:

- `ownership-35.xml`: 16 tests passed, including four new result-ownership cases,
  existing save preconditions and concurrent/stale revision checks.
- `ownership-36.xml`: 64 tests and 11 subtests passed across application project
  workflows, canonical document handling and project-store fast paths.

New regression expectations are independent invariants: the exact server result
and canonical calculation collection must survive empty, stale and fabricated
client echoes; a valid rename succeeds; a repeated obsolete revision conflicts
without changing the project. New-project compatibility remains explicitly tested.

These are scoped regression results, not current full-suite release acceptance.
Rollback: revert this isolated commit if necessary; no database rollback is
required. Reverting reopens the stale-result replacement vulnerability, so do not
restore externally exposed saves without equivalent protection.
