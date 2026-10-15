# Phase 2.4 — Project actions

## User decisions

Sharing is optional and defaults to viewer. Only the project creator can invite/remove members or change their permissions, including granting editor access. Existing admin/editor/reviewer/viewer roles remain readable for compatibility but admin members no longer manage sharing. Normal named saved edit history replaces the proposed separate milestone feature. No milestone/name prompt blocks ordinary editing or saving.

## Implementation

The header's compact Project actions menu opens existing team sharing, project identity/settings, report generation and queued DXF review export. Saved edit history uses the existing durable transaction ledger: server-sealed actor IDs resolve to account names; the creator is shown separately. The endpoint requires project read permission and returns a read-only summary rather than before/after design snapshots. Unsaved edits appear after saving. Deleted/unavailable identities remain Unknown user, not fabricated attribution. This is saved transaction history, not a new realtime collaboration protocol or audit of every cursor/keystroke.

LandXML uses the existing pipe-network writer and exchange-export boundary, including current-calculation checks, preliminary geometry validation, export audit and atomic artifact history finalization. Supported output is review-only feet-based storm/sanitary pipe-network data, not general surfaces/alignments/buildings or guaranteed Civil 3D compatibility. Empty data, unknown/nonpositive pipe length/diameter and unsupported units are rejected. Import/parse verification and review-only/external-verification flags remain explicit. No calculations or provider calls are triggered by opening the menu/history.

Native modal focus containment and local Escape handling prevent the canvas Escape shortcut from swallowing history dismissal. The menu is viewport anchored to avoid narrow-phone clipping. Existing workflows retain their save and stale-result safeguards.

## Limits

Access enforcement is server-side. Full shared-session realtime UI/read-only tool presentation, concurrent collaboration and detailed attribution for Undo/Redo cursor transitions beyond the existing transaction ledger remain Phase 8 work. This milestone does not claim those broader collaboration behaviors complete.

No deployment, provider purchase or production-customer edits. The known Generate/reactive freshness defect remains a separate release blocker. Phase 2.5 is next; it must preserve this compact interaction design while making workspace panels collapsible/resizable.
