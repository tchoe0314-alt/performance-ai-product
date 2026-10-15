# Phase 1.1 — Canonical project model

## Authority and status

October 3, 2026: the founder explicitly requested starting 1.1 with the outstanding Phase 0.5 checks deferred. This is a sequencing change, not proof of Phase 0 completion or a deployment approval. Live mounted-file access, file-backup/recovery and the other recorded release holds remain open.

Latest status: **Phase 1.1 is complete for the locally verified, currently supported workflows.** `canonical_record.py` owns the complete persisted aggregate and reconstructs existing engine/UI shapes as compatibility views. Geometry, project controls and site inputs, current calculation facets, quantity/cost data, generated source/assumption records, alternatives, revision/recovery records and export history are connected. Immutable archived calculations are explicitly referenced by project identity rather than duplicated into every autosave. See [October 4 completion evidence](../release/phase-1-canonical-aggregate-completion-2026-10-04.md) for final verification and limits. No production migration or deployment is claimed. Earlier checkpoints below are historical, not current completion status.

## October 4 aggregate ownership

| Existing path | Authoritative owner / boundary |
| --- | --- |
| Canvas, inspector, chat, drawn/imported placements | Canonical canvas collections and ordered workspace adapter; current save queue compiles once |
| Project/client/site/units/coordinates and custom independent records | Complete canonical document; unknown coordinates remain null; unowned records survive unchanged |
| Setup controls, program-only projects, imported source/candidate review state | `extensions.project_record_v1` input adapters and `site.site_inputs_v1`; explicit compatibility writer refresh |
| Direct/queued engine inputs | Canonical read gateway; unknown length units rejected |
| Current calculations | Owned calculation ID and result sidecar reference; result-only locked publication |
| Quantities/cost, generated sources/assumptions, alternatives | Owned canonical collections; legacy result routes reconstruct views |
| Archived calculations | Immutable `project_calculation_history` reference scoped to the project; authenticated history routes |
| Workflow versions and explicit replacement backups | Owned `revisions` records; compatibility metadata projected on reads |
| Export/download history | Owned `export_history`; metadata update and export finalization share locked persistence |
| Server alternatives/job-revision/chat-feedback read-modify-save | Snapshot revision guard; competing edits return 409 instead of restoring old geometry |
| Structured JSON | Authenticated `/api/projects/{id}/document` hydrates the current result; schema serializer and normal new-project save round trip it |

The active document is the owner, not independently editable duplicate React stores. Large calculation payloads retain their existing sidecar storage; canonical quantity/source/assumption/alternative facets are removed from that payload and reconstructed for compatibility readers. Archive/file references remain explicit: a current-document JSON round trip is not a complete database-and-file disaster-recovery backup.

Existing legacy projects are not bulk rewritten. Their first normal design save retains `legacy_project_backup_v1` and a `canonical_migration_v1` report before conversion. Metadata-only export/history updates do not silently migrate legacy inputs or hide legacy results. Conversion does not invent units, a survey frame or engineering verification.

Two tabs may open the same project without copying. On the first edited save while another tab is present, the user chooses **Save as a copy**, **Replace original**, or **Keep editing**. Copies get a separate project identity and each tab retains its own active-project session. Replacing requires the current revision and retains a bounded recovery snapshot. Keeping edits unsaved blocks silent saving and warns before leaving. Backend revision checks independently reject competing modern saves. Old clients without revision tokens remain compatible; presence detection is same-browser convenience, not the cross-device correctness mechanism.

Phase 1.2 standardized per-object definitions and the agreed drawing/classification/group authoring workflow are now implemented and verified locally; see [stable object definitions](phase-1-stable-object-definitions.md). Phase 1.3 still owns a unified durable transaction ledger covering every operation. This milestone does not claim complete engineering validation, durable undo stacks, hosted/Postgres operational proof, or clearance of deferred Phase 0 release gates.

The next local checkpoint adds retained background-calculation history and a result-only transactional save boundary. Canonical canvas calculations that no longer match saved project inputs are archived, not activated, and cannot rewrite project geometry. Website job-result publication also checks archive/freshness status. This is scoped result-write protection, not a general cross-session revision policy or completion of result/quantity migration. See [calculation history evidence](../release/phase-1-calculation-history-2026-10-03.md).

October 4: supported object edits now have multi-step session undo/redo, and new
calculation bindings are checked against unsaved live inputs before result/preview
publication. Same-workspace late direct results can be retained as history-only.
Durable edit-stack persistence, quantity ownership, and general revision conflict
handling remain open. See [undo/live-input evidence](../release/phase-1-undo-live-calculation-freshness-2026-10-04.md).

October 4 follow-up: newly bound calculation results now include quantity/cost
snapshot references. The quantities panel identifies previous totals, new website
exports check unsaved live inputs, and backend DXF/JSON/PDF export entry points
reject archived or saved-input-stale results. Existing artifact downloads remain
separate. This is reference-based compatibility integration, not full canonical
quantity ownership or general concurrent-save protection. See
[quantity/export version evidence](../release/phase-1-quantity-export-versions-2026-10-04.md).

October 4 export-race follow-up: workflow metadata now merges under a database
lock without rewriting geometry, session state or latest calculations. Export
finalization compares its result against the locked saved inputs; mismatches are
retained as labelled historical downloads, not published as current exports.
General competing editor/autosave revision conflicts remain open. See
[atomic export evidence](../release/phase-1-atomic-export-finalization-2026-10-04.md).

## Document owner

`backend/services/canonical_project.py` owns the version `civora_project_v1`, creation, structural validation and deterministic JSON serialization. The optional project-input slot is `canonical_project_v1`.

