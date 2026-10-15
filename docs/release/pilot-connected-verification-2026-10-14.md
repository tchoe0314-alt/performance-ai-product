# Connected pilot verification — October 14, 2026

This follow-up does not close the entire pilot-to-customers plan. Local software proof, hosted deployment proof and independent acceptance remain different gates.

## Implemented in this pass

1. Hardened the hosted operational-report builder against string/numeric success values. Malformed imported support, backup and ownership flags now remain false; regression tests feed the resulting report into release readiness to prove the values cannot be laundered into approval.
2. Applied a shared validator to imported backup facts. Both hosted and release reports require boolean configured flags, integer retention of at least seven days, and a timezone-qualified restore timestamp no more than 366 days old or five minutes in the future. A `ready` label or nonempty invalid timestamp cannot waive those checks. This validates recorded evidence; it does not perform or independently approve a provider restore.
3. Added `export_manifest_v1` to completed current-drawing export jobs, recording saved canonical revision, project ID, units, exported object IDs, drawing-only scope and exclusion of calculations/construction approval. Existing artifact paths remain unchanged.
4. Extended the real website persistence test through actual DXF export after direct editing, equivalent chat editing, Undo/Redo and reopening. The reader verifies feet units and the saved building origin `[175, 120]`; the job manifest must match the exact checkpoint. Only expected export/revision audit records may change; other canonical/compatibility fields, revision token and calculation results remain unchanged.
5. Ended open/failed PostgreSQL transactions explicitly when returning connections to the pool. This matches the pool's previous automatic rollback semantics without invoking its warning path on every read. Failed reset closes the connection before returning it for discard. Tests verify ordering, idempotent return, idle/unknown handling and failed-reset disposal. This is not a proven fix for the hosted gateway failure.
6. Preserved the existing short deployment `commit_sha` field while adding `full_commit_sha` to API deployment/health metadata. Hosted evidence prefers the full field, allowing the exact release gate to match a real full commit rather than forever rejecting the API's shortened identity. Tests verify an exact match is accepted and another commit with the same short prefix is rejected. Missing commit metadata remains unknown; a build label does not fabricate it.
7. Updated the existing demo recorder for stage-based navigation and configurable localhost/output paths. It now requires the building inspector/edit to exist, accepts any displayed dependency proposal and verifies the changed width before displaying a success caption. It refuses non-localhost destinations. Existing investor artifacts and videos were preserved; the verified new recording is `/tmp/civora-workflow-demo-verified-20261014.wuqh4a/civora-workflow-demo.webm` (1.7 MB). This is a seeded local demonstration, not a real customer project or measured productivity evidence.

## Verification completed

- Existing focused Chrome workflow group: 18 passed (38.6 seconds), including source overrides, geometry alternatives, viewer protection, stale-result exclusion, current drawing PDF/DXF downloads and metric units.
- Extended canonical persistence/export group: two Chrome checks passed (5.5 seconds); six checks passed across desktop WebKit, mobile Chromium and mobile WebKit (22.8 seconds).
- Dependency/history/save-failure/two-tab website group: nine Chrome checks passed (19.5 seconds).
- Canonical state, execution/freshness, save queue, history and dependency contract group: 67 passed (814 milliseconds). These are software contracts, not 67 additional interactive browser workflows.
- Worker queue, startup, combined runner and health group: 67 passed (31.40 seconds).
- Object/editing and delayed-save panel navigation group: five Chrome UI checks passed (7.7 seconds), with mocked backend responses; these are not hosted integration evidence.
- Final affected backup/release/database/export tests: 66 passed, 67 subtests, 33 dependency deprecation warnings (3.02 seconds).
- TypeScript validation and targeted test lint passed. No application frontend source changed, so no new production build is claimed; website tests used the existing production build against the restarted local API.
- Final targeted Python static analysis of five changed application/database/backup files: zero low/medium/high findings; two existing narrow SQL suppressions in backup restoration remained reported. This is not a security certification.
- Runtime dependency compatibility: 66 installed packages compatible.
- Fresh frontend production dependency audit: zero known vulnerabilities. Development audit still reports five high-severity affected nodes in the braces/micromatch/fast-glob/Next lint chain. Its proposed forced downgrade to Next lint configuration 14.2.35 is incompatible with the installed 16.3.8 baseline; no forced downgrade or waiver was applied.
- Commercial benchmark executed with paid providers disabled: automated checks passed, no failed comparisons; independent review remains pending. `/tmp/civora-commercial-benchmark-20261014.json`; reviewer worksheet `/tmp/civora-commercial-review-20261014.json`. Revision correctly remains dirty.
- PDF skill used for read-only visual inspection of both pages of the actual current-drawing website export. Disclosure text, sidebar and title block are readable; the saved drawing excludes calculations and declares fit-to-page rather than measurement scale. Object labels at the small overview scale remain a visual-polish limitation, especially the road label over the island; this inspection does not claim dense-label collision avoidance or external CAD acceptance. Rendered review images: `/tmp/civora-pdf-review-20261014.eqzY3d/page-1.png` and `page-2.png`.
- Demo script syntax check passed and an actual recording completed after the navigation repair. Review/final screenshots were visually inspected. A subprocess guard probe confirmed a hosted target is rejected before launching a browser. The first capture failed on the obsolete `Draw` button; its partial video was retained in a separate temporary folder, not presented as a successful demo.

