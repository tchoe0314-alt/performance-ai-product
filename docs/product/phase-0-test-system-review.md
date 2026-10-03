# Phase 0.3 — Final local validation and closeout review

Recorded October 3, 2026. **Local test-system deliverables verified; formal platform disposition remains open.** This is not overall Phase 0 completion, deployment approval or pilot readiness.

## Evidence and exact scope

- Repeatable validation at clean tracked revision `678556e4d9a22ba5354e044cbdfe24fdd4cc70bc`: **nine gates passed**. Six backend selections: **360 tests passed**; frontend lint/typecheck/isolated production build passed; critical browser selection: **132 passed, zero skipped**; real-local authentication/persistence/export/drainage selection: **three passed, zero skipped**. Report: `/tmp/civora-phase03-closeout.nxgVVs/validation.json`. Before/after tracked revisions match, with no tracked changes. External evidence remains false and construction release disallowed.
- Full website collection at that revision initially finished **382 passed, one failed, 13 skipped**, 5.6 minutes. Failure: mobile WebKit emitted an access-control page error for the isolated concept calculation request during the reload scenario. Five unchanged repeats passed; intermittent behavior is not a disproven failure or a confirmed root-cause diagnosis.
- Repaired only the completed-calculation reload test's readiness: after width changes, wait for the current calculation's stale flag to clear before saving/reloading. No error assertion was removed, filtered or swallowed. **Ten mobile WebKit repeats passed**, 29.8 seconds; targeted lint passed.
- Fresh complete Chromium-selected collection after that test-only repair: **383 passed, 13 skipped, zero failures**, 396 tests, three workers, 4.3 minutes. Report: `/tmp/civora-phase03-closeout.nxgVVs/full-browser-final-report/index.html`. The single tracked test edit has binary-diff SHA-256 `ec71b70a9a74ba85d9038a633b777b995b34d4ba63903aa7b240a90b305009ef`, observed during and after the run. Subsequent evidence documentation does not change application behavior.
- Website/API targets: `http://127.0.0.1:3042` / `http://127.0.0.1:18882`, disposable accounts/storage. Served build: `zdZEGj9jzqkXDFvHfap1C`. Isolated validation build: `VgzKJVszB6GmAyeCkpDjK`. These are different artifacts; the runner explicitly does **not** attest served/deployed artifact identity. Runtime application/public/API/service sources are unchanged since `6ba7cb2e`; later work repairs tests and validation configuration.
- Retained complete backend baseline: **1,859 tests plus 78 subtests passed**, 44 warnings, at the previously recorded `ed45da3c` inputs. Subsequent runner/manifest changes have scoped configuration tests and the fresh six backend gates above. This pass did not rerun the entire backend collection at the latest head; do not label the retained baseline as a new complete run.

## Roadmap requirement review

| Requirement | Local evidence / disposition |
| --- | --- |
| Interrupted candidate-solver tests | `phase0-candidate-contract`: whole-group protection, atomic/snapshot-bound approvals, hard conflicts, requested count, full-pool reranking, invalid geometry, missing boundary and parking shortage. Passed in the current critical/full selections. Bounded modeled search only, not global optimum or engineering certification. |
| No hard-coded alternative names | UI regressions identify option controls through stable identifiers and changed-object metadata; solver comparisons use IDs, metrics and source snapshots. No matches for the inspected old Conservative/Balanced/Aggressive/numbered-name patterns. |
| Stale selectors and stable test IDs | Repaired visible-menu/drawer flows, map fixtures and asynchronous readiness. Current full selection passes; unsupported targets are not force-clicked or silently accepted. |
| Complete suite together | Prior full backend baseline, affected backend checks, fresh complete website selection and all nine repeatable gates are recorded separately above. Thirteen website skips remain explicit. This is not every browser/provider/hosted scenario. |
| Regression coverage | Includes image-failure preservation, save races, stale proposals, protected replacement, native geometry, map coordinates/pan/lock and drainage replay geometry. |
| Test categories | `phase-0-test-matrix.md` distinguishes unit/contracts, backend integration, controlled-response browser workflows, real-local API workflows and external/hosted checks. |
| Release-critical selection | Named browser gate now includes map/preview/error-state regressions; opt-in real-local gate includes save/reload/downloads and drainage outcomes. |
| Repeatable command | `backend/scripts/run_end_state_capability_validation.py`; stable-source guard, calling Python runtime, explicit local origins, opt-in hosted checks and external truth flags. |
| External prerequisites | Test matrix documents credentials, Mapbox build/process configuration, source fixtures, approved targets and environment limitations without embedding credentials. |
| Failure/recovery | Invalid/missing detection success, failed providers, invalid source geometry, approval/stale/race rejection, blocked calculations, owner isolation and unresolved drainage warnings are exercised. |

## Unresolved platform and release conditions

1. **Firefox:** the local graphics/content process cannot launch reliably. Exact-candidate Linux verification or an explicitly approved pilot support limitation is still required. A specific founder question has been sent; no scope waiver is assumed.
2. **Pending-request navigation:** completed-calculation reload now passes, but this does not verify arbitrary reload while a request is still in flight. The initial WebKit error and the earlier main-workspace download/protocol discrepancy remain recorded separately. Native refresh results do not erase protocol failures.
3. **Thirteen website skips:** one Firefox runtime case and twelve credential/target/legacy opt-in cases. There are no remaining skips for the repaired map pan/select, lock, pointer conversion or delayed-save scenarios. Hosted-named tests that ran against localhost are local evidence only.
4. **Release/pilot evidence:** exact deployed frontend/API identity, authenticated hosted workers/persistence/exports, container evidence, hosted migration/recovery/backup/rollback and independent source/CAD/engineering/provider evidence remain under their existing release/pilot owners. No deployment, purchase, plan upgrade, paid resource creation or CI dispatch occurred.

The local test-system repair can support the next independent Phase 0.4 maintainability work. Formal Phase 0.3 platform closeout remains open until its disposition is accepted or verified; Phase 1 still waits for all Phase 0 exit criteria. The next code-maintainability review should focus on the 6,310-line dashboard, 3,180-line preview and remaining command/state adapters, without a broad schema rewrite or changing completed behavior.
