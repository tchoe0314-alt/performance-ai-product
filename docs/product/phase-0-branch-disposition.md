# Phase 0 historical branch disposition

Review date: October 2, 2026. Baseline `c6626735` plus current integration changes. No historical branch has been deleted or automatically merged. The local inventory includes 141 heads; 105 are ancestry-contained and 36 are not. Patch identity is a triage aid, not feature/runtime proof.

## Inspected unique historical work

| Branch | Finding | Disposition / remaining evidence |
| --- | --- | --- |
| `codex/canvas-cad-interaction` | `9223a8d5` added drawing tools to the older monolithic page/preview and types. Current drawing behavior lives in extracted dashboard/preview systems; full browser tests cover drawing, selection, transforms and history. | Preserve historical implementation. Do not reintroduce the old monolithic page. Detailed command-by-command comparison remains open. |
| `codex/chat-174-layer-style-manager` | Original layer-style tests are present; their diff is a review-language assertion, and current CAD layer/style handlers exist. | Active implementation is the current CAD model/workflows, not a competing branch copy. Full backend suite verifies these tests; do not merge merely to change ancestry. |
| `codex/chat-221b-prove-drafting` | `73610118` changed the older preview component. Current browser suite verifies typed coordinates, snapping, join/split, hatch, editing and drawing controls. | Preserve historical implementation; use current extracted preview path. Compare any residual unique behavior before removing the branch. |
| `codex/railway-imagery-gateway-service` | `b07c6520` switches the repository's Railway config from the primary API Dockerfile/health path to the imagery gateway. | Service-specific configuration, not an appropriate main-product merge. Preserve separately; primary API config remains authoritative. Any gateway deployment requires separate approved targeting. |
| `codex/vision-detector-v3` | `3f42afaf` contains substantial evidence-integrity, readiness, public bootstrap and training work absent from HEAD, not just patch-equivalent history. | Preserved experiment; not claimed as part of the verified product. Founder scope question is open before integrating this separate subsystem. Do not claim its readiness or delete it. |

## Patch-equivalent heads

Inventory patch comparison confirms no unique patches for several non-contained heads, including symbol library, CAD history/chat commands, provider source packs, civil surfaces, hydrology, water/fire flow, hosted operations, generate/deliver, project reliability, AI-realism preview, naming trust, preview realism, workspace controls, object manager, visualization performance, ground-truth hardening, learned segmentation and launch-readiness work.

These are preserved as history. Equivalence proves that Git can find matching patch IDs; it does not replace tests of the active implementation, account for later changes, or approve every historical artifact.

## Still open

Follow-up inspection found the historical CAD dimension test unchanged from `90000ec4`, grip tests unchanged from `4657166e`, and PDF-to-CAD tests unchanged from `6eb9f3d2`; layer/style tests differ only in review-language wording. Current model exposes annotation creation/traces and grip editing; current chat workflows implement PDF-to-CAD conversion and fail-closed hydrant catalog source/review requirements. These tests passed in the complete backend run. The overlapping entity-viewer/annotation/source branches therefore must not be merged wholesale merely because patch IDs differ.

The clean-UI and command-power branches have active modern successors and browser regressions (`apple-clean-ui-chat227`, `command-power-layer-chat229`) in the passing full website run. Preserve their older monolithic page changes as historical work; current dashboard/hooks/styles are authoritative. Earlier drafting chrome/hit-layer branches similarly alter the old monolithic preview, while current drawing/hit-layer behavior is verified in the full suite. This is feature-level evidence, not a claim that every historical line should survive.

Unique patches on the annotation/entity-viewer, drawn-boundary, earlier preview, auto-site-context, drafting chrome/hit-layer, clean-UI and command-power heads still need feature-level disposition. The WIP auto-site-context head includes preserved CAD annotations and unrelated pilot/legal work; it must not be merged wholesale into the tested baseline. Record named retained/superseded/excluded behavior before claiming all branches consolidated.

No clean release commit or deployed revision is established by this document.
