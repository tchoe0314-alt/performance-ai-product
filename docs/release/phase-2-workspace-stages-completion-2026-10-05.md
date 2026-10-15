# Phase 2.2 — Implemented and verified locally, 2026-10-05

## Outcome

The roadmap's Brief, Explore, Analyze, Review and Deliver presets replace the old three-workflow rail. They do not gate progression or create another project model. Each stage offers its existing tools through one compact picker and remembers its last-used panel per account/project/browser tab. Refresh restores preferences. Global Chat, Projects, Help and Settings do not overwrite stage destinations.

Rules and architecture: [Workspace stages](../product/phase-2-workspace-stages.md).

## Specific changes and repairs

- Added validated stage definitions and versioned per-tab view memory. This keeps navigation preferences outside saved engineering inputs, calculation signatures and Undo history.
- Connected the rail and drawer picker to the existing panel-opening path. Inspector and shortcut navigation remain consistent with the selected stage.
- Retained first-save/copy view continuity, without leaking one project's preferences into another.
- Regression checks exposed project-transition navigation bugs: Projects could close before restore/copy feedback was visible, and a new blank project could open an unwanted drawer. Hydration now preserves global utilities and an intentionally closed fresh workspace.
- Darkened neutral disclosure status labels after the accessibility audit found the Brief "Not set" label below AA contrast. No status meaning changed.
- Updated legacy test navigation through a shared explicit-tool helper with fallback for the older deployed website. Remembered Generate cannot accidentally substitute for an explicit Draw request.
- Corrected older test expectations for icon-only accessible controls, active inputs versus retained Undo snapshots, and combined physical-object context. Combined wrappers must not double-count their original physical members in engineering handoffs.

## Verification and limits

- Final production build `.next-phase22`, TypeScript, focused lint and whitespace checks passed.
- Final 76 layout/accessibility/stage-memory checks passed across Chromium, WebKit, mobile Chromium and mobile WebKit. Four additional authenticated stage checks passed separately on all four engines: independent projects/tabs, unchanged exact stored inputs/revisions, reload, failed-save live-edit retention and Undo/Redo after switching all five stages. Splitting authentication packs avoids weakening normal registration throttles.
- Eight final authenticated transaction/two-tab checks passed: copy/replace/cancel, persistent Undo/Redo and abandoned branches, failed-save recovery, atomic grouping/chat changes and explicit replacement recovery.
- Eight final project-header checks passed, including persisted identity, geometry autosave and first-edit copy decisions.
- The broad 254-check Chromium run passed 245, skipped four environment-gated checks and failed five. The address check exceeded that run's shortened 45-second limit and passed both checks when rerun with its normal timeout. Final focused checks passed the complete 16-check Projects suite, the Chat-during-save check and both preview performance checks after the navigation/test repairs. The reactive checkpoint check remains a real open failure, not a passing or skipped test.
- Earlier test packs also exposed stale fixture assertions and a 429 registration throttle. Those failures remain in the diagnostic artifacts; successful retests do not turn the combined runs into all-green reports.

No backend code, deployment, purchase or live-customer modification was made. Tests used local production builds, disposable accounts/storage and mocked paid-provider responses. This does not certify live Mapbox/imagery providers, PostgreSQL, Firefox, all engineering calculations or hosted release readiness.

## Open issue and next work

The focused reactive-rerun test fails in both `.next-phase21` and `.next-phase22`: the generated review overlay and flow-summary updates change live inputs while the direct calculation is running, causing its result to be archived rather than available as the next reactive checkpoint. Trace evidence includes calls to `calculations/archive` and the next request missing `reactive_partial_rerun_request`. This predates stage navigation. Preserve the failing test; do not bypass freshness protection to make it green. Repair the Generate/input-publication ordering and prove genuinely later user edits still archive old calculations before release.

Phase 2.2's navigation requirements are completed locally, but this is not an all-green product or deploy-ready declaration. Phase 2.3 environment controls have not started. Ask whether 2D/3D, layer visibility, units, grid and snapping preferences should be remembered per project and tab. Preserve the existing subscriptions/providers and do not purchase replacements.
