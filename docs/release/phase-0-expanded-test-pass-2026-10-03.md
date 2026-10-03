# Expanded Phase 0 verification — October 3, 2026

**Local regression passed; a live mobile save overwrite was confirmed. Not an all-environment pass or release approval.**

## Proven scopes

| Area | Actual result | Evidence and limits |
| --- | --- | --- |
| Full backend collection | **1,867 passed, 78 subtests passed, 44 warnings**, zero failures; 604.32 seconds | `/tmp/civora-phase05-full-backend.xml`; clean tracked `c12a0098cc19578e190c2d9be948882534ebd067`, disposable storage `/tmp/civora-phase05-all-backend.cm0xrC`, AI/image providers disabled. Warnings are retained, not suppressed. |
| Full selected local website collection | **737 passed, zero failures, 13 skipped**, 10.3 minutes, two workers, no automatic retries | `/tmp/civora-phase05-correct-origin-report/index.html`; Chromium collects the complete suite, while desktop WebKit/mobile Chromium/mobile WebKit run opted-in subsets. This is not every test on every browser. Includes local persistence, exports, long-session/two-user isolation, failure/recovery, map and native geometry cases. |
| Engineering/reference-file regression | **10 scenarios, eight reference-file scenarios, 46 comparisons, zero comparison failures** | `/tmp/civora-phase05-engineering-reference.json`; deterministic expected-versus-actual checks, not independent engineer acceptance. |
| Bounded runtime/memory load checks | **Six scenarios, two iterations each, 12 runs passed** across two reports | `/tmp/civora-phase05-bounded-load-report.json` (five scenarios/ten runs) and `/tmp/civora-phase05-roadway-load-report.json` (roadway/two runs). Existing thresholds were not relaxed. Not production-scale concurrency or capacity certification. |
| Runtime monitoring soak | **20 samples, zero sampling failures, queue-monitoring ready** | `/tmp/civora-phase05-runtime-soak.json`; authenticated disposable localhost runtime, approximately 20 seconds. Not a hours/days-long production soak. |
| Seeded local recovery | **All 15 tables, content/schema hashes and integrity checks matched** | `/tmp/civora-phase05-seeded-recovery-report.json`; isolated synthetic user/project with native building geometry. Does not certify the previously oversized test database or hosted Postgres/files. |
| Code rollback retrieval | **Passed**, clean isolated prior checkout and successful verification | `/tmp/civora-phase05-current-code-rollback.json`; current `c12a0098`, prior `c273e2e3`. Not provider rollback, data downgrade or compatibility proof against new customer writes. |
| Live public Chrome workflow | **One passed** | `/tmp/civora-phase05-live-public-report/index.html`; panels, drawing controls, 2D/3D and mock concept imagery/truth wording. No actual paid AI provider execution. |
| Live guarded authenticated workflow | **Desktop Chromium and WebKit passed; mobile Chromium and mobile WebKit failed** | `/tmp/civora-phase05-live-safe-report/index.html` and `/tmp/civora-phase05-live-safe-devices-report/index.html`. Four separate synthetic accounts/projects; generation, imagery, exports and writes outside each test project were guarded. Customer projects were untouched. |
| Identical overwrite scenario on local candidate | **Four passed**, zero failures/skips, 10.6 seconds | `/tmp/civora-phase05-identical-local-repro-report/index.html`; same edit/backend-save/reload/dimension assertions as the live failures. Only the approved target adapter changed; no added completion wait or weakened assertion. |

These scopes overlap. Do not sum them into one unique total or treat local/provider-mocked cases as live evidence.

The website artifact is `.next-phase05-release-identity`, build ID `lcjmEohaVPOMwXI1gN3Jz`, with static revision `34d1cfecf865658773c9b4e16a8016370a8482f1`. Application source is unchanged from that build; `c12a0098` adds documentation only. Final browser checks use localhost:3042 and API localhost:18882. The long-running disposable API is not independently attested as a newly rebuilt hosted candidate; its unchanged auth/project/export/engineering endpoint paths provide local functional evidence, while full backend tests execute the current checked-out sources.

## Confirmed live mobile overwrite

On each mobile configuration, a synthetic building started at X=100; editing it to X=125 produced a successful save and API readback. A later browser-originated save sent the older X=100 layout; refresh then read/displayed X=100. Trace inspection extracted only timestamps, methods, response status and the synthetic object's X position, not credentials.

- Mobile Chromium: POST X=125 at `2026-10-03T23:35:31.924Z` returned 200; a later POST X=100 at `23:35:32.445Z` had an aborted response, but the subsequent GET read X=100; another X=100 save returned 200 after reload.
- Mobile WebKit: POST X=125 at `23:35:53.384Z` returned 200; POST X=100 at `23:35:53.551Z` returned 200; GET at `23:35:54.012Z` read X=100.