Test groups overlap and must not be added as distinct case counts. One expanded browser test initially failed because it incorrectly expected export audit history to remain empty. The test was corrected to require the audit append and exact preservation of all other inputs; the failure artifacts were retained. No production behavior was relaxed to make it pass.

The first full backend sweep passed 2,177 tests, 178 subtests, 56 warnings in 424.54 seconds. Because source fixes were made during that run, it is an intermediate sweep, not the final settled-source proof. A second sweep was deliberately interrupted after 922 passing tests (108.70 seconds) to implement the subsequently discovered full-commit identity fix; it is not counted as a full pass. The API/hosted/release identity regression group then passed 52 tests and 63 subtests. A final settled-code sweep was started with duration reporting and `/tmp/civora-final-candidate-backend-20261014.xml`; its completion result is recorded separately below.

### Final settled backend result

2,185 passed, 195 subtests passed, 56 dependency deprecation warnings, zero failures, 410.29 seconds. The machine-readable result is `/tmp/civora-final-candidate-backend-20261014.xml`. No backend source changed after this run started. This does not mean every website interaction or hosted service was tested.

The slowest assisted/manual test took 54.44 seconds; golden scenario suite 38.08 seconds; two multi-building export/planning cases 34.70 and 34.49 seconds. These timings identify remaining performance work, not certified operating limits. The connected synthetic firm workflow test passed in 4.58 seconds; its name does not make it real customer acceptance.

The final static scan including API code found zero medium/high findings and one low finding; two preexisting narrow SQL suppressions remained reported. The earlier five-file scan's zero-low result must not be generalized to all backend files.

Local aggregate readiness still correctly returns all release permissions false with ten missing formal technical records, six operational, four human and three billing gates in the local invocation. Missing local records/configuration do not prove the corresponding existing hosted services are absent. Report: `/tmp/civora-readiness-20261014.json`.

## Read-only hosted observations

The existing API deployment details show one replica in `us-west2`, Dockerfile build, `/api/health` healthcheck, 300-second healthcheck timeout and restart-on-failure with ten retries. Current deployment logs show recurring PostgreSQL pool rollback warnings. No provider settings, variables or deployments were changed; secret values were not inspected. The earlier login 502 upstream connection closure remains unresolved and has not been reproduced or attributed to the warning path by this pass.

## Remaining connected-plan gates

| Gate | Still needed |
| --- | --- |
| Source/release baseline | Review intended changes and establish a clean candidate from the inherited large dirty tree; passing tests do not create a release identity. |
| Commercial design loop | Complete calculated-system/quantity/sourced-pricing workflow evidence. The connected drawing-only proof does not claim this. |
| Reliability/performance | Representative workload and concurrency limits, resolved hosted login investigation, and Firefox evidence or an explicitly accepted browser policy. |
| Hosted release | Specific candidate/target/rollback approval, deployment and authenticated post-deploy worker/artifact/tenant checks. Historical provider restore evidence exists; this pass did not rerun it. |
| Professional acceptance | Target jurisdiction, rights-cleared real site, authorized engineer/CAD reviewers and attributable findings. Synthetic benchmarks cannot close this. |
| Customer operations/payment | Approved scope, pricing/policies/support ownership and verified existing payment implementation. Repository billing is status/guard infrastructure, not verified customer checkout. No real charges performed. |
| Pilot/investors | Authorized partner, measured real usage and permissioned customer evidence; financial/company/IP facts and an accurate investor package. No invented traction or professional/legal approvals. |

No deployment, purchase, real payment, external outreach, customer-data mutation, blanket commit or push occurred. Existing user work was preserved. This pass created only disposable local test data and artifacts; hosted inspection was read-only.

Existing September 30 investor deck, brief, model and demo files were found under `investor-kit/`; their existence is confirmed, but their financial/legal/customer claims have not been revalidated in this pass. Do not describe them as absent or as verified investor-ready materials.
