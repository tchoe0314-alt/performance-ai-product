# SEC-03 — email ownership and invitation proof boundary

## Implemented and tested locally

Existing accounts no longer receive project membership just because their email
matches a new invitation. Every invitation remains pending until a recipient
uses a purpose-bound, expiring, one-use token. Only token digests persist.
Acceptance binds the authenticated account's current email, rechecks invitation
status/role/project owner and commits membership, verification and consumption
atomically. It emits an access-audit event without the token. Parallel claims
have one winner. Revoked/expired/replayed/wrong-account proofs reject.

Authenticated APIs request/confirm address verification and accept invitations.
Only the creator can send/resend/revoke pending invitations; roles remain
server-controlled and viewer is default. Revoking an accepted invitation does
not silently revoke active membership: membership removal is a separate action.

Delivery uses an explicitly injected interface. The default sender is
unconfigured and fails closed; there is no fake-outbox HTTP endpoint or raw-code
response. Tests inject the approved in-memory fake sender. Undelivered tokens
are invalidated. No real email, paid provider or production record was accessed.

## Evidence

Seven proof tests plus an ASGI scenario cover pre-registration attack denial,
hash-only persistence, exact expiry, wrong identity/purpose, revocation, replay,
concurrent claims and configured/unconfigured sender behavior. Role/collaboration/
history/data-lifecycle tests now explicitly traverse fake-mailbox acceptance
instead of bypassing the proof requirement or assuming email matching grants
access. The direct calculation stub explicitly identifies simulated current
execution; unknown-method archive coverage remains in calculation-history tests.

Fresh combined isolated run:50 PASS, one test-client deprecation warning, no
skips. Report:
`/tmp/civora-repair-verification.NBAOtD/results/identity-regression-21.xml`.

## Not yet closed

This is the backend ownership boundary, not full enrollment readiness. Frontend
confirmation/acceptance controls, registration/invitation enrollment policy,
account recovery, qualified delivery, legacy previously auto-granted membership
review, PostgreSQL race verification and independent AppSec review remain open.
The broad backend run started before these changes and cannot certify them.

The two identity tables are additive and were exercised only in disposable
databases. Existing users/projects are not automatically marked verified. No
existing database migration was run. Deployment must explicitly review additive
schema/recovery behavior and the treatment of old grants. Keep new invitation
routes disabled or equivalently proof-protected on rollback; never return to
automatic membership solely on an unverified email match.
