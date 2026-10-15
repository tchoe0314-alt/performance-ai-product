# Atomic export finalization — October 4, 2026

## Changes

`ProjectStore.update_project_metadata` locks the project before reading its JSON,
rechecks editor permission/deletion, applies a local metadata merge and updates
only metadata/timestamp. SQLite uses BEGIN IMMEDIATE; Postgres uses SELECT FOR
UPDATE. Rollback/connection cleanup apply to errors. No geometry, session, result,
ownership, tags or project name are rewritten by workflow metadata publication.

`save_project_workflow_update` uses that atomic path in the production store.
Compatibility adapters/test doubles without the method retain their old fallback;
they do not gain concurrency guarantees.

DXF, JSON and PDF exports now finalize against locked saved inputs after file
generation. A changed layout retains the file and calculation-linked metadata as
`snapshot_status: historical`, clears release readiness, and returns 409 instead
of success as the current plan. This does not advance the active revision
snapshot. Matching inputs commit as current; unbound legacy inputs remain
unverified. Unavailable/deleted projects do not publish an export as current.

Async workers preserve historical-download information in failed job results and
return a readable error rather than losing the artifact. Job history retains the
artifact identity/status across its merged sources. The website labels these
records “Historical” while keeping the existing authenticated download action.

## Final evidence

- Backend affected selection: **283 tests plus 5 subtests passed**, 22 existing
  dependency warnings, 34.55 seconds. Includes 11 new atomic-finalization checks,
  concurrent metadata writes, all three export-generation edit races, async
  historical artifacts for three export job types, rollback, access isolation,
  deletion, and surrounding project/job/lifecycle/migration tests.
- Web affected selection: **16 checks passed** in the Chromium project, 19 seconds.
  Includes historical-label/identity contract checks, job polling, stale export
  guards, actual local PDF/DXF queue/export/authenticated downloads and reload,
  owner isolation, canonical save/reopen and undo/redo. Contract/component-tree
  checks are Node checks, not all 16 are browser interactions.
- Production website build passed, including TypeScript. Build ID:
  `1HGQpWjDxgpPBCdC5yUHf`. Whitespace validation passed.
- The successful-export browser fixture now uses a fresh grading state: stale
  current-plan export rejection is intentional and separately tested.

## Remaining scope

This closes read-then-full-save workflow metadata publication and the saved-input
race during file generation. It does **not** introduce optimistic revisions for
two editor sessions, or prevent a later full/autosave submission of stale metadata
from overwriting history. General full/shell save conflict protection is next.

Freshness signatures retain the existing canvas/manual/site-input scope, not all
external pricing/source/prompt dependencies. Backend finalization compares saved
inputs; an unsaved browser edit not yet received by the server is outside that
commit boundary. Export current/historical status describes finalization time,
not a perpetual guarantee against future edits.

No hosted Postgres concurrency test or production deployment occurred. Existing
Phase 0 release holds and Phase 1.1 canonical quantity/source migration remain
open. No purchases or bulk project migrations.
