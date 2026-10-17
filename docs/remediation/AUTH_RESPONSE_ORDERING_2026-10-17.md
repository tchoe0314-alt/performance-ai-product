# Authentication response ownership

Base: `2623f4c27ee556d166556a43430af0859a4e3d08`.
SEC-04/client-state-integrity follow-up. This addresses the response-ordering gap
explicitly left open by `BROWSER_SESSION_RESTORE_2026-10-17.md`.

## Independently reproduced behavior

Controlled deferred responses execute the actual `useAuthState` hook and API
classifier without network or sleeps. All six initial assertions failed:

|Interleaving|Required behavior|Original failure|
|---|---|---|
|Old restore401 after new authentication|Keep new token/user|New token erased|
|Old restore200 after new authentication|Keep new identity; no old refresh|Old user published|
|Restore200 after logout|Stay logged out; no old refresh|Old user restored|
|Pending authentication completes after logout|Stay logged out|New token published despite logout|
|Two attempts complete newest then oldest|Newest attempt wins|Older identity/token wins|
|Restore resolves after unmount|No state updates or refresh|Unmounted work still publishes|

These are confirmed client-side state defects, not evidence of a server tenant
authorization bypass. The before log is preserved unchanged except final newline
normalization in `auth-ordering-2026-10-17/ordering-before.log`.

## Implementation

`apps/web/app/hooks/useAuthState.ts` uses a request-generation ref. New auth,
logout and restore lifecycle cleanup invalidate superseded work. Restore reads
identity without side effects, then publishes user/refreshes only while current.
Its success, failure and initial auth-status branches respect lifecycle ownership.
Authentication success/error/loading/status publications check their generation.

Logout invalidates pending work and clears local state immediately, before waiting
for revocation of its captured token. It has no later state mutation that could
erase a subsequent login. Restore effect cleanup also invalidates work on unmount.
No token format, server authorization, expiry, rate limit, project schema or storage
scope changes. No migration or dependency change.

## Final verification

- **10 ordering scenarios passed**: six original cases plus stale restore429,
  delayed logout completion, stale sign-in failure and pending sign-in on unmount.
- **7 prior restore scenarios passed**:429/500/503/403/network retain credentials
  and warn;401 clears;200 refreshes. Expectations not weakened.
- **TypeScript passed** with no emit/incremental writes, all networking denied.
- **Real Chromium:3/3 repeats passed**,0 retries/skips, one workflow:
  actual project/candidate save, acceptance200, concurrent edit, stale decision409,
  API state inspection, browser reload and persistent accepted/pending states.
  This is regression coverage, not DOM execution of each synthetic ordering case.
- Source diff whitespace check passed. Historical traceback whitespace is retained
  in evidence files; do not claim an all-artifact whitespace-clean result.

Verified SHA256:

- useAuthState.ts: `cae6e5fbb67618c7238e6ce93937fe2dcb69d61ff322b0d6f026e665a9c92ac9`
- auth-request-ordering.cjs: `346724cf74cdecbd68afb9309c1065adb3d3550c2030dbb39eb76782c5ed472d`

Reports in `auth-ordering-2026-10-17/`; disposable runtime/source root
`/tmp/civora-session-verification.pW76oM`. Existing node_modules reused, no installs.
Offline handler/type checks deny network and writes. Browser/API lanes use an OS
sandbox denying non-loopback networking and outside-root writes, API guard limiting
connections to owned49321/49611 and denying external .env/database reads and
subprocesses. Fresh fake-sender fixture storage, AI/images/learning disabled.
No existing customer storage, paid provider, hosted website, deployment or push.
Only the temporary Next config gained generated type includes; it is not copied
back. Existing browser/previous repair reports are preserved, not overwritten.

Repeat commands in the isolated copied web tree:
`node tests/auth-request-ordering.cjs`, `node tests/auth-restore-failures.cjs`,
`node node_modules/typescript/bin/tsc --noEmit --incremental false` with readonly
network-denying sandbox. For browser lane follow the prior browser-session record
with fresh fixture storage and fresh config/report paths, same opt-in test,workers1,
repeatEach3,retries0. Do not run against production or customer data.

## Remaining limits and next actions

Generation guards prevent these handlers from starting old-session refreshes after
supersession. They do not cancel project/job refresh callbacks already started
before an account transition: those callbacks need their own ownership checks.
No claim is made of complete all-writer/tenant or whole-UI concurrency correctness.
Ignored auth responses may still have created a server session; cleanup/expiry and
session listing require separate review. Transport requests are not aborted by this
patch; server authorization remains the trust boundary. Multi-tab behavior, full
browser/accessibility acceptance, PostgreSQL, restore/load and independent security
review remain required. Existing seven engineering acceptance failures remain open.

Rollback this client/test group in a new commit; no schema rollback needed.
Reverting reintroduces demonstrated state defects. Retain before/after evidence.
Original reconstructed audit checks last verified24/24 (100%), not rerun here;
release gates0/5 (0%) approved, not overall remediation percentage. Goal stays active.
