# Phase 2.5 — local completion evidence

## Scope and changes

Implemented the flexible supporting-panel shell, compact layout presets, keyboard/pointer resizing, responsive canvas containment, temporary full-canvas focus, account-level saved sizes/visibility/mode, and Reset layout. Existing brief/chat, object inspector, health and reactive calculation summaries are reused rather than inventing design outputs. Workspace preferences have a dedicated authenticated account store and are included in account-data export; no project document fields or revision counters are used for layout persistence.

The SQLite and Postgres schema definitions include the preference table with an account foreign key. Backend payload validation rejects unsupported fields, invalid dimensions and attempts to select another user through the payload. Frontend parsing handles untrusted cache values and optional denied local storage. Failed account synchronization is visible to the user.

Visual inspection caught an overlapping layout button, moved to unused navigation space. Accessibility checks caught low-contrast inherited chat feedback text, corrected before the final browser pack.

## Proven locally

- Final production frontend build completed successfully.
- Focused lint and TypeScript checks passed.
- 36 new browser checks passed across Chromium, WebKit, mobile Chromium and mobile WebKit on the final build. Coverage includes accessibility, 320-pixel portrait and short landscape layouts, 1024/1280/1920 desktop layouts, keyboard and pointer sizing, focus/reset, denied device cache, account persistence in a second isolated browser context, and unchanged project revisions/inputs.
- 18 related Chromium layout, stage and project-action checks passed on the functional build before the final contrast-only adjustment.
- 22 existing drawing/3D/parity checks passed on that functional build.
- 39 workspace-layout, revision-conflict, edit-transaction, team-admin and project-lifecycle backend checks passed.
- 30 database-pool, migration, data-lifecycle and workspace-layout checks passed after the account-export addition. This pack overlaps the workspace checks above; these counts are not distinct totals.
- Whitespace/diff validation passed.

Disposable local users and the local API were used. No deployment or paid-provider execution was performed.

## Limits and next blocker

Hosted Postgres migration/runtime and live deployment remain unverified. Full-canvas focus and the selected mobile supporting region are intentionally temporary; persisted account preferences cover mode, visibility and preferred sizes. Concurrent open devices use last-saved account preferences, not live broadcasts. The Live Delta shell exposes current recalculation summaries; richer quantity deltas remain Phase 7.2.

An inherited Generate/reactive-checkpoint freshness failure remains a release blocker: generation can alter a review/flow input fingerprint during calculation, causing the result to be archived rather than activated. This milestone did not bypass freshness checks or repair that separate calculation workflow.

Next roadmap milestone is Phase 3.1, Active Brief Summary, to make project targets, constraints and missing information visible before generation. Confirm treatment of absent values and automatic assumptions before implementing that milestone.

## Subsequent audit addendum

The subsequent [Phase 0–2.5 regression audit](phase-0-through-2-5-audit-2026-10-06.md) reproduced and repaired the Generate checkpoint ordering failure locally. The statements above record the original 2.5 closeout; the audit contains the newer repair evidence and remaining verification boundaries. No deployment is implied.
