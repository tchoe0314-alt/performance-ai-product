# SEC-02/06 — shared sliding-window protection

Replaced per-process counters with atomic sliding windows in Civora's existing
database. No new paid service, external storage or dependency is required.
SQLite uses a write transaction; PostgreSQL uses row locks and database time
read after lock acquisition. New-identity admission has a shared capacity lock;
active protection is never evicted to make space. Stored identifiers are hashes,
not raw bearer strings, emails or source addresses. Events and capacity are
bounded; expired rows are reclaimed on new-identity admission.

Independent source and normalized account-target limits protect login and
registration. Arbitrary bearer/X-Forwarded-For values cannot reset source limits,
and changing source/worker cannot reset account limits.429 responses include
Retry-After. Storage failure, corrupt state, backward clocks and inconsistent
active replica policy fail closed with503 rather than creating fresh local
counters. There is no permanent account lockout.

Tests now use isolated rate stores instead of clearing a production-style
global map; configured protections were not disabled to obtain passes.

Fresh isolated run:45 tests and5 subtests PASS, one test-client deprecation
warning, no skips. It covers24 concurrent requests across four SQLite store
instances admitting exactly5, capacity/TTL/window boundaries, stable source and
account identities through actual ASGI requests, storage outage, policy drift,
and existing release/account/session/invitation behavior. PostgreSQL SQL-order
coverage uses a fake connection and is explicitly not a real PostgreSQL race.
Report: `/tmp/civora-repair-verification.NBAOtD/results/shared-rate-29.xml`.

## Deployment/review obligations

- Only disposable stores were initialized. Existing/customer databases and
  deployment configuration were not changed. Additive schema/rollback approval
  is required before deployment.
- All replicas must use consistent limit/window configuration. A rolling policy
  mismatch intentionally returns503 until prior active state expires; coordinate
  configuration changes rather than silently resetting protection.
- Expiration is logical; inactive rows are reclaimed on later admission, not
  by a promised automatic physical-retention timer.
- SQLite write contention, PostgreSQL races/throughput, DB-outage operational
  handling, trusted proxy topology and workload/NAT fairness need qualification.
  No local PostgreSQL server binary was available; none was installed or bought.
- Server-provided client identity remains authoritative. Raw forwarded headers
  are not accepted by this code; verify any upstream proxy middleware separately.
- Rollback must retain equivalent shared/source/account protection or disable
  affected public routes. Do not restore a per-worker bypass as a fallback.

This closes the implemented process-local counter gap, not the complete
independent security/production release gate.
