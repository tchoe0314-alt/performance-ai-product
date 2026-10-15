# CIVORA CANONICAL MODEL PLAN

Baseline 2026-10-15 / ab7db888e85fb9b6125551ecff769d08e0ca7322. **Proposed design and verification; no schema/data/code change performed.**
Issues CAN-01–04, SEC-10 alias, ENG-05, TEST-03; packages P02/P05/P09/P14–P16/P20/P22. Authoritative task details/effort in backlog.

## 1. Current representations and transformation map

| Representation | Existing owner/shape | Transformation/use | Intended ownership boundary |
|---|---|---|---|
| canonical_project_v1/civora_project_v1 | Versioned aggregate; geometry collections, units, CRS, sources, results/revisions/export records | canonical_record.seal_record/project_view; canonical_canvas adapters | Persistent design aggregate, not every computational object |
| civora_object_v1 | Defined object geometry, type, quality, provenance/relationships | site_objects.object_definition/placement_from_definition; sealing | Stable identity and editable geometry definition inside aggregate |
| BuildingPlacement | Frontend editing/render representation for many types | withCanonicalCanvasSnapshot / resolveCanonicalCanvas, UI edit commands | Lossless UI projection; never an independent authoritative design |
| ProjectInput.manual_fields | Legacy/UI planner input projection | resolve_canvas_input/reconcile_canvas_save; legacy saves | Explicit compatibility adapter, not parallel owner of objects |
| meta.site_inputs | Source/project requirements/context | canonical site.site_inputs_v1 and UI adapter | Canonical input/source owner; legacy projection tagged |
| ProjectModel | Computational zones/objects/geometry in geometry_core | planner translations and stage generation | Derived engine model keyed to input+engine revision |
| ProjectManager | Metrics, dependencies, stage state, snapshots/transactions | planner orchestration and reactive graph | Execution-specific state, not editable source truth |
| final_plan.actions/meta | Generated actions, discipline summaries, export-ready views | canonical results, report/export adapters | Immutable derived result with input/engine/method identity |
| calculation_history | Archived source inputs/results/signatures/disposition | save_calculation_result binds and activates matching results | Append-only calculation provenance; active pointer conditional |
| edit_transactions/history | Editable-input snapshots/diffs/branches | UI observe/replay + server ledger validation | Design edit history; independent from result approval/archive |
| artifact/export history | Scope, manifest, result/input/revision reference | current_geometry_export/artifact_workflows/export sidecar | Immutable snapshot identity; cannot certify later design |
| raw imported file | Original bytes plus source metadata | import candidates/accepted geometry and derived surfaces | Immutable original source ID/hash, accepted derivatives new IDs |

Current path: UI projection → canonicalCanvasProject → API ProjectStore validation/sealing → JSON aggregate storage; planner resolves compatible ProjectInput → ProjectManager/ProjectModel → final_plan → bound result/canonical facets → export. Reverse load reconstructs compatibility/UI views. Revisions/units/source records must survive each arrow. Diagram and source evidence in master/issue register.

Ownership does not require one giant mutable object. Geometry, inputs and immutable results can have distinct representations if identities/dependencies and transformations are explicit and proven.

## 2. Proposed authoritative ownership contract (ADR-01)

| Concern | Owner | Write authority / invariant |
|---|---|---|
| Editable geometry and IDs | canonical objects | Approved edit transaction/CAS only; stable IDs, no silent regenerated IDs |
| Engineering basis and requirements | canonical input fields with units/source status | Source/assumption-specific command; accepted is not verified |
| Units, CRS, vertical datum and registration | canonical site + surface metadata | Explicit reviewed transform/version; unknown remains unknown |
| Source bytes and provenance | immutable source registry | Unique source/hash and derived_from links; original preserved |
| Dependencies | versioned graph with typed input/output facets | Validate referents/type/cycle; one declared geometry driver or explicit reviewed resolver |
| Results | immutable calculation record | Engine writes new record; input signature/version/control-plane policy required for activation |
| Quantities/cost | versioned derived facets with lineage | Depend on exact geometry/material/prices; not free-floating editable totals labelled computed |
| Revisions | server generated design CAS plus scoped metadata/result revision | Client cannot mint/reuse approval to override changed design |
| Reviews | append-only attributable workflow record | Reviewer action bound to exact artifacts/inputs; professional authority separate |
| Exports | immutable export snapshot/manifest | Saved current input or accepted result, explicit scope; rechecked before publication |
| UI state | per-user workspace preferences | Cannot alter engineering units/control or invalidate model by mere selection/pan |
| Execution checkpoints | job-owned immutable references | Never recursively copied into editable design controls |

