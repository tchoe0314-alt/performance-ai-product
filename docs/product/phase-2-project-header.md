# Phase 2.1 — Compact project header

## Purpose

Keep project identity and persistence truth available without putting every field in the drawing toolbar. The project title still opens Projects. Its adjacent chevron opens one compact, bounded details menu. Existing Undo, Redo, Chat, Help and account actions remain available.

## Details and storage

- Project name uses the existing project name and `manual_fields.project_name` save path.
- Client / ID, Site ID, Address, APN / parcel and Project stage live in `project_input.meta.project_identity_v1`.
- These administrative fields do not re-anchor the map, geocode an address, modify survey/site inputs, or invalidate engineering calculations. Site ID is a user-facing identifier, not a canvas object UUID. Project stage is descriptive text, not a restrictive workflow step.
- The payload builder retains the metadata on later canvas autosaves. Accepted details immediately enter the live save reference so a queued geometry save cannot erase them before React publishes the saved project.
- Details use the existing serialized save queue, revision conflicts, generation guard and two-tab copy/replace/cancel decision. The first identity edit counts as an edit even though it does not alter a calculation fingerprint.
- Form changes are local until Save details. Cancel discards them. Failed saves retain the form for retry. Project switching closes the old form, and late responses cannot update another workspace.
- Project identity is outside the geometry Undo ledger; existing drawing Undo/Redo retains current identity. No parallel backend or duplicate project model is introduced.

## Status authority

- Saved compares the live editable input against the exact accepted request baseline. Saving and Save failed come from the existing save operation; demo work says Local only. Unsaved details is separate from persisted canvas status.
- Active revision is the backend's current revision token, read-only. Last save uses the backend record timestamp, never a client-generated success time.
- Connection distinguishes browser Offline from API unavailable. Online means the API responded to a health request; it is not a claim that every provider or engineering service is healthy. Checks have a timeout, cleanup, online/offline listeners and periodic visible-page rechecks.
- Last calculation uses persisted successful calculation history, including successful archived results. Failed attempts do not advance it. The backend summary searches beyond the bounded history list, without returning full result payloads. Missing times say Not recorded; lookup failures say Unavailable.
- Project health uses workspace blocked/updating/stale/unverified/review states. A saved project or successful draft calculation never becomes engineering Verified merely because the header is present.

## Interaction and limits

The menu scrolls within the viewport on short or narrow screens. Fields retain visible labels; icon actions retain accessible names and tooltips. Escape closes the menu and returns focus to its trigger. Read-only menus explicitly focus their close button, including WebKit where mouse clicks do not automatically focus buttons. Escape does not leak into canvas tool cancellation.

`phase2-project-header.spec.ts` covers identity versus calculation fingerprints, persisted details, geometry autosave, reload, failed-save retry, offline versus API-unavailable states, successful history filtering, two-tab copying, menu accessibility, and representative portrait/landscape bounds.

Phase 2.2 will add Brief / Explore / Analyze / Review / Deliver as non-restrictive workspace presets. It has not been implemented by this milestone.
