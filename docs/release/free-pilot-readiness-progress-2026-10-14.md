# Free invitation pilot: implementation and evidence

Prepared October 14, 2026 (America/Chicago). This is a software verification report, not a declaration that every pilot/customer/investor gate is complete.

## Exact candidate and authority

- Isolated checkout: `/tmp/civora-free-pilot-rc-20261014.8pwoXP`.
- Branch: `codex/free-invite-pilot-rc-20261014`.
- Tested application revision: `23ac4e76fc4aeffc65f3c2af2b2895416fe0ba5e`.
- The production frontend artifact reports that exact full revision at `/api/release-identity`; the candidate working tree remained clean after the final build and tests.
- Both observed live commits are ancestors of this candidate: frontend `ee2055de42b3561eab8822257f911c2dfb693e26`, API `597c46a3353f3a58b70925f74d753a679c8ce3de`.
- The inherited primary working tree and its index were preserved. The candidate contains the relevant accumulated software changes, not only this pass's fixes. Do not mistake the initial 388-file candidate inventory for 388 newly implemented features.
- Founder decisions remain free, invitation-only, locations open, reuse existing hosting/backend/subscriptions, no purchases or paid generation, and founder-arranged participants/reviewers. See `docs/product/free-invitation-pilot-decisions-2026-10-14.md`.

## Changes, reasons and affected verification

| Change | Why | Evidence |
| --- | --- | --- |
| Bound each sign-in attempt to 15 seconds and abort the transport; retain at most one retry for transient gateway/network errors. | A stalled request must release the busy state. Wrong passwords, rate limits, explicit cancellations and ordinary server errors must not loop or create late sessions. | Deadline contracts and actual stalled/recovery website checks; desktop/touch browser checks. |
| Default application keep-alive to 65 seconds in all current backend launch paths, with an explicit environment override. | Mitigate a plausible upstream/application connection-lifetime mismatch. This is not an established diagnosis of the live 502. | Startup/runner tests and two actual Gunicorn/Uvicorn TCP-reuse probes: a 3-second setting closed the socket after a 4.2-second pause; 65 seconds retained it. |
| Give parking its own readiness target and freshness state. | Parking generation must not be hidden behind the roadway target or report roadway freshness. | Readiness contracts and actual parking generation/reopening. |
| Prevent unsuccessful or server-archived calculations from publishing as active browser results. | A completed HTTP request/job is not equivalent to a successful, current calculation. | Execution contracts, actual manual failure UI, backend active/history tests. |
| Persist direct canonical calculations, checking editor access before execution and rechecking at save. | Successful direct runs previously did not enter the same governed history as queued calculations. | Real website calculation/save/reload; direct-route permission and edit-race tests. |
| Only boolean `success: true` may replace the active calculation. | Failed, missing, string or numeric success values must stay history and preserve the last valid active result. | Regression cases and native PostgreSQL JSON/history queries. |
| Save and await the live calculation checkpoint before generation; stop if saving fails. | Generated geometry or stale project-shell inputs must not race the calculation snapshot. | Website generation/persistence and relevant save/execution regressions. |
| Move selective engine omission into validated execution metadata rather than changing canonical manual fields. | Running parking alone must not silently rewrite grading/drainage/utility inputs and make an unchanged result stale. | Seven execution-scope tests; actual parking current/reopen checks. |
| Restore only the successful selected system's freshness. | Reopening parking must not claim unrelated grading or utilities are current. | Reopening contracts and real UI assertions. |
| Honor explicit public-signup settings in private-alpha as well as other modes, including an empty database. | An operator's invitation-only setting was previously ignored in private-alpha; an explicitly closed service must not permit public bootstrap. | Nineteen focused policy cases and native PostgreSQL HTTP signup/login/logout checks. |
| Show sign-in and a support link when signup is closed, rather than a misleading account-creation action. | The visible controls must agree with backend access policy. | Actual closed-registration UI checks in Chrome, WebKit and touch viewports. |
| Allow a revision-verified saved result to be reviewed even if some engineering systems remain stale; retain stale export guards and live-input matching. | A current partial result should not disappear merely because another system still needs work. | Canonical stale-result exclusion and full staged reopening probes. |
| Preserve entered terrain descriptions when rebuilding control payloads. | Terrain has no equivalent dimension control; ordinary canvas operations must not erase its source input. | Explicit edit/clear/preservation contracts and real full-run reopening. |
| Separate review-only terrain assumptions from canonical inputs. Validate their mode/range/schema, preserve explicit terrain/omission contracts, preserve the grading minimum, and record assumption provenance. | A frontend-only terrain/minimum-slope override caused saved controls and calculation requests to disagree. Manual mode must not silently acquire guessed terrain. | Twelve assumption cases, related workflow/history tests, full website runs across browsers and PostgreSQL. |
| Remove internal `runtime_resume` snapshots from parsed-input response echoes only. Engine inputs, final plans, phase controls and input bindings remain intact. | Repeated previous-plan copies inflated each staged response and history entry. | A dedicated equivalence/nonmutation/binding probe; real staged runs. Parsed-input metadata dropped from megabytes to approximately 3.5 KB in the observed fixture; the full result still contains substantial review data. |

