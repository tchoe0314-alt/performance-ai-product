# Terrain request deadline and tile admission

Parent: `ec19c7c7`. Operational resource limits, not numerical conventions.

The surface sampler now admits at most32 distinct tiles and uses a30-second
monotonic request budget. Remaining time is passed to each tile fetch, whose
own transport limit remains at most10seconds. Deadline checks occur before
each sample/fetch and before surface publication; exhaustion returns unavailable
rather than a partial grid. Existing sample/axis/byte/image limits remain intact.
The limits are conservative initial operating policies, not measured capacity
claims. They do not change geometry, elevations or resolution to force success.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/terrain-52.xml`:
26 tests+13 subtests passed across request budgets, tile safety, fallback
provenance and shared transport. Synthetic clocks verify exhaustion and remaining
budget propagation without sleeping; deterministic tile coordinates verify that
the first over-budget tile is never fetched. No live provider, actual token,
production/customer data, deployment or paid service used.

Limitations: deadline checks are cooperative around bounded network/decode work,
not process-preemptive wall-clock guarantees. Provider coverage/runtime at these
limits, cancellation integration and browser diagnostics need qualification.
Units/datum and independent engineering accuracy remain open. Rollback requires
an isolated commit revert, no data/schema migration; retain equivalent limits
before exposing large requests. Existing saved data/evidence was not changed.
