# Connected pilot execution: progress and remaining gates

October 13, 2026, America/Chicago. This is a verified implementation pass under the connected 11-step plan, not completion of the full plan, investor readiness, customer activation or professional acceptance.

## Changes and why

- Release readiness now requires matching report/manifest identities and rejects stale per-section evidence, dirty checkpoints, prefix-only hosted matches and mismatched actual hosted identities. Both verification/readiness commands mark dirty source. Verification does not resume older records under the same dirty label and rejects a checkpoint change during a section. This prevents old passing evidence from clearing a new candidate.
- Candidate storm enrichment may skip its initial deep copy only when the caller already owns a detached working summary. Public/default calls still copy; canonical manager/project copies and rollback remain. Equality, input isolation and existing hydraulic/conflict tests passed. This reduces redundant work without weakening engineering checks.
- Billing status cannot permit charging when paid-pilot mode is off, identity is absent or the user is outside the configured cohort, even with charging/legal/provider flags present. Tests use a fake configured provider; no payment was created. This repository's billing service is status/guard-oriented, not evidence that the user's existing checkout/subscription integration has been fully exercised.
- Project queries now select complete fixed SQLite/PostgreSQL statements rather than splice lock clauses or JSON-success expressions into SQL. Parameters, owner/member conditions, transaction boundaries, PostgreSQL row locks and history behavior remain. The initial scanner findings were constructions requiring review, not established exploitable injection vulnerabilities. They were addressed without adding blanket suppressions.
- Strengthened the bounded hosted test to verify authenticated cross-account read isolation, not merely anonymous rejection. Accounts/projects are synthetic; only the owned synthetic project is edited. Generation, exports, billing, customer data and settings changes are excluded from that harness.
- A live login returned HTTP 502 once. The provider's network record identifies `/api/auth/login`, a 1 ms duration and upstream error `connection closed unexpectedly`. Retry passed, but the underlying hosting cause is not established or repaired. Added local login-only recovery with one delayed retry for network failure or 502/503/504; wrong-password/access/rate-limit/validation/500 failures are not retried. Signup, billing and design writes are not automatically retried. Persistent failure remains visible; this is mitigation, not proof of hosted reliability.
- Prepared an internal pilot-offer/demo/measurement/investor outline, with unknown pricing, site, partner and approval inputs explicitly open. This is not published terms, a recorded demo, a customer case study or a completed pitch deck.

## Final backend and environment evidence

- First full run: **2 failed, 2,163 passed, 130 subtests passed, 56 warnings**, 331.37 seconds. The old temporary runtime had missing metadata across many packages and missing bundled GIS data; PostgreSQL pool import and GeoPackage creation failed. That run is not green and is retained as failure evidence.
- Recreated a separate environment from existing backend/test requirements with uncached wheels and copied files. `uv pip check` confirms **66 installed packages compatible**, including after the final full run. Production requirement audit and actual installed-package audit found no known vulnerabilities.
- Final full run after backend fixes: **2,169 passed, 132 subtests passed, 56 warnings**, 334.24 seconds. No backend source changes followed that run; subsequent frontend changes were tested separately.
- Affected intermediate suites: 75 hydraulic/production/conflict cases passed; 56 pool/GIS/project-revision/export/SQL cases passed in the repaired environment; 41 calculation/history/candidate/fast-path cases passed. These overlap the full run and are not added to its count.
- Static scans: backend/scripts had zero medium/high findings, with 96 low-severity findings and pre-existing narrow suppressions still reported. The three root planner modules had zero medium/high findings and six low findings. This is not a security certification or proof of no possible vulnerability.
- The previously recorded frontend development lint/glob advisory chain is not patched by this pass. Python audit results must not be represented as clearing every JavaScript dependency or every release risk.
- Heavy assisted case: 53.12 seconds total, 52.74-second call, versus the preceding 55.71-second total sample. Different run conditions and one sample per condition preclude a capacity guarantee or robust percentage-speedup claim. Performance remains open.
- Real commercial-pad automated benchmark passed on the final backend, with no failed comparisons; human review remains pending and revision is marked dirty. Report and fail-closed review worksheet: `/tmp/civora-connected-commercial-benchmark-20261013.json`, `/tmp/civora-connected-commercial-review-template-20261013.json`.

## Website/build evidence