## Final verification

- **Settled backend sweep:** 2,239 passed; 195 subtests passed; 56 dependency deprecation warnings; zero failures; 418.64 seconds. XML: `/tmp/civora-free-pilot-final-settled-backend-20261014.xml`. No application source changed after this run began.
- **Production frontend build and TypeScript validation:** passed for the exact candidate revision above. Targeted lint and whitespace checks passed.
- **Latest Chrome calculation/terrain/readiness group:** eight passed in 1.3 minutes. Includes actual manual failure exclusion, parking save/reopen, full staged approvals and reopening, plus software contracts.
- **Latest cross-device group:** twelve passed in 4.3 minutes: four each on desktop WebKit, mobile Chromium and mobile WebKit. Includes the same real calculation paths and closed-registration UI. Touch profiles are emulation, not physical-device certification.
- **Actual PostgreSQL 16.15 website/API group:** nine passed in 1.9 minutes. Includes preliminary PDF/DXF download and owner isolation, stale/canonical editing and reopening, manual/assisted parking, full staged execution, current-drawing exports and metric DXF units. This group includes a pure guard case and an API-only metric case; it is not nine distinct interactive UI journeys.
- **Native PostgreSQL database probe:** six scenario groups passed: schema/account/project initialization and active persistence; exact JSON-boolean history/latest-success queries; viewer write rejection; concurrent edit/calculation row-lock protection and late-result exclusion; failed transaction reset/pool reuse; and exact reopening through a fresh database pool. Preserved diagnostic: `scripts/verify_native_postgres_20261014.py` in the primary workspace, outside the frozen candidate.
- **Native PostgreSQL HTTP access policy probe:** public signup disabled, registration rejected with 403, an approved existing account signs in, an incorrect password returns 401, and logout succeeds. This used a separate disposable local API process, not the hosted site.
- **Other relevant passes in this turn:** 22 Chrome login/canonical checks; 18 cross-device login checks; eight paced two-tab/history/save-recovery checks; actual keep-alive transport tests. These overlap final groups and are not additive case counts.
- **Runtime dependencies:** all 66 installed Python packages compatible. The runtime has no standalone `pip` module; the successful check used `uv pip check`, not the failed `python -m pip` invocation.
- **Dependency/security findings:** fresh production frontend audit reports zero known vulnerabilities. Full development audit still reports five high-severity affected nodes in the braces/micromatch/fast-glob/Next lint chain ([upstream advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)). The suggested forced Next lint downgrade to 14.2.35 is incompatible with the 16.3.8 baseline; no downgrade or waiver was applied. Final targeted backend static scan reports zero medium/high and seven low findings across the selected five files. These are not security certification results.

### What the full staged test does and does not prove

The representative full run completes, saves a revision-bound result and quantities, survives reopening, and preserves immutable calculation history. Its engineering stage record still contains failed/partial work. The test therefore requires calculated exports to remain blocked, rather than treating a completed job or `success: true` as proof that every engineering stage is usable. Default conceptual pricing remains `production_usable: false`; this does not validate a customer budget or prove that every UI represents absent sourced prices as unknown.

The successful fixture-based review PDF/DXF checks and drawing-only exports are separate evidence. They do **not** close the still-needed positive end-to-end gate: a fully valid commercial engineering result through quantities, sourced pricing and calculated review exports, followed by independent CAD/professional acceptance.

## Failures and limits retained, not hidden

