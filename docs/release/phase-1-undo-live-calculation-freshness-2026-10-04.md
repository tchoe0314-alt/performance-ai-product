# Multi-step draft history and unsaved-input protection

Local, uncommitted checkpoint. Phase 1.1 remains incomplete; no deployment,
purchase, production migration, or broad engineering certification.

## Changes

- Replaced single-action draft undo/redo with bounded, detached session stacks
  (100 supported object-edit actions). Undo exposes the preceding action; redo
  consumes its forward entry without clearing remaining forward steps. A new
  edit clears the forward branch. Workspace reset clears both stacks.
- Existing add/delete/update/bulk/combine/explode recovery handlers remain the
  geometry owners and continue marking affected engineering systems stale.
  Selective recent-change undo invalidates the incompatible linear branch.
- Added a portable live-input key to newly bound calculations. Both Python and
  JavaScript encode JSON structure explicitly, binary floating-point numbers,
  and escaped Unicode before hashing. This avoids decimal/scientific-number and
  Unicode serialization differences; the existing saved-input binding is retained.
- Saved-result and background-job loaders compare newly bound calculations with
  current live manual/canvas/site inputs before publication, rechecking workspace
  ownership after asynchronous hashing. An input change during hashing also blocks
  publication. Legacy results without the new key remain unverified and retain
  compatibility behavior.
- Direct runs compare live inputs before publication. If changed, the result is
  retained through the authenticated history-only archive endpoint, which cannot
  activate it even when the database's saved inputs still match. Archive failure
  preserves the drawing and reports that history could not be saved.
- Plan-preview responses and their background success messages are fenced against
  changes to live inputs or workspace ownership during preview generation.

## Verification

- 224 backend tests plus 5 subtests passed across history retention/archive API,
  portable keys, calculation bindings, actual job runners, project/storage paths,
  artifacts, lifecycle/backups, permissions, collaboration, and legacy migration.
  22 existing dependency deprecation warnings; no final selected-test failures.
- 36 Chromium checks passed: stack order/bounds/detachment/branch clearing,
  Python/browser Unicode-decimal key parity, unsaved-input suppression, direct
  result retention, queued results that the server still calls current, existing
  undo recovery, approval/polling/export regressions, and real local persistence.
- Real website workflow: inspector edit 125→150, command edit 150→175, undo twice
  to 125, redo twice to 175, then save/reopen with canonical and compatibility
  geometry intact and independent client metadata preserved.
- 9 additional Safari/WebKit and mobile Chromium/WebKit checks passed, including
  the same repeated undo/redo/save/reopen workflow and saved-result suppression.
- Production build, TypeScript, scoped lint, and whitespace checks passed.
- Website build `7O3BbzzJ8fE-LunyBL56q` on localhost:3050; API localhost:18886 with
  disposable storage `/tmp/civora-phase1-canonical.oAOyri` and paid providers off.

## Limits / next work

- Undo/redo stacks are session-only. Saved final geometry and calculation history
  persist, but reopening does not restore the undo stack. A durable edit ledger,
  reviewable revisions, and broader transaction semantics remain future work.
- This is supported object-edit history, not undo for every source/form/upload or
  external operation. It does not silently make every system fresh after undo.
- Live comparison covers the documented canvas/manual-fields/site-input scope,
  not independent source records, every strategy/prompt, or a complete dependency
  graph. Legacy keys do not gain retrospective verification.
- Quantity ownership, active/stale quantity presentation, export freshness policy,
  and general cross-session revision conflict protection remain incomplete.
- Late direct results after changing workspaces still use the previous publication
  rejection behavior; this checkpoint archives direct results for same-workspace
  live-input changes, not every cross-workspace cancelled request.
- PostgreSQL and hosted production backup/storage gates remain unverified here.
