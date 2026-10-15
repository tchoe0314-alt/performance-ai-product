# Authentication safeguards — partial security remediation

## Implemented

- SEC-04: newly issued tokens persist as SHA-256 digests, not usable bearer
  values. Absolute expiry defaults to7days and idle expiry to24hours; exact
  expiry and future-dated sessions reject. Existing plaintext sessions require
  fresh login rather than an indefinite compatibility fallback. No stored
  project/account data or existing database was migrated during development.
- Atomic single-winner session rotation preserves original absolute lifetime.
  Password-confirmed all-device revocation only removes the actor's sessions.
  Both are exposed through authenticated, rate-limited API routes. Browser
  controls/transport redesign remain separate; rotation is not automatic.
- SEC-02/06 containment: source limits ignore arbitrary bearer and forwarding
  header text. Local counters have a bounded cardinality and fail closed on
  saturation. These remain per-process, not distributed/account-target limits.
- SEC-07: detailed runtime/production diagnostics require explicit operator
  user IDs from `CIVORA_OPERATOR_USER_IDS`; unset policy denies all operators.
  No environment configuration was changed. Operator policy/audit logging and
  real proxy deployment validation still require qualification.

## Fresh tests

53 tests and40 subtests PASS in isolated auth/application-file/core checks;
five standalone session tests cover hashes, legacy rejection, exact expiry,
future timestamps, concurrent rotation and user-isolated revocation. A separate
in-process ASGI test passes authenticated rotation/revocation routes, incorrect
password denial, unauthenticated denial and revoked-token denial. No real
network service, paid API or customer record was involved.

Reports are under `/tmp/civora-repair-verification.NBAOtD/results/`:
`auth-09.xml`, `auth-09.log`, `session-api-10.log`. These are temporary local
verification, not independent security certification or full release evidence.

## Remaining scope and rollback

SEC-03 enrollment/invitations, shared/account limits, browser session storage,
independent AppSec review and final release acceptance remain open. None is
closed by these changes. Existing sessions will log out on eventual deployment;
communicate the reauthentication requirement and verify with the release gate.
Rollback must not restore plaintext/non-expiring authentication. Prefer
roll-forward; code rollback must invalidate incompatible sessions safely.
