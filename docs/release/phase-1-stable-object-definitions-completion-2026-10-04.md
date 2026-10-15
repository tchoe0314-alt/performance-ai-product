# Phase 1.2 local completion — 2026-10-04

Implemented the agreed draw-first/classify-after workflow, optional custom names and fields, project/account custom-type reuse, connected-line combination, editable/uncombinable outlines and nested organizational groups. Standardized canvas objects now save and restore through the canonical project document. Server-owned validation, revisions and authenticated creator attribution prevent client claims from becoming authoritative engineering facts.

## Verification

- 261 backend tests passed across object definitions, project persistence/conflicts, canonical records/results, calculations, job workflows, immutable exports, lifecycle/privacy/deletion, legacy migration and collaboration.
- A 164-test Chromium regression pack passed across the new real-website workflows, canonical persistence, first-edit tab branching, export downloads, object editing, interference rulebook, plan execution and history freshness.
- A subsequent 38-test targeted pack passed after creator/protected-group corrections, including real authenticated save/reopen and linework/group workflows.
- Desktop WebKit: six real-website tests passed, including canonical persistence and PDF/DXF downloads. Mobile Chromium and mobile WebKit: five each passed, covering the three new object workflows and two canonical persistence workflows.
- Final production build and TypeScript validation passed after the custom display-label/prototype-safe classification correction. All 16 final targeted Chromium tests passed (three real object workflows, nine object contracts and four existing native-object integration tests). All three new real-website workflows then passed again on mobile WebKit against that final build; its custom display label was visually verified.
- Screenshots of the custom-object inspector were inspected for compact controls and overlap on desktop/mobile.

Repeated runs are not added together as a unique total. Tests used disposable local accounts, a local production web build and local backend storage with AI/image providers disabled. No real customer data, paid services or deployment were used.

Primary coverage: `tests/test_site_objects.py`, `apps/web/tests/live/phase1-object-definition-contract.spec.ts`, `apps/web/tests/live/phase1-local-object-model.spec.ts`. Earlier evidence directories: `/tmp/civora-phase12-final-chromium`, `/tmp/civora-phase12-final-attribution`, `/tmp/civora-phase12-final-webkit`, `/tmp/civora-phase12-final-mobile-chromium`, `/tmp/civora-phase12-final-mobile-webkit`. Final targeted evidence: `/tmp/civora-phase12-final-latest` and `/tmp/civora-phase12-final-latest-mobile`. These temporary artifacts are local evidence, not durable release attachments.

## Limits and next work

Phase 1.2 is complete locally for the current catalog and agreed authoring scope. It does not certify site engineering, prove production/Postgres deployment behavior, persist complete undo stacks across refresh, or close deferred operational release gates. Custom classifications are reference-only; groups are organizational. Group copy/delete/reclassification requires ungrouping first to preserve the tree safely.

The next milestone is Phase 1.3: move every edit operation through a unified durable transaction/history boundary. Deployment and real-site engineering/source review remain separate activities.

Subsequent milestone: [Phase 1.3 completion](phase-1-unified-edit-transactions-completion-2026-10-04.md) supplies durable history; the limits above describe the Phase 1.2 checkpoint.