- A 63-check Chrome batch initially passed 51 and failed 12 during disposable account creation with HTTP 429. The account-creation protection was not weakened. Affected paths were rerun in smaller batches and subsequent final PostgreSQL/browser groups.
- Earlier full-run probes revealed a missing parking action, missing direct persistence, execution-scope fingerprint drift and terrain-induced reopening drift. Those findings produced the fixes above; they were not waived.
- Larger full-run probes timed out and exhausted local disk while recording repeated large responses; local SQLite also reported disk I/O errors. One intermediate smaller full-run polling request returned HTTP 500. Later settled SQLite and PostgreSQL staged runs passed, but this is not proof of sustained capacity or the live gateway problem's resolution.
- The small fixture's full staged runs took approximately 1.2–1.3 minutes including review checkpoints. Three earlier direct small-commercial benchmark iterations were approximately 6.6–6.9 seconds and 121 MB peak memory. These are different workloads, not comparable capacity promises.
- Earlier builds failed on test schema/type errors and compiler-cache ENOSPC. The type probes were corrected to use the declared schema; final build success is recorded separately above.
- The latest Firefox probe could not complete browser launch and was interrupted. It is unverified, not passed and not an accepted browser-policy exception.
- Existing drawing-only ceilings of 500 objects/3,000 vertices remain rejection limits, not a demonstrated all-feature operating envelope. Hosted concurrency, large-site staged response sizes, worker interruption/durability and real-file limits still need explicit acceptance evidence.

## Hosting and temporary resource handling

Read-only live checks confirmed the frontend still reports `ee2055de42b3561eab8822257f911c2dfb693e26`; API health reports the older `597c46a3353f` build. This candidate is **not live**. Earlier read-only provider logs showed a login 502 with an unexpectedly closed upstream connection. The keep-alive change is a tested mitigation candidate, not a proven hosted fix. Current health 200 is not authenticated workflow verification.

Native PostgreSQL ran in a dedicated localhost-only disposable cluster; no customer database, account, project or backup was changed. Homebrew package attempts failed because no compatible bottle was selected on this prerelease Mac. The alternative was the official single-version [Postgres.app download](https://postgresapp.com/downloads.html), mounted read-only after code-signature verification and notarization assessment. It was not copied into Applications or enabled at login. No additional hosted backend or paid service was created.

Only owned, regenerable compiler caches were removed. Three retired synthetic SQLite databases were losslessly compressed into their corresponding `.db.gz` files (about 27, 24 and 15 MB), preserving recovery evidence. Customer files, inherited investor artifacts, primary source edits and unrelated test evidence were not removed. PostgreSQL test artifacts remain under the dedicated temporary directory; no production restore was performed.

No deployment, push, real payment, paid AI/imagery call or external outreach occurred. Local candidate commits were created; the primary working tree/index was not blanket-staged.

At handoff, the owned temporary frontend, both native API processes and PostgreSQL were stopped cleanly, and the read-only software image was detached. Test databases/artifacts remain recoverable; no background/login service was installed.

## Remaining launch gates and next sequence

1. Complete a **positive** commercial calculation-to-calculated-export proof with valid, consistent constraints and source records; resolve failed/partial stage explanations. Do not convert missing survey/utility/control facts or assumptions into verified engineering evidence.
2. Establish realistic project/run/concurrency bounds and recovery evidence, investigate remaining large-response behavior, and resolve Firefox or obtain a supported-browser decision. Development-only advisories remain explicitly open.
3. Use this exact source candidate or a newly reverified successor for the existing hosting release. Record target settings, current release/rollback IDs, invitation flag, actual API/web identity and backup/recovery evidence. Then deploy under the founder's applicable authorization and run authorized authenticated live login, roles, save/reopen, worker and artifact checks. Local results do not satisfy this gate.
4. Finalize support owner/monitored contact and data-retention preferences. Questions were sent to the founder; no answer or policy approval is assumed. Actual terms/privacy/confidential-data language still needs appropriate human approval before invitation.
5. Founder-arranged rights-cleared real-site inputs, participants and engineer/CAD reviewers remain separate acceptance evidence. Do not recruit or invent acceptance. Free-pilot preparation does not require real billing/payment execution; paid-customer verification and investor claims remain later gates.

Conclusion: core state/access/calculation reliability is materially better and has substantially stronger local evidence. The entire pilot-to-customers plan is **not complete**, and this report does not authorize reliance on engineering outputs or declare the service pilot-ready.