- On the earlier production build against the updated local API, six persistence/layout/unit cases passed; after the SQL/runtime changes, seven export/layout cases passed. These packs overlap and do not constitute every website feature tested on the final auth build.
- Production web build `.next-pilot-auth1` passed, including TypeScript, using the disposable localhost API. Scoped lint and `git diff --check` passed.
- On that auth build: **18 Chromium checks passed**, comprising 11 pure login contracts, five UI recovery/failure checks and two authenticated persistence checks. **15 additional UI checks passed** across WebKit, mobile Chromium and mobile WebKit, five each.
- Login recovery deliberately injects one 502 and then forwards the second request to the real disposable API, verifying the authenticated user's identity. Negative UI cases inject errors to prove bounded retries and absence of a session. These are controlled fault-injection checks, not a real hosting outage reproduced locally.
- Live original bounded edit/save/reopen checks passed on four browser/device profiles. The strengthened two-account collection passed three profiles; mobile WebKit stopped at an actual login 502 before its assertions, then passed unchanged on a separate rerun. The failed run is retained; do not relabel the original collection all-green.
- Live test activity created **13 synthetic accounts and eight synthetic projects**, retained without deletion. No customer projects were touched. No paid generation, imagery, export jobs, real payments or deployment occurred on the live infrastructure in this pass.
- Existing hosting dashboard was inspected read-only through its already-signed-in session. The API service remains on its earlier active deployment; no redeploy, rollback, variable, resource, backup or permission action was performed.
- Firefox remains unverified from the earlier launch failure; no new Firefox pass is claimed.

## Recovery and existing infrastructure

- Local disposable SQLite backup/restore passed: `/tmp/civora-connected-recovery.OdeB24/report.json`. This is not a hosted PostgreSQL restore.
- Reused the existing August 8 hosted recovery record rather than buying or creating a replacement service. Current live health reports PostgreSQL, configured support/bug-report contacts, backups enabled, recorded restore `2026-08-08T15:20:12Z` and 28-day retention. The provider dashboard shows the existing production services/PITR bucket online.
- Configuration presence and a historical drill are not a fresh restore or guarantee of current provider recovery. Before release, confirm the recorded procedure, ownership, configuration and applicability, and obtain approval if repeating it requires a billed resource. Never restore over production.
- Live web identity remains `ee2055de42b3561eab8822257f911c2dfb693e26`; live API reports `597c46a3353f`. New local fixes are not live. The exact-candidate readiness aggregate correctly remains blocked; missing local evidence/configuration is not proof that existing hosted services do not exist.

## Connected plan status

| Steps | Progress | Gate still open |
| --- | --- | --- |
| 1: pilot promise | Existing single-parcel office/retail scope reused; internal offer drafted | Jurisdiction/site, limits and founder business decisions |
| 2: source baseline | Inventory/checkpoint guards strengthened | Clean scoped release from inherited working tree |
| 3: shared state/trust | Broader backend run and focused actual website flows passed | Final supported-scope coverage and legacy-entry audit, not every possible action certified |
| 4: commercial loop | Geometric alternatives and independent automated calculation benchmark exercised | One complete real-source website workflow, connected calculations/quantities and sourced pricing |
| 5: package | Preliminary PDF/DXF regression and owner-isolation checks passed | Detailed claimed geometry and external editable-CAD acceptance |
| 6: reliability | Copy cleanup, environment repair and login fault recovery tested | Representative performance/concurrency limits, Firefox decision and hosted connection failure |
| 7: hosted release | Bounded live isolation/save checks; existing recovery/support evidence reused | Clean candidate, formal revision-bound evidence, worker/artifact/rollback checks and deployment approval |
| 8: external review | Handoff checklist and fail-closed benchmark worksheet prepared | Rights-cleared real inputs, qualified reviewers, independent findings and repair/review loop |
| 9: customer operations | Offer/measurement draft and billing guard tests | Existing payment integration verification, pricing, accepted policies and support/account ownership |
| 10: pilot | Measurement protocol prepared | Authorized partner, real usage, corrections, repeat use and willingness to pay |
| 11: investors | Demo/package outline prepared | Actual founder/company/financial inputs and verified traction; no fictional customer results |

## Next required actions

Investigate the transient hosted upstream close and complete the supported full commercial workflow/performance gates. Identify the intended clean release without committing unrelated inherited work; run candidate-bound release checks and request specific deployment approval. Real-site/professional/customer gates require founder choices and authorized participants. Software tests cannot close them.

The founder was asked which jurisdiction to target and whether reviewers/partner exist or need to be identified. No reply has yet supplied those inputs. No external contact, invitation, purchase, real charge, production deployment, whole-tree commit or push occurred.
