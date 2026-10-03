# Phase 0 implementation authority and responsibility map

## October 3 follow-up: shared object writer and plan lifecycle

The three direct `buildingPlacementsRef.current = ...` compatibility writes in object update, custom drawing and object combination were removed. These adapters now publish only through the synchronous placement owner. A source scan finds no remaining direct assignment to that named ref in the app. The custom-drawing contract uses a read adapter that throws on assignment, proves two consecutive creations use the latest shared state, and verifies persistence observes committed objects. This scan is specific evidence, not proof that every state variable has been consolidated.

`dashboardPlanExecution.ts` owns direct run, staged queue, connectivity/timeout fallback, cancellation, feedback and lifecycle cleanup. It centralizes the repeated queue request/publish paths and returns explicit completed/queued/blocked/cancelled/stale outcomes. UI and geometry/calculation ownership did not move. Workspace generation guards reject late direct/queued responses and late preview completion; cleanup respects the run-controller owner. Project open/new-project actions cancel the current direct request and release its submission/busy state. The outer chat-decision adapter checks the same generation after async boundaries before applying controls, attaching jobs or saving.

Single-system Generate and direct drainage autofix now mark systems fresh only after a completed run, not a failed, cancelled, stale or merely queued result. Connectivity fallback explains a connection interruption instead of falsely claiming timeout. Queue cancellation does not assert that a backend job already accepted by the server was cancelled; job cancellation remains its separate API/workflow.

Dashboard: 5,906 lines, 253 fewer than `522d010f`. Large state/props orchestration, project-input restoration and remaining legacy command adapters are still maintainability work, so 0.4 is not closed. No schema migration, dependency downgrade, paid service, deployment or push.

Evidence: initial shared-writer extraction passed 134 affected checks on `.next-phase04-command-review`; eight executor contracts passed; final `.next-phase04-draft-review` production build, scoped lint and type checks passed. Final lifecycle/Generate/project/save/recovery selection: 86 passed, zero failures/skips, report `/tmp/civora-phase04-execution-verified-report/index.html`. The two new mocked website regressions separately passed after correcting the test assumption that New Project leaves its drawer open. An intermediate type-narrowing error was repaired before the successful build; failed runs are not successful evidence. Final combined writer rerun is recorded separately in the execution register. Chromium-only files and opted-in four-browser/device files have distinct coverage; not every test ran on every browser, and no hosted/Firefox certification is implied.

## October 3 follow-up: command and draft-save ownership

`dashboardGeometryCommands.ts` now owns shared move/resize recognition and patch construction for the two chat adapters. Their strict/conversational grammar, target selection, feedback and canonical validation remain separate, preserving existing behavior. This is not universal intent-execution consolidation.

`dashboardProjectDraft.ts` owns draft-save single-flight handling. Concurrent callers share one request; an old request's completion only clears its own pending slot, preserving a newer request started after project reset/switch. Existing save options and IDs retain their priority, and anonymous/demo workspaces do not create saved drafts. Caller generation guards still own rejection of stale results; returning an ID alone does not bypass those guards.

The dashboard is 6,159 lines. The direct live-ref assignments in object update, custom geometry and object combination are immediately followed by the same synchronous shared placement setter; they are compatibility duplication, not independent state authorities. They remain explicit consolidation targets. Large state/props wiring and direct planning orchestration remain open; this checkpoint does not close 0.4.

Command cleanup: 101 affected checks passed on `.next-phase04-command-review` across the configured desktop/mobile Chromium/WebKit selection. Pure command contracts separately verify aliases, dimensions, metadata and source immutability. Draft contracts: three passed, covering concurrent creation, old/new pending requests, failure cleanup and auth/demo/existing-ID guards. Scoped lint and TypeScript checks passed; both fresh production builds passed after clearing three obsolete generated build caches to recover disk space. Final website draft verification is recorded in the execution register separately.

See [dependency advisory review](phase-0-dependency-review.md): production frontend, declared backend pins, installed local backend and declared optional profiles report no known vulnerabilities; one unpatched development-tool advisory remains open. This is local, scope-specific evidence, not hosted or overall security certification.

Inspected October 2, 2026 at `c6626735` plus the uncommitted integration tree. Integration branch: `codex/phase-0-integration`. This is an implementation map, not release sign-off. The full inventory reports local branches and file hashes separately; historical branches are preserved, not automatically merged or deleted.

