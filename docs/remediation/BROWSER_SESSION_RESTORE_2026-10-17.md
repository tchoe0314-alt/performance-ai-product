# Real local candidate review and transient session restoration

Application base: `ff714618` plus the `useAuthState.ts` repair below.
Scope: follow-up SEC-04/session usability and CAN-03 candidate-review verification.
No deployment, external provider, package installation or customer data access.

## New defect and implementation

A repeated actual Chromium run reached the existing auth rate limit. The restore
hook erased its tab-scoped token for every failed `/api/auth/me`, including429.
The observed screen displayed the auth rate-limit warning instead of the workspace.
An independently executed offline regression of the actual hook/API classifier
also failed:429 changed the synthetic stored token from nonempty to empty.

`useAuthState` now clears credentials only for an authentication-expired response
(401). Rate limits, service failures, access errors and transport errors retain the
potentially valid tab credential and report the failure through the workspace
status callback. Server authorization remains required for every request; retaining
a token does not make its user verified or grant permissions. No rate limit,
session lifetime, authentication requirement or persistence scope is relaxed.

A callback ref avoids restarting the restore effect when the status callback
identity changes. This is not an automatic retry loop; reload retries the check.

## Behavior verified

`apps/web/tests/live/remediation-candidate-review.spec.ts` uses the real local
Next/React site and real FastAPI/SQLite fixture, synthetic owner/project only:

1. Login and create/save two synthetic source candidates through the API.
2. Restore the actual workspace; open the collapsed Site Context control.
3. Accept b1 through the browser; assert real POST200 and Reviewed-tab acceptance.
4. Intercept b2's request only long enough to commit a newer project edit through
   the actual API; forward the unchanged browser request; assert real POST409.
5. Assert the stored revision equals the newer edit, b1 remains accepted, b2 pending.
6. Reload the browser; assert the newer project name and both review states persist.
7. Assert no uncaught browser page errors.

Requests to non-fixture page origins are aborted. The test is explicitly opt-in,
requires a loopback API and fixed owned local UI origin, and cannot run against a
hosted/customer website. The inherited untracked test was completed and preserved,
not discarded. No UI assertion was replaced with a forced click or success mock.

The offline test `apps/web/tests/auth-restore-failures.cjs` runs the actual hook and
API error classifier with a minimal hook-state/effect adapter, fake fetch/storage:
429,500,503,403,network failure retain the token and emit a status message;401
clears it;200 restores identity and refreshes project/job lists. This is behavioral
handler coverage, not independent DOM/browser proof for every error status.

## Results and evidence

Committed reports: `browser-session-2026-10-17/`.

|Run|Outcome|Disposition|
|---|---|---|
|browser-01|1 passed,11.8s|Actual acceptance/conflict/reload before transient-restore repair|
|browser-repeat|2 passed,1 failed|Preserved; exposed rate-limit session erasure|
|browser-final|1 interrupted,2 not run|Preserved, not counted as passing; stopped after mistakenly overlapping the still-running repeat lane|
|restore-before|Failed429 assertion|Actual hook on original implementation|
|restore-final|7 scenarios passed|Actual hook/API classifier on repaired implementation|
|browser-final02|3 passed,15.5s;0 retries/skips|Final test and repaired app; sequential execution, no other browser lane active|
|TypeScript|Passed|`tsc --noEmit --incremental false`; networking and all file writes denied|

Do not sum these overlapping browser runs into feature coverage or erase the failed
and interrupted results. Final02 is three repeats of ONE defined workflow, not
three distinct product workflows. The final repeat does not itself assert that
every transient HTTP status occurred; those are explicit offline scenarios.

Final verified source SHA256:

- useAuthState.ts: `ecbd682c9d0bc7f69ace75b7e669fa52f60309bd4921b5a7ff69e04ffee41f74`
- auth-restore-failures.cjs: `bf44ea0dfb1ba5eb73c2fe608b88177ed8b21f90f2a12f22d9a46bfb79fae4d4`
- remediation-candidate-review.spec.ts: `9cc35182e0e59ab87317f7fabe900b15169e6bde5cb4b052608d2cdea95765dc`
- committed browser-final02.json: `4fec42a1e319135c72fee4c0aa9f69f9f553f4d7a8bacc7f523fc2e5aca11dfb`

Report final newlines are normalized by the patch writer. Original failed outputs
retain traceback whitespace; do not call a whole-evidence whitespace check clean.
Screenshots/error-context referenced by reports remain in the disposable root;
their binary images are not the durable report artifacts. Prior October15 temp
reports were unavailable on resumption; existing historical summaries remain.

## Isolation / repeat recipe

Source copied to `/tmp/civora-session-verification.pW76oM/source`; installed
node_modules reused read-only. OS sandbox denied non-loopback outbound networking,
non-loopback binds and writes outside the owned root. API Python guard limited
bind/connect/DNS to owned loopback ports49321/49611, denied subprocesses and reads
of external .env/database files. No actual environment file was loaded or edited.

API fixture: `tests/remediation/serve_identity_fixture.py`, explicit
`CIVORA_RUN_DISPOSABLE_FIXTURE=1`, newly created temporary storage prefix
`civora-ui-fixture-`, CORS local49321, AI/images/learning disabled. Private fake
mailbox has synthetic addresses only and no HTTP read endpoint. Next used the
temporary source, `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:49611`, telemetry off
and a disposable `.next-remediation` directory. Its automatic temp tsconfig update
was NOT copied into the repository.

For a new authorized isolated run, recreate those guards and a new fixture directory;
do not reuse customer storage. Start API49611 and Next49321. A Playwright config
must set testDir to copied `apps/web/tests/live`, match ONLY
`remediation-candidate-review.spec.ts`, baseURL local49321, Chromium,workers1,
retries0 and new JSON/output paths. Invoke installed Playwright with
`CIVORA_DISPOSABLE_IDENTITY_UI=1 CIVORA_IDENTITY_FIXTURE_API=http://127.0.0.1:49611`.
Use `repeatEach:3` for repeatability; leave actual abuse limits unchanged. Run the
offline handler via `node tests/auth-restore-failures.cjs` and readonly TypeScript
checking from copied `apps/web`. No npm test/build scripts with cleanup hooks.
Both local servers and all browser runners were stopped and process absence checked.

## Remaining scope / rollback

Not a full-browser suite, hosted acceptance, multi-user load/tenant qualification,
all-writer proof, independent usability study or release-gate approval. Race between
an old restore response and a newly logged-in account still requires explicit
generation/cancellation tests; this repair does not claim to solve it. Full UI
recovery controls/status placement and PostgreSQL qualification remain open.

Rollback the hook repair in a new commit if needed; no migration is necessary.
Preserve the tests and original reports. Rollback reintroduces the demonstrated
session loss and therefore is not a safe release disposition. No deployment/push.

Original audit last verified24/24 (100%), not rerun here. Release gates0/5 (0%).
Seven broader engineering acceptance failures and external engineering/security/
legal/customer evidence remain open. No defensible overall completion percentage.
