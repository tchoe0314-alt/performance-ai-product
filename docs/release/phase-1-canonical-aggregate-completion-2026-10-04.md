# Phase 1.1 — Canonical aggregate completion

## Outcome and scope

The master roadmap's 1.1 model is connected across the currently supported website/backend workflows. This is local implementation completion, not completion of all Phase 1, a production migration, or engineering certification.

The ownership/read-write inventory is in [the model document](../product/phase-1-canonical-project-model.md). The owner is `backend/services/canonical_record.py`; schema and lossless geometry adapters remain separate modules. Existing engines/UI use projections rather than independently writable result/quantity/source/alternative copies.

## Changes

- Locked full/shell saves expose deterministic design revision tokens. Competing modern saves return 409 without modifying the project. Current calculation publication and export history do not invalidate an otherwise unchanged editor's design revision.
- Two tabs do not fork simply on opening. The first edited save asks whether to save a copy, replace the original, or keep editing. Copies preserve result/quantity data, use their own project identity/name, and subsequent edits stay on the copy. Each tab restores its own active project. Explicit replacement requires the current revision and retains a bounded recovery snapshot. Pending/cancelled unsaved branch choices warn before leaving.
- Server snapshot workflows also compare their calculation snapshot before writing, so chat feedback, alternative review, queue seeding and job revision cannot silently restore old geometry or overwrite a newer calculation.
- Current results are linked by ID and sidecar reference. Canonical collections own quantity/cost, generated sources, assumptions and alternatives. Full/result routes reconstruct the original result shape; the shell route still avoids loading the heavy result.
- Canonical site inputs and controls override conflicting compatibility shadows. Existing internal legacy writers refresh the owner explicitly. Candidate-review progress survives stale autosaves. Program-only and canvas projects both read canonical length units; explicit unknown canonical units do not retain a previous known value.
- Export/history metadata updates seal their canonical collections within the same lock. Current/historical artifact checks and old download access isolation remain intact.
- Legacy design conversion retains the prior record and a conversion report first. Metadata-only updates do not silently migrate legacy projects or hide their results. Unknown coordinates and verification status remain unknown.
- Authenticated current-document export hydrates the result for structured JSON round trips. Incomplete imports containing an unresolved result-sidecar reference are rejected instead of appearing to restore a partial calculation. Immutable archive/file references remain references; complete disaster recovery still requires database/file backup.
- Testing found a downloads regression: a lightweight job refresh erased fetched artifact detail. Summary merging now retains terminal downloads, rejects older summaries, drops outdated calculation detail on a new snapshot, and respects removed jobs. The real PDF/DXF download-and-reload workflow passes after repair.

## Final verification

- **310 backend tests and 16 subtests passed**, zero failures. Selection covers canonical schema/JSON, canvas gateway, aggregate ownership/import/export, full/shell persistence, revision/concurrent-write races, current/archived calculations, atomic export finalization, application design/project/job/artifact workflows, job queue, legacy database migration, backup/lifecycle, and team/admin/collaboration behavior.
- **49 Chromium website/contract checks passed**, zero failures. Includes actual local authentication, save/edit/reopen, two-tab copy/replace/cancel and subsequent independent edits, preservation of copied quantities, document export, result staleness, direct/queued run fences, undo/redo, quantities, jobs, and authenticated PDF/DXF download/reload/owner isolation.
- **6 checks each passed in desktop WebKit, mobile Chromium, and mobile WebKit**, zero failures. These repeat canonical edit/save/reload, stale-result rejection, all three multi-tab choices, and PDF/DXF download/reload/owner isolation.
- Production build and TypeScript validation passed. Whitespace validation passed.

Evidence locations: `/tmp/civora-phase1-final-49-chromium`, `/tmp/civora-phase1-final-webkit-verified`, `/tmp/civora-phase1-final-mobile-chromium-verified`, `/tmp/civora-phase1-final-mobile-webkit-verified`. These are local temporary test artifacts, not permanent hosted recovery storage.

An initial combined cross-device run hit the normal registration rate limit (429). Final browser packs used fresh disposable local API processes between packs; production rate limits were not weakened. Existing dependency deprecation warnings remain. No paid AI/image provider, production customer data, deployment, or spending was used.

## Next real work / release limits

Phase 1.2 is the next development milestone: standardized object IDs, typed geometry, layers/visibility/locks, source/revision/validation fields, dependencies and calculation/export mappings for every supported object type. Preserved native/custom records are not automatically interpreted as verified engineering inputs.

Phase 1.3 must provide a unified durable transaction ledger and complete undo/redo across every operation. Current undo stacks are session-scoped; replacement recovery snapshots are retained but not a complete recovery UI. Old API clients without revision tokens remain compatible and do not get the modern website's stale-write guarantees.

Hosted/Postgres operational checks, production migration, real-data engineering validation, and previously deferred Phase 0 release gates remain separate holds. Firefox was not included in this pass. The successful local checks do not clear those holds.