Consolidation authority rechecked at `33c23e34`: active interference engine and default canonical review-sheet delegation confirmed; [closeout and capability/limitations register](phase-0-consolidation.md) records the final local baseline. Older line counts and checkpoint-specific results below remain historical observations, not current completion claims. Large-component and operation-adapter cleanup stays under 0.4.

## Active path and responsibility boundaries

| Concern | Active owner | Boundary / limitation |
| --- | --- | --- |
| Dashboard route | `apps/web/app/page.tsx` → `PerformanceAIDashboardView.tsx` | Route wrapper delegates to the client dashboard; dashboard is still oversized (6,350 lines at inspection). |
| Object edit transaction | `app/hooks/useDashboardObjectUpdateAction.ts` | Reads current placement ref, computes proposed edits, checks protection, plans supported dependencies, records undo, marks calculations stale and persists accepted edits. |
| Live placement authority | `app/hooks/useDashboardPlacementState.ts`, `app/utils/placementStateCommit.ts` | All dashboard placement setters synchronously commit the live ref before publishing the React presentation snapshot; no later effect copies an older snapshot back into live authority. Rapid-write contracts and 76 affected website tests passed; full-suite verification remains required. |
| Approval/commercial transaction adapter | `app/hooks/useDashboardPlacementTransactions.ts`, `app/utils/canonicalBatchTransaction.ts` | Pure planning rejects the whole batch on protected/invalid targets, defers the complete batch for Ask review and uses shared canonical commands/dependency planning. The hook owns acceptance/rejection and commercial commit orchestration, sharing placement commit, stale invalidation, undo/change recording and guarded persistence without owning geometry math. |
| Canonical update metadata/protection | `app/utils/canonicalEditCommands.ts` | Shared edit source, revision and protected-object checks; not a universal replacement for every creation/delete/bulk operation. |
| Supported dependency relationships | `app/utils/canonicalDependencyPolicies.ts` | Building-to-parking follow/ask/fixed plus explicit unlinking. Full proposal approval is snapshot/project bound. General multi-discipline graph is not implemented here. |
| Object persistence | `app/hooks/useDashboardObjectPersistenceActions.ts`, `useDashboardProjectSave.ts`, `useDashboardProjectLoad.ts`, `useDashboardProjectResultLoader.ts` | UI adapters to project serialization, saves and restoration. Backend access decisions are not delegated to UI checks. |
| Delayed action persistence | `app/utils/workspaceSaveGuard.ts`, `guardedTransactionSave.ts`; remove/restore, detected-object, draft-refresh and drawn-boundary adapters | Capture requesting workspace generation/current placement snapshot before awaiting draft creation; obsolete requests cannot begin follow-up saves or refresh newer workspaces. Detected-object request ordering also supersedes older inputs without requiring a geometry change; coalesced refresh captures identity at request time. |
| Alternatives | `app/utils/layoutAlternatives.ts` | Bounded deterministic search, complete valid pool, priority reranking and difference snapshots. Checks modeled conflicts/parking capacity; does not certify local code or professional feasibility. |
| Alternative comparison controls | `app/hooks/useDashboardLayoutComparison.ts` | Preview-only generation, cancellation and reranking read current placement/project refs. Application remains a separate snapshot-guarded transaction; comparison controls do not save or mutate project geometry. |
| Parking layout | `app/utils/parkingLayoutEngine.ts`, `previewParkingMapModules.ts` | Capacity, rows/stalls, fit and preview geometry; no silent replacement of required stall counts. |
| Interference truth | `app/utils/siteInterference.ts` | Shared category/geometry/elevation evidence assessments used by alternative validation and selected-object live feedback. |
| Selected-object feedback | `app/utils/liveConstraintFeedback.ts`, `components/PreviewLiveConstraintFeedback.tsx` | Filters interference results for current selection and renders warnings; not another independent engineering engine. |
| Cul-de-sac truth | `app/utils/parametricRoad.ts`, `culDeSacConcept.ts` | Parametric native road and standalone concept support; both require explicit roundtrip/render regression coverage. |
| 2D presentation | `components/PreviewPanelView.tsx`, `Preview2DSurface.tsx`, `PreviewPlanCanvasLayers.tsx` | Presentation coordinates must not replace stored site coordinates. Main preview remains oversized (3,180 lines). |
| 3D presentation | `app/utils/dashboardPreview3DItems.ts` and viewer components | Derives geometry from plan objects, preserves semantic IDs, distinguishes synthetic terrain and missing evidence. |
| Review-sheet presentation | `components/CanonicalCivilReviewSheet.tsx`, `app/utils/reviewSheetGeometry.ts` | Current visible canonical footprints and routes only; empty/invalid inputs are disclosed, not replaced with illustrative geometry or elevations. |
| API/application boundary | `backend/api/app.py`, `backend/application/` | Authenticated HTTP adapters and workflow services. Root planner modules remain compatible execution paths, not abandoned duplicates. |
| Persistence and access | `backend/services/database.py`, `auth_store.py`, `project_store.py` | Database schema/connection, tokens and project access. SQLite disposable tests do not certify hosted Postgres migration/recovery. |
| Recovery | `backend/services/backup_restore.py`, `backend/scripts/run_backup_restore_drill.py` | Content/schema/integrity comparison on local fixtures; hosted readiness requires actual provider evidence. |
| Planning/calculations | `planner_orchestrator.py`, `planner.py`, `core/`, `engines/` | Existing planner orchestration and discipline calculation paths, retained during stabilization. |

