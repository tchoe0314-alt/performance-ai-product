# Phase 0.1 — Consolidation closeout

Recorded October 2, 2026. Status: **complete for the local stabilization baseline**. This does not close Phase 0.2–0.5 or approve a deployment. Product authority remains the founder-approved master roadmap.

## Exact baseline and inventory

- Application checkpoint: `33c23e34918032dd151f913024d4a9d60e4fed34`, on `codex/phase-0-integration`. The tracked tree was clean before this documentation-only closeout.
- Full read-only snapshot: [inventory](phase-0-inventory-33c23e34.json). It records 1,173 non-ignored tracked/untracked paths, categories, source/documentation hashes, local branches and worktree checks. Ignored runtime dependencies, generated build directories and private files are outside this inventory; sensitive-named files receive metadata only, never content hashes.
- Snapshot source fingerprint: `0bebf9fbdbe51f0e0ec4e4ee12f10d5b45bd6ef5c655bfb5559551a7a1afdc64`. This includes inventoried untracked source/documentation and is not the release artifact identity. Adding these closeout documents necessarily changes a later inventory fingerprint.
- 141 local branches: 105 ancestry-contained; 36 not contained. All **26 distinct non-equivalent patches** are explicitly accounted for in the [disposition register](phase-0-branch-disposition.md). A fresh programmatic comparison found no undocumented unique patch.
- 79 registered worktree entries: 16 directories exist, including the integration checkout. The other 15 existing checkouts have zero pending tracked or untracked edits. The remaining 63 entries refer to missing historical directories; these are not active copies or evidence of recoverable uncommitted work. Git metadata and branches were preserved, not pruned.
- Integration checkout has 108 untracked file paths across `.codex-finalizer-investor-deck/`, `investor-kit-build/`, `investor-kit/`, `apps/web/AGENTS.md`, `apps/web/CLAUDE.md`, and `scripts/capture_workflow_demo.mjs`. These user-owned artifacts are preserved and excluded from the tested tracked product baseline. No secret contents were read for consolidation.

The snapshot predates the new closeout documents. Its counts are evidence of that checkpoint, not a permanently fixed count for future HEADs. Reproduce with `python scripts/phase0_inventory.py --output /absolute/local/inventory.json`; compare branch patches with the disposition register before updating the baseline.

## Overlap and experiment decisions

| Overlap / experiment | Authoritative decision |
| --- | --- |
| Historical monolithic dashboard, drawing, object-manager, shell and command variants | Current dashboard, focused hooks and preview components own runtime behavior; preserve historical branches rather than merging obsolete page implementations. Named feature-level dispositions explain what is retained or superseded. |
| Placement snapshots / saved results / rendering geometry | Synchronous live placement ref plus shared setter own current editable placements. React state presents that value; saved results and renderer geometry are adapters, not independent edit authorities. See the [ownership map](phase-0-architecture.md). |
| Interference engines | `siteInterference.ts` is the active assessment engine; `liveConstraintFeedback.ts` filters its results. Unimported `CivoraGeometryEngine.ts` is a separately tested, inactive prototype. |
| Civil review-sheet implementations | Default `CivilReviewSheet.tsx` delegates to `CanonicalCivilReviewSheet.tsx`. The named illustrative prototype is inactive and must not invent evidence for a saved project. |
| Standalone cul-de-sac / native road | Native editable project objects are the product path. Standalone HTML remains a preserved prototype and regression/import surface, not another project model. |
| Main API / imagery gateway deployment configuration | Primary API configuration remains authoritative. Historical gateway-specific deployment configuration stays separate; no deployment is authorized here. |
| Vision V3 | Substantial separate subsystem preserved on its historical branch and excluded from this baseline. No readiness claim or integration commitment. Future integration requires an explicit subsystem decision. |
| Investor/legal materials and generated captures | Separate, unapproved artifacts; not runtime dependencies or published legal terms. Preserve them for later review. |
| Remaining large components and command/state adapters | Known maintainability debt, recorded under 0.4. Identifying ownership closes consolidation; it does not claim the universal Phase 1 model or every operation has already been centralized. |