This is confirmed data overwrite in the currently deployed version, not just an inspector display discrepancy. The local candidate's existing save/restoration fixes pass the identical guarded scenario on all four configurations. That is meaningful regression evidence, **not proof that the live bug is fixed**: the candidate remains undeployed. Reverify both mobile cases against the exact approved deployment before clearing this issue. Raw traces may contain disposable authentication data; keep them private locally and do not commit/publish them. Synthetic live test records were retained in their isolated accounts; no account/project deletion was performed.

To replay the same guarded scenario locally, use `CIVORA_LOCAL_SAFE_TESTS=1` with explicit HTTP localhost website/API origins and disposable storage. The adapter rejects credentials, paths, non-loopback origins and missing explicit ports. A deliberate localhost-website/production-API pairing skipped before any test API writes, `/tmp/civora-phase05-rejected-target-report/index.html`. This expected rejected-target check is separate from the 13 exclusions in the full collection. Production remains opt-in and fixed to the existing exact live website/API pair. Local origin validation alone cannot prove storage isolation.

The target-only test/config adapter was added **after** the full local collection; the unchanged application artifact then passed the four affected exact-reproduction checks, scoped lint and type checks. Do not claim the earlier full collection executed this newly enabled local scenario. Whitespace checks pass, and unrelated user artifacts remain untouched.

## Security results

- Full frontend app/library/browser-test lint and type checks passed. Production build evidence is retained from the unchanged identity artifact.
- Production npm dependencies: zero reported vulnerabilities. Full development audit: five high affected nodes from the single unpatched braces chain, unchanged; unsupported ESLint-major lifecycle remains tracked. Neither finding was waived or silently downgraded away.
- Declared backend pins, installed disposable backend runtime and declared optional renderer/imagery/training pins: no known vulnerabilities reported by the audit tool. Declared optional pins do not certify resolved provider environments or functionality; the hosted environment was not audited.
- Installed backend runtime dependency consistency check passed.
- Full static Python scan across `backend` and `scripts`: zero medium/high findings, **90 low findings**, 12 existing suppression annotations. This is not an all-severity-clean claim or complete application security certification.

## Retained failures and environment corrections

An initial full browser attempt used localhost:3043 while the disposable API allowed only localhost:3042. An explicit preflight returned HTTP 400, `Disallowed CORS origin`. Authenticated PDF editor, exports and persistence failed; the run was stopped: **341 passed, three failed, two interrupted, ten skipped, 394 not run**, 4.9 minutes. Report `/tmp/civora-phase05-full-browser-report/index.html` remains failed/interrupted evidence. The same built artifact was moved to the permitted local port; preflight returned HTTP 200 with the exact allowed origin. No production CORS setting or application source was changed. The fresh corrected run is the 737-pass result above.

Both fresh Firefox launch attempts failed before navigating to Civora: headless SWGL/framebuffer plus sandbox-extension errors; visible mode sandbox/GPU-helper errors. Each attempt had a 15-second launch timeout. Neither is passing Firefox application evidence. Security/sandbox protections were not disabled to obtain a pass.

To retain room for tests, only four explicit regenerable compiler cache directories were removed: `.next-phase05-release-identity/cache`, `.next-phase03-closeout/cache`, `.next-phase0-detection-failure-guard/cache`, `.next-phase0-download-navigation/cache`. Source/project/database data, built runtime artifacts and reports were preserved.

## Not runnable or not certified here

1. **Linux Firefox and actual backend containers:** Docker/Podman and a CI dispatch client are unavailable locally. Existing Linux workflows remain the route to exact-candidate proof; no CI job was dispatched, paid runner created, or platform exclusion approved.
2. **Exact-candidate live release:** Read-only canary `/tmp/civora-phase05-all-public-canary.json` confirms public availability, auth guards, exact-origin CORS and reported recovery readiness, but the live API reports `597c46a3353f` and the website lacks candidate identity. Version mismatch blocks release verification. No deployment/push occurred.
3. **Current hosted restore/migration/provider rollback and production dependency inventory:** The historical August 8 drill and reported recovery status do not replace current isolated recovery evidence. No production data restore or backup/billing configuration change was made.
4. **Real external map/imagery/AI providers and target CAD tools:** Local integration/error/geometry/export checks passed within their scopes; no paid provider generation, target Civil 3D acceptance or provider-rights certification was performed. External tools/provider environments and permitted inputs remain necessary.
5. **Independent engineering review and production-scale capacity:** The automated reference/load checks are useful, but licensed reviewer comparisons, real pilot survey/profile/foundation inputs and an agreed hosted concurrency/dataset envelope remain required. Do not claim full capacity or construction readiness.

Highest priority: preserve the mobile overwrite regression, finish exact-candidate infrastructure gates, request explicit deployment approval, then rerun safe mobile persistence plus the remaining approved hosted workflows. Phase 0.3/0.5 stay open and Phase 1 has not started. No purchase, deployment, push, customer-data mutation or new cloud resource occurred.