Frontend paths in the table are relative to `apps/web` unless fully prefixed.

## Experiments and unresolved consolidation

- `app/utils/CivoraGeometryEngine.ts` currently has no import in the app runtime. It is a separately tested prototype, **not** the authority for the visible website's interference behavior. Preserve it until its future disposition is explicitly evaluated; do not replace the active engine merely because the prototype's tests pass.
- Standalone cul-de-sac HTML is a preserved prototype and regression surface, not a separate commercial project model. Native project objects are the primary product path.
- `IllustrativeCivilReviewSheetPrototype` in `components/CivilReviewSheet.tsx` is preserved but is not the default or active product renderer. The default delegates to `CanonicalCivilReviewSheet`; illustrative content cannot stand in for saved project evidence.
- Investor materials, generated captures and historical Git branches are separate artifacts. Their presence does not make them active application dependencies. No abandoned implementation has yet been proven safe to remove.
- Cross-chat frontend integration is saved in checkpoint `82037356`; subsequent scoped integrity fixes are versioned on the same integration branch. Unrelated investor work and generated instruction files remain preserved outside the release baseline. Fresh combined checks and exact deployed-artifact evidence are still required.
- Command recognition exists in both direct chat and action-intent adapters. They now report proposed/blocked/applied outcomes accurately, but centralization of all intent execution is incomplete.
- Placement React state is a presentation snapshot of the synchronous live ref, updated through the shared placement setter. Backend/latest-result adapters still supply additional read-only representations; this is not yet a single universal canonical project schema. Phase 0 eliminates unsafe writers and establishes clear adapters without silently migrating legacy projects to the future Phase 1 schema. Direct helper assignments to the same ref remain compatibility boundaries, not independent authorities.
- Do not treat the parked prototype, selected-object filter, renderer geometry or generated planner output as separate authorities for editing the same saved object.

## Required next maintainability evidence

Extract focused transaction/alternative UI orchestration from the dashboard while retaining math in utilities; audit all placement writers, project switching and asynchronous save boundaries; document serialization/migration compatibility; rerun affected tests and then combined release-critical checks. No broad rewrite, discarded legacy state or schema migration is justified by this responsibility map alone.
# Phase 0.4 first extraction — October 3, 2026

## Dashboard routing and layout transaction consolidation

`components/DashboardPanelContent.tsx` owns presentation-only routing for all 37 `SidePanelKey` values. Props derive from the existing panel components; projects, trust, and object-manager content remain composition slots with their existing action bindings. The exhaustive switch makes an unhandled new panel a type-check failure. Discipline tabs remain outside the router. No project state, persistence authority, geometry, or engineering decisions moved into the presentation module.

Applying a layout alternative now lives in `useDashboardPlacementTransactions.ts`, alongside supported batch edits and dependency proposals. It reuses the existing shared commit/persist helpers: synchronous placements, preview invalidation, system-stale flags, one before/after Undo record, and generation/snapshot-guarded saves. The existing project/source snapshot rejection and save-failure messages are preserved. `useDashboardLayoutComparison.ts` remains preview-only. This does not turn every legacy operation into a universal transaction.

The dashboard is now 6,172 lines, down 138 from 6,310. Its large state/props orchestration and remaining command adapters still need decomposition. No new schema, dependency, deployment, purchase, or push.

