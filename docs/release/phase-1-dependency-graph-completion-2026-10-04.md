# Phase 1.4 — Local verification, 2026-10-04

Status: complete locally. Not deployed; hosted release verification remains separate.

## What changed

Implemented explicit relationships for every roadmap category: road/parking, building/parking, building/setback, road/cul-de-sac, access/road, pond/drainage area, utility/building and geometry/quantity. Follow, Ask, Fixed and Independent are supported. Ask is the new-link default; selecting another policy is an explicit user choice.

The shared placement boundary checks ordinary writers, including bulk transformations. Inspector/chat planners stage complete graph proposals. Accepted snapshots retain related objects in Phase 1.3's durable history. Graph integrity, missing targets, competing drivers and cycles are validated in the browser and backend. Fixed target changes also fail at the locked save boundary until the relationship policy is explicitly overridden. Canonical owned dependency projections are rebuilt from object intent, not trusted from client claims.

Layout alternatives include dependency effects before scoring/previewing. Choosing Apply approves that exact layout, while stale alternatives or newly unpreviewed moves remain protected. Rectangular setback offsets and bounded parametric cul-de-sac widths are preserved; general related geometry retains its dimensions/offsets and remains review-only.

## Failures found and repaired

- Undo followed by Redo to load-time geometry could be silently skipped by autosave. Successful saves now advance the comparison baseline to the exact saved request, not the original load or a newer unsaved edit.
- Applying an already selected layout could prompt again without applying the chosen option. Dependency effects are now included in the preview; explicit Apply commits the approved preview while preserving Fixed and stale-source safeguards.
- Screenshot review found the desktop canvas toolbar covering the approval card. The card was moved below it and its wording shortened; general review-required warnings are not shown as a green clearance claim.
- New test fixtures were corrected to wait for asynchronous saved metadata and to use the Draw panel for bulk controls. Assertions and existing regression tests were not weakened.

## Verification evidence

- Final functional production build and TypeScript validation passed.
- 371 backend tests plus 44 subtests passed across project/canonical persistence, graph integrity, transactions, calculation/history freshness, immutable exports, jobs, conflicts, lifecycle/privacy, migration and collaboration. A subsequent 41-test dependency pack also passed, including two additional negative cases for forged canonical edge projections, null parking metadata and duplicate edge identity. Repeated coverage is not summed as a new total.
- All 175 existing Chromium regression checks passed after functional corrections, including object controls, saved history, grouped/native geometry, two tabs, commercial edits, layout alternatives and recovery notices.
- A 57-test targeted Chromium pack passed: 34 new graph contracts, four new real authenticated website workflows and 19 existing canonical command/layout checks. Road-width transition regeneration, setback offsets, all policies, stale approval rejection, quantity refresh, bulk approval and saved Undo/Redo are covered.
- Desktop WebKit and mobile Chromium each passed seven real-website workflows before the final presentation-only correction, covering the four new dependency workflows and three existing classification/group/linework workflows.

- On the final production build, 28 Chromium checks passed covering the new dependency workflows, existing canonical commands/layout alternatives and durable saved transactions. The approval card is asserted below the desktop toolbar and its buttons are checked for clickability.
- On that same final build, all four new website workflows passed in desktop WebKit and mobile Chromium (eight checks), and seven workflows passed in mobile WebKit, including classification, grouping and editable linework. The final approval card uses an opaque background to prevent underlying text showing through.
- The final six-check persistence/export pack passed: canonical edit/save/reload, stale saved-result protection, first-edit copy/replace/cancel across tabs, and actual preliminary PDF/DXF downloads with owner isolation.
- Whitespace validation passed. Scoped lint of the dependency implementation passed; a shared save-hook dependency warning and existing library warnings remain, so this is not a claim of a warning-free repository.

All testing uses disposable local accounts and isolated local backend storage with paid AI/image providers disabled. No production customer edits, deployment or purchases occurred. Existing library deprecation warnings remain. Temporary evidence is under `/tmp/civora-phase14-*`, not a durable hosted release artifact.

## Scope and next work

This milestone completes explicit concept-plan dependency behavior, not engineering certification, automatic surveyed endpoint attachment, utility routing, arbitrary setback offsets or hydrologic delineation. Quantity annotations are draft area/length values, not engineering calculation results. Independent associations do not infer clearance, and existing stale-calculation and source-review gates remain required. Hosted operational proof remains separate.

Phase 1.5 is the design system: consistent typography, spacing, panels and controls, plus understandable visual states for selected, fixed, following, stale, blocked, unverified and conflicting objects. No implementation of 1.5 is claimed here.

Architecture: [dependency graph](../product/phase-1-dependency-graph.md).

Subsequent milestone: [Phase 1.5 compact design system completion](phase-1-design-system-completion-2026-10-04.md).
