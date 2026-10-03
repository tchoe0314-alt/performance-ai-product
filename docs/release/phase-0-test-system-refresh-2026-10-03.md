# Phase 0.3 local test-system checkpoint — October 3, 2026

## Verified inputs and results

- Base revision: `c8e888e69f74625d60b9ca44ad583ab8fdb743b5`, integration branch `codex/phase-0-integration`, with scoped tracked runner/configuration/test/documentation changes.
- Stable tracked binary-diff SHA-256 during both complete runs: `85d9b0a982953766bc7efe980dfd09fcce7672828f0d291f6aee59251b8156c9`. Subsequent evidence documentation does not change application behavior. Untracked user files are excluded and preserved.
- Full Python 3.11.15 backend collection: **1,859 passed, 78 subtests passed, zero failures/skips**, 44 warnings, 530.43 seconds. Separate disposable storage: `/tmp/civora-phase03-backend.6GYam0`; JUnit report: `/tmp/civora-phase03-backend.6GYam0/results.xml`.
- Complete Chromium-selected website collection: **381 passed, 15 skipped, zero failures/flaky results**, 396 total, three workers, 4.7 minutes. Preserved HTML report: `/tmp/civora-phase03-full-mapbox-report/index.html`; artifacts: `/tmp/civora-phase03-full-mapbox`.
- Website `http://127.0.0.1:3042`, disposable API `http://127.0.0.1:18882`, production-mode local build `zdZEGj9jzqkXDFvHfap1C`. This is not deployed-artifact attestation.
- Global frontend lint and TypeScript checks passed. Existing public Mapbox token loaded through the website's environment-file loader, retaining explicit process overrides. Credentials were not printed or changed. Deterministic backend AI/image providers remained disabled.

## What changed

The combined browser manifest now includes image failure/recovery regressions. A separate opt-in gate covers real local authentication, owner isolation, geometry save/reload and preliminary PDF/DXF downloads with retained history. Its configuration requires explicit localhost website/API origins and valid ports. This does not attest storage isolation by itself.

Playwright now loads the website's existing environment configuration. The previously skipped map callback and physical-pointer coordinate tests passed individually, in the affected selection, and in the complete website run. No new subscription or resource was purchased.

## Remaining gaps and truthful scope

- Fifteen website skips remain: local Firefox cannot launch its required graphics/content process; hosted-specific credential/target/source/load workflows and staged/legacy opt-in workflows were not enabled; two demo-based map interaction tests skip because the fictional demo has no real geographic anchor. Neither the demo skips nor historical missing-test-token skips establish that Mapbox is unavailable.
- Next local test repair: move map pan/select and map-lock scenarios onto an explicitly map-anchored fixture and replace the misleading missing-token-only skip explanation. Preserve the fictional demo's deliberate lack of a real-world anchor.
- The drainage autofix matrix passed its existing job/UI assertions. Some cases intentionally skip Apply; the second-Apply path can log an unavailable control, and does not assert a deduplicated engineering outcome. Do not treat this run as proof that every drainage fix succeeds or produces a valid design. Add explicit outcome/deduplication assertions and separate job-only coverage from Apply coverage.
- Existing third-party deprecation warnings remain recorded, including parser APIs, Starlette test transport and Pillow image-data access. These are follow-up maintainability items, not hidden test failures.
- Full Chromium selection is not all-platform verification. Exact-revision Firefox/container evidence, real hosted candidate auth/persistence/export/recovery, independent survey/control/CAD/engineering evidence and real rendering-provider validation remain separate gates.

Phase 0.3 remains active; Phase 0 is not release-ready. No deployment, push, plan upgrade, new paid resource or purchase occurred.
