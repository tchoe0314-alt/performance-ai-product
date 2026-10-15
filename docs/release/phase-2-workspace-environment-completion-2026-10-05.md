# Phase 2.3 completion — 2026-10-05

## Status

Phase 2.3 environment controls are implemented and locally verified. No deployment, provider purchase, or production-data write was performed. Phase 2.4 has not started.

## Specific changes and reasons

- Added compact Layers/View controls for satellite, topographic, zoning, parcel, survey and utility visibility, display units, coordinate basis, grid and snapping. These extend existing menus rather than crowding the main toolbar.
- Remembered environment preferences independently by account/project/browser tab, including refresh, first save and explicit copies. Hydration also writes unchanged inherited snapshots so copied settings do not reset on refresh.
- Preserved 2D/3D and quality during quiet panel navigation. Explicit drawing commands still enter 2D.
- Connected the grid spacing to actual pointer snapping, not just a decorative grid. Display metric converts readouts while canonical geometry and typed drafting inputs remain feet.
- Classified actual imported/model source data; absent sources are disabled with No data. Survey points and topographic elevation labels can be controlled independently.
- Kept hidden geometry in canonical constraint checks; hiding zoning does not erase its engineering warning. Hidden render objects do not attract object snaps. Show all restores context, source and native CAD-layer visibility.
- Rebuilt map styles on the same map instance, restoring overlays and preserving camera. The remembered map-off choice does not auto-enable after refresh.
- Fitted menus around other controls, including short mobile landscape. Kept the existing precision HUD's decimal formatting.

Architecture and boundaries: [product specification](../product/phase-2-workspace-environment.md).

## Verification

- Final production build: passed, including TypeScript checking.
- Focused lint of new environment schema/control/memory code and affected navigation hook: passed. Repository diff whitespace check: passed. This is not a claim that every inherited file is lint-clean.
- Final environment suite: **33 passed, 3 intentionally skipped** across desktop/mobile Chromium and WebKit. Includes real disposable authenticated project/tab identity, exact unchanged backend inputs/revisions during view changes, source visibility, retained constraints, actual snap coordinates, copy-and-refresh inheritance, storage-denial handling, accessibility and responsive menu bounds.
- Mapbox WebGL/style/camera/overlay test: passed in desktop Chromium with all provider resources mocked. The other three browser projects intentionally skip that WebGL-specific case; this does not certify live provider availability or all-browser WebGL behavior.
- Final related 3D, canonical geometry, drawing precision, source visibility and performance suite: **27 passed**.
- Two-tab explicit replacement regression rerun: **1 passed**. An earlier large authenticated pack encountered normal registration throttling; protections were not weakened.
- Earlier in this pass: **88 layout/header/stage checks passed** across the four browser projects. An additional **4 authenticated stage-memory checks passed** while the enhanced copy test correctly exposed the now-fixed persistence gap.
- Related transaction/history pack earlier in this pass: 34 passed and one registration-throttled case; that exact remaining case passed the focused rerun above.

## Remaining boundaries and next milestone

This is not a whole-product bug-free certification. The pre-existing Generate/reactive-checkpoint freshness failure remains a release blocker: an intervening live-input change archives the calculation and the next request lacks the expected partial-rerun checkpoint. The freshness guard was not bypassed and that unrelated failure was not declared fixed.

Metric is display-only, coordinates are local feet with an approximate geographic anchor when available, and source layers require actual project data. There is no fabricated zoning/survey CRS or engineering sign-off.

Next roadmap milestone is 2.4: clear share, milestone-save, report/export, revision-history and project-settings actions. Sharing permissions and milestone naming should be confirmed before implementation. Repair the Generate freshness blocker before the next release.