Do not introduce schema v2 until ADR and lossless migration are approved. Proposed additive extension can carry model/source/engine versions; old reader parity must be shown. Unknown extension keys preserved by adapters; unsupported future schema rejected safely, not dropped.

## 3. Dependency graph and invalidation policy

Each edge declares producer facet/version, consumer input facet/version, relationship semantics, units, expected recomputation cost, freshness signature and cycle behavior. Current object geometry links and broader stage DAG remain separate layers with explicit mapping. A DAG-only geometry driver is not sufficient for iterative engineering feedback loops; unsupported cycles rejected; supported coupled solver groups require explicit convergence contract and are not added casually.

| Change | Direct/downstream closure to verify | Behavior |
|---|---|---|
| Road translation/width/alignment | Road edges/curbs/markings/dimensions; adjacent access/parking relationships; grading→drainage→pipes/coordination→earthwork→quantity→cost→exports | Parametric geometry/cheap checks live; ask/follow/fixed policies; heavy results stale and explicit confirmation |
| Road profile/elevation | Stations/sections/grades/ties; drainage/cover/crossings/earthwork and downstream quantities | No automatic vertical inference; dirty affected computations and block calculated exports |
| Surface/breakline edit | TIN/grid/contours/slopes/flow/catchments; pipe cover/inverts where dependent; volumes/quantities/cost | Update source version, invalidate only proven closure; unknown closure conservatively expands |
| Basin/drainage edit | Storage/stage-discharge/hydrograph/outfall/network; grading/earthwork/landscape/quantities | Heavy hydrology explicit rerun; previous approved result remains archived, never current |
| Utility movement/depth | Length/profile/cover/connections/clearance/clusters; trench quantities/cost; dimensions/exports | Cheap geometry checks live; unknown depth/datum review, not clear |
| Building move/resize | Footprint/attached parking/access/setbacks/utility links; impervious area/hydrology/grading; quantities/cost/dimensions | Respect protected/fixed references, atomic proposal approval; no fabricated automatic engineering solution |
| Price book/version change | Cost schedule only if geometry/quantities unchanged | Explicit price basis approval, cost stale; no need to recompute unrelated geometry |
| Standards/source replacement | Rules and derived inputs linked to source; corresponding discipline outputs/exports | Versioned supersession; source acceptance does not retroactively approve results |
| Units/CRS/datum change | All geometry, registration-dependent results/reviews/exports | Explicit transform required; if conversion unknown, block affected analysis, preserve original |
| Presentation/visibility/selection | Rendering only unless semantic classification changed | Hidden physical object still contributes where physical; ignore UI-only state in engineering fingerprint |
| Group/combine/uncombine | Physical identity/quantity coverage and selected dependency sets | No double counting or hidden removal; source IDs and undo preserved |
| Undo/redo/branch | Same facet changes as equivalent forward edit | Recompute/invalidate based on target revision, never reuse newer result based only on label |

Freshness states: current, stale, unknown/unverified, failed, archived; reviewed status is orthogonal and revision-bound. Automatic lightweight regeneration may never consume paid providers or override user fixed geometry. Heavy jobs capture immutable source/version; cancelled/nonconverged jobs cannot activate. Review/export race rechecks model version/role immediately before publish.

Regression oracle: table-driven perturbation on each input facet expects exact dirty closure, result archive vs activation and unchanged facet IDs. Compare approved partial rerun to full deterministic rerun on same inputs; check missing edge via mutation testing. Numerical equality alone does not preserve review validity if source/method changed.

## 4. Complete writer inventory and concurrency

Initial static writer inventory (must expand before P09 implementation):
- UI save/shell: project_workflows.py and useDashboardProjectSave.
- ProjectStore direct SQL: metadata update, save_calculation_result, candidate review, save_project_shell, save_project, duplicate/archive/delete/restore, memberships/comments/reviews/presence/memory.
- project_snapshot.save_project_snapshot wrapper already supplies design and result revisions when snapshot token exists.
- job_workflows generation/source snapshot and direct apply/staged result paths.
- chat_workflows orchestration evidence writer and chat_memory full-record save at5607.
- source_context_workflows write path; plan_pdf_workflows save and acceptance.
- artifact_workflows export finalization/history; queued export role/freshness changes.
- imports/custom type/preferences and server migration/backfill paths.
- user/operator account lifecycle and backup restoration, which must not bypass project ownership.

For each enumerate location, transaction/read/write sets, actor, authorization, revision tokens, side effects, idempotency/retry, permission recheck and publication phase. Search both service methods and raw UPDATE/INSERT projects; tests/protocol stubs are not real writers.

