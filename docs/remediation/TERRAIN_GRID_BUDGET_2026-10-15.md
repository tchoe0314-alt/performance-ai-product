# Terrain provider grid admission

Parent: `a2d28f1b`. Resource/invalid-input follow-up.

The provider previously trusted callers for grid sizing and finite coordinates.
It now independently enforces the grading caller's existing intended12000-sample,
140-per-axis envelope, integer dimensions of at least2, finite numeric inputs,
valid geographic center ranges and positive cell/lot dimensions. Invalid input
returns unavailable before tile fetch. It does not silently coarsen, clip or
change the requested numerical grid. No existing data or numerical units changed.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/budget-50.xml`.
22 tests passed: synthetic invalid/huge/nonfinite grids, valid/missing terrain,
tile safety, fallback provenance and existing TIN behavior. No live provider,
actual token, production/customer data, paid service or deployment used.

This bounds sample allocation, not overall request latency or distinct tile
fetches. Shared constant ownership, caller rounding at the envelope, per-request
tile/deadline budgets, cancellation and missing-tile retry behavior remain open.
Units/datum and independent terrain accuracy remain unverified. Rollback is an
isolated commit revert, no data migration; retain equivalent provider admission
checks before accepting arbitrary grid requests.
