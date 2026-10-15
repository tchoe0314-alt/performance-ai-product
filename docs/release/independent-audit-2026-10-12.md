# Independent Civora audit — October 12, 2026

## Scope and authority

Requested independent tests and an honest assessment of remaining work. This pass changes test coverage and audit documentation only: no application fixes, deployment, purchases, hosted account writes, or release approval. Inherited application changes are preserved.

Candidate: `codex/phase-0-integration`, baseline HEAD `df044329`, with the inherited working tree. A commit alone does not identify all tested application changes. Production-mode local frontend uses `.next-phase22`, `http://127.0.0.1:3050`; disposable local backend uses `http://127.0.0.1:18886`, Python 3.11.15 and SQLite under `/tmp/civora-phase31-audit.9PalJd`. Final backend tests use a separately recreated environment at `/tmp/civora-clean-backend-audit.oiDDyN/runtime`, installed from the exact repository backend/test requirements. AI/image providers are disabled. Synthetic local accounts are not customer accounts. Local results are not deployed-version or engineering certification.

## Execution ledger

| Check | Result |
| --- | --- |
| Lint, concept-source parity, TypeScript | Passed; two inherited unused/dependency lint warnings |
| Installed Google Chrome 152.0.7977.64 | Passed five workspace stages, no page errors, no horizontal document overflow at 1280×900 |
| Live public site, installed Chrome | Workspace loaded with HTTP 200 and no page exceptions. Five-stage candidate smoke failed because the deployed page has the older Setup/Draw/Generate navigation and zero new stage elements. Confirmed by DOM inspection and screenshot; not an authenticated hosted regression pass. |
| Full backend, 2,038 collected tests | Final clean-environment run: **2,038 passed, 128 subtests passed**, 44 warnings, exit 0, 372.47 seconds. Earlier batches/interrupted attempts are retained below; they are not substituted for this final pass. |
| Broad Chromium, 447 selected checks | Initial run: 440 passed, four failed, three skipped. All four failed cases passed unchanged on targeted reruns. Excludes hosted, phase-specific, long-session and heavy drainage packs. |
| Phase 0–3 Chromium milestone pack, 160 selected checks | Initial run: 155 passed, five failed, zero skipped. Four recovered unchanged. Quantity/reload case reproduced a navigation-helper readiness race and passed after the test-only repair. Disposable local persistence enabled. Excludes object/export packs already checked separately and credential-gated runtime suite. |
| WebKit, mobile Chromium and mobile WebKit, 183 selected checks | Initial run: 170 passed, one failed, twelve skipped. Mobile-WebKit denied-cache/reset case passed unchanged on isolated rerun. Authenticated/WebGL-gated skips are not passes. |
| Independent contract/geometry probes | Four passed, three failed; same result reproduced |
| Real website requirement/save probes | Two failed: zero fixture and matching positive-value control. Persisted requirement values retained in both. |
| Real local website object/export pack | Three initially passed (PDF/DXF download and owner isolation; custom types/reload; line combine/edit/uncombine). Nested-group case failed on a local API connection reset, then passed unchanged on rerun through move/hide/undo/redo/nesting/ungroup. |
| Test-only navigation readiness regression | Two passed: delayed new-stage mounting and compatibility with the older deployed navigation |
| Final combined independent acceptance pack | Eleven cases: six passed, five failed, 35.8 seconds. The five failures are the two zero-input builder cases, the proposed-but-unimplemented safe export mode, and both sparse-project saved-header cases; these are not five independent bugs. |
| Real local drainage and two-user/two-window pack | Three passed: six drainage scenarios with explicit Apply outcomes/replay deduplication; 40 concurrent project writes with ownership isolation; 24 two-window navigation cycles and six preview/quality cycles |
| Firefox attempt | Browser launch failed before application assertions: headless graphics/framebuffer and sandbox-extension errors, then a 180-second launch timeout. Firefox application behavior remains unverified. |
| Python installed-dependency scan | Clean recreated environment: scanner exited 0, zero reported known vulnerabilities; 66 installed packages pass dependency compatibility checks and critical GIS/database imports. Old-environment vulnerability scans alone did not reveal its missing metadata/files. |
| Frontend production dependencies | Two high affected package nodes (`sharp`, `next`) trace to one Sharp advisory; not two independent vulnerabilities |
| Frontend full dependency scan | Seven high affected nodes: two in the production image-library chain and five in the development lint/glob chain. Zero critical reported. |

