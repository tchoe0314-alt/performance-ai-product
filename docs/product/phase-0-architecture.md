# Phase 0 implementation authority and responsibility map

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