Evidence on fresh local production build `.next-phase04-dashboard-transactions`, served at port 3042:

- Initial routing extraction: 52 affected Chromium checks passed, including panel actions and native object integration.
- Transaction consolidation: 62 affected Chromium checks passed, including all panel routes, canonical edits, alternatives, dense commercial creation/revision, and one real disposable-backend authentication/save/reload/owner-isolation check. This preceded the stronger Undo/Redo assertions.
- Dependency proposal and stale/apply alternatives: 12 checks passed across desktop WebKit, mobile Chromium, and mobile WebKit.
- Final panel-route coverage: 148 passed, zero failures/skips (37 routes on each of four browser/device configurations). Body assertions exclude discipline navigation tabs. Report: `/tmp/civora-phase04-routing-verified-report/index.html`.
- Strengthened layout Apply/Undo/Redo: 8 passed, zero failures/skips (twice on each of four configurations). It verifies building identity and restored/reapplied X coordinates after reopening Draw, because the existing bulk Undo selects the first visible object and opens recovery chat. Initial failed/interrupted test-assumption runs are retained; they are not successful proof. Final report: `/tmp/civora-phase04-layout-undo-verified-report/index.html`.
- Affected-file lint, TypeScript checks, and production build passed. These are overlapping scoped runs, not one aggregate/full-suite result; no claim of Firefox, hosted artifact, physical Safari, all backend, or overall Phase 0 certification.

## Follow-up: command feedback, property actions, and observed UI gaps

`usePreviewCadCommandFeedback.ts` owns the bounded command-feedback state and formatted display. Undo, Redo, and other command paths now share the same 12-entry feedback writer. `usePreviewCadPropertyCommands.ts` owns layer assignment, dimension annotations, classification/property updates, and draft symbol insertion; writes still use the existing edit/create adapters. No new geometry or persistence authority was introduced. Redundant status writes immediately overwritten by symbol feedback were removed.

New website coverage exposed two pre-existing gaps: typed UNDO/REDO were unknown commands despite working buttons, and the Precision Tools toggle could remain invisible when viewing rather than editing. Typed commands now route to the existing undo/redo actions (arguments are explicitly rejected), and opening the precision dock enters its required editing mode. Tests check bounded history, unavailable history, typed undo/redo outcomes, and dock access from the initial workspace without opening Draw first.

Final affected checks: **26 passed, zero failures/skips** across Chromium, desktop WebKit, mobile Chromium, and mobile WebKit; fresh production build `.next-phase04-precision-recovery` served at local port 3042. Report: `/tmp/civora-phase04-verified-report/index.html`. Affected-file lint and TypeScript checks passed. Initial failing/new-test setup runs and the runs exposing unknown-command/mobile-dock gaps remain in `/tmp/civora-phase04-*`; they are not counted as passing evidence. The original feedback-only extraction separately passed five affected Chromium checks before the next extraction.

The preview is now 2,934 lines (246 fewer than the original 3,180); the 6,310-line dashboard still needs focused decomposition. This is partial 0.4 progress, not full-suite, Firefox, physical-device Safari, hosted, or overall Phase 0 certification. No push, deployment, or purchase.

`apps/web/app/hooks/usePreviewPointerScheduling.ts` now owns the preview's three animation-frame queues: cursor coordinates, draft/snap feedback, and canvas panning. It owns queue cancellation and unmount cleanup; it does not own project geometry, persistence, command transactions, or the map camera. The preview keeps its displayed state and interaction timing. Thresholds and latest-event coalescing are unchanged. Hook callback dependencies explicitly include the supplied React setters.

This reduces `PreviewPanelView.tsx` from 3,180 to 3,092 lines; it is a focused ownership boundary, not a completed split of the preview or dashboard. The dashboard remains approximately 6,310 lines. Remaining Phase 0.4 work includes additional focused extractions, command-adapter duplication review, and dependency/security review. Phase 0.3 platform disposition and Phase 0.5 release verification remain separate open requirements.

Verification: affected-file lint, TypeScript checks, and a fresh production build passed. The new build (`.next-phase04-pointer`) was served on local port 3042, then 15 Chromium website checks passed with zero failures or skips, covering drawing/Finish, precision tools, selection, real Mapbox panning and locking, layers, undo/history, and 2D/3D preview states. This is affected-area local proof, not a fresh full-suite, all-browser, hosted, or engineering certification. No deployment, purchase, or push was performed.