Proposed strategy:
1. Design edits require server CAS on current design revision inside one transaction. SQLite BEGIN IMMEDIATE / PostgreSQL row lock or conditional UPDATE must be atomic, not read-check then unlocked write.
2. Metadata owner patches update only owned keys with scoped revision if necessary; comments/presence in separate rows must not race-replace designs.
3. Calculation completion inserts historical record regardless of changed design, then activates only on locked signature/version match and valid success/scope/permission. Never copy captured inputs over current edits.
4. AI/delayed commands carry immutable base revision, intent/idempotency key, input/source versions and allowed write-set. Conflict returns409 with reload/copy/explicit replace options; no blind full-snapshot retry.
5. Export capture/publish validates revision/result/scope/permissions both before work and after artifact creation. Failed publication leaves task-owned quarantined artifact, not current history.
6. Member revocation and account deletion invalidate queued action authority at execution/publication; operations authorized earlier are not perpetually valid.
7. Persist actor/time/transaction/parent IDs and before/after lineage. Design revisions vs immutable result hash revisions separated so a new result need not spuriously conflict with UI-only state.
8. Caller revision omission cannot bypass design protection, including internal trusted code. Legacy supported writers must use an explicit adapter/generation token or fail409; no broad legacy escape hatch.

Race matrix: UI/UI, UI/chat summary, UI/AI, UI/import accept, UI/job complete, metadata/job, result/export, grant/revoke/queued action, archive/delete/job, duplicate branch and interrupted commit. Barrier-controlled tests in both SQLite and PostgreSQL, simultaneous starts and retries, assert byte/semantic geometry, source/history IDs and permitted result disposition. No stale overwrite considered fixed merely because a sequential save test passes.

## 5. Payload budgets and references (ADR approval required)

Historical report: small Apply input about17MB and result8.5MB; current copying paths persist request_payload and input_meta/controls. Treat as historical symptom; instrument authorized fixtures before designing cleanup.

Proposed active-state design: editable aggregate stores geometry/input/provenance IDs; raw uploads live immutable in source store; execution checkpoints/results immutable referenced by ID/hash; recent history window plus complete archived ledger; archive compression with content hash; no recursive checkpoint/model snapshots. Full exports resolve references under tenant/scope authorization. Garbage collection must account for active jobs/reviews/exports/history/legal holds and never collect a referenced source.

Draft measurable budgets to approve before observing optimized results:
- Small100/medium500/large2000 drawn-object fixtures; object geometry and terrain densities explicitly defined in testing plan. Existing current-drawing export cap500objects/3000vertices remains until separately qualified; large case may require explicit graceful rejection.
- Serialized active editable document <=2x normalized editable source representation, excluding original referenced raw files and immutable results; medium target<=5MiB. Record bytes per facet and eliminate recursive expansion.
- 100 apply/save/undo/reopen cycles: active-document growth<=10% for same final geometry excluding intentionally new metadata; each added result/history record linear in its own payload, no embedding ancestors; archived history complete.
- Medium current save/load p95<=2s in approved environment; separate JSON parse/render/DB timing. Design metadata patch must not rewrite unrelated multi-MB result.
- Peak per-worker RSS <=60% declared memory allocation under approved concurrency, with no progressive leak over repeat cycles. Publish actual MB and platform allocation; if impossible, narrow supported sizes/workers instead of buying memory automatically.
- Archive retrieval target<=5s for approved medium history, checksums and semantic roundtrip exact. Interrupted compression/migration leaves original retrievable.
- Total retention/storage limits approved per account/project with truthful warnings; never silently drop historic geometry/reviews to meet a budget.

Alternative: temporary compression can reduce storage but does not fix recursive ownership; reference storage must not produce cross-tenant dedup leaks. Result reproducibility needs engine/dependency/config/source retention, not indefinite duplicate whole-model copies.

## 6. Compatibility and recovery

Version all numerical/computation semantics; preserve original source document and bytes. Run lossless migration dry-run in isolated copies with object/reference/history/source count and hash checks, roundtrip load/edit/save/reopen/export and old reader tests. Ambiguous legacy surface semantics stay unverified; ask engineer to classify. Reject unknown new schema safely. Dual-read/single-write period, explicit conflict errors, feature-controlled adoption and delayed contraction. Never mix new writes with old writer that can drop fields.

Rollback: revert code only if new data readers compatible; otherwise suspend affected mutation path and roll forward, or explicitly authorized isolated restore rehearsal before production restore. Keep archives/new manifests, never erase evidence. Complete ownership, writer and invalidation maps are prerequisites to broad refactoring (P33), not an excuse for a rewrite.