No abandoned implementation was proven safe and necessary to delete in this pass. No files, branches or worktree records were deleted. Preserving classified inactive/history-only work is intentional, not silently shipping it. Cross-chat reconciliation is recorded in the disposition register; other chats' reported fixes, ratings or deployment permissions are not substituted for current evidence.

## Supported capability register

“Supported” here means present in the local application and exercised by the recorded tests, within the limitations below. Browser coverage mixes controlled-response workflows, pure contracts and real-local service checks; it is not uniformly hosted end-to-end proof.

| Capability | Active boundary / evidence |
| --- | --- |
| Objects and drafting | Creation, selection, movement, resize, rotation, properties, line/area drawing, precision controls, layer visibility/bulk selection and undo/redo; object-manager, drafting and command regressions. |
| Roads and cul-de-sacs | Native editable roads/cul-de-sacs, parametric dimensions, standalone geometry and import/serialization checks; cul-de-sac and native-object suites. |
| Buildings and parking | Commercial concept generation, program revisions and parking layout/reflow. Protected existing objects block whole replacement; edits use shared protection and batch planning. |
| Chat and dependencies | Existing supported building/parking follow, fixed, Ask and unlink behavior. Ask defers the entire supported transaction; rejection preserves geometry and acceptance is undoable. Not a universal discipline graph. |
| Interference and constraints | Category/geometry/elevation-evidence-aware assessments, warning feedback and supported clearance/setback metadata. Missing engineering evidence is disclosed; no blanket rule that pipes can never conflict with buildings. |
| Alternatives | Bounded search, requested count 2–10, full valid-pool reranking, modeled hard-conflict/parking-shortage rejection, comparison/apply/cancel and stale-preview protection. |
| 2D, 3D and review | Canonical footprints/routes, semantic object IDs, truth-aware source/terrain presentation and review sheets. Missing or illustrative data is not certified engineering evidence. |
| Save, reopen and access | Structured saved inputs/results, local owner-isolated project persistence and restoration, guarded late saves/project switches, account/support lifecycle checks. |
| Import and export | Current PDF/import/edit/review/export workflow and existing backend format/calculation contracts. Target-tool interoperability and professional approval remain external gates. |
| Recovery and diagnostics | Local migration/backup/restore contracts, disposable SQLite restore and prior-code fixture-read compatibility. Health identity distinguishes application version from known source revision. |

## Known limitations register

1. No exact deployed-artifact verification for this candidate; public production has not received these fixes. No push or deployment in this closeout.
2. Sixteen full-suite website skips remain unproven; map/provider credentials and hosted authentication are separate prerequisites. Complete cross-browser, exact-candidate container and CI evidence remain open.
3. The dashboard and preview remain oversized. Some legacy command, creation/delete and serialization adapters remain; the universal schema, transaction system and dependency graph belong to Phase 1, not a completed claim here.
4. Collision assessments require object semantics, geometry, elevation/depth and evidence quality. Unknown foundation/utility details cannot establish safe separation or engineering compliance.
5. Local deterministic reference projects, synthetic terrain and test imagery do not replace a real survey, utility profiles, engineer review, external CAD verification or independently validated calculations.
6. Local SQLite recovery and old-code read compatibility do not prove hosted Postgres recovery, provider backup availability, redeployment rollback or compatibility of every future write format.
7. Passing automated tests do not establish bug-free behavior, arbitrary production load capacity, construction readiness, complete security assurance or pilot readiness. Existing dependency deprecation warnings remain documented.

## Completion decision

Closeout verification: four inventory tests passed; all 1,065 tracked checkpoint paths are present in the snapshot; 994 tracked source/documentation hashes match Git at `33c23e34`; all 26 unique patch dispositions and all 15 clean existing peer worktrees were checked. New document links and whitespace checks passed. Application code, dependencies and schemas were not changed, so the existing full application results are retained rather than presented as newly rerun tests.

0.1's deliverables are now recorded: inventory, cross-chat reconciliation, overlap authority, experiment dispositions, one integration branch, a locally tested known-good checkpoint, supported capabilities and known limitations. [Checkpoint notes](../release/phase-0-checkpoint-33c23e34.md) identify the tests and recovery evidence without treating the candidate as a deployed release. Remaining feature/platform verification, maintainability and release engineering stay assigned to 0.2, 0.4 and 0.5. Phase 1 has not started.
