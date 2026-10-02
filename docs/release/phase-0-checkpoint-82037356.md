# Phase 0 stabilization checkpoint — 82037356

Recorded October 2, 2026. Integration revision: `8203735648cbec127703df0eab35b50ae52a28e8`, branch `codex/phase-0-integration`. This is a local engineering checkpoint, **not** Phase 0 completion, staging approval, production promotion or external-review sign-off.

## Changes

- Consolidated existing cross-chat website changes with guarded canonical edits, dependency preview controls, alternative comparison and parking feedback.
- Ask mode now previews the whole supported building/parking transaction; rejecting preserves the plan, accepting records one undoable transaction, and stale/cross-project proposals are rejected.
- Alternative search rejects modeled hard conflicts and parking shortages, supports two through ten requested options, reranks the complete valid candidate pool and rejects applying outdated previews.
- Review sheets use current visible object geometry rather than illustrative filler. Empty/invalid geometry is disclosed; rotation, routes and out-of-site coordinates are preserved.
- Fixed mobile drawer/command clearance and logo accessibility; repaired stale fixture/selectors and added regression tests.
- Extracted layout comparison orchestration into a focused hook. Updated pypdf to 6.19.0, verified isolated dependency installation and strengthened regression cleanup safety.
- Added inventory/branch triage, architecture, legacy SQLite migration tests and release/recovery procedures.

## Verified locally

| Evidence | Result / scope |
| --- | --- |
| Full website | 357 passed, 16 skipped, zero failures; 373 Chromium-selected tests against local production frontend. Includes mocked and real-local workflows; not a hosted run. |
| Full clean backend | 1,831 passed, zero skipped, 78 subtests passed, 42 warnings; isolated Python 3.11 backend/test dependencies. |
| Additional release/inventory/migration checks | 22 passed, seven subtests passed; supplements tests added after full-suite collection. |
| Frontend quality | Production build/typecheck and lint passed; zero lint warnings/errors. |
| Installed Python dependency audit | 68 distributions checked; no known advisories after upgrading isolated installer tools. |
| Static security | No medium/high severity-and-confidence findings in backend/scripts scan; not runtime security certification. |
| Recovery | Disposable SQLite restore/content/integrity drill passed; prior code retrieval/focused verification passed. Neither proves hosted provider restore/rollback. |

Real localhost checks repeated against the clean Python 3.11 backend: **three passed**, covering authentication, owner-isolated project save/reload, support intake, temporary-account export/deletion and PDF editing/export. The repeatable end-state command is also being executed; do not assume it passed until its report exists and has been inspected.

## Supported baseline and limitations

Current regression coverage exercises native object creation/selection/move/resize/rotation/property edits, drawing controls, chat edits, fixed protections, supported follow/ask/unlink behavior, parking reflow, native cul-de-sac/pipe editing/import, modeled warnings, candidate comparison/application/cancel/undo, layer controls, commercial generation, 2D/3D and review exports.

Dependencies are not yet a universal multi-discipline graph. Canonical update adapters do not yet centralize every creation/delete/bulk command. Main dashboard/preview components remain oversized despite focused extraction. Prototype geometry and illustrative review-sheet implementations are preserved but inactive. Detailed historical branch disposition remains open; Vision V3 is not part of this checkpoint and founder direction on its integration is pending.

Provider/map/hosted-credential skips, complete cross-browser certification, real provider imagery, independent survey/engineering evidence and target-CAD verification remain separate limitations. Warnings include parser/image/test-client deprecations. No construction-ready or compliance claim is supported.

## Promotion / rollback

No push or deployment has occurred. Keep staged/production approval separate. Before approval, supply exact target, source/build IDs, migration and backup evidence, rollback candidate, costs/provider settings and hosted test plan using `docs/product/phase-0-release-procedure.md`.

Rollback rehearsal retrieved `f18aa71c724d44193d7fe822fb5534d065c5e792` relative to the pre-checkpoint HEAD. It is not yet a proven rollback target for this checkpoint or its new writes. Verify code/data compatibility on isolated restored storage; never infer database replacement permission from code deployment approval.

Phase 1 must wait for the full Phase 0 exit criteria, including one dependable version and exact approved deployed-build verification.
