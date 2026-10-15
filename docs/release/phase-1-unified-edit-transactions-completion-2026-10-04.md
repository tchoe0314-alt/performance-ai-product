# Phase 1.3 — Local verification, 2026-10-04

## Implementation

One durable transaction graph now owns dashboard edit recovery. Detached snapshots cover complete multi-object edits, Undo/Redo cursors survive save/reopen, and new edits retain abandoned branches. The save boundary validates chains and group integrity, authenticates new transaction actors, preserves immutable stored entries, adopts legacy writers and merges approved concurrent branches. Existing conflict/copy/replace authorization remains intact.

Atomic batch planning, exact snapshot replay, project-load validation before workspace reset, and calculation invalidations protect the current draft. Old results and export history remain preserved rather than silently active. Recovery descriptions and read-only generation/review/visualization notices remain available in the compact history panel.

Issues repaired during verification included restore-time defaults creating false edits, counting roads/groups as buildings, reload leases impersonating another tab, loss of existing recovery wording/selection, and missing history notices. The real-website chat fixture now waits for completed project restoration before submitting a command; a premature submission caused one transient test failure, not a relaxed assertion.

## Verified evidence

- Production build and TypeScript validation passed.
- 332 backend tests and 44 subtests passed across transaction integrity, canonical persistence/results, revisions, jobs, calculations, immutable exports, lifecycle/privacy, migration and collaboration. Existing dependency deprecation warnings remain.
- Eight real-website object/edit/recovery tests passed on desktop WebKit, mobile Chromium and mobile WebKit. These include saved Undo/Redo, retained branches, failed-save retry, whole-request chat recovery, grouped edits and approved two-tab replacement.
- The final 175-test Chromium regression pack passed, covering transaction contracts, real authenticated website edits, existing object controls, native geometry, interference rules, canonical commands, recovery feedback and history notices.

- A separate six-test Chromium pack passed: exact canonical save/reopen, outdated-result protection, second-tab copy/replace/cancel, and actual preliminary PDF/DXF downloads with owner isolation.

Phase 1.3 is complete locally for the agreed edit/recovery scope. Repeated runs are not added together as unique coverage. Final desktop evidence: `/tmp/civora-phase13-final-desktop` and `/tmp/civora-phase13-final-persistence-export`. Cross-browser evidence: `/tmp/civora-phase13-webkit`, `/tmp/civora-phase13-mobile-chromium`, `/tmp/civora-phase13-mobile-webkit`.

Tests use disposable local accounts, a production web build and isolated backend storage. Paid AI/image providers are disabled. No deployment, purchases or real customer-data edits occurred. Temporary evidence is under `/tmp/civora-phase13-*`; it is not a durable hosted release attachment.

## Limits / next milestone

This is local software verification, not engineering certification or production/Postgres operational proof. Undo does not delete uploaded files, external artifacts, account-wide definitions or calculation-history records. Transaction snapshots have a 10,000-node input guard; unbounded history load is not certified. Read-only notices are bounded to 100 entries. Older branches are retained, not offered as unsafe selective Undo over a newer plan.

Phase 1.4 is the dependency graph: Follow, Ask, Fixed and Independent behavior for related geometry and quantities. It requires an explicit default policy for newly established relationships. Existing source/engineering and hosted-release gates remain separate.

Architecture: [unified edit transactions](../product/phase-1-unified-edit-transactions.md).

Subsequent milestone: [Phase 1.4 dependency graph](phase-1-dependency-graph-completion-2026-10-04.md).
