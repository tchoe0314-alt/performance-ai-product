# Isolated cul-de-sac study — readiness notes

This study is deliberately separate from Civora's production editor and saved projects.
Entry point: Libraries → Concept studies → Cul-de-sac, or `/concepts/cul-de-sac.html`.

## Implemented

- One versioned, feet-based design model, with derived geometry separated from saved inputs.
- Tangent circular transitions across bulb radii 35–80 ft and road widths 20–48 ft.
- Analytic rectangle contact against circular bulb, transition arcs, straight approach, and island.
- Asphalt and island conflicts reported separately; exact touching counts as a conflict.
- Independent road/building translation through mouse/touch dragging or accessible sliders.
- Pointer capture, cancelled-drag rollback, grouped drag undo/redo, bounded history.
- Immediate local warnings plus revision/request-generation guarded server checks.
- Explicit device-local save, refresh restoration, and JSON import/export; validation before mutation.
- Browser and server share `app/utils/culDeSacConcept.ts`. The standalone HTML embeds a generated
  copy. Run `npm run concept:sync` after changing that module; `npm run concept:check` detects drift.
- Standalone `file:` mode recalculates locally without requiring a server. It does not imply
  server verification, and device storage availability is reported honestly.

## Intentional limits and integration gates

- One fixed axis-aligned 20 × 20 ft building; no arbitrary footprints, rotation, or multi-object editing.
- Island radius fixed at 15 ft and transition radius fixed at 20 ft. These are study parameters,
  not jurisdiction-specific standards or construction recommendations.
- Floating-point contact tolerance is 1e-7 ft. It is not a setback or required clearance.
- No parcel boundary, legal setbacks, swept vehicle paths, fire access, drainage, grading, or utilities.
- The stale flag refers only to this study's collision check; a successful check is not approval
  of other engineering calculations. Network failures do not silently mark server results current.
- Save is local to the browser/device/origin, not cloud storage or a Civora project. JSON export is
  the portable backup. Imports reject incompatible schema versions/units and oversized files.
- Production integration must map this schema to canonical project objects, coordinate origins,
  permissions, revisions, persisted saves and the main editor's undo/redo lifecycle. Do not insert
  a second authoritative project state or save unverified calculation results as current.
- Independent engineering review is still required before design reliance.

## Verification

Focused tests cover 1,334 tangent geometry combinations, translation invariance, line/arc contact,
false bounding-box positives, island-only conflicts, agreement with the actual Canvas path, drag
cancellation, touch dragging, undo/redo, out-of-order responses, API validation, exact fractional
save/reload and pixel-identical restoration, import/export, invalid imports and unavailable storage.

Browser smoke and automated accessibility checks cover Chrome/Safari desktop and mobile, plus
standalone HTML. Local Firefox startup has produced a host graphics/content-process failure before
page loading; the test skips only that specific launch failure and keeps Firefox unverified.
Re-run Firefox in a working browser environment before claiming full cross-browser readiness.

Useful commands from `apps/web`:

```sh
npm run concept:check
npx eslint app/utils/culDeSacConcept.ts app/api/concepts/cul-de-sac/check/route.ts tests/live/cul-de-sac-*.spec.ts scripts/build-cul-de-sac-core.mjs
PLAYWRIGHT_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3017 npx playwright test --project=chromium --workers=1 tests/live/cul-de-sac-core.spec.ts tests/live/cul-de-sac-concept.spec.ts tests/live/cul-de-sac-editor.spec.ts tests/live/cul-de-sac-cross-browser.spec.ts tests/live/libraries-panel-extraction.spec.ts
```
