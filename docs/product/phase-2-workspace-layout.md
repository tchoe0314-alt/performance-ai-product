# Phase 2.5 — Flexible workspace layouts

## Confirmed user decision

Workspace layout is remembered per user, not per project or browser tab. The same user's layout applies across projects. Include a Reset layout action that restores the default layout without modifying project data, geometry, calculation state, history, or saved source-layer preferences.

This rule applies to supporting-panel sizes, layout mode and explicit panel-visibility preferences. Phase 2.2 stage memory and Phase 2.3 project/tab environment preferences remain separately scoped; the new layout preference must not silently overwrite them.

## Required implementation scope

Follow master-roadmap 2.5: left brief/chat, central design canvas, right inspector/health and bottom Live Delta Bar; collapsible/resizable/context-sensitive/keyboard-accessible supporting panels; full-canvas focus, saved layouts, Simple and Professional modes. Responsive sizing must preserve a usable canvas with both side panels open. Reset layout must remain reachable when supporting panels are hidden.

Account-level persistence, denied/offline storage behavior, different-user isolation, cross-project reuse, reset, pointer/keyboard resizing and representative desktop/mobile containment require verification before declaring this milestone complete.

## Current status

Implemented and verified locally on 2026-10-06. Not deployed by this milestone.

## Delivered behavior

- Left brief/chat, central canvas, right inspector/health and bottom Live Delta supporting regions reuse existing project and calculation data.
- Compact Layout controls offer Simple (default), Professional, independent visibility, size controls, full-canvas focus and Reset layout.
- Desktop separators support pointer and keyboard resizing. Responsive width caps preserve canvas space; stored sizes are preferred sizes rather than a promise to exceed the available screen.
- Phones use one selected supporting region at a time, with accessible size controls and a full-canvas option. The currently selected mobile region and full-canvas focus are temporary UI choices, not saved account preferences.
- Account-authenticated GET/PUT workspace-layout endpoints store mode, three preferred sizes and visibility per user, independently of project revisions. A per-user device cache is optional; denied cache does not block controls. Account-sync failures show an honest device-only notice.
- Reset restores defaults and closes supporting tools without editing project data. Layout changes do not create design history entries or stale calculations.
- Escape closes the layout menu without intercepting existing modal handling. Existing chat is not duplicated in both supporting panels. Chat feedback text contrast was corrected after accessibility testing.

## Verification and limits

See the release evidence record for test counts. Actual hosted Postgres, live account synchronization and deployment have not been exercised here. Account preferences restore on load; open devices do not receive live layout broadcasts. Live Delta displays existing recalculation summaries, not the future Phase 7.2 quantity-delta engine.

The subsequent [Phase 0–2.5 audit](../release/phase-0-through-2-5-audit-2026-10-06.md) repaired the reproduced Generate/reactive-checkpoint ordering failure locally. Hosted calculation/provider workflows remain unverified; layout completion does not certify the entire product as bug-free.
