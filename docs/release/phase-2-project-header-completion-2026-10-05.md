# Phase 2.1 — Completed locally, 2026-10-05

## Outcome

The compact header now has a project-details menu for project name, client / ID, Site ID, address, APN / parcel and descriptive project stage. It also shows backend revision, save state, connection state, last save, last successful recorded calculation and conservative project health. Existing project navigation and drawing controls remain intact. Administrative addresses do not move map context or change engineering inputs.

Architecture and rules: [Phase 2.1 project header](../product/phase-2-project-header.md).

## Repairs and safeguards

- Removed substring-based save normalization that could treat Unsaved as Saved. Live saved status now uses the exact accepted save baseline; pending/failure states come from the real save queue.
- New identity fields survive ordinary geometry autosaves. Details-only saves join the existing queue and read current geometry after any copy/replace decision, rather than replaying a captured old drawing.
- Explicit metadata edits participate in first-edit two-tab protection. Copy creation preserves the original project's identity and geometry.
- Failed saves retain details for retry. Project-generation checks protect against late responses affecting another workspace.
- API reachability is distinct from browser Offline. Successful archived calculations can supply the last-success timestamp; failed attempts cannot. The timestamp lookup is not limited to the most recent 50 history entries and does not expose full results.
- WebKit exposed a real read-only-menu focus issue. The menu now focuses its close control when fields are disabled, and Escape closes it without leaking into canvas cancellation.

## Verification

- Final production build (`.next-phase21`) and TypeScript checks passed.
- 40 focused backend tests passed: calculation history/success summaries, canonical result freshness, project revision conflicts and project-store fast paths. Successful history older than the bounded list remains discoverable after more than 50 failed attempts.
- Final 32 focused header checks passed across Chromium, WebKit, mobile Chromium and mobile WebKit, including signed-in save/reload, metadata preservation after drawing edits, failed-save retry, first-edit copy choice, offline/API-unavailable recovery, successful-history filtering, visible-menu accessibility and four viewport bounds.
- 54 existing design-system/accessibility and header-containment checks passed across desktop WebKit and both mobile engines, covering seven representative resolutions, resizing, keyboard focus/activation and serious/critical accessibility violations.
- 37 existing Chromium panel routes passed. The combined run also passed the then-current seven header checks.
- Eight existing authenticated two-tab and transaction checks passed: copy/replace/cancel, durable Undo/Redo and abandoned branches, failed-save recovery, grouped/chat edits and explicit replacement recovery. A combined pack hit the unchanged registration throttle in the next header test; the isolated final header packs passed. Production throttles were not weakened.
- Focused lint on the new header components/status hook/tests passed. The previously existing save-hook dependency warning remains; it is not a new zero-warning whole-repository claim. Diff whitespace checks passed.

## Scope and remaining validation

No deployment, purchase, live-customer modification or paid provider call was made. Verification used a local production build, disposable accounts and SQLite storage. PostgreSQL-specific JSON lookup syntax is implemented but was not exercised against a live PostgreSQL service; hosted backend/frontend smoke verification remains a release requirement. Mapbox, paid imagery and unrelated engineering engines were not revalidated by this UI milestone. Firefox is not included in the browser evidence.

Phase 2.2 is next: Brief / Explore / Analyze / Review / Deliver as non-restrictive workspace presets that retain the same project and drawing. Ask whether each preset should reopen its last-used panel or always open its default panel before proceeding.
