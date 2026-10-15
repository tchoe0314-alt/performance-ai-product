# Imagery gateway pinned downloads

Parent: `24c928ba`. SEC-01 remaining public image fetch boundary.

Confirmed: imagery _fetch_image checked URL strings but used direct requests,
allowing DNS rebinding or unsafe redirect destinations before final validation.
It now uses public-HTTPS pinned transport with the existing image host policy
checked before every connection/hop. Private/insecure override flags cannot
bypass the public transport. A private connector needs a separate reviewed design.

The common transport adds a strictly integer byte budget, hard-capped15MiB;
JSON/text/terrain defaults remain2MiB. Gateway retains its existing default15MiB
and lower operator limits; higher settings now reject. Image downloads have a
20second transport deadline, bounded streamed reads and no ambient credentials.
The policy callback runs after public destination validation but before connect.
Binary fake responses preserve headers and stream incrementally for offline
regression tests. Detector-provider POST integrations are unchanged.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/imagery-64.xml`:
57 tests+13 subtests passed, one existing httpx warning. Scope: new private-flag
bypass/budget/policy ordering tests, shared DNS/redirect/deadline security tests,
terrain/text binary compatibility and original gateway detection/auth/stream-size
tests. No real image/provider requests, secrets, production/customer data,
deployment, paid API or payments used.

Open: independent AppSec/deployed egress review, detector POST endpoint trust,
image/model resource limits, source rights and real provider qualification. The
transport does not prove image geometry or AI outputs correct. No full security
closure or release acceptance claimed. Rollback is an isolated commit revert,
no schema/data changes; it would restore the direct-request DNS/redirect gap.
