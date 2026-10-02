# Phase 0 test categories and evidence boundaries

Local results apply to the integration checkpoint, not any hosted deployment. The repeatable command's `internal_software_assurance_complete` describes its named gate manifest; it does not satisfy every Phase 0 requirement or eliminate skipped/provider/operational evidence.

| Category | Entry points / examples | What it proves; prerequisites |
| --- | --- | --- |
| Backend unit/domain | Repository-root `tests`; math, canonical entities, importers and candidate/review helpers | Deterministic contracts/reference calculations. Use installed backend/test requirements under Python 3.11, matching the container major/minor runtime. The complete collection also needs Node.js on `PATH` for the hosted-gauntlet script contract tests; their simulated results are not hosted evidence. |
| Backend integration | Application/API workflows, project store/access, queues, backup restore, legacy database migration | Local services and disposable fixtures. Fake Postgres connections do not prove a real hosted migration. |
| Frontend unit/contracts | `canonical-edit-command-foundation`, `phase0-candidate-contract`, geometry cases in `phase0-review-sheet-truth` | Pure functions executed through Playwright's TypeScript harness; these files also contain browser cases, so file selection alone does not mean a unit-only run. |
| Mocked browser workflow | Commercial, drawing, project-race, dependency, candidate and UI regression suites | Visible website behavior with controlled API responses. Does not prove live persistence/auth/provider responses. |
| Real local browser | `phase0-local-persistence`, `pdf-plan-editor`, `rc1-support-data-lifecycle` | Real localhost API/auth/storage with disposable accounts. The persistence test requires `CIVORA_PHASE0_LOCAL_TESTS=1` and rejects nonlocal targets. PDF needs the repository fixture or `CIVORA_PDF_PLAN_FIXTURE`. |
| Full Chromium-selected suite | `npx playwright test --project=chromium --workers=1` | Current broad local regression coverage. Test titles containing “hosted” may execute against localhost; always record actual frontend/API targets. |
| Accessibility/device subset | `rc1-accessibility-cross-browser` across Chromium, WebKit and mobile projects | Fresh-shell accessibility and core navigation only, not all workflows on every browser. Six WebKit/mobile checks passed locally; Chromium subset passed in the full suite. |
| Firefox Linux evidence | `.github/workflows/rc1-firefox-accessibility.yml` | Exact-revision CI browser evidence. Missing/stale CI results remain open; no CI dispatch has occurred in this phase. |
| Container runtime | `.github/workflows/backend-container-runtime.yml` | Fresh/restored-volume API, queue and restricted-user execution. Docker unavailable locally; workflow presence is not a passing result. |
| Hosted authenticated | Hosted auth/source/candidate/load/workflow suites and operational evidence scripts | Requires approved target, scoped test account, `CIVORA_EMAIL`/`CIVORA_PASSWORD` provided through trusted environment, frontend/API URLs and actual deployed revision. Never embed credentials in reports. |
| Map-backed controls | Conditional cases in project-flow, preview and UI friction suites | Requires a usable `NEXT_PUBLIC_MAPBOX_TOKEN` at build time and provider access. These were skipped locally; setting a token is not coordinate-accuracy evidence. Provider calls/costs require authorization. |
| Real renderer/source/CAD/engineering | Separate renderer, survey/control and independent review gates | Requires rights-cleared inputs, provider evidence and qualified external/target-tool verification. Mock imagery and synthetic terrain cannot supply it. |

## Recorded complete runs

- Final local application checkpoint `33c23e34`: complete Chromium-selected website **374 passed, 16 skipped, zero failures**, 390 tests, 10.1 minutes. Repeatable selection **eight gates passed**, browser **107 passed, two skipped**, 3.9 minutes. Clean tracked revision before/after; served/deployed-artifact flags false. Full clean backend at `012dd2a9`: **1,837 passed**, 78 passing subtests, 42 warnings, 549.25 seconds; backend/test inputs unchanged through `33c23e34`. [Exact-checkpoint notes](../release/phase-0-checkpoint-33c23e34.md) preserve target/evidence limitations. Consolidation closeout after this checkpoint changes documentation only.

- Updated placement-state checkpoint `9e1accff`: full local Chromium **368 passed, 16 skipped**, zero failures, 384 tests, 8.7 minutes. Frontend served `.next-phase0-baseline` at localhost:3040; backend was localhost:18880. This run predates restarting the backend to load the health-identity repair. After restart, real local persistence/PDF/account-lifecycle checks passed **three tests** in 6.7 seconds. Hosted/provider skips remain open.
- Full Python 3.11 collection at the same code checkpoint initially finished **1,835 passed, two failed**, 78 subtests, 42 warnings, 418.74 seconds. Both failures were `FileNotFoundError: node` from an overly restricted test-launch `PATH`. Reproduced both failures, then verified both pass with the existing Node runtime available. A corrected complete run is pending; do not call the initial run a pass.
- Corrected complete backend collection: **1,837 passed, zero failed/skipped**, 78 passing subtests, 42 warnings, 370.33 seconds. Backend code unchanged; frontend extraction overlapped the end of the run. This does not certify that later frontend artifact.
- Full local website: **357 passed, 16 skipped**, no failures, 8.8 minutes.
- Clean Python 3.11 backend: **1,831 passed**, no skips, 78 subtests, 42 warnings, 402.52 seconds. Later inventory test passed separately.
- Repeatable end-state command: **eight gates passed**; browser gate **90 passed, two skipped**, 2.7 minutes. No hosted gate was requested; external evidence remains incomplete and construction release disallowed.
- Additional release/inventory/migration runner subset: **22 passed**, seven subtests. Real local persistence/PDF/account lifecycle repeated on the clean backend: **three passed**.

Deprecation warnings are recorded rather than suppressed. Complete-suite success is not evidence that every imaginable input or production load is safe. Keep failure/recovery, geometry/data integrity and owner isolation checks in the critical selection, and require exact-build post-deployment evidence before closing Phase 0.

## Repeatable local use

Run the end-state entry point from repository root using the intended environment:

```text
python backend/scripts/run_end_state_capability_validation.py --list
python backend/scripts/run_end_state_capability_validation.py --output /absolute/isolated/report.json
```

It runs its named backend/frontend/browser selection, not the whole test collection. `scripts/release_regression.sh` is a smaller smoke runner. Record complete backend and browser runs separately. Avoid rebuilding a directory currently served by another process; allocate an isolated `NEXT_DIST_DIR` and explicitly record the artifact used by browser tests.