The document contains project/client/site information, units, coordinate system, parcel geometry, buildings, roads, access points, cul-de-sacs, parking, sidewalks, setbacks, easements, landscape areas, stormwater features, grading concepts, utilities, annotations, constraints, dependencies, sources, assumptions, calculation results, quantities, alternatives, revisions and export history. Custom data belongs in `extensions`.

Unknown units, horizontal CRS, origin and vertical datum are explicit nulls; they are not silently interpreted as surveyed feet or an established elevation datum. Collection contents remain object dictionaries at this checkpoint: detailed geometry, unit compatibility, object identity, reference validation and calculation freshness are not yet enforced. Those must be proven before consumers switch to this model; standardized object definitions are Phase 1.2.

## Persistence rules

- A canonical document is a complete snapshot, not a sparse patch. Every section is required.
- Both workflow and database merge boundaries replace a supplied canonical snapshot whole. Empty arrays, zero and false are preserved, so deletion cannot resurrect an old object through legacy merge behavior.
- Omitting the canonical slot preserves an existing snapshot. Null, incomplete, unsupported-version and structurally invalid documents are rejected rather than clearing it.
- Existing legacy saves retain their established merge behavior. Both formats can coexist during migration, but legacy consumers have not been redirected: there is no claim of one operational authority yet.
- Values must be finite JSON data; unknown top-level sections, duplicate serialized keys, non-finite coordinates and cyclic data are rejected. Validation returns detached data and errors do not echo submitted values.
- Invalid documents at the application save boundary return HTTP 422 before persistence. Existing permission checks continue to apply.

These rules do not implement optimistic concurrency, object-level edits or engineering validity. Canonical snapshots must not be exposed to multiple independent UI writers until the owner/adapters and revision-conflict policy are implemented.

## Next required work

1. Inventory the actual read/write paths for manual geometry, generated results, chat edits, imports, alternatives and export history.
2. Build explicit legacy adapters with lossless fixtures and identify ambiguous units/coordinates instead of guessing.
3. Bind existing editors/calculations to one document owner; avoid independently editable copies. Define revision/stale-write rejection before enabling new writers.
4. Verify old-project migration and full create/edit/save/reopen/export workflows, then reassess 1.1 completion against every roadmap section.

No complete legacy conversion is implemented in this checkpoint. This intentionally avoids pretending that unverified generated geometry and imported survey coordinates share one frame.

## Connected canvas and calculation checkpoint — October 3

`apps/web/app/utils/canonicalCanvasProject.ts` and `backend/services/canonical_canvas.py` provide the compatibility gateway. The existing placement writer, command pipeline and save queue remain the live owners; no second editable React store was introduced.

Canvas placements are retained losslessly as `canvas_placement_v1` records in the appropriate document collections. Site placements live in `parcel_geometry.canvas_placements_v1`; unsupported/custom object kinds are retained in `extensions.canvas_other_placements_v1`. `extensions.canvas_workspace_v1` stores the exact legacy manual-field/control projections plus ordered references to the owned placements. These wrappers are transitional representations, not the final standardized Phase 1.2 object schemas. Unrelated canonical client/revision/source data and records not owned by the canvas adapter are preserved.

Project Save compiles the current input at its existing serialized boundary. Silent-save acknowledgements retain the canonical document while keeping newer live geometry, so following autosaves cannot discard unrelated client data. On Open, restoration validates references before publishing project state and uses the canonical canvas over stale legacy geometry. An explicit empty canvas does not regenerate old building, accepted-candidate or pending-program geometry from compatibility shadows. Legacy projects without an adopted adapter keep the prior restore behavior and adopt the bridge on a normal canvas save; no bulk rewrite occurs.

The existing backend full/shell save paths reconcile newly submitted canonical snapshots before storage. Still-unmigrated internal legacy writers refresh the adapter when they change manual inputs; source-review metadata stays outside the geometry snapshot and can continue updating independently. This is compatibility handling, not cross-client concurrency protection.

The central plan executor seals a detached document **after** chat/inspector request overrides, so direct runs and queued/fallback runs use the same geometry even if the caller's original data later changes. API request models retain the canonical field, omit the absent optional field for old callers, and validate malformed documents/references before queue submission. Calculation preparation and the engine boundary read the canonical manual view. Canonical length units override stale compatibility units; calculation execution rejects unknown units instead of assuming feet. Existing chat command execution then operates on that resolved view.

Remaining completion work: canonical ownership of calculation results/quantities, authoritative source/assumption relationships, alternatives/revisions/export history, object/reference/geometry contracts, and a revision-conflict policy for simultaneous sessions. Independent canonical records not owned by this adapter remain preserved but are not automatically rendered or interpreted as engineering inputs.

Final verification and exact scopes: [connected-model evidence](../release/phase-1-canonical-canvas-integration-2026-10-03.md). No deployment or spending occurred; Phase 0 deferred gates remain open.

## Verification — October 3 checkpoint

Final affected-area selection: **90 passed plus 11 subtests**, no failures. Covers canonical structure and JSON round trips; detached validation; malformed/future/duplicate-key/non-finite/cyclic rejection; both merge layers; real SQLite close/reopen; full and shell saves; full application save and autosave; deletion preservation; legacy data and generated-result preservation; access isolation; team/admin and collaboration/lifecycle behavior; legacy migrations; data lifecycle/backup tests. One existing Starlette/httpx deprecation warning remains. Whitespace validation passed.

This is backend/local evidence, not a browser workflow test of a new canonical editor or proof of production/Postgres migration. No website code was changed, no deployment or purchase occurred, and no legacy projects were rewritten.
