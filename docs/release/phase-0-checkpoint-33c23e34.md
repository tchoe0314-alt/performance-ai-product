# Phase 0 local baseline — 33c23e34

Recorded October 2, 2026. Application revision: `33c23e34918032dd151f913024d4a9d60e4fed34`; integration branch: `codex/phase-0-integration`. Subsequent consolidation-closeout changes are documentation only. This is a locally tested baseline, not a deployed release, Phase 0 completion or pilot approval.

## Changes since the initial consolidation checkpoint

- Protected complete deletion and concept-replacement groups before mutation, so regeneration cannot silently replace locked/fixed/existing/reference objects.
- Made supported commercial revisions and Ask approvals whole-batch, protected and undoable; corrected parking reflow against the resized parent.
- Established synchronous live placement authority so rapid writers do not read an older React snapshot.
- Guarded delayed approval, alternative, ordinary edit, deletion/restore, detected-object, drawn-boundary and queued draft saves against newer workspace state.
- Extracted transaction/comparison orchestration while retaining geometry math in utilities. Preserved legacy serialization and inactive prototypes.
- Recorded validation revision provenance and corrected health reporting so an application version is not misrepresented as a source commit.

## Verified results and scope

| Evidence | Result |
| --- | --- |
| Complete website at this checkpoint | **374 passed, 16 skipped, zero failures**, 390 Chromium-selected tests, 10.1 minutes. Local frontend at localhost:3040, backend at 127.0.0.1:18880; controlled-response and real-local checks both included. Output directory `/tmp/civora-phase0-full-browser-33c23e34`. |
| Repeatable end-state selection | **Eight of eight gates passed**; browser selection **107 passed, two skipped**, 3.9 minutes. Report `/tmp/civora-phase0-end-state-33c23e34.json`. Python 3.11.15; clean tracked revision `33c23e34` before and after. Served/deployed-artifact verification flags are both false; external evidence is incomplete. |
| Complete backend | **1,837 passed, zero failed/skipped**, 78 passing subtests, 42 warnings, 549.25 seconds, at `012dd2a9`. Backend/tests/backend-test requirement inputs are unchanged through `33c23e34`, verified by an empty scoped Git diff. This is backend evidence, not exact combined deployed-artifact certification. |
| Latest changed-path website check | **68 passed, two map-provider skips**, 1.9 minutes; object editing/history, drawn boundaries, project/save races, native objects and real-local save/reload. |
| Frontend quality | Lint/typecheck and isolated production build passed for the save-boundary changes. The repeatable command independently passed its build-quality gate. |
| Local recovery | Disposable SQLite content/schema/integrity restore passed. Prior production code `597c46a3353f3a58b70925f74d753a679c8ce3de` read 83 active projects from a copied fixture snapshot, preserved exact inputs/results and all schema/table contents, and denied unrelated-owner reads. Original snapshot unchanged; no hosted database or provider rollback. |

Recovery reports: `/tmp/civora-phase0-backup-restore-2606dea9.json`, `/tmp/civora-phase0-code-data-rollback-33c23e34.json`, `/tmp/civora-phase0-old-code-data-33c23e34.json`. Old-code compatibility uses the fixture snapshot from `2606dea9`, not arbitrary future formats or real customer data. Temporary evidence paths are local records, not guaranteed long-term archives.

## Release boundaries

[Consolidation register](../product/phase-0-consolidation.md) records capabilities, inactive implementations, source inventory and limitations. Missing hosted credentials/provider tests, complete platform/container checks, actual external engineering/CAD review and hosted backup/rollback evidence are not converted into passes.

No push or deployment occurred. Before staging approval, establish the separate target and noncustomer database, source/build identity, secret/provider settings, cost implications, migration/backup evidence, rollback plan and authenticated post-deployment checks using the [release procedure](../product/phase-0-release-procedure.md). Production approval is separate. The prior-code fixture read is not authorization to restore a database or redeploy production.