Passing counts from previous reports are not substituted for this run. Zero/save-feedback website probes were repeated under reduced load: both still failed, while saved values remained intact. The existing selected browser/workflow checks comprise 779 successful case/browser combinations after recovery across the 447-case broad, 160-case milestone, 183-case device and four-case object/export packs; fifteen remain skipped. The separate drainage/concurrency pack adds three successes, and the two helper regressions add two. Cross-engine repeats of pure contracts are not distinct user workflows. New acceptance failures and the failed Firefox launch remain explicitly open.

## Confirmed findings

### 1. High-priority image-processing dependency patch

Installed overridden `sharp@0.35.4` is below patched 0.35.5. Advisory: [GHSA-wq5f-xc86-pv6w](https://github.com/advisories/GHSA-wq5f-xc86-pv6w). The underlying SVG-processing vulnerability has runtime-dependent exposure, including affected glibc Linux conditions. This scan does not prove exploitation or that the deployed server has those exact conditions. No malicious payload was sent.

Next step: update the pinned image library, verify the installed dependency graph, image behavior and production build, then rescan. The fresh full npm scan also reports a high-severity development lint/glob chain through `braces`, `micromatch`, `fast-glob`, the Next ESLint plugin and ESLint config. Resolve it separately with compatibility checks. Seven affected nodes across these chains are not seven independent vulnerabilities.

### 2. Explicit zero requirements do not survive the live field projection correctly

`buildDashboardManualFields` uses a strictly-positive parser for setback and required parking. An explicit `"0"` becomes omitted, while blank values correctly stay unspecified. Independent tests fail for both zero fields. The real website opens a persisted zero setback as “Not set / Unknown,” although the backend stored zero and retained it after the tested unrelated project-name save.

**No database loss is established by that save probe.** This is a persisted-versus-live/submit-model discrepancy. It can change which inputs are supplied for calculation and misrepresent the active brief. The precise resulting engineering calculation is not certified by these probes.

Next step: distinguish blank, valid zero, and invalid negative values for fields that permit zero. Do not weaken positive-only dimensions globally. Add UI/save/reload/calculation-request regression tests.

### 3. Saved-header feedback needs investigation

Both the zero-requirement fixture and the matching positive-value control successfully persisted a project-name change but did not reach stable “Saved” feedback within the 15-second assertion window. This is not exclusively a zero-value problem. The positive setback was correctly displayed and both saved requirement values remained intact. Fixtures are sparse API-created canonical projects with an empty object list and no embedded project name; coverage of fully populated website-created projects is separate. Reconcile accepted save state and live projection for restored sparse/legacy projects before calling the header reliable. No database loss was established by either probe.

### 4. Missing safe preliminary export mode

Authoritative roadmap Decision 10 permits preliminary exports with disclosed stale calculations, provided geometry/units/representation are safe. The current export blocker universally vetoes staleness and ignores review scope. The new acceptance probe requests a **proposed**, not currently implemented, current-geometry-only mode with explicit preliminary acknowledgment and disclosures; it fails.

This is an unfinished workflow, not permission to export stale results as current. Implement a separate safe current-geometry representation with revision, timestamps, stale-system summary, assumptions and warnings. Preserve blocking for unknown units, corrupted geometry, failed coordinate conversion, security/data-integrity failures and misleading representation. Existing stale-result safety tests should remain intact.

## Additional independent checks that passed

- 150 supported road radius/width combinations: finite geometry and analytic tangency at the bulb/fillet transition.
- Twelve feet/meters and rotation combinations at large coordinates: local/world frame inversion and exact canonical JSON parameter/geometry round trips.
- Seven physical obstacle types: hiding them does not remove their collision assessment.
- Blank setback and parking remain unknown rather than silently becoming zero.

These checks validate software behavior over stated fixtures, not municipal standards, arbitrary inputs, utility/foundation clearances or site feasibility.

The drainage matrix verifies completed jobs, explicit Apply outcomes and duplicate-request handling, not universal design validity. Uphill slope adjustment still returned `SLOPE_ADJUSTMENT_FAILED` with zero valid pipe runs; inlet insertion cleared under-collection but retained orphan/no-flow-path issues. Four scenarios intentionally test calculation/job behavior without applying an autofix. A case named “Valid control” in the legacy test file is not independent engineering approval. The legacy `phase5-autofix` filename does not establish completion of roadmap Phase 5.

The two-window check is a bounded interaction stress test (the successful run lasted roughly eleven seconds), not an hours-long production soak. Forty concurrent local SQLite requests and two users do not prove multi-replica hosted database capacity.

## Run failures requiring classification

- The large browser batches overlapped a period of severe host load and long timing interruptions. Three cases in different batches each took approximately 15–16 minutes despite a two-minute configured timeout; after that interval, normal rendered cases returned to roughly 1–8 seconds. Host suspension/resource interference is a possible explanation, not a proved website defect. Those results cannot establish reliable production latency or capacity. All failed cases must be rerun unchanged with reduced concurrency.
- Additional broad timeouts: multi-select/bulk utility-hide, native cul-de-sac/pipe editing, and new-project preview switching. They passed unchanged on rerun. Milestone timeouts in canonical edit/save/reload (failed while setting up the page), two-tab replacement, compact environment controls and mobile-width brief summary also passed unchanged on rerun.
- Quantity Ask/Follow reload failed again in isolation. The test helper selected legacy navigation before the refreshed workspace mounted, then waited for a nonexistent old Draw button even though the new Explore interface was present. Added a visible-workspace readiness assertion before detecting navigation version; the original quantity/calculation/save assertions remain unchanged and passed. Two dedicated helper regressions also passed. This repairs test reliability, not application functionality.
- Three backend semantic-vision tests reproduced `ModuleNotFoundError: rasterio.features`. The same-version installed distribution's RECORD listed `rasterio/features.py`, but the file was absent in the owned disposable runtime. Reinstalled `rasterio==1.4.3` with no dependency upgrades or repository changes. These cases passed in the final clean full run. This is a local environment-integrity finding, not evidence that the hosted vision runtime is broken.
- The next full pass revealed missing version metadata for the installed Psycopg package and missing Pyogrio GDAL data files. Both reproduced in isolation. Restored `psycopg==3.2.9` and `pyogrio==0.11.1`, matching `requirements_backend.txt`, without dependency upgrades or repository changes. All 37 affected database/GIS/vision/dense-utility checks then passed. Dependency vulnerability scans do not replace installed-file/import integrity checks; these local failures do not establish broken hosted PostgreSQL or GIS processing.
- A broader compatibility check still reported 58 missing/incomplete metadata entries in the old disposable environment. Recreated a separate environment from `requirements_backend.txt` plus `requirements_test.txt`; all 66 packages passed compatibility checks, and real Psycopg version, Rasterio polygonization and Pyogrio/GDAL imports were confirmed. Stopped the redundant old-environment test run and used the clean environment for final backend evidence. No repository dependency versions or hosted environment were changed.
- Backend provenance: first completed batch had 2,034 passes/four failures; the next had 2,036 passes/two failures; all 37 directly affected checks passed after local repairs. An initial long-stalled attempt and a subsequent redundant old-environment attempt were interrupted. The final fully recreated environment passed all 2,038 tests in one uninterrupted batch.
- A 60-second diagnostic timer in an assisted-mode test captured active alternative generation inside coordination snapshot copying (`coordination_state._bounded_copy` / `_copy_segment_list`). The same copying/restoration hotspot triggered a diagnostic in the clean environment with no competing browser jobs. This is a reproducible performance-profiling lead, not a proved deadlock or universal latency measurement. The run continued advancing; large-survey/candidate-generation costs must be measured and bounded before asserting full capacity.
- Broad visualization-off test expected exactly one lifetime job-status poll and received two. Trace shows the second poll started before the actual Off click (network 1,231,877 ms; click action 1,232,720 ms), with no subsequent job polls in the trace. It passed unchanged on rerun. This supports a timing-sensitive assertion, not proof that polling continued after switching Off. Preserve the initial failure; improve the test later to assert no new polling after Off rather than a fixed lifetime count.
- Nested-group website test reached its later move/undo/group operations, then a read of the synthetic local project failed with `ECONNRESET`. Backend remained healthy (HTTP 200). The full case passed unchanged on rerun, including nested grouping and ungrouping; no reproducible grouping implementation bug is established by this connection reset. Local transport instability remains recorded.
- Initial backend test process stopped advancing near 54%; a native sample captured garbage collection and a waiting thread. The owned test process was terminated; no successful full-suite claim is inferred. The verbose rerun progressed into the controlled benchmark test; diagnostic samples there show active Python execution rather than the same captured wait. Root cause of the first stall remains unresolved.

## Candidate versus deployed website

Local testing covers newer Phase 2/3 candidate code, not the current public release. The deployed public workspace still presents Setup, Draw, Generate, Review and Deliver. The candidate presents Brief, Explore, Analyze, Review and Deliver, with new brief classification controls. Do not tell users those candidate changes are already live. Deployment remains a separate verified-release decision, especially while this audit retains failures and the dependency advisory.

## Remaining product and release gates

1. Resolve security and zero-input consistency before the next release candidate; reproduce and correct save-status divergence.
2. Complete Phase 3.3 Edit Brief: direct values/units, priority, sources, confirmations, relaxation, reset to original source and dependent-calculation visibility. Preserve sourced originals and require explicit override for protected values.
3. Complete Phase 3.4 source records/versioning and Phase 3.5 structured missing-information explanations. Existing panels do not establish whole-milestone completion.
4. Implement the safe disclosed preliminary export mode without weakening freshness safeguards.
5. Create a verified, scoped release checkpoint from the inherited large working tree, and test that exact candidate. Do not commit unrelated work indiscriminately.
6. Verify latest authenticated hosted save/reload, configured provider behavior, worker durability and isolated backup restoration against the existing infrastructure. No new paid service is required merely to test locally.
7. Obtain external CAD round-trip checks and independent engineering review with real source/clearance evidence. Synthetic fixtures cannot supply those proofs.
8. Establish representative pilot-size/browser performance and hosted concurrency limits. Parallel local test runs are not a full-capacity production certification.

Maintainability also remains a risk: the main dashboard coordinator is 5,984 lines, and the inherited checkout has roughly 294 changed/untracked entries before these audit additions. Decomposition and scoped commits are useful engineering work, but neither file size nor a dirty tree alone establishes a user-facing bug. Do not combine unrelated edits or substitute refactoring for correcting the confirmed input inconsistency.

The lint pass retained an unused dashboard navigation value and missing save-hook dependency warnings for history/tab-branch callbacks. They are cleanup and stale-closure investigation targets, not proof that the tested undo/save workflows failed. The only existing test helper changed in this pass is `tests/live/helpers/workspaceNavigation.ts`; application source was not edited. Three new independent test files retain failing acceptance probes so these findings cannot be silently declared fixed.

## Reproduction notes

For backend checks, use a complete Python environment installed from `requirements_test.txt` (which includes the pinned backend requirements), verify dependency compatibility and GIS/database imports, then run `python -m pytest tests -q --disable-warnings --tb=short`. Keep paid AI/image providers disabled for this local audit.

For independent browser probes, use the production-mode local frontend and disposable local API, with `PLAYWRIGHT_SKIP_WEBSERVER=1`, explicit localhost `PLAYWRIGHT_BASE_URL` and `PLAYWRIGHT_API_BASE_URL`, and `CIVORA_PHASE0_LOCAL_TESTS=1`. Run `npx playwright test tests/live/independent-audit-2026-10-12.spec.ts tests/live/independent-audit-local-zero.spec.ts tests/live/independent-audit-workspace-helper.spec.ts --project=chromium --workers=1`. The current expected audit result is five red acceptance cases (two zero-builder cases, one unimplemented safe-export mode, and two saved-header cases), not a waived green suite.

Recommendation remains web-first. Successful automated tests improve confidence; they do not establish that nothing is missing, every browser is supported or the product is pilot-ready.

## Final assessment

The existing core has substantial passing software evidence: the clean full backend suite, real local save/reload and object editing, group/combine history, ownership isolation, authenticated PDF/DXF downloads, bounded concurrency, and selected desktop/mobile layouts. A test-helper race and incomplete local dependency installations were repaired; application source was not changed.

The next product fixes are zero-valid input preservation and honest saved-header feedback; the production image-library patch is also a release priority. Safe disclosed preliminary export remains an unfinished governed workflow. Then continue the master plan's Phase 3.3–3.5. Do not call the candidate bug-free or certify full capacity: heavy candidate processing needs profiling, Firefox did not launch, the public website is older than the local candidate, and latest authenticated hosted behavior/worker recovery/backup restoration, real provider outputs, external CAD round trips and engineering review remain separate gates.
