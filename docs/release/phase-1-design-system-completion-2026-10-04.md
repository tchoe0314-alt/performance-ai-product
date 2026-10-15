# Phase 1.5 — Completed locally, 2026-10-04

## Outcome

Implemented the user-approved compact light design system. Obvious drawing/view/object actions now use centered icons with accessible names and tooltips. Ambiguous tools and approval decisions retain words. Compact typography, spacing, panel headers, input sizes, buttons, menu bounds, dialogs, table rows, empty/error/status surfaces and reduced-motion behavior are defined in the shared workspace stylesheet. Mobile drawing controls keep usable touch targets. State badges and relationship line patterns add non-color cues without changing engineering truth.

Architecture and component conventions: [Phase 1.5 design system](../product/phase-1-design-system.md).

## Issues found and repaired

- Narrow-phone layer menus extended beyond the viewport. Their anchoring now uses the whole compact toolbar, with bounded width and scrolling height.
- At short landscape sizes, a mobile drawer's 100% width combined with side insets exceeded the viewport; the drawer could also be squeezed behind the composer. Width now respects its insets, and an open short-screen drawer temporarily hides the composer while retaining navigation.
- Short-screen menus could extend below the viewport. Both view menus now have a scrollable viewport-relative height bound.
- Labeled Flip H/V buttons wrapped into taller cells beside compact icons. They now share the same control height, with measured centering and no horizontal clipping.
- Regression testing found an explicit imported project snapshot could be dropped by live-state autosave deduplication. Explicit input overrides now bypass that optimization. Success, failed-detection preservation, saved Undo/Redo, failed-save retry, copy/replace/cancel and exports were retested.

## Verification

- Final production build and TypeScript validation passed (`.next-phase15-complete`).
- 93 existing Chromium workflow checks passed after the save correction: all panel routes, canonical commands/layout alternatives, native detailed object editing, commercial concepts, error/recovery states, chat controls, Undo/Redo, 3D recorded-video workflow and workspace overlap behavior.
- 104 layout/accessibility/browser checks passed across Chromium, desktop WebKit, mobile Chromium and mobile WebKit. They cover seven viewport sizes from 320×568 to 2560×1440, portrait/landscape, runtime resizing, keyboard focus/activation, state badges, reduced motion, fresh-shell accessibility and Draw/Deliver containment.
- After the final object-button-height adjustment, all 48 focused design-system checks passed on the final build across those same four browser/device projects. Populated object actions are measured for equal height, centered icons and zero horizontal clipping.
- A final 19-check existing error/recovery/Undo/video suite passed on that final build, including the explicit import-save regression and hide/show/copy/transform recovery.
- Eight authenticated saved-history/tab checks passed: repeated reload and Undo/Redo, failed-save recovery, atomic group/chat history, and first-edit copy/replace/cancel with branch preservation.
- Eight authenticated dependency/object/export checks passed: all four relationship policies, stale approval rejection, quantity refresh, atomic bulk transforms, grouping/editable linework and real PDF/DXF downloads with owner isolation.
- Scoped lint of the changed presentation components/helper/new tests passed; whitespace validation passed. Existing shared save-hook/library warnings are not claimed fixed. Repeated test coverage is not summed into a misleading total.

All authenticated tests used disposable local accounts, isolated storage and disabled paid AI/image providers. Registration throttling remained enabled; one pack hit its limit and passed when rerun against a freshly restarted owned local test backend. WebKit uses its all-controls keyboard shortcut for the same focus/activation assertions. The additional Firefox run stalled during startup and was interrupted; no Firefox pass is claimed.

The final build emitted a non-fatal cache-write disk-space warning but completed compilation, type checking and page generation successfully. Three obsolete build directories created for this turn were removed, freeing about 1.1 GB. They are regenerable; source files, pre-existing work and saved projects were not removed.

Temporary screenshots/test traces are under `/tmp/civora-phase15-*`. This is local implementation and browser proof, not a hosted release. Nothing was deployed, no purchases were made, and no live customer project was edited. Representative resolutions do not constitute a guarantee of every conceivable browser, font or device.

## Next milestone

Phase 2.1 adds the global project header and project identity/status details. To preserve the compact direction, decide which details remain visible versus being placed in a Project details menu. No Phase 2.1 implementation is included here.
