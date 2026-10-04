# Aesthetic layout pass — 2026-10-03

Scope: preserve existing branding and canvas-first layout; repair confirmed clipping/crowding. User preference questions about broader redesign and problem devices remain unanswered. This pass is local, not deployed.

## Confirmed and repaired

1. Deliver's four-column export controls squeezed Quantities: live DOM measured content width 77px against client width 59px. Use two columns independent of window width because the desktop drawer remains 320px wide.
2. Draw's four-column layer action cards squeezed Select: measured content width 60px against client width 48px. Use two columns in those cards.
3. Phone command composer clipped the second line of its placeholder. Allow 60px minimum height below the small breakpoint and permit the flex input to shrink; preserve its accessible wording and command behavior. Existing measured dock-height handling repositions the drawer.

## Verification

- Live demo UI inspected for Setup, Draw, Generate, Review, Deliver. This is not an exhaustive review of every expanded disclosure, modal, account state, canvas label, browser or device.
- Corrected baseline regression tests fail against the prior artifact at 1280px for both Quantities and layer Select, matching live observations. An earlier test attempt used an invalid debug panel key and failed to open the drawer; it was corrected to open Deliver through the actual UI, not treated as an application defect.
- Final production-mode local build succeeds. Scoped lint and TypeScript succeed.
- Final affected browser selection: **152 passed, no retries**, about 1.2 minutes. Layout checks cover 375/768/1024/1280/1440px in Chromium and WebKit; routes checked in both engines; object manager, command interactions and export staleness tests in Chromium. This is not 152 visual assertions or all suites in all browsers.
- New checks cover button label overflow, export containment, document horizontal overflow, phone composer clipping and phone drawer/dock separation.
- Report: `/tmp/civora-aesthetics-final-report/index.html`; images/results: `/tmp/civora-aesthetics-final-results`.
- No backend, geometry, persistence or export-handler changes. No paid provider requests or customer-project edits.

Next review areas: expanded inspectors and disclosures, dialogs/projects/chat, short landscape viewports, browser zoom, long names/validation messages, and canvas-label congestion. Passing this focused selection does not certify all visual states as overlap-free.
