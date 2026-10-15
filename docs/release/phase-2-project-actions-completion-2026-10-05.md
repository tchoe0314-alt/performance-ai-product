# Phase 2.4 — Local completion, 2026-10-05

Implemented the user-adjusted main-action scope: compact sharing, report, DXF, supported LandXML, edit-history and project-settings entry points. No separate milestone feature, per user decision.

## Changes and reasons

- Reused existing team, report, export and project-details workflows; avoided duplicate project state and permanent toolbar clutter.
- Default invitations to viewer. Backend invite/remove/role-change guards and both permission surfaces now restrict access management to the creator, not admins. Existing creator-granted editor access still works.
- Added a read-authorized named saved-history summary and modal. Names come from server-sealed actor IDs; the creator is shown. Unavailable identities remain unknown. No raw transaction snapshots are returned.
- Connected limited LandXML pipe-network review exports through current-result, geometry/audit and atomic artifact-history safeguards. Unknown diameter/length, unsupported units and empty networks are rejected. The existing writer keeps external-verification and review-only flags.
- Fixed the new menu's narrow-screen clipping and Escape being consumed by the canvas shortcut. Native dialog behavior contains focus.
- Updated an existing test's obsolete reviewer-default expectation to the user-approved viewer default; explicit creator promotion and other team workflows remain tested.

## Evidence

- Final frontend production build and TypeScript validation passed. Focused lint of action/header/export helper/tests passed. Diff whitespace validation passed.
- New project-action suite: 4 passed per desktop/mobile Chromium and WebKit, **16 passed total**. Includes three viewport sizes, menu containment, Escape dismissal, project settings, real disposable authenticated sharing with viewer default and named creator/editor history.
- Existing header containment/accessibility: five focused checks passed on the final build (included in the eight-check menu/header pack).
- Backend affected pack: **49 passed**, covering limited LandXML, empty/unknown-data rejection, atomic export finalization, named history, creator-only sharing, immutable transactions, revisions and collaboration/lifecycle. Additional endpoint-level LandXML success/outsider rejection assertions passed in the focused two-test rerun.
- Existing browser export/staleness pack: six checks passed, including real authenticated PDF/DXF download/owner isolation and stale-export guards. The remaining older team test initially failed on its obsolete default-role assertion; after updating that assertion, both team/lifecycle checks passed.

These are local disposable accounts/storage with paid providers disabled. LandXML's actual writer/service/endpoint and saved export history were tested locally; external CAD import compatibility and a browser-driven LandXML download were not certified. No deployment or purchases occurred.

## Next work

Phase 2.5: flexible workspace panels. Clarify whether users want panel sizes restored per project/tab and whether explicit reset-to-default should be available. Full realtime collaboration/read-only tool UI belongs to Phase 8; named saved transaction history here does not claim every possible collaborative action is audited. Repair the pre-existing Generate/reactive-checkpoint freshness bug before the next release.
